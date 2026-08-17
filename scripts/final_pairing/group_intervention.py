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
`measure_mechanism_gap()` returns that quantity so the Architect's pending
ruling can be made on a measured number rather than an argument.

ONE CONSEQUENCE THE CALLER MUST SEE, because it is not obvious and it
decides how a control arm must be built:

    Under (b), the null configuration (alpha == 0, or an empty group) is
    an EXACT identity. Under (a) IT IS NOT -- it still replaces h with
    decode(encode(h)). A "no-op" arm run through mechanism (a) therefore
    already moves the model by the whole reconstruction error before any
    feature is touched.

That is a property of the mechanism, not a defect here, and this file
refuses to hide it: `null_configuration_is_exact_identity()` reports it,
`GroupSpec.reconstruction_control()` builds the arm that neutralises it
(an EMPTY group under mechanism (a) is precisely the reconstruction-only
control), and the self-check prints the measured floor.

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
from dataclasses import dataclass, field
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
    "on either final-pairing model.",
    "bfloat16/float16 residual streams: every test runs float32, so the delta-cast rounding "
    "term in the hook is real but unmeasured at production dtype.",
    "Multi-GPU / device_map sharding: assert_devices_before_forward() is exercised only in "
    "the all-CPU case, where it trivially agrees.",
    "The raw-HF (non-TransformerLens) Qwen3.5 hook path: this file drives `model.hooks(...)`, "
    "which the Qwen fallback does not have. See attach_group_hook_raw_hf().",
    "Generation batching: run_arm() deliberately generates one prompt per call (see its "
    "docstring); a padded batch path does not exist and is not tested.",
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

ABLATION_MECHANISMS: tuple[AblationMechanism, ...] = ("reconstruct", "subtract")


@dataclass(frozen=True)
class GroupMember:
    """One feature in the group, with its own weight.

    `weight` means different things per kind, and both are documented here
    rather than inferred: under `amplify` it scales that feature's decoder
    direction in the injected sum; under `ablate` it is the FRACTION of
    that feature's own decoder contribution removed (with the global
    `alpha` multiplying it, so `alpha=1, weight=1` is full ablation)."""

    feature_index: int
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.feature_index, int) or isinstance(self.feature_index, bool):
            raise InvalidGroupSpec(f"feature_index must be an int; got {self.feature_index!r}")
        if self.feature_index < 0:
            raise InvalidGroupSpec(f"feature_index must be non-negative; got {self.feature_index}")
        weight = float(self.weight)
        if weight != weight or weight in (float("inf"), float("-inf")):
            raise InvalidGroupSpec(f"weight must be finite; got {self.weight!r}")


@dataclass(frozen=True)
class GroupSpec:
    """The frozen contract for one group intervention.

    `positions` defaults to `"all"` per the standing science ruling of
    2026-08-13 and matching every number this project has published
    (docs/positions_semantics.md)."""

    kind: InterventionKind
    members: tuple[GroupMember, ...] = ()
    alpha: float = 1.0
    ablation_mechanism: AblationMechanism | None = None
    positions: Positions = "all"
    hook_name: str | None = None
    label: str = ""

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
        if self.kind == "noop" and self.members:
            raise InvalidGroupSpec("kind='noop' must name no members; it is the structural control arm")

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
        return GroupSpec(
            kind=self.kind,
            members=kept,
            alpha=self.alpha,
            ablation_mechanism=self.ablation_mechanism,
            positions=self.positions,
            hook_name=self.hook_name,
            label=f"{self.label or self.kind}-without-{feature_index}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "members": [
                {"feature_index": m.feature_index, "weight": float(m.weight)} for m in self.members
            ],
            "member_count": self.member_count,
            "alpha": float(self.alpha),
            "ablation_mechanism": self.ablation_mechanism,
            "positions": self.positions,
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
    `GroupSpec.reconstruction_control()` as the arm to subtract instead."""
    if spec.kind == "noop":
        return True
    is_null = spec.member_count == 0 or float(spec.alpha) == 0.0
    if not is_null:
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

    @property
    def member_count(self) -> int:
        return int(self.feature_indices.shape[0])

    def expected_amplify_delta(self, dtype: torch.dtype | None = None) -> torch.Tensor:
        """`alpha * sum_f w_f * W_dec[f]` -- the exact vector an amplify
        hook must add at every steered position. Computed here from the
        resolved rows so a test can assert against it WITHOUT calling the
        hook's own code path."""
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
    rows = w_dec.detach().to(torch.float32).index_select(0, indices) if spec.members else torch.zeros(
        (0, d_in), dtype=torch.float32, device=device
    )
    direction = (
        (weights.unsqueeze(1) * rows).sum(dim=0)
        if spec.members
        else torch.zeros(d_in, dtype=torch.float32, device=device)
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

    def summary(self) -> dict[str, Any]:
        return {
            "call_count": self.call_count,
            "prefill_call_count": self.prefill_call_count,
            "decode_call_count": self.decode_call_count,
            "positions_seen": self.positions_seen,
            "positions_modified": self.positions_modified,
            "total_delta_norm": self.total_delta_norm,
            "max_abs_delta": self.max_abs_delta,
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
    of failing a correct hook or hiding a wrong one behind a constant."""
    dtype = before.dtype if before.is_floating_point() else torch.float32
    eps = torch.finfo(dtype).eps
    scale = float(before.detach().abs().max().item()) if before.numel() else 1.0
    if expected is not None and expected.numel():
        scale = max(scale, float(expected.detach().abs().max().item()))
    return float(eps * max(scale, 1.0) * 8.0)


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
    record how exact 'exact' actually was."""
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


# ---------------------------------------------------------------------------
# The two ablation mechanisms, and the gap between them.
# ---------------------------------------------------------------------------


def group_activations(sae: Any, resolved: ResolvedGroup, residual: torch.Tensor) -> torch.Tensor:
    """`[..., k]` -- this group's feature activations at every position."""
    feats = sae.encode(residual.to(torch.float32))
    return feats.index_select(-1, resolved.feature_indices)


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
    amplify_delta32 = resolved.expected_amplify_delta() if spec.kind == "amplify" else None

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

        def record(modified: int, delta_norm: float, max_abs: float) -> None:
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
            if spec.kind == "amplify":
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
            record(
                modified=modified_slots,
                delta_norm=float(effective.norm().item()),
                max_abs=float(effective.abs().max().item()) if effective.numel() else 0.0,
            )

            if verify_exact_delta and spec.kind == "amplify":
                # Checked at EVERY position, steered and unsteered alike. Under
                # `generated_only` the expected delta is the requested vector
                # where the mask is True and EXACTLY ZERO where it is False, so
                # a hook that leaked into the prefill fails here rather than
                # being excused as out of scope.
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


def attach_group_hook_raw_hf(*_args: object, **_kwargs: object):
    """NOT IMPLEMENTED, deliberately and loudly.

    The Qwen3.5-27B final pairing has no transformer_lens entry and runs as
    a raw `AutoModelForCausalLM` with `register_forward_hook`. That path is
    real and this module does not implement it. It raises rather than
    silently falling back to `attach_group_hook`, because a fallback that
    hooked nothing would be exactly the never-fires failure this module
    exists to make impossible."""
    raise NotImplementedError(
        "the raw-HF (Qwen3.5) group-hook path is not implemented in this module. It needs a "
        "`register_forward_hook` on the resolved decoder layer plus the same FiringLedger "
        "contract; it is NOT a rename of attach_group_hook."
    )


# ---------------------------------------------------------------------------
# Device gate.
# ---------------------------------------------------------------------------


def _import_discovery_module() -> Any:
    """Import `final_pairing_concept_discovery` for its device gate ONLY.

    That file belongs to another lane and is never edited from here. No git
    call is involved -- this is an ordinary file import -- so the cluster's
    tarball-extract-with-no-.git shape (where `git show` exits 128) does not
    reach this path."""
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import final_pairing_concept_discovery as discovery
    except Exception as exc:
        raise DeviceGateUnavailable(
            "could not import final_pairing_concept_discovery to run the shared device gate "
            f"({type(exc).__name__}: {exc}). REFUSING to continue: skipping the gate is how job "
            "415590 forwarded a CPU model against cuda:0 inputs."
        ) from exc
    return discovery


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
    exact_identity_to_control: bool | None = None

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec,
            "results": [r.to_dict() for r in self.results],
            "device_placement": self.device_placement,
            "null_configuration_is_exact_identity": self.null_configuration_is_exact_identity,
        }


def _generated_token_logprobs(
    model: Any,
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
    with torch.no_grad(), attach_group_hook(
        model,
        sae,
        spec,
        ledger=ledger,
        prompt_lengths=prompt_lengths,
        verify_exact_delta=verify_exact_delta,
    ):
        logits = model(tokens)
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


def run_arm(
    model: Any,
    sae: Any,
    spec: GroupSpec,
    prompts: Sequence[str],
    *,
    max_new_tokens: int,
    seed: int,
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
    configuration that is an exact identity by construction."""
    if max_new_tokens < 1:
        raise ValueError(f"max_new_tokens must be >= 1; got {max_new_tokens}")

    is_identity = null_configuration_is_exact_identity(spec)
    if require_nonzero_delta is None:
        require_nonzero_delta = not is_identity

    resolved_device = device or str(
        next((p.device for p in model.parameters()), torch.device("cpu"))
    )
    placement = assert_devices_before_forward(device=resolved_device, model=model, sae=sae)

    results: list[PromptResult] = []
    for prompt in prompts:
        tokens = model.to_tokens([prompt])
        prompt_token_count = int(tokens.shape[1])
        ledger = FiringLedger()
        prompt_lengths = prompt_token_count if spec.positions == "generated_only" else None

        torch.manual_seed(seed)
        with attach_group_hook(
            model,
            sae,
            spec,
            ledger=ledger,
            prompt_lengths=prompt_lengths,
            verify_exact_delta=verify_exact_delta,
        ):
            output = model.generate(
                tokens,
                max_new_tokens=max_new_tokens,
                do_sample=do_sample,
                temperature=temperature,
                stop_at_eos=stop_at_eos,
                verbose=False,
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
                model,
                sae,
                spec,
                output,
                prompt_token_count,
                verify_exact_delta=verify_exact_delta,
            )

        full_text = model.to_string(output[0])
        prompt_text = model.to_string(output[0, :prompt_token_count])
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
    control_arm = run_arm(
        model, sae, control, prompts, max_new_tokens=max_new_tokens, seed=seed, **arm_kwargs
    )
    treatment_arm = run_arm(
        model, sae, spec, prompts, max_new_tokens=max_new_tokens, seed=seed, **arm_kwargs
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
