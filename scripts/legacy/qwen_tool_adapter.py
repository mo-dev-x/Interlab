"""Thin Qwen adapter for scripts/legacy/gemma3_tool.py's --sweep-module
contract. Nothing here is a new loader: model loading delegates entirely to
interplab.characterization.model_loading.load_local_hooked_transformer
(already tested, already used by FeatureIndex's own lazy model+SAE load),
and SAE loading delegates entirely to sae_lens.SAE.load_from_pretrained --
the exact call interplab/characterization/feature_index.py:173 already uses
for our own trained checkpoints. This file only adapts those two calls,
plus the feature pool build_qwen_feature_manifest.py builds, to the seven
names gemma3_tool.py consumes: FEATURES, OPTIONAL_FEATURES,
REJECTED_FEATURE_IDXS, WIDTH, load_feature_manifest, load_model_and_sae,
pick_control_feature_idx.

Checkpoint: rwu04lpb (registry/sae_checkpoint/95db17aa3877.json) -- TopK
SAE, k=100, d_sae=163840, layer 28 of Qwen/Qwen2.5-14B-Instruct,
hook blocks.28.hook_resid_post. Do not confuse with the superseded
9odeg5hb/pile-10k checkpoint (see gemma3_sweep.py's own correction note).

FEATURES/OPTIONAL_FEATURES/REJECTED_FEATURE_IDXS below are IMPORTED from
build_qwen_feature_manifest.py, not redefined here. That module was
previously a second, disjoint 9-feature manifest at a different path
(results/qwen_sweep/) while this adapter carried its own separate
3-feature FEATURES constant -- resolve_control_feature_idx (gemma3_tool.py)
builds its exclusion set from THIS module's FEATURES, so the two could
diverge silently: all 9 of the other manifest's features were eligible to
be drawn as "the random control" despite the tool's own header claiming
the control uses "the same exclusion set the D2.1 sweep uses". Importing
rather than duplicating makes that claim true by construction instead of
by convention -- see tests/test_qwen_feature_manifest_schema_parity.py's
adapter/manifest set-equality assertion, which is the actual guard.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_qwen_feature_manifest as _manifest_builder  # noqa: E402

DEFAULT_OUT_DIR = _manifest_builder.OUT_DIR
FEATURE_MANIFEST_FILENAME = _manifest_builder.MANIFEST_FILENAME

SAE_ID = _manifest_builder.SAE_RELEASE
SAE_LOCATION = "tamia:sae_checkpoints/rwu04lpb/final_400001024"
MODEL_ID = _manifest_builder.MODEL_ID
MODEL_REVISION = "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"  # registry/sae_checkpoint/95db17aa3877.json
LAYER = _manifest_builder.LAYER
N_LAYERS = 48
WIDTH = _manifest_builder.WIDTH
L0_VARIANT = _manifest_builder.L0_VARIANT

MAX_ACT_APPROX_CAVEAT = _manifest_builder.MAX_ACT_APPROX_CAVEAT

# Single source of truth: the merged manifest build_qwen_feature_manifest.py
# produces (tier 1: 3 concept-validated features, tier 2: 9 taxonomy-derived
# + 1 optional). FEATURES here IS that manifest's own "features" list (12
# entries, tier 1 first) -- not a copy, the same values, so the two cannot
# drift apart the way the old 3-vs-9 split did.
_MANIFEST: dict[str, Any] = _manifest_builder.build_manifest()
FEATURES: list[dict[str, Any]] = _MANIFEST["features"]
OPTIONAL_FEATURES: list[dict[str, Any]] = [_MANIFEST["optional_feature"]]
REJECTED_FEATURE_IDXS: frozenset[int] = frozenset(r["idx"] for r in _MANIFEST["rejected_features"])


# ---------------------------------------------------------------------------
# Feature manifest -- same open schema as gemma3_sweep.py's, pre-staged once
# and read by gemma3_tool.py via load_feature_manifest(), never derived at
# tool-startup time. Written from _MANIFEST directly (build_qwen_feature_
# manifest.build_manifest()'s own output) rather than reconstructed from
# FEATURES here -- FEATURES already IS a slice of that same manifest, so
# rebuilding it a second, slightly-different way (as the old
# build_feature_manifest_records did, dropping every field but a handful)
# is exactly the kind of divergence this file now exists to prevent.
# ---------------------------------------------------------------------------


def write_feature_manifest(out_dir: Path, *, include_optional: bool = False) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FEATURE_MANIFEST_FILENAME
    payload = dict(_MANIFEST)
    if not include_optional:
        payload = {**payload, "optional_feature": None}
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
