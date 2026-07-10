#!/bin/bash
# SS12 parameterized launcher (§6.3) for `interplab.jobs.train` (SS3).
#
# Usage: bash slurm/launch_train.sh <config.yaml> <run_id>
#
# NOTE: `interplab.jobs.train` / `scripts/train.py` have not been built by
# any work package yet (only the legacy A5 backfill path -- WP2 -- and
# `jobs.backfill_checkpoint` exist today). This launcher is correct,
# ready-to-use SS12 infrastructure per §6.3's explicit four-launcher list,
# targeting the job's expected future location -- the same
# forward-declaration pattern already used for `jobs.steer`'s import-contract
# entry (§1). It will fail at the `python scripts/train.py` step until that
# job lands in a future work package; nothing here should be read as a claim
# that SS3 is complete.
#
# Resource request mirrors the historical (pre-blueprint) train_sae_*.sh
# scripts' successful runs (~14h on a 24h budget); placeholder pending
# recalibration once the real job exists (§10 Open Items 2).
set -euo pipefail

CONFIG="${1:?usage: launch_train.sh <config.yaml> <run_id>}"
RUN_ID="${2:?usage: launch_train.sh <config.yaml> <run_id>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

REMOTE_CMD="module purge && module load python/3.11 arrow && source \"\${INTERPLAB_VENV_DIR:-\$HOME/interplab-venv}/bin/activate\" && cd \"$REPO_ROOT\" && python scripts/train.py --config \"$CONFIG\""

SBATCH_ARGS=(
  --parsable
  --job-name="interplab-train-${RUN_ID}"
  --output="slurm/logs/%j_train_${RUN_ID}.out"
  --error="slurm/logs/%j_train_${RUN_ID}.err"
  --time=20:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=100G
  --gpus-per-node=h100:4
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
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_train_${RUN_ID}.out"
echo "Final result: grep -l '\"stage\": \"train\"' registry/run_card/*.json | xargs ls -t | head -1 | xargs cat"
