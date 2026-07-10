"""Seeded generator for tests/golden/battery_snapshot.json (§8.2
test_battery_snapshot: "tokenization of every battery probe matches pinned
snapshot for pinned tokenizer revision").

Same discipline as tests/fixtures/generate.py and
tests/golden/generate_delta_golden.py (ED-1): generated once and committed,
kept for provenance only. Tests MUST NOT call this at runtime.

Usage (from the local uv-managed venv only):
    uv run python tests/golden/generate_battery_snapshot.py
"""

from __future__ import annotations

import json
from pathlib import Path

from transformers import AutoTokenizer

from interplab.corpus.battery import load_battery

GOLDEN_DIR = Path(__file__).resolve().parent
REPO_ROOT = GOLDEN_DIR.parents[1]
TINY_MODEL_DIR = REPO_ROOT / "tests" / "fixtures" / "tiny_model"
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts"
OUTPUT_PATH = GOLDEN_DIR / "battery_snapshot.json"


def main() -> None:
    tokenizer = AutoTokenizer.from_pretrained(str(TINY_MODEL_DIR))
    concepts = load_battery(CONCEPTS_DIR)

    snapshot: dict[str, dict[str, dict[str, list]]] = {}
    for concept_id, concept in sorted(concepts.items()):
        snapshot[concept_id] = {}
        for lang, entry in sorted(concept["languages"].items()):
            snapshot[concept_id][lang] = {
                "probes": [tokenizer.tokenize(p) for p in entry["probes"]],
                "word_absent": [tokenizer.tokenize(w) for w in entry["word_absent"]],
                "concept_absent": [tokenizer.tokenize(c) for c in entry["concept_absent"]],
                "census_terms": [tokenizer.tokenize(t["term"]) for t in entry["census_terms"]],
            }

    payload = {
        "tokenizer_revision": "tests/fixtures/tiny_model (pinned, §8.1)",
        "battery_version": "1.0.0",
        "concepts": snapshot,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
