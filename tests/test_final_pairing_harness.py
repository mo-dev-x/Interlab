"""Pure-plumbing tests for scripts/legacy/final_pairing_harness.py: the
diagnostic trace wrapper, the QwenScopeSAE duck-typed loader, and the raw-HF
hook adapter. CPU-only torch, small synthetic tensors, no GPU, no real
weights, no network -- these prove the diagnostic and loading PLUMBING
works, not that a live GPU run succeeds (that requires a real allocation
and real weights this investigation did not have access to).
"""

from __future__ import annotations

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


def _fake_qwen_state_dict(d_model=6, d_sae=10, include_b_dec=False):
    state_dict = {
        "W_enc": torch.randn(d_sae, d_model),
        "b_enc": torch.randn(d_sae),
        "W_dec": torch.randn(d_model, d_sae),
    }
    if include_b_dec:
        state_dict["b_dec"] = torch.randn(d_model)
    return state_dict


def test_qwen_scope_sae_shapes_and_topk_sparsity():
    sd = _fake_qwen_state_dict(d_model=6, d_sae=10)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu")
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


def test_qwen_scope_sae_missing_b_dec_defaults_to_zero_and_flags_it():
    sd = _fake_qwen_state_dict(include_b_dec=False)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu")
    assert sae.used_zero_b_dec_default is True
    assert torch.equal(sae.b_dec, torch.zeros_like(sae.b_dec))


def test_qwen_scope_sae_uses_real_b_dec_when_present():
    sd = _fake_qwen_state_dict(include_b_dec=True)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu")
    assert sae.used_zero_b_dec_default is False
    assert torch.equal(sae.b_dec, sd["b_dec"])


def test_qwen_scope_sae_raises_on_missing_required_key():
    sd = _fake_qwen_state_dict()
    del sd["W_dec"]
    with pytest.raises(targets.TargetIdentityMismatch, match="W_dec"):
        harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu")


def test_qwen_scope_sae_works_with_real_make_clamp_hook():
    """The actual point of the duck-type: _make_clamp_hook (imported
    unmodified) must work against QwenScopeSAE exactly as it does against
    sae_lens.SAE or the test suite's own _IdentitySAE."""
    from interplab.interventions.hooks import _make_clamp_hook

    sd = _fake_qwen_state_dict(d_model=6, d_sae=10, include_b_dec=True)
    sae = harness.QwenScopeSAE.from_state_dict(sd, k=3, device="cpu")
    stats: list = []
    hook_fn = _make_clamp_hook(sae, feature_index=0, clamp_value=5.0, positions="all", prompt_lengths=None, stats=stats)
    resid = torch.randn(1, 2, 6)
    out = hook_fn(resid, hook=None)
    assert out.shape == resid.shape
    assert len(stats) == 1
    assert stats[0].delta_norm >= 0.0


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


def test_resolve_qwen_text_decoder_prefers_model_dot_language_model():
    fake = SimpleNamespace(model=SimpleNamespace(language_model="text-decoder-a"))
    assert harness.resolve_qwen_text_decoder(fake) == "text-decoder-a"


def test_resolve_qwen_text_decoder_falls_back_to_direct_attribute():
    fake = SimpleNamespace(language_model="text-decoder-b")
    assert harness.resolve_qwen_text_decoder(fake) == "text-decoder-b"


def test_resolve_qwen_text_decoder_fails_closed_when_neither_present():
    fake = SimpleNamespace(some_other_attr=1)
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
