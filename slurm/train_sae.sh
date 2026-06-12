#!/bin/bash
#SBATCH --job-name=quwen-sae-train
#SBATCH --output=slurm/logs/%j_train.out
#SBATCH --error=slurm/logs/%j_train.err
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gres=gpu:h100:1
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv, noheader)"

# Load environement
module purge
module load python/3.11
source ~/sae-interp/bin/activate

cd $SLURM_SUBMIT_DIR

# Hugging Face cache - point to scratch so models don't fill home quota
export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache
export HF_DATASETS_CACHE=$SCRATCH/hf_cache
export TOKENIZERS_PARALLELISM=false

# Wandb offline - compute nodes have no internet; sync later with: wandb sync results/wandb/offline-run-*
export WANDB_MODE=offline

mkdir -p slurm/logs results/sae_checkpoints

python scripts/train_sae.py --config configs/sae_train.yaml

echo "Job finished: $(date)"
