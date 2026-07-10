"""SS6 specificity: Lodestar rubric (0-3 concept-relatedness) over contexts
sampled from every activation decile of the characterization index.

Invariant: decile contexts are drawn from the characterization index
(`FeatureIndex.feature(i).decile_examples`), never from battery probe
sentences (SS6 invariant, §5.SS6).
"""

from __future__ import annotations

from interplab.characterization.feature_index import FeatureView
from interplab.validation.judge import RubricJudge


def compute_specificity(view: FeatureView, judge: RubricJudge) -> dict:
    """One decile mean per decile present in the index (in ascending decile
    order); deciles with no sampled examples (e.g. columnar-only degraded
    mode, or a dead feature) are simply absent from `decile_means` -- not
    faked as 0.0."""
    decile_means = []
    for decile in sorted(view.decile_examples):
        examples = view.decile_examples[decile]
        if not examples:
            continue
        ratings = [judge.rate(ex["text"]) for ex in examples]
        ratings = [r for r in ratings if r is not None]
        if ratings:
            decile_means.append(sum(ratings) / len(ratings))

    return {
        "decile_means": decile_means,
        "rubric_version": judge.rubric_version,
        "judge_model": judge.model,
        "prompt_version": judge.prompt_version,
    }
