# Necessity Result v1 — Delta-NLL under ablation, Gemma 3 12B layer 31

**Data:** `results/gemma3_necessity/necessity_records.jsonl`, job 399619, commit `15704da`
(288/288 records: 144 own-text cells + 144 within-feature-control candidates, matching the
pre-registered dry run exactly). Module-identity gate and raw-HF equivalence both passed clean
(`d_model=3840`, `n_layers=48`, hook resolved to `blocks.31.hook_resid_post`; cosine similarity
1.00040, relative L2 error 0.0039, against declared tolerances cosine≥0.999 / rel_l2≤0.01).
`harness_git_sha=9d90ef601822c1cacad0b6aade8a1a265f2b0e39`, `harness_git_dirty=true` (disclosed, not
blocking). `checkpoint_hash=sha256:a5c956a5a2146cf0a066d3d0011e8f569c6aab45d86f67b05522ef9277f26db9`
(model config.json + SAE config.json + params.safetensors content hashes).

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

Of 9 features, **2 (250, 2048) show a necessity effect clearly separated from both controls,
consistent across both the whole-snippet and active-position measures, and consistent in sign
across most of their 16 snippets.** The remaining **7 show either no signal distinguishable from
zero, an inconsistent sign between measures, or a mean driven by one or two outlier snippets rather
than a majority effect.** This is not a "mostly positive, some noise" result — for at least one
feature (2500) the effect is flatly absent by every measure used here, and for two more (3500, 4500)
the headline mean is actively misleading on its own (see §5).

**No number below is reported without its control beside it**, per instruction. Read §3 before
trusting any single mean.

---

## 3. Why both controls read exactly 0.0 — mechanism, not a bug

Every one of the 144 cross-feature-control values (both the whole-snippet and active-position
measures) and every one of the 77 *verified* within-feature-control values is **bit-exact 0.0** —
not "small," identically zero, checked directly against the raw JSONL rather than assumed from a
mean of 0.000. This is the mechanically expected consequence of two facts together, not an
instrumentation failure:

1. `attach()`'s ablate hook is a **targeted single-direction edit** (subtract `a · decoder_direction`
   for the one clamped feature), not a full SAE encode-decode replacement of the residual stream.
2. Both controls ablate a feature that is, by construction or by explicit verification, **already
   inactive (`a = 0`) at every position of the text being ablated**: the cross-feature control's
   feature (idx 8950) never fires above threshold on any of these 144 snippets (inferred from this
   exact-zero result — unlike the within-feature control, this run did not independently record
   8950's own activation, so this is a mechanistic inference, not a directly logged check); the
   within-feature control only proceeds after an explicit `verified_non_firing` check.

Subtracting `0 · direction` is an exact floating-point no-op (`x - 0.0 = x`, bit-for-bit). So both
controls are **necessarily** 0.0 whenever the ablated feature is inactive on that text — this is a
positive confirmation that the hook only perturbs the forward pass when the ablated feature is
actually contributing something, not evidence the hook is silently disabled. The target condition's
nonzero deltas (below) confirm the same hook does change computation when the ablated feature *is*
active.

**Consequence for §8's two falsification conditions:** because both controls collapse to the *same*
number (0.0) for the *same* mechanistic reason, this dataset cannot separate "not meaningfully above
cross-feature control" from "not meaningfully above within-feature control" — both conditions reduce
to the identical question, "is ΔNLL for F meaningfully above zero?" The two-control design's
intended falsifiability *in both directions* (prereg §4) does not yield two independent readings
here; it yields one. This is reported as a limitation of this specific ablation mechanism's
interaction with these two controls, not a reason to weaken either control's definition.

---

## 4. Per-feature results, with dispersion, controls beside every mean

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

`within-ctrl` is the verified within-feature-control's ΔNLL, whenever at least one candidate passed
verification for that feature (see §6 for how many did, and how unevenly).

**Every control cell in both tables above is 0.0 — see §3.**

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
  is nothing here distinguishable from the (zero) controls in either direction.
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
2048's top text specifically. This means the within-feature control's *statistical power* (how many
verified cells it can offer) varies from 2 (500) to 16 (12800) — for 500, 4500, and 250/900, the
within-feature control rests on very few (2–6) verified snippets, and any claim built on those means
should be read as low-n.

---

## 7. Falsification conditions (prereg §8), checked explicitly per feature

Both conditions reduce to the same test here (§3): is ΔNLL for F meaningfully above **zero**
(both controls read 0.0)?

| feature | condition 1 (vs. cross-feature ctrl) | condition 2 (vs. within-feature ctrl) |
|---|---|---|
| 250 | **does not fire** — clear, consistent positive effect at both measures | **does not fire** — same evidence, condition 2 asks the identical question here |
| 500 | **fires** at whole-snippet measure (dead-split sign, mean≈0); borderline non-fire at active-position measure (weak, sign 13/3) | same as condition 1 (only 2 verified within-feature cells for this feature — see §6) |
| 2048 | **does not fire** — clear, consistent positive effect at both measures, largest in the set | **does not fire** — same evidence |
| 2500 | **fires** — no signal at either measure, one measure even slightly negative | **fires** — same evidence |
| 3500 | **fires** when judged by median/majority sign (10/16 negative at active positions); ambiguous by mean alone | same as condition 1 |
| 4500 | **fires** by the same logic as 3500 (median 13× smaller than mean, sign near dead-split) | same as condition 1 |
| 11000 | **fires** at the active-position measure (dead-split sign, small negative mean); weak non-fire at whole-snippet measure | same as condition 1 (only 15 verified — one of the better-powered controls, still fires) |
| 12800 | **fires** at the active-position measure (negative mean, sign 9/7); does not clearly fire at whole-snippet measure (sem ratio ≈2.4) | same as condition 1 (16/16 verified — the best-powered within-feature control in the set, and it still fires at active positions) |
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
- **Not evidence the ablation hook is broken.** §3 explains why every control reads exactly 0.0 as a
  mechanistic certainty, not a null result to be alarmed by.
- **Not a reason to re-run with a different instrument.** Per prereg §8, both a clean pass and a
  falsification are valid outcomes of this design; this run produced a mix (2 features clear,
  7 do not, unevenly), and that mix is the result.
