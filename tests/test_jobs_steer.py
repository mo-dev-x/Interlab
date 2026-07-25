"""§6.1 steer job (SS7/SS8, GATE G3 consumer): generation across all
configured arms/scales against a real (fixture) checkpoint + real
characterization index. `corpus_max` and matched-feature sampling verified
to come exclusively from the FeatureIndex search API; claim mode verified
to produce all required control arms + blinding.shuffled = true at creation.

The checkpoint + characterization index (expensive: 256-feature indexing)
are built ONCE per test module and reused read-only across every test below
-- same shared-fixture discipline WP5/WP6/WP7 already established, to stay
inside §8.3's <5min hard-test budget.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope, hashing, uris
from interplab.core._schema_registry import SchemaValidationError
from interplab.jobs import characterize, steer
from interplab.registry.registry import put as registry_put

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _created_by():
    return {"run_id": "r20260710-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


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


def _register_feature_certificate(registry_root: Path, checkpoint_hash: str, feature_index: int) -> str:
    cert = envelope.dump(
        artifact_type="feature_certificate", schema_version=1, created_by=_created_by(),
        subject=[{"content_hash": checkpoint_hash, "location": "local:x", "role": "sae_checkpoint"}],
        payload={
            "feature_index": feature_index, "concept_id": "zorbium",
            "specificity": {"decile_means": [0.1], "rubric_version": "v1", "judge_model": "none", "prompt_version": "v1"},
            "sensitivity": {"status": "unavailable", "word_absent_fire_rate": None, "per_language": None},
            "cross_lingual_firing": None,
            "selectivity": {"neighbors": []},
            "probe": {"auc": 0.9, "feature_auc": 0.8, "gap": 0.1, "probe_config_hash": "sha256:" + "7" * 64},
            "verdict": "green", "verdict_basis": ["specificity"],
        },
    )
    return registry_put(cert, registry_root=registry_root)


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
    registry_root = tmp_path_factory.mktemp("steer_shared_registry")
    index_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "jobs_steer_shared"
    if index_dir.exists():
        shutil.rmtree(index_dir)

    checkpoint_hash = _register_checkpoint(registry_root)
    manifest_hash = _build_characterization_manifest(
        registry_root, tmp_path_factory.mktemp("steer_characterize_cfg"), index_dir, checkpoint_hash
    )

    yield {"registry_root": registry_root, "checkpoint_hash": checkpoint_hash, "manifest_hash": manifest_hash}

    shutil.rmtree(index_dir, ignore_errors=True)


def _write_config(tmp_path: Path, shared: dict, gen_dir: Path, **overrides) -> Path:
    cfg = {
        "checkpoint_hash": shared["checkpoint_hash"],
        "characterization_manifest_hash": shared["manifest_hash"],
        "feature_index": 3,
        "prompts": ["Hello there", "Tell me a story"],
        "scales_in_max_units": [1.0],
        "sampling": {"temperature": 0.0, "top_p": 1.0, "max_new_tokens": 4, "seed": 0},
        "generations_dir": str(gen_dir),
    }
    cfg.update(overrides)
    cfg_path = tmp_path / "steer.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return cfg_path


@pytest.fixture
def gen_scratch_dir(tmp_path):
    d = uris.REPO_ROOT / "results" / "_test_scratch" / f"jobs_steer_{tmp_path.name}"
    if d.exists():
        shutil.rmtree(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_exploratory_mode_writes_two_arms_and_blinds(tmp_path, shared_registry, gen_scratch_dir):
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 0

    results = list((shared_registry["registry_root"] / "intervention_result").glob("*.json"))
    assert len(results) == 1
    payload = envelope.load(results[0])["payload"]

    arms = {a["arm"] for a in payload["arms"]}
    assert arms == {"steered", "baseline"}
    assert payload["blinding"]["shuffled"] is True
    assert payload["blinding"]["map_ref"] is not None
    assert payload["lodestar"] is None
    assert payload["capability_delta"] is None
    steered_arm = next(a for a in payload["arms"] if a["arm"] == "steered")
    assert steered_arm["scales_in_max_units"] == [1.0]
    baseline_arm = next(a for a in payload["arms"] if a["arm"] == "baseline")
    assert baseline_arm["scales_in_max_units"] == []


def test_claim_mode_writes_all_five_arms(tmp_path, shared_registry, gen_scratch_dir):
    fc_hash = _register_feature_certificate(shared_registry["registry_root"], shared_registry["checkpoint_hash"], 3)
    cfg = _write_config(
        tmp_path, shared_registry, gen_scratch_dir,
        feature_certificate_hash=fc_hash,
        prompt_baseline_prompts=["The boiling point of water is", "Photosynthesis converts light into"],
    )
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 0

    results = [envelope.load(p) for p in (shared_registry["registry_root"] / "intervention_result").glob("*.json")]
    claim_result = next(r for r in results if {a["arm"] for a in r["payload"]["arms"]} == {
        "steered", "baseline", "random_direction", "random_feature", "prompt_baseline"
    })
    payload = claim_result["payload"]
    assert payload["blinding"]["shuffled"] is True
    roles = {ref["role"] for ref in claim_result["subject"]}
    assert roles == {"sae_checkpoint", "feature_certificate"}


def test_corpus_max_comes_from_feature_index_search_api(tmp_path, shared_registry, gen_scratch_dir):
    from interplab.characterization.feature_index import FeatureIndex

    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 0

    results = list((shared_registry["registry_root"] / "intervention_result").glob("*.json"))
    payload = envelope.load(results[-1])["payload"]

    index = FeatureIndex.open(shared_registry["manifest_hash"], registry_root=shared_registry["registry_root"])
    assert payload["spec"]["corpus_max"] == index.corpus_max(3)


def test_writes_a_run_card(tmp_path, shared_registry, gen_scratch_dir):
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir)
    steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)

    cards = [json.loads(p.read_text(encoding="utf-8")) for p in (shared_registry["registry_root"] / "run_card").glob("*.json")]
    steer_cards = [c for c in cards if c["payload"]["stage"] == "steer"]
    assert steer_cards
    assert steer_cards[-1]["payload"]["exit_code"] == 0


def test_environment_records_the_real_sae_stack_versions(tmp_path, shared_registry, gen_scratch_dir):
    from importlib.metadata import version as pkg_version

    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir)
    steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)

    cards = [json.loads(p.read_text(encoding="utf-8")) for p in (shared_registry["registry_root"] / "run_card").glob("*.json")]
    steer_cards = [c for c in cards if c["payload"]["stage"] == "steer"]
    env = steer_cards[-1]["payload"]["environment"]
    assert env["sae_lens"] == pkg_version("sae-lens")
    assert env["transformers"] == pkg_version("transformers")
    assert env["transformer_lens"] == pkg_version("transformer-lens")


def test_refuses_to_run_on_sae_lens_baseline_mismatch(tmp_path, shared_registry, gen_scratch_dir, monkeypatch):
    """ED-32 fail-closed: refuses before any registry/model access -- exit
    4, no intervention_result written, run card records the offending
    version. Points at a fresh registry so the refusal is proven
    independent of the shared fixture's content."""
    import interplab.core.environment as environment_module

    monkeypatch.setattr(
        environment_module, "resolve_sae_stack_versions",
        lambda: {"sae_lens": "3.23.0", "transformers": "4.44.0", "transformer_lens": "2.15.4"},
    )

    registry_root = tmp_path / "registry"
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir)
    exit_code = steer.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert not list((registry_root / "intervention_result").glob("*.json"))

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "failed"
    assert card["payload"]["exit_code"] == 4
    assert "environment baseline violated" in card["payload"]["outcome_line"]
    assert card["payload"]["environment"]["sae_lens"] == "3.23.0"


def test_missing_checkpoint_is_contract_violation(tmp_path, shared_registry, gen_scratch_dir):
    fake_hash = "sha256:" + "a" * 64
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir, checkpoint_hash=fake_hash)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_missing_characterization_manifest_is_contract_violation(tmp_path, shared_registry, gen_scratch_dir):
    fake_hash = "sha256:" + "b" * 64
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir, characterization_manifest_hash=fake_hash)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_out_of_range_feature_index_is_contract_violation(tmp_path, shared_registry, gen_scratch_dir):
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir, feature_index=999999)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_missing_feature_certificate_in_claim_mode_is_contract_violation(tmp_path, shared_registry, gen_scratch_dir):
    fake_hash = "sha256:" + "c" * 64
    cfg = _write_config(
        tmp_path, shared_registry, gen_scratch_dir,
        feature_certificate_hash=fake_hash,
        prompt_baseline_prompts=["The boiling point of water is", "Photosynthesis converts light into"],
    )
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_generations_dir_outside_repo_root_is_contract_violation(tmp_path, shared_registry):
    cfg = _write_config(tmp_path, shared_registry, tmp_path / "outside_repo_gens")
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_config_schema_validation_failure_raises(tmp_path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(yaml.safe_dump({"feature_index": 0}), encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        steer.run(cfg_path, registry_root=tmp_path / "registry", repo_root=tmp_path)


def test_claim_mode_without_prompt_baseline_prompts_is_contract_violation(tmp_path, shared_registry, gen_scratch_dir):
    fc_hash = _register_feature_certificate(shared_registry["registry_root"], shared_registry["checkpoint_hash"], 3)
    cfg = _write_config(tmp_path, shared_registry, gen_scratch_dir, feature_certificate_hash=fc_hash)
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 3


def test_prompt_baseline_generations_come_from_supplied_prompt_baseline_prompts(tmp_path, shared_registry, gen_scratch_dir):
    fc_hash = _register_feature_certificate(shared_registry["registry_root"], shared_registry["checkpoint_hash"], 3)
    pb_prompts = ["The boiling point of water is", "Photosynthesis converts light into"]
    cfg = _write_config(
        tmp_path, shared_registry, gen_scratch_dir,
        feature_certificate_hash=fc_hash, prompt_baseline_prompts=pb_prompts,
    )
    exit_code = steer.run(cfg, registry_root=shared_registry["registry_root"], repo_root=tmp_path)
    assert exit_code == 0

    generations = json.loads((gen_scratch_dir / "generations.json").read_text(encoding="utf-8"))["records"]
    pb_records = [r for r in generations if r["arm"] == "prompt_baseline"]
    assert {r["prompt"] for r in pb_records} == set(pb_prompts)
    primary_prompts = {"Hello there", "Tell me a story"}
    assert not (primary_prompts & {r["prompt"] for r in pb_records})
