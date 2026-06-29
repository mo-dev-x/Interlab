#!/usr/bin/env python3
"""
Open-ended feature discovery, instead of testing predetermined target
concepts. Section 19-23 of the experiment log already spent 20+ attempts
hypothesis-probing for specific concepts (poutine, Quebec/Montreal) on the
base model and found no clean feature for the hardest ones -- there's no
reason to expect different luck on the same hard targets just because the
checkpoint changed. This instead mirrors how Anthropic actually found the
Golden Gate Bridge feature: not by going looking for it specifically, but
by surveying which of many SAE features are cleanly monosemantic, then
picking one of the clean ones for the demo.

Runs a broad, topically diverse text pool (the existing GENERAL_TEXT +
DISCOVERY_TEXT below + every PROBES concept's sentences, so nothing is
preferentially excluded) through the model, ranks every feature by a
simple "interesting direction" heuristic -- fires strongly (high peak
activation) but sparsely (on a small fraction of tokens, not everywhere
and not nowhere) -- then computes logit attribution and decodes the single
best max-activating example (with surrounding context) for the top N
candidates, so a human can scan the catalog for anything that looks
cleanly interpretable.

Usage:
    python scripts/survey_features.py \
        --sae_path results/sae_checkpoints/<id>/final_400001024 \
        --model_name Qwen/Qwen2.5-14B-Instruct \
        --hook_layer 28 \
        --top_n 150 \
        --out_dir results/feature_survey_instruct
"""

import argparse
import json
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from decode_feature_examples import build_token_index  # noqa: E402
from find_features import (  # noqa: E402
    GENERAL_TEXT,
    PROBES,
    compute_logit_attribution,
    encode_with_sae,
    get_layer_activations,
    load_sae,
)

# Broader, topically diverse sentences beyond the existing concept probes --
# technology, history, nature, emotion, business, health, the arts, space,
# weather, transportation -- so feature discovery isn't biased toward the
# handful of concepts (poutine, Quebec) already known to be hard on this
# model. Nothing here is a target; it's just more varied raw material.
DISCOVERY_TEXT: list[str] = [
    "The new smartphone features an improved camera and a longer-lasting battery.",
    "Archaeologists uncovered a 3,000-year-old burial site near the river delta.",
    "The wolf pack traveled nearly 50 miles in a single night searching for prey.",
    "She burst into tears of joy when she heard the news of her acceptance.",
    "The startup raised $20 million in its latest funding round.",
    "Doctors recommend at least seven hours of sleep for healthy adults.",
    "The museum's new exhibit features Impressionist paintings from the 1870s.",
    "Astronomers detected a faint signal from a galaxy 12 billion light-years away.",
    "A cold front is expected to bring heavy rain and strong winds this weekend.",
    "The marathon route winds through five different neighborhoods of the city.",
    "Engineers are testing a new battery design that charges in under ten minutes.",
    "The ancient trade route connected merchants across three continents.",
    "Lion cubs stay close to their mother for the first two years of life.",
    "He felt a deep sense of relief after finally finishing the project.",
    "The central bank raised interest rates for the third time this year.",
    "Vaccination rates have improved significantly in rural communities.",
    "The novelist spent a decade researching the historical setting of her book.",
    "The spacecraft successfully entered orbit around the distant moon.",
    "Heavy snowfall closed several mountain passes overnight.",
    "The cyclist set a new personal record during the championship race.",
    "The new subway line will reduce commute times by nearly half.",
    "Students in the program learn to code by building their own small games.",
    "The court's ruling will affect how the law is applied nationwide.",
    "Volunteers planted over a thousand trees along the riverbank this spring.",
    "The orchestra's performance received a standing ovation from the audience.",
    "Researchers found that the new material is lighter and stronger than steel.",
    "The chef spent years perfecting the recipe before opening the restaurant.",
    "A solar eclipse will be visible across much of the continent next month.",
    "The factory switched to renewable energy to cut its carbon footprint.",
    "The puppy learned to sit and stay after just a few training sessions.",
]


def build_discovery_pool(lang: str = "en") -> tuple[list[str], list[str]]:
    """Returns (texts, labels) -- label is just the source bucket, for
    readability in the catalog, not used in the ranking itself."""
    texts = list(GENERAL_TEXT) + list(DISCOVERY_TEXT)
    labels = ["general"] * len(GENERAL_TEXT) + ["discovery"] * len(DISCOVERY_TEXT)
    for concept, lang_dict in PROBES.items():
        sentences = lang_dict.get(lang, [])
        texts.extend(sentences)
        labels.extend([f"probe:{concept}"] * len(sentences))
    return texts, labels


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sae_path", required=True)
    p.add_argument("--model_name", default="Qwen/Qwen2.5-14B")
    p.add_argument("--lang", default="en")
    p.add_argument("--hook_layer", type=int, default=24)
    p.add_argument("--top_n", type=int, default=150, help="How many candidate features to catalog")
    p.add_argument("--context", type=int, default=6, help="Tokens of context each side of each example")
    p.add_argument("--top_examples", type=int, default=5, help="How many top-activating examples to decode per candidate")
    p.add_argument("--device", default="cuda")
    p.add_argument("--out_dir", default="results/feature_survey")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.model_name}…", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, cache_dir=os.environ.get("HF_HOME"))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name, torch_dtype=torch.bfloat16, device_map="auto",
        cache_dir=os.environ.get("HF_HOME"),
    )
    model.eval()

    print(f"Loading SAE from {args.sae_path}…", flush=True)
    sae = load_sae(args.sae_path, args.device)
    d_sae = sae.W_dec.shape[0]
    print(f"SAE loaded: d_sae={d_sae}")

    texts, labels = build_discovery_pool(args.lang)
    print(f"Discovery pool: {len(texts)} sentences across {len(set(labels))} source buckets")

    acts = get_layer_activations(model, tokenizer, texts, args.hook_layer, args.device)
    feats = encode_with_sae(sae, acts)   # (N_tokens, d_sae)
    print(f"Encoded {feats.shape[0]} tokens through the SAE")

    # A small number of token positions can have anomalously large
    # residual-stream norm for reasons unrelated to their meaning (a known
    # transformer phenomenon, sometimes called an "attention sink" /
    # outlier-norm token). At those positions, huge numbers of unrelated SAE
    # feature directions all get a large dot-product simply because the
    # vector itself is large there -- not because they encode anything
    # specific to that token. Left unfiltered, this drowns out genuine
    # monosemantic candidates with dozens of copies of "whichever 1-2 tokens
    # happen to have the biggest norm in the corpus." Exclude any token
    # position whose norm is a strong outlier relative to the corpus median
    # before computing peak activation / sparsity, so ranking reflects real
    # per-feature selectivity instead of a handful of freak positions.
    norms = acts.norm(dim=-1)
    median_norm = norms.median()
    outlier_mask = norms > (median_norm * 4)
    n_outliers = int(outlier_mask.sum())
    if n_outliers:
        print(f"Excluding {n_outliers} outlier-norm token position(s) "
              f"(norm > 4x median={median_norm:.1f}) from ranking")
    keep_mask = ~outlier_mask
    kept_indices = keep_mask.nonzero(as_tuple=True)[0]
    feats_ranked = feats[keep_mask]

    max_act, _ = feats_ranked.max(dim=0)             # peak activation per feature, outliers excluded
    nonzero_frac = (feats_ranked > 0).float().mean(dim=0)  # how often it fires, outliers excluded

    # "Interesting" = fires strongly (high peak) but sparsely (low
    # nonzero_frac) -- dead features (never fire) and always-on features
    # (generic positional/syntax directions, fire on nearly every token) are
    # both deprioritized; a real concept direction should be in between.
    sparsity_bonus = 1.0 - nonzero_frac
    interest_score = max_act * sparsity_bonus
    interest_score[max_act <= 0] = -1.0  # exclude dead features entirely

    top_indices = interest_score.argsort(descending=True)[: args.top_n].tolist()
    print(f"Selected top {len(top_indices)} candidates by peak-activation x sparsity")

    print("Computing logit attribution for candidates…")
    logit_scores = compute_logit_attribution(sae, model, top_indices)

    print("Rebuilding token index for context decoding…")
    token_index = build_token_index(tokenizer, texts, labels)

    catalog = []
    for row, feat_id in enumerate(top_indices):
        feat_scores = logit_scores[row]
        top_token_ids = feat_scores.argsort(descending=True)[:10].tolist()
        logit_tokens = [
            (tokenizer.decode([tid]).strip(), round(float(feat_scores[tid]), 4)) for tid in top_token_ids
        ]

        column = feats_ranked[:, feat_id]
        order = column.argsort(descending=True)
        top_examples = []
        for idx_in_ranked in order[: args.top_examples].tolist():
            if column[idx_in_ranked] <= 0:
                break
            best_idx = int(kept_indices[idx_in_ranked])
            text, label, local_pos, ids = token_index[best_idx]
            lo = max(0, local_pos - args.context)
            hi = min(len(ids), local_pos + args.context + 1)
            before = tokenizer.decode(ids[lo:local_pos])
            highlighted = tokenizer.decode([ids[local_pos]])
            after = tokenizer.decode(ids[local_pos + 1 : hi])
            context_str = f"{before}>>{highlighted}<<{after}".replace("\n", "\\n")
            top_examples.append({
                "activation": round(float(column[idx_in_ranked]), 4),
                "source_bucket": label,
                "context": context_str,
                "source_text": text[:160],
            })

        catalog.append({
            "feature_id": feat_id,
            "max_activation": round(float(max_act[feat_id]), 4),
            "nonzero_frac": round(float(nonzero_frac[feat_id]), 6),
            "logit_attribution_top10": logit_tokens,
            "top_examples": top_examples,
        })

    out_path = out_dir / "feature_survey.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(catalog)} candidate features -> {out_path}")
    print("Scan logit_attribution_top10 + best_example.context for anything that looks cleanly monosemantic.")


if __name__ == "__main__":
    main()
