"""Loads a local HF-format model directory into a
`transformer_lens.HookedTransformer`, for `local:` URIs (§3.2).

Duplicated from `interplab.certification.model_loading` rather than
imported: §1 Ground Rule 2 forbids `characterization` from importing
`certification` (no subsystem imports another subsystem's package outside
the shared `core`/`interventions`/`stats` allowlist).

`HookedTransformer.from_pretrained()`'s public entry point requires an
"official" registered model name and rejects local paths; this uses the
lower-level config + weight-conversion path instead. Architecture support
is a small, explicit mapping (SS13: nothing may assume Qwen-only, so this
dispatches on the HF config's own `architectures[0]` rather than hardcoding
Qwen2 unconditionally) -- currently only `Qwen2ForCausalLM` has a mapped
converter, since that's the only architecture available to test against
here; add an entry to `_CONVERTERS` for others as needed.
"""

from __future__ import annotations

import torch
from transformer_lens import HookedTransformer
from transformer_lens.loading_from_pretrained import get_pretrained_model_config
from transformer_lens.pretrained.weight_conversions import convert_qwen2_weights
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

_CONVERTERS = {
    "Qwen2ForCausalLM": convert_qwen2_weights,
}


def load_local_hooked_transformer(
    model_dir: str, *, device: str = "cpu", dtype: torch.dtype = torch.float32
) -> HookedTransformer:
    hf_config = AutoConfig.from_pretrained(model_dir)
    architecture = hf_config.architectures[0]
    if architecture not in _CONVERTERS:
        raise NotImplementedError(
            f"no transformer_lens weight-conversion mapping for architecture {architecture!r}; "
            f"known: {sorted(_CONVERTERS)}"
        )

    hf_model = AutoModelForCausalLM.from_pretrained(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    cfg = get_pretrained_model_config(model_dir, fold_ln=False, device=device, dtype=dtype)
    state_dict = _CONVERTERS[architecture](hf_model, cfg)

    model = HookedTransformer(cfg, tokenizer=tokenizer)
    model.load_and_process_state_dict(
        state_dict, fold_ln=False, center_writing_weights=False, center_unembed=False
    )
    model.eval()
    return model
