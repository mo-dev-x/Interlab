#!/bin/bash
# ED-7 GPU sbatch wrapper for `interplab.jobs.certify` (SS4, GATE G1) --
# not one of §6.3's four named launchers, but explicitly required by the
# ED-7 correction: certification runs fresh model forwards (ED-5), so
# production checkpoints need a real GPU allocation (tiny-fixture
# certification in CI stays CPU-local).
#
# Usage: bash slurm/launch_certify.sh <config.yaml> <run_id>
#
# Prints the sbatch command, the log-tail command, and the final-result
# command together (the repository's established submission convention),
# then submits. Resource request is calibrated to Tamia's whole-node H100
# policy and the four prior successful certification runs.
set -euo pipefail

CONFIG="${1:?usage: launch_certify.sh <config.yaml> <run_id>}"
RUN_ID="${2:?usage: launch_certify.sh <config.yaml> <run_id>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

REMOTE_CMD="module purge && module load python/3.11 arrow && source \"\${INTERPLAB_VENV_DIR:-\$HOME/interplab-venv}/bin/activate\" && cd \"$REPO_ROOT\" && python scripts/certify.py --config \"$CONFIG\""
# Tamia's generated `sbatch --wrap` script runs under `/bin/sh`, so the
# module/source-heavy remote payload must cross that boundary explicitly via
# login Bash without submit-host expansion of the remote venv fallback.
printf -v WRAP_CMD 'bash -lc %q' "$REMOTE_CMD"

SBATCH_ARGS=(
  --parsable
  --job-name="interplab-certify-${RUN_ID}"
  --output="slurm/logs/%j_certify_${RUN_ID}.out"
  --error="slurm/logs/%j_certify_${RUN_ID}.err"
  --time=02:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=0
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
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_certify_${RUN_ID}.out"
echo "Final result: grep -l '\"stage\": \"certify\"' registry/run_card/*.json | xargs ls -t | head -1 | xargs cat"
