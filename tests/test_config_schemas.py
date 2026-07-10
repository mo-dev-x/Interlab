"""§8.2 test_config_schemas: every job config schema under `schemas/configs/`
rejects a malformed config (the 94%-timeout guard -- infra_architecture.md:
"a typo'd YAML fails at submit time, not 11 hours into a 12-hour SLURM
allocation"). Individual job test files each already exercise this for
their own schema (e.g. test_jobs_steer.py's
test_config_schema_validation_failure_raises); this is the single sweep
that proves the guarantee holds for every job, not just the ones with a
dedicated case.
"""

from __future__ import annotations

import pytest

from interplab.core import configs
from interplab.core._schema_registry import SCHEMAS_ROOT, SchemaValidationError


def _job_names() -> list[str]:
    return sorted(
        p.name.removesuffix("_v1.schema.json") for p in (SCHEMAS_ROOT / "configs").glob("*_v1.schema.json")
    )


@pytest.mark.parametrize("job_name", _job_names())
def test_empty_config_fails_schema_validation(job_name, tmp_path):
    cfg_path = tmp_path / "empty.yaml"
    cfg_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        configs.load_and_validate(cfg_path, job_name)
