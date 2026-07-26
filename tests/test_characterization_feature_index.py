"""SS5 `FeatureIndex`: the frozen search API (§5.SS5), including the ED-3
additions (n_features/firing_rate/sample_matched_frequency) and degraded
local operation."""

import json
from pathlib import Path

import pytest

from interplab.characterization.feature_index import FeatureIndex, MatchedSampleError


def _write_index(tmp_path: Path, features: list[dict], *, with_examples: bool = True) -> Path:
    out_dir = tmp_path / "index"
    out_dir.mkdir()
    columnar = {
        "index_layout_version": 1,
        "n_features": len(features),
        "n_tokens": 1000,
        "chat_slice_tokens": 0,
        "weights_location": "local:tests/fixtures/tiny_sae",
        "model_location": "local:tests/fixtures/tiny_model",
        "hook_name": "blocks.1.hook_resid_post",
        "judge": {"model": "none", "rubric_version": "none", "prompt_version": "none"},
        "features": features,
    }
    (out_dir / "per_feature_stats.json").write_text(json.dumps(columnar), encoding="utf-8")
    if with_examples:
        examples_dir = out_dir / "examples"
        examples_dir.mkdir()
        for f in features:
            path = examples_dir / f"{f['feature_index']}.jsonl"
            rows = [
                {"decile": "top_k", "rank": 0, "text": f"example for {f['feature_index']}", "activation": 1.0,
                 "token_position": 0, "doc_id": 0}
            ]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return out_dir


def _feature_row(i: int, *, firing_rate: float = 0.1, corpus_max: float = 1.0, direction: list[float] | None = None) -> dict:
    return {
        "feature_index": i,
        "corpus_max": corpus_max,
        "firing_rate": firing_rate,
        "decile_boundaries": [0.1 * k for k in range(1, 10)],
        "activation_histogram": {"bin_edges_log10": [-1.0, 0.0], "counts": [1]},
        "logit_top_tokens": ["a", "b"],
        "autointerp_label": f"label-{i}",
        "autointerp_detection_score": 0.5,
        "decoder_direction": direction or [1.0, 0.0, 0.0],
        "chat_slice_max": None,
        "chat_slice_firing_rate": None,
    }


def test_open_from_local_directory(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0), _feature_row(1)])
    fi = FeatureIndex.open(str(out_dir))
    assert fi.n_features == 2


def test_corpus_max_and_firing_rate(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0, firing_rate=0.05, corpus_max=3.2)])
    fi = FeatureIndex.open(str(out_dir))
    assert fi.corpus_max(0) == 3.2
    assert fi.firing_rate(0) == 0.05


def test_feature_returns_stats_and_examples(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0)])
    fi = FeatureIndex.open(str(out_dir))
    view = fi.feature(0)
    assert view.feature_index == 0
    assert view.examples_available is True
    assert len(view.top_k_examples) == 1


def test_feature_missing_index_raises_keyerror(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0)])
    fi = FeatureIndex.open(str(out_dir))
    with pytest.raises(KeyError):
        fi.feature(99)


def test_degraded_open_without_example_shards(tmp_path):
    """§5.SS5 failure mode: FeatureIndex.open must work against a synced
    columnar subset with example shards absent -- no crash, examples empty."""
    out_dir = _write_index(tmp_path, [_feature_row(0)], with_examples=False)
    assert not (out_dir / "examples").exists()

    fi = FeatureIndex.open(str(out_dir))
    assert fi.n_features == 1
    view = fi.feature(0)
    assert view.examples_available is False
    assert view.top_k_examples == []
    assert view.decile_examples == {}
    # columnar-only data is unaffected by the missing example shards.
    assert view.corpus_max == fi.corpus_max(0)


def test_search_by_cosine_ranks_by_decoder_similarity(tmp_path):
    rows = [
        _feature_row(0, direction=[1.0, 0.0]),
        _feature_row(1, direction=[1.0, 0.0]),  # identical to seed -> highest cosine
        _feature_row(2, direction=[0.0, 1.0]),  # orthogonal -> lowest cosine
    ]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    hits = fi.search_by_cosine(0, top_n=2)
    assert [h.feature_index for h in hits] == [1, 2]
    assert hits[0].score > hits[1].score


def test_search_by_cosine_excludes_seed_index(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0), _feature_row(1)])
    fi = FeatureIndex.open(str(out_dir))
    hits = fi.search_by_cosine(0, top_n=10)
    assert 0 not in [h.feature_index for h in hits]


def test_search_by_label_substring_match_case_insensitive(tmp_path):
    rows = [_feature_row(0), _feature_row(1)]
    rows[0]["autointerp_label"] = "cheese and gouda"
    rows[1]["autointerp_label"] = "unrelated topic"
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    hits = fi.search_by_label("CHEESE", top_n=10)
    assert [h.feature_index for h in hits] == [0]


def test_search_by_label_no_match_returns_empty(tmp_path):
    out_dir = _write_index(tmp_path, [_feature_row(0)])
    fi = FeatureIndex.open(str(out_dir))
    assert fi.search_by_label("nonexistent-topic-xyz", top_n=10) == []


# -- ED-3: sample_matched_frequency -----------------------------------------


def test_sample_matched_frequency_is_deterministic_for_fixed_arguments(tmp_path):
    rows = [_feature_row(i, firing_rate=0.1) for i in range(10)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    a = fi.sample_matched_frequency(0, rng_seed=7)
    b = fi.sample_matched_frequency(0, rng_seed=7)
    assert a == b


def test_sample_matched_frequency_changes_with_seed(tmp_path):
    rows = [_feature_row(i, firing_rate=0.1) for i in range(20)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    draws = {fi.sample_matched_frequency(0, rng_seed=s) for s in range(20)}
    assert len(draws) > 1, "expected different seeds to produce different draws over 20 eligible features"


def test_sample_matched_frequency_respects_band_boundaries(tmp_path):
    rows = [
        _feature_row(0, firing_rate=0.30),  # target
        _feature_row(1, firing_rate=0.10),  # exactly target/3 -> eligible (band=3.0)
        _feature_row(2, firing_rate=0.90),  # exactly target*3 -> eligible
        _feature_row(3, firing_rate=0.05),  # below target/3 -> ineligible
        _feature_row(4, firing_rate=2.00),  # above target*3 -> ineligible
    ]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    for seed in range(10):
        draw = fi.sample_matched_frequency(0, rng_seed=seed, band=3.0)
        assert draw in (1, 2)


def test_sample_matched_frequency_excludes_target_index(tmp_path):
    rows = [_feature_row(i, firing_rate=0.1) for i in range(5)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    for seed in range(10):
        assert fi.sample_matched_frequency(0, rng_seed=seed) != 0


def test_sample_matched_frequency_honors_explicit_exclude(tmp_path):
    rows = [_feature_row(i, firing_rate=0.1) for i in range(3)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    for seed in range(10):
        draw = fi.sample_matched_frequency(0, rng_seed=seed, exclude=frozenset({1}))
        assert draw == 2


def test_sample_matched_frequency_raises_on_empty_band(tmp_path):
    rows = [_feature_row(0, firing_rate=0.1), _feature_row(1, firing_rate=100.0)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    with pytest.raises(MatchedSampleError):
        fi.sample_matched_frequency(0, rng_seed=0, band=3.0)


def test_sample_matched_frequency_never_silently_widens_band(tmp_path):
    """An empty band raises rather than being silently widened -- calling
    it twice with the same (impossible) arguments always raises, never
    falls back to a looser match."""
    rows = [_feature_row(0, firing_rate=0.1), _feature_row(1, firing_rate=100.0)]
    out_dir = _write_index(tmp_path, rows)
    fi = FeatureIndex.open(str(out_dir))
    with pytest.raises(MatchedSampleError):
        fi.sample_matched_frequency(0, rng_seed=0, band=3.0)
    with pytest.raises(MatchedSampleError):
        fi.sample_matched_frequency(0, rng_seed=1, band=3.0)


# -- search_by_activation (live model+SAE) -----------------------------------


def test_search_by_activation_ranks_features_on_new_text(tmp_path, tiny_hooked_transformer, tiny_sae):
    from interplab.characterization import indexer as indexer_mod

    index = indexer_mod.build_index(
        tiny_hooked_transformer, tiny_sae, corpus_docs=["cheese gouda brie", "unrelated filler text"],
        judge=indexer_mod.NoOpJudge(),
        weights_location="local:tests/fixtures/tiny_sae", model_location="local:tests/fixtures/tiny_model",
    )
    out_dir = tmp_path / "index"
    indexer_mod.write_index(index, out_dir)

    fi = FeatureIndex.open(str(out_dir))
    hits = fi.search_by_activation(["cheese gouda brie"], top_n=5)
    assert len(hits) == 5
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_index_open_by_content_hash_via_registry(tmp_path):
    """`FeatureIndex.open` resolves a `sha256:` hash by looking up the A7
    manifest's `subject` role="index" entry -- `local:` URIs always resolve
    against the *real* repo root (§3.2), so the index dir has to live
    somewhere real-repo-relative (results/ is gitignored) for this branch
    to be exercisable at all."""
    import shutil

    from interplab.core import envelope, uris
    from interplab.registry.registry import put as registry_put

    real_index_dir = uris.REPO_ROOT / "results" / "_test_scratch" / "feature_index_open_by_hash"
    if real_index_dir.exists():
        shutil.rmtree(real_index_dir)
    real_index_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_index(real_index_dir.parent, [_feature_row(0)])
        (real_index_dir.parent / "index").rename(real_index_dir)

        created_by = {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}
        manifest = envelope.dump(
            artifact_type="characterization_manifest", schema_version=1, created_by=created_by,
            subject=[
                {"content_hash": "sha256:" + "a" * 64, "location": "local:x", "role": "sae_checkpoint"},
                {
                    "content_hash": "sha256:" + "b" * 64,
                    "location": f"local:{real_index_dir.relative_to(uris.REPO_ROOT).as_posix()}",
                    "role": "index",
                },
            ],
            payload={
                "sample": {"n_tokens": 10, "chat_slice_tokens": 0},
                "index_layout_version": 1,
                "per_feature_columns": [
                    "corpus_max", "firing_rate", "decile_boundaries", "logit_top_tokens",
                    "autointerp_label", "autointerp_detection_score",
                ],
                "judge": {"model": "none", "rubric_version": "none", "prompt_version": "none"},
            },
        )
        registry_root = tmp_path / "registry"
        manifest_hash = registry_put(manifest, registry_root=registry_root)

        fi = FeatureIndex.open(manifest_hash, registry_root=registry_root)
        assert fi.n_features == 1
    finally:
        shutil.rmtree(real_index_dir, ignore_errors=True)


def test_index_open_by_content_hash_via_registry_resolves_tamia_location(tmp_path, monkeypatch):
    """ED-34: the registry-ref branch resolves a `tamia:` index location via
    `$SCRATCH`, same as the `local:` case above -- the degraded bare-local-
    directory branch (`test_open_from_local_directory`) is untouched by this
    fix by construction, since it short-circuits before any URI parsing."""
    from interplab.core import envelope
    from interplab.registry.registry import put as registry_put

    scratch = tmp_path / "scratch"
    monkeypatch.setenv("SCRATCH", str(scratch))
    index_dir = scratch / "interplab" / "characterization_indexes" / "abc123"
    index_dir.parent.mkdir(parents=True)
    _write_index(index_dir.parent, [_feature_row(0)])
    (index_dir.parent / "index").rename(index_dir)

    created_by = {"run_id": "r20260709-0000-abcd", "code_commit": "0" * 40, "entrypoint": "test", "host": "tamia"}
    manifest = envelope.dump(
        artifact_type="characterization_manifest", schema_version=1, created_by=created_by,
        subject=[
            {"content_hash": "sha256:" + "a" * 64, "location": "local:x", "role": "sae_checkpoint"},
            {
                "content_hash": "sha256:" + "b" * 64,
                "location": "tamia:characterization_indexes/abc123",
                "role": "index",
            },
        ],
        payload={
            "sample": {"n_tokens": 10, "chat_slice_tokens": 0},
            "index_layout_version": 1,
            "per_feature_columns": [
                "corpus_max", "firing_rate", "decile_boundaries", "logit_top_tokens",
                "autointerp_label", "autointerp_detection_score",
            ],
            "judge": {"model": "none", "rubric_version": "none", "prompt_version": "none"},
        },
    )
    registry_root = tmp_path / "registry"
    manifest_hash = registry_put(manifest, registry_root=registry_root)

    fi = FeatureIndex.open(manifest_hash, registry_root=registry_root)
    assert fi.n_features == 1
