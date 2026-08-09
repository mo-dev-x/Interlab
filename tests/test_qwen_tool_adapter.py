"""Wiring tests for scripts/legacy/qwen_tool_adapter.py -- the thin Qwen
implementation of gemma3_tool.py's --sweep-module contract (FEATURES,
OPTIONAL_FEATURES, REJECTED_FEATURE_IDXS, WIDTH, load_feature_manifest,
load_model_and_sae, pick_control_feature_idx).

No GPU, no real model/SAE weights. What matters here is that the contract
is actually satisfied and that gemma3_tool.py's own generic functions
(feature_by_idx, resolve_control_feature_idx, dose_to_absolute_clamp, ...)
work unchanged against this module's manifest, the same way they already
do against gemma3_sweep.py's.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_SCRIPT = REPO_ROOT / "scripts" / "legacy" / "qwen_tool_adapter.py"
TOOL_SCRIPT = REPO_ROOT / "scripts" / "legacy" / "gemma3_tool.py"
GEMMA_SWEEP_SCRIPT = REPO_ROOT / "scripts" / "legacy" / "gemma3_sweep.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qwen = _load("qwen_tool_adapter", ADAPTER_SCRIPT)
tool = _load("gemma3_tool", TOOL_SCRIPT)
gemma_sweep = _load("gemma3_sweep", GEMMA_SWEEP_SCRIPT)


# ---------------------------------------------------------------------------
# contract shape
# ---------------------------------------------------------------------------

SWEEP_CONTRACT_NAMES = (
    "FEATURES",
    "OPTIONAL_FEATURES",
    "REJECTED_FEATURE_IDXS",
    "WIDTH",
    "load_feature_manifest",
    "load_model_and_sae",
    "pick_control_feature_idx",
)


def test_exposes_every_contract_name():
    for name in SWEEP_CONTRACT_NAMES:
        assert hasattr(qwen, name), f"missing {name!r}"


def test_width_is_qwen_d_sae_not_gemma():
    assert qwen.WIDTH == 163840
    assert qwen.WIDTH != gemma_sweep.WIDTH


def test_features_are_real_characterize_lite_numbers_not_padded_to_nine():
    # Real, measured data exists for exactly 3 features (docs/
    # characterize_lite_findings.md) -- a thinner, real manifest is
    # correct here; padding it out to Gemma's 9 would mean inventing
    # numbers.
    idxs = {f["idx"] for f in qwen.FEATURES}
    assert idxs == {9056, 47735, 44189}
    by_idx = {f["idx"]: f for f in qwen.FEATURES}
    assert by_idx[9056]["maxActApprox"] == pytest.approx(47.50)
    assert by_idx[47735]["maxActApprox"] == pytest.approx(40.75)
    assert by_idx[44189]["maxActApprox"] == pytest.approx(8.50)
    assert by_idx[44189].get("low_confidence") is True


def test_optional_features_and_rejected_idxs_are_honestly_empty():
    assert qwen.OPTIONAL_FEATURES == []
    assert not qwen.REJECTED_FEATURE_IDXS


# ---------------------------------------------------------------------------
# feature manifest -- open schema, same REQUIRED_MANIFEST_FIELDS gemma3_tool.py
# checks against gemma3_sweep.py's manifest.
# ---------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = (
    "idx",
    "label",
    "domain_class",
    "maxActApprox",
    "maxActApprox_caveat",
    "density",
    "sae_id",
    "layer",
    "width",
    "l0_variant",
)


def test_write_then_load_feature_manifest_round_trips_all_required_fields(tmp_path):
    written = qwen.write_feature_manifest(tmp_path)
    manifest = qwen.load_feature_manifest(written)
    assert len(manifest["features"]) == 3
    assert {f["idx"] for f in manifest["features"]} == {9056, 47735, 44189}
    for f in manifest["features"]:
        for field in REQUIRED_MANIFEST_FIELDS:
            assert f.get(field) is not None, f"feature {f.get('idx')} missing {field}"
    assert manifest["sae_release"] == qwen.SAE_ID
    assert manifest["model_id"] == qwen.MODEL_ID
    assert manifest["maxActApprox_caveat"] == qwen.MAX_ACT_APPROX_CAVEAT


def test_load_feature_manifest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        qwen.load_feature_manifest(REPO_ROOT / "does" / "not" / "exist.json")


def test_pretaged_manifest_artifact_is_up_to_date():
    """The committed results/qwen_tool/feature_manifest.json is a real,
    pre-staged artifact (same convention as results/gemma3_sweep/
    feature_manifest.json), not regenerated at tool-startup time -- this
    guards against it drifting from what write_feature_manifest() would
    produce today."""
    staged_path = REPO_ROOT / "results" / "qwen_tool" / "feature_manifest.json"
    if not staged_path.exists():
        pytest.skip("results/qwen_tool/feature_manifest.json not staged in this checkout")
    staged = json.loads(staged_path.read_text(encoding="utf-8"))
    fresh = json.loads(
        json.dumps(
            {
                "maxActApprox_caveat": qwen.MAX_ACT_APPROX_CAVEAT,
                "sae_release": qwen.SAE_ID,
                "model_id": qwen.MODEL_ID,
                "features": qwen.build_feature_manifest_records(),
            }
        )
    )
    assert staged["maxActApprox_caveat"] == fresh["maxActApprox_caveat"]
    assert staged["sae_release"] == fresh["sae_release"]
    assert staged["model_id"] == fresh["model_id"]
    assert staged["features"] == fresh["features"]


# ---------------------------------------------------------------------------
# gemma3_tool.py's generic manifest/dose helpers, run against THIS manifest
# ---------------------------------------------------------------------------


def test_tool_feature_helpers_work_against_qwen_manifest(tmp_path):
    manifest = qwen.load_feature_manifest(qwen.write_feature_manifest(tmp_path))
    choices = tool.feature_dropdown_choices(manifest)
    assert len(choices) == 3
    for _label, idx in choices:
        feature = tool.feature_by_idx(manifest, idx)
        assert feature["idx"] == idx

    cheese = tool.feature_by_idx(manifest, 9056)
    clamp = tool.dose_to_absolute_clamp("steer", 2.0, cheese["maxActApprox"])
    assert clamp == pytest.approx(2.0 * 47.50)
    assert tool.dose_to_absolute_clamp("ablate", 4.0, cheese["maxActApprox"]) == 0.0


# ---------------------------------------------------------------------------
# control feature: pick_control_feature_idx must be a faithful duplicate of
# gemma3_sweep.py's -- same seed, same d_sae, same exclude set -> same draw.
# This is a regression test for the duplication itself, not just for this
# adapter in isolation.
# ---------------------------------------------------------------------------


def test_pick_control_feature_idx_is_deterministic():
    a = qwen.pick_control_feature_idx(exclude=set(), control_rng_seed=42, d_sae=qwen.WIDTH)
    b = qwen.pick_control_feature_idx(exclude=set(), control_rng_seed=42, d_sae=qwen.WIDTH)
    assert a == b


def test_pick_control_feature_idx_never_returns_an_excluded_index():
    exclude = {f["idx"] for f in qwen.FEATURES}
    for seed in range(20):
        idx = qwen.pick_control_feature_idx(exclude=exclude, control_rng_seed=seed, d_sae=qwen.WIDTH)
        assert idx not in exclude
        assert 0 <= idx < qwen.WIDTH


def test_pick_control_feature_idx_matches_gemma_sweeps_implementation_bit_for_bit():
    """Verbatim-duplicate claim, checked: for the same (exclude, seed, d_sae)
    triple the two modules must draw the identical index, since both wrap
    the identical numpy default_rng(seed).integers(0, d_sae) rejection-
    sampling loop. A drift here would mean the duplication silently
    diverged."""
    exclude = {1, 2, 3}
    for seed in range(10):
        assert qwen.pick_control_feature_idx(
            exclude=exclude, control_rng_seed=seed, d_sae=1000
        ) == gemma_sweep.pick_control_feature_idx(exclude=exclude, control_rng_seed=seed, d_sae=1000)


def test_resolve_control_feature_idx_works_against_qwen_adapter(tmp_path):
    manifest = qwen.load_feature_manifest(qwen.write_feature_manifest(tmp_path))
    control_idx = tool.resolve_control_feature_idx(qwen, manifest, control_rng_seed=1337)
    assert control_idx not in {f["idx"] for f in manifest["features"]}
    assert control_idx not in qwen.REJECTED_FEATURE_IDXS
    assert 0 <= control_idx < qwen.WIDTH


# ---------------------------------------------------------------------------
# offline guard + path fail-fast -- load_model_and_sae, and gemma3_tool.py's
# generic load_bundle() run against it.
# ---------------------------------------------------------------------------


def test_load_model_and_sae_without_hf_hub_offline_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    with pytest.raises(RuntimeError):
        qwen.load_model_and_sae(
            str(tmp_path / "does_not_exist_model"), str(tmp_path / "does_not_exist_sae"),
            device="cpu", dtype="bfloat16",
        )


def test_load_model_and_sae_nonexistent_model_path_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    fake_sae_path = tmp_path / "sae"
    fake_sae_path.mkdir()
    with pytest.raises(FileNotFoundError):
        qwen.load_model_and_sae(
            str(tmp_path / "does_not_exist_model"), str(fake_sae_path), device="cpu", dtype="bfloat16",
        )


def test_load_model_and_sae_nonexistent_sae_path_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    fake_model_path = tmp_path / "model"
    fake_model_path.mkdir()
    (fake_model_path / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        qwen.load_model_and_sae(
            str(fake_model_path), str(tmp_path / "does_not_exist_sae"), device="cpu", dtype="bfloat16",
        )


def test_load_bundle_from_gemma3_tool_works_against_qwen_adapter(monkeypatch, tmp_path):
    """gemma3_tool.py's own load_bundle() is generic over the sweep module
    it's handed -- this is the actual point of --sweep-module, checked
    end-to-end rather than just asserting the two modules look similar."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    fake_sae_path = tmp_path / "sae"
    fake_sae_path.mkdir()
    with pytest.raises(FileNotFoundError):
        tool.load_bundle(
            qwen, str(tmp_path / "does_not_exist_model"), str(fake_sae_path), device="cpu", dtype="bfloat16",
        )
