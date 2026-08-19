"""Feature-GROUP intervention machinery for the two final pairings.

WHAT THIS IS. The joint (multi-feature) intervention primitive plus the
harness that measures its effect. Everything else in
`scripts/final_pairing/` *finds* features one at a time; nothing in this
repository, before this file, intervenes on several features TOGETHER in
one forward pass. `protocols/final_pairing/v1/joint_intervention_lane.json`
RULING_4 stage 2 names exactly that operation ("intervene on ALL k members
SIMULTANEOUSLY in one forward pass") and stage 3 names the leave-one-out
minimality sweep built on it. This file is that primitive.

WHAT THIS IS NOT, explicitly:

- It is NOT an authorization. `joint_intervention_lane.json` and
  `group_necessity_and_ablation_claims.json` are both marked
  "AUTHORIZES NOTHING"; this file is ENGINEERING PREVIEW ONLY and submits
  nothing, allocates nothing and spends nothing.
- It invents NO threshold. G-A/G-B/G-C and the G-D dose threshold are
  frozen elsewhere; this file computes measurements and never compares
  them to a number it made up.
- It emits no verdict of the form "these features are the ones needed".
  `RULING_A11a`/`RULING_A11b` bind that wording; see
  `NULL_ABLATION_FROZEN_PHRASING` below, which is reproduced verbatim so a
  caller reporting a null cannot have to reinvent it.

------------------------------------------------------------------------
THE TWO ABLATION MECHANISMS ARE NOT THE SAME OPERATION
------------------------------------------------------------------------

`AblationMechanism` is a REQUIRED, explicitly selected field. There is no
default, because the two mechanisms differ by an error term that is
neither small nor group-dependent, and a silent default would decide a
scientific question by import order.

    (a) "reconstruct" -- encode, scale the group's feature activations
        down, decode, and write THE RECONSTRUCTION back:
            h_new = decode(scale(encode(h)))
        The SAE's reconstruction error is DISCARDED and replaced.

    (b) "subtract" -- subtract the group's decoder contribution from the
        residual stream directly, never reconstructing:
            h_new = h - alpha * sum_f w_f * a_f(h) * W_dec[f]
        The SAE's reconstruction error is PRESERVED untouched.

Because `decode` is affine (`decode(z) = z @ W_dec + b_dec`), the gap
between them is a closed form that this file both derives and MEASURES:

    delta_a - delta_b  ==  decode(encode(h)) - h  ==  -reconstruction_error

independent of the group, of `alpha`, and of the per-feature weights.

RULED, 2026-08-17, RULING_13 Q3: (b) SUBTRACT IS THE INSTRUMENT. The
decisive ground is the no-op test and it is this module's own defect class:
under subtract a non-firing group leaves the residual EXACTLY unchanged, so
NOT-EXERCISED stays detectable; under reconstruct a non-firing group STILL
moves the model by the whole reconstruction error, so the intervention
APPEARS TO HAVE FIRED WHEN IT DID NOT. The reasoning is magnitude-
independent -- both mechanisms are exact against a DIFFERENT REFERENCE, and
the model computes with `h`, not with `decode(encode(h))` -- so it does not
rest on how large the error happens to be at production scale.

Consequences implemented here:

- (a) is NOT a parallel arm and NOT a robustness arm. A robustness arm
  varies with what it checks; this one is a CONSTANT OF THE SAE at its
  hook point. It runs ONCE per (model, SAE, hook point) via
  `measure_sae_fidelity_context()` and is reported alongside results,
  never as evidence about a group.
- An (a) result read against an UNHOOKED control is REFUSED, not
  caveated (`assert_control_is_admissible`). Its only admissible control
  is `GroupSpec.reconstruction_control()`, at the same seed.
- The null-identity asymmetry stands as the FINDING that discriminated
  the two, not as a failed requirement: `null_configuration_is_exact_
  identity()` reports False for (a) and a test pins it.

RECONCILED WITH WHAT ALREADY EXISTED. `interplab.interventions.hooks.
_make_clamp_hook` computes `decode(clamped) - decode(clean)`; for an affine
decoder both the bias AND the reconstruction error cancel in that
difference, so at clamp zero it IS decoder subtraction. This module's
subtract is therefore the SET generalisation of that primitive, not a
second implementation -- measured equal to it at k=1 on live features to
float32 tolerance in
`test_my_subtract_is_the_existing_clamp_hook_generalised_not_a_second_implementation`.

------------------------------------------------------------------------
THE DEFECT CLASS THIS FILE IS BUILT AGAINST
------------------------------------------------------------------------

A hook that never fires while the run reports success. A steering result
taken from a hook that silently did nothing is indistinguishable from a
concept that is not steerable -- a clean negative that reads as a real
absence. This sprint's every genuine bug has had that shape.

So firing is OBSERVED AND ASSERTED, never assumed:

- `FiringLedger` records every invocation: call index, prefill-vs-decode
  classification, tensor shape, the absolute positions the call covered,
  how many position slots were actually MODIFIED, and the delta norm.
- `assert_fired_as_expected()` RAISES on any disagreement. It has no
  warn-and-continue path; there is no verbosity setting that downgrades it.
- The expected counts are derived from the RETURNED TOKEN TENSOR (an
  observable independent of the hook), not from the ledger, so the
  assertion cannot be satisfied by the thing it is checking.
- `assert_exact_delta()` checks `h_after - h_before` against the closed
  form `alpha * sum_f w_f * W_dec[f]`, at a tolerance derived from the
  representable spacing at the residual's own magnitude rather than from a
  hand-chosen epsilon.
- BELOW FLOAT32 THAT IS NOT ENOUGH, and the module says so rather than
  reporting a green assertion. At bfloat16 a delta smaller than the
  spacing at `|h|` is absorbed whole -- `h + d == h` exactly -- so the
  intervention does nothing at that element while the tolerance, which the
  dtype forces to be large, still passes. `FiringRecord` therefore carries
  an absorption census on every call, `assert_no_absorption()` is the
  strong opt-in check, and `minimum_effective_alpha()` sizes a dose that
  can survive the dtype at all. See `DTYPE_LIMITS` for the measured table.

------------------------------------------------------------------------
A CLAMP DOSE THAT EVALUATES TO ZERO IS REFUSED, NEVER RUN
------------------------------------------------------------------------

The clamp dose is `target_f = alpha * corpus_max_f`. On a MAXIMALLY
SELECTIVE feature -- one that fires on the concept and nowhere in the
background, so `corpus_max == 0` -- that product is EXACTLY ZERO, and the
amplify arm would fire, be scored, and have done nothing. 89.52% of
full-space cells have `corpus_max == 0` (architect, mailbox sequence 43,
FULL-SPACE; the 46.86% shortlist figure does not govern), so this is the
common case, not an edge case.

`corpus_max == 0` IS NOT A DEAD FEATURE -- see
`MAXIMAL_SELECTIVITY_IS_NOT_A_DEAD_FEATURE`, quoting the discovery
runner's own words at `final_pairing_concept_discovery.py` lines 1838-1841.
So the fault is in the SCALE, not in the feature, and the response is
neither to exclude the member nor to substitute a default:

- `GroupSpec.__post_init__` RAISES `ZeroClampDose` at construction, so no
  spec naming a zero-dose member can exist to be run.
- `resolve_group` RAISES again on the FLOAT32-evaluated targets, which
  catches a product that is non-zero in float64 and underflows to zero in
  the dtype the target is actually evaluated in.
- A MIXED group refuses too. Dosing only the non-zero members would make a
  5-member group act as a 3-member one -- the same arity corruption this
  module already refuses for an out-of-range index or a duplicate.
- NO REPLACEMENT SCALE IS NAMED HERE. What the reference should be for such
  a feature is a calibration question owned by a lane that does not select
  the group; this module invents nothing.

Ablation-by-subtraction is UNAFFECTED and is measured to be: it removes
`a_f(h) * W_dec[f]`, the feature's actual contribution, and needs no corpus
reference at all.

THE SAME REFUSAL COVERS A ZERO WEIGHT (`ZeroWeightMember`), at the same two
gates. Every per-kind delta here carries `w_f` as a factor, so a weight-0
member contributes exactly nothing at every alpha and in every dose form:
MEASURED before the refusal existed, a k=2 ablate group with one weight-0
member left a residual BIT-IDENTICAL to the k=1 arm while `member_count` still
reported 2. There is no legitimate way to want that -- see
`NO_LEGITIMATE_ZERO_WEIGHT_MEMBER`, which answers the leave-one-out and
placeholder cases explicitly. Negative weights stay legal; a sign flip is a
direction, not inertness.

------------------------------------------------------------------------
BOTH FINAL PAIRINGS ARE HOOKABLE
------------------------------------------------------------------------

`HookedTransformerBackend` drives the Gemma pairing through
`model.hooks(...)`. `RawHfBackend` drives Qwen3.5-27B, which
transformer_lens cannot load, through `register_forward_hook` on the
decoder layer -- reusing `final_pairing_harness`'s own resolvers so the
intervention hooks THE SAME MODULE OBJECT the discovery scorer hooks.
`assert_hooks_the_scored_tensor()` checks that by object identity at
runtime; if the two ever diverged, a feature index would name one
direction while scoring and another while steering, and neither half would
look wrong. `build_group_hook` is shared by both backends, so the
arithmetic, the ledger, the refusals and the absorption census cannot
drift apart between the two pairings.

------------------------------------------------------------------------
DEVICE PLACEMENT
------------------------------------------------------------------------

`HookedTransformer.from_pretrained(hf_model=..., device=...)` moves only
the HookedTransformer; the raw `AutoModel` it copied weights from stays
where it was. Job 415590 (2026-08-15) died one minute into a six-hour
allocation on exactly that. `assert_devices_before_forward()` wraps the
existing `final_pairing_concept_discovery.assert_load_devices_agree`
(imported, never copied, and that file is NOT edited by this lane) and is
called before this harness's first forward. If that helper cannot be
imported this file RAISES -- a device gate that silently declines to run
is the same false-negative shape as a hook that silently declines to fire.

That import is loaded by FILE IDENTITY, not by name. A same-named 23-line
compatibility stub really does exist at
`scripts/legacy/final_pairing_concept_discovery.py`, and putting
`scripts/legacy` on `sys.path` for the raw-HF resolvers made the plain
`import` resolve to it -- the device gate present by name and empty of the
function it was imported for. This module's own test suite caught that;
`_import_module_from_exact_file` is the fix and
`test_a_legacy_stub_of_the_same_name_cannot_shadow_the_device_gate` is the
regression. `RawHfBackend` additionally asserts the DECODER LAYER's
placement separately from the model's, because a `device_map` shard can
put them in different places and the layer is the one the hook runs on.

------------------------------------------------------------------------
WHAT IS EXERCISED WHERE
------------------------------------------------------------------------

No Gemma-3-12B-it / Qwen3.5-27B weights and no GPU exist on the machine
this file was written on. Every arithmetic and firing-count claim above is
provable without them, and is proven in `tests/test_group_intervention.py`
against (i) a synthetic SAE with a random untied decoder and (ii) the
repository's real CPU fixtures -- a real `sae_lens` TopK SAE
(`tests/fixtures/tiny_sae`, d_in=64, d_sae=256) hooked into a real
`transformer_lens.HookedTransformer` (`tests/fixtures/tiny_model`)
through the real `model.hooks(...)` path and real `model.generate(...)`.
What remains unexercised is enumerated in `UNEXERCISED_WITHOUT_GPU`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import torch

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]


# ---------------------------------------------------------------------------
# Frozen wording, reproduced verbatim so no caller has to reinvent it.
# ---------------------------------------------------------------------------

NULL_ABLATION_FROZEN_PHRASING = (
    "Ablating this set did not remove the concept. We cannot distinguish an "
    "unnecessary set from an incomplete one."
)
"""`group_necessity_and_ablation_claims.json` RULING_A11b, verbatim. A null
group-ablation result may be reported in these words and in no others; the
protocol's `PROHIBITED_READINGS` list bans every phrasing that asserts
absence from an instrument which cannot detect presence."""

UNEXERCISED_WITHOUT_GPU = (
    "Real Gemma-3-12B-it / Qwen3.5-27B weights: no forward has ever run through this file "
    "on either final-pairing model. Both hook paths are exercised end to end on this "
    "repository's pinned tiny fixtures instead.",
    "Qwen3_5DecoderLayer AT SCALE: the class itself is no longer unexercised -- the raw-HF path "
    "now runs end to end (resolve, hook, generate, exact delta, ablation, both layer_types) "
    "against a REAL transformers.models.qwen3_5.Qwen3_5DecoderLayer instantiated at fixture "
    "size with random weights from the installed transformers, whose output is MEASURED to be a "
    "plain tensor. What remains unexercised is the 27B weights, the GPU, bfloat16, and Tamia's "
    "transformers==5.14.1 specifically (this machine has 5.12.1). A tuple-returning layer is "
    "DETECTED PRE-GENERATION by probe_raw_hf_layer_output_contract() and refused, not handled: "
    "see QWEN3_5_LAYER_OUTPUT_CONTRACT for why unwrapping it here alone would be worse.",
    "Multi-GPU / device_map sharding: assert_devices_before_forward() is exercised only in "
    "the all-CPU case, where it trivially agrees, and the separate model-vs-decoder_layer "
    "placement assertion on the raw-HF backend has never seen an actually-split model.",
    "Real 27B-scale KV-cache decode: the prefill-then-one-call-per-token firing pattern is "
    "measured on both backends at fixture scale, not at production sequence lengths.",
    "Generation batching: run_arm() deliberately generates one prompt per call (see its "
    "docstring); a padded batch path does not exist and is not tested.",
    "bfloat16/float16 ON A REAL MODEL: the dtype rounding and absorption terms are measured "
    "(see DTYPE_LIMITS) on synthetic tensors at both dtypes, but no model forward has run "
    "at bfloat16 through this file, so the absorbed_fraction a real 27B residual stream "
    "produces at a given alpha is predicted by the same arithmetic and NOT observed.",
    "The clamp dose form at a REAL corpus_max: per-member targets are exercised with "
    "hand-supplied scales, because no corpus census for either final pairing exists on this "
    "machine. The arithmetic is proven; the doses are not real doses. A REAL corpus_max of 0 is "
    "now a REFUSAL (ZeroClampDose) rather than a dose, so what is unexercised is not the zero "
    "case -- it is any non-degenerate real census value.",
    "What dose scale a maximally selective feature should be given: NOT DECIDED HERE and not "
    "decidable here. This module refuses the zero dose and names no replacement; the reference "
    "is a calibration measurement owned by a lane that does not select the group.",
    "Whether an intervention that is APPLIED produces any particular EFFECT: this module "
    "measures and classifies, and owns no success criterion. RULING_13 places that in a "
    "control-only calibration performed by a lane that does not select the group, so no "
    "margin, threshold or ceiling appears here and a test asserts none appears later.",
)


# ---------------------------------------------------------------------------
# Errors. Every one of these is a REFUSAL; none has a warn-and-continue path.
# ---------------------------------------------------------------------------


class GroupInterventionError(RuntimeError):
    """Base for every refusal raised by this module."""


class InvalidGroupSpec(GroupInterventionError):
    """The requested intervention is not well formed."""


class FeatureNotInSAE(InvalidGroupSpec):
    """A named feature index does not exist in the SAE.

    RAISED, never dropped. A group that silently shed an out-of-range
    member would turn a five-feature result into a secret three-feature
    one while every count downstream still read five."""


class ZeroClampDose(InvalidGroupSpec):
    """The clamp dose `alpha * corpus_max` evaluates to EXACTLY ZERO.

    RAISED, never warned. An amplify arm whose dose is zero fires, is
    scored, and did nothing -- a result indistinguishable from 'this concept
    is not steerable'. `corpus_max == 0` means MAXIMAL SELECTIVITY, not a
    dead feature, so the fault is in the SCALE and this module neither
    excludes the member nor substitutes a default."""


class ZeroWeightMember(InvalidGroupSpec):
    """A named member's weight is EXACTLY ZERO, so it is not a member.

    THE SAME DEFECT AS A ZERO DOSE, WITH DIFFERENT ARITHMETIC, and MEASURED
    before this refusal existed: a k=2 ablate group with one weight-0 member
    produced a residual BIT-IDENTICAL to the k=1 arm while `member_count`
    still reported 2. That is arity corruption -- indistinguishable from a
    real k=2 result, and it would misattribute a k=1 effect to a 2-member
    group. This module already refuses an out-of-range index and a duplicate
    on exactly that reasoning."""


class RawHfLayerContractMismatch(GroupInterventionError):
    """The raw-HF decoder layer does not return the plain resid-post tensor
    this pairing's whole raw-HF path -- scoring included -- is built on."""


class UnsupportedSAE(GroupInterventionError):
    """The SAE object does not expose the decoder this module needs."""


class HookFiringMismatch(GroupInterventionError):
    """The hook did not fire the way the caller said it would.

    THE POINT OF THIS MODULE. A run whose expected and actual firing
    counts disagree is a run whose numbers mean nothing, so it fails
    loudly here instead of returning a plausible null."""


class ExactDeltaMismatch(GroupInterventionError):
    """`h_after - h_before` is not the delta that was requested."""


class DeviceGateUnavailable(GroupInterventionError):
    """The shared device gate could not be imported, so it cannot run."""


class SettingsDigestUnbound(GroupInterventionError):
    """`generation_settings_digest` is absent, malformed, or a known placeholder.

    RULING_16's containment: this lane holds both the control arm
    (`control_generation_payload.py`) and the intervened arm (`run_arm`,
    below), and the digest is what proves the two ran under identical
    settings rather than trusting that they did. It is refused HERE, inside
    `run_arm` itself, so neither caller can construct a record that skips it
    -- the same defect class as a zero dose or a zero weight: a record that
    looks bound and is not is worse than one that admits it is not."""


# ---------------------------------------------------------------------------
# SAE accessors. Tolerant of shape, intolerant of ambiguity.
# ---------------------------------------------------------------------------


def resolve_decoder_matrix(sae: Any) -> torch.Tensor:
    """The `[d_sae, d_in]` decoder matrix, row f being feature f's direction.

    Handles the two shapes this project loads: `sae_lens.SAE` and
    `final_pairing_harness.QwenScopeSAE` both expose `W_dec` directly;
    an `nn.Linear`-style decoder exposes `decoder.weight` as `[d_in, d_sae]`
    and is transposed here. Anything else RAISES rather than guessing --
    a wrong transpose would silently steer along d_in arbitrary directions
    and still produce a confident-looking number."""
    w_dec = getattr(sae, "W_dec", None)
    if isinstance(w_dec, torch.Tensor):
        if w_dec.ndim != 2:
            raise UnsupportedSAE(f"sae.W_dec must be 2-D [d_sae, d_in]; got shape {tuple(w_dec.shape)}")
        return w_dec
    decoder = getattr(sae, "decoder", None)
    weight = getattr(decoder, "weight", None)
    if isinstance(weight, torch.Tensor) and weight.ndim == 2:
        return weight.t()
    raise UnsupportedSAE(
        f"{type(sae).__name__} exposes neither a 2-D `W_dec` nor a `decoder.weight` -- refusing to "
        "guess where this SAE keeps its decoder directions."
    )


def resolve_decoder_bias(sae: Any, d_in: int, *, device, dtype) -> torch.Tensor:
    """`b_dec`, or an exact zero vector when the SAE has none.

    Only mechanism (a) reads it, and only through `sae.decode`; it is
    resolved here for the closed-form cross-check in
    `measure_mechanism_gap`, which must not depend on `decode` in order to
    be an independent check of it."""
    b_dec = getattr(sae, "b_dec", None)
    if isinstance(b_dec, torch.Tensor):
        return b_dec.to(device=device, dtype=dtype)
    return torch.zeros(d_in, device=device, dtype=dtype)


def resolve_sae_dims(sae: Any) -> tuple[int, int]:
    """`(d_sae, d_in)` taken from the decoder matrix and CROSS-CHECKED
    against `cfg` where a `cfg` exists.

    The decoder's own shape is authoritative because it is what the hook
    actually indexes into. A `cfg` that disagrees is a refusal, not a
    tie-break: one of the two is wrong, and picking either silently is how
    an out-of-range index becomes an out-of-bounds read on someone else's
    features."""
    w_dec = resolve_decoder_matrix(sae)
    d_sae, d_in = int(w_dec.shape[0]), int(w_dec.shape[1])
    cfg = getattr(sae, "cfg", None)
    for name, measured in (("d_sae", d_sae), ("d_in", d_in)):
        declared = getattr(cfg, name, None) if cfg is not None else None
        if declared is None:
            declared = getattr(sae, name, None)
        if declared is not None and int(declared) != measured:
            raise UnsupportedSAE(
                f"SAE declares {name}={int(declared)} but its decoder matrix has {name}={measured} "
                "-- refusing to run with two disagreeing opinions about the feature space."
            )
    return d_sae, d_in


def resolve_hook_name(sae: Any) -> str:
    """The SAE's own hook point (`blocks.N.hook_resid_post` for every SAE
    in this project). Raised rather than defaulted: hooking the wrong point
    is the single cheapest way to produce a run where nothing happens and
    everything reports fine."""
    cfg = getattr(sae, "cfg", None)
    metadata = getattr(cfg, "metadata", None)
    name = getattr(metadata, "hook_name", None) or getattr(cfg, "hook_name", None)
    if isinstance(name, str) and name:
        return name
    name = getattr(sae, "hook_name", None)
    if isinstance(name, str) and name:
        return name
    raise UnsupportedSAE(
        f"{type(sae).__name__} does not declare a hook_name -- pass GroupSpec(hook_name=...) "
        "explicitly rather than letting this module guess where to intervene."
    )


# ---------------------------------------------------------------------------
# The spec.
# ---------------------------------------------------------------------------

InterventionKind = Literal["noop", "amplify", "ablate"]
AblationMechanism = Literal["reconstruct", "subtract"]
Positions = Literal["all", "generated_only"]
DoseForm = Literal["additive", "clamp"]

ABLATION_MECHANISMS: tuple[AblationMechanism, ...] = ("reconstruct", "subtract")
DOSE_FORMS: tuple[DoseForm, ...] = ("additive", "clamp")

RULED_INSTRUMENT_MECHANISM: AblationMechanism = "subtract"
"""RULING_13 Q3.2: SUBTRACT is the instrument. Three grounds, the decisive
one being the no-op test -- under subtract a non-firing group leaves the
residual EXACTLY unchanged, so NOT-EXERCISED stays detectable; under
reconstruct a non-firing group still moves the model by the whole
reconstruction error, so the intervention APPEARS TO HAVE FIRED WHEN IT DID
NOT. Mechanism (a) is demoted to a once-per-configuration fidelity context
statistic (`measure_sae_fidelity_context`), never a parallel arm."""

RECONSTRUCT_OVERREAD_GUARD = """PROHIBITED READINGS OF THE MECHANISM GAP (RULING_13 Q3.9).

The measured ratio |reconstruction_error| / |delta_b| is a SIGNAL-TO-ARTIFACT
RATIO FOR MECHANISM (a): the reconstruction error against ONE GROUP'S
intervention magnitude. It is decisive for that and for nothing wider.

It is NOT the SAE's fidelity relative to the residual stream. Citing it as
"the SAE misses more than twice what it captures", or any paraphrase making
it a statement about SAE quality in general, is prohibited. The residual-
relative quantity is a DIFFERENT number, `reconstruction_error_norm /
residual_norm`, which `measure_sae_fidelity_context()` reports separately
and labels as its own thing."""


MAXIMAL_SELECTIVITY_IS_NOT_A_DEAD_FEATURE = """corpus_max == 0 DOES NOT MEAN A DEAD FEATURE.

With a live positive set it means MAXIMAL SELECTIVITY -- the feature fires on
the concept and NOWHERE in the background -- and it scores 1.0 in the shadow
statistic ON PURPOSE. The discovery runner says so in its own words
(scripts/final_pairing/final_pairing_concept_discovery.py, docstring of
compute_shadow_fire_rate_corpus_max): "a degenerate reference is NOT the same
thing as a dead cell: `corpus_max == 0` with a live positive set is maximal
selectivity (the feature fires on the concept and nowhere in the background),
and it scores 1.0 here on purpose."

89.52% of FULL-SPACE cells have corpus_max == 0 (architect, mailbox sequence
43). This is the common case, not an edge case, and these are the MOST
SELECTIVE candidates in the dictionary. Excluding them from groups is
explicitly refused; what is wrong is the DOSE SCALE, which references
background activation ("how much this feature normally fires in the corpus")
where the property to be dosed is "how far this feature must be pushed to
change the output"."""

ZERO_DOSE_SCALE_IS_NOT_THIS_MODULE_S_TO_NAME = """NO REPLACEMENT DOSE SCALE IS NAMED HERE.

What the reference should be for a maximally selective feature is a
CALIBRATION question. It is a control-only measurement and it belongs to the
lane that does NOT select the group (architect, mailbox sequence 43: "NOT
RULED: what the replacement reference should be for such features ... I will
not invent a scale"). So this module will not substitute a default, will not
fall back to another member's scale, will not silently skip the member, and
will not drop it from the group. It refuses, and the refusal is the finding."""


NO_LEGITIMATE_ZERO_WEIGHT_MEMBER = """WHY A ZERO-WEIGHT MEMBER IS REFUSED OUTRIGHT AND NOT MADE EXPRESSIBLE.

Asked and answered rather than defaulted, 2026-08-17. The two candidate
legitimate uses are a LEAVE-ONE-OUT arm built by zeroing a member instead of
removing it, and an explicit PLACEHOLDER member. Both are refused, and not on
a technicality:

- The leave-one-out arm ALREADY EXISTS as `GroupSpec.without()` /
  `leave_one_out_specs()`, which REMOVE the member, so `member_count` and
  `feature_indices` tell the truth about the arm that ran. Zeroing would be a
  SECOND way to express the same arm whose only difference is that every
  cardinality downstream is wrong. `joint_intervention_lane.json` RULING_4
  stage 3 is a minimality sweep over ARITY; an arm that lies about its arity
  cannot participate in it.
- A placeholder member is a claim about a group that is not the group. The
  declared, asserted way to say "this arm does nothing" is
  `GroupSpec.noop()`, which registers NO hook, or a whole-spec `alpha == 0`,
  which `null_configuration_is_exact_identity()` reports and `run_arm()`
  asserts as zero positions modified. Both are visible in the record. A
  weight of 0 buried in one member is visible nowhere.

NEGATIVE WEIGHTS REMAIN LEGAL. A sign flip is a direction, not inertness: the
member still moves the residual stream and still earns its place in the count.
Only EXACTLY ZERO is refused."""


def _refuse_zero_weight_members(
    members: Sequence[GroupMember], *, stage: str, evaluated: Sequence[float] | None = None
) -> None:
    """RAISE `ZeroWeightMember` if any member's weight is exactly zero.

    Two gates, mirroring the zero-dose ones: `GroupSpec.__post_init__` (so no
    such spec can exist) and `resolve_group` on the FLOAT32 weights the hook
    actually multiplies by (so a weight that underflows to zero in that dtype
    cannot slip past the float64 check). Both are before any hook exists."""
    rows: list[tuple[int, float, float]] = []
    for position, member in enumerate(members):
        exact = float(member.weight)
        used = exact if evaluated is None else float(evaluated[position])
        rows.append((member.feature_index, exact, used))
    zero = [row for row in rows if row[2] == 0.0]
    if not zero:
        return
    live = [row for row in rows if row[2] != 0.0]
    detail = "; ".join(
        f"feature {index} (weight={exact!r}"
        + (f", evaluated as {used!r}" if used != exact else "")
        + ")"
        for index, exact, used in zero
    )
    underflowed = [row for row in zero if row[1] != 0.0]
    underflow_note = (
        f" Feature(s) {[row[0] for row in underflowed]} carry a weight that is NON-ZERO in float64 "
        "and UNDERFLOWS to exactly zero in float32, the dtype the hook multiplies by."
        if underflowed
        else ""
    )
    mixed_note = (
        f" The remaining member(s) {[row[0] for row in live]} do carry a live weight, so this group "
        f"of {len(rows)} would act as a group of {len(live)} while every count downstream still read "
        f"{len(rows)}."
        if live
        else ""
    )
    raise ZeroWeightMember(
        f"member weight is EXACTLY ZERO for {detail} [{stage}] -- REFUSING: a weight-0 member is "
        f"not a member.{underflow_note}{mixed_note}\n\n"
        "MEASURED, BEFORE THIS REFUSAL EXISTED: a k=2 ablate/subtract group with one weight-0 "
        "member produced a residual BIT-IDENTICAL to the k=1 arm while member_count still reported "
        "2. Every per-kind delta this module computes carries the weight as a factor -- amplify "
        "additive alpha * w_f * W_dec[f], clamp (target_f - a_f(h)) * w_f, subtract -alpha * w_f * "
        "a_f(h) * W_dec[f] -- so a zero weight makes that member contribute EXACTLY NOTHING at "
        "every alpha, in every dose form, at every position. The arm is therefore "
        "indistinguishable from a real result of the stated arity, and it would misattribute a "
        "k=1 effect to a larger group. This is the same refusal as an out-of-range index or a "
        "duplicated member: a group of k that quietly became k-1.\n\n"
        f"{NO_LEGITIMATE_ZERO_WEIGHT_MEMBER}"
    )


def _clamp_dose_rows(
    members: Sequence[GroupMember], alpha: float, evaluated: Sequence[float] | None = None
) -> list[tuple[int, float, float, str]]:
    """`[(feature_index, corpus_max, dose, reason_if_zero)]`, one row per
    member, in member order. `reason_if_zero` is `""` for a live dose.

    `evaluated` overrides the dose with the values actually computed in the
    dtype the hook will use, so an underflow to zero at float32 is reported
    as the underflow it is rather than as a `corpus_max == 0`."""
    rows: list[tuple[int, float, float, str]] = []
    for position, member in enumerate(members):
        corpus_max = 0.0 if member.corpus_max is None else float(member.corpus_max)
        exact = float(alpha) * corpus_max
        dose = exact if evaluated is None else float(evaluated[position])
        reason = ""
        if dose == 0.0:
            if corpus_max == 0.0:
                reason = "corpus_max == 0 (MAXIMAL SELECTIVITY, not a dead feature)"
            elif float(alpha) == 0.0:
                reason = "alpha == 0, so every member's dose is zero whatever its corpus_max is"
            else:
                reason = (
                    f"alpha * corpus_max == {exact!r} in float64 but UNDERFLOWS to exactly zero in "
                    "float32, the dtype the clamp target is evaluated in"
                )
        rows.append((member.feature_index, corpus_max, dose, reason))
    return rows


def _refuse_zero_clamp_dose(
    members: Sequence[GroupMember],
    alpha: float,
    *,
    stage: str,
    evaluated: Sequence[float] | None = None,
) -> None:
    """RAISE `ZeroClampDose` if any member's clamp dose is exactly zero.

    Called at BOTH gates -- `GroupSpec.__post_init__` (so no such spec can
    exist) and `resolve_group` (so a float32 underflow cannot slip past the
    float64 check) -- and in both places BEFORE any hook is registered and
    therefore before any forward pass."""
    rows = _clamp_dose_rows(members, alpha, evaluated)
    zero = [row for row in rows if row[3]]
    if not zero:
        return
    live = [row for row in rows if not row[3]]
    zero_indices = [row[0] for row in zero]
    detail = "; ".join(
        f"feature {index} (corpus_max={corpus_max!r}, dose={dose!r}): {reason}"
        for index, corpus_max, dose, reason in zero
    )
    mixed = ""
    if live:
        mixed = (
            f"\n\nTHIS IS A MIXED GROUP AND IT STILL REFUSES. Feature(s) "
            f"{[row[0] for row in live]} do have a non-zero dose "
            f"({[row[2] for row in live]}), and this group is NOT quietly run on that subset: a "
            f"{len(rows)}-member group acting as a {len(live)}-member one is the same arity "
            "corruption this module refuses for an out-of-range index or a duplicated member, and "
            "every count downstream would still read " + str(len(rows)) + "."
        )
    raise ZeroClampDose(
        f"dose_form='clamp' evaluates a dose of EXACTLY ZERO for feature(s) {zero_indices} at "
        f"alpha={float(alpha)!r} [{stage}] -- REFUSING to run an amplification that cannot amplify. "
        f"The dose is target_f = alpha * corpus_max_f. Per member: {detail}."
        f"{mixed}"
        "\n\nWHY THIS IS A REFUSAL AND NOT A WARNING: with a zero dose the hook fires, the ledger "
        "records a firing, the generation is scored and a verdict is recorded -- and NOTHING WAS "
        "DONE. That outcome is indistinguishable from 'this concept is not steerable', i.e. a "
        "failure manufactured by the instrument, which is this module's named defect class.\n\n"
        f"{MAXIMAL_SELECTIVITY_IS_NOT_A_DEAD_FEATURE}\n\n"
        f"{ZERO_DOSE_SCALE_IS_NOT_THIS_MODULE_S_TO_NAME}\n\n"
        "ABLATION IS UNAFFECTED. kind='ablate' with ablation_mechanism='subtract' removes "
        "a_f(h) * W_dec[f] -- the feature's ACTUAL contribution -- and needs no corpus reference at "
        "all, so this same group with these same members ablates normally. The zero-dose hazard is "
        "confined to the clamp/amplify arm."
    )


@dataclass(frozen=True)
class GroupMember:
    """One feature in the group, with its own weight AND ITS OWN SCALE.

    `weight` means different things per kind, and both are documented here
    rather than inferred: under `amplify` it scales that feature's decoder
    direction in the injected sum; under `ablate` it is the FRACTION of
    that feature's own decoder contribution removed (with the global
    `alpha` multiplying it, so `alpha=1, weight=1` is full ablation). A
    weight of EXACTLY ZERO is REFUSED by `GroupSpec` (`ZeroWeightMember`):
    it makes the member inert in every kind while the group still counts it.
    Negative weights are legal.

    `corpus_max` is THIS MEMBER'S OWN observed activation maximum, and it is
    the fix for RULING_13's D3. The committed bundle path derives ONE
    absolute clamp value from `corpus_max[feature_indices[0]]` and applies
    it to every member; features have different activation scales, so "the
    same dose" is not the same dose, and a group can pass because one member
    was massively overdosed while the others did nothing -- a single-feature
    result wearing a group label. Under `dose_form="clamp"` every member
    must carry its own, or the spec is REFUSED."""

    feature_index: int
    weight: float = 1.0
    corpus_max: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.feature_index, int) or isinstance(self.feature_index, bool):
            raise InvalidGroupSpec(f"feature_index must be an int; got {self.feature_index!r}")
        if self.feature_index < 0:
            raise InvalidGroupSpec(f"feature_index must be non-negative; got {self.feature_index}")
        weight = float(self.weight)
        if weight != weight or weight in (float("inf"), float("-inf")):
            raise InvalidGroupSpec(f"weight must be finite; got {self.weight!r}")
        if self.corpus_max is not None:
            corpus_max = float(self.corpus_max)
            if corpus_max != corpus_max or corpus_max in (float("inf"), float("-inf")):
                raise InvalidGroupSpec(f"corpus_max must be finite; got {self.corpus_max!r}")
            if corpus_max < 0.0:
                raise InvalidGroupSpec(
                    f"corpus_max must be non-negative; got {corpus_max} for feature "
                    f"{self.feature_index}"
                )


@dataclass(frozen=True)
class GroupSpec:
    """The frozen contract for one group intervention.

    `positions` defaults to `"all"` per the standing science ruling of
    2026-08-13 and matching every number this project has published
    (docs/positions_semantics.md).

    `dose_form` is ORTHOGONAL TO THE MECHANISM (RULING_13 Q3.6) and is a
    separate pre-registered choice:

    - `"additive"`: `h += alpha * sum_f w_f * W_dec[f]`. An absolute
      injection that acts whether or not the group already fires.
    - `"clamp"`: `h += sum_f (target_f - a_f(h)) * W_dec[f]` with
      `target_f = alpha * member.corpus_max` -- a dose in EACH MEMBER'S OWN
      max units, exactly the frozen causal grid's form, so a group arm stays
      commensurable with G-D. Under subtract this carries no reconstruction
      error and is an EXACT IDENTITY when every `target_f == a_f(h)`.
      A `target_f` that evaluates to EXACTLY ZERO -- which is what
      `corpus_max == 0`, i.e. MAXIMAL SELECTIVITY, produces at every alpha --
      RAISES `ZeroClampDose` here at construction. A dose of alpha that
      quietly became 0 is the same defect as a group of 5 that quietly became
      3, and it is refused in the same way.

    NEITHER IS MULTIPLICATIVE, on purpose. A multiplicative dose is
    identically zero where the group is silent, so an amplification arm
    built that way cannot induce the concept on precisely the eliciting
    prompts a sufficiency criterion depends on -- an amplifier that cannot
    amplify. This module does not offer that form."""

    kind: InterventionKind
    members: tuple[GroupMember, ...] = ()
    alpha: float = 1.0
    ablation_mechanism: AblationMechanism | None = None
    positions: Positions = "all"
    dose_form: DoseForm = "additive"
    hook_name: str | None = None
    label: str = ""
    #: RULING_13 Q3.8: for ABLATION the positions choice must be STATED, not
    #: defaulted, because `generated_only` leaves a concept encoded during
    #: prompt processing entirely un-ablated. Selecting `generated_only` for
    #: an ablation therefore requires saying so here.
    acknowledge_prompt_positions_unablated: bool = False

    def __post_init__(self) -> None:
        if self.kind not in ("noop", "amplify", "ablate"):
            raise InvalidGroupSpec(f"unknown kind {self.kind!r}")
        if self.positions not in ("all", "generated_only"):
            raise InvalidGroupSpec(f"unknown positions {self.positions!r}")
        alpha = float(self.alpha)
        if alpha != alpha or alpha in (float("inf"), float("-inf")):
            raise InvalidGroupSpec(f"alpha must be finite; got {self.alpha!r}")
        if not isinstance(self.members, tuple):
            raise InvalidGroupSpec("members must be a tuple (it is part of a frozen contract)")
        for member in self.members:
            if not isinstance(member, GroupMember):
                raise InvalidGroupSpec(f"members must be GroupMember instances; got {member!r}")
        seen: dict[int, int] = {}
        for member in self.members:
            seen[member.feature_index] = seen.get(member.feature_index, 0) + 1
        duplicates = sorted(index for index, count in seen.items() if count > 1)
        if duplicates:
            # A duplicate silently doubles that feature's weight and makes a
            # "5-feature group" a 4-feature group with one member counted twice.
            raise InvalidGroupSpec(
                f"group names feature(s) {duplicates} more than once -- refusing to double a "
                "member's weight implicitly; combine them into one GroupMember if that is intended."
            )
        if self.kind == "ablate" and self.ablation_mechanism not in ABLATION_MECHANISMS:
            raise InvalidGroupSpec(
                "kind='ablate' requires an explicit ablation_mechanism from "
                f"{list(ABLATION_MECHANISMS)}; got {self.ablation_mechanism!r}. There is no default: "
                "the two mechanisms differ by the SAE reconstruction error and the choice is a "
                "scientific one, not an implementation detail."
            )
        if self.kind != "ablate" and self.ablation_mechanism is not None:
            raise InvalidGroupSpec(
                f"ablation_mechanism is meaningful only for kind='ablate'; got kind={self.kind!r}"
            )
        # ARITY, NOT DOSE, AND THE SAME DEFECT. A weight-0 member is inert in
        # every kind and at every alpha, so a k-member group silently runs as a
        # (k-1)-member one while member_count still reports k. Refused here,
        # next to the duplicate check it belongs with, for the same reason.
        _refuse_zero_weight_members(self.members, stage="GroupSpec construction")
        if self.kind == "noop" and self.members:
            raise InvalidGroupSpec("kind='noop' must name no members; it is the structural control arm")
        if self.dose_form not in DOSE_FORMS:
            raise InvalidGroupSpec(f"unknown dose_form {self.dose_form!r}; expected one of {list(DOSE_FORMS)}")
        if self.dose_form == "clamp":
            if self.kind != "amplify":
                raise InvalidGroupSpec(
                    f"dose_form='clamp' is defined for kind='amplify'; got kind={self.kind!r}. "
                    "Ablation is already the target=0 case of a clamp and is expressed as kind="
                    "'ablate' so its mechanism stays explicit."
                )
            # RULING_13 D3, made structurally impossible rather than
            # documented: a clamp dose is meaningless without a per-member
            # scale, and one member's scale applied to five members is a
            # single-feature result wearing a group label.
            missing = sorted(m.feature_index for m in self.members if m.corpus_max is None)
            if missing:
                raise InvalidGroupSpec(
                    f"dose_form='clamp' requires a per-member corpus_max; feature(s) {missing} have "
                    "none. REFUSING to reuse another member's scale: features have different "
                    "activation scales, so one member's max applied to the group is not 'the same "
                    "dose' -- it is one member overdosed while the others do nothing."
                )
            # THE FIRST GATE ON A ZERO DOSE, and the earliest one available:
            # at construction, so no spec naming a zero-dose member can exist
            # to be handed to a hook, a backend or a job. 89.52% of full-space
            # cells have corpus_max == 0, which is MAXIMAL SELECTIVITY and not
            # a dead feature, so the refusal is about the scale.
            _refuse_zero_clamp_dose(
                self.members, float(self.alpha), stage="GroupSpec construction"
            )
        if (
            self.kind == "ablate"
            and self.positions == "generated_only"
            and not self.acknowledge_prompt_positions_unablated
        ):
            raise InvalidGroupSpec(
                "kind='ablate' with positions='generated_only' leaves every PROMPT position "
                "un-ablated, so a concept encoded during prompt processing passes the intervention "
                "untouched. That choice must be STATED, not defaulted: pass "
                "acknowledge_prompt_positions_unablated=True if it is deliberate, or use "
                "positions='all'."
            )
        if self.acknowledge_prompt_positions_unablated and not (
            self.kind == "ablate" and self.positions == "generated_only"
        ):
            raise InvalidGroupSpec(
                "acknowledge_prompt_positions_unablated is meaningful only for kind='ablate' with "
                "positions='generated_only'; setting it elsewhere records a choice that was never made"
            )

    # -- convenience constructors -------------------------------------------

    @staticmethod
    def noop(*, hook_name: str | None = None, label: str = "control-noop") -> GroupSpec:
        """The paired same-seed control arm. Registers NO hook at all, so
        bit-identity with an unhooked run is structural rather than
        arithmetic."""
        return GroupSpec(kind="noop", hook_name=hook_name, label=label)

    @staticmethod
    def reconstruction_control(
        *, hook_name: str | None = None, label: str = "control-reconstruction-only"
    ) -> GroupSpec:
        """An EMPTY group under mechanism (a): `h -> decode(encode(h))`,
        touching no feature.

        This is not a wasted arm. Mechanism (a) discards the reconstruction
        error whether or not a feature is ablated, so an (a)-based ablation
        measured against an unhooked control confounds the group's effect
        with the SAE's reconstruction error. This arm isolates that floor,
        and is the control an (a) result must be read against."""
        return GroupSpec(
            kind="ablate",
            members=(),
            alpha=1.0,
            ablation_mechanism="reconstruct",
            hook_name=hook_name,
            label=label,
        )

    # -- derived properties --------------------------------------------------

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def feature_indices(self) -> tuple[int, ...]:
        return tuple(member.feature_index for member in self.members)

    def without(self, feature_index: int) -> GroupSpec:
        """This spec with one member removed -- the leave-one-out arm of
        `joint_intervention_lane.json` RULING_4 stage 3. Raises if the
        feature is not a member, so a mistyped index cannot quietly produce
        a leave-none-out run that looks like a passing minimality test."""
        if feature_index not in self.feature_indices:
            raise InvalidGroupSpec(
                f"cannot leave out feature {feature_index}: it is not a member of this group "
                f"{list(self.feature_indices)}"
            )
        kept = tuple(m for m in self.members if m.feature_index != feature_index)
        # `replace` rather than a hand-listed constructor call: a field added
        # later (dose_form and the positions acknowledgement both were) would
        # otherwise be silently dropped from every leave-one-out arm, making
        # the minimality sweep run a different intervention from the joint one.
        return replace(
            self, members=kept, label=f"{self.label or self.kind}-without-{feature_index}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "members": [
                {
                    "feature_index": m.feature_index,
                    "weight": float(m.weight),
                    "corpus_max": None if m.corpus_max is None else float(m.corpus_max),
                }
                for m in self.members
            ],
            "member_count": self.member_count,
            "alpha": float(self.alpha),
            "ablation_mechanism": self.ablation_mechanism,
            "positions": self.positions,
            "dose_form": self.dose_form,
            "acknowledge_prompt_positions_unablated": self.acknowledge_prompt_positions_unablated,
            "hook_name": self.hook_name,
            "label": self.label,
        }


def null_configuration_is_exact_identity(spec: GroupSpec) -> bool:
    """Is this spec, as configured, a bit-exact no-op?

    `True` for `noop`, for `amplify` with `alpha == 0` or no members, and
    for `ablate`/`subtract` with `alpha == 0` or no members.

    `False` for `ablate`/`reconstruct` even with no members and `alpha == 0`
    -- that path still replaces `h` with `decode(encode(h))`. Callers that
    need a genuine identity under (a) do not have one; they have
    `GroupSpec.reconstruction_control()` as the arm to subtract instead.

    `False` for `dose_form='clamp'` at `alpha == 0` too, and that is not a
    quirk: clamping a group to a target of zero is an ABLATION, the most
    active intervention this module performs. Only an EMPTY clamp group is
    a no-op. Treating alpha==0 as universally inert would have made the
    strongest ablation available report itself as a control.

    That clamp/alpha==0 branch is now DEFENCE IN DEPTH rather than a
    reachable state: `GroupSpec` refuses a clamp spec whose dose evaluates
    to zero (`ZeroClampDose`), and alpha == 0 makes every member's dose
    zero. An ablation must be expressed as `kind='ablate'` with its
    mechanism named, which is what that refusal says. The branch is kept
    because a non-identity must never be reported as an identity, whichever
    gate is doing the refusing."""
    if spec.kind == "noop":
        return True
    if spec.member_count == 0:
        return spec.kind == "amplify" or spec.ablation_mechanism == "subtract"
    if spec.dose_form == "clamp":
        return False
    if float(spec.alpha) != 0.0:
        return False
    if spec.kind == "amplify":
        return True
    return spec.ablation_mechanism == "subtract"


# ---------------------------------------------------------------------------
# Resolution against a real SAE.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedGroup:
    """A `GroupSpec` checked against a specific SAE, with the constant
    parts of the arithmetic precomputed once (never per token)."""

    spec: GroupSpec
    d_sae: int
    d_in: int
    hook_name: str
    feature_indices: torch.Tensor  # [k] long
    weights: torch.Tensor  # [k] float32
    decoder_rows: torch.Tensor  # [k, d_in] float32
    amplify_direction: torch.Tensor  # [d_in] float32 == sum_f w_f * W_dec[f]
    device: torch.device
    #: [k] float32 -- alpha * corpus_max_f per member, the absolute clamp
    #: target IN THAT MEMBER'S OWN MAX UNITS. Empty unless dose_form=='clamp'.
    clamp_targets: torch.Tensor | None = None

    @property
    def member_count(self) -> int:
        return int(self.feature_indices.shape[0])

    def expected_amplify_delta(self, dtype: torch.dtype | None = None) -> torch.Tensor:
        """`alpha * sum_f w_f * W_dec[f]` -- the exact vector an ADDITIVE
        amplify hook must add at every steered position. Computed here from
        the resolved rows so a test can assert against it WITHOUT calling
        the hook's own code path.

        Defined only for `dose_form='additive'`. A clamp delta depends on
        the residual (`target_f - a_f(h)`) and so has no constant form;
        `clamp_amplify_delta()` computes it per call."""
        if self.spec.dose_form != "additive":
            raise InvalidGroupSpec(
                f"expected_amplify_delta is the constant ADDITIVE delta; this spec uses "
                f"dose_form={self.spec.dose_form!r}, whose delta depends on the residual. Use "
                "clamp_amplify_delta(sae, resolved, residual)."
            )
        delta = float(self.spec.alpha) * self.amplify_direction
        return delta if dtype is None else delta.to(dtype)


def resolve_group(sae: Any, spec: GroupSpec) -> ResolvedGroup:
    """Bind a `GroupSpec` to a real SAE, or REFUSE.

    Refuses on: a feature index >= d_sae, a negative index (caught in
    `GroupMember`), a duplicated member (caught in `GroupSpec`), and a
    decoder/cfg dimension disagreement. Nothing is dropped, clamped, or
    rounded into range -- `resolved.member_count == spec.member_count` is
    an invariant this function asserts before returning."""
    d_sae, d_in = resolve_sae_dims(sae)
    w_dec = resolve_decoder_matrix(sae)
    device = w_dec.device

    # Membership is validated BEFORE the hook point is resolved. Ordering
    # matters here: a missing hook_name is a caller-configuration problem
    # that would otherwise mask the more serious FeatureNotInSAE refusal and
    # send whoever hit it looking in the wrong place.
    out_of_range = sorted({i for i in spec.feature_indices if i >= d_sae})
    if out_of_range:
        raise FeatureNotInSAE(
            f"feature index/indices {out_of_range} are not in this SAE (d_sae={d_sae}) -- refusing to "
            f"drop them from the group. A group of {spec.member_count} that quietly became "
            f"{spec.member_count - len(out_of_range)} would report the wrong cardinality everywhere "
            "downstream."
        )

    hook_name = spec.hook_name or resolve_hook_name(sae)

    indices = torch.tensor(spec.feature_indices, dtype=torch.long, device=device)
    weights = torch.tensor(
        [float(m.weight) for m in spec.members], dtype=torch.float32, device=device
    )
    # The SECOND weight gate, on the float32 values the hook multiplies by --
    # the counterpart of the float32 clamp-target gate below, catching a weight
    # that is non-zero in float64 and underflows here. Still before any hook.
    _refuse_zero_weight_members(
        spec.members,
        stage="resolve_group, on the float32-evaluated weights",
        evaluated=[float(v) for v in weights.tolist()],
    )
    rows = w_dec.detach().to(torch.float32).index_select(0, indices) if spec.members else torch.zeros(
        (0, d_in), dtype=torch.float32, device=device
    )
    direction = (
        (weights.unsqueeze(1) * rows).sum(dim=0)
        if spec.members
        else torch.zeros(d_in, dtype=torch.float32, device=device)
    )

    # Per-member clamp target IN THAT MEMBER'S OWN MAX UNITS (RULING_13 D3).
    # There is deliberately no fallback to another member's scale: GroupSpec
    # already refused a clamp spec with a missing corpus_max, so reaching here
    # with one would be an internal contradiction rather than something to
    # paper over.
    clamp_targets = None
    if spec.dose_form == "clamp":
        clamp_targets = torch.tensor(
            [float(spec.alpha) * float(m.corpus_max) for m in spec.members],
            dtype=torch.float32,
            device=device,
        )
        # THE SECOND GATE ON A ZERO DOSE, on the values ACTUALLY EVALUATED in
        # the dtype the hook uses. GroupSpec already refused every dose that is
        # zero in float64; this catches the one it structurally cannot see -- a
        # product that is non-zero in float64 and UNDERFLOWS to exactly zero at
        # float32, which would reach the hook as a silent no-op. Still before
        # any hook is registered, so no forward pass is spent on it.
        _refuse_zero_clamp_dose(
            spec.members,
            float(spec.alpha),
            stage="resolve_group, on the float32-evaluated targets",
            evaluated=[float(v) for v in clamp_targets.tolist()],
        )

    resolved = ResolvedGroup(
        spec=spec,
        d_sae=d_sae,
        d_in=d_in,
        hook_name=hook_name,
        feature_indices=indices,
        weights=weights,
        decoder_rows=rows,
        amplify_direction=direction,
        device=device,
        clamp_targets=clamp_targets,
    )
    if resolved.member_count != spec.member_count:
        raise GroupInterventionError(
            f"internal invariant broken: resolved {resolved.member_count} members from a spec naming "
            f"{spec.member_count}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Firing observability.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FiringRecord:
    """One hook invocation, recorded whether or not it changed anything.

    A call that computed a zero delta still appears here. That is the
    point: 'the hook fired and did nothing' and 'the hook never fired' are
    different failures and must be distinguishable after the fact."""

    call_index: int
    call_classification: Literal["prefill", "decode"]
    hook_name: str
    tensor_shape: tuple[int, ...]
    absolute_position_start: int
    absolute_position_end: int  # exclusive
    positions_seen: int  # batch * seq_len slots this call carried
    positions_modified: int  # batch * seq_len slots this call actually changed
    delta_norm: float
    residual_norm: float
    max_abs_delta: float
    #: Elements where a NON-ZERO delta was requested and the realised delta
    #: was EXACTLY ZERO -- the residual stream absorbed it. Always zero in
    #: float32 at any sane alpha; routine at bfloat16. See DTYPE_LIMITS.
    absorbed_element_count: int = 0
    #: Elements where a non-zero delta was requested at all, the denominator
    #: `absorbed_element_count` is a count out of.
    requested_nonzero_element_count: int = 0
    residual_dtype: str = "unrecorded"

    @property
    def absorbed_fraction(self) -> float:
        if self.requested_nonzero_element_count == 0:
            return 0.0
        return self.absorbed_element_count / self.requested_nonzero_element_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_index": self.call_index,
            "call_classification": self.call_classification,
            "hook_name": self.hook_name,
            "tensor_shape": list(self.tensor_shape),
            "absolute_position_start": self.absolute_position_start,
            "absolute_position_end": self.absolute_position_end,
            "positions_seen": self.positions_seen,
            "positions_modified": self.positions_modified,
            "delta_norm": self.delta_norm,
            "residual_norm": self.residual_norm,
            "max_abs_delta": self.max_abs_delta,
            "absorbed_element_count": self.absorbed_element_count,
            "requested_nonzero_element_count": self.requested_nonzero_element_count,
            "absorbed_fraction": self.absorbed_fraction,
            "residual_dtype": self.residual_dtype,
        }


@dataclass
class FiringLedger:
    """Every invocation of one hook, in order.

    Deliberately a plain mutable object handed INTO the hook builder rather
    than something read off the hook afterwards: the caller holds it, so a
    hook that was never registered leaves an empty ledger the caller still
    owns and still checks. A ledger that only existed inside a hook that
    never ran could not report its own absence."""

    records: list[FiringRecord] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        return len(self.records)

    @property
    def prefill_call_count(self) -> int:
        return sum(1 for r in self.records if r.call_classification == "prefill")

    @property
    def decode_call_count(self) -> int:
        return sum(1 for r in self.records if r.call_classification == "decode")

    @property
    def positions_modified(self) -> int:
        return sum(r.positions_modified for r in self.records)

    @property
    def positions_seen(self) -> int:
        return sum(r.positions_seen for r in self.records)

    @property
    def total_delta_norm(self) -> float:
        return float(sum(r.delta_norm for r in self.records))

    @property
    def max_abs_delta(self) -> float:
        return max((r.max_abs_delta for r in self.records), default=0.0)

    @property
    def absorbed_element_count(self) -> int:
        return sum(r.absorbed_element_count for r in self.records)

    @property
    def requested_nonzero_element_count(self) -> int:
        return sum(r.requested_nonzero_element_count for r in self.records)

    @property
    def absorbed_fraction(self) -> float:
        """Share of requested-non-zero elements the residual stream swallowed
        whole. Zero in float32; routinely large in bfloat16 at small alpha --
        and a green exact-delta assertion does NOT rule it out, which is the
        entire point of recording it. See DTYPE_LIMITS."""
        total = self.requested_nonzero_element_count
        return (self.absorbed_element_count / total) if total else 0.0

    @property
    def residual_dtypes(self) -> tuple[str, ...]:
        return tuple(sorted({r.residual_dtype for r in self.records}))

    def summary(self) -> dict[str, Any]:
        return {
            "call_count": self.call_count,
            "prefill_call_count": self.prefill_call_count,
            "decode_call_count": self.decode_call_count,
            "positions_seen": self.positions_seen,
            "positions_modified": self.positions_modified,
            "total_delta_norm": self.total_delta_norm,
            "max_abs_delta": self.max_abs_delta,
            "absorbed_element_count": self.absorbed_element_count,
            "requested_nonzero_element_count": self.requested_nonzero_element_count,
            "absorbed_fraction": self.absorbed_fraction,
            "residual_dtypes": list(self.residual_dtypes),
        }


@dataclass(frozen=True)
class FiringExpectation:
    """What the caller says the hook will do, stated BEFORE the run.

    `call_count` and `positions_modified` are derived from observables the
    hook does not control -- the prompt's token count and the returned
    sequence's token count -- so checking the ledger against them is a real
    check and not a restatement."""

    call_count: int
    positions_modified: int | None = None
    require_nonzero_delta: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_count": self.call_count,
            "positions_modified": self.positions_modified,
            "require_nonzero_delta": self.require_nonzero_delta,
        }


def expected_generation_firing(
    *,
    prompt_token_count: int,
    generated_token_count: int,
    positions: Positions,
    batch_size: int = 1,
    require_nonzero_delta: bool = True,
) -> FiringExpectation:
    """The exact firing an intervention must produce during one
    `HookedTransformer.generate(..., use_past_kv_cache=True)` call.

    From `docs/positions_semantics.md`, verified against the real fixture
    model in this module's tests: the hook fires ONCE over the whole prompt
    (the prefill, `seq_len == prompt_token_count`, which itself samples the
    FIRST generated token), then once per subsequent token
    (`seq_len == 1`). So

        call_count == generated_token_count

    and, at `positions="all"`, every slot the hook sees is modified:

        positions_modified == batch_size * (prompt_token_count + generated_token_count - 1)

    while at `positions="generated_only"` the prefill contributes nothing:

        positions_modified == batch_size * (generated_token_count - 1)

    `generated_token_count` is taken from the RETURNED token tensor, so
    early `stop_at_eos` termination is handled exactly rather than by
    loosening the assertion into one that cannot fail."""
    if prompt_token_count < 1:
        raise ValueError(f"prompt_token_count must be >= 1; got {prompt_token_count}")
    if generated_token_count < 1:
        raise ValueError(f"generated_token_count must be >= 1; got {generated_token_count}")
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1; got {batch_size}")
    if positions == "all":
        modified = batch_size * (prompt_token_count + generated_token_count - 1)
    elif positions == "generated_only":
        modified = batch_size * (generated_token_count - 1)
    else:
        raise ValueError(f"unknown positions {positions!r}")
    return FiringExpectation(
        call_count=generated_token_count,
        positions_modified=modified,
        require_nonzero_delta=require_nonzero_delta,
    )


def assert_fired_as_expected(
    ledger: FiringLedger, expectation: FiringExpectation, *, context: str = ""
) -> dict[str, Any]:
    """RAISE unless the hook fired exactly as expected. No warn path.

    Returns the ledger summary so a caller can record what it asserted --
    an assertion whose measured value is never written down is one nobody
    can audit afterwards."""
    where = f" [{context}]" if context else ""
    problems: list[str] = []
    if ledger.call_count != expectation.call_count:
        problems.append(
            f"hook fired {ledger.call_count} time(s), expected exactly {expectation.call_count}"
        )
    if expectation.positions_modified is not None and ledger.positions_modified != expectation.positions_modified:
        problems.append(
            f"hook modified {ledger.positions_modified} position slot(s), expected exactly "
            f"{expectation.positions_modified}"
        )
    # Only meaningful once the hook actually ran: "fired 0 times" is already
    # reported above, and repeating it as "every delta was zero" would bury
    # the real cause under a second, derivative complaint.
    if expectation.require_nonzero_delta and ledger.call_count > 0 and ledger.max_abs_delta <= 0.0:
        problems.append(
            "hook fired but every injected delta was exactly zero -- an intervention that ran and "
            "changed nothing is indistinguishable from one that never ran"
        )
    if problems:
        raise HookFiringMismatch(
            f"intervention hook did not fire as expected{where}: "
            + "; ".join(problems)
            + f". Measured: {json.dumps(ledger.summary(), sort_keys=True)}. Expected: "
            + f"{json.dumps(expectation.to_dict(), sort_keys=True)}. Refusing to report a result "
            "from a hook whose behaviour was not the one under test."
        )
    return ledger.summary()


# ---------------------------------------------------------------------------
# Exact-delta checking.
# ---------------------------------------------------------------------------


def delta_tolerance(before: torch.Tensor, expected: torch.Tensor | None = None) -> float:
    """The tolerance at which `(x + d) - x == d` is the strongest claim
    floating point permits.

    Not a hand-tuned epsilon. `(x + d) - x` differs from `d` by at most
    about one unit in the last place OF `x`, so the tolerance is the
    representable spacing at `x`'s own magnitude, with a small factor for
    the intermediate rounding of `d` itself. Passing a large residual and a
    tiny delta therefore relaxes this automatically and honestly, instead
    of failing a correct hook or hiding a wrong one behind a constant.

    MEASURED to hold unchanged at float32, bfloat16 and float16 -- the
    formula needed no dtype-dependent form, because `eps` already carries
    the dtype. See DTYPE_LIMITS for why holding is NOT the useful property
    at bfloat16."""
    dtype = before.dtype if before.is_floating_point() else torch.float32
    eps = torch.finfo(dtype).eps
    scale = float(before.detach().abs().max().item()) if before.numel() else 1.0
    if expected is not None and expected.numel():
        scale = max(scale, float(expected.detach().abs().max().item()))
    return float(eps * max(scale, 1.0) * 8.0)


DTYPE_LIMITS = """THE EXACT-DELTA ASSERTION IS NECESSARY BUT NOT SUFFICIENT BELOW FLOAT32.

Measured THROUGH THIS MODULE'S OWN HOOK (not a side calculation) on the
synthetic fixture, and reproducible with `--selfcheck`, which prints this
table. Residual max |x| ~ 9, a group of three features, 160 elements:

    dtype       alpha    worst        tolerance    passes   absorbed
    float32     10       9.537e-07    8.632e-06    yes        0/160
    float32     0.1      2.305e-07    7.005e-06    yes        0/160
    float32     0.001    2.228e-07    7.005e-06    yes        0/160
    bfloat16    10       7.346e-02    5.657e-01    yes        0/160
    bfloat16    0.1      1.447e-02    4.590e-01    yes       41/160
    bfloat16    0.001    9.052e-04    4.590e-01    yes      157/160
    float16     10       5.457e-03    7.072e-02    yes        0/160
    float16     0.1      1.643e-03    5.737e-02    yes        9/160
    float16     0.001    9.052e-04    5.737e-02    yes      138/160

THE TOLERANCE FORMULA NEEDED NO DTYPE-DEPENDENT FORM. `eps` already carries
the dtype, so `eps * max(|x|, |d|, 1) * 8` holds at all three without
modification -- the worst discrepancy stays roughly an order of magnitude
inside the bound at every row. That question is answered: the derived
`~ulp(x)` tolerance still holds at bfloat16 and float16.

READ THE LAST TWO COLUMNS TOGETHER. The tolerance holds everywhere -- and
that is the problem, not the reassurance. At bfloat16, alpha=0.001, the
residual stream swallowed the requested delta whole at 157 of 160 elements:
the intervention did nothing at those positions, and the exact-delta
assertion PASSED, because the absorbed magnitude (9e-04) is far below the
tolerance the dtype forces (6.3e-01). That is a clean negative wearing a
passing grade -- this module's own named defect class, reached through
arithmetic rather than through a hook that failed to fire.

THE TOLERANCE IS NOT THE FIX AND MUST NOT BE TIGHTENED. The rounding is
real: `x + d == x` exactly whenever |d| falls below the spacing at |x|.
Tightening the bound would fail correct hooks at production dtype, which is
how a green assertion gets negotiated away. The fix is a SECOND, INDEPENDENT
measurement: `FiringRecord.absorbed_element_count`, always recorded, in the
summary of every arm, with `assert_no_absorption()` available for callers
that need the strong guarantee and `minimum_effective_alpha()` to size a
dose that can survive the dtype at all.

WHAT THIS MEANS OPERATIONALLY. At bfloat16 a passing exact-delta assertion
does NOT establish that the intervention was applied. Only the absorption
census does. Any bfloat16 steering result whose absorbed_fraction is not
reported should be read as not having checked."""


def minimum_effective_alpha(
    residual: torch.Tensor, direction: torch.Tensor, *, dtype: torch.dtype | None = None
) -> float:
    """The smallest `alpha` at which `alpha * direction` can survive being
    added to `residual` at `dtype` at all.

    Below roughly `eps * |x| / 2` per element, `x + d == x` exactly and the
    intervention is a silent no-op there. This returns the alpha at which
    the direction's LARGEST component clears that floor, so it is the
    optimistic bound: alphas below it are certainly absorbed somewhere,
    alphas above it are not guaranteed to survive everywhere. It sizes a
    dose; it does not certify one, and `assert_no_absorption()` is what
    actually checks."""
    resolved = dtype or (residual.dtype if residual.is_floating_point() else torch.float32)
    eps = torch.finfo(resolved).eps
    scale = float(residual.detach().abs().max().item()) if residual.numel() else 1.0
    peak = float(direction.detach().abs().max().item()) if direction.numel() else 0.0
    if peak <= 0.0:
        return float("inf")
    return float(eps * max(scale, 1.0) * 0.5 / peak)


def measure_absorption(
    before: torch.Tensor, after: torch.Tensor, expected_delta: torch.Tensor
) -> tuple[int, int]:
    """`(absorbed, requested_nonzero)` element counts.

    Absorbed means: a non-zero delta was requested at that element and the
    realised delta is EXACTLY zero. Counted on the realised tensors, not
    predicted from `eps`, so it stays correct for any dtype and any
    accumulation order the backend actually used."""
    measured = (after - before).to(torch.float32)
    wanted = expected_delta.to(torch.float32).expand_as(measured)
    requested_nonzero = wanted != 0.0
    absorbed = requested_nonzero & (measured == 0.0)
    return int(absorbed.sum().item()), int(requested_nonzero.sum().item())


def assert_exact_delta(
    before: torch.Tensor,
    after: torch.Tensor,
    expected_delta: torch.Tensor,
    *,
    atol: float | None = None,
    context: str = "",
) -> float:
    """RAISE unless `after - before` is exactly `expected_delta`.

    Returns the measured maximum absolute discrepancy so a caller can
    record how exact 'exact' actually was.

    BELOW FLOAT32 A PASS FROM THIS FUNCTION DOES NOT ESTABLISH THAT THE
    DELTA WAS APPLIED -- see DTYPE_LIMITS. Pair it with
    `assert_no_absorption()` or with the `absorbed_fraction` the ledger
    records on every call."""
    if before.shape != after.shape:
        raise ExactDeltaMismatch(
            f"shape changed across the intervention: {tuple(before.shape)} -> {tuple(after.shape)}"
        )
    tol = delta_tolerance(before, expected_delta) if atol is None else float(atol)
    measured = (after - before).to(torch.float32)
    residual = (measured - expected_delta.to(torch.float32).expand_as(measured)).abs()
    worst = float(residual.max().item()) if residual.numel() else 0.0
    if worst > tol:
        where = f" [{context}]" if context else ""
        raise ExactDeltaMismatch(
            f"injected delta is not the delta that was requested{where}: max |measured - expected| = "
            f"{worst:.6g} exceeds tolerance {tol:.6g}"
        )
    return worst


InterventionState = Literal["CONTROL", "NOT_EXERCISED", "FIRED_BUT_INERT", "APPLIED"]

INTERVENTION_STATE_MEANINGS: dict[str, str] = {
    "CONTROL": "The paired control arm. No hook was registered; this is the reference, not a result.",
    "NOT_EXERCISED": (
        "VOID, NOT A NULL. The hook never fired, so no intervention happened. Any downstream "
        "reading of 'the concept was not steerable' from this arm would be a failure MANUFACTURED "
        "BY THE INSTRUMENT."
    ),
    "FIRED_BUT_INERT": (
        "VOID, NOT A NULL. The hook fired and injected an exactly-zero delta at every position -- "
        "e.g. an ablation of a group that was already silent. The model was never perturbed, so "
        "an unchanged continuation carries no information about the group."
    ),
    "APPLIED": (
        "The intervention ran and moved the residual stream. Only this state produces an arm whose "
        "outcome may be read as a result at all."
    ),
}
"""RULING_13: VOID and NOT-EXERCISED ARE NOT NULLS. The ledger already
distinguishes fired-and-identity from never-fired; this is the reporting
layer preserving that distinction instead of collapsing both into a null a
reader would take for evidence of absence."""


def classify_intervention_state(spec: GroupSpec, ledger: FiringLedger) -> InterventionState:
    """Which of the four states this arm is in, from the ledger alone.

    Deliberately NOT a judgement about the effect: no threshold, no margin,
    no comparison to a criterion. It answers only 'did an intervention
    happen', which is the question that must be settled before any outcome
    is read."""
    if spec.kind == "noop":
        return "CONTROL"
    if ledger.call_count == 0:
        return "NOT_EXERCISED"
    if ledger.max_abs_delta <= 0.0:
        return "FIRED_BUT_INERT"
    return "APPLIED"


def assert_no_absorption(ledger: FiringLedger, *, context: str = "") -> dict[str, Any]:
    """RAISE if the residual stream swallowed ANY requested delta whole.

    Opt-in and deliberately not folded into `assert_fired_as_expected`: at
    bfloat16 some absorption is a physical consequence of the dtype, not a
    defect, and a check that always failed there would be waved through
    within a week. This is the strong guarantee, for callers who need to
    state that every requested element actually landed -- a float32
    preflight, or a bfloat16 run whose alpha was sized by
    `minimum_effective_alpha()` and now needs to be verified rather than
    assumed."""
    if ledger.absorbed_element_count == 0:
        return ledger.summary()
    where = f" [{context}]" if context else ""
    raise ExactDeltaMismatch(
        f"the residual stream absorbed {ledger.absorbed_element_count} of "
        f"{ledger.requested_nonzero_element_count} requested-non-zero element(s) "
        f"({ledger.absorbed_fraction:.1%}) at dtype(s) {list(ledger.residual_dtypes)}{where} -- the "
        "intervention was a silent no-op at those elements. The exact-delta assertion cannot see "
        "this: the absorbed magnitude is below the tolerance the dtype forces. Raise alpha (see "
        "minimum_effective_alpha) or run at float32."
    )


# ---------------------------------------------------------------------------
# The two ablation mechanisms, and the gap between them.
# ---------------------------------------------------------------------------


def group_activations(sae: Any, resolved: ResolvedGroup, residual: torch.Tensor) -> torch.Tensor:
    """`[..., k]` -- this group's feature activations at every position."""
    feats = sae.encode(residual.to(torch.float32))
    return feats.index_select(-1, resolved.feature_indices)


def clamp_amplify_delta(sae: Any, resolved: ResolvedGroup, residual: torch.Tensor) -> torch.Tensor:
    """The clamp dose under SUBTRACT (RULING_13 Q3.6):

        h + sum_f (target_f - a_f(h)) * W_dec[f]

    ONE encode of the CLEAN residual, all k targets applied to a single
    feature vector, ONE delta. No reconstruction error enters -- the
    decoder bias and the SAE's error both cancel, exactly as they do in the
    decode-difference form -- and the delta is an EXACT ZERO wherever every
    `target_f` already equals `a_f(h)`.

    This is the form the frozen causal grid uses, so a group arm built on
    it stays commensurable with G-D, and unlike a multiplicative dose it
    still acts where the group is silent (`a_f(h) == 0` gives the full
    `target_f * W_dec[f]`), which is what a sufficiency criterion needs."""
    if resolved.member_count == 0:
        return torch.zeros_like(residual, dtype=torch.float32)
    if resolved.clamp_targets is None:
        raise InvalidGroupSpec("clamp_amplify_delta requires a spec with dose_form='clamp'")
    acts = group_activations(sae, resolved, residual)  # [..., k]
    shortfall = (resolved.clamp_targets - acts) * resolved.weights  # [..., k]
    return shortfall @ resolved.decoder_rows  # [..., d_in]


def ablate_subtract_delta(sae: Any, resolved: ResolvedGroup, residual: torch.Tensor) -> torch.Tensor:
    """Mechanism (b)'s delta: `-alpha * sum_f w_f * a_f(h) * W_dec[f]`.

    The residual stream's own reconstruction error is untouched, because
    nothing here reconstructs."""
    if resolved.member_count == 0:
        return torch.zeros_like(residual, dtype=torch.float32)
    acts = group_activations(sae, resolved, residual)  # [..., k]
    scaled = acts * resolved.weights * float(resolved.spec.alpha)  # [..., k]
    return -(scaled @ resolved.decoder_rows)  # [..., d_in]


def ablate_reconstruct_delta(sae: Any, resolved: ResolvedGroup, residual: torch.Tensor) -> torch.Tensor:
    """Mechanism (a)'s delta: `decode(scaled_feats) - h`.

    Note what is NOT here: any term that carries `h`'s reconstruction error
    forward. `decode(...)` is written back wholesale, so the error is
    discarded. That is the entire difference from (b) and it is present
    even when the group is empty."""
    x32 = residual.to(torch.float32)
    feats = sae.encode(x32)
    if resolved.member_count:
        keep = 1.0 - resolved.weights * float(resolved.spec.alpha)  # [k]
        scaled = feats.clone()
        selected = scaled.index_select(-1, resolved.feature_indices) * keep
        scaled = scaled.index_copy(-1, resolved.feature_indices, selected)
    else:
        scaled = feats
    return sae.decode(scaled).to(torch.float32) - x32


def reconstruction_error(sae: Any, residual: torch.Tensor) -> torch.Tensor:
    """`h - decode(encode(h))` -- the part of the residual stream the SAE
    cannot express."""
    x32 = residual.to(torch.float32)
    return x32 - sae.decode(sae.encode(x32)).to(torch.float32)


def measure_sae_fidelity_context(
    sae: Any, residual: torch.Tensor, *, hook_point: str, reference_spec: GroupSpec | None = None
) -> dict[str, Any]:
    """The ONCE-PER-CONFIGURATION fidelity statistic (RULING_13 Q3.3/Q3.9).

    Mechanism (a) is not a parallel arm and not a robustness arm. Its
    difference from (b) is `decode(encode(h)) - h`, independent of the
    group, of alpha and of the per-feature weights -- A CONSTANT OF THE SAE
    AT ITS HOOK POINT. Running it per prompt re-measures a constant while
    carrying an artifact larger than the signal. So it runs once per
    (model, SAE, hook point) and is reported alongside results, NEVER as
    evidence about a group.

    Two ratios are returned and they are NOT interchangeable:

    - `signal_to_artifact_ratio_for_mechanism_a` = |recon_err| / |delta_b|,
      defined only when a `reference_spec` is supplied. Decisive for
      choosing a mechanism; says nothing about SAE quality in general.
    - `reconstruction_error_over_residual` = |recon_err| / |h|. THIS is the
      residual-relative fidelity number, and it is the one that may be
      described as how much of the stream the SAE fails to express.

    They are reported under separate names precisely because the first gets
    carried into claims only the second could support."""
    with torch.no_grad():
        error = reconstruction_error(sae, residual)
        error_norm = float(error.norm().item())
        residual_norm = float(residual.to(torch.float32).norm().item())
        delta_b_norm = None
        if reference_spec is not None and reference_spec.member_count:
            subtract_spec = replace(
                reference_spec, kind="ablate", ablation_mechanism="subtract", dose_form="additive"
            )
            delta_b_norm = float(
                ablate_subtract_delta(
                    sae, resolve_group(sae, subtract_spec), residual
                ).norm().item()
            )
    return {
        "hook_point": hook_point,
        "measured_once_per": "(model, sae, hook_point)",
        "reconstruction_error_norm": error_norm,
        "residual_norm": residual_norm,
        "reconstruction_error_over_residual": (
            error_norm / residual_norm if residual_norm > 0 else None
        ),
        "reference_group_delta_b_norm": delta_b_norm,
        "signal_to_artifact_ratio_for_mechanism_a": (
            error_norm / delta_b_norm if delta_b_norm else None
        ),
        "ruled_instrument": RULED_INSTRUMENT_MECHANISM,
        "prohibited_readings": RECONSTRUCT_OVERREAD_GUARD,
    }


def assert_control_is_admissible(spec: GroupSpec, control: GroupSpec) -> None:
    """RULING_13 Q3.9: an (a) result read against an UNHOOKED control is
    REFUSED, not caveated.

    Under (a), alpha=0 and even an empty group leave the residual moved by
    the whole reconstruction error, so an (a) arm paired with a noop control
    reports mostly SAE fidelity wearing the label of steering. The required
    control is the reconstruction-only arm."""
    if spec.kind == "ablate" and spec.ablation_mechanism == "reconstruct":
        control_is_reconstruction_only = (
            control.kind == "ablate"
            and control.ablation_mechanism == "reconstruct"
            and control.member_count == 0
        )
        if not control_is_reconstruction_only:
            raise InvalidGroupSpec(
                "a mechanism-(a) (reconstruct) result may NOT be read against control "
                f"{control.kind!r}/{control.ablation_mechanism!r} with {control.member_count} "
                "member(s). Under (a) an empty group already moves the residual by the whole "
                "reconstruction error, so this pairing would credit SAE fidelity to the group. "
                "REQUIRED: GroupSpec.reconstruction_control() at the same seed. (RULING_13 rules "
                "SUBTRACT the instrument; (a) is a once-per-configuration fidelity statistic, see "
                "measure_sae_fidelity_context.)"
            )


def measure_mechanism_gap(sae: Any, spec: GroupSpec, residual: torch.Tensor) -> dict[str, Any]:
    """Measure (a) and (b) on the same residual and report the gap.

    The closed form, from `decode(z) = z @ W_dec + b_dec`:

        delta_a - delta_b == decode(encode(h)) - h == -reconstruction_error

    independent of `alpha`, of the weights, and of which features are in
    the group. This function measures all three quantities separately and
    reports `closed_form_residual`, the disagreement between the measured
    gap and that identity. If that number is not ~0 then either `decode` is
    not affine on this SAE or one of the two mechanisms is wrong, and the
    caller should not proceed on either."""
    ablate_spec = spec if spec.kind == "ablate" else GroupSpec(
        kind="ablate",
        members=spec.members,
        alpha=spec.alpha,
        ablation_mechanism="subtract",
        positions=spec.positions,
        hook_name=spec.hook_name,
        label=spec.label,
    )
    resolved = resolve_group(sae, ablate_spec)
    with torch.no_grad():
        delta_a = ablate_reconstruct_delta(sae, resolved, residual)
        delta_b = ablate_subtract_delta(sae, resolved, residual)
        error = reconstruction_error(sae, residual)
        gap = delta_a - delta_b
        closed_form = -error
        discrepancy = (gap - closed_form).abs()
    return {
        "member_count": resolved.member_count,
        "alpha": float(ablate_spec.alpha),
        "delta_a_norm": float(delta_a.norm().item()),
        "delta_b_norm": float(delta_b.norm().item()),
        "gap_norm": float(gap.norm().item()),
        "reconstruction_error_norm": float(error.norm().item()),
        "residual_norm": float(residual.to(torch.float32).norm().item()),
        "closed_form_residual_max_abs": float(discrepancy.max().item()) if discrepancy.numel() else 0.0,
        "relative_gap": (
            float(gap.norm().item() / delta_b.norm().item()) if float(delta_b.norm().item()) > 0 else None
        ),
    }


# ---------------------------------------------------------------------------
# The hook.
# ---------------------------------------------------------------------------


class _PositionCounter:
    """Absolute sequence position reached so far across calls in one
    context (prefill, then one call per KV-cached decode step). Same
    mechanism as `interplab.interventions.hooks._PositionCounter`, kept
    local because this hook records positions and that one does not."""

    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0


def _positions_mask(
    counter: _PositionCounter,
    seq_len: int,
    batch_size: int,
    prompt_lengths: int | Sequence[int],
    device,
) -> torch.Tensor:
    start = counter.value
    absolute = torch.arange(start, start + seq_len, device=device)
    if isinstance(prompt_lengths, int):
        lengths = torch.full((batch_size,), prompt_lengths, dtype=torch.long, device=device)
    else:
        lengths = torch.as_tensor(list(prompt_lengths), dtype=torch.long, device=device)
        if int(lengths.shape[0]) != batch_size:
            raise InvalidGroupSpec(
                f"prompt_lengths has {int(lengths.shape[0])} entries but the batch is {batch_size}"
            )
    return absolute.unsqueeze(0) >= lengths.unsqueeze(1)


def build_group_hook(
    sae: Any,
    spec: GroupSpec,
    *,
    ledger: FiringLedger,
    prompt_lengths: int | Sequence[int] | None = None,
    verify_exact_delta: bool = True,
) -> tuple[Any, ResolvedGroup]:
    """Build the forward hook for one group intervention.

    Returns `(hook_fn, resolved)`. `kind='noop'` raises here rather than
    returning a passthrough: the control arm must register NO hook at all
    so its bit-identity is structural, and `attach_group_hook()` is where
    that decision lives.

    `verify_exact_delta` turns on the in-hook check that the amplify path's
    realised delta equals the precomputed `alpha * sum_f w_f * W_dec[f]`.
    It is on by default and costs one elementwise subtraction per call. It
    is not applied to the ablation paths, where the 'expected' delta is
    activation-dependent and recomputing it inside the hook would compare
    the hook against itself; those are checked in the test suite against an
    independent closed form instead."""
    if spec.kind == "noop":
        raise InvalidGroupSpec(
            "kind='noop' registers no hook -- call attach_group_hook(), which returns a null "
            "context, rather than asking for a passthrough hook that would only pretend to be one."
        )
    if spec.positions == "generated_only" and prompt_lengths is None:
        raise InvalidGroupSpec("prompt_lengths is required when positions='generated_only'")
    if spec.positions == "all" and prompt_lengths is not None:
        raise InvalidGroupSpec("prompt_lengths must be None when positions='all'")

    resolved = resolve_group(sae, spec)
    counter = _PositionCounter()
    is_identity = null_configuration_is_exact_identity(spec)
    amplify_delta32 = (
        resolved.expected_amplify_delta()
        if spec.kind == "amplify" and spec.dose_form == "additive"
        else None
    )

    def hook_fn(resid: torch.Tensor, hook: Any = None) -> torch.Tensor:
        if resid.ndim != 3:
            raise GroupInterventionError(
                f"expected a [batch, seq, d_model] residual at {resolved.hook_name}; got shape "
                f"{tuple(resid.shape)}"
            )
        batch, seq_len, d_model = resid.shape
        if d_model != resolved.d_in:
            raise GroupInterventionError(
                f"hook point {resolved.hook_name} carries d_model={d_model} but this SAE has "
                f"d_in={resolved.d_in} -- refusing to steer along directions of the wrong width."
            )
        call_index = len(ledger.records)
        classification: Literal["prefill", "decode"] = "prefill" if call_index == 0 else "decode"
        start = counter.value

        mask = None
        if spec.positions == "generated_only":
            mask = _positions_mask(counter, seq_len, batch, prompt_lengths, resid.device)
        counter.value = start + seq_len

        def record(
            modified: int,
            delta_norm: float,
            max_abs: float,
            absorbed: int = 0,
            requested_nonzero: int = 0,
        ) -> None:
            ledger.records.append(
                FiringRecord(
                    call_index=call_index,
                    call_classification=classification,
                    hook_name=str(getattr(hook, "name", resolved.hook_name) or resolved.hook_name),
                    tensor_shape=(batch, seq_len, d_model),
                    absolute_position_start=start,
                    absolute_position_end=start + seq_len,
                    positions_seen=batch * seq_len,
                    positions_modified=modified,
                    delta_norm=delta_norm,
                    residual_norm=float(resid.detach().to(torch.float32).norm().item()),
                    max_abs_delta=max_abs,
                    absorbed_element_count=absorbed,
                    requested_nonzero_element_count=requested_nonzero,
                    residual_dtype=str(resid.dtype),
                )
            )

        # An exact identity returns the INPUT OBJECT. `x + 0.0` is not
        # bit-identical for a -0.0 element, and a control arm that is only
        # nearly identical is not a control arm. The call is still recorded:
        # 'fired and was an exact identity' must stay distinguishable from
        # 'never fired'.
        if is_identity:
            record(0, 0.0, 0.0)
            return resid

        if mask is not None and not bool(mask.any()):
            record(0, 0.0, 0.0)
            return resid

        with torch.no_grad():
            if spec.kind == "amplify" and spec.dose_form == "clamp":
                delta32 = clamp_amplify_delta(sae, resolved, resid)
            elif spec.kind == "amplify":
                delta32 = amplify_delta32.expand(batch, seq_len, resolved.d_in)
            elif spec.ablation_mechanism == "subtract":
                delta32 = ablate_subtract_delta(sae, resolved, resid)
            else:
                delta32 = ablate_reconstruct_delta(sae, resolved, resid)
            delta = delta32.to(resid.dtype)
            steered = resid + delta
            # Structural selection, never a multiply-by-zero mask: 0 * NaN is
            # NaN, so a masked position's output must not be allowed to depend
            # on `steered` at all.
            result = torch.where(mask.unsqueeze(-1), steered, resid) if mask is not None else steered

            effective = (result - resid).to(torch.float32)
            modified_slots = int(mask.sum().item()) if mask is not None else batch * seq_len
            # The requested delta, masked exactly as the realised one was, so
            # the absorption census counts only elements the intervention was
            # actually asking to move.
            requested32 = delta32.expand(batch, seq_len, resolved.d_in)
            if mask is not None:
                requested32 = torch.where(
                    mask.unsqueeze(-1), requested32, torch.zeros((), dtype=requested32.dtype)
                )
            absorbed, requested_nonzero = measure_absorption(resid, result, requested32)
            record(
                modified=modified_slots,
                delta_norm=float(effective.norm().item()),
                max_abs=float(effective.abs().max().item()) if effective.numel() else 0.0,
                absorbed=absorbed,
                requested_nonzero=requested_nonzero,
            )

            if verify_exact_delta and amplify_delta32 is not None:
                # Checked at EVERY position, steered and unsteered alike. Under
                # `generated_only` the expected delta is the requested vector
                # where the mask is True and EXACTLY ZERO where it is False, so
                # a hook that leaked into the prefill fails here rather than
                # being excused as out of scope.
                #
                # ADDITIVE ONLY. A clamp delta is `target_f - a_f(h)`, so
                # recomputing it here would compare the hook against its own
                # encode -- a tautology. The clamp path is checked in the test
                # suite against an independent closed form instead.
                expected = amplify_delta32.expand(batch, seq_len, resolved.d_in)
                if mask is not None:
                    expected = torch.where(
                        mask.unsqueeze(-1), expected, torch.zeros((), dtype=expected.dtype)
                    )
                assert_exact_delta(
                    resid,
                    result,
                    expected,
                    context=f"{resolved.hook_name} call {call_index}",
                )
        return result

    return hook_fn, resolved


class _NullAttach:
    """The control arm's context manager: registers nothing."""

    def __init__(self, resolved: ResolvedGroup | None) -> None:
        self.resolved = resolved

    def __enter__(self) -> _NullAttach:
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        return False


def attach_group_hook(
    model: Any,
    sae: Any,
    spec: GroupSpec,
    *,
    ledger: FiringLedger,
    prompt_lengths: int | Sequence[int] | None = None,
    verify_exact_delta: bool = True,
):
    """Context manager that installs the group hook on a
    `transformer_lens.HookedTransformer` for its duration.

    `kind='noop'` installs NOTHING -- not even a passthrough -- so the
    control arm's bit-identity with an unhooked run is structural.
    `model.hooks(...)` is `finally`-guarded by transformer_lens itself, so
    the 'no hooks left behind' guarantee is inherited rather than
    reimplemented."""
    if spec.kind == "noop":
        return _NullAttach(None)
    hook_fn, resolved = build_group_hook(
        sae,
        spec,
        ledger=ledger,
        prompt_lengths=prompt_lengths,
        verify_exact_delta=verify_exact_delta,
    )
    hooks = getattr(model, "hooks", None)
    if not callable(hooks):
        raise GroupInterventionError(
            f"{type(model).__name__} has no `.hooks(fwd_hooks=...)`; for a raw HF model use "
            "attach_group_hook_raw_hf() instead of pretending this path works."
        )
    return hooks(fwd_hooks=[(resolved.hook_name, hook_fn)])


# ---------------------------------------------------------------------------
# The raw-HF path (Qwen3.5-27B).
#
# transformer_lens has no Qwen3.5 entry, so one of the two frozen final
# pairings has no `model.hooks(...)` at all and must be hooked with
# `register_forward_hook` on the decoder layer module directly.
#
# NOTHING BELOW IS INVENTED. The discovery runner already drives this path,
# and the intervention MUST hook the same tensor at the same point the
# scorer scored, or a feature index means different things in the two halves
# and no result is comparable. Reused, imported and never copied:
#
#   final_pairing_harness.resolve_qwen_text_decoder  -> hf_model.model
#   final_pairing_harness.get_qwen_decoder_layer     -> text_decoder.layers[L]
#   final_pairing_harness.register_qwen_raw_hook     -> the plain-tensor-
#       validating `register_forward_hook` wrapper, which REFUSES if the
#       layer returns a tuple instead of the resid-post tensor.
#
# VERIFIED ON THE BYTES of final_pairing_concept_discovery.py (read-only,
# not edited by this lane): all three Qwen scoring sites --
# `_qwen_max_activation_per_feature`, `encode_texts`, and the Qwen branch of
# `_pooled_residual_and_feature` -- capture from
# `backend._qwen_decoder_layer.register_forward_hook(_capture)` reading the
# module's `output` directly, and `_attached` registers the INTERVENTION on
# that same `backend._qwen_decoder_layer` via `register_qwen_raw_hook`. Same
# module object, same tensor. NO DISCREPANCY FOUND.
# `assert_hooks_the_scored_tensor()` re-checks that identity at runtime
# rather than leaving it to this comment.
# ---------------------------------------------------------------------------


def _import_harness() -> Any:
    """Import `final_pairing_harness` for the three raw-HF resolvers only.

    RAISES if unavailable. Re-deriving `hf_model.model.layers[L]` locally
    would be a second, independently-maintained opinion about where the
    residual stream lives -- which is exactly how an intervention ends up
    hooking a different tensor from the scorer while both look correct."""
    try:
        harness = _import_module_from_exact_file(
            "final_pairing_harness",
            SCRIPT_DIR.parent / "legacy" / "final_pairing_harness.py",
            why="re-deriving the decoder-layer path locally would be a second opinion about where "
            "the residual stream lives, which is how an intervention hooks a different tensor from "
            "the scorer while both look correct.",
        )
    except DeviceGateUnavailable as exc:
        raise GroupInterventionError(str(exc)) from exc
    for name in ("resolve_qwen_text_decoder", "get_qwen_decoder_layer", "register_qwen_raw_hook"):
        if not callable(getattr(harness, name, None)):
            raise GroupInterventionError(
                f"final_pairing_harness has no callable {name} -- the raw-HF contract this module "
                "reuses is not present; refusing to substitute a local reimplementation."
            )
    return harness


def resolve_raw_hf_decoder_layer(hf_model: Any, *, layer: int) -> Any:
    """The `nn.Module` whose forward output IS the residual stream the SAE
    was trained on, resolved exactly as the discovery scorer resolves it.

    `hf_model.model.layers[layer]`, via the harness resolvers, so this
    returns the SAME OBJECT `Backend._qwen_decoder_layer` holds."""
    harness = _import_harness()
    text_decoder = harness.resolve_qwen_text_decoder(hf_model)
    n_layers = len(text_decoder.layers)
    if not isinstance(layer, int) or isinstance(layer, bool):
        raise InvalidGroupSpec(f"layer must be an int; got {layer!r}")
    if not 0 <= layer < n_layers:
        raise InvalidGroupSpec(
            f"layer {layer} is out of range for this model's {n_layers} decoder layers -- refusing "
            "to hook a layer that does not exist, or to wrap a negative index into one that does."
        )
    return harness.get_qwen_decoder_layer(text_decoder, layer)


def assert_hooks_the_scored_tensor(decoder_layer: Any, hf_model: Any, *, layer: int) -> dict[str, str]:
    """RAISE unless the module this intervention will hook is IDENTICAL to
    the one the discovery scorer hooks for the same layer.

    Object identity (`is`), not name equality. If the intervention attached
    anywhere else, feature index f would name one direction during scoring
    and a different one during steering, every gate result would be
    incomparable with every intervention result, and nothing in either half
    would look wrong. Returns what it compared so a run can record it."""
    scorer_module = resolve_raw_hf_decoder_layer(hf_model, layer=layer)
    if decoder_layer is not scorer_module:
        raise GroupInterventionError(
            f"the module this intervention would hook ({type(decoder_layer).__name__} at "
            f"{id(decoder_layer):#x}) is NOT the module the discovery scorer hooks for layer "
            f"{layer} ({type(scorer_module).__name__} at {id(scorer_module):#x}) -- a feature index "
            "would mean a different direction in the two halves. Refusing."
        )
    return {
        "layer": str(layer),
        "module_type": type(decoder_layer).__name__,
        "resolver": "final_pairing_harness.resolve_qwen_text_decoder + get_qwen_decoder_layer",
        "identity": "is-identical-to-scorer-module",
    }


QWEN3_5_LAYER_OUTPUT_CONTRACT = """THE RAW-HF LAYER MUST RETURN THE PLAIN RESID-POST TENSOR.

MEASURED, on the installed transformers==5.12.1, by instantiating the REAL
classes at fixture size (no weights, no GPU) and reading their own source:

  - `transformers.models.qwen3_5.modeling_qwen3_5.Qwen3_5DecoderLayer.forward`
    is annotated `-> torch.FloatTensor` and ends in `return hidden_states`.
  - `Qwen3_5MoeDecoderLayer.forward` unpacks its MoE tuple internally
    (`if isinstance(hidden_states, tuple): hidden_states, _ = hidden_states`)
    and also ends in `return hidden_states`.
  - A real tiny `Qwen3_5ForCausalLM` was generated from, with a forward hook
    on both a `linear_attention` and a `full_attention` layer: every
    invocation delivered a plain `torch.Tensor`.

ARGUED, NOT PROVEN HERE: that Tamia's transformers==5.14.1 is the same. This
machine has 5.12.1 and there is no network; `final_pairing_harness`'s author
records having read the public v5.14.1 source, and that reading is not
re-verified by this module.

WHY A TUPLE IS REFUSED AND NOT UNWRAPPED. It is not that unwrapping is hard.
It is that THE SCORER HAS THE SAME ASSUMPTION AND IS IN ANOTHER LANE'S FILE.
All three Qwen capture sites in `final_pairing_concept_discovery.py` do
`captured.append(output.detach())` on the raw hook `output`; on a tuple that
raises `AttributeError` before any feature is scored. If this module taught
ITSELF to unwrap element 0 and the scorer still could not, the intervention
would steer a tensor the scorer never scored -- exactly the divergence
`assert_hooks_the_scored_tensor()` exists to prevent, and a divergence with
no wrong-looking half. Deciding the unwrap convention is therefore a
CROSS-LANE change to the shared `register_qwen_raw_hook` and to those three
capture sites, not a local fix, and this lane does not make it unilaterally.

WHAT THIS MODULE DOES INSTEAD. `probe_raw_hf_layer_output_contract()` runs a
ONE-TOKEN forward with a capture-only hook -- no intervention, nothing
generated, nothing scored -- and refuses there if the output is not a plain
tensor. `RawHfBackend` runs it at CONSTRUCTION, so on the cluster the refusal
arrives seconds after the model loads, before any prompt, any generation and
any GPU hours."""


def probe_raw_hf_layer_output_contract(
    hf_model: Any,
    decoder_layer: Any,
    *,
    expected_d_model: int | None = None,
    probe_token_id: int | None = None,
) -> dict[str, Any]:
    """Determine, EMPIRICALLY AND CHEAPLY, what the hooked decoder layer
    returns -- then refuse unless it is the plain resid-post tensor.

    One forward over ONE token with a capture-only hook: no intervention is
    installed, nothing is generated and nothing is scored, so this costs a
    single token of compute and cannot contaminate a result. It exists so
    that a layer whose output shape this harness was never verified against
    is caught at CONFIGURATION TIME rather than mid-generation, and so that
    the operator reading the failure is told it is a harness/transformers
    contract mismatch and NOT a model failure.

    Returns what it measured (type name, shape, dtype, device, and whether
    the discovery scorer's own `output.detach()` idiom works on it) so a run
    can record the contract it verified. See
    `QWEN3_5_LAYER_OUTPUT_CONTRACT`."""
    if not callable(getattr(decoder_layer, "register_forward_hook", None)):
        raise GroupInterventionError(
            f"{type(decoder_layer).__name__} has no register_forward_hook -- this is not an "
            "nn.Module decoder layer, so its output contract cannot be probed."
        )
    seen: list[Any] = []

    def _capture(_module: Any, _args: Any, output: Any) -> None:
        seen.append(output)

    device = next((p.device for p in getattr(hf_model, "parameters", lambda: [])()), None)
    token = probe_token_id
    if token is None:
        config = getattr(hf_model, "config", None)
        token = getattr(config, "bos_token_id", None)
        if not isinstance(token, int):
            token = 0
    input_ids = torch.tensor([[int(token)]], dtype=torch.long)
    if device is not None:
        input_ids = input_ids.to(device)

    handle = decoder_layer.register_forward_hook(_capture)
    try:
        with torch.no_grad():
            hf_model(input_ids=input_ids)
    finally:
        handle.remove()

    if not seen:
        raise RawHfLayerContractMismatch(
            f"a one-token probe forward never reached {type(decoder_layer).__name__} -- the layer "
            "this intervention would hook is not on the model's forward path, so the hook would "
            "never fire and the arm would report a null it never earned. Refusing."
        )
    output = seen[-1]
    if not isinstance(output, torch.Tensor):
        extra = ""
        if isinstance(output, tuple):
            shapes = [tuple(v.shape) if isinstance(v, torch.Tensor) else type(v).__name__ for v in output]
            extra = (
                f" The tuple has {len(output)} element(s) with shapes/types {shapes}. Element 0 is "
                "NOT unwrapped automatically here, on purpose -- see below."
            )
        raise RawHfLayerContractMismatch(
            f"{type(decoder_layer).__name__} returned {type(output).__name__}, not the plain "
            f"resid-post torch.Tensor this raw-HF path is built on.{extra}\n\n"
            "THIS IS A HARNESS/TRANSFORMERS CONTRACT MISMATCH, NOT A MODEL FAILURE AND NOT A "
            "SCIENTIFIC RESULT. The model loaded fine; what differs is the decoder layer's return "
            "convention between the transformers this harness was verified against "
            "(5.12.1 here, 5.14.1 read by final_pairing_harness) and the one installed where this "
            "ran. Nothing has been generated, scored or spent at this point: the probe is a "
            "one-token forward that runs before any prompt.\n\n"
            "DO NOT PATCH ONLY THE INTERVENTION. The discovery scorer's three Qwen capture sites "
            "in final_pairing_concept_discovery.py do `output.detach()` on this same raw hook "
            "output and would fail on this same object, so a fix that unwraps here alone would "
            "make the intervention steer a tensor the scorer never scored -- the one divergence "
            "assert_hooks_the_scored_tensor() exists to prevent. The unwrap convention has to be "
            "decided once, in the shared final_pairing_harness.register_qwen_raw_hook and in those "
            "capture sites together.\n\n"
            f"{QWEN3_5_LAYER_OUTPUT_CONTRACT}"
        )
    if output.ndim != 3:
        raise RawHfLayerContractMismatch(
            f"{type(decoder_layer).__name__} returned a tensor of shape {tuple(output.shape)}; this "
            "path requires [batch, seq, d_model], which is what the SAE was trained on and what "
            "the scorer captures. Refusing to reshape a tensor whose layout was never verified."
        )
    measured_d_model = int(output.shape[-1])
    if expected_d_model is not None and measured_d_model != int(expected_d_model):
        raise RawHfLayerContractMismatch(
            f"{type(decoder_layer).__name__} carries d_model={measured_d_model} but the SAE has "
            f"d_in={int(expected_d_model)} -- refusing to steer along directions of the wrong "
            "width, and refusing to discover that mid-generation."
        )
    # The scorer's own idiom, exercised on the real object rather than assumed
    # to work: if `.detach()` fails here it fails in census too.
    scorer_idiom_ok = callable(getattr(output, "detach", None))
    return {
        "layer_type": type(decoder_layer).__name__,
        "output_type": type(output).__name__,
        "output_shape": list(output.shape),
        "output_dtype": str(output.dtype),
        "output_device": str(output.device),
        "probe_token_id": int(token),
        "scorer_capture_idiom_ok": bool(scorer_idiom_ok),
        "contract": "plain-resid-post-tensor",
    }


class _RawHfAttach:
    """Context manager over `register_forward_hook`.

    `torch`'s handle has no `finally` guarantee of its own, so this supplies
    the one `HookedTransformer.hooks(...)` gives the other path for free --
    a hook left behind on a decoder layer would silently steer the NEXT
    arm, including the control."""

    def __init__(self, decoder_layer: Any, hook_fn: Any, harness: Any) -> None:
        self._decoder_layer = decoder_layer
        self._hook_fn = hook_fn
        self._harness = harness
        self._handle: Any = None

    def __enter__(self) -> _RawHfAttach:
        self._handle = self._harness.register_qwen_raw_hook(self._decoder_layer, self._hook_fn)
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        if self._handle is not None:
            self._handle.remove()
            self._handle = None
        return False


def attach_group_hook_raw_hf(
    decoder_layer: Any,
    sae: Any,
    spec: GroupSpec,
    *,
    ledger: FiringLedger,
    prompt_lengths: int | Sequence[int] | None = None,
    verify_exact_delta: bool = True,
    hf_model: Any = None,
    layer: int | None = None,
):
    """Install the group hook on a RAW HF decoder layer for the duration.

    Same contract as `attach_group_hook`: `kind='noop'` registers nothing,
    every other kind registers exactly one hook and fills `ledger`. The
    firing ledger, the exact-delta check, the absorption census, the
    membership refusals and both ablation mechanisms are the SAME code --
    `build_group_hook` is shared, not duplicated, so the two backends
    cannot drift apart in what they compute.

    Pass `hf_model` and `layer` to have `assert_hooks_the_scored_tensor()`
    run first. That is optional only because a caller may already hold the
    module from `Backend._qwen_decoder_layer`; when both are available the
    check is cheap and this module runs it."""
    if spec.kind == "noop":
        return _NullAttach(None)
    if hf_model is not None and layer is not None:
        assert_hooks_the_scored_tensor(decoder_layer, hf_model, layer=layer)
    if not callable(getattr(decoder_layer, "register_forward_hook", None)):
        raise GroupInterventionError(
            f"{type(decoder_layer).__name__} has no register_forward_hook -- this is not an "
            "nn.Module decoder layer. Resolve it with resolve_raw_hf_decoder_layer() rather than "
            "passing the whole model."
        )
    harness = _import_harness()
    hook_fn, _resolved = build_group_hook(
        sae,
        spec,
        ledger=ledger,
        prompt_lengths=prompt_lengths,
        verify_exact_delta=verify_exact_delta,
    )
    return _RawHfAttach(decoder_layer, hook_fn, harness)


# ---------------------------------------------------------------------------
# Device gate.
# ---------------------------------------------------------------------------


def _import_module_from_exact_file(module_name: str, expected_file: Path, *, why: str) -> Any:
    """Import `module_name` and REFUSE unless it came from `expected_file`.

    THIS EXISTS BECAUSE OF A REAL DEFECT THIS MODULE INTRODUCED AND ITS OWN
    TEST SUITE CAUGHT. `scripts/legacy/final_pairing_concept_discovery.py`
    is a 23-line compatibility STUB that forwards to the real runner and
    defines none of its functions. Adding `scripts/legacy` to `sys.path`
    for the raw-HF resolvers made `import final_pairing_concept_discovery`
    resolve to that stub, and the device gate vanished -- a helper that is
    imported, present by name, and empty of the thing it was imported for.
    Exactly this module's named defect class, reached through `sys.path`
    instead of through a hook.

    So the file a module was loaded FROM is checked, an already-cached
    wrong module is evicted rather than accepted, and the search path is
    ordered so this directory wins. Name equality is not identity."""
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
        raise DeviceGateUnavailable(
            f"could not import {module_name} from {resolved_expected} ({type(exc).__name__}: "
            f"{exc}). REFUSING to continue: {why}"
        ) from exc
    actual_file = getattr(module, "__file__", None)
    if actual_file is None or Path(actual_file).resolve() != resolved_expected:
        raise DeviceGateUnavailable(
            f"{module_name} resolved to {actual_file} but this module requires "
            f"{resolved_expected} -- a same-named module on sys.path shadowed it. Refusing to use "
            f"it: {why}"
        )
    return module


def _import_discovery_module() -> Any:
    """Import `final_pairing_concept_discovery` for its device gate ONLY.

    That file belongs to another lane and is never edited from here. No git
    call is involved -- this is an ordinary file import -- so the cluster's
    tarball-extract-with-no-.git shape (where `git show` exits 128) does not
    reach this path. Loaded through the file-identity check above, because
    a same-named compatibility stub really does exist in `scripts/legacy`."""
    return _import_module_from_exact_file(
        "final_pairing_concept_discovery",
        SCRIPT_DIR / "final_pairing_concept_discovery.py",
        why="skipping the shared device gate is how job 415590 forwarded a CPU model against "
        "cuda:0 input_ids one minute into a six-hour allocation.",
    )


def assert_devices_before_forward(*, device: str, **objects: Any) -> dict[str, str]:
    """Run the shared device gate before this harness's first forward.

    Wraps `final_pairing_concept_discovery.assert_load_devices_agree`
    (imported, not copied). Returns the MEASURED placement per object so it
    can be recorded in provenance. If the helper is missing this RAISES:
    a device gate that quietly declines to run reports the same 'fine' as
    one that ran and passed."""
    discovery = _import_discovery_module()
    gate = getattr(discovery, "assert_load_devices_agree", None)
    if not callable(gate):
        raise DeviceGateUnavailable(
            "final_pairing_concept_discovery has no callable assert_load_devices_agree -- refusing "
            "to run a forward with no device gate at all."
        )
    return gate(device=device, **objects)


# ---------------------------------------------------------------------------
# Settings-digest containment (RULING_16). Every record `run_arm` produces
# carries this, and `control_generation_payload.assert_settings_digest_bound`
# is THIS function, not a second copy of a hex-shape check that could drift
# from it -- the containment is one piece of code, not an agreement between
# two.
# ---------------------------------------------------------------------------

_PLACEHOLDER_SETTINGS_DIGESTS = frozenset({"0" * 64, "f" * 64, "deadbeef" * 8})


def assert_settings_digest_bound(digest: Any) -> str:
    """REFUSE an absent, malformed or placeholder `generation_settings_digest`.

    The placeholder set includes the calibration lane's own synthetic test
    constant, because a test double that escaped into a real record would
    satisfy every hex check and bind nothing."""
    text = str(digest or "").strip().lower()
    if not text:
        raise SettingsDigestUnbound(
            "generation_settings_digest is empty. RULING_16 makes this the containment for a lane "
            "holding both the control arm and the intervened arm; an empty value reads to a later "
            "reader as NOT CHECKED."
        )
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SettingsDigestUnbound(
            f"generation_settings_digest={digest!r} is not 64 lowercase hex, which is what "
            "causal_calibration.PinnedCalibration requires."
        )
    if text in _PLACEHOLDER_SETTINGS_DIGESTS:
        raise SettingsDigestUnbound(
            f"generation_settings_digest={text!r} is a PLACEHOLDER. A record that looks bound and "
            "is not is worse than one that admits it is not."
        )
    return text


# ---------------------------------------------------------------------------
# Measurement harness.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptResult:
    """One prompt, one arm."""

    prompt: str
    prompt_token_count: int
    generated_token_count: int
    generated_token_ids: tuple[int, ...]
    full_text: str
    generated_text: str
    per_token_logprob: tuple[float, ...] | None
    sum_logprob: float | None
    firing: dict[str, Any]
    firing_expectation: dict[str, Any]
    #: RULING_16's containment, REQUIRED: proves this record ran under the
    #: same settings as its paired arm rather than trusting that it did.
    #: `run_arm` validates it with `assert_settings_digest_bound` before any
    #: forward pass and stamps the SAME bound value onto every record it
    #: returns.
    generation_settings_digest: str
    intervention_state: InterventionState = "APPLIED"
    exact_identity_to_control: bool | None = None

    @property
    def outcome_is_readable_as_a_result(self) -> bool:
        """False for CONTROL, NOT_EXERCISED and FIRED_BUT_INERT.

        VOID IS NOT A NULL. An unchanged continuation from an arm where no
        perturbation reached the model says nothing about the group, and a
        reader who cannot tell the two apart will read it as evidence of
        absence."""
        return self.intervention_state == "APPLIED"

    def to_dict(self) -> dict[str, Any]:
        data = {
            "prompt": self.prompt,
            "prompt_token_count": self.prompt_token_count,
            "generated_token_count": self.generated_token_count,
            "generated_token_ids": list(self.generated_token_ids),
            "full_text": self.full_text,
            "generated_text": self.generated_text,
            "per_token_logprob": list(self.per_token_logprob) if self.per_token_logprob else None,
            "sum_logprob": self.sum_logprob,
            "firing": self.firing,
            "firing_expectation": self.firing_expectation,
            "generation_settings_digest": self.generation_settings_digest,
            "intervention_state": self.intervention_state,
            "intervention_state_meaning": INTERVENTION_STATE_MEANINGS[self.intervention_state],
            "outcome_is_readable_as_a_result": self.outcome_is_readable_as_a_result,
        }
        if self.exact_identity_to_control is not None:
            data["exact_identity_to_control"] = self.exact_identity_to_control
        return data


@dataclass(frozen=True)
class ArmResult:
    """One intervention applied across a whole prompt set."""

    spec: dict[str, Any]
    results: tuple[PromptResult, ...]
    device_placement: dict[str, str]
    null_configuration_is_exact_identity: bool

    @property
    def intervention_states(self) -> tuple[InterventionState, ...]:
        return tuple(r.intervention_state for r in self.results)

    @property
    def void_prompt_count(self) -> int:
        """Prompts where NO perturbation reached the model. Surfaced at the
        arm level so it cannot be missed by a reader who only reads
        summaries."""
        return sum(
            1 for r in self.results if r.intervention_state in ("NOT_EXERCISED", "FIRED_BUT_INERT")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec,
            "results": [r.to_dict() for r in self.results],
            "device_placement": self.device_placement,
            "null_configuration_is_exact_identity": self.null_configuration_is_exact_identity,
            "intervention_states": list(self.intervention_states),
            "void_prompt_count": self.void_prompt_count,
        }


def _generated_token_logprobs(
    backend: Any,
    sae: Any,
    spec: GroupSpec,
    tokens: torch.Tensor,
    prompt_token_count: int,
    *,
    verify_exact_delta: bool,
) -> tuple[tuple[float, ...], dict[str, Any]]:
    """Teacher-forced log-probability of each generated token UNDER THE
    SAME INTERVENTION.

    A separate ledger from generation's: this is one extra forward over the
    whole sequence, so it fires the hook exactly once, and conflating the
    two counts would make both unassertable."""
    ledger = FiringLedger()
    prompt_lengths = prompt_token_count if spec.positions == "generated_only" else None
    with torch.no_grad(), backend.attach(
        sae,
        spec,
        ledger=ledger,
        prompt_lengths=prompt_lengths,
        verify_exact_delta=verify_exact_delta,
    ):
        logits = backend.forward_logits(tokens)
    logprobs = torch.log_softmax(logits.to(torch.float32), dim=-1)
    values: list[float] = []
    for position in range(prompt_token_count, int(tokens.shape[1])):
        token_id = int(tokens[0, position].item())
        values.append(float(logprobs[0, position - 1, token_id].item()))
    if spec.kind != "noop":
        assert_fired_as_expected(
            ledger,
            FiringExpectation(
                call_count=1,
                positions_modified=None,
                require_nonzero_delta=False,
            ),
            context="teacher-forced scoring pass",
        )
    return tuple(values), ledger.summary()


def resolve_backend(model: Any, **kwargs: Any) -> Any:
    """Accept either backend and return the adapter for it.

    A `Backend` instance passes through. Anything with `.hooks(...)` is a
    `HookedTransformer`. Anything else RAISES rather than being guessed at:
    a raw HF model needs a tokenizer and a layer index that cannot be
    inferred, and silently guessing one would hook the wrong tensor."""
    if isinstance(model, (HookedTransformerBackend, RawHfBackend)):
        return model
    if callable(getattr(model, "hooks", None)):
        return HookedTransformerBackend(model, **kwargs)
    raise GroupInterventionError(
        f"{type(model).__name__} has no `.hooks(fwd_hooks=...)` and is not a resolved backend. For "
        "the raw-HF (Qwen3.5) pairing build a RawHfBackend explicitly -- it needs the tokenizer and "
        "the layer index, neither of which can be inferred from the model alone, and guessing "
        "either would hook a tensor the scorer never scored."
    )


class HookedTransformerBackend:
    """Adapter over `transformer_lens.HookedTransformer` (the Gemma pairing)."""

    kind = "hooked_transformer"

    def __init__(self, model: Any) -> None:
        self.model = model

    @property
    def device(self) -> str:
        return str(next((p.device for p in self.model.parameters()), torch.device("cpu")))

    def device_objects(self) -> dict[str, Any]:
        return {"model": self.model}

    def describe(self) -> dict[str, str]:
        return {"backend": self.kind, "model_type": type(self.model).__name__}

    def to_tokens(self, prompt: str) -> torch.Tensor:
        return self.model.to_tokens([prompt])

    def to_string(self, ids: torch.Tensor) -> str:
        return self.model.to_string(ids)

    def generate(
        self, tokens: torch.Tensor, *, max_new_tokens: int, do_sample: bool,
        temperature: float, stop_at_eos: bool,
    ) -> torch.Tensor:
        return self.model.generate(
            tokens, max_new_tokens=max_new_tokens, do_sample=do_sample,
            temperature=temperature, stop_at_eos=stop_at_eos, verbose=False,
        )

    def forward_logits(self, tokens: torch.Tensor) -> torch.Tensor:
        return self.model(tokens)

    def attach(self, sae, spec, *, ledger, prompt_lengths, verify_exact_delta):
        return attach_group_hook(
            self.model, sae, spec, ledger=ledger, prompt_lengths=prompt_lengths,
            verify_exact_delta=verify_exact_delta,
        )


class RawHfBackend:
    """Adapter over a raw `AutoModelForCausalLM` hooked with
    `register_forward_hook` (the Qwen3.5-27B pairing, which transformer_lens
    cannot load).

    THE INPUT DEVICE IS DERIVED FROM THE MODEL, never passed in. Job 415590
    died because a preflight forwarded a CPU model against `cuda:0`
    input_ids; `HookedTransformer.from_pretrained(hf_model=..., device=...)`
    moves only the HookedTransformer and leaves the raw `AutoModel` where it
    was. Reading the device off the module removes the second opinion that
    caused it."""

    kind = "raw_hf"

    def __init__(
        self,
        hf_model: Any,
        tokenizer: Any,
        *,
        layer: int,
        probe_output_contract: bool = True,
        expected_d_model: int | None = None,
    ) -> None:
        self.model = hf_model
        self.tokenizer = tokenizer
        self.layer = int(layer)
        self.decoder_layer = resolve_raw_hf_decoder_layer(hf_model, layer=self.layer)
        # Runtime proof, not a comment, that this is the scorer's own module.
        self.hook_identity = assert_hooks_the_scored_tensor(
            self.decoder_layer, hf_model, layer=self.layer
        )
        # AT CONSTRUCTION, ON ONE TOKEN. `register_qwen_raw_hook` also refuses a
        # non-tensor output, but it does so from inside the FIRST INTERVENED
        # FORWARD -- after the model is loaded, the arm is configured and a
        # prompt is in flight. Probing here moves that refusal to configuration
        # time for the cost of a single token, which is what "refuse before
        # spending the allocation" has to mean on a 27B model.
        self.output_contract: dict[str, Any] | None = None
        if probe_output_contract:
            self.output_contract = probe_raw_hf_layer_output_contract(
                hf_model, self.decoder_layer, expected_d_model=expected_d_model
            )

    @property
    def device(self) -> str:
        discovery = _import_discovery_module()
        resolved = discovery.resolve_module_device(self.model)
        return str(resolved if resolved is not None else torch.device("cpu"))

    def device_objects(self) -> dict[str, Any]:
        # The decoder layer is asserted SEPARATELY from the model: under a
        # device_map shard they can differ, and the layer is the one the hook
        # actually runs on.
        return {"model": self.model, "decoder_layer": self.decoder_layer}

    def describe(self) -> dict[str, str]:
        described = {
            "backend": self.kind,
            "model_type": type(self.model).__name__,
            **self.hook_identity,
        }
        if self.output_contract is not None:
            described["layer_output_contract"] = json.dumps(
                self.output_contract, sort_keys=True
            )
        return described

    def to_tokens(self, prompt: str) -> torch.Tensor:
        encoded = self.tokenizer(prompt, return_tensors="pt")
        return encoded["input_ids"].to(self.device)

    def to_string(self, ids: torch.Tensor) -> str:
        return self.tokenizer.decode(ids, skip_special_tokens=False)

    def generate(
        self, tokens: torch.Tensor, *, max_new_tokens: int, do_sample: bool,
        temperature: float, stop_at_eos: bool,
    ) -> torch.Tensor:
        kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "attention_mask": torch.ones_like(tokens),
        }
        if do_sample:
            kwargs["temperature"] = temperature
        if not stop_at_eos:
            # `min_new_tokens` is HF's own supported way to say "do not stop
            # early", which is what transformer_lens's stop_at_eos=False
            # means. The firing expectation is still derived from the
            # RETURNED tensor either way, so an early stop stays exact.
            kwargs["min_new_tokens"] = max_new_tokens
        if getattr(self.tokenizer, "pad_token_id", None) is not None:
            kwargs["pad_token_id"] = self.tokenizer.pad_token_id
        with torch.no_grad():
            return self.model.generate(tokens, **kwargs)

    def forward_logits(self, tokens: torch.Tensor) -> torch.Tensor:
        return self.model(input_ids=tokens).logits

    @property
    def hook_label(self) -> str:
        """What the ledger should call this hook point.

        NOT the SAE's own `cfg.metadata.hook_name`: that is a
        TransformerLens-style string (`blocks.N.hook_resid_post`) naming a
        hook point this backend does not have. Recording it here would put a
        hook name in the provenance that never existed in the process, which
        is a small lie of exactly the kind that makes a later audit
        impossible. The caller's own `spec.hook_name` still wins if set."""
        return f"raw_hf.model.layers.{self.layer}"

    def attach(self, sae, spec, *, ledger, prompt_lengths, verify_exact_delta):
        if spec.hook_name is None and spec.kind != "noop":
            spec = replace(spec, hook_name=self.hook_label)
        return attach_group_hook_raw_hf(
            self.decoder_layer, sae, spec, ledger=ledger, prompt_lengths=prompt_lengths,
            verify_exact_delta=verify_exact_delta,
        )


def run_arm(
    model: Any,
    sae: Any,
    spec: GroupSpec,
    prompts: Sequence[str],
    *,
    max_new_tokens: int,
    seed: int,
    generation_settings_digest: str,
    device: str | None = None,
    stop_at_eos: bool = False,
    do_sample: bool = False,
    temperature: float = 1.0,
    want_logprobs: bool = True,
    verify_exact_delta: bool = True,
    require_nonzero_delta: bool | None = None,
) -> ArmResult:
    """Generate under one intervention and measure it.

    ONE PROMPT PER `generate()` CALL, deliberately. A padded batch makes
    every per-row prompt length different, which makes the exact
    `positions_modified` expectation a function of the padding scheme; the
    resulting assertion would be the kind that is technically present and
    practically unfalsifiable. Batching is listed in
    `UNEXERCISED_WITHOUT_GPU` as absent rather than implemented loosely.

    The seed is reset before EVERY generation, so a control arm and a
    treatment arm run at the same seed are paired in the sense the frozen
    control-arm rule requires.

    `require_nonzero_delta` defaults to "whatever this spec should do":
    True for a real intervention, False for `noop` and for any null
    configuration that is an exact identity by construction.

    `generation_settings_digest` is REQUIRED, with no default: this is the
    ONE function both the control arm (`control_generation_payload.py`) and
    the intervened arm call to generate, so validating it HERE -- before any
    forward pass -- is what makes the requirement structural rather than a
    convention each caller has to remember. `assert_settings_digest_bound`
    REFUSES an absent, malformed or placeholder value, the same way a zero
    dose or a zero weight refuses, and the bound value is stamped onto every
    `PromptResult` this call returns."""
    if max_new_tokens < 1:
        raise ValueError(f"max_new_tokens must be >= 1; got {max_new_tokens}")
    bound_digest = assert_settings_digest_bound(generation_settings_digest)

    backend = resolve_backend(model)
    is_identity = null_configuration_is_exact_identity(spec)
    if require_nonzero_delta is None:
        require_nonzero_delta = not is_identity

    resolved_device = device or backend.device
    placement = assert_devices_before_forward(
        device=resolved_device, sae=sae, **backend.device_objects()
    )

    results: list[PromptResult] = []
    for prompt in prompts:
        tokens = backend.to_tokens(prompt)
        prompt_token_count = int(tokens.shape[1])
        ledger = FiringLedger()
        prompt_lengths = prompt_token_count if spec.positions == "generated_only" else None

        torch.manual_seed(seed)
        with backend.attach(
            sae,
            spec,
            ledger=ledger,
            prompt_lengths=prompt_lengths,
            verify_exact_delta=verify_exact_delta,
        ):
            output = backend.generate(
                tokens,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=temperature,
                stop_at_eos=stop_at_eos,
            )

        generated_token_count = int(output.shape[1]) - prompt_token_count
        if generated_token_count < 1:
            raise GroupInterventionError(
                f"generation returned {generated_token_count} new token(s) for prompt {prompt!r}; "
                "nothing can be measured from that and it is not a valid arm."
            )
        expectation = expected_generation_firing(
            prompt_token_count=prompt_token_count,
            generated_token_count=generated_token_count,
            positions=spec.positions,
            batch_size=1,
            require_nonzero_delta=require_nonzero_delta,
        )
        if spec.kind == "noop":
            # The control registers no hook, so the honest expectation is
            # zero calls -- and it is still ASSERTED, because a control that
            # accidentally carried a hook would poison the pairing.
            expectation = FiringExpectation(
                call_count=0, positions_modified=0, require_nonzero_delta=False
            )
        elif is_identity:
            # A null configuration (alpha == 0, or an empty group) DOES
            # register a hook and DOES fire it, and returns the input object
            # untouched. So the expectation is the full call count with
            # exactly zero positions modified -- a strictly stronger pair of
            # claims than the general case, not a relaxation of it.
            expectation = FiringExpectation(
                call_count=expectation.call_count,
                positions_modified=0,
                require_nonzero_delta=False,
            )
        firing = assert_fired_as_expected(ledger, expectation, context=f"generate({prompt!r})")

        logprobs: tuple[float, ...] | None = None
        if want_logprobs:
            logprobs, _ = _generated_token_logprobs(
                backend,
                sae,
                spec,
                output,
                prompt_token_count,
                verify_exact_delta=verify_exact_delta,
            )

        full_text = backend.to_string(output[0])
        prompt_text = backend.to_string(output[0, :prompt_token_count])
        results.append(
            PromptResult(
                prompt=prompt,
                prompt_token_count=prompt_token_count,
                generated_token_count=generated_token_count,
                generated_token_ids=tuple(int(t) for t in output[0, prompt_token_count:].tolist()),
                full_text=full_text,
                generated_text=full_text[len(prompt_text):],
                per_token_logprob=logprobs,
                sum_logprob=float(sum(logprobs)) if logprobs else None,
                firing=firing,
                firing_expectation=expectation.to_dict(),
                generation_settings_digest=bound_digest,
                intervention_state=classify_intervention_state(spec, ledger),
            )
        )

    return ArmResult(
        spec=spec.to_dict(),
        results=tuple(results),
        device_placement=placement,
        null_configuration_is_exact_identity=is_identity,
    )


@dataclass(frozen=True)
class GroupEffectMeasurement:
    """A treatment arm and its paired same-seed control."""

    control: ArmResult
    treatment: ArmResult
    seed: int
    per_prompt: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "control": self.control.to_dict(),
            "treatment": self.treatment.to_dict(),
            "per_prompt": list(self.per_prompt),
        }

    @property
    def any_continuation_changed(self) -> bool:
        return any(not row["token_ids_identical"] for row in self.per_prompt)


def measure_group_effect(
    model: Any,
    sae: Any,
    spec: GroupSpec,
    prompts: Sequence[str],
    *,
    max_new_tokens: int,
    seed: int,
    control_spec: GroupSpec | None = None,
    **arm_kwargs: Any,
) -> GroupEffectMeasurement:
    """Run `spec` and its paired same-seed control and report both.

    `control_spec` defaults to `GroupSpec.noop()`. Under ablation mechanism
    (a) the caller should usually pass `GroupSpec.reconstruction_control()`
    instead: a noop control there leaves the whole reconstruction error
    inside the measured effect, and the difference is not small.

    This function reports MEASUREMENTS. It computes no verdict, compares
    nothing to a threshold, and in particular never converts an unchanged
    continuation into a statement about necessity -- see
    `NULL_ABLATION_FROZEN_PHRASING`."""
    control = control_spec if control_spec is not None else GroupSpec.noop(hook_name=spec.hook_name)
    # RULING_13 Q3.9: an (a) result against an unhooked control is REFUSED,
    # not caveated. Checked BEFORE any generation, so the refusal costs
    # nothing and cannot arrive after a result exists to be attached to.
    assert_control_is_admissible(spec, control)
    # Resolved ONCE and shared by both arms: a backend rebuilt per arm could
    # resolve a different decoder layer for the control than for the
    # treatment, which is the one way a paired comparison can be unpaired
    # without either arm looking wrong.
    backend = resolve_backend(model)
    control_arm = run_arm(
        backend, sae, control, prompts, max_new_tokens=max_new_tokens, seed=seed, **arm_kwargs
    )
    treatment_arm = run_arm(
        backend, sae, spec, prompts, max_new_tokens=max_new_tokens, seed=seed, **arm_kwargs
    )

    rows: list[dict[str, Any]] = []
    for control_row, treatment_row in zip(control_arm.results, treatment_arm.results, strict=True):
        identical = control_row.generated_token_ids == treatment_row.generated_token_ids
        first_divergence: int | None = None
        for position, (a, b) in enumerate(
            zip(control_row.generated_token_ids, treatment_row.generated_token_ids, strict=False)
        ):
            if a != b:
                first_divergence = position
                break
        if first_divergence is None and not identical:
            first_divergence = min(
                len(control_row.generated_token_ids), len(treatment_row.generated_token_ids)
            )
        delta_logprob = None
        if control_row.sum_logprob is not None and treatment_row.sum_logprob is not None:
            delta_logprob = treatment_row.sum_logprob - control_row.sum_logprob
        rows.append(
            {
                "prompt": control_row.prompt,
                "token_ids_identical": identical,
                "first_divergent_generated_position": first_divergence,
                "control_generated_text": control_row.generated_text,
                "treatment_generated_text": treatment_row.generated_text,
                "control_sum_logprob": control_row.sum_logprob,
                "treatment_sum_logprob": treatment_row.sum_logprob,
                "delta_sum_logprob_of_control_continuation": delta_logprob,
                "treatment_total_delta_norm": treatment_row.firing["total_delta_norm"],
                "treatment_hook_call_count": treatment_row.firing["call_count"],
                "treatment_positions_modified": treatment_row.firing["positions_modified"],
                # Carried up to the top level on purpose: a bfloat16 steering
                # result whose absorbed fraction is not reported has not been
                # checked, and a reader should not have to dig for it.
                "treatment_absorbed_fraction": treatment_row.firing["absorbed_fraction"],
                "treatment_residual_dtypes": treatment_row.firing["residual_dtypes"],
                # VOID IS NOT A NULL. `token_ids_identical` above is exactly
                # the field a reader would turn into "the concept was not
                # steerable", so the state that makes it meaningless travels
                # in the same row rather than in a summary elsewhere.
                "treatment_intervention_state": treatment_row.intervention_state,
                "outcome_is_readable_as_a_result": treatment_row.outcome_is_readable_as_a_result,
            }
        )

    return GroupEffectMeasurement(
        control=control_arm, treatment=treatment_arm, seed=seed, per_prompt=tuple(rows)
    )


def leave_one_out_specs(spec: GroupSpec) -> tuple[GroupSpec, ...]:
    """The k leave-one-out arms of `joint_intervention_lane.json` RULING_4
    stage 3, one per member, in member order.

    Building the arms is all this does. Whether removing a member
    "materially degrades" the effect is a judged comparison against a
    threshold this module does not own and does not invent."""
    return tuple(spec.without(index) for index in spec.feature_indices)


# ---------------------------------------------------------------------------
# Self-check. Control-first: the refusals run and print BEFORE any success.
# ---------------------------------------------------------------------------


class _SyntheticSAE:
    """A tiny SAE with an UNTIED random decoder and a real reconstruction
    error, sufficient to prove every arithmetic claim in this module with
    no model weights and no GPU.

    `DEAD_FEATURES` are pinned dead by a large negative encoder bias, so
    ReLU zeroes them for every input. Dead features are a real and
    well-documented property of trained SAEs, and pinning some here is what
    makes the already-zero-activation ablation control runnable at all --
    a control that could not run would be a control that proves nothing."""

    hook_name = "synthetic.blocks.0.hook_resid_post"
    DEAD_FEATURES = (2, 5, 13, 21)

    def __init__(self, d_in: int = 16, d_sae: int = 32, seed: int = 20260816) -> None:
        generator = torch.Generator().manual_seed(seed)
        self.d_in = d_in
        self.d_sae = d_sae
        self.W_enc = torch.randn(d_in, d_sae, generator=generator) / (d_in**0.5)
        self.b_enc = torch.randn(d_sae, generator=generator) * 0.1
        for index in self.DEAD_FEATURES:
            self.b_enc[index] = -1.0e6
        self.W_dec = torch.randn(d_sae, d_in, generator=generator) / (d_sae**0.5)
        self.b_dec = torch.randn(d_in, generator=generator) * 0.1

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return torch.relu(x.to(torch.float32) @ self.W_enc + self.b_enc)

    def decode(self, feats: torch.Tensor) -> torch.Tensor:
        return feats.to(torch.float32) @ self.W_dec + self.b_dec


def _print(title: str) -> None:
    print(f"\n{'-' * 78}\n{title}\n{'-' * 78}", flush=True)


def _selfcheck() -> int:
    """Prints the FAILURE cases first, then the passing ones, with real
    numbers. Returns non-zero if any claim in this module does not hold."""
    torch.manual_seed(20260816)
    sae = _SyntheticSAE()
    residual = torch.randn(2, 5, sae.d_in) * 3.0
    group = (GroupMember(3, 1.0), GroupMember(7, 0.5), GroupMember(11, 2.0))
    failures: list[str] = []

    def must_raise(label: str, fn, expected: type[Exception]) -> None:
        try:
            fn()
        except expected as exc:
            print(f"  REFUSED as required: {label}\n    {type(exc).__name__}: {str(exc)[:180]}")
        except Exception as exc:
            failures.append(f"{label}: raised {type(exc).__name__}, expected {expected.__name__}")
            print(f"  WRONG ERROR: {label}: {type(exc).__name__}: {exc}")
        else:
            failures.append(f"{label}: did NOT raise {expected.__name__}")
            print(f"  *** DID NOT RAISE *** {label}")

    _print("CONTROL 1 -- deliberately broken configurations MUST refuse")
    must_raise(
        "feature index 9999 absent from a d_sae=32 SAE",
        lambda: resolve_group(sae, GroupSpec(kind="amplify", members=(GroupMember(9999),), alpha=1.0)),
        FeatureNotInSAE,
    )
    must_raise(
        "group naming feature 3 twice",
        lambda: GroupSpec(kind="amplify", members=(GroupMember(3), GroupMember(3))),
        InvalidGroupSpec,
    )
    must_raise(
        "kind='ablate' with no explicit mechanism",
        lambda: GroupSpec(kind="ablate", members=group),
        InvalidGroupSpec,
    )
    must_raise(
        "negative feature index",
        lambda: GroupMember(-1),
        InvalidGroupSpec,
    )
    must_raise(
        "leaving out a feature that is not a member",
        lambda: GroupSpec(kind="amplify", members=group).without(999),
        InvalidGroupSpec,
    )

    _print("CONTROL 2 -- a hook that never fires MUST fail the firing assertion")
    empty = FiringLedger()
    must_raise(
        "ledger with 0 calls asserted against an expectation of 5",
        lambda: assert_fired_as_expected(empty, FiringExpectation(call_count=5), context="never-fired"),
        HookFiringMismatch,
    )
    fired = FiringLedger()
    hook, _resolved = build_group_hook(
        sae, GroupSpec(kind="amplify", members=group, alpha=1.5), ledger=fired
    )
    hook(residual)
    must_raise(
        "ledger with 1 call asserted against an expectation of 2",
        lambda: assert_fired_as_expected(fired, FiringExpectation(call_count=2), context="undercount"),
        HookFiringMismatch,
    )
    must_raise(
        "a fired-but-zero-delta hook asserted with require_nonzero_delta",
        lambda: assert_fired_as_expected(
            _zero_delta_ledger(sae, residual), FiringExpectation(call_count=1), context="zero-delta"
        ),
        HookFiringMismatch,
    )

    _print("CONTROL 3 -- exact-delta assertion MUST reject a wrong delta")
    must_raise(
        "claiming alpha=1.5 while the hook injected alpha=1.5 * 2",
        lambda: assert_exact_delta(
            residual,
            residual + 2.0 * _direction(sae, group),
            _direction(sae, group),
            context="wrong-alpha",
        ),
        ExactDeltaMismatch,
    )

    _print("CONTROL 4 -- null configurations MUST be exact identities (except (a))")
    for label, spec in (
        ("amplify, alpha=0", GroupSpec(kind="amplify", members=group, alpha=0.0)),
        ("amplify, empty group", GroupSpec(kind="amplify", members=(), alpha=3.0)),
        ("ablate/subtract, alpha=0", GroupSpec(kind="ablate", members=group, alpha=0.0, ablation_mechanism="subtract")),
        ("ablate/subtract, empty group", GroupSpec(kind="ablate", members=(), alpha=1.0, ablation_mechanism="subtract")),
    ):
        ledger = FiringLedger()
        hook_fn, _ = build_group_hook(sae, spec, ledger=ledger)
        out = hook_fn(residual)
        identical = bool(torch.equal(out, residual)) and out is residual
        print(
            f"  {label:34s} bit-identical={identical}  hook_calls={ledger.call_count} "
            f"positions_modified={ledger.positions_modified}"
        )
        if not identical:
            failures.append(f"{label} was not a bit-exact identity")
        if ledger.call_count != 1:
            failures.append(f"{label} did not record its (identity) firing")

    spec_a_null = GroupSpec(kind="ablate", members=(), alpha=0.0, ablation_mechanism="reconstruct")
    ledger = FiringLedger()
    hook_fn, _ = build_group_hook(sae, spec_a_null, ledger=ledger)
    out = hook_fn(residual)
    floor = float((out - residual).norm().item())
    print(
        f"  {'ablate/reconstruct, alpha=0':34s} bit-identical={bool(torch.equal(out, residual))}  "
        f"|h_after - h_before| = {floor:.6g}   <-- NOT an identity, BY DESIGN OF MECHANISM (a)"
    )
    print(
        f"    null_configuration_is_exact_identity(spec) reports "
        f"{null_configuration_is_exact_identity(spec_a_null)} for it, and True for the four above."
    )
    if floor <= 0.0:
        failures.append("mechanism (a) null configuration showed a zero floor; the fake SAE is degenerate")

    _print("CONTROL 5 -- ablating an already-zero group MUST be an identity under (a) and (b)")
    dead = _dead_features(sae, residual)
    if not dead:
        failures.append("no dead feature found in the synthetic SAE; control 5 could not run")
        print("  *** SKIPPED -- no already-zero feature available (this is itself a failure) ***")
    else:
        dead_group = tuple(GroupMember(i) for i in dead[:3])
        reconstruction = sae.decode(sae.encode(residual))
        for mechanism in ABLATION_MECHANISMS:
            spec = GroupSpec(
                kind="ablate", members=dead_group, alpha=1.0, ablation_mechanism=mechanism
            )
            ledger = FiringLedger()
            hook_fn, _ = build_group_hook(sae, spec, ledger=ledger)
            out = hook_fn(residual)
            activation = float(
                group_activations(sae, resolve_group(sae, spec), residual).abs().max().item()
            )
            versus_h = float((out - residual).abs().max().item())
            versus_recon = float((out - reconstruction).abs().max().item())
            # BOTH baselines are printed on purpose. "Identity" is not a
            # property of the ablation alone: under (b) the group's zero
            # activation makes it an identity against h itself, while under
            # (a) it is an identity only against the RECONSTRUCTION, because
            # (a) overwrites h with decode(encode(h)) whether or not any
            # feature was touched. Printing one number would let the reader
            # believe the mechanisms agree here. They do not.
            print(
                f"  features {dead[:3]} (max group activation {activation:.3g}) under "
                f"({'a' if mechanism == 'reconstruct' else 'b'}) {mechanism:12s}: "
                f"max |h_after - h| = {versus_h:.3g}   "
                f"max |h_after - decode(encode(h))| = {versus_recon:.3g}"
            )
            baseline_gap = versus_recon if mechanism == "reconstruct" else versus_h
            if baseline_gap > 1e-5:
                failures.append(
                    f"zero-activation ablation under {mechanism} moved its own baseline by "
                    f"{baseline_gap:.3g}"
                )
        print(
            "  READ: an already-zero group is an exact no-op under (b) against h, and an exact\n"
            "  no-op under (a) ONLY against decode(encode(h)). Against h, (a) still moves the\n"
            "  stream by the full reconstruction error while touching no live feature."
        )

    _print("CONTROL 6 -- the raw-HF path must REFUSE the ways the TL path does")
    must_raise(
        "hooking a layer index the model does not have",
        lambda: resolve_raw_hf_decoder_layer(_FakeHfModel(n_layers=4), layer=99),
        InvalidGroupSpec,
    )
    must_raise(
        "a negative layer index silently wrapping to a real layer",
        lambda: resolve_raw_hf_decoder_layer(_FakeHfModel(n_layers=4), layer=-1),
        InvalidGroupSpec,
    )
    must_raise(
        "passing the whole model where a decoder layer module is required",
        lambda: attach_group_hook_raw_hf(
            object(), sae, GroupSpec(kind="amplify", members=group), ledger=FiringLedger()
        ),
        GroupInterventionError,
    )
    fake_model = _FakeHfModel(n_layers=4)
    other_model = _FakeHfModel(n_layers=4)
    must_raise(
        "hooking a module that is NOT the one the discovery scorer hooks",
        lambda: assert_hooks_the_scored_tensor(
            other_model.model.layers[1], fake_model, layer=1
        ),
        GroupInterventionError,
    )
    identity = assert_hooks_the_scored_tensor(fake_model.model.layers[1], fake_model, layer=1)
    print(f"  ACCEPTED as required: same-module identity check -> {identity['identity']}")

    _print("CONTROL 7 -- at bfloat16 a PASSING exact-delta assertion proves nothing")
    print(f"  {'dtype':>9} {'alpha':>7} {'worst':>11} {'tolerance':>11} {'passes':>7} {'absorbed':>12}")
    absorption_seen = False
    for dtype in (torch.float32, torch.bfloat16, torch.float16):
        for alpha in (10.0, 0.1, 0.001):
            x = residual.to(dtype)
            spec = GroupSpec(kind="amplify", members=group, alpha=alpha)
            ledger = FiringLedger()
            hook_fn, resolved = build_group_hook(sae, spec, ledger=ledger)
            out = hook_fn(x)
            expected = resolved.expected_amplify_delta()
            tol = delta_tolerance(x, expected)
            worst = float(
                ((out - x).to(torch.float32) - expected.expand_as(out)).abs().max().item()
            )
            record = ledger.records[0]
            if dtype is not torch.float32 and record.absorbed_element_count:
                absorption_seen = True
            if dtype is torch.float32 and record.absorbed_element_count:
                failures.append(f"float32 absorbed {record.absorbed_element_count} element(s)")
            print(
                f"  {str(dtype).replace('torch.',''):>9} {alpha:7} {worst:11.3e} {tol:11.3e} "
                f"{worst <= tol!s:>7} "
                f"{record.absorbed_element_count:5d}/{record.requested_nonzero_element_count:<6d}"
            )
    if not absorption_seen:
        failures.append("no absorption observed at bfloat16/float16; the census cannot be trusted")
    print(
        "  READ: every row PASSES the exact-delta assertion, including rows where the residual\n"
        "  stream swallowed most of the requested delta whole. The tolerance the dtype forces is\n"
        "  larger than the thing that went missing. assert_no_absorption() is the check that sees\n"
        "  it; the exact-delta assertion structurally cannot."
    )
    bf16_alpha = minimum_effective_alpha(
        residual.to(torch.bfloat16), _direction(sae, group), dtype=torch.bfloat16
    )
    fp32_alpha = minimum_effective_alpha(
        residual, _direction(sae, group), dtype=torch.float32
    )
    print(
        f"  minimum_effective_alpha: bfloat16 {bf16_alpha:.4g}, float32 {fp32_alpha:.4g} "
        f"({bf16_alpha / fp32_alpha:.0f}x more dose needed to survive bfloat16 at all)"
    )
    bf_ledger = FiringLedger()
    bf_hook, _ = build_group_hook(
        sae, GroupSpec(kind="amplify", members=group, alpha=0.001), ledger=bf_ledger
    )
    bf_hook(residual.to(torch.bfloat16))
    must_raise(
        "assert_no_absorption on a bfloat16 run that mostly did nothing",
        lambda: assert_no_absorption(bf_ledger, context="bf16 alpha=0.001"),
        ExactDeltaMismatch,
    )

    _print("CONTROL 8 -- RULING_13's three defects, checked against THIS module")
    import itertools

    orders = list(itertools.permutations(group))
    outs = []
    for order in orders:
        spec = GroupSpec(kind="ablate", members=order, alpha=1.0, ablation_mechanism="subtract")
        ledger = FiringLedger()
        hook_fn, _ = build_group_hook(sae, spec, ledger=ledger)
        outs.append(hook_fn(residual))
    spread = max(float((out - outs[0]).abs().max()) for out in outs)
    scale = float((outs[0] - residual).abs().max())
    print(
        f"  D2 order-invariance: {len(orders)} member orders, max pairwise difference = "
        f"{spread:.3e} against an intervention magnitude of {scale:.3e} "
        f"(a GROUP IS A SET; this composes simultaneously)"
    )
    if spread > 1e-3 * scale:
        failures.append("group composition is order-dependent")

    for size in (1, 2, 3):
        spec = GroupSpec(
            kind="ablate", members=group[:size], alpha=1.0, ablation_mechanism="subtract"
        )
        ledger = FiringLedger()
        hook_fn, _ = build_group_hook(sae, spec, ledger=ledger)
        hook_fn(residual)
        state = classify_intervention_state(spec, ledger)
        print(
            f"  D1 firing evidence at k={size}: calls={ledger.call_count} "
            f"delta_norm={ledger.total_delta_norm:.4f} state={state}"
        )
        if ledger.call_count != 1 or ledger.total_delta_norm <= 0.0:
            failures.append(f"firing evidence missing at k={size}")

    must_raise(
        "D3: a clamp dose with no per-member corpus_max",
        lambda: GroupSpec(
            kind="amplify",
            members=(GroupMember(3, corpus_max=2.0), GroupMember(7)),
            dose_form="clamp",
        ),
        InvalidGroupSpec,
    )
    must_raise(
        "an (a) result paired with an unhooked control",
        lambda: assert_control_is_admissible(
            GroupSpec(
                kind="ablate", members=group, alpha=1.0, ablation_mechanism="reconstruct"
            ),
            GroupSpec.noop(),
        ),
        InvalidGroupSpec,
    )
    must_raise(
        "ablating generated_only without stating the prompt-positions choice",
        lambda: GroupSpec(
            kind="ablate",
            members=group,
            ablation_mechanism="subtract",
            positions="generated_only",
        ),
        InvalidGroupSpec,
    )

    _print("CONTROL 9 -- VOID and NOT-EXERCISED are distinct states, never nulls")
    never = FiringLedger()
    amplify_spec = GroupSpec(kind="amplify", members=group, alpha=1.0)
    print(f"  hook never registered           -> {classify_intervention_state(amplify_spec, never)}")
    if dead:
        inert_spec = GroupSpec(
            kind="ablate",
            members=tuple(GroupMember(i) for i in dead[:2]),
            alpha=1.0,
            ablation_mechanism="subtract",
        )
        inert_ledger = FiringLedger()
        build_group_hook(sae, inert_spec, ledger=inert_ledger)[0](residual)
        print(
            f"  fired, group already silent     -> "
            f"{classify_intervention_state(inert_spec, inert_ledger)}"
        )
    applied_ledger = FiringLedger()
    build_group_hook(sae, amplify_spec, ledger=applied_ledger)[0](residual)
    print(
        f"  fired and moved the stream      -> "
        f"{classify_intervention_state(amplify_spec, applied_ledger)}"
    )
    print(f"  the control arm                 -> {classify_intervention_state(GroupSpec.noop(), never)}")
    print(
        "  READ: an unchanged continuation from either VOID state says NOTHING about the group.\n"
        "  Collapsing them into a null would manufacture 'the concept was not steerable' out of an\n"
        "  intervention that never happened."
    )

    _print("CONTROL 10 -- the clamp dose acts where the group is SILENT")
    if dead:
        silent = GroupMember(dead[0], corpus_max=4.0)
        clamp_spec = GroupSpec(
            kind="amplify", members=(silent,), alpha=1.0, dose_form="clamp"
        )
        ledger = FiringLedger()
        out = build_group_hook(sae, clamp_spec, ledger=ledger)[0](residual)
        realised = float((out - residual).abs().max())
        wanted = float((4.0 * resolve_decoder_matrix(sae)[dead[0]]).abs().max())
        print(
            f"  feature {dead[0]} activation 0, clamp target 4.0: realised max|delta| = "
            f"{realised:.4f} against the requested {wanted:.4f}"
        )
        print(
            "  A MULTIPLICATIVE dose would be identically zero here -- an amplifier that cannot\n"
            "  amplify on exactly the prompts a sufficiency criterion needs. This module has no\n"
            "  multiplicative form."
        )
        if abs(realised - wanted) > 1e-4:
            failures.append("clamp dose did not deliver its target on a silent feature")

    _print("CONTROL 11 -- a clamp dose that evaluates to ZERO must REFUSE, before any forward")
    live = [
        i
        for i in range(sae.d_sae)
        if i not in sae.DEAD_FEATURES
        and float(sae.encode(residual)[..., i].abs().max()) > 0.0
    ][:5]
    if len(live) < 5:
        failures.append("need five live features to build the mixed-group control")
        print("  *** SKIPPED -- fewer than five live features (itself a failure) ***")
    else:
        maximally_selective = tuple(GroupMember(i, corpus_max=0.0) for i in live[:3])
        must_raise(
            "every member maximally selective (corpus_max == 0) under dose_form='clamp'",
            lambda: GroupSpec(
                kind="amplify", members=maximally_selective, alpha=1.0, dose_form="clamp"
            ),
            ZeroClampDose,
        )
        mixed = (
            GroupMember(live[0], corpus_max=0.0),
            GroupMember(live[1], corpus_max=3.5),
            GroupMember(live[2], corpus_max=0.0),
            GroupMember(live[3], corpus_max=1.25),
            GroupMember(live[4], corpus_max=8.0),
        )
        must_raise(
            "MIXED group: 2 of 5 members maximally selective, 3 with a live scale",
            lambda: GroupSpec(kind="amplify", members=mixed, alpha=1.0, dose_form="clamp"),
            ZeroClampDose,
        )
        must_raise(
            "alpha == 0 under dose_form='clamp' (a target of 0 is an ABLATION, not an amplify)",
            lambda: GroupSpec(
                kind="amplify",
                members=(GroupMember(live[0], corpus_max=4.0),),
                alpha=0.0,
                dose_form="clamp",
            ),
            ZeroClampDose,
        )
        # Non-zero in float64, EXACTLY zero once evaluated at float32: the one
        # zero dose the construction-time gate structurally cannot see.
        underflow = GroupSpec(
            kind="amplify",
            members=(GroupMember(live[0], corpus_max=1e-30), GroupMember(live[1], corpus_max=2.0)),
            alpha=1e-30,
            dose_form="clamp",
        )
        print(
            f"  the underflow spec IS constructible (float64 dose "
            f"{1e-30 * 1e-30!r} != 0) -- the second gate is what catches it:"
        )
        counting = _CountingSAE(sae)
        underflow_ledger = FiringLedger()
        must_raise(
            "alpha * corpus_max non-zero in float64, zero at float32",
            lambda: build_group_hook(counting, underflow, ledger=underflow_ledger),
            ZeroClampDose,
        )
        print(
            f"  PRE-FORWARD PROOF: after that refusal, sae.encode calls = {counting.encode_calls}, "
            f"sae.decode calls = {counting.decode_calls}, hook invocations recorded = "
            f"{underflow_ledger.call_count}. The refusal comes from resolve_group, which runs "
            "BEFORE build_group_hook returns a hook, so nothing was ever registered and no forward "
            "could have happened."
        )
        print(
            "  PRE-FORWARD PROOF (the other three): raised by GroupSpec.__post_init__, so the spec "
            "OBJECT never came into existence -- there is nothing to hand to a hook, a backend or "
            "a job."
        )

        # ABLATION IS UNAFFECTED, MEASURED ON THE SAME MEMBERS.
        ablate_spec = GroupSpec(
            kind="ablate",
            members=maximally_selective,
            alpha=1.0,
            ablation_mechanism="subtract",
        )
        ablate_ledger = FiringLedger()
        ablate_hook, ablate_resolved = build_group_hook(sae, ablate_spec, ledger=ablate_ledger)
        ablated = ablate_hook(residual)
        acts = group_activations(sae, ablate_resolved, residual)
        closed_form = -(acts * ablate_resolved.weights) @ ablate_resolved.decoder_rows
        discrepancy = float(((ablated - residual) - closed_form).abs().max().item())
        state = classify_intervention_state(ablate_spec, ablate_ledger)
        print(
            f"  ABLATION UNAFFECTED, same members {ablate_resolved.feature_indices.tolist()} all with "
            f"corpus_max=0.0: calls={ablate_ledger.call_count} "
            f"positions_modified={ablate_ledger.positions_modified} "
            f"|delta|={ablate_ledger.total_delta_norm:.4f} state={state}; "
            f"max |delta - (-sum_f w_f a_f W_dec[f])| = {discrepancy:.3e}"
        )
        if state != "APPLIED" or ablate_ledger.total_delta_norm <= 0.0:
            failures.append("ablation of maximally selective members did not apply")
        if discrepancy > 1e-5:
            failures.append("ablation delta on corpus_max==0 members left the closed form")
        print(
            "  READ: corpus_max is a BACKGROUND-ACTIVATION reference and ablation needs none -- it\n"
            "  removes a_f(h), the feature's actual contribution. The zero-dose hazard is confined\n"
            "  to the clamp/amplify arm, and no replacement scale is named anywhere above."
        )

    _print("CONTROL 12 -- a weight-0 member is REFUSED: same defect, different arithmetic")
    inert_direction = _direction(sae, (GroupMember(3, 1.0), GroupMember(7, 0.0)))
    solo_direction = _direction(sae, (GroupMember(3, 1.0),))
    identical = bool(torch.equal(inert_direction, solo_direction))
    print(
        f"  WHY: the k=2 injected direction with weights [1.0, 0.0] is bit-identical to the k=1 "
        f"direction: {identical} (max difference "
        f"{float((inert_direction - solo_direction).abs().max()):.3e}). A k=2 arm built that way "
        "would report member_count=2 and MEASURE a k=1 effect."
    )
    if not identical:
        failures.append("the weight-0 inertness claim does not hold on this SAE")
    must_raise(
        "every member weight zero",
        lambda: GroupSpec(kind="amplify", members=(GroupMember(3, 0.0), GroupMember(7, 0.0))),
        ZeroWeightMember,
    )
    must_raise(
        "ONE weight-0 member among live ones (the k=2-acting-as-k=1 case)",
        lambda: GroupSpec(
            kind="ablate",
            members=(GroupMember(3, 1.0), GroupMember(7, 0.0)),
            alpha=1.0,
            ablation_mechanism="subtract",
        ),
        ZeroWeightMember,
    )
    weight_counter = _CountingSAE(sae)
    weight_ledger = FiringLedger()
    underflow_weight = GroupSpec(
        kind="amplify", members=(GroupMember(3, 1e-50), GroupMember(7, 1.0)), alpha=1.0
    )
    must_raise(
        "a weight non-zero in float64 that underflows to zero at float32",
        lambda: build_group_hook(weight_counter, underflow_weight, ledger=weight_ledger),
        ZeroWeightMember,
    )
    print(
        f"  PRE-FORWARD PROOF: sae.encode calls = {weight_counter.encode_calls}, hook invocations = "
        f"{weight_ledger.call_count}. (The float64-zero cases never get a spec object at all.)"
    )
    negative = GroupSpec(kind="amplify", members=(GroupMember(3, -1.0), GroupMember(7, 2.0)))
    print(
        f"  ACCEPTED as required: negative weights {list(m.weight for m in negative.members)} -- a "
        "sign flip is a DIRECTION, not inertness, and the member still moves the stream."
    )
    print(
        "  READ: leave-one-out is expressed by REMOVING the member (GroupSpec.without), and an\n"
        "  inert arm by GroupSpec.noop() or a whole-spec alpha == 0, both of which are recorded.\n"
        "  A weight of 0 inside one member is visible nowhere. See NO_LEGITIMATE_ZERO_WEIGHT_MEMBER."
    )

    _print("CONTROL 13 -- the raw-HF layer output contract is probed on ONE token, and refuses")
    plain_model = _FakeRawHfModel(d_model=16, wrap="tensor")
    contract = probe_raw_hf_layer_output_contract(plain_model, plain_model.model.layers[1])
    print(f"  a plain-tensor layer is ACCEPTED and recorded -> {json.dumps(contract, sort_keys=True)}")
    tuple_model = _FakeRawHfModel(d_model=16, wrap="tuple")
    must_raise(
        "a decoder layer that returns a TUPLE (the Qwen3.5 unknown)",
        lambda: probe_raw_hf_layer_output_contract(tuple_model, tuple_model.model.layers[1]),
        RawHfLayerContractMismatch,
    )
    unhooked_model = _FakeRawHfModel(d_model=16, wrap="tensor")
    must_raise(
        "a layer that is not on the model's forward path (the hook could never fire)",
        lambda: probe_raw_hf_layer_output_contract(
            unhooked_model, _FakeRawHfModel(d_model=16, wrap="tensor").model.layers[0]
        ),
        RawHfLayerContractMismatch,
    )
    width_model = _FakeRawHfModel(d_model=16, wrap="tensor")
    must_raise(
        "a layer whose d_model does not match the SAE's d_in",
        lambda: probe_raw_hf_layer_output_contract(
            width_model, width_model.model.layers[1], expected_d_model=4096
        ),
        RawHfLayerContractMismatch,
    )
    print(
        "  READ: the probe is ONE TOKEN with a capture-only hook -- no intervention, nothing\n"
        "  generated, nothing scored. On the cluster it refuses seconds after the model loads,\n"
        "  not mid-generation. The REAL Qwen3_5DecoderLayer (and the MoE variant) are read and\n"
        "  run in tests/test_group_intervention.py against the installed transformers."
    )

    _print("SUCCESS 1 -- the amplify delta is EXACTLY alpha * sum_f w_f * decoder[f]")
    for alpha in (0.5, 1.0, 4.0, -2.0):
        spec = GroupSpec(kind="amplify", members=group, alpha=alpha)
        ledger = FiringLedger()
        hook_fn, _resolved = build_group_hook(sae, spec, ledger=ledger)
        out = hook_fn(residual)
        expected = _direction(sae, group) * alpha
        worst = assert_exact_delta(residual, out, expected, context=f"alpha={alpha}")
        tol = delta_tolerance(residual, expected)
        print(
            f"  alpha={alpha:>5}: max |measured - expected| = {worst:.3e}  (tolerance {tol:.3e}, "
            f"|expected|={float(expected.norm().item()):.4f})  calls={ledger.call_count} "
            f"positions_modified={ledger.positions_modified}"
        )

    _print("SUCCESS 2 -- the injected delta is linear in alpha and additive over members")
    base = _hook_delta(sae, GroupSpec(kind="amplify", members=group, alpha=1.0), residual)
    doubled = _hook_delta(sae, GroupSpec(kind="amplify", members=group, alpha=2.0), residual)
    linearity = float((doubled - 2.0 * base).abs().max().item())
    parts = sum(
        _hook_delta(sae, GroupSpec(kind="amplify", members=(m,), alpha=1.0), residual)
        for m in group
    )
    additivity = float((base - parts).abs().max().item())
    print(f"  max |delta(2a) - 2*delta(a)|           = {linearity:.3e}")
    print(f"  max |delta(group) - sum delta(member)| = {additivity:.3e}")
    print(
        "  NOTE: this is linearity OF THE INJECTED VECTOR ONLY. joint_intervention_lane.json\n"
        "  RULING_3 PROHIBITS predicting a joint EFFECT from summed individual effects; nothing\n"
        "  here claims the model's response is additive."
    )
    if linearity > 1e-5 or additivity > 1e-5:
        failures.append("amplify delta was not linear/additive as claimed")

    _print("SUCCESS 3 -- mechanism (a) vs (b): the measured gap is the reconstruction error")
    for alpha in (0.0, 1.0):
        for members, name in ((group, "3 features"), ((), "empty group")):
            spec = GroupSpec(
                kind="ablate", members=members, alpha=alpha, ablation_mechanism="subtract"
            )
            gap = measure_mechanism_gap(sae, spec, residual)
            print(
                f"  alpha={alpha}, {name:11s}: |delta_a|={gap['delta_a_norm']:9.4f}  "
                f"|delta_b|={gap['delta_b_norm']:9.4f}  |gap|={gap['gap_norm']:9.4f}  "
                f"|recon_err|={gap['reconstruction_error_norm']:9.4f}  "
                f"closed-form residual={gap['closed_form_residual_max_abs']:.3e}"
            )
            if gap["closed_form_residual_max_abs"] > 1e-4:
                failures.append(
                    f"delta_a - delta_b != -reconstruction_error at alpha={alpha}, {name}"
                )
    print(
        "  READ: |gap| == |recon_err| at every alpha and every group size, including the empty\n"
        "  group. The two mechanisms are NOT interchangeable and the difference does not shrink\n"
        "  with the intervention -- it is a constant floor set by the SAE's own fidelity."
    )

    _print("SUCCESS 4 -- leave-one-out arms preserve cardinality exactly")
    full = GroupSpec(kind="ablate", members=group, alpha=1.0, ablation_mechanism="subtract")
    loo = leave_one_out_specs(full)
    print(f"  full group k={full.member_count}; leave-one-out arms={len(loo)}")
    for arm in loo:
        print(f"    {arm.label:34s} members={list(arm.feature_indices)} (k={arm.member_count})")
        if arm.member_count != full.member_count - 1:
            failures.append(f"leave-one-out arm {arm.label} has the wrong cardinality")
    if len(loo) != full.member_count:
        failures.append("leave_one_out_specs did not produce one arm per member")

    _print("RESULT")
    if failures:
        for problem in failures:
            print(f"  FAILED: {problem}")
        print(f"\n{len(failures)} claim(s) in this module DO NOT HOLD.")
        return 1
    print("  every claim above held on synthetic tensors. Paths that need a GPU or real weights:")
    for item in UNEXERCISED_WITHOUT_GPU:
        print(f"    - {item}")
    return 0


class _FakeHfModel:
    """The minimum shape `resolve_qwen_text_decoder` accepts -- an object
    with `.model.layers` -- so the raw-HF REFUSALS are provable without any
    model weights. It proves the resolvers' guard rails, not a forward
    pass; the forward pass is proven on the real fixture model in the test
    suite."""

    class _Decoder:
        def __init__(self, n_layers: int) -> None:
            self.layers = [torch.nn.Identity() for _ in range(n_layers)]

    def __init__(self, n_layers: int = 4) -> None:
        self.model = _FakeHfModel._Decoder(n_layers)


class _CountingSAE:
    """A pass-through wrapper that counts `encode`/`decode` calls.

    Exists to make "the refusal happened BEFORE any forward" a MEASUREMENT
    rather than an argument from code order: if the zero-dose gate had fired
    late, these counters would be non-zero."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.encode_calls = 0
        self.decode_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        self.encode_calls += 1
        return self.inner.encode(x)

    def decode(self, feats: torch.Tensor) -> torch.Tensor:
        self.decode_calls += 1
        return self.inner.decode(feats)


class _FakeRawHfLayer(torch.nn.Module):
    """A decoder layer whose RETURN CONVENTION the caller chooses, so the
    output-contract probe's refusals are provable with no Qwen weights. The
    real `Qwen3_5DecoderLayer` is exercised in the test suite."""

    def __init__(self, d_model: int, wrap: str) -> None:
        super().__init__()
        self.bias = torch.nn.Parameter(torch.zeros(d_model))
        self.wrap = wrap

    def forward(self, hidden_states: torch.Tensor) -> Any:
        out = hidden_states + self.bias
        if self.wrap == "tuple":
            return (out, None)
        if self.wrap == "flat":
            return out.reshape(-1)
        return out


class _FakeRawHfModel(torch.nn.Module):
    """`.model.layers` shaped exactly as `Qwen3_5ForCausalLM`'s is, callable
    with `input_ids=`, so `probe_raw_hf_layer_output_contract()` can be
    exercised in both directions without any model weights."""

    def __init__(self, d_model: int = 16, n_layers: int = 2, wrap: str = "tensor") -> None:
        super().__init__()
        self.d_model = d_model
        self.model = torch.nn.Module()
        self.model.layers = torch.nn.ModuleList(
            [_FakeRawHfLayer(d_model, wrap) for _ in range(n_layers)]
        )

    def forward(self, input_ids: torch.Tensor, **_kwargs: Any) -> torch.Tensor:
        hidden = torch.zeros(int(input_ids.shape[0]), int(input_ids.shape[1]), self.d_model)
        for layer in self.model.layers:
            out = layer(hidden)
            if isinstance(out, torch.Tensor) and out.ndim == 3:
                hidden = out
        return hidden


def _direction(sae: Any, members: tuple[GroupMember, ...]) -> torch.Tensor:
    w_dec = resolve_decoder_matrix(sae).to(torch.float32)
    return sum(m.weight * w_dec[m.feature_index] for m in members)


def _hook_delta(sae: Any, spec: GroupSpec, residual: torch.Tensor) -> torch.Tensor:
    ledger = FiringLedger()
    hook_fn, _ = build_group_hook(sae, spec, ledger=ledger)
    return hook_fn(residual) - residual


def _zero_delta_ledger(sae: Any, residual: torch.Tensor) -> FiringLedger:
    ledger = FiringLedger()
    hook_fn, _ = build_group_hook(
        sae, GroupSpec(kind="amplify", members=(), alpha=1.0), ledger=ledger
    )
    hook_fn(residual)
    return ledger


def _dead_features(sae: Any, residual: torch.Tensor, limit: int = 8) -> list[int]:
    feats = sae.encode(residual.to(torch.float32))
    per_feature = feats.abs().amax(dim=tuple(range(feats.ndim - 1)))
    return [int(i) for i in torch.nonzero(per_feature == 0.0).flatten().tolist()][:limit]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Feature-group intervention machinery (ENGINEERING PREVIEW ONLY -- submits nothing, "
            "allocates nothing, spends nothing)."
        )
    )
    parser.add_argument(
        "--selfcheck",
        action="store_true",
        help="prove this module's arithmetic and firing claims on synthetic tensors, failures first",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.selfcheck:
        return _selfcheck()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
