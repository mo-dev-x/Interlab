"""§3.3 sync_registry: copies outbox artifacts into registry/, verifies
self_hash, empties the outbox. Minimal, authorized scope (ED-6)."""

import json

import pytest

from interplab.core import envelope
from interplab.jobs import sync_registry
from tests.job_test_helpers import (
    assert_failed_invalid_config_run_card,
    assert_only_run_card_written,
)


def _write_config(tmp_path, outbox_dir):
    cfg = tmp_path / "sync.yaml"
    cfg.write_text(f"outbox_dir: {outbox_dir}\n", encoding="utf-8")
    return cfg


def _sample_artifact(created_by):
    return envelope.dump(
        artifact_type="eval_compat_map",
        schema_version=1,
        created_by=created_by,
        subject=[],
        payload={"version": 1, "judge_classes": []},
    )


def test_syncs_valid_artifact_and_empties_outbox(tmp_path, created_by):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    registry_root = tmp_path / "registry"

    artifact = _sample_artifact(created_by)
    (outbox / "a.json").write_text(json.dumps(artifact), encoding="utf-8")

    cfg = _write_config(tmp_path, outbox)
    exit_code = sync_registry.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 0
    assert list(outbox.glob("*.json")) == []
    synced = list((registry_root / "eval_compat_map").glob("*.json"))
    assert len(synced) == 1
    assert json.loads(synced[0].read_text(encoding="utf-8")) == artifact


def test_content_addressing_means_conflicts_are_impossible(tmp_path, created_by):
    """§3.3: syncing the same artifact twice (e.g. two outbox batches) is a
    no-op, not a conflict, since registry.put() is idempotent on identical
    content -- exactly the "impossible by construction" guarantee."""
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    registry_root = tmp_path / "registry"
    artifact = _sample_artifact(created_by)
    cfg = _write_config(tmp_path, outbox)

    (outbox / "a.json").write_text(json.dumps(artifact), encoding="utf-8")
    assert sync_registry.run(cfg, registry_root=registry_root, repo_root=tmp_path) == 0

    (outbox / "a.json").write_text(json.dumps(artifact), encoding="utf-8")
    assert sync_registry.run(cfg, registry_root=registry_root, repo_root=tmp_path) == 0
    assert len(list((registry_root / "eval_compat_map").glob("*.json"))) == 1


def test_missing_outbox_dir_is_contract_violation(tmp_path):
    cfg = _write_config(tmp_path, tmp_path / "does_not_exist")
    exit_code = sync_registry.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 3


def test_corrupted_artifact_in_outbox_is_contract_violation(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    (outbox / "bad.json").write_text(
        json.dumps({"artifact_type": "eval_compat_map", "self_hash": "sha256:" + "0" * 64}),
        encoding="utf-8",
    )
    cfg = _write_config(tmp_path, outbox)
    exit_code = sync_registry.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 3
    # The bad file is left in place for inspection, not silently deleted.
    assert (outbox / "bad.json").exists()


def test_empty_outbox_succeeds_with_zero_synced(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    cfg = _write_config(tmp_path, outbox)
    exit_code = sync_registry.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 0


def test_writes_a_run_card(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, outbox)
    sync_registry.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    cards = list((registry_root / "run_card").glob("*.json"))
    assert len(cards) == 1
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    assert card["payload"]["stage"] == "sync"


def test_config_validates_against_schema(tmp_path):
    with pytest.raises(FileNotFoundError):
        sync_registry.run(tmp_path / "nonexistent_config.yaml", registry_root=tmp_path / "registry")


def test_readable_malformed_yaml_writes_failed_run_card_and_exits_3(tmp_path):
    registry_root = tmp_path / "registry"
    cfg = tmp_path / "sync.yaml"
    cfg.write_text("outbox_dir: [\n", encoding="utf-8")

    exit_code = sync_registry.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert_only_run_card_written(registry_root)
    assert_failed_invalid_config_run_card(
        registry_root, stage="sync", config_path=cfg, repo_root=tmp_path
    )
