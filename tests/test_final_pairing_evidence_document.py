"""Tests for scripts/final_pairing/final_pairing_evidence_document.py.

No network, no eng3/concept-bundle checkout required for MOST of these
tests -- `reconcile_against_static_snapshot` is checked against the
committed static snapshot fixture (tests/fixtures/eng3_concept_bundle/
accepted_input_schema_047fe17.json, schema v5.0, including both frozen
Qwen repositories), never a live worktree, and is explicitly NON-GATING. The
prior ff2a565 (schema v3.0)/2003406 (schema v2.0)/ac9ea40 (schema v1.3)
snapshot/report fixtures are kept alongside as the historical record,
never deleted.

`test_real_runner_document_passes_live_gating_report_if_a_worktree_is_available`
below DOES run the real, live `run_gating_report_with_eng3` subprocess --
but only if a checked-out `eng3/concept-bundle` worktree is present on
this machine at `D:/devcache/wt/concept-bundle` (skipped, not failed,
otherwise, since that path is this specific development machine's, not
portable). Neither ff2a565 nor 3aff107 is an ancestor of this branch,
confirmed via `git merge-base --is-ancestor` in both directions for both
commits. Getting this to pass at 2003406 required fixing `producer_
schema_declaration()`'s `causal_validation.selection_records`/
`generation_manifests` blocks (the consumer's own field-flattening
reconciler reads "keys"/"required"/"reference_required" as structurally
distinct keys, not inferred from a nested named sub-object); ff2a565's
schema 3.0 bump required no further shape change beyond the version bump
itself. 3aff107 (schema v3.0 -> v5.0) DOES require further shape change,
implemented here: `generation_manifests.manifest_required` gains
`dose_grid`/`causal_dose_grid_path`/`_version`/`_sha256`, and the root
gains the conditional `suppress_disposition` object -- see this module's
own new test section below.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_evidence_document as ed  # noqa: E402

FROZEN_COMMIT = "880b48a7f50b8c716e64956b915857dd1fcde350"
FROZEN_SHA = "b0b23cf1502dae53f88905ee7393b7e67f8b05f84f3251d26a6c506480a9531f"
ENG3_WORKTREE = Path("D:/devcache/wt/concept-bundle")


def _eng3_worktree_clean() -> bool:
    """The eng3 worktree is a SHARED working directory another party
    commits to directly and sometimes edits in place, uncommitted, mid-
    refactor -- a dirty worktree is a snapshot of in-progress work, not a
    ratified consumer, so this test skips rather than gating on it."""
    if not ENG3_WORKTREE.is_dir():
        return False
    result = subprocess.run(["git", "status", "--porcelain"], cwd=ENG3_WORKTREE, capture_output=True, text=True)
    return result.returncode == 0 and not result.stdout.strip()


_SAMPLE_BINDING_DIR = Path(tempfile.mkdtemp(prefix="evidence_doc_binding_"))
(_SAMPLE_BINDING_DIR / "generation_manifest_amplify.json").write_text(
    json.dumps({"synthetic": "test fixture, not a real run"}), encoding="utf-8"
)
(_SAMPLE_BINDING_DIR / "selection_record_amplify.json").write_text(
    json.dumps({"synthetic": "test fixture, not a real run"}), encoding="utf-8"
)


def _sample_generation_binding(head: str) -> tuple[dict, dict]:
    generation_manifests = {
        "amplify": ed.build_manifest_reference(
            _SAMPLE_BINDING_DIR / "generation_manifest_amplify.json", computed_at_commit=head,
        ),
        "suppress": None,
    }
    selection_records = {
        "amplify": ed.build_selection_record_reference(
            _SAMPLE_BINDING_DIR / "selection_record_amplify.json",
            selection_commit=head, confirmation_judging_commit=head,
        ),
        "suppress": None,
    }
    return generation_manifests, selection_records


def _sample_document(head: str = "0" * 40, **overrides) -> dict:
    generation_manifests, selection_records = _sample_generation_binding(head)
    kwargs = dict(
        generation_manifests=generation_manifests, selection_records=selection_records,
        run_id="r-test-0001", code_commit=head, entrypoint="test", host="test-host",
        created_at="2026-08-13T00:00:00Z",
        model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
        sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="deadbeef" * 5,
        sae_id="resid_post_all/layer_29_width_16k_l0_big", layer=29,
        release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big",
        params_sha256=None,
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
        judge_model="claude-sonnet-4-5-20250929", judge_rubric_version="1.0", judge_prompt_version="lodestar-steering-v1",
        dose_response={
            "amplify": {"computed_at_commit": head,
                        "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "test"}],
                        "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                        "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
        },
        configuration_name="primary", configuration_completeness="COMPLETE",
        configuration_model_n_layers=48, configuration_grid_cells_expected=1, configuration_grid_cells_recorded=1,
        suppress_disposition=ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=None),
    )
    kwargs.update(overrides)
    return ed.assemble_discovery_document(**kwargs)


def test_assemble_discovery_document_emits_all_fourteen_root_fields():
    document = _sample_document()
    # suppress_disposition is a schema-5.0 CONDITIONAL root field -- present
    # here because the sample document's suppress direction is null.
    assert set(document) == set(ed.ROOT_REQUIRED_FIELDS) | {ed.SUPPRESS_DISPOSITION_FIELD}


def test_assemble_discovery_document_rejects_a_noop_judge_model():
    import pytest

    with pytest.raises(ValueError, match="no-op judge identity"):
        _sample_document(judge_model="none")


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


def test_producer_schema_declaration_declares_all_fourteen_root_fields():
    declared = set(ed.producer_schema_declaration()["objects"]["<root>"]["required"])
    assert declared == set(ed.ROOT_REQUIRED_FIELDS)


def test_reconcile_against_static_snapshot_is_marked_non_gating():
    document = _sample_document()
    result = ed.reconcile_against_static_snapshot(REPO_ROOT, document)
    assert result["gating"] is False


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


# ---------------------------------------------------------------------------
# A COMPLETE document built from the REAL runner's own gate dataclasses
# (GateABResult/GateCResult, translated by the real _gate_entries_from_grid_ab_c)
# and identity v1.3's real pinned revision/params-expected-hash/layer_selection
# requirement for the layer-29 departure from Engineer 3's ruled layer-31
# mechanical target -- this is what proved `submission_may_proceed: true`
# against the live ac9ea40 gating-report (see the closing report).
# ---------------------------------------------------------------------------


def _real_runner_document(head: str = "0" * 40) -> dict:
    gate_ab = [asdict(d.GateABResult(
        concept_id="cheese", locale="en", family="f1", feature_index=3,
        separation_auroc=0.95, gate_a_passed=True, fire_rate=0.8,
        activation_floor_fraction=0.3, gate_b_passed=True,
    ))]
    gate_c = [asdict(d.GateCResult(
        concept_id="cheese", locale="en", family="f1", feature_index=3,
        near_miss_auroc=0.9, gate_c_passed=True,
    ))]
    gates = ed._gate_entries_from_grid_ab_c(gate_ab, gate_c)
    generation_manifests, selection_records = _sample_generation_binding(head)
    return ed.assemble_discovery_document(
        generation_manifests=generation_manifests, selection_records=selection_records,
        run_id="r-realdoc-0001", code_commit=head, entrypoint="scripts.final_pairing.final_pairing_concept_discovery",
        host="test-host", created_at="2026-08-13T00:00:00Z",
        model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
        sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="4c419f1ba0be8b7754d4151d4f26c23b92a9029e",
        sae_id="resid_post_all/layer_29_width_16k_l0_big", layer=29,
        release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big",
        params_sha256=d.PRIMARY_CONFIGURATION.gemma_params_expected_sha256,
        layer_selection={
            "selected_by": "scientific_config_identity.json v1.3.0 (commit 5a5175d)",
            "rationale": "Layer 31 was job 407008's mechanical/engineering-only acceptance input, carrying "
                         "no ratified concept meaning; the scientific PRIMARY configuration is layer 29, "
                         "matched to Qwen by transformer depth fraction, frozen at 0fcd51d and unchanged "
                         "through v1.3.0.",
            "recorded_in": "protocols/final_pairing/v1/scientific_config_identity.json#configurations.PRIMARY",
        },
        concept_id="cheese", hypothesis_source="real-runner document for cheese",
        search_scope="fake-backend end-to-end verification, no GPU available in this environment", candidate_index=0,
        engineering_index_rediscovery_note=None,
        feature_certificate={
            "feature_index": 3, "concept_id": "cheese", "specificity": 0.9, "sensitivity": 0.85,
            "cross_lingual_firing": 0.8, "selectivity": 0.88, "probe": {"auc": 0.91},
            "verdict": "green", "verdict_basis": "schema-conformance construction from real dataclasses",
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
        paraphrase_families=[{"family_id": "f1", "prompts": ["p1", "p2"]}],
        causal_validation_computed_at_commit=head, causal_validation_positions="all",
        gates=gates,
        spot_read=None,
        judge_model="claude-sonnet-4-5-20250929", judge_rubric_version="1.0", judge_prompt_version="lodestar-steering-v1",
        dose_response={
            "amplify": {"computed_at_commit": head,
                        "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "test"}],
                        "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                        "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
        },
        configuration_name="primary", configuration_completeness="PARTIAL",
        configuration_model_n_layers=48, configuration_grid_cells_expected=28, configuration_grid_cells_recorded=1,
        suppress_disposition=ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=None),
    )


def test_real_runner_document_passes_offline_reconciliation():
    document = _real_runner_document()
    result = ed.reconcile_against_static_snapshot(REPO_ROOT, document)
    assert result["compatible"] is True


@pytest.mark.skipif(
    not _eng3_worktree_clean(),
    reason=f"no CLEAN eng3/concept-bundle worktree at {ENG3_WORKTREE} (missing, or has uncommitted in-progress edits)",
)
def test_real_runner_document_passes_live_gating_report_if_a_worktree_is_available(tmp_path):
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    document = _real_runner_document(head=head)
    doc_path = tmp_path / "document.json"
    schema_path = tmp_path / "producer_schema.json"
    doc_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    schema_path.write_text(json.dumps(ed.producer_schema_declaration(), indent=2), encoding="utf-8")
    result = ed.run_gating_report_with_eng3(
        producer_schema_path=schema_path, producer_output_path=doc_path, eng3_worktree=ENG3_WORKTREE,
    )
    assert result["exit_code"] == 0, result
    assert result["submission_may_proceed"] is True, result


# ---------------------------------------------------------------------------
# build_discovery_document_from_production_run: a COMPLETE document built
# from real provenance dicts (the exact shape Backend.provenance["model"]/
# ["sae"] returns) and real generation-manifest/selection-record FILE PATHS
# -- never a test/synthetic assembler that hand-types every leaf value.
# ---------------------------------------------------------------------------


def _production_run_kwargs(**overrides) -> dict:
    kwargs = dict(
        run_id="r-prod-0001", code_commit="0" * 40, entrypoint="scripts.final_pairing.final_pairing_one_allocation_generation",
        host="test-host", created_at="2026-08-13T00:00:00Z",
        model_id="google/gemma-3-12b-it", sae_repo_id="google/gemma-scope-2-12b-it",
        model_provenance={"revision": "deadbeef" * 5, "revision_verification": "pinned"},
        sae_provenance={
            "revision": "4c419f1ba0be8b7754d4151d4f26c23b92a9029e",
            "release": "gemma-scope-2-12b-it-res-all", "loader_sae_id": "layer_29_width_16k_l0_big",
            "scientific_sae_id": "resid_post_all/layer_29_width_16k_l0_big",
            "params_sha256": "1" * 64,
        },
        layer=29, layer_selection=None,
        concept_id="cheese", hypothesis_source="real production run for cheese", search_scope="fake backend, no GPU here",
        candidate_index=0, engineering_index_rediscovery_note=None,
        feature_certificate={
            "feature_index": 3, "concept_id": "cheese", "specificity": 0.9, "sensitivity": 0.85,
            "cross_lingual_firing": 0.8, "selectivity": 0.88, "probe": {"auc": 0.91},
            "verdict": "green", "verdict_basis": "test",
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
        paraphrase_families=[{"family_id": "f1", "prompts": ["p1", "p2"]}],
        causal_validation_computed_at_commit="0" * 40, causal_validation_positions="all",
        gates=[{"gate": "G-D", "status": "pass", "direction": "amplify", "evidence": "test"}],
        spot_read=None,
        judge_model="claude-sonnet-4-5-20250929", judge_rubric_version="1.0", judge_prompt_version="lodestar-steering-v1",
        dose_response={
            "amplify": {"computed_at_commit": "0" * 40,
                        "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "test"}],
                        "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                        "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
        },
        configuration_name="primary", configuration_completeness="COMPLETE",
        configuration_model_n_layers=48, configuration_grid_cells_expected=1, configuration_grid_cells_recorded=1,
        generation_manifest_paths={"amplify": _SAMPLE_BINDING_DIR / "generation_manifest_amplify.json", "suppress": None},
        generation_manifest_commits={"amplify": "0" * 40, "suppress": None},
        selection_record_paths={"amplify": _SAMPLE_BINDING_DIR / "selection_record_amplify.json", "suppress": None},
        selection_commits={"amplify": "0" * 40, "suppress": None},
        confirmation_judging_commits={"amplify": "0" * 40, "suppress": None},
        suppress_disposition=ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=None),
    )
    kwargs.update(overrides)
    return kwargs


def test_build_discovery_document_from_production_run_reads_identity_from_real_provenance():
    document = ed.build_discovery_document_from_production_run(**_production_run_kwargs())
    assert set(document) == set(ed.ROOT_REQUIRED_FIELDS) | {ed.SUPPRESS_DISPOSITION_FIELD}
    assert document["pairing"]["model_revision"] == "deadbeef" * 5
    assert document["pairing"]["sae_repo_revision"] == "4c419f1ba0be8b7754d4151d4f26c23b92a9029e"
    assert document["pairing"]["release"] == "gemma-scope-2-12b-it-res-all"
    assert document["pairing"]["loader_sae_id"] == "layer_29_width_16k_l0_big"
    assert document["pairing"]["sae_id"] == "resid_post_all/layer_29_width_16k_l0_big"
    assert document["pairing"]["params_sha256"] == "1" * 64


def test_build_discovery_document_from_production_run_hashes_the_real_manifest_and_selection_files():
    import hashlib

    document = ed.build_discovery_document_from_production_run(**_production_run_kwargs())
    manifest_ref = document["generation_manifests"]["amplify"]
    expected_hash = hashlib.sha256((_SAMPLE_BINDING_DIR / "generation_manifest_amplify.json").read_bytes()).hexdigest()
    assert manifest_ref["source_sha256"] == "sha256:" + expected_hash
    assert document["generation_manifests"]["suppress"] is None
    selection_ref = document["causal_validation"]["selection_records"]["amplify"]
    expected_selection_hash = hashlib.sha256((_SAMPLE_BINDING_DIR / "selection_record_amplify.json").read_bytes()).hexdigest()
    assert selection_ref["source_sha256"] == "sha256:" + expected_selection_hash


def test_build_discovery_document_from_production_run_refuses_missing_qwen_identity():
    """Immutable Qwen provenance may never be guessed or written empty."""
    qwen_sae_provenance = {
        "revision": "4c419f1ba0be8b7754d4151d4f26c23b92a9029e", "sae_family": "L0_100", "sparsity_k": 100,
    }
    with pytest.raises(ValueError, match="authoritative immutable identity"):
        ed.build_discovery_document_from_production_run(
            **_production_run_kwargs(
                model_id="Qwen/Qwen3.5-27B", sae_repo_id="Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100",
                sae_provenance=qwen_sae_provenance, layer=38,
            )
        )


# ---------------------------------------------------------------------------
# generation_manifests / selection_records binding (protocol 40061b6).
# ---------------------------------------------------------------------------


def test_build_manifest_reference_measures_the_hash_from_real_bytes():
    path = _SAMPLE_BINDING_DIR / "generation_manifest_amplify.json"
    ref = ed.build_manifest_reference(path, computed_at_commit="a" * 40)
    import hashlib

    assert ref["source_sha256"] == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert ref["computed_at_commit"] == "a" * 40
    assert ref["protocol_path"] == "protocols/final_pairing/v1/one_allocation_dose_generation.json"


def test_build_selection_record_reference_measures_the_hash_from_real_bytes():
    path = _SAMPLE_BINDING_DIR / "selection_record_amplify.json"
    ref = ed.build_selection_record_reference(path, selection_commit="a" * 40, confirmation_judging_commit="b" * 40)
    import hashlib

    assert ref["source_sha256"] == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert ref["selection_commit"] == "a" * 40 and ref["confirmation_judging_commit"] == "b" * 40


def test_assemble_discovery_document_refuses_both_directions_null_manifests():
    with pytest.raises(ValueError, match="both amplify and suppress null"):
        _sample_document(generation_manifests={"amplify": None, "suppress": None})


def test_assemble_discovery_document_refuses_manifest_nullity_mismatched_with_directions():
    generation_manifests, _ = _sample_generation_binding("0" * 40)
    # amplify is published (directions["amplify"] is not None) but its manifest is null -- mismatch.
    with pytest.raises(ValueError, match="nullity"):
        _sample_document(generation_manifests={"amplify": None, "suppress": generation_manifests["amplify"]})


def test_assemble_discovery_document_refuses_selection_record_nullity_mismatched_with_manifest():
    _generation_manifests, selection_records = _sample_generation_binding("0" * 40)
    with pytest.raises(ValueError, match="nullity"):
        _sample_document(selection_records={"amplify": None, "suppress": selection_records["amplify"]})


# ---------------------------------------------------------------------------
# schema 5.0 (commit 3aff107): suppress_disposition -- required iff
# calibration.directions.suppress is null, prohibited iff it is not, closed
# to {reason, ablation_cleared_ge}, NEVER a gate.
# ---------------------------------------------------------------------------


def test_static_snapshot_points_at_the_current_schema_5_0_consumer():
    assert ed.STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT == "047fe17e8f771ddc790b1f8369e9dea113d3a513"
    assert ed.DISCOVERY_SCHEMA_VERSION == "5.0"


def test_build_suppress_disposition_not_attempted_requires_a_null_ablation_cleared_ge():
    disposition = ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=None)
    assert disposition == {"reason": "NOT_ATTEMPTED", "ablation_cleared_ge": None}


def test_build_suppress_disposition_not_attempted_rejects_a_non_null_ablation_cleared_ge():
    with pytest.raises(ValueError, match="must be None when reason is NOT_ATTEMPTED"):
        ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=False)


@pytest.mark.parametrize("reason", ["NO_DOSE_CLEARED", "INSUFFICIENT_CLAMP_DOSES"])
def test_build_suppress_disposition_other_reasons_require_a_literal_bool(reason):
    with pytest.raises(ValueError, match="must be a literal bool"):
        ed.build_suppress_disposition(reason=reason, ablation_cleared_ge=None)
    disposition = ed.build_suppress_disposition(reason=reason, ablation_cleared_ge=True)
    assert disposition == {"reason": reason, "ablation_cleared_ge": True}


def test_build_suppress_disposition_rejects_an_unknown_reason():
    with pytest.raises(ValueError, match="reason must be one of"):
        ed.build_suppress_disposition(reason="MAYBE_LATER", ablation_cleared_ge=None)


def test_assemble_discovery_document_requires_suppress_disposition_when_suppress_is_null():
    with pytest.raises(ValueError, match="suppress_disposition is required"):
        _sample_document(suppress_disposition=None)


def test_assemble_discovery_document_prohibits_suppress_disposition_when_suppress_is_published():
    directions = {
        "amplify": ed.build_direction_block(
            operation="clamp", feature_indices=[3], unit="corpus_max_multiple",
            unit_source="background corpus max activation", strengths={"low": 0.5, "medium": 1.0, "high": 2.0},
        ),
        "suppress": ed.build_direction_block(operation="ablate", feature_indices=[3]),
    }
    generation_manifests, selection_records = _sample_generation_binding("0" * 40)
    generation_manifests["suppress"] = generation_manifests["amplify"]
    selection_records["suppress"] = selection_records["amplify"]
    with pytest.raises(ValueError, match="PROHIBITED"):
        _sample_document(
            directions=directions, generation_manifests=generation_manifests, selection_records=selection_records,
            suppress_disposition=ed.build_suppress_disposition(reason="NOT_ATTEMPTED", ablation_cleared_ge=None),
        )


def test_validate_suppress_disposition_refuses_an_unknown_field():
    with pytest.raises(ValueError, match="unknown"):
        ed._validate_suppress_disposition({"reason": "NOT_ATTEMPTED", "ablation_cleared_ge": None, "extra": 1})


def test_validate_suppress_disposition_refuses_a_missing_field():
    with pytest.raises(ValueError, match="missing"):
        ed._validate_suppress_disposition({"reason": "NOT_ATTEMPTED"})


def test_validate_no_ge_gate_when_suppress_null_refuses_a_ge_gate():
    directions = {"amplify": {"operation": "clamp"}, "suppress": None}
    gates = [{"gate": "G-D", "status": "pass", "direction": "amplify", "evidence": "test"},
             {"gate": "G-E", "status": "pass", "direction": "suppress", "evidence": "test"}]
    with pytest.raises(ValueError, match="G-E entry while calibration"):
        ed._validate_no_ge_gate_when_suppress_null(directions, gates)


def test_validate_no_ge_gate_when_suppress_null_allows_a_ge_gate_when_suppress_is_published():
    directions = {"amplify": None, "suppress": {"operation": "clamp"}}
    gates = [{"gate": "G-E", "status": "pass", "direction": "suppress", "evidence": "test"}]
    ed._validate_no_ge_gate_when_suppress_null(directions, gates)  # must not raise


def test_producer_schema_declaration_root_conditional_names_suppress_disposition():
    declared = ed.producer_schema_declaration()["objects"]["<root>"]
    assert declared["conditional"] == ["suppress_disposition"]
    assert "suppress_disposition" in ed.producer_schema_declaration()["objects"]
