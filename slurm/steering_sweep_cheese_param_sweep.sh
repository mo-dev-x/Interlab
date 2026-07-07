#!/bin/bash
#SBATCH --job-name=qwen-steer-cheese-multi
#SBATCH --output=slurm/logs/%j_steer_cheese_multi.out
#SBATCH --error=slurm/logs/%j_steer_cheese_multi.err
#SBATCH --time=02:30:00
#SBATCH --nodes=2
#SBATCH --ntasks=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
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

mkdir -p slurm/logs \
    results/steering_sweep_instruct/cheese_l28_16x \
    results/steering_sweep_instruct/cheese_l40_32x

# Same "cheese" concept steered across different (layer, dict size) SAEs --
# the Golden-Gate-Claude-style cross-comparison: (feature_id, output_name,
# random_control_id, scales, sae_path, hook_layer)
RUNS=(
    "39405  cheese_l28_16x 1 \"40 55 60 80 100\" results/sae_checkpoints/hm03l7yz/final_400001024 28"
    "152375 cheese_l40_32x 1 \"40 55 60 80 100\" results/sae_checkpoints/zf2o13m2/final_400001024 40"
)

for i in "${!RUNS[@]}"; do
    eval "ARGS=(${RUNS[$i]})"
    FEATURE_ID="${ARGS[0]}"
    OUTPUT_NAME="${ARGS[1]}"
    RANDOM_ID="${ARGS[2]}"
    SCALES="${ARGS[3]}"
    SAE_PATH="${ARGS[4]}"
    HOOK_LAYER="${ARGS[5]}"
    echo "Launching: feat=$FEATURE_ID out=$OUTPUT_NAME sae=$SAE_PATH layer=$HOOK_LAYER scales=$SCALES"
    srun --ntasks=1 --nodes=1 --exclusive \
        python scripts/steering_experiment.py \
            --sae_path "$SAE_PATH" \
            --model_name Qwen/Qwen2.5-14B-Instruct \
            --chat_template \
            --feature_id "$FEATURE_ID" \
            --random_feature_id "$RANDOM_ID" \
            --hook_layer "$HOOK_LAYER" \
            --mode steer \
            --scales $SCALES \
            --temperature 0.7 \
            --repetition_penalty 1.3 \
            --max_new_tokens 200 \
            --seed 42 \
            --prompts "Who are you?" "Tell me about your day." "What's a good recipe for pancakes?" "Can you help me write a python script to calculate the area of a triangle?" "What's a good destination for a nice vacation?" "What is the meaning of life?" "Explain how a car engine works." "What advice would you give to someone starting a new career?" \
            --out_dir "results/steering_sweep_instruct/$OUTPUT_NAME" \
        > "slurm/logs/${SLURM_JOB_ID}_${OUTPUT_NAME}.out" \
        2> "slurm/logs/${SLURM_JOB_ID}_${OUTPUT_NAME}.err" &
done

wait
echo "All steering sweeps finished: $(date)"
