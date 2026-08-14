"""Build a no-.git Tamia archive with its runtime manifest inside.

Unlike plain ``git archive``, the emitted tarball contains a root-level
``transfer_manifest.json`` and ``SOURCE_COMMIT`` marker.  The manifest is built
from blobs at the requested commit, never from mutable working-tree bytes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

PROMPT_FILES = (
    "prompts/final_pairing/v1/prompt_sets.jsonl",
    "prompts/final_pairing/v1/metadata.json",
)
PROTOCOL_PREFIX = "protocols/final_pairing/v1/"
TRANSFER_MANIFEST_NAME = "transfer_manifest.json"
SOURCE_COMMIT_NAME = "SOURCE_COMMIT"


class ArchiveBuildError(RuntimeError):
    """The exact commit or one of its required blobs cannot be archived."""


def _git(repo_root: Path, *args: str, text: bool = False):
    process = subprocess.run(
        ("git", *args), cwd=repo_root, capture_output=True, text=text,
    )
    if process.returncode:
        stderr = process.stderr if text else process.stderr.decode("utf-8", errors="replace")
        raise ArchiveBuildError(f"git {' '.join(args)} failed: {stderr.strip()}")
    return process.stdout


def _commit_files(repo_root: Path, commit: str) -> tuple[str, ...]:
    listing = _git(
        repo_root, "ls-tree", "-r", "--name-only", commit,
        "--", PROTOCOL_PREFIX, text=True,
    )
    protocols = tuple(
        line.strip() for line in listing.splitlines()
        if line.strip().startswith(PROTOCOL_PREFIX)
    )
    if not protocols:
        raise ArchiveBuildError(f"{commit} contains no files under {PROTOCOL_PREFIX}")
    return (*PROMPT_FILES, *protocols)


def build_runtime_manifest(repo_root: Path, commit: str) -> dict:
    resolved = _git(repo_root, "rev-parse", f"{commit}^{{commit}}", text=True).strip()
    if len(resolved) != 40:
        raise ArchiveBuildError(f"resolved commit is not full 40-hex: {resolved!r}")
    files: dict[str, str] = {}
    for relative in _commit_files(repo_root, resolved):
        blob = _git(repo_root, "show", f"{resolved}:{relative}")
        files[relative] = hashlib.sha256(blob).hexdigest()
    return {"schema_version": 1, "source_commit": resolved, "files": files}


def _tar_member(name: str, payload: bytes, *, mtime: int) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = mtime
    return info, io.BytesIO(payload)


def build_archive(repo_root: Path, commit: str, output: Path) -> dict:
    repo_root = repo_root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_runtime_manifest(repo_root, commit)
    resolved = manifest["source_commit"]
    commit_time = int(_git(repo_root, "show", "-s", "--format=%ct", resolved, text=True).strip())
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    source_bytes = f"SOURCE_COMMIT={resolved}\n".encode("ascii")

    tar_path = Path(str(output) + ".tmp.tar")
    try:
        process = subprocess.run(
            ("git", "archive", "--format=tar", f"--output={tar_path}", resolved),
            cwd=repo_root, capture_output=True, text=True,
        )
        if process.returncode:
            raise ArchiveBuildError(f"git archive failed: {process.stderr.strip()}")
        with tarfile.open(tar_path, "a") as archive:
            for name, payload in (
                (TRANSFER_MANIFEST_NAME, manifest_bytes),
                (SOURCE_COMMIT_NAME, source_bytes),
            ):
                info, stream = _tar_member(name, payload, mtime=commit_time)
                archive.addfile(info, stream)
        with (
            tar_path.open("rb") as source,
            output.open("wb") as raw_output,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, mtime=0) as compressed,
        ):
            while chunk := source.read(1024 * 1024):
                compressed.write(chunk)
    finally:
        tar_path.unlink(missing_ok=True)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = Path(str(output) + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
    return {
        "source_commit": resolved,
        "archive": str(output),
        "archive_size": output.stat().st_size,
        "archive_sha256": digest,
        "sha256_sidecar": str(sidecar),
        "runtime_manifest": manifest,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_archive(args.repo_root, args.commit, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
