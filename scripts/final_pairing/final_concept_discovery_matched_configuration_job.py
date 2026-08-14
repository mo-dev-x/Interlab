"""Primary-then-conditional-backup sequencing for the two predeclared,
matched Qwen/Gemma concept-discovery configurations (`final_pairing_
concept_discovery.PRIMARY_CONFIGURATION` / `BACKUP_CONFIGURATION`).

Reuses `final_concept_discovery_dual_gpu_job.DualGpuOrchestrator` for BOTH
the primary and (if triggered) the backup run -- this file does not
duplicate the concurrent-launch/aggregation logic, only the SEQUENCING
around it: run primary to completion, then decide whether to run backup.

THE BACKUP TRIGGER IS COMPUTED AUTOMATICALLY, NOT SUPPLIED EXTERNALLY.
`protocols/final_pairing/v1/backup_trigger.json` (commit 125b1d3) freezes
`RUN_BACKUP = primary_complete AND (primary_shared_gabc_count < 3)`,
`FAIL_RUN = NOT primary_complete`; `final_pairing_concept_discovery.
evaluate_backup_trigger` implements exactly that formula, and
`final_pairing_concept_discovery.run_concept_grid`/
`compute_primary_completeness_and_shared_count` now assemble the formula's
own inputs (the 14-concept x 2-pairing grid, one G-A/B/C-conjunction
verdict per (concept, pairing) cell). `compute_trigger_from_grid_outputs`
(below) reads the two primary lanes' own `grid.json` outputs -- EXACT,
named paths, never a glob over a parent `concept_discovery/<model>/`
directory -- and calls `evaluate_backup_trigger` for real. The scheduled
entry point (`main`) always uses this automatic path; `run_backup` as an
explicit boolean is a TEST-ONLY override on `run_matched_configuration_job`
(the Python function), impossible to reach through `main`'s own CLI
(`parse_args` below defines no `--run-backup` flag at all).

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
import dataclasses
import functools
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_concept_discovery_dual_gpu_job as dual_gpu  # noqa: E402
import final_pairing_concept_discovery as discovery  # noqa: E402

SCHEMA_VERSION = 1
#: The frozen "1.5x remaining-time" rule: backup is only ATTEMPTED if
#: 1.5 * (primary's own measured elapsed time) fits within however much
#: wall-clock the allocation has left.
BACKUP_TIME_SAFETY_FACTOR = 1.5


class MatchedConfigurationError(ValueError):
    """Raised before any process is launched -- a config collision between
    primary and backup, or a missing/invalid trigger decision."""


@dataclasses.dataclass(frozen=True)
class BackupReadiness:
    attempt: bool
    status: str  # "ready" | "not_attempted_insufficient_time" | "failed_insufficient_vram"
    detail: str


def assert_sufficient_time_for_backup(
    *, job_start_time: float, job_time_limit_seconds: float, primary_elapsed_seconds: float,
    now_fn=None, safety_factor: float = BACKUP_TIME_SAFETY_FACTOR,
) -> BackupReadiness:
    """The frozen 1.5x remaining-time rule. Never raises -- an
    insufficient-time verdict is a legitimate, NOT_ATTEMPTED outcome, not
    a failure; the caller writes that status rather than launching
    backup."""
    import time as _time

    now = (now_fn or _time.time)()
    elapsed_since_start = now - job_start_time
    remaining = job_time_limit_seconds - elapsed_since_start
    required = safety_factor * primary_elapsed_seconds
    if required > remaining:
        return BackupReadiness(
            attempt=False, status="not_attempted_insufficient_time",
            detail=(
                f"backup requires an estimated {required:.0f}s ({safety_factor}x primary's measured "
                f"{primary_elapsed_seconds:.0f}s), but only {remaining:.0f}s remain in the allocation"
            ),
        )
    return BackupReadiness(attempt=True, status="ready", detail=f"{remaining:.0f}s remain, {required:.0f}s required")


class InsufficientVramError(RuntimeError):
    """Raised (never merely logged) when a GPU does not report enough
    free VRAM before backup would launch -- primary's process exiting
    should have released it; a shortfall here is a genuine resource
    failure, not a NOT_ATTEMPTED outcome."""


def assert_sufficient_free_vram(
    gpu_ids: list[str], *, min_free_bytes: int, collect_garbage_fn=None, empty_cache_fn=None, free_vram_fn=None,
) -> dict[str, int]:
    """Releases lingering Python-side references (`gc.collect`), empties
    torch's CUDA caching allocator (`torch.cuda.empty_cache`), then
    queries actual free VRAM per GPU (`torch.cuda.mem_get_info`) and
    asserts every one meets `min_free_bytes`. All three steps are
    injectable seams (real by default) -- no test in this project's
    suite calls the real CUDA functions."""
    import gc as _gc

    (collect_garbage_fn or _gc.collect)()
    if empty_cache_fn is not None:
        empty_cache_fn()
    else:
        import torch

        torch.cuda.empty_cache()

    if free_vram_fn is not None:
        free_bytes = {gid: free_vram_fn(gid) for gid in gpu_ids}
    else:
        import torch

        free_bytes = {}
        for gid in gpu_ids:
            free, _total = torch.cuda.mem_get_info(int(gid))
            free_bytes[gid] = free

    insufficient = {gid: b for gid, b in free_bytes.items() if b < min_free_bytes}
    if insufficient:
        raise InsufficientVramError(
            f"insufficient free VRAM before backup (required >= {min_free_bytes} bytes per GPU): {insufficient}"
        )
    return free_bytes


def check_backup_readiness(
    *, job_start_time: float, job_time_limit_seconds: float, primary_elapsed_seconds: float,
    gpu_ids: list[str], min_free_vram_bytes: int, now_fn=None, collect_garbage_fn=None, empty_cache_fn=None, free_vram_fn=None,
) -> BackupReadiness:
    """The combined time + VRAM gate `run_matched_configuration_job` calls
    right before launching backup (when a `backup_readiness_checker` is
    supplied -- see that function's docstring). Time is checked FIRST
    (cheaper, and a NOT_ATTEMPTED verdict should never depend on having
    already queried GPU memory)."""
    time_readiness = assert_sufficient_time_for_backup(
        job_start_time=job_start_time, job_time_limit_seconds=job_time_limit_seconds,
        primary_elapsed_seconds=primary_elapsed_seconds, now_fn=now_fn,
    )
    if not time_readiness.attempt:
        return time_readiness
    try:
        assert_sufficient_free_vram(
            gpu_ids, min_free_bytes=min_free_vram_bytes, collect_garbage_fn=collect_garbage_fn,
            empty_cache_fn=empty_cache_fn, free_vram_fn=free_vram_fn,
        )
    except InsufficientVramError as exc:
        return BackupReadiness(attempt=False, status="failed_insufficient_vram", detail=str(exc))
    return BackupReadiness(attempt=True, status="ready", detail=time_readiness.detail)


def _lane_elapsed_seconds(dual_gpu_result: dict) -> float:
    """Real, MEASURED elapsed wall time for one dual-GPU lane-group result:
    `max(lane end_time) - min(lane start_time)` across every lane that
    actually attempted -- never a guessed constant. This is the
    `primary_elapsed_seconds` the frozen 1.5x remaining-time backup-
    readiness rule requires; by the time it is computed, `run_backup` is
    only ever True when `primary_result['status'] == 'complete_pass'`, so
    every lane has both timestamps recorded."""
    lanes = dual_gpu_result.get("lanes") or []
    starts = [ln["start_time"] for ln in lanes if ln.get("start_time") is not None]
    ends = [ln["end_time"] for ln in lanes if ln.get("end_time") is not None]
    if not starts or not ends:
        raise ValueError(
            "cannot measure elapsed seconds: no lane in this result recorded both a start_time "
            "and an end_time"
        )
    return max(ends) - min(starts)


def _all_lane_paths(lanes: list[dual_gpu.LaneSpec]) -> dict[Path, str]:
    seen: dict[Path, str] = {}
    for lane in lanes:
        for kind, path in (
            ("out_dir", lane.out_dir), ("state_dir", lane.state_dir),
            ("tmp_dir", lane.tmp_dir), ("log_path", lane.log_path),
        ):
            seen[Path(path).resolve()] = f"{lane.name}:{kind}"
    return seen


def validate_all_lane_paths_disjoint(lane_groups: dict[str, list[dual_gpu.LaneSpec]]) -> None:
    """P0 STOP-LINE correction ('validate all eight grid/generation lane
    paths pairwise'): pairwise path-disjointness across EVERY supplied
    lane group -- up to all eight lanes: primary grid (2) + backup grid
    (2) + primary generation (2) + backup generation (2). Runs BEFORE any
    lane in any group launches. Reports which two groups collided, not
    merely that some collision exists."""
    claims: dict[Path, str] = {}
    for group_name, lanes in lane_groups.items():
        for path, claim in _all_lane_paths(lanes).items():
            full_claim = f"{group_name}:{claim}"
            if path in claims:
                raise MatchedConfigurationError(
                    f"path collision: {full_claim}'s path ({path}) is already claimed by "
                    f"{claims[path]!r} -- refusing to launch any lane."
                )
            claims[path] = full_claim


def validate_primary_backup_paths_disjoint(
    primary_lanes: list[dual_gpu.LaneSpec], backup_lanes: list[dual_gpu.LaneSpec]
) -> None:
    """Primary results are immutable and must never be overwritten -- this
    check runs BEFORE backup is launched (indeed before primary is even
    launched, since both lane lists are known upfront), not after. A
    thin, backward-compatible wrapper over the general `validate_all_
    lane_paths_disjoint` (primary/backup grid lanes only, no generation
    lanes)."""
    validate_all_lane_paths_disjoint({"primary": primary_lanes, "backup": backup_lanes})


def load_trigger_inputs(path: str | Path) -> dict:
    """Loaded and persisted verbatim -- never interpreted, never used to
    compute the boolean itself. Whatever quantities the caller's own
    evaluation of the Architect's rule considered go here, under whatever
    names that evaluation used; this file does not know or assume what
    they are."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


class TriggerResolutionFailed(RuntimeError):
    """Raised when the automatic backup-trigger computation itself cannot
    be trusted -- e.g. `primary_complete=False` (`FAIL_RUN`). This is
    ALWAYS raised before backup is considered; a failed primary must never
    fall through to backup, which would let an infrastructure failure
    masquerade as a scientific finding."""


def compute_trigger_from_grid_outputs(
    *, gemma_grid_path: str | Path, qwen_grid_path: str | Path, concept_ids: list[str],
) -> discovery.BackupTriggerResult:
    """Reads EXACTLY the two named `grid.json` files each primary lane
    wrote to its OWN out_dir (never a glob over a parent
    `concept_discovery/<model>/` directory -- see the 2026-08-13 staging
    facts addendum's collection-safety requirement), computes the real
    `primary_complete`/`primary_shared_gabc_count` from their contents,
    and evaluates the frozen `evaluate_backup_trigger` formula. This is
    the SCIENTIFIC decision input `--run-backup` used to be; this
    function is how the scheduled entry point (`main`, below) now derives
    it automatically instead of requiring an externally-supplied flag."""
    gemma_verdicts = discovery.read_grid_result(gemma_grid_path)
    qwen_verdicts = discovery.read_grid_result(qwen_grid_path)
    complete, shared_count = discovery.compute_primary_completeness_and_shared_count(
        {
            discovery.targets.GEMMA_3_12B_IT_TARGET.name: gemma_verdicts,
            discovery.targets.QWEN_3_5_27B_TARGET.name: qwen_verdicts,
        },
        concept_ids=concept_ids,
    )
    return discovery.evaluate_backup_trigger(
        primary_complete=complete, primary_shared_gabc_count=(shared_count if complete else None),
    )


def run_causal_generation_phase(
    generation_lanes: list[dual_gpu.LaneSpec], *,
    orchestrator_factory=dual_gpu.DualGpuOrchestrator,
    validate_prompt_artifact=dual_gpu.default_prompt_artifact_validator,
    run_preflight=dual_gpu.default_preflight_runner,
    wait_for_ready=None,
    ready_timeout_seconds: float = 1800.0,
    poll_interval_seconds: float = 5.0,
    repo_root: Path = dual_gpu.REPO_ROOT,
) -> dict:
    """Runs the causal-generation lanes (`final_pairing_one_allocation_
    generation.py`'s CLI, one per pairing) through the EXACT same real
    preflight -> prompt-artifact-validation -> staggered-cold-load-
    handshake sequence as a grid lane -- `dual_gpu.run_dual_gpu_job_for_
    lanes`, never a second, weaker launch path. Each generation lane
    reads its OWN pairing's `--grid-path` from DISK (a file the grid
    phase already flushed to disk before this function is ever called);
    this function has no in-memory reference at all to the grid
    subprocess that wrote it, so there is nothing here that could race or
    depend on that subprocess still being alive."""
    return dual_gpu.run_dual_gpu_job_for_lanes(
        generation_lanes, orchestrator_factory=orchestrator_factory, validate_prompt_artifact=validate_prompt_artifact,
        run_preflight=run_preflight, repo_root=repo_root, ready_timeout_seconds=ready_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds, wait_for_ready=wait_for_ready,
    )


def run_matched_configuration_job(
    *,
    primary_lanes: list[dual_gpu.LaneSpec],
    backup_lanes: list[dual_gpu.LaneSpec],
    trigger_inputs: dict,
    job_result_path: Path,
    orchestrator_factory=dual_gpu.DualGpuOrchestrator,
    run_backup: bool | None = None,
    trigger_resolver=None,
    backup_readiness_checker=None,
    validate_prompt_artifact=dual_gpu.default_prompt_artifact_validator,
    run_preflight=dual_gpu.default_preflight_runner,
    wait_for_ready=None,
    ready_timeout_seconds: float = 1800.0,
    poll_interval_seconds: float = 5.0,
    repo_root: Path = dual_gpu.REPO_ROOT,
    primary_generation_lanes: list[dual_gpu.LaneSpec] | None = None,
    backup_generation_lanes: list[dual_gpu.LaneSpec] | None = None,
    required_slurm_job_id: str | None = None,
) -> dict:
    """Runs primary, then EITHER uses the caller-supplied `run_backup`
    (test-only override -- see module docstring; the scheduled entry
    point `main` never passes this) OR, when `run_backup is None`, calls
    `trigger_resolver()` (a zero-argument callable, typically
    `compute_trigger_from_grid_outputs` bound via `functools.partial`)
    AFTER primary completes and uses its `.run_backup` -- raising
    `TriggerResolutionFailed` if `.fail_run` is True (an incomplete
    primary), before backup is ever considered.

    Both primary AND backup launch through `dual_gpu.run_dual_gpu_job_for_
    lanes` -- the SAME real preflight -> prompt-artifact-validation ->
    staggered-cold-load-handshake sequence the standalone dual-GPU job
    uses, never `DualGpuOrchestrator.launch_all()` directly. A primary
    (or backup) that fails this gate before any weights load reports
    `status='failure'` with `lanes: []`, exactly like a lane-level
    failure -- there is no separate, weaker code path here that could
    launch either configuration's lanes concurrently or without having
    first validated the frozen prompt artifact.

    If primary's own gate/lanes did not reach `complete_pass`, the
    backup trigger is never resolved from primary's (possibly nonexistent)
    grid.json -- `run_backup` is forced to `False` and `trigger_result`
    stays `None`; an infrastructure failure must never be read as
    "primary_complete=False" (a SCIENTIFIC verdict) by trying to open a
    grid file that a preflight or validation failure means was never
    written.

    If the trigger says to run backup AND `backup_readiness_checker` is
    supplied (typically `check_backup_readiness` bound via
    `functools.partial` with the job's real time-budget/GPU facts, leaving
    `primary_elapsed_seconds` UNBOUND), it is called ONE more time right
    before backup would launch, as `backup_readiness_checker(primary_
    elapsed_seconds=<real, measured elapsed seconds from primary_result's
    own lane timestamps>)` -- never a guessed constant. A `BackupReadiness`
    with `attempt=False` overrides the trigger's own `run_backup=True` --
    `backup_execution_status` becomes `NOT_ATTEMPTED` (insufficient time)
    rather than launching a backup that cannot complete, or the readiness
    check's own failure is recorded and backup is likewise not launched.
    `backup_readiness_checker` defaults to `None` (no gate) so every
    existing caller/test is unaffected.

    REQUIRED PRODUCTION ORDER (P0 STOP-LINE correction): primary grids ->
    trigger -> conditional matched backup grids -> causal generation.
    NO CAUSAL GENERATION MAY OCCUR BEFORE THE TRIGGER -- both `primary_
    generation_lanes` and `backup_generation_lanes` (if supplied) are
    launched strictly AFTER the trigger has been resolved AND (if
    triggered) the backup grid lanes have themselves been resolved, never
    interleaved with or ahead of that decision. Primary generation still
    depends ONLY on primary's own `grid.json` (unaffected by whether
    backup ran or what it found) and backup generation only on backup's
    own `grid.json` (produced only if backup's grid lanes actually ran and
    reached `complete_pass`); neither phase reads anything from the other
    lane's in-memory process state -- every cross-phase handoff is a file
    already flushed to disk. Passing neither `*_generation_lanes` argument
    (the default) skips the generation phase(s) entirely and reproduces
    the exact prior grid-only behavior.

    A missing (never attempted despite `*_generation_lanes` being
    supplied), failed, or partial generation phase makes the AGGREGATE
    `status` non-`complete_pass` -- a generation-phase problem is never
    silently absorbed by an otherwise-passing grid phase.

    PRIMARY > BACKUP, always: `selected_configuration` is unconditionally
    `discovery.PRIMARY_CONFIGURATION.name` -- backup is replication/
    fallback evidence, reported separately in `backup_result`/`backup_
    generation_result`, and is NEVER promoted to "the selected
    configuration" merely because it happened to run."""
    if run_backup is None and trigger_resolver is None:
        raise ValueError("run_matched_configuration_job requires either run_backup or trigger_resolver")
    # P0 STOP-LINE correction: validate ALL EIGHT grid/generation lane
    # paths pairwise (whichever of the four groups were actually
    # supplied), and, if a SLURM_JOB_ID was required, that every lane's
    # paths are rooted under it -- both BEFORE any lane in any group
    # launches.
    lane_groups: dict[str, list[dual_gpu.LaneSpec]] = {"primary": primary_lanes, "backup": backup_lanes}
    if primary_generation_lanes is not None:
        lane_groups["primary_generation"] = primary_generation_lanes
    if backup_generation_lanes is not None:
        lane_groups["backup_generation"] = backup_generation_lanes
    validate_all_lane_paths_disjoint(lane_groups)
    if required_slurm_job_id is not None:
        for lanes in lane_groups.values():
            dual_gpu.validate_lane_paths_rooted_in_slurm_job_id(lanes, slurm_job_id=required_slurm_job_id)

    primary_result = dual_gpu.run_dual_gpu_job_for_lanes(
        primary_lanes, orchestrator_factory=orchestrator_factory, validate_prompt_artifact=validate_prompt_artifact,
        run_preflight=run_preflight, repo_root=repo_root, ready_timeout_seconds=ready_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds, wait_for_ready=wait_for_ready,
    )

    # TRIGGER RESOLUTION -- strictly BEFORE any causal generation, primary
    # or backup (P0 STOP-LINE correction: "No causal generation may occur
    # before the trigger").
    trigger_result = None
    if run_backup is None:
        if primary_result["status"] != "complete_pass":
            # An infrastructure failure (preflight, prompt-artifact validation, or a lane
            # itself failing) means primary never produced a trustworthy grid.json --
            # resolving the trigger against it would either raise the wrong exception
            # (FileNotFoundError) or read a stale/foreign file. Backup is simply not
            # attempted; this is NOT the same thing as the trigger's own FAIL_RUN.
            run_backup = False
        else:
            trigger_result = trigger_resolver()
            if trigger_result.fail_run:
                raise TriggerResolutionFailed(
                    f"primary_complete=False: the backup-trigger formula cannot be evaluated, and an "
                    f"incomplete primary must never fall through to backup. trigger={trigger_result}"
                )
            run_backup = trigger_result.run_backup

    # CONDITIONAL MATCHED BACKUP GRIDS -- only after the trigger, still
    # strictly before any causal generation.
    backup_result = None
    backup_readiness = None
    backup_execution_status = None
    if run_backup:
        if backup_readiness_checker is not None:
            backup_readiness = backup_readiness_checker(primary_elapsed_seconds=_lane_elapsed_seconds(primary_result))
        if backup_readiness is not None and not backup_readiness.attempt:
            backup_execution_status = "NOT_ATTEMPTED"
        else:
            backup_result = dual_gpu.run_dual_gpu_job_for_lanes(
                backup_lanes, orchestrator_factory=orchestrator_factory, validate_prompt_artifact=validate_prompt_artifact,
                run_preflight=run_preflight, repo_root=repo_root, ready_timeout_seconds=ready_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds, wait_for_ready=wait_for_ready,
            )
            backup_execution_status = "COMPLETE" if backup_result["status"] == "complete_pass" else "PARTIAL"

    # CAUSAL GENERATION -- strictly AFTER the trigger and the (conditional)
    # backup grids above, for BOTH primary and backup.
    primary_generation_result = None
    if primary_generation_lanes is not None:
        if primary_result["status"] == "complete_pass":
            primary_generation_result = run_causal_generation_phase(
                primary_generation_lanes, orchestrator_factory=orchestrator_factory,
                validate_prompt_artifact=validate_prompt_artifact, run_preflight=run_preflight, repo_root=repo_root,
                ready_timeout_seconds=ready_timeout_seconds, poll_interval_seconds=poll_interval_seconds,
                wait_for_ready=wait_for_ready,
            )
        else:
            primary_generation_result = {
                "status": "not_attempted",
                "reason": f"primary grid did not reach complete_pass (status={primary_result['status']!r})",
            }

    backup_generation_result = None
    if backup_generation_lanes is not None:
        if backup_result is not None and backup_result["status"] == "complete_pass":
            backup_generation_result = run_causal_generation_phase(
                backup_generation_lanes, orchestrator_factory=orchestrator_factory,
                validate_prompt_artifact=validate_prompt_artifact, run_preflight=run_preflight,
                repo_root=repo_root, ready_timeout_seconds=ready_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds, wait_for_ready=wait_for_ready,
            )
        else:
            reason = (
                f"backup grid did not reach complete_pass (status={backup_result['status']!r})"
                if backup_result is not None else
                "backup grid was never run (the trigger did not select backup, or the backup "
                "readiness gate declined it)"
            )
            backup_generation_result = {"status": "not_attempted", "reason": reason}

    for lane in primary_result["lanes"]:
        lane["configuration"] = discovery.PRIMARY_CONFIGURATION.name
    if backup_result is not None:
        for lane in backup_result["lanes"]:
            lane["configuration"] = discovery.BACKUP_CONFIGURATION.name

    # A missing (only when the phase was actually requested via *_generation_lanes),
    # failed, or partial generation phase makes the AGGREGATE status non-pass --
    # P0 STOP-LINE correction: a generation-phase problem must never be masked by
    # an otherwise-passing grid phase.
    if primary_result["status"] != "complete_pass":
        overall_status = "failure" if primary_result["status"] == "failure" else "partial_execution"
    elif primary_generation_result is not None and primary_generation_result.get("status") != "complete_pass":
        overall_status = "failure" if primary_generation_result.get("status") == "failure" else "partial_execution"
    elif run_backup and backup_execution_status == "NOT_ATTEMPTED":
        overall_status = "partial_execution"
    elif run_backup and backup_result is not None and backup_result["status"] != "complete_pass":
        overall_status = "failure" if backup_result["status"] == "failure" else "partial_execution"
    elif backup_generation_result is not None and backup_generation_result.get("status") != "complete_pass":
        overall_status = "failure" if backup_generation_result.get("status") == "failure" else "partial_execution"
    else:
        overall_status = "complete_pass"

    result = {
        "schema_version": SCHEMA_VERSION,
        "status": overall_status,
        "overall_exit_code": 0 if overall_status == "complete_pass" else 1,
        # PRIMARY > BACKUP, always: backup is replication/fallback evidence
        # (backup_result/backup_generation_result, reported separately),
        # never promoted to "the selected configuration" merely because it ran.
        "selected_configuration": discovery.PRIMARY_CONFIGURATION.name,
        "run_backup": run_backup,
        "backup_execution_status": backup_execution_status,
        "backup_readiness": None if backup_readiness is None else asdict(backup_readiness),
        "trigger_result": None if trigger_result is None else asdict(trigger_result),
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
        "primary_generation_result": primary_generation_result,
        "backup_result": backup_result,
        "backup_generation_result": backup_generation_result,
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
    p.add_argument("--trigger-inputs-json", required=True, help="Recorded verbatim in the job result for audit; the boolean itself is always computed from --primary-*-grid-path, never from this file.")
    p.add_argument("--primary-gemma-grid-path", required=True, help="The Gemma primary lane's own grid.json (exact path -- never globbed).")
    p.add_argument("--primary-qwen-grid-path", required=True, help="The Qwen primary lane's own grid.json (exact path -- never globbed).")
    p.add_argument("--concept-id", action="append", required=True, dest="concept_ids", help="Repeatable: one --concept-id per concept in the grid (all 14 for a production run).")
    p.add_argument("--job-result-path", required=True)
    p.add_argument("--ready-timeout-seconds", type=float, default=1800.0, help="How long to wait for each configuration's lead lane (Qwen) READY record before failing closed.")
    p.add_argument("--poll-interval-seconds", type=float, default=5.0)
    # P0 STOP-LINE correction: all four generation configs are MANDATORY for
    # the scheduled production entry point -- a production run must never be
    # able to silently skip causal generation for either configuration.
    p.add_argument("--primary-gemma-generation-config", required=True, help="Path to the primary Gemma causal-generation lane's JSON (target_script=final_pairing_one_allocation_generation.py).")
    p.add_argument("--primary-qwen-generation-config", required=True)
    p.add_argument("--backup-gemma-generation-config", required=True, help="Only ACTUALLY LAUNCHED if the trigger runs backup and backup's own grid reaches complete_pass -- still required upfront so the packet never depends on which branch a live run happens to take.")
    p.add_argument("--backup-qwen-generation-config", required=True)
    # P0 STOP-LINE correction: wires the real 1.5x remaining-time and
    # free-VRAM backup-readiness check into main() -- previously the
    # functions existed but nothing in the scheduled entry point called them.
    p.add_argument("--job-start-time-epoch-seconds", type=float, required=True, help="Absolute time.time()-based epoch start of this allocation -- never a duration relative to this process's own start.")
    p.add_argument("--job-time-limit-seconds", type=float, required=True, help="This allocation's total wall-clock time budget.")
    p.add_argument("--gpu-ids", required=True, help="Comma-separated GPU ids to verify have sufficient free VRAM before backup launches (e.g. '0,1').")
    p.add_argument("--min-free-vram-bytes", type=int, required=True, help="Minimum free VRAM required per GPU (after gc.collect/torch.cuda.empty_cache) before backup is allowed to launch.")
    return p.parse_args(argv)


def _load_generation_lanes(gemma_config: str | None, qwen_config: str | None) -> list[dual_gpu.LaneSpec] | None:
    """Both-or-neither: a generation phase needs both lanes' configs to
    run at all. Returns `None` (skip the phase) unless BOTH are
    supplied."""
    if gemma_config is None and qwen_config is None:
        return None
    if gemma_config is None or qwen_config is None:
        raise MatchedConfigurationError(
            "generation lane configs must be supplied for BOTH gemma and qwen together, or neither -- "
            f"got gemma={gemma_config!r} qwen={qwen_config!r}"
        )
    return [dual_gpu.load_lane_spec("gemma", gemma_config), dual_gpu.load_lane_spec("qwen", qwen_config)]


def main(argv: list[str] | None = None) -> int:
    """The scheduled entry point. There is no `--run-backup` flag here --
    the trigger is always computed from the primary lanes' own grid
    outputs via `compute_trigger_from_grid_outputs`, never supplied
    externally. Causal generation for primary (and, if triggered and
    configured, backup) runs for real when the corresponding `--*-
    generation-config` flags are supplied -- this is the real,
    production invocation of `final_pairing_one_allocation_generation.py`,
    not merely exposing its library functions for a caller to wire up
    separately."""
    args = parse_args(argv)
    # P0 STOP-LINE correction ("require SLURM_JOB_ID roots"): main() only
    # ever runs inside a real Slurm allocation -- unlike
    # run_matched_configuration_job (the library function), which stays
    # unaffected for direct callers/tests that supply no SLURM_JOB_ID at all.
    slurm_job_id = os.environ.get("SLURM_JOB_ID")
    if not slurm_job_id:
        raise MatchedConfigurationError(
            "SLURM_JOB_ID is not set -- the scheduled production entry point must run inside a real "
            "Slurm allocation, whose lane paths this job verifies are rooted under."
        )
    primary_lanes = [
        dual_gpu.load_lane_spec("gemma", args.primary_gemma_config),
        dual_gpu.load_lane_spec("qwen", args.primary_qwen_config),
    ]
    backup_lanes = [
        dual_gpu.load_lane_spec("gemma", args.backup_gemma_config),
        dual_gpu.load_lane_spec("qwen", args.backup_qwen_config),
    ]
    primary_generation_lanes = _load_generation_lanes(args.primary_gemma_generation_config, args.primary_qwen_generation_config)
    backup_generation_lanes = _load_generation_lanes(args.backup_gemma_generation_config, args.backup_qwen_generation_config)
    trigger_inputs = load_trigger_inputs(args.trigger_inputs_json)
    trigger_resolver = functools.partial(
        compute_trigger_from_grid_outputs,
        gemma_grid_path=args.primary_gemma_grid_path, qwen_grid_path=args.primary_qwen_grid_path,
        concept_ids=args.concept_ids,
    )
    # The real 1.5x remaining-time and free-VRAM backup-readiness check --
    # primary_elapsed_seconds is left UNBOUND here (supplied by
    # run_matched_configuration_job itself, measured from primary_result's
    # own lane timestamps, never guessed).
    backup_readiness_checker = functools.partial(
        check_backup_readiness,
        job_start_time=args.job_start_time_epoch_seconds, job_time_limit_seconds=args.job_time_limit_seconds,
        gpu_ids=args.gpu_ids.split(","), min_free_vram_bytes=args.min_free_vram_bytes,
    )
    result = run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs=trigger_inputs,
        trigger_resolver=trigger_resolver, backup_readiness_checker=backup_readiness_checker,
        job_result_path=Path(args.job_result_path),
        ready_timeout_seconds=args.ready_timeout_seconds, poll_interval_seconds=args.poll_interval_seconds,
        primary_generation_lanes=primary_generation_lanes, backup_generation_lanes=backup_generation_lanes,
        required_slurm_job_id=slurm_job_id,
    )
    print(json.dumps({"status": result["status"], "selected_configuration": result["selected_configuration"]}, indent=2))
    return result["overall_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
