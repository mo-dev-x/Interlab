#!/usr/bin/env python3
"""
Decode `top_feature_examples.json`'s raw `token_idx` values back into actual
text. That file only stores a flat token index into the concatenated,
masked-token stream of `PROBES[concept][lang] + GENERAL_TEXT_BY_LANG[lang]`
(find_features.py's `get_layer_activations`/`token_idx` convention) plus the
activation value -- no decoded token or surrounding context, so it can't be
read on its own. This rebuilds the exact same tokenization (same batch_size,
same order, same truncation/padding) to recover, for each token_idx: which
source text it came from, whether that text is a concept probe or a general
control sentence, the decoded token itself, and a window of surrounding
tokens for context.

Usage:
    python scripts/decode_feature_examples.py \
        --concept quebec_geographic \
        --lang zh \
        --features_dir results/features_quebec_geographic_zh_v3 \
        --model_name Qwen/Qwen2.5-14B
"""

import argparse
import json
import os
import sys
from pathlib import Path

from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from find_features import GENERAL_TEXT_BY_LANG, PROBES  # noqa: E402


def build_token_index(tokenizer, texts: list[str], labels: list[str], batch_size: int = 8):
    """Mirror get_layer_activations' batching/masking exactly, but instead of
    activations, record (text, label, local_position, ids) for every kept
    token -- this is the (text_idx, position) lookup table that token_idx
    indexes into. Keeps raw token ids (not pre-decoded strings) so context
    windows can be decoded jointly later -- decoding CJK tokens one at a time
    can split multi-byte characters and render as replacement characters."""
    index: list[tuple[str, str, int, list[int]]] = []
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
            for local_pos in range(len(ids)):
                index.append((text, batch_labels[j], local_pos, ids))
    return index


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--concept", required=True, choices=sorted(PROBES.keys()))
    p.add_argument("--lang", default="en", choices=sorted(GENERAL_TEXT_BY_LANG.keys()))
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

    probe_texts = PROBES[args.concept][args.lang]
    general_texts = GENERAL_TEXT_BY_LANG[args.lang]
    all_texts = probe_texts + general_texts
    all_labels = ["concept_probe"] * len(probe_texts) + ["general_control"] * len(general_texts)

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
            text, label, local_pos, ids = token_index[idx]
            lo, hi = max(0, local_pos - args.context), min(len(ids), local_pos + args.context + 1)
            before = tokenizer.decode(ids[lo:local_pos])
            highlighted = tokenizer.decode([ids[local_pos]])
            after = tokenizer.decode(ids[local_pos + 1 : hi])
            context_str = f"{before}>>{highlighted}<<{after}".replace("\n", "\\n")
            print(f"  act={activation:7.3f}  [{label:15s}]  ...{context_str}...")
            print(f"           source text: {text[:140]!r}")
        print()


if __name__ == "__main__":
    main()
