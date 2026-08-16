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
| `authoring/closed_class.py` | the closed-class stopword instrument, derived by category, hash-pinned |
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

## IF YOU ARE EDITING THIS CORPUS, READ THIS FIRST

Two properties are load-bearing for more than they look.

**1. `near_miss` byte-identity and the 15/15 split sizes license the
disjointness instrument.** Family disjointness is measured on **content word
types** — the nation's name and closed-class vocabulary excluded. That
tokenisation is licensed (architect RULING_9) by an arithmetic argument: G-A's
negative set is `unrelated` **pooled with** `near_miss`, so with
`|near_miss| == |unrelated|` the identity
`separation_auroc == (near_miss_auroc + unrelated_auroc) / 2` holds *exactly*;
and because `near_miss` **is** the mirror's positives byte-identical, it carries
every closed-class token the positives carry. A feature keying on that shared
form scores ≈0.5 on the `near_miss` half and is **capped at 0.75 separation**,
below the 0.90 G-A threshold, even with perfect separation from `unrelated`.
The closed-class channel cannot produce a G-A pass.

**Change byte-identity or the 15/15 sizes and that argument lapses.** The
exemption is then unlicensed and the tokenisation must be **re-ruled by the
architect lane** — not re-derived locally.
`validate_prompt_sets.check_ruling_9_condition` fails loudly rather than
quietly measuring on a weaker instrument.

**2. The margin is small and the verdict is not stable across instruments.**
Worst pair `pro_chinese_exceptionalism / fr / f1-f3`: **22 shared content types
of 181**, threshold 27.15 → **5.15 types of headroom**. Both tokenisations are
always reported; raw word-type Jaccard is **reported, never enforced**, because
it measures a quantity no gate can be fooled by. A bare "passes" conceals the
state of the evidence — read `metadata.family_disjointness.margin_*` with the
verdict, never instead of it.

**3. F2 MUST CARRY NO DEEP-TIME VOCABULARY — on either side, in either
locale.** Deep-time vocabulary is label-correlated in this corpus: concentrated
in the Chinese positives, nearly absent from the American ones. That is the
*mirror* of the RULING_9 argument. For `pro_chinese_exceptionalism`, `near_miss`
**is** the American positives and `unrelated` carries no national referent, so
**both** halves of G-A's pooled negative set are clean — a pure era detector
scores ≈1.0 against both and passes G-A at ceiling while being no persona
feature at all. (For `pro_american_exceptionalism` it runs backwards and is
rejected directionally, so the hazard is one-sided.)

What stops it is the **family conjunction**: gates are per family, survival
needs all six cells, and F2 carries no era vocabulary — so a pure era feature
sits at ≈0.5 in the f2 cells and dies there. **That was an accident.** It is
now enforced by `validate_prompt_sets.check_f2_carries_no_deep_time`, which
fails on a single era token in a single f2 row. `f1` and `f3` are deliberately
**not** touched: deep-time content is permitted (it is asserted, not hedged);
what was missing was pre-registration, not permission.

**4. Prompt ids carry their own version — `V2-C01.EN.POS.F1.01`.** Before this,
v2's id space was a strict **subset** of v1's: all 400 ids existed in v1, and
**zero** of the partners shared a `concept_id`. A cross-version `prompt_id` join
returned **400/400 matched, 400/400 wrong rows, 0/400 recoverable** — and the
failure signature is a *perfect match rate*, so every ordinary defence (row
counts, match rate, null checks, join cardinality) reads green. Required by
RULING_11 as a property, not a grammar: `validate_prompt_sets` asserts the
**intersection with v1 is empty**, so any future grammar preserving
disjointness still passes. Parsers splitting on `.` still get five fields; ones
asserting the first field equals `C{nn}` need a one-line update.

`near_miss_of` still means **the mirror concept** here and **the row's own
concept** in v1 — same key, two meanings, neither self-identifying.
`metadata.near_miss_of_semantics` carries the tag. That is strictly weaker than
the id fix: it yields a wrong *value* where the ids yielded wrong *rows*, and it
documents a meaning for a reader who looks rather than disambiguating a key for
code that does not.

**5. Every row records its `claim_type`.** It is MIRROR-LAW-bearing: the
description binds every slot pair to assert *the same claim type*, so leaving it
unrecorded left MIRROR_LAW's core clause mechanically unverifiable and asserted
only by a human reading. Every value is read out of the description's grid —
positives from the per-family allocation, eliciting from its ordinal
allocation, `near_miss` inheriting from the source slot it is byte-copied from —
and the validator re-derives all three and fails on disagreement.

`NOT_APPLICABLE` means **no claim type applies**, never *unknown*. It is carried
by exactly two splits — `unrelated` (60 rows) and `heldout_neutral` (80) — which
are the shared negative substrates, carry no national claim by construction, and
are identical between the concepts, so there is no claim to type and no mirror
pair to bind. `heldout_eliciting` is **not** among them; all 80 of its rows carry
real claim types. **Zero rows are flagged ambiguous**, because the grid is total.

## What is NOT done, and blocks the corpus freeze

- **The independent intensity-parity review.** 50 slot pairs per locale, 100
  for the pair, by a reader who **authored neither concept**. The corpus author
  is disqualified by construction. Its absence is a failure, not a warning.
- **The FLAGGED-PAIR REGISTER.** Produced by that reviewer at step 5.
  `parity_review_worksheet.json` supplies the container, empty, and the 34
  HD/CC pairs inside the reviewer's card scope. Same status as the review.
- **Confirmation of the author's no-restoration-framing claim.** The author
  reports that neither side uses restoration framing, which would narrow the
  card's hard scope from HD+CC to CC alone. RULING_9 concurs but requires the
  **reviewer** to confirm it against the corpus: it is the author reporting on
  their own choice, and it is the one input that shrinks the reviewer's
  workload. Until confirmed, all 17 HD+CC pairs per locale stay in hard scope.
- **`falsifier_3_INVITATION_PARITY`** on `heldout_eliciting`. Frame-sharing on
  this split is **ruled permitted and preferred** (RULING_9, REFERRAL B) — the
  frame is the experimenter's stimulus, not either persona's voice, and 20
  distinct frames per locale are used, not one repeated. It is **not**
  permitted on positives, where 0 of 60 pairs are identical. The residual the
  reviewer still owns: a shared frame can collocate more naturally with one
  nation token than the other, which is a warmer premise. Sharing the frame
  does not discharge the review; it makes it cheap. All 20 eliciting
  ordinal-pairs per locale are flagged
  `in_falsifier_3_collocation_scope`.
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
