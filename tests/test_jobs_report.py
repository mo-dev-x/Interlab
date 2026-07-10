"""§6.1 report job (SS9, GATE G4): claim spec config -> assemble_chain ->
statistics -> render -> A11. `reports/<run_id>/` is git-tracked (ED-17), so
every test cleans up the directories it creates.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope, hashing, uris
from interplab.core._schema_registry import SchemaValidationError
from interplab.jobs import report
from tests.fixtures.synthetic_chains import builder

REPORTS_ROOT = uris.REPO_ROOT / "reports"


@pytest.fixture
def cleanup_report_dirs():
    before = {p.name for p in REPORTS_ROOT.iterdir()} if REPORTS_ROOT.is_dir() else set()
    yield
    if REPORTS_ROOT.is_dir():
        for p in REPORTS_ROOT.iterdir():
            if p.name not in before:
                shutil.rmtree(p, ignore_errors=True)


def _write_config(tmp_path: Path, claim_spec: dict) -> Path:
    cfg_path = tmp_path / "report.yaml"
    cfg_path.write_text(yaml.safe_dump(claim_spec), encoding="utf-8")
    return cfg_path


def test_full_green_chain_certified_end_to_end(tmp_path, cleanup_report_dirs):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    cfg_path = _write_config(tmp_path, claim_spec)

    exit_code = report.run(cfg_path, registry_root=tmp_path, repo_root=tmp_path)
    assert exit_code == 0

    claims = list((tmp_path / "claim_report").glob("*.json"))
    assert len(claims) == 1
    claim = envelope.load(claims[0])
    assert claim["payload"]["stamp"] == "CERTIFIED"
    assert claim["payload"]["statistics"] is not None

    md_ref = claim["payload"]["rendered"]["md_ref"]
    html_ref = claim["payload"]["rendered"]["html_ref"]
    md_path = uris.resolve_local(md_ref["location"])
    html_path = uris.resolve_local(html_ref["location"])
    assert md_path.is_file() and html_path.is_file()
    assert hashing.hash_file(md_path) == md_ref["content_hash"]
    assert hashing.hash_file(html_path) == html_ref["content_hash"]
    assert "CERTIFIED" in md_path.read_text(encoding="utf-8")


def test_missing_link_produces_draft_and_exit_0(tmp_path, cleanup_report_dirs):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_certificate=None)
    builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
        ],
        "eval_compat_version": 1,
    }
    cfg_path = _write_config(tmp_path, claim_spec)

    exit_code = report.run(cfg_path, registry_root=tmp_path, repo_root=tmp_path)
    assert exit_code == 0  # §7.2: DRAFT is not an error

    claims = list((tmp_path / "claim_report").glob("*.json"))
    claim = envelope.load(claims[0])
    assert claim["payload"]["stamp"] == "DRAFT — UNCERTIFIED CHAIN"


def test_multi_anchor_divergence_exits_3(tmp_path, cleanup_report_dirs):
    built_a = builder.build_full_green_chain(tmp_path)
    corpus_b = builder.build_corpus_manifest(tmp_path, name="other")
    store_b = builder.build_store_manifest(tmp_path, corpus_b)
    checkpoint_b = builder.build_sae_checkpoint(tmp_path, store_b)
    index_b = builder.build_characterization_manifest(tmp_path, checkpoint_b)
    feature_cert_b = builder.build_feature_certificate(tmp_path, checkpoint_b, index_b)
    intervention_b = builder.build_intervention_result(tmp_path, checkpoint_b, feature_cert_b)

    claim_spec = builder.full_chain_claim_spec(built_a)
    claim_spec["anchor"]["content_hashes"].append(intervention_b["self_hash"])
    cfg_path = _write_config(tmp_path, claim_spec)

    exit_code = report.run(cfg_path, registry_root=tmp_path, repo_root=tmp_path)
    assert exit_code == 3


def test_missing_eval_compat_map_exits_3(tmp_path, cleanup_report_dirs):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    claim_spec["eval_compat_version"] = 999
    cfg_path = _write_config(tmp_path, claim_spec)

    exit_code = report.run(cfg_path, registry_root=tmp_path, repo_root=tmp_path)
    assert exit_code == 3


def test_writes_a_run_card(tmp_path, cleanup_report_dirs):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    cfg_path = _write_config(tmp_path, claim_spec)

    report.run(cfg_path, registry_root=tmp_path, repo_root=tmp_path)

    cards = [json.loads(p.read_text(encoding="utf-8")) for p in (tmp_path / "run_card").glob("*.json")]
    report_cards = [c for c in cards if c["payload"]["stage"] == "report"]
    assert report_cards
    assert report_cards[-1]["payload"]["exit_code"] == 0


def test_config_schema_validation_failure_raises(tmp_path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(yaml.safe_dump({"question": "?"}), encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        report.run(cfg_path, registry_root=tmp_path / "registry", repo_root=tmp_path)
