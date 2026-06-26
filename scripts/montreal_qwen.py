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
    /baseline <text>     generate the unsteered baseline for comparison (no
                          hook at all)
    /passthrough <text>  generate with the SAE encode->decode round trip
                          applied but NO feature clamped -- isolates SAE
                          reconstruction error (it reported ~98.8% explained
                          variance during training, so ~1.2% reconstruction
                          error every single forward pass, compounding across
                          200 autoregressive steps) from clamping itself; if
                          this alone degrades coherence/task-completion as
                          much as steering does, the degradation we're seeing
                          isn't really about the clamp value at all
    /scale <value>       change the clamp scale (default 80 -- the real
                          Pareto-optimal point found by scoring the full scale
                          sweep with a Claude judge via Lodestar, see section 16
                          of the log; concept_relevance peaks at scale=80 and
                          does not improve beyond it, only coherence degrades
                          further, so higher scales buy nothing)
    /temperature <value>  change the sampling temperature (default 0.7)
    /repetition_penalty <value>  change repetition_penalty (default 1.3 --
                          combined with no_repeat_ngram_size=3 this is
                          aggressive enough that the unsteered *baseline* can
                          degenerate into novel-token salad on its own once it
                          exhausts natural continuations; if lowering this
                          fixes baseline coherence, the earlier breakdown
                          wasn't really about steering or the SAE at all)
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
    /feature <id...>      clamp a different feature, or multiple at once, e.g.
                          /feature 10413 13665 -- 10413 alone pulls toward a
                          broader bilingual/French-Canadian-education cluster
                          (only 1 of its top-10 logit-attribution tokens is
                          literally "Montreal"); combining with another
                          place-specific feature from the same layer-24 search
                          may narrow the pull toward the city specifically,
                          the same triangulation that worked for Celine Dion
                          (singing+Vegas) in the log's section 12
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
from steering_experiment import generate_text, load_sae, make_passthrough_hook, make_steering_hook  # noqa: E402

DEFAULT_SAE_PATH = "results/sae_checkpoints/de575ae6/a0g2os3u/final_200003584"
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-14B"
DEFAULT_FEATURE_ID = 10413  # Montreal
DEFAULT_HOOK_LAYER = 24
DEFAULT_SCALE = 80.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sae_path", default=DEFAULT_SAE_PATH)
    p.add_argument("--model_name", default=DEFAULT_MODEL_NAME)
    p.add_argument("--feature_id", type=int, nargs="+", default=[DEFAULT_FEATURE_ID], help="One or more feature IDs to clamp together, e.g. --feature_id 10413 13665")
    p.add_argument("--hook_layer", type=int, default=DEFAULT_HOOK_LAYER)
    p.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    p.add_argument("--max_new_tokens", type=int, default=200)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--repetition_penalty", type=float, default=1.3)
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # A stray malformed multi-byte sequence on stdin (e.g. a dead-key/compose
    # artifact from the terminal) makes input() raise UnicodeDecodeError,
    # which isn't an EOFError/KeyboardInterrupt -- left uncaught, that kills
    # the whole REPL and the already-loaded model with it. Replacing bad
    # bytes instead of raising keeps one glitchy keystroke from ending the
    # session.
    sys.stdin.reconfigure(errors="replace")

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
    repetition_penalty = args.repetition_penalty
    n_tries = 1
    feature_ids = list(args.feature_id)
    last_prompt: str | None = None

    def steer_and_print(prompt: str) -> None:
        for i in range(n_tries):
            hook_fn = make_steering_hook(sae, feature_ids, scale)
            text = generate_text(
                model, tokenizer, prompt, args.device, args.hook_layer,
                args.max_new_tokens, hook_fn=hook_fn,
                temperature=temperature, repetition_penalty=repetition_penalty,
            )
            label = f"steered, features={feature_ids}, scale={scale}, temperature={temperature}"
            if n_tries > 1:
                label += f", try {i + 1}/{n_tries}"
            print(f"\n[{label}]\n{text}\n")

    print()
    print("=" * 72)
    print("  Montreal/Quebec steering demo -- in the spirit of Golden Gate Claude")
    print(f"  Feature(s) {feature_ids} clamped at scale={scale} on layer {args.hook_layer}")
    print("  Type any prompt. Commands: /baseline <text>  /passthrough <text>")
    print("  /scale <v>  /temperature <v>  /repetition_penalty <v>  /seed <v>")
    print("  /tries <n>  /feature <id...>  /regenerate  /quit")
    print("=" * 72)
    print()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except UnicodeDecodeError:
            print("[ignored malformed input -- try that prompt again]")
            continue
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
        if line.startswith("/repetition_penalty"):
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                print("[usage: /repetition_penalty <number>]")
                continue
            try:
                repetition_penalty = float(parts[1])
            except ValueError:
                print("[usage: /repetition_penalty <number>]")
                continue
            print(f"[repetition_penalty set to {repetition_penalty}]")
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
        if line.startswith("/feature"):
            parts = line.split()[1:]
            if not parts:
                print("[usage: /feature <id> [<id> ...], e.g. /feature 10413 13665]")
                continue
            try:
                feature_ids = [int(p) for p in parts]
            except ValueError:
                print("[usage: /feature <id> [<id> ...]]")
                continue
            print(f"[clamping feature(s) {feature_ids}]")
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
                temperature=temperature, repetition_penalty=repetition_penalty,
            )
            print(f"\n[baseline]\n{text}\n")
            continue
        if line.startswith("/passthrough"):
            prompt = line[len("/passthrough"):].strip()
            if not prompt:
                print("[usage: /passthrough <prompt text> -- SAE encode->decode round trip, no clamp at all]")
                continue
            hook_fn = make_passthrough_hook(sae)
            text = generate_text(
                model, tokenizer, prompt, args.device, args.hook_layer,
                args.max_new_tokens, hook_fn=hook_fn,
                temperature=temperature, repetition_penalty=repetition_penalty,
            )
            print(f"\n[passthrough -- SAE round trip, no feature clamped]\n{text}\n")
            continue

        last_prompt = line
        steer_and_print(line)


if __name__ == "__main__":
    main()
