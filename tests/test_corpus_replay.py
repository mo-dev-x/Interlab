"""interplab.corpus.replay (ED-28): stream-opening, consumption-bound
(subset_spec), and shuffle-buffer logic. `iter_hf_dataset`'s real network
call is never exercised here (hard-CI budget, §8.3) -- it's tested against
a monkeypatched `datasets.load_dataset` so the integration contract (which
arguments get passed, which field gets read) is still verified.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from interplab.corpus import replay

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class _WordTokenizer:
    def __call__(self, text: str) -> dict:
        return {"input_ids": text.split()}


def test_iter_local_jsonl_streams_text_field():
    docs = list(replay.iter_local_jsonl(FIXTURES_DIR / "pinned_text.jsonl"))
    assert len(docs) == 200
    assert all(isinstance(d, str) and d for d in docs)


def test_iter_local_jsonl_is_a_generator_not_a_list():
    gen = replay.iter_local_jsonl(FIXTURES_DIR / "pinned_text.jsonl")
    assert not isinstance(gen, list)
    first = next(gen)
    assert isinstance(first, str)


def test_iter_hf_dataset_calls_load_dataset_streaming_and_reads_text_field(monkeypatch):
    calls = {}

    def fake_load_dataset(dataset, revision=None, split=None, streaming=None):
        calls["args"] = (dataset, revision, split, streaming)
        return [{"text": "row one"}, {"text": "row two"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    docs = list(replay.iter_hf_dataset("HuggingFaceFW/fineweb", revision="main", split="train"))

    assert calls["args"] == ("HuggingFaceFW/fineweb", "main", "train", True)
    assert docs == ["row one", "row two"]


def test_open_stream_local_scheme():
    docs = list(replay.open_stream(
        "local:tests/fixtures/pinned_text.jsonl", split="all", subset_spec=None,
    ))
    assert len(docs) == 200


def test_iter_local_hf_dataset_calls_load_dataset_streaming_with_no_revision(tmp_path, monkeypatch):
    """The real acquisition path used for this campaign's training corpus:
    the same `load_dataset(path, split=..., streaming=True)` call SAELens
    itself made against the local Arrow cache -- no `revision` (there is
    none for a local path)."""
    calls = {}

    def fake_load_dataset(path, split=None, streaming=None):
        calls["args"] = (path, split, streaming)
        return [{"text": "doc one"}, {"text": "doc two"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    local_cache_dir = tmp_path / "fineweb_subset"
    local_cache_dir.mkdir()

    docs = list(replay.iter_local_hf_dataset(local_cache_dir, split="train"))

    assert calls["args"] == (str(local_cache_dir), "train", True)
    assert docs == ["doc one", "doc two"]


def test_open_stream_local_scheme_dispatches_directories_to_hf_dataset_cache(tmp_path, monkeypatch):
    """A local: location that resolves to a directory (not a file) is a
    local HuggingFace dataset cache, not JSONL -- dispatched by what's
    actually on disk, no separate format flag needed."""
    def fake_load_dataset(path, split=None, streaming=None):
        assert path.endswith("fineweb_subset")
        assert split == "train"
        assert streaming is True
        return [{"text": "a"}, {"text": "b"}, {"text": "c"}]

    import datasets

    from interplab.core import uris

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    local_cache_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "fineweb_subset"
    local_cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        rel = local_cache_dir.relative_to(uris.REPO_ROOT).as_posix()
        docs = list(replay.open_stream(f"local:{rel}", split="train", subset_spec=None))
        assert docs == ["a", "b", "c"]
    finally:
        local_cache_dir.rmdir()


def test_open_stream_local_scheme_still_dispatches_files_to_jsonl():
    """A local: location resolving to a file stays JSONL -- the directory
    dispatch added for local HF dataset caches doesn't change the existing
    file-based fixture path."""
    docs = list(replay.open_stream(
        "local:tests/fixtures/pinned_text.jsonl", split="all", subset_spec=None,
    ))
    assert len(docs) == 200


def test_open_stream_hf_scheme(monkeypatch):
    def fake_load_dataset(dataset, revision=None, split=None, streaming=None):
        return [{"text": "a"}, {"text": "b"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    docs = list(replay.open_stream("hf:some/dataset@main", split="train", subset_spec=None))
    assert docs == ["a", "b"]


def test_open_stream_hf_scheme_requires_at_sign():
    """uris.parse itself enforces the '<dataset>@<revision>' shape for
    hf: locations (URIError, a ValueError) -- open_stream doesn't
    re-validate it, just lets it propagate."""
    from interplab.core.uris import URIError

    with pytest.raises(URIError):
        list(replay.open_stream("hf:no-at-sign", split="train", subset_spec=None))


def test_open_stream_rejects_unsupported_scheme():
    with pytest.raises(NotImplementedError):
        list(replay.open_stream("tamia:somewhere", split="train", subset_spec=None))


def test_apply_subset_spec_passthrough_for_none():
    docs = ["a", "b", "c"]
    assert list(replay.apply_subset_spec(iter(docs), None)) == docs


def test_apply_subset_spec_passthrough_for_legacy_unknown_string():
    """ED-8: subset_spec MAY be the literal string 'unknown'."""
    docs = ["a", "b"]
    assert list(replay.apply_subset_spec(iter(docs), "unknown")) == docs


def test_apply_subset_spec_take_docs():
    docs = ["a", "b", "c", "d"]
    result = list(replay.apply_subset_spec(iter(docs), {"take_docs": 2}))
    assert result == ["a", "b"]


def test_apply_subset_spec_take_tokens_is_document_granular():
    docs = ["one two", "three four five", "six"]
    result = list(replay.apply_subset_spec(iter(docs), {"take_tokens": 3}, tokenizer=_WordTokenizer()))
    # "one two" (2 tokens, running=2 < 3, included) then "three four five"
    # (3 tokens, running=2 < 3 so still included whole, running becomes 5) then stop.
    assert result == ["one two", "three four five"]


def test_apply_subset_spec_take_tokens_without_tokenizer_raises():
    with pytest.raises(ValueError, match="tokenizer"):
        list(replay.apply_subset_spec(iter(["a"]), {"take_tokens": 1}))


def test_apply_subset_spec_rejects_both_take_docs_and_take_tokens():
    with pytest.raises(ValueError, match="mutually exclusive"):
        list(replay.apply_subset_spec(iter(["a"]), {"take_docs": 1, "take_tokens": 1}, tokenizer=_WordTokenizer()))


def test_apply_subset_spec_shuffle_then_take_is_deterministic_for_fixed_seed():
    docs = [str(i) for i in range(20)]
    spec = {"shuffle": {"seed": 7, "buffer": 5}, "take_docs": 5}
    a = list(replay.apply_subset_spec(iter(docs), spec))
    b = list(replay.apply_subset_spec(iter(docs), spec))
    assert a == b
    assert len(a) == 5


def test_apply_subset_spec_shuffle_actually_reorders():
    docs = [str(i) for i in range(50)]
    shuffled = list(replay.apply_subset_spec(iter(docs), {"shuffle": {"seed": 1, "buffer": 20}}))
    assert sorted(shuffled) == sorted(docs)  # same multiset
    assert shuffled != docs  # but reordered


def test_buffered_shuffle_preserves_the_full_multiset():
    docs = [str(i) for i in range(37)]
    shuffled = list(replay.buffered_shuffle(iter(docs), seed=0, buffer=10))
    assert sorted(shuffled) == sorted(docs)


def test_buffered_shuffle_different_seeds_differ():
    docs = [str(i) for i in range(50)]
    a = list(replay.buffered_shuffle(iter(docs), seed=1, buffer=10))
    b = list(replay.buffered_shuffle(iter(docs), seed=2, buffer=10))
    assert a != b


def test_buffered_shuffle_rejects_non_positive_buffer():
    with pytest.raises(ValueError):
        list(replay.buffered_shuffle(iter(["a"]), seed=0, buffer=0))


def test_expected_packed_token_range_centers_on_token_count_plus_one_bos_per_doc():
    """ED-31: the center estimate is token_count + doc_count (one BOS per
    document boundary), not the raw document-stream token_count alone."""
    low, high = replay.expected_packed_token_range(token_count=1000, doc_count=50)
    center = 1000 + 50
    assert low == center - replay.PACKING_WINDOW_SLACK_TOKENS
    assert high == center + replay.PACKING_WINDOW_SLACK_TOKENS
    assert low < center < high


def test_expected_packed_token_range_is_generous_relative_to_packing_noise():
    """A delta of a few hundred tokens (typical BOS-count + a single
    dropped window) sits well inside the range, for a realistically-sized
    corpus."""
    token_count, doc_count = 50_000_000, 25_000
    low, high = replay.expected_packed_token_range(token_count, doc_count)
    plausible_packed = token_count + doc_count - 500  # a dropped final window
    assert low <= plausible_packed <= high


def test_expected_packed_token_range_excludes_gross_mismatches():
    """A completely different stream (order-of-magnitude off) falls well
    outside the range -- the band doesn't swallow real replay mistakes."""
    token_count, doc_count = 50_000_000, 25_000
    low, high = replay.expected_packed_token_range(token_count, doc_count)
    assert high < 999_999_999
    assert low > 1000
