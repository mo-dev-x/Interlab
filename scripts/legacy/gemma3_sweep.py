"""D2.1 -- Gemma 3 12B steer/ablate sweep harness.

Out-of-chain by PI directive: scripts/legacy/ is outside the certification
chain. This harness does NOT touch the registry, FeatureIndex, or
config_lifecycle machinery jobs/steer.py uses for Qwen -- no
characterization manifest exists for Gemma yet. It reuses only the
low-level, registry-free intervention primitives (attach, InterventionSpec,
control_arms) that both instruments share.

OFFLINE IS MANDATORY (established 2026-08-07, job 397854 died on exactly
this: Tamia compute nodes have no outbound internet, and a request that
resolves from cache on the login node still attempts a network revision
check on the compute node and hangs ~50 min in). Consequently:
  - --model-path / --sae-path are LOCAL FILESYSTEM PATHS, never a repo_id
    or a bare "google/..." string, anywhere in the runtime load path.
  - load_model_and_sae() fails fast and loudly if either path is missing,
    rather than letting a loader silently fall back to the network.
  - The Week-2 Gradio tool needs the identical offline load path, so
    load_model_and_sae() is a standalone, reusable function -- import it,
    do not copy it.

Model loading uses transformer_lens's TransformerBridge (3.2.1+), not the
classic HookedTransformer.from_pretrained: Gemma 3's HF class
(Gemma3ForConditionalGeneration, multimodal wrapper) has no
transformer_lens.pretrained.weight_conversions entry the way Qwen2 does
(see jobs/steer.py's _load_local_hooked_transformer, which is Qwen2-only
and NotImplementedError's on anything else). TransformerBridge wraps the
HF model directly instead of converting a state dict, so it needs no
per-architecture converter. enable_compatibility_mode(no_processing=True)
is called for two reasons at once: it registers the legacy hook-name
aliases (blocks.N.hook_resid_post) that interplab.interventions.hooks.attach
requires, AND no_processing=True forces fold_ln/center_writing_weights/
center_unembed to False -- the same "never fold" discipline
_load_local_hooked_transformer uses for Qwen, for the same reason: folding
would silently shift the numbers the SAE was calibrated against.

SAE loading reads the raw Gemma-Scope-2 safetensors format
(config.json + params.safetensors) directly off local disk. This
deliberately mirrors -- but does not call -- sae_lens's own
gemma_3_sae_huggingface_loader (pretrained_sae_loaders.py:687), which is
hardwired to hf_hub_download and therefore always repo_id-routed. Only the
network-fetch step is replaced; the actual SAE class construction
(SAE.from_dict + load_state_dict) is the same sae_lens machinery the hub
path itself uses, per "reuse, do not reimplement."
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Feature table (D2.1 brief, 9 final + 1 optional, no substitutions)
# ---------------------------------------------------------------------------

# maxActApprox is a SAMPLE-MAX PROXY over Neuronpedia's activation set, not
# a corpus max. Every artifact that carries this number -- this constant,
# the feature manifest, every output record -- repeats that caveat inline
# rather than only in prose, per the D2.1 addendum's wording requirement.
MAX_ACT_APPROX_CAVEAT = (
    "maxActApprox is a sample-max proxy over Neuronpedia's activation set, not a corpus max."
)

SAE_ID = "layer_31_width_16k_l0_medium"
SAE_RELEASE = "gemma-scope-2-12b-pt-res"
SAE_REPO_ID = "google/gemma-scope-2-12b-pt"
SAE_REPO_REVISION = "bbabd1e4a3964914f5bf0f5f99b56c2a2da09802"  # confirmed at commit e6369b3
MODEL_ID = "google/gemma-3-12b-pt"
LAYER = 31
N_LAYERS = 48
DEPTH_FRACTION = LAYER / N_LAYERS  # 0.6458333... ("64.6%")
WIDTH = 16384
L0_ADVERTISED = 60
L0_VARIANT = "medium"

# CORRECTED 2026-08-07 (D2.1 addendum): the Qwen instrument is rwu04lpb.
# 81920/16x belongs to a DIFFERENT, superseded checkpoint (9odeg5hb,
# pile-10k, abandoned) -- never carry that number into a new artifact.
#
# Named "reference metadata", not "comparison" (schema name audit): the
# approved framing is convergent evidence from two independent
# measurements, not a controlled comparison -- five axes are unmatched
# (model, SAE architecture, expansion ratio, training provenance, relative
# depth). A nested object literally named "comparison" is the strongest
# possible smuggled claim; a reader who sees only the field name, with no
# surrounding text, would believe it licenses a controlled comparison the
# framing explicitly declines to assert.
QWEN_REFERENCE_METADATA = {
    "checkpoint_id": "rwu04lpb",
    "d_in": 5120,
    "d_sae": 163840,
    "architecture": "topk",
    "topk_k": 100,
    "expansion_factor": 32,
    "training_tokens": "400M FineWeb",
    "layer": 28,
    "n_layers": 48,
    "depth_fraction": 28 / 48,  # 0.58333... ("58.3%")
}
# Deliberately not a derived difference, and not named "gap": Gemma's
# depth_fraction (31/48 = 64.6%) vs Qwen's (28/48 = 58.3%) is an escalated
# CONFOUND on the cross-model comparison, not a validated comparison point.
# A field named "gap" invites the magnitude comparison the approved framing
# prohibits, and field names travel further than caveats -- so this carries
# only Qwen's raw depth_fraction; the reader subtracts if they choose.
DEPTH_FRACTION_QWEN = QWEN_REFERENCE_METADATA["depth_fraction"]

FEATURES: list[dict[str, Any]] = [
    {"idx": 250, "label": "advisory / instructional imperatives", "domain_class": "instruction", "maxActApprox": 10717.3232, "density": 0.021364},
    {"idx": 500, "label": "company & brand proper nouns", "domain_class": "entity", "maxActApprox": 5909.8086, "density": 0.007314},
    {"idx": 2048, "label": "date / timestamp components", "domain_class": "temporal", "maxActApprox": 5480.3105, "density": 0.002244},
    {"idx": 2500, "label": "abstract nouns (internal states, moral qualities)", "domain_class": "abstract", "maxActApprox": 2115.7334, "density": 0.004149},
    {"idx": 3500, "label": "staff / personnel in service contexts", "domain_class": "entity", "maxActApprox": 4613.6392, "density": 0.002221},
    {"idx": 4500, "label": "person names", "domain_class": "entity", "maxActApprox": 3998.2297, "density": 0.007500},
    {"idx": 11000, "label": "named entities / media titles", "domain_class": "entity", "maxActApprox": 2303.7383, "density": 0.003796},
    {"idx": 12800, "label": "ordinal numerics in sports reporting", "domain_class": "numeric", "maxActApprox": 5148.6909, "density": 0.000782},
    {"idx": 900, "label": "dynamic action verbs", "domain_class": "syntax", "maxActApprox": 2774.4246, "density": 0.012900, "low_confidence": True},
]
OPTIONAL_FEATURES: list[dict[str, Any]] = [
    {"idx": 8000, "label": "structured-data terminology", "domain_class": "syntax", "maxActApprox": 2653.2581, "density": 0.000221},
]
# Failed snippet verification -- never admit these, listed so a future editor
# can see they were considered and rejected rather than simply missing.
REJECTED_FEATURE_IDXS = frozenset({12345, 7777, 6000, 100, 10500, 13500, 9600, 7000, 400, 14000})

DOSES: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
MODES: tuple[str, ...] = ("steer", "ablate")

# 8, matching Qwen's prompt count exactly (D2.1 fix 1): the PM refused to
# cut doses 6 -> 3 because "a 3-point curve cannot distinguish a plateau
# from a linear rise" -- the same resolution argument applies to prompts,
# and matching Qwen's count keeps the two experiments procedurally aligned
# at zero argumentative cost.
DEFAULT_PROMPTS: list[str] = [
    "Tell me about your day.",
    "Describe a walk through a city street.",
    "What advice would you give to someone starting a new job?",
    "Write a short paragraph about the weather this week.",
    "Explain how to plan a small dinner party.",
    "Describe your favorite way to spend a weekend.",
    "What makes a good story, in your opinion?",
    "Summarize the plot of a movie you might watch tonight.",
]

DEFAULT_OUT_DIR = REPO_ROOT / "results" / "gemma3_sweep"
FEATURE_MANIFEST_FILENAME = "feature_manifest.json"


# ---------------------------------------------------------------------------
# Feature manifest (D2.1 addendum): pre-staged once, read by both this
# harness and the (future) Week-2 Gradio tool, which has no outbound
# internet either and so cannot call Neuronpedia at runtime.
# ---------------------------------------------------------------------------

def build_feature_manifest_records(*, include_optional: bool = False) -> list[dict[str, Any]]:
    pool = list(FEATURES) + (list(OPTIONAL_FEATURES) if include_optional else [])
    records = []
    for f in pool:
        records.append(
            {
                "idx": f["idx"],
                "label": f["label"],
                "domain_class": f["domain_class"],
                "maxActApprox": f["maxActApprox"],
                "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
                "density": f["density"],
                "sae_id": SAE_ID,
                "layer": LAYER,
                "width": WIDTH,
                "l0_variant": L0_VARIANT,
                "low_confidence": bool(f.get("low_confidence", False)),
                # Deliberately absent, not null: the tool will add this field
                # later. Leaving it out (rather than pre-populating None)
                # keeps "has sample_snippets" a clean presence check for
                # whatever reads this manifest next.
            }
        )
    return records


def write_feature_manifest(out_dir: Path, *, include_optional: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FEATURE_MANIFEST_FILENAME
    payload = {
        "schema_note": (
            "One record per feature: idx, label, domain_class, maxActApprox, density, "
            "sae_id, layer, width, l0_variant. Open schema -- the Gradio tool adds "
            "sample_snippets later; do not treat this as a closed/strict record shape."
        ),
        "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
        "sae_release": SAE_RELEASE,
        "sae_repo_id": SAE_REPO_ID,
        "sae_repo_revision": SAE_REPO_REVISION,
        "model_id": MODEL_ID,
        "features": build_feature_manifest_records(include_optional=include_optional),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_feature_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"feature manifest not found at {path}; run this harness once (any mode) to "
            "pre-stage it, or call write_feature_manifest() directly"
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Offline, local-path-only loading -- reusable by the Week-2 Gradio tool.
# ---------------------------------------------------------------------------

def _fail_if_missing(path: Path, *, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{what} not found at {path!r}. This harness only accepts pre-staged local "
            f"filesystem paths -- it will not fall back to a network fetch."
        )


def load_sae_from_local_snapshot(sae_path: Path, *, device: str = "cpu", dtype: str = "float32"):
    """Load a Gemma-Scope-2 JumpReLU SAE from a local directory containing
    the raw HF-hosted files (config.json + params.safetensors), with no
    huggingface_hub call of any kind.

    Mirrors sae_lens.loading.pretrained_sae_loaders.gemma_3_sae_huggingface_loader
    / get_gemma_3_config_from_hf (installed sae_lens 6.44.2,
    pretrained_sae_loaders.py:588-738) field-for-field, but sources every
    value from local disk instead of a repo_id + hf_hub_download.
    """
    import torch
    from safetensors.torch import load_file
    from sae_lens import SAE

    config_path = sae_path / "config.json"
    params_path = sae_path / "params.safetensors"
    _fail_if_missing(config_path, what="SAE config.json")
    _fail_if_missing(params_path, what="SAE params.safetensors")

    raw_cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if raw_cfg.get("architecture") != "jump_relu":
        raise ValueError(
            f"unexpected SAE architecture in {config_path}: {raw_cfg.get('architecture')!r} "
            "(expected 'jump_relu' -- this loader only handles Gemma Scope 2 JumpReLU SAEs)"
        )

    layer_match = re.search(r"layer_(\d+)", sae_path.name) or re.search(r"layer_(\d+)", str(sae_path))
    if layer_match is None:
        raise ValueError(
            f"could not extract a layer number (layer_<N>) from SAE path {sae_path}; "
            "the local snapshot directory name must preserve this component"
        )
    layer = int(layer_match.group(1))
    hook_name = f"blocks.{layer}.hook_resid_post"

    raw_state_dict = load_file(str(params_path), device=device)
    d_in, d_sae = raw_state_dict["w_enc"].shape

    model_name = raw_cfg.get("model_name", MODEL_ID)
    if "google" not in model_name:
        model_name = "google/" + model_name

    cfg_dict = {
        "architecture": "jumprelu",
        "d_in": int(d_in),
        "d_sae": int(d_sae),
        "dtype": dtype,
        "device": device,
        "model_name": model_name,
        "hook_name": hook_name,
        "hook_head_index": None,
        "finetuning_scaling_factor": False,
        "sae_lens_training_version": None,
        "prepend_bos": True,
        "normalize_activations": "none",
        "reshape_activations": "none",
        "hf_hook_name": raw_cfg.get("hf_hook_point_in"),
    }

    state_dict = {
        "W_enc": raw_state_dict["w_enc"],
        "W_dec": raw_state_dict["w_dec"],
        "b_enc": raw_state_dict["b_enc"],
        "b_dec": raw_state_dict["b_dec"],
        "threshold": raw_state_dict["threshold"],
    }

    sae = SAE.from_dict(cfg_dict)
    sae.load_state_dict(state_dict, assign=True)
    sae = sae.to(dtype=getattr(torch, dtype), device=device)
    sae.eval()
    return sae


def load_model_and_sae(
    model_path: str | Path,
    sae_path: str | Path,
    *,
    device: str = "cuda",
    dtype: str = "bfloat16",
):
    """The one offline, local-path-only loader for both the model and the
    SAE. Reusable by the Week-2 Gradio tool -- import this function rather
    than duplicating its loading logic (same offline constraint applies
    there: the tool also runs inside a compute allocation with no outbound
    internet).

    Fails fast and loudly if either path is missing, or if the model's
    hidden size does not match the SAE's d_in (the one escalate-to-PM
    condition confirmed structurally at commit e6369b3).
    """
    import torch
    from transformer_lens.model_bridge.bridge import TransformerBridge
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError(
            "HF_HUB_OFFLINE=1 is not set in the environment. On a Tamia compute node this "
            "is mandatory (job 397854 died without it) -- refusing to proceed rather than "
            "risk a silent network fetch. Export it in the launcher payload before invoking "
            "this harness."
        )

    model_path = Path(model_path)
    sae_path = Path(sae_path)
    _fail_if_missing(model_path, what="model snapshot directory")
    _fail_if_missing(sae_path, what="SAE snapshot directory")

    torch_dtype = getattr(torch, dtype)

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    hf_model = AutoModelForCausalLM.from_pretrained(
        str(model_path), torch_dtype=torch_dtype, local_files_only=True
    )

    # model_name is the literal local path, never "google/gemma-3-12b-pt":
    # with hf_model given, TransformerBridge derives hf_config from
    # hf_model.config directly (transformer_lens/model_bridge/sources/
    # transformers.py:339-342) and never calls AutoConfig.from_pretrained,
    # so this string only ever ends up in bridge_config.model_name as a
    # label -- but passing the local path anyway is the maximally literal
    # reading of "never a repo_id anywhere in the runtime path."
    bridge = TransformerBridge.boot_transformers(
        model_name=str(model_path),
        hf_model=hf_model,
        tokenizer=tokenizer,
        device=device,
        dtype=torch_dtype,
    )
    # no_processing=True: forces fold_ln/center_writing_weights/center_unembed
    # to False (matches jobs/steer.py's _load_local_hooked_transformer
    # discipline for Qwen -- folding would shift the numbers the SAE was
    # calibrated against). Also registers the legacy hook-name aliases
    # (blocks.N.hook_resid_post) that interplab.interventions.hooks.attach
    # requires.
    bridge.enable_compatibility_mode(no_processing=True)

    sae = load_sae_from_local_snapshot(sae_path, device=device, dtype="float32")

    model_d_model = bridge.cfg.d_model
    if model_d_model != sae.cfg.d_in:
        raise RuntimeError(
            f"d_model mismatch: model reports d_model={model_d_model}, SAE reports "
            f"d_in={sae.cfg.d_in}. This is the escalate-to-PM condition from D1.3 -- stop "
            "here, do not proceed with a mismatched hook."
        )

    return bridge, sae


# ---------------------------------------------------------------------------
# Provenance: checkpoint identity hash and harness git SHA
# ---------------------------------------------------------------------------

def compute_checkpoint_hash(model_path: str, sae_path: str, *, dry_run: bool) -> tuple[str, str]:
    """Returns (hash, basis). In a real run, hashes the small identity files
    (model config.json, SAE config.json + params.safetensors) -- not the
    full multi-GB model weights, which would make every job-start pay a
    minutes-long tax. In a dry run, hashes only the path strings, since dry
    runs are explicitly CPU-free and must not require the files to exist."""
    from interplab.core import hashing

    if dry_run:
        basis = "path-strings-only (dry-run, files not required to exist)"
        digest = hashlib.sha256(f"{model_path}\0{sae_path}".encode("utf-8")).hexdigest()
        return f"sha256:{digest}", basis

    parts: list[str] = [f"model_path\0{model_path}", f"sae_path\0{sae_path}"]
    model_cfg = Path(model_path) / "config.json"
    if model_cfg.is_file():
        parts.append(f"model_config\0{hashing.hash_file(model_cfg)}")
    sae_cfg = Path(sae_path) / "config.json"
    sae_params = Path(sae_path) / "params.safetensors"
    if sae_cfg.is_file():
        parts.append(f"sae_config\0{hashing.hash_file(sae_cfg)}")
    if sae_params.is_file():
        parts.append(f"sae_params\0{hashing.hash_file(sae_params)}")
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    basis = "model config.json + SAE config.json + SAE params.safetensors content hashes"
    return f"sha256:{digest}", basis


def harness_git_provenance() -> dict[str, Any]:
    """Read at execution time, not authoring time -- a provenance field
    that names the wrong commit is worse than an absent one, because it
    will be believed (same failure class as reusing line numbers across
    commits). Also records whether the working tree was dirty when this
    ran: a SHA alone does not prove the code that ran matches that commit
    if uncommitted changes were present."""
    try:
        sha_out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10,
        )
        status_out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10,
        )
        return {"sha": sha_out.stdout.strip(), "dirty": bool(status_out.stdout.strip())}
    except Exception as exc:  # not fatal -- provenance-best-effort, never blocks a run
        return {"sha": f"unknown (git rev-parse failed: {exc})", "dirty": None}


def derive_seed(*parts: Any) -> int:
    """Deterministic seed from an arbitrary tuple of (prompt_id, feature_idx,
    dose_multiple, mode, arm, ...) -- so any single cell is exactly
    reproducible in isolation, per the D2.1 brief. Distinct from
    jobs/steer.py's Qwen pipeline, which reuses one global config seed for
    every generation in a run; this harness derives a fresh seed per cell
    instead, as D2.1 explicitly specifies."""
    key = "\0".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**31 - 1)


# ---------------------------------------------------------------------------
# Job matrix construction (no torch/model access -- safe for a dry run)
# ---------------------------------------------------------------------------

def pick_control_feature_idx(*, exclude: set[int], control_rng_seed: int, d_sae: int = WIDTH) -> int:
    import numpy as np

    rng = np.random.default_rng(control_rng_seed)
    while True:
        candidate = int(rng.integers(0, d_sae))
        if candidate not in exclude:
            return candidate


def build_job_matrix(
    *,
    features: list[dict[str, Any]],
    doses: tuple[float, ...],
    modes: tuple[str, ...],
    prompts: list[str],
    control_feature_idx: int,
    checkpoint_hash: str,
    positions: str = "all",
) -> list[dict[str, Any]]:
    """Constructs the full flat list of planned records (grid cells x arms
    x prompts, plus baselines), with NO torch/model access -- every field
    is either config-derived or hash-derived. This is exactly the CPU-free
    dry run's job matrix.

    Grid: 9 features x 6 doses x 2 modes = 108 cells (feature, dose, mode).
    For "ablate" mode dose_multiple is carried only for provenance/seed-
    derivation uniformity -- the realized absolute_clamp_value is always
    0.0 regardless of which of the 6 nominal dose slots a record occupies,
    since ablation has no dose. Each cell produces a "target" record (the
    named feature clamped/ablated) and a "control" record (the single fixed
    random-feature control, drawn once via pick_control_feature_idx and
    reused at every dose and in ablation, per the D2.1 brief) for every
    prompt. Baselines are unhooked and run once per prompt, independent of
    the grid.

    The record key extends the brief's stated 5-tuple
    (feature_idx, mode, dose_multiple, prompt_id, seed) with an explicit
    "arm" component: without it, two control records paired with different
    target features at the same nominal dose_multiple would collide, since
    they share the same hooked control_feature_idx but different absolute
    clamp values and different derived seeds.
    """
    records: list[dict[str, Any]] = []

    for i, prompt in enumerate(prompts):
        prompt_id = f"p{i}"
        seed = derive_seed(prompt_id, None, None, "baseline", "none")
        records.append(
            {
                "feature_idx": None,
                "mode": "baseline",
                "arm": "none",
                "hooked_feature_idx": None,
                "dose_multiple": None,
                "absolute_clamp_value": None,
                "prompt_id": prompt_id,
                "prompt": prompt,
                "seed": seed,
                "positions": "all",
                "kind": "noop",
                "checkpoint_hash": checkpoint_hash,
            }
        )

    for feature in features:
        target_idx = feature["idx"]
        max_act_approx = feature["maxActApprox"]
        for mode in modes:
            kind = "clamp" if mode == "steer" else "ablate"
            for dose in doses:
                seed_base = (target_idx, mode, dose)
                if mode == "steer":
                    absolute_clamp = dose * max_act_approx
                else:
                    absolute_clamp = 0.0  # ablation ignores dose; carried for schema uniformity only

                for arm, hooked_idx in (("target", target_idx), ("random_feature", control_feature_idx)):
                    for i, prompt in enumerate(prompts):
                        prompt_id = f"p{i}"
                        seed = derive_seed(prompt_id, *seed_base, arm)
                        records.append(
                            {
                                "feature_idx": target_idx,
                                "mode": mode,
                                "arm": arm,
                                "hooked_feature_idx": hooked_idx,
                                "dose_multiple": dose,
                                "absolute_clamp_value": absolute_clamp,
                                "maxActApprox": max_act_approx,
                                "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
                                "density": feature["density"],
                                "domain_class": feature["domain_class"],
                                "prompt_id": prompt_id,
                                "prompt": prompt,
                                "seed": seed,
                                "positions": positions,
                                "kind": kind,
                                "checkpoint_hash": checkpoint_hash,
                            }
                        )
    return records


def _record_filename(record: dict[str, Any]) -> str:
    feature_part = "none" if record["feature_idx"] is None else str(record["feature_idx"])
    dose_part = "none" if record["dose_multiple"] is None else str(record["dose_multiple"])
    return (
        f"f{feature_part}_{record['mode']}_{record['arm']}_dose{dose_part}_"
        f"{record['prompt_id']}_seed{record['seed']}.json"
    )


def _record_metadata(record: dict[str, Any], *, git_provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "sae_id": SAE_ID,
        "sae_release": SAE_RELEASE,
        "sae_repo_id": SAE_REPO_ID,
        "sae_repo_revision": SAE_REPO_REVISION,
        "layer": LAYER,
        "n_layers": N_LAYERS,
        "depth_fraction": DEPTH_FRACTION,
        "width": WIDTH,
        "l0_advertised": L0_ADVERTISED,
        "l0_variant": L0_VARIANT,
        "model_id": MODEL_ID,
        "qwen_reference_metadata": QWEN_REFERENCE_METADATA,
        "depth_fraction_qwen": DEPTH_FRACTION_QWEN,
        "harness_git_sha": git_provenance["sha"],
        "harness_git_dirty": git_provenance["dirty"],
    }


# ---------------------------------------------------------------------------
# Module-identity gate (D2.1 fix 4): BEFORE the fan-out, every real run
# must prove blocks.{LAYER}.hook_resid_post resolves to the TEXT tower's
# block LAYER on this multimodal wrapper, not an offset module or the
# vision stack. The failure being ruled out is not "it crashed" -- it is
# "it ran and hooked the wrong tensor," which produces a complete,
# plausible, wrong dataset. A mismatch on any check here is stop-and-
# escalate, not adapt: these functions raise rather than warn.
# ---------------------------------------------------------------------------

# Declared BEFORE any equivalence number is seen, per the review. The
# bridge's own docstring states no_processing mode's "logits/activations
# match HF, *not* legacy HookedTransformer" -- so near-exact agreement is
# expected, but not bit-exact: bf16 rounding and SDPA-vs-eager attention
# kernel differences are legitimate sources of small cross-implementation
# noise, not evidence of a module-identity failure. These two thresholds
# are the full passing bar; nothing here is adjusted after seeing a number.
EQUIVALENCE_COSINE_MIN = 0.999
EQUIVALENCE_REL_L2_MAX = 1e-2


def verify_module_identity(bridge, sae) -> dict[str, Any]:
    """Run once, immediately after load, before any generation. Resolves
    the fully-qualified module path the hook attaches to, confirms the
    hooked tensor's last dim is 3840 (the text-tower width -- the exact
    reason d_model=3840 was the D1.3 decisive check), and confirms
    n_layers==48 / d_model==3840 on the loaded config."""
    hook_name = sae.cfg.metadata.hook_name
    hook_point = bridge.get_hook_point(hook_name)
    if hook_point is None:
        raise RuntimeError(
            f"module-identity gate FAILED: {hook_name!r} does not resolve to any hook "
            f"point on this bridge. Stop and escalate -- do not adapt the hook name."
        )

    module_path = None
    for name, module in bridge.named_modules():
        if module is hook_point:
            module_path = name
            break
    if module_path is None:
        raise RuntimeError(
            f"module-identity gate FAILED: {hook_name!r} resolved to a HookPoint that is "
            f"not reachable via bridge.named_modules() -- cannot establish its "
            f"fully-qualified path. Stop and escalate."
        )

    suspicious_tokens = ("vision", "vit", "image", "siglip", "clip")
    if any(tok in module_path.lower() for tok in suspicious_tokens):
        raise RuntimeError(
            f"module-identity gate FAILED: hook path {module_path!r} looks like it belongs "
            f"to the vision stack, not the text tower. Stop and escalate."
        )

    n_layers = bridge.cfg.n_layers
    d_model = bridge.cfg.d_model
    if n_layers != N_LAYERS:
        raise RuntimeError(
            f"module-identity gate FAILED: bridge.cfg.n_layers={n_layers}, expected "
            f"{N_LAYERS}. Stop and escalate."
        )
    if d_model != 3840:
        raise RuntimeError(
            f"module-identity gate FAILED: bridge.cfg.d_model={d_model}, expected 3840 "
            f"(the D1.3 decisive check: the SAE's own w_enc shape fixes d_in=3840, and the "
            f"text-decoder hidden size must equal it). Stop and escalate."
        )

    captured: dict[str, Any] = {}

    def _capture_hook(tensor, hook):
        captured["tensor"] = tensor
        return tensor

    with bridge.hooks(fwd_hooks=[(hook_name, _capture_hook)]):
        tokens = bridge.to_tokens("The quick brown fox jumps over the lazy dog.")
        bridge(tokens)

    if "tensor" not in captured:
        raise RuntimeError(
            f"module-identity gate FAILED: hook {hook_name!r} never fired during a forward "
            f"pass. Stop and escalate."
        )
    hooked_shape = tuple(captured["tensor"].shape)
    if hooked_shape[-1] != 3840:
        raise RuntimeError(
            f"module-identity gate FAILED: hooked tensor shape {hooked_shape} has last dim "
            f"{hooked_shape[-1]}, expected 3840. This is exactly the failure mode ruled out "
            f"here: the hook ran and captured a tensor, but not the text tower's residual "
            f"stream. Stop and escalate."
        )

    report = {
        "hook_name": hook_name,
        "module_path": module_path,
        "hooked_tensor_shape": list(hooked_shape),
        "n_layers": n_layers,
        "d_model": d_model,
        "passed": True,
    }
    print(f"module-identity gate PASSED:\n{json.dumps(report, indent=2)}")
    return report


def verify_raw_hf_equivalence(bridge, prompt: str, seed: int) -> dict[str, Any]:
    """Same prompt, same seed, both paths: the TransformerBridge's hooked
    blocks.{LAYER}.hook_resid_post capture vs. the underlying raw HF
    model's own hidden_states at the same layer, via bridge.original_model
    -- the exact same weights object the bridge wraps, not a second,
    possibly-diverged load. Tolerances are declared at module scope
    (EQUIVALENCE_COSINE_MIN, EQUIVALENCE_REL_L2_MAX), above, before this
    function is ever called with a real number.
    """
    import torch

    torch.manual_seed(seed)
    tokens = bridge.to_tokens(prompt)

    captured: dict[str, Any] = {}

    def _capture_hook(tensor, hook):
        captured["tensor"] = tensor.detach().clone()
        return tensor

    hook_name = f"blocks.{LAYER}.hook_resid_post"
    with bridge.hooks(fwd_hooks=[(hook_name, _capture_hook)]):
        bridge(tokens)
    bridge_tensor = captured["tensor"]

    raw_hf_model = bridge.original_model
    with torch.no_grad():
        hf_out = raw_hf_model(tokens, output_hidden_states=True)
    hidden_states = hf_out.hidden_states
    if len(hidden_states) != N_LAYERS + 1:
        raise RuntimeError(
            f"equivalence check FAILED: raw HF model returned {len(hidden_states)} "
            f"hidden_states entries, expected {N_LAYERS + 1} (embeddings + one per layer) "
            f"-- cannot safely index layer {LAYER}'s post-block state. Stop and escalate."
        )
    raw_hf_tensor = hidden_states[LAYER + 1].to(bridge_tensor.dtype)

    bridge_flat = bridge_tensor.reshape(-1).float()
    raw_flat = raw_hf_tensor.reshape(-1).float()
    if bridge_flat.shape != raw_flat.shape:
        raise RuntimeError(
            f"equivalence check FAILED: shape mismatch bridge={tuple(bridge_tensor.shape)} "
            f"vs raw_hf={tuple(raw_hf_tensor.shape)}. Stop and escalate."
        )

    cosine_sim = torch.nn.functional.cosine_similarity(bridge_flat, raw_flat, dim=0).item()
    rel_l2 = ((bridge_flat - raw_flat).norm() / raw_flat.norm()).item()
    passed = cosine_sim >= EQUIVALENCE_COSINE_MIN and rel_l2 <= EQUIVALENCE_REL_L2_MAX

    report = {
        "prompt": prompt,
        "seed": seed,
        "cosine_similarity": cosine_sim,
        "relative_l2_error": rel_l2,
        "cosine_min_declared": EQUIVALENCE_COSINE_MIN,
        "rel_l2_max_declared": EQUIVALENCE_REL_L2_MAX,
        "passed": passed,
    }
    print(f"raw-HF equivalence check {'PASSED' if passed else 'FAILED'}:\n{json.dumps(report, indent=2)}")
    if not passed:
        raise RuntimeError(
            f"raw-HF equivalence check FAILED against tolerances declared before this run: "
            f"{report}. Stop and escalate -- do not loosen the tolerance after seeing this "
            f"number."
        )
    return report


# ---------------------------------------------------------------------------
# Real generation (requires a loaded model + SAE -- never called in --dry-run)
# ---------------------------------------------------------------------------

def run_cell(model, sae, record: dict[str, Any], *, sampling: dict[str, Any]) -> str:
    import torch

    from interplab.interventions.hooks import attach
    from interplab.interventions.spec import InterventionSpec

    if record["kind"] == "noop":
        spec = InterventionSpec(
            kind="noop", feature_index=None, value_in_max_units=None, corpus_max=None,
            positions="all", checkpoint_hash=record["checkpoint_hash"], direction_seed=None,
        )
    elif record["kind"] == "ablate":
        spec = InterventionSpec(
            kind="ablate", feature_index=record["hooked_feature_idx"], value_in_max_units=None,
            corpus_max=None, positions=record["positions"], checkpoint_hash=record["checkpoint_hash"],
            direction_seed=None,
        )
    else:
        spec = InterventionSpec(
            kind="clamp", feature_index=record["hooked_feature_idx"], value_in_max_units=record["dose_multiple"],
            corpus_max=record["maxActApprox"], positions=record["positions"],
            checkpoint_hash=record["checkpoint_hash"], direction_seed=None,
        )

    tokens = model.to_tokens(record["prompt"])
    prompt_lengths = tokens.shape[1] if spec.positions == "generated_only" else None
    torch.manual_seed(record["seed"])
    with attach(model, sae, spec, prompt_lengths=prompt_lengths):
        output = model.generate(
            tokens,
            max_new_tokens=sampling["max_new_tokens"],
            temperature=sampling["temperature"],
            top_p=sampling["top_p"],
            do_sample=sampling["temperature"] > 0,
            verbose=False,
        )
    return model.to_string(output[0, tokens.shape[1] :])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_prompts(prompts_file: str | None) -> list[str]:
    if prompts_file is None:
        return list(DEFAULT_PROMPTS)
    path = Path(prompts_file)
    _fail_if_missing(path, what="prompts file")
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(p, str) for p in data):
            raise ValueError(f"{path} must contain a JSON list of strings")
        return data
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D2.1 Gemma 3 12B steer/ablate sweep harness")
    p.add_argument("--model-path", required=True, help="Local filesystem path to the gemma-3-12b-pt snapshot directory")
    p.add_argument("--sae-path", required=True, help="Local filesystem path to the layer_31_width_16k_l0_medium snapshot directory")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory; default results/gemma3_sweep/")
    p.add_argument("--dry-run", action="store_true", help="CPU-free: construct the full job matrix and write stub records, no model/SAE load")
    p.add_argument("--prompts-file", default=None, help="JSON list or newline-delimited text file; default is 5 built-in generic prompts")
    p.add_argument("--include-optional-10th", action="store_true", help="Include feature 8000 (optional 10th) -- OFF by default, keeps the grid at exactly 9 features")
    p.add_argument("--doses", type=float, nargs="+", default=list(DOSES))
    p.add_argument("--positions", choices=["all", "generated_only"], default="all")
    p.add_argument("--control-rng-seed", type=int, default=1337, help="Fixed, recorded RNG seed for drawing the single shared random-feature control")
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--max-new-tokens", type=int, default=200)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--top-p", type=float, default=0.9)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)

    manifest_path = write_feature_manifest(out_dir, include_optional=args.include_optional_10th)
    manifest = load_feature_manifest(manifest_path)
    print(f"feature manifest: {manifest_path} ({len(manifest['features'])} features)")

    features = FEATURES + (OPTIONAL_FEATURES if args.include_optional_10th else [])
    exclude = {f["idx"] for f in FEATURES} | {f["idx"] for f in OPTIONAL_FEATURES} | REJECTED_FEATURE_IDXS
    control_feature_idx = pick_control_feature_idx(exclude=exclude, control_rng_seed=args.control_rng_seed)
    print(f"control feature: idx={control_feature_idx} (control_rng_seed={args.control_rng_seed})")

    checkpoint_hash, checkpoint_hash_basis = compute_checkpoint_hash(
        args.model_path, args.sae_path, dry_run=args.dry_run
    )
    git_provenance = harness_git_provenance()
    print(f"harness git provenance: sha={git_provenance['sha']} dirty={git_provenance['dirty']}")

    prompts = _load_prompts(args.prompts_file)
    matrix = build_job_matrix(
        features=features,
        doses=tuple(args.doses),
        modes=MODES,
        prompts=prompts,
        control_feature_idx=control_feature_idx,
        checkpoint_hash=checkpoint_hash,
        positions=args.positions,
    )
    n_cells = len(features) * len(args.doses) * len(MODES)
    print(
        f"job matrix: {n_cells} (feature, dose, mode) cells "
        f"({len(features)} features x {len(args.doses)} doses x {len(MODES)} modes), "
        f"{len(matrix)} total records ({len(prompts)} prompts x 2 arms x {n_cells} cells, "
        f"plus {len(prompts)} baseline records)"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    sampling = {
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
    }

    model = sae = None
    if not args.dry_run:
        model, sae = load_model_and_sae(
            args.model_path, args.sae_path, device=args.device, dtype=args.dtype
        )

        # Hard gate, BEFORE anything else touches the fan-out (D2.1 fix 4).
        # Stop-and-escalate, not adapt: both functions raise on failure,
        # which aborts main() before a single sweep record is generated.
        identity_report = verify_module_identity(model, sae)
        equivalence_report = verify_raw_hf_equivalence(model, prompts[0], seed=derive_seed("module-identity-check"))
        (out_dir / "module_identity_report.json").write_text(
            json.dumps({"module_identity": identity_report, "raw_hf_equivalence": equivalence_report}, indent=2),
            encoding="utf-8",
        )

    for record in matrix:
        payload = _record_metadata(record, git_provenance=git_provenance)
        payload["model_path"] = str(Path(args.model_path).resolve()) if Path(args.model_path).exists() else args.model_path
        payload["sae_path"] = str(Path(args.sae_path).resolve()) if Path(args.sae_path).exists() else args.sae_path
        payload["checkpoint_hash_basis"] = checkpoint_hash_basis

        if args.dry_run:
            payload["generated"] = False
            payload["text"] = None
        else:
            payload["generated"] = True
            payload["text"] = run_cell(model, sae, record, sampling=sampling)

        out_path = out_dir / _record_filename(record)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {len(matrix)} record(s) under {out_dir}")
    if args.dry_run:
        print("--dry-run: no model/SAE was loaded, no text was generated (stub records only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
