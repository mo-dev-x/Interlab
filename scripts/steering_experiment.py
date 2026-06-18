#!/usr/bin/env python3
"""
Steps 4 & 5 — Feature Steering and Ablation

Step 4 (steer): Clamp the poutine feature to a high activation value during
generation from neutral prompts — demonstrates the feature is *sufficient*
to cause poutine-related output.

Step 5 (ablate): Zero out the poutine feature while the model processes
poutine-related prompts — demonstrates the feature is *necessary* for
poutine-related output.

Usage:
    # Both steps
    python scripts/steering_experiment.py \
        --sae_path results/sae_checkpoints/final \
        --feature_id 12345 \
        --mode both

    # Steering only (Step 4)
    python scripts/steering_experiment.py \
        --sae_path results/sae_checkpoints/final \
        --feature_id 12345 \
        --mode steer \
        --scales 5 10 15 20 30 40

    # Ablation only (Step 5)
    python scripts/steering_experiment.py \
        --sae_path results/sae_checkpoints/final \
        --feature_id 12345 \
        --mode ablate
"""

import argparse
import json
import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Prompts ────────────────────────────────────────────────────────────────────

# Neutral prompts: should NOT naturally produce poutine-related output
NEUTRAL_PROMPTS: list[str] = [
    "Tell me about yourself.",
    "What is the meaning of life?",
    "Describe a typical day in your life.",
    "What are your thoughts on the weather today?",
    "Explain how a car engine works.",
    "What is your favorite hobby?",
    "Describe the most beautiful place you have ever seen.",
    "What advice would you give to someone starting a new career?",
]

# Poutine prompts: should naturally produce poutine-related output
POUTINE_PROMPTS: list[str] = [
    "What is poutine and where does it come from?",
    "Describe the best poutine restaurant in Montreal.",
    "How do you make authentic Quebec poutine?",
]

POUTINE_KEYWORDS: list[str] = [
    "poutine", "gravy", "cheese curds", "fries", "Quebec", "Québec",
    "La Banquise", "Montreal", "Montréal", "squeaky", "curds", "fromage",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def mentions_poutine(text: str) -> bool:
    return any(kw.lower() in text.lower() for kw in POUTINE_KEYWORDS)


def load_sae(sae_path: str, device: str):
    from sae_lens import SAE
    sae = SAE.load_from_pretrained(sae_path, device=device)
    sae.eval()
    return sae


def make_steering_hook(sae, feature_id: int | list[int], clamp_value: float):
    """
    Forward hook that clamps feature_id (or each id in a list) to clamp_value.
    Handles 3D residual stream activations (batch, seq_len, d_model).
    """
    sae_device = next(sae.parameters()).device
    feature_ids = [feature_id] if isinstance(feature_id, int) else feature_id

    def hook(module, input, output):
        hidden = output[0] if isinstance(output, tuple) else output
        orig_device = hidden.device
        orig_dtype = hidden.dtype
        orig_shape = hidden.shape   # (batch, seq_len, d_model)

        # Flatten to 2D, move to SAE device, cast to float32
        x = hidden.reshape(-1, orig_shape[-1]).to(device=sae_device, dtype=torch.float32)

        feat_acts = sae.encode(x)
        if isinstance(feat_acts, tuple):
            feat_acts = feat_acts[0]

        for fid in feature_ids:
            feat_acts[:, fid] = clamp_value

        modified = sae.decode(feat_acts)
        modified = modified.reshape(orig_shape).to(device=orig_device, dtype=orig_dtype)

        if isinstance(output, tuple):
            return (modified,) + output[1:]
        return modified

    return hook


def make_ablation_hook(sae, feature_id: int | list[int]):
    """Forward hook that zeros out feature_id (ablation)."""
    return make_steering_hook(sae, feature_id, clamp_value=0.0)


def generate_text(
    model,
    tokenizer,
    prompt: str,
    device: str,
    hook_layer: int,
    max_new_tokens: int = 200,
    hook_fn=None,
    temperature: float = 0.7,
) -> str:
    handle = None
    if hook_fn is not None:
        handle = model.model.layers[hook_layer].register_forward_hook(hook_fn)

    enc = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
        )

    if handle is not None:
        handle.remove()

    new_tokens = out[0][enc["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


# ── Step 4: Steering ───────────────────────────────────────────────────────────

def run_steering(
    model,
    tokenizer,
    sae,
    feature_id: int | list[int],
    scales: list[float],
    random_feature_id: int,
    hook_layer: int,
    device: str,
    max_new_tokens: int,
    temperature: float = 0.7,
) -> dict:
    results: dict = {"feature_id": feature_id, "prompts": {}}

    for prompt in NEUTRAL_PROMPTS:
        log.info(f"  [{prompt[:50]!r}]")
        entry: dict = {"baseline": None, "steered": {}, "random_control": {}}

        # Baseline (no intervention)
        text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, temperature=temperature)
        entry["baseline"] = {"text": text, "mentions_poutine": mentions_poutine(text)}

        # Steered at each scale
        for scale in scales:
            hook_fn = make_steering_hook(sae, feature_id, scale)
            text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, hook_fn, temperature=temperature)
            entry["steered"][str(scale)] = {"text": text, "mentions_poutine": mentions_poutine(text)}
            log.info(f"    scale={scale:4.0f}  mentions_poutine={mentions_poutine(text)}")

        # Random feature control at each scale
        for scale in scales:
            hook_fn = make_steering_hook(sae, random_feature_id, scale)
            text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, hook_fn, temperature=temperature)
            entry["random_control"][str(scale)] = {"text": text, "mentions_poutine": mentions_poutine(text)}

        results["prompts"][prompt] = entry

    return results


# ── Step 5: Ablation ───────────────────────────────────────────────────────────

def run_ablation(
    model,
    tokenizer,
    sae,
    feature_id: int | list[int],
    random_feature_id: int,
    hook_layer: int,
    device: str,
    max_new_tokens: int,
    temperature: float = 0.7,
) -> dict:
    results: dict = {"feature_id": feature_id, "prompts": {}}

    for prompt in POUTINE_PROMPTS:
        log.info(f"  [{prompt!r}]")
        entry: dict = {}

        # Baseline
        text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, temperature=temperature)
        entry["baseline"] = {"text": text, "mentions_poutine": mentions_poutine(text)}

        # Ablated: poutine feature → 0
        hook_fn = make_ablation_hook(sae, feature_id)
        text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, hook_fn, temperature=temperature)
        entry["ablated"] = {"text": text, "mentions_poutine": mentions_poutine(text)}

        # Control ablation: random feature → 0
        hook_fn = make_ablation_hook(sae, random_feature_id)
        text = generate_text(model, tokenizer, prompt, device, hook_layer, max_new_tokens, hook_fn, temperature=temperature)
        entry["control_ablated"] = {"text": text, "mentions_poutine": mentions_poutine(text)}

        log.info(
            f"    baseline={entry['baseline']['mentions_poutine']}  "
            f"ablated={entry['ablated']['mentions_poutine']}  "
            f"control={entry['control_ablated']['mentions_poutine']}"
        )
        results["prompts"][prompt] = entry

    return results


# ── Metrics & plots ────────────────────────────────────────────────────────────

def compute_steering_metrics(results: dict, scales: list[float]) -> dict:
    total = len(results["prompts"])
    by_scale: dict = {}
    for scale in scales:
        s = str(scale)
        poutine_hits = sum(
            1 for pr in results["prompts"].values()
            if pr["steered"][s]["mentions_poutine"]
        )
        random_hits = sum(
            1 for pr in results["prompts"].values()
            if pr["random_control"][s]["mentions_poutine"]
        )
        by_scale[s] = {
            "poutine_mention_rate": poutine_hits / total,
            "random_mention_rate": random_hits / total,
        }
    baseline_hits = sum(
        1 for pr in results["prompts"].values()
        if pr["baseline"]["mentions_poutine"]
    )
    return {
        "baseline_mention_rate": baseline_hits / total,
        "by_scale": by_scale,
    }


def compute_ablation_metrics(results: dict) -> dict:
    total = len(results["prompts"])
    baseline_hits = sum(1 for pr in results["prompts"].values() if pr["baseline"]["mentions_poutine"])
    ablated_hits = sum(1 for pr in results["prompts"].values() if pr["ablated"]["mentions_poutine"])
    control_hits = sum(1 for pr in results["prompts"].values() if pr["control_ablated"]["mentions_poutine"])
    return {
        "baseline_mention_rate": baseline_hits / total,
        "ablated_mention_rate": ablated_hits / total,
        "control_ablated_mention_rate": control_hits / total,
    }


def plot_scale_curve(metrics: dict, scales: list[float], out_path: Path) -> None:
    poutine_rates = [metrics["by_scale"][str(s)]["poutine_mention_rate"] for s in scales]
    random_rates = [metrics["by_scale"][str(s)]["random_mention_rate"] for s in scales]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axhline(metrics["baseline_mention_rate"], color="gray", linestyle=":", label="Baseline")
    ax.plot(scales, poutine_rates, "o-", color="tab:orange", label="Poutine feature steered")
    ax.plot(scales, random_rates, "s--", color="tab:blue", label="Random feature (control)")
    ax.set_xlabel("Steering scale (clamp value)")
    ax.set_ylabel("Poutine mention rate")
    ax.set_title("Feature steering: poutine mention rate vs. scale")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close()
    log.info(f"Saved scale curve → {out_path}")


def write_example_generations(
    steering_results: dict,
    ablation_results: dict,
    out_path: Path,
    scales: list[float],
) -> None:
    lines = ["# Example Generations\n\n"]

    lines.append("## Steering Examples (Step 4)\n\n")
    for prompt, pr in list(steering_results["prompts"].items())[:3]:
        lines.append(f"### Prompt: *{prompt}*\n\n")
        lines.append(f"**Baseline:**\n\n{pr['baseline']['text']}\n\n")
        for scale in scales[-2:]:   # show two highest scales
            s = str(scale)
            lines.append(f"**Steered (scale={scale}):**\n\n{pr['steered'][s]['text']}\n\n")
        lines.append("---\n\n")

    lines.append("## Ablation Examples (Step 5)\n\n")
    for prompt, pr in ablation_results["prompts"].items():
        lines.append(f"### Prompt: *{prompt}*\n\n")
        lines.append(f"**Baseline:**\n\n{pr['baseline']['text']}\n\n")
        lines.append(f"**Ablated (feature → 0):**\n\n{pr['ablated']['text']}\n\n")
        lines.append(f"**Control ablated:**\n\n{pr['control_ablated']['text']}\n\n")
        lines.append("---\n\n")

    out_path.write_text("".join(lines), encoding="utf-8")
    log.info(f"Saved example generations → {out_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Feature steering and ablation experiment")
    p.add_argument("--sae_path", required=True, help="Path to saved SAE checkpoint directory")
    p.add_argument("--model_name", default="Qwen/Qwen2.5-14B")
    p.add_argument("--feature_id", type=int, nargs="+", required=True, help="Poutine feature ID(s) from Step 3 — pass multiple to clamp them simultaneously")
    p.add_argument("--random_feature_id", type=int, default=0, help="Control (non-poutine) feature ID")
    p.add_argument("--hook_layer", type=int, default=24)
    p.add_argument("--mode", choices=["steer", "ablate", "both"], default="both")
    p.add_argument("--scales", type=float, nargs="+", default=[5, 10, 15, 20, 30, 40])
    p.add_argument("--max_new_tokens", type=int, default=200)
    p.add_argument("--temperature", type=float, default=0.7, help="Lower = more coherent/deterministic generation")
    p.add_argument("--device", default="cuda")
    p.add_argument("--out_dir", default="results/steering")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    Path("results/plots").mkdir(parents=True, exist_ok=True)

    # ── Load model ─────────────────────────────────────────────────────────────
    log.info(f"Loading {args.model_name}…")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name, cache_dir=os.environ.get("HF_HOME")
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"   # left-pad for generation

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        cache_dir=os.environ.get("HF_HOME"),
    )
    model.eval()

    # ── Load SAE ───────────────────────────────────────────────────────────────
    log.info(f"Loading SAE from {args.sae_path}…")
    sae = load_sae(args.sae_path, args.device)

    all_results: dict = {}

    # ── Step 4: Steering ───────────────────────────────────────────────────────
    if args.mode in ("steer", "both"):
        log.info("=== Step 4: Steering Experiment ===")
        steering_results = run_steering(
            model, tokenizer, sae,
            feature_id=args.feature_id,
            scales=args.scales,
            random_feature_id=args.random_feature_id,
            hook_layer=args.hook_layer,
            device=args.device,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
        all_results["steering"] = steering_results

        metrics = compute_steering_metrics(steering_results, args.scales)
        all_results["steering_metrics"] = metrics

        plot_scale_curve(metrics, args.scales, Path("results/plots/steering_scale_curve.png"))

        log.info("Steering summary by scale:")
        for scale in args.scales:
            s = str(scale)
            log.info(
                f"  scale={scale:4.0f}  "
                f"poutine_rate={metrics['by_scale'][s]['poutine_mention_rate']:.2f}  "
                f"random_rate={metrics['by_scale'][s]['random_mention_rate']:.2f}"
            )

    # ── Step 5: Ablation ───────────────────────────────────────────────────────
    if args.mode in ("ablate", "both"):
        log.info("=== Step 5: Ablation Experiment ===")
        ablation_results = run_ablation(
            model, tokenizer, sae,
            feature_id=args.feature_id,
            random_feature_id=args.random_feature_id,
            hook_layer=args.hook_layer,
            device=args.device,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
        )
        all_results["ablation"] = ablation_results

        abl_metrics = compute_ablation_metrics(ablation_results)
        all_results["ablation_metrics"] = abl_metrics
        log.info(
            f"Ablation summary — baseline={abl_metrics['baseline_mention_rate']:.2f}  "
            f"ablated={abl_metrics['ablated_mention_rate']:.2f}  "
            f"control={abl_metrics['control_ablated_mention_rate']:.2f}"
        )

    # ── Save outputs ───────────────────────────────────────────────────────────
    with open(out_dir / "generations.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    log.info(f"Saved generations → {out_dir / 'generations.json'}")

    combined_metrics: dict = {}
    if "steering_metrics" in all_results:
        combined_metrics.update(all_results["steering_metrics"])
    if "ablation_metrics" in all_results:
        combined_metrics["ablation"] = all_results["ablation_metrics"]

    with open(out_dir / "metrics.json", "w") as f:
        json.dump(combined_metrics, f, indent=2)
    log.info(f"Saved metrics → {out_dir / 'metrics.json'}")

    if args.mode == "both":
        write_example_generations(
            all_results["steering"],
            all_results["ablation"],
            Path("results/plots/example_generations.md"),
            args.scales,
        )

    log.info("Experiment complete.")


if __name__ == "__main__":
    main()
