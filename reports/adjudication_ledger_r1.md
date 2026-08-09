# ADJUDICATION LEDGER — RATER 1 PARTITION

Binding under prereg v1.8 §12.1. **Rater 1 (Lab assistant B) writes this file only.**
Merge is performed by the orchestrator. Rater 1 does not read `adjudication_ledger.md` or any
`_r2` file — that partition contains another rater's calls on rows where Rater 1 is the blind
second rater.

Supersedes Rater 1's rows in `adjudication_ledger.md` (commit `63b0c00`, sha
`0a18887d991f0e1d6c2ccf8cd3c40771bf1c83a2bb32a2be3bf9bb79a984b860`).

---

## 1. PRE-MARKER FREEZE — §11.1

**Frozen before any marker data was opened. Verbatim. This block is immutable.**

All 19 rows classified without marker access, with `pre_marker_class` and `pre_marker_bucket` as
decided at the time. Under §11.1 these are the inputs to the **conservative tally**: any row whose
class later changes on marker access *in the direction of the numerator* is reset to
`indeterminate` in that tally.

| feature_idx | column | pre_marker_class | pre_marker_bucket |
|---|---|---|---|
| 14622 | qwen | 11 topical domain — film/cinema | semantic |
| 126804 | qwen | 2 lexical/n-gram — *revise* | surface-form |
| 107244 | qwen | 10 indeterminate | denominator only |
| 71905 | qwen | 10 indeterminate | denominator only |
| 70945 | qwen | 10 indeterminate | denominator only |
| 140672 | qwen | 10 indeterminate | denominator only |
| 114256 | qwen | 10 indeterminate | denominator only |
| 3070 | gemma | 9 discourse-register | denominator only |
| 3169 | gemma | 11 topical domain — electoral politics | semantic |
| 3349 | gemma | 3 code | surface-form |
| 3358 | gemma | 9 discourse-register | denominator only |
| 3648 | gemma | 11 topical domain — document typesetting | semantic |
| 4090 | gemma | 10 indeterminate | denominator only |
| 4572 | gemma | 11 topical domain — software & IT | semantic |
| 5094 | gemma | 2 lexical/POS/n-gram | surface-form |
| 6515 | gemma | 10 indeterminate | denominator only |
| 7055 | gemma | 11 topical domain — programming & mathematics | semantic |
| 212 | gemma | 9 discourse-register | denominator only |
| 976 | gemma | 7 abstract concepts — rule-of-thumb | semantic |

### Also frozen — the two overruled rows, Rater 1's original calls

Recorded because the overrules are themselves marker-driven and belong in the conservative tally's
audit trail.

| feature_idx | column | pre_marker_class (Rater 1) | pre_marker_bucket (Rater 1) | current disposition |
|---|---|---|---|---|
| 3039 | gemma | 10 indeterminate | denominator only | overruled → class 4 formatting, **surface-form** (§11.5) |
| 5231 | gemma | 2 lexical — negation particles | surface-form | overruled → §11.5 `I-SILENT` → **class 12** (§12.3) |

**Direction note.** Of the two marker-driven overrules, 3039 moved *into* the numerator and 5231
moved *out* of it. Both are logged at the moment they occurred, per §11.1's requirement that a
row's pre-marker class cannot be reconstructed afterwards.

### Six confidences do not exist

Rows 3039, 3070, 3349, 3358, 5094, 5231 were decided before confidence became part of per-row
output. They are recorded absent, not reconstructed — a confidence recalled now would be
contaminated by everything learned since.

---

## 2. §12.3 APPLIED — 5231 → CLASS 12

**Class 12, relational/positional trigger, denominator only.**

Test satisfied: the marker token differs across all 16 records (*sad, industry, secretive, town,
highest, immune, -inate, individuals*) — ≥12 of 16 required — and the invariant position is
describable without naming any token: *the constituent closing a negation scope*.

This supersedes the `I-SILENT` disposition. `I-SILENT` recorded a defect in the scheme; §12.3 fixes
the defect, so the code no longer applies. The **bucket is unchanged** — §3 already sent it to
neither numerator, because a positional trigger survives both §3 tests and step 3 routes both-yes
away from surface-form. Only the class name was missing.

---

## 3. RATER 1 ROWS

Schema: `feature_idx | column | class | bucket | conf | reason_code | distinct_sources | n_firings/density | marker_token | pre_marker_class | deciding_quote | disposition`

### QWEN — ARM_PRIMARY (n=40)

Evidence: `example_context_centred1164.json` `centred_1164`, sha
`72e73f263176163fa44e4b6b9c7b6a925d4c1f0f03bb0f9667ab5fc971e5b21c`. `full_chunk` is the sensitivity
arm. **No Qwen marker access at time of writing** — all Qwen classes below are pre-marker.

| feature_idx | class | bucket | conf | reason_code | distinct_sources | n_firings | marker_token | deciding_quote | disposition |
|---|---|---|---|---|---|---|---|---|---|
| 14622 | 11 topical domain — film/cinema | semantic | low | — | 7 | 131 | — | "Congratulations to Jennifer Lawrence who has won Best Performance by an Actress in a Motion Picture (Musical or Comedy) for 'Silver Linings Playbook'!" | classified |
| 126804 | 2 lexical/n-gram — *revise* | surface-form | high | — | 13 | 736 | — | "\*REVISED EDITION FEATURING NEW RECIPES & LAY-FLAT BINDING\*" / "the previous week's revised figure of 367,000" / "REVISED DECLARATION OF HANA WHITFIELD" / "trans. Charles Cotton, revised by William Carew Hazlett" | classified |
| 107244 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 4013 | — | papal memoir vs NC job listings vs aikido vs guitar tablature vs plasma-cutter marketing vs K-pop fandom | classified |
| 71905 | 10 indeterminate | denominator only | med | I-DIVERSE | 14 | 53 | — | "Heroic Halls of Reflection is a place where this truly shines — mobs come in waves" vs "ANDREA DAVIS IS NOT NOW NOR HAS SHE EVER BEEN LICENSED AS A LICENSED PRACTICAL NURSING IN THE STATE OF ALABAMA" | classified |
| 70945 | 10 indeterminate | denominator only | med | **I-THIN** | **2** | 841 | — | "The Queen last year chose to wear blue on 29 per cent of her public engagements" (12/16) vs "A Japanese legend claims that Jesus escaped Jerusalem and made his way to Aomori in Japan" (4/16) | classified |
| 140672 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 125 | — | "Why is it that when light travels from a more dense to a less dense medium, its speed is higher?" vs "Leopoldstadt gained the nickname Mazzesinsel ('Matzoh Island')" — max act 4.31 | classified |
| 114256 | 10 indeterminate | denominator only | med | I-DIVERSE | 15 | 32 | — | "Warm 1 tbs of the oil in a large, deep, heavy frypan over medium heat" vs "you must configure your firewall to accept cookies from the \*.aip.org domain" — max act 3.92 | classified |
| **14081** | **1 numeric/quantitative** *vs* **11 topical domain** | **surface-form vs semantic** | — | — | 6 (effectively 5) | 442 | — | "Advanced tickets are $10 for adults and $8 for children and seniors under 12" / "C$6.80 per day adult, C$5.80 senior, C$3.40 youth 6–16" | **parked** |
| **33008** | **2 lexical/n-gram** *vs* **7 abstract concepts** | **surface-form vs semantic** | — | — | 15 | 5945 | — | "The two are not mutually exclusive" / "the two modes are effectively two sides of the same combat coin" / "those two goals are frequently at odds" | **parked** |

**Qwen: 7 classified, 2 parked, 31 outstanding. Tally VOID under §11.2 while parked rows stand.**

### GEMMA — seeded uniform draw, seed 42, n=40

⚠ Rows 3070–3648 carry a class and little else. Their density, distinct-source counts and deciding
quotes are not recoverable from surviving reports. Marked `—`, not reconstructed. **Retrofit
priority: these rows first**, because they include two of the surface-form numerator's members
(3349, 5094) and cannot currently be audited, only trusted.

| feature_idx | class | bucket | conf | reason_code | distinct_sources | density | marker_token | deciding_quote | disposition |
|---|---|---|---|---|---|---|---|---|---|
| 3039 | 4 formatting | surface-form | — | — | — | — | `:` ×4, `\n\n` ×2, `(`, `<`, `"` | delimiters fire; repetition is why they are frequent (§11.5) | overruled from R1's 10 |
| 3070 | 9 discourse-register | denominator only | — | — | — | — | — | first-person interview register | classified |
| 3169 | 11 topical domain — electoral politics | semantic | — | — | — | — | — | — | classified |
| 3349 | 3 code | surface-form | — | — | — | — | — | — | classified |
| 3358 | 9 discourse-register | denominator only | — | — | — | — | — | promotional register spanning unrelated subjects | classified |
| 3648 | 11 topical domain — document typesetting | semantic | — | — | — | — | — | — | classified |
| 4090 | 10 indeterminate | denominator only | med | I-DIVERSE | — | 0.003116 | — | ".NET stack traces, accounting citation lists, Russian torrent listings, hadith, athletics biography, ToS boilerplate, rugby commentary" | classified |
| 4572 | 11 topical domain — software & IT | semantic | med-high | — | — | 0.002114 | — | "On the Site Settings page, under Users and Permissions, click People and Groups" / "Q6.5.5 – Why can't I launch a job on multiple nodes on Euramoo?" | classified |
| 5094 | 2 lexical/POS/n-gram | surface-form | — | — | — | — | — | pre-ruled by §5; cannot measure agreement (§11.6) | classified (pre-ruled) |
| 5231 | **12 relational/positional** | denominator only | — | — | — | — | varies across 16/16 (*sad, industry, secretive, town, highest, immune, -inate, individuals*) | invariant is the constituent closing a negation scope | overruled from R1's 2 |
| 6515 | 10 indeterminate | denominator only | med | I-DIVERSE | — | 0.003508 | — | four-digit years in ~10 of 16 but absent from six; historical-narrative field covers only ~5 | classified |
| 7055 | 11 topical domain — programming & mathematics | semantic | med | — | — | 0.000609 | — | "increment statement is --k, meaning k = k - 1… the condition will become false and we will exit the loop" / "compress/gzip Package gzip implements reading and writing of gzip format compressed files, as specified in RFC 1952" | classified |
| 212 | 9 discourse-register | denominator only | med | — | — | — | — | "I do not agree with all of his views" / "I don't like either party, I don't like the Clintons, I don't like the track record" / "Don't panic. If everything goes to hell you can roll your own dice" | classified |
| 976 | 7 abstract concepts — rule-of-thumb | semantic | med-high | — | — | — | — | "Dr. Bartlett's rule of 70 is the same as the more common 'rule of 72'" / "As a rough rule, two months should be a safe amount of time" / "A rule of thumb is, getting a fire burning as the highest priority" | classified |

**212 live alternative on record:** class 2 lexical — negation. Present in 16 of 16 records,
including one blog post that breaks the conversational-register reading while retaining dense
negation. **Numerator-bound if the marker sits on the negator.** Resolvable now that Gemma marker
data exists; queued with the retrofit.

**Gemma relay-parked (9):** `819, 869, 1041, 1423, 2582, 2848, 7164, 7314, 8024`. Text uncertified
through the summarizer relay; maxValue sequences monotonic and reproducible. Resolved by the
byte-exact Neuronpedia JSON.

**Gemma: 12 classified, 2 overruled, 9 relay-parked, 17 outstanding.**

---

## 4. COUNT DISCREPANCY — unresolved

Rater 1's running count reported **16** Gemma rows classified; **14 are nameable** and appear above.
The gap arises between a pre-compaction summary listing eight rows before 4090 and a post-compaction
report implying ten. Under §11.4 the two unnameable calls **did not happen**; the Gemma classified
count is 14. They are not reinstated by assertion.

---

## 5. DIRECTIONAL ARTIFACTS AFFECTING THESE ROWS

1. **Qwen opening-line trap (§4.6)** — `full_chunk` starts every record at document char 0.
   `centred_1164` reduces but does not remove it: **38.37% of rows still clip at chunk start.**
   Opening-line evidence refused throughout.
2. **Gemma packed-stream splice (§11.7)** — measured at **46.5% of records, no feature clean, up to
   14/16 on one**, and to be treated as a **floor** since seams without a `<bos>` marker exist.
   ±10-token context is truncated **at** the seam, never read through it.
3. **Context-length residual** — Qwen `centred_1164` achieves median 997 / mean 936 against Gemma's
   byte-exact median 1164 / mean 1148: **−14.3% median, −18.4% mean, against Qwen.** The prior
   `full_chunk` arm ran **+75%**, against Gemma. The `1269–2847` Gemma interval and everything
   binned against it are **void**.
4. **Marker asymmetry (§11.1) — now resolved.** Qwen markers were available all along
   (`activating_token`, `token_position`, `text_marked` in `example_context_centred1164.json`) and
   were **deliberately left unused** by Rater 1 to preserve symmetry while Gemma lacked them. Gemma
   marker data now exists (`gemma_max_activating_tokens.json`), so **both columns have marker
   access and §11.1 trigger-primacy is unblocked.** The 19 frozen rows above were nevertheless
   decided without markers and remain pre-marker; they feed the conservative tally unchanged.
5. **Parking is not neutral (§11.2)** — the gate selects for strong patterns, so the parked set is
   enriched for classifiable rows and the residue for `indeterminate`.

---

## 6. CALIBRATION OVERLAP — TEN GEMMA ROWS, MARKER-INFORMED

Evidence: `scripts/legacy/gemma_max_activating_tokens.json`. 782/782 records emitted, 0 length
mismatches, 0 argmax-vs-`maxValueTokenIndex` disagreements. Context radius ±10.

> ⚠ **EVIDENCE FILE WAS REPLACED MID-ADJUDICATION.** These ten rows were adjudicated against
> **v1**, sha `d4f505beb10baf1e1a58acd179cf7c6f3770aa94f51b75efc79da9d4cbdb22a4` (recoverable as the
> tree state at commit `63b0c00`). The working tree now holds **v2**, sha
> `0bdebba3055989d688d5b16d1ca8c4f8bcc0112053037847dc3bbd4c7c5a4982`, landed in `dfbfbe0`.
>
> **Verified: no call is affected.** `argmax_token` and `argmax_value` are **byte-identical across
> all 782 records** in both versions. Only ±10 context windows changed — 12 of 160 records in these
> ten, 62 of 782 overall — because the truncation rule was revised. §11.1 classifies on the trigger,
> and the trigger did not move.
>
> **v1 over-truncated.** It truncated on an unmarked-fusion heuristic that v2's own metadata reports
> as **~97% false positives** (tokenizer splits such as `B2B`, `WinRAR`, `CompTIA`). It cut real
> words mid-token: `ParkMobile`→`Mobile`, `SoundMagic`→`Sound`, `HoverIntent`→`Intent`,
> `PowerSeries`→`Series`. v2 truncates **only at a literal `<bos>` inside the window** and keeps the
> heuristic as a diagnostic flag never used for truncation.
>
> **Directional: against the numerator.** Over-truncation thins evidence and thin evidence deflates
> surface-form — the project's recurring artifact. Concretely, this row's own record set: 9105 was
> recorded as having *use* in 15 of 16, with rank 10 the exception. It was not an exception —
> v1 had truncated `PowerSeries` into `Series`, hiding *"**Using** the AC2000 DSC Power**Series**
> **interface**"*. Under v2 the pattern is **16/16**. The false seam destroyed the evidence that
> confirmed the reading.
>
> **Seam figures below are v2.** The earlier per-row seam counts derived from the discredited
> heuristic and are withdrawn. `bos_in_window` is the truncating signal; `multi_doc` is the
> reported-floor packing rate (355/782 = 45.4% file-wide).

Adjudicated **under §11.1 trigger-primacy**. Blind: Rater 1 has not seen Rater 2's calls on these
rows. Depth 16, array order.

| feature_idx | class | bucket | conf | reason_code | distinct_sources | bos_in_window / multi_doc | marker_token | deciding_quote |
|---|---|---|---|---|---|---|---|---|
| 9012 | 4 formatting | **surface-form** | high | — | 16 | 0 / 5 | `,` ×13, `—`/`–` ×3 — **delimiter punctuation 16/16** | " …residents of Quebec**,** including temporary and undocumented" / "…user data**—**through apps, web browsing" / "…provided support **–** very likely including financial support" |
| 9105 | 10 indeterminate | denominator only | med | **I-SILENT** | 16 | 0 / 9 | 11 distinct: *form, links, information, System, website, bar, it, app, interface, used, materials* | Marker is the **complement of *use*** in 14/16 and *use[d]* itself in 2/16: "Please **use** this **form**" / "By **using** the Sterling Service Dogs **website**" / "Taurus can be **used** to start every room" |
| 11029 | 2 lexical/n-gram — *chemical* | **surface-form** | high | — | 16 | 1 / 4 | *chemical / Chemical / chemicals / cial* — **16/16** | "protecting **Chemcial** Vapor Deposition (CVD) furnace hot zones" / "if you ask **chemical** engineer Yunfeng Lu" / "a primary feedstock for the **chemical** industry" / "including **chemical** peels, microdermabrasion" |
| 11149 | 9 discourse-register — promotional/service copy | denominator only | med | — | 16 | 0 / 10 | **16/16 distinct**: *SEO, gout, ia, window, messages, loan, theatre, shooting, parking, attorney, homes, PC, limousine, railroads, way, orer* | Marker sits on the advertised keyword across unrelated industries: "enhancing local **SEO**" / "a very effective **gout** treatment" / "an immigration **attorney** on your side" / "wood b**orer** fumigation" |
| 11763 | 9 discourse-register — post-copular superlative assertion | denominator only | med | — | 16 | 1 / 3 | `the` ×15, `a` ×1 | Determiner opening a predicate nominative after a copula, 16/16: "slips and trips continue to be **the** most common cause" / "tiredness is **the** number one complaint" / "Communication is **the** answer" / "at $10,000 is **the** culprit" |
| 12403 | 11 topical domain — software/filesystem configuration | semantic | med | — | 16 | 0 / 4 | 12 distinct; 8/16 path-lexical (`$` ×3, *mkdir, dir, directory, folder* ×2) | "chmod -R g+w **$**REMOTEPATH" / "failed to **mkdir** \"/srv/mediawiki/php-master/images" / "the \"src/assets/stylesheets\" **folder** of your project directory" |
| 12449 | 11 topical domain — soil/earth | semantic | high | — | 16 | 0 / 9 | *soil, Soil, clay, Clay, dirt, bed, brown, grading, otechnical, rained* — ~10/16 soil-lexical | "nutritious bio-diverse **soil**, adequate water" / "a Professor of **Soil** Physics" / "**Clay** brick machine is used to produce clay brick" / "the completion of a Ge**otechnical** Study" |
| 13746 | 10 indeterminate | denominator only | med | **I-AMBIGUOUS** | 16 | 1 / 8 | 9 distinct; punctuation 11/16 (`,` ×5, `.` ×3, `\n\n`, `(` ×2) | Class 4 (heterogeneous punctuation marker) and class 9 (consumer product-advice register) both survive the marker, different buckets: "picked up the GB Pockit**,**" / "These may be just the right touch**.**" / "**Choose** a head with more shower settings" |
| 13825 | 2 lexical/n-gram — *job* | **surface-form** | high | — | 16 | 0 / 9 | *job / Job / JOB / Jobholding* — **16/16** | "**JOB** HUNTING. I'm currently applying for jobs" / "**Job**holding rates declined dramatically for young men" / "according to the **job** site Indeed" / "the **job** is now to win the tournament" |
| 14719 | 11 topical domain — mechanical/physical components | semantic | med | — | 16 | 0 / 6 | 14 distinct, mostly function words (*their, have, is, with, are, to, the, has*) | "valves are working themselves against **their** seats" / "The sensor element **is** a ceramic cylinder plated with porous platinum" / "the chain and SRAM cassette **are** a bit louder" / "the **blade** is removable" |

### §12.3 near-misses recorded, not resolved

| feature_idx | class 12 prong that failed | consequence |
|---|---|---|
| 9105 | *"describable without naming any token"* — the position is **the complement of *use***, which cannot be stated without naming *use*. Prong 1 also marginal (11 distinct < 12). | Routed to `I-SILENT`. |
| 11763 | *"marker differs across ≥12 of 16"* — the marker is `the` in **15 of 16**. The trigger is positional (Det of a predicate nominative) but the position is **lexically constrained**, so it is occupied by a constant token. | Routed to class 9. §2's own lexicon test independently rejects class 2 — a `{the}` lexicon fires on nearly every document, not these 16. |
| 13746 | Prong 1 — 9 distinct markers. | Routed to `I-AMBIGUOUS`. |
| 14719 | Prong 2 — prong 1 passes (14 distinct), but no single position covers markers spanning copulas, prepositions, determiners and content nouns. | Routed to class 11. |

**Neither prong was stretched, and no class was invented.** Recorded for the orchestrator.

---

## 7. QWEN MARKER RETROFIT — §11.1 SYMMETRY CLOSED

Evidence: `scripts/legacy/qwen_max_activating_tokens.json`, sha
`60e920aa3485fb1981e0d7fd603a1893e2be74dd90e0b557d37dca004acd69b0`. 972/972 emitted, 0 length
mismatches, 0 index mismatches, two-way reconstruction gate. Built from `centred_1164`
(`72e73f26…`), the same artifact the pre-marker calls used. **No splice seams** (one `doc_id` per
record). **100% document-initial**, so §4.6's opening-line rule applies to every row;
`position_fraction_in_chunk` used throughout, never `position_fraction`.

Pre-marker classes were frozen in §1 of this file at commit `5cf9900`, before any marker file for
either column was opened.

| idx | pre_marker_class | pre_marker_bucket | post-marker class | bucket | conf | marker evidence | reset? |
|---|---|---|---|---|---|---|---|
| 14622 | 11 film/cinema | semantic | **5 named entities — titles of works** | semantic | high | terminal token of a title, **16/16**: `Silver Lin**ings**`, `The Desc**endants**` ×2, `Sky**fall**` ×4, `Lin**coln**` ×2, `Up In The **Air**`, `The Fault in Our **Stars**`, `Good Night, And Good **Luck**`, `Vicky **Cristina** Barcelona` ×2, `Michael **Clayton**`. cpos 0.04–0.74 | no — bucket unchanged |
| 126804 | 2 lexical — *revise* | surface-form | **2 confirmed** | surface-form | high | `REV**ISED**` ×2, ` revised` **×9**, `**ise**` ×2, `**vised**`, ` revision`, ` revise` — **16/16**. cpos 0.01–0.95. *(Corrected from ×8: Rater 1 transcription error, verified against the file; class unaffected.)* | n/a |

> ⚠ **QWEN MARKER FILE RE-CUT AND NOT AUDITABLE.** `qwen_max_activating_tokens.json` was re-cut from
> `60e920aa3485fb19…` to `b6bf9710a92a1bce37089f9ff69663dc951c7e97eab974428ca190a01ccdb3f6`. Unlike the
> Gemma file, **this one is untracked in git**, so the superseded version is unrecoverable and no
> byte-level diff is possible. Verification fell back to comparing recorded marker distributions:
> **14622, 14081 and 33008 match exactly**; 126804's single discrepancy resolved as a Rater 1
> transcription error. That is reasonable assurance, **not** the proof obtained for Gemma.
> **Recommendation: commit the marker files.** The Gemma re-cut was fully auditable because its file
> was tracked; this one is not, for no reason other than that nobody added it.
| 107244 | 10 indeterminate | denominator only | **5 named entities — titles/name-strings** | **semantic** | med | title-internal token, **12/16**: `Let Us **Be** on Our Way`, `Repelling an Attack **With** the Heart`, `Critical Choices that **Change** Lives`, `Don't **Believe** a Word`, `Right **Off** the Bat`, `The Phillie Phanatic **Goes** Hollywood`. cpos 0.07–0.95 | no — not numerator-ward |
| 71905 | 10 indeterminate | denominator only | **10 confirmed · I-DIVERSE** | denominator only | med | 15 distinct types/16; boilerplate reading covers 4/16; max act 8.88 | n/a |
| 70945 | 10 indeterminate | denominator only | **10 confirmed · I-THIN** | denominator only | med | support still **2 documents** (4239 ×12, 2916 ×4); markers vary but nothing is falsifiable at n=2 | n/a |
| 140672 | 10 indeterminate | denominator only | **10 confirmed · I-DIVERSE** | denominator only | med | 16 distinct types/16, 16 docs, max act 4.31 | n/a |
| 114256 | 10 indeterminate | denominator only | **10 confirmed · I-DIVERSE** | denominator only | med | 16 distinct types/16, 15 docs, max act 3.92 | n/a |
| **14081** | *parked* (1 vs 11) | *none* | **1 numeric/quantitative** | **surface-form** | high | `$` ×10, digits `5`/`8`/`4`/`4` ×4, ` for` ×2 — **14/16 numeral or currency**. Prong 1(a) fails on the pinned records count (6 non-modal < 12); prong 2 fails on no-governor | **see §7.1** |
| **33008** | *parked* (2 vs 7) | *none* | **7 abstract concepts — contrasted pair** | **semantic** | med | marker on the contrasted term, **12/16**: ` modes, systems, tribes, charts, frameworks, versions, goals, recipes`; ` two` only 4/16. Prong 1(a) passes, prong 2 fails on precision | **see §7.1** |

### 7.1 OPEN QUESTION — parked rows and the conservative floor

§11.1 resets rows *whose class changed on marker access toward the numerator*. A parked row never
had a class, so **14081 has nothing to reset from** and, read literally, enters the conservative
tally in the numerator unreset. If §11.2's premise holds — that parking is numerator-enriched by
construction — then a conservative tally that admits resolved parks unreset **is not a floor.**

Empirically, of the two parked rows one resolved to surface-form (14081) and one to semantic
(33008). n = 2 does not support the strong form of §11.2's concern. **Ruling required; not decided
by Rater 1.**

### 7.2 RATER 1 CORRECTION — Finding 1 was over-applied

107244 was classified `indeterminate` **because** Rater 1 discarded a titles reading as an
opening-line artifact (§4.6, Finding 1). Finding 1 was correct that the *window* evidence for titles
was manufactured by `full_chunk` beginning at character 0. It was over-generalised into "the titles
reading is non-evidence." The marker shows the reading was independently right: 12/16 markers are
title-internal at chunk positions 0.07–0.95, nowhere near the document opening.

**The rule stays; its scope narrows.** Opening-line *position* is non-evidence. A *content* pattern
that happens to be visible at an opening is not thereby disqualified — it requires independent
support, which the marker now supplies.

---

## 8. THE NINE RELAY-PARKED GEMMA ROWS — CLOSED FROM MARKERS

Parked because summarizer-relayed *text* was uncertified. Under §11.1 the trigger governs, and
`gemma_max_activating_tokens.json` carries every trigger byte-exact, so these adjudicate with **no
text relay in the path at all.** The blocker was the channel; the channel is bypassed.

Seam handling per ruling: truncate only on a literal `<bos>` strictly inside ±10 (19/782 = 2.4%);
never on the lower→Upper fusion signal (~97% false positive).

**§14.2 note:** these nine are the pre-registered test of §11.2's numerator-enrichment premise.
**The prediction was not consulted during adjudication and no rate is computed here.** Rows are
reported as decided; the test is the orchestrator's to run.

| idx | class | bucket | conf | reason | marker evidence |
|---|---|---|---|---|---|
| 819 | 11 topical — quantitative/technical academic | semantic | **med-low** | — | Markers structurally uninformative: `' '` ×5, `-` ×3, `1` ×2, `,`, `’` = 12/16 whitespace/punct/digit. Passages cohere (15/16 quantitative-technical: composites mechanics, graph isomorphism, ICASSP citations, yield curves, CARA investor, Luenberger observer, circuit analysis). **Class rests on passage, not trigger — flagged.** |
| 869 | **12 relational/positional** — sentence-initial coordination | denominator only | med | — | `And`/` And` ×11 sentence-initial, `,` ×5 immediately after a coordinating *and*: "and**,** eventually," · "**And** not just the most well-known festivals" · "**And** neither was he persecuted". §13.5: coordination → class 12. Recurs unfired in-record ("And how you present it… **And** thank you"). |
| 1041 | **12 relational/positional** — nominal coordination | denominator only | **high** | — | ` and` **16/16**, always joining two NPs: "The male **and** female" · "China **and** the EU" · "Joseph **and** Mary" · "Saturday **and** Sunday" · "iPhone, BlackBerry **and** Windows Mobile". Prong 1(b): recurs unfired in-record ("Fiance **and** his band get up on stage and sing"). |
| 1423 | 3 code/identifiers | **surface-form** | **high** | — | **16/16** substrings inside URLs, emails, hashtags, handles: `@**the**ginguide.com`, `wild**scape**images.biz`, `cheapn**fl**jerseyschina`, `mn**black**livesmatter`, `trevor**ross**.ca`, `**char**lesortel.com`, `**mich**igan.gov`, `dave**pidge**on.net`, `@**ash**ley_r_perez`. Orthographic, not syntactic — 3349 precedent. |
| 2582 | 7 abstract concepts — interpersonal connection | semantic | med | — | 16 distinct markers, 9 in one field: ` felt, connect, relationship, connection, kind, emotionally, moment, try, best` — "our **felt** sensing of wisdom" · "time to **connect**" · "a lack of **connection** by positive touch" · "become **emotionally** aware". |
| 2848 | 10 indeterminate | denominator only | med | **I-DIVERSE** | 13 distinct markers; passages span a printf format string, wedding decor, Lead411 email listings, ASP.NET routing, hosting uptime, Miramichi housing stats, shell scripts, a delete dialog, garbled text. Neither trigger nor passage coheres. |
| 7164 | 7 abstract concepts — effect/consequence | semantic | **high** | — | **16/16** are effect-nouns across 10 distinct lexemes: ` effects` ×2, ` impact` ×5, ` effect/Effect` ×2, ` affects`, ` implications`, ` ramifications`, ` difference`, ` role`, ` benefits`, ` joy`. Synonym substitution preserves firing (*impact*↔*effect*), so §3 routes semantic, not class 2. |
| 7314 | 2 lexical/n-gram — *have to* (deontic necessity) | **surface-form** | **high** | — | ` have` ×13, ` got` ×2, ` had` ×1 — **16/16** the semi-modal: "you're just gonna **have** to find out" · "You've **got** to stay at it" · "he knew exactly what he **had** to do" · "we **have** to act now". Prong 2 fails on **no-governor** — the marker *is* the modal (212 precedent). |
| 8024 | 11 topical — horror/Halloween/supernatural | semantic | med-high | — | 7/16 domain-lexical: ` spooky`, ` Halloween` ×2, ` haunted`, `**erie**` (Eerie), ` legendary`, `how**ls**` — "a knack for **spooky** and abnormal things. I love Tim Burton, Edgar" · "**haunted** by the demon of self-criticism" · "annual Pumpkin Pal[ooza]" · "survive the **legendary** Stygian Abyss". |

**Instrument note:** 7164 is the row whose summarizer relay produced a reproducible 15-of-16
omission. Byte-exact, it has all 16 and a clean 16/16 pattern. The omission was entirely a relay
artifact.

---

## 9. THE LAST SEVEN — GEMMA COLUMN COMPLETE AT 40

| idx | class | bucket | conf | reason | marker evidence |
|---|---|---|---|---|---|
| 7223 | 10 indeterminate | denominator only | med | **I-SILENT** | Markers land **inside malformed word forms**: `infor**mation**` (sic, "informmation"), `upsat**irs**`, `predel**ictions**`, `abil**ites**`, `T**OTA**` (Catalan). Contexts are typo-ridden, OCR-garbled or ungrammatical: "AetU'HY I'AHK, N" · "We is being patient. The Elder Cat tells us that Santa Claws" · "free yourself **form** the hassles". Stable pattern — **degraded/misspelled text** — but **no §6 class describes it.** Scheme defect, not evidence defect. |
| 7623 | **12 relational/positional** — existential *there* | denominator only | **high** | — | ` are` **16/16**, always the copula of an existential: "**There are** two types of airports in India" · "**There are** no Guarantees!" · "**There are** 658 names in this family tree" · "**There are** cricket tragics throughout Trade Me". Prong 2 satisfied with a genuine **governor (existential *there*)**, never naming the marker. §2's lexicon test independently fails — *There are* fires corpus-wide. |
| 8667 | 10 indeterminate | denominator only | — | **I-THIN** | **Only 2 records exist** (structural, n_firings=2): ` directorial` in "The screenwriter's **directorial** debut hits theaters tomorrow" and ` approximate` in "these are **approximate** and no responsibility is taken". Nothing is falsifiable at n=2. |
| 9115 | 2 lexical/n-gram — *drum* | **surface-form** | **high** | — | **16/16** on the string: ` Drum`/`Drum`/` drum`/`drum`/`rums`/` Drums`. Referents are unrelated — **Drum**roaster Coffee (a brand), Tyler **Drum**heller (a surname), drum kits, drum circles, *Drums Along the Mohawk* (a wargame), "**drum** roll", "**drum**beating". The string, not the concept. Open-class constancy → class 2 per the §13.3 guard. |
| 11270 | 10 indeterminate | denominator only | med | **I-DIVERSE** | 13 distinct markers; only 6/16 cohere ("to the **power** of", "the **Powers** of Two"). Remainder spans foreclosure cleanouts, shipping fees, ToS liability, a defrost warning, workplace logout, rental limitations. Prong 1(a) fails (11 non-modal < 12). |
| 13848 | 11 topical — hardware/electronic components | semantic | med | — | 4/16 domain-lexical (` cryogenic`, ` element`, ` inkjet`, ` Failing`); passages uniformly hardware: camera sensors and lens elements, XAAR printheads, a 6½" woofer and tweeter, piezoresistive pressure devices, fusion CPU/GPU chips, hermetically-sealed laser emitters, Ward Leonard DC motor control, laminated-glass roofs. Prong 2 fails — no single position. |
| 15054 | 11 topical — cooking/recipes | semantic | **high** | — | **16/16** cooking: ` Recipes`, ` recipe` ×3, `Muff**ins**`, ` favorite` dishes — "Cafe Rio Shredded Chicken Taco **Recipe**" · "the keto pumpkin cheese cake **recipe**" · "From Helen Corbitt's Cookbook. Serves 4." · "Mix the salt, cumin, paprika, garlic powder". |

**GEMMA COLUMN COMPLETE: 40 of 40 rows carry a class. Zero parked.** §11.2's tally-void no longer
applies to Gemma on parking grounds.

**Tally not computed here.** The Gemma composition now embeds the nine formerly-parked rows, whose
buckets are the input to §14.2's pre-registered test. Computing the composition would compute the
test. Deferred to the orchestrator by default.

---

**Qwen after retrofit: 9 rows resolved (7 classified + 2 parks closed), 0 parked, 31 outstanding.**
§11.2's tally-void no longer applies to Qwen on parking grounds; the column remains incomplete.
**Both columns are now marker-informed — the §8 evidence asymmetry is closed.**

---

## 10. QWEN — THE REMAINING 31. COLUMN COMPLETE AT 40

Evidence: `qwen_max_activating_tokens.json` (`b6bf9710a92a1bce…`) over `centred_1164`
(`72e73f26…`). **Marker-native rows: these 31 were never adjudicated pre-marker, so they carry no
`pre_marker_class`** — see §10.1. No splice seams (§11.7 inapplicable). 100% document-initial, so
§4.6 applies throughout in its §14.3-narrowed form. `position_fraction_in_chunk` used exclusively.

| idx | class | bucket | conf | reason | docs | marker evidence |
|---|---|---|---|---|---|---|
| 45344 | 2 lexical — *role* | **surface-form** | high | — | 16 | ` role` **16/16**, always "played a pivotal/major/vital/critical role"; sixteen unrelated subjects (staffing, O'Connor, Hull-House, dopamine, Brahms, Star Wars) |
| 128052 | 2 lexical — Creative Commons licence | **surface-form** | high | — | 7 | ` Commons`×4, ` License`×3, ` license`×3, ` Domain`, `ported` — the fixed phrase across seven unrelated hosts |
| 145471 | 2 lexical — *Best* in award names | **surface-form** | **low** | — | 5 | `Best`×10; **11 of 16 from one Creative Loafing page** |
| 117551 | 3 code/identifiers — statutory citations | **surface-form** | med | — | 5 | tokens inside `P.L. 99-457`, `Title 17, Chapter 1`, `Directive 2001/20/EC` |
| 37230 | 5 named entities — *iPod* | semantic | high | — | 14 | `iPod`/`Pod`/`od` **16/16**, one referent throughout (cf. 9115, where *drum* spanned unrelated referents → class 2) |
| 73803 | 5 named entities — fighter surnames | semantic | med-high | — | 5 | `son`, `nar`, `aub`, `aggi`, `rage`, ` Johnson`×2, ` Edgar`, ` Nelson` |
| 89363 | 5 named entities | semantic | med | — | 14 | 13/16 inside proper names: `C**heet**os`, `Gil**well**`, `Wo**bbl**ies`, `M**ino**an`, `POTEM**K**IN`, `W**emble**y`. **Live alternative: rare-word subword continuation (surface-form, bucket-changing), covers 11/16** |
| 73791 | 7 abstract — competitive defeat | semantic | med | — | 8 | ` beat`×3, ` over`×2, ` defeated`, ` defeating`, ` against`, ` off`, ` vs` |
| 29908 | 11 topical — human genetics / rare variants | semantic | med | — | 5 | ` rare`×4, ` variants`×3, ` frequency`×2, ` mutations`, ` coding` |
| 20990 | **12** — clause-initial subordinator | denominator only | high | — | 15 | ` As`×8, `As`×6, ` as`×2 introducing attribution/circumstance; governor = matrix clause; prong 1(b) confirmed in-record |
| 105490 | **12** — anaphoric demonstrative | denominator only | med-high | — | 16 | ` that`×14, `that`, ` those`; governor = antecedent. **Boundary case: if anaphora confers no governor this becomes class 2 and enters the numerator** |
| 60751 | 10 indeterminate | denominator only | — | **I-THIN** | 2 | 15/16 from one food-safety page |
| 90863 | 10 indeterminate | denominator only | — | **I-THIN** | 2 | n_firings = 2 |
| 134801 | 10 indeterminate | denominator only | — | **I-THIN** | 2 | 15/16 from one BD corporate page |
| 15095 | 10 indeterminate | denominator only | — | **I-THIN** | 6 | 11/16 from one comment-report widget |
| 15430 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 16 types/16 |
| 86258 | 10 indeterminate | denominator only | med | I-DIVERSE | 14 | 14 types/16 |
| 159845 | 10 indeterminate | denominator only | med | I-DIVERSE | 9 | 6/16 from one dictionary page |
| 120545 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 16 types/16 |
| 124705 | 10 indeterminate | denominator only | med | I-DIVERSE | 15 | 16 types/16 |
| 128788 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 14 types/16 |
| 84087 | 10 indeterminate | denominator only | med | I-DIVERSE | 12 | 16 types/16 |
| 137584 | 10 indeterminate | denominator only | med | I-DIVERSE | 12 | programming reading covers ~7/16 |
| 81977 | 10 indeterminate | denominator only | med | I-DIVERSE | 15 | 14 types/16 |
| 151841 | 10 indeterminate | denominator only | med | I-DIVERSE | 14 | 14 types/16 |
| 65931 | 10 indeterminate | denominator only | med | I-DIVERSE | 12 | **highest-firing feature in the column: 15,318 firings, 99.3rd pctile, no pattern** |
| 72648 | 10 indeterminate | denominator only | med | I-DIVERSE | 14 | 16 types/16 |
| 10455 | 10 indeterminate | denominator only | med | I-DIVERSE | 15 | 16 types/16 |
| 140622 | 10 indeterminate | denominator only | med | I-DIVERSE | 16 | 16 types/16 |
| 135599 | 10 indeterminate | denominator only | med | I-DIVERSE | 13 | 15 types/16 |
| 103491 | 10 indeterminate | denominator only | med | I-DIVERSE | 14 | 16 types/16 |

### 10.1 MARKER-NATIVE ROWS — a second hole of the §14.1 shape

These 31 rows have **no `pre_marker_class`**, because they were never adjudicated without markers.
§11.1's conservative tally resets rows whose class moved toward the numerator on marker access; a
marker-native row cannot move, so it enters the conservative tally unreset by construction.

This is structurally identical to the parked-row gap §14.1 closed, and it is **larger**: 31 rows
versus 2. Of the 9 pre-marker Qwen rows, exactly one moved numerator-ward (14081, from a park).
Whether that rate should be imputed to the 31 marker-native rows, or whether the conservative tally
simply cannot bound this column, is **not decided by Rater 1.**

### 10.2 SUPPORT CONCENTRATION IS THE QWEN COLUMN'S LIMITING DEFECT

Five rows are `I-THIN`, four of them with **one document supplying 11–15 of 16 records**
(60751, 134801, 15095, plus 70945 from the earlier batch). Two more classified rows rest on heavily
concentrated support (145471 at 11/16 single-document, 117551 at 10/16).

Gemma shows nothing comparable: its records come from a packed stream and spread across documents
by construction. **Matched depth (16/16) did not deliver matched support.** This is an unmatched
axis between the columns, discovered after the depth ruling, and it is directional — thin support
pushes rows to `indeterminate`, which deflates the surface-form count.

**QWEN COLUMN COMPLETE: 40 of 40 rows carry a class. Zero parked. Both columns closed.**

**Tally not computed here**, per the standing bar on Rater 1 seeing either composition.

---

## 11. THREE CLOSING ROWS — two tests run from the marker file, one disclosure

Orchestrator ruling received: **an antecedent is not a governor.** Government is syntactic
licensing; anaphora is referential. Class 12 is therefore unavailable to 105490. The ruling was
deliberately not allowed to decide the row, because class 2 covers POS category and anaphors are a
closed one — ruling the governor question alone would have placed a row in the numerator *by
definition rather than by measurement*. Both tests below were run before any class was written.

### 11.1 105490 — do non-anaphoric uses of the same tokens fire? **YES. Class 2, surface-form.**

Method: for each of the 16 top records, every occurrence of `that`/`those` inside the frozen
`centred_1164` window was located and scored fired / unfired, fired being the marked position.
41 occurrences across the 16 windows: **16 fired, 25 unfired.**

**Result A — non-anaphoric demonstratives fire.** 4 of the 16 fired records have no antecedent:

| rank | doc | fired text | use |
|---|---|---|---|
| 4 | 905 | "we can't locate **that** page on ChicagoFed.org" | situational/exophoric — refers to the URL the reader typed, absent from the text |
| 8 | 4463 | "Optimize **that** balance of people, process and cost effective technology" | cataphoric — bullet-initial, reference supplied by the following `of`-phrase |
| 12 | 3048 | "beyond / **that** allowed by fair use" | cataphoric/internally-headed — reference completed by the participial postmodifier |
| 13 | 83 | "**that** other African election, the one in France" | cataphoric-appositive — the appositive supplies the referent forward |

The orchestrator named cataphora as the discriminating case; three of the four are cataphoric.
Branch A of the test is met on its own terms.

**Result B — the same token string does NOT fire in non-demonstrative syntax.** Of the 25 unfired
occurrences, **13 are non-demonstrative** — 9 complementizer (`ensure that you've re-typed`,
`the fact that there were four bugs`, `claimed that their soldiers`, …) and 4 relativizer
(`a service that allows you to log on`, `infrastructure that can prevent`, …). **Zero fired.**
The fired set is 16/16 demonstrative, the non-demonstrative set is 0/13. Under indifference to
syntactic category the fired set would be all-demonstrative with probability ≈ (28/41)^16 ≈ 0.002;
the occurrences are not independent draws, so this is an order-of-magnitude figure, not a test.

**Result C — the decisive one, and it was not in the test as written.** `this`/`these` carry the
identical referential function and **never fire**: zero in the fired set, two present-and-unfired
in-window (`one of these sites` rank 0, `"This partnership is an historic moment` rank 9). If the
invariant were the referential function, `this`/`these` would fire equally. They do not. The
invariant is the lemma pair {that, those} in demonstrative syntax — **a lexical/POS invariant, not
a functional one.**

§3 confirms: form-preserving nonsense preserves the trigger ("all information in those wugs");
paraphrase destroys it ("all information in the accounts just described").

> **105490 → class 2 (lexical/POS), surface-form, confidence HIGH.** 16 distinct doc_ids. Support
> caveat: docs 4652 and 4653 are near-duplicate pages carrying the same sentence, so distinct texts
> number 15, not 16.

**Stated limit on both tests in this section.** "Unfired" means *did not itself reach top-16
strength*, not *did not activate*. If the extractor applies proximity de-duplication within a
document, some unfired positions may be suppressed rather than weak. The extractor is known not to
de-duplicate by document (89363 draws two records each from docs 3093 and 3094), but its proximity
rule is not documented and I did not verify it.

### 11.2 89363 — is the subword reading causally prior? **NO. Class 5 stands, medium.**

The hypothesis under test: rare proper nouns tokenize into subword continuations, so "fires on
subword continuations of rare words" would *produce* "inside proper names" as a downstream artifact.
If so the subword reading is causally prior and the row moves to surface-form.

Method: every multi-token word in the 16 marker windows was reconstructed and each of its
continuation tokens scored fired / unfired.

**Result — non-proper-name rare words with subword continuations are present in these windows and
do not fire.** Eight such continuations, across five records:

| record | word | unfired continuations |
|---|---|---|
| 4 | archaeology | `ology` |
| 4 | amalgamated | `am`, `ated` |
| 5 | solace | `ace` |
| 5 | crewmen | `men` |
| 14 | hilltops | `top`, `s` |
| 15 | craze | `ze` |

By the orchestrator's rule this is the "firing stays confined" branch, and class 5 stands. The
selectivity is sharper still *within* proper names — only one continuation of each fires
(`Wobblies` fires `bl` not `ob`/`ies`; `POTEMKIN` fires `K` not `EM`/`IN`; `Cheetos` fires `heet`
not `os`; `Sprinkles` fires `ink` not `les`) and several whole proper names sit in-window unfired
(`Frito`, `Namakkal`, `Stackhouse`, `Moriarty`, `Gretchen`, `Cupcakes`).

**The alternative is weakened, not dead**, and honesty requires the qualification. Its one unique
win is the top-activating record: `lam|ington|s` — a lowercase common noun, rare, split into
continuations, firing at rank 0 and the highest activation in the set. The subword reading covers
11/16, the proper-name reading 13/16, and **neither covers ranks 10 and 11** (` can` in "I think I
can", ` relationship`), which are whole-word tokens in neither category.

> **89363 → class 5 (named entities), semantic, confidence MEDIUM — unchanged.**
> **Confidence basis recorded as instructed: the margin is two records (13 vs 11) on heavily
> overlapping sets** — 10 records are both proper-name and subword; only 3 are proper-name-only,
> only 1 subword-only.
> **The row did not move. No marker-driven reclassification occurred, so there is no floor
> implication from this row.**
> Additional support note: the top-16 activation range is 4.16–6.25, an order of magnitude below
> 105490's 29.0–39.0. A shallow, low gradient means the membership of this top-16 is less stable
> than the rank ordering suggests. This is part of why the confidence is medium.

### 11.3 145471 — disclosure on the row, as instructed

> **145471 → class 2 (lexical/n-gram), surface-form, confidence LOW — unchanged.**
> **CONCENTRATION, RECORDED ON THE ROW: 11 of 16 records come from a single page** — an artist
> biography listing award credits, carrying ranks 0, 1, 2, 3, 5, 7, 8, 10, 12, 13 and 15.
> **Distinct documents: 5** — that page ×11, one further page ×2 (ranks 6 and 9), and one record
> each at ranks 4, 11 and 14.
>
> *Its doc_id is withheld under §13.2a: the numeral collides with a calibration-reserved feature
> index. The document is fully recoverable from the marker file by the rank list above, so nothing
> auditable is lost.*
>
> This is a **numerator row at low confidence resting on one page**, and it is flagged here for
> individual listing in the write-up, on the same principle applied to Gemma's unauditable numerator
> rows: where the claim is strongest the evidence base gets shown, not summarised.
>
> Two further facts a reader is entitled to. **(a)** The trigger is the award-citation n-gram, not
> the word *Best*: 7 of the 16 markers are not `Best` — three are ` of` (inside "Best of 2009"),
> plus ` Readers`, an apostrophe, and a curly quote. **(b)** Rank 14 contains no *Best* at all —
> "the **“**US Retailer of the Year”" — the frame fires without the word. Both facts support the
> n-gram reading over a lexical-item reading, and neither changes the bucket.

### 11.4 The 31-row floor hole — orchestrator ruling recorded, not repairable

Ruled: the measurement can no longer be taken by anyone. Rater 1 has seen the markers; Rater 2 built
the Qwen marker file. Imputing the 1-of-9 movement rate onto 31 marker-native rows would be
inference from a subsample never shown representative. **The Qwen floor becomes a computed
interval** — lower end resets every marker-native numerator row, upper end resets only measured
movers — and the true floor cannot be located within it. Convergence binds to the lower end.
**Neither end is computed by Rater 1.**

---

**ADJUDICATION COMPLETE. Both columns 40 of 40, zero parked, three closing rows landed.**
No composition, no rate, and no §14.2 result has been computed by Rater 1, and neither the merged
ledger nor any `_r2` file has been opened since the §12.1 partition.
