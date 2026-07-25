"""interplab.jobs.backfill_checkpoint (ED-5): registers a backfilled A5
sae_checkpoint manifest for a pre-blueprint checkpoint. store_hash is
always null; the training corpus is a corpus_manifest reference in
`subject`. Directory hashing MUST happen on the machine holding the
weights (D1) -- this job computes it locally only when the location is
actually reachable, and otherwise requires an explicit pre-computed hash.

ED-27: the weights subject ref uses `hash_checkpoint_dir` (restricted to
the SAELens load closure, `{cfg.json, sae_weights.safetensors}`); the
model subject ref is unaffected and still uses the unrestricted
`hash_directory`.
"""

import json
import shutil

import pytest
import yaml

from interplab.core import envelope
from interplab.jobs import backfill_checkpoint

_CORPUS_HASH = "sha256:" + "4" * 64


_MODEL_LOCATION = "hf:Qwen/Qwen2.5-14B@0123456789abcdef0123456789abcdef01234567"
_MODEL_HASH = "sha256:" + "7" * 64


def _write_config(tmp_path, **overrides):
    cfg = {
        "training_config_path": "local:configs/sae_train_l16_32x.yaml",
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": _MODEL_LOCATION,
        "model_dir_hash": _MODEL_HASH,
        "corpus_manifest_hash": _CORPUS_HASH,
        "tokens_trained": 376_000_000,
        "seed": 42,
        "wandb": None,
        "telemetry_tail": {"fvu": 0.08, "fvu_source": "training_eval", "dead_count": 200},
        "training_provenance": {
            "sae_lens": "6.44.2", "transformers": None, "transformer_lens": None,
            "source": "cfg_metadata", "confidence": "measured",
        },
        "cfg_schema_generation": "6.x",
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


def test_backfill_computes_real_checkpoint_identity_hash_locally(tmp_path):
    """ED-27: weights identity is hash_checkpoint_dir (restricted to
    {cfg.json, sae_weights.safetensors}), not the whole-directory hash_directory."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    from interplab.core import hashing, uris

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    weights_ref = next(ref for ref in checkpoint["subject"] if ref["role"] == "weights")
    expected_hash = hashing.hash_checkpoint_dir(uris.resolve_local("local:tests/fixtures/tiny_sae"))
    assert weights_ref["content_hash"] == expected_hash


def test_backfill_records_hf_pinned_model_location_and_explicit_hash(tmp_path):
    """ED-29: the model ref's location is the revision-pinned hf: URI
    verbatim, and its content_hash is the explicitly-supplied model_dir_hash
    trusted without recomputation -- a real backfill config's model_location
    is never locally resolvable, so this is always the path exercised."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    model_ref = next(ref for ref in checkpoint["subject"] if ref["role"] == "model")
    assert model_ref["location"] == _MODEL_LOCATION
    assert model_ref["content_hash"] == _MODEL_HASH


def test_resolve_dir_hash_defaults_to_unrestricted_hash_directory_for_model(tmp_path):
    """ED-29: model_dir_hash keeps the unrestricted hash_directory -- ED-27's
    weights-only restriction does not generalize to it. Exercised directly
    against the private helper (rather than the full job) because a
    schema-valid backfill config's model_location is now always a
    revision-pinned hf: URI, never locally resolvable."""
    from interplab.core import hashing, uris
    from interplab.jobs.backfill_checkpoint import _resolve_dir_hash

    resolved = _resolve_dir_hash(None, "local:tests/fixtures/tiny_model", "model_dir_hash")
    expected = hashing.hash_directory(uris.resolve_local("local:tests/fixtures/tiny_model"))
    assert resolved == expected


def test_model_location_must_be_hf_scheme(tmp_path):
    """ED-29: the model ref is a consumed artifact whose identity is already
    fixed upstream -- its location MUST be hf:, not local:/tamia:/wandb:."""
    from interplab.core._schema_registry import SchemaValidationError

    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path, model_location="local:tests/fixtures/tiny_model")
    with pytest.raises(SchemaValidationError):
        backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)


def test_model_location_without_revision_pin_is_schema_invalid(tmp_path):
    """ED-29: 'hf:<repo>' with no '@<commit-sha>' is not revision-pinned."""
    from interplab.core._schema_registry import SchemaValidationError

    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path, model_location="hf:Qwen/Qwen2.5-14B")
    with pytest.raises(SchemaValidationError):
        backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)


def test_telemetry_tail_null_fvu_source_requires_null_fvu(tmp_path):
    """ED-30: fvu_source null iff fvu is unrecoverable -- a number can't be
    recorded with no stated provenance."""
    from interplab.core._schema_registry import SchemaValidationError

    registry_root = tmp_path / "registry"
    cfg_path = _write_config(
        tmp_path, telemetry_tail={"fvu": 0.1, "fvu_source": None, "dead_count": 0}
    )
    with pytest.raises(SchemaValidationError):
        backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)


def test_telemetry_tail_fvu_source_requires_non_null_fvu(tmp_path):
    """ED-30: a stated provenance requires an actual recorded value."""
    from interplab.core._schema_registry import SchemaValidationError

    registry_root = tmp_path / "registry"
    cfg_path = _write_config(
        tmp_path, telemetry_tail={"fvu": None, "fvu_source": "training_step", "dead_count": 0}
    )
    with pytest.raises(SchemaValidationError):
        backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)


def test_telemetry_tail_allows_fully_unrecoverable_legacy_row(tmp_path):
    """ED-30: fvu, fvu_source, and dead_count may all be null together for a
    legacy row that recovers none of them -- ED-9's doctrine: zero is a
    measurement, null is the absence of an instrument."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(
        tmp_path, telemetry_tail={"fvu": None, "fvu_source": None, "dead_count": None}
    )
    exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    assert checkpoint["payload"]["telemetry_tail"] == {"fvu": None, "fvu_source": None, "dead_count": None}


def test_telemetry_tail_records_training_step_source_when_that_is_what_is_available(tmp_path):
    """ED-30: training_step is the fallback source when no aggregated
    evaluation FVU was recoverable -- recorded verbatim from the config."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(
        tmp_path, telemetry_tail={"fvu": 0.12, "fvu_source": "training_step", "dead_count": 50}
    )
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    assert checkpoint["payload"]["telemetry_tail"] == {"fvu": 0.12, "fvu_source": "training_step", "dead_count": 50}


def test_training_provenance_and_cfg_schema_generation_pass_through_verbatim(tmp_path):
    """ED-33: recorded exactly as the caller determined it (from cfg.json
    metadata, in this case) -- the job records provenance, it does not
    infer it."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path)
    backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    assert checkpoint["payload"]["training_provenance"] == {
        "sae_lens": "6.44.2", "transformers": None, "transformer_lens": None,
        "source": "cfg_metadata", "confidence": "measured",
    }
    assert checkpoint["payload"]["cfg_schema_generation"] == "6.x"


def test_training_provenance_allows_fully_unrecoverable_legacy_checkpoint(tmp_path):
    """ED-33/ED-9: present-but-null is the honest-absence pattern for a
    checkpoint whose training library can no longer be determined --
    omission would lose the distinction between "unknown" and "not
    recorded"."""
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(
        tmp_path,
        training_provenance={
            "sae_lens": None, "transformers": None, "transformer_lens": None,
            "source": "unknown", "confidence": "unknown",
        },
        cfg_schema_generation=None,
    )
    exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    checkpoint = json.loads(next((registry_root / "sae_checkpoint").glob("*.json")).read_text(encoding="utf-8"))
    assert checkpoint["payload"]["training_provenance"] == {
        "sae_lens": None, "transformers": None, "transformer_lens": None,
        "source": "unknown", "confidence": "unknown",
    }
    assert checkpoint["payload"]["cfg_schema_generation"] is None


def test_training_provenance_is_required_present_not_omittable(tmp_path):
    """ED-33/ED-9: training_provenance MUST be present (sub-values may be
    null), never omitted -- an omitted field loses the honest-absence
    signal a present-but-null object carries."""
    from interplab.core._schema_registry import SchemaValidationError

    registry_root = tmp_path / "registry"
    cfg = {
        "training_config_path": "local:configs/sae_train_l16_32x.yaml",
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": _MODEL_LOCATION,
        "model_dir_hash": _MODEL_HASH,
        "corpus_manifest_hash": _CORPUS_HASH,
        "tokens_trained": 376_000_000,
        "seed": 42,
        "telemetry_tail": {"fvu": 0.08, "fvu_source": "training_eval", "dead_count": 200},
        "cfg_schema_generation": "6.x",
        # training_provenance deliberately omitted
    }
    path = tmp_path / "backfill_missing_provenance.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        backfill_checkpoint.run(path, registry_root=registry_root, repo_root=tmp_path)


def test_backfill_missing_checkpoint_identity_file_is_a_hard_error(tmp_path):
    """ED-27: a weights_location missing cfg.json or sae_weights.safetensors
    must not silently hash whatever subset is present.

    `local:` URIs resolve against the REAL repo root regardless of the
    job's own (test-injected) repo_root (see this job's own docstring), so
    the incomplete directory has to live under the real repo, in the
    conventional gitignored scratch location.
    """
    from interplab.core import uris

    registry_root = tmp_path / "registry"
    scratch_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "backfill_incomplete_weights"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True)
    (scratch_dir / "sae_weights.safetensors").write_bytes(b"weights only, no cfg.json")
    try:
        rel = scratch_dir.relative_to(uris.REPO_ROOT).as_posix()
        cfg_path = _write_config(tmp_path, weights_location=f"local:{rel}")

        exit_code = backfill_checkpoint.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
        assert exit_code != 0
        assert not list((registry_root / "sae_checkpoint").glob("*.json"))
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


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
