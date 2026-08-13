# -*- coding: utf-8 -*-
"""Materialise the frozen bilingual prompt-set artifact.

This script assigns identifiers and serialises. It authors NOTHING. Every string in
the output comes from the modules under authoring/. If a prompt is missing, the fix
is to author it there, never to generate one here.

Output (deterministic, byte-stable across runs on any platform):
  prompt_sets.jsonl   one row per (concept, locale, split, index)
  metadata.json       schema/protocol version, thresholds, rubric identities, counts

Prompt ID grammar:
  C{index:02d}.{LOCALE}.{SPLIT}.{FAMILY}.{ordinal:02d}
  e.g. C01.EN.POS.F1.03  /  C01.FR.POS.F1.03  are the same slot in two locales.
"""

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "authoring"))

from shared_pools import SHARED_UNRELATED, SHARED_HELDOUT_NEUTRAL  # noqa: E402
from concepts_01_04 import CONCEPTS_01_04  # noqa: E402
from concepts_05_08 import CONCEPTS_05_08  # noqa: E402
from concepts_09_11 import CONCEPTS_09_11  # noqa: E402
from concepts_12_14 import CONCEPTS_12_14  # noqa: E402

CONCEPTS = CONCEPTS_01_04 + CONCEPTS_05_08 + CONCEPTS_09_11 + CONCEPTS_12_14

SCHEMA_VERSION = "prompt_set/v1"
PROTOCOL_VERSION = "final-pairing-discovery/1.0.0"

LOCALES = ["en", "fr"]

SPLIT_CODES = {
    "positive": "POS",
    "near_miss": "NEAR",
    "unrelated": "UNREL",
    "heldout_neutral": "HON",
    "heldout_eliciting": "HOE",
}

EXPECTED_COUNTS = {
    "positive": 30,
    "near_miss": 15,
    "unrelated": 15,
    "heldout_neutral": 20,
    "heldout_eliciting": 20,
}

# Pre-registered thresholds. Frozen here so that the artifact and the gates it will
# be judged against travel together and cannot drift apart. Changing any of these
# after activation is computed invalidates the run.
THRESHOLDS = {
    "G_A_separation_auroc_min": 0.90,
    "G_A_scope": "every paraphrase family independently",
    "G_B_fire_rate_min": 0.70,
    "G_B_activation_floor_fraction_of_observed_max": 0.20,
    "G_B_scope": "every paraphrase family independently",
    "G_C_specificity_auroc_vs_near_miss_min": 0.75,
    "G_D_amplify_relevance_delta_min": 3.0,
    "G_D_coherence_median_min": 6.0,
    "G_E_suppress_relevance_delta_max": -3.0,
    "G_E_coherence_median_min": 6.0,
    "G_E_researcher_spot_read_outputs": 10,
    "second_target_relevance_gain_min": 1.0,
    "max_targets_v1": 3,
    "ci_method": "SS9 prompt-group bootstrap; interval must exclude zero",
}

RUBRICS = {
    "coherence": "1.0",
    "concept_relevance": "1.0",
    "scale": "1-10 ordinal",
    "judge_instrument": "lodestar",
    "judge_temperature": 0,
    "sweep_repeats": 1,
    "confirmation_repeats": 3,
}

POSITIONS_POLICY = {
    "public_calibration": "ALL",
    "diagnostic_only": "GENERATED_ONLY",
    "note": "GENERATED_ONLY is reported separately and never merged into a published record.",
}


def _rows_for_concept(concept):
    rows = []
    idx = concept["index"]
    cid = concept["concept_id"]

    def emit(split, family, items):
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
                    "near_miss_of": cid if split == "near_miss" else None,
                    "near_miss_domains": concept["near_miss_domains"] if split == "near_miss" else None,
                    "pi_gated": bool(concept.get("pi_gated", False)),
                    "shared_substrate": split in ("unrelated", "heldout_neutral"),
                    "text": item[locale],
                })

    for family in ("f1", "f2", "f3"):
        emit("positive", family, concept["families"][family])
    emit("near_miss", None, concept["near_miss"])
    emit("unrelated", None, SHARED_UNRELATED)
    emit("heldout_neutral", None, SHARED_HELDOUT_NEUTRAL)
    emit("heldout_eliciting", None, concept["heldout_eliciting"])
    return rows


def build():
    rows = []
    for concept in sorted(CONCEPTS, key=lambda c: c["index"]):
        rows.extend(_rows_for_concept(concept))

    # Deterministic ordering. Sorting by prompt_id alone is enough because the ID
    # encodes concept, locale, split, family and ordinal.
    rows.sort(key=lambda r: r["prompt_id"])

    out_jsonl = os.path.join(HERE, "prompt_sets.jsonl")
    with open(out_jsonl, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    with open(out_jsonl, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    concept_meta = []
    for concept in sorted(CONCEPTS, key=lambda c: c["index"]):
        entry = {
            "index": concept["index"],
            "concept_id": concept["concept_id"],
            "near_miss_domains": concept["near_miss_domains"],
            "pi_gated": bool(concept.get("pi_gated", False)),
            "families": ["f1", "f2", "f3"],
        }
        for optional in ("default_persona_candidate", "researcher_review_required",
                         "pole_positive", "pole_near_miss"):
            if optional in concept:
                entry[optional] = concept[optional]
        concept_meta.append(entry)

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "locales": LOCALES,
        "splits": sorted(EXPECTED_COUNTS),
        "expected_counts_per_concept_per_locale": EXPECTED_COUNTS,
        "concept_count": len(CONCEPTS),
        "row_count": len(rows),
        "prompt_sets_sha256": digest,
        "thresholds": THRESHOLDS,
        "rubrics": RUBRICS,
        "positions_policy": POSITIONS_POLICY,
        "shared_substrate_splits": ["unrelated", "heldout_neutral"],
        "duplicate_scope": "(concept_id, locale, split)",
        "concepts": concept_meta,
        "prohibitions": [
            "No legacy feature index or calibration value may be reused; "
            "Qwen3.5-27B is not Qwen2.5-14B and gemma-3-12b-it is not gemma-3-12b-pt.",
            "No prompt may be modified after activation is computed.",
            "Candidate 14 (political_framing) is PI_GATED and must not enter a public configuration.",
        ],
    }
    with open(os.path.join(HERE, "metadata.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    print("rows: %d" % len(rows))
    print("concepts: %d" % len(CONCEPTS))
    print("prompt_sets.jsonl sha256: %s" % digest)
    return rows


if __name__ == "__main__":
    build()
