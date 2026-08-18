"""The CONTROL-ONLY generation payload for the two final pairings.

WHAT THIS IS. The job payload that produces control continuations AND NOTHING
ELSE, reads each one with the frozen outcome instrument, and writes an artifact
the calibration lane can derive a boundary from. Nothing in this sprint has
ever run a forward pass on either final-pairing model; this is the payload that
would, and it is deliberately the arm that changes nothing.

WHAT IT IS NOT:

- It is NOT an authorization and it submits NOTHING. No sbatch, no ssh, no
  allocation. `--write-job-script` writes a script to disk for LA-B to stage,
  and never runs it.
- It applies NO INTERVENTION. Not amplify, not ablate-with-members, not a
  clamp, not a dose. `assert_control_only()` is a structural gate every arm
  passes through, so a dosing path is UNREACHABLE here rather than merely
  unused, and a test builds every refused shape to prove it.
- It sets NO threshold, margin, band, ceiling or dose. It cannot: an
  `OutcomeBands` requires a calibration digest that only
  `causal_calibration.calibrate` produces, and this payload never constructs
  one. The boundary comes from the controls this payload emits.
- It composes NO outcome scalar. See THE PAIR IS NOT COMPOSED HERE, below.

------------------------------------------------------------------------
THE FOUR CONTROL ARMS, AND WHY FOUR
------------------------------------------------------------------------

    label                      hook?  fires?  moves h?  state
    unhooked_baseline          no     -       no        CONTROL
    noop_control               no     no      no        CONTROL
    identity_hooked_control    yes    YES     no        FIRED_BUT_INERT
    reconstruction_control     yes    YES     YES       APPLIED

RULING_13: VOID AND NOT-EXERCISED ARE NOT NULLS. The distinction between "a
control whose hook never fired" and "a control that fired and was an exact
identity" is the entire reason the middle two arms are separate, and it
survives into the written artifact as `firing.hook_call_count`,
`firing.intervention_state` and the RECORDED OUTCOME of
`causal_outcome.assert_firing_precondition`, which this payload RUNS per record
rather than describes.

Only `unhooked_baseline` and `noop_control` are CALIBRATION-ELIGIBLE, and that
is not this payload's opinion: `assert_firing_precondition(kind="noop")`
requires `hook_call_count == 0` and `max_abs_delta == 0.0`, so the
identity-hooked arm is refused BY THE CALIBRATION LANE'S OWN GATE. It is
carried anyway, because it is the only arm that proves the hook path itself is
an exact identity, and the artifact marks it ineligible per record instead of
dropping it.

`reconstruction_control` moves the residual by the whole SAE reconstruction
error while touching no feature. It is the fidelity floor an (a)-mechanism
result must be read against (`group_intervention.assert_control_is_admissible`)
and it is NOT a null control; the artifact marks it ineligible with that
reason.

------------------------------------------------------------------------
THE PAIR IS NOT COMPOSED HERE
------------------------------------------------------------------------

RULING_15 R2 makes the outcome variable the PAIR (signed difference, assertion
level) with BOTH RAW PER-REFERENT COUNTS RETAINED. This payload retains both
counts per generation and does NOT compute the pair, because
`causal_outcome.BipolarReading` requires a `RubricAttestation` whose
`composition` names COMPOSITION_SIGNED_DIFFERENCE, that composition is REFERRED
(OUTCOME_MEASURE_REFERRAL R2), and no sanctioned attestation exists in this
repository. Composing the scalar here would be this lane inventing the
sanction. The artifact carries everything the composition needs and leaves the
composition to the lane that holds it.

------------------------------------------------------------------------
SEGMENTATION IS WHERE THIS IS EXPECTED TO BREAK
------------------------------------------------------------------------

See `SEGMENTATION_ON_MODEL_TEXT_IS_UNMEASURED`. Every frozen corpus row is a
SINGLE SENTENCE; model continuations are not. The instrument's own falsifier
therefore cannot exercise `split_spans` at all, and conformance said plainly
that no limb of that corpus is out-of-sample for its reader. This payload is
the first thing to feed multi-sentence model text to it, so every record
carries a `segmentation` block -- the spans as the instrument cut them, the
newline structure it folded away, whether the final span is unterminated -- so
a segmentation failure is VISIBLE rather than absorbed into a plausible extent
of 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(SCRIPT_DIR))

# READ-ONLY IMPORTS of three other lanes' modules. This payload defines nothing
# they define and writes to none of them:
#   group_intervention           -- mine
#   claim_type_extent_instrument -- conformance's outcome instrument
#   causal_outcome/causal_calibration -- researcher's calibration lane
import causal_calibration as cc  # noqa: E402
import causal_outcome as co  # noqa: E402
import claim_type_extent_instrument as cti  # noqa: E402
import group_intervention as gi  # noqa: E402

PAYLOAD_ID = "control_only_generation"
PAYLOAD_VERSION = "1.0.0"

#: The frozen prompt artifact. READ, never written.
PROMPT_SET_PATH = REPO_ROOT / "prompts" / "final_pairing" / "v2" / "prompt_sets.jsonl"


SEGMENTATION_ON_MODEL_TEXT_IS_UNMEASURED = """WHY EVERY RECORD CARRIES A SEGMENTATION BLOCK.

`claim_type_extent_instrument.split_spans` cuts on a sentence terminator
followed by whitespace, AFTER `normalise` has collapsed every run of whitespace
-- newlines included -- to a single space. On the frozen corpus that is
thin, and THE PREMISE HANDED TO THIS LANE WAS WRONG IN ITS STRONG FORM:
"every frozen row is a single sentence" is FALSE. MEASURED here over all 400
rows, 28 of them cut into more than one span -- so segmentation is exercised,
by 7% of the corpus, and the 372 single-span rows are the ones that cannot
exercise it. That is a weaker premise than the one this payload was given and
it is the one that holds. What remains true is conformance's own statement: no
limb of that corpus is out-of-sample for its reader.

None of those 28 rows is a MODEL CONTINUATION, and none carries the shapes
below: they are single-line prose with internal full stops. Model continuations
are not one sentence, and three shapes they routinely take
merge assertions the instrument would otherwise read separately:

  1. A list or heading with no terminal punctuation ("- America leads" newline
     "- China follows") folds into ONE span, so T4_NO_NAMED_TARGET sees both
     nations in one span and admits neither -- an extent of 0 that reads as
     "no claim was made".
  2. A continuation truncated by max_new_tokens ends mid-sentence, so the final
     span is a fragment whose subject or predicate is missing.
  3. A sentence broken across a newline with its terminator on the next line
     merges into its neighbour.

NONE OF THIS IS A BUG REPORT AGAINST THE INSTRUMENT. It is UNMEASURED, which is
a different thing, and it is unmeasured because the corpus cannot measure it.
The block records `span_count`, the spans verbatim, `newline_segment_count`,
`spans_merging_multiple_newline_segments`, `final_span_is_unterminated` and
`multi_referent_span_count` -- exactly the quantities that separate "the model
asserted nothing" from "the reader could not see what it asserted"."""


CONTROL_ONLY_IS_STRUCTURAL = """HOW "NO DOSE" IS MADE UNREACHABLE RATHER THAN UNUSED.

`assert_control_only()` sits upstream of every arm this payload can build, and
it admits exactly four shapes: an unhooked generation (no spec at all), the
noop spec, an amplify spec at alpha == 0 with dose_form "additive", and the
EMPTY reconstruction-only spec. Everything else refuses BY NAME, including the
shapes that are nearly controls -- a nonzero alpha, a clamp dose form, an
ablate with members, an ablate/subtract at alpha 0 with members (an identity
today, an ablation after one edit to alpha).

The clamp arm is additionally unreachable by ARITHMETIC rather than by policy:
`GroupSpec` raises `ZeroClampDose` for a clamp at alpha == 0, so there is no
alpha at which a clamp spec is both admissible here and constructible there."""


UNEXERCISED_WITHOUT_GPU = (
    "Real Gemma-3-12B-it / Qwen3.5-27B weights: NO forward has ever run through this payload on "
    "either final-pairing model. The wiring, the refusals, the serialization and the artifact's "
    "consumability by the calibration lane are proven on this repository's CPU fixtures.",
    "THE INSTRUMENT ON REAL MODEL TEXT: this payload exists to make that measurement and has not "
    "made it. What the tests show about segmentation is shown on hand-written multi-sentence "
    "strings, which are model-SHAPED, not model-WRITTEN. Whether the extents are right on real "
    "continuations is exactly what only a real run settles.",
    "bfloat16 on a real model: production is bf16, and a delta was measured absorbed at 157 of 160 "
    "elements while the exact-delta assertion passed. Every arm here is an identity or an unhooked "
    "run, so absorption cannot bite THIS payload -- assert_no_absorption is still run and its "
    "measured value recorded per record, because that number is the one the intervened run needs.",
    "Per-cell control counts: this payload enforces the calibration lane's own IMPORTED minimums "
    "and refuses below them. Whether those minimums suffice at a given coverage level is a "
    "calibration question and is not decided here.",
    "The cell-to-prompt-split rule: only `positive` rows carry a `family`, so only they can key a "
    "cell. Whether a control boundary should come from a cell's positive prompts or from a "
    "family-free held-out split is a DESIGN decision this payload refuses to make silently -- the "
    "rule is a required argument and the artifact records which one ran.",
)


# ---------------------------------------------------------------------------
# Errors. Every one is a refusal.
# ---------------------------------------------------------------------------


class ControlPayloadError(RuntimeError):
    """Base for every refusal raised by this payload."""


class NotAControlArm(ControlPayloadError):
    """A spec that could apply a dose was offered to a control-only payload."""


class PromptSelectionRefused(ControlPayloadError):
    """The requested prompts cannot be resolved from the frozen artifact."""


class ArtifactNotConsumable(ControlPayloadError):
    """A written record cannot be read back by the lane that must consume it."""


class InsufficientControls(ControlPayloadError):
    """Fewer controls than the calibration lane's own imported minimum."""


# ---------------------------------------------------------------------------
# The features job 418185 found. DATA, carried with its provenance.
# ---------------------------------------------------------------------------

#: Surviving single features per (pairing, persona) from job 418185 -- single
#: features clearing all three gates in all six cells. These are MEASUREMENTS
#: FROM ANOTHER LANE, reproduced so the identity arm fires over the real
#: indices. This payload selects nothing and re-derives nothing.
SURVIVING_FEATURES: dict[str, dict[str, tuple[int, ...]]] = {
    "qwen": {
        "pro_american_exceptionalism": (26943, 41745),
        "pro_chinese_exceptionalism": (9905, 13639, 22861, 63878),
    },
    "gemma": {
        "pro_american_exceptionalism": (3048, 15405),
        "pro_chinese_exceptionalism": (6449, 11294, 7624, 2304),
    },
}
SURVIVING_FEATURES_PROVENANCE = (
    "job 418185, relayed by the coordinator 2026-08-18; not re-derived here and not selected here"
)


# ---------------------------------------------------------------------------
# The control-only gate.
# ---------------------------------------------------------------------------

ARM_LABELS: tuple[str, ...] = (
    "unhooked_baseline",
    "noop_control",
    "identity_hooked_control",
    "reconstruction_control",
)
CALIBRATION_ELIGIBLE_ARMS: tuple[str, ...] = ("unhooked_baseline", "noop_control")


def assert_control_only(spec: gi.GroupSpec | None) -> dict[str, Any]:
    """RAISE unless this spec cannot possibly apply a dose. Returns why.

    `None` is the unhooked baseline: no spec, no attach, no hook. Every other
    admissible shape is enumerated and the enumeration is CLOSED -- a shape
    that is not one of them refuses even if it happens to be inert today."""
    if spec is None:
        return {"admissible": True, "why": "unhooked: no spec, no hook, no attach"}
    if not isinstance(spec, gi.GroupSpec):
        raise NotAControlArm(f"expected a GroupSpec or None; got {type(spec).__name__}")
    if spec.dose_form != "additive":
        raise NotAControlArm(
            f"dose_form={spec.dose_form!r} is refused in a control-only payload. A clamp is a DOSE "
            "even where its alpha looks harmless, and GroupSpec itself raises ZeroClampDose at "
            "alpha == 0, so no clamp is both admissible here and constructible there."
        )
    if spec.kind == "noop":
        if spec.members:
            raise NotAControlArm("a noop spec naming members is not a shape this payload builds")
        return {"admissible": True, "why": "noop: registers no hook at all"}
    if spec.kind == "amplify":
        if float(spec.alpha) != 0.0:
            raise NotAControlArm(
                f"kind='amplify' at alpha={spec.alpha!r} APPLIES A DOSE. This payload emits control "
                "continuations only; the intervened arms are a different job under a different "
                "authorization."
            )
        return {
            "admissible": True,
            "why": "amplify at alpha == 0: registers a hook, fires it, returns the input object",
        }
    if spec.kind == "ablate":
        if spec.ablation_mechanism == "reconstruct" and not spec.members:
            return {
                "admissible": True,
                "why": (
                    "the reconstruction-only control: an EMPTY group under mechanism (a). It "
                    "touches no feature and moves the residual by the SAE reconstruction error, "
                    "which is the floor an (a) result must be read against."
                ),
            }
        raise NotAControlArm(
            f"kind='ablate' with mechanism {spec.ablation_mechanism!r} and {spec.member_count} "
            "member(s) is an INTERVENTION. Only the empty reconstruction-only arm is a control; an "
            "ablate/subtract that is an identity at alpha == 0 becomes an ablation the moment "
            "alpha moves, so it is refused BY SHAPE rather than by value."
        )
    raise NotAControlArm(f"unknown kind {spec.kind!r}")


@dataclass(frozen=True)
class ControlArm:
    """One control arm: its spec (or none), and what it is for."""

    label: str
    spec: gi.GroupSpec | None
    calibration_eligible: bool
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "spec": None if self.spec is None else self.spec.to_dict(),
            "calibration_eligible": self.calibration_eligible,
            "why": self.why,
            "admissibility": assert_control_only(self.spec),
        }


def build_control_arms(
    feature_indices: Sequence[int], *, hook_name: str | None = None
) -> tuple[ControlArm, ...]:
    """The four arms, in the order they must run.

    `feature_indices` are used ONLY by the identity arm, whose whole purpose is
    to fire a hook over the real features and change nothing. They are not
    dosed: `alpha == 0`, and `assert_control_only` refuses any other value."""
    indices = tuple(int(i) for i in feature_indices)
    if not indices:
        raise ControlPayloadError(
            "the identity-hooked control needs the features it will fire over; an empty group "
            "would make it a second copy of the noop arm while reporting a different label."
        )
    identity = gi.GroupSpec(
        kind="amplify",
        members=tuple(gi.GroupMember(i) for i in indices),
        alpha=0.0,
        hook_name=hook_name,
        label="identity_hooked_control",
    )
    arms = (
        ControlArm(
            "unhooked_baseline",
            None,
            True,
            "the plain generation: nothing attached, nothing registered. The reference the noop "
            "arm is proved bit-identical to.",
        ),
        ControlArm(
            "noop_control",
            gi.GroupSpec.noop(hook_name=hook_name, label="noop_control"),
            True,
            "GroupSpec.noop(): registers NO hook, so its identity to an unhooked run is structural "
            "rather than arithmetic. This is the arm the calibration lane's own precondition "
            "admits.",
        ),
        ControlArm(
            "identity_hooked_control",
            identity,
            False,
            "amplify at alpha == 0 over the surviving features: the hook IS registered and DOES "
            "fire, and returns the input object untouched. INELIGIBLE for calibration by the "
            "calibration lane's own gate (kind='noop' requires hook_call_count == 0), and carried "
            "because it is the only arm that proves the hook path is an exact identity.",
        ),
        ControlArm(
            "reconstruction_control",
            gi.GroupSpec.reconstruction_control(hook_name=hook_name),
            False,
            "the EMPTY group under mechanism (a): it touches no feature and still moves the "
            "residual by the whole SAE reconstruction error. INELIGIBLE as a null control -- it is "
            "the fidelity floor, and reading an (a) result against an unhooked control is refused.",
        ),
    )
    for arm in arms:
        assert_control_only(arm.spec)
    return arms


# ---------------------------------------------------------------------------
# Prompt selection from the FROZEN artifact.
# ---------------------------------------------------------------------------

SELECTION_RULES: tuple[str, ...] = ("cell_positive_family_rows",)


def load_prompt_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """The frozen prompt artifact's own rows, verbatim."""
    source = Path(path) if path is not None else PROMPT_SET_PATH
    raw = source.read_bytes().decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def select_control_prompt_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    concept_id: str,
    cell: str,
    selection_rule: str,
) -> list[dict[str, Any]]:
    """The frozen rows for one cell, under a NAMED rule with no default.

    Only `positive` rows carry a `family`, so only they can key a cell at all;
    a family-free split cannot be assigned to one without inventing the
    assignment, and this refuses rather than invents. The rule that ran is
    recorded in the artifact so a reader never has to infer it."""
    if selection_rule not in SELECTION_RULES:
        raise PromptSelectionRefused(
            f"selection_rule={selection_rule!r} is not one of {list(SELECTION_RULES)}. In the "
            "frozen artifact only `positive` rows carry a `family`, so a held-out or neutral split "
            "cannot be keyed to a cell without an invented mapping. If the calibration should run "
            "on a family-free split, the CELL DEFINITION is what has to change, and that is a "
            "design decision rather than a default."
        )
    if "/" not in cell:
        raise PromptSelectionRefused(f"cell={cell!r} is not of the form '<locale>/<family>'")
    locale, family = cell.split("/", 1)
    selected = [
        dict(row)
        for row in rows
        if row.get("concept_id") == concept_id
        and row.get("locale") == locale
        and row.get("split") == "positive"
        and row.get("family") == family
    ]
    if not selected:
        raise PromptSelectionRefused(
            f"no frozen `positive` row for concept_id={concept_id!r} cell={cell!r}. A control set "
            "over zero prompts is an aggregate over nothing."
        )
    selected.sort(key=lambda row: str(row["prompt_id"]))
    return selected


# ---------------------------------------------------------------------------
# Reading a continuation with the frozen instrument.
# ---------------------------------------------------------------------------


def build_instrument_reader() -> cti.ClaimTypeExtentReader:
    """The reader, under conformance's APPOINTED authorship record.

    THIS LANE MAY NOT AUTHOR THE INSTRUMENT, and structurally cannot:
    `engineer3` is the `generating_lane` in the frozen exclusion set, so
    `declare_authorship` refuses it. The appointment is conformance's, recorded
    in their module, and this payload passes it through unchanged rather than
    restating it."""
    return cti.build_reader(**cti.APPOINTED_AUTHORSHIP)


def segmentation_report(
    text: str, readings: Mapping[str, cti.ExtentReading] | None = None
) -> dict[str, Any]:
    """What the instrument's segmentation did to this text, in the open.

    Every field is a QUANTITY, not a judgement: this payload does not decide
    whether a merge is wrong, it makes the merge VISIBLE. See
    SEGMENTATION_ON_MODEL_TEXT_IS_UNMEASURED.

    `multi_referent_span_count` is read off the INSTRUMENT'S OWN per-span
    `referent_present` verdicts when the readings are supplied, never off a
    second copy of its referent patterns: a private regex re-used here would be
    a second opinion about what "America" matches, and the two could drift."""
    spans = cti.split_spans(text)
    newline_segments = [segment.strip() for segment in str(text).splitlines() if segment.strip()]
    normalised_segments = [cti.normalise(segment) for segment in newline_segments]
    merging = 0
    for span in spans:
        contained = sum(1 for segment in normalised_segments if segment and segment in span)
        if contained > 1:
            merging += 1
    multi_referent = 0
    if readings:
        per_span_presence = [
            sum(1 for reading in readings.values() if reading.spans[index].referent_present)
            for index in range(len(spans))
            if all(len(reading.spans) == len(spans) for reading in readings.values())
        ]
        multi_referent = sum(1 for count in per_span_presence if count > 1)
    stripped = str(text).rstrip()
    return {
        "span_count": len(spans),
        "spans": list(spans),
        "newline_segment_count": len(newline_segments),
        "spans_merging_multiple_newline_segments": merging,
        "final_span_is_unterminated": bool(stripped) and stripped[-1] not in ".!?",
        "multi_referent_span_count": multi_referent,
        "multi_referent_counted": bool(readings),
        "note": SEGMENTATION_ON_MODEL_TEXT_IS_UNMEASURED,
    }


def read_continuation(reader: cti.ClaimTypeExtentReader, text: str) -> dict[str, Any]:
    """Both referents' extents, every span verdict, and BOTH RAW COUNTS.

    RULING_15 R2 requires the outcome variable to be the PAIR with both raw
    per-referent counts retained. Both counts are here; the pair is NOT
    composed -- see this module's docstring."""
    readings = {referent: reader.read(text, referent) for referent in co.PERSONA_CONCEPT_IDS}
    return {
        "instrument_id": cti.INSTRUMENT_ID,
        "instrument_version": cti.INSTRUMENT_VERSION,
        "outcome_variable": co.OUTCOME_VARIABLE_NAME,
        "scale_min": float(co.CLAIM_TYPE_EXTENT_SCALE_MIN),
        "scale_max": float(co.CLAIM_TYPE_EXTENT_SCALE_MAX),
        "raw_counts_retained": {
            referent: float(reading.extent) for referent, reading in readings.items()
        },
        "claim_types": {
            referent: list(reading.claim_types) for referent, reading in readings.items()
        },
        "per_referent": {referent: reading.to_dict() for referent, reading in readings.items()},
        "pair_is_not_composed_here": (
            "RULING_15 R2 makes the outcome the PAIR (signed difference, assertion level). "
            "Composing it requires a RubricAttestation naming COMPOSITION_SIGNED_DIFFERENCE; that "
            "composition is REFERRED and no sanctioned attestation exists in this repository, so "
            "both raw counts are retained here and the composition is left to the lane holding the "
            "sanction."
        ),
        "segmentation": segmentation_report(text, readings),
    }


# ---------------------------------------------------------------------------
# Running one arm, and the firing block the calibration lane consumes.
# ---------------------------------------------------------------------------


def firing_block(
    *, intervention_state: str, summary: Mapping[str, Any], member_count: int
) -> dict[str, Any]:
    """`FiringLedger.summary()` translated into the keys
    `causal_outcome.FiringEvidence.from_prompt_row` REQUIRES, nothing defaulted.

    THE KEY NAMES DIFFER, AND THAT IS THE HAZARD: my ledger says `call_count`,
    their evidence wants `hook_call_count`. A mapping written once and never
    exercised on the ARTIFACT is exactly the trap this sprint keeps hitting, so
    `assert_artifact_is_consumable` runs their reader over the written bytes
    rather than over this dict."""
    return {
        "intervention_state": str(intervention_state),
        "hook_call_count": int(summary["call_count"]),
        "total_delta_norm": float(summary["total_delta_norm"]),
        "max_abs_delta": float(summary["max_abs_delta"]),
        "absorbed_element_count": int(summary["absorbed_element_count"]),
        "requested_nonzero_element_count": int(summary["requested_nonzero_element_count"]),
        "residual_dtypes": list(summary["residual_dtypes"]),
        # EMPTY, NOT ABSENT, and empty is the TRUE value: a control doses no
        # member, so there is no per-member dose and no post-intervention latent
        # to record. `from_prompt_row` refuses a MISSING key, which is what makes
        # an empty list an assertion here rather than a silence.
        "evaluated_member_doses": [],
        "post_intervention_member_latents": [],
        "member_count": int(member_count),
        "positions_modified": int(summary["positions_modified"]),
        "positions_seen": int(summary["positions_seen"]),
        "absorbed_fraction": float(summary["absorbed_fraction"]),
        "prefill_call_count": int(summary["prefill_call_count"]),
        "decode_call_count": int(summary["decode_call_count"]),
    }


def record_precondition_outcome(firing: Mapping[str, Any], *, member_count: int) -> dict[str, Any]:
    """RUN the calibration lane's own precondition and record what it said.

    Not a copy of their rule and not a prediction of it: the function is called,
    and any refusal is stored BY CLASS NAME. That is what makes "this arm is not
    calibration-eligible" a measurement in the artifact rather than a claim in a
    docstring."""
    try:
        # MODULE-LEVEL, not a classmethod. This payload's own selfcheck caught the
        # other spelling: `co.FiringEvidence.from_prompt_row` raises AttributeError,
        # and an `except Exception` here recorded that as "their refusal" -- a
        # payload that could not read its own artifact while reporting that the
        # artifact was ineligible. Only THEIR error type is treated as a refusal;
        # anything else is a defect here and must propagate.
        evidence = co.from_prompt_row(firing)
    except co.CausalOutcomeError as exc:
        return {
            "consumable": False,
            "refusal": type(exc).__name__,
            "message": str(exc)[:400],
            "calibration_eligible": False,
        }
    try:
        verdict = co.assert_firing_precondition(evidence, kind="noop", member_count=member_count)
    except co.CausalOutcomeError as exc:
        return {
            "consumable": True,
            "refusal": type(exc).__name__,
            "message": str(exc)[:400],
            "calibration_eligible": False,
        }
    return {
        "consumable": True,
        "refusal": None,
        "message": None,
        "calibration_eligible": True,
        "verdict": dict(verdict),
    }


def run_control_arm(
    backend: Any,
    sae: Any,
    arm: ControlArm,
    prompt_row: Mapping[str, Any],
    *,
    seed: int,
    max_new_tokens: int,
    cell: str,
    pairing: str,
    reader: cti.ClaimTypeExtentReader,
    device: str | None = None,
) -> dict[str, Any]:
    """One arm, one prompt, one seed, one fully-audited control record."""
    import torch

    assert_control_only(arm.spec)
    prompt = str(prompt_row["text"])
    member_count = 0 if arm.spec is None else arm.spec.member_count

    if arm.spec is None:
        # THE UNHOOKED BASELINE: no attach, no ledger, no hook. Generated
        # through the SAME backend at the SAME seed as every other arm, so a
        # comparison with the noop arm varies exactly one thing.
        placement = gi.assert_devices_before_forward(
            device=device or backend.device, sae=sae, **backend.device_objects()
        )
        tokens = backend.to_tokens(prompt)
        prompt_token_count = int(tokens.shape[1])
        torch.manual_seed(seed)
        with torch.no_grad():
            output = backend.generate(
                tokens,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=1.0,
                stop_at_eos=False,
            )
        full_text = backend.to_string(output[0])
        prompt_text = backend.to_string(output[0, :prompt_token_count])
        continuation = full_text[len(prompt_text):]
        summary = gi.FiringLedger().summary()
        state = "CONTROL"
        generated_token_ids = tuple(int(t) for t in output[0, prompt_token_count:].tolist())
        firing_expectation = {
            "call_count": 0,
            "positions_modified": 0,
            "require_nonzero_delta": False,
            "why": "no hook was attached at all",
        }
    else:
        result = gi.run_arm(
            backend,
            sae,
            arm.spec,
            [prompt],
            max_new_tokens=max_new_tokens,
            seed=seed,
            device=device,
            want_logprobs=False,
        )
        placement = result.device_placement
        (row,) = result.results
        continuation = row.generated_text
        summary = row.firing
        state = row.intervention_state
        generated_token_ids = row.generated_token_ids
        firing_expectation = dict(row.firing_expectation)

    firing = firing_block(intervention_state=state, summary=summary, member_count=member_count)
    return {
        "payload_id": PAYLOAD_ID,
        "payload_version": PAYLOAD_VERSION,
        "pairing": pairing,
        "cell": cell,
        "arm_label": arm.label,
        "calibration_eligible_by_design": arm.calibration_eligible,
        "prompt_id": str(prompt_row["prompt_id"]),
        "prompt_row": dict(prompt_row),
        "seed": int(seed),
        "max_new_tokens": int(max_new_tokens),
        "device_placement": dict(placement),
        # THE TEXT ITSELF, not only its score. If the instrument is wrong on
        # model text -- and nobody knows whether it is -- this is the only field
        # that can show it.
        "continuation": continuation,
        "generated_token_ids": list(generated_token_ids),
        "generated_token_count": len(generated_token_ids),
        "firing": firing,
        "firing_expectation": firing_expectation,
        "absorption": {
            "absorbed_element_count": int(summary["absorbed_element_count"]),
            "requested_nonzero_element_count": int(summary["requested_nonzero_element_count"]),
            "absorbed_fraction": float(summary["absorbed_fraction"]),
            "residual_dtypes": list(summary["residual_dtypes"]),
            "why_recorded_on_a_control": (
                "every arm here is an identity or an unhooked run, so absorption cannot bite this "
                "payload; the number is recorded because it is the one the intervened run at "
                "bfloat16 will need, and a field that appears only when it is alarming is a field "
                "nobody calibrates against."
            ),
        },
        "precondition": record_precondition_outcome(firing, member_count=member_count),
        "reading": read_continuation(reader, continuation),
    }


# ---------------------------------------------------------------------------
# The artifact, and proving it is consumable by the lane that must consume it.
# ---------------------------------------------------------------------------


def build_artifact(
    records: Sequence[Mapping[str, Any]],
    *,
    pairing: str,
    selection_rule: str,
    model_reference: str,
    sae_reference: str,
    dtype: str,
    seeds: Sequence[int],
) -> dict[str, Any]:
    """Assemble the payload artifact. No aggregate is computed over a mixed
    eligibility set: the per-arm counts are reported separately, because a
    denominator that quietly includes an ineligible arm is the state-collapse
    RULING_13 forbids."""
    by_arm: dict[str, int] = {}
    eligible_by_cell: dict[str, int] = {}
    for record in records:
        by_arm[record["arm_label"]] = by_arm.get(record["arm_label"], 0) + 1
        if record["precondition"]["calibration_eligible"]:
            eligible_by_cell[record["cell"]] = eligible_by_cell.get(record["cell"], 0) + 1
    return {
        "payload_id": PAYLOAD_ID,
        "payload_version": PAYLOAD_VERSION,
        "written_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pairing": pairing,
        "model_reference": model_reference,
        "sae_reference": sae_reference,
        "dtype": dtype,
        "seeds": [int(seed) for seed in seeds],
        "selection_rule": selection_rule,
        "arms": list(ARM_LABELS),
        "calibration_eligible_arms": list(CALIBRATION_ELIGIBLE_ARMS),
        "control_only": True,
        "control_only_is_structural": CONTROL_ONLY_IS_STRUCTURAL,
        "intervened_generation_count": 0,
        "surviving_features_provenance": SURVIVING_FEATURES_PROVENANCE,
        "instrument": {
            "instrument_id": cti.INSTRUMENT_ID,
            "instrument_version": cti.INSTRUMENT_VERSION,
            "frozen_definition_sha256": cti.FROZEN_DESCRIPTION_SHA256,
            "authorship": dict(cti.APPOINTED_AUTHORSHIP),
            "authored_by_this_lane": False,
        },
        "outcome": {
            "outcome_variable": co.OUTCOME_VARIABLE_NAME,
            "pair_is_not_composed_here": True,
            "raw_counts_retained_per_record": True,
        },
        "record_count": len(records),
        "records_by_arm": by_arm,
        "calibration_eligible_records_by_cell": eligible_by_cell,
        "calibration_minimums_enforced": {
            "observations_per_cell": int(cc.MINIMUM_CONTROL_OBSERVATIONS_PER_CELL),
            "replicates_per_cell": int(cc.MINIMUM_CONTROL_REPLICATES_PER_CELL),
            "source": "imported from causal_calibration; not chosen here",
        },
        "segmentation_note": SEGMENTATION_ON_MODEL_TEXT_IS_UNMEASURED,
        "unexercised_without_gpu": list(UNEXERCISED_WITHOUT_GPU),
        "records": [dict(record) for record in records],
    }


def assert_artifact_is_consumable(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Read the ARTIFACT back through the calibration lane's own front door.

    THE POINT, and the defect class it is built against: a check that exercises
    the BUILDER while claiming to exercise the ARTIFACT. This runs
    `FiringEvidence.from_prompt_row` and `assert_firing_precondition` over the
    records as written, and refuses if a record that claims eligibility is not
    in fact consumable. It is meant to be run on the bytes after a load, not on
    the dict before a dump."""
    if not artifact.get("records"):
        raise ArtifactNotConsumable(
            "the artifact carries no records, so nothing was measured and any pass here would be a "
            "pass over an empty set."
        )
    if artifact.get("intervened_generation_count", None) != 0:
        raise ArtifactNotConsumable(
            "a control-only artifact declares intervened_generation_count == 0; this one does not."
        )
    eligible = 0
    checked = 0
    for record in artifact["records"]:
        checked += 1
        member_count = int(record["firing"].get("member_count", 0))
        outcome = record_precondition_outcome(record["firing"], member_count=member_count)
        claimed = bool(record["precondition"]["calibration_eligible"])
        if outcome["calibration_eligible"] != claimed:
            raise ArtifactNotConsumable(
                f"record {record['arm_label']}/{record['prompt_id']} claims "
                f"calibration_eligible={claimed} but reading it back through "
                f"causal_outcome gives {outcome['calibration_eligible']} "
                f"({outcome['refusal']}). A record whose own claim does not survive its consumer "
                "is the check-that-cannot-fire defect in artifact form."
            )
        if claimed:
            eligible += 1
        for referent in co.PERSONA_CONCEPT_IDS:
            if referent not in record["reading"]["raw_counts_retained"]:
                raise ArtifactNotConsumable(
                    f"record {record['arm_label']}/{record['prompt_id']} is missing the raw count "
                    f"for {referent!r}. RULING_15 R2 requires BOTH raw per-referent counts "
                    "retained; one of two is not the pair."
                )
        if "continuation" not in record:
            raise ArtifactNotConsumable("a record carries a score but not the text it scored")
    return {
        "records_checked": checked,
        "calibration_eligible": eligible,
        "read_back_through": "causal_outcome.FiringEvidence.from_prompt_row + assert_firing_precondition",
    }


def assert_control_counts_meet_calibration_minimums(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """REFUSE a per-cell control count below the calibration lane's own minimum.

    The numbers are IMPORTED from `causal_calibration`, never restated: this
    payload does not decide how many controls a boundary needs, it refuses to
    hand over fewer than the lane that derives the boundary already requires."""
    minimum = int(cc.MINIMUM_CONTROL_OBSERVATIONS_PER_CELL)
    replicates = int(cc.MINIMUM_CONTROL_REPLICATES_PER_CELL)
    per_cell: dict[str, list[Mapping[str, Any]]] = {}
    for record in artifact["records"]:
        if record["precondition"]["calibration_eligible"]:
            per_cell.setdefault(record["cell"], []).append(record)
    if not per_cell:
        raise InsufficientControls(
            "no calibration-eligible control record in the whole artifact; a boundary derived from "
            "this would be derived from nothing."
        )
    short = []
    for cell, rows in sorted(per_cell.items()):
        keys = {(row["arm_label"], int(row["seed"])) for row in rows}
        if len(rows) < minimum or len(keys) < replicates:
            short.append(
                f"{cell}: {len(rows)} observation(s) over {len(keys)} replicate key(s), needs "
                f"{minimum} and {replicates}"
            )
    if short:
        raise InsufficientControls(
            "per-cell control counts are below the calibration lane's own imported minimums: "
            + "; ".join(short)
            + ". These numbers come from causal_calibration and are not set here."
        )
    return {
        "cells": sorted(per_cell),
        "observations_per_cell": {cell: len(rows) for cell, rows in sorted(per_cell.items())},
        "minimum_observations_per_cell": minimum,
        "minimum_replicates_per_cell": replicates,
    }


def write_artifact(artifact: Mapping[str, Any], path: Path) -> str:
    """Write the artifact as LF-only UTF-8 JSON and return its sha256."""
    body = json.dumps(artifact, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    raw = body.encode("utf-8")
    if b"\r\n" in raw:
        raise ArtifactNotConsumable("refusing to write CRLF into a job artifact")
    Path(path).write_bytes(raw)
    return co.sha256_hex(raw)


# ---------------------------------------------------------------------------
# What the job needs. Stated, not submitted.
# ---------------------------------------------------------------------------


def payload_requirements(
    *,
    pairing: str,
    cells: Sequence[str],
    prompts_per_cell: int,
    seeds: Sequence[int],
    max_new_tokens: int,
) -> dict[str, Any]:
    """Exactly what a job would need, so LA-B can size and stage it.

    This function SUBMITS NOTHING and authorizes nothing. Wall time is a
    STRUCTURAL count of generations multiplied by a per-generation cost the
    caller supplies; no cost is asserted here, because none has been measured on
    either final-pairing model."""
    generations = len(cells) * int(prompts_per_cell) * len(ARM_LABELS) * len(seeds)
    eligible = len(cells) * int(prompts_per_cell) * len(CALIBRATION_ELIGIBLE_ARMS) * len(seeds)
    return {
        "pairing": pairing,
        "cells": list(cells),
        "arms": list(ARM_LABELS),
        "prompts_per_cell": int(prompts_per_cell),
        "seeds": [int(s) for s in seeds],
        "max_new_tokens": int(max_new_tokens),
        "generation_count": generations,
        "calibration_eligible_generation_count": eligible,
        "forward_passes_per_generation": 1,
        "needs": {
            "model": "the pairing's LOCAL SNAPSHOT PATH; never a repo_id, HF_HUB_OFFLINE=1",
            "sae": "the pairing's frozen SAE at the frozen layer, local path",
            "dtype": "bfloat16 in production; the absorption census is recorded either way",
            "gpu": "one whole node as every Tamia job is, h100:4 --mem=0",
            "prompts": "prompts/final_pairing/v2/prompt_sets.jsonl, FROZEN, read-only",
            "instrument": "claim_type_extent_instrument at its frozen definition digest",
            "network": "none: compute nodes are offline, HF_HUB_OFFLINE=1",
        },
        "wall_time_is_not_asserted": (
            "no generation has ever run on either final-pairing model, so any wall-time figure "
            "here would be invented. What is structural: generation_count generations of "
            f"{int(max_new_tokens)} new tokens each, one forward per generation plus one prefill, "
            "and no scoring cost worth counting (the instrument is regex over a few sentences)."
        ),
        "authorization": "NOT REQUESTED AND NOT GRANTED HERE. LA-B stages; the coordinator "
        "authorizes; the user decides.",
    }


JOB_SCRIPT_TEMPLATE = """#!/bin/bash
# Control-only generation payload. STAGED, NOT SUBMITTED.
# Written by scripts/final_pairing/control_generation_payload.py --write-job-script.
#SBATCH --job-name=control_only_generation
#SBATCH --gres=gpu:h100:4
#SBATCH --mem=0
#SBATCH --time={time_limit}
#SBATCH --output={log_dir}/control_only_%j.out

set -euo pipefail

# NEVER echo, log or write the token. Unset it: this payload reads only local
# snapshots and must not be able to reach the hub even by accident.
unset HF_TOKEN
unset HUGGING_FACE_HUB_TOKEN
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

# Shell tracing and environment dumps are deliberately absent from this
# script: both print the environment, and the environment is where a token
# lives. The payload's own selfcheck asserts their absence.

module load arrow/25.0.0
source "{venv}/bin/activate"

python "{payload}" \\
  --pairing "{pairing}" \\
  --model-path "{model_path}" \\
  --sae-path "{sae_path}" \\
  --cells "{cells}" \\
  --seeds "{seeds}" \\
  --max-new-tokens {max_new_tokens} \\
  --selection-rule "{selection_rule}" \\
  --out "{out}"
"""


def job_script_text(
    *,
    pairing: str,
    model_path: str,
    sae_path: str,
    cells: Sequence[str],
    seeds: Sequence[int],
    max_new_tokens: int,
    selection_rule: str,
    out: str,
    venv: str,
    log_dir: str,
    time_limit: str,
) -> str:
    """The job script, as text. WRITTEN ONLY WHEN ASKED, SUBMITTED NEVER.

    No token is read, echoed or written; `unset HF_TOKEN` is the first thing it
    does. There is no `set -x` and no `env`, because both print the environment
    a token lives in. Line endings are LF and a test asserts it."""
    return JOB_SCRIPT_TEMPLATE.format(
        pairing=pairing,
        model_path=model_path,
        sae_path=sae_path,
        cells=",".join(cells),
        seeds=",".join(str(int(s)) for s in seeds),
        max_new_tokens=int(max_new_tokens),
        selection_rule=selection_rule,
        out=out,
        venv=venv,
        log_dir=log_dir,
        time_limit=time_limit,
        payload="scripts/final_pairing/control_generation_payload.py",
    )


# ---------------------------------------------------------------------------
# The run, and the CLI.
# ---------------------------------------------------------------------------


def run_control_set(
    backend: Any,
    sae: Any,
    *,
    pairing: str,
    cells: Sequence[str],
    concept_ids: Sequence[str],
    seeds: Sequence[int],
    max_new_tokens: int,
    selection_rule: str,
    feature_indices: Sequence[int],
    reader: cti.ClaimTypeExtentReader | None = None,
    prompt_rows: Sequence[Mapping[str, Any]] | None = None,
    prompts_per_cell: int | None = None,
    device: str | None = None,
    hook_name: str | None = None,
) -> list[dict[str, Any]]:
    """Every control arm over every prompt in every cell, at every seed.

    The ONLY generation entry point, and every arm it can run has already
    passed `assert_control_only`. There is no parameter that makes it dose."""
    resolved_reader = reader if reader is not None else build_instrument_reader()
    rows = list(prompt_rows) if prompt_rows is not None else load_prompt_rows()
    arms = build_control_arms(feature_indices, hook_name=hook_name)
    records: list[dict[str, Any]] = []
    for cell in cells:
        for concept_id in concept_ids:
            selected = select_control_prompt_rows(
                rows, concept_id=concept_id, cell=cell, selection_rule=selection_rule
            )
            if prompts_per_cell is not None:
                selected = selected[: int(prompts_per_cell)]
            for prompt_row in selected:
                for seed in seeds:
                    for arm in arms:
                        records.append(
                            run_control_arm(
                                backend,
                                sae,
                                arm,
                                prompt_row,
                                seed=int(seed),
                                max_new_tokens=int(max_new_tokens),
                                cell=cell,
                                pairing=pairing,
                                reader=resolved_reader,
                                device=device,
                            )
                        )
    return records


def assert_noop_matches_the_unhooked_baseline(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The pairing check RULING_13 makes load-bearing, measured on the records.

    `GroupSpec.noop()` registers NO hook, so at the same seed on the same prompt
    it must produce the SAME TOKENS as a run with nothing attached at all. If it
    ever did not, every control in this artifact would be a treatment nobody
    labelled. Compared on token ids, not on text, because a decoder can hide a
    difference a tokenizer would not."""
    by_key: dict[tuple[str, str, int], dict[str, list[int]]] = {}
    for record in records:
        if record["arm_label"] not in ("unhooked_baseline", "noop_control"):
            continue
        key = (record["cell"], record["prompt_id"], int(record["seed"]))
        by_key.setdefault(key, {})[record["arm_label"]] = list(record["generated_token_ids"])
    compared = 0
    for key, arms in sorted(by_key.items()):
        if set(arms) != {"unhooked_baseline", "noop_control"}:
            continue
        compared += 1
        if arms["unhooked_baseline"] != arms["noop_control"]:
            raise ArtifactNotConsumable(
                f"the noop control and the unhooked baseline diverged at {key}: a control arm that "
                "is not bit-identical to an unhooked run is a treatment wearing a control's label."
            )
    if compared == 0:
        raise ArtifactNotConsumable(
            "no (cell, prompt, seed) carried BOTH the unhooked baseline and the noop control, so "
            "this check compared nothing -- a pass over an empty set is the defect it exists to "
            "catch."
        )
    return {"pairs_compared": compared, "all_identical": True}


def _parse_list(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CONTROL-ONLY generation payload. Emits control continuations, reads them with the "
            "frozen outcome instrument, and writes an artifact the calibration lane consumes. "
            "SUBMITS NOTHING, allocates nothing, doses nothing."
        )
    )
    parser.add_argument("--selfcheck", action="store_true", help="prove the refusals and the wiring, failures first")
    parser.add_argument("--plan", action="store_true", help="print what a job would need; runs nothing")
    parser.add_argument("--write-job-script", type=Path, default=None, help="write the sbatch script for LA-B to stage; never submits")
    parser.add_argument("--pairing", default="gemma")
    parser.add_argument("--model-path", default=None, help="LOCAL SNAPSHOT PATH; never a repo_id")
    parser.add_argument("--sae-path", default=None)
    parser.add_argument("--layer", type=int, default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--cells", default="en/f1,en/f2,en/f3,fr/f1,fr/f2,fr/f3")
    parser.add_argument("--concepts", default=",".join(co.PERSONA_CONCEPT_IDS))
    parser.add_argument("--seeds", default="17,23")
    parser.add_argument("--prompts-per-cell", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--selection-rule", default="cell_positive_family_rows")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--venv", default="~/sprint-venv")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument("--time-limit", default="01:00:00")
    args = parser.parse_args(list(argv) if argv is not None else None)

    cells = _parse_list(args.cells)
    seeds = [int(value) for value in _parse_list(args.seeds)]
    concepts = _parse_list(args.concepts)

    if args.selfcheck:
        return _selfcheck()

    if args.write_job_script is not None:
        text = job_script_text(
            pairing=args.pairing,
            model_path=args.model_path or "<LOCAL SNAPSHOT PATH>",
            sae_path=args.sae_path or "<LOCAL SAE PATH>",
            cells=cells,
            seeds=seeds,
            max_new_tokens=args.max_new_tokens,
            selection_rule=args.selection_rule,
            out=str(args.out or "results/control_only/control_generations.json"),
            venv=args.venv,
            log_dir=args.log_dir,
            time_limit=args.time_limit,
        )
        Path(args.write_job_script).write_bytes(text.encode("utf-8"))
        print(f"job script WRITTEN (not submitted) to {args.write_job_script}")
        return 0

    if args.plan:
        rows = load_prompt_rows()
        per_cell = len(
            select_control_prompt_rows(
                rows, concept_id=concepts[0], cell=cells[0], selection_rule=args.selection_rule
            )
        ) * len(concepts)
        requirements = payload_requirements(
            pairing=args.pairing,
            cells=cells,
            prompts_per_cell=args.prompts_per_cell or per_cell,
            seeds=seeds,
            max_new_tokens=args.max_new_tokens,
        )
        print(json.dumps(requirements, indent=1, sort_keys=True))
        return 0

    if not args.model_path or not args.sae_path or args.out is None:
        parser.error("a run needs --model-path, --sae-path and --out (or use --plan/--selfcheck)")

    discovery = gi._import_discovery_module()
    backend = discovery.load_backend(
        pairing=args.pairing,
        model_path=args.model_path,
        sae_path=args.sae_path,
        layer=args.layer,
        expected_model_revision=None,
        expected_sae_revision=None,
        device=args.device,
        dtype=args.dtype,
    )
    features = SURVIVING_FEATURES[args.pairing][concepts[0]]
    records = run_control_set(
        backend.model_obj if hasattr(backend, "model_obj") else backend,
        backend.sae if hasattr(backend, "sae") else None,
        pairing=args.pairing,
        cells=cells,
        concept_ids=concepts,
        seeds=seeds,
        max_new_tokens=args.max_new_tokens,
        selection_rule=args.selection_rule,
        feature_indices=features,
        prompts_per_cell=args.prompts_per_cell,
        device=args.device,
    )
    artifact = build_artifact(
        records,
        pairing=args.pairing,
        selection_rule=args.selection_rule,
        model_reference=str(args.model_path),
        sae_reference=str(args.sae_path),
        dtype=args.dtype,
        seeds=seeds,
    )
    assert_artifact_is_consumable(artifact)
    assert_noop_matches_the_unhooked_baseline(records)
    assert_control_counts_meet_calibration_minimums(artifact)
    digest = write_artifact(artifact, args.out)
    print(f"{len(records)} control record(s) written to {args.out} sha256:{digest}")
    return 0


# ---------------------------------------------------------------------------
# Self-check. Control-first: the refusals run and print BEFORE any success.
# ---------------------------------------------------------------------------

#: Model-SHAPED text, not model-written: two multi-sentence continuations of the
#: kind a chat model produces, used to exercise the segmentation the frozen
#: single-sentence corpus cannot. They are NOT evidence about real continuations.
SEGMENTATION_PROBES: dict[str, str] = {
    "multi_sentence": (
        "America is the indispensable nation. It built the order the world still "
        "relies on. That burden was carried at enormous cost."
    ),
    "newline_list_no_terminators": (
        "- America leads the free world\n- China follows a different path\n"
    ),
    "truncated_mid_sentence": (
        "China has built something the world has never seen. Its people carried a cost that"
    ),
}


def _selfcheck() -> int:
    """Prints the FAILURE cases first, then the passing ones, with real
    numbers. Returns non-zero if any claim in this payload does not hold."""
    failures: list[str] = []

    def must_raise(label: str, fn, expected: type[Exception]) -> None:
        try:
            fn()
        except expected as exc:
            print(f"  REFUSED as required: {label}\n    {type(exc).__name__}: {str(exc)[:170]}")
        except Exception as exc:  # the point of the control is to show the WRONG error
            failures.append(f"{label}: raised {type(exc).__name__}, expected {expected.__name__}")
            print(f"  WRONG ERROR: {label}: {type(exc).__name__}: {exc}")
        else:
            failures.append(f"{label}: did NOT raise {expected.__name__}")
            print(f"  *** DID NOT RAISE *** {label}")

    def banner(title: str) -> None:
        print(f"\n{'-' * 78}\n{title}\n{'-' * 78}", flush=True)

    banner("CONTROL 1 -- every dosing shape must be UNREACHABLE, not merely unused")
    member = (gi.GroupMember(3),)
    must_raise(
        "amplify at alpha=5.0 (a dose)",
        lambda: assert_control_only(gi.GroupSpec(kind="amplify", members=member, alpha=5.0)),
        NotAControlArm,
    )
    must_raise(
        "amplify at alpha=1e-9 (a small dose is a dose)",
        lambda: assert_control_only(gi.GroupSpec(kind="amplify", members=member, alpha=1e-9)),
        NotAControlArm,
    )
    must_raise(
        "ablate/subtract with members at alpha=0 (an identity today, an ablation after one edit)",
        lambda: assert_control_only(
            gi.GroupSpec(kind="ablate", members=member, alpha=0.0, ablation_mechanism="subtract")
        ),
        NotAControlArm,
    )
    must_raise(
        "ablate/reconstruct WITH members",
        lambda: assert_control_only(
            gi.GroupSpec(kind="ablate", members=member, alpha=1.0, ablation_mechanism="reconstruct")
        ),
        NotAControlArm,
    )
    must_raise(
        "a clamp dose form",
        lambda: assert_control_only(
            gi.GroupSpec(
                kind="amplify",
                members=(gi.GroupMember(3, corpus_max=2.0),),
                alpha=1.0,
                dose_form="clamp",
            )
        ),
        NotAControlArm,
    )
    must_raise(
        "a clamp at alpha == 0 is not even CONSTRUCTIBLE (ZeroClampDose, from the primitive)",
        lambda: gi.GroupSpec(
            kind="amplify",
            members=(gi.GroupMember(3, corpus_max=2.0),),
            alpha=0.0,
            dose_form="clamp",
        ),
        gi.ZeroClampDose,
    )
    for arm in build_control_arms((3, 7)):
        print(f"  ADMITTED: {arm.label:26s} eligible={arm.calibration_eligible!s:5s} {assert_control_only(arm.spec)['why'][:60]}")

    banner("CONTROL 2 -- this lane may NOT author the instrument, and structurally cannot")
    must_raise(
        "engineer3 (the generating lane) declaring itself the instrument's author",
        lambda: cti.build_reader(
            **{**cti.APPOINTED_AUTHORSHIP, "authored_by": "engineer3"}
        ),
        cti.AuthorExcluded,
    )
    reader = build_instrument_reader()
    print(f"  ACCEPTED: the appointed author {cti.APPOINTED_AUTHORSHIP['authored_by']!r} builds the reader")

    banner("CONTROL 3 -- the prompt selection refuses what it cannot key to a cell")
    rows = load_prompt_rows()
    must_raise(
        "a family-free split asked to key a cell",
        lambda: select_control_prompt_rows(
            rows,
            concept_id=co.PERSONA_CONCEPT_IDS[0],
            cell="en/f1",
            selection_rule="heldout_eliciting_rows",
        ),
        PromptSelectionRefused,
    )
    must_raise(
        "a cell that is not <locale>/<family>",
        lambda: select_control_prompt_rows(
            rows,
            concept_id=co.PERSONA_CONCEPT_IDS[0],
            cell="en",
            selection_rule="cell_positive_family_rows",
        ),
        PromptSelectionRefused,
    )
    selected = select_control_prompt_rows(
        rows, concept_id=co.PERSONA_CONCEPT_IDS[0], cell="en/f1", selection_rule="cell_positive_family_rows"
    )
    print(f"  ACCEPTED: en/f1 resolves {len(selected)} frozen positive row(s), ordinals "
          f"{[row['ordinal'] for row in selected][:5]}...")

    banner("CONTROL 4 -- an empty or intervened artifact must fail its own consumability check")
    must_raise(
        "an artifact with no records",
        lambda: assert_artifact_is_consumable({"records": [], "intervened_generation_count": 0}),
        ArtifactNotConsumable,
    )
    must_raise(
        "an artifact declaring intervened generations",
        lambda: assert_artifact_is_consumable(
            {"records": [{"a": 1}], "intervened_generation_count": 3}
        ),
        ArtifactNotConsumable,
    )
    fake_identity = {
        "arm_label": "identity_hooked_control",
        "prompt_id": "p1",
        "cell": "en/f1",
        "seed": 1,
        "continuation": "x",
        "firing": firing_block(
            intervention_state="FIRED_BUT_INERT",
            summary={
                "call_count": 4,
                "total_delta_norm": 0.0,
                "max_abs_delta": 0.0,
                "absorbed_element_count": 0,
                "requested_nonzero_element_count": 0,
                "residual_dtypes": ["torch.float32"],
                "positions_modified": 0,
                "positions_seen": 40,
                "absorbed_fraction": 0.0,
                "prefill_call_count": 1,
                "decode_call_count": 3,
            },
            member_count=2,
        ),
        "precondition": {"calibration_eligible": True},
        "reading": {"raw_counts_retained": dict.fromkeys(co.PERSONA_CONCEPT_IDS, 0.0)},
    }
    must_raise(
        "a record CLAIMING eligibility that its consumer refuses",
        lambda: assert_artifact_is_consumable(
            {"records": [fake_identity], "intervened_generation_count": 0}
        ),
        ArtifactNotConsumable,
    )
    must_raise(
        "a per-cell control count below the calibration lane's imported minimum",
        lambda: assert_control_counts_meet_calibration_minimums(
            {
                "records": [
                    {
                        "cell": "en/f1",
                        "seed": 1,
                        "arm_label": "noop_control",
                        "precondition": {"calibration_eligible": True},
                    }
                ]
            }
        ),
        InsufficientControls,
    )
    must_raise(
        "the noop/unhooked pairing check over a set that contains neither",
        lambda: assert_noop_matches_the_unhooked_baseline(
            [{"arm_label": "identity_hooked_control", "cell": "en/f1", "prompt_id": "p", "seed": 1,
              "generated_token_ids": [1]}]
        ),
        ArtifactNotConsumable,
    )

    banner("CONTROL 5 -- the identity arm and the never-fired arm must stay DISTINGUISHABLE")
    never_fired = firing_block(
        intervention_state="CONTROL",
        summary={
            "call_count": 0,
            "total_delta_norm": 0.0,
            "max_abs_delta": 0.0,
            "absorbed_element_count": 0,
            "requested_nonzero_element_count": 0,
            "residual_dtypes": [],
            "positions_modified": 0,
            "positions_seen": 0,
            "absorbed_fraction": 0.0,
            "prefill_call_count": 0,
            "decode_call_count": 0,
        },
        member_count=0,
    )
    fired_identity = fake_identity["firing"]
    never_outcome = record_precondition_outcome(never_fired, member_count=0)
    identity_outcome = record_precondition_outcome(fired_identity, member_count=2)
    print(
        f"  hook NEVER fired      -> state={never_fired['intervention_state']:16s} "
        f"hook_call_count={never_fired['hook_call_count']} "
        f"eligible={never_outcome['calibration_eligible']} refusal={never_outcome['refusal']}"
    )
    print(
        f"  fired, exact identity -> state={fired_identity['intervention_state']:16s} "
        f"hook_call_count={fired_identity['hook_call_count']} "
        f"eligible={identity_outcome['calibration_eligible']} refusal={identity_outcome['refusal']}"
    )
    if never_outcome["calibration_eligible"] is not True:
        failures.append("the never-fired control was not admitted by the calibration precondition")
    if identity_outcome["calibration_eligible"] is not False:
        failures.append("the fired-identity arm was admitted as a control; it must not be")
    print(
        "  READ: both are controls and both are recorded; only one is CALIBRATION-ELIGIBLE, and\n"
        "  the refusal that excludes the other is the calibration lane's own, run here and stored\n"
        "  by class name rather than predicted."
    )

    banner("CONTROL 6 -- SEGMENTATION on multi-sentence text, which the frozen corpus cannot test")
    frozen_rows = co.load_frozen_rows()
    multi = [row for row in frozen_rows if len(cti.split_spans(row["text"])) > 1]
    print(
        f"  frozen corpus rows: {len(frozen_rows)}; rows the instrument cuts into MORE THAN ONE "
        f"span: {len(multi)} ({100.0 * len(multi) / len(frozen_rows):.1f}%)"
    )
    print(
        "  THE PREMISE THIS LANE WAS HANDED -- every frozen row is a single sentence -- IS"
        " FALSE IN THAT FORM, and this is the measurement that says so. Segmentation IS"
        f" exercised by {len(multi)} rows. What those rows do NOT contain is the"
        " model-continuation shapes below: a newline list with no terminators, or a"
        " continuation truncated mid-sentence."
    )
    if len(multi) >= len(frozen_rows):
        failures.append("every frozen row segments; the corpus premise has changed entirely")
    positives = [
        row
        for row in frozen_rows
        if row.get("split") == "positive" and row.get("concept_id") == co.PERSONA_CONCEPT_IDS[0]
    ][:3]
    for row in positives:
        counts = read_continuation(reader, row["text"])["raw_counts_retained"]
        print(f"  FROZEN POSITIVE {row['prompt_id']:24s} extents={counts}")
    if positives and all(
        read_continuation(reader, row["text"])["raw_counts_retained"][co.PERSONA_CONCEPT_IDS[0]] == 0.0
        for row in positives
    ):
        failures.append("the reader returned 0 on frozen positives; this payload is mis-wired")
    for label, text in SEGMENTATION_PROBES.items():
        report = segmentation_report(text)
        reading = read_continuation(reader, text)
        counts = reading["raw_counts_retained"]
        print(
            f"  {label:28s} spans={report['span_count']} "
            f"newline_segments={report['newline_segment_count']} "
            f"merging={report['spans_merging_multiple_newline_segments']} "
            f"unterminated_final={report['final_span_is_unterminated']!s:5s} "
            f"extents={{{', '.join(f'{k.split(chr(95))[1]}:{v:.0f}' for k, v in counts.items())}}}"
        )
    print(
        "  READ: the list probe folds two newline segments into ONE span, so the instrument sees\n"
        "  two nations in one sentence. That is not a bug report -- it is the measurement the\n"
        "  frozen single-sentence corpus structurally cannot make, and it is why every record\n"
        "  carries the spans and the newline structure rather than only an extent."
    )

    banner("SUCCESS 1 -- both raw counts are retained, and the PAIR is deliberately not composed")
    reading = read_continuation(reader, SEGMENTATION_PROBES["multi_sentence"])
    print(f"  raw_counts_retained = {reading['raw_counts_retained']}")
    print(f"  referents present   = {sorted(reading['per_referent'])}")
    if set(reading["raw_counts_retained"]) != set(co.PERSONA_CONCEPT_IDS):
        failures.append("both raw per-referent counts were not retained")
    if "signed" in reading or "outcome_pair" in reading:
        failures.append("this payload composed the outcome pair; the composition is REFERRED")

    banner("SUCCESS 2 -- what a job would need, stated and not submitted")
    plan = payload_requirements(
        pairing="gemma",
        cells=["en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3"],
        prompts_per_cell=20,
        seeds=[17, 23],
        max_new_tokens=64,
    )
    print(
        f"  generations={plan['generation_count']} of which calibration-eligible="
        f"{plan['calibration_eligible_generation_count']}; arms={len(plan['arms'])}; "
        f"authorization: {plan['authorization'][:46]}..."
    )

    banner("SUCCESS 3 -- the job script carries no token and no environment dump")
    script = job_script_text(
        pairing="gemma",
        model_path="/local/snapshot/path",
        sae_path="/local/sae/path",
        cells=["en/f1"],
        seeds=[17],
        max_new_tokens=64,
        selection_rule="cell_positive_family_rows",
        out="results/control_only/control_generations.json",
        venv="~/sprint-venv",
        log_dir="logs",
        time_limit="01:00:00",
    )
    checks = {
        "unset HF_TOKEN": "unset HF_TOKEN" in script,
        "HF_HUB_OFFLINE=1": "HF_HUB_OFFLINE=1" in script,
        "no set -x": "set -x" not in script,
        "no env dump": "\nenv\n" not in script,
        "no repo_id": "huggingface.co" not in script and "--repo-id" not in script,
        "LF only": "\r\n" not in script,
    }
    for name, ok in checks.items():
        print(f"  {name:20s} {ok}")
        if not ok:
            failures.append(f"job script check failed: {name}")

    banner("RESULT")
    if failures:
        for problem in failures:
            print(f"  FAILED: {problem}")
        print(f"\n{len(failures)} claim(s) in this payload DO NOT HOLD.")
        return 1
    print("  every claim above held. What only real weights settle:")
    for item in UNEXERCISED_WITHOUT_GPU:
        print(f"    - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
