# -*- coding: utf-8 -*-
"""Emit the independent parity reviewer's worksheet and the empty register.

MIRROR_LAW.intensity_parity requires "an independent side-by-side review pass
over ALL 30 POSITIVE SLOT PAIRS AND ALL 20 HELDOUT_ELICITING SLOT PAIRS PER
LOCALE -- 50 pairs per locale, 100 for the pair -- by a reader who authored
neither concept".

THE CORPUS AUTHOR MAY NOT RUN THAT REVIEW. This script therefore produces the
INPUT to it and the CONTAINER for its output, and nothing else:

  - the 100 slot pairs, side by side, with the claim type each slot carries
  - the 34 pairs (17 per locale) inside THE_PARITY_REVIEWERS_CARD's scope,
    which is HD and CC only
  - the author's OBSERVATION of temporal shape on those 34 pairs, offered as
    input to step 5, marked as an observation and not as a decision
  - the closed-list hedge-device scan per side, so the reviewer sees candidates
    rather than hunting for them at step 3
  - THE_FLAGGED_PAIR_REGISTER, EMPTY, with review_status NOT_YET_REVIEWED

Every reviewer_decision field is null. A register entry is created at step 5 by
the reviewer, for pairs the reviewer passed at step 4. Passing is the
reviewer's act; the author cannot pre-fill it and has not.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "authoring"))
sys.path.insert(0, HERE)

from persona_exceptionalism import (  # noqa: E402
    CONCEPTS,
    CLAIM_TYPE_ALLOCATION,
    HELDOUT_ELICITING_CLAIM_TYPES,
)
from validate_prompt_sets import scan_hedges, load_rows, index_rows  # noqa: E402

LOCALES = ["en", "fr"]
CARD_SCOPE_CLAIM_TYPES = ("HD", "CC")

# Author's observation of temporal shape, per claim type. NOT a decision.
# RESIDUAL_ASYMMETRIES.1 names the two shapes: FULFILMENT (a founding promise
# still being kept) versus RESTORATION (a former height being regained), and
# for CC an unbroken civilizational span versus a continuous constitutional
# order of far shorter duration.
TEMPORAL_SHAPE_OBSERVATION = {
    "HD": {
        "which_side_carries_a_concession_of_present_shortfall": "NEITHER, as authored",
        "reason": "Both sides are written in FULFILMENT shape: a purpose held now "
                  "and not yet discharged. No RESTORATION framing -- regain, "
                  "reclaim, return to a former height -- was used on either side, "
                  "so the modality drift RESIDUAL_ASYMMETRIES.1 warns about at "
                  "token level has no carrier here. The residual temporal "
                  "difference that remains is the AGE of the purpose: the "
                  "pro_chinese_exceptionalism side locates it further back.",
    },
    "CC": {
        "which_side_carries_a_concession_of_present_shortfall": "NEITHER, as authored",
        "reason": "The pre-registered asymmetry is present and unavoidable: the "
                  "pro_chinese_exceptionalism side asserts an unbroken "
                  "civilizational span measured in millennia, the "
                  "pro_american_exceptionalism side a continuous order of far "
                  "shorter duration. That is a difference in WHAT IS CLAIMED, "
                  "which step 4 permits, and it is recorded here so that step 5 "
                  "has the row-level input it needs. Neither side concedes a "
                  "present shortfall; both assert the identity as holding NOW.",
    },
}


def slot_pairs(idx):
    a, b = CONCEPTS[0], CONCEPTS[1]
    pairs = []
    for locale in LOCALES:
        for family in ("f1", "f2", "f3"):
            allocation = CLAIM_TYPE_ALLOCATION[family]
            rows_a = [r for r in idx[(a["concept_id"], locale, "positive")]
                      if r["family"] == family]
            rows_b = [r for r in idx[(b["concept_id"], locale, "positive")]
                      if r["family"] == family]
            for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
                pairs.append(_pair(ra, rb, locale, "positive",
                                   "%s.%02d" % (family.upper(), i + 1),
                                   allocation[i]))
        rows_a = idx[(a["concept_id"], locale, "heldout_eliciting")]
        rows_b = idx[(b["concept_id"], locale, "heldout_eliciting")]
        for i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
            pairs.append(_pair(ra, rb, locale, "heldout_eliciting",
                               "HOE.%02d" % (i + 1),
                               HELDOUT_ELICITING_CLAIM_TYPES[i]))
    return pairs


def _pair(ra, rb, locale, split, slot, claim_type):
    la, lb = len(ra["text"]), len(rb["text"])
    entry = {
        "slot": slot,
        "locale": locale,
        "split": split,
        "claim_type": claim_type,
        "in_parity_reviewers_card_scope": claim_type in CARD_SCOPE_CLAIM_TYPES,
        "pro_american_exceptionalism": {
            "prompt_id": ra["prompt_id"],
            "text": ra["text"],
            "chars": la,
            "closed_list_devices": sorted(scan_hedges(ra["text"], locale)),
        },
        "pro_chinese_exceptionalism": {
            "prompt_id": rb["prompt_id"],
            "text": rb["text"],
            "chars": lb,
            "closed_list_devices": sorted(scan_hedges(rb["text"], locale)),
        },
        "length_ratio": round(max(la, lb) / float(min(la, lb)), 4),
        "reviewer_decision": None,
    }
    if claim_type in CARD_SCOPE_CLAIM_TYPES:
        entry["author_observation_of_temporal_shape"] = \
            TEMPORAL_SHAPE_OBSERVATION[claim_type]
    return entry


def main():
    idx = index_rows(load_rows())
    pairs = slot_pairs(idx)
    in_scope = [p for p in pairs if p["in_parity_reviewers_card_scope"]]

    worksheet = {
        "$comment": "INPUT TO THE INDEPENDENT INTENSITY-PARITY REVIEW, and the "
                    "empty FLAGGED-PAIR REGISTER. Produced by the corpus author, "
                    "who MAY NOT run the review. Every reviewer_decision is null "
                    "and the register is empty; that is the correct state before "
                    "the review, and it is a FAILURE, not a warning, if it is "
                    "still the state at corpus freeze.",
        "document_type": "parity_review_worksheet",
        "binds_to_description": {
            "path": "prompts/final_pairing/v2/concept_description_persona_exceptionalism.json",
            "document_version": "final-pairing-v2-concept-description-persona-exceptionalism/1.2.0",
            "sha256": "e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234",
        },
        "review_status": "NOT_YET_REVIEWED",
        "reviewer": "UNASSIGNED. Must be a reader who authored neither concept. "
                    "The corpus author is disqualified by construction.",
        "scope": {
            "pairs_total": len(pairs),
            "pairs_per_locale": len(pairs) // len(LOCALES),
            "positive_pairs_per_locale": 30,
            "heldout_eliciting_pairs_per_locale": 20,
            "card_scope_pairs_total": len(in_scope),
            "card_scope_pairs_per_locale": len(in_scope) // len(LOCALES),
            "note": "Counts are read out of MIRROR_LAW.intensity_parity and "
                    "THE_PARITY_REVIEWERS_CARD.scope_they_actually_face. None is "
                    "introduced here.",
        },
        "how_to_apply_the_card": "FIVE STEPS, IN ORDER, HD and CC pairs only. THE "
                                 "FIRST FAILURE DECIDES. step_1 claim-type floor; "
                                 "step_2 main-clause test; step_3 hedge-device test "
                                 "against the CLOSED list of five classes; step_4 "
                                 "pass, temporal shape permitted; step_5 record in "
                                 "the register. The other 33 pairs per locale are "
                                 "judged on intensity parity as written. Read the "
                                 "card in the description; it is not restated here.",
        "closed_list_scan_is_a_convenience_not_a_verdict": "The closed_list_devices "
            "fields are a mechanical scan offered so the reviewer does not have to "
            "hunt at speed. A device MATCHED on both sides at the same slot is "
            "PERMITTED. The scan finds no unmatched device anywhere in this corpus; "
            "the reviewer is not bound by that and decides step 3 themselves.",
        "pairs": pairs,
        "FLAGGED_PAIR_REGISTER": {
            "status": "EMPTY -- NOT YET PRODUCED. Required at corpus freeze on the "
                      "same terms as the review itself: absence is a failure, not a "
                      "warning.",
            "produced_by": "the parity reviewer, at step 5, alongside the review",
            "fields_per_entry": ["slot", "locale", "which_side_carries_the_concession",
                                 "reason"],
            "what_it_feeds": "the ONE-SIDED-RESULT ANALYSIS, as caveat (iii). NEVER "
                             "an input to the pass/fail decision.",
            "entries": [],
        },
    }

    path = os.path.join(HERE, "parity_review_worksheet.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(worksheet, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("pairs: %d (card scope: %d)" % (len(pairs), len(in_scope)))
    print(path)


if __name__ == "__main__":
    main()
