from __future__ import annotations

import ast
import base64
import io
import json
import shutil
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.markers import Marker, default_environment

from interplab.core import _schema_registry, hashing, uris
from interplab.core import environment_bundle as bundle
from interplab.core._schema_registry import (
    SchemaValidationError,
    artifact_schema_path,
)
from interplab.core._schema_registry import (
    validate as validate_schema,
)
from tests.job_test_helpers import (
    TEST_ALLIANCE_CUDA_VERSION,
    TEST_ALLIANCE_TORCH_ORIGIN,
    TEST_ALLIANCE_TORCH_VERSION,
    TEST_REPO_REVISION,
    write_cert_lane_environment_files,
    write_transformer_lens_equivalence_report,
)

_EXPORT_SHA256 = "sha256:9da00e038f1a6daba4fac4ba7b3a845787349180e339c0d5ca1a79223a678314"
_ACQUISITION_MANIFEST_SCHEMA_PATH = (
    _schema_registry.SCHEMAS_ROOT / "environment_acquisition_manifest" / "v1.schema.json"
)
_BLOCK_JSONSCHEMA_IMPORT_HOOK = '''
import sys as _sys

class _BlockJsonschemaFinder:
    _blocked = {"jsonschema", "referencing", "rpds", "attr", "attrs", "jsonschema_specifications"}

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self._blocked:
            raise ImportError(f"blocked for R9-C9 bootstrap-safety test: {fullname}")
        return None

_sys.meta_path.insert(0, _BlockJsonschemaFinder())
'''


def _source_hashes() -> dict:
    return {
        "pyproject": {"path": "pyproject.toml", "sha256": hashing.hash_file(uris.REPO_ROOT / "pyproject.toml")},
        "uv_lock": {"path": "uv.lock", "sha256": hashing.hash_file(uris.REPO_ROOT / "uv.lock")},
        "cluster_requirements": {
            "path": "slurm/requirements.cluster.txt",
            "sha256": hashing.hash_file(uris.REPO_ROOT / "slurm" / "requirements.cluster.txt"),
        },
    }


def _wheel_bytes(distribution: str, version: str) -> bytes:
    buffer = io.BytesIO()
    normalized = distribution.replace("-", "_")
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr(
            f"{normalized}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        )
        wheel.writestr(f"{normalized}-{version}.dist-info/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n")
        if distribution == "pip":
            wheel.writestr("pip/__init__.py", "__version__ = '25.0'\n")
            wheel.writestr(
                "pip/__main__.py",
                textwrap.dedent(
                    """
                    from pip._internal.cli.main import main

                    if __name__ == "__main__":
                        raise SystemExit(main())
                    """
                ).strip()
                + "\n",
            )
            wheel.writestr("pip/_internal/__init__.py", "")
            wheel.writestr("pip/_internal/cli/__init__.py", "")
            wheel.writestr(
                "pip/_internal/cli/main.py",
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import pathlib
                    import sys

                    def main() -> int:
                        target = pathlib.Path(sys.argv[-1])
                        destination = pathlib.Path(sys.prefix) / "Lib" / "site-packages" / target.name
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(target.read_bytes())
                        return 0
                    """
                ).strip()
                + "\n",
            )
    return buffer.getvalue()


def _virtualenv_creator_wheel_bytes(*, marker: str, replacement_bytes: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    replacement_b64 = (
        base64.b64encode(replacement_bytes).decode("ascii")
        if replacement_bytes is not None
        else ""
    )
    virtualenv_module = textwrap.dedent(
        f"""
        from __future__ import annotations

        import base64
        import pathlib
        import sys

        _MARKER = {marker!r}
        _REPLACEMENT_B64 = {replacement_b64!r}

        def main() -> None:
            target = pathlib.Path(sys.argv[-1])
            marker_root = target.parent
            (marker_root / f"creator-{{_MARKER}}.txt").write_text(_MARKER, encoding="utf-8")
            if _REPLACEMENT_B64:
                snapshot = target.parent / f"{{target.name}}.virtualenv-20.26.0-py3-none-any.whl"
                snapshot.write_bytes(base64.b64decode(_REPLACEMENT_B64))
            import creator_payload
            creator_payload.run(target)

        if __name__ == "__main__":
            main()
        """
    ).strip() + "\n"
    creator_payload_module = textwrap.dedent(
        f"""
        from __future__ import annotations

        import pathlib
        import venv

        _MARKER = {marker!r}

        def run(target: pathlib.Path) -> None:
            target = pathlib.Path(target)
            marker_root = target.parent
            (marker_root / f"payload-{{_MARKER}}.txt").write_text(_MARKER, encoding="utf-8")
            venv.EnvBuilder(with_pip=False).create(target)
        """
    ).strip() + "\n"
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr(
            "virtualenv-20.26.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: virtualenv\nVersion: 20.26.0\n",
        )
        wheel.writestr(
            "virtualenv-20.26.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nTag: py3-none-any\n",
        )
        wheel.writestr("virtualenv.py", virtualenv_module)
        wheel.writestr("creator_payload.py", creator_payload_module)
    return buffer.getvalue()


def _sdist_bytes(distribution: str, version: str) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        content = f"{distribution} {version}\n".encode()
        info = tarfile.TarInfo(name=f"{distribution}-{version}/PKG-INFO")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _write_artifact(
    root: Path,
    *,
    distribution: str,
    version: str,
    filename: str,
    content: bytes,
    artifact_type: str = "wheel",
    origin: str = "bundle:test",
    import_name: str | None = None,
) -> dict:
    path = root / filename
    path.write_bytes(content)
    entry = {
        "distribution": distribution,
        "version": version,
        "filename": filename,
        "relative_path": filename,
        "size_bytes": path.stat().st_size,
        "origin": origin,
        "sha256": hashing.hash_file(path),
        "type": artifact_type,
    }
    if import_name is not None:
        entry["import_name"] = import_name
    return entry


def _base_manifest(
    *,
    target: dict | None = None,
    runtime: list[dict],
    tooling: list[dict],
    torch: dict,
    derived_wheels: list[dict] | None = None,
) -> dict:
    return {
        "manifest_type": "environment_acquisition_manifest",
        "schema_version": 1,
        "source_hashes": _source_hashes(),
        "target": target or bundle.current_target(),
        "generator": {
            "uv": "0.8.22",
            "pip": "25.0",
            "virtualenv": "20.26.0",
            "build": "1.2.2",
            "hatchling": "1.27.0",
        },
        "tooling": {"installers": tooling},
        "torch": torch,
        "runtime": runtime,
        "derived_wheels": derived_wheels or [],
    }


def _write_manifest(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _minimal_bundle(tmp_path: Path) -> tuple[Path, Path, dict]:
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    alpha = _write_artifact(
        bundle_root,
        distribution="alpha",
        version="1.0",
        filename="alpha-1.0-py3-none-any.whl",
        content=_wheel_bytes("alpha", "1.0"),
        import_name="json",
    )
    pip_artifact = _write_artifact(
        bundle_root,
        distribution="pip",
        version="25.0",
        filename="pip-25.0-py3-none-any.whl",
        content=_wheel_bytes("pip", "25.0"),
    )
    setuptools_artifact = _write_artifact(
        bundle_root,
        distribution="setuptools",
        version="80.0",
        filename="setuptools-80.0-py3-none-any.whl",
        content=_wheel_bytes("setuptools", "80.0"),
    )
    wheel_artifact = _write_artifact(
        bundle_root,
        distribution="wheel",
        version="0.45.0",
        filename="wheel-0.45.0-py3-none-any.whl",
        content=_wheel_bytes("wheel", "0.45.0"),
    )
    hatchling_artifact = _write_artifact(
        bundle_root,
        distribution="hatchling",
        version="1.27.0",
        filename="hatchling-1.27.0-py3-none-any.whl",
        content=_wheel_bytes("hatchling", "1.27.0"),
    )
    virtualenv_artifact = _write_artifact(
        bundle_root,
        distribution="virtualenv",
        version="20.26.0",
        filename="virtualenv-20.26.0-py3-none-any.whl",
        content=_wheel_bytes("virtualenv", "20.26.0"),
    )
    torch_artifact = _write_artifact(
        bundle_root,
        distribution="torch",
        version=TEST_ALLIANCE_TORCH_VERSION,
        filename="torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl",
        content=_wheel_bytes("torch", TEST_ALLIANCE_TORCH_VERSION),
        origin=TEST_ALLIANCE_TORCH_ORIGIN,
        import_name="torch",
    )
    manifest = _base_manifest(
        runtime=[alpha],
        tooling=[pip_artifact, setuptools_artifact, wheel_artifact, hatchling_artifact, virtualenv_artifact],
        torch=torch_artifact,
    )
    manifest_path = _write_manifest(bundle_root / "environment-acquisition.json", manifest)
    return bundle_root, manifest_path, manifest


def _patch_minimal_export(monkeypatch: pytest.MonkeyPatch, alpha_hash: str) -> None:
    monkeypatch.setattr(
        bundle,
        "parse_requirements_export",
        lambda path: [bundle.ExportRequirement("alpha", "1.0", (alpha_hash,))],
    )
    monkeypatch.setattr(bundle, "load_lock_packages", lambda path: {"torch": {"version": "2.13.0"}})
    monkeypatch.setattr(
        bundle,
        "_validated_tooling_lock_files",
        lambda bundle_root, include_build, path=bundle._TOOLING_LOCK_FILE: bundle._tooling_install_plan(
            include_build=include_build,
            include_pip=True,
            include_uv=False,
        ),
    )


def _packaging_env(target: dict[str, str]) -> dict[str, str]:
    env = default_environment()
    env.update(bundle.marker_environment_for_target(target))
    env["platform_machine"] = target["architecture"]
    return env


def _r5_x2_config() -> dict:
    return {
        "checkpoint_hash": "sha256:3e6fdcb1187aa8e41832151af0437270fb9182fbb18bd6610e3b8145f359a564",
        "n_tokens": 10000000,
        "seq_len": 512,
        "batch_size": 8,
        "bands_version": 1,
        "eval_slice": {
            "corpus_manifest_hash": "sha256:88740b7463610b932917b5a0b0ebe81959cd4170cffe6b36fa229b0df64239dc",
            "corpus_location": "local:data/raw/fineweb_subset",
            "method": "stream_offset",
            "params": {"offset": 601369, "count": 25000},
        },
    }


def _patch_clean_git_head(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)


def _patch_live_torch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    distribution_version: str = TEST_ALLIANCE_TORCH_VERSION,
    cuda: str | None = TEST_ALLIANCE_CUDA_VERSION,
    available: bool = True,
) -> None:
    real_dist_version = bundle.dist_version

    def fake_dist_version(name: str) -> str:
        if bundle.normalize_distribution_name(name) == "torch":
            return distribution_version
        return real_dist_version(name)

    monkeypatch.setattr(bundle, "dist_version", fake_dist_version)
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            version=SimpleNamespace(cuda=cuda),
            cuda=SimpleNamespace(is_available=lambda: available),
        ),
    )


def _patch_pip_check(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int = 0,
    stdout: str = "pip-check-ok\n",
    stderr: str = "",
) -> None:
    real_run = bundle.subprocess.run

    def fake_run(args, **kwargs):
        if list(args[:3]) == [sys.executable, "-m", "pip"] and len(args) >= 4 and args[3] == "check":
            if returncode == 0:
                return SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr)
            raise subprocess.CalledProcessError(returncode, args, output=stdout, stderr=stderr)
        return real_run(args, **kwargs)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)


def _creator_entry(manifest: dict) -> dict:
    return next(
        entry for entry in manifest["tooling"]["installers"] if entry["distribution"] == "virtualenv"
    )


def _materialize_manifest_root_artifacts(bundle_root: Path, manifest_root: Path, manifest: dict) -> None:
    for entry in (_creator_entry(manifest), manifest["torch"]):
        source = bundle_root / entry["relative_path"]
        destination = manifest_root / entry["relative_path"]
        destination.write_bytes(source.read_bytes())


def test_checked_in_cluster_requirements_export_matches_locked_dependency_truth():
    requirements_path = uris.REPO_ROOT / "slurm" / "requirements.cluster.txt"
    requirements = bundle.parse_requirements_export(requirements_path)
    by_name = {requirement.distribution: requirement.version for requirement in requirements}
    lock_packages = bundle.load_lock_packages(uris.REPO_ROOT / "uv.lock")

    assert hashing.hash_file(requirements_path) == _EXPORT_SHA256
    assert len(requirements) == 114
    assert "torch" not in by_name
    assert by_name["sae-lens"] == "6.44.2" == lock_packages["sae-lens"]["version"]
    assert by_name["transformers"] == "5.12.1" == lock_packages["transformers"]["version"]
    assert by_name["transformer-lens"] == "3.2.1" == lock_packages["transformer-lens"]["version"]
    assert all(requirement.hashes for requirement in requirements)


def test_real_export_markers_match_packaging_reference():
    markers = sorted(
        {requirement.marker for requirement in bundle.parse_requirements_export(bundle.requirements_export()) if requirement.marker}
    )
    targets = [
        {"os": "linux", "architecture": "x86_64", "python": "3.11.9", "abi": "cpython-311"},
        {"os": "linux", "architecture": "aarch64", "python": "3.14.1", "abi": "cpython-314"},
        {"os": "windows", "architecture": "AMD64", "python": "3.14.1", "abi": "cpython-314"},
    ]
    assert any("platform_machine" in marker for marker in markers)

    for marker in markers:
        reference = Marker(marker)
        for target in targets:
            env = _packaging_env(target)
            assert bundle.marker_applies(marker, env) == reference.evaluate(environment=env)


def test_validate_bundle_accepts_complete_exact_offline_bundle(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])

    result = bundle.validate_bundle(
        manifest_path,
        bundle_root=bundle_root,
        venv_dir=tmp_path / "venv",
        install_manifest_path=bundle_root / "installed.json",
    )

    assert result["torch"]["version"] == TEST_ALLIANCE_TORCH_VERSION
    assert [entry["distribution"] for entry in result["runtime"]] == ["alpha"]


def test_preflight_is_bootstrap_safe_outside_repository(tmp_path):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    alpha_hash = manifest["runtime"][0]["sha256"]
    child = textwrap.dedent(
        f"""
        import importlib.util
        import pathlib
        import sys
        path = pathlib.Path(r"{(uris.REPO_ROOT / 'interplab' / 'core' / 'environment_bundle.py')}")
        spec = importlib.util.spec_from_file_location("bundle_under_test", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.parse_requirements_export = lambda _: [module.ExportRequirement("alpha", "1.0", ("{alpha_hash}",))]
        module.load_lock_packages = lambda _: {{"torch": {{"version": "2.13.0"}}}}
        module._validated_tooling_lock_files = lambda bundle_root, include_build, path=module._TOOLING_LOCK_FILE: module._tooling_install_plan(
            include_build=include_build,
            include_pip=True,
            include_uv=False,
        )
        sys.exit(module.main([
            "preflight",
            "--manifest", r"{manifest_path}",
            "--bundle-root", r"{bundle_root}",
            "--venv-dir", r"{tmp_path / 'venv'}",
            "--plan-dir", r"{tmp_path / 'plan'}",
        ]))
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", child],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "plan" / "runtime.requirements.txt").is_file()
    assert "jsonschema" not in result.stderr


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (lambda bundle_root, manifest_path, manifest: (bundle_root / manifest["runtime"][0]["filename"]).unlink(), "missing"),
        (
            lambda bundle_root, manifest_path, manifest: (bundle_root / manifest["runtime"][0]["filename"]).write_bytes(
                b"x" * (bundle_root / manifest["runtime"][0]["filename"]).stat().st_size
            ),
            "hash mismatch",
        ),
        (
            lambda bundle_root, manifest_path, manifest: manifest["runtime"].append(dict(manifest["runtime"][0], distribution="beta", filename="beta-1.0.whl", relative_path="beta-1.0.whl")),
            "unexpected",
        ),
        (
            lambda bundle_root, manifest_path, manifest: manifest["tooling"]["installers"].append(dict(manifest["tooling"]["installers"][0], distribution="build", version="1.2.2", filename="build-1.2.2-py3-none-any.whl", relative_path="build-1.2.2-py3-none-any.whl")),
            "unexpected",
        ),
    ],
)
def test_validate_bundle_failure_matrix_stops_before_target_mutation(tmp_path, monkeypatch, mutator, pattern):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    mutator(bundle_root, manifest_path, manifest)
    _write_manifest(manifest_path, manifest)
    venv_dir = tmp_path / "venv"

    with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=venv_dir)

    assert not venv_dir.exists()


def test_validate_bundle_rejects_incomplete_runtime_closure(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    monkeypatch.setattr(
        bundle,
        "parse_requirements_export",
        lambda path: [
            bundle.ExportRequirement("alpha", "1.0", (manifest["runtime"][0]["sha256"],)),
            bundle.ExportRequirement("beta", "2.0", ("sha256:" + "2" * 64,)),
        ],
    )
    monkeypatch.setattr(bundle, "load_lock_packages", lambda path: {"torch": {"version": "2.13.0"}})

    with pytest.raises(bundle.EnvironmentBundleError, match="incomplete non-torch runtime closure"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_wrong_target(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    manifest["target"]["os"] = "windows" if bundle.current_target()["os"] != "windows" else "linux"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(bundle.EnvironmentBundleError, match="target mismatch"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_stale_target_environment(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()

    with pytest.raises(bundle.EnvironmentBundleError, match="must be fresh"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=venv_dir)


def test_create_virtualenv_rejects_spoofed_python_executable_before_mutation(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    expected_staging_prefix = "venv.staging-"

    def fake_run(args, **kwargs):
        staging_path = Path(args[-1])
        staging_path.mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)

    with pytest.raises(bundle.EnvironmentBundleError, match=r"pyvenv\.cfg"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
            python_executable="spoof-python",
        )
    assert not (tmp_path / "venv").exists()
    assert not [path for path in tmp_path.iterdir() if path.name.startswith(expected_staging_prefix)]


def test_create_virtualenv_rejects_non_wheel_creator_bytes_before_mutation(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    creator_entry = _creator_entry(manifest)
    creator_path = bundle_root / creator_entry["filename"]
    creator_path.write_bytes(b"not-a-wheel")
    creator_entry["size_bytes"] = creator_path.stat().st_size
    creator_entry["sha256"] = hashing.hash_file(creator_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(bundle.EnvironmentBundleError, match="readable wheel METADATA"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
        )
    assert not (tmp_path / "venv").exists()


def test_create_virtualenv_rejects_internal_creator_metadata_mismatch_before_mutation(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    creator_entry = _creator_entry(manifest)
    creator_path = bundle_root / creator_entry["filename"]
    creator_path.write_bytes(_wheel_bytes("evil", "9.9"))
    creator_entry["size_bytes"] = creator_path.stat().st_size
    creator_entry["sha256"] = hashing.hash_file(creator_path)
    _write_manifest(manifest_path, manifest)

    with pytest.raises(bundle.EnvironmentBundleError, match="metadata Name does not identify virtualenv"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
        )
    assert not (tmp_path / "venv").exists()


def test_create_virtualenv_rejects_altered_approved_tool_hash_before_mutation(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    virtualenv_entry = _creator_entry(manifest)
    creator_path = bundle_root / virtualenv_entry["filename"]
    creator_path.write_bytes(b"x" * creator_path.stat().st_size)

    with pytest.raises(bundle.EnvironmentBundleError, match="bundle artifact hash mismatch"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
    )
    assert not (tmp_path / "venv").exists()


def test_create_virtualenv_rolls_back_partial_target_on_creator_failure(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])

    def fake_run(args, **kwargs):
        staging_path = Path(args[-1])
        staging_path.mkdir(parents=True, exist_ok=True)
        raise subprocess.CalledProcessError(1, args, stderr="boom")

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)

    with pytest.raises(bundle.EnvironmentBundleError, match="failed before creating the target venv: boom"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
        )
    assert not (tmp_path / "venv").exists()
    assert not [path for path in tmp_path.iterdir() if path.name.startswith("venv.staging-")]


def test_create_virtualenv_preserves_preexisting_target_sentinel(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    sentinel = venv_dir / "sentinel.txt"
    sentinel.write_text("keep me", encoding="utf-8")

    with pytest.raises(bundle.EnvironmentBundleError, match="must be fresh"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=venv_dir,
        )
    assert sentinel.read_text(encoding="utf-8") == "keep me"


def test_create_virtualenv_accepts_valid_creator_and_promotes_staging_target(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    venv_dir = tmp_path / "venv"
    target = manifest["target"]

    def fake_run(args, **kwargs):
        if args[0] == sys.executable:
            staging_path = Path(args[-1])
            python_path = bundle._venv_python_path(staging_path)
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("stub", encoding="utf-8")
            (staging_path / "pyvenv.cfg").write_text("home = base-python\n", encoding="utf-8")
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        staging_python = Path(args[0]).resolve()
        staging_path = staging_python.parent.parent
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "abi": target["abi"],
                    "architecture": target["architecture"],
                    "base_prefix": str(tmp_path / "base-python"),
                    "executable": str(staging_python),
                    "os": target["os"],
                    "prefix": str(staging_path),
                    "python": target["python"],
                }
            ),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    monkeypatch.setattr(bundle, "_assert_unseeded_virtualenv", lambda path: None)
    monkeypatch.setattr(bundle, "_bootstrap_private_pip", lambda **kwargs: None)
    monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", lambda path, expected_pip_version: None)

    created = bundle.create_virtualenv(
        manifest_path,
        bundle_root=bundle_root,
        venv_dir=venv_dir,
    )

    assert created["creator"] == _creator_entry(manifest)["sha256"]
    assert (venv_dir / "pyvenv.cfg").is_file()
    assert bundle._venv_python_path(venv_dir).is_file()
    assert not [path for path in tmp_path.iterdir() if path.name.startswith("venv.staging-")]


def test_create_virtualenv_atomic_promotion_preserves_existing_destination(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    venv_dir = tmp_path / "venv"
    target = manifest["target"]

    def fake_run(args, **kwargs):
        if args[0] == sys.executable:
            staging_path = Path(args[-1])
            python_path = bundle._venv_python_path(staging_path)
            python_path.parent.mkdir(parents=True, exist_ok=True)
            python_path.write_text("stub", encoding="utf-8")
            (staging_path / "pyvenv.cfg").write_text("home = base-python\n", encoding="utf-8")
            return SimpleNamespace(stdout="", stderr="", returncode=0)
        staging_python = Path(args[0]).resolve()
        staging_path = staging_python.parent.parent
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "abi": target["abi"],
                    "architecture": target["architecture"],
                    "base_prefix": str(tmp_path / "base-python"),
                    "executable": str(staging_python),
                    "os": target["os"],
                    "prefix": str(staging_path),
                    "python": target["python"],
                }
            ),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    monkeypatch.setattr(bundle, "_assert_unseeded_virtualenv", lambda path: None)
    monkeypatch.setattr(bundle, "_bootstrap_private_pip", lambda **kwargs: None)

    def create_competitor(path, expected_pip_version):
        venv_dir.mkdir()
        (venv_dir / "sentinel.txt").write_text("preserve\n", encoding="utf-8")

    monkeypatch.setattr(bundle, "_assert_bootstrapped_pip_only", create_competitor)

    with pytest.raises(bundle.EnvironmentBundleError, match="final destination already exists"):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=venv_dir,
        )

    assert (venv_dir / "sentinel.txt").read_text(encoding="utf-8") == "preserve\n"
    assert not [path for path in tmp_path.iterdir() if path.name.startswith("venv.staging-")]


def test_create_virtualenv_preserves_primary_error_when_cleanup_fails(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    sentinel = tmp_path / "outside-sentinel.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    def fake_run(args, **kwargs):
        staging_path = Path(args[-1])
        staging_path.mkdir(parents=True, exist_ok=True)
        raise subprocess.CalledProcessError(1, args, stderr="boom")

    real_rollback = bundle._rollback_partial_path

    def flaky_rollback(path):
        candidate = Path(path)
        if candidate.name.startswith("venv.staging-") or candidate.name.startswith("venv.staging-"):
            raise PermissionError("locked cleanup path")
        return real_rollback(candidate)

    monkeypatch.setattr(bundle.subprocess, "run", fake_run)
    monkeypatch.setattr(bundle, "_rollback_partial_path", flaky_rollback)

    with pytest.raises(bundle.EnvironmentBundleError, match="failed before creating the target venv: boom") as excinfo:
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=tmp_path / "venv",
        )

    assert any("cleanup failed after primary error" in note for note in getattr(excinfo.value, "__notes__", []))
    assert sentinel.read_text(encoding="utf-8") == "keep\n"


def test_create_virtualenv_executes_only_verified_creator_bytes_and_aborts_on_post_verification_replacement(
    tmp_path,
    monkeypatch,
):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    creator_entry = _creator_entry(manifest)
    creator_path = bundle_root / creator_entry["relative_path"]
    replacement_bytes = _virtualenv_creator_wheel_bytes(marker="B")
    creator_path.write_bytes(
        _virtualenv_creator_wheel_bytes(marker="A", replacement_bytes=replacement_bytes)
    )
    creator_entry["size_bytes"] = creator_path.stat().st_size
    creator_entry["sha256"] = hashing.hash_file(creator_path)
    _write_manifest(manifest_path, manifest)
    approved_hash = creator_entry["sha256"]
    replacement_hash = hashing.sha256_prefixed(replacement_bytes)
    venv_dir = tmp_path / "venv"
    sentinel = tmp_path / "sentinel.bin"
    sentinel_bytes = b"retain-me"
    sentinel.write_bytes(sentinel_bytes)

    with pytest.raises(
        bundle.EnvironmentBundleError,
        match=rf"creator snapshot hash mismatch: expected {approved_hash}, got {replacement_hash}",
    ):
        bundle.create_virtualenv(
            manifest_path,
            bundle_root=bundle_root,
            venv_dir=venv_dir,
        )

    assert (tmp_path / "creator-A.txt").read_text(encoding="utf-8") == "A"
    assert (tmp_path / "payload-A.txt").read_text(encoding="utf-8") == "A"
    assert not (tmp_path / "creator-B.txt").exists()
    assert not (tmp_path / "payload-B.txt").exists()
    assert sentinel.read_bytes() == sentinel_bytes
    assert not venv_dir.exists()
    assert not [path for path in tmp_path.iterdir() if path.name.startswith("venv.staging-")]
    assert not [path for path in tmp_path.iterdir() if path.name.startswith("creator-private-")]


def test_validate_bundle_rejects_runtime_alias_duplicates(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    manifest["runtime"][0]["distribution"] = "alpha-beta"
    alias = dict(manifest["runtime"][0], distribution="alpha.beta")
    manifest["runtime"] = [manifest["runtime"][0], alias]
    _write_manifest(manifest_path, manifest)
    monkeypatch.setattr(
        bundle,
        "parse_requirements_export",
        lambda path: [bundle.ExportRequirement("alpha-beta", "1.0", (manifest["runtime"][0]["sha256"],))],
    )
    monkeypatch.setattr(bundle, "load_lock_packages", lambda path: {"torch": {"version": "2.13.0"}})

    with pytest.raises(bundle.EnvironmentBundleError, match="normalized duplicate"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_unnormalized_distribution_name(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    manifest["runtime"][0]["distribution"] = "alpha_beta"
    _write_manifest(manifest_path, manifest)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])

    with pytest.raises(bundle.EnvironmentBundleError, match="normalized distribution name"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_path_escape(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    manifest["runtime"][0]["relative_path"] = "../escape.whl"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(bundle.EnvironmentBundleError, match="contains parent traversal"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_runtime_derived_origin_without_provenance(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    manifest["runtime"][0]["origin"] = "derived:local-build"
    _write_manifest(manifest_path, manifest)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])

    with pytest.raises(bundle.EnvironmentBundleError, match="derived origin"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_validate_bundle_rejects_derived_wheel_metadata_mismatch(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    alpha_hash = manifest["runtime"][0]["sha256"]
    source_entry = _write_artifact(
        bundle_root,
        distribution="alpha",
        version="1.0",
        filename="alpha-1.0.tar.gz",
        content=_sdist_bytes("alpha", "1.0"),
        artifact_type="sdist",
    )
    manifest["runtime"][0]["origin"] = "derived:local-build"
    target_capture = bundle._current_target_capture_fields()
    manifest["derived_wheels"] = [
        {
            "distribution": "alpha",
            "version": "1.0",
            "wheel": manifest["runtime"][0],
            "source_sdist": source_entry,
            "build_inputs": [],
            "build_requirement_mappings": [
                {
                    "raw_requirement": "build==1.2.2",
                    "normalized_name": "build",
                    "marker": None,
                    "marker_result": True,
                    "mapped_artifact": None,
                }
            ],
            "marker_environment": bundle.marker_environment_for_target(manifest["target"]),
            "build_environment": [],
            "extraction_inventory": [
                {
                    "path": "pyproject.toml",
                    "type": "file",
                    "size_bytes": 1,
                    "sha256": "sha256:" + "7" * 64,
                }
            ],
            "extraction_inventory_sha256": bundle._json_sha256(
                [
                    {
                        "path": "pyproject.toml",
                        "type": "file",
                        "size_bytes": 1,
                        "sha256": "sha256:" + "7" * 64,
                    }
                ]
            ),
            "builder": {
                **dict(manifest["target"]),
                "python_full_version": target_capture["python_full_version"],
                "implementation": target_capture["implementation"],
                "soabi": target_capture["soabi"],
                "compatible_tags": list(target_capture["compatible_tags"]),
            },
            "frontend": {
                "name": "build",
                "version": "1.2.2",
                "provider_distribution": "build",
                "module": "build",
                "module_origin": "/tmp/build.py",
                "record_path": "/tmp/build-1.2.2.dist-info/RECORD",
                "record_sha256": "sha256:" + "8" * 64,
            },
            "backend": {
                "name": "hatchling",
                "version": "1.27.0",
                "provider_distribution": "hatchling",
                "module": "hatchling.build",
                "module_origin": "/tmp/hatchling/build.py",
                "record_path": "/tmp/hatchling-1.27.0.dist-info/RECORD",
                "record_sha256": "sha256:" + "9" * 64,
                "backend_path": [],
            },
                "isolation": {
                    "mechanism": "linux-unshare-clone_newnet",
                    "parent_namespace": "net:[111]",
                    "child_namespace": "net:[222]",
                "interfaces": ["lo"],
                "routes": ["Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT"],
                "fd_targets": {"0": "pipe:[1]", "1": "pipe:[2]", "2": "pipe:[3]"},
                "descendant_namespace": "net:[222]",
                "python_connection_attempt": {"succeeded": False, "error": "OSError: offline"},
                "native_connection_attempt": {
                    "argv": ["getent", "hosts", "example.com"],
                        "returncode": 2,
                        "stdout": "",
                        "stderr": "offline",
                    },
                    "outer_argv": ["python", "-m", "build", "--wheel"],
                    "inner_argv": ["-c", "/tmp/out", "/tmp/source.tar.gz", "/tmp/evidence.json", "hatchling.build", "hatchling"],
                "frontend": {
                    "distribution": "build",
                    "module": "build",
                    "module_origin": "/tmp/build.py",
                    "version": "1.2.2",
                    "record_path": "/tmp/build-1.2.2.dist-info/RECORD",
                },
                "backend": {
                    "distribution": "hatchling",
                    "module": "hatchling.build",
                    "module_origin": "/tmp/hatchling/build.py",
                    "version": "1.27.0",
                    "record_path": "/tmp/hatchling-1.27.0.dist-info/RECORD",
                },
                },
                "command": ["python", "-m", "build", "--wheel"],
            }
    ]
    manifest["tooling"]["installers"].append(
        _write_artifact(
            bundle_root,
            distribution="build",
            version="1.2.2",
            filename="build-1.2.2-py3-none-any.whl",
            content=_wheel_bytes("build", "1.2.2"),
        )
    )
    manifest["derived_wheels"][0]["build_inputs"] = list(manifest["tooling"]["installers"])
    manifest["derived_wheels"][0]["build_requirement_mappings"][0]["mapped_artifact"] = dict(manifest["tooling"]["installers"][-1])
    manifest["derived_wheels"][0]["build_environment"] = [
        {"distribution": entry["distribution"], "version": entry["version"]}
        for entry in manifest["tooling"]["installers"]
    ]
    (bundle_root / manifest["runtime"][0]["filename"]).write_bytes(_wheel_bytes("beta", "9.9"))
    manifest["runtime"][0]["sha256"] = hashing.hash_file(bundle_root / manifest["runtime"][0]["filename"])
    manifest["runtime"][0]["size_bytes"] = (bundle_root / manifest["runtime"][0]["filename"]).stat().st_size
    _write_manifest(manifest_path, manifest)
    monkeypatch.setattr(
        bundle,
        "parse_requirements_export",
        lambda path: [
            bundle.ExportRequirement(
                "alpha",
                "1.0",
                (alpha_hash, manifest["runtime"][0]["sha256"], source_entry["sha256"]),
            )
        ],
    )
    monkeypatch.setattr(
        bundle,
        "load_lock_packages",
        lambda path: {"torch": {"version": "2.13.0"}, "alpha": {"sdist": {"url": "https://example.test/alpha-1.0.tar.gz", "hash": source_entry["sha256"]}}},
    )

    with pytest.raises(bundle.EnvironmentBundleError, match="metadata Name"):
        bundle.validate_bundle(manifest_path, bundle_root=bundle_root, venv_dir=tmp_path / "venv")


def test_record_installed_environment_writes_machine_readable_manifest(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    install_manifest_path = tmp_path / "installed.json"
    written = bundle.record_installed_environment(manifest_path, install_manifest_path)

    assert written["manifest_type"] == "environment_install_manifest"
    assert written["torch"]["version"] == TEST_ALLIANCE_TORCH_VERSION
    assert written["torch"]["cuda"] == TEST_ALLIANCE_CUDA_VERSION
    assert "json" in written["verified_imports"]
    assert install_manifest_path.is_file()


def test_record_installed_environment_rejects_empty_cuda_identity(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch, cuda=None)
    _patch_pip_check(monkeypatch)

    with pytest.raises(bundle.EnvironmentBundleError, match=r"measured install torch\.cuda"):
        bundle.record_installed_environment(manifest_path, tmp_path / "installed.json")


def test_record_installed_environment_rejects_installed_extra_distribution(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
            SimpleNamespace(metadata={"Name": "rogue"}, version="9.9"),
        ],
    )
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    with pytest.raises(bundle.EnvironmentBundleError, match="unexpected"):
        bundle.record_installed_environment(manifest_path, tmp_path / "installed.json")


def test_record_installed_environment_rejects_version_mismatch(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="9.9"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    with pytest.raises(bundle.EnvironmentBundleError, match="installed version mismatch"):
        bundle.record_installed_environment(manifest_path, tmp_path / "installed.json")


def test_record_installed_environment_rejects_dirty_worktree(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: (_ for _ in ()).throw(bundle.EnvironmentBundleError("dirty")))
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    with pytest.raises(bundle.EnvironmentBundleError, match="dirty"):
        bundle.record_installed_environment(manifest_path, tmp_path / "installed.json")


def test_record_installed_environment_rejects_failing_pip_check_and_writes_no_manifest(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch, returncode=1, stdout="broken\n")

    install_manifest_path = tmp_path / "installed.json"
    with pytest.raises(bundle.EnvironmentBundleError, match="python -m pip check failed: broken"):
        bundle.record_installed_environment(manifest_path, install_manifest_path)
    assert not install_manifest_path.exists()


def test_record_installed_environment_rejects_existing_manifest_destination(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    install_manifest_path = tmp_path / "installed.json"
    install_manifest_path.write_text("keep-me", encoding="utf-8")
    with pytest.raises(bundle.EnvironmentBundleError, match="already exists"):
        bundle.record_installed_environment(manifest_path, install_manifest_path)
    assert install_manifest_path.read_text(encoding="utf-8") == "keep-me"


def test_record_installed_environment_atomic_manifest_publication_preserves_existing_destination(tmp_path, monkeypatch):
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)
    install_manifest_path = tmp_path / "installed.json"
    real_validate_install_manifest = bundle.validate_install_manifest

    def create_competitor(payload):
        real_validate_install_manifest(payload)
        install_manifest_path.write_text("preserve\n", encoding="utf-8")

    monkeypatch.setattr(bundle, "validate_install_manifest", create_competitor)

    with pytest.raises(bundle.EnvironmentBundleError, match="already exists"):
        bundle.record_installed_environment(manifest_path, install_manifest_path)

    assert install_manifest_path.read_text(encoding="utf-8") == "preserve\n"


def test_certification_environment_inputs_are_empty_locally_without_manifest_env(monkeypatch):
    monkeypatch.delenv(bundle.ACQUISITION_MANIFEST_ENV, raising=False)
    monkeypatch.delenv(bundle.INSTALL_MANIFEST_ENV, raising=False)
    monkeypatch.delenv(bundle.EQUIVALENCE_REPORT_ENV, raising=False)
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.delenv("CC_CLUSTER", raising=False)

    assert bundle.certification_environment_inputs(stage="certify") == []


def test_certification_environment_inputs_require_manifest_refs_on_cluster(monkeypatch):
    monkeypatch.setenv("CC_CLUSTER", "1")
    monkeypatch.delenv(bundle.ACQUISITION_MANIFEST_ENV, raising=False)
    monkeypatch.delenv(bundle.INSTALL_MANIFEST_ENV, raising=False)

    with pytest.raises(bundle.EnvironmentBundleError, match="missing required ED-36"):
        bundle.certification_environment_inputs(stage="certify", config={"checkpoint_hash": "sha256:" + "1" * 64})


def test_certification_environment_inputs_include_required_roles(monkeypatch):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_inputs")

    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        refs = bundle.certification_environment_inputs(
            stage="certify",
            config={"checkpoint_hash": "sha256:" + "1" * 64},
            repo_root=uris.REPO_ROOT,
        )

        roles = [ref["role"] for ref in refs]
        assert roles == [
            "cluster_requirements",
            "environment_acquisition_manifest",
            "environment_install_manifest",
        ]
        ref_by_role = {ref["role"]: ref for ref in refs}
        assert ref_by_role["cluster_requirements"]["content_hash"] == hashing.hash_file(
            uris.REPO_ROOT / "slurm" / "requirements.cluster.txt"
        )
        assert ref_by_role["environment_acquisition_manifest"]["content_hash"] == hashing.hash_file(acquisition)
        assert ref_by_role["environment_install_manifest"]["content_hash"] == hashing.hash_file(install)
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda acquisition, install: acquisition.write_text(
                json.dumps({"manifest_type": "environment_install_manifest", "schema_version": 1}),
                encoding="utf-8",
            ),
            "acquisition manifest",
        ),
        (
            lambda acquisition, install: install.write_text("{not json", encoding="utf-8"),
            "install manifest .* is not valid JSON",
        ),
        (
            lambda acquisition, install: install.write_text(
                json.dumps({**json.loads(install.read_text(encoding="utf-8")), "manifest_type": "wrong_type"}, indent=2),
                encoding="utf-8",
            ),
            "install manifest.manifest_type",
        ),
        (
            lambda acquisition, install: install.write_text(
                json.dumps(
                    {
                        **json.loads(install.read_text(encoding="utf-8")),
                        "acquisition_manifest_hash": "sha256:" + "9" * 64,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            ),
            "acquisition_manifest_hash",
        ),
        (
            lambda acquisition, install: acquisition.write_text(
                json.dumps(
                    {
                        **json.loads(acquisition.read_text(encoding="utf-8")),
                        "source_hashes": {
                            **json.loads(acquisition.read_text(encoding="utf-8"))["source_hashes"],
                            "cluster_requirements": {
                                "path": "slurm/requirements.cluster.txt",
                                "sha256": "sha256:" + "8" * 64,
                            },
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            ),
            "source_hashes.cluster_requirements.sha256 mismatch",
        ),
    ],
)
def test_certification_environment_inputs_reject_invalid_environment_evidence(monkeypatch, mutator, pattern):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_invalid_inputs")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        mutator(acquisition, install)
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern", "refresh_entry"),
    [
        (
            lambda acquisition_payload, creator_path: creator_path.write_bytes(b"not-a-wheel"),
            "virtualenv creator artifact does not contain readable wheel METADATA",
            True,
        ),
        (
            lambda acquisition_payload, creator_path: creator_path.write_bytes(
                b"z" * creator_path.stat().st_size
            ),
            "bundle artifact hash mismatch",
            False,
        ),
        (
            lambda acquisition_payload, creator_path: creator_path.write_bytes(_wheel_bytes("evil", "9.9")),
            "virtualenv creator artifact metadata Name does not identify virtualenv",
            True,
        ),
        (
            lambda acquisition_payload, creator_path: creator_path.write_bytes(_wheel_bytes("virtualenv", "20.26.0.post1")),
            "virtualenv creator artifact metadata Version does not match the manifest",
            True,
        ),
    ],
)
def test_certification_environment_inputs_replay_creator_artifact_validation(
    monkeypatch,
    mutator,
    pattern,
    refresh_entry,
):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_creator_replay")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        acquisition_payload = json.loads(acquisition.read_text(encoding="utf-8"))
        creator_entry = _creator_entry(acquisition_payload)
        creator_path = base / creator_entry["relative_path"]
        mutator(acquisition_payload, creator_path)
        if refresh_entry:
            creator_entry["size_bytes"] = creator_path.stat().st_size
            creator_entry["sha256"] = hashing.hash_file(creator_path)
        acquisition.write_text(json.dumps(acquisition_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        install_payload = json.loads(install.read_text(encoding="utf-8"))
        install_payload["acquisition_manifest_hash"] = hashing.hash_file(acquisition)
        install.write_text(json.dumps(install_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern", "refresh_entry"),
    [
        (
            lambda acquisition_payload, torch_path: torch_path.unlink(),
            "bundle artifact missing",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__("sha256", "sha256:" + "9" * 64),
            "bundle artifact hash mismatch",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: torch_path.write_bytes(
                b"x" * torch_path.stat().st_size
            ),
            "bundle artifact hash mismatch",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__(
                "filename",
                "evil-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl",
            ),
            "torch artifact filename does not identify torch",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__(
                "size_bytes",
                acquisition_payload["torch"]["size_bytes"] + 1,
            ),
            "bundle artifact size mismatch",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__(
                "relative_path",
                "../torch-2.13.0+computecanada-cp311-cp311-linux_x86_64.whl",
            ),
            "contains parent traversal",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: torch_path.write_bytes(_wheel_bytes("evil", TEST_ALLIANCE_TORCH_VERSION)),
            "torch artifact metadata Name does not identify torch",
            True,
        ),
        (
            lambda acquisition_payload, torch_path: torch_path.write_bytes(_wheel_bytes("torch", "2.13.0+cu121")),
            "torch artifact metadata Version does not match the manifest",
            True,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__("origin", "bundle:test"),
            "approved Alliance wheelhouse provenance prefix",
            False,
        ),
        (
            lambda acquisition_payload, torch_path: acquisition_payload["torch"].__setitem__("version", "2.13.0+cu121"),
            "sanctioned Alliance version",
            False,
        ),
    ],
)
def test_certification_environment_inputs_replay_torch_artifact_validation(
    monkeypatch,
    mutator,
    pattern,
    refresh_entry,
):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_torch_replay")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        acquisition_payload = json.loads(acquisition.read_text(encoding="utf-8"))
        torch_entry = acquisition_payload["torch"]
        torch_path = base / torch_entry["relative_path"]
        mutator(acquisition_payload, torch_path)
        if refresh_entry and torch_path.exists():
            torch_entry["size_bytes"] = torch_path.stat().st_size
            torch_entry["sha256"] = hashing.hash_file(torch_path)
        acquisition.write_text(json.dumps(acquisition_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        install_payload = json.loads(install.read_text(encoding="utf-8"))
        install_payload["acquisition_manifest_hash"] = hashing.hash_file(acquisition)
        install.write_text(json.dumps(install_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda payload: payload["torch"].__setitem__("cuda", ""),
            "install manifest torch.cuda must record the measured CUDA build identity",
        ),
        (
            lambda payload: payload["torch"].__setitem__("cuda", "11.8"),
            "install manifest torch.cuda does not match the sanctioned CUDA build identity 13.2",
        ),
        (
            lambda payload: payload["torch"].__setitem__("cuda_available", False),
            "install manifest torch.cuda_available does not match the executing torch runtime",
        ),
        (
            lambda payload: payload["torch"].__setitem__("version", "2.13.0+cu121"),
            "install manifest torch.version does not match the acquisition manifest",
        ),
        (
            lambda payload: payload.__setitem__("loaded_modules", ["python/3.10.14", "arrow/25.0.0"]),
            "install manifest loaded_modules contains incompatible module provenance",
        ),
        (
            lambda payload: payload.__setitem__("loaded_modules", ["python/3.11.5", "cuda/12.1"]),
            "install manifest loaded_modules is missing required module provenance",
        ),
    ],
)
def test_certification_environment_inputs_reject_invalid_cuda_and_module_evidence(
    monkeypatch,
    mutator,
    pattern,
):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_cuda_modules")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        install_payload = json.loads(install.read_text(encoding="utf-8"))
        mutator(install_payload)
        install.write_text(json.dumps(install_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("distribution_version", "cuda", "available", "pattern"),
    [
        (
            "2.13.0+cu121",
            TEST_ALLIANCE_CUDA_VERSION,
            True,
            "install manifest torch.version does not match the executing torch distribution",
        ),
        (
            "2.12.9+computecanada",
            TEST_ALLIANCE_CUDA_VERSION,
            True,
            "install manifest torch.version does not match the executing torch distribution",
        ),
        (
            TEST_ALLIANCE_TORCH_VERSION,
            None,
            False,
            "executing torch runtime did not report a CUDA build identity",
        ),
        (
            TEST_ALLIANCE_TORCH_VERSION,
            "11.8",
            True,
            "executing torch runtime did not report the sanctioned CUDA build identity 13.2",
        ),
        (
            TEST_ALLIANCE_TORCH_VERSION,
            TEST_ALLIANCE_CUDA_VERSION,
            False,
            "executing torch runtime does not provide CUDA availability required by the production cluster profile",
        ),
    ],
)
def test_certification_environment_inputs_reject_wrong_live_torch_runtime(
    monkeypatch,
    distribution_version,
    cuda,
    available,
    pattern,
):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_live_torch_runtime")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(
            monkeypatch,
            distribution_version=distribution_version,
            cuda=cuda,
            available=available,
        )
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda payload: payload.__setitem__("extra", 1),
            "install manifest has unexpected field\\(s\\): extra",
        ),
        (
            lambda payload: payload.pop("torch"),
            "install manifest is missing required field\\(s\\): torch",
        ),
        (
            lambda payload: payload["installer_versions"].__setitem__("pip", ""),
            "installer_versions must map non-empty strings to non-empty strings",
        ),
        (
            lambda payload: payload["installed_distributions"][0].__setitem__("version", ""),
            "installed_distributions\\[0\\].version must be a non-empty string",
        ),
    ],
)
def test_manual_install_validation_matches_committed_schema(mutator, pattern):
    base, _acquisition, install = write_cert_lane_environment_files("environment_bundle_schema_parity")
    try:
        payload = json.loads(install.read_text(encoding="utf-8"))
        mutator(payload)

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.validate_install_manifest(payload)
        with pytest.raises(SchemaValidationError):
            validate_schema(payload, artifact_schema_path("environment_install_manifest", 1))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_certification_environment_inputs_require_r5_x2_equivalence_report(monkeypatch):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_missing_equivalence")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))
        monkeypatch.delenv(bundle.EQUIVALENCE_REPORT_ENV, raising=False)

        with pytest.raises(bundle.EnvironmentBundleError, match="missing required TransformerLens equivalence report"):
            bundle.certification_environment_inputs(
                stage="certify",
                config=_r5_x2_config(),
                config_path=bundle._R5_X2_AUTHORITATIVE_CONFIG_PATH,
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.parametrize(
    ("mutator", "pattern"),
    [
        (
            lambda payload: payload["checks"].__setitem__("tokenization_equal", False),
            "tokenization_equal must equal True",
        ),
        (
            lambda payload: payload.__setitem__("checkpoint_hash", "sha256:" + "1" * 64),
            "checkpoint_hash does not match hm03l7yz",
        ),
        (
            lambda payload: payload["token_stream"]["eval_slice"]["params"].__setitem__("offset", 1),
            "token_stream.eval_slice does not match",
        ),
        (
            lambda payload: payload["comparison"].__setitem__("candidate_transformer_lens", "3.2.2"),
            "candidate_transformer_lens",
        ),
        (
            lambda payload: payload["checks"].pop("sae_forward_passed"),
            "sae_forward_passed must be a boolean",
        ),
    ],
)
def test_certification_environment_inputs_reject_invalid_equivalence_reports(
    monkeypatch,
    mutator,
    pattern,
):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_equivalence_negative")
    _eq_base, report = write_transformer_lens_equivalence_report(
        "environment_bundle_equivalence_negative",
        _r5_x2_config(),
    )
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        payload = json.loads(report.read_text(encoding="utf-8"))
        mutator(payload)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))
        monkeypatch.setenv(bundle.EQUIVALENCE_REPORT_ENV, str(report))

        with pytest.raises(bundle.EnvironmentBundleError, match=pattern):
            bundle.certification_environment_inputs(
                stage="certify",
                config=_r5_x2_config(),
                config_path=bundle._R5_X2_AUTHORITATIVE_CONFIG_PATH,
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_certification_environment_inputs_include_valid_equivalence_report(monkeypatch):
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_equivalence_valid")
    _eq_base, report = write_transformer_lens_equivalence_report(
        "environment_bundle_equivalence_valid",
        _r5_x2_config(),
    )
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))
        monkeypatch.setenv(bundle.EQUIVALENCE_REPORT_ENV, str(report))

        refs = bundle.certification_environment_inputs(
            stage="certify",
            config=_r5_x2_config(),
            config_path=bundle._R5_X2_AUTHORITATIVE_CONFIG_PATH,
            repo_root=uris.REPO_ROOT,
        )

        roles = [ref["role"] for ref in refs]
        assert roles == [
            "cluster_requirements",
            "environment_acquisition_manifest",
            "environment_install_manifest",
            "transformer_lens_equivalence_report",
        ]
        ref_by_role = {ref["role"]: ref for ref in refs}
        assert ref_by_role["transformer_lens_equivalence_report"]["content_hash"] == hashing.hash_file(report)
    finally:
        shutil.rmtree(base, ignore_errors=True)


# --- R9-C9: schema-enforcement boundary (R9-A4 ruling) -----------------------
#
# The Python validators are the normative contract everywhere, pre- and
# post-activation. The schema is additive, defence-in-depth SHAPE checking at
# exactly two post-activation sites. These tests prove: (1) the module stays
# bootstrap-safe under a real blocking import hook, not just inspection; (2) the
# two sites actually consult the schema, in addition to (not instead of) the
# Python validators; (3) the directional anti-drift invariant -- Python is at
# least as strict as the schema, never the reverse.


def test_environment_bundle_module_imports_stay_bootstrap_safe():
    """R9-C9: environment_bundle.py must stay stdlib-only at module scope (plus
    interplab.core.hashing) so it can run before any venv exists (R6-C1). A
    mechanical AST check on the real top-level import statements -- not a promise
    -- so it fails the instant jsonschema (or interplab.core._schema_registry,
    which pulls it in) is added at module level."""
    source = (uris.REPO_ROOT / "interplab" / "core" / "environment_bundle.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            top_level_roots.add(node.module.split(".")[0])

    allowed = set(sys.stdlib_module_names) | {"packaging", "interplab"}
    unexpected = top_level_roots - allowed
    assert not unexpected, f"unexpected module-level import(s): {unexpected}"
    assert "interplab" in top_level_roots, "expected interplab.core.hashing at module level"
    assert "jsonschema" not in top_level_roots


def test_preflight_executes_successfully_with_jsonschema_import_blocked(tmp_path):
    """R9-C9 acceptance criterion: proven by execution under a real import-blocking
    hook, not by inspecting stderr text."""
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    alpha_hash = manifest["runtime"][0]["sha256"]
    child = _BLOCK_JSONSCHEMA_IMPORT_HOOK + textwrap.dedent(
        f"""
        import importlib.util
        import sys
        from pathlib import Path
        path = Path(r"{(uris.REPO_ROOT / 'interplab' / 'core' / 'environment_bundle.py')}")
        spec = importlib.util.spec_from_file_location("bundle_under_test", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.parse_requirements_export = lambda _: [module.ExportRequirement("alpha", "1.0", ("{alpha_hash}",))]
        module.load_lock_packages = lambda _: {{"torch": {{"version": "2.13.0"}}}}
        module._validated_tooling_lock_files = lambda bundle_root, include_build, path=module._TOOLING_LOCK_FILE: module._tooling_install_plan(
            include_build=include_build,
            include_pip=True,
            include_uv=False,
        )
        sys.exit(module.main([
            "preflight",
            "--manifest", r"{manifest_path}",
            "--bundle-root", r"{bundle_root}",
            "--venv-dir", r"{tmp_path / 'venv'}",
            "--plan-dir", r"{tmp_path / 'plan'}",
        ]))
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", child],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "plan" / "runtime.requirements.txt").is_file()


def test_create_venv_executes_successfully_with_jsonschema_import_blocked(tmp_path):
    """R9-C9 acceptance criterion: create-venv is the other pre-activation
    subcommand (setup_env.sh calls it before `source .../activate`); it must also
    survive a real jsonschema import block, not just preflight."""
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    alpha_hash = manifest["runtime"][0]["sha256"]
    target = manifest["target"]
    venv_dir = tmp_path / "venv"
    child = _BLOCK_JSONSCHEMA_IMPORT_HOOK + textwrap.dedent(
        f"""
        import json
        import importlib.util
        import sys
        from pathlib import Path
        from types import SimpleNamespace

        path = Path(r"{(uris.REPO_ROOT / 'interplab' / 'core' / 'environment_bundle.py')}")
        spec = importlib.util.spec_from_file_location("bundle_under_test", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        module.parse_requirements_export = lambda _: [module.ExportRequirement("alpha", "1.0", ("{alpha_hash}",))]
        module.load_lock_packages = lambda _: {{"torch": {{"version": "2.13.0"}}}}
        module._validated_tooling_lock_files = lambda bundle_root, include_build, path=module._TOOLING_LOCK_FILE: module._tooling_install_plan(
            include_build=include_build,
            include_pip=True,
            include_uv=False,
        )

        target = {target!r}
        tmp_root = Path(r"{tmp_path}")

        def fake_run(args, **kwargs):
            if args[0] == sys.executable:
                staging_path = Path(args[-1])
                python_path = module._venv_python_path(staging_path)
                python_path.parent.mkdir(parents=True, exist_ok=True)
                python_path.write_text("stub", encoding="utf-8")
                (staging_path / "pyvenv.cfg").write_text("home = base-python\\n", encoding="utf-8")
                return SimpleNamespace(stdout="", stderr="", returncode=0)
            staging_python = Path(args[0]).resolve()
            staging_path = staging_python.parent.parent
            return SimpleNamespace(
                stdout=json.dumps({{
                    "abi": target["abi"],
                    "architecture": target["architecture"],
                    "base_prefix": str(tmp_root / "base-python"),
                    "executable": str(staging_python),
                    "os": target["os"],
                    "prefix": str(staging_path),
                    "python": target["python"],
                }}),
                stderr="",
                returncode=0,
            )

        module.subprocess.run = fake_run
        module._assert_unseeded_virtualenv = lambda path: None
        module._bootstrap_private_pip = lambda **kwargs: None
        module._assert_bootstrapped_pip_only = lambda path, expected_pip_version: None

        module.create_virtualenv(
            r"{manifest_path}",
            bundle_root=r"{bundle_root}",
            venv_dir=r"{venv_dir}",
        )
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", child],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (venv_dir / "pyvenv.cfg").is_file()


def test_record_installed_environment_enforces_schema_in_addition_to_python_validators(tmp_path, monkeypatch):
    """R9-C9 wiring proof: this exact fixture already passes the Python validators
    unmodified (see test_record_installed_environment_writes_machine_readable_manifest);
    the only change here is forcing the schema call to fail, which proves
    record_installed_environment actually consults it -- additively, after Python
    already accepted the payload, not instead of Python."""
    bundle_root, manifest_path, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    _materialize_manifest_root_artifacts(bundle_root, tmp_path, manifest)
    monkeypatch.setattr(
        bundle,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "alpha"}, version="1.0"),
            SimpleNamespace(metadata={"Name": "pip"}, version="25.0"),
            SimpleNamespace(metadata={"Name": "setuptools"}, version="80.0"),
            SimpleNamespace(metadata={"Name": "wheel"}, version="0.45.0"),
            SimpleNamespace(metadata={"Name": "hatchling"}, version="1.27.0"),
            SimpleNamespace(metadata={"Name": "virtualenv"}, version="20.26.0"),
            SimpleNamespace(metadata={"Name": "torch"}, version=TEST_ALLIANCE_TORCH_VERSION),
            SimpleNamespace(metadata={"Name": "interplab"}, version="0.1.0"),
        ],
    )
    monkeypatch.setattr(
        bundle,
        "dist_version",
        lambda name: {
            "pip": "25.0",
            "setuptools": "80.0",
            "wheel": "0.45.0",
            "hatchling": "1.27.0",
            "virtualenv": "20.26.0",
        }[name],
    )
    monkeypatch.setattr(bundle, "_clean_git_head", lambda repo_root: TEST_REPO_REVISION)
    monkeypatch.setenv("LOADEDMODULES", "python/3.11.5:arrow/25.0.0")
    _patch_live_torch_runtime(monkeypatch)
    _patch_pip_check(monkeypatch)

    def boom(instance, schema_path):
        raise _schema_registry.SchemaValidationError("forced failure to prove wiring", ["forced"])

    monkeypatch.setattr(_schema_registry, "validate", boom)

    with pytest.raises(bundle.EnvironmentBundleError, match="acquisition manifest failed schema validation"):
        bundle.record_installed_environment(manifest_path, tmp_path / "installed.json")


def test_certification_environment_inputs_enforces_schema_in_addition_to_python_validators(monkeypatch):
    """R9-C9 wiring proof, companion to the record_installed_environment one above
    -- this fixture already passes Python validation unmodified (see
    test_certification_environment_inputs_include_required_roles); forcing the
    schema call to fail proves certification_environment_inputs consults it too."""
    base, acquisition, install = write_cert_lane_environment_files("environment_bundle_schema_wiring")
    try:
        _patch_clean_git_head(monkeypatch)
        _patch_live_torch_runtime(monkeypatch)
        monkeypatch.setenv(bundle.ACQUISITION_MANIFEST_ENV, str(acquisition))
        monkeypatch.setenv(bundle.INSTALL_MANIFEST_ENV, str(install))

        def boom(instance, schema_path):
            raise _schema_registry.SchemaValidationError("forced failure to prove wiring", ["forced"])

        monkeypatch.setattr(_schema_registry, "validate", boom)

        with pytest.raises(bundle.EnvironmentBundleError, match="acquisition manifest failed schema validation"):
            bundle.certification_environment_inputs(
                stage="certify",
                config={"checkpoint_hash": "sha256:" + "1" * 64},
                repo_root=uris.REPO_ROOT,
            )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_acquisition_manifest_anti_drift_valid_fixture_accepted_by_both(tmp_path, monkeypatch):
    """R9-C9 anti-drift corpus, class 1 (valid): the untouched fixture must be
    accepted by shape validation, semantic validation, and the schema alike."""
    _, _, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])

    bundle.validate_acquisition_manifest(manifest)
    bundle._validate_acquisition_manifest_semantics(
        manifest,
        repo_root=uris.REPO_ROOT,
        bundle_root=None,
        enforce_current_target=True,
    )
    validate_schema(manifest, _ACQUISITION_MANIFEST_SCHEMA_PATH)


def _mutate_remove_top_level_key(manifest, monkeypatch):
    del manifest["generator"]


def _mutate_add_stray_top_level_key(manifest, monkeypatch):
    manifest["unexpected_top_level_field"] = "nope"


def _mutate_wrong_schema_version(manifest, monkeypatch):
    manifest["schema_version"] = 2


def _mutate_remove_nested_required_key(manifest, monkeypatch):
    del manifest["target"]["os"]


def _mutate_add_stray_artifact_key(manifest, monkeypatch):
    manifest["runtime"][0]["unexpected"] = "nope"


@pytest.mark.parametrize(
    ("mutator", "python_pattern"),
    [
        (_mutate_remove_top_level_key, r"missing required field\(s\): generator"),
        (_mutate_add_stray_top_level_key, r"unexpected field\(s\): unexpected_top_level_field"),
        (_mutate_wrong_schema_version, r"schema_version must equal 1"),
        (_mutate_remove_nested_required_key, r"missing required field\(s\): os"),
        (_mutate_add_stray_artifact_key, r"unexpected field\(s\): unexpected"),
    ],
    ids=[
        "missing-top-level-key",
        "stray-top-level-key",
        "wrong-schema-version",
        "missing-nested-key",
        "stray-artifact-key",
    ],
)
def test_acquisition_manifest_anti_drift_shape_mutations_rejected_by_both(tmp_path, monkeypatch, mutator, python_pattern):
    """R9-C9 anti-drift corpus, class 2 (shape): every structural mutation must be
    rejected by BOTH the Python shape validator and the schema."""
    _, _, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    mutator(manifest, monkeypatch)

    with pytest.raises(bundle.EnvironmentBundleError, match=python_pattern):
        bundle.validate_acquisition_manifest(manifest)
    with pytest.raises(SchemaValidationError):
        validate_schema(manifest, _ACQUISITION_MANIFEST_SCHEMA_PATH)


def _mutate_hash_mismatch(manifest, monkeypatch):
    manifest["source_hashes"]["pyproject"]["sha256"] = "sha256:" + "0" * 64


def _mutate_unauthorized_export_hash(manifest, monkeypatch):
    manifest["runtime"][0]["sha256"] = "sha256:" + "f" * 64


def _mutate_lock_binding_mismatch(manifest, monkeypatch):
    monkeypatch.setattr(bundle, "load_lock_packages", lambda path: {"torch": {"version": "9.9.9"}})


@pytest.mark.parametrize(
    ("mutator", "python_pattern"),
    [
        (_mutate_hash_mismatch, r"source_hashes\.pyproject\.sha256 mismatch"),
        (_mutate_unauthorized_export_hash, "not authorized by the export"),
        (_mutate_lock_binding_mismatch, "torch lock version mismatch"),
    ],
    ids=["hash-mismatch", "unauthorized-export-hash", "lock-binding-mismatch"],
)
def test_acquisition_manifest_anti_drift_semantic_only_mutations_rejected_by_python_accepted_by_schema(
    tmp_path, monkeypatch, mutator, python_pattern
):
    """R9-C9 anti-drift corpus, class 3 (semantic-only, EXPECTED schema acceptance):
    these are exactly the cross-artifact checks the R9-A4 ruling names as things no
    JSON Schema can express (export hash authorization, lock binding, source-hash
    integrity). Python semantics MUST reject. Schema ACCEPTANCE here is expected and
    documented, not a gap -- the invariant is directional: Python at least as strict
    as the schema, never the reverse. Do not "fix" this by tightening the schema to
    match; that would require duplicating cross-file state the schema cannot see."""
    _, _, manifest = _minimal_bundle(tmp_path)
    _patch_minimal_export(monkeypatch, manifest["runtime"][0]["sha256"])
    mutator(manifest, monkeypatch)

    bundle.validate_acquisition_manifest(manifest)  # shape untouched -- still valid
    with pytest.raises(bundle.EnvironmentBundleError, match=python_pattern):
        bundle._validate_acquisition_manifest_semantics(
            manifest,
            repo_root=uris.REPO_ROOT,
            bundle_root=None,
            enforce_current_target=True,
        )
    validate_schema(manifest, _ACQUISITION_MANIFEST_SCHEMA_PATH)  # EXPECTED: schema accepts
