#!/bin/bash
#SBATCH --job-name=qwen-find-mtlplace
#SBATCH --output=slurm/logs/%j_mtlplace.out
#SBATCH --error=slurm/logs/%j_mtlplace.err
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

mkdir -p slurm/logs results/features_montreal_place

# Purely geographic Montreal probes (landmarks, neighborhoods, climate,
# transit -- no language/bilingualism/politics, unlike the "quebec" concept
# that found 10413). Looking for a cleaner, more place-specific feature than
# 10413, which turned out to be entangled with a broader bilingual/language
# theme cluster (only 1/10 top logit-attribution tokens was literally
# "Montreal"; the rest of the cluster surfaces as language/locale artifacts
# under steering, with no way to flavor code or stay coherent at high scale).
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584 \
    --model_name Qwen/Qwen2.5-14B \
    --concept montreal_place \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_montreal_place

echo "Job finished: $(date)"
