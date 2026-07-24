"""§6.1 census job (SS1): builds A1 fresh from a document stream + recipe,
and A3 against the real ConceptBattery. ED-9: literal matching only.
ED-28: streaming replay (local: or hf:), single-pass scan, sampled
coverage. ED-31: n_training_samples is an advisory structural cross-check
against SAELens' packing, never an exact-match identity gate.
"""

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

    assert report["payload"]["method"] == {
        "matcher": "regex", "case_folding": True, "boundary": "word", "coverage": "full",
    }

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


def test_unsupported_docs_location_scheme_is_not_implemented(tmp_path):
    cfg = _write_config(tmp_path, docs_location="tamia:some/path")
    exit_code = census.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 4  # NotImplementedError falls through the generic catch-all (§6.2)


def test_hf_docs_location_streams_via_datasets(tmp_path, monkeypatch):
    """ED-28: hf: dataset URIs are now supported. The real network call is
    never exercised in the hard suite; `datasets.load_dataset` is
    monkeypatched to a small fixed corpus."""
    def fake_load_dataset(dataset, revision=None, split=None, streaming=None):
        assert dataset == "some/dataset"
        assert revision == "main"
        assert streaming is True
        return [{"text": "poutine and gravy"}, {"text": "unrelated text"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)

    cfg = _write_config(
        tmp_path,
        docs_location="hf:some/dataset@main",
        recipe={
            "dataset": "some/dataset", "revision": "main", "split": "train",
            "subset_spec": None, "filters": {},
        },
    )
    exit_code = census.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 0

    manifest = envelope.load(next((tmp_path / "registry" / "corpus_manifest").glob("*.json")))
    assert manifest["payload"]["doc_count"] == 2

    report = envelope.load(next((tmp_path / "registry" / "census_report").glob("*.json")))
    assert report["payload"]["concepts"]["poutine"]["en"]["occurrences_total"] == 1


def _run_once_for_real_counts(tmp_path):
    """tiny_model's tokenizer is real; runs once unchecked to discover the
    real document-stream doc_count/token_count for the pinned fixture,
    matching how a researcher would first observe the replay before
    supplying a WandB-recorded n_training_samples for a real backfill."""
    registry_root = tmp_path / "registry_baseline"
    cfg = _write_config(tmp_path)
    census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    manifest = envelope.load(next((registry_root / "corpus_manifest").glob("*.json")))
    return manifest["payload"]["doc_count"], manifest["payload"]["token_count"]


def test_replay_self_check_accepts_exact_document_stream_token_count(tmp_path):
    """ED-31: the document-stream token_count itself (no BOS/packing
    adjustment at all) is well within the structural band -- the
    relaxation is strictly permissive relative to the old exact-match
    gate, never stricter."""
    _doc_count, real_token_count = _run_once_for_real_counts(tmp_path)

    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, n_training_samples=real_token_count)
    exit_code = census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0


def test_replay_self_check_accepts_expected_packing_delta(tmp_path):
    """ED-31: n_training_samples reflecting SAELens' packing (one BOS per
    document, i.e. token_count + doc_count) is exactly the case the old
    ED-28 exact-equality gate would have wrongly rejected -- proving the
    relaxation actually does something, not just that exact matches still
    pass."""
    from interplab.corpus import replay

    doc_count, real_token_count = _run_once_for_real_counts(tmp_path)
    packed_estimate = real_token_count + doc_count
    assert packed_estimate != real_token_count  # sanity: fixture actually has documents

    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, n_training_samples=packed_estimate)
    exit_code = census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    low, high = replay.expected_packed_token_range(real_token_count, doc_count)
    assert low <= packed_estimate <= high


def test_replay_self_check_rejects_delta_beyond_packing_slack(tmp_path):
    """ED-31: the structural band is bounded, not unlimited -- a delta
    just past PACKING_WINDOW_SLACK_TOKENS is still a hard failure, proving
    this is a real (generous) band and not an accidentally-disabled check."""
    from interplab.corpus import replay

    doc_count, real_token_count = _run_once_for_real_counts(tmp_path)
    _, high = replay.expected_packed_token_range(real_token_count, doc_count)

    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, n_training_samples=high + 1)
    exit_code = census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3
    assert not list((registry_root / "corpus_manifest").glob("*.json"))
    assert not list((registry_root / "census_report").glob("*.json"))


def test_replay_self_check_fails_loudly_on_gross_mismatch(tmp_path):
    cfg = _write_config(tmp_path, n_training_samples=999_999_999)
    exit_code = census.run(cfg, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert exit_code == 3
    # Nothing gets written on a self-check failure.
    assert not list((tmp_path / "registry" / "corpus_manifest").glob("*.json"))
    assert not list((tmp_path / "registry" / "census_report").glob("*.json"))


def test_census_sample_docs_produces_sampled_coverage(tmp_path):
    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, census_sample_docs=10)
    exit_code = census.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    report = envelope.load(next((registry_root / "census_report").glob("*.json")))
    assert report["payload"]["method"]["coverage"] == "sampled"
    assert report["payload"]["method"]["sampling"]["realized_docs"] == 10
    poutine_en = report["payload"]["concepts"]["poutine"]["en"]
    assert poutine_en["status"] == "estimated"

    # A1's manifest is unaffected -- still reflects the whole 200-doc stream.
    manifest = envelope.load(next((registry_root / "corpus_manifest").glob("*.json")))
    assert manifest["payload"]["doc_count"] == 200


def test_config_schema_validation_failure_raises():
    with pytest.raises(FileNotFoundError):
        census.run("nonexistent_config.yaml", registry_root=Path("unused"))
