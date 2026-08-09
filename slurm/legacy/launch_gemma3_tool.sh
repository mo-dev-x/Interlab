#!/bin/bash
# PI deliverable #4 launcher for scripts/legacy/gemma3_tool.py -- the
# interactive Gradio steer/ablate demo. Unlike gemma3_sweep/necessity
# (sbatch batch jobs), this needs an INTERACTIVE allocation: the operator
# stays attached to see Gradio's own log lines and to Ctrl-C when the
# demo session ends.
#
# salloc's own spawned command runs on the node salloc was invoked from
# (the login node), NOT on the allocated compute node -- srun is what
# actually executes a step on the allocated node inside an salloc
# allocation. So the single launch command below is
#   salloc <resource flags> srun --pty <payload> <args>
# not `salloc <payload>` alone.
#
# No `--wrap`, no nested `bash -lc "..."` quoting: srun's command is the
# real payload file (gemma3_tool_payload.sh), same discipline as
# gemma3_sweep's payload-script fix.
#
# Usage: bash slurm/legacy/launch_gemma3_tool.sh <model_snapshot_path> <sae_snapshot_path> [extra gemma3_tool.py args...]
set -euo pipefail

MODEL_PATH="${1:?usage: launch_gemma3_tool.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
SAE_PATH="${2:?usage: launch_gemma3_tool.sh <model_snapshot_path> <sae_snapshot_path> [extra args...]}"
shift 2

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD="$REPO_ROOT/slurm/legacy/gemma3_tool_payload.sh"

# Whole-node GPU, --mem=0, same as every other Tamia job in this project
# (gemma3_sweep_payload.sh) -- Tamia has no allocation quota, so an
# over-request only costs queue position, and the tool needs exactly the
# same offline load path the sweep already proved works at this shape.
SALLOC_ARGS=(
  --job-name="gemma3-tool-interactive"
  --time=04:00:00
  --nodes=1 --ntasks=1 --cpus-per-task=32 --mem=0
  --gres=gpu:h100:4
  --account=aip-chgag196
)

CMD_LINE="salloc"
for a in "${SALLOC_ARGS[@]}"; do CMD_LINE="$CMD_LINE $(printf '%q' "$a")"; done
CMD_LINE="$CMD_LINE srun --pty $(printf '%q' "$PAYLOAD") $(printf '%q' "$MODEL_PATH") $(printf '%q' "$SAE_PATH")"
for a in "$@"; do CMD_LINE="$CMD_LINE $(printf '%q' "$a")"; done
echo "salloc command:"
echo "  $CMD_LINE"
echo
echo "Once granted, the payload prints the allocated node's hostname --"
echo "use it in the SSH port-forward command in slurm/legacy/README_gemma3_tool.md."
echo

exec salloc "${SALLOC_ARGS[@]}" srun --pty "$PAYLOAD" "$MODEL_PATH" "$SAE_PATH" "$@"
