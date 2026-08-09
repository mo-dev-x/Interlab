# SPRINT-2026-08 — Feature necessity, cross-model reproduction, and an interactive intervention tool

**Author:** Mohamed El Yazid — IID
**Period:** 2026-08-05 → 2026-08-12
**Status:** all four deliverables complete. Written against `methods_and_limitations_v1.md`, which is
the full methods record and the appendix to this document.

**Reproducibility.** Every number below is regenerable by one command against a hash-bound artifact.
Digests are in §6 and in `project_management/VERIFICATION_LOG.md`.

---

## 1. What was delivered

| # | Deliverable | Due | State |
|---|---|---|---|
| 1 | Feature-necessity ablation | 08-08 | **Complete** — five comparator generations to a clean final run |
| 2 | Additional features (dose sweep) | 08-08 | **Complete** — full grid, zero missing, malformed or duplicate cells |
| 3 | Cross-model reproduction at Qwen scale | 08-08 | **Complete** — both adjudication columns closed at 40/40, zero parked |
| 4 | Interactive steer/ablate tool | 08-12 | **Built and tested**; live cluster run outstanding (§1.4) |

### 1.1 Feature-necessity ablation

The pre-registered design was **generation-based ablation on generic prompts**. It was abandoned
before producing a result, and the reason is itself a finding: two reruns failed in mirror image —
one prompt's baseline was *imperative-saturated* (the concept appeared regardless of the feature),
the others' baselines showed *near-zero* concept presence (there was nothing to weaken). **Generic
prompts are structurally low-powered for this question**, and running the design as specified would
have produced roughly a hundred cells of uninterpretable data that read as a result.

The substituted instrument ablates each feature **on its own top-activating text**, where by
construction it is doing work, and measures **ΔNLL** — a judge-free, higher-powered necessity
metric. The substitution was pre-registered in `necessity_substitution_prereg_v1.md` **before any
ΔNLL existed**, together with both required controls, the upper-bound framing, and a declared
construct mismatch: ΔNLL measures **representational** necessity, while the Qwen arm's judged
generation result measures **behavioural sufficiency.** These are never cross-compared and never
appear in one table.

**Result.** Of nine features, **two clear a comparator that can fail.**

- **Feature 2048 is necessary at its active positions in 16 of 16 snippets — unanimous.** This is the
  strongest single number in the study. It survives a naive Bonferroni correction across all 18
  feature×measure tests. *(Snippets within a feature are not independent, so effective n is below 16;
  the unanimity is the claim, not a p-value.)*
- **Feature 250** is consistent across both measures (14/16).
- **Six features show no reliable separation.** Two have the control's median at or above the
  target's.
- **One feature reverses sign between measures** — see §2.4, where it becomes a result in its own
  right rather than an anomaly.

**The comparator had to be rebuilt five times, and the sequence is reported as part of the result**
(§5.2). Each generation was degenerate for a different reason, and each was caught downstream of
whoever built it.

### 1.2 Additional features — dose sweep

Full factorial: **8 baselines + 9 features × 2 modes × 6 doses × 2 arms × 8 prompts**, run on Gemma 3
12B at layer 31. The grid is rebuilt from the harness's own constants and asserted against a
pre-registered cell count — never inferred from the data, since a grid inferred from the data cannot
detect that data is missing. **Complete: zero missing cells, zero malformed records, zero
duplicates, zero cells outside the grid.**

**Two pre-registered rulings shaped what is reportable, both fixed before the complete data existed:**

- **The ablate arms are replicates, not a dose response.** The clamp value is identically zero on
  every ablate arm; the dose slot exists only for seed derivation. Reporting them as a flat curve
  would be a misreading of the design rather than a finding. Presented as six replicates with their
  dispersion — which yields a **pooled within-arm noise floor of σ = 0.0624**, measured rather than
  assumed.
- **High doses are uninformative by saturation.** At doses 8 and 16 both the target and the
  random-feature control converge to a divergence of ~1.000, meaning the generation shares no
  vocabulary with baseline at all — the signature of degenerate output, not steering. **A control
  that saturates cannot be a control**, and in one case it saturates *before* the target (0.999
  against 0.936 at dose 4), so the refusal gate removes a cell the dose declaration alone would have
  admitted. **35 of 54 dose-cells survive.**

**Result: most steering effects are inside the replicate noise floor.** Reportable contrasts span
**−0.047 to +0.090**, median **+0.0054**, against a floor of **0.0624**. All but one fall inside it.
The exception is 1.44× the floor, one draw of thirty-five, with no multiplicity correction — **it is
not called an effect.**

**What these metrics measure, stated because it is easy to misread:** the sweep records generated
*text*, so every measure is a surface-form distance from the same-prompt baseline. **It measures how
far a clamp moved the output, not whether it moved toward the feature's nominal concept.** This
instrument cannot see the latter at all.

### 1.3 Cross-model reproduction at Qwen scale

Both instruments were characterised against real weights before any record was generated, and both
adjudication columns were closed at **40 of 40 features, zero parked**.

The composition and the reasons it does not resolve a directional question are §3. **The sweep and
the necessity run are themselves the Gemma-at-scale reproduction**; the taxonomy arm was one claim
inside this deliverable and now contributes to the methodological result (§2) rather than a
directional one.

### 1.4 Interactive steer/ablate tool

A Gradio application over the same instruments: feature selection, steer/ablate mode, dose in units
of the feature's own maximum activation, a deterministic random-feature control, and three
side-by-side generations (baseline, target, control). It imports the **unmodified** clamp hook shared
with the sweep and necessity harnesses, so a change there cannot silently alter two committed
results.

**22 tests pass with no GPU.** The example-snippet panel renders real Neuronpedia text for all nine
features, fetched under a gate that verified the source resolves to the **exact** SAE the sweep uses
— a neighbouring SAE's snippets would have looked entirely plausible and been wrong.

**Outstanding: the tool has never been run against real weights.** This is deliberate — it was built
and tested entirely offline — but it means the path the reader will actually interact with is the one
path never executed. §7 states why that is the sprint's remaining risk.

---

## 2. Headline measurements

Four independent stages of the standard SAE-interpretability workflow were measured. **At each one,
a choice the analyst makes silently moves the answer by more than the effect anyone would report from
it.**

| stage | the unstated choice | measured consequence |
|---|---|---|
| **Selection** — which features you look at | browse vs uniform draw | **2.6×** on the surface-form fraction, same SAE |
| **Classification** — what you call them | how strictly a trigger-primacy rule is applied | **50%** of semantic rows change bucket |
| **Judging** — how you score steering | one word in the concept string | **3.7×** on identical generations |
| **Necessity** — how you measure ablation cost | whole-snippet vs active-position ΔNLL | **sign reversal** |

**None of these was found by looking for it.** Every one surfaced as an obstacle while trying to
answer a different question.

### 2.1 Browsing inflates the surface-form fraction by 2.6×

Browsing a feature dashboard and forming an impression is how a great many practitioners assess SAE
composition. **Both methods were run on the same SAE and the gap measured.**

An initial sample of 33 features, chosen while browsing, gave **58% surface-form**. A seeded uniform
draw of 40 over the same feature space gave **22.5%**.

**This is reportable rather than embarrassing only because the rule was fixed first.** It was
pre-registered — before the uniform draw returned — that the uniform figure would be authoritative
and the browsed figure superseded **whichever direction the number moved**. Choosing the headline
after seeing both would have laundered the selection problem one level up, through the choice of
statistic.

**Direct evidence that browsing was the biasing step:** the uniform draw immediately surfaced topical
domains the browsed sample had missed entirely — soil science, chemistry, cookery, job postings,
mechanical components. Two earlier negative claims ("no geography feature", "no concrete physical
object feature") were bounded at n=33 and are **withdrawn, not softened.**

### 2.2 The composition is not rater-stable

Two adjudicators applied the same pre-registered scheme to byte-identical evidence. **In this study —
one scheme, two raters, n = 40 — the rater effect was comparable in magnitude to the effect being
measured: 50% of semantic rows changed bucket under a second rater applying the same rule more
strictly.**

**This is a demonstration, not a general law.** It is an existence proof against the assumption that
such tallies are stable, which is sufficient. It is **not** the claim that feature-taxonomy
adjudication does not work.

**The difference is systematic, not noisy, and it is diagnosable — which is why it matters.** The
eight disagreements run **4–0 on a single axis**: rater 1 assigns *semantic* where rater 2 assigns
*indeterminate*, never the reverse. The mechanism is visible in the evidence: **rater 1 reads
passages; rater 2 reads activation profiles.** On one feature the passages read as a clean semantic
field — interpersonal connection, mindfulness, emotional awareness — while the activation profile
shows 377 tokens at ≥50% of record maximum, about 24 per record, led by function words. **Rater 2 is
applying the pre-registered trigger-primacy rule more strictly, so the smaller margins are plausibly
the more faithful ones** — a disclosure that runs against the more impressive number.

> **Two adjudication methods differing systematically on one axis is the finding.** Agreement
> statistics assume exchangeable raters, and these are not exchangeable, which is why the
> disagreements are 4–0 rather than scattered. **Agreement is reported as a secondary descriptive:
> 14 of 22 (63.6%).** Stratified, it is **66.7%** on rows where the second rater had no prior
> exposure and **57.1%** where they did — the contamination worry runs in the *inverted* direction,
> and the explanation is that the prior-exposure rows are the ones the scheme was actively changing
> under.

### 2.3 Judged steering scores swing 3.7× on one word

Two judge runs over the **identical 104 generations** scored concept relevance **9.50 vs 2.58** at
the same steering scale, differing only in whether the scoring template said *"cheese"* or *"cheese
curds"*.

**The control is what makes this interpretable:** the random-feature arm sits at **exactly 1.00 at
all six scales, with zero movement**, and the same-string replicate noise floor is ≤0.08. The treated
arm swings up to 4.17×. **The effect is roughly 86× the noise floor**, and the direction is
one-signed with no sign flips — so *control-relative direction survives the concept-string choice
even though magnitude does not.*

**Anyone reporting a judged steering score without publishing their concept string inherits this
fragility.**

### 2.4 The necessity measure is not measure-invariant

For one of the nine features, **the whole-snippet measure says the control costs more and the
active-position measure says the target does.** Same data, opposite conclusions, and no principled
ground for preferring one.

**"Necessity" is therefore not one quantity but a family, and which member is reported determines the
sign.** A fifth instance sits one level further down, at the statistic rather than the stage: feature
2048's whole-snippet **mean is −0.023 while its median is +0.0026 and 11 of 16 snippets are
positive** — a single outlier reversing the sign *inside* a band constructed to remove exactly that
distortion.

---

## 3. The directional question, unresolved

The study set out to test whether SAE features skew toward **surface-form** detectors. **They do
not — and no semantic skew is installed in the vacancy.** The measurement does not resolve the
question.

**Two separate tables. They are not a controlled comparison, they are not laid out as one, and no
delta, ratio or gap between them is computed.**

**Result A — Gemma Scope 2, layer 31** *(seeded uniform draw, n=40, evidence depth 16 per feature)*

| bucket | count |
|---|---|
| surface-form | 9 |
| semantic | 14 |
| discourse-register | 3 |
| indeterminate | 7 |
| relational/positional | 7 |
| **denominator** | **40** |

**Result B — Qwen `rwu04lpb`, layer 28** *(seeded uniform draw, n=40, evidence depth 16 per feature)*

| bucket | count |
|---|---|
| surface-form | 7 |
| semantic | 8 |
| discourse-register | 0 |
| indeterminate | 24 |
| relational/positional | 1 |
| **denominator** | **40** |

The five categories do not partition into two fractions, and the surface-form and semantic fractions
**do not sum to one by construction.**

### 3.1 Why Result A does not establish a direction

The second rater adjudicated 22 of the 40 rows. Extrapolating the observed rater effect to the
remaining 18:

| variant | surface-form | semantic |
|---|---|---|
| as adjudicated (adjudicator of record) | 9 | 14 |
| **asymmetric bound** — semantic loss extrapolated at the observed rate, surface-form held | **8.00** | **7.00** |
| **symmetric bound** — observed flip rate applied to both arms | **6.40** | **7.00** |

**Both bounds are published and neither is adopted as the answer. The interval brackets zero.** No
direction is available *regardless of which extrapolation assumption is taken*, and **that
insensitivity is what makes the non-resolution solid rather than an artifact of choosing a bound.**

**Completion would not fix it.** A third rater on the remaining rows produces a third number, not a
resolution: **the limiting factor is rater instability, not sample size.**

### 3.2 Why Result B does not establish a direction

**60% of the Qwen column is `indeterminate`** — the dominant category. That is a finding about the
**Qwen evidence pipeline**, not a comparative claim about the models: the two columns draw evidence
from different sources and their indeterminate rates are no more comparable than their dead-latent
rates. Within the Qwen column, support is measurably concentrated — five features rest on very few
distinct documents, four of them with a single document supplying 11–15 of 16 records. **Thin support
pushes rows toward `indeterminate`, which deflates that column's surface-form count**, so this
artifact makes any skew *harder* to find rather than easier.

### 3.3 What the two columns jointly support

**Both fail to resolve, by independent mechanisms** — Gemma from rater instability, Qwen from
evidence thinness on a different pipeline. **Two instruments independently finding a question
unresolvable at this power is a joint claim**, and it is the one these measurements genuinely
support. It is not a convergent directional finding and is not presented as one.

---

## 4. Instruments and unmatched axes

| Field | Qwen | Gemma |
|---|---|---|
| Model | Qwen2.5-14B-Instruct | `google/gemma-3-12b-pt` |
| SAE | `rwu04lpb/final_400001024` | Gemma Scope 2, `layer_31_width_16k_l0_medium` |
| Hook | `blocks.28.hook_resid_post` | `blocks.31.hook_resid_post` |
| Geometry | `d_in` 5120, `d_sae` 163840, TopK k=100, **32×** | `d_in` 3840, `d_sae` 16384, JumpReLU, **~4.2×** |
| Training | ours, 400M FineWeb tokens | Google |
| Measured L0 | — | **65.61**, against a registry-claimed 60.0 |

**Six unmatched axes**, enumerated in full in the methods appendix: model, SAE architecture,
expansion ratio, training provenance, relative depth (58.3% vs 64.6%), evidence provenance.

**Depth differs by availability, not design.** Layer 28 on both sides was wanted; Gemma Scope 2's
canonical labelled release does not carry layer 28. A reader will ask, and the one-clause answer is a
good one — its absence would read as carelessness rather than constraint.

**Existence and direction only. Never magnitude.** The expansion gap alone (32× against ~4.2×, a
ratio of roughly 7.6) is a plausible alternative explanation for the size of any composition
difference — a narrower dictionary has less capacity and spends more of it on high-frequency surface
forms. The two percentages are **not commensurable** and must never appear in adjacent numeric cells
or under a spanning header.

**Two features in Result A were pre-ruled by name in the pre-registration** rather than derived by an
adjudicator — for a reliability motive ("so the two adjudicators cannot diverge"), bought at a cost
in validity. Both were later independently confirmed on marker evidence. **They are retained in the
primary tally**, because retaining them holds surface-form at its maximum and therefore makes
"surface-form does not lead" *harder* to satisfy; removing them widens the margin, so that is the
sensitivity line, not the headline.

---

## 5. Field notes — failure modes this experiment hit

**These were found while doing the science, not by a designed methods study.** They are reported as
field notes, quantified where measurable. The two quantified findings in §2 carry the methodological
claim; over-reaching on the rest would undercut them.

### 5.1 Evidence-channel failures

Seven distinct failure modes were characterised in the evidence pipeline, including **label
contamination** (fetching snippets and explanations together produced synthesised snippets and
invalidated an entire earlier evidence set), **omission**, **degenerate repetition**, **tie
collapse**, **scaffold drop**, and — the one most likely to fool a careful reader —
**reproducible fabrication**: a malformed result returned *twice, identically*, where reproducibility
was read as evidence about the data and in fact certified only the shared path.

> **Two agreeing pulls through one summarizer are one observation, not two.**

An eighth is a property of the corpus rather than the channel: **46.5% of Gemma records splice
unrelated documents at a seam with no separator.** The operationally relevant figure is much smaller
— **2.4%** of records have such a seam inside the marker's local context — and conflating the two
overstates the damage roughly nineteen-fold. Both numbers are reported, because they answer different
questions.

**The general lesson, which cost the most to learn:** the pre-registration forbids using labels as
evidence, and an adjudicator could have complied perfectly and still produced a corrupted table,
because the corruption was upstream at the data layer and invisible from inside the adjudication.
**A rule at the judgment layer cannot protect against corruption at the data layer.** Every remedy
that worked was a control at the layer where the failure lived.

### 5.2 The comparator was rebuilt five times

| # | Design | Why it failed |
|---|---|---|
| 1 | Generation-based, generic prompts | Structurally low-powered — saturated or empty baselines |
| 2 | Fixed cross/within-feature control | **Bit-exact 0.0 on every record.** Subtracting zero from an inactive feature is an exact no-op; the result was fixed by arithmetic before any weight loaded |
| 3 | Argmax over the full sequence | Selected the **`<bos>` attention-sink feature** on every record — constant index, bit-identical activation |
| 4 | Argmax excluding position 0 | **98.6% one feature.** Raw activation magnitude is not comparable across features, so argmax selects for a feature's scale rather than its relevance — and the *most*-active feature was never the right reading of "an arbitrary active direction" |
| 5 | Matched-strength random sampling | **Clean.** 137 unique indices, 1.4% maximum share |

**Each design was closer to correct and each defect was harder to see.** Defect 2 announced itself
with an implausible constant; defect 4 hid behind entirely plausible variation. **Detection depended
on what the instrument was required to emit, not on what it checked** — defects 4 and 5 were visible
only because reporting the full selection distribution and the realised strength ratio had been made
mandatory.

> **A gate whose verdict is a boolean must also emit the evidence its verdict was computed from.**

**This is the same lesson as §2.2 from the other direction.** The taxonomy arm found that its rater
effect was comparable to the effect it was measuring; the causal arm needed five rebuilds before its
instrument could produce a number that meant anything. **Both are statements about how much of an
interpretability result is determined by instrument construction rather than by the model.**

### 5.3 Governance and provenance

Discipline that materially changed the outcome, recorded because it is transferable:

- **Every parameter was fixed before the counts existed.** Nineteen amendments to the adjudication
  pre-registration, **and not one was made with a tally visible.**
- **Pre-registration prevented outcome-switching at four levels** — the feature (which sample), the
  statistic (which number is authoritative), the denominator (no features dropped), and the row
  (whose call counts on a disagreement, fixed before either set was tallied).
- **One class was added mid-adjudication and its direction was disclosed.** It moves rows *into* the
  semantic bucket, making the original hypothesis *harder* to support — it cannot have been motivated
  by the result it works against. A later amendment ran the other way, favouring the hypothesis, and
  was adopted **only with a published conservative floor that assumes it away.**
- **A mechanical barrier beat every instruction.** Contamination controls that relied on instructions
  not to read something failed repeatedly; controls that removed the information or made the leak
  structurally impossible held. **Five incidents in the tooling, five structural fixes, zero
  bypasses** — including one that blocked the author of the rule and one that blocked the author of
  the tool.
- **Reports are not artifacts.** Several calls existed only in status reports and not in the
  hash-bound ledger, and one report described work the repository shows was never performed. **A call
  not in the ledger did not happen — and neither did a call that appears only in a report.**

---

## 6. Provenance

| Artifact | SHA-256 (first 16) |
|---|---|
| `reports/adjudication_prereg_v1.md` (v1.19 FINAL) | `69e5594cfb7ac5d0` |
| `reports/methods_and_limitations_v1.md` | `ab4989e4f7e743ed` |
| `reports/adjudication_merged.json` | `1e54c1f207dfdfbc` |
| `reports/adjudication_ledger_r1.canonical.json` | `cfe6e58bea04b5bd` |
| `reports/adjudication_ledger_r2.canonical.json` | `ecc544d16dfc6517` |
| `reports/necessity_result_v1.md` | `77ac7c0334fa0995` |
| `reports/necessity_substitution_prereg_v1.md` | `dbf1029e804655f0` |
| `results/gemma3_sweep/records.jsonl` | `1a888a573e8c19de` |
| `scripts/legacy/qwen_max_activating_tokens.json` | `b6bf9710a92a1bce` |

**Composition:** `python scripts/legacy/merge_adjudication.py` — verified byte-identical on re-run.
**Sweep analysis:** `python scripts/legacy/analyze_gemma3_sweep.py` — exit 0 on the complete grid.

**Scope of the certification chain.** The science in this report ran through `scripts/legacy/`,
**outside** the project's certified pipeline. That was a deliberate trade — speed now, provenance
later — and it is stated openly here rather than concealed. The artifacts are hash-bound and the
analyses are reproducible, but they do not carry the certification the governed chain provides.

---

## 7. Remaining risk

**One item, and it is the deliverable a reader will interact with directly.**

The tool has been built and tested entirely offline against mocked paths. **Its live cluster
execution path has never run.** This sprint produced **six distinct bugs that appeared only against
real weights on the cluster and that no local test caught** — device placement, an out-of-memory
failure from two GPU-resident model copies, a raw HTTP read that bypassed the offline flag, a
multimodal wrapper class mismatch, a silently dropped hook name, and a missing no-gradient context.

**There is no reason to assume the tool is the exception.** The run should be scheduled with days of
margin rather than on the deadline, so that one cluster-only failure can be absorbed rather than
becoming the delivery.
