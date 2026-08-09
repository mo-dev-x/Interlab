"""Tests for the adjudication merge + composition instrument.

The synthetic ledger's composition is HAND-COMPUTED below, not snapshotted from
a run. A tally that agrees with itself proves nothing -- that is exactly how two
parses of the same files produced two different Gemma compositions without
either being detectably wrong.

Every refusal in the spec gets its own test: duplicate feature, feature outside
the pool, missing feature, unparseable class, class outside 1-12, parked row.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "merge_adjudication.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ma = _load("merge_adjudication", SCRIPT)

# --- synthetic pools: 40 per column, disjoint so a cross-column leak is visible
GEMMA_POOL = list(range(1000, 1040))
QWEN_POOL = list(range(2000, 2040))
POOLS = {"gemma": GEMMA_POOL, "qwen": QWEN_POOL}

# --- HAND-BUILT class assignment, 40 per column -------------------------------
# gemma: 12 surface-form, 15 semantic, 5 discourse, 4 indeterminate, 4 relational
#   classes 1,2,3,4  x3 each  = 12  -> surface-form
#   classes 5,6,7,8,11 x3 each = 15 -> semantic
#   class 9  x5 = 5             -> discourse-register
#   class 10 x4 = 4             -> indeterminate
#   class 12 x4 = 4             -> relational-positional
#   total 12+15+5+4+4 = 40
GEMMA_CLASSES = ([1] * 3 + [2] * 3 + [3] * 3 + [4] * 3
                 + [5] * 3 + [6] * 3 + [7] * 3 + [8] * 3 + [11] * 3
                 + [9] * 5 + [10] * 4 + [12] * 4)

# qwen: 20 surface-form, 10 semantic, 4 discourse, 3 indeterminate, 3 relational
#   classes 1,2,3,4 x5 each = 20; 5,6,7,8,11 x2 each = 10; 9 x4; 10 x3; 12 x3
QWEN_CLASSES = ([1] * 5 + [2] * 5 + [3] * 5 + [4] * 5
                + [5] * 2 + [6] * 2 + [7] * 2 + [8] * 2 + [11] * 2
                + [9] * 4 + [10] * 3 + [12] * 3)

EXPECTED_GEMMA = {"surface-form": 12, "semantic": 15, "discourse-register": 5,
                  "indeterminate": 4, "relational-positional": 4}
EXPECTED_QWEN = {"surface-form": 20, "semantic": 10, "discourse-register": 4,
                 "indeterminate": 3, "relational-positional": 3}


def _rows(pool, classes, column, rater="r1"):
    assert len(pool) == len(classes) == 40
    return [{"feature_idx": i, "column": column, "class": c, "rater": rater,
             "disposition": "classified"} for i, c in zip(pool, classes)]


def r1_records():
    recs = _rows(GEMMA_POOL, GEMMA_CLASSES, "gemma") + _rows(QWEN_POOL, QWEN_CLASSES, "qwen")
    return [dict(r, _source_file="r1.json", _source_index=i) for i, r in enumerate(recs)]


def r2_records(overlap=10, flip=0):
    """Rater 2's calibration overlap: first `overlap` gemma rows, with the first
    `flip` of them deliberately disagreeing."""
    out = []
    for k in range(overlap):
        cls = GEMMA_CLASSES[k]
        if k < flip:
            cls = 12 if cls != 12 else 10       # force a bucket-level disagreement
        out.append({"feature_idx": GEMMA_POOL[k], "column": "gemma", "class": cls,
                    "rater": "r2", "disposition": "classified",
                    "_source_file": "r2.json", "_source_index": k})
    return out


# ---------------------------------------------------------------------------
# bucket mapping
# ---------------------------------------------------------------------------

def test_bucket_mapping_is_exactly_the_spec():
    assert ma.BUCKET_OF_CLASS == {
        1: "surface-form", 2: "surface-form", 3: "surface-form", 4: "surface-form",
        5: "semantic", 6: "semantic", 7: "semantic", 8: "semantic", 11: "semantic",
        9: "discourse-register", 10: "indeterminate", 12: "relational-positional"}
    assert set(ma.BUCKET_OF_CLASS) == set(range(1, 13))


def test_composition_has_five_rows_and_class_12_is_its_own():
    assert ma.BUCKET_ROWS == ("surface-form", "semantic", "discourse-register",
                              "indeterminate", "relational-positional")
    assert len(ma.BUCKET_ROWS) == 5
    assert ma.BUCKET_OF_CLASS[12] not in ("discourse-register", "indeterminate")


# ---------------------------------------------------------------------------
# hand-computed composition
# ---------------------------------------------------------------------------

def test_composition_matches_hand_computed_counts():
    result = ma.merge(r1_records(), r2_records(), POOLS)
    for column, expected in (("gemma", EXPECTED_GEMMA), ("qwen", EXPECTED_QWEN)):
        comp = result["columns"][column]["composition"]
        got = {row["bucket"]: row["count"] for row in comp["rows"]}
        assert got == expected, f"{column} composition"
        assert comp["denominator"] == 40
        assert sum(got.values()) == 40


def test_fractions_are_exact():
    result = ma.merge(r1_records(), r2_records(), POOLS)
    rows = {r["bucket"]: r["fraction"] for r in
            result["columns"]["qwen"]["composition"]["rows"]}
    assert rows["surface-form"] == pytest.approx(20 / 40)
    assert rows["semantic"] == pytest.approx(10 / 40)
    assert rows["discourse-register"] == pytest.approx(4 / 40)
    assert rows["indeterminate"] == pytest.approx(3 / 40)
    assert rows["relational-positional"] == pytest.approx(3 / 40)


def test_surface_and_semantic_do_not_sum_to_one():
    """By construction, not by error."""
    result = ma.merge(r1_records(), r2_records(), POOLS)
    for column in ("gemma", "qwen"):
        rows = {r["bucket"]: r["fraction"] for r in
                result["columns"][column]["composition"]["rows"]}
        assert rows["surface-form"] + rows["semantic"] < 1.0


def test_class_counts_are_reported():
    result = ma.merge(r1_records(), r2_records(), POOLS)
    cc = result["columns"]["gemma"]["composition"]["class_counts"]
    assert cc["1"] == 3 and cc["9"] == 5 and cc["10"] == 4 and cc["12"] == 4
    assert sum(cc.values()) == 40


# ---------------------------------------------------------------------------
# MERGE RULE -- rater 2 never enters a tally
# ---------------------------------------------------------------------------

def test_rater2_calls_never_change_the_composition():
    """Rater 2 disagrees on all ten overlap rows; the composition must be
    byte-identical to the run where rater 2 agrees."""
    agree = ma.merge(r1_records(), r2_records(overlap=10, flip=0), POOLS)
    disagree = ma.merge(r1_records(), r2_records(overlap=10, flip=10), POOLS)
    assert (agree["columns"]["gemma"]["composition"]
            == disagree["columns"]["gemma"]["composition"])
    got = {r["bucket"]: r["count"] for r in
           disagree["columns"]["gemma"]["composition"]["rows"]}
    assert got == EXPECTED_GEMMA


def test_argument_order_cannot_swap_the_adjudicator():
    """Structural guard: compose() refuses anything but the adjudicator of record."""
    with pytest.raises(ma.RefusalError, match="adjudicator of record"):
        ma.compose({1000: 1}, "gemma", "r2")


def test_merged_rows_record_that_rater2_did_not_enter():
    result = ma.merge(r1_records(), r2_records(flip=10), POOLS)
    overlap_rows = [r for r in result["merged_ledger"] if r["rater2_in_overlap"]]
    assert len(overlap_rows) == 10
    assert all(r["source"] == "r1" for r in overlap_rows)
    assert all(r["rater2_entered_tally"] is False for r in overlap_rows)
    assert any(r["rater2_class"] != r["class"] for r in overlap_rows)


def test_agreement_is_computed_and_is_separate():
    result = ma.merge(r1_records(), r2_records(overlap=10, flip=4), POOLS)
    agr = result["columns"]["gemma"]["agreement"]
    assert agr["n_overlap"] == 10
    assert agr["exact_class_agreement"] == 6
    assert agr["exact_class_agreement_rate"] == pytest.approx(0.6)
    assert len(agr["disagreements"]) == 4


# ---------------------------------------------------------------------------
# REFUSALS -- one test each
# ---------------------------------------------------------------------------

def test_refuses_duplicate_feature_index():
    recs = r1_records()
    dup = dict(recs[0])
    dup["_source_index"] = 999
    recs.append(dup)
    with pytest.raises(ma.RefusalError, match="DUPLICATE"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_feature_outside_the_pool():
    recs = r1_records()
    recs[0] = dict(recs[0], feature_idx=9999999)
    with pytest.raises(ma.RefusalError, match="OUTSIDE"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_cross_column_leak():
    """A qwen index appearing in the gemma column is outside gemma's pool."""
    recs = r1_records()
    recs[0] = dict(recs[0], feature_idx=QWEN_POOL[0])
    with pytest.raises(ma.RefusalError, match="OUTSIDE the verified gemma pool"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_missing_feature():
    recs = [r for r in r1_records() if r["feature_idx"] != GEMMA_POOL[7]]
    with pytest.raises(ma.RefusalError, match="MISSING"):
        ma.merge(recs, r2_records(), POOLS)


@pytest.mark.parametrize("bad", ["surface-form", "", "3.5", "class 3", None, [3], 3.0])
def test_refuses_unparseable_class(bad):
    recs = r1_records()
    recs[0] = dict(recs[0], **{"class": bad})
    with pytest.raises(ma.RefusalError, match="unparseable class"):
        ma.merge(recs, r2_records(), POOLS)


@pytest.mark.parametrize("bad", [0, 13, -1, 99])
def test_refuses_class_outside_1_to_12(bad):
    recs = r1_records()
    recs[0] = dict(recs[0], **{"class": bad})
    with pytest.raises(ma.RefusalError, match="outside the valid range"):
        ma.merge(recs, r2_records(), POOLS)


def test_string_integer_class_is_accepted():
    """'7' is unambiguous; only genuinely unparseable values refuse."""
    recs = r1_records()
    original = recs[0]["class"]
    recs[0] = dict(recs[0], **{"class": str(original)})
    result = ma.merge(recs, r2_records(), POOLS)
    got = {r["bucket"]: r["count"] for r in
           result["columns"]["gemma"]["composition"]["rows"]}
    assert got == EXPECTED_GEMMA


@pytest.mark.parametrize("field,value", [("disposition", "parked"),
                                         ("disposition", "PARKED"),
                                         ("parked", True)])
def test_refuses_parked_row(field, value):
    recs = r1_records()
    recs[0] = dict(recs[0], **{field: value})
    with pytest.raises(ma.RefusalError, match="PARKED"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_bucket_disagreeing_with_class():
    """A prose bucket field must never silently override the derived bucket."""
    recs = r1_records()
    recs[0] = dict(recs[0], **{"class": 1, "bucket": "semantic"})
    with pytest.raises(ma.RefusalError, match="derives"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_non_integer_feature_idx():
    recs = r1_records()
    recs[0] = dict(recs[0], feature_idx="1000")
    with pytest.raises(ma.RefusalError, match="not an integer"):
        ma.merge(recs, r2_records(), POOLS)


def test_refuses_parked_rater2_row():
    with pytest.raises(ma.RefusalError, match="PARKED"):
        ma.merge(r1_records(),
                 [dict(r2_records()[0], disposition="parked")], POOLS)


def test_all_defects_are_collected_not_just_the_first():
    recs = r1_records()
    recs[0] = dict(recs[0], **{"class": 99})
    recs[1] = dict(recs[1], feature_idx=9999999)
    with pytest.raises(ma.RefusalError) as exc:
        ma.merge(recs, r2_records(), POOLS)
    msg = str(exc.value)
    assert "outside the valid range" in msg and "OUTSIDE" in msg


# ---------------------------------------------------------------------------
# pool derivation from evidence
# ---------------------------------------------------------------------------

def test_gemma_pool_is_derived_from_evidence_not_a_literal():
    """Real evidence: 49 raw captures minus the 9 sweep features = 40."""
    pool = ma.derive_gemma_pool()
    assert len(pool) == 40
    assert len(set(pool)) == 40
    sweep = ma._load_sweep_module()
    assert not (set(pool) & {f["idx"] for f in sweep.FEATURES}), \
        "sweep features must be excluded from the pool"


def test_gemma_pool_refuses_when_evidence_dir_is_wrong_size(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    for i in range(5):
        (d / f"{i}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ma.RefusalError, match="sweep features absent"):
        ma.derive_gemma_pool(d)


def test_gemma_pool_refuses_non_numeric_filenames(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    (d / "notanumber.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ma.RefusalError, match="non-numeric"):
        ma.derive_gemma_pool(d)


def test_qwen_pool_requires_forty(tmp_path):
    p = tmp_path / "sel.json"
    p.write_text(json.dumps({"primary_40": [1, 2, 3]}), encoding="utf-8")
    with pytest.raises(ma.RefusalError, match="expected 40"):
        ma.derive_qwen_pool(p)


def test_missing_ledger_file_refuses(tmp_path):
    with pytest.raises(ma.RefusalError, match="not found"):
        ma.read_canonical_ledger(tmp_path / "nope.json", "r1")


def test_malformed_ledger_json_refuses(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ma.RefusalError, match="not valid JSON"):
        ma.read_canonical_ledger(p, "r1")


# ---------------------------------------------------------------------------
# end-to-end via main(), on synthetic files only
# ---------------------------------------------------------------------------

def _write_ledgers(tmp_path, r1_recs, r2_recs):
    strip = lambda rs: [{k: v for k, v in r.items() if not k.startswith("_")} for r in rs]
    p1 = tmp_path / "r1.canonical.json"
    p2 = tmp_path / "r2.canonical.json"
    p1.write_text(json.dumps({"records": strip(r1_recs)}), encoding="utf-8")
    p2.write_text(json.dumps({"records": strip(r2_recs)}), encoding="utf-8")
    return p1, p2


def test_main_exits_0_and_writes_merged_output(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "derive_gemma_pool", lambda *a, **k: GEMMA_POOL)
    monkeypatch.setattr(ma, "derive_qwen_pool", lambda *a, **k: QWEN_POOL)
    p1, p2 = _write_ledgers(tmp_path, r1_records(), r2_records())
    out = tmp_path / "merged.json"
    rc = ma.main(["--r1", str(p1), "--r2", str(p2), "--out", str(out), "--quiet"])
    assert rc == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    got = {r["bucket"]: r["count"] for r in
           result["columns"]["gemma"]["composition"]["rows"]}
    assert got == EXPECTED_GEMMA
    assert len(result["merged_ledger"]) == 80


def test_main_exits_2_and_writes_nothing_on_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "derive_gemma_pool", lambda *a, **k: GEMMA_POOL)
    monkeypatch.setattr(ma, "derive_qwen_pool", lambda *a, **k: QWEN_POOL)
    recs = r1_records()
    recs[0] = dict(recs[0], **{"class": 13})
    p1, p2 = _write_ledgers(tmp_path, recs, r2_records())
    out = tmp_path / "merged.json"
    rc = ma.main(["--r1", str(p1), "--r2", str(p2), "--out", str(out), "--quiet"])
    assert rc == 2
    assert not out.exists(), "a refused run must not leave a composition on disk"
