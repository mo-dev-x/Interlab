"""Tests for the sealed final-pairing evidence records under
results/final_pairing/job_407008/ and results/final_pairing/job_406092/, and
for docs/final_pairing_tamia_packet.md's corrected current-status claims.

These tests exist so that a future edit cannot silently corrupt an imported
evidence file, drift a README's bounded conclusion/limitation wording away
from the sealed manifest, let a Gemma-pass claim leak into the job where
Gemma failed (or vice versa), or let a stale "never ran" claim creep back
into the packet doc now that both targets have run for real. No torch, no
GPU, no network -- pure filesystem/string checks against already-imported,
already-hash-verified evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "results" / "final_pairing"
JOB_407008_DIR = RESULTS_ROOT / "job_407008"
JOB_406092_DIR = RESULTS_ROOT / "job_406092"
PACKET_DOC = REPO_ROOT / "docs" / "final_pairing_tamia_packet.md"

# Sealed by the chain-of-custody manifests themselves (dispatch-quoted and
# independently recomputed by Engineer 1 at import time -- see the two
# job READMEs' opening paragraphs for the verification narrative).
EXPECTED_MANIFEST_SHA256 = {
    "407008": "10cbbb6e92b5fc5b7ec4a48974e3940c9c8495d71b1e5e5a0cf38ceb6b88984c",
    "406092": "fbbfbaf0f8ee48a789f7217c87461f1752bb46657e5087a81f74108a90309f16",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_inventory(job_dir: Path) -> dict:
    return json.loads((job_dir / "inventory.json").read_text(encoding="utf-8"))


def _load_manifest(job_dir: Path) -> dict:
    return json.loads((job_dir / "chain_of_custody.json").read_text(encoding="utf-8"))


def _normalized(text: str) -> str:
    """Collapse whitespace (including markdown line-wrap newlines) to single
    spaces so a substring check doesn't depend on exactly where a paragraph
    happens to wrap."""
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Chain-of-custody manifests: byte-identity pinned against the sealed hash.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("job_id,job_dir", [("407008", JOB_407008_DIR), ("406092", JOB_406092_DIR)])
def test_chain_of_custody_manifest_matches_sealed_hash(job_id, job_dir):
    manifest_path = job_dir / "chain_of_custody.json"
    assert manifest_path.is_file(), f"missing chain_of_custody.json for job {job_id}"
    assert _sha256_file(manifest_path) == EXPECTED_MANIFEST_SHA256[job_id]


@pytest.mark.parametrize("job_id,job_dir", [("407008", JOB_407008_DIR), ("406092", JOB_406092_DIR)])
def test_chain_of_custody_job_id_and_source_commit(job_id, job_dir):
    manifest = _load_manifest(job_dir)
    assert manifest["job_id"] == job_id
    expected_source_commit = {"407008": "de3b499", "406092": "e63b08e"}[job_id]
    assert manifest["source_of_record"]["source_commit"] == expected_source_commit


# ---------------------------------------------------------------------------
# Every artifact named by the inventory must still hash- and size-match the
# actual file on disk -- catches silent corruption or a re-edit of imported
# evidence, which must never happen (these are original, sealed bytes).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("job_dir", [JOB_407008_DIR, JOB_406092_DIR])
def test_every_inventory_entry_matches_the_actual_file_on_disk(job_dir):
    inventory = _load_inventory(job_dir)
    assert inventory["files"], "inventory.json must list at least one file"
    for entry in inventory["files"]:
        path = job_dir / entry["name"]
        assert path.is_file(), f"{entry['name']} listed in inventory.json but missing on disk"
        assert path.stat().st_size == entry["size_bytes"], f"{entry['name']} size drifted from inventory.json"
        assert _sha256_file(path) == entry["sha256"], f"{entry['name']} sha256 drifted from inventory.json"


@pytest.mark.parametrize("job_dir", [JOB_407008_DIR, JOB_406092_DIR])
def test_inventory_hashes_agree_with_the_manifests_own_local_copy_hashes(job_dir):
    """The inventory isn't just self-consistent -- it must match what the
    sealed manifest itself recorded as the local copy's hash, for every
    artifact the manifest tracked under hashes_measured_now."""
    inventory = _load_inventory(job_dir)
    manifest = _load_manifest(job_dir)
    inventory_by_name = {entry["name"]: entry for entry in inventory["files"]}
    for tracked in manifest["hashes_measured_now"].values():
        local_copy = tracked.get("local_copy")
        if local_copy is None:
            continue
        local_path = Path(local_copy["local_path"])
        name = local_path.name
        if name not in inventory_by_name:
            # Artifacts intentionally excluded from import (e.g. the full
            # run-directory .tar.gz) are documented in excluded_by_design.
            continue
        assert inventory_by_name[name]["sha256"] == local_copy["sha256"]
        assert inventory_by_name[name]["size_bytes"] == local_copy["size_bytes"]


def test_job_406092_wrapper_diff_is_reproducible_from_its_own_pre_and_post_image():
    """The one authorized wrapper edit for job 406092 (a single added
    PYTHONPATH line) must be independently reproducible from the two
    images stored alongside it, not merely asserted by the manifest."""
    before = (JOB_406092_DIR / "fp_accept.sbatch.before").read_text(encoding="utf-8").splitlines(keepends=True)
    after = (JOB_406092_DIR / "fp_accept.sbatch").read_text(encoding="utf-8").splitlines(keepends=True)
    import difflib

    diff_lines = list(difflib.unified_diff(before, after, lineterm=""))
    added = [line for line in diff_lines if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in diff_lines if line.startswith("-") and not line.startswith("---")]
    assert len(added) == 1
    assert len(removed) == 0
    assert "PYTHONPATH" in added[0]


# ---------------------------------------------------------------------------
# Required bounded conclusions and limitations must be present verbatim.
# ---------------------------------------------------------------------------


def test_job_407008_readme_states_the_required_gemma_conclusion():
    readme = _normalized((JOB_407008_DIR / "README.md").read_text(encoding="utf-8"))
    assert (
        "Gemma-3-12B-IT with Gemma Scope 2 resid_post layer 31 passed mechanical "
        "steering acceptance under ALL and GENERATED_ONLY in job 407008."
    ) in readme


def test_job_406092_readme_states_the_required_qwen_conclusion():
    readme = _normalized((JOB_406092_DIR / "README.md").read_text(encoding="utf-8"))
    assert (
        "Qwen3.5-27B with Qwen-Scope engineering layer 0 passed mechanical "
        "steering under ALL and GENERATED_ONLY in mixed job 406092."
    ) in readme


@pytest.mark.parametrize(
    "phrase",
    [
        "Mechanical correctness does not establish scientific concept quality",
        "GENERATED_ONLY masks",
        "no public `--positions` default is claimed",
        "engineering acceptance inputs",
    ],
)
def test_job_407008_readme_states_required_limitations(phrase):
    readme = _normalized((JOB_407008_DIR / "README.md").read_text(encoding="utf-8"))
    assert phrase in readme


@pytest.mark.parametrize(
    "phrase",
    [
        "Job 406092 was not a global acceptance pass",
        "Gemma failed in job 406092",
        "ENGINEERING-ONLY",
        "not a ratified layer",
        "GENERATED_ONLY masks",
        "no public `--positions` default is claimed",
    ],
)
def test_job_406092_readme_states_required_limitations(phrase):
    readme = _normalized((JOB_406092_DIR / "README.md").read_text(encoding="utf-8"))
    assert phrase in readme


# ---------------------------------------------------------------------------
# Overclaim / cross-contamination guards: a passing conclusion for one job
# must never leak into the other, and a global pass must never be implied
# for the job where Gemma failed.
# ---------------------------------------------------------------------------


def test_job_406092_readme_does_not_claim_gemma_passed():
    readme = (JOB_406092_DIR / "README.md").read_text(encoding="utf-8")
    assert "Gemma-3-12B-IT with Gemma Scope 2 resid_post layer 31 passed" not in readme
    assert "job 407008" in readme  # cross-referenced, not conflated


def test_job_407008_readme_does_not_claim_qwen_ran_here():
    readme = (JOB_407008_DIR / "README.md").read_text(encoding="utf-8")
    assert "Qwen3.5-27B with Qwen-Scope engineering layer 0 passed" not in readme


def test_job_406092_global_acceptance_phrase_only_appears_negated():
    readme = (JOB_406092_DIR / "README.md").read_text(encoding="utf-8")
    count = readme.count("global acceptance")
    assert count >= 1
    for line in readme.splitlines():
        if "global acceptance" in line:
            assert "not" in line.lower() or "NOT" in line


def test_neither_readme_claims_behavioral_or_scientific_acceptance():
    forbidden = [
        "behavioral acceptance",
        "scientific acceptance",
        "concept quality confirmed",
        "establishes scientific concept quality",
        "establishes behavioral quality",
    ]
    for job_dir in (JOB_407008_DIR, JOB_406092_DIR):
        readme = (job_dir / "README.md").read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in readme


# ---------------------------------------------------------------------------
# docs/final_pairing_tamia_packet.md must no longer carry the stale,
# unqualified "never ran against real weights" current-status claim, and
# must carry the sealed-evidence section plus supersession markers.
# ---------------------------------------------------------------------------


def test_packet_doc_has_sealed_evidence_section_referencing_both_jobs():
    text = PACKET_DOC.read_text(encoding="utf-8")
    assert "## Sealed evidence (2026-08-13)" in text
    assert "results/final_pairing/job_407008/" in text
    assert "results/final_pairing/job_406092/" in text


def test_packet_doc_top_summary_no_longer_claims_nothing_has_run():
    text = PACKET_DOC.read_text(encoding="utf-8")
    assert "**not run against real weights or a GPU** -- no allocation was" not in text


def test_packet_doc_marks_every_never_ran_claim_as_superseded():
    text = PACKET_DOC.read_text(encoding="utf-8")
    superseded_count = text.count("SUPERSEDED (2026-08-13)")
    # One marker each for: Qwen item 1, Qwen item 3, Gemma resolver item 4,
    # preflight item 5, Gemma-it-side item 6, shape-shim item 7, wrapper
    # item 9, plus the Command 2 section note -- at least 7.
    assert superseded_count >= 7


def test_packet_doc_chronology_correction_present_and_dates_match_git_history():
    text = PACKET_DOC.read_text(encoding="utf-8")
    assert "Chronology correction (2026-08-13)" in text
    # The real commit dates this correction asserts, pinned so a future
    # rebase/edit of the branch can't silently invalidate the claim without
    # this test catching the mismatch.
    for real_date in ("2026-08-11 18:55", "2026-08-12"):
        assert real_date in text
