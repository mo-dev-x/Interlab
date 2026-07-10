"""SS2 store QA metrics + bands (ED-11)."""

from pathlib import Path

import numpy as np
import pytest

from interplab.store_qa.bands import apply_bands, load_bands
from interplab.store_qa.qa import (
    StoreQAMetrics,
    compute_adjacent_autocorrelation,
    compute_chat_divergence,
    compute_metrics,
    compute_norm_by_position,
    compute_special_token_fraction,
    load_store_shards,
    norm_by_position_cv,
)


def _write_shard(store_dir: Path, name: str, activations: np.ndarray, input_ids: np.ndarray) -> Path:
    store_dir.mkdir(parents=True, exist_ok=True)
    path = store_dir / name
    np.savez(path, activations=activations.astype("float32"), input_ids=input_ids.astype("int64"))
    return path


def test_load_store_shards_sorted_order(tmp_path):
    store_dir = tmp_path / "store"
    _write_shard(store_dir, "shard_0002.npz", np.zeros((1, 2, 2)), np.zeros((1, 2)))
    _write_shard(store_dir, "shard_0000.npz", np.zeros((1, 2, 2)), np.zeros((1, 2)))
    _write_shard(store_dir, "shard_0001.npz", np.zeros((1, 2, 2)), np.zeros((1, 2)))
    shards = load_store_shards(store_dir)
    assert [p.name for p in shards] == ["shard_0000.npz", "shard_0001.npz", "shard_0002.npz"]


def test_norm_by_position_flat_store(tmp_path):
    store_dir = tmp_path / "store"
    acts = np.ones((3, 4, 8))  # constant norm at every position
    _write_shard(store_dir, "shard_0000.npz", acts, np.zeros((3, 4)))
    shards = load_store_shards(store_dir)
    norms = compute_norm_by_position(shards)
    assert len(norms) == 4
    assert all(abs(n - norms[0]) < 1e-9 for n in norms)


def test_norm_by_position_cv_zero_for_flat_norms():
    assert norm_by_position_cv([2.0, 2.0, 2.0]) == 0.0


def test_norm_by_position_cv_positive_for_varying_norms():
    assert norm_by_position_cv([1.0, 2.0, 3.0]) > 0.0


def test_special_token_fraction_counts_matching_ids(tmp_path):
    store_dir = tmp_path / "store"
    ids = np.array([[1, 5, 5, 5], [1, 5, 5, 5]])  # id 1 = BOS, 2/8 positions
    _write_shard(store_dir, "shard_0000.npz", np.zeros((2, 4, 3)), ids)
    shards = load_store_shards(store_dir)
    frac = compute_special_token_fraction(shards, {1})
    assert frac == pytest.approx(2 / 8)


def test_special_token_fraction_zero_when_absent(tmp_path):
    store_dir = tmp_path / "store"
    ids = np.full((2, 4), 5)
    _write_shard(store_dir, "shard_0000.npz", np.zeros((2, 4, 3)), ids)
    shards = load_store_shards(store_dir)
    assert compute_special_token_fraction(shards, {1}) == 0.0


def test_adjacent_autocorrelation_high_for_constant_signal(tmp_path):
    """A perfectly repeating norm pattern is maximally autocorrelated at
    lag 1... except a truly constant signal has zero variance (undefined
    correlation, handled as 0.0); use a smoothly varying, highly
    autocorrelated signal instead."""
    store_dir = tmp_path / "store"
    t = np.linspace(0, 4 * np.pi, 100)
    signal = np.sin(t)
    acts = signal.reshape(1, 100, 1) * np.ones((1, 100, 8))
    _write_shard(store_dir, "shard_0000.npz", acts, np.zeros((1, 100)))
    shards = load_store_shards(store_dir)
    autocorr = compute_adjacent_autocorrelation(shards)
    assert autocorr > 0.9


def test_adjacent_autocorrelation_zero_for_constant_signal(tmp_path):
    store_dir = tmp_path / "store"
    acts = np.ones((1, 50, 8))
    _write_shard(store_dir, "shard_0000.npz", acts, np.zeros((1, 50)))
    shards = load_store_shards(store_dir)
    assert compute_adjacent_autocorrelation(shards) == 0.0


def test_adjacent_autocorrelation_low_for_random_noise(tmp_path):
    store_dir = tmp_path / "store"
    rng = np.random.default_rng(0)
    acts = rng.normal(size=(1, 500, 8))
    _write_shard(store_dir, "shard_0000.npz", acts, np.zeros((1, 500)))
    shards = load_store_shards(store_dir)
    autocorr = compute_adjacent_autocorrelation(shards)
    assert abs(autocorr) < 0.3


def test_chat_divergence_null_when_no_chat_shards(tmp_path):
    store_dir = tmp_path / "store"
    _write_shard(store_dir, "shard_0000.npz", np.ones((1, 4, 8)), np.zeros((1, 4)))
    shards = load_store_shards(store_dir)
    assert compute_chat_divergence(shards, []) is None


def test_chat_divergence_is_self_describing_and_never_gate_bearing(tmp_path):
    corpus_dir = tmp_path / "corpus"
    chat_dir = tmp_path / "chat"
    _write_shard(corpus_dir, "shard_0000.npz", np.ones((1, 4, 8)), np.zeros((1, 4)))
    _write_shard(chat_dir, "shard_0000.npz", np.full((1, 4, 8), 100.0), np.zeros((1, 4)))  # wildly different norm
    corpus_shards = load_store_shards(corpus_dir)
    chat_shards = load_store_shards(chat_dir)

    divergence = compute_chat_divergence(corpus_shards, chat_shards)
    assert divergence is not None
    assert "metric" in divergence and "value" in divergence
    assert divergence["value"] > 0  # chat norm >> corpus norm

    # Extreme chat divergence must not affect the verdict (never gate-bearing).
    metrics = StoreQAMetrics(
        norm_by_position=[1.0, 1.0], special_token_fraction=0.0, adjacent_autocorrelation=0.0,
        chat_divergence=divergence,
    )
    bands = load_bands()
    verdict, per_metric = apply_bands(metrics, bands)
    assert verdict == "green"
    assert "chat_divergence" not in per_metric


def test_compute_metrics_end_to_end(tmp_path):
    store_dir = tmp_path / "store"
    _write_shard(store_dir, "shard_0000.npz", np.ones((2, 4, 8)), np.zeros((2, 4)))
    shards = load_store_shards(store_dir)
    metrics = compute_metrics(shards, special_token_ids={99})
    assert len(metrics.norm_by_position) == 4
    assert metrics.special_token_fraction == 0.0
    assert metrics.chat_divergence is None


# -- bands / verdict ----------------------------------------------------------


def test_apply_bands_all_green():
    metrics = StoreQAMetrics(
        norm_by_position=[2.0, 2.0, 2.0], special_token_fraction=0.0, adjacent_autocorrelation=0.0,
        chat_divergence=None,
    )
    verdict, per_metric = apply_bands(metrics, load_bands())
    assert verdict == "green"
    assert set(per_metric) == {"norm_by_position_cv", "special_token_fraction", "adjacent_autocorrelation"}
    assert all(v == "green" for v in per_metric.values())


def test_apply_bands_worst_metric_drives_overall_verdict():
    metrics = StoreQAMetrics(
        norm_by_position=[2.0, 2.0, 2.0], special_token_fraction=0.5, adjacent_autocorrelation=0.0,
        chat_divergence=None,
    )
    verdict, per_metric = apply_bands(metrics, load_bands())
    assert verdict == "red"
    assert per_metric["special_token_fraction"] == "red"
    assert per_metric["norm_by_position_cv"] == "green"


def test_apply_bands_uses_absolute_autocorrelation():
    """A strongly *negative* autocorrelation is just as unhealthy as a
    strongly positive one -- banding uses |adjacent_autocorrelation|."""
    metrics = StoreQAMetrics(
        norm_by_position=[2.0, 2.0], special_token_fraction=0.0, adjacent_autocorrelation=-0.9,
        chat_divergence=None,
    )
    verdict, per_metric = apply_bands(metrics, load_bands())
    assert per_metric["adjacent_autocorrelation"] == "red"
    assert verdict == "red"
