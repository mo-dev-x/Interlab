from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from interplab.core import uris
from tests.job_test_helpers import TEST_ALLIANCE_TORCH_VERSION


def _git_bash() -> Path | None:
    candidate = Path(r"C:\Program Files\Git\bin\bash.exe")
    return candidate if candidate.is_file() else None


def _write_stub(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)

def _prepare_stubbed_shell(tmp_path: Path) -> tuple[Path, Path, Path]:
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    log_path = tmp_path / "stub.log"
    manifest_path = tmp_path / "acquisition.json"
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    manifest_path.write_text("{}", encoding="utf-8")

    _write_stub(
        stub_dir / "module",
        """#!/bin/sh
printf 'module %s\n' "$*" >> "$INTERPLAB_STUB_LOG"
""",
    )
    _write_stub(
        stub_dir / "python",
        """#!/bin/sh
printf 'python %s\n' "$*" >> "$INTERPLAB_STUB_LOG"
if [ "$2" = "preflight" ] && [ "$(basename "$1")" = "environment_bundle.py" ]; then
  if [ "${INTERPLAB_STUB_PREFLIGHT_FAIL:-0}" = "1" ]; then
    exit 1
  fi
  shift 2
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --plan-dir) plan_dir="$2"; shift 2 ;;
      --install-manifest) install_manifest="$2"; shift 2 ;;
      *) shift 1 ;;
    esac
  done
  mkdir -p "$plan_dir"
  printf 'pip==25.0 --hash=sha256:%064d\n' 1 > "$plan_dir/tooling.requirements.txt"
  printf 'torch==__TORCH_VERSION__ --hash=sha256:%064d\n' 2 > "$plan_dir/torch.requirements.txt"
  printf 'alpha==1.0 --hash=sha256:%064d\n' 3 > "$plan_dir/runtime.requirements.txt"
  printf '{}'
  exit 0
fi
if [ "$2" = "create-venv" ] && [ "$(basename "$1")" = "environment_bundle.py" ]; then
  shift 2
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --venv-dir) venv_dir="$2"; shift 2 ;;
      *) shift 1 ;;
    esac
  done
  mkdir -p "$venv_dir/bin"
  printf '# fake activate\n' > "$venv_dir/bin/activate"
  printf '{}'
  exit 0
fi
if [ "$2" = "record-installed" ] && [ "$(basename "$1")" = "environment_bundle.py" ]; then
  shift 2
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --install-manifest) install_manifest="$2"; shift 2 ;;
      *) shift 1 ;;
    esac
  done
  printf '{\"manifest_type\": \"environment_install_manifest\"}\n' > "$install_manifest"
  printf '{}'
  exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  exit 0
fi
exec "$REAL_PYTHON" "$@"
""".replace("__TORCH_VERSION__", TEST_ALLIANCE_TORCH_VERSION),
    )
    return stub_dir, log_path, manifest_path


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_uses_manifest_backed_offline_installs_and_activation_exports(tmp_path):
    bash = _git_bash()
    assert bash is not None
    stub_dir, log_path, manifest_path = _prepare_stubbed_shell(tmp_path)
    venv_dir = tmp_path / "venv"
    install_manifest_path = tmp_path / "installed.json"

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{stub_dir};{env['PATH']}",
            "REAL_PYTHON": sys.executable,
            "INTERPLAB_STUB_LOG": str(log_path),
            "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH": str(manifest_path),
            "INTERPLAB_ENV_BUNDLE_ROOT": str(tmp_path / "bundle"),
            "INTERPLAB_ENV_INSTALL_MANIFEST_PATH": str(install_manifest_path),
            "INTERPLAB_VENV_DIR": str(venv_dir),
        }
    )

    result = subprocess.run(
        [str(bash), str(uris.REPO_ROOT / "slurm" / "setup_env.sh")],
        cwd=uris.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines[0] == "module purge"
    assert log_lines[1] == "module load python/3.11 arrow"
    assert "environment_bundle.py preflight" in log_lines[2]
    assert str(manifest_path) in log_lines[2]
    assert str(install_manifest_path) in log_lines[2]
    assert "environment_bundle.py create-venv" in log_lines[3]
    assert str(venv_dir) in log_lines[3]
    pip_install_lines = [line for line in log_lines if line.startswith("python -m pip install ")]
    assert len(pip_install_lines) == 4
    assert all("--no-index" in line for line in pip_install_lines)
    assert all("--find-links" in line for line in pip_install_lines[:3])
    assert all("--require-hashes" in line for line in pip_install_lines[:3])
    assert "--no-build-isolation" in pip_install_lines[3]
    assert (venv_dir / "bin" / "interplab_env.sh").is_file()
    activate = (venv_dir / "bin" / "activate").read_text(encoding="utf-8")
    assert 'interplab_env.sh' in activate
    exports = (venv_dir / "bin" / "interplab_env.sh").read_text(encoding="utf-8")
    assert "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH" in exports
    assert "INTERPLAB_ENV_INSTALL_MANIFEST_PATH" in exports


@pytest.mark.skipif(_git_bash() is None, reason="Git Bash is unavailable on this host")
def test_setup_env_stops_before_virtualenv_when_preflight_fails(tmp_path):
    bash = _git_bash()
    assert bash is not None
    stub_dir, log_path, manifest_path = _prepare_stubbed_shell(tmp_path)
    venv_dir = tmp_path / "venv"

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{stub_dir};{env['PATH']}",
            "REAL_PYTHON": sys.executable,
            "INTERPLAB_STUB_LOG": str(log_path),
            "INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH": str(manifest_path),
            "INTERPLAB_ENV_BUNDLE_ROOT": str(tmp_path / "bundle"),
            "INTERPLAB_VENV_DIR": str(venv_dir),
            "INTERPLAB_STUB_PREFLIGHT_FAIL": "1",
        }
    )

    result = subprocess.run(
        [str(bash), str(uris.REPO_ROOT / "slurm" / "setup_env.sh")],
        cwd=uris.REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    log_text = log_path.read_text(encoding="utf-8")
    assert "environment_bundle.py preflight" in log_text
    assert "environment_bundle.py create-venv" not in log_text
    assert not venv_dir.exists()
