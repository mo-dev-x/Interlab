# final_pairing v2 — persona pair corpus

**INTERNAL SCIENCE ONLY. `pi_gated: true` on both concepts. PI sign-off ABSENT.**

Every row in `prompt_sets.jsonl` is a **research stimulus** authored to a
specification for an interpretability experiment. It is not the position of the
model, the lab, the researcher, the coordinator, the description author or the
corpus author. No row is presented, quoted, exported or demonstrated without
that disclosure. (`DISCLOSURE_REQUIREMENT`.)

## What this is

Two mirrored concepts, `pro_american_exceptionalism` and
`pro_chinese_exceptionalism`, implementing
`concept_description_persona_exceptionalism.json`
version `final-pairing-v2-concept-description-persona-exceptionalism/1.2.0`,
sha256 `e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234`,
68594 bytes, frozen at commit `220329b`.

The description is the specification and it is binding. Nothing here revises
it. Every count, family, slot identity, ordinal, claim-type allocation and
mirror-slot map is read out of it.

400 rows = 2 concepts x 2 locales x 100.
Per concept per locale: positive 30, near_miss 15, unrelated 15,
heldout_neutral 20, heldout_eliciting 20.

## Files

| file | what it is |
| --- | --- |
| `authoring/persona_exceptionalism.py` | the two concepts' positives and eliciting rows, and the structure constants read out of the description |
| `authoring/shared_pools.py` | `unrelated` and `heldout_neutral`, IDENTICAL between the two concepts |
| `build_prompt_sets.py` | assigns IDs, assembles the byte-identical near_miss split by reference, serialises. Authors nothing. |
| `validate_prompt_sets.py` | every mechanizable falsifier the description states |
| `build_parity_review_worksheet.py` | emits the reviewer's input and the empty register |
| `prompt_sets.jsonl` | generated |
| `metadata.json` | generated |
| `parity_review_worksheet.json` | generated; `review_status: NOT_YET_REVIEWED` |

Regenerate and check:

```
python prompts/final_pairing/v2/build_prompt_sets.py
python prompts/final_pairing/v2/validate_prompt_sets.py
python prompts/final_pairing/v2/build_parity_review_worksheet.py
```

## The near-miss construction

Each concept's 15 `near_miss` rows are the **other** concept's positives,
**byte-identical**, at the 15 designated mirror slots
`F1.01 F1.03 F1.05 F1.07 F1.09 F2.01 F2.03 F2.06 F2.07 F2.09 F3.01 F3.02 F3.03 F3.09 F3.10`,
`near_miss` ordinals 01–15 following that list in order.

They are assembled **by reference** in `build_prompt_sets.py`, never re-typed,
so byte-identity cannot drift. `validate_prompt_sets.py` verifies all 60 by
sha256 against the source slot rather than by eye.

`positive ∩ near_miss` on raw strings, per concept per locale, is **0**. That
holds by construction, not by luck: every positive names its own nation and
that nation is the subject of the greatness claim, so no string is admissible
under both concept definitions. **If the referent requirement is ever relaxed,
that guarantee is lost and the intersection check alone will not report it.**

## What is NOT done, and blocks the corpus freeze

- **The independent intensity-parity review.** 50 slot pairs per locale, 100
  for the pair, by a reader who **authored neither concept**. The corpus author
  is disqualified by construction. Its absence is a failure, not a warning.
- **The FLAGGED-PAIR REGISTER.** Produced by that reviewer at step 5.
  `parity_review_worksheet.json` supplies the container, empty, and the 34
  HD/CC pairs inside the reviewer's card scope. Same status as the review.
- **`falsifier_3_INVITATION_PARITY`** on `heldout_eliciting`.
- **The corpus-implements-definition instrument**, which may be authored by
  neither the description author nor the corpus author.

## Read before interpreting any result from this corpus

`protocols/final_pairing/v1/overlap_interpretation_pre_registration.json`.
Under the frozen gate algebra a **shared** stance feature is structurally
excluded from both feature groups. A **DISJOINT** overlap result was guaranteed
before a single prompt was written and carries **no** evidence that the two
personas are separately represented. Required wording: *"the construction
cannot detect a referent-invariant feature"*. Prohibited: *"separate
representations"*, or any paraphrase of it, on the basis of a DISJOINT result.
