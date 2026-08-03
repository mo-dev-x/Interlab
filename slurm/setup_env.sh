#!/bin/bash
# Cluster environment profile (ED-1, amended by ED-36).
#
# Builds the Alliance/Tamia virtualenv that every SLURM job in slurm/ activates.
# Dependency truth remains pyproject.toml / uv.lock; this script never installs
# a version not already pinned there. Production cluster installation is offline
# only and validates every bundle input before creating or altering the target
# environment.
#
# Checked-in base export (torch excluded, hashes included) from the committed lock:
#   uv export --locked --no-dev --no-emit-project \
#       --no-emit-package torch -o slurm/requirements.cluster.txt
#
# Required environment variables:
#   INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH
#       Absolute or relative path to the ED-36 acquisition manifest JSON.
# Optional environment variables:
#   INTERPLAB_ENV_BUNDLE_ROOT
#       Root directory holding the offline bundle files; defaults to the
#       acquisition-manifest directory.
#   INTERPLAB_ENV_INSTALL_MANIFEST_PATH
#       Where to write the installed-environment manifest; defaults to
#       <bundle-root>/installed-environment.json.
#
# Usage: bash slurm/setup_env.sh

set -euo pipefail

VENV_DIR="${INTERPLAB_VENV_DIR:-$HOME/interplab-venv}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQS_FILE="$REPO_ROOT/slurm/requirements.cluster.txt"
MANIFEST_PATH="${INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH:-}"
EXPECTED_REVISION="$(git -C "$REPO_ROOT" rev-parse HEAD)"

if [ -z "$MANIFEST_PATH" ]; then
  echo "Set INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH to the ED-36 acquisition manifest JSON." >&2
  exit 1
fi

if [ ! -f "$REQS_FILE" ]; then
  echo "Missing $REQS_FILE -- regenerate it from the committed lock with:" >&2
  echo "  uv export --locked --no-dev --no-emit-project --no-emit-package torch -o slurm/requirements.cluster.txt" >&2
  exit 1
fi

BUNDLE_ROOT="${INTERPLAB_ENV_BUNDLE_ROOT:-$(dirname "$MANIFEST_PATH")}"
INSTALL_MANIFEST_PATH="${INTERPLAB_ENV_INSTALL_MANIFEST_PATH:-$BUNDLE_ROOT/installed-environment.json}"
PLAN_DIR="$(mktemp -d "${TMPDIR:-/tmp}/interplab-setup-env.XXXXXX")"
PRECHECK_PATH="$PLAN_DIR/preflight.json"
TOOLING_REQS="$PLAN_DIR/tooling.requirements.txt"
TORCH_REQS="$PLAN_DIR/torch.requirements.txt"
RUNTIME_REQS="$PLAN_DIR/runtime.requirements.txt"
ENV_EXPORTS="$VENV_DIR/bin/interplab_env.sh"
ACTIVATE_SNIPPET='if [ -f "$VIRTUAL_ENV/bin/interplab_env.sh" ]; then . "$VIRTUAL_ENV/bin/interplab_env.sh"; fi'

cleanup() {
  rm -rf "$PLAN_DIR"
}
trap cleanup EXIT

module purge
module load python/3.11 arrow

python "$REPO_ROOT/interplab/core/environment_bundle.py" preflight \
  --manifest "$MANIFEST_PATH" \
  --bundle-root "$BUNDLE_ROOT" \
  --venv-dir "$VENV_DIR" \
  --plan-dir "$PLAN_DIR" \
  --install-manifest "$INSTALL_MANIFEST_PATH" \
  --source-root "$REPO_ROOT" \
  --expected-revision "$EXPECTED_REVISION" \
  > "$PRECHECK_PATH"

python "$REPO_ROOT/interplab/core/environment_bundle.py" create-venv \
  --manifest "$MANIFEST_PATH" \
  --bundle-root "$BUNDLE_ROOT" \
  --venv-dir "$VENV_DIR" \
  --source-root "$REPO_ROOT" \
  --expected-revision "$EXPECTED_REVISION" \
  > "$PLAN_DIR/create-venv.json"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

export PIP_NO_INDEX=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

python -m pip install --no-index --require-hashes --find-links "$BUNDLE_ROOT" -r "$TOOLING_REQS"
python -m pip install --no-index --require-hashes --find-links "$BUNDLE_ROOT" -r "$TORCH_REQS"
python -m pip install --no-index --require-hashes --find-links "$BUNDLE_ROOT" -r "$RUNTIME_REQS"

# Editable install of interplab itself: local source, no index contacted, and
# with build tooling already pinned by the validated offline bundle.
python -m pip install --no-index --no-build-isolation -e "$REPO_ROOT"
python -m pip check

python "$REPO_ROOT/interplab/core/environment_bundle.py" record-installed \
  --manifest "$MANIFEST_PATH" \
  --install-manifest "$INSTALL_MANIFEST_PATH" \
  > "$PLAN_DIR/installed-environment.json"

cat > "$ENV_EXPORTS" <<EOF
export INTERPLAB_ENV_ACQUISITION_MANIFEST_PATH="$MANIFEST_PATH"
export INTERPLAB_ENV_INSTALL_MANIFEST_PATH="$INSTALL_MANIFEST_PATH"
EOF

if ! grep -Fqx "$ACTIVATE_SNIPPET" "$VENV_DIR/bin/activate"; then
  printf '\n%s\n' "$ACTIVATE_SNIPPET" >> "$VENV_DIR/bin/activate"
fi

echo "Cluster environment ready at $VENV_DIR"
echo "Acquire with: source $VENV_DIR/bin/activate"
echo "Acquisition manifest: $MANIFEST_PATH"
echo "Installed manifest:   $INSTALL_MANIFEST_PATH"
