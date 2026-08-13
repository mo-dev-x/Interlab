"""Dual-GPU Tamia orchestration for concurrent Gemma + Qwen concept
discovery, inside ONE Slurm allocation (one node, 4xH100).

Fixed GPU assignment, never configurable from a lane's own JSON: the Gemma
lane gets `CUDA_VISIBLE_DEVICES=0`, the Qwen lane gets
`CUDA_VISIBLE_DEVICES=1`. GPUs 2-3 are reserved for a separately authored
judge process and are never assigned to either lane by this file -- there
is no code path here that can produce any other CUDA_VISIBLE_DEVICES value
for either lane. Because CUDA_VISIBLE_DEVICES remaps visible devices to
start at index 0 inside the child process, this file also forces
`--device cuda:0` onto BOTH lanes' commands (appended last, so it wins over
anything a lane's own JSON specified) -- each child always addresses its
one assigned physical GPU as cuda:0 from its own point of view.

Scope: process orchestration only. This file launches
`final_pairing_concept_discovery.py` as two independent subprocesses,
monitors them concurrently (one finishing does not block on or terminate
the other), and computes ONE aggregate result from the process-level facts
it observes (commands, PIDs, timestamps, exit codes) -- it never reads,
merges, or reinterprets either lane's own `result.json`, never calls into
`interplab`'s registry/envelope machinery, and never authors a bundle or
canonical evidence artifact. That remains Engineer 3's sealing pipeline's
job, working from each lane's own output directory.

Testability: every method that would otherwise spawn a real subprocess
goes through the injectable `launch` callable (see `default_launch` /
`DualGpuOrchestrator.__init__`). Tests substitute a fake process object
with the same 5-method surface (`pid`, `poll`, `wait`, `terminate`,
`send_signal`) -- no test in this project's suite ever spawns a real
process or loads a real model through this file.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DISCOVERY_SCRIPT = SCRIPT_DIR / "final_pairing_concept_discovery.py"
SCHEMA_VERSION = 1

LANE_NAMES = ("gemma", "qwen")
LANE_GPU_ASSIGNMENT = {"gemma": "0", "qwen": "1"}  # fixed; never read from a lane's JSON
RESERVED_JUDGE_GPUS = ("2", "3")  # documented, never assigned to either lane by this file

# Staggered cold-load order (Gemma preflight addendum, item 6): Qwen loads
# FIRST on GPU 1 and must reach READY before Gemma (GPU 0) begins loading.
STAGGER_LEAD_LANE = "qwen"
STAGGER_FOLLOW_LANE = "gemma"
# Must match final_pairing_targets.QWEN_3_5_27B_TARGET.name /
# GEMMA_3_12B_IT_TARGET.name -- literal here (not imported) to keep this
# module's own import graph light; the READY record's own pairing field
# is written by final_pairing_concept_discovery.write_ready_record from
# the SAME --pairing CLI value final_pairing_targets validates elsewhere.
_LANE_PAIRING = {"gemma": "gemma-3-12b-it", "qwen": "qwen-3.5-27b"}


class LaneConfigError(ValueError):
    """A lane's JSON is malformed, names an unknown lane, or collides with
    the other lane's paths -- always raised before any process is
    launched."""


@dataclass
class LaneSpec:
    name: str
    out_dir: Path
    state_dir: Path
    tmp_dir: Path
    log_path: Path
    argv: list[str]


def load_lane_spec(name: str, config_path: str | Path) -> LaneSpec:
    if name not in LANE_NAMES:
        raise LaneConfigError(f"unknown lane name {name!r}; must be one of {LANE_NAMES}")
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    required = ("out_dir", "state_dir", "tmp_dir", "log_path", "argv")
    missing = [k for k in required if k not in data]
    if missing:
        raise LaneConfigError(f"lane config {config_path!r} is missing required field(s): {missing}")
    if not isinstance(data["argv"], list) or not all(isinstance(x, str) for x in data["argv"]):
        raise LaneConfigError(f"lane config {config_path!r}: 'argv' must be a list of strings")
    return LaneSpec(
        name=name, out_dir=Path(data["out_dir"]), state_dir=Path(data["state_dir"]),
        tmp_dir=Path(data["tmp_dir"]), log_path=Path(data["log_path"]), argv=list(data["argv"]),
    )


def validate_lane_paths_disjoint(lanes: list[LaneSpec]) -> None:
    """Fails BEFORE any process is launched if any two lanes share an
    out_dir/state_dir/tmp_dir/log_path -- a silent overlap could let one
    lane's resumable state, temp files, or logs corrupt the other's."""
    seen: dict[Path, str] = {}
    for lane in lanes:
        for kind, path in (
            ("out_dir", lane.out_dir), ("state_dir", lane.state_dir),
            ("tmp_dir", lane.tmp_dir), ("log_path", lane.log_path),
        ):
            resolved = Path(path).resolve()
            claim = f"{lane.name}:{kind}"
            if resolved in seen:
                raise LaneConfigError(
                    f"path collision: {claim}'s path ({resolved}) is already claimed by "
                    f"{seen[resolved]!r} -- refusing to launch either lane."
                )
            seen[resolved] = claim


def build_lane_command(lane: LaneSpec) -> list[str]:
    """Appends --out-dir/--state-dir/--ready-path (authoritative from the
    LaneSpec, not whatever the JSON's own argv might also contain) and
    --device cuda:0 LAST, so they win over any earlier occurrence in argv
    (argparse takes the last value for a repeated store-action flag)."""
    return [
        sys.executable, str(DISCOVERY_SCRIPT), *lane.argv,
        "--out-dir", str(lane.out_dir), "--state-dir", str(lane.state_dir),
        "--ready-path", str(ready_path_for_lane(lane)),
        "--device", "cuda:0",
    ]


def env_for_lane(lane: LaneSpec, *, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)
    env["CUDA_VISIBLE_DEVICES"] = LANE_GPU_ASSIGNMENT[lane.name]
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    env["TMPDIR"] = str(lane.tmp_dir)
    return env


def ready_path_for_lane(lane: LaneSpec) -> Path:
    """The exact, named READY-record path for one lane -- under its OWN
    state_dir (never a shared or globbed location), so two lanes' READY
    records can never collide or be confused with each other."""
    return Path(lane.state_dir) / "ready.json"


# ---------------------------------------------------------------------------
# Process launch seam -- the ONLY place that touches subprocess/os for real.
# ---------------------------------------------------------------------------


class RealProcessHandle:
    def __init__(self, popen: subprocess.Popen, log_file):
        self._popen = popen
        self._log_file = log_file

    @property
    def pid(self) -> int:
        return self._popen.pid

    def poll(self) -> int | None:
        return self._popen.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self._popen.wait(timeout=timeout)

    def send_signal(self, sig) -> None:
        self._popen.send_signal(sig)

    def terminate(self) -> None:
        self._popen.terminate()

    def kill(self) -> None:
        self._popen.kill()

    def close_log(self) -> None:
        self._log_file.close()


def default_launch(command: list[str], *, env: dict[str, str], cwd: Path, log_path: Path) -> RealProcessHandle:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 -- must outlive this function; closed via close_log()
    popen = subprocess.Popen(command, env=env, cwd=str(cwd), stdout=log_file, stderr=subprocess.STDOUT)
    return RealProcessHandle(popen, log_file)


# ---------------------------------------------------------------------------
# Aggregate result -- process-level facts only, never the lanes' own
# scientific output content.
# ---------------------------------------------------------------------------


@dataclass
class LaneResult:
    name: str
    command: list[str]
    cuda_visible_devices: str
    out_dir: str
    state_dir: str
    log_path: str
    pid: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    exit_code: int | None = None
    attempted: bool = False
    terminated_by_signal: bool = False

    @property
    def passed(self) -> bool:
        return self.attempted and not self.terminated_by_signal and self.exit_code == 0


def aggregate(lanes: list[LaneResult], *, cancelled: bool = False) -> dict:
    if cancelled or any(not lane.attempted or lane.terminated_by_signal for lane in lanes):
        status = "partial_execution"
    elif all(lane.passed for lane in lanes):
        status = "complete_pass"
    else:
        status = "failure"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "overall_exit_code": 0 if status == "complete_pass" else 1,
        "cancelled": cancelled,
        "lanes": [asdict(lane) for lane in lanes],
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class DualGpuOrchestrator:
    def __init__(
        self, lanes: list[LaneSpec], *,
        launch=default_launch, repo_root: Path = REPO_ROOT,
        sleep_fn=time.sleep, time_fn=time.time, signal_module=signal,
    ):
        names = [lane.name for lane in lanes]
        if sorted(names) != sorted(LANE_NAMES):
            raise LaneConfigError(f"expected exactly the lanes {LANE_NAMES}, got {names}")
        validate_lane_paths_disjoint(lanes)
        self.lanes = {lane.name: lane for lane in lanes}
        self._launch = launch
        self._repo_root = repo_root
        self._sleep = sleep_fn
        self._time = time_fn
        self._signal = signal_module
        self._processes: dict[str, object] = {}
        self._results: dict[str, LaneResult] = {}
        self._cancelled = False
        self._previous_handlers: dict[int, object] = {}

    def cuda_visible_devices_for(self, name: str) -> str:
        return LANE_GPU_ASSIGNMENT[name]

    def _launch_one(self, name: str) -> None:
        lane = self.lanes[name]
        command = build_lane_command(lane)
        env = env_for_lane(lane)
        proc = self._launch(command, env=env, cwd=self._repo_root, log_path=lane.log_path)
        self._processes[name] = proc
        self._results[name] = LaneResult(
            name=name, command=command, cuda_visible_devices=env["CUDA_VISIBLE_DEVICES"],
            out_dir=str(lane.out_dir), state_dir=str(lane.state_dir), log_path=str(lane.log_path),
            pid=proc.pid, start_time=self._time(), attempted=True,
        )

    def launch_all(self) -> None:
        for name in self.lanes:
            self._launch_one(name)

    def launch_staggered(self, *, ready_timeout_seconds: float = 1800.0, wait_for_ready=None) -> None:
        """Cold-load handshake: launches ONLY `STAGGER_LEAD_LANE` (Qwen,
        physical GPU 1, visible as cuda:0), waits for its own READY record
        (written by `final_pairing_concept_discovery.write_ready_record`
        after `load_backend()` succeeds) via `wait_for_ready` (defaults to
        the real `final_pairing_concept_discovery.wait_for_ready_record`,
        imported lazily), and only THEN launches `STAGGER_FOLLOW_LANE`
        (Gemma, physical GPU 0). A `ReadyHandshakeFailed` (lead exited
        first, timed out, or wrote a record naming the wrong pairing/
        device) is raised BEFORE the follower is ever launched -- this
        is a failure of the ALLOCATION, not a scientific result, and must
        never be reported as one."""
        if wait_for_ready is None:
            import final_pairing_concept_discovery as discovery

            wait_for_ready = discovery.wait_for_ready_record

        self._launch_one(STAGGER_LEAD_LANE)
        lead_process = self._processes[STAGGER_LEAD_LANE]
        wait_for_ready(
            ready_path_for_lane(self.lanes[STAGGER_LEAD_LANE]),
            expected_pairing=_LANE_PAIRING[STAGGER_LEAD_LANE],
            expected_device="cuda:0",
            process_alive_fn=lambda: lead_process.poll() is None,
            timeout_seconds=ready_timeout_seconds, sleep_fn=self._sleep,
        )
        self._launch_one(STAGGER_FOLLOW_LANE)

    def _install_signal_handlers(self) -> None:
        def _handler(signum, frame):
            self._cancelled = True
            self.terminate_all()

        for sig in (self._signal.SIGTERM, self._signal.SIGINT):
            self._previous_handlers[sig] = self._signal.getsignal(sig)
            self._signal.signal(sig, _handler)

    def _restore_signal_handlers(self) -> None:
        for sig, handler in self._previous_handlers.items():
            self._signal.signal(sig, handler)
        self._previous_handlers = {}

    def terminate_all(self) -> None:
        """Forwards termination to every still-running lane -- called both
        by the signal handler (Slurm cancellation) and directly by tests.
        Never terminates a lane that already exited on its own."""
        for proc in self._processes.values():
            if proc.poll() is None:
                proc.terminate()
        for name, proc in self._processes.items():
            result = self._results[name]
            if result.exit_code is not None:
                continue
            try:
                code = proc.wait(timeout=30)
            except Exception:
                proc.kill()
                code = proc.wait(timeout=30)
            result.exit_code = code
            result.end_time = self._time()
            result.terminated_by_signal = True

    def wait_all(self, *, poll_interval: float = 1.0) -> dict:
        """Polls both lanes independently -- a lane finishing early is
        recorded immediately and does not block on, or terminate, the
        other, which is left running until it finishes or the job is
        cancelled."""
        self._install_signal_handlers()
        try:
            pending = set(self._processes)
            while pending and not self._cancelled:
                for name in list(pending):
                    proc = self._processes[name]
                    code = proc.poll()
                    if code is not None:
                        result = self._results[name]
                        result.exit_code = code
                        result.end_time = self._time()
                        pending.discard(name)
                if pending:
                    self._sleep(poll_interval)
        finally:
            self._restore_signal_handlers()
        return aggregate(list(self._results.values()), cancelled=self._cancelled)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gemma-config", required=True, help="Path to the Gemma lane's JSON (out_dir/state_dir/tmp_dir/log_path/argv).")
    p.add_argument("--qwen-config", required=True, help="Path to the Qwen lane's JSON.")
    p.add_argument("--job-result-path", required=True, help="Where to write the aggregate job_result.json.")
    p.add_argument("--poll-interval-seconds", type=float, default=5.0)
    p.add_argument("--ready-timeout-seconds", type=float, default=1800.0, help="How long to wait for the lead lane's (Qwen) READY record before failing closed.")
    return p.parse_args(argv)


def default_prompt_artifact_validator(repo_root: Path) -> None:
    """Runs the real committed `validate_prompt_sets.py` plus the frozen-
    artifact commit/hash/row-count/dirty checks -- BEFORE either lane
    launches. Imported lazily (not at module scope) so this orchestrator
    stays free of any heavy import at load time; tests inject a fake
    validator here instead of ever calling this function for real."""
    import final_pairing_concept_discovery as discovery

    discovery.run_prompt_set_validator(repo_root)
    discovery.load_frozen_prompt_artifact(repo_root)


PREFLIGHT_SCRIPT = SCRIPT_DIR / "discovery_preflight.py"


class PreflightFailed(RuntimeError):
    """Raised when the standalone preflight did not report a clean pass --
    whether it exited nonzero, printed unparsable output, or printed a
    JSON report whose OWN fields (not just the process exit code) don't
    actually add up to a full pass."""


def default_preflight_runner(repo_root: Path) -> dict:
    """Runs `discovery_preflight.py` as a REAL SUBPROCESS (never imported
    and called in-process for this purpose) and independently
    re-validates its JSON report -- this driver does not trust the
    subprocess's exit code alone, in case the preflight script itself has
    a bug that exits 0 without every case actually having run and passed.
    Raises `PreflightFailed` with the full report on any discrepancy."""
    import subprocess
    import sys as _sys

    proc = subprocess.run(
        [_sys.executable, str(PREFLIGHT_SCRIPT)], cwd=str(repo_root), capture_output=True, text=True,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightFailed(
            f"discovery_preflight.py printed non-JSON output (exit={proc.returncode}): "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        ) from exc

    non_passing = [c for c in report.get("cases", []) if c.get("status") != "pass"]
    problems = []
    if proc.returncode != 0:
        problems.append(f"subprocess exit code {proc.returncode} != 0")
    if report.get("overall") != "pass":
        problems.append(f"report['overall'] = {report.get('overall')!r}, not 'pass'")
    if report.get("executed_cases") != report.get("expected_cases"):
        problems.append(f"executed_cases={report.get('executed_cases')} != expected_cases={report.get('expected_cases')}")
    if non_passing:
        problems.append(f"{len(non_passing)} case(s) did not report 'pass': {[c['name'] for c in non_passing]}")
    if problems:
        raise PreflightFailed(
            "discovery_preflight.py did not report a clean pass (checked independently of its exit "
            f"code): {'; '.join(problems)}. Full report: {json.dumps(report)}"
        )
    return report


def run_dual_gpu_job(
    args: argparse.Namespace, *,
    orchestrator_factory=DualGpuOrchestrator,
    validate_prompt_artifact=default_prompt_artifact_validator,
    run_preflight=default_preflight_runner,
    repo_root: Path = REPO_ROOT,
) -> dict:
    """The standalone preflight (`discovery_preflight.py`) runs FIRST,
    before either lane launches and before either child could load any
    weights -- a preflight failure stops both lanes with `lanes: []`,
    exactly like a prompt-artifact validation failure. Only after the
    preflight reports a clean pass does the (cheaper, narrower) frozen-
    prompt-artifact check run, then both lanes launch via the staggered
    cold-load handshake (`DualGpuOrchestrator.launch_staggered` -- Qwen
    first, Gemma only after Qwen's own READY record).

    A hash mismatch, validation failure, or row-count mismatch in the
    frozen prompt artifact stops BOTH lanes -- this check runs once, here,
    before either lane is launched, rather than being duplicated (and
    therefore potentially skipped) inside each lane's own process."""
    try:
        preflight_report = run_preflight(repo_root)
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION, "status": "failure", "overall_exit_code": 1,
            "cancelled": False, "lanes": [], "preflight_error": str(exc),
        }

    try:
        validate_prompt_artifact(repo_root)
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION, "status": "failure", "overall_exit_code": 1,
            "cancelled": False, "lanes": [], "prompt_artifact_validation_error": str(exc),
            "preflight_report": preflight_report,
        }

    lanes = [
        load_lane_spec("gemma", args.gemma_config),
        load_lane_spec("qwen", args.qwen_config),
    ]
    orchestrator = orchestrator_factory(lanes)
    orchestrator.launch_staggered(ready_timeout_seconds=args.ready_timeout_seconds)
    result = orchestrator.wait_all(poll_interval=args.poll_interval_seconds)
    result["preflight_report"] = preflight_report
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_dual_gpu_job(args)

    job_result_path = Path(args.job_result_path)
    job_result_path.parent.mkdir(parents=True, exist_ok=True)
    job_result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "overall_exit_code": result["overall_exit_code"]}, indent=2))
    return result["overall_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
