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
                                                       "corpus author.",
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
