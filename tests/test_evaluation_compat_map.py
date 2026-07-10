"""SS8 eval_compat_map I/O (A12, D2: "edited only by hand, by the
researcher") -- validate + register a hand-authored payload."""

from __future__ import annotations

import pytest
import yaml

from interplab.core._schema_registry import SchemaValidationError
from interplab.evaluation import compat_map
from interplab.registry.registry import get as registry_get


def _created_by():
    return {"run_id": "r1", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


def _valid_payload():
    return {
        "version": 1,
        "judge_classes": [
            {"class_id": "claude-v1", "members": [{"judge_model": "claude-sonnet", "rubric_version": "v1", "prompt_version": "v1"}]},
        ],
    }


def test_register_valid_payload_round_trips(tmp_path):
    h = compat_map.register(_valid_payload(), created_by=_created_by(), registry_root=tmp_path)
    artifact = registry_get(h, registry_root=tmp_path)
    assert artifact["artifact_type"] == "eval_compat_map"
    assert artifact["payload"] == _valid_payload()


def test_register_invalid_payload_raises_schema_validation_error(tmp_path):
    bad_payload = {"version": 1}  # missing required judge_classes
    with pytest.raises(SchemaValidationError):
        compat_map.register(bad_payload, created_by=_created_by(), registry_root=tmp_path)


def test_load_payload_from_yaml_file(tmp_path):
    path = tmp_path / "compat.yaml"
    path.write_text(yaml.safe_dump(_valid_payload()), encoding="utf-8")
    loaded = compat_map.load_payload(path)
    assert loaded == _valid_payload()


def test_load_and_register_end_to_end(tmp_path):
    path = tmp_path / "compat.yaml"
    path.write_text(yaml.safe_dump(_valid_payload()), encoding="utf-8")
    registry_root = tmp_path / "registry"
    h = compat_map.load_and_register(path, created_by=_created_by(), registry_root=registry_root)
    artifact = registry_get(h, registry_root=registry_root)
    assert artifact["payload"]["version"] == 1


def test_load_payload_rejects_non_mapping_top_level(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a mapping"):
        compat_map.load_payload(path)
