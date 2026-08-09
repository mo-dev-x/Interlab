#!/bin/bash
# PI deliverable #4 payload for scripts/legacy/gemma3_tool.py -- executed
# by an `srun --pty` step inside an salloc allocation (see
# launch_gemma3_tool.sh), never by sbatch. A real file, not `--wrap` and
# not a nested `bash -lc "..."` string, per the same discipline
# gemma3_sweep_payload.sh established (job 398628's spool-path failure).
#
# Invoked by slurm/legacy/launch_gemma3_tool.sh via:
#   salloc <salloc-flags> srun --pty gemma3_tool_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra gemma3_tool.py args...]
set -euo pipefail

MODEL_PATH="${1:?usage: gemma3_tool_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
SAE_PATH="${2:?usage: gemma3_tool_payload.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
shift 2

# SLURM_SUBMIT_DIR (not BASH_SOURCE[0]) for the same reason
# gemma3_sweep_payload.sh uses it: the portable source of truth for "where
# was this launched from," regardless of how Slurm staged the script.
REPO_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is unset -- refusing to guess the repo root}"
cd "$REPO_ROOT"

module purge
module load StdEnv/2023 python/3.11 arrow/25.0.0
source "${SPRINT_VENV_DIR:-$HOME/sprint-venv}/bin/activate"

# Same credential defence-in-depth as gemma3_sweep_payload.sh: an
# interactive allocation should never carry HF_TOKEN, and this tool never
# needs one (constraint 3 -- the HF token guard elsewhere in this project
# is SLURM_JOB_ID-conditional).
unset HF_TOKEN
export HF_HUB_OFFLINE=1
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

echo "=================================================================="
echo "gemma3_tool running on node: $(hostname)"
echo "Use that node name in the SSH port-forward command (see"
echo "slurm/legacy/README_gemma3_tool.md)."
echo "=================================================================="

python scripts/legacy/gemma3_tool.py \
  --model-path "$MODEL_PATH" \
  --sae-path "$SAE_PATH" \
  --server-name 127.0.0.1 \
  --server-port 7860 \
  "$@"
