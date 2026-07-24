"""interplab.corpus.replay (SS1, ED-28) -- replays the token stream an A1
corpus_manifest's recipe defines. ED-28: "A1 describes a defined token
stream, never an available dataset." `docs_location` says WHERE (a local:
JSONL file, a local: HuggingFace Arrow dataset cache directory, or an hf:
remote Hub dataset); `recipe['subset_spec']` says HOW MUCH and in what
order -- the consumption bound (`order`, `take_docs`/`take_tokens`,
`shuffle: {seed, buffer}`).

`local:` resolves to a real filesystem path (`uris.resolve_local`) and is
dispatched on what's actually there, not on any config-level format flag:
a file is a JSONL document-per-line corpus (`iter_local_jsonl`); a
directory is a local HuggingFace dataset cache (`iter_local_hf_dataset`)
-- the on-disk format SAELens itself streamed from during real training,
opened the same way SAELens did:
`datasets.load_dataset(<local_path>, split=..., streaming=True)`, with no
`revision` (a local cache has no Hub revision to pin; the directory
contents ARE the pin, same as any other `local:` resource).

This is the only place `interplab.corpus`/`interplab.jobs.census` reads
document text from. Every function here is a generator (or wraps one):
callers never materialize the whole stream in memory.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path

from interplab.core import uris

PACKING_WINDOW_SLACK_TOKENS = 8192
"""ED-31: generous bound on the token delta SAELens packing (a dropped
final partial window, plus any cross-boundary merge effects) can
introduce between the document-stream token count and a training run's
packed/windowed counter. Real `context_size` values used by this lab's
SAE training runs are <= 2048; this is 4x that -- deliberately generous
so genuine packing noise never trips it, while a real replay mistake
(wrong dataset/subset_spec/revision), which differs by a large fraction
of the whole corpus, still exceeds it by orders of magnitude."""


def expected_packed_token_range(token_count: int, doc_count: int) -> tuple[int, int]:
    """ED-31: SAELens packs the document stream before training --
    concatenating documents with a BOS separator between them (plus one
    `prepend_bos` at the very start), then cutting the result into fixed
    `context_size` windows. That packed/windowed counter
    (`n_training_samples`) is therefore NOT the document-stream
    `token_count` A1 certifies: packing is a training-side transformation
    applied to the corpus, not a property of it, so A1's identity is
    (deliberately) packing-independent.

    Returns the structural range a training run's packed token counter is
    expected to fall in for a correct replay of this same document
    stream: `token_count` plus one BOS per document boundary (`doc_count`,
    exact), +/- `PACKING_WINDOW_SLACK_TOKENS` covering the dropped final
    partial window and any cross-boundary merge effects. A value outside
    this range is a structural, order-of-magnitude mismatch -- not
    explainable by packing -- and signals a genuine replay problem
    (wrong dataset, subset_spec, or revision), never a mere packing
    artifact.
    """
    center = token_count + doc_count
    return center - PACKING_WINDOW_SLACK_TOKENS, center + PACKING_WINDOW_SLACK_TOKENS


def iter_local_jsonl(path: str | Path) -> Iterator[str]:
    """Streams a `{"id": ..., "text": ...}`-per-line file's `text` field,
    one document at a time -- never materializes the file in memory."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)["text"]


def iter_local_hf_dataset(path: str | Path, *, split: str, text_field: str = "text") -> Iterator[str]:
    """Streams a local HuggingFace dataset cache's `text_field`, one
    document at a time, via the same acquisition method SAELens itself
    used during real training (`datasets.load_dataset(<local_path>,
    split=..., streaming=True)`) -- no `revision` (there is no Hub
    revision for a local path; the directory's own content is the pin,
    same as any other `local:` resource) and no download (the path is
    already local)."""
    from datasets import load_dataset

    ds = load_dataset(str(path), split=split, streaming=True)
    for row in ds:
        yield row[text_field]


def iter_hf_dataset(dataset: str, *, revision: str, split: str, text_field: str = "text") -> Iterator[str]:
    """Streams a HuggingFace dataset's `text_field`, one document at a
    time, via `datasets`' own streaming mode -- never downloads or
    materializes the dataset."""
    from datasets import load_dataset

    ds = load_dataset(dataset, revision=revision, split=split, streaming=True)
    for row in ds:
        yield row[text_field]


def buffered_shuffle(docs: Iterator[str], *, seed: int, buffer: int) -> Iterator[str]:
    """Deterministic shuffle-buffer (ED-28 `subset_spec.shuffle`): fills a
    buffer of `buffer` documents, then for each new document swaps it in
    at a uniformly random buffer slot and yields the evicted one -- the
    standard streaming-shuffle algorithm (as used by tf.data / HF
    `IterableDataset`). Reimplemented here rather than depended on from a
    library, since ED-28 pins `{seed, buffer}` as the reproducibility
    contract, not any particular library's internal behavior.
    """
    if buffer < 1:
        raise ValueError(f"shuffle buffer must be >= 1, got {buffer}")
    rng = random.Random(seed)
    reservoir: list[str] = []
    for doc in docs:
        if len(reservoir) < buffer:
            reservoir.append(doc)
            continue
        idx = rng.randrange(buffer)
        yield reservoir[idx]
        reservoir[idx] = doc
    rng.shuffle(reservoir)
    yield from reservoir


def apply_subset_spec(docs: Iterator[str], subset_spec: dict | str | None, *, tokenizer=None) -> Iterator[str]:
    """Applies ED-28's consumption bound to a document stream.

    `subset_spec` may be `None`, a plain string (ED-8 legacy "unknown"), or
    a dict with any of: `shuffle: {seed, buffer}` (applied first -- order
    is pinned by shuffling, if at all, before truncating); `take_docs: int`
    XOR `take_tokens: int` (mutually exclusive -- `take_tokens` requires
    `tokenizer` to know where the token boundary falls; truncation is
    document-granular, i.e. the document that crosses the bound is
    included whole, matching how `sample_checksum`'s "first 1000 documents"
    is also document-, not token-, granular).

    A `None`/string/dict-without-these-keys `subset_spec` passes the
    stream through unbounded (the ED-8 legacy / "no consumption bound"
    case).
    """
    if not isinstance(subset_spec, dict):
        yield from docs
        return

    stream = docs
    shuffle = subset_spec.get("shuffle")
    if shuffle:
        stream = buffered_shuffle(stream, seed=shuffle["seed"], buffer=shuffle["buffer"])

    take_docs = subset_spec.get("take_docs")
    take_tokens = subset_spec.get("take_tokens")
    if take_docs is not None and take_tokens is not None:
        raise ValueError("subset_spec: take_docs and take_tokens are mutually exclusive")

    if take_docs is not None:
        for i, doc in enumerate(stream):
            if i >= take_docs:
                return
            yield doc
        return

    if take_tokens is not None:
        if tokenizer is None:
            raise ValueError("subset_spec.take_tokens requires a tokenizer to locate the token boundary")
        consumed = 0
        for doc in stream:
            if consumed >= take_tokens:
                return
            consumed += len(tokenizer(doc)["input_ids"])
            yield doc
        return

    yield from stream


def open_stream(
    location: str, *, split: str, subset_spec: dict | str | None, tokenizer=None
) -> Iterator[str]:
    """Resolves `location` (`local:` or `hf:`) to a document-text stream,
    honoring `subset_spec`'s consumption bound (ED-28). `split` comes from
    the recipe, not the URI -- `hf:` locations are `<dataset>@<revision>`
    only (§3.2); the split is a separate, orthogonal recipe field.

    `uris.parse` already enforces the `<dataset>@<revision>` shape for
    `hf:` locations (raising `URIError`, a `ValueError`), so this function
    does not re-validate it.

    A `local:` location dispatches on what's actually at the resolved
    path: a file streams as JSONL (`iter_local_jsonl`); a directory
    streams as a local HuggingFace dataset cache (`iter_local_hf_dataset`)
    -- the format SAELens itself trained from for this campaign's real
    corpora, opened the same way it did (`load_dataset(path, split=...,
    streaming=True)`, no `revision`).
    """
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        resolved = uris.resolve_local(location)
        raw = iter_local_hf_dataset(resolved, split=split) if resolved.is_dir() else iter_local_jsonl(resolved)
    elif parsed.scheme == "hf":
        dataset, _, revision = parsed.value.partition("@")
        raw = iter_hf_dataset(dataset, revision=revision, split=split)
    else:
        raise NotImplementedError(
            f"corpus replay can only stream local: or hf: locations in this environment; got {location!r}"
        )
    yield from apply_subset_spec(raw, subset_spec, tokenizer=tokenizer)
