"""THE OUTCOME MEASURE, and the firing precondition that gates it.

WHAT THIS MODULE IS FOR
-----------------------
A steering result is not scoreable until three separate things exist: a
quantity the claim is made about, a rule for deciding whether an intervened
generation is even eligible to be scored, and a set of states that must not be
collapsed into "no effect". This module owns the second and third and holds a
REFERRED, UNADOPTED shape for the first.

NO MARGIN, THRESHOLD, CEILING OR BAND IS SET HERE. Every boundary this module
consumes arrives as an argument carrying its own provenance, and
`causal_calibration.py` is the only thing in this repository that computes one
-- from controls, before any intervened generation is scored. A grep for a
float literal used as a decision boundary in this file should find nothing, and
`tests/test_causal_outcome.py` asserts that it does.

THE REFERRAL, AND WHY THIS MODULE DOES NOT DEFINE THE MEASURE
------------------------------------------------------------
See `OUTCOME_MEASURE_REFERRAL`. In one line: the frozen head-of-chain
definition operationalises PRESENCE of the axis and states in its own words
that INTENSITY is not mechanically checkable, while RULING_14 requires an
ORDINAL SIGNED variable. The missing piece is a scale, not an implementation,
and a lane that invents the measure and then calibrates it is the
separation-of-duties defect this sprint has ruled on repeatedly. So the scale,
its anchors, its instrument and the composition rule all arrive here inside a
`RubricAttestation` that no artifact in this repository currently satisfies --
which means the real path REFUSES today, and the refusal is the honest state
rather than a gap papered over with a default.

WHAT IS PROVABLE HERE WITHOUT WEIGHTS
-------------------------------------
The refusals, the arithmetic of the composition, the state bookkeeping and the
non-collapse guarantee. See `UNEXERCISED_WITHOUT_GPU` for what only real
weights can settle.

RULINGS THIS FILE IMPLEMENTS
----------------------------
RULING_13 Q2 clause 1 (the firing precondition is checked BEFORE the outcome is
read; VOID and NOT-EXERCISED are not nulls), Q2 clause 4 (both reported with
counts, neither in a numerator or a denominator), Q4 clause 3 (a bipolar
outcome variable, not two presence booleans; 'asserts both' is its own outcome
class), Q4 clause 4 (crossing, and baseline-conditioning on the origin pole).
RULING_14 addendum's dose clause (a member whose evaluated dose is 0 refuses
rather than runs, and no zero-dose run may be recorded as an amplification).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

#: The frozen head of the v2 binding chain. Cited, never edited, and never
#: parsed for numbers -- it contains none for this purpose and says so.
FROZEN_DESCRIPTION_PATH = "prompts/final_pairing/v2/concept_description_persona_exceptionalism.json"

#: The two concept ids this lane may be asked to score, verbatim from the
#: frozen description's `describes_concepts`.
PERSONA_CONCEPT_IDS = ("pro_american_exceptionalism", "pro_chinese_exceptionalism")

#: The frozen corpus R1 clause 7's falsifier runs against. Read, never edited.
FROZEN_PROMPT_SETS_PATH = "prompts/final_pairing/v2/prompt_sets.jsonl"

OUTCOME_MEASURE_REFERRAL = """ANSWERED AT RULING_15 (architect, mailbox sequence 44). R1 and R2 are ruled; R3 is not this lane's.

WHAT WAS RULED, so that a later reader does not re-open it:
  R1 THE SCALE. An intensity-, force- or strength-graded ordinal derived from
     the frozen definition is REFUSED AS UNREACHABLE BY CONSTRUCTION -- not
     unbuilt, not deferred. The refusal below was upheld and STRENGTHENED by a
     third frozen string this lane had not cited: T3_PREDICATE.rejects,
     "Sub-threshold material is NOT a weak positive." The definition does not
     merely fail to measure force; it REFUSES A GRADED READING OF FORCE AT ITS
     OWN ADMISSION BOUNDARY, so it cannot be the source of one downstream. The
     count offered below is ADOPTED as CLAIM_TYPE_EXTENT: a BREADTH scale, per
     referent, 0 to 6, each instantiating span passing T1-T4 and T6 and violating
     no HARD_EXCLUSION. Clause 3's operative requirement was never force -- it
     was distinguishing FLIPPED from ASSERTS-BOTH from ASSERTS-NEITHER, which a
     signed extent does. See CLAIM_TYPE_EXTENT_SCALE_MIN for the anchor that is
     load-bearing, and THE_COUNT_IS_A_NEW_READING_NOT_AN_APPLICATION_OF_T5 for
     why T5 does not carry. ADOPTION IS CONDITIONAL on the frozen-row falsifier
     (`run_frozen_row_falsifier`), which needs an instrument this lane may not
     author, so the scale is ADOPTED IN FORM and NOT YET DISCHARGED.
  R2 THE COMPOSITION. own minus mirror is SANCTIONED AS A CONSTRUCTION and
     REFUSED AS A SCALAR. The outcome variable is the PAIR (signed difference,
     assertion level) with both raw per-referent counts retained. The second axis
     this lane added on its own arithmetic is now MANDATORY rather than a
     courtesy of the implementation.
  R3 THE INSTRUMENT. NOT THIS LANE'S TO IMPLEMENT. Topical relevance scorers are
     refused as a class. The author must clear FIVE exclusions, one of them new
     at sequence 44 -- NOT THE LANE THAT GENERATES THE INTERVENED CONTINUATIONS
     -- and they are enforced in `assert_separation_of_duties`'s signature rather
     than in this docstring. Naming the lane is the coordinator's.

THE REASONING IS PRESERVED BELOW rather than deleted, because the refusal is the
thing that was upheld and a later reader needs to see what it rested on.

REFERRED UP, NOT INVENTED HERE: the ordinal scale of the outcome measure.

WHAT IS ALREADY DECIDED AND NEEDS NOTHING FROM ANYONE
  The TARGET PROPERTY is frozen and unambiguous. From
  prompts/final_pairing/v2/concept_description_persona_exceptionalism.json,
  document_version final-pairing-v2-concept-description-persona-exceptionalism/1.2.0,
  THE_AXIS.one_sentence: "NATIONAL EXCEPTIONALISM AND CIVILIZATIONAL MISSION,
  ASSERTED IN THE FIRST PERSON AS A FIRST-ORDER BELIEF." Its operational
  content is frozen too: six claim types (HD, ML, CC, SIA, MFO, SE) each with
  a positive_test, six admission tests T1..T6 all of which must pass, and
  HARD_EXCLUSIONS. Nothing about the CONTENT of the measure is open.

WHAT IS MISSING, PRECISELY
  Those artifacts define ADMISSION -- a conjunction of binary tests applied to
  a candidate corpus sentence. RULING_14 (mailbox architect sequence 42,
  carrying RULING_13 Q4 clause 3) requires for any switchability claim "one
  signed score with an explicit neutral band", because two independent
  presence judgements cannot distinguish FLIPPED from NOW-ASSERTS-BOTH from
  NOW-ASSERTS-NEITHER. An ORDINAL instrument is therefore required and the
  frozen artifacts do not contain one. They contain the opposite: the same
  document states at MIRROR_LAW.intensity_parity.enforcement "NOT MECHANICALLY
  CHECKABLE", and at RESIDUAL_ASYMMETRIES.3 "Length parity is checkable;
  superlative strength is not. Nothing in the pipeline can detect one side
  written half a degree stronger", naming that residual "the weakest enforced
  link in this document". An ordinal intensity scale cannot be derived from a
  document that records intensity as unmeasurable.

  A SECOND, INDEPENDENT BIND POINTS THE SAME WAY.
  protocols/final_pairing/v1/a10d_judging_readiness.json rules that a rubric
  used to RANK rather than to gate needs RANK reliability, must state its
  measured RESOLUTION, and must have its text, scale, resolution and tiebreak
  frozen before the first judged output. The crossing predicate ranks
  (strongly-pro-A against weakly-pro-A is exactly the distinction it turns
  on), so A-10d binds it. No rubric for this axis exists at all: the only
  scoring surface in the repository is Lodestar's generic concept_relevance
  v1.0 with target_concept interpolated from the raw concept id, and
  reports/cross_model_comparison_qwen_column.md section C3 records that string
  as an UNCONTROLLED MEASUREMENT VARIABLE with a measured 3.7x swing.

WHY THIS LANE WILL NOT SUPPLY IT
  A measure authored by the lane that then calibrates its thresholds is one
  party marking its own work -- the separation this sprint has now applied to
  the committer, to the corpus-implements-definition instrument, and to the
  entity-discriminator calibrator. The whole force of a control-only
  calibration is that the calibrating lane cannot choose what the number is
  measuring.

THE THREE DECISIONS REQUIRED, AND THEY ARE NOT MINE
  R1 THE ORDINAL SCALE AND ITS ANCHORS. What makes one continuation a 3 and
     another a 5 on the exceptionalism axis, on what scale, with what anchor
     texts. One candidate is derivable entirely from frozen bytes and is
     OFFERED WITHOUT BEING ADOPTED: the COUNT OF THE SIX FROZEN CLAIM TYPES
     whose positive_test the continuation instantiates, an integer 0..6, with
     T1..T6 as the admission gate on each. It needs sanctioning because T5
     freezes "exactly one claim type" for a CORPUS ROW while a free-form
     continuation may instantiate several, so reading the count as an
     intensity is a new reading of a frozen test rather than an application
     of it.
  R2 THE COMPOSITION. RULING_13 Q4 clause 2(b) holds that a shared stance axis
     is STRUCTURALLY EXCLUDED here and that any switch is CONSTRUCTED. So the
     signed axis has to be sanctioned AS A CONSTRUCTION. The only composition
     implemented in this module is COMPOSITION_SIGNED_DIFFERENCE, and it is
     implemented as a shape to be adopted or rejected, not as a default: no
     attestation in this repository names it, so it cannot currently run.
     Note the arithmetic reason a difference alone is insufficient, which is
     the same defect RULING_13 named: own - mirror is 0 both when neither pole
     is asserted and when both are. That is why this module carries a SECOND,
     orthogonal axis (`assertion_level`) and why ASSERTS_BOTH and
     ASSERTS_NEITHER are distinct classes rather than two spellings of NEUTRAL.
  R3 THE INSTRUMENT AND ITS AUTHOR. Who judges, with which prompt at which
     digest, at what temperature and snapshot, with rank reliability and
     resolution MEASURED per A-10d clause 1 and 2. The author may be neither
     the group-selecting lane nor this calibrating lane;
     `assert_separation_of_duties` refuses both.

WHAT IS BUILT ANYWAY, SO THAT THE REFERRAL COSTS NO TIME
  Everything that does not depend on R1..R3: the firing precondition and its
  refusals, the state bookkeeping that keeps VOID and NOT-EXERCISED out of
  every numerator and denominator, the two-axis composition arithmetic, the
  outcome classes including ASSERTS_BOTH, the crossing and baseline-conditioning
  predicates, the whole control-only calibration in causal_calibration.py, and
  the claim-form guard in causal_claims.py. When R1..R3 are answered, what
  changes is the CONTENT of one attestation object."""

UNEXERCISED_WITHOUT_GPU = (
    "Any real generation. No continuation produced by gemma-3-12b-it or Qwen3.5-27B has ever "
    "been scored by this file, because generation needs weights this lane does not have. Every "
    "reading in every test is a synthetic float supplied by the test.",
    "Whether a real rubric can hit the resolution it declares. A_10d clause 2 requires the "
    "smallest reproducibly distinguishable difference to be MEASURED, which needs repeated "
    "judging of real outputs. This file consumes the declared value and can only check that it "
    "is positive and no wider than the scale.",
    "Whether the control distribution is non-degenerate on real weights. The refusals for an "
    "empty, contaminated or unsupportably small control set are exercised on fixtures; whether "
    "real controls trip them is a property of the model, not of this code.",
    "Whether an APPLIED intervention on a real bf16 residual stream reports absorbed elements. "
    "The absorption refusal here reads the intervention lane's ledger; at alpha=0.001 on a "
    "synthetic fixture 157 of 160 elements were absorbed WHILE THE EXACT-DELTA ASSERTION PASSED, "
    "so the refusal is wired to absorbed_element_count and not to that assertion. On real "
    "weights the absorbed fraction at a given alpha is predicted, not observed.",
    "Whether any cell ever passes. This file computes eligibility and arithmetic and owns no "
    "verdict about the model.",
)

# --------------------------------------------------------------------------
# The state vocabulary, owned by the intervention lane and mirrored here.
# --------------------------------------------------------------------------

#: Mirrors `group_intervention.InterventionState` EXACTLY. It is restated
#: rather than imported at module scope on purpose: importing that module
#: pulls in torch and, through it, a 390 KB discovery module, which would make
#: this file's import cost and its liveness depend on two files other lanes are
#: editing right now. The cost of restating is a DRIFT HAZARD, so the drift is
#: made checkable instead of assumed: `assert_state_vocabulary_matches_intervention_lane`
#: imports the real thing and compares, and a test calls it. A mirrored
#: constant with no comparison would be exactly the defect class this sprint is
#: spending itself on.
INTERVENTION_STATES: tuple[str, ...] = ("CONTROL", "NOT_EXERCISED", "FIRED_BUT_INERT", "APPLIED")

#: The only two states whose outcome may be read at all. `APPLIED` is a result;
#: `CONTROL` is the reference a result is measured against. The other two are
#: VOID -- evidence in neither direction -- and RULING_13 prohibits reporting
#: either as a null BY NAME.
READABLE_STATES: tuple[str, ...] = ("CONTROL", "APPLIED")

#: The buckets a refused generation is routed into. Every one of them is
#: reported with its own count and NONE of them enters a numerator or a
#: denominator (RULING_13 Q2 clause 4). The names are the reasons, so a reader
#: of the record can tell an absence of opportunity from an absence of effect.
REFUSAL_BUCKETS: tuple[str, ...] = (
    "not_exercised",
    "fired_but_inert",
    "absorbed",
    "zero_dose",
    "evidence_missing",
    "self_contradictory_record",
)

STATE_IS_NOT_A_NULL = (
    "NOT_EXERCISED and FIRED_BUT_INERT are VOID, NOT NULLS. A no-op ablation whose continuation "
    "is byte-identical to control is an ABSENCE OF THE OPPORTUNITY to test necessity, not a "
    "failure of it, and reporting it as a null is a failure MANUFACTURED BY THE INSTRUMENT. "
    "Neither state enters a numerator or a denominator; both are reported with counts."
)

#: The composition of the two pole readings into one signed axis. REFERRED,
#: NOT ADOPTED -- see `OUTCOME_MEASURE_REFERRAL` R2. It is named so that an
#: attestation can adopt it explicitly; it is not a default and there is no
#: code path that supplies it when an attestation omits it.
COMPOSITION_SIGNED_DIFFERENCE = "signed_difference_over_two_disjoint_poles"
COMPOSITIONS: tuple[str, ...] = (COMPOSITION_SIGNED_DIFFERENCE,)

#: The five outcome classes. ASSERTS_BOTH and ASSERTS_NEITHER exist because a
#: signed difference cannot tell them apart (both give 0) and RULING_13 Q4
#: clause 3 requires 'asserts both' to be "its OWN outcome class rather than
#: scored as a flip or discarded" -- it is a very likely outcome of amplifying
#: one persona while ablating the other.
OUTCOME_CLASSES: tuple[str, ...] = (
    "POLE_OWN",
    "POLE_MIRROR",
    "NEUTRAL",
    "ASSERTS_BOTH",
    "ASSERTS_NEITHER",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_EVIDENCE_REFERENCE = re.compile(r"^(?P<path>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$")

# --------------------------------------------------------------------------
# RULING_15 R1: the adopted outcome variable, its anchors, and the words that
# may not be used for it. NONE OF THESE NUMBERS IS A THRESHOLD THIS LANE CHOSE
# -- each is an IDENTITY fixed by the architect at mailbox sequence 44, and
# scale_min is fixed there precisely BECAUSE this module's own
# classify_bipolar makes ASSERTS_NEITHER unreachable at any other value.
# --------------------------------------------------------------------------

#: The frozen partition of the axis. Its CARDINALITY is the scale maximum, so if
#: the frozen set ever changes size the scale changes with it and any
#: attestation against the old size is void.
FROZEN_CLAIM_TYPES: tuple[str, ...] = ("HD", "ML", "CC", "SIA", "MFO", "SE")

OUTCOME_VARIABLE_NAME = "CLAIM_TYPE_EXTENT"

#: 0 is the NO-CLAIM-TYPE-ADMITTED point. LOAD-BEARING, NOT TASTE:
#: `classify_bipolar` decides ASSERTS_NEITHER on `assertion_level > 0.0`, so for
#: ANY scale whose minimum exceeds zero the assertion level is strictly positive
#: for every possible generation, ASSERTS_NEITHER IS UNREACHABLE BY
#: CONSTRUCTION, and every no-assertion generation files as NEUTRAL -- the
#: collapse RULING_13 Q4 clause 3 exists to prevent, arriving through the
#: validator instead of through the arithmetic. The loader ENFORCES it, so the
#: class's reachability cannot depend on two modules happening to agree.
CLAIM_TYPE_EXTENT_SCALE_MIN = 0.0
CLAIM_TYPE_EXTENT_SCALE_MAX = float(len(FROZEN_CLAIM_TYPES))

#: One claim type. BY ARITHMETIC: an instrument cannot express a difference
#: smaller than one lattice step, so a declared resolution below one step is not
#: a stricter instrument, it is an unreadable one, and it is REFUSED at the
#: attestation. No resolution VALUE is set here -- the measured value is someone
#: else's to produce under a10d clause 2.
CLAIM_TYPE_EXTENT_LATTICE_STEP = 1.0

#: 7 points per referent, 13 on the signed difference over [-6, +6].
CLAIM_TYPE_EXTENT_POINTS_PER_REFERENT = len(FROZEN_CLAIM_TYPES) + 1
CLAIM_TYPE_EXTENT_DIFFERENCE_POINTS = 2 * len(FROZEN_CLAIM_TYPES) + 1

THE_COUNT_IS_A_NEW_READING_NOT_AN_APPLICATION_OF_T5 = """T5 DOES NOT CARRY, AND THIS IS A NEW READING.

T5's stated purpose is that a blend "makes THE GRID unfalsifiable and THE MIRROR
unverifiable". Both objects are properties of an AUTHORED SLOT in a mirrored
grid: a slot has an assigned claim type, a mirror partner and a parity reader. A
model continuation occupies no slot, has no assigned type and has no mirror
partner, so neither harm T5 prevents is available to be caused. T5 is an
AUTHORING constraint; the six positive_tests are CONTENT and they carry.

CONSEQUENCES, BOTH DIRECTIONS. This module may NOT import T5's exactly-one
clause as a validity check on a continuation, and may NOT report a multi-type
continuation as malformed: a continuation asserting four claim types is a 4, not
a violation. And the count may NEVER be cited as "T5" or as "the frozen
admission test" -- it is a NEW READING of frozen tests, recorded as such
wherever it is described. A new reading presented as an inherited one is how a
downstream document comes to describe an axis the corpus never implemented,
which is the failure the definition's own negative list was written against."""

#: Prohibited in prose AND in code symbols for this variable (RULING_15 R1
#: clause 8). The frozen document records force as unmeasurable; a variable named
#: for force asserts a measurement the pipeline cannot make, and a reader cannot
#: see the substitution without opening the definition.
FORCE_WORDS_PROHIBITED: tuple[str, ...] = (
    "intensity",
    "strength",
    "force",
    "how strongly",
    "more strongly",
    "degree of belief",
    "strength of conviction",
)

REQUIRED_EXTENT_WORDING = (
    "'asserted N of the six frozen claim types' / 'claim-type extent N'. Comparisons are BREADTH "
    "comparisons: 'asserted more of the six claim types', NEVER 'asserted them more strongly'."
)



class CausalOutcomeError(RuntimeError):
    """Base for every refusal in this module. There is no warn path."""


class OutcomeMeasureNotSanctioned(CausalOutcomeError):
    """The ordinal scale, its composition or its author is not attested.

    Raised on the REAL path today, because no artifact in this repository
    satisfies `RubricAttestation`. See `OUTCOME_MEASURE_REFERRAL`."""


class OrdinalScaleViolation(CausalOutcomeError):
    """A reading falls outside the scale its own rubric declares."""


class IncommensurablePoles(CausalOutcomeError):
    """Two pole readings taken with different rubrics cannot be composed.

    A difference between numbers produced by two different instruments is not
    a signed score on one axis; it is a comparison of two scales."""


class FiringPreconditionUnmet(CausalOutcomeError):
    """The generation is not eligible to be scored, and this is NOT a null.

    RULING_13 Q2 clause 1: "THE PRECONDITION IS CHECKED BEFORE THE OUTCOME IS
    READ; no outcome may be reported for a generation that fails it.\""""


class NotExercised(FiringPreconditionUnmet):
    """The hook never fired. VOID, and specifically NOT a null.

    A subclass rather than a message, because the first version of
    `CellTally.record_refusal` routed by substring and the FIRED_BUT_INERT
    message contains the words "NOT_EXERCISED" (it quotes
    `STATE_IS_NOT_A_NULL`), so both states landed in ONE bucket -- the two
    distinctions RULING_13 requires kept apart, collapsed by the router meant
    to keep them apart. Caught by this module's own selfcheck before any test
    existed. Routing on TYPE cannot do that."""


class FiredButInert(FiringPreconditionUnmet):
    """The hook fired and injected an exactly-zero delta. VOID, not a null."""


class FiringEvidenceMissing(CausalOutcomeError):
    """Required firing evidence is absent, so eligibility cannot be decided.

    An undecidable precondition is a refusal, never a pass. RULING_13 requires
    the per-call delta_norm series AND the per-member post-intervention latent
    values at intervened positions on EVERY intervened generation."""


class InterventionAbsorbed(CausalOutcomeError):
    """The dtype swallowed the requested delta, so the dose is not the dose.

    Production is bf16. At alpha=0.001 an intervention was measured being
    absorbed at 157 of 160 elements while the exact-delta assertion PASSED,
    because the absorbed magnitude sits under the dtype-forced tolerance. A
    score computed over such a generation is a score of an intervention that
    largely did not land."""


class ZeroDoseRefused(CausalOutcomeError):
    """A member's evaluated dose is zero, so nothing was done to it.

    RULING_14 addendum: "any member whose evaluated dose is 0 REFUSES rather
    than runs ... a zero dose may never be recorded as an amplification of
    that member". The archetypal cause is `corpus_max == 0`, which is MAXIMAL
    SELECTIVITY and not a dead feature -- the fault is the dose SCALE."""


class StateCollapsed(CausalOutcomeError):
    """A tally folded a VOID or NOT-EXERCISED count into a scored count."""


class VacuousTally(CausalOutcomeError):
    """An aggregate was requested over zero scored generations.

    A rate over an empty denominator is not a rate. Engineer 1 hit the
    empty-set form of this: a coverage check that passed over zero features."""


class OrientationNotDerivable(CausalOutcomeError):
    """The sign orientation cannot be derived from the condition record.

    RULING_15 DEFECT_2, and it is the one that produces a WRONG CLAIM rather
    than none. `crosses` previously carried `origin_pole="POLE_MIRROR"` as a
    DEFAULT SCIENTIFIC ORIENTATION: if the true origin was POLE_OWN the
    predicate returned False for every prompt in every cell, and that surfaced as
    NOT_EVIDENCED, whose declared meaning is "admissible prompts existed and none
    crossed". A predicate that cannot fire, reporting a substantive null. There
    is now no default; the orientation is DERIVED from the condition, and a
    condition it cannot be derived from REFUSES."""


class OrientationContradicted(CausalOutcomeError):
    """A supplied orientation disagrees with the one the condition implies."""


class EvidenceNotHashBound(CausalOutcomeError):
    """Evidence asserted in free text where a measurement is required.

    RULING_15 R3 clause 4: `rank_reliability_evidence` accepted any non-empty
    string, so it accepted "looked stable to me". a10d clause 1 requires rank
    reliability DEMONSTRATED and clause 2 requires resolution MEASURED RATHER
    THAN ASSERTED, and a free-text field is exactly an assertion. The remedy is
    the one `post_report.py` HARDEN-2 applied to `report_path`, for the identical
    reason: the value must resolve to an artifact path whose sha256 is present in
    the same record."""


class TwoAxesSeparated(CausalOutcomeError):
    """The signed difference was about to travel without the assertion level."""


class StateVocabularyDrift(CausalOutcomeError):
    """This module's mirrored state names disagree with the intervention lane."""


def sha256_hex(data: bytes) -> str:
    """One digest helper for this lane, so no two files disagree on the form."""
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Byte-identical to `interplab.core.canonical_json.canonicalize`.

    Restated here so that these three files import nothing outside
    `scripts/final_pairing/` -- they have to run from a tarball extract on the
    cluster, where the package may not be installed. The agreement is not
    assumed: `tests/test_causal_calibration.py` imports the real helper and
    asserts byte equality on a nested structure containing every JSON type."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def assert_state_vocabulary_matches_intervention_lane() -> tuple[str, ...]:
    """Compare the mirrored state names against `group_intervention`.

    Lazy and deliberate. This is the check that makes restating the vocabulary
    safe; without it the mirror is a silent divergence waiting for one lane to
    rename a state. It REFUSES on an import failure rather than skipping,
    because a skipped comparison reads as a pass."""
    import importlib
    import sys

    expected_file = SCRIPT_DIR / "group_intervention.py"
    if not expected_file.is_file():
        raise StateVocabularyDrift(
            f"cannot compare the intervention-state vocabulary: {expected_file} is absent, so the "
            f"mirror in INTERVENTION_STATES is unchecked. An unchecked mirror is not a pass."
        )
    directory = str(SCRIPT_DIR)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    module = importlib.import_module("group_intervention")
    resolved = Path(getattr(module, "__file__", "")).resolve()
    if resolved != expected_file.resolve():
        raise StateVocabularyDrift(
            f"'group_intervention' resolved to {resolved}, not {expected_file}. Loading by name "
            f"rather than by file identity is how a same-named stub once shadowed a device gate."
        )
    theirs = tuple(module.InterventionState.__args__)
    if theirs != INTERVENTION_STATES:
        raise StateVocabularyDrift(
            f"the intervention lane's states are {theirs} and this module mirrors "
            f"{INTERVENTION_STATES}. Fix the mirror; do not widen this comparison."
        )
    meanings = module.INTERVENTION_STATE_MEANINGS
    missing = [state for state in INTERVENTION_STATES if state not in meanings]
    if missing:
        raise StateVocabularyDrift(f"states with no recorded meaning upstream: {missing}")
    return theirs


# --------------------------------------------------------------------------
# The attestation that would make the measure real.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RubricAttestation:
    """WHAT THE OUTCOME MEASURE IS, attested rather than assumed.

    Every field is a thing this lane may not decide. The constructor's only
    job is to refuse an attestation that is missing one, so that the absence
    of a sanctioned measure surfaces as a refusal at the top of the scoring
    path rather than as a plausible number at the bottom of it.

    `resolution` is A-10d clause 2's "smallest score difference it can
    reproducibly distinguish, measured rather than asserted". It is NOT a
    threshold this lane sets -- it is a property of someone else's instrument,
    and `causal_calibration` uses it only as a FLOOR on a band derived from
    controls, which is what keeps a zero-spread control set from producing a
    zero-width band."""

    rubric_id: str
    rubric_version: str
    digest: str
    scale_min: float
    scale_max: float
    resolution: float
    composition: str
    anchors_digest: str
    rank_reliability_evidence: str
    sanctioned_by: str
    authored_by: str

    def __post_init__(self) -> None:
        for name in ("rubric_id", "rubric_version", "anchors_digest", "authored_by"):
            if not str(getattr(self, name)).strip():
                raise OutcomeMeasureNotSanctioned(
                    f"RubricAttestation.{name} is empty. A blank reads to a later reader as NOT "
                    f"CHECKED rather than NOT APPLICABLE, and this field is required."
                )
        for name in ("digest", "anchors_digest"):
            if not _HEX64.fullmatch(str(getattr(self, name))):
                raise OutcomeMeasureNotSanctioned(
                    f"RubricAttestation.{name} must be 64 lowercase hex; got "
                    f"{getattr(self, name)!r}. A rubric with no content digest cannot be pinned, "
                    f"and an unpinned rubric can be edited after the scores are seen."
                )
        if not str(self.sanctioned_by).strip():
            raise OutcomeMeasureNotSanctioned(
                "RubricAttestation.sanctioned_by is empty. RULING_13 Q4 clause 2(b) holds that a "
                "shared stance axis is STRUCTURALLY EXCLUDED here, so a signed axis over these two "
                "concepts is a CONSTRUCTION and must be sanctioned as one by name. See "
                "OUTCOME_MEASURE_REFERRAL R2."
            )
        if not str(self.rank_reliability_evidence).strip():
            raise OutcomeMeasureNotSanctioned(
                "RubricAttestation.rank_reliability_evidence is empty. a10d_judging_readiness.json "
                "clause 1 requires RANK reliability, not threshold reliability: a rubric that "
                "cannot reproducibly order 8 against 9 selects noise while every candidate still "
                "clears the floor. The crossing predicate ranks, so this binds. See "
                "OUTCOME_MEASURE_REFERRAL R3."
            )
        # AND IT MAY NOT BE A SENTENCE. RULING_15 DEFECT 4 / R3 clause 4: the
        # field accepted any non-empty string, so it accepted "looked stable to
        # me", where a10d clause 1 requires reliability DEMONSTRATED and clause
        # 2 requires resolution MEASURED RATHER THAN ASSERTED. The form is
        # `<path>@sha256:<64 hex>`, and `assert_evidence_is_hash_bound` checks
        # the digest against the record that carries it.
        if not _EVIDENCE_REFERENCE.fullmatch(str(self.rank_reliability_evidence)):
            raise EvidenceNotHashBound(
                f"rank_reliability_evidence must be a hash-bound artifact reference of the form "
                f"'<path>@sha256:<64 lowercase hex>', not free text; got "
                f"{self.rank_reliability_evidence!r}. a10d requires rank reliability DEMONSTRATED "
                f"and resolution MEASURED RATHER THAN ASSERTED, and a free-text field is exactly "
                f"an assertion. Same remedy post_report.py HARDEN-2 applied to report_path, for "
                f"the same reason."
            )
        if self.composition not in COMPOSITIONS:
            raise OutcomeMeasureNotSanctioned(
                f"composition {self.composition!r} is not one of {COMPOSITIONS}. There is no "
                f"default composition: RULING_13 Q4 clause 3 requires ONE SIGNED SCORE and the way "
                f"two pole readings become one is a science decision, not an implementation detail."
            )
        span = float(self.scale_max) - float(self.scale_min)
        if not span > 0.0:
            raise OrdinalScaleViolation(
                f"scale_max ({self.scale_max}) must exceed scale_min ({self.scale_min}); an "
                f"ordinal scale with no span cannot express an extent."
            )
        if not float(self.resolution) > 0.0:
            raise OrdinalScaleViolation(
                f"resolution must be positive; got {self.resolution}. A rubric that declares zero "
                f"resolution declares that every difference is real, which A-10d clause 2 forbids "
                f"-- differences below the resolution are TIES."
            )
        if float(self.resolution) > span:
            raise OrdinalScaleViolation(
                f"resolution ({self.resolution}) exceeds the scale span ({span}), so the rubric "
                f"cannot distinguish its own endpoints and no band on it means anything."
            )
        # THE ADOPTED ANCHORS, ENFORCED RATHER THAN ASSUMED (RULING_15 R1
        # clause 5, DEFECT 3). Before this, `scale_min` was free: any
        # attestation with a minimum above zero made ASSERTS_NEITHER
        # UNREACHABLE BY CONSTRUCTION, because `classify_bipolar` decides that
        # class on `assertion_level > 0.0` and the level is then strictly
        # positive for every possible generation. The guarantee was held by two
        # modules happening to agree, which is the shape of every defect in
        # this sprint's catalogue.
        if float(self.scale_min) != CLAIM_TYPE_EXTENT_SCALE_MIN:
            raise OrdinalScaleViolation(
                f"scale_min is {self.scale_min} and must be exactly "
                f"{CLAIM_TYPE_EXTENT_SCALE_MIN} -- the NO-CLAIM-TYPE-ADMITTED point. This is not "
                f"taste: classify_bipolar decides ASSERTS_NEITHER on assertion_level > 0.0, so at "
                f"any higher minimum that class is UNREACHABLE BY CONSTRUCTION and every "
                f"no-assertion generation files as NEUTRAL -- the exact collapse RULING_13 Q4 "
                f"clause 3 exists to prevent, arriving through the validator instead of through "
                f"the arithmetic."
            )
        if float(self.scale_max) != CLAIM_TYPE_EXTENT_SCALE_MAX:
            raise OrdinalScaleViolation(
                f"scale_max is {self.scale_max} and must equal the CARDINALITY of the frozen claim "
                f"types, {CLAIM_TYPE_EXTENT_SCALE_MAX} ({list(FROZEN_CLAIM_TYPES)}). If the frozen "
                f"set ever changes size the scale changes with it and this attestation is void."
            )
        if float(self.resolution) < CLAIM_TYPE_EXTENT_LATTICE_STEP:
            raise OrdinalScaleViolation(
                f"resolution {self.resolution} is below one lattice step "
                f"({CLAIM_TYPE_EXTENT_LATTICE_STEP} claim type). An instrument cannot express a "
                f"difference smaller than one step, so a finer declared resolution is not a "
                f"stricter instrument -- it is an unreadable one. The MEASURED value above one "
                f"step is someone else's to produce under a10d clause 2; only the floor is set "
                f"here, and it is arithmetic rather than choice."
            )

    @property
    def span(self) -> float:
        return float(self.scale_max) - float(self.scale_min)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rubric_id": self.rubric_id,
            "rubric_version": self.rubric_version,
            "digest": self.digest,
            "scale_min": float(self.scale_min),
            "scale_max": float(self.scale_max),
            "span": self.span,
            "resolution": float(self.resolution),
            "composition": self.composition,
            "anchors_digest": self.anchors_digest,
            "rank_reliability_evidence": self.rank_reliability_evidence,
            "sanctioned_by": self.sanctioned_by,
            "authored_by": self.authored_by,
        }


def load_rubric_attestation(payload: Mapping[str, Any]) -> RubricAttestation:
    """Build an attestation from a mapping, refusing unknown or missing keys.

    A tolerant loader that ignored an unexpected key would let a renamed field
    read as an absent one, and an absent field here is the whole point."""
    required = {
        "rubric_id",
        "rubric_version",
        "digest",
        "scale_min",
        "scale_max",
        "resolution",
        "composition",
        "anchors_digest",
        "rank_reliability_evidence",
        "sanctioned_by",
        "authored_by",
    }
    got = set(payload)
    if got != required:
        raise OutcomeMeasureNotSanctioned(
            f"rubric attestation keys must be exactly {sorted(required)}; missing "
            f"{sorted(required - got)}, unexpected {sorted(got - required)}"
        )
    return RubricAttestation(
        rubric_id=str(payload["rubric_id"]),
        rubric_version=str(payload["rubric_version"]),
        digest=str(payload["digest"]),
        scale_min=float(payload["scale_min"]),
        scale_max=float(payload["scale_max"]),
        resolution=float(payload["resolution"]),
        composition=str(payload["composition"]),
        anchors_digest=str(payload["anchors_digest"]),
        rank_reliability_evidence=str(payload["rank_reliability_evidence"]),
        sanctioned_by=str(payload["sanctioned_by"]),
        authored_by=str(payload["authored_by"]),
    )


#: THE FIVE EXCLUSIONS, exhaustive, from RULING_15 R3 clause 3. The fifth is
#: NEW at sequence 44 and is the one with the most force behind it: a lane that
#: both steers and scores can make its own steering succeed, and scoring free
#: text has far more discretion in it than any numeric check the sprint has
#: separated so far. Naming which lane remains eligible is a coordination
#: decision and is not implemented here -- only the exclusion set is.
INSTRUMENT_AUTHOR_EXCLUSIONS: tuple[str, ...] = (
    "description_author",
    "corpus_author",
    "selecting_lane",
    "calibrating_lane",
    "generating_lane",
)

INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS = {
    "description_author": "RULING_9 and RULING_12: the description author may not author the "
    "instrument that reads what the description defines.",
    "corpus_author": "RULING_9 and RULING_12, same ground applied to the corpus.",
    "selecting_lane": "The frozen description's who_sets_it clause: NOT the lane that selects the "
    "feature group.",
    "calibrating_lane": "RULING_13 and RULING_14 STANDING: a measure authored and then calibrated "
    "by one lane is one party marking its own work.",
    "generating_lane": "NEW at RULING_15 R3 clause 3. NOT THE LANE THAT GENERATES THE INTERVENED "
    "CONTINUATIONS. RULING_2's reason applies with more force than in any earlier instance: every "
    "failure in this sprint's catalogue that survived review did so because someone with the "
    "ability to make a check pass encountered a check that was failing. A lane that both steers "
    "and scores can make its own steering succeed.",
}


def assert_separation_of_duties(
    attestation: RubricAttestation, **lanes: str
) -> dict[str, str]:
    """The rubric's author may be NONE of the five excluded roles.

    ENFORCED IN THE SIGNATURE, NOT THE DOCSTRING (RULING_15 R3 clause 3: "A
    separation recorded in a docstring and not in the signature is a separation
    nobody can fail"). Every one of `INSTRUMENT_AUTHOR_EXCLUSIONS` must be
    supplied and non-empty; a missing or blank role refuses on the existing
    vacuous-pass reasoning rather than being skipped. This checked TWO lanes
    before sequence 44."""
    missing = [role for role in INSTRUMENT_AUTHOR_EXCLUSIONS if role not in lanes]
    if missing:
        raise OutcomeMeasureNotSanctioned(
            f"assert_separation_of_duties needs all five excluded roles; missing {missing}. The "
            f"exclusion set is exhaustive and a role left unsupplied is a separation nobody can "
            f"fail. Grounds: "
            f"{ {role: INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS[role] for role in missing} }"
        )
    unexpected = [role for role in lanes if role not in INSTRUMENT_AUTHOR_EXCLUSIONS]
    if unexpected:
        raise OutcomeMeasureNotSanctioned(
            f"unknown role(s) {unexpected}; the exclusion set is exactly "
            f"{list(INSTRUMENT_AUTHOR_EXCLUSIONS)} and silently accepting another name would let a "
            f"typo read as a satisfied exclusion."
        )
    author = str(attestation.authored_by).strip().lower()
    for role in INSTRUMENT_AUTHOR_EXCLUSIONS:
        lane = lanes[role]
        if not str(lane).strip():
            raise OutcomeMeasureNotSanctioned(
                f"{role} is empty, so that exclusion cannot be checked at all, and an "
                f"unenforceable separation passes vacuously. "
                f"{INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS[role]}"
            )
        if author == str(lane).strip().lower():
            raise OutcomeMeasureNotSanctioned(
                f"the rubric is authored by {attestation.authored_by!r}, which is the {role}. "
                f"{INSTRUMENT_AUTHOR_EXCLUSION_GROUNDS[role]}"
            )
    return {
        "rubric_authored_by": attestation.authored_by,
        "exclusions_checked": list(INSTRUMENT_AUTHOR_EXCLUSIONS),
        "lanes": {role: lanes[role] for role in INSTRUMENT_AUTHOR_EXCLUSIONS},
        "separation": "SATISFIED",
        "appointment_is_not_made_here": (
            "The exclusion set is structural. Deriving which lanes remain eligible is analysis and "
            "CHOOSING one is a coordination decision; if the five exclusions leave no lane that is "
            "a RESOURCING problem and NOT a licence to collapse an exclusion."
        ),
    }


def assert_evidence_is_hash_bound(
    attestation: RubricAttestation, artifacts: Sequence[Mapping[str, str]]
) -> dict[str, str]:
    """The evidence reference must resolve to an artifact in the SAME record.

    Both halves matter and both can fail: the reference must PARSE as
    `<path>@sha256:<hex>` (checked at construction) and the named path must
    appear in `artifacts` CARRYING THAT DIGEST. A reference to a file nobody
    listed is still an assertion."""
    match = _EVIDENCE_REFERENCE.fullmatch(str(attestation.rank_reliability_evidence))
    if match is None:  # pragma: no cover - construction already refused this
        raise EvidenceNotHashBound("evidence reference does not parse")
    path, digest = match.group("path"), match.group("digest")
    for artifact in artifacts:
        if artifact.get("path") == path:
            if artifact.get("sha256") != digest:
                raise EvidenceNotHashBound(
                    f"evidence names {path!r} at {digest} but the record lists it at "
                    f"{artifact.get('sha256')}. A reference whose digest disagrees with the record "
                    f"binds nothing."
                )
            return {"path": path, "sha256": digest, "hash_bound": "SATISFIED"}
    raise EvidenceNotHashBound(
        f"evidence names {path!r}, which is not among the record's artifacts "
        f"{[a.get('path') for a in artifacts]}. A reference to a file nobody listed is an "
        f"assertion with a colon in it."
    )


# --------------------------------------------------------------------------
# The two-axis reading.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PoleReading:
    """One referent's CLAIM-TYPE EXTENT on one generation, with its instrument.

    EXTENT, NOT INTENSITY. RULING_15 R1: an intensity-, force- or
    strength-graded ordinal derived from the frozen definition is REFUSED AS
    UNREACHABLE BY CONSTRUCTION, on three frozen strings -- intensity parity is
    NOT MECHANICALLY CHECKABLE; superlative strength is not checkable and is the
    weakest enforced link; and T3_PREDICATE.rejects, "Sub-threshold material is
    NOT a weak positive." A document that refuses a graded reading of force at
    its own admission boundary cannot be the source of one downstream. The
    adopted variable is BREADTH -- how many of a frozen partition of the axis are
    asserted. A field named for force would assert a measurement the pipeline
    cannot make, and a reader could not see the substitution without opening the
    frozen definition."""

    concept_id: str
    extent: float
    rubric: RubricAttestation

    def __post_init__(self) -> None:
        value = float(self.extent)
        if not (float(self.rubric.scale_min) <= value <= float(self.rubric.scale_max)):
            raise OrdinalScaleViolation(
                f"claim-type extent {value} for {self.concept_id!r} is outside its rubric's declared "
                f"scale [{self.rubric.scale_min}, {self.rubric.scale_max}]. A reading off its own "
                f"scale is not a narrower reading; it is a broken instrument."
            )


@dataclass(frozen=True)
class BipolarReading:
    """ONE SIGNED SCORE plus the orthogonal axis that makes it interpretable.

    `signed` is the stance axis. `assertion_level` is how much is being
    asserted at all, and it exists because `signed` alone is 0 both when
    neither pole is asserted and when BOTH are -- the presence-versus-ordinal
    defect RULING_13 named, one level up. Carrying both is what lets
    ASSERTS_BOTH be its own class instead of being scored as a non-event.

    `own` is the pole the claim is about; `mirror` is the other one. Which is
    which is a property of the CONDITION, not of the model."""

    own: PoleReading
    mirror: PoleReading

    def __post_init__(self) -> None:
        if self.own.rubric != self.mirror.rubric:
            raise IncommensurablePoles(
                "the two pole readings carry different rubric attestations. A difference between "
                "two instruments' numbers is not a signed score on one axis."
            )
        if self.own.concept_id == self.mirror.concept_id:
            raise IncommensurablePoles(
                f"own and mirror are both {self.own.concept_id!r}. The two persona groups are "
                f"DISJOINT BY CONSTRUCTION (RULING_13 Q4 clause 2a); a pole cannot mirror itself."
            )

    @property
    def rubric(self) -> RubricAttestation:
        return self.own.rubric

    @property
    def signed(self) -> float:
        """own - mirror, under COMPOSITION_SIGNED_DIFFERENCE.

        The composition is REFERRED (see OUTCOME_MEASURE_REFERRAL R2). This
        property is reachable only through a `RubricAttestation` that named it,
        and no attestation in this repository does."""
        return float(self.own.extent) - float(self.mirror.extent)

    @property
    def assertion_level(self) -> float:
        """own + mirror. The axis a signed difference throws away."""
        return float(self.own.extent) + float(self.mirror.extent)

    @property
    def outcome_pair(self) -> tuple[float, float]:
        """THE OUTCOME VARIABLE IS THE PAIR, not the difference.

        RULING_15 R2 VERDICT: "SANCTIONED AS A CONSTRUCTION, and REFUSED AS A
        SCALAR. The signed difference is the sanctioned composition but it is
        NOT the outcome variable." A scalar difference is not injective over the
        classes RULING_13 requires to be distinct -- own minus mirror is 0 both
        when NEITHER pole is asserted and when BOTH are -- so a scalar would
        reintroduce the presence-versus-ordinal defect inside the very variable
        built to remove it."""
        return (self.signed, self.assertion_level)

    def to_dict(self) -> dict[str, Any]:
        return {
            "own_concept_id": self.own.concept_id,
            "own_extent": float(self.own.extent),
            "mirror_concept_id": self.mirror.concept_id,
            "mirror_extent": float(self.mirror.extent),
            "signed": self.signed,
            "assertion_level": self.assertion_level,
            "outcome_pair": list(self.outcome_pair),
            "raw_counts_retained": {
                self.own.concept_id: float(self.own.extent),
                self.mirror.concept_id: float(self.mirror.extent),
            },
            "composition": self.rubric.composition,
            "composition_is_ours": (
                "constructed signed contrast over two disjoint feature groups. NOT a bipolar axis, "
                "NOT the stance axis, NOT a discovered switch, and NOT a statement about anything "
                "inside the model. RULING_15 R2 condition 1."
            ),
            "two_axes_rule": (
                "The signed difference may never be reported, plotted, pooled or thresholded "
                "without the assertion level beside it. A figure showing the difference alone is a "
                "two-boolean instrument with extra arithmetic."
            ),
            "rubric_digest": self.rubric.digest,
        }


@dataclass(frozen=True)
class OutcomeBands:
    """The boundaries that turn a reading into a class. NOT SET HERE.

    Every field arrives from `causal_calibration.calibrate`, which derives it
    from controls only. `calibration_digest` and `derivation` are required and
    validated so that a hand-typed band cannot reach `classify_bipolar`
    without forging a digest -- the point being that forging one is a
    deliberate act rather than an oversight."""

    neutral_low: float
    neutral_high: float
    assertion_floor: float
    calibration_digest: str
    derivation: str

    def __post_init__(self) -> None:
        if not _HEX64.fullmatch(str(self.calibration_digest)):
            raise CausalOutcomeError(
                f"OutcomeBands.calibration_digest must be 64 lowercase hex; got "
                f"{self.calibration_digest!r}. A band with no calibration behind it is an "
                f"invented threshold with extra steps."
            )
        if not str(self.derivation).strip():
            raise CausalOutcomeError(
                "OutcomeBands.derivation is empty. The band must say how it was computed, because "
                "a number whose derivation is unstated cannot be shown to predate the results."
            )
        if float(self.neutral_high) < float(self.neutral_low):
            raise CausalOutcomeError(
                f"neutral band is inverted: [{self.neutral_low}, {self.neutral_high}]"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "neutral_low": float(self.neutral_low),
            "neutral_high": float(self.neutral_high),
            "assertion_floor": float(self.assertion_floor),
            "calibration_digest": self.calibration_digest,
            "derivation": self.derivation,
        }


def classify_bipolar(reading: BipolarReading, bands: OutcomeBands) -> str:
    """One of `OUTCOME_CLASSES`, on two axes rather than one.

    The order of the tests is load-bearing. ASSERTS_BOTH is decided FIRST,
    because a generation that asserts both poles strongly has a signed score
    near zero and would otherwise be filed as NEUTRAL -- which is the exact
    misreading RULING_13 Q4 clause 3 exists to prevent, and the outcome it
    calls "a very likely outcome of amplifying one persona while ablating the
    other"."""
    signed = reading.signed
    inside_neutral = float(bands.neutral_low) <= signed <= float(bands.neutral_high)
    above_floor = reading.assertion_level > float(bands.assertion_floor)
    if inside_neutral:
        if above_floor:
            return "ASSERTS_BOTH"
        return "NEUTRAL" if reading.assertion_level > 0.0 else "ASSERTS_NEITHER"
    return "POLE_OWN" if signed > float(bands.neutral_high) else "POLE_MIRROR"


@dataclass(frozen=True)
class JointCondition:
    """THE CONDITION RECORD THE ORIENTATION IS DERIVED FROM.

    RULING_13 Q4 conjunct 1 requires ONE condition simultaneously ablating group
    A and amplifying group B, same prompt, same seed, same paired same-seed
    control. RULING_15 R2 condition 3 adds that the ORIGIN POLE IS A PROPERTY OF
    THAT CONDITION -- the ablated group's concept is the origin, the amplified
    group's is the target -- and must be DERIVED from it rather than supplied.

    WHY THIS TYPE EXISTS AT ALL. Before sequence 44 the orientation was a
    caller-supplied string with a DEFAULT of "POLE_MIRROR". If the true origin
    was POLE_OWN, `crosses` returned False for every prompt in every cell, and
    that surfaced as NOT_EVIDENCED -- a state whose declared meaning is
    "admissible prompts existed and none crossed". A silent never-fires,
    reported as a substantive null. This lane refused a default COMPOSITION for
    exactly that reason and then left a default ORIENTATION two functions away."""

    ablated_concept_id: str
    amplified_concept_id: str
    own_concept_id: str
    mirror_concept_id: str

    def __post_init__(self) -> None:
        for name in (
            "ablated_concept_id",
            "amplified_concept_id",
            "own_concept_id",
            "mirror_concept_id",
        ):
            if not str(getattr(self, name)).strip():
                raise OrientationNotDerivable(
                    f"JointCondition.{name} is empty, so the orientation cannot be derived and a "
                    f"blank would have to be defaulted. A blank reads as NOT CHECKED."
                )
        if self.ablated_concept_id == self.amplified_concept_id:
            raise OrientationNotDerivable(
                f"the same concept {self.ablated_concept_id!r} is recorded as both ablated and "
                f"amplified, so there is no direction to derive. The two persona groups are "
                f"DISJOINT BY CONSTRUCTION."
            )
        if self.own_concept_id == self.mirror_concept_id:
            raise OrientationNotDerivable(
                f"own and mirror are both {self.own_concept_id!r}; a pole cannot mirror itself."
            )
        if {self.ablated_concept_id, self.amplified_concept_id} != {
            self.own_concept_id,
            self.mirror_concept_id,
        }:
            raise OrientationNotDerivable(
                f"the condition intervenes on "
                f"{sorted({self.ablated_concept_id, self.amplified_concept_id})} while the reading "
                f"is over {sorted({self.own_concept_id, self.mirror_concept_id})}. The orientation "
                f"is only derivable when the intervened concepts ARE the two scored referents; "
                f"guessing which maps to which is the defaulting this type exists to remove."
            )

    @property
    def origin_pole(self) -> str:
        """The pole a control is expected to sit at: the ABLATED concept's.

        Derived, never supplied. Ablating the group that carries a referent
        moves the signed difference AWAY from that referent's pole, so the
        control -- with nothing ablated -- is the side the flip departs from."""
        if self.ablated_concept_id == self.own_concept_id:
            return "POLE_OWN"
        return "POLE_MIRROR"

    @property
    def target_pole(self) -> str:
        """The pole a successful crossing arrives at: the AMPLIFIED concept's."""
        return "POLE_MIRROR" if self.origin_pole == "POLE_OWN" else "POLE_OWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ablated_concept_id": self.ablated_concept_id,
            "amplified_concept_id": self.amplified_concept_id,
            "own_concept_id": self.own_concept_id,
            "mirror_concept_id": self.mirror_concept_id,
            "origin_pole_DERIVED": self.origin_pole,
            "target_pole_DERIVED": self.target_pole,
            "derivation": (
                "The ablated group's concept is the ORIGIN and the amplified group's is the TARGET "
                "(RULING_15 R2 condition 3). Derived from this record; never supplied, and never "
                "defaulted."
            ),
        }

    def mirrored(self) -> JointCondition:
        """The other direction of the same pair, for the bidirectionality arm."""
        return JointCondition(
            ablated_concept_id=self.amplified_concept_id,
            amplified_concept_id=self.ablated_concept_id,
            own_concept_id=self.own_concept_id,
            mirror_concept_id=self.mirror_concept_id,
        )


def derive_origin_pole(condition: JointCondition) -> str:
    """The only way to obtain an orientation. There is no default."""
    return condition.origin_pole


def assert_orientation_agrees(condition: JointCondition, supplied_pole: str) -> str:
    """REFUSE a supplied orientation that contradicts the condition.

    R2 condition 3 requires both halves: derive it, AND refuse a supplied value
    that disagrees. A caller that carries an orientation from somewhere else has
    to be told it is wrong rather than silently overridden -- overriding would
    hide a broken producer, the same reason the APPLIED-with-zero-calls record
    refuses instead of being reclassified."""
    if supplied_pole not in ("POLE_OWN", "POLE_MIRROR"):
        raise OrientationNotDerivable(
            f"supplied orientation {supplied_pole!r} is not a pole. The crossing predicate is "
            f"baseline-conditioned on the ORIGIN pole (RULING_13 Q4 clause 4)."
        )
    derived = condition.origin_pole
    if supplied_pole != derived:
        raise OrientationContradicted(
            f"the condition ablates {condition.ablated_concept_id!r} and amplifies "
            f"{condition.amplified_concept_id!r}, so the origin pole is {derived}; "
            f"{supplied_pole} was supplied. A supplied orientation that contradicts the condition "
            f"is refused rather than honoured: honouring it would make the crossing predicate "
            f"return False for every prompt in every cell and report that as NOT_EVIDENCED."
        )
    return derived


def crosses(control_class: str, intervened_class: str, *, origin_pole: str) -> bool:
    """Did the score CROSS the band, from the origin pole to the other one?

    RULING_13 Q4 clause 4: the score must CROSS the neutral band, not merely
    shift within the origin pole, and it is measured only on prompts whose
    CONTROL sits at the origin pole. A move into ASSERTS_BOTH is NOT a crossing:
    it is its own outcome class, and calling it a flip is the two-boolean defect
    returning by the back door.

    `origin_pole` IS REQUIRED AND HAS NO DEFAULT (RULING_15 DEFECT_2). Obtain it
    from `derive_origin_pole(condition)`; a literal here is a default scientific
    orientation with extra steps, and if it is the wrong one this predicate
    returns False everywhere and the wrongness surfaces as a substantive null.
    `crosses_under(condition, ...)` is the safe entry point."""
    for name, value in (("control_class", control_class), ("intervened_class", intervened_class)):
        if value not in OUTCOME_CLASSES:
            raise CausalOutcomeError(f"{name}={value!r} is not one of {OUTCOME_CLASSES}")
    if origin_pole not in ("POLE_OWN", "POLE_MIRROR"):
        raise CausalOutcomeError(
            f"origin_pole={origin_pole!r} must be a pole; the crossing predicate is "
            f"baseline-conditioned and a prompt whose control is not at a pole cannot evidence a "
            f"flip away from one."
        )
    if control_class != origin_pole:
        return False
    target = "POLE_MIRROR" if origin_pole == "POLE_OWN" else "POLE_OWN"
    return intervened_class == target


def crosses_under(
    condition: JointCondition, control_class: str, intervened_class: str
) -> bool:
    """`crosses` with the orientation DERIVED. The preferred entry point.

    Exists so that the ordinary call site cannot express the defect at all:
    there is no argument here through which an orientation could be supplied."""
    return crosses(control_class, intervened_class, origin_pole=condition.origin_pole)


def baseline_is_at_origin_pole(control_class: str, *, origin_pole: str) -> bool:
    """Is this prompt admissible for a crossing test at all?

    "a prompt already at pole B under control cannot evidence a flip to B, and
    the excluded count is reported." The exclusion is a property of the
    CONTROL, so it is decided before any intervened generation is looked at."""
    if control_class not in OUTCOME_CLASSES:
        raise CausalOutcomeError(f"control_class={control_class!r} is not one of {OUTCOME_CLASSES}")
    return control_class == origin_pole


# --------------------------------------------------------------------------
# The firing precondition.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FiringEvidence:
    """What the intervention lane recorded about whether anything happened.

    Field-for-field consumable from `group_intervention.FiringLedger.summary()`
    plus the per-member dose and latent rows RULING_13 requires. Built through
    `from_prompt_row` so that a missing key is a refusal rather than a zero."""

    intervention_state: str
    hook_call_count: int
    total_delta_norm: float
    max_abs_delta: float
    absorbed_element_count: int
    requested_nonzero_element_count: int
    residual_dtypes: tuple[str, ...]
    evaluated_member_doses: tuple[float, ...]
    post_intervention_member_latents: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.intervention_state not in INTERVENTION_STATES:
            raise FiringEvidenceMissing(
                f"intervention_state={self.intervention_state!r} is not one of "
                f"{INTERVENTION_STATES}. An unrecognised state cannot be classified as readable or "
                f"void, and defaulting it either way would decide the question this field asks."
            )

    @property
    def absorbed_fraction(self) -> float:
        if self.requested_nonzero_element_count <= 0:
            return 0.0
        return self.absorbed_element_count / self.requested_nonzero_element_count

    @property
    def is_control(self) -> bool:
        return self.intervention_state == "CONTROL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervention_state": self.intervention_state,
            "hook_call_count": int(self.hook_call_count),
            "total_delta_norm": float(self.total_delta_norm),
            "max_abs_delta": float(self.max_abs_delta),
            "absorbed_element_count": int(self.absorbed_element_count),
            "requested_nonzero_element_count": int(self.requested_nonzero_element_count),
            "absorbed_fraction": self.absorbed_fraction,
            "residual_dtypes": list(self.residual_dtypes),
            "evaluated_member_doses": [float(dose) for dose in self.evaluated_member_doses],
            "post_intervention_member_latents": [
                float(value) for value in self.post_intervention_member_latents
            ],
        }


def from_prompt_row(row: Mapping[str, Any]) -> FiringEvidence:
    """Build evidence from an intervention-lane record, refusing on absence.

    The keys are the ones `PromptResult.to_dict()` and `FiringLedger.summary()`
    already emit, plus the two per-member series. A default of 0 for a missing
    `max_abs_delta` would read as FIRED_BUT_INERT, and a default of 0 for a
    missing `absorbed_element_count` would read as a clean intervention -- both
    are the same defect, a silence that looks like a measurement."""
    required = (
        "intervention_state",
        "hook_call_count",
        "total_delta_norm",
        "max_abs_delta",
        "absorbed_element_count",
        "requested_nonzero_element_count",
        "residual_dtypes",
        "evaluated_member_doses",
        "post_intervention_member_latents",
    )
    missing = [key for key in required if key not in row]
    if missing:
        raise FiringEvidenceMissing(
            f"firing evidence is missing {missing}. RULING_13 Q2 clause 1 requires the per-call "
            f"delta_norm series and the per-member post-intervention latent values on EVERY "
            f"intervened generation, and a missing field is not a zero."
        )
    return FiringEvidence(
        intervention_state=str(row["intervention_state"]),
        hook_call_count=int(row["hook_call_count"]),
        total_delta_norm=float(row["total_delta_norm"]),
        max_abs_delta=float(row["max_abs_delta"]),
        absorbed_element_count=int(row["absorbed_element_count"]),
        requested_nonzero_element_count=int(row["requested_nonzero_element_count"]),
        residual_dtypes=tuple(str(value) for value in row["residual_dtypes"]),
        evaluated_member_doses=tuple(float(value) for value in row["evaluated_member_doses"]),
        post_intervention_member_latents=tuple(
            float(value) for value in row["post_intervention_member_latents"]
        ),
    )


def assert_firing_precondition(
    evidence: FiringEvidence, *, kind: Literal["noop", "amplify", "ablate"], member_count: int
) -> dict[str, Any]:
    """CHECKED BEFORE THE OUTCOME IS READ. Returns evidence, or raises.

    Every raise here is a state that must be COUNTED AND REPORTED rather than
    scored as zero. The caller routes them through `CellTally.record_refusal`,
    which keeps each in its own bucket and out of every denominator."""
    state = evidence.intervention_state
    if kind == "noop":
        if state != "CONTROL":
            raise FiringPreconditionUnmet(
                f"a noop arm reported state {state!r}. A control that fired is not a control, and "
                f"the paired same-seed control is the reference every delta is measured against."
            )
        if evidence.hook_call_count != 0 or evidence.max_abs_delta != 0.0:
            raise FiringPreconditionUnmet(
                f"the control arm recorded {evidence.hook_call_count} hook call(s) and "
                f"max_abs_delta={evidence.max_abs_delta}. `GroupSpec.noop` registers NO hook at "
                f"all, so a nonzero reading here means the record does not describe a control."
            )
        return {"eligible": True, "state": state, "why": "control reference, no hook registered"}

    if state == "CONTROL":
        raise FiringPreconditionUnmet(
            f"a {kind} arm reported state CONTROL. An intervened arm scored against its own state "
            f"as if it were the reference collapses the comparison the whole design rests on."
        )
    if state == "NOT_EXERCISED":
        raise NotExercised(
            f"NOT_EXERCISED on a {kind} arm: the hook never fired, so no intervention happened. "
            f"{STATE_IS_NOT_A_NULL}"
        )
    if state == "FIRED_BUT_INERT":
        raise FiredButInert(
            f"FIRED_BUT_INERT on a {kind} arm: the hook fired and injected an exactly-zero delta "
            f"at every position, so the model was never perturbed and the continuation carries no "
            f"information. Under the ruled subtract mechanism this is exactly detectable as "
            f"delta_norm == 0. {STATE_IS_NOT_A_NULL}"
        )
    if state != "APPLIED":  # pragma: no cover - the four states are exhaustive
        raise FiringPreconditionUnmet(f"unhandled state {state!r}")

    if evidence.hook_call_count <= 0:
        raise FiringEvidenceMissing(
            f"state APPLIED with hook_call_count={evidence.hook_call_count}. The record "
            f"contradicts itself; classify_intervention_state returns NOT_EXERCISED at zero calls, "
            f"so this row was not produced by the intervention lane's classifier."
        )
    if evidence.max_abs_delta <= 0.0:
        raise FiringEvidenceMissing(
            f"state APPLIED with max_abs_delta={evidence.max_abs_delta}. FIRED_BUT_INERT is the "
            f"state for a zero delta; a record claiming APPLIED at zero delta is self-contradictory "
            f"and is refused rather than reclassified, because reclassifying it here would hide a "
            f"broken producer."
        )
    if evidence.absorbed_element_count > 0:
        raise InterventionAbsorbed(
            f"{evidence.absorbed_element_count} of {evidence.requested_nonzero_element_count} "
            f"requested element(s) were ABSORBED by the residual dtype "
            f"({list(evidence.residual_dtypes)}), a fraction of {evidence.absorbed_fraction:.4f}. "
            f"The dose applied is not the dose requested. Production is bf16, and at alpha=0.001 "
            f"absorption at 157 of 160 elements was measured WHILE THE EXACT-DELTA ASSERTION "
            f"PASSED, so this refusal reads absorbed_element_count and never that assertion. "
            f"Never negotiate the tolerance; raise the dose with minimum_effective_alpha."
        )
    if member_count <= 0:
        raise FiringEvidenceMissing(
            f"member_count={member_count} on a {kind} arm. A group with no members has no "
            f"per-member dose to check, so the zero-dose refusal could not fail, and a check that "
            f"cannot fail is decorative."
        )
    for series, name in (
        (evidence.evaluated_member_doses, "evaluated_member_doses"),
        (evidence.post_intervention_member_latents, "post_intervention_member_latents"),
    ):
        if len(series) != member_count:
            raise FiringEvidenceMissing(
                f"{name} has {len(series)} entr(ies) for a {member_count}-member group. RULING_13 "
                f"requires the record PER MEMBER; a group-level summary cannot show which member "
                f"was dosed at zero."
            )
    if kind == "amplify":
        zero_dosed = [
            index for index, dose in enumerate(evidence.evaluated_member_doses) if dose == 0.0
        ]
        if zero_dosed:
            raise ZeroDoseRefused(
                f"member position(s) {zero_dosed} were dosed at exactly 0.0, so nothing was done "
                f"to them and the arm cannot be read as an amplification. The archetypal cause is "
                f"a clamp scale of `value_in_max_units * corpus_max` on a feature with "
                f"corpus_max == 0, which is MAXIMAL SELECTIVITY -- the feature fires on the "
                f"concept and nowhere in the background -- and NOT a dead feature: 89.52% of "
                f"full-space cells are in that state. The fault is the dose SCALE, not the "
                f"feature, and the replacement reference is a control-only measurement (see "
                f"causal_calibration.DOSE_REFERENCE_IS_A_CONTROL_ONLY_MEASUREMENT)."
            )
    return {
        "eligible": True,
        "state": state,
        "absorbed_fraction": evidence.absorbed_fraction,
        "why": "APPLIED, unabsorbed, every member dosed nonzero",
    }


# --------------------------------------------------------------------------
# Scored generations, and a tally that cannot collapse the states.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredGeneration:
    """One generation that PASSED the precondition and therefore has a score."""

    observation_id: str
    cell: str
    prompt_id: str
    seed: int
    arm_label: str
    kind: str
    reading: BipolarReading
    outcome_class: str
    firing: FiringEvidence

    @property
    def signed(self) -> float:
        return self.reading.signed

    @property
    def assertion_level(self) -> float:
        return self.reading.assertion_level

    @property
    def is_control(self) -> bool:
        return self.firing.is_control

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "cell": self.cell,
            "prompt_id": self.prompt_id,
            "seed": int(self.seed),
            "arm_label": self.arm_label,
            "kind": self.kind,
            "outcome_class": self.outcome_class,
            "reading": self.reading.to_dict(),
            "firing": self.firing.to_dict(),
        }


def score_generation(
    *,
    observation_id: str,
    cell: str,
    prompt_id: str,
    seed: int,
    arm_label: str,
    kind: Literal["noop", "amplify", "ablate"],
    reading: BipolarReading,
    firing: FiringEvidence,
    bands: OutcomeBands,
    member_count: int,
) -> ScoredGeneration:
    """THE ONLY WAY TO GET A SCORE, and it checks eligibility first.

    There is no code path in this module that turns a reading into an outcome
    class without going through `assert_firing_precondition`. That is the
    binding RULING_13 Q2 clause 1 asks for, and it is structural rather than
    procedural: a caller cannot forget to check, because the check is upstream
    of the only constructor."""
    assert_firing_precondition(firing, kind=kind, member_count=member_count)
    return ScoredGeneration(
        observation_id=observation_id,
        cell=cell,
        prompt_id=prompt_id,
        seed=int(seed),
        arm_label=arm_label,
        kind=kind,
        reading=reading,
        outcome_class=classify_bipolar(reading, bands),
        firing=firing,
    )


#: Routing is BY TYPE and the order is most-specific-first, because
#: `NotExercised` and `FiredButInert` are both `FiringPreconditionUnmet`. The
#: first version of this table routed by substring and collapsed the two void
#: states into one bucket; see `NotExercised`.
_BUCKET_FOR_ERROR: tuple[tuple[type[BaseException], str], ...] = (
    (NotExercised, "not_exercised"),
    (FiredButInert, "fired_but_inert"),
    (InterventionAbsorbed, "absorbed"),
    (ZeroDoseRefused, "zero_dose"),
    (FiringEvidenceMissing, "evidence_missing"),
    (FiringPreconditionUnmet, "self_contradictory_record"),
)


@dataclass
class CellTally:
    """One cell's bookkeeping, with the void states kept OUT of the numbers.

    RULING_13 Q2 clause 4: VOID and NOT-EXERCISED are "reported with counts;
    neither enters a numerator or a denominator". The way that is enforced here
    is that `scored` and the refusal buckets are DIFFERENT LISTS, `denominator`
    reads only `scored`, and `to_dict` reports every bucket by name so a reader
    can tell an absence of opportunity from an absence of effect."""

    cell: str
    scored: list[ScoredGeneration] = field(default_factory=list)
    refusals: dict[str, list[str]] = field(default_factory=dict)
    baseline_not_at_origin_pole: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for bucket in REFUSAL_BUCKETS:
            self.refusals.setdefault(bucket, [])

    def add(self, generation: ScoredGeneration) -> None:
        if generation.cell != self.cell:
            raise StateCollapsed(
                f"generation {generation.observation_id!r} is in cell {generation.cell!r}, not "
                f"{self.cell!r}. Pooling across cells is prohibited as the headline: 'this group "
                f"steers the whole concept' is a PER-CELL, PER-LOCALE property."
            )
        self.scored.append(generation)

    def record_refusal(self, observation_id: str, error: BaseException) -> str:
        """Route a refusal into its own named bucket and return the name.

        The mapping is by exception type, and an unmapped type RAISES rather
        than landing in a catch-all: a refusal filed under the wrong reason is
        how a manufactured null gets reported as a real one."""
        for error_type, bucket in _BUCKET_FOR_ERROR:
            if isinstance(error, error_type):
                self.refusals[bucket].append(observation_id)
                return bucket
        raise StateCollapsed(
            f"no bucket for {type(error).__name__}: {error}. Every refusal must be counted under a "
            f"named reason; a catch-all bucket is where a void run turns into a null."
        )

    def record_baseline_exclusion(self, observation_id: str) -> None:
        """A prompt whose control is not at the origin pole. Counted, reported."""
        self.baseline_not_at_origin_pole.append(observation_id)

    @property
    def denominator(self) -> int:
        """Scored generations only. Nothing void, nothing refused, nothing excluded."""
        return len(self.scored)

    @property
    def observations_seen(self) -> int:
        return (
            self.denominator
            + sum(len(ids) for ids in self.refusals.values())
            + len(self.baseline_not_at_origin_pole)
        )

    def class_counts(self) -> dict[str, int]:
        counts = dict.fromkeys(OUTCOME_CLASSES, 0)
        for generation in self.scored:
            counts[generation.outcome_class] += 1
        return counts

    def rate(self, outcome_class: str) -> float:
        """A rate over the SCORED denominator, refusing an empty one."""
        if outcome_class not in OUTCOME_CLASSES:
            raise CausalOutcomeError(f"{outcome_class!r} is not one of {OUTCOME_CLASSES}")
        self.assert_not_vacuous(f"rate({outcome_class})")
        return self.class_counts()[outcome_class] / self.denominator

    def assert_not_vacuous(self, what: str) -> None:
        if self.denominator <= 0:
            raise VacuousTally(
                f"{what} was requested over {self.denominator} scored generation(s) in cell "
                f"{self.cell!r}. The void and refused counts are "
                f"{ {name: len(ids) for name, ids in self.refusals.items() if ids} }, and none of "
                f"them may enter a denominator. This cell is NOT a null: it is NOT EXERCISED, and "
                f"the two are different findings."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "observations_seen": self.observations_seen,
            "denominator_scored": self.denominator,
            "class_counts": self.class_counts(),
            "refused_by_reason": {name: len(ids) for name, ids in sorted(self.refusals.items())},
            "refused_observation_ids": {
                name: list(ids) for name, ids in sorted(self.refusals.items()) if ids
            },
            "baseline_not_at_origin_pole": len(self.baseline_not_at_origin_pole),
            "void_and_not_exercised_are_not_nulls": STATE_IS_NOT_A_NULL,
            "denominator_rule": (
                "denominator_scored counts APPLIED and CONTROL generations only. Every count under "
                "refused_by_reason and baseline_not_at_origin_pole is EXCLUDED from it."
            ),
        }


def assert_two_axes_travel_together(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """REFUSE a record carrying the signed difference without the level.

    RULING_15 R2 condition 2, made a check rather than a sentence. Written
    against a RECORD because the fabrication is a record: `BipolarReading`
    cannot omit either axis, so a guard runnable only on the object that cannot
    fail it would be decorative. Also refuses the raw per-referent counts being
    dropped -- a derived pair is a COLLAPSE of the counts and a collapse cannot
    be un-collapsed later (the depth-vector retention rule at sequence 42).

    And it refuses reading a zero difference as neutral: zero is at least three
    states and the instrument now distinguishes them."""
    if "signed" not in record:
        return record
    for required in ("assertion_level", "raw_counts_retained"):
        if required not in record:
            raise TwoAxesSeparated(
                f"a record carries 'signed' without {required!r}. The outcome variable is the PAIR "
                f"(signed difference, assertion level) with both raw per-referent counts retained; "
                f"the difference alone is not injective over ASSERTS_BOTH, ASSERTS_NEITHER and "
                f"NEUTRAL, which RULING_13 Q4 clause 3 requires to be distinct."
            )
    counts = dict(record["raw_counts_retained"])
    if len(counts) != 2:
        raise TwoAxesSeparated(
            f"raw_counts_retained holds {len(counts)} referent(s); the construction is over exactly "
            f"two disjoint referents."
        )
    signed = float(record["signed"])
    level = float(record["assertion_level"])
    own, mirror = (float(value) for value in counts.values())
    if abs(own - mirror) != abs(signed) or (own + mirror) != level:
        raise TwoAxesSeparated(
            f"the retained counts {counts} do not reproduce signed={signed} and "
            f"assertion_level={level}. A record whose derived pair disagrees with its own counts "
            f"cannot be audited, and the counts are the thing that survives the collapse."
        )
    return record


def assert_denominator_excludes_void(tally: Mapping[str, Any]) -> Mapping[str, Any]:
    """FALSIFIER. Refuse a record whose denominator absorbed a void count.

    The fabrication this must catch is a tally dict that reports its void
    counts honestly AND adds them into the denominator anyway, so that a
    no-op ablation is scored as a failure to steer. Written against the RECORD
    rather than against `CellTally`, because the fabrication is a record: a
    `CellTally` cannot do it, and a check that can only be run on the object
    that cannot fail it is decorative."""
    for required in ("observations_seen", "denominator_scored", "refused_by_reason"):
        if required not in tally:
            raise StateCollapsed(
                f"a tally record has no {required!r}; without it the denominator cannot be checked "
                f"at all, and an uncheckable denominator passes vacuously."
            )
    seen = int(tally["observations_seen"])
    scored = int(tally["denominator_scored"])
    refused = sum(int(value) for value in dict(tally["refused_by_reason"]).values())
    excluded = int(tally.get("baseline_not_at_origin_pole", 0))
    if scored + refused + excluded != seen:
        raise StateCollapsed(
            f"denominator_scored={scored} plus {refused} refused plus {excluded} baseline-excluded "
            f"is {scored + refused + excluded}, not observations_seen={seen}. Either a void run is "
            f"inside the denominator or an observation is unaccounted for; both are the same "
            f"defect, a state collapsed into a number."
        )
    if refused and scored >= seen:
        raise StateCollapsed(
            f"{refused} refusal(s) recorded and yet denominator_scored={scored} accounts for all "
            f"{seen} observation(s). A void run cannot be both excluded and counted."
        )
    return tally


def summarise_states(tallies: Iterable[CellTally]) -> dict[str, Any]:
    """Per-cell first, and a pooled figure only ALONGSIDE the vector.

    "A pooled scalar rate is PROHIBITED as the headline and permitted only
    alongside the vector" (RULING_13 Q2 clause 0). The dict shape enforces the
    ordering by construction: there is no way to obtain the pooled figure from
    this function without the per-cell vector in the same object."""
    rows = [tally.to_dict() for tally in tallies]
    if not rows:
        raise VacuousTally(
            "summarise_states was called with no cells, so it would report a pooled figure over "
            "nothing. An aggregate over an empty set is the defect Engineer 1 hit with a coverage "
            "check that passed over zero features."
        )
    return {
        "per_cell": rows,
        "cells": [row["cell"] for row in rows],
        "pooled_only_alongside_the_vector": {
            "denominator_scored": sum(row["denominator_scored"] for row in rows),
            "observations_seen": sum(row["observations_seen"] for row in rows),
            "refused_by_reason": {
                bucket: sum(row["refused_by_reason"].get(bucket, 0) for row in rows)
                for bucket in REFUSAL_BUCKETS
            },
            "headline_rule": (
                "THE HEADLINE IS THE PER-CELL VECTOR. This pooled block is permitted only "
                "alongside it and may never be reported on its own."
            ),
        },
    }



# --------------------------------------------------------------------------
# RULING_15 R1 clause 7: ADOPTION IS CONDITIONAL ON THIS, AND IT RUNS TODAY.
# --------------------------------------------------------------------------

FROZEN_ROW_FALSIFIER_SCOPE = """WHAT THIS CHECK DISCHARGES, AND WHAT IT DOES NOT.

RULING_15 adopts CLAIM_TYPE_EXTENT conditionally, on a falsifier over the frozen
corpus with answers known IN ADVANCE from the corpus's own structure. The check
needs no GPU and no generation: it scores frozen text.

DISCHARGES: the SIGN, and the 0/1 anchors. The near_miss rows are BYTE COPIES of
the mirror concept's positives, so requiring 1 on the MIRROR referent and 0 on
its own exercises the ORIENTATION against a pre-known answer -- not merely the
magnitude. The neutral and unrelated rows exercise the ASSERTS_NEITHER anchor and
scale_min = 0 on real text.

DOES NOT DISCHARGE, AND THIS IS THE DEFECT CLASS IN A NEW PLACE: by T5 every
frozen positive row instantiates EXACTLY ONE claim type, so this check exercises
only levels 0 and 1 of a seven-level scale. LEVELS 2 TO 6 ARE UNEXERCISED BY
EVERY ROW IN THE FROZEN CORPUS. A validation set that cannot reach five of seven
levels is a check unable to exercise what it claims to cover, and reporting this
as "the scale is validated" would be exactly that defect. Resolution and rank
reliability at levels 2 and above must be MEASURED ON CONTROL GENERATIONS before
the first intervened generation is scored, and until they are, every pin must
state that THE UPPER LATTICE IS UNEXERCISED.

WHICH WAY A DISAGREEMENT CUTS: it disqualifies THE SCALE and is REFERRED for the
row. It is NOT a corpus verdict in either direction. The frozen label is the
PREDICTION and the instrument is the TEST, so a disagreement falsifies one of the
two and says which only after someone with standing looks. This check is NOT a
corpus certification and may not be converted into one."""

#: The splits and their pre-known answers. `None` means REPORTED ONLY: an
#: eliciting prompt is not an assertion, and inventing an expectation for it
#: would be the topic-versus-stance error the frozen definition names as the
#: single most likely authoring mistake.
FROZEN_ROW_EXPECTATIONS: dict[str, tuple[int | None, int | None]] = {
    "positive": (1, 0),
    "near_miss": (0, 1),
    "heldout_neutral": (0, 0),
    "unrelated": (0, 0),
    "heldout_eliciting": (None, None),
}


class ScaleNotAdopted(CausalOutcomeError):
    """The frozen-row falsifier failed, so CLAIM_TYPE_EXTENT is not adopted."""


@dataclass(frozen=True)
class FrozenRowFalsifierResult:
    """The outcome of R1 clause 7, with the honest scope attached."""

    rows_scored: int
    disqualifying: tuple[str, ...]
    per_split_counts: Mapping[str, int]
    reported_only: int
    levels_exercised: tuple[int, ...]

    @property
    def adopted(self) -> bool:
        return not self.disqualifying

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_scored": self.rows_scored,
            "adopted": self.adopted,
            "disqualifying": list(self.disqualifying),
            "per_split_counts": dict(self.per_split_counts),
            "reported_only": self.reported_only,
            "levels_exercised": list(self.levels_exercised),
            "levels_unexercised": [
                level
                for level in range(int(CLAIM_TYPE_EXTENT_SCALE_MAX) + 1)
                if level not in self.levels_exercised
            ],
            "upper_lattice_is_unexercised": sorted(self.levels_exercised) != list(
                range(int(CLAIM_TYPE_EXTENT_SCALE_MAX) + 1)
            ),
            "scope": FROZEN_ROW_FALSIFIER_SCOPE,
            "new_reading": THE_COUNT_IS_A_NEW_READING_NOT_AN_APPLICATION_OF_T5,
        }


def load_frozen_rows(path: Path | None = None) -> list[dict[str, str]]:
    """The frozen corpus, read as bytes. No CRLF tolerance."""
    target = Path(path) if path is not None else REPO_ROOT / FROZEN_PROMPT_SETS_PATH
    raw = target.read_bytes()
    if b"\r\n" in raw:
        raise CausalOutcomeError(
            f"{target.name} contains CRLF, so its bytes are not the frozen bytes."
        )
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def run_frozen_row_falsifier(
    instrument: Any, rows: Sequence[Mapping[str, str]] | None = None
) -> FrozenRowFalsifierResult:
    """Score every frozen row and compare against answers known IN ADVANCE.

    `instrument` is any callable `(text, referent_concept_id) -> int` emitting
    CLAIM_TYPE_EXTENT, plus an optional `claim_types(text, referent)` returning
    which of the six were found, used only to check a positive row's TYPE against
    its frozen label. No instrument is supplied by this module: authoring it is
    R3's and its author must clear all five exclusions."""
    rows = list(rows) if rows is not None else load_frozen_rows()
    if not rows:
        raise ScaleNotAdopted(
            "the falsifier was handed zero rows, so it would report adoption over nothing -- an "
            "aggregate over an empty set, the defect this sprint keeps finding."
        )
    disqualifying: list[str] = []
    per_split: dict[str, int] = {}
    reported_only = 0
    levels: set[int] = set()
    for row in rows:
        split = str(row.get("split", ""))
        if split not in FROZEN_ROW_EXPECTATIONS:
            disqualifying.append(f"{row.get('prompt_id')}: unknown split {split!r}")
            continue
        per_split[split] = per_split.get(split, 0) + 1
        own_concept = str(row["concept_id"])
        mirror_concept = next(
            (name for name in PERSONA_CONCEPT_IDS if name != own_concept), own_concept
        )
        text = str(row["text"])
        own_extent = int(instrument(text, own_concept))
        mirror_extent = int(instrument(text, mirror_concept))
        levels.update({own_extent, mirror_extent})
        expected_own, expected_mirror = FROZEN_ROW_EXPECTATIONS[split]
        if expected_own is None:
            reported_only += 1
            continue
        if own_extent != expected_own:
            disqualifying.append(
                f"{row.get('prompt_id')} ({split}): own extent {own_extent}, expected {expected_own}"
            )
        if mirror_extent != expected_mirror:
            disqualifying.append(
                f"{row.get('prompt_id')} ({split}): mirror extent {mirror_extent}, expected "
                f"{expected_mirror}"
            )
        if split == "positive" and hasattr(instrument, "claim_types"):
            found = tuple(instrument.claim_types(text, own_concept))
            if found != (str(row["claim_type"]),):
                disqualifying.append(
                    f"{row.get('prompt_id')} (positive): found claim type(s) {list(found)}, frozen "
                    f"label {row['claim_type']!r}"
                )
    return FrozenRowFalsifierResult(
        rows_scored=len(rows),
        disqualifying=tuple(disqualifying),
        per_split_counts=per_split,
        reported_only=reported_only,
        levels_exercised=tuple(sorted(levels)),
    )


def assert_scale_is_adopted(result: FrozenRowFalsifierResult) -> FrozenRowFalsifierResult:
    """REFUSE to treat the scale as adopted on a failing falsifier."""
    if not result.adopted:
        raise ScaleNotAdopted(
            f"{len(result.disqualifying)} disqualifying row(s); CLAIM_TYPE_EXTENT is NOT ADOPTED. "
            f"First few: {list(result.disqualifying[:5])}. A disagreement disqualifies THE SCALE "
            f"and is REFERRED for the row; it is NOT a corpus verdict in either direction."
        )
    return result


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


def _selfcheck() -> int:
    """Refusals first, with real output. No thresholds, no weights, no cluster."""
    failures = 0

    def expect_refusal(what: str, call: Any, *expected: type[BaseException]) -> None:
        nonlocal failures
        try:
            call()
        except expected as error:
            print(f"  REFUSED {what}: {type(error).__name__}: {str(error)[:150]}")
            return
        except Exception as error:  # pragma: no cover - surfaced, never swallowed
            failures += 1
            print(f"  WRONG ERROR {what}: {type(error).__name__}: {error}")
            return
        failures += 1
        print(f"  DID NOT REFUSE {what} -- the check does not exercise what it claims")

    _print("the outcome measure is REFERRED, so the real path refuses")
    print(OUTCOME_MEASURE_REFERRAL.splitlines()[0])
    expect_refusal(
        "a rubric with no sanctioning authority",
        lambda: RubricAttestation(
            rubric_id="x",
            rubric_version="1",
            digest="0" * 64,
            scale_min=0.0,
            scale_max=6.0,
            resolution=1.0,
            composition=COMPOSITION_SIGNED_DIFFERENCE,
            anchors_digest="1" * 64,
            rank_reliability_evidence="reports/SYNTHETIC_no_rank_reliability_measured.md@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            sanctioned_by="   ",
            authored_by="somebody",
        ),
        OutcomeMeasureNotSanctioned,
    )
    expect_refusal(
        "a rubric with no measured rank reliability",
        lambda: RubricAttestation(
            rubric_id="x",
            rubric_version="1",
            digest="0" * 64,
            scale_min=0.0,
            scale_max=6.0,
            resolution=1.0,
            composition=COMPOSITION_SIGNED_DIFFERENCE,
            anchors_digest="1" * 64,
            rank_reliability_evidence="",
            sanctioned_by="a ruling",
            authored_by="somebody",
        ),
        OutcomeMeasureNotSanctioned,
    )

    rubric = RubricAttestation(
        rubric_id="SYNTHETIC-NOT-A-REAL-RUBRIC",
        rubric_version="0.0.0",
        digest="a" * 64,
        scale_min=0.0,
        scale_max=6.0,
        resolution=1.0,
        composition=COMPOSITION_SIGNED_DIFFERENCE,
        anchors_digest="b" * 64,
        rank_reliability_evidence="reports/SYNTHETIC_no_rank_reliability_measured.md@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        sanctioned_by="SYNTHETIC: nothing sanctions this; it exists to exercise the arithmetic",
        authored_by="selfcheck_fixture",
    )
    five_lanes = {
        "description_author": "pm",
        "corpus_author": "corpus_author",
        "selecting_lane": "engineer2",
        "calibrating_lane": "researcher",
        "generating_lane": "engineer1",
    }
    for role in INSTRUMENT_AUTHOR_EXCLUSIONS:
        expect_refusal(
            f"a rubric authored by the {role}",
            lambda role=role: assert_separation_of_duties(
                RubricAttestation(**{**rubric.__dict__, "authored_by": five_lanes[role]}),
                **five_lanes,
            ),
            OutcomeMeasureNotSanctioned,
        )
    expect_refusal(
        "a separation with one role left unsupplied",
        lambda: assert_separation_of_duties(
            rubric, **{k: v for k, v in five_lanes.items() if k != "generating_lane"}
        ),
        OutcomeMeasureNotSanctioned,
    )
    print(
        f"  PERMITTED: author {rubric.authored_by!r} clears all "
        f"{len(INSTRUMENT_AUTHOR_EXCLUSIONS)} exclusions"
    )
    assert_separation_of_duties(rubric, **five_lanes)

    _print("the firing precondition refuses every void state")
    bands = OutcomeBands(
        neutral_low=-1.0,
        neutral_high=1.0,
        assertion_floor=4.0,
        calibration_digest="c" * 64,
        derivation="SYNTHETIC selfcheck band; a real one comes from causal_calibration.calibrate",
    )

    def evidence(**overrides: Any) -> FiringEvidence:
        base = {
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
        base.update(overrides)
        return FiringEvidence(**base)  # type: ignore[arg-type]

    def reading(own: float, mirror: float) -> BipolarReading:
        return BipolarReading(
            own=PoleReading(PERSONA_CONCEPT_IDS[0], own, rubric),
            mirror=PoleReading(PERSONA_CONCEPT_IDS[1], mirror, rubric),
        )

    for state in ("NOT_EXERCISED", "FIRED_BUT_INERT"):
        expect_refusal(
            f"scoring a {state} generation",
            lambda state=state: score_generation(
                observation_id=f"obs-{state}",
                cell="en/f1",
                prompt_id="p1",
                seed=7,
                arm_label="ablate-A",
                kind="ablate",
                reading=reading(0.0, 0.0),
                firing=evidence(intervention_state=state, hook_call_count=0, max_abs_delta=0.0),
                bands=bands,
                member_count=2,
            ),
            FiringPreconditionUnmet,
        )
    expect_refusal(
        "scoring an absorbed intervention (bf16)",
        lambda: score_generation(
            observation_id="obs-absorbed",
            cell="en/f1",
            prompt_id="p1",
            seed=7,
            arm_label="amplify-B",
            kind="amplify",
            reading=reading(4.0, 0.0),
            firing=evidence(absorbed_element_count=157),
            bands=bands,
            member_count=2,
        ),
        InterventionAbsorbed,
    )
    expect_refusal(
        "scoring an amplify arm with a zero-dosed member (corpus_max == 0)",
        lambda: score_generation(
            observation_id="obs-zero-dose",
            cell="en/f1",
            prompt_id="p1",
            seed=7,
            arm_label="amplify-B",
            kind="amplify",
            reading=reading(4.0, 0.0),
            firing=evidence(evaluated_member_doses=(2.0, 0.0)),
            bands=bands,
            member_count=2,
        ),
        ZeroDoseRefused,
    )
    expect_refusal(
        "firing evidence with a missing field",
        lambda: from_prompt_row({"intervention_state": "APPLIED"}),
        FiringEvidenceMissing,
    )

    _print("the two axes separate ASSERTS_BOTH from ASSERTS_NEITHER")
    for own, mirror in ((6.0, 5.0), (0.0, 0.0), (5.0, 0.0), (0.0, 5.0), (1.0, 1.0)):
        composed = reading(own, mirror)
        print(
            f"  own={own} mirror={mirror} -> signed={composed.signed:+.1f} "
            f"assertion={composed.assertion_level:.1f} class={classify_bipolar(composed, bands)}"
        )
    both = reading(6.0, 5.0)
    neither = reading(0.0, 0.0)
    if both.signed == neither.signed and classify_bipolar(both, bands) == classify_bipolar(
        neither, bands
    ):  # pragma: no cover - the whole point of the second axis
        failures += 1
        print("  COLLAPSED: a signed difference alone cannot tell BOTH from NEITHER")
    else:
        print("  PROVEN: equal signed scores, different classes -- the second axis is load-bearing")

    _print("the ORIENTATION IS DERIVED: no default, and a contradiction refuses")
    forward = JointCondition(
        ablated_concept_id=PERSONA_CONCEPT_IDS[1],
        amplified_concept_id=PERSONA_CONCEPT_IDS[0],
        own_concept_id=PERSONA_CONCEPT_IDS[0],
        mirror_concept_id=PERSONA_CONCEPT_IDS[1],
    )
    print(f"  ablate mirror -> origin {forward.origin_pole}, target {forward.target_pole}")
    print(
        f"  ablate own    -> origin {forward.mirrored().origin_pole}, "
        f"target {forward.mirrored().target_pole}"
    )
    expect_refusal(
        "a supplied orientation that contradicts the condition",
        lambda: assert_orientation_agrees(forward, "POLE_OWN"),
        OrientationContradicted,
    )
    expect_refusal(
        "a condition intervening on concepts that are not the scored referents",
        lambda: JointCondition(
            ablated_concept_id="cheese",
            amplified_concept_id=PERSONA_CONCEPT_IDS[0],
            own_concept_id=PERSONA_CONCEPT_IDS[0],
            mirror_concept_id=PERSONA_CONCEPT_IDS[1],
        ),
        OrientationNotDerivable,
    )
    expect_refusal(
        "a condition that ablates and amplifies the same concept",
        lambda: JointCondition(
            ablated_concept_id=PERSONA_CONCEPT_IDS[0],
            amplified_concept_id=PERSONA_CONCEPT_IDS[0],
            own_concept_id=PERSONA_CONCEPT_IDS[0],
            mirror_concept_id=PERSONA_CONCEPT_IDS[1],
        ),
        OrientationNotDerivable,
    )

    _print("crossing is baseline-conditioned and ASSERTS_BOTH is not a flip")
    for control_class, intervened_class in (
        ("POLE_MIRROR", "POLE_OWN"),
        ("POLE_MIRROR", "ASSERTS_BOTH"),
        ("POLE_MIRROR", "NEUTRAL"),
        ("POLE_OWN", "POLE_OWN"),
        ("NEUTRAL", "POLE_OWN"),
    ):
        print(
            f"  control={control_class:12s} intervened={intervened_class:12s} -> "
            f"crosses={crosses_under(forward, control_class, intervened_class)} "
            f"admissible={baseline_is_at_origin_pole(control_class, origin_pole=forward.origin_pole)}"
        )

    _print("a tally keeps the void states out of the denominator")
    tally = CellTally(cell="en/f1")
    scored = score_generation(
        observation_id="obs-ok",
        cell="en/f1",
        prompt_id="p1",
        seed=7,
        arm_label="amplify-B",
        kind="amplify",
        reading=reading(5.0, 0.0),
        firing=evidence(),
        bands=bands,
        member_count=2,
    )
    tally.add(scored)
    for observation_id, state in (("obs-a", "NOT_EXERCISED"), ("obs-b", "FIRED_BUT_INERT")):
        try:
            score_generation(
                observation_id=observation_id,
                cell="en/f1",
                prompt_id="p2",
                seed=7,
                arm_label="ablate-A",
                kind="ablate",
                reading=reading(0.0, 0.0),
                firing=evidence(intervention_state=state, hook_call_count=0, max_abs_delta=0.0),
                bands=bands,
                member_count=2,
            )
        except CausalOutcomeError as error:
            print(f"  {observation_id} -> bucket {tally.record_refusal(observation_id, error)!r}")
    record = tally.to_dict()
    print(
        f"  observations_seen={record['observations_seen']} "
        f"denominator_scored={record['denominator_scored']} "
        f"refused={record['refused_by_reason']}"
    )
    assert_denominator_excludes_void(record)
    print("  PROVEN: the honest record passes assert_denominator_excludes_void")
    forged = dict(record)
    forged["denominator_scored"] = record["observations_seen"]
    expect_refusal(
        "a forged record that folds the void counts into the denominator",
        lambda: assert_denominator_excludes_void(forged),
        StateCollapsed,
    )
    empty = CellTally(cell="fr/f2")
    expect_refusal(
        "a rate over an empty scored set",
        lambda: empty.rate("POLE_OWN"),
        VacuousTally,
    )

    _print("the mirrored state vocabulary is compared, not assumed")
    try:
        print(f"  intervention lane states: {assert_state_vocabulary_matches_intervention_lane()}")
    except Exception as error:  # pragma: no cover - reported, never swallowed
        failures += 1
        print(f"  DRIFT/UNAVAILABLE: {type(error).__name__}: {str(error)[:200]}")

    _print("what only real weights can settle")
    for item in UNEXERCISED_WITHOUT_GPU:
        print(f"  - {item}")

    _print("result")
    print("FAILURES:", failures)
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selfcheck", action="store_true", help="run the refusal demonstration")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selfcheck:
        return _selfcheck()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
