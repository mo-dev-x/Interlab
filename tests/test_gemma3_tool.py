"""Wiring tests for scripts/legacy/gemma3_tool.py (PI deliverable #4).

No GPU, no real model/SAE weights, no Gradio launch. What breaks in this
tool is wiring -- a wrong import, a missing manifest field, a dose
computed against the wrong feature's maxActApprox, an offline guard that
doesn't fire before a network call -- so that's what these tests check.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "gemma3_tool.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load("gemma3_tool", SCRIPT)
sweep = tool._load_sweep_module()


# ---------------------------------------------------------------------------
# manifest
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


def test_manifest_loads_all_nine_features_every_field_non_null():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    features = manifest["features"]
    assert len(features) == 9
    assert {f["idx"] for f in features} == {f["idx"] for f in sweep.FEATURES}
    for f in features:
        for field in REQUIRED_MANIFEST_FIELDS:
            assert f.get(field) is not None, f"feature {f.get('idx')} missing {field}"


def test_manifest_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        tool.load_manifest(REPO_ROOT / "does" / "not" / "exist.json", sweep)


def test_feature_by_idx_and_dropdown_choices_agree():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    choices = tool.feature_dropdown_choices(manifest)
    assert len(choices) == 9
    for _label, idx in choices:
        feature = tool.feature_by_idx(manifest, idx)
        assert feature["idx"] == idx


def test_feature_by_idx_unknown_raises():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    with pytest.raises(KeyError):
        tool.feature_by_idx(manifest, 999999)


# ---------------------------------------------------------------------------
# dose -> absolute clamp arithmetic
# ---------------------------------------------------------------------------


def test_dose_to_absolute_clamp_steer_scales_by_max_act_approx():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    feature = tool.feature_by_idx(manifest, 250)
    for dose in tool.DOSE_GRID:
        clamp = tool.dose_to_absolute_clamp("steer", dose, feature["maxActApprox"])
        assert clamp == pytest.approx(dose * feature["maxActApprox"])


def test_dose_to_absolute_clamp_ablate_is_always_zero_regardless_of_dose():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    feature = tool.feature_by_idx(manifest, 4500)
    for dose in tool.DOSE_GRID:
        assert tool.dose_to_absolute_clamp("ablate", dose, feature["maxActApprox"]) == 0.0


def test_dose_to_absolute_clamp_uses_the_selected_feature_own_max_act_approx():
    """Two different features at the same dose must not collapse to the
    same clamp value -- a bug here would silently steer at the wrong
    magnitude while showing the right feature name in the UI."""
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    f250 = tool.feature_by_idx(manifest, 250)
    f4500 = tool.feature_by_idx(manifest, 4500)
    assert f250["maxActApprox"] != f4500["maxActApprox"]
    clamp_250 = tool.dose_to_absolute_clamp("steer", 2.0, f250["maxActApprox"])
    clamp_4500 = tool.dose_to_absolute_clamp("steer", 2.0, f4500["maxActApprox"])
    assert clamp_250 != clamp_4500
    assert clamp_250 == pytest.approx(2.0 * f250["maxActApprox"])
    assert clamp_4500 == pytest.approx(2.0 * f4500["maxActApprox"])


def test_dose_to_absolute_clamp_rejects_unknown_mode():
    with pytest.raises(ValueError):
        tool.dose_to_absolute_clamp("nonsense", 1.0, 100.0)


# ---------------------------------------------------------------------------
# _make_clamp_hook must be imported, never redefined
# ---------------------------------------------------------------------------


def test_make_clamp_hook_is_imported_from_interplab_not_redefined():
    from interplab.interventions import hooks as interplab_hooks

    assert tool._make_clamp_hook is interplab_hooks._make_clamp_hook
    assert tool._make_clamp_hook.__module__ == "interplab.interventions.hooks"


# ---------------------------------------------------------------------------
# offline guard
# ---------------------------------------------------------------------------


def test_load_bundle_nonexistent_model_path_raises_before_any_network_call(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    fake_sae_path = tmp_path / "sae"
    fake_sae_path.mkdir()
    with pytest.raises(FileNotFoundError):
        tool.load_bundle(
            sweep,
            str(tmp_path / "does_not_exist_model"),
            str(fake_sae_path),
            device="cuda",
            dtype="bfloat16",
        )


def test_load_bundle_nonexistent_sae_path_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    fake_model_path = tmp_path / "model"
    fake_model_path.mkdir()
    (fake_model_path / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        tool.load_bundle(
            sweep,
            str(fake_model_path),
            str(tmp_path / "does_not_exist_sae"),
            device="cuda",
            dtype="bfloat16",
        )


def test_load_bundle_without_hf_hub_offline_env_var_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    with pytest.raises(RuntimeError):
        tool.load_bundle(
            sweep,
            str(tmp_path / "does_not_exist_model"),
            str(tmp_path / "does_not_exist_sae"),
            device="cuda",
            dtype="bfloat16",
        )


# ---------------------------------------------------------------------------
# snippets: local-only, graceful degradation
# ---------------------------------------------------------------------------


def test_load_snippets_missing_file_returns_empty_mapping():
    assert tool.load_snippets(Path("/definitely/not/a/real/path.json")) == {}


def test_snippets_display_missing_feature_shows_not_yet_staged_message():
    assert tool.snippets_display({}, 250) == tool.SNIPPETS_NOT_STAGED_MESSAGE


def test_snippets_display_present_feature_shows_text(tmp_path):
    snippets_path = tmp_path / "snippets.json"
    snippets_path.write_text(json.dumps({"250": ["hello world"]}), encoding="utf-8")
    snippets = tool.load_snippets(snippets_path)
    assert tool.snippets_display(snippets, 250) == "hello world"
    assert tool.snippets_display(snippets, 500) == tool.SNIPPETS_NOT_STAGED_MESSAGE


def test_snippets_display_handles_raw_fetch_dict_schema(tmp_path):
    """The schema Engineer 1's real fetch actually produced: a dict per
    entry with 'text'/'maxValue'/'char_len', not a flat string -- same
    shape as gemma_neuronpedia_top16_fulltext.json. A regression test for
    the TypeError this caused before snippets_for_feature learned to
    unwrap it."""
    snippets_path = tmp_path / "snippets.json"
    snippets_path.write_text(
        json.dumps({"250": [{"text": "hello world", "maxValue": 12.3, "char_len": 11}]}),
        encoding="utf-8",
    )
    snippets = tool.load_snippets(snippets_path)
    assert tool.snippets_for_feature(snippets, 250) == ["hello world"]
    assert tool.snippets_display(snippets, 250) == "hello world"


def test_real_snippets_file_loads_and_renders_for_all_nine_features():
    """Integration check against the actual pre-staged file, not a
    fixture -- the exact bug class this guards against (a schema
    mismatch between what the tool assumes and what got fetched) only
    shows up against the real artifact."""
    if not tool.DEFAULT_SNIPPETS_PATH.exists():
        pytest.skip("gemma3_tool_snippets.json not pre-staged in this checkout")
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    snippets = tool.load_snippets(tool.DEFAULT_SNIPPETS_PATH)
    for f in manifest["features"]:
        texts = tool.snippets_for_feature(snippets, f["idx"])
        assert texts, f"feature {f['idx']} has no snippets in the real file"
        assert all(isinstance(t, str) and t for t in texts)
        rendered = tool.snippets_display(snippets, f["idx"])
        assert rendered != tool.SNIPPETS_NOT_STAGED_MESSAGE


# ---------------------------------------------------------------------------
# control feature: fixed, seeded, matches the sweep's own draw
# ---------------------------------------------------------------------------


def test_resolve_control_feature_idx_matches_sweep_default_seed():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    control_idx = tool.resolve_control_feature_idx(sweep, manifest, control_rng_seed=1337)

    exclude = (
        {f["idx"] for f in sweep.FEATURES}
        | {f["idx"] for f in sweep.OPTIONAL_FEATURES}
        | sweep.REJECTED_FEATURE_IDXS
    )
    expected = sweep.pick_control_feature_idx(exclude=exclude, control_rng_seed=1337, d_sae=sweep.WIDTH)
    assert control_idx == expected
    assert control_idx not in {f["idx"] for f in manifest["features"]}


def test_resolve_control_feature_idx_is_deterministic():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    a = tool.resolve_control_feature_idx(sweep, manifest, control_rng_seed=42)
    b = tool.resolve_control_feature_idx(sweep, manifest, control_rng_seed=42)
    assert a == b


# ---------------------------------------------------------------------------
# sample-max-proxy caveat must be in the rendered UI metadata
# ---------------------------------------------------------------------------


def test_feature_metadata_markdown_contains_sample_max_proxy_caveat():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    feature = tool.feature_by_idx(manifest, 250)
    md = tool.feature_metadata_markdown(feature)
    assert sweep.MAX_ACT_APPROX_CAVEAT in md
    assert "sample-max proxy" in md
    assert "corpus max" in md


def test_manifest_top_level_caveat_matches_sweep_constant():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    assert manifest["maxActApprox_caveat"] == sweep.MAX_ACT_APPROX_CAVEAT


def test_build_ui_header_renders_the_sample_max_proxy_caveat():
    """The header markdown build_ui() actually feeds into a gr.Markdown
    component must carry the caveat too, not just the per-feature panel."""
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    control_idx = tool.resolve_control_feature_idx(sweep, manifest, control_rng_seed=1337)

    class _StubBundle:
        pass

    demo = tool.build_ui(_StubBundle(), manifest, {}, control_idx, 1337)
    try:
        rendered = json.dumps(demo.get_config_file())
    finally:
        demo.close()
    assert "sample-max proxy" in rendered
    assert "corpus max" in rendered
