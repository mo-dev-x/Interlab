"""The Tamia archive must carry its verifier inside the tarball."""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import build_transfer_archive as archive_builder  # noqa: E402


def test_archive_contains_exact_root_runtime_manifest_and_no_git(tmp_path: Path):
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=REPO_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    output = tmp_path / "final-pairing.tar.gz"

    report = archive_builder.build_archive(REPO_ROOT, commit, output)

    assert report["source_commit"] == commit
    with tarfile.open(output, "r:gz") as archive:
        names = set(archive.getnames())
        assert archive_builder.TRANSFER_MANIFEST_NAME in names
        assert archive_builder.SOURCE_COMMIT_NAME in names
        assert not any(name == ".git" or name.startswith(".git/") for name in names)
        manifest = json.load(archive.extractfile(archive_builder.TRANSFER_MANIFEST_NAME))
        marker = archive.extractfile(archive_builder.SOURCE_COMMIT_NAME).read().decode("ascii")

    assert manifest == report["runtime_manifest"]
    assert manifest["source_commit"] == commit
    assert marker == f"SOURCE_COMMIT={commit}\n"
    assert manifest["files"]["prompts/final_pairing/v1/prompt_sets.jsonl"] == (
        "b0b23cf1502dae53f88905ee7393b7e67f8b05f84f3251d26a6c506480a9531f"
    )
    assert manifest["files"]["prompts/final_pairing/v1/metadata.json"] == (
        "3f8e298a18c5ba03a2aaaa4a4b99302602f381ee42b024b131fd2cf63b4b59ce"
    )
