import json

import pytest
from pydantic import ValidationError

from interplab.core import envelope
from interplab.core._schema_registry import SchemaValidationError


def _eval_compat_map_artifact(created_by, version=1):
    return envelope.dump(
        artifact_type="eval_compat_map",
        schema_version=1,
        created_by=created_by,
        subject=[],
        payload={"version": version, "judge_classes": []},
    )


def test_dump_produces_verifiable_self_hash(created_by):
    artifact = _eval_compat_map_artifact(created_by)
    assert artifact["self_hash"].startswith("sha256:")
    envelope.verify(artifact)  # must not raise


def test_dump_and_load_roundtrip_via_file(tmp_path, created_by):
    artifact = _eval_compat_map_artifact(created_by)
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")

    loaded = envelope.load(path)
    assert loaded == artifact


def test_load_accepts_dict_directly(created_by):
    artifact = _eval_compat_map_artifact(created_by)
    assert envelope.load(artifact) == artifact


def test_load_detects_hash_tampering(created_by):
    artifact = _eval_compat_map_artifact(created_by)
    tampered = dict(artifact, payload={"version": 999, "judge_classes": []})
    with pytest.raises(envelope.EnvelopeHashMismatchError):
        envelope.load(tampered)


def test_verify_raises_on_missing_self_hash():
    with pytest.raises(envelope.EnvelopeHashMismatchError):
        envelope.verify({"a": 1})


def test_dump_rejects_schema_violation(created_by):
    with pytest.raises(SchemaValidationError):
        envelope.dump(
            artifact_type="eval_compat_map",
            schema_version=1,
            created_by=created_by,
            subject=[],
            payload={"version": "not-an-int", "judge_classes": []},
        )


def test_dump_rejects_unknown_artifact_type(created_by):
    with pytest.raises(FileNotFoundError):
        envelope.dump(
            artifact_type="not_a_real_type",
            schema_version=1,
            created_by=created_by,
            subject=[],
            payload={},
        )


def test_load_rejects_malformed_created_by(created_by):
    artifact = _eval_compat_map_artifact(created_by)
    broken = dict(artifact, created_by={"run_id": "x"})  # missing required sub-fields
    broken["self_hash"] = envelope.compute_self_hash(broken)
    with pytest.raises(ValidationError):
        envelope.load(broken)
