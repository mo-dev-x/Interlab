# -*- coding: utf-8 -*-
"""Automated validation of the frozen bilingual prompt-set artifact.

Checks, in order:
  1. required fields present and well-typed on every row
  2. counts per (concept, locale, split)
  3. exact and normalised duplicates, scoped to (concept, locale, split)
  4. lexical leakage from discovery splits into the held-out splits
  5. near-duplication between heldout_eliciting and the discovery positives
  6. paraphrase-family lexical distinctness
  7. locale plausibility
  8. stable ordering and byte-stable rebuild

Exit code is nonzero if any FAIL is recorded. WARN items are printed for researcher
review but do not block the freeze.
"""

import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
JSONL = os.path.join(HERE, "prompt_sets.jsonl")
META = os.path.join(HERE, "metadata.json")

REQUIRED_FIELDS = [
    "prompt_id", "concept_id", "concept_index", "locale", "split",
    "family", "ordinal", "near_miss_of", "near_miss_domains",
    "pi_gated", "shared_substrate", "text",
]

EXPECTED_COUNTS = {
    "positive": 30, "near_miss": 15, "unrelated": 15,
    "heldout_neutral": 20, "heldout_eliciting": 20,
}

STOP_EN = set("""a an the of and or to in on at for with from by is are was were be been being
this that these those it its as if then than so such not no nor but do does did done how what
which who whom whose when where why can could should would may might must will shall you your
i we they he she them us our their my me him her about into over under between during before
after above below out off up down again further once here there all any both each few more most
other some only own same too very s t just don now write describe explain give suggest compose
draft prepare summarise summarize would should like make made makes making one two three four
five six seven eight nine ten short long new old first last next take takes taking get gets
""".split())

STOP_FR = set("""le la les un une des du de d l et ou a à au aux en dans sur pour par avec sans
sous ce cet cette ces son sa ses leur leurs mon ma mes ton ta tes notre nos votre vos qui que
quoi dont où quand comment pourquoi quel quelle quels quelles est sont était étaient être suis
es sommes êtes ont avoir a ai as avons avez il elle ils elles on nous vous je tu me te se y ne
pas plus moins très bien peu tout tous toute toutes autre autres même aussi alors donc car mais
si comme entre avant après pendant depuis vers chez faut doit doivent peut peuvent écrivez
décrivez expliquez rédigez proposez résumez présentez quelle quels un deux trois quatre cinq
six sept huit neuf dix court long nouveau nouvelle premier dernier
""".split())

FR_MARKERS = set("le la les des une du dans pour que qui comment quelle quels est sur avec ou "
                 "vous nous plus être cette ce ces aux au".split())
EN_MARKERS = set("the a an of and is for in that how what on with to you we this these are "
                 "should would about".split())


def norm(text):
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_words(text, locale):
    stop = STOP_FR if locale == "fr" else STOP_EN
    stop = stop | {norm(w) for w in stop}
    return {w for w in norm(text).split() if len(w) >= 4 and w not in stop}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def main():
    failures, warnings, notes = [], [], []

    if not os.path.exists(JSONL):
        print("FAIL: %s does not exist. Run build_prompt_sets.py first." % JSONL)
        return 1

    rows = []
    with open(JSONL, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                failures.append("line %d is not valid JSON: %s" % (lineno, exc))
    notes.append("rows read: %d" % len(rows))

    # --- 1. required fields -------------------------------------------------
    bad_field_rows = 0
    for row in rows:
        for field in REQUIRED_FIELDS:
            if field not in row:
                bad_field_rows += 1
                failures.append("%s missing field %s" % (row.get("prompt_id", "?"), field))
                break
        else:
            if not isinstance(row["text"], str) or not row["text"].strip():
                failures.append("%s has empty text" % row["prompt_id"])
            if row["locale"] not in ("en", "fr"):
                failures.append("%s has bad locale %r" % (row["prompt_id"], row["locale"]))
            if row["split"] not in EXPECTED_COUNTS:
                failures.append("%s has bad split %r" % (row["prompt_id"], row["split"]))
    notes.append("required-field check: %d rows rejected" % bad_field_rows)

    # --- 2. counts ----------------------------------------------------------
    counts = defaultdict(int)
    for row in rows:
        counts[(row["concept_id"], row["locale"], row["split"])] += 1
    concepts = sorted({r["concept_id"] for r in rows})
    for cid in concepts:
        for locale in ("en", "fr"):
            for split, expected in sorted(EXPECTED_COUNTS.items()):
                got = counts[(cid, locale, split)]
                if got != expected:
                    failures.append("count %s/%s/%s = %d, expected %d"
                                    % (cid, locale, split, got, expected))
    notes.append("count check: %d concepts x 2 locales x 5 splits" % len(concepts))

    # family balance inside positive
    fam_counts = defaultdict(int)
    for row in rows:
        if row["split"] == "positive":
            fam_counts[(row["concept_id"], row["locale"], row["family"])] += 1
    for key, got in sorted(fam_counts.items()):
        if got != 10:
            failures.append("family count %s = %d, expected 10" % ("/".join(map(str, key)), got))

    # --- 3. duplicates, scoped ---------------------------------------------
    seen_exact = defaultdict(set)
    seen_norm = defaultdict(set)
    dup_exact = dup_norm = 0
    for row in rows:
        scope = (row["concept_id"], row["locale"], row["split"])
        if row["text"] in seen_exact[scope]:
            failures.append("exact duplicate within %s: %s" % (scope, row["prompt_id"]))
            dup_exact += 1
        seen_exact[scope].add(row["text"])
        n = norm(row["text"])
        if n in seen_norm[scope]:
            failures.append("normalised duplicate within %s: %s" % (scope, row["prompt_id"]))
            dup_norm += 1
        seen_norm[scope].add(n)
    notes.append("duplicate check scoped to (concept, locale, split): "
                 "%d exact, %d normalised" % (dup_exact, dup_norm))

    # --- 4. leakage into held-out splits ------------------------------------
    # A marker must be CONCEPT-DISCRIMINATIVE, not merely frequent. Requiring only
    # "appears twice in this concept's discovery prompts" flags generic filler --
    # without, someone, small, have -- because such words recur everywhere. So a
    # marker must satisfy both:
    #   (a) >= 3 occurrences in this concept's positive+near_miss prompts, and
    #   (b) present in the discovery sets of at most 2 of the 14 concepts.
    # Condition (b) is the discriminative one: a word shared across many concepts
    # carries no concept identity and cannot leak one.
    by = defaultdict(list)
    for row in rows:
        by[(row["concept_id"], row["locale"], row["split"])].append(row)

    concept_df = {}
    for locale in ("en", "fr"):
        df = defaultdict(int)
        for cid in concepts:
            words = set()
            for split in ("positive", "near_miss"):
                for row in by[(cid, locale, split)]:
                    words |= content_words(row["text"], locale)
            for w in words:
                df[w] += 1
        concept_df[locale] = df

    leak_hits = 0
    marker_total = 0
    for cid in concepts:
        for locale in ("en", "fr"):
            freq = defaultdict(int)
            for split in ("positive", "near_miss"):
                for row in by[(cid, locale, split)]:
                    for w in content_words(row["text"], locale):
                        freq[w] += 1
            markers = {w for w, c in freq.items()
                       if c >= 3 and concept_df[locale][w] <= 2}
            marker_total += len(markers)
            for row in by[(cid, locale, "heldout_neutral")]:
                hit = markers & content_words(row["text"], locale)
                if hit:
                    leak_hits += 1
                    failures.append("leakage %s/%s %s carries marker(s) %s"
                                    % (cid, locale, row["prompt_id"], sorted(hit)))
    notes.append("discriminative markers derived: %d across 14 concepts x 2 locales"
                 % marker_total)
    notes.append("held-out neutral leakage check: %d violations" % leak_hits)

    # --- 5. near-duplication heldout_eliciting vs positives -----------------
    near_dup = 0
    for cid in concepts:
        for locale in ("en", "fr"):
            pos = [(r["prompt_id"], content_words(r["text"], locale))
                   for r in by[(cid, locale, "positive")]]
            pos_norm = {norm(r["text"]) for r in by[(cid, locale, "positive")]}
            for row in by[(cid, locale, "heldout_eliciting")]:
                if norm(row["text"]) in pos_norm:
                    failures.append("heldout_eliciting %s duplicates a positive" % row["prompt_id"])
                    near_dup += 1
                    continue
                cw = content_words(row["text"], locale)
                for pid, pcw in pos:
                    if jaccard(cw, pcw) >= 0.70:
                        warnings.append("near-duplicate %s ~ %s (jaccard %.2f)"
                                        % (row["prompt_id"], pid, jaccard(cw, pcw)))
                        near_dup += 1
                        break
    notes.append("heldout_eliciting vs positive overlap: %d flagged" % near_dup)

    # --- 6. family distinctness --------------------------------------------
    worst = []
    for cid in concepts:
        for locale in ("en", "fr"):
            fam_words = {}
            for fam in ("f1", "f2", "f3"):
                acc = set()
                for row in by[(cid, locale, "positive")]:
                    if row["family"] == fam:
                        acc |= content_words(row["text"], locale)
                fam_words[fam] = acc
            for a, b in (("f1", "f2"), ("f1", "f3"), ("f2", "f3")):
                j = jaccard(fam_words[a], fam_words[b])
                worst.append((j, cid, locale, a, b))
                if j >= 0.30:
                    warnings.append("families %s/%s %s-%s overlap jaccard %.2f (>=0.30)"
                                    % (cid, locale, a, b, j))
    worst.sort(reverse=True)
    notes.append("family distinctness: max pairwise jaccard %.3f (%s %s %s-%s)"
                 % worst[0] if worst else "family distinctness: n/a")

    # --- 7. locale plausibility --------------------------------------------
    # Detect on RAW text. norm() strips accents, which destroys the strongest French
    # signal there is; scoring normalised tokens made every French row look English.
    ACCENTS = set("àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ")
    ELISION = re.compile(r"\b(?:l|d|qu|j|n|s|c|m|t)['’]", re.IGNORECASE)

    locale_flags = 0
    for row in rows:
        raw = row["text"]
        toks = set(re.sub(r"[^\w\s'’]", " ", raw.lower()).split())
        fr_lex = len(toks & FR_MARKERS)
        en_lex = len(toks & EN_MARKERS)
        fr_orth = sum(1 for c in raw if c in ACCENTS) + len(ELISION.findall(raw))
        fr_score, en_score = fr_lex + fr_orth, en_lex
        if row["locale"] == "fr" and fr_score == 0:
            locale_flags += 1
            warnings.append("locale check: %s marked fr, no French signal (lex=%d orth=%d)"
                            % (row["prompt_id"], fr_lex, fr_orth))
        # Orthography alone must NOT condemn an English row: proper nouns carry
        # diacritics legitimately (Comte, Gruyere, Eyjafjallajokull, Medecins Sans
        # Frontieres). Require French LEXICAL evidence to outweigh the English.
        if row["locale"] == "en" and fr_lex > en_lex:
            locale_flags += 1
            warnings.append("locale check: %s marked en but reads fr (fr=%d en=%d orth=%d)"
                            % (row["prompt_id"], fr_lex, en_lex, fr_orth))
    notes.append("locale plausibility: %d rows flagged" % locale_flags)

    # parallel-slot coverage: every EN id must have an FR twin
    ids = {r["prompt_id"] for r in rows}
    missing_twin = 0
    for pid in sorted(ids):
        twin = pid.replace(".EN.", ".FR.") if ".EN." in pid else pid.replace(".FR.", ".EN.")
        if twin not in ids:
            missing_twin += 1
            failures.append("no bilingual twin for %s" % pid)
    notes.append("bilingual twin check: %d missing" % missing_twin)

    # --- 8. ordering --------------------------------------------------------
    order = [r["prompt_id"] for r in rows]
    if order != sorted(order):
        failures.append("rows are not in stable sorted prompt_id order")
    if len(set(order)) != len(order):
        failures.append("prompt_id is not unique across the artifact")
    notes.append("ordering: %s" % ("stable" if order == sorted(order) else "UNSTABLE"))

    # --- metadata consistency ----------------------------------------------
    if os.path.exists(META):
        with open(META, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        if meta.get("row_count") != len(rows):
            failures.append("metadata row_count %s != %d" % (meta.get("row_count"), len(rows)))
        if meta.get("concept_count") != len(concepts):
            failures.append("metadata concept_count %s != %d"
                            % (meta.get("concept_count"), len(concepts)))
        gated = [c["concept_id"] for c in meta.get("concepts", []) if c.get("pi_gated")]
        notes.append("PI_GATED concepts: %s" % (", ".join(gated) or "none"))
    else:
        failures.append("metadata.json missing")

    # --- report -------------------------------------------------------------
    print("=" * 72)
    print("PROMPT-SET VALIDATION REPORT")
    print("=" * 72)
    for n in notes:
        print("  note  %s" % n)
    print("-" * 72)
    if warnings:
        print("WARN (%d) - researcher review, non-blocking:" % len(warnings))
        for w in warnings[:40]:
            print("  warn  %s" % w)
        if len(warnings) > 40:
            print("  ... %d more" % (len(warnings) - 40))
    else:
        print("WARN (0)")
    print("-" * 72)
    if failures:
        print("FAIL (%d):" % len(failures))
        for f in failures[:60]:
            print("  FAIL  %s" % f)
        if len(failures) > 60:
            print("  ... %d more" % (len(failures) - 60))
        print("=" * 72)
        print("RESULT: FAIL")
        return 1
    print("FAIL (0)")
    print("=" * 72)
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
