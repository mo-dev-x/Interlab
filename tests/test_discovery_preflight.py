"""Tests for scripts/final_pairing/discovery_preflight.py itself.

The script is deliberately pytest-free at RUNTIME (it must run inside the
minimal scheduled Tamia environment -- see its own module docstring), but
nothing stops a pytest wrapper from importing and calling its pure
`run_all_cases`/`resolve_source_commit`/sentinel functions directly, the
same way `final_concept_discovery_dual_gpu_job.default_preflight_runner`
exercises it as a real subprocess in production. This file is what caught
(and locks in the fix for) three real bugs found only by actually running
the script end to end rather than only importing pieces of it:

1. `case_both_or_neither_backup` called `run_matched_configuration_job`
   without stubbing `run_preflight`/`validate_prompt_artifact` -- the real
   defaults spawn `python discovery_preflight.py` as a SUBPROCESS, which
   (since this case runs INSIDE that very script's own `run_all_cases`)
   recursed without bound.
2. That same case's fake process launcher never wrote a READY record for
   the staggered cold-load handshake's lead lane, so once
   `run_matched_configuration_job` started routing through the real
   staggered launch (rather than `launch_all`), the fake lead process
   looked like it had already exited before ever becoming ready.
3. P0 FINAL DELTA (LA-B contract rewrite): calling `import final_pairing_
   concept_discovery as d` (for `resolve_and_validate_repo_root`) BEFORE
   `run_all_cases`'s own `import final_concept_discovery_dual_gpu_job`/
   `import final_concept_discovery_matched_configuration_job` transitively
   imports `final_pairing_harness` (scripts/legacy/, which does its OWN
   `sys.path.insert(0, str(Path(__file__).resolve().parent))` for its own
   sibling-module needs) -- since `final_pairing_harness.py` LIVES in
   scripts/legacy/, that push lands scripts/legacy ahead of scripts/
   final_pairing globally, so the FIRST (cache-populating) import of the
   two orchestration modules resolves to scripts/legacy's own thin
   `runpy`-forwarding stubs of the SAME name instead of the real modules.
   Fixed by re-asserting `SCRIPT_DIR` at `sys.path[0]` immediately before
   `run_all_cases`'s own import block -- `test_run_all_cases_reports_the_
   la_b_schema_and_a_clean_pass` below would go red again (with an
   AttributeError on `compute_trigger_from_grid_outputs`/`load_lane_spec`)
   if this regressed.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import discovery_preflight as preflight  # noqa: E402
import final_pairing_concept_discovery as discovery  # noqa: E402

_REAL_ARGS = {
    "prompt_sets": REPO_ROOT / discovery.FROZEN_PROMPT_SET_DIR / "prompt_sets.jsonl",
    "prompt_metadata": REPO_ROOT / discovery.FROZEN_PROMPT_SET_DIR / "metadata.json",
    "backup_trigger": REPO_ROOT / discovery.BACKUP_TRIGGER_PROTOCOL_PATH,
    "pairing_config": REPO_ROOT / discovery.IDENTITY_PROTOCOL_PATH,
}


def test_run_all_cases_reports_the_la_b_schema_and_a_clean_pass(tmp_path):
    """A REAL end-to-end run (fake backends, real file I/O, real
    subprocess-free call graph) -- not a mock of `run_all_cases` itself.
    Slow (tens of seconds: 14x2x3x3x2 real activation-ranking forward
    passes through the fake CPU backends, a real end-to-end `run_
    generation_mode` call, among other things) but this is exactly the
    cost the real scheduled preflight pays too."""
    with tempfile.TemporaryDirectory(prefix="discovery-preflight-test-") as tmp:
        report = preflight.run_all_cases(
            tmp_root=Path(tmp), repo_root=REPO_ROOT,
            gemma_output_root=tmp_path / "gemma_output", qwen_output_root=tmp_path / "qwen_output",
        )

    # Exactly the LA-B contract's eight top-level fields -- no "cases" array,
    # no generic proof-key vocabulary.
    assert set(report) == {
        "schema_version", "source_commit", "expected_case_count", "executed_case_count",
        "passed_case_count", "failed_cases", "overall_passed", "proofs",
    }
    assert report["schema_version"] == preflight.SCHEMA_VERSION
    assert isinstance(report["schema_version"], str)
    assert isinstance(report["source_commit"], str) and len(report["source_commit"]) == 40
    assert report["expected_case_count"] == preflight.EXPECTED_CASE_COUNT
    assert report["executed_case_count"] == preflight.EXPECTED_CASE_COUNT
    assert report["passed_case_count"] == preflight.EXPECTED_CASE_COUNT
    assert report["failed_cases"] == []
    assert report["overall_passed"] is True

    assert set(report["proofs"]) == set(preflight.PROOF_KEYS)
    assert all(value is True for value in report["proofs"].values()), report["proofs"]


def test_sentinel_dir_is_created_and_verified_untouched(tmp_path):
    sentinel_dir = tmp_path / "sentinel"
    preflight.ensure_sentinel(sentinel_dir)
    assert (sentinel_dir / preflight.SENTINEL_FILENAME).is_file()
    before = preflight._sentinel_snapshot(sentinel_dir)
    preflight.verify_sentinel_untouched(sentinel_dir, before)  # must not raise


def test_sentinel_dir_verification_raises_if_the_sentinel_file_changes(tmp_path):
    sentinel_dir = tmp_path / "sentinel"
    preflight.ensure_sentinel(sentinel_dir)
    before = preflight._sentinel_snapshot(sentinel_dir)
    (sentinel_dir / preflight.SENTINEL_FILENAME).write_text("tampered", encoding="utf-8")
    try:
        preflight.verify_sentinel_untouched(sentinel_dir, before)
    except preflight.SiblingTreeContaminated:
        pass
    else:
        raise AssertionError("expected SiblingTreeContaminated for a modified sentinel file")


def test_resolve_source_commit_matches_live_git_head_on_this_dev_checkout():
    assert preflight.resolve_source_commit(REPO_ROOT) == preflight._git_head(REPO_ROOT)


def test_resolve_source_commit_raises_on_a_short_or_non_hex_commit(tmp_path):
    """The LA-B contract requires a FULL 40-character hex commit -- a
    transfer manifest recording anything else (a short SHA, a placeholder
    string) is refused rather than passed through."""
    import json

    manifest = {"schema_version": discovery.SCHEMA_VERSION, "source_commit": "abc123fakearchivedcommit", "files": {}}
    (tmp_path / discovery.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(preflight.SetupFailure, match="40-character hex"):
        preflight.resolve_source_commit(tmp_path)


def test_cli_parses_all_eight_required_flags():
    args = preflight.parse_args([
        "--prompt-sets", str(_REAL_ARGS["prompt_sets"]),
        "--prompt-metadata", str(_REAL_ARGS["prompt_metadata"]),
        "--backup-trigger", str(_REAL_ARGS["backup_trigger"]),
        "--pairing-config", str(_REAL_ARGS["pairing_config"]),
        "--gemma-output-root", "/some/gemma/root",
        "--qwen-output-root", "/some/qwen/root",
        "--sentinel-dir", "/some/sentinel",
        "--report", "/some/report.json",
    ])
    assert args.gemma_output_root == "/some/gemma/root"
    assert args.qwen_output_root == "/some/qwen/root"
    assert args.sentinel_dir == "/some/sentinel"
    assert args.report == "/some/report.json"


@pytest.mark.parametrize(
    "missing_flag",
    [
        "--prompt-sets", "--prompt-metadata", "--backup-trigger", "--pairing-config",
        "--gemma-output-root", "--qwen-output-root", "--sentinel-dir", "--report",
    ],
)
def test_cli_every_one_of_the_eight_flags_is_required(missing_flag):
    """LA-B contract: all eight flags are required, no defaults. Built by
    starting from a COMPLETE, valid argv and removing exactly one
    `--flag value` pair, so this can never accidentally test the wrong
    flag's absence."""
    full_argv = [
        "--prompt-sets", str(_REAL_ARGS["prompt_sets"]),
        "--prompt-metadata", str(_REAL_ARGS["prompt_metadata"]),
        "--backup-trigger", str(_REAL_ARGS["backup_trigger"]),
        "--pairing-config", str(_REAL_ARGS["pairing_config"]),
        "--gemma-output-root", "/some/gemma/root",
        "--qwen-output-root", "/some/qwen/root",
        "--sentinel-dir", "/some/sentinel",
        "--report", "/some/report.json",
    ]
    flag_index = full_argv.index(missing_flag)
    argv = full_argv[:flag_index] + full_argv[flag_index + 2:]
    with pytest.raises(SystemExit):
        preflight.parse_args(argv)


def test_resolve_source_commit_uses_the_transfer_manifest_inside_a_no_git_archive_extraction(tmp_path):
    """The transfer manifest must work inside a no-.git archive
    extraction (P0 STOP-LINE correction) -- simulates the real Tamia
    shape: a `git archive` checkout with transfer_manifest.json present
    and NO .git directory at all. Writes the manifest DIRECTLY (never via
    `build_transfer_manifest`, which itself requires a real `.git` to
    compute `source_commit` from -- exactly the Windows/dev-side-only
    tool this no-.git directory must NOT need)."""
    import json

    assert not (tmp_path / ".git").exists()
    fake_commit = "abc123def456" * 3 + "abcd"  # 12*3 + 4 = 40 hex chars
    manifest = {"schema_version": discovery.SCHEMA_VERSION, "source_commit": fake_commit, "files": {}}
    (tmp_path / discovery.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    assert preflight.resolve_source_commit(tmp_path) == fake_commit


def test_resolve_source_commit_raises_when_neither_transfer_manifest_nor_git_is_present(tmp_path):
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / discovery.TRANSFER_MANIFEST_FILENAME).exists()
    with pytest.raises(preflight.SetupFailure):
        preflight.resolve_source_commit(tmp_path)


# ---------------------------------------------------------------------------
# resolve_and_validate_repo_root: the four explicit paths must all agree on
# ONE consistent repo_root, never trusted individually or derived from
# Path(__file__) alone.
# ---------------------------------------------------------------------------


def test_resolve_and_validate_repo_root_accepts_the_real_committed_paths():
    resolved = preflight.resolve_and_validate_repo_root(
        prompt_sets=_REAL_ARGS["prompt_sets"], prompt_metadata=_REAL_ARGS["prompt_metadata"],
        backup_trigger=_REAL_ARGS["backup_trigger"], pairing_config=_REAL_ARGS["pairing_config"],
    )
    assert resolved == REPO_ROOT


def test_resolve_and_validate_repo_root_rejects_a_mismatched_path(tmp_path):
    """One of the four explicit paths pointing OUTSIDE the root the other
    three agree on is refused -- never silently trusted on its own."""
    with pytest.raises(preflight.SetupFailure, match="do not resolve under one consistent repo root"):
        preflight.resolve_and_validate_repo_root(
            prompt_sets=_REAL_ARGS["prompt_sets"], prompt_metadata=_REAL_ARGS["prompt_metadata"],
            backup_trigger=_REAL_ARGS["backup_trigger"], pairing_config=tmp_path / "nonexistent_pairing_config.json",
        )


# ---------------------------------------------------------------------------
# main(): --report is written EVEN on a setup-level failure, with the
# SAME eight-field/seven-proof shape (all False) as a passing report.
# ---------------------------------------------------------------------------


def test_main_writes_report_even_on_a_setup_level_failure(tmp_path):
    import json

    report_path = tmp_path / "report.json"
    exit_code = preflight.main([
        "--prompt-sets", str(_REAL_ARGS["prompt_sets"]),
        "--prompt-metadata", str(_REAL_ARGS["prompt_metadata"]),
        "--backup-trigger", str(_REAL_ARGS["backup_trigger"]),
        "--pairing-config", str(tmp_path / "nonexistent_pairing_config.json"),
        "--gemma-output-root", str(tmp_path / "gemma_output"),
        "--qwen-output-root", str(tmp_path / "qwen_output"),
        "--sentinel-dir", str(tmp_path / "sentinel"),
        "--report", str(report_path),
    ])
    assert exit_code == 1
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(report) == {
        "schema_version", "source_commit", "expected_case_count", "executed_case_count",
        "passed_case_count", "failed_cases", "overall_passed", "proofs",
    }
    assert report["overall_passed"] is False
    assert report["executed_case_count"] == 0
    assert report["passed_case_count"] == 0
    assert len(report["failed_cases"]) == 1 and report["failed_cases"][0].startswith("setup:")
    assert set(report["proofs"]) == set(preflight.PROOF_KEYS)
    assert all(value is False for value in report["proofs"].values())
