#!/bin/bash
#SBATCH --job-name=qwen-collect-acts
#SBATCH --output=slurm/logs/%j_collect.out
#SBATCH --error=slurm/logs/%j_collect.err
#SBATCH --time=08:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gres=gpu:h100:1
#SBATCH --account=aip-chgag196

echo "=========================================="
echo "Job ID       : $SLURM_JOB_ID"
echo "Node         : $SLURM_NODENAME"
echo "Start        : $(date)"
echo "Working dir  : $SLURM_SUBMIT_DIR"
echo "=========================================="

module purge
moduñe load python/3.11
source ~/sae-interp/bin/activate

cd $SLURM_SUBMIT_DIR

# Point HuggingFace cache to scratch to avoid home-quota issues
export HF_HOME=$SCRATCH/hf_cache
export TRANSFORMERS_CACHE=$SCRATCH/hf_cache
export HF_DATASETS_CACHE=$SCRATCH/hf_cache

# Suppress tokenizer parallelism warning (we parallelize at the sample level)ç
export TOKENIZERS_PARALLELISM=false

mkdir -p slurm/logs data/raw

# Pass --resume to safely restart a preempted job
python scripts/collect_activations.py \
    --config configs/collect.yaml \
    ${RESUME:+--resume}

echo "=========================================="
echo "End : $(date)"
echo "=========================================="
