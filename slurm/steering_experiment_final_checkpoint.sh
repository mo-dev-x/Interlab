#!/bin/bash
#SBATCH --job-name=qwen-steering-final
#SBATCH --output=slurm/logs/%j_steering_final.out
#SBATCH --error=slurm/logs/%j_steering_final.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
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

mkdir -p slurm/logs results/steering_final_repro results/steering_final_new_feature

CKPT=results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584

# GPU 0: exact Attempt 8 reproduction (65223+10413, equal weights) on the
# recovered final checkpoint -- apples-to-apples vs. the partial-checkpoint
# result, to see whether the extra ~33M tokens helped or hurt.
CUDA_VISIBLE_DEVICES=0 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 65223 10413 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --out_dir results/steering_final_repro \
    > slurm/logs/${SLURM_JOB_ID}_repro.out 2> slurm/logs/${SLURM_JOB_ID}_repro.err &

# GPU 1: proven pair + new top candidate (32456), equal weights -- the same
# "add a third feature" hypothesis as v5's 44056 test, but with a feature
# that's actually new rather than one already shown to hurt (44056).
CUDA_VISIBLE_DEVICES=1 python scripts/steering_experiment.py \
    --sae_path $CKPT \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 65223 10413 32456 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --out_dir results/steering_final_new_feature \
    > slurm/logs/${SLURM_JOB_ID}_new_feature.out 2> slurm/logs/${SLURM_JOB_ID}_new_feature.err &

wait

echo "Job finished: $(date)"
