#!/bin/bash
# D2.1 launcher for scripts/legacy/gemma3_sweep.py -- out-of-chain, mirrors
# the style of slurm/launch_steer.sh but is NOT one of the certified
# launchers (scripts/legacy/ is outside the certification chain by PI
# directive, and this file lives in slurm/legacy/ to match).
#
# ONE whole-node fan-out over the full 9-feature x 6-dose x 2-mode grid --
# never many small jobs. Tamia has no allocation quota; resubmit only costs
# queue position.
#
# OFFLINE IS MANDATORY (job 397854 died on exactly this): compute nodes
# have no outbound internet. HF_HUB_OFFLINE=1 is exported in the remote
# payload itself, not assumed from the submitting shell. arrow/25.0.0 MUST
# load before the venv activates -- non-negotiable, per the sprint-venv
# build note.
#
# Usage: bash slurm/legacy/launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra gemma3_sweep.py args...]
#   model_snapshot_path / sae_snapshot_path: local filesystem paths to the
#     pre-staged snapshots under /scratch/y/yazid/hf_cache (staged by the
#     other Engineer) -- never a repo_id.
set -euo pipefail

MODEL_PATH="${1:?usage: launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
SAE_PATH="${2:?usage: launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
shift 2
EXTRA_ARGS=("$@")

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p "$REPO_ROOT/slurm/logs"

RUN_ID="$(date +%Y%m%d_%H%M%S)"

REMOTE_CMD="module purge && module load StdEnv/2023 python/3.11 arrow/25.0.0 && source \"\${SPRINT_VENV_DIR:-\$HOME/sprint-venv}/bin/activate\" && export HF_HUB_OFFLINE=1 && cd \"$REPO_ROOT\" && python scripts/legacy/gemma3_sweep.py --model-path \"$MODEL_PATH\" --sae-path \"$SAE_PATH\" --out-dir results/gemma3_sweep --device cuda --dtype bfloat16 $(printf '%q ' "${EXTRA_ARGS[@]}")"
# Tamia's generated `sbatch --wrap` script runs under `/bin/sh`, so the
# module/source-heavy remote payload must cross that boundary explicitly
# via login Bash without submit-host expansion (same reasoning as
# launch_steer.sh's REMOTE_CMD).
printf -v WRAP_CMD 'bash -lc %q' "$REMOTE_CMD"

SBATCH_ARGS=(
  --parsable
  --job-name="gemma3-sweep-${RUN_ID}"
  --output="slurm/logs/%j_gemma3_sweep_${RUN_ID}.out"
  --error="slurm/logs/%j_gemma3_sweep_${RUN_ID}.err"
  --time=08:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=32 --mem=0
  --gres=gpu:h100:4
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
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_gemma3_sweep_${RUN_ID}.out"
echo "Final result: ls -t results/gemma3_sweep/*.json | head -1 | xargs cat"
