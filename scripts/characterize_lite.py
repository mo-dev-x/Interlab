#!/usr/bin/env python
"""Characterize-Lite -- ad hoc report evidence for a small set of named SAE
features (NOT production infrastructure; does not touch characterize.py).

Extracts only the three report-critical outputs, over a streamed corpus
sample, for the features passed on the command line:

  (1) selectivity   -- firing rate + where each target sits in the
                       population firing-rate distribution, plus a
                       matched-firing-rate control feature's top examples
                       (so "this feature is cheese, the matched-rate control
                       is generic" is a concrete contrast).
  (2) activation distributions -- log-binned histogram + deciles per target,
                       rendered to a PNG each.
  (3) top-k examples -- highest-activating context windows per target.

Reuses the proven certify code paths: GPU/bf16 device selection,
`certification.model_loading` (local:/tamia:/hf: resolution + the manual
fold_ln=False loader), `certification.eval_slice.load_corpus_docs` (lazy
islice stream -- never materializes the full corpus), and the registry to
resolve the checkpoint's weights/model subject refs exactly as certify does.

Output: plain JSON (one file) + one PNG per target feature. No registry
writes, no run card, no dashboards.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np
import torch

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sae_lens import SAE

from interplab.certification import eval_slice
from interplab.certification.model_loading import (
    load_local_hooked_transformer,
    resolve_model_location,
)
from interplab.core import uris
from interplab.registry.registry import get as registry_get

_HIST_MIN_LOG10 = -4.0
_HIST_MAX_LOG10 = 2.0
_HIST_N_BINS = 50
_CONTEXT_BEFORE = 8


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


def _histogram(acts: np.ndarray) -> dict:
    edges = np.linspace(_HIST_MIN_LOG10, _HIST_MAX_LOG10, _HIST_N_BINS + 1)
    pos = acts[acts > 0]
    if pos.size == 0:
        counts = np.zeros(_HIST_N_BINS, dtype=int)
    else:
        counts, _ = np.histogram(np.log10(pos), bins=edges)
    return {"bin_edges_log10": edges.tolist(), "counts": counts.tolist()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint-hash", required=True)
    ap.add_argument("--features", required=True, help="comma-separated feature indices")
    ap.add_argument("--corpus-location", default="local:data/raw/fineweb_subset")
    ap.add_argument("--n-docs", type=int, default=5000)
    ap.add_argument("--seq-len", type=int, default=512)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    targets = [int(x) for x in args.features.split(",")]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    device, dtype = _device_dtype()
    print(f"device={device} dtype={dtype} targets={targets} n_docs={args.n_docs}", flush=True)

    # --- resolve + load, exactly as certify does ---
    checkpoint = registry_get(args.checkpoint_hash)
    weights_ref = _find_ref(checkpoint, "weights")
    model_ref = _find_ref(checkpoint, "model")
    sae = SAE.load_from_pretrained(str(_resolve_local(weights_ref["location"])), device=device)
    model = load_local_hooked_transformer(
        str(resolve_model_location(model_ref["location"])), device=device, dtype=dtype
    )
    model = model.to(device)
    hook_name = sae.cfg.metadata.hook_name
    d_sae = sae.W_dec.shape[0]
    print(f"loaded: d_sae={d_sae} hook={hook_name}", flush=True)

    # --- streaming pass ---
    fire_counts = torch.zeros(d_sae, dtype=torch.float64, device=device)
    max_act = torch.zeros(d_sae, dtype=torch.float64, device=device)
    total_positions = 0
    # per-target detailed records
    tgt_acts: dict[int, list[float]] = {f: [] for f in targets}
    tgt_examples: dict[int, list[dict]] = {f: [] for f in targets}

    docs = eval_slice.load_corpus_docs(args.corpus_location, limit=args.n_docs)
    print(f"streamed {len(docs)} docs", flush=True)

    with torch.no_grad():
        for doc_id, text in enumerate(docs):
            if not text:
                continue
            tokens = model.to_tokens(text)[:, : args.seq_len]
            _, cache = model.run_with_cache(tokens, names_filter=hook_name)
            x = cache[hook_name].to(torch.float32)  # [1, seq, d_model]
            feats = sae.encode(x)[0]  # [seq, d_sae]
            seq_len = feats.shape[0]
            total_positions += seq_len

            fire_counts += (feats != 0).sum(dim=0).double()
            max_act = torch.maximum(max_act, feats.max(dim=0).values.double())

            cols = feats[:, targets].float().cpu().numpy()  # [seq, n_targets]
            str_tokens = model.to_str_tokens(tokens[0])
            for ti, f in enumerate(targets):
                col = cols[:, ti]
                nz = np.nonzero(col)[0]
                for pos in nz.tolist():
                    val = float(col[pos])
                    tgt_acts[f].append(val)
                    tgt_examples[f].append(
                        {
                            "text": "".join(str_tokens[max(0, pos - _CONTEXT_BEFORE) : pos + 1]),
                            "activation": val,
                            "doc_id": doc_id,
                            "token_position": pos,
                        }
                    )
            if (doc_id + 1) % 500 == 0:
                print(f"  ...{doc_id + 1} docs, {total_positions} positions", flush=True)

    # --- population context for selectivity ---
    fc = fire_counts.cpu().numpy()
    rates = fc / max(total_positions, 1)
    ma = max_act.cpu().numpy()
    median_rate = float(np.median(rates))

    def _firing_rate_percentile(f: int) -> float:
        # percentile of this feature's firing rate in the population: fraction of
        # features that fire LESS often. LOW percentile => target fires less than
        # most features => more selective; HIGH => common. (Report raw; reader
        # interprets against the on-concept top examples.)
        return float((rates < rates[f]).mean() * 100.0)

    def _matched_control(f: int) -> int:
        # nearest firing rate among non-target features
        diff = np.abs(rates - rates[f])
        for t in targets:
            diff[t] = np.inf
        return int(np.argmin(diff))

    results = {
        "checkpoint_hash": args.checkpoint_hash,
        "hook_name": hook_name,
        "d_sae": int(d_sae),
        "n_docs": len(docs),
        "total_positions": int(total_positions),
        "population_median_firing_rate": median_rate,
        "features": {},
    }

    for f in targets:
        acts = np.array(tgt_acts[f], dtype=np.float64)
        ex_sorted = sorted(tgt_examples[f], key=lambda e: e["activation"], reverse=True)
        deciles = np.percentile(acts, np.arange(10, 100, 10)).tolist() if acts.size else []
        ctrl = _matched_control(f)
        results["features"][str(f)] = {
            "firing_rate": float(rates[f]),
            "max_activation": float(ma[f]),
            "mean_activation_when_firing": float(acts.mean()) if acts.size else 0.0,
            "n_firings": int(acts.size),
            "firing_rate_percentile": _firing_rate_percentile(f),  # low => selective, high => common
            "selectivity_vs_median": float(rates[f] / median_rate) if median_rate > 0 else None,
            "activation_deciles": deciles,
            "activation_histogram": _histogram(acts),
            "matched_control_feature": ctrl,
            "matched_control_firing_rate": float(rates[ctrl]),
            "matched_control_max_activation": float(ma[ctrl]),
            "top_examples": ex_sorted[:25],
        }

        # PNG: activation distribution
        fig, axpanel = plt.subplots(figsize=(6, 4))
        pos = acts[acts > 0]
        if pos.size:
            axpanel.hist(np.log10(pos), bins=50, color="#3b7dd8")
        axpanel.set_title(f"feature {f} activation dist (log10)\nrate={rates[f]:.2e} max={ma[f]:.2f} n={acts.size}")
        axpanel.set_xlabel("log10(activation)")
        axpanel.set_ylabel("count")
        fig.tight_layout()
        fig.savefig(out_dir / f"feature_{f}_actdist.png", dpi=110)
        plt.close(fig)

    out_json = out_dir / "characterize_lite.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"WROTE {out_json}", flush=True)
    for f in targets:
        r = results["features"][str(f)]
        print(
            f"  feat {f}: rate={r['firing_rate']:.3e} (median {median_rate:.3e}), "
            f"max={r['max_activation']:.2f}, n_fire={r['n_firings']}, "
            f"rate_pctile={r['firing_rate_percentile']:.1f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
