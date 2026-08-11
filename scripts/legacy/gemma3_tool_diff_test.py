"""Differential test (item 4 of the identical-output bug investigation):
run the SAME feature / dose / mode / prompt / seed through the known-good
sweep harness's own call path (gemma3_sweep.run_cell -- attach() +
model.generate()) and through the tool's call path
(gemma3_tool.generate_hooked -- _make_clamp_hook + model.generate()
directly), then diff the resulting text, generated token ids, and the
per-position activation of the intervened feature in each completion.

REQUIRES A REAL MODEL + SAE. Not run by pytest end-to-end (see
tests/test_gemma3_tool_diff_test.py for the pure gating-logic and
mocked-main() coverage that IS run by pytest) -- there was no GPU
allocation available to execute this end-to-end during the original
investigation. It exists so that check is one command once one is: both
call paths already share the identical underlying mechanism (see
docs/positions_semantics.md), so on a correct stack this script should
report identical text, identical token ids, and identical per-position
activations; a real divergence here would mean the two paths are NOT as
equivalent as the code reading in that doc concluded, and that reading
needs to be revisited against real numbers, not just source.

Orchestrator review, 2026-08-13 ("repair Step 0"): live job 406092's own
output showed identical_text=false (first_char_divergence=1) yet the
process exited 0 -- main() computed a diff report and then unconditionally
`return 0`, never consulting any of the fields it had just computed. Two
independent defects, both fixed here:

  1. Both call paths sampled (do_sample=True, temperature=0.7, top_p=0.9)
     under a fixed torch.manual_seed(seed) -- but a fixed seed does not
     guarantee two DIFFERENT code paths consume the RNG stream identically
     (attach() and _make_clamp_hook are the same function, but everything
     else around the two generate() calls is not literally the same code),
     so sampling could diverge even when the mechanism under test is fully
     correct. Both paths now use do_sample=False (greedy) -- fully
     deterministic, no RNG dependency at all, so a divergence can no
     longer be dismissed as "just sampling noise" or hidden by it either.
  2. main() now builds an explicit gate_criteria dict, adds gate_passed
     (all criteria must hold), and returns 0 iff gate_passed -- 1
     otherwise. The activation-comparison criterion is UNCHANGED from what
     this script already computed (max_abs_activation_diff), and is
     required to be EXACTLY 0.0 -- that is not a new invented tolerance,
     it is what a real forward pass over already-generated tokens
     (deterministic, no sampling inside it) should always produce; no
     epsilon has been added here that did not already implicitly apply.
     A NEW criterion, identical_token_ids, compares the raw generated
     token id sequences directly (not just their decoded strings) --
     decoded-text equality does not strictly imply token-id equality.

If a real run under greedy decoding still diverges, that is a genuine
finding to report -- do not loosen gate_passed's criteria to paper over it.

Usage (mirrors gemma3_tool.py's own CLI conventions):
    python scripts/legacy/gemma3_tool_diff_test.py \\
        --model-path /path/to/model --sae-path /path/to/sae \\
        --sweep-module scripts/legacy/gemma3_sweep.py \\
        --feature-idx 250 --mode steer --dose-multiple 4.0 --positions all \\
        --prompt "Tell me about your day." --seed 0 --max-new-tokens 64

Pass --sweep-module scripts/legacy/qwen_tool_adapter.py (with matching
--model-path/--sae-path) to run the same comparison on the Qwen side.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SWEEP_MODULE_PATH = Path(__file__).resolve().parent / "gemma3_sweep.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_activations(model, sae, hook_name: str, tokens, feature_idx: int) -> list[float]:
    """Teacher-forced pass over `tokens` with NO intervention -- just a
    plain forward pass with a recording-only hook -- returning the target
    feature's activation at every position. Used to compare what each
    path's own completion looks like under encode(), independent of
    whichever hook produced that completion."""
    import torch

    activations: list[float] = []

    def hook_fn(resid, hook):
        with torch.no_grad():
            x32 = resid.to(torch.float32)
            feats = sae.encode(x32)
            activations.extend(feats[0, :, feature_idx].tolist())
        return resid

    with torch.no_grad(), model.hooks(fwd_hooks=[(hook_name, hook_fn)]):
        model(tokens, return_type="logits")
    return activations


def run_sweep_path(
    sweep, model, sae, *, feature_idx: int, mode: str, dose_multiple: float, max_act_approx: float,
    positions: str, prompt: str, seed: int, max_new_tokens: int, checkpoint_hash: str,
) -> tuple[str, Any]:
    """Mirrors gemma3_sweep.run_cell exactly (same attach() + model.generate()
    call), constructing the same InterventionSpec run_cell would build for a
    'clamp' or 'ablate' record -- not a reimplementation, so this cannot
    silently drift from what the sweep actually does. do_sample=False
    (greedy): orchestrator review, 2026-08-13 ("repair Step 0") -- see
    module docstring for why sampling, even under a fixed seed, cannot be
    trusted to make two different call paths deterministic relative to
    each other."""
    import torch

    from interplab.interventions.hooks import attach
    from interplab.interventions.spec import InterventionSpec

    spec = InterventionSpec(
        kind="ablate" if mode == "ablate" else "clamp",
        feature_index=feature_idx,
        value_in_max_units=None if mode == "ablate" else dose_multiple,
        corpus_max=None if mode == "ablate" else max_act_approx,
        positions=positions,
        checkpoint_hash=checkpoint_hash,
        direction_seed=None,
    )
    tokens = model.to_tokens(prompt)
    prompt_lengths = tokens.shape[1] if positions == "generated_only" else None
    torch.manual_seed(seed)
    with attach(model, sae, spec, prompt_lengths=prompt_lengths):
        output = model.generate(tokens, max_new_tokens=max_new_tokens, do_sample=False, verbose=False)
    return model.to_string(output[0, tokens.shape[1] :]), output


def run_tool_path(
    tool, bundle, *, feature_idx: int, mode: str, dose_multiple: float, max_act_approx: float,
    positions: str, prompt: str, seed: int, max_new_tokens: int, token_ids_out: list[int] | None = None,
) -> tuple[str, float]:
    """do_sample=False mirrors run_sweep_path's own greedy switch (see that
    function's docstring); token_ids_out lets the caller obtain the raw
    generated token ids without changing generate_hooked's own return
    signature for every other caller (gemma3_tool.py's own _generate
    out-param convention, same as _make_clamp_hook's `stats`)."""
    return tool.generate_hooked(
        bundle, prompt, seed, feature_idx, mode, dose_multiple, max_act_approx,
        max_new_tokens=max_new_tokens, positions=positions, do_sample=False, token_ids_out=token_ids_out,
    )


def diff_report(
    text_a: str, text_b: str, acts_a: list[float], acts_b: list[float],
    token_ids_a: list[int] | None = None, token_ids_b: list[int] | None = None,
) -> dict[str, Any]:
    """Orchestrator review, 2026-08-13 ("repair Step 0"): adds explicit
    gate_criteria + gate_passed -- the fields this function already
    computed were being silently ignored by main()'s own exit code (live
    job 406092: identical_text=false, yet the process exited 0).

    activations_effectively_identical requires max_abs_activation_diff to
    be EXACTLY 0.0, not merely small -- this is not a new invented
    tolerance; a real forward pass over already-generated tokens has no
    sampling inside it at all, so the two paths' per-position activations
    are expected to match exactly on a correct stack, and an empty
    comparison (common_len == 0) is treated as a FAILURE, not a vacuous
    pass, since it proves nothing.

    identical_token_ids only gates the result when token ids were actually
    supplied for BOTH paths ("require identical token IDs when
    available") -- decoded-text equality does not strictly imply token-id
    equality, so this is a strictly stronger, independent check, not a
    restatement of identical_text."""
    identical_text = text_a == text_b
    first_char_divergence = None
    if not identical_text:
        for i, (ca, cb) in enumerate(zip(text_a, text_b, strict=False)):
            if ca != cb:
                first_char_divergence = i
                break
        else:
            first_char_divergence = min(len(text_a), len(text_b))

    token_ids_available = token_ids_a is not None and token_ids_b is not None
    identical_token_ids = (token_ids_a == token_ids_b) if token_ids_available else None

    common_len = min(len(acts_a), len(acts_b))
    act_diffs = [abs(acts_a[i] - acts_b[i]) for i in range(common_len)]
    max_abs_activation_diff = max(act_diffs) if act_diffs else None
    mean_abs_activation_diff = (sum(act_diffs) / len(act_diffs)) if act_diffs else None
    activations_effectively_identical = common_len > 0 and max_abs_activation_diff == 0.0

    gate_criteria = {
        "identical_text": identical_text,
        "identical_token_ids": identical_token_ids,
        "activations_effectively_identical": activations_effectively_identical,
    }
    gate_passed = (
        identical_text and activations_effectively_identical and identical_token_ids is not False
    )

    return {
        "identical_text": identical_text,
        "first_char_divergence": first_char_divergence,
        "sweep_path_text": text_a,
        "tool_path_text": text_b,
        "token_ids_available": token_ids_available,
        "identical_token_ids": identical_token_ids,
        "sweep_path_token_ids": token_ids_a,
        "tool_path_token_ids": token_ids_b,
        "activation_positions_compared": common_len,
        "max_abs_activation_diff": max_abs_activation_diff,
        "mean_abs_activation_diff": mean_abs_activation_diff,
        "activations_effectively_identical": activations_effectively_identical,
        "gate_criteria": gate_criteria,
        "gate_passed": gate_passed,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True)
    p.add_argument("--sweep-module", default=str(DEFAULT_SWEEP_MODULE_PATH))
    p.add_argument("--feature-idx", type=int, required=True)
    p.add_argument("--mode", choices=["steer", "ablate"], required=True)
    p.add_argument("--dose-multiple", type=float, default=1.0)
    p.add_argument("--positions", choices=["all", "generated_only"], default="all")
    p.add_argument("--prompt", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=64)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument(
        "--checkpoint-hash", default="diff-test-not-a-published-run",
        help="Provenance-only field on InterventionSpec; not validated against the SAE at attach() time.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    import json

    args = parse_args(argv)
    sweep = _load(Path(args.sweep_module).stem, Path(args.sweep_module))
    tool_path = Path(__file__).resolve().parent / "gemma3_tool.py"
    tool = _load("gemma3_tool", tool_path)

    manifest_path = (
        REPO_ROOT / "results" / ("qwen_tool" if "qwen" in args.sweep_module.lower() else "gemma3_sweep")
        / "feature_manifest.json"
    )
    manifest = tool.load_manifest(manifest_path, sweep)
    feature = tool.feature_by_idx(manifest, args.feature_idx)
    max_act_approx = feature["maxActApprox"]

    model, sae, hf_model = sweep.load_model_and_sae(args.model_path, args.sae_path, device=args.device, dtype=args.dtype)
    del hf_model
    bundle = tool.ModelBundle(model=model, sae=sae, hook_name=sae.cfg.metadata.hook_name)

    sweep_text, sweep_tokens = run_sweep_path(
        sweep, model, sae, feature_idx=args.feature_idx, mode=args.mode, dose_multiple=args.dose_multiple,
        max_act_approx=max_act_approx, positions=args.positions, prompt=args.prompt, seed=args.seed,
        max_new_tokens=args.max_new_tokens, checkpoint_hash=args.checkpoint_hash,
    )
    tool_token_ids: list[int] = []
    tool_text, clamp_value = run_tool_path(
        tool, bundle, feature_idx=args.feature_idx, mode=args.mode, dose_multiple=args.dose_multiple,
        max_act_approx=max_act_approx, positions=args.positions, prompt=args.prompt, seed=args.seed,
        max_new_tokens=args.max_new_tokens, token_ids_out=tool_token_ids,
    )

    prompt_tokens = model.to_tokens(args.prompt)
    sweep_token_ids = sweep_tokens[0, prompt_tokens.shape[1] :].tolist()
    tool_full_tokens = model.to_tokens(args.prompt + tool_text)
    sweep_acts = _record_activations(model, sae, bundle.hook_name, sweep_tokens, args.feature_idx)
    tool_acts = _record_activations(model, sae, bundle.hook_name, tool_full_tokens, args.feature_idx)

    report = diff_report(
        sweep_text, tool_text, sweep_acts, tool_acts, token_ids_a=sweep_token_ids, token_ids_b=tool_token_ids,
    )
    report["clamp_value"] = clamp_value
    report["feature_idx"] = args.feature_idx
    report["mode"] = args.mode
    report["dose_multiple"] = args.dose_multiple
    report["positions"] = args.positions
    report["prompt_len_tokens"] = prompt_tokens.shape[1]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
