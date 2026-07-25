"""§5 SS10 RunCard lifecycle (ED-6): draft outside the registry, single
`put()` at `finalize()`, idempotency guard, finalize-in-`finally` pattern."""

import json

import pytest

from interplab.core import envelope
from interplab.registry import RegistryError, get, new_run_card


@pytest.fixture
def config_file(tmp_path):
    cfg = tmp_path / "certify.yaml"
    cfg.write_text("checkpoint_hash: sha256:" + "a" * 64 + "\n", encoding="utf-8")
    return cfg


def test_run_id_matches_pattern(tmp_path, config_file):
    handle = new_run_card("certify", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    import re

    assert re.fullmatch(r"r\d{8}-\d{4}-[0-9a-f]{4}", handle.run_id)


def test_draft_written_at_start_and_removed_after_finalize(tmp_path, config_file):
    # "backfill" (not "certify"): this test is about generic draft/finalize
    # lifecycle mechanics, unaffected by ED-32's certification-lane-only
    # `environment` requirement -- a stage outside that lane keeps the test
    # focused on what it actually verifies.
    handle = new_run_card("backfill", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert handle._draft_path.exists()
    draft = json.loads(handle._draft_path.read_text(encoding="utf-8"))
    assert draft["run_id"] == handle.run_id
    assert draft["stage"] == "backfill"

    handle.finalize("completed", outputs=[], exit_code=0)
    assert not handle._draft_path.exists()


def test_draft_is_not_a_registry_artifact(tmp_path, config_file):
    registry_root = tmp_path / "registry"
    new_run_card("certify", config_file, registry_root=registry_root, repo_root=tmp_path)
    # No run_card written until finalize.
    assert not (registry_root / "run_card").exists()


def test_finalize_performs_exactly_one_put(tmp_path, config_file):
    registry_root = tmp_path / "registry"
    handle = new_run_card("backfill", config_file, registry_root=registry_root, repo_root=tmp_path)
    artifact = handle.finalize("completed", outputs=[], exit_code=0, outcome_line="green certificate")

    envelope.load(artifact)  # self-consistent, schema-valid
    fetched = get(artifact["self_hash"], registry_root=registry_root)
    assert fetched == artifact
    assert artifact["payload"]["status"] == "completed"
    assert artifact["payload"]["exit_code"] == 0


def test_finalize_twice_raises(tmp_path, config_file):
    handle = new_run_card("backfill", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    handle.finalize("completed", outputs=[], exit_code=0)
    with pytest.raises(RegistryError):
        handle.finalize("completed", outputs=[], exit_code=0)


def test_finally_pattern_records_failure_on_exception(tmp_path, config_file):
    registry_root = tmp_path / "registry"
    handle = new_run_card("backfill", config_file, registry_root=registry_root, repo_root=tmp_path)

    result = {"status": "failed", "outputs": [], "exit_code": 4, "outcome_line": "unhandled exception"}
    try:
        with pytest.raises(ValueError):
            try:
                raise ValueError("boom")
            finally:
                handle.finalize(**result)
    finally:
        pass

    matches = list((registry_root / "run_card").glob("*.json"))
    assert len(matches) == 1
    card = json.loads(matches[0].read_text(encoding="utf-8"))
    assert card["payload"]["status"] == "failed"
    assert card["payload"]["exit_code"] == 4


def test_outcome_line_truncated_to_200_chars(tmp_path, config_file):
    handle = new_run_card("backfill", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    artifact = handle.finalize("completed", outputs=[], exit_code=0, outcome_line="x" * 500)
    assert len(artifact["payload"]["outcome_line"]) == 200


def test_inputs_become_subject(tmp_path, config_file):
    input_ref = {"content_hash": "sha256:" + "b" * 64, "location": "local:registry/sae_checkpoint/abc.json", "role": "checkpoint"}
    handle = new_run_card(
        "backfill", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path, inputs=[input_ref]
    )
    artifact = handle.finalize("completed", outputs=[], exit_code=0)
    assert artifact["subject"] == [input_ref]
    assert artifact["payload"]["inputs"] == [input_ref]


def test_environment_field_omitted_when_not_supplied(tmp_path, config_file):
    # ED-32 makes `environment` mandatory for the certification-lane stages
    # specifically (certify/characterize/validate/steer) -- "backfill" is
    # not one of them, so omission is still legal there, which is the
    # actual thing this test proves.
    handle = new_run_card("backfill", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    artifact = handle.finalize("completed", outputs=[], exit_code=0)
    assert "environment" not in artifact["payload"]


def test_stage_sync_maps_to_sync_registry_entrypoint(tmp_path, config_file):
    handle = new_run_card("sync", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert handle.created_by["entrypoint"] == "interplab.jobs.sync_registry"


def test_explicit_entrypoint_overrides_stage_derived_default(tmp_path, config_file):
    handle = new_run_card(
        "train", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path,
        entrypoint="interplab.jobs.backfill_checkpoint",
    )
    assert handle.created_by["entrypoint"] == "interplab.jobs.backfill_checkpoint"


_CERTIFICATION_LANE_STAGES = {"certify", "characterize", "validate", "steer"}
_SAMPLE_CERTIFICATION_ENVIRONMENT = {
    "profile": "local", "python": "3.12.0", "torch": "2.4.0", "lock_hash": None,
    "sae_lens": "3.23.0", "transformers": "4.44.0", "transformer_lens": "2.15.4",
}


@pytest.mark.parametrize(
    "stage",
    ["census", "collect", "store_qa", "train", "backfill", "certify", "characterize", "validate", "steer", "judge", "report", "sync"],
)
def test_every_ed11_stage_value_is_schema_valid(tmp_path, config_file, stage):
    """ED-11: the RunCard stage taxonomy names what a run actually did --
    store_qa and backfill are now official stages, distinct from train.
    ED-32: the four certification-lane stages additionally require
    `environment` (with the SAE-stack versions) to be schema-valid."""
    handle = new_run_card(stage, config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    environment = _SAMPLE_CERTIFICATION_ENVIRONMENT if stage in _CERTIFICATION_LANE_STAGES else None
    artifact = handle.finalize("completed", outputs=[], exit_code=0, environment=environment)
    assert artifact["payload"]["stage"] == stage


def test_stage_store_qa_maps_to_store_qa_entrypoint(tmp_path, config_file):
    handle = new_run_card("store_qa", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    assert handle.created_by["entrypoint"] == "interplab.jobs.store_qa"


@pytest.mark.parametrize("stage", sorted(_CERTIFICATION_LANE_STAGES))
def test_certification_lane_stage_without_environment_is_schema_invalid(tmp_path, config_file, stage):
    """ED-32: `environment` is structurally mandatory for the four
    certification-lane stages -- the invariant lives in the schema, not
    just in job code, so a cert-lane run card is impossible to write
    without it regardless of caller."""
    from interplab.core._schema_registry import SchemaValidationError

    handle = new_run_card(stage, config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    with pytest.raises(SchemaValidationError):
        handle.finalize("completed", outputs=[], exit_code=0)


def test_certification_lane_stage_requires_sae_stack_versions_in_environment(tmp_path, config_file):
    """ED-32: `environment` present but missing sae_lens/transformers/
    transformer_lens is still schema-invalid for a cert-lane stage."""
    from interplab.core._schema_registry import SchemaValidationError

    handle = new_run_card("certify", config_file, registry_root=tmp_path / "registry", repo_root=tmp_path)
    incomplete_environment = {"profile": "local", "python": "3.12.0", "torch": "2.4.0", "lock_hash": None}
    with pytest.raises(SchemaValidationError):
        handle.finalize("completed", outputs=[], exit_code=0, environment=incomplete_environment)
