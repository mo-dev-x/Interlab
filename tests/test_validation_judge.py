"""SS6 rubric judge (D2 stub-judge pattern, continued from WP4)."""

from interplab.validation.judge import NoOpRubricJudge, StubRubricJudge


def test_noop_judge_records_none_model():
    j = NoOpRubricJudge()
    assert j.model == "none"
    assert j.rate("cheese and gouda") is None


def test_noop_judge_never_produces_a_fabricated_score():
    j = NoOpRubricJudge()
    for text in ["", "zorbium zorbium zorbium", "unrelated filler"]:
        assert j.rate(text) is None


def test_stub_judge_records_configured_versions():
    j = StubRubricJudge(marker_words=frozenset({"cheese"}), model="m1", rubric_version="r1", prompt_version="p1")
    assert j.model == "m1"
    assert j.rubric_version == "r1"
    assert j.prompt_version == "p1"


def test_stub_judge_rates_by_marker_word_count_capped_at_three():
    j = StubRubricJudge(marker_words=frozenset({"cheese"}))
    assert j.rate("no relevant words here") == 0.0
    assert j.rate("cheese is great") == 1.0
    assert j.rate("cheese cheese cheese cheese") == 3.0  # capped at 3


def test_stub_judge_is_case_insensitive_and_strips_punctuation():
    j = StubRubricJudge(marker_words=frozenset({"cheese"}))
    assert j.rate("Cheese! CHEESE, cheese.") == 3.0
