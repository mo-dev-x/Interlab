#!/usr/bin/env python
"""D2.1 -- analysis pipeline for the Gemma 3 steer/ablate sweep.

ONE COMMAND, deterministic, re-runnable:

    python scripts/analyze_gemma3_sweep.py

Runs offline, CPU-only, no GPU and no network: it reads the sweep's JSONL log
and regenerates the feature manifest via gemma3_sweep.write_feature_manifest(),
which is pure Python.

DESIGN COMMITMENT -- THIS PIPELINE REFUSES TO BE QUIETLY WRONG.
A run over a partial file prints an INCOMPLETE banner naming what is missing
and exits non-zero. A duplicated cell key is a DEFECT that halts the run: two
jobs appending to one JSONL was a live hazard, and averaging two generations of
the same cell would silently halve the variance of whatever it touched. Cells
outside the pre-registered grid are likewise a defect, not a curiosity.

WHAT THE RESPONSE METRICS ARE, AND ARE NOT.
The sweep records generated TEXT, not activations or logits, so every response
metric here is a SURFACE-FORM property of that text measured against the
same-prompt baseline generation. They quantify how far a clamp moved the
output, not whether it moved it toward the feature's nominal concept. Nothing
here assigns or validates a domain class; that is adjudication and belongs to a
separate pass.

EXIT CODES
    0  complete grid, no defects
    1  incomplete (partial sweep) -- expected while the sweep is in flight
    2  defect (duplicate cells, unknown cells, or grid-size mismatch)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SWEEP_MODULE_PATH = REPO_ROOT / "scripts" / "legacy" / "gemma3_sweep.py"

# Pre-registered cell count. 8 baselines + 9 features x 2 modes x 6 doses
# x 2 arms x 8 prompts = 8 + 1728 = 1736. Any deviation is a defect: it means
# the harness config drifted from the registered design, and a curve built on a
# drifted grid is not the experiment that was registered.
PREREGISTERED_CELL_COUNT = 1736

CELL_KEY_FIELDS = ("feature_idx", "mode", "arm", "dose_multiple", "prompt_id")
_WORD_RE = re.compile(r"[a-z0-9']+")

# ---------------------------------------------------------------------------
# PRE-REGISTERED RULINGS -- fixed 2026-08-08, BEFORE the complete records file
# existed (declared while the sweep stood at 900/1736). They are constants, not
# options, so that no threshold can be chosen after seeing which one flatters
# the result.
# ---------------------------------------------------------------------------

# RULING 1 -- ABLATION IS REPLICATES, NOT A DOSE CURVE.
# absolute_clamp_value is 0.0 for every ablate record; the dose slot exists only
# so seed derivation stays uniform across modes. The six dose slots are therefore
# six REPLICATES of one condition. Plotting them against dose would draw a curve
# through a variable that was never varied, and calling the flatness a "flat dose
# response" would report the design as a result. Presented correctly they are
# worth more than they would be worth presented wrongly: their dispersion is a
# free NOISE FLOOR for the steer arms.
ABLATE_IS_REPLICATED_NOT_DOSED = True

# RULING 2 -- SATURATION.
# divergence = 1 - Jaccard(response vocabulary, same-prompt baseline vocabulary).
# At divergence 1.0 the generation shares NO vocabulary with baseline, which is
# the signature of degenerate output rather than steering. Threshold declared at
# 0.99: Jaccard <= 0.01 means at most ~1 shared word against a typical union of
# ~100+, i.e. no meaningful lexical relationship survives.
SATURATION_DIVERGENCE_THRESHOLD = 0.99

# Doses 8 and 16 are declared UNINFORMATIVE-BY-SATURATION in advance. Where both
# arms saturate, the cell cannot discriminate target from control; and a control
# that saturates FIRST is not functioning as a control at all.
DECLARED_UNINFORMATIVE_DOSES = (8.0, 16.0)
INFORMATIVE_DOSES = (0.5, 1.0, 2.0, 4.0)

PREREGISTRATION_NOTE = (
    "Declared 2026-08-08 while the sweep stood at 900/1736, before the complete "
    "file existed. Saturation threshold 0.99 on divergence (1 - Jaccard vs "
    "same-prompt baseline). Doses 8.0 and 16.0 declared uninformative-by-"
    "saturation; informative range 0.5-4.0. Ablation is six replicates of one "
    "condition, never a dose curve. A target-vs-control contrast is REFUSED "
    "wherever the control arm is saturated."
)


# ---------------------------------------------------------------------------
# harness import (pure-Python surface only; every torch import in that module
# is function-local, so importing it here pulls in no heavy dependency)
# ---------------------------------------------------------------------------

def load_sweep_module(path: Path = SWEEP_MODULE_PATH):
    if not path.exists():
        raise FileNotFoundError(f"sweep harness not found at {path}")
    spec = importlib.util.spec_from_file_location("gemma3_sweep_harness", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load a module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

class LoadResult:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.malformed_lines: list[int] = []
        self.n_lines = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_lines_read": self.n_lines,
            "n_records_parsed": len(self.records),
            "malformed_line_numbers": self.malformed_lines,
            "n_malformed": len(self.malformed_lines),
        }


def load_records(path: Path) -> LoadResult:
    """Parses the JSONL log. A partially written final line -- exactly what a
    hard kill mid-write leaves behind -- fails to parse and is REPORTED rather
    than silently dropped, so a truncated file can never masquerade as a short
    but complete one."""
    out = LoadResult()
    if not path.exists():
        raise FileNotFoundError(f"records file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            out.n_lines += 1
            try:
                out.records.append(json.loads(line))
            except json.JSONDecodeError:
                out.malformed_lines.append(lineno)
    return out


# ---------------------------------------------------------------------------
# the pre-registered grid
# ---------------------------------------------------------------------------

def cell_key(record: dict[str, Any]) -> tuple:
    return tuple(record.get(f) for f in CELL_KEY_FIELDS)


def build_expected_grid(sweep) -> list[tuple]:
    """Reconstructs every pre-registered cell key from the harness's own
    constants -- never from the observed records, which is the whole point: a
    grid inferred from the data cannot detect that the data is missing."""
    keys: list[tuple] = []
    prompt_ids = [f"p{i}" for i in range(len(sweep.DEFAULT_PROMPTS))]
    for pid in prompt_ids:
        keys.append((None, "baseline", "none", None, pid))
    for feature in sweep.FEATURES:
        for mode in sweep.MODES:
            for dose in sweep.DOSES:
                for arm in ("target", "random_feature"):
                    for pid in prompt_ids:
                        keys.append((feature["idx"], mode, arm, dose, pid))
    return keys


# ---------------------------------------------------------------------------
# response metrics (surface-form, deterministic)
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def distinct_n(words: list[str], n: int) -> float:
    if len(words) < n:
        return 0.0
    grams = [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]
    return len(set(grams)) / len(grams)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def response_metrics(text: str, baseline_text: str | None) -> dict[str, Any]:
    words = tokenize(text)
    counts = Counter(words)
    m: dict[str, Any] = {
        "n_chars": len(text or ""),
        "n_words": len(words),
        "distinct_1": round(distinct_n(words, 1), 6),
        "distinct_2": round(distinct_n(words, 2), 6),
        "max_word_freq_share": round(max(counts.values()) / len(words), 6) if words else 0.0,
    }
    if baseline_text is None:
        m.update({"jaccard_vs_baseline": None, "divergence_vs_baseline": None,
                  "identical_to_baseline": None, "len_ratio_vs_baseline": None,
                  "saturated": None})
        return m
    bwords = tokenize(baseline_text)
    j = jaccard(set(words), set(bwords))
    divergence = round(1.0 - j, 6)
    m.update({
        "jaccard_vs_baseline": round(j, 6),
        "divergence_vs_baseline": divergence,
        "identical_to_baseline": (text or "") == (baseline_text or ""),
        "len_ratio_vs_baseline": round(len(words) / len(bwords), 6) if bwords else None,
        # pre-declared, not tuned after the fact
        "saturated": divergence >= SATURATION_DIVERGENCE_THRESHOLD,
    })
    return m


def _stdev(xs: list[float]) -> float | None:
    vals = [x for x in xs if x is not None]
    if len(vals) < 2:
        return None
    return round(statistics.stdev(vals), 6)


def _dispersion(xs: list[float]) -> dict[str, Any]:
    vals = [x for x in xs if x is not None]
    if not vals:
        return {"n": 0, "mean": None, "sd": None, "min": None, "max": None}
    return {"n": len(vals), "mean": _mean(vals), "sd": _stdev(vals),
            "min": round(min(vals), 6), "max": round(max(vals), 6)}


def _mean(xs: list[float]) -> float | None:
    vals = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return round(sum(vals) / len(vals), 6) if vals else None


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------

def analyze(records: list[dict[str, Any]], sweep) -> dict[str, Any]:
    expected = build_expected_grid(sweep)
    expected_set = set(expected)

    grid_size_ok = len(expected) == PREREGISTERED_CELL_COUNT

    observed_counts = Counter(cell_key(r) for r in records)
    duplicates = sorted(
        ({"cell": list(k), "n_occurrences": n} for k, n in observed_counts.items() if n > 1),
        key=lambda d: (-d["n_occurrences"], str(d["cell"])),
    )
    unknown = sorted(
        ({"cell": list(k)} for k in observed_counts if k not in expected_set),
        key=lambda d: str(d["cell"]),
    )
    missing = [k for k in expected if k not in observed_counts]

    defects: list[str] = []
    if not grid_size_ok:
        defects.append(
            f"GRID SIZE MISMATCH: harness constants enumerate {len(expected)} cells but the "
            f"pre-registered count is {PREREGISTERED_CELL_COUNT}. The registered design and the "
            f"harness config have diverged; curves built on this grid are not the registered "
            f"experiment."
        )
    if duplicates:
        defects.append(
            f"DUPLICATE CELLS: {len(duplicates)} cell key(s) appear more than once "
            f"({sum(d['n_occurrences'] - 1 for d in duplicates)} excess record(s)). This is the "
            f"two-jobs-appending-to-one-file hazard. Refusing to average over them."
        )
    if unknown:
        defects.append(
            f"UNKNOWN CELLS: {len(unknown)} record(s) carry cell keys outside the pre-registered "
            f"grid."
        )

    # ---- baselines, needed before any divergence metric ----
    baselines = {r["prompt_id"]: r.get("text") for r in records if r.get("mode") == "baseline"}

    # ---- per-record metrics ----
    per_record = []
    for r in records:
        base = baselines.get(r.get("prompt_id")) if r.get("mode") != "baseline" else None
        per_record.append({
            "cell": list(cell_key(r)),
            "feature_idx": r.get("feature_idx"),
            "mode": r.get("mode"),
            "arm": r.get("arm"),
            "dose_multiple": r.get("dose_multiple"),
            "prompt_id": r.get("prompt_id"),
            "absolute_clamp_value": r.get("absolute_clamp_value"),
            "maxActApprox": r.get("maxActApprox"),
            "seed": r.get("seed"),
            **response_metrics(r.get("text") or "", base),
        })

    # ---- dose-response curves: (feature, mode, arm) -> ordered dose points ----
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for m in per_record:
        if m["mode"] == "baseline":
            continue
        buckets[(m["feature_idx"], m["mode"], m["arm"])].append(m)

    feature_meta = {f["idx"]: f for f in sweep.FEATURES}

    def dose_point(pts: list[dict], dose: float) -> dict[str, Any]:
        divs = [p["divergence_vs_baseline"] for p in pts]
        n_sat = sum(1 for p in pts if p.get("saturated"))
        mean_div = _mean(divs)
        return {
            "dose_multiple": dose,
            "n_prompts_observed": len(pts),
            "n_prompts_expected": len(sweep.DEFAULT_PROMPTS),
            "complete": len(pts) == len(sweep.DEFAULT_PROMPTS),
            "mean_divergence_vs_baseline": mean_div,
            "sd_divergence_vs_baseline": _stdev(divs),
            "n_saturated": n_sat,
            "frac_saturated": round(n_sat / len(pts), 6) if pts else None,
            "arm_saturated": (mean_div is not None
                              and mean_div >= SATURATION_DIVERGENCE_THRESHOLD),
            "declared_uninformative_dose": dose in DECLARED_UNINFORMATIVE_DOSES,
            "mean_distinct_2": _mean([p["distinct_2"] for p in pts]),
            "mean_max_word_freq_share": _mean([p["max_word_freq_share"] for p in pts]),
            "mean_n_words": _mean([float(p["n_words"]) for p in pts]),
            "mean_len_ratio_vs_baseline": _mean([p["len_ratio_vs_baseline"] for p in pts]),
            "absolute_clamp_value": pts[0]["absolute_clamp_value"] if pts else None,
        }

    # ---- RULING 1: steer gets dose curves; ablate gets replicates ----
    curves = []
    ablate_replicates = []
    for (fidx, mode, arm), rows in sorted(buckets.items(),
                                          key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        meta = feature_meta.get(fidx, {})
        head = {
            "feature_idx": fidx,
            "label": meta.get("label"),
            "domain_class_from_manifest": meta.get("domain_class"),
            "maxActApprox": meta.get("maxActApprox"),
            "mode": mode,
            "arm": arm,
        }
        if mode == "ablate":
            # Six dose slots = six replicates of ONE condition (clamp value 0.0).
            by_slot: dict[float, list[dict]] = defaultdict(list)
            for row in rows:
                by_slot[row["dose_multiple"]].append(row)
            slot_means = [_mean([p["divergence_vs_baseline"] for p in by_slot[d]])
                          for d in sweep.DOSES if by_slot.get(d)]
            all_divs = [r["divergence_vs_baseline"] for r in rows]
            clamp_values = sorted({r["absolute_clamp_value"] for r in rows
                                   if r["absolute_clamp_value"] is not None})
            ablate_replicates.append({
                **head,
                "presentation": "REPLICATES -- NOT A DOSE CURVE",
                "why": ("absolute_clamp_value is 0.0 in every ablate record; the dose slot "
                        "exists only for seed-derivation uniformity. These are replicates of "
                        "one condition."),
                "n_replicate_slots_observed": sum(1 for d in sweep.DOSES if by_slot.get(d)),
                "n_replicate_slots_expected": len(sweep.DOSES),
                "n_records": len(rows),
                "distinct_absolute_clamp_values": clamp_values,
                "dose_slot_is_inert": clamp_values in ([0.0], []),
                "divergence_pooled": _dispersion(all_divs),
                "divergence_across_slot_means": _dispersion(slot_means),
                "distinct_2_pooled": _dispersion([r["distinct_2"] for r in rows]),
                "n_saturated": sum(1 for r in rows if r.get("saturated")),
            })
        else:
            by_dose: dict[float, list[dict]] = defaultdict(list)
            for row in rows:
                by_dose[row["dose_multiple"]].append(row)
            points = [dose_point(by_dose.get(d, []), d) for d in sweep.DOSES]
            curves.append({
                **head,
                "curve_complete": all(p["complete"] for p in points),
                "n_points_complete": sum(1 for p in points if p["complete"]),
                "n_points_total": len(points),
                "points": points,
            })

    # ---- noise floor from the ablate replicates (free, and only valid because
    # ---- ruling 1 refuses to spend them on a curve) ----
    noise_floor = {
        "source": "ablate replicates (dose slot inert), pooled within-arm dispersion",
        "sd_within_replicate_sets": _dispersion(
            [r["divergence_pooled"]["sd"] for r in ablate_replicates
             if r["divergence_pooled"]["sd"] is not None]),
        "sd_across_slot_means": _dispersion(
            [r["divergence_across_slot_means"]["sd"] for r in ablate_replicates
             if r["divergence_across_slot_means"]["sd"] is not None]),
        "interpretation": ("A steer effect smaller than this dispersion is not "
                           "distinguishable from replicate-to-replicate noise."),
    }

    # ---- RULING 2: target-vs-control contrast, REFUSED where the control saturates ----
    contrasts = []
    steer_by_key = {(c["feature_idx"], c["arm"]): c for c in curves}
    for fidx in sorted({c["feature_idx"] for c in curves}):
        tgt = steer_by_key.get((fidx, "target"))
        ctl = steer_by_key.get((fidx, "random_feature"))
        if not tgt or not ctl:
            continue
        pts = []
        for tp, cp in zip(tgt["points"], ctl["points"]):
            reasons = []
            if cp["arm_saturated"]:
                reasons.append("control_arm_saturated")
            if tp["declared_uninformative_dose"]:
                reasons.append("dose_declared_uninformative_by_saturation")
            if tp["mean_divergence_vs_baseline"] is None or cp["mean_divergence_vs_baseline"] is None:
                reasons.append("missing_data")
            reportable = not reasons
            pts.append({
                "dose_multiple": tp["dose_multiple"],
                "target_mean_divergence": tp["mean_divergence_vs_baseline"],
                "control_mean_divergence": cp["mean_divergence_vs_baseline"],
                "target_saturated": tp["arm_saturated"],
                "control_saturated": cp["arm_saturated"],
                "control_saturated_before_target": bool(
                    cp["arm_saturated"] and not tp["arm_saturated"]),
                "contrast_reported": reportable,
                "refusal_reasons": reasons,
                "target_minus_control": (
                    round(tp["mean_divergence_vs_baseline"] - cp["mean_divergence_vs_baseline"], 6)
                    if reportable else None),
            })
        contrasts.append({
            "feature_idx": fidx,
            "label": feature_meta.get(fidx, {}).get("label"),
            "mode": "steer",
            "n_doses_reportable": sum(1 for p in pts if p["contrast_reported"]),
            "n_doses_refused": sum(1 for p in pts if not p["contrast_reported"]),
            "control_saturates_before_target_at": [
                p["dose_multiple"] for p in pts if p["control_saturated_before_target"]],
            "points": pts,
        })

    complete = not missing and not defects
    return {
        "preregistration": {
            "note": PREREGISTRATION_NOTE,
            "saturation_divergence_threshold": SATURATION_DIVERGENCE_THRESHOLD,
            "declared_uninformative_doses": list(DECLARED_UNINFORMATIVE_DOSES),
            "informative_doses": list(INFORMATIVE_DOSES),
            "ablate_is_replicated_not_dosed": ABLATE_IS_REPLICATED_NOT_DOSED,
        },
        "ablate_replicates": ablate_replicates,
        "noise_floor": noise_floor,
        "target_vs_control_contrasts": contrasts,
        "preregistered_cell_count": PREREGISTERED_CELL_COUNT,
        "enumerated_cell_count": len(expected),
        "grid_size_matches_preregistration": grid_size_ok,
        "n_records": len(records),
        "n_cells_observed": len(observed_counts),
        "n_cells_missing": len(missing),
        "completeness_pct": round(100.0 * len(observed_counts) / len(expected), 2) if expected else 0.0,
        "is_complete": complete,
        "defects": defects,
        "duplicate_cells": duplicates,
        "unknown_cells": unknown,
        "missing_cells": [list(k) for k in missing],
        "missing_summary": summarize_missing(missing, sweep),
        "metric_semantics": (
            "Surface-form text metrics against the same-prompt baseline generation. They "
            "quantify how far a clamp moved the output, NOT whether it moved toward the "
            "feature's nominal concept. No domain class is assigned or validated here."
        ),
        "curves": curves,
        "per_record_metrics": per_record,
    }


def summarize_missing(missing: list[tuple], sweep) -> dict[str, Any]:
    """Names what is missing at a granularity a human can act on, instead of
    emitting a wall of tuples."""
    if not missing:
        return {"features_absent_entirely": [], "by_feature": {}, "by_mode": {}, "baselines_missing": 0}
    by_feature: dict[Any, int] = Counter(k[0] for k in missing)
    by_mode: dict[Any, int] = Counter(k[1] for k in missing)
    per_feature_expected = len(sweep.MODES) * len(sweep.DOSES) * 2 * len(sweep.DEFAULT_PROMPTS)
    absent = sorted(
        f["idx"] for f in sweep.FEATURES
        if by_feature.get(f["idx"], 0) == per_feature_expected
    )
    return {
        "features_absent_entirely": absent,
        "n_features_absent_entirely": len(absent),
        "cells_expected_per_feature": per_feature_expected,
        "by_feature": {str(k): v for k, v in sorted(by_feature.items(), key=lambda kv: str(kv[0]))},
        "by_mode": {str(k): v for k, v in sorted(by_mode.items(), key=lambda kv: str(kv[0]))},
        "baselines_missing": by_mode.get("baseline", 0),
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def render_report(a: dict[str, Any], load: dict[str, Any], manifest_path: Path,
                  max_listed: int = 20) -> str:
    L: list[str] = []
    add = L.append
    add("=" * 78)
    add("D2.1 GEMMA 3 SWEEP -- ANALYSIS")
    add("=" * 78)
    add(f"records file lines read : {load['n_lines_read']}")
    add(f"records parsed          : {load['n_records_parsed']}")
    if load["n_malformed"]:
        add(f"!! MALFORMED LINES      : {load['n_malformed']} at {load['malformed_line_numbers']}")
        add("   (a truncated final line is the signature of a hard kill mid-write)")
    add(f"feature manifest        : {manifest_path}")
    add("")
    add(f"pre-registered cells    : {a['preregistered_cell_count']}")
    add(f"enumerated from harness : {a['enumerated_cell_count']}"
        f"  [{'OK' if a['grid_size_matches_preregistration'] else 'MISMATCH'}]")
    add(f"cells observed          : {a['n_cells_observed']}  ({a['completeness_pct']}%)")
    add(f"cells missing           : {a['n_cells_missing']}")
    add("")

    if a["defects"]:
        add("!" * 78)
        add("DEFECTS -- RESULTS ARE NOT USABLE UNTIL THESE ARE RESOLVED")
        add("!" * 78)
        for d in a["defects"]:
            add(f"  * {d}")
        for d in a["duplicate_cells"][:max_listed]:
            add(f"      duplicated {d['n_occurrences']}x: {d['cell']}")
        if len(a["duplicate_cells"]) > max_listed:
            add(f"      ... and {len(a['duplicate_cells']) - max_listed} more duplicated cell(s) "
                f"(all listed in the JSON)")
        for u in a["unknown_cells"][:max_listed]:
            add(f"      unknown cell: {u['cell']}")
        if len(a["unknown_cells"]) > max_listed:
            add(f"      ... and {len(a['unknown_cells']) - max_listed} more unknown cell(s) "
                f"(all listed in the JSON)")
        add("")

    if a["n_cells_missing"]:
        ms = a["missing_summary"]
        add("*" * 78)
        add("INCOMPLETE -- THIS ANALYSIS RUNS ON A PARTIAL FILE")
        add("*" * 78)
        add(f"  {a['n_cells_missing']} of {a['enumerated_cell_count']} cells are absent "
            f"({round(100 - a['completeness_pct'], 2)}% of the grid).")
        if ms["features_absent_entirely"]:
            add(f"  FEATURES WITH NO DATA AT ALL ({ms['n_features_absent_entirely']}): "
                f"{ms['features_absent_entirely']}")
            add(f"    (each owes {ms['cells_expected_per_feature']} cells)")
        add(f"  missing by feature: {ms['by_feature']}")
        add(f"  missing by mode   : {ms['by_mode']}")
        if ms["baselines_missing"]:
            add(f"  !! {ms['baselines_missing']} BASELINE cell(s) missing -- every divergence "
                f"metric for those prompts is undefined")
        add("  Every missing cell is enumerated in the JSON under 'missing_cells'.")
        add("  Curves below are computed only over observed cells; incomplete dose points are")
        add("  flagged per point via 'complete', and per curve via 'curve_complete'.")
        add("")
    else:
        add("COMPLETE -- all pre-registered cells present.")
        add("")

    pre = a["preregistration"]
    add("-" * 78)
    add("PRE-REGISTERED RULINGS (fixed before the complete file existed)")
    add("-" * 78)
    add(f"  saturation threshold (divergence) : {pre['saturation_divergence_threshold']}")
    add(f"  doses uninformative-by-saturation : {pre['declared_uninformative_doses']}")
    add(f"  informative dose range            : {pre['informative_doses']}")
    add("  ablation                          : REPLICATES, never a dose curve")
    add("")

    add("-" * 78)
    add("STEER DOSE-RESPONSE  (divergence vs same-prompt baseline; 1.0 = no shared vocabulary)")
    add("  [S] = arm saturated at/above threshold   [x] = dose declared uninformative")
    add("-" * 78)
    steer = [c for c in a["curves"] if c["mode"] == "steer"]
    dose_headers = [p["dose_multiple"] for p in steer[0]["points"]] if steer else []
    add(f"{'feature':>8} {'arm':<15} " + " ".join(f"{d:>8}" for d in dose_headers))
    for c in steer:
        cells = []
        for p in c["points"]:
            v = p["mean_divergence_vs_baseline"]
            if v is None:
                cells.append("     -- ")
            else:
                cells.append(f"{v:7.3f}" + ("S" if p["arm_saturated"] else " "))
        flag = "" if c["curve_complete"] else f"  [PARTIAL {c['n_points_complete']}/{c['n_points_total']}]"
        add(f"{c['feature_idx']:>8} {c['arm']:<15} " + " ".join(cells) + flag)
    if dose_headers:
        add(f"{'':>8} {'':<15} " + " ".join(
            f"{'[x]':>8}" if d in pre["declared_uninformative_doses"] else f"{'':>8}"
            for d in dose_headers))
    add("")

    add("-" * 78)
    add("ABLATE -- SIX REPLICATES OF ONE CONDITION, NOT A DOSE CURVE")
    add("  absolute_clamp_value is 0.0 in every ablate record; the dose slot is inert.")
    add("  Dispersion here is the NOISE FLOOR for the steer arms above.")
    add("-" * 78)
    add(f"{'feature':>8} {'arm':<15} {'n':>4} {'mean':>8} {'sd':>8} {'min':>8} {'max':>8} inert")
    for r in a["ablate_replicates"]:
        d = r["divergence_pooled"]
        fmt = lambda v: "      --" if v is None else f"{v:8.3f}"
        add(f"{r['feature_idx']:>8} {r['arm']:<15} {d['n']:>4} "
            f"{fmt(d['mean'])} {fmt(d['sd'])} {fmt(d['min'])} {fmt(d['max'])} "
            f"{'yes' if r['dose_slot_is_inert'] else 'NO(!)'}")
    nf = a["noise_floor"]["sd_within_replicate_sets"]
    if nf["n"]:
        add(f"  pooled within-arm sd across {nf['n']} ablate arms: "
            f"mean {nf['mean']}, range {nf['min']}-{nf['max']}")
        add(f"  {a['noise_floor']['interpretation']}")
    add("")

    add("-" * 78)
    add("TARGET vs CONTROL  (steer) -- REFUSED where the control arm saturates")
    add("-" * 78)
    for c in a["target_vs_control_contrasts"]:
        cells = []
        for p in c["points"]:
            if p["contrast_reported"]:
                cells.append(f"{p['target_minus_control']:+8.3f}")
            else:
                cells.append(f"{'REFUSED':>8}")
        add(f"{c['feature_idx']:>8} " + " ".join(cells)
            + f"   reportable {c['n_doses_reportable']}/{len(c['points'])}")
        if c["control_saturates_before_target_at"]:
            add(f"{'':>8}   !! control saturates BEFORE target at dose(s) "
                f"{c['control_saturates_before_target_at']} -- not functioning as a control")
    add("  A refusal is a result, not a gap: where the control saturates the cell cannot")
    add("  discriminate target from control, so no contrast is defined.")
    add("")
    add(a["metric_semantics"])
    add("")
    status = ("COMPLETE / CLEAN" if a["is_complete"]
              else ("DEFECT" if a["defects"] else "INCOMPLETE (partial sweep)"))
    add(f"STATUS: {status}")
    return "\n".join(L)


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", type=Path,
                    default=REPO_ROOT / "results" / "gemma3_sweep" / "records.jsonl")
    ap.add_argument("--out-dir", type=Path,
                    default=REPO_ROOT / "results" / "gemma3_sweep" / "analysis")
    ap.add_argument("--manifest-dir", type=Path, default=None,
                    help="where to (re)write feature_manifest.json; defaults to --out-dir")
    ap.add_argument("--sweep-module", type=Path, default=SWEEP_MODULE_PATH)
    ap.add_argument("--include-optional-features", action="store_true",
                    help="pass include_optional=True to write_feature_manifest (manifest only; "
                         "does NOT change the pre-registered grid)")
    ap.add_argument("--seed", type=int, default=42,
                    help="recorded for provenance; this pipeline performs no sampling")
    ap.add_argument("--allow-partial", action="store_true",
                    help="exit 0 even when the grid is incomplete (banner is still printed)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    sweep = load_sweep_module(args.sweep_module)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = args.manifest_dir or args.out_dir
    manifest_path = sweep.write_feature_manifest(
        manifest_dir, include_optional=args.include_optional_features)

    load = load_records(args.records)
    a = analyze(load.records, sweep)
    a["seed"] = args.seed
    a["records_path"] = str(args.records)
    a["feature_manifest_path"] = str(manifest_path)
    a["load"] = load.as_dict()

    (args.out_dir / "sweep_analysis.json").write_text(
        json.dumps(a, indent=2, ensure_ascii=False), encoding="utf-8")
    report = render_report(a, load.as_dict(), manifest_path)
    (args.out_dir / "sweep_analysis_report.txt").write_text(report + "\n", encoding="utf-8")
    if not args.quiet:
        print(report)
        print(f"\nWROTE {args.out_dir / 'sweep_analysis.json'}")
        print(f"WROTE {args.out_dir / 'sweep_analysis_report.txt'}")

    if a["defects"]:
        return 2
    if a["n_cells_missing"] or load.malformed_lines:
        return 0 if args.allow_partial else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
