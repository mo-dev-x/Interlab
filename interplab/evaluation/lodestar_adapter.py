"""SS8 judge-facing adapter boundary.

Transforms A9's shuffled generation bundle into judge-safe blinded inputs,
validates returned score identities before any registry write, and keeps all
optional `lodestar` imports isolated here. The locked Interlab environment
does not currently ship a live Lodestar runtime under ED-19, so the default
runtime factory fails closed unless a future optional `lodestar.interlab`
adapter is published.
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from numbers import Real
from typing import Protocol

from interplab.evaluation.blinding import BlindedRecord

_ARM_ORDER = {
    "baseline": 0,
    "steered": 1,
    "random_direction": 2,
    "random_feature": 3,
    "prompt_baseline": 4,
}


class SourceArtifactError(ValueError):
    """Malformed or internally inconsistent A9-side data."""


class EvaluationRuntimeError(RuntimeError):
    """Unavailable or malformed external evaluation runtime/results."""


@dataclass(frozen=True)
class BlindScore:
    blind_id: str
    score: float


@dataclass(frozen=True)
class JudgeRunResult:
    run_ref: str
    judge_model: str
    rubric_version: str
    prompt_version: str | None
    scores: list[BlindScore]


@dataclass(frozen=True)
class CapabilityMeasurement:
    n_tokens: int
    per_arm: list[tuple[str, float | None, float]]


@dataclass(frozen=True)
class ValidatedSourceGrid:
    blinded_records: list[BlindedRecord]
    correlation_map: dict[str, dict]
    declared_cells: tuple[tuple[str, float | None], ...]
    experimental_scales: tuple[float, ...]
    prompt_ids: tuple[str, ...]


class EvaluationRuntime(Protocol):
    def evaluate(self, records: list[BlindedRecord], *, config: dict) -> JudgeRunResult: ...

    def measure_capability(
        self,
        *,
        source_artifact: dict,
        slice_path,
        slice_ref: dict,
        config: dict,
    ) -> CapabilityMeasurement: ...


def build_blinded_records(
    records: list[dict], correlation_map: dict[str, dict], declared_arms: list[dict]
) -> ValidatedSourceGrid:
    if not isinstance(records, list):
        raise SourceArtifactError(f"generations.json 'records' must be a list, got {type(records).__name__}")
    if not isinstance(correlation_map, dict):
        raise SourceArtifactError(
            f"blinding_map.json must contain an object, got {type(correlation_map).__name__}"
        )
    if len(records) != len(correlation_map):
        raise SourceArtifactError(
            f"generation/blinding length mismatch: {len(records)} records vs {len(correlation_map)} blind ids"
        )
    if not records:
        raise SourceArtifactError("source A9 generation grid must contain at least one record")
    if not isinstance(declared_arms, list):
        raise SourceArtifactError(
            f"source payload.arms must be a list, got {type(declared_arms).__name__}"
        )

    declared_arm_scales: dict[str, tuple[float, ...]] = {}
    for index, arm_entry in enumerate(declared_arms):
        if not isinstance(arm_entry, dict):
            raise SourceArtifactError(f"payload.arms[{index}] must be an object, got {type(arm_entry).__name__}")
        if "arm" not in arm_entry or "scales_in_max_units" not in arm_entry:
            raise SourceArtifactError(f"payload.arms[{index}] must contain 'arm' and 'scales_in_max_units'")
        arm = str(arm_entry["arm"])
        if arm in declared_arm_scales:
            raise SourceArtifactError(f"payload.arms declares duplicate arm {arm!r}")
        scales_value = arm_entry["scales_in_max_units"]
        if not isinstance(scales_value, list):
            raise SourceArtifactError(
                f"payload.arms[{index}].scales_in_max_units must be a list, got {type(scales_value).__name__}"
            )
        normalized_scales: list[float] = []
        seen_scales: set[float] = set()
        for scale in scales_value:
            if isinstance(scale, bool) or not isinstance(scale, Real):
                raise SourceArtifactError(f"declared scale for arm {arm!r} must be numeric, got {scale!r}")
            normalized = float(scale)
            if not math.isfinite(normalized):
                raise SourceArtifactError(f"declared scale for arm {arm!r} must be finite, got {scale!r}")
            if normalized in seen_scales:
                raise SourceArtifactError(f"payload.arms declares duplicate scale {normalized!r} for arm {arm!r}")
            seen_scales.add(normalized)
            normalized_scales.append(normalized)
        declared_arm_scales[arm] = tuple(normalized_scales)

    declared_cells = tuple(
        (arm, scale)
        for arm, scales in declared_arm_scales.items()
        for scale in (scales if scales else (None,))
    )
    experimental_scales = tuple(
        sorted({scale for _arm, scales in declared_arm_scales.items() for scale in scales})
    )
    if not experimental_scales:
        raise SourceArtifactError("source A9 declares no experimental scales")

    blinded: list[BlindedRecord] = []
    normalized_map: dict[str, dict] = {}
    seen_cells: set[tuple[str, str, float | None]] = set()
    prompt_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise SourceArtifactError(
                f"generation record {index} must be an object, got {type(record).__name__}"
            )
        blind_id = f"blind-{index:06d}"
        if blind_id not in correlation_map:
            raise SourceArtifactError(f"blinding map is missing {blind_id!r}")
        mapped = correlation_map[blind_id]
        if not isinstance(mapped, dict):
            raise SourceArtifactError(
                f"blinding map entry {blind_id!r} must be an object, got {type(mapped).__name__}"
            )
        for field in ("arm", "scale", "prompt_id"):
            if field not in mapped:
                raise SourceArtifactError(f"blinding map entry {blind_id!r} is missing {field!r}")
        for field in ("arm", "scale", "prompt_id"):
            if record.get(field) != mapped[field]:
                raise SourceArtifactError(
                    f"blinding map mismatch for {blind_id!r}: record {field}={record.get(field)!r} "
                    f"!= map {field}={mapped[field]!r}"
                )
        if "text" not in record or "prompt" not in record:
            raise SourceArtifactError(f"generation record {index} must contain 'text' and 'prompt'")
        arm = str(mapped["arm"])
        if arm not in declared_arm_scales:
            raise SourceArtifactError(f"generation record {index} uses undeclared arm {arm!r}")
        declared_scales = declared_arm_scales[arm]
        raw_scale = mapped["scale"]
        if raw_scale is None:
            if declared_scales:
                raise SourceArtifactError(
                    f"generation record {index} uses null scale for arm {arm!r}, which declares non-null scales"
                )
            normalized_scale = None
        else:
            if isinstance(raw_scale, bool) or not isinstance(raw_scale, Real):
                raise SourceArtifactError(
                    f"generation record {index} has non-numeric scale {raw_scale!r} for arm {arm!r}"
                )
            normalized_scale = float(raw_scale)
            if not math.isfinite(normalized_scale):
                raise SourceArtifactError(
                    f"generation record {index} has non-finite scale {raw_scale!r} for arm {arm!r}"
                )
            if not declared_scales:
                raise SourceArtifactError(
                    f"generation record {index} uses scale {normalized_scale!r} for null-scale arm {arm!r}"
                )
            if normalized_scale not in declared_scales:
                raise SourceArtifactError(
                    f"generation record {index} uses undeclared scale {normalized_scale!r} for arm {arm!r}"
                )
        prompt_id = str(mapped["prompt_id"])
        identity = (prompt_id, arm, normalized_scale)
        if identity in seen_cells:
            raise SourceArtifactError(f"duplicate generation identity {identity!r}")
        seen_cells.add(identity)
        prompt_ids.add(prompt_id)
        blinded.append(
            BlindedRecord(
                blind_id=blind_id,
                text=str(record["text"]),
                prompt=str(record["prompt"]),
            )
        )
        normalized_map[blind_id] = {
            "arm": arm,
            "scale": normalized_scale,
            "prompt_id": prompt_id,
        }

    extra = sorted(set(correlation_map) - set(normalized_map))
    if extra:
        raise SourceArtifactError(f"blinding map contains unknown blind ids: {extra}")
    if not prompt_ids:
        raise SourceArtifactError("source A9 generation grid must contain at least one prompt")
    expected_cells = {
        (prompt_id, arm, scale)
        for prompt_id in prompt_ids
        for arm, scale in declared_cells
    }
    missing = sorted(expected_cells - seen_cells)
    if missing:
        raise SourceArtifactError(f"source A9 generation grid is missing declared prompt/arm/scale cells: {missing}")

    return ValidatedSourceGrid(
        blinded_records=blinded,
        correlation_map=normalized_map,
        declared_cells=tuple(sorted(declared_cells, key=lambda item: (_ARM_ORDER[item[0]], -1.0 if item[1] is None else item[1]))),
        experimental_scales=experimental_scales,
        prompt_ids=tuple(sorted(prompt_ids)),
    )


def materialize_per_prompt_scores(
    scores: list[BlindScore], grid: ValidatedSourceGrid
) -> list[dict]:
    if not isinstance(scores, list):
        raise EvaluationRuntimeError(f"judge scores must be a list, got {type(scores).__name__}")

    seen_ids: set[str] = set()
    output: list[dict] = []
    seen_triples: set[tuple[str, str, float]] = set()
    for item in scores:
        if not isinstance(item, BlindScore):
            raise EvaluationRuntimeError(
                f"judge scores must contain BlindScore entries, got {type(item).__name__}"
            )
        blind_id = item.blind_id
        if blind_id in seen_ids:
            raise EvaluationRuntimeError(f"judge returned duplicate blind_id {blind_id!r}")
        seen_ids.add(blind_id)
        if blind_id not in grid.correlation_map:
            raise EvaluationRuntimeError(f"judge returned unknown blind_id {blind_id!r}")
        if isinstance(item.score, bool) or not isinstance(item.score, Real):
            raise EvaluationRuntimeError(
                f"judge returned a non-numeric score for {blind_id!r}: {item.score!r}"
            )
        score_value = float(item.score)
        if not math.isfinite(score_value):
            raise EvaluationRuntimeError(f"judge returned a non-finite score for {blind_id!r}: {item.score!r}")
        meta = grid.correlation_map[blind_id]
        scales = grid.experimental_scales if meta["scale"] is None else [float(meta["scale"])]
        for scale in scales:
            triple = (str(meta["prompt_id"]), str(meta["arm"]), scale)
            if triple in seen_triples:
                raise EvaluationRuntimeError(
                    f"judge correlation produced duplicate prompt/arm/scale identity {triple!r}"
                )
            seen_triples.add(triple)
            output.append(
                {
                    "prompt_id": str(meta["prompt_id"]),
                    "arm": str(meta["arm"]),
                    "scale": scale,
                    "score": score_value,
                }
            )

    missing = sorted(set(grid.correlation_map) - seen_ids)
    if missing:
        raise EvaluationRuntimeError(f"judge did not return scores for blind ids: {missing}")
    expected = {
        (prompt_id, arm, expanded_scale)
        for prompt_id in grid.prompt_ids
        for arm, scale in grid.declared_cells
        for expanded_scale in (grid.experimental_scales if scale is None else (scale,))
    }
    actual = {(entry["prompt_id"], entry["arm"], entry["scale"]) for entry in output}
    if actual != expected:
        raise EvaluationRuntimeError(
            f"judge correlation produced incomplete per-prompt score coverage: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )

    output.sort(key=lambda entry: (entry["prompt_id"], _ARM_ORDER[entry["arm"]], entry["scale"]))
    return output


def validate_capability_measurement(
    measurement: CapabilityMeasurement, grid: ValidatedSourceGrid
) -> CapabilityMeasurement:
    if isinstance(measurement.n_tokens, bool) or not isinstance(measurement.n_tokens, int):
        raise EvaluationRuntimeError(
            f"capability n_tokens must be a non-boolean integer, got {measurement.n_tokens!r}"
        )
    if measurement.n_tokens < 0:
        raise EvaluationRuntimeError(f"capability n_tokens must be >= 0, got {measurement.n_tokens}")

    expected = set(grid.declared_cells)
    seen: set[tuple[str, float | None]] = set()
    normalized: list[tuple[str, float | None, float]] = []
    for item in measurement.per_arm:
        if not isinstance(item, tuple) or len(item) != 3:
            raise EvaluationRuntimeError(
                f"capability entries must be (arm, scale, ppl) triples, got {item!r}"
            )
        arm, scale, ppl = item
        if scale is None:
            normalized_scale = None
        else:
            if isinstance(scale, bool) or not isinstance(scale, Real):
                raise EvaluationRuntimeError(f"capability scale for arm {arm!r} must be numeric, got {scale!r}")
            normalized_scale = float(scale)
            if not math.isfinite(normalized_scale):
                raise EvaluationRuntimeError(
                    f"capability scale for arm {arm!r} must be finite, got {scale!r}"
                )
        identity = (str(arm), normalized_scale)
        if identity in seen:
            raise EvaluationRuntimeError(f"capability output duplicated arm/scale identity {identity!r}")
        seen.add(identity)
        if isinstance(ppl, bool) or not isinstance(ppl, Real):
            raise EvaluationRuntimeError(f"capability ppl for {identity!r} must be numeric, got {ppl!r}")
        normalized_ppl = float(ppl)
        if not math.isfinite(normalized_ppl):
            raise EvaluationRuntimeError(f"capability ppl for {identity!r} must be finite, got {ppl!r}")
        if normalized_ppl < 0:
            raise EvaluationRuntimeError(f"capability ppl for {identity!r} must be >= 0, got {ppl!r}")
        normalized.append((str(arm), identity[1], normalized_ppl))

    missing = sorted(expected - seen)
    extra = sorted(seen - expected)
    if missing or extra:
        raise EvaluationRuntimeError(
            f"capability output arm/scale mismatch: missing={missing or []}, extra={extra or []}"
        )

    normalized.sort(key=lambda item: (_ARM_ORDER[item[0]], -1.0 if item[1] is None else item[1]))
    return CapabilityMeasurement(n_tokens=measurement.n_tokens, per_arm=normalized)


def build_live_runtime() -> EvaluationRuntime:
    """Resolve an optional live Lodestar runtime.

    The sanctioned Interlab lock does not currently provide one, so this
    factory raises a closed-failure `EvaluationRuntimeError` unless a future
    optional `lodestar.interlab.make_interplab_runtime()` hook exists.
    """

    try:
        module = importlib.import_module("lodestar.interlab")
    except ImportError as error:
        try:
            importlib.import_module("lodestar")
        except ImportError as inner:
            raise EvaluationRuntimeError(
                "live Lodestar runtime unavailable under ED-19: optional dependency 'lodestar' is not installed"
            ) from inner
        raise EvaluationRuntimeError(
            "live Lodestar runtime unavailable: expected optional adapter module "
            "'lodestar.interlab' exposing make_interplab_runtime()"
        ) from error

    factory = getattr(module, "make_interplab_runtime", None)
    if factory is None:
        raise EvaluationRuntimeError(
            "live Lodestar runtime unavailable: lodestar.interlab exposes no make_interplab_runtime()"
        )
    runtime = factory()
    if not hasattr(runtime, "evaluate") or not hasattr(runtime, "measure_capability"):
        raise EvaluationRuntimeError(
            "live Lodestar runtime unavailable: runtime object must expose evaluate() and measure_capability()"
        )
    return runtime
