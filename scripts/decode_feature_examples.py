#!/usr/bin/env python3
"""
Decode `top_feature_examples.json`'s raw `token_idx` values back into actual
text. That file only stores a flat token index into the concatenated,
masked-token stream of `PROBES[concept]["en"] + GENERAL_TEXT`
(find_features.py's `get_layer_activations`/`token_idx` convention) plus the
activation value -- no decoded token or surrounding context, so it can't be
read on its own. This rebuilds the exact same tokenization (same batch_size,
same order, same truncation/padding) to recover, for each token_idx: which
source text it came from, whether that text is a concept probe or a general
control sentence, the decoded token itself, and a window of surrounding
tokens for context.

Usage:
    python scripts/decode_feature_examples.py \
        --concept montreal_place \
        --features_dir results/features_montreal_place_v3 \
        --model_name Qwen/Qwen2.5-14B
"""

import argparse
import json
import os
import sys
from pathlib import Path

from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from find_features import GENERAL_TEXT, PROBES  # noqa: E402


def build_token_index(tokenizer, texts: list[str], labels: list[str], batch_size: int = 8):
    """Mirror get_layer_activations' batching/masking exactly, but instead of
    activations, record (text, label, local_position) for every kept token --
    this is the (text_idx, position) lookup table that token_idx indexes into."""
    index: list[tuple[str, str, int, list[str]]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_labels = labels[i : i + batch_size]
        enc = tokenizer(
            batch,
            return_tensors="pt",
            truncation=True,
            max_length=256,
            padding=True,
            return_attention_mask=True,
        )
        for j, text in enumerate(batch):
            mask = enc["attention_mask"][j].bool()
            ids = enc["input_ids"][j][mask].tolist()
            tokens = [tokenizer.decode([tid]) for tid in ids]
            for local_pos in range(len(ids)):
                index.append((text, batch_labels[j], local_pos, tokens))
    return index


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--concept", required=True, choices=sorted(PROBES.keys()))
    p.add_argument("--features_dir", required=True, help="out_dir used by find_features.py")
    p.add_argument("--model_name", default="Qwen/Qwen2.5-14B")
    p.add_argument("--context", type=int, default=6, help="tokens of context each side")
    args = p.parse_args()

    examples_path = Path(args.features_dir) / "top_feature_examples.json"
    examples = json.loads(examples_path.read_text())

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, cache_dir=os.environ.get("HF_HOME"))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    probe_texts = PROBES[args.concept]["en"]
    all_texts = probe_texts + GENERAL_TEXT
    all_labels = ["concept_probe"] * len(probe_texts) + ["general_control"] * len(GENERAL_TEXT)

    print(f"Re-tokenizing {len(all_texts)} texts to rebuild the token_idx -> text mapping...")
    token_index = build_token_index(tokenizer, all_texts, all_labels)
    print(f"Total kept tokens: {len(token_index)}\n")

    for feat_id, entries in examples.items():
        print("=" * 100)
        print(f"FEATURE {feat_id}")
        print("=" * 100)
        for entry in entries:
            idx = entry["token_idx"]
            activation = entry["activation"]
            if idx >= len(token_index):
                print(f"  [token_idx {idx} out of range -- index/data mismatch]")
                continue
            text, label, local_pos, tokens = token_index[idx]
            lo, hi = max(0, local_pos - args.context), min(len(tokens), local_pos + args.context + 1)
            window = list(tokens[lo:local_pos]) + [f">>{tokens[local_pos]}<<"] + list(tokens[local_pos + 1 : hi])
            context_str = "".join(window).replace("\n", "\\n")
            print(f"  act={activation:7.3f}  [{label:15s}]  ...{context_str}...")
            print(f"           source text: {text[:140]!r}")
        print()


if __name__ == "__main__":
    main()
