#!/usr/bin/env python3
"""DISCRIMINATION HARNESS for the corpus-implements-definition instrument.

A conformance instrument that cannot FAIL is worthless, and one that cannot
PASS is equally so.  This harness builds SYNTHETIC corpora in a temporary
directory, each carrying exactly one injected defect, and asserts that the
instrument flags it.  It also builds two POSITIVE CONTROLS -- corpora in which
a currently-failing check is repaired -- and asserts that the instrument then
PASSES that check, so no check is a constant.

THE REAL CORPUS IS NEVER MUTATED.  Every fixture is written into a temp
directory obtained from tempfile; the real bytes are read out of git blobs at
a pinned rev and are never opened for writing.

Run:
    python conformance/final_pairing/v2/discrimination_fixtures.py

Exit 0 if every fixture behaved as required, 1 otherwise.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

spec = importlib.util.spec_from_file_location(
    "cid_instrument", HERE / "corpus_implements_definition.py"
)
INST = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(INST)


def git_blob(rev: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO), "show", f"{rev}:{path}"],
        capture_output=True, check=True
    ).stdout


def dump_jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


# ---------------------------------------------------------------------------
# Mutations.  Each takes (description_dict, rows, metadata_dict) and returns
# the mutated triple.  Exactly one defect per fixture.
# ---------------------------------------------------------------------------


def _find(rows, **kw):
    for i, r in enumerate(rows):
        if all(r.get(k) == v for k, v in kw.items()):
            return i, r
    raise LookupError(kw)


def m01_wrong_count(d, rows, meta):
    """Drop one positive row: the frozen per-split count is now 29."""
    i, _ = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="positive", family="f1", ordinal=2)
    return d, rows[:i] + rows[i + 1:], meta


def m02_broken_near_miss_byte_identity(d, rows, meta):
    """Re-author one near_miss row so it is no longer the mirror's positive."""
    i, r = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="near_miss", ordinal=1)
    rows[i] = dict(r, text=r["text"].replace("China", "China itself", 1) + " Indeed.")
    return d, rows, meta


def m03_positive_missing_its_nation(d, rows, meta):
    """Strip the nation's own name from one positive, at a NON-mirror slot so
    the near-miss byte-identity check is not disturbed and C-009 is isolated."""
    i, r = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="positive", family="f1", ordinal=2)
    t = r["text"]
    for name in ("United States", "Americans", "American", "America"):
        t = t.replace(name, "our country")
    rows[i] = dict(r, text=t)
    return d, rows, meta


def m04_misjoined_prompt_id(d, rows, meta):
    """A prompt_id that no longer names the row it is attached to."""
    i, r = _find(rows, concept_id="pro_chinese_exceptionalism", locale="fr",
                 split="positive", family="f3", ordinal=7)
    rows[i] = dict(r, prompt_id="C01.EN.POS.F1.01")
    return d, rows, meta


def m05_near_miss_of_points_at_own_concept(d, rows, meta):
    """v1's semantics injected into v2 -- the silent mis-join, materialised."""
    for i, r in enumerate(rows):
        if r["split"] == "near_miss":
            rows[i] = dict(r, near_miss_of=r["concept_id"])
    return d, rows, meta


def m06_vacuous_mirror(d, rows, meta):
    """Make one concept's positive at a mirror slot identical to the string it
    already holds as a near_miss -- falsifier_2, WITHIN a concept."""
    _, nm = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                  split="near_miss", ordinal=1)
    i, p = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="positive", family="f1", ordinal=2)
    rows[i] = dict(p, text=nm["text"])
    return d, rows, meta


def m07_shared_split_diverges(d, rows, meta):
    """unrelated is declared IDENTICAL between the concepts; break that."""
    i, r = _find(rows, concept_id="pro_chinese_exceptionalism", locale="en",
                 split="unrelated", ordinal=3)
    rows[i] = dict(r, text=r["text"] + " Also, remember to rinse it twice.")
    return d, rows, meta


def m08_national_referent_in_neutral(d, rows, meta):
    """heldout_neutral must carry no national referent."""
    for c in ("pro_american_exceptionalism", "pro_chinese_exceptionalism"):
        i, r = _find(rows, concept_id=c, locale="en", split="heldout_neutral", ordinal=4)
        rows[i] = dict(r, text=r["text"] + " Mention Japan if it helps.")
    return d, rows, meta


def m09_length_parity_break(d, rows, meta):
    """One side of a slot pair written far longer than the other."""
    i, r = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="positive", family="f1", ordinal=4)
    rows[i] = dict(r, text=r["text"] + " " + ("It is so, and it remains so. " * 8))
    return d, rows, meta


def m10_description_digest_drift(d, rows, meta):
    """The frozen description is not the frozen description."""
    d = copy.deepcopy(d)
    d["authored_utc"] = "2099-01-01"
    return d, rows, meta


def m11_metadata_drifts_from_description(d, rows, meta):
    """metadata restates a count the description does not state."""
    meta = copy.deepcopy(meta)
    meta["expected_counts_per_concept_per_locale"]["positive"] = 32
    return d, rows, meta


def m12_shared_strings_absent(d, rows, meta):
    """Every near_miss re-authored: the 60 cross-pair shared strings VANISH.
    C-008 must FAIL on ABSENCE.  This is the inverse of the architect's
    correction -- presence is correct, absence is the defect."""
    for i, r in enumerate(rows):
        if r["split"] == "near_miss":
            rows[i] = dict(r, text=r["text"] + " (control)")
    return d, rows, meta


# --- POSITIVE CONTROLS: repair a currently-failing check --------------------


def p01_version_qualified_ids(d, rows, meta):
    """Give v2 rows a version-qualified prompt_id. CV-001 must then PASS."""
    for i, r in enumerate(rows):
        rows[i] = dict(r, prompt_id="V2." + r["prompt_id"])
    return d, rows, meta


def p02_metadata_declares_semantics(d, rows, meta):
    """Add the near_miss_of semantic tag. M-002 must then PASS."""
    meta = copy.deepcopy(meta)
    meta["near_miss_of_semantics"] = {"value": "mirror_concept"}
    return d, rows, meta


# ---------------------------------------------------------------------------
# fixture id -> (mutation, checks that MUST become FAIL, checks that MUST be PASS)
# ---------------------------------------------------------------------------

FIXTURES: list[tuple[str, str, Callable, list[str], list[str]]] = [
    ("M01", "wrong per-split count", m01_wrong_count, ["C-001", "C-002", "C-003"], []),
    ("M02", "broken near-miss byte identity", m02_broken_near_miss_byte_identity,
     ["C-005", "C-006", "C-008"], []),
    ("M03", "positive missing its own nation", m03_positive_missing_its_nation,
     ["C-009"], ["C-005", "C-002"]),
    ("M04", "mis-joined prompt_id", m04_misjoined_prompt_id, ["C-022"], ["C-002"]),
    ("M05", "near_miss_of carries v1 semantics inside v2",
     m05_near_miss_of_points_at_own_concept, ["C-023"], ["C-005"]),
    ("M06", "vacuous mirror: positive == own near_miss", m06_vacuous_mirror,
     ["C-007"], []),
    ("M07", "shared split diverges between concepts", m07_shared_split_diverges,
     ["C-011"], []),
    ("M08", "national referent leaks into heldout_neutral",
     m08_national_referent_in_neutral, ["C-012"], ["C-011"]),
    ("M09", "length parity broken at a slot", m09_length_parity_break,
     ["C-015"], ["C-005"]),
    ("M10", "frozen description digest drifts", m10_description_digest_drift,
     ["D-001"], []),
    ("M11", "metadata drifts from the description",
     m11_metadata_drifts_from_description, ["M-001"], ["C-002"]),
    ("M12", "the 60 cross-pair shared strings are ABSENT", m12_shared_strings_absent,
     ["C-008", "C-005"], []),
]

POSITIVE_CONTROLS: list[tuple[str, str, Callable, list[str]]] = [
    ("P01", "version-qualified prompt_ids repair the cross-version collision",
     p01_version_qualified_ids, ["CV-001"]),
    ("P02", "metadata declaring near_miss_of semantics repairs the missing tag",
     p02_metadata_declares_semantics, ["M-002"]),
]


def run_instrument(tmp: Path, tag: str, d, rows, meta, no_v1: bool = False,
                   raw_desc: bytes | None = None, raw_meta: bytes | None = None,
                   orig_desc=None, orig_meta=None) -> dict:
    """Write the fixture and run the instrument over it.

    An UNMUTATED description or metadata is written back as its ORIGINAL BYTES,
    not re-serialised.  Otherwise D-001 would fire on every fixture -- correctly,
    since a re-serialised frozen artifact is not the frozen artifact, but the
    finding would be about this harness rather than about the injected defect.
    """
    dp = tmp / f"{tag}_description.json"
    cp = tmp / f"{tag}_corpus.jsonl"
    mp = tmp / f"{tag}_metadata.json"
    op = tmp / f"{tag}_report.json"
    if raw_desc is not None and orig_desc is not None and d == orig_desc:
        dp.write_bytes(raw_desc)
    else:
        dp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    if raw_meta is not None and orig_meta is not None and meta == orig_meta:
        mp.write_bytes(raw_meta)
    else:
        mp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    cp.write_text(dump_jsonl(rows), encoding="utf-8")
    argv = ["--description", str(dp), "--corpus", str(cp), "--metadata", str(mp),
            "--json-out", str(op), "--quiet"]
    if no_v1:
        argv.append("--no-v1")
    INST.main(argv)
    return json.loads(op.read_text(encoding="utf-8"))


def status_map(report: dict) -> dict[str, str]:
    return {c["id"]: c["status"] for c in report["checks"]}


def main() -> int:
    raw_desc = git_blob(INST.DESCRIPTION_FREEZE_COMMIT, INST.DESCRIPTION_PATH)
    raw_meta = git_blob(INST.CORPUS_COMMIT, INST.METADATA_PATH)
    desc = json.loads(raw_desc.decode("utf-8"))
    rows = [json.loads(x) for x in
            git_blob(INST.CORPUS_COMMIT, INST.CORPUS_PATH).decode("utf-8").splitlines()
            if x.strip()]
    meta = json.loads(raw_meta.decode("utf-8"))
    _kw = dict(raw_desc=raw_desc, raw_meta=raw_meta, orig_desc=desc, orig_meta=meta)

    results, ok_all = [], True
    with tempfile.TemporaryDirectory(prefix="conformance_fixtures_") as td:
        tmp = Path(td)

        # BASELINE: the unmutated real bytes, round-tripped through the same
        # writer the fixtures use, so a fixture failure cannot be a writer
        # artifact.
        base = run_instrument(tmp, "BASE", copy.deepcopy(desc),
                              copy.deepcopy(rows), copy.deepcopy(meta), **_kw)
        base_status = status_map(base)
        print(f"BASELINE (real bytes, round-tripped): "
              f"{base['summary']['passed']} PASS / {base['summary']['failed']} FAIL / "
              f"{base['summary']['unchecked']} UNCHECKED")
        base_fails = sorted(k for k, v in base_status.items() if v == "FAIL")
        print(f"  baseline FAILs: {base_fails}")

        for tag, title, mut, must_fail, must_pass in FIXTURES:
            d2, r2, m2 = mut(copy.deepcopy(desc), copy.deepcopy(rows), copy.deepcopy(meta))
            st = status_map(run_instrument(tmp, tag, d2, r2, m2, **_kw))
            got_fail = [c for c in must_fail if st.get(c) == "FAIL"]
            bad_pass = [c for c in must_pass if st.get(c) != "PASS"]
            # No check outside the injected blast radius may flip PASS->FAIL.
            collateral = sorted(
                k for k, v in st.items()
                if v == "FAIL" and base_status.get(k) == "PASS" and k not in must_fail
            )
            ok = len(got_fail) == len(must_fail) and not bad_pass
            ok_all &= ok
            results.append({"fixture": tag, "title": title, "ok": ok,
                            "required_to_fail": must_fail, "did_fail": got_fail,
                            "required_to_stay_pass": must_pass,
                            "wrongly_not_pass": bad_pass,
                            "collateral_flips": collateral})
            print(f"  [{'ok ' if ok else 'BAD'}] {tag} {title}: "
                  f"flagged {got_fail}" + (f"  collateral={collateral}" if collateral else ""))

        for tag, title, mut, must_pass in POSITIVE_CONTROLS:
            d2, r2, m2 = mut(copy.deepcopy(desc), copy.deepcopy(rows), copy.deepcopy(meta))
            st = status_map(run_instrument(tmp, tag, d2, r2, m2, **_kw))
            got = [c for c in must_pass if st.get(c) == "PASS"]
            ok = len(got) == len(must_pass)
            ok_all &= ok
            results.append({"fixture": tag, "title": title, "ok": ok,
                            "required_to_pass": must_pass, "did_pass": got,
                            "baseline_status": {c: base_status.get(c) for c in must_pass}})
            print(f"  [{'ok ' if ok else 'BAD'}] {tag} {title}: "
                  f"now PASS {got} (baseline "
                  f"{[base_status.get(c) for c in must_pass]})")

    print(f"\n{len(FIXTURES)} defect fixtures MUST be flagged; "
          f"{sum(1 for r in results if r['fixture'].startswith('M') and r['ok'])} were.")
    print(f"{len(POSITIVE_CONTROLS)} positive controls MUST flip to PASS; "
          f"{sum(1 for r in results if r['fixture'].startswith('P') and r['ok'])} did.")
    print("REAL CORPUS WAS NEVER MUTATED: fixtures were written only under "
          "tempfile.TemporaryDirectory and the real bytes were read from git "
          "blobs at pinned revs.")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
