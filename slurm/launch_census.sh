#!/bin/bash
# SS12 parameterized launcher (§6.3) for `interplab.jobs.census` (SS1).
#
# Usage: bash slurm/launch_census.sh <config.yaml> <run_id>
#
# Prints the sbatch command and a log-tail command, then submits. Resource
# request is calibrated from prior scheduler job 382736 elapsed 00:29:15;
# 2× elapsed = 00:58:30, rounded to 01:00:00. The producing A10 records
# `slurm: null`, so registry linkage must be inferred from exact timestamps and
# pre/post registry snapshots rather than file modification time. Eight CPUs are
# retained because tokenizer parallelism was unenabled/unconfirmed.
set -euo pipefail

CONFIG="${1:?usage: launch_census.sh <config.yaml> <run_id>}"
RUN_ID="${2:?usage: launch_census.sh <config.yaml> <run_id>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

REMOTE_CMD="module purge && module load python/3.11 arrow && source \"\${INTERPLAB_VENV_DIR:-\$HOME/interplab-venv}/bin/activate\" && cd \"$REPO_ROOT\" && python scripts/census.py --config \"$CONFIG\""
# Tamia's generated `sbatch --wrap` script runs under `/bin/sh`, so the
# module/source-heavy remote payload must cross that boundary explicitly via
# login Bash without submit-host expansion of the remote venv fallback.
printf -v WRAP_CMD 'bash -lc %q' "$REMOTE_CMD"

SBATCH_ARGS=(
  --parsable
  --job-name="interplab-census-${RUN_ID}"
  --output="slurm/logs/%j_census_${RUN_ID}.out"
  --error="slurm/logs/%j_census_${RUN_ID}.err"
  --time=01:00:00
  --nodes=1
  --ntasks=1
  --cpus-per-task=8
  --mem=0
  --gpus-per-node=h100:4
  --account=aip-chgag196
  --wrap="$WRAP_CMD"
)

SBATCH_LINE="sbatch"
for a in "${SBATCH_ARGS[@]}"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
echo "sbatch command:"
echo "  $SBATCH_LINE"

JOB_ID=$(sbatch "${SBATCH_ARGS[@]}")
echo
echo "Submitted job $JOB_ID"
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_census_${RUN_ID}.out"
echo "Artifact ID:  compare pre/post registry snapshots and inspect the producing A10 outputs; do not use file modification time"
