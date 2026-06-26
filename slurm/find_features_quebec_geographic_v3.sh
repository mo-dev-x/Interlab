#!/bin/bash
#SBATCH --job-name=qwen-find-qcgeo-v3
#SBATCH --output=slurm/logs/%j_qcgeo_v3.out
#SBATCH --error=slurm/logs/%j_qcgeo_v3.err
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

mkdir -p slurm/logs results/features_quebec_geographic_v3

# Quebec-the-province probes (geography/administration/economy: St. Lawrence
# River, Laurentians, James Bay, hydro dams, Gaspe, boreal forest, winters --
# see PROBES["quebec_geographic"] in find_features.py), deliberately excluding
# the French-language/bilingualism/sovereignty content that made the original
# "quebec" concept entangle feature 10413, and deliberately NOT scoped down to
# Montreal city landmarks (the "montreal_place" probe's mistake -- that target
# was never the actual goal). Run against the v3 (layer 24, 32x dict) SAE to
# check whether the extra capacity isolates a province-specific feature.
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/085jxgqu/final_400001024 \
    --model_name Qwen/Qwen2.5-14B \
    --concept quebec_geographic \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_quebec_geographic_v3

echo "Job finished: $(date)"
