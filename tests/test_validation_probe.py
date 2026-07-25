"""SS6 probe comparator: frozen recipe (logistic regression, 5-fold
stratified CV, mean-pooled activations), recipe hash, and reference-style
tests against a synthetic dataset with a known, predictable AUC ceiling."""

from pathlib import Path

import numpy as np
import pytest
import yaml

from interplab.validation.probe import (
    PROBE_RECIPE,
    ProbeResult,
    _cv_auc,
    probe_config_hash,
    train_probe,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "synthetic_concepts"


# -- reference-style tests: the fixed CV/AUC recipe against known cases -----


def test_cv_auc_perfectly_separable_data_is_one():
    """A trivially linearly-separable dataset must yield AUC == 1.0 under
    the frozen 5-fold stratified recipe -- the canonical reference case."""
    rng = np.random.default_rng(0)
    n = 60
    pos = rng.normal(loc=10.0, scale=0.1, size=(n, 3))
    neg = rng.normal(loc=-10.0, scale=0.1, size=(n, 3))
    X = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(n), np.zeros(n)])
    auc = _cv_auc(X, y, seed=0)
    assert auc == pytest.approx(1.0, abs=1e-6)


def test_cv_auc_random_labels_is_near_chance():
    """Random labels on random data must yield AUC close to 0.5 -- the
    other canonical reference case."""
    rng = np.random.default_rng(1)
    n = 200
    X = rng.normal(size=(n, 5))
    y = rng.integers(0, 2, size=n)
    auc = _cv_auc(X, y, seed=0)
    assert auc == pytest.approx(0.5, abs=0.15)


def test_cv_auc_deterministic_for_fixed_seed():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(60, 3))
    y = np.array([0, 1] * 30)
    a = _cv_auc(X, y, seed=7)
    b = _cv_auc(X, y, seed=7)
    assert a == b


def test_probe_recipe_uses_five_fold_stratified_logistic_regression():
    assert PROBE_RECIPE["n_splits"] == 5
    assert PROBE_RECIPE["cv"] == "StratifiedKFold"
    assert PROBE_RECIPE["model"] == "LogisticRegression"


def test_probe_config_hash_deterministic_for_fixed_seed():
    assert probe_config_hash(0) == probe_config_hash(0)


def test_probe_config_hash_changes_with_seed():
    assert probe_config_hash(0) != probe_config_hash(1)


# -- train_probe integration (real model+SAE forward passes) ----------------


def test_train_probe_returns_result_with_valid_ranges(tiny_hooked_transformer, tiny_sae):
    zorbium = yaml.safe_load((FIXTURES_DIR / "zorbium.yaml").read_text(encoding="utf-8"))
    en = zorbium["languages"]["en"]
    hook_name = tiny_sae.cfg.metadata.hook_name

    result = train_probe(
        tiny_hooked_transformer, tiny_sae, hook_name, 0, en["probes"], en["concept_absent"], seed=0
    )
    assert isinstance(result, ProbeResult)
    assert 0.0 <= result.auc <= 1.0
    assert 0.0 <= result.feature_auc <= 1.0
    assert result.gap == pytest.approx(result.auc - result.feature_auc)
    assert result.probe_config_hash == probe_config_hash(0)


def test_train_probe_deterministic_for_fixed_seed(tiny_hooked_transformer, tiny_sae):
    zorbium = yaml.safe_load((FIXTURES_DIR / "zorbium.yaml").read_text(encoding="utf-8"))
    en = zorbium["languages"]["en"]
    hook_name = tiny_sae.cfg.metadata.hook_name

    a = train_probe(tiny_hooked_transformer, tiny_sae, hook_name, 0, en["probes"], en["concept_absent"], seed=3)
    b = train_probe(tiny_hooked_transformer, tiny_sae, hook_name, 0, en["probes"], en["concept_absent"], seed=3)
    assert a == b


def test_train_probe_requires_at_least_five_examples_per_class(tiny_hooked_transformer, tiny_sae):
    with pytest.raises(ValueError):
        train_probe(tiny_hooked_transformer, tiny_sae, "blocks.1.hook_resid_post", 0, ["a", "b"], ["c", "d", "e", "f", "g"])
