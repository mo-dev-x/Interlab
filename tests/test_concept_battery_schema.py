"""A2 concept_battery source-file schema (schemas/concept_battery/v1.schema.json):
validates one data/concepts/<concept_id>.yaml file. Not an envelope type --
its identity is a directory content hash over data/concepts/ (§2.2), so
there is no envelope.dump path to exercise here.

ED-8: per-language `status` ("complete" | "probes_only") distinguishes
languages with researcher-authored negative controls (>=5 word_absent,
usable for SS6 sensitivity) from languages with probes only (word_absent
may be short or empty, descriptive use only -- existing probes are never
discarded for lacking a matching negative control).

ED-9: per-language `census_terms` are researcher-authored (except English,
which MAY be mechanically derived from concept_id, origin: "concept_id").
Empty is valid -- census_terms presence is orthogonal to `status`.

ED-10: two negative instruments, never conflated. `word_absent` is
concept-present, term-absent contexts -- the sensitivity instrument that
alone governs `status`. `concept_absent` is unrelated baseline text -- the
specificity-denominator instrument, orthogonal to `status` (like
`census_terms`). Populating `concept_absent` never promotes a language to
`complete`; only `word_absent` does.
"""

import pytest

from interplab.core._schema_registry import SCHEMAS_ROOT, SchemaValidationError, validate

SCHEMA_PATH = SCHEMAS_ROOT / "concept_battery" / "v1.schema.json"


def _lang(*, status="complete", n_probes=10, n_absent=5, n_concept_absent=0, census_terms=None) -> dict:
    return {
        "status": status,
        "probes": [f"probe sentence {i}" for i in range(n_probes)],
        "word_absent": [f"absent sentence {i}" for i in range(n_absent)],
        "concept_absent": [f"unrelated sentence {i}" for i in range(n_concept_absent)],
        "census_terms": census_terms if census_terms is not None else [],
    }


def _valid_concept(**overrides) -> dict:
    concept = {
        "concept_id": "cheese",
        "languages": {"en": _lang()},
        "matched_controls": ["poutine"],
        "notes": "test fixture",
    }
    concept.update(overrides)
    return concept


def test_accepts_minimal_valid_concept():
    validate(_valid_concept(), SCHEMA_PATH)


def test_accepts_multiple_languages():
    concept = _valid_concept(languages={"en": _lang(), "fr": _lang()})
    validate(concept, SCHEMA_PATH)


def test_accepts_probes_only_language_with_zero_word_absent():
    """ED-8: a language with probes but no researcher-authored negative
    controls yet is `probes_only`, not dropped and not rejected."""
    concept = _valid_concept(languages={"fr": _lang(status="probes_only", n_absent=0)})
    validate(concept, SCHEMA_PATH)


def test_accepts_probes_only_language_with_sub_minimum_word_absent():
    """ED-8: sub-minimum word_absent entries found in source are preserved
    (losslessness) -- they just don't promote the language to `complete`."""
    concept = _valid_concept(languages={"fr": _lang(status="probes_only", n_absent=2)})
    validate(concept, SCHEMA_PATH)


def test_rejects_too_few_probes():
    concept = _valid_concept(languages={"en": _lang(n_probes=1)})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_too_few_probes_even_when_probes_only():
    """ED-8: the >=10 probes minimum applies regardless of status."""
    concept = _valid_concept(languages={"fr": _lang(status="probes_only", n_probes=1, n_absent=0)})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_too_few_word_absent_when_complete():
    concept = _valid_concept(languages={"en": _lang(n_absent=1)})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_missing_status_field():
    lang = _lang()
    del lang["status"]
    concept = _valid_concept(languages={"en": lang})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_unknown_status_value():
    concept = _valid_concept(languages={"en": _lang(status="verified")})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_unknown_language_code():
    concept = _valid_concept(languages={"de": _lang()})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_bad_concept_id_casing():
    concept = _valid_concept(concept_id="Cheese_Feature")
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_missing_notes_field():
    concept = _valid_concept()
    del concept["notes"]
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


# -- ED-9: census_terms -----------------------------------------------------


def test_rejects_missing_census_terms_field():
    lang = _lang()
    del lang["census_terms"]
    concept = _valid_concept(languages={"en": lang})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_accepts_empty_census_terms():
    """ED-9: census_terms presence is orthogonal to status -- a `complete`
    language may still have zero census terms (measured for sensitivity,
    `no_terms` for census)."""
    concept = _valid_concept(languages={"en": _lang(census_terms=[])})
    validate(concept, SCHEMA_PATH)


def test_accepts_concept_id_derived_english_term():
    concept = _valid_concept(
        languages={"en": _lang(census_terms=[{"term": "cheese", "kind": "canonical", "origin": "concept_id"}])}
    )
    validate(concept, SCHEMA_PATH)


def test_accepts_multiple_terms_per_language():
    concept = _valid_concept(
        languages={
            "en": _lang(
                census_terms=[
                    {"term": "cheese", "kind": "canonical", "origin": "concept_id"},
                    {"term": "cheeses", "kind": "inflection", "origin": "researcher:jdoe"},
                ]
            )
        }
    )
    validate(concept, SCHEMA_PATH)


@pytest.mark.parametrize("kind", ["canonical", "variant", "inflection", "transliteration"])
def test_accepts_every_census_term_kind(kind):
    concept = _valid_concept(
        languages={"en": _lang(census_terms=[{"term": "cheese", "kind": kind, "origin": "researcher:jdoe"}])}
    )
    validate(concept, SCHEMA_PATH)


def test_rejects_unknown_census_term_kind():
    concept = _valid_concept(
        languages={"en": _lang(census_terms=[{"term": "cheese", "kind": "synonym", "origin": "researcher:jdoe"}])}
    )
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_census_term_missing_origin():
    concept = _valid_concept(
        languages={"en": _lang(census_terms=[{"term": "cheese", "kind": "canonical"}])}
    )
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_rejects_census_term_empty_string():
    concept = _valid_concept(
        languages={"en": _lang(census_terms=[{"term": "", "kind": "canonical", "origin": "concept_id"}])}
    )
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


# -- ED-10: two negative instruments, never conflated ------------------------


def test_rejects_missing_concept_absent_field():
    lang = _lang()
    del lang["concept_absent"]
    concept = _valid_concept(languages={"en": lang})
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_accepts_empty_concept_absent():
    concept = _valid_concept(languages={"en": _lang(n_concept_absent=0)})
    validate(concept, SCHEMA_PATH)


def test_accepts_populated_concept_absent():
    concept = _valid_concept(languages={"en": _lang(n_concept_absent=20)})
    validate(concept, SCHEMA_PATH)


def test_populated_concept_absent_does_not_satisfy_the_complete_word_absent_minimum():
    """ED-10: concept_absent is a different instrument from word_absent --
    a language with 20 concept_absent entries but zero word_absent entries
    is still rejected as `complete` (status must honestly reflect
    word_absent, the sensitivity instrument, not concept_absent)."""
    concept = _valid_concept(
        languages={"en": _lang(status="complete", n_absent=0, n_concept_absent=20)}
    )
    with pytest.raises(SchemaValidationError):
        validate(concept, SCHEMA_PATH)


def test_probes_only_with_zero_word_absent_and_populated_concept_absent_is_valid():
    """The battery v1 shape exactly: every language has concept_absent but
    no word_absent, so every language is probes_only."""
    concept = _valid_concept(
        languages={"en": _lang(status="probes_only", n_absent=0, n_concept_absent=20)}
    )
    validate(concept, SCHEMA_PATH)
