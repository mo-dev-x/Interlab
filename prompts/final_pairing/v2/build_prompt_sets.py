# -*- coding: utf-8 -*-
"""Materialise the v2 persona-pair prompt set.

This script assigns identifiers, assembles the byte-identical near-miss split
and serialises. It AUTHORS NOTHING. Every positive, eliciting, unrelated and
neutral string comes from the modules under authoring/.

Bound to prompts/final_pairing/v2/concept_description_persona_exceptionalism.json
version final-pairing-v2-concept-description-persona-exceptionalism/1.2.0,
sha256 e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234,
frozen at commit 220329b.

Prompt ID grammar, carried over from the frozen v1 set:
  C{index:02d}.{LOCALE}.{SPLIT}.{FAMILY}.{ordinal:02d}
near_miss rows carry family X0, per THE_SLOT_GRID.near_miss_mirror_slots
.note_on_id_grammar.

PROMPT IDs ARE SCOPED TO THIS SET. C01 here is pro_american_exceptionalism;
C01 in the frozen v1 set is a different concept in a different set. Index
assignment and ID grammar are explicitly NOT DECIDED by the description
(PREREQUISITES_THIS_DOCUMENT_DOES_NOT_DECIDE.concept_indices_and_prompt_id_grammar);
they are the prompt-set builder's call and are recorded here as such.

NO THRESHOLD IS WRITTEN BY THIS SCRIPT. v2 thresholds are unfrozen and the
corpus author does not set them; metadata records that as a stated absence
rather than leaving the key out.
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "authoring"))

from shared_pools import SHARED_UNRELATED, SHARED_HELDOUT_NEUTRAL  # noqa: E402
from persona_exceptionalism import (  # noqa: E402
    CONCEPTS,
    CLAIM_TYPE_ALLOCATION,
    NEAR_MISS_MIRROR_SLOTS,
    HELDOUT_ELICITING_CLAIM_TYPES,
)
from closed_class import (  # noqa: E402
    STOPWORDS,
    category_depths,
    digest as stopword_digest,
)

SCHEMA_VERSION = "prompt_set/v1"
PROTOCOL_VERSION = "final-pairing-discovery/1.0.0"

DESCRIPTION = {
    "path": "prompts/final_pairing/v2/concept_description_persona_exceptionalism.json",
    "document_version": (
        "final-pairing-v2-concept-description-persona-exceptionalism/1.2.0"
    ),
    "sha256": "e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234",
    "bytes": 68594,
    "freeze_commit": "220329b",
}

LOCALES = ["en", "fr"]

SPLIT_CODES = {
    "positive": "POS",
    "near_miss": "NEAR",
    "unrelated": "UNREL",
    "heldout_neutral": "HON",
    "heldout_eliciting": "HOE",
}

# SPLITS_AND_WHAT_EACH_ONE_IS.counts_are_frozen.per_concept_per_locale
EXPECTED_COUNTS = {
    "positive": 30,
    "near_miss": 15,
    "unrelated": 15,
    "heldout_neutral": 20,
    "heldout_eliciting": 20,
}


def _family_disjointness_record():
    """The disjointness instrument, its margin and its binding condition.

    Required by architect RULING_9 (mailbox sequence 37): the falsifier is
    SUPPLIED, the stopword lists are derived by closed-class category and
    pinned BY HASH, BOTH tokenisations continue to be reported, and THE MARGIN
    is carried in the freeze record because a bare "passes" is a true
    statement that conceals the state of the evidence. 0.15 is NOT touched.
    """
    # Imported here rather than at module scope so that the builder's own
    # import graph stays acyclic and readable; validate_prompt_sets performs
    # no file I/O at import time.
    from validate_prompt_sets import (
        _family_pools, _exempt_tokens, jaccard,
        JACCARD_FALSIFIER, JACCARD_TARGET, RULING_9_CONDITION,
    )

    pairs = []
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        exempt = _exempt_tokens(cid)
        for locale in LOCALES:
            pools = _family_pools(concept, locale)
            for left, right in (("f1", "f2"), ("f1", "f3"), ("f2", "f3")):
                raw_l, raw_r = pools[left] - exempt, pools[right] - exempt
                con_l, con_r = raw_l - STOPWORDS[locale], raw_r - STOPWORDS[locale]
                inter, union = len(con_l & con_r), len(con_l | con_r)
                pairs.append({
                    "concept_id": cid,
                    "locale": locale,
                    "family_pair": "%s-%s" % (left, right),
                    "content_word_type_jaccard": round(jaccard(con_l, con_r), 4),
                    "raw_word_type_jaccard": round(jaccard(raw_l, raw_r), 4),
                    "shared_content_types": inter,
                    "union_content_types": union,
                    "allowed_shared_types_at_threshold": round(JACCARD_TARGET * union, 2),
                    "headroom_in_shared_types": round(JACCARD_TARGET * union - inter, 2),
                })
    worst = max(pairs, key=lambda p: p["content_word_type_jaccard"])
    worst_raw = max(pairs, key=lambda p: p["raw_word_type_jaccard"])
    return {
        "ruling": "architect RULING_9, mailbox sequence 37, 2026-08-15T16:20:00Z. "
                  "The clause is NORMATIVE, not advisory, and the tokenisation is "
                  "CONTENT WORDS.",
        "the_clause": "THE_SLOT_GRID.paraphrase_families.requirement -- 'Three "
                      "LEXICALLY DISJOINT phrasings ... Disjointness is measured, "
                      "not asserted; target max pairwise Jaccard <= 0.15. The "
                      "nation's own name is EXEMPT'.",
        "falsifier_SUPPLIED": JACCARD_FALSIFIER,
        "why_a_falsifier_was_supplied_rather_than_the_requirement_relaxed":
            "Demoting the clause to advisory would have made it unfalsifiable BY "
            "DESIGN. The repair for a missing falsifier is to SUPPLY one, never "
            "to delete the requirement.",
        "threshold": JACCARD_TARGET,
        "threshold_provenance": "THE DESCRIPTION'S. NOT SET, NOT MOVED AND NOT "
                                "RE-DERIVED HERE. Re-deriving it to buy margin is "
                                "refused.",
        "tokenisation": {
            "enforced": "content word types -- all word types minus the nation's "
                        "own name (the clause's own exemption) minus closed-class "
                        "vocabulary",
            "also_reported_never_enforced": "raw word types, minus the nation's "
                                            "own name only",
            "why_content_words": "RULING_9 gives two independent derivations. (i) "
                                 "The clause ALREADY exempts the nation's name "
                                 "because referent_requirement forces it into all "
                                 "three families; closed-class vocabulary is "
                                 "forced into all three by the requirement that "
                                 "rows be well-formed sentences, so the same "
                                 "principle excludes it. (ii) Arithmetic: the "
                                 "closed-class channel CANNOT produce a G-A pass "
                                 "-- see binding_condition.",
            "word_boundary_rule": "the tokeniser SPLITS ON THE APOSTROPHE, so "
                                  "English contractions and French elisions are "
                                  "handled identically. Keeping the apostrophe "
                                  "inside the token silently broke the clause's "
                                  "own nation-name exemption in French.",
        },
        "instrument": {
            "derived_by": "closed-class CATEGORY (determiners, prepositions, "
                          "pronouns, conjunctions, copulas/auxiliaries, plus "
                          "negation and clitics declared explicitly), populated "
                          "exhaustively per locale BEFORE any value was "
                          "recomputed -- not by extending one list until the "
                          "numbers agreed.",
            "stopword_set_sha256": stopword_digest(),
            "source": "prompts/final_pairing/v2/authoring/closed_class.py",
            "category_depths": category_depths(),
            "note_on_unequal_type_counts": "FR carries more types than EN in the "
                                           "copula/auxiliary and determiner "
                                           "categories because French inflects "
                                           "where English does not. EQUAL DEPTH OF "
                                           "COVERAGE OF THE CLOSED CLASS is the "
                                           "requirement, not equal cardinality.",
        },
        "binding_condition": {
            "statement": "The content-word exemption is licensed by an arithmetic "
                         "argument that is BOUND to two facts about this corpus: "
                         "near_miss remains the mirror's positives BYTE-IDENTICAL, "
                         "and |near_miss| == |unrelated| == 15.",
            "the_arithmetic": "G-A's negative set is unrelated POOLED with "
                              "near_miss, so with equal sizes separation_auroc == "
                              "(near_miss_auroc + unrelated_auroc)/2 EXACTLY. A "
                              "feature keying on form shared with the mirror scores "
                              "~0.5 on the near_miss half and is CAPPED at 0.75 "
                              "separation, below the 0.90 G-A threshold, even with "
                              "perfect separation from unrelated.",
            "if_either_fact_changes": RULING_9_CONDITION["if_either_changes"],
            "enforced_at": "validate_prompt_sets.check_ruling_9_condition, which "
                           "FAILS rather than silently measuring on a weaker "
                           "instrument.",
        },
        "margin_MUST_BE_READ_WITH_THE_VERDICT": {
            "why": "A bare 'passes' is a true statement that conceals the whole "
                   "state of the evidence.",
            "worst_content_pair": worst,
            "worst_raw_pair": worst_raw,
            "all_twelve_pairs": pairs,
        },
    }


def _deep_time_record():
    """The measured deep-time asymmetry and the F2 invariant that contains it."""
    from deep_time import deep_time_hits, digest as deep_time_digest

    per_cell = {}
    per_concept = {}
    for concept in CONCEPTS:
        cid = concept["concept_id"]
        per_concept[cid] = {"tokens": 0, "rows": 0}
        for locale in LOCALES:
            for family in ("f1", "f2", "f3"):
                total = rows_with = 0
                for item in concept["families"][family]:
                    found = deep_time_hits(item[locale], locale)
                    total += len(found)
                    rows_with += 1 if found else 0
                per_cell["%s/%s/%s" % (cid, locale, family)] = {
                    "tokens": total, "rows_carrying": rows_with}
                per_concept[cid]["tokens"] += total
                per_concept[cid]["rows"] += rows_with
    f2_total = sum(v["tokens"] for k, v in per_cell.items() if k.endswith("/f2"))
    return {
        "status": "MEASURED, CONTAINED, AND REFERRED UPWARD. Not fixed by "
                  "re-authoring, which was expressly NOT ordered.",
        "the_asymmetry": "Deep-time vocabulary is label-correlated: it is "
                         "concentrated in pro_chinese_exceptionalism's positives "
                         "and nearly absent from pro_american_exceptionalism's.",
        "why_it_is_dangerous_and_it_is_the_MIRROR_of_the_RULING_9_argument":
            "RULING_9 proved that form SHARED with the mirror is capped at 0.75 "
            "separation and cannot pass G-A. Deep-time vocabulary runs the same "
            "identity the OTHER way. For pro_chinese_exceptionalism, near_miss IS "
            "the American positives (byte-identical, ~no deep-time) and unrelated "
            "carries no national referent at all, so BOTH halves of G-A's pooled "
            "negative set are clean and a PURE ERA DETECTOR scores ~1.0 against "
            "both -- a perfect G-A passer that is not a persona feature.",
        "the_hazard_is_ONE_SIDED": "For pro_american_exceptionalism the same "
                                   "feature runs backwards, since ITS near_miss is "
                                   "the Chinese positives where the deep-time "
                                   "vocabulary lives, so it scores ~0 and is "
                                   "rejected directionally. The hazard points at "
                                   "pro_chinese_exceptionalism only.",
        "the_general_lesson": "The byte-identical near-miss design -- this "
                              "corpus's best defence against authoring asymmetry "
                              "-- converts ANY label-correlated lexical asymmetry "
                              "into a maximally advantaged discriminator. That is "
                              "the cost of its greatest strength.",
        "THE_PROTECTION": "Gates are evaluated PER FAMILY and survival requires "
                          "all six cells. F2 carries NO deep-time vocabulary in "
                          "either locale, so a pure era feature sits at ~0.5 in "
                          "the f2 cells and the family conjunction kills it.",
        "it_was_an_accident_and_is_now_an_ENFORCED_INVARIANT":
            "Nothing measured it and nothing named it, and it is destroyed by a "
            "single era phrase entering one f2 row. validate_prompt_sets."
            "check_f2_carries_no_deep_time now FAILS on any deep-time token in "
            "any f2 row, in either locale, ON EITHER SIDE -- the family must "
            "carry none at all, not merely carry it symmetrically.",
        "f2_deep_time_tokens": f2_total,
        "f2_required": 0,
        "per_concept_over_60_positives": per_concept,
        "per_locale_per_family": per_cell,
        "lexicon": {
            "sha256": deep_time_digest(),
            "source": "prompts/final_pairing/v2/authoring/deep_time.py",
            "scope": "markers of GREAT HISTORICAL DEPTH only; generic temporal "
                     "vocabulary (generation, years, still, encore, 'old people', "
                     "'les anciens') is deliberately excluded, because every row "
                     "of a corpus about national endurance carries temporal "
                     "language and counting it would make the measure meaningless.",
            "deliberately_a_superset": "This lexicon counts MORE than the "
                                       "architect's scan did (29 tokens / 19 rows "
                                       "on the Chinese side against their 19 / 17) "
                                       "and still returns f2 == 0, so the f2 "
                                       "result is robust to lexicon choice rather "
                                       "than an artifact of a narrow list.",
        },
        "f1_and_f3_are_NOT_touched": "Deep-time content is PERMITTED under "
                                     "RULING_1: it is asserted, not hedged. What "
                                     "was missing was pre-registration, not "
                                     "permission, and crossing the factor was "
                                     "expressly NOT ordered. The f1 and f3 rows "
                                     "stand; they are counted here for the record "
                                     "only.",
    }


def _by_id(concepts):
    return {c["concept_id"]: c for c in concepts}


def _positive_at_slot(concept, slot, locale):
    """slot is 'F1.03' style; returns the raw string at that slot identity."""
    family, ordinal = slot.split(".")
    return concept["families"][family.lower()][int(ordinal) - 1][locale]


def _rows_for_concept(concept, registry):
    rows = []
    idx = concept["index"]
    cid = concept["concept_id"]
    mirror_id = concept["near_miss_of"]
    mirror = registry[mirror_id]

    def emit(split, family, items, near_miss_of=None):
        code = SPLIT_CODES[split]
        fam = family.upper() if family else "X0"
        for ordinal, item in enumerate(items, start=1):
            for locale in LOCALES:
                rows.append({
                    "prompt_id": "C%02d.%s.%s.%s.%02d" % (
                        idx, locale.upper(), code, fam, ordinal),
                    "concept_id": cid,
                    "concept_index": idx,
                    "locale": locale,
                    "split": split,
                    "family": family,
                    "ordinal": ordinal,
                    "near_miss_of": near_miss_of,
                    "near_miss_domains": None,
                    "pi_gated": bool(concept.get("pi_gated", False)),
                    "shared_substrate": split in ("unrelated", "heldout_neutral"),
                    "text": item[locale],
                })

    for family in ("f1", "f2", "f3"):
        emit("positive", family, concept["families"][family])

    # near_miss: THE MIRROR CONCEPT'S POSITIVES, BYTE-IDENTICAL, at the 15
    # designated mirror slots, in the matching locale. Assembled by reference
    # so that byte-identity cannot drift; it is not re-typed anywhere.
    near_miss_items = [
        {locale: _positive_at_slot(mirror, slot, locale) for locale in LOCALES}
        for slot in NEAR_MISS_MIRROR_SLOTS
    ]
    emit("near_miss", None, near_miss_items, near_miss_of=mirror_id)

    emit("unrelated", None, SHARED_UNRELATED)
    emit("heldout_neutral", None, SHARED_HELDOUT_NEUTRAL)
    emit("heldout_eliciting", None, concept["heldout_eliciting"])
    return rows


def build():
    registry = _by_id(CONCEPTS)
    rows = []
    for concept in sorted(CONCEPTS, key=lambda c: c["index"]):
        rows.extend(_rows_for_concept(concept, registry))

    rows.sort(key=lambda r: r["prompt_id"])

    out_jsonl = os.path.join(HERE, "prompt_sets.jsonl")
    with open(out_jsonl, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    with open(out_jsonl, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    concept_meta = []
    for concept in sorted(CONCEPTS, key=lambda c: c["index"]):
        concept_meta.append({
            "index": concept["index"],
            "concept_id": concept["concept_id"],
            "pole_positive": concept["pole_positive"],
            "pole_near_miss": concept["pole_near_miss"],
            "near_miss_of": concept["near_miss_of"],
            "near_miss_domains": None,
            "pi_gated": bool(concept.get("pi_gated", False)),
            "researcher_review_required": bool(
                concept.get("researcher_review_required", False)),
            "families": ["f1", "f2", "f3"],
        })

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "prompt_set_version": "v2",
        "binds_to_description": DESCRIPTION,
        "locales": LOCALES,
        "splits": sorted(EXPECTED_COUNTS),
        "expected_counts_per_concept_per_locale": EXPECTED_COUNTS,
        "concept_count": len(CONCEPTS),
        "row_count": len(rows),
        "prompt_sets_sha256": digest,
        "thresholds": {
            "status": "NOT SET BY THE CORPUS AUTHOR. v2 thresholds are UNFROZEN. "
                      "Stated rather than omitted: a missing key reads as NOT "
                      "CHECKED rather than NOT APPLICABLE. The v1 values 0.75 "
                      "and 0.90 are v1's and are not inherited here.",
        },
        "shared_substrate_splits": ["unrelated", "heldout_neutral"],
        "duplicate_scope": "(concept_id, locale, split)",
        "claim_type_allocation_per_family": CLAIM_TYPE_ALLOCATION,
        "heldout_eliciting_claim_types_by_ordinal": HELDOUT_ELICITING_CLAIM_TYPES,
        "near_miss_source_slot_map": {
            "note": "near_miss ordinals 01-15 follow this list in order. Recorded "
                    "in metadata rather than in the row ID, per "
                    "THE_SLOT_GRID.near_miss_mirror_slots.note_on_id_grammar.",
            "slots_in_order": NEAR_MISS_MIRROR_SLOTS,
            "source": "the MIRROR concept's positive at the same slot identity, "
                      "byte-identical, in the matching locale",
        },
        "prompt_id_scope": "Unique within THIS prompt set only. C01 here is "
                           "pro_american_exceptionalism; C01 in the frozen v1 set "
                           "is an unrelated concept in an unrelated set. Index "
                           "assignment and ID grammar are the prompt-set builder's "
                           "decision, not the description's.",
        "join_key": {
            "required": ["prompt_set_version", "prompt_id"],
            "hazard": "A tool joining v1 and v2 rows on prompt_id ALONE will "
                      "SILENTLY MISMATCH rather than error, because the ID space "
                      "is reused across sets. Per architect RULING_9 observation 2, "
                      "the join key must be (version, prompt_id).",
            "current_consumers": "No consumer breaks today -- the causal lane binds "
                                 "--grid-path, not prompt_id. That is a fact about "
                                 "today's callers, not a property of the data.",
        },
        "near_miss_of_semantics": {
            "value": "mirror_concept",
            "meaning": "near_miss_of names the OTHER concept, whose positives these "
                       "rows ARE, byte-identical.",
            "hazard": "THE SAME KEY MEANS SOMETHING DIFFERENT IN v1, where "
                      "near_miss_of is set to the row's OWN concept_id. Neither "
                      "value is self-identifying, so a consumer reading the field "
                      "without checking the set version MIS-JOINS SILENTLY. This "
                      "tag exists so the meaning travels with the data rather than "
                      "with the reader's memory of which version they loaded. Per "
                      "architect RULING_9 observation 3.",
        },
        "family_disjointness": _family_disjointness_record(),
        "deep_time_asymmetry_and_the_F2_invariant": _deep_time_record(),
        "concepts": concept_meta,
        "disclosure": {
            "status": "INTERNAL SCIENCE ONLY",
            "text": "Every row of both concepts is a RESEARCH STIMULUS authored to "
                    "a specification for an interpretability experiment. It is not "
                    "the position of the model, the lab, the researcher, the "
                    "coordinator, the description author or the corpus author.",
            "pi_sign_off": "ABSENT. Required before any persona-related demo, "
                           "public label, export or external artifact.",
        },
        "prohibitions": [
            "No legacy feature index or calibration value may be reused; "
            "Qwen3.5-27B is not Qwen2.5-14B and gemma-3-12b-it is not gemma-3-12b-pt.",
            "No prompt may be modified after activation is computed.",
            "Both v2 concepts are PI_GATED and must not enter a public configuration.",
            "No row of this set may be presented, quoted, exported or demonstrated "
            "without the disclosure above.",
        ],
        "corpus_freeze_prerequisites": {
            "intensity_parity_review": "REQUIRED AND NOT DONE. 50 slot pairs per "
                                       "locale, 100 for the pair, by a reader who "
                                       "authored neither concept. Its absence is a "
                                       "failure, not a warning.",
            "flagged_pair_register": "REQUIRED AND NOT DONE. Produced by the parity "
                                     "reviewer. Same status as the review itself.",
            "corpus_implements_definition_instrument": "REQUIRED AND NOT DONE. May "
                                                       "be authored by neither the "
                                                       "description author nor the "
                                                       "corpus author. RULING_9 "
                                                       "could not assign an owner "
                                                       "but ruled who it may NOT be: "
                                                       "not the description author, "
                                                       "not the corpus author -- "
                                                       "both would mark their own "
                                                       "work.",
            "symmetric_disjointness_instrument": "DISCHARGED at this commit. "
                                                 "RULING_9 added it as a freeze "
                                                 "blocker: the locale-asymmetric "
                                                 "stopword list had to be repaired "
                                                 "before the disjointness check "
                                                 "could be cited as a freeze "
                                                 "artifact. It is now derived by "
                                                 "closed-class category and pinned "
                                                 "by hash; see family_disjointness.",
            "no_restoration_framing_claim": "MUST BE CONFIRMED BY THE PARITY "
                                            "REVIEWER, not accepted from the "
                                            "author. It is the author reporting on "
                                            "their own authoring choice and it is "
                                            "the one input that SHRINKS the "
                                            "reviewer's workload. Separation of "
                                            "duties applies to favourable findings "
                                            "exactly as to unfavourable ones.",
        },
    }
    with open(os.path.join(HERE, "metadata.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    print("rows: %d" % len(rows))
    print("concepts: %d" % len(CONCEPTS))
    print("prompt_sets.jsonl sha256: %s" % digest)
    return rows


if __name__ == "__main__":
    build()
