#!/bin/bash
#SBATCH --job-name=qwen-steering-v2combo
#SBATCH --output=slurm/logs/%j_v2combo.out
#SBATCH --error=slurm/logs/%j_v2combo.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=160G
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

mkdir -p slurm/logs results/steering_v2_combo_french results/steering_v2_combo_served

CKPT=results/sae_checkpoints/alhjs2qg/final_400001024

# Attempt 8's winning structure was "dish/recipe signal" + "geographic
# anchor" (65223 recipe + 10413 Montreal). On the v2 checkpoint, 96339
# (fries) is the only real food/ingredient signal we have. Testing two
# candidate anchors in parallel:

# GPU 0: fries + French/France (79438) -- geographic/cultural anchor,
# closest analog to Montreal's role, even though it's the wrong specific
# country (France vs Quebec/Canada).
CUDA_VISIBLE_DEVICES=0 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 96339 79438 \
    --random_feature_id 1 \
    --hook_layer 28 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_v2_combo_french \
    > slurm/logs/${SLURM_JOB_ID}_french.out 2> slurm/logs/${SLURM_JOB_ID}_french.err &

# GPU 1: fries + served/joints (154756) -- restaurant/serving-context
# anchor instead of a geographic one.
CUDA_VISIBLE_DEVICES=1 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 96339 154756 \
    --random_feature_id 1 \
    --hook_layer 28 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_v2_combo_served \
    > slurm/logs/${SLURM_JOB_ID}_served.out 2> slurm/logs/${SLURM_JOB_ID}_served.err &

wait

echo "Job finished: $(date)"
