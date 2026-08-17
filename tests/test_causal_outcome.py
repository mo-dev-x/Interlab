"""Tests for the outcome measure and the firing precondition that gates it.

WHAT THESE TESTS DO NOT DO: assert any margin, threshold, ceiling or band as
correct. There are none to assert -- they come from a control-only calibration
that has no controls to run on, and supplying one here so a test could assert it
is exactly the invention the ruling forbids. Every band in this file arrives as
a synthetic fixture whose only job is to make the ARITHMETIC and the REFUSALS
exercisable, and it is named so in the fixture.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_PAIRING = REPO_ROOT / "scripts" / "final_pairing"
sys.path.insert(0, str(FINAL_PAIRING))

import causal_outcome as co  # noqa: E402

PERSONA_A, PERSONA_B = co.PERSONA_CONCEPT_IDS


def synthetic_rubric(**overrides: object) -> co.RubricAttestation:
    """A rubric that exists ONLY to exercise arithmetic. Not a real rubric.

    Every field that a real attestation would have to earn is filled with a
    string that says so, so that a copy of this fixture cannot be mistaken for
    a sanctioned instrument."""
    payload: dict[str, object] = {
        "rubric_id": "SYNTHETIC-NOT-A-REAL-RUBRIC",
        "rubric_version": "0.0.0",
        "digest": "a" * 64,
        "scale_min": 0.0,
        "scale_max": 6.0,
        "resolution": 1.0,
        "composition": co.COMPOSITION_SIGNED_DIFFERENCE,
        "anchors_digest": "b" * 64,
        "rank_reliability_evidence": "reports/SYNTHETIC_no_rank_reliability_measured.md@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        "sanctioned_by": "SYNTHETIC: nothing sanctions this; see OUTCOME_MEASURE_REFERRAL",
        "authored_by": "test_fixture",
    }
    payload.update(overrides)
    return co.load_rubric_attestation(payload)


def synthetic_bands(**overrides: object) -> co.OutcomeBands:
    payload: dict[str, object] = {
        "neutral_low": -1.0,
        "neutral_high": 1.0,
        "assertion_floor": 4.0,
        "calibration_digest": "c" * 64,
        "derivation": "SYNTHETIC test band; a real one is derived from controls only",
    }
    payload.update(overrides)
    return co.OutcomeBands(**payload)  # type: ignore[arg-type]


def evidence(**overrides: object) -> co.FiringEvidence:
    payload: dict[str, object] = {
        "intervention_state": "APPLIED",
        "hook_call_count": 3,
        "total_delta_norm": 1.5,
        "max_abs_delta": 0.4,
        "absorbed_element_count": 0,
        "requested_nonzero_element_count": 160,
        "residual_dtypes": ("torch.bfloat16",),
        "evaluated_member_doses": (2.0, 3.0),
        "post_intervention_member_latents": (2.0, 3.0),
    }
    payload.update(overrides)
    return co.FiringEvidence(**payload)  # type: ignore[arg-type]


def control_evidence() -> co.FiringEvidence:
    return co.FiringEvidence(
        intervention_state="CONTROL",
        hook_call_count=0,
        total_delta_norm=0.0,
        max_abs_delta=0.0,
        absorbed_element_count=0,
        requested_nonzero_element_count=0,
        residual_dtypes=("torch.bfloat16",),
        evaluated_member_doses=(),
        post_intervention_member_latents=(),
    )


def reading(own: float, mirror: float, rubric: co.RubricAttestation) -> co.BipolarReading:
    return co.BipolarReading(
        own=co.PoleReading(PERSONA_A, own, rubric),
        mirror=co.PoleReading(PERSONA_B, mirror, rubric),
    )


# ---------------------------------------------------------------- no numbers


#: The ONLY module-level numbers permitted in causal_outcome.py: the scale
#: ANCHORS the architect fixed at RULING_15 R1 clause 5. They are identities,
#: not thresholds this lane chose -- `scale_min` in particular is fixed there
#: BECAUSE this module makes ASSERTS_NEITHER unreachable at any other value.
PERMITTED_ANCHOR_CONSTANTS = {
    "CLAIM_TYPE_EXTENT_SCALE_MIN",
    "CLAIM_TYPE_EXTENT_LATTICE_STEP",
}


def test_the_module_declares_no_numeric_decision_boundary():
    """No margin, ceiling, band or dose may be a literal in this file.

    Asserted over the AST rather than by reading, because "I looked and there
    were none" is the class of check this sprint keeps finding to be wrong. The
    R1 anchors are allow-listed BY NAME so that adding any other number fails."""
    tree = ast.parse((FINAL_PAIRING / "causal_outcome.py").read_bytes().decode("utf-8"))
    offenders: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in PERMITTED_ANCHOR_CONSTANTS:
                    offenders.append(f"{target.id} = {node.value.value}")
    assert offenders == [], (
        f"module-level numeric constant(s) {offenders}: a boundary hardcoded here would not be a "
        f"control-only calibration, whatever its comment said"
    )


def test_the_anchors_are_the_ruled_identities_and_are_enforced_by_the_loader():
    """R1 clause 5 / DEFECT 3, both directions."""
    assert co.CLAIM_TYPE_EXTENT_SCALE_MIN == 0.0
    assert co.CLAIM_TYPE_EXTENT_SCALE_MAX == 6.0 == float(len(co.FROZEN_CLAIM_TYPES))
    assert co.FROZEN_CLAIM_TYPES == ("HD", "ML", "CC", "SIA", "MFO", "SE")
    assert co.CLAIM_TYPE_EXTENT_LATTICE_STEP == 1.0
    assert co.CLAIM_TYPE_EXTENT_POINTS_PER_REFERENT == 7
    assert co.CLAIM_TYPE_EXTENT_DIFFERENCE_POINTS == 13
    # DOES NOT FIRE on the ruled anchors.
    assert synthetic_rubric().scale_min == 0.0
    # FIRES on anything else, and the message says why scale_min is load-bearing.
    with pytest.raises(co.OrdinalScaleViolation) as caught:
        synthetic_rubric(scale_min=1.0, scale_max=7.0)
    assert "UNREACHABLE BY CONSTRUCTION" in str(caught.value)
    with pytest.raises(co.OrdinalScaleViolation):
        synthetic_rubric(scale_max=5.0)
    with pytest.raises(co.OrdinalScaleViolation) as caught:
        synthetic_rubric(resolution=0.5)
    assert "one lattice step" in str(caught.value)


def test_a_scale_min_above_zero_would_make_ASSERTS_NEITHER_unreachable():
    """DEFECT 3 demonstrated as ARITHMETIC, not asserted as a rule.

    Shows WHY the loader refuses it: with a minimum above zero the assertion
    level is strictly positive for every possible generation, so the branch
    deciding ASSERTS_NEITHER can never be taken."""
    minimum_above_zero = 1.0
    lowest_possible_assertion_level = 2 * minimum_above_zero
    assert lowest_possible_assertion_level > 0.0, (
        "if this were ever false the class would be reachable and the anchor would be taste"
    )
    assert co.CLAIM_TYPE_EXTENT_SCALE_MIN * 2 == 0.0


def test_no_code_symbol_is_named_for_force():
    """R1 clause 8 / DEFECT 1. The prohibited words may appear only as citations
    of the frozen field name or of the prohibition itself, never as symbols."""
    source = (FINAL_PAIRING / "causal_outcome.py").read_bytes().decode("utf-8")
    tree = ast.parse(source)
    named: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            named.append(node.name)
        elif isinstance(node, ast.Name):
            named.append(node.id)
        elif isinstance(node, ast.arg):
            named.append(node.arg)
        elif isinstance(node, ast.Attribute):
            named.append(node.attr)
    for word in co.FORCE_WORDS_PROHIBITED:
        token = word.replace(" ", "_")
        offenders = sorted({name for name in named if token in name.lower()})
        offenders = [name for name in offenders if name != "FORCE_WORDS_PROHIBITED"]
        assert offenders == [], f"code symbol(s) named for force: {offenders} (word {word!r})"
    assert "extent" in named


def test_the_referral_names_the_frozen_artifacts_it_rests_on():
    """The referral has to be checkable by a reader, so it cites bytes."""
    referral = co.OUTCOME_MEASURE_REFERRAL
    for citation in (
        "concept_description_persona_exceptionalism.json",
        "MIRROR_LAW.intensity_parity",
        "RESIDUAL_ASYMMETRIES.3",
        "a10d_judging_readiness.json",
    ):
        assert citation in referral, f"the referral does not cite {citation}"
    assert (FINAL_PAIRING.parents[1] / co.FROZEN_DESCRIPTION_PATH).is_file()


def test_the_frozen_description_really_says_intensity_is_not_checkable():
    """The referral's load-bearing premise, read off the frozen bytes.

    If this ever fails, the referral is wrong and must be withdrawn -- which is
    why it is a test and not a sentence in a docstring."""
    import json

    description = json.loads(
        (FINAL_PAIRING.parents[1] / co.FROZEN_DESCRIPTION_PATH).read_bytes().decode("utf-8")
    )
    enforcement = description["MIRROR_LAW"]["intensity_parity"]["enforcement"]
    assert "NOT MECHANICALLY CHECKABLE" in enforcement
    residual = description["RESIDUAL_ASYMMETRIES"]["3_INTENSITY_PARITY_IS_NOT_MECHANICALLY_CHECKABLE"]
    assert "superlative strength is not" in residual["the_asymmetry"]
    binding = description["binding_for_this_document"]
    assert set(binding["describes_concepts"]) == set(co.PERSONA_CONCEPT_IDS)
    # The admission tests are a CONJUNCTION OF BINARY TESTS -- the premise of
    # the referral. If a later revision adds an ordinal, the referral changes.
    assert set(description["ADMISSION_TESTS"]) == {
        "how_to_use",
        "T1_SUBJECT",
        "T2_VOICE",
        "T3_PREDICATE",
        "T4_NO_NAMED_TARGET",
        "T5_CLAIM_TYPE",
        "T6_FACTUAL_FLOOR",
    }
    assert "ALL SIX must pass" in description["ADMISSION_TESTS"]["how_to_use"]


# ------------------------------------------------------------- the attestation


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sanctioned_by", "   "),
        ("rank_reliability_evidence", ""),
        ("rubric_id", ""),
        ("authored_by", " "),
        ("digest", "not-a-digest"),
        ("anchors_digest", "A" * 64),
        ("composition", "whatever_i_felt_like"),
    ],
)
def test_an_unattested_rubric_refuses(field: str, value: object):
    with pytest.raises((co.OutcomeMeasureNotSanctioned, co.OrdinalScaleViolation)):
        synthetic_rubric(**{field: value})


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        ({"scale_min": 3.0, "scale_max": 3.0}, "no span"),
        ({"resolution": 0.0}, "zero resolution"),
        ({"resolution": -1.0}, "negative resolution"),
        ({"resolution": 99.0}, "resolution wider than the scale"),
    ],
)
def test_an_unusable_ordinal_scale_refuses(overrides: dict, why: str):
    with pytest.raises(co.OrdinalScaleViolation):
        synthetic_rubric(**overrides)


def test_a_loader_refuses_unknown_and_missing_keys():
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.load_rubric_attestation({"rubric_id": "x"})
    payload = synthetic_rubric().to_dict()
    payload.pop("span")
    payload["surprise"] = 1
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.load_rubric_attestation(payload)


FIVE_LANES = {
    "description_author": "pm",
    "corpus_author": "corpus_author",
    "selecting_lane": "engineer2",
    "calibrating_lane": "researcher",
    "generating_lane": "engineer1",
}


def test_the_exclusion_set_is_exactly_the_five_ruled_roles():
    assert co.INSTRUMENT_AUTHOR_EXCLUSIONS == (
        "description_author",
        "corpus_author",
        "selecting_lane",
        "calibrating_lane",
        "generating_lane",
    )
    assert set(co.INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS) == set(co.INSTRUMENT_AUTHOR_EXCLUSIONS)
    assert "NEW at RULING_15" in co.INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS["generating_lane"]


@pytest.mark.parametrize("role", list(FIVE_LANES))
def test_each_of_the_five_exclusions_FIRES_on_its_own_role(role: str):
    """RULING_15 R3 clause 3: five, not two, and each must be able to fail.
    The fifth -- the lane that GENERATES the continuations -- is new, and a lane
    that both steers and scores can make its own steering succeed."""
    rubric = synthetic_rubric(authored_by=FIVE_LANES[role].upper())
    with pytest.raises(co.OutcomeMeasureNotSanctioned) as caught:
        co.assert_separation_of_duties(rubric, **FIVE_LANES)
    assert role in str(caught.value)


def test_the_separation_DOES_NOT_fire_on_an_uninvolved_author():
    record = co.assert_separation_of_duties(
        synthetic_rubric(authored_by="conformance"), **FIVE_LANES
    )
    assert record["separation"] == "SATISFIED"
    assert record["exclusions_checked"] == list(co.INSTRUMENT_AUTHOR_EXCLUSIONS)


def test_an_unenforceable_separation_refuses_rather_than_passing_vacuously():
    for role in FIVE_LANES:
        blanked = dict(FIVE_LANES, **{role: "  "})
        with pytest.raises(co.OutcomeMeasureNotSanctioned) as caught:
            co.assert_separation_of_duties(synthetic_rubric(), **blanked)
        assert "vacuously" in str(caught.value)
    with pytest.raises(co.OutcomeMeasureNotSanctioned) as caught:
        co.assert_separation_of_duties(
            synthetic_rubric(), **{k: v for k, v in FIVE_LANES.items() if k != "generating_lane"}
        )
    assert "generating_lane" in str(caught.value)
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.assert_separation_of_duties(synthetic_rubric(), **FIVE_LANES, typo_lane="x")


def test_the_evidence_reference_must_be_hash_bound_and_resolve_in_the_record():
    """DEFECT 4 / R3 clause 4, both directions."""
    with pytest.raises(co.EvidenceNotHashBound) as caught:
        synthetic_rubric(rank_reliability_evidence="looked stable to me")
    assert "MEASURED RATHER THAN ASSERTED" in str(caught.value)
    rubric = synthetic_rubric()
    path = rubric.rank_reliability_evidence.split("@sha256:")[0]
    digest = rubric.rank_reliability_evidence.split("@sha256:")[1]
    assert co.assert_evidence_is_hash_bound(rubric, [{"path": path, "sha256": digest}])[
        "hash_bound"
    ] == "SATISFIED"
    with pytest.raises(co.EvidenceNotHashBound) as caught:
        co.assert_evidence_is_hash_bound(rubric, [{"path": path, "sha256": "b" * 64}])
    assert "binds nothing" in str(caught.value)
    with pytest.raises(co.EvidenceNotHashBound) as caught:
        co.assert_evidence_is_hash_bound(rubric, [{"path": "other.md", "sha256": digest}])
    assert "not among the record's artifacts" in str(caught.value)


# ------------------------------------------------------------------ two axes


def test_a_signed_difference_alone_cannot_tell_BOTH_from_NEITHER():
    """THE RULING_13 Q4 CLAUSE 3 FALSIFIER, and it must be able to fail.

    Two independent presence judgements "CANNOT distinguish FLIPPED from
    NOW-ASSERTS-BOTH from NOW-ASSERTS-NEITHER". This asserts that the SIGNED
    AXIS ALONE has exactly that defect, and that the second axis repairs it."""
    rubric = synthetic_rubric()
    bands = synthetic_bands()
    both = reading(6.0, 5.0, rubric)
    neither = reading(0.0, 0.0, rubric)
    assert both.signed == pytest.approx(1.0)
    assert neither.signed == pytest.approx(0.0)
    # Construct the exact collision the ruling names: equal signed scores.
    both_equal = reading(5.0, 5.0, rubric)
    assert both_equal.signed == neither.signed
    assert both_equal.assertion_level != neither.assertion_level
    assert co.classify_bipolar(both_equal, bands) == "ASSERTS_BOTH"
    assert co.classify_bipolar(neither, bands) == "ASSERTS_NEITHER"
    assert co.classify_bipolar(both, bands) == "ASSERTS_BOTH"


def test_the_classes_are_exhaustive_over_the_two_axes():
    rubric = synthetic_rubric()
    bands = synthetic_bands()
    observed = {
        co.classify_bipolar(reading(own, mirror, rubric), bands)
        for own, mirror in ((5.0, 0.0), (0.0, 5.0), (1.0, 1.0), (5.0, 5.0), (0.0, 0.0))
    }
    assert observed == set(co.OUTCOME_CLASSES)


def test_two_different_rubrics_cannot_be_composed():
    with pytest.raises(co.IncommensurablePoles):
        co.BipolarReading(
            own=co.PoleReading(PERSONA_A, 3.0, synthetic_rubric()),
            mirror=co.PoleReading(PERSONA_B, 1.0, synthetic_rubric(rubric_version="9.9.9")),
        )


def test_a_pole_cannot_mirror_itself():
    rubric = synthetic_rubric()
    with pytest.raises(co.IncommensurablePoles):
        co.BipolarReading(
            own=co.PoleReading(PERSONA_A, 3.0, rubric),
            mirror=co.PoleReading(PERSONA_A, 1.0, rubric),
        )


def test_a_reading_off_its_own_scale_refuses():
    rubric = synthetic_rubric()
    with pytest.raises(co.OrdinalScaleViolation):
        co.PoleReading(PERSONA_A, 7.0, rubric)
    with pytest.raises(co.OrdinalScaleViolation):
        co.PoleReading(PERSONA_A, -0.5, rubric)


def test_bands_without_a_calibration_digest_refuse():
    with pytest.raises(co.CausalOutcomeError):
        synthetic_bands(calibration_digest="pinned-by-nobody")
    with pytest.raises(co.CausalOutcomeError):
        synthetic_bands(derivation="")
    with pytest.raises(co.CausalOutcomeError):
        synthetic_bands(neutral_low=2.0, neutral_high=-2.0)


# ---------------------------------------------------------------- crossing


FORWARD = co.JointCondition(
    ablated_concept_id=PERSONA_B,
    amplified_concept_id=PERSONA_A,
    own_concept_id=PERSONA_A,
    mirror_concept_id=PERSONA_B,
)


def test_the_crossing_predicate_has_NO_DEFAULT_ORIENTATION():
    """DEFECT_2, THE DANGEROUS ONE. A default orientation made the predicate
    return False for every prompt in every cell whenever the true origin was the
    other pole, and that surfaced as NOT_EVIDENCED -- 'admissible prompts existed
    and none crossed'. A predicate that cannot fire reporting a substantive
    null. There is now no default, so the wrong-orientation call is a TypeError
    at the call site instead of a wrong claim in a report."""
    import inspect

    parameter = inspect.signature(co.crosses).parameters["origin_pole"]
    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        co.crosses("POLE_MIRROR", "POLE_OWN")  # type: ignore[call-arg]
    assert "origin_pole" not in inspect.signature(co.crosses_under).parameters


def test_the_orientation_is_derived_from_the_condition_and_flips_with_it():
    """FIRES AND DOES NOT FIRE over inputs differing only in the condition."""
    assert FORWARD.origin_pole == "POLE_MIRROR"
    assert FORWARD.target_pole == "POLE_OWN"
    assert FORWARD.mirrored().origin_pole == "POLE_OWN"
    assert FORWARD.mirrored().target_pole == "POLE_MIRROR"
    assert co.derive_origin_pole(FORWARD) == "POLE_MIRROR"
    # The SAME reading crosses under one condition and not under the other.
    assert co.crosses_under(FORWARD, "POLE_MIRROR", "POLE_OWN") is True
    assert co.crosses_under(FORWARD.mirrored(), "POLE_MIRROR", "POLE_OWN") is False
    assert co.crosses_under(FORWARD.mirrored(), "POLE_OWN", "POLE_MIRROR") is True


def test_a_supplied_orientation_that_contradicts_the_condition_is_refused():
    assert co.assert_orientation_agrees(FORWARD, "POLE_MIRROR") == "POLE_MIRROR"
    with pytest.raises(co.OrientationContradicted) as caught:
        co.assert_orientation_agrees(FORWARD, "POLE_OWN")
    assert "refused rather than honoured" in str(caught.value)
    with pytest.raises(co.OrientationNotDerivable):
        co.assert_orientation_agrees(FORWARD, "NEUTRAL")


@pytest.mark.parametrize(
    "overrides",
    [
        {"ablated_concept_id": PERSONA_A},
        {"own_concept_id": PERSONA_B},
        {"ablated_concept_id": "cheese"},
        {"ablated_concept_id": "  "},
    ],
)
def test_an_underivable_condition_refuses_rather_than_defaulting(overrides: dict):
    payload = {
        "ablated_concept_id": PERSONA_B,
        "amplified_concept_id": PERSONA_A,
        "own_concept_id": PERSONA_A,
        "mirror_concept_id": PERSONA_B,
    }
    payload.update(overrides)
    with pytest.raises(co.OrientationNotDerivable):
        co.JointCondition(**payload)


def test_asserts_both_is_not_a_flip_and_the_baseline_conditions_the_test():
    assert co.crosses("POLE_MIRROR", "POLE_OWN", origin_pole="POLE_MIRROR") is True
    assert co.crosses("POLE_MIRROR", "ASSERTS_BOTH", origin_pole="POLE_MIRROR") is False
    assert co.crosses("POLE_MIRROR", "NEUTRAL", origin_pole="POLE_MIRROR") is False
    assert co.crosses("POLE_OWN", "POLE_OWN", origin_pole="POLE_MIRROR") is False
    assert co.crosses("NEUTRAL", "POLE_OWN", origin_pole="POLE_MIRROR") is False
    assert co.crosses("POLE_OWN", "POLE_MIRROR", origin_pole="POLE_OWN") is True
    assert co.baseline_is_at_origin_pole("POLE_MIRROR", origin_pole="POLE_MIRROR") is True
    assert co.baseline_is_at_origin_pole("ASSERTS_BOTH", origin_pole="POLE_MIRROR") is False


def test_the_outcome_variable_is_the_PAIR_and_the_raw_counts_are_retained():
    """R2 VERDICT: sanctioned as a construction, REFUSED AS A SCALAR."""
    rubric = synthetic_rubric()
    composed = reading(4.0, 1.0, rubric)
    assert composed.outcome_pair == (3.0, 5.0)
    record = composed.to_dict()
    assert record["raw_counts_retained"] == {PERSONA_A: 4.0, PERSONA_B: 1.0}
    assert "two_axes_rule" in record
    assert "constructed signed contrast" in record["composition_is_ours"]
    assert co.assert_two_axes_travel_together(record) is record


def test_a_record_carrying_the_difference_alone_is_refused():
    """R2 condition 2, and it FIRES on the collapse and NOT on the honest record."""
    rubric = synthetic_rubric()
    honest = reading(4.0, 1.0, rubric).to_dict()
    co.assert_two_axes_travel_together(honest)
    for dropped in ("assertion_level", "raw_counts_retained"):
        collapsed = {k: v for k, v in honest.items() if k != dropped}
        with pytest.raises(co.TwoAxesSeparated) as caught:
            co.assert_two_axes_travel_together(collapsed)
        assert "the PAIR" in str(caught.value) or "not injective" in str(caught.value)
    forged = dict(honest)
    forged["assertion_level"] = 99.0
    with pytest.raises(co.TwoAxesSeparated):
        co.assert_two_axes_travel_together(forged)
    # A record with no 'signed' key is not this guard's business.
    assert co.assert_two_axes_travel_together({"cell": "en/f1"}) == {"cell": "en/f1"}


def test_a_non_pole_origin_refuses_because_it_cannot_evidence_a_flip():
    with pytest.raises(co.CausalOutcomeError):
        co.crosses("NEUTRAL", "POLE_OWN", origin_pole="NEUTRAL")


# ------------------------------------------------------ the firing precondition


def test_the_state_vocabulary_matches_the_intervention_lane():
    """The mirror is CHECKED. Restating without comparing would be the drift."""
    assert co.assert_state_vocabulary_matches_intervention_lane() == co.INTERVENTION_STATES


@pytest.mark.parametrize("state", ["NOT_EXERCISED", "FIRED_BUT_INERT"])
def test_a_void_state_refuses_and_is_never_scored(state: str):
    rubric = synthetic_rubric()
    with pytest.raises(co.FiringPreconditionUnmet):
        co.score_generation(
            observation_id=f"o-{state}",
            cell="en/f1",
            prompt_id="p1",
            seed=1,
            arm_label="ablate-A",
            kind="ablate",
            reading=reading(0.0, 0.0, rubric),
            firing=evidence(intervention_state=state, hook_call_count=0, max_abs_delta=0.0),
            bands=synthetic_bands(),
            member_count=2,
        )


def test_the_two_void_states_are_DIFFERENT_exception_types():
    """REGRESSION. The first router matched on the error text, and the
    FIRED_BUT_INERT message quotes STATE_IS_NOT_A_NULL, which contains the
    words NOT_EXERCISED -- so both states landed in the same bucket. The two
    distinctions the ruling requires kept apart were collapsed by the router
    meant to keep them apart."""
    assert issubclass(co.NotExercised, co.FiringPreconditionUnmet)
    assert issubclass(co.FiredButInert, co.FiringPreconditionUnmet)
    assert not issubclass(co.FiredButInert, co.NotExercised)
    assert "NOT_EXERCISED" in co.STATE_IS_NOT_A_NULL, (
        "the shared message no longer contains the substring that caused the collapse; the "
        "regression test above is now weaker than it was, so keep the type-based routing"
    )


def test_an_absorbed_intervention_is_refused_not_scored():
    rubric = synthetic_rubric()
    with pytest.raises(co.InterventionAbsorbed) as caught:
        co.score_generation(
            observation_id="o-abs",
            cell="en/f1",
            prompt_id="p1",
            seed=1,
            arm_label="amplify-B",
            kind="amplify",
            reading=reading(5.0, 0.0, rubric),
            firing=evidence(absorbed_element_count=157, requested_nonzero_element_count=160),
            bands=synthetic_bands(),
            member_count=2,
        )
    assert "157 of 160" in str(caught.value)


def test_a_zero_dosed_member_refuses_on_the_amplify_arm_only():
    """The zero-dose hazard is confined to the clamp/amplify arm.

    RULING_14 addendum clause 5: subtraction removes the feature's ACTUAL
    contribution and needs no corpus reference, so ablation is untouched. A
    refusal that fired on both arms would block the instrument the ruling chose."""
    rubric = synthetic_rubric()
    with pytest.raises(co.ZeroDoseRefused) as caught:
        co.score_generation(
            observation_id="o-zero",
            cell="en/f1",
            prompt_id="p1",
            seed=1,
            arm_label="amplify-B",
            kind="amplify",
            reading=reading(5.0, 0.0, rubric),
            firing=evidence(evaluated_member_doses=(2.0, 0.0)),
            bands=synthetic_bands(),
            member_count=2,
        )
    assert "MAXIMAL SELECTIVITY" in str(caught.value)
    scored = co.score_generation(
        observation_id="o-ablate",
        cell="en/f1",
        prompt_id="p1",
        seed=1,
        arm_label="ablate-A",
        kind="ablate",
        reading=reading(0.0, 3.0, rubric),
        firing=evidence(evaluated_member_doses=(2.0, 0.0)),
        bands=synthetic_bands(),
        member_count=2,
    )
    assert scored.outcome_class == "POLE_MIRROR"


def test_a_nonzero_dose_does_NOT_substitute_for_the_firing_evidence():
    """The zero-dose refusal landed upstream at construction time (ab93ee3), so a
    run reaching this scorer has provably had a non-zero dose. THAT IS NOT THE
    SAME PROPERTY. A dose is what was REQUESTED; the firing evidence is what
    HAPPENED. RULING_13 is explicit that VOID and NOT-EXERCISED are not nulls, so
    every one of these rows carries a healthy per-member dose and is STILL
    refused -- because the hook never fired, or fired inertly, or the dtype ate
    the delta. If any of these ever starts returning a score, an upstream
    guarantee has been allowed to stand in for a downstream measurement."""
    rubric = synthetic_rubric()
    healthy_dose = (2.0, 3.0)
    cases = {
        "never fired": (
            {"intervention_state": "NOT_EXERCISED", "hook_call_count": 0, "max_abs_delta": 0.0},
            co.NotExercised,
        ),
        "fired and inert": (
            {"intervention_state": "FIRED_BUT_INERT", "hook_call_count": 4, "max_abs_delta": 0.0},
            co.FiredButInert,
        ),
        "absorbed by the dtype": (
            {"absorbed_element_count": 157, "requested_nonzero_element_count": 160},
            co.InterventionAbsorbed,
        ),
        "applied but claiming no calls": ({"hook_call_count": 0}, co.FiringEvidenceMissing),
    }
    for label, (overrides, expected) in cases.items():
        firing = evidence(evaluated_member_doses=healthy_dose, **overrides)
        assert firing.evaluated_member_doses == healthy_dose, label
        assert all(dose != 0.0 for dose in firing.evaluated_member_doses), label
        with pytest.raises(expected):
            co.score_generation(
                observation_id=f"dose-ok-{label}",
                cell="en/f1",
                prompt_id="p1",
                seed=1,
                arm_label="amplify-B",
                kind="amplify",
                reading=reading(5.0, 0.0, rubric),
                firing=firing,
                bands=synthetic_bands(),
                member_count=2,
            )


def test_a_self_contradictory_applied_record_refuses_rather_than_being_reclassified():
    rubric = synthetic_rubric()
    for overrides in ({"hook_call_count": 0}, {"max_abs_delta": 0.0}):
        with pytest.raises(co.FiringEvidenceMissing):
            co.score_generation(
                observation_id="o-bad",
                cell="en/f1",
                prompt_id="p1",
                seed=1,
                arm_label="amplify-B",
                kind="amplify",
                reading=reading(5.0, 0.0, rubric),
                firing=evidence(**overrides),
                bands=synthetic_bands(),
                member_count=2,
            )


def test_a_control_that_fired_is_not_a_control_and_an_intervened_arm_is_not_a_reference():
    rubric = synthetic_rubric()
    with pytest.raises(co.FiringPreconditionUnmet):
        co.assert_firing_precondition(evidence(intervention_state="CONTROL"), kind="noop", member_count=0)
    with pytest.raises(co.FiringPreconditionUnmet):
        co.assert_firing_precondition(control_evidence(), kind="amplify", member_count=2)
    assert co.assert_firing_precondition(control_evidence(), kind="noop", member_count=0)["eligible"]
    del rubric


def test_per_member_evidence_of_the_wrong_length_refuses():
    with pytest.raises(co.FiringEvidenceMissing):
        co.assert_firing_precondition(
            evidence(evaluated_member_doses=(1.0,)), kind="amplify", member_count=2
        )
    with pytest.raises(co.FiringEvidenceMissing):
        co.assert_firing_precondition(evidence(), kind="amplify", member_count=0)


def test_missing_firing_evidence_is_a_refusal_never_a_zero():
    with pytest.raises(co.FiringEvidenceMissing):
        co.from_prompt_row({"intervention_state": "APPLIED", "hook_call_count": 1})
    with pytest.raises(co.FiringEvidenceMissing):
        co.FiringEvidence(
            intervention_state="MAYBE",
            hook_call_count=1,
            total_delta_norm=1.0,
            max_abs_delta=1.0,
            absorbed_element_count=0,
            requested_nonzero_element_count=1,
            residual_dtypes=(),
            evaluated_member_doses=(1.0,),
            post_intervention_member_latents=(1.0,),
        )


def test_from_prompt_row_round_trips_a_full_record():
    built = co.from_prompt_row(evidence().to_dict())
    assert built.intervention_state == "APPLIED"
    assert built.absorbed_fraction == 0.0


# --------------------------------------------------------------------- tally


def test_the_two_void_states_land_in_different_buckets():
    rubric = synthetic_rubric()
    tally = co.CellTally(cell="en/f1")
    for observation_id, state in (("a", "NOT_EXERCISED"), ("b", "FIRED_BUT_INERT")):
        try:
            co.score_generation(
                observation_id=observation_id,
                cell="en/f1",
                prompt_id="p1",
                seed=1,
                arm_label="ablate-A",
                kind="ablate",
                reading=reading(0.0, 0.0, rubric),
                firing=evidence(intervention_state=state, hook_call_count=0, max_abs_delta=0.0),
                bands=synthetic_bands(),
                member_count=2,
            )
        except co.CausalOutcomeError as error:
            tally.record_refusal(observation_id, error)
    assert tally.refusals["not_exercised"] == ["a"]
    assert tally.refusals["fired_but_inert"] == ["b"]
    assert tally.denominator == 0


def test_an_unmapped_refusal_raises_rather_than_landing_in_a_catch_all():
    tally = co.CellTally(cell="en/f1")
    with pytest.raises(co.StateCollapsed):
        tally.record_refusal("x", ValueError("something else entirely"))


def test_a_generation_from_another_cell_cannot_be_pooled_in():
    rubric = synthetic_rubric()
    tally = co.CellTally(cell="en/f1")
    scored = co.score_generation(
        observation_id="o",
        cell="fr/f2",
        prompt_id="p1",
        seed=1,
        arm_label="amplify-B",
        kind="amplify",
        reading=reading(5.0, 0.0, rubric),
        firing=evidence(),
        bands=synthetic_bands(),
        member_count=2,
    )
    with pytest.raises(co.StateCollapsed):
        tally.add(scored)


def test_a_rate_over_an_empty_denominator_refuses():
    with pytest.raises(co.VacuousTally):
        co.CellTally(cell="en/f1").rate("POLE_OWN")


def test_the_denominator_falsifier_fails_on_a_forged_record_and_passes_on_an_honest_one():
    """RULING_13 Q2 clause 4 made exercisable. Both directions, or the check
    only proves one."""
    rubric = synthetic_rubric()
    tally = co.CellTally(cell="en/f1")
    tally.add(
        co.score_generation(
            observation_id="ok",
            cell="en/f1",
            prompt_id="p1",
            seed=1,
            arm_label="amplify-B",
            kind="amplify",
            reading=reading(5.0, 0.0, rubric),
            firing=evidence(),
            bands=synthetic_bands(),
            member_count=2,
        )
    )
    tally.refusals["not_exercised"].append("void-1")
    tally.record_baseline_exclusion("excluded-1")
    honest = tally.to_dict()
    assert co.assert_denominator_excludes_void(honest) is honest
    assert honest["denominator_scored"] == 1
    assert honest["observations_seen"] == 3

    forged = dict(honest)
    forged["denominator_scored"] = 2
    with pytest.raises(co.StateCollapsed):
        co.assert_denominator_excludes_void(forged)

    truncated = {key: value for key, value in honest.items() if key != "refused_by_reason"}
    with pytest.raises(co.StateCollapsed):
        co.assert_denominator_excludes_void(truncated)


def test_a_pooled_figure_is_only_available_alongside_the_vector():
    tally = co.CellTally(cell="en/f1")
    tally.refusals["not_exercised"].append("v")
    summary = co.summarise_states([tally])
    assert "per_cell" in summary
    assert summary["pooled_only_alongside_the_vector"]["refused_by_reason"]["not_exercised"] == 1
    with pytest.raises(co.VacuousTally):
        co.summarise_states([])


def test_the_unexercised_list_is_honest_about_needing_weights():
    joined = " ".join(co.UNEXERCISED_WITHOUT_GPU).lower()
    assert "no continuation produced by" in joined
    assert len(co.UNEXERCISED_WITHOUT_GPU) >= 4


# ---------------------------------- RULING_15 R1 clause 7: the frozen-row falsifier


class OracleInstrument:
    """A STUB, NOT AN INSTRUMENT, and deliberately TEXT-ONLY.

    It exists to exercise the FALSIFIER, not to score anything: a real instrument
    judges free text and is R3's to author, by a lane clearing all five
    exclusions.

    TEXT-ONLY IS THE LOAD-BEARING PROPERTY, and the first version of this stub got
    it wrong in an instructive way. near_miss rows are BYTE COPIES of the mirror
    concept's positives, so the same string appears under two splits with two
    different `concept_id` values. A stub that looked its answer up by ROW could
    return different extents for identical text -- which no instrument reading
    only text can do, so it would have tested nothing about the instrument and
    everything about the lookup. This version maps TEXT to the concept the text
    asserts, exactly as an instrument must, and the two splits' expectations then
    turn out to be THE SAME STATEMENT expressed relative to different `own`
    referents: the positive says "asserts A, not B" and its near_miss copy says
    "not A, asserts B". That consistency is why the near_miss limb is a genuine
    SIGN test rather than a bookkeeping one."""

    def __init__(self, rows):
        # Which concept does this exact text assert? Answered by the POSITIVE
        # rows only, because those are the rows whose concept authored them.
        self._asserts = {
            row["text"]: row["concept_id"] for row in rows if row["split"] == "positive"
        }
        self._claim_type = {
            row["text"]: row["claim_type"] for row in rows if row["split"] == "positive"
        }

    def __call__(self, text: str, referent: str) -> int:
        return 1 if self._asserts.get(text) == referent else 0

    def claim_types(self, text: str, referent: str):
        if self._asserts.get(text) == referent:
            return (self._claim_type[text],)
        return ()


class WrongSignInstrument(OracleInstrument):
    """Correct magnitudes, INVERTED referent: it credits the mirror instead.

    This is the failure mode the near_miss limb exists to catch, and it is
    exactly the class of the orientation defect RULING_15 found in this lane's own
    `crosses`: every magnitude is plausible and the direction is backwards."""

    def __init__(self, rows):
        super().__init__(rows)
        self._mirror_of = {}
        for text, concept in self._asserts.items():
            self._mirror_of[text] = next(
                name for name in co.PERSONA_CONCEPT_IDS if name != concept
            )

    def __call__(self, text: str, referent: str) -> int:
        return 1 if self._mirror_of.get(text) == referent else 0


def test_the_frozen_corpus_has_the_geometry_the_falsifier_expects():
    rows = co.load_frozen_rows()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["split"]] = counts.get(row["split"], 0) + 1
    assert counts == {
        "positive": 120,
        "near_miss": 60,
        "heldout_neutral": 80,
        "unrelated": 60,
        "heldout_eliciting": 80,
    }
    assert set(counts) == set(co.FROZEN_ROW_EXPECTATIONS)


def test_the_falsifier_PASSES_an_instrument_that_agrees_with_the_frozen_labels():
    rows = co.load_frozen_rows()
    result = co.run_frozen_row_falsifier(OracleInstrument(rows), rows)
    assert result.adopted is True
    assert result.disqualifying == ()
    assert result.rows_scored == 400
    assert result.reported_only == 80, "the eliciting rows are REPORTED ONLY, never expected"
    assert co.assert_scale_is_adopted(result) is result


def test_the_falsifier_FAILS_an_instrument_whose_SIGN_is_inverted():
    """The limb that exercises the orientation against a pre-known answer."""
    rows = co.load_frozen_rows()
    result = co.run_frozen_row_falsifier(WrongSignInstrument(rows), rows)
    assert result.adopted is False
    # 120 positive + 60 near_miss rows, BOTH referents wrong on each: the sign
    # error is caught on every row where the corpus has a pre-known answer, which
    # is the point of a pre-registered validation set. The claim-type limb is NOT
    # among them -- this instrument inherits the correct type lookup, so the
    # magnitude and the type both look right and only the DIRECTION is wrong.
    # That is precisely the shape of the orientation defect in `crosses`.
    assert len(result.disqualifying) == 2 * (120 + 60)
    with pytest.raises(co.ScaleNotAdopted) as caught:
        co.assert_scale_is_adopted(result)
    assert "NOT ADOPTED" in str(caught.value)
    assert "NOT a corpus verdict" in str(caught.value)


def test_the_falsifier_FAILS_an_instrument_that_scores_neutral_rows_nonzero():
    rows = co.load_frozen_rows()

    asserting = {row["text"] for row in rows if row["split"] == "positive"}

    class NeutralLeak(OracleInstrument):
        def __call__(self, text: str, referent: str) -> int:
            if text not in asserting:
                return 1  # fires on neutral and unrelated text, which must be 0
            return super().__call__(text, referent)

    result = co.run_frozen_row_falsifier(NeutralLeak(rows), rows)
    assert result.adopted is False
    # 80 heldout_neutral + 60 unrelated rows, both referents wrong on each.
    assert len(result.disqualifying) == 2 * 140


def test_the_falsifier_FAILS_a_positive_whose_found_type_differs_from_its_label():
    rows = co.load_frozen_rows()

    class WrongType(OracleInstrument):
        def claim_types(self, text: str, referent: str):
            found = super().claim_types(text, referent)
            if not found:
                return found
            return (next(t for t in co.FROZEN_CLAIM_TYPES if t != found[0]),)

    result = co.run_frozen_row_falsifier(WrongType(rows), rows)
    assert result.adopted is False
    assert len(result.disqualifying) == 120


def test_the_falsifier_records_that_the_UPPER_LATTICE_IS_UNEXERCISED():
    """The honest limit RULING_15 refused to bury: by T5 every frozen positive
    instantiates exactly one claim type, so levels 2-6 are unreachable by every
    row in the corpus. Reporting this as 'the scale is validated' would be the
    defect class in a new place."""
    rows = co.load_frozen_rows()
    record = co.run_frozen_row_falsifier(OracleInstrument(rows), rows).to_dict()
    assert record["levels_exercised"] == [0, 1]
    assert record["levels_unexercised"] == [2, 3, 4, 5, 6]
    assert record["upper_lattice_is_unexercised"] is True
    assert "LEVELS 2 TO 6 ARE UNEXERCISED" in record["scope"]
    assert "may not be converted into one" in record["scope"]
    assert "NEVER be cited as" in record["new_reading"]


def test_the_falsifier_refuses_an_empty_row_set():
    with pytest.raises(co.ScaleNotAdopted):
        co.run_frozen_row_falsifier(lambda text, referent: 0, [])


def test_no_instrument_is_supplied_by_this_lane():
    """R3 is not this lane's to implement. The falsifier takes an instrument; it
    does not contain one, and the stubs live in the test file."""
    source = (FINAL_PAIRING / "causal_outcome.py").read_bytes().decode("utf-8")
    assert "class OracleInstrument" not in source
    assert "def claim_types" not in source


def test_the_selfcheck_runs_clean():
    assert co.main(["--selfcheck"]) == 0


# ------------- RULING_15 general clause: the missing direction, made explicit


def test_classify_bipolar_refuses_an_unusable_band_as_well_as_classifying():
    """It only ever returned a class in these tests; it must also refuse."""
    rubric = synthetic_rubric()
    composed = reading(4.0, 1.0, rubric)
    assert co.classify_bipolar(composed, synthetic_bands()) == "POLE_OWN"
    with pytest.raises(co.CausalOutcomeError):
        co.classify_bipolar(composed, synthetic_bands(calibration_digest="nope"))


def test_derive_origin_pole_and_crosses_under_both_answers_and_a_refusal():
    assert co.derive_origin_pole(FORWARD) == "POLE_MIRROR"
    assert co.crosses_under(FORWARD, "POLE_MIRROR", "POLE_OWN") is True
    assert co.crosses_under(FORWARD, "POLE_MIRROR", "ASSERTS_BOTH") is False
    with pytest.raises(co.CausalOutcomeError):
        co.crosses_under(FORWARD, "NOT_A_CLASS", "POLE_OWN")


def test_baseline_is_at_origin_pole_refuses_an_unknown_class():
    assert co.baseline_is_at_origin_pole("POLE_MIRROR", origin_pole="POLE_MIRROR") is True
    assert co.baseline_is_at_origin_pole("NEUTRAL", origin_pole="POLE_MIRROR") is False
    with pytest.raises(co.CausalOutcomeError):
        co.baseline_is_at_origin_pole("NOT_A_CLASS", origin_pole="POLE_MIRROR")


def test_load_frozen_rows_refuses_crlf_as_well_as_loading(tmp_path):
    assert len(co.load_frozen_rows()) == 400
    crlf = tmp_path / "rows.jsonl"
    crlf.write_bytes(b'{"a": 1}\r\n')
    with pytest.raises(co.CausalOutcomeError) as caught:
        co.load_frozen_rows(crlf)
    assert "CRLF" in str(caught.value)


def test_assert_firing_precondition_returns_a_record_as_well_as_refusing():
    record = co.assert_firing_precondition(evidence(), kind="amplify", member_count=2)
    assert record["eligible"] is True
    assert record["state"] == "APPLIED"
    with pytest.raises(co.NotExercised):
        co.assert_firing_precondition(
            evidence(intervention_state="NOT_EXERCISED", hook_call_count=0, max_abs_delta=0.0),
            kind="amplify",
            member_count=2,
        )


def test_the_state_vocabulary_comparison_refuses_when_it_cannot_compare(monkeypatch, tmp_path):
    """It only ever succeeded in these tests. A comparison that cannot run must
    REFUSE rather than skip, because a skipped comparison reads as a pass."""
    assert co.assert_state_vocabulary_matches_intervention_lane() == co.INTERVENTION_STATES
    monkeypatch.setattr(co, "SCRIPT_DIR", tmp_path)
    with pytest.raises(co.StateVocabularyDrift) as caught:
        co.assert_state_vocabulary_matches_intervention_lane()
    assert "not a pass" in str(caught.value)
