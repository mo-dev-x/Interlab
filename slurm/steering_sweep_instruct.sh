#!/bin/bash
#SBATCH --job-name=qwen-steer-sweep
#SBATCH --output=slurm/logs/%j_steer_sweep.out
#SBATCH --error=slurm/logs/%j_steer_sweep.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

# Usage: sbatch slurm/steering_sweep_instruct.sh <feature_id> <output_name> [random_feature_id]
FEATURE_ID="$1"
OUTPUT_NAME="$2"
RANDOM_FEATURE_ID="${3:-1}"
if [ -z "$FEATURE_ID" ] || [ -z "$OUTPUT_NAME" ]; then
    echo "Usage: sbatch steering_sweep_instruct.sh <feature_id> <output_name> [random_feature_id]" >&2
    exit 1
fi

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
echo "Feature: $FEATURE_ID  Output: $OUTPUT_NAME  Random control: $RANDOM_FEATURE_ID"

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

mkdir -p slurm/logs "results/steering_sweep_instruct/$OUTPUT_NAME"

# Generic single-feature scale sweep on the instruct model + chat template,
# using the SAE trained directly on Qwen2.5-14B-Instruct's own activations
# (results/sae_checkpoints/rwu04lpb) -- the first sweep where both the
# response-format gap (section 24) and the SAE-transfer gap are addressed
# at once. --mode steer only: ablation's "necessary for X" framing doesn't
# generalize to arbitrary discovered features the way it did for poutine's
# dedicated concept prompts. Scales chosen to bracket the manually-tested
# scale=80 sweet spot on both sides.
python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/rwu04lpb/final_400001024 \
    --model_name Qwen/Qwen2.5-14B-Instruct \
    --chat_template \
    --feature_id "$FEATURE_ID" \
    --random_feature_id "$RANDOM_FEATURE_ID" \
    --hook_layer 28 \
    --mode steer \
    --scales 40 60 80 100 120 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --prompts "Who are you?" "Tell me about your day." "What's a good recipe for pancakes?" "Can you help me write a python script to calculate the area of a triangle?" "What's a good destination for a nice vacation?" "What is the meaning of life?" "Explain how a car engine works." "What advice would you give to someone starting a new career?" \
    --out_dir "results/steering_sweep_instruct/$OUTPUT_NAME"

echo "Job finished: $(date)"
