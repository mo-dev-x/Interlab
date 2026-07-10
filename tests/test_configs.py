import pytest

from interplab.core import configs
from interplab.core._schema_registry import SchemaNotFoundError


def test_load_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\nb: two\n", encoding="utf-8")
    assert configs.load_yaml(p) == {"a": 1, "b": "two"}


def test_load_yaml_empty_file_is_empty_dict(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    assert configs.load_yaml(p) == {}


def test_load_yaml_rejects_non_mapping(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        configs.load_yaml(p)


def test_load_and_validate_raises_when_job_schema_absent(tmp_path):
    # No job config schemas exist yet in WP0 (§9): each job's schema lands
    # with that job's own work package, not with Contracts Bootstrap.
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    with pytest.raises(SchemaNotFoundError):
        configs.load_and_validate(p, "train")
