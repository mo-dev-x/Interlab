# Methods and Limitations — SPRINT-2026-08 cross-model SAE feature study

**Author:** Mohamed El Yazid — IID
**Status:** authoritative consolidation. Supersedes scattered notes in `COMPLETION_LEDGER.md`,
`VERIFICATION_LOG.md`, `pi_directive_plan_2026_08.md`, and the two pre-registration packets, all of
which remain the primary record for their own items.
**Scope:** everything a reader needs to judge what these measurements support and what they do not.

---

## 0. The claim, stated exactly

> **Two independently-conducted measurements — on different models, different SAE architectures,
> different expansion ratios, different training provenances, and different relative depths — that
> converge on the same qualitative finding: a skew toward surface-form feature detectors.**

**This is not a controlled comparison and is not presented as one.** At **seven** unmatched axes the
honest framing is convergent evidence from independent setups, which is a recognised and often
strong form of inference, and it is the stronger argument available from these facts. The
alternative framing — "a controlled comparison with seven confounds" — describes the same data and
sounds damaged.

> *Corrected 2026-08-08.* This paragraph said **five** twice while §0.1's own table listed **six**
> and §4.10 was titled "a sixth unmatched axis" — the count was understated in the most-read
> paragraph in the document, which is the one place it cannot be. The **seventh** is
> **distinct-source support at matched depth** (§4.11, added the same day): at depth 16 Qwen carries
> a mean of 11.23 distinct documents (exact) against Gemma's ≈15.53 (proxy; Gemma supplies no
> document identifier, so no exact figure exists). **A reviewer who counts table rows must
> arrive at the same number as a reader who reads the prose.**

**Existence and direction only. Never magnitude.** The expansion gap (32× vs ~4.2×) is a plausible
alternative explanation for the *size* of any skew — a narrower dictionary has less capacity and
spends more of it on high-frequency surface forms. The two percentages are therefore **not
commensurable** and must never appear in adjacent numeric cells, in a delta or ratio column, or
under a spanning header that invites subtraction.

**This licenses nothing about any individual feature across models.** There are no matched features
and there never were.

### 0.1 The unmatched axes, and why each differs

| # | Axis | Qwen | Gemma | Differs by |
|---|---|---|---|---|
| 1 | Model | Qwen2.5-14B-Instruct | gemma-3-12b-pt | design |
| 2 | SAE architecture | TopK, k=100 | JumpReLU | design |
| 3 | Expansion | **32×** (`d_in` 5120 → `d_sae` 163840) | ~4.2× (`d_in` 3840 → 16k) | design |
| 4 | Training provenance | trained by us, 400M FineWeb tokens | Google, Gemma Scope 2 | design |
| 5 | Relative depth | layer 28 / 48 = **58.3 %** | layer 31 / 48 = **64.6 %** | **availability** |
| 6 | Evidence provenance | document-initial ≤512-token spans | packed-stream windows | instrument |

**Axis 5 must be named together with its reason.** Depth differs by *availability*, not design: we
wanted 28↔28, and Gemma Scope 2's canonical labelled release does not carry layer 28. A reviewer
will ask why depth was not matched; that one-clause answer is a good one, and its absence reads as
carelessness rather than constraint.

**Axis 6 was discovered during adjudication** and is documented in §4.10.

---

## 1. Instruments

### 1.1 Qwen — `rwu04lpb`

| Field | Value |
|---|---|
| Checkpoint | `rwu04lpb/final_400001024` |
| Hook | `blocks.28.hook_resid_post` |
| Geometry | `d_in` 5120, `d_sae` 163840, TopK, k=100, expansion 32× |
| Training | 400M FineWeb tokens, seed 42, sae-lens 6.44.2 |
| Weights hash | `sha256:95db17aa…e215ce4` |
| A6 certificate | `0a572198764d` (job 383528), verdict **amber** |
| Certificate metrics | fvu 0.0103 · ce_recovered 0.9884 · dead_fraction 0.0008 |

**The verdict is amber and is reported as amber.** The amber arises **solely** from
`max_decoder_cosine_p999`; the other three metrics are individually green, with bands at
placeholder v1. That is characterisation, not hedging, and it is more useful to a reader than the
verdict alone.

**Do not confuse with `9odeg5hb`.** An abandoned pile-10k **base**-model checkpoint with `d_sae`
81920 / expansion 16× appears in `results/FEATURE_EXPERIMENT_LOG.md` §1, which §6 and §25 both
supersede. Any figure citing 16× for *the instrument* is wrong. `hm03l7yz` legitimately carries
`d_sae` 81920 as the L28×16 width-sweep point and is also not the instrument.

### 1.2 Gemma — Gemma Scope 2

| Field | Value |
|---|---|
| Model | `google/gemma-3-12b-pt` |
| SAE | `google/gemma-scope-2-12b-pt`, `resid_post/layer_31_width_16k_l0_medium` |
| Hook | `blocks.31.hook_resid_post` |
| Geometry | `d_in` 3840, `d_sae` 16384, JumpReLU |
| Measured L0 | **65.61** (n=504 tokens) vs registry-claimed 60.0 — reported as measured |
| Loaded class | `HookedTransformer` over `Gemma3ForConditionalGeneration` |

`d_model = 3840` is the **text-tower** width, which is exactly why it is the decisive
identity check on a multimodal wrapper. `n_layers = 48`. Both verified against real weights before
any record was generated.

---

## 2. Sampling

### 2.1 Both columns are seeded uniform draws

| | Qwen | Gemma |
|---|---|---|
| Space | `[0, 163840)` | `[0, 16384)` |
| Seed | 42 (`numpy.default_rng`) | 42 (`random.Random`, stdlib MT) |
| n | 40 primary (+24 reserve) | 40 |
| Dead discarded | **0** | **0** |
| Duplicates rejected | 0 | 0 |

**The earlier Gemma sample was browsed, and is superseded.** Thirty-three features chosen while
browsing Neuronpedia yielded a 58 % surface-form figure. **That figure is retired and is not
published**, for two reasons: browsing is a selection mechanism that threatens *direction* and not
merely magnitude, and the number never appeared in the repository, while `19` is used one line away
in the ledger for a different count — one keystroke from being misread.

**Pre-registered before the uniform draw returned:** the uniform draw is authoritative and the
browsed figure is superseded **whichever direction the new number moves**. Choosing the headline
after seeing both would launder the selection problem one level up, through the choice of
statistic. The uniform draw immediately surfaced topical domains the browsed sample missed entirely
— soil science, chemistry, recipes, job postings, mechanical components — which is direct evidence
that **browsing was the biasing step**, and it means the fraction may move downward.

**Two earlier negatives are withdrawn, not softened.** "No geography feature" and "no concrete
physical object feature" were bounded at n=33 and are contradicted by the uniform draw. A negative
claim that proves to be a sampling artifact should be withdrawn.

### 2.2 Qwen over-recruitment

Dead-exclusion judged *on this pass*, a denominator of exactly 40, and a single job cannot all
hold. Resolution: **64 indices drawn in seed order, all 64 measured in one pass, taxonomy set = the
first 40 alive in stream order**, reserves consumed strictly in seed order and only to backfill a
dead primary. The rule was written to `select_features.py` **before submission**, making it
pre-registration rather than a post-hoc fit. Reserve consumption is **deterministic and never
content-based**, so the resulting 40 remains a uniform sample of *live* features. Zero were
discarded, so no reserve was promoted and `ARM_PRIMARY` equals the primary 40 verbatim.

**Pre-registered before results:** primary n=40 carries the claim unconditionally; the n=64 arm is
a **within-Qwen stability check only** and is not comparable to Gemma, which has no reserves.

### 2.3 If time runs out — matched-prefix fallback

Pre-registered before any count existed: both columns truncate to the **first N features in seed
order**, N = min(Gemma completed, Qwen completed). Seed order is content-neutral, so a prefix of a
seeded uniform sequence is **still a uniform sample** — truncation, not selection. N is reported
explicitly and never as "n=40". Rows classified beyond N are retained and reported separately,
never silently dropped and never used to extend one column past the other.

---

## 3. Classification scheme

### 3.1 Four buckets

| Bucket | Numerator | Denominator |
|---|---|---|
| surface-form | **yes** | yes |
| semantic | no — reported alongside | yes |
| discourse-register | no | **yes** |
| indeterminate | no | **yes** |

**The two headline fractions do not sum to one, by construction.** Two buckets sit in the
denominator and in neither numerator. This is stated explicitly wherever the fractions appear,
because a reader assumes a partition unless stopped, and a figure legend travels further than a
caption.

**Primary result is the full four-way composition; the fraction is derived.** A fraction whose
denominator contains two non-numerator buckets is sensitive to their size. A composition is harder
to manipulate and more informative than any single number extracted from it.

### 3.2 `indeterminate` was pre-registered before the data

Without it, a feature whose evidence does not decide gets silently forced into a bucket to make a
tally come out — row-level laundering, and the most common way a taxonomy quietly becomes an
argument. **There is no minimum-support threshold, ever:** inventing an evidence floor after seeing
the data is precisely the exclusion criterion this bucket exists to prevent.

### 3.3 Class 11 was added mid-adjudication — and it works against the finding

Classes 5–8 are entity-, action-, abstraction- and role-shaped. None describes a feature whose
organising principle is a **subject-matter field** — electoral politics, document typesetting, soil
science, chemistry, cookery, horror fiction, job-seeking. The gap was expected to affect ~7+ of 40
rows.

**Legitimacy:** found from evidence, **before any tally, count or fraction existed**, and the
change moves rows **into** the semantic bucket — which makes the surface-form skew **harder** to
support, not easier. A change that damages the finding it is adjacent to cannot have been motivated
by that finding. Rows classified before the addition are protected by the §5.3 post-hoc re-check.

Rejected alternatives, on the record: forcing these rows to `indeterminate` would systematically
deflate semantic and inflate the two non-numerator buckets — a *directional* bias on the headline.
Widening class 7 by striking "non-perceptual" would merge concrete subject domains with
non-perceptual abstractions under one uninterpretable label.

**Guard against catch-all use:** if the field cannot be named without enumerating the examples, the
row is `indeterminate`, not class 11.

### 3.4 Labels are hypotheses, never evidence

Snippets adjudicate. Both autointerp passes are claims to be checked against the evidence, never
votes. This is not a new rule — snippet inspection already **overturned both labels in 8 of 20**
adjudications, and `gemini-2.5-flash-lite` returns strings such as *"dare I say"*, *"this arena"*,
*"keyboard, Lens"*, *"seeking"* — token dumps, not classifications. Where the two passes imply
different classes there is nothing to break a tie between, because neither was ever a vote.

**Qwen carries no labels at all**, so its evidence is *structurally immune* to label contamination.
Gemma required a protocol fix to reach the footing Qwen has by construction. **On the window and
document-provenance axes the correction runs the other way.** Neither instrument is uniformly
better; they fail differently, and both needed fixing.

### 3.5 Support is reported as distinct sources, not record count

Sixteen records can be re-reads of a handful of documents. **Qwen** idx **14622** looked decisive at
16-of-16 and collapsed to **7 distinct documents** (doc 3498 ×5, doc 4607 ×4), at which point a
competing reading — awards/recognition, 6 of 7 — became live against film/cinema, 5 of 7. The class
was revised downward with the alternative recorded; **the ledger records confidence `low`.** Gemma
has the same exposure (idx 7164 carried two records with near-identical text), so this is a
**matched** improvement, not a Qwen-only adjustment.

> *Corrected 2026-08-08.* This paragraph said **Gemma** idx 14622. **It is a Qwen feature** — the
> ledger row reads `14622 | qwen`. The error mattered more than a mislabel: 14622 is the flagship
> example for the whole distinct-source rule, prereg §11.6 cites it as an independently reproduced
> result, and the closing sentence *"Gemma has the same exposure … not a Qwen-only adjustment"* only
> parses if 14622 is Qwen — so **the paragraph contradicted itself and the contradiction was the
> clue.** Confidence was stated as "revised from high to medium"; `medium` is the *second*
> adjudicator's value, `low` is the first adjudicator's and the one in the ledger. Reporting the
> second rater's number as the column's is the same class of error as the mislabel.

**The bucket is often stable across competing readings even when the class is not** — 14622 is
semantic under either. Where that holds, the four-way composition is unaffected and only the
eleven-class breakdown is uncertain. Say which.

---

## 4. Evidence, and every artifact found in it

### 4.1 Depth is matched at 16/16

| | Qwen | Gemma |
|---|---|---|
| Primary depth | top 16 (truncated from 25, plain slice, **no re-sort**) | top 16 of 20 |
| Sensitivity arm | full 25, **within-Qwen only** | — |
| Low-support row | idx 90863, 2 firings | idx 8667, 2 records |

**Why depth is matched at all:** a 5-vs-25 gap pushes a *directional* artifact into the primary
number. `indeterminate` is assigned when evidence does not decide, so the shallower column
accumulates it purely from having looked less — and that surfaces as a real-looking difference in
composition.

**Revision history `5 → 16 → 20 → 16`.** Every move was evidence-driven and **no counts existed at
any point**; a reader seeing only the endpoint cannot verify that, so the sequence is given.
16 → 20 followed a corrected pool reading; 20 → 16 followed the discovery that the pool figure
itself was unverifiable through the summarizer channel. **Truncation can only undercount**, so a
single reading of ≥16 proves the pool is ≥16 — 16 was verified present everywhere while 20 was
verified nowhere.

**Subsequently settled by direct API fetch:** 39 of 40 Gemma features hold **exactly 20 records**;
idx 8667 holds 2. The ruling of 16 stands and now rests on a measured number rather than an
inference.

**Ties preserve array order on both sides.** Gemma idx 3648 holds three records at exactly
1155.9937 and idx 7623 two at 4587.2803. A re-sort would silently reorder ties and desynchronise
the primary and sensitivity arms for a reason unrelated to evidence.

### 4.2 Top-k construct is confirmed on both sides

Gemma: `maxValue`s descend strictly in array order with no band structure across features spanning
three orders of magnitude in density, and SAEDashboard's quantile markers `binMin` / `binMax` /
`binContains` are the sentinel `-1` on every entry checked. **Idx 11270 is decisive** — at density
1.5e-6 a stratified sampler would have to reach into low-activation bands to fill the pool,
producing visible banding, and the descent stays smooth (2132 → 1649).
Qwen: verified empirically across all 40 features, zero exceptions.
**Matched counts are therefore matched construct**, and no disclosure is needed on this axis.

### 4.3 The window artifact — and why it is directional

A ~90-character excerpt suffices to decide a **topical** trigger and not a **token-level** one. The
class boundary test is literally *"would a token-level lexicon or POS tagger reproduce the firing
set?"*, which cannot be answered from a gist. So short windows push function-word, punctuation and
morphology features — **class 2, in the surface-form numerator** — into `indeterminate`, while
topical classes stay fully decidable. **It deflates the headline fraction for an instrument reason,
with a direction, invisibly.**

Two worked demonstrations, both from verified evidence:

- **idx 212** — at 90 chars, 5 of 16 windows showed a negation and the row was heading for
  `indeterminate`; at 300 chars negation is visible across far more (*"I do not agree with all of
  his views"*, *"I can't seem to see why"*, *"I don't have a blank option"*, *"wouldn't be
  acceptable… it's not acceptable"*).
- **idx 3349** — at 90 chars, "scattered numerals"; at full length, unmistakable URL fragments,
  cache paths, hex correlation IDs and `.php` error traces.

**Resolution correcting a targeted-repair trap:** the re-pull was **uniform across all 40**, not
targeted at the indeterminates, because resolving only the indeterminates **can move rows out but
never in** — an asymmetric re-examination that manufactures exactly the direction being removed.

### 4.4 Matching the window: total context, not nominal width

A prefix delivers context around the trigger only by accident, and by different amounts per column.
**Centring is the matched option.** Measured Gemma record lengths, byte-exact `len()` over all 40
features / 626 top-16 records:

| min | p10 | **median** | p90 | max | mean |
|---|---|---|---|---|---|
| 460 | 980 | **1164** | 1320 | 1547 | 1148 |

This **replaces a provisional 1269–2847 interval estimated from three features**, against which 972
Qwen rows had been binned. The correction reverses the conclusion: Qwen full chunks run median
2038, so **Qwen carried ~1.75× Gemma's context**, not less. More context means fewer
indeterminates, so full-vs-full would have deflated **Gemma's** surface-form numerator.

**Primary arm: `centred_1164`.** Sensitivity arm: `full_chunk`.

**Its cost, measured and accepted deliberately:** only 36.63 % of rows reach the full 1164; median
delivered context is **997**, landing ~14 % *below* Gemma's median rather than on it. That is a
14 % mismatch where full-vs-full was 75 %. **Symmetric-and-weak beats asymmetric-and-strong**,
because a mismatch has a *direction* and direction is the one thing existence-and-direction framing
cannot survive.

**Stated limitation — symmetry, made measurable rather than merely disclosed.** Gemma records are
not centred on the activation: measured trigger positions run **0.6 %–75 %** of the record. Qwen's
`activating_relative_position_pct` has median 49.83 % but p10 19.92 / p90 77.41, range 0.2–99.83 —
so the two distributions **overlap more than "centred vs uncentred" implies**, checkable from the
emitted field rather than assumed.

### 4.5 Alignment of the activating-token marker

The first extraction scored alignment by testing whether the candidate token appeared *anywhere*
inside the recorded 9-token excerpt. Both offset hypotheses satisfy that trivially; the scorer tied
1538–1538 and a `s1 >= s0` tiebreak **silently adopted a one-token shift**. A 100 % containment rate
would have been reported and **would have validated nothing** — a ±150-char window contains a
9-token excerpt whether or not the marker is off by one.

**A check that both hypotheses pass is not a check.** Replaced by an exact-span test:
`characterize_lite` builds each excerpt as `"".join(str_tokens[max(0,pos-8):pos+1])`, so a one-token
shift moves both endpoints and string equality discriminates — **offset=0: 100 %, offset=1: 0 %**.
The run now aborts unless one hypothesis clears 95 % and the other falls below 50 %; no silent
default. For token-level features a one-token shift puts the marker on the neighbour, destroying
precisely the class-2 signal the widening exists to make readable.

### 4.6 Qwen evidence is always document-initial — 100 %, unmitigated

Every Qwen chunk is `text[:c_end]`, beginning at character 0 of its document, **verified
structurally across all 972 rows**, truncated or not. **Every record therefore opens with a title or
masthead by construction.**

This nearly produced a confident and entirely spurious class: Gemma-side adjudication of Qwen idx
**107244** was heading for "titles/headlines" on the strength of 16 of 16 records opening with a
document title — a pattern *guaranteed by the window* and carrying no information about the feature.
It was caught by checking the chunk definition rather than trusting the pattern.

**Binding rule in force for the whole Qwen column: opening-line patterns are NON-EVIDENCE.**
Centring moves the window off the document start for most rows and is the *secondary* defence; the
rule is the primary one, because short documents cannot escape their own start.

### 4.7 Census conditioning — the milder, partial version of the same fact

Distinct from §4.6 and frequently conflated with it. `characterize_lite` processed the first ≤512
tokens of each document, so Qwen's **feature census** — firing rates, corpus maxima, top examples —
is conditioned on document-initial text.

| ARM_PRIMARY | fully contained | truncated |
|---|---|---|
| top-25 rows (972) | 447 (45.99 %) | 525 (54.01 %) |
| top-16 rows (626) | 300 (47.92 %) | 326 (52.08 %) |
| top-16 unique docs (420) | 212 (50.48 %) | 208 (49.52 %) |

Token counts are right-censored at 512 by construction, so **characters** are the exact measure:
median **97.73 %** of each source document was processed, p75 and p90 both 100 %, mean 76.3 %, but
p25 49.36 % and a 1.43 % minimum. Document lengths run median 2,318 chars with a tail to 126,745.

**About half the documents were seen in full; the truncated half loses a median ~50 % of its text,
with a tail where 98 %+ never entered the census.** Not the modest bias an optimistic reading would
give, and far from total.

**These are two different things and the disclosure must state both, because only the second is
partial:** document-initial anchoring is **100 % and unmitigated**; census conditioning is ~52 % of
rows with a median 97.7 % of characters processed.

**No re-run of `characterize_lite` with different chunking was performed.** That is a deliberate
scope decision under deadline, not a claim that it does not matter.

### 4.8 The channel is sound for meaning and unsound for bytes

The single most consequential methodological finding. The two-pull checksum compares `maxValue`,
and **a paraphrased snippet carries the same `maxValue`** — so the gate is *structurally blind* to
text-level corruption.

That is acceptable for adjudication, where records are read for meaning and meaning survives light
paraphrase. It is **fatal** for ΔNLL, which is computed on the exact token sequence: a summarizer
that smooths one clause changes the number and no instrument would ever report it. The
necessity-snippets file was therefore **not** produced through the assistant channel but by direct
`curl` against the public unauthenticated API, byte-exact, with the extracted text verified against
the raw JSON by byte length.

**The general rule: a tool-mediated read that can silently return wrong or partial data is not
evidence.** Aggregates may be trustworthy while element-level claims from the same response are
not.

**And its sharpest corollary:** *two agreeing pulls through one summarizer are one observation, not
two.* Reproducibility certifies only the path the pulls share. The checksum gate must be read as
**within-path consistency**, never as verification.

### 4.9 Instrument failure modes — seven, all characterised

A methods section listing seven characterised instrument failures is *more* trustworthy than one
listing none.

| # | Mode | Evidence |
|---|---|---|
| 1 | **Label contamination** — snippets synthesised from the explanation field | idx 212: label "negation terms" produced snippets *"I don't believe"*, *"Needless to say"*, *"Don't wait"*; the real top-5 under anchored, label-excluded fetching (reproduced on two independent calls) concern a religion hater, Susan Serra, an inspector general, content marketing, revisiting fundamentals |
| 2 | **Omission** — a value silently dropped from a top-k pull | idx 7164 dropped 3353.8188 from position 8; idx 4090 dropped 2244.1062 |
| 3 | **Degenerate repetition** — one snippet emitted many times | idx 7223: a single snippet repeated 11 times |
| 4 | **Tie collapse** — duplicate `maxValue`s deduplicated | idx 3648: three records at 1155.9937 returned as one |
| 5 | **Scaffold drop** — the enumeration pass itself omitting values | idx 7623 (3983.001, correctly ordered between 4023.3096 and 3981.8379) and idx 2848 (1052.2909) |
| 6 | **Reproducible fabrication** | idx 7164 returned "15 entries under a Top 16 header" **twice, reproducibly**; the byte-exact source holds **20**. Feature-specific reproducibility was read as pointing at the record set; it pointed at the summarizer |
| 7 | **Packed-stream splice** — unrelated documents fused at a seam with no separator | `…opinionTomahawk`, `…kainateA new ransomware`. Measured exactly on `<bos>` markers: **291/626 records = 46.5%**, no feature clean (min 2/16 at idx 3039, max **14/16** at idx 7623, median 7). **A lower bound:** both example seams above are in idx 3358 and carry *no* `<bos>`, so unmarked seams demonstrably exist. A surface heuristic (no-space lower→Upper at a token boundary) flagged 57.2% but was **~97% false positive** on inspection — `B2B`, `InfoGroup`, `WinRAR`, `CompTIA`, `AZ-16A` are tokenizer splits, not seams. **46.5% is the floor; the true rate is higher and is not measurable by surface pattern.** Unlike modes 1–6 this is a property of the *corpus*, not the channel — no re-pull removes it |

Further observed: insertion (idx 2848, a value 1333.11 absent from its enumeration, rounded to
2 d.p.); truncation to 110–200 characters; array-length variance of 15/16/19/20 for the same cached
document; and **count-style queries returning 16 where enumeration and explicit length queries both
returned 20**.

**Mode 6 is the one most likely to fool a careful reader**, because reproducibility is normally
evidence. Here it certified only a shared path.

**Why a rule at the judgment layer could not have prevented mode 1:** the pre-registration forbids
labels as evidence and voids the comparison if that is violated. The adjudicator would have complied
perfectly at the judgment layer and still produced a corrupted table, because the corruption was
**upstream, at the data layer**, and invisible from inside the adjudication. **A rule that
constrains reasoning cannot protect against corrupted inputs.** The remedy is a control at the layer
where the failure lives: anchored, label-excluded fetching plus a checksum gate — and, where bytes
matter, bypassing the summarizer entirely.

### 4.10 Evidence provenance is a sixth unmatched axis

Qwen evidence is **always document-initial**; Gemma evidence is an arbitrary packed-stream window,
and many records visibly splice two unrelated documents. So Qwen evidence always shows titles,
mastheads and boilerplate while Gemma evidence often does not. That tilts Qwen toward formatting-
and title-flavoured readings — **class 4, in the numerator** — for purely instrumental reasons.
Disclosed, not fixed; the opening-line rule (§4.6) is the mitigation.

### 4.11 Distinct-source support is a seventh unmatched axis — matched counts did not match support

Found 2026-08-08 by asking the mirror question about degenerate repetition — *if Gemma repeats
snippets, does Qwen?* — on an axis **neither column had measured.**

> ### ⚠ CORRECTED 2026-08-08, same day, before publication — the first version of this section
> compared two different quantities.
>
> It read *"mean distinct documents per feature: Qwen 11.22, Gemma 15.65."* **15.65 is not Gemma's
> distinct-document count. It is Gemma's mean RECORD count**, and the arithmetic is exact rather
> than coincidental: `39 features × 16 records + idx 8667's 2 = 626; 626 / 40 = 15.6500`.
> **The identical figure holds on the Qwen side** — `39 × 16 + idx 90863's 2 = 626`, mean `15.6500`.
> So 15.65 is a number **both columns share by construction** and cannot distinguish them at all.
> The section as first written set an exact count of *documents* against a count of *records* — a
> construct mismatch of exactly the kind §4.11 was added to name, committed inside §4.11 itself.
> Caught by an independent recomputation, not by review.

At the matched depth of **16**, mean distinct sources per feature: **Qwen 11.23** (exact, by
`doc_id`) against **Gemma ≈ 15.53** (**proxy**, by text clustering). Qwen has **13 of 40** features
resting on ≤ 8 distinct documents and **three** — 70945, 60751, 134801 — whose 16 records are just
**2** documents.

**Gemma's figure is a proxy and cannot be made exact.** Neuronpedia returns `dataIndex: null` on all
626 records, so Gemma supplies **no document identifier**; distinct sources can only be estimated by
clustering the record texts. **That estimate is an upper bound** — clustering detects only duplicate
sources visible inside a ~1164-character window, so two windows drawn from distant parts of one long
document read as distinct. **The instrument asymmetry inflates the apparent gap**, and the two sides
of this comparison are therefore measured by different instruments — which is itself the thing this
document says voids magnitude claims.

**So: the direction survives and the magnitude does not, which is the standing framing rather than a
strain on it.** The structural difference is robust to the proxy's blindness — Gemma would need
massive undetected duplication to reach Qwen's 13-of-40-at-≤8 — but *"1.39× thinner"* is withdrawn
and no ratio replaces it.

**One collapse count corrected downward.** 90863 was listed among the 2-document features. It has
**2 firings in total**, so each of its 2 records *is* its own document — that is `I-THIN`, not
collapse. Grouping it with the other three overstated the collapse count. **Three genuine collapses,
not four.**

**§7.1 matched the columns on record count; §3.5 rules that support is distinct sources, not record
count. The two rulings never met.** Matching the number did not match the construct — the same
mistake the depth ruling was written to prevent, one level down.

**Direction, and it is conservative for the claim.** Thinner support means less varied evidence,
which pushes rows toward `indeterminate` — the identical failure shape §4.3 documents for short
windows. That **deflates Qwen's surface-form numerator.** So this artifact makes the convergence
*harder* to support, not easier: a skew found on the Qwen column despite thinner support is stronger
evidence, not weaker. **This is the first of the seven axes whose direction favours the conclusion by
disfavouring the data**, and it is stated here so that it is on the record before either tally exists.

**Not fixable, and the unavailable fix is worth naming.** A distinct-source floor — truncating both
columns to matched support — would **drop the four 2-document Qwen features from the denominator**,
which §9 voids outright. Declared divergence is the only available disposition. Recorded as
measured-and-accepted, never repaired.

**Different cause, same surface, and only one is a channel failure.** Qwen's duplicates are genuine
document reuse — the same document at different token positions, which is what top-k over a chunked
corpus *does*. Gemma's repetition (mode 3, idx 7223) was a summarizer emitting one snippet eleven
times. **Only the Gemma one is an instrument defect**; conflating them would credit the Qwen column
with a bug it does not have.

**A stated asymmetry also flips here.** Window censoring (§4.7) is **total but uniform** on Gemma —
every record exactly 256 tokens, 626/626, zero variance — and **partial but variable** on Qwen (≤512,
52% truncated). **Uniform censoring cannot tilt a comparison; variable censoring can.** The axis is
real, but its risk sits on the Qwen side, which is the opposite of how §4.7 reads.

---

## 5. Adjudication protocol

### 5.1 One adjudicator, deliberately

Both columns are adjudicated under one pair of hands. A second adjudicator would introduce
inter-rater variance as a **further unmatched axis**. Where throughput requires a second, agreement
is measured on a **10-row overlap sample** rather than assumed, and reported as a number.

### 5.2 Streaming, not batch

Full records run 25–45k characters per feature; over 40 features that exceeds what can be held at
once. Batch-everything-then-adjudicate would mean classifying early rows **from memory rather than
from text** — a *certain* fidelity loss, traded against the *possible* bias of impressions forming
mid-stream. The possible one is taken.

`§7` forbids computing any **fraction** before every row is adjudicated; it does not forbid
adjudicating before every row is collected. In force:

1. Flat list, **not grouped by bucket**, so the shape is not visible as it accumulates.
2. No count, tally or fraction until every row in a column carries a class.
3. **The deciding quote is recorded per row.** This is load-bearing and is what makes streaming
   acceptable: every call is auditable after the fact, so a bias that crept in is findable rather
   than merely disclaimed.
4. Post-hoc drift check, below.

### 5.3 Drift check — the guarantee that one rule governed both columns

By the end of the second column the adjudicator has ~80 adjudications of experience and their
effective understanding of the class boundaries has hardened. **The first column was therefore
adjudicated by a less-practised adjudicator than the second** — a different effective rule per
column, which is exactly what voids the comparison, and it would be invisible in the output.

Run twice:

- **(a)** after the first column completes, re-read the first five rows classified and report any
  that would flip.
- **(b)** after the second column completes, re-check **every row of the first column** against its
  retained deciding quote under the final understanding.

Retained quotes make (b) cheap: a read of 40 short lines, no re-fetching. **If rows flip, that is
reported and the run stops** — a flip rate is a finding about the protocol, and whether the first
column is re-adjudicated in full is a decision, not a quiet fix. **If nothing flips, that is a
positive result worth stating.**

The column ordering was inverted mid-sprint for throughput. The re-check target inverted with it:
it always targets whichever column went first.

---

## 6. The causal experiments

### 6.1 Two halves, two constructs — declared, not apologised for

- **Sufficiency** — judged generation under steering — is **behavioural**.
- **Necessity** — ΔNLL under ablation — is **representational**: the feature carries information the
  model uses.

Related, but **not a matched pair**, and not presented as one. The necessity half is the **more
robust** of the two: it is judge-free and therefore immune to the concept-string fragility the
sufficiency half inherits in full (§7).

### 6.2 Dosing

Doses are **multiples of each feature's own `maxActApprox`** — {0.5, 1, 2, 4, 8, 16} — not absolute
clamp values. Qwen's Pareto point was an absolute clamp of 80; that number does not transfer. Gemma
`maxActApprox` spans 2115–10717 (~5×) and density spans 2.2e-4 to 2.1e-2 (~100×).

**`maxActApprox` is a sample-max proxy** over Neuronpedia's activation set, **not a corpus max.**
This wording is carried in the artifact's field-level metadata and in the tool UI, not only in prose.

**The "~2.5× maxAct optimum" is scoped down and must not be generalised.** Computing `scale/maxAct`
on Qwen's two hand-picked anchors (9056 at 47.50, 47735 at 40.75) gives ≈2.53× and ≈2.45×. The
seeded n=40 sample shows the **unbiased** Qwen corpus-max distribution is range **3.86–60.50, median
≈13** — both anchors sit near the **95th percentile**, and only 2 of 40 exceed 40.75. So ~2.5× is an
observation about two atypical features, **not a calibrated optimum**; for a median feature the same
absolute scale implies a multiplier ~3× higher. Whether the optimum sits at a fixed *multiple* of
maxAct or a fixed *absolute* activation is **what the dose sweep tests** and must not be assumed in
the calibration. The grid {0.5 … 16} spans both hypotheses — **that is luck, not design.**

### 6.3 Controls are not optional and were never cut

A random-feature control runs at **every dose and in ablation**, with a fixed recorded seed. Without
it neither the steering nor the ablation result is falsifiable, and feature-necessity ablation is
the primary deliverable. Under the pre-authorised trim order the control was **permanently off the
table** — not at any point, under any time pressure.

### 6.4 The ablation instrument was substituted — the full record

**Original protocol:** clamp the feature to 0.0 during generation on generic prompts and compare
against baseline and a random-feature control.

**Why abandoned — empirical, not anticipatory.** Two anchor-test reruns on feature 250 failed **in
mirror image**:

- *Saturated baseline.* A prompt containing "here is a step-by-step guide" produced an already-
  imperative baseline (*"Lay the bike on its side. Take the tire off…"*) and an ablated continuation
  that was, if anything, more explicitly instructional. The prompt's own wording drives imperative
  continuation independently of the feature.
- *Near-zero baseline.* Neutral prompts ("My laptop won't turn on", "The recipe came out too salty")
  removed the saturation but produced first-person past-tense narrative rather than second-person
  advice — **no concept present, so nothing to weaken.**

**The diagnosis is structural.** Behavioural ablation detects weakening only where the concept is
already present *and* not prompt-driven — a measurable middle band. Two draws from opposite tails
establish the band is narrow, and for low-density features it is effectively empty: **idx 12800 at
density 7.8e-4 will essentially never appear in a neutral continuation.** Running the original
design would have produced ~108 cells of uninterpretable data **that reads as a result**.

**Substituted instrument:** ΔNLL under ablation on the feature's **own top-activating text**, where
by construction the feature is doing work, so headroom is guaranteed. No generation, no sampling
variance, no judge.

**Two controls, both required:**

| Control | Question | Why insufficient alone |
|---|---|---|
| **Cross-feature** — a random feature ablated on **F's own** top text | Is the effect specific to F? | **Weak by construction** — an inactive feature ablates to ~nothing, so it is easy to beat. Must be *same-text*, or text difficulty confounds it |
| **Within-feature** — F ablated on text where **F does not fire** | Does the effect track where F is active? | Says nothing about specificity to F |

The within-feature control's text is **empirically verified non-firing via SAE encode**, not assumed
from which pool it came.

**The number is an upper bound and the schema says so.** Selecting on maximal activation means every
quantity is *"on text where F is maximally active"*, never *"on text"* — carried in field names
(`mean_delta_nll_on_max_activating_text`), not only in prose.

**Falsification conditions, pre-registered:** if F's ΔNLL is not meaningfully above the
cross-feature control, the effect is a property of the text; if not above the within-feature
control, it is a global perturbation. **Either outcome is the finding.** Neither is grounds for
changing the instrument again.

**The behavioural arm still runs and is still reported**, under a conditioning rule refined by the
same reruns: cells whose baseline is concept-**saturated** *and* cells whose baseline shows
**near-zero** concept presence are **both** uninformative for ablation, disclosed with their counts,
never silently pooled and never dropped. **The baseline arm resolves this empirically per prompt per
feature**, so no a priori count is required.

---

## 7. Concept-string sensitivity — a named result

A one-word change to the judge template's `target_concept` swings judged relevance by up to **3.7×
/ 6.92 points** on identical generations. This bears on every paper reporting a judged steering
score without publishing its concept string.

**Method.** Identical generation sets verified by text-set hash; identical rubric version verified
by template digest across all six runs; `target_concept` the only variable. A **same-string
replicate** supplies the noise floor — without it, invariance would be an assertion rather than a
measurement.

**Four-tier result:**

1. **Direction is general.** Narrowing depresses at 6/6 scales, broadening lifts, no sign reversal
   in 24 scale-cells across three features spanning a 5.6× range of feature strength.
2. **Magnitude is feature- and pair-specific.** "Up to ~4× on some features", never "by ~4×". Two
   features of near-equal strength (corpus max 47.50 and 40.75) differ **6.2× on the largest cell
   and 13.7× on the mean** — so **feature strength does not predict concept-string sensitivity**,
   and no floor effect is needed to explain a small swing.
3. **Mechanism is referential exclusion, with a usable predictor.** Effect size tracks how much the
   modifier excludes content actually present. The **score ceiling** — max single treated score,
   cheese 10 → 4, UNESCO 9 → 9, Eurovision 9 → 9 — orders all three pairs correctly where feature
   strength does not, and is **measurable in advance from the generations at zero judge cost.** A
   reader can run this check on their own experiment before publishing.
4. **Control stays at the floor — and is not exactly invariant.** Exactly 1.00 across both strings
   and all six scales on two of three features. On the third, the control and **the unhooked
   baseline** both moved (1.00 → 1.12; control cells +0.00 to +0.25, max single score 3, 5 of 56
   generations). **Because the baseline moved, this is a scoring-frame effect of the string itself,
   not an effect of steering or of the control feature.** Within-run repeat spread is exactly 0
   across all 56 control generations, so the noise floor on control cells is 0.00 and +0.25 is real.
   Localised to a single prompt: travel advice, where narrowing to a place type opens a
   rubric-band-4–6 "related domain" penumbra that the bare institution name admitted no partial
   credit for.

**Binding wording: "control stays at the floor", never "control is exactly invariant" — and the
magnitude travels with the hedge every time it appears:** +0.12 to +0.25 against a steered−control
gap of 5–7 points, **~2 % of signal**, with no arm reordering and no sign change in 24 scale-cells.
**Control-relative direction is safe, and it is not a perfect normalisation.** Both halves in one
sentence.

**Reader guidance:** publish the exact concept string with any judged relevance score — **including
for baseline and control arms**, which nobody currently does. The same untouched text scores 1.00 or
1.12 depending on a string that never touched the model, so baseline-relative numbers across two
papers are not comparable even with identical generations and an identical judge.

**Residual, stated plainly:** the third feature was never narrowed on itself, so a floor effect is
not excluded for that individual feature. What *is* excluded is the general claim that feature
strength drives magnitude.

**Concept strings are rule-derived from the adjudicated label and pre-registered before any
judging**, identically for both models, with no hand-tuning.

---

## 8. Declared divergences

Stated up front. Six or more divergences disclosed by the authors is a document that survives
review; the same six found by a reviewer is not.

| # | Divergence |
|---|---|
| 1 | **Out-of-chain execution.** Science runs via `scripts/legacy/`, outside the certification chain — a deliberate trade of provenance for speed, stated openly |
| 2 | **Pin divergence.** `pyproject.toml` pins `transformers==5.12.1` / `accelerate==0.33.0`; the sprint environment has `5.14.1+computecanada` / `1.14.0+computecanada`, and the wheelhouse has no 5.12.1. `pyproject.toml` was **not** edited — it is a frozen governance surface |
| 3 | **`maxActApprox` is a sample-max proxy**, not a corpus max |
| 4 | **Corpus-max vs sample-max construct mismatch.** Qwen's maxima are corpus maxima over 1.7M positions; Gemma's are sample maxima from Neuronpedia. Different constructs |
| 5 | **Dead rates are differently constructed and are never compared.** Qwen's criterion is `characterize_lite` over 5,000 FineWeb docs with our threshold; Neuronpedia uses its own corpus and criterion. Harmonisation would require re-running Neuronpedia's determination over FineWeb — **declined deliberately, and disclosed rather than faked.** The two rates are never printed adjacent |
| 6 | **Two evidence sources.** Qwen: `characterize_lite` examples over 1.7M FineWeb positions. Gemma: Neuronpedia records over its own corpus. Identical adjudication protocol, different evidence sources |
| 7 | **Dose anchors are unrepresentative.** Qwen's are hand-picked 95th-percentile features; calibrate against the seeded n=40 distribution (median ≈13), not against them |
| 8 | **Construct mismatch between the two causal halves** — behavioural sufficiency vs representational necessity (§6.1) |
| 9 | **Qwen evidence is document-initial: 100 %, unmitigated** (§4.6); **census conditioning ~52 % of rows, median 97.7 % of characters processed** (§4.7). Two different things; only the second is partial |
| 10 | **Evidence depth is matched at 16/16 and total context is matched at ~997 vs 1164; symmetry around the trigger is not** (§4.4) |
| 11 | **Selection protocols.** Both columns are now seeded uniform draws. The superseded browsed sample is retired and unquoted |
| 12 | **`rwu04lpb`'s A6 certificate is amber**, from `max_decoder_cosine_p999` alone (§1.1) |

---

## 9. What voids the comparison

- Computing a cross-model difference, delta, ratio or "gap" between the two compositions.
- Reporting the two fractions as commensurable magnitudes, or laying them out so a reader subtracts
  them.
- Adjudicating the two columns under different class definitions, different evidence depths, or
  different effective rules — which §5.3 exists to detect.
- Reviving the superseded browsed sample or its 58 % figure.
- Treating any autointerp label as evidence.
- Using an unmatched denominator: the intervention set (6 features) and the adjudication samples
  (40 / 40) are **different populations answering different questions and must never share a
  denominator.**
- Building any claim on the **opening lines of Qwen evidence** (§4.6).
- **Publishing a composition while any row in that column is still `parked`** (prereg §11.2). A
  parked row is not `indeterminate`, is not dropped, and does not reduce the denominator — an
  unresolved park **voids the tally for its column.** *Live as of 2026-08-08: 2 Qwen and 9 Gemma
  rows are parked, so **both tallies are void right now.** A reader of this section would not have
  known that, which is why it is stated here and not only in the pre-registration.*
- **Reporting the primary tally without the conservative floor beside it** (prereg §11.1). The
  marked-token amendment favours the hypothesis by construction, so the convergence claim binds to
  the floor, **floor-against-floor across both columns**, and both numbers are published — the gap
  between them *is* the measurement of how much the amendment moved things, and suppressing it makes
  the floor unauditable.
- **Comparing the two columns at unequal distinct-source support** without declaring it (§4.11).

---

## 10. Claim limits stated in advance

- **The floor set's 3-semantic / 3-surface balance is n=3 per side.** It supports **per-feature
  reporting only.** If steering and ablation appear to differ across the semantic/surface split, it
  is reported as **suggestive with the n named** — never as a headline, never as a quantitative
  claim about differential behaviour between classes. Three versus three is an anecdote.
- **The two D1.2 negatives are withdrawn**, not restated with a caveat (§2.1).
- **The 9 sweep features' labels were snippet-verified under the contaminated protocol.**
  Contamination biased toward *confirming* labels, so the rejections are safe and **the admissions
  are exposed.** Feature 250 has independent corroboration from outside Neuronpedia — the anchor
  test found its top-12 real-corpus activations all firing on the sentence-final period of
  imperative sentences — and re-verification under the clean protocol confirmed an
  imperative-saturated corpus. **The corroboration is corpus-level, not token-level:** the endpoint
  supplies `maxValue` without per-token positions, so what is confirmed is that the corpus is
  imperative-dense, **not** that the firing sits on the period. A label that fails re-verification
  does **not** invalidate that feature's dose-response curve — the curve is valid whatever the
  feature is called — but it changes what the curve may be claimed to **mean**.

---

## 11. Reporting structure

**Two self-contained results, then convergence.** A side-by-side table with matched rows **asserts a
controlled comparison in its layout**, whatever the prose says, and a `Qwen | Gemma` column pair
invites row-wise subtraction from every reader who skims — and skimming is the default.

- **Part A** — Qwen, readable without any Gemma number, with its own methods, sample frame,
  denominator and figures.
- **Part B** — Gemma, likewise.
- **Part C** — Convergence. Written **only after both land**, stating what the two independently
  found and what that jointly supports.
- **Part D** — Declared divergences (§8).

Binding table rules: no adjacent numeric cells for the two percentages; no delta, ratio or "gap"
column; each denominator and method printed inline or the cell reads **NOT MEASURED**; no magnitude
language; all four bucket counts shown beside any fraction.

**Field names carry the qualifier, not just captions.** A caveat lives in one paragraph of one
document; a column header propagates into every downstream table, notebook and plot legend, and
nobody re-reads it. `qwen_comparison` was renamed `qwen_reference_metadata` and
`depth_fraction_gap_vs_qwen` became `depth_fraction_qwen` for exactly this reason — a field named
"comparison" or "gap" asserts what the framing declines to assert.

---

## 12. Provenance

`results/` and `reports/` are gitignored, so **SHA-256 digests are the only durable identity these
artifacts have.** All are recorded in `project_management/VERIFICATION_LOG.md` under the R6-V5B
hash-binding precedent, verified on both cluster and workstation after transfer by re-hashing rather
than by trusting `rsync`'s exit code.

Two provenance notes that cannot live inside the artifacts they describe:

- **Job 399311 is recorded FAILED and its artifact is sound.** The payload completed, wrote its
  file, and printed unchanged hash-bound digests; the script then died on a stale `ls` of a deleted
  filename under `set -e`. Verified independently: the digest matches what the job itself printed,
  the JSON parses with the full expected structure, byte counts match on both sides. **A truncated
  write could not reproduce the digest.** The epilogue was subsequently fixed so a cosmetic `ls` can
  never flip a sound run to FAILED — correcting only the filename would have left the trap armed for
  the next rename.
- **`example_context_full.json` embeds a field named `vs_gemma_record_range_1269_2847`** carrying a
  78.09 / 21.30 / 0.62 split. **That interval was estimated from three features / ~15 records** and
  is superseded by the byte-exact distribution in §4.4. The file is **not** edited — breaking a
  binding to fix a documentation gap is the wrong trade — and `full_chunk.char_len` on all 1,538
  rows makes recomputation a pure read of the bound artifact.

---

## 13. Repository surfaces deliberately not touched

`pyproject.toml`, `interplab/**`, `scripts/legacy/steering_experiment.py`,
`slurm/launch_*.sh`, `slurm/setup_env.sh`, and `~/interplab-venv` (verified byte-unchanged:
manifest `sha256 d0aa134b…af168d`, 20,443 files, before and after). The sprint's environment is a
separate `~/sprint-venv`; the frozen ED-36 rebuild was never written to.
