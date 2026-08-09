"""Thin Qwen adapter for scripts/legacy/gemma3_tool.py's --sweep-module
contract. Nothing here is a new loader: model loading delegates entirely to
interplab.characterization.model_loading.load_local_hooked_transformer
(already tested, already used by FeatureIndex's own lazy model+SAE load),
and SAE loading delegates entirely to sae_lens.SAE.load_from_pretrained --
the exact call interplab/characterization/feature_index.py:173 already uses
for our own trained checkpoints. This file only adapts those two calls, plus
three already-measured Qwen features, to the seven names gemma3_tool.py
consumes: FEATURES, OPTIONAL_FEATURES, REJECTED_FEATURE_IDXS, WIDTH,
load_feature_manifest, load_model_and_sae, pick_control_feature_idx.

Checkpoint: rwu04lpb (registry/sae_checkpoint/95db17aa3877.json) -- TopK
SAE, k=100, d_sae=163840, layer 28 of Qwen/Qwen2.5-14B-Instruct,
hook blocks.28.hook_resid_post. Do not confuse with the superseded
9odeg5hb/pile-10k checkpoint (see gemma3_sweep.py's own correction note).

FEATURES below are the three features scripts/characterize_lite.py
actually measured (job 383755, 2026-07-26, streamed 5,000 FineWeb docs /
1,712,777 token positions) -- see docs/characterize_lite_findings.md, the
only source of real, verified per-feature numbers for this checkpoint at
tool-manifest granularity today. maxActApprox/density here are a MEASURED
sample max and firing rate over that one stream, not a Neuronpedia
sample-max proxy like Gemma's -- see MAX_ACT_APPROX_CAVEAT. Nothing is
invented to pad the list out to Gemma's nine; a thinner, real manifest is
worth more than a fabricated one the size of Gemma's.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "qwen_tool"
FEATURE_MANIFEST_FILENAME = "feature_manifest.json"

SAE_ID = "rwu04lpb"
SAE_LOCATION = "tamia:sae_checkpoints/rwu04lpb/final_400001024"
MODEL_ID = "Qwen/Qwen2.5-14B-Instruct"
MODEL_REVISION = "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"  # registry/sae_checkpoint/95db17aa3877.json
LAYER = 28
N_LAYERS = 48
WIDTH = 163840
L0_VARIANT = "topk_k100"  # TopK architecture (k=100) -- not a JumpReLU l0 in Gemma's sense

MAX_ACT_APPROX_CAVEAT = (
    "Measured max activation over a 5,000-document / 1,712,777-token-position FineWeb "
    "sample (scripts/characterize_lite.py, job 383755, 2026-07-26; see "
    "docs/characterize_lite_findings.md) -- a sample max over that one stream, not a "
    "full-corpus max, and NOT the same provenance as Gemma's Neuronpedia sample-max "
    "proxy (gemma3_sweep.MAX_ACT_APPROX_CAVEAT). Do not treat the two numbers as "
    "measured the same way."
)

# idx/label/maxActApprox/density/verdict copied verbatim from
# docs/characterize_lite_findings.md's summary table -- real measured
# numbers, not placeholders.
FEATURES: list[dict[str, Any]] = [
    {
        "idx": 9056,
        "label": "cheese",
        "domain_class": "topic",
        "maxActApprox": 47.50,
        "density": 0.000586,
        "verdict": "clean monosemantic (characterize_lite, n=1003 firings, 14.5x median rate)",
    },
    {
        "idx": 47735,
        "label": "UNESCO World Heritage",
        "domain_class": "topic",
        "maxActApprox": 40.75,
        "density": 0.000408,
        "verdict": "clean monosemantic (characterize_lite, n=699 firings, 10.1x median rate)",
    },
    {
        "idx": 44189,
        "label": "Eurovision",
        "domain_class": "topic",
        "maxActApprox": 8.50,
        "density": 0.000231,
        "low_confidence": True,
        "verdict": "weak/marginal, confirmed entangled -- carry only as the documented weak "
                   "case (characterize_lite, n=395 firings, 5.7x median rate)",
    },
]
# No optional pool and nothing rejected: characterize_lite measured exactly
# these three, and none failed verification -- an empty list/frozenset is
# the honest state, not a placeholder to fill in later.
OPTIONAL_FEATURES: list[dict[str, Any]] = []
REJECTED_FEATURE_IDXS: frozenset[int] = frozenset()


# ---------------------------------------------------------------------------
# Feature manifest -- same open schema as gemma3_sweep.py's, pre-staged once
# and read by gemma3_tool.py via load_feature_manifest(), never derived at
# tool-startup time.
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
                "verdict": f.get("verdict"),
            }
        )
    return records


def write_feature_manifest(out_dir: Path, *, include_optional: bool = False) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FEATURE_MANIFEST_FILENAME
    payload = {
        "schema_note": (
            "One record per feature: idx, label, domain_class, maxActApprox, density, "
            "sae_id, layer, width, l0_variant. Open schema, same shape as "
            "gemma3_sweep.py's manifest -- must satisfy gemma3_tool.py's "
            "REQUIRED_MANIFEST_FIELDS."
        ),
        "maxActApprox_caveat": MAX_ACT_APPROX_CAVEAT,
        "sae_release": SAE_ID,
        "sae_location": SAE_LOCATION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "features": build_feature_manifest_records(include_optional=include_optional),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_feature_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Qwen feature manifest not found at {path}; run this once to pre-stage it: "
            "python -c \"from pathlib import Path; import importlib.util as u; "
            "spec = u.spec_from_file_location('qwen_tool_adapter', "
            "'scripts/legacy/qwen_tool_adapter.py'); m = u.module_from_spec(spec); "
            "spec.loader.exec_module(m); m.write_feature_manifest(Path('results/qwen_tool'))\""
        )
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Control feature: verbatim duplicate of gemma3_sweep.pick_control_feature_idx.
# Pure and generic over d_sae already -- "generalises as-is" -- so this is a
# straight copy, per this project's established duplicate-rather-than-
# cross-import convention for out-of-chain adapters (never import from a
# frozen sibling harness; keep each adapter self-contained and hand-verified).
# ---------------------------------------------------------------------------


def pick_control_feature_idx(*, exclude: set[int], control_rng_seed: int, d_sae: int = WIDTH) -> int:
    import numpy as np

    rng = np.random.default_rng(control_rng_seed)
    while True:
        candidate = int(rng.integers(0, d_sae))
        if candidate not in exclude:
            return candidate


# ---------------------------------------------------------------------------
# Model + SAE loading -- delegates entirely to existing, already-tested
# interplab loaders. No new loader is written here.
# ---------------------------------------------------------------------------


def _fail_if_missing(path: Path, *, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{what} not found at {path!r}. This adapter only accepts pre-staged local "
            f"filesystem paths -- it will not fall back to a network fetch."
        )


def load_model_and_sae(
    model_path: str | Path,
    sae_path: str | Path,
    *,
    device: str = "cuda",
    dtype: str = "bfloat16",
):
    """Returns (model, sae, hf_model), matching gemma3_sweep.load_model_and_sae's
    return shape so gemma3_tool.py's load_bundle() works unchanged against
    either module.

    hf_model is always None here: load_local_hooked_transformer (below)
    does not hand back the raw HF object it converts from -- unlike
    Gemma's loader, which keeps it for an equivalence check this tool never
    runs. Returning None is honest about that; loading a second ~28GB+ copy
    of the raw HF model just to fill the tuple slot would cost a real load
    for a value load_bundle() deletes immediately (`del hf_model`) anyway.

    KNOWN, NOT FIXED HERE: load_local_hooked_transformer's own
    AutoModelForCausalLM.from_pretrained call takes no dtype argument, so
    the raw HF load happens at the checkpoint's stored dtype regardless of
    the `dtype` passed here; `dtype` only reaches the resulting
    HookedTransformer's own config. This is a property of the shared,
    already-tested certification loader (interplab/characterization/
    model_loading.py) -- out of scope to change from this adapter, per the
    instruction not to write new loaders.
    """
    import torch
    from sae_lens import SAE

    from interplab.characterization.model_loading import load_local_hooked_transformer

    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise RuntimeError(
            "HF_HUB_OFFLINE=1 is not set in the environment. Every Tamia compute-node job "
            "in this project requires it -- refusing to proceed rather than risk a silent "
            "network fetch."
        )

    model_path = Path(model_path)
    sae_path = Path(sae_path)
    _fail_if_missing(model_path, what="Qwen model snapshot directory")
    _fail_if_missing(sae_path, what="Qwen SAE snapshot directory")

    torch_dtype = getattr(torch, dtype)

    model = load_local_hooked_transformer(str(model_path), device=device, dtype=torch_dtype)
    model.eval()

    sae = SAE.load_from_pretrained(str(sae_path), device="cpu")
    sae = sae.to(dtype=torch.float32, device=device)
    sae.eval()

    model_d_model = model.cfg.d_model
    if model_d_model != sae.cfg.d_in:
        raise RuntimeError(
            f"d_model mismatch: model reports d_model={model_d_model}, SAE reports "
            f"d_in={sae.cfg.d_in}. Stop here rather than proceed with a mismatched hook."
        )

    return model, sae, None
