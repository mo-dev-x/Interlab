"""§6.1 store_qa job (SS2, ED-11 stage="store_qa"): QA measurements over a
finished activation store; verdict; A4 emission."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml

from interplab.core import envelope, uris
from interplab.jobs import store_qa
from interplab.registry.registry import put as registry_put
from tests.job_test_helpers import (
    assert_failed_invalid_config_run_card,
    assert_only_run_card_written,
)


def _write_shard(store_dir: Path, name: str, activations: np.ndarray, input_ids: np.ndarray) -> None:
    store_dir.mkdir(parents=True, exist_ok=True)
    np.savez(store_dir / name, activations=activations.astype("float32"), input_ids=input_ids.astype("int64"))


def _register_corpus_manifest(registry_root: Path) -> str:
    created_by = {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}
    manifest = envelope.dump(
        artifact_type="corpus_manifest", schema_version=1, created_by=created_by, subject=[],
        payload={
            "name": "n", "recipe": {"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
            "token_count": 100, "doc_count": 10, "dedup_rate": None, "tokenizer": {"name": "t", "revision": "v1"},
            "sample_checksum": "sha256:" + "0" * 64,
        },
    )
    return registry_put(manifest, registry_root=registry_root)


@pytest.fixture
def store_scratch_dir():
    d = uris.REPO_ROOT / "results" / "_test_scratch" / "jobs_store_qa"
    if d.exists():
        shutil.rmtree(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _base_config(corpus_hash: str, store_rel_location: str, **overrides) -> dict:
    cfg = {
        "store_location": f"local:{store_rel_location}",
        "corpus_manifest_hash": corpus_hash,
        "model": {"name": "tiny", "revision": "v1"},
        "hook_name": "blocks.1.hook_resid_post",
        "hook_layer": 1,
        "context_size": 8,
        "prepend_bos": True,
        "dtype": "float32",
        "position_policy": {"exclude_bos": False, "exclude_padding": False, "excluded_first_n": 0},
        "eval_holdout": None,
        "special_token_ids": [1],
    }
    cfg.update(overrides)
    return cfg


def test_full_run_healthy_store_is_green(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)

    # A large i.i.d. sample so per-position norm variance and lag-1
    # autocorrelation both average out near zero (small samples land amber
    # by chance -- this is deliberately generous to avoid a flaky test).
    rng = np.random.default_rng(0)
    acts = rng.normal(size=(200, 8, 16)).astype("float32")
    ids = rng.integers(2, 100, size=(200, 8))  # no id==1 (BOS) anywhere -> special_token_fraction 0
    _write_shard(store_scratch_dir, "shard_0000.npz", acts, ids)

    rel = store_scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
    cfg = _base_config(corpus_hash, rel)
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    manifests = list((registry_root / "store_manifest").glob("*.json"))
    assert len(manifests) == 1
    manifest = envelope.load(manifests[0])
    assert manifest["payload"]["qa"]["special_token_fraction"] == 0.0
    assert manifest["payload"]["qa"]["verdict"] == "green"
    assert manifest["subject"][0]["role"] == "corpus_manifest"


def test_unhealthy_store_is_red_and_exit_code_2(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)

    acts = np.ones((5, 8, 16), dtype="float32")
    ids = np.ones((5, 8), dtype="int64")  # every position is the "special" id -> fraction 1.0
    _write_shard(store_scratch_dir, "shard_0000.npz", acts, ids)

    rel = store_scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
    cfg = _base_config(corpus_hash, rel)
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 2

    manifests = list((registry_root / "store_manifest").glob("*.json"))
    manifest = envelope.load(manifests[0])
    assert manifest["payload"]["qa"]["verdict"] == "red"

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "gate_failed"
    assert card["payload"]["exit_code"] == 2


def test_chat_slice_recorded_as_evidence_never_gate_bearing(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)

    corpus_dir = store_scratch_dir / "corpus"
    chat_dir = store_scratch_dir / "chat"
    _write_shard(corpus_dir, "shard_0000.npz", np.ones((5, 8, 16), dtype="float32") * 1.0, np.full((5, 8), 5))
    _write_shard(chat_dir, "shard_0000.npz", np.ones((5, 8, 16), dtype="float32") * 50.0, np.full((5, 8), 5))

    corpus_rel = corpus_dir.relative_to(uris.REPO_ROOT).as_posix()
    chat_rel = chat_dir.relative_to(uris.REPO_ROOT).as_posix()
    cfg = _base_config(corpus_hash, corpus_rel, chat_slice_location=f"local:{chat_rel}")
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0  # chat divergence must not affect the verdict

    manifests = list((registry_root / "store_manifest").glob("*.json"))
    manifest = envelope.load(manifests[0])
    assert manifest["payload"]["qa"]["chat_divergence"] is not None
    assert manifest["payload"]["qa"]["verdict"] == "green"


def test_writes_a_run_card(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)
    _write_shard(store_scratch_dir, "shard_0000.npz", np.ones((3, 8, 16), dtype="float32"), np.full((3, 8), 5))
    rel = store_scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(_base_config(corpus_hash, rel)), encoding="utf-8")

    store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    cards = list((registry_root / "run_card").glob("*.json"))
    assert len(cards) == 1
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    assert card["payload"]["stage"] == "store_qa"


def test_missing_corpus_manifest_is_contract_violation(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    _write_shard(store_scratch_dir, "shard_0000.npz", np.ones((3, 8, 16), dtype="float32"), np.full((3, 8), 5))
    rel = store_scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
    fake_hash = "sha256:" + "a" * 64
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(_base_config(fake_hash, rel)), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_empty_store_is_contract_violation(tmp_path, store_scratch_dir):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)
    store_scratch_dir.mkdir(parents=True)
    rel = store_scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(_base_config(corpus_hash, rel)), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_non_local_store_location_is_not_implemented(tmp_path):
    registry_root = tmp_path / "registry"
    corpus_hash = _register_corpus_manifest(registry_root)
    cfg = _base_config(corpus_hash, "unused")
    cfg["store_location"] = "tamia:some/cluster/path"
    cfg_path = tmp_path / "store_qa.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 4


def test_config_schema_validation_failure_writes_failed_run_card(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(yaml.safe_dump({"store_location": "not-a-uri"}), encoding="utf-8")

    exit_code = store_qa.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert not list((registry_root / "store_manifest").glob("*.json"))
    assert_only_run_card_written(registry_root)
    assert_failed_invalid_config_run_card(
        registry_root, stage="store_qa", config_path=cfg_path, repo_root=tmp_path
    )
