"""Controls for per-cell SHADOW G-B retention.

Coordinator ruling, 2026-08-16, on the collapse this lane reported: ADD
per-cell retention, do NOT remove or alter the pooled histogram/quantile
fields. Additive means no current consumer can break, which is what makes
it safe to land without waiting on the lane that owns the consumer.

CONTROLS FIRST, and there are two distinct things to control:

1. THE ADDITION IS REALLY ADDITIVE. Every pre-existing pooled field must be
   BYTE-IDENTICAL with and without the new record. A test that only checked
   the new fields exist could not tell an addition from a rewrite.
2. THE ADDITION IS NOT VACUOUS. A per-cell record that merely repeated the
   pooled numbers would satisfy (1) and be worthless. So the two
   populations the pooled form is BLIND to are constructed deliberately and
   the test requires the per-cell record to expose them AND requires the
   pooled record to be unable to.

Both use synthetic vectors rather than a model: the quantities under test
are the retention and the arithmetic, and no forward pass enters either.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402

CELLS = ("en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3")
FIRE_RATE_MIN = 0.70


def _synthetic_cells(d_sae: int = 200, seed: int = 20260816):
    """Six cells with a DELIBERATE per-cell asymmetry, plus the two
    pathological populations the pooled form cannot see.

    en/f1 is made anti-specific-and-firing on purpose: separation below 0.5
    (fires harder on controls than on the concept) while the within-cell
    fire rate clears 0.70. Pooled over six cells that population is diluted
    into a distribution that looks unremarkable."""
    rng = np.random.default_rng(seed)
    corpus_max = rng.random(d_sae) * 4.0
    corpus_max[: d_sae // 4] = 0.0  # a quarter of features below background resolution

    per_cell = {}
    for index, cell in enumerate(CELLS):
        within = rng.random(d_sae)
        shadow = rng.random(d_sae)
        separation = rng.random(d_sae) * 0.4 + 0.55  # mostly specific
        positive_max = rng.random(d_sae) * 3.0
        if cell == "en/f1":
            separation[:40] = 0.2       # anti-specific
            within[:40] = 0.95          # and passing within-cell G-B anyway
        if index >= 3:
            within = within * 0.3       # fr cells fire much less
        per_cell[cell] = {
            "within": within, "shadow": shadow,
            "separation": separation, "positive_max": positive_max,
        }
    return per_cell, corpus_max, d_sae


def _pooled_kwargs(per_cell, corpus_max, d_sae):
    within_all = np.concatenate([v["within"] for v in per_cell.values()])
    shadow_all = np.concatenate([v["shadow"] for v in per_cell.values()])
    within_counts = np.zeros(d.SHADOW_HISTOGRAM_BINS, dtype=np.int64)
    shadow_counts = np.zeros(d.SHADOW_HISTOGRAM_BINS, dtype=np.int64)
    for vectors in per_cell.values():
        within_counts += d.shadow_histogram_bins(vectors["within"])
        shadow_counts += d.shadow_histogram_bins(vectors["shadow"])
    return {
        "within_cell_counts": within_counts, "corpus_max_counts": shadow_counts,
        "within_cell_values": within_all, "corpus_max_values": shadow_all,
        "degenerate_reference_features": int((corpus_max <= 0).sum()),
        "dead_cell_pairs": 0, "cells": len(per_cell), "d_sae": d_sae,
        "fire_rate_min": FIRE_RATE_MIN, "floor_fraction": 0.20,
    }


# ---------------------------------------------------------------------------
# CONTROL 1: the addition is additive
# ---------------------------------------------------------------------------


def test_every_pooled_field_is_byte_identical_with_and_without_the_new_record():
    """CORRECT-NEVER-REMOVE, checked rather than asserted. If any pooled
    figure moved, this is a rewrite wearing an addition's label."""
    per_cell, corpus_max, d_sae = _synthetic_cells()
    kwargs = _pooled_kwargs(per_cell, corpus_max, d_sae)

    before = d.summarise_shadow_distribution(**kwargs)
    after = d.summarise_shadow_distribution(
        **kwargs,
        per_cell=d.summarise_shadow_per_cell(
            per_cell, fire_rate_min=FIRE_RATE_MIN, corpus_max_by_feature=corpus_max, d_sae=d_sae
        ),
    )

    added = set(after) - set(before)
    assert added == set(), "the new keys must exist in BOTH shapes, defaulting to None"
    for key in before:
        if key in ("per_cell", "per_cell_status"):
            continue
        assert json.dumps(before[key], sort_keys=True) == json.dumps(after[key], sort_keys=True), key

    assert before["per_cell"] is None
    assert before["per_cell_status"] == "not computed"
    assert after["per_cell_status"] == f"retained for {len(CELLS)} cells"


def test_the_pooled_form_carries_its_provenance_rather_than_being_deleted():
    per_cell, corpus_max, d_sae = _synthetic_cells()
    summary = d.summarise_shadow_distribution(**_pooled_kwargs(per_cell, corpus_max, d_sae))
    assert summary["fire_rate_within_cell"]["histogram"]
    assert summary["fire_rate_corpus_max"]["quantiles"]
    provenance = summary["pooled_across_cells_provenance"]
    assert "POOLED OVER ALL SIX" in provenance
    assert "RETAINED" in provenance
    assert "RULING_8" in provenance


# ---------------------------------------------------------------------------
# CONTROL 2: the addition is not vacuous
# ---------------------------------------------------------------------------


def test_the_per_cell_record_exposes_what_the_pooled_record_cannot():
    """The load-bearing control. A per-cell block that merely echoed the
    pooled numbers would pass CONTROL 1 and be worthless."""
    per_cell, corpus_max, d_sae = _synthetic_cells()
    pooled = d.summarise_shadow_distribution(**_pooled_kwargs(per_cell, corpus_max, d_sae))
    cells = d.summarise_shadow_per_cell(
        per_cell, fire_rate_min=FIRE_RATE_MIN, corpus_max_by_feature=corpus_max, d_sae=d_sae
    )

    # ANTI-SPECIFIC AND STILL PASSING G-B: constructed into en/f1 only.
    passing = {c: cells[c]["anti_specific_and_passing_within_cell_gate_b"] for c in CELLS}
    assert passing["en/f1"] == 40
    assert all(passing[c] == 0 for c in CELLS if c != "en/f1")
    # The pooled record has no field that can express this AT ALL.
    assert not any("anti_specific" in key for key in pooled)

    # PER-CELL FIRE-RATE DISTRIBUTIONS GENUINELY DIFFER, so a single pooled
    # threshold is not the same statement as six per-cell ones.
    medians = {c: cells[c]["fire_rate_within_cell"]["quantiles"]["median"] for c in CELLS}
    assert max(medians.values()) - min(medians.values()) > 0.2
    pooled_median = pooled["fire_rate_within_cell"]["quantiles"]["median"]
    assert any(abs(m - pooled_median) > 0.1 for m in medians.values())

    # THE BACKGROUND-RESOLUTION POPULATION is counted and labelled as a
    # resolution limit rather than as specificity.
    for cell in CELLS:
        assert cells[cell]["degenerate_reference_features"] == d_sae // 4
        assert "BELOW THE RESOLUTION" in cells[cell]["degenerate_reference_note"]
        assert "never evidence of perfect specificity" in cells[cell]["degenerate_reference_note"]


def test_the_per_cell_histograms_sum_back_to_the_pooled_one():
    """The two records must describe the SAME underlying population -- if
    they did not, one of them would be wrong rather than coarser."""
    per_cell, corpus_max, d_sae = _synthetic_cells()
    pooled = d.summarise_shadow_distribution(**_pooled_kwargs(per_cell, corpus_max, d_sae))
    cells = d.summarise_shadow_per_cell(
        per_cell, fire_rate_min=FIRE_RATE_MIN, corpus_max_by_feature=corpus_max, d_sae=d_sae
    )
    for statistic in ("fire_rate_within_cell", "fire_rate_corpus_max"):
        summed = [
            sum(cells[c][statistic]["histogram"][i] for c in CELLS)
            for i in range(d.SHADOW_HISTOGRAM_BINS)
        ]
        assert summed == pooled[statistic]["histogram"]


def test_the_scan_populates_the_per_cell_shadow_record_end_to_end():
    """Through the production path, not the helper: the scan must carry the
    per-cell block whenever it carries the pooled one."""
    import persona_v2_preflight as pf

    artifact = d.load_frozen_persona_artifact(REPO_ROOT)
    backend, _model = pf._surrogate_backend()
    cache = d.FeatureMatrixCache()
    d.pin_shared_substrate(cache, backend, artifact)
    reference = d.shadow_corpus_max_per_feature(backend, artifact, cache=cache)
    scan = d.score_full_feature_space(
        backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0], cache=cache,
        corpus_max_by_feature=reference,
    )
    summary = scan.shadow_fire_rate_summary
    assert summary is not None
    assert set(summary["per_cell"]) == set(scan.cell_keys)
    for cell in scan.cell_keys:
        block = summary["per_cell"][cell]
        assert block["features_scored"] == backend.d_sae
        assert len(block["fire_rate_within_cell"]["histogram"]) == d.SHADOW_HISTOGRAM_BINS
        assert "anti_specific_and_passing_within_cell_gate_b" in block
    assert json.loads(json.dumps(summary)) == summary  # serialises without loss


def test_a_scan_without_a_shadow_reference_still_omits_both_forms():
    """The per-cell record must not appear out of nowhere: no shadow
    reference means no shadow summary at all, pooled or per-cell."""
    import persona_v2_preflight as pf

    artifact = d.load_frozen_persona_artifact(REPO_ROOT)
    backend, _model = pf._surrogate_backend()
    scan = d.score_full_feature_space(
        backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0]
    )
    assert scan.shadow_fire_rate_summary is None


# ---------------------------------------------------------------------------
# Grid-level aggregation
# ---------------------------------------------------------------------------


def test_per_cell_counts_sum_across_concepts_and_quantiles_deliberately_do_not():
    per_cell, corpus_max, d_sae = _synthetic_cells()
    one = d.summarise_shadow_distribution(
        **_pooled_kwargs(per_cell, corpus_max, d_sae),
        per_cell=d.summarise_shadow_per_cell(
            per_cell, fire_rate_min=FIRE_RATE_MIN, corpus_max_by_feature=corpus_max, d_sae=d_sae
        ),
    )
    verdicts = [
        d.ConceptPairingVerdict(
            concept_id=f"c{i}", pairing="gemma-3-12b-it", status="fail",
            surviving_feature_index=None, candidates_evaluated=[], error=None,
            shadow_gate_b_summary=copy.deepcopy(one),
        )
        for i in range(3)
    ]
    aggregated = d.aggregate_shadow_summaries(verdicts)
    assert set(aggregated["per_cell"]) == set(CELLS)
    for cell in CELLS:
        block = aggregated["per_cell"][cell]
        assert block["concepts_summarised"] == 3
        assert block["anti_specific_features"] == 3 * one["per_cell"][cell]["anti_specific_features"]
        assert block["fire_rate_within_cell"]["histogram"] == [
            3 * x for x in one["per_cell"][cell]["fire_rate_within_cell"]["histogram"]
        ]
        # A fabricated grid-level per-cell quantile is refused rather than averaged.
        assert "quantiles" not in block["fire_rate_within_cell"]
        assert "quantiles_not_summed" in block["fire_rate_within_cell"]


def test_aggregation_returns_none_for_per_cell_when_no_concept_carries_it():
    verdicts = [
        d.ConceptPairingVerdict(
            concept_id="c0", pairing="gemma-3-12b-it", status="fail",
            surviving_feature_index=None, candidates_evaluated=[], error=None,
            shadow_gate_b_summary=None,
        )
    ]
    assert d.aggregate_shadow_summaries(verdicts) is None


def test_the_retention_audit_now_reports_the_shadow_collapse_as_repaired():
    import persona_v2_preflight as pf

    artifact = d.load_frozen_persona_artifact(REPO_ROOT)
    backend, _model = pf._surrogate_backend()
    scan = d.score_full_feature_space(backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0])
    audit = d.audit_retention_granularity(scan)
    assert "shadow_gate_b" in audit["repaired_by_ruling_13"]
    assert "shadow_fire_rate_summary_is_pooled_across_cells" not in (
        audit["STILL_COLLAPSED_AT_RETENTION_AND_NOT_CHANGED_HERE"]
    )
    # ...and the honest residual is still named.
    assert "shadow_per_feature_values" in audit["STILL_COLLAPSED_AT_RETENTION_AND_NOT_CHANGED_HERE"]


def test_per_cell_shadow_retention_cost_is_measured(capsys):
    """The ruling requires the cost measured, not guessed."""
    per_cell, corpus_max, d_sae = _synthetic_cells(d_sae=81920)
    block = d.summarise_shadow_per_cell(
        per_cell, fire_rate_min=FIRE_RATE_MIN, corpus_max_by_feature=corpus_max, d_sae=d_sae
    )
    serialised = len(json.dumps(block))
    with capsys.disabled():
        print(
            f"\n  PER-CELL SHADOW RECORD at d_sae 81920 x 6 cells: {serialised} bytes JSON "
            f"({serialised / 1024:.1f} KiB) per concept, {14 * serialised / 1024:.1f} KiB for a "
            f"14-concept grid"
        )
    # Fixed-size per cell: histograms are 21 bins and everything else is a
    # scalar, so this cannot grow with d_sae. Bounded well under the 3.37 MB
    # worst case measured for A[f,c].
    assert serialised < 64 * 1024
