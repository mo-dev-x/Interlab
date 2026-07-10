"""§5 SS4 eval-slice selection (ED-5): holdout_split matching A4.eval_holdout,
stream_offset for legacy checkpoints, and tokenization into batches."""

import pytest

from interplab.certification.eval_slice import (
    doc_hash_mod,
    load_corpus_docs,
    select_holdout_split,
    select_stream_offset,
    tokenize_to_batches,
)

_DOCS = [f"document number {i} with some filler words" for i in range(50)]


def test_doc_hash_mod_is_deterministic():
    assert doc_hash_mod("hello", 20) == doc_hash_mod("hello", 20)


def test_doc_hash_mod_in_range():
    for doc in _DOCS:
        assert 0 <= doc_hash_mod(doc, 7) < 7


def test_holdout_split_is_deterministic_and_disjoint_from_complement():
    held = select_holdout_split(_DOCS, modulus=10, residues=[0])
    held_again = select_holdout_split(_DOCS, modulus=10, residues=[0])
    assert held == held_again

    non_held = [d for d in _DOCS if d not in held]
    assert set(held).isdisjoint(non_held)
    assert len(held) + len(non_held) == len(_DOCS)


def test_holdout_split_multiple_residues_widens_selection():
    one_residue = select_holdout_split(_DOCS, modulus=10, residues=[0])
    two_residues = select_holdout_split(_DOCS, modulus=10, residues=[0, 1])
    assert set(one_residue) <= set(two_residues)


def test_stream_offset_selects_a_fixed_slice():
    selected = select_stream_offset(_DOCS, offset=5, count=3)
    assert selected == _DOCS[5:8]


def test_stream_offset_past_end_returns_partial():
    selected = select_stream_offset(_DOCS, offset=48, count=10)
    assert selected == _DOCS[48:50]


class _FakeTokenizer:
    """Deterministic stand-in: each doc tokenizes to a fixed number of ids."""

    def __call__(self, text: str) -> dict:
        return {"input_ids": list(range(len(text.split())))}


def test_tokenize_to_batches_respects_seq_len_and_batch_size():
    docs = ["one two three four five six seven eight"] * 10  # 8 tokens/doc
    batches = tokenize_to_batches(docs, _FakeTokenizer(), seq_len=4, batch_size=3, n_tokens=40)
    for b in batches[:-1]:
        assert b.shape[0] == 3
    assert all(b.shape[1] == 4 for b in batches)


def test_tokenize_to_batches_truncates_to_n_tokens():
    docs = ["one two three four five six seven eight"] * 10
    batches = tokenize_to_batches(docs, _FakeTokenizer(), seq_len=4, batch_size=100, n_tokens=12)
    total_tokens = sum(b.shape[0] * b.shape[1] for b in batches)
    assert total_tokens <= 12


def test_tokenize_to_batches_raises_when_not_enough_tokens():
    docs = ["one two"]
    with pytest.raises(ValueError):
        tokenize_to_batches(docs, _FakeTokenizer(), seq_len=100, batch_size=1, n_tokens=1000)


def test_load_corpus_docs_reads_pinned_fixture():
    docs = load_corpus_docs("local:tests/fixtures/pinned_text.jsonl")
    assert len(docs) == 200
    assert all(isinstance(d, str) and d for d in docs)


def test_load_corpus_docs_respects_limit():
    docs = load_corpus_docs("local:tests/fixtures/pinned_text.jsonl", limit=5)
    assert len(docs) == 5


def test_load_corpus_docs_rejects_unsupported_scheme():
    with pytest.raises(ValueError):
        load_corpus_docs("wandb:some-run")
