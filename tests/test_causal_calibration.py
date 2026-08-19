"""Tests for the control-only calibration, its refusals, and its seal.

THE THING THESE TESTS DO NOT ASSERT: that any particular margin, ceiling or
band is the RIGHT one. No such assertion is possible -- the numbers come from
controls that do not exist, and inventing one so a test could assert it is the
ruling biting rather than a gap in coverage. What is asserted is that every
number is an exact FUNCTION of the control set (run the derivation on two
different control sets and the outputs must both move), that a control set which
cannot support the derivation REFUSES and states its minimum, and that the pin
cannot be produced after a result has been scored against it.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FINAL_PAIRING = REPO_ROOT / "scripts" / "final_pairing"
sys.path.insert(0, str(FINAL_PAIRING))

import causal_calibration as cc  # noqa: E402
import causal_outcome as co  # noqa: E402
from test_causal_outcome import (  # noqa: E402
    PERSONA_A,
    PERSONA_B,
    control_evidence,
    evidence,
    synthetic_rubric,
)

#: Built THROUGH THE CONTRACT rather than typed, so that a change to the covered field
#: set changes the fixture too and a stale test cannot pass on a stale digest.
SETTINGS = {name: f"SYNTHETIC-{name}" for name, _ in cc.GENERATION_SETTINGS_FIELDS}
SETTINGS_DIGEST = cc.generation_settings_digest(SETTINGS)

#: The orientation is DERIVED from this, never supplied (RULING_15 DEFECT_2).
FORWARD_CONDITION = co.JointCondition(
    ablated_concept_id=PERSONA_B,
    amplified_concept_id=PERSONA_A,
    own_concept_id=PERSONA_A,
    mirror_concept_id=PERSONA_B,
)


@pytest.fixture(autouse=True)
def _reopen_the_seal():
    """The seal is process-global BY DESIGN, so each test starts from closed=false.

    Reset in a fixture rather than inside tests, so that a test which forgets
    cannot inherit another test's sealed state and pass for the wrong reason."""
    cc._reset_seal_for_tests_only()
    yield
    cc._reset_seal_for_tests_only()


def control(
    observation_id: str,
    cell: str,
    prompt: str,
    seed: int,
    *,
    own: float = 0.0,
    mirror: float = 0.0,
    arm_label: str = "control-noop",
    is_control: bool = True,
    outcome_class: str | None = None,
) -> cc.ControlObservation:
    signed = own - mirror
    if outcome_class is None:
        outcome_class = "POLE_OWN" if signed > 1.0 else ("POLE_MIRROR" if signed < -1.0 else "NEUTRAL")
    return cc.ControlObservation(
        observation_id=observation_id,
        cell=cell,
        prompt_id=prompt,
        seed=seed,
        arm_label=arm_label,
        is_control=is_control,
        signed=signed,
        assertion_level=own + mirror,
        outcome_class=outcome_class,
    )


def paired_controls(cell: str, *, n_prompts: int, seeds=(1, 2), **kwargs):
    return [
        control(f"{cell}-{seed}-p{i}", cell, f"p{i}", seed, **kwargs)
        for seed in seeds
        for i in range(n_prompts)
    ]


# -------------------------------------------------------- the lane's boundary


def test_the_calibration_module_reads_nothing_from_the_selection_lane():
    """CONSTITUTIONAL. The calibrating lane must not select the group.

    Asserted over the source rather than by intent: any import of
    `group_selection` here would give this lane sight of the candidate groups
    the thresholds are measured against."""
    source = (FINAL_PAIRING / "causal_calibration.py").read_bytes().decode("utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert "group_selection" not in imported, (
        f"causal_calibration imports {imported}; importing the selection lane would let the "
        f"calibrator see the groups its thresholds are measured against"
    )
    for forbidden in ("GroupCandidate", "coverage_vector", "exact_minimum_cover", "A[f,c]"):
        assert forbidden not in source, f"{forbidden!r} is selection vocabulary"


def test_only_the_two_derived_minimums_are_numeric_constants():
    """Any other module-level number here would be an invented threshold."""
    tree = ast.parse((FINAL_PAIRING / "causal_calibration.py").read_bytes().decode("utf-8"))
    numeric: dict[str, object] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, (int, float))
            and not isinstance(node.value.value, bool)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    numeric[target.id] = node.value.value
    assert set(numeric) == {
        "MINIMUM_CONTROL_OBSERVATIONS_PER_CELL",
        "MINIMUM_CONTROL_REPLICATES_PER_CELL",
    }, f"unexpected module-level number(s): {numeric}"
    assert "attained_coverage_level(1) == 0.5" in cc.MINIMUM_IS_DERIVED
    assert "P=1" in cc.MINIMUM_IS_DERIVED


def test_the_reset_helper_is_called_by_no_production_module():
    """A seal with a reachable reset in production is not a seal."""
    callers = [
        path.name
        for path in sorted(FINAL_PAIRING.glob("*.py"))
        if "_reset_seal_for_tests_only" in path.read_bytes().decode("utf-8")
        and path.name != "causal_calibration.py"
    ]
    assert callers == [], f"{callers} reach into the seal reset"


def test_the_assignment_gap_is_recorded_on_the_face_of_the_pin():
    record = cc.CALIBRATION_ASSIGNMENT_IS_A_COORDINATION_RECORD
    assert "entity_discriminator_calibrator_assignment.json" in record
    assert "engineer3" in record
    assert "There is no protocol artifact assigning it" in record
    assert (
        REPO_ROOT / "protocols/final_pairing/v1/entity_discriminator_calibrator_assignment.json"
    ).is_file()


# ------------------------------------------------------ the canonical form


def test_the_local_canonical_json_is_byte_identical_to_the_shared_helper():
    """The restatement is CHECKED, not assumed.

    These three files import nothing outside `scripts/final_pairing/` because
    they have to run from a cluster tarball extract. That makes the canonical
    form a duplicate, so the duplicate is compared against the real one on a
    structure containing every JSON type."""
    from interplab.core.canonical_json import canonicalize

    payload = {
        "z": [1, 2.5, True, False, None, "é"],
        "a": {"nested": {"k": -0.0}},
        "unicode": "national exceptionalism — mission",
        "": "empty key",
    }
    assert co.canonical_json(payload) == canonicalize(payload)


def test_the_digest_of_a_control_set_is_a_property_of_the_set_not_its_order():
    rows = paired_controls("en/f1", n_prompts=3)
    assert cc.digest_control_set(rows) == cc.digest_control_set(list(reversed(rows)))
    edited = list(rows)
    edited[0] = control("en/f1-1-p0", "en/f1", "p0", 1, own=4.0)
    assert cc.digest_control_set(edited) != cc.digest_control_set(rows)


# ---------------------------------------------- level-free bounds are functions


@pytest.mark.parametrize(("n", "expected"), [(1, 0.5), (2, 2 / 3), (3, 0.75), (9, 0.9), (19, 0.95)])
def test_the_attained_level_is_a_function_of_n(n: int, expected: float):
    """THE DERIVED-CEILING FALSIFIER SHAPE. A stored literal passes at most one
    of these; the same construction RULING_14 required of its own ceiling
    ("Run on a 4-cell and a 9-cell universe; recorded ceiling must be 4 and 9")."""
    assert cc.attained_coverage_level(n) == pytest.approx(expected)


def test_a_level_below_one_observation_has_no_bound_to_report():
    with pytest.raises(cc.EmptyControlSet):
        cc.attained_coverage_level(0)


@pytest.mark.parametrize(("level", "n"), [(0.5, 1), (0.75, 3), (0.9, 10), (0.95, 19)])
def test_minimum_controls_for_level_inverts_the_attained_level(level: float, n: int):
    assert cc.minimum_controls_for_level(level) == n
    assert cc.attained_coverage_level(n) >= level


def test_an_impossible_level_refuses():
    for level in (0.0, 1.0, -1.0, 2.0):
        with pytest.raises(cc.CalibrationError):
            cc.minimum_controls_for_level(level)


# ------------------------------------------------------------- the refusals


def test_an_empty_control_set_refuses_and_states_its_minimum():
    with pytest.raises(cc.EmptyControlSet) as caught:
        cc.calibrate_cell("en/f1", [], rubric=synthetic_rubric(), target_outcome_class="POLE_OWN")
    message = str(caught.value)
    assert "MINIMUM" in message
    assert str(cc.MINIMUM_CONTROL_OBSERVATIONS_PER_CELL) in message
    assert "attained_coverage_level(1) == 0.5" in message


def test_one_observation_refuses_because_its_bound_is_a_coin():
    with pytest.raises(cc.InsufficientControlSet):
        cc.calibrate_cell(
            "en/f1",
            [control("a", "en/f1", "p0", 1)],
            rubric=synthetic_rubric(),
            target_outcome_class="POLE_OWN",
        )


def test_one_replicate_refuses_because_no_null_difference_exists():
    with pytest.raises(cc.InsufficientControlSet) as caught:
        cc.calibrate_cell(
            "en/f1",
            paired_controls("en/f1", n_prompts=4, seeds=(1,)),
            rubric=synthetic_rubric(),
            target_outcome_class="POLE_OWN",
        )
    assert "the margin would have to be invented" in str(caught.value)


def test_an_intervened_generation_in_the_control_set_refuses():
    rows = paired_controls("en/f1", n_prompts=2)
    rows.append(control("bad", "en/f1", "p0", 3, own=5.0, arm_label="amplify-B", is_control=False))
    with pytest.raises(cc.ContaminatedControlSet) as caught:
        cc.calibrate_cell("en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN")
    assert "ZERO intervened generations" in str(caught.value)


def test_a_scored_generation_that_is_not_a_control_cannot_become_one():
    rubric = synthetic_rubric()
    intervened = co.score_generation(
        observation_id="amp",
        cell="en/f1",
        prompt_id="p0",
        seed=1,
        arm_label="amplify-B",
        kind="amplify",
        reading=co.BipolarReading(
            own=co.PoleReading(PERSONA_A, 5.0, rubric), mirror=co.PoleReading(PERSONA_B, 0.0, rubric)
        ),
        firing=evidence(),
        bands=co.OutcomeBands(
            neutral_low=-1.0,
            neutral_high=1.0,
            assertion_floor=9.0,
            calibration_digest="c" * 64,
            derivation="synthetic",
        ),
        member_count=2,
    )
    with pytest.raises(cc.ContaminatedControlSet):
        cc.control_observation_from_scored(intervened)


def test_replicates_covering_different_prompts_refuse():
    rows = [
        control("a", "en/f1", "p0", 1),
        control("b", "en/f1", "p1", 1),
        control("c", "en/f1", "p0", 2),
    ]
    with pytest.raises(cc.UnpairedControlReplicates) as caught:
        cc.calibrate_cell("en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN")
    assert "not a null difference" in str(caught.value)


def test_observations_from_another_cell_refuse_rather_than_pooling():
    rows = paired_controls("en/f1", n_prompts=2) + paired_controls("fr/f1", n_prompts=2)
    with pytest.raises(cc.CalibrationError) as caught:
        cc.calibrate_cell("en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN")
    assert "RULING_8" in str(caught.value)


def test_an_undeclared_cell_refuses_rather_than_being_silently_ignored():
    with pytest.raises(cc.CalibrationError) as caught:
        cc.calibrate(
            paired_controls("en/f1", n_prompts=2) + paired_controls("zz/f9", n_prompts=2),
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
            generating_lane="engineer3",
            generation_settings=SETTINGS,
            generation_settings_digest=SETTINGS_DIGEST,
        )
    assert "undeclared cell" in str(caught.value)


def test_calibrate_refuses_zero_cells_and_zero_observations():
    with pytest.raises(cc.CalibrationError):
        cc.calibrate(
            paired_controls("en/f1", n_prompts=2),
            rubric=synthetic_rubric(),
            cells=(),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
            generating_lane="engineer3",
            generation_settings=SETTINGS,
            generation_settings_digest=SETTINGS_DIGEST,
        )
    with pytest.raises(cc.EmptyControlSet):
        cc.calibrate(
            [],
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
            generating_lane="engineer3",
            generation_settings=SETTINGS,
            generation_settings_digest=SETTINGS_DIGEST,
        )


def test_the_calibrating_lane_may_not_be_the_selecting_lane():
    with pytest.raises(cc.CalibrationError) as caught:
        cc.calibrate(
            paired_controls("en/f1", n_prompts=2),
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="Engineer2",
            selecting_lane="engineer2",
            generating_lane="engineer3",
            generation_settings=SETTINGS,
            generation_settings_digest=SETTINGS_DIGEST,
        )
    assert "VOID if the calibrating lane also selects" in str(caught.value)


# ------------------------------------------------- the derivations are functions


@pytest.mark.parametrize(("n_prompts", "resolution"), [(2, 0.5), (4, 0.25), (10, 0.1), (20, 0.05)])
def test_the_rate_resolution_is_one_over_the_prompt_count(n_prompts: int, resolution: float):
    """A rate over n prompts cannot resolve below 1/n. Four different n, four
    different answers -- a stored literal satisfies at most one."""
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=n_prompts),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    assert calibration.rate_resolution == pytest.approx(resolution)


@pytest.mark.parametrize("n_prompts", [2, 4, 10, 20])
def test_the_ceiling_moves_whenever_the_margin_moves(n_prompts: int):
    """RULING_14's own falsifier shape, applied to this ceiling: change the
    margin and the ceiling MUST move. `rate_margin + rate_ceiling == 1` is the
    identity that makes a stored literal impossible."""
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=n_prompts),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    assert calibration.rate_margin + calibration.rate_ceiling == pytest.approx(1.0)
    assert calibration.rate_margin >= calibration.rate_resolution


def test_the_margin_is_the_observed_null_extreme_when_it_exceeds_the_resolution():
    """One replicate at 3/4 and one at 0/4 gives an observed null spread of
    0.75, which is larger than the 0.25 resolution, so the margin is the
    OBSERVED value and not the floor."""
    rows = [control(f"a{i}", "en/f1", f"p{i}", 1, own=0.0) for i in range(4)]
    rows += [control(f"b{i}", "en/f1", f"p{i}", 2, own=5.0 if i < 3 else 0.0) for i in range(4)]
    calibration = cc.calibrate_cell(
        "en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN"
    )
    assert calibration.observed_null_rate_difference_max == pytest.approx(0.75)
    assert calibration.rate_margin == pytest.approx(0.75)
    assert calibration.rate_ceiling == pytest.approx(0.25)
    assert calibration.replicate_rates == (0.0, 0.75)


def test_a_zero_spread_control_set_widens_the_band_to_the_rubrics_resolution():
    """A margin or band of zero would pass ANY nonzero movement. The floor is
    the rubric's own declared resolution -- a measured property of someone
    else's instrument, not a number chosen here."""
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(resolution=2.0),
        target_outcome_class="POLE_OWN",
    )
    assert calibration.observed_signed_min == calibration.observed_signed_max == 0.0
    assert calibration.neutral_high - calibration.neutral_low == pytest.approx(2.0)
    assert calibration.neutral_low == pytest.approx(-1.0)


def test_a_wide_control_spread_is_used_as_observed():
    rows = [control("a", "en/f1", "p0", 1, own=4.0), control("b", "en/f1", "p1", 1, mirror=3.0)]
    rows += [control("c", "en/f1", "p0", 2), control("d", "en/f1", "p1", 2)]
    calibration = cc.calibrate_cell(
        "en/f1", rows, rubric=synthetic_rubric(resolution=1.0), target_outcome_class="POLE_OWN"
    )
    assert calibration.neutral_low == pytest.approx(-3.0)
    assert calibration.neutral_high == pytest.approx(4.0)
    assert calibration.assertion_floor == pytest.approx(4.0)


def test_the_stated_limitations_say_the_minimum_is_where_arithmetic_exists_not_where_it_is_adequate():
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    joined = " ".join(calibration.stated_limitations)
    assert "NOT WHERE IT IS ADEQUATE" in joined
    assert "ARITHMETIC impossibility" in joined
    assert calibration.attained_level_rate_margin == pytest.approx(0.5), (
        "two replicates give exactly one null difference, so the margin's coverage is 1/2; if this "
        "changes, the honesty sentence above must change with it"
    )


# ------------------------------------------------- the resample floor on the margin


def test_the_leave_one_out_spread_is_a_function_of_the_data_not_a_stored_value():
    """Three control sets, three different spreads."""
    cases = {
        "one prompt carries the rate": (
            [
                control(f"a-{seed}-p{i}", "en/f1", f"p{i}", seed, own=5.0 if i == 0 else 0.0)
                for seed in (1, 2)
                for i in range(4)
            ],
            pytest.approx(1 / 3),
        ),
        "every control identical": (paired_controls("en/f1", n_prompts=4), pytest.approx(0.0)),
        "half the prompts carry the rate": (
            [
                control(f"c-{seed}-p{i}", "en/f1", f"p{i}", seed, own=5.0 if i < 2 else 0.0)
                for seed in (1, 2)
                for i in range(4)
            ],
            pytest.approx(1 / 3),
        ),
    }
    for label, (rows, expected) in cases.items():
        calibration = cc.calibrate_cell(
            "en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN"
        )
        assert calibration.control_rate_loo_spread == expected, label


def test_the_margin_is_floored_at_the_resample_spread_and_records_what_bound_it():
    """THE COORDINATOR REQUIREMENT, made exercisable.

    The gate statistics this pipeline produces are noisier than the margins read
    off them -- a leave-one-positive-out spread of 62.2 lattice steps of 1/600
    was MEASURED on a single feature's separation AUROC, which is structural at
    10 positives per cell. A margin below its own resample noise would let a
    result be called significant inside the wobble of the thing it bounds."""
    resample_bound = [
        control(f"a-{seed}-p{i}", "en/f1", f"p{i}", seed, own=5.0 if i == 0 else 0.0)
        for seed in (1, 2)
        for i in range(4)
    ]
    calibration = cc.calibrate_cell(
        "en/f1", resample_bound, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN"
    )
    assert calibration.control_rate_loo_spread == pytest.approx(1 / 3)
    assert calibration.rate_resolution == pytest.approx(0.25)
    assert calibration.observed_null_rate_difference_max == pytest.approx(0.0)
    assert calibration.rate_margin == pytest.approx(1 / 3), "the resample spread must bind"
    assert calibration.margin_bound_by == ("control_rate_leave_one_prompt_out_spread",)
    assert calibration.rate_ceiling == pytest.approx(1 - 1 / 3)

    resolution_bound = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    assert resolution_bound.margin_bound_by == ("rate_resolution",)


def test_no_calibrated_cell_ever_has_a_margin_below_its_resample_spread():
    """THE INVARIANT, asserted over every shape these tests build."""
    patterns = (lambda i: 0.0, lambda i: 5.0 if i == 0 else 0.0, lambda i: 5.0)
    for n_prompts in (2, 4, 10):
        for own_pattern in patterns:
            rows = [
                control(f"x-{seed}-p{i}", "en/f1", f"p{i}", seed, own=own_pattern(i))
                for seed in (1, 2)
                for i in range(n_prompts)
            ]
            calibration = cc.calibrate_cell(
                "en/f1", rows, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN"
            )
            assert calibration.margin_is_at_least_the_resample_spread, (
                f"n_prompts={n_prompts} margin={calibration.rate_margin} "
                f"spread={calibration.control_rate_loo_spread}"
            )


def test_a_passing_cell_can_never_sit_inside_the_control_resample_spread():
    """The structural consequence of the floor: because the margin is at least
    the resample spread and a PASS requires the delta to EXCEED the margin, a
    PASS inside the noise is arithmetically impossible."""
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 5.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.status == "PASS"
    assert verdict.paired_delta_inside_control_resample_spread is False
    assert abs(verdict.paired_rate_delta) > verdict.control_rate_loo_spread


def test_a_fail_inside_the_spread_is_distinguishable_from_a_fail_outside_it():
    """A point estimate would render these identically, which is the thing the
    instruction forbids."""
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 0.0, "p1": 0.0, "p2": 0.0, "p3": 0.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.status == "FAIL"
    assert verdict.paired_rate_delta == pytest.approx(0.0)
    assert verdict.paired_delta_inside_control_resample_spread is True
    assert "DIFFERENT FINDINGS" in verdict.to_dict()["resample_rule"]


def test_a_not_exercised_cell_reports_no_resample_comparison_rather_than_false():
    """None, not False. A cell that was never tested has no delta to compare, and
    False would read as measured-and-outside-the-noise."""
    pin = build_pin()
    verdict = cc.evaluate_cell(
        cell="fr/f1",
        pin=pin,
        control_scored=[],
        intervened_scored=[],
        void_counts={"not_exercised": 4},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.paired_delta_inside_control_resample_spread is None


def test_a_resample_that_cannot_vary_anything_refuses():
    with pytest.raises(cc.InsufficientControlSet) as caught:
        cc.leave_one_prompt_out_rates(
            [control("z", "en/f1", "p0", 1)], target_outcome_class="POLE_OWN", prompts=["p0"]
        )
    assert "62.2 lattice steps" in str(caught.value)
    with pytest.raises(cc.InsufficientControlSet):
        cc.leave_one_prompt_out_signed_midranges([control("z", "en/f1", "p0", 1)], prompts=["p0"])


def test_a_spread_over_no_values_refuses_rather_than_reporting_zero_uncertainty():
    with pytest.raises(cc.DegenerateControlSet):
        cc.observed_spread([])


def test_the_full_leave_one_out_distribution_is_retained_not_only_its_spread():
    """Do not design a measure that can only report a point estimate."""
    calibration = cc.calibrate_cell(
        "en/f1",
        [
            control(f"a-{seed}-p{i}", "en/f1", f"p{i}", seed, own=5.0 if i == 0 else 0.0)
            for seed in (1, 2)
            for i in range(4)
        ],
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    assert len(calibration.control_rate_loo_values) == 4
    assert calibration.control_rate_loo_values[0] == pytest.approx(0.0)
    record = calibration.to_dict()
    assert len(record["control_rate_loo_values"]) == 4
    assert "62.2 lattice steps of 1/600" in record["resample_rule"]
    assert "POINT ESTIMATE IS NOT ENOUGH" in record["resample_rule"]


def test_the_resample_note_cites_the_measurement_and_the_retention_commit():
    note = cc.RESAMPLE_UNCERTAINTY_IS_NOT_OPTIONAL
    assert "62.2 lattice steps of 1/600" in note
    assert "10 positives per cell" in note
    assert "fr/f1 clears its bar by ONE lattice step and fr/f2 misses by SIX" in note
    assert "5b1da92" in note
    assert "PARAMETER-FREE" in note


# --------------------------------------------------------------- the pin


def build_pin(
    cells=("en/f1", "fr/f1"), n_prompts=4, calibrating_lane_override=None, **kwargs
) -> cc.PinnedCalibration:
    observations: list[cc.ControlObservation] = []
    for cell in cells:
        observations += paired_controls(cell, n_prompts=n_prompts)
    return cc.calibrate(
        observations,
        rubric=synthetic_rubric(),
        cells=cells,
        target_outcome_class="POLE_OWN",
        calibrating_lane=calibrating_lane_override or "researcher",
        selecting_lane="engineer2",
        generating_lane="engineer3",
        generation_settings=SETTINGS,
        generation_settings_digest=SETTINGS_DIGEST,
        now="2026-08-17T00:00:00Z",
        **kwargs,
    )


def test_a_pin_verifies_against_its_own_bytes_and_is_reproducible():
    first = build_pin()
    second = build_pin()
    assert first.digest == second.digest
    assert cc.verify_pin(first.to_dict()) == first.digest
    assert first.body().get("contains_zero_intervened_generations") is True
    assert "digest" not in first.body()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record["cells"][0].__setitem__("rate_margin", 0.0),
        lambda record: record["cells"][0].__setitem__("rate_ceiling", 1.0),
        lambda record: record["cells"][0].__setitem__("neutral_high", 99.0),
        lambda record: record.__setitem__("control_set_digest", "0" * 64),
        lambda record: record.__setitem__("calibrating_lane", "engineer2"),
    ],
)
def test_a_pin_edited_after_pinning_refuses(mutate):
    record = build_pin().to_dict()
    mutate(record)
    with pytest.raises(cc.CalibrationDigestMismatch):
        cc.verify_pin(record)


def test_a_record_with_no_digest_refuses():
    with pytest.raises(cc.CalibrationDigestMismatch):
        cc.verify_pin({"cells": []})


def test_a_pin_file_is_written_as_lf_and_refuses_to_be_overwritten_differently(tmp_path):
    pin = build_pin()
    path = tmp_path / "pin.json"
    assert cc.write_pin(path, pin) == pin.digest
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert cc.write_pin(path, pin) == pin.digest  # idempotent on identical bytes
    other = build_pin(n_prompts=10)
    assert other.digest != pin.digest
    with pytest.raises(cc.CalibrationError) as caught:
        cc.write_pin(path, other)
    assert "not pinned" in str(caught.value)
    assert cc.read_pin(path)["digest"] == pin.digest


def test_reading_a_pin_with_crlf_refuses_because_its_bytes_moved(tmp_path):
    pin = build_pin()
    path = tmp_path / "pin.json"
    cc.write_pin(path, pin)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(cc.CalibrationError) as caught:
        cc.read_pin(path)
    assert "CRLF" in str(caught.value)


def test_an_absent_cell_is_not_exercised_rather_than_a_cell_that_failed():
    pin = build_pin()
    with pytest.raises(cc.CalibrationError) as caught:
        pin.cell("zz/f9")
    assert "NOT EXERCISED" in str(caught.value)


def test_the_bands_carry_the_pin_they_came_from():
    pin = build_pin()
    bands = pin.bands("en/f1")
    assert bands.calibration_digest == pin.digest
    assert "no level chosen" in bands.derivation


# ---------------------------------------------------------------- the seal


def scored_pair(pin: cc.PinnedCalibration, cell: str, own_by_prompt: dict[str, float]):
    rubric = synthetic_rubric()
    bands = pin.bands(cell)

    def read(own: float, mirror: float) -> co.BipolarReading:
        return co.BipolarReading(
            own=co.PoleReading(PERSONA_A, own, rubric), mirror=co.PoleReading(PERSONA_B, mirror, rubric)
        )

    controls = [
        co.score_generation(
            observation_id=f"ctl-{prompt}",
            cell=cell,
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=read(0.0, 3.0),
            firing=control_evidence(),
            bands=bands,
            member_count=0,
        )
        for prompt in own_by_prompt
    ]
    intervened = [
        co.score_generation(
            observation_id=f"amp-{prompt}",
            cell=cell,
            prompt_id=prompt,
            seed=1,
            arm_label="joint",
            kind="amplify",
            reading=read(own, 0.0),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt, own in own_by_prompt.items()
    ]
    return controls, intervened


def test_calibrating_after_a_result_has_been_scored_refuses():
    """THE LOAD-BEARING REFUSAL. Pinning after the fact is the whole thing the
    rule exists to prevent, so it is made impossible rather than prohibited."""
    pin = build_pin()
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 0.0})
    cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert cc.seal_state()["scoring_has_begun"] is True
    assert cc.seal_state()["pin_digest"] == pin.digest
    with pytest.raises(cc.CalibrationSealed) as caught:
        build_pin()
    assert "pinning after the fact" in str(caught.value)


def test_two_different_pins_in_one_scoring_pass_refuse():
    first = build_pin()
    second = build_pin(n_prompts=10)
    assert first.digest != second.digest
    cc.note_scoring_has_begun(first.digest, "obs-1")
    cc.note_scoring_has_begun(first.digest, "obs-2")  # same pin is fine
    with pytest.raises(cc.CalibrationSealed):
        cc.note_scoring_has_begun(second.digest, "obs-3")


def test_the_seal_refuses_a_digest_it_cannot_record():
    with pytest.raises(cc.CalibrationDigestMismatch):
        cc.note_scoring_has_begun("not-a-digest", "obs-1")


# --------------------------------------------------------- the cell verdict


def test_a_cell_with_no_eligible_intervened_generation_is_not_exercised_not_a_fail():
    pin = build_pin()
    verdict = cc.evaluate_cell(
        cell="fr/f1",
        pin=pin,
        control_scored=[],
        intervened_scored=[],
        void_counts={"not_exercised": 4, "zero_dose": 2},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.status == "NOT_EXERCISED"
    assert verdict.crossing_status == "NOT_EXERCISED"
    assert verdict.passed is False
    assert verdict.paired_rate_delta is None
    assert verdict.void_counts == {"not_exercised": 4, "zero_dose": 2}
    assert "VOID, NOT A NULL" in verdict.reason


def test_intervened_generations_with_no_paired_control_refuse():
    pin = build_pin()
    _, intervened = scored_pair(pin, "en/f1", {"p0": 5.0})
    with pytest.raises(cc.EmptyControlSet) as caught:
        cc.evaluate_cell(
            cell="en/f1",
            pin=pin,
            control_scored=[],
            intervened_scored=intervened,
            void_counts={},
            baseline_excluded=0,
            condition=FORWARD_CONDITION,
            intervened_settings=SETTINGS,
            intervened_settings_digest=SETTINGS_DIGEST,
        )
    assert "one-armed reading is not a result" in str(caught.value)


def test_a_baseline_already_at_the_target_pole_is_excluded_and_counted():
    pin = build_pin()
    rubric = synthetic_rubric()
    bands = pin.bands("en/f1")

    def read(own: float, mirror: float) -> co.BipolarReading:
        return co.BipolarReading(
            own=co.PoleReading(PERSONA_A, own, rubric), mirror=co.PoleReading(PERSONA_B, mirror, rubric)
        )

    controls = [
        co.score_generation(
            observation_id=f"ctl-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=read(5.0, 0.0),  # already at POLE_OWN under control
            firing=control_evidence(),
            bands=bands,
            member_count=0,
        )
        for prompt in ("p0", "p1")
    ]
    intervened = [
        co.score_generation(
            observation_id=f"amp-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="joint",
            kind="amplify",
            reading=read(5.0, 0.0),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt in ("p0", "p1")
    ]
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.crossing_status == "NO_ADMISSIBLE_BASELINE"
    assert verdict.baseline_excluded == 2
    # The SUFFICIENCY arm still has a denominator, and it reports honestly: the
    # controls were already at the target pole, so the cell is ceiling-excluded
    # rather than failed. Two criteria, two answers, neither merged.
    assert verdict.status == "CEILING_EXCLUDED_BY_ARITHMETIC"
    assert verdict.passed is False


def test_the_ceiling_is_REACHABLE_and_a_ceilinged_cell_is_never_a_fail():
    """REGRESSION FOR A DEFECT IN THIS FILE'S SUBJECT, found by this test.

    The first `evaluate_cell` computed the control rate over BASELINE-CONDITIONED
    prompts only. A conditioned control sits at the ORIGIN pole and the target is
    the OPPOSITE pole, so the control rate was identically 0 and
    `CEILING_EXCLUDED` could never fire -- a check that passes while unable to
    exercise what it claims. The repair was to give the two criteria the two
    denominators the rulings give them: sufficiency over ALL paired prompts,
    crossing over the conditioned subset. This test makes the ceiling FIRE."""
    pin = build_pin(n_prompts=4)  # resolution 0.25 -> margin 0.25 -> ceiling 0.75
    calibration = pin.cell("en/f1")
    assert calibration.rate_ceiling == pytest.approx(0.75)
    rubric = synthetic_rubric()
    bands = pin.bands("en/f1")

    def read(own: float, mirror: float) -> co.BipolarReading:
        return co.BipolarReading(
            own=co.PoleReading(PERSONA_A, own, rubric), mirror=co.PoleReading(PERSONA_B, mirror, rubric)
        )

    # Three of four controls are ALREADY at the target pole: the concept is
    # largely there before any intervention, so a further gain of at least the
    # margin is arithmetically unavailable.
    control_readings = {"p0": (5.0, 0.0), "p1": (5.0, 0.0), "p2": (5.0, 0.0), "p3": (0.0, 3.0)}
    controls = [
        co.score_generation(
            observation_id=f"ctl-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=read(*values),
            firing=control_evidence(),
            bands=bands,
            member_count=0,
        )
        for prompt, values in control_readings.items()
    ]
    intervened = [
        co.score_generation(
            observation_id=f"amp-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="joint",
            kind="amplify",
            reading=read(5.0, 0.0),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt in control_readings
    ]
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.control_rate == pytest.approx(0.75)
    assert verdict.status == "CEILING_EXCLUDED_BY_ARITHMETIC"
    assert verdict.passed is False
    assert "already there" in verdict.reason
    # The crossing arm still reports over its OWN denominator: only p3's control
    # sat at the origin pole, and it crossed.
    assert verdict.n == 4
    assert verdict.n_admissible_for_crossing == 1
    assert verdict.crossing_status == "EVIDENCED"
    assert verdict.baseline_excluded == 3


def test_the_two_criteria_have_different_denominators():
    """The repair, asserted directly: n and n_admissible_for_crossing differ
    whenever any control sits off the origin pole, and the record says so."""
    pin = build_pin(n_prompts=4)
    rubric = synthetic_rubric()
    bands = pin.bands("en/f1")

    def read(own: float, mirror: float) -> co.BipolarReading:
        return co.BipolarReading(
            own=co.PoleReading(PERSONA_A, own, rubric), mirror=co.PoleReading(PERSONA_B, mirror, rubric)
        )

    control_readings = {"p0": (0.0, 3.0), "p1": (0.0, 3.0), "p2": (1.0, 1.0), "p3": (1.0, 1.0)}
    controls = [
        co.score_generation(
            observation_id=f"ctl-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=read(*values),
            firing=control_evidence(),
            bands=bands,
            member_count=0,
        )
        for prompt, values in control_readings.items()
    ]
    intervened = [
        co.score_generation(
            observation_id=f"amp-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="joint",
            kind="amplify",
            reading=read(5.0, 0.0),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt in control_readings
    ]
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.n == 4
    assert verdict.n_admissible_for_crossing == 2
    assert verdict.crossings == 2
    assert verdict.status == "PASS"
    assert "may not be merged" in verdict.to_dict()["two_criteria_rule"]


def test_a_pass_requires_the_delta_to_EXCEED_the_margin_not_merely_reach_it():
    pin = build_pin(n_prompts=4)
    margin = pin.cell("en/f1").rate_margin
    assert margin == pytest.approx(0.25)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 0.0, "p2": 0.0, "p3": 0.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.paired_rate_delta == pytest.approx(0.25)
    assert verdict.status == "FAIL", "a delta exactly AT the margin does not exceed it"

    cc._reset_seal_for_tests_only()
    pin2 = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin2, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 0.0, "p3": 0.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin2,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.paired_rate_delta == pytest.approx(0.5)
    assert verdict.status == "PASS"
    assert verdict.crossings == 2


def test_crossings_are_counted_through_the_shared_predicate():
    """ASSERTS_BOTH must not be counted as a flip, and the count must come from
    `causal_outcome.crosses` so there is one implementation of the rule."""
    pin = build_pin(n_prompts=4)
    rubric = synthetic_rubric()
    bands = pin.bands("en/f1")

    def read(own: float, mirror: float) -> co.BipolarReading:
        return co.BipolarReading(
            own=co.PoleReading(PERSONA_A, own, rubric), mirror=co.PoleReading(PERSONA_B, mirror, rubric)
        )

    controls = [
        co.score_generation(
            observation_id=f"ctl-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=read(0.0, 3.0),
            firing=control_evidence(),
            bands=bands,
            member_count=0,
        )
        for prompt in ("p0", "p1", "p2", "p3")
    ]
    # p0 flips, p1 asserts both, p2 goes neutral, p3 stays at the origin pole.
    plan = {"p0": (5.0, 0.0), "p1": (6.0, 6.0), "p2": (0.0, 0.0), "p3": (0.0, 3.0)}
    intervened = [
        co.score_generation(
            observation_id=f"amp-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="joint",
            kind="amplify",
            reading=read(*values),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt, values in plan.items()
    ]
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.crossings == 1
    assert verdict.asserts_both == 1
    assert verdict.moved_without_crossing == 1


def test_a_target_pole_that_disagrees_with_the_origin_pole_refuses():
    pin = build_pin()
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0})
    with pytest.raises(cc.CalibrationError) as caught:
        cc.evaluate_cell(
            cell="en/f1",
            pin=pin,
            control_scored=controls,
            intervened_scored=intervened,
            void_counts={},
            baseline_excluded=0,
            condition=FORWARD_CONDITION.mirrored(),
            intervened_settings=SETTINGS,
            intervened_settings_digest=SETTINGS_DIGEST,
        )
    assert "describe different events" in str(caught.value)


def test_the_result_vector_is_the_headline_and_the_scalar_travels_with_it():
    pin = build_pin()
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 0.0})
    passing = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    void = cc.evaluate_cell(
        cell="fr/f1",
        pin=pin,
        control_scored=[],
        intervened_scored=[],
        void_counts={"not_exercised": 4},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    vector = cc.result_vector([passing, void])
    assert [row["status"] for row in vector["vector"]] == ["PASS", "NOT_EXERCISED"]
    assert vector["n_pass_alongside_the_vector"] == 1
    assert vector["status_counts"]["NOT_EXERCISED"] == 1
    assert "PARTIAL is PRE-DECLARED" in vector["partial_is_a_legitimate_outcome"]
    assert set(vector["verdict_state_meanings"]) == set(cc.VERDICT_STATES)
    assert set(vector["crossing_state_meanings"]) == set(cc.CROSSING_STATES)
    assert vector["crossing_status_counts"]["NOT_EXERCISED"] == 1
    with pytest.raises(cc.CalibrationError):
        cc.result_vector([])


# ------------------------------------------------------------ dose reference


def test_the_dose_reference_refuses_an_undeclared_substrate_and_a_zero_measurement():
    with pytest.raises(cc.DoseReferenceUndeclared):
        cc.derive_dose_reference(feature_index=1, substrate="", activations=[1.0])
    with pytest.raises(cc.DoseReferenceUndeclared):
        cc.derive_dose_reference(feature_index=1, substrate="declared", activations=[])
    with pytest.raises(cc.DoseReferenceUndeclared) as caught:
        cc.derive_dose_reference(feature_index=1, substrate="background_corpus_max", activations=[0.0])
    assert "MAXIMAL SELECTIVITY" in str(caught.value)


def test_the_dose_reference_reports_the_substrate_and_its_attained_level():
    reference = cc.derive_dose_reference(
        feature_index=42, substrate="declared_elsewhere", activations=[0.2, 1.5, 0.9]
    )
    assert reference.measured_value == pytest.approx(1.5)
    assert reference.n_substrate_rows == 3
    assert "0.7500" in reference.measurement
    assert "declared_elsewhere" in reference.to_dict()["substrate"]


def test_no_replacement_substrate_is_named_by_this_module():
    """The architect declined to rule it and this lane declines to invent it."""
    note = cc.DOSE_REFERENCE_IS_A_CONTROL_ONLY_MEASUREMENT
    assert "NO DEFAULT SUBSTRATE IS SUPPLIED" in note
    assert "may not be the BACKGROUND corpus maximum" in note


def test_the_unexercised_list_says_no_number_may_be_quoted():
    joined = " ".join(cc.UNEXERCISED_WITHOUT_GPU)
    assert "NO MARGIN, CEILING OR BAND FOR EITHER PERSONA HAS BEEN COMPUTED" in joined


def test_the_selfcheck_runs_clean():
    assert cc.main(["--selfcheck"]) == 0


# ------------------------------------- RULING_15: orientation, coverage, assignment


def test_the_orientation_is_derived_and_a_supplied_pole_cannot_be_passed_at_all():
    """DEFECT_2. There is no argument through which an orientation reaches
    evaluate_cell, so the defect is not merely fixed -- it is inexpressible."""
    import inspect

    parameters = set(inspect.signature(cc.evaluate_cell).parameters)
    assert "origin_pole" not in parameters
    assert "condition" in parameters


def test_the_derived_orientation_travels_on_the_verdict_and_flips_with_the_condition():
    """FIRES AND DOES NOT FIRE, over inputs differing only in the condition."""
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 5.0})
    forward = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert forward.origin_pole_derived == "POLE_MIRROR"
    assert forward.crossing_status == "EVIDENCED"
    # The MIRRORED condition derives the other origin, and on the same data the
    # crossing predicate must stop firing rather than silently returning False
    # under a default nobody chose.
    with pytest.raises(cc.CalibrationError) as caught:
        cc.evaluate_cell(
            cell="en/f1",
            pin=pin,
            control_scored=controls,
            intervened_scored=intervened,
            void_counts={},
            baseline_excluded=0,
            condition=FORWARD_CONDITION.mirrored(),
            intervened_settings=SETTINGS,
            intervened_settings_digest=SETTINGS_DIGEST,
        )
    assert "describe different events" in str(caught.value)


def test_a_pooled_coverage_figure_is_refused_and_a_per_cell_one_is_not():
    cc.refuse_pooled_coverage(["en/f1"])
    cc.refuse_pooled_coverage(["en/f1", "en/f1"])
    with pytest.raises(cc.CalibrationError) as caught:
        cc.refuse_pooled_coverage(["en/f1", "fr/f1"])
    assert "STRATIFIED" in str(caught.value)


def test_a_pin_without_a_usable_generation_settings_digest_refuses():
    with pytest.raises(cc.SettingsDigestMissing) as caught:
        cc.calibrate(
            paired_controls("en/f1", n_prompts=4),
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
            generating_lane="engineer3",
            generation_settings=SETTINGS,
            generation_settings_digest="not-a-digest",
        )
    assert "no producer" in str(caught.value)


def valid_assignment(**overrides):
    payload = {
        "path": "protocols/final_pairing/v1/causal_calibration_assignment.json",
        "sha256": "a" * 64,
        "recorded_by": "committer",
        "assigned_by": "the coordinator",
        "generating_lane_excluded": "engineer3",
        "quantities_covered": cc.ASSIGNED_QUANTITIES,
    }
    payload.update(overrides)
    return cc.AssignmentReference(**payload)


def test_a_self_declared_assignment_is_unwritable_and_a_recorded_one_is_accepted():
    """The gap's structural closure. Both directions."""
    accepted = cc.assert_assignment_is_not_self_declared(
        valid_assignment(), calibrating_lane="researcher"
    )
    assert accepted["recorded_by_is_not_the_calibrating_lane"] is True
    assert "STRICT ANCESTOR" in accepted["discharge_is_ancestry_not_existence"]
    with pytest.raises(cc.AssignmentSelfDeclared) as caught:
        cc.assert_assignment_is_not_self_declared(
            valid_assignment(recorded_by="researcher"), calibrating_lane="researcher"
        )
    assert "IS the calibrating lane" in str(caught.value)
    with pytest.raises(cc.AssignmentSelfDeclared):
        cc.assert_assignment_is_not_self_declared(
            valid_assignment(), calibrating_lane="   "
        )


def test_an_assignment_must_name_the_quantities_not_the_file():
    with pytest.raises(cc.AssignmentSelfDeclared) as caught:
        cc.assert_assignment_is_not_self_declared(
            valid_assignment(quantities_covered=("causal_rate_margin",)),
            calibrating_lane="researcher",
        )
    assert "orphan" in str(caught.value)
    with pytest.raises(cc.AssignmentSelfDeclared):
        cc.AssignmentReference(
            path="p",
            sha256="a" * 64,
            recorded_by="x",
            assigned_by="y",
            generating_lane_excluded="engineer3",
            quantities_covered=(),
        )
    with pytest.raises(cc.AssignmentSelfDeclared):
        cc.AssignmentReference(
            path="p",
            sha256="short",
            recorded_by="x",
            assigned_by="y",
            generating_lane_excluded="engineer3",
            quantities_covered=cc.ASSIGNED_QUANTITIES,
        )


def test_a_hash_bound_assignment_reaches_the_pin_and_its_absence_is_recorded():
    pinned = build_pin(assignment=valid_assignment())
    record = pinned.to_dict()
    assert record["assignment_is_hash_bound"] is True
    assert record["assignment"]["recorded_by"] == "committer"
    unassigned = build_pin()
    assert unassigned.to_dict()["assignment_is_hash_bound"] is False
    assert "There is no protocol artifact assigning it" in unassigned.to_dict()["assignment_record"]


def test_the_pin_refuses_a_self_declared_assignment_at_calibrate_time():
    with pytest.raises(cc.AssignmentSelfDeclared):
        build_pin(assignment=valid_assignment(recorded_by="researcher"))


def test_the_ceiling_reports_the_unexcluded_high_baseline_residue():
    """The arithmetic ceiling's scope, made visible per cell."""
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 0.0, "p2": 0.0, "p3": 0.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    assert verdict.status == "FAIL"
    assert verdict.distance_to_arithmetic_ceiling == pytest.approx(0.75)
    record = verdict.to_dict()
    assert "may never license" in record["unexcluded_high_baseline_residue"]
    assert "headroom" in record["unexcluded_high_baseline_residue"]


def test_the_margin_actually_used_is_asserted_strictly_positive():
    """RESAMPLE BOUND_2, and BOTH directions.

    On real input the 1/n resolution is always positive so the assertion cannot
    fire -- which is exactly why it must be exercisable somewhere. The check is a
    named helper, so a zero margin can be handed to it directly rather than
    reached through mock gymnastics that would prove only that mocks work."""
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    assert calibration.rate_margin > 0.0
    # DOES NOT FIRE on a positive margin.
    assert cc.assert_margin_binds("en/f1", 0.25, {"rate_resolution": 0.25}) == 0.25
    # FIRES on a margin that binds nothing.
    for vacuous in (0.0, -0.1):
        with pytest.raises(cc.DegenerateControlSet) as caught:
            cc.assert_margin_binds("en/f1", vacuous, {"rate_resolution": 0.0})
        assert "binds nothing" in str(caught.value)


def test_crossing_reachability_fires_both_ways():
    """A band inside the lattice leaves expressible values outside it; a band
    covering the whole lattice does not."""
    reachable = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    report = cc.crossing_reachability(reachable)
    assert report["crossing_reachable_on_this_lattice"] is True
    assert report["finding_if_not"] is None
    assert report["lattice_points"] == co.CLAIM_TYPE_EXTENT_DIFFERENCE_POINTS

    wide = [
        control("a", "en/f1", "p0", 1, own=6.0),
        control("b", "en/f1", "p1", 1, mirror=6.0),
        control("c", "en/f1", "p0", 2, own=6.0),
        control("d", "en/f1", "p1", 2, mirror=6.0),
    ]
    saturated = cc.calibrate_cell(
        "en/f1", wide, rubric=synthetic_rubric(), target_outcome_class="POLE_OWN"
    )
    report = cc.crossing_reachability(saturated)
    assert report["crossing_reachable_on_this_lattice"] is False
    assert "UNREACHABLE ON THIS LATTICE" in report["finding_if_not"]
    assert "PROHIBITED" in report["finding_if_not"]


# ===========================================================================
# RULING_15's GENERAL CLAUSE, APPLIED RETROACTIVELY, AND THE SERIALIZATION
# LESSON FROM JOB 418185.
#
# Engineer 2 built the per-item retention, validated it against its own declared
# scope, and never asserted that the object WRITTEN TO DISK carried it. Fourteen
# tests passed because they exercised the builder and the verifier DIRECTLY; the
# values were computed, validated, then dropped one layer out, and job 418185
# came back with the field occurring ZERO times at byte level in all four grids.
# Its diagnosis is the part that generalises: THE SERIALIZATION PREDICATE HAD
# EVERY TEST A DOES-NOT-FIRE AND NONE A FIRES, which is why it could not tell a
# recorded retention from an unrecorded one. Two independent instances of that in
# one sprint, and in both the POSITIVE direction was the missing one.
#
# So these tests assert over BYTES, not over the objects that produced them.
# ===========================================================================


#: Every quantity this lane computes and would lose if a `to_dict` forgot it.
#: Named explicitly so that adding a field to `CellCalibration` without adding it
#: here is itself a failure -- an allow-list that is silently incomplete is the
#: same defect one level up.
PIN_FIELDS_THAT_MUST_REACH_THE_BYTES = (
    "rate_margin",
    "rate_ceiling",
    "rate_resolution",
    "observed_null_rate_difference_max",
    "control_rate_loo_spread",
    "control_rate_loo_values",
    "signed_loo_spread",
    "margin_bound_by",
    "neutral_low",
    "neutral_high",
    "assertion_floor",
    "attained_level_signed_band",
    "attained_level_rate_margin",
    "replicate_rates",
    "generation_settings_digest",
    "control_set_digest",
    "assignment_is_hash_bound",
    "contains_zero_intervened_generations",
)


def _pin_keys(record: dict) -> set[str]:
    """Every KEY in a pin record, at the top level and per cell.

    KEYS, NOT SUBSTRINGS, and the first version of this check got that wrong in
    the most instructive possible place. It scanned the file TEXT for each field
    name, and `rate_margin` also occurs inside `resample_rule`,
    `stated_limitations` and the VALUES of `margin_bound_by` -- so deleting the
    field left the substring in place and the check could not fire at all. A
    check unable to distinguish a recorded field from an unrecorded one IS the
    418185 defect, and it had reappeared inside the check written to catch it.
    It is also the same substring mistake as the earlier n-and-N guard, which is
    twice now that a text scan stood in for a structural one. Structure is the
    only thing here that can fail."""
    keys = set(record)
    for cell in record.get("cells", []):
        keys |= set(cell)
    return keys


def test_every_computed_field_reaches_the_BYTES_written_to_disk(tmp_path):
    """DOES NOT FIRE on a complete record. Asserted over the FILE, not the object.

    Job 418185's defect shape run against this lane's own writer: not "does the
    builder compute it" but "is it in the file". Engineer 2's fourteen tests
    passed because they exercised the builder and verifier directly, and the
    value was dropped one layer out."""
    pin = build_pin(assignment=valid_assignment())
    path = tmp_path / "pin.json"
    cc.write_pin(path, pin)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    written = json.loads(raw.decode("utf-8"))
    present = _pin_keys(written)
    missing = [field for field in PIN_FIELDS_THAT_MUST_REACH_THE_BYTES if field not in present]
    assert missing == [], f"computed but never serialized: {missing}"
    # The ALLOW-LIST must itself be complete: a field added to CellCalibration and
    # not serialized has to fail HERE, so the declared dataclass fields are
    # compared against what the bytes actually carry.
    declared = set(cc.CellCalibration.__dataclass_fields__)
    serialized = set(written["cells"][0])
    assert declared - serialized == set(), (
        f"CellCalibration fields absent from the written bytes: {sorted(declared - serialized)}"
    )
    assert written["assignment"]["recorded_by"] == "committer"


def test_the_serialization_check_FIRES_when_any_field_is_dropped():
    """THE POSITIVE DIRECTION, the one that was missing in 418185.

    Every field in the allow-list is removed in turn and the check must catch
    each one. Over ALL of them rather than a sample, because the field that goes
    missing in production is never the one the sample happened to include."""
    pin = build_pin(assignment=valid_assignment())
    record = json.loads(json.dumps(pin.to_dict()))
    undetected: list[str] = []
    for victim in PIN_FIELDS_THAT_MUST_REACH_THE_BYTES:
        crippled = json.loads(json.dumps(record))
        if victim in crippled:
            del crippled[victim]
        elif victim in crippled["cells"][0]:
            for cell in crippled["cells"]:
                del cell[victim]
        else:  # pragma: no cover - would mean the allow-list is wrong
            undetected.append(f"{victim} (absent to begin with)")
            continue
        if victim in _pin_keys(crippled):
            undetected.append(victim)
    assert undetected == [], (
        f"dropping {undetected} was not detected -- the check cannot distinguish a recorded field "
        f"from an unrecorded one, which is exactly the 418185 defect"
    )


def test_the_verdict_serializes_every_field_it_computes():
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 5.0})
    verdict = cc.evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={"not_exercised": 1},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
        intervened_settings=SETTINGS,
        intervened_settings_digest=SETTINGS_DIGEST,
    )
    text = json.dumps(verdict.to_dict())
    declared = set(cc.CellVerdict.__dataclass_fields__)
    serialized = set(verdict.to_dict())
    assert declared - serialized == set(), f"CellVerdict fields lost in to_dict: {declared - serialized}"
    for field in ("origin_pole_derived", "distance_to_arithmetic_ceiling", "margin_bound_by"):
        assert field in text


# --------------- the one-directional predicates, given their missing direction


def test_observed_spread_fires_on_empty_and_does_not_on_a_populated_set():
    assert cc.observed_spread([0.25, 0.75]) == pytest.approx(0.5)
    assert cc.observed_spread([1.0]) == pytest.approx(0.0)
    with pytest.raises(cc.DegenerateControlSet):
        cc.observed_spread([])


def test_the_leave_one_out_helpers_return_values_as_well_as_refusing():
    rows = paired_controls("en/f1", n_prompts=3)
    rates = cc.leave_one_prompt_out_rates(
        rows, target_outcome_class="POLE_OWN", prompts=["p0", "p1", "p2"]
    )
    assert rates == (0.0, 0.0, 0.0)
    midranges = cc.leave_one_prompt_out_signed_midranges(rows, prompts=["p0", "p1", "p2"])
    assert midranges == (0.0, 0.0, 0.0)
    with pytest.raises(cc.InsufficientControlSet):
        cc.leave_one_prompt_out_rates(rows, target_outcome_class="POLE_OWN", prompts=["p0"])


def test_minimum_controls_for_level_returns_as_well_as_refusing():
    assert cc.minimum_controls_for_level(0.75) == 3
    with pytest.raises(cc.CalibrationError):
        cc.minimum_controls_for_level(1.0)


def test_read_pin_succeeds_as_well_as_refusing(tmp_path):
    pin = build_pin()
    path = tmp_path / "pin.json"
    cc.write_pin(path, pin)
    assert cc.read_pin(path)["digest"] == pin.digest
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(cc.CalibrationError):
        cc.read_pin(path)


def test_digest_control_set_changes_and_does_not_change_for_the_right_reasons():
    rows = paired_controls("en/f1", n_prompts=3)
    baseline = cc.digest_control_set(rows)
    assert cc.digest_control_set(list(reversed(rows))) == baseline
    changed = list(rows)
    changed[0] = control("en/f1-1-p0", "en/f1", "p0", 1, own=6.0)
    assert cc.digest_control_set(changed) != baseline


def test_crossing_reachability_refuses_nothing_but_answers_both_ways():
    """It is a REPORT, not a guard, so its two directions are its two answers --
    and both are asserted in test_crossing_reachability_fires_both_ways. Here the
    shape of the report itself is pinned, so a field cannot vanish silently."""
    calibration = cc.calibrate_cell(
        "en/f1",
        paired_controls("en/f1", n_prompts=4),
        rubric=synthetic_rubric(),
        target_outcome_class="POLE_OWN",
    )
    report = cc.crossing_reachability(calibration)
    assert set(report) == {
        "cell",
        "lattice_points",
        "lattice_step_in_claim_types",
        "neutral_band",
        "expressible_values_outside_the_band",
        "crossing_reachable_on_this_lattice",
        "finding_if_not",
    }


# ===========================================================================
# RULING_16 CONTAINMENT_2: THE SETTINGS DIGEST, WHICH PREVIOUSLY COULD NOT FAIL.
# ===========================================================================


def test_the_contract_covers_the_settings_that_could_make_the_arms_differ():
    """The field set is the contract. Each entry carries WHY omitting it is
    unsafe, because an omission without a reason is indistinguishable from an
    oversight -- and the deliberate omissions carry reasons too."""
    names = [name for name, _ in cc.GENERATION_SETTINGS_FIELDS]
    assert len(names) == len(set(names)), "a duplicated field would be hashed twice"
    for name, why in cc.GENERATION_SETTINGS_FIELDS:
        assert why.strip(), f"{name} has no recorded reason"
    # The settings most likely to drift between two arms sharing a code path.
    for expected in (
        "model_reference",
        "sae_reference",
        "layer",
        "hook_name",
        "dtype",
        "max_new_tokens",
        "do_sample",
        "temperature",
        "prompt_set_digest",
        "prompt_render_digest",
        "transformers_version",
    ):
        assert expected in names
    # SEED IS EXCLUDED ON PURPOSE and the reason is recorded: replicates differ
    # by seed BY DESIGN, so a digest covering it could never match.
    assert "seed" not in names
    assert "seed_policy" in names
    assert "BREAK the check" in cc.GENERATION_SETTINGS_DELIBERATE_OMISSIONS["seed"]
    assert "intervention_parameters" in cc.GENERATION_SETTINGS_DELIBERATE_OMISSIONS


def test_the_digest_is_order_independent_and_changes_with_any_covered_field():
    """A canonical form that depended on dict order would make two identical
    settings maps disagree; one that ignored a field would make two different
    runs agree. Both are checked."""
    shuffled = dict(reversed(list(SETTINGS.items())))
    assert cc.generation_settings_digest(shuffled) == SETTINGS_DIGEST
    for name, _ in cc.GENERATION_SETTINGS_FIELDS:
        drifted = dict(SETTINGS, **{name: "CHANGED"})
        assert cc.generation_settings_digest(drifted) != SETTINGS_DIGEST, (
            f"changing {name} did not change the digest, so that field is covered in name only"
        )


def test_the_canonical_form_refuses_a_missing_and_an_unexpected_field():
    with pytest.raises(cc.SettingsDigestMissing) as caught:
        cc.generation_settings_digest({k: v for k, v in SETTINGS.items() if k != "layer"})
    assert "layer" in str(caught.value)
    with pytest.raises(cc.SettingsDigestMissing) as caught:
        cc.generation_settings_digest(dict(SETTINGS, surprise="x"))
    assert "MEANING without changing" in str(caught.value)


def test_settings_identity_DOES_NOT_FIRE_on_a_genuine_match():
    """The negative direction, and NOT with a constant on both sides: both
    digests are computed through the contract from their own field maps."""
    control = dict(SETTINGS)
    intervened = dict(reversed(list(SETTINGS.items())))
    record = cc.assert_settings_identity(
        control_settings=control,
        control_digest=cc.generation_settings_digest(control),
        intervened_settings=intervened,
        intervened_digest=cc.generation_settings_digest(intervened),
    )
    assert record["identical"] is True
    assert record["settings_digest"] == SETTINGS_DIGEST
    assert "does NOT establish" in record["what_this_establishes"]


@pytest.mark.parametrize("field", [name for name, _ in cc.GENERATION_SETTINGS_FIELDS])
def test_settings_identity_FIRES_on_a_difference_in_ANY_covered_field(field: str):
    """Over EVERY field rather than a sample: the setting that drifts in
    production is never the one the sample happened to include."""
    intervened = dict(SETTINGS, **{field: "DIFFERENT"})
    with pytest.raises(cc.SettingsIdentityMismatch) as caught:
        cc.assert_settings_identity(
            control_settings=SETTINGS,
            control_digest=SETTINGS_DIGEST,
            intervened_settings=intervened,
            intervened_digest=cc.generation_settings_digest(intervened),
        )
    message = str(caught.value)
    assert field in message, "the refusal must NAME what differed, not just say the digests differ"
    assert "DIFFERENT" in message


@pytest.mark.parametrize("digest", [None, "", "not-hex", "A" * 64, "a" * 63])
def test_an_unusable_digest_on_either_arm_REFUSES_and_is_never_read_as_a_match(digest):
    """THE VACUITY GUARD. This is the exact state the field was in before the
    contract existed: a value with no producer, treated as satisfied."""
    with pytest.raises(cc.SettingsDigestMissing):
        cc.assert_settings_identity(
            control_settings=SETTINGS,
            control_digest=digest,
            intervened_settings=SETTINGS,
            intervened_digest=SETTINGS_DIGEST,
        )
    with pytest.raises(cc.SettingsDigestMissing):
        cc.assert_settings_identity(
            control_settings=SETTINGS,
            control_digest=SETTINGS_DIGEST,
            intervened_settings=SETTINGS,
            intervened_digest=digest,
        )


def test_a_producer_whose_digest_disagrees_with_its_own_fields_refuses():
    """Catches a producer that hashes one thing and reports another. Neither the
    digest nor the field map can be trusted then, and which describes the run
    cannot be decided by the consumer."""
    with pytest.raises(cc.SettingsDigestInconsistent) as caught:
        cc.assert_settings_identity(
            control_settings=SETTINGS,
            control_digest=cc.generation_settings_digest(dict(SETTINGS, dtype="fp32")),
            intervened_settings=SETTINGS,
            intervened_digest=SETTINGS_DIGEST,
        )
    assert "bound nothing" in str(caught.value)


def test_evaluate_cell_REFUSES_an_intervened_arm_whose_settings_differ():
    """THE POINT OF THE WHOLE CONTRACT, at the place the boundary judges an
    output. Fires on a drifted arm and does not fire on a matching one."""
    pin = build_pin(n_prompts=4)
    controls, intervened = scored_pair(pin, "en/f1", {"p0": 5.0, "p1": 5.0, "p2": 5.0, "p3": 5.0})
    kwargs = dict(
        cell="en/f1",
        pin=pin,
        control_scored=controls,
        intervened_scored=intervened,
        void_counts={},
        baseline_excluded=0,
        condition=FORWARD_CONDITION,
    )
    verdict = cc.evaluate_cell(
        **kwargs, intervened_settings=SETTINGS, intervened_settings_digest=SETTINGS_DIGEST
    )
    assert verdict.status == "PASS"
    assert verdict.settings_digest_verified == SETTINGS_DIGEST
    assert "VERIFIED EQUAL" in verdict.to_dict()["settings_identity_rule"]

    cc._reset_seal_for_tests_only()
    drifted = dict(SETTINGS, max_new_tokens="9999")
    with pytest.raises(cc.SettingsIdentityMismatch) as caught:
        cc.evaluate_cell(
            **kwargs,
            intervened_settings=drifted,
            intervened_settings_digest=cc.generation_settings_digest(drifted),
        )
    assert "max_new_tokens" in str(caught.value)


def test_the_pin_carries_the_settings_MAP_not_only_the_digest(tmp_path):
    """A digest alone cannot name what differed. The map has to reach the bytes."""
    pin = build_pin(assignment=valid_assignment())
    path = tmp_path / "pin.json"
    cc.write_pin(path, pin)
    written = json.loads(path.read_bytes().decode("utf-8"))
    assert written["generation_settings"] == SETTINGS
    assert written["generation_settings_digest"] == SETTINGS_DIGEST
    covered = {entry["field"] for entry in written["generation_settings_fields_and_why"]}
    assert covered == {name for name, _ in cc.GENERATION_SETTINGS_FIELDS}
    assert "seed" in written["generation_settings_deliberate_omissions"]


def test_this_lane_does_not_derive_the_digest_from_an_artifact():
    """The consumer specifies the FORM and verifies; it must never compute the
    value from something it was handed, because a digest the consumer derives
    agrees with itself by construction."""
    source = (FINAL_PAIRING / "causal_calibration.py").read_bytes().decode("utf-8")
    assert "THE PRODUCER CALLS THIS" in source
    assert "not a binding, it is a\n  restatement" in source or "restatement" in source
    # calibrate() must VERIFY the digest it is handed, never compute it.
    body = source[source.index("def calibrate("):source.index("def verify_pin(")]
    assert "_check_one_arm(" in body
    assert "generation_settings_digest(generation_settings)" not in body


# ------------------------------------------------------- G-CAL as a field


def test_G_CAL_is_enforced_by_a_field_and_fires_both_ways():
    """RULING_16 P1, both directions plus the vacuity guard."""
    # DOES NOT FIRE: today's configuration.
    pin = build_pin()
    assert pin.generating_lane_excluded == "engineer3"
    assert pin.to_dict()["generating_lane_excluded"] == "engineer3"
    # FIRES under case-folding.
    with pytest.raises(cc.CalibrationError) as caught:
        build_pin(calibrating_lane_override="engineer3")
    assert "PRODUCES O MAY NOT BE THE LANE THAT FIXES B" in str(caught.value)


@pytest.mark.parametrize("blank", ["", "   "])
def test_an_empty_generating_lane_refuses_rather_than_passing_vacuously(blank: str):
    with pytest.raises(cc.CalibrationError) as caught:
        cc.calibrate(
            paired_controls("en/f1", n_prompts=4),
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
            generating_lane=blank,
            generation_settings=SETTINGS,
            generation_settings_digest=SETTINGS_DIGEST,
        )
    assert "vacuously" in str(caught.value)


def test_the_assignment_carries_the_generating_lane_and_refuses_a_collision():
    accepted = cc.assert_assignment_is_not_self_declared(
        valid_assignment(), calibrating_lane="researcher"
    )
    assert accepted["generating_lane_is_not_the_calibrating_lane"] is True
    with pytest.raises(cc.AssignmentSelfDeclared) as caught:
        cc.assert_assignment_is_not_self_declared(
            valid_assignment(generating_lane_excluded="Researcher"), calibrating_lane="researcher"
        )
    assert "BOTH the generating" in str(caught.value)
    with pytest.raises(cc.AssignmentSelfDeclared):
        cc.AssignmentReference(
            path="p",
            sha256="a" * 64,
            recorded_by="x",
            assigned_by="y",
            generating_lane_excluded="  ",
            quantities_covered=cc.ASSIGNED_QUANTITIES,
        )


def test_a_repin_is_a_record_repair_when_the_values_do_not_move():
    """RULING_16's ordered note, both directions. Nothing is in this state today
    -- no boundary exists -- so this is the rule written before it is needed."""
    pin = build_pin()
    same = cc.assert_repin_is_a_record_repair(pin.to_dict(), pin)
    assert same["record_repair"] is True
    assert "RECORD REPAIR" in same["disposition"]
    previous = json.loads(json.dumps(pin.to_dict()))
    previous["cells"][0]["rate_margin"] = 0.99
    moved = cc.assert_repin_is_a_record_repair(previous, pin)
    assert moved["record_repair"] is False
    assert "rate_margin" in moved["changed_boundary_values"][pin.cells[0].cell]
    assert "itself the finding" in moved["disposition"]
