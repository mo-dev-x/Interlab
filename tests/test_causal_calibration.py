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
        )
    with pytest.raises(cc.EmptyControlSet):
        cc.calibrate(
            [],
            rubric=synthetic_rubric(),
            cells=("en/f1",),
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
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
        "en/f1", rows, rubric=synthetic_rubric(resolution=0.5), target_outcome_class="POLE_OWN"
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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


def build_pin(cells=("en/f1", "fr/f1"), n_prompts=4, **kwargs) -> cc.PinnedCalibration:
    observations: list[cc.ControlObservation] = []
    for cell in cells:
        observations += paired_controls(cell, n_prompts=n_prompts)
    return cc.calibrate(
        observations,
        rubric=synthetic_rubric(),
        cells=cells,
        target_outcome_class="POLE_OWN",
        calibrating_lane="researcher",
        selecting_lane="engineer2",
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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
            origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
    )
    assert verdict.crossing_status == "NO_ADMISSIBLE_BASELINE"
    assert verdict.baseline_excluded == 2
    # The SUFFICIENCY arm still has a denominator, and it reports honestly: the
    # controls were already at the target pole, so the cell is ceiling-excluded
    # rather than failed. Two criteria, two answers, neither merged.
    assert verdict.status == "CEILING_EXCLUDED"
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
        origin_pole="POLE_MIRROR",
    )
    assert verdict.control_rate == pytest.approx(0.75)
    assert verdict.status == "CEILING_EXCLUDED"
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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
        origin_pole="POLE_MIRROR",
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
            origin_pole="POLE_OWN",
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
        origin_pole="POLE_MIRROR",
    )
    void = cc.evaluate_cell(
        cell="fr/f1",
        pin=pin,
        control_scored=[],
        intervened_scored=[],
        void_counts={"not_exercised": 4},
        baseline_excluded=0,
        origin_pole="POLE_MIRROR",
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
