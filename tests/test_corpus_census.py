"""interplab.corpus.census: literal term matching only (ED-9)."""

from interplab.corpus.census import (
    build_payload,
    census_language_row,
    is_byte_fallback_token,
    term_token_split,
)


class _WordTokenizer:
    """Whitespace tokenizer; `tokenize(term)` splits on spaces, no subword
    merges -- enough to exercise token_split/byte_fallback plumbing without
    pulling in a real HF tokenizer."""

    def tokenize(self, text: str) -> list[str]:
        return text.split()


def test_is_byte_fallback_token():
    assert is_byte_fallback_token("<0x0A>")
    assert is_byte_fallback_token("<0xff>")
    assert not is_byte_fallback_token("poutine")
    assert not is_byte_fallback_token("<0x1>")


def test_term_token_split():
    assert term_token_split("world cup", _WordTokenizer()) == ["world", "cup"]


def test_no_terms_language_yields_null_counts():
    row = census_language_row(
        census_terms=[], docs=["poutine is great"], tokenizer=_WordTokenizer(),
        total_tokens=100, boundary="word", case_folding=True,
    )
    assert row == {
        "status": "no_terms", "per_term": None,
        "occurrences_total": None, "per_million_tokens": None, "doc_count": None,
    }


def test_measured_language_counts_word_boundary_matches():
    docs = ["I love poutine.", "Poutine and gravy.", "No relation here."]
    row = census_language_row(
        census_terms=[{"term": "poutine", "kind": "canonical", "origin": "concept_id"}],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=1_000_000,
        boundary="word", case_folding=True,
    )
    assert row["status"] == "measured"
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 2
    assert row["per_million_tokens"] == 2.0
    assert row["per_term"] == [
        {"term": "poutine", "occurrences": 2, "token_split": ["poutine"], "byte_fallback": False}
    ]


def test_word_boundary_does_not_match_substring():
    """ED-9: literal matching under the recorded boundary policy -- 'word'
    boundary must not match 'poutine' inside 'poutinerie'."""
    docs = ["The poutinerie downtown is popular."]
    row = census_language_row(
        census_terms=[{"term": "poutine", "kind": "canonical", "origin": "concept_id"}],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=100,
        boundary="word", case_folding=True,
    )
    assert row["occurrences_total"] == 0
    assert row["status"] == "measured"  # a term was recorded and searched; 0 is a real measurement


def test_substring_boundary_matches_within_words():
    docs = ["The poutinerie downtown is popular."]
    row = census_language_row(
        census_terms=[{"term": "poutine", "kind": "canonical", "origin": "concept_id"}],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=100,
        boundary="substring", case_folding=True,
    )
    assert row["occurrences_total"] == 1


def test_case_folding_false_is_case_sensitive():
    docs = ["Poutine", "poutine"]
    row = census_language_row(
        census_terms=[{"term": "poutine", "kind": "canonical", "origin": "concept_id"}],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=100,
        boundary="word", case_folding=False,
    )
    assert row["occurrences_total"] == 1


def test_multiple_terms_per_language_sum_into_totals():
    docs = ["cheese curds", "gouda wedge", "unrelated text"]
    row = census_language_row(
        census_terms=[
            {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
            {"term": "gouda", "kind": "variant", "origin": "researcher:jdoe"},
        ],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=100,
        boundary="word", case_folding=True,
    )
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 2
    assert [t["term"] for t in row["per_term"]] == ["cheese", "gouda"]


def test_doc_count_does_not_double_count_a_doc_matching_multiple_terms():
    docs = ["cheese and gouda in one doc"]
    row = census_language_row(
        census_terms=[
            {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
            {"term": "gouda", "kind": "variant", "origin": "researcher:jdoe"},
        ],
        docs=docs, tokenizer=_WordTokenizer(), total_tokens=100,
        boundary="word", case_folding=True,
    )
    assert row["occurrences_total"] == 2
    assert row["doc_count"] == 1


def test_byte_fallback_true_when_any_split_token_is_byte_fallback():
    class _ByteFallbackTokenizer:
        def tokenize(self, text: str) -> list[str]:
            return ["<0x0A>", "poutine"]

    row = census_language_row(
        census_terms=[{"term": "poutine", "kind": "canonical", "origin": "concept_id"}],
        docs=["poutine"], tokenizer=_ByteFallbackTokenizer(), total_tokens=100,
        boundary="word", case_folding=True,
    )
    assert row["per_term"][0]["byte_fallback"] is True


def test_build_payload_emits_a_row_for_every_probe_language():
    battery = {
        "poutine": {
            "languages": {
                "en": {"census_terms": [{"term": "poutine", "kind": "canonical", "origin": "concept_id"}]},
                "fr": {"census_terms": []},
            }
        }
    }
    payload = build_payload(
        battery=battery, docs=["poutine here"], tokenizer=_WordTokenizer(), total_tokens=100,
        matcher="regex", case_folding=True, boundary="word",
    )
    assert payload["method"] == {"matcher": "regex", "case_folding": True, "boundary": "word"}
    assert payload["concepts"]["poutine"]["en"]["status"] == "measured"
    assert payload["concepts"]["poutine"]["fr"]["status"] == "no_terms"
