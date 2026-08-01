#!/usr/bin/env python
"""Multilingual battery rerun on the INSTRUCT SAE (rwu04lpb) -- T1.1.

Replaces the stale `results/features/multilingual/` (which was computed on the
base SAE via a raw-HF layer-24 forward hook, and is degenerate: the same 20
"shared" features appear for every concept). This rerun reuses the *same probe
sentences* but measures features the correct way: rwu04lpb's own
`hook_resid_post` (layer 28) via the transformer_lens loader already proven in
certify/characterize_lite, on the actual TopK (k=100) instruct SAE.

Method (faithful to scripts/legacy/find_features.py's multilingual block):
per (concept, language) take the MEAN feature activation over all probe tokens
-> top-20 feature ids; overlap matrix = intersection of the four languages'
top-20 (shared_all_languages) and each language's top-20 minus the union of the
others (unique_to_<lang>). One deliberate change, documented: the BOS token is
excluded from the mean -- BOS carries constant, concept-independent
high-activation features that otherwise collapse every concept onto the same
"shared" set.

Output: plain JSON only (no registry writes, no dashboards):
  results/features/multilingual_rwu04lpb/multilingual_feature_activations.json
  results/features/multilingual_rwu04lpb/multilingual_overlap_matrix.json
  results/features/multilingual_rwu04lpb/multilingual_overlap_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from sae_lens import SAE

from interplab.certification.model_loading import (
    load_local_hooked_transformer,
    resolve_model_location,
)
from interplab.core import uris
from interplab.registry.registry import get as registry_get

TOP_K = 20


def _device_dtype() -> tuple[str, torch.dtype]:
    if torch.cuda.is_available():
        return "cuda", torch.bfloat16
    return "cpu", torch.float32


def _find_ref(artifact: dict, role: str) -> dict:
    for ref in artifact["subject"]:
        if ref["role"] == role:
            return ref
    raise KeyError(f"no subject ref with role {role!r}")


def _resolve_local(location: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        return uris.resolve_local(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    raise NotImplementedError(f"cannot resolve SAE weights from {location!r} (want local:/tamia:)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint-hash", required=True)
    ap.add_argument("--probes", required=True, help="path to multilingual_probe_sentences.json")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    device, dtype = _device_dtype()
    probes = json.loads(Path(args.probes).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"device={device} concepts={list(probes)}", flush=True)

    checkpoint = registry_get(args.checkpoint_hash)
    weights_ref = _find_ref(checkpoint, "weights")
    model_ref = _find_ref(checkpoint, "model")
    sae = SAE.load_from_pretrained(str(_resolve_local(weights_ref["location"])), device=device)
    model = load_local_hooked_transformer(
        str(resolve_model_location(model_ref["location"])), device=device, dtype=dtype
    ).to(device)
    hook_name = sae.cfg.metadata.hook_name
    d_sae = sae.W_dec.shape[0]
    print(f"loaded: d_sae={d_sae} hook={hook_name}", flush=True)

    activations: dict = {}
    with torch.no_grad():
        for concept, lang_dict in probes.items():
            activations[concept] = {}
            for lang, sentences in lang_dict.items():
                sum_acts = torch.zeros(d_sae, dtype=torch.float64, device=device)
                n_tokens = 0
                for text in sentences:
                    tokens = model.to_tokens(text)
                    _, cache = model.run_with_cache(tokens, names_filter=hook_name)
                    x = cache[hook_name].to(torch.float32)  # [1, seq, d_model]
                    feats = sae.encode(x)[0]  # [seq, d_sae]
                    if feats.shape[0] <= 1:
                        continue
                    feats = feats[1:]  # drop BOS position
                    sum_acts += feats.double().sum(dim=0)
                    n_tokens += feats.shape[0]
                mean_act = (sum_acts / max(n_tokens, 1)).cpu()
                top = torch.topk(mean_act, TOP_K)
                top_ids = top.indices.tolist()
                activations[concept][lang] = {
                    "top_feature_ids": top_ids,
                    "top_feature_activations": [float(v) for v in top.values.tolist()],
                    "n_tokens": n_tokens,
                }
                print(f"  {concept}/{lang}: n_tokens={n_tokens} top1={top_ids[0]}", flush=True)

    # overlap matrix (same computation as legacy find_features.py)
    overlap: dict = {}
    summary: dict = {}
    for concept, lang_data in activations.items():
        sets = {lang: set(d["top_feature_ids"]) for lang, d in lang_data.items()}
        langs = list(sets)
        shared = set.intersection(*sets.values()) if sets else set()
        overlap[concept] = {"shared_all_languages": sorted(shared)}
        for lang in langs:
            others = set().union(*(sets[other_lang] for other_lang in langs if other_lang != lang))
            overlap[concept][f"unique_to_{lang}"] = sorted(sets[lang] - others)
        # pairwise Jaccard for the report figure
        pair_jac = {}
        for i, a in enumerate(langs):
            for b in langs[i + 1 :]:
                inter = len(sets[a] & sets[b])
                union = len(sets[a] | sets[b])
                pair_jac[f"{a}-{b}"] = inter / union if union else 0.0
        summary[concept] = {
            "n_shared_all_languages": len(shared),
            "top_k": TOP_K,
            "shared_fraction": len(shared) / TOP_K,
            "pairwise_jaccard": pair_jac,
            "mean_pairwise_jaccard": (sum(pair_jac.values()) / len(pair_jac)) if pair_jac else 0.0,
        }

    (out_dir / "multilingual_feature_activations.json").write_text(
        json.dumps(activations, indent=2), encoding="utf-8"
    )
    (out_dir / "multilingual_overlap_matrix.json").write_text(
        json.dumps(overlap, indent=2), encoding="utf-8"
    )
    (out_dir / "multilingual_overlap_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("=== overlap summary ===", flush=True)
    for concept, s in summary.items():
        print(
            f"  {concept}: shared_all={s['n_shared_all_languages']}/{TOP_K} "
            f"(frac {s['shared_fraction']:.2f}), mean_pairwise_jaccard={s['mean_pairwise_jaccard']:.2f}",
            flush=True,
        )
    print(f"WROTE {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
