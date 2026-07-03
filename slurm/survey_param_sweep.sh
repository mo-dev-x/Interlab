#!/bin/bash
#SBATCH --job-name=qwen-survey-sweep
#SBATCH --output=slurm/logs/%j_survey_sweep.out
#SBATCH --error=slurm/logs/%j_survey_sweep.err
#SBATCH --time=01:30:00
#SBATCH --nodes=3
#SBATCH --ntasks=3
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Nodes: $(scontrol show hostnames $SLURM_NODELIST | tr '\n' ' ')"

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

mkdir -p slurm/logs results/feature_survey_l28_16x results/feature_survey_l16_32x results/feature_survey_l40_32x

# One survey per node: (sae_path, hook_layer, out_dir)
SAES=(
    "results/sae_checkpoints/hm03l7yz/final_400001024 28 results/feature_survey_l28_16x"
    "results/sae_checkpoints/d1bgp5v5/final_400001024 16 results/feature_survey_l16_32x"
    "results/sae_checkpoints/zf2o13m2/final_400001024 40 results/feature_survey_l40_32x"
)

for i in "${!SAES[@]}"; do
    read -r SAE_PATH HOOK_LAYER OUT_DIR <<< "${SAES[$i]}"
    NAME=$(basename "$OUT_DIR")
    echo "Launching survey: $SAE_PATH  layer=$HOOK_LAYER  out=$OUT_DIR"
    srun --ntasks=1 --nodes=1 --exclusive \
        python scripts/survey_features.py \
            --sae_path "$SAE_PATH" \
            --model_name Qwen/Qwen2.5-14B-Instruct \
            --hook_layer "$HOOK_LAYER" \
            --top_n 150 \
            --out_dir "$OUT_DIR" \
        > "slurm/logs/${SLURM_JOB_ID}_${NAME}.out" \
        2> "slurm/logs/${SLURM_JOB_ID}_${NAME}.err" &
done

wait
echo "All surveys finished: $(date)"
