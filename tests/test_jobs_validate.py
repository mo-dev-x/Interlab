"""§6.1 validate job (SS6, GATE G2): specificity/sensitivity/cross_lingual_firing
/selectivity/probe against a real (fixture) checkpoint + characterization
index + synthetic complete battery, applies bands, emits A8.

The checkpoint + characterization index (256-feature indexing + dashboard
rendering) are built ONCE per test session (session-scoped fixture) and
reused read-only across every test below -- content-addressed registry
artifacts are immutable, so sharing is safe, and rebuilding per-test would
otherwise dominate this file's runtime well past §8.3's <5min hard-test
budget.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope, environment_bundle, hashing, uris
from interplab.jobs import characterize, validate
from interplab.registry.registry import put as registry_put
from tests.job_test_helpers import (
    TEST_REPO_REVISION,
    assert_failed_environment_run_card,
    assert_failed_invalid_config_run_card,
    assert_only_run_card_written,
    patch_alliance_torch_runtime,
    write_cert_lane_environment_files,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _created_by():
    return {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


def _register_checkpoint(registry_root: Path) -> str:
    weights_hash = hashing.hash_checkpoint_dir(FIXTURES_DIR / "tiny_sae")
    model_hash = hashing.hash_directory(FIXTURES_DIR / "tiny_model")
    checkpoint = envelope.dump(
        artifact_type="sae_checkpoint", schema_version=1, created_by=_created_by(),
        subject=[
            {"content_hash": weights_hash, "location": "local:tests/fixtures/tiny_sae", "role": "weights"},
            {"content_hash": model_hash, "location": "local:tests/fixtures/tiny_model", "role": "model"},
        ],
        payload={
            "config": {}, "store_hash": None, "seed": 0, "tokens_trained": 1000, "wandb": None,
            "telemetry_tail": {"fvu": 0.1, "fvu_source": "training_eval", "dead_count": 0},
            "training_provenance": {
                "sae_lens": None, "transformers": None, "transformer_lens": None,
                "source": "unknown", "confidence": "unknown",
            },
            "cfg_schema_generation": None,
        },
    )
    return registry_put(checkpoint, registry_root=registry_root)


def _register_corpus_manifest(registry_root: Path) -> str:
    manifest = envelope.dump(
        artifact_type="corpus_manifest", schema_version=1, created_by=_created_by(), subject=[],
        payload={
            "name": "pinned-text", "recipe": {"dataset": "unknown", "revision": "unknown", "split": "unknown", "subset_spec": None, "filters": {}},
            "token_count": 1000, "doc_count": 200, "dedup_rate": None,
            "tokenizer": {"name": "tiny-tokenizer", "revision": "main"}, "sample_checksum": "sha256:" + "9" * 64,
        },
    )
    return registry_put(manifest, registry_root=registry_root)


def _register_census(registry_root: Path) -> str:
    census = envelope.dump(
        artifact_type="census_report", schema_version=1, created_by=_created_by(),
        subject=[{"content_hash": "sha256:" + "a" * 64, "location": "local:registry/corpus_manifest/abc.json", "role": "corpus_manifest"}],
        payload={"method": {"matcher": "regex", "case_folding": True, "boundary": "word", "coverage": "full"}, "concepts": {}},
    )
    return registry_put(census, registry_root=registry_root)


def _build_characterization_manifest(registry_root: Path, tmp_path: Path, index_dir: Path, checkpoint_hash: str) -> str:
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = {
        "checkpoint_hash": checkpoint_hash,
        "corpus_manifest_hash": corpus_manifest_hash,
        "corpus_location": "local:tests/fixtures/pinned_text.jsonl",
        "n_docs": 20,
        "judge": "none",
        "rng_seed": 0,
        "index_dir": str(index_dir),
    }
    cfg_path = tmp_path / "characterize.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    exit_code = characterize.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0
    manifest_path = next((registry_root / "characterization_manifest").glob("*.json"))
    return json.loads(manifest_path.read_text(encoding="utf-8"))["self_hash"]


@pytest.fixture(scope="module")
def shared_registry(tmp_path_factory):
    """Built once for this module: a checkpoint, a census_report, and a
    real characterization index+manifest -- everything downstream is
    read-only against this registry."""
    registry_root = tmp_path_factory.mktemp("validate_shared_registry")
    index_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "jobs_validate_shared"
    if index_dir.exists():
        shutil.rmtree(index_dir)

    checkpoint_hash = _register_checkpoint(registry_root)
    census_hash = _register_census(registry_root)
    manifest_hash = _build_characterization_manifest(
        registry_root, tmp_path_factory.mktemp("validate_characterize_cfg"), index_dir, checkpoint_hash
    )

    yield {
        "registry_root": registry_root,
        "checkpoint_hash": checkpoint_hash,
        "census_hash": census_hash,
        "manifest_hash": manifest_hash,
    }

    shutil.rmtree(index_dir, ignore_errors=True)


def _write_validate_config(tmp_path: Path, **overrides) -> Path:
    cfg = {
        "concepts_location": "local:tests/fixtures/synthetic_concepts",
        "concept_id": "zorbium",
        "feature_index": 0,
        "specificity_judge": "stub",
        "stub_judge_marker_words": ["zorbium"],
        "selectivity_top_n": 3,
        "probe_seed": 0,
    }
    cfg.update(overrides)
    cfg_path = tmp_path / "validate.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return cfg_path


def test_full_run_against_synthetic_complete_battery(tmp_path, shared_registry):
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"],
    )
    exit_code = validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code in (0, 2)  # green/amber -> 0, red -> 2 (gate_failed, not a failure)

    certs = list((shared_registry["registry_root"] / "feature_certificate").glob("*.json"))
    assert len(certs) == 1
    cert = envelope.load(certs[0])

    assert cert["payload"]["concept_id"] == "zorbium"
    assert cert["payload"]["sensitivity"]["status"] == "measured"
    assert cert["payload"]["cross_lingual_firing"] is not None
    assert "fr" in cert["payload"]["cross_lingual_firing"]
    assert {ref["role"] for ref in cert["subject"]} == {
        "sae_checkpoint", "characterization_manifest", "concept_battery", "census_report",
    }
    assert isinstance(cert["payload"]["verdict_basis"], list)
    assert "sensitivity" in cert["payload"]["verdict_basis"]


def test_writes_a_run_card(tmp_path, shared_registry):
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"],
    )
    validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)

    cards = list((shared_registry["registry_root"] / "run_card").glob("*.json"))
    validate_cards = [json.loads(c.read_text(encoding="utf-8")) for c in cards]
    validate_cards = [c for c in validate_cards if c["payload"]["stage"] == "validate"]
    assert validate_cards, "expected at least one validate-stage run card"
    assert validate_cards[-1]["payload"]["exit_code"] in (0, 2)


def test_environment_records_the_real_sae_stack_versions(tmp_path, shared_registry):
    from importlib.metadata import version as pkg_version

    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"],
    )
    validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)

    cards = [json.loads(c.read_text(encoding="utf-8")) for c in (shared_registry["registry_root"] / "run_card").glob("*.json")]
    validate_cards = [c for c in cards if c["payload"]["stage"] == "validate"]
    env = validate_cards[-1]["payload"]["environment"]
    assert env["sae_lens"] == pkg_version("sae-lens")
    assert env["transformers"] == pkg_version("transformers")
    assert env["transformer_lens"] == pkg_version("transformer-lens")


def test_refuses_to_run_on_sae_lens_baseline_mismatch(tmp_path, monkeypatch):
    """ED-32 fail-closed: refuses before any registry/model access -- exit
    4, no feature_certificate written, run card records the offending
    version. Uses a fresh registry, not `shared_registry`, since the
    refusal happens before any lookup and shouldn't touch the shared
    module-scoped fixture."""
    import interplab.core.environment as environment_module

    monkeypatch.setattr(
        environment_module, "resolve_sae_stack_versions",
        lambda: {"sae_lens": "3.23.0", "transformers": "4.44.0", "transformer_lens": "2.15.4"},
    )

    registry_root = tmp_path / "registry"
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash="sha256:" + "a" * 64,
        census_report_hash="sha256:" + "b" * 64,
    )
    exit_code = validate.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert not list((registry_root / "feature_certificate").glob("*.json"))

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "failed"
    assert card["payload"]["exit_code"] == 4
    assert "environment baseline violated" in card["payload"]["outcome_line"]
    assert card["payload"]["environment"]["sae_lens"] == "3.23.0"


def test_cluster_environment_inputs_are_recorded_when_manifest_paths_are_present(tmp_path, shared_registry, monkeypatch):
    cfg = _write_validate_config(
        tmp_path,
        characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"],
    )
    scratch_dir, acquisition, install = write_cert_lane_environment_files("jobs_validate_env_inputs")

    try:
        monkeypatch.setattr(environment_bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
        patch_alliance_torch_runtime(monkeypatch)
        monkeypatch.setenv("INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH", str(acquisition))
        monkeypatch.setenv("INTERPLAB_ENV_INSTALL_MANIFEST_PATH", str(install))

        validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)

        cards = [
            json.loads(c.read_text(encoding="utf-8"))
            for c in (shared_registry["registry_root"] / "run_card").glob("*.json")
        ]
        candidate_roles = [
            {entry["role"] for entry in c["payload"]["inputs"]}
            for c in cards
            if c["payload"]["stage"] == "validate"
            and c["payload"]["config_hash"] == hashing.hash_file(cfg)
        ]
        assert any(
            {
                "characterization_manifest",
                "census_report",
                "cluster_requirements",
                "environment_acquisition_manifest",
                "environment_install_manifest",
            } <= roles
            for roles in candidate_roles
        )
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


def test_no_complete_language_and_no_concept_absent_is_contract_violation(tmp_path, shared_registry):
    """quixnorf has zero concept_absent anywhere -- the probe comparator
    has no language-matched negative class, which is a genuine contract
    violation (unlike sensitivity, `probe` is not status-bearing per A8)."""
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"], concept_id="quixnorf",
    )
    exit_code = validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_missing_characterization_manifest_is_contract_violation(tmp_path):
    registry_root = tmp_path / "registry"
    census_hash = _register_census(registry_root)
    fake_hash = "sha256:" + "a" * 64
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=fake_hash, census_report_hash=census_hash,
    )
    exit_code = validate.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_missing_census_report_is_contract_violation(tmp_path, shared_registry):
    fake_census = "sha256:" + "b" * 64
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=fake_census,
    )
    exit_code = validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_missing_concept_file_is_contract_violation(tmp_path, shared_registry):
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"], concept_id="does-not-exist",
    )
    exit_code = validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_out_of_range_feature_index_is_contract_violation(tmp_path, shared_registry):
    cfg = _write_validate_config(
        tmp_path, characterization_manifest_hash=shared_registry["manifest_hash"],
        census_report_hash=shared_registry["census_hash"], feature_index=999999,
    )
    exit_code = validate.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_config_schema_validation_failure_writes_failed_run_card(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_CLUSTER", "1")
    monkeypatch.delenv("INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("INTERPLAB_ENV_INSTALL_MANIFEST_PATH", raising=False)
    registry_root = tmp_path / "registry"
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(yaml.safe_dump({"feature_index": 0}), encoding="utf-8")

    exit_code = validate.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 3
    assert not list((registry_root / "feature_certificate").glob("*.json"))
    assert_only_run_card_written(registry_root)
    assert_failed_invalid_config_run_card(
        registry_root, stage="validate", config_path=cfg_path, repo_root=tmp_path, expect_environment=True
    )


def test_missing_cluster_environment_evidence_fails_before_heavy_work(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_CLUSTER", "1")
    monkeypatch.delenv("INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("INTERPLAB_ENV_INSTALL_MANIFEST_PATH", raising=False)
    monkeypatch.setattr(validate, "_get_or_raise", lambda *args, **kwargs: pytest.fail("registry access should not start"))

    registry_root = tmp_path / "registry"
    cfg = _write_validate_config(
        tmp_path,
        characterization_manifest_hash="sha256:" + "a" * 64,
        census_report_hash="sha256:" + "b" * 64,
    )
    exit_code = validate.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert_only_run_card_written(registry_root)
    assert_failed_environment_run_card(
        registry_root,
        stage="validate",
        config_path=cfg,
        repo_root=tmp_path,
        expected_roles={"characterization_manifest", "census_report"},
    )
