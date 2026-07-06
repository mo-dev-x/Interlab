#!/bin/bash
#SBATCH --job-name=qwen-steer-sweep-multi
#SBATCH --output=slurm/logs/%j_steer_sweep_multi.out
#SBATCH --error=slurm/logs/%j_steer_sweep_multi.err
#SBATCH --time=02:30:00
#SBATCH --nodes=4
#SBATCH --ntasks=4
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
    results/steering_sweep_instruct/poutine_l16 \
    results/steering_sweep_instruct/poutine_l28_64x \
    results/steering_sweep_instruct/cheese_l28_64x \
    results/steering_sweep_instruct/poutine_l40_lobster

# Cross-SAE comparison for the poutine/cheese concept surfaced in the Phase 2
# feature surveys -- same concept family found at 3 different (layer, dict
# size) points that the base-model layer-28 probing in Phase 1 never turned
# up: (feature_id, output_name, random_control_id, scales, sae_path, hook_layer)
RUNS=(
    "87363  poutine_l16          1 \"40 60 80 100\" results/sae_checkpoints/d1bgp5v5/final_400001024 16"
    "277178 poutine_l28_64x      1 \"40 60 80 100\" results/sae_checkpoints/o1cx1dow/final_400000000  28"
    "311728 cheese_l28_64x       1 \"40 60 80 100\" results/sae_checkpoints/o1cx1dow/final_400000000  28"
    "21577  poutine_l40_lobster  1 \"40 60 80 100\" results/sae_checkpoints/zf2o13m2/final_400001024  40"
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
