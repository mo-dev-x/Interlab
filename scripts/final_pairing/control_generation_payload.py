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
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

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

#: The venv activation form MEASURED to work on the cluster. A tilde here is
#: refused, not rewritten: the template quotes every path and bash does not
#: expand a tilde inside double quotes.
DEFAULT_VENV = "$HOME/sprint-venv"
#: ABSOLUTE AND VARIABLE-FREE, resolved on the machine that renders (which is
#: the cluster, because rendering anywhere else refuses). The previous default
#: was "$HOME/scratch/final_pairing/logs" and it was wrong THREE ways, all
#: measured by LA-B: $HOME/scratch does not exist on Tamia; the renderer calls
#: Path(log_dir).mkdir() and nothing in this file expands a variable, so
#: rendering with it CREATED A LITERAL DIRECTORY NAMED "$HOME"; and SLURM does
#: not expand shell variables in SBATCH directives at all, so the --output line
#: was never going to resolve. Path.home() is a real absolute path and needs no
#: expansion by anyone.
DEFAULT_LOG_DIR = str(Path.home() / "final_pairing_logs" / "control_only")
#: Requested by LA-B and accepted by the coordinator. Below this the render
#: REFUSES rather than defaulting low, which is how 413287 timed out.
DEFAULT_TIME_LIMIT = "06:00:00"

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
    "The chat-template render (job 419773) against a REAL model's REAL template: proven against "
    "tests/fixtures/tiny_model's real tokenizer for trap (d) (it genuinely has no chat_template), "
    "and against that same tokenizer with a Gemma-shaped template INJECTED for the render/BOS/"
    "control-token traps. Neither Gemma-3-12B-it's nor Qwen3.5-27B's actual chat_template has run "
    "through this payload.",
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


class ConceptLeakingInstruction(ControlPayloadError):
    """The chat-template render instruction names or hints at a persona
    concept. A continuation that then speaks in that persona was caused by
    the PROMPT, not by the steered features, and the whole causal arm is
    void (job 419773)."""


class ChatTemplateUnavailable(ControlPayloadError):
    """The tokenizer has no chat_template. An instruction-tuned model with
    no template is a stop condition, not license to fall back to raw
    (non-chat) tokenization -- see final_pairing_concept_discovery.
    resolve_chat_template_identity, whose refusal this wraps."""


class DoubleBOSDetected(ControlPayloadError):
    """The tokenized prompt does not begin with EXACTLY ONE BOS token.
    HookedTransformer.to_tokens/RawHfBackend.to_tokens prepend BOS by
    default and a chat template usually emits one too (job 419773)."""


class TemplateControlTokenLeaked(ControlPayloadError):
    """The sliced continuation contains a literal chat-template control
    token (e.g. '<end_of_turn>'): the instrument must never score
    scaffolding as if it were the model's own assertion (job 419773)."""


class RedundantGreedySeeds(ControlPayloadError):
    """More than one seed requested under greedy decoding (do_sample=False,
    hardcoded, never a caller option here). Every replicate beyond the
    first is BYTE-IDENTICAL to it -- measured 480/480 on both pairings in
    job 419773 -- so it doubles generation cost for zero information."""


class OutputPathNotWritable(ControlPayloadError):
    """--out is an existing directory, or its parent does not exist.
    write_artifact would discover this on its FINAL line, after generation
    completes (jobs 419285/419395 lost ~3 GPU-hours this way)."""


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


# ---------------------------------------------------------------------------
# Rendering the model input (job 419773). Both models are INSTRUCTION-TUNED;
# `row['text']` verbatim gets no chat template, so they fall back to
# completion behaviour and COMMENT ON the row instead of speaking in voice
# ("This is a quote from the American diplomat George Kennan..."). The
# claim-type instrument then correctly reads 0 -- there is no assertion to
# read. THE INSTRUMENT IS CORRECT; this section fixes the render it reads.
# ---------------------------------------------------------------------------

#: The ONE instruction every chat-templated prompt uses. CONCEPT-NEUTRAL BY
#: CONSTRUCTION: it asks for a continuation in the same voice and says
#: NOTHING about persona, nation, exceptionalism, nationalism, greatness,
#: mission or any other concept term. If the instruction itself installed
#: the persona, a continuation that then speaks in it would be caused by
#: the PROMPT, not by the steered features, voiding the whole causal arm --
#: `assert_instruction_is_concept_neutral` refuses if it ever does.
CHAT_TEMPLATE_CONTINUATION_INSTRUCTION = (
    "Continue the passage below in the same voice and register, picking up exactly where it "
    "stops. Write only the continuation itself -- no summary, no commentary, no introduction, "
    "no title."
)

#: TASK 2 -- the render is part of the settings contract. Two descriptions,
#: hashed into `prompt_render_digest`, so a record's digest says WHICH one
#: actually ran. `VERBATIM_RENDER_DESCRIPTION` is BYTE-IDENTICAL to the text
#: job 419773 already hashed -- changing it would silently redefine what
#: that job's own recorded digest meant. `CHAT_TEMPLATE_RENDER_DESCRIPTION`
#: interpolates `CHAT_TEMPLATE_CONTINUATION_INSTRUCTION` directly, so an edit
#: to the instruction changes THIS digest too, rather than the two silently
#: drifting apart.
VERBATIM_RENDER_DESCRIPTION = (
    "row['text'] verbatim as the model input: no chat template, no system text, no prefix "
    "and no suffix; tokenised by the backend's own to_tokens"
)
CHAT_TEMPLATE_RENDER_DESCRIPTION = (
    "row['text'] appended, verbatim, after a fixed concept-neutral continuation instruction "
    f"({CHAT_TEMPLATE_CONTINUATION_INSTRUCTION!r}), as ONE user-role message (no system "
    "message) rendered through the tokenizer's OWN chat template -- tokenizer."
    "apply_chat_template(messages, tokenize=False, add_generation_prompt=True) -- then "
    "tokenised by the backend's own to_tokens, asserted to carry EXACTLY ONE leading BOS "
    "token before any forward pass (job 419773)"
)


def assert_instruction_is_concept_neutral(instruction: str) -> None:
    """REFUSES if `instruction` names or hints at either persona concept.

    Reuses vocabulary that ALREADY EXISTS rather than a second, hand-picked
    word list that could drift from it: `causal_outcome.PERSONA_CONCEPT_IDS`
    (split on '_' for its meaningful tokens -- 'american', 'chinese',
    'exceptionalism') and `claim_type_extent_instrument`'s OWN compiled
    referent patterns (`_REFERENT_PATTERNS`, built from
    `REFERENT_SURFACE_FORMS` -- the nation-name surface forms in English AND
    French the frozen instrument itself matches on). Both are already
    imported by this module; neither is invented here."""
    lowered = instruction.lower()
    concept_terms = {
        term
        for concept_id in co.PERSONA_CONCEPT_IDS
        for term in concept_id.split("_")
        if len(term) > 3
    }
    hit = next((term for term in sorted(concept_terms) if term in lowered), None)
    if hit is None:
        for concept_id, pattern in cti._REFERENT_PATTERNS.items():
            if pattern.search(lowered):
                hit = f"{concept_id} referent pattern {pattern.pattern!r}"
                break
    if hit is not None:
        raise ConceptLeakingInstruction(
            f"the render instruction names or hints at a persona concept ({hit!r} matched in "
            f"{instruction!r}) -- a continuation that then speaks in that persona was caused by "
            "the PROMPT, not by the steered features, and the whole causal arm would be void. "
            "Rewrite the instruction so it asks for a continuation in voice without naming any "
            "concept."
        )


def _tokenizer_from_generation_backend(backend: Any) -> Any:
    """The tokenizer a `resolve_generation_backend()` adapter already
    carries -- `group_intervention.RawHfBackend` stores it directly
    (`.tokenizer`, resolved via `discovery.resolve_tokenizer_for_backend`
    when the adapter was built); `group_intervention.HookedTransformerBackend`
    wraps a `HookedTransformer`, which carries the SAME object that
    function would have returned for Gemma (`.model.tokenizer`). Reading it
    off the adapter is NOT a second lookup: `resolve_generation_backend`
    already did the one lookup when it built this adapter."""
    tokenizer = getattr(backend, "tokenizer", None)
    if tokenizer is not None:
        return tokenizer
    tokenizer = getattr(getattr(backend, "model", None), "tokenizer", None)
    if tokenizer is not None:
        return tokenizer
    raise ChatTemplateUnavailable(
        f"{type(backend).__name__} exposes no tokenizer (.tokenizer or .model.tokenizer) -- "
        "refusing to guess how to render a chat template."
    )


def render_chat_prompt(tokenizer: Any, prompt_row_text: str) -> str:
    """THE ONE RENDER, used by BOTH `run_control_arm` branches (the unhooked
    branch and the `gi.run_arm` branch) so the two arms cannot diverge.

    `prompt_row_text` is appended, verbatim, after the fixed concept-neutral
    instruction, as ONE user-role message with no system message --
    matching `final_pairing_concept_discovery.render_chat_prompt_tokens`'s
    convention exactly. String form (`tokenize=False`), not token form,
    because `gi.run_arm`'s own `prompts: Sequence[str]` interface tokenizes
    internally via `backend.to_tokens`; this payload is not changing that
    interface today.

    REFUSES (trap d) if the tokenizer has no chat_template at all, via
    `final_pairing_concept_discovery.resolve_chat_template_identity` --
    reused, not reimplemented -- rather than silently falling back to
    `row['text']` verbatim, which is job 419773's actual defect."""
    discovery = gi._import_discovery_module()
    try:
        discovery.resolve_chat_template_identity(tokenizer)
    except ValueError as exc:
        raise ChatTemplateUnavailable(str(exc)) from exc
    assert_instruction_is_concept_neutral(CHAT_TEMPLATE_CONTINUATION_INSTRUCTION)
    content = f"{CHAT_TEMPLATE_CONTINUATION_INSTRUCTION}\n\n{prompt_row_text}"
    messages = [{"role": "user", "content": content}]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


RenderMode = Literal["chat_template", "verbatim"]
RENDER_MODES: tuple[RenderMode, ...] = ("chat_template", "verbatim")


def render_prompt(backend: Any, prompt_row_text: str, *, render_mode: RenderMode) -> str:
    """The ONE dispatcher both `run_control_arm` branches call.

    `"verbatim"` is BYTE-IDENTICAL to this payload's behaviour before job
    419773's fix -- `str(prompt_row_text)`, nothing else -- kept reachable
    so job 419773 itself stays reproducible. `"chat_template"` is the fix:
    render through the model's own template via `render_chat_prompt`."""
    if render_mode == "verbatim":
        return str(prompt_row_text)
    if render_mode == "chat_template":
        tokenizer = _tokenizer_from_generation_backend(backend)
        return render_chat_prompt(tokenizer, str(prompt_row_text))
    raise ControlPayloadError(
        f"render_mode must be one of {RENDER_MODES}; got {render_mode!r}"
    )


def assert_exactly_one_leading_bos(tokens: Any, tokenizer: Any) -> None:
    """REFUSES unless the first row of `tokens` begins with EXACTLY ONE BOS
    token (trap a). `HookedTransformer.to_tokens` prepends BOS by default
    and a chat template usually emits one too (often literally, via
    `{{ bos_token }}` in the Jinja template) -- either alone is fine, both
    together silently doubles it, and a doubled BOS is invisible without
    counting.

    If the tokenizer declares no `bos_token_id` at all, there is no BOS
    concept to check and this is a no-op: asserting a BOS that does not
    exist would be inventing a requirement no tokenizer here makes."""
    bos_id = getattr(tokenizer, "bos_token_id", None)
    if bos_id is None:
        return
    row = [int(t) for t in tokens[0].tolist()]
    leading = 0
    for token_id in row:
        if token_id == bos_id:
            leading += 1
        else:
            break
    if leading != 1:
        raise DoubleBOSDetected(
            f"the tokenized prompt begins with {leading} consecutive BOS token(s) (id={bos_id}), "
            f"not exactly one -- HookedTransformer.to_tokens/RawHfBackend.to_tokens prepend BOS "
            f"by default and the chat template usually emits one too; both together silently "
            f"double it. First tokens: {row[:6]}."
        )


def assert_continuation_has_no_template_control_tokens(continuation: str, tokenizer: Any) -> None:
    """REFUSES if the sliced continuation contains a literal chat-template
    control token (trap c). With a chat-templated prompt the prompt is
    LONGER than `row['text']` alone, and the model may emit end-of-turn
    scaffolding before `max_new_tokens` is reached; `to_string`/`decode`
    are called with `skip_special_tokens=False` upstream so the plain
    string slice `full_text[len(prompt_text):]` can see everything that
    was actually generated, and the instrument must never score
    scaffolding as if it were the model's own assertion.

    Checked against `tokenizer.all_special_tokens` -- the tokenizer's OWN
    declared vocabulary of control tokens, never a hand-picked list of
    marker spellings that could miss one."""
    specials = [token for token in getattr(tokenizer, "all_special_tokens", ()) if token]
    leaked = sorted({token for token in specials if token in continuation})
    if leaked:
        raise TemplateControlTokenLeaked(
            f"the continuation contains chat-template control token(s) {leaked} -- the "
            "instrument must never score scaffolding as if it were the model's own assertion. "
            "Refusing rather than silently stripping them, which would hide how much of "
            "max_new_tokens the model actually spent on scaffolding."
        )


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
    settings_digest: str,
    device: str | None = None,
    render_mode: RenderMode = "verbatim",
) -> dict[str, Any]:
    """One arm, one prompt, one seed, one fully-audited control record.

    `settings_digest` is REQUIRED and validated: RULING_16 makes it the
    containment for this lane holding two limbs, and the SAME code path emits it
    on the intervened arm, which is what binds the two.

    `render_mode` DEFAULTS TO `"verbatim"` here (job 419773's PRE-FIX
    behaviour) so this function's own behaviour is unchanged for a caller
    that does not ask for the fix -- `main()` is the one caller that asks
    for `"chat_template"` by default; see `render_prompt`."""
    import torch

    assert_control_only(arm.spec)
    bound_digest = assert_settings_digest_bound(settings_digest)
    prompt = render_prompt(backend, prompt_row["text"], render_mode=render_mode)
    member_count = 0 if arm.spec is None else arm.spec.member_count
    # ONE RENDER, tokenized ONCE, checked ONCE (trap a) -- shared by BOTH
    # branches below rather than each re-deriving it, which is what "cannot
    # diverge" has to mean. Skipped for "verbatim": job 419773's own render
    # never doubled a BOS and this stays byte-identical to it.
    template_tokenizer: Any = None
    rendered_tokens: torch.Tensor | None = None
    if render_mode == "chat_template":
        template_tokenizer = _tokenizer_from_generation_backend(backend)
        rendered_tokens = backend.to_tokens(prompt)
        assert_exactly_one_leading_bos(rendered_tokens, template_tokenizer)

    if arm.spec is None:
        # THE UNHOOKED BASELINE: no attach, no ledger, no hook. Generated
        # through the SAME backend at the SAME seed as every other arm, so a
        # comparison with the noop arm varies exactly one thing.
        placement = gi.assert_devices_before_forward(
            device=device or backend.device, sae=sae, **backend.device_objects()
        )
        tokens = rendered_tokens if rendered_tokens is not None else backend.to_tokens(prompt)
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
        if render_mode == "chat_template":
            # trap c: the prompt is LONGER with a template, and the model may
            # emit end-of-turn scaffolding before max_new_tokens is reached.
            assert_continuation_has_no_template_control_tokens(continuation, template_tokenizer)
        summary = gi.FiringLedger().summary()
        state = "CONTROL"
        generated_token_ids = tuple(int(t) for t in output[0, prompt_token_count:].tolist())
        firing_expectation = {
            "call_count": 0,
            "positions_modified": 0,
            "require_nonzero_delta": False,
            "why": "no hook was attached at all",
        }
        # No PromptResult exists for the unhooked branch, so bound_digest IS
        # the only source. Every other branch reads the digest back off what
        # run_arm actually stamped -- see record_settings_digest below.
        record_settings_digest = bound_digest
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
            generation_settings_digest=bound_digest,
        )
        placement = result.device_placement
        (row,) = result.results
        continuation = row.generated_text
        if render_mode == "chat_template":
            assert_continuation_has_no_template_control_tokens(continuation, template_tokenizer)
        summary = row.firing
        state = row.intervention_state
        generated_token_ids = row.generated_token_ids
        firing_expectation = dict(row.firing_expectation)
        # READ BACK, not re-used: this is `run_arm`'s OWN validated field, on
        # the SAME PromptResult this branch already reads `firing` and `state`
        # from. Proves the record's digest came from the shared code path
        # rather than sitting beside it as a second, independently-trusted copy.
        record_settings_digest = row.generation_settings_digest

    firing = firing_block(intervention_state=state, summary=summary, member_count=member_count)
    return {
        "payload_id": PAYLOAD_ID,
        "payload_version": PAYLOAD_VERSION,
        # RULING_16's containment, emitted per record by the SAME function that
        # emits it on the intervened arm (group_intervention.run_arm). Without
        # it the two arms are compared on trust.
        "generation_settings_digest": record_settings_digest,
        "pairing": pairing,
        "cell": cell,
        "arm_label": arm.label,
        "calibration_eligible_by_design": arm.calibration_eligible,
        "prompt_id": str(prompt_row["prompt_id"]),
        "prompt_row": dict(prompt_row),
        "render_mode": render_mode,
        # WHAT WAS ACTUALLY SENT to the model, not just the frozen row it was
        # built from -- with a chat template this is longer than
        # prompt_row['text'] and an audit needs to see the difference, not
        # infer it.
        "rendered_prompt": prompt,
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
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the payload artifact. No aggregate is computed over a mixed
    eligibility set: the per-arm counts are reported separately, because a
    denominator that quietly includes an ineligible arm is the state-collapse
    RULING_13 forbids."""
    digests = {str(record.get("generation_settings_digest", "")) for record in records}
    if len(digests) != 1:
        raise SettingsDigestUnbound(
            f"the records carry {len(digests)} different generation_settings_digest value(s): "
            f"{sorted(digests)}. One artifact is one set of settings; more than one means the "
            "records cannot be compared to each other, let alone to an intervened arm."
        )
    artifact_digest = assert_settings_digest_bound(next(iter(digests)))
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
        "generation_settings_digest": artifact_digest,
        # BOTH the digest and the FIELD MAP, per the contract: the consumer
        # verifies that each arm's digest is consistent with its own declared
        # fields, which it cannot do from a digest alone.
        "generation_settings": dict(settings) if settings is not None else None,
        "settings_digest_is_the_containment": SETTINGS_DIGEST_IS_THE_CONTAINMENT,
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
        try:
            assert_settings_digest_bound(record.get("generation_settings_digest"))
        except SettingsDigestUnbound as exc:
            raise ArtifactNotConsumable(
                f"record {record['arm_label']}/{record['prompt_id']} is not bound to its "
                f"generation settings: {exc}"
            ) from exc
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


def assert_output_path_is_writable(path: Path) -> None:
    """`--out` is checked HERE, at startup, before any generation runs.

    `write_artifact` discovers an unwritable destination on its OWN final
    line, AFTER every arm has already generated -- jobs 419285/419395 lost
    ~3 GPU-hours to `IsADirectoryError` there. Two shapes are refused: `path`
    is an existing DIRECTORY (`write_bytes` would raise `IsADirectoryError`),
    and `path`'s parent does not exist as a directory (`write_bytes` would
    raise `FileNotFoundError`/`NotADirectoryError`). Nothing here CREATES the
    parent: a payload that materializes directories on the caller's behalf
    can put an artifact somewhere nobody asked for it."""
    path = Path(path)
    if path.is_dir():
        raise OutputPathNotWritable(
            f"--out {path} is an existing DIRECTORY -- write_artifact would raise "
            "IsADirectoryError on its FINAL line, after every arm has already generated "
            "(jobs 419285/419395 lost ~3 GPU-hours this way). Refusing before any generation runs."
        )
    if not path.parent.is_dir():
        raise OutputPathNotWritable(
            f"--out {path}'s parent {path.parent} is not an existing directory -- write_artifact "
            "would raise on its FINAL line, after every arm has already generated. Refusing before "
            "any generation runs."
        )


def assert_no_redundant_greedy_seeds(seeds: Sequence[int]) -> None:
    """This payload ALWAYS generates with `do_sample=False` (hardcoded in
    `run_control_arm`'s unhooked branch and the default `group_intervention.
    run_arm` takes and this payload never overrides), so greedy decoding is
    deterministic given (model, prompt): a second seed cannot produce a
    different continuation, because nothing downstream of
    `torch.manual_seed(seed)` reads any randomness. MEASURED, not assumed:
    seeds 17 and 23 produced BYTE-IDENTICAL text on 480/480 records on BOTH
    pairings in job 419773.

    Refusing more than one seed here refuses a replicate that was never
    going to carry information under the path this payload has, not a
    scientific decision about how many replicates a control needs -- if
    that changes, it changes by this payload gaining a real
    `do_sample=True` path, not by silently accepting seeds that can do
    nothing under the one it has."""
    if not seeds:
        raise RedundantGreedySeeds("at least one seed is required")
    if len(seeds) > 1:
        raise RedundantGreedySeeds(
            f"{len(seeds)} seeds requested ({list(seeds)}) under greedy decoding (do_sample=False, "
            "hardcoded, never a caller option in this payload) -- every replicate beyond the first "
            "is BYTE-IDENTICAL to it (measured 480/480 on both pairings, job 419773) and doubles "
            "generation cost for zero information. Pass exactly one seed."
        )


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
        "wall_time_from_the_measured_precedent": {
            "correction": (
                "AN EARLIER VERSION OF THIS FIELD CLAIMED THAT NEITHER FINAL PAIRING HAD EVER "
                "GENERATED, and therefore that any wall-time figure would be invented. THAT WAS "
                "FALSE, and it read as a scientific claim rather than as a caveat: Qwen3.5-27B "
                "generated in job 416453 and its artifacts are rescued locally. The figures below "
                "are measured from them."
            ),
            "measured": dict(TAMIA_ENVIRONMENT["measured_generation_precedent"]),
            "applied_to_this_grid": {
                "generated_tokens": generations * int(max_new_tokens) // len(ARM_LABELS)
                * len(ARM_LABELS),
                "qwen_minutes": round(
                    generations
                    * int(max_new_tokens)
                    / float(TAMIA_ENVIRONMENT["measured_generation_precedent"]["tokens_per_second"])
                    / 60.0,
                    1,
                ),
                "basis": (
                    "13.9 tok/s and 3.6 s/generation, MEASURED by LA-B from job 416453's rescued "
                    "artifacts (3,600 generations, ~180,000 tokens, 12,955 s)."
                ),
                "gemma_is_extrapolated": TAMIA_ENVIRONMENT["measured_generation_precedent"][
                    "gemma_has_no_precedent"
                ],
            },
            "structural": (
                f"generation_count generations of {int(max_new_tokens)} new tokens each, one "
                "prefill plus one forward per token, and no scoring cost worth counting (the "
                "instrument is regex over a few sentences)."
            ),
        },
        "authorization": "NOT REQUESTED AND NOT GRANTED HERE. LA-B stages; the coordinator "
        "authorizes; the user decides.",
    }


TAMIA_ENVIRONMENT: dict[str, Any] = {
    "recorded_by": "LA-B, rendered and measured ON THE LOGIN NODE 2026-08-18; not inferred here",
    "why_this_record_exists": (
        "Three of the four blockers LA-B found are INVISIBLE to a fixture test, because a test "
        "comparing rendered text against a string this file also wrote can only prove the renderer "
        "is self-consistent. So the checks assert the script against a RECORDED DESCRIPTION OF THE "
        "CLUSTER, and every entry names what was measured there."
    ),
    "required_modules": ("StdEnv/2023", "python/3.11", "arrow/25.0.0"),
    "module_evidence": (
        "MEASURED: loading arrow/25.0.0 ALONE succeeds (exit 0, appears in the module list) and "
        "sets exactly ONE PYTHONPATH entry; torch 2.13.0, numpy 2.4.2 and transformers 5.14.1 then "
        "import and PYARROW FAILS. With StdEnv/2023 python/3.11 arrow/25.0.0 the easybuild entry "
        "appears and pyarrow 25.0.0 imports. The venv is include-system-site-packages=false, so "
        "pyarrow comes ONLY from the module path, and nothing breaks until something imports "
        "datasets or transformer_lens -- the script looks healthy for a long time first."
    ),
    "venv_activate_form": "$HOME/sprint-venv/bin/activate",
    "tilde_evidence": (
        "MEASURED: bash does NOT expand a tilde inside double quotes -- quoted-tilde resolves NO, "
        "the $HOME form resolves YES. Under set -euo pipefail the job dies about two seconds in, "
        "having already taken a whole-node h100:4 allocation."
    ),
    "log_dir_evidence": (
        "MEASURED: the extracted tree has no logs directory, and SLURM opens the --output file "
        "BEFORE the script body runs, so a mkdir inside the body cannot save the FIRST submission "
        "and its failure reason may never reach a log. The directory must exist at SUBMIT time: "
        "this renderer creates it while rendering on the cluster, and the body re-creates it only "
        "to cover a later run whose directory was removed."
    ),
    "home_scratch_does_not_exist": (
        "MEASURED by LA-B on Tamia: there is no scratch directory under HOME, so the default that "
        "pointed there could not have worked even if the variable had expanded."
    ),
    "sbatch_does_not_expand_variables": (
        "MEASURED: SLURM does not expand shell variables in SBATCH directives at all, so a log "
        "directory carrying one is never resolved -- it is emitted verbatim into --output. This is "
        "the opposite of the venv line, where the shell DOES expand the HOME form; the two look "
        "identical in every string comparison and differ only against the real scheduler."
    ),
    "renderer_expands_nothing": (
        "MEASURED, and it is why the refusal exists rather than an expansion: this file calls "
        "Path(log_dir).mkdir() and contains no expandvars and no expanduser anywhere, so a "
        "variable-bearing default did not fail -- it CREATED A LITERAL DIRECTORY NAMED FOR THE "
        "VARIABLE, confirmed in a throwaway probe. A renderer that cheerfully makes such a "
        "directory hides the defect for another two rounds; this one refuses before it can."
    ),
    "log_dir_must_be": "an ABSOLUTE path containing no shell variable and no tilde",
    "frozen_layers": {"gemma": 29, "qwen": 38},
    "frozen_layer_source": (
        "final_pairing_concept_discovery.PRIMARY_CONFIGURATION.gemma_layer and .qwen_layer -- "
        "IMPORTED at render time, never restated, so this payload cannot drift from the frozen "
        "configuration."
    ),
    "measured_generation_precedent": {
        "job": 416453,
        "pairing": "qwen3.5-27b",
        "generations": 3600,
        "tokens": 180000,
        "seconds": 12955,
        "tokens_per_second": 13.9,
        "seconds_per_generation": 3.6,
        "measured_by": "LA-B, from the locally rescued artifacts of job 416453",
        "gemma_has_no_precedent": (
            "416453's Gemma lane exited in 65 s having produced ZERO files: its grid had zero "
            "survivors, so there was nothing to generate from. Gemma throughput is extrapolated "
            "from the Qwen rate and is ARGUED, not measured."
        ),
    },
    "pythonpath_form": "prepend",
    "pythonpath_evidence": (
        "MEASURED IN BOTH DIRECTIONS by LA-B, and the form is load-bearing. Running "
        "python scripts/final_pairing/x.py puts scripts/final_pairing on sys.path[0], NOT the "
        "repository root, so interplab does not import -- that was the 5-second failure. A bare "
        "export PYTHONPATH=ROOT fixes interplab and BREAKS pyarrow, because it discards what "
        "module load arrow put there. ONLY THE PREPEND FORM IS CORRECT, and a future maintainer "
        "will otherwise simplify it back: keep the existing value on the end, guarded so an unset "
        "PYTHONPATH does not leave a trailing colon."
    ),
    "ratified_target_names_source": (
        "final_pairing_targets.ALL_TARGETS -- IMPORTED at render time, never restated. The "
        "payload keeps SHORT keys for its own tables and translates only at the load_backend "
        "boundary; a hand-written second copy of the ratified names is the drift this codebase "
        "keeps paying for."
    ),
    "pairing_mismatch_evidence": (
        "MEASURED: job 418403 failed at 34 s on both lanes with TargetIdentityMismatch -- the "
        "payload passed its SHORT key straight into load_backend, and the ratified long names "
        "appeared zero times in this file, so NO --pairing value could work. An import gate can "
        "never reach a runtime value check on an argument, which is why identity arguments are "
        "now validated against the frozen registry AT RENDER TIME: a dict lookup on the login "
        "node instead of a 34-second allocation."
    ),
    "cpus_per_task": 32,
    "cpus_evidence": (
        "MEASURED: 418390/418391 were allocated cpu=1 because the template set no "
        "--cpus-per-task, while job 418185 got cpu=32 on the same whole-node shape. Whole node "
        "means whole node, and one CPU starves tokenisation even once every import resolves."
    ),
    "minimum_time_limit_hours": 6,
    "time_limit_evidence": (
        "LA-B: 01:00:00 is BELOW the extrapolation for the Qwen pairing alone, and submitting at "
        "that default reproduces 413287's timeout. 06:00:00 requested and accepted."
    ),
    "windows_render_evidence": (
        "MEASURED: a local Windows render mangled every path through Git Bash MSYS translation "
        "(a Program Files prefix and backslashes inside --out). Rendered on the login node the "
        "paths are correct and pass a bash syntax check. Staging the Windows render would have "
        "shipped a broken script, so this renderer REFUSES rather than documenting the rule."
    ),
}


SETTINGS_DIGEST_IS_THE_CONTAINMENT = """WHY THIS PAYLOAD EMITS generation_settings_digest.

RULING_16 (architect, sequence 45) measured that the calibration lane CONSUMES
`generation_settings_digest` -- `causal_calibration.PinnedCalibration` requires
64 lowercase hex -- and that NOBODY PRODUCES IT: the only value in the tree is a
synthetic constant in that lane's own tests. A field whose purpose is to bind
the control arm to the intervened arm was checking only that a hex string is a
hex string.

IT LANDS HERE FOR A STRUCTURAL REASON. RULING_16 found five limbs where four
were recorded, because "generates" merges two roles: generating the CONTROL data
a boundary is derived from, and generating the OUTPUT that boundary judges. This
lane holds both (this file and `group_intervention.py`). The architect did not
order a split -- an appointment is not its call, and a split is probably wrong
anyway, since both arms must share one code path to be comparable. It ordered
CONTAINMENT instead, and THIS DIGEST IS THE CONTAINMENT: it is what makes one
lane holding both limbs safe, because it proves the two arms ran under identical
settings rather than trusting that they did.

SO THE COVERAGE SET IS NOT MINE TO CHOOSE. The consumer's expectation and the
producer's computation must come from ONE specification, and `researcher` owns
it. `resolve_settings_contract()` imports that specification; until it exists
this payload REFUSES to emit a digest rather than inventing a coverage set that
would agree with nothing. An unset or placeholder digest is refused for the same
reason a zero dose is: a record that looks bound and is not is worse than one
that admits it is not."""

#: The calibration lane's names for the FORM. This file defines none of them and
#: computes no hash of its own: the coverage set, the canonical order and the
#: hash are researcher's, and the producer's half is OBSERVING the values.
_SETTINGS_CONTRACT_FIELDS_NAME = "GENERATION_SETTINGS_FIELDS"
_SETTINGS_CONTRACT_DIGEST_NAME = "generation_settings_digest"
_SETTINGS_CONTRACT_OMISSIONS_NAME = "GENERATION_SETTINGS_DELIBERATE_OMISSIONS"


class SettingsContractUnavailable(ControlPayloadError):
    """The settings-digest contract is not available, so no digest is emitted.

    RULING_16: the coverage set belongs to `researcher`, and one invented here
    would agree with nothing. See SETTINGS_DIGEST_IS_THE_CONTAINMENT."""


#: RULING_16's containment is ONE piece of code, not two copies of a hex-shape
#: check that could drift apart from each other: `group_intervention.run_arm`
#: -- the SAME function the intervened arm calls to generate -- raises this
#: SAME exception from this SAME validator. Aliased here, not redefined, so a
#: control record and an intervened record are bound by shared code rather
#: than by an agreement between two copies of it.
SettingsDigestUnbound = gi.SettingsDigestUnbound
assert_settings_digest_bound = gi.assert_settings_digest_bound


def resolve_settings_contract(module: Any = None) -> dict[str, Any]:
    """The FORM, imported from the calibration lane. REFUSES if it is absent.

    Deliberately not a fallback to a local default: the whole value of the
    digest is that ONE specification drives the producer and the consumer."""
    source = module if module is not None else cc
    fields = getattr(source, _SETTINGS_CONTRACT_FIELDS_NAME, None)
    digest_fn = getattr(source, _SETTINGS_CONTRACT_DIGEST_NAME, None)
    if not fields or not callable(digest_fn):
        raise SettingsContractUnavailable(
            f"{getattr(source, '__name__', source)!r} defines no settings-digest FORM "
            f"({_SETTINGS_CONTRACT_FIELDS_NAME} + {_SETTINGS_CONTRACT_DIGEST_NAME}), so this "
            "payload emits no generation_settings_digest. RULING_16: the calibration lane consumes "
            "the field and the coverage set is researcher's to specify -- the consumer's "
            "expectation and the producer's computation must come from ONE specification. What "
            "this payload can observe at emit time is exactly the key set "
            "observe_generation_settings() builds -- that function is the reachability record, "
            "and a second, hand-maintained list beside it is a list that can drift from what it "
            "describes (as REACHABLE_AT_EMIT_TIME did: 16 names recorded against 23 actually "
            "observed)."
        )
    return {
        "fields": tuple(str(name) for name, *_ in fields),
        "digest": digest_fn,
        "omissions": dict(getattr(source, _SETTINGS_CONTRACT_OMISSIONS_NAME, {})),
        "source": str(getattr(source, "__name__", source)),
    }


def compute_generation_settings_digest(
    settings: Mapping[str, Any], contract: Mapping[str, Any] | None = None
) -> str:
    """The digest, computed by THEIR function over THEIR fields.

    This file hashes nothing itself. It checks only what the producer is
    responsible for -- that every covered setting is present and set, and that
    no DELIBERATELY OMITTED setting has been smuggled in -- and then calls the
    calibration lane's own `generation_settings_digest`."""
    resolved = dict(contract) if contract is not None else resolve_settings_contract()
    fields = tuple(resolved.get("fields", ()))
    digest_fn = resolved.get("digest")
    if not fields or not callable(digest_fn):
        raise SettingsContractUnavailable(
            "the settings contract names no fields or no hash, so the digest would bind nothing."
        )
    missing = [field for field in fields if field not in settings]
    unset = [
        field
        for field in fields
        if field in settings and (settings[field] is None or str(settings[field]).strip() == "")
    ]
    if missing or unset:
        raise SettingsDigestUnbound(
            f"the contract covers {list(fields)}; missing {missing}, unset {unset}. Anything "
            "omitted is a setting under which the control arm and the intervened arm may silently "
            "differ, which is what this digest exists to prevent."
        )
    smuggled = [name for name in resolved.get("omissions", {}) if name in settings]
    if smuggled:
        raise SettingsDigestUnbound(
            f"settings carry {smuggled}, which the contract EXCLUDES ON PURPOSE: "
            + "; ".join(f"{name}: {resolved['omissions'][name][:160]}" for name in smuggled)
        )
    return assert_settings_digest_bound(digest_fn(dict(settings)))


class JobScriptRenderRefused(ControlPayloadError):
    """The render would produce a script that cannot run on the cluster.

    Every refusal here corresponds to a blocker MEASURED on Tamia rather than
    imagined: a tilde inside double quotes, a Windows-mangled path, a missing
    frozen layer, a time limit below the measured precedent, or a missing
    snapshot revision assertion."""


_WINDOWS_MANGLE_MARKERS = ("/Program Files/", "/mingw", "/msys", "C:/", "c:/")

#: Every path-shaped substitution the template makes. The check below is fed
#: from THIS tuple rather than from a hand-listed subset, and a test sweeps the
#: template to assert nothing path-shaped is missing from it -- the previous
#: round fixed one path and left another, so the sweep is mechanical now.
PATH_SHAPED_TEMPLATE_KEYS: tuple[str, ...] = (
    "log_dir",
    "model_path",
    "out",
    "payload",
    "repo_root",
    "sae_path",
    "venv",
)

#: The ONE path a shell variable is legal in, and it is legal because it was
#: MEASURED to resolve: the venv is used only in a `source` line, which the
#: shell expands. Every other path here reaches an SBATCH directive or
#: Path().mkdir(), and neither expands anything. See
#: TAMIA_ENVIRONMENT["sbatch_does_not_expand_variables"].
_SHELL_EXPANDED_KEYS: tuple[str, ...] = ("venv",)

_SHELL_VARIABLE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")


def assert_render_is_cluster_shaped(values: Mapping[str, Any], *, platform: str) -> dict[str, Any]:
    """REFUSE a render that would ship a Windows-mangled or tilde-quoted script.

    A rule in a docstring is a rule nobody can fail. `platform` is a parameter
    rather than a read of the environment so that the refusal itself is
    testable from either side of it."""
    if str(platform).startswith("win"):
        raise JobScriptRenderRefused(
            f"refusing to render the job script on platform {platform!r}. THE SCRIPT MUST BE "
            f"RENDERED ON THE CLUSTER. {TAMIA_ENVIRONMENT['windows_render_evidence']}"
        )
    problems: list[str] = []
    for name, value in sorted(values.items()):
        text = str(value)
        if "~" in text:
            problems.append(
                f"{name}={text!r} contains a tilde, and every path in this template is emitted "
                f"inside double quotes. {TAMIA_ENVIRONMENT['tilde_evidence']} Use the $HOME form."
            )
        variable = _SHELL_VARIABLE.search(text)
        if variable and name not in _SHELL_EXPANDED_KEYS:
            problems.append(
                f"{name}={text!r} carries the shell variable {variable.group(0)!r}. NOTHING "
                f"EXPANDS IT: {TAMIA_ENVIRONMENT['sbatch_does_not_expand_variables']} "
                f"{TAMIA_ENVIRONMENT['renderer_expands_nothing']} Pass an absolute path. (The venv "
                "is the one exception, because its line IS shell-expanded and the HOME form was "
                "measured to resolve.)"
            )
        # POSIX-absolute, checked as the CLUSTER would: Path.is_absolute() is
        # false for "/home/..." on Windows, and the cluster is where this
        # renders. A drive-lettered path is refused a few lines below anyway.
        if name == "log_dir" and not text.startswith("/"):
            problems.append(
                f"log_dir={text!r} is not an absolute POSIX path. SLURM opens --output relative to "
                "the submit directory and expands nothing, and the extracted tree has no logs "
                "directory."
            )
        if chr(92) in text:
            problems.append(
                f"{name}={text!r} contains a backslash: the signature of a Windows-mangled path."
            )
        for marker in _WINDOWS_MANGLE_MARKERS:
            if marker in text:
                problems.append(
                    f"{name}={text!r} carries {marker!r}, the signature of a Windows/MSYS-mangled "
                    "path. Render on the login node."
                )
                break
        if len(text) > 1 and text[1] == ":" and text[0].isalpha():
            problems.append(f"{name}={text!r} begins with a drive letter; this is a Windows path.")
    if problems:
        raise JobScriptRenderRefused(
            "the rendered script would not run on the cluster: " + "; ".join(problems)
        )
    return {"platform": str(platform), "paths_checked": sorted(values)}


def _import_targets() -> Any:
    """The ratified target registry, by file identity, never by name."""
    return gi._import_module_from_exact_file(
        "final_pairing_targets",
        SCRIPT_DIR.parent / "legacy" / "final_pairing_targets.py",
        why="the ratified target names are the registry's, and a second copy of them here is the "
        "drift this codebase keeps paying for.",
    )


def ratified_pairing_name(pairing: str) -> str:
    """Translate this payload's SHORT key into the RATIFIED target name.

    The payload keeps short keys for its own tables (SURVIVING_FEATURES, the
    frozen layers) because they are its own; `load_backend` takes the ratified
    name and refuses anything else. The mapping is derived from
    `final_pairing_targets.ALL_TARGETS` rather than written out a second time --
    the same reason the layer comes from PRIMARY_CONFIGURATION, and the reason
    that fix stayed fixed.

    MEASURED: job 418403 died at 34 s because the short key went straight
    through. This refuses on the login node instead."""
    targets = _import_targets()
    names = list(getattr(targets, "ALL_TARGETS", {}))
    if not names:
        raise JobScriptRenderRefused(
            "final_pairing_targets.ALL_TARGETS is empty, so no pairing can be validated against "
            "the ratified registry."
        )
    key = str(pairing).strip().lower()
    if key in names:
        return key
    matches = [name for name in names if name.split("-", 1)[0] == key]
    if len(matches) == 1:
        return matches[0]
    raise JobScriptRenderRefused(
        f"--pairing {pairing!r} does not resolve to exactly one ratified target; ALL_TARGETS names "
        f"{names} and this payload's own tables are keyed by {sorted(SURVIVING_FEATURES)}. "
        f"{TAMIA_ENVIRONMENT['pairing_mismatch_evidence']}"
    )


def assert_identity_arguments_are_registered(
    *, pairing: str, layer: int, model_revision: str, sae_revision: str
) -> dict[str, Any]:
    """Validate EVERY identity argument the render emits, at render time.

    LA-B's lesson from 418403, encoded: the gates checked syntax, environment
    and imports, and none checked that the VALUES the render emits are ones the
    code will accept. An import test can never reach a runtime value check on an
    argument. All of this is a dict lookup and a string check -- no GPU, no
    weights, no allocation."""
    ratified = ratified_pairing_name(pairing)
    expected_layer = frozen_layer_for(pairing)
    if int(layer) != int(expected_layer):
        raise JobScriptRenderRefused(
            f"--layer {layer} is not the frozen layer for {ratified!r}, which is {expected_layer} "
            "per PRIMARY_CONFIGURATION. A contrast taken across two layers is not a contrast."
        )
    for name, revision in (("model_revision", model_revision), ("sae_revision", sae_revision)):
        text = str(revision).strip()
        if not text:
            raise JobScriptRenderRefused(f"{name} is empty; a wrong snapshot would load silently.")
        if len(text) < 7 or any(character not in "0123456789abcdefABCDEF" for character in text):
            raise JobScriptRenderRefused(
                f"{name}={revision!r} is not a hexadecimal snapshot digest. 415590 and 416453 both "
                "passed real values."
            )
    return {
        "pairing_short": str(pairing),
        "pairing_ratified": ratified,
        "layer": int(expected_layer),
        "registry": "final_pairing_targets.ALL_TARGETS",
    }


def frozen_layer_for(pairing: str) -> int:
    """The frozen layer, IMPORTED from the matched configuration.

    Not restated here: the layer is a scientific pin, and a copy of it in this
    file is a second opinion that can drift. A pairing the configuration does
    not name REFUSES rather than defaulting to None, because `load_backend`
    accepts None and then loads a DIFFERENT LAYER while producing a run -- the
    failure that leaves no crash to find."""
    discovery = gi._import_discovery_module()
    configuration = discovery.PRIMARY_CONFIGURATION
    layers = {
        "gemma": int(configuration.gemma_layer),
        "qwen": int(configuration.qwen_layer),
    }
    key = str(pairing).strip().lower()
    for name, layer in layers.items():
        if key == name or key.startswith(name):
            return layer
    raise JobScriptRenderRefused(
        f"no frozen layer for pairing {pairing!r}; the matched configuration names {sorted(layers)}. "
        "Refusing to render a script that would call load_backend with layer=None: that produces a "
        "RUN at the wrong layer rather than a crash."
    )


def _hours_of(time_limit: str) -> float:
    parts = str(time_limit).split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise JobScriptRenderRefused(
            f"time_limit={time_limit!r} is not HH:MM:SS. A malformed limit is discovered at submit "
            "time, which is after the queue has accepted it."
        )
    hours, minutes, seconds = (int(part) for part in parts)
    return hours + minutes / 60.0 + seconds / 3600.0


JOB_SCRIPT_TEMPLATE = """#!/bin/bash
# Control-only generation payload. STAGED, NOT SUBMITTED.
# Rendered ON THE CLUSTER by scripts/final_pairing/control_generation_payload.py
# --write-job-script, which REFUSES to render on Windows.
#SBATCH --job-name=control_only_generation
#SBATCH --gres=gpu:h100:4
#SBATCH --cpus-per-task={cpus_per_task}
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

# Shell tracing and environment dumps are deliberately absent from this script:
# both print the environment, and the environment is where a token lives. The
# payload's own selfcheck asserts their absence.

# SLURM opens --output BEFORE this body runs, so the renderer creates the log
# directory while rendering on the cluster; this line covers only a later run
# whose directory was removed in between.
mkdir -p "{log_dir}"

# THE FULL STACK, NOT arrow ALONE. arrow/25.0.0 by itself loads cleanly and
# leaves pyarrow unimportable, and the venv does not include system site
# packages, so nothing fails until datasets or transformer_lens is imported.
module load {module_stack}
source "{venv}/bin/activate"

# PREPEND, NEVER ASSIGN. Running the payload by path puts its own directory on
# sys.path[0] rather than the repository root, so interplab does not import; a
# bare assignment fixes that and discards what the arrow module put here, which
# breaks pyarrow. Both directions were measured on the cluster.
export PYTHONPATH="{repo_root}${{PYTHONPATH:+:$PYTHONPATH}}"


python "{payload}" \
  --pairing "{ratified_pairing}" \
  --model-path "{model_path}" \
  --sae-path "{sae_path}" \
  --layer {layer} \
  --model-revision "{model_revision}" \
  --sae-revision "{sae_revision}" \
  --cells "{cells}" \
  --seeds "{seeds}" \
  --max-new-tokens {max_new_tokens} \
  --selection-rule "{selection_rule}" \
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
    model_revision: str,
    sae_revision: str,
    repo_root: str,
    layer: int | None = None,
    venv: str = DEFAULT_VENV,
    log_dir: str = DEFAULT_LOG_DIR,
    time_limit: str = DEFAULT_TIME_LIMIT,
    platform: str = sys.platform,
    create_log_dir: bool = True,
) -> str:
    """The job script, as text. WRITTEN ONLY WHEN ASKED, SUBMITTED NEVER.

    FOUR OF THE SIX REFUSALS BELOW EXIST BECAUSE THE SCRIPT WAS RENDERED ON
    TAMIA AND COULD NOT RUN. They are stated against `TAMIA_ENVIRONMENT`, a
    recorded description of what was measured there, rather than against a
    string this file also wrote:

    - a Windows render, or any path carrying a drive letter, a backslash or an
      MSYS prefix, REFUSES (`assert_render_is_cluster_shaped`);
    - a tilde REFUSES, because the template quotes every path and bash does not
      expand a tilde inside double quotes;
    - the module stack is the FULL stack, because arrow alone leaves pyarrow
      unimportable in a venv without system site packages;
    - the frozen `layer` is IMPORTED from the matched configuration and emitted,
      because `load_backend(layer=None)` produces a run at the wrong layer
      rather than a crash;
    - both snapshot REVISIONS are required and emitted, because a wrong snapshot
      would otherwise load silently;
    - a time limit below the measured precedent REFUSES rather than defaulting
      low, which is how 413287 timed out.

    No token is read, echoed or written; unsetting it is the first thing the
    script does. There is no shell tracing and no environment dump, because both
    print the environment a token lives in. Line endings are LF, and the log
    directory is created HERE -- at render time, on the cluster -- because SLURM
    opens the output file before the body runs."""
    resolved_layer = frozen_layer_for(pairing) if layer is None else int(layer)
    # EVERY IDENTITY ARGUMENT, AGAINST THE FROZEN REGISTRY, ON THE LOGIN NODE.
    identity = assert_identity_arguments_are_registered(
        pairing=pairing,
        layer=resolved_layer,
        model_revision=model_revision,
        sae_revision=sae_revision,
    )
    for name, revision in (("model_revision", model_revision), ("sae_revision", sae_revision)):
        if not str(revision).strip():
            raise JobScriptRenderRefused(
                f"{name} is empty. Jobs 415590 and 416453 both passed real values, and "
                "load_backend accepts None: an unasserted snapshot digest means a WRONG SNAPSHOT "
                "LOADS SILENTLY. Pass the revision the path was pinned to."
            )
    hours = _hours_of(time_limit)
    minimum = float(TAMIA_ENVIRONMENT["minimum_time_limit_hours"])
    if hours < minimum:
        raise JobScriptRenderRefused(
            f"time_limit={time_limit!r} is {hours:.2f} h, below the {minimum:.0f} h floor. "
            f"{TAMIA_ENVIRONMENT['time_limit_evidence']}"
        )
    payload_path = "scripts/final_pairing/control_generation_payload.py"
    # FED FROM PATH_SHAPED_TEMPLATE_KEYS, not from a hand-listed subset: last
    # round the mkdir moved to render time and the unexpanded variable stayed,
    # because the fix addressed one path and the timing rather than every value.
    candidates = {
        "log_dir": log_dir,
        "model_path": model_path,
        "out": out,
        "payload": payload_path,
        "repo_root": repo_root,
        "sae_path": sae_path,
        "venv": venv,
    }
    missing = [key for key in PATH_SHAPED_TEMPLATE_KEYS if key not in candidates]
    if missing:
        raise JobScriptRenderRefused(
            f"path-shaped template key(s) {missing} are never checked before rendering. A "
            "substitution nobody checks is the one that ships broken."
        )
    assert_render_is_cluster_shaped(candidates, platform=platform)
    # AFTER the refusal, never before: a renderer that creates a directory whose
    # name contains a variable hides the defect instead of surfacing it, which is
    # how a literal directory named for the variable ended up on the cluster.
    if create_log_dir:
        # AT RENDER TIME, ON THE CLUSTER. SLURM opens --output before the body
        # runs, so a mkdir in the body cannot save the first submission.
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    return JOB_SCRIPT_TEMPLATE.format(
        pairing=pairing,
        ratified_pairing=identity["pairing_ratified"],
        repo_root=repo_root,
        model_path=model_path,
        sae_path=sae_path,
        layer=int(resolved_layer),
        model_revision=model_revision,
        sae_revision=sae_revision,
        cells=",".join(cells),
        seeds=",".join(str(int(s)) for s in seeds),
        max_new_tokens=int(max_new_tokens),
        selection_rule=selection_rule,
        out=out,
        venv=venv,
        log_dir=log_dir,
        time_limit=time_limit,
        module_stack=" ".join(TAMIA_ENVIRONMENT["required_modules"]),
        cpus_per_task=int(TAMIA_ENVIRONMENT["cpus_per_task"]),
        payload=payload_path,
    )


# ---------------------------------------------------------------------------
# The run, and the CLI.
# ---------------------------------------------------------------------------


def observe_generation_settings(
    *,
    hook_name: str,
    device_objects: Mapping[str, Any],
    model_path: str,
    model_revision: str,
    sae_path: str,
    sae_revision: str,
    layer: int,
    dtype: str,
    max_new_tokens: int,
    selection_rule: str,
    contract: Mapping[str, Any] | None = None,
    render_mode: RenderMode = "verbatim",
) -> dict[str, Any]:
    """THE PRODUCER'S HALF: the covered settings, OBSERVED FROM THE LIVE RUN.

    The contract is explicit that only the producer can bind these, by reading
    them off the live objects rather than off its own configuration -- so
    `hook_name` and the library versions come from the loaded backend and the
    imported modules, not from arguments. The FIELD SET is the contract's; this
    function fills it and refuses if it cannot fill one, because a field this
    payload cannot observe is a field researcher has to be told about rather
    than one to quietly default.

    `hook_name` and `device_objects` are taken as EXPLICIT VALUES rather than
    derived here from a generic `backend: Any` via `getattr` duck-typing --
    that duck-typing is exactly what let a fixture stand in for a real
    `discovery.Backend` and prove nothing (job 419181). The caller resolves
    both from whichever object actually carries them: `discovery.Backend.hook_name`
    for the first, `resolve_generation_backend(backend).device_objects()` for
    the second -- two different objects, because a `discovery.Backend` and a
    `group_intervention` adapter are not the same thing and this function no
    longer pretends they are.

    `render_mode` DEFAULTS TO `"verbatim"`, matching `run_control_arm`'s and
    `run_control_set`'s own default, and MUST be the SAME value passed to
    whichever of those two actually generated: `prompt_render_digest` is
    only honest if it names the render that ran, not a different one
    (job 419773, TASK 2)."""
    import torch as _torch
    import transformers as _transformers

    if render_mode not in RENDER_MODES:
        raise ControlPayloadError(f"render_mode must be one of {RENDER_MODES}; got {render_mode!r}")
    resolved = dict(contract) if contract is not None else resolve_settings_contract()
    render = (
        CHAT_TEMPLATE_RENDER_DESCRIPTION if render_mode == "chat_template" else VERBATIM_RENDER_DESCRIPTION
    )
    stop = "stop_at_eos=False; raw-HF also sets min_new_tokens=max_new_tokens to mean the same"
    observed = {
        "model_reference": f"{model_path}@{model_revision}",
        "tokenizer_reference": f"{model_path}@{model_revision}",
        "sae_reference": f"{sae_path}@{sae_revision}",
        "layer": int(layer),
        "hook_name": str(hook_name),
        "dtype": str(dtype),
        "device_placement": json.dumps(
            {name: str(getattr(obj, "device", "no-parameters")) for name, obj in
             sorted(device_objects.items())},
            sort_keys=True,
        ),
        "max_new_tokens": int(max_new_tokens),
        "do_sample": False,
        "temperature": 1.0,
        "top_p": "not-passed-by-this-payload",
        "top_k": "not-passed-by-this-payload",
        "repetition_penalty": "not-passed-by-this-payload",
        "stop_condition": stop,
        "batch_size": 1,
        "prompt_set_digest": co.sha256_hex(PROMPT_SET_PATH.read_bytes()),
        "prompt_selection_rule": str(selection_rule),
        "prompt_render_digest": co.sha256_hex(render.encode("utf-8")),
        # HOW seeds are derived, never WHICH: the contract EXCLUDES the seed
        # itself, because replicates differ by seed by design.
        "seed_policy": (
            "torch.manual_seed(seed) immediately before each generate call; one seed per "
            "(arm, prompt, replicate); seeds supplied per run and NOT covered by this digest"
        ),
        "transformers_version": str(_transformers.__version__),
        "torch_version": str(_torch.__version__),
        "payload_id": PAYLOAD_ID,
        "payload_version": PAYLOAD_VERSION,
    }
    unobservable = [field for field in resolved.get("fields", ()) if field not in observed]
    if unobservable:
        raise SettingsDigestUnbound(
            f"the contract covers {unobservable}, which this payload does not observe. A field the "
            "producer cannot read off the live run must be raised with researcher rather than "
            "defaulted here: a defaulted setting is one under which the two arms may differ."
        )
    return observed


def resolve_generation_backend(backend: Any) -> Any:
    """`discovery.load_backend`'s return value, wrapped in the SAME adapter
    `group_intervention.run_arm` builds internally -- `.to_tokens`,
    `.to_string`, `.generate`, `.device`, `.device_objects()` -- so this
    payload's control arms and a future intervened arm share ONE adapter
    shape rather than each learning to read `discovery.Backend`'s own fields.

    THE DECISION, AND WHY: `discovery.Backend` (final_pairing_concept_
    discovery.py:2289) is a plain dataclass recording what was loaded -- it
    has `model_obj`/`sae`/`_qwen_decoder_layer`, no methods at all, and
    `run_control_arm`'s unhooked branch needs `.to_tokens`/`.to_string`/
    `.generate`/`.device`/`.device_objects()` together, not `device_objects()`
    alone. Adding all five to `discovery.Backend` would be a THIRD
    implementation of the interface `group_intervention.HookedTransformerBackend`
    and `.RawHfBackend` already are (group_intervention.py:2622, :2702) --
    exactly the drift this file's own `assert_settings_digest_bound` alias
    exists to refuse elsewhere. So the payload goes through the
    `group_intervention` adapters instead, built ONCE, right after
    `load_backend()` returns.

    For Qwen, `discovery.Backend._qwen_decoder_layer` is read only to DECIDE
    which adapter this is (a marker of "this backend is Qwen-shaped"), never
    passed into the adapter as the decoder module itself: `gi.RawHfBackend`
    independently re-derives that module from `(hf_model, layer)` at
    construction, as its own proof that the intervention hook and the
    discovery scorer target the SAME tensor object
    (`assert_hooks_the_scored_tensor`) -- a stored reference is not trusted
    uninspected. The only thing fetched fresh here, rather than re-derived, is
    the tokenizer, via `discovery.resolve_tokenizer_for_backend` -- the ONE
    place that already knows how (Gemma's `HookedTransformer` carries its
    own; Qwen's raw HF model does not, so it reloads from the validated local
    path) -- never a second, payload-local tokenizer lookup."""
    if backend._qwen_decoder_layer is not None:
        discovery = gi._import_discovery_module()
        tokenizer = discovery.resolve_tokenizer_for_backend(backend)
        return gi.RawHfBackend(backend.model_obj, tokenizer, layer=int(backend.layer))
    return gi.resolve_backend(backend.model_obj)


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
    settings_digest: str,
    reader: cti.ClaimTypeExtentReader | None = None,
    prompt_rows: Sequence[Mapping[str, Any]] | None = None,
    prompts_per_cell: int | None = None,
    device: str | None = None,
    hook_name: str | None = None,
    render_mode: RenderMode = "verbatim",
) -> list[dict[str, Any]]:
    """Every control arm over every prompt in every cell, at every seed.

    The ONLY generation entry point, and every arm it can run has already
    passed `assert_control_only`. There is no parameter that makes it dose.

    `render_mode` DEFAULTS TO `"verbatim"`, matching `run_control_arm`'s own
    default: this function's behaviour is unchanged for a caller that does
    not ask for job 419773's fix. `main()` asks for `"chat_template"`."""
    bound_digest = assert_settings_digest_bound(settings_digest)
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
                                settings_digest=bound_digest,
                                device=device,
                                render_mode=render_mode,
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
    # IMPORTED BEFORE THE PARSER IS BUILT: --qwen-sae-family's `choices=` comes
    # from the ratified registry, not a hand-copied tuple, so a third scientific
    # family can never be typo'd into existence here.
    discovery = gi._import_discovery_module()
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
    parser.add_argument(
        "--layer",
        type=int,
        default=None,
        help="the frozen layer; when omitted it is IMPORTED from PRIMARY_CONFIGURATION, never "
        "left as None (load_backend accepts None and then runs at the wrong layer)",
    )
    parser.add_argument(
        "--model-revision",
        default=None,
        help="REQUIRED for a run and for a render: the snapshot digest the model path is "
        "pinned to. Without it a wrong snapshot loads silently.",
    )
    parser.add_argument(
        "--sae-revision",
        default=None,
        help="REQUIRED for a run and for a render: the SAE snapshot digest.",
    )
    parser.add_argument(
        "--qwen-sae-family",
        choices=list(discovery._QWEN_SCIENTIFIC_SAE_FAMILIES),
        default=None,
        help="REQUIRED for a qwen pairing; distinct from --qwen-sparsity and --layer. "
        "load_backend refuses a qwen run without it, and job 419181 hit that refusal only "
        "after a 27B model load -- checked here instead, at argument-parse time.",
    )
    parser.add_argument(
        "--qwen-sparsity",
        type=int,
        default=None,
        help="REQUIRED for a qwen pairing: the SAE's TopK k. Distinct from --qwen-sae-family "
        "and --layer -- three independently recorded fields, none defaulted from another.",
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--cells", default="en/f1,en/f2,en/f3,fr/f1,fr/f2,fr/f3")
    parser.add_argument("--concepts", default=",".join(co.PERSONA_CONCEPT_IDS))
    parser.add_argument(
        "--seeds",
        default="17",
        help="do_sample=False makes every seed's text BYTE-IDENTICAL (measured 480/480 on both "
        "pairings, job 419773) -- more than one is refused, not silently accepted.",
    )
    parser.add_argument(
        "--verbatim-render",
        action="store_true",
        help="use job 419773's PRE-FIX render (row['text'] verbatim, no chat template) instead "
        "of the default chat-template render, so that job stays exactly reproducible. Do not use "
        "this for a new run: instruction-tuned models complete/comment on a bare prompt instead "
        "of speaking in voice without a chat template.",
    )
    parser.add_argument("--prompts-per-cell", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--selection-rule", default="cell_positive_family_rows")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--venv", default=DEFAULT_VENV)
    parser.add_argument(
        "--repo-root",
        default=None,
        help="the extracted repository root, PREPENDED to PYTHONPATH by the rendered script; "
        "required for a render because running the payload by path puts its own directory on "
        "sys.path[0] instead",
    )
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR)
    parser.add_argument("--time-limit", default=DEFAULT_TIME_LIMIT)
    args = parser.parse_args(list(argv) if argv is not None else None)

    cells = _parse_list(args.cells)
    seeds = [int(value) for value in _parse_list(args.seeds)]
    concepts = _parse_list(args.concepts)
    render_mode: RenderMode = "verbatim" if args.verbatim_render else "chat_template"
    # DIE HERE, not after generating half the redundant work: applies to
    # every subcommand, not only a real run, since --plan's own
    # generation_count would otherwise double-count a redundant seed too.
    try:
        assert_no_redundant_greedy_seeds(seeds)
    except RedundantGreedySeeds as exc:
        parser.error(str(exc))

    if args.selfcheck:
        return _selfcheck()

    if args.write_job_script is not None:
        if not args.model_revision or not args.sae_revision:
            parser.error(
                "--write-job-script requires --model-revision and --sae-revision: load_backend "
                "accepts None for both, and an unasserted snapshot digest means a wrong snapshot "
                "loads silently. Jobs 415590 and 416453 both passed real values."
            )
        if not args.repo_root:
            parser.error(
                "--write-job-script requires --repo-root: running the payload by path puts "
                "scripts/final_pairing on sys.path[0], not the repository root, and interplab then "
                "does not import (job 418390/418391, 5 s)."
            )
        text = job_script_text(
            pairing=args.pairing,
            repo_root=args.repo_root,
            model_path=args.model_path or "<LOCAL SNAPSHOT PATH>",
            sae_path=args.sae_path or "<LOCAL SAE PATH>",
            layer=args.layer,
            model_revision=args.model_revision,
            sae_revision=args.sae_revision,
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

    # DIE ON THE LOGIN NODE, NOT ON THE FINAL LINE (jobs 419285/419395, ~3
    # GPU-hours each): --out is checked here, before any generation runs.
    try:
        assert_output_path_is_writable(args.out)
    except OutputPathNotWritable as exc:
        parser.error(str(exc))

    if not args.model_revision or not args.sae_revision:
        parser.error(
            "a run requires --model-revision and --sae-revision. load_backend accepts None for "
            "both and would then load a WRONG SNAPSHOT SILENTLY; 415590 and 416453 both asserted "
            "real values."
        )
    # DIE ON THE LOGIN NODE, NOT AFTER A 27B LOAD (job 419181). load_backend
    # itself refuses a qwen pairing with sae_family/sparsity unset, but that
    # refusal only fires once load_backend actually runs -- after the model
    # is already loading. This is the same check, moved to argument-parse time.
    if str(args.pairing).strip().lower().startswith("qwen") and (
        args.qwen_sae_family is None or args.qwen_sparsity is None
    ):
        parser.error(
            "--qwen-sae-family and --qwen-sparsity are both required for a qwen pairing -- "
            "SAE family, transformer layer and sparsity are three independently recorded "
            "fields and none of them defaults from another. job 419181 hit load_backend's own "
            "refusal for this only after loading a 27B model; refusing here dies in "
            "milliseconds on the login node instead."
        )
    # TRANSLATED AT THE BOUNDARY, from the registry: the payload's own tables are
    # keyed short, load_backend takes the ratified name and refuses anything
    # else. 418403 died at 34 s because the short key went straight through.
    backend = discovery.load_backend(
        pairing=ratified_pairing_name(args.pairing),
        model_path=args.model_path,
        sae_path=args.sae_path,
        # IMPORTED, never None: load_backend accepts None and then runs at a
        # different layer than the frozen one, producing a result rather than a
        # crash. Gemma 29 / Qwen 38 come from PRIMARY_CONFIGURATION.
        layer=args.layer if args.layer is not None else frozen_layer_for(args.pairing),
        expected_model_revision=args.model_revision,
        expected_sae_revision=args.sae_revision,
        device=args.device,
        dtype=args.dtype,
        sae_family=args.qwen_sae_family,
        sparsity=args.qwen_sparsity,
    )
    # ONE ADAPTER, BUILT ONCE: `discovery.Backend` is a plain data holder with
    # no `.to_tokens`/`.generate`/`.device_objects()` of its own (job 419181's
    # AttributeError). resolve_generation_backend() wraps it in the SAME
    # group_intervention adapter run_arm builds internally, and everything
    # below reads FROM THAT, not from a second unwrapping of `backend` done
    # differently in two places.
    generation_backend = resolve_generation_backend(backend)
    features = SURVIVING_FEATURES[args.pairing][concepts[0]]
    # THE CONTRACT IS RESEARCHER'S. This refuses until it exists rather than
    # hashing a coverage set invented here, which would agree with nothing.
    contract = resolve_settings_contract()
    observed_settings = observe_generation_settings(
        hook_name=backend.hook_name,
        device_objects=generation_backend.device_objects(),
        model_path=str(args.model_path),
        model_revision=str(args.model_revision),
        sae_path=str(args.sae_path),
        sae_revision=str(args.sae_revision),
        layer=int(args.layer if args.layer is not None else frozen_layer_for(args.pairing)),
        dtype=str(args.dtype),
        max_new_tokens=int(args.max_new_tokens),
        selection_rule=str(args.selection_rule),
        contract=contract,
        render_mode=render_mode,
    )
    settings_digest = compute_generation_settings_digest(observed_settings, contract)
    records = run_control_set(
        generation_backend,
        backend.sae,
        pairing=args.pairing,
        cells=cells,
        concept_ids=concepts,
        seeds=seeds,
        max_new_tokens=args.max_new_tokens,
        selection_rule=args.selection_rule,
        feature_indices=features,
        settings_digest=settings_digest,
        prompts_per_cell=args.prompts_per_cell,
        device=args.device,
        render_mode=render_mode,
    )
    artifact = build_artifact(
        records,
        settings=observed_settings,
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


def _probe_settings(contract: Mapping[str, Any]) -> dict[str, Any]:
    """A fully-populated settings map for the CONTRACT'S OWN FIELDS.

    Exercises the mechanism without choosing what it covers: the field list is
    read from the contract, and the values are obvious probes."""
    values = {
        "layer": 29,
        "max_new_tokens": 64,
        "do_sample": False,
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": 0,
        "repetition_penalty": 1.0,
        "batch_size": 1,
        "payload_id": PAYLOAD_ID,
        "payload_version": PAYLOAD_VERSION,
    }
    return {field: values.get(field, f"probe-{field}") for field in contract["fields"]}


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

    banner("CONTROL 7 -- the RENDER must refuse what Tamia measured it could not run")
    cluster_paths = {
        "model_path": "/home/user/scratch/snapshots/gemma",
        "sae_path": "/home/user/scratch/snapshots/gemma-sae",
        "out": "/home/user/scratch/final_pairing/control_generations.json",
        "venv": DEFAULT_VENV,
        "log_dir": "/home/user/scratch/final_pairing/logs",
    }
    must_raise(
        "rendering ON WINDOWS at all (LA-B's local render mangled every path)",
        lambda: assert_render_is_cluster_shaped(cluster_paths, platform="win32"),
        JobScriptRenderRefused,
    )
    must_raise(
        "a quoted TILDE venv (bash does not expand it inside double quotes; dies ~2 s into an h100:4)",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "venv": "~/sprint-venv"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "an MSYS-mangled path (the exact shape of the Windows render)",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "out": "C:/Program Files/Git/scratch/out.json"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "a backslash inside a path",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "out": "scratch" + chr(92) + "out.json"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "a log dir carrying $HOME (SLURM expands NOTHING in an SBATCH directive)",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "log_dir": "$HOME/scratch/final_pairing/logs"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "a log dir carrying ${SCRATCH}",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "log_dir": "${SCRATCH}/logs"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "a variable in an --out path",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "out": "$SLURM_TMPDIR/control.json"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    must_raise(
        "a RELATIVE log dir",
        lambda: assert_render_is_cluster_shaped(
            {**cluster_paths, "log_dir": "logs"}, platform="linux"
        ),
        JobScriptRenderRefused,
    )
    print(
        f"  ACCEPTED on a cluster-shaped render: "
        f"{assert_render_is_cluster_shaped(cluster_paths, platform='linux')}"
    )
    print(
        f"  ACCEPTED, and the ONE legal variable: venv={DEFAULT_VENV!r} -- its line is "
        "shell-expanded and the HOME form was MEASURED to resolve; every other path reaches an "
        "SBATCH directive or a mkdir, and neither expands anything."
    )
    probe = Path(tempfile.mkdtemp()) / "$HOME" / "logs"
    must_raise(
        "RENDERING with a variable-bearing log dir (this is what created a literal $HOME dir)",
        lambda: job_script_text(
            pairing="gemma",
            model_path=cluster_paths["model_path"],
            sae_path=cluster_paths["sae_path"],
            cells=["en/f1"],
            seeds=[17],
            max_new_tokens=64,
            selection_rule="cell_positive_family_rows",
            out=cluster_paths["out"],
            model_revision="a" * 40,
            sae_revision="b" * 40,
            repo_root="/home/user/scratch/final_pairing/repo",
            log_dir="$HOME/scratch/logs",
            platform="linux",
            create_log_dir=True,
        ),
        JobScriptRenderRefused,
    )
    print(
        f"  AND NOTHING WAS CREATED: the refusal runs BEFORE the mkdir, so no directory named for "
        f"a variable exists after it (probe parent has {len(list(probe.parent.parent.iterdir()))} "
        "entries)."
    )
    print(
        f"  DEFAULT_LOG_DIR is now absolute and variable-free: {DEFAULT_LOG_DIR!r} "
        f"(contains '$': {'$' in DEFAULT_LOG_DIR}, contains '~': {'~' in DEFAULT_LOG_DIR})"
    )

    def render(**overrides):
        kwargs = dict(
            pairing="gemma",
            model_path=cluster_paths["model_path"],
            sae_path=cluster_paths["sae_path"],
            cells=["en/f1"],
            seeds=[17],
            max_new_tokens=64,
            selection_rule="cell_positive_family_rows",
            out=cluster_paths["out"],
            model_revision="a" * 40,
            sae_revision="b" * 40,
            log_dir=cluster_paths["log_dir"],
            repo_root="/home/user/scratch/final_pairing/repo",
            platform="linux",
            create_log_dir=False,
        )
        kwargs.update(overrides)
        return job_script_text(**kwargs)

    must_raise(
        "a time limit of 01:00:00 (below the Qwen extrapolation; 413287 timed out that way)",
        lambda: render(time_limit="01:00:00"),
        JobScriptRenderRefused,
    )
    must_raise(
        "an empty model revision (load_backend accepts None and loads a wrong snapshot silently)",
        lambda: render(model_revision=""),
        JobScriptRenderRefused,
    )
    must_raise(
        "an empty SAE revision",
        lambda: render(sae_revision=""),
        JobScriptRenderRefused,
    )
    must_raise(
        "a pairing the frozen configuration does not name (would render layer=None)",
        lambda: render(pairing="llama"),
        JobScriptRenderRefused,
    )
    must_raise(
        "a --layer that is not the frozen layer for that pairing",
        lambda: render(layer=12),
        JobScriptRenderRefused,
    )
    must_raise(
        "a revision that is not a hexadecimal digest",
        lambda: render(model_revision="main"),
        JobScriptRenderRefused,
    )
    must_raise(
        "a repo root carrying a variable (PYTHONPATH would be prepended with a literal)",
        lambda: render(repo_root="$SLURM_TMPDIR/repo"),
        JobScriptRenderRefused,
    )
    identity = assert_identity_arguments_are_registered(
        pairing="gemma", layer=frozen_layer_for("gemma"), model_revision="a" * 40,
        sae_revision="b" * 40,
    )
    print(
        f"  IDENTITY VALIDATED AT RENDER TIME against {identity['registry']}: "
        f"{identity['pairing_short']!r} -> {identity['pairing_ratified']!r} at layer "
        f"{identity['layer']}. 418403 spent 34 s of an allocation to learn this; it is a dict "
        "lookup here."
    )

    banner("CONTROL 8 -- generation_settings_digest: RULING_16's containment, and it REFUSES")
    contract = resolve_settings_contract()
    print(
        f"  CONTRACT RESOLVED from {contract['source']}: {len(contract['fields'])} covered field(s), "
        f"hashed by THEIR function; deliberate omissions {sorted(contract['omissions'])}"
    )
    must_raise(
        "a module that defines no settings FORM (this payload invents no coverage set)",
        lambda: resolve_settings_contract(object()),
        SettingsContractUnavailable,
    )
    must_raise(
        "smuggling in a DELIBERATELY OMITTED setting (seed differs by design across replicates)",
        lambda: compute_generation_settings_digest(
            {**_probe_settings(contract), "seed": 17}, contract
        ),
        SettingsDigestUnbound,
    )
    for label, value in (
        ("empty", ""),
        ("None", None),
        ("not hex", "z" * 64),
        ("too short", "ab" * 8),
        ("the calibration lane's own synthetic placeholder", "f" * 64),
        ("all zeroes", "0" * 64),
    ):
        must_raise(
            f"a {label} digest",
            lambda value=value: assert_settings_digest_bound(value),
            SettingsDigestUnbound,
        )
    probe_settings = _probe_settings(contract)
    dropped = dict(probe_settings)
    dropped.pop(contract["fields"][0])
    must_raise(
        f"a covered setting that is MISSING ({contract['fields'][0]})",
        lambda: compute_generation_settings_digest(dropped, contract),
        SettingsDigestUnbound,
    )
    must_raise(
        "a covered setting that is present but UNSET",
        lambda: compute_generation_settings_digest(
            {**probe_settings, contract["fields"][0]: ""}, contract
        ),
        SettingsDigestUnbound,
    )
    must_raise(
        "a contract that covers no field at all",
        lambda: compute_generation_settings_digest(probe_settings, {"fields": (), "digest": None}),
        SettingsContractUnavailable,
    )
    first = compute_generation_settings_digest(probe_settings, contract)
    again = compute_generation_settings_digest(dict(probe_settings), contract)
    moved = compute_generation_settings_digest({**probe_settings, "layer": 38}, contract)
    print(f"  EMISSION FIRES on real settings: {first}")
    print(f"  stable across calls: {first == again}; changes when a covered setting moves: {first != moved}")
    if first != again or first == moved:
        failures.append("the settings digest is not a function of the covered settings")
    if assert_settings_digest_bound(first) != first:
        failures.append("a real digest did not survive its own bound check")

    banner("SUCCESS 3 -- the rendered script matches the RECORDED CLUSTER DESCRIPTION")
    script = render()
    stack = " ".join(TAMIA_ENVIRONMENT["required_modules"])
    layers = TAMIA_ENVIRONMENT["frozen_layers"]
    checks = {
        "module stack is the FULL stack": f"module load {stack}" in script,
        "venv uses the $HOME form": 'source "$HOME/sprint-venv/bin/activate"' in script,
        "no quoted tilde anywhere": '"~' not in script,
        "log dir is created in the body too": 'mkdir -p "' in script,
        "the frozen layer is EMITTED": f"--layer {layers['gemma']}" in script,
        "the RATIFIED pairing name is emitted": '--pairing "gemma-3-12b-it"' in script,
        "no short pairing key reaches load_backend": '--pairing "gemma"' not in script,
        "PYTHONPATH is PREPENDED, not assigned": 'PYTHONPATH="/home/user/scratch/final_pairing/repo${PYTHONPATH:+:$PYTHONPATH}"'
        in script,
        "whole-node CPUs are requested": "#SBATCH --cpus-per-task=32" in script,
        "both revisions are emitted": "--model-revision" in script and "--sae-revision" in script,
        "time limit is at least the floor": "--time=06:00:00" in script,
        "unset HF_TOKEN": "unset HF_TOKEN" in script,
        "HF_HUB_OFFLINE=1": "HF_HUB_OFFLINE=1" in script,
        "no shell tracing": "set -x" not in script,
        "no env dump": "\nenv\n" not in script,
        "no repo_id": "huggingface.co" not in script and "--repo-id" not in script,
        "LF only": "\r\n" not in script,
    }
    for name, ok in checks.items():
        print(f"  {name:38s} {ok}")
        if not ok:
            failures.append(f"rendered script check failed: {name}")
    print(f"  frozen layers IMPORTED from the matched configuration: {layers}")
    print(f"  qwen render emits --layer {frozen_layer_for('qwen')}")
    if f"--layer {layers['qwen']}" not in render(pairing="qwen"):
        failures.append("the qwen render did not emit the frozen qwen layer")

    banner("SUCCESS 4 -- wall time comes from a MEASURED precedent, not from a disclaimer")
    precedent = TAMIA_ENVIRONMENT["measured_generation_precedent"]
    plan = payload_requirements(
        pairing="qwen",
        cells=["en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3"],
        prompts_per_cell=20,
        seeds=[17, 23],
        max_new_tokens=64,
    )
    applied = plan["wall_time_from_the_measured_precedent"]["applied_to_this_grid"]
    print(
        f"  job {precedent['job']}: {precedent['generations']} generations, {precedent['tokens']} "
        f"tokens in {precedent['seconds']} s = {precedent['tokens_per_second']} tok/s"
    )
    print(f"  applied to this grid: {applied['qwen_minutes']} min for qwen at 64 new tokens")
    print(f"  gemma: {precedent['gemma_has_no_precedent'][:96]}...")
    if "no generation has ever run" in json.dumps(plan):
        failures.append("the plan still carries the false no-generation-has-ever-run claim")

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
