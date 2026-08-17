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

OUTCOME_MEASURE_REFERRAL = """REFERRED UP, NOT INVENTED HERE: the ordinal scale of the outcome measure.

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
                f"ordinal scale with no span cannot express an intensity."
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


def assert_separation_of_duties(
    attestation: RubricAttestation, *, calibrating_lane: str, selecting_lane: str
) -> dict[str, str]:
    """The rubric's author may be neither the calibrator nor the selector.

    Same separation the sprint already applies to the committer, to the
    corpus-implements-definition instrument and to the entity-discriminator
    calibrator, and for the reason RULING_2 gives verbatim: every failure in
    this sprint's catalogue that survived review did so because someone with
    the ability to make a check pass encountered a check that was failing."""
    author = str(attestation.authored_by).strip().lower()
    for role, lane in (("calibrating_lane", calibrating_lane), ("selecting_lane", selecting_lane)):
        if not str(lane).strip():
            raise OutcomeMeasureNotSanctioned(
                f"{role} is empty, so the separation cannot be checked at all, and an "
                f"unenforceable separation passes vacuously."
            )
        if author == str(lane).strip().lower():
            raise OutcomeMeasureNotSanctioned(
                f"the rubric is authored by {attestation.authored_by!r}, which is the "
                f"{role.replace('_', ' ')}. A measure authored and then calibrated (or authored "
                f"and then selected against) by one lane is one party marking its own work."
            )
    return {
        "rubric_authored_by": attestation.authored_by,
        "calibrating_lane": calibrating_lane,
        "selecting_lane": selecting_lane,
        "separation": "SATISFIED",
    }


# --------------------------------------------------------------------------
# The two-axis reading.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PoleReading:
    """One pole's ordinal intensity on one generation, with its instrument."""

    concept_id: str
    intensity: float
    rubric: RubricAttestation

    def __post_init__(self) -> None:
        value = float(self.intensity)
        if not (float(self.rubric.scale_min) <= value <= float(self.rubric.scale_max)):
            raise OrdinalScaleViolation(
                f"intensity {value} for {self.concept_id!r} is outside its rubric's declared scale "
                f"[{self.rubric.scale_min}, {self.rubric.scale_max}]. A reading off its own scale "
                f"is not a weaker reading; it is a broken instrument."
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
        return float(self.own.intensity) - float(self.mirror.intensity)

    @property
    def assertion_level(self) -> float:
        """own + mirror. The axis a signed difference throws away."""
        return float(self.own.intensity) + float(self.mirror.intensity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "own_concept_id": self.own.concept_id,
            "own_intensity": float(self.own.intensity),
            "mirror_concept_id": self.mirror.concept_id,
            "mirror_intensity": float(self.mirror.intensity),
            "signed": self.signed,
            "assertion_level": self.assertion_level,
            "composition": self.rubric.composition,
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


def crosses(
    control_class: str, intervened_class: str, *, origin_pole: str = "POLE_MIRROR"
) -> bool:
    """Did the score CROSS the band, from the origin pole to the other one?

    RULING_13 Q4 clause 4: "The score must CROSS the neutral band, not merely
    shift within the origin pole -- strongly-pro-A to weakly-pro-A is not a
    flip", and it is measured only on prompts whose CONTROL sits at the origin
    pole. A move into ASSERTS_BOTH is NOT a crossing: it is its own outcome
    class, and calling it a flip is the two-boolean defect returning by the
    back door."""
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
            rank_reliability_evidence="measured",
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
        rank_reliability_evidence="SYNTHETIC: no rank reliability has been measured for any axis",
        sanctioned_by="SYNTHETIC: nothing sanctions this; it exists to exercise the arithmetic",
        authored_by="selfcheck_fixture",
    )
    expect_refusal(
        "a rubric authored by the calibrating lane",
        lambda: assert_separation_of_duties(
            rubric, calibrating_lane="selfcheck_fixture", selecting_lane="engineer2"
        ),
        OutcomeMeasureNotSanctioned,
    )

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
            f"crosses={crosses(control_class, intervened_class)} "
            f"admissible={baseline_is_at_origin_pole(control_class, origin_pole='POLE_MIRROR')}"
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
