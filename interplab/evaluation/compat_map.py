"""SS8 `eval_compat_map` I/O (§5 SS8, A12, D2): A12 is "edited only by hand,
by the researcher" -- not computed by any job. This module wraps a
hand-authored payload (`{version, judge_classes}`) into a proper envelope
(`self_hash` is computed, never hand-assembled -- §2.1) and registers it,
the same `envelope.dump` + `registry.put` path every other artifact in this
codebase goes through. No `interplab.jobs.*` module: A12 registration isn't
one of §6.1's named jobs, so there is no RunCard to write (Ground Rule 4
applies to jobs; this is a library helper the researcher invokes directly).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from interplab.core import envelope
from interplab.registry.registry import REGISTRY_ROOT
from interplab.registry.registry import put as registry_put


def load_payload(path: str | Path) -> dict:
    """Load a hand-authored `{version, judge_classes}` payload from YAML or
    JSON. Payload-only -- envelope fields are added by `register`, never
    hand-written."""
    with open(path, encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a mapping at the top level, got {type(payload).__name__}")
    return payload


def register(
    payload: dict, *, created_by: dict, registry_root: Path = REGISTRY_ROOT
) -> str:
    """Wrap `payload` into a schema-validated, self-hashed envelope and
    register it. Raises `SchemaValidationError` (via `envelope.dump`) if
    `payload` doesn't match A12's schema -- the same fail-fast discipline
    every other artifact-producing path in this codebase already has."""
    artifact = envelope.dump(
        artifact_type="eval_compat_map",
        schema_version=1,
        created_by=created_by,
        subject=[],
        payload=payload,
    )
    return registry_put(artifact, registry_root=registry_root)


def load_and_register(
    path: str | Path, *, created_by: dict, registry_root: Path = REGISTRY_ROOT
) -> str:
    return register(load_payload(path), created_by=created_by, registry_root=registry_root)
