# BINDING PRE-REGISTRATION v1.7 — feature-class adjudication scheme

**Handoff packet for the Gemma Scope 2 assistant.** This is the sole remaining dependency for
the n = 40 Gemma adjudication. It is self-contained: everything needed to adjudicate is below.

> ## ⛔ v1.7 SUPERSEDES EVERYTHING BELOW WHERE THEY CONFLICT — READ §11 FIRST.
>
> §11 (2026-08-08, v1.6→v1.7) makes the **marked activating token** primary evidence on both columns,
> creates **`parked`** as a disposition distinct from `indeterminate`, requires **reason codes**
> on every `indeterminate`, and requires the adjudication to live in a **hash-bound file** rather
> than in a report. It also **voids the first inter-rater calibration** and specifies its re-run.
> Two named rows are ruled there. **§11 governs; then §7.1; then the rest.**
>
> *(Version history: v1.1 `40e40b98…` → v1.2 → v1.3 `108c576d…` → v1.4 `77f629c0…` → v1.5
> `6ebaac18…` class 11 → v1.6 `6194e13a…` → v1.7 this (§11.8–11.9). The v1.3 title survived the v1.4/v1.5 edits by oversight —
> the body was current, the header was not. That is the same header-lags-body defect that made
> the v1.2 packet self-contradictory. Corrected here; the fix is the reason the version line now
> appears exactly twice, in §9's two methods lines, both auto-checkable against this title.)*

> ## 🚨 READ BEFORE YOU BEGIN — THIS SETS WHAT YOU COLLECT.
>
> **Evidence depth is matched at 16/16, pre-registered before any counts.** Full ruling and the
> reasoning in **§7.1**, which governs on any difference anywhere in this document. Three things
> to action first:
>
> 1. **Collect the top 16 examples per feature** — you had collected 5. **16 is the primary depth
>    and it carries the claim.** Qwen truncates 25 → 16 by plain slice, so both columns match.
>    *(A v1.2 banner circulated briefly saying 20/20. **That is superseded and wrong.** The pool
>    figure proved unverifiable: the fetcher truncates large documents at a varying point,
>    returning 15/16/19/20 for the same cached JSON. Truncation can only **undercount**, so one
>    reading of ≥16 proves the pool is ≥16 — **16 is measured, 20 is aspirational.** Full history
>    in §7.1.)*
> 2. **TOP-K IS ALREADY CONFIRMED — do not re-verify it, and do not hold adjudication for it.**
>    Both columns are strict top-k by activation: Gemma's maxValues descend strictly with no band
>    structure and SAEDashboard's `binMin`/`binMax`/`binContains` are the sentinel `-1` throughout
>    (idx 11270 at density 1.5e-6 is the decisive case); Qwen verified empirically across all 40.
>    **Matched counts are matched construct. No disclosure needed on this axis.** *(A v1.2 banner
>    asked you to verify this first — that instruction is discharged.)*
> 3. **Feature 8667 (2 records)** is a structural twin of Qwen's 90863 (2 firings): keep it in the
>    denominator, `indeterminate` if its snippets do not decide, disclose the support count.
>    **There is no minimum-support threshold.**
>
> **Ties are present on both sides** — Gemma idx 3648 holds three records at exactly 1155.9937 and
> idx 7623 two at 4587.2803. Take the first *n* in array order; **do not re-sort.**

| | |
|---|---|
| **Version** | **v1.7**, frozen 2026-08-08. Depth history `5 → 16 → 20 → 16`, every move evidence-driven, **no counts existed at any point** — see §7.1. |
| **Status** | **BINDING on both models.** Written *before* the 40-feature `rwu04lpb` adjudication data exists. |
| **Source of truth** | `reports/cross_model_comparison_qwen_column.md` §9. This file is a verbatim extract for handoff; if the two ever differ, §9 governs. |
| **Applies to** | Qwen `rwu04lpb` layer 28 (n = 40) and Gemma Scope 2 layer 31 (n = 40), identically |
| **Author** | Mohamed El Yazid — IID |

**Why a pre-registration at all:** Gemma's earlier 58 % was computed under *implicit* class
definitions. This document makes them explicit so both tallies are computed under one rule, and
so neither adjudicator can tune a boundary after seeing which way the count is going.

**Two things that are NOT in scope for you, stated so you don't have to ask:**

1. **Do not compute or report a cross-model difference, delta, ratio, or gap.** Existence and
   direction only. Publish your own composition; the convergence statement is written later, by
   the PM, only after both measurements land.
2. **Do not revive the 58 % / n = 33 browsed sample.** It is pre-registered as superseded. Your
   denominator is **40**.

---

## 1. FOUR-BUCKET SCHEME (binding on both models)

| Bucket | Numerator? | Denominator? |
|---|---|---|
| **surface-form** | **YES — the numerator** | yes |
| **semantic** | no — **reported alongside** | yes |
| **discourse-register** | **no** | **yes** |
| **indeterminate** | **no** | **yes** |

**`indeterminate` is added deliberately, before the data exists.** Without it, a feature whose
snippets do not decide gets silently forced into a bucket — row-level laundering, the exact
failure the bucket rules exist to prevent.

> **PRIMARY RESULT IS THE FULL FOUR-WAY COMPOSITION, NOT THE FRACTION.**
> Publish all four counts. A fraction whose denominator contains two non-numerator buckets is
> sensitive to their size; showing the counts makes that visible instead of hidden.

*(Historical note, record only: the earlier browsed Gemma sample did in effect leave
discourse/register outside both numerators. Catching that is what prompted this ruling. It is
**not** a precedent and is **not** to be mirrored — no rule is inherited from it, and nothing
needs re-tallying.)*

---

## 2. THE BOUNDARY: lexical/POS/n-gram **vs** discourse/register/genre

Both look like "the feature fires on a word class". The cut is **scope of evidence**:

| | **lexical / POS / n-gram** → SURFACE-FORM | **discourse / register / genre** → NEITHER |
|---|---|---|
| Trigger scope | The **token or n-gram itself**, decidable from the span in isolation | The **surrounding passage's function or style**; the trigger token is unremarkable alone |
| Test | Would a token-level lexicon or POS tagger reproduce the firing set? → lexical/POS | Do you need to read the sentence/paragraph to know why it fired? → discourse/register |
| Invariance | Fires on the form regardless of what the passage is doing | Fires across *varied* forms that share a communicative function |
| Examples | plural `-s`; auxiliary verbs; a fixed collocation; a specific punctuation bigram | hedging; contrastive connectives; imperative how-to guidance; academic-abstract register; list-item framing |
| Failure mode | Over-assigning here when the token merely *correlates* with a genre | Over-assigning here when one connective word does all the work |

**Tie-break:** if the top-activating snippets share a *surface string* → lexical/POS. If they
share a *communicative function* across differing strings → discourse/register. If both, the
class is decided by whichever survives when the shared string is removed from consideration.

---

## 3. THE SURFACE-FORM vs SEMANTIC CUT

**SURFACE-FORM** — the feature tracks *how text is written*: orthography, token identity,
morphology, numeric/date form, code syntax, layout/markup. It would substantially survive
translation into meaningless-but-well-formed text of the same shape.

**SEMANTIC** — the feature tracks *what the text is about*: entities, actions, abstract
concepts, institutional roles. It would substantially survive paraphrase into different surface
forms carrying the same meaning.

**Operational test — apply in this order. The order is load-bearing.**

1. *Paraphrase test* — rewrite the snippet with different words, same meaning. Would it still
   fire? **Yes → semantic.**
2. *Form-preserving nonsense test* — keep the shape (digits, casing, syntax, markup) but destroy
   the meaning. Would it still fire? **Yes → surface-form.**
3. Both yes, or both no → **discourse/register**, not a forced choice.

---

## 4. RULE (d) — TIE-BREAK WHEN THE TWO AUTOINTERP PASSES DISAGREE

*This affects roughly 30 of your 40 rows, so read it before you start.*

> **SNIPPETS ADJUDICATE. LABELS ARE HYPOTHESES TO TEST, NEVER EVIDENCE.**

Not a new rule — it is the protocol that already **overturned both labels in 8 of 20 cases**
(`docs/pi_directive_plan_2026_08.md:119`). It is made explicit because label quality
demonstrably does not support adjudication: the two passes disagree materially on ~60 % of
checked features (`:310-315`), and `gemini-2.5-flash-lite` returns strings such as *"dare I
say"*, *"this arena"*, *"keyboard, Lens"*, *"seeking"* — token dumps, not classifications.

Procedure when the two passes imply different classes:

1. **Ignore both labels.** Read the top-activating snippets and apply §3's ordered test.
2. Use the labels only afterwards, as *hypotheses to check against the snippets* — never as a
   tiebreaker, never as deciding evidence.
3. **A label never decides a class.** If the snippets are genuinely insufficient, the class is
   **`indeterminate`** — **never the label's guess**. Disagreement between passes is weak
   evidence that the feature is *hard*; it is not evidence *for* any class.

---

## 5. HARD-CASE RULING — semantic domain, orthographic trigger

Two of your rows turn on this and several others will: **idx 9115** fires on the substring
`"drum"`; **idx 5094** fires on words beginning with `"V"`.

**RULING: both are SURFACE-FORM (class 2, lexical/POS/n-gram).** Recorded here so neither
adjudicator re-derives it and they cannot diverge.

**Why**, by §3's ordered procedure:

1. **Paraphrase test first.** Rewrite with different words, same meaning: *drum → percussion
   instrument*; a V-word → a synonym starting with another letter. The trigger string disappears
   and the feature would **not** fire. **Fails the semantic test.**
2. **Form-preserving nonsense test.** Preserve orthography, destroy meaning: *conundrum*,
   *eardrum*, an invented V-word. The trigger string survives and the feature **would** fire.
   **Passes the surface-form test.**

The apparent semantic domain (percussion; nothing coherent for "V") is an **artifact of which
words happen to contain the string**, not the thing the feature tracks. A feature that survives
destruction of meaning but not preservation of meaning is tracking form.

**The one diagnostic that would overturn this — apply it before accepting the ruling on any
similar row.** Check whether the snippets contain a *semantically unrelated* word carrying the
same string (*conundrum*, *eardrum*):

- Such a word **is** present and the feature fires → **surface-form, confirmed**.
- The top-16 contain **only** semantically coherent uses, no counterexample → the orthographic
  reading is **unproven** → record **`indeterminate`**. Do not guess either way.

Generalised: *semantic domain + orthographic trigger → surface-form, **unless** the top-16
contain no orthographic counterexample, in which case → indeterminate.*

---

## 6. THE NINE CLASSES (+ indeterminate)

**Surface-form bucket → the numerator**

1. **numeric/date/quantitative** — digits, dates, timestamps, measurements, ordinals; the
   numeric *form* is the trigger.
2. **lexical/POS/n-gram** — a specific token, morpheme, POS category, or fixed collocation (§2).
3. **code** — programming syntax, identifiers, markup, structured-data literals.
4. **formatting** — layout and typography: bullets, headers, delimiters, whitespace/punctuation
   structure.

**Semantic bucket → reported alongside, not in the numerator**

5. **named entities** — specific people, places, organisations, works, brands.
6. **action verbs** — dynamic events/processes as *meaning*, not as verb morphology (if
   morphology drives it → class 2).
7. **abstract concepts** — internal states, moral/evaluative qualities, non-perceptual notions.
8. **institutional roles** — occupational or organisational positions ("staff", "personnel",
   office-holders).
11. **topical domain** — the feature tracks a **subject-matter field** rather than a specific
    entity, action, abstraction or role. Examples: electoral politics, document typesetting, soil
    science, chemistry, cookery, horror fiction, job-seeking. *(Added 2026-08-07, mid-adjudication
    — see the note below. Numbered 11 so the existing 1–10 assignments are undisturbed.)*
    - **Test:** name the field in one to three words; then confirm the top-16 span **multiple
      distinct entities or documents within that field**, and that paraphrase preserves firing.
    - **Guard against catch-all use:** if you cannot name the field without enumerating the
      examples, the row is **`indeterminate`**, not class 11.
    - **vs class 9 (discourse-register):** class 9 is *communicative function* — how and why the
      text is written. Class 11 is *subject matter* — what it is about. Promotional copy across
      unrelated products is 9; soil science across unrelated documents is 11.
    - **vs class 5 (named entities):** class 5 fires on **specific** entities. Class 11 fires on
      the field regardless of which entities appear in it.
    - **vs class 7 (abstract concepts):** class 7 is explicitly non-perceptual. Concrete,
      perceptual domains (soil, recipes) belong in 11, and class 7 is **not** widened to absorb
      them — merging them would make the class-7 count uninterpretable.

> **Why this was added after adjudication began, and why it is not outcome-driven.** The four
> semantic classes 5–8 are entity-, action-, abstraction- and role-shaped; none describes a feature
> whose organising principle is a subject-matter field. The gap was found from evidence (idx 3169
> electoral politics, idx 3648 document typesetting) **before any tally, count or fraction had been
> computed**, and it is expected to affect ~7+ of 40 rows. **The change moves rows INTO the semantic
> bucket, which makes the surface-form skew HARDER to support, not easier** — it cannot have been
> motivated by the result it works against. The alternatives were rejected on grounds recorded
> here: forcing these rows to `indeterminate` would systematically deflate the semantic count and
> inflate the two non-numerator buckets; widening class 7 would merge perceptual subject domains
> with non-perceptual abstractions under one uninterpretable label.
> **Rows classified before this addition are protected by the §7 post-hoc re-check**, which
> re-examines every Gemma row against its retained deciding quote under the final understanding.
> Class 11 binds **identically on both models**.

**In the denominator, in neither numerator**

9. **discourse-register** (genre) — communicative function, stance, or text-type (§2).
10. **indeterminate** — the top-16 snippets do not decide. **A required disposition, not a
    failure.** Use it whenever evidence is insufficient; when the two autointerp passes disagree
    and the snippets do not resolve it (§4); or when a semantic-domain / orthographic-trigger row
    has no counterexample in the top-16 (§5). **Never force a row into a bucket to avoid using
    this.**

---

## 7. ADJUDICATION PROTOCOL (identical both models)

- **Evidence:** top-activating snippets only, at the depth fixed in §7.1. **Autointerp labels are
  not evidence.**
- **Sampling:** seeded-random draw, **seed recorded**. Gemma n = 40, Qwen n = 40. **No
  hand-picking; no substituting a feature because it turned out uninformative.** *(The figure 33
  belongs to the superseded browsed sample and is not a draw size under this protocol. Your
  denominator is 40.)*
- **One label per feature.** Ambiguous → the *dominant* class across snippets; if genuinely
  split → class 9.

### 7.1 EVIDENCE DEPTH — MATCHED AT 16/16 (binding, pre-registered before any counts)

| | |
|---|---|
| **PRIMARY — carries the claim** | **16 examples per feature, both columns.** Gemma: Neuronpedia's top **16** (you had 5). Qwen: Engineer 3's 25 truncated to **16 by plain slice, no re-sort**. |
| **SENSITIVITY** | Qwen at the full **25** — a depth-robustness check only. **Never compared to Gemma.** |
| **Low-support twins** | Gemma **8667** (2 records) and Qwen **90863** (2 firings). **In the denominator; `indeterminate` if the snippets do not decide; support count disclosed. No minimum-support threshold** — a low-support feature is not dropped and not forced. |

**Why depth is matched at all.** A 5-vs-25 gap would have pushed a **directional artifact into
the primary number**: the shallower column accumulates `indeterminate` purely from having looked
less, and that shows up as a real-looking difference in composition. Matching the depth removes
it. This is why the pull to 16 is not optional and why the primary number cannot be computed at 5.

**Revision history — state all three moves in your methods, not just the final value.**
`5 → 16 → 20 → 16`. Every move was evidence-driven and **no counts existed at any point**, so
none of them is outcome-switching — but a reader who sees only the endpoint cannot verify that,
so give the sequence.
1. **5 → 16.** Matching depth across columns, to remove the directional `indeterminate` artifact.
2. **16 → 20.** A corrected reading said Neuronpedia's pool was 20; the original 16 had come from
   an unreliable count-style query.
3. **20 → 16, and this is the binding value.** The pool figure itself proved unverifiable: the
   fetcher **truncates large documents at a varying point**, returning 15, 16, 19 or 20 for the
   same cached JSON depending on prompt style. Two internal contradictions establish this is tool
   failure rather than real variation — idx **2848** reported "16 entries" while citing an ID
   span of 20 objects (`…411f5`–`…41208`, 0x41208 − 0x411f5 + 1 = 20), and idx **13848** returned
   the same terminal element (`maxValue` 1086.5598) at two different positions, 19 and 16.
   **Truncation can only undercount, never overcount** — so a single reading of ≥16 proves the
   pool is ≥16, and 16 is therefore *verified* to exist in every pool. **20 is not verified
   anywhere.** That asymmetry alone decides it: a 20-cap could silently fall short on any feature
   whose pool the instrument never confirmed, reintroducing the invisible mismatch this ruling
   exists to close. **16 is measured; 20 is aspirational.**
   *(Corrected 2026-08-07: an earlier version of this section cited "idx 7623 reads 19 with
   position 20 absent" as a measured fact. **Withdraw that example.** The enumeration pass has
   since been caught **dropping** values — 7623's anchored pull returned 3983.001 at position 6,
   correctly ordered between 4023.3096 and 3981.8379 and absent from the enumeration, and 2848
   behaved identically with 1052.2909. Every "19" reading is therefore attributable to the
   enumeration omitting an item, not to a 19-item pool; 7623's pool is most likely 20. **The
   ruling is unchanged and is not reopened** — it never depended on that example, only on the
   asymmetry between what is verified present and what is not.)*

**Top-k construct is CONFIRMED on both sides — this axis needs no disclosure.** Gemma: maxValues
descend strictly in array order with no band structure across features spanning three orders of
magnitude in density, and SAEDashboard's quantile markers `binMin`/`binMax`/`binContains` are the
sentinel `-1` on every entry checked, so no quantile subsampling was applied. Idx **11270** is the
decisive case — at density 1.5e-6 a stratified sampler would have to reach into low-activation
bands to fill the pool, producing visible banding, and the descent stays smooth (2132 → 1649).
Qwen: verified empirically across all 40 features, zero exceptions (`characterize_lite.py:192`,
`reverse=True`). **Both columns are strict top-k, so matched counts are matched construct.**

**Ties are present on both sides — the no-re-sort rule is not Qwen-specific.** Gemma idx **3648**
holds three records at exactly 1155.9937 and idx **7623** two at 4587.2803. Take the first *n* in
array order. **Do not re-sort:** on tied activations a re-sort would silently reorder and
desynchronise the primary and sensitivity arms for reasons unrelated to depth.

**Depth interacts with §5.** The counterexample diagnostic (semantic domain + orthographic
trigger) is applied over the **primary 16**, not over 5 — a wider window makes an orthographic
counterexample more likely to appear, which is exactly why the depth must be fixed in advance
rather than chosen per row.
- **Low-confidence features stay in the denominator**, flagged, never dropped.
- **Blind to the hypothesis:** adjudicate every row before computing any fraction.
- **Record per feature:** id, assigned class, bucket, confidence, **and the snippet evidence that
  decided it** — so the tally is auditable rather than a bare percentage. This is exactly what
  the Gemma side currently lacks.

---

## 8. WHAT VOIDS THE COMPARISON

Any one of:

- a bucket rule differing from §1 on either model;
- autointerp labels used as evidence rather than hypotheses (§4);
- hand-picked samples;
- features dropped from the denominator;
- `indeterminate` avoided by forcing rows into a bucket;
- publishing a bare fraction instead of the four-way composition;
- reviving the superseded browsed-sample number.

**And regardless of outcome: existence and direction only, never magnitude.**

---

## 9. REPORTING TEMPLATE — TWO SEPARATE TABLES, never one with two columns

**A two-column table asserts a controlled comparison in its layout.** The two measurements were
independently conducted and are **not** matched on architecture, expansion factor, layer depth,
corpus, or selection protocol. Each gets its own self-contained table, in its own section, with
its own methods line. **Do not merge them; do not place them adjacent; do not add a percentage,
delta, ratio, or "gap" column; do not write a header spanning both models.**

Every methods line must state the **evidence depth**. A composition table without its depth is not
interpretable, because `indeterminate` is depth-sensitive by construction.

**Result B — Gemma Scope 2 L31 composition** *(uniform draw, n = 40, seed …, layer 31, JumpReLU
~4.2×; **evidence depth 16/feature — top 16 by activation**; adjudicated per pre-registration
v1.7)*

| Bucket | Count |
|---|---|
| surface-form | *n* |
| semantic | *n* |
| discourse-register | *n* |
| indeterminate | *n* |
| **total (denominator)** | **40** |

**Result A — Qwen `rwu04lpb` composition** *(uniform draw, n = 40, seed …, layer 28, TopK 32×;
**evidence depth 16/feature — top 16 of 25 by plain slice**; adjudicated per pre-registration
v1.7)* — same table shape, separate section, produced independently.

**Convergence statement** — separate section, written **only after both land**, by the PM: what
each measurement independently found, and what the two **jointly** support. Existence and
direction only; no magnitude, no subtraction.

---

## 10. WHAT TO RETURN

0. **DISCHARGED — do not action.** This item asked you to verify whether Neuronpedia's records
   are top-k by activation. **That is confirmed on both sides** (monotonic descent, no band
   structure, `binMin`/`binMax`/`binContains` sentinel `-1`, idx 11270 decisive; Qwen verified
   empirically across all 40). Retained only so the discharge is on the record.
0b. **Instead, report the anti-contamination checksum for every row.** Snippets MUST be fetched
   **anchored to `maxValue`, with an explicit read-the-tokens / do-not-consult-explanations
   instruction**, and the returned sequence **checksummed against an independently verified
   enumeration**. A row enters the table **only if its checksum matches**. Evidence collected
   under any other protocol is discarded, not downgraded.
1. The 40-row adjudication table: `feature_idx | class (1–10) | bucket | confidence | support count | deciding snippet evidence`, adjudicated at **depth 16**.
2. The four-way composition table above, filled in.
3. The recorded **seed** for the uniform draw.
4. Every row you assigned `indeterminate`, with the reason (insufficient evidence / passes
   disagreed and snippets did not resolve / no orthographic counterexample in top-16).
5. Any row where you believe this pre-registration is **wrong or silent** — flag it rather than
   improvising a boundary. A gap in the pre-registration is a PM decision, not an adjudicator's.

**Do not** compute a Qwen comparison, a delta, or a headline percentage.

---

## 11. AMENDMENTS v1.6–v1.7 — 2026-08-08 (governs on any conflict with §1–§10)

Four independent reports converged on the same structural gap: **the adjudicators have been
inferring which token fires, when the data says which token fires.** §11.1 closes that. §11.2–§11.4
handle the consequences. §11.5–§11.7 rule the named cases.

### 11.1 THE MARKED ACTIVATING TOKEN IS PRIMARY EVIDENCE, ON BOTH COLUMNS

Both corpora carry per-token activations. Qwen has exact-span marking (offset-0 validated: 100%
exact, 0% at offset 1). Gemma's Neuronpedia raw JSON carries `tokens[]`, per-token `values[]` and
`maxValueTokenIndex` — present all along, unused because the earlier summarizer-mediated reads
could not align parallel arrays. Parsed directly, they can.

**Binding: classify on the trigger, not on the context.** A feature is a function of activations;
what it fires *on* is what it detects. The surrounding passage is where the trigger occurs, not
what the feature is. Where marker and passage disagree, the marker governs.

> **⚠ THIS AMENDMENT FAVOURS THE RESULT. Class 11 worked against it; this one works for it.**
> Token-level triggers map to surface-form classes *by construction*, so sharpening trigger
> identification is expected to move rows into the numerator on balance. It is adopted anyway,
> because the alternative is knowingly adjudicating from weaker evidence when stronger evidence is
> in hand — but the direction is disclosed, and it is not enough to disclose it.
>
> **Mandatory: report the tally twice.**
> - **Primary tally** — trigger-primacy applied.
> - **Conservative tally** — every row whose class changed on marker access *in the direction of
>   the numerator* is reset to `indeterminate`.
>
> The conservative tally is a floor, not a sensitivity check, and **both go in the write-up**. If
> the qualitative finding does not survive the conservative tally, it is not reported as found.
> Marker-driven changes must therefore be **logged per row at the moment they occur** — a row's
> pre-marker class cannot be reconstructed afterwards.

**Symmetry is the binding constraint, not the marker itself.** §8 already voids the comparison on
evidence asymmetry. **No row in either column may be classified under trigger-primacy until both
columns have marker access.** Until then, rows turning on trigger-vs-context are `parked` (§11.2).

### 11.2 `parked` — A DISPOSITION DISTINCT FROM `indeterminate`

§7 says *"if genuinely split → class 9."* That covers **split evidence** — different snippets
showing different patterns. It does **not** cover the case both adjudicators actually hit:
**unanimous evidence, competing descriptions.** All 16 snippets show one pattern; two readings of
that one pattern fall in different buckets. Routing those to class 9 or to `indeterminate` would
be a substantive verdict rendered by a rule written for a different situation.

- **`parked`** = the evidence is strong and consistent; a specific, named, obtainable piece of
  discriminating evidence would settle it; that evidence has not arrived yet.
- **`parked` is not a bucket. It never appears in a tally. It is not a synonym for
  `indeterminate` and must never be collapsed into one.**
- Every parked row records: the two competing classes, their buckets, and **the specific
  observation that would settle it.** "Unclear" is not a park; a park names its own resolution.

> **⚠ PARKING IS NOT NEUTRAL AND MUST NOT BE ALLOWED TO STAND.** Rows get parked *because* they
> have strong patterns, and strong patterns are what generate trigger-vs-context ambiguity. So the
> parked set is enriched for exactly the rows that would otherwise be classified, and the rows that
> pass the gate are enriched for rows with no pattern — which are `indeterminate` by definition.
> Left unresolved, parking silently drains the numerator into the denominator. This is the sixth
> instance of the project's recurring directional artifact: *anything that thins evidence deflates
> the surface-form count.* It is the first instance created by governance rather than by an
> instrument.
>
> **Therefore: an unresolved parked row VOIDS THE TALLY FOR ITS COLUMN (added to §8).** It does not
> default to `indeterminate`, it is not dropped, and the denominator is not reduced. Publishing a
> composition with rows still parked is prohibited.

### 11.3 REASON CODES ON EVERY `indeterminate`

`indeterminate` currently pools failures with opposite causes. Two features that are weak and rare
but maximally diverse, and one feature whose evidence collapsed to two documents, are the same
count and different findings. Every `indeterminate` row now carries exactly one code:

| Code | Meaning |
|---|---|
| `I-THIN` | Too few distinct sources or too weak an activation to support any reading. |
| `I-DIVERSE` | Ample distinct sources, no pattern coheres across them. The feature is genuinely polysemantic or weak-and-diffuse at this depth. |
| `I-SILENT` | A clear, stable pattern exists, but **no class in §6 describes it.** A pre-registration defect, not an evidence defect. |
| `I-AMBIGUOUS` | Two readings in different buckets survive all available discriminating evidence, including the marker. A terminal park. |

**This is a reporting refinement and moves no row between buckets** — it therefore cannot be
outcome-driven, and needs no direction disclosure. Retrofit to all rows already classified.
`I-SILENT` counts are a result about the scheme and are reported as such, not buried in a total.

### 11.4 THE ADJUDICATION MUST LIVE IN A HASH-BOUND FILE

The taxonomy arm's entire output — every class, bucket, confidence and deciding quote in both
columns — currently exists **only inside agent reports in a chat transcript.** A search of the
tracked tree for the calibration feature indices returns zero hits. Every other artifact in this
project is hash-bound; the one that carries the claim is not, and it is not visible to any lane but
the one that produced it.

**Binding:** both columns are written to `reports/adjudication_ledger.md`, one row per feature,
schema `feature_idx | column | class | bucket | conf | reason_code | distinct_sources | n_firings |
marker_token | pre_marker_class | deciding_quote | disposition`. Appended as rows are decided, not
at the end. Hash-bound in `VERIFICATION_LOG.md` at each column's completion. **A call not in the
ledger did not happen.**

### 11.5 RULINGS ON THE TWO §10.5 SCHEME-SILENCE FLAGS

**Gemma 3039 → class 4, surface-form, stands.** The flag was that "verbatim repetition / templated
boilerplate" is nowhere in §6. Correct, and it does not need to be: the markers are `:` ×4, `\n\n`
×2, `(`, `<`, `"` — literally class 4's "delimiters, whitespace/punctuation structure." The
repetition is why the delimiters are *frequent*; the delimiter is what *fires*. Under §11.1 the
trigger governs, so §6 covers this row unextended. **Class 4 is not widened** — widening it would
have been a numerator-favourable scheme change, which is precisely what §11.1's disclosure exists
to prevent being made silently.

**Gemma 5231 → `indeterminate`, code `I-SILENT`.** The flag was that a syntactic construction — the
constituent closing a negation scope — matches none of class 2's four listed triggers. The §2
tie-break was applied on the ground that the governing string (`not`/`n't`/`neither`) is *in the
span*; but under §11.1 the marker sits on the **complement, not on the negator**, and in-span is
not at-marker. So trigger-primacy removes the basis for class 2 without supplying a replacement:
the trigger varies lexically across all 16 (*sad, industry, secretive, town, highest, immune,
-inate, individuals*) and the invariant is a **structural position**, which §6 does not encode.
Class 9 (hedging) is a live reading and would also leave the numerator.
**The honest disposition is that the scheme has a hole here, not that the feature is unclear.**
Any of the three available moves — inventing class 12, stretching class 2, or forcing class 9 —
would be a mid-adjudication scheme change made after the evidence was seen. `I-SILENT` records the
defect where a reader can count it.

### 11.6 THE FIRST INTER-RATER CALIBRATION IS VOID

Ten rows were drawn; **no usable agreement figure exists.** Two independent defects, both in the
calibration's design:

1. **Four rows were not blind.** The second adjudicator was instructed to read the pre-registration
   and the methods document in full before adjudicating. Those documents *contain the first
   adjudicator's outcomes* — §5 rules 5094 by name; §4.3 gives 3349's class and quotes three of
   212's records verbatim; §3.5 gives 14622's support collapse, both competing readings, and its
   confidence revision. The two instructions were in direct contradiction and the adjudicator
   flagged it rather than concealing it, which is the correct behaviour and the reason this is
   recoverable. **5094 is worse than contaminated: §5 pre-rules it explicitly so that "neither
   adjudicator re-derives it and they cannot diverge." A pre-ruled row cannot measure agreement —
   it measures compliance.** It should never have been drawn.
2. **Five of the remaining six were evidence-asymmetric.** The second adjudicator used the Gemma
   marker; the first did not. Agreement or disagreement on those rows measures information
   asymmetry, not inter-rater variance. This is demonstrated rather than assumed: 3070 reads as
   *first-person interview register* (class 9, denominator) from the window alone and as *and/but*
   (class 2, numerator) with the marker — **one row, one evidence upgrade, a bucket flip.**

That leaves **one** row both clean and evidence-symmetric. n = 1 is not a calibration.

**Re-run, after both columns have markers.** Draw 10 fresh rows **in index order** from the pool
(content-blind selection), excluding every index named anywhere in the prereg, the methods document
or the ledger. Both adjudicators work from the same evidence, both under §11.1. Agreement is
computed by the orchestrator only, on **bucket**, and separately on **class**; a bucket-level
disagreement is the one that matters.

**The void calibration is not a wasted pass.** It produced the marker finding that drove §11.1, an
independent reproduction of 14622's support collapse, the checksum-clean confirmation on all eight
Gemma features, both §10.5 flags, and §11.7 — all of which survive because none of them depend on
the blind.

### 11.7 GEMMA PACKED-STREAM SPLICE — THE MIRROR OF §4.6

Gemma records splice unrelated documents at seams with **no separator** (`…opinionTomahawk`,
`…kainateA new ransomware`). Measured across eight features it runs **2 to 11 of 16**, so it is a
corpus-wide packed-stream property, not a feature property. It is the Gemma-side analogue of the
Qwen opening-line trap and is handled the same way: **a pattern that appears only across a splice
seam is an artifact of corpus packing and cannot support a class.** Where a splice straddles the
marker's ±10-token context, the context is truncated at the seam rather than read through it.

This is the **seventh characterised instrument failure mode**, and the first found on the Gemma
side by looking for the mirror of a known Qwen defect — a search that should be run in both
directions for every artifact already recorded.

### 11.8 THE CALIBRATION MEASURED THE MARKER, NOT THE RATERS (2026-08-08)

The first adjudicator returned their eight calibration calls **unrevised, including the two since
overruled**, which is what makes the following computable. Their calls were made from the window
alone; the second adjudicator's from the window **plus the marker**.

| idx | rater 1 (no marker) | rater 2 (marker) | bucket 1 | bucket 2 | effect |
|---|---|---|---|---|---|
| 3039 | 10 indeterminate | 4 formatting | indeterminate | surface-form | **→ numerator** |
| 3070 | 9 discourse-register | 2 lexical | denominator | surface-form | **→ numerator** |
| 3349 ⚠ | 3 code | 3 code | surface-form | surface-form | — |
| 3358 | 9 discourse-register | 10 indeterminate | denominator | indeterminate | lateral |
| 5094 ⚠ | 2 lexical | 2 lexical | surface-form | surface-form | — |
| 5231 | 2 lexical | 2 lexical | surface-form | surface-form | — *(both overruled → `I-SILENT`)* |
| 212 ⚠ | 9 discourse-register | 2 lexical | denominator | surface-form | **→ numerator** |
| 976 | 7 abstract concepts | 7 abstract concepts | semantic | semantic | — |
| *Qwen* 14622 ⚠ | 11 topical domain | 5 named entities | semantic | semantic | class differs, bucket holds |
| *Qwen* 126804 | 2 lexical | 2 lexical | surface-form | surface-form | — |

⚠ = blind broken (§11.6). Raw bucket agreement 6/10, raw class agreement 5/10 — **both figures are
uninterpretable** and are recorded only so nobody recomputes them and reports them.

**The inter-rater result stands at n = 1** (Qwen 126804, agree). Unchanged from §11.6.

**But the marker effect is now measured rather than predicted, and it is one-signed.**

- Bucket changed on marker access: **4 of 8** Gemma rows.
- Moved **into** the numerator: **3** (3039, 3070, 212).
- Moved **out** of the numerator: **0.**
- Lateral (denominator → indeterminate): 1 (3358).
- Surface-form count over these eight rows: **3 without the marker → 6 with it. It doubles.**

Restricting to the five Gemma rows that are *also* clean of contamination (3039, 3070, 3358, 5231,
976) preserves the direction: 3 of 5 change bucket, 2 into the numerator, **0 out**.

> **This is why §11.1's conservative tally is mandatory and not a sensitivity check.** On this
> sample the conservative floor is the difference between 3/8 and 6/8 — a factor of two on the
> headline statistic, produced entirely by evidence depth on a *fixed* set of features and a
> *fixed* scheme. **The composition is at least as sensitive to how deeply the evidence is read as
> it is to which model produced it.** Any convergent-evidence claim that does not survive the floor
> is an artifact of reading depth, and the two columns must be read at equal depth or not compared
> at all (§8).
>
> **Caveats, stated so the number is not over-read:** n = 8, non-random (a calibration draw, not
> the seeded sample), 3 of 8 contaminated, and one rater is not two independent measurements of the
> marker's effect. **The direction is the finding; the factor of two is an illustration and must
> not be reported as an effect size.**

**Consequence for §11.5, which I must tag against myself.** I ruled 3039 → class 4 while holding
only the second rater's report; I did not know the first rater had called it `indeterminate`. The
ruling is correct on the merits — the markers *are* delimiters, which is class 4's own wording —
but it is not an affirmation of an existing call, it **resolves a disagreement I could not see**,
and it is **a marker-driven move into the numerator.** It therefore resets under the conservative
tally exactly like 3039's row above. The 5231 ruling moves the other way (out of the numerator) and
does not reset.

**`5231` is the limit case on what agreement can certify.** Both raters independently returned
class 2, surface-form. **Both were overruled** (§11.5): under trigger-primacy the marker sits on
the complement, not the negator, so the §2 tie-break they both applied had no basis. **Two
independent adjudicators agreed and were jointly wrong, because they applied the same defective
rule.** Inter-rater agreement certifies only that the scheme was applied consistently — it cannot
detect a defect in the scheme itself. This is the adjudication-layer form of the already-recorded
principle that *two agreeing pulls through one summarizer are one observation, not two.*

### 11.9 TWO RECORD DEFECTS FOUND BY WRITING THE LEDGER

**(a) Confidence is absent on the early rows, and will not be reconstructed.** Confidence entered
the first rater's per-row output only from idx 4090 onward; of the eight calibration rows only 212
and 976 fall after that change. The rater reported the other six as **absent rather than
reconstructing them**, on the ground that a confidence recalled now is contaminated by everything
learned since. **That is correct and is adopted as a rule: no field is ever backfilled from
memory.** An absent field is data about the record; a reconstructed one is fiction with a
plausible shape. §10.1 requires confidence on the 40-row table, so this is a **declared
divergence** — the §11.6 re-run supplies confidence agreement, and the early rows carry `—`
permanently.

**(b) The record is uneven, and it is thinnest exactly where the claim is strongest.** Rows
3039–3648 carry a class and nothing else — no confidence, no distinct-source count, no deciding
quote, no density. Rows from 4090 carry most fields; rows from 14622 carry all of them.
**Those early, unauditable rows include three of the four rows in the Gemma surface-form
numerator** (3349, 5094, and 5231 before it was overruled). The numerator's evidentiary base is
therefore the least auditable part of the column — a fifth directional finding, and the first that
concerns *provenance* rather than classification.

**Binding: the byte-exact retrofit runs in record-completeness order, worst-documented first, not
in index order.** Sweeping the column in index order would leave the numerator's weakest rows for
last, which is the ordering most likely to run out of time exactly where it matters. Retrofitted
rows keep their original call in `pre_marker_class`; the diff between the two is data, not
correction.
