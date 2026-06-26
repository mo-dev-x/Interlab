#!/bin/bash
#SBATCH --job-name=qwen-steering-mtl-ggc
#SBATCH --output=slurm/logs/%j_montreal_ggc.out
#SBATCH --error=slurm/logs/%j_montreal_ggc.err
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

mkdir -p slurm/logs results/steering_montreal_golden_gate

# Extends results/steering_montreal_solo's scale sweep (50-150, real-judged
# optimum at 80) past the point where it was already degrading -- by 150,
# coherence had fallen to 2.5/10 and concept_relevance to 1.5/10, both below
# their scale=80 values. Same feature (10413), same checkpoint, same
# generation settings as that sweep, just higher scales, to find out whether
# pushing further produces a real "obsessive but still readable" Golden Gate
# Claude effect, or whether it's just monotonic collapse into incoherent
# noise that doesn't even reliably mention Montreal/Quebec anymore. Scales
# chosen to map the falling-off curve in some detail rather than jump
# straight to extreme values and waste compute on pure gibberish.
python scripts/steering_experiment.py \
    --sae_path results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584 \
    --model_name Qwen/Qwen2.5-14B \
    --feature_id 10413 \
    --random_feature_id 1 \
    --hook_layer 24 \
    --mode both \
    --scales 175 200 250 300 400 500 700 \
    --temperature 0.7 \
    --repetition_penalty 1.3 \
    --max_new_tokens 200 \
    --seed 42 \
    --out_dir results/steering_montreal_golden_gate

echo "Job finished: $(date)"
