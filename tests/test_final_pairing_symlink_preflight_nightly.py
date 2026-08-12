"""Real-filesystem Hugging Face cache symlink-containment tests --
orchestrator review, 2026-08-16 ("Correct and comprehensively audit Gemma
path-containment guards", live job 406957).

Orchestrator review, 2026-08-17 ("Make the Tamia symlink preflight
self-contained and pytest-free"): this file is NO LONGER what
scripts/legacy/final_pairing_gpu_job.py invokes as its scheduled Tamia
preflight gate -- ~/sprint-venv (Tamia's real, shared scientific
environment) has no pytest/pluggy/iniconfig, and installing them there is
forbidden. The wrapper now runs scripts/legacy/final_pairing_symlink_
preflight.py (standalone, standard-library-only) instead. This file
REMAINS, unchanged in purpose, as independent developer regression
coverage: the tests below exercise the production validators directly;
the one at the bottom (test_standalone_preflight_script_passes_when_run_
for_real) exercises the standalone SCRIPT itself, end-to-end, as a real
subprocess -- proving the actual artifact Tamia runs, not just the
validators it calls.

Marked @pytest.mark.nightly so the default per-commit gate
(pyproject.toml's `addopts = ... -m "not nightly"`) excludes it; run
explicitly via `pytest ... -m nightly` (verified this overrides addopts'
default filter).

Deliberately does NOT follow this project's usual ED-23 nightly discipline
of skip-with-an-explicit-reason for an optional cluster resource (see
test_interventions_identity_nightly.py): a real symlink is not an optional
resource for this specific file's purpose, it is the entire thing being
proven. If symlink creation fails here, that is treated as a genuine test
FAILURE, not a skip -- an all-skipped run would exit 0, and a preflight
gate that can silently "pass" by skipping every real check defeats the
reason it runs inside the allocation instead of on the login node. Local
iteration on a machine without symlink privileges (e.g. this project's own
Windows dev machine) should use test_final_pairing_targets.py's own
dev-machine-tolerant (skip-on-OSError) real-symlink tests instead -- those
are unchanged and still the right choice for that purpose.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_targets as targets  # noqa: E402

pytestmark = pytest.mark.nightly


def _real_symlink(link_path: Path, target_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(target_path)


def _build_realistic_hf_cache(tmp_path: Path):
    """A realistic huggingface_hub cache skeleton:
        models--google--gemma-scope-2-12b-it/
          blobs/<blob-id>
          snapshots/<revision>/
    Returns (repo_root, snapshot_dir, blob_path)."""
    repo_root = tmp_path / "models--google--gemma-scope-2-12b-it"
    blob_path = repo_root / "blobs" / "deadbeefcafe0123"
    blob_path.parent.mkdir(parents=True)
    blob_path.write_bytes(b"fake sae weights")
    snapshot_dir = repo_root / "snapshots" / "abc123"
    snapshot_dir.mkdir(parents=True)
    return repo_root, snapshot_dir, blob_path


def test_intended_resid_post_symlink_passes_the_snapshot_guard(tmp_path):
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    targets.validate_sae_files_match_snapshot(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


def test_intended_resid_post_symlink_passes_the_exact_subdirectory_guard(tmp_path):
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    provenance = targets.validate_sae_files_match_expected_subdirectory(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True


def test_dereferenced_blob_passes_the_physical_repository_cache_guard(tmp_path):
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


def test_entry_outside_the_validated_snapshot_revision_fails_the_snapshot_guard(tmp_path):
    """A logical entry resolved from a DIFFERENT, sibling revision
    directory under the same repository cache -- i.e. genuinely outside
    snapshots/<validated-revision> -- must fail."""
    repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    other_revision_dir = repo_root / "snapshots" / "deadbeef-a-different-revision"
    link_path = other_revision_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_files_match_snapshot([str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET)


def test_sibling_prefix_revision_directory_fails_the_snapshot_guard(tmp_path):
    """snapshots/<revision>-evil must fail -- a naive str.startswith()
    containment comparison would have incorrectly ACCEPTED this, since the
    string "<revision>-evil" starts with the string "<revision>"."""
    repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    evil_revision_dir = repo_root / "snapshots" / (snapshot_dir.name + "-evil")
    link_path = evil_revision_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_files_match_snapshot([str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET)


@pytest.mark.parametrize("sibling_family", ["attn_out", "mlp_out", "transcoder"])
def test_sibling_sae_family_passes_the_snapshot_guard_but_fails_the_family_guard(tmp_path, sibling_family):
    """A sibling family lives genuinely INSIDE the correct snapshot (so the
    broader snapshot guard alone cannot catch it) -- only the exact-
    subdirectory guard may reject it."""
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / sibling_family / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, blob_path)

    targets.validate_sae_files_match_snapshot(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise -- it IS inside the correct snapshot
    with pytest.raises(targets.TargetIdentityMismatch, match=sibling_family):
        targets.validate_sae_files_match_expected_subdirectory(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )


def test_symlink_escaping_the_repository_cache_fails_the_physical_guard(tmp_path):
    _repo_root, snapshot_dir, _blob_path = _build_realistic_hf_cache(tmp_path)
    outside_target = tmp_path / "some_other_repo" / "blobs" / "deadbeefcafe0123"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_bytes(b"fake weights from a different repository")
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(link_path, outside_target)

    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_symlink_targets_stay_in_repository_cache(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )


def test_non_symlink_regular_file_inside_the_snapshot_passes_all_guards(tmp_path):
    """A real, non-symlinked file (e.g. under HF_HUB_DISABLE_SYMLINKS_
    DOWNLOAD) must pass every guard -- symlink containment must never be a
    REQUIREMENT, only a check applied when a symlink is actually present."""
    _repo_root, snapshot_dir, _blob_path = _build_realistic_hf_cache(tmp_path)
    regular_file = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    regular_file.parent.mkdir(parents=True)
    regular_file.write_bytes(b"a real, non-symlinked file")

    targets.validate_sae_files_match_snapshot([str(regular_file)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET)
    provenance = targets.validate_sae_files_match_expected_subdirectory(
        [str(regular_file)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True
    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        [str(regular_file)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # no-op: not a symlink, nothing to dereference


def test_duplicate_captured_paths_remain_valid_and_each_occurrence_is_checked(tmp_path):
    """params.safetensors appearing twice in resolved_files (e.g. captured
    once for the shape lookup, once for the weights fetch) must remain
    valid when correct, and a BAD path appearing twice must still be
    reported both times -- proving neither validator accidentally
    deduplicates resolved_files before checking it."""
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    good_link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "params.safetensors"
    _real_symlink(good_link, blob_path)
    good_resolved = [str(good_link), str(good_link)]

    targets.validate_sae_files_match_snapshot(good_resolved, snapshot_dir, targets.GEMMA_3_12B_IT_TARGET)
    provenance = targets.validate_sae_files_match_expected_subdirectory(
        good_resolved, snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True

    bad_link = snapshot_dir / "attn_out" / "layer_31_width_16k_l0_medium" / "config.json"
    _real_symlink(bad_link, blob_path)
    bad_resolved = [str(bad_link), str(bad_link)]
    with pytest.raises(targets.TargetIdentityMismatch, match="attn_out") as exc_info:
        targets.validate_sae_files_match_expected_subdirectory(
            bad_resolved, snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )
    # both occurrences reported, not deduplicated -- the message embeds
    # repr(path) inside a list repr, which escapes backslashes on Windows.
    assert str(exc_info.value).count(repr(str(bad_link))) == 2


# ---------------------------------------------------------------------------
# The standalone script itself, end-to-end, as a REAL subprocess --
# orchestrator review, 2026-08-17. Proves the actual artifact
# final_pairing_gpu_job.py invokes on Tamia, not just the validators the
# tests above already exercise directly.
# ---------------------------------------------------------------------------


def test_standalone_preflight_script_passes_when_run_for_real(tmp_path):
    script_path = REPO_ROOT / "scripts" / "legacy" / "final_pairing_symlink_preflight.py"
    out_path = tmp_path / "symlink_preflight_result.json"
    completed = subprocess.run(
        [sys.executable, str(script_path), "--work-dir", str(tmp_path), "--out", str(out_path), "--source-commit", "test"],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    result = json.loads(out_path.read_text())
    assert result["executed_count"] == 11
    assert result["passed_count"] == 11
    assert result["overall_passed"] is True
    assert result["setup_failure"] is None
    assert result["source_commit"] == "test"
    assert all(case["passed"] for case in result["cases"])
    # the scratch tree is cleaned up; only the JSON artifact remains under --work-dir.
    assert not (tmp_path / "final_pairing_symlink_preflight_scratch").exists()
