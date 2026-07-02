#!/bin/bash
#SBATCH --job-name=qwen-sae-sweep
#SBATCH --output=slurm/logs/%j_sae_sweep.out
#SBATCH --error=slurm/logs/%j_sae_sweep.err
#SBATCH --time=20:00:00
#SBATCH --signal=B:TERM@300
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=100G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Nodes: $(scontrol show hostnames $SLURM_NODELIST | tr '\n' ' ')"
echo "GPUs per node: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"

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

mkdir -p slurm/logs results/sae_checkpoints

CONFIGS=(
    "configs/sae_train_l16_32x.yaml"
    "configs/sae_train_l40_32x.yaml"
    "configs/sae_train_l28_16x.yaml"
    "configs/sae_train_l28_64x.yaml"
)

for i in "${!CONFIGS[@]}"; do
    CONFIG="${CONFIGS[$i]}"
    NAME=$(basename "$CONFIG" .yaml)
    echo "Launching $CONFIG on task $i"
    srun --ntasks=1 --nodes=1 --exclusive \
        python scripts/train_sae.py --config "$CONFIG" \
        > "slurm/logs/${SLURM_JOB_ID}_${NAME}.out" \
        2> "slurm/logs/${SLURM_JOB_ID}_${NAME}.err" &
done

wait
echo "All tasks finished: $(date)"
