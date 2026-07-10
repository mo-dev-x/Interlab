"""SS6 selectivity: behavior of nearest-neighbor features (decoder cosine)
on the same probes -- flags duplicate/entangled features.

SEARCH API ONLY (§1): everything here goes through `FeatureIndex`'s frozen
public methods (`search_by_cosine`, `search_by_activation`) -- validation
never reaches into characterization's internals.
"""

from __future__ import annotations

from interplab.characterization.feature_index import FeatureIndex


def compute_selectivity(index: FeatureIndex, target_index: int, probes: list[str], *, top_n: int = 5) -> dict:
    neighbors = index.search_by_cosine(target_index, top_n=top_n)
    if not neighbors or not probes:
        return {"neighbors": [{"index": h.feature_index, "cosine": h.score, "note": "no probes available"} for h in neighbors]}

    activation_hits = index.search_by_activation(probes, top_n=index.n_features)
    activation_by_index = {h.feature_index: h.score for h in activation_hits}
    target_probe_score = activation_by_index.get(target_index, 0.0)

    result = []
    for h in neighbors:
        neighbor_score = activation_by_index.get(h.feature_index, 0.0)
        if target_probe_score > 0 and neighbor_score >= 0.5 * target_probe_score:
            note = "co-fires strongly on the same probes -- possible duplicate/entangled feature"
        elif neighbor_score > 0:
            note = "fires weakly on the same probes"
        else:
            note = "does not fire on the same probes"
        result.append({"index": h.feature_index, "cosine": h.score, "note": note})

    return {"neighbors": result}
