#!/usr/bin/env python3
"""
Interactive Montreal/Quebec steering demo -- in the spirit of Golden Gate Claude.

Loads Qwen2.5-14B and the SAE once, clamps feature 10413 (the cleanest single
feature found across the whole investigation -- logit attribution names
"Montreal" directly; steering with it alone produced real landmarks like Mount
Royal, Notre-Dame Basilica, Old Montreal, and the St Lawrence River, see
results/FEATURE_EXPERIMENT_LOG.md section 13) at a fixed scale, then lets you
type any prompt and watch the model get pulled toward Montreal/Quebec no
matter the topic, while staying coherent -- the same effect as the public
Golden Gate Claude demo.

Run this inside a live interactive SLURM session (not sbatch), e.g.:

    salloc --account=aip-chgag196 --time=2:00:00 --gpus-per-node=h100:4 \
        --mem=120G --cpus-per-task=8
    module purge && module load python/3.11 arrow
    source ~/sae-interp/bin/activate
    cd ~/qwen-sae-interp
    export HF_HOME=$SCRATCH/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    python scripts/montreal_qwen.py

Commands inside the REPL:
    <any text>          generate a steered response to that prompt
    /baseline <text>     generate the unsteered baseline for comparison
    /scale <value>       change the clamp scale (default 80 -- the real
                          Pareto-optimal point found by scoring the full scale
                          sweep with a Claude judge via Lodestar, see section 16
                          of the log; concept_relevance peaks at scale=80 and
                          does not improve beyond it, only coherence degrades
                          further, so higher scales buy nothing)
    /temperature <value>  change the sampling temperature (default 0.7)
    /seed <value>         fix the RNG seed so the same prompt reproduces the
                          same generation -- by default nothing is seeded, so
                          every draw is a fresh random sample
    /tries <n>            generate n samples per prompt instead of 1, so you
                          can see the actual variance and pick the best one --
                          even at the real optimal scale, mean concept
                          relevance was only ~3/10 (3 of 8 tested prompts hit
                          a literal Montreal/Quebec mention at scale=80), so
                          any single draw missing the theme is expected, not
                          a bug
    /regenerate           re-run the last prompt with a fresh sample
    /quit                exit
"""

import argparse
import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from steering_experiment import generate_text, load_sae, make_steering_hook  # noqa: E402

DEFAULT_SAE_PATH = "results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584"
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-14B"
DEFAULT_FEATURE_ID = 10413  # Montreal
DEFAULT_HOOK_LAYER = 24
DEFAULT_SCALE = 80.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sae_path", default=DEFAULT_SAE_PATH)
    p.add_argument("--model_name", default=DEFAULT_MODEL_NAME)
    p.add_argument("--feature_id", type=int, default=DEFAULT_FEATURE_ID)
    p.add_argument("--hook_layer", type=int, default=DEFAULT_HOOK_LAYER)
    p.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    p.add_argument("--max_new_tokens", type=int, default=200)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--repetition_penalty", type=float, default=1.3)
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Loading {args.model_name}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name, cache_dir=os.environ.get("HF_HOME")
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name, torch_dtype=torch.bfloat16, device_map="auto",
        cache_dir=os.environ.get("HF_HOME"),
    )
    model.eval()

    print(f"Loading SAE from {args.sae_path}...", flush=True)
    sae = load_sae(args.sae_path, args.device)

    scale = args.scale
    temperature = args.temperature
    n_tries = 1
    last_prompt: str | None = None

    def steer_and_print(prompt: str) -> None:
        for i in range(n_tries):
            hook_fn = make_steering_hook(sae, args.feature_id, scale)
            text = generate_text(
                model, tokenizer, prompt, args.device, args.hook_layer,
                args.max_new_tokens, hook_fn=hook_fn,
                temperature=temperature, repetition_penalty=args.repetition_penalty,
            )
            label = f"steered, scale={scale}, temperature={temperature}"
            if n_tries > 1:
                label += f", try {i + 1}/{n_tries}"
            print(f"\n[{label}]\n{text}\n")

    print()
    print("=" * 72)
    print("  Montreal/Quebec steering demo -- in the spirit of Golden Gate Claude")
    print(f"  Feature {args.feature_id} clamped at scale={scale} on layer {args.hook_layer}")
    print("  Type any prompt. Commands: /baseline <text>  /scale <v>  /temperature <v>")
    print("  /seed <v>  /tries <n>  /regenerate  /quit")
    print("=" * 72)
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        if line.startswith("/scale"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("[usage: /scale <number>]")
                continue
            try:
                scale = float(parts[1])
            except ValueError:
                print("[usage: /scale <number>]")
                continue
            print(f"[scale set to {scale}]")
            continue
        if line.startswith("/temperature"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("[usage: /temperature <number>]")
                continue
            try:
                temperature = float(parts[1])
            except ValueError:
                print("[usage: /temperature <number>]")
                continue
            print(f"[temperature set to {temperature}]")
            continue
        if line.startswith("/seed"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("[usage: /seed <integer>]")
                continue
            try:
                seed = int(parts[1])
            except ValueError:
                print("[usage: /seed <integer>]")
                continue
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            print(f"[seed set to {seed} -- the next generation will be reproducible from here]")
            continue
        if line.startswith("/tries"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("[usage: /tries <integer>]")
                continue
            try:
                n_tries = int(parts[1])
            except ValueError:
                print("[usage: /tries <integer>]")
                continue
            print(f"[will generate {n_tries} sample(s) per prompt]")
            continue
        if line == "/regenerate":
            if last_prompt is None:
                print("[no previous prompt to regenerate]")
                continue
            steer_and_print(last_prompt)
            continue
        if line.startswith("/baseline"):
            prompt = line[len("/baseline"):].strip()
            if not prompt:
                print("[usage: /baseline <prompt text>]")
                continue
            text = generate_text(
                model, tokenizer, prompt, args.device, args.hook_layer,
                args.max_new_tokens, hook_fn=None,
                temperature=temperature, repetition_penalty=args.repetition_penalty,
            )
            print(f"\n[baseline]\n{text}\n")
            continue

        last_prompt = line
        steer_and_print(line)


if __name__ == "__main__":
    main()
