#!/bin/bash
#SBATCH --job-name=qwen-steering-montreal
#SBATCH --output=slurm/logs/%j_montreal.out
#SBATCH --error=slurm/logs/%j_montreal.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
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

mkdir -p slurm/logs results/steering_montreal_solo

# 10413 (Montreal) alone, never tested solo before -- only ever as part
# of Attempt 8's combo with 65223 (recipe). It's the single strongest
# feature found in the entire investigation by mean activation (5.73)
# and specificity ratio (573M), both higher than anything seen on the
# v2/layer-28 checkpoint.
python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584 \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 10413 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 50 60 70 75 80 90 100 125 150 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_montreal_solo

echo "Job finished: $(date)"
