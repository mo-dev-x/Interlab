#!/bin/bash
#SBATCH --job-name=qwen-find-mtlplace-v3
#SBATCH --output=slurm/logs/%j_mtlplace_v3.out
#SBATCH --error=slurm/logs/%j_mtlplace_v3.err
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

mkdir -p slurm/logs results/features_montreal_place_v3

# Same montreal_place probe set as the v2-checkpoint search
# (slurm/find_features_montreal_place.sh), re-run against the v3 SAE: same
# 32x dict-size increase that disentangled French-culture/Sandwich on v2,
# but trained at hook_layer 24 (where 10413 lives) instead of 28. Checking
# whether the extra capacity, applied at the right layer this time, finally
# splits a purely geographic "Montreal-the-place" feature away from the
# bilingual/language cluster 10413 was entangled with on the 1x checkpoint.
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/085jxgqu/final_400001024 \
    --model_name Qwen/Qwen2.5-14B \
    --concept montreal_place \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_montreal_place_v3

echo "Job finished: $(date)"
