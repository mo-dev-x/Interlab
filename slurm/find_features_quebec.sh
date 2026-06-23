#!/bin/bash
#SBATCH --job-name=qwen-find-quebec
#SBATCH --output=slurm/logs/%j_quebec.out
#SBATCH --error=slurm/logs/%j_quebec.err
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

mkdir -p slurm/logs results/features_quebec_v2

# "quebec" was already in PROBES (added earlier for the multilingual
# objective) but never run through the candidate-search path until
# today's --concept generalization. Quebec/Montreal are the actual
# target geography for this whole project, more directly relevant than
# the generic "Las Vegas" result from the celine_dion search.
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/alhjs2qg/final_400001024 \
    --model_name Qwen/Qwen2.5-14B \
    --concept quebec \
    --hook_layer 28 \
    --top_k 20 \
    --out_dir results/features_quebec_v2

echo "Job finished: $(date)"
