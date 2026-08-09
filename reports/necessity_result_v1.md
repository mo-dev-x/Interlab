# Necessity Result v1 — Delta-NLL under ablation, Gemma 3 12B layer 31

**Data:** `results/gemma3_necessity/necessity_records.jsonl`, five generations of run, all analyzed
in this report and none discarded (§9): **399619** (commit `15704da`, 288/288 records: 144 own-text
cells + 144 within-feature-control candidates, matching the pre-registered dry run exactly) supplies
§4–§7 (target vs. the two zero-guaranteed checks). **400287** and **400297** are the two intervening
failed comparator designs (§3b–§3c). **400342** (§3d–§3f, kept for the record) is the one-sided
matched-strength design that first worked structurally but carried a directional bias. **400377**
(§3g–§3h) is the clean, genuinely two-sided, properly-powered run that supersedes 400342's own
primary analysis. Same harness, same seeds throughout; the target and cross-feature-check numbers
were spot-checked bit-identical across 399619, 400342, and 400377, confirming nothing about the
underlying measurement changed across any of these runs, only the comparator under test. Module-
identity gate and raw-HF equivalence both passed clean on every run (`d_model=3840`, `n_layers=48`,
hook resolved to `blocks.31.hook_resid_post`; cosine similarity 1.00040, relative L2 error 0.0039,
against declared tolerances cosine≥0.999 / rel_l2≤0.01).
`harness_git_sha=9d90ef601822c1cacad0b6aade8a1a265f2b0e39` on every run (the Tamia checkout executing
these jobs had not pulled every fix landed locally since — a provenance gap worth noting, not one
that changes any number here, since the fixes it missed were unrelated to the code paths these jobs
exercised), `harness_git_dirty=true` (disclosed, not blocking).
`checkpoint_hash=sha256:a5c956a5a2146cf0a066d3d0011e8f569c6aab45d86f67b05522ef9277f26db9`
(model config.json + SAE config.json + params.safetensors content hashes) — identical on every run.

**Governing document:** `reports/necessity_substitution_prereg_v1.md`
(`sha256:dbf1029e804655f032a6f831f3d4b766fefc14b75aa1f26ee89dad790e1ebbf2`, 6282 bytes) — re-hashed
before writing this report; matches. Authored before any ΔNLL measurement existed. This report
follows its binding framing exactly; see §1–3 below before reading any number.

No agent analyzed this data before this report. This is the first read of it.

---

## 1. Binding framing (verbatim from the prereg — read this before the numbers)

- **"The number is an upper bound"** (prereg §5): selecting on maximal activation means every
  quantity here is *"on text where F is maximally active,"* never *"on text."* This is why every
  field name below carries `..._on_max_activating_text`. Nothing here estimates the effect of
  ablating F on typical text — only on the text most favorable to detecting an effect.
- **The construct mismatch is declared, not discovered** (prereg §6): this measures
  **representational necessity** (does the feature carry information the model uses, on its own
  best text). The Qwen sufficiency arm measures **behavioural sufficiency** under judged generation
  on generic prompts. These are related but **not a matched pair** — different model, different
  text, different mechanism (ablation vs. steering), different failure modes (this arm is
  judge-free; the sufficiency arm inherits a measured 3.7× judge swing). **This report does not
  cross-compare the two, and contains no table pairing them.** If you are looking for "does Gemma's
  necessity number beat/match Qwen's sufficiency number," that comparison is out of scope by design
  — the prereg forbids it, not this report's author.
- **Falsification, not confirmation, is the goal** (prereg §8): the pre-registered failure modes
  are checked explicitly per feature in §4 below, and where they fire, that is reported as the
  finding — not treated as a reason to re-run or re-instrument.

---

## 2. Headline, stated plainly

Of 9 features, **2 (250, 2048) show a necessity effect clearly separated from zero on both instrument-specificity checks (§3),
consistent across both the whole-snippet and active-position measures, and consistent in sign
across most of their 16 snippets.** The remaining **7 show either no signal distinguishable from
zero, an inconsistent sign between measures, or a mean driven by one or two outlier snippets rather
than a majority effect.** This is not a "mostly positive, some noise" result — for at least one
feature (2500) the effect is flatly absent by every measure used here, and for two more (3500, 4500)
the headline mean is actively misleading on its own (see §5).

**Final (§3b–§3h): the same 2 features (250, 2048) separate from a real, falsifiable comparator** —
a feature confirmed active on the same snippet, matched to the target's own activation strength, not
a mechanically-guaranteed zero — after four successive generations of that comparator's own design
were found degenerate and fixed on real data before the fifth produced a properly-powered, genuinely
two-sided result (§3b–§3g). Under the clean run, 2048's active-position result is now the single
most decisive number in the study (16 of 16 snippets positive); a residual-sensitivity check confirms
this is not an artifact of the comparator's own ratio band (§3h). The other 7 features still show no
reliable separation, with one new, real wrinkle: feature 500 shows a genuine measure-dependent sign
split (control costs more at the whole-snippet measure, target costs more at active positions) that
only became visible once the sample was properly powered — not noise, and not resolved by picking
one measure over the other. Clearing a real, properly-powered comparator is a harder bar than
clearing zero; that the same 2 features are the ones that clear it is the final form of this report's
finding.

**No number below is reported without its check/comparator beside it**, per instruction. Read §3
and §3b–§3h before trusting any single mean.

---

## 3. Why both checks read exactly 0.0 — and why that means they are not controls

**A check that cannot fail is not a control.** Every one of the 144 cross-feature values (both the
whole-snippet and active-position measures) and every one of the 77 *verified* within-feature values
is **bit-exact 0.0** — not "small," identically zero, checked directly against the raw JSONL rather
than assumed from a mean of 0.000. This is not a surprising empirical result; it is the *guaranteed*
consequence of two facts that were both true before the job ran:

1. `attach()`'s ablate hook is a **targeted single-direction edit** (subtract `a · decoder_direction`
   for the one clamped feature), not a full SAE encode-decode replacement of the residual stream.
2. Both conditions ablate a feature that is, by construction or by explicit verification, **already
   inactive (`a = 0`) at every position of the text being ablated**: the cross-feature check's
   feature (idx 8950) never fires above threshold on any of these 144 snippets (inferred from this
   exact-zero result — unlike the within-feature check, this run did not independently record
   8950's own activation, so this is a mechanistic inference, not a directly logged check); the
   within-feature check only proceeds after an explicit `verified_non_firing` check.

Subtracting `0 · direction` is an exact floating-point no-op (`x - 0.0 = x`, bit-for-bit). Given (1)
and (2), **the result was determined before any weight was loaded** — no measurement on real data
could have produced anything but 0.0. That is precisely why neither of these is a **scientific
control**, whatever the code's own field names (`cross_feature_control_idx`,
`mean_delta_nll_cross_feature_control_...`) call them — those field names are not renamed here, since
real data is already committed under them, but this report does not use the word "control" for
either going forward. Both are correctly understood as an **instrument specificity check**: they
confirm the hook is surgical — it touches only the intended feature, and produces zero effect
exactly when and where the ablated feature was already silent. That is a real and useful thing to
have confirmed. It is not evidence about *F*.

**Consequence for §8's two falsification conditions:** because both checks collapse to the *same*
number (0.0) for the *same* mechanistic reason, this dataset cannot separate "not meaningfully above
cross-feature check" from "not meaningfully above within-feature check" — both conditions reduce to
testing the identical thing: "is ΔNLL for F meaningfully above zero?" The two-control design's
intended falsifiability *in both directions* (prereg §4) does not yield two independent readings
here; it yields one, for a mechanistic reason that was knowable in advance. This is reported as a
limitation of pairing this specific ablation mechanism with these two particular checks, not a
reason to weaken either check's definition, and not a reason to trust §4/§7 below any less on their
own terms — they still show 2 of 9 features clearing zero and 7 that do not.

## 3a. The comparator that can fail — first design (superseded, kept for the record)

Zero has no scale. "F's ΔNLL is above zero" says less than "F's ΔNLL is above the cost of removing
*some other* direction that was equally active on the same text." The first design ablated the
single highest-activating non-target feature per snippet via argmax. **This design went through
three real-data failures before it produced a trustworthy number** — recounted in §3b–§3g below,
along with the methodological point that the sequence of failures is itself worth reporting. §4–§7
below (the target vs. the two zero-guaranteed instrument-specificity checks, from job 399619) are
unaffected by any of this and remain unchanged.

## 3b. First failure: the BOS attention-sink (job 400287)

Argmax over the full sequence, every time, selected feature 180 — bit-identically, on all 144
records. Position 0 (`<bos>`) is an attention-sink position with anomalously large activation on a
fixed feature regardless of input content; ablating it is a maximally damaging, content-independent
ablation, which would have set an artificially high bar the target features could almost never clear
and misread as "necessity not demonstrated" when the real problem was the comparator. **Fix:**
exclude position 0 from the max.

## 3c. Second failure: magnitude scale, not relevance (job 400297)

Excluding `<bos>` was not sufficient. Raw-activation argmax over the remaining positions still
selects for a feature's intrinsic activation *scale*, not its relevance to that snippet — one
large-typical-magnitude feature (idx 221) won on 142 of 144 real records regardless of target or
content. "The most-active feature" is the extreme of the activation distribution, not a draw from
it, which was never what "an arbitrary active direction" meant. The gate that shipped with the BOS
fix (`len(set(chosen_idx)) > 1`) passed on this data — 2 unique values (180 had already been fixed
away, but 221 and one other index together still satisfy "more than one") — which is exactly the
failure the gate was meant to catch. **A cardinality check is not a diversity check.** **Fix:**
matched-strength random sampling (`pick_matched_strength_active_nontarget`) — sample uniformly at
random from non-target features whose own max activation on the snippet is within a declared
fraction of the target's own max on that same snippet, seeded per record — replacing the max-share
gate for the cardinality one.

## 3d. Third failure: matched strength, but one-sided (job 400342)

The gate on this run passed decisively: 137 of 144 selections landed on distinct feature indices,
the single most-selected feature accounted for 2.1% of the sample (declared ceiling was 50%), and
zero snippets had an empty eligible set. The selection mechanism itself works — genuine per-snippet
variation, not a fixed feature surviving under a new name.

But the design (`>= 0.5 × target_max`) is a one-sided floor, and the real distribution of the
resulting `active_nontarget_control_strength_match_ratio` (control's own max activation ÷ target's
own max activation, both on the same snippet, n=144) shows why that is not enough:

| statistic | value |
|---|---|
| mean | 0.936 |
| Q1 (25th pct.) | 0.594 |
| **median** | **0.756** |
| Q3 (75th pct.) | 0.990 |
| min | 0.504 |
| max | 5.315 |
| **fraction > 1.0** | **24.3%** (35/144) |

Min/median/max alone — as originally reported when this was flagged — cannot settle which direction
the bias runs; a wide max only shows the comparator is *sometimes* stronger than the target. The
full distribution shows the *typical* case is the opposite: **three-quarters of records draw a
control weaker than the target.** A comparator that is usually weaker ablates less, producing a
smaller control ΔNLL, which makes the target look *more* necessary than a properly strength-matched
comparison would — the opposite bias direction from the fat upper tail that was first flagged. Both
directions are real, in different records; a one-sided `>=` floor does not control either one on its
own.

**Is the target-vs-control difference actually driven by where the ratio falls?** If so, any
apparent "target beats control" reading would be substantially an artifact of the band, not a
property of the target feature. Simple OLS across all 144 records, [ΔNLL(target) − ΔNLL(control)]
against the ratio (no formal significance test was pre-registered for this either):

| measure | slope | r | R² |
|---|---|---|---|
| whole-snippet diff vs. ratio | −0.00056 | −0.054 | 0.003 |
| active-position diff vs. ratio | −0.0686 | −0.145 | 0.021 |
| whole-snippet diff vs. log(ratio) | −0.00127 | −0.085 | 0.007 |
| active-position diff vs. log(ratio) | −0.119 | −0.174 | 0.030 |

Weak, and in the mechanically expected direction (a stronger control shrinks the difference) — this
is reassuring for the headline separations in §3e, but a weak *pooled* correlation across 9
heterogeneous features and 144 snippets can hide feature-specific sensitivity that a single global
regression averages away. §3e's per-feature, band-restricted comparison is the more direct test;
this pooled number is context, not the final word.

## 3e. Primary analysis under job 400342's proxy band (superseded by §3g — kept for the record)

**[0.8, 1.25]** was proposed and declared before it was applied to this data (not fit to the ratio
distribution above after seeing it). Restricting to this band: **39 of 144 records (27%) qualify** —
itself a finding: the one-sided design left most of the sample outside where a genuinely
strength-matched comparison holds, and the shortfall is sharply uneven across features:

| feature | n in-band / 16 |
|---|---|
| 250 | 4 |
| 500 | **1** |
| 2048 | 6 |
| 2500 | 5 |
| 3500 | 6 |
| 4500 | **2** |
| 11000 | 6 |
| 12800 | 6 |
| 900 | 3 |

**Features 500 (n=1) and 4500 (n=2) are too thin to support any per-feature conclusion in the
primary analysis — that is reported as the finding for those two features, not a reason to widen the
band after seeing this.** 900 (n=3) and 250 (n=4) are thin enough that any claim from them is
suggestive, not confident. 2048, 2500, 3500, 11000, 12800 (n=5–6) allow a rough median, not a firm
one.

**Whole-snippet ΔNLL, medians, primary (band) alongside sensitivity arm (full set):**

| feature | n (band) | target median (band) | control median (band) | n (full) | target median (full) | control median (full) |
|---|---|---|---|---|---|---|
| 250 | 4 | +0.00826 | +0.00065 | 16 | +0.00807 | −0.00013 |
| 500 | 1 | −0.00377 | +0.00485 | 16 | +0.00007 | +0.00005 |
| 2048 | 6 | +0.00111 | +0.00060 | 16 | +0.00439 | −0.00045 |
| 2500 | 5 | +0.00011 | −0.00026 | 16 | −0.00015 | −0.00024 |
| 3500 | 6 | −0.00007 | −0.00127 | 16 | +0.00159 | +0.00020 |
| 4500 | 2 | +0.00261 | +0.00097 | 16 | +0.00212 | +0.00167 |
| 11000 | 6 | −0.00084 | −0.00083 | 16 | +0.00044 | −0.00034 |
| 12800 | 6 | +0.00078 | +0.00193 | 16 | +0.00137 | +0.00175 |
| 900 | 3 | +0.00021 | +0.00230 | 16 | +0.00090 | +0.00041 |

**Active-position ΔNLL, medians, same layout:**

| feature | n (band) | target median (band) | control median (band) | n (full) | target median (full) | control median (full) |
|---|---|---|---|---|---|---|
| 250 | 4 | +0.06598 | −0.00407 | 16 | +0.08130 | +0.00191 |
| 500 | 1 | +0.01807 | +0.00000 | 16 | +0.00246 | −0.00002 |
| 2048 | 6 | +0.09082 | −0.00006 | 16 | +0.24365 | +0.00003 |
| 2500 | 5 | +0.00586 | +0.00000 | 16 | +0.00369 | +0.00000 |
| 3500 | 6 | +0.24097 | −0.00781 | 16 | −0.02182 | +0.00000 |
| 4500 | 2 | +0.03693 | +0.00597 | 16 | +0.00940 | −0.00105 |
| 11000 | 6 | −0.01782 | −0.00227 | 16 | +0.00125 | +0.00000 |
| 12800 | 6 | −0.00076 | +0.00006 | 16 | +0.00514 | +0.00144 |
| 900 | 3 | +0.00177 | −0.00098 | 16 | +0.00438 | −0.00263 |

**Reading this per feature, not pooled:**

- **250 and 2048 are the only two features where target clearly and consistently exceeds the control,
  in both the primary (thin-n) and sensitivity populations, at both measures.** 250: target above
  control at both measures in both populations, direction stable despite n=4 in-band. 2048: the
  whole-snippet gap narrows sharply in-band (+0.00111 vs. +0.00060 — much closer than the full set's
  +0.00439 vs. −0.00045), but the active-position gap remains enormous and one-sided in both
  populations (+0.091 vs. −0.00006 in-band; +0.244 vs. +0.00003 full) — the strongest, most
  consistent effect in the set, survives the stricter band specifically at the position-resolved
  measure.
- **The other seven features do not show a reliable separation in the primary analysis.** Several
  band-restricted medians put the control *at or above* the target: 12800 (whole-snippet control
  +0.00193 > target +0.00078), 900 (whole-snippet control +0.00230 > target +0.00021), 11000
  (both medians negative and nearly tied). 3500's active-position band median (+0.241) is the
  opposite sign from its own full-set median (−0.022, itself already flagged in §5 as a single-
  outlier artifact) — six records is enough to flip a sign entirely, which is the thin-band problem
  in miniature. 500 and 4500 have no meaningful band-restricted read at all (n=1, n=2).
- **Net: against a comparator that can fail, the same two features (250, 2048) are the ones that do
  not fail against it, and the rest show no reliable separation once restricted to a genuinely
  strength-matched population.** This is a stronger, more informative result than the original
  "2 of 9 clear zero" headline (§2) — clearing a real, comparably-active alternative is a harder bar
  than clearing a mechanically-guaranteed zero, and for 12800 specifically, the comparator was not
  just uninformative but *larger* than the target on the primary population.

## 3f. Should this be re-run with true two-sided eligibility?

The 39/144 figure in §3e is a **lower-bound proxy**, not the true two-sided-eligible population: it
only counts records whose single random one-sided draw happened to land in-band. It says nothing
about snippets where a *different*, undrawn, one-sided-eligible feature would have landed in-band —
the true two-sided eligible-set size per snippet was never computed at run time, because two-sided
eligibility did not exist in the code when job 400342 ran (added after this analysis,
`pick_matched_strength_active_nontarget(..., strength_band=(0.8, 1.25))`).

**Recommendation: worth firing.** The job completes in minutes, and the per-feature shortfall is
severe enough for at least two features (500, 4500) that a real two-sided draw could plausibly
recover more than this proxy shows for every feature, not only the thin ones — the proxy is a lower
bound precisely because it discards information the one-sided run had access to but didn't use for
this purpose. This recommendation carries real uncertainty, stated plainly rather than assumed away:
if 500's and 4500's *true* two-sided eligible sets are also genuinely tiny — i.e., on those specific
snippets, few features anywhere in the SAE ever land within 25% of the target's own strength — the
re-run will reproduce the same thinness for a structural reason, not a sampling one, and that outcome
would itself answer this section's question rather than motivate a fourth redesign.

**Resolved by §3g: the re-run happened (job 400377), and the uncertainty above did not materialize.**
Every feature retained the full 16/16 two-sided-eligible snippets — 500 and 4500 were not
structurally thin after all; the thinness in §3e was an artifact of the one-sided design's single
random draw, not a property of the SAE's activation structure. §3e is kept above for the record: it
is what a properly-declared-but-honest analysis looks like when the underlying sample is too thin,
and the fact that it turned out to be a sampling artifact rather than a structural one does not make
reporting the thinness at the time wrong.

## 3g. Fifth generation: the clean run (job 400377) — genuinely two-sided, properly powered

The ratio distribution this run actually produced (n=144, all eligible):

| statistic | job 400342 (one-sided) | job 400377 (two-sided band) |
|---|---|---|
| min | 0.504 | 0.801 |
| Q1 | 0.594 | 0.881 |
| **median** | **0.756** | **0.943** |
| Q3 | 0.990 | 1.051 |
| max | 5.315 | 1.248 |
| mean | 0.936 | 0.965 |

Genuinely two-sided this time, medians clustered near 1.0 across all nine features — every feature's
per-feature eligible count is 16/16 (`active_nontarget_control_distribution.json`,
`per_feature_measurability`), all tagged `MEASURABLE`; the pre-declared
`ACTIVE_NONTARGET_MIN_MEASURABLE_N=10` structural-thinness warning did not fire for any feature.

**Per-feature results, paired per-snippet difference [ΔNLL(target) − ΔNLL(control)], medians and
dispersion — not means alone, for exactly the reason §5 already gave for 3500/4500:**

*Whole-snippet:*

| feature | median diff | mean diff | sd | IQR | sign (+/−) |
|---|---|---|---|---|---|
| 250 | **+0.00933** | +0.00816 | 0.00777 | [+0.00232, +0.01116] | 14/2 |
| 500 | **−0.00173** | −0.00360 | 0.00902 | [−0.00348, +0.00064] | 4/12 |
| 2048 | +0.00256 | −0.02289 | 0.09746 | [−0.00147, +0.00639] | 11/5 |
| 2500 | −0.00073 | −0.00027 | 0.00250 | [−0.00213, +0.00141] | 6/10 |
| 3500 | −0.00093 | −0.00424 | 0.01370 | [−0.00421, +0.00289] | 7/9 |
| 4500 | +0.00044 | +0.00108 | 0.00673 | [−0.00487, +0.00639] | 10/6 |
| 11000 | −0.00059 | +0.00053 | 0.00332 | [−0.00131, +0.00185] | 7/9 |
| 12800 | −0.00062 | −0.00285 | 0.01169 | [−0.00201, +0.00529] | 7/9 |
| 900 | +0.00072 | −0.00539 | 0.02568 | [−0.00244, +0.00610] | 9/7 |

*Active-position:*

| feature | median diff | mean diff | sd | IQR | sign (+/−) |
|---|---|---|---|---|---|
| 250 | **+0.08463** | +0.09208 | 0.08789 | [+0.03154, +0.12549] | 14/2 |
| 500 | +0.00223 | +0.00063 | 0.01429 | [+0.00031, +0.01065] | 12/4 |
| 2048 | **+0.25391** | +0.28978 | 0.25302 | [+0.09815, +0.35938] | **16/0** |
| 2500 | +0.00274 | +0.00188 | 0.02610 | [−0.01685, +0.01953] | 9/7 |
| 3500 | −0.02231 | +0.29732 | 0.72729 | [−0.06259, +0.31250] | 6/10 |
| 4500 | +0.00615 | +0.11823 | 0.27890 | [−0.00662, +0.12459] | 10/6 |
| 11000 | +0.00109 | −0.00379 | 0.01826 | [−0.01268, +0.00772] | 9/7 |
| 12800 | −0.00239 | −0.01584 | 0.08160 | [−0.00739, +0.02338] | 7/9 |
| 900 | +0.00902 | +0.01271 | 0.04774 | [−0.02275, +0.05943] | 10/6 |

**Does the 2-of-9 headline hold? Yes — and one new, real wrinkle shows up only now that the sample is
properly powered:**

- **250 and 2048 remain the clear cases, and 2048's active-position result is now the most decisive
  number in the entire study: 16 of 16 snippets show a positive diff**, median +0.254 nats — every
  single snippet, not a majority. 250 is consistent at both measures (14/16 both).
- **2048's own whole-snippet MEAN (−0.023) is the opposite sign from its median (+0.00256) and its
  own majority (11/16 positive)** — a single extreme snippet pulls the mean far net-negative even in
  this clean, properly-banded run. This is the same mean-vs-median trap §5 flagged for 3500/4500,
  showing up in a *different* feature and measure once the underlying data changed — reported here
  rather than treated as resolved just because the band is now clean. Read 2048's whole-snippet
  result from its median and sign-split, not its mean.
- **500 is a genuine, newly-visible split between measures, not noise from a thin sample.** At n=16
  (not the earlier n=1 proxy): whole-snippet diff is *negative* and fairly consistent (median
  −0.00173, 4/16 positive — the control costs *more* than the target on most snippets); active-position
  diff is *positive* and fairly consistent (median +0.00223, 12/16 positive). Properly powered data
  shows this is a real, measure-dependent disagreement for this feature, not an artifact of an
  earlier n=1 read that simply couldn't say anything either way.
- **2500, 3500, 11000, 12800 show no reliable positive separation** — medians at or below zero,
  sign-splits at or past 50/50 against a positive diff, in at least one measure each (3500 and 12800
  in both measures). 3500's active-position mean (+0.297) is again wildly outlier-driven relative to
  its own median (−0.022) and majority sign (6/16 positive) — the same pattern flagged for this
  feature in §5, now confirmed under the clean band rather than an artifact of the earlier biased
  sample.
- **4500 and 900 are weakly, consistently positive at both measures** (10/16 and 9–10/16 respectively)
  but small in magnitude relative to their own dispersion — real direction, not a strong effect.

**Net: the headline does not become fewer — it becomes better-evidenced and more precisely
characterized.** 250 and 2048 are confirmed as the two features with a real necessity effect under a
comparator that can fail and did not, this time, need a thin-sample caveat to say so. The rest remain
without reliable separation, and 500's measure-dependent split is a genuine addition to the record,
not something either extreme (positive or negative) would have shown on its own.

## 3h. The ratio regression, re-run inside the clean band — confirmed, not assumed

§3d's pooled OLS of [ΔNLL(target) − ΔNLL(control)] against the ratio was already weak on job
400342's wide, skewed ratio range (R² 0.003–0.03). With the median now at 0.943 and the full range
compressed to [0.80, 1.25], residual ratio-sensitivity should shrink further if the earlier weak
correlation was genuinely about the ratio and not some other confound. It does:

| measure | job 400342 (ratio 0.50–5.31) | job 400377 (ratio 0.80–1.25) |
|---|---|---|
| whole-snippet r | −0.054 | **0.002** |
| whole-snippet R² | 0.003 | **0.0000** |
| active-position r | −0.145 | **0.012** |
| active-position R² | 0.021 | **0.0001** |

Confirmed, not assumed: the correlation collapses to essentially zero once the ratio itself is
tightly banded, in both measures. This is direct evidence that the §3g separations (250, 2048) are
not an artifact of where in a wide ratio range the comparator happened to land — there is no
meaningful range left for that artifact to hide in.

---

## 4. Per-feature results, with dispersion, checks beside every mean

No formal significance test was pre-registered for "meaningfully above." The heuristic used below —
disclosed, not authoritative — is: mean vs. standard error (`sem = sd/√16`) as a rough
signal-to-noise indicator, plus the **sign split** across the 16 snippets (how many show a positive
vs. negative delta), since a mean can be positive while most snippets are not (see §5).

### 4a. Whole-snippet ΔNLL (`mean_delta_nll_on_max_activating_text`)

| feature | label | density | mean | median | sd | sem | range | sign (+/−) | cross-ctrl |
|---|---|---|---|---|---|---|---|---|---|
| 250 | advisory/instructional imperatives | 0.02136 | +0.00841 | +0.00807 | 0.00817 | 0.00204 | [−0.00644, +0.02441] | 14/2 | **0.0** |
| 500 | company & brand proper nouns | 0.00731 | −0.00052 | +0.00007 | 0.00240 | 0.00060 | [−0.00528, +0.00313] | 8/8 | **0.0** |
| 2048 | date/timestamp components | 0.00224 | +0.00465 | +0.00439 | 0.00355 | 0.00089 | [−0.00078, +0.01215] | 15/1 | **0.0** |
| 2500 | abstract nouns (internal states, moral qualities) | 0.00415 | +0.00008 | −0.00015 | 0.00264 | 0.00066 | [−0.00433, +0.00684] | 7/9 | **0.0** |
| 3500 | staff/personnel in service contexts | 0.00222 | +0.00119 | +0.00159 | 0.00379 | 0.00095 | [−0.00662, +0.00854] | 10/6 | **0.0** |
| 4500 | person names | 0.00750 | +0.00181 | +0.00212 | 0.00514 | 0.00128 | [−0.00577, +0.01660] | 10/6 | **0.0** |
| 11000 | named entities/media titles | 0.00380 | +0.00094 | +0.00044 | 0.00226 | 0.00056 | [−0.00230, +0.00705] | 10/6 | **0.0** |
| 12800 | ordinal numerics in sports reporting | 0.00078 | +0.00167 | +0.00137 | 0.00277 | 0.00069 | [−0.00346, +0.00684] | 10/6 | **0.0** |
| 900* | dynamic action verbs (*low_confidence*) | 0.01290 | +0.00115 | +0.00090 | 0.00425 | 0.00106 | [−0.00534, +0.01080] | 10/6 | **0.0** |

All units are nats/token, mean over the 16 snippets. n=16 per feature throughout.

### 4b. ΔNLL at F's own active positions (`..._at_active_positions`)

| feature | mean | median | sd | sem | range | sign (+/−) | median n_active/snippet | within-ctrl |
|---|---|---|---|---|---|---|---|---|
| 250 | +0.08861 | +0.08130 | 0.08855 | 0.02214 | [−0.05444, +0.26562] | 14/2 | 23 | **0.0** |
| 500 | +0.00454 | +0.00246 | 0.00831 | 0.00208 | [−0.00854, +0.02246] | 13/3 | 5 | **0.0** |
| 2048 | +0.28778 | +0.24365 | 0.25153 | 0.06288 | [−0.02490, +0.85547] | 15/1 | 2 | **0.0** |
| 2500 | −0.00182 | +0.00369 | 0.02700 | 0.00675 | [−0.05200, +0.06006] | 10/6 | 5 | **0.0** |
| 3500 | +0.31635 | **−0.02182** | 0.72037 | 0.18009 | [−0.28711, +2.32812] | 6/10 | 3 | **0.0** |
| 4500 | +0.11857 | +0.00940 | 0.27985 | 0.06996 | [−0.10156, +1.03125] | 9/7 | 3 | **0.0** |
| 11000 | −0.00574 | +0.00125 | 0.02077 | 0.00519 | [−0.06787, +0.01538] | 8/8 | 34 | **0.0** |
| 12800 | −0.01387 | +0.00514 | 0.07639 | 0.01910 | [−0.22266, +0.08496] | 9/7 | 27 | **0.0** |
| 900* | +0.01596 | +0.00438 | 0.03703 | 0.00926 | [−0.04126, +0.08350] | 10/6 | 20 | **0.0** |

`within-ctrl` is the verified within-feature check's ΔNLL (an instrument-specificity check, not a
scientific control -- see §3), whenever at least one candidate passed verification for that feature
(see §6 for how many did, and how unevenly).

**Every check cell in both tables above is 0.0 — see §3 for why that is guaranteed, not a result.**

---

## 5. Where the mean lies: per-feature reads, not a pooled average

Per instruction: a pooled mean across the 9 features would hide exactly this. Reading each row on
its own terms:

- **250 and 2048 are the two features with a clear, cross-measure-consistent, majority-sign effect.**
  250: 14/16 snippets positive at both measures, mean/sem ≈4 at both. 2048: 15/16 positive at both
  measures, mean/sem ≈5 (whole-snippet) and ≈4.6 (active-position) — the single largest active-
  position effect in the set (+0.288 nats mean), despite having the lowest median active-position
  count of any feature (2 tokens/snippet) and the second-lowest density (0.00224). A sparse feature
  with very few active positions per snippet still shows the strongest, most consistent effect —
  when it fires, it appears to matter a great deal locally.
- **2500 shows no signal by either measure.** Whole-snippet: mean≈0, sign split 7/9 (a coin flip).
  Active-position: mean is *negative* (−0.00182), sign split 10/6, sem larger than the mean. There
  is nothing here distinguishable from the (necessarily zero) checks in either direction.
- **3500 and 4500's active-position means are misleading if read alone.** 3500's active-position
  mean (+0.316) is driven almost entirely by one snippet (max +2.328); the **median is negative**
  (−0.022) and **10 of 16 snippets show a negative delta**. 4500 shows the same pattern at smaller
  scale: mean +0.119, median +0.009 (13× smaller), sign split 9/7. Reporting either feature's
  active-position mean without its median and sign split would overstate the effect by an order of
  magnitude.
- **11000 and 12800 disagree between measures.** Both show a weak-to-moderate *positive*
  whole-snippet mean (sem ratio ≈1.7 and ≈2.4 respectively) but a small *negative* mean at active
  positions (11000: dead-split 8/8 sign; 12800: 9/7, sem larger than the mean). The
  more construct-relevant measure — ΔNLL specifically where the feature is active — does not
  confirm the whole-snippet signal for either.
- **500 is weak and measure-dependent**: whole-snippet is a dead-split coin flip (8/8, mean
  essentially 0); active-position shows a small but more sign-consistent positive tilt (13/3),
  magnitude ~0.0045 nats — an order of magnitude smaller than 250 or 2048's active-position effect.
- **900 is weak-positive at both measures** (sign 10/6 both), below the bar cleared by 250 and 2048.
  This feature already carried a `low_confidence` flag in the original feature table — this result
  is consistent with that flag, not a reason to remove it.

---

## 6. Within-feature-control rejection rate, per feature — a result about construction, not noise

67 of 144 candidates (46.5%) failed the `verified_non_firing` check and were never ablated —
rejected, not silently dropped; every rejection is a real record with `rejection_reason`. The
rejection rate is **sharply non-uniform across features**, and the pairing (`WITHIN_FEATURE_CONTROL_OFFSET=1`,
cyclic by feature-table order) shows *why*: rejection depends on how often a target feature happens
to co-fire on a **specific other feature's** top-16 text, not on the target's own density in
isolation.

| target F | draws non-firing candidates from | candidates | rejected | rate | verified |
|---|---|---|---|---|---|
| 250 | 500 | 16 | 10 | 0.625 | 6 |
| 500 | 2048 | 16 | 14 | **0.875** | 2 |
| 2048 | 2500 | 16 | 3 | 0.188 | 13 |
| 2500 | 3500 | 16 | 11 | 0.688 | 5 |
| 3500 | 4500 | 16 | 6 | 0.375 | 10 |
| 4500 | 11000 | 16 | 12 | 0.750 | 4 |
| 11000 | 12800 | 16 | 1 | 0.062 | 15 |
| 12800 | 900 | 16 | 0 | **0.000** | 16 |
| 900 | 250 | 16 | 10 | 0.625 | 6 |

Density alone does not predict this: 12800 has the **lowest** density (0.00078) in the table and the
**lowest** rejection rate (0%) — it essentially never co-fires on 900's top text. 500 has a
mid-range density (0.00731) but the **highest** rejection rate (87.5%) — it co-fires often on
2048's top text specifically. This means the within-feature check's *statistical power* (how many
verified cells it can offer) varies from 2 (500) to 16 (12800) — for 500, 4500, and 250/900, the
within-feature check rests on very few (2–6) verified snippets, and any claim built on those means
should be read as low-n.

---

## 7. Falsification conditions (prereg §8), checked explicitly per feature

Both conditions reduce to the same test here (§3): is ΔNLL for F meaningfully above **zero**
(both checks read 0.0, guaranteed in advance -- see §3)?

| feature | condition 1 (vs. cross-feature ctrl) | condition 2 (vs. within-feature ctrl) |
|---|---|---|
| 250 | **does not fire** — clear, consistent positive effect at both measures | **does not fire** — same evidence, condition 2 asks the identical question here |
| 500 | **fires** at whole-snippet measure (dead-split sign, mean≈0); borderline non-fire at active-position measure (weak, sign 13/3) | same as condition 1 (only 2 verified within-feature cells for this feature — see §6) |
| 2048 | **does not fire** — clear, consistent positive effect at both measures, largest in the set | **does not fire** — same evidence |
| 2500 | **fires** — no signal at either measure, one measure even slightly negative | **fires** — same evidence |
| 3500 | **fires** when judged by median/majority sign (10/16 negative at active positions); ambiguous by mean alone | same as condition 1 |
| 4500 | **fires** by the same logic as 3500 (median 13× smaller than mean, sign near dead-split) | same as condition 1 |
| 11000 | **fires** at the active-position measure (dead-split sign, small negative mean); weak non-fire at whole-snippet measure | same as condition 1 (only 15 verified — one of the better-powered checks, still fires) |
| 12800 | **fires** at the active-position measure (negative mean, sign 9/7); does not clearly fire at whole-snippet measure (sem ratio ≈2.4) | same as condition 1 (16/16 verified — the best-powered within-feature check in the set, and it still fires at active positions) |
| 900 | **does not clearly fire, but weak** — positive at both measures, sign 10/6 both, below the bar cleared by 250/2048; consistent with the pre-existing `low_confidence` flag | same as condition 1 (only 6 verified) |

**Net: condition 1 and/or condition 2 fire, at least partially, for 7 of 9 features.** Only 250 and
2048 clear both falsification conditions cleanly at both measures. This is reported as the finding,
per prereg §8's own instruction that either outcome is the result and neither is grounds to change
the instrument again.

---

## 8. What this report is not

- **Not a comparison to the Qwen sufficiency result.** No number above should be read next to a
  Qwen judged-generation number. Different construct (§1), different model, different text.
- **Not a point estimate of "how necessary is this feature on typical text."** Every number here is
  conditioned on the feature's own top-16 activating snippets — an upper bound by construction
  (prereg §5).
- **Not evidence the ablation hook is broken.** §3 explains why every check reads exactly 0.0 as a
  mechanistic certainty, not a null result to be alarmed by.
- **Not a reason to re-run with a different instrument.** Per prereg §8, both a clean pass and a
  falsification are valid outcomes of this design; this run produced a mix (2 features clear,
  7 do not, unevenly), and that mix is the result.
- **Not a case where the comparator's difficulty was a reason to relax it.** The band ([0.8, 1.25])
  was declared before looking at job 400342's data and was not widened when two features came out
  thin under it (§3e); it was not widened after job 400377 showed every feature measurable, either —
  there was no occasion to.
- **Not a case where thinness turned out to mean what it looked like.** §3e reported 500 and 4500 as
  too thin to conclude anything under job 400342's one-sided-draw proxy. §3g's clean run shows this
  was a sampling artifact of that proxy, not a structural property of the SAE — both statements are
  kept in the record (§3e, §3g) because reporting the thinness honestly, at the time, was correct
  regardless of how it later resolved.

---

## 9. Methodological note: five generations of a comparator, not one clean run

| generation | job | what failed | property violated |
|---|---|---|---|
| 1 | 399619 | `cross_feature_control` / `within_feature_control` degenerate **by construction** — guaranteed to read exactly zero before any weight loaded, because both ablate a feature already inactive on the text (§3) | determinacy — the result was knowable in advance |
| 2 | 400287 | converged on the `<bos>` attention-sink feature, bit-identically, on every record (§3b) | position-independence |
| 3 | 400297 | excluding `<bos>` still selected for activation *magnitude*, not relevance; a cardinality-based gate passed on data still dominated by one feature (§3c) | scale-independence |
| 4 | 400342 | matched-strength selection fixed the magnitude problem but was one-sided, so its typical draw was weaker than the target — the opposite bias from the one that prompted the fix (§3d) | directional symmetry |
| 5 | 400377 | **clean** — genuinely two-sided, every feature properly powered, residual ratio-sensitivity confirmed negligible (§3g–§3h) | — |

Each of the first four failures was a different property of "what makes a control a control," and
each was found only because the actual distribution was checked against a pre-declared bar, not
because the design was re-read more carefully. A single clean run at any of these four stages would
have produced plausible-looking numbers and no indication anything was wrong — generation 4 in
particular looked clean by its own gate (diversity, max-share) while still carrying a real directional
bias only a distributional check caught. The sequence of failures, not the final clean run alone, is
what makes generation 5 (§3g) trustworthy. Reported here as part of the result, not cleaned out of it.

**One connection worth naming across this project's two arms.** The taxonomy/adjudication work
elsewhere in this repo has just concluded that its own rater effect is comparable in size to the
effect it was measuring — a correlational instrument that had to confront the possibility that what
it measured was partly its own measurement process. This comparator's five generations are the same
finding from the causal side: an instrument that has to be rebuilt five times before it can produce a
number that means anything, because the first four numbers it produced were each, in their own way,
a property of the instrument rather than of the thing the instrument was pointed at.
