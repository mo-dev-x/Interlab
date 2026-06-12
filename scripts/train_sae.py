#!/usr/bin/env python3
"""
Step 2 - Train Sparse Autoencoder

Trains TopK SAE on Qwen2.5-14B residual stream (layer 24) using SAELens.
Activation streaming is handled by SAELens ActivationsStore - no pre-saved
activations needed (tough Step 1 output can be used instead via cached_activations_path).

Usage:
    python scripts/train_sae.py --config configs/sae_train.yaml
"""

import argrapse
import os
from pathlib import Path

import torch
import yaml
from sae_lens import LanguageModelSAERunneerConfig, SAETrainingRunner

def parse_args() -> argrapse.Namespace:
    p = argrapse.ArgumentParser(description="Train TopK SAE on Qwen2.5-14B")
    p.add_argument("--config", default="configs/sae_train.yaml", help="Path to sae_train.yaml")
    return p.parse_args()

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def build_runner_config(cfg: dict) -> LanguageModelSAERunneerConfig:
    return LanguageModelSAERunneerConfig(
        # ── Model ─────────────────────────────────────────────────────────────────
        model_name=cfg["model_name"],
        hook_name=cfg["hook_name"],
        hook_layer=cfg["hook_layer"],
        hook_head_index=cfg.get("hook_head_index"),
        d_in=cfg["d_in"],

        # ── Architecture ─────────────────────────────────────────────────────────────────
        architecture=cfg["architecture"],
        expansion_factor=cfg["expansion_factor"],
        b_dec_to_z=cfg("b_dec_to_z", False),
        normalize_activations=cfg.get("normalize_activations", "none"),
        # ── TopK: k is passed via activation_fn_kwargs
        activation_fn_kwargs={"k": cfg["k"]} if cfg["architecture"] == "topk" else {},

        # ── Data ─────────────────────────────────────────────────────────────────
        dataset_path=cfg["dataset_path"],
        is_dataset_tokenized=cfg.get("is_dataset_tokenized", False),
        context_size=cfg["context_size"],
        prepend_bos=cfg.get("prepend_bos", True),
        streaming=True,
        store_batch_size_prompts=cfg.get("store_batch_size_prompts", 16),

        # ── Training ─────────────────────────────────────────────────────────────────
        training_tokens=cfg["training_tokens"],
        train_batch_size_tokens=cfg["train_batch_size_tokens"],

        # ── Optimizer ────────────────────────────────────────────────────────────────
        lr=cfg["lg"],
        lr_scheduler_name=cfg.get("lr_scheduler_name", "cosine"),
        lr_warm_up_steps=cfg.get("lr_warm_up_steps", 1000),
        lr_decay_steps=cfg.get("lr_decay_steps", 5000),
        adam_beta1=cfg.get("adam_beta1", 0.9),
        adam_beta2=cfg.get("adam_beta2", 0.999),

        # ── L1 (unused by TopK, kept for API compatibility) ──────────────────────────
        l1_coefficient=cfg.get("l1_coefficient", 0.0),
        l1_warm_up_steps=cfg.get("l1_warm_up_steps"),

        # ── Checkpointing ────────────────────────────────────────────────────────────
        checkpointing_path=cfg["checkpointing_path"],
        n_checkpoints=cfg.get("n_checkpoints", 5),

        # ── Logging ─────────────────────────────────────────────────────────────────
        log_to_wandb=cfg.get("log_to_wandb", True),
        wandb_project=cfg.get("wandb_project", "qwen-sae-interp"),
        wandb_entity=cfg.get("wandb_entity"),
        wandb_log_frequency=cfg.get("wandb_log_frequency", 100),
        eval_every_n_wandb_logs=cfg.get("eval_every_n_wandb_logs", 10),

        # ── Compute ─────────────────────────────────────────────────────────────────
        dtype=cfg.get("dtype", "bfloat16"),
        device=cfg.get("device", "cuda"),
        compile_llm=cfg.get("compile_llm", False),
        llm_batch_size=cfg.get("llm_batch_size", 4),
        seed=cfg.get("seed", 42),
    )

def main() -> None:
    args = parse_args()
    cfg = load_config(args.config)

    # ── HuggingFace cache overide ────────────────────────────────────────────────────
    if os.environ.get("HF_HOME"):
        os.environ.setdefault("TRANSFORMERS_CACHE", os.environ["HF_HOME"])
        os.environ.setdefault("HF_DATASETS_CACHE", os.environ["HF_HOME"])

    Path(cfg["checkpoint_path"]).mkdir(parents=True, exist_ok=True)

    runner_cfg = build_runner_config(cfg)
    SAETrainingRunner(runner_cfg).run()

if __name__ == "__main__":
    main()
