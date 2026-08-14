"""Resource-isolation tests for
scripts/final_pairing/final_concept_discovery_dual_gpu_job.py.

Every test here uses a fake process/signal seam -- no real subprocess is
ever spawned, no real OS signal is ever delivered, and (verified
structurally below) this module never imports torch/transformers/sae_lens/
sklearn at all, so nothing in this file or the module it tests can load a
real model.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_concept_discovery_dual_gpu_job as job  # noqa: E402


class _FakeProcess:
    def __init__(self, pid: int, *, exit_code: int | None = None, exit_after_polls: int = 1):
        self._pid = pid
        self._exit_code = exit_code
        self._exit_after_polls = exit_after_polls
        self._poll_count = 0
        self.terminate_called = False
        self.kill_called = False
        self.signals_received: list[int] = []

    @property
    def pid(self) -> int:
        return self._pid

    def poll(self) -> int | None:
        self._poll_count += 1
        if self._exit_code is not None and self._poll_count >= self._exit_after_polls:
            return self._exit_code
        return None

    def wait(self, timeout: float | None = None) -> int:
        if self._exit_code is None:
            self._exit_code = -15
        return self._exit_code

    def send_signal(self, sig) -> None:
        self.signals_received.append(sig)

    def terminate(self) -> None:
        self.terminate_called = True

    def kill(self) -> None:
        self.kill_called = True


class _FakeSignalModule:
    SIGTERM = 15
    SIGINT = 2

    def __init__(self):
        self._handlers: dict[int, object] = {}

    def signal(self, sig, handler):
        previous = self._handlers.get(sig)
        self._handlers[sig] = handler
        return previous

    def getsignal(self, sig):
        return self._handlers.get(sig)

    def fire(self, sig) -> None:
        handler = self._handlers.get(sig)
        if handler is not None:
            handler(sig, None)


def _write_lane_json(tmp_path: Path, name: str, *, argv: list[str] | None = None) -> Path:
    lane_dir = tmp_path / name
    payload = {
        "out_dir": str(lane_dir / "out"),
        "state_dir": str(lane_dir / "state"),
        "tmp_dir": str(lane_dir / "tmp"),
        "log_path": str(lane_dir / "log.txt"),
        "argv": argv if argv is not None else ["--pairing", "gemma-3-12b-it" if name == "gemma" else "qwen-3.5-27b"],
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_lanes(tmp_path: Path) -> list[job.LaneSpec]:
    gemma_path = _write_lane_json(tmp_path, "gemma")
    qwen_path = _write_lane_json(tmp_path, "qwen")
    return [job.load_lane_spec("gemma", gemma_path), job.load_lane_spec("qwen", qwen_path)]


# ---------------------------------------------------------------------------
# CUDA_VISIBLE_DEVICES isolation
# ---------------------------------------------------------------------------


def test_gemma_and_qwen_lanes_receive_different_cuda_visible_devices(tmp_path):
    lanes = _make_lanes(tmp_path)
    envs = {lane.name: job.env_for_lane(lane, base_env={}) for lane in lanes}
    assert envs["gemma"]["CUDA_VISIBLE_DEVICES"] == "0"
    assert envs["qwen"]["CUDA_VISIBLE_DEVICES"] == "1"
    assert envs["gemma"]["CUDA_VISIBLE_DEVICES"] != envs["qwen"]["CUDA_VISIBLE_DEVICES"]


def test_no_lane_can_ever_be_assigned_a_reserved_judge_gpu(tmp_path):
    lanes = _make_lanes(tmp_path)
    for lane in lanes:
        env = job.env_for_lane(lane, base_env={})
        assert env["CUDA_VISIBLE_DEVICES"] not in job.RESERVED_JUDGE_GPUS
    assert set(job.LANE_GPU_ASSIGNMENT.values()).isdisjoint(job.RESERVED_JUDGE_GPUS)


def test_lane_json_cannot_override_the_fixed_gpu_assignment(tmp_path):
    """Even if a lane's own JSON tried to smuggle a CUDA_VISIBLE_DEVICES
    value into argv, env_for_lane's own assignment (keyed by lane NAME, not
    by anything in the JSON) is what actually lands in the child's
    environment."""
    sneaky_argv = ["--pairing", "gemma-3-12b-it", "--cuda-visible-devices-lie", "2,3"]
    path = _write_lane_json(tmp_path, "gemma", argv=sneaky_argv)
    lane = job.load_lane_spec("gemma", path)
    env = job.env_for_lane(lane, base_env={})
    assert env["CUDA_VISIBLE_DEVICES"] == "0"


def test_build_lane_command_forces_device_cuda_0_last(tmp_path):
    lanes = _make_lanes(tmp_path)
    for lane in lanes:
        command = job.build_lane_command(lane)
        device_indices = [i for i, tok in enumerate(command) if tok == "--device"]
        assert device_indices, "no --device flag was appended"
        last_device_index = device_indices[-1]
        assert command[last_device_index + 1] == "cuda:0"
        assert last_device_index == len(command) - 2  # the very last flag/value pair


# ---------------------------------------------------------------------------
# Path isolation
# ---------------------------------------------------------------------------


def test_lanes_have_disjoint_out_state_tmp_and_log_paths(tmp_path):
    lanes = _make_lanes(tmp_path)
    job.validate_lane_paths_disjoint(lanes)  # must not raise


def test_duplicate_output_paths_fail_before_any_launch(tmp_path, monkeypatch):
    shared = tmp_path / "shared_out"
    gemma_path = tmp_path / "gemma.json"
    qwen_path = tmp_path / "qwen.json"
    gemma_path.write_text(json.dumps({
        "out_dir": str(shared), "state_dir": str(tmp_path / "gemma_state"),
        "tmp_dir": str(tmp_path / "gemma_tmp"), "log_path": str(tmp_path / "gemma.log"), "argv": [],
    }), encoding="utf-8")
    qwen_path.write_text(json.dumps({
        "out_dir": str(shared), "state_dir": str(tmp_path / "qwen_state"),
        "tmp_dir": str(tmp_path / "qwen_tmp"), "log_path": str(tmp_path / "qwen.log"), "argv": [],
    }), encoding="utf-8")
    lanes = [job.load_lane_spec("gemma", gemma_path), job.load_lane_spec("qwen", qwen_path)]

    launched = []
    monkeypatch.setattr(job, "default_launch", lambda *a, **k: launched.append(1))

    with pytest.raises(job.LaneConfigError):
        job.DualGpuOrchestrator(lanes, launch=job.default_launch)
    assert launched == [], "no process must be launched when paths collide"


def test_duplicate_state_or_tmp_or_log_paths_also_fail(tmp_path):
    for colliding_field in ("state_dir", "tmp_dir", "log_path"):
        gemma_payload = {
            "out_dir": str(tmp_path / "g_out"), "state_dir": str(tmp_path / "g_state"),
            "tmp_dir": str(tmp_path / "g_tmp"), "log_path": str(tmp_path / "g.log"), "argv": [],
        }
        qwen_payload = {
            "out_dir": str(tmp_path / "q_out"), "state_dir": str(tmp_path / "q_state"),
            "tmp_dir": str(tmp_path / "q_tmp"), "log_path": str(tmp_path / "q.log"), "argv": [],
        }
        qwen_payload[colliding_field] = gemma_payload[colliding_field]
        gemma_path, qwen_path = tmp_path / "g2.json", tmp_path / "q2.json"
        gemma_path.write_text(json.dumps(gemma_payload), encoding="utf-8")
        qwen_path.write_text(json.dumps(qwen_payload), encoding="utf-8")
        lanes = [job.load_lane_spec("gemma", gemma_path), job.load_lane_spec("qwen", qwen_path)]
        with pytest.raises(job.LaneConfigError):
            job.validate_lane_paths_disjoint(lanes)


def test_load_lane_spec_rejects_an_unknown_lane_name(tmp_path):
    path = _write_lane_json(tmp_path, "gemma")
    with pytest.raises(job.LaneConfigError):
        job.load_lane_spec("not-a-real-lane", path)


def test_load_lane_spec_rejects_missing_required_fields(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"out_dir": "x"}), encoding="utf-8")
    with pytest.raises(job.LaneConfigError):
        job.load_lane_spec("gemma", path)


# ---------------------------------------------------------------------------
# Aggregate status / failure propagation
# ---------------------------------------------------------------------------


def _lane_result(name: str, *, attempted=True, exit_code=0, terminated_by_signal=False) -> job.LaneResult:
    return job.LaneResult(
        name=name, command=["x"], cuda_visible_devices=job.LANE_GPU_ASSIGNMENT[name],
        out_dir="o", state_dir="s", log_path="l", pid=1, start_time=0.0, end_time=1.0,
        exit_code=exit_code, attempted=attempted, terminated_by_signal=terminated_by_signal,
    )


def test_aggregate_is_complete_pass_only_when_both_lanes_exit_zero():
    result = job.aggregate([_lane_result("gemma"), _lane_result("qwen")])
    assert result["status"] == "complete_pass"
    assert result["overall_exit_code"] == 0


def test_one_lane_failing_makes_the_aggregate_fail_even_if_the_other_passed():
    result = job.aggregate([_lane_result("gemma", exit_code=0), _lane_result("qwen", exit_code=1)])
    assert result["status"] == "failure"
    assert result["overall_exit_code"] == 1


def test_a_later_success_never_masks_an_earlier_failure_regardless_of_list_order():
    forward = job.aggregate([_lane_result("gemma", exit_code=1), _lane_result("qwen", exit_code=0)])
    backward = job.aggregate([_lane_result("qwen", exit_code=0), _lane_result("gemma", exit_code=1)])
    assert forward["status"] == "failure"
    assert backward["status"] == "failure"


def test_an_unattempted_lane_is_partial_execution_not_failure():
    result = job.aggregate([_lane_result("gemma", attempted=True, exit_code=0), _lane_result("qwen", attempted=False, exit_code=None)])
    assert result["status"] == "partial_execution"


def test_cancellation_flag_forces_partial_execution_even_if_both_lanes_happened_to_exit_zero():
    result = job.aggregate([_lane_result("gemma"), _lane_result("qwen")], cancelled=True)
    assert result["status"] == "partial_execution"
    assert result["cancelled"] is True


# ---------------------------------------------------------------------------
# Orchestrator behavior: independent completion, cancellation propagation
# ---------------------------------------------------------------------------


def test_one_lane_finishing_does_not_block_or_terminate_the_other(tmp_path):
    lanes = _make_lanes(tmp_path)
    processes = {"gemma": _FakeProcess(pid=100, exit_code=0, exit_after_polls=1), "qwen": _FakeProcess(pid=200, exit_code=0, exit_after_polls=3)}

    def fake_launch(command, *, env, cwd, log_path):
        name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
        return processes[name]

    orch = job.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    orch.launch_all()
    result = orch.wait_all(poll_interval=0)

    assert result["status"] == "complete_pass"
    assert not processes["gemma"].terminate_called
    assert not processes["qwen"].terminate_called


def test_cancellation_is_propagated_to_both_lanes_via_the_injected_signal_module(tmp_path):
    lanes = _make_lanes(tmp_path)
    processes = {"gemma": _FakeProcess(pid=100, exit_code=None), "qwen": _FakeProcess(pid=200, exit_code=None)}
    fake_signal = _FakeSignalModule()
    poll_calls = {"n": 0}

    def fake_launch(command, *, env, cwd, log_path):
        name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
        return processes[name]

    def fake_sleep(_seconds):
        poll_calls["n"] += 1
        if poll_calls["n"] == 1:
            fake_signal.fire(fake_signal.SIGTERM)  # simulates Slurm cancelling the job mid-wait

    orch = job.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=fake_sleep, signal_module=fake_signal)
    orch.launch_all()
    result = orch.wait_all(poll_interval=0)

    assert result["cancelled"] is True
    assert result["status"] == "partial_execution"
    assert processes["gemma"].terminate_called
    assert processes["qwen"].terminate_called


def test_terminate_all_does_not_re_terminate_a_lane_that_already_exited(tmp_path):
    lanes = _make_lanes(tmp_path)
    already_done = _FakeProcess(pid=100, exit_code=0, exit_after_polls=1)
    still_running = _FakeProcess(pid=200, exit_code=None)

    def fake_launch(command, *, env, cwd, log_path):
        return already_done if env["CUDA_VISIBLE_DEVICES"] == "0" else still_running

    orch = job.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    orch.launch_all()
    already_done.poll()  # advance it to "exited" before terminate_all runs
    orch.terminate_all()

    assert not already_done.terminate_called
    assert still_running.terminate_called


def test_launch_all_records_pid_command_and_start_time(tmp_path):
    lanes = _make_lanes(tmp_path)
    processes = {"gemma": _FakeProcess(pid=111, exit_code=0), "qwen": _FakeProcess(pid=222, exit_code=0)}

    def fake_launch(command, *, env, cwd, log_path):
        name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
        return processes[name]

    orch = job.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    orch.launch_all()

    assert orch._results["gemma"].pid == 111
    assert orch._results["qwen"].pid == 222
    assert orch._results["gemma"].start_time is not None
    assert orch._results["gemma"].command[0] == sys.executable
    assert str(job.DISCOVERY_SCRIPT) in orch._results["gemma"].command


def test_orchestrator_rejects_anything_other_than_exactly_gemma_and_qwen_lanes(tmp_path):
    gemma_path = _write_lane_json(tmp_path, "gemma")
    with pytest.raises(job.LaneConfigError):
        job.DualGpuOrchestrator([job.load_lane_spec("gemma", gemma_path)])


# ---------------------------------------------------------------------------
# Prompt-artifact validation gates BOTH lanes before either launches.
# ---------------------------------------------------------------------------


_PASSING_PREFLIGHT_REPORT = {
    "schema_version": 1, "source_commit": "0" * 40, "expected_cases": 1, "executed_cases": 1, "passed_cases": 1,
    "failed_cases": [], "cases": [{"name": "fake", "status": "pass", "detail": "", "elapsed_seconds": 0.0}],
    "overall_passed": True, "proofs": {},
}


def test_a_failing_prompt_artifact_validator_stops_both_lanes_before_any_launch(tmp_path):
    launched = []

    def fake_orchestrator_factory(lane_list):
        launched.append(lane_list)
        raise AssertionError("must never be constructed when prompt-artifact validation fails")

    def failing_validator(repo_root):
        raise job.LaneConfigError("hash mismatch")

    args = job.parse_args([
        "--gemma-config", str(_write_lane_json(tmp_path, "gemma")),
        "--qwen-config", str(_write_lane_json(tmp_path, "qwen")),
        "--job-result-path", str(tmp_path / "result.json"),
    ])
    result = job.run_dual_gpu_job(
        args, orchestrator_factory=fake_orchestrator_factory, validate_prompt_artifact=failing_validator,
        run_preflight=lambda repo_root: dict(_PASSING_PREFLIGHT_REPORT),
    )
    assert result["status"] == "failure"
    assert result["overall_exit_code"] == 1
    assert result["lanes"] == []
    assert "hash mismatch" in result["prompt_artifact_validation_error"]
    assert launched == []


def test_a_passing_prompt_artifact_validator_allows_both_lanes_to_launch(tmp_path):
    processes = {"gemma": _FakeProcess(pid=1, exit_code=0), "qwen": _FakeProcess(pid=2, exit_code=0)}

    def fake_launch(command, *, env, cwd, log_path):
        name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
        if name == job.STAGGER_LEAD_LANE:
            # Mimics the real subprocess reaching READY instantly, so
            # launch_staggered's wait_for_ready_record finds it on its
            # very first check -- no real sleep needed in this test.
            ready_index = command.index("--ready-path")
            ready_path = Path(command[ready_index + 1])
            import final_pairing_concept_discovery as discovery

            discovery.write_ready_record(ready_path, pairing="qwen-3.5-27b", device="cuda:0", pid=processes["qwen"].pid)
        return processes[name]

    def fake_orchestrator_factory(lane_list):
        return job.DualGpuOrchestrator(lane_list, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())

    args = job.parse_args([
        "--gemma-config", str(_write_lane_json(tmp_path, "gemma")),
        "--qwen-config", str(_write_lane_json(tmp_path, "qwen")),
        "--job-result-path", str(tmp_path / "result.json"),
    ])
    result = job.run_dual_gpu_job(
        args, orchestrator_factory=fake_orchestrator_factory, validate_prompt_artifact=lambda repo_root: None,
        run_preflight=lambda repo_root: dict(_PASSING_PREFLIGHT_REPORT),
    )
    assert result["status"] == "complete_pass"
    assert result["preflight_report"] == _PASSING_PREFLIGHT_REPORT


# ---------------------------------------------------------------------------
# The standalone preflight runs FIRST, before prompt-artifact validation and
# before either lane launches; the driver re-validates the report itself
# rather than trusting only the subprocess exit code.
# ---------------------------------------------------------------------------


def test_a_failing_preflight_stops_both_lanes_before_prompt_artifact_validation_even_runs(tmp_path):
    validator_called = {"n": 0}

    def spy_validator(repo_root):
        validator_called["n"] += 1

    def fake_orchestrator_factory(lane_list):
        raise AssertionError("must never be constructed when the preflight fails")

    def failing_preflight(repo_root):
        raise job.PreflightFailed("2 case(s) did not report 'pass'")

    args = job.parse_args([
        "--gemma-config", str(_write_lane_json(tmp_path, "gemma")),
        "--qwen-config", str(_write_lane_json(tmp_path, "qwen")),
        "--job-result-path", str(tmp_path / "result.json"),
    ])
    result = job.run_dual_gpu_job(
        args, orchestrator_factory=fake_orchestrator_factory, validate_prompt_artifact=spy_validator,
        run_preflight=failing_preflight,
    )
    assert result["status"] == "failure"
    assert result["lanes"] == []
    assert "did not report 'pass'" in result["preflight_error"]
    assert validator_called["n"] == 0


def test_default_preflight_runner_rejects_a_zero_exit_with_a_non_passing_case():
    """The independent re-validation this task requires: a subprocess that
    exits 0 but whose OWN JSON report contains a non-passing case (or a
    executed/expected mismatch) must still be treated as a failure -- the
    exit code alone is not trusted."""
    import json as _json
    import types

    lying_report = {
        "schema_version": 1, "source_commit": "0" * 40, "expected_cases": 2, "executed_cases": 2, "passed_cases": 1,
        "failed_cases": [],  # deliberately lying: "b" failed but is not listed here either
        "cases": [
            {"name": "a", "status": "pass", "detail": "", "elapsed_seconds": 0.0},
            {"name": "b", "status": "fail", "detail": "boom", "elapsed_seconds": 0.0},
        ],
        "overall_passed": True,  # deliberately lying about its own per-case results
        "proofs": {},
    }

    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=_json.dumps(lying_report), stderr="")

    import subprocess as _subprocess
    original = _subprocess.run
    _subprocess.run = fake_run
    try:
        try:
            job.default_preflight_runner(job.REPO_ROOT)
        except job.PreflightFailed as exc:
            assert "did not report 'pass'" in str(exc) or "case(s) did not report" in str(exc)
        else:
            raise AssertionError("expected PreflightFailed for a report with a non-passing case")
    finally:
        _subprocess.run = original


def test_default_preflight_runner_rejects_unparsable_output():
    import types

    def fake_run(*args, **kwargs):
        return types.SimpleNamespace(returncode=1, stdout="not json", stderr="traceback")

    import subprocess as _subprocess
    original = _subprocess.run
    _subprocess.run = fake_run
    try:
        try:
            job.default_preflight_runner(job.REPO_ROOT)
        except job.PreflightFailed as exc:
            assert "non-JSON output" in str(exc)
        else:
            raise AssertionError("expected PreflightFailed for unparsable output")
    finally:
        _subprocess.run = original


# ---------------------------------------------------------------------------
# Never writes canonical evidence, never touches GPUs 2-3, never loads a
# model -- structural proofs, not behavioral ones.
# ---------------------------------------------------------------------------


def test_module_never_imports_heavy_ml_or_registry_libraries():
    source = Path(job.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    forbidden = {"torch", "transformers", "sae_lens", "sklearn", "interplab"}
    assert imported_roots.isdisjoint(forbidden), f"unexpected heavy/registry import(s): {imported_roots & forbidden}"


def test_aggregate_result_contains_no_scientific_payload_fields():
    """The aggregate result is process bookkeeping only -- it must never
    carry a lane's own result.json content (verdict/calibration/bundle/
    etc.), which would be this file authoring evidence it isn't supposed
    to touch."""
    result = job.aggregate([_lane_result("gemma"), _lane_result("qwen")])
    forbidden_keys = {"verdict", "calibration_candidates", "bundle", "specificity_results", "dose_response"}
    assert forbidden_keys.isdisjoint(result.keys())
    for lane in result["lanes"]:
        assert forbidden_keys.isdisjoint(lane.keys())


# ---------------------------------------------------------------------------
# CUDA_DEVICE_ORDER and staggered cold-load READY handshake
# ---------------------------------------------------------------------------


def test_env_for_lane_sets_cuda_device_order_pci_bus_id(tmp_path):
    lanes = _make_lanes(tmp_path)
    for lane in lanes:
        env = job.env_for_lane(lane, base_env={})
        assert env["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"


def _write_real_ready_record(lane: job.LaneSpec, *, pairing: str, device: str = "cuda:0", pid: int | None = None) -> None:
    import final_pairing_concept_discovery as discovery

    discovery.write_ready_record(job.ready_path_for_lane(lane), pairing=pairing, device=device, pid=pid)


def test_launch_staggered_launches_qwen_first_and_gemma_only_after_ready(tmp_path):
    lanes = _make_lanes(tmp_path)
    lead_lane = next(lane for lane in lanes if lane.name == job.STAGGER_LEAD_LANE)

    # P0 STOP-LINE correction: launch_staggered now deletes any stale READY
    # file for BOTH lanes BEFORE launching, so the record must be written
    # AFTER (i.e. by) the fake launch callback -- exactly mirroring the
    # real production shape, where the CHILD process writes it, not the
    # parent before the child even exists. `pid=proc.pid` matches
    # wait_for_ready_record's new expected_pid check against THIS fake
    # process's own advertised pid.
    def launch(command, *, env, cwd, log_path):
        proc = _FakeProcess(pid=1)
        if env["CUDA_VISIBLE_DEVICES"] == job.LANE_GPU_ASSIGNMENT[job.STAGGER_LEAD_LANE]:
            _write_real_ready_record(lead_lane, pairing="qwen-3.5-27b", pid=proc.pid)
        return proc

    orch = job.DualGpuOrchestrator(lanes, launch=launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    orch.launch_staggered()
    assert set(orch._processes) == {"gemma", "qwen"}
    assert orch._results["qwen"].start_time <= orch._results["gemma"].start_time


def test_launch_staggered_fails_closed_when_lead_process_exits_before_ready(tmp_path):
    lanes = _make_lanes(tmp_path)

    def launch(command, *, env, cwd, log_path):
        # The lead's process exits immediately (poll() returns non-None on
        # the very first call) and NEVER writes a READY record.
        return _FakeProcess(pid=1, exit_code=1, exit_after_polls=1)

    orch = job.DualGpuOrchestrator(lanes, launch=launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    with pytest.raises(Exception) as excinfo:
        orch.launch_staggered(ready_timeout_seconds=5.0)
    assert "exited before writing" in str(excinfo.value)
    # The follower must never have been launched.
    assert job.STAGGER_FOLLOW_LANE not in orch._processes


def test_launch_staggered_fails_closed_on_a_ready_record_naming_the_wrong_pairing(tmp_path):
    lanes = _make_lanes(tmp_path)
    lead_lane = next(lane for lane in lanes if lane.name == job.STAGGER_LEAD_LANE)

    def launch(command, *, env, cwd, log_path):
        proc = _FakeProcess(pid=1)
        if env["CUDA_VISIBLE_DEVICES"] == job.LANE_GPU_ASSIGNMENT[job.STAGGER_LEAD_LANE]:
            _write_real_ready_record(lead_lane, pairing="the-wrong-pairing", pid=proc.pid)
        return proc

    orch = job.DualGpuOrchestrator(lanes, launch=launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    with pytest.raises(Exception) as excinfo:
        orch.launch_staggered()
    assert "names pairing" in str(excinfo.value)
    assert job.STAGGER_FOLLOW_LANE not in orch._processes


def test_launch_staggered_fails_closed_on_a_ready_record_naming_the_wrong_pid(tmp_path):
    """P0 STOP-LINE correction: 'require READY pid/start time to match
    this child' -- a READY record naming a DIFFERENT pid than the actual
    spawned lead process must be refused, even if pairing/device agree."""
    lanes = _make_lanes(tmp_path)
    lead_lane = next(lane for lane in lanes if lane.name == job.STAGGER_LEAD_LANE)

    def launch(command, *, env, cwd, log_path):
        proc = _FakeProcess(pid=1)
        if env["CUDA_VISIBLE_DEVICES"] == job.LANE_GPU_ASSIGNMENT[job.STAGGER_LEAD_LANE]:
            _write_real_ready_record(lead_lane, pairing="qwen-3.5-27b", pid=99999)  # deliberately wrong pid
        return proc

    orch = job.DualGpuOrchestrator(lanes, launch=launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    with pytest.raises(Exception) as excinfo:
        orch.launch_staggered()
    assert "names pid" in str(excinfo.value)
    assert job.STAGGER_FOLLOW_LANE not in orch._processes


def test_launch_staggered_deletes_a_stale_ready_record_before_launching(tmp_path):
    """P0 STOP-LINE correction: 'delete an old READY file before launch'
    -- a READY record left over from a previous run in the same state_dir
    must never be misread as this run's signal. Without the deletion, the
    lead lane's wait would immediately (and wrongly) succeed against the
    stale record instead of waiting for a REAL one this launch writes."""
    lanes = _make_lanes(tmp_path)
    lead_lane = next(lane for lane in lanes if lane.name == job.STAGGER_LEAD_LANE)
    stale_path = job.ready_path_for_lane(lead_lane)
    _write_real_ready_record(lead_lane, pairing="qwen-3.5-27b", pid=424242)  # a stale record from "a previous run"

    def launch(command, *, env, cwd, log_path):
        proc = _FakeProcess(pid=1)
        if env["CUDA_VISIBLE_DEVICES"] == job.LANE_GPU_ASSIGNMENT[job.STAGGER_LEAD_LANE]:
            assert not stale_path.is_file()  # the stale record must already be gone by launch time
            _write_real_ready_record(lead_lane, pairing="qwen-3.5-27b", pid=proc.pid)
        return proc

    orch = job.DualGpuOrchestrator(lanes, launch=launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    orch.launch_staggered()
    assert set(orch._processes) == {"gemma", "qwen"}


def test_launch_staggered_uses_an_injectable_wait_for_ready_seam(tmp_path):
    """A fake wait_for_ready (mimicking a timeout, without a real sleep)
    proves the seam is genuinely used rather than the real function being
    hardcoded in."""
    lanes = _make_lanes(tmp_path)
    calls = {"n": 0}

    def fake_wait_for_ready(ready_path, *, expected_pairing, expected_device, process_alive_fn, timeout_seconds, sleep_fn=None, **_kwargs):
        calls["n"] += 1
        raise TimeoutError(f"simulated timeout waiting for {ready_path}")

    orch = job.DualGpuOrchestrator(lanes, launch=lambda *a, **k: _FakeProcess(pid=1), sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())
    with pytest.raises(TimeoutError):
        orch.launch_staggered(wait_for_ready=fake_wait_for_ready)
    assert calls["n"] == 1
    assert job.STAGGER_FOLLOW_LANE not in orch._processes


# ---------------------------------------------------------------------------
# P0 STOP-LINE correction: validate generation lane argv identity before
# launch; require SLURM_JOB_ID-rooted lane paths.
# ---------------------------------------------------------------------------


def _write_generation_lane_json(tmp_path: Path, name: str, *, argv: list[str]) -> Path:
    lane_dir = tmp_path / name
    payload = {
        "out_dir": str(lane_dir / "out"), "state_dir": str(lane_dir / "state"),
        "tmp_dir": str(lane_dir / "tmp"), "log_path": str(lane_dir / "log.txt"),
        "argv": argv, "target_script": str(job.GENERATION_SCRIPT),
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


_COMPLETE_GENERATION_ARGV = [
    "--pairing", "gemma-3-12b-it", "--model-path", "/fake/model", "--sae-path", "/fake/sae",
    "--layer", "29", "--configuration-name", "primary", "--grid-path", "/fake/grid.json",
    "--pairing-id", "google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
    "--run-id", "r-test-0001", "--source-commit", "0" * 40,
]


def test_validate_generation_lane_argv_is_a_noop_for_a_grid_discovery_lane(tmp_path):
    lane = job.load_lane_spec("gemma", _write_lane_json(tmp_path, "gemma"))
    job.validate_generation_lane_argv(lane)  # must not raise


def test_validate_generation_lane_argv_accepts_a_complete_generation_lane(tmp_path):
    lane = job.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "gemma", argv=_COMPLETE_GENERATION_ARGV))
    job.validate_generation_lane_argv(lane)  # must not raise


def test_validate_generation_lane_argv_rejects_a_generation_lane_missing_required_flags(tmp_path):
    lane = job.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "gemma", argv=["--pairing", "gemma-3-12b-it"]))
    with pytest.raises(job.LaneConfigError, match="missing required flag"):
        job.validate_generation_lane_argv(lane)


def test_run_dual_gpu_job_for_lanes_rejects_an_incomplete_generation_lane_before_any_launch(tmp_path):
    launched = []

    def factory(lanes):
        def fake_launch(command, *, env, cwd, log_path):
            launched.append(env["CUDA_VISIBLE_DEVICES"])
            return _FakeProcess(pid=1)

        return job.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())

    gemma_lane = job.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "gemma", argv=["--pairing", "gemma-3-12b-it"]))
    qwen_lane = job.load_lane_spec("qwen", _write_generation_lane_json(tmp_path, "qwen", argv=_COMPLETE_GENERATION_ARGV))
    with pytest.raises(job.LaneConfigError, match="missing required flag"):
        job.run_dual_gpu_job_for_lanes(
            [gemma_lane, qwen_lane], orchestrator_factory=factory,
            validate_prompt_artifact=lambda repo_root: None, run_preflight=lambda repo_root: dict(_PASSING_PREFLIGHT_REPORT),
        )
    assert launched == []


def test_validate_lane_paths_rooted_in_slurm_job_id_accepts_rooted_paths(tmp_path):
    job_root = tmp_path / "SLURM_JOB_42"
    lane = job.LaneSpec(
        name="gemma", out_dir=job_root / "out", state_dir=job_root / "state",
        tmp_dir=job_root / "tmp", log_path=job_root / "log.txt", argv=["--pairing", "gemma-3-12b-it"],
    )
    job.validate_lane_paths_rooted_in_slurm_job_id([lane], slurm_job_id="SLURM_JOB_42")  # must not raise


def test_validate_lane_paths_rooted_in_slurm_job_id_rejects_a_substring_only_match(tmp_path):
    """A job id that merely appears as a SUBSTRING of a path component
    (not as its own exact component) must not pass."""
    job_root = tmp_path / "SLURM_JOB_42x"
    lane = job.LaneSpec(
        name="gemma", out_dir=job_root / "out", state_dir=job_root / "state",
        tmp_dir=job_root / "tmp", log_path=job_root / "log.txt", argv=["--pairing", "gemma-3-12b-it"],
    )
    with pytest.raises(job.LaneConfigError, match="SLURM_JOB_ID"):
        job.validate_lane_paths_rooted_in_slurm_job_id([lane], slurm_job_id="SLURM_JOB_42")


def test_validate_lane_paths_rooted_in_slurm_job_id_rejects_an_unrooted_path(tmp_path):
    lane = job.load_lane_spec("gemma", _write_lane_json(tmp_path, "gemma"))
    with pytest.raises(job.LaneConfigError, match="SLURM_JOB_ID"):
        job.validate_lane_paths_rooted_in_slurm_job_id([lane], slurm_job_id="SLURM_JOB_42")
