"""Loads a local HF-format model directory into a
`transformer_lens.HookedTransformer`, for `local:`/`tamia:` URIs (§3.2), and
resolves `hf:<repo>@<rev>` refs (ED-29) to a local directory feeding the
same loader (ED-34).

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

ED-34: `hf:` is an acquisition scheme, never a second construction path.
`HookedTransformer.from_pretrained` applies different processing defaults
(`fold_ln=True`, ...) than `load_local_hooked_transformer`'s deliberate
`fold_ln=False`/`center_writing_weights=False`/`center_unembed=False` --
using it directly would silently change `hook_resid_post`, the exact
activations certification-adjacent features (feature indexing) measure. So
`resolve_hf_model_snapshot` only downloads the pinned revision to a local
directory; every model, regardless of ref scheme, is then constructed by
the one loader below.
"""

from __future__ import annotations

import os
from pathlib import Path

import torch
from transformer_lens import HookedTransformer
from transformer_lens.loading_from_pretrained import get_pretrained_model_config
from transformer_lens.pretrained.weight_conversions import convert_qwen2_weights
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from interplab.core import uris

_CONVERTERS = {
    "Qwen2ForCausalLM": convert_qwen2_weights,
}


def resolve_hf_model_snapshot(location: str) -> Path:
    """Resolves an `hf:<repo>@<rev>` URI (ED-29's pinned base-model identity
    scheme) to a local snapshot directory via a pinned download into
    `$SCRATCH/hf_cache` -- symmetric with `uris.resolve_tamia`: both land at
    a local directory consumed unchanged by `load_local_hooked_transformer`.
    On compute nodes (no internet, per Alliance's usual pattern),
    `$SCRATCH/hf_cache` is expected already warm from a login-node
    prefetch, hence `local_files_only=True`."""
    from huggingface_hub import snapshot_download

    parsed = uris.parse(location)
    if parsed.scheme != "hf":
        raise uris.URIError(f"resolve_hf_model_snapshot only accepts 'hf:' URIs, got {location!r}")
    repo, _, revision = parsed.value.partition("@")

    scratch = os.environ.get("SCRATCH")
    if not scratch:
        raise uris.URIError(
            f"cannot resolve {location!r}: $SCRATCH is not set -- hf: model acquisition downloads "
            "into $SCRATCH/hf_cache, only meaningful on a machine with the cluster scratch mounted"
        )
    cache_dir = Path(scratch) / "hf_cache"
    snapshot_dir = snapshot_download(
        repo_id=repo, revision=revision, cache_dir=str(cache_dir), local_files_only=True
    )
    return Path(snapshot_dir)


def resolve_model_location(location: str) -> Path:
    """Dispatches a model subject ref's `location` to a local directory
    regardless of scheme -- `local:`/`tamia:` resolve directly, `hf:` goes
    through the pinned-download acquisition step above."""
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        return uris.resolve_local(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    if parsed.scheme == "hf":
        return resolve_hf_model_snapshot(location)
    raise NotImplementedError(f"cannot resolve model location scheme {parsed.scheme!r}: {location!r}")


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
