"""SS2 store QA measurements (A4).

Store format (implementer's choice, documented -- no format is pinned by
the blueprint beyond "store on cluster"): a directory of `shard_NNNN.npz`
files, each holding `activations` `[n_seq, context_size, d_model]` float
and `input_ids` `[n_seq, context_size]` int, read in **sorted filename
order** -- that order is the store's "serving order" (SS2 invariant:
autocorrelation is computed on serving order, not shuffled).

QA verdict mechanics (ED-11): the verdict is driven by exactly three
metrics -- norm-by-position flatness (reduced to a coefficient of
variation for banding), special-token fraction, and adjacent
autocorrelation. `chat_divergence` is recorded evidence with a
self-describing shape, nullable, and never gate-bearing (excluded from
`apply_bands` on purpose).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np


@dataclasses.dataclass(frozen=True)
class StoreQAMetrics:
    norm_by_position: list[float]
    special_token_fraction: float
    adjacent_autocorrelation: float
    chat_divergence: dict | None


def load_store_shards(store_dir: str | Path) -> list[Path]:
    """Sorted-filename order = the store's serving order."""
    return sorted(Path(store_dir).glob("shard_*.npz"))


def _iter_shards(shard_paths: list[Path]):
    for p in shard_paths:
        with np.load(p) as data:
            yield data["activations"], data["input_ids"]


def compute_norm_by_position(shard_paths: list[Path]) -> list[float]:
    """Mean activation L2 norm at each within-sequence position, across
    every sequence in every shard."""
    sums: np.ndarray | None = None
    counts = 0
    for acts, _ in _iter_shards(shard_paths):
        norms = np.linalg.norm(acts, axis=-1)  # [n_seq, context_size]
        if sums is None:
            sums = np.zeros(norms.shape[1], dtype=np.float64)
        sums += norms.sum(axis=0)
        counts += norms.shape[0]
    if sums is None or counts == 0:
        return []
    return (sums / counts).tolist()


def norm_by_position_cv(norm_by_position: list[float]) -> float:
    """Coefficient of variation of the per-position mean norm -- the
    scalar "flatness" figure the QA bands grade on."""
    arr = np.array(norm_by_position, dtype=np.float64)
    if arr.size == 0 or arr.mean() == 0:
        return 0.0
    return float(arr.std() / arr.mean())


def compute_special_token_fraction(shard_paths: list[Path], special_token_ids: set[int]) -> float:
    total = 0
    special = 0
    for _, ids in _iter_shards(shard_paths):
        total += ids.size
        special += int(np.isin(ids, list(special_token_ids)).sum())
    return special / total if total else 0.0


def compute_adjacent_autocorrelation(shard_paths: list[Path]) -> float:
    """Lag-1 Pearson autocorrelation of the per-position activation-norm
    signal, in serving order (shard order, then within-shard sequence
    order, then within-sequence position order)."""
    chunks = [np.linalg.norm(acts, axis=-1).reshape(-1) for acts, _ in _iter_shards(shard_paths)]
    flat = np.concatenate(chunks).astype(np.float64) if chunks else np.array([], dtype=np.float64)
    if flat.size < 2:
        return 0.0
    a, b = flat[:-1], flat[1:]
    # float64 throughout, plus a relative tolerance scaled to the signal's
    # own magnitude: float32 activation-norm rounding noise on a genuinely
    # constant input produces a std() around 1e-7 relative to the mean, not
    # exactly 0.0 (observed on np.ones((...), dtype="float32") fixtures).
    tol = 1e-5 * max(abs(flat.mean()), 1e-12)
    if a.std() < tol or b.std() < tol:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def compute_chat_divergence(corpus_shards: list[Path], chat_shards: list[Path]) -> dict | None:
    """Self-describing, nullable, never gate-bearing (ED-11): a simple
    mean-norm delta between the chat slice and the corpus sample, recorded
    as evidence only."""
    if not chat_shards:
        return None
    corpus_norms = compute_norm_by_position(corpus_shards)
    chat_norms = compute_norm_by_position(chat_shards)
    if not corpus_norms or not chat_norms:
        return None
    return {
        "metric": "mean_norm_delta",
        "value": float(np.mean(chat_norms) - np.mean(corpus_norms)),
    }


def compute_metrics(
    corpus_shards: list[Path],
    *,
    special_token_ids: set[int],
    chat_shards: list[Path] | None = None,
) -> StoreQAMetrics:
    return StoreQAMetrics(
        norm_by_position=compute_norm_by_position(corpus_shards),
        special_token_fraction=compute_special_token_fraction(corpus_shards, special_token_ids),
        adjacent_autocorrelation=compute_adjacent_autocorrelation(corpus_shards),
        chat_divergence=compute_chat_divergence(corpus_shards, chat_shards or []),
    )
