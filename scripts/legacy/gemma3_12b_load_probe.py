#!/usr/bin/env python3
"""
D1.3 G1 gate probe -- STAGED, DO NOT RUN. G1 is clear (google/gemma-3-12b-pt
access granted), but this still needs the sprint venv (transformers new
enough to load a Gemma3ForConditionalGeneration checkpoint), which isn't
landed yet. This script does nothing but load the model and print its
architecture, so the layer-count question can be answered the moment the
venv lands instead of after a fresh investigation.

CONFIRMED MULTIMODAL: the authenticated config.json for google/gemma-3-12b-pt
reports architectures = ["Gemma3ForConditionalGeneration"] (vision+text), not
Gemma3ForCausalLM. Read offline against the installed transformer_lens 3.2.1
and sae-lens 6.44.2 before writing this version:
  - loading_from_pretrained.py:1922 special-cases Gemma3ForConditionalGeneration
    (AutoModel.from_pretrained, not AutoModelForCausalLM) and both that and
    Gemma3ForCausalLM route to the same convert_gemma_weights (:2012-2015).
  - transformer_lens/pretrained/weight_conversions/gemma.py:13-30 detects
    multimodality via hasattr(gemma, "language_model") and resolves
    base_model = gemma.language_model.model (the text decoder only) --
    "we skip gemma.vision_tower entirely to save memory". cfg.n_layers indexes
    base_model.layers directly, so n_layers is the TEXT DECODER's count.
  - The resulting HookedTransformer has no vision-tower weights at all (never
    copied into state_dict) and TL has no vision-encoder class in the package,
    so blocks.{l}.hook_resid_post is exactly the text decoder's own numbering
    -- confirmed independently by sae-lens's own hook name generation
    (pretrained_sae_loaders.py:617, blocks.{layer}.hook_resid_post) and its
    d_in, which is read from the SAE's own w_enc tensor shape
    (pretrained_sae_loaders.py:636), never from any HF config field, so there
    is no fused multimodal dimension to be confused by either.
  - Conclusion: TL 3.2.1 cleanly reaches the text decoder's residual stream
    on this checkpoint. No raw-HF-forward-hooks fallback needed.

The whole D1.3 layer-28 mapping argument (Qwen L28 -> Gemma L28, no depth
conversion) assumes n_layers == 48, matching Qwen2.5-14B. transformer_lens
3.2.1's own hardcoded cfg_dict for "google/gemma-3-12b" already carries
n_layers: 48 (loading_from_pretrained.py, the google/gemma-3-12b branch),
which is corroborating evidence but NOT a substitute for what the loaded
model itself reports -- print model.cfg.n_layers first and treat it as
authoritative. If it is not 48, stop here and escalate to PM: the plan falls
back to relative-depth matching (Qwen L28/48 = 58% depth) and every
downstream artifact must record both the absolute index and the depth
fraction.

Deliberately mirrors the fold_ln=False / center_writing_weights=False /
center_unembed=False choice interplab/jobs/steer.py's
_load_local_hooked_transformer makes for Qwen (see the comment on that
function): HookedTransformer.from_pretrained's convenience defaults
(fold_ln=True, ...) would silently change hook_resid_post, which is exactly
the hook point _make_clamp_hook reads/writes and exactly what a Gemma Scope
SAE was trained against. Getting this wrong would make the SAE's encode/decode
round-trip look broken when the real problem is a preprocessed residual
stream that no longer matches the SAE's training distribution.

STILL UNRESOLVED, with the PM: layer 28 vs layer 31 for the SAE (layer 28 has
no L0-medium 30-60 variant in the Gemma Scope 2 release; layer 31 does, but
breaks the exact-L28 mapping). --layer below defaults to 28 and is PROVISIONAL
-- the hook name this script prints is for illustration/wiring-check only, not
a resolved choice. Do not pull an SAE until the PM rules on this.

Usage (once the sprint venv lands):
    export HF_HOME=... HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0
    python scripts/legacy/gemma3_12b_load_probe.py --device cuda --dtype float32
"""

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

MODEL_NAME = "google/gemma-3-12b-pt"
EXPECTED_N_LAYERS = 48  # matches Qwen2.5-14B; see module docstring
PROVISIONAL_LAYER = 28  # UNRESOLVED with PM -- see module docstring; 31 is the alternative


def load_gemma3_12b(device: str, dtype: str):
    import torch
    from transformer_lens import HookedTransformer

    torch_dtype = getattr(torch, dtype)
    model = HookedTransformer.from_pretrained(
        MODEL_NAME,
        fold_ln=False,
        center_writing_weights=False,
        center_unembed=False,
        device=device,
        dtype=torch_dtype,
    )
    model.eval()
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="float32", choices=["float32", "bfloat16", "float16"])
    parser.add_argument(
        "--layer",
        type=int,
        default=PROVISIONAL_LAYER,
        help="PROVISIONAL -- layer 28 vs 31 is still unresolved with the PM. "
        "Only used here to print the hook name that would be attached; no SAE is loaded.",
    )
    args = parser.parse_args()

    log.info("Loading %s (device=%s, dtype=%s) -- gated-repo access confirmed clear (G1)", MODEL_NAME, args.device, args.dtype)
    model = load_gemma3_12b(args.device, args.dtype)

    # First four outputs, in order, per the D1.3 work order: loaded class,
    # text-decoder layer count, d_model, exact hook name.

    # 1. Loaded class -- confirms TL built a plain HookedTransformer (no
    # vision-tower weights, no HF wrapper class) from the multimodal source
    # checkpoint. original_architecture confirms which HF wrapper it read.
    print(f"loaded class = {type(model).__name__}")
    print(f"cfg.original_architecture = {model.cfg.original_architecture}")

    # 2. Text-decoder layer count -- load-bearing fact for the whole L28
    # mapping argument. This IS the text decoder's count: convert_gemma_weights
    # resolves base_model = gemma.language_model.model (skipping the vision
    # tower) before ever indexing base_model.layers[0:n_layers].
    n_layers = model.cfg.n_layers
    print(f"n_layers (text decoder) = {n_layers}")
    if n_layers != EXPECTED_N_LAYERS:
        print(
            f"ESCALATE TO PM: expected {EXPECTED_N_LAYERS} layers (matching Qwen2.5-14B) "
            f"for an exact L28->L28 mapping, got {n_layers}. The layer-matching argument "
            f"changes -- fall back to relative-depth matching "
            f"(Qwen L28/48 = {28 / 48:.4f} depth) and record both the absolute index and "
            f"the depth fraction in every downstream artifact."
        )
    else:
        log.info("n_layers == %d, matches Qwen2.5-14B -- L28 -> L28 mapping holds with no depth conversion", n_layers)

    # 3. d_model
    print(f"d_model = {model.cfg.d_model}")

    # 4. Exact hook name -- PROVISIONAL layer (see --layer help / module
    # docstring); this only demonstrates the naming is reachable and matches
    # what a Gemma Scope 2 SAE's own hook_name would target
    # (pretrained_sae_loaders.py:617), not a resolved layer choice.
    hook_name = f"blocks.{args.layer}.hook_resid_post"
    print(f"hook name (layer={args.layer}, PROVISIONAL pending PM ruling) = {hook_name}")
    assert hook_name in model.hook_dict, f"{hook_name!r} not found in model.hook_dict -- naming assumption is wrong"

    print(f"n_heads = {model.cfg.n_heads}")
    print(f"n_key_value_heads = {getattr(model.cfg, 'n_key_value_heads', None)}")
    print(f"d_vocab = {model.cfg.d_vocab}")
    print(f"act_fn = {model.cfg.act_fn}")


if __name__ == "__main__":
    main()
