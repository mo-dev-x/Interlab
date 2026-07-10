#!/bin/bash
# Cluster environment profile (ED-1, docs/implementation_blueprint.md §1.1).
#
# Builds the Alliance/Tamia virtualenv that every SLURM job in slurm/ activates.
# Dependency truth is pyproject.toml; this script never installs a version that
# isn't already pinned there. It installs from two offline sources only:
#   1. slurm/requirements.cluster.txt -- a `uv export` of pyproject.toml's base
#      dependencies (torch excluded), regenerated on the machine that has `uv`
#      (local profile) whenever pyproject.toml or uv.lock changes:
#        uv export --no-dev --no-emit-project --no-emit-package torch \
#            --no-hashes -o slurm/requirements.cluster.txt
#   2. the Alliance wheelhouse, via `pip install --no-index`, for torch itself
#      (CUDA build) since the CPU build pinned locally (pyproject.toml's
#      pytorch-cpu index) is not what a GPU job needs.
#
# Usage: bash slurm/setup_env.sh
# Re-run any time slurm/requirements.cluster.txt changes; it is idempotent.

set -euo pipefail

VENV_DIR="${INTERPLAB_VENV_DIR:-$HOME/interplab-venv}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQS_FILE="$REPO_ROOT/slurm/requirements.cluster.txt"

if [ ! -f "$REQS_FILE" ]; then
  echo "Missing $REQS_FILE -- regenerate it from the local profile with:" >&2
  echo "  uv export --no-dev --no-emit-project --no-emit-package torch --no-hashes -o slurm/requirements.cluster.txt" >&2
  exit 1
fi

module purge
module load python/3.11 arrow

virtualenv --no-download "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --no-index --upgrade pip

# CUDA torch comes from the Alliance wheelhouse, not from pyproject.toml's
# CPU index -- this is the one dependency the two profiles legitimately
# resolve differently (ED-1).
pip install --no-index torch

pip install --no-index -r "$REQS_FILE"

# Editable install of interplab itself: local source, no index contacted.
pip install --no-index --no-build-isolation -e "$REPO_ROOT"

echo "Cluster environment ready at $VENV_DIR"
echo "Activate with: source $VENV_DIR/bin/activate"
