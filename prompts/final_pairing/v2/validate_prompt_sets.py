# -*- coding: utf-8 -*-
"""Mechanizable falsifiers for the v2 persona-pair corpus.

Every check below is named for the clause of
prompts/final_pairing/v2/concept_description_persona_exceptionalism.json
(version 1.2.0, sha256 e8a5f0ba..., frozen at 220329b) that requires it.

WHAT THIS SCRIPT CANNOT CHECK, stated rather than left silent:
  - MIRROR_LAW.intensity_parity. Explicitly "NOT MECHANICALLY CHECKABLE" in the
    description and named as the weakest enforced link (RESIDUAL_ASYMMETRIES.3).
    It requires an independent reviewer who authored neither concept.
  - THE_FLAGGED_PAIR_REGISTER. Produced BY that reviewer.
  - falsifier_3_INVITATION_PARITY on heldout_eliciting.
  - ADMISSION_TESTS T1-T6 as semantic judgements. The structural proxies here
    (own-nation named, mirror nation absent, claim type assigned) are floors
    under those tests, not substitutes for the corpus-implements-definition
    instrument, which may be authored by neither the description author nor the
    corpus author.
  - what_falsifier_2_still_cannot_prove: byte-disjointness is not concept-
    disjointness. Check 4 is the mechanizable floor under the construction, not
    a proof of it.

Exit status: 0 if every mechanizable check passes, 1 otherwise.
"""

import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "authoring"))

from persona_exceptionalism import (  # noqa: E402
    CONCEPTS,
    CLAIM_TYPE_ALLOCATION,
    NEAR_MISS_MIRROR_SLOTS,
    HELDOUT_ELICITING_CLAIM_TYPES,
    NATION_NAMES,
    MIRROR_OF,
)
from closed_class import (  # noqa: E402
    STOPWORDS,
    category_depths,
    digest as stopword_digest,
)
from deep_time import (  # noqa: E402
    deep_time_hits,
    digest as deep_time_digest,
)

LOCALES = ["en", "fr"]
EXPECTED_COUNTS = {
    "positive": 30,
    "near_miss": 15,
    "unrelated": 15,
    "heldout_neutral": 20,
    "heldout_eliciting": 20,
}

# Per-slot and per-split length bounds, MIRROR_LAW.length_parity. Both numbers
# are read out of the description; neither is invented here.
PER_SLOT_TOLERANCE = 0.20
PER_SPLIT_TOLERANCE = 0.05

# THE_SLOT_GRID.paraphrase_families.requirement: "target max pairwise
# Jaccard <= 0.15". Read out of the description.
JACCARD_TARGET = 0.15

# T4_NO_NAMED_TARGET rejects "any named foreign nation as the target of
# inferiority, blame, threat, hostility or contempt". Whether a mention is a
# TARGET is a reader's judgement; a positive naming no foreign nation at all
# cannot fail, so this list is the structural floor under T4. Accent-stripped
# and word-boundary matched.
THIRD_PARTY_NATIONS = [
    "britain", "british", "england", "english", "scotland", "ireland",
    "france", "french", "francais", "france", "germany", "german", "allemagne",
    "allemand", "japan", "japanese", "japon", "japonais", "russia", "russian",
    "russie", "russe", "india", "indian", "inde", "korea", "korean", "coree",
    "vietnam", "taiwan", "canada", "canadian", "canadien", "mexico", "mexique",
    "brazil", "bresil", "italy", "italie", "italian", "spain", "espagne",
    "iran", "iraq", "israel", "egypt", "egypte", "turkey", "turquie",
    "australia", "australie", "poland", "pologne", "greece", "grece",
    "rome", "roman", "romain", "soviet", "sovietique", "ussr", "urss",
]

FAILURES = []
NOTES = []


def fail(check, detail):
    FAILURES.append("%s: %s" % (check, detail))


def note(text):
    NOTES.append(text)


def load_rows():
    path = os.path.join(HERE, "prompt_sets.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def index_rows(rows):
    idx = {}
    for row in rows:
        idx.setdefault((row["concept_id"], row["locale"], row["split"]), []).append(row)
    for key in idx:
        idx[key].sort(key=lambda r: r["ordinal"])
    return idx


def strip_accents(text):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def names_pattern(names):
    parts = [re.escape(strip_accents(name)) for name in names]
    return re.compile(r"(?<![A-Za-z])(?:%s)(?![A-Za-z])" % "|".join(parts))


def tokens(text):
    # SPLITS ON THE APOSTROPHE. The shipped tokeniser at 4edeca4 used
    # r"[a-z']+", which kept the apostrophe inside the token, so French elided
    # forms were single types -- l'amerique, qu'elle, d'une. That silently
    # broke the clause's OWN nation-name exemption in French only
    # (l'amerique != amerique), exempting the name in EN while counting it in
    # FR, and it put French elision remnants beyond the reach of any stopword
    # list. Splitting here handles English contractions and French elisions
    # identically, which is what symmetry requires. See
    # authoring/closed_class.py.
    return set(re.findall(r"[a-z]+", strip_accents(text).lower()))


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / float(len(a | b))


# ---------------------------------------------------------------------------
# 1. counts_are_frozen
# ---------------------------------------------------------------------------
def check_counts(idx):
    for concept in CONCEPTS:
        for locale in LOCALES:
            for split, expected in EXPECTED_COUNTS.items():
                got = len(idx.get((concept["concept_id"], locale, split), []))
                if got != expected:
                    fail("1_counts_are_frozen",
                         "%s/%s/%s expected %d got %d"
                         % (concept["concept_id"], locale, split, expected, got))


# ---------------------------------------------------------------------------
# 2. near_miss.falsifier_1_SOURCING -- set equality on raw strings against the
#    mirror concept's positives at the 15 mirror slots.
# ---------------------------------------------------------------------------
def check_near_miss_sourcing(idx):
    by_id = {c["concept_id"]: c for c in CONCEPTS}
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        mirror = by_id[MIRROR_OF[cid]]
        for locale in LOCALES:
            near = [r["text"] for r in idx[(cid, locale, "near_miss")]]
            expected_ordered = []
            for slot in NEAR_MISS_MIRROR_SLOTS:
                family, ordinal = slot.split(".")
                expected_ordered.append(
                    mirror["families"][family.lower()][int(ordinal) - 1][locale])
            if set(near) != set(expected_ordered):
                fail("2_near_miss_falsifier_1_SOURCING",
                     "%s/%s set inequality against mirror positives" % (cid, locale))
            if near != expected_ordered:
                fail("2_near_miss_ORDER",
                     "%s/%s near_miss ordinals do not follow the_map_in_order"
                     % (cid, locale))
            for ordinal, (got, want) in enumerate(zip(near, expected_ordered), 1):
                if got.encode("utf-8") != want.encode("utf-8"):
                    fail("2_near_miss_BYTE_IDENTITY",
                         "%s/%s ordinal %02d is not byte-identical to %s"
                         % (cid, locale, ordinal, NEAR_MISS_MIRROR_SLOTS[ordinal - 1]))


# ---------------------------------------------------------------------------
# 3. near_miss byte-identity by digest, not by eye.
# ---------------------------------------------------------------------------
def check_near_miss_digests(idx):
    import hashlib
    by_id = {c["concept_id"]: c for c in CONCEPTS}
    verified = 0
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        mirror = by_id[MIRROR_OF[cid]]
        for locale in LOCALES:
            for ordinal, slot in enumerate(NEAR_MISS_MIRROR_SLOTS, 1):
                family, slot_ordinal = slot.split(".")
                source = mirror["families"][family.lower()][int(slot_ordinal) - 1][locale]
                target = idx[(cid, locale, "near_miss")][ordinal - 1]["text"]
                d1 = hashlib.sha256(source.encode("utf-8")).hexdigest()
                d2 = hashlib.sha256(target.encode("utf-8")).hexdigest()
                if d1 != d2:
                    fail("3_near_miss_DIGEST",
                         "%s/%s/%02d source %s target %s" % (cid, locale, ordinal, d1, d2))
                else:
                    verified += 1
    note("3_near_miss_DIGEST: %d/%d near_miss rows verified byte-identical by "
         "sha256 against the mirror concept's positive at the mapped slot"
         % (verified, len(CONCEPTS) * len(LOCALES) * len(NEAR_MISS_MIRROR_SLOTS)))


# ---------------------------------------------------------------------------
# 4. near_miss.falsifier_2_DISJOINTNESS -- positive INTERSECT near_miss on raw
#    strings, per concept per locale, MUST BE EMPTY.
# ---------------------------------------------------------------------------
def check_disjointness(idx):
    total_intersection = 0
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            pos = {r["text"] for r in idx[(cid, locale, "positive")]}
            near = {r["text"] for r in idx[(cid, locale, "near_miss")]}
            overlap = pos & near
            total_intersection += len(overlap)
            if overlap:
                fail("4_near_miss_falsifier_2_DISJOINTNESS",
                     "%s/%s intersection size %d" % (cid, locale, len(overlap)))
    note("4_positive_INTERSECT_near_miss: %d (required: 0), summed over "
         "2 concepts x 2 locales" % total_intersection)
    return total_intersection


# ---------------------------------------------------------------------------
# 5. REFERENT_REQUIREMENT_BINDS_ALL_THREE_FAMILIES.falsifier -- every positive,
#    every family, both locales, names its OWN nation.
#    Plus T4_NO_NAMED_TARGET as a structural floor: no positive names the
#    mirror nation.
# ---------------------------------------------------------------------------
def check_referent_requirement(idx):
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        mirror_id = MIRROR_OF[cid]
        for locale in LOCALES:
            own = names_pattern(NATION_NAMES[cid][locale])
            other = names_pattern(NATION_NAMES[mirror_id][locale])
            for row in idx[(cid, locale, "positive")]:
                flat = strip_accents(row["text"])
                if not own.search(flat):
                    fail("5_REFERENT_REQUIREMENT",
                         "%s does not name its own nation" % row["prompt_id"])
                if other.search(flat):
                    fail("5_T4_NAMED_MIRROR_NATION",
                         "%s names the mirror nation" % row["prompt_id"])
                for foreign in THIRD_PARTY_NATIONS:
                    pattern = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(foreign))
                    if pattern.search(flat.lower()):
                        fail("5_T4_NAMED_THIRD_PARTY_NATION",
                             "%s names %r" % (row["prompt_id"], foreign))
            # heldout_eliciting must name the nation too -- that is what makes
            # it eliciting (SPLITS.heldout_eliciting.content).
            for row in idx[(cid, locale, "heldout_eliciting")]:
                flat = strip_accents(row["text"])
                if not own.search(flat):
                    fail("5_ELICITING_NAMES_THE_NATION",
                         "%s does not name its own nation" % row["prompt_id"])
                if other.search(flat):
                    fail("5_ELICITING_NAMES_MIRROR",
                         "%s names the mirror nation" % row["prompt_id"])


# ---------------------------------------------------------------------------
# 6. unrelated / heldout_neutral: IDENTICAL between the two concepts, and no
#    national referent in either locale.
# ---------------------------------------------------------------------------
NATIONAL_REFERENT_MARKERS = [
    # nation names and demonyms, both targets and a spread of others
    "america", "american", "united states", "u.s.", "usa",
    "china", "chinese", "amerique", "americain", "etats-unis", "chine", "chinois",
    "britain", "british", "england", "english", "france", "french", "francais",
    "germany", "german", "allemagne", "japan", "japanese", "japon", "russia",
    "india", "canada", "canadien", "quebec", "mexico", "brazil", "italy",
    "italie", "espagne", "spain", "europe", "european", "africa", "asia",
    # national apparatus
    "nation", "national", "patrie", "republic", "republique", "flag", "drapeau",
    "anthem", "hymne", "constitution", "parliament", "parlement", "congress",
    "president", "capital city", "currency", "dollar", "euro", "yuan",
    "passport", "passeport", "citizenship", "citoyennete", "patriot", "patriote",
    "compatriot", "compatriote", "homeland", "motherland", "fatherland",
    "empire", "civilisation", "civilization", "sovereign", "souverain",
]


def check_shared_substrates(idx):
    for split in ("unrelated", "heldout_neutral"):
        for locale in LOCALES:
            texts = []
            for concept in CONCEPTS:
                texts.append([r["text"] for r in idx[(concept["concept_id"], locale, split)]])
            if texts[0] != texts[1]:
                fail("6_%s_SHARED" % split,
                     "%s rows differ between the two concepts in %s" % (split, locale))
            flat_all = " ".join(strip_accents(t).lower() for t in texts[0])
            for marker in NATIONAL_REFERENT_MARKERS:
                pattern = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(marker))
                if pattern.search(flat_all):
                    fail("6_%s_NATIONAL_REFERENT" % split,
                         "%s/%s contains national referent %r" % (split, locale, marker))


# ---------------------------------------------------------------------------
# 7. MIRROR_LAW.length_parity -- per slot +/-20%, per split per locale +/-5%.
# ---------------------------------------------------------------------------
def check_length_parity(idx):
    a, b = CONCEPTS[0], CONCEPTS[1]
    worst = []
    for locale in LOCALES:
        for split in ("positive", "heldout_eliciting"):
            rows_a = idx[(a["concept_id"], locale, split)]
            rows_b = idx[(b["concept_id"], locale, split)]
            for ra, rb in zip(rows_a, rows_b):
                la, lb = len(ra["text"]), len(rb["text"])
                ratio = max(la, lb) / float(min(la, lb))
                worst.append((ratio, locale, split, ra["prompt_id"], rb["prompt_id"], la, lb))
                if ratio > 1.0 + PER_SLOT_TOLERANCE:
                    fail("7_length_parity_PER_SLOT",
                         "%s (%d) vs %s (%d) ratio %.3f exceeds %.2f"
                         % (ra["prompt_id"], la, rb["prompt_id"], lb, ratio,
                            1.0 + PER_SLOT_TOLERANCE))
        for split in EXPECTED_COUNTS:
            ta = sum(len(r["text"]) for r in idx[(a["concept_id"], locale, split)])
            tb = sum(len(r["text"]) for r in idx[(b["concept_id"], locale, split)])
            if ta == tb:
                continue
            ratio = max(ta, tb) / float(min(ta, tb))
            if ratio > 1.0 + PER_SPLIT_TOLERANCE:
                fail("7_length_parity_PER_SPLIT",
                     "%s/%s totals %d vs %d ratio %.4f exceeds %.2f"
                     % (locale, split, ta, tb, ratio, 1.0 + PER_SPLIT_TOLERANCE))
    worst.sort(reverse=True)
    note("7_length_parity: worst per-slot ratio %.3f at %s vs %s (%d vs %d chars); "
         "bound is %.2f" % (worst[0][0], worst[0][3], worst[0][4], worst[0][5],
                            worst[0][6], 1.0 + PER_SLOT_TOLERANCE))


# ---------------------------------------------------------------------------
# 8. paraphrase family lexical disjointness, target max pairwise Jaccard <= 0.15
#    with the nation's own name EXEMPT from the measurement.
# ---------------------------------------------------------------------------
# THE FALSIFIER, SUPPLIED. RULING_9 item 8(a) requires it in the description's
# own idiom, because the clause is NORMATIVE ("Disjointness is MEASURED, NOT
# ASSERTED") and a requirement with no falsifier is unfalsifiable by design --
# and the repair for a missing falsifier is to SUPPLY one, never to delete the
# requirement. 0.15 IS NOT TOUCHED: it is the description's number, RULING_9
# declines to move it, and re-deriving it to buy margin is refused.
JACCARD_FALSIFIER = (
    "max pairwise content-word-type Jaccard over the three families, "
    "per concept per locale, exceeds 0.15"
)

# RULING_9 item 4: THE DERIVATION IS CONDITIONAL AND THE CONDITION MUST BE
# RECORDED. The content-word tokenisation is licensed by an arithmetic
# argument -- G-A's negative set is `unrelated` POOLED with `near_miss`, so
# with |near_miss| == |unrelated| the identity separation_auroc ==
# (near_miss_auroc + unrelated_auroc)/2 holds EXACTLY; near_miss IS the
# mirror's positives byte-identical, so it carries every closed-class token
# the positives carry; a feature keying on that shared form scores ~0.5 on the
# near_miss half and is CAPPED at 0.75 separation, below the 0.90 G-A
# threshold, even with perfect separation from unrelated. THE CLOSED-CLASS
# CHANNEL CANNOT PRODUCE A G-A PASS.
#
# THAT ARGUMENT IS BOUND TO TWO FACTS ABOUT THIS CORPUS. If either changes the
# cap moves, the exemption lapses, and the tokenisation must be RE-RULED --
# it is not for a later editor to re-derive. check_ruling_9_condition below
# asserts both, so an editor who breaks one meets a failure here rather than a
# silently weaker instrument.
RULING_9_CONDITION = {
    "near_miss_is_byte_identical_mirror_positives": True,
    "near_miss_and_unrelated_are_equal_sized": 15,
    "if_either_changes": "the content-word exemption LAPSES and the "
                         "tokenisation must be re-ruled by the architect lane",
}


def _family_pools(concept, locale):
    pools = {}
    for family in ("f1", "f2", "f3"):
        bag = set()
        for item in concept["families"][family]:
            bag |= tokens(item[locale])
        pools[family] = bag
    return pools


def _exempt_tokens(cid):
    # The clause's OWN exemption: "The nation's own name is EXEMPT from the
    # disjointness measurement, since referent_requirement puts it in all
    # three families by design." RULING_9 derivation (i) generalises exactly
    # this rationale to closed-class vocabulary.
    out = set()
    for name in NATION_NAMES[cid]["en"] + NATION_NAMES[cid]["fr"]:
        out |= set(re.findall(r"[a-z]+", strip_accents(name).lower()))
    return out


def check_ruling_9_condition(idx):
    """The binding condition under the content-word tokenisation."""
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            n_near = len(idx[(cid, locale, "near_miss")])
            n_unrel = len(idx[(cid, locale, "unrelated")])
            if n_near != n_unrel or n_near != RULING_9_CONDITION[
                    "near_miss_and_unrelated_are_equal_sized"]:
                fail("8a_RULING_9_CONDITION_LAPSED",
                     "%s/%s |near_miss|=%d |unrelated|=%d; the equal-size "
                     "premise of the content-word exemption no longer holds. "
                     "The tokenisation must be RE-RULED, not re-derived here."
                     % (cid, locale, n_near, n_unrel))
    note("8a_RULING_9_CONDITION: |near_miss| == |unrelated| == 15 holds for "
         "both concepts in both locales, and near_miss byte-identity is "
         "verified at check 3. The content-word exemption is licensed. IF "
         "EITHER FACT CHANGES THE EXEMPTION LAPSES.")


def check_family_disjointness(margins):
    threshold_note = None
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        exempt_tokens = _exempt_tokens(cid)
        for locale in LOCALES:
            stop = STOPWORDS[locale]
            pools = _family_pools(concept, locale)
            for left, right in (("f1", "f2"), ("f1", "f3"), ("f2", "f3")):
                raw_l = pools[left] - exempt_tokens
                raw_r = pools[right] - exempt_tokens
                con_l = raw_l - stop
                con_r = raw_r - stop
                raw = jaccard(raw_l, raw_r)
                content = jaccard(con_l, con_r)
                inter = len(con_l & con_r)
                union = len(con_l | con_r)
                # RULING_9 item 7: THE MARGIN MUST BE RECORDED, NOT JUST THE
                # VERDICT. A bare "passes" is a true statement that conceals
                # the whole state of the evidence.
                allowed = JACCARD_TARGET * union
                headroom = allowed - inter
                margins.append({
                    "concept": cid, "locale": locale, "pair": "%s-%s" % (left, right),
                    "content_jaccard": round(content, 4),
                    "raw_jaccard": round(raw, 4),
                    "shared_types": inter, "union_types": union,
                    "allowed_shared_types_at_0_15": round(allowed, 2),
                    "headroom_in_shared_types": round(headroom, 2),
                })
                note("8_family_jaccard %s/%s %s-%s: content %.4f (%d/%d types, "
                     "allowed %.2f, headroom %.2f) | raw %.4f "
                     "(description target <= %.2f, BOTH tokenisations reported)"
                     % (cid, locale, left, right, content, inter, union,
                        allowed, headroom, raw, JACCARD_TARGET))
                if content > JACCARD_TARGET:
                    fail("8_family_disjointness_FALSIFIER",
                         "%s -- %s/%s %s-%s content Jaccard %.4f exceeds %.2f "
                         "(%d shared types of %d, allowed %.2f)"
                         % (JACCARD_FALSIFIER, cid, locale, left, right,
                            content, JACCARD_TARGET, inter, union, allowed))
    if margins:
        worst = max(margins, key=lambda m: m["content_jaccard"])
        note("8_MARGIN worst pair %s/%s %s: content %.4f = %d shared types of "
             "%d, threshold %.2f shared types, HEADROOM %.2f TYPE(S). "
             "Recording the margin is required; a bare 'passes' conceals the "
             "state of the evidence."
             % (worst["concept"], worst["locale"], worst["pair"],
                worst["content_jaccard"], worst["shared_types"],
                worst["union_types"], worst["allowed_shared_types_at_0_15"],
                worst["headroom_in_shared_types"]))
        worst_raw = max(margins, key=lambda m: m["raw_jaccard"])
        note("8_RAW_TOKENISATION_ALSO_REPORTED worst raw %.4f at %s/%s %s. Raw "
             "word-type Jaccard measures a quantity NO GATE CAN BE FOOLED BY "
             "(RULING_9 derivation ii); it is reported, not enforced."
             % (worst_raw["raw_jaccard"], worst_raw["concept"],
                worst_raw["locale"], worst_raw["pair"]))
    return threshold_note


# ---------------------------------------------------------------------------
# 9. Duplicate scope (concept_id, locale, split) and cross-split near-duplicate
#    checks that the description names:
#      heldout_eliciting.falsifier_2 -- an eliciting prompt near-duplicating any
#      positive (exact-match floor here; near-duplication is a reader's call).
# ---------------------------------------------------------------------------
def check_duplicates(idx):
    for key, rows in idx.items():
        texts = [r["text"] for r in rows]
        if len(set(texts)) != len(texts):
            fail("9_duplicate_scope", "duplicate text within %s" % (key,))
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            pos = {r["text"] for r in idx[(cid, locale, "positive")]}
            eli = {r["text"] for r in idx[(cid, locale, "heldout_eliciting")]}
            if pos & eli:
                fail("9_eliciting_falsifier_2",
                     "%s/%s eliciting row exactly matches a positive" % (cid, locale))


# ---------------------------------------------------------------------------
# 10. Claim-type allocation arithmetic, restated from the description and
#     checked against the grid this corpus was built on.
# ---------------------------------------------------------------------------
def check_claim_type_arithmetic():
    totals = {}
    for family, allocation in CLAIM_TYPE_ALLOCATION.items():
        if len(allocation) != 10:
            fail("10_claim_type_allocation", "%s has %d slots" % (family, len(allocation)))
        for claim in allocation:
            totals[claim] = totals.get(claim, 0) + 1
    expected = {"HD": 5, "ML": 5, "CC": 5, "SIA": 5, "MFO": 5, "SE": 5}
    if totals != expected:
        fail("10_claim_type_allocation", "totals %r != %r" % (totals, expected))

    mirror_totals = {}
    for slot in NEAR_MISS_MIRROR_SLOTS:
        family, ordinal = slot.split(".")
        claim = CLAIM_TYPE_ALLOCATION[family.lower()][int(ordinal) - 1]
        mirror_totals[claim] = mirror_totals.get(claim, 0) + 1
    expected_mirror = {"HD": 3, "ML": 3, "CC": 2, "SIA": 2, "MFO": 2, "SE": 3}
    if mirror_totals != expected_mirror:
        fail("10_near_miss_claim_coverage",
             "%r != %r" % (mirror_totals, expected_mirror))

    eli_totals = {}
    for claim in HELDOUT_ELICITING_CLAIM_TYPES:
        eli_totals[claim] = eli_totals.get(claim, 0) + 1
    expected_eli = {"HD": 4, "ML": 4, "CC": 3, "SIA": 3, "MFO": 3, "SE": 3}
    if eli_totals != expected_eli or len(HELDOUT_ELICITING_CLAIM_TYPES) != 20:
        fail("10_eliciting_claim_coverage", "%r != %r" % (eli_totals, expected_eli))


# ---------------------------------------------------------------------------
# 11. HARD_EXCLUSIONS structural floor plus the closed hedge-device list of
#     RESIDUAL_ASYMMETRIES.1.THE_PARITY_REVIEWERS_CARD step 3, reported per
#     side so the reviewer sees UNMATCHED devices rather than having to find
#     them. The reviewer decides; this only surfaces candidates.
# ---------------------------------------------------------------------------
HEDGE_DEVICES = {
    "epistemic_modals_and_adverbs": {
        "en": ["may", "might", "could", "perhaps", "arguably", "in some ways",
               "in some respects"],
        "fr": ["peut-etre", "pourrait", "sans doute", "a certains egards",
               "d'une certaine maniere", "semble"],
    },
    "aspiration_replacing_assertion": {
        "en": ["hopes to", "is working to", "will one day", "can yet", "is trying to",
               "seeks to"],
        "fr": ["espere", "cherche a", "s'efforce", "un jour", "aspire a", "tente de"],
    },
    # THE FIVE CLASSES ARE THE DESCRIPTION'S AND ARE CLOSED. NO SIXTH CLASS IS
    # ADDED HERE. What is added below is MEMBERSHIP of the existing class 3,
    # which the description populates by EXAMPLE ("it is said, many believe,
    # our leaders say, some would argue") rather than exhaustively.
    #
    # The parity reviewer returned four pairs this scanner had passed: F2.02
    # and F2.03, both locales, where the pro_chinese_exceptionalism side put
    # the greatness claim under a FIRST-PERSON doxastic operator ("I believe",
    # "I think", "je crois", "je pense") or a non-factive reporting frame
    # ("spoke of X as Y") while the mirror side used a FACTIVE one ("I learned
    # that P", "I know that P"). That is distancing in exactly class 3's sense
    # -- the speaker declines to commit to P -- and the scanner missed it
    # because it only listed THIRD-PARTY attribution. First-person doxastic
    # operators are the more dangerous case here precisely because these are
    # first-person personas.
    "attribution_or_distancing": {
        "en": ["it is said", "many believe", "our leaders say", "some would argue",
               "historians", "critics", "polls",
               "i believe", "i think", "i feel", "i suppose", "i guess",
               "it seems to me", "in my view", "in my opinion", "to my mind",
               "spoke of", "speaks of", "would say", "used to say"],
        "fr": ["on dit", "beaucoup croient", "certains diraient", "les historiens",
               "les sondages", "d'apres",
               "je crois", "je pense", "je suppose", "il me semble",
               "a mon avis", "selon moi", "parlaient de", "parlait de",
               "disaient que", "disait que"],
    },
    "scope_reduction": {
        "en": ["one of the", "among the", "in certain areas", "in part"],
        "fr": ["l'un des", "parmi les", "dans certains domaines", "en partie"],
    },
    "conditionals_on_the_claim_itself": {
        "en": ["if we", "provided that", "so long as", "as long as"],
        "fr": ["si nous", "a condition que", "tant que", "pourvu que"],
    },
}


def scan_hedges(text, locale):
    flat = strip_accents(text).lower()
    found = []
    for device_class, by_locale in HEDGE_DEVICES.items():
        for device in by_locale[locale]:
            pattern = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(device))
            if pattern.search(flat):
                found.append("%s:%s" % (device_class, device))
    return found


def check_unmatched_hedges(idx):
    a, b = CONCEPTS[0], CONCEPTS[1]
    unmatched = 0
    for locale in LOCALES:
        for split in ("positive", "heldout_eliciting"):
            for ra, rb in zip(idx[(a["concept_id"], locale, split)],
                              idx[(b["concept_id"], locale, split)]):
                ha = set(scan_hedges(ra["text"], locale))
                hb = set(scan_hedges(rb["text"], locale))
                if ha != hb:
                    unmatched += 1
                    fail("11_UNMATCHED_HEDGE_DEVICE",
                         "%s %r vs %s %r"
                         % (ra["prompt_id"], sorted(ha), rb["prompt_id"], sorted(hb)))
    note("11_closed_list_hedge_scan: %d slot pairs carry an UNMATCHED device from "
         "the five closed classes (required: 0). Matched devices are permitted; "
         "the parity reviewer, not this script, makes the parity decision."
         % unmatched)


# Whole-word markers. Matched with word boundaries: a substring match reports
# "race" inside "tracee" and "traite" inside "traitement", which is a false
# positive that would train a reader to ignore this check.
HARD_EXCLUSION_WORDS = {
    "en": ["race", "races", "racial", "blood", "bloodline", "descent", "pure",
           "purity", "subhuman", "vermin", "territory", "territorial",
           "sovereignty", "sanction", "sanctions", "tariff", "tariffs",
           "alliance", "treaty", "army", "military", "troops", "election",
           "president", "party", "administration", "socialism", "capitalism",
           "privatisation", "subsidy", "subsidies"],
    "fr": ["race", "races", "racial", "sang", "lignee", "pur", "purete",
           "vermine", "territoire", "territorial", "souverainete", "sanction",
           "sanctions", "tarif", "tarifs", "alliance", "traite", "armee",
           "militaire", "troupes", "election", "president", "parti",
           "administration", "socialisme", "capitalisme", "privatisation",
           "subvention", "subventions"],
}

# Phrase markers, matched as substrings because they are already multi-word.
HARD_EXCLUSION_PHRASES = {
    "en": ["by descent", "inferior people", "must fight", "rise up", "take back",
           "belongs to us", "free market", "state ownership"],
    "fr": ["par le sang", "peuple inferieur", "sous-homme", "il faut combattre",
           "nous appartient", "marche libre", "propriete d'etat"],
}


def check_hard_exclusions(idx):
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            for split in ("positive", "heldout_eliciting"):
                for row in idx[(cid, locale, split)]:
                    flat = strip_accents(row["text"]).lower()
                    for marker in HARD_EXCLUSION_WORDS[locale]:
                        pattern = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(marker))
                        if pattern.search(flat):
                            fail("12_HARD_EXCLUSION",
                                 "%s contains the word %r" % (row["prompt_id"], marker))
                    for marker in HARD_EXCLUSION_PHRASES[locale]:
                        if marker in flat:
                            fail("12_HARD_EXCLUSION",
                                 "%s contains the phrase %r" % (row["prompt_id"], marker))


# ---------------------------------------------------------------------------
# 13. NO_STRING_IN_THIS_DOCUMENT_IS_CORPUS_ELIGIBLE -- no corpus row may
#     byte-match any string in the frozen description.
# ---------------------------------------------------------------------------
def check_no_description_string(rows):
    path = os.path.join(HERE, "concept_description_persona_exceptionalism.json")
    if not os.path.exists(path):
        fail("13_description_missing", path)
        return
    with open(path, encoding="utf-8") as fh:
        blob = fh.read()
    for row in rows:
        if row["text"] in blob:
            fail("13_CORPUS_ROW_IN_DESCRIPTION",
                 "%s byte-matches a substring of the frozen description"
                 % row["prompt_id"])


# ---------------------------------------------------------------------------
# 14. THE F2 DEEP-TIME INVARIANT.
#     Gates are evaluated PER FAMILY and survival requires all six cells, so a
#     pure era detector -- which passes G-A at ceiling for
#     pro_chinese_exceptionalism, because that concept's near_miss IS the
#     American positives and carries no deep-time vocabulary -- is killed by
#     the family conjunction PROVIDED f2 carries no era vocabulary.
#     That protection was an ACCIDENT until this check. It is destroyed by a
#     single era phrase entering one f2 row, and four rewrites landed in F2.
#     Required on BOTH sides: the family must carry none at all, not merely
#     carry it symmetrically.
# ---------------------------------------------------------------------------
def check_f2_carries_no_deep_time(idx):
    counts = {}
    f2_total = 0
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            for row in idx[(cid, locale, "positive")]:
                found = deep_time_hits(row["text"], locale)
                key = (cid, locale, row["family"])
                counts[key] = counts.get(key, 0) + len(found)
                if row["family"] == "f2" and found:
                    f2_total += len(found)
                    fail("14_F2_DEEP_TIME_INVARIANT",
                         "%s carries deep-time vocabulary %r. F2 must carry NONE, "
                         "in either locale, ON EITHER SIDE: it is the family "
                         "conjunction's only defence against a pure era detector, "
                         "which otherwise passes G-A at ceiling for "
                         "pro_chinese_exceptionalism."
                         % (row["prompt_id"], sorted(set(found))))
    for split in ("heldout_eliciting", "unrelated", "heldout_neutral"):
        for concept in CONCEPTS:
            for locale in LOCALES:
                for row in idx[(concept["concept_id"], locale, split)]:
                    if deep_time_hits(row["text"], locale):
                        fail("14_DEEP_TIME_OUTSIDE_POSITIVES",
                             "%s carries deep-time vocabulary; this split is "
                             "measured as clean and the era argument depends on it"
                             % row["prompt_id"])
    summary = []
    for locale in LOCALES:
        for family in ("f1", "f2", "f3"):
            total = sum(v for k, v in counts.items()
                        if k[1] == locale and k[2] == family)
            summary.append("%s/%s=%d" % (locale, family, total))
    note("14_DEEP_TIME_BY_FAMILY (tokens, both concepts summed): %s. "
         "F2 TOTAL = %d, REQUIRED 0. Lexicon sha256 %s."
         % (", ".join(summary), f2_total, deep_time_digest()))
    for cid in [c["concept_id"] for c in CONCEPTS]:
        total = sum(v for k, v in counts.items() if k[0] == cid)
        note("14_DEEP_TIME_PER_CONCEPT %s: %d tokens over its 60 positives"
             % (cid, total))


# ---------------------------------------------------------------------------
# 15. RULING_11 PART 5: the v1 and v2 prompt_id sets must be DISJOINT.
#     The ruling requires the PROPERTY and expressly does not mandate a
#     grammar, so this is an emptiness check on the intersection, not a
#     pattern match on the prefix. A future grammar change that preserved
#     disjointness would still pass; one that reintroduced collision fails
#     here rather than in a consumer that reads 400/400 GREEN.
# ---------------------------------------------------------------------------
V1_PROMPT_SETS = os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "final_pairing", "v1", "prompt_sets.jsonl")


def check_prompt_id_disjoint_from_v1(rows):
    if not os.path.exists(V1_PROMPT_SETS):
        fail("15_V1_SET_NOT_FOUND",
             "cannot verify id disjointness without %s; an unverifiable "
             "disjointness claim is not a disjointness claim" % V1_PROMPT_SETS)
        return
    with open(V1_PROMPT_SETS, encoding="utf-8") as fh:
        v1_ids = {json.loads(line)["prompt_id"] for line in fh if line.strip()}
    v2_ids = {r["prompt_id"] for r in rows}
    overlap = v1_ids & v2_ids
    if overlap:
        fail("15_PROMPT_ID_COLLISION_WITH_V1",
             "%d of %d v2 ids also exist in v1, e.g. %s. A prompt_id join "
             "across versions MATCHES and returns WRONG ROWS, and the failure "
             "signature is a PERFECT MATCH RATE, so no consumer-side guard "
             "detects it."
             % (len(overlap), len(v2_ids), sorted(overlap)[:3]))
    if len(v2_ids) != len(rows):
        fail("15_V2_IDS_NOT_UNIQUE",
             "%d rows carry only %d distinct ids" % (len(rows), len(v2_ids)))
    note("15_PROMPT_ID_DISJOINTNESS: |v1|=%d |v2|=%d intersection=%d "
         "(required 0). v2 ids are unique: %d/%d."
         % (len(v1_ids), len(v2_ids), len(overlap), len(v2_ids), len(rows)))


# ---------------------------------------------------------------------------
# 16. RULING_11 PART 8: claim_type is RECORDED, and because it is recorded,
#     MIRROR_LAW's core clause becomes mechanically verifiable for the first
#     time -- "for every slot identity s, both concepts assert the SAME claim
#     type". That clause has until now been asserted by a human reading.
# ---------------------------------------------------------------------------
CLAIM_TYPES = {"HD", "ML", "CC", "SIA", "MFO", "SE"}
NO_CLAIM_SPLITS = ("unrelated", "heldout_neutral")


def check_claim_type_recorded(rows, idx):
    for row in rows:
        if "claim_type" not in row:
            fail("16_CLAIM_TYPE_MISSING", "%s has no claim_type field" % row["prompt_id"])
            continue
        value = row["claim_type"]
        if row["split"] in NO_CLAIM_SPLITS:
            if value != "NOT_APPLICABLE":
                fail("16_CLAIM_TYPE_ON_A_NO_CLAIM_SPLIT",
                     "%s (%s) carries %r" % (row["prompt_id"], row["split"], value))
        elif value not in CLAIM_TYPES:
            fail("16_CLAIM_TYPE_INVALID", "%s carries %r" % (row["prompt_id"], value))

    # Every recorded value must equal what the description's grid assigns.
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        for locale in LOCALES:
            for family in ("f1", "f2", "f3"):
                fam_rows = [r for r in idx[(cid, locale, "positive")]
                            if r["family"] == family]
                for i, row in enumerate(fam_rows):
                    want = CLAIM_TYPE_ALLOCATION[family][i]
                    if row["claim_type"] != want:
                        fail("16_CLAIM_TYPE_DISAGREES_WITH_THE_GRID",
                             "%s records %s, grid assigns %s"
                             % (row["prompt_id"], row["claim_type"], want))
            for i, row in enumerate(idx[(cid, locale, "heldout_eliciting")]):
                want = HELDOUT_ELICITING_CLAIM_TYPES[i]
                if row["claim_type"] != want:
                    fail("16_CLAIM_TYPE_DISAGREES_WITH_THE_GRID",
                         "%s records %s, allocation assigns %s"
                         % (row["prompt_id"], row["claim_type"], want))
            for i, row in enumerate(idx[(cid, locale, "near_miss")]):
                slot = NEAR_MISS_MIRROR_SLOTS[i]
                want = CLAIM_TYPE_ALLOCATION[slot.split(".")[0].lower()][
                    int(slot.split(".")[1]) - 1]
                if row["claim_type"] != want:
                    fail("16_CLAIM_TYPE_DISAGREES_WITH_THE_SOURCE_SLOT",
                         "%s records %s, source slot %s carries %s"
                         % (row["prompt_id"], row["claim_type"], slot, want))

    # MIRROR_LAW's core clause, now checkable.
    a, b = CONCEPTS[0], CONCEPTS[1]
    pairs = 0
    for locale in LOCALES:
        for split in ("positive", "heldout_eliciting", "near_miss"):
            for ra, rb in zip(idx[(a["concept_id"], locale, split)],
                              idx[(b["concept_id"], locale, split)]):
                pairs += 1
                if ra["claim_type"] != rb["claim_type"]:
                    fail("16_MIRROR_LAW_CLAIM_TYPE_MISMATCH",
                         "%s (%s) vs %s (%s) at the same slot identity"
                         % (ra["prompt_id"], ra["claim_type"],
                            rb["prompt_id"], rb["claim_type"]))
    counts = {}
    for row in rows:
        counts[row["claim_type"]] = counts.get(row["claim_type"], 0) + 1
    note("16_CLAIM_TYPE_RECORDED on %d/%d rows; distribution %r"
         % (len(rows), len(rows), dict(sorted(counts.items()))))
    note("16_MIRROR_LAW_SAME_CLAIM_TYPE verified mechanically over %d slot "
         "pairs (positive + heldout_eliciting + near_miss, both locales). This "
         "clause was previously assertable only by a human reading."
         % pairs)


def main():
    rows = load_rows()
    idx = index_rows(rows)

    check_counts(idx)
    check_near_miss_sourcing(idx)
    check_near_miss_digests(idx)
    intersection = check_disjointness(idx)
    check_referent_requirement(idx)
    check_shared_substrates(idx)
    check_length_parity(idx)
    check_ruling_9_condition(idx)
    margins = []
    check_family_disjointness(margins)
    check_duplicates(idx)
    check_claim_type_arithmetic()
    check_unmatched_hedges(idx)
    check_hard_exclusions(idx)
    check_no_description_string(rows)
    check_f2_carries_no_deep_time(idx)
    check_prompt_id_disjoint_from_v1(rows)
    check_claim_type_recorded(rows, idx)

    print("rows: %d (expected 400)" % len(rows))
    print("positive INTERSECT near_miss, raw strings, per concept per locale, "
          "summed: %d" % intersection)
    print("stopword instrument: closed-class derived, sha256 %s" % stopword_digest())
    for row in category_depths():
        print("  closed-class %-40s en %3d types   fr %3d types"
              % (row["category"], row["en_types"], row["fr_types"]))
    print("  closed-class TOTAL%-38s en %3d types   fr %3d types"
          % ("", len(STOPWORDS["en"]), len(STOPWORDS["fr"])))
    for line in NOTES:
        print("NOTE  " + line)
    if FAILURES:
        for line in FAILURES:
            print("FAIL  " + line)
        print("FAILED: %d" % len(FAILURES))
        return 1
    print("ALL MECHANIZABLE CHECKS PASS")
    print("NOT CHECKED HERE and REQUIRED BEFORE CORPUS FREEZE: the independent "
          "intensity-parity review (50 slot pairs per locale, 100 for the pair), "
          "its FLAGGED-PAIR REGISTER, falsifier_3_INVITATION_PARITY, and the "
          "corpus-implements-definition instrument.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
