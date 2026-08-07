#!/bin/bash
# Launcher for scripts/legacy/gemma3_necessity.py -- out-of-chain, mirrors
# slurm/legacy/launch_gemma3_sweep.sh's (already-fixed) style, but is an
# independent job so it can run in parallel with the sweep and neither one
# needs to touch the other.
#
# Whole-node GPU request even though this job is much lighter than the
# sweep (up to ~576 short forward passes, no generation, no sampling) --
# every Tamia job in this project is whole-node (h100:4, --mem=0); Tamia
# has no allocation quota, so matching that convention costs only queue
# position, never a CPU-carve-out exception.
#
# No `--wrap`: the actual job payload is
# slurm/legacy/gemma3_necessity_payload.sh, a real file SLURM executes
# directly.
#
# Usage: bash slurm/legacy/launch_gemma3_necessity.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra gemma3_necessity.py args...]
#   model_snapshot_path / sae_snapshot_path: local filesystem paths to the
#     pre-staged snapshots under /scratch/y/yazid/hf_cache -- never a repo_id.
#   snippets_file: local JSON file mapping each of the 9 feature indices to
#     its own top-16 activating snippets (compute nodes are offline; this
#     is never fetched from Neuronpedia here).
#
# Do not submit this against real weights until the sweep's module-identity
# gate (results/gemma3_sweep/module_identity_report.json) has reported
# clean -- both jobs hook the same instrument, and racing them on the same
# as-yet-unvalidated finding is the thing to avoid, not the parallelism
# itself.
set -euo pipefail

MODEL_PATH="${1:?usage: launch_gemma3_necessity.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
SAE_PATH="${2:?usage: launch_gemma3_necessity.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
SNIPPETS_FILE="${3:?usage: launch_gemma3_necessity.sh <model_snapshot_path> <sae_snapshot_path> <snippets_file> [extra args...]}"
shift 3

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD="$REPO_ROOT/slurm/legacy/gemma3_necessity_payload.sh"
mkdir -p "$REPO_ROOT/slurm/logs"

RUN_ID="$(date +%Y%m%d_%H%M%S)"

# Up to 288 short forward passes (144 own-text cells x 2-3 passes each,
# plus up to 144 within-feature-control candidates x 1-2 passes each) on
# short snippets -- no generation, no sampling. Unbenchmarked but should be
# well under an hour; 2h is a deliberately generous, disclosed estimate
# (Tamia has no allocation quota, so over-requesting only costs queue
# position). Recalibrate against the first real run's actual throughput.
SBATCH_ARGS=(
  --parsable
  --job-name="gemma3-necessity-${RUN_ID}"
  --output="slurm/logs/%j_gemma3_necessity_${RUN_ID}.out"
  --error="slurm/logs/%j_gemma3_necessity_${RUN_ID}.err"
  --time=02:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=32 --mem=0
  --gres=gpu:h100:4
  --account=aip-chgag196
)

SBATCH_LINE="sbatch"
for a in "${SBATCH_ARGS[@]}"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$PAYLOAD") $(printf '%q' "$MODEL_PATH") $(printf '%q' "$SAE_PATH") $(printf '%q' "$SNIPPETS_FILE")"
for a in "$@"; do SBATCH_LINE="$SBATCH_LINE $(printf '%q' "$a")"; done
echo "sbatch command:"
echo "  $SBATCH_LINE"

JOB_ID=$(sbatch "${SBATCH_ARGS[@]}" "$PAYLOAD" "$MODEL_PATH" "$SAE_PATH" "$SNIPPETS_FILE" "$@")
echo
echo "Submitted job $JOB_ID"
echo "Log tail:     tail -f slurm/logs/${JOB_ID}_gemma3_necessity_${RUN_ID}.out"
echo "Module-identity report (check this FIRST): cat results/gemma3_necessity/necessity_module_identity_report.json"
echo "Final records: cat results/gemma3_necessity/necessity_records.jsonl"
