"""Tests for scripts/legacy/audit_and_retire_reserved_leaks.py (incident 4
remediation): scan + retire in one process, so a leaked index value never
crosses a process boundary or touches stdout/stderr -- only counts do.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "audit_and_retire_reserved_leaks.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_mod = _load("audit_and_retire_reserved_leaks", SCRIPT)


def _init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    return path


def _write_and_commit(repo: Path, relative_path: str, content: str, message: str = "seed commit") -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", relative_path], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def test_audit_and_retire_finds_and_retires_a_content_leak(tmp_path):
    repo = _init_repo(tmp_path)
    pool_path = repo / "reports" / "calibration_pool_reserved.json"
    audit_mod.pool_mod.write_reserved_pool(pool_path)

    before = json.loads(pool_path.read_text(encoding="utf-8"))
    leaked_index = before["reserved_features"][7]["index"]
    _write_and_commit(repo, "ledger.md", f"We already discussed feature {leaked_index} here.\n")

    result = audit_mod.audit_and_retire(repo, pool_path)
    assert result["tracked_tree_leak_count"] == 1
    assert result["commit_message_leak_count"] == 0
    assert result["retired_slot_count"] == 1

    after = json.loads(pool_path.read_text(encoding="utf-8"))
    after_indices = {r["index"] for r in after["reserved_features"]}
    assert leaked_index not in after_indices


def test_audit_and_retire_finds_leak_in_both_content_and_commit_message(tmp_path):
    repo = _init_repo(tmp_path)
    pool_path = repo / "reports" / "calibration_pool_reserved.json"
    audit_mod.pool_mod.write_reserved_pool(pool_path)

    before = json.loads(pool_path.read_text(encoding="utf-8"))
    leaked_index = before["reserved_features"][20]["index"]
    _write_and_commit(
        repo, "ledger.md", f"mentions {leaked_index}.\n", message=f"also mentions {leaked_index} here"
    )

    result = audit_mod.audit_and_retire(repo, pool_path)
    assert result["tracked_tree_leak_count"] == 1
    assert result["commit_message_leak_count"] == 1
    assert result["total_distinct_leaked"] == 1  # same index, union not sum
    assert result["retired_slot_count"] == 1


def test_audit_and_retire_no_op_on_a_clean_repo(tmp_path):
    repo = _init_repo(tmp_path)
    pool_path = repo / "reports" / "calibration_pool_reserved.json"
    audit_mod.pool_mod.write_reserved_pool(pool_path)
    before = pool_path.read_text(encoding="utf-8")
    _write_and_commit(repo, "ledger.md", "nothing sensitive here at all.\n")

    result = audit_mod.audit_and_retire(repo, pool_path)
    assert result == {
        "tracked_tree_leak_count": 0,
        "commit_message_leak_count": 0,
        "total_distinct_leaked": 0,
        "retired_slot_count": 0,
    }
    assert pool_path.read_text(encoding="utf-8") == before


def test_main_prints_counts_only_never_the_leaked_value(tmp_path):
    """The binding constraint made explicit as a test: run the real CLI
    end to end (subprocess, exactly as an operator would) against a repo
    with a genuine leak, and assert the leaked value itself never appears
    in stdout or stderr -- only the four count lines do."""
    repo = tmp_path
    _init_repo(repo)
    pool_path = repo / "reports" / "calibration_pool_reserved.json"
    audit_mod.pool_mod.write_reserved_pool(pool_path)

    before = json.loads(pool_path.read_text(encoding="utf-8"))
    leaked_index = before["reserved_features"][30]["index"]
    _write_and_commit(repo, "ledger.md", f"a paragraph mentioning {leaked_index} directly.\n")

    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0
    assert str(leaked_index) not in result.stdout
    assert str(leaked_index) not in result.stderr
    assert result.stdout == (
        "tracked-tree content leak count: 1\n"
        "commit-message leak count: 0\n"
        "distinct indices leaked (union): 1\n"
        "slots retired and replaced by continuing the seeded sequence: 1\n"
    )


def test_main_reports_zero_and_leaves_pool_untouched_when_clean(tmp_path):
    repo = tmp_path
    _init_repo(repo)
    pool_path = repo / "reports" / "calibration_pool_reserved.json"
    audit_mod.pool_mod.write_reserved_pool(pool_path)
    before = pool_path.read_text(encoding="utf-8")
    _write_and_commit(repo, "ledger.md", "a perfectly ordinary paragraph.\n")

    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 0
    assert "leak count: 0" in result.stdout
    assert pool_path.read_text(encoding="utf-8") == before


def test_main_fails_clearly_when_pool_absent(tmp_path):
    repo = tmp_path
    _init_repo(repo)
    _write_and_commit(repo, "ledger.md", "clean\n")

    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True)
    assert result.returncode == 1
    assert "not found" in result.stderr
