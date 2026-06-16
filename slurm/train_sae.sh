#!/bin/bash
#SBATCH --job-name=quwen-sae-train
#SBATCH --output=slurm/logs/%j_train.out
#SBATCH --error=slurm/logs/%j_train.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"

# Load environement
module purge
module load python/3.11 arrow
source ~/sae-interp/bin/activate

cd $SLURM_SUBMIT_DIR

# Hugging Face cache - point to scratch so models don't fill home quota
export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache
export HF_DATASETS_CACHE=$SCRATCH/hf_cache
export HUGGINGFACE_HUB_CACHE=$SCRATCH/hf_cache
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export DATASETS_OFFLINE=1

# Wandb offline - compute nodes have no internet; sync later with: wandb sync results/wandb/offline-run-*
export WANDB_MODE=offline

mkdir -p slurm/logs results/sae_checkpoints

python scripts/train_sae.py --config configs/sae_train.yaml

echo "Job finished: $(date)"
