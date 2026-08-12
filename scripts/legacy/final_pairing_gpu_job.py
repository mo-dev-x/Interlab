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
Step 0 or a Gemma scenario spends any GPU time. Runs tests/test_final_
pairing_symlink_preflight_nightly.py (marked @pytest.mark.nightly, so the
default per-commit `-m "not nightly"` gate excludes it; this wrapper
explicitly overrides that with `-m nightly`). A preflight failure stops
the job immediately, exactly like a Step 0 failure does -- neither Step 0
nor either Gemma scenario is attempted -- and is recorded as its own
`preflight` entry in job_result.json, independent of `step0`.
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


@dataclass
class ScenarioResult:
    name: str
    command: list[str]
    attempted: bool
    exit_code: int | None

    @property
    def passed(self) -> bool:
        return self.attempted and self.exit_code == 0


def _run(name: str, command: list[str]) -> ScenarioResult:
    completed = subprocess.run(command, check=False)
    return ScenarioResult(name=name, command=command, attempted=True, exit_code=completed.returncode)


def build_preflight_command() -> list[str]:
    """Runs tests/test_final_pairing_symlink_preflight_nightly.py -- a
    real-filesystem (no mocks) proof that the local snapshot's actual HF
    cache symlink layout passes every applicable containment guard,
    inside this allocation. -m nightly explicitly overrides pyproject.
    toml's own `addopts = ... -m "not nightly"` default, which otherwise
    excludes this file from a plain `pytest` invocation. Takes no CLI
    arguments -- the preflight targets a fixed test file, not anything
    derived from --model-path/--sae-path (those are validated for real by
    Step 0 and the Gemma scenarios that follow)."""
    return [
        sys.executable, "-m", "pytest",
        str(REPO_ROOT / "tests" / "test_final_pairing_symlink_preflight_nightly.py"),
        "-m", "nightly", "-q",
    ]


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
    preflight: ScenarioResult, step0: ScenarioResult, scenarios: list[ScenarioResult]
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
    p.add_argument("--out-dir", required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    preflight = _run("symlink_containment_preflight", build_preflight_command())
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
