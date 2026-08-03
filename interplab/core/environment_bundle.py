from __future__ import annotations

import argparse
import ast
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
from pathlib import Path
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
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DISTRIBUTION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


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
) -> list[str]:
    return [
        str(env_python),
        "-I",
        "-m",
        "build",
        "--wheel",
        "--no-isolation",
        "--outdir",
        str(out_dir),
        str(sdist_path),
    ]


def _extract_sdist_to_directory(sdist_path: Path, destination: Path) -> Path:
    with tarfile.open(sdist_path, "r:gz") as archive:
        archive.extractall(destination)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise EnvironmentBundleError(
            f"source distribution {sdist_path.name!r} must unpack to exactly one top-level directory"
        )
    return roots[0]


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


def _pip_bootstrap_child_source() -> str:
    return """
import hashlib
import json
import os
import pathlib
import runpy
import stat
import sys

snapshot_path, expected_hash = sys.argv[1], sys.argv[2]
snapshot = pathlib.Path(snapshot_path)
before = snapshot.stat()
snapshot_bytes = snapshot.read_bytes()
actual_hash = "sha256:" + hashlib.sha256(snapshot_bytes).hexdigest()
if actual_hash != expected_hash:
    raise SystemExit(
        f"pip snapshot hash mismatch: expected {expected_hash}, got {actual_hash}"
    )
sys.path.insert(0, str(snapshot))
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
if after_hash != expected_hash:
    raise SystemExit(
        f"pip snapshot hash mismatch: expected {expected_hash}, got {after_hash}"
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
    _wheel_path, pip_bytes = _validated_artifact_bytes(pip_entry, bundle_root=bundle_root)
    pip_identity = _read_wheel_identity_from_bytes(
        pip_bytes,
        filename=pip_entry["filename"],
        context="pip bootstrap artifact",
    )
    if normalize_distribution_name(pip_identity["metadata_name"]) != "pip":
        raise EnvironmentBundleError("pip bootstrap artifact metadata Name does not identify pip")
    if pip_identity["metadata_version"] != pip_entry["version"]:
        raise EnvironmentBundleError("pip bootstrap artifact metadata Version does not match the manifest")
    snapshot_path = (
        venv_path.parent / f"{venv_path.name}.{Path(pip_entry['filename']).name}"
    ).resolve()
    snapshot_path.write_bytes(pip_bytes)
    expected_hash = hashing.sha256_prefixed(pip_bytes)
    try:
        subprocess.run(
            [
                str(_venv_python_path(venv_path)),
                "-I",
                "-c",
                _pip_bootstrap_child_source(),
                str(snapshot_path),
                expected_hash,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(f"private pip bootstrap failed: {detail}") from exc
    finally:
        _rollback_partial_path(snapshot_path)


def _build_derived_runtime_wheel(
    *,
    requirement: ExportRequirement,
    source_sdist: dict[str, Any],
    tooling_by_name: dict[str, dict[str, Any]],
    target_report: dict[str, Any],
    staging_dir: Path,
) -> dict[str, Any]:
    target = target_report["target"]
    current = current_target()
    for field in ("os", "architecture", "python", "abi"):
        if target[field] != current[field]:
            raise EnvironmentBundleError(
                f"derived wheels may only be built on a target-matching host; {field} expected {target[field]!r}, got {current[field]!r}"
            )
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
    build_inputs = _tooling_install_plan(include_build=True, include_pip=False, include_uv=False)
    requirements_path = evidence_root / "build-inputs.requirements.txt"
    _write_requirements_file(requirements_path, build_inputs)
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
    build_system = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8")).get("build-system")
    if not isinstance(build_system, dict):
        raise EnvironmentBundleError(f"derived wheel source {normalized!r} is missing [build-system]")
    requires = build_system.get("requires")
    if not isinstance(requires, list) or not requires:
        raise EnvironmentBundleError(f"derived wheel source {normalized!r} must declare build-system.requires")
    approved_inputs = {
        normalize_distribution_name(entry["distribution"]): entry for entry in build_inputs
    }
    for raw_requirement in requires:
        requirement_obj = PackagingRequirement(_require_nonempty_string(raw_requirement, context=f"{normalized} build-system.requires"))
        required_name = normalize_distribution_name(requirement_obj.name)
        if required_name not in approved_inputs:
            raise EnvironmentBundleError(
                f"derived wheel {normalized!r} declares undeclared build requirement {required_name!r}"
            )

    command = _derived_wheel_command(
        env_python=_venv_python_path(build_env),
        sdist_path=sdist_path,
        out_dir=build_out,
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
            },
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
    provenance = {
        "distribution": requirement.distribution,
        "version": requirement.version,
        "wheel": dict(wheel_entry),
        "source_sdist": sdist_entry,
        "build_inputs": [dict(entry) for entry in build_inputs],
        "builder": dict(target),
        "frontend": {"name": "build", "version": tooling_by_name["build"]["version"]},
        "backend": {
            "name": normalize_distribution_name(str(build_system.get("build-backend", "hatchling")).split(".", 1)[0]),
            "version": tooling_by_name["hatchling"]["version"],
        },
        "command": command,
    }
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
    output = Path(output_path)
    if output.exists():
        raise EnvironmentBundleError(f"target capture output {output} already exists")
    soabi = (
        sysconfig.get_config_var("SOABI")
        or sysconfig.get_config_var("SO")
        or sys.implementation.cache_tag
    )
    if not isinstance(soabi, str) or not soabi:
        raise EnvironmentBundleError("could not determine the exact SOABI for target capture")
    compatible_tags = [str(tag) for tag in packaging_tags.sys_tags()]
    payload = {
        "report_type": _TARGET_CAPTURE_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        "source_root": str(source_root_path),
        "repo_revision": revision,
        "source_hashes": source_hashes_for_root(source_root_path),
        "target": current_target(),
        "python_full_version": ".".join(str(part) for part in sys.version_info[:3]),
        "implementation": sys.implementation.name,
        "soabi": soabi,
        "compatible_tags": compatible_tags,
        "builder": {
            "name": "interplab.core.environment_bundle",
            "python_version": sys.version.split()[0],
        },
    }
    validate_target_capture_report(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    target_report = _load_json_payload(target_report_path, context="target capture")
    validate_target_capture_report(target_report)
    load_tooling_lock(tooling_lock_path)
    staging_path = Path(staging_dir).resolve()
    if not staging_path.exists():
        raise EnvironmentBundleError(f"runtime staging directory {staging_path} must exist and be empty")
    if any(staging_path.iterdir()):
        raise EnvironmentBundleError(f"runtime staging directory {staging_path} must be empty")

    requirements = parse_requirements_export(source_root_path / "slurm" / "requirements.cluster.txt")
    lock_packages = load_lock_packages(source_root_path / "uv.lock")
    runtime_requirements = selected_runtime_requirements(
        {"target": target_report["target"]},
        requirements,
    )
    source_only = [
        requirement
        for requirement in runtime_requirements
        if not (lock_packages[requirement.distribution].get("wheels") or [])
    ]
    _enforce_real_repo_runtime_expectations(
        source_hashes_for_root(source_root_path),
        runtime_requirements,
        source_only,
    )

    tooling_artifacts = tooling_lock_artifacts(tooling_lock_path, include_build=True)
    tooling_by_name = {
        normalize_distribution_name(entry["distribution"]): entry for entry in tooling_artifacts
    }
    runtime_entries: list[dict[str, Any]] = []
    derived_wheels: list[dict[str, Any]] = []
    copied_files: list[str] = []

    for artifact in tooling_artifacts:
        file_path = staging_path / artifact["filename"]
        _download_and_verify_artifact(artifact, destination=file_path)
        copied_files.append(file_path.name)

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
                copied_files.append(runtime_file.name)
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
        copied_files.extend(path for path in (derived["wheel"]["filename"], derived["source_sdist"]["relative_path"]) if path not in copied_files)

    extra_installable = {
        path.name
        for path in staging_path.iterdir()
        if path.is_file() and path.suffix in {".whl", ".gz"}
    }
    expected_installable = {
        entry["filename"] for entry in runtime_entries
    } | {
        artifact["filename"] for artifact in tooling_artifacts
    } | {
        provenance["source_sdist"]["relative_path"] for provenance in derived_wheels
    }
    unexpected = sorted(extra_installable - expected_installable)
    if unexpected:
        raise EnvironmentBundleError(f"runtime staging contains unexpected installable artifacts: {unexpected}")

    receipt = {
        "stage_type": _RUNTIME_STAGE_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        "source_root": str(source_root_path),
        "repo_revision": revision,
        "source_hashes": source_hashes_for_root(source_root_path),
        "target_report": json.loads(json.dumps(target_report)),
        "tooling_lock_path": str(Path(tooling_lock_path).resolve()),
        "tooling": [
            _manifest_entry_from_tooling_lock_artifact(artifact)
            for artifact in tooling_artifacts
        ],
        "runtime": runtime_entries,
        "derived_wheels": derived_wheels,
    }
    validate_runtime_stage_receipt(receipt)
    (staging_path / "runtime-stage.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


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
    for index, entry in enumerate(_require_list(payload, "tooling", context="runtime stage")):
        _validate_manifest_entry_shape(entry, context=f"runtime stage.tooling[{index}]")
    for index, entry in enumerate(_require_list(payload, "runtime", context="runtime stage")):
        _validate_manifest_entry_shape(entry, context=f"runtime stage.runtime[{index}]")
    for index, entry in enumerate(_require_list(payload, "derived_wheels", context="runtime stage")):
        _validate_derived_entry_shape(entry, context=f"runtime stage.derived_wheels[{index}]")


def import_alliance_torch_artifact(
    *,
    artifact_path: str | Path,
    origin: str,
    transcript_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    artifact = Path(artifact_path).resolve()
    if not artifact.is_file():
        raise EnvironmentBundleError(f"Alliance torch artifact {artifact} is missing")
    receipt_path = Path(output_path)
    if receipt_path.exists():
        raise EnvironmentBundleError(f"torch receipt output {receipt_path} already exists")
    transcript = Path(transcript_path).read_text(encoding="utf-8")
    if "no-index" not in transcript or "no-deps" not in transcript or "only-binary" not in transcript:
        raise EnvironmentBundleError("Alliance torch transcript must record no-index/no-deps/only-binary acquisition controls")
    if not origin.startswith(_ALLIANCE_TORCH_ORIGIN_PREFIX):
        raise EnvironmentBundleError("Alliance torch origin must use the approved Alliance wheelhouse prefix")
    identity = _read_wheel_metadata(artifact)
    if normalize_distribution_name(identity["metadata_name"]) != "torch":
        raise EnvironmentBundleError("Alliance torch artifact metadata Name does not identify torch")
    if identity["metadata_version"] != _ALLIANCE_TORCH_VERSION:
        raise EnvironmentBundleError("Alliance torch artifact metadata Version does not match the sanctioned Alliance build")
    if _public_version(identity["metadata_version"]) != _ALLIANCE_TORCH_PUBLIC_VERSION:
        raise EnvironmentBundleError("Alliance torch artifact must preserve the locked public torch version")
    payload = {
        "receipt_type": _TORCH_RECEIPT_TYPE,
        "schema_version": 1,
        "created_at": _utcnow(),
        "artifact": {
            "distribution": "torch",
            "version": identity["metadata_version"],
            "filename": artifact.name,
            "relative_path": artifact.name,
            "size_bytes": artifact.stat().st_size,
            "origin": origin,
            "sha256": hashing.hash_file(artifact),
            "type": "wheel",
            "import_name": "torch",
        },
        "public_version": _ALLIANCE_TORCH_PUBLIC_VERSION,
        "transcript_path": str(Path(transcript_path).resolve()),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    runtime_stage_path = Path(runtime_staging_dir).resolve()
    if not runtime_stage_path.is_dir():
        raise EnvironmentBundleError(f"runtime staging directory {runtime_stage_path} is missing")
    target_report = _load_json_payload(target_report_path, context="target capture")
    validate_target_capture_report(target_report)
    runtime_stage = _load_json_payload(runtime_stage_path / "runtime-stage.json", context="runtime stage")
    validate_runtime_stage_receipt(runtime_stage)
    torch_receipt = _load_json_payload(torch_receipt_path, context="torch receipt")
    if torch_receipt.get("receipt_type") != _TORCH_RECEIPT_TYPE:
        raise EnvironmentBundleError("torch receipt has the wrong type")
    torch_entry = _require_mapping(torch_receipt, "artifact", context="torch receipt")
    _validate_manifest_entry_shape(torch_entry, context="torch receipt.artifact")
    output_root_path = Path(output_root).resolve()
    output_root_path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "manifest_type": _RUNTIME_MANIFEST_TYPE,
        "schema_version": 1,
        "source_hashes": source_hashes_for_root(source_root_path),
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

    staging_publish = output_root_path / f".bundle-staging-{uuid.uuid4().hex[:8]}"
    staging_publish.mkdir(parents=True, exist_ok=False)
    try:
        for path in runtime_stage_path.iterdir():
            if path.is_symlink():
                raise EnvironmentBundleError(f"runtime staging contains a symlink: {path.name}")
            if path.is_file():
                if path.suffix in {".whl", ".gz"}:
                    shutil.copyfile(path, staging_publish / path.name)
                continue
            if path.name == "evidence":
                shutil.copytree(path, staging_publish / path.name)
        torch_source = Path(torch_receipt_path).resolve().parent / torch_entry["relative_path"]
        if not torch_source.is_file():
            raise EnvironmentBundleError(f"torch artifact missing beside receipt: {torch_source}")
        shutil.copyfile(torch_source, staging_publish / torch_entry["filename"])
        manifest_path = staging_publish / "environment-acquisition.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt = {
            "created_at": _utcnow(),
            "repo_revision": revision,
            "target_report_path": str(Path(target_report_path).resolve()),
            "torch_receipt_path": str(Path(torch_receipt_path).resolve()),
        }
        (staging_publish / "construction-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
        if final_path.exists():
            raise EnvironmentBundleError(f"final bundle destination already exists: {final_path}")
        staging_publish.replace(final_path)
        return {
            "bundle_root": str(final_path),
            "manifest_path": str(final_path / "environment-acquisition.json"),
            "manifest_hash": f"sha256:{manifest_hash}",
        }
    except Exception:
        _rollback_partial_path(staging_publish)
        raise


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
        install_parent = install_target.resolve().parent if install_target.exists() else install_target.parent.resolve()
        if install_parent != bundle_root_path and bundle_root_path not in install_parent.parents:
            raise EnvironmentBundleError(
                f"install manifest path {install_target} escapes bundle root {bundle_root_path}"
            )
        if install_target.exists():
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
) -> dict[str, Any]:
    manifest = load_acquisition_manifest(manifest_path)
    validated = _validate_acquisition_manifest_semantics(
        manifest,
        repo_root=repo_root,
        bundle_root=Path(manifest_path).resolve().parent,
        enforce_current_target=True,
        require_files=False,
    )
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
    if install_path.exists():
        raise EnvironmentBundleError(f"install manifest destination {install_path} already exists")
    install_path.parent.mkdir(parents=True, exist_ok=True)
    install_path.write_text(json.dumps(install_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return install_manifest


def load_acquisition_manifest(path: str | Path) -> dict[str, Any]:
    payload = _load_json_payload(path, context="acquisition manifest")
    validate_acquisition_manifest(payload)
    return payload


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
    runtime_entries = _validate_runtime_manifest(runtime_requirements, manifest["runtime"])
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
        if derived["builder"] != target:
            raise EnvironmentBundleError(f"derived wheel {normalized!r} builder target must equal the manifest target")
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
    if venv_path.exists():
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
    _wheel_path, creator_bytes = _validated_artifact_bytes(
        creator_entry,
        bundle_root=bundle_root_path,
    )
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
            [interpreter, "-I", "-c", code, str(snapshot_path), executed_creator_hash, str(staging_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
    except FileNotFoundError as exc:
        _rollback_partial_path(staging_path)
        _rollback_partial_path(snapshot_path)
        raise EnvironmentBundleError(f"Python executable {interpreter!r} is unavailable") from exc
    except subprocess.CalledProcessError as exc:
        _rollback_partial_path(staging_path)
        _rollback_partial_path(snapshot_path)
        detail = (exc.stderr or exc.stdout or "").strip() or "no stderr/stdout"
        raise EnvironmentBundleError(
            f"approved virtualenv creator failed before creating the target venv: {detail}"
        ) from exc
    except Exception:
        _rollback_partial_path(staging_path)
        _rollback_partial_path(snapshot_path)
        raise
    try:
        post_execution_hash = hashing.hash_file(snapshot_path)
        if post_execution_hash != executed_creator_hash:
            raise EnvironmentBundleError(
                f"creator snapshot hash mismatch: expected {executed_creator_hash}, got {post_execution_hash}"
            )
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
        staging_path.replace(venv_path)
    except Exception:
        _rollback_partial_path(staging_path)
        _rollback_partial_path(snapshot_path)
        raise
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
            "builder",
            "frontend",
            "backend",
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
    for field in ("builder", "frontend", "backend"):
        _require_mapping(entry, field, context=context)
    builder = entry["builder"]
    _require_exact_keys(
        builder,
        required={"os", "architecture", "python", "abi"},
        context=f"{context}.builder",
    )
    for field in ("os", "architecture", "python", "abi"):
        _require_string(builder, field, context=f"{context}.builder")
    for field in ("frontend", "backend"):
        tool = entry[field]
        _require_exact_keys(tool, required={"name", "version"}, context=f"{context}.{field}")
        _require_distribution(tool, "name", context=f"{context}.{field}")
        _require_string(tool, "version", context=f"{context}.{field}")
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
    for _ in range(32):
        candidate = (venv_path.parent / f"{venv_path.name}.staging-{uuid.uuid4().hex[:8]}").resolve()
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise EnvironmentBundleError(f"could not allocate a fresh staging directory for {venv_path}")


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
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=False)
        return
    path.unlink()


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
            manifest = record_installed_environment(args.manifest, args.install_manifest)
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
