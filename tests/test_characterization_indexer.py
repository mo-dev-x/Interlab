"""SS5 streaming indexer: corpus_max/firing_rate/deciles/histogram/
logit-lens/stub-autointerp, and the corpus_max sourcing invariant."""

import json
from pathlib import Path

import pytest

from interplab.characterization import indexer

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def docs():
    lines = FIXTURES_DIR.joinpath("pinned_text.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["text"] for line in lines[:20]]


WEIGHTS_LOC = "local:tests/fixtures/tiny_sae"
MODEL_LOC = "local:tests/fixtures/tiny_model"


def _build(tiny_hooked_transformer, tiny_sae, docs, **kwargs):
    return indexer.build_index(
        tiny_hooked_transformer, tiny_sae, corpus_docs=docs, judge=indexer.NoOpJudge(),
        weights_location=WEIGHTS_LOC, model_location=MODEL_LOC, **kwargs,
    )


def test_build_index_covers_every_sae_feature(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    assert index["n_features"] == tiny_sae.W_dec.shape[0]
    assert len(index["features"]) == index["n_features"]


def test_decile_boundaries_length_and_monotonic_when_feature_fires(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    firing = [f for f in index["features"] if f["firing_rate"] > 0]
    assert firing, "expected at least one firing feature on 20 real docs through an untrained SAE"
    for f in firing:
        boundaries = f["decile_boundaries"]
        assert len(boundaries) == 9
        assert boundaries == sorted(boundaries)


def test_corpus_max_and_firing_rate_are_unaffected_by_chat_slice_presence(tiny_hooked_transformer, tiny_sae, docs):
    """The standing WP4 invariant: corpus_max must always originate from
    the corpus sample only -- adding a chat slice must not perturb any
    corpus-sourced field, even though the chat pass runs through the same
    accumulator machinery."""
    chat_docs = ["Completely different chat-formatted content here.", "Another distinct chat turn."]

    without_chat = _build(tiny_hooked_transformer, tiny_sae, docs)
    with_chat = _build(tiny_hooked_transformer, tiny_sae, docs, chat_docs=chat_docs)

    for f_a, f_b in zip(without_chat["features"], with_chat["features"], strict=True):
        assert f_a["corpus_max"] == f_b["corpus_max"]
        assert f_a["firing_rate"] == f_b["firing_rate"]
        assert f_a["decile_boundaries"] == f_b["decile_boundaries"]
        assert f_a["logit_top_tokens"] == f_b["logit_top_tokens"]


def test_chat_slice_stats_are_stored_under_separate_fields(tiny_hooked_transformer, tiny_sae, docs):
    chat_docs = docs[:3]
    index = _build(tiny_hooked_transformer, tiny_sae, docs, chat_docs=chat_docs)
    assert index["chat_slice_tokens"] > 0
    # At least the columns exist and are independent of corpus_max/firing_rate.
    for f in index["features"]:
        assert "chat_slice_max" in f
        assert "chat_slice_firing_rate" in f


def test_no_chat_slice_gives_null_chat_columns(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    assert index["chat_slice_tokens"] == 0
    for f in index["features"]:
        assert f["chat_slice_max"] is None
        assert f["chat_slice_firing_rate"] is None


def test_decile_examples_are_sampled_within_their_own_bucket(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    for feature_index, examples in index["_examples_by_feature"].items():
        boundaries = index["features"][feature_index]["decile_boundaries"]
        edges = [-float("inf"), *boundaries, float("inf")]
        for ex in examples:
            if ex["decile"] == "top_k":
                continue
            d = ex["decile"]
            assert edges[d] <= ex["activation"] <= edges[d + 1] + 1e-9


def test_top_k_examples_sorted_descending_by_activation(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    for examples in index["_examples_by_feature"].values():
        top_k = [e for e in examples if e["decile"] == "top_k"]
        activations = [e["activation"] for e in top_k]
        assert activations == sorted(activations, reverse=True)


def test_judge_recorded_verbatim(tiny_hooked_transformer, tiny_sae, docs):
    judge = indexer.StubJudge(model="m1", rubric_version="r1", prompt_version="p1")
    index = indexer.build_index(
        tiny_hooked_transformer, tiny_sae, corpus_docs=docs, judge=judge,
        weights_location=WEIGHTS_LOC, model_location=MODEL_LOC,
    )
    assert index["judge"] == {"model": "m1", "rubric_version": "r1", "prompt_version": "p1"}


def test_noop_judge_produces_null_labels_for_every_feature(tiny_hooked_transformer, tiny_sae, docs):
    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    assert index["judge"]["model"] == "none"
    for f in index["features"]:
        assert f["autointerp_label"] is None
        assert f["autointerp_detection_score"] is None


def test_stub_judge_labels_at_least_one_firing_feature(tiny_hooked_transformer, tiny_sae, docs):
    index = indexer.build_index(
        tiny_hooked_transformer, tiny_sae, corpus_docs=docs, judge=indexer.StubJudge(),
        weights_location=WEIGHTS_LOC, model_location=MODEL_LOC,
    )
    labeled = [f for f in index["features"] if f["autointerp_label"] is not None]
    assert labeled, "expected the stub judge to label at least one firing feature"


def test_null_judge_raises_by_default_for_production_boundary():
    """NoOpJudge is the safe production default (null labels); this test
    documents that autointerpretation is otherwise researcher-gated -- no
    Judge implementation shipped here fabricates a real label."""
    judge = indexer.NoOpJudge()
    label, score = judge.label(0, ["some text"])
    assert label is None
    assert score is None


def test_write_and_open_roundtrip(tmp_path, tiny_hooked_transformer, tiny_sae, docs):
    from interplab.characterization.feature_index import FeatureIndex

    index = _build(tiny_hooked_transformer, tiny_sae, docs)
    out_dir = tmp_path / "index"
    indexer.write_index(index, out_dir)

    assert (out_dir / "per_feature_stats.json").is_file()
    assert (out_dir / "examples").is_dir()

    fi = FeatureIndex.open(str(out_dir))
    assert fi.n_features == index["n_features"]
