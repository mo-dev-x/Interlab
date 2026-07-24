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

ED-28: `build_payload` takes precomputed `doc_count`/`token_count` and a
bounded `sample_docs` (the first up to 1000 documents in stream order, per
`hashing.hash_sample_checksum`'s own `n=1000` default) rather than a full
`docs: list[str]` -- the caller (`interplab.jobs.census`, via
`interplab.corpus.census.scan_stream`) produces these as a by-product of a
single streaming pass over the corpus, since materializing the whole
consumed stream in memory is exactly what ED-28 forbids. Document loading
itself lives in `interplab.corpus.replay`, not here.
"""

from __future__ import annotations

from interplab.core import hashing


def build_payload(
    *,
    name: str,
    recipe: dict,
    doc_count: int,
    sample_docs: list[str],
    tokenizer_name: str,
    tokenizer_revision: str,
    token_count: int,
    dedup_rate: float | None = None,
) -> dict:
    """Assembles the A1 payload. Callers supply `token_count`/`doc_count`
    explicitly (from a fresh streaming scan, or recovered values for a
    legacy corpus per ED-8) so this function stays free of any
    tokenizer-loading or stream-consuming concern. `sample_docs` MUST be
    the first `doc_count` documents in stream order (or all of them, if
    fewer than 1000) -- `sample_checksum`'s well-definedness depends on
    that order being pinned (ED-28)."""
    return {
        "name": name,
        "recipe": recipe,
        "token_count": token_count,
        "doc_count": doc_count,
        "dedup_rate": dedup_rate,
        "tokenizer": {"name": tokenizer_name, "revision": tokenizer_revision},
        "sample_checksum": hashing.hash_sample_checksum(sample_docs),
    }
