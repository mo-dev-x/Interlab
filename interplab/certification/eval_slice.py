"""§5 SS4 eval-slice selection (ED-5): deterministic text selection matching
A4's `eval_holdout` rule (store-backed checkpoints) or a recorded
stream-offset argument (legacy checkpoints), then tokenization into
fixed-length batches for fresh activation collection.
"""

from __future__ import annotations

import hashlib
import json

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


def select_stream_offset(docs: list[str], *, offset: int, count: int) -> list[str]:
    """A6 `selection.method == "stream_offset"`: a recorded, fixed
    positional slice for legacy checkpoints. Disjointness here is "by
    offset argument" -- a recorded claim, not a structural guarantee,
    since legacy stores predate `eval_holdout`."""
    return docs[offset : offset + count]


def load_corpus_docs(location: str, *, text_field: str = "text", limit: int | None = None) -> list[str]:
    """Loads raw document text from a `local:` (JSONL, one `{"text": ...}`
    per line -- the same shape as tests/fixtures/pinned_text.jsonl) or
    `hf:` (streamed via `datasets`) URI. `tamia:` is not resolvable here
    (no `$SCRATCH` mount in this environment); `wandb:` is not a text
    source.
    """
    parsed = uris.parse(location)

    if parsed.scheme == "local":
        path = uris.resolve_local(location)
        docs: list[str] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                docs.append(json.loads(line)[text_field])
                if limit is not None and len(docs) >= limit:
                    break
        return docs

    if parsed.scheme == "hf":
        import datasets

        dataset_name, _, revision = parsed.value.partition("@")
        ds = datasets.load_dataset(dataset_name, revision=revision, split="train", streaming=True)
        docs = []
        for row in ds:
            docs.append(row[text_field])
            if limit is not None and len(docs) >= limit:
                break
        return docs

    raise ValueError(f"unsupported corpus location scheme for eval slice: {parsed.scheme!r}")


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
