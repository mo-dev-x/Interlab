"""Pure-plumbing tests for scripts/legacy/final_pairing_harness.py: the
diagnostic trace wrapper, the QwenScopeSAE duck-typed loader, and the raw-HF
hook adapter. CPU-only torch, small synthetic tensors, no GPU, no real
weights, no network -- these prove the diagnostic and loading PLUMBING
works, not that a live GPU run succeeds (that requires a real allocation
and real weights this investigation did not have access to).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_harness as harness  # noqa: E402
import final_pairing_targets as targets  # noqa: E402


class _IdentitySAE:
    """Same duck-typed convention as tests/test_gemma3_tool.py's
    _IdentitySAE -- _make_clamp_hook only ever calls .encode()/.decode()."""

    def encode(self, x):
        return x.clone()

    def decode(self, feats):
        return feats.clone()


# ---------------------------------------------------------------------------
# wrap_hook_with_diagnostics
# ---------------------------------------------------------------------------


def _passthrough_inner_hook(resid, hook):
    return resid


def _zeroing_inner_hook(feature_index):
    def inner(resid, hook):
        out = resid.clone()
        out[..., feature_index] = 0.0
        return out

    return inner


def test_wrap_hook_classifies_first_call_prefill_and_later_calls_decode():
    trace: list = []
    wrapped = harness.wrap_hook_with_diagnostics(
        _passthrough_inner_hook, sae=_IdentitySAE(), feature_index=0, mode="ablate",
        dose_or_raw_label="ablate (always 0.0 regardless of dose)", calibration_input=None,
        resolved_absolute_target=0.0, hook_name="blocks.31.hook_resid_post", trace_out=trace,
    )
    prefill_resid = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4)  # prefill: 3 positions
    decode_resid_1 = torch.ones((1, 1, 4), dtype=torch.float32)  # decode: 1 position
    decode_resid_2 = torch.full((1, 1, 4), 2.0)

    wrapped(prefill_resid, hook=None)
    wrapped(decode_resid_1, hook=None)
    wrapped(decode_resid_2, hook=None)

    assert [t.call_classification for t in trace] == ["prefill", "decode", "decode"]
    assert [t.call_index for t in trace] == [0, 1, 2]


def test_wrap_hook_is_pure_observation_never_alters_output():
    """Preserving f355126's accepted findings depends on this: the
    diagnostic wrapper must be functionally transparent."""
    trace: list = []
    wrapped = harness.wrap_hook_with_diagnostics(
        _zeroing_inner_hook(feature_index=1), sae=_IdentitySAE(), feature_index=1, mode="ablate",
        dose_or_raw_label="ablate (always 0.0 regardless of dose)", calibration_input=None,
        resolved_absolute_target=0.0, hook_name="blocks.31.hook_resid_post", trace_out=trace,
    )
    resid = torch.arange(8, dtype=torch.float32).reshape(1, 2, 4)
    direct_output = _zeroing_inner_hook(feature_index=1)(resid, hook=None)
    wrapped_output = wrapped(resid, hook=None)
    assert torch.equal(direct_output, wrapped_output)


def test_wrap_hook_captures_all_required_trace_fields():
    trace: list = []
    wrapped = harness.wrap_hook_with_diagnostics(
        _zeroing_inner_hook(feature_index=2), sae=_IdentitySAE(), feature_index=2, mode="steer",
        dose_or_raw_label="dose_multiple=2.0 x calibration_value=10.0", calibration_input=10.0,
        resolved_absolute_target=20.0, hook_name="blocks.31.hook_resid_post", trace_out=trace,
    )
    resid = torch.arange(8, dtype=torch.float32).reshape(1, 2, 4)
    wrapped(resid, hook=None)

    t = trace[0]
    assert t.requested_mode == "steer"
    assert t.requested_dose_or_raw == "dose_multiple=2.0 x calibration_value=10.0"
    assert t.calibration_input == 10.0
    assert t.resolved_absolute_target == 20.0
    assert t.backend_received_value == 20.0
    assert t.assigned_feature_value == 20.0
    assert t.hook_name == "blocks.31.hook_resid_post"
    assert t.hooked_tensor_shape == (1, 2, 4)
    # identity SAE + zeroing hook: feature 2's last-position activation was
    # nonzero going in, zero coming out.
    assert t.feature_activation_before == pytest.approx(resid[0, -1, 2].item())
    assert t.feature_activation_after == pytest.approx(0.0)
    assert t.residual_delta_norm > 0.0
    assert t.residual_norm == pytest.approx(resid.norm().item())


def test_wrap_hook_masked_call_shows_zero_delta_and_unchanged_activation():
    """A masked (no-op) call under positions="generated_only" -- inner_hook_fn
    passed straight through, per _make_clamp_hook's own early-return
    contract -- must show delta 0 and before==after, the documented
    generated_only first-call signature, not a broken hook."""
    trace: list = []
    wrapped = harness.wrap_hook_with_diagnostics(
        _passthrough_inner_hook, sae=_IdentitySAE(), feature_index=0, mode="steer",
        dose_or_raw_label="dose_multiple=2.0 x calibration_value=10.0", calibration_input=10.0,
        resolved_absolute_target=20.0, hook_name="blocks.31.hook_resid_post", trace_out=trace,
    )
    resid = torch.arange(8, dtype=torch.float32).reshape(1, 2, 4)
    wrapped(resid, hook=None)
    t = trace[0]
    assert t.residual_delta_norm == pytest.approx(0.0)
    assert t.feature_activation_before == pytest.approx(t.feature_activation_after)


# ---------------------------------------------------------------------------
# find_first_disappearance_boundary / mechanical_verdict
# ---------------------------------------------------------------------------


def _fake_trace(call_index: int, classification: str, delta_norm: float) -> harness.InterventionTrace:
    return harness.InterventionTrace(
        call_index=call_index, call_classification=classification, requested_mode="steer",
        requested_dose_or_raw="x", calibration_input=1.0, resolved_absolute_target=2.0,
        backend_received_value=2.0, hook_name="h", hooked_tensor_shape=(1, 1, 4),
        feature_activation_before=0.0, assigned_feature_value=2.0, feature_activation_after=1.0,
        residual_delta_norm=delta_norm, residual_norm=1.0,
    )


def test_boundary_skips_accepted_generated_only_first_call_noop():
    trace = [_fake_trace(0, "prefill", 0.0), _fake_trace(1, "decode", 5.0), _fake_trace(2, "decode", 5.0)]
    assert harness.find_first_disappearance_boundary(trace, positions="generated_only") is None


def test_boundary_finds_real_disappearance_after_prefill():
    trace = [_fake_trace(0, "prefill", 0.0), _fake_trace(1, "decode", 5.0), _fake_trace(2, "decode", 0.0)]
    boundary = harness.find_first_disappearance_boundary(trace, positions="generated_only")
    assert boundary.call_index == 2


def test_boundary_does_not_skip_first_call_under_positions_all():
    """Under positions="all" nothing should ever be masked -- a zero delta
    at call 0 IS a real boundary, not the generated_only exemption."""
    trace = [_fake_trace(0, "prefill", 0.0), _fake_trace(1, "decode", 5.0)]
    boundary = harness.find_first_disappearance_boundary(trace, positions="all")
    assert boundary.call_index == 0


def test_mechanical_verdict_confirms_nonzero_and_counts_calls():
    trace = [_fake_trace(0, "prefill", 0.0), _fake_trace(1, "decode", 5.0), _fake_trace(2, "decode", 3.0)]
    verdict = harness.mechanical_verdict(trace, positions="generated_only")
    assert verdict["hook_invocation_count"] == 3
    assert verdict["prefill_call_count"] == 1
    assert verdict["decode_call_count"] == 2
    assert verdict["nonzero_steer_confirmed"] is True
    assert verdict["first_disappearance_boundary"] is None


def test_mechanical_verdict_rejects_when_a_real_call_shows_zero_delta():
    trace = [_fake_trace(0, "prefill", 0.0), _fake_trace(1, "decode", 0.0)]
    verdict = harness.mechanical_verdict(trace, positions="generated_only")
    assert verdict["nonzero_steer_confirmed"] is False
    assert verdict["first_disappearance_boundary"]["call_index"] == 1


# ---------------------------------------------------------------------------
# QwenScopeSAE
# ---------------------------------------------------------------------------


def _fake_qwen_state_dict(d_model=6, d_sae=10, include_b_dec=True):
    """include_b_dec defaults to True: orchestrator review, 2026-08-11 --
    the release's own checkpoint contract lists b_dec as present, so a
    valid state dict includes it by default now; tests that need to prove
    the missing-key rejection pass include_b_dec=False explicitly."""
    state_dict = {
        "W_enc": torch.randn(d_sae, d_model),
        "b_enc": torch.randn(d_sae),
        "W_dec": torch.randn(d_model, d_sae),
    }
    if include_b_dec:
        state_dict["b_dec"] = torch.randn(d_model)
    return state_dict


class _TinyTargetForShapeTests:
    """A TargetPairing-shaped stand-in with small d_model/d_sae/k so tests
    don't need real 5120x81920 tensors -- construction validation in
    QwenScopeSAE.from_state_dict is generic over the target passed in."""

    expected_hidden_dim = 6
    expected_d_sae = 10
    expected_k = 3
    name = "tiny-test-target"


_TINY_TARGET = _TinyTargetForShapeTests()


def test_qwen_scope_sae_shapes_and_topk_sparsity():
    sd = _fake_qwen_state_dict(d_model=6, d_sae=10)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)
    assert sae.d_in == 6
    assert sae.d_sae == 10
    x = torch.randn(1, 2, 6)
    feats = sae.encode(x)
    assert feats.shape == (1, 2, 10)
    # top-k=3: exactly 3 nonzero entries per position (relu'd values are
    # generically distinct from zero for random input).
    nonzero_counts = (feats != 0.0).sum(dim=-1)
    assert torch.all(nonzero_counts <= 3)
    recon = sae.decode(feats)
    assert recon.shape == x.shape


def test_qwen_scope_sae_rejects_missing_b_dec():
    """Orchestrator review, 2026-08-11: the release's own checkpoint
    contract lists b_dec as present -- a missing b_dec now fails closed
    rather than silently defaulting to a zero bias (used_zero_b_dec_default
    is removed entirely). This test fails against the pre-fix code, which
    would have accepted this state dict and set a zero default instead."""
    sd = _fake_qwen_state_dict(include_b_dec=False)
    with pytest.raises(targets.TargetIdentityMismatch, match="b_dec"):
        harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)


def test_qwen_scope_sae_uses_real_b_dec_when_present():
    sd = _fake_qwen_state_dict(include_b_dec=True)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)
    assert torch.equal(sae.b_dec, sd["b_dec"])
    assert not hasattr(sae, "used_zero_b_dec_default")


@pytest.mark.parametrize("missing_key", ["W_enc", "b_enc", "W_dec", "b_dec"])
def test_qwen_scope_sae_raises_on_missing_required_key(missing_key):
    sd = _fake_qwen_state_dict()
    del sd[missing_key]
    with pytest.raises(targets.TargetIdentityMismatch, match=missing_key):
        harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)


def test_qwen_scope_sae_works_with_real_make_clamp_hook():
    """The actual point of the duck-type: _make_clamp_hook (imported
    unmodified) must work against QwenScopeSAE exactly as it does against
    sae_lens.SAE or the test suite's own _IdentitySAE."""
    from interplab.interventions.hooks import _make_clamp_hook

    sd = _fake_qwen_state_dict(d_model=6, d_sae=10, include_b_dec=True)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)
    stats: list = []
    hook_fn = _make_clamp_hook(sae, feature_index=0, clamp_value=5.0, positions="all", prompt_lengths=None, stats=stats)
    resid = torch.randn(1, 2, 6)
    out = hook_fn(resid, hook=None)
    assert out.shape == resid.shape
    assert len(stats) == 1
    assert stats[0].delta_norm >= 0.0


def test_qwen_scope_sae_from_state_dict_rejects_mismatched_k():
    sd = _fake_qwen_state_dict(d_model=6, d_sae=10)
    with pytest.raises(targets.TargetIdentityMismatch, match="structural"):
        harness.QwenScopeSAE.from_state_dict(sd, k=5, device="cpu", target=_TINY_TARGET)


def test_qwen_scope_sae_from_state_dict_rejects_mismatched_shapes():
    """W_enc built for the wrong d_model must fail closed at construction,
    not surface as a cryptic torch shape-mismatch error three calls later."""
    sd = _fake_qwen_state_dict(d_model=99, d_sae=10)
    with pytest.raises(targets.TargetIdentityMismatch):
        harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu", target=_TINY_TARGET)


# ---------------------------------------------------------------------------
# _capture_sae_download_paths / _restore_sae_download_paths -- the SAE
# provenance proof (orchestrator review defect: validated sae_path and then
# let SAE.from_pretrained resolve an independent cached revision with no
# check the two agreed).
# ---------------------------------------------------------------------------


def test_capture_sae_download_paths_records_calls_and_restores_cleanly(monkeypatch):
    import sae_lens.loading.pretrained_sae_loaders as psl

    def fake_hf_hub_download(repo_id, filename, **kwargs):
        return f"/fake/cache/{repo_id}/{filename}"

    monkeypatch.setattr(psl, "hf_hub_download", fake_hf_hub_download)
    captured: list = []
    saved_original = harness._capture_sae_download_paths(captured)
    try:
        result = psl.hf_hub_download(repo_id="google/gemma-scope-2-12b-it", filename="cfg.json")
    finally:
        harness._restore_sae_download_paths(saved_original)

    assert result == "/fake/cache/google/gemma-scope-2-12b-it/cfg.json"
    assert captured == [result]
    # restored to whatever was patched in immediately before capture, not
    # some hardcoded "real" function -- proves restore is a true pop, not a
    # guess at what "original" means.
    assert psl.hf_hub_download is fake_hf_hub_download


def test_capture_sae_download_paths_records_multiple_calls(monkeypatch):
    import sae_lens.loading.pretrained_sae_loaders as psl

    monkeypatch.setattr(psl, "hf_hub_download", lambda repo_id, filename, **k: f"{repo_id}/{filename}")
    captured: list = []
    saved_original = harness._capture_sae_download_paths(captured)
    try:
        psl.hf_hub_download(repo_id="r", filename="a.json")
        psl.hf_hub_download(repo_id="r", filename="b.safetensors")
    finally:
        harness._restore_sae_download_paths(saved_original)

    assert captured == ["r/a.json", "r/b.safetensors"]


# ---------------------------------------------------------------------------
# load_qwen_target -- the auto-class route orchestrator review (2026-08-11)
# realigned with Tamia's actual transformers==5.14.1 and the official
# Qwen-Scope release's own application: AutoModelForCausalLM ->
# Qwen3_5ForCausalLM, hooking model.model.layers[layer] directly, not the
# multimodal AutoModelForImageTextToText -> Qwen3_5ForConditionalGeneration
# route this harness used previously.
#
# The three fake classes below are DELIBERATELY named exactly like the real
# classes they stand in for (not _Fake-prefixed) so that
# type(obj).__name__ genuinely equals what targets.validate_runtime_class
# checks against -- exercising that check for real rather than bypassing it
# with a differently-named double.
# ---------------------------------------------------------------------------


class _FakeQwenTextModel:
    """Stands in for Qwen3_5TextModel -- .layers is its own list directly,
    no .language_model indirection (that nesting is specific to the
    multimodal Qwen3_5ForConditionalGeneration class this harness no
    longer loads)."""

    def __init__(self):
        self.config = SimpleNamespace(hidden_size=5120)
        self.layers = [SimpleNamespace() for _ in range(64)]


class Qwen3_5Model:
    """Stands in for what transformers.AutoModel actually dispatches
    "qwen3_5" to -- has NO GenerationMixin/.generate() (verified locally
    against the installed transformers' own MODEL_MAPPING_NAMES). If
    load_qwen_target used AutoModel, this is what it would get back."""

    def __init__(self):
        self.language_model = _FakeQwenTextModel()

    def eval(self):
        return self

    def to(self, device):
        return self


class Qwen3_5ForConditionalGeneration:
    """Stands in for what transformers.AutoModelForImageTextToText
    dispatches "qwen3_5" to -- the multimodal class this harness no longer
    loads. Has .generate() but the WRONG decoder-attribute shape
    (.model.language_model.layers, not .model.layers) for the
    now-expected causal-LM route."""

    def __init__(self):
        self.model = SimpleNamespace(language_model=_FakeQwenTextModel())

    def eval(self):
        return self

    def to(self, device):
        return self

    def generate(self, **kwargs):
        return "generated"


class Qwen3_5ForCausalLM:
    """Stands in for what transformers.AutoModelForCausalLM dispatches
    "qwen3_5" to on Tamia's actual transformers==5.14.1 (MODEL_FOR_CAUSAL_LM_
    MAPPING_NAMES) -- independently re-confirmed against this machine's own
    installed transformers==5.12.1, which already has the same dispatch.
    Has .generate() (GenerationMixin) and .model.layers reachable directly,
    matching the official Qwen-Scope release's own application."""

    def __init__(self):
        self.model = _FakeQwenTextModel()

    def eval(self):
        return self

    def to(self, device):
        return self

    def generate(self, **kwargs):
        return "generated"


class _FakeSaeForQwenLoadTest:
    d_in = 5120
    d_sae = 81920
    k = 50


def test_load_qwen_target_uses_auto_model_for_causal_lm_not_image_text_to_text(monkeypatch, tmp_path):
    """The exact defect this review fixes: a prior version called
    transformers.AutoModelForImageTextToText (dispatch: the multimodal
    Qwen3_5ForConditionalGeneration). Tamia's actual transformers==5.14.1
    (and this machine's installed 5.12.1, independently confirmed)
    dispatches model_type="qwen3_5" through AutoModelForCausalLM to
    Qwen3_5ForCausalLM instead -- the same route the official Qwen-Scope
    release's own application uses. This test fails against the pre-fix
    code (AutoModelForCausalLM would never be called at all) and passes
    against the corrected loader."""
    import transformers

    monkeypatch.setattr(
        transformers.AutoModelForCausalLM, "from_pretrained",
        staticmethod(lambda path, **kwargs: Qwen3_5ForCausalLM()),
    )

    def _must_not_be_used(name):
        def _raise(*args, **kwargs):
            raise AssertionError(f"transformers.{name} must not be used for Qwen3.5 anymore.")

        return _raise

    monkeypatch.setattr(
        transformers.AutoModelForImageTextToText, "from_pretrained",
        staticmethod(_must_not_be_used("AutoModelForImageTextToText")),
    )
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", staticmethod(_must_not_be_used("AutoModel")))
    monkeypatch.setattr(
        harness.QwenScopeSAE, "from_layer_file",
        staticmethod(lambda path, *, k, device, target: _FakeSaeForQwenLoadTest()),
    )
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    model_dir = tmp_path / "qwen_model"
    model_dir.mkdir()
    sae_file = tmp_path / "layer31.sae.pt"
    sae_file.write_bytes(b"fake")

    hf_model, _text_decoder, _sae, _hook_identifier, provenance = harness.load_qwen_target(
        model_dir, sae_file, layer=31, expected_model_revision="rev1", expected_sae_revision="rev1",
    )

    assert hasattr(hf_model, "generate"), "load_qwen_target must return a model with a callable .generate()"
    assert callable(hf_model.generate)
    assert provenance["model"]["actual_class"] == "Qwen3_5ForCausalLM"
    assert provenance["model"]["selected_auto_class"] == "AutoModelForCausalLM"
    assert provenance["model"]["decoder_attribute_path"] == "model.layers"
    assert isinstance(provenance["model"]["transformers_version"], str)
    assert provenance["layer"]["engineering_layer"] == 31
    assert provenance["layer"]["engineering_only"] is True
    assert provenance["sae"]["k"] == 50
    assert "used_zero_b_dec_default" not in provenance["sae"]


def test_load_qwen_target_rejects_when_auto_model_for_causal_lm_returns_wrong_class(monkeypatch, tmp_path):
    """Proves targets.validate_runtime_class is actually wired into
    load_qwen_target -- not merely defined and separately unit-tested."""
    import transformers

    monkeypatch.setattr(
        transformers.AutoModelForCausalLM, "from_pretrained",
        staticmethod(lambda path, **kwargs: Qwen3_5Model()),
    )
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    model_dir = tmp_path / "qwen_model"
    model_dir.mkdir()
    sae_file = tmp_path / "layer31.sae.pt"
    sae_file.write_bytes(b"fake")

    with pytest.raises(targets.TargetIdentityMismatch, match="Qwen3_5ForCausalLM"):
        harness.load_qwen_target(
            model_dir, sae_file, layer=31, expected_model_revision="rev1", expected_sae_revision="rev1",
        )


def test_load_qwen_target_rejects_missing_generate(monkeypatch, tmp_path):
    """Proves targets.validate_has_callable_generate is actually wired into
    load_qwen_target, independent of validate_runtime_class -- a class that
    happens to be named correctly but has no .generate() must still fail
    closed rather than crash deep inside the generation call later."""
    import transformers

    class Qwen3_5ForCausalLM:  # local shadow: right name, deliberately no .generate()
        def __init__(self):
            self.model = _FakeQwenTextModel()

        def eval(self):
            return self

        def to(self, device):
            return self

    monkeypatch.setattr(
        transformers.AutoModelForCausalLM, "from_pretrained",
        staticmethod(lambda path, **kwargs: Qwen3_5ForCausalLM()),
    )
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    model_dir = tmp_path / "qwen_model"
    model_dir.mkdir()
    sae_file = tmp_path / "layer31.sae.pt"
    sae_file.write_bytes(b"fake")

    with pytest.raises(targets.TargetIdentityMismatch, match="generate"):
        harness.load_qwen_target(
            model_dir, sae_file, layer=31, expected_model_revision="rev1", expected_sae_revision="rev1",
        )


def test_load_qwen_target_rejects_layer_filename_mismatch(monkeypatch, tmp_path):
    import transformers

    monkeypatch.setattr(
        transformers.AutoModelForCausalLM, "from_pretrained",
        staticmethod(lambda path, **kwargs: Qwen3_5ForCausalLM()),
    )
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    model_dir = tmp_path / "qwen_model"
    model_dir.mkdir()
    sae_file = tmp_path / "layer31.sae.pt"  # filename says layer 31
    sae_file.write_bytes(b"fake")

    with pytest.raises(targets.TargetIdentityMismatch, match="layer 31"):
        harness.load_qwen_target(
            model_dir, sae_file, layer=40, expected_model_revision="rev1", expected_sae_revision="rev1",
        )  # --qwen-layer=40 disagrees with the file name


# ---------------------------------------------------------------------------
# raw-HF hook adapter + text-decoder resolution
# ---------------------------------------------------------------------------


class _TinyLayer(torch.nn.Module):
    def forward(self, x):
        return x * 2.0


def test_register_qwen_raw_hook_bridges_to_make_clamp_hook_contract():
    """register_forward_hook's (module, args, output) must reach
    _make_clamp_hook-style (resid, hook) -> resid closures unchanged, and a
    replacement tensor returned from the hook must actually replace the
    module's output -- the entire point of the adapter."""
    layer = _TinyLayer()
    seen = {}

    def fake_inner_hook(resid, hook):
        seen["resid"] = resid
        return resid + 100.0

    handle = harness.register_qwen_raw_hook(layer, fake_inner_hook)
    try:
        x = torch.ones(1, 3)
        result = layer(x)
    finally:
        handle.remove()

    assert torch.equal(seen["resid"], x * 2.0)  # the layer's real output, before the hook's replacement
    assert torch.equal(result, x * 2.0 + 100.0)  # the hook's replacement is what the caller actually sees


class _TupleReturningLayer(torch.nn.Module):
    """Simulates a decoder layer whose forward() returns a tuple -- the
    opposite of what modeling_qwen3_5.py's own Qwen3_5DecoderLayer.forward()
    was verified to return (a plain tensor). Proves the orchestrator
    review's new output-type check fails clearly rather than silently
    mishandling a tuple."""

    def forward(self, x):
        return (x * 2.0, None)


def test_register_qwen_raw_hook_fails_closed_on_non_tensor_output():
    layer = _TupleReturningLayer()

    def fake_inner_hook(resid, hook):
        return resid

    handle = harness.register_qwen_raw_hook(layer, fake_inner_hook)
    try:
        with pytest.raises(targets.TargetIdentityMismatch, match="plain tensor"):
            layer(torch.ones(1, 3))
    finally:
        handle.remove()


def test_resolve_qwen_text_decoder_reads_model_dot_layers():
    """Qwen3_5ForCausalLM.model is a Qwen3_5TextModel with its own .layers
    directly -- no .language_model indirection (that nesting is specific to
    the multimodal Qwen3_5ForConditionalGeneration class this harness no
    longer loads)."""
    fake = SimpleNamespace(model=SimpleNamespace(layers=["layer0", "layer1"]))
    assert harness.resolve_qwen_text_decoder(fake) is fake.model


def test_resolve_qwen_text_decoder_fails_closed_when_model_attribute_missing():
    fake = SimpleNamespace(some_other_attr=1)
    with pytest.raises(targets.TargetIdentityMismatch):
        harness.resolve_qwen_text_decoder(fake)


def test_resolve_qwen_text_decoder_fails_closed_on_the_old_multimodal_shape():
    """The multimodal Qwen3_5ForConditionalGeneration's .model is a
    Qwen3_5Model, which has .language_model but no .layers of its own. A
    prior version of this function would have accepted this shape (it
    preferred .model.language_model); the corrected function no longer
    reaches for .language_model at all, so this must now fail closed
    rather than silently returning the wrong object."""
    fake = SimpleNamespace(model=SimpleNamespace(language_model=SimpleNamespace(layers=["x"])))
    with pytest.raises(targets.TargetIdentityMismatch):
        harness.resolve_qwen_text_decoder(fake)


def test_get_qwen_decoder_layer_indexes_layers_list():
    fake_decoder = SimpleNamespace(layers=["layer0", "layer1", "layer2"])
    assert harness.get_qwen_decoder_layer(fake_decoder, 1) == "layer1"


# ---------------------------------------------------------------------------
# resolve_target_value -- reuses gemma3_tool.dose_to_absolute_clamp verbatim,
# preserving f355126's accepted non-positive-clamp guard.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tool_module():
    return harness._load_gemma3_tool()


def test_resolve_target_value_ablate_always_zero(tool_module):
    value, label = harness.resolve_target_value(
        tool_module, mode="ablate", dose_multiple=4.0, calibration_value=99.0, raw_clamp_value=None,
    )
    assert value == 0.0
    assert "ablate" in label


def test_resolve_target_value_steer_from_dose_and_calibration(tool_module):
    value, label = harness.resolve_target_value(
        tool_module, mode="steer", dose_multiple=2.0, calibration_value=10.0, raw_clamp_value=None,
    )
    assert value == pytest.approx(20.0)
    assert "dose_multiple=2.0" in label


def test_resolve_target_value_steer_from_raw_clamp_value(tool_module):
    value, label = harness.resolve_target_value(
        tool_module, mode="steer", dose_multiple=None, calibration_value=None, raw_clamp_value=42.0,
    )
    assert value == 42.0
    assert "raw engineering value" in label


def test_resolve_target_value_rejects_raw_and_dose_together(tool_module):
    with pytest.raises(ValueError, match="mutually exclusive"):
        harness.resolve_target_value(
            tool_module, mode="steer", dose_multiple=2.0, calibration_value=None, raw_clamp_value=42.0,
        )


def test_resolve_target_value_steer_requires_both_dose_and_calibration(tool_module):
    with pytest.raises(ValueError):
        harness.resolve_target_value(
            tool_module, mode="steer", dose_multiple=2.0, calibration_value=None, raw_clamp_value=None,
        )


def test_resolve_target_value_preserves_non_positive_calibration_guard(tool_module):
    """f355126's accepted finding: dose_to_absolute_clamp raises rather
    than silently resolving to a clamp of 0/negative for a non-positive
    calibration value under steer. Must still hold through this new path."""
    with pytest.raises(ValueError, match="non-positive"):
        harness.resolve_target_value(
            tool_module, mode="steer", dose_multiple=2.0, calibration_value=0.0, raw_clamp_value=None,
        )


# ---------------------------------------------------------------------------
# resolve_target_value -- reject zero/negative/NaN/infinite raw STEER values
# (orchestrator review defect: --raw-clamp-value had no validation at all).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0.0, -5.0, float("nan"), float("inf"), float("-inf")])
def test_resolve_target_value_rejects_non_finite_or_non_positive_raw_clamp_value(tool_module, bad_value):
    with pytest.raises(targets.TargetIdentityMismatch):
        harness.resolve_target_value(
            tool_module, mode="steer", dose_multiple=None, calibration_value=None, raw_clamp_value=bad_value,
        )


def test_resolve_target_value_rejects_nan_calibration_value_that_would_slip_past_dose_to_absolute_clamp(tool_module):
    """dose_to_absolute_clamp's own guard is `if max_act_approx <= 0.0`,
    which is False for NaN -- a NaN calibration_value would otherwise
    silently resolve to a NaN clamp. validate_finite_positive on the
    RESOLVED value catches it regardless of which input caused it."""
    with pytest.raises(targets.TargetIdentityMismatch, match="not finite"):
        harness.resolve_target_value(
            tool_module, mode="steer", dose_multiple=2.0, calibration_value=float("nan"), raw_clamp_value=None,
        )


def test_resolve_target_value_ablate_is_never_subject_to_the_positive_check(tool_module):
    # 0.0 is ablate's correct value, not a rejected one.
    value, _ = harness.resolve_target_value(
        tool_module, mode="ablate", dose_multiple=None, calibration_value=None, raw_clamp_value=None,
    )
    assert value == 0.0


# ---------------------------------------------------------------------------
# main() -- proves the Tamia packet's documented JSON schema is what the
# actual CLI entry point writes, not an aspirational description of it.
# ---------------------------------------------------------------------------


class _FakeModelForMainTest:
    cfg = SimpleNamespace(d_model=6)

    def __init__(self):
        self._hook_fn = None

    def to_tokens(self, prompt):
        return torch.zeros((1, 3), dtype=torch.long)

    def hooks(self, fwd_hooks):
        import contextlib

        self._hook_fn = fwd_hooks[0][1]
        return contextlib.nullcontext()

    def generate(self, tokens, **kwargs):
        self._hook_fn(torch.randn(1, 3, 6), hook=None)
        return None


def test_main_gemma_writes_the_documented_json_schema(monkeypatch, tmp_path):
    fake_model = _FakeModelForMainTest()
    fake_sae = _IdentitySAE()
    fake_sae.cfg = SimpleNamespace(d_sae=6, d_in=6)
    fake_provenance = {"target": "gemma-3-12b-it", "model": {}, "sae": {}, "layer": {}}

    monkeypatch.setattr(
        harness, "load_gemma_it_target",
        lambda *a, **k: (fake_model, fake_sae, "blocks.31.hook_resid_post", dict(fake_provenance)),
    )

    out_path = tmp_path / "out.json"
    argv = [
        "--target", "gemma-3-12b-it", "--model-path", "x", "--sae-path", "y",
        "--feature-idx", "0", "--mode", "ablate", "--out", str(out_path),
    ]
    exit_code = harness.main(argv)

    payload = json.loads(out_path.read_text())
    for key in (
        "target", "positions", "requested_mode", "requested_dose_multiple", "requested_calibration_value",
        "requested_raw_clamp_value", "resolved_absolute_target", "dose_or_raw_label", "provenance", "trace",
        "verdict",
    ):
        assert key in payload, f"documented Tamia-packet schema key {key!r} missing from main()'s actual output"
    assert payload["provenance"]["feature_idx"] == 0
    assert payload["verdict"]["hook_invocation_count"] == 1
    assert exit_code in (0, 1)


def test_main_rejects_bad_raw_clamp_value_before_any_loader_is_called(monkeypatch, tmp_path):
    """Acceptance: nonpositive/nonfinite raw STEER values fail BEFORE
    loading weights -- assert the loader is never even reached."""

    def _loader_must_not_be_called(*a, **k):
        raise AssertionError("load_gemma_it_target must not be called when the raw clamp value is invalid")

    monkeypatch.setattr(harness, "load_gemma_it_target", _loader_must_not_be_called)
    argv = [
        "--target", "gemma-3-12b-it", "--model-path", "x", "--sae-path", "y",
        "--feature-idx", "0", "--mode", "steer", "--raw-clamp-value", "0",
        "--out", str(tmp_path / "out.json"),
    ]
    with pytest.raises(targets.TargetIdentityMismatch):
        harness.main(argv)
