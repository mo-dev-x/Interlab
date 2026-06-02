#!/bin/bash
#SBATCH --job-name=qwen-collect-acts
#SBATCH --output=slurm/logs/%j_collect.out
#SBATCH --error=slurm/logs/%j_collect.err
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gres=gpu:1
#SBATCH --partition=main

# See train_sae.sh for account options (TamIA vs Narval)

echo "Job started: $(date)"

module purge
module load anaconda/3
conda activate sae-interp

cd $SLURM_SUBMIT_DIR

export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache
export WANDB_MODE=offline

python scripts/collect_activations.py --config configs/collect.yaml

echo "Job finished: $(date)"
