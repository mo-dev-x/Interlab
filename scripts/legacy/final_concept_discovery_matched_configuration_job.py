"""Primary-then-conditional-backup sequencing for the two predeclared,
matched Qwen/Gemma concept-discovery configurations (`final_pairing_
concept_discovery.PRIMARY_CONFIGURATION` / `BACKUP_CONFIGURATION`).

Reuses `final_concept_discovery_dual_gpu_job.DualGpuOrchestrator` for BOTH
the primary and (if triggered) the backup run -- this file does not
duplicate the concurrent-launch/aggregation logic, only the SEQUENCING
around it: run primary to completion, persist whatever trigger inputs the
caller supplies, and launch backup ONLY if the caller's own
`--run-backup` boolean says so.

CORRECTION: an earlier version of this docstring said the backup trigger's
Boolean rule had "not yet [been] returned." It has: it is frozen at
`protocols/final_pairing/v1/backup_trigger.json` (commit 125b1d3) --
`RUN_BACKUP = primary_complete AND (primary_shared_gabc_count < 3)`,
`FAIL_RUN = NOT primary_complete` -- and `final_pairing_concept_discovery.
evaluate_backup_trigger` implements exactly that formula. What this file
still does NOT do is compute that formula's own INPUTS:
`primary_shared_gabc_count` requires a full 14-concept x 2-pairing x
3-gate x 3-family x 2-locale grid with a per-feature G-A/B/C conjunction
(`feature_survives_gabc`) that no script in this repository assembles yet
(`final_pairing_concept_discovery.py` discovers one concept per invocation
and has no G-C implementation at all). Until that aggregation exists,
`--run-backup` stays a required, externally-decided argument -- whoever
(or whatever script) assembles the grid should call
`evaluate_backup_trigger(primary_complete=..., primary_shared_gabc_count=...)`
and pass ITS `.run_backup` result in here, rather than re-deriving the
formula. This file still invents neither the rule (now known) nor its
inputs (still not assembled).

Because primary and backup lanes run as separate subprocesses launched
sequentially (never concurrently -- backup is only ever launched after
`wait_all()` returns for primary), primary's CUDA context and loaded
model/SAE weights are already released by the time backup launches: this
falls out of process-boundary isolation, not anything this file has to
manage explicitly.

Never combines features from different layers or SAE families into one
bundle: this file never reads or touches either configuration's discovered
feature/bundle content at all (see `final_concept_discovery_dual_gpu_job`'s
own "never write canonical evidence" invariant) -- each configuration's
lanes are separate `final_pairing_concept_discovery.py` invocations against
a single backend each; there is no code path anywhere in this job that
could mix content across configurations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_concept_discovery_dual_gpu_job as dual_gpu  # noqa: E402
import final_pairing_concept_discovery as discovery  # noqa: E402

SCHEMA_VERSION = 1


class MatchedConfigurationError(ValueError):
    """Raised before any process is launched -- a config collision between
    primary and backup, or a missing/invalid trigger decision."""


def _all_lane_paths(lanes: list[dual_gpu.LaneSpec]) -> dict[Path, str]:
    seen: dict[Path, str] = {}
    for lane in lanes:
        for kind, path in (
            ("out_dir", lane.out_dir), ("state_dir", lane.state_dir),
            ("tmp_dir", lane.tmp_dir), ("log_path", lane.log_path),
        ):
            seen[Path(path).resolve()] = f"{lane.name}:{kind}"
    return seen


def validate_primary_backup_paths_disjoint(
    primary_lanes: list[dual_gpu.LaneSpec], backup_lanes: list[dual_gpu.LaneSpec]
) -> None:
    """Primary results are immutable and must never be overwritten -- this
    check runs BEFORE backup is launched (indeed before primary is even
    launched, since both lane lists are known upfront), not after."""
    primary_paths = _all_lane_paths(primary_lanes)
    backup_paths = _all_lane_paths(backup_lanes)
    collisions = set(primary_paths) & set(backup_paths)
    if collisions:
        detail = ", ".join(f"{p} ({primary_paths[p]} vs {backup_paths[p]})" for p in sorted(collisions))
        raise MatchedConfigurationError(
            f"primary and backup paths must never collide -- refusing to run either: {detail}"
        )


def load_trigger_inputs(path: str | Path) -> dict:
    """Loaded and persisted verbatim -- never interpreted, never used to
    compute the boolean itself. Whatever quantities the caller's own
    evaluation of the Architect's rule considered go here, under whatever
    names that evaluation used; this file does not know or assume what
    they are."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_matched_configuration_job(
    *,
    primary_lanes: list[dual_gpu.LaneSpec],
    backup_lanes: list[dual_gpu.LaneSpec],
    trigger_inputs: dict,
    run_backup: bool,
    job_result_path: Path,
    orchestrator_factory=dual_gpu.DualGpuOrchestrator,
) -> dict:
    validate_primary_backup_paths_disjoint(primary_lanes, backup_lanes)

    primary_orchestrator = orchestrator_factory(primary_lanes)
    primary_orchestrator.launch_all()
    primary_result = primary_orchestrator.wait_all()

    backup_result = None
    if run_backup:
        backup_orchestrator = orchestrator_factory(backup_lanes)
        backup_orchestrator.launch_all()
        backup_result = backup_orchestrator.wait_all()

    for lane in primary_result["lanes"]:
        lane["configuration"] = discovery.PRIMARY_CONFIGURATION.name
    if backup_result is not None:
        for lane in backup_result["lanes"]:
            lane["configuration"] = discovery.BACKUP_CONFIGURATION.name

    if primary_result["status"] != "complete_pass":
        overall_status = "failure" if primary_result["status"] == "failure" else "partial_execution"
    elif run_backup and backup_result is not None and backup_result["status"] != "complete_pass":
        overall_status = "failure" if backup_result["status"] == "failure" else "partial_execution"
    else:
        overall_status = "complete_pass"

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": overall_status,
        "overall_exit_code": 0 if overall_status == "complete_pass" else 1,
        "selected_configuration": discovery.BACKUP_CONFIGURATION.name if run_backup else discovery.PRIMARY_CONFIGURATION.name,
        "run_backup": run_backup,
        "trigger_inputs": trigger_inputs,
        "primary_configuration": {
            "name": discovery.PRIMARY_CONFIGURATION.name,
            "qwen_layer": discovery.PRIMARY_CONFIGURATION.qwen_layer,
            "qwen_sae_family": discovery.PRIMARY_CONFIGURATION.qwen_sae_family,
            "qwen_sparsity": discovery.PRIMARY_CONFIGURATION.qwen_sparsity,
            "gemma_layer": discovery.PRIMARY_CONFIGURATION.gemma_layer,
        },
        "backup_configuration": {
            "name": discovery.BACKUP_CONFIGURATION.name,
            "qwen_layer": discovery.BACKUP_CONFIGURATION.qwen_layer,
            "qwen_sae_family": discovery.BACKUP_CONFIGURATION.qwen_sae_family,
            "qwen_sparsity": discovery.BACKUP_CONFIGURATION.qwen_sparsity,
            "gemma_layer": discovery.BACKUP_CONFIGURATION.gemma_layer,
        },
        "primary_result": primary_result,
        "backup_result": backup_result,
    }
    job_result_path.parent.mkdir(parents=True, exist_ok=True)
    job_result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--primary-gemma-config", required=True)
    p.add_argument("--primary-qwen-config", required=True)
    p.add_argument("--backup-gemma-config", required=True)
    p.add_argument("--backup-qwen-config", required=True)
    p.add_argument("--trigger-inputs-json", required=True, help="Whatever record the Architect's rule was evaluated against -- persisted verbatim, never computed here.")
    p.add_argument("--run-backup", required=True, choices=["true", "false"], help="The externally-decided result of applying the Architect's (not yet returned) backup-trigger rule. Never computed by this file.")
    p.add_argument("--job-result-path", required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    primary_lanes = [
        dual_gpu.load_lane_spec("gemma", args.primary_gemma_config),
        dual_gpu.load_lane_spec("qwen", args.primary_qwen_config),
    ]
    backup_lanes = [
        dual_gpu.load_lane_spec("gemma", args.backup_gemma_config),
        dual_gpu.load_lane_spec("qwen", args.backup_qwen_config),
    ]
    trigger_inputs = load_trigger_inputs(args.trigger_inputs_json)
    result = run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs=trigger_inputs,
        run_backup=(args.run_backup == "true"), job_result_path=Path(args.job_result_path),
    )
    print(json.dumps({"status": result["status"], "selected_configuration": result["selected_configuration"]}, indent=2))
    return result["overall_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
