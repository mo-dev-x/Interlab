"""G-D (Amplify) / G-E (Suppress) causal validation via the real,
installable Lodestar package (a separate repository at `d:\\lodstar` in
this environment; commit/entry point recorded below) -- never vendored,
never reimplemented.

WHAT IS REUSED FROM LODESTAR, VERBATIM, NOT REIMPLEMENTED:

- `lodestar.rubrics.steering.COHERENCE` / `CONCEPT_RELEVANCE` -- the exact
  rubrics named `coherence`/`concept_relevance`, version "1.0" each,
  matching this task's own "concept_relevance and coherence v1.0"
  requirement letter-for-letter.
- `lodestar.judges.anthropic.AnthropicJudge` -- the real, network-backed
  judge. `lodestar.judges.base.JUDGE_TEMPERATURE = 0` is hardcoded inside
  Lodestar itself and is never overridden here -- "use the existing
  Lodestar implementation at temperature 0" is true by construction the
  moment this module calls `AnthropicJudge`, not something this module
  configures.
- `lodestar.metrics.stats.bootstrap_ci` -- the real bootstrap CI
  primitive. Fed a list of PER-PROMPT-GROUP delta statistics (one value
  per prompt, `mean(steered scores for that prompt) - mean(control scores
  for that prompt)`) rather than raw per-generation scores: resampling a
  list whose elements already ARE prompt-groups is what makes this a
  prompt-group bootstrap (matches `metadata.json["thresholds"]["ci_method"]
  == "SS9 prompt-group bootstrap; interval must exclude zero"`) without
  this module re-deriving the resampling arithmetic itself.

ARCHITECTURAL SEPARATION FROM THE GPU ALLOCATION -- STATED PLAINLY, NOT
SILENTLY WORKED AROUND: Tamia compute nodes have no internet access (this
project's own established, repeatedly-verified fact --
docs/final_pairing_tamia_packet.md's environment section, and this
project's `HF_HUB_OFFLINE=1` discipline throughout). `AnthropicJudge`
makes real network calls to the Anthropic API. This module CANNOT run its
live judge inside the scheduled dual-GPU allocation, and does not try to.
It is designed to run as a SEPARATE stage, on a machine with network
access (a login node, or off-cluster), consuming the `generations`
produced by the (offline) GPU discovery stage and already written to
disk, and returning a `causal_validation`-shaped result for the gates
G-D/G-E that a later step folds into the discovery document (see
`final_pairing_evidence_document.py`). This is a physical constraint, not
a deferred implementation -- no code in this file or any other changes
where a compute node's network cable is (or is not) connected.

FAIL-CLOSED, NEVER FAKED: if `lodestar` is not importable, or no
Anthropic API key is available, `build_live_causal_judge_runtime` raises
`CausalJudgeUnavailable`. This module never substitutes a mock/no-op
judge into a production call path -- exactly the rule
`interplab/validation/judge.py`'s `NoOpRubricJudge` docstring already
states for this codebase's other judge boundary: "running the test-only
StubRubricJudge against real production data would fabricate specificity
scores disguised as real ones."

TESTABILITY WITHOUT LODESTAR INSTALLED: `lodestar` is not pip-installed
into this repository's own environment (confirmed: `import lodestar`
raises `ModuleNotFoundError` here), so every lodestar import in this file
is LAZY (inside a function body, never at module scope) -- importing this
module must never require lodestar to be present. The gate-evaluation
functions below (`evaluate_gate_d`/`evaluate_gate_e`) are written against
plain duck-typed attributes (`.score`, `.generation_id`/`.prompt_id`),
which a real `lodestar.models.Judgment`/`Generation` satisfies and a
lightweight test double can satisfy too without importing lodestar at
all.
"""

from __future__ import annotations

import asyncio
import statistics
from dataclasses import dataclass
from typing import Any

LODESTAR_JUDGE_MODULE = "lodestar.judges.anthropic"
LODESTAR_JUDGE_CLASS = "AnthropicJudge"
LODESTAR_RUBRICS_MODULE = "lodestar.rubrics.steering"
LODESTAR_STATS_MODULE = "lodestar.metrics.stats"
COHERENCE_RUBRIC_NAME = "coherence"
COHERENCE_RUBRIC_VERSION = "1.0"
CONCEPT_RELEVANCE_RUBRIC_NAME = "concept_relevance"
CONCEPT_RELEVANCE_RUBRIC_VERSION = "1.0"

#: `metadata.json["thresholds"]["G_E_researcher_spot_read_outputs"]` -- a
#: spot read of fewer generations is not a spot read.
G_E_SPOT_READ_SAMPLE_SIZE = 10


class CausalJudgeUnavailable(RuntimeError):
    """Raised when the real Lodestar judge cannot run in this process: the
    `lodestar` package is not importable, or no API key is available.
    Never caught to fall back to a mock -- a caller that wants a
    structurally-passing test double must construct one explicitly and
    pass it to `evaluate_gate_d`/`evaluate_gate_e` directly, never through
    this function."""


def _import_lodestar_submodule(dotted: str):
    import importlib

    try:
        return importlib.import_module(dotted)
    except ImportError as error:
        raise CausalJudgeUnavailable(
            f"'{dotted}' is not importable in this environment -- G-D/G-E causal judging is a "
            f"SEPARATE stage from GPU discovery (see this module's docstring: Tamia compute nodes "
            f"have no internet, and Lodestar's judge requires the Anthropic API) and must run "
            f"wherever lodestar is installed and network access is available."
        ) from error


def build_live_causal_judge_runtime(*, judge_model: str, api_key: str | None = None) -> Any:
    """A real, network-backed `AnthropicJudge` at temperature 0 (baked
    into Lodestar itself -- see module docstring). Raises
    `CausalJudgeUnavailable` if `lodestar` is not importable or no API key
    is available; never falls back to a mock runtime."""
    import os

    module = _import_lodestar_submodule(LODESTAR_JUDGE_MODULE)
    judge_class = getattr(module, LODESTAR_JUDGE_CLASS, None)
    if judge_class is None:
        raise CausalJudgeUnavailable(f"{LODESTAR_JUDGE_MODULE} has no {LODESTAR_JUDGE_CLASS}")
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise CausalJudgeUnavailable(
            "ANTHROPIC_API_KEY is not set -- refusing to construct a live judge without one "
            "rather than falling back to an unauthenticated or mock runtime."
        )
    return judge_class(model_name=judge_model, api_key=key)


def load_steering_rubrics() -> tuple[Any, Any]:
    """Returns Lodestar's real `(COHERENCE, CONCEPT_RELEVANCE)` rubric
    objects, name/version "coherence"/"1.0" and "concept_relevance"/"1.0"
    respectively -- never re-authored here."""
    module = _import_lodestar_submodule(LODESTAR_RUBRICS_MODULE)
    coherence = module.COHERENCE
    concept_relevance = module.CONCEPT_RELEVANCE
    if (coherence.name, coherence.version) != (COHERENCE_RUBRIC_NAME, COHERENCE_RUBRIC_VERSION):
        raise CausalJudgeUnavailable(
            f"lodestar.rubrics.steering.COHERENCE is {coherence.name!r}/{coherence.version!r}, "
            f"expected {COHERENCE_RUBRIC_NAME!r}/{COHERENCE_RUBRIC_VERSION!r} -- refusing to use an "
            f"unexpected rubric identity for a gate whose threshold is calibrated against 1.0."
        )
    if (concept_relevance.name, concept_relevance.version) != (
        CONCEPT_RELEVANCE_RUBRIC_NAME, CONCEPT_RELEVANCE_RUBRIC_VERSION,
    ):
        raise CausalJudgeUnavailable(
            f"lodestar.rubrics.steering.CONCEPT_RELEVANCE is {concept_relevance.name!r}/"
            f"{concept_relevance.version!r}, expected {CONCEPT_RELEVANCE_RUBRIC_NAME!r}/"
            f"{CONCEPT_RELEVANCE_RUBRIC_VERSION!r}."
        )
    return coherence, concept_relevance


def run_judge_batch(judge: Any, items: list[tuple[Any, Any]], *, repeats: int = 1) -> list[Any]:
    """Runs `judge.judge_batch(items, repeats)` (Lodestar's real async
    protocol) to completion. `judge` and the generations inside `items`
    are duck-typed: a real `lodestar.judges.anthropic.AnthropicJudge` over
    real `lodestar.models.Generation` objects satisfies this in
    production; a test double satisfying the same async
    `judge_batch(items, repeats) -> list[Judgment-like]` shape (with
    `.score`/`.generation_id`) satisfies it in tests, without either this
    function or its callers importing `lodestar` at all."""
    if repeats < 1:
        raise ValueError("repeats must be at least one")
    return asyncio.run(judge.judge_batch(items, repeats))


def compute_prompt_group_bootstrap_ci(
    per_prompt_deltas: list[float], *, confidence: float = 0.95, n_resamples: int = 2000, seed: int = 42,
) -> tuple[float, float]:
    """SS9 prompt-group bootstrap CI on the MEAN per-prompt-group delta,
    computed by Lodestar's own real `bootstrap_ci` (never reimplemented
    here) fed a list whose elements already ARE one-per-prompt-group
    statistics -- resampling THIS list resamples prompt-groups, which is
    the entire content of "prompt-group" as opposed to "per-generation"
    bootstrapping."""
    if len(per_prompt_deltas) < 2:
        raise ValueError(
            f"a prompt-group bootstrap needs at least 2 prompt groups, got {len(per_prompt_deltas)}"
        )
    stats_module = _import_lodestar_submodule(LODESTAR_STATS_MODULE)
    import numpy as np

    return stats_module.bootstrap_ci(
        per_prompt_deltas, statistic=np.mean, confidence=confidence, n_resamples=n_resamples, seed=seed,
    )


def _per_prompt_mean(scores_by_prompt_and_generation: dict[str, list[float]]) -> dict[str, float]:
    return {prompt_id: statistics.fmean(scores) for prompt_id, scores in scores_by_prompt_and_generation.items()}


def _paired_deltas(
    steered_by_prompt: dict[str, list[float]], control_by_prompt: dict[str, list[float]],
) -> dict[str, float]:
    steered_means = _per_prompt_mean(steered_by_prompt)
    control_means = _per_prompt_mean(control_by_prompt)
    shared = sorted(set(steered_means) & set(control_means))
    if not shared:
        raise ValueError("no prompt_id is present in both the steered and control score maps")
    missing_steered = sorted(set(control_means) - set(steered_means))
    missing_control = sorted(set(steered_means) - set(control_means))
    if missing_steered or missing_control:
        raise ValueError(
            f"steered/control prompt coverage disagrees: missing from steered={missing_steered}, "
            f"missing from control={missing_control} -- a paired delta needs both arms for the "
            f"SAME prompt_id"
        )
    return {prompt_id: steered_means[prompt_id] - control_means[prompt_id] for prompt_id in shared}


@dataclass(frozen=True)
class GateDResult:
    relevance_delta: float
    relevance_delta_min: float
    ci_low: float
    ci_high: float
    ci_excludes_zero_in_amplify_direction: bool
    coherence_median: float
    coherence_median_min: float
    passed: bool


def evaluate_gate_d(
    *, steered_relevance_by_prompt: dict[str, list[float]], control_relevance_by_prompt: dict[str, list[float]],
    steered_coherence_scores: list[float], relevance_delta_min: float, coherence_median_min: float,
    seed: int = 42, bootstrap_ci_fn=compute_prompt_group_bootstrap_ci,
) -> GateDResult:
    """G-D (Amplify): relevance_delta >= relevance_delta_min, the SS9
    prompt-group bootstrap CI on that delta excludes zero IN THE AMPLIFY
    DIRECTION (`ci_low > 0`, never merely `0 not in [ci_low, ci_high]`
    with the wrong sign), and coherence_median >= coherence_median_min.
    Every one of the three must hold -- `passed` is their conjunction, not
    a weighted score.

    `bootstrap_ci_fn` defaults to the real, Lodestar-backed
    `compute_prompt_group_bootstrap_ci` (this project's established
    injectable-seam convention: a real default, substitutable in tests) --
    tests supply a numpy/scipy-only equivalent so this gate's PURE
    arithmetic (no network, no Anthropic API call) is exercisable without
    `lodestar` being importable, which is a genuinely separate concern
    from whether the JUDGE itself is available."""
    deltas = _paired_deltas(steered_relevance_by_prompt, control_relevance_by_prompt)
    relevance_delta = statistics.fmean(deltas.values())
    ci_low, ci_high = bootstrap_ci_fn(list(deltas.values()), seed=seed)
    ci_excludes_zero_amplify = ci_low > 0
    coherence_median = statistics.median(steered_coherence_scores)
    passed = (
        relevance_delta >= relevance_delta_min
        and ci_excludes_zero_amplify
        and coherence_median >= coherence_median_min
    )
    return GateDResult(
        relevance_delta=relevance_delta, relevance_delta_min=relevance_delta_min,
        ci_low=ci_low, ci_high=ci_high, ci_excludes_zero_in_amplify_direction=ci_excludes_zero_amplify,
        coherence_median=coherence_median, coherence_median_min=coherence_median_min, passed=passed,
    )


@dataclass(frozen=True)
class SpotReadPacket:
    sampled_generations: tuple[dict[str, str], ...]  # ({"prompt_id":..., "text":...}, ...), deterministic order


def build_spot_read_packet(
    suppressed_generations: list[dict[str, str]], *, sample_size: int = G_E_SPOT_READ_SAMPLE_SIZE,
) -> SpotReadPacket:
    """A deterministic 10-output Suppress spot-read packet: sorted by
    `prompt_id` (never by insertion order or a random sample), so the same
    generation set always produces the same packet for the researcher to
    read. Raises if fewer than `sample_size` generations are available --
    a spot read of fewer than the required count is not a spot read."""
    if len(suppressed_generations) < sample_size:
        raise ValueError(
            f"need at least {sample_size} suppressed generations for a spot read, got "
            f"{len(suppressed_generations)}"
        )
    ordered = sorted(suppressed_generations, key=lambda g: g["prompt_id"])
    return SpotReadPacket(sampled_generations=tuple(ordered[:sample_size]))


@dataclass(frozen=True)
class SpotReadDecision:
    approved: bool
    approved_by: str
    approved_at: str
    note: str
    sampled_generations: int


def resolve_spot_read_decision(
    packet: SpotReadPacket, *, approved: bool, approved_by: str, approved_at: str, note: str,
) -> SpotReadDecision:
    """The resume input for the researcher's explicit spot-read decision
    -- persisted verbatim by the caller (e.g. in `ProgressLog`), never
    inferred from gate statistics. A refusal (`approved=False`) is a
    complete, valid decision, not an error."""
    if not note.strip():
        raise ValueError("a spot-read decision requires a non-empty note")
    if not approved_by.strip():
        raise ValueError("a spot-read decision requires a non-empty approved_by")
    return SpotReadDecision(
        approved=approved, approved_by=approved_by, approved_at=approved_at, note=note,
        sampled_generations=len(packet.sampled_generations),
    )


@dataclass(frozen=True)
class GateEResult:
    relevance_delta: float
    relevance_delta_max: float
    ci_low: float
    ci_high: float
    ci_excludes_zero_in_suppress_direction: bool
    coherence_median: float
    coherence_median_min: float
    spot_read: SpotReadDecision | None
    passed: bool


def evaluate_gate_e(
    *, steered_relevance_by_prompt: dict[str, list[float]], control_relevance_by_prompt: dict[str, list[float]],
    steered_coherence_scores: list[float], relevance_delta_max: float, coherence_median_min: float,
    spot_read: SpotReadDecision | None, seed: int = 42, bootstrap_ci_fn=compute_prompt_group_bootstrap_ci,
) -> GateEResult:
    """G-E (Suppress): relevance_delta <= relevance_delta_max, the SS9
    bootstrap CI excludes zero IN THE SUPPRESS DIRECTION (`ci_high < 0`),
    coherence_median >= coherence_median_min, AND a researcher spot_read
    with `approved=True`. `passed` is False -- a null Suppress, never a
    partial one -- if EITHER the automated gate fails OR the spot read is
    missing/refused; an automated gate alone never establishes that
    suppression reads as suppression. `bootstrap_ci_fn`: see
    `evaluate_gate_d`'s docstring -- the same injectable seam."""
    deltas = _paired_deltas(steered_relevance_by_prompt, control_relevance_by_prompt)
    relevance_delta = statistics.fmean(deltas.values())
    ci_low, ci_high = bootstrap_ci_fn(list(deltas.values()), seed=seed)
    ci_excludes_zero_suppress = ci_high < 0
    coherence_median = statistics.median(steered_coherence_scores)
    automated_passed = (
        relevance_delta <= relevance_delta_max
        and ci_excludes_zero_suppress
        and coherence_median >= coherence_median_min
    )
    spot_read_approved = spot_read is not None and spot_read.approved
    return GateEResult(
        relevance_delta=relevance_delta, relevance_delta_max=relevance_delta_max,
        ci_low=ci_low, ci_high=ci_high, ci_excludes_zero_in_suppress_direction=ci_excludes_zero_suppress,
        coherence_median=coherence_median, coherence_median_min=coherence_median_min,
        spot_read=spot_read, passed=automated_passed and spot_read_approved,
    )
