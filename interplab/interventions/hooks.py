"""§5 SS7 `attach()` -- the single implementation of intervention hooking.

`model` MUST already be a `transformer_lens.HookedTransformer` (SAELens's
own `hook_name`/`hook_layer` convention is TransformerLens's naming scheme;
`attach()` does not load or convert models, only hooks an existing one).
Hook registration uses `HookedTransformer.hooks(...)`, whose `finally`-guarded
context manager already gives the "zero hooks left behind" guarantee this
module's own invariant depends on.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Sequence

import numpy as np
import torch
from sae_lens import SAE

from interplab.interventions.spec import InterventionSpec


@dataclasses.dataclass(frozen=True)
class CallStats:
    """One record per hook invocation during an `attach()` context (§5 SS7
    measurement clause: "per-run logging of injected-delta norms relative
    to residual norms")."""

    delta_norm: float
    residual_norm: float


class AttachHandle:
    """The object `attach()` returns: a context manager that, after exit,
    still exposes `.stats` -- one `CallStats` per hook invocation during the
    context. Empty for `noop`, which never invokes a hook."""

    def __init__(self, inner_cm, stats: list[CallStats]):
        self._inner_cm = inner_cm
        self._stats = stats

    def __enter__(self) -> AttachHandle:
        self._inner_cm.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._inner_cm.__exit__(exc_type, exc_val, exc_tb)

    @property
    def stats(self) -> list[CallStats]:
        return list(self._stats)


def attach(
    model,
    sae: SAE,
    spec: InterventionSpec,
    *,
    prompt_lengths: int | Sequence[int] | None = None,
) -> AttachHandle:
    _check_positions_contract(spec, prompt_lengths)
    _check_direction_seed_contract(spec)

    if spec.kind == "noop":
        # Bullet 2: does not touch the stream at all -- no hook is registered,
        # not even a passthrough one. Bit-identity is structural, and there
        # is nothing to measure.
        return AttachHandle(contextlib.nullcontext(), [])

    stats: list[CallStats] = []

    if spec.kind in ("clamp", "ablate"):
        sae_fp32 = _fp32_copy(sae)
        clamp_value = 0.0 if spec.kind == "ablate" else float(spec.value_in_max_units) * float(spec.corpus_max)
        hook_fn = _make_clamp_hook(sae_fp32, spec.feature_index, clamp_value, spec.positions, prompt_lengths, stats)
    elif spec.kind == "add_direction":
        d_hat = _direction_vector(spec.direction_seed, sae.cfg.d_in, sae.W_dec.device)
        alpha = float(spec.value_in_max_units) * float(spec.corpus_max)
        hook_fn = _make_add_direction_hook(d_hat, alpha, spec.positions, prompt_lengths, stats)
    else:
        raise ValueError(f"unknown InterventionSpec.kind: {spec.kind!r}")

    inner_cm = model.hooks(fwd_hooks=[(sae.cfg.hook_name, hook_fn)])
    return AttachHandle(inner_cm, stats)


def _check_positions_contract(spec: InterventionSpec, prompt_lengths) -> None:
    if spec.positions == "generated_only" and prompt_lengths is None:
        raise ValueError(
            "prompt_lengths is required when InterventionSpec.positions == 'generated_only' (ED-4)"
        )
    if spec.positions == "all" and prompt_lengths is not None:
        raise ValueError(
            "prompt_lengths must be None when InterventionSpec.positions == 'all' (ED-4)"
        )


def _check_direction_seed_contract(spec: InterventionSpec) -> None:
    if spec.kind == "add_direction" and spec.direction_seed is None:
        raise ValueError("InterventionSpec.direction_seed is required when kind == 'add_direction' (ED-3)")
    if spec.kind != "add_direction" and spec.direction_seed is not None:
        raise ValueError("InterventionSpec.direction_seed must be None unless kind == 'add_direction' (ED-3)")


def _fp32_copy(sae: SAE) -> SAE:
    """A non-mutating fp32 copy of `sae`'s weights, resolved once at attach
    time (never per-token, per the device/dtype failure-mode note). Rebuilds
    via a fresh SAE + state dict rather than `sae.float()` so the caller's
    live object is never mutated."""
    fp32_cfg = dataclasses.replace(sae.cfg, dtype="float32")
    sae32 = SAE(fp32_cfg)
    sae32.load_state_dict({k: v.detach().to(torch.float32) for k, v in sae.state_dict().items()})
    return sae32.to(sae.W_dec.device)


def _direction_vector(seed: int, d_in: int, device) -> torch.Tensor:
    """Bullet 5: d_hat = normalize(np.random.default_rng(seed).standard_normal(d_in)),
    computed once at attach."""
    rng = np.random.default_rng(seed)
    raw = rng.standard_normal(d_in)
    unit = raw / np.linalg.norm(raw)
    return torch.from_numpy(unit).to(dtype=torch.float32, device=device)


def _resolve_prompt_lengths_tensor(prompt_lengths, batch_size: int, device) -> torch.Tensor:
    if isinstance(prompt_lengths, int):
        return torch.full((batch_size,), prompt_lengths, dtype=torch.long, device=device)
    lengths = torch.as_tensor(list(prompt_lengths), dtype=torch.long, device=device)
    if lengths.shape[0] != batch_size:
        raise ValueError(f"prompt_lengths has {lengths.shape[0]} entries but batch size is {batch_size}")
    return lengths


class _PositionCounter:
    """Tracks the absolute sequence position reached so far across hook
    calls within one `attach()` context (prefill call, then one call per
    KV-cached decode step)."""

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0


def _positions_mask(counter: _PositionCounter, seq_len: int, batch_size: int, prompt_lengths, device) -> torch.Tensor:
    """[batch, seq_len] bool mask, True where this call's absolute position
    is >= that row's prompt length. Advances `counter` by seq_len."""
    start = counter.value
    counter.value += seq_len
    abs_positions = torch.arange(start, start + seq_len, device=device)
    lengths = _resolve_prompt_lengths_tensor(prompt_lengths, batch_size, device)
    return abs_positions.unsqueeze(0) >= lengths.unsqueeze(1)


def _make_clamp_hook(
    sae_fp32: SAE, feature_index: int, clamp_value: float, positions: str, prompt_lengths, stats: list[CallStats]
):
    counter = _PositionCounter()

    def hook_fn(resid, hook):
        batch, seq_len, _ = resid.shape
        mask = None
        if positions == "generated_only":
            mask = _positions_mask(counter, seq_len, batch, prompt_lengths, resid.device)
            if not bool(mask.any()):
                # Bullet 3: masked positions are never touched -- no encode/decode
                # round trip at all when nothing in this call needs steering.
                stats.append(CallStats(delta_norm=0.0, residual_norm=resid.norm().item()))
                return resid

        x = resid
        x32 = x.to(torch.float32)
        feats = sae_fp32.encode(x32)
        clean_recon = sae_fp32.decode(feats)
        feats_clamped = feats.clone()
        feats_clamped[..., feature_index] = clamp_value
        clamped_recon = sae_fp32.decode(feats_clamped)
        delta32 = clamped_recon - clean_recon
        delta = delta32.to(x.dtype)
        steered = x + delta

        # Structural selection, not additive zeroing: masked positions take `x`
        # directly, regardless of what `steered` computed to there (a
        # multiply-by-zero mask would still propagate NaN/Inf via 0*NaN=NaN;
        # `where` never lets a masked position's output depend on `steered`).
        result = torch.where(mask.unsqueeze(-1), steered, x) if mask is not None else steered

        effective_delta = result - x
        stats.append(CallStats(delta_norm=effective_delta.norm().item(), residual_norm=x.norm().item()))
        return result

    return hook_fn


def _make_add_direction_hook(d_hat: torch.Tensor, alpha: float, positions: str, prompt_lengths, stats: list[CallStats]):
    counter = _PositionCounter()

    def hook_fn(resid, hook):
        batch, seq_len, _ = resid.shape
        mask = None
        if positions == "generated_only":
            mask = _positions_mask(counter, seq_len, batch, prompt_lengths, resid.device)
            if not bool(mask.any()):
                stats.append(CallStats(delta_norm=0.0, residual_norm=resid.norm().item()))
                return resid

        x = resid
        delta32 = alpha * d_hat  # [d_in], fp32
        delta = delta32.to(x.dtype)
        steered = x + delta  # broadcasts over [batch, seq, d_in]

        result = torch.where(mask.unsqueeze(-1), steered, x) if mask is not None else steered

        effective_delta = result - x
        stats.append(CallStats(delta_norm=effective_delta.norm().item(), residual_norm=x.norm().item()))
        return result

    return hook_fn
