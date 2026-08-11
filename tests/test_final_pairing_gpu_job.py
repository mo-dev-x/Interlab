"""Tests for scripts/legacy/final_pairing_gpu_job.py: the Tamia GPU job
wrapper's exit-code aggregation. Orchestrator review, 2026-08-13
("aggregate job failure"): Slurm job 406092 ended COMPLETED/0 even though
both required Gemma scenarios exited 1 -- these tests exist so that
specific failure mode can never silently reappear.

No GPU, no real model/SAE weights, no real subprocess ever actually
launched -- _run is monkeypatched everywhere main() is exercised.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_gpu_job as job  # noqa: E402


def _result(name: str, *, attempted: bool, exit_code: int | None) -> job.ScenarioResult:
    return job.ScenarioResult(name=name, command=["fake", name], attempted=attempted, exit_code=exit_code)


# ---------------------------------------------------------------------------
# aggregate_job_result -- the pure classification logic.
# ---------------------------------------------------------------------------


def test_aggregate_complete_pass_when_step0_and_both_scenarios_pass():
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=True, exit_code=0)]
    result = job.aggregate_job_result(step0, scenarios)
    assert result["status"] == "complete_pass"
    assert result["overall_exit_code"] == 0


def test_aggregate_partial_execution_when_step0_fails():
    step0 = _result("step0", attempted=True, exit_code=1)
    result = job.aggregate_job_result(step0, [])
    assert result["status"] == "partial_execution"
    assert result["overall_exit_code"] != 0


def test_aggregate_failure_when_one_scenario_fails_even_if_the_other_passes():
    """The exact live defect: a later successful scenario must not
    overwrite an earlier scenario's failure."""
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=1), _result("generated_only", attempted=True, exit_code=0)]
    result = job.aggregate_job_result(step0, scenarios)
    assert result["status"] == "failure"
    assert result["overall_exit_code"] != 0


def test_aggregate_failure_when_the_scenario_order_is_reversed():
    """Same as above with the fail/pass order swapped -- proves this
    isn't accidentally keying off which scenario is LAST."""
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=True, exit_code=1)]
    result = job.aggregate_job_result(step0, scenarios)
    assert result["status"] == "failure"
    assert result["overall_exit_code"] != 0


def test_aggregate_partial_execution_when_a_required_scenario_never_attempted():
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=False, exit_code=None)]
    result = job.aggregate_job_result(step0, scenarios)
    assert result["status"] == "partial_execution"
    assert result["overall_exit_code"] != 0


def test_scenario_result_passed_requires_both_attempted_and_zero_exit():
    assert _result("x", attempted=True, exit_code=0).passed is True
    assert _result("x", attempted=True, exit_code=1).passed is False
    assert _result("x", attempted=False, exit_code=None).passed is False


# ---------------------------------------------------------------------------
# main() -- proves Step 0 gates the scenarios, both required scenarios are
# attempted once Step 0 passes (even if the first fails), and the overall
# exit code is wired to aggregate_job_result -- not to any single
# subprocess's own exit code in isolation.
# ---------------------------------------------------------------------------


def _base_argv(tmp_path):
    return [
        "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
        "--raw-clamp-value", "5000", "--out-dir", str(tmp_path / "out"),
    ]


def test_main_stops_immediately_and_never_attempts_scenarios_when_step0_fails(monkeypatch, tmp_path):
    calls = []

    def fake_run(name, command):
        calls.append(name)
        return job.ScenarioResult(name=name, command=command, attempted=True, exit_code=1)

    monkeypatch.setattr(job, "_run", fake_run)
    exit_code = job.main(_base_argv(tmp_path))

    assert calls == ["step0_differential_check"]  # neither scenario was even attempted
    assert exit_code != 0


def test_main_attempts_both_scenarios_even_when_the_first_one_fails(monkeypatch, tmp_path):
    def fake_run(name, command):
        exit_code = 0 if name != "gemma_it_all" else 1
        return job.ScenarioResult(name=name, command=command, attempted=True, exit_code=exit_code)

    monkeypatch.setattr(job, "_run", fake_run)
    exit_code = job.main(_base_argv(tmp_path))

    result = json.loads((tmp_path / "out" / "job_result.json").read_text())
    scenario_names = [s["name"] for s in result["scenarios"]]
    assert scenario_names == ["gemma_it_all", "gemma_it_generated_only"]
    assert all(s["attempted"] for s in result["scenarios"])
    assert result["status"] == "failure"
    assert exit_code != 0


def test_main_exit_code_zero_only_when_everything_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(
        job, "_run", lambda name, command: job.ScenarioResult(name=name, command=command, attempted=True, exit_code=0)
    )
    exit_code = job.main(_base_argv(tmp_path))
    result = json.loads((tmp_path / "out" / "job_result.json").read_text())
    assert result["status"] == "complete_pass"
    assert exit_code == 0


def test_main_writes_structured_result_file_even_on_step0_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        job, "_run", lambda name, command: job.ScenarioResult(name=name, command=command, attempted=True, exit_code=1)
    )
    job.main(_base_argv(tmp_path))
    result_path = tmp_path / "out" / "job_result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text())
    assert result["status"] == "partial_execution"
    assert result["scenarios"] == []


# ---------------------------------------------------------------------------
# command builders -- pure, no subprocess involved.
# ---------------------------------------------------------------------------


def test_build_step0_command_uses_dose_multiple_and_positions_all(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--dose-multiple", "4.0", "--raw-clamp-value", "5000", "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_step0_command(args)
    assert "--dose-multiple" in cmd and cmd[cmd.index("--dose-multiple") + 1] == "4.0"
    assert "--positions" in cmd and cmd[cmd.index("--positions") + 1] == "all"
    assert str(job.SCRIPT_DIR / "gemma3_tool_diff_test.py") in cmd


def test_build_gemma_scenario_command_uses_raw_clamp_value_and_requested_positions(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--scenario-max-new-tokens", "8", "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_gemma_scenario_command(args, positions="generated_only", out_path=tmp_path / "out.json")
    assert "--raw-clamp-value" in cmd and cmd[cmd.index("--raw-clamp-value") + 1] == "5000.0"
    assert "--positions" in cmd and cmd[cmd.index("--positions") + 1] == "generated_only"
    assert "--max-new-tokens" in cmd and cmd[cmd.index("--max-new-tokens") + 1] == "8"
    assert str(job.SCRIPT_DIR / "final_pairing_harness.py") in cmd


def test_build_gemma_scenario_command_includes_expected_revisions_when_given(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--expected-model-revision", "rev1", "--expected-sae-revision", "rev2",
            "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_gemma_scenario_command(args, positions="all", out_path=tmp_path / "out.json")
    assert "--expected-model-revision" in cmd and cmd[cmd.index("--expected-model-revision") + 1] == "rev1"
    assert "--expected-sae-revision" in cmd and cmd[cmd.index("--expected-sae-revision") + 1] == "rev2"


def test_build_gemma_scenario_command_omits_expected_revisions_when_not_given(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_gemma_scenario_command(args, positions="all", out_path=tmp_path / "out.json")
    assert "--expected-model-revision" not in cmd
    assert "--expected-sae-revision" not in cmd


def test_parse_args_defaults_match_the_ratified_next_job_scope(tmp_path):
    """Next GPU job scope: Step 0 max_new_tokens=64 (unchanged), final
    scenarios max_new_tokens=8."""
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--out-dir", str(tmp_path),
        ]
    )
    assert args.step0_max_new_tokens == 64
    assert args.scenario_max_new_tokens == 8
