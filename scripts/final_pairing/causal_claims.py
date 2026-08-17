"""THE CLAIM-FORM GUARD: impermissible sentences are UNWRITABLE, not discouraged.

WHAT THIS MODULE IS FOR
-----------------------
RULING_14 REFERRAL A clause 3 permits exactly two claim forms about an emitted
group and no others, and it establishes that a third form people will reach for
is unreachable BY CONSTRUCTION rather than merely unproven:

  "PERMITTED CLAIM FORMS, and they are the only two: (i) EXISTENTIAL -- 'a
  minimum-cardinality cover of arity k, realisation [indices], jointly steers
  concept X under the declared tier', with the exact population size reported
  alongside; (ii) BOUNDED NEGATIVE -- 'n of N realisations tested (N exact,
  from the multiplicities), no success', where n and N BOTH travel in the
  sentence. REFUSED: any sentence of the form 'minimal groups do not steer',
  'the minimal group for X', or 'the group failed', each of which asserts a
  universal it has not measured."

The reason the universal is unreachable is a measurement: one production-scale
pattern class held 11,424,000 feature-level realisations, and "the causal arm
cannot test a class. It tests ONE REALISATION and learns about ONE
REALISATION." So the population of minimum covers is astronomically large and
exactly known, and no budget this sprint could run reaches the universal.

HOW "UNWRITABLE" IS ACHIEVED
----------------------------
Three things together, and none of them alone is sufficient:

1. THERE IS NO FREE-TEXT CLAIM CONSTRUCTOR. Every sentence this module can
   produce comes from a function that REQUIRES the numbers the ruling says must
   travel in it -- arity, coverage vector, realisation population, tier, and
   for a negative both n and N. A caller who lacks a number cannot render a
   sentence, rather than rendering one without it.
2. EVERY PRODUCED SENTENCE IS SCREENED. `assert_no_refused_phrase` runs on the
   output of each constructor, so a constructor cannot emit a refused phrase
   even by accident -- and the same function is exported for prose a human
   wrote, which is where the refused phrasings actually come from.
3. THE STATE DISTINCTIONS ARE READ FROM THE VERDICT, NOT PASSED AS INTEGERS.
   A steering claim is built from a `CellVerdict`, so a cell whose sufficiency
   status is NOT_EXERCISED or CEILING_EXCLUDED -- or whose crossing status is
   NO_ADMISSIBLE_BASELINE or NOT_EXERCISED -- CANNOT be rendered as a null: the
   constructor refuses. That is the RULING_13 bind -- "REPORTING A VOID RUN AS A
   NULL IS PROHIBITED BY NAME" -- made structural. The two status families are
   checked against SEPARATE tuples because they have separate denominators.

WHAT THIS MODULE DOES NOT DUPLICATE
-----------------------------------
`scripts/final_pairing/group_selection.py` already owns the SELECTION-side
claim layer: `bounded_negative_sentence`, `assert_null_is_not_universal`,
`claim_sentence`, `assert_no_depth_claim`. This module is the CAUSAL side and
DELEGATES to those where they already exist, by a lazy import that REFUSES
rather than skips if the module is unavailable -- a skipped delegation would
mean two implementations of one rule, drifting.
"""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

#: Cells whose status is any of these are NOT nulls, and a claim built on one
#: as though it were is the failure manufactured by the instrument.
NON_NULL_NON_RESULT_STATUSES = ("NOT_EXERCISED", "CEILING_EXCLUDED_BY_ARITHMETIC")

#: The switchability sub-result states that are not results either. Kept in a
#: SEPARATE tuple from the sufficiency statuses above, because the two criteria
#: have different denominators: merging them once made the sufficiency ceiling
#: unreachable by construction. See `causal_calibration.CellVerdict`.
NON_NULL_NON_RESULT_CROSSING_STATUSES = ("NO_ADMISSIBLE_BASELINE", "NOT_EXERCISED")

#: Substrings that may never appear in any claim sentence, caption or abstract
#: this lane emits. Each entry is (pattern, why). The patterns are lowercase
#: regexes over a lowercased sentence, because the refused forms are shapes
#: rather than exact strings -- "the minimal group" and "the  minimal   group"
#: are the same claim.
REFUSED_PHRASES: tuple[tuple[str, str], ...] = (
    (
        r"minimal\s+groups?\s+do\s+not\s+steer",
        "asserts a universal over a population that was sampled once",
    ),
    (
        r"minimum[- ]cardinality\s+covers?\s+do\s+not\s+steer",
        "UNREACHABLE BY CONSTRUCTION, not merely unproven",
    ),
    (
        r"minimum\s+covers?\s+do\s+not\s+steer",
        "UNREACHABLE BY CONSTRUCTION, not merely unproven",
    ),
    (
        r"\bthe\s+minimal\s+group\b",
        "names a single object where the population is astronomically large",
    ),
    (
        r"\bthe\s+minimum[- ]cardinality\s+cover\s+for\b",
        "definite article over a population sampled once",
    ),
    (r"\bthe\s+group\s+failed\b", "a universal over a population that was sampled once"),
    (
        r"\bthe\s+features\s+needed\b",
        "the pool bound is PERMANENT BY CONSTRUCTION; recall is never established",
    ),
    (r"\bthese\s+are\s+the\s+features\b", "same pool bound"),
    (
        r"\bthe\s+group\s+is\s+not\s+necessary\b",
        "a necessity claim from an instrument that cannot detect presence",
    ),
    (
        r"\bnot\s+necessary\s+for\s+the\s+concept\b",
        "prohibited reading of a null ablation (RULING_A11b)",
    ),
    (
        r"\bablation\s+showed\s+no\s+causal\s+role\b",
        "prohibited reading of a null ablation (RULING_A11b)",
    ),
    (
        r"\bdoes\s+not\s+depend\s+on\s+this\s+set\b",
        "prohibited reading of a null ablation (RULING_A11b)",
    ),
    (r"\btrends?\s+toward\b", "a null may not be softened (RULING_13 Q2 clause 4)"),
    (r"\bapproaches\s+the\s+margin\b", "a null may not be softened"),
    (r"\bdirectionally\s+consistent\b", "a null may not be softened"),
    (
        r"\bseparate\s+representations?\b",
        "the two persona groups are DISJOINT BY CONSTRUCTION, so a disjoint result carries no "
        "information about separate representation",
    ),
    (
        r"\basymmetry\s+in\s+the\s+model'?s?\s+representation\b",
        "a one-sided outcome MAY NEVER be reported this way, with no condition",
    ),
    (
        r"\bhas\s+a\s+pro-?american\s+representation\b",
        "the FALSE, INFLAMMATORY sentence a scoring convention produces from a one-directional flip",
    ),
    (
        r"\bhas\s+a\s+pro-?chinese\s+representation\b",
        "the mirror of the same prohibited sentence",
    ),
    (
        r"\bbipolar\s+axis\b",
        "the axis is a CONSTRUCTION of ours, never a bipolar axis of the model (RULING_15 R2 "
        "condition 1)",
    ),
    (r"\bthe\s+stance\s+axis\b", "same: names a discovered object that is structurally excluded"),
    (r"\ba\s+signed\s+stance\s+direction\b", "same"),
    (r"\bmodel\s+represents\s+stance\s+on\s+one\s+axis\b", "same"),
    (r"\ba\s+discovered\s+switch\b", "any switch here is CONSTRUCTED, never discovered"),
    (r"\bmodel'?s?\s+stance\s+representation\b", "attributes the construction to the model"),
    (
        r"\basserted\s+(?:them\s+)?more\s+strongly\b",
        "FORCE wording: the variable is BREADTH. Required form: 'asserted more of the six claim "
        "types' (RULING_15 R1 clause 8)",
    ),
    (r"\bhow\s+strongly\b", "force wording for a breadth variable"),
    (r"\bstrength\s+of\s+conviction\b", "force wording for a breadth variable"),
    (r"\bdegree\s+of\s+belief\b", "force wording for a breadth variable"),
    (
        r"\bthe\s+baseline\s+was\s+low\b",
        "the arithmetic ceiling excludes IMPOSSIBILITY only and licenses no statement about how low "
        "a baseline was (RULING_15)",
    ),
    (r"\bthere\s+was\s+headroom\b", "same: the unexcluded high-baseline residue is not a finding"),
    (r"\bcontrol\s+rate\s+was\s+acceptable\b", "same"),
    (
        r"\bconfident\s+the\s+intervention\s+worked\b",
        "attained coverage is a property of the BOUND, not a confidence level for the science; this "
        "is a category error and is refused",
    ),
)

#: RULING_12 / RULING_13 Q5 clause 1. Until the era alternative is addressed,
#: a causal result may be attributed to the CORPUS-DEFINED CONTRAST and never
#: to a nation.
PERSONA_ATTRIBUTION_PERMITTED = "this group steers the corpus-defined contrast"
PERSONA_ATTRIBUTION_PROHIBITED = (
    "'this group steers the pro-Chinese persona', or any national attribution. PERMITTED until "
    "RULING_10 6(b) or 6(c) is addressed: 'this group steers the corpus-defined contrast'."
)

#: The frozen unconditional form for a one-sided outcome, and its three
#: MANDATORY caveats, transcribed from the frozen description's
#: SYMMETRIC_TREATMENT_AT_EVERY_STAGE. They are caveats on the report, never
#: conditions on a model-level claim: "Ruling one of them out rules out NONE of
#: the others, and ruling out all three licenses NOTHING."
SINGLE_AXIS_COLLAPSE_HEADLINE = "SINGLE-AXIS COLLAPSE DETECTED"
SINGLE_AXIS_COLLAPSE_MANDATORY_CAVEATS = (
    "(i) SINGLE-AXIS COLLAPSE under directional AUROC: on a symmetric mirror-only comparison "
    "AUROC_B(f) = 1 - AUROC_A(f) exactly, so a one-sided outcome is the CORRECT DETECTION of a "
    "single axis and not an artifact to be hedged about.",
    "(ii) PRETRAINING PREVALENCE (frozen description RESIDUAL_ASYMMETRIES.5), which cannot be "
    "fixed at the corpus layer.",
    "(iii) REFERENT TEMPORAL SHAPE on the HD and CC claim types (RESIDUAL_ASYMMETRIES.1), named "
    "there as the first confound to check against any asymmetric outcome, with the FLAGGED-PAIR "
    "REGISTER as the row-level record of which pairs carry it.",
)
SINGLE_AXIS_COLLAPSE_CLOSURE = (
    "There is no test, and no combination of tests, whose completion converts this result into a "
    "claim about the model."
)


UNEXERCISED_WITHOUT_GPU = (
    "Every sentence this module has ever produced was built from SYNTHETIC verdicts. No claim about "
    "either pairing has been rendered, because no generation has been scored, so no sentence here "
    "has ever carried a real number.",
    "Whether the phrase screen catches the phrasings a real write-up reaches for. It has only been "
    "run on sentences THIS LANE WROTE, which is the weakest possible sample: the author of a screen "
    "is the worst person to generate its test cases, because the shapes they think of are the "
    "shapes they already blocked. Every entry is proven ABLE to fire, which is a different and "
    "smaller claim than proven SUFFICIENT. Running it over an actual draft report -- and over the "
    "existing reports/ prose -- is a real task and it is not done.",
    "Whether the joint-condition attestation is honest in practice. It is a flag a caller sets, "
    "because a CellVerdict cannot distinguish one joint arm from two composed arms. Making it "
    "derivable rather than attested needs the arm record to carry its own composition, which is the "
    "intervention lane's to emit and is not built.",
)
"""What this module cannot settle. It needs no GPU to run, which is exactly why
the honest list is about SUFFICIENCY rather than execution: a screen whose
author also wrote its test cases is proven able to fire and is not proven
complete."""


class ClaimFormError(RuntimeError):
    """Base for every refusal here."""


class RefusedClaimForm(ClaimFormError):
    """The sentence asserts a universal it has not measured."""


class VoidReportedAsNull(ClaimFormError):
    """A cell that was never exercised was about to be reported as a null."""


class PersonaAttributionRefused(ClaimFormError):
    """A national attribution without the era alternative addressed."""


class MultiplicityMissing(ClaimFormError):
    """A sentence names a group without the population it was drawn from."""


class SelectionLayerUnavailable(ClaimFormError):
    """The selection-side claim layer could not be loaded, so the shared rule
    cannot be delegated to and would have to be reimplemented here."""


def _selection_module() -> Any:
    """Load `group_selection` BY FILE IDENTITY, refusing on failure.

    Lazy because that module imports a 390 KB discovery module at import time
    and is being edited by another lane; importing it at this module's scope
    would make this file's import cost and liveness depend on theirs. It
    REFUSES rather than falling back to a local copy: two implementations of
    one rule is how the rule stops being one rule."""
    expected = SCRIPT_DIR / "group_selection.py"
    if not expected.is_file():
        raise SelectionLayerUnavailable(
            f"{expected} is absent, so the selection-side claim layer cannot be delegated to. This "
            f"module will not reimplement bounded_negative_sentence or "
            f"assert_null_is_not_universal locally."
        )
    directory = str(SCRIPT_DIR)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    try:
        module = importlib.import_module("group_selection")
    except Exception as error:  # pragma: no cover - surfaced with its cause
        raise SelectionLayerUnavailable(
            f"importing group_selection failed: {type(error).__name__}: {error}"
        ) from error
    resolved = Path(getattr(module, "__file__", "")).resolve()
    if resolved != expected.resolve():
        raise SelectionLayerUnavailable(
            f"'group_selection' resolved to {resolved}, not {expected}"
        )
    return module


def _frozen_null_ablation_phrasing() -> str:
    """The frozen wording, read from the intervention lane rather than copied.

    `group_intervention.NULL_ABLATION_FROZEN_PHRASING` already carries it
    verbatim from `group_necessity_and_ablation_claims.json` RULING_A11b. A
    second transcription in this file would be a second thing to keep correct,
    and the frozen sentence is one whose wording is the whole point."""
    expected = SCRIPT_DIR / "group_intervention.py"
    if not expected.is_file():
        raise SelectionLayerUnavailable(
            f"{expected} is absent, so the frozen null-ablation phrasing cannot be read from the "
            f"lane that owns it. It is NOT re-transcribed here."
        )
    directory = str(SCRIPT_DIR)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    module = importlib.import_module("group_intervention")
    resolved = Path(getattr(module, "__file__", "")).resolve()
    if resolved != expected.resolve():
        raise SelectionLayerUnavailable(
            f"'group_intervention' resolved to {resolved}, not {expected}"
        )
    phrasing = str(module.NULL_ABLATION_FROZEN_PHRASING)
    if "incomplete" not in phrasing.lower():
        raise ClaimFormError(
            f"the frozen null-ablation phrasing read from group_intervention does not contain the "
            f"incomplete-set alternative: {phrasing!r}. Every prohibited paraphrase includes any "
            f"sentence where a null ablation appears WITHOUT that alternative in the SAME sentence, "
            f"so a phrasing missing it cannot be the frozen one."
        )
    return phrasing


def assert_no_refused_phrase(sentence: str) -> str:
    """Screen any sentence, caption or abstract. Returns it, or refuses.

    Exported deliberately: the refused phrasings do not usually come out of a
    constructor, they come out of a human writing a summary. This is the
    function to run over that."""
    lowered = re.sub(r"\s+", " ", str(sentence).lower())
    for pattern, why in REFUSED_PHRASES:
        match = re.search(pattern, lowered)
        if match:
            raise RefusedClaimForm(
                f"refused phrase {match.group(0)!r}: {why}. Sentence: {str(sentence)[:200]!r}"
            )
    return sentence


def _require_multiplicity(realisation_population: int, realisations_named: int) -> None:
    if realisation_population < 1:
        raise MultiplicityMissing(
            f"realisation_population={realisation_population}. RULING_14 REFERRAL A clause 10 binds "
            f"the multiplicity to travel IN THE SENTENCE, not only in a JSON field: 'a claim "
            f"sentence naming a realisation while its multiplicity sits in a JSON field is a caveat "
            f"that cannot be exercised by a reader of the claim'. A population below 1 is not a "
            f"population."
        )
    if realisations_named > realisation_population:
        raise MultiplicityMissing(
            f"{realisations_named} realisation(s) named out of a population of "
            f"{realisation_population}. N is EXACT from the class multiplicities and n cannot "
            f"exceed it."
        )


def _coverage_text(coverage_vector: Sequence[int]) -> str:
    if not coverage_vector:
        raise MultiplicityMissing(
            "coverage_vector is empty, so |cov(G)| would be reported over no cells. The headline is "
            "the coverage VECTOR and the only permitted scalar is |cov(G)|."
        )
    vector = [int(value) for value in coverage_vector]
    if any(value not in (0, 1) for value in vector):
        raise MultiplicityMissing(
            f"coverage_vector {vector} is not a 0/1 vector. cov(G) is the SIGN of the per-cell "
            f"depth vector; a raw depth in a claim sentence is refused (depth is a spend ORDER and "
            f"never a claim)."
        )
    return f"cov(G)={''.join(str(value) for value in vector)} (|cov(G)|={sum(vector)}/{len(vector)})"


def witness_sentence(
    *,
    concept_id: str,
    tier: str,
    arity: int,
    realisation_indices: Sequence[int],
    coverage_vector: Sequence[int],
    realisation_population: int,
    verdict: Any,
    calibration_digest: str,
    era_alternative_addressed: bool = False,
) -> str:
    """FORM (i), EXISTENTIAL. The only positive sentence available.

    Requires everything RULING_14 says must travel: the arity, the coverage
    vector, the exact realisation population, the declared tier -- and, added
    here because this is the causal side, the pin the verdict was scored
    against and the per-cell status. A witness is a statement about ONE
    REALISATION and this sentence says so on its face."""
    status = str(getattr(verdict, "status", ""))
    if status != "PASS":
        raise ClaimFormError(
            f"a witness sentence was requested for a cell whose status is {status!r}. An "
            f"existential claim needs a witness; {status!r} is not one."
        )
    _require_multiplicity(int(realisation_population), len(realisation_indices))
    if int(arity) != len(realisation_indices):
        raise MultiplicityMissing(
            f"arity={arity} but {len(realisation_indices)} realisation index/indices were named. "
            f"The arity IS the number of members and a mismatch means the sentence describes a "
            f"different object from the one tested."
        )
    if str(tier).upper().endswith("TIER_J") or str(tier).upper() == "TIER_J":
        raise ClaimFormError(
            f"tier={tier!r}: TIER-J is REFUSED for any concept-attributed claim. Its outputs may "
            f"not carry the concept's name -- 'a direction set that changes the text', NEVER 'the "
            f"{concept_id} features'."
        )
    if era_alternative_addressed:
        subject = f"this group steers {concept_id}"
    else:
        subject = (
            f"{PERSONA_ATTRIBUTION_PERMITTED} defined by {concept_id}'s frozen corpus "
            f"(NOT a national attribution: RULING_10 6(b)/6(c) is not addressed, so no "
            f"persona-specific reading is licensed)"
        )
    remaining = int(realisation_population) - len(realisation_indices)
    sentence = (
        f"EXISTENTIAL: a minimum-cardinality cover of arity {int(arity)}, realisation "
        f"{list(int(index) for index in realisation_indices)}, jointly steers the concept under "
        f"{tier} in cell {verdict.cell} -- {subject}. {_coverage_text(coverage_vector)}. Drawn from "
        f"an EXACT realisation population of {int(realisation_population)}, of which {remaining} "
        f"remain untested; this is a WITNESS about ONE REALISATION and asserts nothing about the "
        f"class or the concept. Scored against control-only calibration {calibration_digest} with "
        f"margin {verdict.rate_margin} and ceiling {verdict.rate_ceiling}: n={verdict.n}, control "
        f"rate {verdict.control_rate}, intervened rate {verdict.intervened_rate}, paired delta "
        f"{verdict.paired_rate_delta}. VOID and NOT-EXERCISED counts, excluded from every "
        f"numerator and denominator: {dict(verdict.void_counts)}; baseline-excluded "
        f"{verdict.baseline_excluded}. Among features that individually clear {tier}; the recall "
        f"caveat is PERMANENT BY CONSTRUCTION."
    )
    return assert_no_refused_phrase(sentence)


def bounded_negative_steering_sentence(
    *,
    concept_id: str,
    tier: str,
    realisations_examined: int,
    realisation_population: int,
    verdicts: Sequence[Any],
    calibration_digest: str,
) -> str:
    """FORM (ii), BOUNDED NEGATIVE, with n AND N in the sentence.

    Refuses if any cell in the vector is a non-null non-result, because a
    negative built over a cell that was never exercised is a null manufactured
    by the instrument. Refuses if n exceeds N. Never becomes universal at any
    n: `remaining` is printed even when it is zero, so the reader always sees
    the denominator that bounds the claim."""
    if not verdicts:
        raise VoidReportedAsNull(
            "a bounded-negative sentence was requested over an EMPTY verdict vector, so it would "
            "report a negative over nothing. An aggregate over an empty set is the defect this "
            "sprint keeps finding."
        )
    n = int(realisations_examined)
    population = int(realisation_population)
    if n < 1:
        raise MultiplicityMissing(
            f"realisations_examined={n}: a bounded negative over zero tested realisations is not a "
            f"negative result, it is NOT EXERCISED."
        )
    _require_multiplicity(population, n)
    blocked = [
        (str(v.cell), str(v.status)) for v in verdicts if str(v.status) in NON_NULL_NON_RESULT_STATUSES
    ]
    if blocked:
        raise VoidReportedAsNull(
            f"cells {blocked} are not nulls: {NON_NULL_NON_RESULT_STATUSES} are absences of the "
            f"OPPORTUNITY to test, not absences of effect. RULING_13: 'REPORTING A VOID RUN AS A "
            f"NULL IS PROHIBITED BY NAME.' Report "
            f"them with their counts beside the negative, not inside it."
        )
    if any(str(v.status) == "PASS" for v in verdicts):
        raise ClaimFormError(
            f"cell(s) {[v.cell for v in verdicts if str(v.status) == 'PASS']} PASSED. A witness "
            f"licenses the EXISTENTIAL claim; it may not be reported as a bounded negative."
        )
    remaining = population - n
    sentence = (
        f"BOUNDED NEGATIVE for the contrast defined by {concept_id}'s frozen corpus at {tier}: "
        f"{n} of {population} feature-level realisations of minimum-cardinality covers tested, no "
        f"success. N is EXACT from the class multiplicities and counts minimum-cardinality covers "
        f"ONLY. {remaining} realisation(s) remain untested, so this is NOT a statement that "
        f"minimum-cardinality covers fail to steer the concept -- that sentence is UNREACHABLE BY "
        f"CONSTRUCTION, because the causal arm's unit is a REALISATION. Per-cell vector "
        f"{[(str(v.cell), str(v.status)) for v in verdicts]} against control-only calibration "
        f"{calibration_digest}; VOID and NOT-EXERCISED counts are reported per cell and enter no "
        f"numerator or denominator."
    )
    return assert_no_refused_phrase(sentence)


def ablation_null_sentence(
    *, set_description: str, paired_control: str, verdict: Any, calibration_digest: str
) -> str:
    """The frozen wording, and the frozen wording only.

    RULING_A11b froze the sentence and prohibited "any sentence in which a null
    ablation appears without the incomplete-set alternative stated in the same
    sentence". The frozen text is READ from the lane that owns it rather than
    re-transcribed here, and the constructor refuses a cell that was never
    exercised -- a no-op ablation is the archetype of the manufactured null."""
    status = str(getattr(verdict, "status", ""))
    if status in NON_NULL_NON_RESULT_STATUSES:
        raise VoidReportedAsNull(
            f"cell {verdict.cell} has status {status!r}, which is NOT a null. Under ablation, if no "
            f"member fired at control, zeroing is the IDENTITY and the generation is byte-identical "
            f"to control; a naive scorer reads that as 'the concept survived ablation, therefore "
            f"the set is not necessary' -- A NULL MANUFACTURED BY A NO-OP."
        )
    if status == "PASS":
        raise ClaimFormError(
            f"cell {verdict.cell} PASSED, so the null-ablation phrasing does not apply. A POSITIVE "
            f"ablation establishes NECESSITY and is licensed on its own terms."
        )
    frozen = _frozen_null_ablation_phrasing()
    sentence = (
        f"{frozen} Set: {set_description}. Paired same-seed control: {paired_control}. Cell "
        f"{verdict.cell}, n={verdict.n}, control rate {verdict.control_rate}, intervened rate "
        f"{verdict.intervened_rate}, paired delta {verdict.paired_rate_delta} against margin "
        f"{verdict.rate_margin} from control-only calibration {calibration_digest}. VOID and "
        f"NOT-EXERCISED counts, in neither numerator nor denominator: "
        f"{dict(verdict.void_counts)}. Group necessity is a SEPARATE CLAIM and is never a "
        f"precondition for publishing a sufficient minimal-cardinality cover."
    )
    return assert_no_refused_phrase(sentence)


def single_axis_collapse_sentence(*, yielding_concept_id: str, empty_concept_id: str) -> str:
    """The frozen unconditional form, with all three mandatory caveats.

    "IT MAY NEVER BE REPORTED AS AN ASYMMETRY IN THE MODEL'S REPRESENTATION.
    There is no test, and no combination of tests, whose completion converts
    this result into a claim about the model." The escape clause that once
    guarded this was DELETED with no condition, and a tightened escape clause is
    still an escape clause -- so there is no parameter on this function by which
    a caller could discharge a caveat."""
    if yielding_concept_id == empty_concept_id:
        raise ClaimFormError(
            "a one-sided outcome needs two different concepts; the pair is ONE ARTIFACT WITH A "
            "MIRROR AXIS and both receive identical treatment at every stage."
        )
    caveats = " ".join(SINGLE_AXIS_COLLAPSE_MANDATORY_CAVEATS)
    sentence = (
        f"{SINGLE_AXIS_COLLAPSE_HEADLINE}: {yielding_concept_id} yielded a feature group under the "
        f"directional-AUROC convention and {empty_concept_id} did not. ALL THREE pre-registered "
        f"alternative explanations accompany this report and none of them can be discharged: "
        f"{caveats} Ruling one of them out rules out NONE of the others, and ruling out all three "
        f"licenses NOTHING -- they are caveats on the report, never conditions on a model-level "
        f"claim. {SINGLE_AXIS_COLLAPSE_CLOSURE}"
    )
    return assert_no_refused_phrase(sentence)


def constructed_switch_sentence(
    *,
    forward: Any,
    mirrored: Any,
    calibration_digest: str,
    forward_is_one_joint_condition: bool,
    mirrored_is_one_joint_condition: bool,
) -> str:
    """A switch here is CONSTRUCTED, never a discovered bipolar representation.

    RULING_13 Q4 clause 2: the two persona groups are disjoint BY ALGEBRA,
    decided before a single prompt was written, and a shared stance axis is
    "STRUCTURALLY EXCLUDED ENTIRELY. Not 'was not found'. CANNOT BE FOUND." So
    the sentence says CONSTRUCTED on its face, and requires BOTH directions --
    a one-directional flip is a steering result and takes the single-axis
    collapse form instead.

    THE TWO JOINT-CONDITION FLAGS ARE REQUIRED, NOT DEFAULTED, and they have no
    default value on purpose. RULING_13 Q4 conjunct 1 needs "ONE condition
    SIMULTANEOUSLY ablating group A and amplifying group B, same prompt, same
    seed, same paired same-seed control", and rules that "Two separate results
    -- amplify B alone, ablate A alone -- DO NOT establish switchability and MAY
    NOT BE COMPOSED", because SAE features are not guaranteed independent and two
    groups even less so. A `CellVerdict` cannot tell a joint arm from a composed
    pair, so the first version of this function stated the prohibition in the
    sentence it emitted and could not check it -- an assertion where a check was
    required. A caller now has to say which it had, and saying the wrong thing is
    a false attestation rather than an oversight."""
    for name, flag in (
        ("forward", forward_is_one_joint_condition),
        ("mirrored", mirrored_is_one_joint_condition),
    ):
        if not flag:
            raise ClaimFormError(
                f"the {name} arm is not attested as ONE joint condition. Two separate results -- "
                f"amplify B alone and ablate A alone -- MAY NOT BE COMPOSED into a switch: the "
                f"frozen prohibition on predicting a joint effect by summing or maxing individual "
                f"deltas applies ACROSS GROUPS, and SAE features are not guaranteed independent."
            )
    for name, verdict in (("forward", forward), ("mirrored", mirrored)):
        status = str(getattr(verdict, "status", ""))
        crossing = str(getattr(verdict, "crossing_status", ""))
        if status in NON_NULL_NON_RESULT_STATUSES:
            raise VoidReportedAsNull(
                f"the {name} arm's cell {verdict.cell} has status {status!r}, which is not a "
                f"result in either direction."
            )
        if crossing in NON_NULL_NON_RESULT_CROSSING_STATUSES:
            raise VoidReportedAsNull(
                f"the {name} arm's cell {verdict.cell} has crossing_status {crossing!r}: no prompt "
                f"could evidence a flip, so there is no crossing in either direction to report."
            )
        if status != "PASS":
            raise ClaimFormError(
                f"the {name} arm did not pass (status {status!r}). BIDIRECTIONALITY is NOT A NICETY "
                f"-- it is THE ONLY DISCRIMINATOR against the single-axis-collapse artifact, whose "
                f"careless report is FALSE, INFLAMMATORY, AND PRODUCED BY A SCORING CONVENTION. A "
                f"one-directional flip takes single_axis_collapse_sentence()."
            )
        if crossing != "EVIDENCED":
            raise ClaimFormError(
                f"the {name} arm's crossing_status is {crossing!r}. A score that moved without "
                f"CROSSING the neutral band is 'directional influence without a flip', which is "
                f"reportable and MAY NOT be written as switchability -- strongly-pro-A to "
                f"weakly-pro-A is not a flip."
            )
    sentence = (
        f"CONSTRUCTED SWITCH, not a discovered bipolar representation: a composition WE assemble "
        f"over two groups that are DISJOINT BY CONSTRUCTION, on a signed axis that is structurally "
        f"excluded as a discovered object. Both directions moved the signed outcome variable across "
        f"the neutral band on the same prompts and the same seeds: forward cell {forward.cell} "
        f"delta {forward.paired_rate_delta} with {forward.crossings} crossing(s), mirrored cell "
        f"{mirrored.cell} delta {mirrored.paired_rate_delta} with {mirrored.crossings} crossing(s), "
        f"both against margin {forward.rate_margin} from control-only calibration "
        f"{calibration_digest}. ASSERTS_BOTH is reported as its own outcome class and is NOT a "
        f"flip: {forward.asserts_both} forward and {mirrored.asserts_both} mirrored. Both arms were "
        f"run as ONE joint condition per direction; two separate results MAY NOT be composed."
    )
    return assert_no_refused_phrase(sentence)


def assert_claim_is_permitted(claim: Mapping[str, Any]) -> Mapping[str, Any]:
    """FALSIFIER, written against a fabricated RECORD rather than an object.

    RULING_14 attached this falsifier to its own clause: "a fabricated record
    reporting a concept-level null while realisations_examined <
    realisations_in_population must FAIL the check. If it passes, the check is
    decorative." A `CellVerdict` cannot fabricate that, so a check that could
    only be run on the object that cannot fail it would be decorative -- which
    is why this reads a mapping.

    DELEGATES the shared arithmetic to `group_selection.assert_null_is_not_universal`
    so there is one implementation, and refuses if that module cannot be
    loaded."""
    required = ("form", "scope", "realisations_examined", "realisations_in_population", "sentence")
    missing = [key for key in required if key not in claim]
    if missing:
        raise RefusedClaimForm(
            f"a claim record is missing {missing}. Without all of them the claim cannot be checked "
            f"at all, and an uncheckable claim passes vacuously."
        )
    form = str(claim["form"]).upper()
    if form not in ("EXISTENTIAL", "BOUNDED_NEGATIVE"):
        raise RefusedClaimForm(
            f"form={claim['form']!r} is not one of the two permitted forms. RULING_14 REFERRAL A "
            f"clause 3: 'PERMITTED CLAIM FORMS, and they are the only two'."
        )
    assert_no_refused_phrase(str(claim["sentence"]))
    n = int(claim["realisations_examined"])
    population = int(claim["realisations_in_population"])
    sentence = str(claim["sentence"])
    if form == "BOUNDED_NEGATIVE":
        for number, label in ((n, "n"), (population, "N")):
            #: A STANDALONE NUMERIC TOKEN, not a substring. `str(n) in sentence`
            #: was the first version and it passed a sentence that omitted n
            #: entirely, because a single-digit n is a substring of almost any
            #: large N -- "2" sits inside "11424000". A check that a
            #: denominator-only sentence satisfies is precisely the vacuity
            #: defect this clause exists against, one level up. Digit-boundary
            #: lookaround rather than `\b`, because `\b` matches between a digit
            #: and a digit's neighbour in "11424000" is false but between "2"
            #: and "," is true -- the hazard is adjacent DIGITS specifically.
            if not re.search(rf"(?<!\d){re.escape(str(number))}(?!\d)", sentence):
                raise RefusedClaimForm(
                    f"the bounded-negative sentence does not contain {label}={number} as a number. "
                    f"Both n AND N must travel IN THE SENTENCE, not only in the record: a caveat in "
                    f"a JSON field cannot be exercised by a reader of the claim."
                )
    module = _selection_module()
    module.assert_null_is_not_universal(
        {
            "scope": claim["scope"],
            "realisations_examined": n,
            "realisations_in_population": population,
        }
    )
    return claim


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


def _selfcheck() -> int:
    """Refusals first, with real output. Every impermissible form demonstrated."""
    from dataclasses import dataclass as _dataclass

    failures = 0

    def expect_refusal(what: str, call: Any, *expected: type[BaseException]) -> None:
        nonlocal failures
        try:
            call()
        except expected as error:
            print(f"  REFUSED {what}: {type(error).__name__}: {str(error)[:170]}")
            return
        except Exception as error:  # pragma: no cover
            failures += 1
            print(f"  WRONG ERROR {what}: {type(error).__name__}: {error}")
            return
        failures += 1
        print(f"  DID NOT REFUSE {what} -- the check does not exercise what it claims")

    @_dataclass
    class FakeVerdict:
        cell: str
        status: str
        n: int = 20
        control_rate: float = 0.05
        intervened_rate: float = 0.60
        paired_rate_delta: float = 0.55
        rate_margin: float = 0.10
        rate_ceiling: float = 0.90
        void_counts: Mapping[str, int] | None = None
        baseline_excluded: int = 3
        crossing_status: str = "EVIDENCED"
        n_admissible_for_crossing: int = 17
        crossings: int = 12
        asserts_both: int = 2
        moved_without_crossing: int = 4

        def __post_init__(self) -> None:
            if self.void_counts is None:
                self.void_counts = {"not_exercised": 2, "fired_but_inert": 1, "zero_dose": 0}

    digest = "d" * 64

    _print("every impermissible sentence is refused by the screen")
    for sentence in (
        "Minimal groups do not steer this concept.",
        "Minimum-cardinality covers do not steer pro_american_exceptionalism.",
        "The minimal group for cheese is {12, 40, 77}.",
        "The group failed.",
        "These are the features needed to carry the concept.",
        "The group is not necessary.",
        "The effect trends toward the margin.",
        "The two concepts have separate representations.",
        "This is an asymmetry in the model's representation.",
        "The model has a pro-American representation and no pro-Chinese one.",
    ):
        expect_refusal(f"{sentence!r}", lambda s=sentence: assert_no_refused_phrase(s), RefusedClaimForm)

    _print("a witness sentence requires every number the ruling says must travel")
    expect_refusal(
        "a witness for a cell that did not pass",
        lambda: witness_sentence(
            concept_id="pro_american_exceptionalism",
            tier="TIER_C",
            arity=3,
            realisation_indices=(11, 22, 33),
            coverage_vector=(1, 1, 1, 1, 1, 1),
            realisation_population=11_424_000,
            verdict=FakeVerdict("en/f1", "FAIL"),
            calibration_digest=digest,
        ),
        ClaimFormError,
    )
    expect_refusal(
        "a witness whose arity disagrees with the realisation it names",
        lambda: witness_sentence(
            concept_id="pro_american_exceptionalism",
            tier="TIER_C",
            arity=5,
            realisation_indices=(11, 22, 33),
            coverage_vector=(1, 1, 1, 1, 1, 1),
            realisation_population=11_424_000,
            verdict=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
        ),
        MultiplicityMissing,
    )
    expect_refusal(
        "a concept-attributed witness from TIER_J",
        lambda: witness_sentence(
            concept_id="pro_american_exceptionalism",
            tier="TIER_J",
            arity=3,
            realisation_indices=(11, 22, 33),
            coverage_vector=(1, 1, 1, 1, 1, 1),
            realisation_population=11_424_000,
            verdict=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
        ),
        ClaimFormError,
    )
    witness = witness_sentence(
        concept_id="pro_american_exceptionalism",
        tier="TIER_C",
        arity=3,
        realisation_indices=(11, 22, 33),
        coverage_vector=(1, 1, 1, 1, 1, 1),
        realisation_population=11_424_000,
        verdict=FakeVerdict("en/f1", "PASS"),
        calibration_digest=digest,
    )
    print(f"  PERMITTED (i): {witness}")

    _print("a bounded negative carries n AND N, and refuses a void cell")
    expect_refusal(
        "a negative built over a NOT_EXERCISED cell",
        lambda: bounded_negative_steering_sentence(
            concept_id="pro_chinese_exceptionalism",
            tier="TIER_C",
            realisations_examined=1,
            realisation_population=11_424_000,
            verdicts=[FakeVerdict("en/f1", "FAIL"), FakeVerdict("fr/f2", "NOT_EXERCISED")],
            calibration_digest=digest,
        ),
        VoidReportedAsNull,
    )
    expect_refusal(
        "a negative built over a CEILING_EXCLUDED_BY_ARITHMETIC cell",
        lambda: bounded_negative_steering_sentence(
            concept_id="pro_chinese_exceptionalism",
            tier="TIER_C",
            realisations_examined=1,
            realisation_population=11_424_000,
            verdicts=[FakeVerdict("en/f1", "CEILING_EXCLUDED_BY_ARITHMETIC")],
            calibration_digest=digest,
        ),
        VoidReportedAsNull,
    )
    expect_refusal(
        "n exceeding N",
        lambda: bounded_negative_steering_sentence(
            concept_id="pro_chinese_exceptionalism",
            tier="TIER_C",
            realisations_examined=9,
            realisation_population=4,
            verdicts=[FakeVerdict("en/f1", "FAIL")],
            calibration_digest=digest,
        ),
        MultiplicityMissing,
    )
    negative = bounded_negative_steering_sentence(
        concept_id="pro_chinese_exceptionalism",
        tier="TIER_C",
        realisations_examined=2,
        realisation_population=11_424_000,
        verdicts=[FakeVerdict("en/f1", "FAIL"), FakeVerdict("fr/f1", "FAIL")],
        calibration_digest=digest,
    )
    print(f"  PERMITTED (ii): {negative}")

    _print("the frozen null-ablation phrasing is read from the owning lane")
    expect_refusal(
        "an ablation null on a cell that was never exercised",
        lambda: ablation_null_sentence(
            set_description="{11, 22, 33}",
            paired_control="control-noop seed 7",
            verdict=FakeVerdict("fr/f2", "NOT_EXERCISED"),
            calibration_digest=digest,
        ),
        VoidReportedAsNull,
    )
    try:
        print(
            "  FROZEN: "
            + ablation_null_sentence(
                set_description="{11, 22, 33}",
                paired_control="control-noop seed 7",
                verdict=FakeVerdict("en/f1", "FAIL"),
                calibration_digest=digest,
            )
        )
    except SelectionLayerUnavailable as error:  # pragma: no cover
        failures += 1
        print(f"  UNAVAILABLE: {error}")

    _print("a one-directional flip cannot be written as a switch")
    expect_refusal(
        "a switch claim with only the forward arm passing",
        lambda: constructed_switch_sentence(
            forward=FakeVerdict("en/f1", "PASS"),
            mirrored=FakeVerdict("en/f1", "FAIL"),
            calibration_digest=digest,
            forward_is_one_joint_condition=True,
            mirrored_is_one_joint_condition=True,
        ),
        ClaimFormError,
    )
    expect_refusal(
        "a switch claim whose score moved without crossing the band",
        lambda: constructed_switch_sentence(
            forward=FakeVerdict("en/f1", "PASS", crossing_status="NOT_EVIDENCED"),
            mirrored=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
            forward_is_one_joint_condition=True,
            mirrored_is_one_joint_condition=True,
        ),
        ClaimFormError,
    )
    expect_refusal(
        "a switch claim on a cell where no baseline was admissible",
        lambda: constructed_switch_sentence(
            forward=FakeVerdict("en/f1", "PASS", crossing_status="NO_ADMISSIBLE_BASELINE"),
            mirrored=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
            forward_is_one_joint_condition=True,
            mirrored_is_one_joint_condition=True,
        ),
        VoidReportedAsNull,
    )
    print(
        "  FROZEN: "
        + single_axis_collapse_sentence(
            yielding_concept_id="pro_american_exceptionalism",
            empty_concept_id="pro_chinese_exceptionalism",
        )[:400]
        + " ..."
    )
    expect_refusal(
        "a switch composed from two separate arms rather than one joint condition",
        lambda: constructed_switch_sentence(
            forward=FakeVerdict("en/f1", "PASS"),
            mirrored=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
            forward_is_one_joint_condition=False,
            mirrored_is_one_joint_condition=True,
        ),
        ClaimFormError,
    )
    print(
        "  CONSTRUCTED: "
        + constructed_switch_sentence(
            forward=FakeVerdict("en/f1", "PASS"),
            mirrored=FakeVerdict("en/f1", "PASS"),
            calibration_digest=digest,
            forward_is_one_joint_condition=True,
            mirrored_is_one_joint_condition=True,
        )[:340]
        + " ..."
    )

    _print("the fabricated-record falsifier, delegated to the selection layer")
    for scope, n, population in (("CONCEPT", 2, 11_424_000), ("CLASS", 1, 35)):
        expect_refusal(
            f"a fabricated {scope}-level null at n={n} of N={population}",
            lambda scope=scope, n=n, population=population: assert_claim_is_permitted(
                {
                    "form": "BOUNDED_NEGATIVE",
                    "scope": scope,
                    "realisations_examined": n,
                    "realisations_in_population": population,
                    "sentence": f"{n} of {population} realisations tested, no success.",
                }
            ),
            Exception,
        )
    expect_refusal(
        "a bounded negative whose sentence omits N",
        lambda: assert_claim_is_permitted(
            {
                "form": "BOUNDED_NEGATIVE",
                "scope": "REALISATION",
                "realisations_examined": 2,
                "realisations_in_population": 11_424_000,
                "sentence": "2 realisations tested, no success.",
            }
        ),
        RefusedClaimForm,
    )
    expect_refusal(
        "a third claim form",
        lambda: assert_claim_is_permitted(
            {
                "form": "SUGGESTIVE",
                "scope": "REALISATION",
                "realisations_examined": 2,
                "realisations_in_population": 11_424_000,
                "sentence": "2 of 11424000 tested.",
            }
        ),
        RefusedClaimForm,
    )

    _print("result")
    print("FAILURES:", failures)
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selfcheck", action="store_true", help="demonstrate every refusal")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selfcheck:
        return _selfcheck()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
