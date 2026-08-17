"""CPU-only tests for scripts/final_pairing/group_selection.py.

CONTROLS FIRST. The first block of this file is the two refusal classes the
selector exists to be safe against -- VACUITY (a completeness claim computed
over an empty pool, which already happened once in this sprint) and SILENT
FALLBACK TO THE COLLAPSED DATA (a selector reaching for `min_*` when the
per-cell retention is missing). Only after those does anything test a
successful selection.

NO GPU, NO MODEL WEIGHTS, NO GENERATION. Group selection is set arithmetic
over a boolean matrix, so every test here runs on real numpy arrays and
real production code paths: `A[f, c]` is always built by the discovery
runner's own `build_admissibility_matrix`, never by a private
reimplementation that could agree with the selector while disagreeing with
production. The one place a fake appears is the `Backend` used to produce a
genuine end-to-end scan, which is the established convention in this suite
(no real Gemma/Qwen weights exist on any machine in this investigation).

THE EXACTNESS CLAIM IS TESTED AGAINST BRUTE FORCE. RULING_13 Q1 clause 8
refuses greedy for cover construction because the exact answer is available,
and `minimum` is load-bearing for the minimality-under-removal requirement.
So `test_the_exact_minimum_and_the_whole_solution_set_agree_with_brute_force`
enumerates EVERY subset of the admissible pool up to |C| members on randomly
generated matrices and requires the selector's minimum arity AND its
complete solution set to match, set for set.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import group_selection as gs  # noqa: E402
from final_pairing_fakes import make_fake_gemma_backend  # noqa: E402

CELLS = gs.SIX_CELLS
DECLARED = (gs.TIER_S, gs.TIER_C)


def _problem_from_patterns(patterns, *, d_sae=64, tier=gs.TIER_C, concept_id="surrogate", **kwargs):
    return gs.surrogate_problem(
        patterns=patterns, d_sae=d_sae, tier=tier, tiers_declared_in_advance=DECLARED,
        concept_id=concept_id, label="pytest surrogate", **kwargs
    )


def _mask_of(problem, group):
    vector = gs.coverage_vector(problem, group)
    return sum(1 << i for i, bit in enumerate(vector) if bit)


def _brute_force_minimum_covers(problem, target_mask):
    """Every minimum-cardinality cover of `target_mask`, found by exhaustive
    enumeration over subsets of the pool. Deliberately the dumbest possible
    implementation -- its only job is to be obviously correct."""
    pool = problem.pool
    for k in range(1, problem.n_cells + 1):
        found = {
            frozenset(combo)
            for combo in itertools.combinations(pool, k)
            if (_mask_of(problem, combo) & target_mask) == target_mask
        }
        if found:
            return k, found
    return None, set()


# ---------------------------------------------------------------------------
# CONTROL BLOCK 1 -- VACUITY
# ---------------------------------------------------------------------------


def test_the_empty_set_is_never_complete():
    """`all([])` is True. A group with no members must not inherit that:
    `cov(emptyset) = 0^|C|`, and the empty set is not a cover of anything."""
    problem = _problem_from_patterns({"111111": 1})
    assert gs.coverage_vector(problem, ()) == (0, 0, 0, 0, 0, 0)
    assert gs.coverage_size(gs.coverage_vector(problem, ())) == 0
    assert gs.is_complete(problem, ()) is False
    # And the trap itself, stated so the difference is visible in the file.
    assert all(gs.is_complete(problem, g) for g in []) is True


def test_a_universe_with_no_cells_refuses_instead_of_reporting_completeness():
    """With zero cells `all()` over the coverage vector is True, so EVERY
    set would be 'complete'. That is refused at construction, with the
    scan's own exception class."""
    with pytest.raises(gs.PerCellRetentionMissing, match="vacuity defect"):
        gs.CoverageProblem(
            concept_id="x", tier=gs.TIER_C, cell_order=(), admissible_by_cell={},
            pattern_to_features={}, features_admissible_in_no_cell=0, features_scored=0,
            data_provenance="SURROGATE", tiers_declared_in_advance=(gs.TIER_C,),
        )


def test_a_concept_with_zero_admissible_features_produces_zero_groups_loudly():
    """THE DEFECT THAT ALREADY BIT. An admissibility check passed while
    computing cov() over the empty set, because the surrogate had zero
    admissible features and 'all groups complete' was therefore true and
    worthless. A concept with no admissible feature must produce zero groups
    with a status that says so, and must be DISTINGUISHABLE from a concept
    that has groups."""
    empty = _problem_from_patterns({}, concept_id="zero_admissible")
    result = gs.select_groups(empty)
    assert result.status == gs.STATUS_NO_ADMISSIBLE
    assert result.pool_size == 0
    assert result.groups == ()
    assert result.emitted_group_count == 0
    assert result.complete_group_count == 0
    assert result.all_groups_complete is False
    assert result.best_achievable_coverage == (0, 0, 0, 0, 0, 0)
    assert "ZERO" in " ".join(result.notes)
    assert "no candidates" in gs.claim_sentence(result)

    # Distinguishable, on the field a reader would actually look at.
    populated = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1}))
    assert populated.status == gs.STATUS_COMPLETE
    assert populated.status != result.status
    assert populated.all_groups_complete is True
    assert populated.pool_size == 2


def test_all_groups_complete_is_false_over_zero_groups_where_all_would_say_true():
    result = gs.select_groups(_problem_from_patterns({}))
    assert all(g.complete for g in result.groups) is True  # the trap
    assert result.all_groups_complete is False  # the field that does not fall for it


def test_assert_not_vacuous_refuses_a_completeness_claim_over_an_empty_pool():
    """The guard is exercised on a forged record, because nothing in the
    selector can produce one -- and the defect it names was not detected by
    the code that produced it, so the guard exists anyway."""
    good = gs.select_groups(_problem_from_patterns({"111111": 1}))
    gs.assert_not_vacuous(good)  # the passing direction, first
    forged = gs.GroupSelectionResult(
        **{**{k: getattr(good, k) for k in good.__dataclass_fields__}, "pool_size": 0}
    )
    with pytest.raises(gs.VacuousCoverageClaim, match="vacuity defect"):
        gs.assert_not_vacuous(forged)


def test_an_empty_target_mask_is_refused_rather_than_covered_by_nothing():
    problem = _problem_from_patterns({"111111": 1})
    with pytest.raises(gs.VacuousCoverageClaim, match="nothing to cover"):
        gs.exact_minimum_cover(problem, target_mask=0)


# ---------------------------------------------------------------------------
# CONTROL BLOCK 2 -- NO SILENT FALLBACK TO THE COLLAPSED DATA
# ---------------------------------------------------------------------------


def test_the_refusal_class_is_the_scans_own_class_not_a_look_alike():
    """One refusal identity for the whole sprint. Two classes with the same
    name would let a consumer's `except` miss the other's refusal, which is
    how a hard refusal quietly becomes a fallback."""
    assert gs.PerCellRetentionMissing is d.PerCellRetentionMissing
    assert gs._DISCOVERY.__file__ == str(
        (REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_concept_discovery.py").resolve()
    )
    # And the file-identity guard refuses a stub that carries the name only.
    with pytest.raises(gs.GroupSelectionError, match="requires"):
        gs._import_module_from_exact_file(
            "final_pairing_concept_discovery",
            REPO_ROOT / "scripts" / "final_pairing" / "group_selection.py",
            why="pytest",
        )


def test_a_record_carrying_only_the_collapsed_minima_is_refused():
    with pytest.raises(gs.PerCellRetentionMissing, match="QUALIFIER, not a RANKER"):
        gs.build_problem_from_record(
            {"min_separation_auroc": [0.99] * 8, "min_fire_rate": [0.9] * 8,
             "min_near_miss_auroc": [0.9] * 8},
            tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="cheese",
            data_provenance="SURROGATE",
        )


def test_a_record_predating_the_matrix_is_distinguished_from_no_admissible_feature():
    """`None` says 'this record does not say'; an empty support says 'no
    feature is admissible'. Conflating them turns a stale record into a
    scientific finding."""
    with pytest.raises(gs.PerCellRetentionMissing, match="predates"):
        gs.build_problem_from_record(
            None, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="cheese",
            data_provenance="SURROGATE",
        )
    # The other side of the distinction reaches a RESULT, not an exception.
    assert gs.select_groups(_problem_from_patterns({})).status == gs.STATUS_NO_ADMISSIBLE


def test_a_partial_or_wrongly_typed_matrix_is_refused():
    with pytest.raises(gs.PerCellRetentionMissing, match="no per-cell retention"):
        gs.build_problem_from_matrix(
            None, cell_keys=CELLS, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED,
            concept_id="cheese", data_provenance="SURROGATE",
        )
    with pytest.raises(gs.PerCellRetentionMissing, match="dtype"):
        gs.build_problem_from_matrix(
            np.ones((8, 6)), cell_keys=CELLS, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED,
            concept_id="cheese", data_provenance="SURROGATE",
        )
    with pytest.raises(gs.PerCellRetentionMissing, match="expected"):
        gs.build_problem_from_matrix(
            np.ones((8, 3), dtype=bool), cell_keys=CELLS, tier=gs.TIER_C,
            tiers_declared_in_advance=DECLARED, concept_id="cheese", data_provenance="SURROGATE",
        )
    with pytest.raises(gs.PerCellRetentionMissing, match="missing the cells"):
        gs.build_problem_from_record(
            {"cell_order": list(CELLS), "admissible_feature_indices_by_cell": {CELLS[0]: [1]}},
            tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="cheese",
            data_provenance="SURROGATE",
        )


def test_the_per_cell_support_decides_and_a_misleading_minimum_is_never_read():
    """THE BEHAVIOURAL VERSION OF 'min IS NOT A RANKER'. This record carries
    per-cell support that supports a 2-feature complete cover AND `min_*`
    arrays that say nothing is admissible anywhere. If the selector ever
    consulted the collapsed arrays the answer would flip, so the answer is
    the test."""
    honest = _problem_from_patterns({"111000": 1, "000111": 1})
    record = {
        "cell_order": list(CELLS),
        "admissible_feature_indices_by_cell": {
            cell: sorted(honest.admissible_by_cell[cell]) for cell in CELLS
        },
        # Deliberately contradictory collapsed limbs.
        "min_separation_auroc": [0.0] * 64,
        "min_fire_rate": [0.0] * 64,
        "min_near_miss_auroc": [0.0] * 64,
    }
    problem = gs.build_problem_from_record(
        record, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="cheese",
        data_provenance="SURROGATE",
    )
    result = gs.select_groups(problem)
    assert result.status == gs.STATUS_COMPLETE
    assert result.search.minimum_arity == 2
    assert result.groups[0].coverage == (1, 1, 1, 1, 1, 1)


def test_an_error_verdict_in_a_grid_is_refused_not_read_as_a_null(tmp_path):
    grid = tmp_path / "grid.json"
    grid.write_text(
        json.dumps({"pairing": "gemma-3-12b-it", "verdicts": [
            {"concept_id": "cheese", "status": "error", "error": "CudaOOM: boom",
             "admissibility_matrix": None}
        ]}),
        encoding="utf-8",
    )
    with pytest.raises(gs.PerCellRetentionMissing, match="ERROR cell"):
        gs.load_problems_from_grid(grid, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED)


def test_a_grid_is_read_from_the_exact_path_and_never_globbed(tmp_path):
    with pytest.raises(FileNotFoundError, match="never globs"):
        gs.load_problems_from_grid(
            tmp_path / "nope" / "grid.json", tier=gs.TIER_C, tiers_declared_in_advance=DECLARED
        )


# ---------------------------------------------------------------------------
# CONTROL BLOCK 3 -- TIER DISCIPLINE AND THE CAUSAL BOUNDARY
# ---------------------------------------------------------------------------


def test_the_tier_must_be_declared_before_selection():
    with pytest.raises(gs.TierNotDeclared, match="DECLARED BEFORE SELECTION"):
        _problem_from_patterns({"111111": 1}, tier=gs.TIER_C).__class__(
            concept_id="x", tier=gs.TIER_C, cell_order=CELLS,
            admissible_by_cell={c: frozenset() for c in CELLS}, pattern_to_features={},
            features_admissible_in_no_cell=0, features_scored=0, data_provenance="SURROGATE",
            tiers_declared_in_advance=(gs.TIER_S,),
        )


def test_tier_j_is_refused_at_construction_because_its_certificate_would_be_vacuous():
    with pytest.raises(gs.TierNotSelectableHere, match="zero information"):
        _problem_from_patterns({"111000": 1}, tier=gs.TIER_J)


def test_tier_j_may_never_carry_the_concepts_name():
    good = gs.select_groups(_problem_from_patterns({"111111": 1}))
    forged = gs.GroupSelectionResult(
        **{**{k: getattr(good, k) for k in good.__dataclass_fields__},
           "tier": gs.TIER_J, "groups": ()}
    )
    with pytest.raises(gs.ConceptAttributionRefused, match="direction set that changes the text"):
        gs.claim_sentence(forged)
    assert "UNATTRIBUTED" in gs.claim_sentence(forged, attribute_to_concept=False)


def test_tier_s_restricts_membership_to_survivors_and_may_be_empty():
    """min-across-cells AS A QUALIFIER is permitted; it does no ranking
    here. TIER_S over a jointly-only matrix is EMPTY, and that is a
    reportable null rather than a licence to widen silently -- widening
    requires TIER_C to have been declared in advance, which
    `tiers_declared_in_advance` enforces."""
    patterns = {"111000": 3, "000111": 2}
    tier_s = gs.select_groups(_problem_from_patterns(patterns, tier=gs.TIER_S))
    assert tier_s.pool_size == 0
    assert tier_s.status == gs.STATUS_NO_ADMISSIBLE
    tier_c = gs.select_groups(_problem_from_patterns(patterns, tier=gs.TIER_C))
    assert tier_c.status == gs.STATUS_COMPLETE
    assert tier_c.survivor_count == 0
    assert tier_c.search.minimum_arity == 2


def test_causal_spend_is_refused_without_a_written_per_member_disposition():
    result = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1}))
    with pytest.raises(gs.EntityDiscriminatorDispositionMissing, match="nation-name detector"):
        gs.assert_ready_for_causal_spend(result)
    with pytest.raises(gs.EntityDiscriminatorDispositionMissing, match="PER MEMBER"):
        gs.assert_ready_for_causal_spend(result, {0: "proceed with the flag", 1: "   "})
    passed = gs.assert_ready_for_causal_spend(
        result, {0: "proceed with the flag", 1: "three-substrate read: stance band"}
    )
    assert sorted(passed["dispositions"]) == [0, 1]
    # And even then, what remains untested is named rather than implied.
    assert any("alpha" in item for item in passed["still_unexercised"])


def test_no_group_spec_and_no_dose_is_ever_produced_here():
    """The selector must not size an intervention: the dose, margin and
    ceiling come from a control-only calibration by a lane that does not
    select the group. A `GroupSpec` built here would be that boundary
    crossed."""
    source = (REPO_ROOT / "scripts" / "final_pairing" / "group_selection.py").read_bytes()
    assert b"GroupSpec(" not in source
    assert b"alpha=" not in source


# ---------------------------------------------------------------------------
# EXACTNESS, MINIMALITY, AND THE WHOLE SOLUTION SET
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seed", "density"),
    # MEASURED, NOT ASSUMED, and the reason both densities are here: at 0.30
    # all twelve seeds reach the COMPLETE branch (arities 2/3/4, up to 35
    # equally minimal classes) and NONE reaches the UNREACHABLE branch, so
    # the sparse block below is what exercises the partial-cover arm. A
    # parametrisation that only hit one arm would be a check unable to
    # exercise what it claims to cover.
    [(seed, 0.30) for seed in range(12)] + [(1000 + seed, 0.06) for seed in range(8)],
)
def test_the_exact_minimum_and_the_whole_solution_set_agree_with_brute_force(seed, density):
    """'MINIMUM' IS A CLAIM, NOT A LABEL. A greedy result called minimal
    would be a false claim, and minimality under removal is load-bearing, so
    the selector's answer is checked against exhaustive enumeration over
    every subset of the pool up to |C| members -- both the minimum arity and
    the complete set of minimum covers, set for set."""
    rng = np.random.default_rng(seed)
    matrix = rng.random((14, 6)) < density
    problem = gs.build_problem_from_matrix(
        matrix, cell_keys=CELLS, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED,
        concept_id=f"random_{seed}", data_provenance="SURROGATE random boolean matrix",
    )
    if problem.pool_size == 0:
        assert gs.select_groups(problem).status == gs.STATUS_NO_ADMISSIBLE
        return
    result = gs.select_groups(problem)
    target = problem.reachable_mask
    brute_k, brute_solutions = _brute_force_minimum_covers(problem, target)
    assert result.search.minimum_arity == brute_k
    assert result.search.exact is True

    covers, _nodes = gs.enumerate_minimum_pattern_covers(
        problem, arity=result.search.minimum_arity, target_mask=target
    )
    mine = {
        frozenset(features)
        for cover in covers
        for features in gs.expand_pattern_cover(problem, cover)
    }
    assert mine == brute_solutions
    assert result.feature_level_solution_count == len(brute_solutions)
    assert result.pattern_solution_count == len(covers)
    # Whether 1^6 was reachable is a property of the matrix, and the status
    # must agree with it either way.
    if target == problem.universe_mask:
        assert result.status == gs.STATUS_COMPLETE
        assert all(g.complete for g in result.groups)
    else:
        assert result.status == gs.STATUS_UNREACHABLE
        assert result.unreachable_cells
        assert not any(g.complete for g in result.groups)


def test_minimality_under_removal_is_measured_for_every_emitted_group():
    result = gs.select_groups(_problem_from_patterns({"110000": 2, "001100": 2, "000011": 2}))
    assert result.search.minimum_arity == 3
    for group in result.groups:
        record = group.minimality
        assert record["minimal_under_removal"] is True
        assert len(record["removals"]) == group.arity
        for removal in record["removals"]:
            assert removal["removal_strictly_reduces_coverage"] is True
            assert removal["still_complete_without_it"] is False
            assert removal["cells_lost"]


def test_a_redundant_member_is_caught_by_the_removal_test():
    """The check has to be able to FAIL. A superset of a minimum cover is
    still complete but is NOT minimal, and the removal test must say so
    rather than inheriting minimality from the search that produced it."""
    problem = _problem_from_patterns({"111000": 1, "000111": 1, "111111": 1})
    redundant = (0, 1, 2)
    assert gs.is_complete(problem, redundant) is True
    record = gs.verify_minimality_under_removal(problem, redundant)
    assert record["minimal_under_removal"] is False
    dropped = [r for r in record["removals"] if not r["removal_strictly_reduces_coverage"]]
    assert dropped and all(r["cells_lost"] == [] for r in dropped)


def test_the_jointly_only_case_is_exactly_what_a_group_is_for():
    """RULING_13 Q1 clause 6: individual CAUSAL sufficiency must NOT be
    required, and individual survivorship is not required either. This
    matrix has ZERO survivors and a complete cover at arity 2 -- the shape
    engineer 1 demonstrated (`survivors == 0` while `cov({0,1}) == 1^6`)."""
    problem = _problem_from_patterns({"111000": 3, "000111": 2, "110000": 5})
    assert problem.survivors == ()
    result = gs.select_groups(problem)
    assert result.survivor_count == 0
    assert result.status == gs.STATUS_COMPLETE
    assert result.search.minimum_arity == 2
    assert any("jointly-only" in note for note in result.notes)


def test_an_arity_one_cover_is_reported_as_a_single_feature():
    result = gs.select_groups(_problem_from_patterns({"111111": 2, "110000": 3}))
    assert result.search.minimum_arity == 1
    assert result.groups[0].arity == 1
    assert result.groups[0].to_record()["single_feature_not_a_group_of_one"] is True
    assert "SINGLE FEATURE" in gs.claim_sentence(result)


def test_every_equally_minimal_group_is_emitted_and_the_multiplicity_is_exact():
    """If many groups achieve cov = 1^6, emitting one is a collapse. The
    pattern-level classes are all emitted, and each carries the EXACT number
    of feature-level realisations it stands for."""
    problem = _problem_from_patterns({"111000": 4, "000111": 5, "101010": 6, "010101": 7})
    result = gs.select_groups(problem)
    assert result.search.minimum_arity == 2
    assert result.pattern_solution_count == 2
    assert result.emitted_group_count == 2
    assert result.feature_level_solution_count == 4 * 5 + 6 * 7
    assert result.dropped_from_emission == {}
    for group in result.groups:
        expanded = gs.expand_pattern_cover(
            problem, [int(p[::-1], 2) for p in group.equivalence_class_patterns]
        )
        assert group.realisation_multiplicity == len(expanded)
        assert group.feature_indices in expanded


def test_a_bounded_emission_names_exactly_what_it_dropped():
    """A silent top-N reads as 'these are all of them'."""
    problem = _problem_from_patterns({"111000": 4, "000111": 5, "101010": 6, "010101": 7})
    bounded = gs.select_groups(problem, max_emitted_groups=1)
    assert bounded.emitted_group_count == 1
    assert bounded.pattern_solution_count == 2
    assert bounded.dropped_from_emission["pattern_level_classes_dropped"] == 1
    assert bounded.dropped_from_emission["dropped_class_patterns"] == [["101010", "010101"]]
    assert bounded.feature_level_solution_count == 4 * 5 + 6 * 7


def test_members_available_per_slot_reports_what_the_listing_omitted():
    problem = _problem_from_patterns({"111000": 30, "000111": 2}, d_sae=64)
    result = gs.select_groups(problem, members_listed_per_slot=5)
    slot = next(
        s for s in result.groups[0].members_available_per_slot
        if s["coverage_pattern_left_to_right"] == "111000"
    )
    assert slot["members_available"] == 30
    assert len(slot["members_listed"]) == 5
    assert slot["members_omitted_from_this_listing"] == 25


# ---------------------------------------------------------------------------
# NULLS: UNREACHABLE CELLS, ARITY CEILINGS, AND BUDGETS
# ---------------------------------------------------------------------------


def test_an_unreachable_cell_is_named_and_the_null_is_not_arity_limited():
    """RULING_13 Q2 clause 4 (`NULL_COVER`): report the best partial cover
    and NAME the cells no admissible feature covers. Coverage is monotone in
    arity and the union of all patterns is the ceiling, so this null is a
    statement about the encoding, not about where the search stopped."""
    problem = _problem_from_patterns({"111000": 2, "000110": 3})
    result = gs.select_groups(problem)
    assert result.status == gs.STATUS_UNREACHABLE
    assert result.unreachable_cells == ("fr/f3",)
    assert result.best_achievable_coverage == (1, 1, 1, 1, 1, 0)
    assert gs.coverage_size(result.best_achievable_coverage) == 5
    record = result.to_record()
    assert record["null_is_arity_limited"] is False
    assert record["best_achievable_coverage_size"] == 5
    claim = gs.claim_sentence(result)
    assert "UNREACHABLE" in claim
    assert "may NOT be read as covering the cells it misses" in claim


def test_an_unreachable_cell_is_undisambiguated_when_no_ceilings_are_supplied():
    result = gs.select_groups(_problem_from_patterns({"111000": 2, "000110": 3}))
    verdicts = {
        cell: why["verdict"] for cell, why in result.unreachable_cell_disambiguation.items()
    }
    assert verdicts == {"fr/f3": "UNDISAMBIGUATED_NO_PER_CELL_CEILINGS_SUPPLIED"}


def test_a_below_bar_ceiling_makes_an_unreachable_cell_a_property_of_the_encoding():
    ceilings = {
        "separation_auroc": {"cells": {
            cell: {"max_separation_auroc": 0.99 if cell != "fr/f3" else 0.41} for cell in CELLS
        }},
        "fire_rate": {"cells": {cell: {"max_fire_rate": 0.95} for cell in CELLS}},
        "near_miss_auroc": {"cells": {cell: {"max_near_miss_auroc": 0.90} for cell in CELLS}},
    }
    result = gs.select_groups(
        _problem_from_patterns({"111000": 2, "000110": 3}, per_cell_ceilings=ceilings)
    )
    why = result.unreachable_cell_disambiguation["fr/f3"]
    assert why["verdict"] == "ENCODING_PROPERTY_FOR_THE_FAILING_LIMB"
    assert why["limbs"]["separation_auroc"]["ceiling"] == 0.41
    assert why["limbs"]["separation_auroc"]["frozen_bar"] == 0.90
    assert why["limbs"]["separation_auroc"]["ceiling_clears_bar"] is False


def test_a_conjunction_failure_is_named_as_its_own_finding():
    """A third case the ruling's one-limb dichotomy does not cover: every
    limb's ceiling clears its own bar in the cell, and still no single
    feature clears all three AT ONCE. Named rather than assimilated into
    either of the two."""
    ceilings = {
        "separation_auroc": {"cells": {cell: {"max_separation_auroc": 0.99} for cell in CELLS}},
        "fire_rate": {"cells": {cell: {"max_fire_rate": 0.95} for cell in CELLS}},
        "near_miss_auroc": {"cells": {cell: {"max_near_miss_auroc": 0.90} for cell in CELLS}},
    }
    result = gs.select_groups(
        _problem_from_patterns({"111000": 2, "000110": 3}, per_cell_ceilings=ceilings)
    )
    assert result.unreachable_cell_disambiguation["fr/f3"]["verdict"] == (
        "CONJUNCTION_FAILURE_NOT_A_SINGLE_LIMB_CEILING"
    )


def test_k_max_defaults_to_the_derived_structural_bound_and_is_not_invented():
    """RULING_13 REFUSES setting `K_max` as a number while requiring one be
    pre-registered. It is DERIVED here: every irredundant cover of |C| cells
    has at most |C| members, so searching to |C| exhausts the space rather
    than bounding a search inside it."""
    problem = _problem_from_patterns({"100000": 1, "010000": 1, "001000": 1,
                                      "000100": 1, "000010": 1, "000001": 1})
    result = gs.select_groups(problem)
    assert result.search.k_max == 6 == problem.n_cells
    assert "DERIVED" in result.search.k_max_basis
    assert result.search.minimum_arity == 6
    assert result.search.maximum_arity_examined == 6
    assert result.to_record()["null_is_arity_limited"] is False
    assert result.groups[0].feature_indices == (0, 1, 2, 3, 4, 5)
    assert result.groups[0].minimality["minimal_under_removal"] is True


def test_a_smaller_k_max_is_a_cost_bound_and_its_null_says_it_is_ceiling_limited():
    problem = _problem_from_patterns({"111000": 1, "000111": 1})
    result = gs.select_groups(problem, k_max=1)
    assert result.status == gs.STATUS_ARITY_CEILING
    assert result.groups == ()
    assert result.search.minimum_arity is None
    assert result.search.maximum_arity_examined == 1
    assert result.to_record()["null_is_arity_limited"] is True
    assert "CALLER-SUPPLIED COST BOUND" in result.search.k_max_basis
    assert "ceiling-limited" in " ".join(result.notes)


def test_the_search_budget_refuses_rather_than_degrading_to_greedy():
    problem = _problem_from_patterns({"111000": 2, "000111": 2, "101010": 2, "010101": 2})
    with pytest.raises(gs.SearchBudgetExceeded, match="REFUSING to substitute a greedy"):
        gs.enumerate_minimum_pattern_covers(problem, arity=2, node_budget=1)


def test_the_closure_saturation_is_recorded_when_nothing_more_is_reachable():
    """Coverage is monotone in arity, so once the reachable set of
    covered-masks stops growing no larger arity can help. That is what makes
    an unreachable cell a finding rather than a stopping point."""
    problem = _problem_from_patterns({"100000": 1})
    search = gs.exact_minimum_cover(problem)
    assert search.minimum_arity is None
    # One feature covering one cell: arity 1 adds its mask, arity 2 adds
    # nothing, so growth stops at 2 and the null is not arity-limited.
    assert search.closure_stopped_growing_at_arity == 2
    ceiling_limited = gs.exact_minimum_cover(
        _problem_from_patterns({"111000": 1, "000111": 1}), k_max=1
    )
    assert ceiling_limited.minimum_arity is None
    assert ceiling_limited.closure_stopped_growing_at_arity is None


# ---------------------------------------------------------------------------
# THE SEAM WITH THE PRODUCTION EMITTER
# ---------------------------------------------------------------------------


def test_the_matrix_path_and_the_record_path_agree_exactly():
    """`A` reaches a consumer two ways -- the in-memory boolean array and the
    lossless JSON record. They must describe the same matrix, or a group
    computed from `grid.json` differs from one computed in the run."""
    rng = np.random.default_rng(7)
    d_sae = 24
    per_cell = {
        quantity: {cell: rng.random(d_sae) for cell in CELLS}
        for quantity in ("separation_auroc", "fire_rate", "near_miss_auroc")
    }
    matrix, record = d.build_admissibility_matrix(
        per_cell, cell_keys=CELLS, auroc_min=0.5, fire_rate_min=0.5, near_miss_auroc_min=0.5,
        d_sae=d_sae,
    )
    from_matrix = gs.build_problem_from_matrix(
        matrix, cell_keys=CELLS, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED,
        concept_id="seam", data_provenance="SURROGATE",
    )
    from_record = gs.build_problem_from_record(
        record, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="seam",
        data_provenance="SURROGATE",
    )
    assert from_matrix.admissible_by_cell == from_record.admissible_by_cell
    assert from_matrix.pattern_to_features == from_record.pattern_to_features
    assert from_matrix.pool == from_record.pool
    left = gs.select_groups(from_matrix).to_record()
    right = gs.select_groups(from_record).to_record()
    for key in ("status", "minimum_arity_MEASURED", "pattern_level_solution_count",
                "feature_level_solution_count_EXACT", "groups"):
        assert left[key] == right[key]


def test_selection_runs_end_to_end_on_a_real_scan_from_the_discovery_runner():
    """A genuine `FullSpaceScan` from the production scan path, on the fake
    backend this suite uses everywhere (no real weights exist anywhere in
    this investigation). SURROGATE DATA THROUGH REAL CODE: the point is the
    seam, not the numbers."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    assert scan.admissibility_matrix is not None
    assert scan.cell_keys and len(scan.cell_keys) == 6
    problem = gs.build_problem_from_matrix(
        scan.admissibility_matrix, cell_keys=scan.cell_keys, tier=gs.TIER_C,
        tiers_declared_in_advance=DECLARED, concept_id="cheese",
        data_provenance="SURROGATE: fake backend through the real scan",
    )
    result = gs.select_groups(problem)
    assert result.status in (gs.STATUS_COMPLETE, gs.STATUS_UNREACHABLE, gs.STATUS_NO_ADMISSIBLE)
    assert result.cell_order == tuple(scan.cell_keys)
    assert "SURROGATE" in result.data_provenance
    gs.assert_not_vacuous(result)
    if result.groups:
        assert all(g.minimality["minimal_under_removal"] for g in result.groups)


def test_a_written_grid_json_round_trips_into_coverage_problems(tmp_path):
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    assert verdict.admissibility_matrix is not None
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    problems = gs.load_problems_from_grid(
        path, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_ids=["cheese"]
    )
    assert set(problems) == {"cheese"}
    problem = problems["cheese"]
    assert problem.data_provenance.startswith("real:")
    assert problem.cell_order == tuple(verdict.admissibility_matrix["cell_order"])
    result = gs.select_groups(problem)
    gs.assert_not_vacuous(result)
    # A concept the grid does not carry is an error, never an empty result.
    with pytest.raises(gs.GroupSelectionError, match="no verdict for concepts"):
        gs.load_problems_from_grid(
            path, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_ids=["poutine"]
        )


# ---------------------------------------------------------------------------
# REPORTING FORM
# ---------------------------------------------------------------------------


def test_the_headline_is_the_vector_and_the_scalar_never_replaces_it():
    result = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1}))
    record = result.to_record()
    group = record["groups"][0]
    assert group["coverage_vector"] == [1, 1, 1, 1, 1, 1]
    assert group["coverage_size_reported_alongside_the_vector_never_instead"] == 6
    assert "coverage_vector" in group and "arity_MEASURED_not_pre_registered" in group
    assert record["best_achievable_coverage_vector"] == [1, 1, 1, 1, 1, 1]
    claim = gs.claim_sentence(result)
    assert "[1, 1, 1, 1, 1, 1]" in claim


def test_every_record_carries_the_pool_bound_and_the_no_causal_evidence_caveats():
    result = gs.select_groups(_problem_from_patterns({"111111": 1}))
    caveats = result.to_record()["caveats"]
    assert "NOT a claim that these are the features needed" in caveats["pool_bound"]
    assert "recall caveat is permanent" in caveats["pool_bound"]
    assert "no intervened generation" in caveats["no_causal_evidence"]
    assert "nation-name detector" in caveats["entity_discriminator"]
    # The prohibited sentence appears ONLY inside its own prohibition.
    claim = gs.claim_sentence(result)
    assert "these are the features needed" in claim
    assert "NOT a claim that these are the features needed" in claim
    assert claim.count("these are the features needed") == 1


def test_the_minimum_is_stated_as_a_lower_bound_because_a_is_a_screen_derived_superset():
    """`A` is screened at `threshold - screen_epsilon`, so it is a SUPERSET
    of the exactly-computed admissible set. Set inclusion runs one way
    through minimum cover -- a superset can only make a cover easier -- so
    the reported minimum arity is a LOWER BOUND on the minimum over the
    exact `A`, and the band that bounds the slack travels with it."""
    problem = _problem_from_patterns({"111000": 1, "000111": 1})
    record = gs.select_groups(problem).to_record()["minimum_is_with_respect_to_A_AS_RECORDED"]
    assert "LOWER BOUND" in record["why"]
    assert record["screen_epsilon"] == pytest.approx(1e-9)
    assert record["features_within_screen_epsilon_band"] is not None
    # The matrix path carries no band, and says UNKNOWN rather than nothing.
    from_matrix = gs.build_problem_from_matrix(
        np.ones((4, 6), dtype=bool), cell_keys=CELLS, tier=gs.TIER_C,
        tiers_declared_in_advance=DECLARED, concept_id="x", data_provenance="SURROGATE",
    )
    assert "UNKNOWN" in from_matrix.screen_provenance["screen_derived"]


def test_the_record_is_json_serialisable_and_deterministic():
    problem = _problem_from_patterns({"111000": 4, "000111": 5, "101010": 6, "010101": 7})
    first = json.dumps(gs.select_groups(problem).to_record(), sort_keys=True)
    second = json.dumps(gs.select_groups(problem).to_record(), sort_keys=True)
    assert first == second
    assert gs.CANONICAL_REALISATION_RULE in first


def test_the_canonical_realisation_is_the_lowest_index_and_carries_no_preference():
    problem = _problem_from_patterns({"111000": 3, "000111": 2})
    result = gs.select_groups(problem)
    # features 0,1,2 hold 111000 and 3,4 hold 000111 -> canonical is (0, 3)
    assert result.groups[0].feature_indices == (0, 3)
    assert result.groups[0].realisation_multiplicity == 6
    assert "not a preference among equally minimal groups" in gs.CANONICAL_REALISATION_RULE


def test_the_selfcheck_passes_and_labels_everything_surrogate(capsys):
    assert gs._selfcheck() == 0
    out = capsys.readouterr().out
    assert "CONTROL 1 -- VACUITY" in out
    assert out.index("CONTROL 1") < out.index("SURROGATE RESULT A")
    assert "SURROGATE (not a measurement)" in out or "SURROGATE" in out
    assert "UNEXERCISED HERE" in out


def test_the_cli_requires_the_tier_to_be_declared_and_has_no_default(tmp_path, capsys):
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    with pytest.raises(SystemExit):
        gs.main(["--grid", str(path)])
    assert "--tier is required" in capsys.readouterr().err
    out_path = tmp_path / "selection.json"
    assert gs.main([
        "--grid", str(path), "--tier", gs.TIER_C, "--declare-tier", gs.TIER_S,
        "--declare-tier", gs.TIER_C, "--json-out", str(out_path),
    ]) == 0
    records = json.loads(out_path.read_text(encoding="utf-8"))
    assert records and records[0]["tier"] == gs.TIER_C
    assert records[0]["k_max_basis"]
