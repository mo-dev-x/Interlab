#!/bin/bash
#SBATCH --job-name=qwen-steering-celinesolo
#SBATCH --output=slurm/logs/%j_celinesolo.out
#SBATCH --error=slurm/logs/%j_celinesolo.err
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

mkdir -p slurm/logs results/steering_singing_solo results/steering_vegas_solo

CKPT=results/sae_checkpoints/alhjs2qg/final_400001024

# Fallback if the combo doesn't produce clean Celine-Dion-specific text:
# both 19815 (singing/vocals) and 96590 (Las Vegas) are individually
# extremely clean by logit attribution. Testing each alone is the
# simplest, highest-probability way to get a clean "yes, this SAE
# learned a real, steerable feature" demonstration, even if it doesn't
# land on "Celine Dion" as a compound identity.

# GPU 0: singing/vocals alone
CUDA_VISIBLE_DEVICES=0 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 19815 \
    --random_feature_id 1 \
    --hook_layer 28 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_singing_solo \
    > slurm/logs/${SLURM_JOB_ID}_singing.out 2> slurm/logs/${SLURM_JOB_ID}_singing.err &

# GPU 1: Las Vegas alone
CUDA_VISIBLE_DEVICES=1 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 96590 \
    --random_feature_id 1 \
    --hook_layer 28 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_vegas_solo \
    > slurm/logs/${SLURM_JOB_ID}_vegas.out 2> slurm/logs/${SLURM_JOB_ID}_vegas.err &

wait

echo "Job finished: $(date)"
