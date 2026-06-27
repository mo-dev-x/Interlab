#!/bin/bash
#SBATCH --job-name=qwen-find-instruct-all
#SBATCH --output=slurm/logs/%j_instruct_all.out
#SBATCH --error=slurm/logs/%j_instruct_all.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

# Usage: sbatch slurm/find_features_instruct_all.sh <sae_checkpoint_path>
# e.g.:  sbatch slurm/find_features_instruct_all.sh results/sae_checkpoints/<id>/final_400001024
SAE_PATH="$1"
if [ -z "$SAE_PATH" ]; then
    echo "Usage: sbatch find_features_instruct_all.sh <sae_checkpoint_path>" >&2
    exit 1
fi

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "SAE checkpoint: $SAE_PATH"

module purge
module load python/3.11 arrow
source ~/sae-interp/bin/activate

cd $SLURM_SUBMIT_DIR

export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache
export HF_DATASETS_CACHE=$SCRATCH/hf_cache
export HUGGINGFACE_HUB_CACHE=$SCRATCH/hf_cache
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DATASETS_OFFLINE=1

mkdir -p slurm/logs results/features_instruct_all

# Runs every concept already in PROBES (poutine, world_cup, couscous,
# quebec, celine_dion, montreal_place, quebec_geographic) against the new
# SAE trained directly on Qwen2.5-14B-Instruct's own activations, loading
# the model and SAE exactly once and reusing them across all seven --
# instead of one ad-hoc single-concept search at a time, this produces a
# full comparison table in one job: which concepts get clean monosemantic
# features on THIS checkpoint, directly comparable against every prior
# base-model find_features run (sections 1-23 of the experiment log).
python scripts/find_features.py \
    --sae_path "$SAE_PATH" \
    --model_name Qwen/Qwen2.5-14B-Instruct \
    --concept all \
    --hook_layer 28 \
    --top_k 20 \
    --out_dir results/features_instruct_all

echo "Job finished: $(date)"
