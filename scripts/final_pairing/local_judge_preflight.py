"""Standalone, pytest-free preflight for the LOCAL judge stage (stages 4-5
of `protocols/final_pairing/v1/one_allocation_dose_generation.json`) --
the separate, network-connected machine `final_pairing_judge_cli.py` runs
on, never the offline Tamia GPU allocation.

WHAT THIS PREFLIGHT DOES NOT CLAIM: it never makes a paid Anthropic API
call. Every case below either uses a real, zero-cost Lodestar code path
(cost estimation is pure local arithmetic; rubric/model-snapshot
validation reads no network) or exercises a deliberately-refused path
(missing credential, over-budget estimate, a mock judge model string) --
proving the REFUSAL machinery is real, not merely documented. `discovery_
preflight.py` (the GPU-side preflight) is explicit that IT does not claim
live-judge reachability; this file is that claim's actual home, still
without spending money.

Emits strict JSON: `{"expected_cases", "executed_cases", "passed_cases",
"cases": [...], "overall": "pass"|"fail"}` -- this file's OWN contract,
for the SEPARATE judge-stage machine; it does not track `discovery_
preflight.py`'s own (LA-B) contract, which is a different shape for a
different machine (`discovery_preflight.py` is the GPU-side preflight).
`Runner`/`CaseResult` are independently re-derived here rather than
importing that module's internals, since this preflight is meant to be
runnable standalone on a DIFFERENT machine that may not have this
repository's GPU-side dependencies installed at all.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

EXPECTED_CASE_COUNT = 9


class SetupFailure(RuntimeError):
    """A case raises this to report a missing optional dependency or
    environment precondition it cannot proceed without -- distinct from a
    genuine logic defect (`status='fail'`). Still causes a nonzero exit."""


@dataclass
class CaseResult:
    name: str
    status: str
    detail: str
    elapsed_seconds: float


class Runner:
    def __init__(self) -> None:
        self.results: list[CaseResult] = []

    def case(self, name: str, fn) -> None:
        start = time.monotonic()
        try:
            detail = fn()
            status = "pass"
        except SetupFailure as exc:
            detail = str(exc)
            status = "setup_failure"
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            status = "fail"
        elapsed = time.monotonic() - start
        self.results.append(CaseResult(name=name, status=status, detail=detail, elapsed_seconds=elapsed))


def run_all_cases() -> dict[str, Any]:
    import final_pairing_judge_cli as jc

    runner = Runner()

    # -----------------------------------------------------------------
    # 1. Lodestar is importable via the explicit D:-based source root.
    # -----------------------------------------------------------------
    def case_lodestar_importable() -> str:
        root = jc.ensure_lodestar_importable()
        import lodestar

        return f"lodestar importable from {root} (version {getattr(lodestar, '__version__', 'unknown')})"

    runner.case("lodestar_importable_from_explicit_d_source_root", case_lodestar_importable)

    # -----------------------------------------------------------------
    # 2. A bogus source root is refused, not silently accepted.
    # -----------------------------------------------------------------
    def case_bogus_source_root_refused() -> str:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            try:
                jc.ensure_lodestar_importable(tmp)
            except jc.causal_judge.CausalJudgeUnavailable:
                return "bogus source root correctly refused"
        raise AssertionError("expected ensure_lodestar_importable to refuse a directory with no lodestar package")

    runner.case("bogus_lodestar_source_root_is_refused", case_bogus_source_root_refused)

    # -----------------------------------------------------------------
    # 3. The pinned judge model is a real, resolved snapshot (not a moving
    # alias) -- checked via Lodestar's own real `is_snapshot`.
    # -----------------------------------------------------------------
    def case_pinned_snapshot() -> str:
        jc.ensure_lodestar_importable()
        try:
            from lodestar.judges.cost import is_snapshot
        except ImportError as exc:
            # lodestar.judges.__init__ eagerly imports lodestar.judges.cache, which needs
            # aiosqlite, even though is_snapshot() itself does not -- a package-structure fact,
            # not something this preflight can route around without editing Lodestar itself.
            raise SetupFailure(
                f"lodestar.judges.cost is not importable in this environment ({exc}) -- "
                f"lodestar.judges.__init__ eagerly imports lodestar.judges.cache, which needs "
                f"aiosqlite; run this preflight in an environment with Lodestar's full "
                f"dependency set installed"
            ) from exc

        model = "claude-sonnet-4-5-20250929"
        if not is_snapshot(model):
            raise AssertionError(f"{model!r} is not recognized as a pinned snapshot by Lodestar's own is_snapshot()")
        return f"{model} is a pinned snapshot"

    runner.case("pinned_judge_model_is_a_real_snapshot", case_pinned_snapshot)

    # -----------------------------------------------------------------
    # 4. Credential presence is reported as a bare bool, never the value;
    # absence is a clean, fail-closed refusal from require_api_key.
    # -----------------------------------------------------------------
    def case_credential_handling() -> str:
        present = jc.api_key_present()
        if not isinstance(present, bool):
            raise AssertionError("api_key_present() must return a bare bool")
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            try:
                jc.require_api_key()
                raise AssertionError("expected CredentialMissing with ANTHROPIC_API_KEY unset")
            except jc.CredentialMissing:
                pass
        finally:
            if saved is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved
        return f"key_present={present}; missing-credential path correctly fail-closed"

    runner.case("credential_present_as_bool_and_missing_case_fail_closed", case_credential_handling)

    # -----------------------------------------------------------------
    # 5. Scientific-mode mock refusal: a mock/no-op judge model can never
    # reach a function that persists attested evidence.
    # -----------------------------------------------------------------
    def case_mock_refused() -> str:
        for candidate in (jc.MOCK_JUDGE_MODEL_NAME, "Mock-Anything", "MOCK"):
            try:
                jc.assert_judge_model_is_attestable(candidate)
            except jc.ScientificModeMockRefused:
                continue
            raise AssertionError(f"expected {candidate!r} to be refused as a mock/test judge identity")
        jc.assert_judge_model_is_attestable("claude-sonnet-4-5-20250929")  # must NOT raise
        return "mock/no-op judge model names refused; real pinned snapshot accepted"

    runner.case("scientific_mode_refuses_mock_judge_models", case_mock_refused)

    # -----------------------------------------------------------------
    # 6. D:-only cache/output paths -- never C:.
    # -----------------------------------------------------------------
    def case_d_only_paths() -> str:
        for label, value in (
            ("DEFAULT_LODESTAR_SOURCE_ROOT", jc.DEFAULT_LODESTAR_SOURCE_ROOT),
            ("DEFAULT_CACHE_PATH", jc.DEFAULT_CACHE_PATH),
            ("DEFAULT_OUTPUT_ROOT", jc.DEFAULT_OUTPUT_ROOT),
        ):
            if not str(value).upper().startswith("D:"):
                raise AssertionError(f"{label}={value!r} is not D:-rooted")
        return "all default source/cache/output paths are D:-rooted"

    runner.case("d_only_cache_and_output_paths", case_d_only_paths)

    # -----------------------------------------------------------------
    # 7. Real, zero-cost cost estimate -- no API call is made.
    # -----------------------------------------------------------------
    import tempfile

    def case_real_zero_cost_estimate() -> str:
        jc.ensure_lodestar_importable()
        try:
            import aiosqlite  # noqa: F401
        except ImportError as exc:
            raise SetupFailure(
                "aiosqlite is not installed in this environment -- JudgeCache (used by run_estimate for "
                "cache-hit counting) needs it; run this preflight in an environment with Lodestar's full "
                "dependency set installed"
            ) from exc
        from lodestar.models import Generation

        generation = Generation(
            text="a paragraph about cheese", prompt="tell me about cheese", prompt_id="p0",
            condition="baseline", model_name="test-model", language="en", target_concept="cheese",
        )
        coherence, concept_relevance = jc.causal_judge.load_steering_rubrics()
        with tempfile.TemporaryDirectory() as tmp:
            report = jc.run_estimate(
                generations=[generation], rubrics=[coherence, concept_relevance], repeats=1,
                judge_model="claude-sonnet-4-5-20250929", cache_path=Path(tmp) / "cache.sqlite",
            )
        if report["predicted_cost_usd"] <= 0:
            raise AssertionError(f"expected a positive predicted cost, got {report['predicted_cost_usd']}")
        return f"real estimate: {report['total_judgments']} judgments, ${report['predicted_cost_usd']:.4f} predicted, 0 API calls made"

    runner.case("real_zero_cost_estimate_before_any_paid_call", case_real_zero_cost_estimate)

    # -----------------------------------------------------------------
    # 8. Budget refusal: an over-budget estimate STOPS before any call.
    # -----------------------------------------------------------------
    def case_budget_refusal() -> str:
        try:
            jc.assert_within_budget(30.0, budget_usd=25.0)
        except jc.BudgetExceeded:
            pass
        else:
            raise AssertionError("expected BudgetExceeded for a $30 estimate against a $25 budget")
        jc.assert_within_budget(10.0, budget_usd=25.0)  # must not raise
        return "over-budget estimate correctly refused; under-budget estimate correctly passes"

    runner.case("budget_ceiling_refuses_before_any_paid_call", case_budget_refusal)

    # -----------------------------------------------------------------
    # 9. Real CLI wiring: the argparse parser exposes every required
    # subcommand with its required flags.
    # -----------------------------------------------------------------
    def case_cli_wiring() -> str:
        parser = jc.build_arg_parser()
        subparsers_action = next(a for a in parser._actions if a.dest == "command")
        expected = {"estimate-sweep", "judge-sweep", "write-selection", "judge-confirmation"}
        if set(subparsers_action.choices) != expected:
            raise AssertionError(f"expected subcommands {expected}, got {set(subparsers_action.choices)}")
        return f"CLI exposes subcommands: {sorted(expected)}"

    runner.case("real_cli_exposes_every_required_subcommand", case_cli_wiring)

    passed = sum(1 for r in runner.results if r.status == "pass")
    return {
        "expected_cases": EXPECTED_CASE_COUNT,
        "executed_cases": len(runner.results),
        "passed_cases": passed,
        "cases": [asdict(r) for r in runner.results],
        "overall": "pass" if (passed == EXPECTED_CASE_COUNT and len(runner.results) == EXPECTED_CASE_COUNT) else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    report = run_all_cases()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
