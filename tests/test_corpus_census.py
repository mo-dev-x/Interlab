"""interplab.corpus.census: literal term matching only (ED-9), single-pass
streaming scan (ED-28). Exercised through the public `build_payload`/
`scan_stream` entry points -- row assembly is an internal detail, but every
row-shape/matching-semantics guarantee `census_language_row` used to test
directly is still verified here, just via the public surface.
"""

from interplab.corpus.census import (
    build_payload,
    is_byte_fallback_token,
    scan_stream,
    term_token_split,
)


class _WordTokenizer:
    """Whitespace tokenizer; `tokenize(term)` splits on spaces, no subword
    merges -- enough to exercise token_split/byte_fallback plumbing without
    pulling in a real HF tokenizer. `__call__` (used for token counting)
    does the same whitespace split."""

    def tokenize(self, text: str) -> list[str]:
        return text.split()

    def __call__(self, text: str) -> dict:
        return {"input_ids": text.split()}


def _battery(concept_id: str, **languages) -> dict[str, dict]:
    return {concept_id: {"languages": languages}}


def test_is_byte_fallback_token():
    assert is_byte_fallback_token("<0x0A>")
    assert is_byte_fallback_token("<0xff>")
    assert not is_byte_fallback_token("poutine")
    assert not is_byte_fallback_token("<0x1>")


def test_term_token_split():
    assert term_token_split("world cup", _WordTokenizer()) == ["world", "cup"]


def test_no_terms_language_yields_null_counts():
    battery = _battery("poutine", en={"census_terms": []})
    payload, _ = build_payload(
        battery=battery, docs=["poutine is great"], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["poutine"]["en"]
    assert row == {
        "status": "no_terms", "per_term": None,
        "occurrences_total": None, "per_million_tokens": None, "doc_count": None,
    }


def test_measured_language_counts_word_boundary_matches():
    docs = ["I love poutine.", "Poutine and gravy.", "No relation here."]
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    payload, _ = build_payload(
        battery=battery, docs=docs, tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["poutine"]["en"]
    assert row["status"] == "measured"
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 2
    assert row["per_term"] == [
        {"term": "poutine", "occurrences": 2, "token_split": ["poutine"], "byte_fallback": False}
    ]


def test_word_boundary_does_not_match_substring():
    """ED-9: literal matching under the recorded boundary policy -- 'word'
    boundary must not match 'poutine' inside 'poutinerie'."""
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    payload, _ = build_payload(
        battery=battery, docs=["The poutinerie downtown is popular."], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["poutine"]["en"]
    assert row["occurrences_total"] == 0
    assert row["status"] == "measured"  # a term was recorded and searched; 0 is a real measurement


def test_substring_boundary_matches_within_words():
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    payload, _ = build_payload(
        battery=battery, docs=["The poutinerie downtown is popular."], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="substring",
    )
    assert payload["concepts"]["poutine"]["en"]["occurrences_total"] == 1


def test_case_folding_false_is_case_sensitive():
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    payload, _ = build_payload(
        battery=battery, docs=["Poutine", "poutine"], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=False, boundary="word",
    )
    assert payload["concepts"]["poutine"]["en"]["occurrences_total"] == 1


def test_multiple_terms_per_language_sum_into_totals():
    docs = ["cheese curds", "gouda wedge", "unrelated text"]
    battery = _battery(
        "cheese",
        en={"census_terms": [
            {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
            {"term": "gouda", "kind": "variant", "origin": "researcher:jdoe"},
        ]},
    )
    payload, _ = build_payload(
        battery=battery, docs=docs, tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["cheese"]["en"]
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 2
    assert [t["term"] for t in row["per_term"]] == ["cheese", "gouda"]


def test_doc_count_does_not_double_count_a_doc_matching_multiple_terms():
    battery = _battery(
        "cheese",
        en={"census_terms": [
            {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
            {"term": "gouda", "kind": "variant", "origin": "researcher:jdoe"},
        ]},
    )
    payload, _ = build_payload(
        battery=battery, docs=["cheese and gouda in one doc"], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["cheese"]["en"]
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 1


def test_byte_fallback_true_when_any_split_token_is_byte_fallback():
    class _ByteFallbackTokenizer(_WordTokenizer):
        def tokenize(self, text: str) -> list[str]:
            return ["<0x0A>", "poutine"]

    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    payload, _ = build_payload(
        battery=battery, docs=["poutine"], tokenizer=_ByteFallbackTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    assert payload["concepts"]["poutine"]["en"]["per_term"][0]["byte_fallback"] is True


def test_build_payload_emits_a_row_for_every_probe_language():
    battery = {
        "poutine": {
            "languages": {
                "en": {"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]},
                "fr": {"census_terms": []},
            }
        }
    }
    payload, _ = build_payload(
        battery=battery, docs=["poutine here"], tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    assert payload["method"] == {"matcher": "regex", "case_folding": True, "boundary": "word", "coverage": "full"}
    assert payload["concepts"]["poutine"]["en"]["status"] == "measured"
    assert payload["concepts"]["poutine"]["fr"]["status"] == "no_terms"


def test_build_payload_is_a_single_pass_over_a_one_shot_iterator():
    """ED-28: docs may be a genuine one-shot generator (not a re-iterable
    list) -- build_payload must still see every document exactly once,
    checking every term against it, not re-consume the iterator per term."""
    def one_shot():
        yield "cheese and gouda"
        yield "just cheese"

    battery = _battery(
        "cheese",
        en={"census_terms": [
            {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
            {"term": "gouda", "kind": "variant", "origin": "researcher:jdoe"},
        ]},
    )
    payload, stream_stats = build_payload(
        battery=battery, docs=one_shot(), tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    row = payload["concepts"]["cheese"]["en"]
    assert row["occurrences_total"] == 3  # cheese x2, gouda x1
    assert row["doc_count"] == 2
    assert stream_stats["total_docs"] == 2


def test_stream_stats_carries_token_and_doc_counts_and_sample():
    battery = _battery("poutine", en={"census_terms": []})
    docs = ["a b c", "d e"]
    _, stream_stats = build_payload(
        battery=battery, docs=docs, tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
    )
    assert stream_stats["total_tokens"] == 5
    assert stream_stats["total_docs"] == 2
    assert stream_stats["sample_docs"] == docs


def test_sampled_coverage_marks_estimated_and_records_sampling():
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    docs = ["poutine one", "poutine two", "poutine three", "poutine four"]
    payload, stream_stats = build_payload(
        battery=battery, docs=docs, tokenizer=_WordTokenizer(),
        matcher="regex", case_folding=True, boundary="word",
        census_take_docs=2, sampling_rule="stream_prefix", sampling_seed=None,
    )
    assert payload["method"]["coverage"] == "sampled"
    assert payload["method"]["sampling"] == {
        "rule": "stream_prefix", "seed": None, "realized_docs": 2, "realized_tokens": 4,
    }
    row = payload["concepts"]["poutine"]["en"]
    assert row["status"] == "estimated"
    assert row["occurrences_total"] == 2  # only the first 2 of 4 docs scanned
    # A1's manifest is unaffected by the census-level sample:
    assert stream_stats["total_docs"] == 4
    assert stream_stats["total_tokens"] == 8


def test_scan_stream_exposes_raw_counts_for_reuse():
    battery = _battery("poutine", en={"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]})
    scan = scan_stream(
        ["poutine here", "nothing"], battery=battery, tokenizer=_WordTokenizer(),
        boundary="word", case_folding=True,
    )
    assert scan["occurrences"][("poutine", "en", 0)] == 1
    assert scan["matched_docs"][("poutine", "en")] == 1
    assert scan["total_docs"] == 2
