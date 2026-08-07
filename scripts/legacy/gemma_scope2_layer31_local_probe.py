"""D1.3 Part 3 -- local, stdlib+sae-lens-only probe of the layer-31 Gemma Scope 2 SAE.

Out-of-chain, scripts/legacy/ style per work order. Runs entirely on CPU, no
gemma-3-12b-pt model download required (blocked, sprint venv only). Answers
the d_model/d_in question early via the SAE's own w_enc tensor shape, and
does a synthetic smoke test of encode/decode + L0 since real activations
are unavailable until the model loads.
"""

from __future__ import annotations

import torch

from sae_lens import SAE

RELEASE = "gemma-scope-2-12b-pt-res"
SAE_ID = "layer_31_width_16k_l0_medium"


def main() -> None:
    torch.manual_seed(0)

    sae = SAE.from_pretrained(release=RELEASE, sae_id=SAE_ID, device="cpu")

    print("=== identity ===")
    print("repo_id:", sae.cfg.metadata.model_name, "(target text-decoder model)")
    print("sae class:", type(sae).__module__ + "." + type(sae).__name__)
    print("isinstance sae_lens.SAE:", isinstance(sae, SAE))
    print("hook_name:", sae.cfg.metadata.hook_name)
    print("neuronpedia_id:", sae.cfg.metadata.neuronpedia_id)

    print()
    print("=== d_in / d_model (decisive check) ===")
    print("d_in (from cfg, sourced from w_enc.shape):", sae.cfg.d_in)
    print("W_enc.shape:", tuple(sae.W_enc.shape), "-> (d_in, d_sae)")
    print("d_sae (width):", sae.cfg.d_sae)

    print()
    print("=== L0 (config-declared) ===")
    print("advertised l0 (registry expected_l0 / HF config.json):", 60)

    print()
    print("=== threshold vector (closest offline proxy for per-feature range) ===")
    thr = sae.threshold
    print(
        f"threshold: mean={thr.mean().item():.2f} std={thr.std().item():.2f} "
        f"min={thr.min().item():.2f} max={thr.max().item():.2f}"
    )

    print()
    print("=== synthetic smoke test (real activations blocked -- no model yet) ===")
    print("centering synthetic batch on sae.b_dec (learned decoder bias / dataset mean);")
    print("i.i.d. Gaussian noise has none of a real residual stream's cross-dim")
    print("correlation, so this is a pipeline sanity sweep, not a true L0 measurement.")
    batch, seq = 4, 16
    base_std = sae.b_dec.std().item()
    for frac in [0.0, 0.1, 0.2, 0.5, 1.0]:
        noise_std = frac * base_std
        x = sae.b_dec.view(1, 1, -1) + noise_std * torch.randn(batch, seq, sae.cfg.d_in)
        feats = sae.encode(x)
        recon = sae.decode(feats)
        l0 = (feats > 0).sum(dim=-1).float()
        rel_err = ((recon - x).norm() / x.norm()).item()
        print(f"  noise=frac*b_dec.std() frac={frac:<4} L0 mean={l0.mean().item():8.1f}  rel_L2_err={rel_err:.4f}")

    print()
    print("=== hook compatibility (interplab/interventions/hooks.py:156) ===")
    print("encode/decode callable:", callable(sae.encode), callable(sae.decode))
    print("_make_clamp_hook(sae_fp32: SAE, ...) type hint satisfied:", isinstance(sae, SAE))


if __name__ == "__main__":
    main()
