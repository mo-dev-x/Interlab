#!/bin/bash
#SBATCH --job-name=qwen-survey-instruct
#SBATCH --output=slurm/logs/%j_survey_instruct.out
#SBATCH --error=slurm/logs/%j_survey_instruct.err
#SBATCH --time=00:45:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

# Usage: sbatch slurm/survey_features_instruct.sh <sae_checkpoint_path> [hook_layer] [out_dir]
SAE_PATH="$1"
HOOK_LAYER="${2:-28}"
OUT_DIR="${3:-results/feature_survey_instruct}"
if [ -z "$SAE_PATH" ]; then
    echo "Usage: sbatch survey_features_instruct.sh <sae_checkpoint_path> [hook_layer] [out_dir]" >&2
    exit 1
fi

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "SAE checkpoint: $SAE_PATH  Hook layer: $HOOK_LAYER  Out dir: $OUT_DIR"

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

mkdir -p slurm/logs "$OUT_DIR"

python scripts/survey_features.py \
    --sae_path "$SAE_PATH" \
    --model_name Qwen/Qwen2.5-14B-Instruct \
    --hook_layer "$HOOK_LAYER" \
    --top_n 150 \
    --out_dir "$OUT_DIR"

echo "Job finished: $(date)"
