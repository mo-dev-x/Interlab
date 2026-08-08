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

Model loading (REVISED 2026-08-07, ported verbatim from Engineer 1's
job 398619 -- the run that produced the accepted D1.5 results):
TransformerBridge.boot_transformers was tried first and dies during
set_original_components with AttributeError: 'SiglipVisionModel' object
has no attribute 'vision_model' -- the installed transformer_lens's
generic bridge adapter assumes a .vision_model nesting under the vision
tower that this transformers version's SiglipVisionModel does not have.
Grepped: zero Gemma-3/Siglip-aware component mappings exist in the
installed package. That is a library incompatibility, not something to
repair under deadline. The classic HookedTransformer.from_pretrained path
works instead: transformer_lens's convert_gemma_weights dispatches on
cfg.original_architecture == "Gemma3ForConditionalGeneration", detects
multimodality via hasattr(gemma, "language_model"), resolves
base_model = gemma.language_model.model, and EXPLICITLY SKIPS
gemma.vision_tower itself -- no manual reach into .language_model is
needed here, transformer_lens already does the text-tower extraction.
fold_ln=False / center_writing_weights=False / center_unembed=False is
the same "never fold" discipline jobs/steer.py's
_load_local_hooked_transformer uses for Qwen, for the same reason:
folding would silently shift the numbers the SAE was calibrated against.

SAE loading uses sae_lens's own SAE.from_pretrained(release=, sae_id=),
not a hand-rolled local-safetensors reader. This looks like it violates
"never a repo_id anywhere in the runtime path" (MODEL_ID and SAE_RELEASE
below read like repo_ids) but does not violate the rule's actual purpose
(no network on compute nodes): job 398619 completed with zero network
under HF_HUB_OFFLINE=1, because hf_model= is already loaded locally and
_patch_gemma3_safetensors_shape_lookup() (below) routes the one call that
would otherwise bypass HF_HUB_OFFLINE through the local cache too. A
THIRD bug, found by Engineer 1, is why that patch exists: installed
sae_lens's Gemma-3 loader issues a raw requests.get() HTTP range read for
tensor shapes that bypasses huggingface_hub AND HF_HUB_OFFLINE entirely --
an immediate hang-then-fail on a compute node with no outbound internet.
load_sae_from_local_snapshot() (further below) is retained even though it
is no longer called: its handle_config_defaulting() fix is real, costs
nothing to keep, and this code path may simply go unused.

Gemma-specific caveat for whoever builds the Week-2 tool: this whole load
path works only because transformer_lens ships a hardcoded
convert_gemma_weights entry for this exact architecture string. A
different multimodal architecture with no registered converter hits
NotImplementedError in the same dispatch table. It would work unchanged
on text-only Gemma-3 (Gemma3ForCausalLM, no vision tower to skip).
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


# No longer called from load_model_and_sae() (see module docstring) --
# retained because handle_config_defaulting() below is a real, verified
# fix and costs nothing to keep even if this path goes unused.
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
    from sae_lens.loading.pretrained_sae_loaders import handle_config_defaulting

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
    # SAEConfig.from_dict filters cfg_dict down to SAEConfig's own dataclass
    # fields; "hook_name" is not one of them (it lives on cfg.metadata), so
    # passed flat it is silently dropped and sae.cfg.metadata.hook_name
    # comes back None -- attach() then fails at model.hooks(fwd_hooks=[(None,
    # ...)]) instead of here. handle_config_defaulting() is the same public
    # function the hub-based loading path already calls before
    # SAEConfig.from_dict; it re-nests hook_name (and the other loose keys
    # above) into cfg_dict["metadata"] correctly.
    cfg_dict = handle_config_defaulting(cfg_dict)

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


def _patch_gemma3_safetensors_shape_lookup() -> None:
    """Installed sae_lens's Gemma-3 loader issues a raw requests.get() HTTP
    range read for tensor shapes that bypasses huggingface_hub AND
    HF_HUB_OFFLINE entirely -- on a compute node with no outbound internet
    that is an immediate hang-then-fail. Ported verbatim from Engineer 1's
    job 398619 (the run that produced the accepted D1.5 results): routes
    the same shape lookup through hf_hub_download instead, which respects
    HF_HUB_OFFLINE and the local cache like every other call in this file."""
    import sae_lens.loading.pretrained_sae_loaders as psl
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    def _local_get_safetensors_tensor_shapes(repo_id: str, filename: str) -> dict:
        local_path = hf_hub_download(repo_id=repo_id, filename=filename)
        with safe_open(local_path, framework="pt") as f:
            return {k: list(f.get_slice(k).get_shape()) for k in f.keys()}

    psl.get_safetensors_tensor_shapes = _local_get_safetensors_tensor_shapes


def load_model_and_sae(
    model_path: str | Path,
    sae_path: str | Path,
    *,
    device: str = "cuda",
    dtype: str = "bfloat16",
):
    """The one offline loader for both the model and the SAE. Reusable by
    the Week-2 Gradio tool -- import this function rather than duplicating
    its loading logic (same offline constraint applies there: the tool
    also runs inside a compute allocation with no outbound internet).

    Ported verbatim from Engineer 1's job 398619 (see module docstring for
    why TransformerBridge was abandoned). Returns (model, sae, hf_model) --
    hf_model is the raw HF object powering the weight conversion, kept
    around so verify_raw_hf_equivalence has the actual weights object to
    compare against rather than a second, possibly-diverged load.
    hf_model comes back on CPU, not device -- see the loader comment
    above for why; the caller relocates it to a second GPU only for the
    brief equivalence forward pass, then frees it.

    Fails fast and loudly if the model path is missing or invalid, or if
    the model's hidden size does not match the SAE's d_in (the one
    escalate-to-PM condition confirmed structurally at commit e6369b3).
    """
    import torch
    from sae_lens import SAE
    from transformer_lens import HookedTransformer
    from transformers import AutoModel, AutoTokenizer

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
    if not (model_path / "config.json").is_file():
        print(f"ESCALATE: {str(model_path)!r} has no config.json -- not a valid local snapshot dir.")
        sys.exit(2)

    torch_dtype = getattr(torch, dtype)

    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    # Left on CPU deliberately (job 398885's OOM): moving hf_model to
    # device here put two ~24GB bf16 copies of the model on the same GPU
    # during HookedTransformer.from_pretrained's own weight-conversion
    # clones (fold_value_biases etc.), peaking at 79.09/79.18 GiB. The
    # caller moves hf_model to a SEPARATE GPU immediately before the
    # equivalence forward pass instead (see _secondary_cuda_device) --
    # conversion here never sees a second GPU-resident copy at all.
    hf_model = AutoModel.from_pretrained(str(model_path), dtype=torch_dtype)
    model = HookedTransformer.from_pretrained(
        MODEL_ID,  # config/conversion routing only; hf_model= means no network use
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
    sae = SAE.from_pretrained(release=SAE_RELEASE, sae_id=SAE_ID, device=device)
    sae = sae.to(dtype=torch.float32)
    sae.eval()

    model_d_model = model.cfg.d_model
    if model_d_model != sae.cfg.d_in:
        raise RuntimeError(
            f"d_model mismatch: model reports d_model={model_d_model}, SAE reports "
            f"d_in={sae.cfg.d_in}. This is the escalate-to-PM condition from D1.3 -- stop "
            "here, do not proceed with a mismatched hook."
        )

    return model, sae, hf_model


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


# D2.1 fix A (highest priority in the sprint): incremental, resumable
# writes. 1736 records at a deliberately generous 24h wall time means a
# death at hour 23 -- timeout, node failure, preemption -- must not lose
# everything. Output is one growing JSONL file, appended to and fsync'd
# after every record, not one file per record: on restart, the harness
# reads whatever lines already parsed successfully and skips those cells,
# rather than regenerating the whole matrix. This supersedes the original
# "one JSON per run" per-file framing -- a deliberate, disclosed
# consequence of adding resumability, not scope creep.
RECORDS_FILENAME = "records.jsonl"

_CELL_KEY_FIELDS = ("feature_idx", "mode", "arm", "dose_multiple", "prompt_id")


def _cell_key(record: dict[str, Any]) -> tuple:
    return tuple(record[k] for k in _CELL_KEY_FIELDS)


def load_completed_keys(records_path: Path) -> set[tuple]:
    """Reads whatever already exists in the JSONL log and returns the set
    of cell keys already completed. A partially-written last line (the
    exact shape a hard kill mid-write leaves behind) fails json.loads and
    is silently skipped -- it was never fsync'd as complete, so it is
    correctly treated as not-yet-done and will be regenerated."""
    completed: set[tuple] = set()
    if not records_path.exists():
        return completed
    with records_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            completed.add(tuple(rec.get(k) for k in _CELL_KEY_FIELDS))
    return completed


def append_record(records_path: Path, payload: dict[str, Any]) -> None:
    """Append one record and fsync before returning. fsync cost is
    negligible next to a multi-second generation call, so this runs after
    every record, not on a periodic batch -- a batch interval is itself a
    window in which a kill loses everything since the last flush.

    If the file's last byte is not a newline (exactly what a kill mid-write
    leaves behind), a leading newline is written first. Without this, the
    next append glues onto the end of the corrupted partial line instead of
    starting its own line, corrupting the new record too -- caught by
    deliberately reproducing a mid-write kill and inspecting the resulting
    file byte-for-byte, not assumed correct."""
    needs_leading_newline = False
    if records_path.exists() and records_path.stat().st_size > 0:
        with records_path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_leading_newline = f.read(1) != b"\n"

    with records_path.open("a", encoding="utf-8") as f:
        if needs_leading_newline:
            f.write("\n")
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


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

# Declared BEFORE any equivalence number is seen, per the review. Near-
# exact agreement is expected, but not bit-exact: bf16 rounding and
# SDPA-vs-eager attention kernel differences are legitimate sources of
# small cross-implementation noise, not evidence of a module-identity
# failure. These two thresholds are the full passing bar; nothing here is
# adjusted after seeing a number.
EQUIVALENCE_COSINE_MIN = 0.999
EQUIVALENCE_REL_L2_MAX = 1e-2


class EquivalenceToleranceFailure(RuntimeError):
    """Raised ONLY when a real cosine/rel_l2 number falls outside the
    tolerances declared above. Every other failure in
    verify_raw_hf_equivalence (OOM, device mismatch, malformed
    hidden_states, any exception not raised by this class) is left as a
    plain exception, so the caller can tell a science problem (this type)
    apart from an infrastructural one (everything else) by exception type
    alone -- not by whoever is reading the log deciding which case they
    think it is."""


def _gpu_memory_snapshot(device: str) -> dict[str, Any] | None:
    """None on a non-CUDA device -- dry runs never reach this, but a real
    run on CPU should not crash trying to query CUDA stats. Reports
    allocated/reserved bytes so headroom around hf_model's ~24GB is known
    at the gate and after it is freed, not assumed."""
    import torch

    if not (isinstance(device, str) and device.startswith("cuda")) or not torch.cuda.is_available():
        return None
    return {
        "allocated_bytes": torch.cuda.memory_allocated(device),
        "max_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "reserved_bytes": torch.cuda.memory_reserved(device),
    }


def _secondary_cuda_device(primary_device: str) -> str | None:
    """The equivalence check's raw-HF forward pass runs on a SEPARATE GPU
    from the sweep's own model/SAE/generation (which occupy primary_device
    for the next ~24h), so the two ~24GB bf16 copies never contend for the
    same device's memory. This is the second half of the job 398885 OOM
    fix -- loading hf_model on CPU (see load_model_and_sae) removed the
    conversion-time peak; this removes the equivalence-time one. Returns
    None on a non-CUDA primary device or when fewer than 2 GPUs are
    visible -- the caller then leaves hf_model on CPU rather than
    guessing at a device that doesn't exist (the equivalence forward pass
    still runs, just slower)."""
    import torch

    if not (isinstance(primary_device, str) and primary_device.startswith("cuda")):
        return None
    if not torch.cuda.is_available() or torch.cuda.device_count() < 2:
        return None
    return "cuda:1"


def verify_module_identity(model, sae) -> dict[str, Any]:
    """Run once, immediately after load, before any generation. Resolves
    the fully-qualified module path the hook attaches to, confirms the
    hooked tensor's last dim is 3840 (the text-tower width -- the exact
    reason d_model=3840 was the D1.3 decisive check), and confirms
    n_layers==48 / d_model==3840 on the loaded config.

    model is a transformer_lens.HookedTransformer (see load_model_and_sae
    -- TransformerBridge was abandoned for this architecture); hook_dict is
    HookedTransformer's own registry of every HookPoint by name, populated
    in setup(), and is the direct replacement for the bridge-specific
    get_hook_point() this gate used before the loader port."""
    hook_name = sae.cfg.metadata.hook_name
    hook_point = model.hook_dict.get(hook_name)
    if hook_point is None:
        raise RuntimeError(
            f"module-identity gate FAILED: {hook_name!r} does not resolve to any hook "
            f"point on this model. Stop and escalate -- do not adapt the hook name."
        )

    module_path = None
    for name, module in model.named_modules():
        if module is hook_point:
            module_path = name
            break
    if module_path is None:
        raise RuntimeError(
            f"module-identity gate FAILED: {hook_name!r} resolved to a HookPoint that is "
            f"not reachable via model.named_modules() -- cannot establish its "
            f"fully-qualified path. Stop and escalate."
        )

    suspicious_tokens = ("vision", "vit", "image", "siglip", "clip")
    if any(tok in module_path.lower() for tok in suspicious_tokens):
        raise RuntimeError(
            f"module-identity gate FAILED: hook path {module_path!r} looks like it belongs "
            f"to the vision stack, not the text tower. Stop and escalate."
        )

    n_layers = model.cfg.n_layers
    d_model = model.cfg.d_model
    if n_layers != N_LAYERS:
        raise RuntimeError(
            f"module-identity gate FAILED: model.cfg.n_layers={n_layers}, expected "
            f"{N_LAYERS}. Stop and escalate."
        )
    if d_model != 3840:
        raise RuntimeError(
            f"module-identity gate FAILED: model.cfg.d_model={d_model}, expected 3840 "
            f"(the D1.3 decisive check: the SAE's own w_enc shape fixes d_in=3840, and the "
            f"text-decoder hidden size must equal it). Stop and escalate."
        )

    captured: dict[str, Any] = {}

    def _capture_hook(tensor, hook):
        captured["tensor"] = tensor
        return tensor

    with model.hooks(fwd_hooks=[(hook_name, _capture_hook)]):
        tokens = model.to_tokens("The quick brown fox jumps over the lazy dog.")
        model(tokens)

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


def verify_raw_hf_equivalence(model, hf_model, prompt: str, seed: int) -> dict[str, Any]:
    """Same prompt, same seed, both paths: the HookedTransformer's hooked
    blocks.{LAYER}.hook_resid_post capture vs. the underlying raw HF
    model's own hidden_states at the same layer. hf_model is the exact
    object returned by load_model_and_sae -- the same weights object that
    powered the HookedTransformer.from_pretrained(hf_model=...) conversion,
    not a second, possibly-diverged load. Tolerances are declared at
    module scope (EQUIVALENCE_COSINE_MIN, EQUIVALENCE_REL_L2_MAX), above,
    before this function is ever called with a real number.

    model and hf_model may be on DIFFERENT CUDA devices (job 398885's OOM
    fix moves hf_model to a second GPU precisely so the two ~24GB copies
    never contend for the same device's memory) -- tokens are moved to
    hf_model.device for its forward pass, and both captured tensors are
    moved to CPU before the actual comparison. Never compare across
    devices directly; that would either error or silently misbehave
    depending on the backend, neither of which is a real number.
    """
    import torch

    torch.manual_seed(seed)
    tokens = model.to_tokens(prompt)

    captured: dict[str, Any] = {}

    def _capture_hook(tensor, hook):
        captured["tensor"] = tensor.detach().clone()
        return tensor

    hook_name = f"blocks.{LAYER}.hook_resid_post"
    with model.hooks(fwd_hooks=[(hook_name, _capture_hook)]):
        model(tokens)
    model_tensor = captured["tensor"]

    with torch.no_grad():
        hf_out = hf_model(tokens.to(hf_model.device), output_hidden_states=True)
    hidden_states = hf_out.hidden_states
    if len(hidden_states) != N_LAYERS + 1:
        raise RuntimeError(
            f"equivalence check FAILED: raw HF model returned {len(hidden_states)} "
            f"hidden_states entries, expected {N_LAYERS + 1} (embeddings + one per layer) "
            f"-- cannot safely index layer {LAYER}'s post-block state. Stop and escalate."
        )
    raw_hf_tensor = hidden_states[LAYER + 1].to(model_tensor.dtype)

    # Both to CPU before comparing -- model_tensor and raw_hf_tensor may
    # be on different CUDA devices (see docstring); comparing across
    # devices directly is not a real number.
    model_flat = model_tensor.reshape(-1).float().cpu()
    raw_flat = raw_hf_tensor.reshape(-1).float().cpu()
    if model_flat.shape != raw_flat.shape:
        raise RuntimeError(
            f"equivalence check FAILED: shape mismatch model={tuple(model_tensor.shape)} "
            f"vs raw_hf={tuple(raw_hf_tensor.shape)}. Stop and escalate."
        )

    cosine_sim = torch.nn.functional.cosine_similarity(model_flat, raw_flat, dim=0).item()
    rel_l2 = ((model_flat - raw_flat).norm() / raw_flat.norm()).item()
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
        raise EquivalenceToleranceFailure(
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
    p.add_argument(
        "--restart", action="store_true",
        help="Discard any existing records.jsonl in --out-dir and regenerate the full matrix "
        "from scratch. Default behavior (no flag) is to resume: read what already completed "
        "and skip those cells.",
    )
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

    model = sae = hf_model = None
    if not args.dry_run:
        model, sae, hf_model = load_model_and_sae(
            args.model_path, args.sae_path, device=args.device, dtype=args.dtype
        )

        # Hard gate, BEFORE anything else touches the fan-out (D2.1 fix 4).
        # module-identity is load-bearing and always stop-and-escalate on
        # failure. raw-HF equivalence is a stronger nice-to-have that
        # needs a second ~24GB copy of the model resident -- an
        # infrastructural failure there (OOM, device error, anything that
        # is not a tolerance number) is pre-authorized to fall back to
        # module-identity alone; a real tolerance failure is not.
        identity_report = verify_module_identity(model, sae)

        # hf_model came back on CPU from load_model_and_sae (job 398885's
        # OOM fix, part 1). Relocate it to a second GPU only for this
        # brief forward pass (part 2) -- never onto args.device, which is
        # about to hold generation activations for the next ~24h.
        equivalence_device = _secondary_cuda_device(args.device)
        if equivalence_device is not None:
            hf_model = hf_model.to(equivalence_device)
        print(f"raw-HF equivalence check running hf_model on: {equivalence_device or 'cpu'}")

        try:
            equivalence_report = verify_raw_hf_equivalence(
                model, hf_model, prompts[0], seed=derive_seed("module-identity-check")
            )
        except EquivalenceToleranceFailure:
            # A real cosine/rel_l2 number outside the declared bar -- a
            # science problem, not an infrastructure hiccup. No fallback
            # applies here: verify_raw_hf_equivalence already printed the
            # failing numbers before raising. Do not relax the declared
            # tolerance after seeing this.
            print(f"GPU memory at gate (failing run): {_gpu_memory_snapshot(args.device)}")
            raise
        except Exception as exc:
            # Everything else -- OOM, device mismatch, malformed output.
            # module-identity already passed above and is what protects
            # the science (d_model, n_layers, hooked module path, hooked
            # tensor shape). Recorded as explicitly NOT RUN, never as
            # passed and never silently omitted, and the sweep proceeds.
            equivalence_report = {"not_run": True, "reason": f"{type(exc).__name__}: {exc}"}
            print(
                f"raw-HF equivalence check NOT RUN (infrastructural failure, proceeding on "
                f"module-identity alone): {type(exc).__name__}: {exc}"
            )

        gpu_mem_at_gate = _gpu_memory_snapshot(args.device)
        print(f"GPU memory at gate: {gpu_mem_at_gate}")

        # hf_model is dead weight for the next 24h of generation once the
        # gate is done with it: TransformerLens converts and copies rather
        # than aliasing the text tower, so the HookedTransformer holds its
        # own ~24GB copy independent of hf_model -- both resident at once
        # peaks around 50GB on an 80GB H100. Freeing this is required, not
        # an optimisation: an OOM at record 1400 is the worst possible
        # time to discover hf_model was still resident.
        del hf_model
        import torch

        torch.cuda.empty_cache()
        gpu_mem_after_free = _gpu_memory_snapshot(args.device)
        print(f"GPU memory after hf_model free: {gpu_mem_after_free}")

        (out_dir / "module_identity_report.json").write_text(
            json.dumps(
                {
                    "module_identity": identity_report,
                    "raw_hf_equivalence": equivalence_report,
                    "gpu_memory_at_gate": gpu_mem_at_gate,
                    "gpu_memory_after_hf_model_free": gpu_mem_after_free,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    records_path = out_dir / RECORDS_FILENAME
    if args.restart and records_path.exists():
        records_path.unlink()
    completed_keys = load_completed_keys(records_path)
    if completed_keys:
        print(f"resume: {records_path} has {len(completed_keys)} completed cell(s) already -- skipping those")

    n_skipped = 0
    n_written = 0
    for record in matrix:
        if _cell_key(record) in completed_keys:
            n_skipped += 1
            continue

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

        append_record(records_path, payload)
        n_written += 1

    print(f"wrote {n_written} record(s), skipped {n_skipped} already-complete cell(s) -> {records_path}")
    if args.dry_run:
        print("--dry-run: no model/SAE was loaded, no text was generated (stub records only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
