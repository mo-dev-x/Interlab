"""Final-pairing mechanical acceptance harness: prove a nonzero STEER
intervention reaches the residual stream for each ratified target pairing
(google/gemma-3-12b-it + google/gemma-scope-2-12b-it, and Qwen/Qwen3.5-27B +
Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50), with full diagnostic instrumentation.

SCOPE, explicitly: mechanical acceptance only. No feature meanings, no
concept discovery, no PT-Gemma/Qwen2.5 feature identities (feature_idx here
is a bare engineering integer, supplied on the command line). The intent is
identical to scripts/legacy/gemma3_tool_diff_test.py's differential check,
extended with the target-identity validation and per-call diagnostic trace
this task's acceptance criteria require, and generalized to load paths that
scripts/legacy/gemma3_sweep.py's frozen loader cannot serve (see
final_pairing_targets.py's module docstring for exactly why not).

Nothing here edits gemma3_sweep.py, gemma3_necessity.py,
qwen_tool_adapter.py, build_qwen_feature_manifest.py, or
interplab/interventions/hooks.py. _make_clamp_hook is imported unmodified,
exactly as scripts/legacy/gemma3_tool.py already does -- this file only
wraps its OUTPUT with an observation-only diagnostic layer (see
wrap_hook_with_diagnostics), never changes what it computes or returns.
That is also how f355126's accepted zero-clamp guard and generated_only
first-token semantics are preserved rather than re-implemented: this module
reuses gemma3_tool.dose_to_absolute_clamp verbatim (imported, not copied)
for the manifest/calibration -> resolved-absolute-target arithmetic.

Nothing here downloads weights. Every loader takes LOCAL filesystem paths
and fails closed if they're missing, misidentified, or dimensionally
inconsistent with the ratified target -- see final_pairing_targets.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from interplab.interventions.hooks import _make_clamp_hook

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import final_pairing_targets as targets  # noqa: E402


def _load_gemma3_tool():
    """gemma3_tool.py is Engineer 1's own file (this investigation's own
    prior commit, f355126) -- imported here (never edited) purely to reuse
    dose_to_absolute_clamp verbatim, so the accepted non-positive-clamp
    guard applies to these new targets automatically rather than being
    re-implemented and risking drift."""
    path = Path(__file__).resolve().parent / "gemma3_tool.py"
    spec = importlib.util.spec_from_file_location("gemma3_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# QwenScopeSAE -- duck-typed stand-in for sae_lens.SAE, built from a raw
# Qwen-Scope layerN.sae.pt file. _make_clamp_hook only ever calls
# .encode()/.decode() on whatever it's given (same convention as
# tests/test_gemma3_tool.py's _IdentitySAE), so this is sufficient without
# touching sae_lens's own SAE class.
#
# Verified against Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50's own app.py source
# (public, read-only fetch -- no weights downloaded): torch.load() yields a
# dict with W_enc [d_sae, d_model], b_enc [d_sae], W_dec [d_model, d_sae];
# encode is relu(x @ W_enc.T + b_enc) then top-k-by-value zeroing everything
# outside the top k; decode is feats @ W_dec.T (+ a bias the app's own
# steering shortcut never reads -- see b_dec handling below).
# ---------------------------------------------------------------------------


def _topk_relu(x, k: int):
    import torch

    relu_x = torch.relu(x)
    values, indices = torch.topk(relu_x, k, dim=-1)
    out = torch.zeros_like(relu_x)
    out.scatter_(-1, indices, values)
    return out


class QwenScopeSAE:
    """b_dec's presence in the real checkpoint is UNCONFIRMED: the
    release's own app.py never reads it (its steering feature adds a raw
    decoder column directly to the residual, bypassing decode() entirely).
    If the loaded state_dict has no 'b_dec' key, this defaults to zeros and
    sets used_zero_b_dec_default=True so a diagnostic run can tell "verified
    zero bias" apart from "assumed zero bias because the key was absent" --
    this is exactly the kind of thing a mechanical acceptance run should
    surface, not silently paper over."""

    def __init__(self, W_enc, b_enc, W_dec, b_dec, *, k: int, used_zero_b_dec_default: bool):
        self.W_enc = W_enc  # [d_model, d_sae]
        self.b_enc = b_enc  # [d_sae]
        self.W_dec = W_dec  # [d_model, d_sae]
        self.b_dec = b_dec  # [d_model]
        self.k = k
        self.used_zero_b_dec_default = used_zero_b_dec_default
        self.d_in = W_enc.shape[0]
        self.d_sae = W_enc.shape[1]

    def encode(self, x):
        pre = x.to(self.W_enc.dtype) @ self.W_enc + self.b_enc
        return _topk_relu(pre, self.k)

    def decode(self, feats):
        return feats.to(self.W_dec.dtype) @ self.W_dec.T + self.b_dec

    @classmethod
    def from_state_dict(cls, state_dict: dict[str, Any], *, k: int, device: str) -> QwenScopeSAE:
        import torch

        required = ("W_enc", "b_enc", "W_dec")
        missing = [key for key in required if key not in state_dict]
        if missing:
            raise targets.TargetIdentityMismatch(
                f"Qwen-Scope layer file is missing expected key(s) {missing} -- the loaded "
                f"file does not match the schema verified against the release's own app.py "
                f"(W_enc/b_enc/W_dec); refusing to guess a substitute."
            )
        w_enc_raw = state_dict["W_enc"].to(dtype=torch.float32, device=device)  # [d_sae, d_model]
        b_enc = state_dict["b_enc"].to(dtype=torch.float32, device=device)
        w_dec = state_dict["W_dec"].to(dtype=torch.float32, device=device)  # [d_model, d_sae]
        used_zero_b_dec_default = "b_dec" not in state_dict
        b_dec = (
            torch.zeros(w_dec.shape[0], dtype=torch.float32, device=device)
            if used_zero_b_dec_default
            else state_dict["b_dec"].to(dtype=torch.float32, device=device)
        )
        return cls(
            W_enc=w_enc_raw.T.contiguous(), b_enc=b_enc, W_dec=w_dec, b_dec=b_dec,
            k=k, used_zero_b_dec_default=used_zero_b_dec_default,
        )

    @classmethod
    def from_layer_file(cls, path: str | Path, *, k: int, device: str) -> QwenScopeSAE:
        import torch

        state_dict = torch.load(str(path), map_location=device, weights_only=True)
        return cls.from_state_dict(state_dict, k=k, device=device)


# ---------------------------------------------------------------------------
# Raw-HF forward-hook adapter for Qwen3.5 -- transformer_lens==3.2.1 has no
# entry for this model (verified, see final_pairing_targets.py), so there is
# no HookedTransformer.hooks() context manager to attach through. PyTorch's
# native register_forward_hook has signature (module, args, output); this
# adapts it to _make_clamp_hook's (resid, hook) -> resid contract so the
# SAME unmodified hook function drives both targets.
# ---------------------------------------------------------------------------


def resolve_qwen_text_decoder(hf_model):
    """Qwen3_5ForConditionalGeneration's text decoder: verified directly
    against transformers==5.12.1's modeling_qwen3_5.py source (not inferred
    by analogy) -- Qwen3_5ForConditionalGeneration.__init__ sets
    self.model = Qwen3_5Model(config); Qwen3_5Model.__init__ sets
    self.language_model = AutoModel.from_config(config.text_config).
    Mirrors the already-solved Gemma3ForConditionalGeneration pattern
    (reach .language_model explicitly; the vision tower is a sibling,
    never touched)."""
    if hasattr(hf_model, "model") and hasattr(hf_model.model, "language_model"):
        return hf_model.model.language_model
    if hasattr(hf_model, "language_model"):
        return hf_model.language_model
    raise targets.TargetIdentityMismatch(
        f"could not locate a .language_model text decoder on the loaded model "
        f"(type={type(hf_model).__name__}); the modeling_qwen3_5.py structure this was "
        f"verified against may not match what actually loaded on this machine -- stop "
        f"rather than guess a different attribute path."
    )


def get_qwen_decoder_layer(text_decoder, layer: int):
    return text_decoder.layers[layer]


def register_qwen_raw_hook(decoder_layer_module, hook_fn):
    """Qwen3_5DecoderLayer.forward() returns hidden_states as a plain
    tensor, not a tuple (verified against modeling_qwen3_5.py's own
    `return hidden_states`) -- register_forward_hook's `output` argument is
    therefore directly the resid-post tensor, no unwrapping needed, and
    returning a replacement tensor from the hook replaces the layer's
    output exactly as _make_clamp_hook expects."""

    def native_hook(module, args, output):
        return hook_fn(output, hook=None)

    return decoder_layer_module.register_forward_hook(native_hook)


# ---------------------------------------------------------------------------
# Diagnostics -- the full field list this task's acceptance criteria
# require, captured by OBSERVING an unmodified _make_clamp_hook closure,
# never by altering it.
# ---------------------------------------------------------------------------


@dataclass
class InterventionTrace:
    call_index: int
    call_classification: Literal["prefill", "decode"]
    requested_mode: str
    requested_dose_or_raw: str
    calibration_input: float | None
    resolved_absolute_target: float
    backend_received_value: float
    hook_name: str
    hooked_tensor_shape: tuple[int, ...]
    feature_activation_before: float
    assigned_feature_value: float
    feature_activation_after: float
    residual_delta_norm: float
    residual_norm: float


def wrap_hook_with_diagnostics(
    inner_hook_fn,
    *,
    sae,
    feature_index: int,
    mode: str,
    dose_or_raw_label: str,
    calibration_input: float | None,
    resolved_absolute_target: float,
    hook_name: str,
    trace_out: list[InterventionTrace],
):
    """Wraps an already-built hook_fn from _make_clamp_hook (imported
    unmodified) with pure observation. Never alters what inner_hook_fn
    computes or returns -- every field below is captured by an INDEPENDENT
    encode() call on the tensor going in and the tensor coming out, not by
    reading _make_clamp_hook's internals.

    feature_activation_after is a diagnostic RE-ENCODE of the modified
    residual, not a guaranteed exact readback of assigned_feature_value:
    encode(decode(x)) is not necessarily an exact identity for a lossy
    dictionary, so a large-but-inexact match to the target is the expected,
    healthy signal; an activation_after indistinguishable from
    activation_before is the actual "intervention disappeared" signal this
    trace exists to catch.

    call_classification: call_index == 0 is "prefill" (the full-prompt
    call), every later call is "decode" (a single new token under the KV
    cache) -- this matches HookedTransformer.generate()'s own per-step call
    pattern (docs/positions_semantics.md) and the standard HF GenerationMixin
    cached-decode pattern the raw-HF Qwen path also relies on."""
    call_counter = {"value": 0}

    def hook_fn(resid, hook):
        import torch

        call_index = call_counter["value"]
        call_counter["value"] += 1
        classification: Literal["prefill", "decode"] = "prefill" if call_index == 0 else "decode"

        with torch.no_grad():
            feats_before = sae.encode(resid.to(torch.float32))
            activation_before = float(feats_before[0, -1, feature_index].item())

        output = inner_hook_fn(resid, hook)

        with torch.no_grad():
            feats_after = sae.encode(output.to(torch.float32))
            activation_after = float(feats_after[0, -1, feature_index].item())
            delta = (output - resid).to(torch.float32)
            residual_delta_norm = float(delta.norm().item())
            residual_norm = float(resid.to(torch.float32).norm().item())

        trace_out.append(
            InterventionTrace(
                call_index=call_index,
                call_classification=classification,
                requested_mode=mode,
                requested_dose_or_raw=dose_or_raw_label,
                calibration_input=calibration_input,
                resolved_absolute_target=resolved_absolute_target,
                backend_received_value=resolved_absolute_target,
                hook_name=hook_name,
                hooked_tensor_shape=tuple(resid.shape),
                feature_activation_before=activation_before,
                assigned_feature_value=resolved_absolute_target,
                feature_activation_after=activation_after,
                residual_delta_norm=residual_delta_norm,
                residual_norm=residual_norm,
            )
        )
        return output

    return hook_fn


def find_first_disappearance_boundary(
    traces: list[InterventionTrace], *, positions: str
) -> InterventionTrace | None:
    """The first call whose residual_delta_norm is 0.0 where that is NOT
    the accepted generated_only first-call no-op (docs/positions_semantics.md,
    preserved here rather than re-litigated). None means no boundary found
    -- every applicable call showed a nonzero delta."""
    for t in traces:
        if positions == "generated_only" and t.call_index == 0:
            continue
        if t.residual_delta_norm == 0.0:
            return t
    return None


def mechanical_verdict(traces: list[InterventionTrace], *, positions: str) -> dict[str, Any]:
    boundary = find_first_disappearance_boundary(traces, positions=positions)
    applicable = [t for t in traces if not (positions == "generated_only" and t.call_index == 0)]
    return {
        "hook_invocation_count": len(traces),
        "prefill_call_count": sum(1 for t in traces if t.call_classification == "prefill"),
        "decode_call_count": sum(1 for t in traces if t.call_classification == "decode"),
        "nonzero_steer_confirmed": bool(applicable) and all(t.residual_delta_norm > 0.0 for t in applicable),
        "first_disappearance_boundary": asdict(boundary) if boundary is not None else None,
    }


# ---------------------------------------------------------------------------
# Target-specific loaders. Neither reuses gemma3_sweep.load_model_and_sae or
# qwen_tool_adapter.load_model_and_sae -- see final_pairing_targets.py's
# module docstring for exactly why not (hardcoded identity constants that
# would silently override whatever path is passed).
# ---------------------------------------------------------------------------


def _require_offline() -> None:
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError(
            "HF_HUB_OFFLINE=1 is not set. Every Tamia compute-node job in this project "
            "requires it -- refusing to proceed rather than risk a silent network fetch."
        )


def _patch_gemma3_safetensors_shape_lookup() -> None:
    """Verbatim duplicate of gemma3_sweep.py's own patch (same
    duplicate-rather-than-cross-import convention this project already uses
    for out-of-chain adapters, e.g. qwen_tool_adapter.pick_control_feature_idx)
    -- NOT an edit to gemma3_sweep.py. Installed sae_lens's Gemma-3 loader
    issues a raw requests.get() HTTP range read for tensor shapes that
    bypasses huggingface_hub AND HF_HUB_OFFLINE entirely; this routes the
    same shape lookup through hf_hub_download instead. Applies to ANY
    conversion_func="gemma_3" release, verified via the locally-installed
    sae_lens==6.44.2 registry to include gemma-scope-2-12b-it-res, not just
    the -pt release this patch was first written against."""
    import sae_lens.loading.pretrained_sae_loaders as psl
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    def _local_get_safetensors_tensor_shapes(repo_id: str, filename: str) -> dict:
        local_path = hf_hub_download(repo_id=repo_id, filename=filename)
        with safe_open(local_path, framework="pt") as f:
            return {k: list(f.get_slice(k).get_shape()) for k in f}

    psl.get_safetensors_tensor_shapes = _local_get_safetensors_tensor_shapes


def load_gemma_it_target(
    model_path: str | Path, sae_path: str | Path, *, device: str = "cuda", dtype: str = "bfloat16",
    expected_revision: str | None = None,
):
    """UNTESTED against real weights (no GPU allocation was available for
    this investigation) -- see the report for exactly what is and isn't
    verified. Fails closed via final_pairing_targets' validators at every
    step that can be checked mechanically."""
    import torch
    from sae_lens import SAE
    from transformer_lens import HookedTransformer
    from transformers import AutoModel, AutoTokenizer

    target = targets.GEMMA_3_12B_IT_TARGET
    _require_offline()
    model_path = Path(model_path)
    sae_path = Path(sae_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model snapshot directory not found: {model_path}")
    if not sae_path.exists():
        raise FileNotFoundError(f"SAE snapshot directory not found: {sae_path}")
    targets.validate_local_snapshot_identity(model_path, target, which="model", expected_revision=expected_revision)
    targets.validate_local_snapshot_identity(sae_path, target, which="sae", expected_revision=expected_revision)

    torch_dtype = getattr(torch, dtype)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    hf_model = AutoModel.from_pretrained(str(model_path), dtype=torch_dtype)
    model = HookedTransformer.from_pretrained(
        target.model_repo_id,
        hf_model=hf_model,
        tokenizer=tokenizer,
        fold_ln=False,
        center_writing_weights=False,
        center_unembed=False,
        device=device,
        dtype=torch_dtype,
    )
    model.eval()

    _patch_gemma3_safetensors_shape_lookup()
    sae = SAE.from_pretrained(release=target.sae_release, sae_id=target.sae_id, device=device)
    sae = sae.to(dtype=torch.float32)
    sae.eval()

    hook_name = sae.cfg.metadata.hook_name
    targets.validate_hook_identity(hook_name, target)
    targets.validate_hidden_dims(model.cfg.d_model, sae.cfg.d_in, target)

    return model, sae, hook_name


def load_qwen_target(
    model_path: str | Path, sae_layer_file_path: str | Path, *, layer: int, k: int | None = None,
    device: str = "cuda", dtype: str = "bfloat16", expected_revision: str | None = None,
):
    """UNTESTED against real weights. Raw-HF path (no HookedTransformer --
    transformer_lens==3.2.1 does not know Qwen3.5, verified in
    final_pairing_targets.py). k defaults to the ratified target's
    expected_k (50) if not overridden."""
    import torch
    from transformers import AutoModel

    target = targets.QWEN_3_5_27B_TARGET
    k = target.expected_k if k is None else k
    targets.validate_qwen_layer_choice(layer, target)
    _require_offline()

    model_path = Path(model_path)
    sae_layer_file_path = Path(sae_layer_file_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model snapshot directory not found: {model_path}")
    if not sae_layer_file_path.exists():
        raise FileNotFoundError(f"Qwen-Scope layer file not found: {sae_layer_file_path}")
    targets.validate_local_snapshot_identity(model_path, target, which="model", expected_revision=expected_revision)
    targets.validate_local_snapshot_identity(
        sae_layer_file_path.parent, target, which="sae", expected_revision=expected_revision
    )

    torch_dtype = getattr(torch, dtype)
    hf_model = AutoModel.from_pretrained(str(model_path), dtype=torch_dtype)
    hf_model.eval()
    hf_model.to(device)

    text_decoder = resolve_qwen_text_decoder(hf_model)
    hidden_size = text_decoder.config.hidden_size

    sae = QwenScopeSAE.from_layer_file(sae_layer_file_path, k=k, device=device)
    targets.validate_hidden_dims(hidden_size, sae.d_in, target)

    hook_identifier = f"{target.expected_hook_name}:layer_{layer}"
    targets.validate_hook_identity(hook_identifier, target)

    return hf_model, text_decoder, sae, hook_identifier


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def resolve_target_value(
    tool_module, *, mode: str, dose_multiple: float | None, calibration_value: float | None,
    raw_clamp_value: float | None,
) -> tuple[float, str]:
    if mode == "ablate":
        return 0.0, "ablate (always 0.0 regardless of dose)"
    if raw_clamp_value is not None:
        if dose_multiple is not None or calibration_value is not None:
            raise ValueError("--raw-clamp-value is mutually exclusive with --dose-multiple/--calibration-value")
        return float(raw_clamp_value), "raw engineering value (no manifest/calibration input available)"
    if dose_multiple is None or calibration_value is None:
        raise ValueError(
            "steer mode requires either --raw-clamp-value alone, or both --dose-multiple and "
            "--calibration-value"
        )
    resolved = tool_module.dose_to_absolute_clamp("steer", dose_multiple, calibration_value)
    return resolved, f"dose_multiple={dose_multiple} x calibration_value={calibration_value}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, choices=sorted(targets.ALL_TARGETS))
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True, help="Gemma: SAE snapshot dir. Qwen: the specific layerN.sae.pt file.")
    p.add_argument("--qwen-layer", type=int, default=None, help="Required for --target qwen-3.5-27b. Engineering-only.")
    p.add_argument("--expected-revision", default=None)
    p.add_argument("--feature-idx", type=int, required=True)
    p.add_argument("--mode", choices=["steer", "ablate"], required=True)
    p.add_argument("--dose-multiple", type=float, default=None)
    p.add_argument("--calibration-value", type=float, default=None)
    p.add_argument("--raw-clamp-value", type=float, default=None)
    p.add_argument("--positions", choices=["all", "generated_only"], default="all")
    p.add_argument("--prompt", default="Tell me about your day.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--out", required=True, help="Output path for the JSON trace artifact.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    import torch

    args = parse_args(argv)
    tool_module = _load_gemma3_tool()

    resolved_target_value, dose_or_raw_label = resolve_target_value(
        tool_module, mode=args.mode, dose_multiple=args.dose_multiple,
        calibration_value=args.calibration_value, raw_clamp_value=args.raw_clamp_value,
    )

    trace: list[InterventionTrace] = []

    if args.target == "gemma-3-12b-it":
        model, sae, hook_name = load_gemma_it_target(
            args.model_path, args.sae_path, device=args.device, dtype=args.dtype,
            expected_revision=args.expected_revision,
        )
        tokens = model.to_tokens(args.prompt)
        prompt_lengths = tokens.shape[1] if args.positions == "generated_only" else None
        inner_hook = _make_clamp_hook(sae, args.feature_idx, resolved_target_value, args.positions, prompt_lengths, [])
        hook_fn = wrap_hook_with_diagnostics(
            inner_hook, sae=sae, feature_index=args.feature_idx, mode=args.mode,
            dose_or_raw_label=dose_or_raw_label, calibration_input=args.calibration_value,
            resolved_absolute_target=resolved_target_value, hook_name=hook_name, trace_out=trace,
        )
        torch.manual_seed(args.seed)
        with model.hooks(fwd_hooks=[(hook_name, hook_fn)]):
            model.generate(tokens, max_new_tokens=args.max_new_tokens, do_sample=True, temperature=0.7, top_p=0.9, verbose=False)

    elif args.target == "qwen-3.5-27b":
        from transformers import AutoTokenizer

        if args.qwen_layer is None:
            raise ValueError("--qwen-layer is required for --target qwen-3.5-27b (engineering-only, no default)")
        hf_model, text_decoder, sae, hook_name = load_qwen_target(
            args.model_path, args.sae_path, layer=args.qwen_layer, device=args.device, dtype=args.dtype,
            expected_revision=args.expected_revision,
        )
        # hf_model.generate() is transformers' own GenerationMixin.generate() --
        # Qwen3_5ForConditionalGeneration extends GenerationMixin (verified against
        # modeling_qwen3_5.py), so this is the standard, heavily-exercised HF decode
        # path (prefill full prompt, then one new token per step under its own
        # past_key_values cache) -- not a hand-rolled loop. The hook is attached to
        # the single decoder layer via PyTorch's native register_forward_hook
        # (register_qwen_raw_hook), which fires on every real invocation of that
        # layer regardless of what's driving the forward pass.
        tokenizer = AutoTokenizer.from_pretrained(str(args.model_path))
        inputs = tokenizer(args.prompt, return_tensors="pt").to(args.device)
        prompt_lengths = inputs["input_ids"].shape[1] if args.positions == "generated_only" else None

        decoder_layer = get_qwen_decoder_layer(text_decoder, args.qwen_layer)
        inner_hook = _make_clamp_hook(sae, args.feature_idx, resolved_target_value, args.positions, prompt_lengths, [])
        hook_fn = wrap_hook_with_diagnostics(
            inner_hook, sae=sae, feature_index=args.feature_idx, mode=args.mode,
            dose_or_raw_label=dose_or_raw_label, calibration_input=args.calibration_value,
            resolved_absolute_target=resolved_target_value, hook_name=hook_name, trace_out=trace,
        )
        handle = register_qwen_raw_hook(decoder_layer, hook_fn)
        try:
            torch.manual_seed(args.seed)
            with torch.no_grad():
                hf_model.generate(
                    **inputs, max_new_tokens=args.max_new_tokens, do_sample=True, temperature=0.7, top_p=0.9,
                )
        finally:
            handle.remove()

    verdict = mechanical_verdict(trace, positions=args.positions)
    payload = {
        "target": args.target,
        "positions": args.positions,
        "requested_mode": args.mode,
        "resolved_absolute_target": resolved_target_value,
        "dose_or_raw_label": dose_or_raw_label,
        "trace": [asdict(t) for t in trace],
        "verdict": verdict,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["nonzero_steer_confirmed"] else 1


if __name__ == "__main__":
    sys.exit(main())
