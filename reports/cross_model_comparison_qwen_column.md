# Qwen measurement — one of two independently-conducted measurements

> **FRAMING (PM ruling — binding on structure, not only on wording).**
> This is **not** a controlled cross-model comparison, and it must not be presented as one.
> It is **two independently-conducted measurements — on different models, SAE architectures,
> expansion ratios, training provenances, and relative depths — that converge on the same
> qualitative finding.** Convergent evidence from independent setups is a recognised and often
> strong form of inference; this is the same facts and a better argument than "controlled
> comparison with confounds".
>
> **The five unmatched axes.** Four differ **by design**: model, SAE architecture
> (TopK vs JumpReLU), expansion ratio (32× vs ~4.2×), and training provenance. The fifth —
> **relative depth (58 % vs 65 %) — differs by AVAILABILITY, not design: we wanted 28↔28, and
> Gemma Scope 2's canonical labelled release does not carry layer 28.** State the axis and the
> reason in the same breath; a reviewer will ask why depth was not matched, and its absence
> reads as carelessness rather than constraint.
>
> **STRUCTURAL CONSEQUENCE — a side-by-side table with matched rows asserts a controlled
> comparison in its layout, whatever the prose says.** The deliverable is therefore
> **two self-contained results**, each with its own methods, sample frame, denominator and
> figures, followed by a **separately labelled CONVERGENCE section**. **Not a "Qwen | Gemma"
> column pair** — a column pair invites row-wise subtraction from every reader who skims, and
> skimming is the default. This is the same principle as field names travelling further than
> caveats, applied one level up to document structure.

**Purpose:** the **Qwen measurement**, self-contained, with file:line provenance — and the
shared pre-registered definitions (§9) under which the Gemma measurement is conducted
independently.

**Document shape (binding):**

| Part | Contents |
|---|---|
| **A — Qwen measurement** (§1–§5, §10) | Instrument, methods, sample frame, denominator, results, figures. Self-contained; readable without any Gemma number. |
| **B — Gemma measurement** (separate document, Gemma assistant) | Same, self-contained. |
| **C — Convergence** (written only after both land) | States what the two independently found and what that **jointly** supports. Existence and direction only. |
| **D — Declared divergences** (§7.1) | The six, stated up front. |
| **Shared pre-registration** (§9) | Bucket scheme, class definitions, adjudication protocol — identical for both. |

**Assembled:** 2026-08-07, local repository only (no Tamia access, no downloads, no edits
outside this file). Every search over `docs/`, `reports/`, `results/`,
`project_management/` used `grep -rn` with explicit paths, because those trees are
gitignored and the Grep tool silently skips them.

**Rule applied:** empty cells are reported as `NOT FOUND IN REPO`. No value here is
reconstructed, inferred, or filled in from memory.

---

## 0. TWO ANSWERS THE PM NEEDS NOW (do not read past these)

### ✅ ITEM 1 — THE EXACT RUBRIC TEXT SURVIVES. D3 IS NOT BLOCKED.

The verbatim prompt templates for `coherence` and `concept_relevance` exist, versioned and
machine-readable, in every Lodestar `run.json` — **not** as prose that could have drifted.
Full text in §1. **No PM decision is required on this axis; no reconstruction was needed.**
The one thing D3 must control is `{{ target_concept }}`, which is interpolated into the
relevance prompt and is itself a measurement variable (§1.4 — a 6.9-point swing on identical
text).

### 🔴 ITEM 4 — NO QWEN SURFACE-FORM BREAKDOWN EXISTS. THE HEADLINE IS ONE-SIDED.

Exhaustively searched (`grep -rn`, explicit paths, `results/ docs/ reports/
project_management/`). **No domain-class taxonomy, feature-class tally, or surface-form
fraction was ever produced for any Qwen SAE.** Every hit for `surface-form`/`domain skew` is
Gemma/Neuronpedia. The Qwen side has only qualitative per-feature prose
("monosemantic"/"polysemantic") for a handful of hand-picked features — no labels, no
denominator, no sample frame. Detail and consequences in §4. **This needs to reach the PM
before 08-08.**

---

## 0.1 Executive answer to the five questions

| # | Question | Answer |
|---|---|---|
| 1 | Judging rubric | **FOUND, verbatim** — §1 below. Stored as structured `rubrics[]` in every Lodestar `run.json`, not as loose prose. |
| 2 | Qwen SAE identity | **FOUND** — published steering results use **`rwu04lpb/final_400001024`** (instruct SAE, 32×, d_sae 163,840). Sections 1 and 6 are *both* superseded. |
| 3 | Sweep results | **FOUND** — but per-scale coherence/relevance live in `results/lodestar_*/run.json`, **not** in `metrics.json`. `metrics.json` holds only mention rates. |
| 4 | Qwen surface-form fraction | **NOT FOUND IN REPO** — no domain-class taxonomy was ever produced for Qwen features. The headline comparison currently has **only the Gemma side**. |
| 5 | topk-vs-JumpReLU / expansion | **FOUND** — already escalated as `CROSS-MODEL-ARCHITECTURE-CONFOUND`, **but with the wrong Qwen numbers** (see §6). |

---

## 1. THE JUDGING RUBRIC (verbatim)

**Source:** `results/lodestar_montreal_eval/run.json:81847` (`rubrics[]` array);
`coherence` at `:81849`, `concept_relevance` at `:81880`. The same six-rubric suite is
embedded in every `results/lodestar_*/run.json`.
**Judge model:** `claude-sonnet-4-5-20250929` (`run.json` → `judge_model`).
**Referenced from:** `scripts/legacy/montreal_qwen.py:37-42`; `results/FEATURE_EXPERIMENT_LOG.md:1560` (section 16).

### 1.1 `coherence` — version 1.0, ordinal 1–10, `deterministic: false`

> Description: `Grammatical fluency and readability, independent of topic.`

```
You are a rigorous evaluator for a mechanistic-interpretability experiment on
LLM activation steering. You will score ONE piece of model-generated text on a
SINGLE dimension. Judge only what is asked. Be strict and calibrated.

DIMENSION: Coherence (grammatical fluency and readability)
- 10: flawless, fluent, natural prose.
- 7-9: minor awkwardness; fully readable.
- 4-6: degraded grammar or mild repetition; meaning still recoverable.
- 2-3: heavy repetition, broken syntax, or fragmentary.
- 1: gibberish / repeated tokens / no recoverable meaning.
IMPORTANT: Judge coherence ONLY. A perfectly fluent off-topic text scores high.
Do NOT reward or penalize topic.

TEXT TO EVALUATE:
"""{{ generation.text }}"""

Respond with JSON only, no preamble:
{"score": <int 1-10>, "rationale": "<=20 words"}
```

### 1.2 `concept_relevance` — version 1.0, ordinal 1–10, `deterministic: false`

> Description: `How centrally and specifically the output expresses the target concept.`

```
You are a rigorous evaluator for a mechanistic-interpretability experiment on
LLM activation steering. You will score ONE piece of model-generated text on a
SINGLE dimension. Judge only what is asked. Be strict and calibrated.

DIMENSION: Concept relevance to "{{ target_concept }}"
- 10: centrally about {{ target_concept }} with accurate specifics.
- 7-9: clearly about {{ target_concept }} or its defining attributes.
- 4-6: related domain but not {{ target_concept }} specifically.
- 2-3: only tangential association.
- 1: unrelated.
Score relevance ONLY; ignore grammar/fluency.
TEXT: """{{ generation.text }}"""
Respond with JSON only:
{"score": <int 1-10>, "rationale": "<=20 words"}
```

**Shared output schema (both):**
`{"type":"object","properties":{"score":{"type":"integer","minimum":1,"maximum":10},"rationale":{"type":"string"}},"required":["score","rationale"],"additionalProperties":false}`

### 1.3 Other rubrics in the same suite (D3 should decide explicitly whether to run them)

`literal_mention` (binary, `deterministic: true`, alias-driven), plus
`prompt_adherence` and `integration_naturalness`, which appear in the aggregate stats at
`results/lodestar_cheese_curds/corrected_stats.txt`. Six rubrics total per
`results/FEATURE_EXPERIMENT_LOG.md:1567` ("run the full 6-rubric steering suite").

### 1.4 ⚠️ Rubric-templating hazard that will break the comparison if ignored

`concept_relevance` interpolates `{{ target_concept }}` into the prompt, so **the target
string is part of the measurement**. Two runs over the *identical* 104 generations differ
only in that string and produce wildly different scores:

| Run | `target_concept` | concept_relevance @ scale 120 | coherence @ scale 120 |
|---|---|---|---|
| `results/lodestar_cheese_curds/run.json` | `cheese` | **9.50** | 4.88 |
| `results/lodestar_cheese_curds_fine/run.json` | `cheese curds` | **2.58** | 4.75 |

Same text, same judge, same rubric version — a 6.9-point swing from the concept string
alone. **D3 must fix the exact `target_concept` string for Gemma and record it**, or the
cross-model numbers are not comparable.

**Scope, per §10.6c:** 6.9 points is the *largest* swing measured, not a typical one. The same
manipulation on a feature of equal strength (47735) moved the score by at most **1.12 points**.
The hazard is therefore **unbounded in direction but variable in size** — which is why the
string must be fixed and published rather than estimated from this one number.

---

## 2. QWEN SAE IDENTITY

**Which checkpoint the published results actually used:** `rwu04lpb/final_400001024`.
Sections 1 *and* 6 of the log are both superseded — section 1 (`9odeg5hb`, pile-10k) was
superseded by section 6 (`de575ae6`, FineWeb), and both are **base-model** SAEs later
superseded by the **instruct** SAE trained in section 25.

| Axis | Qwen value | Source |
|---|---|---|
| Published checkpoint | `results/sae_checkpoints/rwu04lpb/final_400001024` | `results/FEATURE_EXPERIMENT_LOG.md:2369` |
| Checkpoint hash | `sha256:95db17aa38771e25a9ec6138f96ad857c04b82b26b0f962f5f0b64e86e215ce4` | `results/characterize_lite/rwu04lpb/characterize_lite.json` |
| Base model | `Qwen/Qwen2.5-14B-Instruct` | **`configs/backfill/inputs/rwu04lpb_runner_cfg.json`** (`model_name`) |
| Hook | `blocks.28.hook_resid_post` (layer 28) | runner cfg (`hook_name`); `configs/sae_train_instruct.yaml:14-15` |
| `d_in` | **5120** | runner cfg (`sae.d_in`); `configs/sae_train_instruct.yaml:18` |
| `d_sae` | **163,840** | runner cfg (`sae.d_sae`); `characterize_lite.json`; `configs/sae_train_instruct.yaml:19` |
| Expansion factor | **32×** (163,840 / 5120) | `configs/sae_train_instruct.yaml:19` |
| Architecture | **topk** | runner cfg (`sae.architecture`); `configs/sae_train_instruct.yaml:23` |
| `k` | **100** | runner cfg (`sae.k`); `configs/sae_train_instruct.yaml:24` |
| `sae_lens_version` | **6.44.2** | runner cfg (`sae_lens_version`) |
| Training tokens | **400,000,000** | runner cfg (`training_tokens`); `configs/sae_train_instruct.yaml:34` |
| Dataset | FineWeb subset (`HuggingFaceFW/fineweb`, `CC-MAIN-2013-20` shards) at `/scratch/y/yazid/hf_cache/fineweb_subset` | `configs/sae_train_instruct.yaml:26`; `results/FEATURE_EXPERIMENT_LOG.md:290` |
| Corpus manifest (A1) | `sha256:88740b74…` — 601,369 docs / 400,000,109 tokens, coverage full | `registry/run_card/fb3b861d79dc.json` (cluster A10) |
| Context size | 512 | `configs/sae_train_instruct.yaml:28` |
| dtype / seed | `bfloat16` / 42 | `configs/sae_train_instruct.yaml:57,60` |
| Training wall-clock | 15 h 04 m, SLURM job 357597 | `results/FEATURE_EXPERIMENT_LOG.md:2368` |
| `logger.run_name` | `topk-163840-LR-0.0002-Tokens-4.000e+08` (nested key, not top-level) | runner cfg (`logger.run_name`) |
| **A6 certificate** | **`0a572198764d`, verdict AMBER** — job 383528, L28×32 | `docs/implementation_log.md:154-159`; `registry/sae_certificate/0a572198764d.json` |
| FVU (certified) | **0.010255** (per-metric verdict *green*) | cert `payload.metrics.fvu` |
| CE recovered | **0.98837** (green) | cert `payload.metrics.ce_recovered` |
| Dead fraction | **0.000842** (green) | cert `payload.metrics.dead_fraction` |
| Why AMBER | **`max_decoder_cosine_p999` is the sole amber metric**; fvu / ce_recovered / dead_fraction are each green. Bands are placeholder v1. | cert `payload.per_metric_verdicts`; `docs/implementation_log.md:161-162` |
| Certification slice | 9,999,872 tokens, corpus `sha256:88740b74…` (same FineWeb lineage) | cert `payload.eval_slice`; `docs/implementation_log.md:152` |
| Training-time EV (**superseded telemetry — do not cite as the metric**) | 0.9609 → fvu 0.0391, dead 133 | `docs/implementation_log.md:47` |

### Superseded checkpoints (do **not** use in the table)

| Checkpoint | Why superseded | Source |
|---|---|---|
| `9odeg5hb/166670336` — pile-10k, d_sae 81,920, expansion 16×, topk k=100, 166.67M/200M tokens (~83%) | Wrong corpus (no poutine content); explicitly "Superseded by the FineWeb retrain in section 6" | `results/FEATURE_EXPERIMENT_LOG.md:9-31` (dims at `:20`) |
| `de575ae6/166670336` — FineWeb, 200M tokens, EV 0.998 | Base model, not instruct; superseded by section 25 instruct retrain | `results/FEATURE_EXPERIMENT_LOG.md:290-310` |
| `alhjs2qg/final_400001024` — "v2", layer 28, 32× | Base model; section 24 found base-SAE features do not transfer to instruct geometry | `results/FEATURE_EXPERIMENT_LOG.md:2132` |

---

## 3. QWEN SWEEP RESULTS

### 3.1 `metrics.json` schema — align the Gemma harness to this

**Source:** `results/steering_sweep_instruct/*/metrics.json` (9 files).

```json
{
  "baseline_mention_rate": 0.0,
  "by_scale": {
    "40.0":  { "poutine_mention_rate": 0.125, "random_mention_rate": 0.0 },
    "60.0":  { "poutine_mention_rate": 0.0,   "random_mention_rate": 0.0 }
  }
}
```

**⚠️ `metrics.json` contains NO coherence and NO concept_relevance.** It carries only
keyword mention rates, and the key is literally named `poutine_mention_rate` in *every*
sweep regardless of the actual concept (a poutine-era legacy field). The judged scores live
separately in `results/lodestar_*/run.json`. **The Gemma harness must emit both artifacts**,
or align to the Lodestar `run.json` shape:

- `generations[]`: `id, text, prompt, prompt_id, condition ∈ {baseline, control, steered}, model_name, language, target_concept, steering_config{scale}, seed, metadata{}`
- `judgments[]`: `generation_id, rubric_name, rubric_version, score, rationale, judge_model, repeat_index, raw_response, usage{}, cached, metadata{}`
- `rubrics[]`, `judge_model`

### 3.2 Scale grids actually run (instruct SAE, `rwu04lpb`)

| Sweep dir | Concept | Feature | Scale grid |
|---|---|---|---|
| `steering_sweep_instruct/cheese_curds` | cheese | 9056 | 40, 60, 80, 100, 120, 150 |
| `steering_sweep_instruct/cheese_curds_mid` | cheese | 9056 | 45, 50, 55 |
| `steering_sweep_instruct/unesco_heritage` | UNESCO | 47735 | 40, 60, 80, 100, 120, 150 |
| `steering_sweep_instruct/unesco_mid` | UNESCO World Heritage | 47735 | 85, 90, 95, 105, 110 |
| `steering_sweep_instruct/eurovision` | Eurovision | 44189 | present; per-scale judged values **NOT extracted here** |
| also present | poutine_l16, poutine_l28_64x, poutine_l40_lobster, cheese_l28_64x | — | layer/width variants |

### 3.3 Per-scale judged frontier — cheese, feature 9056 (`target_concept = "cheese"`)

Computed from `results/lodestar_cheese_curds/run.json` + `results/lodestar_cheese_mid/run.json`
(mean over n=24 judgments per cell).

| scale | condition | coherence | concept_relevance |
|---|---|---|---|
| — | baseline | 9.12 | 1.00 |
| 40 | steered | 6.50 | 2.62 |
| 45 | steered | 5.88 | 4.12 |
| 50 | steered | 4.79 | 5.00 |
| 55 | steered | 5.25 | 5.50 |
| 60 | steered | 4.67 | 7.75 |
| 80 | steered | 4.25 | 6.62 |
| 100 | steered | 4.38 | 7.88 |
| 120 | steered | **4.88** | **9.50** |
| 150 | steered | 3.25 | 9.04 |
| 40–150 | control (matched-freq) | 7.38 → 2.75 | **1.00 at every scale** |

The control arm **staying at the floor** across all six scales while the steered arm reaches
9.50 is the cleanest specificity evidence in the Qwen column. *(On this feature the floor is
exactly 1.00; the general claim is "stays at the floor" — see §10.6c(1) and §10.8.)*

### 3.4 Per-scale judged frontier — UNESCO, feature 47735

From `results/lodestar_unesco/run.json` and `results/lodestar_unesco_mid/run.json`.

| scale | coherence (steered) | concept_relevance (steered) |
|---|---|---|
| baseline | 9.00 | 1.00 |
| 40 | 6.12 | 2.12 |
| 60 | 4.08 | 4.38 |
| 80 | 4.50 | 6.62 |
| 85 | 4.75 | 6.75 |
| 90 | 4.21 | 7.62 |
| 95 | 4.38 | 6.00 |
| 100 | 5.33 | **8.12** |
| 120 | 3.38 | 7.50 |
| 150 | 2.00 | 7.38 |

### 3.5 Historical frontier — Montreal feature 10413 (**base-model SAE — do not use**)

`results/FEATURE_EXPERIMENT_LOG.md:1600-1612` reports a 9-scale frontier (50→150) peaking at
scale 80 (coherence 5.875, concept_relevance 3.00). **This is the pre-instruct checkpoint and
the feature later shown to be bilingually entangled** (§7). It is the sweep that
`scripts/legacy/montreal_qwen.py:37-42` refers to. Excluded from the comparison column.

### 3.6 ⚠️ Two aggregation methods disagree

`results/lodestar_cheese_curds/corrected_stats.txt` reports scale-40 coherence **7.29 (valid
n=21, broken 3)**; recomputing the plain mean over all judgments for the steered arm gives
**6.50 (n=24)**. The `corrected_stats.txt` path filters "broken" rows and appears to pool
conditions differently. **D3 must pick one aggregation rule and apply it to both models.**

---

## 4. QWEN SURFACE-FORM FRACTION

# NOT FOUND IN REPO

**This is a real finding, not a search failure.** No domain-class breakdown, feature
taxonomy, or surface-form-vs-semantic tally exists for any Qwen SAE. Searched with explicit
paths across `results/`, `docs/`, `reports/`, `project_management/` for
`surface[- ]form`, `domain class`, `adjudicat`, `feature taxonomy`, `feature class` — the
only hits are Gemma-side or unrelated prose.

What exists on the Qwen side is **not** a class breakdown:

| Artifact | What it actually contains | Source |
|---|---|---|
| Feature survey (top-30, outlier-masked) | Per-feature themes read by hand for the top candidates; no class labels, no denominator | `results/FEATURE_EXPERIMENT_LOG.md:2397-2410` |
| `characterize_lite` | Firing rate / max activation / selectivity for exactly **3** features (9056, 47735, 44189) | `results/characterize_lite/rwu04lpb/characterize_lite.json` |
| `results/features/logit_attribution.json`, `top_feature_examples.json`, `poutine_candidates.json` | Per-feature evidence for selected candidates only | — |

**Consequence for the sprint:** the headline "Gemma layer-31 is 58% surface-form detectors
(19/33)" has **no Qwen counterpart**. As of now the comparison axis is one-sided. Producing
it would require adjudicating a random sample of `rwu04lpb` features against the same class
definitions used for Gemma — work that has not been scoped or run. **The PM needs to know
this before 08-08.**

The Gemma-side class definitions, for reference if that work is commissioned
(`docs/pi_directive_plan_2026_08.md:127-131`): numeric/date/quantitative, lexical/POS,
discourse/register, code, named entities, formatting, action verbs, abstract concepts,
institutional roles — with "surface-form detectors" as the union of the non-semantic classes.

### 4.1 FRAMING CONSTRAINT — how this axis may and may not be rendered

The approved claim is that the surface-form skew **reproduces across two models, two SAE
architectures (TopK vs JumpReLU), two expansion ratios (32× vs ~4.2×), and two training
provenances — EXISTENCE AND DIRECTION ONLY, NOT MAGNITUDE.**

Binding consequences for the table:

- **Do not place the two percentages in adjacent numeric cells.** A shared column header with
  two numbers under it is an implicit claim that the difference is meaningful. It is not:
  the samples differ in frame, denominator, adjudication procedure, and — for Qwen —
  do not exist at all.
- **Do not compute, display, or imply a delta, ratio, or "gap"** between the Gemma and Qwen
  surface-form fractions.
- Render this axis as a **direction/existence statement per model**, with each model's own
  denominator and method printed inline, or leave the Qwen cell explicitly
  `NOT MEASURED` — which is the honest state today.
- Any magnitude language ("more skewed", "twice as", "58% vs X%") is out of scope for the
  approved claim.

Note also that the Gemma denominator is not stable across the sprint's own documents (C2),
and the *experiment* proceeds on a trimmed floor set of six features —
"three surface-form (500, 2048, 4500) + three semantic (250, 2500, 3500), preserving the
skew claim's evidentiary base" (`project_management/COMPLETION_LEDGER.md:25`). That is a
third, smaller frame again, and it is the one the measurements will actually come from.

---

## 5. TOPK-VS-JUMPRELU AND EXPANSION-FACTOR DIFFERENCES

| Axis | Qwen (`rwu04lpb`) | Gemma Scope 2 L31 (as recorded) | Source |
|---|---|---|---|
| Architecture | **topk**, k=100 | **JumpReLU**, per-feature threshold (mean 607, std 657) | `configs/sae_train_instruct.yaml:23-24`; `docs/pi_directive_plan_2026_08.md:176,191` |
| `d_in` | 5120 | 3840 | `configs/sae_train_instruct.yaml:18`; `project_management/COMPLETION_LEDGER.md:12` |
| Dictionary width | 163,840 | 16k | `characterize_lite.json`; `COMPLETION_LEDGER.md:12` |
| Expansion | **32×** | ~4.2× | `configs/sae_train_instruct.yaml:19`; `COMPLETION_LEDGER.md:12` |
| Sparsity control | fixed k=100 per token | learned per-feature threshold | as above |
| Layer depth | 28 of 48 (~58%) | 31 (~65% depth) | `configs/sae_train_instruct.yaml:15`; `docs/pi_directive_plan_2026_08.md:129` |

Already escalated as **`CROSS-MODEL-ARCHITECTURE-CONFOUND` → "Escalated to PM"**
(`project_management/COMPLETION_LEDGER.md:12`): *"Cross-model reproduction at Qwen scale is
**not architecture-matched**. Scientific framing is the PM's call; the measurement proceeds
either way with maxAct-relative dosing."*

Dosing note carried from `docs/pi_directive_plan_2026_08.md:120-123`: Gemma feature density
spans four orders of magnitude, so **a fixed multiple of maxAct will not give comparable
intervention strength across features** — dose must be calibrated per feature. The Qwen
sweeps used absolute scale values (40–150), not maxAct-relative units; **the two columns'
scale axes are therefore not directly comparable without conversion.**

No prose comparing topk vs JumpReLU *reconstruction behaviour* exists beyond the loader note
at `docs/pi_directive_plan_2026_08.md:425`.

---

## 6. ⚠️ CONTRADICTIONS WITH THE GEMMA-SIDE NUMBERS / SPRINT FRAMING

### C0 — Misattribution audit: which published figures cite the wrong width for the instrument

Three checkpoints legitimately carry three widths, so every quoted Qwen number was traced to
its checkpoint. Audited: all of `reports/`, `docs/`, `project_management/` for
`81920` / `expansion_factor 16` / `16×`.

**Result — the published reports are CORRECT.** They attribute 16×/81,920 to `9odeg5hb` and
`de575ae6` (both layer 24) and place `rwu04lpb` at layer 28 / 32×:

| Location | Statement | Verdict |
|---|---|---|
| `reports/internship_report.md:49-50` (and `reports/presentation/internship_report.md:49-50`, `reports/evidence_inventory.md:15-16`) | `9odeg5hb` L24 16× (81,920); `de575ae6` L24 16× (81,920) | ✅ correct — these are the abandoned/base checkpoints |
| `reports/internship_report.md:274` (+ `.html:481`, presentation copy) | Explicitly notes L24 entries are 16× and 32× entries (`alhjs2qg`, `rwu04lpb`) are L28, and carries the unresolved L24/32× search attribution at reduced confidence | ✅ correct, and commendably self-flagged |
| `reports/internship_report.md:488` (+ `.html:766`, presentation copy) | "Doubling the SAE's dictionary size (16× to 32× expansion) did not produce a clean poutine feature" | ✅ correct — a within-Qwen width comparison, not an instrument claim |
| `docs/archive/troubleshooting.md:91` | "your 81,920 features" | ⚠️ generic teaching prose, pre-dates the instrument; not a published figure |

**The single real error is `project_management/COMPLETION_LEDGER.md:12`** — see C1. It is the
only place where 81,920 / 16× is asserted as *"Qwen SAE"* in a cross-model context, i.e. as
the instrument. Everywhere else the width is correctly bound to its checkpoint.

### C1 — The escalated architecture confound cites the WRONG Qwen SAE (highest severity)

`project_management/COMPLETION_LEDGER.md:12` records the Qwen side as
**`d_sae=81920`, expansion 16×**. Those are the dimensions of **`9odeg5hb`** — the
pile-10k, base-model, 83%-trained checkpoint that the log itself marks superseded
(`results/FEATURE_EXPERIMENT_LOG.md:20,31`).

The SAE that produced every published Qwen result is **`rwu04lpb`: `d_sae=163,840`,
expansion 32×** (`characterize_lite.json`; `configs/sae_train_instruct.yaml:19`).

The expansion-ratio gap in the escalation is therefore understated by 2×:
**actual 32× vs ~4.2× (≈7.6:1), not 16× vs 4.2× (≈3.8:1)**. The ledger entry should be
corrected before the PM rules on framing, since the ruling is about how mismatched the
architectures are.

### C2 — Surface-form percentage is inconsistent across Gemma-side sources

- Task brief: **58%**, 19 of **33** adjudicated.
- `docs/pi_directive_plan_2026_08.md:129`: **≈64%**, across **28** distinct features.
- `docs/pi_directive_plan_2026_08.md:315`: **8 of 22** numeric/code/formatting (≈36%) in the coverage sample.
- `project_management/COMPLETION_LEDGER.md:7`: n=**33** adjudicated, 9 admitted, rejection 10/20 = 50%.

### C2 — RESOLVED BY PM RULING. Two populations, never one denominator.

**BINDING SEPARATION.** The skew fraction and the intervention set are different populations
answering different questions and **must never share a denominator, or a table section**:

| Population | Frame | Question it answers |
|---|---|---|
| **Adjudication sample** | **33 Gemma / 40 Qwen** | What fraction of features are surface-form? → **the skew fraction** |
| **Intervention floor set** | **6 Gemma** (3 surface / 3 semantic) | Do steering and ablation behave comparably on surface vs semantic features? → **contributes nothing to the skew fraction** |

The 3-surface/3-semantic balance of the floor set is a *design choice for the intervention
experiment*, not evidence about population composition. Encoding this in structure: the skew
axis and the intervention axis go in **separate table sections with separate headers**.

**PM ruling: the earlier browsed-sample percentage is RETIRED from all forward-facing text.**

- **Do not publish 58 %, 19/33, 64 %, or any figure from the browsed sample.** The number
  appears nowhere in the repository (verified by raw `grep -rn` for `58 ?%`, `19 of 33`,
  `19/33` across all four ignored trees — the only in-repo hits are an unrelated depth
  calculation at `docs/pi_directive_plan_2026_08.md:423` and a circular quotation of this
  report at `COMPLETION_LEDGER.md:25`). It is also one keystroke from misreading:
  `COMPLETION_LEDGER.md:7` already uses **19** for a different quantity — the count of named
  shortlist features (9 admitted + 10 rejected).
- **Do NOT build the n = 33 feature→class table retroactively.** It is superseded; the effort
  belongs on the uniform draw.
- **Methods-note wording, used once, with no number attached:** *"an earlier browsed sample,
  superseded by the uniform draw."*

Both models therefore report from **uniform draws only**, adjudicated under the four-bucket
scheme (§9.1), published as **four counts each** — never as a bare fraction, never as
commensurable percentages (§4.1).

### C3 — The `target_concept` string is an uncontrolled measurement variable

See §1.4: identical generations scored 9.50 vs 2.58 depending on `"cheese"` vs
`"cheese curds"`. If Gemma's harness picks a different granularity of concept string, the
cross-model relevance comparison is invalid regardless of everything else.

### C4 — ARITHMETIC HOLDS FOR TWO FEATURES; THE GENERALISATION DOES NOT. (PM correction, 2026-08-07)

Corpus maxima from `docs/characterize_lite_findings.md`: feature 9056 → **47.5**,
feature 47735 → **40.75**. Judged relevance peaks therefore convert as:

| Feature | Concept | Peak absolute scale | Corpus max | **maxAct-relative dose** |
|---|---|---|---|---|
| 9056 | cheese | 120 | 47.50 | **≈ 2.53×** |
| 47735 | UNESCO | 100 | 40.75 | **≈ 2.45×** |

**⚠️ The earlier reading of this table — "the two Qwen optima converge at ≈2.5× maxAct,
report it as a finding" — is WITHDRAWN by PM ruling.** Engineer 3's seeded n = 40 sample
establishes the unbiased Qwen corpus-max distribution: **range 3.86–60.50, median ≈ 13**, with
only **2 of 40** features exceeding 40.75. Both dose anchors above therefore sit near the
**95th percentile** of the population they would be generalised from.

**Binding restatement:**

> **≈2.5× maxAct is an observation on two hand-picked, atypical (95th-percentile) features, not
> a calibrated optimum. Whether the dose optimum sits at a fixed MULTIPLE of maxAct or a fixed
> ABSOLUTE activation is what the dose sweep tests; it is not assumed here.**

The arithmetic is correct for these two features and is retained as such. What is retired is
the inference from two features to a calibration constant. Any maxAct-relative multiplier used
forward must be calibrated against the **seeded n = 40 distribution** (median ≈ 13), not
against 9056 and 47735 — see divergence 7 in §7.1.

**Luck, not design — stated so no one later claims foresight:** Gemma's dose grid
`{0.5, 1, 2, 4, 8, 16}` spans both the ≈2.5× and the ≈9× hypotheses, so it **brackets either
outcome**. The grid was not chosen for that reason. It is a fortunate property of a grid picked
before this question was posed, and it should be reported as such.

**REQUIRED CAVEAT — the two denominators are different constructs.** Qwen's is a **corpus
max** over 1,712,777 token positions (`characterize_lite`, job 383755). Gemma's
`maxActApprox` is a **sample max** from Neuronpedia's activation-collection set, explicitly
corrected in `docs/pi_directive_plan_2026_08.md:131-137` from "corpus max" to
"sample-max proxy". A 2.5× dose does not mean the same thing on both sides. **Added to the
declared-divergence list** alongside out-of-chain execution and the transformers pin.

### C5 — WITHDRAWN. This was my error; `rwu04lpb` **does** have an A6 certificate.

Certificate `0a572198764d`, verdict **AMBER**, job 383528
(`docs/implementation_log.md:154-159`; `registry/sae_certificate/0a572198764d.json`):
fvu **0.010255**, ce_recovered **0.98837**, dead_fraction **0.000842**, over a
9,999,872-token slice on the same FineWeb corpus lineage.

Two things to carry forward correctly:

1. **Cite the certificate, not the telemetry.** EV 0.9609 (`docs/implementation_log.md:47`)
   is final-training-step telemetry and is superseded by the fresh held-out fp32 certify
   slice. They are different measurements, and `docs/implementation_log.md:161-162` says so
   explicitly.
2. **The verdict is AMBER, not green** — but the amber comes *solely* from
   `max_decoder_cosine_p999`; fvu, ce_recovered and dead_fraction are each individually
   green, and the bands are placeholder v1. State it that way rather than as a blanket
   quality flag.

**Root cause of my error, recorded so it is not repeated:** I concluded "no A6 exists" from a
Grep-tool search over `docs/`, which is gitignored — the tool skips those trees silently and
returns zero matches with no warning. `registry/sae_certificate/0a572198764d.json` had even
appeared in an earlier raw-grep result in this same session and I failed to connect it.
**Rule applied from here: a zero-match Grep result over `docs/`, `reports/`,
`project_management/`, or `results/` is UNPROVEN, never ABSENT — re-run with `grep -rn` and
an explicit path.** Every remaining `NOT FOUND IN REPO` verdict in this document has now been
re-checked with raw `grep -rn`; item 4 (§4) survives that re-check unchanged.

---

## 7.1 DECLARED DIVERGENCES — state all eight up front

*Eight declared divergences stated up front is a document that survives review; eight discovered
by a reviewer is not.* These are **declared**, not defended.

| # | Divergence | What it means |
|---|---|---|
| 1 | **Out-of-chain execution** | Part of the Qwen evidence was produced by `scripts/legacy/` and ad-hoc scripts (`characterize_lite.py`, the steering sweeps) outside the canonical registry-producing chain. No A7/A8/A9 lineage for those results; they are exploratory by construction. |
| 2 | **transformers pin divergence** | Locked `transformers==5.12.1` vs the cluster-installed `5.14.1+computecanada`. The two measurements were not produced under an identical library build. |
| 3 | **`maxActApprox` is a sample-max proxy** | Gemma's dose denominator is the max over Neuronpedia's activation-collection set, **not** over pretraining data — corrected from "corpus max" in `docs/pi_directive_plan_2026_08.md:131-137`. Must be described as a sample-max proxy wherever the dose axis appears. |
| 4 | **Corpus-max vs sample-max construct mismatch** | Qwen's denominator is a **corpus max** over 1,712,777 token positions; Gemma's is a **sample max** (as above). A "2.5× maxAct" dose is therefore not the same physical quantity on the two sides (§C4). |
| 5 | **Differently-constructed dead rates** | Qwen `dead_fraction` comes from the certify slice (9,999,872 tokens, fresh held-out fp32); Gemma's is from its release documentation under a different procedure. **Never print the two adjacent.** |
| 6 | **Two selection protocols** | Qwen features were reached by open-ended survey plus researcher choice; Gemma's by Neuronpedia browsing then a uniform draw. Only the **uniform draws** are authoritative for the skew composition (§9.5); the earlier browsed sample is superseded and unquoted (§C2). |
| 7 | **Dose anchors are hand-picked and unrepresentative** | The Qwen maxAct anchors (9056 → 47.50, 47735 → 40.75) come from **hand-picked** features. Against the seeded n = 40 corpus-max distribution — **range 3.86–60.50, median ≈ 13, only 2/40 above 40.75** — both sit near the **95th percentile**. **Any maxAct-relative multiplier derived from them is not representative; calibrate against the seeded n = 40 distribution instead** (§C4). |
| 8 | **The two halves of the causal result are different constructs** | **Sufficiency** (judged generation under steering) is **BEHAVIOURAL**. **Necessity** (ΔNLL under ablation on top-activating text) is **REPRESENTATIONAL** — the feature carries information the model uses. Related, but **not a matched pair**, and the write-up must not present them as one. **Stated in the same breath, because it is not a weakness: the necessity half is the MORE ROBUST of the two — it is judge-free, and therefore immune to the concept-string fragility (up to 3.7×, §10) that the sufficiency half inherits in full.** See §7.2. |

Depth (58 % vs 65 %) is **not** in this list because it is an axis of the framing, not a
methodological divergence — and it differs **by availability, not design**: layer 28↔28 was
wanted, and Gemma Scope 2's canonical labelled release does not carry layer 28.

## 7.2 DIVERGENCE 8 IN FULL — sufficiency is behavioural, necessity is representational

Full pre-registration: **`reports/necessity_substitution_prereg_v1.md`**, authored 2026-08-07
**before any ΔNLL measurement existed**, on any feature, by any agent.

| Half | Instrument | Construct | Judge? |
|---|---|---|---|
| **Sufficiency** | judged generation under steering | **behavioural** | yes — inherits the §10 concept-string fragility in full |
| **Necessity** | ΔNLL under ablation on the feature's own top-activating text | **representational** — the feature carries information the model uses | **no** |

**Name the mismatch; do not present the two as a matched pair. And say the second half in the
same breath: the necessity arm is now the more robust of the two.** It is judge-free, so it is
immune to the fragility this document measures on the sufficiency side — a one-word concept-string
change swung judged relevance by up to **3.7× / 6.92 points** (§10.2), and no analogous degree of
freedom exists in a ΔNLL readout. The construct mismatch is a **declared scope statement, not an
apology**.

**Why the instrument was substituted — empirical, not anticipatory.** Behavioural ablation on
generic prompts was abandoned after **two anchor reruns on feature 250 failed in mirror image**:
one baseline was **concept-saturated by the prompt's own wording** (an imperative "step-by-step
guide" prompt drives imperative continuation through pathways independent of the feature), and the
other sat at **near-zero concept presence with no headroom to weaken**. **The diagnosis is
structural, not prompt tuning:** behavioural ablation can only detect weakening in a measurable
middle band where the concept is already present *and* not prompt-driven, and two draws from
opposite tails show that band is narrow. At density **7.8e-4** a neutral continuation essentially
cannot contain the concept, so no prompt choice rescues it. The original design would have produced
~108 cells of uninterpretable data **that reads as a result**.

**The behavioural arm still runs and is still reported** — under the pre-registered conditioning
rule: cells whose baseline is concept-**saturated** and cells whose baseline shows **near-zero**
concept presence are *both* reported as **uninformative for ablation**, disclosed with their
counts, never silently pooled and never dropped. **Two measurements of necessity — one direct, one
behavioural — not a replacement.**

**Carried through into field names, not only prose:** every necessity quantity is *"on text where
F is maximally active,"* never *"on text"* — e.g. `mean_delta_nll_on_max_activating_text`. Field
names propagate into every downstream table and plot legend; a caveat lives in one paragraph.

## 7. PROVENANCE CAVEATS TO CARRY INTO THE TABLE

1. The Montreal 10413 frontier (§3.5) is **base-model** and the feature was later found
   bilingual/translation-entangled — `results/FEATURE_EXPERIMENT_LOG.md:1402,1519-1534`.
2. `characterize_lite` is **not** a production A7 certificate — `docs/characterize_lite_findings.md:1-9,53-61`.
3. All steering sweeps here are exploratory: **no production A9, no judged A9′**. The
   preregistered necessity ablation for 9056 has not run — and when it does, it runs under the
   **substituted ΔNLL instrument** (§7.2), which is a *different construct* from the sufficiency
   sweeps quoted here, not a continuation of them.
4. Eurovision 44189 is pre-registered weak (max activation 8.5) — carry only as the
   entanglement case, `docs/characterize_lite_findings.md:34-40`.

---

## 9. PRE-REGISTRATION — nine-class adjudication scheme (BINDING, written before Qwen data lands)

**Status:** written 2026-08-07, **before** the 40-feature `rwu04lpb` adjudication data exists.
Applies identically to both models. Gemma's 58 % was computed under *implicit* definitions;
this section makes them explicit so the Qwen tally is computed under the same rule.

### 9.1 FOUR-BUCKET SCHEME — pre-registered, binding on BOTH models

**PM ruling (overrules the earlier mirroring proposal).** No rule is inherited from the
earlier browsed sample: reconstructing a classification rule from rounded percentages is
itself error-prone, and that sample is pre-registered as **superseded**. There is therefore
nothing to stay consistent with, and **nothing needs re-tallying**. The scheme is defined
cleanly, before the uniform draw is adjudicated.

| Bucket | Numerator? | Denominator? |
|---|---|---|
| **surface-form** | **YES — the numerator** | yes |
| **semantic** | no — **reported alongside** | yes |
| **discourse-register** | **no** | **yes** |
| **indeterminate** | **no** | **yes** |

**`indeterminate` is added deliberately before the data exists.** Without it, a feature whose
snippets do not decide gets silently forced into a bucket — row-level laundering, the same
failure the bucket rules exist to prevent.

> **PRIMARY RESULT IS THE FULL FOUR-WAY COMPOSITION, NOT THE FRACTION.**
> Publish all four counts for each model. A fraction whose denominator contains two
> non-numerator buckets is sensitive to their size; showing the counts makes that visible
> instead of hidden.

*(Historical note, for the record only: the earlier browsed Gemma sample did in effect leave
discourse/register outside both numerators — catching that is what prompted this ruling. It is
not a precedent and is not to be mirrored.)*

### 9.2 The boundary the PM asked for: lexical/POS/n-gram **vs** discourse/register/genre

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

### 9.3 The surface-form vs semantic cut

**SURFACE-FORM** — the feature tracks *how text is written*: orthography, token identity,
morphology, numeric/date form, code syntax, layout/markup. It would substantially survive
translation into meaningless-but-well-formed text of the same shape.

**SEMANTIC** — the feature tracks *what the text is about*: entities, actions, abstract
concepts, institutional roles. It would substantially survive paraphrase into different
surface forms carrying the same meaning.

**Operational test (apply in this order):**
1. *Paraphrase test* — rewrite the snippet with different words, same meaning. Would it still
   fire? **Yes → semantic.**
2. *Form-preserving nonsense test* — keep the shape (digits, casing, syntax, markup) but
   destroy the meaning. Would it still fire? **Yes → surface-form.**
3. Both yes, or both no → **discourse/register** (the third bucket), not a forced choice.

### 9.3b (d) TIE-BREAK WHEN THE TWO AUTOINTERP PASSES DISAGREE — affects ~30 of 40 Gemma rows

> **RULE: SNIPPETS ADJUDICATE. LABELS ARE HYPOTHESES TO TEST, NEVER EVIDENCE.**

This is not a new rule — it is the protocol that already **overturned both labels in 8 of 20
cases** (`docs/pi_directive_plan_2026_08.md:119`). It is made explicit because label quality
demonstrably does not support adjudication: the two passes disagree materially on ~60 % of
checked features (`:310-315`), and `gemini-2.5-flash-lite` returns strings such as
*"dare I say"*, *"this arena"*, *"keyboard, Lens"*, *"seeking"* — which are token dumps, not
classifications.

Procedure when the two passes imply different classes:

1. **Ignore both labels.** Read the top-activating snippets and apply §9.3's ordered test.
2. Use the labels only afterwards, as *hypotheses to check against the snippets* — never as a
   tiebreaker, and never as the deciding evidence.
3. **A label never decides a class.** If the snippets are genuinely insufficient to decide, the
   class is **`indeterminate`** — **never the label's guess**. Disagreement between passes is
   itself weak evidence that the feature is hard, but it is not evidence *for* any class.

### 9.3c HARD-CASE RULING — semantic domain, orthographic trigger

Two Gemma rows turn on this, and several others will: **idx 9115** fires on the substring
`"drum"`; **idx 5094** fires on words beginning with `"V"`.

**RULING: both are SURFACE-FORM (class 2, lexical/POS/n-gram).** Recorded here so neither
adjudicator re-derives it.

**Why**, by §9.3's ordered procedure — the order is what decides it:

1. **Paraphrase test first.** Rewrite the snippet with different words, same meaning:
   *drum → percussion instrument*; a V-word → a synonym starting with another letter. The
   trigger string disappears and the feature would **not** fire. **Fails the semantic test.**
2. **Form-preserving nonsense test.** Preserve the orthography, destroy the meaning:
   *conundrum*, *eardrum*, an invented V-word. The trigger string survives and the feature
   **would** fire. **Passes the surface-form test.**

The apparent semantic domain (percussion; nothing coherent for "V") is an **artifact of which
words happen to contain the string**, not the thing the feature tracks. A feature that
survives destruction of meaning but not preservation of meaning is tracking form.

**The one diagnostic that would overturn this** — apply it before accepting the ruling on any
similar row: check whether the snippets contain a *semantically unrelated* word carrying the
same string (*conundrum*, *eardrum*). If such a word **is** present and the feature fires →
surface-form, confirmed. If the snippets contain **only** semantically coherent uses and no
counterexample appears in the top-5, the orthographic reading is **unproven**: record
`indeterminate` rather than guessing either way. Generalise as: *semantic domain +
orthographic trigger → surface-form, unless the top-5 contain no orthographic counterexample,
in which case → indeterminate.*

### 9.4 The nine classes

**Surface-form bucket**
1. **numeric/date/quantitative** — digits, dates, timestamps, measurements, ordinals; the numeric *form* is the trigger.
2. **lexical/POS/n-gram** — a specific token, morpheme, POS category, or fixed collocation (§9.2).
3. **code** — programming syntax, identifiers, markup, structured-data literals.
4. **formatting** — layout and typography: bullets, headers, delimiters, whitespace/punctuation structure.

**Semantic bucket**
5. **named entities** — specific people, places, organisations, works, brands.
6. **action verbs** — dynamic events/processes as *meaning*, not as verb morphology (if morphology drives it → class 2).
7. **abstract concepts** — internal states, moral/evaluative qualities, non-perceptual notions.
8. **institutional roles** — occupational or organisational positions ("staff", "personnel", office-holders).

**In denominator, in neither numerator**
9. **discourse-register** (genre) — communicative function, stance, or text-type (§9.2).
10. **indeterminate** — the top-5 snippets do not decide. **Required disposition, not a
    failure**: use it whenever the evidence is insufficient, when the two autointerp passes
    disagree and the snippets do not resolve it (§9.3b), or when a semantic-domain /
    orthographic-trigger row has no counterexample in the top-5 (§9.3c). Never force a row
    into a bucket to avoid using this.

### 9.5 Adjudication protocol (identical both models)

- **Evidence:** top-activating snippets only. **Autointerp labels are not evidence** — `docs/pi_directive_plan_2026_08.md:310-315` records the two passes disagreeing on ~60 % of checked features.
- **EVIDENCE DEPTH IS MATCHED AT 16/16, pre-registered before any counts.** Binding text lives in `reports/adjudication_prereg_v1.md` §7.1 (amended copy, sha256 `b64a74a18a47…855eb2ab`, superseding `40e40b98…`); this is the summary, and **§7.1 governs on any difference**:
  - **PRIMARY — 16 examples per feature, both columns. This carries the claim.** Gemma: Neuronpedia's top **16** (5 had been collected). Qwen: Engineer 3's 25 truncated to **16 by plain slice, no re-sort**.
  - **Rationale:** a 5-vs-25 depth gap would push a *directional artifact* into the primary number — the shallower column accumulates `indeterminate` purely from having looked less. Matching the depth removes it.
  - **SENSITIVITY — Qwen at the full 25**, depth-robustness check only. **Never compared to Gemma.**
  - **Revision history — publish all three moves, not just the endpoint: `5 → 16 → 20 → 16`.** Every move was evidence-driven and **no counts existed at any point**, so none is outcome-switching; a reader seeing only the endpoint cannot verify that, so the sequence is disclosed. (1) 5 → 16: match depth across columns. (2) 16 → 20: a corrected reading put Neuronpedia's pool at 20. (3) **20 → 16, binding:** the pool figure proved unverifiable — the fetcher truncates large documents at a varying point, returning 15/16/19/20 for the same cached JSON. Two internal contradictions prove tool failure rather than real variation (idx **2848** reported 16 entries while citing a 20-object ID span `…411f5`–`…41208`; idx **13848** returned the same terminal element, `maxValue` 1086.5598, at both position 19 and position 16). **Truncation can only undercount**, so one reading of ≥16 proves the pool is ≥16 — **16 is measured, 20 is aspirational**, and idx **7623** reads 19 with position 20 absent, which a 20-cap would silently fall short of.
  - **Top-k construct CONFIRMED on both sides — this axis needs no disclosure.** Gemma: `maxValues` descend strictly in array order with no band structure across features spanning three orders of magnitude in density, and SAEDashboard's `binMin`/`binMax`/`binContains` are the sentinel `-1` on every entry checked (idx **11270** is decisive — at density 1.5e-6 a stratified sampler would have to reach into low bands and the descent stays smooth, 2132 → 1649). Qwen: verified across all 40 features, zero exceptions (`characterize_lite.py:192`, `reverse=True`). **Matched counts are therefore matched construct** — the invisible confound this ruling existed to close is closed.
  - **Ties exist on both sides, so the no-re-sort rule is not Qwen-specific.** Gemma idx **3648** holds three records at exactly 1155.9937, idx **7623** two at 4587.2803. Take the first *n* in array order; re-sorting would desynchronise the primary and sensitivity arms for reasons unrelated to depth.
  - **Low-support twins:** Gemma **8667** (2 records) and Qwen **90863** (2 firings) — **in the denominator, `indeterminate` if their snippets do not decide, support count disclosed. No minimum-support threshold.**
  - Where this section says "top-5", read "top-16 primary / top-25 sensitivity" — §9.3c's counterexample diagnostic applies over the **primary 16**.
- **Sampling:** seeded-random draws, seed recorded. **Qwen n = 40; Gemma n = 40** — the Gemma uniform draw is collected at 40/40. *(The figure **33** belongs to the superseded browsed sample and is not a draw size under this protocol; see §C2. Do not use 33 as a denominator.)* **No hand-picking, no substitution of a feature because it is uninformative.**
- **One label per feature.** Ambiguous → the *dominant* class across snippets; if genuinely split, class 9.
- **Low-confidence features stay in the denominator**, flagged, never dropped.
- **Blind to the hypothesis:** adjudicate before computing any fraction.
- **Record per feature:** id, assigned class, bucket, confidence, and the snippet evidence that decided it — so the tally is auditable rather than a bare percentage. This is exactly what the Gemma side currently lacks (§C2).

### 9.6 What voids the comparison

Any of: a bucket rule differing from §9.1 on either model; autointerp labels used as evidence
rather than hypotheses (§9.3b); hand-picked samples; features dropped from the denominator;
`indeterminate` avoided by forcing rows into a bucket; publishing a bare fraction instead of
the four-way composition; or reviving the superseded browsed-sample number (§C2).
**And regardless of outcome: existence and direction only, never magnitude (§4.1).**

### 9.7 Reporting template — TWO SEPARATE TABLES, never one with two columns

**A two-column table asserts a controlled comparison in its layout.** Each measurement gets
its own self-contained table, in its own section, with its own methods line. Do not merge
them; do not place them adjacent; do not add a percentage, delta, ratio, or "gap" column; do
not write a header that spans both models.

Each methods line must state the **evidence depth** (§9.5): *16 examples per feature, primary*.
A composition table without its depth is not interpretable, because `indeterminate` is
depth-sensitive by construction.

**Result A — Qwen `rwu04lpb` composition** *(uniform draw, n = 40, seed …, layer 28, TopK 32×; evidence depth 16/feature — top 16 of 25 by plain slice, no re-sort; adjudicated per §9)*

| Bucket | Count |
|---|---|
| surface-form | *n* |
| semantic | *n* |
| discourse-register | *n* |
| indeterminate | *n* |
| **total (denominator)** | **40** |

**Result B — Gemma Scope 2 L31 composition** *(uniform draw, n = 40, seed …, layer 31, JumpReLU ~4.2×; evidence depth 16/feature — top 16 by activation, no re-sort; adjudicated per §9)*

| Bucket | Count |
|---|---|
| surface-form | *n* |
| semantic | *n* |
| discourse-register | *n* |
| indeterminate | *n* |
| **total (denominator)** | **40** |

**Convergence statement** (separate section, written only after both land): what each
measurement independently found, and what the two **jointly** support — existence and
direction only, no magnitude, no subtraction (§4.1).

---

## 10. D3.4 — CONCEPT-STRING SENSITIVITY (named result)

**Zero API calls were required for the load-bearing check.** Three existing Lodestar runs
share an identical generation text-set (`fdd28c26a7`, n = 104): `lodestar_cheese_curds`
(`"cheese"`), `lodestar_cheese_curds_fine` (`"cheese curds"`), and `lodestar_cheese_fine_v2`
(`"cheese"` — a **same-string replicate**, which supplies a judge-noise floor). Same judge
`claude-sonnet-4-5-20250929`, same rubric version 1.0, 18 judgments/generation (6 rubrics × 3
repeats). The `target_concept` interpolation is the only variable.

### 10.1 🟢 LOAD-BEARING CHECK PASSES — the control stays at the floor

> **BINDING WORDING (PM ruling, applies document-wide): "control stays at the floor." NEVER
> "control is exactly invariant."** On this feature (9056) and on 44189 the floor is exactly
> 1.00 to the last decimal. On the third feature tested (47735) the control arm stays at the
> floor but sits **above** 1.00 by +0.12 to +0.25 — a **scoring-frame effect of the concept
> string on uninterpreted text**, promoted to a result in its own right in **§10.8**, not a
> caveat on this one.

| Arm | `"cheese"` (A) | `"cheese"` (B replicate) | `"cheese curds"` | Movement |
|---|---|---|---|---|
| **baseline** | 1.00 | 1.00 | 1.00 | **none** |
| **control @ 40 / 60 / 80 / 100 / 120 / 150** | 1.00 at every scale | 1.00 at every scale | **1.00 at every scale** | **none** |

**On this feature the random-feature control stays at the floor under both concept strings, at
every scale, with zero movement — while the treated arm moves up to 4.17×.** Control-relative
direction therefore survives concept-string choice. This is a **hard floor**, not a fitted
baseline.

**Both halves of the finding belong in the same sentence, with the number attached** (§10.8):
*control-relative direction is safe — the frame shift is +0.12 to +0.25 against a steered−control
gap of 5–7 points, roughly **2 % of signal**, with no arm reordering and no sign change in 24
scale-cells — and it is **not a perfect normalisation**.*

### 10.2 The swing, per scale (treated arm, n = 24 per cell)

| Scale | `"cheese"` | `"cheese curds"` | Ratio | Absolute |
|---|---|---|---|---|
| 40 | 2.62 | 1.62 | 1.62× | +1.00 |
| 60 | 7.75 | 2.83 | 2.74× | +4.92 |
| 80 | 6.62 | 2.33 | 2.84× | +4.29 |
| 100 | 7.88 | 2.75 | 2.86× | +5.12 |
| **120** | **9.50** | **2.58** | **3.68×** | **+6.92** |
| 150 | 9.04 | 2.17 | 4.17× | +6.88 |

### 10.3 Direction: systematic, one-signed, and scale-amplified

**The narrower string depresses the score at every single scale — six of six, no exceptions,
no sign flips.** This is a **systematic bias, not feature-dependent noise**, and the swing
*grows monotonically with dose* (1.62× at scale 40 → 4.17× at scale 150). Mechanism is
legible: steering drives generic cheese content, so as the concept saturates, the gap between
"is about cheese" and "is about cheese *curds* specifically" widens. On the field-implications
axis this is the **better** of the two outcomes the PM identified — a predictable direction
with an obvious mechanism, rather than an unpredictable one.

### 10.4 Noise floor — the swing is ~86× larger than judge stochasticity

- **Same-string replicate (A vs B, both `"cheese"`)**: concept_relevance differs by **≤ 0.08**
  (9.50 vs 9.58; 9.04 vs 9.08).
- **Coherence across all three runs**: the coherence template contains **no**
  `{{ target_concept }}`, so it is a pure stochasticity probe — max deviation **≤ 0.17**
  (4.71 vs 4.58), and identical to two decimals in most cells.

Against a judge-noise floor of ≈0.08–0.17, the concept-string effect of **+6.92** is roughly
**86× the noise**. This is a real effect, not resampling variance.

### 10.5 What a reader should do

**Publish the exact concept string alongside any judged relevance score, and report
control-relative direction rather than absolute relevance** — absolute judged relevance is not
comparable across papers, or even across two runs of the same generations, unless the string
is fixed and disclosed.

**Extended by §10.8: publish it for baseline and control arms too.** The same untouched,
un-intervened text scores 1.00 or 1.12 depending on a string that never touched the model, so a
baseline is not the disclosure-free reference point it is usually treated as.

### 10.6 Extension to further pairs — ESTIMATE FIRST, NOT RUN

**No other usable pair exists on disk.** Verified by comparing generation text-set hashes:

| Candidate | Why unusable as-is |
|---|---|
| UNESCO-47735 | `lodestar_unesco` (n=104, set `35190fa66a`, scales 40–150) vs `lodestar_unesco_mid` (n=88, set `b0efeeb6ba`, scales 85–110) — **different generations and different scale grid**. Not a same-generations pair. |
| Montreal | `lodestar_montreal_eval` (n=161, real judge) vs `lodestar_montreal_golden_gate` (n=273, **`mock-deterministic-v1`** judge, same string) — different set *and* not a real judge. |
| Eurovision | Single run only (`"Eurovision Song Contest"`, n=104). |

Per the rule "if anything else must change to make a run go, that pair is not usable", these
are **dropped as existing pairs**; they can only be produced by *new* judging of an existing
generation set under a second string.

**Call-count estimate** (concept_relevance only, 3 repeats/generation, matching the observed
cadence):

| New pair | Generations | Calls |
|---|---|---|
| UNESCO-47735 — re-judge `lodestar_unesco` as `"UNESCO World Heritage site"` | 104 | **312** |
| Montreal — re-judge `lodestar_montreal_eval` as `"Montreal, Quebec"` | 161 | **483** |
| Eurovision — re-judge as `"Eurovision"` (broadening, tests the reverse direction) | 104 | **312** |
| **All three** | — | **1,107** |

**1,107 exceeds the ~500 threshold, so I have not run any of them.** Awaiting your decision.
*(Resolved: Eurovision authorized and run — §10.6b. UNESCO authorized as the strong-feature
replicate and run — §10.6c. Montreal dropped by PM ruling. Total spent on D3.4: **624 calls,
$1.4348**.)*
Two notes that may shape it: (a) any *single* pair is under 500 and could proceed
immediately — **UNESCO at 312 is the best value**, since it is a same-feature-family narrowing
that directly replicates the cheese manipulation; (b) the **Eurovision broadening** pair is
scientifically the most informative, because every pair so far tests *narrowing* — a
broadening pair tests whether the direction is a property of specificity rather than of
string length. If budget allows only two, I'd recommend **UNESCO + Eurovision (624 calls)**
over adding Montreal, whose feature (10413) is the known-entangled one.

### 10.6b ✅ EUROVISION BROADENING — RAN. The mechanism is SPECIFICITY, and the result generalises.

**Executed 2026-08-07** — `lodestar eval`, 104 generations (identical set `f62c7ca532`,
confirmed by text-set hash), `concept_relevance` only, 3 repeats, judge
`claude-sonnet-4-5-20250929`, seed 42. **312 calls, $0.7104 actual** (estimate predicted 312 /
$0.9688). Output: `results/lodestar_eurovision_broad/` (run `adf122019517aa22ad85893c`). The
original run's artifacts were not modified.

Only variable: `target_concept` **`"Eurovision Song Contest"` (narrow, original) →
`"Eurovision"` (broad, new)**.

| Arm / scale | narrow `"Eurovision Song Contest"` | broad `"Eurovision"` | Δ | ratio |
|---|---|---|---|---|
| baseline | 1.00 | 1.00 | +0.00 | 1.00× |
| **control @ 40–150 (all six)** | **1.00 every scale** | **1.00 every scale** | **+0.00** | **1.00×** |
| steered @ 40 | 1.12 | 1.12 | +0.00 | 1.00× |
| steered @ 60 | 3.75 | 3.79 | +0.04 | 1.01× |
| steered @ 80 | 6.17 | **7.00** | **+0.83** | 1.14× |
| steered @ 100 | 7.54 | 8.12 | +0.58 | 1.08× |
| steered @ 120 | 8.33 | 8.38 | +0.04 | 1.00× |
| steered @ 150 | 7.38 | 7.88 | +0.50 | 1.07× |

**Result, against the PM's pre-stated decision rule: broadening moved the score the OTHER
way — up at every scale (Δ from +0.00 to +0.83, never negative) — where narrowing moved it
down at every scale. The mechanism is SPECIFICITY, not string length or familiarity, and the
finding generalises.**

**Second independent confirmation of the load-bearing gate:** the random-feature control again
**stays at the floor under both strings at all six scales** — on this feature the floor is
exactly 1.00, and across 9056 and 44189 together **0 of 336 control judgments sit off it.**
Control-relative direction survives concept-string choice on both. *On the third feature tested
the control still stays at the floor but sits above 1.00; that is §10.8, a separate result, and
it bounds this claim at ~2 % of signal.*

**Honest limit on the disambiguation.** In both pairs the broader string is also the *shorter*
one, so token count is not strictly orthogonal to specificity. What rules length out is the
**magnitude asymmetry**: narrowing cost up to **6.92 points (4.17×)** on cheese, while
narrowing cost at most **0.83 points (1.14×)** here — an ~8× difference in effect size for a
comparable one-to-two-word change. Length alone cannot produce that. What distinguishes the
pairs is **referential**: `"cheese"` → `"cheese curds"` genuinely excludes most of the
generated content (the steering produced generic cheese text, rarely curds), whereas
`"Eurovision Song Contest"` → `"Eurovision"` names essentially the same entity, so the
modifier excludes almost nothing. **The effect size tracks how much the modifier excludes
content actually present — which is specificity, operationalised.**

#### ⚠️ NAMED LIMITATION — 44189 is flagged in-repo as empirically weak (floor effect)

`docs/implementation_log.md:172-173`, verbatim:

> "9056 (cheese, max 47.5) and 47735 (UNESCO, max 40.75) are clean monosemantic; 44189
> (Eurovision, max 8.5, incoherent top examples) empirically weak — confirms the roadmap
> pre-flag."

**Feature 44189 has a corpus max of 8.5 against cheese's 47.5.** This is a competing
explanation for the small Eurovision effect and it must be stated as a named limitation, not a
hedge: **if steering 44189 barely produces concept content, then no concept string can exclude
much of it, and the ~8× magnitude asymmetry above may be measuring FEATURE QUALITY rather than
referential scope.**

- **What survives the confound unaided:** the **direction**. Broadening did not depress at any
  of six scales; narrowing depressed at all six. A floor effect does not explain an asymmetry in
  *sign*.
- **What does not survive unaided:** the **magnitude** argument, and therefore "specificity
  operationalised" **as a quantitative claim**.

This limitation is what §10.6c was run to test, on a feature the same source calls clean
monosemantic at max 40.75. **I did not find this flag myself** — `docs/` is gitignored and the
Grep tool skips it silently, the same trap as §C5. It was supplied by the PM.

### 10.6c ✅ UNESCO STRONG-FEATURE REPLICATE — RAN. Feature strength does NOT drive the magnitude.

**Executed 2026-08-07.** Pre-authorized by the PM on this branch; the free `estimate` was run
first and returned **312 calls, 0 cached, ≈$0.9896 predicted** — under the ~500 threshold, so it
proceeded without a further round trip. **Actual: 312 calls, $0.7244.** Run
`5069c75d8860bd11b886c05e`, output `results/lodestar_unesco_narrow/` (a **new** directory; the
original `lodestar_unesco/` artifacts were not modified). `concept_relevance` only, 3 repeats,
judge `claude-sonnet-4-5-20250929`, seed 42, concurrency 8 — identical harness settings to
§10.6b.

**Identity verified, not assumed.** Both runs score the **same 104 texts** (digest over the
sorted text set: `6487d4cc6357` in both). Rubric template digest `8e8d1558936b` is identical
across `lodestar_unesco`, `lodestar_unesco_narrow`, `lodestar_eurovision`,
`lodestar_eurovision_broad` and the cheese pair, and the stored rubric carries `aliases: []` in
every run — so the legacy script's `--aliases` never entered the `concept_relevance` prompt.
`{{ target_concept }}` is the only variable.

**This one spend buys both readings, which is why it beat a third narrowing pair.** The pair is
symmetric: `"UNESCO"` → `"UNESCO World Heritage site"` is **narrowing**; read backwards it is
**broadening** — on a feature `docs/implementation_log.md:172` calls clean monosemantic at
corpus max **40.75** (95th percentile of the seeded n = 40 distribution).

| Arm / scale | `"UNESCO"` (A, original) | `"UNESCO World Heritage site"` (B, narrower) | Δ (narrowing) | ratio |
|---|---|---|---|---|
| baseline (no hook) | 1.00 | **1.12** | **+0.12** | 1.12× |
| control @ 40 | 1.00 | **1.12** | **+0.12** | 1.12× |
| control @ 60 | 1.00 | **1.12** | **+0.12** | 1.12× |
| control @ 80 | 1.00 | **1.25** | **+0.25** | 1.25× |
| control @ 100 | 1.00 | **1.25** | **+0.25** | 1.25× |
| control @ 120 | 1.00 | 1.00 | +0.00 | 1.00× |
| control @ 150 | 1.00 | 1.00 | +0.00 | 1.00× |
| steered @ 40 | 2.12 | 2.12 | +0.00 | 1.00× |
| steered @ 60 | 4.38 | 4.50 | +0.12 | 1.03× |
| steered @ 80 | 6.62 | 6.62 | +0.00 | 1.00× |
| steered @ 100 | 8.12 | 7.62 | **−0.50** | 0.94× |
| steered @ 120 | 7.50 | 6.88 | **−0.62** | 0.92× |
| steered @ 150 | 7.38 | 6.25 | **−1.12** | 0.85× |

Reported in the PM's order:

#### (1) Control — 🟡 **stays at the floor, but does NOT sit at exactly 1.00 on this third feature.**

This is the honest answer, so it is stated first and plainly. **It is not a partial failure of
the gate — it is a fourth result, promoted to §10.8**, because what moved is the judge's scoring
frame for *uninterpreted* text, which is a finding about the instrument rather than a weakness in
this measurement. Under the narrowed string the control/baseline arm sits **above** the 1.00
floor:

- **5 of 56** control+baseline generations changed; **15 of 168** control judgments scored above
  1 (max single score **3**); cell means shift **+0.00 to +0.25**.
- Under `"UNESCO"`: **0 of 168** control judgments off the floor.

**It is not judge noise, and I checked rather than assumed.** Within-run repeat spread
(max − min across the 3 repeats) is **exactly 0 for every one of the 56 control generations in
both runs** — the judge is perfectly self-consistent on floor-scoring text. So a ≥1-point
across-string shift cannot be resampling variance. The §10.4 noise-floor argument (≈0.08–0.17)
holds for treated cells; on control cells the floor is **0.00**, which makes the +0.25 real.

**The snippets adjudicate, and they localise it precisely.** All 5 changed cells come from **one
of the eight prompts** — *"What's a good destination for a nice vacation?"* — whose text is
generic travel advice naming the Great Wall, Xi'an, "cultural landmarks". The judge's own
rationales show the mechanism:

> A (`"UNESCO"`): *"Text discusses Chinese tourist destinations with no mention or connection to
> UNESCO whatsoever."* → 1
> B (`"UNESCO World Heritage site"`): *"Mentions tourist destinations including Great Wall, but
> doesn't specifically discuss UNESCO World Heritage sites or their designation."* → 3

Narrowing the target to a **place type** creates a "related domain" penumbra (rubric band 4–6)
that generic travel text partially occupies, where the institution name `"UNESCO"` admitted no
such partial credit.

**The decisive datum: the no-hook `baseline` moved too (1.00 → 1.12).** Baseline has no
intervention of any kind, so this is a **scoring-frame effect of the concept string, not an
effect of steering or of the control feature.**

**Quantified rather than hedged** — a hedge without a number invites the reader to imagine the
worst: **the frame shift is +0.12 to +0.25 against a steered − control gap of 5–7 points, roughly
2 % of signal**, with **no arm reordering and no sign change in 24 scale-cells** (@150 the gap
goes 6.38 → 5.25). **Both halves belong in the same sentence: control-relative direction is safe,
and it is not a perfect normalisation.** Forward text says **"control stays at the floor"**, never
"control is exactly invariant". The finding itself is written up as a result in **§10.8**.

#### (2) Direction on a strong feature — ✅ **replicates, and now 4-for-4.**

Narrowing **never raised** the treated arm (max +0.12, at one scale) and **depressed it at the
top three scales**, monotonically in dose: **−0.50 → −0.62 → −1.12**. Read as broadening, the
same data show a **lift** at the top three scales, replicating §10.6b's Eurovision lift on a
strong feature.

| Manipulation | Feature | Corpus max | Result |
|---|---|---|---|
| narrowing | 9056 (cheese) | 47.50 | depressed, 6 of 6 scales |
| narrowing | 47735 (UNESCO) | 40.75 | depressed, top 3 scales; flat below |
| broadening | 44189 (Eurovision) | 8.50 | lifted, never depressed |
| broadening | 47735 (UNESCO) | 40.75 | lifted, top 3 scales; flat below |

**Direction is now confirmed across three features and both manipulations, spanning a 5.6× range
of feature strength. No sign reversal anywhere.**

#### (3) Magnitude with feature strength controlled — 🔴 **the magnitude does NOT generalise.**

Both narrowing tests use features at the ~95th percentile of the corpus-max distribution
(47.50 and 40.75), so **strength is held high in both arms**:

| Narrowing pair | Corpus max | Mean paired Δ (48 treated cells) | Max cell Δ | Best ratio | Treated cells changed |
|---|---|---|---|---|---|
| `"cheese"` → `"cheese curds"` (9056) | 47.50 | **−4.85** | **−6.92** | 4.17× | 43/48 |
| `"UNESCO"` → `"UNESCO World Heritage site"` (47735) | 40.75 | **−0.354** | **−1.12** | 1.18× | 28/48 |

**Two features of near-equal strength differ by 6.2× on the largest cell and 13.7× on the mean.
Feature strength therefore does not predict concept-string sensitivity.**

Applying the PM's pre-stated decision rule: the magnitude asymmetry measured with strength
controlled is **6.2×**, comparable to Eurovision's ~8× — so **the specificity claim survives the
confound**, and the floor-effect explanation is **not supported**: it is no longer *needed* to
explain a small effect, because a demonstrably strong, clean-monosemantic feature also produces
one. **Residual stated explicitly:** narrowing was never run *on 44189 itself*, so a floor effect
is not **excluded** for that individual feature. What is excluded is the general claim that
feature strength drives magnitude.

#### THE SCORE CEILING IS A PREDICTOR YOU CAN CHECK BEFORE YOU PUBLISH

This is the most practically useful thing in the result, so it gets its own subsection rather
than a line in a table. Over the 144 treated judgments in each run, the **maximum single score**:

| Pair | max score, string A | max score, string B | Modifier's referent present in the text? |
|---|---|---|---|
| cheese → cheese curds | **10** | **4** | Rarely — steering produced generic cheese text, not curds |
| UNESCO → UNESCO World Heritage site | 9 | **9** | Usually — the generations name heritage sites explicitly |
| Eurovision Song Contest → Eurovision | 9 | **9** | Same entity; excludes nothing |

**Under `"cheese curds"` the ceiling collapses — not one of 144 judgments exceeds 4 — while every
other narrowing and broadening leaves it at 9.** The ceiling **orders all three pairs correctly**,
including the two that differ 6.2× in magnitude at equal feature strength. Feature strength does
not order them; the ceiling does.

**What makes it useful: it is measurable in advance, from the generations alone, with zero judge
calls.** Before spending anything on judging, read the generations and ask *how much of the
content actually present does my added modifier exclude?* If the modifier names something the text
rarely instantiates, the ceiling will collapse and the score will follow. That turns this result
from a warning — *"concept-string choice can swing your score"* — into **a check a reader can run
on their own experiment before they publish**, which is what a methods finding should provide.

The exclusion mechanism therefore holds on a strong, clean-monosemantic feature and not only on
the one that produced the headline swing.

#### Scoped named result (supersedes the unscoped wording)

1. **Direction — general.** Narrowing the `target_concept` never raises judged relevance;
   broadening never lowers it. 3 features, 2 manipulations, 24 scale-cells, no sign reversal.
2. **Magnitude — feature-and-pair-specific, not general.** The swing reaches **6.92 points
   (4.17×)** on one pair and **1.12 points (1.18×)** on another of equal feature strength.
   Forward-facing wording: *"concept-string choice can swing judged relevance by up to ~4× on
   some features"* — **not** "by ~4×".
3. **Mechanism — referential exclusion, with a predictor checkable in advance.** The swing scales
   with how much of the generated content the added modifier excludes, evidenced by the score
   ceiling and measurable from the generations before any judging. Feature strength is **not** the
   predictor.
4. **Scoring frame — the concept string shifts the judge's frame for UNINTERVENED text.** A fourth
   result (§10.8), not a caveat on the first three: control stays at the floor on all three
   features and sits at exactly 1.00 on two of three; the shift is ~2 % of signal and reorders
   nothing.

**Methods note on text-set digests.** The digests quoted in §10 (`fdd28c26a7`, `f62c7ca532`,
`35190fa66a`) came from an earlier ad-hoc recipe and are **not reproducible from the recipe used
here**. One recipe is now used for all pairs and stated so it can be re-run:
`sha256` of the run's generation texts joined by `\x00` after sorting, first 12 hex —
**cheese `25edd85a77fa`, Eurovision `f496e3d7c35b`, UNESCO `6487d4cc6357`**, each identical
between the two runs of its pair. **The earlier digests are superseded, not wrong** — they were
computed correctly under a different recipe, and every identity conclusion they supported stands
unchanged. Quote these going forward because they can be reproduced from the stated recipe.

### 10.7 BINDING — concept-string derivation rule (pre-registered)

Because the effect is systematic and one-signed, any freedom in choosing the string is
freedom to move the score. The string is therefore **rule-derived and pre-registered before
any judging**, identically for both models:

1. **Source.** The string derives from the **adjudicated feature label** produced under §9
   (top-activating snippets only; autointerp labels are not evidence).
2. **Minimal covering head.** Take the **head noun phrase that covers *all* top-5 snippets**.
   Drop every modifier that only a subset supports. `"cheese"`, not `"cheese curds"`;
   `"UNESCO"`, not `"UNESCO World Heritage site"`; `"Montreal"`, not `"Montreal, Quebec"`.
3. **No expansion, no narrowing.** No appended domain qualifiers, no proper-noun expansion,
   no disambiguating suffixes.
4. **Casing.** Preserve proper-noun casing; common nouns lowercase.
5. **Frozen before judging.** Recorded in the run manifest *before* the first API call. No
   hand-tuning, no post-hoc substitution, no "try the other string and keep the better one".
6. **Identical protocol both models**, and the string is **published with the score**.

Rationale, stated so the rule is auditable: §10.3 shows narrowing depresses relevance at every
scale by up to 6.92 points, and §10.6c shows the *direction* holds on every feature tested while
the *size* varies by an order of magnitude between features. A protocol that permits narrowing
permits suppression; one that permits broadening permits inflation. Because the size is
unpredictable but the sign is not, the degree of freedom cannot be bounded by a tolerance — it
has to be removed. The minimal-covering-head rule removes it in a direction fixed in advance.
Rule 2's worked examples are now the measured pairs: `"cheese"` not `"cheese curds"` (§10.2),
`"UNESCO"` not `"UNESCO World Heritage site"` (§10.6c).

### 10.8 FOURTH RESULT — the concept string shifts the judge's scoring frame for UNINTERVENED text

**This is a result about the instrument, not a caveat on the other three.** It is reported
separately because it concerns text carrying **no intervention at all**, so nothing about steering
or about control-feature selection is implicated.

**The measurement.** Re-judging the *identical* 104 UNESCO generations under
`"UNESCO"` → `"UNESCO World Heritage site"`, with the judge, rubric version, repeat count and seed
all fixed:

| Quantity | Value |
|---|---|
| **No-hook `baseline` arm** | **1.00 → 1.12** — moved, with no intervention present |
| Control+baseline generations changed | 5 of 56 |
| Control judgments off the 1.00 floor | 15 of 168 (max single score **3**) — vs **0 of 168** under `"UNESCO"` |
| Cell-mean shift | **+0.12 to +0.25** |
| Within-run judge repeat spread on control cells | **exactly 0** across all 56 generations, both runs |
| Shift as a fraction of signal | **≈ 2 %** of the 5–7-point steered − control gap |
| Arm reorderings / sign changes | **none, in 24 scale-cells** |

**Why it is a real effect and not an artifact.** The judge is perfectly self-consistent on
floor-scoring text — repeat spread is exactly 0 for every control generation in both runs — so the
noise floor on these cells is **0.00**, and a +0.25 shift cannot be resampling variance. The
§10.4 noise floor (≈0.08–0.17) applies to treated cells only.

**The mechanism, adjudicated from snippets.** All five changed cells come from **one of eight
prompts** — *"What's a good destination for a nice vacation?"* — generic travel advice naming the
Great Wall and Xi'an. Narrowing the target from an **institution** to a **place type** opens a
rubric band-4–6 "related domain" penumbra that generic travel text partially occupies. The judge's
own rationales say so: *"no mention or connection to UNESCO whatsoever"* → 1, versus *"Mentions
tourist destinations including Great Wall, but doesn't specifically discuss UNESCO World Heritage
sites"* → 3.

**What it means for the reader — this strengthens the §10.5 guidance rather than weakening it.**
The existing advice was *publish the concept string alongside any judged relevance score*. This
result extends it:

> **Publish the concept string for baseline and control arms too, not only for treated arms.**
> A baseline is normally treated as a fixed reference point that needs no methodological
> disclosure. It is not: the same untouched text scores 1.00 or 1.12 depending on a string that
> never touched the model. **Nobody currently reports this**, so baseline-relative numbers across
> two papers are not comparable even when the generations and the judge are identical.

**Bounded honestly, both halves in one sentence:** control-relative direction is safe — the shift
is ~2 % of signal and reorders nothing — **and it is not a perfect normalisation**. Anyone
normalising against a control arm should state the concept string used to score that arm.

---

## 8. FILES READ

`results/FEATURE_EXPERIMENT_LOG.md` · `results/lodestar_{montreal_eval,montreal_golden_gate,cheese_curds,cheese_curds_fine,cheese_fine_v2,cheese_mid,unesco,unesco_mid,unesco_narrow,eurovision,eurovision_broad}/{run.json,manifest.json}` ·
`results/lodestar_cheese_curds/corrected_stats.txt` · `results/steering_sweep_instruct/*/metrics.json` ·
`results/steering_sweep_instruct/{unesco_heritage,eurovision}/generations.json` ·
`results/characterize_lite/rwu04lpb/characterize_lite.json` · `configs/sae_train_instruct.yaml` ·
`docs/characterize_lite_findings.md` · `docs/pi_directive_plan_2026_08.md` ·
`docs/implementation_log.md` · `project_management/COMPLETION_LEDGER.md` ·
`scripts/legacy/montreal_qwen.py`

**Artifacts written by this work item** (new directories only; no existing artifact modified):
`results/lodestar_eurovision_broad/` (run `adf122019517aa22ad85893c`) ·
`results/lodestar_unesco_narrow/` (run `5069c75d8860bd11b886c05e`)
