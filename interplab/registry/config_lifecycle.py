"""Shared readable-config lifecycle for job entry points.

Every job still validates its config before heavy work. The special case
handled here is narrower: if the config file is readable but malformed,
non-mapping, or schema-invalid, the attempt must still finalize exactly one
failed RunCard (A10) with exit code 3 before returning.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import yaml

from interplab.core import configs
from interplab.core._schema_registry import SchemaValidationError
from interplab.core.environment_bundle import (
    EnvironmentBundleError,
    certification_environment_inputs,
)
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.run_card import RunCardHandle, new_run_card

_READABLE_INVALID_CONFIG_ERRORS = (yaml.YAMLError, SchemaValidationError, ValueError)
_CERTIFICATION_LANE_STAGES = frozenset({"certify", "characterize", "validate", "steer"})


class PreparedJobRunFailed(RuntimeError):
    """`prepare_job_run()` already finalized the required failed RunCard."""

    def __init__(self, exit_code: int):
        super().__init__(f"job preparation failed with exit code {exit_code}")
        self.exit_code = exit_code


def _compact(text: str) -> str:
    return " ".join(text.split())


def _invalid_config_outcome(error: Exception) -> str:
    if isinstance(error, SchemaValidationError) and error.errors:
        detail = error.errors[0]
        if len(error.errors) > 1:
            detail = f"{detail} (+{len(error.errors) - 1} more)"
    else:
        detail = str(error)
    return f"invalid config: {_compact(detail)}"


def _environment_failure_outcome(error: Exception) -> str:
    return f"environment evidence invalid: {_compact(str(error))}"


def prepare_job_run(
    *,
    stage: str,
    job_name: str,
    config_path: str | Path,
    build_inputs: Callable[[dict], list[dict]] | None = None,
    build_environment: Callable[[], dict] | None = None,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
    entrypoint: str | None = None,
) -> tuple[dict, RunCardHandle] | None:
    """Load a job config and open its normal RunCard.

    Returns `(config, handle)` for a valid config. For a readable invalid
    config, finalizes exactly one failed RunCard and returns `None`. Missing
    or unreadable paths intentionally propagate unchanged.
    """

    try:
        config = configs.load_and_validate(config_path, job_name)
    except _READABLE_INVALID_CONFIG_ERRORS as error:
        environment = build_environment() if build_environment is not None else None
        handle = new_run_card(
            stage,
            config_path,
            inputs=[],
            registry_root=registry_root,
            repo_root=repo_root,
            entrypoint=entrypoint,
        )
        handle.finalize(
            "failed",
            [],
            3,
            outcome_line=_invalid_config_outcome(error),
            environment=environment,
        )
        return None

    inputs = build_inputs(config) if build_inputs is not None else []
    if stage in _CERTIFICATION_LANE_STAGES:
        try:
            cert_lane_inputs = certification_environment_inputs(
                stage=stage,
                config=config,
                config_path=config_path,
                repo_root=repo_root,
            )
        except EnvironmentBundleError as error:
            environment = build_environment() if build_environment is not None else None
            handle = new_run_card(
                stage,
                config_path,
                inputs=inputs,
                registry_root=registry_root,
                repo_root=repo_root,
                entrypoint=entrypoint,
            )
            handle.finalize(
                "failed",
                [],
                4,
                outcome_line=_environment_failure_outcome(error),
                environment=environment,
            )
            raise PreparedJobRunFailed(4) from error
        inputs.extend(cert_lane_inputs)
    handle = new_run_card(
        stage,
        config_path,
        inputs=inputs,
        registry_root=registry_root,
        repo_root=repo_root,
        entrypoint=entrypoint,
    )
    return config, handle
