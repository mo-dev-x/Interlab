"""D2.1-necessity -- judge-free representational-necessity measurement,
substituting for the generation-based ablation arm's structural low power
on generic prompts.

PRE-REGISTERED: reports/necessity_substitution_prereg_v1.md (sha256
dbf1029e804655f032a6f831f3d4b766fefc14b75aa1f26ee89dad790e1ebbf2, 6282
bytes), authored before any measurement exists. That document is binding;
this docstring summarizes it, but the file is the source of truth --
re-hash it before trusting a summary that may have drifted.

WHY A SEPARATE FILE: scripts/legacy/gemma3_sweep.py stays FROZEN. This
script does not import from it in a way that would require editing it, so
the sweep can run in parallel and unfreezing risk stays at zero. Per this
project's Ground Rule 2 ("duplicate rather than cross-import" -- see
jobs/steer.py), small stable primitives (feature table, seed derivation,
git provenance, JSONL resume machinery, checkpoint hashing) are duplicated
here rather than imported. The module-identity gate
(verify_module_identity / verify_raw_hf_equivalence) is loaded dynamically
from gemma3_sweep.py instead, per this task's explicit invitation to
"import and reuse the one you already wrote" -- re-deriving 100+ lines of
already-validated TransformerBridge introspection would itself be a
correctness risk, and a read-only import does not touch the frozen file.

TWO BUGS FOUND IN THE SWEEP WHILE BUILDING THIS, BOTH NOW FIXED THERE AND
RE-PORTED HERE (2026-08-08):
  1. gemma3_sweep.py's original load_sae_from_local_snapshot() built
     cfg_dict with a flat top-level "hook_name" key and called
     SAE.from_dict(cfg_dict) directly. SAEConfig.from_dict filters cfg_dict
     down to SAEConfig's own dataclass fields -- "hook_name" is not one of
     them, so it was silently dropped and sae.cfg.metadata.hook_name came
     back None. This script's own load_sae_from_local_snapshot() (below)
     was written with the fix already applied (calls the public
     handle_config_defaulting(), the same function the sae_lens hub path
     itself calls) and never inherited the bug -- retained, though unused
     now that the SAE is loaded via SAE.from_pretrained() (see bug 2).
  2. gemma3_sweep.py's loader used TransformerBridge.boot_transformers,
     which dies during set_original_components on this transformers
     version's Gemma3+Siglip combination (AttributeError: SiglipVisionModel
     has no attribute vision_model -- zero Gemma-3/Siglip component
     mappings in the installed package). Fixed in the sweep by porting
     Engineer 1's proven job-398619 loader: classic
     HookedTransformer.from_pretrained(hf_model=...), which uses
     transformer_lens's own Gemma weight converter and skips the vision
     tower automatically. THIS SCRIPT DUPLICATED THE SWEEP'S LOADER BEFORE
     THAT PORT (Ground Rule 2 means the fix does not propagate by itself)
     and job 399600 died on the identical AttributeError at the identical
     stack depth. load_model_and_sae() below is now re-ported to match,
     by hand, verbatim -- see its docstring. The two loaders (here and in
     gemma3_sweep.py) must be kept in sync by hand going forward; nothing
     enforces that automatically, per Ground Rule 2's deliberate tradeoff.

DESIGN (pre-registration section 3-8):
  For each of 9 features F, take F's own top-16 activating snippets (an
  input file -- compute nodes are offline, this never fetches from
  Neuronpedia). For each snippet: one unhooked forward pass, one with F
  clamped to 0.0 (ablate) via interplab.interventions.hooks.attach() (the
  public wrapper around the private _make_clamp_hook this project already
  uses -- the leading underscore marks it as not meant for external
  import, so attach() is reused instead, same as gemma3_sweep.py does).
  Two controls, both required (section 4):
    - CROSS-FEATURE: the single shared random-feature control (same
      construction as the sweep's) ablated on the SAME snippet as F --
      answers "is the effect specific to F?"
    - WITHIN-FEATURE: F itself ablated on text where F does NOT fire --
      answers "does the effect track where F is active, or is it a global
      perturbation?" Candidate non-firing text is drawn from a different
      feature's top-16 pool (cyclic pairing, WITHIN_FEATURE_CONTROL_OFFSET)
      and VERIFIED non-firing via an SAE encode before use, never assumed
      from which pool it came from.
  Field names carry the "on max-activating text" / "on non-firing text"
  qualifier explicitly (section 5) -- never a bare "mean_delta_nll".
  Every record carries CONSTRUCT_NOTE (section 6: this measures
  representational necessity; the sweep's steering arm measures
  behavioural sufficiency; related but not a matched pair) and
  FALSIFICATION_CONDITIONS (section 8) verbatim, so a downstream reader
  never has to infer them or go find this file.

ADDED 2026-08-08, after analyzing job 399619's real data: every
cross-feature and within-feature value came back bit-exact 0.0 -- both
ablate a feature already inactive everywhere on the text, and the ablate
hook's subtraction of activation*direction is an exact no-op on an
already-zero activation. Both are real INSTRUMENT SPECIFICITY CHECKS (the
hook only touches the intended feature/positions) but neither is a
scientific control -- a check that cannot fail is not a control, and
prereg section 8's two conditions collapse to testing the same thing here
for the same reason. See INSTRUMENT_SPECIFICITY_NOTE. A third,
falsifiable comparator is added on own-text cells only:
active_nontarget_control ablates a feature sampled uniformly at random,
per snippet, from non-target features matched in activation STRENGTH to
the target on that same snippet (not a fixed feature, and NOT the single
highest-activating one -- two prior selection mechanisms tried exactly
that and both were degenerate on real data, see
pick_matched_strength_active_nontarget and ACTIVE_NONTARGET_CONTROL_NOTE),
so the target's delta-NLL has an actual "cost of removing some arbitrary
active direction" to be judged against. Old real records (job 399619,
committed at 15704da) predate this field and must be regenerated with
--restart -- resume-by-cell-key would otherwise skip them and leave the
new fields permanently absent from those rows.

CONSTRAINTS, unchanged from the sweep: HF_HUB_OFFLINE=1 with local paths
as required arguments, never a repo_id; module purge && module load
StdEnv/2023 python/3.11 arrow/25.0.0 then source ~/sprint-venv/bin/activate
(arrow before activate); unset HF_TOKEN after activate; payload script, no
--wrap; runtime-derived git SHA + dirty flag; incremental resumable JSONL
writes, same pattern already proven (and the same append-must-check-for-
a-missing-trailing-newline fix, duplicated here for the same reason).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_PATH = REPO_ROOT / "reports" / "necessity_substitution_prereg_v1.md"
PREREG_SHA256 = "dbf1029e804655f032a6f831f3d4b766fefc14b75aa1f26ee89dad790e1ebbf2"

# ---------------------------------------------------------------------------
# Dynamically load gemma3_sweep.py's module-identity gate. Read-only import
# by file path (not a package import) -- does not require scripts/legacy
# to be a package, does not touch the frozen file, and does not require
# interplab to already be importable: neither verify_module_identity nor
# verify_raw_hf_equivalence imports interplab (checked -- they only use
# bridge/sae methods and torch).
# ---------------------------------------------------------------------------

def _load_sweep_module():
    sweep_path = Path(__file__).resolve().parent / "gemma3_sweep.py"
    spec = importlib.util.spec_from_file_location("gemma3_sweep", sweep_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Duplicated small primitives (Ground Rule 2). Same values as
# gemma3_sweep.py by construction -- both describe the same fixed
# instrument (layer-31 Gemma Scope 2 SAE on gemma-3-12b-pt).
# ---------------------------------------------------------------------------

MAX_ACT_APPROX_CAVEAT = (
    "maxActApprox is a sample-max proxy over Neuronpedia's activation set, not a corpus max."
)

SAE_ID = "layer_31_width_16k_l0_medium"
SAE_RELEASE = "gemma-scope-2-12b-pt-res"
SAE_REPO_ID = "google/gemma-scope-2-12b-pt"
SAE_REPO_REVISION = "bbabd1e4a3964914f5bf0f5f99b56c2a2da09802"
MODEL_ID = "google/gemma-3-12b-pt"
LAYER = 31
N_LAYERS = 48
WIDTH = 16384
DEPTH_FRACTION = LAYER / N_LAYERS

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
REJECTED_FEATURE_IDXS = frozenset({12345, 7777, 6000, 100, 10500, 13500, 9600, 7000, 400, 14000})

TOP_N_SNIPPETS = 16

# Cyclic pairing for the within-feature control's candidate non-firing text:
# feature at FEATURES[i] draws candidates from FEATURES[(i+1) % len(FEATURES)]'s
# own top-16 pool. Fixed and deterministic, not re-drawn per run. Candidates
# are still VERIFIED non-firing via an SAE encode before use -- this pairing
# only decides where to look, never substitutes for the check.
WITHIN_FEATURE_CONTROL_OFFSET = 1

# Pre-registration section 6, carried verbatim on every record so a
# downstream reader joining this file with the sweep's cannot assume they
# are commensurable without being told.
CONSTRUCT_NOTE = (
    "Necessity (this file, delta-NLL under ablation) is REPRESENTATIONAL: the feature "
    "carries information the model uses. The sweep's steering arm measures BEHAVIOURAL "
    "sufficiency (judged generation). Related but different constructs, not a matched "
    "pair -- this half is the more robust one, being judge-free and therefore immune to "
    "the measured 3.7x concept-string judge swing the sufficiency half inherits."
)

# Pre-registration section 8, carried verbatim.
FALSIFICATION_CONDITIONS = {
    "cross_feature": (
        "If F's delta-NLL on F's own top-activating text is not meaningfully above the "
        "cross-feature control's, the effect is a property of the text, not of F."
    ),
    "within_feature": (
        "If F's delta-NLL on F's own top-activating text is not meaningfully above the "
        "within-feature control's (F ablated on text where F does not fire), the effect "
        "is a global perturbation, not activity-tracking."
    ),
    "note": "Either outcome is reported as the finding. Neither is grounds for changing the instrument again.",
}

# Added 2026-08-08 after the first real run (job 399619) showed every
# cross-feature and within-feature value at bit-exact 0.0: both ablate a
# feature verified/constructed to already be inactive everywhere on the
# text, and attach()'s ablate hook is a single-direction subtraction, so
# `x - 0*direction = x` is an exact floating-point no-op. Both were
# GUARANTEED to read 0.0 before the job ran -- they check that the hook
# only touches the intended feature/positions (a real, valuable
# INSTRUMENT SPECIFICITY CHECK), but neither is a scientific control: a
# check that cannot fail is not a control, and prereg section 8's two
# falsification conditions collapse to testing the identical thing here
# (delta-NLL vs. zero) for the identical mechanistic reason. This does not
# retroactively rename cross_feature_control_idx / the two "..._control_"
# field names already written into committed real data -- see
# necessity_result_v1.md for the reframing in prose.
INSTRUMENT_SPECIFICITY_NOTE = (
    "The cross-feature and within-feature checks both ablate a feature already inactive "
    "(verified or constructed) everywhere on the text being ablated; attach()'s ablate hook "
    "subtracts activation*direction, so ablating an already-zero activation is an exact "
    "floating-point no-op and both were guaranteed to read 0.0 before this job ran. They "
    "confirm the hook is surgical (touches only the intended feature, at only the intended "
    "positions) -- a real instrument specificity check -- but neither is a scientific "
    "control, and prereg section 8's two falsification conditions collapse to one test here "
    "for the same mechanistic reason."
)

# The falsifiable comparator prereg section 8 actually needs: how much
# does removing an ARBITRARY ACTIVE direction cost, on this same snippet,
# versus removing the target? TWO prior selection mechanisms were both
# determined before any weight loaded and both failed on real data: raw
# argmax over the full sequence selected the <bos> attention-sink feature
# every time (job 400287); excluding <bos> alone still selected for a
# feature's intrinsic activation SCALE rather than its relevance, so one
# large-typical-magnitude feature won on 142/144 real records regardless
# of target or content. Matched-strength random selection (see
# pick_matched_strength_active_nontarget) fixes both: sample UNIFORMLY AT
# RANDOM, seeded per record, from non-target features whose own max
# activation (excluding <bos>) on this snippet is within a pre-declared
# fraction of the target's own max on the SAME snippet -- matching the
# strength variable the checks above are NOT testing, varying the
# identity variable that is. If no feature qualifies, the cell is marked
# ineligible and skipped, never falling back to argmax.
ACTIVE_NONTARGET_CONTROL_NOTE = (
    "active_nontarget_control ablates a feature sampled uniformly at random (seeded per "
    "record) from non-target features whose own max activation on this same snippet "
    "(excluding the <bos> position) is within a pre-declared fraction of the target's own "
    "max activation on the same snippet -- reproducible from (active_nontarget_control_rng_seed, "
    "active_nontarget_control_idx) alone, never hand-chosen -- unlike cross_feature_control's "
    "single fixed feature shared across all snippets. This matches the comparator on activation "
    "strength (not under test) and varies it on feature identity (under test), which is what "
    "'an arbitrary active direction' requires; the raw most-active feature is the extreme of the "
    "activation distribution, not a draw from it, and is not used here. If no feature qualifies, "
    "the cell is recorded as ineligible and the ablation is skipped -- never a fallback to "
    "argmax. This is the comparator with the capacity to fail: it measures the cost of removing "
    "an arbitrary active direction on the same text, so the target's delta-NLL has a scale to be "
    "judged against."
)

DEFAULT_OUT_DIR = REPO_ROOT / "results" / "gemma3_necessity"
RECORDS_FILENAME = "necessity_records.jsonl"


# ---------------------------------------------------------------------------
# Snippets: an input file, never fetched (compute nodes are offline).
# ---------------------------------------------------------------------------

def _stub_snippets(features: list[dict[str, Any]]) -> dict[int, list[str]]:
    return {
        f["idx"]: [f"[STUB SNIPPET {i} for feature {f['idx']} -- dry-run placeholder, no real text]" for i in range(TOP_N_SNIPPETS)]
        for f in features
    }


def load_snippets(snippets_file: str | None, features: list[dict[str, Any]], *, dry_run: bool) -> tuple[dict[int, list[str]], bool]:
    """Returns (snippets_by_feature_idx, is_stub). Real schema: a JSON
    object mapping the string form of each feature idx to a list of up to
    TOP_N_SNIPPETS strings, e.g. {"250": ["...", ...], "500": [...]}."""
    if snippets_file is not None and Path(snippets_file).exists():
        data = json.loads(Path(snippets_file).read_text(encoding="utf-8"))
        snippets: dict[int, list[str]] = {}
        for f in features:
            key = str(f["idx"])
            if key not in data:
                raise ValueError(
                    f"{snippets_file} is missing an entry for feature {f['idx']} -- "
                    f"every one of the 9 features needs its own top-{TOP_N_SNIPPETS} snippets"
                )
            snippets[f["idx"]] = list(data[key])[:TOP_N_SNIPPETS]
        return snippets, False

    if not dry_run:
        raise FileNotFoundError(
            f"--snippets-file {snippets_file!r} not found. This is a required local input file "
            "(compute nodes are offline; snippets are never fetched from Neuronpedia here). "
            "Only --dry-run tolerates a missing file, using clearly-labeled stub text instead."
        )
    return _stub_snippets(features), True


# ---------------------------------------------------------------------------
# Offline loading, duplicated from gemma3_sweep.py per Ground Rule 2 (kept
# in sync by hand, not by import -- see module docstring, bug 2).
# ---------------------------------------------------------------------------

def _fail_if_missing(path: Path, *, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{what} not found at {path!r}. This harness only accepts pre-staged local "
            f"filesystem paths -- it will not fall back to a network fetch."
        )


# No longer called from load_model_and_sae() (the SAE is now loaded via
# SAE.from_pretrained() below, matching the sweep's re-ported loader) --
# retained because handle_config_defaulting() is a real, verified fix and
# costs nothing to keep even if this path goes unused.
def load_sae_from_local_snapshot(sae_path: Path, *, device: str = "cpu", dtype: str = "float32"):
    """Reads the raw Gemma-Scope-2 safetensors format directly and calls
    the public sae_lens.loading.pretrained_sae_loaders.handle_config_defaulting()
    before SAE.from_dict() -- the step gemma3_sweep.py's ORIGINAL local-path
    loader omitted (see module docstring bug 1), which is exactly why
    sae.cfg.metadata.hook_name came back None there. This is the same
    function the sae_lens hub-based loading path itself calls
    (from_pretrained_with_cfg_and_sparsity), not a reimplementation."""
    import re

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
    assert sae.cfg.metadata.hook_name == hook_name, (
        f"hook_name propagation failed even after handle_config_defaulting: "
        f"got {sae.cfg.metadata.hook_name!r}, expected {hook_name!r}"
    )
    return sae


def _patch_gemma3_safetensors_shape_lookup() -> None:
    """Duplicated verbatim from gemma3_sweep.py (Ground Rule 2). Installed
    sae_lens's Gemma-3 loader issues a raw requests.get() HTTP range read
    for tensor shapes that bypasses huggingface_hub AND HF_HUB_OFFLINE
    entirely -- an immediate hang-then-fail on a compute node with no
    outbound internet. Routes the same shape lookup through
    hf_hub_download instead, which respects HF_HUB_OFFLINE and the local
    cache like everything else in this file."""
    import sae_lens.loading.pretrained_sae_loaders as psl
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    def _local_get_safetensors_tensor_shapes(repo_id: str, filename: str) -> dict:
        local_path = hf_hub_download(repo_id=repo_id, filename=filename)
        with safe_open(local_path, framework="pt") as f:
            return {k: list(f.get_slice(k).get_shape()) for k in f.keys()}

    psl.get_safetensors_tensor_shapes = _local_get_safetensors_tensor_shapes


def load_model_and_sae(model_path: str | Path, sae_path: str | Path, *, device: str = "cuda", dtype: str = "bfloat16"):
    """Re-ported from gemma3_sweep.py's fixed loader (Ground Rule 2 --
    duplicated by hand, not imported; see module docstring bug 2 for why
    this file's own prior copy died on job 399600). Returns
    (model, sae, hf_model): hf_model comes back on CPU, not device -- the
    caller relocates it to a second GPU only if/while the equivalence
    check needs it, then frees it (this script has no 24h generation loop
    after the gate, so freeing early costs nothing either way)."""
    import torch
    from sae_lens import SAE
    from transformer_lens import HookedTransformer
    from transformers import AutoModel, AutoTokenizer

    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError(
            "HF_HUB_OFFLINE=1 is not set in the environment. Refusing to proceed rather than "
            "risk a silent network fetch on a compute node with no outbound internet."
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
    # Left on CPU deliberately (mirrors gemma3_sweep.py's job-398885 OOM
    # fix): moving hf_model to device here would put two ~24GB bf16
    # copies of the model on the same GPU during
    # HookedTransformer.from_pretrained's own weight-conversion clones.
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

    if model.cfg.d_model != sae.cfg.d_in:
        raise RuntimeError(
            f"d_model mismatch: model reports d_model={model.cfg.d_model}, SAE reports "
            f"d_in={sae.cfg.d_in}. Stop here, do not proceed with a mismatched hook."
        )
    return model, sae, hf_model


# ---------------------------------------------------------------------------
# Provenance + resumable JSONL (duplicated from gemma3_sweep.py, Ground Rule 2)
# ---------------------------------------------------------------------------

def harness_git_provenance() -> dict[str, Any]:
    try:
        sha_out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10)
        status_out = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True, timeout=10)
        return {"sha": sha_out.stdout.strip(), "dirty": bool(status_out.stdout.strip())}
    except Exception as exc:
        return {"sha": f"unknown (git rev-parse failed: {exc})", "dirty": None}


def derive_seed(*parts: Any) -> int:
    key = "\0".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**31 - 1)


def pick_control_feature_idx(*, exclude: set[int], control_rng_seed: int, d_sae: int = WIDTH) -> int:
    import numpy as np

    rng = np.random.default_rng(control_rng_seed)
    while True:
        candidate = int(rng.integers(0, d_sae))
        if candidate not in exclude:
            return candidate


_CELL_KEY_FIELDS = ("cell_type", "feature_idx", "source_feature_idx", "source_snippet_index")


def _cell_key(record: dict[str, Any]) -> tuple:
    return tuple(record.get(k) for k in _CELL_KEY_FIELDS)


def load_completed_keys(records_path: Path) -> set[tuple]:
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


def compute_checkpoint_hash(model_path: str, sae_path: str, *, dry_run: bool) -> tuple[str, str]:
    if dry_run:
        digest = hashlib.sha256(f"{model_path}\0{sae_path}".encode("utf-8")).hexdigest()
        return f"sha256:{digest}", "path-strings-only (dry-run, files not required to exist)"

    from interplab.core import hashing

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
    return f"sha256:{digest}", "model config.json + SAE config.json + SAE params.safetensors content hashes"


# ---------------------------------------------------------------------------
# Measurement (requires a loaded model + SAE -- never called in --dry-run)
# ---------------------------------------------------------------------------

def _baseline_pass(model, sae, snippet: str, seed: int):
    """One unhooked forward pass + SAE encode. Returns (tokens, nll_per_token
    [shape seq_len-1], feat_acts [shape 1, seq_len, d_sae])."""
    import torch

    tokens = model.to_tokens(snippet)
    hook_name = sae.cfg.metadata.hook_name
    captured: dict[str, Any] = {}

    def _capture(t, hook):
        captured["resid"] = t.detach().clone()
        return t

    torch.manual_seed(seed)
    with torch.no_grad():
        with model.hooks(fwd_hooks=[(hook_name, _capture)]):
            logits = model(tokens)
        feat_acts = sae.encode(captured["resid"].to(torch.float32))
    nll = model.loss_fn(logits, tokens, per_token=True)
    return tokens, nll, feat_acts


def _ablated_pass_nll(model, sae, tokens, feature_idx: int, seed: int, checkpoint_hash: str):
    """One forward pass with `feature_idx` clamped to 0.0 via attach() (the
    public wrapper around _make_clamp_hook). Returns nll_per_token."""
    import torch

    from interplab.interventions.hooks import attach
    from interplab.interventions.spec import InterventionSpec

    spec = InterventionSpec(
        kind="ablate", feature_index=feature_idx, value_in_max_units=None, corpus_max=None,
        positions="all", checkpoint_hash=checkpoint_hash, direction_seed=None,
    )
    torch.manual_seed(seed)
    with torch.no_grad():
        with attach(model, sae, spec, prompt_lengths=None):
            logits = model(tokens)
    return model.loss_fn(logits, tokens, per_token=True)


# Declared BEFORE any run against real data, per instruction -- neither
# threshold is adjusted after seeing a distribution.
#
# STRENGTH_FRACTION: an eligible non-target feature's own max activation
# (excluding <bos>) must be at least this fraction of the target's own
# max activation on the SAME snippet, and genuinely active (> 0). This
# matches the control on the variable not under test (activation
# strength) and varies it on the variable under test (feature identity) --
# what "an arbitrary active direction" literally requires. 0.5 is
# proposed as "same order of magnitude as the target," loose enough that
# most snippets have a non-empty eligible set, tight enough to exclude
# the long tail of near-zero-activation features an unconstrained draw
# would mostly land on.
ACTIVE_NONTARGET_STRENGTH_FRACTION = 0.5

# MAX_SHARE: no single feature index may account for more than this share
# of a real selection sample, or the diversity gate raises. This REPLACES
# a cardinality check (len(set(idx)) > 1), which job 400287's successor
# defect showed is not a diversity check: 142-identical-of-144 selections
# is 2 unique values, satisfying cardinality > 1 while being exactly the
# failure the gate exists to catch. 0.5 -- "no single feature is a
# majority of the sample" -- is declared here, before any real
# distribution exists to fit it to.
ACTIVE_NONTARGET_MAX_SHARE = 0.5


def pick_matched_strength_active_nontarget(feat_acts, target_idx: int, *, strength_fraction: float, rng_seed: int) -> dict[str, Any]:
    """Third fix to this comparator's selection mechanism. First fix
    excluded <bos> (job 400287: an attention-sink position with
    anomalously large activation on a fixed feature regardless of input,
    selected bit-identically on every record). That alone was not
    sufficient: raw-activation argmax over the remaining positions still
    selects for a feature's intrinsic activation SCALE, not its relevance
    to this snippet -- one large-typical-magnitude feature won on
    142/144 real records regardless of target or snippet content, and
    "the most-active feature" is the extreme of the activation
    distribution, not a draw from it, which was never what "an arbitrary
    active direction" meant.

    Matched-strength random selection instead: excludes <bos> (unchanged
    from the prior fix), computes the target's own max activation on this
    snippet, builds the ELIGIBLE set of non-target features whose own max
    activation on this snippet is >= strength_fraction * target_max AND
    genuinely active (> 0), then samples UNIFORMLY AT RANDOM from that
    eligible set -- seeded per record (rng_seed) so the draw is
    reproducible from (rng_seed, chosen index) alone, never hand-chosen.
    If the eligible set is empty, returns eligible=False; the caller
    records that explicitly and skips the ablation for this cell --
    it never falls back to argmax, which is how the second defect
    happened."""
    import numpy as np
    import torch

    acts = feat_acts[0, 1:, :]  # exclude position 0 (<bos> attention sink -- job 400287)
    if acts.shape[0] == 0:
        raise RuntimeError(
            "snippet has no non-BOS positions to select an active-nontarget feature from "
            "-- cannot proceed with a single-token (BOS-only) snippet."
        )
    per_feature_max = acts.max(dim=0).values.clone()
    target_max = float(per_feature_max[target_idx].item())
    per_feature_max[target_idx] = float("-inf")  # exclude the target itself from eligibility

    threshold = strength_fraction * target_max
    eligible_mask = (per_feature_max >= threshold) & (per_feature_max > 0.0)
    eligible_idxs = torch.nonzero(eligible_mask, as_tuple=True)[0]
    n_eligible = int(eligible_idxs.numel())

    result: dict[str, Any] = {
        "target_max_activation": target_max,
        "strength_fraction_declared": strength_fraction,
        "n_eligible": n_eligible,
        "rng_seed": rng_seed,
    }
    if n_eligible == 0:
        result.update({"eligible": False, "chosen_idx": None, "chosen_activation": None, "strength_match_ratio": None})
        return result

    rng = np.random.default_rng(rng_seed)
    chosen_pos = int(rng.integers(0, n_eligible))
    chosen_idx = int(eligible_idxs[chosen_pos].item())
    chosen_activation = float(per_feature_max[chosen_idx].item())
    ratio = (chosen_activation / target_max) if target_max > 0 else None
    result.update({"eligible": True, "chosen_idx": chosen_idx, "chosen_activation": chosen_activation, "strength_match_ratio": ratio})
    return result


def verify_active_nontarget_control_diversity(
    model, sae, own_text_matrix: list[dict[str, Any]], *,
    strength_fraction: float = ACTIVE_NONTARGET_STRENGTH_FRACTION,
    max_share: float = ACTIVE_NONTARGET_MAX_SHARE,
) -> dict[str, Any]:
    """Run once, right after the module-identity/equivalence gates and
    before the main fan-out. REPLACES the prior cardinality check
    (len(set(idx)) > 1) -- that check is satisfied by 142-identical-of-144
    (2 unique values), which is exactly the failure it was written to
    guard against: a cardinality check is not a diversity check. This
    gate instead asserts no single chosen index exceeds max_share of a
    REAL selection sample.

    Runs the actual selection (pick_matched_strength_active_nontarget) on
    EVERY (feature, snippet) pair in own_text_matrix -- the full real
    population this run will measure, not a small subsample -- using
    baseline-pass-only forward passes (no ablation), so this is cheap
    relative to the measurement loop's 3-ablation-passes-per-record cost,
    but the resulting distribution IS the real one, not a proxy for it.
    measure_own_text_cell (below) re-derives the identical selection later
    using the identical seed -- deterministic given the seed, so the real
    run's distribution matches what this gate reports exactly, not
    approximately.

    Binding rule from this task: any gate whose verdict is a boolean must
    also emit the evidence the verdict was computed from. Always returns
    and prints the full chosen-index distribution and the
    eligible/ineligible split, whether it passes or fails."""
    picks: list[dict[str, Any]] = []
    for cell in own_text_matrix:
        target_idx = cell["feature"]["idx"]
        snippet_index = cell["snippet_index"]
        snippet = cell["snippet"]
        baseline_seed = derive_seed("own_text", target_idx, snippet_index)
        selection_seed = derive_seed("active_nontarget_selection", target_idx, snippet_index)
        _, _, feat_acts = _baseline_pass(model, sae, snippet, baseline_seed)
        pick = pick_matched_strength_active_nontarget(
            feat_acts, target_idx, strength_fraction=strength_fraction, rng_seed=selection_seed
        )
        picks.append({"target_feature_idx": target_idx, "snippet_index": snippet_index, **pick})

    eligible_picks = [p for p in picks if p["eligible"]]
    ineligible_picks = [p for p in picks if not p["eligible"]]

    distribution: dict[int, int] = {}
    for p in eligible_picks:
        distribution[p["chosen_idx"]] = distribution.get(p["chosen_idx"], 0) + 1

    n_eligible_total = len(eligible_picks)
    max_count = max(distribution.values()) if distribution else 0
    max_share_observed = (max_count / n_eligible_total) if n_eligible_total > 0 else None
    dominant_idx = max(distribution, key=distribution.get) if distribution else None

    report = {
        "n_probes": len(picks),
        "n_eligible": n_eligible_total,
        "n_ineligible": len(ineligible_picks),
        "strength_fraction_declared": strength_fraction,
        "max_share_declared": max_share,
        "chosen_index_distribution": distribution,
        "n_unique_indices": len(distribution),
        "dominant_idx": dominant_idx,
        "max_share_observed": max_share_observed,
    }
    print(f"active_nontarget_control diversity gate (full real population):\n{json.dumps(report, indent=2)}")

    if n_eligible_total == 0:
        report["passed"] = False
        raise RuntimeError(
            f"active_nontarget_control diversity gate FAILED: every probe snippet had an empty "
            f"eligible set at strength_fraction={strength_fraction} -- no selection was possible "
            f"at all. Stop and escalate; do not loosen the threshold after seeing this."
        )
    if max_share_observed > max_share:
        report["passed"] = False
        raise RuntimeError(
            f"active_nontarget_control diversity gate FAILED: feature {dominant_idx} accounts for "
            f"{max_count}/{n_eligible_total} ({max_share_observed:.1%}) of eligible selections, "
            f"exceeding the declared max share {max_share:.1%}. Distribution: {distribution}. "
            f"Stop and escalate; do not proceed with a comparator dominated by one feature."
        )

    report["passed"] = True
    print(
        f"active_nontarget_control diversity gate PASSED "
        f"(n_unique_indices={len(distribution)}, max_share_observed={max_share_observed:.1%} <= "
        f"{max_share:.1%} declared, n_ineligible={len(ineligible_picks)}/{len(picks)})"
    )
    return report


def measure_own_text_cell(model, sae, *, feature: dict[str, Any], snippet_index: int, snippet: str, control_feature_idx: int, checkpoint_hash: str) -> dict[str, Any]:
    """Target necessity + two checks, all on F's own top-activating
    snippet (pre-reg section 3-4): cross_feature and within_feature are
    instrument-specificity checks (see INSTRUMENT_SPECIFICITY_NOTE --
    both are guaranteed to read 0.0 here, by construction, and are not
    scientific controls); active_nontarget_control is the falsifiable
    comparator (see ACTIVE_NONTARGET_CONTROL_NOTE) that actually has the
    capacity to fail."""
    target_idx = feature["idx"]
    seed = derive_seed("own_text", target_idx, snippet_index)

    tokens, nll_baseline, feat_acts = _baseline_pass(model, sae, snippet, seed)
    active_mask = (feat_acts[..., target_idx] > 0)[:, :-1]  # align to per_token loss: position i predicts token i+1

    # Identical seed derivation to verify_active_nontarget_control_diversity's
    # pre-flight pass -- deterministic given the seed, so this reproduces
    # exactly the selection the gate already reported, not a fresh draw.
    selection_seed = derive_seed("active_nontarget_selection", target_idx, snippet_index)
    pick = pick_matched_strength_active_nontarget(
        feat_acts, target_idx, strength_fraction=ACTIVE_NONTARGET_STRENGTH_FRACTION, rng_seed=selection_seed
    )

    nll_target = _ablated_pass_nll(model, sae, tokens, target_idx, seed, checkpoint_hash)
    nll_control = _ablated_pass_nll(model, sae, tokens, control_feature_idx, seed, checkpoint_hash)

    delta_target = (nll_target - nll_baseline)[0]
    delta_control = (nll_control - nll_baseline)[0]
    mask = active_mask[0]
    n_active = int(mask.sum().item())
    n_total = int(mask.shape[0])

    # Never falls back to argmax when ineligible (job 400287's second
    # defect) -- an empty eligible set is recorded explicitly and the
    # ablation is skipped for this cell; the target/cross-feature halves
    # above are unaffected and still reported.
    if pick["eligible"]:
        nll_active_nontarget = _ablated_pass_nll(model, sae, tokens, pick["chosen_idx"], seed, checkpoint_hash)
        delta_active_nontarget = (nll_active_nontarget - nll_baseline)[0]
        mean_delta_active_nontarget = delta_active_nontarget.mean().item()
        mean_delta_active_nontarget_active_pos = delta_active_nontarget[mask].mean().item() if n_active > 0 else None
    else:
        mean_delta_active_nontarget = None
        mean_delta_active_nontarget_active_pos = None

    return {
        "cell_type": "own_text",
        "feature_idx": target_idx,
        "source_feature_idx": target_idx,
        "source_snippet_index": snippet_index,
        "snippet_text": snippet,
        "n_tokens": int(tokens.shape[1]),
        "n_total_positions": n_total,
        "n_active_positions": n_active,
        "seed": seed,
        "mean_delta_nll_on_max_activating_text": delta_target.mean().item(),
        "mean_delta_nll_on_max_activating_text_at_active_positions": delta_target[mask].mean().item() if n_active > 0 else None,
        "cross_feature_control_idx": control_feature_idx,
        "mean_delta_nll_cross_feature_control_on_max_activating_text": delta_control.mean().item(),
        "mean_delta_nll_cross_feature_control_on_max_activating_text_at_active_positions": delta_control[mask].mean().item() if n_active > 0 else None,
        "active_nontarget_control_eligible": pick["eligible"],
        "active_nontarget_control_n_eligible": pick["n_eligible"],
        "active_nontarget_control_strength_fraction_declared": pick["strength_fraction_declared"],
        "active_nontarget_control_target_max_activation_on_max_activating_text": pick["target_max_activation"],
        "active_nontarget_control_rng_seed": pick["rng_seed"],
        "active_nontarget_control_idx": pick["chosen_idx"],
        "active_nontarget_control_activation_on_max_activating_text": pick["chosen_activation"],
        "active_nontarget_control_strength_match_ratio": pick["strength_match_ratio"],
        "mean_delta_nll_active_nontarget_control_on_max_activating_text": mean_delta_active_nontarget,
        "mean_delta_nll_active_nontarget_control_on_max_activating_text_at_active_positions": mean_delta_active_nontarget_active_pos,
        "construct_note": CONSTRUCT_NOTE,
        "falsification_conditions": FALSIFICATION_CONDITIONS,
        "instrument_specificity_note": INSTRUMENT_SPECIFICITY_NOTE,
        "active_nontarget_control_note": ACTIVE_NONTARGET_CONTROL_NOTE,
        "checkpoint_hash": checkpoint_hash,
    }


def measure_within_feature_control_cell(model, sae, *, feature: dict[str, Any], source_feature_idx: int, source_snippet_index: int, snippet: str, checkpoint_hash: str) -> dict[str, Any]:
    """Within-feature control: verifies F does not fire anywhere on this
    candidate text (drawn from a DIFFERENT feature's top-16 pool), and only
    if verified, ablates F on it (pre-reg section 4, "within-feature" row).
    Always returns a record -- verified_non_firing=False candidates are
    recorded as rejected, not silently dropped, so resume never re-checks
    them and rejection counts stay auditable."""
    target_idx = feature["idx"]
    seed = derive_seed("within_feature_control", target_idx, source_feature_idx, source_snippet_index)

    tokens, nll_baseline, feat_acts = _baseline_pass(model, sae, snippet, seed)
    target_active_anywhere = bool((feat_acts[..., target_idx] > 0).any().item())

    record: dict[str, Any] = {
        "cell_type": "within_feature_control",
        "feature_idx": target_idx,
        "source_feature_idx": source_feature_idx,
        "source_snippet_index": source_snippet_index,
        "snippet_text": snippet,
        "n_tokens": int(tokens.shape[1]),
        "seed": seed,
        "verified_non_firing": not target_active_anywhere,
        "construct_note": CONSTRUCT_NOTE,
        "falsification_conditions": FALSIFICATION_CONDITIONS,
        "checkpoint_hash": checkpoint_hash,
    }

    if target_active_anywhere:
        record["mean_delta_nll_within_feature_control_on_non_firing_text"] = None
        record["rejection_reason"] = f"feature {target_idx} is active somewhere on this candidate text -- not usable as non-firing text"
        return record

    nll_ablated = _ablated_pass_nll(model, sae, tokens, target_idx, seed, checkpoint_hash)
    delta = (nll_ablated - nll_baseline)[0]
    record["mean_delta_nll_within_feature_control_on_non_firing_text"] = delta.mean().item()
    return record


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_own_text_matrix(features: list[dict[str, Any]], snippets_by_feature: dict[int, list[str]]) -> list[dict[str, Any]]:
    cells = []
    for feature in features:
        snippets = snippets_by_feature[feature["idx"]]
        for i, snippet in enumerate(snippets):
            cells.append({"feature": feature, "snippet_index": i, "snippet": snippet})
    return cells


def build_within_feature_control_candidates(features: list[dict[str, Any]], snippets_by_feature: dict[int, list[str]]) -> list[dict[str, Any]]:
    cells = []
    n = len(features)
    for i, feature in enumerate(features):
        source_feature = features[(i + WITHIN_FEATURE_CONTROL_OFFSET) % n]
        for j, snippet in enumerate(snippets_by_feature[source_feature["idx"]]):
            cells.append({
                "feature": feature,
                "source_feature_idx": source_feature["idx"],
                "source_snippet_index": j,
                "snippet": snippet,
            })
    return cells


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D2.1-necessity: judge-free representational-necessity measurement")
    p.add_argument("--model-path", required=True, help="Local filesystem path to the gemma-3-12b-pt snapshot directory")
    p.add_argument("--sae-path", required=True, help="Local filesystem path to the layer_31_width_16k_l0_medium snapshot directory")
    p.add_argument("--snippets-file", default=None, help="Required JSON file mapping each feature idx to its top-16 activating snippets; required unless --dry-run")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--dry-run", action="store_true", help="CPU-free: construct the full job matrix and write stub records, no model/SAE load")
    p.add_argument("--control-rng-seed", type=int, default=1337)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--restart", action="store_true", help="Discard any existing necessity_records.jsonl and regenerate from scratch")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prereg_bytes = PREREG_PATH.read_bytes()
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    if prereg_sha != PREREG_SHA256:
        raise RuntimeError(
            f"pre-registration document {PREREG_PATH} has sha256 {prereg_sha}, expected "
            f"{PREREG_SHA256}. It governs this measurement's design -- refusing to proceed "
            "against a document that does not match what was reviewed."
        )
    print(f"pre-registration verified: {PREREG_PATH} sha256={prereg_sha}")

    features = FEATURES
    exclude = {f["idx"] for f in FEATURES} | REJECTED_FEATURE_IDXS
    control_feature_idx = pick_control_feature_idx(exclude=exclude, control_rng_seed=args.control_rng_seed)
    print(f"cross-feature control: idx={control_feature_idx} (control_rng_seed={args.control_rng_seed})")

    snippets_by_feature, is_stub = load_snippets(args.snippets_file, features, dry_run=args.dry_run)
    if is_stub:
        print("WARNING: no --snippets-file found; using stub placeholder text (dry-run only, no real snippet data)")

    checkpoint_hash, checkpoint_hash_basis = compute_checkpoint_hash(args.model_path, args.sae_path, dry_run=args.dry_run)
    git_provenance = harness_git_provenance()
    print(f"harness git provenance: sha={git_provenance['sha']} dirty={git_provenance['dirty']}")

    own_text_matrix = build_own_text_matrix(features, snippets_by_feature)
    within_candidates = build_within_feature_control_candidates(features, snippets_by_feature)
    print(
        f"job matrix: {len(own_text_matrix)} own-text cells (9 features x {TOP_N_SNIPPETS} snippets), "
        f"{len(within_candidates)} within-feature-control candidates (9 features x up to {TOP_N_SNIPPETS} "
        f"candidates each, verified non-firing before use, some may be rejected)"
    )

    model = sae = hf_model = None
    if not args.dry_run:
        model, sae, hf_model = load_model_and_sae(args.model_path, args.sae_path, device=args.device, dtype=args.dtype)

        sweep = _load_sweep_module()
        identity_report = sweep.verify_module_identity(model, sae)

        # hf_model came back on CPU from load_model_and_sae. Relocate to a
        # second GPU only for this brief equivalence forward pass (reusing
        # the sweep's already-fixed _secondary_cuda_device, since this is
        # gate machinery loaded dynamically the same way verify_* already
        # is -- not the loader itself, so Ground Rule 2 does not apply),
        # then free it immediately: this script has no 24h generation loop
        # after the gate, so there is no reason to keep hf_model resident
        # at all past this one check.
        equivalence_device = sweep._secondary_cuda_device(args.device)
        if equivalence_device is not None:
            hf_model = hf_model.to(equivalence_device)
        print(f"raw-HF equivalence check running hf_model on: {equivalence_device or 'cpu'}")

        equivalence_report = sweep.verify_raw_hf_equivalence(
            model, hf_model, own_text_matrix[0]["snippet"], seed=derive_seed("necessity-module-identity-check")
        )

        gpu_mem_at_gate = sweep._gpu_memory_snapshot(args.device)
        del hf_model
        import torch

        torch.cuda.empty_cache()
        gpu_mem_after_free = sweep._gpu_memory_snapshot(args.device)
        print(f"GPU memory at gate: {gpu_mem_at_gate}")
        print(f"GPU memory after hf_model free: {gpu_mem_after_free}")

        # Third hard gate, still before the fan-out: a control whose
        # selection is supposed to vary per input must be shown to vary
        # before spending the GPU time to run the full 144-cell loop on
        # it (job 400287). Stop-and-escalate on failure, same as the two
        # gates above -- this one raises before a single own-text record
        # is written, not after all of them are.
        diversity_report = verify_active_nontarget_control_diversity(model, sae, own_text_matrix)

        (out_dir / "necessity_module_identity_report.json").write_text(
            json.dumps(
                {
                    "module_identity": identity_report,
                    "raw_hf_equivalence": equivalence_report,
                    "gpu_memory_at_gate": gpu_mem_at_gate,
                    "gpu_memory_after_hf_model_free": gpu_mem_after_free,
                    "active_nontarget_control_diversity_probe": diversity_report,
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

    n_written = n_skipped = 0

    for cell in own_text_matrix:
        record_key_probe = {"cell_type": "own_text", "feature_idx": cell["feature"]["idx"], "source_feature_idx": cell["feature"]["idx"], "source_snippet_index": cell["snippet_index"]}
        if _cell_key(record_key_probe) in completed_keys:
            n_skipped += 1
            continue

        if args.dry_run:
            payload = {**record_key_probe, "snippet_text": cell["snippet"], "generated": False,
                       "mean_delta_nll_on_max_activating_text": None,
                       "mean_delta_nll_on_max_activating_text_at_active_positions": None,
                       "cross_feature_control_idx": control_feature_idx,
                       "mean_delta_nll_cross_feature_control_on_max_activating_text": None,
                       "mean_delta_nll_cross_feature_control_on_max_activating_text_at_active_positions": None,
                       "active_nontarget_control_eligible": None,
                       "active_nontarget_control_n_eligible": None,
                       "active_nontarget_control_strength_fraction_declared": ACTIVE_NONTARGET_STRENGTH_FRACTION,
                       "active_nontarget_control_target_max_activation_on_max_activating_text": None,
                       "active_nontarget_control_rng_seed": None,
                       "active_nontarget_control_idx": None,
                       "active_nontarget_control_activation_on_max_activating_text": None,
                       "active_nontarget_control_strength_match_ratio": None,
                       "mean_delta_nll_active_nontarget_control_on_max_activating_text": None,
                       "mean_delta_nll_active_nontarget_control_on_max_activating_text_at_active_positions": None,
                       "construct_note": CONSTRUCT_NOTE, "falsification_conditions": FALSIFICATION_CONDITIONS,
                       "instrument_specificity_note": INSTRUMENT_SPECIFICITY_NOTE,
                       "active_nontarget_control_note": ACTIVE_NONTARGET_CONTROL_NOTE,
                       "checkpoint_hash": checkpoint_hash}
        else:
            payload = measure_own_text_cell(
                model, sae, feature=cell["feature"], snippet_index=cell["snippet_index"], snippet=cell["snippet"],
                control_feature_idx=control_feature_idx, checkpoint_hash=checkpoint_hash,
            )
            payload["generated"] = True

        payload.update({
            "sae_id": SAE_ID, "sae_release": SAE_RELEASE, "sae_repo_id": SAE_REPO_ID, "sae_repo_revision": SAE_REPO_REVISION,
            "layer": LAYER, "n_layers": N_LAYERS, "depth_fraction": DEPTH_FRACTION, "width": WIDTH, "model_id": MODEL_ID,
            "maxActApprox": cell["feature"]["maxActApprox"], "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
            "density": cell["feature"]["density"], "domain_class": cell["feature"]["domain_class"],
            "harness_git_sha": git_provenance["sha"], "harness_git_dirty": git_provenance["dirty"],
            "checkpoint_hash_basis": checkpoint_hash_basis,
            "model_path": str(Path(args.model_path).resolve()) if Path(args.model_path).exists() else args.model_path,
            "sae_path": str(Path(args.sae_path).resolve()) if Path(args.sae_path).exists() else args.sae_path,
        })
        append_record(records_path, payload)
        n_written += 1

    # Full-run distribution, not just the 9-snippet pre-flight probe --
    # "report the distribution either way," including if a fresh run
    # turns up low-but-nonzero diversity that the pre-flight gate above
    # would have passed without it being a clean result. Read back from
    # disk rather than accumulating in-loop, so this reflects every
    # own-text record present (freshly written this run AND resumed from
    # a prior run alike), not just what this invocation itself wrote.
    full_distribution: dict[Any, int] = {}
    if records_path.exists():
        with records_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("cell_type") == "own_text":
                    idx = rec.get("active_nontarget_control_idx")
                    full_distribution[idx] = full_distribution.get(idx, 0) + 1
    print(f"active_nontarget_control_idx distribution across all {sum(full_distribution.values())} own-text record(s): {full_distribution}")
    (out_dir / "active_nontarget_control_distribution.json").write_text(
        json.dumps({"chosen_index_distribution": full_distribution, "n_unique_indices": len(full_distribution)}, indent=2),
        encoding="utf-8",
    )

    n_rejected = n_within_written = 0
    for cell in within_candidates:
        record_key_probe = {"cell_type": "within_feature_control", "feature_idx": cell["feature"]["idx"], "source_feature_idx": cell["source_feature_idx"], "source_snippet_index": cell["source_snippet_index"]}
        if _cell_key(record_key_probe) in completed_keys:
            n_skipped += 1
            continue

        if args.dry_run:
            payload = {**record_key_probe, "snippet_text": cell["snippet"], "generated": False,
                       "verified_non_firing": None,
                       "mean_delta_nll_within_feature_control_on_non_firing_text": None,
                       "construct_note": CONSTRUCT_NOTE, "falsification_conditions": FALSIFICATION_CONDITIONS,
                       "checkpoint_hash": checkpoint_hash}
        else:
            payload = measure_within_feature_control_cell(
                model, sae, feature=cell["feature"], source_feature_idx=cell["source_feature_idx"],
                source_snippet_index=cell["source_snippet_index"], snippet=cell["snippet"], checkpoint_hash=checkpoint_hash,
            )
            payload["generated"] = True
            if payload.get("verified_non_firing") is False:
                n_rejected += 1

        payload.update({
            "sae_id": SAE_ID, "sae_release": SAE_RELEASE, "sae_repo_id": SAE_REPO_ID, "sae_repo_revision": SAE_REPO_REVISION,
            "layer": LAYER, "n_layers": N_LAYERS, "depth_fraction": DEPTH_FRACTION, "width": WIDTH, "model_id": MODEL_ID,
            "maxActApprox": cell["feature"]["maxActApprox"], "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
            "density": cell["feature"]["density"], "domain_class": cell["feature"]["domain_class"],
            "harness_git_sha": git_provenance["sha"], "harness_git_dirty": git_provenance["dirty"],
            "checkpoint_hash_basis": checkpoint_hash_basis,
            "model_path": str(Path(args.model_path).resolve()) if Path(args.model_path).exists() else args.model_path,
            "sae_path": str(Path(args.sae_path).resolve()) if Path(args.sae_path).exists() else args.sae_path,
        })
        append_record(records_path, payload)
        n_within_written += 1

    print(
        f"wrote {n_written} own-text record(s) + {n_within_written} within-feature-control record(s) "
        f"({n_rejected} of those rejected as not-verified-non-firing), skipped {n_skipped} already-complete "
        f"cell(s) -> {records_path}"
    )
    if args.dry_run:
        print("--dry-run: no model/SAE was loaded, no forward pass ran (stub records only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
