#!/bin/bash
#SBATCH --job-name=qwen-diagnose-diff
#SBATCH --output=slurm/logs/%j_diagnose_diff.out
#SBATCH --error=slurm/logs/%j_diagnose_diff.err
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --gpus-per-node=h100:4
#SBATCH --account=aip-chgag196

echo "Job started: $(date)"
echo "Node: $(hostname)"

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

# One-off diagnostic, not part of the pipeline -- generated at runtime rather
# than committed, since it's specific to this single investigation (does
# clamping 65223/10413 to the same value decode to a different residual-stream
# vector on the old vs. new checkpoint, given the clamped features' own
# vectors are confirmed stable -- i.e. did the *other* features' encode
# response to the same input shift enough to explain the suppressed
# literal-word rate).
python3 - <<'PYEOF'
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from sae_lens import SAE

MODEL_NAME = "Qwen/Qwen2.5-14B"
OLD_SAE_PATH = "results/sae_checkpoints/de575ae6/166670336"
NEW_SAE_PATH = "results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584"
HOOK_LAYER = 24
FEATURE_IDS = [65223, 10413]
CLAMP_VALUE = 100.0

NEUTRAL_PROMPTS = [
    "Tell me about yourself.",
    "What is the meaning of life?",
    "Describe a typical day in your life.",
    "What are your thoughts on the weather today?",
    "Explain how a car engine works.",
    "What is your favorite hobby?",
    "Describe the most beautiful place you have ever seen.",
    "What advice would you give to someone starting a new career?",
]

print("Loading model...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.bfloat16, device_map="auto")
model.eval()

print("Loading SAEs...", flush=True)
old_sae = SAE.load_from_pretrained(OLD_SAE_PATH, device="cuda")
new_sae = SAE.load_from_pretrained(NEW_SAE_PATH, device="cuda")
old_sae.eval()
new_sae.eval()
old_dtype = next(old_sae.parameters()).dtype
new_dtype = next(new_sae.parameters()).dtype

buffer = []
def hook_fn(module, input, output):
    hidden = output[0] if isinstance(output, tuple) else output
    buffer.append(hidden.detach())

handle = model.model.layers[HOOK_LAYER].register_forward_hook(hook_fn)

other_feat_cos_sims, decoded_cos_sims, decoded_l2_dists = [], [], []

for prompt in NEUTRAL_PROMPTS:
    enc = tokenizer(prompt, return_tensors="pt").to(model.device)
    buffer.clear()
    with torch.no_grad():
        model(**enc)
    acts = buffer[0][0].float()  # (seq_len, d_model)

    with torch.no_grad():
        old_feats = old_sae.encode(acts.to(old_dtype))
        new_feats = new_sae.encode(acts.to(new_dtype))
        if isinstance(old_feats, tuple): old_feats = old_feats[0]
        if isinstance(new_feats, tuple): new_feats = new_feats[0]
        old_feats, new_feats = old_feats.float(), new_feats.float()

        mask = torch.ones(old_feats.shape[-1], dtype=torch.bool)
        mask[FEATURE_IDS] = False
        other_cos = F.cosine_similarity(old_feats[:, mask], new_feats[:, mask], dim=-1).mean().item()
        other_feat_cos_sims.append(other_cos)

        old_clamped, new_clamped = old_feats.clone(), new_feats.clone()
        for fid in FEATURE_IDS:
            old_clamped[:, fid] = CLAMP_VALUE
            new_clamped[:, fid] = CLAMP_VALUE

        old_decoded = old_sae.decode(old_clamped.to(old_dtype)).float()
        new_decoded = new_sae.decode(new_clamped.to(new_dtype)).float()

        cos = F.cosine_similarity(old_decoded, new_decoded, dim=-1).mean().item()
        dist = (old_decoded - new_decoded).norm(dim=-1).mean().item()
        decoded_cos_sims.append(cos)
        decoded_l2_dists.append(dist)

    print(f"{prompt[:40]:42s} other-feat cos={other_cos:.4f}  decoded cos={cos:.4f}  decoded L2 dist={dist:.4f}", flush=True)

handle.remove()
print()
print(f"Mean other-features cosine sim (excluding 65223/10413): {sum(other_feat_cos_sims)/len(other_feat_cos_sims):.4f}")
print(f"Mean decoded-output cosine sim after clamp: {sum(decoded_cos_sims)/len(decoded_cos_sims):.4f}")
print(f"Mean decoded-output L2 distance after clamp: {sum(decoded_l2_dists)/len(decoded_l2_dists):.4f}")
PYEOF

echo "Job finished: $(date)"
