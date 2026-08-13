"""Tests for scripts/final_pairing/final_pairing_evidence_document.py.

No network, no eng3/concept-bundle checkout required for these tests --
`reconcile_against_static_snapshot` is checked against the committed
static snapshot fixture (tests/fixtures/eng3_concept_bundle/
accepted_input_schema_2c8cf5b.json), never a live worktree. The live
`reconcile_producer_output_with_eng3`/`reconcile_schema_with_eng3`
subprocess wrappers were verified manually against a clean worktree of
eng3/concept-bundle@2c8cf5b during development (see the commit message
for e6e2a7f) -- exercising them here would require that worktree to
exist on whatever machine runs this suite, so they are not re-tested
automatically.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_evidence_document as ed  # noqa: E402

FROZEN_COMMIT = "880b48a7f50b8c716e64956b915857dd1fcde350"
FROZEN_SHA = "b0b23cf1502dae53f88905ee7393b7e67f8b05f84f3251d26a6c506480a9531f"


def _sample_document(head: str = "0" * 40) -> dict:
    return ed.assemble_discovery_document(
        run_id="r-test-0001", code_commit=head, entrypoint="test", host="test-host",
        created_at="2026-08-13T00:00:00Z",
        model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
        sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="deadbeef" * 5,
        sae_id="resid_post_all/layer_29_width_16k_l0_big", layer=29,
        layer_selection={"selected_by": "test", "rationale": "test", "recorded_in": "tamia:test/discovery_record.json"},
        concept_id="cheese", hypothesis_source="test hypothesis",
        search_scope="test scope", candidate_index=1, engineering_index_rediscovery_note=None,
        feature_certificate={
            "feature_index": 3, "concept_id": "cheese", "specificity": 0.9, "sensitivity": 0.85,
            "cross_lingual_firing": 0.8, "selectivity": 0.88, "probe": {"auc": 0.91},
            "verdict": "green", "verdict_basis": "test fixture",
        },
        subject=[{"content_hash": "sha256:" + "0" * 64, "location": "tamia:test/subject.json", "role": "discovery_record"}],
        calibration_protocol="test-v1", calibrated_by="test", calibrated_at="2026-08-13T00:00:00Z",
        directions={
            "amplify": ed.build_direction_block(
                operation="clamp", feature_indices=[3], unit="corpus_max_multiple",
                unit_source="background corpus max activation", strengths={"low": 0.5, "medium": 1.0, "high": 2.0},
            ),
            "suppress": None,
        },
        positions="all",
        prompt_set_id="final_pairing_v1_cheese", prompt_set_source_path="prompts/final_pairing/v1/prompt_sets.jsonl",
        prompt_set_source_sha256="sha256:" + FROZEN_SHA, prompt_set_source_commit=FROZEN_COMMIT,
        paraphrase_families=[{"family_id": fam, "prompts": ["p1", "p2"]} for fam in ("f1", "f2", "f3")],
        causal_validation_computed_at_commit=head, causal_validation_positions="all",
        gates=[
            *[{"gate": g, "status": "pass", "family_id": f, "evidence": "test"} for f in ("f1", "f2", "f3") for g in ("G-A", "G-B", "G-C")],
            {"gate": "G-D", "status": "pass", "direction": "amplify", "evidence": "test"},
        ],
        spot_read=None,
        dose_response={
            "amplify": {"computed_at_commit": head,
                        "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "test"}],
                        "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                        "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
        },
    )


def test_assemble_discovery_document_emits_all_twelve_root_fields():
    document = _sample_document()
    assert set(document) == set(ed.ROOT_REQUIRED_FIELDS)


def test_assemble_discovery_document_amplify_only_leaves_suppress_none():
    document = _sample_document()
    assert document["calibration"]["directions"]["suppress"] is None
    assert document["calibration"]["directions"]["amplify"] is not None


def test_reconcile_against_static_snapshot_passes_for_a_well_formed_document():
    document = _sample_document()
    result = ed.reconcile_against_static_snapshot(REPO_ROOT, document)
    assert result["compatible"] is True
    assert result["missing_root_fields"] == []
    assert result["snapshot_commit"] == ed.STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT


def test_reconcile_against_static_snapshot_flags_a_missing_root_field():
    document = _sample_document()
    del document["dose_response"]
    result = ed.reconcile_against_static_snapshot(REPO_ROOT, document)
    assert result["compatible"] is False
    assert "dose_response" in result["missing_root_fields"]


def test_producer_schema_declaration_declares_all_twelve_root_fields():
    declared = set(ed.producer_schema_declaration()["objects"]["<root>"]["required"])
    assert declared == set(ed.ROOT_REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# build_direction_block: enforces the ablate/clamp shape, never trusts the
# caller.
# ---------------------------------------------------------------------------


def test_build_direction_block_ablate_has_no_unit_and_weight_exactly_one():
    block = ed.build_direction_block(operation="ablate", feature_indices=[3, 7])
    assert block["operation"] == "ablate"
    assert "unit" not in block and "unit_source" not in block and "strengths" not in block
    assert all(t["weight"] == 1.0 for t in block["targets"])


def test_build_direction_block_ablate_rejects_a_caller_supplied_unit():
    with pytest.raises(ValueError, match="no unit/unit_source/strengths"):
        ed.build_direction_block(operation="ablate", feature_indices=[3], unit="corpus_max_multiple")


def test_build_direction_block_clamp_requires_unit_unit_source_and_strengths():
    with pytest.raises(ValueError, match="requires unit, unit_source, and strengths"):
        ed.build_direction_block(operation="clamp", feature_indices=[3])


def test_build_direction_block_clamp_rejects_incomplete_strengths():
    with pytest.raises(ValueError, match="exactly the keys low/medium/high"):
        ed.build_direction_block(
            operation="clamp", feature_indices=[3], unit="corpus_max_multiple",
            unit_source="background corpus max activation", strengths={"low": 0.5, "medium": 1.0},
        )


def test_build_direction_block_rejects_an_unknown_operation():
    with pytest.raises(ValueError, match="operation must be"):
        ed.build_direction_block(operation="scale", feature_indices=[3])
