"""Synthetic registry-tree builders for SS9 chain-assembly tests.

Not a test file (no `test_` functions) -- imported by `test_reports_chain.py`
and `test_jobs_report.py` to construct small, hand-wired registry trees that
exercise `assemble_chain`'s traversal without needing a real cluster
pipeline. Every artifact uses the fictional concept "zorbium"
(`tests/fixtures/synthetic_concepts/zorbium.yaml`, WP5) or plain synthetic
data -- test data only, never laboratory content, same discipline as every
prior work package's synthetic fixtures.

Each `build_*` function writes a fully schema-valid artifact via
`envelope.dump` + `registry.put` and returns the loaded (self-hash-verified)
artifact dict, so callers can chain hashes together (`subject=[...]`)
exactly the way a real job would.
"""

from __future__ import annotations

from pathlib import Path

from interplab.core import envelope
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put

_HASH_WEIGHTS = "sha256:" + "1" * 64
_HASH_MODEL = "sha256:" + "2" * 64
_HASH_BATTERY = "sha256:" + "3" * 64
_HASH_CENSUS = "sha256:" + "4" * 64


def _created_by(run_id: str = "r20260709-0000-test") -> dict:
    return {"run_id": run_id, "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


def _ref(artifact: dict, role: str) -> dict:
    return {"content_hash": artifact["self_hash"], "location": f"local:registry/{artifact['artifact_type']}/x.json", "role": role}


def _put(
    artifact_type: str, subject: list[dict], payload: dict, *, registry_root: Path, created_at: str | None = None
) -> dict:
    artifact = envelope.dump(
        artifact_type=artifact_type, schema_version=1, created_by=_created_by(), subject=subject, payload=payload,
        created_at=created_at,
    )
    h = registry_put(artifact, registry_root=registry_root)
    return registry_get(h, registry_root=registry_root)


def build_corpus_manifest(registry_root: Path, *, name: str = "zorbium-corpus") -> dict:
    payload = {
        "name": name,
        "recipe": {"dataset": "synthetic/zorbium", "revision": "v1", "split": "train", "subset_spec": None, "filters": {}},
        "token_count": 100_000, "doc_count": 100, "dedup_rate": None,
        "tokenizer": {"name": "tiny-tokenizer", "revision": "main"},
        "sample_checksum": "sha256:" + "5" * 64,
    }
    return _put("corpus_manifest", [], payload, registry_root=registry_root)


def build_store_manifest(registry_root: Path, corpus_manifest: dict, *, verdict: str = "green") -> dict:
    payload = {
        "model": {"name": "tiny-model", "revision": "main"},
        "hook_name": "blocks.1.hook_resid_post", "hook_layer": 1,
        "context_size": 64, "prepend_bos": True, "dtype": "float32", "token_count": 100_000,
        "position_policy": {"exclude_bos": True, "exclude_padding": True, "excluded_first_n": 1},
        "eval_holdout": {"method": "doc_hash_mod", "modulus": 20, "residues": [0]},
        "qa": {
            "norm_by_position": [1.0, 1.0], "special_token_fraction": 0.0, "adjacent_autocorrelation": 0.0,
            "chat_divergence": None, "verdict": verdict,
        },
    }
    return _put("store_manifest", [_ref(corpus_manifest, "corpus_manifest")], payload, registry_root=registry_root)


def build_sae_checkpoint(registry_root: Path, store_manifest: dict | None) -> dict:
    """`store_hash` non-null (points at `store_manifest`) so the ED-15
    payload-carried special case is exercised; `subject` deliberately omits
    corpus_manifest (matches the real, current `jobs.characterize` /
    non-legacy-checkpoint shape) so corpus_manifest is reachable *only*
    through `store_manifest.subject`, exercising the multi-hop `subject_ref`
    scan."""
    payload = {
        "config": {"d_in": 64, "d_sae": 256}, "store_hash": store_manifest["self_hash"] if store_manifest else None,
        "seed": 0, "tokens_trained": 100_000, "wandb": None,
        "telemetry_tail": {"fvu": 0.05, "fvu_source": "training_eval", "dead_count": 0},
        "training_provenance": {
            "sae_lens": None, "transformers": None, "transformer_lens": None,
            "source": "unknown", "confidence": "unknown",
        },
        "cfg_schema_generation": None,
    }
    subject = [
        {"content_hash": _HASH_WEIGHTS, "location": "local:tests/fixtures/tiny_sae", "role": "weights"},
        {"content_hash": _HASH_MODEL, "location": "local:tests/fixtures/tiny_model", "role": "model"},
    ]
    return _put("sae_checkpoint", subject, payload, registry_root=registry_root)


def build_sae_certificate(
    registry_root: Path, sae_checkpoint: dict, *, verdict: str = "green", created_at: str | None = None
) -> dict:
    payload = {
        "eval_slice": {
            "corpus": {"content_hash": "sha256:" + "6" * 64, "location": "hf:synthetic/zorbium@v1"},
            "selection": {"method": "holdout_split", "params": {"modulus": 20, "residues": [0]}},
            "n_tokens": 10_000, "disjointness": "by_construction",
        },
        "metrics": {
            "ce_recovered": 0.97, "fvu": 0.05, "dead_fraction": 0.02,
            "density_histogram": {"bin_edges_log10": [-6, -5, -4], "counts": [10, 20]},
            "max_decoder_cosine_p999": 0.3, "per_position_fvu": [0.05, 0.06],
        },
        "bands_version": 1, "verdict": verdict, "per_metric_verdicts": {"ce_recovered": verdict},
    }
    return _put(
        "sae_certificate", [_ref(sae_checkpoint, "sae_checkpoint")], payload,
        registry_root=registry_root, created_at=created_at,
    )


def build_characterization_manifest(
    registry_root: Path, sae_checkpoint: dict, *, judge: dict | None = None
) -> dict:
    judge = judge or {"model": "none", "rubric_version": "none", "prompt_version": "none"}
    payload = {
        "sample": {"n_tokens": 100_000, "chat_slice_tokens": 0},
        "index_layout_version": 1,
        "per_feature_columns": [
            "corpus_max", "firing_rate", "decile_boundaries", "logit_top_tokens",
            "autointerp_label", "autointerp_detection_score",
        ],
        "judge": judge,
    }
    return _put(
        "characterization_manifest", [_ref(sae_checkpoint, "sae_checkpoint")], payload, registry_root=registry_root
    )


def build_feature_certificate(
    registry_root: Path, sae_checkpoint: dict, characterization_manifest: dict, *,
    verdict: str = "green", verdict_basis: list[str] | None = None,
    specificity_judge: dict | None = None, feature_index: int = 9,
) -> dict:
    specificity_judge = specificity_judge or {"model": "none", "rubric_version": "none", "prompt_version": "none"}
    verdict_basis = verdict_basis if verdict_basis is not None else ["specificity", "selectivity", "probe"]
    payload = {
        "feature_index": feature_index, "concept_id": "zorbium",
        "specificity": {
            "decile_means": [0.1, 0.5, 2.9],
            "rubric_version": specificity_judge["rubric_version"],
            "judge_model": specificity_judge["model"],
            "prompt_version": specificity_judge["prompt_version"],
        },
        "sensitivity": {"status": "measured", "word_absent_fire_rate": 0.02, "per_language": {"en": 0.02}},
        "cross_lingual_firing": None,
        "selectivity": {"neighbors": [{"index": 3, "cosine": 0.2, "note": "fires weakly"}]},
        "probe": {"auc": 0.95, "feature_auc": 0.9, "gap": 0.05, "probe_config_hash": "sha256:" + "7" * 64},
        "verdict": verdict, "verdict_basis": verdict_basis,
    }
    subject = [
        _ref(sae_checkpoint, "sae_checkpoint"),
        _ref(characterization_manifest, "characterization_manifest"),
        {"content_hash": _HASH_BATTERY, "location": "local:tests/fixtures/synthetic_concepts", "role": "concept_battery"},
        {"content_hash": _HASH_CENSUS, "location": "local:registry/census_report/x.json", "role": "census_report"},
    ]
    return _put("feature_certificate", subject, payload, registry_root=registry_root)


_DEFAULT_ARMS = ["steered", "baseline", "random_direction", "random_feature", "prompt_baseline"]


def build_intervention_result(
    registry_root: Path, sae_checkpoint: dict, feature_certificate: dict | None, *,
    arms: list[str] | None = None, shuffled: bool = True,
    lodestar_judge: dict | None = None, per_prompt_scores: list[dict] | None = None,
) -> dict:
    arms = arms if arms is not None else _DEFAULT_ARMS
    lodestar = None
    if lodestar_judge is not None:
        lodestar = {
            "run_ref": "lodestar:run/synthetic", "judge_model": lodestar_judge["model"],
            "rubric_version": lodestar_judge["rubric_version"], "per_prompt_scores": per_prompt_scores,
        }
    payload = {
        "spec": {
            "kind": "clamp", "feature_index": 9, "value_in_max_units": 2.0, "corpus_max": 5.0,
            "positions": "all", "checkpoint_hash": sae_checkpoint["self_hash"], "direction_seed": None,
        },
        "arms": [
            {"arm": a, "scales_in_max_units": [1.0, 2.0], "generations_ref": {"content_hash": "sha256:" + "8" * 64, "location": "tamia:generations/x"}}
            for a in arms
        ],
        "blinding": {"shuffled": shuffled, "map_ref": "local:registry/blinding/x.json"},
        "sampling": {"temperature": 1.0, "top_p": 0.9, "max_new_tokens": 20, "seed": 0},
        "lodestar": lodestar,
        "capability_delta": None,
    }
    subject = [_ref(sae_checkpoint, "sae_checkpoint")]
    if feature_certificate is not None:
        subject.append(_ref(feature_certificate, "feature_certificate"))
    return _put("intervention_result", subject, payload, registry_root=registry_root)


def build_eval_compat_map(registry_root: Path, *, version: int = 1, judge_classes: list[dict] | None = None) -> dict:
    judge_classes = judge_classes if judge_classes is not None else [
        {"class_id": "stub-class", "members": [
            {"judge_model": "stub-rubric-judge-v1", "rubric_version": "stub-v1", "prompt_version": "stub-v1"},
            {"judge_model": "lodestar-stub", "rubric_version": "stub-v1", "prompt_version": "stub-v1"},
        ]},
        {"class_id": "none-class", "members": [{"judge_model": "none", "rubric_version": "none", "prompt_version": "none"}]},
    ]
    payload = {"version": version, "judge_classes": judge_classes}
    return _put("eval_compat_map", [], payload, registry_root=registry_root)


def build_full_green_chain(registry_root: Path, *, feature_verdict_basis: list[str] | None = None) -> dict:
    """The §7.3 worked chain (cheese dose-response, reskinned to zorbium):
    corpus_manifest -> store_manifest -> sae_checkpoint -> sae_certificate
    -> characterization_manifest -> feature_certificate -> intervention_result
    (anchor). Every link green/ok; `assemble_chain` should stamp CERTIFIED.
    Returns a dict of every artifact, keyed by artifact_type, plus the
    eval_compat_map, for callers to build a claim_spec against."""
    corpus = build_corpus_manifest(registry_root)
    store = build_store_manifest(registry_root, corpus)
    checkpoint = build_sae_checkpoint(registry_root, store)
    certificate = build_sae_certificate(registry_root, checkpoint)
    index = build_characterization_manifest(registry_root, checkpoint)
    feature_cert = build_feature_certificate(
        registry_root, checkpoint, index, verdict_basis=feature_verdict_basis,
    )
    intervention = build_intervention_result(
        registry_root, checkpoint, feature_cert,
        lodestar_judge={"model": "none", "rubric_version": "none"},
        per_prompt_scores=[
            {"prompt_id": "p1", "arm": "steered", "scale": 2.0, "score": 0.9},
            {"prompt_id": "p2", "arm": "steered", "scale": 2.0, "score": 0.8},
            {"prompt_id": "p3", "arm": "steered", "scale": 2.0, "score": 0.85},
            {"prompt_id": "p1", "arm": "baseline", "scale": 2.0, "score": 0.1},
            {"prompt_id": "p2", "arm": "baseline", "scale": 2.0, "score": 0.2},
            {"prompt_id": "p3", "arm": "baseline", "scale": 2.0, "score": 0.15},
        ],
    )
    compat_map = build_eval_compat_map(registry_root)
    return {
        "corpus_manifest": corpus, "store_manifest": store, "sae_checkpoint": checkpoint,
        "sae_certificate": certificate, "characterization_manifest": index,
        "feature_certificate": feature_cert, "intervention_result": intervention,
        "eval_compat_map": compat_map,
    }


def full_chain_claim_spec(chain: dict, *, require_instruments: list[str] | None = None) -> dict:
    """The claim_spec matching `build_full_green_chain`'s topology."""
    required_links = [
        {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
        {"artifact_type": "sae_checkpoint", "subject_role": "sae_checkpoint", "via": "subject_ref", "min_schema_version": 1},
        {"artifact_type": "sae_certificate", "subject_role": "sae_checkpoint", "via": "subject_of", "min_schema_version": 1},
        {"artifact_type": "characterization_manifest", "subject_role": "characterization_manifest", "via": "subject_ref", "min_schema_version": 1},
        {"artifact_type": "store_manifest", "subject_role": "store_manifest", "via": "subject_ref", "min_schema_version": 1},
        {"artifact_type": "corpus_manifest", "subject_role": "corpus_manifest", "via": "subject_ref", "min_schema_version": 1},
    ]
    if require_instruments is not None:
        required_links[0]["require_instruments"] = require_instruments
    return {
        "question": "does the zorbium-9 feature respond to steering?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [chain["intervention_result"]["self_hash"]]},
        "required_links": required_links,
        "eval_compat_version": chain["eval_compat_map"]["payload"]["version"],
    }
