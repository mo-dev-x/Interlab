"""interplab.corpus.census (SS1, A3) -- literal term matching only (ED-9).

Matches exactly the recorded `census_terms` strings under the recorded
matcher config: no stemming, no fuzzy matching, no automatic morphological
expansion, no translation, no keyword extraction. A language with probes but
no `census_terms` gets `status: "no_terms"` with null counts everywhere --
zero is a measurement (the instrument ran and found nothing), null is the
absence of an instrument.

ED-28: `scan_stream` is the single pass over the corpus stream -- every
concept x language x term is checked against each document as it streams
by, since the stream may be a one-shot iterable (an `hf:` dataset in
streaming mode) that cannot be re-consumed once per term the way a
materialized `docs: list[str]` could. `build_payload` also carries
`method.coverage`/`method.sampling`: `"full"` when the pass covers the
whole corpus stream A1 defines, `"sampled"` when `census_take_docs` stops
term-accumulation early (the stream itself keeps flowing past that point
so the caller's token/doc counts -- A1's manifest fields -- still reflect
the whole corpus). Affected rows get `status: "estimated"` rather than
`"measured"`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

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


def _assemble_row(
    *,
    census_terms: list[dict],
    term_occurrences: list[int],
    doc_count: int,
    total_tokens: int,
    tokenizer,
    estimated: bool,
) -> dict:
    """Builds one A3 per-concept-per-language row from precomputed counts
    (`term_occurrences` parallel to `census_terms`, `doc_count` = distinct
    docs matching >=1 term) -- ED-28: counts come from a single streaming
    pass over every concept/language/term at once; this function only
    formats them."""
    if not census_terms:
        return {
            "status": "no_terms", "per_term": None,
            "occurrences_total": None, "per_million_tokens": None, "doc_count": None,
        }

    occurrences_total = sum(term_occurrences)
    per_term = []
    for entry, occurrences in zip(census_terms, term_occurrences, strict=True):
        token_split = term_token_split(entry["term"], tokenizer)
        per_term.append(
            {
                "term": entry["term"],
                "occurrences": occurrences,
                "token_split": token_split,
                "byte_fallback": any(is_byte_fallback_token(t) for t in token_split),
            }
        )

    per_million_tokens = (occurrences_total / total_tokens * 1_000_000) if total_tokens else 0.0
    return {
        "status": "estimated" if estimated else "measured",
        "per_term": per_term,
        "occurrences_total": occurrences_total,
        "per_million_tokens": per_million_tokens,
        "doc_count": doc_count,
    }


def scan_stream(
    docs: Iterable[str],
    *,
    battery: dict[str, dict],
    tokenizer,
    boundary: str,
    case_folding: bool,
    census_take_docs: int | None = None,
    sample_size: int = 1000,
) -> dict:
    """Single pass over `docs` (ED-28). Returns a dict with:

    - `layout`: `[(concept_id, lang, census_terms), ...]` -- the fixed,
      ordered flattening of `battery` this scan checked.
    - `occurrences`: `{(concept_id, lang, term_index): int}`.
    - `matched_docs`: `{(concept_id, lang): int}` -- distinct docs matching
      >=1 term of that language.
    - `total_tokens`, `total_docs`: over the WHOLE input iterable.
    - `realized_tokens`, `realized_docs`: over the portion actually
      scanned for term matches (equals total_tokens/total_docs unless
      `census_take_docs` cut term-accumulation short).
    - `sample_docs`: the first `sample_size` documents, in stream order.

    `census_take_docs`, if given, stops ACCUMULATING term matches after
    that many documents (ED-28 `coverage: "sampled"`) but the stream keeps
    flowing past that point so `total_tokens`/`total_docs` still cover the
    whole corpus -- A1's manifest needs the full stream's statistics
    regardless of how much of it the census itself scanned.
    """
    layout: list[tuple[str, str, list[dict]]] = [
        (concept_id, lang, lang_entry.get("census_terms", []))
        for concept_id, concept in battery.items()
        for lang, lang_entry in concept["languages"].items()
    ]
    patterns: dict[tuple[str, str, int], re.Pattern[str]] = {
        (concept_id, lang, i): _term_pattern(entry["term"], boundary=boundary, case_folding=case_folding)
        for concept_id, lang, term_entries in layout
        for i, entry in enumerate(term_entries)
    }
    occurrences: dict[tuple[str, str, int], int] = dict.fromkeys(patterns, 0)
    matched_docs: dict[tuple[str, str], int] = {(concept_id, lang): 0 for concept_id, lang, _ in layout}

    total_tokens = 0
    total_docs = 0
    realized_tokens = 0
    realized_docs = 0
    sample_docs: list[str] = []

    for doc in docs:
        doc_tokens = len(tokenizer(doc)["input_ids"])
        total_tokens += doc_tokens
        total_docs += 1
        if len(sample_docs) < sample_size:
            sample_docs.append(doc)

        if census_take_docs is None or realized_docs < census_take_docs:
            realized_docs += 1
            realized_tokens += doc_tokens
            for concept_id, lang, term_entries in layout:
                matched = False
                for i in range(len(term_entries)):
                    n = len(patterns[(concept_id, lang, i)].findall(doc))
                    if n:
                        occurrences[(concept_id, lang, i)] += n
                        matched = True
                if matched:
                    matched_docs[(concept_id, lang)] += 1

    return {
        "layout": layout,
        "occurrences": occurrences,
        "matched_docs": matched_docs,
        "total_tokens": total_tokens,
        "total_docs": total_docs,
        "realized_tokens": realized_tokens,
        "realized_docs": realized_docs,
        "sample_docs": sample_docs,
    }


def build_payload(
    *,
    battery: dict[str, dict],
    docs: Iterable[str],
    tokenizer,
    matcher: str,
    case_folding: bool,
    boundary: str,
    census_take_docs: int | None = None,
    sampling_rule: str | None = None,
    sampling_seed: int | None = None,
) -> tuple[dict, dict]:
    """Builds the full A3 payload: every concept x every probe-language in
    the battery gets a row (SS1 invariant: a language with probes is
    always a row, `measured`/`estimated`/`no_terms`, never an omission).

    Returns `(census_payload, stream_stats)` -- `stream_stats` carries
    `total_tokens`/`total_docs`/`sample_docs`, the by-products of the same
    single pass A1's manifest also needs (ED-28: census and manifest are
    built from ONE scan of the stream, never two).

    `census_take_docs`/`sampling_rule`/`sampling_seed` together implement
    ED-28's `coverage: "sampled"` case: A1 still defines the full consumed
    stream (reflected in `stream_stats`), but this census only scanned a
    prefix of it for term matches. `sampling_rule`/`sampling_seed` are
    recorded verbatim in `method.sampling`, not interpreted here.
    """
    scan = scan_stream(
        docs, battery=battery, tokenizer=tokenizer, boundary=boundary,
        case_folding=case_folding, census_take_docs=census_take_docs,
    )
    sampled = census_take_docs is not None
    method = {
        "matcher": matcher, "case_folding": case_folding, "boundary": boundary,
        "coverage": "sampled" if sampled else "full",
    }
    if sampled:
        method["sampling"] = {
            "rule": sampling_rule,
            "seed": sampling_seed,
            "realized_docs": scan["realized_docs"],
            "realized_tokens": scan["realized_tokens"],
        }

    row_total_tokens = scan["realized_tokens"] if sampled else scan["total_tokens"]
    concepts: dict[str, dict] = {}
    for concept_id, lang, term_entries in scan["layout"]:
        row = _assemble_row(
            census_terms=term_entries,
            term_occurrences=[scan["occurrences"][(concept_id, lang, i)] for i in range(len(term_entries))],
            doc_count=scan["matched_docs"][(concept_id, lang)],
            total_tokens=row_total_tokens,
            tokenizer=tokenizer,
            estimated=sampled,
        )
        concepts.setdefault(concept_id, {})[lang] = row

    census_payload = {"method": method, "concepts": concepts}
    stream_stats = {
        "total_tokens": scan["total_tokens"],
        "total_docs": scan["total_docs"],
        "sample_docs": scan["sample_docs"],
    }
    return census_payload, stream_stats
