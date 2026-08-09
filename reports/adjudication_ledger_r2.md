# ADJUDICATION LEDGER — RATER 2 partition (§12.1)

Binding artifact under prereg v1.6 §11.4, partitioned under §12.1. **Rater 2 writes this file
only and reads no other ledger.** The merged file is derived by the orchestrator; no rater
reads it.

Prereg: `reports/adjudication_prereg_v1.md` v1.6, sha256
`6194e13a8f464bc15f24172134d633d3f5f08a60d4423dbbb0602f7e66ee1052`.
Methods: `reports/methods_and_limitations_v1.md`, sha256
`3bdbdb05eba868febf6a277548b665dc38e7af6b1ca29e670563fa404555a5b1`.

**No tally is computed in this file.** One row is `parked`; under §11.2 an unresolved parked row
voids the tally for its column.

**Machine record:** `reports/adjudication_ledger_r2.canonical.json`, sha256
`ecc544d16dfc65175825e4e37d6f411ee74d4d72a15bb4f5bd105af3a8825a0f` — **24 rows** (draw 2's ten plus
draw 3's fourteen), 22 classified and 2 parked, validated clean under the §16.4 schema. Supersedes
`8be88650edd03c52435cb750b9d029d24f354b839d060aff400145d037155b63`, which is the 10-row state and is
retained, not deleted. This prose file is the human
record; the canonical JSON is what a tally reads. The two were cross-checked programmatically —
all 10 rows agree on `feature_idx`, `class` and `disposition`. **No bucket is written in either
file**: the class→bucket mapping lives in the merge instrument, so a bucket written here would be a
second source of truth able to drift from the first.

**Status: closed.** All ten rows are final. `12403` is `parked` under §16.4, which is a legal
disposition; the canonical file validates clean with zero errors and zero warnings.

**These rows never enter a composition tally** (§16.2 — rater 1 is the adjudicator of record). They
measure reliability. `12403` is excluded from the agreement denominator, so **agreement is over 9 of
10 and is stated as such, never as 10.**

> ⚠ **Merge hazard.** These ten rows were appended to `adjudication_ledger.md` in the turn before
> §12.1 partitioned the ledger. That copy predates the class 12 retrofit below and will duplicate
> these rows on merge. It must be removed from the r1 file by the orchestrator — Rater 2 cannot,
> being now barred from opening it. **This file supersedes that copy.**

---

## Draw 2 — §11.6 re-run, Gemma column

**Blind direction (§12.1 ruling).** Rater 1 has not touched these ten rows, so on this draw
Rater 2 is first and Rater 1 is the blind second. Neither §11.6 defect can recur: both raters
marker-informed on byte-identical evidence, and none of the ten is named in the prereg or the
methods document.

**Selection.** Index order over the Gemma pool, content-blind, excluding every index named in the
prereg, the methods document, or the ledger. 29 of 40 excluded, 11 survive, this draw takes 10.
`15054` is the sole remainder. **No third blind Gemma draw exists.**

**Evidence.** Depth 16. Primary evidence is the marked activating token (§11.1) from
`scripts/legacy/gemma_neuronpedia_raw/<idx>.json`, corroborated by the full ≥50%-of-max activation
profile. Context truncated at splice seams (§11.7). `explanations` never opened. Checksum —
fulltext top-16 `maxValue` equals the raw enumeration's first 16 — **10 of 10 match**.
All ten hold 16 distinct sources over 16 records (20 available; 16 by plain slice, no re-sort).

| feature_idx | column | class | bucket | conf | reason_code | distinct_sources | n_firings | marker_token | pre_marker_class | deciding_quote | disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 9012 | gemma | **12 relational/positional — delimiter introducing an appositive or elaborating continuation** | denominator only | high | — | 16 | 16 of 20 | `,` ×13, `—` ×2, `–` ×1 | **10 indeterminate** | "health cards to all residents of Quebec[,] including temporary and undocumented" — all 23 tokens at ≥50% of record max across all 16 records are commas or dashes. Prong 1(b) verified: **173 commas across the 16 records, argmax only 13 times, 155 below half-max** — a feature firing on ~7.5% of available commas is not a comma detector | classified (**retrofit from class 4, §13.5**) |
| 9105 | gemma | **12 relational/positional — object of *use*** | denominator only | med | — | 16 | 16 of 20 | complement of *use* — ` form`, ` links`, ` information`, ` website`, ` app`, ` it`, ` materials` | 10 indeterminate (I-DIVERSE) | "Please use this[ form] for credit card payments" / "Google will use this[ information] to evaluate your use of" — trigger varies lexically across all 16; the invariant is the object position of *use* | classified (**retrofit from I-SILENT, §12.3**) |
| 11029 | gemma | 2 lexical/n-gram — *chemical* | surface-form | high | — | 16 | 16 of 20 | ` chemical` ×6, ` Chemical` ×5, `Chemical` ×2, `cial` ×2, ` chemicals` | **11 topical domain — chemistry** | "internet awards for tracks on the second "[Chemical] Process"" — a music-track title, semantically unrelated to chemistry, fires; and the misspelling "Chem[cial] Vapor Deposition" fires. §5 counterexample satisfied → surface-form confirmed | classified |
| 11149 | gemma | **12 relational/positional — head noun of the document's own topical compound** | denominator only | med | — | 16 | 16 of 20 | ` SEO`, ` gout`, ` window`, ` loan`, ` attorney`, ` limousine`, ` railroads`, `orer` | 9 discourse-register | "great scope for enhancing local[ SEO]" vs "a very effective[ gout] treatment" — the ≥50% profile is each record's *own* subject keyword, so the field differs per document; §6.11's guard refuses class 11 | classified (**retrofit from I-SILENT, §12.3**) |
| 11763 | gemma | **12 relational/positional — determiner opening a post-copular predicate nominative** | denominator only | high | — | 16 | 16 of 20 | ` the` ×15, ` a` ×1 | **10 indeterminate** | "tiredness is[ the] number one complaint that we visit our doctor with" / "elegance is[ the] status quo" — 16 of the 20 tokens at ≥50% of max are ` the`. Prong 1(b) verified: ` the` occurs **130 times** across these 16 records, is the argmax only **15** times, and **114** occurrences sit below half-max | classified (**retrofit from class 2, §13.3**) |
| **12403** | gemma | **3 code** *vs* **11 topical domain — filesystems/IT** | **surface-form vs semantic** | — | — | 16 | 16 of 20 | ` $` ×6, ` folder` ×6, ` in` ×5, `_` ×4, ` file` ×4, `HOME` ×3, ` mkdir` ×2 | 11 topical domain — software/IT | "chmod -R g+w[ $]REMOTEPATH" / "failed to[ mkdir] "/srv/mediawiki/" / "posted from the photos[ folder] on my laptop" — a path expression throughout, but spanning shell syntax (`$`, `_`, `HOME`) *and* plain-prose path nouns | **parked** |
| 12449 | gemma | 11 topical domain — soil | semantic | high | — | 16 | 16 of 20 | ` soil`/` Soil` ×4, ` clay`/`Clay` ×2, `rained`, ` dirt`, ` grading`, `otechnical`, ` bed`, ` brown` | — | "its needs met (nutritious bio-diverse[ soil], adequate water, plentiful" / "A Professor of[ Soil] Physics in the Department of" — field nameable in one word without enumerating examples; 16 distinct sources; paraphrase preserves firing | classified |
| 13746 | gemma | 4 formatting — sentence/clause boundary punctuation | surface-form | **low** | — | 16 | 16 of 20 | `,` ×5, `.` ×3, `\n\n`, ` (` ×2, + 5 function words | **10 indeterminate** | "In case you want a gentle experience[,] you will find that many showerheads" — 52 of 99 tokens at ≥50% of max are `.`/`,`/`\n\n`/`?`/`:`/`(`. Low confidence: profile diffuse, half the high tokens not punctuation. Recorded alternative: `indeterminate` | classified |
| 13825 | gemma | 2 lexical/n-gram — *job* | surface-form | high | — | 16 | 16 of 20 | ` job` ×11, ` Job`/`Job` ×4, `JOB` — all 16 | **11 topical domain — employment/job-seeking** | "Aguilleira said the[ job] is now to win the tournament" (cricket; *job* = task) and "Booking a[ Job]" (removals firm) — unrelated senses fire, §5 counterexample satisfied → surface-form confirmed | classified |
| 14719 | gemma | 10 indeterminate | denominator only | med | **I-DIVERSE** | 16 | 16 of 20 | ` their`, ` including`, ` have`, ` is`, ` with`, ` are`, ` to`, ` blade`, ` supply`, ` round` | 9 discourse-register | "The sensor element[ is] a ceramic cylinder plated inside" / "The chain and SRAM cassette[ are] a bit louder" — no trigger coheres; 279 tokens at ≥50% of record max across 16 records (~17 per record): weak-and-diffuse at this depth, not polysemantic | classified |

### Class 12 retrofits (§12.3, then §13.3)

`9105` and `11149` moved from `10 indeterminate / I-SILENT` to **class 12**, and `11763` moves from
**class 2 → class 12** under §13.3's replaced test. `9105` and `11763` are the two rows §13.3 names.
All three are denominator-only before and after, so no bucket changes and neither tally moves.

Rater 2's original flag identified the shape (trigger varies lexically; the invariant is *where the
token sits*, not *what it is*) and correctly concluded §6 had no name for it. What Rater 2 could not
determine without §3 in hand: **§3 had already fixed the bucket.** A positional trigger survives
both §3 tests — paraphrase preserves the position, form-preserving nonsense preserves it too — and
step 3 routes both-yes to neither numerator. The bucket was never open; only the name was missing.

Fourth instance of the shape, with `5231` (complement of a negator) ruled under §11.5.

### §13.3 re-check of all ten rows — measured, not asserted

Prong 1(a) read as **non-modal records ≥ 12**, disambiguated by §13.3's own worked example: `9105`
has 11 distinct marker types but 12 non-modal records, and §13.3 routes it to class 12, so the
criterion counts records rather than types.

| feature_idx | distinct marker types | non-modal records | prong 1 | prong 2 | outcome |
|---|---|---|---|---|---|
| 9012 | 4 | 3 | 1(a) fails; **1(b) holds** — punctuation ruled closed-class (§13.5) | "delimiter introducing an appositive or elaborating continuation" | **class 12 (moved)** |
| 9105 | 11 | 12 | 1(a) holds | "complement of *use*" | class 12 ✓ |
| 11029 | 5 | 7 | fails — open-class constancy guard | — | stays class 2 ✓ |
| 11149 | 16 | 15 | 1(a) holds | "head noun of a modifier–noun compound" | class 12 ✓ |
| 11763 | 2 | 1 | 1(b) holds, verified 130/15/114 | "determiner opening a post-copular predicate nominative" | **class 12 (moved)** |
| 12403 | 12 | 13 | 1(a) holds | **fails** — "filesystem path expression" is a content category, not a syntactic role statable against a governor | **stays parked** |
| 12449 | 15 | 14 | 1(a) holds | **fails** — "soil/earth substance" is a semantic field, not a role | stays class 11 ✓ |
| 13746 | 9 | 11 | **1(a) fails (11 < 12); marker not constant so 1(b) unavailable** | — | **stays class 4** |
| 13825 | 4 | 6 | fails — open-class constancy guard (`job`, all four types are case variants of one lexeme) | — | stays class 2 ✓ |
| 14719 | 14 | 14 | 1(a) holds | **fails on evidence** — no stable position exists to name: 279 tokens sit at ≥50% of record max (~17/record) against 23 for `9012`, so the argmax is not distinguished from ~16 other high tokens per record | stays 10 indeterminate / I-DIVERSE |

**Both rows flagged for attention resolve as no-move.** `12403` fails prong 2 and stays parked with
its two original competing readings; `13746` fails prong 1 on both limbs by measurement.

### §10.5 FLAG — RULED in v1.11 §13.5: punctuation IS closed-class, and class 4 survives

**Ruling:** punctuation is closed-class, so prong 1(b) is available to it; class 4 survives because
**prong 2 was already doing the work.** Class 4 is *layout and typography*, which is not the same
thing as grammatical punctuation — an appositive comma is syntax, a `Category:`/`Type:` template
delimiter is layout. Name the position, then read which vocabulary was needed: grammatical → class
12; document → class 4; neither → `indeterminate`, which explicitly does **not** default to class 4,
since defaulting to a numerator class on a failed test is the directional artifact in its purest
form.

**`9012` → class 12**, leaving the numerator. **`3039` and `13746` stand at class 4.** The original
flag is retained below as the record of what was escalated.

#### Original flag as raised

`9012` is the one row whose disposition is not determined by the text as written. Its marker is `,`
×13, `—` ×2, `–` ×1 — constant in the sense §13.3 uses for `11763` (15/16), and the
occurs-elsewhere-without-firing condition is satisfied decisively: **173 commas across the 16
records, argmax only 13 times, 155 below half-max.** Prong 2 would hold — "the delimiter introducing
an appositive or elaborating continuation" names a position, not a token.

The blocker is that §13.3 enumerates the closed classes as *determiner, preposition, auxiliary,
conjunction, pronoun, particle*. **Punctuation is not listed.** §13.3's own rationale applies to it
with full force — a `{,}` lexicon would fire on nearly every document in the corpus rather than on
these 16, which is exactly the independent §2 rejection cited as what makes `11763` safe to route.

**Consequence, and it is large.** §6 class 4 *is* "delimiters, whitespace/punctuation structure". A
class-4 row is by construction a near-constant punctuation marker that occurs elsewhere without
firing. **If punctuation counts as closed-class, essentially every class-4 row satisfies prong 1(b),
and class 4 ceases to exist as a numerator class.** Direction is adverse — it removes rows from the
numerator — so it is not outcome-driven in either direction, but it is a scheme-level change and not
an adjudicator's call. Flagged rather than improvised, per §10.5. `13746` is unaffected either way:
its marker is not constant (modal `,` at 5/16) and it fails 1(a) at 11.

### Schema gap — RULED in v1.17 §16.4, deviation adopted as the general principle

**Ruling:** `"parked"` joins the `disposition` enum, and `class: null` is permitted **only** when
`disposition` is `"parked"`. Omitting the row was the worst option: *a parked row voids a tally, an
omitted row voids nothing* — the instrument would have tallied nine rows and emitted a number that
should not exist. Breaking the schema loudly beat conforming quietly.

**No re-cut was required.** The amendment legalises the bytes already on disk rather than demanding
different ones: `12403` was emitted as `class: null` / `disposition: "parked"`, which is exactly what
§16.4 now permits. Re-validated against the amended schema — 10 objects, **zero errors, zero
warnings**. The digest is therefore unchanged at
`8be88650edd03c52435cb750b9d029d24f354b839d060aff400145d037155b63`; nothing is superseded, because
nothing changed.

**A park in this file does not void the Gemma tally** (§16.2 + §16.4). These rows never enter a
tally, and the adjudicator of record has a call on `12403`, so the column is complete. The row is
excluded from the **agreement denominator** instead, and that exclusion is reported explicitly:
**agreement is over 9 of 10, stated as such, never as 10.** A park by the reliability rater is a
reliability signal, not a completeness gap — conflating the two would let the reliability arm block
the measurement it exists to characterise.

#### The gap as originally raised

The canonical schema fixed `class` as an int 1–12 and `disposition` to the single value
`"classified"`. **`12403` is parked, and neither field could hold it.** The three available moves, and
why two are worse than deviating:

- **Write one of the competing classes (3 or 11).** Fabricates a verdict the evidence does not
  support, and §11.2 forbids collapsing a park.
- **Write class 10.** §11.2: `parked` "is not a synonym for `indeterminate` and must never be
  collapsed into one."
- **Omit the row.** Worst of the three. A parked row *voids the tally for its column* (§11.2). An
  omitted row voids nothing — the instrument would tally nine rows and report a number that should
  not exist. Silent loss of a publication-blocking state.

**Emitted as `class: null`, `disposition: "parked"`.** This deviates from the stated enum and type in
exactly two places, and it deviates *loudly*: any tally accepting only `"classified"` will fail on
this row rather than skip it, which is the correct behaviour for a row that must block the tally.
Flagged for ruling rather than resolved unilaterally, per §10.5.

### Parked row — resolving observation (§11.2)

| feature_idx | competing classes | buckets | observation that settles it |
|---|---|---|---|
| 12403 | 3 code vs 11 topical domain (filesystems/IT) | surface-form vs semantic | **SAE-encode a probe set holding the path nouns fixed and varying the syntactic frame:** *"a folder of paperwork on the desk"*, *"put the file in the cabinet"* against *"$HOME/folder"*, *"mkdir /srv/file"*. Firing requires co-occurring shell/config syntax → class 3. `folder`/`file` fire in office prose with no code → class 11. The marker cannot settle it: the profile holds both `$`/`_`/`HOME` and bare `folder`/`file`, and one record (BMW forum, "photos folder on my laptop") already carries the noun with no code around it. |

### Marker-driven changes (§11.1 conservative-tally inputs)

Logged at the moment they occurred; not reconstructable afterwards.

| feature_idx | pre-marker | post-marker | direction |
|---|---|---|---|
| 11029 | 11 topical domain (semantic) | 2 lexical | **into the numerator** |
| 13746 | 10 indeterminate | 4 formatting | **into the numerator** |
| 13825 | 11 topical domain (semantic) | 2 lexical | **into the numerator** |
| 9012 | 10 indeterminate | 12 relational/positional (§13.5) | neither numerator, both before and after |
| 11763 | 10 indeterminate | 12 relational/positional (§13.3) | neither numerator, both before and after |
| 11149 | 9 discourse-register | 12 relational/positional | neither numerator, both before and after |
| 14719 | 9 discourse-register | 10 indeterminate (I-DIVERSE) | neither numerator, both before and after |
| 9105 | 10 indeterminate | 12 relational/positional | neither numerator, both before and after |
| 12403 | 11 topical domain | parked | — |
| 12449 | 11 topical domain — soil | unchanged | — |

**Under §11.1 the conservative tally resets `11029`, `13825`, `13746` to `indeterminate`.**
`11763` dropped off under §13.3 and `9012` under §13.5 — both land in class 12, denominator-only on
either side of the marker, so neither moved numerator-ward and neither needs a conservative reset.
Two of the remaining three (`11029`, `13825`) left the *semantic* bucket, not merely `indeterminate`:
both read as convincing topical domains from the window and dissolved when the marker showed one
token firing across unrelated senses.

---

## Draw 3 — calibration overlap extension, 14 rows, Gemma column

**Selection.** Supplied by the orchestrator: `819, 869, 1041, 1423, 2582, 2848, 7164, 7223, 7314,
7623, 8024, 11270, 13848, 15054`. These are the indices for which Rater 2 has never seen a recorded
class. Two candidates were excluded on Rater 2's objection and both exclusions were verified: `9115`
(pre-ruled by name in prereg §5, so it measures compliance, not agreement — 5094's problem exactly)
and `8667` (§7.1 conditional steer, and at 2 records its agreement datum would be near-worthless).

**An earlier eight-row set was refused.** `3169, 3358, 3648, 4090, 4572, 6515, 7055, 976` all sat in
the fourteen-row Gemma table Rater 2 read when §11.4 required writing to the shared ledger. All eight
were contaminated; the refusal is on record and the orchestrator recorded the selection as its error.

**Method.** Markers only, per the instruction — **no window-only pass was run**, so `pre_marker_class`
is `null` on every row and `marker_driven_numerator_move` is `false` throughout. That is not a claim
that the marker changed nothing; it is that no pre-marker class ever existed to change. These rows
therefore contribute nothing to the §11.1 conservative tally, which is correct: they never enter a
tally at all (§16.2).

Evidence: `scripts/legacy/gemma_max_activating_tokens.json` plus the ≥50%-of-max activation profile
from the raw per-feature provenance — the same instrument, per-token activations, which §11.1 makes
primary. Seam handling per the file's own rule: truncation only on a literal `<bos>` strictly inside
±10. Checksum — marker-file `argmax_value` first-16 against fulltext `maxValue` first-16 —
**14 of 14 match.** `distinct_sources` was computed by text clustering as a counts-only script; the
passages were never displayed, so the blind holds.

| feature_idx | column | class | conf | reason_code | distinct_sources | n_firings | marker_token | deciding evidence | disposition |
|---|---|---|---|---|---|---|---|---|---|
| 819 | gemma | 10 indeterminate | med | **I-DIVERSE** | 16 | 16 of 20 | ` ` ×5, `-` ×3, `1` ×2, `,`, `’`, ` order`, ` CAR`, `uen`, ` same` | Academic/technical prose throughout, but the trigger does not cohere: 7 of 16 are numeric-adjacent (a space before a numeral, a digit inside a year or DOI), the other 9 are hyphens in compounds, an apostrophe, and content words. The ≥50% profile splits ~evenly, 18 numeric-adjacent against 20 not, so class 1 is unsupported | classified |
| **869** | gemma | **2 lexical** *vs* **12 relational/positional** | — | — | 16 | 16 of 20 | ` And` ×6, `And` ×5, `,` ×5 | "cities of Brazil.  [And], as you'll see" / "role and[,] further, that" — fires on capitalised *And* and on the comma of the *And,* collocation | **parked** |
| 1041 | gemma | 12 relational/positional — coordinator joining two noun phrases | high | — | 16 | 16 of 20 | ` and` ×16 | "The male[ and] female become entwined" / "iPhone, BlackBerry[ and] Windows Mobile". Prong 1(b) verified: ` and` occurs **111 times** across the 16 records, is the argmax **16** times, and **89** occurrences sit below half-max — it fires on roughly one *and* in seven, so token identity cannot be what selects them | classified |
| 1423 | gemma | 3 code — identifier interior | high | — | 16 | 16 of 20 | `scape`, `fl`, `black`, `elite`, `action`, `ross`, `center`, `char`, `mich`, `ash`, `ave`, `uv`, `the` ×2, ` #`, ` phoenix` | Every marker is a sub-word **inside a URL, email address or handle**: "members@[the]ginguide.com", "www.wild[scape]images.biz", "social[action]@uvablsa.org", "senior[center].us". The ≥50% profile is the constituent pieces of those strings plus their `@` and `.` separators | classified |
| 2582 | gemma | 10 indeterminate | med | **I-DIVERSE** | 16 | 16 of 20 | ` felt`, ` our`, ` connect`, ` relationship`, ` moment`, ` try`, ` to`, ` But`, ` for`, ` all`, ` the` | Passages read as a coherent field (interpersonal connection, mindfulness), **but the trigger refuses it**: 377 tokens sit at ≥50% of record max, ~24 per record, led by ` to`, ` you`, `.`, ` of`, ` is`. ` the` occurs 147 times with 140 below half-max and 1 argmax. Weak-and-diffuse at this depth | classified |
| 2848 | gemma | 10 indeterminate | med | **I-DIVERSE** | 15 | 16 of 20 | `by`, `’`, ` and` ×3, `,`, `.` ×2, ` of` ×2, ` at`, ` are`, ` delete`, `6`, `\n\n`, ` that` | Density 9.5e-05. No thread: format strings, email-list enumerations, ASP.NET prose, real-estate boilerplate, a UI prompt. The largest sub-pattern is ` and` before the last item of an email list, 3 of 16. Recs 5 and 8 are one document, hence 15 sources | classified |
| 7164 | gemma | 7 abstract concepts — effect/consequence | high | — | 16 | 16 of 20 | ` impact` ×5, ` effects` ×2, ` effect`, ` affects`, ` implications`, ` ramifications`, ` benefits`, ` difference`, ` role`, ` joy`, ` Effect` | Eleven distinct lexemes, one meaning: "concerned about the[ impact] to their credit score", "the harmful[ ramifications] that blocked guttering can have", "the cultural[ effects] of migration". Paraphrase preserves firing and no field is nameable — basements, credit, pharma regulation, narcissism, retail, architecture, music therapy | classified |
| 7223 | gemma | 10 indeterminate | med | **I-DIVERSE** | 16 | 16 of 20 | `A`, `.` ×3, ` part`, `mation`, `\n\n`, `irs`, `ictions`, ` earth`, ` us`, ` options`, `condition`, ` lenses`, `OTA`, `ilites` | 152 tokens at ≥50% max, ~9.5 per record. A real sub-pattern exists — the marker completes a **misspelled** word in 5 of 16 (*informmation, upsatirs, predelictions, abilites, TOTA*) — but 11 of 16 fall outside it and the profile is dominated by sentence-final `.` | classified |
| 7314 | gemma | 12 relational/positional — auxiliary heading a *to*-infinitive obligation | high | — | 16 | 16 of 20 | ` have` ×13, ` got` ×2, ` had` | All 16 are the semi-modal obligation frame: "you don't[ have] to choose", "You've[ got] to stay at it", "he[ had] to do". Prong 1(b) verified: ` have` occurs 28 times, argmax 13, **13 below half-max**. ` to` occurs 110 times with **0** argmax, so the trigger is the auxiliary slot, not the particle | classified |
| 7623 | gemma | 12 relational/positional — copula of an existential *there*-clause | high | — | 16 | 16 of 20 | ` are` ×16 | **All 16 records are "There are"**: "There[ are] two types of airports", "There[ are] 658 names in this family tree". Prong 1(b) verified: ` are` occurs 38 times, argmax 16, **22 below half-max**; ` There`/`There` occur 19 times with **0** argmax, so the governor names the position and the copula carries the firing. Tightest profile in the draw — 16 high tokens, one per record | classified |
| 8024 | gemma | 11 topical domain — horror/Halloween | med | — | 16 | 16 of 20 | ` spooky`, ` Halloween` ×2, ` haunted`, `erie`, ` legendary`, ` annual`, `ls`, ` of` ×3, ` in`, ` lately`, `'`, ` `, `9` | All 16 records are horror or Halloween content — "a knack for[ spooky] and abnormal things", "[ haunted] by the demon of self-criticism", "disposal[ of] the zombie hordes", "silence of the tomb. Still. Quiet. E[erie]". Confidence held at med: the ≥50% profile is diffuse at ~8 tokens per record and led by function words | classified |
| 11270 | gemma | 10 indeterminate | med | **I-DIVERSE** | 16 | 16 of 20 | ` power` ×4, ` Powers`, ` knowledge`, ` start`, `outs`, ` build`, ` fees`, ` discretion`, ` businesses`, `ING`, ` happen`, ` done`, ` limitations` | Density **1e-06**, the sparsest feature in the pool, and very sharply tuned — 18 high tokens, ~1.1 per record — but tuned to fifteen different things. Mathematical exponentiation covers 5 of 16 ("2 to the[ power] of 3", "the[ Powers] of Two"); nothing links the remainder | classified |
| 13848 | gemma | 10 indeterminate | med | **I-DIVERSE** | 16 | 16 of 20 | ` is`, `2` ×2, ` a`, `.`, ` and` ×2, ` cryogenic`, ` element`, ` Failing`, ` of`, ` the` ×2, ` (`, ` for`, ` inkjet` | Passages are fairly uniform electronics and optics, but the marker is a function word in 10 of 16 and the profile is the most diffuse in the draw at 266 high tokens, ~16.6 per record. §11.1 binds: the passage says hardware, the marker says nothing | classified |
| 15054 | gemma | 11 topical domain — cookery | med-high | — | 16 | 16 of 20 | ` recipe` ×3, ` Recipes`, `ins`, `\n\n` ×4, `.` ×2, ` This`, ` this`, ` favorite`, `’`, `Want` | All 16 records are recipe text. Domain vocabulary sits at the marker in 5 of 16 and in the profile (` recipes` 5, ` recipe` 4, ` dough` 3, ` salad` 2); the four `\n\n` markers fall at recipe-section boundaries — "lasts 3-4 weeks in the refrigerator.[\n\n]Mix the salt, cumin, paprika" | classified |

### Draw-3 parked row — resolving observation (§11.2)

| feature_idx | competing classes | buckets | observation that settles it |
|---|---|---|---|
| 869 | 2 lexical (*And* / the *And,* collocation) vs 12 relational/positional (sentence-initial coordinator) | surface-form vs denominator-only | **The two readings are confounded in this corpus and the marker cannot separate them.** Capitalised ` And` occurs 9 times and *every one fires* (0 below half-max); `And` occurs 5 times, all argmax. Lowercase ` and` occurs 63 times with **0** argmax and 60 below half-max. So a `{And}` lexicon reproduces the firing set exactly — but every capitalised *And* in these 16 records is also sentence-initial, so position predicts identically. §13.3 prong 1(b) fails on its third condition (the same token never occurs without firing), which routes away from class 12; that routing is an artifact of the confound, not evidence against position. **Resolution: SAE-encode probes holding the token constant and breaking the position** — title case and proper names, *"Rock And Roll"*, *"Smith And Sons Ltd"*, *"Law And Order"*. Fires there → class 2. Silent there → class 12. |

### Draw-3 seam audit (§11.7)

Five records across the fourteen carry a literal `<bos>` strictly inside ±10 — `819` rec 0, `1041`
rec 7, `7164` rec 11, `7623` rec 7, `8024` rec 9. In every one the truncation cut the **far** side and
the trigger environment is intra-document: *"In[ order] to account"*, *"The cork[ and] latex"*,
*"the cultural[ effects] of migration"*, *"There[ are]"*, *"this year's[ annual] Pumpkin Pal"*. None
is load-bearing — `1041` and `7623` rest on occurrence statistics across all 16 records that no single
record can swing, and `819` is indeterminate on the whole set. **No call in this draw depends on
spliced context.**

### Draw-3 note — two conjunction features, opposite answers

`869` and `1041` both fire on a coordinating conjunction, and prong 1(b) separates them cleanly,
which is the test doing exactly what it was written for. `1041` fires on **one ` and` in seven**
(111 occurrences, 16 argmax, 89 below half-max) — token identity cannot be selecting them, so the
position is. `869` fires on **every capitalised *And* there is** (14 of 14) — token identity is
sufficient. The difference is measured, not asserted; it is also why `869` parks rather than
following `1041` to class 12.

---

### §11.7 seam audit — does any deciding evidence sit within ±10 tokens of a seam?

Source: `scripts/legacy/gemma_max_activating_tokens.json` (regenerated; sha256
`0bdebba3055989d688d5b16d1ca8c4f8bcc0112053037847dc3bbd4c7c5a4982`). Its own `_meta` now
distinguishes three signals: `is_multi_document_record` (>1 literal `<bos>` anywhere in the record —
reported floor), `bos_in_context_window` (a literal `<bos>` **strictly inside ±10** — the only
signal used for truncation), and `unmarked_fusion_heuristic` (**~97% false positives, diagnostic
only, never used for truncation**).

| feature | multi-doc /16 | **`<bos>` inside ±10 /16** | fusion heuristic /16 | deciding evidence seam-exposed? |
|---|---|---|---|---|
| 9012 | 5 | **0** | 0 | no |
| 9105 | 9 | **0** | 2 | no |
| 11029 | 4 | **1** (rec 0) | 1 | rec 0 is quoted — **not load-bearing, see below** |
| 11149 | 10 | **0** | 1 | no |
| 11763 | 3 | **1** (rec 14) | 0 | no — quotes are recs 1 and 5 |
| **12403** | 4 | **0** | 3 | **no — zero exposure, see below** |
| 12449 | 9 | **0** | 1 | no |
| 13746 | 8 | **1** (rec 5) | 0 | no — quote is rec 1 |
| 13825 | 9 | **0** | 2 | no — seam precedes the marker, see below |
| 14719 | 6 | **0** | 2 | no |

**Only three records across all ten rows carry a real seam inside ±10, and only one of those is a
record I quoted.**

- **11029 rec 0** — `<bos>` falls immediately *after* the marker: `AVS has built Chem|cial` ‖ `<bos>`.
  The marker and its left context are intra-document, so the trigger environment is uncontaminated.
  Not load-bearing regardless: the class rests on 16/16 marker identity plus two independent
  counterexamples (rec 4 music-track *"Chemical Process"*, rec 14 *"chemical peels"*), and the
  misspelling evidence has a clean second instance in **rec 1**, which carries no seam flag of any
  kind. **Class 2 stands.**
- **11763 rec 14** and **13746 rec 5** — both intra-document at the marker (*"the show gardens are
  the highlight"*, *"a lightweight travel stroller, and picked up"*); neither is a deciding-quote
  record. 11763's prong 1(b) rests on the 130/15/114 occurrence statistics across all 16, which no
  single record can swing. **Both classes stand.**
- **13825 rec 14** — carries a *genuine* unmarked seam (`…and the stone` ‖ `Booking a Job:` —
  jewellery text into a removals firm), one of the minority of true positives on that signal. **The
  seam precedes the marker**, so `Booking a Job` is intra-document and the quote is sound. The
  second counterexample (rec 12, cricket *"the job is now to win"*) carries no seam flag. **Class 2
  stands.**

**12403, the parked row — zero seam exposure.** No `<bos>` inside ±10 on any of its 16 records. All
three records carrying its competing readings — rec 0 (`chmod -R g+w[ $]REMOTEPATH`), rec 1
(`failed to[ mkdir] "/srv/mediawiki/`), rec 14 (`photos[ folder] on my laptop`) — are clean on
**all three** signals, `is_multi_document_record` included. Its three fusion-heuristic hits are
recs 4, 9 and 12, none of which is a deciding-evidence record, and all three are visibly false
positives on inspection: `TEXMFHOME`/`MiKTeX`, `MediaServer`, `HoverIntent` — CamelCase product
names, not document boundaries. **Parking 12403 does not park a contaminated reading, and resolving
it later will resolve clean evidence.**

### Correction to Rater 2's own §11.7 measurement

The "2 to 11 of 16" range Rater 2 reported, which is quoted in §11.7, was computed with the
lowercase→uppercase concatenation regex — **the signal the marker file now documents as ~97% false
positive.** That range measured tokenizer splits, not seams, and should not be cited as a seam rate.
The qualitative finding it supported is unaffected and is now better evidenced: multi-document
records run **355 of 782** file-wide, so packed-stream splicing is real and common. The
truncation-relevant rate is far smaller — **19 of 782** records carry a `<bos>` inside ±10.

Consequently the contexts Rater 2 read during adjudication were truncated on the over-aggressive
signal. The direction of that error is toward seeing *less* context, not toward manufacturing a
pattern, and every class in this draw was decided on the marker token plus the ≥50%-of-max
activation profile — both seam-agnostic. **No call in this draw moves.**

### Density (`frac_nonzero`, raw provenance)

`9012` 0.001734 · `9105` 0.003863 · `11029` 0.000695 · `11149` 0.012011 · `11763` 0.001669 ·
`12403` 0.000905 · `12449` 0.004159 · `13746` 0.004386 · `13825` 0.000911 · `14719` 0.005487

---

## Artifact produced this pass — Qwen marker parity (§11.1)

`scripts/legacy/qwen_max_activating_tokens.json`, sha256
`60e920aa3485fb1981e0d7fd603a1893e2be74dd90e0b557d37dca004acd69b0`.
Builder: `scripts/legacy/build_qwen_max_activating_tokens.py`.

40 features, **972 of 972 records emitted, 0 skipped**. Full field parity with the Gemma marker
file. Tokenizer `Qwen/Qwen2.5-14B-Instruct` (`Qwen2Tokenizer`, vocab 151643).

Verification per record, both passing on all 972: the token at
`activating_char_offset_in_window` equals `activating_token`; and the nine tokens ending there
rejoin to `original_excerpt` byte for byte. Records failing either check would have been skipped,
never guessed.

**§11.1's precondition is now satisfied — both columns have marker access.**
