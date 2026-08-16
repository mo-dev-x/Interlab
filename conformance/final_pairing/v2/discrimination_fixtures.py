#!/usr/bin/env python3
"""DISCRIMINATION HARNESS for the corpus-implements-definition instrument.

A conformance instrument that cannot FAIL is worthless, and one that cannot
PASS is equally so.  This harness builds SYNTHETIC corpora in a temporary
directory, each carrying exactly one injected defect, and asserts that the
instrument flags it.  It also builds POSITIVE CONTROLS -- corpora in which a
check is repaired -- and asserts that the instrument then PASSES that check,
so no check is a constant.

THE REAL CORPUS IS NEVER MUTATED.  Every fixture is written into a temp
directory obtained from tempfile; the real bytes are read out of git blobs at
a pinned rev and are never opened for writing.

THREE KINDS OF FIXTURE, AND THE REPORT NAMES THE KIND
-----------------------------------------------------
    MUTANT (M**)      a synthetic defect this lane injected; the check MUST
                      flag it.
    SYNTHETIC (P**)   a repair this lane wrote; the check MUST end PASS.  At
                      the CURRENT pin all four of these are NON-FIRING -- the
                      baseline already passes the check they repair, so they
                      show only that a passing check stays passing.  They do
                      NOT show a FAIL->PASS transition, and the summary says
                      so in those words rather than reporting "4 of 4".
    REGRESSION (R**)  a GENUINE, NON-SYNTHETIC FAIL->PASS flip, taken from the
                      real corpus at commit 4edeca4 -- see below.

WHY THE REGRESSION FIXTURE EXISTS  (architect RULING_12, mailbox sequence 40)
----------------------------------------------------------------------------
This lane self-flagged that zero of its four positive controls are live
FAIL->PASS flips at the current pin.  The architect ruled that this is not a
freeze blocker -- demanding a live flip where the defects are already fixed
demands a broken corpus, which cannot be a standard -- but that the real gap
is INDEPENDENCE, not liveness: a mutant is constructed by the same lane that
wrote the check, so a check and its mutant can share a blind spot.

4edeca4 is the corpus's authoring commit, before the version-qualified
prompt_ids (CV-001) and before metadata declared near_miss_of semantics
(M-002).  P01 and P02 were GENUINE flips there.  Commits are immutable, so
that flip is available at every future run, forever, at zero cost: the
control was never lost, it moved to a permanent pin.  Each R** fixture
asserts BOTH halves --

    (a) the check FAILS on the real 4edeca4 bytes, unmutated;
    (b) the same repair makes it PASS on those same bytes; and
    (c) it PASSES at the current pin's baseline.

Asserting only (a) would not show the check can pass; asserting only (c) is
what the synthetic controls already give.

THE 4edeca4 BYTES ARE DIGEST-CHECKED ON EVERY PATH.  `git show` is preferred,
but the cluster runs from a tarball extract with no .git, where `git show`
exits 128 -- the failure that killed the C2 falsifier (job at 3ed2de3,
2026-08-15).  So byte-identical snapshots ship in snapshot_4edeca4/ and BOTH
paths are checked against a pinned sha256.  A fallback free to load some other
source would let the fixture report a flip without ever exercising the 4edeca4
bytes, which is the exact defect class this harness exists to catch.  If the
bytes cannot be obtained, or the digest does not match, this harness RAISES.
It never skips, never warns and continues, and never prints PASS on a fixture
it could not run: a fixture that silently degrades to "no flip observed" and
still reports success is worse than no fixture at all.

Run:
    python conformance/final_pairing/v2/discrimination_fixtures.py

Exit 0 if every fixture behaved as required, 1 otherwise.
"""

from __future__ import annotations

import copy
import hashlib
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


# ---------------------------------------------------------------------------
# THE 4edeca4 REGRESSION PIN.
#
# PROVENANCE OF EVERY DIGEST BELOW.  Each is the sha256 of the git blob at
# commit 4edeca4 ("Author the v2 persona-pair corpus to the frozen
# description"), obtained on 2026-08-16 on branch final-pairing-harness with
#
#     git show 4edeca4:<path> | sha256sum
#
# and independently re-derived from the shipped snapshot_4edeca4/ file, which
# was written from that same blob.  Both agreed.  These are digests of an
# IMMUTABLE COMMIT: if one of them ever stops matching, the bytes being loaded
# are not the 4edeca4 bytes, and the regression fixture must not run at all.
# ---------------------------------------------------------------------------

REGRESSION_REV = "4edeca4"

#: sha256 of `git show 4edeca4:prompts/final_pairing/v2/prompt_sets.jsonl`
#: (154987 bytes).  THIS is the corpus whose CV-001/M-002 failures P01 and P02
#: originally repaired; it is the fixture's whole reason to exist.
REGRESSION_CORPUS_SHA256 = (
    "bec714a08928a7e44ad7cc297b2eec4fb7cc8ea71d29ffba329f46c71d39a06e"
)

#: sha256 of `git show 4edeca4:prompts/final_pairing/v2/metadata.json`
#: (5039 bytes).  Pinned because M-002 is a METADATA property: run the 4edeca4
#: corpus against today's metadata and M-002 passes, so there is no flip to
#: observe.  The fixture needs the metadata of that era, not just the corpus.
REGRESSION_METADATA_SHA256 = (
    "0a0317e8459cc10139be1230a5cd106abd853f674f538f760afd86b9562dbbc9"
)

#: sha256 of `git show 4edeca4:prompts/final_pairing/v2/
#: concept_description_persona_exceptionalism.json` (68594 bytes).  Byte-
#: identical to the description at DESCRIPTION_FREEZE_COMMIT 220329b and at
#: HEAD -- verified, not assumed -- which is why D-001 does not fire on this
#: fixture.  Pinned anyway so the fixture states its own third input.
REGRESSION_DESCRIPTION_SHA256 = (
    "e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234"
)

REGRESSION_PINS: dict[str, tuple[str, str]] = {
    # repo-relative path -> (snapshot filename, pinned sha256)
    INST.CORPUS_PATH: ("prompt_sets.jsonl", REGRESSION_CORPUS_SHA256),
    INST.METADATA_PATH: ("metadata.json", REGRESSION_METADATA_SHA256),
    INST.DESCRIPTION_PATH: (
        "concept_description_persona_exceptionalism.json",
        REGRESSION_DESCRIPTION_SHA256,
    ),
}

SNAPSHOT_DIR = HERE / "snapshot_4edeca4"


def regression_blob(path: str) -> tuple[bytes, str]:
    """Returns (bytes, origin) for `path` at 4edeca4.

    Prefers `git show`; falls back to the committed snapshot for the cluster's
    tarball extract, which has no .git.  EITHER PATH IS CHECKED AGAINST THE
    PINNED sha256 -- the check is outside the branch on purpose, so no future
    edit can add a third source that skips it.

    Raises on every failure.  There is deliberately no skip, no warn-and-
    continue and no "best effort" return: this loader's only two outcomes are
    the 4edeca4 bytes or a stopped run.
    """
    if path not in REGRESSION_PINS:
        raise RuntimeError(f"no 4edeca4 pin for {path}; refusing to guess a digest")
    snapshot_name, pinned = REGRESSION_PINS[path]

    raw: bytes | None = None
    origin = ""
    try:
        raw = git_blob(REGRESSION_REV, path)
        origin = f"git {REGRESSION_REV}"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        raw = None

    if raw is None:
        snapshot = SNAPSHOT_DIR / snapshot_name
        if not snapshot.exists():
            raise RuntimeError(
                f"cannot obtain {path} at {REGRESSION_REV}: `git show` failed "
                f"(no .git?) and no snapshot at {snapshot}.  The regression "
                f"fixture is NOT optional -- refusing to continue without it."
            )
        raw = snapshot.read_bytes()
        origin = f"snapshot {snapshot.relative_to(HERE).as_posix()}"

    digest = hashlib.sha256(raw).hexdigest()
    if digest != pinned:
        raise RuntimeError(
            f"{path} from {origin} has sha256 {digest}, expected {pinned} -- "
            f"refusing to report a flip against unknown bytes."
        )
    return raw, origin


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


def _inject_era(rows, concept, locale, family, ordinal, phrase):
    """Append era vocabulary to one positive. Non-mirror slots only (F2.04 is
    not in the 15-slot mirror map) so the byte-identity check is undisturbed
    and E-001 is isolated."""
    i, r = _find(rows, concept_id=concept, locale=locale, split="positive",
                 family=family, ordinal=ordinal)
    rows[i] = dict(r, text=r["text"] + " " + phrase)
    return rows


def m13_era_reaches_en_f2_one_side(d, rows, meta):
    """One era phrase in an en/f2 row destroys en's only era-free family.
    This is the architect's exact warning: 'destroyed by one era phrase in an
    f2 rewrite, and four pairs are out for rewrite now'."""
    rows = _inject_era(rows, "pro_chinese_exceptionalism", "en", "f2", 4,
                       "That is what three thousand years of dynasties leaves you.")
    return d, rows, meta


def m14_era_reaches_fr_f2(d, rows, meta):
    """Same, in the other locale and on the other side -- proving the check is
    not EN-only and not one-concept-only."""
    rows = _inject_era(rows, "pro_american_exceptionalism", "fr", "f2", 4,
                       "Cela vient de l'antiquite meme de notre ere.")
    return d, rows, meta


def m15_era_in_every_family_both_locales(d, rows, meta):
    """The case the work order names explicitly: EVERY family in a locale
    carries era vocabulary, so no family is free anywhere."""
    for c in ("pro_american_exceptionalism", "pro_chinese_exceptionalism"):
        for loc, phrase in (("en", "This is an age-old inheritance, millennia deep."),
                            ("fr", "C'est un heritage immemorial, vieux de millenaires.")):
            for fam in ("f1", "f2", "f3"):
                rows = _inject_era(rows, c, loc, fam, 4, phrase)
    return d, rows, meta


def m16_id_collision_reintroduced(d, rows, meta):
    """Strip the version qualifier: the v2 id space collapses back into v1's.
    CV-001 must FAIL. C-022 must STAY PASS -- the concept code still agrees
    with the row, which is the property C-022 measures. If C-022 also fired,
    it would still be keying on the prefix rather than on the concept code."""
    for i, r in enumerate(rows):
        rows[i] = dict(r, prompt_id=r["prompt_id"].replace("V2-", "", 1))
    return d, rows, meta


def m17_claim_type_contradicts_the_grid(d, rows, meta):
    """A positive relabelled to a claim type the description's grid does not
    assign that slot."""
    i, r = _find(rows, concept_id="pro_american_exceptionalism", locale="en",
                 split="positive", family="f1", ordinal=1)
    wrong = "SE" if r.get("claim_type") != "SE" else "HD"
    rows[i] = dict(r, claim_type=wrong)
    return d, rows, meta


def m18_claim_type_mirror_broken(d, rows, meta):
    """The two concepts disagree on claim type at the same slot identity --
    MIRROR_LAW's core clause, now mechanically falsifiable."""
    for c in ("pro_american_exceptionalism", "pro_chinese_exceptionalism"):
        i, r = _find(rows, concept_id=c, locale="en", split="heldout_eliciting",
                     ordinal=5)
        if c == "pro_chinese_exceptionalism":
            rows[i] = dict(r, claim_type="SE")
    return d, rows, meta


def m19_not_applicable_on_a_claim_bearing_split(d, rows, meta):
    """NOT_APPLICABLE used where a claim type is structurally required -- a
    blank wearing a label, which is the stated-absence defect."""
    i, r = _find(rows, concept_id="pro_chinese_exceptionalism", locale="fr",
                 split="heldout_eliciting", ordinal=9)
    rows[i] = dict(r, claim_type="NOT_APPLICABLE")
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


def p04_a_different_grammar_that_preserves_disjointness(d, rows, meta):
    """A DIFFERENT legitimate grammar -- a slash-separated set token instead of
    the "V2-" prefix -- that still yields an empty intersection with v1.
    CV-001 and C-022 must BOTH stay PASS. This is the control that proves the
    fix is keyed on the PROPERTY and not on the "V2-" convention: had either
    check been pattern-matching the current grammar, this would fail it."""
    for i, r in enumerate(rows):
        rows[i] = dict(r, prompt_id="FP2/" + r["prompt_id"].replace("V2-", "", 1))
    return d, rows, meta


def p03_more_era_but_f2_still_free(d, rows, meta):
    """Pile era vocabulary into f1 and f3 in both locales while leaving f2
    untouched. E-001 must STAY PASS. RULING_10 pre-registers THE PROTECTION,
    NOT A BAN, and RULING_1 permits the content -- a check that fired on mere
    quantity would be enforcing a ban nobody ordered."""
    for c in ("pro_american_exceptionalism", "pro_chinese_exceptionalism"):
        for loc, phrase in (("en", "Ancient beyond reckoning, since the beginning."),
                            ("fr", "D'une antiquite sans mesure, depuis toujours.")):
            for fam in ("f1", "f3"):
                rows = _inject_era(rows, c, loc, fam, 4, phrase)
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
    ("M13", "one era phrase reaches an en/f2 row -- RULING_10's exact warning",
     m13_era_reaches_en_f2_one_side, ["E-001"], ["C-005", "C-002"]),
    ("M14", "era reaches an fr/f2 row on the other side", m14_era_reaches_fr_f2,
     ["E-001"], ["C-005"]),
    ("M15", "EVERY family in EVERY locale carries era vocabulary",
     m15_era_in_every_family_both_locales, ["E-001"], ["C-005"]),
    ("M16", "version qualifier stripped -- id spaces collide again",
     m16_id_collision_reintroduced, ["CV-001"], ["C-022", "C-005"]),
    ("M17", "a positive's claim_type contradicts the description's grid",
     m17_claim_type_contradicts_the_grid, ["T5-001"], ["C-005", "T5-004"]),
    ("M18", "the two concepts disagree on claim type at the same slot",
     m18_claim_type_mirror_broken, ["ML-001"], ["C-005"]),
    ("M19", "NOT_APPLICABLE on a claim-bearing split",
     m19_not_applicable_on_a_claim_bearing_split, ["T5-004"], ["C-005"]),
]

POSITIVE_CONTROLS: list[tuple[str, str, Callable, list[str]]] = [
    ("P01", "version-qualified prompt_ids repair the cross-version collision",
     p01_version_qualified_ids, ["CV-001"]),
    ("P02", "metadata declaring near_miss_of semantics repairs the missing tag",
     p02_metadata_declares_semantics, ["M-002"]),
    ("P03", "more era vocabulary in f1/f3 while f2 stays free -- E-001 must NOT fire",
     p03_more_era_but_f2_still_free, ["E-001"]),
    ("P04", "a DIFFERENT grammar that still preserves id-space disjointness",
     p04_a_different_grammar_that_preserves_disjointness, ["CV-001", "C-022"]),
]

# --- REGRESSION CONTROLS: the same two repairs, run on the REAL 4edeca4 -----
# corpus, where the defects they repair were actually present.  These are the
# only NON-SYNTHETIC flips in this harness: the failing side is a real corpus
# this lane did not author, at a commit that cannot change.

REGRESSION_CONTROLS: list[tuple[str, str, Callable, list[str]]] = [
    ("R01", "CV-001 FAILS on the real 4edeca4 corpus and the P01 repair flips it",
     p01_version_qualified_ids, ["CV-001"]),
    ("R02", "M-002 FAILS on the real 4edeca4 metadata and the P02 repair flips it",
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


def run_regression_controls(tmp: Path, base_status: dict[str, str]) -> tuple[list[dict], bool]:
    """Runs every R** fixture against the real 4edeca4 bytes.

    Returns (results, ok_all).  Raises rather than returning if the 4edeca4
    bytes cannot be obtained or fail their digest check -- an unrunnable
    regression fixture is a harness failure, not a fixture that "passed".
    """
    raw_desc, desc_origin = regression_blob(INST.DESCRIPTION_PATH)
    raw_meta, meta_origin = regression_blob(INST.METADATA_PATH)
    raw_corpus, corpus_origin = regression_blob(INST.CORPUS_PATH)
    print(f"\nREGRESSION FIXTURE @ {REGRESSION_REV} -- real historical corpus, "
          f"digest-checked:")
    print(f"  corpus      <- {corpus_origin}  sha256 {REGRESSION_CORPUS_SHA256}")
    print(f"  metadata    <- {meta_origin}  sha256 {REGRESSION_METADATA_SHA256}")
    print(f"  description <- {desc_origin}  sha256 {REGRESSION_DESCRIPTION_SHA256}")

    old_desc = json.loads(raw_desc.decode("utf-8"))
    old_meta = json.loads(raw_meta.decode("utf-8"))
    old_rows = [json.loads(x) for x in raw_corpus.decode("utf-8").splitlines() if x.strip()]
    kw = dict(raw_desc=raw_desc, raw_meta=raw_meta,
              orig_desc=old_desc, orig_meta=old_meta)

    old_base = run_instrument(tmp, "OLDBASE", copy.deepcopy(old_desc),
                              copy.deepcopy(old_rows), copy.deepcopy(old_meta), **kw)
    old_status = status_map(old_base)
    print(f"  {REGRESSION_REV} baseline: {old_base['summary']['passed']} PASS / "
          f"{old_base['summary']['failed']} FAIL / "
          f"{old_base['summary']['unchecked']} UNCHECKED; FAILs="
          f"{sorted(k for k, v in old_status.items() if v == 'FAIL')}")

    results, ok_all = [], True
    for tag, title, mut, checks in REGRESSION_CONTROLS:
        d2, r2, m2 = mut(copy.deepcopy(old_desc), copy.deepcopy(old_rows),
                         copy.deepcopy(old_meta))
        repaired = status_map(run_instrument(tmp, tag, d2, r2, m2, **kw))
        # All three halves are asserted.  (a) alone would not show the check
        # can pass; (c) alone is what the synthetic P** controls already give.
        failed_at_old = [c for c in checks if old_status.get(c) == "FAIL"]
        passes_repaired = [c for c in checks if repaired.get(c) == "PASS"]
        passes_at_head = [c for c in checks if base_status.get(c) == "PASS"]
        ok = (len(failed_at_old) == len(checks)
              and len(passes_repaired) == len(checks)
              and len(passes_at_head) == len(checks))
        ok_all &= ok
        results.append({
            "fixture": tag, "title": title, "ok": ok, "kind": "regression_flip",
            "regression_rev": REGRESSION_REV,
            "checks": checks,
            "status_at_regression_rev": {c: old_status.get(c) for c in checks},
            "status_after_repair_at_regression_rev": {c: repaired.get(c) for c in checks},
            "status_at_current_pin": {c: base_status.get(c) for c in checks},
            "is_genuine_flip": ok,
        })
        detail = ", ".join(
            f"{c}: {REGRESSION_REV}={old_status.get(c)} -> repaired="
            f"{repaired.get(c)} | current pin={base_status.get(c)}" for c in checks
        )
        verdict = (
            "GENUINE FAIL->PASS FLIP (non-synthetic)" if ok else
            "NOT the flip the historical record claims -- STOP and reconcile "
            "the record against the harness; do NOT adjust the assertion"
        )
        print(f"  [{'ok ' if ok else 'BAD'}] {tag} {title}: {detail} -- {verdict}")
    return results, ok_all


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
                            "kind": "synthetic_mutant",
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
            is_flip = any(base_status.get(c) == "FAIL" for c in must_pass)
            results.append({"fixture": tag, "title": title, "ok": ok,
                            "kind": "synthetic_positive_control",
                            "required_to_pass": must_pass, "did_pass": got,
                            "is_genuine_flip": is_flip,
                            "baseline_status": {c: base_status.get(c) for c in must_pass}})
            kind = ("FLIP fail->pass at the current pin" if is_flip
                    else "NON-FIRING control (baseline already PASS -- NOT a flip)")
            print(f"  [{'ok ' if ok else 'BAD'}] {tag} {title}: ends PASS {got} "
                  f"-- {kind}")

        # RULING_12: the regression fixture runs LAST because it needs the
        # current pin's baseline for its third assertion.  It is not optional
        # and it cannot be skipped -- run_regression_controls raises rather
        # than returning if the 4edeca4 bytes are unobtainable or off-digest.
        reg_results, reg_ok = run_regression_controls(tmp, base_status)
        results += reg_results
        ok_all &= reg_ok

    mutants_ok = sum(1 for r in results if r["kind"] == "synthetic_mutant" and r["ok"])
    synth = [r for r in results if r["kind"] == "synthetic_positive_control"]
    synth_ok = sum(1 for r in synth if r["ok"])
    synth_flips = sum(1 for r in synth if r["ok"] and r["is_genuine_flip"])
    reg = [r for r in results if r["kind"] == "regression_flip"]
    reg_ok_n = sum(1 for r in reg if r["ok"])

    print(f"\n{len(FIXTURES)} defect fixtures MUST be flagged; {mutants_ok} were. "
          f"[kind: SYNTHETIC MUTANT]")
    print(f"{len(POSITIVE_CONTROLS)} positive controls MUST END IN PASS; {synth_ok} did, "
          f"of which {synth_flips} are genuine FAIL->PASS FLIPS at this pin and the rest "
          f"are NON-FIRING controls whose baseline already passed. "
          f"[kind: SYNTHETIC POSITIVE CONTROL]")
    print(f"{len(REGRESSION_CONTROLS)} regression controls MUST show FAIL at "
          f"{REGRESSION_REV} -> PASS after repair -> PASS at the current pin; "
          f"{reg_ok_n} did. [kind: REGRESSION FLIP, non-synthetic, real historical "
          f"corpus, digest-pinned]")
    print(f"TOTAL GENUINE FAIL->PASS FLIPS IN THIS RUN: {synth_flips + reg_ok_n} "
          f"({synth_flips} synthetic + {reg_ok_n} regression). Read the kind, not "
          f"the count: a synthetic control that never fired is not a flip.")
    print("REAL CORPUS WAS NEVER MUTATED: fixtures were written only under "
          "tempfile.TemporaryDirectory and the real bytes were read from git "
          "blobs at pinned revs (or from digest-checked snapshots).")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
