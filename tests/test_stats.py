"""SS9 `interplab.stats` (TRUNK): the four frozen statistics primitives."""

import numpy as np
import pytest

from interplab.stats import (
    CI,
    CohensD,
    DegenerateEffectError,
    SeedVar,
    bh_fdr,
    bootstrap_ci,
    effect_size,
    seed_variance,
)

# -- bootstrap_ci -------------------------------------------------------------


def test_bootstrap_ci_returns_ci_dataclass():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    groups = [0, 0, 1, 1, 2, 2]
    ci = bootstrap_ci(values, groups, n_boot=500, seed=0)
    assert isinstance(ci, CI)


def test_bootstrap_ci_estimate_is_the_real_mean_not_a_bootstrap_product():
    values = [1.0, 2.0, 3.0, 4.0]
    groups = [0, 1, 2, 3]
    ci = bootstrap_ci(values, groups, n_boot=100, seed=0)
    assert ci.estimate == pytest.approx(2.5)


def test_bootstrap_ci_deterministic_for_fixed_seed():
    rng = np.random.default_rng(1)
    values = rng.normal(size=100)
    groups = np.repeat(np.arange(20), 5)
    a = bootstrap_ci(values, groups, n_boot=1000, seed=42)
    b = bootstrap_ci(values, groups, n_boot=1000, seed=42)
    assert a == b


def test_bootstrap_ci_different_seeds_give_different_bounds():
    rng = np.random.default_rng(1)
    values = rng.normal(size=100)
    groups = np.repeat(np.arange(20), 5)
    a = bootstrap_ci(values, groups, n_boot=500, seed=1)
    b = bootstrap_ci(values, groups, n_boot=500, seed=2)
    assert (a.ci_low, a.ci_high) != (b.ci_low, b.ci_high)


def test_bootstrap_ci_n_groups_matches_unique_group_count():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    groups = ["p1", "p1", "p2", "p2", "p3", "p3"]
    ci = bootstrap_ci(values, groups, n_boot=200, seed=0)
    assert ci.n_groups == 3


def test_bootstrap_ci_resamples_groups_not_individual_values():
    """The defining invariant: resampling unit is the GROUP, so all values
    within a resampled group always travel together. A degenerate dataset
    where every group is internally uniform but groups differ wildly makes
    this observable: every bootstrap replicate's mean must be an average of
    whole per-group means, so the CI must stay within [min group mean, max
    group mean] -- resampling individual values instead would let extreme
    combinations of *within-group* value pairs leak the CI outside that
    range on a suitably adversarial (but here trivial, uniform-per-group)
    input."""
    # Groups 0/1/2 have per-group constant values 0, 0, 100 -- if values
    # were resampled independently of groups, replicate means could take on
    # many more distinct values than the 3 possible whole-group-average
    # combinations actually available here.
    values = [0.0, 0.0, 0.0, 0.0, 100.0, 100.0]
    groups = [0, 0, 1, 1, 2, 2]
    ci = bootstrap_ci(values, groups, n_boot=3000, seed=0)
    assert ci.ci_low >= 0.0
    assert ci.ci_high <= 100.0


def test_bootstrap_ci_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], [0], n_boot=10, seed=0)


def test_bootstrap_ci_empty_values_raises():
    with pytest.raises(ValueError):
        bootstrap_ci([], [], n_boot=10, seed=0)


def test_bootstrap_ci_level_widens_interval():
    rng = np.random.default_rng(3)
    values = rng.normal(size=200)
    groups = np.repeat(np.arange(40), 5)
    narrow = bootstrap_ci(values, groups, n_boot=2000, level=0.80, seed=0)
    wide = bootstrap_ci(values, groups, n_boot=2000, level=0.99, seed=0)
    assert (wide.ci_high - wide.ci_low) > (narrow.ci_high - narrow.ci_low)


# -- bh_fdr ---------------------------------------------------------------


def test_bh_fdr_returns_boolean_mask_in_original_order():
    pvalues = [0.5, 0.001, 0.2]
    mask = bh_fdr(pvalues, q=0.05)
    assert mask.dtype == bool
    assert len(mask) == 3


def test_bh_fdr_all_null_all_rejected_below_threshold():
    """m=1, single p-value below q -> always rejected."""
    mask = bh_fdr([0.001], q=0.05)
    assert mask.tolist() == [True]


def test_bh_fdr_nothing_significant_when_all_pvalues_large():
    mask = bh_fdr([0.9, 0.8, 0.7], q=0.05)
    assert not mask.any()


def test_bh_fdr_matches_hand_computed_example():
    # sorted: 0.001, 0.01, 0.02, 0.5, 0.7, 0.9 ; m=6, q=0.05
    # thresholds: 0.00833, 0.01667, 0.025, 0.0333, 0.0417, 0.05
    # 0.001<=t1 T, 0.01<=t2 T, 0.02<=t3 T, 0.5<=t4 F, 0.7<=t5 F, 0.9<=t6 F -> reject first 3
    pvalues = [0.001, 0.01, 0.02, 0.5, 0.7, 0.9]
    mask = bh_fdr(pvalues, q=0.05)
    assert mask.tolist() == [True, True, True, False, False, False]


def test_bh_fdr_preserves_original_order_not_sorted_order():
    pvalues = [0.9, 0.001, 0.5]  # unsorted; only index 1 should be rejected
    mask = bh_fdr(pvalues, q=0.05)
    assert mask.tolist() == [False, True, False]


def test_bh_fdr_empty_input():
    mask = bh_fdr([], q=0.05)
    assert mask.tolist() == []


def test_bh_fdr_larger_q_rejects_at_least_as_many():
    rng = np.random.default_rng(0)
    pvalues = rng.uniform(0, 1, size=50)
    strict = bh_fdr(pvalues, q=0.01)
    loose = bh_fdr(pvalues, q=0.20)
    assert loose.sum() >= strict.sum()


# -- seed_variance -------------------------------------------------------------


def test_seed_variance_n_seeds_always_present():
    sv = seed_variance([1.0, 2.0, 3.0])
    assert isinstance(sv, SeedVar)
    assert sv.n_seeds == 3


def test_seed_variance_single_seed_std_is_none_not_zero():
    """ED-9-style discipline: std is unmeasurable from one sample, so it's
    None, never a dishonest 0.0."""
    sv = seed_variance([5.0])
    assert sv.n_seeds == 1
    assert sv.std is None
    assert sv.mean == 5.0


def test_seed_variance_two_seeds_computes_std():
    sv = seed_variance([1.0, 3.0])
    assert sv.n_seeds == 2
    assert sv.std is not None
    assert sv.mean == 2.0


def test_seed_variance_zero_seeds():
    sv = seed_variance([])
    assert sv.n_seeds == 0
    assert sv.std is None


def test_seed_variance_preserves_per_seed_values():
    sv = seed_variance([1.0, 2.0, 3.0])
    assert sv.per_seed == [1.0, 2.0, 3.0]


# -- effect_size ----------------------------------------------------------


def test_effect_size_returns_cohens_d_dataclass():
    groups = [0, 1, 2, 3]
    a = [1.0, 2.0, 3.0, 4.0]
    b = [2.0, 3.0, 4.0, 5.0]
    es = effect_size(a, b, groups)
    assert isinstance(es, CohensD)


def test_effect_size_zero_for_identical_distributions():
    groups = list(range(10))
    a = [float(i) for i in range(10)]
    b = [float(i) for i in range(10)]
    es = effect_size(a, b, groups)
    assert es.d == pytest.approx(0.0)


def test_effect_size_matches_hand_computed_pooled_formula():
    # Two groups per condition, no within-group aggregation needed (1 obs/group).
    a = [2.0, 4.0]  # mean=3, var(ddof=1)=2
    b = [0.0, 0.0]  # mean=0, var(ddof=1)=0
    groups = [0, 1]
    es = effect_size(a, b, groups)
    # pooled_std = sqrt(((2-1)*2 + (2-1)*0) / (2+2-2)) = sqrt(2/2) = 1
    # d = (3 - 0) / 1 = 3
    assert es.d == pytest.approx(3.0)
    assert es.n_a == 2
    assert es.n_b == 2


def test_effect_size_aggregates_multiple_observations_per_group():
    """Multiple generations for the same prompt must not add extra weight
    -- aggregated to one mean per group before the pooled-std formula."""
    groups = [0, 0, 0, 1, 1, 1]  # 3 observations each for 2 prompts
    a = [10.0, 10.0, 10.0, 0.0, 0.0, 0.0]  # group means: 10, 0
    b = [10.0, 10.0, 10.0, 0.0, 0.0, 0.0]  # identical -> d should be 0
    es = effect_size(a, b, groups)
    assert es.d == pytest.approx(0.0)
    assert es.n_a == 2  # aggregated down to 2 groups, not 6 raw observations


def test_effect_size_mismatched_lengths_raises():
    with pytest.raises(ValueError):
        effect_size([1.0, 2.0], [1.0], [0, 1])


def test_effect_size_requires_at_least_two_groups():
    with pytest.raises(ValueError):
        effect_size([1.0], [2.0], [0])


def test_effect_size_sign_reflects_direction():
    groups = list(range(5))
    a_arr = [5.0, 5.1, 4.9, 5.0, 5.05]
    b_arr = [1.0, 1.1, 0.9, 1.0, 1.05]
    es_pos = effect_size(a_arr, b_arr, groups)
    es_neg = effect_size(b_arr, a_arr, groups)
    assert es_pos.d > 0
    assert es_neg.d < 0
    assert es_pos.d == pytest.approx(-es_neg.d)


def test_effect_size_constant_scores_different_means_raises_degenerate_effect_error():
    """Zero pooled std with genuinely different means is a degenerate case,
    not "no effect" -- must raise, never silently report d=0.0."""
    groups = [0, 1, 2]
    baseline = [2.0, 2.0, 2.0]
    steered = [3.0, 3.0, 3.0]
    with pytest.raises(DegenerateEffectError):
        effect_size(steered, baseline, groups)


def test_effect_size_constant_scores_equal_means_returns_zero():
    """Zero pooled std with equal means is genuinely zero effect."""
    groups = [0, 1, 2]
    a = [2.0, 2.0, 2.0]
    b = [2.0, 2.0, 2.0]
    es = effect_size(a, b, groups)
    assert es.d == 0.0
