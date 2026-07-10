"""interplab.jobs.sync_registry (SS10, §3.3) -- pulls cluster-outbox
artifacts into the local registry/ tree.

Minimal, authorized scope only (ED-6): this job operates on a local
filesystem path standing in for `$SCRATCH/interplab/outbox/`. How those
bytes arrive at that path (rsync/scp/mount) is out of scope here -- this
job only copies-and-verifies-and-empties, exactly as §3.3 specifies.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from interplab.core import configs, envelope, hashing
from interplab.core._schema_registry import SchemaValidationError
from interplab.core.envelope import EnvelopeHashMismatchError
from interplab.core.errors import ContractViolationError
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card


def run(
    config_path: str | Path, *, registry_root: Path = REGISTRY_ROOT, repo_root: Path = REPO_ROOT
) -> int:
    """Validates config, opens a RunCard, syncs the outbox, finalizes the
    RunCard from `finally`, and returns the process exit code (§6.2)."""
    config = configs.load_and_validate(config_path, "sync_registry")
    outbox_dir = Path(config["outbox_dir"])

    handle = new_run_card("sync", config_path, registry_root=registry_root, repo_root=repo_root)
    outputs: list[dict] = []
    status = "failed"
    exit_code = 4
    outcome_line = "unhandled error"

    try:
        if not outbox_dir.is_dir():
            raise ContractViolationError(f"outbox_dir does not exist or is not a directory: {outbox_dir}")

        synced = 0
        for path in sorted(outbox_dir.glob("*.json")):
            try:
                artifact = envelope.load(path)
            except (EnvelopeHashMismatchError, SchemaValidationError, ValidationError) as e:
                raise ContractViolationError(f"invalid artifact in outbox at {path.name}: {e}") from e

            content_hash = registry_put(artifact, registry_root=registry_root)
            hash12 = hashing.short_hash(content_hash)
            outputs.append(
                {
                    "content_hash": content_hash,
                    "location": f"local:registry/{artifact['artifact_type']}/{hash12}.json",
                    "role": artifact["artifact_type"],
                }
            )
            path.unlink()
            synced += 1

        status, exit_code = "completed", 0
        outcome_line = f"synced {synced} artifact(s) from {outbox_dir}"
    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
