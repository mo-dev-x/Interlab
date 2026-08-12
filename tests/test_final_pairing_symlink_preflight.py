"""Ordinary (non-nightly) unit tests for scripts/legacy/final_pairing_
symlink_preflight.py -- orchestrator review, 2026-08-17 ("Make the Tamia
symlink preflight self-contained and pytest-free"). Tests the RUNNER
machinery (CaseResult classification, run_preflight's aggregation and
cleanup, main()'s CLI/exit-code/JSON wiring) using FAKE cases and
monkeypatched capability probes -- no real symlinks needed, so this file
runs deterministically on any platform, including this project's own
Windows dev machine.

The REAL 11 named cases against REAL symlinks are proven separately:
directly here for the one case that needs no symlink at all
(case_regular_in_snapshot_file_passes), and end-to-end via
tests/test_final_pairing_symlink_preflight_nightly.py's real-subprocess
test on a symlink-capable platform (that file is unchanged developer
regression coverage, not part of the scheduled Tamia gate anymore).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_symlink_preflight as preflight  # noqa: E402


def _raise(exc: BaseException):
    raise exc


# ---------------------------------------------------------------------------
# CASES registry -- structural invariants.
# ---------------------------------------------------------------------------


def test_cases_registry_has_exactly_eleven_entries():
    assert len(preflight.CASES) == 11
    assert preflight.EXPECTED_CASE_COUNT == 11


def test_cases_registry_names_match_the_dispatch_required_set():
    names = {name for name, _expected, _fn in preflight.CASES}
    assert names == {
        "intended_symlink_passes_snapshot_guard",
        "intended_symlink_passes_exact_sae_family_guard",
        "intended_symlink_passes_physical_cache_guard",
        "wrong_snapshot_revision_fails",
        "sibling_prefix_revision_fails",
        "attn_out_fails",
        "mlp_out_fails",
        "transcoder_fails",
        "escaping_symlink_fails_physical_containment",
        "regular_in_snapshot_file_passes",
        "duplicate_captured_paths_are_independently_accepted_and_retained",
    }


def _assert_no_pytest_import_or_invocation(source_path: Path) -> None:
    """Parses the AST (not a raw substring search, which would also flag
    this docstring's own prose about WHY pytest is avoided) and asserts:
    no `import pytest`/`from pytest import ...`, and no string literal
    anywhere in the code is exactly "pytest" (which would catch a
    subprocess argument list like [..., "-m", "pytest", ...])."""
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


def test_no_pytest_dependency_anywhere_in_the_standalone_script():
    """The entire reason this script exists: ~/sprint-venv has no pytest."""
    _assert_no_pytest_import_or_invocation(Path(preflight.__file__))


# ---------------------------------------------------------------------------
# _expect_raises / _expect_passes -- the assertion-classification helpers.
# ---------------------------------------------------------------------------


def test_expect_raises_accepts_the_exact_exception_type():
    preflight._expect_raises(ValueError, lambda: _raise(ValueError("x")))  # must not raise


def test_expect_raises_rejects_a_different_exception_type():
    with pytest.raises(AssertionError, match="expected ValueError, got TypeError"):
        preflight._expect_raises(ValueError, lambda: _raise(TypeError("x")))


def test_expect_raises_rejects_no_exception_at_all():
    with pytest.raises(AssertionError, match="returned normally"):
        preflight._expect_raises(ValueError, lambda: None)


def test_expect_passes_accepts_a_clean_call():
    preflight._expect_passes(lambda: None)  # must not raise


def test_expect_passes_rejects_any_exception():
    with pytest.raises(AssertionError, match="expected the call to pass"):
        preflight._expect_passes(lambda: _raise(ValueError("boom")))


# ---------------------------------------------------------------------------
# _run_case -- classification into passed / assertion_failure / unexpected_exception.
# ---------------------------------------------------------------------------


def test_run_case_classifies_a_clean_case_as_passed(tmp_path):
    result = preflight._run_case("x", "must pass", lambda case_dir: None, tmp_path)
    assert result.passed is True
    assert result.actual_outcome == "passed"


def test_run_case_classifies_an_assertion_error_as_assertion_failure(tmp_path):
    def _case(case_dir):
        raise AssertionError("containment guard misbehaved")

    result = preflight._run_case("x", "must pass", _case, tmp_path)
    assert result.passed is False
    assert result.actual_outcome.startswith("assertion_failure:")
    assert "containment guard misbehaved" in result.actual_outcome


def test_run_case_classifies_any_other_exception_as_unexpected(tmp_path):
    def _case(case_dir):
        raise ValueError("bug in case setup code")

    result = preflight._run_case("x", "must pass", _case, tmp_path)
    assert result.passed is False
    assert result.actual_outcome.startswith("unexpected_exception: ValueError:")


# ---------------------------------------------------------------------------
# _probe_symlink_capability -- deterministic, monkeypatched (both
# directions), so this doesn't depend on this machine's own privilege.
# ---------------------------------------------------------------------------


def test_probe_symlink_capability_returns_none_when_symlink_creation_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "symlink_to", lambda self, target: None)
    assert preflight._probe_symlink_capability(tmp_path) is None


def test_probe_symlink_capability_returns_a_reason_string_on_oserror(monkeypatch, tmp_path):
    def _raise_oserror(self, target):
        raise OSError("no privilege")

    monkeypatch.setattr(Path, "symlink_to", _raise_oserror)
    reason = preflight._probe_symlink_capability(tmp_path)
    assert reason is not None
    assert "OSError" in reason


# ---------------------------------------------------------------------------
# run_preflight -- aggregation and cleanup, using FAKE cases (no real
# symlinks needed) so this runs deterministically on any platform.
# ---------------------------------------------------------------------------


def _fake_case_pass(case_dir):
    return None


def _fake_case_fail(case_dir):
    raise AssertionError("fake failure")


def test_run_preflight_reports_setup_failure_and_zero_executed_when_capability_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: "OSError: simulated")
    result = preflight.run_preflight(tmp_path, None)
    assert result["executed_count"] == 0
    assert result["passed_count"] == 0
    assert result["overall_passed"] is False
    assert result["setup_failure"] == "OSError: simulated"
    assert result["cases"] == []


def test_run_preflight_passes_when_all_expected_cases_pass(monkeypatch, tmp_path):
    fake_cases = [(f"fake_case_{i}", "must pass", _fake_case_pass) for i in range(3)]
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: None)
    monkeypatch.setattr(preflight, "CASES", fake_cases)
    monkeypatch.setattr(preflight, "EXPECTED_CASE_COUNT", 3)
    result = preflight.run_preflight(tmp_path, "46a8643")
    assert result["executed_count"] == 3
    assert result["passed_count"] == 3
    assert result["overall_passed"] is True
    assert result["source_commit"] == "46a8643"
    assert result["case_count"] == 3


def test_run_preflight_fails_overall_when_one_case_fails(monkeypatch, tmp_path):
    fake_cases = [
        ("fake_case_0", "must pass", _fake_case_pass),
        ("fake_case_1", "must pass", _fake_case_fail),
        ("fake_case_2", "must pass", _fake_case_pass),
    ]
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: None)
    monkeypatch.setattr(preflight, "CASES", fake_cases)
    monkeypatch.setattr(preflight, "EXPECTED_CASE_COUNT", 3)
    result = preflight.run_preflight(tmp_path, None)
    assert result["executed_count"] == 3
    assert result["passed_count"] == 2
    assert result["overall_passed"] is False


def test_run_preflight_fails_when_zero_cases_are_registered(monkeypatch, tmp_path):
    """Zero executed cases must never report success, even though the
    (empty) loop trivially completes without raising anything."""
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: None)
    monkeypatch.setattr(preflight, "CASES", [])
    result = preflight.run_preflight(tmp_path, None)
    assert result["executed_count"] == 0
    assert result["overall_passed"] is False


def test_run_preflight_cleans_up_its_scratch_tree_even_when_a_case_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: None)
    monkeypatch.setattr(preflight, "CASES", [("fake_case_0", "must pass", _fake_case_fail)])
    monkeypatch.setattr(preflight, "EXPECTED_CASE_COUNT", 1)
    preflight.run_preflight(tmp_path, None)
    assert not (tmp_path / "final_pairing_symlink_preflight_scratch").exists()


def test_run_preflight_cleans_up_even_when_the_capability_probe_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "_probe_symlink_capability", lambda scratch_root: "nope")
    preflight.run_preflight(tmp_path, None)
    assert not (tmp_path / "final_pairing_symlink_preflight_scratch").exists()


# ---------------------------------------------------------------------------
# main() -- CLI/exit-code/JSON-writing wiring, with run_preflight faked
# entirely (its own correctness is proven above).
# ---------------------------------------------------------------------------


def _fake_passing_result(**overrides):
    result = {
        "preflight_name": "final_pairing_symlink_preflight", "schema_version": 1, "source_commit": None,
        "platform": "x", "case_count": 11, "executed_count": 11, "passed_count": 11,
        "overall_passed": True, "setup_failure": None, "cases": [],
    }
    result.update(overrides)
    return result


def test_main_exits_zero_and_writes_json_when_overall_passed(monkeypatch, tmp_path):
    fake_result = _fake_passing_result()
    monkeypatch.setattr(preflight, "run_preflight", lambda base, source_commit: fake_result)
    exit_code = preflight.main(["--work-dir", str(tmp_path)])
    assert exit_code == 0
    written = json.loads((tmp_path / "symlink_preflight_result.json").read_text())
    assert written == fake_result


def test_main_exits_nonzero_when_overall_passed_is_false(monkeypatch, tmp_path):
    fake_result = _fake_passing_result(overall_passed=False, executed_count=0, passed_count=0, setup_failure="nope")
    monkeypatch.setattr(preflight, "run_preflight", lambda base, source_commit: fake_result)
    exit_code = preflight.main(["--work-dir", str(tmp_path)])
    assert exit_code != 0


def test_main_respects_explicit_out_path(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "run_preflight", lambda base, source_commit: _fake_passing_result())
    out_path = tmp_path / "custom" / "result.json"
    preflight.main(["--work-dir", str(tmp_path), "--out", str(out_path)])
    assert out_path.exists()


def test_main_passes_source_commit_through_to_run_preflight(monkeypatch, tmp_path):
    captured = {}

    def fake_run_preflight(base, source_commit):
        captured["source_commit"] = source_commit
        return _fake_passing_result()

    monkeypatch.setattr(preflight, "run_preflight", fake_run_preflight)
    preflight.main(["--work-dir", str(tmp_path), "--source-commit", "46a8643"])
    assert captured["source_commit"] == "46a8643"


def test_main_uses_slurm_tmpdir_env_var_when_work_dir_not_given(monkeypatch, tmp_path):
    captured = {}

    def fake_run_preflight(base, source_commit):
        captured["base"] = base
        return _fake_passing_result()

    monkeypatch.setattr(preflight, "run_preflight", fake_run_preflight)
    monkeypatch.setenv("SLURM_TMPDIR", str(tmp_path))
    preflight.main([])
    assert captured["base"] == tmp_path


def test_resolve_base_dir_falls_back_to_a_fresh_tempdir_when_neither_is_given(monkeypatch):
    import shutil

    monkeypatch.delenv("SLURM_TMPDIR", raising=False)
    base = preflight._resolve_base_dir(None)
    try:
        assert base.exists()
        assert "final_pairing_symlink_preflight_" in base.name
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# One REAL case, exercised for real (no symlink privilege required) --
# case_regular_in_snapshot_file_passes never creates a symlink at all.
# ---------------------------------------------------------------------------


def test_case_regular_in_snapshot_file_passes_runs_for_real_against_the_real_validators(tmp_path):
    preflight.case_regular_in_snapshot_file_passes(tmp_path)  # must not raise
