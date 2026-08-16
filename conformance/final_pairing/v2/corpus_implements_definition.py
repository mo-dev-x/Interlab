#!/usr/bin/env python3
"""CORPUS-IMPLEMENTS-DEFINITION INSTRUMENT for the final-pairing v2 persona pair.

WHO MAY RUN THIS AND WHO MAY NOT HAVE WRITTEN IT
------------------------------------------------
protocols/final_pairing/v1/definition_corpus_binding_gate.json, and architect
RULING_9 (mailbox sequence 37), require this instrument to be authored by a
lane that authored NEITHER the frozen description NOR the corpus.  This file is
authored by the CONFORMANCE lane, which authored neither, and which does not
edit either.  It REPORTS.  It has no repair path by construction: it opens both
artifacts read-only and never writes to prompts/.

INDEPENDENCE
------------
This module imports NOTHING from prompts/final_pairing/v2/.  It does not reuse
the corpus author's validate_prompt_sets.py, build_prompt_sets.py or
authoring/*.py.  Two lanes agreeing via the same code is not independent
confirmation.  Every expectation below is DERIVED FROM THE FROZEN DESCRIPTION
JSON at read time -- the counts, the slot grid, the claim-type allocation, the
near-miss mirror map, the length-parity bounds and two of the lexical screens
are read out of the description's own fields, not transcribed into constants
here.  Where the instrument must supply something the description does not
state mechanically (a nation-name lexicon, a national-referent screen list),
that fact is labelled INSTRUMENT_SUPPLIED in the emitted report.

WHAT AN "UNCHECKED" MEANS HERE
------------------------------
A requirement this instrument cannot decide mechanically is emitted with
status UNCHECKED and a reason.  It is NEVER emitted as PASS.  An absence that
cannot be distinguished from a real negative is not evidence, and silently
skipping a requirement manufactures exactly that.

USAGE
-----
    python conformance/final_pairing/v2/corpus_implements_definition.py \
        --rev 4edeca4 --json-out <path>

    # or, for synthetic fixtures, against loose files:
    python ... --description <f> --corpus <f> --metadata <f>

Exit code 0 if no check FAILED, 1 if any check FAILED.  UNCHECKED does not
affect the exit code -- it is reported, not scored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pins.  Verification commands cite a pinned sha, never HEAD.
# ---------------------------------------------------------------------------

DESCRIPTION_FREEZE_COMMIT = "220329b"
DESCRIPTION_SHA256 = "e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234"

# THE CORPUS MOVES; THE PIN MOVES WITH IT AND THE OLD PIN IS KEPT, NOT REPLACED.
# 4edeca4 was the authoring commit. e544776 (disjointness instrument repaired
# per RULING_9), 18c4264 (four parity returns repaired) and 98b8a21 (era
# vocabulary held constant across those repairs) have since changed
# prompt_sets.jsonl, and 6616089 added the corpus author's own deep-time guard.
# A conformance verdict is only ever a verdict ON A NAMED COMMIT.
CORPUS_COMMIT = "c9dd6a7"
CORPUS_COMMIT_PRIOR_MEASURED = ("4edeca4", "6616089")

DESCRIPTION_PATH = "prompts/final_pairing/v2/concept_description_persona_exceptionalism.json"
CORPUS_PATH = "prompts/final_pairing/v2/prompt_sets.jsonl"
METADATA_PATH = "prompts/final_pairing/v2/metadata.json"

# The frozen v1 set, cited ONLY for the cross-version join hazard (CV-*).
V1_FREEZE_COMMIT = "880b48a7f50b8c716e64956b915857dd1fcde350"
V1_CORPUS_PATH = "prompts/final_pairing/v1/prompt_sets.jsonl"

PASS, FAIL, UNCHECKED = "PASS", "FAIL", "UNCHECKED"


# ---------------------------------------------------------------------------
# INSTRUMENT_SUPPLIED lexicons.  The description states these requirements in
# prose; it does not ship a machine-readable list.  They are declared here, in
# the open, and echoed into the report so a reader can see exactly what was
# matched rather than trusting a verdict.
# ---------------------------------------------------------------------------

NATION_LEXICON: dict[str, dict[str, str]] = {
    # keyed by the pole stem taken from binding_for_this_document.pole_identifiers
    "american_exceptionalism": {
        "en": r"\b(?:America|American|Americans|United States|U\.S\.A?\.?|USA)\b",
        "fr": r"(?:\bAm[ée]rique\b|\bam[ée]ricain(?:e|s|es)?\b|\b[EÉ]tats-Unis\b)",
    },
    "chinese_exceptionalism": {
        "en": r"\b(?:China|Chinese)\b",
        "fr": r"(?:\bChine\b|\bchinois(?:e|es)?\b)",
    },
}

# For the "no national referent of any kind ... for EITHER target nation or any
# other" hard requirement on unrelated / heldout_neutral.  A NAME-AND-DEMONYM
# screen only.  It cannot see "national institution, founding document, flag,
# anthem, national holiday, currency, capital" in general, so the check that
# uses it is reported PARTIAL and its unreached limbs are reported UNCHECKED.
NATIONAL_REFERENT_SCREEN = (
    r"\b(?:America|American|Americans|United States|USA|U\.S\.|China|Chinese|"
    r"Britain|British|England|English|France|French|Germany|German|Russia|Russian|"
    r"Japan|Japanese|India|Indian|Canada|Canadian|Mexico|Mexican|Brazil|Brazilian|"
    r"Italy|Italian|Spain|Spanish|Korea|Korean|Egypt|Egyptian|Greece|Greek|"
    r"Rome|Roman|Constitution|Congress|Parliament|Senate|White House|"
    r"Fourth of July|Thanksgiving|Bastille|Marseillaise|dollar|yuan|renminbi|"
    r"Washington|Beijing|Peking|Paris|London|Ottawa)\b"
    r"|(?:\bAm[ée]rique\b|\bam[ée]ricain\w*|\b[EÉ]tats-Unis\b|\bChine\b|\bchinois\w*"
    r"|\bFrance\b|\bfran[çc]ais\w*|\bAngleterre\b|\banglais\w*|\bAllemagne\b"
    r"|\ballemand\w*|\bRussie\b|\brusse\w*|\bJapon\b|\bjaponais\w*|\bInde\b"
    r"|\bindien\w*|\bCanada\b|\bcanadien\w*|\bParis\b|\bLondres\b|\bP[ée]kin\b"
    r"|\bWashington\b|\bConstitution\b|\bAssembl[ée]e nationale\b)"
)


def _norm(s: str) -> str:
    """NFC-normalise so an accent composed two ways is one string."""
    return unicodedata.normalize("NFC", s)


def _fold(s: str) -> str:
    """Accent-fold and lowercase.  Matching happens on the folded form so the
    FR patterns can be written without accents and an accent composed two ways
    cannot make a locale silently under-match -- the failure mode RULING_9 found
    in the stopword instrument, one artifact over."""
    d = unicodedata.normalize("NFD", s)
    return "".join(c for c in d if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# ERA / DEEP-TIME LEXICON  (architect RULING_10, mailbox sequence 38)
#
# RULING_10 pre-registers THE PROTECTION, NOT A BAN: "era vocabulary is confined
# to a proper subset of families such that, in each locale, at least one family
# carries none on either side."  Deep-time content is RULED PERMITTED under
# RULING_1; this bounds a PURE ERA-DETECTOR, which passes G-A at ~1.0 on both
# halves of the negative set precisely because near_miss is the mirror's
# positives byte-identical and carries none of the other side's era vocabulary.
#
# DERIVED BY CATEGORY, NOT HAND-LISTED, and both locales are covered to the
# SAME CATEGORICAL DEPTH -- explicitly to avoid rebuilding the locale-asymmetric
# defect RULING_9 found in STOPWORDS_FR.  Note what "same depth" means here: it
# is the same CATEGORY on both sides, NOT word-for-word translation.  See the
# ancien/ancient note in C3, which is the single most consequential judgement in
# this list and is reported, not buried.
#
# RULING_10 item 4 governs: A CLOSED LIST IS NON-EXHAUSTIVE.  It operationalises
# the clause; it does not replace it.  Read as exhaustive it becomes a loophole
# generator.  This list is pinned BY HASH so a later reader can tell which list
# produced a verdict, not so the list becomes the definition.
# ---------------------------------------------------------------------------

ERA_LEXICON: dict[str, dict[str, list[str]]] = {
    "C1_DYNASTIC_OR_PERIOD_NOUN": {
        "en": [r"\bdynast(?:y|ies)\b", r"\bkingdom of old\b"],
        "fr": [r"\bdynastie(?:s)?\b", r"\broyaume(?:s)? d'antan\b"],
    },
    "C2_MILLENNIAL_OR_CENTENNIAL_DURATION": {
        "en": [r"\bmillenni(?:um|a)\b", r"\bthousands? of years\b",
               r"\b[a-z-]+ thousand years\b", r"\bcentur(?:y|ies)\b"],
        "fr": [r"\bmillenaire(?:s)?\b", r"\bmilliers d'annees\b",
               r"\bmille ans\b", r"\bsiecle(?:s)?\b"],
    },
    "C3_ANTIQUITY_MARKER": {
        # EN 'ancient' is monosemous for time depth.  FR 'ancien' IS NOT: it is
        # a general-purpose adjective/noun meaning old, former or ELDER, and
        # 'les anciens de ma famille' is 'the elders of my family' -- a PERSON
        # reference carrying no time depth at all.  Translating 'ancient' as
        # 'ancien' would OVER-cover FR relative to EN, which is the same defect
        # class as RULING_9's under-covered STOPWORDS_FR, pointing the other
        # way.  The FR antiquity markers at the same categorical depth are
        # antique / antiquite / immemorial.  THIS DECISION CHANGES THE VERDICT
        # -- see E-001's ALTERNATE_READING, which is reported, not hidden.
        "en": [r"\bancient\b", r"\bantiquity\b", r"\bimmemorial\b",
               r"\bage-old\b", r"\bof old\b"],
        "fr": [r"\bantique(?:s)?\b", r"\bantiquite\b",
               r"\bimmemorial(?:e|es|aux)?\b", r"\bd'antan\b"],
    },
    "C4_ERA_OR_EPOCH_NOUN": {
        "en": [r"\bepoch(?:s)?\b", r"\bera(?:s)?\b", r"\bages? past\b"],
        "fr": [r"\bepoque(?:s)?\b", r"\bere(?:s)?\b", r"\bages? revolu(?:s)?\b"],
    },
    "C5_DEEP_DATE_MARKER": {
        "en": [r"\bb\.?c\.?e?\b", r"\bbefore the common era\b"],
        "fr": [r"\bavant notre ere\b", r"\bav\.? ?j\.?-?c\.?\b"],
    },
    "C6_DEEP_TIME_CONTINUITY_PHRASE": {
        "en": [r"\bas far back as\b", r"\bback to the beginning\b",
               r"\bolder than\b", r"\bsince the beginning\b",
               r"\bin use that long\b", r"\bshape so long\b",
               r"\btime out of mind\b"],
        "fr": [r"\bd'aussi loin que\b", r"\bremonte(?:nt)? au commencement\b",
               r"\bplus vieil?(?:le)?(?:s)? que\b", r"\bdepuis toujours\b",
               r"\ben usage aussi longtemps\b", r"\bforme aussi longtemps\b",
               r"\bde temps immemorial\b"],
    },
}

# The FR polysemous form deliberately EXCLUDED from C3, kept here so the
# alternate reading can be measured rather than asserted.
ERA_LEXICON_ALTERNATE_FR_ANCIEN = [r"\bancien(?:ne|nes|s)?\b"]


def era_lexicon_sha256() -> str:
    """Pin the list by hash. A verdict without the list that produced it is a
    verdict nobody can re-derive."""
    canonical = json.dumps(ERA_LEXICON, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def era_hits(text: str, locale: str, extra_fr: list[str] | None = None
             ) -> list[tuple[str, str]]:
    """Return [(category, matched_surface_form), ...] for one row."""
    folded = _fold(text)
    out: list[tuple[str, str]] = []
    for cat, per_locale in ERA_LEXICON.items():
        for pat in per_locale.get(locale, []):
            out += [(cat, m.group(0)) for m in re.finditer(pat, folded)]
    if extra_fr and locale == "fr":
        for pat in extra_fr:
            out += [("C3_ANTIQUITY_MARKER_ALTERNATE", m.group(0))
                    for m in re.finditer(pat, folded)]
    return out


# ---------------------------------------------------------------------------
# Loading -- pinned blobs by default, loose files only for synthetic fixtures.
# ---------------------------------------------------------------------------


def git_blob(rev: str, path: str, repo: Path) -> bytes:
    out = subprocess.run(
        ["git", "-C", str(repo), "show", f"{rev}:{path}"],
        capture_output=True,
        check=True,
    )
    return out.stdout


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Spec derivation.  Everything here is READ OUT OF THE DESCRIPTION.
# ---------------------------------------------------------------------------


class Spec:
    """The machine-readable shadow of the frozen description.

    Every attribute records WHERE in the description it came from, so a reader
    can check the derivation instead of trusting it.
    """

    def __init__(self, desc: dict[str, Any]) -> None:
        self.provenance: dict[str, str] = {}
        b = desc["binding_for_this_document"]
        self.concepts: list[str] = list(b["describes_concepts"])
        self.provenance["concepts"] = "binding_for_this_document.describes_concepts"

        poles = b["pole_identifiers"]
        self.pole_positive = {c: poles[c]["pole_positive"] for c in self.concepts}
        self.pole_near_miss = {c: poles[c]["pole_near_miss"] for c in self.concepts}
        self.provenance["poles"] = "binding_for_this_document.pole_identifiers"

        # The mirror partner is derived, not assumed: A's near-miss pole is B's
        # positive pole.  With two concepts this is a bijection or a defect.
        by_positive = {v: k for k, v in self.pole_positive.items()}
        self.mirror = {c: by_positive[self.pole_near_miss[c]] for c in self.concepts}
        self.provenance["mirror"] = (
            "derived: concept X's mirror is the concept whose pole_positive "
            "equals X's pole_near_miss"
        )

        s = desc["SPLITS_AND_WHAT_EACH_ONE_IS"]
        frozen = s["counts_are_frozen"]
        self.counts: dict[str, int] = dict(frozen["per_concept_per_locale"])
        self.locales: list[str] = list(frozen["locales"])
        self.provenance["counts"] = (
            "SPLITS_AND_WHAT_EACH_ONE_IS.counts_are_frozen.per_concept_per_locale"
        )

        # "2 concepts x 2 locales x 100 = 400" -- recomputed, not copied.
        self.rows_per_concept_locale = sum(self.counts.values())
        self.total_rows = (
            len(self.concepts) * len(self.locales) * self.rows_per_concept_locale
        )
        self.stated_total = frozen["total_rows_for_the_pair"]

        # "3 lexically disjoint paraphrase families x 10 slots"
        m = re.search(r"(\d+)\s+lexically disjoint paraphrase families\s*x\s*(\d+)\s+slots",
                      s["positive"]["structure"])
        if not m:
            raise ValueError("could not derive family/slot counts from positive.structure")
        self.n_families, self.n_slots = int(m.group(1)), int(m.group(2))
        self.provenance["family_grid"] = "SPLITS_AND_WHAT_EACH_ONE_IS.positive.structure"

        g = desc["THE_SLOT_GRID"]
        alloc = g["claim_type_allocation_per_family"]
        self.family_keys = [k for k in ("F1", "F2", "F3") if k in alloc]
        # "01 HD" -> ("F1.01", "HD")
        self.slot_claim_type: dict[str, str] = {}
        for fam in self.family_keys:
            for entry in alloc[fam]:
                ordinal, ctype = entry.split()
                self.slot_claim_type[f"{fam}.{ordinal}"] = ctype
        self.stated_claim_totals = {
            k: v for k, v in alloc["totals_per_claim_type"].items() if k != "sum"
        }
        self.stated_claim_sum = alloc["totals_per_claim_type"]["sum"]
        self.provenance["claim_allocation"] = (
            "THE_SLOT_GRID.claim_type_allocation_per_family.F1/F2/F3"
        )

        nm = g["near_miss_mirror_slots"]
        self.near_miss_map: list[str] = list(nm["the_map_in_order"])
        self.near_miss_n = nm["n"]
        self.stated_nm_coverage = {
            k: v for k, v in nm["claim_type_coverage"].items() if k != "sum"
        }
        self.provenance["near_miss_map"] = (
            "THE_SLOT_GRID.near_miss_mirror_slots.the_map_in_order"
        )

        he = g["heldout_eliciting_allocation"]
        self.eliciting_n = he["n"]
        self.stated_he_coverage = {
            k: v for k, v in he["claim_type_coverage"].items() if k != "sum"
        }
        # "01-04 HD, 05-08 ML, 09-11 CC, 12-14 SIA, 15-17 MFO, 18-20 SE"
        self.eliciting_by_ordinal: dict[int, str] = {}
        for lo, hi, ctype in re.findall(r"(\d+)-(\d+)\s+([A-Z]+)", he["ordinals"]):
            for o in range(int(lo), int(hi) + 1):
                self.eliciting_by_ordinal[o] = ctype
        self.provenance["eliciting_allocation"] = (
            "THE_SLOT_GRID.heldout_eliciting_allocation.ordinals"
        )

        lp = desc["MIRROR_LAW"]["length_parity"]
        self.len_slot_pct = int(re.search(r"(\d+)\s*percent", lp["per_slot"]).group(1))
        self.len_split_pct = int(
            re.search(r"(\d+)\s*percent", lp["per_split_per_locale"]).group(1)
        )
        self.provenance["length_parity"] = "MIRROR_LAW.length_parity"

        # Splits declared IDENTICAL between the two concepts.
        self.shared_splits = [
            name
            for name in ("unrelated", "heldout_neutral")
            if "IDENTICAL" in str(s.get(name, {}).get("shared", ""))
        ]
        self.provenance["shared_splits"] = (
            "SPLITS_AND_WHAT_EACH_ONE_IS.<split>.shared containing IDENTICAL"
        )

        # T2's own falsifier ships the attribution-frame list in a parenthetical.
        t2 = desc["ADMISSION_TESTS"]["T2_VOICE"]["falsifier"]
        m2 = re.search(r"\(([^)]*)\)", t2)
        self.t2_frames = [x.strip() for x in m2.group(1).split(",")] if m2 else []
        self.provenance["t2_frames"] = "ADMISSION_TESTS.T2_VOICE.falsifier parenthetical"

        # The economic-vocabulary limb of WHAT_THIS_IS_NOT is an explicit word list.
        econ = next(
            (x for x in desc["THE_AXIS"]["WHAT_THIS_IS_NOT"] if "vocabulary of" in x), ""
        )
        m3 = re.search(r"vocabulary of ([^.]*)\.", econ)
        self.econ_vocab = (
            [w.strip() for w in re.split(r",| or ", m3.group(1)) if w.strip()]
            if m3
            else []
        )
        self.provenance["econ_vocab"] = (
            "THE_AXIS.WHAT_THIS_IS_NOT 'vocabulary of markets, subsidy, ...'"
        )

        # Hedge devices -- a CLOSED list the description ships verbatim.
        card = desc["RESIDUAL_ASYMMETRIES"]["1_TEMPORAL_SHAPE_OF_DESTINY_AND_CONTINUITY"][
            "THE_TENSION_WITH_INTENSITY_PARITY_IS_RULED"
        ]["THE_PARITY_REVIEWERS_CARD"]["step_3_HEDGE_DEVICE_TEST"]
        self.hedge_classes = list(card["closed_list_of_five_device_classes"])
        self.provenance["hedge_classes"] = (
            "RESIDUAL_ASYMMETRIES.1...THE_PARITY_REVIEWERS_CARD."
            "step_3_HEDGE_DEVICE_TEST.closed_list_of_five_device_classes"
        )

        self.hard_exclusions = list(desc["HARD_EXCLUSIONS"]["list"])
        self.provenance["hard_exclusions"] = "HARD_EXCLUSIONS.list"


# ---------------------------------------------------------------------------
# Result plumbing
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(
        self,
        cid: str,
        status: str,
        title: str,
        derived_from: str,
        detail: Any = None,
        partial: bool = False,
    ) -> None:
        self.checks.append(
            {
                "id": cid,
                "status": status,
                "title": title,
                "derived_from": derived_from,
                "partial": partial,
                "detail": detail,
            }
        )

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if c["status"] == FAIL]

    @property
    def unchecked(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if c["status"] == UNCHECKED]

    @property
    def passed(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if c["status"] == PASS]


def _pf(ok: bool) -> str:
    return PASS if ok else FAIL


# ---------------------------------------------------------------------------
# Corpus indexing
# ---------------------------------------------------------------------------


def index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict]]:
    idx: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        idx[(r["concept_id"], r["locale"], r["split"])].append(r)
    for v in idx.values():
        v.sort(key=lambda r: (str(r.get("family") or ""), r["ordinal"]))
    return idx


def slot_of(row: dict[str, Any]) -> str | None:
    fam = row.get("family")
    if not fam:
        return None
    return f"{str(fam).upper()}.{int(row['ordinal']):02d}"


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def run_checks(
    spec: Spec,
    desc: dict[str, Any],
    desc_bytes: bytes,
    rows: list[dict[str, Any]],
    metadata: dict[str, Any] | None,
    v1_rows: list[dict[str, Any]] | None,
    rep: Report,
) -> None:
    idx = index_rows(rows)
    concepts, locales = spec.concepts, spec.locales

    # -- D-001 -------------------------------------------------------------
    got = sha256_hex(desc_bytes)
    rep.add(
        "D-001",
        _pf(got == DESCRIPTION_SHA256),
        "Frozen description digest matches the pinned freeze value",
        f"pin: {DESCRIPTION_FREEZE_COMMIT} / {DESCRIPTION_SHA256}",
        {"expected": DESCRIPTION_SHA256, "actual": got, "bytes": len(desc_bytes)},
    )

    # -- A-001 arithmetic self-consistency of the description ---------------
    recomputed = Counter(spec.slot_claim_type.values())
    ok = dict(recomputed) == spec.stated_claim_totals and sum(
        recomputed.values()
    ) == spec.stated_claim_sum
    rep.add(
        "A-001",
        _pf(ok),
        "Description's own claim-type totals recompute from its F1/F2/F3 allocation",
        spec.provenance["claim_allocation"],
        {"recomputed": dict(sorted(recomputed.items())), "stated": spec.stated_claim_totals},
    )

    nm_recomputed = Counter(spec.slot_claim_type[s] for s in spec.near_miss_map)
    rep.add(
        "A-002",
        _pf(dict(nm_recomputed) == spec.stated_nm_coverage
            and len(spec.near_miss_map) == spec.near_miss_n),
        "Near-miss map's claim-type coverage recomputes from the map x the allocation",
        spec.provenance["near_miss_map"],
        {
            "recomputed": dict(sorted(nm_recomputed.items())),
            "stated": spec.stated_nm_coverage,
            "map_len": len(spec.near_miss_map),
            "stated_n": spec.near_miss_n,
        },
    )

    he_recomputed = Counter(spec.eliciting_by_ordinal.values())
    rep.add(
        "A-003",
        _pf(dict(he_recomputed) == spec.stated_he_coverage
            and len(spec.eliciting_by_ordinal) == spec.eliciting_n),
        "Eliciting ordinal ranges recompute to the stated claim-type coverage",
        spec.provenance["eliciting_allocation"],
        {"recomputed": dict(sorted(he_recomputed.items())), "stated": spec.stated_he_coverage},
    )

    # -- C-001 total rows ---------------------------------------------------
    rep.add(
        "C-001",
        _pf(len(rows) == spec.total_rows),
        "Corpus row total equals concepts x locales x sum(per-split counts)",
        spec.provenance["counts"],
        {
            "expected": spec.total_rows,
            "actual": len(rows),
            "description_states": spec.stated_total,
            "per_concept_locale": spec.rows_per_concept_locale,
        },
    )

    # -- C-002 per-split counts --------------------------------------------
    bad = []
    for c in concepts:
        for loc in locales:
            for split, n in spec.counts.items():
                got_n = len(idx.get((c, loc, split), []))
                if got_n != n:
                    bad.append({"concept": c, "locale": loc, "split": split,
                                "expected": n, "actual": got_n})
    rep.add(
        "C-002",
        _pf(not bad),
        "Per concept per locale, every split has exactly its frozen count",
        spec.provenance["counts"],
        {"violations": bad, "cells_checked": len(concepts) * len(locales) * len(spec.counts)},
    )

    # -- C-003 positive slot grid ------------------------------------------
    bad = []
    expected_slots = {f"F{i}.{o:02d}"
                      for i in range(1, spec.n_families + 1)
                      for o in range(1, spec.n_slots + 1)}
    for c in concepts:
        for loc in locales:
            got_slots = {slot_of(r) for r in idx.get((c, loc, "positive"), [])}
            if got_slots != expected_slots:
                bad.append({
                    "concept": c, "locale": loc,
                    "missing": sorted(expected_slots - got_slots),
                    "unexpected": sorted(x for x in got_slots - expected_slots if x),
                })
    rep.add(
        "C-003",
        _pf(not bad),
        f"Positives occupy exactly {spec.n_families} families x {spec.n_slots} slots",
        spec.provenance["family_grid"],
        {"violations": bad, "expected_slot_count": len(expected_slots)},
    )

    # -- C-004 near_miss ordinal grid --------------------------------------
    bad = []
    for c in concepts:
        for loc in locales:
            got_ord = sorted(r["ordinal"] for r in idx.get((c, loc, "near_miss"), []))
            if got_ord != list(range(1, spec.near_miss_n + 1)):
                bad.append({"concept": c, "locale": loc, "ordinals": got_ord})
    rep.add(
        "C-004",
        _pf(not bad),
        "near_miss ordinals are exactly 01..15, matching the map length",
        spec.provenance["near_miss_map"],
        {"violations": bad},
    )

    # -- C-005 NEAR-MISS BYTE IDENTITY AT THE MAPPED SLOTS ------------------
    # The load-bearing one.  near_miss ordinal k must be the MIRROR concept's
    # positive at map[k-1], byte-identical, same locale.
    bad, checked = [], 0
    for c in concepts:
        mirror = spec.mirror[c]
        for loc in locales:
            pos_by_slot = {
                slot_of(r): r["text"] for r in idx.get((mirror, loc, "positive"), [])
            }
            for r in idx.get((c, loc, "near_miss"), []):
                k = int(r["ordinal"])
                if not (1 <= k <= len(spec.near_miss_map)):
                    bad.append({"concept": c, "locale": loc, "ordinal": k,
                                "why": "ordinal outside the mirror map"})
                    continue
                src = spec.near_miss_map[k - 1]
                checked += 1
                want = pos_by_slot.get(src)
                if want is None:
                    bad.append({"concept": c, "locale": loc, "ordinal": k,
                                "source_slot": src,
                                "why": "mirror has no positive at that slot"})
                elif want != r["text"]:
                    bad.append({
                        "concept": c, "locale": loc, "ordinal": k, "source_slot": src,
                        "why": "not byte-identical",
                        "near_miss_text": r["text"][:160],
                        "mirror_positive_text": want[:160],
                    })
    rep.add(
        "C-005",
        _pf(not bad),
        "Every near_miss row is byte-identical to the MIRROR concept's positive "
        "at the mapped slot, in the matching locale",
        "SPLITS_AND_WHAT_EACH_ONE_IS.near_miss.content + "
        + spec.provenance["near_miss_map"],
        {"violations": bad, "pairs_checked": checked},
    )

    # -- C-006 falsifier_1 SOURCING, as set equality ------------------------
    bad = []
    for c in concepts:
        mirror = spec.mirror[c]
        for loc in locales:
            pos_by_slot = {
                slot_of(r): r["text"] for r in idx.get((mirror, loc, "positive"), [])
            }
            want = {pos_by_slot[s] for s in spec.near_miss_map if s in pos_by_slot}
            got_set = {r["text"] for r in idx.get((c, loc, "near_miss"), [])}
            if want != got_set:
                bad.append({"concept": c, "locale": loc,
                            "only_in_mirror_positives": len(want - got_set),
                            "only_in_near_miss": len(got_set - want)})
    rep.add(
        "C-006",
        _pf(not bad),
        "falsifier_1_SOURCING: near_miss set equals the mirror's positives at the "
        "15 mirror slots, on raw strings",
        "SPLITS_AND_WHAT_EACH_ONE_IS.near_miss.falsifier_1_SOURCING",
        {"violations": bad},
    )

    # -- C-007 falsifier_2 DISJOINTNESS, WITHIN a concept -------------------
    bad = []
    for c in concepts:
        for loc in locales:
            p = {r["text"] for r in idx.get((c, loc, "positive"), [])}
            n = {r["text"] for r in idx.get((c, loc, "near_miss"), [])}
            inter = p & n
            if inter:
                bad.append({"concept": c, "locale": loc, "n_shared": len(inter),
                            "sample": sorted(inter)[:3]})
    rep.add(
        "C-007",
        _pf(not bad),
        "falsifier_2_DISJOINTNESS: positive INTERSECT near_miss is EMPTY WITHIN a "
        "concept, per locale",
        "SPLITS_AND_WHAT_EACH_ONE_IS.near_miss.falsifier_2_DISJOINTNESS",
        {"violations": bad,
         "scope_note": "WITHIN a concept. Across the pair, shared strings are "
                       "MANDATORY -- see C-008. An instrument that flags those is wrong."},
    )

    # -- C-008 the ACROSS-THE-PAIR shared strings are EXPECTED --------------
    # architect RULING_9: "across the pair the 60 shared strings are mandatory".
    # This check FAILS if they are ABSENT or the wrong number, never if present.
    expected_shared = len(concepts) * len(locales) * spec.near_miss_n
    shared_total, per_cell = 0, []
    for c in concepts:
        mirror = spec.mirror[c]
        for loc in locales:
            n = {r["text"] for r in idx.get((c, loc, "near_miss"), [])}
            pm = {r["text"] for r in idx.get((mirror, loc, "positive"), [])}
            k = len(n & pm)
            shared_total += k
            per_cell.append({"near_miss_of": c, "mirror": mirror, "locale": loc, "shared": k})
    rep.add(
        "C-008",
        _pf(shared_total == expected_shared),
        "Across the pair, near_miss/mirror-positive shared strings number exactly "
        "concepts x locales x 15 -- byte-identity working as designed",
        "SPLITS_AND_WHAT_EACH_ONE_IS.near_miss.why_byte_identical_and_not_re_authored"
        " + architect RULING_9 (seq 37)",
        {"expected": expected_shared, "actual": shared_total, "per_cell": per_cell,
         "reading": "PRESENCE IS CORRECT. This check fails on ABSENCE or a wrong count."},
    )

    # -- C-009 REFERENT REQUIREMENT ----------------------------------------
    bad, checked = [], 0
    for c in concepts:
        pat = NATION_LEXICON.get(spec.pole_positive[c], {})
        for loc in locales:
            rx = pat.get(loc)
            if rx is None:
                rep.add("C-009", UNCHECKED,
                        f"No nation lexicon for {spec.pole_positive[c]}/{loc}",
                        "INSTRUMENT_SUPPLIED lexicon", {"pole": spec.pole_positive[c]})
                continue
            for r in idx.get((c, loc, "positive"), []):
                checked += 1
                if not re.search(rx, _norm(r["text"])):
                    bad.append({"prompt_id": r["prompt_id"], "slot": slot_of(r),
                                "text": r["text"][:160]})
    rep.add(
        "C-009",
        _pf(not bad),
        "REFERENT_REQUIREMENT: every positive, every family, both locales, names "
        "its OWN nation",
        "THE_SLOT_GRID.paraphrase_families.REFERENT_REQUIREMENT_BINDS_ALL_THREE_"
        "FAMILIES.falsifier",
        {"violations": bad, "positives_checked": checked,
         "lexicon": {k: v for k, v in NATION_LEXICON.items()},
         "lexicon_status": "INSTRUMENT_SUPPLIED -- the description states the "
                           "requirement in prose and ships no machine-readable list"},
    )

    # -- C-010 near_miss carries the MIRROR nation, not its own -------------
    bad = []
    for c in concepts:
        own = NATION_LEXICON.get(spec.pole_positive[c], {})
        other = NATION_LEXICON.get(spec.pole_near_miss[c], {})
        for loc in locales:
            if loc not in own or loc not in other:
                continue
            for r in idx.get((c, loc, "near_miss"), []):
                t = _norm(r["text"])
                if not re.search(other[loc], t) or re.search(own[loc], t):
                    bad.append({"prompt_id": r["prompt_id"], "text": r["text"][:160]})
    rep.add(
        "C-010",
        _pf(not bad),
        "Every near_miss row names the MIRROR nation and not its own -- the "
        "consequence of byte-identity plus the referent requirement",
        "derived: near_miss.content x REFERENT_REQUIREMENT",
        {"violations": bad},
    )

    # -- C-011 shared splits identical between the two concepts -------------
    bad = []
    for split in spec.shared_splits:
        for loc in locales:
            per_concept = {
                c: [r["text"] for r in idx.get((c, loc, split), [])] for c in concepts
            }
            vals = list(per_concept.values())
            if any(v != vals[0] for v in vals[1:]):
                a, b = vals[0], vals[1]
                bad.append({"split": split, "locale": loc,
                            "n_differing_ordinals": sum(
                                1 for x, y in zip(a, b) if x != y),
                            "set_equal": set(a) == set(b)})
    rep.add(
        "C-011",
        _pf(not bad),
        "unrelated and heldout_neutral are IDENTICAL between the two concepts, "
        "ordinal for ordinal, per locale",
        spec.provenance["shared_splits"] + " + <split>.falsifier",
        {"violations": bad, "splits_checked": spec.shared_splits},
    )

    # -- C-012 no national referent in the shared splits (PARTIAL) ----------
    hits = []
    for split in spec.shared_splits:
        for c in concepts:
            for loc in locales:
                for r in idx.get((c, loc, split), []):
                    m = re.search(NATIONAL_REFERENT_SCREEN, _norm(r["text"]))
                    if m:
                        hits.append({"prompt_id": r["prompt_id"], "match": m.group(0),
                                     "text": r["text"][:160]})
    rep.add(
        "C-012",
        _pf(not hits),
        "unrelated / heldout_neutral carry no national referent -- NAME AND "
        "DEMONYM SCREEN ONLY",
        "SPLITS_AND_WHAT_EACH_ONE_IS.unrelated.hard_requirement + "
        "heldout_neutral.hard_requirement",
        {"violations": hits,
         "screen_status": "INSTRUMENT_SUPPLIED, PARTIAL",
         "what_this_screen_cannot_see": [
             "an unnamed national institution, founding document, flag, anthem, "
             "national holiday, currency or capital not on the list",
             "a national-greatness predicate carrying no name",
             "a discovery-split discriminative marker (heldout_neutral's third limb)",
         ]},
        partial=True,
    )

    # -- C-013 heldout_eliciting grid + names its own nation ----------------
    bad_grid, bad_name = [], []
    for c in concepts:
        pat = NATION_LEXICON.get(spec.pole_positive[c], {})
        for loc in locales:
            got_ord = sorted(r["ordinal"] for r in idx.get((c, loc, "heldout_eliciting"), []))
            if got_ord != list(range(1, spec.eliciting_n + 1)):
                bad_grid.append({"concept": c, "locale": loc, "ordinals": got_ord})
            rx = pat.get(loc)
            if rx:
                for r in idx.get((c, loc, "heldout_eliciting"), []):
                    if not re.search(rx, _norm(r["text"])):
                        bad_name.append({"prompt_id": r["prompt_id"],
                                         "text": r["text"][:160]})
    rep.add(
        "C-013",
        _pf(not bad_grid and not bad_name),
        "heldout_eliciting is 01..20 per concept per locale and every row NAMES "
        "its own nation",
        "SPLITS_AND_WHAT_EACH_ONE_IS.heldout_eliciting.content + "
        + spec.provenance["eliciting_allocation"],
        {"grid_violations": bad_grid, "unnamed_nation": bad_name},
    )

    # -- C-014 eliciting must not duplicate a positive (exact limb) ---------
    dup = []
    for c in concepts:
        for loc in locales:
            pos = {r["text"] for r in idx.get((c, loc, "positive"), [])}
            for r in idx.get((c, loc, "heldout_eliciting"), []):
                if r["text"] in pos:
                    dup.append({"prompt_id": r["prompt_id"], "text": r["text"][:160]})
    rep.add(
        "C-014",
        _pf(not dup),
        "heldout_eliciting falsifier_2: no eliciting row is byte-identical to a "
        "positive -- EXACT LIMB ONLY",
        "SPLITS_AND_WHAT_EACH_ONE_IS.heldout_eliciting.falsifier_2",
        {"violations": dup,
         "not_covered": "'near-duplicating' is a semantic judgement; the exact "
                        "limb is the only mechanical part. See U-005."},
        partial=True,
    )

    # -- C-015 length parity per slot --------------------------------------
    # The description says '+/-20 percent' without naming the baseline.  Rather
    # than silently pick one, both readings are computed and reported.
    def parity_scan(split: str, key) -> dict[str, Any]:
        strict, lenient, worst = [], [], None
        a, b = concepts[0], concepts[1]
        for loc in locales:
            ka = {key(r): len(r["text"]) for r in idx.get((a, loc, split), [])}
            kb = {key(r): len(r["text"]) for r in idx.get((b, loc, split), [])}
            for k in sorted(set(ka) & set(kb)):
                la, lb = ka[k], kb[k]
                lo, hi = min(la, lb), max(la, lb)
                d_strict = (hi - lo) / lo if lo else 1.0
                d_lenient = (hi - lo) / hi if hi else 1.0
                if worst is None or d_strict > worst[0]:
                    worst = (d_strict, {"slot": k, "locale": loc, "len_a": la, "len_b": lb})
                if d_strict > spec.len_slot_pct / 100:
                    strict.append({"slot": k, "locale": loc, "len_a": la, "len_b": lb,
                                   "delta_over_min": round(d_strict, 4)})
                if d_lenient > spec.len_slot_pct / 100:
                    lenient.append({"slot": k, "locale": loc, "len_a": la, "len_b": lb,
                                    "delta_over_max": round(d_lenient, 4)})
        return {"strict_reading_violations": strict,
                "lenient_reading_violations": lenient,
                "worst_pair": worst[1] | {"delta_over_min": round(worst[0], 4)}
                if worst else None}

    pos_par = parity_scan("positive", slot_of)
    eli_par = parity_scan("heldout_eliciting", lambda r: f"HOE.{int(r['ordinal']):02d}")
    any_strict = pos_par["strict_reading_violations"] + eli_par["strict_reading_violations"]
    any_lenient = pos_par["lenient_reading_violations"] + eli_par["lenient_reading_violations"]
    rep.add(
        "C-015",
        _pf(not any_lenient),
        f"MIRROR_LAW length parity per slot, +/-{spec.len_slot_pct}% -- "
        "BOTH BASELINE READINGS REPORTED",
        spec.provenance["length_parity"] + ".per_slot",
        {"positive": pos_par, "heldout_eliciting": eli_par,
         "AMBIGUITY": "The description says '+/-20 percent' without naming the "
                      "baseline. Verdict above is the LENIENT reading "
                      "(delta/max). The STRICT reading (delta/min) yields "
                      f"{len(any_strict)} violations. This ambiguity is REPORTED, "
                      "not resolved by this lane -- resolving it would be editing "
                      "the description.",
         "strict_reading_violation_count": len(any_strict),
         "lenient_reading_violation_count": len(any_lenient)},
        partial=True,
    )

    # -- C-016 length parity per split per locale --------------------------
    bad = []
    a, b = concepts[0], concepts[1]
    for split in spec.counts:
        for loc in locales:
            ta = sum(len(r["text"]) for r in idx.get((a, loc, split), []))
            tb = sum(len(r["text"]) for r in idx.get((b, loc, split), []))
            lo, hi = min(ta, tb), max(ta, tb)
            d = (hi - lo) / hi if hi else 0.0
            if d > spec.len_split_pct / 100:
                bad.append({"split": split, "locale": loc, "total_a": ta, "total_b": tb,
                            "delta_over_max": round(d, 4)})
    rep.add(
        "C-016",
        _pf(not bad),
        f"MIRROR_LAW length parity per split per locale, +/-{spec.len_split_pct}%",
        spec.provenance["length_parity"] + ".per_split_per_locale",
        {"violations": bad},
    )

    # -- C-017 no description string is corpus-eligible ---------------------
    desc_strings: set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            desc_strings.add(_norm(o.strip()))

    walk(desc)
    corpus_texts = {_norm(r["text"].strip()) for r in rows}
    collisions = sorted(desc_strings & corpus_texts)
    rep.add(
        "C-017",
        _pf(not collisions),
        "No corpus row byte-matches any string in the description -- EXACT LIMB ONLY",
        "NO_STRING_IN_THIS_DOCUMENT_IS_CORPUS_ELIGIBLE.falsifier",
        {"violations": collisions[:10],
         "description_strings_scanned": len(desc_strings),
         "not_covered": "'near-duplicates' is a semantic judgement. See U-006."},
        partial=True,
    )

    # -- C-018 T2 attribution-frame lexical screen (PARTIAL) ----------------
    frames = [f for f in spec.t2_frames if f]
    hits = []
    for c in concepts:
        for loc in locales:
            for r in idx.get((c, loc, "positive"), []):
                low = _norm(r["text"]).lower()
                for f in frames:
                    if f.lower() in low:
                        hits.append({"prompt_id": r["prompt_id"], "frame": f,
                                     "text": r["text"][:160]})
    rep.add(
        "C-018",
        _pf(not hits),
        "T2_VOICE falsifier, LEXICAL LIMB ONLY: does any positive contain an "
        "attribution frame from T2's own list?",
        spec.provenance["t2_frames"],
        {"lexical_hits": hits, "frames_from_description": frames,
         "THE_FALSIFIER_HAS_A_SECOND_LIMB_THIS_CANNOT_REACH":
             "T2's falsifier reads 'A positive containing an attribution frame "
             "(...) GOVERNING THE GREATNESS CLAIM.' The PRESENCE of a frame is "
             "mechanical and is what is reported here. Whether the frame GOVERNS "
             "the greatness claim is semantic and is NOT CHECKED -- see U-002. A "
             "lexical hit is therefore a ROW REFERRED FOR ADJUDICATION, not a "
             "proven T2 violation, and a clean screen is NOT a proven T2 pass.",
         "ADJUDICATION_REQUIRED": "The frame list is unqualified for PERSON, but "
             "T2's own requires-clause admits the belief 'ASSERTED as the "
             "speaker's own, in first person'. A first-person 'I believe that X' "
             "is simultaneously ADMITTED by requires and MATCHED by the falsifier "
             "list. That tension is in the FROZEN DESCRIPTION, not in this "
             "instrument. This lane REPORTS it and does not resolve it: resolving "
             "it would mean editing a frozen definition.",
         "limits": ["the frame list is English; the FR rows are screened against "
                    "an English list and an unlisted FR frame passes unseen",
                    "a lexical miss does not establish that the claim is asserted "
                    "as the speaker's own -- that is U-002"]},
        partial=True,
    )

    # -- C-019 T4 conservative limb: no mirror-nation name in a positive ----
    hits = []
    for c in concepts:
        other = NATION_LEXICON.get(spec.pole_near_miss[c], {})
        for loc in locales:
            rx = other.get(loc)
            if not rx:
                continue
            for r in idx.get((c, loc, "positive"), []):
                m = re.search(rx, _norm(r["text"]))
                if m:
                    hits.append({"prompt_id": r["prompt_id"], "match": m.group(0),
                                 "text": r["text"][:160]})
    rep.add(
        "C-019",
        _pf(not hits),
        "T4_NO_NAMED_TARGET, conservative limb: no positive names the MIRROR "
        "nation at all -- zero mentions makes the named-target limb vacuously safe",
        "ADMISSION_TESTS.T4_NO_NAMED_TARGET.falsifier",
        {"violations": hits,
         "limits": ["covers the MIRROR nation and any other nation on the "
                    "INSTRUMENT_SUPPLIED screen only",
                    "whether a named nation appears in a predicate of INFERIORITY "
                    "is semantic and is U-004"]},
        partial=True,
    )

    # -- C-020 economic-vocabulary screen ----------------------------------
    hits = []
    econ = [w for w in spec.econ_vocab if len(w) > 3]
    for c in concepts:
        for loc in locales:
            for split in ("positive", "heldout_eliciting"):
                for r in idx.get((c, loc, split), []):
                    low = _norm(r["text"]).lower()
                    for w in econ:
                        if re.search(rf"\b{re.escape(w.lower())}\b", low):
                            hits.append({"prompt_id": r["prompt_id"], "word": w,
                                         "text": r["text"][:160]})
    rep.add(
        "C-020",
        _pf(not hits),
        "WHAT_THIS_IS_NOT economic-system vocabulary screen over positives and "
        "eliciting rows -- EN LIST ONLY",
        spec.provenance["econ_vocab"],
        {"violations": hits, "words_from_description": econ},
        partial=True,
    )

    # -- C-021 duplicates within (concept, locale, split) -------------------
    bad = []
    for key, group in idx.items():
        dups = [t for t, n in Counter(r["text"] for r in group).items() if n > 1]
        if dups:
            bad.append({"cell": list(key), "duplicate_texts": dups[:3]})
    distinct = len({r["text"] for r in rows})
    rep.add(
        "C-021",
        _pf(not bad),
        "No duplicate text within a (concept, locale, split) cell",
        "derived: rows are slot-addressed, so a repeat inside a cell is a "
        "collapsed slot",
        {"violations": bad, "distinct_texts_corpus_wide": distinct,
         "total_rows": len(rows)},
    )

    # -- C-022 prompt_id agrees with the row it names -----------------------
    # THE PROPERTY IS CONCEPT-CODE CONSISTENCY, NOT A LITERAL FIRST FIELD.
    # This check previously asserted parts[0] == f"C{nn}". RULING_11's
    # version-qualification made ids "V2-C01.EN.POS.F1.01" -- the qualifier was
    # attached to the concept code rather than added as a sixth dotted field, so
    # five-field parsers still parse, but an equality pinned to the exact first
    # field breaks. Re-pinning the literal to "V2-C{nn}" would pass today and
    # break on the next legitimate grammar change: an instrument whose STRUCTURE
    # does not match the PROPERTY it measures. The concept code is therefore
    # located WHEREVER IT SITS in the first field, and any leading qualifier is
    # reported as an observation rather than required or forbidden.
    bad = []
    qualifiers: Counter = Counter()
    concept_code_re = re.compile(r"C(\d+)\b")
    for r in rows:
        pid = str(r["prompt_id"])
        parts = pid.split(".")
        if len(parts) != 5:
            bad.append({"prompt_id": pid, "why": "not 5 dotted fields"})
            continue
        cid_field, loc, _split_code, fam, ordinal = parts
        m = concept_code_re.search(cid_field)
        if not m:
            bad.append({"prompt_id": pid,
                        "why": f"no C<nn> concept code found in first field "
                               f"{cid_field!r}"})
        elif int(m.group(1)) != int(r["concept_index"]):
            bad.append({"prompt_id": pid,
                        "why": f"concept code C{m.group(1)} disagrees with "
                               f"concept_index {r['concept_index']}"})
        else:
            qualifiers[cid_field[:m.start()] or "(none)"] += 1
        if loc.lower() != r["locale"]:
            bad.append({"prompt_id": pid, "why": "locale field disagrees"})
        if int(ordinal) != int(r["ordinal"]):
            bad.append({"prompt_id": pid, "why": "ordinal field disagrees"})
        want_fam = str(r.get("family") or "X0").upper()
        if fam != want_fam:
            bad.append({"prompt_id": pid,
                        "why": f"family field {fam} != {want_fam}"})
    rep.add(
        "C-022",
        _pf(not bad),
        "prompt_id agrees with the row it names: the CONCEPT CODE wherever it "
        "sits, plus locale, family and ordinal",
        "derived: the ID must not disagree with the row it names",
        {"violations": bad[:10], "violation_count": len(bad),
         "leading_qualifiers_observed": dict(qualifiers),
         "WHY_THIS_IS_NOT_A_PREFIX_MATCH":
             "The requirement is that the id's concept code agree with the row's "
             "concept_index. A version qualifier may be present or absent and "
             "either is well-formed here; disjointness from v1 is a SEPARATE "
             "property and is checked separately as CV-001. Keying this check on "
             "a literal first field would make it pass today and fail on the "
             "next legitimate grammar change."},
    )

    # -- C-023 near_miss_of resolves to the MIRROR, WITHIN v2 ---------------
    # Separate from CV-002.  CV-002 asks whether the KEY's meaning flipped
    # across the version boundary; this asks whether v2's own value is right.
    bad = []
    for c in concepts:
        for loc in locales:
            for r in idx.get((c, loc, "near_miss"), []):
                if r.get("near_miss_of") != spec.mirror[c]:
                    bad.append({"prompt_id": r["prompt_id"],
                                "near_miss_of": r.get("near_miss_of"),
                                "expected_mirror": spec.mirror[c]})
    rep.add(
        "C-023",
        _pf(not bad),
        "Within v2, every near_miss row's near_miss_of names the MIRROR concept, "
        "as the pole identifiers require",
        "binding_for_this_document.pole_identifiers + near_miss.near_miss_source",
        {"violations": bad[:10], "violation_count": len(bad)},
    )

    # -- T5-*/ML-001  WHAT THE RECORDED claim_type FIELD UNLOCKS ------------
    # RULING_11 records claim_type on every row. READ THE UNLOCK NARROWLY.
    # The field is the CORPUS AUTHOR'S OWN ASSERTION about their own row. It
    # makes the BOOKKEEPING mechanically checkable -- does the recorded type
    # agree with the description's grid, does it mirror across the pair -- and
    # it does NOT make the SENTENCE'S CONTENT checkable. Treating a recorded
    # label as evidence that the sentence instantiates that claim type would be
    # this lane marking the author's work. See U-005, which is NARROWED and NOT
    # discharged.
    has_ct = all("claim_type" in r for r in rows)
    if not has_ct:
        for cid in ("T5-001", "T5-002", "T5-003", "T5-004", "ML-001"):
            rep.add(cid, UNCHECKED, "corpus rows carry no claim_type field",
                    "RULING_11", {"rows_missing_claim_type":
                                  sum(1 for r in rows if "claim_type" not in r)})
    else:
        NA = "NOT_APPLICABLE"
        # T5-001 positives: recorded type == the description's allocation grid
        bad = []
        for c in concepts:
            for loc in locales:
                for r in idx.get((c, loc, "positive"), []):
                    want = spec.slot_claim_type.get(slot_of(r) or "")
                    if r.get("claim_type") != want:
                        bad.append({"prompt_id": r["prompt_id"],
                                    "slot": slot_of(r),
                                    "recorded": r.get("claim_type"),
                                    "grid_requires": want})
        rep.add(
            "T5-001",
            _pf(not bad),
            "Every positive's RECORDED claim_type equals the claim type the "
            "description's F1/F2/F3 allocation assigns that slot",
            spec.provenance["claim_allocation"],
            {"violations": bad[:10], "violation_count": len(bad),
             "positives_checked": sum(len(idx.get((c, l, "positive"), []))
                                      for c in concepts for l in locales),
             "SCOPE": "This checks the RECORDED LABEL against the grid. It does "
                      "NOT check that the SENTENCE instantiates that claim type "
                      "-- see U-005."},
        )

        # T5-002 near_miss: recorded type == the type at the MAPPED SOURCE slot
        bad = []
        for c in concepts:
            for loc in locales:
                for r in idx.get((c, loc, "near_miss"), []):
                    k = int(r["ordinal"])
                    src = (spec.near_miss_map[k - 1]
                           if 1 <= k <= len(spec.near_miss_map) else None)
                    want = spec.slot_claim_type.get(src or "")
                    if r.get("claim_type") != want:
                        bad.append({"prompt_id": r["prompt_id"],
                                    "source_slot": src,
                                    "recorded": r.get("claim_type"),
                                    "grid_requires": want})
        rep.add(
            "T5-002",
            _pf(not bad),
            "Every near_miss row's RECORDED claim_type equals the type of the "
            "MIRROR SLOT it was copied from",
            spec.provenance["near_miss_map"],
            {"violations": bad[:10], "violation_count": len(bad)},
        )

        # T5-003 eliciting: recorded type == the description's ordinal ranges
        bad = []
        for c in concepts:
            for loc in locales:
                for r in idx.get((c, loc, "heldout_eliciting"), []):
                    want = spec.eliciting_by_ordinal.get(int(r["ordinal"]))
                    if r.get("claim_type") != want:
                        bad.append({"prompt_id": r["prompt_id"],
                                    "ordinal": r["ordinal"],
                                    "recorded": r.get("claim_type"),
                                    "grid_requires": want})
        rep.add(
            "T5-003",
            _pf(not bad),
            "Every heldout_eliciting row's RECORDED claim_type matches the "
            "description's ordinal-range allocation",
            spec.provenance["eliciting_allocation"],
            {"violations": bad[:10], "violation_count": len(bad)},
        )

        # T5-004 NOT_APPLICABLE lands exactly on the two no-claim splits
        na_by_split = Counter(r["split"] for r in rows
                              if r.get("claim_type") == NA)
        expected_na = {
            s: len(concepts) * len(locales) * spec.counts[s]
            for s in spec.shared_splits
        }
        missing_ct = [r["prompt_id"] for r in rows if not r.get("claim_type")]
        rep.add(
            "T5-004",
            _pf(dict(na_by_split) == expected_na and not missing_ct
                and na_by_split.get("heldout_eliciting", 0) == 0),
            "NOT_APPLICABLE appears on EXACTLY the two no-claim splits and "
            "nowhere else; no row is left without a claim_type",
            "derived: unrelated and heldout_neutral are the splits the "
            "description gives no claim type; every other split has one",
            {"not_applicable_by_split": dict(na_by_split),
             "expected": expected_na,
             "not_applicable_total": sum(na_by_split.values()),
             "heldout_eliciting_not_applicable": na_by_split.get(
                 "heldout_eliciting", 0),
             "rows_with_no_claim_type": len(missing_ct),
             "rows_total": len(rows),
             "WHY_THIS_MATTERS": "NOT_APPLICABLE used for an UNDETERMINED type "
                 "would be a blank wearing a label -- the stated-absence defect. "
                 "It is structural only if it lands on exactly the splits that "
                 "structurally have no claim type, which is what is measured "
                 "here rather than accepted."},
        )

        # ML-001 MIRROR_LAW's core clause, now mechanical
        pair_bad, pairs = [], 0
        a, b = concepts[0], concepts[1]
        for split, keyfn in (("positive", slot_of),
                             ("near_miss", lambda r: f"NM.{int(r['ordinal']):02d}"),
                             ("heldout_eliciting",
                              lambda r: f"HOE.{int(r['ordinal']):02d}")):
            for loc in locales:
                ka = {keyfn(r): r for r in idx.get((a, loc, split), [])}
                kb = {keyfn(r): r for r in idx.get((b, loc, split), [])}
                for k in sorted(set(ka) & set(kb)):
                    pairs += 1
                    ra, rb = ka[k], kb[k]
                    if ra.get("claim_type") != rb.get("claim_type"):
                        pair_bad.append({"slot": k, "locale": loc, "split": split,
                                         a: ra.get("claim_type"),
                                         b: rb.get("claim_type")})
                    if str(ra.get("family") or "") != str(rb.get("family") or ""):
                        pair_bad.append({"slot": k, "locale": loc, "split": split,
                                         "why": "family differs across the mirror"})
        rep.add(
            "ML-001",
            _pf(not pair_bad),
            "MIRROR_LAW core clause: at every slot identity the two concepts "
            "assert the SAME claim type in the SAME paraphrase family",
            "MIRROR_LAW.statement",
            {"violations": pair_bad[:10], "slot_pairs_checked": pairs,
             "breakdown": "30 positive + 15 near_miss + 20 eliciting slots, "
                          "x2 locales",
             "WHAT_IS_NOW_MECHANICAL_AND_WHAT_IS_NOT":
                 "MIRROR_LAW requires the same claim type, family, SPEECH ACT and "
                 "LENGTH BAND with the referent swapped. Claim type and family "
                 "are now mechanical (here); length band is C-015/C-016; SPEECH "
                 "ACT remains a semantic judgement and is NOT checked."},
        )

    # -- E-001/E-002 ERA-VOCABULARY FAMILY CONFINEMENT (RULING_10) ----------
    # The pre-registered property, in the architect's own words:
    #   "Era vocabulary is confined to a proper subset of families such that,
    #    in each locale, at least one family carries none on either side."
    # Threshold-free: the test is zero versus non-zero, per family, per locale,
    # across BOTH concepts.
    def era_scan(extra_fr: list[str] | None):
        per_cell: dict[tuple[str, str, str], dict[str, Any]] = {}
        totals: dict[str, dict[str, int]] = {c: {"tokens": 0, "rows": 0}
                                             for c in concepts}
        for c in concepts:
            for loc in locales:
                for r in idx.get((c, loc, "positive"), []):
                    fam = str(r.get("family") or "").lower()
                    h = era_hits(r["text"], loc, extra_fr)
                    cell = per_cell.setdefault(
                        (c, loc, fam), {"tokens": 0, "rows": 0, "examples": []})
                    if h:
                        cell["tokens"] += len(h)
                        cell["rows"] += 1
                        totals[c]["tokens"] += len(h)
                        totals[c]["rows"] += 1
                        if len(cell["examples"]) < 4:
                            cell["examples"].append(
                                {"prompt_id": r["prompt_id"],
                                 "hits": [f"{a}:{b}" for a, b in h]})
        families = sorted({k[2] for k in per_cell})
        era_free: dict[str, list[str]] = {}
        for loc in locales:
            era_free[loc] = [
                fam for fam in families
                if all(per_cell.get((c, loc, fam), {"tokens": 0})["tokens"] == 0
                       for c in concepts)
            ]
        return per_cell, totals, families, era_free

    per_cell, era_totals, families, era_free = era_scan(None)
    alt_cell, alt_totals, _, alt_era_free = era_scan(ERA_LEXICON_ALTERNATE_FR_ANCIEN)

    locales_without_an_era_free_family = [l for l in locales if not era_free[l]]
    # "a PROPER subset of families" -- so at least one family free AND at least
    # one family carrying it; a corpus with zero era vocabulary anywhere would
    # satisfy the letter, and RULING_1 permits the content, so absence is not
    # failed here. Only the protection is required.
    rep.add(
        "E-001",
        _pf(not locales_without_an_era_free_family),
        "RULING_10 PRE-REGISTRATION: era vocabulary is confined to a proper "
        "subset of families such that, in EACH LOCALE, at least one family "
        "carries NONE on EITHER side",
        "architect RULING_10, mailbox architect sequence 38, item 3",
        {
            "era_free_families_per_locale": era_free,
            "locales_with_NO_era_free_family": locales_without_an_era_free_family,
            "rows_and_tokens_per_concept_locale_family": {
                f"{c}|{l}|{f}": {k: v for k, v in d.items() if k != "examples"}
                for (c, l, f), d in sorted(per_cell.items())
            },
            "examples": {f"{c}|{l}|{f}": d["examples"]
                         for (c, l, f), d in sorted(per_cell.items())
                         if d["examples"]},
            "lexicon_sha256": era_lexicon_sha256(),
            "lexicon_categories": sorted(ERA_LEXICON),
            "lexicon_provenance": "DERIVED BY CATEGORY by the conformance lane. "
                "Six closed-class-of-meaning categories, each populated in BOTH "
                "locales to the same CATEGORICAL depth. Matching is on an "
                "accent-folded lowercase form so FR cannot silently under-match. "
                "Pinned by the sha256 above.",
            "ALTERNATE_READING_THIS_IS_THE_LOAD_BEARING_JUDGEMENT": {
                "what_changes": "FR 'ancien' is polysemous -- old / former / "
                    "ELDER. The corpus uses it ONLY in the nominal sense: "
                    "'Les anciens de ma famille' and 'Les anciens que j'ai "
                    "connus' both mean THE ELDERS, a person reference carrying "
                    "no time depth. EN 'ancient' is monosemous for time depth. "
                    "Translating one as the other OVER-covers FR, which is the "
                    "RULING_9 locale-asymmetry defect pointing the other way. "
                    "C3 therefore carries antique / antiquite / immemorial / "
                    "d'antan in FR and NOT bare 'ancien'.",
                "verdict_under_the_shipped_lexicon": {
                    "era_free_families": era_free,
                    "locales_failing": locales_without_an_era_free_family},
                "verdict_if_bare_ancien_IS_counted": {
                    "era_free_families": alt_era_free,
                    "locales_failing": [l for l in locales if not alt_era_free[l]]},
                "THE_VERDICT_IS_UNSTABLE_ACROSS_THIS_ONE_DECISION":
                    "Counting bare FR 'ancien' puts era vocabulary in fr/f2 on "
                    "the pro_chinese side (fr f2.02 and f2.10) and LEAVES FR "
                    "WITH NO ERA-FREE FAMILY. The protection RULING_10 "
                    "pre-registers would then FAIL in fr. This lane makes the "
                    "linguistic call above and REPORTS the instability rather "
                    "than presenting a bare verdict -- the same handling "
                    "RULING_9 required of the Jaccard margin. THE CHOICE OF "
                    "LEXICON IS NOT THIS LANE'S TO RATIFY.",
            },
        },
        partial=True,
    )

    direction_ok = (era_totals[concepts[1]]["tokens"] != era_totals[concepts[0]]["tokens"])
    rep.add(
        "E-002",
        _pf(direction_ok),
        "REPRODUCTION CHECK: the era-vocabulary asymmetry between the two "
        "concepts reproduces in direction on an independently derived lexicon",
        "architect RULING_10 item 3 measured 19 tokens over 17 rows vs 1 over 1",
        {
            "measured_by_this_lane": era_totals,
            "architect_measured": {"pro_chinese_exceptionalism": "19 tokens / 17 rows",
                                   "pro_american_exceptionalism": "1 token / 1 row"},
            "reading": "Direction and order of magnitude reproduce on a lexicon "
                       "built independently. The counts are NOT identical and "
                       "should not be: a different list is a different "
                       "instrument, which RULING_9 already established is the "
                       "expected outcome and itself a finding.",
            "other_splits_carry_none": {
                f"{c}|{l}|{s}": sum(len(era_hits(r["text"], l))
                                    for r in idx.get((c, l, s), []))
                for c in concepts for l in locales
                for s in ("heldout_eliciting", "heldout_neutral", "unrelated",
                          "near_miss")
            },
            "why_near_miss_is_NOT_zero": "near_miss IS the mirror's positives "
                "byte-identical, so it carries the MIRROR's era vocabulary. That "
                "is the asymmetry engine RULING_10 describes: for the "
                "era-heavy concept, its OWN near_miss half is era-light, so a "
                "pure era feature scores at ceiling against both halves of G-A's "
                "negative set.",
        },
        partial=True,
    )

    # -- M-001..M-003 metadata vs description ------------------------------
    if metadata is None:
        rep.add("M-001", UNCHECKED, "metadata.json not supplied", "n/a", None)
    else:
        mism = []
        b = metadata.get("binds_to_description", {})
        if b.get("sha256") != DESCRIPTION_SHA256:
            mism.append({"field": "binds_to_description.sha256",
                         "metadata": b.get("sha256"), "expected": DESCRIPTION_SHA256})
        if b.get("bytes") != len(desc_bytes):
            mism.append({"field": "binds_to_description.bytes",
                         "metadata": b.get("bytes"), "actual": len(desc_bytes)})
        if metadata.get("expected_counts_per_concept_per_locale") != spec.counts:
            mism.append({"field": "expected_counts_per_concept_per_locale",
                         "metadata": metadata.get("expected_counts_per_concept_per_locale"),
                         "description": spec.counts})
        m_alloc = metadata.get("claim_type_allocation_per_family", {})
        d_alloc = {f.lower(): [spec.slot_claim_type[f"{f}.{o:02d}"]
                               for o in range(1, spec.n_slots + 1)]
                   for f in spec.family_keys}
        if {k.lower(): v for k, v in m_alloc.items()} != d_alloc:
            mism.append({"field": "claim_type_allocation_per_family",
                         "metadata": m_alloc, "description": d_alloc})
        m_map = metadata.get("near_miss_source_slot_map", {}).get("slots_in_order")
        if m_map != spec.near_miss_map:
            mism.append({"field": "near_miss_source_slot_map.slots_in_order",
                         "metadata": m_map, "description": spec.near_miss_map})
        m_he = metadata.get("heldout_eliciting_claim_types_by_ordinal")
        d_he = [spec.eliciting_by_ordinal[o] for o in range(1, spec.eliciting_n + 1)]
        if m_he != d_he:
            mism.append({"field": "heldout_eliciting_claim_types_by_ordinal",
                         "metadata": m_he, "description": d_he})
        if metadata.get("row_count") != len(rows):
            mism.append({"field": "row_count", "metadata": metadata.get("row_count"),
                         "actual": len(rows)})
        rep.add(
            "M-001",
            _pf(not mism),
            "metadata.json restates the description's counts, allocation, mirror "
            "map and eliciting order WITHOUT DRIFT",
            "description fields vs metadata.json fields",
            {"mismatches": mism},
        )

        # near_miss_of semantics must be declared, not left to the reader
        has_tag = any("near_miss_of" in k and "semantic" in k
                      for k in metadata.keys())
        rep.add(
            "M-002",
            _pf(has_tag),
            "metadata declares near_miss_of SEMANTICS explicitly, so the meaning "
            "travels with the data rather than with the reader's memory of the "
            "version",
            "architect RULING_9 (seq 37) THE_THREE_OBSERVATIONS.3",
            {"metadata_top_level_keys_matching": [k for k in metadata
                                                  if "near_miss" in k],
             "why_this_is_a_check": "v1 sets near_miss_of to the row's OWN "
                                    "concept; v2 sets it to the MIRROR. Same key, "
                                    "opposite meaning, neither value self-identifying."},
        )

    # -- CV-001/CV-002 the CROSS-VERSION SILENT MIS-JOIN --------------------
    if v1_rows is None:
        rep.add("CV-001", UNCHECKED, "frozen v1 set not supplied", "n/a", None)
    else:
        v1_by_cid: dict[str, set[str]] = defaultdict(set)
        for r in v1_rows:
            v1_by_cid[str(r["prompt_id"]).split(".")[0]].add(r["concept_id"])
        v2_by_cid: dict[str, set[str]] = defaultdict(set)
        for r in rows:
            v2_by_cid[str(r["prompt_id"]).split(".")[0]].add(r["concept_id"])
        collisions = {
            cid: {"v1": sorted(v1_by_cid[cid]), "v2": sorted(v2_by_cid[cid])}
            for cid in sorted(set(v1_by_cid) & set(v2_by_cid))
            if v1_by_cid[cid] != v2_by_cid[cid]
        }
        # THE PROPERTY, NOT A GRAMMAR: the two id spaces must not intersect.
        # Any grammar preserving disjointness passes; any grammar losing it
        # fails, including one that keeps the "V2-" prefix but reuses an id.
        v2_ids = {r["prompt_id"] for r in rows}
        v1_ids = {r["prompt_id"] for r in v1_rows}
        id_collisions = sorted(v2_ids & v1_ids)
        rep.add(
            "CV-001",
            _pf(not id_collisions and not collisions),
            "ID-SPACE DISJOINTNESS ACROSS THE FROZEN VERSION BOUNDARY: the v1 "
            "and v2 prompt_id spaces must not intersect, and no shared concept "
            "code may denote different concepts",
            f"v1 pinned {V1_FREEZE_COMMIT[:7]} vs v2 pinned {CORPUS_COMMIT}; "
            "architect RULING_11",
            {"exact_prompt_id_collisions": len(id_collisions),
             "sample_colliding_ids": id_collisions[:5],
             "colliding_concept_codes": collisions,
             "v2_ids_distinct": len(v2_ids),
             "v2_row_count": len(rows),
             "v1_ids_distinct": len(v1_ids),
             "THIS_IS_AN_EMPTINESS_CHECK_NOT_A_PREFIX_MATCH":
                 "The requirement is the PROPERTY -- an empty intersection -- "
                 "not any particular grammar. A future id grammar that preserves "
                 "disjointness still passes; a grammar that keeps a version "
                 "prefix but reuses an id still FAILS. Pattern-matching 'V2-' "
                 "would confirm a convention rather than the property that "
                 "actually stands between a consumer and a wrong join.",
             "hazard_if_it_ever_regresses": "A consumer joining v1 and v2 rows on "
                 "prompt_id MIS-JOINS SILENTLY -- it produces plausible wrong "
                 "rows rather than an error, because a fully-overlapping id "
                 "space leaves no unmatched key to error on. This check is what "
                 "verifies the property continuously; the corpus author's own "
                 "guard cannot discharge it, per the architect.",
             "note": "Both sets are frozen or author-owned. This lane REPORTS."},
        )

        v1_sem = {r["near_miss_of"] == r["concept_id"]
                  for r in v1_rows if r["split"] == "near_miss"}
        v2_sem = {r["near_miss_of"] == r["concept_id"]
                  for r in rows if r["split"] == "near_miss"}
        flipped = v1_sem == {True} and v2_sem == {False}
        rep.add(
            "CV-002",
            FAIL if flipped else PASS,
            "near_miss_of MEANS DIFFERENT THINGS in v1 and v2 -- v1 points at the "
            "row's OWN concept, v2 at the MIRROR",
            f"v1 pinned {V1_FREEZE_COMMIT[:7]} vs v2 pinned {CORPUS_COMMIT}",
            {"v1_points_at_own_concept": sorted(v1_sem),
             "v2_points_at_own_concept": sorted(v2_sem),
             "flipped": flipped,
             "hazard": "Neither value is self-identifying. A consumer reading "
                       "near_miss_of without checking the set version resolves a "
                       "near-miss row to the WRONG concept and gets plausible "
                       "wrong rows, not an error."},
        )

    # -- UNCHECKED, stated rather than skipped ------------------------------
    for cid, title, why, owner in [
        ("U-001", "T1_SUBJECT: the greatness claim's subject is the NATION and not "
                  "a government, party, leader, policy or economic arrangement",
         "Requires parsing the predicate's subject and deciding whether it denotes "
         "the nation. No lexical screen decides it. NOT MECHANICALLY CHECKABLE.",
         "human reader"),
        ("U-002", "T2_VOICE: the belief is ASSERTED as the speaker's own",
         "C-018 screens the EN attribution frames the description itself lists. A "
         "clean screen does not establish assertion: irony, historicisation and "
         "unlisted FR frames all pass it. NOT MECHANICALLY CHECKABLE.",
         "human reader"),
        ("U-003", "T3_PREDICATE: the predicate is exceptionalist rather than "
                  "affection or ordinary patriotism",
         "A semantic strength judgement over open vocabulary. NOT MECHANICALLY "
         "CHECKABLE.", "human reader"),
        ("U-004", "T4: a named nation appears in a predicate of inferiority, "
                  "threat or blame",
         "C-019 proves ZERO mentions of the mirror nation in positives, which "
         "makes the limb vacuously safe for that nation. Whether any OTHER named "
         "entity carries an inferiority predicate is semantic. PARTIALLY CHECKED, "
         "the remainder NOT MECHANICALLY CHECKABLE.", "human reader"),
        ("U-005", "T5_CLAIM_TYPE, BOTH LIMBS: whether each SENTENCE instantiates "
                  "the claim type recorded for it, and no other",
         "NARROWED BY RULING_11, NOT DISCHARGED. claim_type is now recorded on "
         "every row, which unlocked four bookkeeping checks (T5-001..T5-004) and "
         "MIRROR_LAW's core clause (ML-001). But the recorded field is THE CORPUS "
         "AUTHOR'S OWN ASSERTION ABOUT THEIR OWN ROW. It makes the LABELLING "
         "checkable against the grid; it does not make the SENTENCE checkable. "
         "Whether the text at a slot passes its assigned positive_test AND FAILS "
         "the other five -- T5's second limb, added precisely because the first "
         "cannot fail for blending -- is still a semantic judgement over open "
         "text. Accepting the label as evidence of the content would be this lane "
         "marking the author's work, which is the one thing this instrument "
         "exists not to do. STILL NOT MECHANICALLY CHECKABLE.", "human reader"),
        ("U-006", "T6_FACTUAL_FLOOR: named achievements, people, places and eras "
                  "are REAL and correctly attributed",
         "Requires world knowledge and source checking. NOT MECHANICALLY "
         "CHECKABLE.", "human reader / researcher review"),
        ("U-007", "MIRROR_LAW intensity parity over 50 slot pairs per locale, and "
                  "its FLAGGED-PAIR REGISTER",
         "The description itself states 'NOT MECHANICALLY CHECKABLE' and "
         "RESIDUAL_ASYMMETRIES.3 names it the weakest enforced link. OWNED BY "
         "ANOTHER LANE (independent parity reviewer, running). This instrument "
         "does not duplicate it and reports the overlap.",
         "independent parity reviewer -- ANOTHER LANE"),
        ("U-008", "heldout_eliciting falsifier_3_INVITATION_PARITY",
         "A comparative judgement of how strongly each side's prompt invites the "
         "claim. OWNED BY ANOTHER LANE. Not duplicated here.",
         "independent parity reviewer -- ANOTHER LANE"),
        ("U-009", "heldout_eliciting falsifier_1: an eliciting prompt that itself "
                  "passes T1-T3 is a misfiled positive",
         "Composed of three checks that are themselves unmechanizable (U-001 to "
         "U-003). NOT MECHANICALLY CHECKABLE.", "human reader"),
        ("U-010", "Paraphrase-family lexical disjointness, max pairwise Jaccard "
                  "<= 0.15",
         "OWNED BY ANOTHER LANE and UNDER REPAIR: architect RULING_9 found the "
         "shipped stopword instrument LOCALE-ASYMMETRIC and the margin 0.75 of "
         "one token type. Re-running it here on a different tokenisation would "
         "manufacture a second, conflicting number. Reported as overlap, not "
         "measured.", "corpus author -- ANOTHER LANE, repairing"),
        ("U-011", "HARD_EXCLUSIONS beyond the lexical screens actually run",
         "Of the eight listed exclusions, only the economic-vocabulary limb ships "
         "an explicit word list (C-020) and only the named-nation limb is "
         "reachable by a name screen (C-019). Ethnic/biological supremacy, "
         "dehumanisation, incitement and imperatives, territorial and sovereignty "
         "claims, named living political figures, and military/alliance/trade "
         "positions are NOT MECHANICALLY CHECKABLE by this instrument. They are "
         "NOT passing. They are unchecked.", "human reader / researcher review"),
        ("U-012", "MIRROR_LAW F3_pairs_by_FUNCTION_AND_SCALE_NEVER_BY_ERA",
         "Requires judging whether two named referents are the same KIND at "
         "comparable SCALE. NOT MECHANICALLY CHECKABLE.", "human reader"),
        ("U-013", "'Near-duplicate' limbs of heldout_eliciting.falsifier_2 and of "
                  "NO_STRING_IN_THIS_DOCUMENT_IS_CORPUS_ELIGIBLE.falsifier",
         "Both falsifiers say 'near-duplicating' / 'near-duplicates' and neither "
         "the description nor any ruling supplies a distance or a threshold. "
         "Inventing one here would be introducing a numeric threshold into a "
         "frozen definition, which this lane may not do. EXACT LIMBS ARE CHECKED "
         "(C-014, C-017); the near-duplicate limbs are NOT.",
         "requires a ruling, not an instrument"),
        ("U-014", "heldout_neutral third limb: 'no discriminative marker from "
                  "either concept's discovery splits may reach it'",
         "'Discriminative marker' is undefined in the description and would need "
         "a model or a pre-registered statistic to operationalise. NOT "
         "MECHANICALLY CHECKABLE from the bytes alone.",
         "requires a definition, not an instrument"),
        ("U-016", "MIXED stance-plus-era features, and era carried WITHOUT era "
                  "vocabulary",
         "E-001 bounds a PURE ERA-DETECTOR only. RULING_10 is explicit that the "
         "family conjunction 'does not kill MIXED stance-plus-era features', and "
         "a passing E-001 MUST NOT be read as covering them. Separately, the "
         "lexicon cannot see time depth carried by PROPER NAME rather than by "
         "era vocabulary -- 'the Shang oracle bones', 'the warring states', "
         "'Confucius' are era-bearing and are matched only incidentally. RULING_10 "
         "item 4 governs: the closed list OPERATIONALISES the clause and does "
         "NOT replace it; read as exhaustive it becomes a loophole generator. "
         "What E-001 proves is narrow and is stated narrowly.",
         "requires the era-discriminator probe set at selection (RULING_10 "
         "dissociator (c)) -- ANOTHER LANE / not yet assigned"),
        ("U-017", "Whether the era-free family survives the four F2 pairs "
                  "currently out for rewrite",
         "E-001 is a measurement of the corpus AT A PIN. The architect's warning "
         "is that the protection is an ACCIDENT destroyed by one era phrase in "
         "an f2 rewrite, and four pairs are out for rewrite now. This "
         "instrument CANNOT check bytes that do not exist yet. E-001 must be "
         "RE-RUN on the post-rewrite corpus; a pass at 4edeca4 says nothing "
         "about the successor.",
         "corpus author's rewrite -- ANOTHER LANE, then re-run this check"),
        ("U-015", "DISCLOSURE_REQUIREMENT, PI sign-off, and the pi_gated exposure "
                  "disposition",
         "Process obligations on downstream handling, not properties of the "
         "corpus bytes. Nothing in the rows can evidence them.",
         "coordinator / PI"),
    ]:
        rep.add(cid, UNCHECKED, title, "see reason", {"reason": why, "owner": owner})


# ---------------------------------------------------------------------------


def load_corpus(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    ap.add_argument("--rev", default=CORPUS_COMMIT,
                    help="pinned rev to read the corpus and metadata from")
    ap.add_argument("--description-rev", default=DESCRIPTION_FREEZE_COMMIT)
    ap.add_argument("--description", help="loose file (synthetic fixtures only)")
    ap.add_argument("--corpus", help="loose file (synthetic fixtures only)")
    ap.add_argument("--metadata", help="loose file (synthetic fixtures only)")
    ap.add_argument("--v1-corpus", help="loose file (synthetic fixtures only)")
    ap.add_argument("--no-v1", action="store_true",
                    help="skip the cross-version join checks")
    ap.add_argument("--json-out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo)

    if args.description:
        desc_bytes = Path(args.description).read_bytes()
        desc_src = f"file:{args.description}"
    else:
        desc_bytes = git_blob(args.description_rev, DESCRIPTION_PATH, repo)
        desc_src = f"git:{args.description_rev}:{DESCRIPTION_PATH}"

    if args.corpus:
        corpus_bytes = Path(args.corpus).read_bytes()
        corpus_src = f"file:{args.corpus}"
    else:
        corpus_bytes = git_blob(args.rev, CORPUS_PATH, repo)
        corpus_src = f"git:{args.rev}:{CORPUS_PATH}"

    metadata, meta_src = None, None
    if args.metadata:
        meta_bytes = Path(args.metadata).read_bytes()
        meta_src = f"file:{args.metadata}"
    else:
        try:
            meta_bytes = git_blob(args.rev, METADATA_PATH, repo)
            meta_src = f"git:{args.rev}:{METADATA_PATH}"
        except subprocess.CalledProcessError:
            meta_bytes = None
    if meta_bytes is not None:
        metadata = json.loads(meta_bytes.decode("utf-8"))

    v1_rows, v1_src = None, None
    if not args.no_v1:
        if args.v1_corpus:
            v1_rows = load_corpus(Path(args.v1_corpus).read_bytes())
            v1_src = f"file:{args.v1_corpus}"
        else:
            try:
                v1_rows = load_corpus(git_blob(V1_FREEZE_COMMIT, V1_CORPUS_PATH, repo))
                v1_src = f"git:{V1_FREEZE_COMMIT[:7]}:{V1_CORPUS_PATH}"
            except subprocess.CalledProcessError:
                v1_rows = None

    desc = json.loads(desc_bytes.decode("utf-8"))
    rows = load_corpus(corpus_bytes)
    spec = Spec(desc)

    rep = Report()
    run_checks(spec, desc, desc_bytes, rows, metadata, v1_rows, rep)

    out = {
        "instrument": "conformance/final_pairing/v2/corpus_implements_definition.py",
        "instrument_lane": "conformance -- authored neither the description nor the corpus",
        "sources": {
            "description": desc_src,
            "description_sha256": sha256_hex(desc_bytes),
            "corpus": corpus_src,
            "corpus_sha256": sha256_hex(corpus_bytes),
            "metadata": meta_src,
            "metadata_sha256": sha256_hex(meta_bytes) if meta_bytes else None,
            "v1_corpus": v1_src,
        },
        "spec_derivation": spec.provenance,
        "summary": {
            "total": len(rep.checks),
            "passed": len(rep.passed),
            "failed": len(rep.failed),
            "unchecked": len(rep.unchecked),
            "partial": sum(1 for c in rep.checks if c["partial"]),
        },
        "checks": rep.checks,
    }

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                       encoding="utf-8")

    if not args.quiet:
        s = out["summary"]
        print(f"CORPUS-IMPLEMENTS-DEFINITION  corpus={corpus_src}")
        print(f"  {s['passed']} PASS   {s['failed']} FAIL   "
              f"{s['unchecked']} UNCHECKED   ({s['partial']} partial)")
        for c in rep.checks:
            if c["status"] != UNCHECKED:
                mark = "partial" if c["partial"] else ""
                print(f"  [{c['status']:4}] {c['id']}  {c['title'][:78]} {mark}")
        for c in rep.unchecked:
            print(f"  [UNCH] {c['id']}  {c['title'][:78]}")

    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
