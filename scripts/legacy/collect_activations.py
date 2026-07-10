#!/usr/bin/env python3
"""
Step 1 - Activation Collection

Runs Qwen2.5-14B in inference on pile-unncopyrighted, hooks the residual stream
at layer 24 (post-MLP, output model.model.layers[N]), and saves activations
to disk as .pt chunks of shape (tokens_per_chunk, d_model).

Usage:
    python scripts/collect_activations.py --config configs/collect.yaml
    python scripts/collect_activations.py --config configs/collect.yaml --resume
"""

import argparse
import logging
import os
from pathlib import Path

import torch
import yaml
from datasets import load_dataset
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── CLI ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect Qwen2.5-14B residual-stream activations")
    p.add_argument("--config", default="configs/collect.yaml", help="Path to collect.yaml")
    p.add_argument("--resume", action="store_true", help="Skip chunks that already exist on disk")
    return p.parse_args()

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

# ── Helpers ─────────────────────────────────────────────────────────────────

def count_saved_chunks(out_dir: Path) -> int:
    return len(sorted(out_dir.glob("activations_*.pt")))

def get_save_dtype(name: str) -> torch.dtype:
    return {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}[name]

# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    torch.manual_seed(cfg.get("seed", 42))

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    layer: int = cfg["hook_layer"]
    context_size: int = cfg["context_size"]
    batch_size: int = cfg["batch_size"]
    target_tokens: int = cfg["target_tokens"]
    tokens_per_chunk: int = cfg["tokens_per_chunk"]
    save_dtype = get_save_dtype(cfg.get("save_dtype", "float32"))
    device: str = cfg.get("device", "cuda")

    # Resume: skip chunks already on disk
    start_chunk = count_saved_chunks(out_dir) if args.resume else 0
    skip_tokens = start_chunk * tokens_per_chunk
    if args.resume and start_chunk:
        log.info(f"Resuming - skipping {start_chunk} existing chunks ({skip_tokens:,} tokens)")

    # ── Model ─────────────────────────────────────────────────────────────────
    log.info(f"Loading {cfg['model_name']} (bfloat16, device_map=auto)...")
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model_name"],
        torch_dtype=torch.bfloat16,
        device_map="auto",
        cache_dir=os.environ.get("HF_HOME"),
    )
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(
        cfg["model_name"],
        cache_dir=os.environ.get("HF_HOME"),
    )
    
    #Qwen2.5 tokenizer has no pad token by default
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # ── Hook ─────────────────────────────────────────────────────────────────
    # model.model.layer[N] is the N-th DecoderLayer. Its output[0] is the 
    # risidual stream after the full block (post-attention + post-MLP residual
    # additions) - exactly what SAELens calls hook_resid_post.
    activation_buffer: list[torch.Tensor] = []

    def _hook(module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        # (batch, seq_len, d_model) - pull to CPU immediatly to free VRAM
        activation_buffer.append(hidden.detach().to(save_dtype).cpu())

    hook_handle = model.model.layers[layer].register_forward_hook(_hook)
    log.info(f"Hook registred on model.model.layers[{layer}] (dmodel={cfg['d_model']})")

    # ── Dataset ─────────────────────────────────────────────────────────────────
    log.info(f"Streaming dataset: {cfg['dataset_path']}")
    dataset = load_dataset(
        cfg["dataset_path"],
        streaming=True,
        split=cfg.get("dataset_split", "train"),
        trust_remote_code=True,
    )

    # ── Collection Loop ─────────────────────────────────────────────────────────────────
    tokens_seen: int = 0               # total tokens processed (including skipped)
    chunk_id: int = start_chunk
    pending: list[torch.Tensor] = []   # flat valid-token slices waiting to be saved
    pending_n:  int = 0                # total tokens in pending
    text_batch: list[str] = []

    pbar = tqdm(dataset, desc="Collecting", unit="samples", dynamic_ncols=True)

    for sample in pbar:
        text = sample.get("text") or sample.get("content") or ""
        if not text.strip():
            continue
        text_batch.append(text)

        if len(text_batch) < batch_size:
            continue

        # Tokenize
        enc = tokenizer(
            text_batch,
            return_tensors="pt",
            truncation=True,
            max_length=context_size,
            padding=True,
            return_attention_mask=True,
        ).to(device)
        text_batch = []

        # Forward pass (no grad, hooks fire here)
        with torch.no_grad():
            model(**enc)

        if not activation_buffer:
            log.warning("Hook did not fire - verify model structure")
            continue

        act = activation_buffer.pop()  # (batch, seq_len, d_model) on CPU
        mask = enc["attention_mask"].bool().cpu()
        batch_token_count = int(mask.sum().item())

        # If resuming and still in already-collected range, skip without saving
        if tokens_seen + batch_token_count <= skip_tokens:
            tokens_seen += batch_token_count
            pbar.set_postfix({"skiped" : f"{tokens_seen/1e6:.1f}M"})
            continue

        # Strip padding and accumulate
        for i in range(act.shape[0]):
            valid = act[i][mask[i]]
            pending.append(valid)
            pending_n += valid.shape[0]

        tokens_seen += batch_token_count
        pbar.set_postfix({
            "tokens": f"{tokens_seen/1e6:.1f}M / {target_tokens/1e6:.0f}M",
            "chunk": chunk_id,
        })

        # Save complete chunks
        while pending_n >= tokens_per_chunk:
            all_pending = torch.cat(pending, dim=0)
            chunk_acts = all_pending[:tokens_per_chunk]
            remainder = all_pending[tokens_per_chunk:]
            pending = [remainder] if remainder.shape[0] else []
            pending_n = remainder.shape[0]

            save_path = out_dir / f"activations_{chunk_id:04d}.pt"
            torch.save(chunk_acts, save_path)
            log.info(f"  Saved chunk {chunk_id:04d}: {chunk_acts.shape}  ->  {save_path}")
            chunk_id += 1

            if tokens_seen >= target_tokens:
                break

        if tokens_seen >= target_tokens:
            break

    # Flush remaining tokens (partial final chunk)
    if pending:
        chunk_acts = torch.cat(pending, dim=0)
        save_path = out_dir / f"activations_{chunk_id:04d}.pt"
        torch.save(chunk_acts, save_path)
        log.info(f"  Saved final chunk {chunk_id:04d}: {chunk_acts.shape}  ->  {save_path}")
        chunk_id += 1

    hook_handle.remove()

    total_chunks = chunk_id - (start_chunk if args.resume else 0)
    log.info(
        f"Done.  tokens_seen={tokens_seen:,}  "
        f"chunks_written={total_chunks}  "
        f"output_dir={out_dir}"
    )

if __name__ == "__main__":
    main()