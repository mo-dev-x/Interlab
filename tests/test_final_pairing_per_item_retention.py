"""CPU-only tests for the PER-ITEM probe-score retention in
`final_pairing_concept_discovery.py`.

WHY THIS RETENTION EXISTS. An AUROC is a summary and cannot be resampled; its
inputs can. `rank_auroc_matrix(positives, negatives)` holds every feature's
per-item probe scores in memory simultaneously and then discards them, keeping
only the aggregate -- so the question "would this cell's ceiling still sit
below the bar under a resample of its ten positives?" was UNANSWERABLE from
the output rather than merely unanswered. LA-B enumerated all 98 distinct keys
across all five rescued grids and searched 22 candidate field names over 43
files: per-item scores are absent everywhere. A collapse at retention is
irreversible, which is the same finding this file has already been corrected
for twice.

WHAT THESE TESTS ARE MOSTLY ABOUT: THAT IT IS A TRUNCATION AND SAYS SO. This
sprint's recurring defect is a truncation later mistaken for full coverage --
the 182-vs-295 undercount, a top-25 shortlist read as the space, a withdrawn
pooled f3-boundness claim. So the record declares its own scope AS DATA and
`verify_per_item_retention` REFUSES a record whose declaration disagrees with
its contents. A scope declaration that could not be contradicted would be
decoration; these tests are what make it falsifiable.

NO GPU, NO MODEL WEIGHTS, NO GENERATION.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
from final_pairing_fakes import make_fake_gemma_backend  # noqa: E402

CELLS = ("en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3")
DISCOVERY_PATH = REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_concept_discovery.py"


def _block(d_sae=64, seed=0, n_pos=10, n_near=15, n_unrelated=15):
    rng = np.random.default_rng(seed)
    positives = rng.random((n_pos, d_sae))
    near_miss = rng.random((n_near, d_sae))
    unrelated = rng.random((n_unrelated, d_sae))
    limbs = {
        "separation_auroc": d.rank_auroc_matrix(
            positives, np.concatenate([unrelated, near_miss], axis=0)
        ),
        "fire_rate": d.fire_rate_matrix(positives, floor_fraction=0.5)[0],
        "near_miss_auroc": d.rank_auroc_matrix(positives, near_miss),
    }
    block = d.per_item_retention_for_cell(
        positives=positives, near_miss=near_miss, unrelated=unrelated, limb_values=limbs
    )
    return block, positives, near_miss, unrelated, limbs


def _record(**kwargs):
    block, *_rest = _block(**kwargs)
    return d.build_per_item_retention_record(
        {cell: copy.deepcopy(block) for cell in CELLS}, d_sae=kwargs.get("d_sae", 64)
    )


# ---------------------------------------------------------------------------
# CONTROL BLOCK 1 -- THE TRUNCATION MUST NOT BE ABLE TO PASS AS THE SPACE
# ---------------------------------------------------------------------------


def test_a_missing_argmax_is_detected_and_refused_rather_than_emitted_short():
    """CONTROL 1, the one the coordinator asked for by name. The entire
    scoping argument is "a CEILING feature is by definition a per-cell maximum
    and therefore a per-cell leader, so it is retained". If that ever fails,
    the block cannot support a resample of the ceiling it claims to cover --
    and a short record that certified itself as sufficient would be this
    sprint's defect in its purest form.

    Constructed by removing the G-A argmax from a REAL record, which is the
    exact shape the failure would take."""
    record = _record()
    cell = record["cells"]["en/f1"]
    argmax = cell["argmax_feature_by_limb"]["G-A"]
    assert argmax in cell["retained_feature_indices"]
    # Remove the argmax, and keep every count self-consistent so that ONLY the
    # argmax rule can catch it. A tamper that also broke the counts would not
    # prove this control fires.
    cell["retained_feature_indices"] = [i for i in cell["retained_feature_indices"] if i != argmax]
    cell["per_item_scores_by_feature"].pop(str(argmax))
    cell["features_retained"] -= 1
    cell["features_NOT_retained"] += 1
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="argmax"):
        d.verify_per_item_retention(record)


def test_a_declared_argmax_with_no_stored_scores_is_refused():
    """A retention that was DECLARED and did not happen is worse than no
    retention: the record would name the feature a resample needs and carry
    nothing for it."""
    record = _record()
    cell = record["cells"]["fr/f2"]
    argmax = cell["argmax_feature_by_limb"]["G-A"]
    cell["per_item_scores_by_feature"].pop(str(argmax))
    with pytest.raises(d.PerItemRetentionScopeMismatch):
        d.verify_per_item_retention(record)


def test_a_declared_scope_that_disagrees_with_the_contents_is_refused():
    """CONTROL 2, also asked for by name. Five independent disagreements, each
    tampered separately, because a check that only caught one of them would
    pass while unable to exercise what it claims."""
    # (a) the declared count disagrees with the index list
    record = _record()
    record["cells"]["en/f1"]["features_retained"] += 1
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="lists"):
        d.verify_per_item_retention(record)

    # (b) the declared count disagrees with the stored features
    record = _record()
    cell = record["cells"]["en/f2"]
    dropped = cell["retained_feature_indices"][-1]
    if dropped in cell["argmax_feature_by_limb"].values():
        dropped = next(
            i for i in cell["retained_feature_indices"]
            if i not in cell["argmax_feature_by_limb"].values()
        )
    cell["per_item_scores_by_feature"].pop(str(dropped))
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="stores per-item"):
        d.verify_per_item_retention(record)

    # (c) the dropped count does not reconcile -- the only field that makes
    # this truncation's own size visible
    record = _record()
    record["cells"]["en/f3"]["features_NOT_retained"] += 7
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="do not reconcile"):
        d.verify_per_item_retention(record)

    # (d) a per-item vector shorter than its declared split cannot be
    # resampled and must not read as if it could
    record = _record()
    cell = record["cells"]["fr/f1"]
    first = cell["retained_feature_indices"][0]
    cell["per_item_scores_by_feature"][str(first)]["positives"].pop()
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="cannot be resampled"):
        d.verify_per_item_retention(record)

    # (e) a split missing altogether
    record = _record()
    cell = record["cells"]["fr/f3"]
    first = cell["retained_feature_indices"][0]
    cell["per_item_scores_by_feature"][str(first)].pop("unrelated")
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="per-item splits are"):
        d.verify_per_item_retention(record)


def test_a_record_that_declares_nothing_about_its_scope_is_refused():
    """A record with no scope block cannot be distinguished from a full-space
    record, which is the whole failure mode."""
    record = _record()
    del record["scope"]
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="declares nothing"):
        d.verify_per_item_retention(record)

    record = _record()
    record["scope"]["top_k"] = 0
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="positive k as DATA"):
        d.verify_per_item_retention(record)

    record = _record()
    record["scope"]["splits_retained"] = ["positives"]
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="All three are"):
        d.verify_per_item_retention(record)

    # ZERO CELLS: `all()` over nothing would report every check satisfied.
    record = _record()
    record["cells"] = {}
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="vacuity"):
        d.verify_per_item_retention(record)


def test_a_top_k_below_one_cannot_contain_any_argmax_and_is_refused_at_source():
    with pytest.raises(d.PerItemRetentionScopeMismatch, match="at least 1"):
        d.per_item_retention_for_cell(
            positives=np.random.default_rng(1).random((10, 8)),
            near_miss=np.random.default_rng(2).random((15, 8)),
            unrelated=np.random.default_rng(3).random((15, 8)),
            limb_values={
                "separation_auroc": np.zeros(8), "fire_rate": np.zeros(8),
                "near_miss_auroc": np.zeros(8),
            },
            top_k=0,
        )


# ---------------------------------------------------------------------------
# THE SCOPE DECLARATION, AND THE SINGLE RANKING
# ---------------------------------------------------------------------------


def test_the_record_states_its_own_scope_as_data_not_as_a_comment():
    """The scope must travel with a `grid.json`, so every clause a future
    reader needs in order NOT to mistake this for the space is a FIELD."""
    record = _record(d_sae=64)
    scope = record["scope"]
    # The KEY names the hazard so it is unmissable in a JSON dump; the VALUE
    # says what the scope actually is, in numbers.
    assert "THIS_IS_A_TRUNCATION_AND_NOT_THE_SPACE" in scope
    declaration = scope["THIS_IS_A_TRUNCATION_AND_NOT_THE_SPACE"]
    assert "LEADERS only" in declaration
    assert "NOT the 64-feature dictionary" in declaration
    assert "Reading it as the space is the defect" in declaration
    assert scope["selection"] == "TOP_K_PER_CELL_UNION_OVER_THE_THREE_LIMBS"
    assert scope["top_k"] == d.PER_CELL_FULL_SPACE_TOP_K == 25
    assert "argsort(-values" in scope["selection_rule"]
    assert scope["d_sae"] == 64
    assert scope["limbs_ranked"] == ["G-A", "G-B", "G-C"]
    assert scope["splits_retained"] == ["positives", "near_miss", "unrelated"]
    # The pooled order is recorded so the separation AUROC is exactly
    # reconstructable rather than guessable.
    assert scope["pooled_negative_order_for_separation_auroc"] == ["unrelated", "near_miss"]
    assert "positives alone would answer nothing" in scope["why_all_three_splits"].lower()
    # And the dropped population is COUNTABLE per cell.
    for cell in CELLS:
        block = record["cells"][cell]
        assert block["features_NOT_retained"] == (
            block["features_scored_in_this_cell"] - block["features_retained"]
        )
    # The scope survives JSON, which is where a reader will meet it.
    assert "TRUNCATION" in json.dumps(record)


def test_the_selection_rule_is_derived_from_the_existing_top_k_not_a_second_ranking():
    """The coordinator's constraint, and it is the right one: two silently
    different rankings would be worse than no retention, because the per-item
    values would then describe features other than the ones the ceiling was
    computed from.

    Asserted three ways -- one function, one call site in each consumer, and
    identical output."""
    source = DISCOVERY_PATH.read_text(encoding="utf-8")
    # Exactly ONE per-cell descending ranking exists in the file.
    assert source.count('np.argsort(-np.asarray(values, dtype=np.float64), kind="stable")') == 1
    assert "def per_cell_leader_indices" in source
    # `summarise_per_cell_auroc` uses it rather than its own copy.
    assert "order = per_cell_leader_indices(values, top_k=top_k)" in source
    assert 'order = np.argsort(-values, kind="stable")[:top_k]' not in source
    # And the ranking really is the summaries' ranking.
    rng = np.random.default_rng(5)
    values = rng.random(64)
    summary = d.summarise_per_cell_auroc({"en/f1": values}, auroc_min=0.5, quantity="separation_auroc")
    from_summary = [f["feature_index"] for f in summary["cells"]["en/f1"]["top_features"]]
    from_helper = [int(i) for i in d.per_cell_leader_indices(values, top_k=25)]
    assert from_summary == from_helper


def test_the_argmax_of_every_limb_is_retained_because_the_ranking_is_a_descending_sort():
    """Not assumed -- measured over many random matrices, and separately for
    each limb, because the three limbs have three different argmaxes and that
    is exactly why the retained set is a UNION."""
    for seed in range(12):
        block, _p, _n, _u, limbs = _block(d_sae=200, seed=seed)
        retained = set(block["retained_feature_indices"])
        for quantity, label in (
            ("separation_auroc", "G-A"), ("fire_rate", "G-B"), ("near_miss_auroc", "G-C")
        ):
            assert int(np.argmax(limbs[quantity])) in retained
            assert block["argmax_retained_by_limb"][label] is True
        # order[0] IS the argmax, which is the property the guarantee rests on.
        assert block["retained_is_the_union_of_these_rankings"]["G-A"][0] == int(
            np.argmax(limbs["separation_auroc"])
        )


def test_retaining_only_one_limbs_top_k_would_have_lost_another_limbs_argmax():
    """The justification for the UNION, measured rather than asserted. If one
    limb's top-25 always contained the others' argmaxes the union would be
    unnecessary; it does not, so retaining only G-A's leaders would leave a
    G-C or G-B ceiling unresamplable."""
    missed = 0
    for seed in range(12):
        _blk, _p, _n, _u, limbs = _block(d_sae=2000, seed=100 + seed)
        g_a_only = set(int(i) for i in d.per_cell_leader_indices(limbs["separation_auroc"], top_k=25))
        for quantity in ("fire_rate", "near_miss_auroc"):
            if int(np.argmax(limbs[quantity])) not in g_a_only:
                missed += 1
    assert missed > 0, (
        "on this sample one limb's top-k always contained the others' argmaxes, so this test cannot "
        "exercise the reason the union exists"
    )


# ---------------------------------------------------------------------------
# THE RETENTION IS USABLE -- THE STRONGEST CHECK
# ---------------------------------------------------------------------------


def test_the_retained_per_item_values_reproduce_the_recorded_auroc_exactly():
    """THE CHECK THAT MATTERS MOST. Presence is not usability: the record
    could carry forty numbers per feature and still be useless if they were
    the wrong probes, the wrong feature, or in the wrong order. So the AUROC
    is RECOMPUTED from the retained per-item values, through the production
    primitive, and required to match the per-cell statistic bit for bit.

    That is what makes a resample possible, and it also confirms the recorded
    pooled negative order is the real one."""
    block, positives, near_miss, unrelated, limbs = _block(d_sae=64, seed=7)
    for feature in block["retained_feature_indices"]:
        stored = block["per_item_scores_by_feature"][str(feature)]
        pos = np.asarray(stored["positives"], dtype=np.float64)
        nm = np.asarray(stored["near_miss"], dtype=np.float64)
        un = np.asarray(stored["unrelated"], dtype=np.float64)
        # The stored values ARE this feature's column.
        assert np.array_equal(pos, positives[:, feature])
        assert np.array_equal(nm, near_miss[:, feature])
        assert np.array_equal(un, unrelated[:, feature])
        # And they reproduce both AUROC limbs through the production primitive,
        # using the pooled order the record declares.
        pooled = np.concatenate([un, nm])
        assert d.rank_auroc_matrix(pos, pooled)[0] == pytest.approx(
            limbs["separation_auroc"][feature], abs=0.0, rel=0.0
        )
        assert d.rank_auroc_matrix(pos, nm)[0] == pytest.approx(
            limbs["near_miss_auroc"][feature], abs=0.0, rel=0.0
        )


def test_a_resample_of_the_positives_is_now_actually_computable():
    """The question the retention exists for, executed end to end: drop one
    positive (leave-one-out) and see whether the recomputed AUROC crosses a
    bar. NO BAR IS SET HERE -- the bar is passed in by the caller and this
    test asserts only that the computation is POSSIBLE and that it moves,
    which is precisely what was unanswerable before."""
    block, _p, _n, _u, limbs = _block(d_sae=64, seed=11)
    feature = block["argmax_feature_by_limb"]["G-A"]
    stored = block["per_item_scores_by_feature"][str(feature)]
    pos = np.asarray(stored["positives"], dtype=np.float64)
    pooled = np.concatenate([
        np.asarray(stored["unrelated"], dtype=np.float64),
        np.asarray(stored["near_miss"], dtype=np.float64),
    ])
    full = d.rank_auroc_matrix(pos, pooled)[0]
    assert full == pytest.approx(limbs["separation_auroc"][feature])
    leave_one_out = [
        float(d.rank_auroc_matrix(np.delete(pos, i), pooled)[0]) for i in range(len(pos))
    ]
    assert len(leave_one_out) == 10
    # The whole point: the statistic MOVES under a resample, by an amount that
    # is now measurable rather than argued.
    assert max(leave_one_out) != min(leave_one_out)
    spread = max(leave_one_out) - min(leave_one_out)
    # One lattice step for a 10x30 rank AUROC is 1/600. A cell one step above
    # its bar is a cell whose clearance a single probe can decide, and this
    # asserts the retained data can see movement at that scale.
    assert spread > 1.0 / 600.0


# ---------------------------------------------------------------------------
# THE PRODUCTION SEAM, AND THAT THE CHANGE IS ADDITIVE
# ---------------------------------------------------------------------------


def test_the_production_scan_retains_per_item_scores_with_the_v2_counts():
    """End to end through `score_full_feature_space` on the fake backend this
    suite uses everywhere. The split sizes also independently confirm the
    counts the lattice denominators are derived from: 10 positives, 15
    near-miss, 15 unrelated -> 2*10*30 = 600 for G-A, 2*10*15 = 300 for G-C,
    10 for G-B."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    record = scan.per_item_positive_scores
    assert record is not None
    assert set(record["cells"]) == set(scan.cell_keys)
    lattice = scan.admissibility["lattice_denominator_by_cell_and_gate"]
    for cell in scan.cell_keys:
        block = record["cells"][cell]
        sizes = block["split_sizes"]
        assert sizes["positives"] == 10
        assert sizes["near_miss"] == 15
        assert sizes["unrelated"] == 15
        # The retention's own counts reproduce the derived lattice denominators.
        assert lattice[cell]["G-B"] == sizes["positives"]
        assert lattice[cell]["G-C"] == 2 * sizes["positives"] * sizes["near_miss"]
        assert lattice[cell]["G-A"] == 2 * sizes["positives"] * (
            sizes["near_miss"] + sizes["unrelated"]
        )
        assert all(block["argmax_retained_by_limb"].values())
    # It survives JSON, which is how it will reach a grid.
    assert json.loads(json.dumps(record))["scope"]["top_k"] == 25


def test_the_retention_is_additive_and_removes_or_reshapes_nothing():
    """CORRECT-NEVER-REMOVE. Every field the previous scan emitted must still
    be present with the same shape, or a consumer written against `ec74390`
    breaks."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    for field in (
        "min_separation_auroc", "min_fire_rate", "min_near_miss_auroc", "cells_scored",
        "admissibility", "admissibility_matrix", "cell_keys", "per_cell_values",
        "per_cell_separation_auroc", "per_cell_fire_rate", "per_cell_near_miss_auroc",
    ):
        assert getattr(scan, field) is not None
    # The admissibility record keeps every key the previous commit emitted,
    # including the ones added for the lattice comparison and the band.
    for key in (
        "cell_order", "d_sae", "thresholds_used", "screen_epsilon", "screen_derived",
        "admissible_feature_indices_by_cell", "admissible_count_by_cell",
        "per_gate_pass_count_by_cell", "features_within_screen_epsilon_band",
        "features_within_screen_epsilon_band_indices", "gate_comparison_basis",
        "lattice_denominator_by_cell_and_gate", "coverage_pattern_census",
    ):
        assert key in scan.admissibility, key
    # The per-cell summaries still carry their own top-k leaders unchanged.
    leaders = scan.per_cell_separation_auroc["cells"][scan.cell_keys[0]]["top_features"]
    assert leaders and "feature_index" in leaders[0]
    # The withdrawn exact-A key is still absent.
    assert "admissible_feature_indices_by_cell_EXACT" not in scan.admissibility


def test_the_retained_size_is_measured_and_small():
    """The measured figure, not an estimate. At the real dictionary size the
    union of three top-25 sets is 75 features per cell, so 75 x 6 x 40 = 18000
    scalars per concept and 288000 across 16 -- against ~2.5 GB raw for full
    space, which is why the scoping exists."""
    rng = np.random.default_rng(0)
    d_sae = 81920
    block = d.per_item_retention_for_cell(
        positives=rng.random((10, d_sae)),
        near_miss=rng.random((15, d_sae)),
        unrelated=rng.random((15, d_sae)),
        limb_values={
            "separation_auroc": rng.random(d_sae),
            "fire_rate": rng.random(d_sae),
            "near_miss_auroc": rng.random(d_sae),
        },
    )
    assert block["features_retained"] <= 3 * d.PER_CELL_FULL_SPACE_TOP_K
    assert block["features_NOT_retained"] == d_sae - block["features_retained"]
    record = d.build_per_item_retention_record(
        {cell: block for cell in CELLS}, d_sae=d_sae
    )
    megabytes = len(json.dumps(record)) / 1024 / 1024
    # One concept. Sixteen concepts is ~16x this and still single-digit MiB.
    assert megabytes < 1.0, megabytes
    scalars = sum(
        len(v)
        for cell in CELLS
        for splits in record["cells"][cell]["per_item_scores_by_feature"].values()
        for v in splits.values()
    )
    assert scalars == 6 * block["features_retained"] * 40
