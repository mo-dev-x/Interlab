#!/usr/bin/env python3
"""GROUP SELECTION over the admissibility matrix `A[f, c]` (architect RULING_13 Q1).

WHAT THIS FILE IS FOR. Two halves of the group deliverable existed and the
link between them did not: `final_pairing_concept_discovery.py` retains and
emits `A[f, c]` (commit `c3941d1`), and `group_intervention.py` can amplify
or ablate a SET of features (commit `19aa2cc`). Nothing turned `A` into
candidate groups. This file is that step and NOTHING ELSE -- it is set
arithmetic over a boolean matrix. It loads no model, needs no GPU, scores no
generation, and cannot establish sufficiency: no intervened generation is
run or read anywhere in it.

THE DEFINITION IT IMPLEMENTS, verbatim in structure from RULING_13 Q1
clause 3: A GROUP IS A SET PLUS A COVERAGE CERTIFICATE. `A[f, c] = 1` iff
feature `f` passes the three frozen gates IN CELL `c`, over the six cells
`c = locale x paraphrase family`; `cov(G)[c] = 1` iff some member of `G` is
admissible in `c`; `G` is COMPLETE iff `cov(G) == 1^|C|`. THE HEADLINE IS
THE VECTOR. The only scalar permitted is `|cov(G)|`, and every record this
file emits carries the vector and the scalar together, never the scalar
alone.

WHAT IS NOT PRE-REGISTERED HERE, DELIBERATELY. No group size. Cardinality
is an OUTCOME (clause 2): `arity` is reported as measured, a cover of size 1
is reported AS A SINGLE FEATURE rather than dressed as a group of one, and
the concept counts 1/3/5 and 1/2/3 appear nowhere in this file because they
are SHARED-CONCEPT counts and were never group sizes. No margin, no
ceiling, no dose, no alpha: those come from a control-only calibration
performed by a lane that does not select the group, and this file therefore
cannot and does not build a `GroupSpec` -- see `assert_ready_for_causal_spend`
for the boundary it refuses to cross.

MEMBERSHIP (clause 6). Individual CORRELATIONAL admissibility is REQUIRED:
a member must pass the gates in AT LEAST ONE cell, which is the only
evidence tying it to this concept rather than to anything whatsoever.
Individual CAUSAL sufficiency is NOT required and is not consulted -- a
selector that required it would be structurally incapable of finding
jointly-only sets, which are the entire scientific content of a group
claim. The Qwen grid produced 3 survivors across 14 concepts; TIER-C exists
because uniformity moves from the MEMBER to the GROUP.

SELECTION IS EXACT (clause 8), AND THAT IS A CLAIM THIS FILE HAS TO EARN.
With |C| cells every feature collapses to one of `2^|C|` coverage patterns
(64 at |C| = 6), so minimum cover is a finite enumeration rather than an
approximation problem. `exact_minimum_cover` runs a breadth-first closure
over the `2^|C|` covered-masks and returns the TRUE minimum;
`enumerate_minimum_pattern_covers` then returns EVERY minimum-cardinality
cover, deduplicated, with the node count it took. Greedy is not implemented
here -- not as a fallback, not as a comparison -- because a greedy result
labelled "minimal" would be a false claim and minimality is load-bearing.
If the search budget were ever exceeded this file RAISES
`SearchBudgetExceeded` rather than degrading to an approximation.

WHY min-across-cells APPEARS NOWHERE IN THIS FILE. RULING_13 Q1 clause 4:
min is correct as a QUALIFIER and REFUSED as a RANKER, and a min-ranked pool
holds by construction the features least in need of a group. This selector
reads `A` only. It never reads `min_separation_auroc`, `min_fire_rate` or
`min_near_miss_auroc`, and it never consumes `select_candidates_from_scan`'s
output, which clause 5 prohibits as a candidate pool. When per-cell
retention is absent the answer is `PerCellRetentionMissing` -- the SAME
exception class the scan raises, imported from it by file identity so there
is exactly one refusal identity in the sprint and no silent fallback to the
collapsed data.

THE TWO CONTROLS THAT COME BEFORE ANY RESULT. Both are the same defect
class -- a check that passes while unable to exercise what it claims:

1. VACUITY. `all()` over an empty iterable is `True`, so "every group is
   complete" is trivially satisfiable by a concept with ZERO admissible
   features, and that is not a hypothetical: it already happened once in
   this sprint. So `is_complete` returns False for the empty set BY
   CONSTRUCTION, a universe with no cells REFUSES instead of reporting
   `1^0`, a concept with no admissible feature yields
   `NULL_COVER_NO_ADMISSIBLE_FEATURE` with zero groups, and
   `assert_not_vacuous` exists to catch a completeness claim that was
   computed over nothing.
2. SILENT FALLBACK. A loader that can reach for `min_*` when the per-cell
   support is missing will eventually do so and report groups that were
   never per-cell. Every entry point here refuses instead, and the refusal
   distinguishes "this record predates the field" from "this concept has no
   admissible feature", which are opposite findings.

Run `python scripts/final_pairing/group_selection.py --selfcheck` for the
refusals first and the passing cases after, on surrogate data that is
labelled surrogate in every line of output.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]


class GroupSelectionError(RuntimeError):
    """Base class for every refusal in this file."""


class SearchBudgetExceeded(GroupSelectionError):
    """The exact enumeration hit its node budget.

    RAISED, NEVER DEGRADED TO GREEDY. RULING_13 Q1 clause 8 refuses greedy
    for cover construction on the ground that the exact answer is available,
    so an approximation is not a trade-off but a worse answer. If this
    raises, the measured node count is the thing to report -- a silent
    downgrade would put the word "minimal" on a result that had not earned
    it."""


class VacuousCoverageClaim(GroupSelectionError):
    """A completeness claim was computed over an empty pool or no cells.

    THE DEFECT THIS SPRINT KEEPS PRODUCING. `all([])` is True, so "all
    groups complete" is true and worthless when there are no groups, and
    `1^0` is not a coverage certificate. A concept with zero admissible
    features must produce zero groups LOUDLY and must be distinguishable
    from a concept that has groups."""


class TierNotDeclared(GroupSelectionError):
    """The tier was not declared before selection (RULING_13 Q1 clause 7).

    The binding rule: the tier is DECLARED BEFORE SELECTION, carried in
    every sentence reporting the result, and results from different tiers
    are NEVER MERGED. Widening from TIER-S to TIER-C after seeing TIER-S
    empty is permitted ONLY if both were declared in advance -- which is
    why `tiers_declared_in_advance` is a required field and not an
    afterthought."""


class ConceptAttributionRefused(GroupSelectionError):
    """A TIER-J result was asked to carry the concept's name.

    RULING_13 Q1 clause 7: TIER-J requires no gate of its members and is
    REFUSED for any concept-attributed claim. Its outputs may be called
    'a direction set that changes the text' and NEVER 'the cheese
    features'."""


class TierNotSelectableHere(GroupSelectionError):
    """TIER-J cannot be CONSTRUCTED from `A[f, c]`, and manufacturing it
    would be the vacuity defect wearing a tier label.

    TWO INDEPENDENT REASONS, both structural. (1) TIER-J requires NO gate of
    its members, and `A` is by definition the gate record -- this file has
    no ungated pool and will not invent one. (2) If it did, by declaring
    every scored feature admissible in every cell, then `cov(G) = 1^|C|`
    for ANY non-empty `G`: the coverage certificate would carry ZERO
    information and every single feature would be a 'complete group'. That
    is a check that cannot fail, which is this sprint's named defect class.

    TIER-J exploration is permitted by RULING_13 for engineering only, and a
    lane doing it must build its pool from something other than `A` and must
    not call the result by the concept's name."""


class EntityDiscriminatorDispositionMissing(GroupSelectionError):
    """A group was handed toward causal spend without the written,
    per-member entity-discriminator disposition (RULING_13 Q1 clause 9).

    The three-substrate comparison is computed, read AND DISPOSITIONED IN
    WRITING at selection, BEFORE ANY CAUSAL SPEND. The disposition may be
    'proceed with the flag'; it may NOT be silence and may NOT arrive after
    the grid."""


#: RULING_13 Q1 clause 9, the PM's sentence carried verbatim on any group
#: that reaches a causal arm without the discriminator dispositioned.
ENTITY_DISCRIMINATOR_SENTENCE = (
    "...a group reported without it has not been distinguished from a nation-name detector"
)

TIER_C = "TIER_C"
TIER_S = "TIER_S"
TIER_J = "TIER_J"
TIERS = (TIER_C, TIER_S, TIER_J)

#: What each tier requires OF A MEMBER. The GROUP's coverage requirement is
#: identical in all three (`cov(G) == 1^|C|`); the tiers differ only in the
#: membership bar, which is the whole point of clause 7.
TIER_MEMBERSHIP = {
    TIER_C: "admissible in AT LEAST ONE cell (individual CORRELATIONAL admissibility)",
    TIER_S: "admissible in ALL cells (survivorship; min-across-cells AS A QUALIFIER)",
    TIER_J: "no gate required of members -- REFUSED for any concept-attributed claim",
}

#: TIER-C is PRIMARY (clause 7). Recorded as a constant so a caller reading
#: this file does not have to infer the primary tier from a default argument.
PRIMARY_TIER = TIER_C

#: How the search ceiling is obtained. RULING_13 REFUSES setting `K_max` as
#: a number while REQUIRING that one be pre-registered, so this file DERIVES
#: it instead of inventing it: every IRREDUNDANT cover of a universe of |C|
#: cells has at most |C| members, since each member must hold at least one
#: cell no other member holds. Arity |C| is therefore a STRUCTURAL
#: EXHAUSTION BOUND and not a tuned ceiling -- searching to |C| searches the
#: whole space of irredundant covers, so a null at this ceiling is NOT
#: arity-limited. A caller may pass a SMALLER `k_max` as a cost bound; the
#: result then says so explicitly and the null becomes ceiling-limited.
K_MAX_BASIS = (
    "DERIVED, not invented: every irredundant cover of |C| cells has at most |C| members, because "
    "each member must hold a cell no other member holds. k_max = |C| therefore exhausts the space "
    "of irredundant covers rather than bounding a search inside it."
)

#: Reporting bound on how many candidate members are LISTED per pattern slot
#: of an equivalence class. It bounds the LISTING only: the exact number of
#: feature-level realisations is reported as an integer regardless, and the
#: omitted count is named per slot. A silent top-N here would read as "these
#: are all of them".
DEFAULT_MEMBERS_LISTED_PER_SLOT = 25

#: Node budget for the exact enumeration. A COST bound, not a scientific
#: threshold, and exceeding it RAISES (see `SearchBudgetExceeded`).
DEFAULT_NODE_BUDGET = 2_000_000

#: The permanent caveat on any group claim, whatever the tier (clause 7,
#: 'the_pool_bound_inherited_unchanged'). PERMITTED: 'among features that
#: individually clear [tier], this minimal cover jointly steers the
#: concept'. PROHIBITED: 'these are the features needed'.
POOL_BOUND_CAVEAT = (
    "POOL-BOUNDED BY CONSTRUCTION: this is a minimal cover AMONG features that individually clear "
    "the declared tier's membership bar. It is NOT a claim that these are the features needed, and "
    "the recall caveat is permanent -- features outside the pool are not excluded by this result."
)

#: Selection is not sufficiency. Nothing in this file scores a generation.
NO_CAUSAL_EVIDENCE_CAVEAT = (
    "SELECTION ONLY: no intervened generation exists behind this record. cov(G) is a CORRELATIONAL "
    "coverage certificate over the frozen gates; joint sufficiency is UNTESTED here, the margin and "
    "ceiling that would decide it are unset by ruling, and they come from a control-only calibration "
    "run by a lane that does not select the group."
)


def _import_module_from_exact_file(module_name: str, expected_file: Path, *, why: str):
    """Import `module_name` and REFUSE unless it came from `expected_file`.

    Same guard, same reason, as `group_intervention._import_module_from_exact_file`:
    `scripts/legacy/final_pairing_concept_discovery.py` is a 23-line stub
    that defines none of the runner's functions, so a `sys.path` accident
    makes `import final_pairing_concept_discovery` succeed with the wanted
    names PRESENT AND EMPTY. Name equality is not identity. Duplicated here
    rather than imported from `group_intervention` because importing that
    module to obtain an import helper would pull in the whole intervention
    stack for a file that needs no torch model at all."""
    resolved_expected = expected_file.resolve()
    cached = sys.modules.get(module_name)
    if cached is not None:
        cached_file = getattr(cached, "__file__", None)
        if cached_file is None or Path(cached_file).resolve() != resolved_expected:
            del sys.modules[module_name]
    search_dir = str(resolved_expected.parent)
    while search_dir in sys.path:
        sys.path.remove(search_dir)
    sys.path.insert(0, search_dir)
    try:
        module = __import__(module_name)
    except Exception as exc:
        raise GroupSelectionError(
            f"could not import {module_name} from {resolved_expected} "
            f"({type(exc).__name__}: {exc}). REFUSING to continue: {why}"
        ) from exc
    actual_file = getattr(module, "__file__", None)
    if actual_file is None or Path(actual_file).resolve() != resolved_expected:
        raise GroupSelectionError(
            f"{module_name} resolved to {actual_file} but this module requires {resolved_expected} "
            f"-- a same-named module on sys.path shadowed it. Refusing to use it: {why}"
        )
    return module


def _import_discovery_module():
    """Import the discovery runner for its REFUSAL IDENTITY and its
    admissibility builder.

    Two things are taken from it and nothing else: `PerCellRetentionMissing`,
    so a missing-per-cell refusal raised here is the SAME CLASS a caller
    already catches from the scan, and `build_admissibility_matrix`, so this
    file can be handed per-cell floats and produce `A` through the
    production path instead of a private reimplementation that could drift
    from it. Loaded by file identity because the legacy stub really
    exists."""
    module = _import_module_from_exact_file(
        "final_pairing_concept_discovery",
        SCRIPT_DIR / "final_pairing_concept_discovery.py",
        why="the admissibility matrix and its refusal class define what a group even is; a stub "
        "that carries those names while defining neither would make every result here vacuous.",
    )
    for required in ("PerCellRetentionMissing", "build_admissibility_matrix"):
        if not hasattr(module, required):
            raise GroupSelectionError(
                f"final_pairing_concept_discovery at {module.__file__} has no {required!r} -- a "
                f"module present by name and empty of the thing it was imported for."
            )
    return module


_DISCOVERY = _import_discovery_module()

#: THE SAME CLASS the scan raises, not a look-alike. A second refusal
#: identity would let one consumer's `except` clause miss the other's
#: refusal, which is how a hard refusal becomes a silent fallback.
PerCellRetentionMissing = _DISCOVERY.PerCellRetentionMissing

#: Keys that mean the caller handed over the COLLAPSED record. Named
#: explicitly so the refusal can say WHICH collapse it found rather than
#: reporting a generic KeyError.
_COLLAPSED_KEYS = ("min_separation_auroc", "min_fire_rate", "min_near_miss_auroc")


@dataclass(frozen=True)
class CoverageProblem:
    """`A[f, c]`, the declared tier, and nothing that could rank a feature.

    `admissible_by_cell` is the COMPLETE support of `A` per cell -- the
    record the scan emits is untruncated at any k, and this dataclass keeps
    it that way. `pattern_to_features` is the same information grouped by
    the `2^|C|` coverage patterns, which is the object the exact cover
    search reads."""

    concept_id: str
    tier: str
    cell_order: tuple[str, ...]
    admissible_by_cell: dict[str, frozenset[int]]
    pattern_to_features: dict[int, tuple[int, ...]]
    features_admissible_in_no_cell: int
    features_scored: int | None
    #: "real" or a string beginning "surrogate" -- carried into every record
    #: so a surrogate result can never read as a measurement.
    data_provenance: str
    tiers_declared_in_advance: tuple[str, ...]
    pairing: str | None = None
    thresholds_used: dict = field(default_factory=dict)
    #: Optional per-cell full-space ceilings (`per_cell_full_space_*`
    #: summaries). Used ONLY to disambiguate an unreachable cell, and only
    #: by comparing recorded ceilings against recorded frozen thresholds --
    #: no number is invented to do it.
    per_cell_ceilings: dict = field(default_factory=dict)
    #: WHAT THE MATRIX'S OWN PROVENANCE DOES TO THIS FILE'S HEADLINE NUMBER.
    #: `build_admissibility_matrix` screens each gate at
    #: `threshold - screen_epsilon`, so `A` is a SUPERSET of the
    #: exactly-computed admissible set -- never a subset. Set inclusion runs
    #: one way through minimum cover: a superset can only make a cover
    #: EASIER, so `minimum_arity` measured here is a LOWER BOUND on the
    #: minimum over the exact `A`, and a group could in principle owe a
    #: member to last-ulp slack. `features_within_screen_epsilon_band`, which
    #: the scan already records per cell and per gate, is the exact bound on
    #: how many features that slack could have added. Carried rather than
    #: dropped, because dropping it would leave 'minimum' looking exact in a
    #: direction it is not.
    screen_provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cell_order:
            raise PerCellRetentionMissing(
                "no cells: a coverage problem with an empty cell order cannot carry a coverage "
                "certificate, and `all()` over zero cells would report every set COMPLETE. This is "
                "the vacuity defect, refused at construction."
            )
        if self.tier not in TIERS:
            raise TierNotDeclared(f"tier must be one of {TIERS}, got {self.tier!r}")
        if self.tier == TIER_J:
            raise TierNotSelectableHere(
                "TIER_J requires no gate of its members, so it cannot be constructed from "
                "A[f, c] -- and if every feature were declared admissible everywhere then "
                f"cov(G) = 1^{len(self.cell_order)} for ANY non-empty G, a coverage certificate "
                "carrying zero information. Refused rather than manufactured. TIER_J exploration "
                "must build its pool elsewhere and may never carry the concept's name."
            )
        if self.tier not in self.tiers_declared_in_advance:
            raise TierNotDeclared(
                f"tier {self.tier!r} is not in tiers_declared_in_advance="
                f"{self.tiers_declared_in_advance!r}. RULING_13 Q1 clause 7: the tier is DECLARED "
                f"BEFORE SELECTION, and widening (e.g. TIER_S -> TIER_C after seeing TIER_S empty) "
                f"is permitted ONLY if both were declared in advance."
            )
        if not set(self.admissible_by_cell) >= set(self.cell_order):
            missing = sorted(set(self.cell_order) - set(self.admissible_by_cell))
            raise PerCellRetentionMissing(
                f"per-cell admissible support is missing the cells {missing} -- a partial support "
                f"cannot produce a sound coverage vector"
            )

    @property
    def n_cells(self) -> int:
        return len(self.cell_order)

    @property
    def universe_mask(self) -> int:
        return (1 << self.n_cells) - 1

    @property
    def pool(self) -> tuple[int, ...]:
        """Every feature admissible in at least one cell, ascending. THE
        POOL IS THE POOL: no ranking, no cut, no top-N."""
        return tuple(sorted({f for features in self.pattern_to_features.values() for f in features}))

    @property
    def pool_size(self) -> int:
        return len(self.pool)

    @property
    def survivors(self) -> tuple[int, ...]:
        """Features admissible in ALL cells (TIER-S membership). MAY BE
        EMPTY, and an empty TIER-S is a reportable null."""
        return tuple(sorted(self.pattern_to_features.get(self.universe_mask, ())))

    @property
    def reachable_mask(self) -> int:
        """The best coverage ANY set of admissible features can achieve --
        the union of every pattern present. Nothing larger is reachable at
        any arity, which is what makes an unreachable cell a statement about
        the encoding rather than about the search."""
        mask = 0
        for pattern in self.pattern_to_features:
            mask |= pattern
        return mask

    def pattern_of(self, feature: int) -> int:
        mask = 0
        for index, cell in enumerate(self.cell_order):
            if feature in self.admissible_by_cell[cell]:
                mask |= 1 << index
        return mask

    def cells_of_mask(self, mask: int) -> tuple[str, ...]:
        return tuple(
            cell for index, cell in enumerate(self.cell_order) if mask & (1 << index)
        )

    def format_mask(self, mask: int) -> str:
        """Binary string in `cell_order` order, LEFT to RIGHT. The scan's
        own census strings are right-to-left (bit i counting from the right
        is `cell_order[i]`); this file states its direction on every string
        it prints rather than leaving a reader to guess between two
        conventions."""
        return "".join("1" if mask & (1 << index) else "0" for index in range(self.n_cells))


def coverage_vector(problem: CoverageProblem, group: Iterable[int]) -> tuple[int, ...]:
    """`cov(G)[c] = 1` iff some member of `G` is admissible in `c`.

    Computed from the per-cell SUPPORT, not from the pattern abstraction the
    search runs over, so a minimality check performed with this function is
    independent of the search's construction rather than tautological in
    it."""
    members = set(group)
    return tuple(
        1 if members & problem.admissible_by_cell[cell] else 0 for cell in problem.cell_order
    )


def coverage_size(vector: Sequence[int]) -> int:
    """`|cov(G)|` in `0..|C|`. Reported ALONGSIDE the vector, never instead
    of it (RULING_13 Q1 clause 3)."""
    return int(sum(vector))


def is_complete(problem: CoverageProblem, group: Iterable[int]) -> bool:
    """`G` is COMPLETE iff `cov(G) == 1^|C|`.

    THE EMPTY SET IS NEVER COMPLETE, and that is not pedantry: `all([])` is
    True, and a `cov()` computed over an empty group with zero cells is how
    an admissibility check passed in this sprint while being unable to
    exercise anything. A problem with zero cells cannot be constructed
    (`CoverageProblem.__post_init__` refuses), and an empty group short-
    circuits to False here."""
    members = set(group)
    if not members:
        return False
    return all(coverage_vector(problem, members))


def assert_not_vacuous(result: GroupSelectionResult) -> None:
    """REFUSE a completeness claim that was computed over nothing.

    The failure this catches, in its exact historical shape: a surrogate
    with zero admissible features, `cov()` taken over the empty set, and
    'all groups complete' reported True. Nothing in this file can produce
    that -- and this assertion exists anyway, because the defect was not
    detected by the code that produced it."""
    if result.complete_group_count and result.pool_size == 0:
        raise VacuousCoverageClaim(
            f"{result.complete_group_count} complete group(s) claimed for concept "
            f"{result.concept_id!r} while the admissible pool is EMPTY. A concept with zero "
            f"admissible features has zero groups; a completeness claim over an empty pool is the "
            f"vacuity defect."
        )
    if result.complete_group_count and not result.cell_order:
        raise VacuousCoverageClaim(
            "completeness claimed over ZERO cells -- 1^0 is not a coverage certificate"
        )
    for group in result.groups:
        if group.complete and not group.feature_indices:
            raise VacuousCoverageClaim(
                "a group with no members is reported COMPLETE -- cov over the empty set"
            )
        if group.complete and coverage_size(group.coverage) != result.n_cells:
            raise VacuousCoverageClaim(
                f"group {group.feature_indices} is flagged complete with |cov| = "
                f"{coverage_size(group.coverage)} over {result.n_cells} cells"
            )


def _patterns_from_support(
    admissible_by_cell: Mapping[str, Iterable[int]], cell_order: Sequence[str]
) -> dict[int, tuple[int, ...]]:
    """Group features by coverage pattern. Features admissible in NO cell
    get pattern 0 and are DROPPED here -- correlational admissibility is the
    membership bar (clause 6), so a feature with an empty pattern is not
    eligible for any tier that carries the concept's name. The count of what
    was dropped is reported, never silently absorbed."""
    pattern_by_feature: dict[int, int] = {}
    for index, cell in enumerate(cell_order):
        bit = 1 << index
        for feature in admissible_by_cell[cell]:
            pattern_by_feature[int(feature)] = pattern_by_feature.get(int(feature), 0) | bit
    grouped: dict[int, list[int]] = {}
    for feature, pattern in pattern_by_feature.items():
        if pattern:
            grouped.setdefault(pattern, []).append(feature)
    return {pattern: tuple(sorted(features)) for pattern, features in sorted(grouped.items())}


def build_problem_from_record(
    record: Mapping,
    *,
    tier: str,
    tiers_declared_in_advance: Sequence[str],
    concept_id: str,
    data_provenance: str,
    pairing: str | None = None,
    per_cell_ceilings: Mapping | None = None,
) -> CoverageProblem:
    """Build the coverage problem from the scan's LOSSLESS admissibility
    record (`FullSpaceScan.admissibility`, carried on a verdict and in
    `grid.json`).

    THE REFUSALS COME FIRST AND THEY ARE HARD. A record that carries only
    the collapsed `min_*` arrays, or that is missing the per-cell support,
    raises `PerCellRetentionMissing` -- the same class the scan raises. It
    is never approximated from a minimum, because a selector that could
    read `min_*` when the per-cell data is missing would eventually do so
    and report groups that were never per-cell."""
    if record is None:
        raise PerCellRetentionMissing(
            "the admissibility record is None. A verdict written before A[f, c] existed does not "
            "say that no feature is admissible -- it says nothing, and conflating 'this record "
            "predates the field' with 'this concept has no admissible feature' would turn a stale "
            "record into a scientific finding."
        )
    collapsed = [key for key in _COLLAPSED_KEYS if key in record]
    if collapsed and "admissible_feature_indices_by_cell" not in record:
        raise PerCellRetentionMissing(
            f"this record carries the COLLAPSED quantities {collapsed} and no per-cell admissible "
            f"support. min-across-cells is a QUALIFIER, not a RANKER, and it cannot be inverted: "
            f"the matrix determines the min, the min never determines the matrix. Re-run the scan "
            f"with per-cell retention; nothing here will approximate A from a minimum."
        )
    for required in ("cell_order", "admissible_feature_indices_by_cell"):
        if required not in record:
            raise PerCellRetentionMissing(
                f"admissibility record has no {required!r} -- without it there is no A[f, c], "
                f"therefore no cov(G), therefore no group"
            )
    cell_order = tuple(str(cell) for cell in record["cell_order"])
    support = record["admissible_feature_indices_by_cell"]
    missing = [cell for cell in cell_order if cell not in support]
    if missing:
        raise PerCellRetentionMissing(
            f"admissible support is missing the cells {missing}; a partial support cannot produce "
            f"a sound coverage vector"
        )
    admissible = {cell: frozenset(int(f) for f in support[cell]) for cell in cell_order}
    if tier == TIER_S:
        survivors = frozenset.intersection(*(admissible[cell] for cell in cell_order))
        admissible = {cell: (admissible[cell] & survivors) for cell in cell_order}
    patterns = _patterns_from_support(admissible, cell_order)
    return CoverageProblem(
        concept_id=str(concept_id),
        tier=tier,
        cell_order=cell_order,
        admissible_by_cell=admissible,
        pattern_to_features=patterns,
        features_admissible_in_no_cell=int(record.get("features_admissible_in_no_cell", 0)),
        features_scored=(int(record["d_sae"]) if "d_sae" in record else None),
        data_provenance=str(data_provenance),
        tiers_declared_in_advance=tuple(tiers_declared_in_advance),
        pairing=pairing,
        thresholds_used=dict(record.get("thresholds_used", {})),
        per_cell_ceilings=dict(per_cell_ceilings or {}),
        screen_provenance={
            "screen_epsilon": record.get("screen_epsilon"),
            "screen_derived": record.get("screen_derived"),
            "features_within_screen_epsilon_band": record.get(
                "features_within_screen_epsilon_band"
            ),
        },
    )


def build_problem_from_matrix(
    matrix: np.ndarray,
    *,
    cell_keys: Sequence[str],
    tier: str,
    tiers_declared_in_advance: Sequence[str],
    concept_id: str,
    data_provenance: str,
    pairing: str | None = None,
    thresholds_used: Mapping | None = None,
    per_cell_ceilings: Mapping | None = None,
) -> CoverageProblem:
    """Build the problem from the in-memory boolean `[d_sae, n_cells]`
    matrix (`FullSpaceScan.admissibility_matrix`). Same refusals: a matrix
    whose column count disagrees with `cell_keys` is a partial retention,
    not a smaller universe."""
    if matrix is None:
        raise PerCellRetentionMissing(
            "admissibility_matrix is None -- this scan carries no per-cell retention, and a "
            "minimum will not be substituted for it"
        )
    array = np.asarray(matrix)
    if array.ndim != 2 or array.shape[1] != len(cell_keys):
        raise PerCellRetentionMissing(
            f"admissibility matrix has shape {array.shape}, expected (d_sae, {len(cell_keys)}) for "
            f"cell_keys={tuple(cell_keys)!r}"
        )
    if array.dtype != bool:
        raise PerCellRetentionMissing(
            f"admissibility matrix dtype is {array.dtype}, expected bool -- A[f, c] is a boolean "
            f"conjunction of three gates, and a float matrix here means an un-thresholded quantity "
            f"was passed where the boolean was required"
        )
    admissible = {
        cell: frozenset(int(f) for f in np.flatnonzero(array[:, column]).tolist())
        for column, cell in enumerate(cell_keys)
    }
    if tier == TIER_S:
        survivors = frozenset(int(f) for f in np.flatnonzero(array.all(axis=1)).tolist())
        admissible = {cell: (values & survivors) for cell, values in admissible.items()}
    return CoverageProblem(
        concept_id=str(concept_id),
        tier=tier,
        cell_order=tuple(str(cell) for cell in cell_keys),
        admissible_by_cell=admissible,
        pattern_to_features=_patterns_from_support(admissible, tuple(cell_keys)),
        features_admissible_in_no_cell=int((~array.any(axis=1)).sum()),
        features_scored=int(array.shape[0]),
        data_provenance=str(data_provenance),
        tiers_declared_in_advance=tuple(tiers_declared_in_advance),
        pairing=pairing,
        thresholds_used=dict(thresholds_used or {}),
        per_cell_ceilings=dict(per_cell_ceilings or {}),
        screen_provenance={
            "screen_epsilon": None,
            "screen_derived": (
                "NOT SUPPLIED on this path: the caller handed over the boolean matrix without the "
                "record that carries the screen epsilon and its band, so how much of A is owed to "
                "last-ulp slack is UNKNOWN here rather than zero."
            ),
            "features_within_screen_epsilon_band": None,
        },
    )


def load_problems_from_grid(
    path: str | Path,
    *,
    tier: str,
    tiers_declared_in_advance: Sequence[str],
    concept_ids: Sequence[str] | None = None,
) -> dict[str, CoverageProblem]:
    """Read EXACTLY the named `grid.json` -- never glob a parent directory,
    the same rule `read_grid_result` states for itself.

    An `error` verdict is NOT a concept with no admissible features: it is a
    cell with no measurement, and it is skipped with its error carried into
    the raised message rather than being silently read as a null."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"grid not found at the exact path {path} (this function never globs a parent directory)"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    problems: dict[str, CoverageProblem] = {}
    for verdict in data.get("verdicts", []):
        concept_id = verdict.get("concept_id")
        if concept_ids is not None and concept_id not in concept_ids:
            continue
        if verdict.get("status") == "error":
            raise PerCellRetentionMissing(
                f"verdict for concept {concept_id!r} is an ERROR cell ({verdict.get('error')!r}) -- "
                f"it carries no admissibility matrix, and an absent measurement is not a null"
            )
        problems[concept_id] = build_problem_from_record(
            verdict.get("admissibility_matrix"),
            tier=tier,
            tiers_declared_in_advance=tiers_declared_in_advance,
            concept_id=concept_id,
            data_provenance=f"real:{path.name}",
            pairing=verdict.get("pairing") or data.get("pairing"),
            per_cell_ceilings={
                "separation_auroc": verdict.get("per_cell_full_space_auroc"),
                "fire_rate": verdict.get("per_cell_full_space_fire_rate"),
                "near_miss_auroc": verdict.get("per_cell_full_space_near_miss_auroc"),
            },
        )
    if concept_ids is not None:
        absent = [c for c in concept_ids if c not in problems]
        if absent:
            raise GroupSelectionError(f"grid {path} carries no verdict for concepts {absent}")
    return problems


@dataclass(frozen=True)
class MinimumCoverSearch:
    """What the exact search actually did, so 'minimum' is a measured claim.

    `closure_stopped_growing_at_arity` is the load-bearing field for a null.
    It is the FIRST arity at which the frontier added no new covered-mask;
    since the set of achievable masks grows monotonically with arity, nothing
    new is reachable at any larger arity either. A null reported with this
    field set is therefore NOT arity-limited -- it is a statement about the
    encoding, not about where the search stopped. `None` means the search
    reached `k_max` while still growing, and only then is a null
    ceiling-limited."""

    minimum_arity: int | None
    target_mask: int
    k_max: int
    k_max_basis: str
    maximum_arity_examined: int
    closure_stopped_growing_at_arity: int | None
    distinct_patterns: int
    dp_states: int
    enumeration_nodes: int
    exact: bool = True
    method: str = (
        "breadth-first closure over the 2^|C| covered-masks for the exact minimum, then "
        "depth-first enumeration of EVERY minimum-cardinality cover with a dp lower-bound cut. "
        "No greedy step exists in this file."
    )


def _cover_lower_bounds(pattern_masks: Sequence[int], n_cells: int) -> list[int]:
    """`lower[u]` = the exact minimum number of patterns needed to cover the
    cells in mask `u`. Computed over all `2^|C|` masks (64 at |C| = 6), so
    it is a table, not a heuristic, and it is what makes the enumeration's
    pruning exact rather than approximate."""
    size = 1 << n_cells
    infinity = size + 1
    best = [infinity] * size
    best[0] = 0
    #: Forward closure over covered-masks: reachable[k] grows monotonically.
    frontier = [0]
    arity = 0
    while frontier:
        arity += 1
        nxt = []
        for covered in frontier:
            for pattern in pattern_masks:
                merged = covered | pattern
                if best[merged] > arity:
                    best[merged] = arity
                    nxt.append(merged)
        frontier = nxt
    lower = [infinity] * size
    for uncovered in range(size):
        candidates = [best[c] for c in range(size) if (c & uncovered) == uncovered]
        lower[uncovered] = min(candidates) if candidates else infinity
    return lower


def exact_minimum_cover(
    problem: CoverageProblem, *, target_mask: int | None = None, k_max: int | None = None
) -> MinimumCoverSearch:
    """THE EXACT MINIMUM, plus the evidence that it is exact.

    Every feature collapses to one of `2^|C|` patterns, so the minimum cover
    of `target_mask` is the shortest path from the empty covered-mask to
    `target_mask` in a graph of at most `2^|C|` nodes. Breadth-first search
    over that graph returns the TRUE minimum: no approximation, no ranking,
    no tie-break involved at this stage. `closure_stopped_growing_at_arity`
    records where the reachable set stopped growing, which is how a null is
    distinguished from a search that merely stopped early."""
    universe = problem.universe_mask if target_mask is None else int(target_mask)
    ceiling = problem.n_cells if k_max is None else int(k_max)
    basis = K_MAX_BASIS if k_max is None else (
        f"CALLER-SUPPLIED COST BOUND k_max={ceiling} (the derived structural bound is "
        f"{problem.n_cells}); a null under this ceiling IS arity-limited and says so"
    )
    pattern_masks = tuple(problem.pattern_to_features)
    if universe == 0:
        # Refused rather than answered: an empty target is a coverage
        # question with no cells in it, and 'covered' would be vacuously
        # true for the empty set.
        raise VacuousCoverageClaim(
            "the target coverage mask is empty -- there is nothing to cover, and reporting the "
            "empty set as a cover of nothing is the vacuity defect"
        )
    reached = {0}
    frontier = [0]
    arity = 0
    saturated_at: int | None = None
    minimum: int | None = None
    while arity < ceiling:
        arity += 1
        nxt = []
        for covered in frontier:
            for pattern in pattern_masks:
                merged = covered | pattern
                if merged not in reached:
                    reached.add(merged)
                    nxt.append(merged)
        # `reached` holds every mask attainable with AT MOST `arity`
        # patterns, so the first arity at which the target appears IS the
        # exact minimum. No ranking and no tie-break is involved.
        if any((covered & universe) == universe for covered in reached):
            minimum = arity
            break
        if not nxt:
            # The closure stopped growing. Coverage is monotone in arity, so
            # NO larger arity can cover anything new -- the null is a
            # statement about the encoding, not about where the search
            # stopped.
            saturated_at = arity
            break
        frontier = nxt
    return MinimumCoverSearch(
        minimum_arity=minimum,
        target_mask=universe,
        k_max=ceiling,
        k_max_basis=basis,
        maximum_arity_examined=arity,
        closure_stopped_growing_at_arity=saturated_at,
        distinct_patterns=len(pattern_masks),
        dp_states=len(reached),
        enumeration_nodes=0,
    )


def enumerate_minimum_pattern_covers(
    problem: CoverageProblem,
    *,
    arity: int,
    target_mask: int | None = None,
    node_budget: int = DEFAULT_NODE_BUDGET,
) -> tuple[tuple[frozenset[int], ...], int]:
    """EVERY minimum-cardinality cover, at the level of coverage patterns.

    Complete by construction: at each step the search takes the LOWEST
    still-uncovered cell and branches over every pattern covering it, so no
    cover can be missed; the same set can be reached by more than one order,
    so results are deduplicated and the raw node count is returned
    alongside. The `lower[]` table cuts a branch only when the EXACT
    remaining requirement already exceeds the budget, so pruning cannot
    remove a solution.

    PATTERNS, NOT FEATURES, ARE THE EQUIVALENCE CLASSES. Two features with
    the same pattern are interchangeable for coverage, so the pattern-level
    solution set is the complete and finite description of the solution
    space; `expand_pattern_cover` turns one class into its feature-level
    members and `realisation_multiplicity` counts them exactly."""
    universe = problem.universe_mask if target_mask is None else int(target_mask)
    pattern_masks = tuple(problem.pattern_to_features)
    lower = _cover_lower_bounds(pattern_masks, problem.n_cells)
    by_cell: dict[int, tuple[int, ...]] = {
        bit: tuple(p for p in pattern_masks if p & (1 << bit)) for bit in range(problem.n_cells)
    }
    solutions: set[frozenset[int]] = set()
    nodes = 0

    def recurse(covered: int, chosen: tuple[int, ...]) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > node_budget:
            raise SearchBudgetExceeded(
                f"exact enumeration exceeded {node_budget} nodes at arity {arity} with "
                f"{len(pattern_masks)} distinct patterns. REFUSING to substitute a greedy "
                f"approximation: RULING_13 Q1 clause 8 refuses greedy for cover construction, so "
                f"the honest outcome is this refusal plus the measured node count."
            )
        uncovered = universe & ~covered
        if not uncovered:
            solutions.add(frozenset(chosen))
            return
        remaining_budget = arity - len(chosen)
        if remaining_budget <= 0 or lower[uncovered] > remaining_budget:
            return
        lowest = (uncovered & -uncovered).bit_length() - 1
        for pattern in by_cell[lowest]:
            if pattern in chosen:
                continue
            recurse(covered | pattern, (*chosen, pattern))

    recurse(0, ())
    ordered = tuple(
        sorted(solutions, key=lambda s: (len(s), tuple(sorted(s))))
    )
    return ordered, nodes


def expand_pattern_cover(
    problem: CoverageProblem, pattern_cover: Iterable[int]
) -> tuple[tuple[int, ...], ...]:
    """Every feature-level realisation of one pattern-level cover.

    UNBOUNDED BY DESIGN and therefore not called by the reporting path: the
    count is the PRODUCT of the pattern multiplicities and can be
    astronomically large, which is exactly why the report emits the
    pattern-level classes plus an exact integer count instead of a
    truncated list of feature sets. Provided so a test can compare this
    file's answer against brute force at small scale."""
    slots = [problem.pattern_to_features[p] for p in sorted(pattern_cover)]
    return tuple(tuple(sorted(combo)) for combo in product(*slots))


def verify_minimality_under_removal(
    problem: CoverageProblem, group: Sequence[int]
) -> dict:
    """MEASURED, NEVER ASSUMED FROM THE SEARCH.

    A minimum-cardinality cover is necessarily irredundant, but this file is
    not permitted to report minimality as a corollary of its own
    construction -- that would be a check unable to fail. So every emitted
    group is re-tested member by member, AGAINST THE PER-CELL SUPPORT, and
    the coverage vector after each removal is recorded rather than
    summarised into a boolean.

    Reported per member: the coverage vector without it, `|cov|` without it,
    and which cells are lost. `minimal_under_removal` is true iff removing
    ANY member strictly reduces the coverage vector -- for a complete group
    that is exactly 'no member can be dropped while covering all cells'."""
    members = tuple(sorted(set(int(f) for f in group)))
    full_vector = coverage_vector(problem, members)
    removals = []
    minimal = bool(members)
    for member in members:
        remainder = tuple(f for f in members if f != member)
        vector = coverage_vector(problem, remainder)
        lost = tuple(
            cell
            for index, cell in enumerate(problem.cell_order)
            if full_vector[index] and not vector[index]
        )
        strictly_smaller = coverage_size(vector) < coverage_size(full_vector)
        if not strictly_smaller:
            minimal = False
        removals.append(
            {
                "removed_feature": member,
                "coverage_vector_without_it": list(vector),
                "coverage_size_without_it": coverage_size(vector),
                "cells_lost": list(lost),
                "still_complete_without_it": all(vector) if remainder else False,
                "removal_strictly_reduces_coverage": strictly_smaller,
            }
        )
    return {
        "minimal_under_removal": minimal,
        "method": (
            "each member removed in turn and cov() recomputed FROM THE PER-CELL SUPPORT, not "
            "inferred from the pattern-level search that produced the group"
        ),
        "coverage_vector": list(full_vector),
        "removals": removals,
    }


@dataclass(frozen=True)
class GroupCandidate:
    """One group: a SET plus its COVERAGE CERTIFICATE, and the equivalence
    class it represents.

    `feature_indices` is the canonical realisation (see
    `CANONICAL_REALISATION_RULE`); `realisation_multiplicity` is the EXACT
    number of feature-level groups in the same equivalence class, so an
    emitted representative can never read as 'the only one'."""

    tier: str
    concept_id: str
    feature_indices: tuple[int, ...]
    arity: int
    coverage: tuple[int, ...]
    coverage_size: int
    complete: bool
    pattern_by_member: tuple[tuple[int, str], ...]
    equivalence_class_patterns: tuple[str, ...]
    realisation_multiplicity: int
    members_available_per_slot: tuple[dict, ...]
    minimality: dict

    def to_record(self) -> dict:
        return {
            "tier": self.tier,
            "concept_id_or_label": self.concept_id,
            "feature_indices": list(self.feature_indices),
            "arity_MEASURED_not_pre_registered": self.arity,
            "coverage_vector": list(self.coverage),
            "coverage_size_reported_alongside_the_vector_never_instead": self.coverage_size,
            "complete": self.complete,
            "pattern_by_member": [
                {"feature_index": f, "coverage_pattern_left_to_right": p}
                for f, p in self.pattern_by_member
            ],
            "equivalence_class_patterns": list(self.equivalence_class_patterns),
            "feature_level_realisations_of_this_class": self.realisation_multiplicity,
            "members_available_per_slot": list(self.members_available_per_slot),
            "minimality_under_removal": self.minimality,
            "single_feature_not_a_group_of_one": self.arity == 1,
        }


#: The tie-break, pre-registered here and deterministic (RULING_13 Q1 clause
#: 8 requires one 'ending in ascending feature index'). It is ONLY a
#: reporting order and a canonical representative: EVERY minimum cover is
#: emitted at the pattern level and every class carries its exact
#: multiplicity, so nothing is selected away by it. Deliberately carries NO
#: scientific preference -- the smallest feature index has no property that
#: recommends it -- because a preference among equally minimal groups is not
#: ruled, and inventing one here would smuggle a selection rule into a
#: formatting decision. That gap is named in the report as a referral.
CANONICAL_REALISATION_RULE = (
    "within each pattern slot take the LOWEST feature index; order groups lexicographically by the "
    "ascending feature-index tuple. Reporting order and canonical representative ONLY -- not a "
    "preference among equally minimal groups, which RULING_13 does not rule on."
)


@dataclass(frozen=True)
class GroupSelectionResult:
    """The whole solution set, not a winner."""

    status: str
    concept_id: str
    tier: str
    tiers_declared_in_advance: tuple[str, ...]
    pairing: str | None
    data_provenance: str
    cell_order: tuple[str, ...]
    pool_size: int
    survivor_count: int
    features_admissible_in_no_cell: int
    features_scored: int | None
    best_achievable_coverage: tuple[int, ...]
    unreachable_cells: tuple[str, ...]
    unreachable_cell_disambiguation: dict
    groups: tuple[GroupCandidate, ...]
    pattern_solution_count: int
    feature_level_solution_count: int
    emitted_group_count: int
    dropped_from_emission: dict
    search: MinimumCoverSearch
    coverage_pattern_census: dict
    screen_provenance: dict
    notes: tuple[str, ...]

    @property
    def n_cells(self) -> int:
        return len(self.cell_order)

    @property
    def complete_group_count(self) -> int:
        return sum(1 for g in self.groups if g.complete)

    @property
    def all_groups_complete(self) -> bool:
        """FALSE when there are no groups.

        `all(...)` over an empty sequence is True, which is precisely how
        'all groups complete' was reported for a concept with zero
        admissible features. This property refuses to inherit that."""
        return bool(self.groups) and all(g.complete for g in self.groups)

    def to_record(self) -> dict:
        return {
            "status": self.status,
            "concept_id_or_label": self.concept_id,
            "tier": self.tier,
            "tier_membership_bar": TIER_MEMBERSHIP[self.tier],
            "tiers_declared_in_advance": list(self.tiers_declared_in_advance),
            "pairing": self.pairing,
            "data_provenance": self.data_provenance,
            "cell_order": list(self.cell_order),
            "n_cells": self.n_cells,
            "pool_size": self.pool_size,
            "survivor_count_TIER_S_may_be_empty": self.survivor_count,
            "features_admissible_in_no_cell": self.features_admissible_in_no_cell,
            "features_scored": self.features_scored,
            "minimum_arity_MEASURED": self.search.minimum_arity,
            "maximum_arity_examined": self.search.maximum_arity_examined,
            "k_max": self.search.k_max,
            "k_max_basis": self.search.k_max_basis,
            "closure_stopped_growing_at_arity": self.search.closure_stopped_growing_at_arity,
            "null_is_arity_limited": (
                self.search.minimum_arity is None
                and self.search.closure_stopped_growing_at_arity is None
            ),
            "exact": self.search.exact,
            "search_method": self.search.method,
            "distinct_coverage_patterns": self.search.distinct_patterns,
            "enumeration_nodes": self.search.enumeration_nodes,
            "best_achievable_coverage_vector": list(self.best_achievable_coverage),
            "best_achievable_coverage_size": coverage_size(self.best_achievable_coverage),
            "unreachable_cells": list(self.unreachable_cells),
            "unreachable_cell_disambiguation": self.unreachable_cell_disambiguation,
            "pattern_level_solution_count": self.pattern_solution_count,
            "feature_level_solution_count_EXACT": self.feature_level_solution_count,
            "emitted_group_count": self.emitted_group_count,
            "dropped_from_emission": self.dropped_from_emission,
            "all_groups_complete": self.all_groups_complete,
            "complete_group_count": self.complete_group_count,
            "canonical_realisation_rule": CANONICAL_REALISATION_RULE,
            "minimum_is_with_respect_to_A_AS_RECORDED": {
                "why": (
                    "A is screen-derived at threshold - screen_epsilon, so it is a SUPERSET of the "
                    "exactly-computed admissible set. A superset can only make a cover easier, so "
                    "the minimum arity above is a LOWER BOUND on the minimum over the exact A."
                ),
                **self.screen_provenance,
            },
            # Named for its BIT DIRECTION. The scan's own census strings run
            # right-to-left (bit i from the right is cell_order[i]); these run
            # left-to-right. Two conventions for the same object is how a
            # reader silently transposes a coverage pattern.
            "coverage_pattern_census_bits_left_to_right": self.coverage_pattern_census,
            "groups": [g.to_record() for g in self.groups],
            "caveats": {
                "pool_bound": POOL_BOUND_CAVEAT,
                "no_causal_evidence": NO_CAUSAL_EVIDENCE_CAVEAT,
                "entity_discriminator": (
                    "NOT DISPOSITIONED HERE. RULING_13 Q1 clause 9 requires the three-substrate "
                    "comparison read and dispositioned IN WRITING, per member, before any causal "
                    f"spend. {ENTITY_DISCRIMINATOR_SENTENCE}"
                ),
            },
            "notes": list(self.notes),
        }


#: Statuses. Each names WHAT WAS FOUND, so a null can never be read as a
#: different null (RULING_13 Q2 clause 4).
STATUS_COMPLETE = "COMPLETE_COVER"
STATUS_NO_ADMISSIBLE = "NULL_COVER_NO_ADMISSIBLE_FEATURE"
STATUS_UNREACHABLE = "NULL_COVER_UNREACHABLE_CELLS"
STATUS_ARITY_CEILING = "NULL_COVER_ARITY_CEILING"


def _disambiguate_unreachable(problem: CoverageProblem, cells: Sequence[str]) -> dict:
    """For each unreachable cell, WHY -- using only numbers already
    recorded.

    RULING_13 Q2 clause 4 (`NULL_COVER`): a failing cell whose full-space
    ceiling clears the bar means a SELECTION ARTIFACT; a ceiling below the
    bar means a PROPERTY OF THE ENCODING. That dichotomy is stated for ONE
    limb, and admissibility is a CONJUNCTION of three, so a third case
    exists and is named rather than forced into one of the two: every limb's
    ceiling clears its own bar and still no single feature clears all three
    at once. Nothing is invented here -- the ceilings come from the scan's
    per-cell summaries and the bars from the frozen thresholds carried in
    the same record."""
    if not cells:
        return {}
    ceilings = problem.per_cell_ceilings or {}
    bars = {
        "separation_auroc": problem.thresholds_used.get("G_A_separation_auroc_min"),
        "fire_rate": problem.thresholds_used.get("G_B_fire_rate_min"),
        "near_miss_auroc": problem.thresholds_used.get("G_C_specificity_auroc_vs_near_miss_min"),
    }
    out: dict = {}
    for cell in cells:
        limbs: dict = {}
        for quantity, bar in bars.items():
            summary = (ceilings.get(quantity) or {}).get("cells", {}).get(cell)
            ceiling = None
            if summary is not None:
                ceiling = summary.get(f"max_{quantity}", summary.get("max_separation_auroc"))
            limbs[quantity] = {
                "ceiling": ceiling,
                "frozen_bar": bar,
                "ceiling_clears_bar": (
                    None if ceiling is None or bar is None else bool(ceiling >= bar)
                ),
            }
        known = [v["ceiling_clears_bar"] for v in limbs.values()]
        if any(value is None for value in known):
            verdict = "UNDISAMBIGUATED_NO_PER_CELL_CEILINGS_SUPPLIED"
            because = (
                "the per-cell full-space ceilings for this cell were not supplied, so this cell's "
                "emptiness is NOT disambiguated. Stated rather than guessed."
            )
        elif all(known):
            verdict = "CONJUNCTION_FAILURE_NOT_A_SINGLE_LIMB_CEILING"
            because = (
                "every limb's ceiling clears its own frozen bar in this cell, yet no single feature "
                "clears all three AT ONCE. This is neither of the two cases the ruling names for a "
                "one-limb failure, and is reported as its own finding rather than assimilated."
            )
        elif any(known):
            verdict = "ENCODING_PROPERTY_FOR_THE_FAILING_LIMB"
            because = (
                "at least one limb's full-space ceiling sits BELOW its frozen bar in this cell, so "
                "no feature can be admissible here under this SAE at this layer -- a property of "
                "the encoding, not of the selection."
            )
        else:
            verdict = "ENCODING_PROPERTY_ALL_LIMBS_BELOW_BAR"
            because = "no limb's ceiling reaches its frozen bar in this cell."
        out[cell] = {"verdict": verdict, "because": because, "limbs": limbs}
    return out


def select_groups(
    problem: CoverageProblem,
    *,
    k_max: int | None = None,
    members_listed_per_slot: int = DEFAULT_MEMBERS_LISTED_PER_SLOT,
    max_emitted_groups: int | None = None,
    node_budget: int = DEFAULT_NODE_BUDGET,
) -> GroupSelectionResult:
    """Turn `A[f, c]` into the COMPLETE set of minimal candidate groups.

    ORDER OF OPERATIONS, and it is the order the controls demand:

    1. The pool. Empty pool -> `NULL_COVER_NO_ADMISSIBLE_FEATURE` with zero
       groups. Loud, distinguishable, and not a coverage claim.
    2. Reachability. `best_achievable_coverage` is the union of every
       pattern present. If it is short of `1^|C|` the unreachable cells are
       NAMED and the status is `NULL_COVER_UNREACHABLE_CELLS` -- a finding
       about the encoding, per RULING_13 Q2 clause 4, and the best partial
       cover is still computed and emitted for exactly those cells that ARE
       reachable.
    3. The exact minimum over the reachable target, then EVERY
       minimum-cardinality cover.
    4. Minimality under removal, re-measured per group.

    `k_max` defaults to the DERIVED structural bound `|C|` (see
    `K_MAX_BASIS`); pass a smaller one only as a cost bound, and the result
    will say the null is ceiling-limited."""
    notes: list[str] = []
    census = {
        problem.format_mask(pattern): len(features)
        for pattern, features in sorted(problem.pattern_to_features.items())
    }
    empty_search = MinimumCoverSearch(
        minimum_arity=None,
        target_mask=problem.universe_mask,
        k_max=problem.n_cells if k_max is None else int(k_max),
        k_max_basis=K_MAX_BASIS if k_max is None else f"CALLER-SUPPLIED COST BOUND k_max={k_max}",
        maximum_arity_examined=0,
        closure_stopped_growing_at_arity=0,
        distinct_patterns=0,
        dp_states=1,
        enumeration_nodes=0,
    )
    if problem.pool_size == 0:
        return GroupSelectionResult(
            status=STATUS_NO_ADMISSIBLE,
            concept_id=problem.concept_id,
            tier=problem.tier,
            tiers_declared_in_advance=problem.tiers_declared_in_advance,
            pairing=problem.pairing,
            data_provenance=problem.data_provenance,
            cell_order=problem.cell_order,
            pool_size=0,
            survivor_count=0,
            features_admissible_in_no_cell=problem.features_admissible_in_no_cell,
            features_scored=problem.features_scored,
            best_achievable_coverage=tuple([0] * problem.n_cells),
            unreachable_cells=problem.cell_order,
            unreachable_cell_disambiguation=_disambiguate_unreachable(problem, problem.cell_order),
            groups=(),
            pattern_solution_count=0,
            feature_level_solution_count=0,
            emitted_group_count=0,
            dropped_from_emission={},
            search=empty_search,
            coverage_pattern_census=census,
            screen_provenance=problem.screen_provenance,
            notes=(
                f"ZERO features are admissible in ANY cell at tier {problem.tier}, so there are "
                f"ZERO groups. This is NOT 'all groups complete': cov() over an empty set is "
                f"0^{problem.n_cells}, and a completeness claim computed over an empty pool is the "
                f"vacuity defect this status exists to make impossible to report as a success.",
                f"tier membership bar: {TIER_MEMBERSHIP[problem.tier]}",
            ),
        )

    reachable = problem.reachable_mask
    unreachable_cells = problem.cells_of_mask(problem.universe_mask & ~reachable)
    best_vector = tuple(1 if reachable & (1 << i) else 0 for i in range(problem.n_cells))
    target = reachable & problem.universe_mask
    search = exact_minimum_cover(problem, target_mask=target, k_max=k_max)
    if unreachable_cells:
        notes.append(
            f"cov = 1^{problem.n_cells} is UNREACHABLE for concept {problem.concept_id!r} at tier "
            f"{problem.tier}: no admissible feature exists in the cell(s) "
            f"{list(unreachable_cells)}. The best achievable coverage is {list(best_vector)} "
            f"(|cov| = {coverage_size(best_vector)}) and that ceiling holds at EVERY arity, since "
            f"the union of all patterns present is the maximum any set can reach. Per RULING_13 Q2 "
            f"clause 4 this is a finding about the encoding, not a lane failure."
        )
    if search.minimum_arity is None:
        status = STATUS_ARITY_CEILING
        # Reached ONLY through a caller-supplied k_max smaller than |C|: the
        # union of all patterns present is always coverable by at most one
        # pattern per cell, so under the derived ceiling the reachable target
        # always has a cover. The note is derived from the recorded
        # saturation field rather than asserted about it.
        ceiling_limited = search.closure_stopped_growing_at_arity is None
        notes.append(
            f"no cover of the reachable target at arity <= {search.k_max}. This null IS "
            f"ceiling-limited: the closure was still growing when the ceiling was reached."
            if ceiling_limited
            else
            f"no cover of the reachable target at arity <= {search.k_max}, and the closure had "
            f"already stopped growing at arity {search.closure_stopped_growing_at_arity} -- so "
            f"this null is NOT arity-limited."
        )
        return GroupSelectionResult(
            status=status,
            concept_id=problem.concept_id,
            tier=problem.tier,
            tiers_declared_in_advance=problem.tiers_declared_in_advance,
            pairing=problem.pairing,
            data_provenance=problem.data_provenance,
            cell_order=problem.cell_order,
            pool_size=problem.pool_size,
            survivor_count=len(problem.survivors),
            features_admissible_in_no_cell=problem.features_admissible_in_no_cell,
            features_scored=problem.features_scored,
            best_achievable_coverage=best_vector,
            unreachable_cells=unreachable_cells,
            unreachable_cell_disambiguation=_disambiguate_unreachable(problem, unreachable_cells),
            groups=(),
            pattern_solution_count=0,
            feature_level_solution_count=0,
            emitted_group_count=0,
            dropped_from_emission={},
            search=search,
            coverage_pattern_census=census,
            screen_provenance=problem.screen_provenance,
            notes=tuple(notes),
        )

    pattern_solutions, nodes = enumerate_minimum_pattern_covers(
        problem, arity=search.minimum_arity, target_mask=target, node_budget=node_budget
    )
    search = MinimumCoverSearch(
        minimum_arity=search.minimum_arity,
        target_mask=search.target_mask,
        k_max=search.k_max,
        k_max_basis=search.k_max_basis,
        maximum_arity_examined=max(search.maximum_arity_examined, search.minimum_arity),
        closure_stopped_growing_at_arity=search.closure_stopped_growing_at_arity,
        distinct_patterns=search.distinct_patterns,
        dp_states=search.dp_states,
        enumeration_nodes=nodes,
    )

    total_feature_level = 0
    candidates: list[GroupCandidate] = []
    for pattern_cover in pattern_solutions:
        slots = sorted(pattern_cover)
        multiplicity = math.prod(len(problem.pattern_to_features[p]) for p in slots)
        total_feature_level += multiplicity
        canonical = tuple(sorted(problem.pattern_to_features[p][0] for p in slots))
        vector = coverage_vector(problem, canonical)
        candidates.append(
            GroupCandidate(
                tier=problem.tier,
                concept_id=problem.concept_id,
                feature_indices=canonical,
                arity=len(canonical),
                coverage=vector,
                coverage_size=coverage_size(vector),
                complete=is_complete(problem, canonical),
                pattern_by_member=tuple(
                    (f, problem.format_mask(problem.pattern_of(f))) for f in canonical
                ),
                equivalence_class_patterns=tuple(problem.format_mask(p) for p in slots),
                realisation_multiplicity=multiplicity,
                members_available_per_slot=tuple(
                    {
                        "coverage_pattern_left_to_right": problem.format_mask(p),
                        "cells_covered": list(problem.cells_of_mask(p)),
                        "members_available": len(problem.pattern_to_features[p]),
                        "members_listed": list(
                            problem.pattern_to_features[p][:members_listed_per_slot]
                        ),
                        "members_omitted_from_this_listing": max(
                            0, len(problem.pattern_to_features[p]) - members_listed_per_slot
                        ),
                    }
                    for p in slots
                ),
                minimality=verify_minimality_under_removal(problem, canonical),
            )
        )

    candidates.sort(key=lambda g: g.feature_indices)
    dropped: dict = {}
    emitted = tuple(candidates)
    if max_emitted_groups is not None and len(candidates) > max_emitted_groups:
        emitted = tuple(candidates[:max_emitted_groups])
        dropped = {
            "pattern_level_classes_found": len(candidates),
            "pattern_level_classes_emitted": len(emitted),
            "pattern_level_classes_dropped": len(candidates) - len(emitted),
            "dropped_class_patterns": [
                list(g.equivalence_class_patterns) for g in candidates[max_emitted_groups:]
            ],
            "why_this_is_named": (
                "a silent top-N would read as 'these are all of them'. The complete class count and "
                "the exact feature-level total are reported above regardless of this bound."
            ),
        }
    status = STATUS_COMPLETE if not unreachable_cells else STATUS_UNREACHABLE
    if problem.tier == TIER_S and problem.pool_size:
        notes.append(
            "TIER_S: every member is admissible in ALL cells, so min-across-cells is doing the "
            "QUALIFYING here (permitted) and no ranking is derived from it (refused)."
        )
    if not problem.survivors:
        achieved = (
            f"a COMPLETE cover exists at arity {search.minimum_arity}"
            if status == STATUS_COMPLETE
            else f"the best achievable coverage {list(best_vector)} is reached at arity "
            f"{search.minimum_arity}"
        )
        notes.append(
            f"survivors == 0 at tier {problem.tier} (no feature is admissible in all "
            f"{problem.n_cells} cells) while {achieved}. This is the jointly-only case: individual "
            f"CAUSAL sufficiency is not required of a member (that is what a group is for) and "
            f"individual survivorship is not either -- only correlational admissibility in at "
            f"least one cell."
        )
    if search.minimum_arity == 1:
        notes.append(
            "minimum arity is 1: RULING_13 Q1 clause 8 requires this be REPORTED AS A SINGLE "
            "FEATURE, not dressed up as a group of one."
        )
    notes.append(
        f"the null-arity question does not arise: the exact minimum was found at arity "
        f"{search.minimum_arity} <= k_max {search.k_max}, and k_max is the DERIVED structural "
        f"bound, not a tuned ceiling ({search.k_max_basis})."
    )
    result = GroupSelectionResult(
        status=status,
        concept_id=problem.concept_id,
        tier=problem.tier,
        tiers_declared_in_advance=problem.tiers_declared_in_advance,
        pairing=problem.pairing,
        data_provenance=problem.data_provenance,
        cell_order=problem.cell_order,
        pool_size=problem.pool_size,
        survivor_count=len(problem.survivors),
        features_admissible_in_no_cell=problem.features_admissible_in_no_cell,
        features_scored=problem.features_scored,
        best_achievable_coverage=best_vector,
        unreachable_cells=unreachable_cells,
        unreachable_cell_disambiguation=_disambiguate_unreachable(problem, unreachable_cells),
        groups=emitted,
        pattern_solution_count=len(candidates),
        feature_level_solution_count=total_feature_level,
        emitted_group_count=len(emitted),
        dropped_from_emission=dropped,
        search=search,
        coverage_pattern_census=census,
        screen_provenance=problem.screen_provenance,
        notes=tuple(notes),
    )
    assert_not_vacuous(result)
    return result


def claim_sentence(result: GroupSelectionResult, *, attribute_to_concept: bool = True) -> str:
    """The one sentence this result licenses, with the tier in it.

    PERMITTED (clause 7): 'among features that individually clear [tier],
    this minimal cover jointly steers the concept'. PROHIBITED: 'these are
    the features needed'. And no sentence produced here asserts steering at
    all, because no intervened generation exists behind it."""
    if result.tier == TIER_J and attribute_to_concept:
        raise ConceptAttributionRefused(
            "TIER_J requires no gate of its members and is REFUSED for any concept-attributed "
            "claim (RULING_13 Q1 clause 7). Its output is 'a direction set that changes the text', "
            f"never 'the {result.concept_id} features'. Call with attribute_to_concept=False."
        )
    tiers = {g.tier for g in result.groups}
    if len(tiers) > 1:
        raise GroupSelectionError(
            f"groups from different tiers {sorted(tiers)} in one result -- results from different "
            f"tiers are NEVER MERGED (RULING_13 Q1 clause 7)"
        )
    subject = (
        f"concept {result.concept_id!r}" if attribute_to_concept else "a direction set (UNATTRIBUTED)"
    )
    if result.status == STATUS_NO_ADMISSIBLE:
        return (
            f"NULL_COVER for {subject} at {result.tier}: ZERO features are admissible in any of the "
            f"{result.n_cells} cells, so there are ZERO groups. |pool| = 0, k_max = "
            f"{result.search.k_max}, maximum arity examined = {result.search.maximum_arity_examined}. "
            f"This is not 'no complete group was found among candidates' -- there were no "
            f"candidates. {result.data_provenance}"
        )
    if result.status == STATUS_ARITY_CEILING:
        return (
            f"NULL_COVER for {subject} at {result.tier}: no complete cover at arity <= "
            f"{result.search.k_max}. |pool| = {result.pool_size}, maximum arity examined = "
            f"{result.search.maximum_arity_examined}, best achievable coverage "
            f"{list(result.best_achievable_coverage)}. {result.data_provenance}"
        )
    head = (
        f"Among features that individually clear {result.tier} membership "
        f"({TIER_MEMBERSHIP[result.tier]}), |pool| = {result.pool_size} over {result.n_cells} cells"
    )
    if result.status == STATUS_UNREACHABLE:
        return (
            f"{head}: cov = 1^{result.n_cells} is UNREACHABLE for {subject} -- no admissible "
            f"feature exists in {list(result.unreachable_cells)}. Best achievable coverage vector "
            f"{list(result.best_achievable_coverage)}, |cov| = "
            f"{coverage_size(result.best_achievable_coverage)}, reached minimally at arity "
            f"{result.search.minimum_arity} by {result.pattern_solution_count} distinct pattern "
            f"class(es). An incomplete group's result may NOT be read as covering the cells it "
            f"misses. {POOL_BOUND_CAVEAT} {NO_CAUSAL_EVIDENCE_CAVEAT} {result.data_provenance}"
        )
    thing = "a SINGLE FEATURE" if result.search.minimum_arity == 1 else (
        f"a minimal cover of {result.search.minimum_arity} features"
    )
    vector = list(result.groups[0].coverage) if result.groups else [1] * result.n_cells
    return (
        f"{head}: {thing} covers all {result.n_cells} cells for {subject} -- cov(G) = "
        f"{vector}, |cov(G)| = {sum(vector)}. "
        f"{result.pattern_solution_count} distinct minimal pattern class(es) achieve this, "
        f"{result.feature_level_solution_count} feature-level realisation(s) in total; the arity is "
        f"MEASURED, not pre-registered. {POOL_BOUND_CAVEAT} {NO_CAUSAL_EVIDENCE_CAVEAT} "
        f"{result.data_provenance}"
    )


def assert_ready_for_causal_spend(
    result: GroupSelectionResult, dispositions: Mapping[int, str] | None = None
) -> dict:
    """THE BOUNDARY THIS FILE REFUSES TO CROSS.

    RULING_13 Q1 clause 9: the three-substrate entity-discriminator
    comparison is computed, read AND DISPOSITIONED IN WRITING at selection,
    PER MEMBER, BEFORE ANY CAUSAL SPEND; the disposition may be 'proceed
    with the flag' but may not be silence. This selector cannot compute it
    (it needs substrate data this file never sees), so it REFUSES to hand a
    group onward until a written per-member disposition is supplied, and it
    never builds a `GroupSpec`: the dose is a number set by the calibrating
    lane, and this lane selects the group."""
    dispositions = dict(dispositions or {})
    members = sorted({f for g in result.groups for f in g.feature_indices})
    if not members:
        raise EntityDiscriminatorDispositionMissing(
            f"no group to spend on: status {result.status}. {ENTITY_DISCRIMINATOR_SENTENCE}"
        )
    undispositioned = [
        f for f in members if not str(dispositions.get(f, "")).strip()
    ]
    if undispositioned:
        raise EntityDiscriminatorDispositionMissing(
            f"features {undispositioned} carry NO WRITTEN entity-discriminator disposition. It "
            f"applies PER MEMBER, it must be written BEFORE any causal spend, and it may not be "
            f"silence. {ENTITY_DISCRIMINATOR_SENTENCE}"
        )
    if result.tier == TIER_J:
        raise ConceptAttributionRefused(
            "TIER_J may not carry a concept-attributed causal claim (RULING_13 Q1 clause 7)"
        )
    return {
        "members": members,
        "dispositions": {int(f): str(dispositions[f]) for f in members},
        "still_unexercised": [
            "the intervention dose (alpha) is NOT set here -- it comes from the calibrating lane, "
            "and group_intervention.minimum_effective_alpha is the instrument that sizes a "
            "survivable one under bf16 absorption",
            "the margin and ceiling for the sufficiency criterion are unset by ruling and come "
            "from a control-only calibration pinned before any intervened generation is scored",
            "the firing precondition (delta_norm per call, per-member post-intervention latents) "
            "is checked by the intervention lane, not here",
        ],
    }


# ---------------------------------------------------------------------------
# Surrogate builders for the self-check. THEY ARE LABELLED SURROGATE
# EVERYWHERE, because a surrogate result that reads as a measurement is the
# same defect class as a check that cannot fail.
# ---------------------------------------------------------------------------

SIX_CELLS = ("en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3")


def surrogate_problem(
    *,
    patterns: Mapping[str, int],
    d_sae: int,
    tier: str = PRIMARY_TIER,
    tiers_declared_in_advance: Sequence[str] = (TIER_S, TIER_C),
    concept_id: str,
    cell_keys: Sequence[str] = SIX_CELLS,
    label: str,
    thresholds_used: Mapping | None = None,
    per_cell_ceilings: Mapping | None = None,
) -> CoverageProblem:
    """Build a surrogate problem THROUGH the production emitter.

    `patterns` maps a left-to-right binary string to how many features carry
    that pattern. The per-cell floats are synthesised from it and then run
    through the REAL `build_admissibility_matrix`, so the surrogate can
    never assert against a matrix the production path would not produce --
    the same discipline the discovery suite's `_synthetic_scan` uses."""
    cell_keys = tuple(cell_keys)
    auroc_min, fire_min, near_min = 0.90, 0.70, 0.75
    sep = {cell: np.zeros(d_sae) for cell in cell_keys}
    fire = {cell: np.zeros(d_sae) for cell in cell_keys}
    near = {cell: np.zeros(d_sae) for cell in cell_keys}
    feature = 0
    for pattern_string, count in patterns.items():
        if len(pattern_string) != len(cell_keys):
            raise ValueError(
                f"pattern {pattern_string!r} has {len(pattern_string)} bits, expected "
                f"{len(cell_keys)} (one per cell, LEFT to RIGHT in cell_keys order)"
            )
        for _ in range(count):
            if feature >= d_sae:
                raise ValueError("more patterned features requested than d_sae")
            for index, bit in enumerate(pattern_string):
                if bit == "1":
                    cell = cell_keys[index]
                    sep[cell][feature] = 0.99
                    fire[cell][feature] = 0.95
                    near[cell][feature] = 0.90
            feature += 1
    _matrix, record = _DISCOVERY.build_admissibility_matrix(
        {"separation_auroc": sep, "fire_rate": fire, "near_miss_auroc": near},
        cell_keys=cell_keys,
        auroc_min=auroc_min,
        fire_rate_min=fire_min,
        near_miss_auroc_min=near_min,
        d_sae=d_sae,
    )
    return build_problem_from_record(
        record,
        tier=tier,
        tiers_declared_in_advance=tiers_declared_in_advance,
        concept_id=concept_id,
        data_provenance=f"SURROGATE (not a measurement): {label}",
        pairing=None,
        per_cell_ceilings=per_cell_ceilings,
    )


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


def _selfcheck() -> int:
    """CONTROLS FIRST, then the passing cases. Every line of the passing
    output carries SURROGATE, because no real `A[f, c]` exists on this
    machine: the grids that would carry one are on `/scratch` behind an
    access outage."""
    failures: list[str] = []

    def refuses(label: str, fn, expected: type[Exception], must_contain: str = "") -> None:
        try:
            fn()
        except expected as exc:
            message = str(exc)
            ok = must_contain.lower() in message.lower()
            print(f"[{'REFUSED' if ok else 'REFUSED-BUT-WRONG-REASON'}] {label}")
            print(f"          {type(exc).__name__}: {message[:300]}")
            if not ok:
                failures.append(f"{label}: message lacked {must_contain!r}")
        except Exception as exc:  # a control must report ANY wrong failure, not a curated subset
            print(f"[WRONG-EXCEPTION] {label}: {type(exc).__name__}: {exc}")
            failures.append(f"{label}: raised {type(exc).__name__}")
        else:
            print(f"[DID-NOT-REFUSE] {label}  <-- CONTROL FAILED")
            failures.append(f"{label}: did not refuse")

    _print("CONTROL 1 -- VACUITY: a concept with ZERO admissible features")
    empty = surrogate_problem(
        patterns={}, d_sae=64, concept_id="surrogate_zero_admissible",
        label="zero admissible features anywhere",
    )
    empty_result = select_groups(empty)
    print(f"status                : {empty_result.status}")
    print(f"pool_size             : {empty_result.pool_size}")
    print(f"groups emitted        : {empty_result.emitted_group_count}")
    print(f"all_groups_complete   : {empty_result.all_groups_complete}")
    print(f"naive all([]) would be: {all(is_complete(empty, g) for g in [])}  <-- THE TRAP")
    print(f"best achievable cov   : {list(empty_result.best_achievable_coverage)}")
    print(f"claim: {claim_sentence(empty_result)[:300]}")
    if empty_result.status != STATUS_NO_ADMISSIBLE or empty_result.groups:
        failures.append("vacuity control: an empty pool produced groups or the wrong status")
    if empty_result.all_groups_complete:
        failures.append("vacuity control: all_groups_complete was True over zero groups")

    _print("CONTROL 2 -- the empty set is never complete, and zero cells REFUSES")
    print(f"is_complete(problem, ()) : {is_complete(empty, ())}")
    if is_complete(empty, ()):
        failures.append("the empty set was reported complete")
    refuses(
        "a coverage problem with NO cells",
        lambda: CoverageProblem(
            concept_id="x", tier=TIER_C, cell_order=(), admissible_by_cell={},
            pattern_to_features={}, features_admissible_in_no_cell=0, features_scored=0,
            data_provenance="SURROGATE", tiers_declared_in_advance=(TIER_C,),
        ),
        PerCellRetentionMissing,
        "vacuity",
    )

    _print("CONTROL 3 -- assert_not_vacuous catches a hand-built vacuous claim")
    good = surrogate_problem(
        patterns={"111111": 1}, d_sae=8, concept_id="surrogate_single",
        label="one feature admissible everywhere",
    )
    good_result = select_groups(good)
    forged = GroupSelectionResult(
        **{
            **{k: getattr(good_result, k) for k in good_result.__dataclass_fields__},
            "pool_size": 0,
        }
    )
    refuses(
        "a completeness claim with an EMPTY pool",
        lambda: assert_not_vacuous(forged),
        VacuousCoverageClaim,
        "vacuity defect",
    )

    _print("CONTROL 4 -- REFUSAL: the collapsed min-only record")
    refuses(
        "a record carrying only min_* arrays",
        lambda: build_problem_from_record(
            {"min_separation_auroc": [0.99] * 8, "min_fire_rate": [0.9] * 8},
            tier=TIER_C, tiers_declared_in_advance=(TIER_C,), concept_id="cheese",
            data_provenance="SURROGATE",
        ),
        PerCellRetentionMissing,
        "QUALIFIER, not a RANKER",
    )
    refuses(
        "a verdict that PREDATES A[f, c] (record is None)",
        lambda: build_problem_from_record(
            None, tier=TIER_C, tiers_declared_in_advance=(TIER_C,), concept_id="cheese",
            data_provenance="SURROGATE",
        ),
        PerCellRetentionMissing,
        "predates",
    )
    refuses(
        "an admissibility matrix that is None",
        lambda: build_problem_from_matrix(
            None, cell_keys=SIX_CELLS, tier=TIER_C, tiers_declared_in_advance=(TIER_C,),
            concept_id="cheese", data_provenance="SURROGATE",
        ),
        PerCellRetentionMissing,
        "no per-cell retention",
    )
    refuses(
        "a FLOAT matrix where the boolean conjunction was required",
        lambda: build_problem_from_matrix(
            np.ones((8, 6)), cell_keys=SIX_CELLS, tier=TIER_C,
            tiers_declared_in_advance=(TIER_C,), concept_id="cheese", data_provenance="SURROGATE",
        ),
        PerCellRetentionMissing,
        "dtype",
    )

    _print("CONTROL 5 -- REFUSAL: a tier that was not declared before selection")
    refuses(
        "TIER_C selected when only TIER_S was declared in advance",
        lambda: surrogate_problem(
            patterns={"111111": 1}, d_sae=8, tier=TIER_C, tiers_declared_in_advance=(TIER_S,),
            concept_id="cheese", label="tier declaration control",
        ),
        TierNotDeclared,
        "DECLARED BEFORE SELECTION",
    )

    _print("CONTROL 6 -- REFUSAL: TIER_J is not constructible here, and never carries the name")
    refuses(
        "constructing a TIER_J coverage problem from A[f, c]",
        lambda: surrogate_problem(
            patterns={"111000": 1, "000111": 1}, d_sae=8, tier=TIER_J,
            tiers_declared_in_advance=(TIER_J,), concept_id="cheese",
            label="TIER_J construction control",
        ),
        TierNotSelectableHere,
        "carrying zero information",
    )
    # The naming guard is belt and braces: the builders refuse TIER_J
    # earlier, so it is exercised on a FORGED result to prove it is not
    # dead code.
    forged_tier_j = GroupSelectionResult(
        **{
            **{k: getattr(good_result, k) for k in good_result.__dataclass_fields__},
            "tier": TIER_J,
            "groups": (),
        }
    )
    refuses(
        "a concept-attributed claim sentence at TIER_J",
        lambda: claim_sentence(forged_tier_j),
        ConceptAttributionRefused,
        "direction set that changes the text",
    )

    _print("CONTROL 7 -- REFUSAL: causal spend without the written per-member disposition")
    refuses(
        "handing a group onward with no entity-discriminator disposition",
        lambda: assert_ready_for_causal_spend(good_result),
        EntityDiscriminatorDispositionMissing,
        "nation-name detector",
    )

    _print("SURROGATE RESULT A -- a single feature admissible everywhere (arity 1)")
    print(f"status                : {good_result.status}")
    print(f"minimum arity MEASURED: {good_result.search.minimum_arity}")
    print(f"cov(G)                : {list(good_result.groups[0].coverage)}")
    print(f"|cov(G)|              : {good_result.groups[0].coverage_size}")
    print(f"claim: {claim_sentence(good_result)[:260]}")

    _print("SURROGATE RESULT B -- the JOINTLY-ONLY case: survivors == 0, cov(G) == 1^6")
    jointly = surrogate_problem(
        patterns={"111000": 3, "000111": 2, "110000": 5, "000011": 4},
        d_sae=256, concept_id="surrogate_jointly_only",
        label="no feature admissible in all six cells; complementary halves",
    )
    jointly_result = select_groups(jointly)
    print(f"survivors (TIER_S)          : {jointly_result.survivor_count}")
    print(f"status                      : {jointly_result.status}")
    print(f"minimum arity MEASURED      : {jointly_result.search.minimum_arity}")
    print(f"k_max / max arity examined  : {jointly_result.search.k_max} / "
          f"{jointly_result.search.maximum_arity_examined}")
    print(f"pattern-level solutions     : {jointly_result.pattern_solution_count}")
    print(f"feature-level solutions     : {jointly_result.feature_level_solution_count} (EXACT)")
    print(f"enumeration nodes           : {jointly_result.search.enumeration_nodes}")
    for group in jointly_result.groups:
        print(
            f"  group {list(group.feature_indices)} arity {group.arity} cov {list(group.coverage)} "
            f"|cov| {group.coverage_size} minimal_under_removal "
            f"{group.minimality['minimal_under_removal']} class "
            f"{list(group.equivalence_class_patterns)} realisations "
            f"{group.realisation_multiplicity}"
        )
    if jointly_result.survivor_count != 0 or jointly_result.status != STATUS_COMPLETE:
        failures.append("jointly-only surrogate did not reproduce survivors==0 with a complete cover")
    if not all(g.minimality["minimal_under_removal"] for g in jointly_result.groups):
        failures.append("a minimum-cardinality group failed minimality under removal")

    _print("SURROGATE RESULT C -- 1^6 UNREACHABLE (the open cheese shape)")
    unreachable = surrogate_problem(
        patterns={"111000": 2, "000110": 3},
        d_sae=64, concept_id="surrogate_unreachable_cell",
        label="no admissible feature in fr/f3",
        per_cell_ceilings={
            "separation_auroc": {
                "cells": {cell: {"max_separation_auroc": 0.99 if cell != "fr/f3" else 0.41}
                          for cell in SIX_CELLS}
            },
            "fire_rate": {"cells": {cell: {"max_fire_rate": 0.95} for cell in SIX_CELLS}},
            "near_miss_auroc": {
                "cells": {cell: {"max_near_miss_auroc": 0.90} for cell in SIX_CELLS}
            },
        },
    )
    unreachable_result = select_groups(unreachable)
    print(f"status                    : {unreachable_result.status}")
    print(f"unreachable cells         : {list(unreachable_result.unreachable_cells)}")
    print(f"best achievable cov       : {list(unreachable_result.best_achievable_coverage)} "
          f"(|cov| {coverage_size(unreachable_result.best_achievable_coverage)})")
    print(f"minimum arity for the best: {unreachable_result.search.minimum_arity}")
    for cell, why in unreachable_result.unreachable_cell_disambiguation.items():
        print(f"  {cell}: {why['verdict']}")
    print(f"claim: {claim_sentence(unreachable_result)[:300]}")
    if unreachable_result.status != STATUS_UNREACHABLE:
        failures.append("the unreachable surrogate did not report NULL_COVER_UNREACHABLE_CELLS")

    _print("SURROGATE RESULT D -- MANY equally minimal groups (nothing silently dropped)")
    many = surrogate_problem(
        patterns={"111000": 4, "000111": 5, "101010": 6, "010101": 7},
        d_sae=256, concept_id="surrogate_many_minimal",
        label="four complementary patterns, two disjoint pairings",
    )
    many_result = select_groups(many)
    print(f"minimum arity              : {many_result.search.minimum_arity}")
    print(f"pattern-level classes      : {many_result.pattern_solution_count}")
    print(f"feature-level realisations : {many_result.feature_level_solution_count} (EXACT)")
    print(f"emitted                    : {many_result.emitted_group_count}")
    for group in many_result.groups:
        print(
            f"  class {list(group.equivalence_class_patterns)} canonical "
            f"{list(group.feature_indices)} realisations {group.realisation_multiplicity}"
        )
    bounded = select_groups(many, max_emitted_groups=1)
    print(f"with max_emitted_groups=1 -> emitted {bounded.emitted_group_count}, dropped record: "
          f"{json.dumps(bounded.dropped_from_emission)[:200]}")
    if not bounded.dropped_from_emission:
        failures.append("a bounded emission dropped classes without naming them")

    _print("SELF-CHECK SUMMARY")
    if failures:
        for failure in failures:
            print(f"FAILED: {failure}")
        return 1
    print("all controls refused as required and every surrogate result is labelled SURROGATE")
    print(
        "UNEXERCISED HERE: no real A[f, c] exists on this machine (the grids are on /scratch behind "
        "the access outage), no GPU, no model, no intervened generation, no dose, no margin."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Selection of candidate GROUPS from the admissibility matrix A[f, c]: exact minimum "
            "cover over the 2^|C| coverage patterns, the COMPLETE minimal solution set, and "
            "minimality re-measured under removal. No model, no GPU, no generation."
        )
    )
    parser.add_argument("--selfcheck", action="store_true", help="controls first, then surrogates")
    parser.add_argument("--grid", type=Path, default=None, help="exact path to a grid.json")
    parser.add_argument("--concept", action="append", default=None, help="repeatable concept id")
    parser.add_argument(
        "--tier", choices=TIERS, default=None,
        help="the tier, DECLARED BEFORE SELECTION; there is deliberately no default",
    )
    parser.add_argument(
        "--declare-tier", action="append", default=None,
        help="repeatable: the tiers declared in advance (widening needs both declared)",
    )
    parser.add_argument(
        "--k-max", type=int, default=None,
        help="cost bound only; the default is the DERIVED structural bound |C|",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="write the records here")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return _selfcheck()
    if args.grid is None:
        parser.error("either --selfcheck or --grid is required")
    if args.tier is None:
        parser.error(
            "--tier is required and has no default: RULING_13 Q1 clause 7 binds the tier to be "
            "DECLARED BEFORE SELECTION"
        )
    declared = tuple(args.declare_tier or (args.tier,))
    problems = load_problems_from_grid(
        args.grid, tier=args.tier, tiers_declared_in_advance=declared,
        concept_ids=args.concept,
    )
    records = []
    for concept_id, problem in sorted(problems.items()):
        result = select_groups(problem, k_max=args.k_max)
        records.append(result.to_record())
        print(f"\n=== {concept_id} [{result.tier}] ===")
        print(claim_sentence(result, attribute_to_concept=result.tier != TIER_J))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"\nwrote {len(records)} record(s) to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
