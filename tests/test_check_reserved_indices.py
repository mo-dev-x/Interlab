"""Tests for scripts/legacy/check_reserved_indices.py.

Four incidents, four fixes, one test file per incident's fix plus the
regression cases the earlier fixes already covered:
  1. *.md/*.py content scoping (v1.9/v1.10) -- generated-data false
     positives (records.jsonl) pass regardless of content.
  2. magnitude floor (v1.10) -- covered in test_make_calibration_pool.py,
     not re-tested here.
  3. diff-scoping (v1.14 SS14.6) -- an ADDED line with a reserved index
     fails; an UNMODIFIED (pre-existing) line containing one passes; a
     first-time file addition containing one fails (every line of it is
     "added"); the real VERIFICATION_LOG.md with only an unrelated new
     entry appended passes.
  4. the trailing-period false negative, and the BINDING RULE it produced:
     every detector gets a deliberate false-negative suite, not only a
     false-positive one. The "DELIBERATE FALSE-NEGATIVE SUITE" section
     below enumerates the ways a reserved index can legitimately appear
     in prose and asserts the scanner catches every one -- symmetric to
     the false-positive tests above it, which assert what it must NOT
     flag. Testing what it must, not only what it mustn't.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "check_reserved_indices.py"
REAL_RECORDS_JSONL = REPO_ROOT / "results" / "gemma3_sweep" / "records.jsonl"
REAL_VERIFICATION_LOG = REPO_ROOT / "project_management" / "VERIFICATION_LOG.md"
REAL_POOL = REPO_ROOT / "reports" / "calibration_pool_reserved.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load("check_reserved_indices", SCRIPT)

RESERVED = [12403, 8950, 250]  # arbitrary stand-ins, disjoint from any real pool content
COMPOSITION_ONLY = [3039]  # NOT in RESERVED -- stands in for an already-spent composition index


def _assert_fixture_stand_ins_are_safe() -> None:
    """This file's own lesson, applied to its own foundational fixture:
    a hardcoded stand-in that happens to collide with a REAL reserved
    index would burn that slot the moment this file is committed and
    tracked (exactly what the incident-fixed test above caught for its
    own placeholders). Checked once, loudly, at collection time -- a
    count only, never which stand-in or what the real value is -- so a
    future pool regeneration that happens to draw one of these can't
    silently ship a leak inside the test suite meant to catch it."""
    if not REAL_POOL.exists():
        return
    real_reserved = set(checker.load_reserved_indices(REAL_POOL))
    colliding = [v for v in RESERVED if v in real_reserved]
    assert not colliding, (
        f"{len(colliding)} of this file's RESERVED stand-in(s) now collide with the real "
        "reserved pool -- replace them with different placeholder values before committing."
    )


_assert_fixture_stand_ins_are_safe()


# ---------------------------------------------------------------------------
# regex-level: find_reserved_index_hits / find_reserved_index_hits_in_lines
# ---------------------------------------------------------------------------


def test_standalone_reserved_index_is_flagged():
    hits = checker.find_reserved_index_hits("discussing feature 12403 today", RESERVED)
    assert hits == [(1, 12403)]


def test_reserved_index_embedded_in_a_longer_integer_passes():
    hits = checker.find_reserved_index_hits("the run took 112403 seconds", RESERVED)
    assert hits == []


def test_standalone_reserved_index_at_end_of_sentence_is_flagged():
    """Regression: an earlier version's lookahead excluded ANY trailing
    '.', including an ordinary sentence-ending period -- silently never
    detecting the single most common way a reserved index would actually
    appear in prose. A false negative, found by accident while debugging
    the diff-scoping fix, not something asked for."""
    hits = checker.find_reserved_index_hits("We discussed feature 12403.", RESERVED)
    assert hits == [(1, 12403)]


def test_reserved_index_inside_a_decimal_fraction_passes():
    """The matplotlib-colormap-float false positive this hook exists to
    avoid: a bare \\b12403\\b scan would still fire here, because regex
    \\b treats '.' as a non-word boundary."""
    hits = checker.find_reserved_index_hits("cmap threshold = 0.12403", RESERVED)
    assert hits == []


def test_reserved_index_inside_an_identifier_passes():
    hits = checker.find_reserved_index_hits("see feature_12403_notes.md", RESERVED)
    assert hits == []


def test_composition_only_index_is_never_flagged_because_its_not_reserved():
    hits = checker.find_reserved_index_hits(
        f"composition row {COMPOSITION_ONLY[0]} is already adjudicated", RESERVED
    )
    assert hits == []


def test_find_reserved_index_hits_in_lines_uses_given_line_numbers():
    """Diff-scoped matching: line numbers come from the hunk header, not
    from re-splitting a string at 1."""
    numbered_lines = [(572, "mentions 8950 here"), (831, "clean"), (832, "mentions 250 too")]
    hits = checker.find_reserved_index_hits_in_lines(numbered_lines, RESERVED)
    assert hits == [(572, 8950), (832, 250)]


# ---------------------------------------------------------------------------
# path-level matching: find_reserved_index_in_path
# ---------------------------------------------------------------------------


def test_path_with_reserved_index_as_filename_stem_is_flagged():
    assert checker.find_reserved_index_in_path(
        "scripts/legacy/gemma_neuronpedia_raw/12403.json", set(RESERVED)
    ) == 12403


def test_path_with_index_embedded_in_a_longer_number_passes():
    assert checker.find_reserved_index_in_path("run_112403_output.json", set(RESERVED)) is None


def test_path_with_composition_only_index_passes_because_its_not_reserved():
    assert checker.find_reserved_index_in_path(
        f"scripts/legacy/gemma_neuronpedia_raw/{COMPOSITION_ONLY[0]}.json", set(RESERVED)
    ) is None


# ---------------------------------------------------------------------------
# _parse_added_lines: the diff-parsing core of incident 3's fix
# ---------------------------------------------------------------------------


def test_parse_added_lines_only_returns_plus_lines_with_new_file_numbers():
    diff = (
        "diff --git a/f.md b/f.md\n"
        "index abc..def 100644\n"
        "--- a/f.md\n"
        "+++ b/f.md\n"
        "@@ -10,0 +11,2 @@\n"
        "+first added line\n"
        "+second added line\n"
    )
    assert checker._parse_added_lines(diff) == [
        (11, "first added line"),
        (12, "second added line"),
    ]


def test_parse_added_lines_skips_removed_lines_without_advancing_counter():
    diff = (
        "diff --git a/f.md b/f.md\n"
        "--- a/f.md\n"
        "+++ b/f.md\n"
        "@@ -5,1 +5,1 @@\n"
        "-old line\n"
        "+new line\n"
    )
    assert checker._parse_added_lines(diff) == [(5, "new line")]


def test_parse_added_lines_handles_multiple_hunks():
    diff = (
        "diff --git a/f.md b/f.md\n"
        "--- a/f.md\n"
        "+++ b/f.md\n"
        "@@ -1,0 +1,1 @@\n"
        "+top addition\n"
        "@@ -50,0 +52,1 @@\n"
        "+bottom addition\n"
    )
    assert checker._parse_added_lines(diff) == [(1, "top addition"), (52, "bottom addition")]


# ---------------------------------------------------------------------------
# full staged-git integration
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


def _write_and_commit(repo: Path, relative_path: str, content: str, message: str = "seed commit") -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", relative_path], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def _stage(repo: Path, relative_path: str, content: str) -> None:
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", relative_path], cwd=repo, check=True)


def _run_checker(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True)


def test_main_blocks_an_added_line_with_a_reserved_index(tmp_path):
    """Case 1: a first-time file addition containing a reserved index --
    every line of a new file is an added line."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "notes.md", "We discussed feature 12403 with the PM today.")

    result = _run_checker(repo)
    assert result.returncode == 1
    assert "notes.md" in result.stderr
    assert "12403" in result.stderr
    assert "COMMIT BLOCKED" in result.stderr


def test_main_allows_an_unmodified_line_with_a_reserved_index(tmp_path):
    """Case 2: the SAME reserved index, already committed (pre-existing,
    unmodified) content -- an unrelated later edit to the same file must
    not re-flag it. This is incident 3's exact shape."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _write_and_commit(repo, "ledger.md", "Line one mentions feature 12403 already.\nLine two.\n")

    _stage(repo, "ledger.md", "Line one mentions feature 12403 already.\nLine two.\nLine three is new and clean.\n")

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_blocks_a_genuinely_new_line_with_a_reserved_index_in_an_existing_file(tmp_path):
    """The positive control for the previous test: a NEW line in an
    already-tracked file, containing a reserved index, must still fail."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _write_and_commit(repo, "ledger.md", "Line one is clean.\n")

    _stage(repo, "ledger.md", "Line one is clean.\nLine two newly mentions feature 12403.\n")

    result = _run_checker(repo)
    assert result.returncode == 1
    assert "12403" in result.stderr


def test_main_allows_the_real_records_jsonl(tmp_path):
    """Out of content-scan scope regardless of diff-scoping (not *.md/*.py)."""
    if not REAL_RECORDS_JSONL.exists():
        pytest.skip("results/gemma3_sweep/records.jsonl not present in this checkout")
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "results/gemma3_sweep/records.jsonl", REAL_RECORDS_JSONL.read_text(encoding="utf-8"))

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_the_real_verification_log_with_only_an_unrelated_new_entry(tmp_path):
    """Case 4, against the real artifact: project_management/
    VERIFICATION_LOG.md, committed as pre-existing (whatever it actually
    contains), then a clean new entry appended and staged -- must pass
    using the REAL current reserved pool, entirely by diff-scoping (no
    floor tuning, no per-file exemption)."""
    if not REAL_VERIFICATION_LOG.exists() or not REAL_POOL.exists():
        pytest.skip("real VERIFICATION_LOG.md or calibration_pool_reserved.json not present")
    repo = _init_repo(tmp_path)
    (repo / "reports").mkdir(parents=True, exist_ok=True)
    (repo / "reports" / "calibration_pool_reserved.json").write_text(
        REAL_POOL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    original = REAL_VERIFICATION_LOG.read_text(encoding="utf-8")
    _write_and_commit(repo, "project_management/VERIFICATION_LOG.md", original)

    _stage(
        repo,
        "project_management/VERIFICATION_LOG.md",
        original + "\n## New entry: unrelated routine update, nothing sensitive.\n",
    )

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_a_synthetic_jsonl_with_ordinary_governance_prose_numbers(tmp_path):
    """The original incident's shape (ordinary numbers in generated prose
    colliding with a reserved-shaped pool) -- but the placeholder values
    must never be literals that could coincidentally BE a real reserved
    index once this test file is itself committed and tracked. An
    earlier version of this test hardcoded a 4-digit "year" placeholder
    that turned out to ALSO be a currently-real reserved index --
    committing this file would have permanently burned that slot, inside
    the test suite that exists to prevent exactly that. (Deliberately not
    naming the value here either: writing it into this docstring to
    explain the incident would repeat it.)

    FIX: assert the safety PROPERTY (every placeholder is below
    make_calibration_pool.RESERVED_FLOOR) rather than trusting a literal
    to happen to be safe. This needs no dependency on the real pool's
    actual contents -- floor-protected values can never collide with a
    real reserved index by construction, regardless of what the pool
    contains today or after any future regeneration."""
    placeholders = [18, 42, 7]  # an age, a platform number, a page number
    pool_mod = _load("make_calibration_pool", REPO_ROOT / "scripts" / "legacy" / "make_calibration_pool.py")
    assert all(v < pool_mod.RESERVED_FLOOR for v in placeholders), (
        "a placeholder here is >= RESERVED_FLOOR and could coincidentally collide with a real "
        "reserved index -- pick a value provably below the floor instead"
    )

    repo = _init_repo(tmp_path)
    _write_pool(repo, placeholders)
    content = '{"text": "the narrator turned 18, waited on platform 42, and read page 7."}\n'
    _stage(repo, "results/gemma3_sweep/records.jsonl", content)

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_a_md_doc_with_index_embedded_in_a_longer_number(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "notes.md", "Run 112403 finished at 0.12403 seconds per step.")

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_a_md_doc_with_a_composition_index_already_spent(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "ledger.md", f"Composition row {COMPOSITION_ONLY[0]} is adjudicated and closed.")

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_blocks_a_py_docstring_containing_a_reserved_index(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "scripts/notes.py", '"""discussing feature 12403 in this docstring"""\n')

    result = _run_checker(repo)
    assert result.returncode == 1
    assert "scripts/notes.py" in result.stderr
    assert "12403" in result.stderr


def test_main_allows_a_py_file_with_index_embedded_in_a_longer_number(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "scripts/notes.py", "TIMEOUT_MS = 112403  # unrelated constant\n")

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_blocks_a_newly_added_file_named_after_a_reserved_index(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "scripts/legacy/gemma_neuronpedia_raw/12403.json", '{"activations": []}')

    result = _run_checker(repo)
    assert result.returncode == 1
    assert "12403" in result.stderr
    assert "gemma_neuronpedia_raw/12403.json" in result.stderr


def test_main_allows_an_unrelated_edit_to_an_already_tracked_reserved_named_file(tmp_path):
    """Path-scan is also diff-scoped (diff-filter AC, not ACM): a file
    already tracked under a reserved-index name, edited again, must not
    re-flag its unchanged path."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _write_and_commit(repo, "scripts/legacy/gemma_neuronpedia_raw/12403.json", '{"activations": []}')

    _stage(repo, "scripts/legacy/gemma_neuronpedia_raw/12403.json", '{"activations": [], "note": "clean edit"}')

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_allows_a_non_md_file_named_after_a_composition_index(tmp_path):
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(
        repo,
        f"scripts/legacy/gemma_neuronpedia_raw/{COMPOSITION_ONLY[0]}.json",
        '{"activations": []}',
    )

    result = _run_checker(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_main_scans_only_staged_content_not_working_tree(tmp_path):
    """A file staged clean, then dirtied in the working tree without
    re-staging, must be checked against the STAGED version."""
    repo = _init_repo(tmp_path)
    _write_pool(repo, RESERVED)
    _stage(repo, "notes.md", "nothing sensitive here")
    (repo / "notes.md").write_text("now mentions 12403 unstaged", encoding="utf-8")

    result = _run_checker(repo)
    assert result.returncode == 0


def test_main_warns_but_allows_commit_when_pool_file_absent(tmp_path):
    repo = _init_repo(tmp_path)
    _stage(repo, "notes.md", "mentions 12403 with no pool file present")

    result = _run_checker(repo)
    assert result.returncode == 0
    assert "not found" in result.stderr
    assert "Commit allowed" in result.stderr


def test_installed_hook_matches_tracked_canonical_copy():
    tracked = REPO_ROOT / "scripts" / "legacy" / "githooks" / "pre-commit"
    installed = REPO_ROOT / ".git" / "hooks" / "pre-commit"
    assert tracked.exists(), "tracked canonical hook copy is missing"
    if installed.exists():
        assert tracked.read_text(encoding="utf-8") == installed.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# DELIBERATE FALSE-NEGATIVE SUITE (binding rule, incident 4): every
# detector gets a suite asserting what it MUST flag, not only what it
# must NOT. One test per legitimate way a reserved index can appear in
# real prose -- each of these was a plausible blind spot; none should be.
# ---------------------------------------------------------------------------


def test_false_negative_sentence_final():
    assert checker.find_reserved_index_hits("We discussed feature 12403.", RESERVED) == [(1, 12403)]


def test_false_negative_parenthesised():
    assert checker.find_reserved_index_hits("the outlier (12403) was excluded", RESERVED) == [(1, 12403)]


def test_false_negative_comma_listed():
    hits = checker.find_reserved_index_hits("Features 12403, 8950, 250 were reviewed.", RESERVED)
    assert {index for _lineno, index in hits} == {12403, 8950, 250}


def test_false_negative_hyphen_adjacent():
    assert checker.find_reserved_index_hits("the pre-12403 baseline", RESERVED) == [(1, 12403)]
    assert checker.find_reserved_index_hits("feature 12403-tagged rows", RESERVED) == [(1, 12403)]


def test_false_negative_line_initial():
    assert checker.find_reserved_index_hits("12403 is the value in question", RESERVED) == [(1, 12403)]


def test_false_negative_line_final_no_trailing_punctuation():
    assert checker.find_reserved_index_hits("the value in question is 12403", RESERVED) == [(1, 12403)]


def test_false_negative_markdown_table_cell():
    assert checker.find_reserved_index_hits("| 12403 | some label | 0.42 |", RESERVED) == [(1, 12403)]


def test_false_negative_quoted():
    assert checker.find_reserved_index_hits('the id is "12403" per the log', RESERVED) == [(1, 12403)]
    assert checker.find_reserved_index_hits("the id is '12403' per the log", RESERVED) == [(1, 12403)]


def test_false_negative_footnote_marked():
    assert checker.find_reserved_index_hits("a claim needing support[^12403]", RESERVED) == [(1, 12403)]
    assert checker.find_reserved_index_hits("a claim needing support[12403]", RESERVED) == [(1, 12403)]


def test_false_negative_colon_prefixed_field():
    assert checker.find_reserved_index_hits("index: 12403", RESERVED) == [(1, 12403)]


def test_false_negative_semicolon_separated_list():
    hits = checker.find_reserved_index_hits("rows 12403; 8950; 250 all moved.", RESERVED)
    assert {index for _lineno, index in hits} == {12403, 8950, 250}


# ---------------------------------------------------------------------------
# whole-tree / whole-history audit (incident 4 remediation)
# ---------------------------------------------------------------------------


def test_scan_tracked_tree_content_finds_a_committed_leak(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(repo, "ledger.md", "We discussed feature 12403 already.\n")

    leaked = checker.scan_tracked_tree_content(repo, RESERVED)
    assert leaked == {12403}


def test_scan_tracked_tree_content_ignores_non_md_py_files(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(repo, "results/records.jsonl", '{"text": "mentions 12403 here"}\n')

    leaked = checker.scan_tracked_tree_content(repo, RESERVED)
    assert leaked == set()


def test_scan_tracked_tree_content_ignores_embedded_and_composition_numbers(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(
        repo,
        "ledger.md",
        f"the run took 112403 seconds; composition row {COMPOSITION_ONLY[0]} is closed.\n",
    )

    leaked = checker.scan_tracked_tree_content(repo, RESERVED)
    assert leaked == set()


def test_scan_commit_message_history_finds_a_leaked_message(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(repo, "notes.md", "clean file", message="mentions feature 12403 in the message")

    leaked = checker.scan_commit_message_history(repo, RESERVED)
    assert leaked == {12403}


def test_scan_commit_message_history_ignores_clean_messages(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(repo, "notes.md", "clean file", message="wire up the steer/ablate tool")

    leaked = checker.scan_commit_message_history(repo, RESERVED)
    assert leaked == set()


def test_scan_commit_message_history_covers_all_commits_not_just_head(tmp_path):
    repo = _init_repo(tmp_path)
    _write_and_commit(repo, "a.md", "a", message="clean first commit")
    _write_and_commit(repo, "b.md", "b", message="mentions 8950 in a middle commit")
    _write_and_commit(repo, "c.md", "c", message="clean last commit")

    leaked = checker.scan_commit_message_history(repo, RESERVED)
    assert leaked == {8950}
