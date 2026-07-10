"""§6.1 census job (SS1): builds A1 fresh from a docs file + recipe, and A3
against the real ConceptBattery. ED-9: literal matching only."""

import json
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope
from interplab.jobs import census

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PINNED_TEXT = FIXTURES_DIR / "pinned_text.jsonl"
TINY_MODEL_DIR = FIXTURES_DIR / "tiny_model"


def _write_config(tmp_path, **overrides) -> Path:
    config = {
        "name": "pinned-text-fixture",
        "recipe": {
            "dataset": "local:tests/fixtures/pinned_text.jsonl",
            "revision": "v1",
            "split": "all",
            "subset_spec": None,
            "filters": {},
        },
        "docs_location": "local:tests/fixtures/pinned_text.jsonl",
        "tokenizer_location": "local:tests/fixtures/tiny_model",
        "tokenizer_revision": "v1",
        "matcher": "regex",
        "case_folding": True,
        "boundary": "word",
    }
    config.update(overrides)
    cfg_path = tmp_path / "census.yaml"
    cfg_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return cfg_path


def test_full_run_against_real_fixtures_and_battery(tmp_path):
    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path)

    exit_code = census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    census_reports = list((registry_root / "census_report").glob("*.json"))
    assert len(census_reports) == 1
    report = envelope.load(census_reports[0])

    poutine = report["payload"]["concepts"]["poutine"]
    assert poutine["en"]["status"] == "measured"
    # Pinned fixture, deterministic: "poutine" (word boundary, case-folded)
    # appears exactly 37 times across tests/fixtures/pinned_text.jsonl.
    assert poutine["en"]["occurrences_total"] == 37
    assert poutine["en"]["per_term"][0]["term"] == "poutine"
    assert poutine["fr"]["status"] == "no_terms"
    assert poutine["fr"]["per_term"] is None
    assert poutine["fr"]["occurrences_total"] is None

    assert report["payload"]["method"] == {"matcher": "regex", "case_folding": True, "boundary": "word"}

    corpus_manifests = list((registry_root / "corpus_manifest").glob("*.json"))
    assert len(corpus_manifests) == 1
    manifest = envelope.load(corpus_manifests[0])
    assert manifest["payload"]["doc_count"] == 200
    assert manifest["payload"]["token_count"] > 0

    assert report["subject"][0]["role"] == "corpus_manifest"
    assert report["subject"][0]["content_hash"] == manifest["self_hash"]
    assert report["subject"][1]["role"] == "concept_battery"
    assert report["subject"][1]["location"] == "local:data/concepts"


def test_writes_a_run_card(tmp_path):
    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path)
    census.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    cards = list((registry_root / "run_card").glob("*.json"))
    assert len(cards) == 1
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    assert card["payload"]["stage"] == "census"
    assert card["payload"]["status"] == "completed"
    assert card["payload"]["exit_code"] == 0


def test_empty_docs_file_is_contract_violation(tmp_path):
    # local: URIs always resolve against the real repo root (never tmp_path),
    # so an empty docs fixture has to live under the real tests/fixtures/.
    empty_fixture = FIXTURES_DIR / "empty_docs_for_test.jsonl"
    empty_fixture.write_text("", encoding="utf-8")
    try:
        cfg = _write_config(tmp_path, docs_location="local:tests/fixtures/empty_docs_for_test.jsonl")
        exit_code = census.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
        assert exit_code == 3
    finally:
        empty_fixture.unlink(missing_ok=True)


def test_non_local_docs_location_is_not_implemented(tmp_path):
    cfg = _write_config(tmp_path, docs_location="hf:some/dataset@main")
    exit_code = census.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 4  # NotImplementedError falls through the generic catch-all (§6.2)


def test_config_schema_validation_failure_raises():
    with pytest.raises(FileNotFoundError):
        census.run("nonexistent_config.yaml", registry_root=Path("unused"))
