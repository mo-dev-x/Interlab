"""§5 SS4 certification metrics -- all computed in fp32 (SS4 invariant).

Certification collects activations fresh through the model (ED-5: never
from a stored slice, since CE-recovered structurally requires model
forwards). Every function here that needs activations takes a `model`
(`transformer_lens.HookedTransformer`) + `sae` + already-tokenized batches,
and runs the forward passes itself; nothing here reads a persisted store.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import torch
from sae_lens import SAE
from transformer_lens import utils as tl_utils

_DENSITY_MIN_LOG10 = -8.0
_DENSITY_MAX_LOG10 = 0.0
_DENSITY_N_BINS = 50


@dataclasses.dataclass(frozen=True)
class CertificationMetrics:
    ce_recovered: float
    fvu: float
    dead_fraction: float
    density_histogram: dict
    max_decoder_cosine_p999: float
    per_position_fvu: list[float]


def fp32_copy(sae: SAE) -> SAE:
    """A non-mutating fp32 copy of `sae`'s weights (same pattern as
    `interplab.interventions.hooks._fp32_copy`): certification MUST NOT
    depend on the checkpoint's native storage dtype."""
    fp32_cfg = dataclasses.replace(sae.cfg, dtype="float32")
    sae32 = SAE(fp32_cfg)
    sae32.load_state_dict({k: v.detach().to(torch.float32) for k, v in sae.state_dict().items()})
    return sae32.to(sae.W_dec.device)


def _cross_entropy_fp32(logits: torch.Tensor, tokens: torch.Tensor) -> tuple[float, int]:
    """Returns (mean_loss, n_tokens) so callers can weight across batches."""
    n_tokens = tokens.shape[0] * (tokens.shape[1] - 1)
    loss = tl_utils.lm_cross_entropy_loss(logits.to(torch.float32), tokens, per_token=False)
    return float(loss.item()), n_tokens


def compute_metrics(
    model,
    sae: SAE,
    hook_name: str,
    token_batches: list[torch.Tensor],
    *,
    decoder_cosine_chunk_size: int = 2048,
) -> CertificationMetrics:
    """Runs the full A6 metric suite over `token_batches` (each `[batch,
    seq_len]`, all sharing the same `seq_len` so per-position stats align).

    Invariants preserved: ce_recovered's baseline is zero-ablation of
    `hook_name`, same slice, same batch order as the clean and
    substitute-reconstruction passes; every computation is fp32.
    """
    sae32 = fp32_copy(sae)
    device = sae32.W_dec.device

    seq_len: int | None = None
    ce_clean_sum = ce_recon_sum = ce_zero_sum = 0.0
    n_ce_tokens = 0

    pos_sq_error: torch.Tensor | None = None
    pos_sq_total: torch.Tensor | None = None
    sq_error_total = 0.0
    sq_total_total = 0.0

    d_sae = sae32.W_dec.shape[0]
    fire_counts = torch.zeros(d_sae, dtype=torch.float64)
    total_positions = 0

    with torch.no_grad():
        for tokens in token_batches:
            tokens = tokens.to(device)
            batch, this_seq_len = tokens.shape
            if seq_len is None:
                seq_len = this_seq_len
                pos_sq_error = torch.zeros(seq_len, dtype=torch.float64)
                pos_sq_total = torch.zeros(seq_len, dtype=torch.float64)
            elif this_seq_len != seq_len:
                raise ValueError(
                    f"all token batches must share the same sequence length for per-position "
                    f"metrics; got {this_seq_len} after {seq_len}"
                )

            # Clean pass: baseline CE + the activations to reconstruct/ablate.
            clean_logits, cache = model.run_with_cache(tokens, names_filter=hook_name)
            clean_loss, n = _cross_entropy_fp32(clean_logits, tokens)
            x = cache[hook_name].to(torch.float32)  # [batch, seq, d_model]

            feats = sae32.encode(x)
            recon = sae32.decode(feats)

            def _substitute_hook(resid, hook, _recon=recon):
                return _recon.to(resid.dtype)

            recon_logits = model.run_with_hooks(tokens, fwd_hooks=[(hook_name, _substitute_hook)])
            recon_loss, _ = _cross_entropy_fp32(recon_logits, tokens)

            def _zero_hook(resid, hook):
                return torch.zeros_like(resid)

            zero_logits = model.run_with_hooks(tokens, fwd_hooks=[(hook_name, _zero_hook)])
            zero_loss, _ = _cross_entropy_fp32(zero_logits, tokens)

            ce_clean_sum += clean_loss * n
            ce_recon_sum += recon_loss * n
            ce_zero_sum += zero_loss * n
            n_ce_tokens += n

            sq_error, sq_total = squared_error_and_total(x, recon)

            pos_sq_error += sq_error.sum(dim=0).double()
            pos_sq_total += sq_total.sum(dim=0).double()
            sq_error_total += float(sq_error.sum().item())
            sq_total_total += float(sq_total.sum().item())

            fire_counts += (feats != 0).sum(dim=(0, 1)).double()
            total_positions += batch * seq_len

    ce_clean = ce_clean_sum / n_ce_tokens
    ce_recon = ce_recon_sum / n_ce_tokens
    ce_zero = ce_zero_sum / n_ce_tokens
    denom = ce_zero - ce_clean
    ce_recovered = 1.0 if denom == 0 else 1.0 - (ce_recon - ce_clean) / denom

    fvu = sq_error_total / sq_total_total if sq_total_total > 0 else 0.0
    per_position_fvu = (pos_sq_error / pos_sq_total.clamp_min(1e-12)).tolist()

    dead_fraction = float((fire_counts == 0).sum().item()) / d_sae
    density_histogram = _density_histogram(fire_counts, total_positions)
    max_cosine_p999 = max_decoder_cosine_p999(sae32, chunk_size=decoder_cosine_chunk_size)

    return CertificationMetrics(
        ce_recovered=ce_recovered,
        fvu=fvu,
        dead_fraction=dead_fraction,
        density_histogram=density_histogram,
        max_decoder_cosine_p999=max_cosine_p999,
        per_position_fvu=per_position_fvu,
    )


def squared_error_and_total(x: torch.Tensor, recon: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-(batch, position) squared reconstruction error and squared
    deviation from the batch mean, both `[batch, seq]`. FVU = sum(error) /
    sum(total); exposed standalone so the formula is unit-testable without
    a real SAE/model forward pass."""
    error = x - recon
    mean_x = x.mean(dim=(0, 1), keepdim=True)
    sq_error = error.pow(2).sum(dim=-1)
    sq_total = (x - mean_x).pow(2).sum(dim=-1)
    return sq_error, sq_total


def _density_histogram(fire_counts: torch.Tensor, total_positions: int) -> dict:
    rates = (fire_counts / max(total_positions, 1)).numpy()
    nonzero = rates[rates > 0]
    bin_edges_log10 = np.linspace(_DENSITY_MIN_LOG10, _DENSITY_MAX_LOG10, _DENSITY_N_BINS + 1)
    if nonzero.size == 0:
        counts = np.zeros(_DENSITY_N_BINS, dtype=int)
    else:
        log_rates = np.log10(nonzero)
        counts, _ = np.histogram(log_rates, bins=bin_edges_log10)
    return {"bin_edges_log10": bin_edges_log10.tolist(), "counts": counts.tolist()}


def max_decoder_cosine_p999(sae32: SAE, *, chunk_size: int = 2048) -> float:
    """ED-5 metric pin: per feature, the max cosine to any *other* feature's
    decoder direction; the 99.9th percentile of that per-feature
    distribution, computed exactly via chunked matmul -- never sampled."""
    w = sae32.W_dec  # [d_sae, d_in], fp32
    w_norm = w / w.norm(dim=1, keepdim=True).clamp_min(1e-12)
    d_sae = w_norm.shape[0]
    max_cos = torch.full((d_sae,), -1.0, dtype=torch.float32, device=w.device)

    for i0 in range(0, d_sae, chunk_size):
        i1 = min(i0 + chunk_size, d_sae)
        block_i = w_norm[i0:i1]
        for j0 in range(0, d_sae, chunk_size):
            j1 = min(j0 + chunk_size, d_sae)
            block_j = w_norm[j0:j1]
            sims = block_i @ block_j.T  # [bi, bj]
            if i0 == j0:
                diag = torch.arange(i1 - i0, device=w.device)
                sims[diag, diag] = -1.0
            max_cos[i0:i1] = torch.maximum(max_cos[i0:i1], sims.max(dim=1).values)

    return float(torch.quantile(max_cos.double(), 0.999).item())
