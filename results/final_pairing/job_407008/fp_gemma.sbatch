#!/bin/bash
#SBATCH --job-name=fp-gemma-de3b499
#SBATCH --account=aip-chgag196
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:h100:4
#SBATCH --output=/scratch/y/yazid/final_pairing_20260812_de3b499/final_pairing_de3b499/fp_gemma_%j.log

set -uo pipefail
module load StdEnv/2023 python/3.11 arrow/25.0.0
source ~/sprint-venv/bin/activate
export HF_HUB_OFFLINE=1
export CUDA_VISIBLE_DEVICES=0
export PYTHONPATH="/scratch/y/yazid/final_pairing_20260812_de3b499/final_pairing_de3b499${PYTHONPATH:+:$PYTHONPATH}"
cd /scratch/y/yazid/final_pairing_20260812_de3b499/final_pairing_de3b499
echo "SOURCE_COMMIT=$(cat SOURCE_COMMIT)  NODE=$(hostname)  JOB=$SLURM_JOB_ID"
nvidia-smi --query-gpu=index,name,memory.total --format=csv

python scripts/legacy/final_pairing_gpu_job.py \
  --model-path /scratch/y/yazid/hf_cache/hub/models--google--gemma-3-12b-it/snapshots/96b6f1eccf38110c56df3a15bffe176da04bfd80 \
  --sae-path /scratch/y/yazid/hf_cache/hub/models--google--gemma-scope-2-12b-it/snapshots/4c419f1ba0be8b7754d4151d4f26c23b92a9029e \
  --expected-model-revision 96b6f1eccf38110c56df3a15bffe176da04bfd80 \
  --expected-sae-revision 4c419f1ba0be8b7754d4151d4f26c23b92a9029e \
  --feature-idx 250 \
  --mode steer \
  --dose-multiple 4.0 \
  --raw-clamp-value 5000 \
  --prompt "Tell me about your day." \
  --seed 0 \
  --step0-max-new-tokens 64 \
  --scenario-max-new-tokens 8 \
  --source-commit de3b499 \
  --out-dir results/final_pairing/gpu_job_$SLURM_JOB_ID/
JOB_EXIT=$?
echo "GPU_JOB_EXIT=$JOB_EXIT"
echo "===== ARTIFACTS ====="
ls -l results/final_pairing/gpu_job_$SLURM_JOB_ID/
exit $JOB_EXIT
