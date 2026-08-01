"""§8.2 test_schema_validate: every schema in schemas/ compiles; every
registry file validates against its declared version."""

from pathlib import Path

import pytest

from interplab.core import envelope
from interplab.core._schema_registry import SCHEMAS_ROOT, schema_compiles
from interplab.registry.registry import REGISTRY_ROOT


def _all_schema_files() -> list[Path]:
    return sorted(SCHEMAS_ROOT.rglob("*.schema.json"))


@pytest.mark.parametrize(
    "schema_path", _all_schema_files(), ids=lambda p: str(p.relative_to(SCHEMAS_ROOT)).replace("\\", "/")
)
def test_every_schema_compiles(schema_path):
    schema_compiles(schema_path)


def test_expected_a1_a12_schema_files_present():
    expected = {
        "corpus_manifest/v1.schema.json",
        "concept_battery/v1.schema.json",
        "census_report/v1.schema.json",
        "store_manifest/v1.schema.json",
        "sae_checkpoint/v1.schema.json",
        "sae_certificate/v1.schema.json",
        "characterization_manifest/v1.schema.json",
        "feature_certificate/v1.schema.json",
        "intervention_result/v1.schema.json",
        "run_card/v1.schema.json",
        "claim_report/v1.schema.json",
        "eval_compat_map/v1.schema.json",
        "environment_acquisition_manifest/v1.schema.json",
        "environment_install_manifest/v1.schema.json",
    }
    # Scoped to the §4 artifact-type schemas -- schemas/configs/*.schema.json
    # (job config schemas, landing one per job's own work package) are a
    # different category, covered by test_every_schema_compiles above but
    # not by this A1-A12 inventory check.
    present = {
        str(p.relative_to(SCHEMAS_ROOT)).replace("\\", "/")
        for p in _all_schema_files()
        if p.relative_to(SCHEMAS_ROOT).parts[0] != "configs"
    }
    assert present == expected


def test_expected_config_schema_files_present():
    expected = {
        "configs/certify_v1.schema.json",
        "configs/sync_registry_v1.schema.json",
        "configs/backfill_checkpoint_v1.schema.json",
        "configs/census_v1.schema.json",
        "configs/characterize_v1.schema.json",
        "configs/judge_v1.schema.json",
        "configs/store_qa_v1.schema.json",
        "configs/validate_v1.schema.json",
        "configs/report_v1.schema.json",
        "configs/steer_v1.schema.json",
    }
    present = {
        str(p.relative_to(SCHEMAS_ROOT)).replace("\\", "/")
        for p in _all_schema_files()
        if p.relative_to(SCHEMAS_ROOT).parts[0] == "configs"
    }
    assert present == expected


def test_every_registry_file_validates_against_declared_version():
    for path in sorted(REGISTRY_ROOT.rglob("*.json")):
        envelope.load(path)  # raises on hash mismatch or schema violation
