"""Job config loading + schema validation (§6.1: every job validates its
config against `schemas/configs/<job>_v1.schema.json` before any heavy
work -- the job-338944 rule: a typo'd YAML must fail at submit time, not 11
hours into a 12-hour SLURM allocation).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from interplab.core._schema_registry import config_schema_path
from interplab.core._schema_registry import validate as validate_against_schema


def load_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}"
        )
    return data


def load_and_validate(path: str | Path, job_name: str) -> dict:
    """Load a job config YAML and validate it against that job's schema.

    Raises `SchemaNotFoundError` (interplab.core._schema_registry) if the
    job has no published config schema yet -- every job's schema lands with
    that job's own work package (§9), not with WP0.
    """
    config = load_yaml(path)
    schema_path = config_schema_path(job_name)
    validate_against_schema(config, schema_path)
    return config
