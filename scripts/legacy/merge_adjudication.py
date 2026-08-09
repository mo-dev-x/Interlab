#!/usr/bin/env python
"""Adjudication merge + composition instrument (prereg v1.16 SS16.1/SS16.2).

Two successive parses of the same two prose ledgers returned two different Gemma
compositions. A number whose instrument has not been validated is not a number,
so this replaces prose parsing entirely: it reads canonical machine-readable
ledgers, one record per feature with fixed fields and no free text in any field
the tally reads.

IT REFUSES TO PROCEED RATHER THAN TALLYING WHAT IT CAN READ.
Every one of these halts the run with a non-zero exit and no composition:
  * a duplicate feature index within a rater/column
  * a feature outside its column's verified pool
  * a missing feature (each column must be EXACTLY 40)
  * an unparseable class
  * a class outside 1-12
  * a null class on any row whose disposition is not `parked`
  * a parked row in the ADJUDICATOR OF RECORD's file (SS11.2: an unresolved park
    voids the tally for its column)

A PARKED ROW IN THE RELIABILITY RATER'S FILE DOES NOT REFUSE (SS16.4). Rater 2's
rows never enter a tally and the adjudicator of record has a call on that
feature, so the column is still complete. The feature is instead EXCLUDED FROM
THE AGREEMENT DENOMINATOR, and both the exclusion count and the excluded feature
indices appear in the output: agreement is reported over nine of ten, never over
ten, and never silently over nine.

POOLS ARE VERIFIED FROM EVIDENCE, NOT FROM A LIST IN A DOCUMENT.
The Gemma pool is derived by scanning scripts/legacy/gemma_neuronpedia_raw/ and
removing the nine sweep features imported from the sweep harness itself. The
Qwen pool is read from the seeded-draw selection record. A pool transcribed into
this file would be exactly the unvalidated instrument this exists to replace.

MERGE RULE (SS16.2, decided before any tally existed).
Rater 1 is the adjudicator of record and adjudicated all 40 rows in both
columns, so THE COMPOSITION IS RATER 1'S CALLS THROUGHOUT. Rater 2's overlap
rows NEVER enter a tally; they feed a separate agreement computation only. This
is asserted structurally -- the tally function is only ever handed rater 1's
records, and a guard re-checks provenance before counting -- not left to
argument order, because argument order is what silently swapped ten of forty
rows in the first place.

BUCKET MAPPING -- fixed, derived from the class NUMBER. Any prose bucket field
present in the input is ignored, and disagreement with it is reported as a
defect rather than silently resolved.
    1,2,3,4      -> surface-form
    5,6,7,8,11   -> semantic
    9            -> discourse-register
    10           -> indeterminate
    12           -> relational-positional

The composition is FIVE rows, not four. Class 12 gets its own reporting row:
collapsing it into discourse-register or indeterminate would misreport what
those counts mean. surface-form and semantic do not sum to one, by construction.

EXIT CODES
    0  merged and tallied
    2  refused -- one or more defects (no composition emitted)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
GEMMA_RAW_DIR = REPO_ROOT / "scripts" / "legacy" / "gemma_neuronpedia_raw"
SWEEP_MODULE_PATH = REPO_ROOT / "scripts" / "legacy" / "gemma3_sweep.py"
QWEN_SELECTION_PATH = (REPO_ROOT / "results" / "characterize_lite"
                       / "rwu04lpb_taxonomy40" / "feature_selection.json")

POOL_SIZE = 40
VALID_CLASSES = frozenset(range(1, 13))

BUCKET_OF_CLASS: dict[int, str] = {
    1: "surface-form", 2: "surface-form", 3: "surface-form", 4: "surface-form",
    5: "semantic", 6: "semantic", 7: "semantic", 8: "semantic", 11: "semantic",
    9: "discourse-register",
    10: "indeterminate",
    12: "relational-positional",
}
# Fixed reporting order. Five rows.
BUCKET_ROWS = ("surface-form", "semantic", "discourse-register",
               "indeterminate", "relational-positional")

ADJUDICATOR_OF_RECORD = "r1"
COLUMNS = ("gemma", "qwen")


class RefusalError(Exception):
    """Raised when the instrument must not produce a composition."""


# ---------------------------------------------------------------------------
# pools, verified from evidence
# ---------------------------------------------------------------------------

def _load_sweep_module(path: Path = SWEEP_MODULE_PATH):
    spec = importlib.util.spec_from_file_location("gemma3_sweep_for_pool", path)
    if spec is None or spec.loader is None:
        raise RefusalError(f"cannot load sweep harness from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_gemma_pool(raw_dir: Path = GEMMA_RAW_DIR,
                      sweep_module_path: Path = SWEEP_MODULE_PATH) -> list[int]:
    """Gemma pool = every feature index with a Neuronpedia raw capture, minus the
    nine sweep features. Both sides come from evidence: the filenames on disk and
    the sweep harness's own FEATURES constant."""
    if not raw_dir.is_dir():
        raise RefusalError(f"gemma pool evidence directory not found: {raw_dir}")
    captured: set[int] = set()
    bad: list[str] = []
    for p in sorted(raw_dir.glob("*.json")):
        try:
            captured.add(int(p.stem))
        except ValueError:
            bad.append(p.name)
    if bad:
        raise RefusalError(
            f"non-numeric filenames in the gemma pool evidence directory: {bad}")
    sweep = _load_sweep_module(sweep_module_path)
    sweep_idxs = {f["idx"] for f in sweep.FEATURES}
    missing_sweep = sorted(sweep_idxs - captured)
    if missing_sweep:
        raise RefusalError(
            f"sweep features absent from the raw capture directory, so the "
            f"subtraction is not evidence-backed: {missing_sweep}")
    pool = sorted(captured - sweep_idxs)
    if len(pool) != POOL_SIZE:
        raise RefusalError(
            f"gemma pool derived from evidence has {len(pool)} features, expected "
            f"{POOL_SIZE} ({len(captured)} captured minus {len(sweep_idxs)} sweep). "
            f"The pool is not what the design says it is; refusing.")
    return pool


def derive_qwen_pool(selection_path: Path = QWEN_SELECTION_PATH) -> list[int]:
    """Qwen pool = the seeded uniform draw's primary 40, read from the selection
    record written before the characterization run."""
    if not selection_path.exists():
        raise RefusalError(f"qwen pool evidence not found: {selection_path}")
    try:
        sel = json.loads(selection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RefusalError(f"qwen pool evidence is not valid JSON: {exc}") from exc
    pool = sel.get("primary_40")
    if not isinstance(pool, list) or not all(isinstance(x, int) for x in pool):
        raise RefusalError("qwen pool evidence has no integer 'primary_40' list")
    if len(set(pool)) != POOL_SIZE:
        raise RefusalError(
            f"qwen pool has {len(set(pool))} distinct features, expected {POOL_SIZE}")
    return sorted(pool)


# ---------------------------------------------------------------------------
# canonical ledger reading
# ---------------------------------------------------------------------------

def _coerce_class(value: Any, where: str, defects: list[str]) -> int | None:
    """A class must be an integer, or a string that is exactly an integer. A
    float, a range, a bare word, or anything needing interpretation is
    unparseable -- and unparseable halts the run."""
    if isinstance(value, bool):
        defects.append(f"{where}: class is a boolean ({value!r}), unparseable")
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        parsed = int(value.strip())
    else:
        defects.append(f"{where}: unparseable class {value!r}")
        return None
    if parsed not in VALID_CLASSES:
        defects.append(f"{where}: class {parsed} outside the valid range 1-12")
        return None
    return parsed


def _is_parked(record: dict[str, Any]) -> bool:
    disposition = record.get("disposition")
    if isinstance(disposition, str) and disposition.strip().lower() == "parked":
        return True
    return bool(record.get("parked"))


def _null_class_defect(record: dict[str, Any], where: str) -> str | None:
    """`class: null` is permitted ONLY on a parked row (SS16.4 schema). On any
    other disposition a null class is a missing call wearing a valid-looking
    field, so it refuses."""
    if record.get("class") is not None:
        return None
    if _is_parked(record):
        return None
    return (f"{where}: class is null but disposition is "
            f"{record.get('disposition')!r} -- a null class is permitted only on "
            f"a parked row")


def read_canonical_ledger(path: Path, rater: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise RefusalError(f"canonical ledger not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RefusalError(f"{path.name} is not valid JSON: {exc}") from exc
    records = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise RefusalError(
            f"{path.name}: expected a list of records, or an object with a "
            f"'records' list")
    out = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise RefusalError(f"{path.name} record {i}: not an object")
        r = dict(r)
        r.setdefault("rater", rater)
        r["_source_file"] = path.name
        r["_source_index"] = i
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# validation -- every check below is a refusal, never a warning
# ---------------------------------------------------------------------------

def validate_column(records: list[dict[str, Any]], column: str, pool: list[int],
                    rater: str) -> tuple[dict[int, int], list[str]]:
    """Returns (feature_idx -> class) for the column, plus defects. A non-empty
    defect list means no composition may be computed for this column."""
    defects: list[str] = []
    pool_set = set(pool)

    rows = [r for r in records if r.get("column") == column and r.get("rater") == rater]

    seen: dict[int, int] = {}
    idx_counts: Counter = Counter()
    for r in rows:
        where = f"{r['_source_file']}[{r['_source_index']}] column={column}"
        raw_idx = r.get("feature_idx")
        if isinstance(raw_idx, bool) or not isinstance(raw_idx, int):
            defects.append(f"{where}: feature_idx {raw_idx!r} is not an integer")
            continue
        idx_counts[raw_idx] += 1

        if _is_parked(r):
            defects.append(
                f"{where}: feature {raw_idx} is still PARKED -- an unresolved park "
                f"voids the tally for its column (SS11.2)")
            continue
        if raw_idx not in pool_set:
            defects.append(
                f"{where}: feature {raw_idx} is OUTSIDE the verified {column} pool")
            continue
        null_defect = _null_class_defect(r, f"{where} feature {raw_idx}")
        if null_defect:
            defects.append(null_defect)
            continue
        cls = _coerce_class(r.get("class"), f"{where} feature {raw_idx}", defects)
        if cls is None:
            continue

        stated_bucket = r.get("bucket")
        derived = BUCKET_OF_CLASS[cls]
        if isinstance(stated_bucket, str) and stated_bucket.strip() and \
                stated_bucket.strip() != derived:
            defects.append(
                f"{where}: feature {raw_idx} states bucket {stated_bucket!r} but class "
                f"{cls} derives {derived!r}. The bucket is derived from the class "
                f"number; refusing to silently resolve the disagreement.")
            continue
        seen[raw_idx] = cls

    for idx, n in sorted(idx_counts.items()):
        if n > 1:
            defects.append(
                f"column={column} rater={rater}: DUPLICATE feature index {idx} appears "
                f"{n} times")

    if not defects:
        missing = sorted(pool_set - set(seen))
        if missing:
            defects.append(
                f"column={column}: MISSING {len(missing)} feature(s) -- the column must "
                f"be exactly {POOL_SIZE}: {missing}")
        if len(seen) != POOL_SIZE:
            defects.append(
                f"column={column}: {len(seen)} classified rows, expected exactly "
                f"{POOL_SIZE}")
    return seen, defects


# ---------------------------------------------------------------------------
# composition + agreement
# ---------------------------------------------------------------------------

def compose(calls: dict[int, int], column: str, provenance_rater: str) -> dict[str, Any]:
    """Five-row composition. Refuses if handed anything but the adjudicator of
    record -- structural, so argument order cannot decide whose calls count."""
    if provenance_rater != ADJUDICATOR_OF_RECORD:
        raise RefusalError(
            f"compose() was handed rater {provenance_rater!r}; only "
            f"{ADJUDICATOR_OF_RECORD!r} is the adjudicator of record (SS16.2). "
            f"Rater 2's calls never enter a tally.")
    n = len(calls)
    bucket_counts = Counter(BUCKET_OF_CLASS[c] for c in calls.values())
    class_counts = Counter(calls.values())
    rows = []
    for bucket in BUCKET_ROWS:
        count = bucket_counts.get(bucket, 0)
        rows.append({
            "bucket": bucket,
            "count": count,
            "fraction": round(count / n, 6) if n else None,
        })
    return {
        "column": column,
        "adjudicator_of_record": provenance_rater,
        "denominator": n,
        "rows": rows,
        "class_counts": {str(c): class_counts.get(c, 0) for c in sorted(VALID_CLASSES)},
        "note": ("Five rows. Class 12 is reported separately; collapsing it into "
                 "discourse-register or indeterminate would misreport those counts. "
                 "surface-form and semantic do not sum to 1 by construction."),
    }


def agreement(r1_calls: dict[int, int], r2_calls: dict[int, int], column: str,
              parked_excluded: list[int] | None = None) -> dict[str, Any]:
    """Reliability only. These rows never enter a tally.

    SS16.4: a parked rater-2 row is EXCLUDED from the denominator rather than
    refusing the column. The exclusion is reported explicitly -- both the count
    and the feature indices -- so the rate is never read as though it were over
    the full overlap, and never silently over the reduced one."""
    parked_excluded = sorted(parked_excluded or [])
    overlap = sorted(set(r1_calls) & set(r2_calls))
    exact = [i for i in overlap if r1_calls[i] == r2_calls[i]]
    bucket_same = [i for i in overlap
                   if BUCKET_OF_CLASS[r1_calls[i]] == BUCKET_OF_CLASS[r2_calls[i]]]
    return {
        "column": column,
        "n_overlap_candidates": len(overlap) + len(parked_excluded),
        "n_excluded_parked": len(parked_excluded),
        "excluded_parked_features": parked_excluded,
        "denominator_note": (
            f"agreement computed over {len(overlap)} of "
            f"{len(overlap) + len(parked_excluded)} candidate overlap rows; "
            f"{len(parked_excluded)} excluded as parked in the reliability "
            f"rater's file (SS16.4)"),
        "n_overlap": len(overlap),
        "overlap_features": overlap,
        "exact_class_agreement": len(exact),
        "exact_class_agreement_rate": round(len(exact) / len(overlap), 6) if overlap else None,
        "bucket_agreement": len(bucket_same),
        "bucket_agreement_rate": round(len(bucket_same) / len(overlap), 6) if overlap else None,
        "disagreements": [
            {"feature_idx": i, "r1_class": r1_calls[i], "r2_class": r2_calls[i],
             "r1_bucket": BUCKET_OF_CLASS[r1_calls[i]],
             "r2_bucket": BUCKET_OF_CLASS[r2_calls[i]]}
            for i in overlap if r1_calls[i] != r2_calls[i]
        ],
        "note": ("Reliability arm only. Per SS16.2 rater 2's calls never enter a "
                 "composition; letting them override on the overlap would make the "
                 "composition partly a function of which rows were drawn for "
                 "calibration."),
    }


def merge(r1_records: list[dict[str, Any]], r2_records: list[dict[str, Any]],
          pools: dict[str, list[int]]) -> dict[str, Any]:
    defects: list[str] = []
    per_column: dict[str, Any] = {}
    r1_by_col: dict[str, dict[int, int]] = {}
    r2_by_col: dict[str, dict[int, int]] = {}
    r2_parked_by_col: dict[str, list[int]] = {}

    for column in COLUMNS:
        pool = pools[column]
        r1_calls, d1 = validate_column(r1_records, column, pool, "r1")
        defects.extend(d1)
        r1_by_col[column] = r1_calls
        # rater 2 is validated for parseability and pool membership, but is NOT
        # required to be complete -- it is an overlap sample by design.
        r2_calls: dict[int, int] = {}
        r2_parked: list[int] = []
        for r in [x for x in r2_records if x.get("column") == column
                  and x.get("rater") == "r2"]:
            where = f"{r['_source_file']}[{r['_source_index']}] column={column}"
            idx = r.get("feature_idx")
            if isinstance(idx, bool) or not isinstance(idx, int):
                defects.append(f"{where}: feature_idx {idx!r} is not an integer")
                continue
            if idx not in set(pool):
                defects.append(
                    f"{where}: rater 2 feature {idx} is OUTSIDE the verified "
                    f"{column} pool")
                continue
            if idx in r2_calls or idx in r2_parked:
                defects.append(
                    f"column={column} rater=r2: DUPLICATE feature index {idx}")
                continue
            if _is_parked(r):
                # SS16.4: does NOT refuse. The adjudicator of record has a call on
                # this feature, so the column is complete; only the reliability
                # denominator shrinks, and the exclusion is reported.
                r2_parked.append(idx)
                continue
            null_defect = _null_class_defect(r, f"{where} feature {idx}")
            if null_defect:
                defects.append(null_defect)
                continue
            cls = _coerce_class(r.get("class"), f"{where} feature {idx}", defects)
            if cls is not None:
                r2_calls[idx] = cls
        r2_by_col[column] = r2_calls
        r2_parked_by_col[column] = r2_parked

    if defects:
        raise RefusalError("\n".join(defects))

    merged_rows = []
    for column in COLUMNS:
        per_column[column] = {
            "composition": compose(r1_by_col[column], column, ADJUDICATOR_OF_RECORD),
            "agreement": agreement(r1_by_col[column], r2_by_col[column], column,
                                   r2_parked_by_col[column]),
        }
        for idx in sorted(r1_by_col[column]):
            cls = r1_by_col[column][idx]
            merged_rows.append({
                "column": column,
                "feature_idx": idx,
                "class": cls,
                "bucket": BUCKET_OF_CLASS[cls],
                "source": ADJUDICATOR_OF_RECORD,
                "rater2_class": r2_by_col[column].get(idx),
                "rater2_in_overlap": idx in r2_by_col[column],
                "rater2_parked": idx in r2_parked_by_col[column],
                "rater2_entered_tally": False,
            })

    return {
        "instrument": "merge_adjudication.py (prereg v1.16 SS16.1/SS16.2)",
        "adjudicator_of_record": ADJUDICATOR_OF_RECORD,
        "merge_rule": ("Composition is rater 1's calls throughout. Rater 2's overlap "
                       "rows feed the agreement computation only and never enter a tally."),
        "bucket_mapping": {str(k): v for k, v in sorted(BUCKET_OF_CLASS.items())},
        "bucket_rows": list(BUCKET_ROWS),
        "pools": {c: pools[c] for c in COLUMNS},
        "columns": per_column,
        "merged_ledger": merged_rows,
    }


# ---------------------------------------------------------------------------

def render(result: dict[str, Any]) -> str:
    L = ["=" * 74, "ADJUDICATION MERGE + COMPOSITION", "=" * 74,
         f"adjudicator of record : {result['adjudicator_of_record']}",
         f"merge rule            : {result['merge_rule']}", ""]
    for column in COLUMNS:
        comp = result["columns"][column]["composition"]
        agr = result["columns"][column]["agreement"]
        L.append("-" * 74)
        L.append(f"COLUMN: {column}   denominator {comp['denominator']}")
        L.append("-" * 74)
        for row in comp["rows"]:
            frac = "" if row["fraction"] is None else f"{row['fraction']:.4f}"
            L.append(f"  {row['bucket']:<24} {row['count']:>4}   {frac}")
        L.append(f"  (five rows; surface-form + semantic do not sum to 1 by construction)")
        L.append(f"  agreement arm: {agr['exact_class_agreement']} exact / "
                 f"{agr['bucket_agreement']} bucket, over {agr['n_overlap']} of "
                 f"{agr['n_overlap_candidates']} candidate overlap rows "
                 f"-- NOT in any tally")
        if agr["n_excluded_parked"]:
            L.append(f"  EXCLUDED from the agreement denominator as parked in the "
                     f"reliability rater's file: {agr['n_excluded_parked']} "
                     f"feature(s) {agr['excluded_parked_features']}")
        L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--r1", type=Path,
                    default=REPO_ROOT / "reports" / "adjudication_ledger_r1.canonical.json")
    ap.add_argument("--r2", type=Path,
                    default=REPO_ROOT / "reports" / "adjudication_ledger_r2.canonical.json")
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "reports" / "adjudication_merged.json")
    ap.add_argument("--gemma-raw-dir", type=Path, default=GEMMA_RAW_DIR)
    ap.add_argument("--qwen-selection", type=Path, default=QWEN_SELECTION_PATH)
    ap.add_argument("--sweep-module", type=Path, default=SWEEP_MODULE_PATH)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        pools = {
            "gemma": derive_gemma_pool(args.gemma_raw_dir, args.sweep_module),
            "qwen": derive_qwen_pool(args.qwen_selection),
        }
        result = merge(read_canonical_ledger(args.r1, "r1"),
                       read_canonical_ledger(args.r2, "r2"), pools)
    except RefusalError as exc:
        print("REFUSED -- no composition computed.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.quiet:
        print(render(result))
        print(f"WROTE {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
