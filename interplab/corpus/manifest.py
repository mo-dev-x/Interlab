"""interplab.corpus.manifest (SS1, A1) -- builds a corpus_manifest payload.

§2.2: A1's primary identity is the recipe hash (`core.hashing.hash_recipe`),
recomputable from `payload["recipe"]`; the envelope's own `self_hash` (added
by `core.envelope.dump`) is the uniform registry-addressing mechanism, same
as every other artifact type -- nothing special-cased here.

ED-8 legacy provision: for pre-blueprint corpora whose full recipe is
unrecoverable, `recipe` fields MAY carry the literal string "unknown"; the
existing schema already allows this (`recipe.*` fields are plain strings),
so `build_payload` accepts whatever `recipe` dict it's given without
validating dataset/revision/split content -- `sample_checksum` remains
mandatory and becomes the operative identity in that case, exactly as ED-8
specifies.
"""

from __future__ import annotations

import json
from pathlib import Path

from interplab.core import hashing


def load_docs_jsonl(path: str | Path) -> list[str]:
    """Loads a `{"id": ..., "text": ...}`-per-line corpus file (the
    `tests/fixtures/pinned_text.jsonl` convention)."""
    docs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line)["text"])
    return docs


def count_tokens(docs: list[str], tokenizer) -> int:
    return sum(len(tokenizer(doc)["input_ids"]) for doc in docs)


def build_payload(
    *,
    name: str,
    recipe: dict,
    docs: list[str],
    tokenizer_name: str,
    tokenizer_revision: str,
    token_count: int,
    dedup_rate: float | None = None,
) -> dict:
    """Assembles the A1 payload. Callers supply `token_count` explicitly
    (via `count_tokens` for a fresh scan, or a recovered value for a legacy
    corpus per ED-8) so this function stays free of any tokenizer-loading
    concern -- `interplab.corpus` has no sanctioned dependency on a
    tokenizer-loading library beyond what the caller already has in hand."""
    return {
        "name": name,
        "recipe": recipe,
        "token_count": token_count,
        "doc_count": len(docs),
        "dedup_rate": dedup_rate,
        "tokenizer": {"name": tokenizer_name, "revision": tokenizer_revision},
        "sample_checksum": hashing.hash_sample_checksum(docs),
    }
