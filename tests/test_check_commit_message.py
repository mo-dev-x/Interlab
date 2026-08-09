"""Tests for scripts/legacy/check_commit_message.py (Prereg v1.10 SS13.4).

Covers the leak SS13.4 documents that the pre-commit index scan
structurally cannot see: a commit MESSAGE recording a tally ("3
surface-form, 3 semantic, 4 denominator") or a reserved index, written
into history any rater may read. Two independent checks, tested
separately and together: reserved-index reuse from
check_reserved_indices.py, and the new composition-fragment heuristic.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "check_commit_message.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load("check_commit_message", SCRIPT)

RESERVED = [12403, 8950, 250]


# ---------------------------------------------------------------------------
# find_composition_fragments
# ---------------------------------------------------------------------------


def test_the_actual_incident_message_is_flagged():
    hits = checker.find_composition_fragments("3 surface-form, 3 semantic, 4 denominator")
    assert len(hits) == 3


def test_number_then_bucket_word_is_flagged():
    assert checker.find_composition_fragments("3 surface-form calls this batch") != []
    assert checker.find_composition_fragments("4 denominator rows") != []


def test_bucket_word_then_number_is_flagged():
    assert checker.find_composition_fragments("denominator: 3 this round") != []
    assert checker.find_composition_fragments("tally = 7") != []


def test_bare_fraction_adjacent_to_a_class_name_is_flagged():
    """Gated, not unconditional (5th-incident fix): a fraction only fires
    when a real taxonomy class name shares its line."""
    assert checker.find_composition_fragments("closed 9/40 surface-form this pass") != []


def test_rows_and_classes_alone_pass():
    """SS13.4 explicitly: 'Rows and classes are fine; counts by bucket
    are not.'"""
    assert checker.find_composition_fragments("11763 -> class 12 (from class 9)") == []
    assert checker.find_composition_fragments("retrofit row 9105 to class 12") == []


def test_ordinary_commit_messages_pass():
    assert checker.find_composition_fragments("fix semantic search, closes #42") == []
    assert checker.find_composition_fragments("bump numpy to 2.1, fixes 3 tests") == []
    assert checker.find_composition_fragments("Add gemma3_tool.py and its 20 tests") == []


# ---------------------------------------------------------------------------
# 5th-incident fix: bare N/M fractions are gated on an adjacent taxonomy
# class name. Exact cases from the incident report, both directions --
# per the binding rule (check_reserved_indices.py's incident-4 docstring),
# narrowing a detector is exactly where a false negative can silently open
# a hole, so both what must still be blocked AND what must now pass are
# pinned here, not left to a single regex test.
# ---------------------------------------------------------------------------


def test_false_positive_job_id_pair_passes():
    """The actual incident: two ordinary Gemma tool feature indices,
    written as a slash pair, with no composition vocabulary nearby."""
    assert checker.find_composition_fragments("Wire up features 3500/4500 in the tool") == []


def test_false_positive_record_count_pair_passes():
    assert checker.find_composition_fragments("sweep progress: records 900/1736") == []


def test_false_positive_identical_pair_passes():
    assert checker.find_composition_fragments("all 16/16 doses covered") == []


def test_false_positive_bare_fraction_no_adjacency_word_passes():
    assert checker.find_composition_fragments("3500/4500") == []


def test_false_negative_fraction_with_adjacent_class_name_still_fires():
    """The exact positive control the narrowing must not break: a
    fraction that IS describing a class-bucket split."""
    assert checker.find_composition_fragments("9/40 surface-form") != []
    assert checker.find_composition_fragments("semantic 3/40 this round") != []
    assert checker.find_composition_fragments("discourse-register split: 5/40") != []
    assert checker.find_composition_fragments("indeterminate 2/40") != []
    assert checker.find_composition_fragments("relational-positional 4/40") != []


def test_false_negative_fraction_adjacency_is_per_line_not_whole_message():
    """Adjacency is real, not global: a class name elsewhere in a
    multi-line message must not gate-open a fraction on an unrelated line."""
    message = "surface-form notes below\n\nunrelated: closed features 3500/4500 today"
    assert checker.find_composition_fragments(message) == []


def test_strip_comment_lines_removes_hash_prefixed_lines_only():
    raw = "real message\n# On branch main\n# Changes to be committed:\nmore real text"
    cleaned = checker.strip_comment_lines(raw)
    assert "# On branch main" not in cleaned
    assert "real message" in cleaned
    assert "more real text" in cleaned


# ---------------------------------------------------------------------------
# check_message: reserved-index reuse + composition-fragment together
# ---------------------------------------------------------------------------


def test_check_message_flags_reserved_index():
    index_hits, fragment_hits = checker.check_message("mentions feature 12403 directly", RESERVED)
    assert index_hits == [(1, 12403)]
    assert fragment_hits == []


def test_check_message_flags_composition_fragment_with_no_reserved_index():
    index_hits, fragment_hits = checker.check_message(
        "3 surface-form, 3 semantic, 4 denominator", RESERVED
    )
    assert index_hits == []
    assert len(fragment_hits) == 3


def test_check_message_passes_clean_message():
    index_hits, fragment_hits = checker.check_message("wire up the steer/ablate tool", RESERVED)
    assert index_hits == []
    assert fragment_hits == []


def test_check_message_index_matching_reuses_the_same_boundary_rules():
    """Regression guard: this must be the SAME function as
    check_reserved_indices.find_reserved_index_hits, not a re-implementation
    that could silently drift (e.g. re-introduce the \\b-on-floats bug)."""
    from check_reserved_indices import find_reserved_index_hits as canonical

    assert checker.find_reserved_index_hits is canonical


# ---------------------------------------------------------------------------
# main(): full CLI, given a real commit-msg-style temp file
# ---------------------------------------------------------------------------


def _init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    return path


def _write_pool(repo: Path, reserved_indices: list[int]) -> None:
    reports = repo / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload = {
        "reserved_features": [
            {"slot": i + 1, "index": idx, "fetched": False} for i, idx in enumerate(reserved_indices)
        ]
    }
    (reports / "calibration_pool_reserved.json").write_text(json.dumps(payload), encoding="utf-8")


def _run_checker(repo: Path, message: str) -> subprocess.CompletedProcess:
    msg_path = repo / "COMMIT_EDITMSG"
    msg_path.write_text(message, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(msg_path)], cwd=repo, capture_output=True, text=True
    )


def test_main_blocks_a_message_with_a_reserved_index(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    result = _run_checker(repo, "Fix hook for feature 12403")
    assert result.returncode == 1
    assert "12403" in result.stderr
    assert "COMMIT BLOCKED" in result.stderr


def test_main_blocks_a_message_with_a_tally(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    result = _run_checker(repo, "Calibration round: 3 surface-form, 3 semantic, 4 denominator")
    assert result.returncode == 1
    assert "COMMIT BLOCKED" in result.stderr


def test_main_allows_a_message_naming_rows_and_classes(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    result = _run_checker(repo, "Retrofit row 9105 to class 12, per SS12.3 replacement")
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_a_clean_message(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    result = _run_checker(repo, "Wire up the steer/ablate tool and its tests")
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_strips_git_comment_lines_before_checking(tmp_path):
    """A verbose commit template's diff-summary comment lines must not
    themselves trigger the checks (they can legitimately contain a diff
    line with a stray number)."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    message = "clean commit message\n# Please enter the commit message...\n# modified: file 12403.json\n"
    result = _run_checker(repo, message)
    assert result.returncode == 0


def test_main_warns_but_allows_when_pool_file_absent(tmp_path):
    repo = _init_repo(tmp_path)
    result = _run_checker(repo, "mentions 12403 with no pool file present")
    assert result.returncode == 0
    assert "not found" in result.stderr


def test_installed_hook_matches_tracked_canonical_copy():
    tracked = REPO_ROOT / "scripts" / "legacy" / "githooks" / "commit-msg"
    installed = REPO_ROOT / ".git" / "hooks" / "commit-msg"
    assert tracked.exists(), "tracked canonical commit-msg hook copy is missing"
    if installed.exists():
        assert tracked.read_text(encoding="utf-8") == installed.read_text(encoding="utf-8")
