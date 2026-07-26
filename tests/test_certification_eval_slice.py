"""§5 SS4 eval-slice selection (ED-5): holdout_split matching A4.eval_holdout,
stream_offset for legacy checkpoints, and tokenization into batches."""

import pytest

from interplab.certification.eval_slice import (
    doc_hash_mod,
    iter_corpus_docs,
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


def test_load_corpus_docs_dispatches_local_directories_to_hf_dataset_cache(tmp_path, monkeypatch):
    """ED-34: a local: location resolving to a directory is a local
    HuggingFace dataset cache, not JSONL -- eval_slice's local: branch used
    to handle JSONL only, which is exactly the deeper defect ED-34 named."""
    from interplab.core import uris

    def fake_load_dataset(path, split=None, streaming=None):
        assert path.endswith("fineweb_subset")
        assert split == "train"
        assert streaming is True
        return [{"text": "a"}, {"text": "b"}, {"text": "c"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    local_cache_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "fineweb_subset"
    local_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = local_cache_dir.relative_to(uris.REPO_ROOT).as_posix()
        docs = load_corpus_docs(f"local:{rel}")
        assert docs == ["a", "b", "c"]
    finally:
        local_cache_dir.rmdir()


def test_load_corpus_docs_resolves_tamia_jsonl_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRATCH", str(tmp_path))
    corpus_dir = tmp_path / "interplab" / "eval_corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "docs.jsonl").write_text('{"id": 0, "text": "hello"}\n{"id": 1, "text": "world"}\n', encoding="utf-8")

    docs = load_corpus_docs("tamia:eval_corpus/docs.jsonl")
    assert docs == ["hello", "world"]


def test_load_corpus_docs_dispatches_tamia_directories_to_hf_dataset_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRATCH", str(tmp_path))
    cache_dir = tmp_path / "interplab" / "hf_cache" / "fineweb_subset"
    cache_dir.mkdir(parents=True)

    def fake_load_dataset(path, split=None, streaming=None):
        assert path.endswith("fineweb_subset")
        assert split == "train"
        assert streaming is True
        return [{"text": "x"}, {"text": "y"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    docs = load_corpus_docs("tamia:hf_cache/fineweb_subset")
    assert docs == ["x", "y"]


def test_load_corpus_docs_tamia_without_scratch_raises_clearly(monkeypatch):
    monkeypatch.delenv("SCRATCH", raising=False)
    with pytest.raises(Exception, match="SCRATCH"):
        load_corpus_docs("tamia:eval_corpus/docs.jsonl")


# ED-34 Gate-3: lazy iter_corpus_docs + stream_offset that never materializes the corpus.


def test_iter_corpus_docs_matches_eager_load():
    eager = load_corpus_docs("local:tests/fixtures/pinned_text.jsonl")
    lazy = list(iter_corpus_docs("local:tests/fixtures/pinned_text.jsonl"))
    assert lazy == eager


def test_stream_offset_over_iterator_is_byte_identical_to_list_slice():
    eager = load_corpus_docs("local:tests/fixtures/pinned_text.jsonl")
    lazy_slice = select_stream_offset(
        iter_corpus_docs("local:tests/fixtures/pinned_text.jsonl"), offset=10, count=5
    )
    assert lazy_slice == eager[10:15]


def test_stream_offset_materializes_only_offset_plus_count_from_lazy_source():
    """The core Gate-3 guarantee: islice stops after offset+count and never
    consumes (nor materializes) the rest of the stream -- proven here against
    an unbounded generator that would hang/OOM if fully consumed."""
    produced = {"n": 0}

    def unbounded():
        i = 0
        while True:
            produced["n"] += 1
            yield f"doc {i}"
            i += 1

    selected = select_stream_offset(unbounded(), offset=5, count=3)
    assert selected == [f"doc {i}" for i in range(5, 8)]
    assert produced["n"] == 8  # exactly offset+count consumed, then stopped
