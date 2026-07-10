"""ED-17 statistics composition: bootstrap_ci/seed_variance land in the
schema-fixed `statistics` shape; effect_size is supplementary (no CI, so
never forced into that shape -- see `interplab.reports.statistics`'s
module docstring)."""

from __future__ import annotations

from interplab.reports import statistics as statistics_mod


def _anchor(per_prompt_scores):
    return {
        "self_hash": "sha256:" + "1" * 64,
        "payload": {"lodestar": {"run_ref": "x", "judge_model": "m", "rubric_version": "v", "per_prompt_scores": per_prompt_scores}},
    }


def test_no_anchors_with_scores_yields_none():
    stats, effects = statistics_mod.compose_statistics([None, None])
    assert stats is None
    assert effects == []


def test_anchor_without_lodestar_yields_none():
    anchor = {"self_hash": "x", "payload": {"lodestar": None}}
    stats, effects = statistics_mod.compose_statistics([anchor])
    assert stats is None
    assert effects == []


def test_single_anchor_bootstrap_and_effect_size():
    scores = [
        {"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.9},
        {"prompt_id": "p2", "arm": "steered", "scale": 1.0, "score": 0.8},
        {"prompt_id": "p3", "arm": "steered", "scale": 1.0, "score": 0.85},
        {"prompt_id": "p1", "arm": "baseline", "scale": 1.0, "score": 0.1},
        {"prompt_id": "p2", "arm": "baseline", "scale": 1.0, "score": 0.15},
        {"prompt_id": "p3", "arm": "baseline", "scale": 1.0, "score": 0.2},
    ]
    stats, effects = statistics_mod.compose_statistics([_anchor(scores)])

    assert stats is not None
    steered_key = "lodestar_score|arm=steered|scale=1.0"
    baseline_key = "lodestar_score|arm=baseline|scale=1.0"
    assert steered_key in stats and baseline_key in stats
    entry = stats[steered_key]
    assert entry["n_prompts"] == 3
    assert entry["n_seeds"] == 1
    assert entry["ci_low"] <= entry["estimate"] <= entry["ci_high"]
    assert entry["method"] == "bootstrap_ci+seed_variance"

    assert len(effects) == 1
    eff = effects[0]
    assert eff.arm == "steered" and eff.baseline_arm == "baseline"
    assert eff.d > 0  # steered scores are higher than baseline


def test_baseline_arm_gets_no_effect_size_entry():
    scores = [
        {"prompt_id": "p1", "arm": "baseline", "scale": 1.0, "score": 0.1},
        {"prompt_id": "p2", "arm": "baseline", "scale": 1.0, "score": 0.2},
    ]
    stats, effects = statistics_mod.compose_statistics([_anchor(scores)])
    assert "lodestar_score|arm=baseline|scale=1.0" in stats
    assert effects == []


def test_two_anchor_replicates_surface_n_seeds_2():
    scores_a = [
        {"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.9},
        {"prompt_id": "p2", "arm": "steered", "scale": 1.0, "score": 0.8},
    ]
    scores_b = [
        {"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.7},
        {"prompt_id": "p2", "arm": "steered", "scale": 1.0, "score": 0.6},
    ]
    stats, _effects = statistics_mod.compose_statistics([_anchor(scores_a), _anchor(scores_b)])
    entry = stats["lodestar_score|arm=steered|scale=1.0"]
    assert entry["n_seeds"] == 2
    assert entry["n_prompts"] == 2  # same 2 prompt_ids recur across both anchors, not 4 distinct


def test_degenerate_effect_size_is_omitted_not_fabricated():
    """Both arms constant but at *different* levels -> pooled_std is zero
    (zero within-condition variance) while the means differ:
    DegenerateEffectError from the frozen `effect_size` primitive, must be
    skipped, never reported as a fabricated d=0.0 ("no effect")."""
    scores = [
        {"prompt_id": "p1", "arm": "steered", "scale": 1.0, "score": 0.9},
        {"prompt_id": "p2", "arm": "steered", "scale": 1.0, "score": 0.9},
        {"prompt_id": "p1", "arm": "baseline", "scale": 1.0, "score": 0.1},
        {"prompt_id": "p2", "arm": "baseline", "scale": 1.0, "score": 0.1},
    ]
    _stats, effects = statistics_mod.compose_statistics([_anchor(scores)])
    assert effects == []
