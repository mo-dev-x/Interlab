#!/bin/bash
# SS12 parameterized launcher (§6.3) for `interplab.jobs.characterize` (SS5).
#
# Usage: bash slurm/launch_characterize.sh <config.yaml> <run_id>
#
# Prints the sbatch command, the log-tail command, and the final-result
# command together (the repository's established submission convention),
# then submits. Resource request is a starting placeholder pending
# calibration on the first real index build (§10 Open Items 2).
set -euo pipefail

CONFIG="${1:?usage: launch_characterize.sh <config.yaml> <run_id>}"
RUN_ID="${2:?usage: launch_characterize.sh <config.yaml> <run_id>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

REMOTE_CMD="module purge && module load python/3.11 arrow && source \"\${INTERPLAB_VENV_DIR:-\$HOME/interplab-venv}/bin/activate\" && cd \"$REPO_ROOT\" && python scripts/characterize.py --config \"$CONFIG\""

SBATCH_ARGS=(
  --parsable
  --job-name="interplab-characterize-${RUN_ID}"
  --output="slurm/logs/%j_characterize_${RUN_ID}.out"
  --error="slurm/logs/%j_characterize_${RUN_ID}.err"
  --time=08:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=64G
  --gpus-per-node=h100:1
  --account=aip-chgag196
  --wrap="$REMOTE_CMD"
)

SBATCH_LINE="sbatch"
for a in "${SBATCH_ARGS[@]}"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
echo "sbatch command:"
echo "  $SBATCH_LINE"

JOB_ID=$(sbatch "${SBATCH_ARGS[@]}")
echo
echo "Submitted job $JOB_ID"
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_characterize_${RUN_ID}.out"
echo "Final result: grep -l '\"stage\": \"characterize\"' registry/run_card/*.json | xargs ls -t | head -1 | xargs cat"
