"""Tamia GPU job wrapper for Gemma mechanical acceptance (orchestrator
review, 2026-08-13, "aggregate job failure"): Slurm job 406092 ended
COMPLETED/0 even though both required Gemma scenarios exited 1 -- whatever
ad hoc shell chaining ran them did not aggregate exit codes at all. This
module makes that aggregation itself deterministic and testable, rather
than leaving it to be re-typed correctly (or not) in a Slurm script each
time.

Scope (per the "Next GPU job" instruction, 2026-08-13): Step 0
(scripts/legacy/gemma3_tool_diff_test.py) only, then the two REQUIRED
Gemma-3-12b-it scenarios (--positions all, --positions generated_only,
via scripts/legacy/final_pairing_harness.py) at --max-new-tokens 8. No
Qwen rerun.

Rules this module enforces, matching the acceptance criteria exactly:
  - Step 0 failure stops immediately -- neither Gemma scenario is even
    attempted (no point spending GPU time on scenarios if the shared
    mechanism itself is unproven).
  - Once Step 0 passes, BOTH required scenarios are still run and their
    exit codes collected, even if the first one fails -- diagnostic
    completeness, not fail-fast, past that gate.
  - The overall exit code is nonzero if Step 0 OR ANY required scenario
    failed -- a later scenario succeeding can never overwrite an earlier
    failure. This is exactly the job-406092 bug: aggregate_job_result
    computes status from ALL scenario results together, never by
    sequentially overwriting a running "last exit code" variable.
  - The structured result distinguishes three states: complete_pass
    (everything ran and passed), failure (everything ran, something
    failed), partial_execution (Step 0 failed, so the required scenarios
    were never even attempted).

Do not: run GPU work locally (this module only shells out to the two
scripts above; it is never invoked with real weights outside Tamia),
rerun Qwen (out of scope for this job), add behavioral thresholds (the
gates it aggregates are exactly the ones those two scripts already
define, nothing new is invented here).

Orchestrator review, 2026-08-16 ("Correct and comprehensively audit Gemma
path-containment guards", live job 406957): added a symlink-containment
PREFLIGHT step, run BEFORE Step 0 -- job 406957 proved the local-only
resolver, loader-id validation, and shape shim all work, but a separate
audit found validate_sae_files_match_snapshot (final_pairing_targets.py)
was still calling Path.resolve() (follows symlinks -- wrong for a logical
identity check) with a str.startswith() containment comparison (unsafe
sibling-prefix false-match). That defect is fixed; this preflight step
exists so a REAL Hugging Face cache's actual symlink layout is proven
against all three SAE-file/path guards -- inside the real GPU allocation,
not the login node, since that is the only place real symlink creation
and this cache's true on-disk shape are both available -- before either
Step 0 or a Gemma scenario spends any GPU time. A preflight failure stops
the job immediately, exactly like a Step 0 failure does -- neither Step 0
nor either Gemma scenario is attempted -- and is recorded as its own
`preflight` entry in job_result.json, independent of `step0`.

Orchestrator review, 2026-08-17 ("Make the Tamia symlink preflight
self-contained and pytest-free"): the 2026-08-16 preflight invoked pytest
(`tests/test_final_pairing_symlink_preflight_nightly.py`, `-m nightly`) --
Lab Assistant B correctly stopped before submission because
~/sprint-venv (Tamia's real, shared scientific environment) has no
pytest/pluggy/iniconfig installed, and installing them there is forbidden.
This wrapper now invokes scripts/legacy/final_pairing_symlink_preflight.py
instead -- a standalone, standard-library-only script (see that module's
own docstring for its 11-case design) -- via sys.executable directly, no
pytest anywhere in the scheduled path. That pytest-based nightly test file
still exists, unchanged, as independent developer regression coverage; it
is simply no longer what this wrapper runs. Beyond trusting the
subprocess's own exit code, this wrapper INDEPENDENTLY re-reads the
preflight's own JSON artifact and re-verifies executed_count == 11,
passed_count == 11, and overall_passed == true before treating it as
passed -- defense in depth against a hypothetical bug in the preflight
script's own exit-code logic, not merely trusting a single signal.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import final_pairing_symlink_preflight as symlink_preflight  # noqa: E402


@dataclass
class ScenarioResult:
    name: str
    command: list[str]
    attempted: bool
    exit_code: int | None

    @property
    def passed(self) -> bool:
        return self.attempted and self.exit_code == 0


@dataclass
class PreflightResult:
    """Distinct from ScenarioResult: the preflight's own JSON artifact
    (executed_count/passed_count/overall_passed) is independently
    re-checked here rather than trusting the subprocess's exit code
    alone -- defense in depth against a hypothetical bug in the preflight
    script's own exit-code logic."""

    name: str
    command: list[str]
    attempted: bool
    exit_code: int | None
    json_path: str
    executed_count: int | None
    passed_count: int | None
    overall_passed: bool | None

    @property
    def passed(self) -> bool:
        return (
            self.attempted
            and self.exit_code == 0
            and self.executed_count == symlink_preflight.EXPECTED_CASE_COUNT
            and self.passed_count == symlink_preflight.EXPECTED_CASE_COUNT
            and self.overall_passed is True
        )


def _run(name: str, command: list[str]) -> ScenarioResult:
    completed = subprocess.run(command, check=False)
    return ScenarioResult(name=name, command=command, attempted=True, exit_code=completed.returncode)


def _run_preflight(command: list[str], json_path: Path) -> PreflightResult:
    """Runs the standalone preflight, then INDEPENDENTLY re-reads its own
    JSON artifact (not merely the subprocess exit code) for executed_
    count/passed_count/overall_passed -- a missing or unparseable JSON
    file (e.g. the process crashed before writing one) leaves all three
    as None, which PreflightResult.passed treats as failure, never as an
    ambiguous pass."""
    completed = subprocess.run(command, check=False)
    executed_count = passed_count = overall_passed = None
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            executed_count = data.get("executed_count")
            passed_count = data.get("passed_count")
            overall_passed = data.get("overall_passed")
        except (json.JSONDecodeError, OSError):
            pass
    return PreflightResult(
        name="symlink_containment_preflight",
        command=command,
        attempted=True,
        exit_code=completed.returncode,
        json_path=str(json_path),
        executed_count=executed_count,
        passed_count=passed_count,
        overall_passed=overall_passed,
    )


def build_preflight_command(args: argparse.Namespace, *, out_path: Path) -> list[str]:
    """Invokes scripts/legacy/final_pairing_symlink_preflight.py directly
    via sys.executable -- standard-library-only, no pytest anywhere in
    this command. --out is the wrapper-controlled, known path
    _run_preflight reads back afterward; --work-dir is deliberately left
    unset so the preflight resolves its own scratch root from
    $SLURM_TMPDIR (the normal case inside a real Tamia allocation)."""
    cmd = [
        sys.executable, str(SCRIPT_DIR / "final_pairing_symlink_preflight.py"),
        "--out", str(out_path),
    ]
    if args.source_commit is not None:
        cmd += ["--source-commit", args.source_commit]
    return cmd


def build_step0_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable, str(SCRIPT_DIR / "gemma3_tool_diff_test.py"),
        "--model-path", args.model_path, "--sae-path", args.sae_path,
        "--sweep-module", args.sweep_module,
        "--feature-idx", str(args.feature_idx), "--mode", args.mode,
        "--dose-multiple", str(args.dose_multiple), "--positions", "all",
        "--prompt", args.prompt, "--seed", str(args.seed),
        "--max-new-tokens", str(args.step0_max_new_tokens),
        "--device", args.device, "--dtype", args.dtype,
    ]


def build_gemma_scenario_command(args: argparse.Namespace, *, positions: str, out_path: Path) -> list[str]:
    cmd = [
        sys.executable, str(SCRIPT_DIR / "final_pairing_harness.py"),
        "--target", "gemma-3-12b-it",
        "--model-path", args.model_path, "--sae-path", args.sae_path,
        "--feature-idx", str(args.feature_idx), "--mode", args.mode,
        "--raw-clamp-value", str(args.raw_clamp_value),
        "--positions", positions,
        "--prompt", args.prompt, "--seed", str(args.seed),
        "--max-new-tokens", str(args.scenario_max_new_tokens),
        "--device", args.device, "--dtype", args.dtype,
        "--out", str(out_path),
    ]
    if args.expected_model_revision is not None:
        cmd += ["--expected-model-revision", args.expected_model_revision]
    if args.expected_sae_revision is not None:
        cmd += ["--expected-sae-revision", args.expected_sae_revision]
    return cmd


def aggregate_job_result(
    preflight: PreflightResult, step0: ScenarioResult, scenarios: list[ScenarioResult]
) -> dict[str, Any]:
    """Structured result distinguishing complete_pass / failure /
    partial_execution -- see module docstring for the exact rules.
    overall_exit_code is 0 iff status == "complete_pass"; status is
    computed from ALL results together (never by sequentially
    overwriting a running "last exit code"), so a later scenario passing
    can never mask an earlier one's failure.

    Orchestrator review, 2026-08-16: preflight is checked FIRST, ahead of
    step0 -- a failed preflight means step0 itself was never attempted
    either (attempted=False in the ScenarioResult main() passes in), and
    both cases map to the SAME "partial_execution" status as an existing
    Step 0 failure already did; the two are recorded as distinct entries
    in the returned dict (preflight vs step0) so a reader can always tell
    which gate actually stopped the job, never collapsed into one field."""
    if not preflight.passed or not step0.passed:
        status = "partial_execution"
    elif all(s.attempted for s in scenarios) and all(s.passed for s in scenarios):
        status = "complete_pass"
    elif all(s.attempted for s in scenarios):
        status = "failure"
    else:
        status = "partial_execution"
    return {
        "status": status,
        "overall_exit_code": 0 if status == "complete_pass" else 1,
        "preflight": asdict(preflight),
        "step0": asdict(step0),
        "scenarios": [asdict(s) for s in scenarios],
    }


def _write_result(out_dir: Path, result: dict[str, Any]) -> None:
    out_path = out_dir / "job_result.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True)
    p.add_argument("--expected-model-revision", default=None)
    p.add_argument("--expected-sae-revision", default=None)
    p.add_argument("--feature-idx", type=int, required=True)
    p.add_argument("--mode", choices=["steer", "ablate"], required=True)
    p.add_argument("--dose-multiple", type=float, default=4.0, help="Step 0's own manifest-based check.")
    p.add_argument("--raw-clamp-value", type=float, required=True, help="Used by both required Gemma scenarios.")
    p.add_argument("--prompt", default="Tell me about your day.")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--step0-max-new-tokens", type=int, default=64)
    p.add_argument("--scenario-max-new-tokens", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--sweep-module", default=str(SCRIPT_DIR / "gemma3_sweep.py"))
    p.add_argument("--source-commit", default=None, help="Recorded in the preflight's JSON artifact if supplied.")
    p.add_argument("--out-dir", required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    preflight_json_path = out_dir / "symlink_preflight_result.json"
    preflight = _run_preflight(build_preflight_command(args, out_path=preflight_json_path), preflight_json_path)
    if not preflight.passed:
        step0_not_attempted = ScenarioResult(
            name="step0_differential_check", command=build_step0_command(args), attempted=False, exit_code=None
        )
        result = aggregate_job_result(preflight, step0_not_attempted, [])
        _write_result(out_dir, result)
        return result["overall_exit_code"]

    step0 = _run("step0_differential_check", build_step0_command(args))
    if not step0.passed:
        result = aggregate_job_result(preflight, step0, [])
        _write_result(out_dir, result)
        return result["overall_exit_code"]

    scenario_specs = [
        ("gemma_it_all", "all", out_dir / "gemma_3_12b_it_all.json"),
        ("gemma_it_generated_only", "generated_only", out_dir / "gemma_3_12b_it_generated_only.json"),
    ]
    scenarios = [
        _run(name, build_gemma_scenario_command(args, positions=positions, out_path=out_path))
        for name, positions, out_path in scenario_specs
    ]
    result = aggregate_job_result(preflight, step0, scenarios)
    _write_result(out_dir, result)
    return result["overall_exit_code"]


if __name__ == "__main__":
    sys.exit(main())
