from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.job_test_helpers import TEST_ALLIANCE_TORCH_VERSION


def _git_bash() -> Path | None:
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    return candidate if candidate.is_file() else None


def _write_stub(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _fixture_checkout(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "fixture-repo"
    (repo / "slurm").mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "slurm" / "setup_env.sh",
        repo / "slurm" / "setup_env.sh",
    )
    (repo / "slurm" / "requirements.cluster.txt").write_text(
        "alpha==1.0 --hash=sha256:" + "3" * 64 + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (repo / "README.md").write_text("fixture checkout\n", encoding="utf-8", newline="\n")
    _run_git(repo, "init")
    _run_git(repo, "config", "user.name", "Fixture")
    _run_git(repo, "config", "user.email", "fixture@example.test")
    _run_git(repo, "add", "README.md", "slurm/setup_env.sh", "slurm/requirements.cluster.txt")
    _run_git(repo, "commit", "-m", "fixture")
    head = _run_git(repo, "rev-parse", "HEAD").stdout.strip()
    assert len(head) == 40
    return repo, head


def _prepare_stubbed_shell(tmp_path: Path) -> tuple[Path, Path, Path]:
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    helper = tmp_path / "python_stub_helper.py"
    helper.write_text(
        textwrap.dedent(
            """
            from __future__ import annotations

            import json
            import os
            import pathlib
            import sys

            from interplab.core import environment_bundle as bundle


            def _log() -> None:
                log_path = os.environ.get("INTERPLAB_STUB_LOG")
                if log_path:
                    with open(log_path, "a", encoding="utf-8", newline="\\n") as handle:
                        handle.write(f"python {' '.join(sys.argv[1:])}\\n")


            def _parse_flag(flag: str) -> str:
                args = sys.argv[1:]
                for index, token in enumerate(args):
                    if token == flag and index + 1 < len(args):
                        return args[index + 1]
                raise SystemExit(f"missing {flag}")


            def main() -> int:
                _log()
                args = sys.argv[1:]
                if len(args) >= 2 and pathlib.Path(args[0]).name == "environment_bundle.py" and args[1] == "preflight":
                    source_root = pathlib.Path(_parse_flag("--source-root")).resolve()
                    expected_revision = _parse_flag("--expected-revision")
                    bundle._validate_clean_source_root(source_root, expected_revision)
                    if os.environ.get("INTERPLAB_STUB_PREFLIGHT_FAIL") == "1":
                        return 1
                    plan_dir = pathlib.Path(_parse_flag("--plan-dir"))
                    plan_dir.mkdir(parents=True, exist_ok=True)
                    (plan_dir / "tooling.requirements.txt").write_text(
                        "pip==25.0 --hash=sha256:" + "1" * 64 + "\\n",
                        encoding="utf-8",
                    )
                    (plan_dir / "torch.requirements.txt").write_text(
                        "torch==__TORCH_VERSION__ --hash=sha256:" + "2" * 64 + "\\n",
                        encoding="utf-8",
                    )
                    (plan_dir / "runtime.requirements.txt").write_text(
                        "alpha==1.0 --hash=sha256:" + "3" * 64 + "\\n",
                        encoding="utf-8",
                    )
                    sys.stdout.write("{}")
                    return 0
                if len(args) >= 2 and pathlib.Path(args[0]).name == "environment_bundle.py" and args[1] == "create-venv":
                    venv_dir = pathlib.Path(_parse_flag("--venv-dir"))
                    (venv_dir / "bin").mkdir(parents=True, exist_ok=True)
                    (venv_dir / "bin" / "activate").write_text("# fake activate\\n", encoding="utf-8")
                    sys.stdout.write("{}")
                    return 0
                if len(args) >= 2 and pathlib.Path(args[0]).name == "environment_bundle.py" and args[1] == "record-installed":
                    install_manifest = pathlib.Path(_parse_flag("--install-manifest"))
                    install_manifest.write_text(
                        '{"manifest_type": "environment_install_manifest"}\\n',
                        encoding="utf-8",
                    )
                    sys.stdout.write("{}")
                    return 0
                if len(args) >= 2 and args[0] == "-m" and args[1] == "pip":
                    return 0
                os.execv(sys.executable, [sys.executable, *args])
                return 1


            if __name__ == "__main__":
                raise SystemExit(main())
            """.replace("__TORCH_VERSION__", TEST_ALLIANCE_TORCH_VERSION)
        ).strip()
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_stub(
        stub_dir / "module",
        """#!/bin/sh
if [ -n "${INTERPLAB_STUB_LOG:-}" ]; then
  printf 'module %s\n' "$*" >> "$INTERPLAB_STUB_LOG"
fi
""",
    )
    _write_stub(
        stub_dir / "python",
        """#!/bin/sh
exec "$REAL_PYTHON" "$INTERPLAB_STUB_HELPER" "$@"
""",
    )
    manifest_path = tmp_path / "acquisition.json"
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    manifest_path.write_text("{}", encoding="utf-8")
    return stub_dir, helper, manifest_path


def _setup_env_result(
    tmp_path: Path,
    *,
    expected_revision: str | None,
    use_stub_log: bool,
    use_fixture_head: bool = False,
    dirty_checkout: bool = False,
    preflight_fail: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, str, Path, Path, Path]:
    bash = _git_bash()
    assert bash is not None
    repo, head = _fixture_checkout(tmp_path)
    if dirty_checkout:
        (repo / "README.md").write_text("dirty fixture\n", encoding="utf-8", newline="\n")
    stub_dir, helper, manifest_path = _prepare_stubbed_shell(tmp_path)
    venv_dir = tmp_path / "venv"
    install_manifest_path = tmp_path / "installed.json"
    log_path = tmp_path / "stub.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{stub_dir};{env['PATH']}",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "REAL_PYTHON": sys.executable,
            "INTERPLAB_STUB_HELPER": str(helper),
            "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH": str(manifest_path),
            "INTERPLAB_ENV_BUNDLE_ROOT": str(tmp_path / "bundle"),
            "INTERPLAB_ENV_INSTALL_MANIFEST_PATH": str(install_manifest_path),
            "INTERPLAB_VENV_DIR": str(venv_dir),
        }
    )
    if use_fixture_head:
        env["INTERPLAB_EXPECTED_REVISION"] = head
    elif expected_revision is not None:
        env["INTERPLAB_EXPECTED_REVISION"] = expected_revision
    if use_stub_log:
        env["INTERPLAB_STUB_LOG"] = str(log_path)
    if preflight_fail:
        env["INTERPLAB_STUB_PREFLIGHT_FAIL"] = "1"
    result = subprocess.run(
        [str(bash), str(repo / "slurm" / "setup_env.sh")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, repo, head, venv_dir, install_manifest_path, log_path


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
@pytest.mark.parametrize("use_stub_log", [False, True])
def test_setup_env_uses_matching_fixture_head_and_reaches_stubbed_mutation_steps(tmp_path, use_stub_log):
    result, _repo, head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision=None,
        use_stub_log=use_stub_log,
        use_fixture_head=True,
    )

    assert result.returncode == 0, result.stderr
    assert (venv_dir / "bin" / "interplab_env.sh").is_file()
    assert install_manifest_path.is_file()
    activate = (venv_dir / "bin" / "activate").read_text(encoding="utf-8")
    assert "interplab_env.sh" in activate
    exports = (venv_dir / "bin" / "interplab_env.sh").read_text(encoding="utf-8")
    assert "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH" in exports
    assert "INTERPLAB_ENV_INSTALL_MANIFEST_PATH" in exports
    if use_stub_log:
        log_lines = log_path.read_text(encoding="utf-8").splitlines()
        assert log_lines[0] == "module purge"
        assert log_lines[1] == "module load python/3.11 arrow"
        assert f"--expected-revision {head}" in log_lines[2]
        assert "environment_bundle.py create-venv" in log_lines[3]
        pip_install_lines = [line for line in log_lines if line.startswith("python -m pip install ")]
        assert len(pip_install_lines) == 4
        assert all("--no-index" in line for line in pip_install_lines)
        assert all("--find-links" in line for line in pip_install_lines[:3])
        assert all("--require-hashes" in line for line in pip_install_lines[:3])
        assert "--no-build-isolation" in pip_install_lines[3]


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_requires_explicit_expected_revision_authority(tmp_path):
    result, _repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision=None,
        use_stub_log=True,
    )

    assert result.returncode != 0
    assert "INTERPLAB_EXPECTED_REVISION" in result.stderr
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    assert not log_path.exists()


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_rejects_malformed_expected_revision_before_mutation(tmp_path):
    result, _repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision="deadbeef",
        use_stub_log=True,
    )

    assert result.returncode != 0
    assert "40-character lowercase Git revision" in result.stderr
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    assert not log_path.exists()


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_rejects_all_zero_expected_revision_before_mutation(tmp_path):
    result, _repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision="0" * 40,
        use_stub_log=True,
    )

    assert result.returncode != 0
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "environment_bundle.py preflight" in log_text
    assert "environment_bundle.py create-venv" not in log_text


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
@pytest.mark.parametrize("use_stub_log", [False, True])
def test_setup_env_rejects_other_valid_expected_revision_before_mutation(tmp_path, use_stub_log):
    result, repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision="1" * 40,
        use_stub_log=use_stub_log,
    )

    assert result.returncode != 0
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    if use_stub_log:
        log_text = log_path.read_text(encoding="utf-8")
        assert "environment_bundle.py preflight" in log_text
        assert "environment_bundle.py create-venv" not in log_text
    assert _run_git(repo, "rev-parse", "HEAD").stdout.strip() != "1" * 40


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_rejects_dirty_checkout_before_mutation(tmp_path):
    result, _repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision=None,
        use_stub_log=True,
        use_fixture_head=True,
        dirty_checkout=True,
    )

    assert result.returncode != 0
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "environment_bundle.py preflight" in log_text
    assert "environment_bundle.py create-venv" not in log_text


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_stops_before_virtualenv_when_preflight_fails(tmp_path):
    result, _repo, _head, venv_dir, install_manifest_path, log_path = _setup_env_result(
        tmp_path,
        expected_revision=None,
        use_stub_log=True,
        use_fixture_head=True,
        preflight_fail=True,
    )

    assert result.returncode != 0
    assert not venv_dir.exists()
    assert not install_manifest_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "environment_bundle.py preflight" in log_text
    assert "environment_bundle.py create-venv" not in log_text
