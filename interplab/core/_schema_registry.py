"""Private helper: locate and validate against `schemas/<type>/v<N>.schema.json`.

Not part of the public `interplab.core` surface (§5: core's public modules
are `hashing`, `envelope`, `uris`, `configs`, `canonical_json`). `envelope`
and `configs` both need "validate this dict against an externally versioned
JSON Schema file"; this is where that shared, artifact-agnostic plumbing
lives. Callers supply the artifact type / job name; nothing here hardcodes
any payload's field names, so the core invariant ("no module here knows any
artifact payload semantics") holds -- payload semantics live only in the
schema *files* under schemas/, which are data, not code.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_ROOT = REPO_ROOT / "schemas"


class SchemaNotFoundError(FileNotFoundError):
    pass


class SchemaValidationError(ValueError):
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


@functools.cache
def _load_schema(schema_path: Path) -> dict:
    if not schema_path.is_file():
        raise SchemaNotFoundError(str(schema_path))
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def artifact_schema_path(
    artifact_type: str, schema_version: int, *, schemas_root: Path = SCHEMAS_ROOT
) -> Path:
    return schemas_root / artifact_type / f"v{schema_version}.schema.json"


def config_schema_path(job_name: str, *, schemas_root: Path = SCHEMAS_ROOT) -> Path:
    return schemas_root / "configs" / f"{job_name}_v1.schema.json"


def validate(instance: dict, schema_path: Path) -> None:
    """Raise SchemaValidationError with every violation, not just the first."""
    schema = _load_schema(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: [str(p) for p in e.path])
    if errors:
        formatted = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]
        raise SchemaValidationError(f"{schema_path}: {len(errors)} error(s)", formatted)


def schema_compiles(schema_path: Path) -> None:
    """Raise if the schema file at `schema_path` is not itself a valid JSON Schema."""
    schema = _load_schema(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
