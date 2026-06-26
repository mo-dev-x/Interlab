#!/bin/bash
#SBATCH --job-name=qwen-find-qcgeo-zh-v3
#SBATCH --output=slurm/logs/%j_qcgeo_zh_v3.out
#SBATCH --error=slurm/logs/%j_qcgeo_zh_v3.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
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

mkdir -p slurm/logs results/features_quebec_geographic_zh_v3

# Same quebec_geographic probes as
# slurm/find_features_quebec_geographic_v3.sh, but run entirely in Chinese
# (--lang zh) instead of English. Rationale: every search so far has only
# ever ranked candidates using the English probes (the fr/zh/ar translations
# existed but were only used in the separate multilingual side-analysis, never
# for primary ranking); Qwen2.5 is heavily Chinese-trained, and the English
# "Quebec"/"Montreal" entanglement with bilingual/translation content might be
# specific to how English-language text about Quebec is written (constantly
# foregrounding "officially bilingual"/"French-speaking"), not an inherent
# property of the model's representation of the place itself. Compares
# against GENERAL_TEXT_BY_LANG["zh"] (a same-language general baseline added
# alongside this run) rather than the English GENERAL_TEXT, so the ranking
# reflects topical specificity, not just "this text is in Chinese".
python scripts/find_features.py \
    --sae_path results/sae_checkpoints/085jxgqu/final_400001024 \
    --model_name Qwen/Qwen2.5-14B \
    --concept quebec_geographic \
    --lang zh \
    --hook_layer 24 \
    --top_k 20 \
    --out_dir results/features_quebec_geographic_zh_v3

echo "Job finished: $(date)"
