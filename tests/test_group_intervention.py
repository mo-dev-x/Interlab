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


def test_raw_hf_path_raises_rather_than_falling_back():
    """A fallback that silently hooked nothing is precisely the never-fires
    failure this module exists to make impossible."""
    with pytest.raises(NotImplementedError, match="not implemented"):
        gi.attach_group_hook_raw_hf()


def test_attach_on_a_model_without_hooks_raises(synthetic_sae):
    with pytest.raises(gi.GroupInterventionError, match=r"has no `\.hooks"):
        gi.attach_group_hook(
            object(),
            synthetic_sae,
            gi.GroupSpec(kind="amplify", members=GROUP),
            ledger=gi.FiringLedger(),
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
