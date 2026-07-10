"""§3.2 location URIs: `tamia:`, `local:`, `hf:`, `wandb:`.

`core.uris` parses/validates; no raw path strings in payloads -- every
cross-machine reference goes through a URI validated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Scheme = Literal["tamia", "local", "hf", "wandb"]
SCHEMES: tuple[Scheme, ...] = ("tamia", "local", "hf", "wandb")

REPO_ROOT = Path(__file__).resolve().parents[2]


class URIError(ValueError):
    pass


@dataclass(frozen=True)
class URI:
    scheme: Scheme
    value: str  # scheme-specific remainder, e.g. the path, `<dataset>@<revision>`, or run id

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}"


def parse(uri: str) -> URI:
    if ":" not in uri:
        raise URIError(f"not a valid location URI (missing scheme): {uri!r}")
    scheme, _, value = uri.partition(":")
    if scheme not in SCHEMES:
        raise URIError(f"unknown URI scheme {scheme!r}; must be one of {SCHEMES}")
    if not value:
        raise URIError(f"empty URI value: {uri!r}")

    if scheme == "local":
        _validate_relative_path(uri, value)
    elif scheme == "tamia":
        if value.startswith("/") or value.startswith("\\"):
            raise URIError(f"tamia: URIs are relative to $SCRATCH/interplab, got {uri!r}")
        _validate_relative_path(uri, value)
    elif scheme == "hf":
        if value.count("@") != 1:
            raise URIError(f"hf: URIs must be '<dataset>@<revision>', got {uri!r}")
        dataset, _, revision = value.partition("@")
        if not dataset or not revision:
            raise URIError(f"hf: URIs must be '<dataset>@<revision>', got {uri!r}")
    # wandb: value is an opaque run identifier -- nothing further to validate.

    return URI(scheme=scheme, value=value)  # type: ignore[arg-type]


def _validate_relative_path(uri: str, value: str) -> None:
    if value.startswith("/") or value.startswith("\\") or (len(value) > 1 and value[1] == ":"):
        raise URIError(f"path must be relative, got {uri!r}")
    parts = value.replace("\\", "/").split("/")
    if ".." in parts:
        raise URIError(f"path must not contain '..' traversal: {uri!r}")


def validate(uri: str) -> None:
    parse(uri)


def resolve_local(uri: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve a `local:` URI to an actual filesystem path under `repo_root`.

    Only `local:` is resolvable this way -- `tamia:` needs `$SCRATCH` (a
    cluster-only concept not meaningful here), and `hf:`/`wandb:` are
    resolved by their own client libraries, not by path lookup.
    """
    parsed = parse(uri)
    if parsed.scheme != "local":
        raise URIError(f"resolve_local only accepts 'local:' URIs, got {uri!r}")
    return repo_root / parsed.value
