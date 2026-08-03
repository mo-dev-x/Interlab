from __future__ import annotations

import io
import json
import os
import subprocess
import tarfile
import textwrap
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.tags import Tag

from interplab.core import environment_bundle as bundle
from interplab.core import hashing


def _wheel_bytes(distribution: str, version: str, *, wheel_tag: str = "py3-none-any") -> bytes:
    buffer = io.BytesIO()
    normalized = distribution.replace("-", "_")
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr(
            f"{normalized}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        )
        wheel.writestr(
            f"{normalized}-{version}.dist-info/WHEEL",
            f"Wheel-Version: 1.0\nTag: {wheel_tag}\n",
        )
    return buffer.getvalue()


def _sdist_bytes(distribution: str, version: str, *, pyproject: str) -> bytes:
    buffer = io.BytesIO()
    root = f"{distribution}-{version}"
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in {
            f"{root}/pyproject.toml": pyproject,
            f"{root}/PKG-INFO": f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        }.items():
            payload = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _tar_bytes(entries: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info, payload in entries:
            archive.addfile(info, None if payload is None else io.BytesIO(payload))
    return buffer.getvalue()


def _write_artifact(
    root: Path,
    *,
    distribution: str,
    version: str,
    filename: str,
    content: bytes,
    artifact_type: str = "wheel",
    origin: str = "file://artifact",
) -> dict:
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "distribution": distribution,
        "version": version,
        "filename": filename,
        "relative_path": filename.replace("\\", "/"),
        "size_bytes": path.stat().st_size,
        "origin": origin,
        "sha256": hashing.hash_file(path),
        "type": artifact_type,
        "source_path": str(path),
    }


def _write_source_root(
    root: Path,
    *,
    alpha_hash: str,
    derived_hash: str,
    alpha_filename: str = "alpha-1.0-py3-none-any.whl",
) -> None:
    (root / "slurm").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "interplab"
            version = "0.1.0"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "slurm" / "requirements.cluster.txt").write_text(
        "\n".join(
            [
                f"alpha==1.0 --hash={alpha_hash}",
                f"py2store==0.1.22 --hash={derived_hash}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        textwrap.dedent(
            f"""
            version = 1

            [[package]]
            name = "alpha"
            version = "1.0"
            wheels = [
              {{ url = "https://example.test/{alpha_filename}", hash = "{alpha_hash}", size = 321 }}
            ]

            [[package]]
            name = "py2store"
            version = "0.1.22"
            sdist = {{ url = "https://example.test/py2store-0.1.22.tar.gz", hash = "sha256:{'4' * 64}", size = 123 }}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _fake_tool_artifact(name: str, version: str) -> dict:
    filename = f"{name.replace('-', '_')}-{version}-py3-none-any.whl"
    return {
        "distribution": name,
        "version": version,
        "filename": filename,
        "origin_url": f"https://example.test/{filename}",
        "size_bytes": 17,
        "sha256": "sha256:" + "a" * 64,
        "wheel_tags": ["py3-none-any"],
        "requires_python": ">=3.8",
        "root_is_purelib": "true",
    }


def _target_report(source_root: Path, revision: str) -> dict:
    current = bundle._current_target_capture_fields()
    return {
        "report_type": bundle._TARGET_CAPTURE_TYPE,
        "schema_version": 1,
        "created_at": "2026-08-03T00:00:00Z",
        "source_root": str(source_root),
        "repo_revision": revision,
        "source_hashes": bundle.source_hashes_for_root(source_root),
        "target": current["target"],
        "python_full_version": current["python_full_version"],
        "implementation": current["implementation"],
        "soabi": current["soabi"],
        "compatible_tags": current["compatible_tags"],
        "builder": {"name": "bundle", "python_version": current["python_full_version"]},
    }


def _git_bash() -> Path | None:
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    return candidate if candidate.is_file() else None


def test_checked_in_tooling_lock_matches_accepted_d4_evidence():
    payload = bundle.load_tooling_lock()

    assert payload["lock_type"] == bundle._TOOLING_LOCK_TYPE
    assert payload["target_host"] == {
        "os": "linux",
        "architecture": "x86_64",
        "python": "3.11.15",
        "abi": "cp311",
        "soabi": "cpython-311-x86_64-linux-gnu",
    }
    assert [entry["distribution"] for entry in payload["runtime_overlaps"]] == [
        "filelock",
        "packaging",
        "platformdirs",
        "setuptools",
    ]
    assert len(payload["artifacts"]) == 15
    assert payload["artifacts"][-1]["distribution"] == "wheel"
    assert payload["generator"]["artifact"]["filename"] == "uv-0.8.22-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    assert payload["virtualenv_embedded_seed_wheels"][0]["sha256"] == "sha256:ba0d021a166865d2265246961bec0152ff124de910c5cc39f1156ce3fa7c69dc"


def test_capture_target_report_records_exact_identity(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "slurm").mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")
    (source_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_root / "slurm" / "requirements.cluster.txt").write_text("alpha==1.0 --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
    output_path = tmp_path / "target.json"
    monkeypatch.setattr(bundle, "_validate_clean_source_root", lambda root, rev: rev)
    monkeypatch.setattr(bundle.packaging_tags, "sys_tags", lambda: [Tag("cp311", "cp311", "linux_x86_64"), Tag("py3", "none", "any")])

    payload = bundle.capture_target_report(
        output_path,
        source_root=source_root,
        expected_revision="a" * 40,
    )

    assert payload["repo_revision"] == "a" * 40
    assert payload["target"] == bundle.current_target()
    assert payload["compatible_tags"][:2] == ["cp311-cp311-linux_x86_64", "py3-none-any"]
    assert output_path.is_file()


def test_select_locked_wheel_for_target_uses_tag_precedence_then_url():
    wheels = [
        {
            "url": "https://example.test/alpha-1.0-cp311-cp311-linux_x86_64.whl",
            "hash": "sha256:" + "1" * 64,
            "size": 1,
        },
        {
            "url": "https://example.test/alpha-1.0-py3-none-any.whl",
            "hash": "sha256:" + "2" * 64,
            "size": 1,
        },
    ]
    selected = bundle._select_locked_wheel_for_target(
        "alpha",
        "1.0",
        wheels,
        ["cp311-cp311-linux_x86_64", "py3-none-any"],
    )
    assert selected["hash"] == "sha256:" + "1" * 64


def test_build_runtime_bundle_copies_locked_wheels_and_records_derived_provenance(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    alpha_filename = "alpha-1.0-py3-none-any.whl"
    alpha_hash = "sha256:" + "a" * 64
    derived_hash = "sha256:" + "b" * 64
    _write_source_root(source_root, alpha_hash=alpha_hash, derived_hash=derived_hash, alpha_filename=alpha_filename)

    target_report = _target_report(source_root, "c" * 40)
    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(target_report), encoding="utf-8")
    staging_parent = tmp_path / "staging"
    staging_parent.mkdir()
    tooling_lock_path = tmp_path / "tooling-lock.json"
    tooling_lock_path.write_text("{}", encoding="utf-8")

    tooling = [
        _fake_tool_artifact("pip", "25.0"),
        _fake_tool_artifact("setuptools", "83.0.0"),
        _fake_tool_artifact("wheel", "0.45.0"),
        _fake_tool_artifact("hatchling", "1.27.0"),
        _fake_tool_artifact("virtualenv", "20.26.0"),
        _fake_tool_artifact("build", "1.2.2"),
    ]
    monkeypatch.setattr(bundle, "_validate_clean_source_root", lambda root, rev: rev)
    monkeypatch.setattr(bundle, "load_tooling_lock", lambda path: {"lock_type": bundle._TOOLING_LOCK_TYPE})
    monkeypatch.setattr(bundle, "tooling_lock_artifacts", lambda path, include_build=True: list(tooling))
    monkeypatch.setattr(bundle, "_enforce_real_repo_runtime_expectations", lambda *args, **kwargs: None)

    def fake_download(artifact, *, destination):
        destination.write_bytes(b"x" * artifact.get("size_bytes", artifact.get("size", 1)))
        return destination

    monkeypatch.setattr(bundle, "_download_and_verify_artifact", fake_download)
    monkeypatch.setattr(
        bundle,
        "_build_derived_runtime_wheel",
        lambda **kwargs: {
            "wheel": {
                "distribution": "py2store",
                "version": "0.1.22",
                "filename": "py2store-0.1.22-py3-none-any.whl",
                "relative_path": "py2store-0.1.22-py3-none-any.whl",
                "size_bytes": 7,
                "origin": "derived:py2store-0.1.22.tar.gz",
                "sha256": derived_hash,
                "type": "wheel",
            },
            "source_sdist": {
                "distribution": "py2store",
                "version": "0.1.22",
                "filename": "py2store-0.1.22.tar.gz",
                "relative_path": "evidence/py2store/py2store-0.1.22.tar.gz",
                "size_bytes": 3,
                "origin": "https://example.test/py2store-0.1.22.tar.gz",
                "sha256": "sha256:" + "4" * 64,
                "type": "sdist",
            },
                "provenance": {
                "distribution": "py2store",
                "version": "0.1.22",
                "wheel": {
                    "distribution": "py2store",
                    "version": "0.1.22",
                    "filename": "py2store-0.1.22-py3-none-any.whl",
                    "relative_path": "py2store-0.1.22-py3-none-any.whl",
                    "size_bytes": 7,
                    "origin": "derived:py2store-0.1.22.tar.gz",
                    "sha256": derived_hash,
                    "type": "wheel",
                },
                "source_sdist": {
                    "distribution": "py2store",
                    "version": "0.1.22",
                    "filename": "py2store-0.1.22.tar.gz",
                    "relative_path": "evidence/py2store/py2store-0.1.22.tar.gz",
                    "size_bytes": 3,
                    "origin": "https://example.test/py2store-0.1.22.tar.gz",
                    "sha256": "sha256:" + "4" * 64,
                    "type": "sdist",
                },
                    "build_inputs": [
                        {
                            "distribution": "build",
                            "version": "1.2.2",
                            "filename": "build-1.2.2-py3-none-any.whl",
                            "relative_path": "build-1.2.2-py3-none-any.whl",
                            "size_bytes": 17,
                            "origin": "https://example.test/build-1.2.2-py3-none-any.whl",
                            "sha256": "sha256:" + "a" * 64,
                            "type": "wheel",
                        }
                    ],
                "builder": target_report["target"],
                "frontend": {"name": "build", "version": "1.2.2"},
                "backend": {"name": "hatchling", "version": "1.27.0"},
                "command": ["python", "-m", "build"],
            },
        },
    )

    receipt = bundle.build_runtime_bundle(
        source_root=source_root,
        expected_revision="c" * 40,
        target_report_path=target_report_path,
        tooling_lock_path=tooling_lock_path,
        staging_dir=staging_parent,
    )

    assert receipt["repo_revision"] == "c" * 40
    assert [entry["distribution"] for entry in receipt["runtime"]] == ["alpha", "py2store"]
    assert receipt["runtime"][0]["filename"] == alpha_filename
    assert receipt["derived_wheels"][0]["distribution"] == "py2store"
    stage_dir = Path(receipt["staging_dir"])
    assert stage_dir.parent == staging_parent.resolve()
    assert receipt["staging_root"] == str(stage_dir)
    assert receipt["tooling_lock_sha256"].startswith("sha256:")
    assert (stage_dir / "runtime-stage.json").is_file()


def test_build_derived_runtime_wheel_rejects_undeclared_build_input(tmp_path, monkeypatch):
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    evidence_dir = staging_dir / "evidence"
    tool_names = ["pip", "setuptools", "wheel", "hatchling", "virtualenv", "build"]
    monkeypatch.setattr(
        bundle,
        "_tooling_install_plan",
        lambda include_build, include_pip, include_uv: [
            {
                "distribution": name,
                "version": "1.0" if name != "pip" else "25.0",
                "filename": f"{name}-1.0-py3-none-any.whl" if name != "pip" else "pip-25.0-py3-none-any.whl",
                "relative_path": f"{name}-1.0-py3-none-any.whl" if name != "pip" else "pip-25.0-py3-none-any.whl",
                "size_bytes": 1,
                "origin": f"https://example.test/{name}.whl",
                "sha256": "sha256:" + name[0] * 64,
                "type": "wheel",
            }
            for name in tool_names
        ],
    )
    monkeypatch.setattr(bundle, "_bootstrap_private_pip", lambda **kwargs: None)

    def fake_run(args, **kwargs):
        if args[:4] == [bundle.sys.executable, "-m", "venv", "--without-pip"]:
            Path(args[-1]).mkdir(parents=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)

    pyproject = """
[build-system]
requires = ["rogue-builder"]
build-backend = "hatchling.build"
"""
    sdist_path = evidence_dir / "source.tar.gz"
    sdist_path.parent.mkdir(parents=True)
    sdist_bytes = _sdist_bytes("py2store", "0.1.22", pyproject=pyproject)
    sdist_path.write_bytes(sdist_bytes)
    monkeypatch.setattr(
        bundle,
        "_download_and_verify_artifact",
        lambda artifact, *, destination: destination.write_bytes(sdist_bytes),
    )

    with pytest.raises(bundle.EnvironmentBundleError, match="undeclared build requirement 'rogue-builder'"):
        bundle._build_derived_runtime_wheel(
            requirement=bundle.ExportRequirement("py2store", "0.1.22", ("sha256:" + "1" * 64,)),
            source_sdist={
                "url": "https://example.test/py2store-0.1.22.tar.gz",
                "hash": "sha256:" + "4" * 64,
                "size": len(sdist_bytes),
            },
                tooling_by_name={
                    "build": {"version": "1.2.2"},
                    "hatchling": {"version": "1.27.0"},
                    "pip": _fake_tool_artifact("pip", "25.0"),
                },
                target_report={
                    "target": bundle.current_target(),
                    "python_full_version": bundle.current_target()["python"],
                    "implementation": bundle.sys.implementation.name,
                    "soabi": bundle._current_target_capture_fields()["soabi"],
                    "compatible_tags": bundle._current_target_capture_fields()["compatible_tags"],
                },
                staging_dir=staging_dir,
            )


def test_import_alliance_torch_artifact_records_valid_receipt(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "slurm").mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='interplab'\nversion='0.1.0'\n", encoding="utf-8")
    (source_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_root / "slurm" / "requirements.cluster.txt").write_text("alpha==1.0 --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
    target_report = _target_report(source_root, "e" * 40)
    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(target_report), encoding="utf-8")
    artifact_dir = tmp_path / "torch-acquire"
    artifact_dir.mkdir()
    artifact_path = artifact_dir / "torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl"
    artifact_path.write_bytes(_wheel_bytes("torch", bundle._ALLIANCE_TORCH_VERSION))
    transcript_path = artifact_dir / "transcript.txt"
    transcript_path.write_text(
        f"--no-index --no-deps --only-binary=:all: {artifact_path.name}\n",
        encoding="utf-8",
    )
    expected_identity_path = tmp_path / "expected.json"
    expected_identity_path.write_text(
        json.dumps(
            {
                "filename": artifact_path.name,
                "size_bytes": artifact_path.stat().st_size,
                "sha256": hashing.hash_file(artifact_path),
                "distribution": "torch",
                "version": bundle._ALLIANCE_TORCH_VERSION,
                "public_version": "2.13.0",
                "origin": "alliance:wheelhouse/torch-2.13.0+computecanada-cp311",
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "receipt.json"
    original_validate = bundle._validate_clean_source_root
    bundle._validate_clean_source_root = lambda root, rev: rev

    try:
        payload = bundle.import_alliance_torch_artifact(
            artifact_path=artifact_path,
            origin="alliance:wheelhouse/torch-2.13.0+computecanada-cp311",
            transcript_path=transcript_path,
            expected_identity_path=expected_identity_path,
            target_report_path=target_report_path,
            source_root=source_root,
            expected_revision="e" * 40,
            output_path=output_path,
        )
    finally:
        bundle._validate_clean_source_root = original_validate

    assert payload["artifact"]["version"] == bundle._ALLIANCE_TORCH_VERSION
    assert payload["public_version"] == "2.13.0"
    assert output_path.is_file()


def test_finalize_bundle_publishes_hash_addressed_bundle(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "slurm").mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='interplab'\nversion='0.1.0'\n", encoding="utf-8")
    (source_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_root / "slurm" / "requirements.cluster.txt").write_text("alpha==1.0 --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(bundle, "_validate_clean_source_root", lambda root, rev: rev)
    monkeypatch.setattr(bundle, "validate_bundle", lambda *args, **kwargs: {"ok": True})

    staging_dir = tmp_path / "runtime-staging"
    staging_dir.mkdir()
    runtime_entry = _write_artifact(
        staging_dir,
        distribution="alpha",
        version="1.0",
        filename="alpha-1.0-py3-none-any.whl",
        content=_wheel_bytes("alpha", "1.0"),
    )
    tooling_entry = _write_artifact(
        staging_dir,
        distribution="pip",
        version="25.0",
        filename="pip-25.0-py3-none-any.whl",
        content=_wheel_bytes("pip", "25.0"),
    )
    runtime_entry = {key: value for key, value in runtime_entry.items() if key != "source_path"}
    tooling_entry = {key: value for key, value in tooling_entry.items() if key != "source_path"}
    target_report = _target_report(source_root, "d" * 40)
    runtime_stage = {
        "stage_type": bundle._RUNTIME_STAGE_TYPE,
        "schema_version": 1,
        "created_at": "2026-08-03T00:00:00Z",
        "source_root": str(source_root),
        "repo_revision": "d" * 40,
        "source_hashes": bundle.source_hashes_for_root(source_root),
        "target_report": target_report,
        "tooling_lock_path": str(bundle._TOOLING_LOCK_FILE),
        "tooling_lock_sha256": "sha256:" + "1" * 64,
        "staging_root": str(staging_dir),
        "tooling": [tooling_entry],
        "runtime": [runtime_entry],
        "derived_wheels": [],
    }
    (staging_dir / "runtime-stage.json").write_text(json.dumps(runtime_stage), encoding="utf-8")

    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(target_report), encoding="utf-8")
    torch_dir = tmp_path / "torch"
    torch_dir.mkdir()
    torch_artifact = _write_artifact(
        torch_dir,
        distribution="torch",
        version=bundle._ALLIANCE_TORCH_VERSION,
        filename="torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl",
        content=_wheel_bytes("torch", bundle._ALLIANCE_TORCH_VERSION),
        origin="alliance:wheelhouse/torch-2.13.0+computecanada-cp311",
    )
    torch_artifact = {key: value for key, value in torch_artifact.items() if key != "source_path"}
    torch_receipt_path = torch_dir / "torch-receipt.json"
    (torch_dir / "transcript.txt").write_text("torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl\n", encoding="utf-8")
    torch_receipt_path.write_text(
        json.dumps(
            {
                "receipt_type": bundle._TORCH_RECEIPT_TYPE,
                "schema_version": 1,
                "created_at": "2026-08-03T00:00:00Z",
                "source_root": str(source_root),
                "repo_revision": "d" * 40,
                "source_hashes": bundle.source_hashes_for_root(source_root),
                "target_report": target_report,
                "artifact": torch_artifact,
                "public_version": "2.13.0",
                "expected_identity_path": str(tmp_path / "expected.json"),
                "transcript_path": str(torch_dir / "transcript.txt"),
            }
        ),
        encoding="utf-8",
    )

    result = bundle.finalize_bundle(
        runtime_staging_dir=staging_dir,
        target_report_path=target_report_path,
        torch_receipt_path=torch_receipt_path,
        source_root=source_root,
        expected_revision="d" * 40,
        output_root=tmp_path / "published",
    )

    bundle_root = Path(result["bundle_root"])
    assert bundle_root.is_dir()
    assert (bundle_root / "environment-acquisition.json").is_file()
    assert result["manifest_hash"].startswith("sha256:")


def test_extract_sdist_rejects_parent_traversal_member(tmp_path):
    info = tarfile.TarInfo(name="../escape.txt")
    payload = b"escape"
    info.size = len(payload)
    sdist_path = tmp_path / "bad.tar.gz"
    sdist_path.write_bytes(_tar_bytes([(info, payload)]))
    destination = tmp_path / "extract"
    destination.mkdir()

    with pytest.raises(bundle.EnvironmentBundleError, match="parent traversal"):
        bundle._extract_sdist_to_directory(sdist_path, destination)


def test_extract_sdist_rejects_symlink_member(tmp_path):
    info = tarfile.TarInfo(name="pkg-1.0/link")
    info.type = tarfile.SYMTYPE
    info.linkname = "target"
    sdist_path = tmp_path / "bad-link.tar.gz"
    sdist_path.write_bytes(_tar_bytes([(info, None)]))
    destination = tmp_path / "extract"
    destination.mkdir()

    with pytest.raises(bundle.EnvironmentBundleError, match="must not be a link"):
        bundle._extract_sdist_to_directory(sdist_path, destination)


def test_build_runtime_bundle_rejects_target_report_from_other_source_root(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    _write_source_root(source_root, alpha_hash="sha256:" + "a" * 64, derived_hash="sha256:" + "b" * 64)
    other_root = tmp_path / "other"
    other_root.mkdir()
    _write_source_root(other_root, alpha_hash="sha256:" + "a" * 64, derived_hash="sha256:" + "b" * 64)
    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(_target_report(other_root, "f" * 40)), encoding="utf-8")
    tooling_lock_path = tmp_path / "tooling-lock.json"
    tooling_lock_path.write_text("{}", encoding="utf-8")
    (tmp_path / "stage-parent").mkdir()
    monkeypatch.setattr(bundle, "_validate_clean_source_root", lambda root, rev: rev)
    monkeypatch.setattr(bundle, "load_tooling_lock", lambda path: {"lock_type": bundle._TOOLING_LOCK_TYPE})

    with pytest.raises(bundle.EnvironmentBundleError, match=r"target capture\.source_root mismatch"):
        bundle.build_runtime_bundle(
            source_root=source_root,
            expected_revision="f" * 40,
            target_report_path=target_report_path,
            tooling_lock_path=tooling_lock_path,
            staging_dir=tmp_path / "stage-parent",
        )


def test_import_alliance_torch_artifact_rejects_expected_identity_mismatch(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "slurm").mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='interplab'\nversion='0.1.0'\n", encoding="utf-8")
    (source_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_root / "slurm" / "requirements.cluster.txt").write_text("alpha==1.0 --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
    target_report = _target_report(source_root, "g" * 40)
    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(target_report), encoding="utf-8")
    artifact_dir = tmp_path / "torch-acquire"
    artifact_dir.mkdir()
    artifact_path = artifact_dir / "torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl"
    artifact_path.write_bytes(_wheel_bytes("torch", bundle._ALLIANCE_TORCH_VERSION))
    transcript_path = artifact_dir / "transcript.txt"
    transcript_path.write_text(
        f"--no-index --no-deps --only-binary=:all: {artifact_path.name}\n",
        encoding="utf-8",
    )
    expected_identity_path = tmp_path / "expected.json"
    expected_identity_path.write_text(
        json.dumps(
            {
                "filename": artifact_path.name,
                "size_bytes": artifact_path.stat().st_size + 1,
                "sha256": hashing.hash_file(artifact_path),
                "distribution": "torch",
                "version": bundle._ALLIANCE_TORCH_VERSION,
                "public_version": "2.13.0",
                "origin": "alliance:wheelhouse/torch-2.13.0+computecanada-cp311",
            }
        ),
        encoding="utf-8",
    )
    original_validate = bundle._validate_clean_source_root
    bundle._validate_clean_source_root = lambda root, rev: rev
    try:
        with pytest.raises(bundle.EnvironmentBundleError, match="expected identity mismatch for size_bytes"):
            bundle.import_alliance_torch_artifact(
                artifact_path=artifact_path,
                origin="alliance:wheelhouse/torch-2.13.0+computecanada-cp311",
                transcript_path=transcript_path,
                expected_identity_path=expected_identity_path,
                target_report_path=target_report_path,
                source_root=source_root,
                expected_revision="g" * 40,
                output_path=tmp_path / "receipt.json",
            )
    finally:
        bundle._validate_clean_source_root = original_validate


def test_finalize_bundle_rejects_mismatched_torch_target_report(tmp_path, monkeypatch):
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "slurm").mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='interplab'\nversion='0.1.0'\n", encoding="utf-8")
    (source_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (source_root / "slurm" / "requirements.cluster.txt").write_text("alpha==1.0 --hash=sha256:" + "1" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(bundle, "_validate_clean_source_root", lambda root, rev: rev)
    target_report = _target_report(source_root, "h" * 40)
    mismatched_target = dict(target_report, compatible_tags=["py3-none-any", "cp999-none-any"])
    stage_dir = tmp_path / "stage"
    stage_dir.mkdir()
    runtime_entry = _write_artifact(stage_dir, distribution="alpha", version="1.0", filename="alpha-1.0-py3-none-any.whl", content=_wheel_bytes("alpha", "1.0"))
    tooling_entry = _write_artifact(stage_dir, distribution="pip", version="25.0", filename="pip-25.0-py3-none-any.whl", content=_wheel_bytes("pip", "25.0"))
    runtime_stage = {
        "stage_type": bundle._RUNTIME_STAGE_TYPE,
        "schema_version": 1,
        "created_at": "2026-08-03T00:00:00Z",
        "source_root": str(source_root),
        "repo_revision": "h" * 40,
        "source_hashes": bundle.source_hashes_for_root(source_root),
        "target_report": target_report,
        "tooling_lock_path": str(bundle._TOOLING_LOCK_FILE),
        "tooling_lock_sha256": "sha256:" + "1" * 64,
        "staging_root": str(stage_dir),
        "tooling": [{k: v for k, v in tooling_entry.items() if k != "source_path"}],
        "runtime": [{k: v for k, v in runtime_entry.items() if k != "source_path"}],
        "derived_wheels": [],
    }
    (stage_dir / "runtime-stage.json").write_text(json.dumps(runtime_stage), encoding="utf-8")
    target_report_path = tmp_path / "target.json"
    target_report_path.write_text(json.dumps(target_report), encoding="utf-8")
    torch_dir = tmp_path / "torch"
    torch_dir.mkdir()
    torch_artifact = _write_artifact(torch_dir, distribution="torch", version=bundle._ALLIANCE_TORCH_VERSION, filename="torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl", content=_wheel_bytes("torch", bundle._ALLIANCE_TORCH_VERSION), origin="alliance:wheelhouse/torch-2.13.0+computecanada-cp311")
    torch_receipt_path = torch_dir / "torch-receipt.json"
    torch_receipt_path.write_text(
        json.dumps(
            {
                "receipt_type": bundle._TORCH_RECEIPT_TYPE,
                "schema_version": 1,
                "created_at": "2026-08-03T00:00:00Z",
                "source_root": str(source_root),
                "repo_revision": "h" * 40,
                "source_hashes": bundle.source_hashes_for_root(source_root),
                "target_report": mismatched_target,
                "artifact": {k: v for k, v in torch_artifact.items() if k != "source_path"},
                "public_version": "2.13.0",
                "expected_identity_path": str(tmp_path / "expected.json"),
                "transcript_path": str(torch_dir / "transcript.txt"),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(bundle.EnvironmentBundleError, match="torch receipt and supplied target report do not describe the same captured target"):
        bundle.finalize_bundle(
            runtime_staging_dir=stage_dir,
            target_report_path=target_report_path,
            torch_receipt_path=torch_receipt_path,
            source_root=source_root,
            expected_revision="h" * 40,
            output_root=tmp_path / "published",
        )


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_requires_explicit_expected_revision_authority(tmp_path):
    bash = _git_bash()
    assert bash is not None
    manifest_path = tmp_path / "acquisition.json"
    manifest_path.write_text("{}", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH": str(manifest_path),
            "INTERPLAB_ENV_BUNDLE_ROOT": str(tmp_path),
            "INTERPLAB_VENV_DIR": str(tmp_path / "venv"),
        }
    )
    result = subprocess.run(
        [str(bash), str(Path(__file__).resolve().parents[1] / "slurm" / "setup_env.sh")],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "INTERPLAB_EXPECTED_REVISION" in result.stderr
