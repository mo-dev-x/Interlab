"""Tests for the D2.1 Gemma sweep analysis pipeline.

The three cases that matter are the ones where a pipeline can be quietly
wrong rather than loudly broken:
  1. a synthetic file with a HAND-COMPUTED answer  -- the metrics are right
  2. a TRUNCATED file                              -- partial data is announced, not smoothed
  3. a DUPLICATED cell                             -- detected, never averaged over
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "analyze_gemma3_sweep.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ana = _load("analyze_gemma3_sweep", SCRIPT)
sweep = ana.load_sweep_module()


# ---------------------------------------------------------------------------
# grid
# ---------------------------------------------------------------------------

def test_grid_matches_preregistered_count():
    """8 baselines + 9 features x 2 modes x 6 doses x 2 arms x 8 prompts."""
    keys = ana.build_expected_grid(sweep)
    assert len(keys) == 1736
    assert len(keys) == ana.PREREGISTERED_CELL_COUNT
    assert len(set(keys)) == len(keys), "expected grid must contain no duplicate keys"


def test_grid_arithmetic_is_explicit():
    n_base = len(sweep.DEFAULT_PROMPTS)
    n_grid = (len(sweep.FEATURES) * len(sweep.MODES) * len(sweep.DOSES)
              * 2 * len(sweep.DEFAULT_PROMPTS))
    assert n_base == 8
    assert n_grid == 1728
    assert n_base + n_grid == ana.PREREGISTERED_CELL_COUNT


def test_grid_size_mismatch_is_reported_as_defect(monkeypatch):
    """A harness that drifts from the registered design must trip a defect,
    not silently analyse a different experiment."""
    monkeypatch.setattr(sweep, "DOSES", (0.5, 1.0, 2.0), raising=True)
    result = ana.analyze([], sweep)
    assert result["grid_size_matches_preregistration"] is False
    assert any("GRID SIZE MISMATCH" in d for d in result["defects"])


# ---------------------------------------------------------------------------
# helpers to synthesise records
# ---------------------------------------------------------------------------

def _baseline(pid: str, text: str) -> dict:
    return {"feature_idx": None, "mode": "baseline", "arm": "none",
            "dose_multiple": None, "prompt_id": pid, "text": text}


def _cell(fidx: int, mode: str, arm: str, dose: float, pid: str, text: str) -> dict:
    return {"feature_idx": fidx, "mode": mode, "arm": arm, "dose_multiple": dose,
            "prompt_id": pid, "text": text, "absolute_clamp_value": dose * 100.0,
            "maxActApprox": 100.0, "seed": 1}


def _write(tmp_path: Path, records: list[dict], *, truncate_last: bool = False) -> Path:
    p = tmp_path / "records.jsonl"
    lines = [json.dumps(r) for r in records]
    body = "\n".join(lines)
    if truncate_last:
        body = body[: -len(lines[-1]) // 2]  # sever the final line mid-JSON
    p.write_text(body + ("" if truncate_last else "\n"), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 1. synthetic file with a known answer
# ---------------------------------------------------------------------------

def test_metrics_have_hand_computed_values():
    # baseline vocabulary {a,b,c,d}; response vocabulary {a,b,x,y}
    # intersection {a,b} = 2, union {a,b,c,d,x,y} = 6 -> jaccard 1/3
    m = ana.response_metrics("a b x y", "a b c d")
    assert m["jaccard_vs_baseline"] == pytest.approx(1 / 3, abs=1e-6)
    assert m["divergence_vs_baseline"] == pytest.approx(2 / 3, abs=1e-6)
    assert m["n_words"] == 4
    assert m["len_ratio_vs_baseline"] == pytest.approx(1.0)
    assert m["identical_to_baseline"] is False


def test_identical_text_has_zero_divergence():
    m = ana.response_metrics("the same words", "the same words")
    assert m["divergence_vs_baseline"] == 0.0
    assert m["identical_to_baseline"] is True


def test_degenerate_repetition_metrics():
    # "ha ha ha ha": 1 distinct unigram / 4 -> 0.25; bigrams all ("ha","ha") -> 1/3
    m = ana.response_metrics("ha ha ha ha", "something else entirely")
    assert m["distinct_1"] == pytest.approx(0.25)
    assert m["distinct_2"] == pytest.approx(1 / 3, abs=1e-6)
    assert m["max_word_freq_share"] == pytest.approx(1.0)
    assert m["divergence_vs_baseline"] == pytest.approx(1.0)


def test_curve_means_are_exact_over_two_prompts():
    """Two prompts per dose, divergences 0.0 and 2/3 -> mean exactly 1/3."""
    fidx = sweep.FEATURES[0]["idx"]
    dose = sweep.DOSES[0]
    recs = [
        _baseline("p0", "a b c d"),
        _baseline("p1", "a b c d"),
        _cell(fidx, "steer", "target", dose, "p0", "a b c d"),   # divergence 0.0
        _cell(fidx, "steer", "target", dose, "p1", "a b x y"),   # divergence 2/3
    ]
    result = ana.analyze(recs, sweep)
    curve = next(c for c in result["curves"]
                 if c["feature_idx"] == fidx and c["mode"] == "steer" and c["arm"] == "target")
    pt = next(p for p in curve["points"] if p["dose_multiple"] == dose)
    assert pt["n_prompts_observed"] == 2
    assert pt["mean_divergence_vs_baseline"] == pytest.approx(1 / 3, abs=1e-6)
    assert pt["complete"] is False          # 2 of 8 prompts
    assert curve["curve_complete"] is False


def test_complete_synthetic_grid_reports_complete(tmp_path):
    """A full 1736-cell file must report complete, no defects, exit 0."""
    recs = [_baseline(f"p{i}", "base text here") for i in range(len(sweep.DEFAULT_PROMPTS))]
    for f in sweep.FEATURES:
        for mode in sweep.MODES:
            for dose in sweep.DOSES:
                for arm in ("target", "random_feature"):
                    for i in range(len(sweep.DEFAULT_PROMPTS)):
                        recs.append(_cell(f["idx"], mode, arm, dose, f"p{i}", "base text here"))
    assert len(recs) == 1736
    p = _write(tmp_path, recs)
    rc = ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    assert rc == 0
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    assert result["is_complete"] is True
    assert result["n_cells_missing"] == 0
    assert result["defects"] == []
    assert result["completeness_pct"] == 100.0


# ---------------------------------------------------------------------------
# 2. truncated file
# ---------------------------------------------------------------------------

def test_truncated_file_is_announced_not_smoothed(tmp_path):
    recs = [_baseline("p0", "a b c d"),
            _cell(sweep.FEATURES[0]["idx"], "steer", "target", sweep.DOSES[0], "p0", "a b x y")]
    p = _write(tmp_path, recs, truncate_last=True)
    load = ana.load_records(p)
    assert load.malformed_lines, "a severed final line must be reported, not silently dropped"
    result = ana.analyze(load.records, sweep)
    assert result["is_complete"] is False
    assert result["n_cells_missing"] > 0


def test_partial_run_exits_nonzero_and_names_missing_features(tmp_path):
    """Only baselines present: all 9 features must be named as absent entirely."""
    recs = [_baseline(f"p{i}", "base") for i in range(len(sweep.DEFAULT_PROMPTS))]
    p = _write(tmp_path, recs)
    rc = ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    assert rc == 1, "an incomplete grid must not exit 0 by default"
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    ms = result["missing_summary"]
    assert ms["n_features_absent_entirely"] == len(sweep.FEATURES)
    assert sorted(ms["features_absent_entirely"]) == sorted(f["idx"] for f in sweep.FEATURES)
    assert result["n_cells_missing"] == 1728
    assert len(result["missing_cells"]) == 1728, "every missing cell must be enumerated"


def test_report_text_contains_incomplete_banner(tmp_path):
    recs = [_baseline("p0", "base")]
    p = _write(tmp_path, recs)
    ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    txt = (tmp_path / "out" / "sweep_analysis_report.txt").read_text(encoding="utf-8")
    assert "INCOMPLETE" in txt
    assert "THIS ANALYSIS RUNS ON A PARTIAL FILE" in txt
    assert "FEATURES WITH NO DATA AT ALL" in txt


def test_allow_partial_flag_still_prints_banner(tmp_path):
    recs = [_baseline("p0", "base")]
    p = _write(tmp_path, recs)
    rc = ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"),
                   "--allow-partial", "--quiet"])
    assert rc == 0
    txt = (tmp_path / "out" / "sweep_analysis_report.txt").read_text(encoding="utf-8")
    assert "INCOMPLETE" in txt, "silencing the exit code must not silence the banner"


def test_missing_baseline_is_flagged(tmp_path):
    """A missing baseline makes divergence undefined for that prompt; say so."""
    recs = [_baseline(f"p{i}", "base") for i in range(len(sweep.DEFAULT_PROMPTS) - 1)]
    p = _write(tmp_path, recs)
    ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    assert result["missing_summary"]["baselines_missing"] == 1


# ---------------------------------------------------------------------------
# 3. duplicated cell -- the two-jobs-one-file hazard
# ---------------------------------------------------------------------------

def test_duplicate_cell_is_detected_and_not_averaged(tmp_path):
    fidx, dose = sweep.FEATURES[0]["idx"], sweep.DOSES[0]
    recs = [
        _baseline("p0", "a b c d"),
        _cell(fidx, "steer", "target", dose, "p0", "a b c d"),   # divergence 0.0
        _cell(fidx, "steer", "target", dose, "p0", "x y z w"),   # divergence 1.0, SAME cell
    ]
    p = _write(tmp_path, recs)
    rc = ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    assert rc == 2, "a duplicated cell is a defect and must exit 2"
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    assert len(result["duplicate_cells"]) == 1
    dup = result["duplicate_cells"][0]
    assert dup["n_occurrences"] == 2
    assert dup["cell"] == [fidx, "steer", "target", dose, "p0"]
    assert any("DUPLICATE CELLS" in d for d in result["defects"])
    # the mean of 0.0 and 1.0 is 0.5 -- a plausible-looking number that must
    # never be presented as if it were one measurement
    txt = (tmp_path / "out" / "sweep_analysis_report.txt").read_text(encoding="utf-8")
    assert "DEFECTS" in txt
    assert "RESULTS ARE NOT USABLE" in txt


def test_unknown_cell_is_a_defect(tmp_path):
    recs = [_baseline("p0", "base"),
            _cell(999999, "steer", "target", sweep.DOSES[0], "p0", "text")]
    p = _write(tmp_path, recs)
    rc = ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    assert rc == 2
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    assert len(result["unknown_cells"]) == 1
    assert any("UNKNOWN CELLS" in d for d in result["defects"])


def test_duplicate_detection_survives_interleaving(tmp_path):
    """Two jobs appending concurrently interleave rather than append in blocks."""
    fidx, dose = sweep.FEATURES[0]["idx"], sweep.DOSES[0]
    recs = [_baseline("p0", "a b")]
    for i in range(4):
        recs.append(_cell(fidx, "steer", "target", dose, f"p{i}", "job one output"))
    for i in range(4):
        recs.append(_cell(fidx, "steer", "target", dose, f"p{i}", "job two output"))
    p = _write(tmp_path, recs)
    result = ana.analyze(ana.load_records(p).records, sweep)
    assert len(result["duplicate_cells"]) == 4
    assert all(d["n_occurrences"] == 2 for d in result["duplicate_cells"])


# ---------------------------------------------------------------------------
# determinism / re-runnability
# ---------------------------------------------------------------------------

def test_two_runs_are_byte_identical(tmp_path):
    recs = [_baseline("p0", "a b c"),
            _cell(sweep.FEATURES[0]["idx"], "steer", "target", sweep.DOSES[0], "p0", "a b x")]
    p = _write(tmp_path, recs)
    # Same command, twice, into the same directory: that is what "re-runnable"
    # means. (Comparing across different --out-dir values would fail for a
    # legitimate reason -- the manifest path is recorded as provenance.)
    d = tmp_path / "out"
    outs = []
    for _ in range(2):
        ana.main(["--records", str(p), "--out-dir", str(d), "--quiet"])
        outs.append((d / "sweep_analysis.json").read_bytes())
    assert outs[0] == outs[1], "the pipeline must be deterministic across runs"


def test_only_provenance_paths_differ_across_out_dirs(tmp_path):
    """Guards the above: everything except the recorded paths is identical."""
    recs = [_baseline("p0", "a b c"),
            _cell(sweep.FEATURES[0]["idx"], "steer", "target", sweep.DOSES[0], "p0", "a b x")]
    p = _write(tmp_path, recs)
    payloads = []
    for i in range(2):
        d = tmp_path / f"out{i}"
        ana.main(["--records", str(p), "--out-dir", str(d), "--quiet"])
        obj = json.loads((d / "sweep_analysis.json").read_text(encoding="utf-8"))
        obj.pop("feature_manifest_path")
        payloads.append(json.dumps(obj, sort_keys=True))
    assert payloads[0] == payloads[1]


def test_manifest_is_regenerated(tmp_path):
    recs = [_baseline("p0", "base")]
    p = _write(tmp_path, recs)
    out = tmp_path / "out"
    ana.main(["--records", str(p), "--out-dir", str(out), "--quiet"])
    mpath = out / sweep.FEATURE_MANIFEST_FILENAME
    assert mpath.exists()
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    assert len(manifest["features"]) == len(sweep.FEATURES)
    assert {f["idx"] for f in manifest["features"]} == {f["idx"] for f in sweep.FEATURES}


def test_missing_records_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ana.load_records(tmp_path / "nope.jsonl")


# ---------------------------------------------------------------------------
# RULING 1 -- ablation is replicates, not a dose curve
# ---------------------------------------------------------------------------

def _ablate_cell(fidx, dose, pid, text):
    r = _cell(fidx, "ablate", "target", dose, pid, text)
    r["absolute_clamp_value"] = 0.0      # ablation ignores dose, by design
    return r


def test_ablate_is_not_emitted_as_a_dose_curve():
    fidx = sweep.FEATURES[0]["idx"]
    recs = [_baseline("p0", "a b c d")]
    for dose in sweep.DOSES:
        recs.append(_ablate_cell(fidx, dose, "p0", "a b x y"))
    result = ana.analyze(recs, sweep)
    assert all(c["mode"] != "ablate" for c in result["curves"]), \
        "ablate must never appear among the dose curves"
    reps = [r for r in result["ablate_replicates"] if r["feature_idx"] == fidx]
    assert len(reps) == 1
    assert reps[0]["presentation"] == "REPLICATES -- NOT A DOSE CURVE"
    assert reps[0]["dose_slot_is_inert"] is True
    assert reps[0]["distinct_absolute_clamp_values"] == [0.0]
    assert reps[0]["n_replicate_slots_observed"] == len(sweep.DOSES)


def test_ablate_replicates_carry_dispersion_for_the_noise_floor():
    fidx = sweep.FEATURES[0]["idx"]
    recs = [_baseline("p0", "a b c d")]
    # identical texts -> zero dispersion, an exactly known noise floor
    for dose in sweep.DOSES:
        recs.append(_ablate_cell(fidx, dose, "p0", "a b x y"))
    result = ana.analyze(recs, sweep)
    rep = result["ablate_replicates"][0]
    assert rep["divergence_pooled"]["n"] == len(sweep.DOSES)
    assert rep["divergence_pooled"]["mean"] == pytest.approx(2 / 3, abs=1e-6)
    assert rep["divergence_pooled"]["sd"] == pytest.approx(0.0, abs=1e-9)
    assert rep["divergence_pooled"]["min"] == rep["divergence_pooled"]["max"]


def test_report_labels_ablate_as_replicates(tmp_path):
    fidx = sweep.FEATURES[0]["idx"]
    recs = [_baseline("p0", "a b c d")]
    for dose in sweep.DOSES:
        recs.append(_ablate_cell(fidx, dose, "p0", "a b x y"))
    p = _write(tmp_path, recs)
    ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    txt = (tmp_path / "out" / "sweep_analysis_report.txt").read_text(encoding="utf-8")
    assert "SIX REPLICATES OF ONE CONDITION, NOT A DOSE CURVE" in txt
    assert "NOISE FLOOR" in txt


# ---------------------------------------------------------------------------
# RULING 2 -- saturation is asserted, not left to the reader
# ---------------------------------------------------------------------------

def test_saturation_threshold_is_preregistered_constant():
    assert ana.SATURATION_DIVERGENCE_THRESHOLD == 0.99
    assert ana.DECLARED_UNINFORMATIVE_DOSES == (8.0, 16.0)
    assert ana.INFORMATIVE_DOSES == (0.5, 1.0, 2.0, 4.0)


def test_per_cell_saturated_flag():
    # no shared vocabulary at all -> divergence 1.0 -> saturated
    assert ana.response_metrics("x y z", "a b c")["saturated"] is True
    # heavy overlap -> not saturated
    assert ana.response_metrics("a b c", "a b c d")["saturated"] is False


def test_contrast_refused_when_control_saturates(tmp_path):
    """Control shares no vocabulary with baseline; target does. The contrast
    must be REFUSED rather than reported as a large target effect."""
    fidx, dose = sweep.FEATURES[0]["idx"], 2.0   # an informative dose
    recs = [_baseline(f"p{i}", "a b c d") for i in range(len(sweep.DEFAULT_PROMPTS))]
    for i in range(len(sweep.DEFAULT_PROMPTS)):
        recs.append(_cell(fidx, "steer", "target", dose, f"p{i}", "a b x y"))       # 2/3
        recs.append(_cell(fidx, "steer", "random_feature", dose, f"p{i}", "q r s"))  # 1.0
    result = ana.analyze(recs, sweep)
    con = next(c for c in result["target_vs_control_contrasts"] if c["feature_idx"] == fidx)
    pt = next(p for p in con["points"] if p["dose_multiple"] == dose)
    assert pt["control_saturated"] is True
    assert pt["target_saturated"] is False
    assert pt["control_saturated_before_target"] is True
    assert pt["contrast_reported"] is False
    assert pt["target_minus_control"] is None
    assert "control_arm_saturated" in pt["refusal_reasons"]
    assert dose in con["control_saturates_before_target_at"]


def test_contrast_reported_when_neither_arm_saturates():
    fidx, dose = sweep.FEATURES[0]["idx"], 2.0
    recs = [_baseline("p0", "a b c d")]
    recs.append(_cell(fidx, "steer", "target", dose, "p0", "a b x y"))          # 2/3
    # control "a b c x" vs baseline "a b c d": intersection 3, union 5
    # -> jaccard 0.6, divergence 0.4
    recs.append(_cell(fidx, "steer", "random_feature", dose, "p0", "a b c x"))
    result = ana.analyze(recs, sweep)
    con = next(c for c in result["target_vs_control_contrasts"] if c["feature_idx"] == fidx)
    pt = next(p for p in con["points"] if p["dose_multiple"] == dose)
    assert pt["contrast_reported"] is True
    assert pt["control_mean_divergence"] == pytest.approx(0.4, abs=1e-6)
    assert pt["target_mean_divergence"] == pytest.approx(2 / 3, abs=1e-6)
    assert pt["target_minus_control"] == pytest.approx(2 / 3 - 0.4, abs=1e-6)


def test_declared_uninformative_doses_are_always_refused():
    fidx = sweep.FEATURES[0]["idx"]
    recs = [_baseline("p0", "a b c d")]
    for dose in (8.0, 16.0):
        # neither arm saturates -- refusal must come from the pre-declaration alone
        recs.append(_cell(fidx, "steer", "target", dose, "p0", "a b x y"))
        recs.append(_cell(fidx, "steer", "random_feature", dose, "p0", "a b c x"))
    result = ana.analyze(recs, sweep)
    con = next(c for c in result["target_vs_control_contrasts"] if c["feature_idx"] == fidx)
    for dose in (8.0, 16.0):
        pt = next(p for p in con["points"] if p["dose_multiple"] == dose)
        assert pt["contrast_reported"] is False
        assert "dose_declared_uninformative_by_saturation" in pt["refusal_reasons"]


def test_report_shows_refusals_and_preregistration(tmp_path):
    fidx = sweep.FEATURES[0]["idx"]
    recs = [_baseline("p0", "a b c d")]
    recs.append(_cell(fidx, "steer", "target", 8.0, "p0", "a b x y"))
    recs.append(_cell(fidx, "steer", "random_feature", 8.0, "p0", "q r s"))
    p = _write(tmp_path, recs)
    ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    txt = (tmp_path / "out" / "sweep_analysis_report.txt").read_text(encoding="utf-8")
    assert "PRE-REGISTERED RULINGS" in txt
    assert "REFUSED" in txt
    assert "not functioning as a control" in txt


def test_preregistration_block_is_persisted(tmp_path):
    recs = [_baseline("p0", "base")]
    p = _write(tmp_path, recs)
    ana.main(["--records", str(p), "--out-dir", str(tmp_path / "out"), "--quiet"])
    result = json.loads((tmp_path / "out" / "sweep_analysis.json").read_text(encoding="utf-8"))
    pre = result["preregistration"]
    assert pre["saturation_divergence_threshold"] == 0.99
    assert pre["declared_uninformative_doses"] == [8.0, 16.0]
    assert "before the complete" in pre["note"]
