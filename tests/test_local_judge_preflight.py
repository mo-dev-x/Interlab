"""Tests for scripts/final_pairing/local_judge_preflight.py.

Tolerant of this specific dev machine's disclosed dependency gap
(`aiosqlite` is not installed here, by design -- see
test_final_pairing_judge_cli.py's own docstring for the same fact): this
test asserts every case reaches either "pass" or the SPECIFIC, expected
"setup_failure" for that reason, never "fail" -- so a genuine logic
regression is still caught even though this machine cannot achieve a
literal green `overall`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import local_judge_preflight as preflight  # noqa: E402

REAL_LODESTAR_ROOT = Path("D:/lodstar")

pytestmark = pytest.mark.skipif(
    not (REAL_LODESTAR_ROOT / "lodestar" / "__init__.py").is_file(),
    reason="requires the real D:/lodstar checkout present in this development environment",
)


@pytest.fixture(autouse=True)
def _lodestar_source_root_env(monkeypatch):
    """final_pairing_judge_cli.ensure_lodestar_importable() no longer has
    any hardcoded fallback (docs/repo_cleanup_plan.md Phase 3 P0 follow-
    up) -- case 1 below calls it with no argument, so it now requires
    LODESTAR_SOURCE_ROOT. This module's whole premise is REAL_LODESTAR_ROOT
    (d:/lodstar), so every test gets it for free."""
    monkeypatch.setenv("LODESTAR_SOURCE_ROOT", str(REAL_LODESTAR_ROOT))


_KNOWN_SETUP_FAILURE_CASES = {
    "pinned_judge_model_is_a_real_snapshot",
    "real_zero_cost_estimate_before_any_paid_call",
}


def test_expected_case_count_matches_the_actual_number_of_registered_cases():
    report = preflight.run_all_cases()
    assert report["expected_cases"] == preflight.EXPECTED_CASE_COUNT
    assert report["executed_cases"] == preflight.EXPECTED_CASE_COUNT


def test_no_case_reports_a_genuine_logic_failure():
    report = preflight.run_all_cases()
    genuine_failures = [c for c in report["cases"] if c["status"] == "fail"]
    assert genuine_failures == [], genuine_failures


def test_every_case_passes_or_hits_the_specific_known_aiosqlite_gap():
    report = preflight.run_all_cases()
    for case in report["cases"]:
        if case["status"] == "pass":
            continue
        assert case["status"] == "setup_failure", case
        assert case["name"] in _KNOWN_SETUP_FAILURE_CASES, case
        assert "aiosqlite" in case["detail"], case


def test_pinned_snapshot_case_passes_once_the_import_gate_alone_is_resolved(monkeypatch):
    """Proves the `pinned_judge_model_is_a_real_snapshot` case's
    `setup_failure` is caused SPECIFICALLY by `lodestar.judges.__init__`'s
    eager `aiosqlite` import (nothing more) -- faking just enough of
    `aiosqlite` to satisfy that import (this case never calls
    `aiosqlite.connect`, unlike the cost-estimate case, which genuinely
    needs a working async sqlite backend and is out of scope for this
    narrower proof) makes it pass for real."""
    import types

    monkeypatch.setitem(sys.modules, "aiosqlite", types.ModuleType("aiosqlite"))
    for name in list(sys.modules):
        if name == "lodestar" or name.startswith("lodestar."):
            del sys.modules[name]
    try:
        report = preflight.run_all_cases()
    finally:
        for name in list(sys.modules):
            if name == "lodestar" or name.startswith("lodestar."):
                del sys.modules[name]
    by_name = {c["name"]: c for c in report["cases"]}
    assert by_name["pinned_judge_model_is_a_real_snapshot"]["status"] == "pass"
