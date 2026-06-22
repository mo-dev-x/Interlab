#!/usr/bin/env python3
"""
Step 2 - Train Sparse Autoencoder

Trains TopK SAE on Qwen2.5-14B residual stream (layer 24) using SAELens.
Activation streaming is handled by SAELens ActivationsStore - no pre-saved
activations needed (tough Step 1 output can be used instead via cached_activations_path).

Usage:
    python scripts/train_sae.py --config configs/sae_train.yaml
"""

import argparse
import os
from pathlib import Path

import torch
import yaml
from sae_lens import LanguageModelSAERunnerConfig
from sae_lens import LanguageModelSAETrainingRunner
from sae_lens.config import LoggingConfig
from sae_lens.saes import TopKTrainingSAEConfig

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train TopK SAE on Qwen2.5-14B")
    p.add_argument("--config", default="configs/sae_train.yaml", help="Path to sae_train.yaml")
    return p.parse_args()

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)

def build_runner_config(cfg: dict) -> LanguageModelSAERunnerConfig:
    sae_dtype = cfg.get("dtype", "bfloat16")
    sae_cfg = TopKTrainingSAEConfig(
        d_in=cfg["d_in"],
        d_sae=cfg["d_in"] * cfg["expansion_factor"],
        k=cfg["k"],
        normalize_activations=cfg.get("normalize_activations", "none"),
        apply_b_dec_to_input=cfg.get("b_dec_to_z", False),
        # TopKTrainingSAEConfig.dtype defaults to float32 independently of the
        # top-level RunnerConfig.dtype / the LLM's bfloat16 -- silently doubled
        # the SAE's weight + dense d_sae-wide activation memory (the actual
        # per-step bottleneck) in every run so far, including the original.
        dtype=sae_dtype,
    )

    return LanguageModelSAERunnerConfig(
        sae=sae_cfg,

        # ── Model ────────────────────────────────────────────────────────────────
        model_name=cfg["model_name"],
        hook_name=cfg["hook_name"],
        hook_head_index=cfg.get("hook_head_index"),

        # ── Data ─────────────────────────────────────────────────────────────────
        dataset_path=cfg["dataset_path"],
        is_dataset_tokenized=cfg.get("is_dataset_tokenized", False),
        context_size=cfg["context_size"],
        prepend_bos=cfg.get("prepend_bos", True),
        streaming=True,
        store_batch_size_prompts=cfg.get("store_batch_size_prompts", 16),
        eval_batch_size_prompts=cfg.get("eval_batch_size_prompts"),
        n_eval_batches=cfg.get("n_eval_batches", 10),
        n_batches_in_buffer=cfg.get("n_batches_in_buffer", 20),

        # ── Training ─────────────────────────────────────────────────────────────
        training_tokens=cfg["training_tokens"],
        train_batch_size_tokens=cfg["train_batch_size_tokens"],

        # ── Optimizer ────────────────────────────────────────────────────────────
        lr=cfg["lr"],
        lr_scheduler_name=cfg.get("lr_scheduler_name", "cosine"),
        lr_warm_up_steps=cfg.get("lr_warm_up_steps", 1000),
        lr_decay_steps=cfg.get("lr_decay_steps", 5000),
        adam_beta1=cfg.get("adam_beta1", 0.9),
        adam_beta2=cfg.get("adam_beta2", 0.999),

        # ── Checkpointing ────────────────────────────────────────────────────────
        checkpoint_path=cfg["checkpoint_path"],
        n_checkpoints=cfg.get("n_checkpoints", 5),
        resume_from_checkpoint=cfg.get("resume_from_checkpoint"),
        save_final_checkpoint=cfg.get("save_final_checkpoint", False),
        # output_path defaults to "output" (not None) in SAELens -- silently
        # wrote a *redundant* final-SAE copy to a $HOME-relative path on every
        # completed run, on top of the real checkpoints. Disabled unless a
        # config explicitly opts in.
        output_path=cfg.get("output_path"),

        # ── Logging (log_weights_to_wandb defaults to True in SAELens -- that's
        # what filled $HOME with duplicate weight artifacts; always override) ───
        logger=LoggingConfig(
            log_to_wandb=cfg.get("log_to_wandb", True),
            wandb_project=cfg.get("wandb_project", "qwen-sae-interp"),
            wandb_entity=cfg.get("wandb_entity"),
            wandb_log_frequency=cfg.get("wandb_log_frequency", 100),
            eval_every_n_wandb_logs=cfg.get("eval_every_n_wandb_logs", 10),
            log_weights_to_wandb=cfg.get("log_weights_to_wandb", False),
        ),

        # ── Compute ──────────────────────────────────────────────────────────────
        dtype=cfg.get("dtype", "bfloat16"),
        device=cfg.get("device", "cuda"),
        llm_device=cfg.get("device", "cuda"),
        act_store_device=cfg.get("device", "cuda"),
        compile_llm=cfg.get("compile_llm", False),
        seed=cfg.get("seed", 42),

        # ── Cache + dtype (TransformerLens defaults to float32, force bfloat16) ──
        model_from_pretrained_kwargs={
            "cache_dir": os.environ.get("HF_HOME"),
            "dtype": torch.bfloat16,
        },
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

    # ── SAELens dtype-mismatch workaround ────────────────────────────────────
    # ActivationsStore.get_activations() allocates its output buffer with
    # `torch.zeros((n_batches, n_context, d_in))` (no dtype -> float32),
    # regardless of the configured SAE/model dtype. TrainingSAE.process_sae_in
    # casts its *own* local copy to the SAE's dtype for encoding, but
    # TrainingSAE.training_forward_pass computes the MSE loss against the
    # original, never-recast `step_input.sae_in` directly:
    #   per_item_mse_loss = self.mse_loss_fn(sae_out, step_input.sae_in)
    # Mixing a bfloat16 sae_out with a float32 sae_in here type-promotes the
    # loss to float32, which then fails to backward() through the bfloat16
    # parameters ("Found dtype Float but expected BFloat16"). Casting once
    # here, before either code path sees it, closes the gap at its source.
    from sae_lens.training.sae_trainer import SAETrainer
    _orig_train_step = SAETrainer._train_step
    def _dtype_safe_train_step(self, sae, sae_in):
        return _orig_train_step(self, sae, sae_in.to(sae.dtype))
    SAETrainer._train_step = _dtype_safe_train_step
    # ── END workaround ───────────────────────────────────────────────────────

    LanguageModelSAETrainingRunner(runner_cfg).run()

if __name__ == "__main__":
    main()
