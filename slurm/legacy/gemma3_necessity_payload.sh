#!/bin/bash
# Batch payload for scripts/legacy/gemma3_necessity.py -- a real file, no
# `--wrap`, no nested `bash -lc "..."` escaping, mirroring
# slurm/legacy/gemma3_sweep_payload.sh's already-fixed pattern exactly
# (that file is frozen; this is an independent, separately-submitted job so
# the sweep can run in parallel and unfreezing risk stays at zero).
#
# Invoked by slurm/legacy/launch_gemma3_necessity.sh via:
#   sbatch <sbatch-flags> gemma3_necessity_payload.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra gemma3_necessity.py args...]
set -euo pipefail

MODEL_PATH="${1:?usage: gemma3_necessity_payload.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
SAE_PATH="${2:?usage: gemma3_necessity_payload.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
SNIPPETS_FILE="${3:?usage: gemma3_necessity_payload.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
shift 3

# NOT derived from BASH_SOURCE[0]: Slurm copies a script submitted directly
# to sbatch (as this one is -- no --wrap) into /var/spool/... before
# executing it, so BASH_SOURCE[0] there resolves to a spool path, not this
# repo (the sweep payload hit exactly this in job 398628). SLURM_SUBMIT_DIR
# is the directory `sbatch` was invoked from (launch_gemma3_necessity.sh
# runs it from the repo root), the correct and portable source of truth.
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
# `python scripts/legacy/gemma3_necessity.py` (a script PATH) puts the
# script's own directory in sys.path[0], not $REPO_ROOT -- interplab is not
# pip-installed in sprint-venv, so `from interplab.core import hashing` /
# `from interplab.interventions.hooks import attach` raise
# ModuleNotFoundError without this (same fix as the sweep payload, same
# root cause). Prepend, not overwrite: `module load arrow/25.0.0` sets its
# own PYTHONPATH for pyarrow's bindings (job 398618 broke `import pyarrow`
# by overwriting instead of prepending).
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

python scripts/legacy/gemma3_necessity.py \
  --model-path "$MODEL_PATH" \
  --sae-path "$SAE_PATH" \
  --snippets-file "$SNIPPETS_FILE" \
  --out-dir results/gemma3_necessity \
  --device cuda \
  --dtype bfloat16 \
  "$@"
