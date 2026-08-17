"""Tests for scripts/final_pairing/group_intervention.py.

Two layers, deliberately:

1. SYNTHETIC. A tiny SAE with an untied random decoder, where every
   arithmetic claim -- the exact injected delta, linearity in alpha,
   additivity over members, and the closed form for the gap between the
   two ablation mechanisms -- is checkable to floating-point tolerance
   with no model weights at all.

2. REAL, ON CPU. The repository's own pinned fixtures: a real `sae_lens`
   TopK SAE (`tests/fixtures/tiny_sae`, d_in=64, d_sae=256, hook
   `blocks.1.hook_resid_post`) hooked into a real
   `transformer_lens.HookedTransformer` (`tests/fixtures/tiny_model`)
   through the real `model.hooks(...)` path, with real
   `model.generate(...)`. The firing counts, the prefill/decode call
   pattern, and the bit-identity of the control arms are measured on that
   real path, not on a mock of it.

No Gemma-3-12B-it / Qwen3.5-27B weights and no GPU exist on any machine
used in this investigation, so what is NOT covered here is enumerated in
`group_intervention.UNEXERCISED_WITHOUT_GPU` and asserted to be non-empty
by `test_unexercised_paths_are_declared` -- an absent-coverage list that
quietly emptied itself would be worse than none.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import group_intervention as gi  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# Synthetic fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def synthetic_sae() -> gi._SyntheticSAE:
    return gi._SyntheticSAE()


@pytest.fixture
def synthetic_residual() -> torch.Tensor:
    torch.manual_seed(4242)
    return torch.randn(2, 5, 16) * 3.0


GROUP = (gi.GroupMember(3, 1.0), gi.GroupMember(7, 0.5), gi.GroupMember(11, 2.0))


def _expected_direction(sae, members) -> torch.Tensor:
    w_dec = gi.resolve_decoder_matrix(sae).to(torch.float32)
    return sum(m.weight * w_dec[m.feature_index] for m in members)


def _apply(sae, spec, residual):
    ledger = gi.FiringLedger()
    hook_fn, resolved = gi.build_group_hook(sae, spec, ledger=ledger)
    return hook_fn(residual), ledger, resolved


# ---------------------------------------------------------------------------
# CONTROL LAYER -- the refusals. These come first on purpose: a harness whose
# failure cases are untested is a harness whose successes mean nothing.
# ---------------------------------------------------------------------------


def test_out_of_range_feature_raises_and_does_not_shrink_the_group(synthetic_sae):
    """The named defect: a five-feature group that silently becomes three."""
    spec = gi.GroupSpec(
        kind="amplify",
        members=(gi.GroupMember(3), gi.GroupMember(7), gi.GroupMember(9999)),
        alpha=1.0,
    )
    with pytest.raises(gi.FeatureNotInSAE) as excinfo:
        gi.resolve_group(synthetic_sae, spec)
    assert "9999" in str(excinfo.value)
    assert spec.member_count == 3, "the spec itself must be unchanged by the refusal"


def test_out_of_range_refusal_is_not_masked_by_a_missing_hook_name(synthetic_sae):
    """Ordering matters: the membership refusal must reach the caller even
    when the SAE would also fail hook-name resolution."""

    class _NoHookName:
        W_dec = synthetic_sae.W_dec
        b_dec = synthetic_sae.b_dec

    with pytest.raises(gi.FeatureNotInSAE):
        gi.resolve_group(_NoHookName(), gi.GroupSpec(kind="amplify", members=(gi.GroupMember(9999),)))


def test_duplicate_member_raises(synthetic_sae):
    with pytest.raises(gi.InvalidGroupSpec, match="more than once"):
        gi.GroupSpec(kind="amplify", members=(gi.GroupMember(3), gi.GroupMember(3)))


def test_negative_feature_index_raises():
    with pytest.raises(gi.InvalidGroupSpec, match="non-negative"):
        gi.GroupMember(-1)


def test_non_integer_feature_index_raises():
    with pytest.raises(gi.InvalidGroupSpec, match="must be an int"):
        gi.GroupMember(3.0)  # type: ignore[arg-type]


def test_non_finite_alpha_and_weight_raise():
    with pytest.raises(gi.InvalidGroupSpec, match="alpha must be finite"):
        gi.GroupSpec(kind="amplify", members=GROUP, alpha=float("nan"))
    with pytest.raises(gi.InvalidGroupSpec, match="weight must be finite"):
        gi.GroupMember(3, float("inf"))


def test_ablation_mechanism_has_no_default():
    """The two mechanisms differ by the reconstruction error; picking one by
    default would settle a scientific question with an import."""
    with pytest.raises(gi.InvalidGroupSpec, match="requires an explicit ablation_mechanism"):
        gi.GroupSpec(kind="ablate", members=GROUP, alpha=1.0)


def test_ablation_mechanism_rejected_on_non_ablate_kinds():
    with pytest.raises(gi.InvalidGroupSpec, match="meaningful only for kind='ablate'"):
        gi.GroupSpec(kind="amplify", members=GROUP, ablation_mechanism="subtract")


def test_noop_may_not_name_members():
    with pytest.raises(gi.InvalidGroupSpec, match="must name no members"):
        gi.GroupSpec(kind="noop", members=GROUP)


def test_noop_refuses_to_build_a_passthrough_hook(synthetic_sae):
    with pytest.raises(gi.InvalidGroupSpec, match="registers no hook"):
        gi.build_group_hook(synthetic_sae, gi.GroupSpec.noop(), ledger=gi.FiringLedger())


def test_leave_one_out_of_a_non_member_raises():
    spec = gi.GroupSpec(kind="amplify", members=GROUP)
    with pytest.raises(gi.InvalidGroupSpec, match="not a member"):
        spec.without(999)


def test_dimension_disagreement_between_decoder_and_cfg_raises(synthetic_sae):
    class _Lying:
        W_dec = synthetic_sae.W_dec
        d_sae = 999

    with pytest.raises(gi.UnsupportedSAE, match="two disagreeing opinions"):
        gi.resolve_sae_dims(_Lying())


def test_sae_without_a_decoder_raises():
    with pytest.raises(gi.UnsupportedSAE, match="refusing to guess"):
        gi.resolve_decoder_matrix(object())


def test_raw_hf_attach_refuses_a_non_module(synthetic_sae):
    """The raw-HF path takes the decoder LAYER, not the model. Passing the
    model would silently hook nothing on a duck-typed object."""
    with pytest.raises(gi.GroupInterventionError, match="no register_forward_hook"):
        gi.attach_group_hook_raw_hf(
            object(),
            synthetic_sae,
            gi.GroupSpec(kind="amplify", members=GROUP),
            ledger=gi.FiringLedger(),
        )


def test_resolve_backend_refuses_to_guess_a_raw_hf_backend():
    """A raw HF model needs a tokenizer and a layer index that cannot be
    inferred; guessing either would hook a tensor the scorer never scored."""
    with pytest.raises(gi.GroupInterventionError, match="can be inferred from the model alone"):
        gi.resolve_backend(object())


@pytest.mark.parametrize("layer", [99, -1, 4])
def test_raw_hf_layer_index_out_of_range_raises(layer):
    """-1 must NOT wrap to the last layer: a wrapped index hooks a real
    module that is not the one the caller named, which is the silent
    version of this failure."""
    with pytest.raises(gi.InvalidGroupSpec, match="out of range"):
        gi.resolve_raw_hf_decoder_layer(gi._FakeHfModel(n_layers=4), layer=layer)


def test_raw_hf_rejects_a_model_without_a_decoder_stack():
    with pytest.raises(Exception, match=r"could not locate a \.model\.layers"):
        gi.resolve_raw_hf_decoder_layer(object(), layer=0)


def test_hooking_a_different_module_from_the_scorer_raises():
    """The load-bearing cross-half check: if the intervention attached
    anywhere else, feature f would name one direction while scoring and
    another while steering, and neither half would look wrong."""
    mine = gi._FakeHfModel(n_layers=4)
    theirs = gi._FakeHfModel(n_layers=4)
    with pytest.raises(gi.GroupInterventionError, match="NOT the module the discovery scorer"):
        gi.assert_hooks_the_scored_tensor(theirs.model.layers[1], mine, layer=1)


def test_hooking_the_scorer_module_is_accepted_and_recorded():
    model = gi._FakeHfModel(n_layers=4)
    identity = gi.assert_hooks_the_scored_tensor(model.model.layers[2], model, layer=2)
    assert identity["identity"] == "is-identical-to-scorer-module"
    assert "final_pairing_harness" in identity["resolver"]


def test_a_legacy_stub_of_the_same_name_cannot_shadow_the_device_gate():
    """REGRESSION, for a defect this module introduced and this suite caught.

    `scripts/legacy/final_pairing_concept_discovery.py` is a 23-line
    compatibility stub that forwards to the real runner and defines none of
    its functions. Putting `scripts/legacy` on sys.path for the raw-HF
    resolvers made `import final_pairing_concept_discovery` resolve to that
    stub, and the device gate silently vanished -- a helper imported by
    name, present, and empty of the thing it was imported for.

    The two asserts below are the whole fix: the stub is REAL (so the
    hazard is real, not hypothetical), and the loader still returns the
    canonical file even with the legacy directory searched first."""
    legacy_stub = REPO_ROOT / "scripts" / "legacy" / "final_pairing_concept_discovery.py"
    canonical = REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_concept_discovery.py"
    assert legacy_stub.exists(), "the shadowing hazard this test guards no longer exists"
    assert "assert_load_devices_agree" not in legacy_stub.read_text(encoding="utf-8")

    original = list(sys.path)
    try:
        sys.path.insert(0, str(legacy_stub.parent))
        module = gi._import_discovery_module()
        assert Path(module.__file__).resolve() == canonical.resolve()
        assert callable(module.assert_load_devices_agree)
    finally:
        sys.path[:] = original


def test_wrong_file_under_the_right_name_is_refused(tmp_path):
    """The loader checks the file a module CAME FROM, not its name."""
    decoy = tmp_path / "final_pairing_concept_discovery.py"
    decoy.write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(gi.DeviceGateUnavailable, match="shadowed it"):
        gi._import_module_from_exact_file(
            "final_pairing_concept_discovery",
            tmp_path / "does_not_exist.py",
            why="test",
        )


def test_raw_hf_resolvers_are_the_harness_resolvers_not_a_local_copy():
    """Structural. A local re-derivation of `hf_model.model.layers[L]` would
    be a second, independently-maintained opinion about where the residual
    stream lives -- the exact way the two halves drift apart."""
    import inspect

    source = inspect.getsource(gi.resolve_raw_hf_decoder_layer)
    assert "harness.resolve_qwen_text_decoder" in source
    assert "harness.get_qwen_decoder_layer" in source
    attach_source = inspect.getsource(gi._RawHfAttach)
    assert "register_qwen_raw_hook" in attach_source


def test_attach_on_a_model_without_hooks_raises(synthetic_sae):
    with pytest.raises(gi.GroupInterventionError, match="can be inferred from the model alone"):
        gi.resolve_backend(object()).attach(
            synthetic_sae,
            gi.GroupSpec(kind="amplify", members=GROUP),
            ledger=gi.FiringLedger(),
            prompt_lengths=None,
            verify_exact_delta=True,
        )


def test_wrong_width_hook_point_raises(synthetic_sae):
    """Hooking a point whose d_model is not the SAE's d_in would steer along
    directions of the wrong width and still produce numbers."""
    ledger = gi.FiringLedger()
    hook_fn, _ = gi.build_group_hook(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP), ledger=ledger
    )
    with pytest.raises(gi.GroupInterventionError, match="refusing to steer"):
        hook_fn(torch.randn(1, 2, 32))


# --- the firing assertion itself must be able to fail -----------------------


def test_firing_assertion_fails_when_the_hook_never_fired():
    empty = gi.FiringLedger()
    with pytest.raises(gi.HookFiringMismatch, match="fired 0 time"):
        gi.assert_fired_as_expected(empty, gi.FiringExpectation(call_count=5))


def test_firing_assertion_fails_on_an_undercount(synthetic_sae, synthetic_residual):
    _, ledger, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.5), synthetic_residual
    )
    assert ledger.call_count == 1
    with pytest.raises(gi.HookFiringMismatch, match="expected exactly 2"):
        gi.assert_fired_as_expected(ledger, gi.FiringExpectation(call_count=2))


def test_firing_assertion_fails_on_a_position_count_mismatch(synthetic_sae, synthetic_residual):
    _, ledger, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.5), synthetic_residual
    )
    with pytest.raises(gi.HookFiringMismatch, match="position slot"):
        gi.assert_fired_as_expected(
            ledger, gi.FiringExpectation(call_count=1, positions_modified=999)
        )


def test_firing_assertion_fails_when_the_hook_fired_but_did_nothing(synthetic_sae, synthetic_residual):
    """'Ran and changed nothing' is a different failure from 'never ran',
    and both must be caught."""
    _, ledger, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=(), alpha=1.0), synthetic_residual
    )
    assert ledger.call_count == 1
    with pytest.raises(gi.HookFiringMismatch, match="every injected delta was exactly zero"):
        gi.assert_fired_as_expected(ledger, gi.FiringExpectation(call_count=1))


def test_firing_assertion_has_no_warn_and_continue_path():
    """Structural: a firing disagreement has exactly one exit and it is a
    raise. Guards against a later 'strict=False' convenience flag, and
    against the whole module growing a warnings-based downgrade."""
    import ast
    import inspect

    source = inspect.getsource(gi.assert_fired_as_expected)
    body = source.replace(gi.assert_fired_as_expected.__doc__ or "", "")
    assert "warn" not in body.lower(), "no warn-and-continue path may exist in the assertion body"
    assert "raise HookFiringMismatch" in body

    signature = inspect.signature(gi.assert_fired_as_expected)
    assert set(signature.parameters) == {"ledger", "expectation", "context"}, (
        "no parameter may be added that could switch the assertion off"
    )

    module_source = Path(gi.__file__).read_text(encoding="utf-8")
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(module_source))
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(ast.parse(module_source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "warnings" not in imported, "this module must not be able to downgrade a refusal"


def test_exact_delta_assertion_rejects_a_wrong_delta(synthetic_sae, synthetic_residual):
    expected = _expected_direction(synthetic_sae, GROUP)
    with pytest.raises(gi.ExactDeltaMismatch, match="not the delta that was requested"):
        gi.assert_exact_delta(
            synthetic_residual, synthetic_residual + 2.0 * expected, expected
        )


def test_exact_delta_assertion_rejects_a_shape_change(synthetic_residual):
    with pytest.raises(gi.ExactDeltaMismatch, match="shape changed"):
        gi.assert_exact_delta(
            synthetic_residual, synthetic_residual[:, :2], torch.zeros(16)
        )


def test_delta_tolerance_scales_with_the_residual_magnitude():
    """Not a hand-tuned epsilon: at a residual of magnitude 1e6 the tolerance
    must widen, because (x + d) - x genuinely loses precision there."""
    small = gi.delta_tolerance(torch.ones(4, dtype=torch.float32))
    large = gi.delta_tolerance(torch.full((4,), 1.0e6, dtype=torch.float32))
    assert large > small > 0.0
    assert large == pytest.approx(small * 1.0e6, rel=1e-6)


# --- null configurations ----------------------------------------------------


@pytest.mark.parametrize(
    "spec",
    [
        gi.GroupSpec(kind="amplify", members=GROUP, alpha=0.0),
        gi.GroupSpec(kind="amplify", members=(), alpha=3.0),
        gi.GroupSpec(kind="ablate", members=GROUP, alpha=0.0, ablation_mechanism="subtract"),
        gi.GroupSpec(kind="ablate", members=(), alpha=1.0, ablation_mechanism="subtract"),
    ],
    ids=["amplify-alpha0", "amplify-empty", "subtract-alpha0", "subtract-empty"],
)
def test_null_configurations_are_bit_exact_identities(synthetic_sae, synthetic_residual, spec):
    """Bit-exact, not merely close: the hook returns the INPUT OBJECT, so a
    -0.0 element cannot be flipped to +0.0 by an `x + 0.0`."""
    assert gi.null_configuration_is_exact_identity(spec) is True
    out, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual)
    assert out is synthetic_residual
    assert torch.equal(out, synthetic_residual)
    assert ledger.call_count == 1, "the identity must still be RECORDED as having fired"
    assert ledger.positions_modified == 0


def test_negative_zero_survives_a_null_amplify(synthetic_sae):
    """The reason bit-identity is stated as returning the input object."""
    residual = torch.zeros(1, 1, 16)
    residual[0, 0, 0] = -0.0
    out, _, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=0.0), residual
    )
    assert torch.equal(torch.signbit(out), torch.signbit(residual))


def test_mechanism_a_null_configuration_is_NOT_an_identity(synthetic_sae, synthetic_residual):
    """PINNED, not papered over. Mechanism (a) writes decode(encode(h)) back
    whether or not any feature is touched, so its null arm still moves the
    stream by the whole reconstruction error. Callers needing a genuine
    baseline under (a) use GroupSpec.reconstruction_control()."""
    spec = gi.GroupSpec(kind="ablate", members=(), alpha=0.0, ablation_mechanism="reconstruct")
    assert gi.null_configuration_is_exact_identity(spec) is False
    out, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual)
    assert not torch.equal(out, synthetic_residual)
    floor = float((out - synthetic_residual).norm().item())
    expected = float(gi.reconstruction_error(synthetic_sae, synthetic_residual).norm().item())
    assert floor == pytest.approx(expected, rel=1e-5)
    assert ledger.call_count == 1


def test_reconstruction_control_is_exactly_the_empty_group_under_mechanism_a(synthetic_sae):
    control = gi.GroupSpec.reconstruction_control()
    assert control.kind == "ablate"
    assert control.ablation_mechanism == "reconstruct"
    assert control.member_count == 0


def test_ablating_an_already_zero_group_is_an_identity_against_its_own_baseline(
    synthetic_sae, synthetic_residual
):
    dead = gi._dead_features(synthetic_sae, synthetic_residual)
    assert dead, "the synthetic SAE must expose dead features or this control cannot run"
    members = tuple(gi.GroupMember(i) for i in dead[:3])
    reconstruction = synthetic_sae.decode(synthetic_sae.encode(synthetic_residual))

    subtract = gi.GroupSpec(kind="ablate", members=members, alpha=1.0, ablation_mechanism="subtract")
    out_b, _, _ = _apply(synthetic_sae, subtract, synthetic_residual)
    assert torch.allclose(out_b, synthetic_residual, atol=1e-6)

    reconstruct = gi.GroupSpec(
        kind="ablate", members=members, alpha=1.0, ablation_mechanism="reconstruct"
    )
    out_a, _, _ = _apply(synthetic_sae, reconstruct, synthetic_residual)
    assert torch.allclose(out_a, reconstruction, atol=1e-5)
    # And explicitly NOT an identity against h. Asserting only the first
    # comparison would let a reader conclude the mechanisms agree here.
    assert not torch.allclose(out_a, synthetic_residual, atol=1e-3)


# ---------------------------------------------------------------------------
# SUCCESS LAYER -- the arithmetic.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alpha", [0.5, 1.0, 4.0, -2.0, 137.0])
def test_amplify_delta_is_exactly_alpha_times_the_weighted_decoder_sum(
    synthetic_sae, synthetic_residual, alpha
):
    spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=alpha)
    out, ledger, resolved = _apply(synthetic_sae, spec, synthetic_residual)
    expected = _expected_direction(synthetic_sae, GROUP) * alpha
    worst = gi.assert_exact_delta(synthetic_residual, out, expected)
    assert worst <= gi.delta_tolerance(synthetic_residual, expected)
    # The resolved group's own precomputed direction must agree with the
    # independently recomputed one -- otherwise the assertion above would be
    # the hook checking itself.
    assert torch.allclose(resolved.expected_amplify_delta(), expected, atol=1e-6)
    assert ledger.positions_modified == synthetic_residual.shape[0] * synthetic_residual.shape[1]


def test_per_feature_weights_are_honoured(synthetic_sae, synthetic_residual):
    w_dec = synthetic_sae.W_dec
    members = (gi.GroupMember(3, 2.0), gi.GroupMember(7, -1.5))
    out, _, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=members, alpha=1.0), synthetic_residual
    )
    expected = 2.0 * w_dec[3] + (-1.5) * w_dec[7]
    gi.assert_exact_delta(synthetic_residual, out, expected)


def test_injected_delta_is_linear_in_alpha(synthetic_sae, synthetic_residual):
    base = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.0), synthetic_residual
    )[0] - synthetic_residual
    doubled = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=2.0), synthetic_residual
    )[0] - synthetic_residual
    assert torch.allclose(doubled, 2.0 * base, atol=1e-5)


def test_injected_delta_is_additive_over_members(synthetic_sae, synthetic_residual):
    """Additivity OF THE INJECTED VECTOR. joint_intervention_lane.json
    RULING_3 prohibits predicting a joint EFFECT from summed individual
    effects, and nothing here claims otherwise -- this is arithmetic on the
    steering vector, not a claim about the model's response."""
    whole = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.0), synthetic_residual
    )[0] - synthetic_residual
    parts = sum(
        _apply(
            synthetic_sae,
            gi.GroupSpec(kind="amplify", members=(member,), alpha=1.0),
            synthetic_residual,
        )[0]
        - synthetic_residual
        for member in GROUP
    )
    assert torch.allclose(whole, parts, atol=1e-5)


def test_subtract_mechanism_removes_exactly_the_group_decoder_contribution(
    synthetic_sae, synthetic_residual
):
    """Independent closed form, not a re-run of the hook's own code."""
    spec = gi.GroupSpec(kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="subtract")
    out, _, resolved = _apply(synthetic_sae, spec, synthetic_residual)
    feats = synthetic_sae.encode(synthetic_residual)
    expected = torch.zeros_like(synthetic_residual)
    for member in GROUP:
        expected = expected + (
            feats[..., member.feature_index : member.feature_index + 1]
            * member.weight
            * synthetic_sae.W_dec[member.feature_index]
        )
    assert torch.allclose(out, synthetic_residual - expected, atol=1e-5)
    assert resolved.member_count == 3


def test_reconstruct_mechanism_writes_the_reconstruction_back(synthetic_sae, synthetic_residual):
    spec = gi.GroupSpec(kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="reconstruct")
    out, _, _ = _apply(synthetic_sae, spec, synthetic_residual)
    feats = synthetic_sae.encode(synthetic_residual).clone()
    for member in GROUP:
        feats[..., member.feature_index] = feats[..., member.feature_index] * (1.0 - member.weight)
    assert torch.allclose(out, synthetic_sae.decode(feats), atol=1e-5)


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0, 3.0])
@pytest.mark.parametrize("members", [(), GROUP], ids=["empty", "three"])
def test_mechanism_gap_is_exactly_minus_the_reconstruction_error(
    synthetic_sae, synthetic_residual, alpha, members
):
    """The closed form: delta_a - delta_b == decode(encode(h)) - h, for any
    alpha and any group -- including the empty one. This is what makes the
    two mechanisms non-interchangeable."""
    spec = gi.GroupSpec(
        kind="ablate", members=members, alpha=alpha, ablation_mechanism="subtract"
    )
    gap = gi.measure_mechanism_gap(synthetic_sae, spec, synthetic_residual)
    assert gap["closed_form_residual_max_abs"] < 1e-4
    assert gap["gap_norm"] == pytest.approx(gap["reconstruction_error_norm"], rel=1e-5)
    assert gap["member_count"] == len(members)


def test_the_two_mechanisms_disagree_by_a_non_trivial_amount(synthetic_sae, synthetic_residual):
    """Guards the claim that this distinction MATTERS. If the fixture SAE
    ever reconstructed perfectly, the gap would vanish and every mechanism
    test above would pass while proving nothing."""
    spec = gi.GroupSpec(kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="subtract")
    gap = gi.measure_mechanism_gap(synthetic_sae, spec, synthetic_residual)
    assert gap["reconstruction_error_norm"] > 0.1 * gap["residual_norm"]
    assert gap["relative_gap"] is not None and gap["relative_gap"] > 1.0


def test_generated_only_delta_is_exact_at_steered_and_zero_at_unsteered_positions(
    synthetic_sae, synthetic_residual
):
    """The masked path is held to the SAME exactness as the unmasked one:
    the requested vector where the mask is True, and EXACTLY zero where it
    is False. A hook leaking into the prefill fails here rather than being
    excused as out of scope."""
    prompt_len = 3
    spec = gi.GroupSpec(
        kind="amplify", members=GROUP, alpha=2.0, positions="generated_only"
    )
    ledger = gi.FiringLedger()
    hook_fn, _ = gi.build_group_hook(
        synthetic_sae, spec, ledger=ledger, prompt_lengths=prompt_len
    )
    out = hook_fn(synthetic_residual)
    delta = out - synthetic_residual
    expected = _expected_direction(synthetic_sae, GROUP) * 2.0
    assert torch.equal(delta[:, :prompt_len], torch.zeros_like(delta[:, :prompt_len]))
    assert torch.allclose(
        delta[:, prompt_len:],
        expected.expand_as(delta[:, prompt_len:]),
        atol=gi.delta_tolerance(synthetic_residual, expected),
    )
    batch, seq_len, _ = synthetic_residual.shape
    assert ledger.positions_modified == batch * (seq_len - prompt_len)


def test_leave_one_out_specs_preserve_kind_alpha_mechanism_and_cardinality():
    spec = gi.GroupSpec(
        kind="ablate", members=GROUP, alpha=2.5, ablation_mechanism="reconstruct", label="g"
    )
    arms = gi.leave_one_out_specs(spec)
    assert len(arms) == spec.member_count
    for arm, dropped in zip(arms, spec.feature_indices, strict=True):
        assert arm.member_count == spec.member_count - 1
        assert dropped not in arm.feature_indices
        assert arm.kind == "ablate"
        assert arm.alpha == 2.5
        assert arm.ablation_mechanism == "reconstruct"
    assert {frozenset(a.feature_indices) for a in arms} == {
        frozenset({7, 11}),
        frozenset({3, 11}),
        frozenset({3, 7}),
    }


# ---------------------------------------------------------------------------
# DTYPE LAYER. The production residual stream is bfloat16/float16, and the
# exact-delta assertion behaves differently there in a way that matters.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16, torch.float16])
def test_derived_tolerance_still_holds_at_every_dtype(synthetic_sae, synthetic_residual, dtype):
    """Answers the question directly: the `~ulp(x)` form needed NO
    dtype-dependent variant, because eps already carries the dtype."""
    for alpha in (10.0, 1.0, 0.1, 0.001):
        x = synthetic_residual.to(dtype)
        spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=alpha)
        out, _, resolved = _apply(synthetic_sae, spec, x)
        expected = resolved.expected_amplify_delta()
        worst = float(((out - x).to(torch.float32) - expected.expand_as(out)).abs().max().item())
        assert worst <= gi.delta_tolerance(x, expected), f"{dtype} alpha={alpha}"


def test_float32_absorbs_nothing(synthetic_sae, synthetic_residual):
    for alpha in (10.0, 0.1, 0.001):
        spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=alpha)
        _, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual.to(torch.float32))
        assert ledger.absorbed_element_count == 0
        assert ledger.absorbed_fraction == 0.0


@pytest.mark.parametrize("dtype", [torch.bfloat16, torch.float16])
def test_low_precision_absorbs_a_small_delta_while_the_assertion_still_passes(
    synthetic_sae, synthetic_residual, dtype
):
    """THE FINDING. At bfloat16 a passing exact-delta assertion does NOT
    establish that the intervention was applied: the absorbed magnitude is
    below the tolerance the dtype forces. Both halves are asserted here --
    that the assertion passes, AND that it passed over a mostly-absorbed
    delta -- because either alone would misrepresent the situation."""
    x = synthetic_residual.to(dtype)
    spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=0.001)
    out, ledger, resolved = _apply(synthetic_sae, spec, x)
    expected = resolved.expected_amplify_delta()

    # The assertion passes ...
    gi.assert_exact_delta(x, out, expected)
    # ... over a delta that was mostly swallowed whole.
    assert ledger.absorbed_fraction > 0.5, f"{dtype} did not absorb; this test proves nothing"
    assert ledger.requested_nonzero_element_count == x.numel()
    assert ledger.residual_dtypes == (str(dtype),)


@pytest.mark.parametrize("dtype", [torch.bfloat16, torch.float16])
def test_assert_no_absorption_catches_what_exact_delta_cannot(
    synthetic_sae, synthetic_residual, dtype
):
    x = synthetic_residual.to(dtype)
    _, ledger, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=0.001), x
    )
    with pytest.raises(gi.ExactDeltaMismatch, match="absorbed"):
        gi.assert_no_absorption(ledger)


def test_assert_no_absorption_passes_at_float32(synthetic_sae, synthetic_residual):
    _, ledger, _ = _apply(
        synthetic_sae, gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.0), synthetic_residual
    )
    summary = gi.assert_no_absorption(ledger)
    assert summary["absorbed_element_count"] == 0


def test_a_large_enough_alpha_survives_bfloat16(synthetic_sae, synthetic_residual):
    """The absorption census is not a blanket bfloat16 refusal: a dose above
    minimum_effective_alpha lands everywhere and passes the strong check."""
    x = synthetic_residual.to(torch.bfloat16)
    floor = gi.minimum_effective_alpha(x, _expected_direction(synthetic_sae, GROUP))
    spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=floor * 1000.0)
    _, ledger, _ = _apply(synthetic_sae, spec, x)
    gi.assert_no_absorption(ledger)


def test_minimum_effective_alpha_is_far_larger_at_bfloat16_than_float32(
    synthetic_sae, synthetic_residual
):
    direction = _expected_direction(synthetic_sae, GROUP)
    at_bf16 = gi.minimum_effective_alpha(synthetic_residual, direction, dtype=torch.bfloat16)
    at_fp32 = gi.minimum_effective_alpha(synthetic_residual, direction, dtype=torch.float32)
    assert at_bf16 > at_fp32 * 1000.0
    ratio = torch.finfo(torch.bfloat16).eps / torch.finfo(torch.float32).eps
    assert at_bf16 / at_fp32 == pytest.approx(ratio, rel=1e-3)


def test_minimum_effective_alpha_is_infinite_for_a_zero_direction(synthetic_residual):
    assert gi.minimum_effective_alpha(synthetic_residual, torch.zeros(16)) == float("inf")


def test_absorption_census_is_masked_like_the_delta(synthetic_sae, synthetic_residual):
    """Under generated_only the unsteered positions requested nothing, so
    they must not inflate the denominator into looking healthy."""
    prompt_len = 3
    x = synthetic_residual.to(torch.bfloat16)
    spec = gi.GroupSpec(
        kind="amplify", members=GROUP, alpha=0.001, positions="generated_only"
    )
    ledger = gi.FiringLedger()
    hook_fn, _ = gi.build_group_hook(synthetic_sae, spec, ledger=ledger, prompt_lengths=prompt_len)
    hook_fn(x)
    batch, seq_len, d_in = x.shape
    assert ledger.requested_nonzero_element_count == batch * (seq_len - prompt_len) * d_in


def test_dtype_limits_documents_the_insufficiency():
    text = gi.DTYPE_LIMITS
    assert "NECESSARY BUT NOT SUFFICIENT" in text
    assert "MUST NOT BE TIGHTENED" in text
    assert "bfloat16" in text and "float16" in text


def test_spec_to_dict_records_member_count_and_mechanism():
    spec = gi.GroupSpec(kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="subtract")
    data = spec.to_dict()
    assert data["member_count"] == 3
    assert data["ablation_mechanism"] == "subtract"
    assert data["positions"] == "all", "positions defaults to ALL per the standing science ruling"
    assert [m["feature_index"] for m in data["members"]] == [3, 7, 11]


def test_positions_defaults_to_all():
    assert gi.GroupSpec(kind="amplify", members=GROUP).positions == "all"


def test_generated_only_requires_prompt_lengths(synthetic_sae):
    spec = gi.GroupSpec(kind="amplify", members=GROUP, positions="generated_only")
    with pytest.raises(gi.InvalidGroupSpec, match="prompt_lengths is required"):
        gi.build_group_hook(synthetic_sae, spec, ledger=gi.FiringLedger())


def test_positions_all_rejects_prompt_lengths(synthetic_sae):
    spec = gi.GroupSpec(kind="amplify", members=GROUP, positions="all")
    with pytest.raises(gi.InvalidGroupSpec, match="must be None"):
        gi.build_group_hook(synthetic_sae, spec, ledger=gi.FiringLedger(), prompt_lengths=3)


def test_expected_generation_firing_matches_the_documented_call_pattern():
    """docs/positions_semantics.md: one prefill call over the whole prompt,
    then one call per subsequent token."""
    at_all = gi.expected_generation_firing(
        prompt_token_count=11, generated_token_count=5, positions="all"
    )
    assert at_all.call_count == 5
    assert at_all.positions_modified == 11 + 5 - 1
    generated_only = gi.expected_generation_firing(
        prompt_token_count=11, generated_token_count=5, positions="generated_only"
    )
    assert generated_only.call_count == 5
    assert generated_only.positions_modified == 4


def test_unexercised_paths_are_declared():
    assert gi.UNEXERCISED_WITHOUT_GPU
    joined = " ".join(gi.UNEXERCISED_WITHOUT_GPU).lower()
    assert "gemma" in joined and "qwen" in joined


def test_frozen_null_ablation_phrasing_is_verbatim():
    """RULING_A11b froze this sentence before the instrument existed. If it
    drifts, a null result gets reported in words the protocol prohibits."""
    assert gi.NULL_ABLATION_FROZEN_PHRASING == (
        "Ablating this set did not remove the concept. We cannot distinguish an "
        "unnecessary set from an incomplete one."
    )


def test_selfcheck_runs_clean():
    assert gi.main(["--selfcheck"]) == 0


# ---------------------------------------------------------------------------
# REAL-WEIGHTS LAYER (CPU): real HookedTransformer + real sae_lens SAE.
# ---------------------------------------------------------------------------

PROMPT = "hello world"


@pytest.fixture(scope="module")
def real_model():
    from interplab.certification.model_loading import load_local_hooked_transformer

    return load_local_hooked_transformer(str(REPO_ROOT / "tests" / "fixtures" / "tiny_model"))


@pytest.fixture(scope="module")
def real_sae():
    from sae_lens import SAE

    return SAE.load_from_pretrained(str(REPO_ROOT / "tests" / "fixtures" / "tiny_sae"), device="cpu")


@pytest.fixture(scope="module")
def real_tokens(real_model):
    return real_model.to_tokens([PROMPT])


def _live_features(real_sae, residual, limit=3):
    feats = real_sae.encode(residual.to(torch.float32))
    per_feature = feats.abs().amax(dim=tuple(range(feats.ndim - 1)))
    order = torch.argsort(per_feature, descending=True)
    return [int(i) for i in order[:limit].tolist()]


def _dead_real_features(real_sae, residual, limit=3):
    feats = real_sae.encode(residual.to(torch.float32))
    per_feature = feats.abs().amax(dim=tuple(range(feats.ndim - 1)))
    return [int(i) for i in torch.nonzero(per_feature == 0.0).flatten().tolist()][:limit]


def test_real_sae_decoder_is_affine_so_the_closed_form_applies(real_sae):
    """The gap identity depends on decode() being affine. Measured on the
    real sae_lens TopK SAE rather than assumed from its architecture."""
    feats = real_sae.encode(torch.randn(2, 3, 64))
    modified = feats.clone()
    modified[..., 5] = 0.0
    lhs = real_sae.decode(modified) - real_sae.decode(feats)
    rhs = -(feats[..., 5:6] * real_sae.W_dec[5])
    assert torch.allclose(lhs, rhs, atol=1e-5)


def test_real_group_resolves_against_the_real_sae(real_sae):
    resolved = gi.resolve_group(
        real_sae, gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7), gi.GroupMember(64)))
    )
    assert (resolved.d_sae, resolved.d_in) == (256, 64)
    assert resolved.hook_name == "blocks.1.hook_resid_post"
    assert resolved.member_count == 2


def test_real_sae_rejects_an_index_at_d_sae(real_sae):
    with pytest.raises(gi.FeatureNotInSAE):
        gi.resolve_group(real_sae, gi.GroupSpec(kind="amplify", members=(gi.GroupMember(256),)))


def test_device_gate_is_live_and_can_fail(real_model, real_sae):
    """Proof the gate is not decorative: the same call that passes on CPU
    RAISES when told the run is on cuda:0, which is exactly the placement
    disagreement that killed job 415590."""
    measured = gi.assert_devices_before_forward(device="cpu", model=real_model, sae=real_sae)
    assert measured["model"] == "cpu" and measured["sae"] == "cpu"
    with pytest.raises(Exception) as excinfo:
        gi.assert_devices_before_forward(device="cuda:0", model=real_model, sae=real_sae)
    assert "cuda" in str(excinfo.value).lower()


def test_hook_fires_the_documented_number_of_times_on_the_real_model(
    real_model, real_sae, real_tokens
):
    """One prefill call over the whole prompt, then one per later token --
    measured through the real model.hooks(...) + model.generate(...) path."""
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=1.0)
    ledger = gi.FiringLedger()
    torch.manual_seed(7)
    with gi.attach_group_hook(real_model, real_sae, spec, ledger=ledger):
        out = real_model.generate(
            real_tokens, max_new_tokens=5, do_sample=False, stop_at_eos=False, verbose=False
        )
    prompt_len = int(real_tokens.shape[1])
    generated = int(out.shape[1]) - prompt_len
    assert generated == 5
    expectation = gi.expected_generation_firing(
        prompt_token_count=prompt_len, generated_token_count=generated, positions="all"
    )
    summary = gi.assert_fired_as_expected(ledger, expectation)
    assert summary["call_count"] == 5
    assert summary["prefill_call_count"] == 1
    assert summary["decode_call_count"] == 4
    assert summary["positions_modified"] == prompt_len + 4
    assert [tuple(r.tensor_shape) for r in ledger.records] == [
        (1, prompt_len, 64),
        (1, 1, 64),
        (1, 1, 64),
        (1, 1, 64),
        (1, 1, 64),
    ]


def test_generation_outside_the_attach_context_fails_the_firing_assertion(
    real_model, real_sae, real_tokens
):
    """THE FAILURE THIS MODULE EXISTS FOR, on the real model. The hook was
    built and the ledger was held, but generation ran outside the context,
    so nothing fired. Without the assertion this returns a perfectly normal
    continuation and a perfectly normal 'no effect' conclusion."""
    spec = gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7),), alpha=50.0)
    ledger = gi.FiringLedger()
    gi.build_group_hook(real_sae, spec, ledger=ledger)
    out = real_model.generate(
        real_tokens, max_new_tokens=4, do_sample=False, stop_at_eos=False, verbose=False
    )
    generated = int(out.shape[1]) - int(real_tokens.shape[1])
    with pytest.raises(gi.HookFiringMismatch, match="fired 0 time"):
        gi.assert_fired_as_expected(
            ledger,
            gi.expected_generation_firing(
                prompt_token_count=int(real_tokens.shape[1]),
                generated_token_count=generated,
                positions="all",
            ),
        )


def test_an_all_dead_group_ablation_is_caught_as_a_silent_no_op(real_model, real_sae, real_tokens):
    """A real, non-hypothetical silent no-op: a TopK SAE leaves most
    features at exactly zero, so ablating a group of them fires the hook and
    changes nothing. That must FAIL, not return a null result."""
    with torch.no_grad():
        _, cache = real_model.run_with_cache(real_tokens, names_filter="blocks.1.hook_resid_post")
    residual = cache["blocks.1.hook_resid_post"]
    dead = _dead_real_features(real_sae, residual)
    assert len(dead) >= 3
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in dead),
        alpha=1.0,
        ablation_mechanism="subtract",
    )
    ledger = gi.FiringLedger()
    with gi.attach_group_hook(real_model, real_sae, spec, ledger=ledger):
        real_model(real_tokens)
    assert ledger.call_count == 1
    with pytest.raises(gi.HookFiringMismatch, match="every injected delta was exactly zero"):
        gi.assert_fired_as_expected(ledger, gi.FiringExpectation(call_count=1))


def test_generated_only_never_steers_the_prefill_on_the_real_model(
    real_model, real_sae, real_tokens
):
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(
        kind="amplify",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        positions="generated_only",
    )
    ledger = gi.FiringLedger()
    prompt_len = int(real_tokens.shape[1])
    with gi.attach_group_hook(
        real_model, real_sae, spec, ledger=ledger, prompt_lengths=prompt_len
    ):
        out = real_model.generate(
            real_tokens, max_new_tokens=5, do_sample=False, stop_at_eos=False, verbose=False
        )
    generated = int(out.shape[1]) - prompt_len
    gi.assert_fired_as_expected(
        ledger,
        gi.expected_generation_firing(
            prompt_token_count=prompt_len,
            generated_token_count=generated,
            positions="generated_only",
        ),
    )
    assert ledger.records[0].positions_modified == 0, "the prefill must never be steered"
    assert ledger.positions_modified == generated - 1


def test_alpha_zero_leaves_the_real_logits_bit_identical(real_model, real_sae, real_tokens):
    """Stronger than the noop control: the hook IS registered and DOES fire,
    and the logits are still bit-identical."""
    with torch.no_grad():
        baseline = real_model(real_tokens)
    spec = gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7), gi.GroupMember(64)), alpha=0.0)
    ledger = gi.FiringLedger()
    with torch.no_grad(), gi.attach_group_hook(real_model, real_sae, spec, ledger=ledger):
        steered = real_model(real_tokens)
    assert ledger.call_count == 1, "the hook must have fired"
    assert torch.equal(baseline, steered)


def test_noop_control_registers_no_hook_and_is_bit_identical(real_model, real_sae, real_tokens):
    with torch.no_grad():
        baseline = real_model(real_tokens)
    ledger = gi.FiringLedger()
    with torch.no_grad(), gi.attach_group_hook(
        real_model, real_sae, gi.GroupSpec.noop(), ledger=ledger
    ):
        control = real_model(real_tokens)
    assert ledger.call_count == 0
    assert torch.equal(baseline, control)


def test_exact_delta_holds_on_the_real_residual_stream(real_model, real_sae, real_tokens):
    """h_after - h_before == alpha * sum_f w_f * W_dec[f], measured on the
    real model's own residual stream at the SAE's own hook point."""
    captured: dict[str, torch.Tensor] = {}

    def capture(resid, hook):
        captured["before"] = resid.detach().clone()
        return resid

    with torch.no_grad(), real_model.hooks(fwd_hooks=[("blocks.1.hook_resid_post", capture)]):
        real_model(real_tokens)
    before = captured["before"]

    members = (gi.GroupMember(7, 1.0), gi.GroupMember(64, -0.5), gi.GroupMember(129, 2.0))
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=3.0)
    ledger = gi.FiringLedger()
    hook_fn, resolved = gi.build_group_hook(real_sae, spec, ledger=ledger)
    after = hook_fn(before)
    expected = 3.0 * sum(m.weight * real_sae.W_dec[m.feature_index] for m in members)
    worst = gi.assert_exact_delta(before, after, expected.detach())
    assert worst <= gi.delta_tolerance(before, expected.detach())
    assert resolved.member_count == 3


def test_a_large_amplification_actually_changes_the_real_continuation(
    real_model, real_sae, real_tokens
):
    """The positive control for the whole harness. Every identity test above
    would also pass on a hook that did nothing; this one would not."""
    live = _live_features(real_sae, torch.randn(1, 4, 64), limit=5)
    spec = gi.GroupSpec(
        kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=200.0
    )
    torch.manual_seed(11)
    control = real_model.generate(
        real_tokens, max_new_tokens=6, do_sample=False, stop_at_eos=False, verbose=False
    )
    ledger = gi.FiringLedger()
    torch.manual_seed(11)
    with gi.attach_group_hook(real_model, real_sae, spec, ledger=ledger):
        treated = real_model.generate(
            real_tokens, max_new_tokens=6, do_sample=False, stop_at_eos=False, verbose=False
        )
    assert ledger.call_count == 6
    assert ledger.max_abs_delta > 0.0
    assert not torch.equal(control, treated)


def test_run_arm_asserts_firing_and_returns_per_token_quantities(real_model, real_sae):
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(
        kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=25.0, label="treat"
    )
    arm = gi.run_arm(
        real_model, real_sae, spec, [PROMPT], max_new_tokens=4, seed=3, device="cpu"
    )
    assert arm.device_placement == {"model": "cpu", "sae": "cpu"}
    assert arm.null_configuration_is_exact_identity is False
    (row,) = arm.results
    assert row.generated_token_count == 4
    assert row.firing["call_count"] == 4
    assert row.firing["positions_modified"] == row.prompt_token_count + 3
    assert row.per_token_logprob is not None and len(row.per_token_logprob) == 4
    assert all(value <= 0.0 for value in row.per_token_logprob)
    assert row.sum_logprob == pytest.approx(sum(row.per_token_logprob))
    assert len(row.generated_token_ids) == 4


def test_run_arm_control_arm_asserts_zero_calls(real_model, real_sae):
    arm = gi.run_arm(
        real_model, real_sae, gi.GroupSpec.noop(), [PROMPT], max_new_tokens=3, seed=3, device="cpu"
    )
    (row,) = arm.results
    assert row.firing["call_count"] == 0
    assert row.firing_expectation["call_count"] == 0
    assert arm.null_configuration_is_exact_identity is True


def test_measure_group_effect_pairs_control_and_treatment_at_one_seed(real_model, real_sae):
    live = _live_features(real_sae, torch.randn(1, 4, 64), limit=4)
    spec = gi.GroupSpec(
        kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=200.0, label="joint"
    )
    measurement = gi.measure_group_effect(
        real_model, real_sae, spec, [PROMPT], max_new_tokens=5, seed=17, device="cpu"
    )
    assert measurement.seed == 17
    (row,) = measurement.per_prompt
    assert row["treatment_hook_call_count"] == 5
    assert row["treatment_total_delta_norm"] > 0.0
    assert measurement.any_continuation_changed is True
    assert row["first_divergent_generated_position"] is not None
    assert measurement.control.results[0].firing["call_count"] == 0


def test_measure_group_effect_with_a_null_treatment_reproduces_the_control(real_model, real_sae):
    """A zero-alpha treatment must be byte-identical to its paired control.
    If the pairing were broken (different seeds, different prompts) this
    would diverge."""
    spec = gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7),), alpha=0.0)
    measurement = gi.measure_group_effect(
        real_model,
        real_sae,
        spec,
        [PROMPT],
        max_new_tokens=5,
        seed=17,
        device="cpu",
        require_nonzero_delta=False,
    )
    (row,) = measurement.per_prompt
    assert row["token_ids_identical"] is True
    assert row["first_divergent_generated_position"] is None
    assert row["delta_sum_logprob_of_control_continuation"] == pytest.approx(0.0, abs=1e-6)


def test_measure_group_effect_against_the_reconstruction_control(real_model, real_sae):
    """Mechanism (a) measured against its own floor. The reconstruction
    control is itself an intervention, so it fires and is asserted."""
    with torch.no_grad():
        _, cache = real_model.run_with_cache(
            real_model.to_tokens([PROMPT]), names_filter="blocks.1.hook_resid_post"
        )
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=3)
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        ablation_mechanism="reconstruct",
    )
    measurement = gi.measure_group_effect(
        real_model,
        real_sae,
        spec,
        [PROMPT],
        max_new_tokens=4,
        seed=5,
        device="cpu",
        control_spec=gi.GroupSpec.reconstruction_control(),
    )
    assert measurement.control.results[0].firing["call_count"] == 4
    assert measurement.treatment.results[0].firing["call_count"] == 4


def test_mechanism_gap_on_the_real_sae_is_the_real_reconstruction_error(real_model, real_sae):
    with torch.no_grad():
        _, cache = real_model.run_with_cache(
            real_model.to_tokens([PROMPT]), names_filter="blocks.1.hook_resid_post"
        )
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=3)
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        ablation_mechanism="subtract",
    )
    gap = gi.measure_mechanism_gap(real_sae, spec, residual)
    assert gap["closed_form_residual_max_abs"] < 1e-3
    assert gap["gap_norm"] == pytest.approx(gap["reconstruction_error_norm"], rel=1e-4)
    assert gap["delta_b_norm"] > 0.0


# ---------------------------------------------------------------------------
# RAW-HF LAYER (CPU): the Qwen3.5 pairing's path, on a REAL AutoModelForCausalLM
# hooked with register_forward_hook. transformer_lens cannot load Qwen3.5, so
# without this path one of the two frozen final pairings has no intervention at
# all. Proven here against tests/fixtures/tiny_model, a real Qwen2ForCausalLM
# whose Qwen2DecoderLayer returns a plain tensor exactly as
# final_pairing_harness documents Qwen3_5DecoderLayer doing.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def raw_hf_model():
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        str(REPO_ROOT / "tests" / "fixtures" / "tiny_model"), dtype=torch.float32
    )
    model.eval()
    return model


@pytest.fixture(scope="module")
def raw_hf_tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(str(REPO_ROOT / "tests" / "fixtures" / "tiny_model"))


@pytest.fixture(scope="module")
def raw_backend(raw_hf_model, raw_hf_tokenizer):
    # Layer 1 -- the layer tests/fixtures/tiny_sae was trained at
    # (cfg.metadata.hook_name is blocks.1.hook_resid_post).
    return gi.RawHfBackend(raw_hf_model, raw_hf_tokenizer, layer=1)


def test_raw_backend_resolves_the_same_module_the_scorer_hooks(raw_backend, raw_hf_model):
    """`Backend._qwen_decoder_layer` in the discovery runner is
    `harness.get_qwen_decoder_layer(harness.resolve_qwen_text_decoder(m), L)`.
    This asserts object identity with that, so a feature index cannot mean
    one direction while scoring and another while steering."""
    scorer_module = gi.resolve_raw_hf_decoder_layer(raw_hf_model, layer=1)
    assert raw_backend.decoder_layer is scorer_module
    assert raw_backend.decoder_layer is raw_hf_model.model.layers[1]
    assert raw_backend.hook_identity["identity"] == "is-identical-to-scorer-module"


def test_raw_hf_layer_output_is_a_plain_tensor_as_the_harness_asserts(raw_hf_model):
    """The contract `register_qwen_raw_hook` validates at runtime, measured
    rather than assumed: if this fixture's decoder layer returned a tuple,
    the whole raw-HF path would refuse instead of silently mis-hooking."""
    seen = []
    handle = raw_hf_model.model.layers[1].register_forward_hook(
        lambda _m, _a, out: seen.append(out)
    )
    try:
        with torch.no_grad():
            raw_hf_model(input_ids=torch.tensor([[1, 2, 3]]))
    finally:
        handle.remove()
    assert isinstance(seen[0], torch.Tensor)
    assert seen[0].shape[-1] == 64


def test_raw_hf_hook_returning_a_tuple_is_refused(real_sae):
    """The refusal that stands in for real Qwen3.5 weights. If Tamia's
    installed layer ever returns a tuple, the harness stops rather than
    guessing how to unwrap it -- exercised here by hooking a module that
    really does return one."""
    harness = gi._import_harness()

    class _TupleReturningLayer(torch.nn.Module):
        def forward(self, x):
            return (x,)

    layer = _TupleReturningLayer()
    ledger = gi.FiringLedger()
    hook_fn, _ = gi.build_group_hook(
        real_sae, gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7),)), ledger=ledger
    )
    handle = harness.register_qwen_raw_hook(layer, hook_fn)
    try:
        with pytest.raises(Exception, match="plain tensor"):
            layer(torch.randn(1, 3, 64))
    finally:
        handle.remove()
    assert ledger.call_count == 0


def test_raw_hf_hook_fires_the_documented_number_of_times(raw_backend, real_sae):
    """MEASURED, not carried over: HF's own KV-cached generate produces the
    same one-prefill-then-one-per-token pattern transformer_lens does, so
    expected_generation_firing applies unchanged to both backends."""
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(
        kind="amplify",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        hook_name="raw-hf.layers.1",
    )
    tokens = raw_backend.to_tokens(PROMPT)
    prompt_len = int(tokens.shape[1])
    ledger = gi.FiringLedger()
    torch.manual_seed(7)
    with raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        out = raw_backend.generate(
            tokens, max_new_tokens=5, do_sample=False, temperature=1.0, stop_at_eos=False
        )
    generated = int(out.shape[1]) - prompt_len
    assert generated == 5
    summary = gi.assert_fired_as_expected(
        ledger,
        gi.expected_generation_firing(
            prompt_token_count=prompt_len, generated_token_count=generated, positions="all"
        ),
    )
    assert summary["call_count"] == 5
    assert summary["prefill_call_count"] == 1
    assert summary["decode_call_count"] == 4
    assert summary["positions_modified"] == prompt_len + 4
    assert [tuple(r.tensor_shape) for r in ledger.records] == [
        (1, prompt_len, 64),
        (1, 1, 64),
        (1, 1, 64),
        (1, 1, 64),
        (1, 1, 64),
    ]


def test_raw_hf_generation_outside_the_attach_context_fails_the_assertion(raw_backend, real_sae):
    """The sharpest control, carried onto the raw-HF path: the hook was
    built and the ledger held, generation ran outside the context, the
    continuation looks entirely normal, and the assertion refuses."""
    spec = gi.GroupSpec(
        kind="amplify", members=(gi.GroupMember(7),), alpha=50.0, hook_name="raw-hf.layers.1"
    )
    ledger = gi.FiringLedger()
    gi.build_group_hook(real_sae, spec, ledger=ledger)
    tokens = raw_backend.to_tokens(PROMPT)
    out = raw_backend.generate(
        tokens, max_new_tokens=4, do_sample=False, temperature=1.0, stop_at_eos=False
    )
    generated = int(out.shape[1]) - int(tokens.shape[1])
    with pytest.raises(gi.HookFiringMismatch, match="fired 0 time"):
        gi.assert_fired_as_expected(
            ledger,
            gi.expected_generation_firing(
                prompt_token_count=int(tokens.shape[1]),
                generated_token_count=generated,
                positions="all",
            ),
        )


def test_raw_hf_hook_is_removed_on_exit_even_when_the_body_raises(raw_backend, real_sae):
    """A hook left behind on a decoder layer would silently steer the NEXT
    arm, including the control. torch's handle has no finally guarantee of
    its own, so this module supplies the one HookedTransformer.hooks gives
    the other path for free."""
    spec = gi.GroupSpec(
        kind="amplify", members=(gi.GroupMember(7),), alpha=1.0, hook_name="raw-hf.layers.1"
    )
    ledger = gi.FiringLedger()
    with pytest.raises(RuntimeError, match="deliberate"), raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        raise RuntimeError("deliberate")
    tokens = raw_backend.to_tokens(PROMPT)
    with torch.no_grad():
        raw_backend.forward_logits(tokens)
    assert ledger.call_count == 0, "a hook survived the raising context and steered a later forward"


def test_raw_hf_alpha_zero_leaves_logits_bit_identical(raw_backend, real_sae):
    spec = gi.GroupSpec(
        kind="amplify",
        members=(gi.GroupMember(7), gi.GroupMember(64)),
        alpha=0.0,
        hook_name="raw-hf.layers.1",
    )
    tokens = raw_backend.to_tokens(PROMPT)
    with torch.no_grad():
        baseline = raw_backend.forward_logits(tokens)
    ledger = gi.FiringLedger()
    with torch.no_grad(), raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        steered = raw_backend.forward_logits(tokens)
    assert ledger.call_count == 1, "the hook must have fired"
    assert torch.equal(baseline, steered)


def test_raw_hf_noop_registers_no_hook(raw_backend, real_sae):
    tokens = raw_backend.to_tokens(PROMPT)
    with torch.no_grad():
        baseline = raw_backend.forward_logits(tokens)
    ledger = gi.FiringLedger()
    with torch.no_grad(), raw_backend.attach(
        real_sae, gi.GroupSpec.noop(), ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        control = raw_backend.forward_logits(tokens)
    assert ledger.call_count == 0
    assert torch.equal(baseline, control)


def test_raw_hf_out_of_range_and_duplicate_members_still_refuse(raw_backend, real_sae):
    """The membership refusals are the SAME code on both backends, because
    build_group_hook is shared rather than duplicated."""
    with pytest.raises(gi.FeatureNotInSAE):
        raw_backend.attach(
            real_sae,
            gi.GroupSpec(kind="amplify", members=(gi.GroupMember(9999),)),
            ledger=gi.FiringLedger(),
            prompt_lengths=None,
            verify_exact_delta=True,
        )
    with pytest.raises(gi.InvalidGroupSpec, match="more than once"):
        gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7), gi.GroupMember(7)))


def _capture_raw_residual(raw_backend):
    captured = {}
    handle = raw_backend.decoder_layer.register_forward_hook(
        lambda _m, _a, out: captured.__setitem__("resid", out.detach().clone())
    )
    try:
        with torch.no_grad():
            raw_backend.forward_logits(raw_backend.to_tokens(PROMPT))
    finally:
        handle.remove()
    return captured["resid"]


def test_raw_hf_all_dead_group_ablation_is_caught_as_a_silent_no_op(raw_backend, real_sae):
    residual = _capture_raw_residual(raw_backend)
    dead = _dead_real_features(real_sae, residual)
    assert len(dead) >= 3
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in dead),
        alpha=1.0,
        ablation_mechanism="subtract",
        hook_name="raw-hf.layers.1",
    )
    ledger = gi.FiringLedger()
    with torch.no_grad(), raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        raw_backend.forward_logits(raw_backend.to_tokens(PROMPT))
    assert ledger.call_count == 1
    with pytest.raises(gi.HookFiringMismatch, match="every injected delta was exactly zero"):
        gi.assert_fired_as_expected(ledger, gi.FiringExpectation(call_count=1))


def test_raw_hf_exact_delta_holds_on_the_real_residual_stream(raw_backend, real_sae):
    before = _capture_raw_residual(raw_backend)
    members = (gi.GroupMember(7, 1.0), gi.GroupMember(64, -0.5), gi.GroupMember(129, 2.0))
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=3.0, hook_name="raw-hf.layers.1")
    ledger = gi.FiringLedger()
    hook_fn, _ = gi.build_group_hook(real_sae, spec, ledger=ledger)
    after = hook_fn(before)
    expected = 3.0 * sum(m.weight * real_sae.W_dec[m.feature_index] for m in members)
    gi.assert_exact_delta(before, after, expected.detach())
    assert ledger.absorbed_element_count == 0, "float32 must absorb nothing"


def test_raw_hf_both_ablation_mechanisms_remain_separately_selectable(raw_backend, real_sae):
    residual = _capture_raw_residual(raw_backend)
    live = _live_features(real_sae, residual, limit=3)
    outs = {}
    for mechanism in gi.ABLATION_MECHANISMS:
        spec = gi.GroupSpec(
            kind="ablate",
            members=tuple(gi.GroupMember(i) for i in live),
            alpha=1.0,
            ablation_mechanism=mechanism,
            hook_name="raw-hf.layers.1",
        )
        ledger = gi.FiringLedger()
        hook_fn, _ = gi.build_group_hook(real_sae, spec, ledger=ledger)
        outs[mechanism] = hook_fn(residual)
    gap = (outs["reconstruct"] - outs["subtract"]).to(torch.float32)
    expected_gap = -gi.reconstruction_error(real_sae, residual)
    assert torch.allclose(gap, expected_gap, atol=1e-4)
    assert not torch.allclose(outs["reconstruct"], outs["subtract"], atol=1e-3)


def test_raw_hf_generated_only_never_steers_the_prefill(raw_backend, real_sae):
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(
        kind="amplify",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        positions="generated_only",
        hook_name="raw-hf.layers.1",
    )
    tokens = raw_backend.to_tokens(PROMPT)
    prompt_len = int(tokens.shape[1])
    ledger = gi.FiringLedger()
    with raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=prompt_len, verify_exact_delta=True
    ):
        out = raw_backend.generate(
            tokens, max_new_tokens=5, do_sample=False, temperature=1.0, stop_at_eos=False
        )
    generated = int(out.shape[1]) - prompt_len
    gi.assert_fired_as_expected(
        ledger,
        gi.expected_generation_firing(
            prompt_token_count=prompt_len,
            generated_token_count=generated,
            positions="generated_only",
        ),
    )
    assert ledger.records[0].positions_modified == 0


def test_raw_hf_run_arm_and_measure_group_effect_end_to_end(raw_backend, real_sae):
    live = _live_features(real_sae, torch.randn(1, 4, 64), limit=4)
    spec = gi.GroupSpec(
        kind="amplify",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=200.0,
        hook_name="raw-hf.layers.1",
        label="raw-hf-joint",
    )
    measurement = gi.measure_group_effect(
        raw_backend, real_sae, spec, [PROMPT], max_new_tokens=5, seed=17, device="cpu"
    )
    (row,) = measurement.per_prompt
    assert row["treatment_hook_call_count"] == 5
    assert row["treatment_total_delta_norm"] > 0.0
    assert row["treatment_absorbed_fraction"] == 0.0
    assert row["treatment_residual_dtypes"] == ["torch.float32"]
    assert measurement.control.results[0].firing["call_count"] == 0
    assert measurement.any_continuation_changed is True
    assert measurement.treatment.device_placement["decoder_layer"] == "cpu"


def test_raw_hf_device_gate_asserts_the_decoder_layer_separately(raw_backend, real_sae):
    """Under a device_map shard the model and the layer the hook runs on can
    differ; the raw-HF backend asserts both, not just the model."""
    placement = gi.assert_devices_before_forward(
        device="cpu", sae=real_sae, **raw_backend.device_objects()
    )
    assert set(placement) == {"model", "decoder_layer", "sae"}
    assert set(raw_backend.device_objects()) == {"model", "decoder_layer"}
    with pytest.raises(Exception) as excinfo:
        gi.assert_devices_before_forward(
            device="cuda:0", sae=real_sae, **raw_backend.device_objects()
        )
    assert "cuda" in str(excinfo.value).lower()


def test_both_backends_share_one_hook_implementation():
    """Structural: the two pairings cannot drift apart in what they compute,
    because there is only one implementation to drift."""
    import inspect

    assert "attach_group_hook(" in inspect.getsource(gi.HookedTransformerBackend.attach)
    assert "attach_group_hook_raw_hf(" in inspect.getsource(gi.RawHfBackend.attach)
    assert "build_group_hook" in inspect.getsource(gi.attach_group_hook)
    assert "build_group_hook" in inspect.getsource(gi.attach_group_hook_raw_hf)


def test_raw_hf_backend_records_an_honest_hook_label(raw_backend, real_sae):
    """The SAE declares a TransformerLens hook name this backend does not
    have. Recording it would put a hook point in the provenance that never
    existed in the process."""
    spec = gi.GroupSpec(kind="amplify", members=(gi.GroupMember(7),), alpha=1.0)
    assert spec.hook_name is None
    ledger = gi.FiringLedger()
    with torch.no_grad(), raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        raw_backend.forward_logits(raw_backend.to_tokens(PROMPT))
    assert ledger.records[0].hook_name == "raw_hf.model.layers.1"
    assert real_sae.cfg.metadata.hook_name == "blocks.1.hook_resid_post"


def test_raw_hf_backend_does_not_override_an_explicit_hook_name(raw_backend, real_sae):
    spec = gi.GroupSpec(
        kind="amplify", members=(gi.GroupMember(7),), alpha=1.0, hook_name="caller-chose-this"
    )
    ledger = gi.FiringLedger()
    with torch.no_grad(), raw_backend.attach(
        real_sae, spec, ledger=ledger, prompt_lengths=None, verify_exact_delta=True
    ):
        raw_backend.forward_logits(raw_backend.to_tokens(PROMPT))
    assert ledger.records[0].hook_name == "caller-chose-this"


# ---------------------------------------------------------------------------
# RULING_13 LAYER.
#
# The architect ruled SUBTRACT the instrument and named three defects in the
# COMMITTED bundle path (`_bundle_hook_fn` / `run_intervention` in
# final_pairing_concept_discovery.py, which this lane does not edit). The
# tests below are the EVIDENCE that this module does not share them, plus the
# new requirements the ruling adds.
# ---------------------------------------------------------------------------


def _clamp_hook_delta(sae, feature_index, residual):
    """The existing single-feature primitive's delta, at clamp value 0."""
    from interplab.interventions.hooks import _make_clamp_hook

    return _make_clamp_hook(sae, feature_index, 0.0, "all", None, [])(residual, None) - residual


def test_my_subtract_is_the_existing_clamp_hook_generalised_not_a_second_implementation(
    real_sae, real_model, real_tokens
):
    """RECONCILIATION. RULING_13 Q3.1: hooks.py's decode-difference form
    ALREADY IS decoder subtraction -- for an affine decoder both the bias
    and the reconstruction error cancel in the difference. So this module
    must not be a second, subtly different subtract. Measured on LIVE
    features (a dead feature would agree trivially and prove nothing)."""
    with torch.no_grad():
        _, cache = real_model.run_with_cache(real_tokens, names_filter="blocks.1.hook_resid_post")
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=4)
    for feature in live:
        theirs = _clamp_hook_delta(real_sae, feature, residual)
        spec = gi.GroupSpec(
            kind="ablate",
            members=(gi.GroupMember(feature),),
            alpha=1.0,
            ablation_mechanism="subtract",
        )
        mine = gi.ablate_subtract_delta(real_sae, gi.resolve_group(real_sae, spec), residual)
        # Scaled to the residual rather than an absolute constant: a dead
        # feature would make both sides exactly zero and the agreement
        # meaningless, which is the only thing this guard is for.
        assert float(mine.norm()) > 1e-3 * float(residual.norm()), (
            f"feature {feature} is inert on this residual; the comparison proves nothing"
        )
        assert torch.allclose(theirs, mine, atol=1e-5), f"feature {feature}"


def test_group_subtract_equals_the_sum_of_single_feature_clamp_hook_deltas(
    real_sae, real_model, real_tokens
):
    """The group generalisation is exactly the SIMULTANEOUS form: every
    member's activation read from the ONE clean residual. Against the
    existing primitive, that means the group delta equals the sum of the
    per-member deltas each computed on the CLEAN residual -- which is NOT
    what sequential chaining produces (next test)."""
    with torch.no_grad():
        _, cache = real_model.run_with_cache(real_tokens, names_filter="blocks.1.hook_resid_post")
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=3)
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        ablation_mechanism="subtract",
    )
    group_delta = gi.ablate_subtract_delta(real_sae, gi.resolve_group(real_sae, spec), residual)
    clean_sum = sum(_clamp_hook_delta(real_sae, i, residual) for i in live)
    assert torch.allclose(group_delta, clean_sum, atol=1e-5)


def test_group_composition_is_order_invariant_and_sequential_chaining_is_not(
    real_sae, real_model, real_tokens
):
    """RULING_13 D2, checked BOTH ways.

    A GROUP IS A SET; A SET HAS NO ORDER. This module composes
    simultaneously, so permuting the members changes nothing beyond float32
    noise. The committed path's sequential form (`out = inner(out, hook)`)
    is measured alongside it and is order-dependent by orders of magnitude
    -- that contrast is what makes the first assertion meaningful rather
    than a tautology about a single code path."""
    import itertools

    with torch.no_grad():
        _, cache = real_model.run_with_cache(real_tokens, names_filter="blocks.1.hook_resid_post")
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=3)

    simultaneous = []
    for order in itertools.permutations(live):
        spec = gi.GroupSpec(
            kind="ablate",
            members=tuple(gi.GroupMember(int(i)) for i in order),
            alpha=1.0,
            ablation_mechanism="subtract",
        )
        ledger = gi.FiringLedger()
        hook_fn, _ = gi.build_group_hook(real_sae, spec, ledger=ledger)
        simultaneous.append(hook_fn(residual))
    simultaneous_spread = max(
        float((out - simultaneous[0]).abs().max()) for out in simultaneous
    )

    from interplab.interventions.hooks import _make_clamp_hook

    def chained(order):
        out = residual
        for feature in order:
            out = _make_clamp_hook(real_sae, int(feature), 0.0, "all", None, [])(out, None)
        return out

    sequential = [chained(order) for order in itertools.permutations(live)]
    sequential_spread = max(float((out - sequential[0]).abs().max()) for out in sequential)

    # Compared to each other and to the intervention's own magnitude, not to
    # absolute constants: the point is the CONTRAST, and an absolute bound
    # would silently stop discriminating if the fixture's scale changed.
    delta_scale = float((simultaneous[0] - residual).abs().max())
    assert simultaneous_spread < 1e-3 * delta_scale, (
        "this module's group composition is order-dependent"
    )
    assert sequential_spread > 0.1 * delta_scale, (
        "sequential chaining did not show order dependence here, so this contrast proves nothing"
    )
    assert not torch.allclose(simultaneous[0], sequential[0], atol=1e-3), (
        "simultaneous and sequential composition are genuinely different operations"
    )


def test_group_activations_are_read_from_the_clean_residual(synthetic_sae, synthetic_residual):
    """RULING_13 D2 consequence_b, the moving-reference defect: iterated
    removal measures a2 against an ALREADY-ALTERED residual. This module
    encodes once, so every member's activation is the clean one."""
    spec = gi.GroupSpec(
        kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="subtract"
    )
    resolved = gi.resolve_group(synthetic_sae, spec)
    acts = gi.group_activations(synthetic_sae, resolved, synthetic_residual)
    clean_feats = synthetic_sae.encode(synthetic_residual)
    for position, member in enumerate(GROUP):
        assert torch.allclose(acts[..., position], clean_feats[..., member.feature_index])


def test_firing_evidence_is_retained_at_every_group_size(synthetic_sae, synthetic_residual):
    """RULING_13 D1 EVIDENCE. The committed bundle path builds each inner
    hook with an EMPTY stats list, so for k > 1 there is no firing record at
    all. Here the ledger is the SAME object at every k, and the recorded
    delta_norm is the group's own -- the evidence does not thin out as the
    group grows, which is precisely where groups are the point."""
    norms = {}
    for size in (1, 2, 3):
        spec = gi.GroupSpec(
            kind="ablate",
            members=GROUP[:size],
            alpha=1.0,
            ablation_mechanism="subtract",
        )
        ledger = gi.FiringLedger()
        hook_fn, _ = gi.build_group_hook(synthetic_sae, spec, ledger=ledger)
        hook_fn(synthetic_residual)
        assert ledger.call_count == 1, f"k={size} recorded no firing"
        assert ledger.records[0].delta_norm > 0.0, f"k={size} recorded a zero delta"
        assert ledger.records[0].positions_modified > 0
        norms[size] = ledger.total_delta_norm
    assert norms[3] != norms[1], "the recorded delta must be the GROUP's, not one member's"


# --- the clamp dose form (RULING_13 Q3.6) -----------------------------------


def test_clamp_dose_requires_a_per_member_corpus_max():
    """RULING_13 D3, made structurally impossible. The committed path
    derives ONE absolute value from `corpus_max[feature_indices[0]]` and
    applies it to every member."""
    with pytest.raises(gi.InvalidGroupSpec, match="requires a per-member corpus_max"):
        gi.GroupSpec(
            kind="amplify",
            members=(gi.GroupMember(3, corpus_max=2.0), gi.GroupMember(7)),
            alpha=1.0,
            dose_form="clamp",
        )


def test_clamp_dose_is_in_each_members_own_max_units(synthetic_sae, synthetic_residual):
    """Two members with different scales get different absolute targets from
    the same `alpha`, which is what 'the same dose' has to mean when
    features have different activation scales."""
    members = (gi.GroupMember(3, corpus_max=2.0), gi.GroupMember(7, corpus_max=50.0))
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=0.5, dose_form="clamp")
    resolved = gi.resolve_group(synthetic_sae, spec)
    assert resolved.clamp_targets.tolist() == [1.0, 25.0]


def test_clamp_dose_delta_matches_an_independent_closed_form(synthetic_sae, synthetic_residual):
    """h + sum_f (target_f - a_f(h)) * W_dec[f], recomputed here member by
    member rather than by calling the module's own vectorised path."""
    members = (gi.GroupMember(3, corpus_max=2.0), gi.GroupMember(7, corpus_max=5.0))
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=2.0, dose_form="clamp")
    out, ledger, _resolved = _apply(synthetic_sae, spec, synthetic_residual)
    feats = synthetic_sae.encode(synthetic_residual)
    expected = torch.zeros_like(synthetic_residual)
    for member in members:
        target = 2.0 * member.corpus_max
        shortfall = target - feats[..., member.feature_index : member.feature_index + 1]
        expected = expected + shortfall * synthetic_sae.W_dec[member.feature_index]
    assert torch.allclose(out - synthetic_residual, expected, atol=1e-5)
    assert ledger.call_count == 1


def test_clamp_to_the_current_activation_is_an_exact_no_op(synthetic_sae, synthetic_residual):
    """The identity the clamp form must satisfy: target_f == a_f(h) leaves
    the stream where it was, with no reconstruction error introduced."""
    feats = synthetic_sae.encode(synthetic_residual)
    # A residual whose group activations are constant across positions, so a
    # single scalar target can equal them exactly.
    flat = synthetic_residual[:1, :1]
    feats_flat = synthetic_sae.encode(flat)
    members = tuple(
        gi.GroupMember(m.feature_index, corpus_max=float(feats_flat[0, 0, m.feature_index]))
        for m in GROUP
    )
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=1.0, dose_form="clamp")
    out, _, _ = _apply(synthetic_sae, spec, flat)
    assert torch.allclose(out, flat, atol=1e-5)
    assert feats.shape[-1] == synthetic_sae.d_sae


def test_clamp_dose_acts_where_the_group_is_silent(synthetic_sae, synthetic_residual):
    """The hazard RULING_13 Q3.6 names: a MULTIPLICATIVE dose is identically
    zero where the group is silent, so it cannot induce a concept on the
    eliciting prompts a sufficiency criterion depends on. The clamp form
    delivers the full target there. This module offers no multiplicative
    form at all."""
    dead = gi._dead_features(synthetic_sae, synthetic_residual)
    assert dead, "need a silent feature for this test to mean anything"
    member = gi.GroupMember(dead[0], corpus_max=4.0)
    acts = synthetic_sae.encode(synthetic_residual)[..., dead[0]]
    assert float(acts.abs().max()) == 0.0
    spec = gi.GroupSpec(kind="amplify", members=(member,), alpha=1.0, dose_form="clamp")
    out, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual)
    expected = 4.0 * synthetic_sae.W_dec[dead[0]]
    assert torch.allclose(out - synthetic_residual, expected.expand_as(out), atol=1e-5)
    assert ledger.max_abs_delta > 0.0


def test_clamp_dose_form_is_rejected_for_ablation():
    with pytest.raises(gi.InvalidGroupSpec, match="defined for kind='amplify'"):
        gi.GroupSpec(
            kind="ablate",
            members=(gi.GroupMember(3, corpus_max=1.0),),
            ablation_mechanism="subtract",
            dose_form="clamp",
        )


def test_clamp_at_alpha_zero_is_not_reported_as_an_identity():
    """Clamping a group to zero is an ABLATION -- the most active thing this
    module does. Reporting it as a null configuration would have made the
    strongest available intervention describe itself as a control."""
    spec = gi.GroupSpec(
        kind="amplify",
        members=(gi.GroupMember(3, corpus_max=2.0),),
        alpha=0.0,
        dose_form="clamp",
    )
    assert gi.null_configuration_is_exact_identity(spec) is False


def test_expected_amplify_delta_refuses_for_a_clamp_spec(synthetic_sae):
    spec = gi.GroupSpec(
        kind="amplify", members=(gi.GroupMember(3, corpus_max=1.0),), dose_form="clamp"
    )
    resolved = gi.resolve_group(synthetic_sae, spec)
    with pytest.raises(gi.InvalidGroupSpec, match="depends on the residual"):
        resolved.expected_amplify_delta()


def test_leave_one_out_preserves_dose_form_and_per_member_scales():
    """The `replace`-based implementation: a field added later must not be
    silently dropped from every minimality arm, which would make the sweep
    run a different intervention from the joint one."""
    members = (
        gi.GroupMember(3, corpus_max=2.0),
        gi.GroupMember(7, corpus_max=5.0),
        gi.GroupMember(11, corpus_max=9.0),
    )
    spec = gi.GroupSpec(kind="amplify", members=members, alpha=1.5, dose_form="clamp")
    for arm in gi.leave_one_out_specs(spec):
        assert arm.dose_form == "clamp"
        assert arm.alpha == 1.5
        assert all(m.corpus_max is not None for m in arm.members)


# --- positions must be stated for ablation (RULING_13 Q3.8) -----------------


def test_ablation_with_generated_only_must_state_the_choice():
    with pytest.raises(gi.InvalidGroupSpec, match="must be STATED, not defaulted"):
        gi.GroupSpec(
            kind="ablate",
            members=GROUP,
            ablation_mechanism="subtract",
            positions="generated_only",
        )


def test_ablation_with_generated_only_is_allowed_once_acknowledged():
    spec = gi.GroupSpec(
        kind="ablate",
        members=GROUP,
        ablation_mechanism="subtract",
        positions="generated_only",
        acknowledge_prompt_positions_unablated=True,
    )
    assert spec.to_dict()["acknowledge_prompt_positions_unablated"] is True


def test_the_acknowledgement_cannot_be_set_where_no_choice_was_made():
    with pytest.raises(gi.InvalidGroupSpec, match="records a choice that was never made"):
        gi.GroupSpec(kind="amplify", members=GROUP, acknowledge_prompt_positions_unablated=True)


# --- mechanism (a) demotion and its control (RULING_13 Q3.3/Q3.9) ----------


def test_a_reconstruct_result_may_not_be_paired_with_an_unhooked_control(real_model, real_sae):
    """REFUSED, not caveated. Under (a) an empty group already moves the
    residual by the whole reconstruction error, so this pairing would credit
    SAE fidelity to the group."""
    spec = gi.GroupSpec(
        kind="ablate",
        members=(gi.GroupMember(7),),
        alpha=1.0,
        ablation_mechanism="reconstruct",
    )
    with pytest.raises(gi.InvalidGroupSpec, match="may NOT be read against control"):
        gi.measure_group_effect(
            real_model, real_sae, spec, [PROMPT], max_new_tokens=3, seed=1, device="cpu"
        )


def test_a_reconstruct_result_is_admissible_against_the_reconstruction_only_arm():
    spec = gi.GroupSpec(
        kind="ablate",
        members=(gi.GroupMember(7),),
        alpha=1.0,
        ablation_mechanism="reconstruct",
    )
    gi.assert_control_is_admissible(spec, gi.GroupSpec.reconstruction_control())


def test_subtract_results_may_use_the_ordinary_noop_control():
    spec = gi.GroupSpec(
        kind="ablate", members=GROUP, alpha=1.0, ablation_mechanism="subtract"
    )
    gi.assert_control_is_admissible(spec, gi.GroupSpec.noop())


def test_subtract_is_recorded_as_the_ruled_instrument():
    assert gi.RULED_INSTRUMENT_MECHANISM == "subtract"


def test_fidelity_context_separates_the_two_ratios(real_sae, real_model, real_tokens):
    """RULING_13 Q3.9 guards the signal-to-artifact ratio from being read as
    a statement about SAE quality. The two quantities are reported under
    separate names because the first gets carried into claims only the
    second could support."""
    with torch.no_grad():
        _, cache = real_model.run_with_cache(real_tokens, names_filter="blocks.1.hook_resid_post")
    residual = cache["blocks.1.hook_resid_post"]
    live = _live_features(real_sae, residual, limit=3)
    reference = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in live),
        alpha=1.0,
        ablation_mechanism="subtract",
    )
    context = gi.measure_sae_fidelity_context(
        real_sae, residual, hook_point="blocks.1.hook_resid_post", reference_spec=reference
    )
    assert context["measured_once_per"] == "(model, sae, hook_point)"
    assert context["ruled_instrument"] == "subtract"
    assert context["reconstruction_error_over_residual"] > 0.0
    assert context["signal_to_artifact_ratio_for_mechanism_a"] > 0.0
    # They are DIFFERENT numbers; conflating them is the prohibited over-read.
    assert context["reconstruction_error_over_residual"] != pytest.approx(
        context["signal_to_artifact_ratio_for_mechanism_a"], rel=1e-6
    )
    assert "PROHIBITED" in context["prohibited_readings"]


def test_fidelity_context_needs_no_reference_group():
    """It is a constant of the SAE, so it is computable with no group at
    all -- which is the whole reason it runs once rather than per arm."""
    sae = gi._SyntheticSAE()
    torch.manual_seed(1)
    context = gi.measure_sae_fidelity_context(
        sae, torch.randn(1, 3, 16), hook_point="synthetic"
    )
    assert context["signal_to_artifact_ratio_for_mechanism_a"] is None
    assert context["reconstruction_error_over_residual"] > 0.0


# --- VOID is not a NULL -----------------------------------------------------


def test_never_fired_is_classified_NOT_EXERCISED(synthetic_sae):
    spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=1.0)
    assert gi.classify_intervention_state(spec, gi.FiringLedger()) == "NOT_EXERCISED"


def test_fired_with_a_zero_delta_is_FIRED_BUT_INERT(synthetic_sae, synthetic_residual):
    dead = gi._dead_features(synthetic_sae, synthetic_residual)
    spec = gi.GroupSpec(
        kind="ablate",
        members=tuple(gi.GroupMember(i) for i in dead[:2]),
        alpha=1.0,
        ablation_mechanism="subtract",
    )
    _, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual)
    assert gi.classify_intervention_state(spec, ledger) == "FIRED_BUT_INERT"


def test_a_real_intervention_is_APPLIED(synthetic_sae, synthetic_residual):
    spec = gi.GroupSpec(kind="amplify", members=GROUP, alpha=2.0)
    _, ledger, _ = _apply(synthetic_sae, spec, synthetic_residual)
    assert gi.classify_intervention_state(spec, ledger) == "APPLIED"


def test_the_noop_arm_is_CONTROL_not_a_void_result(synthetic_sae):
    assert gi.classify_intervention_state(gi.GroupSpec.noop(), gi.FiringLedger()) == "CONTROL"


@pytest.mark.parametrize("state", ["CONTROL", "NOT_EXERCISED", "FIRED_BUT_INERT"])
def test_void_states_are_not_readable_as_results(state):
    row = gi.PromptResult(
        prompt="p", prompt_token_count=1, generated_token_count=1, generated_token_ids=(1,),
        full_text="", generated_text="", per_token_logprob=None, sum_logprob=None,
        firing={}, firing_expectation={}, intervention_state=state,
    )
    assert row.outcome_is_readable_as_a_result is False
    assert "NOT A NULL" in row.to_dict()["intervention_state_meaning"] or state == "CONTROL"


def test_run_arm_records_the_intervention_state(real_model, real_sae):
    live = _live_features(real_sae, torch.randn(1, 4, 64))
    spec = gi.GroupSpec(kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=25.0)
    arm = gi.run_arm(
        real_model, real_sae, spec, [PROMPT], max_new_tokens=3, seed=3, device="cpu"
    )
    assert arm.intervention_states == ("APPLIED",)
    assert arm.void_prompt_count == 0
    assert arm.results[0].outcome_is_readable_as_a_result is True
    control = gi.run_arm(
        real_model, real_sae, gi.GroupSpec.noop(), [PROMPT], max_new_tokens=3, seed=3, device="cpu"
    )
    assert control.intervention_states == ("CONTROL",)
    assert control.results[0].outcome_is_readable_as_a_result is False


def test_measure_group_effect_carries_the_state_next_to_the_identity_flag(real_model, real_sae):
    """`token_ids_identical` is exactly the field a reader turns into 'the
    concept was not steerable', so the state that would make it meaningless
    travels in the same row."""
    live = _live_features(real_sae, torch.randn(1, 4, 64), limit=3)
    spec = gi.GroupSpec(kind="amplify", members=tuple(gi.GroupMember(i) for i in live), alpha=200.0)
    measurement = gi.measure_group_effect(
        real_model, real_sae, spec, [PROMPT], max_new_tokens=4, seed=5, device="cpu"
    )
    (row,) = measurement.per_prompt
    assert row["treatment_intervention_state"] == "APPLIED"
    assert row["outcome_is_readable_as_a_result"] is True
    assert "token_ids_identical" in row


def test_no_threshold_or_margin_is_defined_anywhere_in_the_module():
    """RULING_13: the success criterion comes from a control-only
    calibration performed by a lane that does not select the group. This
    module must not invent one, and must not acquire one later."""
    import inspect

    source = inspect.getsource(gi)
    for forbidden in ("MARGIN", "SUCCESS_THRESHOLD", "PASS_THRESHOLD", "CEILING"):
        assert forbidden not in source, f"{forbidden} appeared; thresholds are not this lane's to set"
    assert gi.classify_intervention_state.__doc__ is not None
    assert "no threshold" in gi.classify_intervention_state.__doc__.lower()
