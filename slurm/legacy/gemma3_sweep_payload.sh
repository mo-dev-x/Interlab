#!/bin/bash
# D2.1 fix 3: the actual batch payload, as a real file -- no `--wrap`, no
# nested `bash -lc "..."` escaping. The prior --wrap version embedded
# `\"\${SPRINT_VENV_DIR:-\$HOME/sprint-venv}\"` inside a second shell layer,
# the same inline-quoting hazard that produced a false-empty grep elsewhere
# in this project: a command that silently does the wrong thing and still
# returns exit 0. SLURM invokes this file directly; $1/$2/... are plain
# positional parameters, no shell-through-a-shell involved.
#
# Invoked by slurm/legacy/launch_gemma3_sweep.sh via:
#   sbatch <sbatch-flags> gemma3_sweep_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra gemma3_sweep.py args...]
set -euo pipefail

MODEL_PATH="${1:?usage: gemma3_sweep_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
SAE_PATH="${2:?usage: gemma3_sweep_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
shift 2

# NOT derived from BASH_SOURCE[0]: Slurm copies a script submitted directly
# to sbatch (as this one is -- no --wrap) into /var/spool/... before
# executing it, so BASH_SOURCE[0] there resolves to a spool path, not this
# repo (confirmed: job 398628 failed in 3s on `can't open file
# '/var/spool/scripts/legacy/gemma3_sweep.py'`). SLURM_SUBMIT_DIR is the
# directory `sbatch` was invoked from (launch_gemma3_sweep.sh runs it from
# the repo root), which is the correct and portable source of truth here.
REPO_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is unset -- refusing to guess the repo root}"
cd "$REPO_ROOT"

module purge
module load StdEnv/2023 python/3.11 arrow/25.0.0
source "${SPRINT_VENV_DIR:-$HOME/sprint-venv}/bin/activate"
# Defence in depth: the module-load/activate guard elsewhere in this
# project is already SLURM_JOB_ID-conditional, so a job should never carry
# HF_TOKEN -- this costs one line and the failure it prevents
# (a credential leaking into an offline compute-node job's environment) is
# unrecoverable.
unset HF_TOKEN
export HF_HUB_OFFLINE=1
# `python scripts/legacy/gemma3_sweep.py` (a script PATH) puts the script's
# own directory in sys.path[0], not $REPO_ROOT -- interplab is not
# pip-installed in sprint-venv, so `from interplab.core import hashing`
# (compute_checkpoint_hash, hit even under --dry-run) raises
# ModuleNotFoundError without this. Confirmed via a free CPU-only --dry-run
# on the login node before this line was added; harness itself untouched.
# Prepend, not overwrite: `module load arrow/25.0.0` sets its own
# PYTHONPATH for pyarrow's bindings (job 398618 broke `import pyarrow` by
# overwriting instead of prepending).
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

python scripts/legacy/gemma3_sweep.py \
  --model-path "$MODEL_PATH" \
  --sae-path "$SAE_PATH" \
  --out-dir results/gemma3_sweep \
  --device cuda \
  --dtype bfloat16 \
  "$@"
