"""§5 SS4 eval-slice selection (ED-5): deterministic text selection matching
A4's `eval_holdout` rule (store-backed checkpoints) or a recorded
stream-offset argument (legacy checkpoints), then tokenization into
fixed-length batches for fresh activation collection.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterator
from pathlib import Path

import torch

from interplab.core import uris


def doc_hash_mod(doc_id: str, modulus: int) -> int:
    """Deterministic hash-mod matching A4.eval_holdout's rule: a stable
    function of document content, not a random seed, so the same rule
    applied independently at store-collection time and at certification
    time always selects the same documents."""
    digest = hashlib.sha256(doc_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % modulus


def select_holdout_split(docs: list[str], *, modulus: int, residues: list[int]) -> list[str]:
    """A6 `selection.method == "holdout_split"`: documents whose
    `doc_hash_mod` falls in `residues` -- the same rule A4.eval_holdout
    records, applied here at certification time. Disjoint from training
    "by construction" since the store never saw these documents."""
    residue_set = set(residues)
    return [doc for doc in docs if doc_hash_mod(doc, modulus) in residue_set]


def select_stream_offset(docs, *, offset: int, count: int) -> list[str]:
    """A6 `selection.method == "stream_offset"`: a recorded, fixed
    positional slice for legacy checkpoints. Disjointness here is "by
    offset argument" -- a recorded claim, not a structural guarantee,
    since legacy stores predate `eval_holdout`.

    ED-34 Gate-3: `docs` may be a materialized list OR a lazy iterator
    (`iter_corpus_docs`). `itertools.islice(docs, offset, offset + count)`
    is byte-identical to `docs[offset:offset + count]` for a list, but over
    an iterator it materializes only the `count` selected documents -- never
    the full corpus (32.6M docs / ~101GB for `fineweb_subset`). Pure
    performance; the certified slice is unchanged."""
    return list(itertools.islice(docs, offset, offset + count))


def _iter_local_jsonl(path: Path) -> Iterator[str]:
    """Duplicated from `interplab.corpus.replay.iter_local_jsonl` (Ground
    Rule 2: `certification` may only import `core`, `registry` -- not
    `corpus`). Streams a `{"id": ..., "text": ...}`-per-line file's `text`
    field one document at a time (ED-34 Gate-3: a generator, mirroring the
    blessed `replay` twin -- never materializes the file)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)["text"]


def _iter_local_hf_dataset(path: Path, *, split: str, text_field: str = "text") -> Iterator[str]:
    """Duplicated from `interplab.corpus.replay.iter_local_hf_dataset`
    (Ground Rule 2, same as above -- `replay.iter_local_hf_dataset` depends
    on `datasets`, so it cannot be promoted to `core` either, which is
    stdlib/numpy/pydantic/jsonschema only). Same acquisition method
    SAELens itself used at training time: `datasets.load_dataset(path,
    split=..., streaming=True)`, no `revision` -- the directory's own
    content is the pin, same as any other `local:`/`tamia:` resource.

    ED-34 Gate-3: a generator (yields one document at a time), mirroring the
    blessed `replay.iter_local_hf_dataset` twin -- never materializes the
    corpus, so a downstream `stream_offset` islice touches only the
    documents it selects."""
    from datasets import load_dataset

    ds = load_dataset(str(path), split=split, streaming=True)
    for row in ds:
        yield row[text_field]


def iter_corpus_docs(location: str, *, split: str = "train", text_field: str = "text") -> Iterator[str]:
    """Lazy document-text stream from a `local:`/`tamia:` location or a
    remote `hf:` (streamed via `datasets`) URI. `wandb:` is not a text
    source.

    ED-34: `local:`/`tamia:` dispatch on what's actually at the resolved
    path -- a file streams as JSONL (the same shape as
    tests/fixtures/pinned_text.jsonl); a directory streams as a local
    HuggingFace dataset cache (`_iter_local_hf_dataset`), the format the
    real training corpus is stored in (per A5 `config.dataset_path`).
    Mirrors `corpus.replay.open_stream`'s own file-vs-directory dispatch,
    duplicated rather than imported (cross-referenced as sanctioned twins,
    ED-34).

    ED-34 Gate-3: this is a **generator** -- it never materializes the
    corpus. `select_stream_offset` islices it, so a positional slice touches
    only the documents it selects; `load_corpus_docs` (below) wraps it when a
    fully materialized list is actually wanted.
    """
    parsed = uris.parse(location)

    if parsed.scheme in ("local", "tamia"):
        path = uris.resolve_local(location) if parsed.scheme == "local" else uris.resolve_tamia(location)
        rows = (
            _iter_local_hf_dataset(path, split=split, text_field=text_field)
            if path.is_dir()
            else _iter_local_jsonl(path)
        )
        yield from rows
        return

    if parsed.scheme == "hf":
        import datasets

        dataset_name, _, revision = parsed.value.partition("@")
        ds = datasets.load_dataset(dataset_name, revision=revision, split=split, streaming=True)
        for row in ds:
            yield row[text_field]
        return

    raise ValueError(f"unsupported corpus location scheme for eval slice: {parsed.scheme!r}")


def load_corpus_docs(
    location: str, *, split: str = "train", text_field: str = "text", limit: int | None = None
) -> list[str]:
    """Materializing wrapper over `iter_corpus_docs` (backward-compatible
    list return). Used by the `holdout_split` path, which must scan the whole
    corpus. `limit` early-stops the stream via `islice` -- so a bounded read
    (e.g. a test fixture, or the first N documents) never reads further than
    asked. The `stream_offset` path does NOT go through here: it consumes
    `iter_corpus_docs` lazily so only the selected `count` documents are
    materialized (ED-34 Gate-3)."""
    rows = iter_corpus_docs(location, split=split, text_field=text_field)
    if limit is not None:
        return list(itertools.islice(rows, limit))
    return list(rows)


def tokenize_to_batches(
    docs: list[str],
    tokenizer,
    *,
    seq_len: int,
    batch_size: int,
    n_tokens: int,
) -> list[torch.Tensor]:
    """Concatenates tokenized docs into a flat stream, chunks into
    fixed-length `seq_len` rows, batches them, truncated to `n_tokens`."""
    all_ids: list[int] = []
    for doc in docs:
        all_ids.extend(tokenizer(doc)["input_ids"])
        if len(all_ids) >= n_tokens:
            break
    all_ids = all_ids[:n_tokens]

    n_rows = len(all_ids) // seq_len
    if n_rows == 0:
        raise ValueError(
            f"not enough tokens ({len(all_ids)}) in the selected slice to form even one "
            f"row of seq_len={seq_len}"
        )
    all_ids = all_ids[: n_rows * seq_len]

    tensor = torch.tensor(all_ids, dtype=torch.long).reshape(n_rows, seq_len)
    return [tensor[i : i + batch_size] for i in range(0, n_rows, batch_size)]
