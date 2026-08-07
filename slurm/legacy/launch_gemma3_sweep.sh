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
# No `--wrap`: the actual job payload is slurm/legacy/gemma3_sweep_payload.sh,
# a real file SLURM executes directly, avoiding the nested `bash -lc "..."`
# quoting this launcher used before fix 3 (D2.1 review).
#
# Usage: bash slurm/legacy/launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra gemma3_sweep.py args...]
#   model_snapshot_path / sae_snapshot_path: local filesystem paths to the
#     pre-staged snapshots under /scratch/y/yazid/hf_cache (staged by the
#     other Engineer) -- never a repo_id.
set -euo pipefail

MODEL_PATH="${1:?usage: launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
SAE_PATH="${2:?usage: launch_gemma3_sweep.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
shift 2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD="$REPO_ROOT/slurm/legacy/gemma3_sweep_payload.sh"

# ABSOLUTE, not "slurm/logs/...": a relative --output/--error is resolved
# by Slurm against WorkDir at submission time, not the repo -- if that
# directory doesn't exist on whatever checkout WorkDir happens to be, the
# log is written NOWHERE, no error, no warning (job 398667's missing log).
# ~/interplab_logs/ is the same absolute location Engineer 3's jobs already
# use, so logs from every job in this project land in one tailable place.
LOG_DIR="$HOME/interplab_logs"
mkdir -p "$LOG_DIR"

RUN_ID="$(date +%Y%m%d_%H%M%S)"

# 8x prompts (5 -> 8, D2.1 fix 1) brings the matrix to 8 x 2 x 108 + 8 =
# 1736 records, up from 1085 at the original --time=08:00:00 estimate --
# and that original estimate was itself an unbenchmarked placeholder, not
# a measured rate. No real generation has been timed on this instrument
# yet, so this is a deliberately generous, disclosed-as-unbenchmarked
# budget: Tamia has no allocation quota, so an over-request only costs
# queue position, while a job killed at the wall-time boundary loses the
# whole run. Recalibrate against the first real run's actual throughput.
SBATCH_ARGS=(
  --parsable
  --job-name="gemma3-sweep-${RUN_ID}"
  --output="${LOG_DIR}/%j_gemma3_sweep_${RUN_ID}.out"
  --error="${LOG_DIR}/%j_gemma3_sweep_${RUN_ID}.err"
  --time=24:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=32 --mem=0
  --gres=gpu:h100:4
  --account=aip-chgag196
)

SBATCH_LINE="sbatch"
for a in "${SBATCH_ARGS[@]}"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$PAYLOAD") $(printf '%q' "$MODEL_PATH") $(printf '%q' "$SAE_PATH")"
for a in "$@"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
echo "sbatch command:"
echo "  $SBATCH_LINE"

JOB_ID=$(sbatch "${SBATCH_ARGS[@]}" "$PAYLOAD" "$MODEL_PATH" "$SAE_PATH" "$@")
echo
echo "Submitted job $JOB_ID"
echo "Log tail:     tail -f ${LOG_DIR}/${JOB_ID}_gemma3_sweep_${RUN_ID}.out"
echo "Module-identity report (check this FIRST): cat results/gemma3_sweep/module_identity_report.json"
echo "Final records: cat results/gemma3_sweep/records.jsonl"
