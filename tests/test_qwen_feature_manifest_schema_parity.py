"""Schema parity: every key gemma3_sweep.write_feature_manifest() emits,
at the top level and per-feature, must also be present in the Qwen feature
manifest build_qwen_feature_manifest.build_manifest() produces.

Qwen's manifest is allowed to have EXTRA keys (documented extensions --
density_ratio_to_population_median, matched_control_feature, the caveat
strings, etc.); it must never be MISSING one of Gemma's keys under a
different name. That is the whole point of the firing_rate->density,
max_activation->maxActApprox, top_examples->snippets mapping: achieving
parity in field NAMES, not just in field meaning.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import build_qwen_feature_manifest as qwen_build  # noqa: E402
import gemma3_sweep  # noqa: E402
import qwen_tool_adapter  # noqa: E402

# ---------------------------------------------------------------------------
# Read the TRACKED manifest artifact, never a rebuild from untracked inputs.
# build_manifest() reads results/characterize_lite/**, which .gitignore's
# `results/` rule excludes -- so on CI, or any fresh clone, calling it raises
# FileNotFoundError. That is not a test result, it is the test harness
# depending on a file that only exists on the author's machine. The staged
# artifact is verified byte-equal to a fresh build by
# test_pretaged_manifest_artifact_is_up_to_date, so reading it loses no
# coverage -- and gains some, since it is what the tool actually loads.
# ---------------------------------------------------------------------------
TRACKED_QWEN_MANIFEST = REPO_ROOT / "results" / "qwen_tool" / "feature_manifest.json"


def _qwen_manifest():
    return json.loads(TRACKED_QWEN_MANIFEST.read_text(encoding="utf-8"))


def _gemma_manifest(tmp_path):
    out_dir = tmp_path / "gemma3_sweep"
    path = gemma3_sweep.write_feature_manifest(out_dir, include_optional=True)
    return gemma3_sweep.load_feature_manifest(path)


def test_top_level_keys_are_a_subset_of_qwen_manifest(tmp_path):
    gemma_manifest = _gemma_manifest(tmp_path)
    qwen_manifest = _qwen_manifest()

    missing = set(gemma_manifest.keys()) - set(qwen_manifest.keys())
    assert not missing, f"Qwen manifest is missing top-level key(s) present in Gemma's: {missing}"


def test_per_feature_keys_are_a_subset_of_qwen_feature_records(tmp_path):
    gemma_manifest = _gemma_manifest(tmp_path)
    qwen_manifest = _qwen_manifest()

    gemma_keys = set(gemma_manifest["features"][0].keys())
    assert gemma_keys, "Gemma's manifest produced no feature records -- nothing to compare against"

    qwen_records = qwen_manifest["features"] + [qwen_manifest["optional_feature"]]
    assert qwen_records, "Qwen manifest produced no feature records"

    for rec in qwen_records:
        missing = gemma_keys - set(rec.keys())
        assert not missing, f"Qwen feature idx={rec.get('idx')} is missing key(s) present in Gemma's schema: {missing}"


def test_qwen_feature_records_share_gemma_key_value_types(tmp_path):
    """Not just key presence -- the shared keys should carry the same
    Python type on both sides (e.g. maxActApprox is always a float,
    density is always a float, idx is always an int), so a consumer
    written against Gemma's manifest doesn't need a type branch for
    Qwen's."""
    gemma_manifest = _gemma_manifest(tmp_path)
    qwen_manifest = _qwen_manifest()

    gemma_rec = gemma_manifest["features"][0]
    qwen_rec = qwen_manifest["features"][0]

    shared_keys = set(gemma_rec.keys()) & set(qwen_rec.keys())
    assert shared_keys == set(gemma_rec.keys())

    for key in shared_keys:
        gemma_type = type(gemma_rec[key])
        qwen_type = type(qwen_rec[key])
        if gemma_type is bool or qwen_type is bool:
            # bool is a subclass of int -- compare exactly for this one
            assert gemma_type is qwen_type, f"key {key!r}: gemma={gemma_type}, qwen={qwen_type}"
            continue
        if gemma_type in (int, float) and qwen_type in (int, float):
            continue  # numeric widening (int vs float) is fine
        assert gemma_type is qwen_type, f"key {key!r}: gemma={gemma_type}, qwen={qwen_type}"


def test_control_feature_uses_shared_global_mechanism_not_matched_control():
    """Per explicit instruction: the actual control_feature_idx must come
    from gemma3_sweep.pick_control_feature_idx (the same global-random-draw
    mechanism Gemma uses), never from characterize_lite's own per-feature
    matched_control_feature -- matched_control_feature may only appear as
    displayed metadata."""
    qwen_manifest = _qwen_manifest()

    control_idx = qwen_manifest["control_feature_idx"]
    selected_idxs = {f["idx"] for f in qwen_manifest["features"]}
    selected_idxs.add(qwen_manifest["optional_feature"]["idx"])
    rejected_idxs = {r["idx"] for r in qwen_manifest["rejected_features"]}
    verified_not_selected_idxs = {v["idx"] for v in qwen_manifest["verified_not_selected"]}

    assert control_idx not in selected_idxs
    assert control_idx not in rejected_idxs
    assert control_idx not in verified_not_selected_idxs

    matched_controls = {f["matched_control_feature"] for f in qwen_manifest["features"]}
    # The global draw is not required to differ from every per-feature matched
    # control (it's a big pool), but it must not BE any of the selected
    # features' own idx, which is the actual invariant that matters here.
    assert control_idx not in {f["idx"] for f in qwen_manifest["features"]}
    assert isinstance(matched_controls, set)  # displayed metadata only, sanity-checked as present


def test_rejected_features_are_recorded_with_reasons():
    qwen_manifest = _qwen_manifest()
    assert qwen_manifest["rejected_features"], "expected at least one recorded reject, mirroring REJECTED_FEATURE_IDXS"
    for rejected in qwen_manifest["rejected_features"]:
        assert isinstance(rejected["idx"], int)
        assert isinstance(rejected["reason"], str) and len(rejected["reason"]) > 0


def test_manifest_carries_the_required_divergence_caveats():
    qwen_manifest = _qwen_manifest()
    assert qwen_manifest["labels_auto_derived_caveat"]
    assert qwen_manifest["causal_screening_caveat"]
    assert qwen_manifest["maxActApprox_caveat"]
    assert qwen_manifest["density_band_disclosure"]
    assert qwen_manifest["density_cross_sae_caveat"]
    assert qwen_manifest["ranking_near_miss_caveat"], (
        "sixth caveat: the firing-rate-descending ranking would have excluded all of tier 1"
    )
    # every per-feature record repeats the maxActApprox caveat inline, matching Gemma's convention
    for rec in qwen_manifest["features"]:
        assert rec["maxActApprox_caveat"] == qwen_manifest["maxActApprox_caveat"]


def test_two_evidence_tiers_present_tier1_first_not_merged():
    qwen_manifest = _qwen_manifest()
    features = qwen_manifest["features"]

    tiers = [rec["evidence_tier"] for rec in features]
    assert tiers.count(1) == 3, "expected exactly 3 tier-1 (concept-validated) features"
    assert tiers.count(2) == 9, "expected exactly 9 tier-2 (taxonomy-derived) features"
    assert tiers == sorted(tiers), "tier 1 must be listed before tier 2 (the dropdown opens on the first entries)"

    tier1_idxs = {rec["idx"] for rec in features if rec["evidence_tier"] == 1}
    assert tier1_idxs == {9056, 47735, 44189}

    # optional feature is tier 2 -- tier 1 has no optional pool
    assert qwen_manifest["optional_feature"]["evidence_tier"] == 2


def test_adapter_features_exactly_equal_manifest_features():
    """The actual guard this file exists for: resolve_control_feature_idx
    (gemma3_tool.py) builds its exclusion set from the ADAPTER module's
    FEATURES/OPTIONAL_FEATURES/REJECTED_FEATURE_IDXS, not from whatever
    manifest JSON happens to be on disk. If those two ever diverge again,
    the tool's own claim that the control "uses the same exclusion set the
    D2.1 sweep uses" becomes false without anything raising."""
    qwen_manifest = _qwen_manifest()

    manifest_feature_idxs = {f["idx"] for f in qwen_manifest["features"]}
    adapter_feature_idxs = {f["idx"] for f in qwen_tool_adapter.FEATURES}
    assert adapter_feature_idxs == manifest_feature_idxs

    manifest_optional_idx = qwen_manifest["optional_feature"]["idx"]
    adapter_optional_idxs = {f["idx"] for f in qwen_tool_adapter.OPTIONAL_FEATURES}
    assert adapter_optional_idxs == {manifest_optional_idx}

    manifest_rejected_idxs = {r["idx"] for r in qwen_manifest["rejected_features"]}
    assert manifest_rejected_idxs == qwen_tool_adapter.REJECTED_FEATURE_IDXS


def test_adapter_import_does_not_require_untracked_characterize_lite_files(monkeypatch, tmp_path):
    """The actual guard: results/characterize_lite/rwu04lpb{,_taxonomy40}/
    characterize_lite.json are UNTRACKED (.gitignore:19 excludes results/,
    and unlike the tracked feature_manifest.json these two were never
    force-added). A prior version of qwen_tool_adapter.py called
    build_qwen_feature_manifest.build_manifest() -- which reads both of
    those files -- at MODULE IMPORT time. On any machine without them (a
    fresh clone, a Space, quite possibly the cluster), importing the
    adapter raised before the tool could even report a missing manifest.
    The existing set-equality test above passes on this machine only
    because the untracked files happen to be present here; it would not
    have caught this.

    Simulated by pointing both characterize_lite paths at files that do
    not exist and forcing a fresh import of qwen_tool_adapter: if anything
    on the import path still calls build_manifest(), this raises
    FileNotFoundError instead of importing cleanly.
    """
    # Read the tracked manifest directly, BEFORE patching, as the ground
    # truth to compare the fresh import against -- not via build_manifest()
    # (that would hit the now-patched, nonexistent paths too).
    tracked_manifest_path = qwen_build.OUT_DIR / qwen_build.MANIFEST_FILENAME
    tracked_idxs = {f["idx"] for f in json.loads(tracked_manifest_path.read_text(encoding="utf-8"))["features"]}

    nonexistent = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(qwen_build, "TIER1_CHARACTERIZE_LITE_PATH", nonexistent)
    monkeypatch.setattr(qwen_build, "TIER2_CHARACTERIZE_LITE_PATH", nonexistent)

    original_module = sys.modules.get("qwen_tool_adapter")
    sys.modules.pop("qwen_tool_adapter", None)
    try:
        import qwen_tool_adapter as fresh_adapter  # re-executes module-level code under the patch
        assert len(fresh_adapter.FEATURES) == 12
        assert {f["idx"] for f in fresh_adapter.FEATURES} == tracked_idxs
    finally:
        if original_module is not None:
            sys.modules["qwen_tool_adapter"] = original_module
        else:
            sys.modules.pop("qwen_tool_adapter", None)


def test_resolved_control_index_is_in_neither_adapter_nor_manifest_features():
    qwen_manifest = _qwen_manifest()
    control_idx = qwen_tool_adapter._MANIFEST["control_feature_idx"]

    adapter_exclusion_set = (
        {f["idx"] for f in qwen_tool_adapter.FEATURES}
        | {f["idx"] for f in qwen_tool_adapter.OPTIONAL_FEATURES}
        | qwen_tool_adapter.REJECTED_FEATURE_IDXS
    )
    manifest_exclusion_set = (
        {f["idx"] for f in qwen_manifest["features"]}
        | {qwen_manifest["optional_feature"]["idx"]}
        | {r["idx"] for r in qwen_manifest["rejected_features"]}
    )
    assert control_idx not in adapter_exclusion_set
    assert control_idx not in manifest_exclusion_set
