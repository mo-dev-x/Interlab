# FREEZE ATTESTATION — v2 persona-exceptionalism corpus

**ENGINEERING REFERENCE FREEZE. NOT a validation of the corpus against its definition.**

Authority: architect RULING_12 (mailbox sequence 40, `inbox/architect.json`), which PERMITS this
freeze and enumerates nine required attestation contents. A freeze missing any of the nine is not
authorized. The nine are labelled (a) through (i) below so a future reader can check completeness
against the ruling directly.

Executed by: the COMMITTER lane, under coordinator authority. Not the architect (a lane that rules
on a freeze must not also execute it) and not the corpus author (that would be marking their own
work). The figures in items (c), (d) and (i) are taken from the checking lanes' pinned reports and
were not re-derived here; re-deriving them would be this lane marking the checking lanes' work.

---

## (a) Corpus commit and corpus digest

- Corpus commit: `c9dd6a7cd661653936b8e8b6570efdcbd475476d`
- `prompts/final_pairing/v2/prompt_sets.jsonl` sha256:
  `9c2975e9f013957d19128018e307b5b2bf6624232d20e8647b2d991ecbd4b5cc`

Re-computed by this lane at commit time, not inherited:

```
git show c9dd6a7:prompts/final_pairing/v2/prompt_sets.jsonl | sha256sum
9c2975e9f013957d19128018e307b5b2bf6624232d20e8647b2d991ecbd4b5cc
```

## (b) Description digest, and that it has not moved since 220329b

- `prompts/final_pairing/v2/concept_description_persona_exceptionalism.json` sha256:
  `e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234`

The description has NOT MOVED since it was frozen at `220329b`. Re-computed by this lane at all
four pins; all four are byte-identical:

```
for c in 220329b 4edeca4 6616089 c9dd6a7; do
  git show $c:prompts/final_pairing/v2/concept_description_persona_exceptionalism.json | sha256sum
done
220329b  e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234
4edeca4  e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234
6616089  e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234
c9dd6a7  e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234
```

Four corpus commits, zero drift in the frozen head.

## (c) Conformance result, with the seventeen UNCHECKED items ENUMERATED BY NAME

**37 PASS / 1 FAIL / 17 UNCHECKED**, over 55 emitted items, measured at `c9dd6a7`.

Source: conformance lane, mailbox sequence 2 (`inbox/conformance.json`), pinned report
`conformance/final_pairing/v2/conformance_report_c9dd6a7.json`
(sha256 `869cb5ceafdde2bae0fbbf5ef3fb507bdcba7819b620935380ba35277cffb738`),
instrument at commit `20c4740`. The single remaining FAIL is CV-002, recorded at (e).

RULING_12 is explicit that a count is not an enumeration and only an enumeration survives citation.
The seventeen, by check ID and by the title the pinned report gives each one:

| ID | UNCHECKED requirement, as titled in the pinned report |
|---|---|
| U-001 | T1_SUBJECT: the greatness claim's subject is the NATION and not a government, party, leader, policy or economic arrangement |
| U-002 | T2_VOICE: the belief is ASSERTED as the speaker's own |
| U-003 | T3_PREDICATE: the predicate is exceptionalist rather than affection or ordinary patriotism |
| U-004 | T4: a named nation appears in a predicate of inferiority, threat or blame |
| U-005 | T5_CLAIM_TYPE, BOTH LIMBS: whether each SENTENCE instantiates the claim type recorded for it, and no other |
| U-006 | T6_FACTUAL_FLOOR: named achievements, people, places and eras are REAL and correctly attributed |
| U-007 | MIRROR_LAW intensity parity over 50 slot pairs per locale, and its FLAGGED-PAIR REGISTER |
| U-008 | heldout_eliciting falsifier_3_INVITATION_PARITY |
| U-009 | heldout_eliciting falsifier_1: an eliciting prompt that itself passes T1-T3 is a misfiled positive |
| U-010 | Paraphrase-family lexical disjointness, max pairwise Jaccard <= 0.15 |
| U-011 | HARD_EXCLUSIONS beyond the lexical screens actually run |
| U-012 | MIRROR_LAW F3_pairs_by_FUNCTION_AND_SCALE_NEVER_BY_ERA |
| U-013 | 'Near-duplicate' limbs of heldout_eliciting.falsifier_2 and of NO_STRING_IN_THIS_DOCUMENT_IS_CORPUS_ELIGIBLE.falsifier |
| U-014 | heldout_neutral third limb: 'no discriminative marker from either concept's discovery splits may reach it' |
| U-015 | DISCLOSURE_REQUIREMENT, PI sign-off, and the pi_gated exposure disposition |
| U-016 | MIXED stance-plus-era features, and era carried WITHOUT era vocabulary |
| U-017 | Whether the era-free family survives the four F2 pairs currently out for rewrite |

Notes the conformance lane attached to this list, preserved rather than summarised:

- Under U-011, SIX of the eight hard exclusions remain unreachable and **are not passing**:
  ethnic/racial/biological supremacy, dehumanisation, incitement and imperatives, territorial and
  sovereignty claims, named living political figures, and military/alliance/trade positions.
- UNCHECKED was 17 of 50 and is now 17 of 55. **Zero items moved off the list.** The `claim_type`
  field bought FIVE NEW PASSING CHECKS (T5-001/2/3/4 and ML-001); it discharged no existing
  UNCHECKED item, and the lane declined to report it as the latter.
- U-005 is **NARROWED, not discharged**. `claim_type` is the corpus author's own assertion about
  their own row. It makes the LABELLING checkable against the grid; it does not make the SENTENCE
  checkable. A blended sentence carries a correct-looking label and passes all five new checks.
- U-002's screen is partial: C-018 is an EN lexical screen and its passing is NOT a proven T2 pass.
- U-010 the lane deliberately does NOT re-measure, because a second number on its own tokenisation
  would obscure a repair whose margin is 0.75 of one token type.

Observation by this lane, recorded rather than reconciled: the pinned report's `summary` block reads
`total 55, passed 37, failed 1, unchecked 17, partial 9`. 37 + 1 + 17 = 55 exactly, so `partial: 9`
is an annotation overlaying items already counted in those three buckets, not a fifth disjoint
bucket. This lane did not re-derive it and states it as an observation only.

## (d) The conformance lane's bottom line, preserved in force with the number updated

Passing **37** mechanical checks while UNREAD on the CONTENT limbs of T1/T3/T5/T6 shows that the
corpus **does not STRUCTURALLY CONTRADICT its definition** — **not** that it implements it. Those
are different claims and only the first is the conformance lane's to make.

The lane's own framing, preserved: "37 mechanical checks passing with 17 requirements unchecked
shows the corpus does not CONTRADICT its definition structurally, which is not the same claim as
implementing it."

## (e) CV-002, recorded as a DECIDED limitation, with the loud-failure reasoning

**CV-002 is the one remaining FAIL and it is a RECORDED LIMITATION, not a blocker.** It was
adjudicated, not missed.

The defect: `near_miss_of` means the OPPOSITE thing across the version boundary. v1 sets it to the
row's OWN concept in 420 of 420 near_miss rows; v2 sets it to the MIRROR in 60 of 60. Same key,
opposite meaning, and **neither value is self-identifying**. Id-space disjointness (CV-001) closes
the cross-version JOIN hazard completely, and the metadata `near_miss_of_semantics` tag documents
the meaning (M-001/M-002 pass), but NEITHER closes CV-002: the hazard needs no cross-version join at
all. A consumer holding a v2 row and applying v1's reading resolves it to the WRONG CONCEPT of the
pair using only v2 data.

The reasoning that decided it, recorded so a future reader sees the adjudication rather than
re-opening it. The architect applied the same test it used on the id case — is the failure signature
invisible to every automated defence? — and it came out the other way:

- **Loud where it matters.** A v1-trained reader makes each concept's near_miss set into its own
  positives. By the RULING_9 identity, `near_miss_auroc` collapses to about 0.5 and
  `separation_auroc` is capped near 0.75, so **NOTHING PASSES G-A ANYWHERE**. The signature is TOTAL
  ABSENCE OF SURVIVORS — the loudest failure this pipeline can produce, the exact opposite of the id
  case's perfect match rate. A defect that announces itself by making every result vanish needs
  recording so the eventual investigator reaches it in one step, not prevention by construction.
- **Invariant where it does not.** With exactly two mirrored concepts, `near_miss_of` is a
  bijection. Row counts, per-concept totals and every aggregate that does not use it for ASSIGNMENT
  are identical under either reading.

The architect marks the collapse-to-0.5 and the 0.75 cap as **ARGUED, not PROVEN**: they follow from
the RULING_9 identity, but no one has run it and the cap is a modelling estimate, not a measurement.

Severity downgrade, recorded explicitly by the conformance lane rather than left stale: this is now a
**misreading hazard**, not a silent-wrong-join hazard. The lane downgraded it and declined to CLEAR
it; those are not the same act and it did the first without doing the second.

Remaining repair, not made and not required here: a self-identifying value IN the row, or a consumer
contract.

## (f) The mixed stance-plus-era residual — explicitly UNBOUNDED, no instrument claimed by anyone

**Status: UNBOUNDED.** Every lane says so independently, **no lane has claimed an instrument for it,
and the architect declined to invent one.**

E-001 passes — f2 is era-free in both locales on both sides — but the conformance lane states the
caveat unchanged, because a pass invites the wrong reading: **E-001 BOUNDS A PURE ERA-DETECTOR ONLY.
It does NOT kill mixed stance-plus-era features**, per RULING_10 itself, and it cannot see era
carried by proper name (U-016). Nor does a pass at this pin say anything about a post-rewrite corpus
(U-017). The verdict is also unstable on one token: counting bare FR `ancien` would leave FR with no
era-free family and E-001 would fail. **No era lexicon has been ratified by anyone with authority to
ratify one.**

The corpus-side lever that would address it — crossing the factor, deep-time pro_american and
shallow pro_chinese — is CORPUS-ADDRESSABLE (RULING_10 option d) and was **declined**, both when
first raised and again in RULING_12: presence is roughly 2.7:1, the density bound holds, and the
cost is a full re-authoring of a corpus that has just passed parity 100/0.

Why it is not corpus fitness: a mixed feature is a property of the MODEL, not of these bytes. No
arrangement of this corpus makes a model stop having one. Both mitigations (RULING_10 6(b) and 6(c))
act AT SELECTION, downstream of freeze, so they cannot gate it. What IS required instead is the
pre-registration recorded in the separate section below.

## (g) The sequence-35 provenance caveat

The parity reviewer's **step-3 basis rests on a transcription it cannot check**, and this is not
repaired.

Architect sequence 35 — which ruled on RESIDUAL_1 and supplied the parity reviewer's five-step card
— is **IRRECOVERABLE AT SOURCE**. It is absent from the whole mailbox tree at any nesting depth. The
architect declined to reconstruct it from its downstream transcription, on the grounds that
presenting a reconstruction as the original would manufacture an authoritative-looking artifact
nobody could distinguish from the real one. A loss record was written instead
(`architect-000035-IRRECOVERABLE-LOSS-RECORD-NOT-THE-RULING.json`); that file is explicitly NOT the
ruling and nothing in it may be cited as sequence 35's content.

All that is attested verbatim is the sequence number and an event string truncated at 80 characters,
which establishes only the SUBJECTS of the ruling — temporal shape is CONTENT, modality is
INTENSITY, and an entity discriminator — and NONE of its reasoning, scope, step definitions, the
34-pair scope, the closed list of five hedge-device classes, or any threshold, exemption or
condition it contained.

**Standing consequence:** any downstream artifact whose authority traces to sequence 35 traces it
through the PM's transcription alone, and that must be recorded wherever RULING_3 is cited. **The
only repair is re-derivation and re-ratification as a NEW ruling under a NEW sequence number — never
as a restoration of 35.** The parity reviewer confirms the caveat is untouched by the citation
refresh and still stands.

## (h) What this freeze IS, and what it is NOT

**This is an ENGINEERING REFERENCE FREEZE. It is NOT a validation of the corpus against its
definition.**

What it IS: it fixes the bytes and makes them a stable, citable reference, so downstream work can
build against something that cannot move underneath it.

What it is NOT, and this is the load-bearing half: it does **not** certify that the corpus
implements its definition. It does not assert that the sentences implement T1–T6. The scientific
claim remains **unestablished and is carried forward as unestablished**. Engineering may proceed
against fixed bytes precisely because the scientific claim is NOT being made — separating the two
explicitly is what prevents an engineering convenience from laundering into a scientific result.

**Any downstream artifact citing this freeze inherits the limits, not just the hash.**

The architect's REFUSED list is reproduced here so nothing on it is later read as granted:
certifying that the corpus implements its definition; assigning an owner to the semantic
corpus-implements-definition instrument; ordering the crossed-factor re-authoring; requiring the
`near_miss_of` rename; and committing the freeze itself.

## (i) Parity result, register pin, and the directional finding

**100 PASS / 0 RETURNED.** 14 register entries, 14/14 toward pro_chinese.

- Register: `prompts/final_pairing/v2/flagged_pair_register.json`
- Register commit: **`06d5b3efa07a5cededd751d2caa484dc44aa79aa`** (`06d5b3e`), a direct child of
  `c9dd6a7`
- Register sha256: `5ef0d831f03483b407939d9bdc80319e0a0eef7e0d8a5aee34d4c7c737288536`
  (previously `db7ac3f71313e7933b2fb7271eac12a75e1ff4c06d39bb5a6d56a745fa052fce` at `427b2cd`)

Source: parity reviewer, mailbox sequence 2 (`inbox/parity_reviewer.json`), and the re-review at
archive sequence 1.

**THE DIRECTIONAL FINDING, in the reviewer's own terms:** "**ALL FOUR REPAIRED THE WEAKER SIDE
UPWARD and left pro_american BYTE-UNCHANGED** — verified on the rows, not taken from the commit
message. That removes an asymmetry rather than relocating it." The four are F2.02 en/fr (non-factive
"spoke of ... as" becomes factive "knew ... was"; two "I believe" operators become flat main-clause
assertions) and F2.03 en/fr ("I think" / "je pense que" become a bare declarative and a cleft, plus
the FR calque `nous LA marchons` -> `nous Y marchons`).

The move from `427b2cd` to `06d5b3e` is a **CITATION REFRESH ONLY**, proven rather than asserted:
228 prompt_id citations gained the `V2-` prefix and the reviewer walked both structures scalar by
scalar, classifying every difference — 228 of 228 are a prompt_id whose new value is exactly `V2-`
plus its old value, and ZERO are anything else. The 100 (slot, locale, decision, deciding_step,
register_entry) tuples, the 14 register entries with their reasons and DIRECTION, the counts block
and the whole-corpus direction audit are all IDENTICAL. No decision moved, and slot-plus-locale was
always the key — prompt_id appears only as a citation into the corpus.

Two residuals survive, recorded by the reviewer and pointing the same way as the original four:
committed markers +3 to pro_american, scope-limiting partitives +5 to pro_chinese (F1.07 and F3.05,
both locales, both SIA, outside card scope). Neither fails under the clause. Era is untouched by the
repairs and remains the dominant one-directional residue.

---

# ADDITIONAL RULING_12 REQUIREMENT — NOT one of the nine

## PRE-REGISTRATION: a bound on INTERPRETATION, not on the bytes

RULING_12 requires this in addition to the nine attestation contents, and it **binds whether or not
the corpus is frozen**:

> **NO CAUSAL-ARM RESULT MAY BE READ AS PERSONA-SPECIFIC UNTIL THE ERA ALTERNATIVE HAS BEEN
> ADDRESSED BY RULING_10 6(b) — the eliciting necessary-condition test — OR RULING_10 6(c) — the
> era-discriminator probe set.**

This is a constraint on CONCLUSIONS, not on the corpus. Both mitigations apply when a candidate
feature is CHOSEN, which is downstream of freeze, which is why neither could gate this freeze and
why the constraint is pre-registered here instead. Until 6(b) or 6(c) has been run, a causal-arm
result on this corpus is consistent with an era feature and may not be reported as persona-specific.

---

# RECORDED LIMITATIONS — FOUR, carried forward with this freeze

RULING_12 permits the freeze **carrying four recorded limitations**. A citation of this freeze
inherits all four.

1. **CV-002** — `near_miss_of` means the opposite thing across the version boundary; neither value
   is self-identifying. Decided limitation, full reasoning at (e). Still the one FAIL.
2. **The U-005 semantic limb — UNOWNED.** A MECHANICAL corpus-implements-definition instrument now
   exists; the SEMANTIC one **does not**. Per RULING_9 it may be neither the description author nor
   the corpus author. The architect declined to name its owner, holding that naming one is a
   coordination decision and not architecture. **As of this freeze, no lane owns it.**
3. **The mixed stance-plus-era residual — UNBOUNDED, with no instrument claimed by anyone.** Full
   record at (f).
4. **The sequence-35 provenance caveat.** Full record at (g).

---

# ALSO RECORDED

## The era density bound is now MEASURED, not argued

The architect re-ran the per-cell era density **under the union of EVERY lexicon anyone has
proposed** — its own deep list PLUS `anciens` PLUS dates PLUS founding vocabulary. **Maximum
era-bearing rows in any cell: 6 of 10, against G-B's frozen floor of 7 of 10.**

RULING_11 ARGUED that the bound was lexicon-independent. This **MEASURES** it. The lexicon question
is therefore SETTLED for this property rather than bypassed, and no future lexicon dispute can
reopen it without pushing a cell past 7.

This makes the flagged lexicon delta moot for the property, and both sources are recorded here
without reconciliation, as they stand in their own reports:

- Architect: wide era presence **19/60 against 12/60** by rows.
- Parity reviewer: **27/60 against 10/60** on a different lexicon (the reviewer's folds
  `founding`/`fondation` and `the beginning`/`commencement` into presence).
- Parity reviewer, separately: per-cell era-bearing rows max at **5/10 depth-keyed and 6/10
  presence-keyed** against the same 7/10 floor.

Same direction, same order of magnitude, and every figure sits under the 7/10 per-cell floor, so
none of them decides anything. The architect records that the reviewer flagging the delta BEFORE it
could be mistaken for a failed reproduction was correct handling and needs no action.

## The `near_miss_of` rename — the acknowledged cheap repair, explicitly NOT REQUIRED

Renaming the v2 field (`near_miss_source_concept` or similar) is the obvious cheap repair: a
different NAME cannot be misread as the same field. **The architect explicitly did NOT require it,
and it is not taken here.**

**TAKE IT IF THE SCHEMA IS OPENED AGAIN FOR ANY OTHER REASON.** It does not block on its own,
because "freeze is the last cheap moment" is an argument about COST while the blocker test is about
HAZARD. If cheapness alone made a thing a blocker, everything noticed before a freeze would be one
and no artifact would ever freeze.

## ENGINEERING PREVIEW ONLY still stands

**Nothing in this freeze authorizes a cluster submission.** No Tamia submission. ENGINEERING PREVIEW
ONLY stands; internal science only. The freeze fixes bytes for downstream engineering to build
against and does nothing else.

Still outstanding and NOT discharged by this freeze: the era-discriminator probe at selection
(RULING_10 dissociator (c)); ratification of any era lexicon by an authority competent to ratify
one; a self-identifying `near_miss_of` value or a consumer contract (CV-002); an owner for the
semantic corpus-implements-definition instrument; and every semantic requirement in the seventeen
enumerated at (c).

Separately REQUIRED by RULING_12 but gating the HARNESS rather than this freeze, since it touches no
corpus byte: the discrimination harness must carry the `4edeca4` corpus as a regression fixture and
report that flip alongside the mutants. At the present pin, ZERO of the four positive controls is a
genuine FAIL->PASS flip, because the checks they target now pass on the real corpus; P01 and P02
were real flips at `4edeca4` and became non-firing as the repairs landed. Commits are immutable, so
running the harness against `4edeca4` is a real, non-synthetic flip available at every future run.
Until that fixture lands, the harness's claim that its controls discriminate rests entirely on the
19 mutants.

---

# VERIFICATION PERFORMED BY THE COMMITTING LANE

Recorded because an attestation that pins a hash nobody re-computed is the defect this sprint has
spent itself on. Every command below was run in this repository at commit time.

| # | Check | Result |
|---|---|---|
| 1 | `git show c9dd6a7:prompts/final_pairing/v2/prompt_sets.jsonl \| sha256sum` | `9c2975e9f013957d19128018e307b5b2bf6624232d20e8647b2d991ecbd4b5cc` — MATCHES (a) |
| 2 | `git show c9dd6a7:prompts/final_pairing/v2/concept_description_persona_exceptionalism.json \| sha256sum` | `e8a5f0ba2380ffd17bfe5d0202b4432d6a843c1b9a4772703e3c68465c8e6234` — MATCHES (b) |
| 3 | Description sha256 at `220329b`, `4edeca4`, `6616089`, `c9dd6a7` | All four `e8a5f0ba…` — BYTE-IDENTICAL |
| 4 | Post-freeze drift: both files at `c9dd6a7` vs current `HEAD` | **NO DRIFT** — see below |
| 5 | `git merge-base --is-ancestor c9dd6a7 HEAD` | TRUE — `c9dd6a7` is an ancestor of HEAD on `final-pairing-harness` |

**Check 4 in full**, because it is the one that decides whether this freeze pins a superseded file.
Compared by git blob object id, which is a content hash, as well as by sha256:

```
git rev-parse c9dd6a7:prompts/final_pairing/v2/prompt_sets.jsonl   0f404336efd91e2be1cb610e5ad087fce4b1f003
git rev-parse HEAD:prompts/final_pairing/v2/prompt_sets.jsonl      0f404336efd91e2be1cb610e5ad087fce4b1f003
git rev-parse c9dd6a7:prompts/final_pairing/v2/concept_description_persona_exceptionalism.json   bd60347a058fc3c19067bea1c2b68bb39b452bad
git rev-parse HEAD:prompts/final_pairing/v2/concept_description_persona_exceptionalism.json      bd60347a058fc3c19067bea1c2b68bb39b452bad
```

Both frozen artifacts are byte-identical at `c9dd6a7` and at HEAD. **This freeze does not pin a
superseded file.**

Commits landed on this branch strictly after `c9dd6a7`, `git log --oneline c9dd6a7..HEAD`:

- `06d5b3e` Re-resolve the register's prompt_id citations to the version-qualified ids
- `20c4740` Key C-022 and CV-001 on the property, not the id grammar; re-pin to c9dd6a7

Neither touches either frozen artifact. `git diff --name-status c9dd6a7 HEAD` reports changes only
under `conformance/final_pairing/v2/` (the conformance lane's own instrument and its report, a tree
owned by that lane) and to `prompts/final_pairing/v2/flagged_pair_register.json`, which is the
parity reviewer's deliverable and is NOT one of the two artifacts this freeze pins. The register at
HEAD is byte-identical to the register at `06d5b3e` (blob `a5490d10d4440e21d2560d0bb81b14109e8a4bdb`,
sha256 `5ef0d831f03483b407939d9bdc80319e0a0eef7e0d8a5aee34d4c7c737288536`), so the pin at (i) is
current.

**Correction to the ordering recorded in the work order, stated rather than reconciled.** The work
order named `06d5b3e`, `427b2cd` and `c2574a2` as commits landing after `c9dd6a7`. Measured:
`427b2cd` and `c2574a2` are both **ANCESTORS** of `c9dd6a7`, not descendants
(`git merge-base --is-ancestor 427b2cd c9dd6a7` and likewise for `c2574a2` both return true), so
their content is already inside the frozen commit. `20c4740`, which the work order did not name, IS
after `c9dd6a7` and is the current HEAD. The drift check at 4 covers the full `c9dd6a7..HEAD` range
regardless of which commits were expected, so the conclusion does not depend on the correction.

This lane did NOT re-run the conformance harness, the discrimination fixtures, or the parity review,
and did not re-derive any figure in (c), (d) or (i). Those are the checking lanes' results, cited
from their pinned reports, and re-deriving them here would be this lane marking their work.
