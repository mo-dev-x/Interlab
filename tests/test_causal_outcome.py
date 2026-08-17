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
        "rank_reliability_evidence": "SYNTHETIC: nothing has been measured for any axis",
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


def test_the_module_declares_no_numeric_decision_boundary():
    """No margin, ceiling, band or dose may be a literal in this file.

    Asserted over the AST rather than by reading, because "I looked and there
    were none" is the class of check this sprint keeps finding to be wrong."""
    tree = ast.parse((FINAL_PAIRING / "causal_outcome.py").read_bytes().decode("utf-8"))
    offenders: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    offenders.append(f"{target.id} = {node.value.value}")
    assert offenders == [], (
        f"module-level numeric constant(s) {offenders}: a boundary hardcoded here would not be a "
        f"control-only calibration, whatever its comment said"
    )


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


def test_the_rubric_author_may_be_neither_calibrator_nor_selector():
    rubric = synthetic_rubric(authored_by="engineer2")
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.assert_separation_of_duties(rubric, calibrating_lane="researcher", selecting_lane="engineer2")
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.assert_separation_of_duties(
            synthetic_rubric(authored_by="RESEARCHER"),
            calibrating_lane="researcher",
            selecting_lane="engineer2",
        )
    record = co.assert_separation_of_duties(
        synthetic_rubric(authored_by="pm"), calibrating_lane="researcher", selecting_lane="engineer2"
    )
    assert record["separation"] == "SATISFIED"


def test_an_unenforceable_separation_refuses_rather_than_passing_vacuously():
    with pytest.raises(co.OutcomeMeasureNotSanctioned):
        co.assert_separation_of_duties(synthetic_rubric(), calibrating_lane="", selecting_lane="x")


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


def test_asserts_both_is_not_a_flip_and_the_baseline_conditions_the_test():
    assert co.crosses("POLE_MIRROR", "POLE_OWN") is True
    assert co.crosses("POLE_MIRROR", "ASSERTS_BOTH") is False
    assert co.crosses("POLE_MIRROR", "NEUTRAL") is False
    assert co.crosses("POLE_OWN", "POLE_OWN") is False
    assert co.crosses("NEUTRAL", "POLE_OWN") is False
    assert co.crosses("POLE_OWN", "POLE_MIRROR", origin_pole="POLE_OWN") is True
    assert co.baseline_is_at_origin_pole("POLE_MIRROR", origin_pole="POLE_MIRROR") is True
    assert co.baseline_is_at_origin_pole("ASSERTS_BOTH", origin_pole="POLE_MIRROR") is False


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


def test_the_selfcheck_runs_clean():
    assert co.main(["--selfcheck"]) == 0
