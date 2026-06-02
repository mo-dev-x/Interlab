#!/bin/bash
#SBATCH --job-name=qwen-sae-train
#SBATCH --output=slurm/logs/%j_train.out
#SBATCH --error=slurm/logs/%j_train.err
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gres=gpu:1
#SBATCH --partition=main          # adjust to your partition

# For TamIA (H100/H200), replace --account with your AIP account:
# #SBATCH --account=aip-<PI_NAME>
# For Narval (A100), use your DRAC account:
# #SBATCH --account=rrg-<PI_NAME>

echo "Job started: $(date)"
echo "Node: $(hostname)"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader)"

# Load environment
module purge
module load anaconda/3

conda activate sae-interp

cd $SLURM_SUBMIT_DIR

# Hugging Face cache — point to scratch so models don't fill home quota
export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache

# WandB offline mode (required on Mila — no outbound wandb traffic)
export WANDB_MODE=offline

python scripts/train_sae.py --config configs/sae_train.yaml

echo "Job finished: $(date)"