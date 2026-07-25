"""interplab.core.environment (ED-1 §1.1, ED-32, ED-33) -- resolves the
producing environment for the A10 `environment` RunCard field, and enforces
ED-32/ED-33's SAE-stack baseline for the certification lane (SS4/SS5/SS6/SS7).

ED-33 revised the baseline from sae-lens 3.x to sae-lens 6.x: verified T0.2
metadata showed all four P1 checkpoints were trained under sae-lens 6.44.2,
not 3.23.0 as ED-19/ED-32 had inherited and never checked -- confirmed
decisive by cfg.json's 6.x-format schema (ED-27's identity-bearing artifact)
loading faithfully under 6.44.2 and failing structurally under 3.23.0.
`check_sae_stack_baseline` gates ONLY `sae_lens`'s major version --
deliberately: ED-32's assertion clause names only `sae-lens`, so
`transformers`/`transformer_lens` are recorded but never independently
version-gated here.
"""

from __future__ import annotations

import os
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import torch

from interplab.core.errors import EnvironmentBaselineError
from interplab.core.hashing import hash_file
from interplab.core.uris import REPO_ROOT

SAE_STACK_BASELINE_MAJOR = 6
"""ED-32/ED-33: the supported SAE-stack baseline is the sae-lens 6.x era
(pinned 6.44.2 in pyproject.toml) -- fixed by the P1 checkpoints' real
training provenance, not chosen. ED-33 revised this from major 3 (an
inherited, never-verified premise) after verified T0.2 metadata and a
direct empirical load test showed the checkpoints were genuinely trained
under 6.44.2. A resolved sae-lens major version other than this is
unsanctioned environment drift (ED-32 item 3), never a signal to relax
the pin."""

_SAE_STACK_DIST_NAMES = {
    "sae_lens": "sae-lens",
    "transformers": "transformers",
    "transformer_lens": "transformer-lens",
}


def detect_profile() -> str:
    """ED-1: 'cluster' under SLURM/the Alliance environment, 'local'
    otherwise -- the same signal `registry.run_card._detect_host()` uses
    for `host`, duplicated rather than imported (both live in `core`, so
    Ground Rule 2 permits the import, but `_detect_host` is a private
    helper of a different module; the two-line check is cheap enough that
    duplicating it is simpler than promoting it to a shared surface for
    one caller)."""
    if os.environ.get("SLURM_JOB_ID") or os.environ.get("CC_CLUSTER"):
        return "cluster"
    return "local"


def _resolved_lock_hash(repo_root: Path) -> str | None:
    lock_path = repo_root / "uv.lock"
    return hash_file(lock_path) if lock_path.is_file() else None


def detect_environment(*, repo_root: Path = REPO_ROOT) -> dict:
    """The ED-1 baseline `environment` fields (`profile`/`python`/`torch`/
    `lock_hash`), common to any job that chooses to record them."""
    return {
        "profile": detect_profile(),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "torch": torch.__version__,
        "lock_hash": _resolved_lock_hash(repo_root),
    }


def resolve_sae_stack_versions() -> dict:
    """The three SAE-stack libraries ED-32 requires named on every
    certification-lane run card. `None` per-field if a package is somehow
    not installed at all -- never guessed."""
    resolved = {}
    for field, dist_name in _SAE_STACK_DIST_NAMES.items():
        try:
            resolved[field] = _pkg_version(dist_name)
        except PackageNotFoundError:
            resolved[field] = None
    return resolved


def check_sae_stack_baseline(sae_stack_versions: dict) -> None:
    """ED-32 fail-closed enforcement: the resolved `sae_lens` major version
    MUST equal `SAE_STACK_BASELINE_MAJOR`, or the certification-lane job
    MUST refuse to run (§6.2 exit code 4 -- an environment failure, not a
    missing/invalid input artifact, so `ContractViolationError`/exit 3
    would name the wrong problem). Raises `EnvironmentBaselineError`,
    never a bare exception -- ED-32: a fail-closed refusal is a designed
    guarantee, not an unexpected failure, and must not wear the same type.
    """
    resolved = sae_stack_versions["sae_lens"]
    if resolved is None:
        raise EnvironmentBaselineError(
            "sae-lens is not installed in this environment -- ED-32/ED-33 require the "
            f"{SAE_STACK_BASELINE_MAJOR}.x baseline (pinned 6.44.2); rebuild the environment from "
            "the sanctioned pyproject/uv.lock flow (slurm/setup_env.sh), never install ad hoc"
        )
    major = int(resolved.split(".")[0])
    if major != SAE_STACK_BASELINE_MAJOR:
        raise EnvironmentBaselineError(
            f"sae-lens major version mismatch (ED-32/ED-33): resolved {resolved}, baseline requires "
            f"{SAE_STACK_BASELINE_MAJOR}.x (pinned 6.44.2) -- the P1 checkpoints under certification "
            f"were trained under 6.44.2 (ED-33: verified against real T0.2 metadata and a direct "
            f"empirical load test, superseding ED-32's inherited 3.23.0 premise); a different major "
            f"version decodes the same weights as a different function (ED-27's logic pushed one "
            f"level out). This is unsanctioned environment drift, not a signal to relax the pin -- "
            f"rebuild the environment from the sanctioned pyproject/uv.lock flow (slurm/setup_env.sh). "
            f"If the pinned stack genuinely cannot be built here, stop and escalate to the researcher "
            f"(ED-19 §2) -- a silent jump to a different version is never the fallback."
        )


def build_certification_environment(*, repo_root: Path = REPO_ROOT) -> dict:
    """The full A10 `environment` payload for a certification-lane job
    (SS4/SS5/SS6/SS7): ED-1's base fields plus ED-32's mandatory SAE-stack
    versions. Does NOT itself enforce the baseline -- call
    `check_sae_stack_baseline` separately, so a caller can finalize a
    *failed* run card carrying this same (offending) environment before
    the exception propagates. A refusal that records why is worth more
    than one that just fails.
    """
    env = detect_environment(repo_root=repo_root)
    env.update(resolve_sae_stack_versions())
    return env
