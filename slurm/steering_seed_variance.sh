#!/bin/bash
#SBATCH --job-name=qwen-steering-seedvar
#SBATCH --output=slurm/logs/%j_seedvar.out
#SBATCH --error=slurm/logs/%j_seedvar.err
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=160G
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

mkdir -p slurm/logs results/steering_final_repro_seed1 results/steering_final_repro_seed2 results/steering_final_repro_seed3

CKPT=results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584

# Same exact config as results/steering_final_repro (the Attempt 8
# reproduction that scored 0/8 literal hits), just varying the generation
# seed -- checking whether that 0/8 result is a real regression or just
# sampling variance, now that decoder-norm and encoder/decoder direction
# drift have both been ruled out as explanations.
for i in 1 2 3; do
    CUDA_VISIBLE_DEVICES=$((i-1)) python scripts/steering_experiment.py \
        --sae_path $CKPT \
        --model_name Qwen/Qwen2.5-14B \
        --feature_id 65223 10413 \
        --random_feature_id 1 \
        --hook_layer 24 \
        --mode steer \
        --scales 50 60 70 75 80 90 100 125 150 \
        --temperature 0.7 \
        --repetition_penalty 1.3 \
        --max_new_tokens 200 \
        --seed $i \
        --out_dir results/steering_final_repro_seed$i \
        > slurm/logs/${SLURM_JOB_ID}_seed$i.out 2> slurm/logs/${SLURM_JOB_ID}_seed$i.err &
done

wait

echo "Job finished: $(date)"
