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

# Usage: sbatch slurm/survey_features_instruct.sh <sae_checkpoint_path>
SAE_PATH="$1"
if [ -z "$SAE_PATH" ]; then
    echo "Usage: sbatch survey_features_instruct.sh <sae_checkpoint_path>" >&2
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

mkdir -p slurm/logs results/feature_survey_instruct

# Open-ended discovery (scripts/survey_features.py) instead of re-testing
# the specific concepts (poutine, Quebec/Montreal) already known to be hard
# on the base model -- surveys the SAE's actual feature space for anything
# cleanly monosemantic, the way Anthropic found the Golden Gate Bridge
# feature in the first place: by inspecting many features, not by
# searching for one specific predetermined concept.
python scripts/survey_features.py \
    --sae_path "$SAE_PATH" \
    --model_name Qwen/Qwen2.5-14B-Instruct \
    --hook_layer 28 \
    --top_n 150 \
    --out_dir results/feature_survey_instruct

echo "Job finished: $(date)"
