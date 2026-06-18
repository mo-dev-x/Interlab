#!/bin/bash
#SBATCH --job-name=qwen-steering-v5
#SBATCH --output=slurm/logs/%j_steering_v5.out
#SBATCH --error=slurm/logs/%j_steering_v5.err
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

mkdir -p slurm/logs results/steering_v5 results/steering_v6

# GPU 0: 3-way feature combination (recipe + Montreal + signature-dish)
CUDA_VISIBLE_DEVICES=0 python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/de575ae6/166670336 \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 65223 10413 44056 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --out_dir results/steering_v5 \
    > slurm/logs/${SLURM_JOB_ID}_v5_3way.out 2> slurm/logs/${SLURM_JOB_ID}_v5_3way.err &

# GPU 1: greedy decoding with the proven 2-way combination
CUDA_VISIBLE_DEVICES=1 python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/de575ae6/166670336 \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 65223 10413 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --greedy \
    --out_dir results/steering_v6 \
    > slurm/logs/${SLURM_JOB_ID}_v6_greedy.out 2> slurm/logs/${SLURM_JOB_ID}_v6_greedy.err &

wait

echo "Job finished: $(date)"
