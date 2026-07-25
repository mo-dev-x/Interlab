"""interplab.core.environment (ED-1 §1.1, ED-32): environment detection for
the A10 `environment` RunCard field, and the SAE-stack baseline fail-closed
check for the certification lane.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version

import pytest

from interplab.core import environment
from interplab.core.errors import EnvironmentBaselineError


def test_detect_profile_is_local_without_cluster_env_vars(monkeypatch):
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.delenv("CC_CLUSTER", raising=False)
    assert environment.detect_profile() == "local"


def test_detect_profile_is_cluster_under_slurm_job_id(monkeypatch):
    monkeypatch.delenv("CC_CLUSTER", raising=False)
    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    assert environment.detect_profile() == "cluster"


def test_detect_profile_is_cluster_under_cc_cluster(monkeypatch):
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setenv("CC_CLUSTER", "tamia")
    assert environment.detect_profile() == "cluster"


def test_detect_environment_has_the_ed1_baseline_shape():
    env = environment.detect_environment()
    assert env["profile"] in ("local", "cluster")
    assert isinstance(env["python"], str) and env["python"]
    assert isinstance(env["torch"], str) and env["torch"]
    assert env["lock_hash"] is None or env["lock_hash"].startswith("sha256:")


def test_detect_environment_lock_hash_is_none_when_uv_lock_is_absent(tmp_path):
    env = environment.detect_environment(repo_root=tmp_path)
    assert env["lock_hash"] is None


def test_detect_environment_lock_hash_is_computed_when_uv_lock_exists(tmp_path):
    (tmp_path / "uv.lock").write_text("fake lock contents", encoding="utf-8")
    env = environment.detect_environment(repo_root=tmp_path)
    assert env["lock_hash"] is not None
    assert env["lock_hash"].startswith("sha256:")


def test_resolve_sae_stack_versions_resolves_the_real_installed_packages():
    # This environment genuinely has the pinned baseline installed (dev +
    # CI both `uv sync` from the same lockfile), so this is a real,
    # non-flaky assertion against ground truth, not a mock.
    versions = environment.resolve_sae_stack_versions()
    assert versions["sae_lens"] == pkg_version("sae-lens")
    assert versions["transformers"] == pkg_version("transformers")
    assert versions["transformer_lens"] == pkg_version("transformer-lens")


def test_resolve_sae_stack_versions_is_none_for_an_uninstalled_package(monkeypatch):
    from importlib.metadata import PackageNotFoundError

    def fake_version(dist_name):
        raise PackageNotFoundError(dist_name)

    monkeypatch.setattr(environment, "_pkg_version", fake_version)
    versions = environment.resolve_sae_stack_versions()
    assert versions == {"sae_lens": None, "transformers": None, "transformer_lens": None}


def test_check_sae_stack_baseline_passes_for_the_real_installed_version():
    versions = environment.resolve_sae_stack_versions()
    environment.check_sae_stack_baseline(versions)  # must not raise


def test_check_sae_stack_baseline_raises_for_a_wrong_major_version():
    with pytest.raises(EnvironmentBaselineError, match=r"6\.44\.2"):
        environment.check_sae_stack_baseline(
            {"sae_lens": "6.44.2", "transformers": "5.0.0", "transformer_lens": "3.0.0"}
        )


def test_check_sae_stack_baseline_raises_when_sae_lens_is_not_installed():
    with pytest.raises(EnvironmentBaselineError, match="not installed"):
        environment.check_sae_stack_baseline(
            {"sae_lens": None, "transformers": "4.44.0", "transformer_lens": "2.15.4"}
        )


def test_check_sae_stack_baseline_does_not_gate_transformers_or_transformer_lens():
    """ED-32's assertion clause names only sae-lens -- a mismatched
    transformers/transformer_lens version is recorded, never gated."""
    environment.check_sae_stack_baseline(
        {"sae_lens": "3.23.0", "transformers": "999.0.0", "transformer_lens": "0.0.1"}
    )  # must not raise


def test_build_certification_environment_merges_both_dicts():
    env = environment.build_certification_environment()
    assert set(env.keys()) == {
        "profile", "python", "torch", "lock_hash", "sae_lens", "transformers", "transformer_lens",
    }
    assert env["sae_lens"] == pkg_version("sae-lens")
