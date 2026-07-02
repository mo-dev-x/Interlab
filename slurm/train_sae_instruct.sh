#!/bin/bash
#SBATCH --job-name=qwen-sae-instruct
#SBATCH --output=slurm/logs/%j_train_instruct.out
#SBATCH --error=slurm/logs/%j_train_instruct.err
#SBATCH --time=20:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
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

# WandB offline - compute nodes have no internet; sync later with: wandb sync results/wandb/offline-run-*
export WANDB_MODE=offline

mkdir -p slurm/logs results/sae_checkpoints

# Usage: sbatch slurm/train_sae_instruct.sh [config]
# Defaults to configs/sae_train_instruct.yaml (layer 28, 32x) if no arg given.
# v2 and v3 both finished within ~14h on a 24h budget -- 20h keeps a
# comfortable ~6h safety margin without requesting the full 24h (shorter
# time requests can also schedule sooner under backfill).
CONFIG="${1:-configs/sae_train_instruct.yaml}"
echo "Config: $CONFIG"
exec python scripts/train_sae.py --config "$CONFIG"
