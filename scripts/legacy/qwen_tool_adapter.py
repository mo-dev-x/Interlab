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

FEATURES/OPTIONAL_FEATURES/REJECTED_FEATURE_IDXS below are derived from the
TRACKED manifest at results/qwen_tool/feature_manifest.json, read at import
time -- NOT from calling build_qwen_feature_manifest.build_manifest(),
which reads two UNTRACKED characterize_lite.json files (.gitignore:19
excludes results/; those two were never force-added, unlike the manifest
itself). An earlier version of this file called build_manifest() directly
at module scope: it worked on this machine because those files happen to
be present here, and would raise ModuleNotFoundError-adjacent ImportError
on any fresh clone, Space, or cluster checkout that only has the tracked
manifest -- the artifact that would have prevented the crash, unread.
Same defect class as the Gemma manifest fix earlier this week, one layer
deeper: an ignore rule silently excluding something a downstream consumer
requires.

This also matches Gemma's own pattern exactly: gemma3_sweep.py's tool
contract consumes a pre-staged manifest file and never regenerates one at
runtime. build_qwen_feature_manifest.py remains the REGENERATOR -- run it
directly (`python scripts/legacy/build_qwen_feature_manifest.py`) or call
write_feature_manifest() below -- but nothing on the import path calls it.
The exclusion set and the manifest a human reads now come from the same
bytes on disk, not two derivations that happen to agree today.
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

# Cheap, no file I/O: these are plain literals on the builder module, not a
# build_manifest() call.
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


def load_feature_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Qwen feature manifest not found at {path}; regenerate it deliberately (requires "
            "the untracked characterize_lite.json inputs, unlike loading the tracked manifest "
            "itself): python scripts/legacy/build_qwen_feature_manifest.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


# Import-time read of the TRACKED manifest only -- see module docstring.
# This is the one line that must never become build_qwen_feature_manifest.build_manifest().
_MANIFEST: dict[str, Any] = load_feature_manifest(DEFAULT_OUT_DIR / FEATURE_MANIFEST_FILENAME)
FEATURES: list[dict[str, Any]] = _MANIFEST["features"]
OPTIONAL_FEATURES: list[dict[str, Any]] = [_MANIFEST["optional_feature"]]
REJECTED_FEATURE_IDXS: frozenset[int] = frozenset(r["idx"] for r in _MANIFEST["rejected_features"])


# ---------------------------------------------------------------------------
# Regeneration -- deliberate only, never on import. Rebuilds from the
# untracked characterize_lite.json inputs via build_qwen_feature_manifest
# and overwrites the tracked manifest. Run this after the underlying
# characterize_lite data changes; nothing else in this file calls it.
# ---------------------------------------------------------------------------


def write_feature_manifest(out_dir: Path, *, include_optional: bool = False) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FEATURE_MANIFEST_FILENAME
    payload = _manifest_builder.build_manifest()
    if not include_optional:
        payload = {**payload, "optional_feature": None}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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
