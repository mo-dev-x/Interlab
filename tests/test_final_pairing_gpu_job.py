"""Tests for scripts/legacy/final_pairing_gpu_job.py: the Tamia GPU job
wrapper's exit-code aggregation. Orchestrator review, 2026-08-13
("aggregate job failure"): Slurm job 406092 ended COMPLETED/0 even though
both required Gemma scenarios exited 1 -- these tests exist so that
specific failure mode can never silently reappear.

Orchestrator review, 2026-08-16 ("Correct and comprehensively audit Gemma
path-containment guards", live job 406957): added the symlink-containment
PREFLIGHT gate (runs before Step 0).

Orchestrator review, 2026-08-17 ("Make the Tamia symlink preflight
self-contained and pytest-free"): the preflight now runs the standalone,
pytest-free scripts/legacy/final_pairing_symlink_preflight.py via
_run_preflight (a DIFFERENT function from _run, since it independently
re-reads the preflight's own JSON artifact) -- tests below monkeypatch
_run_preflight and _run separately, and PreflightResult (not
ScenarioResult) is used for the preflight argument throughout.

No GPU, no real model/SAE weights, no real subprocess ever actually
launched -- _run/_run_preflight are monkeypatched everywhere main() is
exercised.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_gpu_job as job  # noqa: E402


def _result(name: str, *, attempted: bool, exit_code: int | None) -> job.ScenarioResult:
    return job.ScenarioResult(name=name, command=["fake", name], attempted=attempted, exit_code=exit_code)


def _preflight_result(
    *, attempted: bool = True, exit_code: int | None = 0, executed_count: int | None = 11,
    passed_count: int | None = 11, overall_passed: bool | None = True,
) -> job.PreflightResult:
    return job.PreflightResult(
        name="symlink_containment_preflight", command=["fake", "preflight"], attempted=attempted,
        exit_code=exit_code, json_path="fake_preflight_result.json", executed_count=executed_count,
        passed_count=passed_count, overall_passed=overall_passed,
    )


def _passing_preflight() -> job.PreflightResult:
    return _preflight_result()


def _fake_run_preflight(**overrides):
    result = _preflight_result(**overrides)

    def fake(command, json_path):
        return job.PreflightResult(
            name=result.name, command=command, attempted=result.attempted, exit_code=result.exit_code,
            json_path=str(json_path), executed_count=result.executed_count, passed_count=result.passed_count,
            overall_passed=result.overall_passed,
        )

    return fake


def _tracking_fake_run(calls: list[str], *, exit_code: int = 0):
    def fake_run(name, command):
        calls.append(name)
        return job.ScenarioResult(name=name, command=command, attempted=True, exit_code=exit_code)

    return fake_run


def _assert_no_pytest_import_or_invocation(source_path: Path) -> None:
    """Parses the AST (not a raw substring search, which would also flag
    this module's own docstrings about WHY pytest is avoided)."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name == "pytest" or alias.name.startswith("pytest.") for alias in node.names), (
                f"{source_path} imports pytest directly"
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module != "pytest" and not module.startswith("pytest."), f"{source_path} imports from pytest"
        elif isinstance(node, ast.Constant) and node.value == "pytest":
            raise AssertionError(f"{source_path} contains the literal string 'pytest' in code (not just prose)")


def test_gpu_driver_never_imports_or_invokes_pytest():
    _assert_no_pytest_import_or_invocation(Path(job.__file__))


# ---------------------------------------------------------------------------
# PreflightResult.passed -- defense in depth: exit_code alone is never
# trusted; executed_count/passed_count/overall_passed are checked too.
# ---------------------------------------------------------------------------


def test_preflight_result_passed_requires_exit_code_and_full_case_count_and_overall_passed():
    assert _preflight_result().passed is True
    assert _preflight_result(exit_code=1).passed is False
    assert _preflight_result(executed_count=10).passed is False
    assert _preflight_result(passed_count=10).passed is False
    assert _preflight_result(overall_passed=False).passed is False
    assert _preflight_result(overall_passed=None).passed is False
    assert _preflight_result(executed_count=0, passed_count=0, overall_passed=False).passed is False
    # defense in depth: a (hypothetically buggy) exit_code=0 must not
    # override a wrong executed_count/passed_count/overall_passed.
    assert _preflight_result(exit_code=0, executed_count=0, passed_count=0, overall_passed=False).passed is False


# ---------------------------------------------------------------------------
# aggregate_job_result -- the pure classification logic.
# ---------------------------------------------------------------------------


def test_aggregate_complete_pass_when_preflight_step0_and_both_scenarios_pass():
    preflight = _passing_preflight()
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=True, exit_code=0)]
    result = job.aggregate_job_result(preflight, step0, scenarios)
    assert result["status"] == "complete_pass"
    assert result["overall_exit_code"] == 0


def test_aggregate_partial_execution_when_preflight_fails_before_step0_or_scenarios():
    """The earliest gate: a failed preflight must stop the job before
    Step 0 is even attempted, exactly like an existing Step 0 failure
    already stops it before the scenarios."""
    preflight = _preflight_result(exit_code=1, executed_count=0, passed_count=0, overall_passed=False)
    step0_not_attempted = _result("step0", attempted=False, exit_code=None)
    result = job.aggregate_job_result(preflight, step0_not_attempted, [])
    assert result["status"] == "partial_execution"
    assert result["overall_exit_code"] != 0
    assert result["preflight"]["executed_count"] == 0
    assert result["step0"]["attempted"] is False


def test_aggregate_partial_execution_when_step0_fails():
    preflight = _passing_preflight()
    step0 = _result("step0", attempted=True, exit_code=1)
    result = job.aggregate_job_result(preflight, step0, [])
    assert result["status"] == "partial_execution"
    assert result["overall_exit_code"] != 0


def test_aggregate_failure_when_one_scenario_fails_even_if_the_other_passes():
    """The exact live defect: a later successful scenario must not
    overwrite an earlier scenario's failure."""
    preflight = _passing_preflight()
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=1), _result("generated_only", attempted=True, exit_code=0)]
    result = job.aggregate_job_result(preflight, step0, scenarios)
    assert result["status"] == "failure"
    assert result["overall_exit_code"] != 0


def test_aggregate_failure_when_the_scenario_order_is_reversed():
    """Same as above with the fail/pass order swapped -- proves this
    isn't accidentally keying off which scenario is LAST."""
    preflight = _passing_preflight()
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=True, exit_code=1)]
    result = job.aggregate_job_result(preflight, step0, scenarios)
    assert result["status"] == "failure"
    assert result["overall_exit_code"] != 0


def test_aggregate_partial_execution_when_a_required_scenario_never_attempted():
    preflight = _passing_preflight()
    step0 = _result("step0", attempted=True, exit_code=0)
    scenarios = [_result("all", attempted=True, exit_code=0), _result("generated_only", attempted=False, exit_code=None)]
    result = job.aggregate_job_result(preflight, step0, scenarios)
    assert result["status"] == "partial_execution"
    assert result["overall_exit_code"] != 0


def test_scenario_result_passed_requires_both_attempted_and_zero_exit():
    assert _result("x", attempted=True, exit_code=0).passed is True
    assert _result("x", attempted=True, exit_code=1).passed is False
    assert _result("x", attempted=False, exit_code=None).passed is False


# ---------------------------------------------------------------------------
# main() -- proves the preflight gates Step 0, Step 0 gates the scenarios,
# both required scenarios are attempted once Step 0 passes (even if the
# first fails), and the overall exit code is wired to aggregate_job_result
# -- not to any single subprocess's own exit code in isolation.
# ---------------------------------------------------------------------------


def _base_argv(tmp_path):
    return [
        "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
        "--raw-clamp-value", "5000", "--out-dir", str(tmp_path / "out"),
    ]


def test_main_stops_immediately_and_never_attempts_step0_or_scenarios_when_preflight_fails(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(job, "_run", _tracking_fake_run(calls, exit_code=1))
    monkeypatch.setattr(
        job, "_run_preflight", _fake_run_preflight(exit_code=1, executed_count=0, passed_count=0, overall_passed=False)
    )
    exit_code = job.main(_base_argv(tmp_path))

    assert calls == []  # neither step0 nor either scenario was even attempted
    assert exit_code != 0
    result = json.loads((tmp_path / "out" / "job_result.json").read_text())
    assert result["status"] == "partial_execution"
    assert result["step0"]["attempted"] is False
    assert result["scenarios"] == []


def test_main_stops_before_step0_when_preflight_reports_zero_executed_cases_even_if_exit_code_is_zero(
    monkeypatch, tmp_path
):
    """Defense in depth: exit_code alone must never be trusted -- a
    preflight reporting executed_count=0 must block Step 0 even if its
    own exit code were (incorrectly) 0."""
    calls: list[str] = []
    monkeypatch.setattr(job, "_run", _tracking_fake_run(calls))
    monkeypatch.setattr(
        job, "_run_preflight", _fake_run_preflight(exit_code=0, executed_count=0, passed_count=0, overall_passed=False)
    )
    exit_code = job.main(_base_argv(tmp_path))

    assert calls == []
    assert exit_code != 0


def test_main_stops_before_step0_when_one_preflight_case_fails(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(job, "_run", _tracking_fake_run(calls))
    monkeypatch.setattr(
        job, "_run_preflight", _fake_run_preflight(exit_code=1, executed_count=11, passed_count=10, overall_passed=False)
    )
    exit_code = job.main(_base_argv(tmp_path))

    assert calls == []
    assert exit_code != 0


def test_main_proceeds_to_step0_when_preflight_reports_all_eleven_cases_passing(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(job, "_run", _tracking_fake_run(calls))
    monkeypatch.setattr(job, "_run_preflight", _fake_run_preflight())  # 11/11, overall_passed=True
    exit_code = job.main(_base_argv(tmp_path))

    assert "step0_differential_check" in calls
    assert exit_code == 0


def test_main_stops_immediately_and_never_attempts_scenarios_when_step0_fails(monkeypatch, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(job, "_run", _tracking_fake_run(calls, exit_code=1))
    monkeypatch.setattr(job, "_run_preflight", _fake_run_preflight())
    exit_code = job.main(_base_argv(tmp_path))

    assert calls == ["step0_differential_check"]  # neither scenario was attempted
    assert exit_code != 0


def test_main_attempts_both_scenarios_even_when_the_first_one_fails(monkeypatch, tmp_path):
    def fake_run(name, command):
        exit_code = 0 if name != "gemma_it_all" else 1
        return job.ScenarioResult(name=name, command=command, attempted=True, exit_code=exit_code)

    monkeypatch.setattr(job, "_run", fake_run)
    monkeypatch.setattr(job, "_run_preflight", _fake_run_preflight())
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
    monkeypatch.setattr(job, "_run_preflight", _fake_run_preflight())
    exit_code = job.main(_base_argv(tmp_path))
    result = json.loads((tmp_path / "out" / "job_result.json").read_text())
    assert result["status"] == "complete_pass"
    assert exit_code == 0


def test_main_writes_structured_result_file_even_on_step0_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        job, "_run", lambda name, command: job.ScenarioResult(name=name, command=command, attempted=True, exit_code=1)
    )
    monkeypatch.setattr(job, "_run_preflight", _fake_run_preflight())
    job.main(_base_argv(tmp_path))
    result_path = tmp_path / "out" / "job_result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text())
    assert result["status"] == "partial_execution"
    assert result["scenarios"] == []


def test_main_writes_structured_result_file_even_on_preflight_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        job, "_run", lambda name, command: job.ScenarioResult(name=name, command=command, attempted=True, exit_code=1)
    )
    monkeypatch.setattr(
        job, "_run_preflight", _fake_run_preflight(exit_code=1, executed_count=0, passed_count=0, overall_passed=False)
    )
    job.main(_base_argv(tmp_path))
    result_path = tmp_path / "out" / "job_result.json"
    assert result_path.exists()
    result = json.loads(result_path.read_text())
    assert result["status"] == "partial_execution"
    assert result["preflight"]["exit_code"] == 1
    assert result["step0"]["attempted"] is False
    assert result["scenarios"] == []


# ---------------------------------------------------------------------------
# _run_preflight -- reads the preflight's own JSON artifact independently
# of its exit code.
# ---------------------------------------------------------------------------


def test_run_preflight_reads_executed_and_passed_counts_from_the_json_artifact(monkeypatch, tmp_path):
    json_path = tmp_path / "symlink_preflight_result.json"
    json_path.write_text(
        json.dumps({"executed_count": 11, "passed_count": 11, "overall_passed": True}), encoding="utf-8"
    )

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(job.subprocess, "run", lambda command, check: _FakeCompleted())
    result = job._run_preflight(["fake", "command"], json_path)
    assert result.exit_code == 0
    assert result.executed_count == 11
    assert result.passed_count == 11
    assert result.overall_passed is True
    assert result.passed is True


def test_run_preflight_treats_a_missing_json_artifact_as_failure(monkeypatch, tmp_path):
    json_path = tmp_path / "does_not_exist.json"

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(job.subprocess, "run", lambda command, check: _FakeCompleted())
    result = job._run_preflight(["fake", "command"], json_path)
    assert result.executed_count is None
    assert result.passed_count is None
    assert result.overall_passed is None
    assert result.passed is False  # exit_code=0 alone is not enough


def test_run_preflight_treats_malformed_json_as_failure(monkeypatch, tmp_path):
    json_path = tmp_path / "symlink_preflight_result.json"
    json_path.write_text("not valid json {{{", encoding="utf-8")

    class _FakeCompleted:
        returncode = 0

    monkeypatch.setattr(job.subprocess, "run", lambda command, check: _FakeCompleted())
    result = job._run_preflight(["fake", "command"], json_path)
    assert result.passed is False


# ---------------------------------------------------------------------------
# command builders -- pure, no subprocess involved.
# ---------------------------------------------------------------------------


def test_build_preflight_command_invokes_the_standalone_script_not_pytest(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--out-dir", str(tmp_path),
        ]
    )
    out_path = tmp_path / "symlink_preflight_result.json"
    cmd = job.build_preflight_command(args, out_path=out_path)
    assert str(job.SCRIPT_DIR / "final_pairing_symlink_preflight.py") in cmd
    assert "--out" in cmd and cmd[cmd.index("--out") + 1] == str(out_path)
    assert "pytest" not in cmd


def test_build_preflight_command_includes_source_commit_when_given(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--source-commit", "46a8643", "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_preflight_command(args, out_path=tmp_path / "out.json")
    assert "--source-commit" in cmd and cmd[cmd.index("--source-commit") + 1] == "46a8643"


def test_build_preflight_command_omits_source_commit_when_not_given(tmp_path):
    args = job.parse_args(
        [
            "--model-path", "m", "--sae-path", "s", "--feature-idx", "250", "--mode", "steer",
            "--raw-clamp-value", "5000", "--out-dir", str(tmp_path),
        ]
    )
    cmd = job.build_preflight_command(args, out_path=tmp_path / "out.json")
    assert "--source-commit" not in cmd


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
