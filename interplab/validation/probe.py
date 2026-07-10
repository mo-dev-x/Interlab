"""SS6 probe comparator (frozen recipe, §5.SS6): a linear probe trained on
the same residual stream, for the same concept, giving the ceiling of what
is linearly decodable. `feature_auc` is the same classification task using
only the SAE's target-feature activation, so `gap = auc - feature_auc`
splits "model doesn't have it" from "SAE didn't find it" in one number.

Frozen recipe: logistic regression, 5-fold (stratified, to fix class
imbalance -- SS6's own named failure mode) cross-validation, mean-pooled
per-example activations. `probe_config_hash` records the recipe verbatim so
it's auditable and reproducible.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

from interplab.core import canonical_json, hashing

PROBE_RECIPE = {
    "model": "LogisticRegression",
    "solver": "lbfgs",
    "max_iter": 1000,
    "cv": "StratifiedKFold",
    "n_splits": 5,
    "pooling": "mean_over_tokens",
    "scoring": "roc_auc",
}


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    auc: float
    feature_auc: float
    gap: float
    probe_config_hash: str


def probe_config_hash(seed: int) -> str:
    return hashing.sha256_prefixed(canonical_json.canonicalize({**PROBE_RECIPE, "seed": seed}))


def _mean_pooled_activations(model, sae, hook_name: str, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Returns (residual_vectors [n, d_model], feature_scalar [n]) -- both
    mean-pooled over token positions, per example."""
    residuals = []
    features = []
    with torch.no_grad():
        for text in texts:
            tokens = model.to_tokens(text)
            _, cache = model.run_with_cache(tokens, names_filter=hook_name)
            x = cache[hook_name].to(torch.float32)[0]  # [seq, d_model]
            feats = sae.encode(x)  # [seq, d_sae]
            residuals.append(x.mean(dim=0).numpy())
            features.append(feats.mean(dim=0).numpy())
    return np.stack(residuals), np.stack(features)


def _cv_auc(X: np.ndarray, y: np.ndarray, *, seed: int) -> float:
    cv = StratifiedKFold(n_splits=PROBE_RECIPE["n_splits"], shuffle=True, random_state=seed)
    clf = LogisticRegression(solver=PROBE_RECIPE["solver"], max_iter=PROBE_RECIPE["max_iter"])
    scores = cross_val_score(clf, X, y, cv=cv, scoring=PROBE_RECIPE["scoring"])
    return float(scores.mean())


def train_probe(
    model, sae, hook_name: str, feature_index: int,
    positive_texts: list[str], negative_texts: list[str], *, seed: int = 0,
) -> ProbeResult:
    n_splits = PROBE_RECIPE["n_splits"]
    if len(positive_texts) < n_splits or len(negative_texts) < n_splits:
        raise ValueError(
            f"probe comparator needs at least {n_splits} examples per class for "
            f"{n_splits}-fold stratified CV; got {len(positive_texts)} positive, "
            f"{len(negative_texts)} negative"
        )

    residual_pos, feat_pos = _mean_pooled_activations(model, sae, hook_name, positive_texts)
    residual_neg, feat_neg = _mean_pooled_activations(model, sae, hook_name, negative_texts)

    X_full = np.concatenate([residual_pos, residual_neg], axis=0)
    X_feature = np.concatenate([feat_pos[:, feature_index], feat_neg[:, feature_index]]).reshape(-1, 1)
    y = np.concatenate([np.ones(len(positive_texts)), np.zeros(len(negative_texts))])

    auc = _cv_auc(X_full, y, seed=seed)
    feature_auc = _cv_auc(X_feature, y, seed=seed)

    return ProbeResult(
        auc=auc, feature_auc=feature_auc, gap=auc - feature_auc,
        probe_config_hash=probe_config_hash(seed),
    )
