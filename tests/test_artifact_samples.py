"""One minimal-but-valid sample payload per §4 artifact type (A1, A3-A12),
built through `envelope.dump`. Proves each hand-authored schema is actually
satisfiable, not just syntactically valid JSON Schema (that's
test_schema_validate's job) -- and exercises registry put/get across every
type, not just eval_compat_map. A2 (concept_battery) is not an envelope
type and is covered separately in test_concept_battery_schema.py.
"""

import pytest

from interplab.core import envelope
from interplab.registry import registry

_HASH_A = "sha256:" + "a" * 64
_HASH_B = "sha256:" + "b" * 64
_HASH_C = "sha256:" + "c" * 64


def _sample(artifact_type: str) -> tuple[list[dict], dict]:
    """Returns (subject, payload) for a minimal valid instance of `artifact_type`."""
    samples: dict[str, tuple[list[dict], dict]] = {
        "corpus_manifest": (
            [],
            {
                "name": "fineweb-sample",
                "recipe": {
                    "dataset": "HuggingFaceFW/fineweb",
                    "revision": "abc123",
                    "split": "train",
                    "subset_spec": None,
                    "filters": {},
                },
                "token_count": 1000,
                "doc_count": 10,
                "dedup_rate": None,
                "tokenizer": {"name": "Qwen/Qwen2.5-14B", "revision": "main"},
                "sample_checksum": _HASH_A,
            },
        ),
        "census_report": (
            [{"content_hash": _HASH_A, "location": "local:registry/corpus_manifest/abc.json", "role": "corpus_manifest"}],
            {
                "method": {"matcher": "regex", "case_folding": True, "boundary": "word", "coverage": "full"},
                "concepts": {
                    "poutine": {
                        "en": {
                            "status": "measured",
                            "per_term": [{"term": "poutine", "occurrences": 0, "token_split": ["pou", "tine"], "byte_fallback": False}],
                            "occurrences_total": 0,
                            "per_million_tokens": 0.0,
                            "doc_count": 0,
                        },
                        "fr": {
                            "status": "no_terms",
                            "per_term": None,
                            "occurrences_total": None,
                            "per_million_tokens": None,
                            "doc_count": None,
                        },
                    }
                },
            },
        ),
        "store_manifest": (
            [{"content_hash": _HASH_A, "location": "local:registry/corpus_manifest/abc.json", "role": "corpus_manifest"}],
            {
                "model": {"name": "Qwen/Qwen2.5-14B", "revision": "main"},
                "hook_name": "blocks.28.hook_resid_post",
                "hook_layer": 28,
                "context_size": 128,
                "prepend_bos": True,
                "dtype": "bfloat16",
                "token_count": 1_000_000,
                "position_policy": {"exclude_bos": True, "exclude_padding": True, "excluded_first_n": 1},
                "eval_holdout": {"method": "doc_hash_mod", "modulus": 20, "residues": [0]},
                "qa": {
                    "norm_by_position": [1.0, 2.0],
                    "special_token_fraction": 0.0,
                    "adjacent_autocorrelation": 0.01,
                    "chat_divergence": None,
                    "verdict": "green",
                },
            },
        ),
        "sae_checkpoint": (
            [{"content_hash": _HASH_A, "location": "tamia:store/abc", "role": "store"}],
            {
                "config": {"d_in": 5120, "d_sae": 163840},
                "store_hash": _HASH_A,
                "seed": 42,
                "tokens_trained": 500_000_000,
                "wandb": None,
                "telemetry_tail": {"fvu": 0.05, "fvu_source": "training_eval", "dead_count": 120},
            },
        ),
        "sae_certificate": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
            {
                "eval_slice": {
                    "corpus": {"content_hash": _HASH_A, "location": "hf:HuggingFaceFW/fineweb@main"},
                    "selection": {"method": "holdout_split", "params": {"modulus": 20, "residues": [0]}},
                    "n_tokens": 10_000_000,
                    "disjointness": "by_construction",
                },
                "metrics": {
                    "ce_recovered": 0.97,
                    "fvu": 0.05,
                    "dead_fraction": 0.02,
                    "density_histogram": {"bin_edges_log10": [-6, -5, -4], "counts": [10, 20]},
                    "max_decoder_cosine_p999": 0.3,
                    "per_position_fvu": [0.05, 0.06],
                },
                "bands_version": 1,
                "verdict": "green",
                "per_metric_verdicts": {"ce_recovered": "green"},
            },
        ),
        "characterization_manifest": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
            {
                "sample": {"n_tokens": 5_000_000, "chat_slice_tokens": 100_000},
                "index_layout_version": 1,
                "per_feature_columns": [
                    "corpus_max", "firing_rate", "decile_boundaries",
                    "logit_top_tokens", "autointerp_label", "autointerp_detection_score",
                ],
                "judge": {"model": "claude-sonnet", "rubric_version": "v1", "prompt_version": "v1"},
            },
        ),
        "feature_certificate": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
            {
                "feature_index": 9056,
                "concept_id": "cheese",
                "specificity": {"decile_means": [0.1, 0.2, 3.0], "rubric_version": "v1", "judge_model": "claude", "prompt_version": "v1"},
                "sensitivity": {"status": "measured", "word_absent_fire_rate": 0.01, "per_language": {"en": 0.01}},
                "cross_lingual_firing": {"fr": {"probe_fire_rate": 0.2}},
                "selectivity": {"neighbors": [{"index": 123, "cosine": 0.4, "note": "unrelated"}]},
                "probe": {"auc": 0.9, "feature_auc": 0.85, "gap": 0.05, "probe_config_hash": _HASH_B},
                "verdict": "green",
                "verdict_basis": ["specificity", "sensitivity", "selectivity", "probe"],
            },
        ),
        "intervention_result": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
            {
                "spec": {
                    "kind": "clamp", "feature_index": 9056, "value_in_max_units": 2.0,
                    "corpus_max": 8.3, "positions": "all", "checkpoint_hash": _HASH_A,
                    "direction_seed": None,
                },
                "arms": [
                    {"arm": "steered", "scales_in_max_units": [1.0, 2.0], "generations_ref": {"content_hash": _HASH_C, "location": "tamia:generations/abc"}}
                ],
                "blinding": {"shuffled": True, "map_ref": "local:registry/blinding/abc.json"},
                "sampling": {"temperature": 1.0, "top_p": 0.9, "max_new_tokens": 50, "seed": 0},
                "lodestar": {
                    "run_ref": "lodestar:run/abc", "judge_model": "claude-sonnet", "rubric_version": "v1",
                    "per_prompt_scores": [{"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.8}],
                },
                "capability_delta": {
                    "slice": {"content_hash": _HASH_A, "location": "local:data/pinned_capability_slice.jsonl"},
                    "n_tokens": 128,
                    "per_arm": [
                        {"arm": "baseline", "scale": None, "ppl": 12.5},
                        {"arm": "steered", "scale": 2.0, "ppl": 15.1},
                    ],
                },
            },
        ),
        "run_card": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
            {
                "run_id": "r20260708-1432-a7f3",
                "stage": "certify",
                "config_hash": _HASH_B,
                "config_ref": "local:configs/certify_l28.yaml",
                "inputs": [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "checkpoint"}],
                "outputs": [{"content_hash": _HASH_C, "location": "local:registry/sae_certificate/abc.json", "role": "certificate"}],
                "status": "completed",
                "exit_code": 0,
                "outcome_line": "green certificate",
                "slurm": None,
                "log_section": None,
                "environment": {
                    "profile": "local", "python": "3.12.0", "torch": "2.4.0", "lock_hash": None,
                    "sae_lens": "3.23.0", "transformers": "4.44.0", "transformer_lens": "2.15.4",
                },
            },
        ),
        "claim_report": (
            [{"content_hash": _HASH_A, "location": "tamia:sae_checkpoint/abc", "role": "sae_checkpoint"}],
            {
                "claim_spec": {
                    "question": "does cheese-9056 respond to steering?",
                    "anchor": {"artifact_type": "intervention_result", "content_hashes": [_HASH_C]},
                    "required_links": [
                        {
                            "artifact_type": "feature_certificate", "subject_role": "feature_certificate",
                            "via": "subject_ref", "min_schema_version": 1, "require_instruments": ["specificity"],
                        },
                        {"artifact_type": "sae_certificate", "subject_role": "sae_checkpoint", "via": "subject_of", "min_schema_version": 1},
                    ],
                    "eval_compat_version": 1,
                },
                "chain": [
                    {"link": "intervention_result", "artifact_hash": _HASH_C, "status": "ok", "note": None},
                    {"link": "feature_certificate", "artifact_hash": _HASH_B, "status": "ok", "note": None},
                    {"link": "sae_certificate", "artifact_hash": None, "status": "missing", "note": "not found"},
                ],
                "stamp": "DRAFT — UNCERTIFIED CHAIN",
                "statistics": {"lodestar_score|arm=steered|scale=1.0": {"estimate": 0.5, "ci_low": 0.3, "ci_high": 0.7, "n_prompts": 100, "n_seeds": 3, "method": "bootstrap_ci+seed_variance"}},
                "figures": [{"name": "dose_response", "ref": {"content_hash": _HASH_A, "location": "local:reports/r1/fig1.png"}}],
                "rendered": {
                    "md_ref": {"content_hash": _HASH_B, "location": "local:reports/r1/report.md"},
                    "html_ref": {"content_hash": _HASH_C, "location": "local:reports/r1/report.html"},
                },
            },
        ),
        "eval_compat_map": (
            [],
            {
                "version": 1,
                "judge_classes": [{"class_id": "claude-v1", "members": [{"judge_model": "claude-sonnet", "rubric_version": "v1", "prompt_version": "v1"}]}],
            },
        ),
    }
    return samples[artifact_type]


ARTIFACT_TYPES = [
    "corpus_manifest", "census_report", "store_manifest", "sae_checkpoint",
    "sae_certificate", "characterization_manifest", "feature_certificate",
    "intervention_result", "run_card", "claim_report", "eval_compat_map",
]


@pytest.mark.parametrize("artifact_type", ARTIFACT_TYPES)
def test_sample_payload_satisfies_schema_and_round_trips_through_registry(
    artifact_type, tmp_path, created_by
):
    subject, payload = _sample(artifact_type)
    artifact = envelope.dump(
        artifact_type=artifact_type,
        schema_version=1,
        created_by=created_by,
        subject=subject,
        payload=payload,
    )
    h = registry.put(artifact, registry_root=tmp_path)
    assert registry.get(h, registry_root=tmp_path) == artifact
    assert registry.find(artifact_type, registry_root=tmp_path) == [artifact]
