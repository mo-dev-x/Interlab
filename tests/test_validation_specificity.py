"""SS6 specificity: rubric over characterization-index decile examples."""

from interplab.characterization.feature_index import FeatureView
from interplab.validation.judge import NoOpRubricJudge, StubRubricJudge
from interplab.validation.specificity import compute_specificity


def _view(decile_examples: dict) -> FeatureView:
    return FeatureView(
        feature_index=0, corpus_max=1.0, firing_rate=0.1, decile_boundaries=[0.1] * 9,
        activation_histogram={"bin_edges_log10": [], "counts": []}, logit_top_tokens=[],
        autointerp_label=None, autointerp_detection_score=None, chat_slice_max=None,
        chat_slice_firing_rate=None, top_k_examples=[], decile_examples=decile_examples,
        examples_available=True,
    )


def test_decile_means_computed_per_decile_in_ascending_order():
    view = _view({
        0: [{"text": "no relevant words"}],
        1: [{"text": "cheese cheese"}],
    })
    judge = StubRubricJudge(marker_words=frozenset({"cheese"}))
    result = compute_specificity(view, judge)
    assert result["decile_means"] == [0.0, 2.0]


def test_decile_with_no_examples_is_omitted_not_faked_as_zero():
    view = _view({0: [], 1: [{"text": "cheese"}]})
    judge = StubRubricJudge(marker_words=frozenset({"cheese"}))
    result = compute_specificity(view, judge)
    assert result["decile_means"] == [1.0]


def test_noop_judge_gives_empty_decile_means_not_fabricated_zeros():
    view = _view({0: [{"text": "cheese"}], 1: [{"text": "gouda"}]})
    judge = NoOpRubricJudge()
    result = compute_specificity(view, judge)
    assert result["decile_means"] == []


def test_records_judge_versions_verbatim():
    view = _view({0: [{"text": "cheese"}]})
    judge = StubRubricJudge(marker_words=frozenset({"cheese"}), model="m1", rubric_version="r1", prompt_version="p1")
    result = compute_specificity(view, judge)
    assert result["judge_model"] == "m1"
    assert result["rubric_version"] == "r1"
    assert result["prompt_version"] == "p1"


def test_multiple_examples_per_decile_averaged():
    view = _view({0: [{"text": "cheese"}, {"text": "no match"}, {"text": "cheese cheese"}]})
    judge = StubRubricJudge(marker_words=frozenset({"cheese"}))
    result = compute_specificity(view, judge)
    # ratings: 1, 0, 2 -> mean 1.0
    assert result["decile_means"] == [1.0]
