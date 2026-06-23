#!/bin/bash
#SBATCH --job-name=qwen-find-quebec24
#SBATCH --output=slurm/logs/%j_quebec24.out
#SBATCH --error=slurm/logs/%j_quebec24.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"

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

mkdir -p slurm/logs results/features_quebec_layer24

# Re-checking "quebec" concept on the original/recovered checkpoint
# (16x dict, layer 24) instead of v2 (32x dict, layer 28) -- feature
# 10413 ("Montreal") was characterized earlier on this exact checkpoint
# during the poutine search, so layer 24 may represent Quebec/Montreal
# more cleanly than layer 28 does.
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584 \
    --model_name Qwen/Qwen2.5-14B \
    --concept quebec \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_quebec_layer24

echo "Job finished: $(date)"
