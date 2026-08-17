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
import dataclasses
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


# ---------------------------------------------------------------------------
# THE SERIALIZED ARTIFACT -- THE ASSERTION WHOSE ABSENCE LET THE RETENTION BE
# COMPUTED, VALIDATED AND THEN DISCARDED
#
# Job 418185 ran with the retention implemented and `per_item_scores_by_feature`
# occurs ZERO times at byte level in all four grids. Every test in this file
# passed, because they exercised `per_item_retention_for_cell`,
# `build_per_item_retention_record` and `verify_per_item_retention` DIRECTLY.
# Nothing asserted that the object actually written to disk carried the record.
# That is a check that passes while unable to exercise what it claims to cover
# -- the defect class this sprint is about -- and it survived a review in which
# the retention was discussed at length.
#
# So these tests assert on the WRITTEN JSON BYTES, through the real write path,
# and never on a builder's return value.
# ---------------------------------------------------------------------------


def test_the_written_grid_json_carries_the_per_item_retention(tmp_path):
    """THE ASSERTION THAT WOULD HAVE CAUGHT IT. Serialize a verdict through
    `write_grid_result` -- the real path that produced job 418185's four grids
    -- and assert on the resulting bytes.

    Byte-level first, deliberately: the coordinator found the defect by raw
    grep rather than by a structural walk, and a structural walk over a dict
    that has already been re-parsed can be satisfied by an object that was
    never written. The byte assertion cannot."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    raw = Path(path).read_bytes()

    # 1. BYTE LEVEL, exactly as the defect was found.
    assert b"per_item_scores_by_feature" in raw
    assert b"THIS_IS_A_TRUNCATION_AND_NOT_THE_SPACE" in raw
    assert b"per_item_positive_scores" in raw
    assert b"pooled_negative_order_for_separation_auroc" in raw

    # 2. AND POPULATED, because a present-but-empty field is the same failure
    #    wearing a key. `features_NOT_retained` is what makes the truncation's
    #    own size visible, so it has to survive too.
    written = json.loads(raw.decode("utf-8"))
    record = written["verdicts"][0]["per_item_positive_scores"]
    assert record is not None
    assert record["cells"], "the retention reached the file with no cells in it"
    for cell, block in record["cells"].items():
        assert block["per_item_scores_by_feature"], f"cell {cell} carries no per-item scores"
        assert block["features_retained"] > 0
        assert "features_NOT_retained" in block
        assert all(block["argmax_retained_by_limb"].values())
        for splits in block["per_item_scores_by_feature"].values():
            assert set(splits) == {"positives", "near_miss", "unrelated"}
            assert len(splits["positives"]) == 10
            assert len(splits["near_miss"]) == 15
            assert len(splits["unrelated"]) == 15

    # 3. The scope block survives serialization intact -- it is the part a
    #    future reader needs in order not to mistake this for the space.
    scope = record["scope"]
    assert scope["top_k"] == d.PER_CELL_FULL_SPACE_TOP_K
    assert scope["selection"] == "TOP_K_PER_CELL_UNION_OVER_THE_THREE_LIMBS"
    assert scope["splits_retained"] == ["positives", "near_miss", "unrelated"]

    # 4. And the WRITTEN record still passes its own verifier, so the bytes on
    #    disk are self-consistent rather than merely present.
    d.verify_per_item_retention(record)


def test_the_written_retention_survives_the_read_path_too(tmp_path):
    """A record that serializes and cannot be read back is not retained. The
    group lane reads `grid.json` through `read_grid_result`, so the round trip
    is the property that matters, not the write alone."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    restored = d.read_grid_result(path)
    verdicts = restored["verdicts"] if isinstance(restored, dict) else restored
    first = verdicts[0]
    record = first["per_item_positive_scores"] if isinstance(first, dict) else (
        first.per_item_positive_scores
    )
    assert record is not None
    d.verify_per_item_retention(record)
    # The values are numbers after a round trip, not strings.
    block = next(iter(record["cells"].values()))
    splits = next(iter(block["per_item_scores_by_feature"].values()))
    assert all(isinstance(v, float) for v in splits["positives"])


def test_deleting_the_copy_line_makes_the_end_to_end_assertion_fail(tmp_path):
    """MADE TO FAIL, per RULING_15's general clause: a check that cannot fail
    and a check that cannot fire are the same defect wearing different clothes.

    This reproduces the exact defect -- a scan that computed and validated the
    retention, and a verdict that did not copy it -- by building the verdict
    with the field left at its default, and shows the byte-level assertion
    catching it. The `None` default is what let this pass silently, so the
    reproduction uses that default rather than a tampered value."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    # The producer DID compute it and it DID validate -- that was never the bug.
    assert verdict.per_item_positive_scores is not None
    d.verify_per_item_retention(verdict.per_item_positive_scores)

    # Now the recorder as it stood at 5b1da92: every other field copied, this
    # one left at its default.
    unrecorded = dataclasses.replace(verdict, per_item_positive_scores=None)
    path = d.write_grid_result(tmp_path / "unrecorded", "gemma-3-12b-it", [unrecorded])
    raw = Path(path).read_bytes()

    # THE ASSERTION FIRES. This is the line whose absence cost a scan.
    assert b"per_item_scores_by_feature" not in raw
    assert b"THIS_IS_A_TRUNCATION_AND_NOT_THE_SPACE" not in raw
    with pytest.raises(AssertionError):
        assert b"per_item_scores_by_feature" in raw, "the end-to-end assertion fires as designed"

    # And a `None` retention is DISTINGUISHABLE from a retention with no
    # cells, which is why the field defaults to None rather than to {}.
    written = json.loads(raw.decode("utf-8"))
    assert written["verdicts"][0]["per_item_positive_scores"] is None
    with pytest.raises(d.PerItemRetentionScopeMismatch):
        d.verify_per_item_retention({"scope": {"top_k": 25,
                                               "splits_retained": ["positives", "near_miss",
                                                                   "unrelated"]},
                                     "cells": {}})


# ---------------------------------------------------------------------------
# THE SIBLING SWEEP -- ASSUME THERE IS A THIRD
#
# `ConceptPairingVerdict` copies five of `FullSpaceScan`'s sixteen fields. This
# is the SECOND retention to land in the producer and not the recorder
# (`surviving_feature_indices` was the first, for a scalar that dropped a
# survivor). So rather than eyeball it once, every scan field gets a RECORDED
# DECISION here, and the test fails the moment a new scan field appears without
# one. A future field cannot be forgotten in silence; it can only be forgotten
# loudly.
# ---------------------------------------------------------------------------

#: Every `FullSpaceScan` field -> where it lands on the serialized verdict, or
#: `None` plus the reason it deliberately does not. Exhaustiveness is asserted
#: against the dataclass, so this cannot drift out of date quietly.
SCAN_FIELD_DISPOSITION: dict[str, tuple[str | None, str]] = {
    "concept_id": (
        "concept_id",
        "SERIALIZED. Set from the same argument rather than copied off the scan.",
    ),
    "locales": (
        None,
        "NOT SERIALIZED, RECOVERABLE. admissibility_matrix['cell_order'] carries every "
        "locale/family cell key, so the locale set is derivable from the written record with no "
        "loss. Nothing downstream reads it off the verdict.",
    ),
    "families_by_locale": (
        None,
        "NOT SERIALIZED, RECOVERABLE. Same ground as `locales`: cell_order is 'locale/family' per "
        "cell, so the mapping is reconstructable exactly.",
    ),
    "min_separation_auroc": (
        None,
        "NOT SERIALIZED, DELIBERATE AND SUPERSEDED. A [d_sae] float array whose per-cell detail is "
        "the thing RULING_8 found collapsed; the per-cell summaries and the admissibility record "
        "supersede it, and RULING_13 clause 4/5 make min a QUALIFIER that may not be consumed as a "
        "ranked pool. Serializing it would re-offer the prohibited object.",
    ),
    "min_fire_rate": (None, "NOT SERIALIZED. Same ground as min_separation_auroc."),
    "min_near_miss_auroc": (None, "NOT SERIALIZED. Same ground as min_separation_auroc."),
    "cells_scored": (
        None,
        "NOT SERIALIZED, RECOVERABLE. Equals len(admissibility_matrix['cell_order']), asserted "
        "below so the recoverability is measured rather than claimed.",
    ),
    "admissibility_matrix": (
        None,
        "NOT SERIALIZED AS AN ARRAY, BY DESIGN AND DOCUMENTED. The in-memory boolean [d_sae, "
        "n_cells] array is represented losslessly by the `admissibility` RECORD, which IS "
        "serialized as verdict.admissibility_matrix. The support lists are exactly the array's "
        "information in the sparse regime and are untruncated at any k.",
    ),
    "cell_keys": (
        None,
        "NOT SERIALIZED UNDER THIS NAME, PRESENT AS DATA. admissibility_matrix['cell_order'] is the "
        "same tuple in the same order; asserted equal below.",
    ),
    "per_cell_values": (
        None,
        "NOT SERIALIZED, A STATED TRUNCATION. The full per-cell float vectors are ~3.9 MB per "
        "concept in memory and ~10 MB as JSON per quantity. The per-cell summaries keep each "
        "cell's top_k and SAY SO in their own `truncation` field. This is the one remaining "
        "computed-then-discarded quantity and it is a KNOWN, DECLARED loss rather than a silent "
        "one -- and it is exactly why the per-item retention had to be taken separately.",
    ),
    "shadow_fire_rate_summary": ("shadow_gate_b_summary", "SERIALIZED."),
    "per_cell_separation_auroc": ("per_cell_full_space_auroc", "SERIALIZED."),
    "per_cell_fire_rate": ("per_cell_full_space_fire_rate", "SERIALIZED."),
    "per_cell_near_miss_auroc": ("per_cell_full_space_near_miss_auroc", "SERIALIZED."),
    "admissibility": ("admissibility_matrix", "SERIALIZED (under a different name)."),
    "per_item_positive_scores": (
        "per_item_positive_scores",
        "SERIALIZED -- and it was NOT, at 5b1da92, which is the defect this sweep exists because "
        "of. Job 418185 wrote four grids in which per_item_scores_by_feature occurs zero times at "
        "byte level.",
    ),
}


def test_every_scan_field_has_a_recorded_serialization_decision():
    """THE TRIPWIRE FOR THE THIRD INSTANCE. If a field is added to
    `FullSpaceScan` and nobody decides whether it reaches the written record,
    THIS TEST FAILS. That is the structural repair; the copy line was only the
    symptom.

    Two directions, so it cannot pass vacuously: a scan field with no decision
    fails, and a decision naming a field that no longer exists fails."""
    actual = set(d.FullSpaceScan.__dataclass_fields__)
    declared = set(SCAN_FIELD_DISPOSITION)
    assert declared - actual == set(), (
        f"SCAN_FIELD_DISPOSITION names fields that are no longer on FullSpaceScan: "
        f"{sorted(declared - actual)}"
    )
    assert actual - declared == set(), (
        f"FullSpaceScan has fields with NO recorded serialization decision: "
        f"{sorted(actual - declared)}. This is the second time a computed value never reached the "
        f"written record; decide explicitly and add it to SCAN_FIELD_DISPOSITION."
    )
    # Every declared target really is a verdict field, and every reason is real.
    verdict_fields = set(d.ConceptPairingVerdict.__dataclass_fields__)
    for name, (target, reason) in SCAN_FIELD_DISPOSITION.items():
        assert reason.strip(), name
        if target is not None:
            assert target in verdict_fields, (name, target)


def test_the_fields_declared_serialized_really_reach_the_written_json(tmp_path):
    """The declaration above is checked against the BYTES, not against the
    source. A disposition table that agreed with a comment and disagreed with
    the artifact would be the original defect with extra steps."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    written = json.loads(Path(path).read_text(encoding="utf-8"))["verdicts"][0]
    for name, (target, _reason) in SCAN_FIELD_DISPOSITION.items():
        if target is None or name == "concept_id":
            continue
        assert target in written, f"{name} is declared serialized as {target!r} and is not in the JSON"
        # THE COPY IS WHAT IS CHECKED, not the value. Comparing against the
        # scan's own value catches a copy that dropped something, and does not
        # spuriously fail when the scan legitimately produced None -- which is
        # the case for `shadow_fire_rate_summary` whenever no shadow reference
        # corpus is supplied, as on this fixture. Asserting non-null outright
        # would have made this test pass or fail on the FIXTURE rather than on
        # the wiring, which is the mistake one layer down from the original.
        produced = getattr(scan, name)
        if produced is None:
            assert written[target] is None, (
                f"{name} was None on the scan and non-null in the JSON, so the two disagree"
            )
        else:
            assert written[target] is not None, (
                f"{name} was produced by the scan and reached the JSON as null -- the copy at the "
                f"verdict construction site dropped it. THIS IS THE DEFECT SHAPE."
            )


def test_the_fields_declared_recoverable_really_are_recoverable_from_the_written_json(tmp_path):
    """Four fields are excused from serialization on the ground that they are
    RECOVERABLE from what is written. That is a claim, so it is measured. An
    excuse that turned out to be false would be a silent loss justified by a
    comment."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    written = json.loads(Path(path).read_text(encoding="utf-8"))["verdicts"][0]
    cell_order = written["admissibility_matrix"]["cell_order"]
    # cell_keys
    assert tuple(cell_order) == tuple(scan.cell_keys)
    # cells_scored
    assert len(cell_order) == scan.cells_scored
    # locales and families_by_locale
    recovered_locales = sorted({key.split("/")[0] for key in cell_order})
    assert recovered_locales == sorted(scan.locales)
    recovered_families: dict[str, list[str]] = {}
    for key in cell_order:
        locale, family = key.split("/", 1)
        recovered_families.setdefault(locale, []).append(family)
    assert {k: sorted(v) for k, v in recovered_families.items()} == {
        k: sorted(v) for k, v in scan.families_by_locale.items()
    }


def test_the_per_cell_float_vectors_are_the_one_declared_loss_and_they_say_so(tmp_path):
    """`per_cell_values` is the only remaining computed-then-discarded
    quantity, and the difference between it and the per-item defect is that
    this one DECLARES ITSELF in the written record. Asserted on the bytes, so
    "it is a stated truncation" is a property of the artifact rather than of a
    docstring."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    written = json.loads(Path(path).read_text(encoding="utf-8"))["verdicts"][0]
    for key in ("per_cell_full_space_auroc", "per_cell_full_space_fire_rate",
                "per_cell_full_space_near_miss_auroc"):
        summary = written[key]
        assert "truncation" in summary, key
        assert "is NOT retained" in summary["truncation"]
        assert summary["top_k_retained_per_cell"] == d.PER_CELL_FULL_SPACE_TOP_K
        # And the boolean that is NOT subject to the top_k says so in the same
        # breath, so a reader cannot generalise the truncation to A[f, c].
        assert "ADMISSIBILITY BOOLEAN is retained for every feature" in summary["truncation"]


# ---------------------------------------------------------------------------
# RULING_15's GENERAL CLAUSE, APPLIED RETROACTIVELY
#
# "EVERY predicate this ruling introduces or amends ships TWO tests over inputs
# differing ONLY in the quantity it claims to read: one in which it FIRES and
# one in which it does NOT. A check that cannot fail and a check that cannot
# fire are the same defect wearing different clothes."
#
# The retention work predates that clause. Applying it retroactively is what
# found nothing new for three of these predicates and everything for the
# fourth -- the end-to-end one, which had no fires-direction test at all.
# ---------------------------------------------------------------------------


def test_predicate_pairs_fire_and_do_not_fire_on_inputs_differing_in_one_quantity():
    """Each pair below differs ONLY in the quantity the predicate claims to
    read, so a pass proves the predicate reads THAT and not something
    correlated with it."""
    # 1. verify_per_item_retention -- ARGMAX MEMBERSHIP. Same record, one index
    #    removed from the retained set.
    record = _record()
    d.verify_per_item_retention(record)                                    # DOES NOT FIRE
    tampered = copy.deepcopy(record)
    cell = tampered["cells"]["en/f1"]
    argmax = cell["argmax_feature_by_limb"]["G-A"]
    cell["retained_feature_indices"] = [i for i in cell["retained_feature_indices"] if i != argmax]
    cell["per_item_scores_by_feature"].pop(str(argmax))
    cell["features_retained"] -= 1
    cell["features_NOT_retained"] += 1
    with pytest.raises(d.PerItemRetentionScopeMismatch):                   # FIRES
        d.verify_per_item_retention(tampered)

    # 2. lattice_gate -- THE DENOMINATOR, and nothing else changes.
    values = np.array([540 / 600, 539 / 600])
    d.lattice_gate(values, threshold=0.90, denominator=600)                # DOES NOT FIRE
    with pytest.raises(d.LatticeDenominatorWrong):                        # FIRES
        d.lattice_gate(values, threshold=0.90, denominator=7)

    # 3. `_resampling_reach` is the fourth predicate in this family, and it
    #    lives in group_selection.py rather than here; its fires /
    #    does-not-fire pair is
    #    `test_a_deficit_beyond_resampling_reach_is_not_given_the_softer_verdict`
    #    in tests/test_group_selection.py, which asserts True at 6 steps on 10
    #    positives and False at 300. Named rather than duplicated, so the pair
    #    is locatable without this file reaching into another module.

    # 4. per_cell_leader_indices -- THE VALUES. The argmax moves with them and
    #    with nothing else.
    ascending = np.arange(50, dtype=np.float64)
    assert int(d.per_cell_leader_indices(ascending, top_k=25)[0]) == 49
    assert int(d.per_cell_leader_indices(-ascending, top_k=25)[0]) == 0

    # 5. per_item_retention_for_cell -- TOP_K, which is the only input that
    #    decides whether the argmax can be present at all.
    kwargs = dict(
        positives=np.random.default_rng(4).random((10, 8)),
        near_miss=np.random.default_rng(5).random((15, 8)),
        unrelated=np.random.default_rng(6).random((15, 8)),
        limb_values={
            "separation_auroc": np.arange(8, dtype=np.float64),
            "fire_rate": np.arange(8, dtype=np.float64),
            "near_miss_auroc": np.arange(8, dtype=np.float64),
        },
    )
    ok = d.per_item_retention_for_cell(top_k=1, **kwargs)                  # DOES NOT FIRE
    assert ok["features_retained"] == 1
    assert ok["argmax_retained_by_limb"]["G-A"] is True
    with pytest.raises(d.PerItemRetentionScopeMismatch):                   # FIRES
        d.per_item_retention_for_cell(top_k=0, **kwargs)


def test_the_end_to_end_predicate_has_both_directions_which_is_what_it_lacked(tmp_path):
    """The pair that did not exist before, stated as its own test because its
    absence is the whole finding: the serialization predicate had a
    does-not-fire direction (every earlier test) and NO fires direction, so it
    could not distinguish a recorded retention from an unrecorded one.

    Both directions now, over verdicts differing ONLY in whether the copy
    happened."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")

    recorded = Path(d.write_grid_result(tmp_path / "recorded", "gemma-3-12b-it", [verdict]))
    unrecorded = Path(d.write_grid_result(
        tmp_path / "unrecorded", "gemma-3-12b-it",
        [dataclasses.replace(verdict, per_item_positive_scores=None)],
    ))

    assert b"per_item_scores_by_feature" in recorded.read_bytes()          # DOES NOT FIRE
    assert b"per_item_scores_by_feature" not in unrecorded.read_bytes()    # FIRES
    # The two artifacts differ in nothing else that matters: same concept, same
    # gates, same admissibility support.
    left = json.loads(recorded.read_text(encoding="utf-8"))["verdicts"][0]
    right = json.loads(unrecorded.read_text(encoding="utf-8"))["verdicts"][0]
    assert left["admissibility_matrix"] == right["admissibility_matrix"]
    assert left["per_cell_full_space_auroc"] == right["per_cell_full_space_auroc"]
    assert left["per_item_positive_scores"] is not None
    assert right["per_item_positive_scores"] is None
