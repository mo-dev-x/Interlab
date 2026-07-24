"""Content-hash strategies by artifact class (blueprint §2.2).

`core.hashing` implements all of these; subsystems MUST NOT implement their
own -- every content hash in the registry, regardless of artifact class,
traces back to a function in this module.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from interplab.core.canonical_json import canonicalize

SHA256_PREFIX = "sha256:"

_DEFAULT_EXCLUDE_SUFFIXES: tuple[str, ...] = (".tmp", ".temp", ".part")


def _prefixed(hex_digest: str) -> str:
    return f"{SHA256_PREFIX}{hex_digest}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_prefixed(data: bytes) -> str:
    return _prefixed(sha256_hex(data))


def hash_file(path: str | Path) -> str:
    """§2.2 "Single heavy file": sha256(file bytes)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return _prefixed(digest.hexdigest())


def hash_directory(
    path: str | Path,
    *,
    exclude_hidden: bool = True,
    exclude_suffixes: Iterable[str] = _DEFAULT_EXCLUDE_SUFFIXES,
) -> str:
    """§2.2 "Heavy directory" strategy: sha256 over the sorted lines
    `"<relpath>\\0<sha256(file)>\\n"` for every file; hidden/tmp files excluded.

    MUST be computed at creation, on the machine that created the directory
    (D1) -- this function only computes the hash, callers own when/where.
    """
    root = Path(path)
    if not root.is_dir():
        raise NotADirectoryError(root)

    lines: list[str] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(root)
        rel_posix = rel.as_posix()
        if exclude_hidden and any(part.startswith(".") for part in rel.parts):
            continue
        if any(rel_posix.endswith(suffix) for suffix in exclude_suffixes):
            continue
        file_hex = hash_file(file_path)[len(SHA256_PREFIX) :]
        lines.append(f"{rel_posix}\0{file_hex}\n")

    lines.sort()
    manifest_bytes = "".join(lines).encode("utf-8")
    return sha256_prefixed(manifest_bytes)


CHECKPOINT_IDENTITY_FILES: tuple[str, ...] = ("cfg.json", "sae_weights.safetensors")


def hash_checkpoint_dir(path: str | Path) -> str:
    """§2.2 heavy-directory manifest restricted to the SAELens load closure
    (ED-27, A5 identity): exactly `{cfg.json, sae_weights.safetensors}` --
    the files `SAE.load_from_pretrained` reads to instantiate the function
    a certificate speaks about. Same `"<relpath>\\0<sha256(file)>\\n"` sorted
    line format as `hash_directory`, but over this fixed file set only.

    Either file missing is a hard error, never a silently narrower subset.
    `trainer_state.pt`, `runner_cfg.json`, `sparsity.safetensors`, logs, and
    any other auxiliary or stray file are excluded from identity by
    construction -- this function never looks at anything but the two
    named files, regardless of what else is in `path`.

    MUST be computed at creation/backfill, on the machine holding the
    weights (D1) -- same discipline as `hash_directory`.
    """
    root = Path(path)
    if not root.is_dir():
        raise NotADirectoryError(root)

    lines: list[str] = []
    for name in CHECKPOINT_IDENTITY_FILES:
        file_path = root / name
        if not file_path.is_file():
            raise FileNotFoundError(
                f"checkpoint identity requires {name!r} in {root} (ED-27: the SAELens load "
                f"closure is exactly {CHECKPOINT_IDENTITY_FILES}); found no such file"
            )
        file_hex = hash_file(file_path)[len(SHA256_PREFIX) :]
        lines.append(f"{name}\0{file_hex}\n")

    lines.sort()
    manifest_bytes = "".join(lines).encode("utf-8")
    return sha256_prefixed(manifest_bytes)


def hash_recipe(recipe: dict) -> str:
    """§2.2 "External corpus" primary identity: sha256 of canonical JSON
    `{dataset, revision, split, subset_spec, filters}`."""
    return sha256_prefixed(canonicalize(recipe))


def hash_sample_checksum(texts: list[str], *, n: int = 1000) -> str:
    """§2.2 advisory `sample_checksum`: sha256 of the first `n` documents' text.

    Canonicalized as a JSON array of strings so the exact encoding is
    deterministic and auditable; this is advisory only, `hash_recipe` is the
    corpus's primary identity.
    """
    return sha256_prefixed(canonicalize(list(texts[:n])))


def hash_battery(concepts_dir: str | Path) -> str:
    """§2.2 ConceptBattery identity: content hash of the canonicalized file
    set (as a heavy directory)."""
    return hash_directory(concepts_dir)


def hash_self(artifact: dict) -> str:
    """§2.1 `self_hash`: sha256 of the canonical JSON form of the artifact
    with `self_hash` removed."""
    stripped = {key: value for key, value in artifact.items() if key != "self_hash"}
    return sha256_prefixed(canonicalize(stripped))


def short_hash(content_hash: str) -> str:
    """First 12 hex chars of a `sha256:<hex>` content hash (§3.1's `<hash12>`)."""
    if not content_hash.startswith(SHA256_PREFIX):
        raise ValueError(f"expected a 'sha256:'-prefixed hash, got {content_hash!r}")
    hex_part = content_hash[len(SHA256_PREFIX) :]
    if len(hex_part) != 64 or any(c not in "0123456789abcdef" for c in hex_part):
        raise ValueError(f"malformed sha256 hex digest: {content_hash!r}")
    return hex_part[:12]
