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
labelled a MINIMUM-CARDINALITY cover would be a false claim, and the
irredundance that rests on it is load-bearing.
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

WHAT RULING_14 AND ITS ADDENDUM CHANGED HERE (sequences 42 and 43). Four
referrals this file raised were answered and one defect was found INSIDE this
file's own honesty correction. In summary, because the reasoning is at each
clause:

1. ALL EQUALLY-MINIMUM-CARDINALITY CLASSES ARE CARRIED. Candidacy is not
   readable at selection time: the property that would decide it is JOINT
   CAUSAL SUFFICIENCY and this file holds `A`, which is CORRELATIONAL. Every
   selection-time scientific ranking is refused AS A CLASS. The set is the
   deliverable, never a winner. See `SPEND_ORDER_ARBITRARY`.
2. A CLASS IS NOT A TESTABLE UNIT, so the UNIVERSAL null over
   minimum-cardinality covers is UNREACHABLE BY CONSTRUCTION at any budget.
   Only two claim forms exist -- existential, and bounded-negative carrying
   both `n` and `N`. See `PERMITTED_CLAIM_FORMS`, `bounded_negative_sentence`
   and `assert_null_is_not_universal`.
3. THE DERIVED `k_max` DISCHARGES PRE-REGISTRATION, and more strongly than a
   human number would: a theorem has no free parameter to tune post hoc. It
   also proves more than this file had claimed -- every cover CONTAINS an
   irredundant subcover, so a null at arity `<= |C|` is UNCONDITIONAL OVER
   ARITY. Conditional on the ceiling remaining a FUNCTION of `|C|`, never a
   stored 6.
4. 'MINIMAL' STOPS NAMING THE ENUMERATED OBJECT. The enumeration is over
   MINIMUM-CARDINALITY covers, which are all irredundant but are not all of
   the irredundant covers, so the word named a larger set than the one
   measured. That is a SECOND RECALL BOUND beside the pool bound, and the
   widening to larger irredundant covers is PRE-DECLARED on exhaustion.
5. THE TIER-J REFUSAL MOVED TO THE SCHEMA LAYER. Refusing at the pool layer
   is necessary and insufficient, because a tautological certificate is
   indistinguishable from an earned one once serialised. An ungated set is
   admissible and ENCOURAGED as a labelled negative control -- see
   `UngatedControlSet` -- and there is NO WIDENING PATH INTO TIER-J.
6. THE EPSILON BAND WAS A COUNT, so the caveat this file attached to every
   record could not be exercised on the group it qualified. It is now an INDEX
   LIST and group-level membership is DECIDABLE.

AND ONE CLAUSE OF THE RULING WAS WITHDRAWN BY ITS AUTHOR, which this file
records rather than absorbs. Sequence 42 required a plain-float
`values >= threshold` be emitted as "exact A" and HEADLINED over the screened
form. Sequence 43 withdrew it after measuring the numbers: `screen_epsilon` is
1e-9 while one G-A lattice step is 1/600 = 1.7e-3, so the band cannot contain
an ATTAINABLE value -- only a feature whose true rational EQUALS the bar and
whose float64 evaluation fell a few ulps short. The screened form is therefore
the FAITHFUL one and the plain float `>=` is the form carrying the artifact.
What supersedes both is the LATTICE-INTEGER comparison in the scan
(`lattice_gate`), whose denominator is DERIVED per cell from the actual
positive and negative counts. No exact-A headline is implemented here.

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
from itertools import combinations as _combinations
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


class TierWideningIntoTierJRefused(GroupSelectionError):
    """TIER_J was declared as a WIDENING DESTINATION from a gated tier.

    ARCHITECT RULING_14 REFERRAL D CLAUSE 4, closing a hole in RULING_13's own
    clause 7. Read literally, "widening between tiers is permitted if both
    were declared in advance" licensed pre-declaring TIER_J and then widening
    into it once TIER_C came back empty. The architect did not intend that and
    closed it: S to C is a widening from a stronger GATE to a weaker GATE, and
    both are gates -- evidence to less evidence. C to J is a step from
    EVIDENCE TO NO EVIDENCE, and no advance declaration can license it,
    because what makes widening safe is that the destination still supports
    the claim. An empty TIER_C is a REPORTABLE NULL, exactly as an empty
    TIER_S is.

    TIER_J may still be declared in advance as a labelled CONTROL ARM -- see
    `UngatedControlSet`, which is a different object and does not pass
    through `tiers_declared_in_advance` at all. That is the distinction this
    refusal has to be able to make, and the falsifier asserts both
    directions."""


class UngatedSetCannotWearACertificate(GroupSelectionError):
    """An ungated set was pushed through a record shape carrying a coverage
    certificate.

    ARCHITECT RULING_14 REFERRAL D CLAUSE 2. Refusing at the POOL layer, as
    this file already did, is NECESSARY AND INSUFFICIENT: if a TIER_J result
    were ever emitted through the group-record schema its `coverage_vector`
    would read `1^|C|`, `complete` would read true, `minimality_under_removal`
    would read true and the pool-bound caveat would be attached -- and NO
    READER COULD DISTINGUISH A TAUTOLOGICAL CERTIFICATE FROM AN EARNED ONE by
    looking at the record. The defect would arrive by SERIALISATION after
    being refused at the door. So the refusal lives in the schema: an ungated
    set cannot be EXPRESSED as a group at all.

    Also raised when an ungated control set is asked to carry a concept name,
    a coverage certificate, or a table column shared with a gated tier --
    conditions (b), (c) and (e) of the five under which the architect
    ADMITTED and ENCOURAGED the ungated arm as a negative control."""


class UniversalNullUnreachable(GroupSelectionError):
    """A concept-level or class-level null was claimed over untested
    realisations.

    ARCHITECT RULING_14 REFERRAL A CLAUSE 3, and it is a statement about what
    is REACHABLE rather than about what has been done. A pattern-level
    equivalence class is an equivalence class FOR COVERAGE ONLY: two features
    with the same pattern are interchangeable in `cov(G)` and are NOT
    interchangeable under intervention, because they are different directions
    in the residual stream. So the causal arm tests ONE REALISATION and learns
    about ONE REALISATION. With the population of minimum-cardinality covers
    running to millions of realisations, the sentence "minimum-cardinality
    covers do not jointly steer this concept" is not merely unproven, it is
    UNREACHABLE BY CONSTRUCTION at any budget.

    Only two claim forms exist: EXISTENTIAL (a named witness) and BOUNDED
    NEGATIVE (`n` of `N` realisations tested, no success, with `n` AND `N`
    both in the sentence and `N` exact from the multiplicities)."""


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

#: THE SPEND ORDER. Which of the equally-minimum-cardinality classes the
#: causal arm touches first. RULING_14 REFERRAL A dissolves the referral this
#: file raised: candidacy is NOT readable at selection time, because the
#: property that would decide it is JOINT CAUSAL SUFFICIENCY and this file
#: holds `A`, which is CORRELATIONAL. Every selection-time scientific ranking
#: of equally-minimum-cardinality groups is refused AS A CLASS on that ground.
#: Since only existential and bounded-negative claims are available (see
#: `PERMITTED_CLAIM_FORMS`), WHICH realisation is tested first cannot corrupt
#: an inference -- it can only change the probability of finding a witness. So
#: the order is a POWER question, not a VALIDITY one, and a power heuristic
#: requires no scientific warrant, only a declaration.
SPEND_ORDER_ARBITRARY = "declared_arbitrary_lowest_feature_index"
SPEND_ORDER_DEPTH = "elected_per_cell_coverage_depth"
SPEND_ORDERS = (SPEND_ORDER_ARBITRARY, SPEND_ORDER_DEPTH)

#: `d(G)[c] = |{f in G : A[f, c] = 1}|`, of which `cov(G)` is the SIGN. So
#: depth is a strict REFINEMENT of the coverage certificate and the
#: certificate is a collapse of it. RECORDED FOR EVERY EMITTED CLASS whether
#: or not it is elected as the order, because whether depth predicts causal
#: robustness is exactly what the first causal grid could answer and cannot
#: answer retroactively (RULING_14 REFERRAL A clause 7). The addendum at
#: sequence 43 MOTIVATES this further: depth 1 in every cell means every cover
#: is a partition and there is no wider irredundant arm to open at all, while
#: depth above 1 somewhere means there is -- so depth is the quantity that
#: decides REFERRAL C, and it is unmeasured until a real grid runs.
DEPTH_DEFINITION = (
    "d(G)[c] = |{f in G : A[f, c] = 1}|, the PER-CELL DEPTH VECTOR. cov(G) is its sign, so the "
    "coverage certificate is a COLLAPSE of the depth vector and never the other way round."
)

#: The binds on depth, and they are hard (RULING_14 REFERRAL A clause 7,
#: `the_binds_and_they_are_hard`). Depth is permitted as an ORDER and REFUSED
#: as a CLAIM, because that depth predicts causal robustness is ARGUED and
#: unmeasured -- an order does not need it to be true and a claim would.
DEPTH_BINDS = (
    "min-depth is NOT part of the coverage certificate, is NOT a headline, and the word 'depth' may "
    "not appear in any claim sentence, figure caption or abstract. The headline is the coverage "
    "VECTOR and the only permitted scalar is |cov(G)|. The depth vector is retained PER CELL and "
    "never collapsed at retention; any depth scalar appears ONLY inside a spend-order "
    "justification. A group is never described as 'deeper', 'stronger' or 'more robust' on this "
    "basis. That depth predicts causal robustness is ARGUED and unmeasured."
)

#: Words that may not appear in a claim sentence, a caption or an abstract on
#: the strength of the depth vector. Checked by
#: `assert_no_depth_claim`, which exists so the bind above can FAIL rather
#: than merely be stated.
DEPTH_WORDS_REFUSED_IN_A_CLAIM = ("depth", "deeper", "thicker", "stronger", "more robust", "robuster")

#: THE ONLY POOL THIS FILE WILL BUILD A GROUP RECORD FROM. `A` is by
#: definition the gate record, so a set that is not derived from it has no
#: representation in this instrument (RULING_14 REFERRAL D clause 1).
POOL_SOURCE_A = "A[f, c] -- the per-cell three-gate conjunction, which IS the gate record"

#: An ungated set's pool MUST come from somewhere that is not `A`, and it must
#: SAY WHICH -- condition (a) of the five (RULING_14 REFERRAL D clause 3).
UNGATED_POOL_SOURCES = ("random", "top_magnitude", "hand_picked")

#: Condition (b): the label. Never "TIER_J-as-a-result", because a control is
#: an object MEANT TO FAIL, and calling it a tier invites its failure to be
#: read as a group finding and its success as a group result.
UNGATED_CONTROL_LABEL = "control_ungated_set"

#: All five conditions, carried on every ungated control record so the reader
#: of the record has them without the ruling. The architect ENCOURAGES this
#: arm: the group claim is considerably stronger with an ungated arm that
#: failed to steer than without one.
UNGATED_CONTROL_CONDITIONS = (
    "(a) the pool's source is NAMED in the record and is NOT A -- random, top-magnitude or "
    "hand-picked",
    "(b) it is labelled control_ungated_set, NEVER TIER_J-as-a-result: a control is an object MEANT "
    "TO FAIL, and calling it a tier invites its failure to be read as a group finding and its "
    "success as a group result",
    "(c) it carries NO coverage certificate and NO concept name",
    "(d) its outputs may be called 'a direction set that changes the text' and NEVER 'the cheese "
    "features'",
    "(e) it is NEVER merged with, pooled into, or tabulated in the same column as a TIER_C or "
    "TIER_S result",
)

#: What the record must say when no ungated arm was run. RULING_14 REFERRAL D
#: clause 5: confirming the TIER_J refusal creates the hazard that a lane
#: cites the ruling to omit the control entirely. Whether the arm is
#: affordable is an allocation question; whether its absence must be STATED is
#: not, and it must be.
UNGATED_ARM_NOT_EXERCISED = (
    "NOT EXERCISED. No ungated control arm accompanies this selection. Any claim that a group's "
    "effect is attributable to the CONCEPT rather than to intervention-at-that-arity requires an "
    "arm that intervenes at that arity WITHOUT the gates; absent it, this is stated rather than "
    "left blank, and a blank would read as NOT APPLICABLE instead of NOT CHECKED."
)

#: THE TWO CLAIM FORMS, and they are the only two (RULING_14 REFERRAL A
#: clause 3). Carried in every record so that the shape of a permitted
#: sentence travels with the numbers that would go into it.
PERMITTED_CLAIM_FORMS = (
    "EXISTENTIAL -- 'a minimum-cardinality cover of arity k, realisation [indices], jointly steers "
    "concept X under the declared tier', with the EXACT realisation population reported alongside",
    "BOUNDED NEGATIVE -- 'n of N realisations tested (N exact, from the multiplicities), no "
    "success', where n AND N both travel IN THE SENTENCE",
)

#: REFUSED sentence shapes, each of which asserts a universal that no budget
#: can measure. Recorded next to the permitted forms because the prohibition
#: is only useful where the numbers are.
REFUSED_CLAIM_FORMS = (
    "'minimum-cardinality covers do not steer this concept' -- UNREACHABLE BY CONSTRUCTION, not "
    "merely unproven",
    "'the minimum-cardinality cover for X' or 'the group failed' -- a universal over a population "
    "that was sampled once",
    "the unqualified word 'minimal' for the ENUMERATED object, which names a strictly larger set "
    "than the one enumerated",
)

#: WHICH POPULATION `N` COUNTS. RULING_14 REFERRAL C clause 7: if the wider
#: irredundant arm is ever opened, `N` changes and every previously reported
#: bounded-negative denominator becomes a denominator over a proper subset. A
#: denominator whose population is unstated is the vacuity defect in its
#: original form.
REALISATION_POPULATION = (
    "N counts feature-level realisations of MINIMUM-CARDINALITY covers ONLY. It does NOT count "
    "realisations of larger irredundant covers, which are pre-declared as a permitted widening on "
    "exhaustion and are NOT in this population. If that arm is opened, N changes and every earlier "
    "bounded-negative claim's denominator becomes a denominator over a proper subset."
)

#: THE SECOND RECALL BOUND, named because RULING_14 REFERRAL C clause 2
#: requires it named rather than left implicit. It sits BESIDE the pool bound,
#: not inside it.
SECOND_RECALL_BOUND = (
    "SECOND RECALL BOUND, beside the pool bound and not inside it: the enumeration is over "
    "MINIMUM-CARDINALITY covers, which are all irredundant, but NOT over all irredundant covers -- "
    "irredundance permits arities strictly above the minimum and up to |C|. So the enumerated "
    "object is a SUBSET of the object 'minimal under removal' describes. Nothing is overstated as "
    "to CLAIM; the SEARCH is bounded and that is a consequence, not a free choice. PRE-DECLARED "
    "(RULING_14 REFERRAL C clause 6): larger irredundant covers come INTO SCOPE if and only if the "
    "minimum-cardinality arm is exhausted without success under the pre-registered stopping rule, "
    "and the two arms are REPORTED SEPARATELY and NEVER MERGED."
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
#: individually clear [tier], this MINIMUM-CARDINALITY cover jointly steers the
#: concept'. PROHIBITED: 'these are the features needed'.
#:
#: REWORDED under RULING_14 REFERRAL C clause 3, the instrument-structure rule
#: applied to LANGUAGE: the word "minimal", unqualified, asserts the removal
#: property AND implies the enumeration ranged over all covers holding it. The
#: second half is false of what is emitted. So the enumerated object is "the
#: minimum-cardinality covers"; the verified per-group property is
#: "irredundant / minimal under removal"; and the two phrases may not be
#: substituted for one another anywhere.
POOL_BOUND_CAVEAT = (
    "POOL-BOUNDED BY CONSTRUCTION: this is a MINIMUM-CARDINALITY cover AMONG features that "
    "individually clear the declared tier's membership bar. It is NOT a claim that these are the "
    "features needed, and the recall caveat is permanent -- features outside the pool are not "
    "excluded by this result."
)

#: THE STOPPING RULE, pre-registered by RULING_14 REFERRAL A clause 6 BEFORE
#: any causal arm runs, so that it cannot be chosen after seeing an outcome.
#: Carried here because the selector's record is where the `n` and `N` a
#: bounded-negative sentence needs are computed.
STOPPING_RULE_PRE_REGISTERED = (
    "(a) spend proceeds realisation by realisation in the declared order; (b) the FIRST SUCCESS "
    "terminates the concept's group arm and licenses the EXISTENTIAL claim, because a witness is a "
    "witness and further spend buys no additional claim form; (c) a failure terminates NOTHING and "
    "licenses only the bounded-negative form with n and N; (d) there is NO n at which the "
    "bounded-negative becomes universal; (e) the ceiling on n is a COST bound owned by whoever "
    "holds the allocation, is not the architect's and not this file's, and must be declared before "
    "the arm runs so that a stop is never read as an exhaustion."
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
    #: WHAT THE MATRIX'S OWN PROVENANCE DOES TO THIS FILE'S HEADLINE NUMBER,
    #: as CORRECTED by the RULING_14 ADDENDUM at sequence 43.
    #:
    #: This file previously carried the caveat that `A` is screened at
    #: `threshold - screen_epsilon` and is therefore a SUPERSET of the
    #: plain-float admissible set, so `minimum_arity` is a LOWER BOUND. The
    #: arithmetic is right and the architect withdrew the conclusion it had
    #: drawn from it after measuring the numbers: `screen_epsilon` is 1e-9
    #: against a G-A lattice step of 1/600 = 1.7e-3, so the band cannot
    #: contain an ATTAINABLE value at all -- only a feature whose true
    #: rational EQUALS the bar and whose float64 evaluation fell a few ulps
    #: short. The screened form is therefore the FAITHFUL one and the plain
    #: float `>=` is the form carrying the artifact. The scan now decides the
    #: gate by LATTICE-INTEGER comparison where the counts are known, which
    #: removes the epsilon rather than bounding it.
    #:
    #: What survives, with a better reason: the band as an INDEX LIST. It
    #: names the features whose admissibility is FLOAT-REPRESENTATION-
    #: CONTINGENT, and only a list -- never the count that used to be all
    #: this file had -- can decide whether THIS group has such a member.
    screen_provenance: dict = field(default_factory=dict)
    #: Per cell, per gate, THE INDICES of the float-representation-contingent
    #: features (`admissible under the screen, not under the plain float`).
    #: `None` means the record predates the field or the caller handed over a
    #: bare matrix: UNKNOWN, which is a finding, never a blank.
    screen_band_indices_by_cell: dict[str, dict[str, tuple[int, ...]]] | None = None
    #: The spend order, ELECTED BEFORE THE SELECTOR RUNS. It lives on the
    #: PROBLEM rather than on `select_groups` deliberately: RULING_14 permits
    #: the depth order only as an election made in advance, and a keyword on
    #: the search call could be chosen after seeing a result.
    spend_order: str = SPEND_ORDER_ARBITRARY

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
        if TIER_J in self.tiers_declared_in_advance:
            raise TierWideningIntoTierJRefused(
                f"TIER_J appears in tiers_declared_in_advance={self.tiers_declared_in_advance!r}, "
                f"which declares it as a WIDENING DESTINATION from a gated tier. REFUSED. "
                f"RULING_14 REFERRAL D clause 4 closes this hole in RULING_13's own clause 7: "
                f"TIER_S -> TIER_C is a widening from a stronger GATE to a weaker GATE and both are "
                f"gates, so it is evidence to less evidence; TIER_C -> TIER_J is a step from "
                f"EVIDENCE TO NO EVIDENCE, and no advance declaration can license it, because what "
                f"makes a widening safe is that the destination still supports the claim. An empty "
                f"TIER_C is a REPORTABLE NULL. An ungated set is admissible and encouraged as a "
                f"labelled control arm -- build it with UngatedControlSet, which does not pass "
                f"through this field at all."
            )
        if self.tier not in self.tiers_declared_in_advance:
            raise TierNotDeclared(
                f"tier {self.tier!r} is not in tiers_declared_in_advance="
                f"{self.tiers_declared_in_advance!r}. RULING_13 Q1 clause 7: the tier is DECLARED "
                f"BEFORE SELECTION, and widening (e.g. TIER_S -> TIER_C after seeing TIER_S empty) "
                f"is permitted ONLY if both were declared in advance."
            )
        if self.spend_order not in SPEND_ORDERS:
            raise GroupSelectionError(
                f"spend_order must be one of {SPEND_ORDERS}, got {self.spend_order!r}. The default "
                f"is declared-arbitrary and claims nothing; the depth order must be ELECTED IN "
                f"ADVANCE and still claims nothing."
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

    def depth_vector(self, group: Iterable[int]) -> tuple[int, ...]:
        """`d(G)[c] = |{f in G : A[f, c] = 1}|`, computed from the per-cell
        SUPPORT and never collapsed here.

        `cov(G)` is the SIGN of this vector, so the coverage certificate is a
        collapse of it and not the reverse. Recorded for every emitted class
        whether or not the depth order is elected -- RULING_14 REFERRAL A
        clause 7 requires it recorded precisely because whether depth predicts
        causal robustness is what the first causal grid could answer and
        cannot answer retroactively. NO SCALAR IS RETURNED. Collapsing to a
        min here would put a depth scalar where the ruling permits only the
        coverage vector and `|cov(G)|`."""
        members = set(int(f) for f in group)
        return tuple(
            len(members & self.admissible_by_cell[cell]) for cell in self.cell_order
        )

    def band_bits_of(self, group: Iterable[int]) -> dict:
        """IS THIS GROUP'S ADMISSIBILITY FLOAT-REPRESENTATION-CONTINGENT.

        THE DEFECT THIS METHOD EXISTS TO REMOVE. The scan used to record only
        `features_within_screen_epsilon_band`, an int COUNT per cell and per
        gate. A count bounds the POPULATION that the screen slack could have
        admitted and says NOTHING about the group being spent on, so the
        honesty caveat this file attached to every record travelled while
        being unable to be exercised on the object it qualified -- a qualifier
        that cannot fail, which is this sprint's named defect class appearing
        inside the correction written to prevent an instance of it. RULING_14
        found that, and its ADDENDUM kept the repair with a sharper reason:
        the band names the features whose true rational EQUALS the bar and
        whose float64 evaluation mis-rounded below it.

        DECIDABLE, not bounded: with the index list in hand the answer for a
        SPECIFIC group is exact. `decidable` is False only when the indices
        were never recorded, and then the reason is stated rather than the
        field left blank."""
        members = sorted(set(int(f) for f in group))
        if self.screen_band_indices_by_cell is None:
            return {
                "decidable": False,
                "why_not": (
                    "the per-cell per-gate BAND INDICES are absent from this problem's provenance, "
                    "so whether a member of this group is float-representation-contingent is "
                    "UNKNOWN. UNKNOWN is a finding; the count that used to stand here could bound "
                    "the population and never decide this group."
                ),
                "contingent_bits": [],
                "group_is_float_representation_contingent": None,
            }
        bits = [
            {"feature_index": member, "cell": cell, "gate": gate}
            for cell in self.cell_order
            for gate, indices in sorted(self.screen_band_indices_by_cell.get(cell, {}).items())
            for member in members
            if member in set(indices)
        ]
        return {
            "decidable": True,
            "method": (
                "each member checked against the recorded band INDEX LIST for every cell and every "
                "gate limb; an empty list is a DECIDED negative, not an unmeasured one"
            ),
            "contingent_bits": bits,
            "group_is_float_representation_contingent": bool(bits),
        }

    def assert_slot_carries_no_within_slot_preference(self, pattern: int) -> None:
        """MEASURED, NOT ASSUMED: every feature in a pattern slot is
        BIT-IDENTICAL in `A`.

        RULING_14 REFERRAL A clause 9 and the addendum's Q3: between classes
        `A` carries information, and WITHIN a slot it carries NONE, so a
        within-slot preference on scientific grounds is an instrument with no
        resolution at the level of its own claim and is REFUSED. That argument
        rests on the slot members being indistinguishable in `A`, which is
        true by the definition of the slot -- and this file is not permitted to
        rest a refusal on a property it never checked. So the property is
        re-derived from the per-cell support, independently of
        `_patterns_from_support` that produced the slot."""
        members = self.pattern_to_features.get(pattern, ())
        for member in members:
            rebuilt = self.pattern_of(member)
            if rebuilt != pattern:
                raise GroupSelectionError(
                    f"feature {member} sits in pattern slot {self.format_mask(pattern)} but its "
                    f"per-cell support gives {self.format_mask(rebuilt)}. The slot is supposed to "
                    f"make its members BIT-IDENTICAL in A, which is the whole ground for refusing a "
                    f"within-slot preference; if that fails the refusal is unfounded."
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
    spend_order: str = SPEND_ORDER_ARBITRARY,
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
            # WHICH COMPARISON DECIDED THIS SUPPORT. Absent from records
            # written before the lattice comparison landed, and then the
            # answer is UNKNOWN rather than an assumed float screen.
            "gate_comparison_basis": record.get(
                "gate_comparison_basis",
                "UNKNOWN: this record predates the gate_comparison_basis field, so whether the "
                "screened float or the lattice-integer comparison decided it is not recorded here",
            ),
            "lattice_denominator_by_cell_and_gate": record.get(
                "lattice_denominator_by_cell_and_gate"
            ),
            "gate_disagreement_count_by_cell": record.get("gate_disagreement_count_by_cell"),
        },
        screen_band_indices_by_cell=_band_indices_from_record(record, cell_order),
        spend_order=spend_order,
    )


def _band_indices_from_record(record: Mapping, cell_order: Sequence[str]) -> dict | None:
    """The per-cell per-gate BAND INDEX LIST, or `None` for UNKNOWN.

    `None` and an empty list are DIFFERENT FINDINGS and this function keeps
    them apart: `None` means the record predates the field, so whether any
    group is float-representation-contingent was never measured; an empty list
    per cell means it WAS measured and nothing sits at the bar, which under
    the lattice comparison is the expected result and is reported rather than
    dropped."""
    indices = record.get("features_within_screen_epsilon_band_indices")
    if not isinstance(indices, Mapping):
        return None
    return {
        cell: {
            str(gate): tuple(int(f) for f in (values or ()))
            for gate, values in sorted((indices.get(cell) or {}).items())
        }
        for cell in cell_order
    }


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
    spend_order: str = SPEND_ORDER_ARBITRARY,
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
                "record that carries the screen epsilon and its band, so which comparison decided "
                "A, and whether any bit of it is float-representation-contingent, are UNKNOWN here "
                "rather than zero."
            ),
            "features_within_screen_epsilon_band": None,
            "gate_comparison_basis": (
                "UNKNOWN: a bare boolean matrix carries no record of the comparison that produced it"
            ),
            "lattice_denominator_by_cell_and_gate": None,
            "gate_disagreement_count_by_cell": None,
        },
        # UNKNOWN, and the distinction matters: `None` here means never
        # measured, where an empty dict would mean measured-and-empty.
        screen_band_indices_by_cell=None,
        spend_order=spend_order,
    )


def load_problems_from_grid(
    path: str | Path,
    *,
    tier: str,
    tiers_declared_in_advance: Sequence[str],
    concept_ids: Sequence[str] | None = None,
    spend_order: str = SPEND_ORDER_ARBITRARY,
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
            spend_order=spend_order,
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
    emitted representative can never read as 'the only one'.

    A CLASS IS NOT A TESTABLE UNIT, and this dataclass is where that has to
    be visible. A pattern-level equivalence class is an equivalence class FOR
    COVERAGE ONLY: two features with the same pattern are interchangeable in
    `cov(G)` and are NOT interchangeable under intervention, because they are
    different directions in the residual stream. So the causal arm tests ONE
    REALISATION and learns about ONE REALISATION, and
    `realisation_multiplicity` is the denominator that has to travel in any
    sentence naming this group (RULING_14 REFERRAL A clauses 2, 3 and 10).

    THE SCHEMA REFUSES AN UNGATED SET. `pool_source` must be `POOL_SOURCE_A`
    and `tier` must not be TIER_J, checked at construction, because a
    tautological certificate is indistinguishable from an earned one once it
    has been serialised through this shape."""

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
    #: `d(G)[c]`, per cell, never collapsed. Recorded whether or not the depth
    #: spend order was elected.
    depth: tuple[int, ...] = ()
    #: Whether THIS group's members sit in the screen band -- decidable, not
    #: bounded. See `CoverageProblem.band_bits_of`.
    epsilon_band: dict = field(default_factory=dict)
    #: Defaulted so that the schema check has something to check, and checked
    #: so that the default cannot be quietly overridden with an ungated pool.
    pool_source: str = POOL_SOURCE_A

    def __post_init__(self) -> None:
        # THE SCHEMA-LAYER REFUSAL (RULING_14 REFERRAL D clause 2). Refusing
        # at the pool layer, which `CoverageProblem` already does, is
        # necessary and insufficient: emitted through this shape, an ungated
        # set's coverage_vector reads 1^|C|, complete reads true and
        # minimality_under_removal reads true, and no reader can tell a
        # tautological certificate from an earned one. So an ungated set
        # cannot be EXPRESSED as a group.
        if self.tier == TIER_J:
            raise UngatedSetCannotWearACertificate(
                f"a group record was constructed at tier {TIER_J}, which requires NO gate of its "
                f"members. TIER_J is not a tier OF THIS INSTRUMENT: A is by definition the gate "
                f"record, so a tier requiring no gate has no representation in it. Emitted through "
                f"this shape the certificate would read complete=true with cov = 1^|C| and would be "
                f"INDISTINGUISHABLE FROM AN EARNED ONE. Use UngatedControlSet, which carries no "
                f"coverage certificate and no concept name."
            )
        if self.pool_source != POOL_SOURCE_A:
            raise UngatedSetCannotWearACertificate(
                f"a group record was constructed from pool_source {self.pool_source!r}, which is not "
                f"A. A coverage certificate over a pool that is not the gate record is a check that "
                f"cannot fail. Permitted pool source: {POOL_SOURCE_A!r}."
            )

    def to_record(self) -> dict:
        return {
            "tier": self.tier,
            "concept_id_or_label": self.concept_id,
            "pool_source": self.pool_source,
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
            "realisation_population_this_denominator_counts": REALISATION_POPULATION,
            "a_class_is_not_a_testable_unit": (
                "the causal arm tests ONE REALISATION and learns about ONE REALISATION: two features "
                "in the same pattern slot are interchangeable in cov(G) and are NOT interchangeable "
                "under intervention, being different directions in the residual stream. A success on "
                "a realisation is a WITNESS; a failure is a statement about that realisation and "
                "about nothing else."
            ),
            "members_available_per_slot": list(self.members_available_per_slot),
            "minimality_under_removal": self.minimality,
            # PER CELL, NEVER COLLAPSED, and never a headline. Any scalar
            # derived from it belongs only inside a spend-order justification.
            "per_cell_depth_vector_d_G": list(self.depth),
            "per_cell_depth_vector_definition": DEPTH_DEFINITION,
            "per_cell_depth_vector_binds": DEPTH_BINDS,
            "screen_band_membership_of_THIS_group": self.epsilon_band,
            "single_feature_not_a_group_of_one": self.arity == 1,
        }


#: The tie-break, pre-registered here and deterministic (RULING_13 Q1 clause
#: 8 requires one 'ending in ascending feature index'). It is ONLY a
#: reporting order and a canonical representative: EVERY minimum cover is
#: emitted at the pattern level and every class carries its exact
#: multiplicity, so nothing is selected away by it. Deliberately carries NO
#: scientific preference -- the smallest feature index has no property that
#: recommends it -- because a preference among equally-minimum-cardinality groups is not
#: ruled, and inventing one here would smuggle a selection rule into a
#: formatting decision. That gap is named in the report as a referral.
CANONICAL_REALISATION_RULE = (
    "within each pattern slot take the LOWEST feature index; order groups lexicographically by the "
    "ascending feature-index tuple. Reporting order and canonical representative ONLY -- not a "
    "preference among equally-minimum-cardinality groups. RULING_14 REFERRAL A clause 9 PROVED why "
    "no such preference is available WITHIN a slot: the candidates are BIT-IDENTICAL in A by the "
    "definition of the slot, so no function of A can order them, and a within-slot rule would need "
    "a criterion this file deliberately does not read. Declared-arbitrary, deterministic, "
    "pre-registered, and claiming nothing -- which is what makes it sufficient."
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
    #: Which order the classes are emitted in, and therefore the order the
    #: causal arm would spend in. Declared-arbitrary by default.
    spend_order: str = SPEND_ORDER_ARBITRARY
    #: What the depth election did or did not read, recorded either way.
    spend_order_justification: dict = field(default_factory=dict)
    #: RULING_14 REFERRAL C clause 5: what the minimum-cardinality
    #: restriction COSTS, computed rather than argued, and UNKNOWN rather than
    #: blank when the budget refuses.
    irredundant_census: dict = field(default_factory=dict)
    #: RULING_14 REFERRAL D clause 5: absent, this says NOT EXERCISED.
    ungated_control_arm: str = UNGATED_ARM_NOT_EXERCISED

    def __post_init__(self) -> None:
        # THE SCHEMA-LAYER REFUSAL, at the result shape as well as the group
        # shape. A result object carrying a coverage certificate, a status of
        # COMPLETE_COVER and `all_groups_complete` is a record shape carrying a
        # certificate, so RULING_14 REFERRAL D clause 2's bind reaches it too.
        if self.tier == TIER_J:
            raise UngatedSetCannotWearACertificate(
                f"a GroupSelectionResult was constructed at tier {TIER_J}. This shape carries a "
                f"coverage certificate (status, best_achievable_coverage, all_groups_complete), and "
                f"an ungated set may not be expressed through any shape that carries one. TIER_J is "
                f"not a tier of this instrument; an ungated set is admissible and ENCOURAGED as a "
                f"labelled negative control -- see UngatedControlSet."
            )
        if self.spend_order not in SPEND_ORDERS:
            raise GroupSelectionError(
                f"spend_order must be one of {SPEND_ORDERS}, got {self.spend_order!r}"
            )

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
            # RULING_14 REFERRAL B clause 3 PROVED MORE THAN THIS FILE HAD
            # CLAIMED, and said the stronger statement should be the recorded
            # one. The derivation this file made was: every IRREDUNDANT cover
            # of |C| cells has at most |C| members. The step it did not take:
            # EVERY COVER CONTAINS AN IRREDUNDANT SUBCOVER, obtained by
            # dropping redundant members one at a time. Therefore if no cover
            # exists at arity <= |C|, NO COVER EXISTS AT ANY ARITY -- the null
            # under the derived ceiling is UNCONDITIONAL OVER ARITY, not merely
            # not-arity-limited. It is available for free and is now recorded.
            "null_is_unconditional_over_arity": (
                self.search.minimum_arity is None
                and self.search.k_max >= self.n_cells
            ),
            "null_is_unconditional_over_arity_proof": (
                "every cover CONTAINS an irredundant subcover (drop redundant members one at a "
                "time), and every irredundant cover of |C| cells has at most |C| members (each "
                "member holds a cell no other member holds). So no cover at arity <= |C| implies NO "
                "COVER AT ANY ARITY. This holds only while the ceiling is >= |C|; under a "
                "caller-supplied smaller cost bound the null is ceiling-limited instead."
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
            "spend_order": self.spend_order,
            "spend_order_justification": self.spend_order_justification,
            "stopping_rule_pre_registered": STOPPING_RULE_PRE_REGISTERED,
            "permitted_claim_forms": list(PERMITTED_CLAIM_FORMS),
            "refused_claim_forms": list(REFUSED_CLAIM_FORMS),
            "realisation_population_this_denominator_counts": REALISATION_POPULATION,
            "second_recall_bound": SECOND_RECALL_BOUND,
            "cost_of_the_minimum_cardinality_restriction": self.irredundant_census,
            "ungated_control_arm": self.ungated_control_arm,
            "minimum_is_with_respect_to_A_AS_RECORDED": {
                "why": (
                    "A is decided per cell by the three-gate conjunction. Where the scan supplied "
                    "lattice denominators the comparison is LATTICE-INTEGER and carries no epsilon "
                    "at all; where it did not, the gate is the screened float at "
                    "threshold - screen_epsilon, which the RULING_14 ADDENDUM established is the "
                    "FAITHFUL float form rather than a loosened one -- the epsilon is ~1.7e6 times "
                    "finer than one lattice step, so it can only re-admit a feature whose true "
                    "rational EQUALS the bar and whose float64 mis-rounded below it. The band "
                    "INDICES, not the count, are what decide whether a GIVEN group has such a "
                    "member; see each group's screen_band_membership_of_THIS_group."
                ),
                "withdrawn_clause": (
                    "This file briefly carried the sequence-42 clause that a plain-float "
                    "`values >= threshold` be emitted as 'exact A' and HEADLINED over the screened "
                    "form. The architect WITHDREW that clause at sequence 43 after measuring the "
                    "lattice step, on the ground that it 'would have made the record look more "
                    "rigorous while being LESS faithful'. It is not implemented, and the withdrawal "
                    "is recorded rather than silently absorbed."
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
                "second_recall_bound": SECOND_RECALL_BOUND,
                "no_causal_evidence": NO_CAUSAL_EVIDENCE_CAVEAT,
                "a_class_is_not_a_testable_unit": (
                    "the universal null over minimum-cardinality covers is UNREACHABLE BY "
                    "CONSTRUCTION at any budget, because the causal arm's unit is a REALISATION and "
                    f"this concept's population is {self.feature_level_solution_count} of them. Only "
                    "existential and bounded-negative claims exist; see permitted_claim_forms."
                ),
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


#: The verdict states an unreachable cell can be given, each naming WHAT WAS
#: FOUND. `CEILINGED_ON_THIS_CORPUS_WITHIN_RESAMPLING_REACH` is the fourth,
#: REQUIRED by the RULING_14 ADDENDUM (sequence 43) on the first real data.
VERDICT_UNDISAMBIGUATED = "UNDISAMBIGUATED_NO_PER_CELL_CEILINGS_SUPPLIED"
VERDICT_CONJUNCTION_FAILURE = "CONJUNCTION_FAILURE_NOT_A_SINGLE_LIMB_CEILING"
VERDICT_ENCODING_ONE_LIMB = "ENCODING_PROPERTY_FOR_THE_FAILING_LIMB"
VERDICT_ENCODING_ALL_LIMBS = "ENCODING_PROPERTY_ALL_LIMBS_BELOW_BAR"
VERDICT_CEILINGED_WITHIN_RESAMPLING_REACH = "CEILINGED_ON_THIS_CORPUS_WITHIN_RESAMPLING_REACH"


def _resampling_reach(deficit_in_steps: float | None, n_positives: int | None) -> bool | None:
    """Is a sub-bar ceiling's deficit comparable to the corpus's own sampling
    variability? `None` when the inputs to decide it were not recorded.

    NOT A THRESHOLD, and the distinction is the whole reason this returns a
    comparison rather than a verdict. The architect set no bar: the state is
    entered by comparing a deficit MEASURED IN LATTICE STEPS against the
    POSITIVE COUNT, both of which are recorded quantities. One step in a mean
    of two sub-AUROCs is a single TIE-HALF in one of them; a full
    discordant-pair inversion moves the mean by TWO steps. So a deficit of `k`
    steps is `k/2` pair inversions out of `n_pos * n_neg` pairs, on a cell with
    `n_pos` positives -- and with `n_pos` in single figures, a handful of
    inversions is well inside what a resample of the positives could produce.

    The comparison implemented: the deficit is within reach when the number of
    pair inversions it represents does not exceed the number of positives. At
    the measured cheese instance -- 534/600 against a 540/600 bar, 6 steps, 3
    inversions, 10 positives -- that is TRUE, which is the case the state was
    added for. No number here is invented: `2` is the steps-per-inversion of
    the mean identity, and `n_positives` is measured."""
    if deficit_in_steps is None or n_positives is None or n_positives <= 0:
        return None
    return bool((float(deficit_in_steps) / 2.0) <= float(n_positives))


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
    the same record.

    A PER-LIMB MAXIMUM IS NEVER READ AS A CONJUNCTION, and the RULING_14
    ADDENDUM made this the decisive point rather than a caveat. Each per-cell
    ceiling is a maximum over features taken INDEPENDENTLY FOR ONE LIMB, and
    the property is that THE SAME FEATURE clears three limbs at once.
    `max(G-A) >= bar_A`, `max(G-B) >= bar_B` and `max(G-C) >= bar_C` can all
    hold with the argmaxes being three DIFFERENT features and NO feature
    clearing all three. So three per-limb maxima carry NO information about
    the conjunction: they can REFUTE admissibility in a cell (a limb below its
    bar admits nobody) and they can never ESTABLISH it. That asymmetry is why
    `CONJUNCTION_FAILURE_NOT_A_SINGLE_LIMB_CEILING` is a finding of its own,
    and the addendum names it the LEADING hypothesis for cheese's three
    non-ceilinged cells rather than a completeness item.

    AND A FOURTH STATE, required by the addendum on the first real numbers.
    `CEILINGED_ON_THIS_CORPUS_WITHIN_RESAMPLING_REACH` covers a cell whose
    full-space ceiling falls below the bar by a margin comparable to the
    corpus's own sampling variability. A maximum over 81,920 features does NOT
    reduce that uncertainty: every feature is scored against THE SAME
    positives and THE SAME negatives, so corpus-sampling error is COMMON MODE
    across features and does not average out in a maximum. What the state
    FORBIDS is the unqualified sentence 'the encoding cannot represent this
    concept in this cell'. What it PRESERVES is the operative consequence:
    `cov(G)[c] = 0` ON THIS CORPUS, which is the only corpus there is, so no
    complete cover exists here at any arity."""
    if not cells:
        return {}
    ceilings = problem.per_cell_ceilings or {}
    bars = {
        "separation_auroc": problem.thresholds_used.get("G_A_separation_auroc_min"),
        "fire_rate": problem.thresholds_used.get("G_B_fire_rate_min"),
        "near_miss_auroc": problem.thresholds_used.get("G_C_specificity_auroc_vs_near_miss_min"),
    }
    lattice = (problem.screen_provenance or {}).get("lattice_denominator_by_cell_and_gate") or {}
    gate_label = {"separation_auroc": "G-A", "fire_rate": "G-B", "near_miss_auroc": "G-C"}
    out: dict = {}
    for cell in cells:
        limbs: dict = {}
        # THE POSITIVE COUNT, DERIVED AND NOT ADDED AS A FIELD. `fire_rate` is
        # an integer count over the positives, so its lattice denominator IS
        # `n_positives` exactly (`fire_rate_lattice_denominator`). The number
        # the resampling-reach comparison needs is therefore already recorded,
        # and reading it from there beats adding a field to a shared file.
        n_positives = (lattice.get(cell) or {}).get("G-B")
        for quantity, bar in bars.items():
            summary = (ceilings.get(quantity) or {}).get("cells", {}).get(cell)
            ceiling = None
            if summary is not None:
                ceiling = summary.get(f"max_{quantity}", summary.get("max_separation_auroc"))
            denominator = (lattice.get(cell) or {}).get(gate_label[quantity])
            # THE DEFICIT IN LATTICE STEPS, which is the unit the addendum
            # reasons in. Available only where the denominator was recorded;
            # None otherwise, never guessed.
            deficit_steps = None
            if ceiling is not None and bar is not None and denominator:
                deficit_steps = float(bar) * float(denominator) - float(ceiling) * float(denominator)
                deficit_steps = round(deficit_steps, 6)
            limbs[quantity] = {
                "ceiling": ceiling,
                "frozen_bar": bar,
                "ceiling_clears_bar": (
                    None if ceiling is None or bar is None else bool(ceiling >= bar)
                ),
                "lattice_denominator": denominator,
                "deficit_in_lattice_steps": deficit_steps,
                "n_positives_behind_the_ceiling": n_positives,
                "n_positives_source": (
                    "DERIVED from this cell's G-B lattice denominator, which is the positive count "
                    "exactly, because a fire rate is an integer count over the positives"
                ),
                "deficit_within_corpus_resampling_reach": _resampling_reach(
                    deficit_steps if (deficit_steps or 0) > 0 else None, n_positives
                ),
                "a_maximum_is_not_a_conjunction": (
                    "this ceiling is a maximum over features taken INDEPENDENTLY for this limb. It "
                    "can REFUTE admissibility in this cell and can never ESTABLISH it, because the "
                    "three limbs' argmaxes may be three different features."
                ),
            }
        known = [v["ceiling_clears_bar"] for v in limbs.values()]
        within_reach = [
            v["deficit_within_corpus_resampling_reach"] for v in limbs.values()
            if v["ceiling_clears_bar"] is False
        ]
        if any(value is None for value in known):
            verdict = VERDICT_UNDISAMBIGUATED
            because = (
                "the per-cell full-space ceilings for this cell were not supplied, so this cell's "
                "emptiness is NOT disambiguated. Stated rather than guessed."
            )
        elif all(known):
            verdict = VERDICT_CONJUNCTION_FAILURE
            because = (
                "every limb's ceiling clears its own frozen bar in this cell, yet no single feature "
                "clears all three AT ONCE. This is neither of the two cases the ruling names for a "
                "one-limb failure, and is reported as its own finding rather than assimilated. Note "
                "what these ceilings CANNOT show: three per-limb maxima carry no information about a "
                "three-limb conjunction, because the argmaxes may be three different features. The "
                "architect names this the LEADING hypothesis where it arises, not a proven cause."
            )
        elif within_reach and all(value is True for value in within_reach):
            verdict = VERDICT_CEILINGED_WITHIN_RESAMPLING_REACH
            because = (
                "at least one limb's full-space ceiling sits BELOW its frozen bar, and the deficit "
                "measured IN LATTICE STEPS is comparable to what a resample of this cell's positives "
                "could move -- one step is a single tie-half and a full pair inversion is two steps. "
                "A maximum over the whole dictionary does NOT reduce this uncertainty: every feature "
                "is scored against the SAME positives and negatives, so corpus-sampling error is "
                "COMMON MODE and does not average out in a maximum. THEREFORE: cov(G)[this cell] = 0 "
                "ON THIS CORPUS -- the operative consequence is unchanged and no complete cover "
                "exists here at any arity -- but the sentence 'the encoding cannot represent this "
                "concept in this cell' is NOT supported. A POINT verdict. Settling it needs a "
                "resample or leave-one-positive-out over the positives, which needs PER-ITEM scores "
                "rather than the AUROC; whether those were retained is UNKNOWN here."
            )
        elif any(known):
            verdict = VERDICT_ENCODING_ONE_LIMB
            because = (
                "at least one limb's full-space ceiling sits BELOW its frozen bar in this cell, so "
                "no feature can be admissible here under this SAE at this layer -- a property of "
                "the encoding, not of the selection. The deficit is larger than this cell's "
                "resampling reach, or the positive count needed to judge that was not recorded."
            )
        else:
            verdict = VERDICT_ENCODING_ALL_LIMBS
            because = "no limb's ceiling reaches its frozen bar in this cell."
        out[cell] = {"verdict": verdict, "because": because, "limbs": limbs}
    return out


def _apply_spend_order(
    problem: CoverageProblem, candidates: Sequence[GroupCandidate]
) -> tuple[list[GroupCandidate], dict]:
    """Put the classes in the order the causal arm would spend in, and RECORD
    which order it was and what that order read.

    THE DEFAULT CLAIMS NOTHING AND READS NOTHING, and RULING_14 REFERRAL A
    clause 8 makes that pairing the general rule: an ordering that claims
    nothing may read nothing, and an ordering offered as a REASON TO PREFER
    one group must read the per-cell matrix AND BE DEMONSTRATED TO READ IT.
    The falsifier is the mutation test: add one admissibility bit to one
    member of an emitted class, leaving completeness and arity unchanged; the
    depth-elected order MUST change and the declared-arbitrary order MUST NOT.

    THE DEPTH ORDER IS NOT `min` AS A RANKER RETURNING BY THE BACK DOOR.
    RULING_13 refused `min` as a ranker on two grounds and neither reaches
    here: this orders GROUPS rather than features, so the
    anti-correlation-with-complementarity argument has no purchase; and the
    property being ordered -- survival of the coverage certificate when one
    admissibility bit turns out to be false -- IS CONJUNCTIVE OVER CELLS,
    exactly as survivorship is, which is the same reasoning that made `min`
    correct as a QUALIFIER. No bar is set on depth, so no threshold is
    created, and no depth scalar leaves this function's justification dict."""
    ordered = sorted(candidates, key=lambda g: g.feature_indices)
    if problem.spend_order == SPEND_ORDER_ARBITRARY:
        return ordered, {
            "order": SPEND_ORDER_ARBITRARY,
            "reads_the_per_cell_matrix": False,
            "claims": "NOTHING. It is deterministic, pre-registered and arbitrary by declaration.",
            "why_that_is_sufficient": (
                "an ordering that claims nothing may read nothing (RULING_14 REFERRAL A clause 8). "
                "Because only existential and bounded-negative claims are available, WHICH "
                "realisation is tested first cannot corrupt an inference -- it can only change the "
                "probability of finding a witness. The choice is a POWER question, not a VALIDITY "
                "one, so no threshold is needed and none is set."
            ),
            "depth_vectors_recorded_anyway": True,
            "rule": CANONICAL_REALISATION_RULE,
        }
    # ELECTED IN ADVANCE, on the problem, never as a keyword to the search.
    # `sorted(d)` ascending compared lexicographically DESCENDING: prefer the
    # class whose THINNEST cell is thickest. Ties fall back to the arbitrary
    # rule so the order stays total and deterministic.
    ordered = sorted(
        candidates,
        key=lambda g: (tuple(-value for value in sorted(g.depth)), g.feature_indices),
    )
    return list(ordered), {
        "order": SPEND_ORDER_DEPTH,
        "reads_the_per_cell_matrix": True,
        "criterion": (
            "classes ordered by the PER-CELL DEPTH VECTOR sorted ascending and compared "
            "lexicographically descending -- prefer the class whose THINNEST cell is thickest. "
            "Computed from admissible_feature_indices_by_cell, which is already emitted untruncated, "
            "so it needs no new scan field."
        ),
        "claims": (
            "NOTHING SCIENTIFIC. This is a POWER heuristic and a spend order. That depth predicts "
            "causal robustness is ARGUED and UNMEASURED."
        ),
        "binds": DEPTH_BINDS,
        "not_min_as_a_ranker_because": (
            "RULING_13 refused min AS A RANKER on two grounds, neither of which reaches here: this "
            "orders GROUPS not features, so the anti-correlation-with-complementarity argument has "
            "no purchase; and the ordered property -- survival of the coverage certificate when one "
            "admissibility bit turns out false -- is CONJUNCTIVE OVER CELLS, exactly as survivorship "
            "is, which is the same reasoning that made min correct as a QUALIFIER."
        ),
        "no_bar_is_set_on_depth": True,
        "depth_vectors_recorded_anyway": True,
    }


def _irredundant_census(
    problem: CoverageProblem, *, minimum_arity: int, target_mask: int, node_budget: int
) -> dict:
    """WHAT THE MINIMUM-CARDINALITY RESTRICTION COSTS, COMPUTED.

    RULING_14 REFERRAL C clause 5. The architect declined to require the larger
    enumeration now -- making the first real run hostage to an unbudgeted
    search would be motivated by nothing measured -- and required instead a
    COMPUTED statement of what the restriction costs: the number of distinct
    patterns present, and, when it fits the existing node budget, the count of
    pattern-level IRREDUNDANT covers above the minimum arity. If it does not
    fit, the field reads UNKNOWN and never blank, because a blank reads as NOT
    CHECKED rather than NOT APPLICABLE.

    The addendum sharpens why the number is worth having: if the per-cell
    clearing sets are PAIRWISE DISJOINT then every cover is a partition,
    minimum arity equals the number of cells, depth is 1 everywhere, and the
    maximum irredundant arity EQUALS the minimum -- total disjointness
    COLLAPSES the distinction rather than widening it. So a count of zero here
    is a real finding about the overlap structure and not an absence."""
    patterns = tuple(problem.pattern_to_features)
    census: dict = {
        "distinct_patterns_present": len(patterns),
        "minimum_arity": minimum_arity,
        "maximum_irredundant_arity_possible": problem.n_cells,
        "what_this_measures": (
            "every minimum-cardinality cover is irredundant; NOT every irredundant cover is "
            "minimum-cardinality. So the enumerated object is a SUBSET of what 'minimal under "
            "removal' describes, and this counts the part left out."
        ),
        "widening_is_pre_declared_not_post_hoc": SECOND_RECALL_BOUND,
    }
    nodes = 0
    counts: dict[int, int] = {}
    try:
        for arity in range(minimum_arity + 1, problem.n_cells + 1):
            found = 0
            for combo in _combinations(patterns, arity):
                nodes += 1
                if nodes > node_budget:
                    raise SearchBudgetExceeded("irredundant census exceeded the node budget")
                merged = 0
                for pattern in combo:
                    merged |= pattern
                if (merged & target_mask) != target_mask:
                    continue
                # IRREDUNDANT: every member holds at least one cell no other
                # member of the same cover holds.
                irredundant = True
                for pattern in combo:
                    others = 0
                    for other in combo:
                        if other != pattern:
                            others |= other
                    if (pattern & target_mask & ~others) == 0:
                        irredundant = False
                        break
                if irredundant:
                    found += 1
            counts[arity] = found
        census["pattern_level_irredundant_covers_above_the_minimum"] = {
            str(arity): value for arity, value in counts.items()
        }
        census["pattern_level_irredundant_covers_above_the_minimum_total"] = sum(counts.values())
        census["census_nodes"] = nodes
    except SearchBudgetExceeded:
        # REFUSES rather than degrades, and says UNKNOWN rather than nothing.
        census["pattern_level_irredundant_covers_above_the_minimum"] = "UNKNOWN"
        census["pattern_level_irredundant_covers_above_the_minimum_total"] = "UNKNOWN"
        census["census_nodes"] = nodes
        census["why_unknown"] = (
            f"the irredundant census exceeded the {node_budget}-node budget at "
            f"{len(patterns)} distinct patterns. UNKNOWN is a finding: the budget REFUSES rather "
            f"than degrading to an estimate, and a blank here would read as NOT APPLICABLE."
        )
    return census


def select_groups(
    problem: CoverageProblem,
    *,
    k_max: int | None = None,
    members_listed_per_slot: int = DEFAULT_MEMBERS_LISTED_PER_SLOT,
    max_emitted_groups: int | None = None,
    node_budget: int = DEFAULT_NODE_BUDGET,
    #: A SEPARATE cost bound for the irredundant census, because it is a
    #: different search over a larger space and starving it must not starve the
    #: cover enumeration. Exceeding this one yields UNKNOWN in the census;
    #: exceeding `node_budget` still RAISES, because a cover search that
    #: degraded would put the word minimum on a result that had not earned it.
    census_node_budget: int | None = None,
) -> GroupSelectionResult:
    """Turn `A[f, c]` into the COMPLETE set of MINIMUM-CARDINALITY candidate groups.

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
            spend_order=problem.spend_order,
            spend_order_justification=_apply_spend_order(problem, ())[1],
            irredundant_census={
                "distinct_patterns_present": 0,
                "pattern_level_irredundant_covers_above_the_minimum": 0,
                "why": "there is no cover at any arity: the pool is empty.",
            },
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
            spend_order=problem.spend_order,
            spend_order_justification=_apply_spend_order(problem, ())[1],
            irredundant_census={
                "distinct_patterns_present": search.distinct_patterns,
                "pattern_level_irredundant_covers_above_the_minimum": 0,
                "why": (
                    "no cover of the reachable target exists at or below the recorded ceiling, so "
                    "there is nothing above a minimum arity to count -- there is no minimum arity."
                ),
            },
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
        # ASSERTED, NOT ASSUMED. RULING_14 REFERRAL A clause 9 refuses a
        # within-slot preference on the ground that the slot's members are
        # BIT-IDENTICAL in A. That ground is checked here, per slot, against
        # the per-cell support -- a refusal resting on an unchecked property
        # would be the defect class in the argument rather than the code.
        for pattern in slots:
            problem.assert_slot_carries_no_within_slot_preference(pattern)
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
                # RECORDED EITHER WAY, whether or not the depth order was
                # elected: whether depth predicts causal robustness is what
                # the first causal grid could answer and cannot answer
                # retroactively.
                depth=problem.depth_vector(canonical),
                # DECIDABLE FOR THIS GROUP, not bounded for the population.
                epsilon_band=problem.band_bits_of(canonical),
            )
        )

    candidates, spend_justification = _apply_spend_order(problem, candidates)
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
        spend_order=problem.spend_order,
        spend_order_justification=spend_justification,
        irredundant_census=_irredundant_census(
            problem,
            minimum_arity=search.minimum_arity,
            target_mask=target,
            node_budget=node_budget if census_node_budget is None else int(census_node_budget),
        ),
    )
    assert_not_vacuous(result)
    return result


@dataclass(frozen=True)
class UngatedControlSet:
    """AN UNGATED SET, ADMISSIBLE AND ENCOURAGED -- as a NEGATIVE CONTROL and
    as nothing else.

    RULING_14 REFERRAL D clause 3. Confirming that TIER_J cannot be
    constructed from `A` creates a hazard the architect named in the same
    breath: a lane can now cite the ruling to omit an ungated arm entirely,
    and it should not. "Does any direction set of this arity change the text?"
    is a real and necessary question, an ungated set is the right instrument
    for it, and the group claim is CONSIDERABLY STRONGER with an ungated arm
    that failed to steer than without one.

    THIS IS NOT A GROUP AND CANNOT BECOME ONE. It carries no coverage vector,
    no `complete` flag, no minimality record and no concept name, because a
    control is an object MEANT TO FAIL: calling it a tier invites its failure
    to be read as a group finding and its success as a group result. All five
    of the architect's conditions are enforced here rather than documented --
    (a) the pool source is named and is not `A`; (b) the label is fixed; (c)
    no certificate and no concept name; (d) the permitted sentence is carried
    verbatim; (e) merging with a gated tier RAISES, see
    `assert_not_merged_with_gated`."""

    label: str
    pool_source: str
    feature_indices: tuple[int, ...]
    arity: int
    #: How the pool was drawn, in enough detail to be reproduced. Required:
    #: naming the SOURCE without saying how it was drawn is a stated absence
    #: pretending to be a statement.
    pool_construction: str
    n_features_available: int | None = None

    def __post_init__(self) -> None:
        if self.label != UNGATED_CONTROL_LABEL:
            raise UngatedSetCannotWearACertificate(
                f"an ungated set must be labelled {UNGATED_CONTROL_LABEL!r}, got {self.label!r}. "
                f"Condition (b): NEVER TIER_J-as-a-result. A control is an object MEANT TO FAIL, and "
                f"a tier label invites its failure to be read as a group finding and its success as "
                f"a group result."
            )
        if self.pool_source not in UNGATED_POOL_SOURCES:
            raise UngatedSetCannotWearACertificate(
                f"pool_source must be one of {UNGATED_POOL_SOURCES} and must NOT be A, got "
                f"{self.pool_source!r}. Condition (a): the pool's source is NAMED in the record and "
                f"is not the gate record. A set drawn from A is a group and belongs in "
                f"GroupCandidate; a set drawn from anywhere else may never carry a certificate."
            )
        if not self.pool_construction.strip():
            raise UngatedSetCannotWearACertificate(
                "pool_construction is empty. Naming the source without saying how the pool was drawn "
                "is a stated absence wearing the clothes of a statement."
            )
        if not self.feature_indices:
            raise UngatedSetCannotWearACertificate(
                "an ungated control set with no members cannot control anything -- cov over the "
                "empty set is the vacuity defect whatever the pool"
            )
        if self.arity != len(set(self.feature_indices)):
            raise UngatedSetCannotWearACertificate(
                f"arity {self.arity} disagrees with {len(set(self.feature_indices))} distinct "
                f"members. The whole point of this arm is to intervene AT A MATCHED ARITY."
            )

    def to_record(self) -> dict:
        return {
            "label": self.label,
            "is_a_group": False,
            "pool_source_NOT_A": self.pool_source,
            "pool_construction": self.pool_construction,
            "feature_indices": list(self.feature_indices),
            "arity_matched_to_the_group_arm": self.arity,
            "n_features_available": self.n_features_available,
            # (c) NO CERTIFICATE AND NO CONCEPT NAME. These keys are absent by
            # construction, and their absence is stated so a reader does not
            # conclude the fields were dropped.
            "coverage_vector": (
                "ABSENT BY CONSTRUCTION: an ungated set has no coverage certificate. A fabricated "
                "A = 1 everywhere makes cov(G) = 1^|C| for ANY non-empty G, the minimum arity 1 for "
                "every concept, and the certificate a check that cannot fail."
            ),
            "concept_id": (
                "ABSENT BY CONSTRUCTION: a control arm carries no concept name. Its outputs may be "
                "called 'a direction set that changes the text' and NEVER 'the cheese features'."
            ),
            "what_this_arm_answers": (
                "does ANY direction set of this arity change the text? A REQUIRED-IF-CLAIMED "
                "companion to any claim that a group's effect is attributable to the CONCEPT rather "
                "than to intervention-at-that-arity."
            ),
            "conditions_all_five": list(UNGATED_CONTROL_CONDITIONS),
            "never_merged": (
                "condition (e): NEVER merged with, pooled into, or tabulated in the same column as a "
                "TIER_C or TIER_S result. assert_not_merged_with_gated enforces it."
            ),
            "expected_outcome_is_not_a_prediction": (
                "if this arm SUCCEEDED the group claim would be in serious trouble, which is exactly "
                "why the arm is worth running and why its outcome is not predicted here."
            ),
        }


def assert_not_merged_with_gated(
    control: UngatedControlSet, gated_results: Sequence[GroupSelectionResult]
) -> dict:
    """Condition (e), enforced rather than documented.

    An ungated control and a gated result may be REPORTED TOGETHER -- that is
    the point of having the arm -- and they may not be MERGED, pooled, or put
    in the same table column, because the two arms answer different questions
    and a shared column is a merge whatever the caption says. This function
    exists so that the code path which would put them in one row has to go
    through a refusal to do it."""
    tiers = sorted({r.tier for r in gated_results})
    if not tiers:
        raise UngatedSetCannotWearACertificate(
            "assert_not_merged_with_gated was called with no gated result to be kept apart from, so "
            "it cannot exercise what it claims to check"
        )
    return {
        "control_label": control.label,
        "gated_tiers_reported_separately": tiers,
        "merged": False,
        "separation_rule": UNGATED_CONTROL_CONDITIONS[4],
        "how_to_report": (
            "SEPARATE columns, SEPARATE rows, SEPARATE sentences. The ungated arm's outcome is "
            "'a direction set that changes the text' or does not; it is never a coverage result, and "
            "a gated null and an ungated null are not the same null."
        ),
    }


def assert_no_depth_claim(sentence: str) -> str:
    """REFUSE a claim sentence, caption or abstract that leans on depth.

    RULING_14 REFERRAL A clause 7 binds this hard: the word 'depth' may not
    appear in any claim sentence, figure caption or abstract, and a group is
    never described as deeper, stronger or more robust on the strength of the
    depth vector. Depth is permitted as an ORDER and refused as a CLAIM,
    because that it predicts causal robustness is ARGUED and unmeasured. The
    bind exists as a function so it can FAIL rather than merely be stated."""
    lowered = sentence.lower()
    found = [word for word in DEPTH_WORDS_REFUSED_IN_A_CLAIM if word in lowered]
    if found:
        raise GroupSelectionError(
            f"this sentence leans on the depth vector via {found}: {sentence[:160]!r}. Depth is a "
            f"SPEND ORDER and not a claim. The headline is the coverage VECTOR and the only "
            f"permitted scalar is |cov(G)|. {DEPTH_BINDS}"
        )
    return sentence


def bounded_negative_sentence(
    result: GroupSelectionResult, *, realisations_examined: int, successes: int = 0
) -> str:
    """THE ONLY NEGATIVE SENTENCE AVAILABLE, with `n` AND `N` in it.

    RULING_14 REFERRAL A clause 3. `N` is exact, from the multiplicities, and
    it counts a NAMED population (`REALISATION_POPULATION`). There is no `n`
    at which this becomes universal, and this function refuses to produce a
    sentence that would read as universal: `realisations_examined` above the
    population is a bookkeeping error, and a claimed success contradicts the
    form."""
    population = result.feature_level_solution_count
    n = int(realisations_examined)
    if n < 0 or n > population:
        raise UniversalNullUnreachable(
            f"realisations_examined={n} is not in 0..{population}. N is exact from the "
            f"multiplicities and n cannot exceed it; a denominator that is smaller than its "
            f"numerator is the vacuity defect with the arithmetic reversed."
        )
    if successes:
        raise UniversalNullUnreachable(
            f"{successes} success(es) reported with the BOUNDED-NEGATIVE form. A witness licenses "
            f"the EXISTENTIAL claim and terminates the concept's group arm under the pre-registered "
            f"stopping rule; it may not be reported as a bounded negative."
        )
    return (
        f"BOUNDED NEGATIVE for {result.concept_id!r} at {result.tier}: {n} of {population} "
        f"feature-level realisations of minimum-cardinality covers tested, no success. N is EXACT "
        f"from the class multiplicities and counts minimum-cardinality covers ONLY. This is NOT a "
        f"statement that minimum-cardinality covers do not steer this concept: that sentence is "
        f"UNREACHABLE BY CONSTRUCTION, because the causal arm's unit is a REALISATION and "
        f"{population - n} realisation(s) remain untested. {result.data_provenance}"
    )


def assert_null_is_not_universal(claim: Mapping) -> Mapping:
    """REFUSE a fabricated record that reports a concept-level or class-level
    null while realisations remain untested.

    The falsifier RULING_14 attached to its own clause: "a fabricated record
    reporting a concept-level null while realisations_examined <
    realisations_in_population must FAIL the check. If it passes, the check is
    decorative." So this reads a claim record rather than a
    `GroupSelectionResult`, because the fabrication the architect described is
    a RECORD and not a selector output."""
    for required in ("scope", "realisations_examined", "realisations_in_population"):
        if required not in claim:
            raise UniversalNullUnreachable(
                f"a null claim record has no {required!r}. Without all three the claim cannot be "
                f"checked at all, and an uncheckable claim passes vacuously."
            )
    scope = str(claim["scope"]).upper()
    n = int(claim["realisations_examined"])
    population = int(claim["realisations_in_population"])
    if scope in ("REALISATION", "WITNESS"):
        return claim
    if scope not in ("CONCEPT", "CLASS"):
        raise UniversalNullUnreachable(
            f"scope {claim['scope']!r} is not one of REALISATION, CLASS or CONCEPT, so what the null "
            f"quantifies over is unstated"
        )
    if n < population:
        raise UniversalNullUnreachable(
            f"a {scope}-level null is claimed with {n} of {population} realisations examined. "
            f"REFUSED. A pattern-level equivalence class is an equivalence class FOR COVERAGE ONLY: "
            f"its members are interchangeable in cov(G) and are NOT interchangeable under "
            f"intervention, so the causal arm tests ONE REALISATION and learns about ONE "
            f"REALISATION. The permitted form is BOUNDED NEGATIVE, carrying n={n} and N={population} "
            f"in the sentence. {population - n} realisation(s) are untested."
        )
    raise UniversalNullUnreachable(
        f"a {scope}-level null is claimed with all {population} realisations examined. STILL "
        f"REFUSED, and this is the clause that is easy to miss: there is NO n at which the "
        f"bounded-negative becomes universal. Exhausting the population of MINIMUM-CARDINALITY "
        f"covers says nothing about larger irredundant covers, which are a pre-declared widening and "
        f"are not in this denominator. {REALISATION_POPULATION}"
    )


def claim_sentence(result: GroupSelectionResult, *, attribute_to_concept: bool = True) -> str:
    """The one sentence this result licenses, with the tier in it.

    PERMITTED (RULING_13 clause 7, with RULING_14's terminology correction
    applied): 'among features that individually clear [tier], this
    MINIMUM-CARDINALITY cover jointly steers the concept'. PROHIBITED: 'these
    are the features needed'. And no sentence produced here asserts steering
    at all, because no intervened generation exists behind it.

    THE MULTIPLICITY TRAVELS IN THE SENTENCE, NOT ONLY IN THE RECORD
    (RULING_14 REFERRAL A clause 10). Emitting
    `feature_level_realisations_of_this_class` in a JSON field is necessary and
    not sufficient: a sentence naming a realisation while its multiplicity
    sits in a field is a caveat that cannot be exercised by a reader of the
    claim -- the same shape as the G-A-pass denominator whose absence exposed a
    vacuity in RULING_13. So every sentence naming an emitted group carries its
    ARITY, its COVERAGE VECTOR, and the EXACT REALISATION POPULATION it was
    drawn from, with that population NAMED.

    AND THE WORD 'minimal' DOES NOT APPEAR HERE for the enumerated object
    (REFERRAL C clause 3). Unqualified, it asserts the removal property AND
    implies the enumeration ranged over every cover holding it; the second half
    is false of what this file emits. The enumerated object is 'the
    minimum-cardinality covers'; the per-group verified property is
    'irredundant / minimal under removal'; the two are not substitutable."""
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
            f"class(es) over {result.feature_level_solution_count} feature-level realisation(s). An "
            f"incomplete group's result may NOT be read as covering the cells it misses. "
            f"{POOL_BOUND_CAVEAT} {SECOND_RECALL_BOUND} {NO_CAUSAL_EVIDENCE_CAVEAT} "
            f"{result.data_provenance}"
        )
    thing = "a SINGLE FEATURE" if result.search.minimum_arity == 1 else (
        f"a MINIMUM-CARDINALITY cover of {result.search.minimum_arity} features"
    )
    vector = list(result.groups[0].coverage) if result.groups else [1] * result.n_cells
    return (
        f"{head}: {thing} covers all {result.n_cells} cells for {subject} -- arity "
        f"{result.search.minimum_arity}, cov(G) = {vector}, |cov(G)| = {sum(vector)}. "
        f"{result.pattern_solution_count} distinct minimum-cardinality pattern class(es) achieve "
        f"this, drawn from a population of EXACTLY {result.feature_level_solution_count} "
        f"feature-level realisation(s) of minimum-cardinality covers; the arity is MEASURED, not "
        f"pre-registered, and no single realisation may be reported as 'the' cover. "
        f"{POOL_BOUND_CAVEAT} {SECOND_RECALL_BOUND} {NO_CAUSAL_EVIDENCE_CAVEAT} "
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
    # THE BAND CONTINGENCY IS SURFACED AT THE BOUNDARY, not buried in the
    # group record. It is DECIDED per group rather than bounded for the
    # population, so at the point of spend the answer is a list of bits and not
    # a count. This does not refuse: the RULING_14 ADDENDUM withdrew the clause
    # that would have made it a refusal, having measured that the screened form
    # is the FAITHFUL one and the band can only hold features whose true
    # rational EQUALS the bar.
    contingency = [
        {
            "feature_indices": list(group.feature_indices),
            "band": group.epsilon_band,
        }
        for group in result.groups
        if group.epsilon_band.get("group_is_float_representation_contingent") is not False
    ]
    return {
        "members": members,
        "dispositions": {int(f): str(dispositions[f]) for f in members},
        "spend_order": result.spend_order,
        "stopping_rule_pre_registered": STOPPING_RULE_PRE_REGISTERED,
        "realisation_population_N": result.feature_level_solution_count,
        "realisation_population_N_counts": REALISATION_POPULATION,
        "float_representation_contingency_DECIDED_per_group": contingency or (
            "NONE: every emitted group was checked member by member against the recorded band INDEX "
            "LIST and no member sits at the bar. A DECIDED negative, not an unmeasured one."
        ),
        "ungated_control_arm": result.ungated_control_arm,
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
    band_bits: Sequence[tuple[int, int]] = (),
    spend_order: str = SPEND_ORDER_ARBITRARY,
) -> CoverageProblem:
    """Build a surrogate problem THROUGH the production emitter.

    `patterns` maps a left-to-right binary string to how many features carry
    that pattern. The per-cell floats are synthesised from it and then run
    through the REAL `build_admissibility_matrix`, so the surrogate can
    never assert against a matrix the production path would not produce --
    the same discipline the discovery suite's `_synthetic_scan` uses.

    `band_bits` is a sequence of `(feature_index, cell_index)` pairs whose G-A
    value is placed INSIDE the screen band -- just under the bar and within
    `screen_epsilon` of it, which is the position a feature occupies when its
    true rational EQUALS the bar and its float64 evaluation mis-rounded. That
    is the only thing the band can contain (RULING_14 ADDENDUM: the epsilon is
    ~1.7e6 times finer than one lattice step), so it is the only construction
    that can exercise the band machinery honestly. G-B and G-C are left clearly
    above their bars, so the contingency is attributable to ONE named limb.

    NO LATTICE DENOMINATORS ARE SUPPLIED HERE, deliberately. The synthesised
    values (0.99/0.95/0.90) do not lie on the lattice any real cell count would
    produce, and `lattice_gate` REFUSES a denominator that does not divide the
    statistic rather than pretending. So the surrogate exercises the
    screened-float path and the record says the lattice comparison was NOT
    EXERCISED; the lattice path is exercised separately on values that really
    are rationals with a known denominator."""
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
    for band_feature, band_cell in band_bits:
        cell = cell_keys[int(band_cell)]
        if sep[cell][int(band_feature)] <= 0:
            raise ValueError(
                f"band bit ({band_feature}, {band_cell}) names a (feature, cell) that the pattern "
                f"map does not admit at all; a band bit MODIFIES an admitted bit rather than adding "
                f"one, or the surrogate would not be exercising the band"
            )
        # Inside [bar - screen_epsilon, bar): admitted by the screen, refused
        # by a plain float comparison. Half an epsilon below the bar.
        sep[cell][int(band_feature)] = auroc_min - _DISCOVERY._SCREEN_EPSILON / 2.0
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
        spend_order=spend_order,
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
    _print("CONTROL 6b -- SCHEMA LAYER: an ungated set cannot be EXPRESSED as a group")
    # RULING_14 REFERRAL D clause 2: refusing at the POOL layer is necessary
    # and INSUFFICIENT, because emitted through the group-record shape a
    # tautological certificate is indistinguishable from an earned one. So the
    # refusal is exercised directly against the two record shapes.
    refuses(
        "a GroupCandidate at TIER_J (the record shape itself)",
        lambda: GroupCandidate(
            tier=TIER_J, concept_id="cheese", feature_indices=(7,), arity=1,
            coverage=(1,) * 6, coverage_size=6, complete=True, pattern_by_member=((7, "111111"),),
            equivalence_class_patterns=("111111",), realisation_multiplicity=1,
            members_available_per_slot=(), minimality={"minimal_under_removal": True},
        ),
        UngatedSetCannotWearACertificate,
        "INDISTINGUISHABLE FROM AN EARNED ONE",
    )
    refuses(
        "a GroupCandidate whose pool is not derived from A",
        lambda: GroupCandidate(
            tier=TIER_C, concept_id="cheese", feature_indices=(7,), arity=1,
            coverage=(1,) * 6, coverage_size=6, complete=True, pattern_by_member=((7, "111111"),),
            equivalence_class_patterns=("111111",), realisation_multiplicity=1,
            members_available_per_slot=(), minimality={"minimal_under_removal": True},
            pool_source="random",
        ),
        UngatedSetCannotWearACertificate,
        "check that cannot fail",
    )
    refuses(
        "a GroupSelectionResult at TIER_J (the outer record shape)",
        lambda: GroupSelectionResult(
            **{
                **{k: getattr(good_result, k) for k in good_result.__dataclass_fields__},
                "tier": TIER_J,
                "groups": (),
            }
        ),
        UngatedSetCannotWearACertificate,
        "may not be expressed through any shape that carries one",
    )
    # The claim-sentence guard is now SECOND LINE: the schema above refuses
    # TIER_J before a result can exist. It is still exercised, on a result
    # built by DELIBERATELY BYPASSING the schema, so it cannot rot into dead
    # code behind the newer refusal.
    forged_tier_j = object.__new__(GroupSelectionResult)
    for name in good_result.__dataclass_fields__:
        object.__setattr__(forged_tier_j, name, getattr(good_result, name))
    object.__setattr__(forged_tier_j, "tier", TIER_J)
    object.__setattr__(forged_tier_j, "groups", ())
    print("[BYPASS] schema deliberately bypassed via object.__new__ to reach the second-line guard")
    refuses(
        "a concept-attributed claim sentence at TIER_J",
        lambda: claim_sentence(forged_tier_j),
        ConceptAttributionRefused,
        "direction set that changes the text",
    )

    _print("CONTROL 6c -- NO WIDENING PATH INTO TIER_J, and the control arm is NOT refused")
    refuses(
        "TIER_J declared in advance as a FALLBACK DESTINATION from TIER_C",
        lambda: surrogate_problem(
            patterns={"111000": 1, "000111": 1}, d_sae=8, tier=TIER_C,
            tiers_declared_in_advance=(TIER_C, TIER_J), concept_id="cheese",
            label="TIER_J-as-fallback control",
        ),
        TierWideningIntoTierJRefused,
        "EVIDENCE TO NO EVIDENCE",
    )
    control_set = UngatedControlSet(
        label=UNGATED_CONTROL_LABEL, pool_source="random", feature_indices=(11, 12), arity=2,
        pool_construction="SURROGATE: two indices drawn uniformly without reference to A",
        n_features_available=64,
    )
    print(f"[NOT-REFUSED] the same ungated set as a labelled control arm: {control_set.label}")
    print(f"          pool source (NOT A)   : {control_set.pool_source}")
    print(f"          carries a certificate : "
          f"{'coverage_vector' in control_set.to_record() and 'ABSENT' in control_set.to_record()['coverage_vector']}"
          f"  (the key states its own absence)")
    separation = assert_not_merged_with_gated(control_set, [good_result])
    print(f"          kept apart from       : {separation['gated_tiers_reported_separately']}")
    refuses(
        "an ungated set wearing a TIER_J label instead of the control label",
        lambda: UngatedControlSet(
            label="TIER_J", pool_source="random", feature_indices=(1,), arity=1,
            pool_construction="SURROGATE",
        ),
        UngatedSetCannotWearACertificate,
        "MEANT TO FAIL",
    )
    refuses(
        "an ungated control set whose pool is A after all",
        lambda: UngatedControlSet(
            label=UNGATED_CONTROL_LABEL, pool_source=POOL_SOURCE_A, feature_indices=(1,), arity=1,
            pool_construction="SURROGATE",
        ),
        UngatedSetCannotWearACertificate,
        "must NOT be A",
    )

    _print("CONTROL 6d -- THE UNIVERSAL NULL IS UNREACHABLE, and the check is not decorative")
    refuses(
        "a fabricated CONCEPT-level null with realisations left untested",
        lambda: assert_null_is_not_universal(
            {"scope": "CONCEPT", "realisations_examined": 3, "realisations_in_population": 11424000}
        ),
        UniversalNullUnreachable,
        "learns about ONE REALISATION",
    )
    refuses(
        "a CONCEPT-level null even with the whole population examined",
        lambda: assert_null_is_not_universal(
            {"scope": "CONCEPT", "realisations_examined": 6, "realisations_in_population": 6}
        ),
        UniversalNullUnreachable,
        "NO n at which the bounded-negative becomes universal",
    )
    kept = assert_null_is_not_universal(
        {"scope": "REALISATION", "realisations_examined": 1, "realisations_in_population": 6}
    )
    print(f"[NOT-REFUSED] a REALISATION-scoped null: scope={kept['scope']}  <-- the permitted form")

    _print("CONTROL 6e -- DEPTH IS A SPEND ORDER AND MAY NOT ENTER A CLAIM")
    refuses(
        "a claim sentence calling one group deeper than another",
        lambda: assert_no_depth_claim(
            "the deeper cover for cheese is more robust across cells"
        ),
        GroupSelectionError,
        "SPEND ORDER and not a claim",
    )
    print(f"[NOT-REFUSED] the production claim sentence: "
          f"{'passes' if assert_no_depth_claim(claim_sentence(good_result)) else ''} "
          f"the depth-word bind")

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

    _print("SURROGATE RESULT D -- MANY equally-minimum-cardinality classes (none silently dropped)")
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

    _print("SURROGATE RESULT E -- ADD ONE ADMISSIBILITY BIT: depth order MUST move, arbitrary MUST NOT")
    # THE FALSIFIER RULING_14 REFERRAL A CLAUSE 8 NAMES EXPLICITLY. Four cells
    # so the whole thing is inspectable by eye. The classes, their canonical
    # representatives and their arity are IDENTICAL before and after; the only
    # difference is one bit, which changes one class's per-cell depth.
    four = ("c0", "c1", "c2", "c3")
    before = {"0001": 1, "1001": 1, "0100": 1, "0110": 1, "1110": 1}
    after = {"0101": 1, "1001": 1, "0100": 1, "0110": 1, "1110": 1}

    def order_of(patterns_map, order):
        problem = surrogate_problem(
            patterns=patterns_map, d_sae=8, cell_keys=four, concept_id="surrogate_mutation",
            label="add-one-bit mutation falsifier", spend_order=order,
        )
        result = select_groups(problem)
        return (
            [list(g.feature_indices) for g in result.groups],
            [list(g.depth) for g in result.groups],
            result.search.minimum_arity,
            all(g.complete for g in result.groups),
        )

    arb_before, depth_vectors_before, arity_before, complete_before = order_of(
        before, SPEND_ORDER_ARBITRARY
    )
    arb_after, _dv, arity_after, complete_after = order_of(after, SPEND_ORDER_ARBITRARY)
    dep_before, _dv2, _a, _c = order_of(before, SPEND_ORDER_DEPTH)
    dep_after, depth_vectors_after, _a2, _c2 = order_of(after, SPEND_ORDER_DEPTH)
    print("the mutation      : feature 0's pattern 0001 -> 0101 (one bit added, in cell c1)")
    print(f"arity             : {arity_before} -> {arity_after}   (unchanged, as required)")
    print(f"all complete      : {complete_before} -> {complete_after}   (unchanged, as required)")
    print(f"depth vectors     : {depth_vectors_before} -> {depth_vectors_after}")
    print(f"ARBITRARY order   : {arb_before}")
    print(f"                 -> {arb_after}   {'UNCHANGED (required)' if arb_before == arb_after else 'CHANGED  <-- FAILED'}")
    print(f"DEPTH order       : {dep_before}")
    print(f"                 -> {dep_after}   {'CHANGED (required)' if dep_before != dep_after else 'UNCHANGED  <-- FAILED'}")
    if arity_before != arity_after or not (complete_before and complete_after):
        failures.append("mutation falsifier: the added bit changed arity or completeness")
    if arb_before != arb_after:
        failures.append("mutation falsifier: the DECLARED-ARBITRARY order moved, so it read the matrix")
    if dep_before == dep_after:
        failures.append("mutation falsifier: the DEPTH-ELECTED order did NOT move, so it read nothing")
    if dep_before == arb_before:
        failures.append("mutation falsifier: the two orders coincide, so the test cannot tell them apart")

    _print("SURROGATE RESULT F -- THE CEILING IS A FUNCTION OF |C|, NOT A STORED 6")
    for cells in (("a", "b", "c", "d"), tuple(f"c{i}" for i in range(9))):
        pattern = "1" * len(cells)
        problem = surrogate_problem(
            patterns={pattern: 1}, d_sae=8, cell_keys=cells,
            concept_id=f"surrogate_{len(cells)}_cells", label=f"{len(cells)}-cell universe",
        )
        result = select_groups(problem)
        print(f"|C| = {len(cells)}  ->  k_max = {result.search.k_max}  "
              f"{'OK' if result.search.k_max == len(cells) else 'FAILED (a stored literal)'}")
        if result.search.k_max != len(cells):
            failures.append(f"the ceiling did not follow |C| at {len(cells)} cells")
        if "DERIVED" not in result.search.k_max_basis:
            failures.append(f"the ceiling basis at {len(cells)} cells did not say DERIVED")

    _print("SURROGATE RESULT G -- BAND MEMBERSHIP IS DECIDABLE FOR A SPECIFIC GROUP")
    # The count that used to stand here could bound the population and never
    # decide THIS group. One member is placed inside the band, in one cell, on
    # one limb, and the group record names that bit.
    banded = surrogate_problem(
        patterns={"111000": 1, "000111": 1}, d_sae=8, concept_id="surrogate_band",
        label="feature 0 sits AT the G-A bar in en/f1 and mis-rounds below it",
        band_bits=((0, 0),),
    )
    banded_result = select_groups(banded)
    clean_result = select_groups(
        surrogate_problem(
            patterns={"111000": 1, "000111": 1}, d_sae=8, concept_id="surrogate_no_band",
            label="no feature at any bar",
        )
    )
    banded_band = banded_result.groups[0].epsilon_band
    clean_band = clean_result.groups[0].epsilon_band
    print(f"group with a banded member : contingent="
          f"{banded_band['group_is_float_representation_contingent']}  bits="
          f"{banded_band['contingent_bits']}")
    print(f"group with none            : contingent="
          f"{clean_band['group_is_float_representation_contingent']}  bits={clean_band['contingent_bits']}"
          f"   <-- a DECIDED negative, not an unmeasured one")
    from_matrix_only = build_problem_from_matrix(
        np.ones((4, 6), dtype=bool), cell_keys=SIX_CELLS, tier=TIER_C,
        tiers_declared_in_advance=(TIER_C,), concept_id="surrogate_matrix_only",
        data_provenance="SURROGATE",
    )
    unknown_band = select_groups(from_matrix_only).groups[0].epsilon_band
    print(f"matrix-only path           : decidable={unknown_band['decidable']}  "
          f"contingent={unknown_band['group_is_float_representation_contingent']}   <-- UNKNOWN, "
          f"which is a finding")
    if banded_band["group_is_float_representation_contingent"] is not True:
        failures.append("band control: a group with a banded member was not flagged contingent")
    if clean_band["group_is_float_representation_contingent"] is not False:
        failures.append("band control: a group with no banded member was not a decided negative")
    if unknown_band["decidable"] is not False:
        failures.append("band control: the matrix-only path claimed decidability it does not have")

    _print("SURROGATE RESULT H -- AN UNREACHABLE CELL: WHICH CELL, AND WHY")
    # This is now the LIVE path rather than a hypothetical branch. On the first
    # real data a concept's full-space G-A ceiling in one cell sits BELOW the
    # bar, and a ceiling is a maximum over the whole dictionary, so A[f, c] = 0
    # for EVERY f, cov(G)[c] = 0 for EVERY G, and cov = 1^|C| is unreachable at
    # every arity under every tier and every tie-break.
    ceilinged = surrogate_problem(
        patterns={"111100": 2, "000010": 3},
        d_sae=64, concept_id="surrogate_ceilinged_cell",
        label="no admissible feature in fr/f3; its G-A ceiling is BELOW the bar",
        per_cell_ceilings={
            "separation_auroc": {"cells": {
                cell: {"max_separation_auroc": 0.99 if cell != "fr/f3" else 0.89}
                for cell in SIX_CELLS
            }},
            "fire_rate": {"cells": {cell: {"max_fire_rate": 0.95} for cell in SIX_CELLS}},
            "near_miss_auroc": {"cells": {cell: {"max_near_miss_auroc": 0.90} for cell in SIX_CELLS}},
        },
    )
    ceilinged_result = select_groups(ceilinged)
    print(f"status                : {ceilinged_result.status}")
    print(f"WHICH cell            : {list(ceilinged_result.unreachable_cells)}")
    print(f"best achievable cov   : {list(ceilinged_result.best_achievable_coverage)} "
          f"(|cov| = {coverage_size(ceilinged_result.best_achievable_coverage)}, a ceiling at EVERY "
          f"arity)")
    for cell, why in ceilinged_result.unreachable_cell_disambiguation.items():
        limb = why["limbs"]["separation_auroc"]
        print(f"WHY  {cell}          : {why['verdict']}")
        print(f"                        G-A ceiling {limb['ceiling']} vs frozen bar "
              f"{limb['frozen_bar']} -> clears={limb['ceiling_clears_bar']}")
        print(f"                        a maximum is not a conjunction: "
              f"{limb['a_maximum_is_not_a_conjunction'][:88]}...")
    if ceilinged_result.status != STATUS_UNREACHABLE:
        failures.append("the ceilinged surrogate did not report NULL_COVER_UNREACHABLE_CELLS")
    if list(ceilinged_result.unreachable_cells) != ["fr/f3"]:
        failures.append("the ceilinged surrogate did not NAME the single unreachable cell")
    verdicts = {
        why["verdict"] for why in ceilinged_result.unreachable_cell_disambiguation.values()
    }
    if verdicts != {VERDICT_ENCODING_ONE_LIMB}:
        failures.append(f"the ceilinged cell's verdict was {verdicts}, not the sub-bar-limb finding")

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
