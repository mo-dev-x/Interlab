"""SS9 chain assembly (TRUNK): §5.SS9's ED-14/ED-15/ED-16 algorithm against
synthetic registry trees (`tests/fixtures/synthetic_chains/builder.py`).
Covers every `chain[].status` value plus the multi-anchor-divergence and
missing-eval_compat_map contract-violation paths.
"""

from __future__ import annotations

import pytest

from interplab.core.errors import ContractViolationError
from interplab.reports import chain as chain_mod
from tests.fixtures.synthetic_chains import builder


def _status_by_link(resolution: chain_mod.ChainResolution) -> dict[str, str]:
    return {row.link: row.status for row in resolution.rows}


def test_full_green_chain_is_certified(tmp_path):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)

    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "CERTIFIED"
    assert all(row.status == "ok" for row in resolution.rows)
    statuses = _status_by_link(resolution)
    assert set(statuses) == {
        "intervention_result", "feature_certificate", "sae_checkpoint", "sae_certificate",
        "characterization_manifest", "store_manifest", "corpus_manifest",
    }
    assert len(resolution.anchor_artifacts) == 1
    assert resolution.anchor_artifacts[0]["self_hash"] == built["intervention_result"]["self_hash"]


def test_missing_anchor_is_missing_not_an_error(tmp_path):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    claim_spec["anchor"]["content_hashes"] = ["sha256:" + "9" * 64]

    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "DRAFT — UNCERTIFIED CHAIN"
    anchor_row = resolution.rows[0]
    assert anchor_row.status == "missing"
    assert anchor_row.note is not None
    assert resolution.anchor_artifacts == [None]


def test_missing_required_link_when_role_unreachable(tmp_path):
    """Break the chain by pointing the anchor at a checkpoint with no
    feature_certificate subject ref -- feature_certificate becomes
    unreachable via subject_ref."""
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_certificate=None)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "does zorbium-9 respond to steering?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
        ],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "DRAFT — UNCERTIFIED CHAIN"
    fc_row = next(r for r in resolution.rows if r.link == "feature_certificate")
    assert fc_row.status == "missing"
    assert fc_row.note is not None


def test_red_verdict_propagates_as_red_verdict_status(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    certificate = builder.build_sae_certificate(tmp_path, checkpoint, verdict="red")
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(tmp_path, checkpoint, index)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_cert)
    compat_map = builder.build_eval_compat_map(tmp_path)
    del certificate

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
            {"artifact_type": "sae_checkpoint", "subject_role": "sae_checkpoint", "via": "subject_ref", "min_schema_version": 1},
            {"artifact_type": "sae_certificate", "subject_role": "sae_checkpoint", "via": "subject_of", "min_schema_version": 1},
        ],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "DRAFT — UNCERTIFIED CHAIN"
    cert_row = next(r for r in resolution.rows if r.link == "sae_certificate")
    assert cert_row.status == "red_verdict"


def test_require_instruments_missing_is_insufficient_evidence(tmp_path):
    built = builder.build_full_green_chain(tmp_path, feature_verdict_basis=["specificity", "selectivity", "probe"])
    claim_spec = builder.full_chain_claim_spec(built, require_instruments=["sensitivity"])

    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "DRAFT — UNCERTIFIED CHAIN"
    fc_row = next(r for r in resolution.rows if r.link == "feature_certificate")
    assert fc_row.status == "insufficient_evidence"
    assert "sensitivity" in fc_row.note


def test_require_instruments_satisfied_stays_ok(tmp_path):
    built = builder.build_full_green_chain(tmp_path, feature_verdict_basis=["specificity", "sensitivity", "selectivity", "probe"])
    claim_spec = builder.full_chain_claim_spec(built, require_instruments=["sensitivity"])

    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    fc_row = next(r for r in resolution.rows if r.link == "feature_certificate")
    assert fc_row.status == "ok"


def test_claim_grade_missing_control_arm_is_insufficient_evidence(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(tmp_path, checkpoint, index)
    arms = [a for a in builder._DEFAULT_ARMS if a != "random_direction"]
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_cert, arms=arms)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.rows[0].status == "insufficient_evidence"
    assert "control arms" in resolution.rows[0].note


def test_claim_grade_unshuffled_is_insufficient_evidence(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(tmp_path, checkpoint, index)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_cert, shuffled=False)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.rows[0].status == "insufficient_evidence"
    assert "shuffled" in resolution.rows[0].note


def test_claim_grade_no_feature_certificate_ref_is_insufficient_evidence(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_certificate=None)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.rows[0].status == "insufficient_evidence"
    assert "feature_certificate" in resolution.rows[0].note


def test_eval_incompatible_judge_tuple_not_in_any_class(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(
        tmp_path, checkpoint, index,
        specificity_judge={"model": "unknown-judge", "rubric_version": "v9", "prompt_version": "v9"},
    )
    intervention = builder.build_intervention_result(
        tmp_path, checkpoint, feature_cert,
        lodestar_judge={"model": "lodestar-stub", "rubric_version": "stub-v1"},
        per_prompt_scores=[{"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.5}],
    )
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
        ],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    fc_row = next(r for r in resolution.rows if r.link == "feature_certificate")
    assert fc_row.status == "eval_incompatible"


def test_ambiguous_subject_of_picks_newest_and_notes_it(tmp_path):
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    builder.build_sae_certificate(tmp_path, checkpoint, verdict="red", created_at="2026-01-01T00:00:00Z")
    newest = builder.build_sae_certificate(tmp_path, checkpoint, verdict="green", created_at="2026-06-01T00:00:00Z")
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(tmp_path, checkpoint, index)
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_cert)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "sae_checkpoint", "subject_role": "sae_checkpoint", "via": "subject_ref", "min_schema_version": 1},
            {"artifact_type": "sae_certificate", "subject_role": "sae_checkpoint", "via": "subject_of", "min_schema_version": 1},
        ],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    cert_row = next(r for r in resolution.rows if r.link == "sae_certificate")
    assert cert_row.artifact_hash == newest["self_hash"]
    assert cert_row.status == "ok"
    assert "ambiguous" in cert_row.note


def test_multi_anchor_divergence_raises_contract_violation(tmp_path):
    built_a = builder.build_full_green_chain(tmp_path)
    # A second, independent checkpoint tree -> a second intervention_result
    # anchor whose upstream resolves to *different* artifacts than built_a's.
    corpus_b = builder.build_corpus_manifest(tmp_path, name="other-corpus")
    store_b = builder.build_store_manifest(tmp_path, corpus_b)
    checkpoint_b = builder.build_sae_checkpoint(tmp_path, store_b)
    index_b = builder.build_characterization_manifest(tmp_path, checkpoint_b)
    feature_cert_b = builder.build_feature_certificate(tmp_path, checkpoint_b, index_b)
    intervention_b = builder.build_intervention_result(tmp_path, checkpoint_b, feature_cert_b)

    claim_spec = builder.full_chain_claim_spec(built_a)
    claim_spec["anchor"]["content_hashes"].append(intervention_b["self_hash"])

    with pytest.raises(ContractViolationError, match="diverge"):
        chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)


def test_multiple_identical_anchors_resolve_consistently(tmp_path):
    built = builder.build_full_green_chain(tmp_path)
    checkpoint = built["sae_checkpoint"]
    feature_cert = built["feature_certificate"]
    intervention_2 = builder.build_intervention_result(
        tmp_path, checkpoint, feature_cert,
        lodestar_judge={"model": "none", "rubric_version": "none"},
        per_prompt_scores=[{"prompt_id": "p9", "arm": "steered", "scale": 3.0, "score": 0.7}],
    )
    claim_spec = builder.full_chain_claim_spec(built)
    claim_spec["anchor"]["content_hashes"].append(intervention_2["self_hash"])

    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    assert resolution.stamp == "CERTIFIED"
    assert len(resolution.anchor_artifacts) == 2
    assert sum(1 for r in resolution.rows if r.link == "intervention_result") == 2


def test_missing_eval_compat_map_version_raises_contract_violation(tmp_path):
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    claim_spec["eval_compat_version"] = 999

    with pytest.raises(ContractViolationError, match="eval_compat_map"):
        chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)


def test_duplicate_required_link_artifact_type_raises_contract_violation(tmp_path):
    """Compliance revision, Finding 1: the schema can't express
    element-uniqueness on required_links[].artifact_type, so assemble_chain
    enforces "at most one required link per artifact_type" itself, exit-3,
    same tier as ED-14's anchor-divergence check."""
    built = builder.build_full_green_chain(tmp_path)
    claim_spec = builder.full_chain_claim_spec(built)
    claim_spec["required_links"].append(dict(claim_spec["required_links"][0]))  # duplicate artifact_type

    with pytest.raises(ContractViolationError, match="feature_certificate"):
        chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)


def test_lone_unclassed_judge_tuple_is_eval_incompatible(tmp_path):
    """Compliance revision, Finding 2: the compat pass must run whenever
    >=1 judge-bearing row exists (not only when >=2), so a single
    certificate carrying a judge tuple absent from every class is caught
    rather than defaulting to CERTIFIED."""
    corpus = builder.build_corpus_manifest(tmp_path)
    store = builder.build_store_manifest(tmp_path, corpus)
    checkpoint = builder.build_sae_checkpoint(tmp_path, store)
    index = builder.build_characterization_manifest(tmp_path, checkpoint)
    feature_cert = builder.build_feature_certificate(
        tmp_path, checkpoint, index,
        specificity_judge={"model": "totally-unknown-judge", "rubric_version": "v9", "prompt_version": "v9"},
    )
    # lodestar_judge omitted -> lodestar stays None -> the anchor is not
    # judge-bearing, so feature_certificate is the *only* judge-bearing row.
    intervention = builder.build_intervention_result(tmp_path, checkpoint, feature_cert)
    compat_map = builder.build_eval_compat_map(tmp_path)

    claim_spec = {
        "question": "?",
        "anchor": {"artifact_type": "intervention_result", "content_hashes": [intervention["self_hash"]]},
        "required_links": [
            {"artifact_type": "feature_certificate", "subject_role": "feature_certificate", "via": "subject_ref", "min_schema_version": 1},
        ],
        "eval_compat_version": compat_map["payload"]["version"],
    }
    resolution = chain_mod.assemble_chain(claim_spec, registry_root=tmp_path)

    fc_row = next(r for r in resolution.rows if r.link == "feature_certificate")
    assert fc_row.status == "eval_incompatible"
    assert resolution.stamp == "DRAFT — UNCERTIFIED CHAIN"


def test_gate_checks_stale_schema_reference_style():
    """Unit-level: every schema in this repo currently pins schema_version
    to a single const, so stale_schema can't be exercised end-to-end yet
    (D3: recalibration is what eventually bumps a version). Tests the
    helper directly against a hand-built artifact dict instead."""
    artifact = {"schema_version": 1, "payload": {}}
    status, note = chain_mod._gate_checks(artifact, min_schema_version=2, require_instruments=None)
    assert status == "stale_schema"
    assert "2" in note
