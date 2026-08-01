#!/bin/bash
# SS12 parameterized launcher (§6.3) for `interplab.jobs.steer` (SS7/SS8, GATE G3 consumer).
#
# Usage: bash slurm/launch_steer.sh <config.yaml> <run_id>
#
# NOTE: `interplab.jobs.steer` / `scripts/steer.py` are present; this
# launcher is the SS12 entry point for that implemented job. The resource
# request below is still a starting placeholder inherited from the historical
# steering sweeps and should be recalibrated against real production runs
# before relying on it as a tuned cluster profile.
#
# Resource request mirrors the historical (pre-blueprint) single-config
# steering sweep scripts; placeholder pending recalibration against real
# production runs (§10 Open Items 2). Multi-config sweeps use the existing
# N-node `srun --exclusive` pattern (§6.3) -- out of scope for this
# single-config launcher.
set -euo pipefail

CONFIG="${1:?usage: launch_steer.sh <config.yaml> <run_id>}"
RUN_ID="${2:?usage: launch_steer.sh <config.yaml> <run_id>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

REMOTE_CMD="module purge && module load python/3.11 arrow && source \"\${INTERPLAB_VENV_DIR:-\$HOME/interplab-venv}/bin/activate\" && cd \"$REPO_ROOT\" && python scripts/steer.py --config \"$CONFIG\""

SBATCH_ARGS=(
  --parsable
  --job-name="interplab-steer-${RUN_ID}"
  --output="slurm/logs/%j_steer_${RUN_ID}.out"
  --error="slurm/logs/%j_steer_${RUN_ID}.err"
  --time=02:30:00
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
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_steer_${RUN_ID}.out"
echo "Final result: grep -l '\"stage\": \"steer\"' registry/run_card/*.json | xargs ls -t | head -1 | xargs cat"
