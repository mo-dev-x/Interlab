import json

import pytest
from pydantic import ValidationError

from interplab.core import envelope, hashing
from interplab.registry import registry


def _eval_compat_map(created_by, version=1):
    return envelope.dump(
        artifact_type="eval_compat_map",
        schema_version=1,
        created_by=created_by,
        subject=[],
        payload={"version": version, "judge_classes": []},
    )


def test_put_then_get_roundtrip(tmp_path, created_by):
    # Also covers "prefix lookup" behavior: on-disk lookup is by hash12
    # filename, and this exercises that path end to end for the matching case.
    artifact = _eval_compat_map(created_by)
    h = registry.put(artifact, registry_root=tmp_path)
    assert h == artifact["self_hash"]
    assert registry.get(h, registry_root=tmp_path) == artifact


def test_get_rejects_full_hash_mismatch_against_hash12_prefix(tmp_path, created_by):
    # Simulates a hash12 collision / corrupted registry file: the file at
    # the requested hash's hash12 path is internally self-consistent (its
    # own self_hash verifies) but belongs to a different full hash than the
    # one requested. get() must not silently return it.
    artifact = _eval_compat_map(created_by)
    h = registry.put(artifact, registry_root=tmp_path)
    hash12 = hashing.short_hash(h)

    other = _eval_compat_map(created_by, version=2)
    path = tmp_path / "eval_compat_map" / f"{hash12}.json"
    path.write_text(json.dumps(other), encoding="utf-8")

    with pytest.raises(registry.RegistryError):
        registry.get(h, registry_root=tmp_path)


def test_put_is_idempotent(tmp_path, created_by):
    artifact = _eval_compat_map(created_by)
    h1 = registry.put(artifact, registry_root=tmp_path)
    h2 = registry.put(artifact, registry_root=tmp_path)
    assert h1 == h2


def test_put_rejects_overwrite_with_different_content(tmp_path, created_by):
    artifact = _eval_compat_map(created_by)
    h = registry.put(artifact, registry_root=tmp_path)
    hash12 = hashing.short_hash(h)
    path = tmp_path / "eval_compat_map" / f"{hash12}.json"
    path.write_text('{"tampered": true}', encoding="utf-8")

    with pytest.raises(registry.RegistryError):
        registry.put(artifact, registry_root=tmp_path)


def test_put_rejects_invalid_artifact(tmp_path):
    with pytest.raises(ValidationError):
        registry.put({"not": "an artifact"}, registry_root=tmp_path)


def test_get_raises_for_unknown_hash(tmp_path):
    with pytest.raises(registry.RegistryError):
        registry.get("sha256:" + "00" * 32, registry_root=tmp_path)


def test_find_by_type_and_payload_filter(tmp_path, created_by):
    a1 = _eval_compat_map(created_by, version=1)
    a2 = _eval_compat_map(created_by, version=2)
    registry.put(a1, registry_root=tmp_path)
    registry.put(a2, registry_root=tmp_path)

    assert len(registry.find("eval_compat_map", registry_root=tmp_path)) == 2

    only_v2 = registry.find("eval_compat_map", registry_root=tmp_path, version=2)
    assert len(only_v2) == 1
    assert only_v2[0]["payload"]["version"] == 2


def test_find_by_subject_hash(tmp_path, created_by):
    subject_hash = "sha256:" + "ab" * 32
    artifact = envelope.dump(
        artifact_type="census_report",
        schema_version=1,
        created_by=created_by,
        subject=[
            {
                "content_hash": subject_hash,
                "location": "local:registry/corpus_manifest/abc.json",
                "role": "corpus_manifest",
            }
        ],
        payload={"method": {"matcher": "regex", "case_folding": True, "boundary": "word"}, "concepts": {}},
    )
    registry.put(artifact, registry_root=tmp_path)

    found = registry.find("census_report", subject_hash=subject_hash, registry_root=tmp_path)
    assert len(found) == 1

    not_found = registry.find(
        "census_report", subject_hash="sha256:" + "00" * 32, registry_root=tmp_path
    )
    assert not_found == []


def test_find_missing_type_dir_returns_empty(tmp_path):
    assert registry.find("sae_checkpoint", registry_root=tmp_path) == []
