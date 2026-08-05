from __future__ import annotations

import argparse
import ast
import contextlib
import ctypes
import errno
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from email.parser import BytesParser
from importlib import import_module
from importlib.metadata import distributions
from importlib.metadata import version as dist_version
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from packaging import tags as packaging_tags
from packaging.requirements import Requirement as PackagingRequirement
from packaging.utils import canonicalize_name as packaging_canonicalize_name
from packaging.utils import parse_wheel_filename

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from interplab.core import hashing  # noqa: E402

ACQUISITION_MANIFEST_ENV = "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH"
INSTALL_MANIFEST_ENV = "INTERPLAB_ENV_INSTALL_MANIFEST_PATH"
EQUIVALENCE_REPORT_ENV = "INTERPLAB_TRANSFORMER_LENS_EQUIVALENCE_REPORT_PATH"

_REQUIREMENTS_FILE = REPO_ROOT / "slurm" / "requirements.cluster.txt"
_PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
_LOCK_FILE = REPO_ROOT / "uv.lock"
_TOOLING_LOCK_FILE = REPO_ROOT / "slurm" / "environment_bundle.tooling.lock.json"
_CERTIFICATION_LANE_STAGES = frozenset({"certify", "characterize", "validate", "steer"})
_BASE_TOOLING = ("pip", "setuptools", "wheel", "hatchling", "virtualenv")
_DERIVED_WHEEL_TOOLING = (*_BASE_TOOLING, "build")
_RUNTIME_MANIFEST_TYPE = "environment_acquisition_manifest"
_INSTALL_MANIFEST_TYPE = "environment_install_manifest"
_TARGET_CAPTURE_TYPE = "environment_bundle_target_capture"
_RUNTIME_STAGE_TYPE = "environment_bundle_runtime_stage"
_TORCH_RECEIPT_TYPE = "environment_bundle_torch_receipt"
_TOOLING_LOCK_TYPE = "environment_bundle_tooling_lock"
_EQUIVALENCE_REPORT_TYPE = "transformer_lens_equivalence_report"
_R5_X2_CHECKPOINT_HASH = "sha256:3e6fdcb1187aa8e41832151af0437270fb9182fbb18bd6610e3b8145f359a564"
_R5_X2_AUTHORITATIVE_CONFIG_PATH = REPO_ROOT / "configs" / "certify" / "hm03l7yz.yaml"
_R5_X2_AUTHORITATIVE_CONFIG_HASH = (
    "sha256:6dfb9e35d5f179177f8f584b050f0e480fa30bbb3753c29ca7954d6b96c9f326"
)
_R5_X2_TRANSFORMER_LENS_BASELINE = "3.2.1"
_R5_X2_TRANSFORMER_LENS_COMPARISON = "3.4.0"
_R5_X2_ACTIVATION_HOOK = "blocks.28.hook_resid_post"
_ALLIANCE_TORCH_VERSION = "2.13.0+computecanada"
_ALLIANCE_TORCH_PUBLIC_VERSION = "2.13.0"
_ALLIANCE_TORCH_CUDA_VERSION = "13.2"
_ALLIANCE_TORCH_ORIGIN_PREFIX = "alliance:wheelhouse"
_R5_X2_AUTHORITATIVE_CONFIG = {
    "checkpoint_hash": _R5_X2_CHECKPOINT_HASH,
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
_REQUIRED_LOADED_MODULES = {
    "python": "3.11",
    "arrow": None,
}
_TOOLING_LOCK_RUNTIME_OVERLAPS = frozenset({"filelock", "packaging", "platformdirs", "setuptools"})
_TOOLING_LOCK_PLATFORM_COUPLED_EXCEPTIONS = frozenset({"uv"})
_SOURCE_ONLY_RUNTIME_DISTRIBUTIONS = frozenset({"py2store", "transformers-stream-generator"})
_EXPECTED_VIRTUALENV_SEED_WHEELS = (
    ("pip", "24.0", "pip-24.0-py3-none-any.whl", "sha256:ba0d021a166865d2265246961bec0152ff124de910c5cc39f1156ce3fa7c69dc"),
    ("setuptools", "68.0.0", "setuptools-68.0.0-py3-none-any.whl", "sha256:11e52c67415a381d10d6b462ced9cfb97066179f0e871399e006c4ab101fc85f"),
    ("setuptools", "69.5.1", "setuptools-69.5.1-py3-none-any.whl", "sha256:c636ac361bc47580504644275c9ad802c50415c7522212252c033bd15f301f32"),
    ("wheel", "0.42.0", "wheel-0.42.0-py3-none-any.whl", "sha256:177f9c9b0d45c47873b619f5b650346d632cdc35fb5e4d25058e09c9e581433d"),
    ("wheel", "0.43.0", "wheel-0.43.0-py3-none-any.whl", "sha256:55c570405f142630c6b9f72fe09d9b67cf1477fcf543ae5b8dcb1f5b7377da81"),
)
_APPROVED_SOURCE_BUILD_BACKENDS = {
    "py2store": {
        "backend": "hatchling.build",
        "backend_distribution": "hatchling",
        "backend_path": [],
    },
    "transformers-stream-generator": {
        "backend": "hatchling.build",
        "backend_distribution": "hatchling",
        "backend_path": [],
    },
}
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DISTRIBUTION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
_CLONE_NEWNET = 0x40000000


class EnvironmentBundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportRequirement:
    distribution: str
    version: str
    hashes: tuple[str, ...]
    marker: str | None = None


def normalize_distribution_name(name: str) -> str:
    normalized = re.sub(r"[-_.]+", "-", name.strip()).lower()
    if not normalized:
        raise EnvironmentBundleError("distribution names must be non-empty")
    return normalized


def _require_nonempty_string(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise EnvironmentBundleError(f"{context} must be a non-empty string")
    return value


def current_target() -> dict[str, str]:
    return {
        "os": _target_os(sys.platform),
        "architecture": platform.machine().lower() or "unknown",
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "abi": sys.implementation.cache_tag or "unknown",
    }


def marker_environment_for_target(target: dict[str, str]) -> dict[str, str]:
    python_version = ".".join(target["python"].split(".")[:2])
    return {
        "implementation_name": sys.implementation.name,
        "platform_machine": target["architecture"],
        "platform_python_implementation": platform.python_implementation(),
        "python_full_version": target["python"],
        "python_version": python_version,
        "sys_platform": _sys_platform_for_target(target["os"]),
    }


def marker_environment() -> dict[str, str]:
    return marker_environment_for_target(current_target())


def requirements_export(path: str | Path = _REQUIREMENTS_FILE) -> Path:
    return Path(path)


def parse_requirements_export(path: str | Path) -> list[ExportRequirement]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    logical_lines: list[str] = []
    current_parts: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current_parts.append(stripped[:-1].rstrip() if stripped.endswith("\\") else stripped)
        if not stripped.endswith("\\"):
            logical_lines.append(" ".join(current_parts))
            current_parts = []
    if current_parts:
        logical_lines.append(" ".join(current_parts))

    requirements: list[ExportRequirement] = []
    for logical_line in logical_lines:
        hashes = tuple(
            token[len("--hash=") :]
            for token in logical_line.split()
            if token.startswith("--hash=")
        )
        line_without_hashes = " ".join(
            token for token in logical_line.split() if not token.startswith("--hash=")
        )
        requirement_part, _, marker = line_without_hashes.partition(";")
        tokens = requirement_part.split()
        if not tokens or "==" not in tokens[0]:
            raise EnvironmentBundleError(f"could not parse requirements export line: {logical_line!r}")
        distribution, version = tokens[0].split("==", 1)
        if not hashes:
            raise EnvironmentBundleError(f"requirement {distribution!r} is missing hashes in {path}")
        requirements.append(
            ExportRequirement(
                distribution=normalize_distribution_name(distribution),
                version=version,
                hashes=hashes,
                marker=marker.strip() or None,
            )
        )
    return requirements


def source_hashes_for_root(source_root: str | Path) -> dict[str, dict[str, str]]:
    root = Path(source_root).resolve()
    return {
        "pyproject": {
            "path": "pyproject.toml",
            "sha256": hashing.hash_file(root / "pyproject.toml"),
        },
        "uv_lock": {
            "path": "uv.lock",
            "sha256": hashing.hash_file(root / "uv.lock"),
        },
        "cluster_requirements": {
            "path": "slurm/requirements.cluster.txt",
            "sha256": hashing.hash_file(root / "slurm" / "requirements.cluster.txt"),
        },
    }


def _current_target_capture_fields() -> dict[str, Any]:
    soabi = (
        sysconfig.get_config_var("SOABI")
        or sysconfig.get_config_var("SO")
        or sys.implementation.cache_tag
    )
    if not isinstance(soabi, str) or not soabi:
        raise EnvironmentBundleError("could not determine the exact SOABI for target capture")
    return {
        "target": current_target(),
        "python_full_version": ".".join(str(part) for part in sys.version_info[:3]),
        "implementation": sys.implementation.name,
        "soabi": soabi,
        "compatible_tags": [str(tag) for tag in packaging_tags.sys_tags()],
    }


def _source_binding_fields(
    source_root: Path,
    *,
    revision: str,
    source_hashes: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    resolved = Path(source_root).resolve()
    return {
        "source_root": str(resolved),
        "repo_revision": revision,
        "source_hashes": json.loads(
            json.dumps(source_hashes if source_hashes is not None else source_hashes_for_root(resolved))
        ),
    }


def _assert_source_binding(
    payload: dict[str, Any],
    *,
    source_root: Path,
    revision: str,
    source_hashes: dict[str, dict[str, str]],
    context: str,
) -> None:
    expected_root = str(Path(source_root).resolve())
    actual_root = _require_string(payload, "source_root", context=context)
    if actual_root != expected_root:
        raise EnvironmentBundleError(
            f"{context}.source_root mismatch: expected {expected_root!r}, got {actual_root!r}"
        )
    actual_revision = _require_string(payload, "repo_revision", context=context)
    if actual_revision != revision:
        raise EnvironmentBundleError(
            f"{context}.repo_revision mismatch: expected {revision!r}, got {actual_revision!r}"
        )
    actual_hashes = _require_mapping(payload, "source_hashes", context=context)
    if actual_hashes != source_hashes:
        raise EnvironmentBundleError(f"{context}.source_hashes do not match the required clean source bytes")


def _assert_target_capture_matches_current_source(
    payload: dict[str, Any],
    *,
    source_root: Path,
    revision: str,
    source_hashes: dict[str, dict[str, str]],
    context: str,
) -> None:
    validate_target_capture_report(payload)
    _assert_source_binding(
        payload,
        source_root=source_root,
        revision=revision,
        source_hashes=source_hashes,
        context=context,
    )


def _assert_target_host_compatibility(payload: dict[str, Any], *, context: str) -> None:
    current = _current_target_capture_fields()
    for field in ("target", "python_full_version", "implementation", "soabi", "compatible_tags"):
        if payload[field] != current[field]:
            raise EnvironmentBundleError(
                f"{context} host mismatch for {field}: expected {payload[field]!r}, got {current[field]!r}"
            )


def _artifact_stat_identity(path: Path) -> dict[str, Any]:
    stat_result = os.stat(path)
    return {
        "st_dev": getattr(stat_result, "st_dev", None),
        "st_ino": getattr(stat_result, "st_ino", None),
        "st_mode": stat.S_IMODE(stat_result.st_mode),
        "st_size": stat_result.st_size,
        "sha256": hashing.hash_file(path),
    }


def _assert_artifact_identity(path: Path, expected: dict[str, Any], *, context: str) -> None:
    measured = _artifact_stat_identity(path)
    for field, expected_value in expected.items():
        if measured.get(field) != expected_value:
            raise EnvironmentBundleError(
                f"{context} {field} mismatch: expected {expected_value!r}, got {measured.get(field)!r}"
            )


def _open_exclusive_binary(path: Path, *, mode: int = 0o600) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if no_follow:
        flags |= no_follow
    return os.open(path, flags, mode)


def _write_bytes_noclobber(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    fd = _open_exclusive_binary(path, mode=mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except Exception:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise
    with contextlib.suppress(OSError):
        os.chmod(path, mode)


def _write_text_noclobber(path: Path, text: str, *, mode: int = 0o600) -> None:
    _write_bytes_noclobber(path, text.encode("utf-8"), mode=mode)


def _allocate_owned_directory(parent: Path, *, prefix: str, mode: int = 0o700) -> Path:
    parent_path = Path(parent).resolve()
    if not parent_path.is_dir():
        raise EnvironmentBundleError(f"staging parent {parent_path} is not a directory")
    _reject_reparse_or_symlink_path(parent_path, parent_path.parent if parent_path.parent.exists() else parent_path)
    for _ in range(64):
        candidate = (parent_path / f"{prefix}{uuid.uuid4().hex[:12]}").resolve()
        try:
            candidate.mkdir(mode=mode)
        except FileExistsError:
            continue
        with contextlib.suppress(OSError):
            os.chmod(candidate, mode)
        return candidate
    raise EnvironmentBundleError(f"could not allocate a fresh owned directory beneath {parent_path}")


def _atomic_write_json_noclobber(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_noclobber(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _rethrow_primary_with_cleanup(primary: Exception, *owned_paths: Path) -> None:
    cleanup_failures: list[str] = []
    for owned_path in owned_paths:
        try:
            _rollback_partial_path(owned_path)
        except Exception as exc:  # pragma: no cover - exercised via deterministic tests
            cleanup_failures.append(f"{owned_path}: {exc}")
    if cleanup_failures:
        primary.add_note("cleanup failed after primary error: " + " | ".join(cleanup_failures))
    raise primary


def _path_exists_or_is_link(path: Path) -> bool:
    return os.path.lexists(path)


def _atomic_promote_directory_noclobber(source: Path, destination: Path) -> None:
    source_path = Path(source).resolve()
    destination_path = Path(destination).resolve()
    if not source_path.is_dir():
        raise EnvironmentBundleError(f"atomic promotion source {source_path} is not a directory")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        move_file_ex = ctypes.windll.kernel32.MoveFileExW
        move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file_ex.restype = ctypes.c_int
        if move_file_ex(str(source_path), str(destination_path), 0x00000008):
            return
        error_code = ctypes.windll.kernel32.GetLastError()
        if error_code in {80, 183}:
            raise EnvironmentBundleError(f"final destination already exists: {destination_path}")
        raise EnvironmentBundleError(
            f"platform atomic no-clobber directory promotion failed with Windows error {error_code}"
        )
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise EnvironmentBundleError("platform cannot provide atomic non-overwriting directory promotion")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        rename_noreplace = 1
        at_fdcwd = -100
        result = renameat2(
            at_fdcwd,
            os.fsencode(str(source_path)),
            at_fdcwd,
            os.fsencode(str(destination_path)),
            rename_noreplace,
        )
        if result == 0:
            return
        error_code = ctypes.get_errno()
        if error_code == errno.EEXIST:
            raise EnvironmentBundleError(f"final destination already exists: {destination_path}")
        raise EnvironmentBundleError(
            f"platform atomic no-clobber directory promotion failed with errno {error_code}"
        )
    raise EnvironmentBundleError("platform cannot provide atomic non-overwriting directory promotion")


def _transformer_lens_version_from_entry(entry: dict[str, Any]) -> str | None:
    if normalize_distribution_name(entry.get("distribution", "")) != "transformer-lens":
        return None
    return _require_string(entry, "version", context="transformer-lens entry")


def _reject_transformer_lens_contamination(
    entries: list[dict[str, Any]],
    *,
    context: str,
    require_exact_runtime: bool = False,
) -> None:
    versions = [
        version
        for entry in entries
        if (version := _transformer_lens_version_from_entry(entry)) is not None
    ]
    if any(version == _R5_X2_TRANSFORMER_LENS_COMPARISON for version in versions):
        raise EnvironmentBundleError(
            f"{context} contains forbidden transformer-lens {_R5_X2_TRANSFORMER_LENS_COMPARISON}"
        )
    if any(version != _R5_X2_TRANSFORMER_LENS_BASELINE for version in versions):
        raise EnvironmentBundleError(
            f"{context} contains an unexpected transformer-lens version: {versions!r}"
        )
    if require_exact_runtime and versions != [_R5_X2_TRANSFORMER_LENS_BASELINE]:
        raise EnvironmentBundleError(
            f"{context} must contain exactly one transformer-lens=={_R5_X2_TRANSFORMER_LENS_BASELINE} artifact"
        )


def _runtime_stage_expected_paths(runtime_stage: dict[str, Any]) -> tuple[set[str], set[str]]:
    files = {"runtime-stage.json"}
    for entry in [*runtime_stage["tooling"], *runtime_stage["runtime"]]:
        files.add(_require_string(entry, "relative_path", context="runtime stage manifest entry"))
    for derived in runtime_stage["derived_wheels"]:
        source_path = _require_string(
            _require_mapping(derived, "source_sdist", context="runtime stage derived wheel"),
            "relative_path",
            context="runtime stage derived wheel.source_sdist",
        )
        files.add(source_path)
        files.add(str(PurePosixPath(source_path).parent / "build-receipt.json"))
    directories = {str(PurePosixPath(path).parent) for path in files if str(PurePosixPath(path).parent) != "."}
    if runtime_stage["derived_wheels"]:
        directories.add("evidence")
    return files, directories


def _expected_final_bundle_paths(manifest: dict[str, Any]) -> tuple[set[str], set[str]]:
    files = {"environment-acquisition.json", "construction-receipt.json"}
    for entry in [*manifest["tooling"]["installers"], *manifest["runtime"], manifest["torch"]]:
        files.add(_require_string(entry, "relative_path", context="final manifest entry"))
    for derived in manifest["derived_wheels"]:
        source_path = _require_string(
            _require_mapping(derived, "source_sdist", context="final derived wheel"),
            "relative_path",
            context="final derived wheel.source_sdist",
        )
        files.add(source_path)
        files.add(str(PurePosixPath(source_path).parent / "build-receipt.json"))
    directories = {str(PurePosixPath(path).parent) for path in files if str(PurePosixPath(path).parent) != "."}
    if manifest["derived_wheels"]:
        directories.add("evidence")
    return files, directories


def _validate_exact_tree(root: Path, *, expected_files: set[str], expected_directories: set[str], context: str) -> None:
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or _is_reparse_point(path):
            raise EnvironmentBundleError(f"{context} contains a symlink or reparse point at {relative}")
        if path.is_dir():
            actual_directories.add(relative)
            if relative not in expected_directories:
                raise EnvironmentBundleError(f"{context} contains an unexpected directory {relative!r}")
            continue
        actual_files.add(relative)
        if relative not in expected_files:
            raise EnvironmentBundleError(f"{context} contains an unexpected file {relative!r}")
    missing = sorted(expected_files - actual_files)
    if missing:
        raise EnvironmentBundleError(f"{context} is missing allowlisted file(s): {missing}")
    missing_directories = sorted(expected_directories - actual_directories)
    if missing_directories:
        raise EnvironmentBundleError(f"{context} is missing allowlisted directorie(s): {missing_directories}")


def _copy_relative_file(source_root: Path, destination_root: Path, relative_path: str) -> None:
    source = source_root / PurePosixPath(relative_path)
    destination = destination_root / PurePosixPath(relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _json_sha256(payload: Any) -> str:
    return hashing.sha256_prefixed(
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    )


def _directory_inventory_and_hash(root: Path) -> tuple[list[dict[str, Any]], str]:
    inventory: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or _is_reparse_point(path):
            raise EnvironmentBundleError(f"directory inventory cannot include symlink/reparse point {relative!r}")
        if path.is_dir():
            inventory.append({"path": relative, "type": "directory"})
            continue
        inventory.append(
            {
                "path": relative,
                "type": "file",
                "size_bytes": path.stat().st_size,
                "sha256": hashing.hash_file(path),
            }
        )
    return inventory, _json_sha256(inventory)

def load_tooling_lock(path: str | Path = _TOOLING_LOCK_FILE) -> dict[str, Any]:
    payload = _load_json_payload(path, context="tooling lock")
    validate_tooling_lock(payload)
    return payload


def validate_tooling_lock(payload: dict[str, Any]) -> None:
    _require_mapping(payload, context="tooling lock")
    _require_exact_keys(
        payload,
        required={
            "lock_type",
            "schema_version",
            "generator",
            "target_host",
            "platform_coupled_exceptions",
            "runtime_overlaps",
            "artifacts",
            "virtualenv_embedded_seed_wheels",
        },
        optional={"evidence_root"},
        context="tooling lock",
    )
    _require_string(payload, "lock_type", expected=_TOOLING_LOCK_TYPE, context="tooling lock")
    _require_int(payload, "schema_version", expected=1, context="tooling lock")
    _require_nullable_string(payload, "evidence_root", context="tooling lock")

    generator = _require_mapping(payload, "generator", context="tooling lock")
    _require_exact_keys(
        generator,
        required={"name", "version", "artifact"},
        context="tooling lock.generator",
    )
    _require_distribution(generator, "name", context="tooling lock.generator")
    _require_string(generator, "version", context="tooling lock.generator")
    _validate_tooling_lock_artifact(
        _require_mapping(generator, "artifact", context="tooling lock.generator"),
        context="tooling lock.generator.artifact",
    )

    target_host = _require_mapping(payload, "target_host", context="tooling lock")
    _require_exact_keys(
        target_host,
        required={"os", "architecture", "python", "abi", "soabi"},
        context="tooling lock.target_host",
    )
    for field in ("os", "architecture", "python", "abi", "soabi"):
        _require_string(target_host, field, context="tooling lock.target_host")

    platform_coupled = _require_list(payload, "platform_coupled_exceptions", context="tooling lock")
    normalized_platform_coupled = {
        normalize_distribution_name(_require_nonempty_string(value, context="tooling lock.platform_coupled_exceptions"))
        for value in platform_coupled
    }
    if normalized_platform_coupled != _TOOLING_LOCK_PLATFORM_COUPLED_EXCEPTIONS:
        raise EnvironmentBundleError(
            "tooling lock.platform_coupled_exceptions must enumerate exactly ['uv']"
        )

    runtime_overlaps = _require_list(payload, "runtime_overlaps", context="tooling lock")
    overlap_names: set[str] = set()
    for index, entry in enumerate(runtime_overlaps):
        artifact = _require_mapping(entry, context=f"tooling lock.runtime_overlaps[{index}]")
        _require_exact_keys(
            artifact,
            required={"distribution", "version", "filename", "origin_url", "size_bytes", "sha256"},
            optional={"export_hash_present"},
            context=f"tooling lock.runtime_overlaps[{index}]",
        )
        _require_distribution(artifact, "distribution", context=f"tooling lock.runtime_overlaps[{index}]")
        _require_string(artifact, "version", context=f"tooling lock.runtime_overlaps[{index}]")
        _require_string(artifact, "filename", context=f"tooling lock.runtime_overlaps[{index}]")
        _require_string(artifact, "origin_url", context=f"tooling lock.runtime_overlaps[{index}]")
        _require_int(artifact, "size_bytes", minimum=0, context=f"tooling lock.runtime_overlaps[{index}]")
        _require_sha(artifact, "sha256", context=f"tooling lock.runtime_overlaps[{index}]")
        if "export_hash_present" in artifact and not isinstance(artifact["export_hash_present"], bool):
            raise EnvironmentBundleError(
                f"tooling lock.runtime_overlaps[{index}].export_hash_present must be a boolean when present"
            )
        overlap_names.add(normalize_distribution_name(artifact["distribution"]))
    if overlap_names != _TOOLING_LOCK_RUNTIME_OVERLAPS:
        raise EnvironmentBundleError(
            "tooling lock.runtime_overlaps must enumerate exactly filelock, packaging, platformdirs, and setuptools"
        )

    artifacts = _require_list(payload, "artifacts", context="tooling lock")
    seen: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(artifacts):
        artifact = _require_mapping(entry, context=f"tooling lock.artifacts[{index}]")
        _validate_tooling_lock_artifact(artifact, context=f"tooling lock.artifacts[{index}]")
        normalized = normalize_distribution_name(artifact["distribution"])
        if normalized in seen:
            raise EnvironmentBundleError(f"tooling lock.artifacts contains duplicate distribution {normalized!r}")
        seen[normalized] = artifact
    expected_artifacts = set(_BASE_TOOLING) | {"build", "distlib", "filelock", "packaging", "pathspec", "platformdirs", "pluggy", "pyproject-hooks", "trove-classifiers", "uv"}
    if set(seen) != expected_artifacts:
        missing = sorted(expected_artifacts - set(seen))
        unexpected = sorted(set(seen) - expected_artifacts)
        raise EnvironmentBundleError(
            f"tooling lock.artifacts mismatch: missing={missing or '[]'}, unexpected={unexpected or '[]'}"
        )
    uv_artifact = seen["uv"]
    if uv_artifact["root_is_purelib"] != "false":
        raise EnvironmentBundleError("tooling lock uv artifact must preserve the accepted non-purelib identity")
    for name, artifact in seen.items():
        if name == "uv":
            continue
        for wheel_tag in artifact["wheel_tags"]:
            expanded = [str(tag) for tag in packaging_tags.parse_tag(wheel_tag)]
            for tag_text in expanded:
                _python, abi, platform_tag = tag_text.split("-")
                if abi != "none" or platform_tag != "any":
                    raise EnvironmentBundleError(
                        f"tooling lock artifact {name!r} must be pure-Python any-platform; got {tag_text}"
                    )

    seed_entries = _require_list(payload, "virtualenv_embedded_seed_wheels", context="tooling lock")
    if len(seed_entries) != len(_EXPECTED_VIRTUALENV_SEED_WHEELS):
        raise EnvironmentBundleError("tooling lock.virtualenv_embedded_seed_wheels must contain exactly five entries")
    observed_seed_keys = []
    for index, entry in enumerate(seed_entries):
        seed = _require_mapping(entry, context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_exact_keys(
            seed,
            required={"distribution", "version", "filename", "internal_path", "size_bytes", "sha256", "wheel_tags"},
            optional={"metadata_name", "metadata_version", "requires_python"},
            context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]",
        )
        _require_distribution(seed, "distribution", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_string(seed, "version", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_string(seed, "filename", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_string(seed, "internal_path", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_int(seed, "size_bytes", minimum=0, context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_sha(seed, "sha256", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        _require_list(seed, "wheel_tags", context=f"tooling lock.virtualenv_embedded_seed_wheels[{index}]")
        observed_seed_keys.append(
            (
                normalize_distribution_name(seed["distribution"]),
                seed["version"],
                seed["filename"],
                seed["sha256"],
            )
        )
    if tuple(observed_seed_keys) != _EXPECTED_VIRTUALENV_SEED_WHEELS:
        raise EnvironmentBundleError("tooling lock virtualenv embedded seed-wheel inventory does not match the accepted D4 evidence")


def _validate_tooling_lock_artifact(entry: dict[str, Any], *, context: str) -> None:
    _require_exact_keys(
        entry,
        required={
            "distribution",
            "version",
            "filename",
            "origin_url",
            "size_bytes",
            "sha256",
            "wheel_tags",
            "requires_python",
            "root_is_purelib",
        },
        optional={"metadata_name", "metadata_version", "runtime_overlap"},
        context=context,
    )
    _require_distribution(entry, "distribution", context=context)
    _require_string(entry, "version", context=context)
    _require_string(entry, "filename", context=context)
    _require_string(entry, "origin_url", context=context)
    _require_int(entry, "size_bytes", minimum=0, context=context)
    _require_sha(entry, "sha256", context=context)
    tags = _require_list(entry, "wheel_tags", context=context)
    if not tags:
        raise EnvironmentBundleError(f"{context}.wheel_tags must not be empty")
    for index, wheel_tag in enumerate(tags):
        if not isinstance(wheel_tag, str) or not wheel_tag:
            raise EnvironmentBundleError(f"{context}.wheel_tags[{index}] must be a non-empty string")
    _require_nullable_string(entry, "requires_python", context=context)
    root_is_purelib = _require_string(entry, "root_is_purelib", context=context)
    if root_is_purelib not in {"true", "false"}:
        raise EnvironmentBundleError(f"{context}.root_is_purelib must be the string 'true' or 'false'")
    _require_nullable_string(entry, "metadata_name", context=context)
    _require_nullable_string(entry, "metadata_version", context=context)
    if "runtime_overlap" in entry and not isinstance(entry["runtime_overlap"], bool):
        raise EnvironmentBundleError(f"{context}.runtime_overlap must be a boolean when present")


def tooling_lock_artifacts(
    path: str | Path = _TOOLING_LOCK_FILE,
    *,
    include_build: bool = True,
) -> list[dict[str, Any]]:
    lock = load_tooling_lock(path)
    artifacts = list(lock["artifacts"])
    if include_build:
        return artifacts
    return [
        artifact
        for artifact in artifacts
        if normalize_distribution_name(artifact["distribution"]) != "build"
    ]


def _validated_tooling_lock_files(
    bundle_root: Path,
    *,
    include_build: bool,
    path: str | Path = _TOOLING_LOCK_FILE,
) -> list[dict[str, Any]]:
    entries = []
    for artifact in tooling_lock_artifacts(path, include_build=include_build):
        manifest_entry = {
            "distribution": artifact["distribution"],
            "version": artifact["version"],
            "filename": artifact["filename"],
            "relative_path": artifact["filename"],
            "size_bytes": artifact["size_bytes"],
            "origin": artifact["origin_url"],
            "sha256": artifact["sha256"],
            "type": "wheel",
        }
        _validated_artifact_bytes(manifest_entry, bundle_root=bundle_root)
        entries.append(manifest_entry)
    return entries


def load_lock_packages(path: str | Path) -> dict[str, dict[str, Any]]:
    payload = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    packages = payload.get("package")
    if not isinstance(packages, list):
        raise EnvironmentBundleError(f"uv.lock at {path} is missing [[package]] entries")
    by_name: dict[str, dict[str, Any]] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise EnvironmentBundleError(f"uv.lock at {path} contains a non-table package entry")
        name = package.get("name")
        if not isinstance(name, str):
            raise EnvironmentBundleError(f"uv.lock at {path} contains a package without a string name")
        normalized = normalize_distribution_name(name)
        by_name[normalized] = package
    return by_name


def selected_runtime_requirements(
    manifest: dict[str, Any],
    requirements: list[ExportRequirement],
) -> list[ExportRequirement]:
    env = marker_environment_for_target(manifest["target"])
    selected = [requirement for requirement in requirements if marker_applies(requirement.marker, env)]
    if not selected:
        raise EnvironmentBundleError("requirements export selects no runtime requirements for the manifest target")
    return selected


def marker_applies(marker: str | None, env: dict[str, str]) -> bool:
    if marker is None:
        return True
    expression = ast.parse(marker, mode="eval")
    return _evaluate_marker_node(expression.body, env)


def certification_environment_inputs(
    *,
    stage: str,
    config: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> list[dict[str, str]]:
    if stage not in _CERTIFICATION_LANE_STAGES:
        return []

    acquisition = os.environ.get(ACQUISITION_MANIFEST_ENV)
    install = os.environ.get(INSTALL_MANIFEST_ENV)
    equivalence = os.environ.get(EQUIVALENCE_REPORT_ENV)
    running_on_cluster = _running_on_cluster()

    equivalence_required = _requires_transformer_lens_equivalence_report(
        stage,
        config,
        config_path=config_path,
    )

    if not acquisition and not install and not equivalence and not running_on_cluster and not equivalence_required:
        return []

    if not acquisition or not install:
        raise EnvironmentBundleError(
            "missing required ED-36 environment manifests for a certification-lane cluster run"
        )

    acquisition_manifest = load_acquisition_manifest(acquisition)
    _validate_acquisition_manifest_semantics(
        acquisition_manifest,
        repo_root=REPO_ROOT,
        bundle_root=Path(acquisition).resolve().parent,
        enforce_current_target=True,
    )
    _validate_acquisition_manifest_against_schema(acquisition_manifest)

    install_manifest = load_install_manifest(install)
    _validate_install_manifest_consistency(
        install_manifest,
        acquisition_manifest=acquisition_manifest,
        acquisition_manifest_path=acquisition,
        repo_root=REPO_ROOT,
    )

    refs: list[dict[str, str]] = [
        _file_ref(_REQUIREMENTS_FILE, role="cluster_requirements", repo_root=repo_root),
        _file_ref(acquisition, role="environment_acquisition_manifest", repo_root=repo_root),
        _file_ref(install, role="environment_install_manifest", repo_root=repo_root),
    ]
    if equivalence_required:
        if not equivalence:
            raise EnvironmentBundleError(
                "missing required TransformerLens equivalence report for R5-X2 certification"
            )
        _validate_authoritative_r5_x2_config(config=config, config_path=config_path)
        _validate_equivalence_report_path(
            equivalence,
            config=config,
            config_path=config_path,
        )
        refs.append(
            _file_ref(
                equivalence,
                role="transformer_lens_equivalence_report",
                repo_root=repo_root,
            )
        )
    return refs


def _validate_clean_source_root(source_root: Path, expected_revision: str) -> str:
    resolved = Path(source_root).resolve()
    if not resolved.is_dir():
        raise EnvironmentBundleError(f"source root {resolved} is not a directory")
    actual_revision = _clean_git_head(resolved)
    if actual_revision != expected_revision:
        raise EnvironmentBundleError(
            f"clean source revision mismatch: expected {expected_revision}, got {actual_revision}"
        )
    return actual_revision


def _real_repo_source_hashes() -> dict[str, dict[str, str]]:
    return source_hashes_for_root(REPO_ROOT)


def _enforce_real_repo_runtime_expectations(
    source_hashes: dict[str, Any],
    runtime_requirements: list[ExportRequirement],
    source_only: list[ExportRequirement],
) -> None:
    if source_hashes != _real_repo_source_hashes():
        return
    if len(runtime_requirements) != 110:
        raise EnvironmentBundleError(
            f"real repository runtime closure drifted: expected 110 marker-active non-torch distributions, got {len(runtime_requirements)}"
        )
    source_only_names = {
        (requirement.distribution, requirement.version) for requirement in source_only
    }
    expected = {
        ("py2store", "0.1.22"),
        ("transformers-stream-generator", "0.0.5"),
    }
    if source_only_names != expected:
        raise EnvironmentBundleError(
            "real repository source-only runtime set drifted: "
            f"expected {sorted(expected)!r}, got {sorted(source_only_names)!r}"
        )


def _artifact_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    if not filename:
        raise EnvironmentBundleError(f"artifact URL {url!r} does not end with a filename")
    return filename


def _manifest_entry_from_selected_artifact(
    distribution: str,
    version: str,
    selected: dict[str, Any],
) -> dict[str, Any]:
    filename = _artifact_filename_from_url(selected["url"])
    return {
        "distribution": distribution,
        "version": version,
        "filename": filename,
        "relative_path": filename,
        "size_bytes": selected["size"],
        "origin": selected["url"],
        "sha256": selected["hash"],
        "type": "wheel",
    }


def _manifest_entry_from_tooling_lock_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "distribution": artifact["distribution"],
        "version": artifact["version"],
        "filename": artifact["filename"],
        "relative_path": artifact["filename"],
        "size_bytes": artifact["size_bytes"],
        "origin": artifact["origin_url"],
        "sha256": artifact["sha256"],
        "type": "wheel",
    }


def _select_locked_wheel_for_target(
    distribution: str,
    version: str,
    wheels: list[dict[str, Any]],
    compatible_tags: list[str],
) -> dict[str, Any]:
    if not wheels:
        raise EnvironmentBundleError(
            f"runtime package {distribution!r} does not provide locked wheels for target selection"
        )
    rank_by_tag = {tag: index for index, tag in enumerate(compatible_tags)}
    candidates: list[tuple[int, str, str, dict[str, Any]]] = []
    for wheel in wheels:
        if not isinstance(wheel, dict):
            raise EnvironmentBundleError(f"runtime package {distribution!r} has a non-table wheel entry in uv.lock")
        url = _require_nonempty_string(wheel.get("url"), context=f"{distribution} wheel.url")
        filename = _artifact_filename_from_url(url)
        filename_distribution, filename_version, _build, parsed_tags = parse_wheel_filename(filename)
        if packaging_canonicalize_name(filename_distribution) != packaging_canonicalize_name(distribution):
            raise EnvironmentBundleError(
                f"runtime package {distribution!r} locked wheel filename identifies {filename_distribution!r}"
            )
        if str(filename_version) != version:
            raise EnvironmentBundleError(
                f"runtime package {distribution!r} locked wheel filename version mismatch: expected {version}, got {filename_version}"
            )
        matched_ranks = sorted(
            rank_by_tag[str(tag)]
            for tag in parsed_tags
            if str(tag) in rank_by_tag
        )
        if not matched_ranks:
            continue
        candidates.append((matched_ranks[0], url, filename, wheel))
    if not candidates:
        raise EnvironmentBundleError(
            f"runtime package {distribution!r} has no wheel compatible with the captured target tags"
        )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def _download_and_verify_artifact(artifact: dict[str, Any], *, destination: Path) -> Path:
    if destination.exists():
        raise EnvironmentBundleError(f"refusing to overwrite artifact destination {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_path = artifact.get("source_path")
    if isinstance(source_path, str) and source_path:
        shutil.copyfile(Path(source_path), destination)
    else:
        try:
            with urlopen(_require_nonempty_string(artifact.get("origin_url") or artifact.get("url"), context="artifact origin")) as response:
                destination.write_bytes(response.read())
        except OSError as exc:
            raise EnvironmentBundleError(
                f"could not acquire artifact {_require_nonempty_string(artifact.get('filename') or _artifact_filename_from_url(artifact.get('origin_url') or artifact.get('url')), context='artifact filename')!r}"
            ) from exc
    expected_size = artifact.get("size_bytes", artifact.get("size"))
    expected_hash = artifact.get("sha256", artifact.get("hash"))
    if not isinstance(expected_size, int) or expected_size < 0:
        raise EnvironmentBundleError("artifact size metadata must be a non-negative integer")
    if not isinstance(expected_hash, str):
        raise EnvironmentBundleError("artifact hash metadata must be present")
    actual_size = destination.stat().st_size
    if actual_size != expected_size:
        raise EnvironmentBundleError(
            f"artifact size mismatch for {destination.name}: expected {expected_size}, got {actual_size}"
        )
    actual_hash = hashing.hash_file(destination)
    if actual_hash != expected_hash:
        raise EnvironmentBundleError(
            f"artifact hash mismatch for {destination.name}: expected {expected_hash}, got {actual_hash}"
        )
    return destination


def _read_wheel_metadata(path: Path) -> dict[str, str]:
    return _read_wheel_identity(path, context=f"wheel artifact {path.name!r}")


def _tooling_install_plan(
    *,
    include_build: bool,
    include_pip: bool,
    include_uv: bool,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for artifact in tooling_lock_artifacts(include_build=include_build):
        normalized = normalize_distribution_name(artifact["distribution"])
        if normalized == "uv" and not include_uv:
            continue
        if normalized == "pip" and not include_pip:
            continue
        selected.append(_manifest_entry_from_tooling_lock_artifact(artifact))
    return selected


def _derived_wheel_command(
    *,
    env_python: Path,
    sdist_path: Path,
    out_dir: Path,
    evidence_path: Path,
    backend_module: str,
    backend_provider: str,
) -> list[str]:
    return [
        str(env_python),
        "-I",
        "-c",
        _build_no_network_child_source(),
        str(out_dir),
        str(sdist_path),
        str(evidence_path),
        backend_module,
        backend_provider,
    ]


def _build_no_network_child_source() -> str:
    return """
import importlib
import importlib.metadata
import json
import os
import pathlib
import runpy
import socket
import subprocess
import sys
import tempfile
import urllib.request

def _deny(*args, **kwargs):
    raise RuntimeError("network access is forbidden during offline derived-wheel construction")

sitecustomize_source = '''
import socket
import urllib.request

def _deny(*args, **kwargs):
    raise RuntimeError("network access is forbidden during offline derived-wheel construction")

socket.create_connection = _deny
socket.getaddrinfo = _deny
socket.gethostbyname = _deny
socket.gethostbyname_ex = _deny
socket.gethostbyaddr = _deny
urllib.request.urlopen = _deny

class _DeniedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        _deny(*args, **kwargs)

    def connect_ex(self, *args, **kwargs):
        _deny(*args, **kwargs)

socket.socket = _DeniedSocket
'''

socket.create_connection = _deny
socket.getaddrinfo = _deny
socket.gethostbyname = _deny
socket.gethostbyname_ex = _deny
socket.gethostbyaddr = _deny
urllib.request.urlopen = _deny

class _DeniedSocket(socket.socket):
    def connect(self, *args, **kwargs):
        _deny(*args, **kwargs)

    def connect_ex(self, *args, **kwargs):
        _deny(*args, **kwargs)

socket.socket = _DeniedSocket
with tempfile.TemporaryDirectory(prefix="interplab-build-net-deny-") as site_dir:
    site_dir_path = pathlib.Path(site_dir)
    (site_dir_path / "sitecustomize.py").write_text(sitecustomize_source, encoding="utf-8")
    existing_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = (
        str(site_dir_path)
        if not existing_pythonpath
        else str(site_dir_path) + os.pathsep + existing_pythonpath
    )
    original_argv = list(sys.argv)
    evidence_path = pathlib.Path(sys.argv[3])
    backend_module_name = sys.argv[4]
    backend_provider = sys.argv[5]
    frontend_module = importlib.import_module("build")
    backend_module = importlib.import_module(backend_module_name)
    frontend_dist = importlib.metadata.distribution("build")
    backend_dist = importlib.metadata.distribution(backend_provider)
    fd_targets = {}
    for fd_name in sorted(os.listdir("/proc/self/fd")):
        fd_path = pathlib.Path("/proc/self/fd") / fd_name
        try:
            fd_targets[fd_name] = os.readlink(fd_path)
        except OSError as exc:
            fd_targets[fd_name] = f"unreadable:{type(exc).__name__}:{exc}"
    socket_fds = {
        fd_name: target
        for fd_name, target in fd_targets.items()
        if isinstance(target, str) and target.startswith("socket:")
    }
    if socket_fds:
        raise RuntimeError(f"inherited socket descriptors are forbidden: {socket_fds}")
    routes = pathlib.Path("/proc/net/route").read_text(encoding="utf-8").splitlines()
    interfaces = sorted(path.name for path in pathlib.Path("/sys/class/net").iterdir())
    descendant_namespace = subprocess.run(
        ["readlink", "/proc/self/ns/net"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    python_attempt = {}
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=0.2)
        python_attempt = {"succeeded": True}
    except Exception as exc:
        python_attempt = {"succeeded": False, "error": f"{type(exc).__name__}: {exc}"}
    if python_attempt["succeeded"]:
        raise RuntimeError("python connection attempt unexpectedly succeeded inside isolated build namespace")
    native_attempt = subprocess.run(
        ["getent", "hosts", "example.com"],
        capture_output=True,
        text=True,
        check=False,
    )
    if native_attempt.returncode == 0:
        raise RuntimeError("native descendant network lookup unexpectedly succeeded inside isolated build namespace")
    frontend_record = next(
        str(frontend_dist.locate_file(candidate))
        for candidate in frontend_dist.files or []
        if str(candidate).endswith("RECORD")
    )
    backend_record = next(
        str(backend_dist.locate_file(candidate))
        for candidate in backend_dist.files or []
        if str(candidate).endswith("RECORD")
    )
    evidence = {
        "mechanism": "linux-unshare-clone_newnet",
        "parent_namespace": os.environ["INTERPLAB_PARENT_NETNS"],
        "child_namespace": os.readlink("/proc/self/ns/net"),
        "interfaces": interfaces,
        "routes": routes,
        "fd_targets": fd_targets,
        "descendant_namespace": descendant_namespace,
        "python_connection_attempt": python_attempt,
        "native_connection_attempt": {
            "argv": ["getent", "hosts", "example.com"],
            "returncode": native_attempt.returncode,
            "stdout": native_attempt.stdout,
            "stderr": native_attempt.stderr,
        },
        "outer_argv": json.loads(os.environ["INTERPLAB_OUTER_ARGV"]),
        "inner_argv": original_argv,
        "frontend": {
            "distribution": "build",
            "module": "build",
            "module_origin": getattr(frontend_module, "__file__", ""),
            "version": frontend_dist.version,
            "record_path": frontend_record,
        },
        "backend": {
            "distribution": backend_provider,
            "module": backend_module_name,
            "module_origin": getattr(backend_module, "__file__", ""),
            "version": backend_dist.version,
            "record_path": backend_record,
        },
    }
    if evidence["parent_namespace"] == evidence["child_namespace"]:
        raise RuntimeError("linux network namespace isolation did not change namespace identity")
    if any(name != "lo" for name in interfaces):
        raise RuntimeError(f"isolated build namespace exposed external interfaces: {interfaces}")
    non_header_routes = [line for line in routes[1:] if line.strip()]
    if non_header_routes:
        raise RuntimeError(f"isolated build namespace exposed routes: {non_header_routes}")
    sys.argv = [
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        sys.argv[1],
        sys.argv[2],
    ]
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    runpy.run_module("build", run_name="__main__")
"""


def _derived_build_subprocess_kwargs() -> dict[str, Any]:
    if not sys.platform.startswith("linux"):
        raise EnvironmentBundleError("derived wheel construction requires a Linux host with kernel namespace support")
    libc = ctypes.CDLL(None, use_errno=True)
    unshare = getattr(libc, "unshare", None)
    if unshare is None:
        raise EnvironmentBundleError("linux host cannot provide the unshare syscall required for derived-wheel isolation")
    unshare.argtypes = [ctypes.c_int]
    unshare.restype = ctypes.c_int

    def _preexec() -> None:
        result = unshare(_CLONE_NEWNET)
        if result != 0:
            error_code = ctypes.get_errno()
            raise OSError(error_code, os.strerror(error_code))

    return {"preexec_fn": _preexec}


def _safe_extract_member_path(member_name: str, destination: Path) -> Path:
    pure = PurePosixPath(member_name)
    if pure.is_absolute():
        raise EnvironmentBundleError(f"source archive member {member_name!r} must not be absolute")
    if any(part == ".." for part in pure.parts):
        raise EnvironmentBundleError(f"source archive member {member_name!r} must not contain parent traversal")
    candidate = destination.joinpath(*pure.parts)
    resolved = candidate.resolve(strict=False)
    if resolved != destination and destination not in resolved.parents:
        raise EnvironmentBundleError(f"source archive member {member_name!r} escapes the extraction root")
    return candidate


def _extract_sdist_to_directory(sdist_path: Path, destination: Path) -> Path:
    seen: dict[str, str] = {}
    normalized_seen: dict[str, str] = {}
    try:
        with tarfile.open(sdist_path, "r:gz") as archive:
            for member in archive.getmembers():
                relative_name = member.name.rstrip("/")
                if not relative_name:
                    continue
                if member.issym() or member.islnk():
                    raise EnvironmentBundleError(f"source archive member {member.name!r} must not be a link")
                if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                    raise EnvironmentBundleError(
                        f"source archive member {member.name!r} uses an unsupported special file type"
                    )
                if not (member.isdir() or member.isfile()):
                    raise EnvironmentBundleError(
                        f"source archive member {member.name!r} uses an unsupported archive entry type"
                    )
                target = _safe_extract_member_path(relative_name, destination)
                relative_key = str(target.relative_to(destination)).replace("\\", "/")
                normalized_relative_key = "/".join(part.casefold() for part in PurePosixPath(relative_key).parts)
                entry_type = "dir" if member.isdir() else "file"
                previous = seen.get(relative_key)
                if previous is not None and previous != entry_type:
                    raise EnvironmentBundleError(
                        f"source archive member {member.name!r} conflicts with an existing extracted path"
                    )
                normalized_previous = normalized_seen.get(normalized_relative_key)
                if normalized_previous is not None and normalized_previous != relative_key:
                    raise EnvironmentBundleError(
                        f"source archive member {member.name!r} conflicts with an existing normalized extracted path"
                    )
                seen[relative_key] = entry_type
                normalized_seen[normalized_relative_key] = relative_key
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise EnvironmentBundleError(
                        f"source archive member {member.name!r} could not be read as a regular file"
                    )
                with source, open(target, "xb") as handle:
                    shutil.copyfileobj(source, handle)
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown sdist extraction failure"),
            destination,
        )
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        _rethrow_primary_with_cleanup(
            EnvironmentBundleError(
                f"source distribution {sdist_path.name!r} must unpack to exactly one top-level directory"
            ),
            destination,
        )
    return roots[0]


def _normalize_build_requirement(raw_requirement: str, *, target_env: dict[str, str], context: str) -> PackagingRequirement | None:
    requirement = PackagingRequirement(_require_nonempty_string(raw_requirement, context=context))
    if requirement.marker is not None and not requirement.marker.evaluate(environment=target_env):
        return None
    return requirement


def _validate_build_system_contract(
    distribution: str,
    *,
    build_system: dict[str, Any],
    build_inputs: list[dict[str, Any]],
    target_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    approved_contract = _APPROVED_SOURCE_BUILD_BACKENDS.get(distribution)
    if approved_contract is None:
        raise EnvironmentBundleError(f"derived wheel {distribution!r} has no approved build backend contract")
    requires = build_system.get("requires")
    if not isinstance(requires, list) or not requires:
        raise EnvironmentBundleError(f"derived wheel source {distribution!r} must declare build-system.requires")
    target_env = marker_environment_for_target(target_report["target"])
    approved_inputs = {
        normalize_distribution_name(entry["distribution"]): entry for entry in build_inputs
    }
    active_inputs: list[dict[str, Any]] = []
    requirement_mappings: list[dict[str, Any]] = []
    seen_requirements: set[str] = set()
    for raw_requirement in requires:
        normalized_raw = _require_nonempty_string(raw_requirement, context=f"{distribution} build-system.requires")
        parsed_requirement = PackagingRequirement(normalized_raw)
        if parsed_requirement.url:
            raise EnvironmentBundleError(
                f"derived wheel {distribution!r} build requirement must not use a direct URL"
            )
        if parsed_requirement.extras:
            raise EnvironmentBundleError(
                f"derived wheel {distribution!r} build requirement must not use extras for {parsed_requirement.name!r}"
            )
        marker_result = True
        if parsed_requirement.marker is not None:
            marker_result = parsed_requirement.marker.evaluate(environment=target_env)
        if not marker_result:
            requirement_mappings.append(
                {
                    "raw_requirement": normalized_raw,
                    "normalized_name": normalize_distribution_name(parsed_requirement.name),
                    "marker": str(parsed_requirement.marker) if parsed_requirement.marker is not None else None,
                    "marker_result": False,
                    "mapped_artifact": None,
                }
            )
            continue
        normalized_name = normalize_distribution_name(parsed_requirement.name)
        if normalized_name in seen_requirements:
            raise EnvironmentBundleError(f"derived wheel {distribution!r} declares duplicate build requirement {normalized_name!r}")
        seen_requirements.add(normalized_name)
        if normalized_name not in approved_inputs:
            raise EnvironmentBundleError(
                f"derived wheel {distribution!r} declares undeclared build requirement {normalized_name!r}"
            )
        approved_entry = approved_inputs[normalized_name]
        if parsed_requirement.specifier and approved_entry["version"] not in parsed_requirement.specifier:
            raise EnvironmentBundleError(
                f"derived wheel {distribution!r} build requirement {normalized_name!r} does not admit approved version {approved_entry['version']!r}"
            )
        active_inputs.append(approved_entry)
        requirement_mappings.append(
            {
                "raw_requirement": normalized_raw,
                "normalized_name": normalized_name,
                "marker": str(parsed_requirement.marker) if parsed_requirement.marker is not None else None,
                "marker_result": True,
                "mapped_artifact": dict(approved_entry),
            }
        )
    backend = _require_nonempty_string(
        build_system.get("build-backend", ""),
        context=f"{distribution} build-system.build-backend",
    )
    if backend != approved_contract["backend"]:
        raise EnvironmentBundleError(
            f"derived wheel {distribution!r} build backend mismatch: expected {approved_contract['backend']!r}, got {backend!r}"
        )
    backend_path = build_system.get("backend-path", [])
    if backend_path is None:
        backend_path = []
    if not isinstance(backend_path, list) or any(not isinstance(item, str) or not item for item in backend_path):
        raise EnvironmentBundleError(f"derived wheel {distribution!r} build-system.backend-path must be a list of strings")
    if backend_path != approved_contract["backend_path"]:
        raise EnvironmentBundleError(
            f"derived wheel {distribution!r} backend-path mismatch: expected {approved_contract['backend_path']!r}, got {backend_path!r}"
        )
    backend_distribution = approved_contract["backend_distribution"]
    if backend_distribution not in seen_requirements:
        raise EnvironmentBundleError(
            f"derived wheel {distribution!r} build-system.requires is missing backend provider {backend_distribution!r}"
        )
    build_receipt_backend = {
        "name": backend_distribution,
        "version": approved_inputs[backend_distribution]["version"],
        "module": backend,
        "backend_path": list(backend_path),
        "provider_distribution": backend_distribution,
    }
    return list(build_inputs), requirement_mappings, build_receipt_backend, target_env


def _measure_venv_inventory(venv_path: Path) -> dict[str, Any]:
    python_path = _venv_python_path(venv_path)
    code = """
import importlib.util
import json
from importlib.metadata import distributions

installed = sorted(
    {
        dist.metadata.get("Name", "").strip()
        for dist in distributions()
        if dist.metadata.get("Name", "").strip()
    }
)
print(json.dumps({
    "installed": installed,
    "pip_importable": importlib.util.find_spec("pip") is not None,
    "setuptools_importable": importlib.util.find_spec("setuptools") is not None,
    "wheel_importable": importlib.util.find_spec("wheel") is not None,
}, sort_keys=True))
"""
    try:
        result = subprocess.run(
            [str(python_path), "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except FileNotFoundError as exc:
        raise EnvironmentBundleError(f"virtualenv interpreter {python_path} is unavailable") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"virtualenv inventory probe failed: {detail}") from exc
    try:
        measured = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EnvironmentBundleError("virtualenv inventory probe produced unreadable JSON") from exc
    if not isinstance(measured, dict):
        raise EnvironmentBundleError("virtualenv inventory probe did not return a JSON object")
    return measured


def _assert_unseeded_virtualenv(venv_path: Path) -> None:
    measured = _measure_venv_inventory(venv_path)
    if measured.get("installed") != []:
        raise EnvironmentBundleError(
            f"newly created staging virtualenv must contain no distributions, got {measured.get('installed')!r}"
        )
    for field in ("pip_importable", "setuptools_importable", "wheel_importable"):
        if measured.get(field) is not False:
            raise EnvironmentBundleError(
                "newly created staging virtualenv must leave pip, setuptools, and wheel absent"
            )


def _assert_bootstrapped_pip_only(venv_path: Path, *, expected_pip_version: str) -> None:
    measured = _measure_venv_inventory(venv_path)
    if measured.get("installed") != ["pip"]:
        raise EnvironmentBundleError(
            f"post-bootstrap staging virtualenv must contain exactly pip, got {measured.get('installed')!r}"
        )
    if measured.get("setuptools_importable") or measured.get("wheel_importable"):
        raise EnvironmentBundleError("post-bootstrap staging virtualenv must still leave setuptools and wheel absent")
    try:
        installed_pip_version = subprocess.run(
            [str(_venv_python_path(venv_path)), "-I", "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"pip bootstrap verification failed: {detail}") from exc
    if expected_pip_version not in installed_pip_version:
        raise EnvironmentBundleError(
            f"post-bootstrap pip version mismatch: expected {expected_pip_version}, got {installed_pip_version.strip()!r}"
        )


def _inspect_build_environment(
    venv_path: Path,
    *,
    frontend_distribution: str,
    frontend_module: str,
    backend_distribution: str,
    backend_module: str,
) -> dict[str, Any]:
    code = """
import importlib
import importlib.metadata
import json

frontend_distribution, frontend_module, backend_distribution, backend_module = __import__("sys").argv[1:5]

def _record_path(distribution_name):
    dist = importlib.metadata.distribution(distribution_name)
    record = next(
        str(dist.locate_file(candidate))
        for candidate in dist.files or []
        if str(candidate).endswith("RECORD")
    )
    return {
        "distribution": distribution_name,
        "version": dist.version,
        "record_path": record,
    }

installed = sorted(
    {
        dist.metadata["Name"].strip().lower(): dist.version
        for dist in importlib.metadata.distributions()
        if dist.metadata.get("Name", "").strip()
    }.items()
)
frontend = importlib.import_module(frontend_module)
backend = importlib.import_module(backend_module)
print(json.dumps({
    "installed": [{"distribution": name, "version": version} for name, version in installed],
    "frontend": {
        **_record_path(frontend_distribution),
        "module": frontend_module,
        "module_origin": getattr(frontend, "__file__", ""),
    },
    "backend": {
        **_record_path(backend_distribution),
        "module": backend_module,
        "module_origin": getattr(backend, "__file__", ""),
    },
}, sort_keys=True))
"""
    try:
        result = subprocess.run(
            [
                str(_venv_python_path(venv_path)),
                "-I",
                "-c",
                code,
                frontend_distribution,
                frontend_module,
                backend_distribution,
                backend_module,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"build environment inspection failed: {detail}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EnvironmentBundleError("build environment inspection produced unreadable JSON") from exc


def _pip_bootstrap_child_source() -> str:
    return """
import hashlib
import json
import pathlib
import runpy
import stat
import sys

snapshot_path, expected_json = sys.argv[1], sys.argv[2]
snapshot = pathlib.Path(snapshot_path)
expected = json.loads(expected_json)
before = snapshot.stat()
snapshot_bytes = snapshot.read_bytes()
actual_hash = "sha256:" + hashlib.sha256(snapshot_bytes).hexdigest()
actual = {
    "st_dev": getattr(before, "st_dev", None),
    "st_ino": getattr(before, "st_ino", None),
    "st_mode": stat.S_IMODE(before.st_mode),
    "st_size": before.st_size,
    "sha256": actual_hash,
}
if actual != expected:
    raise SystemExit(
        f"pip snapshot identity mismatch: expected {expected}, got {actual}"
    )
sys.path.insert(0, str(snapshot))
import pip
from pip._internal.cli.main import main as pip_main
normalized_snapshot = snapshot.as_posix()
for origin in (getattr(pip, "__file__", ""), getattr(pip_main, "__code__", None) and pip_main.__code__.co_filename):
    normalized_origin = str(origin).replace("\\\\", "/")
    if not normalized_origin.startswith(normalized_snapshot):
        raise SystemExit(f"pip loaded from an unexpected origin: {origin}")
sys.argv = [
    "pip",
    "install",
    "--isolated",
    "--no-index",
    "--no-deps",
    "--no-cache-dir",
    "--ignore-installed",
    "--disable-pip-version-check",
    str(snapshot),
]
runpy.run_module("pip", run_name="__main__")
after = snapshot.stat()
for field in ("st_dev", "st_ino", "st_mode", "st_size"):
    if getattr(before, field, None) != getattr(after, field, None):
        raise SystemExit(f"pip snapshot {field} changed during bootstrap")
after_hash = "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()
if after_hash != expected["sha256"]:
    raise SystemExit(
        f"pip snapshot hash mismatch: expected {expected['sha256']}, got {after_hash}"
    )
print(json.dumps({
    "st_dev": getattr(after, "st_dev", None),
    "st_ino": getattr(after, "st_ino", None),
    "st_mode": stat.S_IMODE(after.st_mode),
    "st_size": after.st_size,
    "sha256": after_hash,
}, sort_keys=True))
"""


def _bootstrap_private_pip(
    *,
    venv_path: Path,
    pip_entry: dict[str, Any],
    bundle_root: Path,
) -> None:
    wheel_path, pip_bytes = _validated_artifact_bytes(pip_entry, bundle_root=bundle_root)
    pip_identity = _read_wheel_identity_from_bytes(
        pip_bytes,
        filename=pip_entry["filename"],
        context="pip bootstrap artifact",
    )
    if normalize_distribution_name(pip_identity["metadata_name"]) != "pip":
        raise EnvironmentBundleError("pip bootstrap artifact metadata Name does not identify pip")
    if pip_identity["metadata_version"] != pip_entry["version"]:
        raise EnvironmentBundleError("pip bootstrap artifact metadata Version does not match the manifest")
    original_identity = _artifact_stat_identity(wheel_path)
    private_root = _allocate_owned_directory(venv_path.parent, prefix=f".{venv_path.name}.pip-private-")
    snapshot_path = (private_root / Path(pip_entry["filename"]).name).resolve()
    _write_bytes_noclobber(snapshot_path, pip_bytes, mode=0o400)
    expected_identity = _artifact_stat_identity(snapshot_path)
    try:
        subprocess.run(
            [
                str(_venv_python_path(venv_path)),
                "-I",
                "-c",
                _pip_bootstrap_child_source(),
                str(snapshot_path),
                json.dumps(expected_identity, sort_keys=True),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        _rethrow_primary_with_cleanup(
            EnvironmentBundleError(f"private pip bootstrap failed: {detail}"),
            private_root,
        )
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown private pip bootstrap failure"),
            private_root,
        )
    try:
        _assert_artifact_identity(snapshot_path, expected_identity, context="private pip snapshot")
        _assert_artifact_identity(wheel_path, original_identity, context="retained original pip artifact")
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown private pip identity verification failure"),
            private_root,
        )
    _rollback_partial_path(private_root)


def _build_derived_runtime_wheel(
    *,
    requirement: ExportRequirement,
    source_sdist: dict[str, Any],
    tooling_by_name: dict[str, dict[str, Any]],
    target_report: dict[str, Any],
    staging_dir: Path,
) -> dict[str, Any]:
    _assert_target_host_compatibility(target_report, context="derived wheel build")
    target = target_report["target"]
    normalized = requirement.distribution
    if normalized not in _SOURCE_ONLY_RUNTIME_DISTRIBUTIONS:
        raise EnvironmentBundleError(f"runtime sdists are forbidden outside the approved derived-wheel path: {normalized}")
    evidence_root = staging_dir / "evidence" / normalized
    evidence_root.mkdir(parents=True, exist_ok=False)
    sdist_filename = _artifact_filename_from_url(source_sdist["url"])
    sdist_path = evidence_root / sdist_filename
    _download_and_verify_artifact(
        {
            "url": source_sdist["url"],
            "hash": source_sdist["hash"],
            "size": source_sdist["size"],
            "filename": sdist_filename,
            "source_path": source_sdist.get("source_path"),
        },
        destination=sdist_path,
    )
    if source_sdist["hash"] not in requirement.hashes:
        raise EnvironmentBundleError(
            f"derived wheel {normalized!r} source sdist hash {source_sdist['hash']} is not authorized by the export"
        )
    build_env = evidence_root / "build-env"
    build_out = evidence_root / "wheelhouse"
    build_out.mkdir()
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", str(build_env)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"failed to create offline build environment for {normalized}: {detail}") from exc
    pip_entry = _manifest_entry_from_tooling_lock_artifact(tooling_by_name["pip"])
    _bootstrap_private_pip(venv_path=build_env, pip_entry=pip_entry, bundle_root=staging_dir)
    _assert_bootstrapped_pip_only(build_env, expected_pip_version=pip_entry["version"])
    build_inputs = _tooling_install_plan(include_build=True, include_pip=False, include_uv=False)
    complete_build_environment = [dict(pip_entry), *[dict(entry) for entry in build_inputs]]
    requirements_path = evidence_root / "build-inputs.requirements.txt"
    _write_requirements_file(requirements_path, build_inputs)
    _reject_transformer_lens_contamination(build_inputs, context=f"{normalized} build inputs")
    try:
        subprocess.run(
            [
                str(_venv_python_path(build_env)),
                "-I",
                "-m",
                "pip",
                "install",
                "--isolated",
                "--no-index",
                "--no-cache-dir",
                "--require-hashes",
                "--find-links",
                str(staging_dir),
                "-r",
                str(requirements_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            env={
                **os.environ,
                "PIP_NO_INDEX": "1",
                "PIP_NO_CACHE_DIR": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            },
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"failed to install offline build tooling for {normalized}: {detail}") from exc

    unpack_root = evidence_root / "src"
    unpack_root.mkdir()
    project_root = _extract_sdist_to_directory(sdist_path, unpack_root)
    extraction_inventory, extraction_inventory_sha256 = _directory_inventory_and_hash(project_root)
    build_system = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8")).get("build-system")
    if not isinstance(build_system, dict):
        raise EnvironmentBundleError(f"derived wheel source {normalized!r} is missing [build-system]")
    recorded_build_inputs, requirement_mappings, backend_record, marker_environment = _validate_build_system_contract(
        normalized,
        build_system=build_system,
        build_inputs=complete_build_environment,
        target_report=target_report,
    )
    build_environment = _inspect_build_environment(
        build_env,
        frontend_distribution="build",
        frontend_module="build",
        backend_distribution=backend_record["provider_distribution"],
        backend_module=backend_record["module"],
    )
    evidence_path = evidence_root / "isolation-evidence.json"

    command = _derived_wheel_command(
        env_python=_venv_python_path(build_env),
        sdist_path=sdist_path,
        out_dir=build_out,
        evidence_path=evidence_path,
        backend_module=backend_record["module"],
        backend_provider=backend_record["provider_distribution"],
    )
    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
            env={
                **os.environ,
                "PIP_NO_INDEX": "1",
                "PIP_NO_CACHE_DIR": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "INTERPLAB_NETWORK_DENIED": "1",
                "INTERPLAB_PARENT_NETNS": os.readlink("/proc/self/ns/net") if sys.platform.startswith("linux") else "",
                "INTERPLAB_OUTER_ARGV": json.dumps(command),
            },
            **_derived_build_subprocess_kwargs(),
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"offline derived-wheel build failed for {normalized}: {detail}") from exc
    built_wheels = sorted(build_out.glob("*.whl"))
    if len(built_wheels) != 1:
        raise EnvironmentBundleError(
            f"offline derived-wheel build for {normalized!r} must produce exactly one wheel, got {len(built_wheels)}"
        )
    built_wheel = built_wheels[0]
    wheel_entry = {
        "distribution": requirement.distribution,
        "version": requirement.version,
        "filename": built_wheel.name,
        "relative_path": built_wheel.name,
        "size_bytes": built_wheel.stat().st_size,
        "origin": f"derived:{sdist_filename}",
        "sha256": hashing.hash_file(built_wheel),
        "type": "wheel",
    }
    _validate_wheel_metadata(built_wheel, wheel_entry)
    final_wheel_path = staging_dir / built_wheel.name
    if final_wheel_path.exists():
        raise EnvironmentBundleError(f"derived wheel destination already exists: {final_wheel_path}")
    shutil.copyfile(built_wheel, final_wheel_path)
    sdist_entry = {
        "distribution": requirement.distribution,
        "version": requirement.version,
        "filename": sdist_filename,
        "relative_path": str(Path("evidence") / normalized / sdist_filename).replace("\\", "/"),
        "size_bytes": sdist_path.stat().st_size,
        "origin": source_sdist["url"],
        "sha256": hashing.hash_file(sdist_path),
        "type": "sdist",
    }
    isolation_evidence = _load_json_payload(evidence_path, context="derived-wheel isolation evidence")
    provenance = {
        "distribution": requirement.distribution,
        "version": requirement.version,
        "wheel": dict(wheel_entry),
        "source_sdist": sdist_entry,
        "build_inputs": [dict(entry) for entry in recorded_build_inputs],
        "build_requirement_mappings": requirement_mappings,
        "marker_environment": dict(marker_environment),
        "build_environment": build_environment["installed"],
        "extraction_inventory": extraction_inventory,
        "extraction_inventory_sha256": extraction_inventory_sha256,
        "builder": {
            **dict(target),
            "python_full_version": target_report["python_full_version"],
            "implementation": target_report["implementation"],
            "soabi": target_report["soabi"],
            "compatible_tags": list(target_report["compatible_tags"]),
        },
        "frontend": {
            "name": "build",
            "version": tooling_by_name["build"]["version"],
            "provider_distribution": "build",
            "module": "build",
            "module_origin": build_environment["frontend"]["module_origin"],
            "record_path": build_environment["frontend"]["record_path"],
            "record_sha256": hashing.hash_file(Path(build_environment["frontend"]["record_path"])),
        },
        "backend": {
            **backend_record,
            "module_origin": build_environment["backend"]["module_origin"],
            "record_path": build_environment["backend"]["record_path"],
            "record_sha256": hashing.hash_file(Path(build_environment["backend"]["record_path"])),
        },
        "isolation": isolation_evidence,
        "command": command,
    }
    _atomic_write_json_noclobber(evidence_root / "build-receipt.json", provenance)
    shutil.rmtree(build_env, ignore_errors=False)
    shutil.rmtree(build_out, ignore_errors=False)
    _rollback_partial_path(unpack_root)
    return {
        "wheel": wheel_entry,
        "source_sdist": sdist_entry,
        "provenance": provenance,
    }


def capture_target_report(
    output_path: str | Path,
    *,
    source_root: str | Path,
    expected_revision: str,
) -> dict[str, Any]:
    source_root_path = Path(source_root).resolve()
    revision = _validate_clean_source_root(source_root_path, expected_revision)
    source_hashes = source_hashes_for_root(source_root_path)
    output = Path(output_path)
    if output.exists():
        raise EnvironmentBundleError(f"target capture output {output} already exists")
    current = _current_target_capture_fields()
    payload = {
        "report_type": _TARGET_CAPTURE_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        **_source_binding_fields(source_root_path, revision=revision, source_hashes=source_hashes),
        "target": current["target"],
        "python_full_version": current["python_full_version"],
        "implementation": current["implementation"],
        "soabi": current["soabi"],
        "compatible_tags": current["compatible_tags"],
        "builder": {
            "name": "interplab.core.environment_bundle",
            "python_version": sys.version.split()[0],
        },
    }
    validate_target_capture_report(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_text_noclobber(output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def validate_target_capture_report(payload: dict[str, Any]) -> None:
    _require_mapping(payload, context="target capture")
    _require_exact_keys(
        payload,
        required={
            "report_type",
            "schema_version",
            "created_at",
            "source_root",
            "repo_revision",
            "source_hashes",
            "target",
            "python_full_version",
            "implementation",
            "soabi",
            "compatible_tags",
            "builder",
        },
        context="target capture",
    )
    _require_string(payload, "report_type", expected=_TARGET_CAPTURE_TYPE, context="target capture")
    _require_int(payload, "schema_version", expected=1, context="target capture")
    _require_datetime_string(payload, "created_at", context="target capture")
    _require_string(payload, "source_root", context="target capture")
    _require_string(payload, "repo_revision", context="target capture")
    _validate_source_hashes(
        _require_mapping(payload, "source_hashes", context="target capture"),
        repo_root=Path(payload["source_root"]),
    )
    target = _require_mapping(payload, "target", context="target capture")
    _require_exact_keys(target, required={"os", "architecture", "python", "abi"}, context="target capture.target")
    for field in ("os", "architecture", "python", "abi"):
        _require_string(target, field, context="target capture.target")
    _require_string(payload, "python_full_version", context="target capture")
    _require_string(payload, "implementation", context="target capture")
    _require_string(payload, "soabi", context="target capture")
    compatible_tags = _require_list(payload, "compatible_tags", context="target capture")
    if not compatible_tags or not all(isinstance(tag, str) and tag for tag in compatible_tags):
        raise EnvironmentBundleError("target capture.compatible_tags must contain ordered non-empty strings")
    builder = _require_mapping(payload, "builder", context="target capture")
    _require_exact_keys(builder, required={"name", "python_version"}, context="target capture.builder")
    _require_string(builder, "name", context="target capture.builder")
    _require_string(builder, "python_version", context="target capture.builder")


def build_runtime_bundle(
    *,
    source_root: str | Path,
    expected_revision: str,
    target_report_path: str | Path,
    tooling_lock_path: str | Path,
    staging_dir: str | Path,
) -> dict[str, Any]:
    source_root_path = Path(source_root).resolve()
    revision = _validate_clean_source_root(source_root_path, expected_revision)
    source_hashes = source_hashes_for_root(source_root_path)
    target_report = _load_json_payload(target_report_path, context="target capture")
    _assert_target_capture_matches_current_source(
        target_report,
        source_root=source_root_path,
        revision=revision,
        source_hashes=source_hashes,
        context="target capture",
    )
    load_tooling_lock(tooling_lock_path)
    staging_parent = Path(staging_dir).resolve()
    staging_path = _allocate_owned_directory(staging_parent, prefix="runtime-staging-")

    requirements = parse_requirements_export(source_root_path / "slurm" / "requirements.cluster.txt")
    lock_packages = load_lock_packages(source_root_path / "uv.lock")
    runtime_requirements = selected_runtime_requirements(
        {"target": target_report["target"]},
        requirements,
    )
    if len({requirement.distribution for requirement in runtime_requirements}) != len(runtime_requirements):
        raise EnvironmentBundleError("runtime export contains duplicate normalized distribution names")
    transformer_lens_requirements = [
        requirement.version
        for requirement in runtime_requirements
        if requirement.distribution == "transformer-lens"
    ]
    if source_hashes == _real_repo_source_hashes() and transformer_lens_requirements != [_R5_X2_TRANSFORMER_LENS_BASELINE]:
        raise EnvironmentBundleError(
            "runtime export selection must contain exactly one transformer-lens==3.2.1 requirement"
        )
    source_only = [
        requirement
        for requirement in runtime_requirements
        if not (lock_packages[requirement.distribution].get("wheels") or [])
    ]
    _enforce_real_repo_runtime_expectations(
        source_hashes,
        runtime_requirements,
        source_only,
    )

    tooling_artifacts = tooling_lock_artifacts(tooling_lock_path, include_build=True)
    _reject_transformer_lens_contamination(tooling_artifacts, context="tooling lock artifacts")
    tooling_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in tooling_artifacts
    }
    runtime_entries: list[dict[str, Any]] = []
    derived_wheels: list[dict[str, Any]] = []

    try:
        for artifact in tooling_artifacts:
            file_path = staging_path / artifact["filename"]
            _download_and_verify_artifact(artifact, destination=file_path)

        for requirement in runtime_requirements:
            package = lock_packages.get(requirement.distribution)
            if package is None:
                raise EnvironmentBundleError(f"uv.lock is missing runtime package {requirement.distribution!r}")
            lock_version = package.get("version")
            if lock_version != requirement.version:
                raise EnvironmentBundleError(
                    f"runtime package {requirement.distribution!r} version mismatch: export requires {requirement.version}, lock has {lock_version}"
                )
            wheels = package.get("wheels") or []
            if wheels:
                selected = _select_locked_wheel_for_target(
                    requirement.distribution,
                    requirement.version,
                    wheels,
                    target_report["compatible_tags"],
                )
                runtime_entry = _manifest_entry_from_selected_artifact(
                    requirement.distribution,
                    requirement.version,
                    selected,
                )
                if runtime_entry["sha256"] not in requirement.hashes:
                    raise EnvironmentBundleError(
                        f"runtime hash mismatch for {requirement.distribution!r}: {runtime_entry['sha256']} not authorized by the export"
                    )
                overlap_name = normalize_distribution_name(requirement.distribution)
                if overlap_name in _TOOLING_LOCK_RUNTIME_OVERLAPS:
                    tooling_artifact = tooling_by_name[overlap_name]
                    for field, tooling_field in (("filename", "filename"), ("origin", "origin_url"), ("size_bytes", "size_bytes"), ("sha256", "sha256")):
                        if runtime_entry[field] != tooling_artifact[tooling_field]:
                            raise EnvironmentBundleError(
                                f"runtime/tooling overlap for {overlap_name!r} must use the identical accepted artifact identity"
                            )
                runtime_entries.append(runtime_entry)
                runtime_file = staging_path / runtime_entry["filename"]
                if not runtime_file.exists():
                    _download_and_verify_artifact(selected, destination=runtime_file)
                continue

            sdist_info = package.get("sdist")
            if not isinstance(sdist_info, dict):
                raise EnvironmentBundleError(f"source-only runtime package {requirement.distribution!r} has no locked sdist")
            derived = _build_derived_runtime_wheel(
                requirement=requirement,
                source_sdist=sdist_info,
                tooling_by_name=tooling_by_name,
                target_report=target_report,
                staging_dir=staging_path,
            )
            runtime_entries.append(derived["wheel"])
            derived_wheels.append(derived["provenance"])

        _reject_transformer_lens_contamination(
            runtime_entries,
            context="runtime staging runtime",
            require_exact_runtime=source_hashes == _real_repo_source_hashes(),
        )
        receipt = {
            "stage_type": _RUNTIME_STAGE_TYPE,
            "schema_version": 1,
            "created_at": _utcnow(),
            **_source_binding_fields(source_root_path, revision=revision, source_hashes=source_hashes),
            "target_report": json.loads(json.dumps(target_report)),
            "tooling_lock_path": str(Path(tooling_lock_path).resolve()),
            "tooling_lock_sha256": hashing.hash_file(tooling_lock_path),
            "staging_root": str(staging_path),
            "tooling": [
                _manifest_entry_from_tooling_lock_artifact(artifact)
                for artifact in tooling_artifacts
            ],
            "runtime": runtime_entries,
            "derived_wheels": derived_wheels,
        }
        validate_runtime_stage_receipt(receipt)
        _atomic_write_json_noclobber(staging_path / "runtime-stage.json", receipt)
        receipt["staging_dir"] = str(staging_path)
        return receipt
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown runtime bundle construction failure"),
            staging_path,
        )


def validate_runtime_stage_receipt(payload: dict[str, Any]) -> None:
    _require_mapping(payload, context="runtime stage")
    _require_exact_keys(
        payload,
        required={
            "stage_type",
            "schema_version",
            "created_at",
            "source_root",
            "repo_revision",
            "source_hashes",
            "target_report",
            "tooling_lock_path",
            "tooling_lock_sha256",
            "staging_root",
            "tooling",
            "runtime",
            "derived_wheels",
        },
        context="runtime stage",
    )
    _require_string(payload, "stage_type", expected=_RUNTIME_STAGE_TYPE, context="runtime stage")
    _require_int(payload, "schema_version", expected=1, context="runtime stage")
    _require_datetime_string(payload, "created_at", context="runtime stage")
    _require_string(payload, "source_root", context="runtime stage")
    _require_string(payload, "repo_revision", context="runtime stage")
    _validate_source_hashes(_require_mapping(payload, "source_hashes", context="runtime stage"), repo_root=Path(payload["source_root"]))
    validate_target_capture_report(_require_mapping(payload, "target_report", context="runtime stage"))
    _require_string(payload, "tooling_lock_path", context="runtime stage")
    _require_sha(payload, "tooling_lock_sha256", context="runtime stage")
    _require_string(payload, "staging_root", context="runtime stage")
    for index, entry in enumerate(_require_list(payload, "tooling", context="runtime stage")):
        _validate_manifest_entry_shape(entry, context=f"runtime stage.tooling[{index}]")
    for index, entry in enumerate(_require_list(payload, "runtime", context="runtime stage")):
        _validate_manifest_entry_shape(entry, context=f"runtime stage.runtime[{index}]")
    for index, entry in enumerate(_require_list(payload, "derived_wheels", context="runtime stage")):
        _validate_derived_entry_shape(entry, context=f"runtime stage.derived_wheels[{index}]")
    _reject_transformer_lens_contamination(
        _require_list(payload, "tooling", context="runtime stage"),
        context="runtime stage.tooling",
    )
    _reject_transformer_lens_contamination(
        _require_list(payload, "runtime", context="runtime stage"),
        context="runtime stage.runtime",
        require_exact_runtime=_require_mapping(payload, "source_hashes", context="runtime stage")
        == _real_repo_source_hashes(),
    )


def import_alliance_torch_artifact(
    *,
    artifact_path: str | Path,
    origin: str,
    transcript_path: str | Path,
    expected_identity_path: str | Path,
    target_report_path: str | Path,
    source_root: str | Path,
    expected_revision: str,
    output_path: str | Path,
) -> dict[str, Any]:
    source_root_path = Path(source_root).resolve()
    revision = _validate_clean_source_root(source_root_path, expected_revision)
    source_hashes = source_hashes_for_root(source_root_path)
    target_report = _load_json_payload(target_report_path, context="target capture")
    _assert_target_capture_matches_current_source(
        target_report,
        source_root=source_root_path,
        revision=revision,
        source_hashes=source_hashes,
        context="target capture",
    )
    artifact = Path(artifact_path).resolve()
    if not artifact.is_file():
        raise EnvironmentBundleError(f"Alliance torch artifact {artifact} is missing")
    receipt_path = Path(output_path)
    if receipt_path.exists():
        raise EnvironmentBundleError(f"torch receipt output {receipt_path} already exists")
    acquisition_root = artifact.parent.resolve()
    entries = sorted(path.name for path in acquisition_root.iterdir())
    if entries != sorted([artifact.name, Path(transcript_path).name]):
        raise EnvironmentBundleError(
            f"Alliance torch acquisition directory must contain exactly the artifact and transcript, got {entries!r}"
        )
    transcript = Path(transcript_path).read_text(encoding="utf-8")
    if "no-index" not in transcript or "no-deps" not in transcript or "only-binary" not in transcript:
        raise EnvironmentBundleError("Alliance torch transcript must record no-index/no-deps/only-binary acquisition controls")
    if not origin.startswith(_ALLIANCE_TORCH_ORIGIN_PREFIX):
        raise EnvironmentBundleError("Alliance torch origin must use the approved Alliance wheelhouse prefix")
    if artifact.name not in transcript:
        raise EnvironmentBundleError("Alliance torch transcript must name exactly the retained artifact")
    expected_identity = _load_json_payload(expected_identity_path, context="torch expected identity")
    identity = _read_wheel_metadata(artifact)
    if normalize_distribution_name(identity["metadata_name"]) != "torch":
        raise EnvironmentBundleError("Alliance torch artifact metadata Name does not identify torch")
    if identity["metadata_version"] != _ALLIANCE_TORCH_VERSION:
        raise EnvironmentBundleError("Alliance torch artifact metadata Version does not match the sanctioned Alliance build")
    if _public_version(identity["metadata_version"]) != _ALLIANCE_TORCH_PUBLIC_VERSION:
        raise EnvironmentBundleError("Alliance torch artifact must preserve the locked public torch version")
    measured_hash = hashing.hash_file(artifact)
    measured_size = artifact.stat().st_size
    expected_fields = {
        "filename": artifact.name,
        "size_bytes": measured_size,
        "sha256": measured_hash,
        "distribution": "torch",
        "version": identity["metadata_version"],
        "public_version": _ALLIANCE_TORCH_PUBLIC_VERSION,
        "origin": origin,
    }
    for field, measured_value in expected_fields.items():
        if expected_identity.get(field) != measured_value:
            raise EnvironmentBundleError(
                f"Alliance torch expected identity mismatch for {field}: expected {expected_identity.get(field)!r}, got {measured_value!r}"
            )
    payload = {
        "receipt_type": _TORCH_RECEIPT_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        **_source_binding_fields(source_root_path, revision=revision, source_hashes=source_hashes),
        "target_report": json.loads(json.dumps(target_report)),
        "artifact": {
            "distribution": "torch",
            "version": identity["metadata_version"],
            "filename": artifact.name,
            "relative_path": artifact.name,
            "size_bytes": measured_size,
            "origin": origin,
            "sha256": measured_hash,
            "type": "wheel",
            "import_name": "torch",
        },
        "public_version": _ALLIANCE_TORCH_PUBLIC_VERSION,
        "expected_identity_path": str(Path(expected_identity_path).resolve()),
        "transcript_path": str(Path(transcript_path).resolve()),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_noclobber(receipt_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def finalize_bundle(
    *,
    runtime_staging_dir: str | Path,
    target_report_path: str | Path,
    torch_receipt_path: str | Path,
    source_root: str | Path,
    expected_revision: str,
    output_root: str | Path,
) -> dict[str, Any]:
    source_root_path = Path(source_root).resolve()
    revision = _validate_clean_source_root(source_root_path, expected_revision)
    source_hashes = source_hashes_for_root(source_root_path)
    runtime_stage_path = Path(runtime_staging_dir).resolve()
    if not runtime_stage_path.is_dir():
        raise EnvironmentBundleError(f"runtime staging directory {runtime_stage_path} is missing")
    target_report = _load_json_payload(target_report_path, context="target capture")
    _assert_target_capture_matches_current_source(
        target_report,
        source_root=source_root_path,
        revision=revision,
        source_hashes=source_hashes,
        context="target capture",
    )
    runtime_stage = _load_json_payload(runtime_stage_path / "runtime-stage.json", context="runtime stage")
    validate_runtime_stage_receipt(runtime_stage)
    _assert_source_binding(
        runtime_stage,
        source_root=source_root_path,
        revision=revision,
        source_hashes=source_hashes,
        context="runtime stage",
    )
    if runtime_stage["target_report"] != target_report:
        raise EnvironmentBundleError("runtime stage and supplied target report do not describe the same captured target")
    torch_receipt = _load_json_payload(torch_receipt_path, context="torch receipt")
    if torch_receipt.get("receipt_type") != _TORCH_RECEIPT_TYPE:
        raise EnvironmentBundleError("torch receipt has the wrong type")
    _assert_source_binding(
        torch_receipt,
        source_root=source_root_path,
        revision=revision,
        source_hashes=source_hashes,
        context="torch receipt",
    )
    if torch_receipt.get("target_report") != target_report:
        raise EnvironmentBundleError("torch receipt and supplied target report do not describe the same captured target")
    torch_entry = _require_mapping(torch_receipt, "artifact", context="torch receipt")
    _validate_manifest_entry_shape(torch_entry, context="torch receipt.artifact")
    output_root_path = Path(output_root).resolve()
    output_root_path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "manifest_type": _RUNTIME_MANIFEST_TYPE,
        "schema_version": 1,
        "source_hashes": source_hashes,
        "target": runtime_stage["target_report"]["target"],
        "generator": {
            "uv": "0.8.22",
            "pip": "25.0",
            "virtualenv": "20.26.0",
            "hatchling": "1.27.0",
            "build": "1.2.2" if runtime_stage["derived_wheels"] else None,
        },
        "tooling": {
            "installers": [
                entry
                for entry in runtime_stage["tooling"]
                if normalize_distribution_name(entry["distribution"]) in set(_BASE_TOOLING) | {"build"}
                and (runtime_stage["derived_wheels"] or normalize_distribution_name(entry["distribution"]) != "build")
            ]
        },
        "torch": torch_entry,
        "runtime": runtime_stage["runtime"],
        "derived_wheels": runtime_stage["derived_wheels"],
    }
    validate_acquisition_manifest(manifest)
    _reject_transformer_lens_contamination(manifest["tooling"]["installers"], context="acquisition manifest.tooling")
    _reject_transformer_lens_contamination(
        manifest["runtime"],
        context="acquisition manifest.runtime",
        require_exact_runtime=source_hashes == _real_repo_source_hashes(),
    )
    expected_stage_files, expected_stage_directories = _runtime_stage_expected_paths(runtime_stage)
    _validate_exact_tree(
        runtime_stage_path,
        expected_files=expected_stage_files,
        expected_directories=expected_stage_directories,
        context="runtime staging",
    )
    stage_artifacts = [
        *runtime_stage["tooling"],
        *runtime_stage["runtime"],
        *[derived["source_sdist"] for derived in runtime_stage["derived_wheels"]],
    ]
    _build_artifact_index(stage_artifacts, context="runtime staging artifact inventory")
    for entry in stage_artifacts:
        _validated_artifact_bytes(entry, bundle_root=runtime_stage_path)
    for derived in runtime_stage["derived_wheels"]:
        source_relative = _require_string(
            _require_mapping(derived, "source_sdist", context="runtime stage derived wheel"),
            "relative_path",
            context="runtime stage derived wheel.source_sdist",
        )
        receipt_relative = str(PurePosixPath(source_relative).parent / "build-receipt.json")
        receipt_path = runtime_stage_path / PurePosixPath(receipt_relative)
        _reject_reparse_or_symlink_path(receipt_path, runtime_stage_path)
        if not receipt_path.is_file():
            raise EnvironmentBundleError(f"runtime staging is missing derived build receipt {receipt_relative!r}")
        receipt_payload = _load_json_payload(receipt_path, context=f"runtime stage derived receipt {receipt_relative}")
        if receipt_payload != derived:
            raise EnvironmentBundleError(
                f"runtime stage derived receipt {receipt_relative!r} does not match the staged derived-wheel provenance"
            )

    staging_publish = _allocate_owned_directory(output_root_path, prefix=".bundle-staging-")
    try:
        for relative_path in sorted(expected_stage_files - {"runtime-stage.json"}):
            _copy_relative_file(runtime_stage_path, staging_publish, relative_path)
        torch_root = Path(torch_receipt_path).resolve().parent
        torch_source, _ = _validated_artifact_bytes(torch_entry, bundle_root=torch_root)
        shutil.copyfile(torch_source, staging_publish / torch_entry["filename"])
        manifest_path = staging_publish / "environment-acquisition.json"
        _write_text_noclobber(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        receipt = {
            "created_at": _utcnow(),
            "repo_revision": revision,
            "source_root": str(source_root_path),
            "source_hashes": source_hashes,
            "target_report_path": str(Path(target_report_path).resolve()),
            "torch_receipt_path": str(Path(torch_receipt_path).resolve()),
            "runtime_stage_path": str(runtime_stage_path),
            "runtime_stage_tooling_lock_sha256": runtime_stage["tooling_lock_sha256"],
        }
        _write_text_noclobber(
            staging_publish / "construction-receipt.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        )
        expected_final_files, expected_final_directories = _expected_final_bundle_paths(manifest)
        _validate_exact_tree(
            staging_publish,
            expected_files=expected_final_files,
            expected_directories=expected_final_directories,
            context="bundle publication staging",
        )
        validate_bundle(
            manifest_path,
            bundle_root=staging_publish,
            venv_dir=staging_publish / ".validate-venv",
            source_root=source_root_path,
            expected_revision=expected_revision,
        )
        manifest_hash = hashing.hash_file(manifest_path).split(":", 1)[1]
        final_path = output_root_path / f"bundle-{manifest_hash}"
        _atomic_promote_directory_noclobber(staging_publish, final_path)
        return {
            "bundle_root": str(final_path),
            "manifest_path": str(final_path / "environment-acquisition.json"),
            "manifest_hash": f"sha256:{manifest_hash}",
        }
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown bundle finalization failure"),
            staging_publish,
        )


def validate_bundle(
    manifest_path: str | Path,
    *,
    bundle_root: str | Path | None = None,
    venv_dir: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
    install_manifest_path: str | Path | None = None,
    source_root: str | Path | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    if (source_root is None) != (expected_revision is None):
        raise EnvironmentBundleError("validate_bundle requires source_root and expected_revision together")
    if source_root is not None and expected_revision is not None:
        _validate_clean_source_root(Path(source_root).resolve(), expected_revision)
    manifest = load_acquisition_manifest(manifest_path)
    bundle_root_path = (
        Path(bundle_root).resolve()
        if bundle_root is not None
        else Path(manifest_path).resolve().parent
    )
    manifest_path_resolved = Path(manifest_path).resolve()
    if manifest_path_resolved.parent != bundle_root_path and bundle_root_path not in manifest_path_resolved.parents:
        raise EnvironmentBundleError(
            f"acquisition manifest {manifest_path_resolved} must reside inside bundle root {bundle_root_path}"
        )
    venv_path = Path(venv_dir).resolve() if venv_dir is not None else None

    validated = _validate_acquisition_manifest_semantics(
        manifest,
        repo_root=repo_root,
        bundle_root=bundle_root_path,
        enforce_current_target=True,
        require_files=True,
    )

    if venv_path is not None and venv_path.exists():
        raise EnvironmentBundleError(f"target virtualenv {venv_path} must be fresh")

    if install_manifest_path is not None:
        install_target = Path(install_manifest_path)
        install_parent = install_target.parent.resolve()
        if install_parent != bundle_root_path and bundle_root_path not in install_parent.parents:
            raise EnvironmentBundleError(
                f"install manifest path {install_target} escapes bundle root {bundle_root_path}"
            )
        if _path_exists_or_is_link(install_target):
            raise EnvironmentBundleError(f"install manifest destination {install_target} already exists")

    tooling_closure = _validated_tooling_lock_files(
        bundle_root_path,
        include_build=bool(manifest["derived_wheels"]),
    )
    tooling_install_plan = [
        entry
        for entry in tooling_closure
        if normalize_distribution_name(entry["distribution"]) not in {"pip", "uv"}
    ]

    return {
        "manifest_path": str(manifest_path_resolved),
        "bundle_root": str(bundle_root_path),
        "runtime": validated["runtime"],
        "tooling": validated["tooling"],
        "tooling_closure": tooling_install_plan,
        "torch": validated["torch"],
        "target": manifest["target"],
        "plan_files": {
            "runtime": "runtime.requirements.txt",
            "tooling": "tooling.requirements.txt",
            "torch": "torch.requirements.txt",
        },
    }


def write_selected_requirements(preflight: dict[str, Any], plan_dir: str | Path) -> dict[str, str]:
    plan_path = Path(plan_dir)
    plan_path.mkdir(parents=True, exist_ok=True)
    runtime_path = plan_path / "runtime.requirements.txt"
    tooling_path = plan_path / "tooling.requirements.txt"
    torch_path = plan_path / "torch.requirements.txt"
    tooling_names = {
        normalize_distribution_name(entry["distribution"]) for entry in preflight["tooling"]
    }
    runtime_plan = [
        entry
        for entry in preflight["runtime"]
        if normalize_distribution_name(entry["distribution"]) not in tooling_names
    ]
    _write_requirements_file(runtime_path, runtime_plan)
    tooling_plan = preflight.get("tooling_closure", preflight["tooling"])
    _write_requirements_file(tooling_path, tooling_plan)
    _write_requirements_file(torch_path, [preflight["torch"]])
    return {
        "runtime_requirements": str(runtime_path),
        "tooling_requirements": str(tooling_path),
        "torch_requirements": str(torch_path),
    }


def record_installed_environment(
    manifest_path: str | Path,
    install_manifest_path: str | Path,
    *,
    repo_root: Path = REPO_ROOT,
    source_root: str | Path | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    if (source_root is None) != (expected_revision is None):
        raise EnvironmentBundleError("record_installed_environment requires source_root and expected_revision together")
    if source_root is not None and expected_revision is not None:
        _validate_clean_source_root(Path(source_root).resolve(), expected_revision)
    manifest = load_acquisition_manifest(manifest_path)
    validated = _validate_acquisition_manifest_semantics(
        manifest,
        repo_root=repo_root,
        bundle_root=Path(manifest_path).resolve().parent,
        enforce_current_target=True,
        require_files=False,
    )
    _validate_acquisition_manifest_against_schema(manifest)
    runtime_entries = validated["runtime"]
    tooling_entries = validated["tooling"]
    torch_entry = validated["torch"]

    installed = _installed_distributions()
    required_installed = {
        normalize_distribution_name(entry["distribution"]): entry["version"]
        for entry in [*runtime_entries, *tooling_entries, torch_entry]
    }
    optional_installed = _approved_optional_tooling_versions(manifest)
    project_name, project_version = _local_project_identity(repo_root)
    required_installed[project_name] = project_version

    extras = sorted(set(installed) - set(required_installed) - set(optional_installed))
    missing = sorted(set(required_installed) - set(installed))
    if extras or missing:
        raise EnvironmentBundleError(
            "installed distribution set mismatch: "
            f"missing={missing or '[]'}, unexpected={extras or '[]'}"
        )
    for distribution_name, expected_version in required_installed.items():
        actual_version = installed[distribution_name]
        if actual_version != expected_version:
            raise EnvironmentBundleError(
                f"installed version mismatch for {distribution_name!r}: expected {expected_version}, got {actual_version}"
            )
    for distribution_name, expected_version in optional_installed.items():
        if distribution_name in installed and installed[distribution_name] != expected_version:
            raise EnvironmentBundleError(
                f"installed optional tooling version mismatch for {distribution_name!r}: expected {expected_version}, got {installed[distribution_name]}"
            )

    verified_imports: list[str] = []
    for import_name in _required_import_names(runtime_entries, [torch_entry]):
        import_module(import_name)
        verified_imports.append(import_name)

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except FileNotFoundError as exc:
        raise EnvironmentBundleError("could not execute target-venv python -m pip check") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stdout or "") + (exc.stderr or "")
        detail = detail.strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"python -m pip check failed: {detail}") from exc

    repo_revision = _clean_git_head(repo_root)
    loaded_modules = _measured_loaded_modules()
    installer_versions = {
        normalize_distribution_name(name): dist_version(name)
        for name in _expected_tooling_names(manifest)
    }
    for name in sorted(optional_installed):
        if name in installed:
            installer_versions[name] = dist_version(name)

    install_manifest = {
        "manifest_type": _INSTALL_MANIFEST_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        "acquisition_manifest_hash": hashing.hash_file(manifest_path),
        "repo_revision": repo_revision,
        "source_hashes": manifest["source_hashes"],
        "target": manifest["target"],
        "loaded_modules": loaded_modules,
        "installer_versions": installer_versions,
        "torch": _live_torch_runtime_identity(distribution_version=installed["torch"]),
        "verified_imports": sorted(verified_imports),
        "installed_distributions": [
            {"distribution": name, "version": version}
            for name, version in sorted(installed.items())
        ],
    }
    _validate_torch_runtime_identity(
        install_manifest["torch"],
        expected_entry=torch_entry,
        live_runtime=install_manifest["torch"],
        context="measured install torch",
    )
    validate_install_manifest(install_manifest)
    install_path = Path(install_manifest_path)
    install_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_text_noclobber(install_path, json.dumps(install_manifest, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        if _path_exists_or_is_link(install_path) or exc.errno in {
            errno.EEXIST,
            errno.EISDIR,
            errno.ELOOP,
            errno.EPERM,
        }:
            raise EnvironmentBundleError(f"install manifest destination {install_path} already exists") from exc
        raise
    return install_manifest


def load_acquisition_manifest(path: str | Path) -> dict[str, Any]:
    payload = _load_json_payload(path, context="acquisition manifest")
    validate_acquisition_manifest(payload)
    return payload


def _validate_acquisition_manifest_against_schema(payload: dict[str, Any]) -> None:
    """Defence-in-depth SHAPE check via the declarative JSON Schema (R9-A4 ruling).
    Additive only: the hand-written Python validators remain the sole normative
    contract, strictly stronger since they enforce cross-artifact semantics no
    JSON Schema can express. The import is lazy and must stay that way -- jsonschema
    is unavailable on the pre-activation bootstrap path (R9-C7). Call this only from
    post-activation code (record_installed_environment, certification_environment_inputs)."""
    from interplab.core._schema_registry import SCHEMAS_ROOT, SchemaValidationError
    from interplab.core._schema_registry import validate as _validate_against_schema

    schema_path = SCHEMAS_ROOT / "environment_acquisition_manifest" / "v1.schema.json"
    try:
        _validate_against_schema(payload, schema_path)
    except SchemaValidationError as exc:
        raise EnvironmentBundleError(f"acquisition manifest failed schema validation: {exc}") from exc


def load_install_manifest(path: str | Path) -> dict[str, Any]:
    payload = _load_json_payload(path, context="install manifest")
    validate_install_manifest(payload)
    return payload


def validate_acquisition_manifest(payload: dict[str, Any]) -> None:
    _require_mapping(payload, context="acquisition manifest")
    _require_exact_keys(
        payload,
        required={
            "manifest_type",
            "schema_version",
            "source_hashes",
            "target",
            "generator",
            "tooling",
            "torch",
            "runtime",
            "derived_wheels",
        },
        context="acquisition manifest",
    )
    _require_string(payload, "manifest_type", expected=_RUNTIME_MANIFEST_TYPE, context="acquisition manifest")
    _require_int(payload, "schema_version", expected=1, context="acquisition manifest")
    source_hashes = _require_mapping(payload, "source_hashes", context="acquisition manifest")
    target = _require_mapping(payload, "target", context="acquisition manifest")
    generator = _require_mapping(payload, "generator", context="acquisition manifest")
    tooling = _require_mapping(payload, "tooling", context="acquisition manifest")
    torch_entry = _require_mapping(payload, "torch", context="acquisition manifest")
    runtime = _require_list(payload, "runtime", context="acquisition manifest")
    derived = _require_list(payload, "derived_wheels", context="acquisition manifest")

    _require_exact_keys(
        source_hashes,
        required={"pyproject", "uv_lock", "cluster_requirements"},
        context="source_hashes",
    )
    for field in ("pyproject", "uv_lock", "cluster_requirements"):
        entry = _require_mapping(source_hashes, field, context="source_hashes")
        _require_exact_keys(entry, required={"path", "sha256"}, context=f"source_hashes.{field}")
        _require_string(entry, "path", context=f"source_hashes.{field}")
        _require_sha(entry, "sha256", context=f"source_hashes.{field}")

    _require_exact_keys(target, required={"os", "architecture", "python", "abi"}, context="target")
    for field in ("os", "architecture", "python", "abi"):
        _require_string(target, field, context="target")

    _require_exact_keys(
        generator,
        required={"uv"},
        optional={"pip", "virtualenv", "build", "hatchling"},
        context="generator",
    )
    _require_string(generator, "uv", context="generator")
    for field in ("pip", "virtualenv", "build", "hatchling"):
        _require_nullable_string(generator, field, context="generator")

    installers = _require_list(tooling, "installers", context="tooling")
    _require_exact_keys(tooling, required={"installers"}, context="tooling")
    if not installers:
        raise EnvironmentBundleError("tooling installers must not be empty")
    if not runtime:
        raise EnvironmentBundleError("acquisition manifest.runtime must not be empty")

    _validate_manifest_entry_shape(torch_entry, context="torch")
    for index, entry in enumerate(runtime):
        _validate_manifest_entry_shape(entry, context=f"runtime[{index}]")
    for index, entry in enumerate(installers):
        _validate_manifest_entry_shape(entry, context=f"tooling.installers[{index}]")
    for index, entry in enumerate(derived):
        _validate_derived_entry_shape(entry, context=f"derived_wheels[{index}]")


def validate_install_manifest(payload: dict[str, Any]) -> None:
    _require_mapping(payload, context="install manifest")
    _require_exact_keys(
        payload,
        required={
            "manifest_type",
            "schema_version",
            "created_at",
            "acquisition_manifest_hash",
            "repo_revision",
            "source_hashes",
            "target",
            "loaded_modules",
            "installer_versions",
            "torch",
            "verified_imports",
            "installed_distributions",
        },
        context="install manifest",
    )
    _require_string(payload, "manifest_type", expected=_INSTALL_MANIFEST_TYPE, context="install manifest")
    _require_int(payload, "schema_version", expected=1, context="install manifest")
    _require_datetime_string(payload, "created_at", context="install manifest")
    _require_sha(payload, "acquisition_manifest_hash", context="install manifest")
    _require_string(payload, "repo_revision", context="install manifest")
    source_hashes = _require_mapping(payload, "source_hashes", context="install manifest")
    _require_exact_keys(
        source_hashes,
        required={"pyproject", "uv_lock", "cluster_requirements"},
        context="install manifest.source_hashes",
    )
    for field in ("pyproject", "uv_lock", "cluster_requirements"):
        entry = _require_mapping(source_hashes, field, context="install manifest.source_hashes")
        _require_exact_keys(
            entry,
            required={"path", "sha256"},
            context=f"install manifest.source_hashes.{field}",
        )
        _require_string(entry, "path", context=f"install manifest.source_hashes.{field}")
        _require_sha(entry, "sha256", context=f"install manifest.source_hashes.{field}")
    target = _require_mapping(payload, "target", context="install manifest")
    _require_exact_keys(target, required={"os", "architecture", "python", "abi"}, context="install target")
    for field in ("os", "architecture", "python", "abi"):
        _require_string(target, field, context="install target")
    loaded_modules = _require_list(payload, "loaded_modules", context="install manifest")
    for index, name in enumerate(loaded_modules):
        if not isinstance(name, str) or not name:
            raise EnvironmentBundleError(
                f"install manifest.loaded_modules[{index}] must be a non-empty string"
            )
    installer_versions = _require_mapping(payload, "installer_versions", context="install manifest")
    for name, version in installer_versions.items():
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise EnvironmentBundleError(
                "installer_versions must map non-empty strings to non-empty strings"
            )
    torch_entry = _require_mapping(payload, "torch", context="install manifest")
    _require_exact_keys(
        torch_entry,
        required={"distribution", "version", "cuda", "cuda_available"},
        context="install torch",
    )
    _require_distribution(torch_entry, "distribution", context="install torch")
    _require_string(torch_entry, "version", context="install torch")
    if not isinstance(torch_entry["cuda"], str | type(None)):
        raise EnvironmentBundleError("install torch.cuda must be a string or null")
    if "cuda_available" not in torch_entry or not isinstance(torch_entry["cuda_available"], bool):
        raise EnvironmentBundleError("install torch.cuda_available must be a boolean")
    verified_imports = _require_list(payload, "verified_imports", context="install manifest")
    if not all(isinstance(name, str) and name for name in verified_imports):
        raise EnvironmentBundleError("verified_imports must contain only strings")
    installed = _require_list(payload, "installed_distributions", context="install manifest")
    for index, entry in enumerate(installed):
        _require_mapping(entry, context=f"installed_distributions[{index}]")
        _require_exact_keys(
            entry,
            required={"distribution", "version"},
            context=f"installed_distributions[{index}]",
        )
        _require_distribution(entry, "distribution", context=f"installed_distributions[{index}]")
        _require_string(entry, "version", context=f"installed_distributions[{index}]")


def _validate_acquisition_manifest_semantics(
    manifest: dict[str, Any],
    *,
    repo_root: Path,
    bundle_root: Path | None = None,
    enforce_current_target: bool = True,
    require_files: bool = False,
) -> dict[str, Any]:
    _validate_source_hashes(manifest["source_hashes"], repo_root=repo_root)
    if enforce_current_target:
        _validate_target(manifest["target"], current_target())
    requirements = parse_requirements_export(requirements_export())
    lock_packages = load_lock_packages(_LOCK_FILE)
    runtime_requirements = selected_runtime_requirements(manifest, requirements)
    runtime_entries = _validate_runtime_manifest(runtime_requirements, manifest["runtime"], manifest["derived_wheels"])
    tooling_entries = _validate_tooling_entries(manifest)
    overlap_names = _validate_runtime_tooling_overlap(runtime_entries, tooling_entries)
    torch_entry = _validate_torch(manifest["torch"], lock_packages)
    _validate_derived_origins(runtime_entries, manifest["derived_wheels"])
    source_sdists = [derived["source_sdist"] for derived in manifest["derived_wheels"]]
    all_entries = [*runtime_entries, *tooling_entries, torch_entry, *source_sdists]
    artifact_index = _build_artifact_index(all_entries, context="manifest artifact inventory")
    if bundle_root is not None:
        _validate_virtualenv_tool_artifact(manifest, tooling_entries, bundle_root=bundle_root)
        _validate_torch_artifact_file(torch_entry, bundle_root=bundle_root)
        _validate_derived_wheels(
            manifest["derived_wheels"],
            artifact_index,
            lock_packages,
            manifest["target"],
            bundle_root,
            target_capture=_current_target_capture_fields() if enforce_current_target else None,
        )
        if require_files:
            _validate_files(all_entries, bundle_root)
    return {
        "runtime": runtime_entries,
        "tooling": tooling_entries,
        "torch": torch_entry,
        "overlap_names": overlap_names,
    }


def _validate_install_manifest_consistency(
    install_manifest: dict[str, Any],
    *,
    acquisition_manifest: dict[str, Any],
    acquisition_manifest_path: str | Path,
    repo_root: Path,
) -> None:
    _validate_source_hashes(install_manifest["source_hashes"], repo_root=repo_root)
    expected_acquisition_hash = hashing.hash_file(acquisition_manifest_path)
    if install_manifest["acquisition_manifest_hash"] != expected_acquisition_hash:
        raise EnvironmentBundleError(
            "install manifest acquisition_manifest_hash does not match the referenced acquisition manifest"
        )
    if install_manifest["source_hashes"] != acquisition_manifest["source_hashes"]:
        raise EnvironmentBundleError(
            "install manifest source_hashes do not match the referenced acquisition manifest"
        )
    if install_manifest["target"] != acquisition_manifest["target"]:
        raise EnvironmentBundleError(
            "install manifest target does not match the referenced acquisition manifest"
        )
    _validate_target(acquisition_manifest["target"], current_target())
    validated = _validate_acquisition_manifest_semantics(
        acquisition_manifest,
        repo_root=repo_root,
        bundle_root=Path(acquisition_manifest_path).resolve().parent,
        enforce_current_target=True,
    )
    runtime_entries = validated["runtime"]
    tooling_entries = validated["tooling"]
    torch_entry = validated["torch"]

    required_installer_versions = {
        normalize_distribution_name(entry["distribution"]): entry["version"]
        for entry in tooling_entries
    }
    approved_optional_installers = {
        normalize_distribution_name(entry["distribution"]): entry["version"]
        for entry in _tooling_install_plan(
            include_build=bool(acquisition_manifest["derived_wheels"]),
            include_pip=False,
            include_uv=False,
        )
        if normalize_distribution_name(entry["distribution"]) not in required_installer_versions
    }
    actual_installer_versions = install_manifest["installer_versions"]
    missing_installers = sorted(set(required_installer_versions) - set(actual_installer_versions))
    unexpected_installers = sorted(
        set(actual_installer_versions) - set(required_installer_versions) - set(approved_optional_installers)
    )
    if missing_installers or unexpected_installers:
        raise EnvironmentBundleError(
            "install manifest installer_versions do not match the approved tooling set"
        )
    for name, expected_version in required_installer_versions.items():
        if actual_installer_versions[name] != expected_version:
            raise EnvironmentBundleError(
                f"install manifest installer_versions mismatch for {name!r}: expected {expected_version}, got {actual_installer_versions[name]}"
            )
    for name, expected_version in approved_optional_installers.items():
        if name in actual_installer_versions and actual_installer_versions[name] != expected_version:
            raise EnvironmentBundleError(
                f"install manifest optional installer_versions mismatch for {name!r}: expected {expected_version}, got {actual_installer_versions[name]}"
            )
    _validate_loaded_modules(
        install_manifest["loaded_modules"],
        context="install manifest loaded_modules",
    )

    required_installed = {
        normalize_distribution_name(entry["distribution"]): entry["version"]
        for entry in [*runtime_entries, *tooling_entries, torch_entry]
    }
    approved_optional_installed = dict(approved_optional_installers)
    project_name, project_version = _local_project_identity(repo_root)
    required_installed[project_name] = project_version
    expected_repo_revision = _clean_git_head(repo_root)
    if install_manifest["repo_revision"] != expected_repo_revision:
        raise EnvironmentBundleError(
            "install manifest repo_revision does not equal the exact current clean HEAD"
        )
    actual_installed = _normalize_distribution_versions(
        install_manifest["installed_distributions"],
        context="install manifest installed_distributions",
    )
    if set(actual_installed) - set(required_installed) - set(approved_optional_installed):
        extras = sorted(set(actual_installed) - set(required_installed) - set(approved_optional_installed))
        missing = sorted(set(required_installed) - set(actual_installed))
        raise EnvironmentBundleError(
            "install manifest installed_distributions mismatch: "
            f"missing={missing or '[]'}, unexpected={extras or '[]'}"
        )
    missing_required = sorted(set(required_installed) - set(actual_installed))
    if missing_required:
        raise EnvironmentBundleError(
            "install manifest installed_distributions mismatch: "
            f"missing={missing_required or '[]'}, unexpected=[]"
        )
    for distribution_name, expected_version in required_installed.items():
        actual_version = actual_installed[distribution_name]
        if actual_version != expected_version:
            raise EnvironmentBundleError(
                f"install manifest installed_distributions version mismatch for {distribution_name!r}: "
                f"expected {expected_version}, got {actual_version}"
            )
    for distribution_name, expected_version in approved_optional_installed.items():
        if distribution_name in actual_installed and actual_installed[distribution_name] != expected_version:
            raise EnvironmentBundleError(
                f"install manifest optional installed_distributions version mismatch for {distribution_name!r}: "
                f"expected {expected_version}, got {actual_installed[distribution_name]}"
            )

    torch_record = install_manifest["torch"]
    if normalize_distribution_name(torch_record["distribution"]) != normalize_distribution_name(
        torch_entry["distribution"]
    ):
        raise EnvironmentBundleError(
            "install manifest torch.distribution does not match the acquisition manifest"
        )
    if torch_record["version"] != torch_entry["version"]:
        raise EnvironmentBundleError(
            "install manifest torch.version does not match the acquisition manifest"
        )
    live_torch = _live_torch_runtime_identity()
    _validate_torch_runtime_identity(
        torch_record,
        expected_entry=torch_entry,
        live_runtime=live_torch,
        context="install manifest torch",
    )

    expected_imports = _required_import_names(runtime_entries, [torch_entry])
    actual_imports = install_manifest["verified_imports"]
    if len(actual_imports) != len(set(actual_imports)):
        raise EnvironmentBundleError("install manifest verified_imports contains duplicates")
    if sorted(actual_imports) != expected_imports:
        raise EnvironmentBundleError(
            "install manifest verified_imports do not match the approved runtime imports"
        )


def _validate_source_hashes(source_hashes: dict[str, Any], *, repo_root: Path) -> None:
    expected = {
        "pyproject": repo_root / "pyproject.toml",
        "uv_lock": repo_root / "uv.lock",
        "cluster_requirements": repo_root / "slurm" / "requirements.cluster.txt",
    }
    for field, expected_path in expected.items():
        entry = source_hashes[field]
        declared_path = entry["path"]
        if declared_path != expected_path.relative_to(repo_root).as_posix():
            raise EnvironmentBundleError(
                f"source_hashes.{field}.path mismatch: expected {expected_path.relative_to(repo_root).as_posix()}, got {declared_path}"
            )
        actual_hash = hashing.hash_file(expected_path)
        if entry["sha256"] != actual_hash:
            raise EnvironmentBundleError(
                f"source_hashes.{field}.sha256 mismatch: expected {actual_hash}, got {entry['sha256']}"
            )


def _requires_transformer_lens_equivalence_report(
    stage: str,
    config: dict[str, Any] | None,
    config_path: str | Path | None = None,
) -> bool:
    authoritative_path = (
        config_path is not None
        and Path(config_path).resolve() == _R5_X2_AUTHORITATIVE_CONFIG_PATH.resolve()
    )
    return (
        stage == "certify"
        and (
            authoritative_path
            or (
                isinstance(config, dict)
                and config.get("checkpoint_hash") == _R5_X2_CHECKPOINT_HASH
            )
        )
    )


def _validate_equivalence_report_path(
    path: str | Path,
    *,
    config: dict[str, Any] | None,
    config_path: str | Path | None,
) -> None:
    if not isinstance(config, dict):
        raise EnvironmentBundleError("TransformerLens equivalence validation requires the loaded certify config")
    payload = _load_json_payload(path, context="TransformerLens equivalence report")
    _validate_transformer_lens_equivalence_report(
        payload,
        config=config,
        config_path=config_path,
    )


def _validate_transformer_lens_equivalence_report(
    payload: dict[str, Any],
    *,
    config: dict[str, Any],
    config_path: str | Path | None,
) -> None:
    _require_mapping(payload, context="TransformerLens equivalence report")
    _require_string(
        payload,
        "report_type",
        expected=_EQUIVALENCE_REPORT_TYPE,
        context="TransformerLens equivalence report",
    )
    _require_int(
        payload,
        "schema_version",
        expected=1,
        context="TransformerLens equivalence report",
    )
    checkpoint_hash = _require_sha(
        payload,
        "checkpoint_hash",
        context="TransformerLens equivalence report",
    )
    config_hash = _require_sha(
        payload,
        "config_hash",
        context="TransformerLens equivalence report",
    )
    if config_hash != _R5_X2_AUTHORITATIVE_CONFIG_HASH:
        raise EnvironmentBundleError(
            "TransformerLens equivalence report config_hash does not match authoritative hm03l7yz config"
        )
    if config_path is not None and hashing.hash_file(config_path) != config_hash:
        raise EnvironmentBundleError(
            "TransformerLens equivalence report config_hash does not match the certify config bytes"
        )
    if checkpoint_hash != _R5_X2_CHECKPOINT_HASH:
        raise EnvironmentBundleError(
            "TransformerLens equivalence report checkpoint_hash does not match hm03l7yz"
        )
    if checkpoint_hash != config["checkpoint_hash"]:
        raise EnvironmentBundleError(
            "TransformerLens equivalence report checkpoint_hash does not match the certify config"
        )

    token_stream = _require_mapping(payload, "token_stream", context="TransformerLens equivalence report")
    _require_int(token_stream, "n_tokens", expected=config["n_tokens"], context="equivalence token_stream")
    _require_int(token_stream, "seq_len", expected=config["seq_len"], context="equivalence token_stream")
    _require_int(
        token_stream,
        "batch_size",
        expected=config["batch_size"],
        context="equivalence token_stream",
    )
    reported_eval_slice = _require_mapping(
        token_stream,
        "eval_slice",
        context="equivalence token_stream",
    )
    if reported_eval_slice != config["eval_slice"]:
        raise EnvironmentBundleError(
            "TransformerLens equivalence report token_stream.eval_slice does not match the certify config"
        )

    comparison = _require_mapping(payload, "comparison", context="TransformerLens equivalence report")
    _require_string(
        comparison,
        "baseline_transformer_lens",
        expected=_R5_X2_TRANSFORMER_LENS_BASELINE,
        context="equivalence comparison",
    )
    _require_string(
        comparison,
        "candidate_transformer_lens",
        expected=_R5_X2_TRANSFORMER_LENS_COMPARISON,
        context="equivalence comparison",
    )

    checks = _require_mapping(payload, "checks", context="TransformerLens equivalence report")
    _require_string(
        checks,
        "activation_hook",
        expected=_R5_X2_ACTIVATION_HOOK,
        context="equivalence checks",
    )
    _require_bool(
        checks,
        "tokenization_equal",
        expected=True,
        context="equivalence checks",
    )
    _require_bool(
        checks,
        "positions_equal",
        expected=True,
        context="equivalence checks",
    )
    _require_bool(
        checks,
        "activations_equal",
        expected=True,
        context="equivalence checks",
    )
    _require_bool(
        checks,
        "sae_forward_passed",
        expected=True,
        context="equivalence checks",
    )


def _validate_authoritative_r5_x2_config(
    *,
    config: dict[str, Any] | None,
    config_path: str | Path | None,
) -> None:
    if not isinstance(config, dict):
        raise EnvironmentBundleError("R5-X2 equivalence validation requires the loaded certify config")
    if config_path is None:
        raise EnvironmentBundleError("R5-X2 equivalence validation requires the certify config path")
    if Path(config_path).resolve() != _R5_X2_AUTHORITATIVE_CONFIG_PATH.resolve():
        raise EnvironmentBundleError(
            "certify config path is not authoritative configs/certify/hm03l7yz.yaml"
        )
    if hashing.hash_file(config_path) != _R5_X2_AUTHORITATIVE_CONFIG_HASH:
        raise EnvironmentBundleError(
            "certify config bytes do not match authoritative configs/certify/hm03l7yz.yaml"
        )
    for field in ("checkpoint_hash", "n_tokens", "seq_len", "batch_size", "bands_version"):
        if config.get(field) != _R5_X2_AUTHORITATIVE_CONFIG[field]:
            raise EnvironmentBundleError(
                f"certify config {field} does not match authoritative hm03l7yz"
            )
    if config.get("eval_slice") != _R5_X2_AUTHORITATIVE_CONFIG["eval_slice"]:
        raise EnvironmentBundleError(
            "certify config eval_slice does not match authoritative hm03l7yz"
        )


def _validate_target(declared: dict[str, str], actual: dict[str, str]) -> None:
    for field in ("os", "architecture", "python", "abi"):
        if declared[field] != actual[field]:
            raise EnvironmentBundleError(
                f"target mismatch for {field!r}: expected {actual[field]!r}, got {declared[field]!r}"
            )


def _validate_tooling_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    expected_names = _expected_tooling_names(manifest)
    entries = _validate_manifest_entries(
        manifest["tooling"]["installers"],
        expected_names=expected_names,
        context="tooling installers",
    )
    versions = {normalize_distribution_name(entry["distribution"]): entry["version"] for entry in entries}
    generator = manifest["generator"]
    required_generator_versions = {
        "pip": _require_generator_version(generator, "pip"),
        "hatchling": _require_generator_version(generator, "hatchling"),
        "virtualenv": _require_generator_version(generator, "virtualenv"),
    }
    if "build" in expected_names:
        required_generator_versions["build"] = _require_generator_version(generator, "build")
    for distribution_name, expected_version in required_generator_versions.items():
        if versions[distribution_name] != expected_version:
            raise EnvironmentBundleError(
                f"tooling version mismatch for {distribution_name!r}: expected {expected_version}, got {versions[distribution_name]}"
            )
    return entries


def _validate_runtime_tooling_overlap(
    runtime_entries: list[dict[str, Any]],
    tooling_entries: list[dict[str, Any]],
) -> tuple[str, ...]:
    runtime_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in runtime_entries
    }
    tooling_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in tooling_entries
    }
    overlap = sorted(set(runtime_by_name) & set(tooling_by_name))
    for name in overlap:
        runtime_entry = runtime_by_name[name]
        tooling_entry = tooling_by_name[name]
        for field in (
            "distribution",
            "version",
            "filename",
            "relative_path",
            "size_bytes",
            "origin",
            "sha256",
            "type",
            "import_name",
        ):
            if runtime_entry.get(field) != tooling_entry.get(field):
                raise EnvironmentBundleError(
                    f"runtime/tooling overlap for {name!r} must have one identical approved version and artifact identity"
                )
    return tuple(overlap)


def _validate_runtime_manifest(
    requirements: list[ExportRequirement],
    runtime_entries: list[dict[str, Any]],
    derived_wheels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not runtime_entries:
        raise EnvironmentBundleError("runtime artifacts must not be empty")
    expected_names = [requirement.distribution for requirement in requirements]
    normalized_expected = {normalize_distribution_name(name) for name in expected_names}
    seen: dict[str, str] = {}
    runtime: list[dict[str, Any]] = []
    for index, entry in enumerate(runtime_entries):
        _validate_manifest_entry_shape(entry, context=f"runtime artifacts[{index}]")
        normalized = normalize_distribution_name(entry["distribution"])
        previous = seen.get(normalized)
        if previous is not None:
            raise EnvironmentBundleError(
                f"runtime artifacts contains normalized duplicate distribution {normalized!r} via {previous!r} and {entry['distribution']!r}"
            )
        seen[normalized] = entry["distribution"]
        runtime.append(entry)
    seen_names = set(seen)
    unexpected = sorted(seen_names - normalized_expected)
    missing = sorted(normalized_expected - seen_names)
    if missing and not unexpected:
        raise EnvironmentBundleError(
            f"incomplete non-torch runtime closure: missing {', '.join(missing)}"
        )
    if missing or unexpected:
        raise EnvironmentBundleError(
            f"runtime artifacts mismatch: missing={missing or '[]'}, unexpected={unexpected or '[]'}"
        )
    runtime_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in runtime
    }
    derived_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in derived_wheels
    }
    for requirement in requirements:
        entry = runtime_by_name.get(requirement.distribution)
        if entry is None:
            raise EnvironmentBundleError(
                f"incomplete non-torch runtime closure: missing {requirement.distribution!r}"
            )
        if entry["version"] != requirement.version:
            raise EnvironmentBundleError(
                f"runtime version mismatch for {requirement.distribution!r}: expected {requirement.version}, got {entry['version']}"
            )
        derived = derived_by_name.get(requirement.distribution)
        if derived is not None:
            if entry["sha256"] != derived["wheel"]["sha256"]:
                raise EnvironmentBundleError(
                    f"derived runtime artifact hash mismatch for {requirement.distribution!r}: expected {derived['wheel']['sha256']}, got {entry['sha256']}"
                )
            for field in ("filename", "relative_path", "size_bytes"):
                if entry[field] != derived["wheel"][field]:
                    raise EnvironmentBundleError(
                        f"derived runtime artifact {field} mismatch for {requirement.distribution!r}"
                    )
            if derived["source_sdist"]["sha256"] not in requirement.hashes:
                raise EnvironmentBundleError(
                    f"derived wheel {requirement.distribution!r} source sdist hash is not authorized by the export"
                )
            continue
        if entry["sha256"] not in requirement.hashes:
            raise EnvironmentBundleError(
                f"runtime hash mismatch for {requirement.distribution!r}: {entry['sha256']} not authorized by the export"
            )
    return runtime


def _validate_manifest_entries(
    entries: list[dict[str, Any]],
    *,
    expected_names: list[str] | tuple[str, ...],
    context: str,
) -> list[dict[str, Any]]:
    if not entries:
        raise EnvironmentBundleError(f"{context} must not be empty")
    normalized_expected = {normalize_distribution_name(name) for name in expected_names}
    seen: dict[str, str] = {}
    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        _validate_manifest_entry_shape(entry, context=f"{context}[{index}]")
        normalized = normalize_distribution_name(entry["distribution"])
        previous = seen.get(normalized)
        if previous is not None:
            raise EnvironmentBundleError(
                f"{context} contains normalized duplicate distribution {normalized!r} via {previous!r} and {entry['distribution']!r}"
            )
        seen[normalized] = entry["distribution"]
        validated.append(entry)
    seen_names = set(seen)
    unexpected = sorted(seen_names - normalized_expected)
    missing = sorted(normalized_expected - seen_names)
    if missing or unexpected:
        raise EnvironmentBundleError(
            f"{context} mismatch: missing={missing or '[]'}, unexpected={unexpected or '[]'}"
        )
    return validated


def _validate_torch(torch_entry: dict[str, Any], lock_packages: dict[str, dict[str, Any]]) -> dict[str, Any]:
    _validate_manifest_entry_shape(torch_entry, context="torch")
    if normalize_distribution_name(torch_entry["distribution"]) != "torch":
        raise EnvironmentBundleError("torch artifact must declare distribution 'torch'")
    if torch_entry["type"] != "wheel":
        raise EnvironmentBundleError("torch artifact must be a wheel")
    if torch_entry["version"] != _ALLIANCE_TORCH_VERSION:
        raise EnvironmentBundleError(
            f"torch artifact must declare the sanctioned Alliance version {_ALLIANCE_TORCH_VERSION}"
        )
    lock_version = lock_packages["torch"]["version"]
    if _public_version(torch_entry["version"]) != _ALLIANCE_TORCH_PUBLIC_VERSION:
        raise EnvironmentBundleError(
            f"torch artifact must preserve locked public version {_ALLIANCE_TORCH_PUBLIC_VERSION}"
        )
    if _public_version(lock_version) != _ALLIANCE_TORCH_PUBLIC_VERSION:
        raise EnvironmentBundleError(
            f"torch lock version mismatch: expected public version {_ALLIANCE_TORCH_PUBLIC_VERSION}, got {lock_version}"
        )
    if _public_version(torch_entry["version"]) != _public_version(lock_version):
        raise EnvironmentBundleError(
            f"torch version mismatch: manifest declares {torch_entry['version']}, lock resolves {lock_version}"
        )
    if not torch_entry["origin"].startswith(_ALLIANCE_TORCH_ORIGIN_PREFIX):
        raise EnvironmentBundleError(
            f"torch artifact origin must declare the approved Alliance wheelhouse provenance prefix {_ALLIANCE_TORCH_ORIGIN_PREFIX!r}"
        )
    return torch_entry


def _validate_torch_artifact_file(torch_entry: dict[str, Any], *, bundle_root: Path) -> None:
    _path, artifact_bytes = _validated_artifact_bytes(torch_entry, bundle_root=bundle_root)
    identity = _read_wheel_identity_from_bytes(
        artifact_bytes,
        filename=torch_entry["filename"],
        context="torch artifact",
    )
    if normalize_distribution_name(identity["filename_distribution"]) != "torch":
        raise EnvironmentBundleError("torch artifact filename does not identify torch")
    if identity["filename_version"] != torch_entry["version"]:
        raise EnvironmentBundleError("torch artifact filename version does not match the manifest")
    if normalize_distribution_name(identity["metadata_name"]) != "torch":
        raise EnvironmentBundleError("torch artifact metadata Name does not identify torch")
    if identity["metadata_version"] != torch_entry["version"]:
        raise EnvironmentBundleError("torch artifact metadata Version does not match the manifest")


def _validate_derived_wheels(
    derived_wheels: list[dict[str, Any]],
    artifact_index: dict[str, dict[str, Any]],
    lock_packages: dict[str, dict[str, Any]],
    target: dict[str, str],
    bundle_root: Path,
    *,
    target_capture: dict[str, Any] | None = None,
) -> None:
    tooling_index = {
        normalize_distribution_name(entry["distribution"]): entry
        for entry in artifact_index.values()
        if normalize_distribution_name(entry["distribution"]) in _DERIVED_WHEEL_TOOLING
    }
    for derived in derived_wheels:
        normalized = normalize_distribution_name(derived["distribution"])
        if derived["wheel"]["type"] != "wheel":
            raise EnvironmentBundleError(f"derived wheel {normalized!r} must point to an artifact of type 'wheel'")
        if derived["source_sdist"]["type"] != "sdist":
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} must point to a lock-matching source sdist artifact"
            )
        wheel_entry = _resolve_index_entry(artifact_index, derived["wheel"], context=f"derived wheel {normalized!r} wheel")
        source_entry = _resolve_index_entry(
            artifact_index,
            derived["source_sdist"],
            context=f"derived wheel {normalized!r} source_sdist",
        )
        if normalize_distribution_name(wheel_entry["distribution"]) != normalized or wheel_entry["version"] != derived["version"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} does not match its runtime artifact distribution/version"
            )
        if normalize_distribution_name(source_entry["distribution"]) != normalized or source_entry["version"] != derived["version"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} source sdist does not match its distribution/version"
            )
        lock_package = lock_packages.get(normalized)
        if lock_package is None or not isinstance(lock_package.get("sdist"), dict):
            raise EnvironmentBundleError(f"derived wheel {normalized!r} has no lock-recorded sdist to match against")
        lock_sdist = lock_package["sdist"]
        parsed = urlparse(lock_sdist["url"])
        expected_filename = Path(parsed.path).name
        if source_entry["filename"] != expected_filename:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} source filename mismatch: expected {expected_filename}, got {source_entry['filename']}"
            )
        if source_entry["sha256"] != lock_sdist["hash"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} source hash mismatch: expected {lock_sdist['hash']}, got {source_entry['sha256']}"
            )
        builder = derived["builder"]
        for field, expected_value in target.items():
            if builder[field] != expected_value:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} builder {field} mismatch: expected {expected_value!r}, got {builder[field]!r}"
                )
        if target_capture is not None:
            for field in ("python_full_version", "implementation", "soabi", "compatible_tags"):
                if builder[field] != target_capture[field]:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} builder {field} mismatch: expected {target_capture[field]!r}, got {builder[field]!r}"
                    )
        expected_marker_environment = marker_environment_for_target(target)
        if derived["marker_environment"] != expected_marker_environment:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} marker_environment does not match the captured target"
            )
        expected_build_inputs = set(tooling_index)
        actual_build_inputs: dict[str, dict[str, Any]] = {}
        for build_input in derived["build_inputs"]:
            entry = _resolve_index_entry(artifact_index, build_input, context=f"derived wheel {normalized!r} build_inputs")
            input_name = normalize_distribution_name(entry["distribution"])
            if input_name in actual_build_inputs:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build_inputs contains normalized duplicate {input_name!r}"
                )
            actual_build_inputs[input_name] = entry
        if set(actual_build_inputs) != expected_build_inputs:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} build_inputs must equal the complete approved build-input closure"
            )
        for tool_name, tool_entry in actual_build_inputs.items():
            approved = tooling_index[tool_name]
            for field in ("filename", "relative_path", "sha256", "version"):
                if tool_entry[field] != approved[field]:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} build input {tool_name!r} mismatches approved tooling {field}"
                    )
        frontend_name = normalize_distribution_name(derived["frontend"]["name"])
        backend_name = normalize_distribution_name(derived["backend"]["name"])
        for name, record in ((frontend_name, derived["frontend"]), (backend_name, derived["backend"])):
            if name not in actual_build_inputs:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} references unapproved {name!r} in build provenance"
                )
            if record["version"] != actual_build_inputs[name]["version"]:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} {name!r} version mismatch in build provenance"
                )
        build_environment = _normalize_distribution_versions(
            derived["build_environment"],
            context=f"derived wheel {normalized!r} build_environment",
        )
        expected_environment = {
            normalize_distribution_name(entry["distribution"]): entry["version"]
            for entry in derived["build_inputs"]
        }
        if build_environment != expected_environment:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} build_environment must exactly match the approved build inputs"
            )
        if _json_sha256(derived["extraction_inventory"]) != derived["extraction_inventory_sha256"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} extraction inventory hash does not match the recorded extraction inventory"
            )
        seen_inventory_paths: set[str] = set()
        for item in derived["extraction_inventory"]:
            relative = PurePosixPath(item["path"])
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} extraction inventory contains an invalid path {item['path']!r}"
                )
            normalized_path = "/".join(part.casefold() for part in relative.parts)
            if normalized_path in seen_inventory_paths:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} extraction inventory contains a duplicate normalized path {item['path']!r}"
                )
            seen_inventory_paths.add(normalized_path)
        requirement_mappings = derived["build_requirement_mappings"]
        seen_requirement_names: set[str] = set()
        for index, mapping in enumerate(requirement_mappings):
            parsed_requirement = PackagingRequirement(mapping["raw_requirement"])
            normalized_name = normalize_distribution_name(parsed_requirement.name)
            if normalized_name != mapping["normalized_name"]:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build requirement mapping {index} normalized_name mismatch"
                )
            if parsed_requirement.url:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build requirement mapping {index} must not use a direct URL"
                )
            if parsed_requirement.extras:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build requirement mapping {index} must not use extras"
                )
            expected_marker = str(parsed_requirement.marker) if parsed_requirement.marker is not None else None
            if mapping["marker"] != expected_marker:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build requirement mapping {index} marker mismatch"
                )
            expected_marker_result = True
            if parsed_requirement.marker is not None:
                expected_marker_result = parsed_requirement.marker.evaluate(environment=expected_marker_environment)
            if mapping["marker_result"] != expected_marker_result:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} build requirement mapping {index} marker_result mismatch"
                )
            if mapping["marker_result"]:
                if normalized_name in seen_requirement_names:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} build requirement mappings contain duplicate active name {normalized_name!r}"
                    )
                seen_requirement_names.add(normalized_name)
                mapped = mapping["mapped_artifact"]
                if mapped is None:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} active build requirement {normalized_name!r} is missing its artifact mapping"
                    )
                resolved_mapping = _resolve_index_entry(
                    artifact_index,
                    mapped,
                    context=f"derived wheel {normalized!r} build requirement mapping {index}",
                )
                if normalize_distribution_name(resolved_mapping["distribution"]) != normalized_name:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} build requirement mapping {index} artifact identifies the wrong distribution"
                    )
                if parsed_requirement.specifier and resolved_mapping["version"] not in parsed_requirement.specifier:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} build requirement mapping {index} does not admit version {resolved_mapping['version']!r}"
                    )
                if normalized_name not in actual_build_inputs or actual_build_inputs[normalized_name] != resolved_mapping:
                    raise EnvironmentBundleError(
                        f"derived wheel {normalized!r} build requirement mapping {index} does not point to the approved build input"
                    )
            elif mapping["mapped_artifact"] is not None:
                raise EnvironmentBundleError(
                    f"derived wheel {normalized!r} inactive build requirement {normalized_name!r} must not record an artifact mapping"
                )
        isolation = derived["isolation"]
        if isolation["mechanism"] != "linux-unshare-clone_newnet":
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation mechanism must be linux-unshare-clone_newnet"
            )
        if isolation["parent_namespace"] == isolation["child_namespace"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation did not change the namespace identity"
            )
        if isolation["descendant_namespace"] != isolation["child_namespace"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} descendant namespace does not remain inside the isolated namespace"
            )
        if isolation["interfaces"] != ["lo"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation interfaces must contain only loopback"
            )
        non_header_routes = [line for line in isolation["routes"][1:] if line.strip()]
        if non_header_routes:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation routes must not expose non-loopback routes"
            )
        socket_fds = {
            fd_name: target_value
            for fd_name, target_value in isolation["fd_targets"].items()
            if isinstance(target_value, str) and target_value.startswith("socket:")
        }
        if socket_fds:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation retained socket descriptors: {socket_fds}"
            )
        python_attempt = isolation["python_connection_attempt"]
        if python_attempt.get("succeeded") is not False:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation python connection attempt must fail"
            )
        native_attempt = isolation["native_connection_attempt"]
        native_returncode = native_attempt.get("returncode")
        if native_returncode is None or native_returncode == 0:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation native descendant network attempt must fail"
            )
        if isolation["outer_argv"] != derived["command"]:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation outer argv does not match the recorded command"
            )
        if len(isolation["inner_argv"]) < 6:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation inner argv is incomplete"
            )
        if isolation["frontend"] != {
            "distribution": derived["frontend"]["provider_distribution"],
            "module": derived["frontend"]["module"],
            "module_origin": derived["frontend"]["module_origin"],
            "version": derived["frontend"]["version"],
            "record_path": derived["frontend"]["record_path"],
        }:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation frontend evidence does not match the recorded frontend provenance"
            )
        if isolation["backend"] != {
            "distribution": derived["backend"]["provider_distribution"],
            "module": derived["backend"]["module"],
            "module_origin": derived["backend"]["module_origin"],
            "version": derived["backend"]["version"],
            "record_path": derived["backend"]["record_path"],
        }:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} isolation backend evidence does not match the recorded backend provenance"
            )
        wheel_path = _resolve_artifact_path(wheel_entry, bundle_root)
        _validate_wheel_metadata(wheel_path, wheel_entry)


def _validate_derived_origins(runtime_entries: list[dict[str, Any]], derived_wheels: list[dict[str, Any]]) -> None:
    derived_names = {
        normalize_distribution_name(entry["distribution"]): entry
        for entry in derived_wheels
    }
    for runtime_entry in runtime_entries:
        origin = runtime_entry["origin"]
        normalized = normalize_distribution_name(runtime_entry["distribution"])
        if origin.startswith("derived:") and normalized not in derived_names:
            raise EnvironmentBundleError(
                f"runtime artifact {normalized!r} declares a derived origin without derived wheel provenance"
            )


def _validate_files(entries: list[dict[str, Any]], bundle_root: Path) -> None:
    for entry in entries:
        path = _resolve_artifact_path(entry, bundle_root)
        if not path.is_file():
            raise EnvironmentBundleError(f"bundle artifact missing: {entry['relative_path']}")
        actual_size = path.stat().st_size
        if actual_size != entry["size_bytes"]:
            raise EnvironmentBundleError(
                f"bundle artifact size mismatch for {entry['relative_path']}: expected {entry['size_bytes']}, got {actual_size}"
            )
        actual_hash = hashing.hash_file(path)
        if actual_hash != entry["sha256"]:
            raise EnvironmentBundleError(
                f"bundle artifact hash mismatch for {entry['relative_path']}: expected {entry['sha256']}, got {actual_hash}"
            )


def _validated_artifact_bytes(
    entry: dict[str, Any],
    *,
    bundle_root: Path,
) -> tuple[Path, bytes]:
    path = _resolve_artifact_path(entry, bundle_root)
    if not path.is_file():
        raise EnvironmentBundleError(f"bundle artifact missing: {entry['relative_path']}")
    artifact_bytes = path.read_bytes()
    actual_size = len(artifact_bytes)
    if actual_size != entry["size_bytes"]:
        raise EnvironmentBundleError(
            f"bundle artifact size mismatch for {entry['relative_path']}: expected {entry['size_bytes']}, got {actual_size}"
        )
    actual_hash = hashing.sha256_prefixed(artifact_bytes)
    if actual_hash != entry["sha256"]:
        raise EnvironmentBundleError(
            f"bundle artifact hash mismatch for {entry['relative_path']}: expected {entry['sha256']}, got {actual_hash}"
        )
    return path, artifact_bytes


def _validate_virtualenv_tool_artifact(
    manifest: dict[str, Any],
    tooling_entries: list[dict[str, Any]],
    *,
    bundle_root: Path,
) -> dict[str, Any]:
    expected_version = _require_generator_version(manifest["generator"], "virtualenv")
    tooling_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in tooling_entries
    }
    entry = tooling_by_name.get("virtualenv")
    if entry is None:
        raise EnvironmentBundleError("tooling installers must include the approved virtualenv creator artifact")
    if entry["type"] != "wheel":
        raise EnvironmentBundleError("virtualenv creator artifact must be a wheel")
    if normalize_distribution_name(entry["distribution"]) != "virtualenv":
        raise EnvironmentBundleError("virtualenv creator artifact must declare distribution 'virtualenv'")
    if entry["version"] != expected_version:
        raise EnvironmentBundleError(
            f"virtualenv creator artifact version mismatch: expected {expected_version}, got {entry['version']}"
        )
    _validate_files([entry], bundle_root)
    wheel_path = _resolve_artifact_path(entry, bundle_root)
    identity = _read_wheel_identity(wheel_path, context="virtualenv creator artifact")
    if normalize_distribution_name(identity["filename_distribution"]) != "virtualenv":
        raise EnvironmentBundleError(
            "virtualenv creator artifact filename does not identify virtualenv"
        )
    if identity["filename_version"] != entry["version"]:
        raise EnvironmentBundleError(
            "virtualenv creator artifact filename version does not match the manifest"
        )
    if normalize_distribution_name(identity["metadata_name"]) != "virtualenv":
        raise EnvironmentBundleError(
            "virtualenv creator artifact metadata Name does not identify virtualenv"
        )
    if identity["metadata_version"] != entry["version"]:
        raise EnvironmentBundleError(
            "virtualenv creator artifact metadata Version does not match the manifest"
        )
    return entry


def create_virtualenv(
    manifest_path: str | Path,
    *,
    bundle_root: str | Path | None = None,
    venv_dir: str | Path,
    python_executable: str | None = None,
    repo_root: Path = REPO_ROOT,
    source_root: str | Path | None = None,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    if (source_root is None) != (expected_revision is None):
        raise EnvironmentBundleError("create_virtualenv requires source_root and expected_revision together")
    if source_root is not None and expected_revision is not None:
        _validate_clean_source_root(Path(source_root).resolve(), expected_revision)
    manifest = load_acquisition_manifest(manifest_path)
    bundle_root_path = (
        Path(bundle_root).resolve()
        if bundle_root is not None
        else Path(manifest_path).resolve().parent
    )
    venv_path = Path(venv_dir).resolve()
    if _path_exists_or_is_link(venv_path):
        raise EnvironmentBundleError(f"target virtualenv {venv_path} must be fresh")
    validated = _validate_acquisition_manifest_semantics(
        manifest,
        repo_root=repo_root,
        bundle_root=bundle_root_path,
        enforce_current_target=True,
        require_files=False,
    )
    creator_entry = _validate_virtualenv_tool_artifact(
        manifest,
        validated["tooling"],
        bundle_root=bundle_root_path,
    )
    pip_entry = next(
        (
            entry
            for entry in validated["tooling"]
            if normalize_distribution_name(entry["distribution"]) == "pip"
        ),
        None,
    )
    if pip_entry is None:
        raise EnvironmentBundleError("tooling installers must include the approved pip bootstrap artifact")
    wheel_path, creator_bytes = _validated_artifact_bytes(
        creator_entry,
        bundle_root=bundle_root_path,
    )
    original_creator_identity = _artifact_stat_identity(wheel_path)
    executed_creator_hash = hashing.sha256_prefixed(creator_bytes)
    interpreter = python_executable or sys.executable
    staging_path = _fresh_staging_path(venv_path)
    snapshot_path = (
        staging_path.parent / f"{staging_path.name}.{Path(creator_entry['filename']).name}"
    ).resolve()
    snapshot_path.write_bytes(creator_bytes)
    code = _virtualenv_child_source()
    try:
        subprocess.run(
            [
                interpreter,
                "-I",
                "-c",
                code,
                str(snapshot_path),
                executed_creator_hash,
                str(staging_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except FileNotFoundError:
        _rethrow_primary_with_cleanup(
            EnvironmentBundleError(f"Python executable {interpreter!r} is unavailable"),
            staging_path,
            snapshot_path,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        _rethrow_primary_with_cleanup(
            EnvironmentBundleError(
                f"approved virtualenv creator failed before creating the target venv: {detail}"
            ),
            staging_path,
            snapshot_path,
        )
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown virtualenv creation failure"),
            staging_path,
            snapshot_path,
        )
    try:
        post_execution_hash = hashing.hash_file(snapshot_path)
        if post_execution_hash != executed_creator_hash:
            raise EnvironmentBundleError(
                f"creator snapshot hash mismatch: expected {executed_creator_hash}, got {post_execution_hash}"
            )
        _assert_artifact_identity(wheel_path, original_creator_identity, context="retained original creator artifact")
        _validate_created_virtualenv(staging_path, expected_target=manifest["target"])
        _assert_unseeded_virtualenv(staging_path)
        _bootstrap_private_pip(
            venv_path=staging_path,
            pip_entry=pip_entry,
            bundle_root=bundle_root_path,
        )
        _assert_bootstrapped_pip_only(
            staging_path,
            expected_pip_version=pip_entry["version"],
        )
        _atomic_promote_directory_noclobber(staging_path, venv_path)
    except Exception:
        _rethrow_primary_with_cleanup(
            sys.exc_info()[1] or EnvironmentBundleError("unknown virtualenv promotion failure"),
            staging_path,
            snapshot_path,
        )
    _rollback_partial_path(snapshot_path)
    return {
        "manifest_path": str(Path(manifest_path).resolve()),
        "bundle_root": str(bundle_root_path),
        "venv_dir": str(venv_path),
        "creator": executed_creator_hash,
    }


def _virtualenv_child_source() -> str:
    return """
import hashlib
import pathlib
import runpy
import sys
import tempfile

wheel_path, expected_hash, target = sys.argv[1], sys.argv[2], sys.argv[3]
snapshot = pathlib.Path(wheel_path)
snapshot_bytes = snapshot.read_bytes()
actual_hash = "sha256:" + hashlib.sha256(snapshot_bytes).hexdigest()
if actual_hash != expected_hash:
    raise SystemExit(
        f"creator snapshot hash mismatch: expected {expected_hash}, got {actual_hash}"
    )
with tempfile.TemporaryDirectory(
    prefix="creator-private-",
    dir=str(pathlib.Path(target).parent),
) as private_root:
    private_root_path = pathlib.Path(private_root)
    private_wheel = private_root_path / snapshot.name
    private_wheel.write_bytes(snapshot_bytes)
    sys.path.insert(0, str(private_wheel))
    app_data = private_root_path / "app-data"
    app_data.mkdir()
    sys.argv = [
        "virtualenv",
        "--no-download",
        "--no-periodic-update",
        "--no-seed",
        "--app-data",
        str(app_data),
        target,
    ]
    runpy.run_module("virtualenv", run_name="__main__")
"""


def _build_artifact_index(entries: list[dict[str, Any]], *, context: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry["sha256"]
        existing = index.get(key)
        if existing is not None and existing != entry:
            raise EnvironmentBundleError(f"{context} reuses hash {key} for conflicting artifact entries")
        index[key] = entry
    return index


def _resolve_index_entry(index: dict[str, dict[str, Any]], entry: dict[str, Any], *, context: str) -> dict[str, Any]:
    for field in ("distribution", "version", "filename", "relative_path", "size_bytes", "origin", "sha256", "type"):
        if field not in entry:
            raise EnvironmentBundleError(f"{context} is missing {field!r}")
    resolved = index.get(entry["sha256"])
    if resolved is None:
        raise EnvironmentBundleError(f"{context} does not reference an approved manifest artifact")
    for field in ("distribution", "version", "filename", "relative_path", "size_bytes", "origin", "type"):
        if resolved[field] != entry[field]:
            raise EnvironmentBundleError(f"{context} mismatches approved artifact field {field!r}")
    return resolved


def _resolve_artifact_path(entry: dict[str, Any], bundle_root: Path) -> Path:
    relative = Path(entry["relative_path"])
    if relative.is_absolute():
        raise EnvironmentBundleError(f"artifact path {entry['relative_path']!r} must be relative to the bundle root")
    if ".." in relative.parts:
        raise EnvironmentBundleError(f"artifact path {entry['relative_path']!r} contains parent traversal")
    candidate = bundle_root / relative
    _reject_reparse_or_symlink_path(candidate, bundle_root)
    resolved = candidate.resolve(strict=False)
    if resolved != bundle_root and bundle_root not in resolved.parents:
        raise EnvironmentBundleError(f"artifact path {entry['relative_path']!r} escapes bundle root {bundle_root}")
    return resolved


def _reject_reparse_or_symlink_path(candidate: Path, bundle_root: Path) -> None:
    current = bundle_root.resolve()
    for part in Path(candidate.relative_to(bundle_root)).parts:
        current = current / part
        if not current.exists():
            continue
        if current.is_symlink() or _is_reparse_point(current):
            raise EnvironmentBundleError(f"artifact path {candidate.relative_to(bundle_root)!s} traverses a symlink or junction")


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _validate_wheel_metadata(path: Path, entry: dict[str, Any]) -> None:
    identity = _read_wheel_identity(path, context=f"derived wheel {entry['filename']!r}")
    if normalize_distribution_name(identity["metadata_name"]) != normalize_distribution_name(
        entry["distribution"]
    ):
        raise EnvironmentBundleError(f"derived wheel {entry['filename']!r} metadata Name does not match the manifest")
    if identity["metadata_version"] != entry["version"]:
        raise EnvironmentBundleError(f"derived wheel {entry['filename']!r} metadata Version does not match the manifest")
    if (
        normalize_distribution_name(identity["filename_distribution"])
        != normalize_distribution_name(entry["distribution"])
        or identity["filename_version"] != entry["version"]
    ):
        raise EnvironmentBundleError(f"derived wheel {entry['filename']!r} filename does not match the manifest distribution/version")


def _parse_wheel_filename(filename: str) -> tuple[str, str]:
    if not filename.endswith(".whl"):
        raise EnvironmentBundleError(f"wheel filename {filename!r} does not end with .whl")
    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) < 5:
        raise EnvironmentBundleError(f"wheel filename {filename!r} is not PEP 427-shaped")
    return parts[0], parts[1]


def _read_wheel_identity_from_bytes(
    artifact_bytes: bytes,
    *,
    filename: str,
    context: str,
) -> dict[str, str]:
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_bytes)) as wheel:
            metadata_path = next(
                name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
            )
            metadata = BytesParser().parsebytes(wheel.read(metadata_path))
    except (StopIteration, KeyError, zipfile.BadZipFile) as exc:
        raise EnvironmentBundleError(f"{context} does not contain readable wheel METADATA") from exc
    metadata_name = metadata.get("Name")
    metadata_version = metadata.get("Version")
    if metadata_name is None or metadata_version is None:
        raise EnvironmentBundleError(f"{context} metadata is missing Name/Version")
    filename_distribution, filename_version = _parse_wheel_filename(filename)
    return {
        "metadata_name": metadata_name,
        "metadata_version": metadata_version,
        "filename_distribution": filename_distribution,
        "filename_version": filename_version,
    }


def _read_wheel_identity(path: Path, *, context: str) -> dict[str, str]:
    return _read_wheel_identity_from_bytes(
        path.read_bytes(),
        filename=path.name,
        context=context,
    )


def _validate_manifest_entry_shape(entry: dict[str, Any], *, context: str) -> None:
    _require_mapping(entry, context=context)
    _require_exact_keys(
        entry,
        required={
            "distribution",
            "version",
            "filename",
            "relative_path",
            "size_bytes",
            "origin",
            "sha256",
            "type",
        },
        optional={"import_name"},
        context=context,
    )
    _require_distribution(entry, "distribution", context=context)
    _require_string(entry, "version", context=context)
    _require_string(entry, "filename", context=context)
    _require_string(entry, "relative_path", context=context)
    _require_int(entry, "size_bytes", minimum=0, context=context)
    _require_string(entry, "origin", context=context)
    _require_sha(entry, "sha256", context=context)
    _require_enum(entry, "type", {"wheel", "sdist"}, context=context)
    if "import_name" in entry and not isinstance(entry["import_name"], str | type(None)):
        raise EnvironmentBundleError(f"{context}.import_name must be a string when present")


def _validate_derived_entry_shape(entry: dict[str, Any], *, context: str) -> None:
    _require_mapping(entry, context=context)
    _require_exact_keys(
        entry,
        required={
            "distribution",
            "version",
            "wheel",
            "source_sdist",
            "build_inputs",
            "build_requirement_mappings",
            "marker_environment",
            "build_environment",
            "extraction_inventory",
            "extraction_inventory_sha256",
            "builder",
            "frontend",
            "backend",
            "isolation",
            "command",
        },
        context=context,
    )
    _require_distribution(entry, "distribution", context=context)
    _require_string(entry, "version", context=context)
    _validate_manifest_entry_shape(_require_mapping(entry, "wheel", context=context), context=f"{context}.wheel")
    _validate_manifest_entry_shape(
        _require_mapping(entry, "source_sdist", context=context),
        context=f"{context}.source_sdist",
    )
    build_inputs = _require_list(entry, "build_inputs", context=context)
    if not build_inputs:
        raise EnvironmentBundleError(f"{context}.build_inputs must not be empty")
    for index, build_input in enumerate(build_inputs):
        _validate_manifest_entry_shape(build_input, context=f"{context}.build_inputs[{index}]")
    requirement_mappings = _require_list(entry, "build_requirement_mappings", context=context)
    if not requirement_mappings:
        raise EnvironmentBundleError(f"{context}.build_requirement_mappings must not be empty")
    for index, mapping in enumerate(requirement_mappings):
        item = _require_mapping(mapping, context=f"{context}.build_requirement_mappings[{index}]")
        _require_exact_keys(
            item,
            required={"raw_requirement", "normalized_name", "marker", "marker_result", "mapped_artifact"},
            context=f"{context}.build_requirement_mappings[{index}]",
        )
        _require_string(item, "raw_requirement", context=f"{context}.build_requirement_mappings[{index}]")
        _require_distribution(item, "normalized_name", context=f"{context}.build_requirement_mappings[{index}]")
        if item["marker"] is not None and not isinstance(item["marker"], str):
            raise EnvironmentBundleError(f"{context}.build_requirement_mappings[{index}].marker must be a string or null")
        if not isinstance(item["marker_result"], bool):
            raise EnvironmentBundleError(f"{context}.build_requirement_mappings[{index}].marker_result must be a boolean")
        mapped_artifact = item["mapped_artifact"]
        if mapped_artifact is not None:
            _validate_manifest_entry_shape(
                _require_mapping(item, "mapped_artifact", context=f"{context}.build_requirement_mappings[{index}]"),
                context=f"{context}.build_requirement_mappings[{index}].mapped_artifact",
            )
    marker_environment = _require_mapping(entry, "marker_environment", context=context)
    _require_exact_keys(
        marker_environment,
        required={
            "implementation_name",
            "platform_machine",
            "platform_python_implementation",
            "python_full_version",
            "python_version",
            "sys_platform",
        },
        context=f"{context}.marker_environment",
    )
    for field in (
        "implementation_name",
        "platform_machine",
        "platform_python_implementation",
        "python_full_version",
        "python_version",
        "sys_platform",
    ):
        _require_string(marker_environment, field, context=f"{context}.marker_environment")
    build_environment = _require_list(entry, "build_environment", context=context)
    if not build_environment:
        raise EnvironmentBundleError(f"{context}.build_environment must not be empty")
    for index, item in enumerate(build_environment):
        payload = _require_mapping(item, context=f"{context}.build_environment[{index}]")
        _require_exact_keys(
            payload,
            required={"distribution", "version"},
            context=f"{context}.build_environment[{index}]",
        )
        _require_distribution(payload, "distribution", context=f"{context}.build_environment[{index}]")
        _require_string(payload, "version", context=f"{context}.build_environment[{index}]")
    extraction_inventory = _require_list(entry, "extraction_inventory", context=context)
    if not extraction_inventory:
        raise EnvironmentBundleError(f"{context}.extraction_inventory must not be empty")
    for index, item in enumerate(extraction_inventory):
        payload = _require_mapping(item, context=f"{context}.extraction_inventory[{index}]")
        _require_exact_keys(
            payload,
            required={"path", "type"},
            optional={"size_bytes", "sha256"},
            context=f"{context}.extraction_inventory[{index}]",
        )
        _require_string(payload, "path", context=f"{context}.extraction_inventory[{index}]")
        _require_enum(payload, "type", {"file", "directory"}, context=f"{context}.extraction_inventory[{index}]")
        if payload["type"] == "file":
            _require_int(payload, "size_bytes", minimum=0, context=f"{context}.extraction_inventory[{index}]")
            _require_sha(payload, "sha256", context=f"{context}.extraction_inventory[{index}]")
    _require_sha(entry, "extraction_inventory_sha256", context=context)
    for field in ("builder", "frontend", "backend"):
        _require_mapping(entry, field, context=context)
    builder = entry["builder"]
    _require_exact_keys(
        builder,
        required={"os", "architecture", "python", "abi", "python_full_version", "implementation", "soabi", "compatible_tags"},
        context=f"{context}.builder",
    )
    for field in ("os", "architecture", "python", "abi", "python_full_version", "implementation", "soabi"):
        _require_string(builder, field, context=f"{context}.builder")
    compatible_tags = _require_list(builder, "compatible_tags", context=f"{context}.builder")
    if not compatible_tags or any(not isinstance(item, str) or not item for item in compatible_tags):
        raise EnvironmentBundleError(f"{context}.builder.compatible_tags must be a non-empty list of strings")
    for field in ("frontend", "backend"):
        tool = entry[field]
        required_keys = {"name", "version", "provider_distribution", "module", "module_origin", "record_path", "record_sha256"}
        _require_exact_keys(
            tool,
            required=(required_keys | {"backend_path"}) if field == "backend" else required_keys,
            context=f"{context}.{field}",
        )
        _require_distribution(tool, "name", context=f"{context}.{field}")
        _require_string(tool, "version", context=f"{context}.{field}")
        _require_distribution(tool, "provider_distribution", context=f"{context}.{field}")
        _require_string(tool, "module", context=f"{context}.{field}")
        _require_string(tool, "module_origin", context=f"{context}.{field}")
        _require_string(tool, "record_path", context=f"{context}.{field}")
        _require_sha(tool, "record_sha256", context=f"{context}.{field}")
    backend_path = entry["backend"]["backend_path"]
    if not isinstance(backend_path, list) or backend_path:
        raise EnvironmentBundleError(f"{context}.backend.backend_path must be an empty list")
    isolation = _require_mapping(entry, "isolation", context=context)
    _require_exact_keys(
        isolation,
        required={
            "mechanism",
            "parent_namespace",
            "child_namespace",
            "interfaces",
            "routes",
            "fd_targets",
            "descendant_namespace",
            "python_connection_attempt",
            "native_connection_attempt",
            "outer_argv",
            "inner_argv",
            "frontend",
            "backend",
        },
        context=f"{context}.isolation",
    )
    _require_string(isolation, "mechanism", context=f"{context}.isolation")
    _require_string(isolation, "parent_namespace", context=f"{context}.isolation")
    _require_string(isolation, "child_namespace", context=f"{context}.isolation")
    if isolation["parent_namespace"] == isolation["child_namespace"]:
        raise EnvironmentBundleError(f"{context}.isolation must change the network namespace identity")
    for list_field in ("interfaces", "routes", "outer_argv", "inner_argv"):
        values = _require_list(isolation, list_field, context=f"{context}.isolation")
        if any(not isinstance(item, str) or (list_field in {"interfaces", "outer_argv", "inner_argv"} and not item) for item in values):
            raise EnvironmentBundleError(f"{context}.isolation.{list_field} must contain strings")
    _require_mapping(isolation, "fd_targets", context=f"{context}.isolation")
    _require_string(isolation, "descendant_namespace", context=f"{context}.isolation")
    python_connection_attempt = _require_mapping(isolation, "python_connection_attempt", context=f"{context}.isolation")
    _require_exact_keys(
        python_connection_attempt,
        required={"succeeded", "error"},
        context=f"{context}.isolation.python_connection_attempt",
    )
    native_connection_attempt = _require_mapping(isolation, "native_connection_attempt", context=f"{context}.isolation")
    _require_exact_keys(
        native_connection_attempt,
        required={"argv", "returncode", "stdout", "stderr"},
        context=f"{context}.isolation.native_connection_attempt",
    )
    for nested in ("frontend", "backend"):
        nested_payload = _require_mapping(isolation, nested, context=f"{context}.isolation")
        _require_exact_keys(
            nested_payload,
            required={"distribution", "module", "module_origin", "version", "record_path"},
            context=f"{context}.isolation.{nested}",
        )
        for field in ("distribution", "module", "module_origin", "version", "record_path"):
            _require_string(nested_payload, field, context=f"{context}.isolation.{nested}")
    command = _require_list(entry, "command", context=context)
    if not command:
        raise EnvironmentBundleError(f"{context}.command must not be empty")
    for index, token in enumerate(command):
        if not isinstance(token, str) or not token:
            raise EnvironmentBundleError(f"{context}.command[{index}] must be a non-empty string")


def _require_mapping(
    payload: dict[str, Any] | Any,
    key: str | None = None,
    *,
    context: str,
) -> dict[str, Any]:
    value = payload if key is None else payload.get(key)
    if not isinstance(value, dict):
        suffix = "" if key is None else f".{key}"
        raise EnvironmentBundleError(f"{context}{suffix} must be an object")
    return value


def _require_list(payload: dict[str, Any], key: str, *, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise EnvironmentBundleError(f"{context}.{key} must be a list")
    return value


def _require_string(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
    expected: str | None = None,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EnvironmentBundleError(f"{context}.{key} must be a non-empty string")
    if expected is not None and value != expected:
        raise EnvironmentBundleError(f"{context}.{key} must equal {expected!r}, got {value!r}")
    return value


def _require_nullable_string(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
) -> str | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise EnvironmentBundleError(f"{context}.{key} must be a non-empty string or null")
    return value


def _require_datetime_string(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = _require_string(payload, key, context=context)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnvironmentBundleError(f"{context}.{key} must be a valid date-time string") from exc
    return value


def _require_int(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
    expected: int | None = None,
    minimum: int | None = None,
) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise EnvironmentBundleError(f"{context}.{key} must be an integer")
    if expected is not None and value != expected:
        raise EnvironmentBundleError(f"{context}.{key} must equal {expected}, got {value}")
    if minimum is not None and value < minimum:
        raise EnvironmentBundleError(f"{context}.{key} must be >= {minimum}")
    return value


def _require_bool(
    payload: dict[str, Any],
    key: str,
    *,
    context: str,
    expected: bool | None = None,
) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise EnvironmentBundleError(f"{context}.{key} must be a boolean")
    if expected is not None and value is not expected:
        raise EnvironmentBundleError(f"{context}.{key} must equal {expected}")
    return value


def _require_sha(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise EnvironmentBundleError(f"{context}.{key} must be a sha256:... digest")
    return value


def _require_distribution(payload: dict[str, Any], key: str, *, context: str) -> str:
    value = _require_string(payload, key, context=context)
    if not _DISTRIBUTION_PATTERN.fullmatch(value):
        raise EnvironmentBundleError(f"{context}.{key} must be a normalized distribution name")
    return value


def _require_enum(
    payload: dict[str, Any],
    key: str,
    allowed: set[str],
    *,
    context: str,
) -> str:
    value = _require_string(payload, key, context=context)
    if value not in allowed:
        raise EnvironmentBundleError(
            f"{context}.{key} must be one of {sorted(allowed)!r}, got {value!r}"
        )
    return value


def _require_exact_keys(
    payload: dict[str, Any],
    *,
    required: set[str],
    context: str,
    optional: set[str] | None = None,
) -> None:
    allowed = set(required)
    if optional:
        allowed |= optional
    keys = set(payload)
    missing = sorted(required - keys)
    if missing:
        raise EnvironmentBundleError(
            f"{context} is missing required field(s): {', '.join(missing)}"
        )
    unexpected = sorted(keys - allowed)
    if unexpected:
        raise EnvironmentBundleError(
            f"{context} has unexpected field(s): {', '.join(unexpected)}"
        )


def _load_json_payload(path: str | Path, *, context: str) -> dict[str, Any]:
    resolved = Path(path).resolve()
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise EnvironmentBundleError(f"{context} {resolved} is unreadable") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EnvironmentBundleError(f"{context} {resolved} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise EnvironmentBundleError(f"{context} {resolved} must be a JSON object")
    return payload


def _normalize_distribution_versions(
    entries: list[dict[str, Any]],
    *,
    context: str,
) -> dict[str, str]:
    seen: dict[str, str] = {}
    versions: dict[str, str] = {}
    for index, entry in enumerate(entries):
        _require_mapping(entry, context=f"{context}[{index}]")
        distribution = _require_string(entry, "distribution", context=f"{context}[{index}]")
        version = _require_string(entry, "version", context=f"{context}[{index}]")
        normalized = normalize_distribution_name(distribution)
        previous = seen.get(normalized)
        if previous is not None:
            raise EnvironmentBundleError(
                f"{context} contains normalized duplicate distribution {normalized!r} via "
                f"{previous!r} and {distribution!r}"
            )
        seen[normalized] = distribution
        versions[normalized] = version
    return versions


def _evaluate_marker_node(node: ast.AST, env: dict[str, str]) -> bool:
    if isinstance(node, ast.BoolOp):
        values = [_evaluate_marker_node(value, env) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
    if isinstance(node, ast.Compare):
        left = _marker_value(node.left, env)
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            right = _marker_value(comparator, env)
            if not _marker_compare(left, operator, right):
                return False
            left = right
        return True
    raise EnvironmentBundleError(f"unsupported requirement marker expression: {ast.dump(node)}")


def _marker_value(node: ast.AST, env: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise EnvironmentBundleError(f"unsupported requirement marker variable {node.id!r}")
        return env[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise EnvironmentBundleError(f"unsupported requirement marker operand: {ast.dump(node)}")


def _marker_compare(left: str, operator: ast.cmpop, right: str) -> bool:
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    if isinstance(operator, ast.Lt):
        return left < right
    if isinstance(operator, ast.LtE):
        return left <= right
    if isinstance(operator, ast.Gt):
        return left > right
    if isinstance(operator, ast.GtE):
        return left >= right
    if isinstance(operator, ast.In):
        return left in right
    if isinstance(operator, ast.NotIn):
        return left not in right
    raise EnvironmentBundleError(f"unsupported requirement marker comparator: {operator.__class__.__name__}")


def _public_version(version: str) -> str:
    return version.split("+", 1)[0]


def _required_import_names(runtime_entries: list[dict[str, Any]], extra_entries: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in [*runtime_entries, *extra_entries]:
        import_name = entry.get("import_name")
        if isinstance(import_name, str):
            names.append(import_name)
    return sorted(set(names))


def _expected_tooling_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    return _DERIVED_WHEEL_TOOLING if manifest["derived_wheels"] else _BASE_TOOLING


def _approved_optional_tooling_versions(manifest: dict[str, Any]) -> dict[str, str]:
    required = {
        normalize_distribution_name(name)
        for name in _expected_tooling_names(manifest)
    }
    versions: dict[str, str] = {}
    for entry in _tooling_install_plan(
        include_build=bool(manifest["derived_wheels"]),
        include_pip=False,
        include_uv=False,
    ):
        normalized = normalize_distribution_name(entry["distribution"])
        if normalized in required:
            continue
        versions[normalized] = entry["version"]
    return versions


def _require_generator_version(generator: dict[str, Any], field: str) -> str:
    value = _require_nullable_string(generator, field, context="generator")
    if value is None:
        raise EnvironmentBundleError(f"generator.{field} must declare the approved tooling version")
    return value


def _validate_loaded_modules(loaded_modules: list[str], *, context: str) -> None:
    if not loaded_modules:
        raise EnvironmentBundleError(f"{context} must not be empty")
    if len(loaded_modules) != len(set(loaded_modules)):
        raise EnvironmentBundleError(f"{context} contains duplicate module names")
    missing: list[str] = []
    incompatible: list[str] = []
    for family, required_prefix in _REQUIRED_LOADED_MODULES.items():
        candidates = [
            module
            for module in loaded_modules
            if module == family or module.startswith(f"{family}/")
        ]
        if not candidates:
            missing.append(family if required_prefix is None else f"{family}/{required_prefix}")
            continue
        if not any(
            _module_matches_requirement(
                module,
                family=family,
                version_prefix=required_prefix,
            )
            for module in candidates
        ):
            incompatible.append(candidates[0])
    if missing:
        raise EnvironmentBundleError(
            f"{context} is missing required module provenance: {', '.join(missing)}"
        )
    if incompatible:
        raise EnvironmentBundleError(
            f"{context} contains incompatible module provenance: {', '.join(incompatible)}"
        )


def _measured_loaded_modules() -> list[str]:
    raw = os.environ.get("LOADEDMODULES")
    if raw is None:
        raise EnvironmentBundleError(
            "LOADEDMODULES is missing; refusing to invent loaded module provenance"
        )
    modules = [part for part in raw.split(":") if part]
    _validate_loaded_modules(modules, context="LOADEDMODULES")
    return modules


def _module_matches_requirement(
    module: str,
    *,
    family: str,
    version_prefix: str | None,
) -> bool:
    if module == family:
        return version_prefix is None
    if not module.startswith(f"{family}/"):
        return False
    version = module.split("/", 1)[1]
    if not version:
        return False
    if version_prefix is None:
        return True
    return version == version_prefix or version.startswith(f"{version_prefix}.")


def _live_torch_runtime_identity(*, distribution_version: str | None = None) -> dict[str, Any]:
    torch_module = import_module("torch")
    version = distribution_version if distribution_version is not None else dist_version("torch")
    return {
        "distribution": "torch",
        "version": version,
        "cuda": getattr(getattr(torch_module, "version", None), "cuda", None),
        "cuda_available": bool(torch_module.cuda.is_available()),
    }


def _validate_torch_runtime_identity(
    torch_record: dict[str, Any],
    *,
    expected_entry: dict[str, Any],
    live_runtime: dict[str, Any],
    context: str,
) -> None:
    if normalize_distribution_name(torch_record["distribution"]) != normalize_distribution_name(
        expected_entry["distribution"]
    ):
        raise EnvironmentBundleError(f"{context}.distribution does not match the approved artifact")
    if torch_record["version"] != expected_entry["version"]:
        raise EnvironmentBundleError(f"{context}.version does not match the approved artifact")
    if expected_entry["version"] != _ALLIANCE_TORCH_VERSION:
        raise EnvironmentBundleError(
            f"{context} expected the sanctioned Alliance torch version {_ALLIANCE_TORCH_VERSION}"
        )
    if normalize_distribution_name(live_runtime["distribution"]) != "torch":
        raise EnvironmentBundleError("executing torch runtime does not report distribution 'torch'")
    if not isinstance(live_runtime["version"], str) or not live_runtime["version"]:
        raise EnvironmentBundleError("executing torch runtime did not report an installed distribution version")
    actual_cuda = torch_record["cuda"]
    if not isinstance(actual_cuda, str) or not actual_cuda:
        raise EnvironmentBundleError(f"{context}.cuda must record the measured CUDA build identity")
    live_cuda = live_runtime["cuda"]
    if not isinstance(live_cuda, str) or not live_cuda:
        raise EnvironmentBundleError("executing torch runtime did not report a CUDA build identity")
    if actual_cuda != _ALLIANCE_TORCH_CUDA_VERSION:
        raise EnvironmentBundleError(
            f"{context}.cuda does not match the sanctioned CUDA build identity {_ALLIANCE_TORCH_CUDA_VERSION}"
        )
    if live_cuda != _ALLIANCE_TORCH_CUDA_VERSION:
        raise EnvironmentBundleError(
            f"executing torch runtime did not report the sanctioned CUDA build identity {_ALLIANCE_TORCH_CUDA_VERSION}"
        )
    if torch_record["version"] != live_runtime["version"]:
        raise EnvironmentBundleError(
            f"{context}.version does not match the executing torch distribution"
        )
    if actual_cuda != live_cuda:
        raise EnvironmentBundleError(
            f"{context}.cuda does not match the executing torch runtime"
        )
    live_cuda_available = live_runtime["cuda_available"]
    if live_cuda_available is not True:
        raise EnvironmentBundleError(
            "executing torch runtime does not provide CUDA availability required by the production cluster profile"
        )
    if torch_record["cuda_available"] != live_cuda_available:
        raise EnvironmentBundleError(
            f"{context}.cuda_available does not match the executing torch runtime"
        )


def _venv_python_path(venv_path: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable_name = "python.exe" if os.name == "nt" else "python"
    return venv_path / scripts_dir / executable_name


def _fresh_staging_path(venv_path: Path) -> Path:
    return _allocate_owned_directory(venv_path.parent, prefix=f"{venv_path.name}.staging-")


def _validate_created_virtualenv(venv_path: Path, *, expected_target: dict[str, str]) -> None:
    pyvenv_cfg = venv_path / "pyvenv.cfg"
    if not pyvenv_cfg.is_file():
        raise EnvironmentBundleError(
            "approved virtualenv creator did not produce a functioning pyvenv.cfg"
        )
    cfg_text = pyvenv_cfg.read_text(encoding="utf-8", errors="replace")
    if "home" not in cfg_text:
        raise EnvironmentBundleError(
            "approved virtualenv creator produced pyvenv.cfg without base interpreter provenance"
        )
    python_path = _venv_python_path(venv_path)
    if not python_path.is_file():
        raise EnvironmentBundleError(
            "approved virtualenv creator did not produce the target virtualenv interpreter"
        )
    code = (
        "import json, platform, sys; "
        "print(json.dumps({"
        "'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix, "
        "'executable': sys.executable, "
        "'python': '.'.join(str(part) for part in sys.version_info[:3]), "
        "'abi': sys.implementation.cache_tag or 'unknown', "
        "'architecture': platform.machine().lower() or 'unknown', "
        "'os': 'windows' if sys.platform.startswith('win') else ('darwin' if sys.platform == 'darwin' else 'linux')"
        "}, sort_keys=True))"
    )
    try:
        result = subprocess.run(
            [str(python_path), "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except FileNotFoundError as exc:
        raise EnvironmentBundleError(
            "approved virtualenv creator produced an unusable target interpreter"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(
            f"approved virtualenv creator produced an interpreter that could not execute: {detail}"
        ) from exc
    try:
        measured = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EnvironmentBundleError(
            "approved virtualenv creator produced an interpreter with unreadable identity output"
        ) from exc
    if Path(measured["prefix"]).resolve() != venv_path.resolve():
        raise EnvironmentBundleError(
            "approved virtualenv creator produced an interpreter with the wrong sys.prefix"
        )
    if measured["prefix"] == measured["base_prefix"]:
        raise EnvironmentBundleError(
            "approved virtualenv creator did not separate sys.prefix from sys.base_prefix"
        )
    if Path(measured["executable"]).resolve() != python_path.resolve():
        raise EnvironmentBundleError(
            "approved virtualenv creator reported an unexpected interpreter path"
        )
    for field in ("python", "abi", "architecture", "os"):
        if measured[field] != expected_target[field]:
            raise EnvironmentBundleError(
                f"approved virtualenv creator produced the wrong {field}: expected {expected_target[field]!r}, got {measured[field]!r}"
            )


def _rollback_partial_path(path: Path) -> None:
    target = Path(path)
    if not target.exists():
        return
    last_error: OSError | None = None
    for _ in range(5):
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=False)
            else:
                target.unlink()
            return
        except OSError as exc:
            if target.exists():
                try:
                    if target.is_dir():
                        for child in target.rglob("*"):
                            with contextlib.suppress(OSError):
                                child.chmod(0o700 if child.is_dir() else 0o600)
                        target.chmod(0o700)
                    else:
                        target.chmod(0o600)
                except OSError:
                    pass
            last_error = exc
    if last_error is not None:
        raise last_error


def _installed_distributions() -> dict[str, str]:
    installed: dict[str, str] = {}
    originals: dict[str, str] = {}
    for distribution in distributions():
        name = distribution.metadata["Name"]
        if not name:
            raise EnvironmentBundleError("encountered an installed distribution without metadata Name")
        normalized = normalize_distribution_name(name)
        previous = originals.get(normalized)
        if previous is not None:
            raise EnvironmentBundleError(
                f"installed distributions contain normalized duplicate {normalized!r} via {previous!r} and {name!r}"
            )
        originals[normalized] = name
        installed[normalized] = distribution.version
    return installed


def _local_project_identity(repo_root: Path) -> tuple[str, str]:
    payload = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = payload.get("project")
    if not isinstance(project, dict):
        raise EnvironmentBundleError("pyproject.toml is missing [project]")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise EnvironmentBundleError("pyproject.toml must declare project name and version")
    return normalize_distribution_name(name), version


def _file_ref(path: str | Path, *, role: str, repo_root: Path) -> dict[str, str]:
    resolved = Path(path).resolve()
    return {
        "role": role,
        "location": infer_location_uri(resolved, repo_root=repo_root),
        "content_hash": hashing.hash_file(resolved),
    }


def infer_location_uri(path: str | Path, *, repo_root: Path = REPO_ROOT) -> str:
    resolved = Path(path).resolve()
    candidate_roots = []
    for candidate in (Path(repo_root).resolve(), REPO_ROOT.resolve()):
        if candidate not in candidate_roots:
            candidate_roots.append(candidate)
    for candidate_root in candidate_roots:
        if resolved == candidate_root or candidate_root in resolved.parents:
            return f"local:{resolved.relative_to(candidate_root).as_posix()}"
    scratch = os.environ.get("SCRATCH")
    if scratch:
        scratch_root = (Path(scratch) / "interplab").resolve()
        if resolved == scratch_root or scratch_root in resolved.parents:
            return f"tamia:{resolved.relative_to(scratch_root).as_posix()}"
    raise EnvironmentBundleError(f"cannot infer a local:/tamia: URI for {resolved}")


def _write_requirements_file(path: Path, entries: list[dict[str, Any]]) -> None:
    lines = []
    for entry in sorted(entries, key=lambda item: normalize_distribution_name(item["distribution"])):
        lines.append(f"{entry['distribution']}=={entry['version']} --hash={entry['sha256']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _clean_git_head(repo_root: Path) -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise EnvironmentBundleError("could not determine an exact clean repository revision") from exc
    if not head:
        raise EnvironmentBundleError("git rev-parse HEAD returned an empty revision")
    if status:
        raise EnvironmentBundleError("repository worktree is dirty; refusing to record a misleading clean HEAD revision")
    return head


def _running_on_cluster() -> bool:
    return bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("CC_CLUSTER"))


def _sys_platform_for_target(target_os: str) -> str:
    if target_os == "windows":
        return "win32"
    if target_os == "darwin":
        return "darwin"
    return "linux"


def _target_os(value: str) -> str:
    if value.startswith("win"):
        return "windows"
    if value == "darwin":
        return "darwin"
    return "linux"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an ED-36 offline environment bundle.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--manifest", required=True)
    preflight.add_argument("--bundle-root")
    preflight.add_argument("--venv-dir", required=True)
    preflight.add_argument("--plan-dir", required=True)
    preflight.add_argument("--install-manifest")
    preflight.add_argument("--source-root")
    preflight.add_argument("--expected-revision")

    create_venv = subparsers.add_parser("create-venv")
    create_venv.add_argument("--manifest", required=True)
    create_venv.add_argument("--bundle-root")
    create_venv.add_argument("--venv-dir", required=True)
    create_venv.add_argument("--python-executable")
    create_venv.add_argument("--source-root")
    create_venv.add_argument("--expected-revision")

    record = subparsers.add_parser("record-installed")
    record.add_argument("--manifest", required=True)
    record.add_argument("--install-manifest", required=True)
    record.add_argument("--source-root")
    record.add_argument("--expected-revision")

    capture_target = subparsers.add_parser("capture-target")
    capture_target.add_argument("--output", required=True)
    capture_target.add_argument("--source-root", required=True)
    capture_target.add_argument("--expected-revision", required=True)

    build_runtime = subparsers.add_parser("build-runtime")
    build_runtime.add_argument("--source-root", required=True)
    build_runtime.add_argument("--expected-revision", required=True)
    build_runtime.add_argument("--target-report", required=True)
    build_runtime.add_argument("--tooling-lock", required=True)
    build_runtime.add_argument("--staging-dir", required=True)

    import_torch = subparsers.add_parser("import-alliance-torch")
    import_torch.add_argument("--artifact", required=True)
    import_torch.add_argument("--origin", required=True)
    import_torch.add_argument("--transcript", required=True)
    import_torch.add_argument("--expected-identity", required=True)
    import_torch.add_argument("--target-report", required=True)
    import_torch.add_argument("--source-root", required=True)
    import_torch.add_argument("--expected-revision", required=True)
    import_torch.add_argument("--output", required=True)

    finalize = subparsers.add_parser("finalize-bundle")
    finalize.add_argument("--runtime-staging-dir", required=True)
    finalize.add_argument("--target-report", required=True)
    finalize.add_argument("--torch-receipt", required=True)
    finalize.add_argument("--source-root", required=True)
    finalize.add_argument("--expected-revision", required=True)
    finalize.add_argument("--output-root", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            preflight = validate_bundle(
                args.manifest,
                bundle_root=args.bundle_root,
                venv_dir=args.venv_dir,
                install_manifest_path=args.install_manifest,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
            )
            write_selected_requirements(preflight, args.plan_dir)
            print(json.dumps(preflight, indent=2, sort_keys=True))
            return 0
        if args.command == "create-venv":
            created = create_virtualenv(
                args.manifest,
                bundle_root=args.bundle_root,
                venv_dir=args.venv_dir,
                python_executable=args.python_executable,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
            )
            print(json.dumps(created, indent=2, sort_keys=True))
            return 0
        if args.command == "record-installed":
            manifest = record_installed_environment(
                args.manifest,
                args.install_manifest,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
            )
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0
        if args.command == "capture-target":
            payload = capture_target_report(
                args.output,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "build-runtime":
            payload = build_runtime_bundle(
                source_root=args.source_root,
                expected_revision=args.expected_revision,
                target_report_path=args.target_report,
                tooling_lock_path=args.tooling_lock,
                staging_dir=args.staging_dir,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "import-alliance-torch":
            payload = import_alliance_torch_artifact(
                artifact_path=args.artifact,
                origin=args.origin,
                transcript_path=args.transcript,
                expected_identity_path=args.expected_identity,
                target_report_path=args.target_report,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
                output_path=args.output,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "finalize-bundle":
            payload = finalize_bundle(
                runtime_staging_dir=args.runtime_staging_dir,
                target_report_path=args.target_report,
                torch_receipt_path=args.torch_receipt,
                source_root=args.source_root,
                expected_revision=args.expected_revision,
                output_root=args.output_root,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
    except EnvironmentBundleError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    raise AssertionError(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
