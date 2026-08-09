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
