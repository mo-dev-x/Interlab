"""THE CONTROL-ONLY CALIBRATION, and the pin that has to predate the results.

WHAT THIS MODULE IS FOR
-----------------------
RULING_13 Q2 clause 2, verbatim: "Margin and ceiling come from a CONTROL-ONLY
CALIBRATION containing ZERO intervened generations, pinned by hash, BEFORE any
intervened generation is scored, by the calibrating lane -- which is not the
group-selecting lane. This preserves pre-registration without my inventing a
number I have no basis for, and makes fitting STRUCTURALLY IMPOSSIBLE rather
than merely prohibited."

Everything here follows from that sentence. The three hard parts, and how each
is discharged structurally rather than by discipline:

1. NO NUMBER MAY BE INVENTED, TUNED, DEFAULTED OR HARDCODED. Every boundary
   below is an EXACT ORDER STATISTIC of the control set, or an exact function
   of one, with NO FREE LEVEL PARAMETER. There is no quantile level to pick,
   because picking one is picking a number. What a level-free bound costs is
   stated rather than hidden: its coverage is a CONSEQUENCE of the sample size
   (`attained_coverage_level`), so the calibration REPORTS the level it
   achieved instead of asserting one it wanted. `test_causal_calibration.py`
   runs the derivation on a 3-observation and a 9-observation set and asserts
   3/4 and 9/10 -- a stored literal passes neither.

2. A CALIBRATION OVER AN EMPTY OR DEGENERATE CONTROL SET MUST REFUSE. It would
   otherwise happily produce a threshold, which is the sprint's defect class in
   its purest form: Engineer 1 hit the empty-set version when a coverage check
   passed over zero features. Every refusal here STATES THE MINIMUM IT REQUIRES
   and where that minimum comes from -- and the minimum is DERIVED (a one-sided
   distribution-free bound at n=1 attains exactly 1/2, which cannot separate
   the null from anything), never chosen.

3. PINNING AFTER THE FACT IS THE WHOLE THING THE RULE EXISTS TO PREVENT. So
   the pin carries a self-digest over its own canonical bytes, and the module
   SEALS on first use: once any intervened generation has been scored against a
   pin, `calibrate` refuses to produce another one in that process. A pin file
   also refuses to be overwritten with different bytes, the same discipline
   `post_report.py` adopted after two rulings were destroyed by an overwrite.

WHAT THIS LANE IS AND IS NOT
----------------------------
It calibrates and it does NOT SELECT, RANK OR PREFER A FEATURE GROUP. That is
the binding half: RULING_13 and RULING_14 both state that calibration "is VOID
if that lane also selects the group". Nothing in this file reads an
admissibility matrix, a coverage certificate, a depth vector or a candidate
group, and `tests/test_causal_calibration.py` asserts over the file that it
imports no selection symbol.

A COORDINATION ITEM, FLAGGED NOT DECIDED
----------------------------------------
See `CALIBRATION_ASSIGNMENT_IS_A_COORDINATION_RECORD`. RULING_13's STANDING
block names engineer3 as the calibrator by an earlier coordinator assignment
and says naming any other owner "remains a coordination decision and is not
mine". This file is authored by the researcher lane on a coordinator
instruction that is not yet in any protocol artifact, and the frozen precedent
(`entity_discriminator_calibrator_assignment.json`) shows what recording one
looks like. The assignment needs recording; this file cannot record it.
"""

from __future__ import annotations

import datetime as _datetime
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import causal_outcome
from causal_outcome import (
    OUTCOME_CLASSES,
    OutcomeBands,
    RubricAttestation,
    ScoredGeneration,
    canonical_json,
    sha256_hex,
)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

#: LOADED BY FILE IDENTITY, not by name. `scripts/legacy/` holds a same-named
#: 23-line stub of another module in this lane, and putting that directory on
#: `sys.path` once made a device gate resolve to an empty function -- present
#: BY NAME and doing nothing. Checking the resolved path costs one comparison
#: and is the difference between importing a module and importing its name.
_OUTCOME_FILE = SCRIPT_DIR / "causal_outcome.py"
if Path(causal_outcome.__file__).resolve() != _OUTCOME_FILE.resolve():  # pragma: no cover
    raise ImportError(
        f"'causal_outcome' resolved to {causal_outcome.__file__}, not {_OUTCOME_FILE}. Refusing to "
        f"calibrate against an outcome measure loaded from somewhere else."
    )

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

CALIBRATION_ASSIGNMENT_IS_A_COORDINATION_RECORD = """WHO CALIBRATES IS NOT SETTLED BY THIS FILE.

The constraint is frozen and is satisfied here: the calibrating lane must be
NEITHER the group-selecting lane, NOR the description author, NOR the corpus
author (prompts/final_pairing/v2/concept_description_persona_exceptionalism.json,
RESIDUAL_ASYMMETRIES.2.THE_PRE_REGISTERED_GRADED_READING.calibration_procedure.who_sets_it),
and RULING_13/RULING_14 add that the calibration is VOID if the calibrating
lane also selects the group.

The IDENTITY is a coordinator decision and the architect says so explicitly:
"Calibration is engineer3's by the coordinator's assignment and is VOID if that
lane also selects the group; naming any other owner remains a coordination
decision and is not mine" (RULING_13 STANDING.who_does_what, repeated at
RULING_14 STANDING.who_does_what).

TWO ASSIGNMENTS ARE THEREFORE IN PLAY AND THEY ARE NOT THE SAME QUANTITY:
  (a) THE ENTITY-DISCRIMINATOR number -- the numeric form of "materially
      below" for the STANCE signature, on the corpus-max activation
      distribution over three substrates. ASSIGNED TO engineer3 in
      protocols/final_pairing/v1/entity_discriminator_calibrator_assignment.json,
      THE_ASSIGNMENT.CALIBRATING_LANE. NOT TOUCHED BY THIS FILE, and this file
      computes nothing on that substrate.
  (b) THE CAUSAL margin, ceiling and crossing band -- what this file computes.
      There is no protocol artifact assigning it. The coordinator instructed
      this lane to build it; the instruction is not a recorded assignment.

WHAT IS NEEDED, AND WHY THE GAP MATTERS RATHER THAN BEING PEDANTRY: the frozen
rule is that "who sets the number" is PRE-REGISTERED. A calibration whose owner
was never recorded can be argued after the fact to have been performed by
whoever the result suits, which is precisely the failure mode the
pre-registration exists against. The remedy is cheap and has a template: one
protocol artifact of the same shape as (a), naming the lane, by the
coordinator, recorded by someone who neither selects nor calibrates. Until it
exists this calibration is ENGINEERING PREVIEW like everything else in the
sprint, and `PinnedCalibration.assignment_record` carries the gap on its face
rather than leaving the field blank -- a blank reads as NOT CHECKED."""

DOSE_REFERENCE_IS_A_CONTROL_ONLY_MEASUREMENT = """THE REPLACEMENT DOSE SCALE, and what is and is not decided here.

THE DEFECT (architect, mailbox sequence 43): the clamp dose is
`value_in_max_units * corpus_max`. For a maximally selective feature
corpus_max == 0, so the product is EXACTLY ZERO -- "the amplification arm is
structurally incapable of dosing PRECISELY THE FEATURES WITH THE BEST
SPECIFICITY, and it fails silently". 89.52% of full-space cells are in that
state. Excluding those features is REFUSED: they are the most selective
candidates in the dictionary and the fault is the SCALE.

WHO OWNS IT: "NOT RULED: what the replacement reference should be for such
features. That is a calibration question, it is a control-only measurement, it
belongs to the lane that does not select the group, and I will not invent a
scale."

WHAT THIS FILE DOES, AND ITS LIMIT: it will not name a substrate either,
because a substrate choice made without the activations in hand is a guess
wearing a procedure's clothes. What it provides is the PROCEDURE: a reference
must be (i) declared by substrate, (ii) MEASURED on control-only data, (iii)
strictly positive for every member or the member REFUSES, and (iv) pinned with
the rest of the calibration so it cannot move after a dose has been scored.
`derive_dose_reference` implements exactly that and refuses when the substrate
is undeclared or the measured value is zero. NO DEFAULT SUBSTRATE IS SUPPLIED.

THE ONE THING THAT IS SETTLED, because it is arithmetic and not a choice: the
reference may not be the BACKGROUND corpus maximum, since that is the quantity
measured to be zero for exactly the features at issue. A dose referenced to
"how much this feature normally fires in the corpus" has the wrong structure
for the property "how far this feature must be pushed to change the output"."""

WHY_THE_CEILING_IS_A_FUNCTION_OF_THE_MARGIN = """THE CEILING, DERIVED, AND WHAT IT DOES NOT DO.

RULING_13 Q2 clause 2 requires a cell to pass only if "the control rate is
below a pre-registered CEILING", and gives the reason: "a cell whose control
generations already carry the concept can pass while the intervention did
nothing. The ceiling makes 'it was already there' a declared exclusion rather
than an unnoticed pass."

A CONTROL-ONLY MEASUREMENT CANNOT SAY HOW MUCH BASELINE IS TOO MUCH. That is a
judgement about headroom, and inventing it is exactly what this lane may not
do. What a control-only measurement CAN establish is the point beyond which the
required movement is ARITHMETICALLY IMPOSSIBLE: a rate cannot exceed 1, so if
the control rate is above 1 - margin, no paired delta of at least `margin`
exists to be observed. Hence `rate_ceiling = 1 - rate_margin`, an exact
function of a quantity that is itself an exact function of the controls.

WHAT IT CATCHES: a cell that cannot evidence a pass is EXCLUDED and counted
rather than reported as a fail, so a ceiling-blocked cell can never be read as
a null. That closes the specific hole the ruling names -- an unnoticed pass is
impossible when the pass is arithmetically unavailable.

WHAT IT DOES NOT CATCH, STATED PLAINLY BECAUSE A LIMIT REPORTED AS A FEATURE IS
WORSE THAN NO LIMIT: it does not exclude a cell whose control rate is merely
HIGH. A cell at 0.60 with a margin of 0.10 clears this ceiling and can pass on
a move to 0.71, and whether that is scientifically interesting at a baseline of
0.60 is a question this ceiling does not answer. A stricter ceiling is a
science decision, it is not derivable from controls alone, and it is not this
lane's to make. It is recorded in `stated_limitations` on every pinned cell.

THE FALSIFIER, and it is the shape RULING_14 required of its own derived
ceiling: change the margin and the ceiling MUST move. A stored literal passes
every test at one margin and fails this one."""

UNEXERCISED_WITHOUT_GPU = (
    "Every number this module has ever produced. No control generation exists, on either "
    "pairing, because generation needs weights and a cluster this lane has neither. The "
    "arithmetic, the derived minima and the refusals are proven on synthetic control sets; NO "
    "MARGIN, CEILING OR BAND FOR EITHER PERSONA HAS BEEN COMPUTED AND NONE MAY BE QUOTED.",
    "Whether a real control set clears the derived minimum. `minimum_controls_for_level` and the "
    "n=1 refusal are exercised on fixtures; how many control generations the budget actually "
    "affords per cell is an allocation question that is not settled and is not this lane's.",
    "Whether real controls are degenerate. A control set with zero spread on the signed axis is "
    "handled (the band widens to the rubric's declared resolution) and a control set with no "
    "second replicate REFUSES, but which of those a real run produces is unknown.",
    "The replacement dose reference. `derive_dose_reference` refuses without a declared "
    "substrate and a measured positive value, and no substrate is declared and no activation has "
    "been measured, so the amplify arm's zero-dose defect is REFUSED-AT-THE-GATE and NOT REPAIRED.",
    "Wiring the resample to the per-item probe retention. Per-item scores are retained for "
    "per-cell leaders as of commit 5b1da92, which makes resampling first-class on FUTURE grids; the "
    "resample machinery here is parameter-free and applies unchanged to any per-item series handed "
    "to it, but no grid carrying that format exists on this machine, so the gate-side uncertainty "
    "is still unmeasured and this lane's resample runs only over control OUTCOME classes.",
    "Whether the seal survives a process boundary in the real pipeline. The in-process seal and "
    "the refuse-to-overwrite-a-pin-file rule are both exercised; a pipeline that runs "
    "calibration and scoring as two separate jobs is protected by the file rule and by the "
    "digest, not by the flag.",
)


class CalibrationError(RuntimeError):
    """Base for every refusal here. There is no warn path and no fallback."""


class EmptyControlSet(CalibrationError):
    """No control observations at all, so there is no null to calibrate on."""


class ContaminatedControlSet(CalibrationError):
    """An observation that is not a control appeared in the calibration input.

    "a control-only calibration containing ZERO intervened generations". A
    single intervened row makes the null distribution partly a distribution of
    the effect being tested, which is fitting."""


class InsufficientControlSet(CalibrationError):
    """The control set cannot support the calibration. States the minimum."""


class DegenerateControlSet(CalibrationError):
    """The control set has no structure the calibration needs."""


class UnpairedControlReplicates(CalibrationError):
    """Two control replicates cover different prompts, so their rates differ
    for a reason that is not the null."""


class CalibrationSealed(CalibrationError):
    """A calibration was requested after an intervened generation was scored.

    This is the refusal that makes post-hoc pinning structurally impossible
    rather than merely prohibited."""


class CalibrationDigestMismatch(CalibrationError):
    """A pin's recomputed digest disagrees with the digest it carries."""


class PinNotPresented(CalibrationError):
    """Scoring was attempted without a pinned calibration to score against."""


class DoseReferenceUndeclared(CalibrationError):
    """A dose reference was requested with no substrate or no measurement."""


# --------------------------------------------------------------------------
# Level-free bounds: what a sample size buys, reported rather than chosen.
# --------------------------------------------------------------------------

LEVEL_FREE_DERIVATION = (
    "Every boundary is an exact order statistic of the control set (a MAXIMUM or a MINIMUM), so "
    "no quantile level is chosen anywhere. For a one-sided distribution-free bound the sample "
    "maximum of n exchangeable draws attains coverage n/(n+1) -- the probability that an "
    "independent (n+1)-th draw is not the largest of the n+1. The level is therefore a "
    "CONSEQUENCE of n and is REPORTED, never selected. Strictness runs in the safe direction: a "
    "bound at the observed extreme is harder to clear than a bound at an interior quantile, so a "
    "PASS under it is conservative and a NULL under it MAY NOT be read as an absence -- the same "
    "positive/null asymmetry RULING_13 REFERRAL A froze for the inherited gate thresholds."
)

NULL_UNDER_A_LEVEL_FREE_BOUND_REQUIRED_WORDING = (
    "no cell reached a margin set at the largest movement the control arms themselves produced; "
    "this does not establish that the group has no effect, because the bound is the observed "
    "extreme of the null rather than an interior quantile of it."
)


def attained_coverage_level(n: int) -> float:
    """n/(n+1): what the sample maximum of n control draws actually covers.

    Reported, not chosen. A FUNCTION and never a stored literal -- the
    falsifier is that n=3 must give 0.75 and n=9 must give 0.9, which no
    hardcoded value satisfies for both."""
    if n < 1:
        raise EmptyControlSet(
            f"attained_coverage_level(n={n}): a bound over fewer than one observation is not a "
            f"bound. There is no level to report because there is no order statistic."
        )
    return n / (n + 1)


def minimum_controls_for_level(level: float) -> int:
    """The smallest n whose sample maximum attains at least `level`.

    Inverse of `attained_coverage_level`. Used ONLY to answer "how many would I
    need" in a refusal message; this module never picks a level, so nothing in
    the calibration path calls it with a level of its own."""
    if not 0.0 < float(level) < 1.0:
        raise CalibrationError(
            f"level={level} must lie strictly between 0 and 1; n/(n+1) never reaches 1 and a level "
            f"of 0 is not a bound."
        )
    return max(1, math.ceil(float(level) / (1.0 - float(level))))


#: THE DERIVED MINIMUM, and it is derived rather than chosen. At n=1 the
#: sample maximum attains 1/(1+1) = 1/2 exactly: a bound that an independent
#: draw exceeds half the time separates the null from nothing at all. n=2 is
#: the smallest sample whose one-sided bound is better than a coin. There is no
#: taste in this number; it falls out of `attained_coverage_level`.
MINIMUM_CONTROL_OBSERVATIONS_PER_CELL = 2

#: Two replicates are the fewest that yield ONE null difference. With one
#: replicate there is no difference to take, so the margin would have to come
#: from somewhere other than the controls -- which is the thing forbidden.
MINIMUM_CONTROL_REPLICATES_PER_CELL = 2

MINIMUM_IS_DERIVED = (
    f"MINIMUM_CONTROL_OBSERVATIONS_PER_CELL = {MINIMUM_CONTROL_OBSERVATIONS_PER_CELL} because "
    f"attained_coverage_level(1) == 0.5 exactly, so a one-observation bound is a coin and n=2 is "
    f"the smallest sample whose one-sided distribution-free bound beats one. "
    f"MINIMUM_CONTROL_REPLICATES_PER_CELL = {MINIMUM_CONTROL_REPLICATES_PER_CELL} because P "
    f"replicates yield P*(P-1)/2 null differences, which is zero at P=1: with a single replicate "
    f"there is no observed null movement, and a margin would have to be invented. Neither number "
    f"is a threshold on the science; both are the points below which the arithmetic does not exist."
)


# --------------------------------------------------------------------------
# Control observations.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ControlObservation:
    """One CONTROL generation, already read by the outcome measure.

    `is_control` is required and checked rather than inferred from the label,
    because inferring it from a string is how an intervened arm named
    "control_ungated_set" would enter the null. RULING_13 permits an
    intervention EXPLICITLY RECORDED AS A CONTROL -- so the flag is the record,
    and `arm_label` says which control arm it was."""

    observation_id: str
    cell: str
    prompt_id: str
    seed: int
    arm_label: str
    is_control: bool
    signed: float
    assertion_level: float
    outcome_class: str

    def __post_init__(self) -> None:
        if self.outcome_class not in OUTCOME_CLASSES:
            raise CalibrationError(
                f"outcome_class={self.outcome_class!r} is not one of {OUTCOME_CLASSES}"
            )
        for name in ("observation_id", "cell", "prompt_id", "arm_label"):
            if not str(getattr(self, name)).strip():
                raise CalibrationError(f"ControlObservation.{name} is empty")

    @property
    def replicate_key(self) -> tuple[str, int]:
        """What makes two control readings of the same prompt independent."""
        return (self.arm_label, int(self.seed))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "cell": self.cell,
            "prompt_id": self.prompt_id,
            "seed": int(self.seed),
            "arm_label": self.arm_label,
            "is_control": bool(self.is_control),
            "signed": float(self.signed),
            "assertion_level": float(self.assertion_level),
            "outcome_class": self.outcome_class,
        }


def control_observation_from_scored(generation: ScoredGeneration) -> ControlObservation:
    """Adapt a scored CONTROL generation, refusing anything intervened.

    The only bridge from the outcome measure into the calibration, and it is
    one-directional on purpose: there is no function here that turns an
    intervened generation into a control observation."""
    if not generation.is_control:
        raise ContaminatedControlSet(
            f"generation {generation.observation_id!r} is in state "
            f"{generation.firing.intervention_state!r}, not CONTROL. A control-only calibration "
            f"contains ZERO intervened generations."
        )
    return ControlObservation(
        observation_id=generation.observation_id,
        cell=generation.cell,
        prompt_id=generation.prompt_id,
        seed=generation.seed,
        arm_label=generation.arm_label,
        is_control=True,
        signed=generation.signed,
        assertion_level=generation.assertion_level,
        outcome_class=generation.outcome_class,
    )


# --------------------------------------------------------------------------
# The per-cell calibration.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CellCalibration:
    """One cell's boundaries, every one of them derived from that cell only.

    PER CELL, because "this group steers the whole concept" is a PER-CELL,
    PER-LOCALE property and a pooled scalar is prohibited as the headline. A
    single pooled calibration would also silently apply one locale's null to
    the other, which is the collapse RULING_8 was about."""

    cell: str
    target_outcome_class: str
    n_control_observations: int
    n_prompts: int
    n_replicates: int
    n_null_differences: int
    neutral_low: float
    neutral_high: float
    assertion_floor: float
    rate_resolution: float
    observed_null_rate_difference_max: float
    rate_margin: float
    rate_ceiling: float
    observed_signed_min: float
    observed_signed_max: float
    rubric_resolution: float
    attained_level_signed_band: float
    attained_level_rate_margin: float
    replicate_rates: tuple[float, ...]
    control_rate_loo_spread: float
    signed_loo_spread: float
    control_rate_loo_values: tuple[float, ...]
    margin_bound_by: tuple[str, ...]

    @property
    def stated_limitations(self) -> tuple[str, ...]:
        return (
            WHY_THE_CEILING_IS_A_FUNCTION_OF_THE_MARGIN.splitlines()[0],
            (
                f"the signed band covers {self.attained_level_signed_band:.4f} of the null per "
                f"side, which is n/(n+1) at n={self.n_control_observations} and is REPORTED rather "
                f"than chosen"
            ),
            (
                f"the rate margin covers {self.attained_level_rate_margin:.4f}, which is P/(P+1) "
                f"at P={self.n_null_differences} null difference(s)"
            ),
            (
                f"THE DERIVED MINIMUM IS WHERE THE ARITHMETIC EXISTS, NOT WHERE IT IS ADEQUATE. At "
                f"the minimum of {MINIMUM_CONTROL_REPLICATES_PER_CELL} replicates there is P=1 null "
                f"difference and the margin's attained coverage is EXACTLY 1/2 -- a bound an "
                f"independent replicate exceeds half the time. This cell is at "
                f"P={self.n_null_differences}, coverage "
                f"{self.attained_level_rate_margin:.4f}. Raising it is an ALLOCATION decision (more "
                f"control replicates per cell) and is not this lane's to make; what this lane can "
                f"do is refuse to hide the number, and P/(P+1) is reported on every cell for that "
                f"reason."
            ),
            (
                f"the margin is floored at the control rate's LEAVE-ONE-PROMPT-OUT spread "
                f"({self.control_rate_loo_spread:.6f}) as well as at the observed null difference "
                f"and the 1/n resolution; it was bound by {list(self.margin_bound_by)}. So NO "
                f"PASSING CELL can have a paired delta inside the resample noise of its own control "
                f"measurement. The statistics this pipeline produces are noisier than the margins "
                f"read off them: a leave-one-positive-out spread of "
                f"62.2 lattice steps of 1/600 was MEASURED on a single feature's separation "
                f"AUROC, which is structural at 10 positives per cell."
            ),
            NULL_UNDER_A_LEVEL_FREE_BOUND_REQUIRED_WORDING,
            (
                "the rate ceiling excludes only ARITHMETIC impossibility, not a merely high "
                "baseline; a stricter ceiling is a science decision and is not derivable from "
                "controls alone"
            ),
        )

    def bands(self, calibration_digest: str) -> OutcomeBands:
        """The per-generation boundaries, carrying the pin they came from."""
        return OutcomeBands(
            neutral_low=self.neutral_low,
            neutral_high=self.neutral_high,
            assertion_floor=self.assertion_floor,
            calibration_digest=calibration_digest,
            derivation=(
                f"cell {self.cell}: neutral band is the observed control signed range "
                f"[{self.observed_signed_min}, {self.observed_signed_max}] widened to at least the "
                f"rubric's declared resolution {self.rubric_resolution}; assertion_floor is the "
                f"observed control maximum of own+mirror. Both are exact order statistics of "
                f"{self.n_control_observations} control observation(s), no level chosen. "
                f"{LEVEL_FREE_DERIVATION}"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "target_outcome_class": self.target_outcome_class,
            "n_control_observations": int(self.n_control_observations),
            "n_prompts": int(self.n_prompts),
            "n_replicates": int(self.n_replicates),
            "n_null_differences": int(self.n_null_differences),
            "neutral_low": float(self.neutral_low),
            "neutral_high": float(self.neutral_high),
            "assertion_floor": float(self.assertion_floor),
            "rate_resolution": float(self.rate_resolution),
            "observed_null_rate_difference_max": float(self.observed_null_rate_difference_max),
            "rate_margin": float(self.rate_margin),
            "rate_ceiling": float(self.rate_ceiling),
            "observed_signed_min": float(self.observed_signed_min),
            "observed_signed_max": float(self.observed_signed_max),
            "rubric_resolution": float(self.rubric_resolution),
            "attained_level_signed_band": float(self.attained_level_signed_band),
            "attained_level_rate_margin": float(self.attained_level_rate_margin),
            "replicate_rates": [float(rate) for rate in self.replicate_rates],
            "control_rate_loo_spread": float(self.control_rate_loo_spread),
            "signed_loo_spread": float(self.signed_loo_spread),
            "control_rate_loo_values": [float(value) for value in self.control_rate_loo_values],
            "margin_bound_by": list(self.margin_bound_by),
            "resample_rule": RESAMPLE_UNCERTAINTY_IS_NOT_OPTIONAL,
            "stated_limitations": list(self.stated_limitations),
        }

    @property
    def margin_is_at_least_the_resample_spread(self) -> bool:
        """THE INVARIANT. A margin below its own measurement noise would let a
        result be called significant inside the wobble of the thing it bounds."""
        return self.rate_margin >= self.control_rate_loo_spread


RESAMPLE_UNCERTAINTY_IS_NOT_OPTIONAL = """WHY THE MARGIN CARRIES A RESAMPLE FLOOR, AND WHY A POINT ESTIMATE IS NOT ENOUGH.

THE MEASUREMENT THAT FORCES THIS. Engineer 2 ran a leave-one-positive-out
resample on a synthetic fixture and measured a spread of
62.2 lattice steps of 1/600 on a SINGLE feature's separation AUROC. The magnitude is STRUCTURAL rather
than fixture-specific: the frozen corpus geometry gives 10 positives per cell, so
dropping one necessarily moves an AUROC by roughly a tenth of its range. On the
cheese data the consequence is visible:
fr/f1 clears its bar by ONE lattice step and fr/f2 misses by SIX,
and BOTH sit far inside that spread.

THE CONSEQUENCE FOR THIS LANE, STATED AS THE HAZARD IT IS: the statistics this
pipeline produces are NOISIER THAN THE MARGINS BEING READ OFF THEM. A calibration
that reported only a point estimate would let a steering result be called
significant while sitting inside the noise of its own measurement -- which is the
sprint's defect class wearing a decimal point. A margin is not conservative
because it is small; it is conservative because it is larger than the wobble of
the thing it bounds.

WHAT IS DONE ABOUT IT, WITH NO NUMBER CHOSEN. The margin is floored at the
LEAVE-ONE-PROMPT-OUT SPREAD of the control rate, alongside the two floors it
already had (the observed null difference across control replicates, and the
rate's own 1/n resolution). Leave-one-out is PARAMETER-FREE: no resample count,
no confidence level, no distributional form. It is computed on CONTROLS ONLY, so
it introduces no dependence on any intervened generation. `margin_bound_by`
records WHICH component bound the margin, so a reader can see whether the bound
came from the null, from the resolution, or from the resample noise.

THE STRUCTURAL GUARANTEE THIS BUYS, and it is asserted as an invariant rather
than hoped for: because the margin is at least the resample spread and a PASS
requires the delta to EXCEED the margin, NO PASSING CELL CAN HAVE A DELTA INSIDE
THE CONTROL RESAMPLE SPREAD. A test asserts that over every calibrated cell.
`CellVerdict.paired_delta_inside_control_resample_spread` reports the comparison
on every cell anyway, so a FAIL that is merely inside the noise is
distinguishable from a FAIL that is outside it -- two different findings that a
point estimate would render identically.

WHAT IS NOT A POINT ESTIMATE ANY MORE. Each cell now carries the FULL
leave-one-out distribution of its control rate, not just a summary: the values,
their spread, and the same for the signed band's midrange. A consumer that wants
a different summary of that distribution has the distribution.

WHAT IS STILL AHEAD OF THIS. Per-item probe scores are retained for per-cell
leaders as of commit 5b1da92 -- 10 positives, 15 near-miss and 15 unrelated per
(feature, cell) plus the pooled negative order, scoped to the union of the three
limbs' top-25. That makes resampling a FIRST-CLASS operation on future grids and
means the gate-side uncertainty can be measured rather than assumed parametric.
This module's resample machinery is parameter-free and applies unchanged to any
per-item series it is handed; wiring it to that retention format is not done and
is listed as unexercised, because no grid carrying it exists on this machine."""


def observed_spread(values: Sequence[float]) -> float:
    """max - min, refusing an empty set rather than returning zero.

    A spread of 0.0 returned over no values would read as "no uncertainty",
    which is the strongest possible claim made from the weakest possible
    evidence."""
    if not values:
        raise DegenerateControlSet(
            "observed_spread() was called with no values, so it would report zero uncertainty from "
            "zero measurements. An empty resample is not a tight one."
        )
    return max(values) - min(values)


def leave_one_prompt_out_rates(
    observations: Sequence[ControlObservation],
    *,
    target_outcome_class: str,
    prompts: Sequence[str],
) -> tuple[float, ...]:
    """The control rate recomputed with each prompt dropped from EVERY replicate.

    Dropping the prompt from every replicate rather than dropping single
    observations is what preserves the pairing: the design requires a paired
    same-seed control per prompt, so a resample that removed one replicate's
    view of a prompt would change the rate for a reason that is not the
    resample. Parameter-free, and control-only.

    Returns one rate per dropped prompt. With fewer than two prompts there is
    nothing to leave out and the resample REFUSES rather than reporting a spread
    of zero from a resample that never varied anything."""
    if len(prompts) < 2:
        raise InsufficientControlSet(
            f"a leave-one-prompt-out resample needs at least 2 prompts per cell; got "
            f"{len(prompts)}. With one prompt there is nothing to leave out, so the resample would "
            f"report a spread of ZERO -- the strongest possible uncertainty claim from a resample "
            f"that never varied anything. Engineer 2 measured a spread of "
            f"62.2 lattice steps of 1/600 on a single feature's separation AUROC under "
            f"leave-one-positive-out, which is why this refuses rather than reporting a "
            f"comfortable zero."
        )
    rates: list[float] = []
    for dropped in prompts:
        kept = [obs for obs in observations if obs.prompt_id != dropped]
        if not kept:  # pragma: no cover - the prompt-count guard forbids this
            raise DegenerateControlSet(f"dropping prompt {dropped!r} left no observations")
        hits = sum(1 for obs in kept if obs.outcome_class == target_outcome_class)
        rates.append(hits / len(kept))
    return tuple(rates)


def leave_one_prompt_out_signed_midranges(
    observations: Sequence[ControlObservation], *, prompts: Sequence[str]
) -> tuple[float, ...]:
    """The signed band's MIDRANGE recomputed with each prompt dropped.

    The band itself is a pair of order statistics, so its own leave-one-out
    behaviour is what says whether the band is a property of the control
    distribution or of one prompt. The midrange is used because it moves when
    EITHER endpoint moves, so a single prompt holding up one end of the band
    shows up here."""
    if len(prompts) < 2:
        raise InsufficientControlSet(
            f"a leave-one-prompt-out resample of the signed band needs at least 2 prompts; got "
            f"{len(prompts)}."
        )
    midranges: list[float] = []
    for dropped in prompts:
        kept = [float(obs.signed) for obs in observations if obs.prompt_id != dropped]
        if not kept:  # pragma: no cover
            raise DegenerateControlSet(f"dropping prompt {dropped!r} left no signed values")
        midranges.append((min(kept) + max(kept)) / 2.0)
    return tuple(midranges)


def _group_replicates(
    observations: Sequence[ControlObservation],
) -> dict[tuple[str, int], list[ControlObservation]]:
    groups: dict[tuple[str, int], list[ControlObservation]] = {}
    for observation in observations:
        groups.setdefault(observation.replicate_key, []).append(observation)
    return groups


def calibrate_cell(
    cell: str,
    observations: Sequence[ControlObservation],
    *,
    rubric: RubricAttestation,
    target_outcome_class: str,
) -> CellCalibration:
    """Derive one cell's boundaries, or REFUSE and say what is missing.

    Order of the refusals is deliberate: contamination first (a wrong input
    makes every later number wrong), then emptiness, then the derived minima,
    then the structural requirement that replicates be comparable. Each names
    the minimum and where the minimum comes from, because a refusal that does
    not say what would satisfy it stops a lane without telling it how to
    proceed."""
    if target_outcome_class not in OUTCOME_CLASSES:
        raise CalibrationError(
            f"target_outcome_class={target_outcome_class!r} is not one of {OUTCOME_CLASSES}"
        )
    intervened = [obs.observation_id for obs in observations if not obs.is_control]
    if intervened:
        raise ContaminatedControlSet(
            f"cell {cell!r}: {len(intervened)} observation(s) are not controls: {intervened[:8]}. A "
            f"control-only calibration contains ZERO intervened generations, so the null cannot be "
            f"partly a distribution of the effect being tested."
        )
    wrong_cell = sorted({obs.cell for obs in observations if obs.cell != cell})
    if wrong_cell:
        raise CalibrationError(
            f"cell {cell!r} received observations from {wrong_cell}. Calibrating across cells pools "
            f"one locale's null into the other's, which is the collapse RULING_8 was about."
        )
    n = len(observations)
    if n == 0:
        raise EmptyControlSet(
            f"cell {cell!r} has NO control observations. A calibration over an empty control set "
            f"would still produce numbers, which is why this refuses. MINIMUM: "
            f"{MINIMUM_CONTROL_OBSERVATIONS_PER_CELL} control observation(s) across at least "
            f"{MINIMUM_CONTROL_REPLICATES_PER_CELL} replicate(s). {MINIMUM_IS_DERIVED}"
        )
    if n < MINIMUM_CONTROL_OBSERVATIONS_PER_CELL:
        raise InsufficientControlSet(
            f"cell {cell!r} has {n} control observation(s); the minimum is "
            f"{MINIMUM_CONTROL_OBSERVATIONS_PER_CELL}. {MINIMUM_IS_DERIVED}"
        )

    replicates = _group_replicates(observations)
    if len(replicates) < MINIMUM_CONTROL_REPLICATES_PER_CELL:
        raise InsufficientControlSet(
            f"cell {cell!r} has {len(replicates)} control replicate(s) "
            f"({sorted(replicates)}); the minimum is {MINIMUM_CONTROL_REPLICATES_PER_CELL}. With "
            f"one replicate there is NO observed null movement, so the margin would have to be "
            f"invented -- which is the thing this whole calibration exists to prevent. A second "
            f"replicate is a second seed on the same prompts, or a second arm explicitly recorded "
            f"as a control. {MINIMUM_IS_DERIVED}"
        )
    prompt_sets = {key: {obs.prompt_id for obs in rows} for key, rows in replicates.items()}
    reference_key = sorted(prompt_sets)[0]
    reference = prompt_sets[reference_key]
    for key, prompts in sorted(prompt_sets.items()):
        if prompts != reference:
            raise UnpairedControlReplicates(
                f"cell {cell!r}: replicate {key} covers {len(prompts)} prompt(s) and replicate "
                f"{reference_key} covers {len(reference)}; the symmetric difference is "
                f"{sorted(prompts ^ reference)}. Two rates over different prompt sets differ for a "
                f"reason that is not the null, so their difference is not a null difference. The "
                f"design already requires a paired same-seed control per prompt, so this is a "
                f"bookkeeping fault rather than a budget one."
            )
    n_prompts = len(reference)
    if n_prompts == 0:
        raise EmptyControlSet(f"cell {cell!r}: replicates cover zero prompts")

    rates = []
    for key in sorted(replicates):
        rows = replicates[key]
        hits = sum(1 for obs in rows if obs.outcome_class == target_outcome_class)
        rates.append(hits / len(rows))
    differences = [
        abs(rates[i] - rates[j]) for i in range(len(rates)) for j in range(i + 1, len(rates))
    ]
    if not differences:  # pragma: no cover - the replicate minimum already forbids this
        raise DegenerateControlSet(
            f"cell {cell!r}: no null rate difference could be formed from {len(rates)} replicate(s)"
        )
    observed_null_max = max(differences)

    #: A rate estimated from `n_prompts` prompts cannot resolve a difference
    #: below 1/n_prompts -- one prompt changing class is the smallest move that
    #: exists. So the margin is floored at the instrument's own resolution
    #: rather than at a number: an observed null spread of exactly zero would
    #: otherwise yield a margin of zero, under which ANY nonzero movement
    #: passes. Both terms are measured; neither is chosen.
    rate_resolution = 1.0 / n_prompts

    #: THE THIRD FLOOR, AND IT IS THE ONE THAT MAKES THE MARGIN UNABLE TO SIT
    #: INSIDE ITS OWN MEASUREMENT NOISE. See RESAMPLE_UNCERTAINTY_IS_NOT_OPTIONAL.
    #: Leave-one-prompt-out is parameter-free -- there is no resample count, no
    #: level and no distributional form to choose -- and it is computed on
    #: CONTROLS ONLY, so it adds no dependence on any intervened generation.
    loo_rates = leave_one_prompt_out_rates(
        observations, target_outcome_class=target_outcome_class, prompts=sorted(reference)
    )
    control_rate_loo_spread = observed_spread(loo_rates)
    signed_loo_spread = observed_spread(
        leave_one_prompt_out_signed_midranges(observations, prompts=sorted(reference))
    )

    components = {
        "observed_null_rate_difference_max": observed_null_max,
        "rate_resolution": rate_resolution,
        "control_rate_leave_one_prompt_out_spread": control_rate_loo_spread,
    }
    rate_margin = max(components.values())
    margin_bound_by = sorted(
        name for name, value in components.items() if value == rate_margin
    )
    rate_ceiling = 1.0 - rate_margin

    signed_values = [float(obs.signed) for obs in observations]
    low = min(signed_values)
    high = max(signed_values)
    resolution = float(rubric.resolution)
    if high - low < resolution:
        midpoint = (low + high) / 2.0
        band_low = midpoint - resolution / 2.0
        band_high = midpoint + resolution / 2.0
    else:
        band_low, band_high = low, high
    assertion_floor = max(float(obs.assertion_level) for obs in observations)

    return CellCalibration(
        cell=cell,
        target_outcome_class=target_outcome_class,
        n_control_observations=n,
        n_prompts=n_prompts,
        n_replicates=len(replicates),
        n_null_differences=len(differences),
        neutral_low=band_low,
        neutral_high=band_high,
        assertion_floor=assertion_floor,
        rate_resolution=rate_resolution,
        observed_null_rate_difference_max=observed_null_max,
        rate_margin=rate_margin,
        rate_ceiling=rate_ceiling,
        observed_signed_min=low,
        observed_signed_max=high,
        rubric_resolution=resolution,
        attained_level_signed_band=attained_coverage_level(n),
        attained_level_rate_margin=attained_coverage_level(len(differences)),
        replicate_rates=tuple(rates),
        control_rate_loo_spread=control_rate_loo_spread,
        signed_loo_spread=signed_loo_spread,
        control_rate_loo_values=loo_rates,
        margin_bound_by=tuple(margin_bound_by),
    )


# --------------------------------------------------------------------------
# The pin, and the seal that makes post-hoc pinning impossible.
# --------------------------------------------------------------------------

_SEAL: dict[str, Any] = {"scoring_has_begun": False, "pin_digest": None, "first_scored": None}


def seal_state() -> dict[str, Any]:
    """What the seal currently knows. Read-only view for reporting."""
    return dict(_SEAL)


def note_scoring_has_begun(pin_digest: str, observation_id: str) -> None:
    """Close the calibration path. Called by every intervened-scoring entry.

    After this, `calibrate` refuses in this process. That is the whole
    mechanism by which "pinned BEFORE any intervened generation is scored"
    stops being a rule someone has to remember."""
    if not _HEX64.fullmatch(str(pin_digest)):
        raise CalibrationDigestMismatch(
            f"pin_digest={pin_digest!r} is not 64 lowercase hex, so the seal cannot record WHICH "
            f"calibration the scoring was done against."
        )
    if _SEAL["scoring_has_begun"] and _SEAL["pin_digest"] != pin_digest:
        raise CalibrationSealed(
            f"scoring already began against pin {_SEAL['pin_digest']} (first observation "
            f"{_SEAL['first_scored']!r}) and this call presents pin {pin_digest}. Two different "
            f"calibrations in one scoring pass means one of them was chosen after seeing results."
        )
    if not _SEAL["scoring_has_begun"]:
        _SEAL["scoring_has_begun"] = True
        _SEAL["pin_digest"] = pin_digest
        _SEAL["first_scored"] = observation_id


def _reset_seal_for_tests_only() -> None:
    """Reopen the seal. NOT A PRODUCTION PATH.

    Named so that its appearance anywhere outside a test is obvious in a diff,
    and `tests/test_causal_calibration.py` asserts that no module under
    `scripts/final_pairing/` calls it."""
    _SEAL.update({"scoring_has_begun": False, "pin_digest": None, "first_scored": None})


@dataclass(frozen=True)
class PinnedCalibration:
    """A calibration with its own digest over its own canonical bytes."""

    cells: tuple[CellCalibration, ...]
    control_set_digest: str
    n_control_observations: int
    rubric: RubricAttestation
    calibrating_lane: str
    selecting_lane_excluded: str
    pinned_at_utc: str
    digest: str

    def cell(self, name: str) -> CellCalibration:
        for calibration in self.cells:
            if calibration.cell == name:
                return calibration
        raise CalibrationError(
            f"no calibration for cell {name!r}; pinned cells are "
            f"{[c.cell for c in self.cells]}. A cell with no calibration is NOT EXERCISED and is "
            f"not a cell that failed."
        )

    def bands(self, cell: str) -> OutcomeBands:
        return self.cell(cell).bands(self.digest)

    def body(self) -> dict[str, Any]:
        """Everything the digest covers. `digest` itself is NOT in here."""
        return {
            "schema": "final-pairing-causal-control-only-calibration/1",
            "cells": [calibration.to_dict() for calibration in self.cells],
            "control_set_digest": self.control_set_digest,
            "n_control_observations": int(self.n_control_observations),
            "rubric": self.rubric.to_dict(),
            "calibrating_lane": self.calibrating_lane,
            "selecting_lane_excluded": self.selecting_lane_excluded,
            "pinned_at_utc": self.pinned_at_utc,
            "level_free_derivation": LEVEL_FREE_DERIVATION,
            "minimum_is_derived": MINIMUM_IS_DERIVED,
            "ceiling_derivation": WHY_THE_CEILING_IS_A_FUNCTION_OF_THE_MARGIN,
            "assignment_record": CALIBRATION_ASSIGNMENT_IS_A_COORDINATION_RECORD,
            "dose_reference": DOSE_REFERENCE_IS_A_CONTROL_ONLY_MEASUREMENT,
            "contains_zero_intervened_generations": True,
        }

    def to_dict(self) -> dict[str, Any]:
        record = self.body()
        record["digest"] = self.digest
        return record

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.body())


def _digest_of_body(body: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json(dict(body)))


def digest_control_set(observations: Sequence[ControlObservation]) -> str:
    """Digest the exact control rows a calibration was derived from.

    Sorted by observation_id so the digest is a property of the SET rather than
    of the order it happened to arrive in, and computed over every field so a
    silently edited reading changes it."""
    rows = sorted((obs.to_dict() for obs in observations), key=lambda row: row["observation_id"])
    return sha256_hex(canonical_json(rows))


def calibrate(
    observations: Sequence[ControlObservation],
    *,
    rubric: RubricAttestation,
    cells: Sequence[str],
    target_outcome_class: str,
    calibrating_lane: str,
    selecting_lane: str,
    now: str | None = None,
) -> PinnedCalibration:
    """THE ONLY WAY TO GET A MARGIN, A CEILING OR A BAND.

    Refuses if the seal is closed, if any input is not a control, if any
    declared cell has no controls, or if any cell's control set cannot support
    the derivation. Every cell in `cells` must be calibrated: a partially
    calibrated pin would leave a cell whose scoring silently falls back to
    another cell's boundaries."""
    if _SEAL["scoring_has_begun"]:
        raise CalibrationSealed(
            f"an intervened generation has already been scored in this process against pin "
            f"{_SEAL['pin_digest']} (first: {_SEAL['first_scored']!r}). Calibrating now would be "
            f"pinning after the fact, which is the whole thing the rule exists to prevent."
        )
    if not cells:
        raise CalibrationError(
            "calibrate() was called with no cells, so it would produce a pin that covers nothing "
            "and yet reads as a completed calibration."
        )
    if str(calibrating_lane).strip().lower() == str(selecting_lane).strip().lower():
        raise CalibrationError(
            f"calibrating_lane and selecting_lane are both {calibrating_lane!r}. RULING_13 and "
            f"RULING_14 both hold that the calibration is VOID if the calibrating lane also selects "
            f"the group."
        )
    if not observations:
        raise EmptyControlSet(
            f"calibrate() received zero control observations for cells {list(cells)}. MINIMUM: "
            f"{MINIMUM_CONTROL_OBSERVATIONS_PER_CELL} observation(s) across "
            f"{MINIMUM_CONTROL_REPLICATES_PER_CELL} replicate(s) PER CELL. {MINIMUM_IS_DERIVED}"
        )

    by_cell: dict[str, list[ControlObservation]] = {name: [] for name in cells}
    unexpected: list[str] = []
    for observation in observations:
        if observation.cell in by_cell:
            by_cell[observation.cell].append(observation)
        else:
            unexpected.append(observation.cell)
    if unexpected:
        raise CalibrationError(
            f"observations arrived for undeclared cell(s) {sorted(set(unexpected))}; declared cells "
            f"are {list(cells)}. Silently ignoring them would calibrate on a subset while "
            f"reporting the whole."
        )
    calibrated = tuple(
        calibrate_cell(
            name, by_cell[name], rubric=rubric, target_outcome_class=target_outcome_class
        )
        for name in cells
    )
    timestamp = now or _datetime.datetime.now(_datetime.UTC).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    pin = PinnedCalibration(
        cells=calibrated,
        control_set_digest=digest_control_set(observations),
        n_control_observations=len(observations),
        rubric=rubric,
        calibrating_lane=calibrating_lane,
        selecting_lane_excluded=selecting_lane,
        pinned_at_utc=timestamp,
        digest="0" * 64,
    )
    return PinnedCalibration(
        cells=pin.cells,
        control_set_digest=pin.control_set_digest,
        n_control_observations=pin.n_control_observations,
        rubric=pin.rubric,
        calibrating_lane=pin.calibrating_lane,
        selecting_lane_excluded=pin.selecting_lane_excluded,
        pinned_at_utc=pin.pinned_at_utc,
        digest=_digest_of_body(pin.body()),
    )


def verify_pin(record: Mapping[str, Any]) -> str:
    """RECOMPUTE the digest from the bytes and refuse a disagreement.

    Never reads the digest off the field the record declares about itself,
    which is the discipline `write_generation_manifest` already records for
    this lane: a self-declared digest that nobody recomputed is the defect."""
    if "digest" not in record:
        raise CalibrationDigestMismatch(
            "a calibration record carries no digest, so it cannot be shown to be the one the "
            "scoring was done against."
        )
    body = {key: value for key, value in record.items() if key != "digest"}
    recomputed = _digest_of_body(body)
    declared = str(record["digest"])
    if recomputed != declared:
        raise CalibrationDigestMismatch(
            f"the calibration's recomputed digest {recomputed} disagrees with the declared "
            f"{declared}. The bytes moved after they were pinned."
        )
    return recomputed


def write_pin(path: Path, pin: PinnedCalibration) -> str:
    """Write the pin as LF bytes, refusing to overwrite different bytes.

    `read_bytes`/`write_bytes` and never `write_text`: on Windows `write_text`
    turns every LF into CRLF and `.gitattributes` carries `* -text`, so the CR
    becomes real content and every pinned sha256 over the file breaks. Refusing
    to overwrite is the same rule `post_report.py` adopted after two rulings
    were destroyed by a silent overwrite."""
    payload = json.dumps(pin.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    raw = payload.encode("utf-8")
    if b"\r\n" in raw:  # pragma: no cover - json.dumps does not emit CRLF
        raise CalibrationError("refusing to write a pin containing CRLF")
    path = Path(path)
    if path.exists():
        existing = path.read_bytes()
        if existing != raw:
            raise CalibrationError(
                f"refusing to overwrite {path.name}: a pin already exists there with different "
                f"bytes. A calibration that can be rewritten is not pinned."
            )
        return pin.digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return pin.digest


def read_pin(path: Path) -> dict[str, Any]:
    """Read and VERIFY. There is no unverified read."""
    raw = Path(path).read_bytes()
    if b"\r\n" in raw:
        raise CalibrationError(
            f"{Path(path).name} contains CRLF, so its bytes are not the bytes that were digested."
        )
    record = json.loads(raw.decode("utf-8"))
    verify_pin(record)
    return record


# --------------------------------------------------------------------------
# The per-cell verdict, scored against the pin.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CellVerdict:
    """One of the six entries in the result vector, or a stated non-result.

    TWO CRITERIA, KEPT SEPARATE, AND THE SEPARATION IS A REPAIR.
    `status` is the SUFFICIENCY criterion (RULING_13 Q2 clause 2): a paired rate
    delta over ALL PAIRED PROMPTS against the margin, with the control rate
    against the ceiling. `crossing_status` is the SWITCHABILITY criterion
    (RULING_13 Q4 clause 4): a crossing of the neutral band, measured ONLY on
    prompts whose control sits at the ORIGIN POLE.

    They were merged in the first version of this file and the merge made
    `CEILING_EXCLUDED` UNREACHABLE BY CONSTRUCTION -- with the control rate
    computed over baseline-conditioned prompts only, and the target pole being
    the opposite of the origin pole, a conditioned control can never be at the
    target, so the control rate was identically 0 and the ceiling could never
    bite. A check that cannot fire is the sprint's defect class, and it was
    found by writing the test that tried to make it fire rather than by reading
    the code. The two criteria are different arms of the ruling and are now
    computed over different denominators, which is what the ruling says."""

    cell: str
    status: str
    n: int
    control_rate: float | None
    intervened_rate: float | None
    paired_rate_delta: float | None
    rate_margin: float
    rate_ceiling: float
    void_counts: Mapping[str, int]
    baseline_excluded: int
    crossing_status: str
    n_admissible_for_crossing: int
    crossings: int
    asserts_both: int
    moved_without_crossing: int
    control_rate_loo_spread: float
    paired_delta_inside_control_resample_spread: bool | None
    margin_bound_by: tuple[str, ...]
    reason: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": self.cell,
            "status": self.status,
            "n": int(self.n),
            "control_rate": self.control_rate,
            "intervened_rate": self.intervened_rate,
            "paired_rate_delta": self.paired_rate_delta,
            "rate_margin": float(self.rate_margin),
            "rate_ceiling": float(self.rate_ceiling),
            "void_counts": dict(self.void_counts),
            "baseline_excluded": int(self.baseline_excluded),
            "crossing_status": self.crossing_status,
            "n_admissible_for_crossing": int(self.n_admissible_for_crossing),
            "crossings": int(self.crossings),
            "asserts_both": int(self.asserts_both),
            "moved_without_crossing": int(self.moved_without_crossing),
            "control_rate_loo_spread": float(self.control_rate_loo_spread),
            "paired_delta_inside_control_resample_spread": (
                self.paired_delta_inside_control_resample_spread
            ),
            "margin_bound_by": list(self.margin_bound_by),
            "resample_rule": (
                "The margin is floored at the control rate's leave-one-prompt-out spread, so a PASS "
                "can never sit inside the resample noise of its own control measurement. A FAIL "
                "inside that spread and a FAIL outside it are DIFFERENT FINDINGS and are "
                "distinguishable here; a point estimate would render them identically."
            ),
            "reason": self.reason,
            "two_criteria_rule": (
                "status is SUFFICIENCY over all paired prompts (n); crossing_status is "
                "SWITCHABILITY over the baseline-conditioned subset (n_admissible_for_crossing). "
                "They have different denominators on purpose and may not be merged."
            ),
        }


#: The sufficiency states, and NONE of them is a null except FAIL. RULING_13's
#: whole Q2 clause 1 is that a cell with no opportunity to be tested must be
#: reportable as such.
VERDICT_STATES = (
    "PASS",
    "FAIL",
    "NOT_EXERCISED",
    "CEILING_EXCLUDED",
)

#: The switchability sub-result, reported BESIDE the sufficiency status and
#: never folded into it. A one-directional crossing is a steering result and not
#: a switch, so nothing here is a switch claim on its own.
CROSSING_STATES = (
    "EVIDENCED",
    "NOT_EVIDENCED",
    "NO_ADMISSIBLE_BASELINE",
    "NOT_EXERCISED",
)

CROSSING_STATE_MEANINGS = {
    "EVIDENCED": (
        "At least one prompt whose control sat at the ORIGIN pole crossed the neutral band to the "
        "other pole. A count, not a rate, and not on its own a switch: BIDIRECTIONALITY is the "
        "only discriminator against the single-axis-collapse artifact."
    ),
    "NOT_EVIDENCED": (
        "Admissible prompts existed and none crossed. 'Directional influence without a flip' is "
        "reportable and MAY NOT be written as switchability."
    ),
    "NO_ADMISSIBLE_BASELINE": (
        "Every paired prompt's control already sat at the target pole, so no prompt could evidence "
        "a flip to it. Excluded and counted; never a fail. This is a property of the CONTROL and "
        "is decided before any intervened generation is looked at."
    ),
    "NOT_EXERCISED": "No eligible intervened generation, so the crossing test never ran.",
}

VERDICT_STATE_MEANINGS = {
    "PASS": "The paired rate delta exceeded the margin and the control rate was below the ceiling.",
    "FAIL": (
        "The paired rate delta did not exceed the margin, on a cell that HAD the opportunity to "
        "show one. This is the only state that is a null, and it carries the level-free bound's "
        "asymmetry: see NULL_UNDER_A_LEVEL_FREE_BOUND_REQUIRED_WORDING."
    ),
    "NOT_EXERCISED": (
        "VOID, NOT A NULL. No intervened generation in this cell passed the firing precondition, "
        "so the cell was never tested. Reporting this as a failure to steer is a failure "
        "MANUFACTURED BY THE INSTRUMENT."
    ),
    "CEILING_EXCLUDED": (
        "The control rate over all paired prompts was at or above the ceiling, so a movement of at "
        "least the margin was ARITHMETICALLY UNAVAILABLE. Excluded and counted; never a fail. This "
        "is 'it was already there' as a DECLARED exclusion rather than an unnoticed pass."
    ),
}


def evaluate_cell(
    *,
    cell: str,
    pin: PinnedCalibration,
    control_scored: Sequence[ScoredGeneration],
    intervened_scored: Sequence[ScoredGeneration],
    void_counts: Mapping[str, int],
    baseline_excluded: int,
    origin_pole: str,
) -> CellVerdict:
    """Score one cell AGAINST THE PIN, and seal the calibration path.

    The first call anywhere in the process closes `calibrate`. Every boundary
    is read from the pin; none is a parameter of this function, so there is no
    signature through which a caller could supply one."""
    calibration = pin.cell(cell)
    verify_pin(pin.to_dict())
    first = intervened_scored[0].observation_id if intervened_scored else f"{cell}:none"
    note_scoring_has_begun(pin.digest, first)

    target = calibration.target_outcome_class
    #: The rate is measured on `target` and the crossing predicate is measured
    #: from `origin_pole` to the OPPOSITE pole. If those are not the same pole
    #: the cell reports a rate on one axis end and a crossing count on the
    #: other, and the two numbers in one verdict would describe different
    #: events. Refused rather than reconciled, because reconciling it here would
    #: silently pick which of the two the caller meant.
    if origin_pole not in ("POLE_OWN", "POLE_MIRROR"):
        raise CalibrationError(
            f"origin_pole={origin_pole!r} is not a pole. The crossing predicate is "
            f"baseline-conditioned on the ORIGIN pole (RULING_13 Q4 clause 4)."
        )
    opposite = "POLE_MIRROR" if origin_pole == "POLE_OWN" else "POLE_OWN"
    if target != opposite:
        raise CalibrationError(
            f"the pin calibrates cell {cell!r} on target_outcome_class={target!r} while this call "
            f"conditions on origin_pole={origin_pole!r}, whose opposite pole is {opposite!r}. The "
            f"rate and the crossing count would then describe different events in one verdict."
        )
    counts = dict(void_counts)
    if not intervened_scored:
        return CellVerdict(
            cell=cell,
            status="NOT_EXERCISED",
            n=0,
            control_rate=None,
            intervened_rate=None,
            paired_rate_delta=None,
            rate_margin=calibration.rate_margin,
            rate_ceiling=calibration.rate_ceiling,
            void_counts=counts,
            baseline_excluded=baseline_excluded,
            crossing_status="NOT_EXERCISED",
            n_admissible_for_crossing=0,
            crossings=0,
            asserts_both=0,
            moved_without_crossing=0,
            control_rate_loo_spread=calibration.control_rate_loo_spread,
            paired_delta_inside_control_resample_spread=None,
            margin_bound_by=calibration.margin_bound_by,
            reason=VERDICT_STATE_MEANINGS["NOT_EXERCISED"],
        )
    if not control_scored:
        raise EmptyControlSet(
            f"cell {cell!r} has intervened generations and NO paired control. Every delta is "
            f"measured against the paired same-seed control; without it there is no delta, and a "
            f"one-armed reading is not a result."
        )

    by_prompt_control = {generation.prompt_id: generation for generation in control_scored}
    paired = [
        generation
        for generation in intervened_scored
        if generation.prompt_id in by_prompt_control
    ]
    if not paired:
        raise EmptyControlSet(
            f"cell {cell!r}: no intervened generation shares a prompt with a control. The pairing "
            f"is by prompt AND seed by design; an unpaired comparison is not a paired delta."
        )
    # CRITERION ONE, SUFFICIENCY (RULING_13 Q2 clause 2). Denominator: EVERY
    # paired prompt. The ceiling is a bound on the control rate and can only
    # bite here, because a baseline-conditioned control is at the ORIGIN pole
    # and therefore never at the target -- conditioning first makes the control
    # rate identically zero and the ceiling unreachable.
    n = len(paired)
    control_hits = sum(
        1
        for generation in paired
        if by_prompt_control[generation.prompt_id].outcome_class == target
    )
    intervened_hits = sum(1 for generation in paired if generation.outcome_class == target)
    control_rate = control_hits / n
    intervened_rate = intervened_hits / n
    delta = intervened_rate - control_rate

    # CRITERION TWO, SWITCHABILITY CROSSING (RULING_13 Q4 clause 4). Denominator:
    # only prompts whose CONTROL sits at the origin pole. Reported beside the
    # sufficiency figures with its own n, never merged into them.
    admissible = [
        generation
        for generation in paired
        if causal_outcome.baseline_is_at_origin_pole(
            by_prompt_control[generation.prompt_id].outcome_class, origin_pole=origin_pole
        )
    ]
    total_excluded = int(baseline_excluded) + (len(paired) - len(admissible))
    #: Counted through `causal_outcome.crosses` rather than by an equality on
    #: the class, so there is ONE implementation of "did it cross". An equality
    #: here would happen to agree today and would stop agreeing the moment the
    #: crossing rule gained a clause -- and it is the rule that says ASSERTS_BOTH
    #: is not a flip.
    crossings = sum(
        1
        for generation in admissible
        if causal_outcome.crosses(
            by_prompt_control[generation.prompt_id].outcome_class,
            generation.outcome_class,
            origin_pole=origin_pole,
        )
    )
    asserts_both = sum(1 for g in admissible if g.outcome_class == "ASSERTS_BOTH")
    moved_without_crossing = sum(
        1
        for generation in admissible
        if generation.outcome_class not in (target, origin_pole, "ASSERTS_BOTH")
    )
    if not admissible:
        crossing_status = "NO_ADMISSIBLE_BASELINE"
    elif crossings:
        crossing_status = "EVIDENCED"
    else:
        crossing_status = "NOT_EVIDENCED"

    if control_rate >= calibration.rate_ceiling:
        status = "CEILING_EXCLUDED"
    elif delta > calibration.rate_margin:
        status = "PASS"
    else:
        status = "FAIL"
    return CellVerdict(
        cell=cell,
        status=status,
        n=n,
        control_rate=control_rate,
        intervened_rate=intervened_rate,
        paired_rate_delta=delta,
        rate_margin=calibration.rate_margin,
        rate_ceiling=calibration.rate_ceiling,
        void_counts=counts,
        baseline_excluded=total_excluded,
        crossing_status=crossing_status,
        n_admissible_for_crossing=len(admissible),
        crossings=crossings,
        asserts_both=asserts_both,
        moved_without_crossing=moved_without_crossing,
        control_rate_loo_spread=calibration.control_rate_loo_spread,
        paired_delta_inside_control_resample_spread=(
            abs(delta) <= calibration.control_rate_loo_spread
        ),
        margin_bound_by=calibration.margin_bound_by,
        reason=(
            f"{VERDICT_STATE_MEANINGS[status]} CROSSING: "
            f"{CROSSING_STATE_MEANINGS[crossing_status]}"
        ),
    )


def result_vector(verdicts: Sequence[CellVerdict]) -> dict[str, Any]:
    """THE HEADLINE IS THE VECTOR. The only permitted scalar travels with it.

    "the RESULT IS A SIX-VECTOR OF PER-CELL VERDICTS. A pooled scalar rate is
    PROHIBITED as the headline and permitted only alongside the vector." The
    dict makes that structural: there is no function here returning the scalar
    on its own, and PARTIAL is pre-declared a legitimate outcome rather than a
    failure to be re-run until uniform."""
    if not verdicts:
        raise CalibrationError(
            "result_vector() was called with no cells, so it would report a pass count over "
            "nothing. An aggregate over an empty set is the defect this sprint keeps finding."
        )
    passes = [verdict.cell for verdict in verdicts if verdict.passed]
    return {
        "vector": [verdict.to_dict() for verdict in verdicts],
        "cells": [verdict.cell for verdict in verdicts],
        "n_pass_alongside_the_vector": len(passes),
        "passing_cells": passes,
        "status_counts": {
            state: sum(1 for verdict in verdicts if verdict.status == state)
            for state in VERDICT_STATES
        },
        "crossing_status_counts": {
            state: sum(1 for verdict in verdicts if verdict.crossing_status == state)
            for state in CROSSING_STATES
        },
        "verdict_state_meanings": dict(VERDICT_STATE_MEANINGS),
        "crossing_state_meanings": dict(CROSSING_STATE_MEANINGS),
        "inside_resample_spread": [
            verdict.cell
            for verdict in verdicts
            if verdict.paired_delta_inside_control_resample_spread
        ],
        "resample_rule": RESAMPLE_UNCERTAINTY_IS_NOT_OPTIONAL,
        "partial_is_a_legitimate_outcome": (
            "PARTIAL is PRE-DECLARED A LEGITIMATE REPORTABLE OUTCOME, not a failure to be re-run "
            "until uniform -- requiring uniformity would create an incentive to re-run until the "
            "vector goes green."
        ),
        "headline_rule": (
            "The headline is this vector. n_pass is permitted ONLY alongside it and never on its "
            "own, and no cell whose status is NOT_EXERCISED, CEILING_EXCLUDED or "
            "NO_ADMISSIBLE_BASELINE may be read as a null."
        ),
    }


# --------------------------------------------------------------------------
# The dose reference: procedure supplied, substrate NOT chosen.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DoseReference:
    """A per-member dose scale, MEASURED on a DECLARED control-only substrate."""

    feature_index: int
    substrate: str
    measured_value: float
    n_substrate_rows: int
    measurement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_index": int(self.feature_index),
            "substrate": self.substrate,
            "measured_value": float(self.measured_value),
            "n_substrate_rows": int(self.n_substrate_rows),
            "measurement": self.measurement,
        }


def derive_dose_reference(
    *, feature_index: int, substrate: str, activations: Sequence[float]
) -> DoseReference:
    """The procedure, with no substrate default and no zero result.

    Refuses an undeclared substrate, an empty activation set, and a measured
    maximum of zero. It does NOT decide which substrate is right -- see
    `DOSE_REFERENCE_IS_A_CONTROL_ONLY_MEASUREMENT`. A member whose reference
    cannot be measured refuses PER MEMBER, which is what the ruling asked for:
    "the per-member dose RULING_13 already requires makes this a per-member
    refusal rather than a whole-group one"."""
    if not str(substrate).strip():
        raise DoseReferenceUndeclared(
            f"feature {feature_index}: no substrate declared. A dose reference whose substrate is "
            f"unstated cannot be shown to be control-only, and the whole defect being repaired is "
            f"a reference measured on the WRONG substrate (background corpus activation, which is "
            f"0 for a maximally selective feature)."
        )
    if not activations:
        raise DoseReferenceUndeclared(
            f"feature {feature_index}: substrate {substrate!r} yielded no activations, so nothing "
            f"was measured. A reference over an empty substrate would still produce a number."
        )
    value = max(float(activation) for activation in activations)
    if value <= 0.0:
        raise DoseReferenceUndeclared(
            f"feature {feature_index}: the measured maximum on substrate {substrate!r} over "
            f"{len(activations)} row(s) is {value}, so the dose would be zero and the member would "
            f"be recorded as amplified while nothing was done to it. This REFUSES rather than "
            f"falling back to another member's scale, skipping the member, or dropping it from the "
            f"group. corpus_max == 0 is MAXIMAL SELECTIVITY, not a dead feature."
        )
    return DoseReference(
        feature_index=feature_index,
        substrate=str(substrate),
        measured_value=value,
        n_substrate_rows=len(activations),
        measurement=(
            f"maximum activation over {len(activations)} control-only row(s) of substrate "
            f"{substrate!r}; an exact order statistic, attained coverage "
            f"{attained_coverage_level(len(activations)):.4f}"
        ),
    )


def _print(title: str) -> None:
    print(f"\n=== {title} ===")


def _selfcheck() -> int:
    """CONTROLS FIRST, WITH REAL OUTPUT. No weights, no cluster, no thresholds."""
    from causal_outcome import (
        BipolarReading,
        FiringEvidence,
        OutcomeMeasureNotSanctioned,
        PoleReading,
        RubricAttestation,
        score_generation,
    )

    failures = 0

    def expect_refusal(what: str, call: Any, *expected: type[BaseException]) -> None:
        nonlocal failures
        try:
            call()
        except expected as error:
            print(f"  REFUSED {what}: {type(error).__name__}: {str(error)[:190]}")
            return
        except Exception as error:  # pragma: no cover
            failures += 1
            print(f"  WRONG ERROR {what}: {type(error).__name__}: {error}")
            return
        failures += 1
        print(f"  DID NOT REFUSE {what} -- the check does not exercise what it claims")

    _print("no real rubric exists, so the REAL path refuses at the top")
    expect_refusal(
        "loading a rubric attestation with no sanctioning authority",
        lambda: RubricAttestation(
            rubric_id="r",
            rubric_version="1",
            digest="0" * 64,
            scale_min=0.0,
            scale_max=6.0,
            resolution=1.0,
            composition="signed_difference_over_two_disjoint_poles",
            anchors_digest="1" * 64,
            rank_reliability_evidence="m",
            sanctioned_by="",
            authored_by="a",
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
        composition="signed_difference_over_two_disjoint_poles",
        anchors_digest="b" * 64,
        rank_reliability_evidence="SYNTHETIC: no rank reliability measured for any axis",
        sanctioned_by="SYNTHETIC: nothing sanctions this; it exercises the arithmetic only",
        authored_by="selfcheck_fixture",
    )

    def control(observation_id: str, cell: str, prompt: str, seed: int, own: float, mirror: float):
        signed = own - mirror
        level = own + mirror
        cls = "POLE_OWN" if signed > 1.0 else ("POLE_MIRROR" if signed < -1.0 else "NEUTRAL")
        return ControlObservation(
            observation_id=observation_id,
            cell=cell,
            prompt_id=prompt,
            seed=seed,
            arm_label="control-noop",
            is_control=True,
            signed=signed,
            assertion_level=level,
            outcome_class=cls,
        )

    _print("a calibration that cannot be supported REFUSES and states the minimum")
    expect_refusal(
        "an empty control set",
        lambda: calibrate_cell("en/f1", [], rubric=rubric, target_outcome_class="POLE_OWN"),
        EmptyControlSet,
    )
    expect_refusal(
        "one control observation",
        lambda: calibrate_cell(
            "en/f1",
            [control("c1", "en/f1", "p1", 1, 0.0, 0.0)],
            rubric=rubric,
            target_outcome_class="POLE_OWN",
        ),
        InsufficientControlSet,
    )
    expect_refusal(
        "two observations in ONE replicate (no null difference exists)",
        lambda: calibrate_cell(
            "en/f1",
            [control("c1", "en/f1", "p1", 1, 0.0, 0.0), control("c2", "en/f1", "p2", 1, 0.0, 0.0)],
            rubric=rubric,
            target_outcome_class="POLE_OWN",
        ),
        InsufficientControlSet,
    )
    contaminated = ControlObservation(
        observation_id="bad",
        cell="en/f1",
        prompt_id="p1",
        seed=1,
        arm_label="amplify-B",
        is_control=False,
        signed=3.0,
        assertion_level=3.0,
        outcome_class="POLE_OWN",
    )
    expect_refusal(
        "an intervened generation inside the control set",
        lambda: calibrate_cell(
            "en/f1",
            [control("c1", "en/f1", "p1", 1, 0.0, 0.0), contaminated],
            rubric=rubric,
            target_outcome_class="POLE_OWN",
        ),
        ContaminatedControlSet,
    )
    expect_refusal(
        "replicates covering different prompts",
        lambda: calibrate_cell(
            "en/f1",
            [
                control("c1", "en/f1", "p1", 1, 0.0, 0.0),
                control("c2", "en/f1", "p2", 1, 0.0, 0.0),
                control("c3", "en/f1", "p1", 2, 0.0, 0.0),
            ],
            rubric=rubric,
            target_outcome_class="POLE_OWN",
        ),
        UnpairedControlReplicates,
    )

    _print("the attained level is a FUNCTION of n, not a stored literal")
    for n in (1, 2, 3, 9, 19):
        print(f"  n={n:3d} -> attained coverage {attained_coverage_level(n):.6f}")
    for level in (0.5, 0.75, 0.9, 0.95):
        print(f"  level {level} needs n >= {minimum_controls_for_level(level)}")

    _print("a real calibration on a synthetic CONTROL-ONLY set")
    cells = ("en/f1", "fr/f1")
    observations: list[ControlObservation] = []
    for cell in cells:
        for seed in (1, 2):
            for index, prompt in enumerate(("p1", "p2", "p3", "p4")):
                own = 1.0 if (seed == 2 and index == 0 and cell == "en/f1") else 0.0
                observations.append(
                    control(f"{cell}-{seed}-{prompt}", cell, prompt, seed, own, 0.0)
                )
    pin = calibrate(
        observations,
        rubric=rubric,
        cells=cells,
        target_outcome_class="POLE_OWN",
        calibrating_lane="researcher",
        selecting_lane="engineer2",
        now="2026-08-17T00:00:00Z",
    )
    print(f"  pin digest {pin.digest}")
    print(f"  control set digest {pin.control_set_digest} over {pin.n_control_observations} rows")
    for calibration in pin.cells:
        print(
            f"  {calibration.cell}: margin={calibration.rate_margin:.4f} "
            f"ceiling={calibration.rate_ceiling:.4f} "
            f"rate_resolution={calibration.rate_resolution:.4f} "
            f"observed_null_max={calibration.observed_null_rate_difference_max:.4f} "
            f"band=[{calibration.neutral_low:+.3f}, {calibration.neutral_high:+.3f}] "
            f"assertion_floor={calibration.assertion_floor:.3f} "
            f"levels={calibration.attained_level_signed_band:.4f}/"
            f"{calibration.attained_level_rate_margin:.4f}"
        )
        print(
            f"    resample: control_rate LOO spread="
            f"{calibration.control_rate_loo_spread:.4f} signed LOO spread="
            f"{calibration.signed_loo_spread:.4f} margin_bound_by="
            f"{list(calibration.margin_bound_by)} "
            f"margin>=spread={calibration.margin_is_at_least_the_resample_spread}"
        )
    print(f"  recomputed digest verifies: {verify_pin(pin.to_dict()) == pin.digest}")
    tampered = pin.to_dict()
    tampered["cells"][0]["rate_margin"] = 0.0
    expect_refusal(
        "a pin whose margin was edited after pinning",
        lambda: verify_pin(tampered),
        CalibrationDigestMismatch,
    )

    _print("the ceiling is a FUNCTION of the margin (falsifier: change one, the other moves)")
    for n_prompts in (4, 10):
        rows = [
            control(f"x-{seed}-{i}", "en/f2", f"q{i}", seed, 0.0, 0.0)
            for seed in (1, 2)
            for i in range(n_prompts)
        ]
        one = calibrate_cell("en/f2", rows, rubric=rubric, target_outcome_class="POLE_OWN")
        print(
            f"  n_prompts={n_prompts:3d} -> resolution={one.rate_resolution:.4f} "
            f"margin={one.rate_margin:.4f} ceiling={one.rate_ceiling:.4f} "
            f"(margin+ceiling={one.rate_margin + one.rate_ceiling:.4f})"
        )

    _print("the margin is floored at its own RESAMPLE NOISE, not only at the null and 1/n")
    for label, rows in (
        (
            "one prompt carries the whole control rate (LOO spread binds)",
            [
                control(f"r-{seed}-p{i}", "en/f3", f"p{i}", seed, 5.0 if i == 0 else 0.0, 0.0)
                for seed in (1, 2)
                for i in range(4)
            ],
        ),
        (
            "every control identical (resolution binds)",
            [
                control(f"s-{seed}-p{i}", "en/f3", f"p{i}", seed, 0.0, 0.0)
                for seed in (1, 2)
                for i in range(4)
            ],
        ),
    ):
        one = calibrate_cell("en/f3", rows, rubric=rubric, target_outcome_class="POLE_OWN")
        print(
            f"  {label}: null_max={one.observed_null_rate_difference_max:.4f} "
            f"resolution={one.rate_resolution:.4f} "
            f"loo_spread={one.control_rate_loo_spread:.4f} -> margin={one.rate_margin:.4f} "
            f"bound_by={list(one.margin_bound_by)}"
        )
        print(f"    LOO rates: {[round(value, 4) for value in one.control_rate_loo_values]}")
    expect_refusal(
        "a leave-one-out resample over a single prompt (it would report zero uncertainty)",
        lambda: leave_one_prompt_out_rates(
            [control("z-1", "en/f4", "p0", 1, 0.0, 0.0), control("z-2", "en/f4", "p0", 2, 0.0, 0.0)],
            target_outcome_class="POLE_OWN",
            prompts=["p0"],
        ),
        InsufficientControlSet,
    )
    expect_refusal(
        "a spread over no values",
        lambda: observed_spread([]),
        DegenerateControlSet,
    )

    _print("scoring against the pin, then the SEAL closes the calibration path")

    def evidence(state: str = "APPLIED") -> FiringEvidence:
        if state == "CONTROL":
            return FiringEvidence(
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
        return FiringEvidence(
            intervention_state=state,
            hook_call_count=4,
            total_delta_norm=2.0,
            max_abs_delta=0.5,
            absorbed_element_count=0,
            requested_nonzero_element_count=160,
            residual_dtypes=("torch.bfloat16",),
            evaluated_member_doses=(2.0, 3.0),
            post_intervention_member_latents=(2.0, 3.0),
        )

    def reading(own: float, mirror: float) -> BipolarReading:
        return BipolarReading(
            own=PoleReading("pro_american_exceptionalism", own, rubric),
            mirror=PoleReading("pro_chinese_exceptionalism", mirror, rubric),
        )

    bands = pin.bands("en/f1")
    controls_scored = [
        score_generation(
            observation_id=f"ctl-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="control-noop",
            kind="noop",
            reading=reading(0.0, 3.0),
            firing=evidence("CONTROL"),
            bands=bands,
            member_count=0,
        )
        for prompt in ("p1", "p2", "p3", "p4")
    ]
    intervened_scored = [
        score_generation(
            observation_id=f"amp-{prompt}",
            cell="en/f1",
            prompt_id=prompt,
            seed=1,
            arm_label="joint-ablate-A-amplify-B",
            kind="amplify",
            reading=reading(own, 0.0),
            firing=evidence(),
            bands=bands,
            member_count=2,
        )
        for prompt, own in (("p1", 5.0), ("p2", 5.0), ("p3", 5.0), ("p4", 0.0))
    ]
    verdict = evaluate_cell(
        cell="en/f1",
        pin=pin,
        control_scored=controls_scored,
        intervened_scored=intervened_scored,
        void_counts={"not_exercised": 1, "fired_but_inert": 2, "zero_dose": 3},
        baseline_excluded=0,
        origin_pole="POLE_MIRROR",
    )
    print(f"  {verdict.to_dict()}")
    print(f"  seal: {seal_state()}")
    expect_refusal(
        "calibrating AFTER an intervened generation has been scored",
        lambda: calibrate(
            observations,
            rubric=rubric,
            cells=cells,
            target_outcome_class="POLE_OWN",
            calibrating_lane="researcher",
            selecting_lane="engineer2",
        ),
        CalibrationSealed,
    )

    _print("a cell with no eligible intervened generation is NOT_EXERCISED, not a fail")
    unexercised = evaluate_cell(
        cell="fr/f1",
        pin=pin,
        control_scored=[],
        intervened_scored=[],
        void_counts={"not_exercised": 4},
        baseline_excluded=0,
        origin_pole="POLE_MIRROR",
    )
    print(f"  status={unexercised.status} reason={unexercised.reason[:90]}")
    vector = result_vector([verdict, unexercised])
    print(
        f"  vector statuses={[row['status'] for row in vector['vector']]} "
        f"n_pass={vector['n_pass_alongside_the_vector']}"
    )

    _print("the calibrating lane may not also be the selecting lane")
    _reset_seal_for_tests_only()
    expect_refusal(
        "one lane doing both",
        lambda: calibrate(
            observations,
            rubric=rubric,
            cells=cells,
            target_outcome_class="POLE_OWN",
            calibrating_lane="engineer2",
            selecting_lane="engineer2",
        ),
        CalibrationError,
    )

    _print("the dose reference: procedure supplied, substrate NOT chosen")
    expect_refusal(
        "an undeclared substrate",
        lambda: derive_dose_reference(feature_index=7, substrate="  ", activations=[1.0]),
        DoseReferenceUndeclared,
    )
    expect_refusal(
        "a measured maximum of zero (the corpus_max == 0 case)",
        lambda: derive_dose_reference(
            feature_index=7, substrate="background_corpus_max", activations=[0.0, 0.0]
        ),
        DoseReferenceUndeclared,
    )
    reference = derive_dose_reference(
        feature_index=7, substrate="DECLARED-BY-SOMEONE-ELSE", activations=[0.4, 1.9, 1.1]
    )
    print(f"  {reference.to_dict()}")

    _print("what only real weights can settle")
    for item in UNEXERCISED_WITHOUT_GPU:
        print(f"  - {item}")

    _print("result")
    print("FAILURES:", failures)
    return 1 if failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selfcheck", action="store_true", help="controls first, with real output")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selfcheck:
        return _selfcheck()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
