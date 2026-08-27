# Figure design brief — paste this into Claude Design

*Author: Mohamed El Yazid — IID · 2026-08-25*

This file is **self-contained on purpose**. Every number a figure needs is written out below, so the
designer never has to guess, infer, or read the full consolidated report. If a value you need
is not in this brief, it does not exist in the sources — say so rather than inventing it.

---

## 0. Context block — paste this first

> I am building a scientific poster from a body of mechanistic-interpretability research: sparse
> autoencoders on large language models, run over four months, across three repositories (a science
> repo, a shipped product, and an evaluation/governance platform).
>
> **The poster's thesis is unusual and must not be softened into a normal "we found a thing" poster.**
> The headline result is *negative and methodological*: at four independent stages of the standard
> SAE-interpretability workflow, a choice the analyst makes silently moves the reported answer by
> more than the effect anyone would report from it. The work's value is that it measured this on
> itself, withdrew its own earlier claims when they failed, and kept every correction in the record.
>
> Design accordingly. Do not make the negative results look like failures or footnotes — they are the
> contribution. Do not add optimistic framing, growth arrows, or "impact" language that the data does
> not support.

**Visual register.** Sober, print-first, high contrast, no gradients, no 3-D, no drop shadows, no
decorative icons. Think a good journal figure, not a marketing slide. Colour is meaning-bearing only.

**Palette used in the eight already-generated figures — reuse it exactly for consistency:**

| Role | Hex |
|---|---|
| ink / axes | `#1a1a1a` |
| muted grey (secondary, sources) | `#9aa0a6` |
| the analyst's unstated choice | `#7b8794` |
| the effect / the warning | `#c0392b` |
| confirmed, holds, good | `#1e7b4f` |
| caution, ambiguous | `#b7791f` |
| neutral data blue | `#2c5f8a` |
| governance purple | `#6a4c93` |
| panel wash | `#eceff1` / `#f4f1ea` |

**Typography.** One humanist sans throughout (DejaVu Sans / Source Sans / Inter). Titles bold and
sentence-case. Every figure carries its source Part in 8 pt italic grey, bottom-right.

---

## 1. Hard constraints — these are not style preferences

1. **Gemma and Qwen must NEVER be drawn as adjacent columns of one table or one grouped bar chart.**
   A side-by-side layout asserts a controlled comparison, and the sources explicitly void that
   comparison: the two composition breakdowns do not sum to one, were produced under different
   conditions, and must never be subtracted. Where both models appear, separate them with a visible
   rule, a gap, or two distinct panels, and state the rule in the caption. *The layout is itself the
   methodological point.*
2. **Do not use a log or symlog axis for the control-floor counts (0/480 and 19/480).** A log axis
   makes 19 look like a finding. Linear, against the full N.
3. **Never quote a bare test count.** There are two series — *test cases collected* (583 → 1,040 →
   2,796) and *test modules on disk* (61 → 77 → 102). Always label which.
4. **Figure numbering is already consistent — do NOT renumber.** The corrections spec contains a
   superseded *plan* ("Figure 3's removal shifts 4–11 down by one … do this as the very last step
   before submission") and, above it, the dated *execution record* that supersedes it: regeneration
   was completed 2026-07-26 and **"Figure 3 kept as a zoom companion rather than merged, preserving
   numbering."** The removal never happened, so no renumbering is owed and Figures 1–11 as embedded
   in the flagship are correct. The new figures use a `gen*` prefix with no ordinal, so they do not
   collide with that series either.
5. **Every value must be traceable.** No smoothed curves through two points, no simulated point
   clouds, no illustrative-only numbers presented as data.
6. **Author line is "Mohamed El Yazid — IID".** Not Mila.

---

## 2. Already generated — restyle only, do not re-derive

Twelve figures exist at `reports/pics/generated/`. The last three (gen10–gen12) **replace** the hand-authored FP-1, FP-3 and FP-4; use them instead of the originals, which are not in the export bundle. They are correct and lossless; they are also
plain matplotlib. If the poster needs them restyled, **restyle, do not recompute.** All their input
values are in §4 below.

| File | What it shows | Priority |
|---|---|---|
| `gen01_analyst_displacement.png` | four-stage displacement, 4 stacked panels | **headline** |
| `gen02_comparator_evolution.png` | four generations of a comparator + band collapse | **headline** |
| `gen03_interval_brackets_zero.png` | the cross-model interval containing zero | **headline** |
| `gen04_dose_noise_floor.png` | 35 contrasts vs the σ = 0.0624 floor | high |
| `gen05_feature_2048.png` | the one unambiguous causal win, 16/16 | high |
| `gen06_control_floor.png` | 0/480 and 19/480 | medium |
| `gen07_interlab_growth.png` | two test series + architecture growth | medium |
| `gen08_repo_map.png` | three repositories, one authority rule | medium |
| `gen09_concept_globality_redrawn.png` | cross-lingual Jaccard, both caveats *in the figure* | medium |
| `gen10_pipeline_nine_stage.png` | the nine-stage experimental pipeline | medium |
| `gen11_interlab_architecture.png` | Interlab's twelve subsystems by gate | medium |
| `gen12_provenance_chain.png` | the A1→A11 artifact dependency structure | medium |

---

## 3. Still to generate — four figures, specified

### 3.1 The research-program frame  *(highest value of the remaining five)*

A single horizontal timeline placing this work inside a stated five-year research architecture.

- Five threads, left to right, as overlapping horizontal bands:
  **P1** Identifiability Phase Diagrams via Controlled-Ontology Testbeds — *months 0–12*;
  **P2** Representation-Invariant Units: What Is a Feature, Formally? — *months 9–24*;
  **P3** A Faithfulness Calculus for Mechanistic Explanations — *years 2–3*;
  **P4** Mechanism → Disposition: Predictive Interpretability on Model Organisms — *years 3–5*;
  **P5** Synthesis Thread — *continuous, deliverable only by year 5*.
- **P1 is highlighted; everything else is greyed.** A marker on P1 reads *"this body of work."*
- One callout: *"The four-stage displacement result is an **identifiability** finding in this
  program's own vocabulary — it shows the reported answer is not identified by the data alone."*
- Source: `docs/research_program.md`, Part XIII §2.3.

### 3.2 The two compositions — deliberately NOT side by side

Two **separate** five-segment horizontal bars, Gemma (n = 40) and Qwen (n = 40), with a visible rule
between them and generous vertical separation. Caption, mandatory and on the figure:
*"The fractions do not sum to one by construction. These two bars must never be subtracted from each
other."* See constraint 1. *Source: Part II §3, layout rules Part III §11.*

### 3.3 The defect-class panel

A pure table, no plot. Two columns: **the check that passed** | **why it could not have failed.**
Seven rows, drawn from Part 0 §0.6 of the consolidated report. This is the intellectual spine of the
whole body of work and reads better as clean typography than as a graphic. Set it as a figure so it
gets figure-weight on the poster.

### 3.4 The shipped tool — one annotated screenshot

`sae-concept-lab` is a delivered, operable artifact and has no image anywhere in the corpus. One
annotated screenshot of the running interface: the concept selector, the direction control
(amplify / suppress), the strength control, and the Compare panel showing baseline against modified
for the same prompt. Call out four things: the concept bundle identity, the direction, the strength,
and the two Compare panes. *The seven existing `Figure6_Lodestar/*.png` screenshots are the model to
follow.* Requires a live capture — flag it to the author rather than mocking it up.

---

## 4. The data — every number, so nothing is invented

### 4.1 Four-stage displacement (`gen01`)

| Stage | The unstated choice | Values |
|---|---|---|
| Selection | browse vs seeded uniform draw | surface-form fraction **58.0%** vs **22.5%** → **2.6×**; the 58% is *retired* |
| Classification | strictness of trigger-primacy | **50%** of semantic rows change bucket; at 50% the directional question stops resolving |
| Judging | one word in the concept string | judged score **9.50** vs **2.58** → **3.7×**, on identical generations; control arm invariant at **1.00** |
| Necessity | whole-snippet vs active-position ΔNLL | feature 500: median **−0.00173** (sign 4/12) vs **+0.00223** (sign 12/4) → **sign reversal** |

### 4.2 Comparator evolution (`gen02`)

Four generations, each discarded for a named violated property:
gen 1 BOS attention sink → *determinacy*; gen 2 magnitude-not-relevance → *position-independence*;
gen 3 one-sided band → *scale-independence*; gen 4 clean two-sided band → all four hold.
Ratio band collapses **[0.50, 5.31] → [0.80, 1.25]** (an 11.9× wide band to a 1.6× wide band).
Plot on a log ratio axis with 1.0 marked. Only the first and last bands are recorded — **do not
invent bands for generations 2 and 3.**

### 4.3 Cross-model interval (`gen03`)

Two defensible extrapolations: **8.00 vs 7.00 = +1.00** and **6.40 vs 7.00 = −0.60**. The span
[−0.60, +1.00] contains zero. The limit is rater instability, not sample size.

### 4.4 Dose–response (`gen04`)

**35 of 54** dose-cells survive the pre-registered refusal rule. Surviving contrasts span
**−0.047 to +0.090**, median **+0.0054**. Pooled within-arm replicate noise floor **σ = 0.0624**,
measured. All but one contrast falls inside it; the exception is **1.44×** the floor — one draw of
thirty-five, no multiplicity correction, **not called an effect**.
**The 35 individual values are not tabulated anywhere. Plot the range, the median and the single
exceedance, and say on the figure that the per-point series does not exist.**

### 4.5 Feature 2048 (`gen05`)

| Measure | median | mean | IQR | sign (+/−) |
|---|---|---|---|---|
| active-position | **+0.25391** | +0.28978 | [+0.09815, +0.35938] | **16 / 0** |
| whole-snippet | +0.00256 | **−0.02289** | [−0.00147, +0.00639] | 11 / 5 |

The mean and the median have opposite signs under whole-snippet: a single outlier reverses the sign
*inside* a band built to remove exactly that distortion. Active-position survives Bonferroni over 18
tests.

### 4.6 Cross-lingual overlap (§3.4 redraw)

Top-20 feature overlap, Jaccard: **world_cup 0.66 · quebec 0.62 · poutine 0.51 · couscous 0.38.**
**Both caveats are already drawn into `gen09_concept_globality_redrawn.png`; reuse it rather than
redrawing.** They are: (1) these are *set-level* overlaps of the top-20 features per language — poutine's
0.51 does **not** mean a monosemantic poutine feature exists, and the 16-search negative result sits at a
different unit of analysis, so the two are not in tension; (2) the "globality" ordering is a qualitative
link across four data points, validated against no independent measure of concept prevalence or corpus
frequency. Shared-across-all-four counts: world_cup 13/20, quebec 12/20, poutine 10/20, couscous 4/20.

### 4.7 Control floor (`gen06`)

Gemma-3-12B-it **0 / 480 (0.0%)**. Qwen3.5-27B **19 / 480 (4.0%)**, but only **9 distinct texts**.
On the six-point extent scale the maximum ever reached in the control arm was **1**. Linear axis.

### 4.8 Repository state, measured on disk 2026-08-25 (`gen07`, `gen08`)

| | qwen-sae-interp | sae-concept-lab | lodestar |
|---|---|---|---|
| role | science — sole source of truth | product — derivative, never authoritative | governance — independent judging + audit |
| python modules | 69 (`interplab/`) | 38 | 28 (`lodestar/`) |
| test modules | 102 | 22 | **14** |
| other | 12 subsystems, 15 artifact schemas | branch `84f1320`; `main` at `e3b6fc0` | 118 authored documents; not a git repo at this path |

Growth series: test cases **583 → 1,040 → 2,796**; test modules **61 → 77 → 102**; artifact schemas
**11 → 14 → 15**; subsystems **12 throughout — flat, and
correctly so** (SS13 is a frozen deferral, not a missing piece), at July 2026 → 2026-08-09 → 2026-08-21.

**Lodestar's live test surface is 14 modules.** A naive recursive count returns 469 — that number is
five embedded copies of another repository's tree and must never be used.

### 4.9 Other headline numbers available for callouts

- **0.890 < 0.90** — the cheese ceiling: a complete feature group is structurally impossible on the
  final-pairing corpus. A proof, not an estimate.
- **5.38 / 5.50 at scale 55** — feature 9056 "cheese", judged coherence / concept relevance at the
  selected operating point. Sweep context: scale 40 → coherence 6.50, relevance 2.63; scale 60 →
  coherence 4.50, relevance 7.75. The operating point is a coherence-floor selection, **not** a
  global maximum of either metric.
- **9056 > 47735 > 44189** — three independent measurements agree on one feature-quality ranking.
- **16+ attempts, 2 checkpoints** — no clean poutine feature; corpus coverage, not pipeline
  capability, bounds discoverability.
- **Qwen feature 26943**: observed max activation **25.83**; dictionary decoder-norm ceiling
  **56.61**; shipped amplify doses **28 / 57 / 113**. No coherent-and-steered window exists: ≤57 has
  no visible effect, ≥113 produces token corruption.

---

## 5. What to say if asked for more figures

Three things in this corpus deliberately have **no** figure and should stay that way:

- **Any Gemma-vs-Qwen comparison chart.** See constraint 1.
- **An extended Figure-11 steering curve past scale 150.** The only judging artifacts in that range
  record `judge_model: mock-deterministic-v1` for all 4,914 judgments. Plotting them would mix mock
  placeholders into a real-judge figure.
- **A calibrated dose curve.** No dose in this body of work is calibrated. Every one is an
  engineering default or a measured activation scale. A curve implying calibration would be a claim
  the work does not make.
