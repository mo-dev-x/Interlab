"""interplab.jobs.judge (SS8 producer) -- reads one unjudged A9, runs the
isolated evaluation boundary, and writes a distinct immutable A9' with
materialized per-prompt scores and capability perplexities.

The source A9 is never mutated. Live Lodestar/capability execution remains
optional and fail-closed under ED-19: unavailable or malformed runtime
behavior maps to exit 4 with one failed RunCard and no A9'.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from interplab.core import envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.evaluation import capability as capability_mod
from interplab.evaluation import lodestar_adapter as adapter_mod
from interplab.registry.config_lifecycle import prepare_job_run
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put


def _judge_inputs(config: dict) -> list[dict]:
    source_hash = config["intervention_result_hash"]
    slice_ref = config["capability_slice"]
    return [
        {
            "content_hash": source_hash,
            "location": f"local:registry/intervention_result/{hashing.short_hash(source_hash)}.json",
            "role": "intervention_result",
        },
        {
            "content_hash": slice_ref["content_hash"],
            "location": slice_ref["location"],
            "role": "capability_slice",
        },
    ]


def _get_or_raise(content_hash: str, *, registry_root: Path, role: str) -> dict:
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except Exception as error:
        raise ContractViolationError(f"could not resolve {role} {content_hash!r}: {error}") from error


def _resolve_local_or_tamia(location: str, *, what: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        return uris.resolve_local(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    raise NotImplementedError(f"judge can only load {what} from local:/tamia: URIs; got {location!r}")


def _load_json_file(path: Path, *, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ContractViolationError(f"missing {what} at {path}") from error
    except json.JSONDecodeError as error:
        raise ContractViolationError(f"{what} at {path} is not valid JSON: {error}") from error


def _validate_unjudged_source(source: dict) -> None:
    if source["artifact_type"] != "intervention_result":
        raise ContractViolationError(
            f"resolved source {source['self_hash']!r} has artifact_type {source['artifact_type']!r}, "
            "expected 'intervention_result'"
        )
    if any(ref["role"] == "judged_from" for ref in source["subject"]):
        raise ContractViolationError(
            f"source intervention_result {source['self_hash']!r} is already a judged A9' "
            "(subject role 'judged_from')"
        )
    payload = source["payload"]
    if payload.get("lodestar") is not None or payload.get("capability_delta") is not None:
        raise ContractViolationError(
            f"source intervention_result {source['self_hash']!r} is already populated with SS8 outputs"
        )
    if payload["blinding"]["shuffled"] is not True or payload["blinding"]["map_ref"] is None:
        raise ContractViolationError(
            f"source intervention_result {source['self_hash']!r} is missing the required shuffled blinding map"
        )


def _resolve_generation_bundle(source: dict) -> tuple[list[dict], dict[str, dict]]:
    generation_refs = {
        (
            arm["generations_ref"]["content_hash"],
            arm["generations_ref"]["location"],
        )
        for arm in source["payload"]["arms"]
    }
    if not generation_refs:
        raise ContractViolationError(
            f"source intervention_result {source['self_hash']!r} carries no generations_ref entries"
        )
    if len(generation_refs) != 1:
        raise ContractViolationError(
            f"source intervention_result {source['self_hash']!r} carries multiple generations_ref targets"
        )

    generations_hash, generations_location = next(iter(generation_refs))
    generations_dir = _resolve_local_or_tamia(generations_location, what="the generations bundle")
    if not generations_dir.is_dir():
        raise ContractViolationError(f"generations bundle {generations_dir} is missing or not a directory")
    actual_hash = hashing.hash_directory(generations_dir)
    if actual_hash != generations_hash:
        raise ContractViolationError(
            f"generations bundle hash mismatch: stored={generations_hash!r} recomputed={actual_hash!r}"
        )

    map_path = _resolve_local_or_tamia(source["payload"]["blinding"]["map_ref"], what="the blinding map")
    generations_payload = _load_json_file(generations_dir / "generations.json", what="generations.json")
    if not isinstance(generations_payload, dict) or "records" not in generations_payload:
        raise ContractViolationError("generations.json must contain an object with a 'records' field")
    correlation_map = _load_json_file(map_path, what="blinding_map.json")
    try:
        grid = adapter_mod.build_blinded_records(
            generations_payload["records"], correlation_map, source["payload"]["arms"]
        )
    except adapter_mod.SourceArtifactError as error:
        raise ContractViolationError(str(error)) from error
    return grid.blinded_records, grid


def _load_and_verify_capability_slice(slice_ref: dict) -> Path:
    slice_path = _resolve_local_or_tamia(slice_ref["location"], what="the capability slice")
    if not slice_path.is_file():
        raise ContractViolationError(f"capability slice {slice_path} is missing or not a file")
    actual_hash = hashing.hash_file(slice_path)
    if actual_hash != slice_ref["content_hash"]:
        raise ContractViolationError(
            f"capability slice hash mismatch: stored={slice_ref['content_hash']!r} recomputed={actual_hash!r}"
        )
    return slice_path


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    prepared = prepare_job_run(
        stage="judge",
        job_name="judge",
        config_path=config_path,
        build_inputs=_judge_inputs,
        registry_root=registry_root,
        repo_root=repo_root,
    )
    if prepared is None:
        return 3
    config, handle = prepared
    source_ref, _slice_ref = _judge_inputs(config)

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        source = _get_or_raise(
            config["intervention_result_hash"], registry_root=registry_root, role="intervention_result"
        )
        _validate_unjudged_source(source)
        blinded_records, validated_grid = _resolve_generation_bundle(source)
        slice_path = _load_and_verify_capability_slice(config["capability_slice"])
        sealed_source_hash = source["self_hash"]
        sealed_schema_version = source["schema_version"]
        sealed_subject = copy.deepcopy(source["subject"])
        sealed_payload = copy.deepcopy(source["payload"])
        sealed_slice_ref = copy.deepcopy(config["capability_slice"])

        runtime = adapter_mod.build_live_runtime()
        judge_result = runtime.evaluate(copy.deepcopy(blinded_records), config=copy.deepcopy(config))
        per_prompt_scores = adapter_mod.materialize_per_prompt_scores(judge_result.scores, validated_grid)

        measurement = runtime.measure_capability(
            source_artifact=copy.deepcopy(source),
            slice_path=slice_path,
            slice_ref=copy.deepcopy(sealed_slice_ref),
            config=copy.deepcopy(config),
        )
        normalized = adapter_mod.validate_capability_measurement(measurement, validated_grid)
        capability_delta = capability_mod.assemble_capability_delta(
            slice_ref=sealed_slice_ref,
            n_tokens=normalized.n_tokens,
            per_arm=normalized.per_arm,
        )

        payload = sealed_payload
        payload["lodestar"] = {
            "run_ref": judge_result.run_ref,
            "judge_model": judge_result.judge_model,
            "rubric_version": judge_result.rubric_version,
            "per_prompt_scores": per_prompt_scores,
        }
        payload["capability_delta"] = capability_delta

        judged_from_ref = {
            "content_hash": sealed_source_hash,
            "location": source_ref["location"],
            "role": "judged_from",
        }
        artifact = envelope.dump(
            artifact_type="intervention_result",
            schema_version=sealed_schema_version,
            created_by=handle.created_by,
            subject=[*sealed_subject, judged_from_ref],
            payload=payload,
        )
        result_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {
                "content_hash": result_hash,
                "location": f"local:registry/intervention_result/{hashing.short_hash(result_hash)}.json",
                "role": "intervention_result",
            }
        ]
        status, exit_code = "completed", 0
        outcome_line = (
            f"judged intervention_result {hashing.short_hash(result_hash)} from "
            f"{hashing.short_hash(sealed_source_hash)}"
        )

    except ContractViolationError as error:
        status, exit_code = "failed", 3
        outcome_line = str(error)
    except adapter_mod.EvaluationRuntimeError as error:
        status, exit_code = "failed", 4
        outcome_line = str(error)
    except Exception as error:
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {error}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
