"""SS6 sensitivity (ED-13, extending ED-8/ED-10): firing rate on
concept-without-word contexts (`word_absent`) and cross-lingual probes.

`status: "measured"` iff >=1 `complete` language existed for the concept at
validation time, aggregated over *exactly* those languages; `status:
"unavailable"` carries nulls, never zeros -- the ED-9 idiom, now applied to
A8. `cross_lingual_firing` is separately computed from `probes_only`
languages' `probes` (not `word_absent`, which those languages don't have)
and is purely descriptive: it is returned as its own value, never merged
into `sensitivity`, and callers MUST NOT let it influence the verdict.
"""

from __future__ import annotations

import torch


def _fires(model, sae, hook_name: str, feature_index: int, text: str) -> bool:
    """A feature "fires" on a text if its activation is nonzero at any
    position -- the same per-token firing definition used throughout SS5
    (WP4), applied here as a whole-text predicate."""
    with torch.no_grad():
        tokens = model.to_tokens(text)
        _, cache = model.run_with_cache(tokens, names_filter=hook_name)
        feats = sae.encode(cache[hook_name].to(torch.float32))[0]  # [seq, d_sae]
        return bool((feats[:, feature_index] != 0).any().item())


def compute_sensitivity_and_cross_lingual_firing(
    model, sae, hook_name: str, feature_index: int, concept: dict,
) -> tuple[dict, dict | None]:
    """Returns (sensitivity, cross_lingual_firing)."""
    complete_langs = {
        lang: entry for lang, entry in concept["languages"].items() if entry["status"] == "complete"
    }
    probes_only_langs = {
        lang: entry for lang, entry in concept["languages"].items() if entry["status"] == "probes_only"
    }

    if not complete_langs:
        sensitivity = {"status": "unavailable", "word_absent_fire_rate": None, "per_language": None}
    else:
        per_language: dict[str, float] = {}
        total_fires = 0
        total_n = 0
        for lang, entry in complete_langs.items():
            word_absent = entry["word_absent"]
            fires = sum(_fires(model, sae, hook_name, feature_index, t) for t in word_absent)
            per_language[lang] = fires / len(word_absent)
            total_fires += fires
            total_n += len(word_absent)
        sensitivity = {
            "status": "measured",
            "word_absent_fire_rate": total_fires / total_n,
            "per_language": per_language,
        }

    if not probes_only_langs:
        cross_lingual_firing = None
    else:
        cross_lingual_firing = {}
        for lang, entry in probes_only_langs.items():
            probes = entry["probes"]
            fires = sum(_fires(model, sae, hook_name, feature_index, t) for t in probes)
            cross_lingual_firing[lang] = {"probe_fire_rate": fires / len(probes)}

    return sensitivity, cross_lingual_firing
