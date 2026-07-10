"""SS6 selectivity: nearest-neighbor behavior on the same probes.
SEARCH API ONLY -- everything here goes through FeatureIndex's public
methods, never characterization internals."""

import json
from pathlib import Path

from interplab.characterization.feature_index import FeatureIndex
from interplab.validation.selectivity import compute_selectivity


def _write_index(tmp_path: Path, features: list[dict]) -> Path:
    out_dir = tmp_path / "index"
    out_dir.mkdir()
    columnar = {
        "index_layout_version": 1,
        "n_features": len(features),
        "n_tokens": 100,
        "chat_slice_tokens": 0,
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": "local:tests/fixtures/tiny_model",
        "hook_name": "blocks.1.hook_resid_post",
        "judge": {"model": "none", "rubric_version": "none", "prompt_version": "none"},
        "features": features,
    }
    (out_dir / "per_feature_stats.json").write_text(json.dumps(columnar), encoding="utf-8")
    return out_dir


def _row(i: int, direction: list[float]) -> dict:
    return {
        "feature_index": i, "corpus_max": 1.0, "firing_rate": 0.1,
        "decile_boundaries": [0.1] * 9, "activation_histogram": {"bin_edges_log10": [], "counts": []},
        "logit_top_tokens": [], "autointerp_label": None, "autointerp_detection_score": None,
        "decoder_direction": direction, "chat_slice_max": None, "chat_slice_firing_rate": None,
    }


def test_selectivity_returns_neighbors_from_search_by_cosine(tmp_path, monkeypatch):
    rows = [_row(0, [1.0, 0.0]), _row(1, [1.0, 0.0]), _row(2, [0.0, 1.0])]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))

    # search_by_activation needs a live model -- stub it so this test stays
    # a pure, fast unit test of compute_selectivity's own logic.
    monkeypatch.setattr(
        fi, "search_by_activation",
        lambda texts, top_n: [type("Hit", (), {"feature_index": i, "score": 0.0})() for i in range(top_n)],
    )
    result = compute_selectivity(fi, 0, ["some probe text"], top_n=2)
    assert [n["index"] for n in result["neighbors"]] == [1, 2]


def test_no_probes_gives_neighbors_without_calling_search_by_activation(tmp_path):
    rows = [_row(0, [1.0, 0.0]), _row(1, [1.0, 0.0])]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    result = compute_selectivity(fi, 0, [], top_n=1)
    assert result["neighbors"][0]["note"] == "no probes available"


def test_co_firing_neighbor_is_flagged_as_possible_duplicate(tmp_path, monkeypatch):
    rows = [_row(0, [1.0, 0.0]), _row(1, [1.0, 0.0])]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))

    def fake_search_by_activation(texts, top_n):
        scores = {0: 1.0, 1: 0.9}  # neighbor 1 fires almost as strongly as target
        return [type("Hit", (), {"feature_index": i, "score": s})() for i, s in scores.items()]

    monkeypatch.setattr(fi, "search_by_activation", fake_search_by_activation)
    result = compute_selectivity(fi, 0, ["probe"], top_n=1)
    assert "possible duplicate" in result["neighbors"][0]["note"]


def test_non_firing_neighbor_is_flagged_as_not_firing(tmp_path, monkeypatch):
    rows = [_row(0, [1.0, 0.0]), _row(1, [1.0, 0.0])]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))

    def fake_search_by_activation(texts, top_n):
        scores = {0: 1.0, 1: 0.0}
        return [type("Hit", (), {"feature_index": i, "score": s})() for i, s in scores.items()]

    monkeypatch.setattr(fi, "search_by_activation", fake_search_by_activation)
    result = compute_selectivity(fi, 0, ["probe"], top_n=1)
    assert result["neighbors"][0]["note"] == "does not fire on the same probes"
