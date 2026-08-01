"""§5 SS10 RunCard lifecycle (ED-6), pulled forward into WP2.

`new_run_card(stage, config_path) -> RunCardHandle` / `.finalize(status,
outputs, exit_code)` is the frozen entry point. Lifecycle: the handle holds
a *draft outside the registry* (a scratch file under the OS temp dir, for
crash forensics only -- never a registry artifact, never schema-validated);
`finalize()` performs the single `registry.put()` of the completed,
immutable card. Ground Rule 4's "even on failure" means callers finalize
from a `finally:` block with `status="failed"` on the unhandled-exception
path; a job killed too abruptly to reach `finally` simply leaves no card --
an absent card honestly means the run never completed as a recorded fact.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from interplab.core import envelope, hashing
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT, RegistryError
from interplab.registry.registry import put as registry_put

_ENTRYPOINT_BY_STAGE = {
    "sync": "interplab.jobs.sync_registry",
}


def _entrypoint_for_stage(stage: str) -> str:
    return _ENTRYPOINT_BY_STAGE.get(stage, f"interplab.jobs.{stage}")


def _detect_code_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _detect_host() -> str:
    if os.environ.get("SLURM_JOB_ID") or os.environ.get("CC_CLUSTER"):
        return "tamia"
    return "local"


def _generate_run_id() -> str:
    now = datetime.now(UTC)
    suffix = secrets.token_hex(2)
    return f"r{now:%Y%m%d}-{now:%H%M}-{suffix}"


def _draft_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "interplab_run_card_drafts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_ref_for_path(config_path: Path, *, repo_root: Path) -> str:
    candidate_roots: list[Path] = []
    for candidate in (repo_root.resolve(), REPO_ROOT.resolve()):
        if candidate not in candidate_roots:
            candidate_roots.append(candidate)
    for candidate_root in candidate_roots:
        if config_path == candidate_root or candidate_root in config_path.parents:
            return f"local:{config_path.relative_to(candidate_root).as_posix()}"
    raise ValueError(f"config path {config_path} is not under repo roots {candidate_roots}")


class RunCardHandle:
    def __init__(
        self,
        *,
        run_id: str,
        stage: str,
        config_hash: str,
        config_ref: str,
        inputs: list[dict],
        created_by: dict,
        draft_path: Path,
        registry_root: Path,
    ):
        self.run_id = run_id
        self.created_by = created_by
        self._stage = stage
        self._config_hash = config_hash
        self._config_ref = config_ref
        self._inputs = inputs
        self._draft_path = draft_path
        self._registry_root = registry_root
        self._finalized = False

    def finalize(
        self,
        status: str,
        outputs: list[dict],
        exit_code: int,
        *,
        outcome_line: str = "",
        slurm: dict | None = None,
        log_section: int | None = None,
        environment: dict | None = None,
    ) -> dict:
        """The single `put()` of the completed, immutable card. Idempotent
        guard: a handle can only be finalized once."""
        if self._finalized:
            raise RegistryError(f"RunCardHandle for run_id {self.run_id!r} already finalized")
        self._finalized = True

        payload: dict = {
            "run_id": self.run_id,
            "stage": self._stage,
            "config_hash": self._config_hash,
            "config_ref": self._config_ref,
            "inputs": self._inputs,
            "outputs": outputs,
            "status": status,
            "exit_code": exit_code,
            "outcome_line": outcome_line[:200],
            "slurm": slurm,
            "log_section": log_section,
        }
        if environment is not None:
            payload["environment"] = environment

        artifact = envelope.dump(
            artifact_type="run_card",
            schema_version=1,
            created_by=self.created_by,
            subject=list(self._inputs),
            payload=payload,
        )
        registry_put(artifact, registry_root=self._registry_root)

        if self._draft_path.exists():
            self._draft_path.unlink()

        return artifact


def new_run_card(
    stage: str,
    config_path: str | Path,
    *,
    inputs: list[dict] | None = None,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
    entrypoint: str | None = None,
) -> RunCardHandle:
    config_path = Path(config_path).resolve()
    repo_root = Path(repo_root).resolve()
    run_id = _generate_run_id()
    config_hash = hashing.hash_file(config_path)
    config_ref = _config_ref_for_path(config_path, repo_root=repo_root)
    created_by = {
        "run_id": run_id,
        "code_commit": _detect_code_commit(),
        "entrypoint": entrypoint or _entrypoint_for_stage(stage),
        "host": _detect_host(),
    }
    resolved_inputs = list(inputs) if inputs is not None else []

    draft_path = _draft_dir() / f"{run_id}.json"
    draft = {
        "run_id": run_id,
        "stage": stage,
        "config_hash": config_hash,
        "config_ref": config_ref,
        "inputs": resolved_inputs,
        "started_at": envelope.utcnow_iso(),
    }
    draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")

    return RunCardHandle(
        run_id=run_id,
        stage=stage,
        config_hash=config_hash,
        config_ref=config_ref,
        inputs=resolved_inputs,
        created_by=created_by,
        draft_path=draft_path,
        registry_root=registry_root,
    )
