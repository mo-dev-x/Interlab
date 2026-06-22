#!/bin/bash
#SBATCH --job-name=qwen-find-features-final
#SBATCH --output=slurm/logs/%j_features_final.out
#SBATCH --error=slurm/logs/%j_features_final.err
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

mkdir -p slurm/logs results/features_final_checkpoint results/plots

# Using the recovered, properly-completed final checkpoint (200,003,584
# tokens) -- not the partial 166.67M one every prior feature-search/steering
# attempt used. Feature indices are not guaranteed stable across the extra
# ~33M tokens of training, so this is a fresh search, not a re-run with the
# old feature_ids.
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584 \
    --model_name Qwen/Qwen2.5-14B \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_final_checkpoint

echo "Job finished: $(date)"
