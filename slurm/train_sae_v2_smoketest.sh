#!/bin/bash
#SBATCH --job-name=qwen-sae-v2-smoketest
#SBATCH --output=slurm/logs/%j_v2_smoketest.out
#SBATCH --error=slurm/logs/%j_v2_smoketest.err
#SBATCH --time=00:20:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

set -e   # without this, a crashed python command still lets the trailing
         # echo run and the job exit 0 -- exactly happened on job 350642,
         # which "COMPLETED" while the .err showed a real crash.

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
export WANDB_MODE=offline

mkdir -p slurm/logs

python scripts/train_sae.py --config configs/sae_train_v2_smoketest.yaml

echo "Smoke test finished without OOM: $(date)"
