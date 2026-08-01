from __future__ import annotations

import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

from interplab.core import environment_bundle, hashing, uris
from interplab.registry import run_card as run_card_module

_CERT_LANE_ENV_FIELDS = {
    "profile",
    "python",
    "torch",
    "lock_hash",
    "sae_lens",
    "transformers",
    "transformer_lens",
}
TEST_REPO_REVISION = "c" * 40
TEST_LOADED_MODULES = ["python/3.11.5", "arrow/25.0.0"]
TEST_ALLIANCE_TORCH_VERSION = "2.13.0+computecanada"
TEST_ALLIANCE_CUDA_VERSION = "13.2"
TEST_ALLIANCE_TORCH_ORIGIN = "alliance:wheelhouse/torch-2.13.0+computecanada-cp311"


def load_stage_run_cards(registry_root: Path, stage: str) -> list[dict]:
    cards = [json.loads(path.read_text(encoding="utf-8")) for path in (registry_root / "run_card").glob("*.json")]
    return [card for card in cards if card["payload"]["stage"] == stage]


def _expected_config_ref(config_path: Path, repo_root: Path) -> str:
    return run_card_module._config_ref_for_path(config_path.resolve(), repo_root=repo_root.resolve())


def patch_alliance_torch_runtime(
    monkeypatch,
    *,
    distribution_version: str = TEST_ALLIANCE_TORCH_VERSION,
    cuda: str | None = TEST_ALLIANCE_CUDA_VERSION,
    available: bool = True,
) -> None:
    real_dist_version = environment_bundle.dist_version

    def fake_dist_version(name: str) -> str:
        if environment_bundle.normalize_distribution_name(name) == "torch":
            return distribution_version
        return real_dist_version(name)

    monkeypatch.setattr(environment_bundle, "dist_version", fake_dist_version)
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            version=SimpleNamespace(cuda=cuda),
            cuda=SimpleNamespace(is_available=lambda: available),
        ),
    )


def assert_only_run_card_written(registry_root: Path) -> None:
    artifact_paths = list(registry_root.rglob("*.json"))
    assert len(artifact_paths) == 1
    assert artifact_paths[0].parent.name == "run_card"


def assert_failed_invalid_config_run_card(
    registry_root: Path,
    *,
    stage: str,
    config_path: Path,
    repo_root: Path,
    expect_environment: bool = False,
) -> dict:
    cards = load_stage_run_cards(registry_root, stage)
    assert len(cards) == 1
    card = cards[0]
    payload = card["payload"]

    assert payload["stage"] == stage
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 3
    assert payload["inputs"] == []
    assert payload["outputs"] == []
    assert card["subject"] == []
    assert payload["outcome_line"].startswith("invalid config:")
    assert payload["config_hash"] == hashing.hash_file(config_path)
    assert payload["config_ref"] == _expected_config_ref(config_path, repo_root)

    if expect_environment:
        assert _CERT_LANE_ENV_FIELDS.issubset(payload["environment"])
    else:
        assert "environment" not in payload

    return card


def assert_failed_environment_run_card(
    registry_root: Path,
    *,
    stage: str,
    config_path: Path,
    repo_root: Path,
    expected_roles: set[str],
    outcome_prefix: str = "environment evidence invalid:",
) -> dict:
    cards = load_stage_run_cards(registry_root, stage)
    assert len(cards) == 1
    card = cards[0]
    payload = card["payload"]

    assert payload["stage"] == stage
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 4
    assert payload["outputs"] == []
    assert {entry["role"] for entry in payload["inputs"]} == expected_roles
    assert card["subject"] == payload["inputs"]
    assert payload["outcome_line"].startswith(outcome_prefix)
    assert payload["config_hash"] == hashing.hash_file(config_path)
    assert payload["config_ref"] == _expected_config_ref(config_path, repo_root)
    assert _CERT_LANE_ENV_FIELDS.issubset(payload["environment"])

    return card


def _source_hashes() -> dict:
    return {
        "pyproject": {
            "path": "pyproject.toml",
            "sha256": hashing.hash_file(uris.REPO_ROOT / "pyproject.toml"),
        },
        "uv_lock": {
            "path": "uv.lock",
            "sha256": hashing.hash_file(uris.REPO_ROOT / "uv.lock"),
        },
        "cluster_requirements": {
            "path": "slurm/requirements.cluster.txt",
            "sha256": hashing.hash_file(uris.REPO_ROOT / "slurm" / "requirements.cluster.txt"),
        },
    }


def _manifest_entry(
    distribution: str,
    version: str,
    sha256: str,
    *,
    relative_dir: str,
    artifact_type: str = "wheel",
    origin: str = "bundle:test",
) -> dict:
    stem = distribution.replace("-", "_")
    filename = (
        f"{stem}-{version}-py3-none-any.whl"
        if artifact_type == "wheel"
        else f"{stem}-{version}.tar.gz"
    )
    return {
        "distribution": distribution,
        "version": version,
        "filename": filename,
        "relative_path": f"{relative_dir}/{filename}",
        "size_bytes": 1,
        "origin": origin,
        "sha256": sha256,
        "type": artifact_type,
    }


def _write_bundle_artifact(base: Path, entry: dict, content: bytes = b"x") -> dict:
    path = base / entry["relative_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    updated = dict(entry)
    updated["size_bytes"] = path.stat().st_size
    updated["sha256"] = hashing.hash_file(path)
    return updated


def _wheel_bytes(distribution: str, version: str) -> bytes:
    buffer = io.BytesIO()
    normalized = distribution.replace("-", "_")
    with zipfile.ZipFile(buffer, "w") as wheel:
        wheel.writestr(
            f"{normalized}-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        )
        wheel.writestr(
            f"{normalized}-{version}.dist-info/WHEEL",
            "Wheel-Version: 1.0\nTag: py3-none-any\n",
        )
    return buffer.getvalue()


def _acquisition_manifest_payload() -> dict:
    target = environment_bundle.current_target()
    requirements = environment_bundle.selected_runtime_requirements(
        {"target": target},
        environment_bundle.parse_requirements_export(environment_bundle.requirements_export()),
    )
    runtime_by_name: dict[str, dict] = {}
    for requirement in requirements:
        runtime_by_name.setdefault(
            requirement.distribution,
            _manifest_entry(
                requirement.distribution,
                requirement.version,
                requirement.hashes[0],
                relative_dir="runtime",
            ),
        )
    runtime = list(runtime_by_name.values())
    tooling_versions = {
        "pip": "25.0",
        "setuptools": "80.0",
        "wheel": "0.45.0",
        "hatchling": "1.27.0",
        "virtualenv": "20.26.0",
    }
    tooling = []
    for name, version, digit in (
        ("pip", tooling_versions["pip"], "a"),
        ("setuptools", tooling_versions["setuptools"], "b"),
        ("wheel", tooling_versions["wheel"], "c"),
        ("hatchling", tooling_versions["hatchling"], "d"),
        ("virtualenv", tooling_versions["virtualenv"], "e"),
    ):
        tooling.append(
            dict(runtime_by_name[name])
            if name in runtime_by_name
            else _manifest_entry(name, version, f"sha256:{digit * 64}", relative_dir="tooling")
        )
    return {
        "manifest_type": "environment_acquisition_manifest",
        "schema_version": 1,
        "source_hashes": _source_hashes(),
        "target": target,
        "generator": {
            "uv": "0.8.22",
            "pip": tooling_versions["pip"],
            "virtualenv": "20.26.0",
            "hatchling": tooling_versions["hatchling"],
        },
        "tooling": {"installers": tooling},
        "torch": _manifest_entry(
            "torch",
            TEST_ALLIANCE_TORCH_VERSION,
            "sha256:" + "e" * 64,
            relative_dir="torch",
            origin=TEST_ALLIANCE_TORCH_ORIGIN,
        ),
        "runtime": runtime,
        "derived_wheels": [],
    }


def _install_manifest_payload(acquisition_manifest: dict, acquisition_hash: str) -> dict:
    project_name, project_version = environment_bundle._local_project_identity(uris.REPO_ROOT)
    installed_by_name: dict[str, dict[str, str]] = {}
    for entry in [
        *acquisition_manifest["runtime"],
        *acquisition_manifest["tooling"]["installers"],
        acquisition_manifest["torch"],
    ]:
        installed_by_name[environment_bundle.normalize_distribution_name(entry["distribution"])] = {
            "distribution": entry["distribution"],
            "version": entry["version"],
        }
    installed_by_name[project_name] = {"distribution": project_name, "version": project_version}
    return {
        "manifest_type": "environment_install_manifest",
        "schema_version": 1,
        "created_at": "2026-07-30T00:00:00Z",
        "acquisition_manifest_hash": acquisition_hash,
        "repo_revision": TEST_REPO_REVISION,
        "source_hashes": acquisition_manifest["source_hashes"],
        "target": acquisition_manifest["target"],
        "loaded_modules": list(TEST_LOADED_MODULES),
        "installer_versions": {
            entry["distribution"]: entry["version"]
            for entry in acquisition_manifest["tooling"]["installers"]
        },
        "torch": {
            "distribution": acquisition_manifest["torch"]["distribution"],
            "version": acquisition_manifest["torch"]["version"],
            "cuda": TEST_ALLIANCE_CUDA_VERSION,
            "cuda_available": True,
        },
        "verified_imports": [],
        "installed_distributions": sorted(
            installed_by_name.values(),
            key=lambda entry: entry["distribution"].lower(),
        ),
    }


def write_cert_lane_environment_files(name: str) -> tuple[Path, Path, Path]:
    base = uris.REPO_ROOT / "results" / "_test_scratch" / name
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    acquisition = base / "environment_acquisition_manifest.json"
    install = base / "environment_install_manifest.json"
    acquisition_payload = _acquisition_manifest_payload()
    acquisition_payload["tooling"]["installers"] = [
        _write_bundle_artifact(
            base,
            entry,
            content=_wheel_bytes(entry["distribution"], entry["version"]),
        )
        if entry["distribution"] == "virtualenv"
        else entry
        for entry in acquisition_payload["tooling"]["installers"]
    ]
    acquisition_payload["torch"] = _write_bundle_artifact(
        base,
        acquisition_payload["torch"],
        content=_wheel_bytes(
            acquisition_payload["torch"]["distribution"],
            acquisition_payload["torch"]["version"],
        ),
    )
    acquisition.write_text(json.dumps(acquisition_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    install_payload = _install_manifest_payload(acquisition_payload, hashing.hash_file(acquisition))
    install.write_text(json.dumps(install_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return base, acquisition, install


def write_transformer_lens_equivalence_report(
    name: str,
    config: dict,
) -> tuple[Path, Path]:
    base = uris.REPO_ROOT / "results" / "_test_scratch" / name
    base.mkdir(parents=True, exist_ok=True)
    report = base / "transformer_lens_equivalence_report.json"
    payload = {
        "report_type": "transformer_lens_equivalence_report",
        "schema_version": 1,
        "checkpoint_hash": config["checkpoint_hash"],
        "config_hash": environment_bundle._R5_X2_AUTHORITATIVE_CONFIG_HASH,
        "token_stream": {
            "n_tokens": config["n_tokens"],
            "seq_len": config["seq_len"],
            "batch_size": config["batch_size"],
            "eval_slice": config["eval_slice"],
        },
        "comparison": {
            "baseline_transformer_lens": "3.2.1",
            "candidate_transformer_lens": "3.4.0",
        },
        "checks": {
            "activation_hook": "blocks.28.hook_resid_post",
            "tokenization_equal": True,
            "positions_equal": True,
            "activations_equal": True,
            "sae_forward_passed": True,
        },
    }
    report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return base, report
