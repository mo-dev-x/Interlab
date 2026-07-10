"""SS10 registry: put/get/find over the registry/ tree (§3.4).

`new_run_card`/`RunCardHandle` live in `interplab.registry.run_card` (pulled
forward into WP2 per ED-6, ahead of WP7's original "run cards everywhere"
scope, since `certify` is the first real job and Ground Rule 4 is
unconditional).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from interplab.core import envelope, hashing

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_ROOT = REPO_ROOT / "registry"

Hash = str


class RegistryError(ValueError):
    pass


def _type_dir(artifact_type: str, *, registry_root: Path) -> Path:
    return registry_root / artifact_type


def _artifact_path(artifact_type: str, hash12: str, *, registry_root: Path) -> Path:
    return _type_dir(artifact_type, registry_root=registry_root) / f"{hash12}.json"


def put(artifact: dict, *, registry_root: Path = REGISTRY_ROOT) -> Hash:
    """Validate schema + self-hash, then write (§5 SS10). The only writer of
    registry/ files.

    Files are immutable once written: writing a different artifact to the
    path an existing hash already occupies is a hard error; writing
    byte-for-byte-equivalent content again is a no-op (§5 SS10 invariant).
    """
    # put() is the trust boundary: re-verify independent of what the caller claims.
    artifact = envelope.load(artifact)

    artifact_type = artifact["artifact_type"]
    content_hash = artifact["self_hash"]
    hash12 = hashing.short_hash(content_hash)

    type_dir = _type_dir(artifact_type, registry_root=registry_root)
    type_dir.mkdir(parents=True, exist_ok=True)
    dest = _artifact_path(artifact_type, hash12, registry_root=registry_root)

    if dest.exists():
        existing = json.loads(dest.read_text(encoding="utf-8"))
        if existing != artifact:
            raise RegistryError(
                f"refusing to overwrite {dest}: existing content differs from the artifact "
                f"being written, despite matching hash12 {hash12!r} (registry files are immutable)"
            )
        return content_hash

    fd, tmp_path = tempfile.mkstemp(prefix=f".{hash12}-", suffix=".json.tmp", dir=type_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp_path, dest)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    return content_hash


def get(h: Hash, *, registry_root: Path = REGISTRY_ROOT) -> dict:
    """Look up an artifact by its full content hash.

    Lookup is by hash12 prefix on disk (registry files are named
    `<hash12>.json`), but content addressing is a property of the full
    hash: the loaded artifact's `self_hash` MUST exactly equal `h`, or this
    raises rather than silently returning a hash12 collision.
    """
    hash12 = hashing.short_hash(h)
    matches = list(registry_root.glob(f"*/{hash12}.json"))
    if not matches:
        raise RegistryError(f"no registry artifact found for hash {h!r}")
    if len(matches) > 1:
        raise RegistryError(f"ambiguous hash {h!r}: found in multiple type directories: {matches}")

    artifact = envelope.load(matches[0])
    if artifact["self_hash"] != h:
        raise RegistryError(
            f"content-addressing violation: {matches[0]} has self_hash "
            f"{artifact['self_hash']!r}, expected {h!r} (hash12 {hash12!r} "
            "collision or corrupted registry file)"
        )
    return artifact


def find(
    artifact_type: str,
    subject_hash: Hash | None = None,
    *,
    registry_root: Path = REGISTRY_ROOT,
    **payload_filters: Any,
) -> list[dict]:
    type_dir = _type_dir(artifact_type, registry_root=registry_root)
    if not type_dir.is_dir():
        return []

    results = []
    for path in sorted(type_dir.glob("*.json")):
        artifact = envelope.load(path)
        if subject_hash is not None:
            subject_hashes = {ref["content_hash"] for ref in artifact["subject"]}
            if subject_hash not in subject_hashes:
                continue
        payload = artifact["payload"]
        if any(payload.get(key) != value for key, value in payload_filters.items()):
            continue
        results.append(artifact)
    return results
