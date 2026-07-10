"""interplab.jobs.backfill_checkpoint (ED-5): registers a backfilled A5
sae_checkpoint manifest for a pre-blueprint checkpoint. store_hash is
always null; the training corpus is a corpus_manifest reference in
`subject`. Directory hashing MUST happen on the machine holding the
weights (D1) -- this job computes it locally only when the location is
actually reachable, and otherwise requires an explicit pre-computed hash.
"""

import json

import pytest
import yaml

from interplab.core import envelope
from interplab.jobs import backfill_checkpoint

_CORPUS_HASH = "sha256:" + "4" * 64


def _write_config(tmp_path, **overrides):
    cfg = {
        "training_config_path": "local:configs/sae_train_l16_32x.yaml",
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": "local:tests/fixtures/tiny_model",
        "corpus_manifest_hash": _CORPUS_HASH,
        "tokens_trained": 376_000_000,
        "seed": 42,
        "wandb": None,
        "telemetry_tail": {"fvu": 0.08, "dead_count": 200},
    }
    cfg.update(overrides)
    path = tmp_path / "backfill.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def test_backfill_registers_a5_with_null_store_hash(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)

    exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 0
    ckpts = list((registry_root / "sae_checkpoint").glob("*.json"))
    assert len(ckpts) == 1
    checkpoint = json.loads(ckpts[0].read_text(encoding="utf-8"))
    envelope.load(checkpoint)  # self-consistent, schema-valid
    assert checkpoint["payload"]["store_hash"] is None
    assert checkpoint["payload"]["tokens_trained"] == 376_000_000
    assert checkpoint["payload"]["seed"] == 42


def test_backfill_records_corpus_manifest_in_subject(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    roles = {ref["role"]: ref for ref in checkpoint["subject"]}
    assert "weights" in roles
    assert "model" in roles
    assert "corpus_manifest" in roles
    assert roles["corpus_manifest"]["content_hash"] == _CORPUS_HASH


def test_backfill_serializes_real_training_config_verbatim(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    with open("configs/sae_train_l16_32x.yaml", encoding="utf-8") as f:
        expected = yaml.safe_load(f)
    assert checkpoint["payload"]["config"] == expected


def test_backfill_computes_real_directory_hash_locally(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    from interplab.core import hashing, uris

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    weights_ref = next(ref for ref in checkpoint["subject"] if ref["role"] == "weights")
    expected_hash = hashing.hash_directory(uris.resolve_local("local:tests/fixtures/tiny_sae"))
    assert weights_ref["content_hash"] == expected_hash


def test_explicit_weights_dir_hash_is_trusted_without_recomputation(tmp_path):
    registry_root = tmp_path / "registry"
    explicit_hash = "sha256:" + "9" * 64
    cfg_path = _write_config(tmp_path, weights_dir_hash=explicit_hash)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    weights_ref = next(ref for ref in checkpoint["subject"] if ref["role"] == "weights")
    assert weights_ref["content_hash"] == explicit_hash


def test_non_local_location_without_explicit_hash_is_contract_violation(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path, weights_location="tamia:sae_checkpoints/l16_32x/final")

    exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_missing_training_config_is_contract_violation(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path, training_config_path="local:configs/does_not_exist.yaml")

    exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_writes_a_run_card_with_backfill_stage_and_backfill_entrypoint(tmp_path):
    """ED-11: backfill runs are not training runs -- stage is "backfill"."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["stage"] == "backfill"
    assert card["created_by"]["entrypoint"] == "interplab.jobs.backfill_checkpoint"
    assert card["payload"]["status"] == "completed"
    assert card["payload"]["exit_code"] == 0


def test_config_must_validate_against_schema(tmp_path):
    with pytest.raises(FileNotFoundError):
        backfill_checkpoint.run(tmp_path / "nonexistent.yaml", registry_root=tmp_path / "registry")
