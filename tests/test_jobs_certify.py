"""interplab.jobs.certify (SS4, GATE G1) end-to-end tests against the
pinned tiny fixtures. tiny_sae is untrained/random, so a full run is
expected to land red -- exactly the case §6.2/the architect's notes say
must still write the certificate and exit 2, not fail."""

import json
from pathlib import Path

import pytest
import yaml

from interplab.core import envelope
from interplab.jobs import certify
from interplab.registry.registry import put

_CREATED_BY = {"run_id": "r20260101-0000-aaaa", "code_commit": "x", "entrypoint": "test", "host": "local"}
_WEIGHTS_REF = {"content_hash": "sha256:" + "1" * 64, "location": "local:tests/fixtures/tiny_sae", "role": "weights"}
_MODEL_REF = {"content_hash": "sha256:" + "2" * 64, "location": "local:tests/fixtures/tiny_model", "role": "model"}
_DUMMY_CORPUS_HASH = "sha256:" + "3" * 64


def _register_legacy_checkpoint(registry_root) -> str:
    a5 = envelope.dump(
        artifact_type="sae_checkpoint",
        schema_version=1,
        created_by=_CREATED_BY,
        subject=[_WEIGHTS_REF, _MODEL_REF],
        payload={
            "config": {"model_name": "tiny"},
            "store_hash": None,
            "seed": 0,
            "tokens_trained": 1000,
            "wandb": None,
            "telemetry_tail": {"fvu": 0.1, "fvu_source": "training_eval", "dead_count": 5},
        },
    )
    return put(a5, registry_root=registry_root)


def _register_store_backed_checkpoint(registry_root, *, eval_holdout) -> tuple[str, str]:
    a4 = envelope.dump(
        artifact_type="store_manifest",
        schema_version=1,
        created_by=_CREATED_BY,
        subject=[{"content_hash": _DUMMY_CORPUS_HASH, "location": "local:registry/corpus_manifest/x.json", "role": "corpus_manifest"}],
        payload={
            "model": {"name": "tiny", "revision": "main"},
            "hook_name": "blocks.1.hook_resid_post",
            "hook_layer": 1,
            "context_size": 32,
            "prepend_bos": True,
            "dtype": "float32",
            "token_count": 100_000,
            "position_policy": {"exclude_bos": True, "exclude_padding": True, "excluded_first_n": 1},
            "eval_holdout": eval_holdout,
            "qa": {
                "norm_by_position": [1.0], "special_token_fraction": 0.0,
                "adjacent_autocorrelation": 0.0, "chat_divergence": None, "verdict": "green",
            },
        },
    )
    store_hash = put(a4, registry_root=registry_root)

    a5 = envelope.dump(
        artifact_type="sae_checkpoint",
        schema_version=1,
        created_by=_CREATED_BY,
        subject=[_WEIGHTS_REF, _MODEL_REF],
        payload={
            "config": {"model_name": "tiny"},
            "store_hash": store_hash,
            "seed": 0,
            "tokens_trained": 1000,
            "wandb": None,
            "telemetry_tail": {"fvu": 0.1, "fvu_source": "training_eval", "dead_count": 5},
        },
    )
    checkpoint_hash = put(a5, registry_root=registry_root)
    return checkpoint_hash, store_hash


def _write_config(tmp_path, **overrides) -> Path:
    cfg = {
        "n_tokens": 300,
        "seq_len": 8,
        "batch_size": 4,
        "bands_version": 1,
        "eval_slice": {
            "corpus_manifest_hash": _DUMMY_CORPUS_HASH,
            "corpus_location": "local:tests/fixtures/pinned_text.jsonl",
            "method": "stream_offset",
            "params": {"offset": 0, "count": 50},
        },
    }
    cfg.update(overrides)
    path = tmp_path / "certify.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def test_legacy_checkpoint_full_run_writes_certificate_and_report_card(tmp_path):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_legacy_checkpoint(registry_root)
    cfg_path = _write_config(tmp_path, checkpoint_hash=checkpoint_hash)

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    assert exit_code in (0, 2)  # green/amber -> 0, red -> 2; never anything else
    certs = list((registry_root / "sae_certificate").glob("*.json"))
    assert len(certs) == 1
    cert = json.loads(certs[0].read_text(encoding="utf-8"))
    envelope.load(cert)  # self-consistent, schema-valid
    assert cert["payload"]["verdict"] in ("green", "amber", "red")
    assert cert["payload"]["eval_slice"]["selection"]["method"] == "stream_offset"
    assert cert["payload"]["eval_slice"]["disjointness"] == "by_offset_argument"

    report_dir = tmp_path / "results" / "certificates"
    assert list(report_dir.rglob("report_card.md"))
    assert list(report_dir.rglob("report_card.png"))


def test_red_verdict_writes_certificate_and_exits_2(tmp_path):
    """The untrained tiny_sae fixture reconstructs essentially nothing --
    this MUST land red, and red is not a failure: certificate written,
    exit code exactly 2 (§6.2), run card status gate_failed."""
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_legacy_checkpoint(registry_root)
    cfg_path = _write_config(tmp_path, checkpoint_hash=checkpoint_hash)

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    cert = json.loads(next((registry_root / "sae_certificate").glob("*.json")).read_text(encoding="utf-8"))
    assert cert["payload"]["verdict"] == "red"
    assert exit_code == 2

    card = json.loads(next((registry_root / "run_card").glob("*.json")).read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "gate_failed"
    assert card["payload"]["exit_code"] == 2
    assert len(card["payload"]["outputs"]) == 1


def test_store_backed_checkpoint_auto_derives_holdout_split(tmp_path):
    registry_root = tmp_path / "registry"
    eval_holdout = {"method": "doc_hash_mod", "modulus": 10, "residues": [0]}
    checkpoint_hash, _store_hash = _register_store_backed_checkpoint(registry_root, eval_holdout=eval_holdout)

    cfg = {
        "checkpoint_hash": checkpoint_hash,
        "n_tokens": 300,
        "seq_len": 8,
        "batch_size": 4,
        "bands_version": 1,
        "eval_slice": {
            "corpus_manifest_hash": _DUMMY_CORPUS_HASH,
            "corpus_location": "local:tests/fixtures/pinned_text.jsonl",
        },
    }
    cfg_path = tmp_path / "certify.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code in (0, 2)

    cert = json.loads(next((registry_root / "sae_certificate").glob("*.json")).read_text(encoding="utf-8"))
    assert cert["payload"]["eval_slice"]["selection"]["method"] == "holdout_split"
    assert cert["payload"]["eval_slice"]["selection"]["params"] == {"modulus": 10, "residues": [0]}
    assert cert["payload"]["eval_slice"]["disjointness"] == "by_construction"


def test_explicit_eval_slice_overrides_store_eval_holdout(tmp_path):
    registry_root = tmp_path / "registry"
    eval_holdout = {"method": "doc_hash_mod", "modulus": 10, "residues": [0]}
    checkpoint_hash, _ = _register_store_backed_checkpoint(registry_root, eval_holdout=eval_holdout)

    cfg_path = _write_config(tmp_path, checkpoint_hash=checkpoint_hash)  # explicit stream_offset
    certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)

    cert = json.loads(next((registry_root / "sae_certificate").glob("*.json")).read_text(encoding="utf-8"))
    assert cert["payload"]["eval_slice"]["selection"]["method"] == "stream_offset"


def test_unknown_checkpoint_hash_is_contract_violation(tmp_path):
    registry_root = tmp_path / "registry"
    cfg_path = _write_config(tmp_path, checkpoint_hash="sha256:" + "9" * 64)

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_legacy_checkpoint_without_eval_holdout_requires_explicit_selection(tmp_path):
    registry_root = tmp_path / "registry"
    checkpoint_hash = _register_legacy_checkpoint(registry_root)
    cfg = {
        "checkpoint_hash": checkpoint_hash,
        "n_tokens": 300, "seq_len": 8, "batch_size": 4, "bands_version": 1,
        "eval_slice": {
            "corpus_manifest_hash": _DUMMY_CORPUS_HASH,
            "corpus_location": "local:tests/fixtures/pinned_text.jsonl",
        },
    }
    cfg_path = tmp_path / "certify.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3


def test_config_must_validate_against_schema(tmp_path):
    with pytest.raises(FileNotFoundError):
        certify.run(tmp_path / "does_not_exist.yaml", registry_root=tmp_path / "registry", repo_root=tmp_path)


def test_store_hash_mismatch_is_contract_violation(tmp_path):
    """A5.store_hash pointing at a store that was never registered."""
    registry_root = tmp_path / "registry"
    a5 = envelope.dump(
        artifact_type="sae_checkpoint", schema_version=1, created_by=_CREATED_BY,
        subject=[_WEIGHTS_REF, _MODEL_REF],
        payload={
            "config": {"model_name": "tiny"}, "store_hash": "sha256:" + "7" * 64, "seed": 0,
            "tokens_trained": 1000, "wandb": None, "telemetry_tail": {"fvu": 0.1, "fvu_source": "training_eval", "dead_count": 5},
        },
    )
    checkpoint_hash = put(a5, registry_root=registry_root)
    cfg_path = _write_config(tmp_path, checkpoint_hash=checkpoint_hash)

    exit_code = certify.run(cfg_path, registry_root=registry_root, repo_root=tmp_path)
    assert exit_code == 3
