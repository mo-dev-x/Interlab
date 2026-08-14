#!/bin/bash
# Section 7: the scheduled, production entry point for the final-pairing
# matched-configuration job (primary grids -> automatic backup trigger ->
# conditional matched backup grids -> causal generation, both directions,
# all five doses, both configurations that actually ran).
#
# Submit from the extracted repo root on Tamia scratch (a git-archive
# extraction, no .git -- see discovery_preflight.py's own module docstring
# for why REPO_ROOT is derived from --prompt-sets etc. rather than __file__
# at that layer; this script derives it from its OWN location instead,
# which is valid here since it is never git-archived to a different
# relative layout on its own):
#
#   sbatch slurm/final_pairing_matched_configuration_job.sbatch
#
# Real precedent for account/time/resources/HF-cache layout: this
# project's own prior successful Tamia jobs against these exact two
# pairings (results/final_pairing/job_406092/fp_accept.sbatch,
# job_407008/fp_gemma.sbatch). --shortlist-size 20 is this project's own
# already-documented value (docs/final_pairing_concept_discovery_packet.md),
# not invented here.
#
# --model-path/--sae-path below assume the exact HF snapshots named have
# already been materialised on the LOGIN node at the pinned revisions
# (protocols/final_pairing/v1/scientific_config_identity.json
# "runtime_loading.required_procedure") -- staging weights is a separate,
# standing operational precondition this script does not perform (Tamia
# compute nodes have no outbound internet; HF_HUB_OFFLINE=1 below refuses
# to fall back to a network fetch).
#
#SBATCH --job-name=final-pairing-matched-config
#SBATCH --account=aip-chgag196
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:h100:4
#SBATCH --time=03:00:00
#SBATCH --output=results/final_pairing/final_pairing_matched_configuration_job_%j.out

set -uo pipefail

module load StdEnv/2023 python/3.11 arrow/25.0.0
source ~/sprint-venv/bin/activate

export HF_HOME=/scratch/y/yazid/hf_cache
export HF_HUB_CACHE=/scratch/y/yazid/hf_cache/hub
export HF_HUB_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

JOB_ID="$SLURM_JOB_ID"
BASE="/scratch/y/yazid/final_pairing/$JOB_ID"
mkdir -p "$BASE/rendered_configs" "$BASE/preflight"

echo "SLURM_JOB_ID=$JOB_ID  NODE=$(hostname)  REPO_ROOT=$REPO_ROOT"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# ---------------------------------------------------------------------------
# Resolve the exact transfer-manifest source commit -- this checkout has no
# .git at all (a git-archive extraction); transfer_manifest.json's own
# recorded source_commit is the one fact it can verify against. Reuses the
# real, already-tested discovery_preflight.resolve_source_commit rather than
# re-deriving this logic a second time.
# ---------------------------------------------------------------------------
SOURCE_COMMIT="$(python -c "
import sys
sys.path.insert(0, 'scripts/final_pairing')
import discovery_preflight as p
from pathlib import Path
print(p.resolve_source_commit(Path('.')))
")"
if [ -z "$SOURCE_COMMIT" ]; then
  echo "Could not resolve the transfer-manifest source commit -- refusing to proceed."
  exit 1
fi
echo "SOURCE_COMMIT=$SOURCE_COMMIT"

JOB_START_EPOCH="$(date +%s)"
# 2h55m from job start -- 5 minutes of margin before the 3h allocation ends,
# for the preflight, both grid phases, and orderly shutdown.
JOB_DEADLINE_EPOCH=$(( JOB_START_EPOCH + 10500 ))

# ---------------------------------------------------------------------------
# Render the 8 committed lane-config TEMPLATES (configs/final_pairing/*.json)
# into this run's real values -- SLURM_JOB_ID/SOURCE_COMMIT/
# JOB_DEADLINE_EPOCH_SECONDS/GENERATION_SCRIPT_PATH are not known until now;
# every OTHER field in each template is already a concrete, frozen, ratified
# value (model/SAE identity, layer, shortlist size) with no engineering
# placeholder. GENERATION_SCRIPT_PATH must be the exact absolute path
# final_concept_discovery_dual_gpu_job.GENERATION_SCRIPT resolves to at
# runtime (SCRIPT_DIR = Path(__file__).resolve().parent there) -- a lane's
# target_script is compared to that constant by equality
# (validate_generation_lane_argv), so a relative or differently-resolved
# path would silently skip that check rather than fail loudly.
# ---------------------------------------------------------------------------
GENERATION_SCRIPT_PATH="$REPO_ROOT/scripts/final_pairing/final_pairing_one_allocation_generation.py"
render() {
  sed \
    -e "s/@@SLURM_JOB_ID@@/$JOB_ID/g" \
    -e "s/@@SOURCE_COMMIT@@/$SOURCE_COMMIT/g" \
    -e "s/@@JOB_DEADLINE_EPOCH_SECONDS@@/$JOB_DEADLINE_EPOCH/g" \
    -e "s#@@GENERATION_SCRIPT_PATH@@#$GENERATION_SCRIPT_PATH#g" \
    "configs/final_pairing/$1.json" > "$BASE/rendered_configs/$1.json"
}
for cfg in primary_gemma_grid primary_qwen_grid backup_gemma_grid backup_qwen_grid \
           primary_gemma_generation primary_qwen_generation backup_gemma_generation backup_qwen_generation; do
  render "$cfg"
done

TRIGGER_INPUTS="$BASE/rendered_configs/trigger_inputs.json"
cat > "$TRIGGER_INPUTS" <<EOF
{
  "note": "The backup-trigger boolean is computed automatically from --primary-gemma-grid-path/--primary-qwen-grid-path via compute_trigger_from_grid_outputs (protocols/final_pairing/v1/backup_trigger.json, commit 125b1d3). This file is retained verbatim for audit only and is never itself used to compute the boolean.",
  "backup_trigger_protocol_path": "protocols/final_pairing/v1/backup_trigger.json",
  "backup_trigger_protocol_commit": "125b1d3e825f0e6cc83c20ba54ef2c345e4372f9",
  "slurm_job_id": "$JOB_ID",
  "source_commit": "$SOURCE_COMMIT"
}
EOF

# ---------------------------------------------------------------------------
# The frozen eight-flag LA-B preflight -- run explicitly, visibly, BEFORE
# either CUDA child loads anything. (final_concept_discovery_dual_gpu_job.
# default_preflight_runner re-runs this same preflight automatically,
# internally, before every lane-group launch below -- this explicit gate
# additionally stops the job early, before any GPU allocation time is spent,
# on the very first failure.)
# ---------------------------------------------------------------------------
python scripts/final_pairing/discovery_preflight.py \
  --prompt-sets prompts/final_pairing/v1/prompt_sets.jsonl \
  --prompt-metadata prompts/final_pairing/v1/metadata.json \
  --backup-trigger protocols/final_pairing/v1/backup_trigger.json \
  --pairing-config protocols/final_pairing/v1/scientific_config_identity.json \
  --gemma-output-root "$BASE/preflight/gemma" \
  --qwen-output-root "$BASE/preflight/qwen" \
  --sentinel-dir "$BASE/preflight/sentinel" \
  --report "$BASE/preflight/report.json"
PREFLIGHT_EXIT=$?
echo "PREFLIGHT_EXIT=$PREFLIGHT_EXIT"
cat "$BASE/preflight/report.json"
if [ $PREFLIGHT_EXIT -ne 0 ]; then
  echo "LA-B preflight did not pass -- refusing to launch either CUDA child."
  exit $PREFLIGHT_EXIT
fi

# ---------------------------------------------------------------------------
# Primary grids -> automatic backup trigger -> conditional matched backup
# grids -> causal generation (both configurations that actually ran, both
# directions, all five doses). Qwen (physical GPU 1) must load and emit
# READY before Gemma (physical GPU 0) begins loading -- DualGpuOrchestrator.
# launch_staggered (STAGGER_LEAD_LANE="qwen") enforces this for every lane
# group below; this script never calls launch_all, which would load both
# concurrently. No Lodestar/judging/spot-reading/selection import is
# reachable from this entry point (test_stamp_manifest_with_selection_is_
# unreachable_from_any_gpu_entry_point and the module-scope AST scans in
# each GPU-side module's own test suite already prove this structurally).
# ---------------------------------------------------------------------------
python scripts/final_pairing/final_concept_discovery_matched_configuration_job.py \
  --primary-gemma-config "$BASE/rendered_configs/primary_gemma_grid.json" \
  --primary-qwen-config "$BASE/rendered_configs/primary_qwen_grid.json" \
  --backup-gemma-config "$BASE/rendered_configs/backup_gemma_grid.json" \
  --backup-qwen-config "$BASE/rendered_configs/backup_qwen_grid.json" \
  --trigger-inputs-json "$TRIGGER_INPUTS" \
  --primary-gemma-grid-path "$BASE/primary/gemma/grid/out/grid.json" \
  --primary-qwen-grid-path "$BASE/primary/qwen/grid/out/grid.json" \
  --concept-id formal_register --concept-id cheese --concept-id chess --concept-id jazz \
  --concept-id courtroom --concept-id astronomy --concept-id volcanic_activity --concept-id sailing \
  --concept-id clinical_examination --concept-id mountaineering --concept-id desert \
  --concept-id winter_snow --concept-id beekeeping --concept-id political_framing \
  --job-result-path "$BASE/job_result.json" \
  --primary-gemma-generation-config "$BASE/rendered_configs/primary_gemma_generation.json" \
  --primary-qwen-generation-config "$BASE/rendered_configs/primary_qwen_generation.json" \
  --backup-gemma-generation-config "$BASE/rendered_configs/backup_gemma_generation.json" \
  --backup-qwen-generation-config "$BASE/rendered_configs/backup_qwen_generation.json" \
  --job-start-time-epoch-seconds "$JOB_START_EPOCH" \
  --job-time-limit-seconds 10800 \
  --gpu-ids 0,1 \
  --min-free-vram-bytes 64424509440
JOB_EXIT=$?
echo "JOB_EXIT=$JOB_EXIT"
echo "===== job_result.json ====="
cat "$BASE/job_result.json"
echo "===== PEAK GPU MEMORY ====="
nvidia-smi --query-gpu=index,memory.used --format=csv
exit $JOB_EXIT
