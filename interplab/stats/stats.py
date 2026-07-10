"""SS9 `interplab.stats` (TRUNK, shared library, not delegable).

The four frozen statistics primitives (§5.SS9): `bootstrap_ci`, `bh_fdr`,
`seed_variance`, `effect_size`. Pure computation -- no registry
interactions, no jobs, no schemas. Every function is deterministic for
fixed inputs and a fixed `seed` where applicable.

Prompts, not generations, are the exchangeable resampling unit (infra doc
§SS9): `bootstrap_ci` resamples at the group (prompt) level, never
individual values, and `effect_size` aggregates to one value per group
before computing Cohen's d -- the same discipline applied consistently,
not just in the bootstrap.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np


@dataclasses.dataclass(frozen=True)
class CI:
    estimate: float
    ci_low: float
    ci_high: float
    level: float
    n_boot: int
    n_groups: int
    seed: int


@dataclasses.dataclass(frozen=True)
class SeedVar:
    mean: float
    std: float | None  # None (not 0.0) when n_seeds < 2 -- unmeasurable, not zero
    n_seeds: int
    per_seed: list[float]


@dataclasses.dataclass(frozen=True)
class CohensD:
    d: float
    n_a: int
    n_b: int


class DegenerateEffectError(Exception):
    """`effect_size`: pooled std is zero (every group-aggregated value is
    identical within each condition) but the two conditions' means differ.
    Cohen's d is undefined here -- 0.0 would falsely report "no effect,"
    and +/-inf is not permitted (canonical JSON forbids non-finite
    numbers). Callers should report the raw per-condition means directly
    instead of a standardized effect size for this case."""


def _group_buckets(values: np.ndarray, groups: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """Returns (unique_groups, [values for group 0, values for group 1, ...])."""
    unique_groups, group_ids = np.unique(groups, return_inverse=True)
    order = np.argsort(group_ids, kind="stable")
    sorted_group_ids = group_ids[order]
    sorted_values = values[order]
    boundaries = np.searchsorted(sorted_group_ids, np.arange(len(unique_groups) + 1))
    buckets = [sorted_values[boundaries[i] : boundaries[i + 1]] for i in range(len(unique_groups))]
    return unique_groups, buckets


def bootstrap_ci(
    values: np.ndarray | list[float],
    groups: np.ndarray | list,
    n_boot: int = 10_000,
    level: float = 0.95,
    seed: int = 0,
) -> CI:
    """Percentile bootstrap; resampling unit = groups (prompt IDs), never
    individual values. Each replicate resamples group *identities* with
    replacement (same count as the original number of groups), pools every
    value belonging to the resampled groups, and computes the mean over
    that pooled set. The point estimate is the real (non-resampled) mean.
    """
    values = np.asarray(values, dtype=np.float64)
    groups = np.asarray(groups)
    if values.shape[0] != groups.shape[0]:
        raise ValueError(
            f"values and groups must have the same length; got {values.shape[0]} vs {groups.shape[0]}"
        )
    if values.size == 0:
        raise ValueError("bootstrap_ci requires at least one value")

    _unique_groups, buckets = _group_buckets(values, groups)
    n_groups = len(buckets)

    estimate = float(values.mean())
    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        sampled_idx = rng.integers(0, n_groups, size=n_groups)
        pooled = np.concatenate([buckets[i] for i in sampled_idx])
        boot_stats[b] = pooled.mean()

    alpha = 1.0 - level
    lo, hi = np.percentile(boot_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return CI(
        estimate=estimate, ci_low=float(lo), ci_high=float(hi),
        level=level, n_boot=n_boot, n_groups=n_groups, seed=seed,
    )


def bh_fdr(pvalues: np.ndarray | list[float], q: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg step-up procedure. Returns a boolean mask in the
    *original* input order (`True` = reject null / significant after
    correction).

    Standard BH: sort p-values ascending, find the largest rank `k` such
    that `p_(k) <= (k/m) * q`, reject every hypothesis at or below that
    rank.
    """
    pvalues = np.asarray(pvalues, dtype=np.float64)
    m = pvalues.shape[0]
    if m == 0:
        return np.zeros(0, dtype=bool)

    order = np.argsort(pvalues, kind="stable")
    sorted_p = pvalues[order]
    thresholds = (np.arange(1, m + 1) / m) * q
    below = sorted_p <= thresholds

    hits = np.nonzero(below)[0]
    k = int(hits.max()) + 1 if hits.size else 0

    mask_sorted = np.zeros(m, dtype=bool)
    mask_sorted[:k] = True
    mask = np.zeros(m, dtype=bool)
    mask[order] = mask_sorted
    return mask


def seed_variance(per_seed_estimates: np.ndarray | list[float]) -> SeedVar:
    """`n_seeds` is always surfaced, even at 0 or 1. `std` is `None` (not
    `0.0`) when fewer than 2 seeds exist -- variance is honestly
    unmeasurable from a single sample, the same null-vs-zero discipline
    this codebase already applies elsewhere (ED-9)."""
    arr = np.asarray(per_seed_estimates, dtype=np.float64)
    n_seeds = arr.shape[0]
    mean = float(arr.mean()) if n_seeds else float("nan")
    std = float(arr.std(ddof=1)) if n_seeds >= 2 else None
    return SeedVar(mean=mean, std=std, n_seeds=n_seeds, per_seed=arr.tolist())


def effect_size(
    a: np.ndarray | list[float],
    b: np.ndarray | list[float],
    groups: np.ndarray | list,
) -> CohensD:
    """Cohen's d with pooled standard deviation, computed over
    per-group-aggregated values: `a`/`b` are aggregated to one mean per
    group (prompt) each *before* the pooled-std formula runs, so a prompt
    with more generations does not get extra weight -- the same
    exchangeable-resampling-unit discipline `bootstrap_ci` applies."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    groups = np.asarray(groups)
    if a.shape[0] != groups.shape[0] or b.shape[0] != groups.shape[0]:
        raise ValueError("a, b, and groups must all have the same length")

    _unique_groups_a, buckets_a = _group_buckets(a, groups)
    _unique_groups_b, buckets_b = _group_buckets(b, groups)
    a_agg = np.array([bucket.mean() for bucket in buckets_a], dtype=np.float64)
    b_agg = np.array([bucket.mean() for bucket in buckets_b], dtype=np.float64)

    n_a, n_b = a_agg.shape[0], b_agg.shape[0]
    if n_a < 2 or n_b < 2:
        raise ValueError("effect_size requires at least 2 groups per condition to estimate a pooled std")

    var_a = a_agg.var(ddof=1)
    var_b = b_agg.var(ddof=1)
    pooled_std = math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    mean_diff = a_agg.mean() - b_agg.mean()

    if pooled_std > 0:
        d = mean_diff / pooled_std
    elif mean_diff == 0:
        d = 0.0
    else:
        raise DegenerateEffectError(
            f"pooled std is zero (both conditions have constant, zero-variance group-aggregated "
            f"values) but the means differ (a={float(a_agg.mean())!r}, b={float(b_agg.mean())!r}) "
            f"-- Cohen's d is undefined for this case; report the raw per-condition means instead "
            f"of a standardized effect size"
        )
    return CohensD(d=float(d), n_a=n_a, n_b=n_b)
