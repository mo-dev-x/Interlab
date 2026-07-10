"""§2.1 artifact envelope: load/dump with self-hash verification.

`envelope.load()` is the only sanctioned way to read a registry artifact;
never hand-parse a registry JSON file (§2.1). No artifact-payload semantics
live here -- `payload` is an opaque dict; per-type field meaning is enforced
only via the schema file located through `_schema_registry`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from interplab.core import hashing
from interplab.core._schema_registry import artifact_schema_path
from interplab.core._schema_registry import validate as validate_against_schema


class EnvelopeHashMismatchError(ValueError):
    pass


class CreatedBy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    code_commit: str
    entrypoint: str
    host: str


class SubjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_hash: str
    location: str
    role: str


class Envelope(BaseModel):
    """Typed view of the common §2.1 fields. `payload` stays an opaque dict."""

    model_config = ConfigDict(extra="forbid")
    artifact_type: str
    schema_version: int
    self_hash: str
    created_at: str
    created_by: CreatedBy
    subject: list[SubjectRef]
    payload: dict[str, Any]


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_self_hash(artifact: dict) -> str:
    return hashing.hash_self(artifact)


def verify(artifact: dict) -> None:
    """Raise EnvelopeHashMismatchError if `self_hash` does not match recomputation."""
    if "self_hash" not in artifact:
        raise EnvelopeHashMismatchError("artifact has no self_hash field")
    expected = hashing.hash_self(artifact)
    if artifact["self_hash"] != expected:
        raise EnvelopeHashMismatchError(
            f"self_hash mismatch: stored={artifact['self_hash']!r} recomputed={expected!r}"
        )


def dump(
    *,
    artifact_type: str,
    schema_version: int,
    created_by: dict,
    subject: list[dict],
    payload: dict,
    created_at: str | None = None,
) -> dict:
    """Build a complete, self-hashed, schema-validated envelope dict.

    This is the only sanctioned way to construct a registry artifact; never
    hand-assemble the envelope fields.
    """
    artifact: dict[str, Any] = {
        "artifact_type": artifact_type,
        "schema_version": schema_version,
        "created_at": created_at or utcnow_iso(),
        "created_by": created_by,
        "subject": subject,
        "payload": payload,
    }
    artifact["self_hash"] = compute_self_hash(artifact)

    Envelope.model_validate(artifact)
    schema_path = artifact_schema_path(artifact_type, schema_version)
    validate_against_schema(artifact, schema_path)
    return artifact


def load(source: dict | str | Path) -> dict:
    """Load (if given a path), verify `self_hash`, validate against the
    declared type/version schema, and return the artifact dict."""
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as f:
            artifact = json.load(f)
    else:
        artifact = source

    Envelope.model_validate(artifact)
    verify(artifact)

    schema_path = artifact_schema_path(artifact["artifact_type"], artifact["schema_version"])
    validate_against_schema(artifact, schema_path)
    return artifact
