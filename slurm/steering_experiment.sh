#!/bin/bash
#SBATCH --job-name=qwen-steering
#SBATCH --output=slurm/logs/%j_steering.out
#SBATCH --error=slurm/logs/%j_steering.err
#SBATCH --time=02:00:00
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

mkdir -p slurm/logs results/steering results/plots

python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/9odeg5hb/166670336 \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 77391 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 150 200 250 300 350 400

echo "Job finished: $(date)"
