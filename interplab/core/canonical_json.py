"""Deterministic canonical JSON serialization (blueprint §2.1).

Follows RFC 8785 (JSON Canonicalization Scheme) structurally: object members
sorted by key, no insignificant whitespace, UTF-8 output, non-ASCII left
unescaped, non-finite numbers rejected. Number formatting uses Python's
native float/int representation rather than the ECMAScript algorithm RFC
8785 specifies: nothing outside this codebase needs to reproduce the exact
JCS byte form, only deterministic self-consistency within this Python
codebase, which Python's own formatting already guarantees across calls.
"""

from __future__ import annotations

import json
import math
from typing import Any


class CanonicalizationError(ValueError):
    pass


def _check_finite(obj: Any) -> None:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise CanonicalizationError(f"canonical JSON forbids non-finite float: {obj!r}")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"canonical JSON object keys must be str, got {type(key)!r}"
                )
            _check_finite(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _check_finite(value)


def canonicalize_str(obj: Any) -> str:
    """Render `obj` as canonical JSON text: sorted keys, compact separators,
    UTF-8-safe (non-ASCII unescaped), no NaN/Infinity."""
    _check_finite(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonicalize(obj: Any) -> bytes:
    """Canonical JSON as UTF-8 bytes, ready for hashing."""
    return canonicalize_str(obj).encode("utf-8")
