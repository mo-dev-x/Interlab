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


def _forge_tier_j_result(good):
    """A TIER_J result built by DELIBERATELY BYPASSING the schema.

    The schema layer now refuses TIER_J at construction, so the second-line
    guard in `claim_sentence` is no longer reachable through the constructor.
    Bypassing it here is the only way to keep that guard exercised instead of
    letting it rot into dead code behind the newer refusal -- and the bypass is
    labelled rather than quiet."""
    forged = object.__new__(gs.GroupSelectionResult)
    for name in good.__dataclass_fields__:
        object.__setattr__(forged, name, getattr(good, name))
    object.__setattr__(forged, "tier", gs.TIER_J)
    object.__setattr__(forged, "groups", ())
    return forged


def test_tier_j_may_never_carry_the_concepts_name():
    good = gs.select_groups(_problem_from_patterns({"111111": 1}))
    forged = _forge_tier_j_result(good)
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
                "feature_level_solution_count_EXACT"):
        assert left[key] == right[key]
    # The GROUPS agree on everything the matrix determines...
    for a, b in zip(left["groups"], right["groups"], strict=True):
        for key in ("feature_indices", "coverage_vector", "arity_MEASURED_not_pre_registered",
                    "complete", "equivalence_class_patterns", "per_cell_depth_vector_d_G",
                    "feature_level_realisations_of_this_class", "minimality_under_removal"):
            assert a[key] == b[key]
    # ...and DELIBERATELY DISAGREE on what only the record can carry. A bare
    # boolean matrix cannot say whether a bit of it was decided at the bar, so
    # the matrix path reports UNKNOWN and the record path DECIDES. Asserting
    # these equal would be asserting that a stated absence is a measurement.
    assert left["groups"][0]["screen_band_membership_of_THIS_group"]["decidable"] is False
    assert right["groups"][0]["screen_band_membership_of_THIS_group"]["decidable"] is True


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


def test_the_screen_provenance_travels_and_the_withdrawn_exact_a_clause_is_not_implemented():
    """The architect WITHDREW its own clause that a plain float
    `values >= threshold` be emitted as "exact A" and HEADLINED over the
    screened form (sequence 43, correcting sequence 42). The measured reason:
    `screen_epsilon` is 1e-9 while one G-A lattice step is 1/600 = 1.7e-3, so
    the band cannot hold an ATTAINABLE value -- only a feature whose true
    rational EQUALS the bar and whose float64 fell a few ulps short. The
    screened form is therefore the FAITHFUL one and the plain float `>=` is the
    form carrying the artifact.

    So this test asserts the ABSENCE of the withdrawn machinery as well as the
    presence of the surviving provenance. A withdrawal that leaves its
    implementation behind is not a withdrawal."""
    problem = _problem_from_patterns({"111000": 1, "000111": 1})
    record = gs.select_groups(problem).to_record()["minimum_is_with_respect_to_A_AS_RECORDED"]
    assert record["screen_epsilon"] == pytest.approx(1e-9)
    assert record["features_within_screen_epsilon_band"] is not None
    assert "FAITHFUL" in record["why"]
    assert "WITHDREW" in record["withdrawn_clause"]
    # The withdrawn key is ABSENT from the scan record, not merely unread.
    _m, scan_record = d.build_admissibility_matrix(
        {q: {c: np.full(4, 0.99) for c in CELLS}
         for q in ("separation_auroc", "fire_rate", "near_miss_auroc")},
        cell_keys=CELLS, auroc_min=0.9, fire_rate_min=0.7, near_miss_auroc_min=0.75, d_sae=4,
    )
    assert "admissible_feature_indices_by_cell_EXACT" not in scan_record
    assert scan_record["gate_comparison_basis"] == "SCREENED_FLOAT"
    assert "NOT EXERCISED" in scan_record["gate_comparison_basis_why"]
    # The matrix path carries no band, and says UNKNOWN rather than nothing.
    from_matrix = gs.build_problem_from_matrix(
        np.ones((4, 6), dtype=bool), cell_keys=CELLS, tier=gs.TIER_C,
        tiers_declared_in_advance=DECLARED, concept_id="x", data_provenance="SURROGATE",
    )
    assert "UNKNOWN" in from_matrix.screen_provenance["screen_derived"]
    assert from_matrix.screen_band_indices_by_cell is None


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
    assert "not a preference among equally-minimum-cardinality groups" in (
        gs.CANONICAL_REALISATION_RULE
    )
    assert "BIT-IDENTICAL in A" in gs.CANONICAL_REALISATION_RULE


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


# ---------------------------------------------------------------------------
# RULING_14 AND ITS ADDENDUM -- CONTROLS AND FALSIFIERS
#
# Every clause below carries a falsifier that is DEMONSTRATED ABLE TO FAIL,
# because the architect's own standard for this ruling was that it would add no
# clause that cannot fail. Where a check could pass while being unable to
# exercise what it claims, the mis-implementation is written out and asserted
# to fail.
# ---------------------------------------------------------------------------


FOUR_CELLS = ("c0", "c1", "c2", "c3")

#: THE MUTATION. Feature 0's pattern gains ONE bit, in cell c1. Arity,
#: completeness, the class set and every canonical representative are
#: unchanged; the only thing that moves is one class's per-cell depth.
_MUTATION_BEFORE = {"0001": 1, "1001": 1, "0100": 1, "0110": 1, "1110": 1}
_MUTATION_AFTER = {"0101": 1, "1001": 1, "0100": 1, "0110": 1, "1110": 1}

SOURCE_PATH = REPO_ROOT / "scripts" / "final_pairing" / "group_selection.py"
DISCOVERY_PATH = REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_concept_discovery.py"


def _four_cell_problem(patterns, order=gs.SPEND_ORDER_ARBITRARY):
    return gs.surrogate_problem(
        patterns=patterns, d_sae=8, cell_keys=FOUR_CELLS, tier=gs.TIER_C,
        tiers_declared_in_advance=DECLARED, concept_id="mutation",
        label="pytest add-one-bit falsifier", spend_order=order,
    )


def _emitted_order(patterns, order):
    result = gs.select_groups(_four_cell_problem(patterns, order))
    return [g.feature_indices for g in result.groups], result


# --- the band: an index list, so a GROUP's membership is decidable ----------


def test_the_band_is_an_index_list_so_a_specific_groups_membership_is_decidable():
    """THE DEFECT INSIDE THE HONESTY CORRECTION. The scan recorded
    `features_within_screen_epsilon_band` as an int COUNT per cell and per
    gate. A count bounds the POPULATION the screen slack could have admitted
    and cannot say whether any member of a GIVEN group sits in the band, so the
    caveat this file attached to every record travelled while being unable to
    be exercised on the object it qualified.

    Three states have to be distinguishable and all three are asserted:
    DECIDED-POSITIVE, DECIDED-NEGATIVE, and UNKNOWN. Collapsing the last two is
    the same defect in a different place."""
    banded = gs.surrogate_problem(
        patterns={"111000": 1, "000111": 1}, d_sae=8, tier=gs.TIER_C,
        tiers_declared_in_advance=DECLARED, concept_id="banded",
        label="pytest: feature 0 sits AT the G-A bar in en/f1", band_bits=((0, 0),),
    )
    group = gs.select_groups(banded).groups[0]
    assert group.epsilon_band["decidable"] is True
    assert group.epsilon_band["group_is_float_representation_contingent"] is True
    assert group.epsilon_band["contingent_bits"] == [
        {"feature_index": 0, "cell": "en/f1", "gate": "G-A"}
    ]
    # The count alone could not have told us this: it is 1 for that cell and
    # gate whether or not the banded feature is a member of the emitted group.
    assert banded.screen_provenance["features_within_screen_epsilon_band"]["en/f1"]["G-A"] == 1

    # DECIDED NEGATIVE, which is a different finding from UNKNOWN.
    clean = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1})).groups[0]
    assert clean.epsilon_band["decidable"] is True
    assert clean.epsilon_band["group_is_float_representation_contingent"] is False
    assert clean.epsilon_band["contingent_bits"] == []

    # UNKNOWN, and it must not read as a decided negative.
    unknown = gs.select_groups(
        gs.build_problem_from_matrix(
            np.ones((4, 6), dtype=bool), cell_keys=CELLS, tier=gs.TIER_C,
            tiers_declared_in_advance=DECLARED, concept_id="x", data_provenance="SURROGATE",
        )
    ).groups[0]
    assert unknown.epsilon_band["decidable"] is False
    assert unknown.epsilon_band["group_is_float_representation_contingent"] is None
    assert "UNKNOWN" in unknown.epsilon_band["why_not"]


def test_the_band_decision_is_per_group_and_not_merely_per_cell():
    """THE FALSIFIER FOR THE CLAUSE ABOVE, and it is precisely what a count
    cannot do. Two groups drawn from the SAME matrix, one containing the banded
    feature and one not: a per-cell count is identical for both, and the
    per-group decision differs. If both groups reported the same contingency the
    record would be back to bounding a population."""
    problem = gs.surrogate_problem(
        # Two disjoint classes; feature 0 is banded in c0 and is a member of
        # exactly one of them.
        patterns={"111000": 1, "000111": 1, "101010": 1, "010101": 1},
        d_sae=8, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="split",
        label="pytest: one banded feature, two classes", band_bits=((0, 0),),
    )
    result = gs.select_groups(problem)
    flags = {
        g.feature_indices: g.epsilon_band["group_is_float_representation_contingent"]
        for g in result.groups
    }
    assert True in flags.values() and False in flags.values(), flags
    # And the group flagged contingent is exactly the one containing feature 0.
    for members, flag in flags.items():
        assert flag is (0 in members)


# --- the lattice comparison, which superseded the withdrawn clause ---------


def test_the_lattice_denominator_is_derived_from_the_counts_and_never_stored():
    """`600` is nowhere in the code. It is `2 * n_pos * n_neg`, derived from
    `rank_auroc_matrix`'s own arithmetic: average ranks are multiples of 1/2, so
    the AUROC numerator is a multiple of 1/2 over `n_pos * n_neg`.

    A stored 600 would pass every v2-count test and silently mis-scale the
    moment a cell had different counts -- the same defect shape as a stored
    `k_max` of 6."""
    assert d.rank_auroc_lattice_denominator(10, 30) == 600
    assert d.rank_auroc_lattice_denominator(10, 15) == 300
    assert d.fire_rate_lattice_denominator(10) == 10
    # Different counts, different lattice. This is the falsifier for "derived".
    assert d.rank_auroc_lattice_denominator(12, 30) == 720
    assert d.rank_auroc_lattice_denominator(10, 45) == 900
    assert d.fire_rate_lattice_denominator(7) == 7
    source = DISCOVERY_PATH.read_text(encoding="utf-8")
    assert "denominator = 600" not in source
    assert "lattice_denominators = {" not in source
    for bad in (0, -1):
        with pytest.raises(d.LatticeDenominatorWrong, match="no lattice"):
            d.rank_auroc_lattice_denominator(bad, 30)
        with pytest.raises(d.LatticeDenominatorWrong, match="no lattice"):
            d.fire_rate_lattice_denominator(bad)


def test_the_lattice_gate_has_no_epsilon_and_admits_the_value_the_float_form_drops():
    """The whole ground for the withdrawal, made exercisable. A feature whose
    true rational EQUALS the bar but whose float64 evaluation fell one ulp short
    is DROPPED by the plain float comparison and ADMITTED by the lattice one.
    That is the artifact the withdrawn clause would have headlined as 'exact'."""
    at_the_bar = 540 / 600
    mis_rounded = np.nextafter(at_the_bar, 0.0)
    # The float form carries the artifact...
    assert bool(mis_rounded >= 0.90) is False
    # ...and the integer comparison does not.
    passed, integer_bar, residual = d.lattice_gate(
        np.array([mis_rounded, 539 / 600, 541 / 600]), threshold=0.90, denominator=600
    )
    assert integer_bar == 540
    assert passed.tolist() == [True, False, True]
    assert residual < 1e-9
    # The integer bar is ROUNDED when the bar is a lattice point and CEIL'd only
    # when it genuinely falls between two, because `bar * D` is itself a float
    # and a naive ceil would move the gate by a whole lattice step.
    _p, bar_half, _r = d.lattice_gate(np.array([0.5]), threshold=0.5, denominator=600)
    assert bar_half == 300
    # A bar strictly between lattice points rounds UP, never down.
    _p2, bar_between, _r2 = d.lattice_gate(
        np.array([0.5]), threshold=1.0 / 3.0, denominator=10
    )
    assert bar_between == 4


def test_a_wrong_lattice_denominator_refuses_instead_of_falling_back():
    """The comparison's merit is having NO free parameter, so a denominator that
    does not divide the statistic would put one back. It refuses rather than
    quietly reverting to the float comparison."""
    with pytest.raises(d.LatticeDenominatorWrong, match="NOT on a 1/7 lattice"):
        d.lattice_gate(np.array([548 / 600]), threshold=0.90, denominator=7)
    with pytest.raises(d.LatticeDenominatorWrong, match="must be positive"):
        d.lattice_gate(np.array([0.5]), threshold=0.5, denominator=0)
    # And the refusal reaches the matrix builder, not only the primitive.
    with pytest.raises(d.LatticeDenominatorWrong):
        d.build_admissibility_matrix(
            {q: {c: np.full(4, 548 / 600) for c in CELLS}
             for q in ("separation_auroc", "fire_rate", "near_miss_auroc")},
            cell_keys=CELLS, auroc_min=0.9, fire_rate_min=0.7, near_miss_auroc_min=0.75,
            d_sae=4, lattice_denominators={"separation_auroc": {c: 7 for c in CELLS}},
        )


def test_the_lattice_and_screened_comparisons_agree_and_the_agreement_is_measured():
    """Under real lattice values the two gates give the same support, which is
    the addendum's point: at 1e-9 against a 1/600 step the screen is FAITHFUL,
    not loose. The record REPORTS the disagreement count so the agreement is
    measured rather than argued, and reports the band as zero rather than
    dropping it -- a permanently-zero diagnostic that is still measured is the
    right end state for it."""
    rng = np.random.default_rng(11)
    d_sae = 64
    # Genuine 1/600, 1/300 and 1/10 rationals.
    sep = {c: rng.integers(0, 601, d_sae) / 600.0 for c in CELLS}
    near = {c: rng.integers(0, 301, d_sae) / 300.0 for c in CELLS}
    fire = {c: rng.integers(0, 11, d_sae) / 10.0 for c in CELLS}
    denominators = {
        "separation_auroc": {c: 600 for c in CELLS},
        "near_miss_auroc": {c: 300 for c in CELLS},
        "fire_rate": {c: 10 for c in CELLS},
    }
    _matrix, record = d.build_admissibility_matrix(
        {"separation_auroc": sep, "fire_rate": fire, "near_miss_auroc": near},
        cell_keys=CELLS, auroc_min=0.90, fire_rate_min=0.70, near_miss_auroc_min=0.75,
        d_sae=d_sae, lattice_denominators=denominators,
    )
    assert record["gate_comparison_basis"] == "LATTICE_INTEGER"
    assert record["lattice_integer_bar_by_cell_and_gate"][CELLS[0]]["G-A"] == 540
    assert record["lattice_integer_bar_by_cell_and_gate"][CELLS[0]]["G-B"] == 7
    assert record["lattice_integer_bar_by_cell_and_gate"][CELLS[0]]["G-C"] == 225
    assert set(record["gate_disagreement_count_by_cell"].values()) == {0}
    for cell in CELLS:
        for gate in ("G-A", "G-B", "G-C"):
            assert record["features_within_screen_epsilon_band"][cell][gate] == 0
            assert record["features_within_screen_epsilon_band_indices"][cell][gate] == []


def test_the_scan_supplies_derived_denominators_so_the_gate_is_the_lattice_one():
    """End to end through the production scan: the denominators are derived
    inside the cell loop from the real array shapes, so the emitted record's
    gate is the integer comparison rather than the float screen."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    assert scan.admissibility["gate_comparison_basis"] == "LATTICE_INTEGER"
    lattice = scan.admissibility["lattice_denominator_by_cell_and_gate"]
    for cell in scan.cell_keys:
        # G-B's denominator IS the positive count, which is what makes the
        # resampling-reach comparison computable without adding a field.
        assert lattice[cell]["G-B"] > 0
        # G-A pools both negative sets, so its denominator strictly exceeds
        # G-C's, which sees the near-miss set only.
        assert lattice[cell]["G-A"] > lattice[cell]["G-C"]
        assert lattice[cell]["G-A"] == 2 * lattice[cell]["G-B"] * (
            lattice[cell]["G-A"] // (2 * lattice[cell]["G-B"])
        )
    assert set(scan.admissibility["gate_disagreement_count_by_cell"].values()) == {0}


# --- the schema-layer TIER_J refusal, and the ungated set as a control ------


def test_an_ungated_set_cannot_be_expressed_as_a_group_at_all():
    """RULING_14 REFERRAL D clause 2. Refusing at the POOL layer is necessary
    and INSUFFICIENT: emitted through the group-record shape, an ungated set's
    `coverage_vector` reads `1^|C|`, `complete` reads true and
    `minimality_under_removal` reads true, and NO READER COULD DISTINGUISH A
    TAUTOLOGICAL CERTIFICATE FROM AN EARNED ONE. So the refusal moves to the
    schema: an ungated set cannot be EXPRESSED as a group."""
    certificate = dict(
        concept_id="cheese", feature_indices=(7,), arity=1, coverage=(1,) * 6, coverage_size=6,
        complete=True, pattern_by_member=((7, "111111"),), equivalence_class_patterns=("111111",),
        realisation_multiplicity=1, members_available_per_slot=(),
        minimality={"minimal_under_removal": True},
    )
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="INDISTINGUISHABLE"):
        gs.GroupCandidate(tier=gs.TIER_J, **certificate)
    for ungated_pool in gs.UNGATED_POOL_SOURCES:
        with pytest.raises(gs.UngatedSetCannotWearACertificate, match="cannot fail"):
            gs.GroupCandidate(tier=gs.TIER_C, pool_source=ungated_pool, **certificate)
    # And the OUTER shape too: it carries a certificate as much as the inner one.
    good = gs.select_groups(_problem_from_patterns({"111111": 1}))
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="any shape that carries one"):
        gs.GroupSelectionResult(
            **{**{k: getattr(good, k) for k in good.__dataclass_fields__}, "tier": gs.TIER_J}
        )
    # The pool layer still refuses too. Both layers, because the ruling holds
    # the pool layer NECESSARY as well as insufficient.
    with pytest.raises(gs.TierNotSelectableHere, match="zero information"):
        _problem_from_patterns({"111000": 1}, tier=gs.TIER_J)


def test_no_record_constructing_path_accepts_a_pool_that_is_not_derived_from_a():
    """The falsifier the architect attached verbatim: "assert over the file that
    no code path constructs a group record from a pool not derived from A."
    Asserted over the source AND over the behaviour, because either alone can
    pass while the other fails."""
    source = SOURCE_PATH.read_text(encoding="utf-8")
    # Scoped to the PRODUCTION half of the file. `_selfcheck` deliberately
    # constructs ungated pools in order to be REFUSED, and an assertion that
    # could not tell a refusal control from a production path would be the
    # defect class in the check itself.
    production, _sep, selfcheck = source.partition("def _selfcheck()")
    assert selfcheck, "the selfcheck boundary moved; this assertion's scope is no longer meaningful"
    for bad in gs.UNGATED_POOL_SOURCES:
        assert f'pool_source="{bad}"' not in production, bad
        assert f"pool_source='{bad}'" not in production, bad
        # ...and the selfcheck's occurrences are all inside a `refuses(...)` control.
        assert f'pool_source="{bad}"' not in selfcheck or "refuses(" in selfcheck
    # The field default is the ONLY thing that supplies a pool source.
    assert "pool_source: str = POOL_SOURCE_A" in production
    for patterns in ({"111111": 1}, {"111000": 2, "000111": 3}, {"101010": 1, "010101": 1}):
        groups = gs.select_groups(_problem_from_patterns(patterns)).groups
        assert groups
        for group in groups:
            assert group.pool_source == gs.POOL_SOURCE_A
            assert group.to_record()["pool_source"] == gs.POOL_SOURCE_A


def test_the_ungated_control_set_is_admissible_under_all_five_conditions():
    """RULING_14 REFERRAL D clause 3, and clause 5's warning that confirming the
    refusal must not become a reason to skip the control. An ungated set is
    admissible and ENCOURAGED -- as a labelled negative control, under five
    conditions, implemented rather than approximated."""
    control = gs.UngatedControlSet(
        label=gs.UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(11, 12), arity=2,
        pool_construction="pytest: two indices drawn uniformly, without reference to A",
        n_features_available=64,
    )
    record = control.to_record()
    # (a) the source is NAMED and is not A
    assert record["pool_source_NOT_A"] == "random"
    assert record["pool_source_NOT_A"] != gs.POOL_SOURCE_A
    assert record["pool_construction"]
    # (b) the label, never TIER_J-as-a-result
    assert record["label"] == "control_ungated_set"
    assert record["is_a_group"] is False
    # TIER_J appears in this record ONLY inside its own prohibition, never as a
    # value. A blanket "TIER_J is absent" assertion would forbid the record from
    # explaining why it is not a tier.
    assert "TIER_J" not in {record["label"], record["pool_source_NOT_A"]}
    assert "NEVER TIER_J-as-a-result" in record["conditions_all_five"][1]
    # (c) no coverage certificate and no concept name -- and the keys STATE
    # their own absence rather than being silently missing
    assert "ABSENT BY CONSTRUCTION" in record["coverage_vector"]
    assert "ABSENT BY CONSTRUCTION" in record["concept_id"]
    for certificate_key in ("complete", "minimality_under_removal", "coverage_size", "tier"):
        assert certificate_key not in record
    # (d) the permitted sentence, verbatim
    assert "a direction set that changes the text" in record["concept_id"]
    assert "NEVER 'the cheese features'" in record["conditions_all_five"][3]
    # (e) never merged
    assert len(record["conditions_all_five"]) == 5
    good = gs.select_groups(_problem_from_patterns({"111111": 1}))
    separation = gs.assert_not_merged_with_gated(control, [good])
    assert separation["merged"] is False
    assert separation["gated_tiers_reported_separately"] == [gs.TIER_C]
    # ...and the separation check must be unable to pass vacuously.
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="cannot exercise"):
        gs.assert_not_merged_with_gated(control, [])


def test_the_ungated_control_refuses_every_way_of_dressing_it_as_a_result():
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="MEANT TO FAIL"):
        gs.UngatedControlSet(
            label="TIER_J", pool_source="random", feature_indices=(1,), arity=1,
            pool_construction="pytest",
        )
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="must NOT be A"):
        gs.UngatedControlSet(
            label=gs.UNGATED_CONTROL_LABEL, pool_source=gs.POOL_SOURCE_A, feature_indices=(1,),
            arity=1, pool_construction="pytest",
        )
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="stated absence"):
        gs.UngatedControlSet(
            label=gs.UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(1,), arity=1,
            pool_construction="   ",
        )
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="vacuity defect"):
        gs.UngatedControlSet(
            label=gs.UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(), arity=0,
            pool_construction="pytest",
        )
    with pytest.raises(gs.UngatedSetCannotWearACertificate, match="MATCHED ARITY"):
        gs.UngatedControlSet(
            label=gs.UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(1, 2), arity=5,
            pool_construction="pytest",
        )


def test_there_is_no_widening_path_into_tier_j_but_the_control_arm_is_not_refused():
    """BOTH DIRECTIONS, or the check cannot tell them apart -- which is exactly
    what the architect required of this falsifier. RULING_14 REFERRAL D clause 4
    closes a hole in RULING_13: declaring TIER_J in advance as a FALLBACK
    DESTINATION must raise, and declaring it as a labelled CONTROL ARM must
    not."""
    # DIRECTION 1: TIER_J as a widening destination from a gated tier. RAISES.
    with pytest.raises(gs.TierWideningIntoTierJRefused, match="EVIDENCE TO NO EVIDENCE"):
        gs.surrogate_problem(
            patterns={"111000": 1, "000111": 1}, d_sae=8, tier=gs.TIER_C,
            tiers_declared_in_advance=(gs.TIER_C, gs.TIER_J), concept_id="fallback",
            label="pytest TIER_J-as-fallback",
        )
    with pytest.raises(gs.TierWideningIntoTierJRefused):
        gs.CoverageProblem(
            concept_id="x", tier=gs.TIER_C, cell_order=CELLS,
            admissible_by_cell={c: frozenset({1}) for c in CELLS},
            pattern_to_features={63: (1,)}, features_admissible_in_no_cell=0, features_scored=8,
            data_provenance="SURROGATE",
            tiers_declared_in_advance=(gs.TIER_S, gs.TIER_C, gs.TIER_J),
        )
    # DIRECTION 2: the same ungated arm, declared as a labelled control. DOES NOT RAISE.
    control = gs.UngatedControlSet(
        label=gs.UNGATED_CONTROL_LABEL, pool_source="hand_picked", feature_indices=(3, 4), arity=2,
        pool_construction="pytest: declared in advance as a CONTROL ARM, not as a fallback",
    )
    assert control.to_record()["label"] == gs.UNGATED_CONTROL_LABEL
    # And an empty gated tier is a reportable NULL rather than a licence to widen.
    empty = gs.select_groups(_problem_from_patterns({"111000": 3, "000111": 2}, tier=gs.TIER_S))
    assert empty.status == gs.STATUS_NO_ADMISSIBLE
    assert gs.TIER_J not in empty.tiers_declared_in_advance
    # The permitted widening, TIER_S -> TIER_C, still works: both are gates.
    widened = gs.select_groups(_problem_from_patterns({"111000": 3, "000111": 2}, tier=gs.TIER_C))
    assert widened.status == gs.STATUS_COMPLETE


def test_a_missing_ungated_arm_says_not_exercised_rather_than_nothing():
    """Clause 5's hazard, closed. Confirming the TIER_J refusal must not become
    a reason to omit the control silently: absent, the record says NOT
    EXERCISED, never blank."""
    result = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1}))
    assert "NOT EXERCISED" in result.ungated_control_arm
    assert "NOT EXERCISED" in result.to_record()["ungated_control_arm"]
    handed = gs.assert_ready_for_causal_spend(
        result, {0: "proceed with the flag", 1: "three-substrate read: stance band"}
    )
    assert "NOT EXERCISED" in handed["ungated_control_arm"]
    assert "REQUIRED-IF-CLAIMED" in gs.UngatedControlSet(
        label=gs.UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(1, 2), arity=2,
        pool_construction="pytest",
    ).to_record()["what_this_arm_answers"]


# --- the spend order, and the add-one-bit falsifier ------------------------


def test_the_depth_vector_is_recorded_whether_or_not_the_depth_order_is_elected():
    """RULING_14 REFERRAL A clause 7: record now, decide never-in-this-ruling.
    Whether depth predicts causal robustness is what the first causal grid could
    answer and cannot answer retroactively, and the addendum's Q2 adds that
    depth is the quantity deciding REFERRAL C -- depth 1 everywhere means every
    cover is a partition and there is no wider irredundant arm at all."""
    for order in (gs.SPEND_ORDER_ARBITRARY, gs.SPEND_ORDER_DEPTH):
        result = gs.select_groups(_four_cell_problem(_MUTATION_BEFORE, order))
        assert result.spend_order == order
        assert result.spend_order_justification["depth_vectors_recorded_anyway"] is True
        for group in result.groups:
            assert len(group.depth) == 4
            # PER CELL, never collapsed, and the SIGN is the coverage vector.
            assert tuple(1 if v else 0 for v in group.depth) == group.coverage
            record = group.to_record()
            assert record["per_cell_depth_vector_d_G"] == list(group.depth)
            assert "NOT a headline" in record["per_cell_depth_vector_binds"]
            # No depth SCALAR is emitted anywhere in the group record.
            assert "min_depth" not in json.dumps(record)


def test_adding_one_admissibility_bit_moves_the_depth_order_and_never_the_arbitrary_one():
    """THE FALSIFIER RULING_14 REFERRAL A CLAUSE 8 NAMES EXPLICITLY, and the
    reason it exists: an ordering that claims nothing may read nothing, and an
    ordering offered as a REASON TO PREFER one group must read the per-cell
    matrix AND BE DEMONSTRATED TO READ IT.

    The mutation adds ONE bit to one member of an emitted class, leaving arity,
    completeness and the set of canonical representatives unchanged. BOTH
    directions are asserted, or the test only proves one."""
    arb_before, before = _emitted_order(_MUTATION_BEFORE, gs.SPEND_ORDER_ARBITRARY)
    arb_after, after = _emitted_order(_MUTATION_AFTER, gs.SPEND_ORDER_ARBITRARY)
    dep_before, depth_before = _emitted_order(_MUTATION_BEFORE, gs.SPEND_ORDER_DEPTH)
    dep_after, _ = _emitted_order(_MUTATION_AFTER, gs.SPEND_ORDER_DEPTH)

    # The mutation really did preserve what it was required to preserve.
    assert before.search.minimum_arity == after.search.minimum_arity == 2
    assert all(g.complete for g in before.groups)
    assert all(g.complete for g in after.groups)
    assert sorted(arb_before) == sorted(arb_after)
    # ...and it really did add exactly ONE bit.
    assert sum(sum(g.depth) for g in after.groups) == sum(sum(g.depth) for g in before.groups) + 1

    # THE TWO ASSERTIONS. A depth-elected order MUST change...
    assert dep_before != dep_after, (dep_before, dep_after)
    # ...and a declared-arbitrary order MUST NOT.
    assert arb_before == arb_after, (arb_before, arb_after)
    # And the two orders must be distinguishable at all, or neither assertion
    # means anything.
    assert dep_before != arb_before
    assert before.spend_order_justification["reads_the_per_cell_matrix"] is False
    assert depth_before.spend_order_justification["reads_the_per_cell_matrix"] is True


def test_the_add_one_bit_falsifier_is_able_to_fail():
    """DEMONSTRATED ABLE TO FAIL, on the architect's own standard for this
    ruling. Two mis-implementations are written out and each is shown to break
    the test above:

    1. A "depth" order that secretly sorts by feature index reads nothing, so
       the mutation does not move it -- and the MUST-CHANGE assertion fires.
    2. An "arbitrary" order that secretly sorts by depth reads the matrix, so
       the mutation moves it -- and the MUST-NOT-CHANGE assertion fires.

    A falsifier that cannot be made to fail is the defect class this whole
    ruling is about."""
    def order_with(patterns, key):
        result = gs.select_groups(_four_cell_problem(patterns))
        return [g.feature_indices for g in sorted(result.groups, key=key)]

    def arbitrary_key(group):
        return group.feature_indices

    def depth_key(group):
        return (tuple(-v for v in sorted(group.depth)), group.feature_indices)

    # 1. A DEPTH ORDER THAT READS NOTHING. The MUST-CHANGE assertion fires.
    sham_depth_before = order_with(_MUTATION_BEFORE, arbitrary_key)
    sham_depth_after = order_with(_MUTATION_AFTER, arbitrary_key)
    assert sham_depth_before == sham_depth_after, "the sham depth order did not read the matrix"
    with pytest.raises(AssertionError):
        assert sham_depth_before != sham_depth_after, "MUST-CHANGE fires as designed"

    # 2. AN ARBITRARY ORDER THAT READS DEPTH. The MUST-NOT-CHANGE assertion fires.
    sham_arbitrary_before = order_with(_MUTATION_BEFORE, depth_key)
    sham_arbitrary_after = order_with(_MUTATION_AFTER, depth_key)
    assert sham_arbitrary_before != sham_arbitrary_after
    with pytest.raises(AssertionError):
        assert sham_arbitrary_before == sham_arbitrary_after, "MUST-NOT-CHANGE fires as designed"


def test_the_depth_order_prefers_the_class_whose_thinnest_cell_is_thickest():
    """The criterion, stated and then checked: the depth vector sorted
    ASCENDING, compared lexicographically DESCENDING."""
    _order, result = _emitted_order(_MUTATION_BEFORE, gs.SPEND_ORDER_DEPTH)
    keys = [tuple(sorted(g.depth)) for g in result.groups]
    assert keys == sorted(keys, reverse=True)
    assert "THINNEST cell is thickest" in result.spend_order_justification["criterion"]
    assert result.spend_order_justification["no_bar_is_set_on_depth"] is True
    assert "ARGUED and UNMEASURED" in result.spend_order_justification["claims"]
    assert "CONJUNCTIVE OVER CELLS" in result.spend_order_justification[
        "not_min_as_a_ranker_because"
    ]


def test_an_unknown_spend_order_is_refused_rather_than_silently_defaulted():
    with pytest.raises(gs.GroupSelectionError, match="spend_order must be one of"):
        _four_cell_problem(_MUTATION_BEFORE, "by_vibes")


def test_within_a_slot_the_candidates_are_bit_identical_in_a_asserted_not_assumed():
    """RULING_14 REFERRAL A clause 9 and the addendum's Q3 both rest a REFUSAL on
    this property, so it is MEASURED rather than taken from the definition of
    the slot. A refusal resting on an unchecked property is the defect class in
    the argument instead of in the code."""
    problem = _problem_from_patterns({"111000": 4, "000111": 3})
    for pattern, members in problem.pattern_to_features.items():
        problem.assert_slot_carries_no_within_slot_preference(pattern)
        # The property itself: identical bits, cell by cell.
        assert len({problem.pattern_of(f) for f in members}) == 1
    # ABLE TO FAIL: a hand-built problem whose slot mixes two patterns.
    broken = gs.CoverageProblem(
        concept_id="x", tier=gs.TIER_C, cell_order=CELLS,
        admissible_by_cell={
            c: (frozenset({0, 1}) if i < 3 else frozenset({1})) for i, c in enumerate(CELLS)
        },
        # 0 and 1 do NOT share a pattern, and this slot claims they do.
        pattern_to_features={0b000111: (0, 1)},
        features_admissible_in_no_cell=0, features_scored=8, data_provenance="SURROGATE",
        tiers_declared_in_advance=DECLARED,
    )
    with pytest.raises(gs.GroupSelectionError, match="BIT-IDENTICAL"):
        broken.assert_slot_carries_no_within_slot_preference(0b000111)


# --- k_max is a function of |C| --------------------------------------------


@pytest.mark.parametrize("n_cells", [2, 3, 4, 6, 9])
def test_the_ceiling_is_a_function_of_the_cell_count_and_not_a_stored_six(n_cells):
    """RULING_14 REFERRAL B clause 4, and its falsifier verbatim: "run the
    selector on a 4-cell and a 9-cell universe and assert the recorded ceiling is
    4 and 9. A literal would pass every 6-cell test ever written, which is
    precisely this sprint's defect class." Three locales times three families is
    nine cells, and a hard 6 would then report ceiling-limited nulls as
    unconditional ones."""
    cells = tuple(f"c{i}" for i in range(n_cells))
    result = gs.select_groups(
        gs.surrogate_problem(
            patterns={"1" * n_cells: 1}, d_sae=8, cell_keys=cells, tier=gs.TIER_C,
            tiers_declared_in_advance=DECLARED, concept_id=f"c{n_cells}",
            label=f"pytest {n_cells}-cell universe",
        )
    )
    assert result.n_cells == n_cells
    assert result.search.k_max == n_cells
    assert result.to_record()["k_max"] == n_cells
    assert "DERIVED" in result.search.k_max_basis
    # And the ceiling really is computed rather than stored.
    assert "ceiling = problem.n_cells if k_max is None else int(k_max)" in SOURCE_PATH.read_text(
        encoding="utf-8"
    )


def test_the_null_under_the_derived_ceiling_is_unconditional_over_arity():
    """RULING_14 REFERRAL B clause 3 PROVED MORE than this file had claimed and
    said the stronger statement should be the recorded one: every cover CONTAINS
    an irredundant subcover, so no cover at arity <= |C| means NO COVER AT ANY
    ARITY."""
    unreachable = gs.select_groups(_problem_from_patterns({"111000": 2, "000110": 3}))
    record = unreachable.to_record()
    assert record["unreachable_cells"] == ["fr/f3"]
    assert "irredundant subcover" in record["null_is_unconditional_over_arity_proof"]
    assert "NO COVER AT ANY ARITY" in record["null_is_unconditional_over_arity_proof"]
    # Under a CALLER-SUPPLIED smaller ceiling the null is ceiling-limited and
    # therefore NOT unconditional. The two must not be conflated.
    ceiling_limited = gs.select_groups(
        _problem_from_patterns({"111000": 1, "000111": 1}), k_max=1
    ).to_record()
    assert ceiling_limited["null_is_arity_limited"] is True
    assert ceiling_limited["null_is_unconditional_over_arity"] is False
    assert "CALLER-SUPPLIED" in ceiling_limited["k_max_basis"]
    # A caller-supplied bound may NOT inherit the derived basis string.
    assert "DERIVED" not in ceiling_limited["k_max_basis"]


# --- the second recall bound, computed rather than argued ------------------


def test_the_cost_of_the_minimum_cardinality_restriction_is_computed_or_unknown():
    """RULING_14 REFERRAL C clause 5. The architect declined to REQUIRE the
    larger enumeration -- making the first real run hostage to an unbudgeted
    search would be motivated by nothing measured -- and required instead a
    COMPUTED statement of what the restriction costs, with UNKNOWN rather than
    blank when the budget refuses."""
    patterns = {"111100": 2, "001111": 3, "111000": 1, "000111": 1}
    census = gs.select_groups(
        _problem_from_patterns(patterns)
    ).to_record()["cost_of_the_minimum_cardinality_restriction"]
    assert census["minimum_arity"] == 2
    assert census["maximum_irredundant_arity_possible"] == 6
    assert census["distinct_patterns_present"] == 4
    assert isinstance(census["pattern_level_irredundant_covers_above_the_minimum_total"], int)
    assert "SUBSET" in census["what_this_measures"]
    assert "PRE-DECLARED" in census["widening_is_pre_declared_not_post_hoc"]
    # UNKNOWN rather than blank when the budget refuses, and the refusal says
    # why. The census has its OWN bound: starving it must not starve the cover
    # enumeration, which still RAISES rather than degrading.
    starved_result = gs.select_groups(_problem_from_patterns(patterns), census_node_budget=3)
    starved = starved_result.to_record()["cost_of_the_minimum_cardinality_restriction"]
    assert starved["pattern_level_irredundant_covers_above_the_minimum"] == "UNKNOWN"
    assert starved["pattern_level_irredundant_covers_above_the_minimum_total"] == "UNKNOWN"
    assert "REFUSES rather than degrading" in starved["why_unknown"]
    assert "NOT APPLICABLE" in starved["why_unknown"]
    # The COVER result is untouched by the census starving: an UNKNOWN cost is
    # not allowed to become an unknown minimum.
    assert starved_result.search.minimum_arity == 2
    assert starved_result.pattern_solution_count > 0
    # And the cover search's own budget still RAISES rather than degrading.
    with pytest.raises(gs.SearchBudgetExceeded, match="REFUSING to substitute a greedy"):
        gs.select_groups(_problem_from_patterns(patterns), node_budget=3)


def test_the_disjoint_case_collapses_the_minimum_versus_irredundant_distinction():
    """The addendum's Q2, which REVERSES the sharpening that was put to it: if
    the per-cell clearing sets are PAIRWISE DISJOINT then every cover is a
    partition, minimum arity equals the number of cells, depth is 1 everywhere,
    and the maximum irredundant arity EQUALS the minimum. Total disjointness
    COLLAPSES the distinction rather than widening it, so a zero here is a
    finding about the overlap structure and not an absence."""
    disjoint = gs.select_groups(
        _problem_from_patterns({p: 2 for p in (
            "100000", "010000", "001000", "000100", "000010", "000001"
        )})
    )
    assert disjoint.search.minimum_arity == 6 == disjoint.n_cells
    assert all(tuple(g.depth) == (1,) * 6 for g in disjoint.groups)
    census = disjoint.to_record()["cost_of_the_minimum_cardinality_restriction"]
    assert census["pattern_level_irredundant_covers_above_the_minimum_total"] == 0


def test_the_second_recall_bound_is_named_and_the_widening_is_pre_declared():
    result = gs.select_groups(_problem_from_patterns({"111000": 1, "000111": 1}))
    record = result.to_record()
    assert "SECOND RECALL BOUND" in record["second_recall_bound"]
    assert "NOT over all irredundant covers" in record["second_recall_bound"]
    assert "PRE-DECLARED" in record["second_recall_bound"]
    assert "NEVER MERGED" in record["second_recall_bound"]
    assert record["caveats"]["second_recall_bound"] == gs.SECOND_RECALL_BOUND
    assert gs.SECOND_RECALL_BOUND in gs.claim_sentence(result)


def test_the_word_minimal_no_longer_names_the_enumerated_object():
    """RULING_14 REFERRAL C clause 3, the instrument-structure rule applied to
    LANGUAGE. Unqualified, "minimal" asserts the removal property AND implies the
    enumeration ranged over every cover holding it; the second half is false of
    what is emitted. `minimality_under_removal` is PERMITTED -- it names the
    verified per-group property -- and the two may not be substituted."""
    source = SOURCE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (
        "minimal cover", "minimal covers", "minimal group", "minimal groups",
        "minimal candidate", "minimal pattern class", "equally minimal",
    ):
        assert forbidden not in source, forbidden
    # The permitted phrases are still there, naming the property they measure.
    assert "minimality_under_removal" in source
    assert "minimum-cardinality" in source
    # And the emitted record does not carry the forbidden phrase either.
    blob = json.dumps(
        gs.select_groups(_problem_from_patterns({"111000": 2, "000111": 3})).to_record()
    ).lower()
    for forbidden in ("minimal cover", "minimal group", "equally minimal"):
        assert forbidden not in blob, forbidden
    assert "minimal_under_removal" in blob
    # ...nor does any claim sentence this file produces.
    for patterns in ({"111111": 1}, {"111000": 2, "000111": 3}, {"111000": 2, "000110": 3}):
        claim = gs.claim_sentence(gs.select_groups(_problem_from_patterns(patterns))).lower()
        for forbidden in ("minimal cover", "minimal group", "equally minimal"):
            assert forbidden not in claim, (forbidden, claim[:120])


# --- the two permitted claim forms, and nothing stronger -------------------


def test_the_claim_sentence_carries_the_arity_the_vector_and_the_exact_population():
    """RULING_14 REFERRAL A clause 10: a sentence naming a realisation while its
    multiplicity sits in a JSON field is a caveat a reader of the CLAIM cannot
    exercise. Precedent: the G-A-pass denominator, whose absence exposed a
    vacuity in RULING_13, and this applies the same shape to a second
    quantity."""
    result = gs.select_groups(_problem_from_patterns({"111000": 3, "000111": 2}))
    claim = gs.claim_sentence(result)
    assert "arity 2" in claim
    assert "[1, 1, 1, 1, 1, 1]" in claim
    assert "EXACTLY 6 feature-level realisation" in claim
    assert "minimum-cardinality" in claim
    assert "no single realisation may be reported as 'the' cover" in claim
    # The UNREACHABLE arm carries the population too, not only the complete arm.
    partial = gs.claim_sentence(gs.select_groups(_problem_from_patterns({"111000": 2, "000110": 3})))
    assert "feature-level realisation" in partial


def test_a_concept_level_null_is_refused_and_the_check_is_not_decorative():
    """The falsifier verbatim: "a fabricated record reporting a concept-level
    null while realisations_examined < realisations_in_population must FAIL the
    check. If it passes, the check is decorative."
    """
    with pytest.raises(gs.UniversalNullUnreachable, match="ONE REALISATION"):
        gs.assert_null_is_not_universal(
            {"scope": "CONCEPT", "realisations_examined": 3,
             "realisations_in_population": 11424000}
        )
    with pytest.raises(gs.UniversalNullUnreachable, match="ONE REALISATION"):
        gs.assert_null_is_not_universal(
            {"scope": "CLASS", "realisations_examined": 1, "realisations_in_population": 6}
        )
    # AND THE CLAUSE THAT IS EASY TO MISS: there is NO n at which it becomes
    # universal, so even an exhausted population is refused.
    with pytest.raises(gs.UniversalNullUnreachable, match="NO n at which"):
        gs.assert_null_is_not_universal(
            {"scope": "CONCEPT", "realisations_examined": 6, "realisations_in_population": 6}
        )
    # The permitted scope passes...
    assert gs.assert_null_is_not_universal(
        {"scope": "REALISATION", "realisations_examined": 1, "realisations_in_population": 6}
    )["scope"] == "REALISATION"
    # ...and an unstated scope or a missing denominator cannot pass vacuously.
    with pytest.raises(gs.UniversalNullUnreachable, match="not one of"):
        gs.assert_null_is_not_universal(
            {"scope": "whatever", "realisations_examined": 1, "realisations_in_population": 6}
        )
    for missing in ("scope", "realisations_examined", "realisations_in_population"):
        claim = {"scope": "CONCEPT", "realisations_examined": 1, "realisations_in_population": 6}
        claim.pop(missing)
        with pytest.raises(gs.UniversalNullUnreachable, match="has no"):
            gs.assert_null_is_not_universal(claim)


def test_the_bounded_negative_sentence_carries_both_n_and_capital_n():
    result = gs.select_groups(_problem_from_patterns({"111000": 3, "000111": 2}))
    sentence = gs.bounded_negative_sentence(result, realisations_examined=2)
    assert "2 of 6" in sentence
    assert "UNREACHABLE BY CONSTRUCTION" in sentence
    assert "4 realisation(s) remain untested" in sentence
    assert "minimum-cardinality covers ONLY" in sentence
    # n cannot exceed N, and a success is not a bounded negative.
    with pytest.raises(gs.UniversalNullUnreachable, match=r"not in 0\.\.6"):
        gs.bounded_negative_sentence(result, realisations_examined=7)
    with pytest.raises(gs.UniversalNullUnreachable, match="EXISTENTIAL"):
        gs.bounded_negative_sentence(result, realisations_examined=2, successes=1)


def test_the_record_states_which_population_the_denominator_counts():
    """RULING_14 REFERRAL C clause 7: if the wider irredundant arm is opened, N
    changes and every earlier denominator becomes a denominator over a proper
    subset. A denominator whose population is unstated is the vacuity defect in
    its original form."""
    record = gs.select_groups(_problem_from_patterns({"111000": 3, "000111": 2})).to_record()
    assert "MINIMUM-CARDINALITY covers ONLY" in record[
        "realisation_population_this_denominator_counts"
    ]
    assert record["groups"][0]["realisation_population_this_denominator_counts"] == (
        gs.REALISATION_POPULATION
    )
    assert len(record["permitted_claim_forms"]) == 2
    assert any("EXISTENTIAL" in f for f in record["permitted_claim_forms"])
    assert any("BOUNDED NEGATIVE" in f for f in record["permitted_claim_forms"])
    assert any("UNREACHABLE" in f for f in record["refused_claim_forms"])
    assert "FIRST SUCCESS" in record["stopping_rule_pre_registered"]
    assert "UNREACHABLE BY CONSTRUCTION" in record["caveats"]["a_class_is_not_a_testable_unit"]
    assert "ONE REALISATION" in record["groups"][0]["a_class_is_not_a_testable_unit"]


def test_no_depth_word_reaches_a_claim_sentence_and_the_bind_can_fail():
    for patterns in ({"111111": 1}, {"111000": 2, "000111": 3}, {"111000": 2, "000110": 3}):
        result = gs.select_groups(_problem_from_patterns(patterns))
        gs.assert_no_depth_claim(gs.claim_sentence(result))
        gs.assert_no_depth_claim(gs.bounded_negative_sentence(result, realisations_examined=0))
    # ABLE TO FAIL, in the obvious and in the paraphrased form.
    for sentence in (
        "the depth vector shows this cover is best",
        "this cover is more robust across cells",
        "the deeper of the two classes",
        "a stronger group for cheese",
    ):
        with pytest.raises(gs.GroupSelectionError, match="SPEND ORDER and not a claim"):
            gs.assert_no_depth_claim(sentence)


# --- the unreachable cell, now the live path rather than a spare branch -----


def test_an_unreachable_cell_names_which_cell_and_why_the_ceiling_is_below_the_bar():
    """NOT A HYPOTHETICAL BRANCH. On the first real data a concept's full-space
    G-A ceiling in one cell sits below the bar, and a ceiling is a MAXIMUM OVER
    THE WHOLE DICTIONARY, so `A[f, c] = 0` for every `f`, `cov(G)[c] = 0` for
    every `G`, and `cov = 1^|C|` is unreachable at every arity, under every tier,
    under every tie-break. `|cov|` is capped at `|C| - 1` for all time on this
    corpus."""
    problem = _problem_from_patterns(
        {"111100": 2, "000010": 3},
        per_cell_ceilings={
            "separation_auroc": {"cells": {
                c: {"max_separation_auroc": 0.99 if c != "fr/f3" else 0.89} for c in CELLS
            }},
            "fire_rate": {"cells": {c: {"max_fire_rate": 0.95} for c in CELLS}},
            "near_miss_auroc": {"cells": {c: {"max_near_miss_auroc": 0.90} for c in CELLS}},
        },
    )
    result = gs.select_groups(problem)
    assert result.status == gs.STATUS_UNREACHABLE
    # WHICH cell.
    assert list(result.unreachable_cells) == ["fr/f3"]
    # WHY -- the ceiling, the bar, and the comparison, not merely "completion failed".
    why = result.unreachable_cell_disambiguation["fr/f3"]
    assert why["verdict"] == gs.VERDICT_ENCODING_ONE_LIMB
    limb = why["limbs"]["separation_auroc"]
    assert limb["ceiling"] == pytest.approx(0.89)
    assert limb["frozen_bar"] == pytest.approx(0.90)
    assert limb["ceiling_clears_bar"] is False
    assert why["limbs"]["fire_rate"]["ceiling_clears_bar"] is True
    assert why["limbs"]["near_miss_auroc"]["ceiling_clears_bar"] is True
    # The ceiling holds at EVERY arity, and the claim sentence says so.
    assert result.best_achievable_coverage == (1, 1, 1, 1, 1, 0)
    assert gs.coverage_size(result.best_achievable_coverage) == 5
    claim = gs.claim_sentence(result)
    assert "UNREACHABLE" in claim and "fr/f3" in claim
    assert "may NOT be read as covering the cells it misses" in claim
    # And the minimum cover OF THE REACHABLE TARGET is still computed and
    # emitted as INCOMPLETE rather than withheld.
    assert result.search.minimum_arity == 2
    assert result.groups
    assert all(g.complete is False for g in result.groups)


def test_a_per_limb_maximum_is_never_read_as_a_conjunction():
    """The addendum's decisive point. Three per-limb maxima can all clear their
    bars with the argmaxes being three DIFFERENT features and no feature clearing
    all three at once, so they can REFUTE admissibility in a cell and can never
    ESTABLISH it. The record has to say so on every limb, and the architect now
    names CONJUNCTION_FAILURE the LEADING hypothesis where it arises."""
    problem = _problem_from_patterns(
        {"111110": 2},
        per_cell_ceilings={
            "separation_auroc": {"cells": {c: {"max_separation_auroc": 0.99} for c in CELLS}},
            "fire_rate": {"cells": {c: {"max_fire_rate": 0.95} for c in CELLS}},
            "near_miss_auroc": {"cells": {c: {"max_near_miss_auroc": 0.90} for c in CELLS}},
        },
    )
    why = gs.select_groups(problem).unreachable_cell_disambiguation["fr/f3"]
    assert why["verdict"] == gs.VERDICT_CONJUNCTION_FAILURE
    assert "LEADING hypothesis" in why["because"]
    assert "no information about a" in why["because"]
    for limb in why["limbs"].values():
        assert "can REFUTE admissibility" in limb["a_maximum_is_not_a_conjunction"]
        assert "never ESTABLISH it" in limb["a_maximum_is_not_a_conjunction"]


def test_a_sub_bar_ceiling_within_resampling_reach_gets_its_own_verdict():
    """THE FOURTH VERDICT STATE the addendum requires, on the measured numbers
    that produced it: a full-space ceiling of 534/600 against a 540/600 bar is
    SIX LATTICE STEPS, three pair-inversions, on a cell with ten positives. A
    maximum over 81,920 features does not reduce that uncertainty, because every
    feature is scored against the SAME positives and the sampling error is COMMON
    MODE.

    What the state FORBIDS is 'the encoding cannot represent this concept here'.
    What it PRESERVES is `cov(G)[c] = 0` ON THIS CORPUS, which is the only corpus
    there is."""
    record = {
        "cell_order": list(CELLS),
        "d_sae": 8,
        "admissible_feature_indices_by_cell": {
            c: ([0, 1] if c != "fr/f2" else []) for c in CELLS
        },
        "thresholds_used": {
            "G_A_separation_auroc_min": 0.90,
            "G_B_fire_rate_min": 0.70,
            "G_C_specificity_auroc_vs_near_miss_min": 0.75,
        },
        # The DERIVED denominators, in the shape the scan now emits them.
        "lattice_denominator_by_cell_and_gate": {
            c: {"G-A": 600, "G-B": 10, "G-C": 300} for c in CELLS
        },
    }
    problem = gs.build_problem_from_record(
        record, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="cheese_shaped",
        data_provenance="SURROGATE: shaped after the measured cheese ceilings",
        per_cell_ceilings={
            "separation_auroc": {"cells": {
                c: {"max_separation_auroc": (534 / 600 if c == "fr/f2" else 548 / 600)}
                for c in CELLS
            }},
            "fire_rate": {"cells": {c: {"max_fire_rate": 0.95} for c in CELLS}},
            "near_miss_auroc": {"cells": {c: {"max_near_miss_auroc": 0.90} for c in CELLS}},
        },
    )
    result = gs.select_groups(problem)
    assert list(result.unreachable_cells) == ["fr/f2"]
    why = result.unreachable_cell_disambiguation["fr/f2"]
    assert why["verdict"] == gs.VERDICT_CEILINGED_WITHIN_RESAMPLING_REACH
    limb = why["limbs"]["separation_auroc"]
    assert limb["deficit_in_lattice_steps"] == pytest.approx(6.0)
    assert limb["n_positives_behind_the_ceiling"] == 10
    assert limb["deficit_within_corpus_resampling_reach"] is True
    assert "COMMON MODE" in why["because"]
    assert "POINT verdict" in why["because"]
    assert "is NOT supported" in why["because"]
    # The OPERATIVE consequence is unchanged: no complete cover, at any arity.
    assert result.status == gs.STATUS_UNREACHABLE
    assert gs.coverage_size(result.best_achievable_coverage) == 5
    # And the softer verdict is NOT given to the cells that clear the bar.
    assert set(result.unreachable_cell_disambiguation) == {"fr/f2"}


def test_a_deficit_beyond_resampling_reach_is_not_given_the_softer_verdict():
    """The falsifier for the state above: it must be able NOT to be entered, or
    it is a verdict that cannot fail. A deficit of 300 lattice steps on ten
    positives is 150 pair-inversions and is not within resampling reach."""
    assert gs._resampling_reach(6.0, 10) is True
    assert gs._resampling_reach(20.0, 10) is True
    assert gs._resampling_reach(21.0, 10) is False
    assert gs._resampling_reach(300.0, 10) is False
    # UNKNOWN inputs give None, never a verdict.
    assert gs._resampling_reach(None, 10) is None
    assert gs._resampling_reach(6.0, None) is None
    assert gs._resampling_reach(6.0, 0) is None
    # And end to end: a ceiling far below the bar keeps the harder verdict.
    record = {
        "cell_order": list(CELLS),
        "d_sae": 8,
        "admissible_feature_indices_by_cell": {
            c: ([0, 1] if c != "fr/f2" else []) for c in CELLS
        },
        "thresholds_used": {
            "G_A_separation_auroc_min": 0.90,
            "G_B_fire_rate_min": 0.70,
            "G_C_specificity_auroc_vs_near_miss_min": 0.75,
        },
        "lattice_denominator_by_cell_and_gate": {
            c: {"G-A": 600, "G-B": 10, "G-C": 300} for c in CELLS
        },
    }
    far_below = gs.build_problem_from_record(
        record, tier=gs.TIER_C, tiers_declared_in_advance=DECLARED, concept_id="far_below",
        data_provenance="SURROGATE",
        per_cell_ceilings={
            "separation_auroc": {"cells": {
                c: {"max_separation_auroc": (0.40 if c == "fr/f2" else 548 / 600)} for c in CELLS
            }},
            "fire_rate": {"cells": {c: {"max_fire_rate": 0.95} for c in CELLS}},
            "near_miss_auroc": {"cells": {c: {"max_near_miss_auroc": 0.90} for c in CELLS}},
        },
    )
    why = gs.select_groups(far_below).unreachable_cell_disambiguation["fr/f2"]
    assert why["verdict"] == gs.VERDICT_ENCODING_ONE_LIMB
    assert why["limbs"]["separation_auroc"]["deficit_within_corpus_resampling_reach"] is False


def test_an_unreachable_cell_without_ceilings_says_undisambiguated():
    """The three states must stay distinguishable: a missing ceiling is not a
    sub-bar ceiling, and neither is a conjunction failure."""
    result = gs.select_groups(_problem_from_patterns({"111000": 2, "000110": 3}))
    why = result.unreachable_cell_disambiguation["fr/f3"]
    assert why["verdict"] == gs.VERDICT_UNDISAMBIGUATED
    assert "Stated rather than guessed" in why["because"]
    assert why["limbs"]["separation_auroc"]["deficit_in_lattice_steps"] is None
    # All five verdict states are distinct strings, or two findings could be
    # read as one.
    states = {
        gs.VERDICT_UNDISAMBIGUATED, gs.VERDICT_CONJUNCTION_FAILURE,
        gs.VERDICT_ENCODING_ONE_LIMB, gs.VERDICT_ENCODING_ALL_LIMBS,
        gs.VERDICT_CEILINGED_WITHIN_RESAMPLING_REACH,
    }
    assert len(states) == 5
