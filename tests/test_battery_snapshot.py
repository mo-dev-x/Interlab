"""§8.2 test_battery_snapshot (hard): tokenization of every battery probe
matches a pinned snapshot for the pinned tokenizer revision.

Golden file is generated once and committed (tests/golden/generate_battery_snapshot.py,
same discipline as §8.1's fixtures / test_delta_golden) -- this test never
regenerates it, only compares live tokenization against the pinned bytes.
"""

import json
from pathlib import Path

from transformers import AutoTokenizer

from interplab.corpus.battery import load_battery

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "battery_snapshot.json"
TINY_MODEL_DIR = Path(__file__).resolve().parent / "fixtures" / "tiny_model"
CONCEPTS_DIR = Path(__file__).resolve().parents[1] / "data" / "concepts"


def _snapshot() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_snapshot_covers_every_concept_and_language_in_the_current_battery():
    snapshot = _snapshot()
    concepts = load_battery(CONCEPTS_DIR)
    assert set(snapshot["concepts"]) == set(concepts)
    for concept_id, concept in concepts.items():
        assert set(snapshot["concepts"][concept_id]) == set(concept["languages"])


def test_live_tokenization_matches_pinned_snapshot():
    snapshot = _snapshot()
    tokenizer = AutoTokenizer.from_pretrained(str(TINY_MODEL_DIR))
    concepts = load_battery(CONCEPTS_DIR)

    for concept_id, concept in concepts.items():
        for lang, entry in concept["languages"].items():
            pinned = snapshot["concepts"][concept_id][lang]

            live_probes = [tokenizer.tokenize(p) for p in entry["probes"]]
            assert live_probes == pinned["probes"], f"{concept_id}/{lang}/probes drifted from the pinned snapshot"

            live_word_absent = [tokenizer.tokenize(w) for w in entry["word_absent"]]
            assert live_word_absent == pinned["word_absent"], (
                f"{concept_id}/{lang}/word_absent drifted from the pinned snapshot"
            )

            live_concept_absent = [tokenizer.tokenize(c) for c in entry["concept_absent"]]
            assert live_concept_absent == pinned["concept_absent"], (
                f"{concept_id}/{lang}/concept_absent drifted from the pinned snapshot"
            )

            live_census_terms = [tokenizer.tokenize(t["term"]) for t in entry["census_terms"]]
            assert live_census_terms == pinned["census_terms"], (
                f"{concept_id}/{lang}/census_terms drifted from the pinned snapshot"
            )


def test_snapshot_records_battery_version():
    assert _snapshot()["battery_version"] == "1.0.0"


def test_snapshot_word_absent_is_empty_everywhere():
    """ED-10: battery v1 has no true word-absent content for any language;
    GENERAL_TEXT-style baselines live in concept_absent instead."""
    snapshot = _snapshot()
    for languages in snapshot["concepts"].values():
        for entry in languages.values():
            assert entry["word_absent"] == []
