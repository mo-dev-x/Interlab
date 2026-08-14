"""Tests for scripts/final_pairing/discovery_preflight.py itself.

The script is deliberately pytest-free at RUNTIME (it must run inside the
minimal scheduled Tamia environment -- see its own module docstring), but
nothing stops a pytest wrapper from importing and calling its pure
`run_all_cases`/`resolve_source_commit`/sentinel functions directly, the
same way `final_concept_discovery_dual_gpu_job.default_preflight_runner`
exercises it as a real subprocess in production. This file is what caught
(and locks in the fix for) two real bugs found only by actually running
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

Both are fixed in the script itself; the case below (`overall_passed`)
would go red again if either regressed.
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


def test_run_all_cases_reports_the_la_b_schema_and_a_clean_pass():
    """A REAL end-to-end run (fake backends, real file I/O, real
    subprocess-free call graph) -- not a mock of `run_all_cases` itself.
    Slow (tens of seconds: 14x2x3x3x2 real activation-ranking forward
    passes through the fake CPU backends, among other things) but this is
    exactly the cost the real scheduled preflight pays too."""
    with tempfile.TemporaryDirectory(prefix="discovery-preflight-test-") as tmp:
        report = preflight.run_all_cases(tmp_root=Path(tmp))

    assert report["schema_version"] == preflight.SCHEMA_VERSION
    assert isinstance(report["source_commit"], str) and len(report["source_commit"]) >= 7
    assert report["expected_cases"] == preflight.EXPECTED_CASE_COUNT
    assert report["executed_cases"] == preflight.EXPECTED_CASE_COUNT
    assert report["failed_cases"] == []
    assert report["overall_passed"] is True

    required_proofs = {
        "grid_creation", "causal_order_generation", "manifests", "controls",
        "prompt_ids", "explicit_kwargs", "staggered_load", "readiness", "sibling_tree_isolation",
    }
    assert required_proofs <= set(report["proofs"])
    assert all(report["proofs"][key] is True for key in required_proofs), report["proofs"]


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
    assert preflight.resolve_source_commit(REPO_ROOT) == preflight._git_head()


def test_cli_parses_sentinel_dir_flag():
    args = preflight.parse_args(["--sentinel-dir", "/some/path"])
    assert args.sentinel_dir == "/some/path"


def test_cli_sentinel_dir_is_required():
    """P0 STOP-LINE correction: --sentinel-dir is REQUIRED, not optional."""
    with pytest.raises(SystemExit):
        preflight.parse_args([])


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
    manifest = {"schema_version": discovery.SCHEMA_VERSION, "source_commit": "abc123fakearchivedcommit", "files": {}}
    (tmp_path / discovery.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    assert preflight.resolve_source_commit(tmp_path) == "abc123fakearchivedcommit"


def test_resolve_source_commit_raises_when_neither_transfer_manifest_nor_git_is_present(tmp_path):
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / discovery.TRANSFER_MANIFEST_FILENAME).exists()
    with pytest.raises(preflight.SetupFailure):
        preflight.resolve_source_commit(tmp_path)
