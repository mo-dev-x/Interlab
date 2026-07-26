"""§6.1 characterize job (SS5): streaming indexer + A7 manifest + dashboards
against a real (fixture) sae_checkpoint."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope, hashing, uris
from interplab.core._schema_registry import SchemaValidationError
from interplab.jobs import characterize
from interplab.registry.registry import put as registry_put

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _register_checkpoint(registry_root: Path) -> str:
    created_by = {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}
    weights_hash = hashing.hash_checkpoint_dir(FIXTURES_DIR / "tiny_sae")
    model_hash = hashing.hash_directory(FIXTURES_DIR / "tiny_model")
    checkpoint = envelope.dump(
        artifact_type="sae_checkpoint", schema_version=1, created_by=created_by,
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
    created_by = {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}
    manifest = envelope.dump(
        artifact_type="corpus_manifest", schema_version=1, created_by=created_by, subject=[],
        payload={
            "name": "pinned-text", "recipe": {"dataset": "unknown", "revision": "unknown", "split": "unknown", "subset_spec": None, "filters": {}},
            "token_count": 1000, "doc_count": 200, "dedup_rate": None,
            "tokenizer": {"name": "tiny-tokenizer", "revision": "main"}, "sample_checksum": "sha256:" + "9" * 64,
        },
    )
    return registry_put(manifest, registry_root=registry_root)


def _write_config(
    tmp_path: Path, checkpoint_hash: str, index_dir: Path, *, corpus_manifest_hash: str | None = None, **overrides
) -> Path:
    cfg = {
        "checkpoint_hash": checkpoint_hash,
        "corpus_manifest_hash": corpus_manifest_hash or "sha256:" + "9" * 64,
        "corpus_location": "local:tests/fixtures/pinned_text.jsonl",
        "n_docs": 15,
        "judge": "stub",
        "rng_seed": 0,
        "index_dir": str(index_dir),
    }
    cfg.update(overrides)
    cfg_path = tmp_path / "characterize.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return cfg_path


@pytest.fixture
def index_scratch_dir():
    d = uris.REPO_ROOT / "results" / "_test_scratch" / "jobs_characterize"
    if d.exists():
        shutil.rmtree(d)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_full_run_writes_index_manifest_and_dashboards(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = _write_config(tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=corpus_manifest_hash)

    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    assert (index_scratch_dir / "per_feature_stats.json").is_file()
    assert (index_scratch_dir / "examples").is_dir()
    assert (index_scratch_dir / "dashboards" / "catalog.md").is_file()

    manifests = list((registry_root / "characterization_manifest").glob("*.json"))
    assert len(manifests) == 1
    manifest = envelope.load(manifests[0])
    assert manifest["payload"]["judge"]["model"] == "stub-judge-v1"
    assert manifest["payload"]["sample"]["n_tokens"] > 0
    assert set(manifest["payload"]["per_feature_columns"]) >= {
        "corpus_max", "firing_rate", "decile_boundaries", "logit_top_tokens",
        "autointerp_label", "autointerp_detection_score",
    }

    # WP7 compliance fix: A7's own spec (§4) requires corpus_manifest(s) of
    # the sample in `subject`, alongside sae_checkpoint.
    roles = {ref["role"] for ref in manifest["subject"]}
    assert roles == {"sae_checkpoint", "corpus_manifest", "index"}
    corpus_ref = next(r for r in manifest["subject"] if r["role"] == "corpus_manifest")
    assert corpus_ref["content_hash"] == corpus_manifest_hash


def test_writes_a_run_card(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = _write_config(tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=corpus_manifest_hash)
    characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    cards = list((registry_root / "run_card").glob("*.json"))
    assert len(cards) == 1
    card = json.loads(cards[0].read_text(encoding="utf-8"))
    assert card["payload"]["stage"] == "characterize"
    assert card["payload"]["status"] == "completed"
    assert card["payload"]["exit_code"] == 0


def test_chat_slice_is_recorded_but_kept_separate(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = _write_config(
        tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=corpus_manifest_hash,
        chat_slice_location="local:tests/fixtures/pinned_text.jsonl", n_chat_docs=3,
    )
    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 0

    manifests = list((registry_root / "characterization_manifest").glob("*.json"))
    manifest = envelope.load(manifests[0])
    assert manifest["payload"]["sample"]["chat_slice_tokens"] > 0

    stats = json.loads((index_scratch_dir / "per_feature_stats.json").read_text(encoding="utf-8"))
    assert any(f["chat_slice_max"] is not None for f in stats["features"])


def test_environment_records_the_real_sae_stack_versions(tmp_path, index_scratch_dir):
    from importlib.metadata import version as pkg_version

    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = _write_config(tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=corpus_manifest_hash)
    characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    env = card["payload"]["environment"]
    assert env["sae_lens"] == pkg_version("sae-lens")
    assert env["transformers"] == pkg_version("transformers")
    assert env["transformer_lens"] == pkg_version("transformer-lens")


def test_refuses_to_run_on_sae_lens_baseline_mismatch(tmp_path, index_scratch_dir, monkeypatch):
    """ED-32 fail-closed: refuses before any registry/model access -- exit
    4, no manifest written, run card records the offending version."""
    import interplab.core.environment as environment_module

    monkeypatch.setattr(
        environment_module, "resolve_sae_stack_versions",
        lambda: {"sae_lens": "3.23.0", "transformers": "4.44.0", "transformer_lens": "2.15.4"},
    )

    registry_root = tmp_path / "registry"
    fake_hash = "sha256:" + "a" * 64
    cfg = _write_config(tmp_path, fake_hash, index_scratch_dir)

    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code == 4
    assert not list((registry_root / "characterization_manifest").glob("*.json"))

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "failed"
    assert card["payload"]["exit_code"] == 4
    assert "environment baseline violated" in card["payload"]["outcome_line"]
    assert card["payload"]["environment"]["sae_lens"] == "3.23.0"


def test_missing_checkpoint_is_contract_violation(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    fake_hash = "sha256:" + "a" * 64
    cfg = _write_config(tmp_path, fake_hash, index_scratch_dir)
    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_missing_corpus_manifest_is_contract_violation(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    fake_corpus_manifest_hash = "sha256:" + "b" * 64
    cfg = _write_config(tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=fake_corpus_manifest_hash)
    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_empty_corpus_is_contract_violation(tmp_path, index_scratch_dir):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    empty_docs = FIXTURES_DIR / "empty_docs_for_characterize_test.jsonl"
    empty_docs.write_text("", encoding="utf-8")
    try:
        cfg = _write_config(
            tmp_path, checkpoint_hash, index_scratch_dir, corpus_manifest_hash=corpus_manifest_hash,
            corpus_location="local:tests/fixtures/empty_docs_for_characterize_test.jsonl",
        )
        del_key = "n_docs"
        cfg_data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        cfg_data.pop(del_key, None)
        cfg.write_text(yaml.safe_dump(cfg_data), encoding="utf-8")

        exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
        assert exit_code == 3
    finally:
        empty_docs.unlink(missing_ok=True)


def test_index_dir_outside_repo_root_is_contract_violation(tmp_path):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_checkpoint(registry_root)
    corpus_manifest_hash = _register_corpus_manifest(registry_root)
    cfg = _write_config(
        tmp_path, checkpoint_hash, tmp_path / "outside_repo_index", corpus_manifest_hash=corpus_manifest_hash
    )
    exit_code = characterize.run(cfg, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_config_schema_validation_failure_raises(tmp_path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(yaml.safe_dump({"checkpoint_hash": "not-a-hash"}), encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        characterize.run(cfg_path, registry_root=tmp_path / "registry", repo_root=tmp_path)


def test_load_docs_dispatches_local_directories_to_hf_dataset_cache(tmp_path, monkeypatch):
    """ED-34: `_load_docs` (like `certification.eval_slice.load_corpus_docs`,
    its sanctioned twin) dispatches on what's actually at the resolved
    path -- a directory is a local HuggingFace dataset cache, not JSONL."""
    def fake_load_dataset(path, split=None, streaming=None):
        assert path.endswith("fineweb_subset")
        assert split == "train"
        assert streaming is True
        return [{"text": "a"}, {"text": "b"}]

    import datasets

    monkeypatch.setattr(datasets, "load_dataset", fake_load_dataset)
    cache_dir = tmp_path / "fineweb_subset"
    cache_dir.mkdir()

    docs = characterize._load_docs(cache_dir)
    assert docs == ["a", "b"]


def test_load_docs_dispatches_files_to_jsonl(tmp_path):
    jsonl_path = tmp_path / "docs.jsonl"
    jsonl_path.write_text('{"id": 0, "text": "hello"}\n{"id": 1, "text": "world"}\n', encoding="utf-8")

    docs = characterize._load_docs(jsonl_path)
    assert docs == ["hello", "world"]


def test_load_local_resolves_tamia_corpus_location(tmp_path, monkeypatch):
    """ED-34: characterize's own `_load_local` (weights/corpus/chat_slice
    guard) resolves `tamia:` via `$SCRATCH`, same as the other four sites."""
    monkeypatch.setenv("SCRATCH", str(tmp_path))
    corpus_dir = tmp_path / "interplab" / "eval_corpus"
    corpus_dir.mkdir(parents=True)

    resolved = characterize._load_local("tamia:eval_corpus", what="the corpus")
    assert resolved == corpus_dir
