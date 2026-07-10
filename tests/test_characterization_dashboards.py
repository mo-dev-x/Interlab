"""SS5 dashboards (leaf): per-feature cards + catalog page."""

import json
from pathlib import Path

from interplab.characterization import dashboards
from interplab.characterization.feature_index import FeatureIndex


def _write_index(tmp_path: Path, n_features: int = 3) -> Path:
    out_dir = tmp_path / "index"
    out_dir.mkdir()
    features = [
        {
            "feature_index": i,
            "corpus_max": float(i + 1),
            "firing_rate": 0.01 * (i + 1),
            "decile_boundaries": [0.1 * k for k in range(1, 10)],
            "activation_histogram": {"bin_edges_log10": [-1.0, 0.0], "counts": [1]},
            "logit_top_tokens": ["a", "b"],
            "autointerp_label": f"label-{i}" if i > 0 else None,
            "autointerp_detection_score": 0.5 if i > 0 else None,
            "decoder_direction": [1.0, 0.0],
            "chat_slice_max": None,
            "chat_slice_firing_rate": None,
        }
        for i in range(n_features)
    ]
    columnar = {
        "index_layout_version": 1,
        "n_features": n_features,
        "n_tokens": 100,
        "chat_slice_tokens": 0,
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": "local:tests/fixtures/tiny_model",
        "hook_name": "blocks.1.hook_resid_post",
        "judge": {"model": "stub", "rubric_version": "v1", "prompt_version": "v1"},
        "features": features,
    }
    (out_dir / "per_feature_stats.json").write_text(json.dumps(columnar), encoding="utf-8")
    examples_dir = out_dir / "examples"
    examples_dir.mkdir()
    for i in range(n_features):
        rows = [
            {"decile": "top_k", "rank": 0, "text": f"top example {i}", "activation": 1.0, "token_position": 0, "doc_id": 0},
            {"decile": 5, "rank": 0, "text": f"decile example {i}", "activation": 0.5, "token_position": 1, "doc_id": 0},
        ]
        (examples_dir / f"{i}.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return out_dir


def test_render_feature_produces_md_and_png(tmp_path):
    index_dir = _write_index(tmp_path)
    fi = FeatureIndex.open(str(index_dir))
    md_path, png_path = dashboards.render_feature(fi, 1, tmp_path / "dash")
    assert md_path.is_file()
    assert png_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "Feature 1" in text
    assert "label-1" in text
    assert "top example 1" in text
    assert "decile example 1" in text


def test_render_feature_degraded_mode_notes_missing_examples(tmp_path):
    index_dir = _write_index(tmp_path)
    (index_dir / "examples").rename(tmp_path / "examples_backup")
    fi = FeatureIndex.open(str(index_dir))
    md_path, _ = dashboards.render_feature(fi, 0, tmp_path / "dash")
    text = md_path.read_text(encoding="utf-8")
    assert "degraded mode" in text.lower()


def test_render_catalog_lists_every_feature(tmp_path):
    index_dir = _write_index(tmp_path, n_features=5)
    fi = FeatureIndex.open(str(index_dir))
    catalog_path = dashboards.render_catalog(fi, tmp_path / "dash")
    text = catalog_path.read_text(encoding="utf-8")
    for i in range(5):
        assert f"| {i} |" in text
