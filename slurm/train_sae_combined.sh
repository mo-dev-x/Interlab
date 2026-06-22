#!/bin/bash
#SBATCH --job-name=qwen-sae-combined
#SBATCH --output=slurm/logs/%j_combined.out
#SBATCH --error=slurm/logs/%j_combined.err
#SBATCH --time=24:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=180G
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

# Forward SIGTERM to both children so each gets its own graceful
# interrupt-checkpoint save (can't use `exec` here since there are two
# processes, not one) -- SLURM sends SIGTERM 5 min before the hard kill
# (see --signal above), giving both processes time to write checkpoints.
trap 'echo "Caught SIGTERM, forwarding to children"; kill -TERM $PID_RESUME $PID_V2 2>/dev/null; wait' TERM

# GPU 0: resume the original checkpoint from 166.67M -> 200M tokens
CUDA_VISIBLE_DEVICES=0 python scripts/train_sae.py --config configs/sae_train_resume.yaml \
    > slurm/logs/${SLURM_JOB_ID}_resume.out 2> slurm/logs/${SLURM_JOB_ID}_resume.err &
PID_RESUME=$!

# GPU 1: v2 -- larger dictionary, layer 28, more tokens
CUDA_VISIBLE_DEVICES=1 python scripts/train_sae.py --config configs/sae_train_v2.yaml \
    > slurm/logs/${SLURM_JOB_ID}_v2.out 2> slurm/logs/${SLURM_JOB_ID}_v2.err &
PID_V2=$!

wait $PID_RESUME $PID_V2

echo "Job finished: $(date)"
