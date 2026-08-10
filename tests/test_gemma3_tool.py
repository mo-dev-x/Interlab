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


def test_dose_to_absolute_clamp_rejects_non_positive_max_act_approx_under_steer():
    """A zero or negative maxActApprox (e.g. a manifest entry for a
    checkpoint that hasn't been characterized yet) must not silently
    resolve to clamp_value=0.0 -- that is indistinguishable on screen from
    a real steer request but is actually a no-op generation. This is the
    'Resulting absolute clamp value: 0' failure mode: fail loudly here,
    pointing at the manifest, instead of shipping a vacuous experiment."""
    for bad_max_act_approx in (0.0, -1.0):
        with pytest.raises(ValueError, match="non-positive"):
            tool.dose_to_absolute_clamp("steer", 2.0, bad_max_act_approx)


def test_dose_to_absolute_clamp_ablate_tolerates_non_positive_max_act_approx():
    # ablate's clamp is always 0.0 regardless of max_act_approx, so a dead
    # feature's own (possibly zero) maxActApprox must not raise here --
    # unlike steer, ablate never scales by it.
    assert tool.dose_to_absolute_clamp("ablate", 2.0, 0.0) == 0.0


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


# ---------------------------------------------------------------------------
# (1) sweep-module parameterisation -- _load_sweep_module() must still
# default to gemma3_sweep.py (every test above relies on that), but must
# now also accept an explicit path so this tool can run against a
# different model's adapter.
# ---------------------------------------------------------------------------

QWEN_ADAPTER = REPO_ROOT / "scripts" / "legacy" / "qwen_tool_adapter.py"
SWEEP_CONTRACT_NAMES = (
    "FEATURES",
    "OPTIONAL_FEATURES",
    "REJECTED_FEATURE_IDXS",
    "WIDTH",
    "load_feature_manifest",
    "load_model_and_sae",
    "pick_control_feature_idx",
)


def test_load_sweep_module_default_still_loads_gemma3_sweep():
    default_sweep = tool._load_sweep_module()
    assert default_sweep.WIDTH == 16384
    assert default_sweep.SAE_ID == sweep.SAE_ID


def test_load_sweep_module_accepts_explicit_path_to_same_file():
    explicit = tool._load_sweep_module(tool.DEFAULT_SWEEP_MODULE_PATH)
    assert explicit.WIDTH == sweep.WIDTH


def test_load_sweep_module_can_load_qwen_adapter_and_exposes_full_contract():
    qwen = tool._load_sweep_module(QWEN_ADAPTER)
    for name in SWEEP_CONTRACT_NAMES:
        assert hasattr(qwen, name), f"qwen_tool_adapter.py is missing {name!r}"
    assert qwen.WIDTH == 163840


def test_cli_sweep_module_flag_defaults_to_gemma3_sweep_and_is_overridable():
    default_args = tool.parse_args(["--model-path", "m", "--sae-path", "s"])
    assert Path(default_args.sweep_module) == tool.DEFAULT_SWEEP_MODULE_PATH

    overridden_args = tool.parse_args(
        ["--model-path", "m", "--sae-path", "s", "--sweep-module", str(QWEN_ADAPTER)]
    )
    assert overridden_args.sweep_module == str(QWEN_ADAPTER)


# ---------------------------------------------------------------------------
# (2) position mode -- generate_hooked must default to "generated_only" and
# must compute prompt_lengths from the tokenized prompt itself (not leave
# it None, which is the ED-4 contract failure hooks.py guards against
# inside attach(); this tool calls _make_clamp_hook directly, so the
# equivalent guarantee has to be enforced at the call site here instead).
# ---------------------------------------------------------------------------


class _RecordingStubModel:
    """Stands in for a HookedTransformer: to_tokens returns a fixed-length
    prompt, generate appends a fixed number of new tokens, hooks() is a
    no-op context manager. No torch model, no GPU -- just enough surface
    for generate_hooked/_generate's own control flow to run."""

    def __init__(self, prompt_len: int, n_new_tokens: int):
        self.prompt_len = prompt_len
        self.n_new_tokens = n_new_tokens

    def to_tokens(self, prompt):
        import torch

        return torch.zeros((1, self.prompt_len), dtype=torch.long)

    def generate(self, tokens, **kwargs):
        import torch

        return torch.zeros((1, tokens.shape[1] + self.n_new_tokens), dtype=torch.long)

    def to_string(self, tokens):
        return "stub-completion"

    def hooks(self, fwd_hooks):
        import contextlib

        return contextlib.nullcontext()


class _StubBundleForGenerate:
    sae = "not-a-real-sae"  # never touched: _make_clamp_hook is monkeypatched away
    hook_name = "blocks.0.hook_resid_post"

    def __init__(self, prompt_len: int, n_new_tokens: int = 3):
        self.model = _RecordingStubModel(prompt_len, n_new_tokens)


def test_generate_hooked_defaults_to_generated_only():
    import inspect

    assert inspect.signature(tool.generate_hooked).parameters["positions"].default == "generated_only"
    assert tool.DEFAULT_POSITIONS == "generated_only"


def test_generate_hooked_generated_only_passes_prompt_token_count_as_prompt_lengths(monkeypatch):
    captured = {}

    def fake_make_clamp_hook(sae_obj, feature_index, clamp_value, positions, prompt_lengths, stats):
        captured["positions"] = positions
        captured["prompt_lengths"] = prompt_lengths
        return lambda resid, hook: resid

    monkeypatch.setattr(tool, "_make_clamp_hook", fake_make_clamp_hook)

    bundle = _StubBundleForGenerate(prompt_len=7)
    text, clamp = tool.generate_hooked(
        bundle, "some prompt", seed=0, feature_idx=5, mode="ablate",
        dose_multiple=1.0, max_act_approx=10.0,
    )
    assert text == "stub-completion"
    # ablate clamps to 0.0 regardless of the dose passed (dose_to_absolute_clamp);
    # the dose slot is carried for provenance/seed uniformity only. Asserting it here
    # rather than discarding it -- ruff flagged the unpacked name as unused, which it
    # was, because the invariant it carries had never been checked.
    assert clamp == 0.0
    assert captured["positions"] == "generated_only"
    assert captured["prompt_lengths"] == 7  # NOT None -- this is the ED-4 contract this call site owes


def test_generate_hooked_positions_all_passes_prompt_lengths_none(monkeypatch):
    captured = {}

    def fake_make_clamp_hook(sae_obj, feature_index, clamp_value, positions, prompt_lengths, stats):
        captured["positions"] = positions
        captured["prompt_lengths"] = prompt_lengths
        return lambda resid, hook: resid

    monkeypatch.setattr(tool, "_make_clamp_hook", fake_make_clamp_hook)

    bundle = _StubBundleForGenerate(prompt_len=7)
    tool.generate_hooked(
        bundle, "some prompt", seed=0, feature_idx=5, mode="ablate",
        dose_multiple=1.0, max_act_approx=10.0, positions="all",
    )
    assert captured["positions"] == "all"
    assert captured["prompt_lengths"] is None


def test_generate_hooked_rejects_unknown_positions_mode():
    bundle = _StubBundleForGenerate(prompt_len=7)
    with pytest.raises(ValueError):
        tool.generate_hooked(
            bundle, "some prompt", seed=0, feature_idx=5, mode="ablate",
            dose_multiple=1.0, max_act_approx=10.0, positions="prompt_only_typo",
        )


def test_generate_hooked_logs_hook_diagnostics_at_debug_level(monkeypatch, caplog):
    """generate_hooked() used to build the CallStats list _make_clamp_hook
    populates via its `stats` out-param and then silently discard it --
    the "hook fires every generated token" claim was uncheckable from the
    tool's own output. Verify the fire count and delta_norms are actually
    surfaced now (console/job-log, gated behind --log-level DEBUG), not
    just computed and dropped again under a different name."""
    from dataclasses import dataclass

    @dataclass
    class _FakeCallStats:
        delta_norm: float
        residual_norm: float

    def fake_make_clamp_hook(sae_obj, feature_index, clamp_value, positions, prompt_lengths, stats):
        stats.append(_FakeCallStats(delta_norm=0.0, residual_norm=1.0))  # masked prefill call
        stats.append(_FakeCallStats(delta_norm=5.0, residual_norm=1.5))  # steered decode step
        return lambda resid, hook: resid

    monkeypatch.setattr(tool, "_make_clamp_hook", fake_make_clamp_hook)
    bundle = _StubBundleForGenerate(prompt_len=7)

    with caplog.at_level("DEBUG", logger=tool._LOGGER.name):
        tool.generate_hooked(
            bundle, "some prompt", seed=0, feature_idx=5, mode="steer",
            dose_multiple=2.0, max_act_approx=10.0,
        )

    assert "clamp_value=20.0" in caplog.text
    assert "hook fired 2 time(s), 1 with a nonzero delta_norm" in caplog.text
    assert "delta_norm=5.000000" in caplog.text


def test_generate_hooked_diagnostics_silent_below_debug_level(monkeypatch, caplog):
    def fake_make_clamp_hook(sae_obj, feature_index, clamp_value, positions, prompt_lengths, stats):
        return lambda resid, hook: resid

    monkeypatch.setattr(tool, "_make_clamp_hook", fake_make_clamp_hook)
    bundle = _StubBundleForGenerate(prompt_len=7)

    with caplog.at_level("WARNING", logger=tool._LOGGER.name):
        tool.generate_hooked(
            bundle, "some prompt", seed=0, feature_idx=5, mode="steer",
            dose_multiple=2.0, max_act_approx=10.0,
        )
    assert caplog.text == ""


class _IdentitySAE:
    """Minimal duck-typed stand-in for sae_lens.SAE. _make_clamp_hook only
    ever calls .encode()/.decode() on the object gemma3_tool.py passes it
    (gemma3_tool.py passes bundle.sae straight through, unlike attach(),
    which wraps it in _fp32_copy() first) -- an identity map over
    encode/decode is enough to exercise the real, unmodified hook without
    needing sae_lens's own config machinery."""

    def encode(self, x):
        return x.clone()

    def decode(self, feats):
        return feats.clone()


def test_generate_hooked_generated_only_prompt_lengths_actually_masks_prompt_positions():
    """End-to-end check that positions="generated_only" really does leave
    prompt positions untouched, using the real _make_clamp_hook (imported,
    never redefined) -- not just checking that the right string gets passed
    around."""
    import contextlib

    import torch

    d_in = 4
    fake_sae = _IdentitySAE()
    captured = {}

    def fake_generate(bundle, prompt, seed, max_new_tokens, hook_fn=None, tokens=None):
        # 3 prompt positions + 2 generated positions, batch of 1.
        resid = torch.arange(5 * d_in, dtype=torch.float32).reshape(1, 5, d_in)
        with contextlib.nullcontext():
            out = hook_fn(resid, None) if hook_fn is not None else resid
        captured["resid_in"] = resid
        captured["resid_out"] = out
        return "stub"

    class RecordingBundle(_StubBundleForGenerate):
        sae = fake_sae

    orig_generate = tool._generate
    try:
        tool._generate = fake_generate
        bundle = RecordingBundle(prompt_len=3)
        tool.generate_hooked(
            bundle, "abc", seed=0, feature_idx=0, mode="ablate",
            dose_multiple=1.0, max_act_approx=10.0, positions="generated_only",
        )
    finally:
        tool._generate = orig_generate

    resid_in = captured["resid_in"]
    resid_out = captured["resid_out"]
    # Ablating feature 0 zeroes that identity-decoder coordinate wherever the
    # hook actually applies. Prompt positions (0, 1, 2) must be bit-identical
    # to the input; only generated positions (3, 4) may differ.
    assert torch.equal(resid_out[:, :3, :], resid_in[:, :3, :])
    assert not torch.equal(resid_out[:, 3:, :], resid_in[:, 3:, :])


# ---------------------------------------------------------------------------
# (3) dose grid -- doses 8 and 16 are pre-registered (scripts/
# analyze_gemma3_sweep.py) as uninformative-by-saturation. They stay
# selectable, but must be visibly labelled as such, never silently dropped.
# ---------------------------------------------------------------------------


def test_dose_grid_still_includes_the_declared_uninformative_doses():
    analyzer = tool._load_analyzer_module()
    for d in analyzer.DECLARED_UNINFORMATIVE_DOSES:
        assert d in tool.DOSE_GRID, f"dose {d} must stay selectable, not be removed"


def test_dose_dropdown_choices_labels_uninformative_doses_and_leaves_informative_ones_plain():
    analyzer = tool._load_analyzer_module()
    choices = tool.dose_dropdown_choices(analyzer)
    assert {value for _label, value in choices} == {str(d) for d in tool.DOSE_GRID}
    label_by_value = {value: label for label, value in choices}
    for d in analyzer.DECLARED_UNINFORMATIVE_DOSES:
        assert "uninformative-by-saturation" in label_by_value[str(d)]
    for d in analyzer.INFORMATIVE_DOSES:
        assert "uninformative-by-saturation" not in label_by_value[str(d)]


def test_build_ui_renders_dose_uninformative_caveat_and_positions_disclosure():
    manifest = tool.load_manifest(tool.DEFAULT_MANIFEST_PATH, sweep)
    control_idx = tool.resolve_control_feature_idx(sweep, manifest, control_rng_seed=1337)

    class _StubBundle:
        pass

    demo = tool.build_ui(_StubBundle(), manifest, {}, control_idx, 1337)
    try:
        rendered = json.dumps(demo.get_config_file())
    finally:
        demo.close()
    assert "uninformative-by-saturation" in rendered
    assert "generated_only" in rendered
    assert "This tool defaults to" in rendered  # PUBLISHED_NUMBERS_POSITIONS_NOTE
