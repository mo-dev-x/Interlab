"""interplab.corpus.battery: loads/validates data/concepts/*.yaml (A2)."""

from pathlib import Path

import pytest
import yaml

from interplab.core._schema_registry import SchemaValidationError
from interplab.corpus.battery import battery_hash, battery_version, load_battery

REAL_CONCEPTS_DIR = Path(__file__).resolve().parents[1] / "data" / "concepts"


def _write_concept(concepts_dir: Path, concept_id: str, **overrides) -> None:
    payload = {
        "concept_id": concept_id,
        "languages": {
            "en": {
                "status": "complete",
                "probes": [f"probe {i}" for i in range(10)],
                "word_absent": [f"absent {i}" for i in range(5)],
                "concept_absent": [],
                "census_terms": [{"term": concept_id, "kind": "canonical", "origin": "concept_id"}],
            }
        },
        "matched_controls": [],
        "notes": "fixture",
    }
    payload.update(overrides)
    (concepts_dir / f"{concept_id}.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_loads_every_concept_keyed_by_concept_id(tmp_path):
    _write_concept(tmp_path, "cheese")
    _write_concept(tmp_path, "gouda")
    concepts = load_battery(tmp_path)
    assert set(concepts) == {"cheese", "gouda"}


def test_ignores_battery_meta_file(tmp_path):
    _write_concept(tmp_path, "cheese")
    (tmp_path / "battery.yaml").write_text("battery_version: '1.0.0'\n", encoding="utf-8")
    concepts = load_battery(tmp_path)
    assert set(concepts) == {"cheese"}


def test_raises_on_invalid_concept_file(tmp_path):
    _write_concept(tmp_path, "bad", languages={"en": {"probes": ["one"], "word_absent": []}})
    with pytest.raises(SchemaValidationError):
        load_battery(tmp_path)


def test_battery_hash_is_deterministic_and_content_sensitive(tmp_path):
    _write_concept(tmp_path, "cheese")
    h1 = battery_hash(tmp_path)
    h2 = battery_hash(tmp_path)
    assert h1 == h2

    _write_concept(tmp_path, "gouda")
    h3 = battery_hash(tmp_path)
    assert h3 != h1


def test_battery_version_reads_meta_file(tmp_path):
    (tmp_path / "battery.yaml").write_text("battery_version: '1.0.0'\n", encoding="utf-8")
    assert battery_version(tmp_path) == "1.0.0"


def test_real_battery_loads_and_validates():
    """ED-10: battery v1 has no true word-absent content for any language,
    so every language -- including en/zh, which have concept_absent -- is
    probes_only."""
    concepts = load_battery(REAL_CONCEPTS_DIR)
    assert "poutine" in concepts
    for lang in ("en", "fr", "zh", "ar"):
        assert concepts["poutine"]["languages"][lang]["status"] == "probes_only"
        assert concepts["poutine"]["languages"][lang]["word_absent"] == []


def test_real_battery_concept_absent_populated_for_en_and_zh_only():
    """ED-10: GENERAL_TEXT/GENERAL_TEXT_ZH landed in concept_absent, not
    word_absent -- the two negative instruments are never conflated."""
    concepts = load_battery(REAL_CONCEPTS_DIR)
    langs = concepts["poutine"]["languages"]
    assert len(langs["en"]["concept_absent"]) == 20
    assert len(langs["zh"]["concept_absent"]) == 20
    assert langs["fr"]["concept_absent"] == []
    assert langs["ar"]["concept_absent"] == []


def test_real_battery_english_census_terms_derived_from_concept_id():
    """ED-9: battery v1's only mechanical census-term carve-out."""
    concepts = load_battery(REAL_CONCEPTS_DIR)
    en_terms = concepts["world-cup"]["languages"]["en"]["census_terms"]
    assert en_terms == [{"term": "world cup", "kind": "canonical", "origin": "concept_id"}]


def test_real_battery_non_english_census_terms_are_empty():
    """ED-9: non-English census terms must be researcher-authored; battery
    v1 has none, so those languages are census `no_terms`, not guessed."""
    concepts = load_battery(REAL_CONCEPTS_DIR)
    for lang in ("fr", "zh", "ar"):
        assert concepts["poutine"]["languages"][lang]["census_terms"] == []


def test_real_battery_version_is_v1():
    assert battery_version(REAL_CONCEPTS_DIR) == "1.0.0"
