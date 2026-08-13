"""Resource-isolation tests for
scripts/legacy/final_concept_discovery_dual_gpu_job.py.

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
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

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
        return processes[name]

    def fake_orchestrator_factory(lane_list):
        return job.DualGpuOrchestrator(lane_list, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())

    args = job.parse_args([
        "--gemma-config", str(_write_lane_json(tmp_path, "gemma")),
        "--qwen-config", str(_write_lane_json(tmp_path, "qwen")),
        "--job-result-path", str(tmp_path / "result.json"),
    ])
    result = job.run_dual_gpu_job(args, orchestrator_factory=fake_orchestrator_factory, validate_prompt_artifact=lambda repo_root: None)
    assert result["status"] == "complete_pass"


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
