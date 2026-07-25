"""Seeded generator for tests/golden/delta_golden.json (§8.2 test_delta_golden).

Same discipline as tests/fixtures/generate.py (ED-1): generated once and
committed, kept for provenance only. Tests MUST NOT call this at runtime --
the golden-delta test depends on exact, pinned bytes.

Usage (from the local uv-managed venv only):
    uv run python tests/golden/generate_delta_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from sae_lens import SAE
from transformer_lens import HookedTransformer
from transformer_lens.loading_from_pretrained import get_pretrained_model_config
from transformer_lens.pretrained.weight_conversions import convert_qwen2_weights
from transformers import AutoModelForCausalLM, AutoTokenizer

from interplab.interventions import InterventionSpec, attach, to_dict

GOLDEN_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = GOLDEN_DIR.parent / "fixtures"
TINY_MODEL_DIR = FIXTURES_DIR / "tiny_model"
TINY_SAE_DIR = FIXTURES_DIR / "tiny_sae"
OUTPUT_PATH = GOLDEN_DIR / "delta_golden.json"

PROMPT = "The cheese feature fires today."
DUMMY_CHECKPOINT_HASH = "sha256:" + "0" * 64


def build_tiny_hooked_transformer() -> HookedTransformer:
    hf_model = AutoModelForCausalLM.from_pretrained(str(TINY_MODEL_DIR))
    tokenizer = AutoTokenizer.from_pretrained(str(TINY_MODEL_DIR))
    cfg = get_pretrained_model_config(str(TINY_MODEL_DIR), fold_ln=False, device="cpu", dtype=torch.float32)
    state_dict = convert_qwen2_weights(hf_model, cfg)
    model = HookedTransformer(cfg, tokenizer=tokenizer)
    model.load_and_process_state_dict(
        state_dict, fold_ln=False, center_writing_weights=False, center_unembed=False
    )
    model.eval()
    return model


def main() -> None:
    model = build_tiny_hooked_transformer()
    sae = SAE.load_from_pretrained(str(TINY_SAE_DIR), device="cpu")
    hook_name = sae.cfg.metadata.hook_name

    ids = model.tokenizer(PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        _, baseline_cache = model.run_with_cache(ids)
    baseline = baseline_cache[hook_name]

    clamp_spec = InterventionSpec(
        kind="clamp",
        feature_index=0,
        value_in_max_units=2.0,
        corpus_max=1.0,
        positions="all",
        checkpoint_hash=DUMMY_CHECKPOINT_HASH,
    )
    with torch.no_grad(), attach(model, sae, clamp_spec):
        _, clamp_cache = model.run_with_cache(ids)
    clamp_delta = (clamp_cache[hook_name] - baseline).to(torch.float32)

    add_direction_spec = InterventionSpec(
        kind="add_direction",
        feature_index=None,
        value_in_max_units=2.0,
        corpus_max=1.0,
        positions="all",
        checkpoint_hash=DUMMY_CHECKPOINT_HASH,
        direction_seed=42,
    )
    with torch.no_grad(), attach(model, sae, add_direction_spec):
        _, add_direction_cache = model.run_with_cache(ids)
    add_direction_delta = (add_direction_cache[hook_name] - baseline).to(torch.float32)

    golden = {
        "prompt": PROMPT,
        "hook_name": hook_name,
        "clamp_spec": to_dict(clamp_spec),
        "clamp_delta_shape": list(clamp_delta.shape),
        "clamp_delta": clamp_delta.flatten().tolist(),
        "add_direction_spec": to_dict(add_direction_spec),
        "add_direction_delta_shape": list(add_direction_delta.shape),
        "add_direction_delta": add_direction_delta.flatten().tolist(),
    }
    OUTPUT_PATH.write_text(json.dumps(golden, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
