"""interplab.corpus.census (SS1, A3) -- literal term matching only (ED-9).

Matches exactly the recorded `census_terms` strings under the recorded
matcher config: no stemming, no fuzzy matching, no automatic morphological
expansion, no translation, no keyword extraction. A language with probes but
no `census_terms` gets `status: "no_terms"` with null counts everywhere --
zero is a measurement (the instrument ran and found nothing), null is the
absence of an instrument.
"""

from __future__ import annotations

import re

_BYTE_FALLBACK_RE = re.compile(r"^<0x[0-9A-Fa-f]{2}>$")


def is_byte_fallback_token(token: str) -> bool:
    """A raw-byte SentencePiece-style fallback token, e.g. `<0x0A>`."""
    return bool(_BYTE_FALLBACK_RE.match(token))


def term_token_split(term: str, tokenizer) -> list[str]:
    return list(tokenizer.tokenize(term))


def _term_pattern(term: str, *, boundary: str, case_folding: bool) -> re.Pattern[str]:
    escaped = re.escape(term)
    pattern = rf"\b{escaped}\b" if boundary == "word" else escaped
    flags = re.IGNORECASE if case_folding else 0
    return re.compile(pattern, flags)


def _term_occurrences(
    docs: list[str], term: str, *, boundary: str, case_folding: bool
) -> tuple[int, set[int]]:
    """Returns (occurrence_count, {indices of docs containing >=1 match})."""
    pattern = _term_pattern(term, boundary=boundary, case_folding=case_folding)
    occurrences = 0
    doc_indices: set[int] = set()
    for i, doc in enumerate(docs):
        n = len(pattern.findall(doc))
        if n:
            occurrences += n
            doc_indices.add(i)
    return occurrences, doc_indices


def census_language_row(
    *,
    census_terms: list[dict],
    docs: list[str],
    tokenizer,
    total_tokens: int,
    boundary: str,
    case_folding: bool,
) -> dict:
    """Builds one A3 per-concept-per-language row.

    `census_terms` empty (ED-9: a language with probes but no
    researcher-authored census terms) -> `status: "no_terms"`, every count
    field `null`. Otherwise -> `status: "measured"`, with a `per_term`
    breakdown plus totals across every term for this language.
    """
    if not census_terms:
        return {
            "status": "no_terms",
            "per_term": None,
            "occurrences_total": None,
            "per_million_tokens": None,
            "doc_count": None,
        }

    per_term = []
    occurrences_total = 0
    doc_indices: set[int] = set()
    for entry in census_terms:
        term = entry["term"]
        occurrences, term_doc_indices = _term_occurrences(
            docs, term, boundary=boundary, case_folding=case_folding
        )
        occurrences_total += occurrences
        doc_indices |= term_doc_indices
        token_split = term_token_split(term, tokenizer)
        per_term.append(
            {
                "term": term,
                "occurrences": occurrences,
                "token_split": token_split,
                "byte_fallback": any(is_byte_fallback_token(t) for t in token_split),
            }
        )

    per_million_tokens = (occurrences_total / total_tokens * 1_000_000) if total_tokens else 0.0
    return {
        "status": "measured",
        "per_term": per_term,
        "occurrences_total": occurrences_total,
        "per_million_tokens": per_million_tokens,
        "doc_count": len(doc_indices),
    }


def build_payload(
    *,
    battery: dict[str, dict],
    docs: list[str],
    tokenizer,
    total_tokens: int,
    matcher: str,
    case_folding: bool,
    boundary: str,
) -> dict:
    """Builds the full A3 payload: every concept x every probe-language in
    the battery gets a row (SS1 invariant: a language with probes is always
    a row, `measured` or `no_terms`, never an omission)."""
    concepts: dict[str, dict] = {}
    for concept_id, concept in battery.items():
        concepts[concept_id] = {
            lang: census_language_row(
                census_terms=lang_entry.get("census_terms", []),
                docs=docs,
                tokenizer=tokenizer,
                total_tokens=total_tokens,
                boundary=boundary,
                case_folding=case_folding,
            )
            for lang, lang_entry in concept["languages"].items()
        }
    return {
        "method": {"matcher": matcher, "case_folding": case_folding, "boundary": boundary},
        "concepts": concepts,
    }
