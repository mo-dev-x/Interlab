"""SS5 streaming indexer: runs the model+SAE over a corpus sample (+ an
optional chat-formatted slice) and produces the CharacterizationIndex
(per-feature columnar stats + example shards) that `FeatureIndex` reads.

corpus_max sourcing invariant: `corpus_max`/`firing_rate`/`decile_boundaries`
/`activation_histogram`/`logit_top_tokens`/examples are computed **only**
from the corpus-sample pass. The chat-slice pass (if any) produces its own,
separately-named `chat_slice_max`/`chat_slice_firing_rate` columns that
`FeatureIndex.corpus_max`/`.firing_rate` never read -- the two are never
merged (per the blueprint's SS5 invariant and this WP's standing
constraint).

Autointerpretation (D2, stub-judge resolution): `Judge` is a narrow
protocol (`label(feature_index, top_examples) -> (label, detection_score)`);
the indexer records `judge: {model, rubric_version, prompt_version}`
verbatim from whatever judge it was given, exactly as A7 requires.
Production autointerpretation (a real Lodestar-backed judge) is
researcher-gated and out of scope here: `NoOpJudge` is the honest default
(null labels, `judge.model = "none"`); `StubJudge` is a deterministic test
double, never wired to production.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Protocol

import numpy as np
import torch
from sae_lens import SAE

_HIST_MIN_LOG10 = -8.0
_HIST_MAX_LOG10 = 0.0
_HIST_N_BINS = 20
_N_DECILES = 10
_TOP_K_EXAMPLES = 10
_EXAMPLES_PER_DECILE = 5


class Judge(Protocol):
    model: str
    rubric_version: str
    prompt_version: str

    def label(self, feature_index: int, top_examples: list[str]) -> tuple[str | None, float | None]: ...


@dataclasses.dataclass(frozen=True)
class NoOpJudge:
    """Records honestly that no judge ran: `autointerp_label`/
    `autointerp_detection_score` are `null` for every feature, `judge`
    metadata names no real model. This is the production-safe default --
    running the test-only `StubJudge` against real production data would
    fabricate autointerp labels disguised as real ones. Wiring a real
    Lodestar-backed judge is a separate, explicitly researcher-gated task
    (D2), out of scope for WP4."""

    model: str = "none"
    rubric_version: str = "none"
    prompt_version: str = "none"

    def label(self, feature_index: int, top_examples: list[str]) -> tuple[str | None, float | None]:
        return None, None


@dataclasses.dataclass(frozen=True)
class StubJudge:
    """Deterministic test double: labels a feature by its most common
    top-example word. Exercises the full A7 judge-recording path
    end-to-end without a real Lodestar call -- test-only, never wired to
    production."""

    model: str = "stub-judge-v1"
    rubric_version: str = "stub-v1"
    prompt_version: str = "stub-v1"

    def label(self, feature_index: int, top_examples: list[str]) -> tuple[str | None, float | None]:
        if not top_examples:
            return None, None
        words: list[str] = []
        for ex in top_examples:
            words.extend(w.strip(".,!?").lower() for w in ex.split())
        if not words:
            return None, None
        label = max(set(words), key=words.count)
        score = words.count(label) / len(words)
        return label, score


def fp32_copy(sae: SAE) -> SAE:
    """Non-mutating fp32 copy (same pattern as `certification.metrics.fp32_copy`,
    duplicated per §1's per-subsystem isolation)."""
    fp32_cfg = dataclasses.replace(sae.cfg, dtype="float32")
    sae32 = SAE(fp32_cfg)
    sae32.load_state_dict({k: v.detach().to(torch.float32) for k, v in sae.state_dict().items()})
    return sae32.to(sae.W_dec.device)


@dataclasses.dataclass
class _FeatureAccumulator:
    max_activation: float = 0.0
    fire_count: int = 0
    activations: list[float] = dataclasses.field(default_factory=list)
    examples: list[dict] = dataclasses.field(default_factory=list)  # {text, activation, token_position, doc_id}


def _run_pass(model, sae32: SAE, hook_name: str, docs: list[str]) -> tuple[dict[int, _FeatureAccumulator], int]:
    """Runs one forward+encode pass over `docs`. Returns (per-feature
    accumulators, total_positions)."""
    d_sae = sae32.W_dec.shape[0]
    accs: dict[int, _FeatureAccumulator] = {i: _FeatureAccumulator() for i in range(d_sae)}
    total_positions = 0

    with torch.no_grad():
        for doc_id, text in enumerate(docs):
            tokens = model.to_tokens(text)
            _, cache = model.run_with_cache(tokens, names_filter=hook_name)
            x = cache[hook_name].to(torch.float32)  # [1, seq, d_model]
            feats = sae32.encode(x)[0]  # [seq, d_sae]
            str_tokens = model.to_str_tokens(tokens[0])
            seq_len = feats.shape[0]
            total_positions += seq_len

            for pos in range(seq_len):
                row = feats[pos]
                nonzero = torch.nonzero(row, as_tuple=True)[0]
                for i_t in nonzero.tolist():
                    val = float(row[i_t].item())
                    acc = accs[i_t]
                    acc.fire_count += 1
                    acc.activations.append(val)
                    acc.max_activation = max(acc.max_activation, val)
                    acc.examples.append(
                        {
                            "text": "".join(str_tokens[max(0, pos - 5) : pos + 1]),
                            "activation": val,
                            "token_position": pos,
                            "doc_id": doc_id,
                        }
                    )

    return accs, total_positions


def _activation_histogram(activations: list[float]) -> dict:
    bin_edges_log10 = np.linspace(_HIST_MIN_LOG10, _HIST_MAX_LOG10, _HIST_N_BINS + 1)
    arr = np.array([a for a in activations if a > 0], dtype=np.float64)
    if arr.size == 0:
        counts = np.zeros(_HIST_N_BINS, dtype=int)
    else:
        counts, _ = np.histogram(np.log10(arr), bins=bin_edges_log10)
    return {"bin_edges_log10": bin_edges_log10.tolist(), "counts": counts.tolist()}


def _decile_boundaries(activations: list[float]) -> list[float]:
    """9 interior quantile cut-points (10th-90th percentile) of the nonzero
    activation distribution -- implementer's choice, documented (WP4
    plan): standard, reversible (index is content-addressed/recomputed on
    demand, per D3, if a different convention is later preferred)."""
    if not activations:
        return [0.0] * (_N_DECILES - 1)
    arr = np.array(activations, dtype=np.float64)
    qs = np.linspace(0, 100, _N_DECILES + 1)[1:-1]  # 10..90
    return np.percentile(arr, qs).tolist()


def _decile_examples(examples: list[dict], boundaries: list[float], rng: np.random.Generator) -> dict[int, list[dict]]:
    """Uniform sampling *within* each decile bucket (SS5 invariant) -- every
    example in a decile is equally likely to be picked, not just the
    highest-activating one."""
    if not examples:
        return {d: [] for d in range(_N_DECILES)}
    edges = [-float("inf"), *boundaries, float("inf")]
    buckets: dict[int, list[dict]] = {d: [] for d in range(_N_DECILES)}
    for ex in examples:
        for d in range(_N_DECILES):
            if edges[d] < ex["activation"] <= edges[d + 1] or (d == 0 and ex["activation"] == edges[0]):
                buckets[d].append(ex)
                break
    sampled: dict[int, list[dict]] = {}
    for d, bucket in buckets.items():
        if not bucket:
            sampled[d] = []
            continue
        n = min(_EXAMPLES_PER_DECILE, len(bucket))
        idx = rng.choice(len(bucket), size=n, replace=False)
        sampled[d] = [bucket[j] for j in sorted(idx.tolist())]
    return sampled


def _logit_top_tokens(model, decoder_direction: torch.Tensor, top_k: int = 8) -> list[str]:
    """Logit-lens: project the (unnormalized) decoder direction onto the
    unembedding matrix, take the top-k tokens by logit value."""
    logits = decoder_direction.to(torch.float32) @ model.W_U.to(torch.float32)
    top = torch.topk(logits, k=min(top_k, logits.shape[0]))
    return [model.tokenizer.decode([t]) for t in top.indices.tolist()]


def build_index(
    model,
    sae: SAE,
    *,
    corpus_docs: list[str],
    chat_docs: list[str] | None = None,
    judge: Judge,
    weights_location: str,
    model_location: str,
    rng_seed: int = 0,
) -> dict:
    """Runs the full streaming pass and returns the index payload as a
    plain dict, ready for `write_index`. `chat_docs` (if given) contributes
    only `chat_slice_max`/`chat_slice_firing_rate` -- never corpus_max.

    `weights_location`/`model_location` (`local:`/`tamia:` URIs) are
    recorded in the columnar subset so `FeatureIndex.search_by_activation`
    can lazily reload the same model+SAE later -- the frozen interface's
    signature has no room for a caller-supplied model, so the index must be
    self-describing enough to resolve one itself."""
    sae32 = fp32_copy(sae)
    hook_name = sae32.cfg.hook_name
    d_sae = sae32.W_dec.shape[0]
    rng = np.random.default_rng(rng_seed)

    corpus_accs, corpus_n = _run_pass(model, sae32, hook_name, corpus_docs)
    chat_accs, chat_n = (_run_pass(model, sae32, hook_name, chat_docs) if chat_docs else ({}, 0))

    w_dec_norm = sae32.W_dec / sae32.W_dec.norm(dim=1, keepdim=True).clamp_min(1e-12)

    features = []
    examples_by_feature: dict[int, list[dict]] = {}
    for i in range(d_sae):
        acc = corpus_accs[i]
        firing_rate = acc.fire_count / corpus_n if corpus_n else 0.0
        boundaries = _decile_boundaries(acc.activations)
        deciles = _decile_examples(acc.examples, boundaries, rng)
        top_k = sorted(acc.examples, key=lambda e: e["activation"], reverse=True)[:_TOP_K_EXAMPLES]

        chat_acc = chat_accs.get(i)
        chat_max = chat_acc.max_activation if chat_acc and chat_acc.fire_count else None
        chat_rate = (chat_acc.fire_count / chat_n) if chat_acc and chat_n else None

        top_example_texts = [e["text"] for e in top_k]
        label, score = judge.label(i, top_example_texts)

        features.append(
            {
                "feature_index": i,
                "corpus_max": acc.max_activation,
                "firing_rate": firing_rate,
                "decile_boundaries": boundaries,
                "activation_histogram": _activation_histogram(acc.activations),
                "logit_top_tokens": _logit_top_tokens(model, w_dec_norm[i]),
                "autointerp_label": label,
                "autointerp_detection_score": score,
                "decoder_direction": w_dec_norm[i].tolist(),
                "chat_slice_max": chat_max,
                "chat_slice_firing_rate": chat_rate,
            }
        )
        examples_by_feature[i] = [{"decile": "top_k", "rank": r, **e} for r, e in enumerate(top_k)] + [
            {"decile": d, "rank": r, **e} for d, exs in deciles.items() for r, e in enumerate(exs)
        ]

    return {
        "index_layout_version": 1,
        "n_features": d_sae,
        "n_tokens": corpus_n,
        "chat_slice_tokens": chat_n,
        "weights_location": weights_location,
        "model_location": model_location,
        "hook_name": hook_name,
        "judge": {
            "model": judge.model,
            "rubric_version": judge.rubric_version,
            "prompt_version": judge.prompt_version,
        },
        "features": features,
        "_examples_by_feature": examples_by_feature,
    }


def write_index(index: dict, out_dir: Path) -> None:
    """Writes the columnar subset (`per_feature_stats.json`, safe to sync
    without example shards -- degraded-mode operation, §5.SS5) and the
    example shards (`examples/<feature_index>.jsonl`, one per feature)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    columnar = {k: v for k, v in index.items() if k != "_examples_by_feature"}
    (out_dir / "per_feature_stats.json").write_text(json.dumps(columnar, indent=2), encoding="utf-8")

    examples_dir = out_dir / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)
    for feature_index, examples in index["_examples_by_feature"].items():
        path = examples_dir / f"{feature_index}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")
