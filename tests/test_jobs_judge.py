"""§6.1 judge job (SS8 producer): immutable A9 -> A9' ingestion, blinding
correlation integrity, capability payload assembly, and fail-closed runtime
behavior under ED-17/19/20/21."""

from __future__ import annotations

import copy
import json
import math
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope, hashing, uris
from interplab.evaluation import lodestar_adapter as adapter_mod
from interplab.jobs import judge
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from tests.job_test_helpers import (
    assert_failed_invalid_config_run_card,
    assert_only_run_card_written,
)

_CHECKPOINT_HASH = "sha256:" + "1" * 64
_FEATURE_CERT_HASH = "sha256:" + "2" * 64
_SLICE_LINES = ['{"text":"alpha beta"}', '{"text":"gamma delta"}']


def _created_by():
    return {"run_id": "r20260728-0000-jd00", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


@pytest.fixture
def scratch_dir(tmp_path):
    path = uris.REPO_ROOT / "results" / "_test_scratch" / f"jobs_judge_{tmp_path.name}"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _write_slice(scratch_dir: Path) -> dict:
    path = scratch_dir / "capability_slice.jsonl"
    path.write_text("\n".join(_SLICE_LINES) + "\n", encoding="utf-8")
    return {
        "content_hash": hashing.hash_file(path),
        "location": f"local:{path.relative_to(uris.REPO_ROOT).as_posix()}",
    }


def _source_records():
    return [
        {"arm": "steered", "scale": 2.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "steered two"},
        {"arm": "baseline", "scale": None, "prompt_id": "p0", "prompt": "Explain zero", "text": "base zero"},
        {"arm": "random_feature", "scale": 1.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "rf zero"},
        {"arm": "steered", "scale": 1.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "steered zero"},
        {"arm": "prompt_baseline", "scale": None, "prompt_id": "p1", "prompt": "Baseline alpha", "text": "pb alpha"},
        {"arm": "random_direction", "scale": 2.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "rd zero two"},
        {"arm": "random_direction", "scale": 1.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "rd alpha"},
        {"arm": "random_feature", "scale": 2.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "rf alpha"},
        {"arm": "baseline", "scale": None, "prompt_id": "p1", "prompt": "Explain alpha", "text": "base alpha"},
        {"arm": "steered", "scale": 1.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "steered alpha"},
        {"arm": "random_direction", "scale": 1.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "rd zero"},
        {"arm": "random_direction", "scale": 2.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "rd alpha two"},
        {"arm": "prompt_baseline", "scale": None, "prompt_id": "p0", "prompt": "Baseline zero", "text": "pb zero"},
        {"arm": "random_feature", "scale": 1.0, "prompt_id": "p1", "prompt": "Explain alpha", "text": "rf alpha one"},
        {"arm": "steered", "scale": 2.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "steered zero two"},
        {"arm": "random_feature", "scale": 2.0, "prompt_id": "p0", "prompt": "Explain zero", "text": "rf zero two"},
    ]


def _write_generation_bundle(
    scratch_dir: Path,
    *,
    records: list[dict] | None = None,
    map_overrides: dict[str, dict] | None = None,
) -> tuple[dict, list[dict]]:
    gen_dir = scratch_dir / "generations_bundle"
    gen_dir.mkdir(parents=True, exist_ok=True)
    records = list(_source_records() if records is None else records)
    (gen_dir / "generations.json").write_text(
        json.dumps({"records": records}, indent=2), encoding="utf-8"
    )
    correlation_map = {
        f"blind-{index:06d}": {
            "arm": record["arm"],
            "scale": record["scale"],
            "prompt_id": record["prompt_id"],
        }
        for index, record in enumerate(records)
    }
    if map_overrides:
        for blind_id, value in map_overrides.items():
            correlation_map[blind_id] = value
    (gen_dir / "blinding_map.json").write_text(
        json.dumps(correlation_map, indent=2), encoding="utf-8"
    )
    return {
        "generations_ref": {
            "content_hash": hashing.hash_directory(gen_dir),
            "location": f"local:{gen_dir.relative_to(uris.REPO_ROOT).as_posix()}",
        },
        "map_ref": f"local:{(gen_dir / 'blinding_map.json').relative_to(uris.REPO_ROOT).as_posix()}",
    }, records


def _arms_payload(generations_ref: dict) -> list[dict]:
    return [
        {"arm": "steered", "scales_in_max_units": [1.0, 2.0], "generations_ref": generations_ref},
        {"arm": "baseline", "scales_in_max_units": [], "generations_ref": generations_ref},
        {"arm": "random_direction", "scales_in_max_units": [1.0, 2.0], "generations_ref": generations_ref},
        {"arm": "random_feature", "scales_in_max_units": [1.0, 2.0], "generations_ref": generations_ref},
        {"arm": "prompt_baseline", "scales_in_max_units": [], "generations_ref": generations_ref},
    ]


def _register_source_a9(
    registry_root: Path,
    scratch_dir: Path,
    *,
    records: list[dict] | None = None,
    arms_payload: list[dict] | Callable[[dict], list[dict]] | None = None,
    map_overrides: dict[str, dict] | None = None,
) -> tuple[dict, list[dict]]:
    bundle, records = _write_generation_bundle(scratch_dir, records=records, map_overrides=map_overrides)
    if callable(arms_payload):
        resolved_arms_payload = arms_payload(bundle["generations_ref"])
    elif arms_payload is None:
        resolved_arms_payload = _arms_payload(bundle["generations_ref"])
    else:
        resolved_arms_payload = arms_payload
    artifact = envelope.dump(
        artifact_type="intervention_result",
        schema_version=1,
        created_by=_created_by(),
        subject=[
            {"content_hash": _CHECKPOINT_HASH, "location": "local:registry/sae_checkpoint/x.json", "role": "sae_checkpoint"},
            {"content_hash": _FEATURE_CERT_HASH, "location": "local:registry/feature_certificate/x.json", "role": "feature_certificate"},
        ],
        payload={
            "spec": {
                "kind": "clamp",
                "feature_index": 9,
                "value_in_max_units": None,
                "corpus_max": 5.0,
                "positions": "all",
                "checkpoint_hash": _CHECKPOINT_HASH,
                "direction_seed": None,
            },
            "arms": resolved_arms_payload,
            "blinding": {"shuffled": True, "map_ref": bundle["map_ref"]},
            "sampling": {"temperature": 0.0, "top_p": 1.0, "max_new_tokens": 8, "seed": 0},
            "lodestar": None,
            "capability_delta": None,
        },
    )
    content_hash = registry_put(artifact, registry_root=registry_root)
    return registry_get(content_hash, registry_root=registry_root), records


def _register_eval_compat_map(registry_root: Path) -> dict:
    artifact = envelope.dump(
        artifact_type="eval_compat_map",
        schema_version=1,
        created_by=_created_by(),
        subject=[],
        payload={"version": 1, "judge_classes": []},
    )
    content_hash = registry_put(artifact, registry_root=registry_root)
    return registry_get(content_hash, registry_root=registry_root)


def _expected_score_cells():
    scales = (1.0, 2.0)
    prompt_ids = ("p0", "p1")
    cells = set()
    for prompt_id in prompt_ids:
        for scale in scales:
            cells.add((prompt_id, "baseline", scale))
            cells.add((prompt_id, "steered", scale))
            cells.add((prompt_id, "random_direction", scale))
            cells.add((prompt_id, "random_feature", scale))
            cells.add((prompt_id, "prompt_baseline", scale))
    return cells


def _write_config(tmp_path: Path, source_hash: str, slice_ref: dict) -> Path:
    cfg_path = tmp_path / "judge.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "intervention_result_hash": source_hash,
                "capability_slice": slice_ref,
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def _score_map() -> dict[str, float]:
    return {
        "base zero": 0.2,
        "base alpha": 0.9,
        "steered zero": 0.4,
        "steered zero two": 1.4,
        "steered alpha": 1.0,
        "steered two": 0.1,
        "rd zero": 1.1,
        "rd zero two": 0.6,
        "rd alpha": 0.7,
        "rd alpha two": 0.8,
        "rf zero": 0.3,
        "rf zero two": 1.5,
        "rf alpha one": 1.3,
        "rf alpha": 0.8,
        "pb zero": 1.2,
        "pb alpha": 0.5,
    }


class _FakeRuntime:
    def __init__(self, scores_by_text: dict[str, float]):
        self.records_seen = None
        self._scores_by_text = scores_by_text

    def evaluate(self, records, *, config):
        self.records_seen = records
        return adapter_mod.JudgeRunResult(
            run_ref="lodestar:run/fake",
            judge_model="lodestar-stub",
            rubric_version="stub-v1",
            prompt_version="stub-v1",
            scores=[
                adapter_mod.BlindScore(blind_id=record.blind_id, score=self._scores_by_text[record.text])
                for record in records
            ],
        )

    def measure_capability(self, *, source_artifact, slice_path, slice_ref, config):
        assert slice_path.is_file()
        assert slice_ref["content_hash"] == hashing.hash_file(slice_path)
        return adapter_mod.CapabilityMeasurement(
            n_tokens=128,
            per_arm=[
                ("baseline", None, 10.0),
                ("steered", 1.0, 11.0),
                ("steered", 2.0, 12.0),
                ("random_direction", 1.0, 13.0),
                ("random_direction", 2.0, 14.0),
                ("random_feature", 1.0, 15.0),
                ("random_feature", 2.0, 16.0),
                ("prompt_baseline", None, 10.5),
            ],
        )


class _MutatingRuntime(_FakeRuntime):
    def __init__(self, scores_by_text: dict[str, float], *, source_hash: str, slice_ref: dict):
        super().__init__(scores_by_text)
        self._expected_source_hash = source_hash
        self._expected_slice_ref = slice_ref
        self.evaluate_config_seen = None
        self.measure_source_seen = None
        self.measure_slice_ref_seen = None
        self.measure_config_seen = None

    def evaluate(self, records, *, config):
        original_records = list(records)
        self.records_seen = original_records
        self.evaluate_config_seen = copy.deepcopy(config)
        records.clear()
        records.append(adapter_mod.BlindedRecord(blind_id="blind-mutation", text="mutated", prompt="mutated"))
        config["intervention_result_hash"] = "sha256:" + "9" * 64
        config["capability_slice"]["content_hash"] = "sha256:" + "8" * 64
        config["capability_slice"]["location"] = "local:mutated/evaluate.jsonl"
        return adapter_mod.JudgeRunResult(
            run_ref="lodestar:run/fake",
            judge_model="lodestar-stub",
            rubric_version="stub-v1",
            prompt_version="stub-v1",
            scores=[
                adapter_mod.BlindScore(blind_id=record.blind_id, score=self._scores_by_text[record.text])
                for record in original_records
            ],
        )

    def measure_capability(self, *, source_artifact, slice_path, slice_ref, config):
        assert source_artifact["self_hash"] == self._expected_source_hash
        assert slice_ref == self._expected_slice_ref
        self.measure_source_seen = copy.deepcopy(source_artifact)
        self.measure_slice_ref_seen = copy.deepcopy(slice_ref)
        self.measure_config_seen = copy.deepcopy(config)
        assert slice_path.is_file()
        assert slice_ref["content_hash"] == hashing.hash_file(slice_path)
        source_artifact["payload"]["spec"]["feature_index"] = 777
        source_artifact["payload"]["sampling"]["seed"] = 999
        source_artifact["payload"]["blinding"]["map_ref"] = "local:mutated/map.json"
        source_artifact["payload"]["arms"][0]["arm"] = "mutated_arm"
        source_artifact["subject"].append(
            {"content_hash": "sha256:" + "7" * 64, "location": "local:mutated/subject.json", "role": "mutated"}
        )
        slice_ref["content_hash"] = "sha256:" + "6" * 64
        slice_ref["location"] = "local:mutated/slice.jsonl"
        config["capability_slice"]["content_hash"] = "sha256:" + "5" * 64
        config["capability_slice"]["location"] = "local:mutated/config-slice.jsonl"
        config["intervention_result_hash"] = "sha256:" + "4" * 64
        return adapter_mod.CapabilityMeasurement(
            n_tokens=128,
            per_arm=[
                ("baseline", None, 10.0),
                ("steered", 1.0, 11.0),
                ("steered", 2.0, 12.0),
                ("random_direction", 1.0, 13.0),
                ("random_direction", 2.0, 14.0),
                ("random_feature", 1.0, 15.0),
                ("random_feature", 2.0, 16.0),
                ("prompt_baseline", None, 10.5),
            ],
        )


class _RuntimeWithBadScores(_FakeRuntime):
    def __init__(self, bad_score):
        self.records_seen = None
        self._bad_score = bad_score

    def evaluate(self, records, *, config):
        self.records_seen = records
        scores = [
            adapter_mod.BlindScore(
                blind_id=record.blind_id,
                score=self._bad_score if index == 0 else 0.5 + index,
            )
            for index, record in enumerate(records)
        ]
        return adapter_mod.JudgeRunResult(
            run_ref="lodestar:run/fake",
            judge_model="lodestar-stub",
            rubric_version="stub-v1",
            prompt_version="stub-v1",
            scores=scores,
        )

    def measure_capability(self, *, source_artifact, slice_path, slice_ref, config):
        raise AssertionError("measure_capability must not run when score validation already failed")


class _RuntimeWithBadCapability(_FakeRuntime):
    def __init__(self, *, n_tokens=128, per_arm=None):
        self.records_seen = None
        self._n_tokens = n_tokens
        self._per_arm = per_arm

    def evaluate(self, records, *, config):
        self.records_seen = records
        return adapter_mod.JudgeRunResult(
            run_ref="lodestar:run/fake",
            judge_model="lodestar-stub",
            rubric_version="stub-v1",
            prompt_version="stub-v1",
            scores=[adapter_mod.BlindScore(blind_id=record.blind_id, score=0.5) for record in records],
        )

    def measure_capability(self, *, source_artifact, slice_path, slice_ref, config):
        per_arm = self._per_arm
        if per_arm is None:
            per_arm = [
                ("baseline", None, 10.0),
                ("steered", 1.0, 11.0),
                ("steered", 2.0, 12.0),
                ("random_direction", 1.0, 13.0),
                ("random_direction", 2.0, 14.0),
                ("random_feature", 1.0, 15.0),
                ("random_feature", 2.0, 16.0),
                ("prompt_baseline", None, 10.5),
            ]
        return adapter_mod.CapabilityMeasurement(n_tokens=self._n_tokens, per_arm=per_arm)


def _judge_cards(registry_root: Path) -> list[dict]:
    cards = [json.loads(path.read_text(encoding="utf-8")) for path in (registry_root / "run_card").glob("*.json")]
    return [card for card in cards if card["payload"]["stage"] == "judge"]


def _assert_failed_judge_run(registry_root: Path, *, exit_code: int) -> None:
    cards = _judge_cards(registry_root)
    assert len(cards) == 1
    assert cards[0]["payload"]["status"] == "failed"
    assert cards[0]["payload"]["exit_code"] == exit_code
    assert cards[0]["payload"]["outputs"] == []


def _load_judged_artifact(registry_root: Path, source_hash: str) -> dict:
    results = [envelope.load(path) for path in (registry_root / "intervention_result").glob("*.json")]
    assert len(results) == 2
    return next(artifact for artifact in results if artifact["self_hash"] != source_hash)


def test_valid_source_a9_writes_distinct_schema_valid_a9prime_and_preserves_source(
    tmp_path, scratch_dir, monkeypatch
):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    source_path = registry_root / "intervention_result" / f"{hashing.short_hash(source['self_hash'])}.json"
    source_bytes_before = source_path.read_bytes()

    fake_runtime = _FakeRuntime(_score_map())
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: fake_runtime)

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 0
    judged = _load_judged_artifact(registry_root, source["self_hash"])
    assert source_path.read_bytes() == source_bytes_before
    assert judged["artifact_type"] == "intervention_result"
    assert judged["self_hash"] != source["self_hash"]
    assert judged["payload"]["spec"] == source["payload"]["spec"]
    assert judged["payload"]["arms"] == source["payload"]["arms"]
    assert judged["payload"]["blinding"] == source["payload"]["blinding"]
    assert judged["payload"]["sampling"] == source["payload"]["sampling"]
    assert judged["subject"][:-1] == source["subject"]
    assert judged["subject"][-1] == {
        "content_hash": source["self_hash"],
        "location": f"local:registry/intervention_result/{hashing.short_hash(source['self_hash'])}.json",
        "role": "judged_from",
    }
    assert judged["payload"]["lodestar"] == {
        "run_ref": "lodestar:run/fake",
        "judge_model": "lodestar-stub",
        "rubric_version": "stub-v1",
        "per_prompt_scores": [
            {"prompt_id": "p0", "arm": "baseline", "scale": 1.0, "score": 0.2},
            {"prompt_id": "p0", "arm": "baseline", "scale": 2.0, "score": 0.2},
            {"prompt_id": "p0", "arm": "steered", "scale": 1.0, "score": 0.4},
            {"prompt_id": "p0", "arm": "steered", "scale": 2.0, "score": 1.4},
            {"prompt_id": "p0", "arm": "random_direction", "scale": 1.0, "score": 1.1},
            {"prompt_id": "p0", "arm": "random_direction", "scale": 2.0, "score": 0.6},
            {"prompt_id": "p0", "arm": "random_feature", "scale": 1.0, "score": 0.3},
            {"prompt_id": "p0", "arm": "random_feature", "scale": 2.0, "score": 1.5},
            {"prompt_id": "p0", "arm": "prompt_baseline", "scale": 1.0, "score": 1.2},
            {"prompt_id": "p0", "arm": "prompt_baseline", "scale": 2.0, "score": 1.2},
            {"prompt_id": "p1", "arm": "baseline", "scale": 1.0, "score": 0.9},
            {"prompt_id": "p1", "arm": "baseline", "scale": 2.0, "score": 0.9},
            {"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 1.0},
            {"prompt_id": "p1", "arm": "steered", "scale": 2.0, "score": 0.1},
            {"prompt_id": "p1", "arm": "random_direction", "scale": 1.0, "score": 0.7},
            {"prompt_id": "p1", "arm": "random_direction", "scale": 2.0, "score": 0.8},
            {"prompt_id": "p1", "arm": "random_feature", "scale": 1.0, "score": 1.3},
            {"prompt_id": "p1", "arm": "random_feature", "scale": 2.0, "score": 0.8},
            {"prompt_id": "p1", "arm": "prompt_baseline", "scale": 1.0, "score": 0.5},
            {"prompt_id": "p1", "arm": "prompt_baseline", "scale": 2.0, "score": 0.5},
        ],
    }
    assert judged["payload"]["capability_delta"] == {
        "slice": slice_ref,
        "n_tokens": 128,
        "per_arm": [
            {"arm": "baseline", "scale": None, "ppl": 10.0},
            {"arm": "steered", "scale": 1.0, "ppl": 11.0},
            {"arm": "steered", "scale": 2.0, "ppl": 12.0},
            {"arm": "random_direction", "scale": 1.0, "ppl": 13.0},
            {"arm": "random_direction", "scale": 2.0, "ppl": 14.0},
            {"arm": "random_feature", "scale": 1.0, "ppl": 15.0},
            {"arm": "random_feature", "scale": 2.0, "ppl": 16.0},
            {"arm": "prompt_baseline", "scale": None, "ppl": 10.5},
        ],
    }
    assert type(judged["payload"]["capability_delta"]["n_tokens"]) is int
    assert {
        (entry["arm"], entry["scale"])
        for entry in judged["payload"]["capability_delta"]["per_arm"]
    } == {
        ("baseline", None),
        ("steered", 1.0),
        ("steered", 2.0),
        ("random_direction", 1.0),
        ("random_direction", 2.0),
        ("random_feature", 1.0),
        ("random_feature", 2.0),
        ("prompt_baseline", None),
    }

    assert fake_runtime.records_seen is not None
    assert all(isinstance(record, adapter_mod.BlindedRecord) for record in fake_runtime.records_seen)
    assert {(record.blind_id, record.text, record.prompt) for record in fake_runtime.records_seen}
    assert not any(hasattr(record, "arm") or hasattr(record, "scale") or hasattr(record, "prompt_id") for record in fake_runtime.records_seen)
    actual_cells = {
        (entry["prompt_id"], entry["arm"], entry["scale"])
        for entry in judged["payload"]["lodestar"]["per_prompt_scores"]
    }
    assert actual_cells == _expected_score_cells()
    assert len(actual_cells) == len(judged["payload"]["lodestar"]["per_prompt_scores"])

    cards = _judge_cards(registry_root)
    assert len(cards) == 1
    assert cards[0]["payload"]["status"] == "completed"
    assert cards[0]["payload"]["exit_code"] == 0


def test_runtime_mutation_cannot_contaminate_a9prime_lineage(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    sealed_source = copy.deepcopy(source)
    slice_ref = _write_slice(scratch_dir)
    sealed_slice_ref = copy.deepcopy(slice_ref)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    source_path = registry_root / "intervention_result" / f"{hashing.short_hash(source['self_hash'])}.json"
    source_bytes_before = source_path.read_bytes()

    mutating_runtime = _MutatingRuntime(_score_map(), source_hash=source["self_hash"], slice_ref=sealed_slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: mutating_runtime)

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 0
    judged = _load_judged_artifact(registry_root, source["self_hash"])
    assert source_path.read_bytes() == source_bytes_before
    assert mutating_runtime.evaluate_config_seen == {
        "intervention_result_hash": source["self_hash"],
        "capability_slice": sealed_slice_ref,
    }
    assert mutating_runtime.measure_source_seen == sealed_source
    assert mutating_runtime.measure_slice_ref_seen == sealed_slice_ref
    assert mutating_runtime.measure_config_seen == {
        "intervention_result_hash": source["self_hash"],
        "capability_slice": sealed_slice_ref,
    }

    expected_payload = copy.deepcopy(sealed_source["payload"])
    expected_payload["lodestar"] = {
        "run_ref": "lodestar:run/fake",
        "judge_model": "lodestar-stub",
        "rubric_version": "stub-v1",
        "per_prompt_scores": judged["payload"]["lodestar"]["per_prompt_scores"],
    }
    expected_payload["capability_delta"] = {
        "slice": sealed_slice_ref,
        "n_tokens": 128,
        "per_arm": [
            {"arm": "baseline", "scale": None, "ppl": 10.0},
            {"arm": "steered", "scale": 1.0, "ppl": 11.0},
            {"arm": "steered", "scale": 2.0, "ppl": 12.0},
            {"arm": "random_direction", "scale": 1.0, "ppl": 13.0},
            {"arm": "random_direction", "scale": 2.0, "ppl": 14.0},
            {"arm": "random_feature", "scale": 1.0, "ppl": 15.0},
            {"arm": "random_feature", "scale": 2.0, "ppl": 16.0},
            {"arm": "prompt_baseline", "scale": None, "ppl": 10.5},
        ],
    }
    assert judged["payload"] == expected_payload
    assert judged["subject"] == [
        *sealed_source["subject"],
        {
            "content_hash": sealed_source["self_hash"],
            "location": f"local:registry/intervention_result/{hashing.short_hash(sealed_source['self_hash'])}.json",
            "role": "judged_from",
        },
    ]


def test_missing_source_a9_exits_3_with_failed_run_card_and_no_a9prime(tmp_path, scratch_dir):
    registry_root = tmp_path / "registry"
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, "sha256:" + "a" * 64, slice_ref)

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert not list((registry_root / "intervention_result").glob("*.json"))
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_hash_mismatched_source_a9_exits_3_without_writing_a9prime(tmp_path, scratch_dir):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    source_path = registry_root / "intervention_result" / f"{hashing.short_hash(source['self_hash'])}.json"
    tampered = json.loads(source_path.read_text(encoding="utf-8"))
    tampered["payload"]["sampling"]["seed"] = 99
    source_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_missing_declared_generation_cell_exits_3_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    incomplete_records = [
        record for record in _source_records()
        if not (record["prompt_id"] == "p1" and record["arm"] == "random_direction" and record["scale"] == 2.0)
    ]
    source, _records = _register_source_a9(registry_root, scratch_dir, records=incomplete_records)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: pytest.fail("runtime must not be invoked"))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_empty_generation_grid_exits_3_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir, records=[])
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: pytest.fail("runtime must not be invoked"))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_duplicate_generation_cell_exits_3_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    duplicate_records = list(_source_records())
    duplicate_records.append(dict(duplicate_records[0], text="duplicate cell text"))
    source, _records = _register_source_a9(registry_root, scratch_dir, records=duplicate_records)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: pytest.fail("runtime must not be invoked"))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_declared_arm_mismatch_exits_3_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(
        registry_root,
        scratch_dir,
        arms_payload=lambda generations_ref: [
            arm for arm in _arms_payload(generations_ref) if arm["arm"] != "random_feature"
        ],
    )
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: pytest.fail("runtime must not be invoked"))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_wrong_artifact_type_exits_3_with_no_a9prime(tmp_path, scratch_dir):
    registry_root = tmp_path / "registry"
    source = _register_eval_compat_map(registry_root)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert len(list((registry_root / "eval_compat_map").glob("*.json"))) == 1
    assert not list((registry_root / "intervention_result").glob("*.json"))
    _assert_failed_judge_run(registry_root, exit_code=3)


def test_malformed_evaluator_output_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)

    class _BadRuntime:
        def evaluate(self, records, *, config):
            return adapter_mod.JudgeRunResult(
                run_ref="lodestar:run/bad",
                judge_model="lodestar-stub",
                rubric_version="stub-v1",
                prompt_version="stub-v1",
                scores=[
                    adapter_mod.BlindScore(blind_id=records[0].blind_id, score=0.1),
                    adapter_mod.BlindScore(blind_id=records[0].blind_id, score=0.2),
                ],
            )

        def measure_capability(self, *, source_artifact, slice_path, slice_ref, config):
            raise AssertionError("measure_capability must not run when score correlation already failed")

    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: _BadRuntime())

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


def test_fractional_token_count_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: _RuntimeWithBadCapability(n_tokens=1.5))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


def test_boolean_token_count_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: _RuntimeWithBadCapability(n_tokens=True))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


@pytest.mark.parametrize("bad_score", [math.nan, math.inf])
def test_nonfinite_score_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch, bad_score):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    monkeypatch.setattr(adapter_mod, "build_live_runtime", lambda: _RuntimeWithBadScores(bad_score))

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


@pytest.mark.parametrize("bad_ppl", [math.nan, math.inf])
def test_nonfinite_perplexity_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch, bad_ppl):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    bad_per_arm = [
        ("baseline", None, 10.0),
        ("steered", 1.0, bad_ppl),
        ("steered", 2.0, 12.0),
        ("random_direction", 1.0, 13.0),
        ("random_direction", 2.0, 14.0),
        ("random_feature", 1.0, 15.0),
        ("random_feature", 2.0, 16.0),
        ("prompt_baseline", None, 10.5),
    ]
    monkeypatch.setattr(
        adapter_mod,
        "build_live_runtime",
        lambda: _RuntimeWithBadCapability(per_arm=bad_per_arm),
    )

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


def test_capability_grid_mismatch_exits_4_with_no_a9prime(tmp_path, scratch_dir, monkeypatch):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)
    bad_per_arm = [
        ("baseline", None, 10.0),
        ("steered", 1.0, 11.0),
        ("steered", 2.0, 12.0),
        ("random_direction", 1.0, 13.0),
        ("random_feature", 1.0, 15.0),
        ("random_feature", 2.0, 16.0),
        ("prompt_baseline", None, 10.5),
    ]
    monkeypatch.setattr(
        adapter_mod,
        "build_live_runtime",
        lambda: _RuntimeWithBadCapability(per_arm=bad_per_arm),
    )

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


def test_unavailable_live_runtime_exits_4_with_no_a9prime(tmp_path, scratch_dir):
    registry_root = tmp_path / "registry"
    source, _records = _register_source_a9(registry_root, scratch_dir)
    slice_ref = _write_slice(scratch_dir)
    cfg_path = _write_config(tmp_path, source["self_hash"], slice_ref)

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert len(list((registry_root / "intervention_result").glob("*.json"))) == 1
    _assert_failed_judge_run(registry_root, exit_code=4)


def test_readable_invalid_config_writes_failed_run_card_and_exits_3(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = tmp_path / "judge.yaml"
    cfg_path.write_text(yaml.safe_dump({"intervention_result_hash": "sha256:" + "a" * 64}), encoding="utf-8")

    exit_code = judge.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert_only_run_card_written(registry_root)
    assert_failed_invalid_config_run_card(
        registry_root, stage="judge", config_path=cfg_path, repo_root=tmp_path
    )
