"""PI deliverable #4 -- interactive Gradio steer/ablate tool for the
Gemma-3 12B SAE (layer 31, width 16k, l0_medium). Runs inside a Tamia
interactive allocation; see slurm/legacy/launch_gemma3_tool.sh and
slurm/legacy/README_gemma3_tool.md for the exact operator commands.

THE THREE OFFLINE CONSTRAINTS (compute nodes have no outbound internet --
job 397854 died on a 50-minute connection timeout to huggingface.co while
the login node answers in 90ms):
  1. --model-path / --sae-path are required local filesystem paths, never
     a repo_id. load_model_and_sae() (imported from gemma3_sweep.py) fails
     fast if either is missing or HF_HUB_OFFLINE isn't set, before any
     network-capable call.
  2. This tool never calls Neuronpedia at runtime. The feature browser
     reads two local, pre-staged files: --manifest-path (labels/indices/
     densities/maxActApprox) and --snippets-path (top-16 example snippets
     per feature, schema: {"<idx>": ["snippet", ...]}). A missing
     manifest is a hard failure (there is no tool without it); a missing
     snippets file degrades to an explicit "not yet pre-staged" message
     per feature rather than raising -- the real fetch for these 9
     features is gated on verifying the Neuronpedia source resolves to
     the exact SAE this tool uses, and if that gate fails there SHOULD be
     no snippets shown here. Silently drawing text from a neighbouring
     SAE would look fine on screen and be wrong.
  3. The HF token guard elsewhere in this project is SLURM_JOB_ID-
     conditional, so an interactive allocation carries no credential --
     this tool never needs one, and never touches HF_TOKEN.

Model loading duplicates nothing: load_model_and_sae() is imported (by
file path, not a package import -- scripts/legacy has no __init__.py) from
gemma3_sweep.py, which is FROZEN and must not be edited. This is the same
load path the sweep and the necessity harness use; see that module's
docstring for why TransformerBridge cannot be used for this model, and why
the SAE loader must be patched before SAE.from_pretrained() is called.
This works only because transformer_lens ships a hardcoded
convert_gemma_weights entry for the Gemma3ForConditionalGeneration
architecture string -- a different multimodal architecture with no
registered converter would hit NotImplementedError in the same dispatch
table.

Steering/ablation hooking is interplab.interventions.hooks._make_clamp_hook,
imported unmodified. It is shared with the sweep's own attach() call and
the necessity harness -- forking it here could let this tool disagree with
numbers already reported elsewhere.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any

from interplab.interventions.hooks import _make_clamp_hook

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "results" / "gemma3_sweep" / "feature_manifest.json"
DEFAULT_SNIPPETS_PATH = REPO_ROOT / "results" / "gemma3_sweep" / "gemma3_tool_snippets.json"
SNIPPETS_NOT_STAGED_MESSAGE = "example snippets not yet pre-staged"
DOSE_GRID: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
MODES: tuple[str, ...] = ("steer", "ablate")
DEFAULT_CONTROL_RNG_SEED = 1337  # matches gemma3_sweep.py's --control-rng-seed default (job 399312)
DEFAULT_MAX_NEW_TOKENS = 200


# ---------------------------------------------------------------------------
# Dynamic import of the frozen sweep module (same pattern as
# gemma3_necessity.py's _load_sweep_module). Read-only, by file path --
# scripts/legacy has no __init__.py by design.
# ---------------------------------------------------------------------------


def _load_sweep_module():
    sweep_path = Path(__file__).resolve().parent / "gemma3_sweep.py"
    spec = importlib.util.spec_from_file_location("gemma3_sweep", sweep_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Pure logic -- no torch/gradio import beyond the hooks import above, so
# this half of the file is fully testable without a GPU or a Gradio
# install exercising real generation.
# ---------------------------------------------------------------------------


def dose_to_absolute_clamp(mode: str, dose_multiple: float, max_act_approx: float) -> float:
    """Mirrors gemma3_sweep.py's build_job_matrix arithmetic exactly:
    ablation always clamps to 0.0 regardless of dose (carried only for
    provenance/seed uniformity); steer scales the feature's own
    maxActApprox by the chosen dose multiple."""
    if mode == "ablate":
        return 0.0
    if mode != "steer":
        raise ValueError(f"unknown mode: {mode!r}; expected 'steer' or 'ablate'")
    return float(dose_multiple) * float(max_act_approx)


def load_manifest(path: Path, sweep_module) -> dict[str, Any]:
    return sweep_module.load_feature_manifest(Path(path))


def feature_by_idx(manifest: dict[str, Any], idx: int) -> dict[str, Any]:
    for f in manifest["features"]:
        if f["idx"] == idx:
            return f
    raise KeyError(f"feature idx {idx} not found in manifest")


def feature_dropdown_choices(manifest: dict[str, Any]) -> list[tuple[str, int]]:
    return [(f"{f['idx']} — {f['label']}", f["idx"]) for f in manifest["features"]]


def load_snippets(path: Path) -> dict[str, list[str]]:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _snippet_text(entry: str | dict[str, Any]) -> str:
    """Snippet entries come in two schemas: a plain string (the
    necessity-adapter's flattened output), or a raw-fetch dict with a
    "text" field alongside "maxValue"/"char_len" (what Engineer 1's
    fetch actually produced, byte-identical to the raw Neuronpedia
    provenance format used elsewhere in this project). Accept both."""
    if isinstance(entry, str):
        return entry
    return entry["text"]


def snippets_for_feature(snippets: dict[str, list[Any]], idx: int) -> list[str]:
    return [_snippet_text(entry) for entry in snippets.get(str(idx), [])]


def snippets_display(snippets: dict[str, list[Any]], idx: int) -> str:
    texts = snippets_for_feature(snippets, idx)
    if not texts:
        return SNIPPETS_NOT_STAGED_MESSAGE
    return "\n\n---\n\n".join(texts)


def resolve_control_feature_idx(sweep_module, manifest: dict[str, Any], *, control_rng_seed: int) -> int:
    """The fixed, seeded random-feature control -- a feature outside the
    manifest's 9. Reuses gemma3_sweep.py's own exclusion set and RNG
    helper so this tool's control feature matches the one a real sweep
    run at the same control_rng_seed draws, rather than silently
    disagreeing with it."""
    exclude = (
        {f["idx"] for f in sweep_module.FEATURES}
        | {f["idx"] for f in sweep_module.OPTIONAL_FEATURES}
        | sweep_module.REJECTED_FEATURE_IDXS
    )
    return sweep_module.pick_control_feature_idx(
        exclude=exclude, control_rng_seed=control_rng_seed, d_sae=sweep_module.WIDTH
    )


def feature_metadata_markdown(feature: dict[str, Any]) -> str:
    low_conf = " (low confidence)" if feature.get("low_confidence") else ""
    return (
        f"**idx {feature['idx']}** — {feature['label']}{low_conf}\n\n"
        f"- domain: {feature['domain_class']}\n"
        f"- density: {feature['density']:.6f}\n"
        f"- maxActApprox: {feature['maxActApprox']:.4f}\n"
        f"- _{feature['maxActApprox_caveat']}_\n"
        f"- SAE: {feature['sae_id']} (layer {feature['layer']}, width {feature['width']}, "
        f"l0 {feature['l0_variant']})"
    )


# ---------------------------------------------------------------------------
# Model loading + generation -- the GPU-touching half.
# ---------------------------------------------------------------------------


class ModelBundle:
    __slots__ = ("model", "sae", "hook_name")

    def __init__(self, model, sae, hook_name: str):
        self.model = model
        self.sae = sae
        self.hook_name = hook_name


def load_bundle(sweep_module, model_path: str, sae_path: str, *, device: str, dtype: str) -> ModelBundle:
    """The one GPU-touching loader. Delegates entirely to gemma3_sweep.py's
    load_model_and_sae() -- the offline guard, path-missing fail-fast, and
    d_model/d_in mismatch check all live there, not duplicated here (see
    module docstring). hf_model is freed immediately: this tool has no
    equivalence check, so there is no reason to hold a second ~24GB copy
    for the session."""
    import torch

    model, sae, hf_model = sweep_module.load_model_and_sae(model_path, sae_path, device=device, dtype=dtype)
    del hf_model
    torch.cuda.empty_cache()
    return ModelBundle(model=model, sae=sae, hook_name=sae.cfg.metadata.hook_name)


def _generate(bundle: ModelBundle, prompt: str, seed: int, max_new_tokens: int, hook_fn=None) -> str:
    import torch

    torch.manual_seed(seed)
    tokens = bundle.model.to_tokens(prompt)
    fwd_hooks = [(bundle.hook_name, hook_fn)] if hook_fn is not None else []
    with bundle.model.hooks(fwd_hooks=fwd_hooks):
        output = bundle.model.generate(
            tokens,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            verbose=False,
        )
    completion_tokens = output[:, tokens.shape[1] :]
    return bundle.model.to_string(completion_tokens[0])


def generate_baseline(bundle: ModelBundle, prompt: str, seed: int, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> str:
    return _generate(bundle, prompt, seed, max_new_tokens, hook_fn=None)


def generate_hooked(
    bundle: ModelBundle,
    prompt: str,
    seed: int,
    feature_idx: int,
    mode: str,
    dose_multiple: float,
    max_act_approx: float,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
) -> tuple[str, float]:
    clamp_value = dose_to_absolute_clamp(mode, dose_multiple, max_act_approx)
    stats: list = []
    hook_fn = _make_clamp_hook(bundle.sae, feature_idx, clamp_value, "all", None, stats)
    text = _generate(bundle, prompt, seed, max_new_tokens, hook_fn=hook_fn)
    return text, clamp_value


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def build_ui(bundle: ModelBundle, manifest: dict[str, Any], snippets: dict[str, list[str]], control_feature_idx: int, control_rng_seed: int):
    import gradio as gr

    choices = feature_dropdown_choices(manifest)
    default_idx = choices[0][1]
    default_feature = feature_by_idx(manifest, default_idx)
    default_dose = DOSE_GRID[0]

    header_md = (
        "## Gemma-3 12B SAE steer / ablate tool\n\n"
        f"SAE: `{manifest['sae_release']}` &nbsp;|&nbsp; model: `{manifest['model_id']}`\n\n"
        f"**{manifest['maxActApprox_caveat']}**\n\n"
        f"Random-feature control: idx `{control_feature_idx}` (fixed; drawn via "
        f"control_rng_seed={control_rng_seed}, the same seed the D2.1 sweep uses)."
    )

    with gr.Blocks(title="Gemma-3 SAE steer/ablate") as demo:
        gr.Markdown(header_md)
        with gr.Row():
            feature_dd = gr.Dropdown(choices=choices, value=default_idx, label="Feature")
            mode_radio = gr.Radio(choices=list(MODES), value="steer", label="Mode")
            dose_dd = gr.Dropdown(
                choices=[str(d) for d in DOSE_GRID], value=str(default_dose), label="Dose (x maxActApprox)"
            )
        feature_info_md = gr.Markdown(feature_metadata_markdown(default_feature), label="Feature info")
        snippets_md = gr.Markdown(snippets_display(snippets, default_idx), label="Example snippets")
        clamp_display = gr.Number(
            label="Resulting absolute clamp value",
            value=dose_to_absolute_clamp("steer", default_dose, default_feature["maxActApprox"]),
            interactive=False,
        )
        control_toggle = gr.Checkbox(
            value=True,
            label="Random-feature control (on by default -- without it, nothing on screen is falsifiable)",
        )

        prompt_box = gr.Textbox(label="Prompt", lines=3, value="Tell me about your day.")
        seed_box = gr.Number(label="Seed", value=random.randint(0, 2**31 - 1), precision=0)
        generate_btn = gr.Button("Generate")

        with gr.Row():
            baseline_out = gr.Textbox(label="Baseline (unhooked)", lines=8, interactive=False)
            target_out = gr.Textbox(label="Target feature (hooked)", lines=8, interactive=False)
            control_out = gr.Textbox(label="Random-feature control (hooked)", lines=8, interactive=False)

        def _on_feature_or_mode_or_dose_change(feature_idx, mode, dose_str):
            feature = feature_by_idx(manifest, feature_idx)
            clamp = dose_to_absolute_clamp(mode, float(dose_str), feature["maxActApprox"])
            return (
                feature_metadata_markdown(feature),
                snippets_display(snippets, feature_idx),
                clamp,
            )

        for trigger in (feature_dd, mode_radio, dose_dd):
            trigger.change(
                _on_feature_or_mode_or_dose_change,
                inputs=[feature_dd, mode_radio, dose_dd],
                outputs=[feature_info_md, snippets_md, clamp_display],
            )

        def _on_generate(feature_idx, mode, dose_str, use_control, prompt, seed):
            feature = feature_by_idx(manifest, feature_idx)
            seed = int(seed)
            baseline_text = generate_baseline(bundle, prompt, seed)
            target_text, _clamp = generate_hooked(
                bundle, prompt, seed, feature_idx, mode, float(dose_str), feature["maxActApprox"]
            )
            if not use_control:
                return baseline_text, target_text, ""
            control_text, _ = generate_hooked(
                bundle, prompt, seed, control_feature_idx, mode, float(dose_str), feature["maxActApprox"]
            )
            return baseline_text, target_text, control_text

        generate_btn.click(
            _on_generate,
            inputs=[feature_dd, mode_radio, dose_dd, control_toggle, prompt_box, seed_box],
            outputs=[baseline_out, target_out, control_out],
        )

    return demo


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--model-path", required=True, help="Local filesystem path to the gemma-3-12b-pt snapshot directory. Never a repo_id."
    )
    p.add_argument(
        "--sae-path",
        required=True,
        help="Local filesystem path to the layer_31_width_16k_l0_medium SAE snapshot directory. Never a repo_id.",
    )
    p.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    p.add_argument("--snippets-path", default=str(DEFAULT_SNIPPETS_PATH))
    p.add_argument("--control-rng-seed", type=int, default=DEFAULT_CONTROL_RNG_SEED)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument(
        "--server-name",
        default="127.0.0.1",
        help="Bind address -- localhost only. Reach it via an SSH port-forward (see README); never 0.0.0.0 on a shared compute node.",
    )
    p.add_argument("--server-port", type=int, default=7860)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sweep = _load_sweep_module()

    manifest = load_manifest(Path(args.manifest_path), sweep)
    snippets = load_snippets(Path(args.snippets_path))
    control_feature_idx = resolve_control_feature_idx(sweep, manifest, control_rng_seed=args.control_rng_seed)
    print(f"feature manifest: {args.manifest_path} ({len(manifest['features'])} features)")
    print(f"control feature: idx={control_feature_idx} (control_rng_seed={args.control_rng_seed})")

    bundle = load_bundle(sweep, args.model_path, args.sae_path, device=args.device, dtype=args.dtype)

    demo = build_ui(bundle, manifest, snippets, control_feature_idx, args.control_rng_seed)
    demo.launch(server_name=args.server_name, server_port=args.server_port, share=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
