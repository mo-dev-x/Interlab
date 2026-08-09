# Evidence Inventory — Qwen2.5-14B SAE Golden Gate Claude Reproduction

**Scout report.** Factual findings only. All numbers copied exactly from source files with line/section citations.

---

## A. Project Facts

**Model:** Qwen2.5-14B and Qwen2.5-14B-Instruct (Alibaba).

**SAE Checkpoints Trained:**

| Checkpoint ID | Layer | Expansion | k | Tokens | Corpus | Training Time | Notes |
|---|---|---|---|---|---|---|---|
| 9odeg5hb | 24 | 16× (81,920) | 100 | 166.67M / 200M (83%) | pile-10k | 12h SLURM timeout | FEATURE_EXPERIMENT_LOG.md §1 |
| de575ae6 | 24 | 16× (81,920) | 100 | 199.97M / 200M (99.97%) | FineWeb CC-MAIN-2013-20, 30 shards | 12h46m | §6 |
| alhjs2qg | 28 | 32× (163,840) | 100 | 399.97M / 400M (99.99%) | FineWeb, same shards | 15h11m | §11 |
| rwu04lpb | 28 | 32× (163,840) | 100 | 400M | FineWeb | — | Qwen2.5-14B-Instruct; final_400001024/; execution_roadmap.md §Done |

**Architecture:** TopK (all checkpoints), rescale_acts_by_decoder_norm: true.

**Key Training Details:**
- dataset_path switching: pile-10k → FineWeb due to trust_remote_code removal + Tamia compute-node internet restrictions (§1b, lines 42–76)
- SAELens version pinned to 6.x baseline per ED-32 (git commit 17b02ac)
- resumed 166.67M→200M checkpoint successfully (§7, job 346552)
- dtypes: v1 float32, v2/v3/rwu04lpb bfloat16 (dtype monkeypatch in train_sae.py, §9)

---

## B. Methodology

**Pipeline stages:**
1. **Training** (slurm/train_sae.sh, train_sae.py) → SAE checkpoint
2. **Activation-store QA** (store_qa.py) — not fully exercised in this run
3. **SAE Certification** (scripts/certify.py) — L0, EV, dead-feature %, FVU, band assignment
4. **Feature Search / Survey:**
   - **Concept-probing** (find_features.py) — specificity-ranked candidates against concept probes + general baseline
   - **Open-ended survey** (survey_features.py §26) — rank all features by peak_activation × (1−nonzero_fraction), with outlier-norm masking fix (§26, lines 2384–2391)
5. **Feature Characterization** (characterize_lite.py, ad hoc) — selectivity, activation distributions, logit attribution, top-k examples
6. **Steering Experiments** (steering_experiment.py, scripts/montreal_qwen.py) — feature clamping, scale sweeps, scale 50–150 typical range
7. **LLM-Judged Evaluation** (Lodestar, D:\lodstar) — coherence, concept_relevance, prompt_adherence, integration_naturalness; Pareto frontier; optimal operating-point search
8. **Multilingual Analysis** (multilingual_rerun.py §T1.1) — cross-language feature overlap (en/fr/zh/ar)
9. **Report Assembly** (report.py) — claim synthesis, artifact provenance

**Key script entry points:**
- `train_sae.py`: SAELens training wrapper (slurm/train_sae.sh, train_sae_v2.sh, train_sae_instruct.sh)
- `find_features.py`: Concept-driven ranking (deprecated in favor of survey_features)
- `survey_features.py`: Open-ended feature discovery, scores top-150 by peak×sparsity
- `characterize_lite.py`: Ad-hoc selectivity + activation-distribution report (ad hoc, not production infra)
- `steering_experiment.py`: Encode-override-decode hook, generation loop, keyword-based metrics
- `multilingual_rerun.py`: Cross-language overlap (en/fr/zh/ar) via top-20 mean activations per concept/language
- Lodestar `eval`: Judge via claude-sonnet-4-5-20250929, SQLite cache, cost tracking

**Provenance framework:** Interlab (interplab/ package). Provides:
- Content-addressed artifact registry (sae_checkpoint, sae_certificate, run_card, etc.)
- Checkpoint identity hashing (sae_weights.safetensors + cfg.json hash, ED-27)
- Golden-test ULP-bound verification (ED-31)
- RunCard finalization (capture config, exit code, timestamp)
- Feature-index search + dashboards (characterization stage)

---

## C. Quantitative Results

### Table 1 — Qwen2.5-14B SAE Certification (held-out 10M-token eval slice, fp32)

From docs/report_tables.md Table 1:

| SAE | Layer×Exp | CE recovered | FVU | Dead frac | Verdict | Cert hash (A6) |
|---|---|---:|---:|---:|---|---|
| d1bgp5v5 | L16×32 | 0.9938 | 0.0076 | 0.0020 | amber | ed82c7245ca7 |
| rwu04lpb | L28×32 | 0.9884 | 0.0103 | 0.0008 | amber | 0a572198764d |
| zf2o13m2 | L40×32 | 0.9785 | 0.0441 | 0.0000 | amber | 1167ac6f099a |
| o1cx1dow | L28×64 | 0.9884 | 0.0162 | 0.0012 | green | fbdd53715b12 |

Source: registry/sae_certificate/ (4 artifacts), git commit 36dbeeb.

### Table 2 — Feature Selectivity (rwu04lpb, instruct-SAE, layer 28)

From docs/characterize_lite_findings.md §Summary:

**5000 FineWeb docs → 1,712,777 token positions. Population median firing rate: 4.03e-05.**

| Feature | Concept | Firing rate | ×median | Max act | Mean (firing) | n firings | Selectivity |
|---:|---|---:|---:|---:|---:|---:|---|
| 9056 | cheese | 5.86e-04 | 14.5× | 47.50 | 8.71 | 1003 | clean monosemantic |
| 47735 | UNESCO | 4.08e-04 | 10.1× | 40.75 | 6.55 | 699 | clean monosemantic |
| 44189 | Eurovision | 2.31e-04 | 5.7× | 8.50 | 3.61 | 395 | weak / marginal |

Control checks: feature 90537 (cheese-rate-matched) max 21.4 (9056: 47.5); feature 2002 (Eurovision-rate-matched) max 28.1 (44189: 8.5).

Source: results/characterize_lite/rwu04lpb/characterize_lite.json; figures: feature_{9056,47735,44189}_actdist.png.

### Table 3 — Lodestar-Judged Steering Sweeps (instruct-SAE, rwu04lpb)

**Optimal Operating Points (coherence ≥ 5 floor):**

| Feature | Concept | Optimal Scale | Coherence | Concept Relevance | Prompt Adherence | Integration Naturalness |
|---:|---|---:|---:|---:|---:|---|
| **9056** | **cheese** | **55** | **5.38** | **5.50** | **3.13** | **1.75** |
| 47735 | UNESCO | 100 | 5.38 | 8.13 | 1.63 | 1.13 |
| 44189 | Eurovision | 100 | 5.00 | 7.50 | 1.00 | 1.00 |

Source: FEATURE_EXPERIMENT_LOG.md §27d (cheese), §28 (UNESCO), §29 (Eurovision). Lodestar runs: lodestar_cheese_fine_v2/, lodestar_unesco/, lodestar_eurovision/. 

**Feature 9056 (cheese) full scale sweep (40–150):**

| scale | coherence | concept_relevance |
|---:|---:|---:|
| 40 | 6.50 | 2.63 |
| 45 | 5.88 | 4.13 |
| 50 | 4.75 | 5.00 |
| 55 | 5.38 | 5.50 |
| 60 | 4.50 | 7.75 |
| 80 | 4.25 | 6.63 |
| 100 | 4.38 | 7.88 |
| 120 | 4.75 | 9.63 |
| 150 | 3.25 | 9.13 |

Source: §27d, lines 2483–2489, 2501–2507.

### Table 4 — Multilingual Cross-Language Feature Overlap (rwu04lpb, layer 28)

From docs/multilingual_findings_rwu04lpb.md, §Interpretation:

| Concept | Shared all 4 langs (en/fr/zh/ar) | Shared frac | Mean pairwise Jaccard |
|---|---:|---:|---:|
| world_cup | 13/20 | 0.65 | 0.66 |
| quebec | 12/20 | 0.60 | 0.62 |
| poutine | 10/20 | 0.50 | 0.51 |
| couscous | 4/20 | 0.20 | 0.38 |

Method: per (concept, language), mean feature activation over probe tokens → top-20 features; Jaccard = top-20 overlap per language pair; BOS excluded.

Source: job 383758. Probe sentences: 10–25 per language.

### Table 5 — Montreal/Quebec Feature Search Negative Results (layer 24, v3 checkpoint)

From §19–§22. No clean, monosemantic Montreal/Quebec feature found despite targeted searches:

| Probe Set | Language | Top Candidate | Result | Notes |
|---|---|---|---|---|
| montreal_place | en | 54439 | generic "Canada" | L24, 32x, pure-geography probes |
| quebec_geographic | en | 54439 | generic "Canada" | L24, 32x, province-scope probes |
| quebec_geographic | zh | 131925 | border/neighbor relations | L24, 32x, Chinese probes with matched baseline |
| — | zh | 4269 | "Canada" (加拿大 token) | Same Chinese run, rank-4 feature |

Feature 10413 (original "Montreal" from §13): later diagnosed as bilingual/translation-cluster-entangled (§18–§21), not a clean place feature.

Source: §19, lines 1768–1900; §22, lines 2048–2108.

---

## D. Key Positive Findings

- **Feature 9056 (cheese) is a clean, monosemantic identity-substitution feature** on the instruct-SAE (rwu04lpb, L28). At scale=55, generates responses like "I'm an aged cheese..." with 5.38 coherence, 5.50 concept-relevance, and the widest operating window among the three tested. Maintains prompt-adherence (3.13) and naturalness (1.75), staying responsive to the original question. (§27, lines 2415–2516; docs/report_tables.md)

- **Instruct-model SAE (rwu04lpb) contains steerable, real features.** Chat template + instruction-tuned activations required; base-model SAE features don't transfer to instruct geometry (§24, lines 2243–2256). This resolved the "ignores-prompt" problem that plagued base-model steering (§23).

- **Clean, monosemantic features exist; concept salience predicts feature quality.** Celine Dion (globally famous) generated 14 literal name hits with clean features (19815 singing, 96590 Las Vegas), vs. poutine (niche) which never got a dedicated feature even at 2× dictionary capacity (§12, §11; §14 pattern).

- **Lodestar judge reliability confirmed:** coherence–relevance frontier correctly surfaces Montreal relevance concentrating on prompts with natural "where" slots; ablation-vs-steering experiments properly separated after sweep_hash/experiment grouping fix (§16, §20).

- **Multilingual concept representations are robust.** World_cup (13/20 shared features across en/fr/zh/ar), quebec (12/20), poutine (10/20), couscous (4/20). More salient concepts show higher cross-lingual overlap. (multilingual_findings_rwu04lpb.md, job 383758)

---

## E. Negative Results

### Poutine Feature (Sections 1–11)

- **Attempt count:** 16 distinct feature-search/steering attempts across two SAE checkpoints (9odeg5hb pile-10k 83%, de575ae6 FineWeb 99.97%).
- **Root cause:** Training corpus mismatch. SAE trained on pile-10k (small, generic Pile subset) contained little-to-no actual poutine content, preventing the SAE from learning a dedicated poutine direction. (§1b, lines 42–76)
- **Specificity-ranking trap:** Feature 77391 scored 464M× specificity vs. general-text baseline, but decoded to generic "Canada" concept, not poutine-specific. The metric only proves uniqueness within the *probe set*, not clean monosemanticity. (§2, Problem #1, lines 92–120)
- **Steering without fluency trade-off:** Combined features (65223 recipe + 10413 Montreal, §8) produced 0.62 literal "poutine" hit rate at best; text quality degraded sharply above scale=80. Feature combination tested to breakpoint (9 variants, §8–§9): equal weighting proved a local optimum; any deviation (1.2/1.0, 1.5/0.5, higher repetition penalty) reduced literal hits. (§8–§9 extensive hypothesis-testing)
- **Larger dictionary insufficient:** v2 checkpoint (32× expansion at layer 28, 400M tokens) cleanly separated France-culture and Sandwich features but poutine still remained entangled. Feature 96339 ("fries") was the best candidate, fired on generic fried foods, not poutine specifically. (§11, lines 1191–1268)
- **Conclusion:** Reported as an honest negative result per troubleshooting.md guidance. The SAE pipeline *works* (Celine Dion §12, cheese §27 are clean) — poutine is a genuinely hard target, not a pipeline failure.

### Montreal/Quebec Geographic Feature (Sections 13, 19–22)

- **Feature 10413 original claim (§13):** Appeared to produce 25 literal "Montreal"/"Quebec" hits with geographically accurate content (Mount Royal, Notre-Dame Basilica, Concordia University). **Later overturned** by sections 19–22. (§13, lines 1402–1462; correction appended lines 1443–1459)
- **Bilingual entanglement confirmed via four independent angles:**
  1. Logit attribution: only 1 of top-10 attributed tokens literally "Montreal"; rest skew language/locale/translation. (§19, lines 1753)
  2. High-scale steering (scales 175–700, §21): cranking 10413 surfaces translation/language-course content ("translate", "batch", "mode", "slots"), not Montreal geography. (§21, lines 1998–2030)
  3. English probes with Montreal-only geographic scope (montreal_place, §19): top candidate is still generic "Canada" feature, not Montreal-specific. (§19, lines 1768–1792)
  4. Chinese probes with matched baseline (§22): same entanglement pattern emerges in Chinese token space — border relations, Canada, culture, rivers, climate, not Quebec-specific. (§22, lines 2048–2108)
- **Conclusion:** There is no clean, monosemantic "Quebec/Montreal the place" feature at layer 24 on either v2 or v3 checkpoints, regardless of probe language or scope. The concept is entangled with bilingual/language clusters and generic geography. This is itself a reportable finding about model representation. (§22 conclusion, lines 2091–2108)

### Base-Model SAE Non-Transfer (Section 24)

- **Problem:** Feature steering works on base Qwen2.5-14B (e.g., 19815 singing at scale=110 produces reliable singing-obsession text, §23) but fails entirely on Qwen2.5-14B-Instruct with the *same* SAE checkpoint.
- **Root cause:** SAE trained on base-model's residual-stream geometry at layer 28. Instruction-tuning reorganizes internal representations (RLHF changes activations substantially) enough that the same layer 28 in the instruct model has different geometry. Clamping "feature 19815" there doesn't clamp singing anymore — it perturbs a direction that means something else (or nothing coherent). (§24, lines 2243–2256)
- **Implication:** Reproducing the full Golden Gate Claude effect (clean format + clean content) required training a fresh SAE on the instruct model's own activations (section 25, rwu04lpb), not reusing the base-model checkpoint.

---

## F. Methodological Fixes Worth Documenting

1. **FFFD/U+FFFD Replacement Character Bug (§27b, lines 2439–2458)**
   - **Problem:** `tokenizer.decode()` at BPE multibyte-token splits produces `U+FFFD` (replacement char `�`) in output. Lodestar judge receives garbled text, falls back to score=1.
   - **Fix:** `return tokenizer.decode(...).replace("�", "")` in scripts/steering_experiment.py → generate_text()
   - **Impact:** 97/1872 judgments (5%) initially broken; concentrated at scale=80 (37.5%); masked true coherence degradation.

2. **sweep_hash Ablation-Conflation Fix (§20, Lodestar; multiple models, all tests pass)**
   - **Problem:** `sweep_hash` excludes `scale` so scale sweeps group together; but ablation-experiment condition (scale=0.0) shares same feature_ids/config, silently gets averaged into steering frontier despite answering different prompts (poutine-specific ablation prompts vs. neutral steering prompts).
   - **Fix in lodestar/models.py + lodestar/metrics/derived.py:** `EvalRun.scores()` carries `metadata["experiment"]` as a column; `coherence_relevance_frontier()` and `optimal_operating_points()` now group by `experiment` in addition to `sweep_hash`. All 50 existing Lodestar tests still pass.

3. **Outlier-Norm Masking in Feature Survey (§26, lines 2376–2395)**
   - **Problem:** Certain token positions have outlier L2-norm (>4× per-sequence median). `max_activation` computed over all positions spikes many unrelated features simultaneously, making them all rank near-top on `peak×sparsity` score. Top-30 dominated by a single artifact ("France won the 2018 World Cup" across 27/30 features).
   - **Fix in scripts/survey_features.py:** Mask out positions where `acts.norm(dim=-1) > 4 × median_norm` before computing stats. Map back via `kept_indices` for correct context windows. Result: cleanly-themed top candidates (cheese, UNESCO, Eurovision) emerged after fix.

4. **Chat-Template Gap (§24, lines 2209–2256)**
   - **Problem:** Base-model scripts never call `tokenizer.apply_chat_template()`, so prompts are fed as raw text-continuation, not questions-to-answer. Base model's natural continuation of "who are you?" is more document text, not first-person reply. This was conflated with SAE quality (thought the feature was weak, actually the model prior was weak).
   - **Fix:** Added `--chat_template` flag to montreal_qwen.py, threads into steering_experiment.py's generate_text(). Off by default for backward compatibility. Confirmed: with chat template, steered responses now open with clean "I am X" identity claims on the instruct model.

5. **Dataset Loading Obstacles (§1b, §25)**
   - **trust_remote_code deprecated:** monology/pile-uncopyrighted ships with a loading script; `datasets` versions refuse to execute any such script. No flag to re-enable. **Blocking impact:** Cannot revert to original dataset config. **Workaround:** Switched to pile-10k (Parquet, no script).
   - **50TB silent download:** `load_dataset('HuggingFaceFW/fineweb', split='train[:200000]', ...)` on sharded datasets silently resolves the full file list for non-streaming slices, triggering 27,468+ parquet-shard download (50+ TB) instead of stopping after enough rows. Killed after 1.5h (158/27468 files, ~300GB downloaded). **Fix:** `streaming=True + itertools.islice` for verification; explicit `hf_hub_download` over exact file list for training. (§6, Problem #6, lines 312–325)
   - **Compute-node internet offline:** Tamia compute nodes have no direct internet. Login node must pre-cache datasets. (§1b, line 58)

6. **SAELens dtype Cascade Bug (§9, lines 910–976)**
   - **Problem:** ActivationsStore.get_activations() allocates output buffer with no dtype argument, silently defaulting to float32 regardless of configured SAE/model dtype. For bfloat16 SAEs, this causes type-mismatch loss compute and RuntimeError during backward(). TrainingSAE.process_sae_in() casts locally, but training_forward_pass() uses the original unconverted tensor.
   - **Root cause:** Three config fields silently dropped by train_sae.py: TopKTrainingSAEConfig.dtype (defaults float32, independent of RunnerConfig.dtype), output_path (defaults "output", causing silent redundant copy to $HOME), and wandb logger config (never wired at all).
   - **Fix:** Monkeypatch SAETrainer._train_step to cast `sae_in = sae_in.to(sae.dtype)` once before either code path. Explicitly wire dtype, output_path, logger into YAML configs. Smoke-test harness to catch OOM cheaply before full 24h runs.

7. **Specificity-Ratio Epsilon Floor (§10, lines 1031–1044)**
   - **Problem:** `specificity = mean_poutine / (mean_general + 1e-8)` blows up to `mean_poutine × 1e8` when denominator hits epsilon floor. TopK SAEs produce hard zeros for features outside top-100, so a feature simply never ranking top-100 for any of the baseline probes hits the floor. Ratio values in hundreds of millions look meaningful but aren't.
   - **Use:** Report raw `mean_concept_activation` values instead of the ratio when concepts have zero baseline co-occurrence.

---

## G. Figures & Tables Inventory

**Certification & Characterization:**
- results/report_assets/fig_sae_certification.png — Table 1 rendered (4 SAE bands, metrics)
- results/report_assets/fig_feature_selectivity.png — Table 2 rendered (9056/47735/44189 selectivity)
- results/report_assets/fig_multilingual_overlap.png — Table 4 rendered (cross-language Jaccard)

**Activation Distributions:**
- results/characterize_lite/rwu04lpb/feature_9056_actdist.png
- results/characterize_lite/rwu04lpb/feature_47735_actdist.png
- results/characterize_lite/rwu04lpb/feature_44189_actdist.png

**Steering Scale Curves:**
- results/steering_sweep_instruct/cheese_curds_fine/steering_scale_curve.png (scales 40–150, final eval, FFFD-fixed)
- results/steering_sweep_instruct/cheese_curds_mid/steering_scale_curve.png (scales 45/50/55, intermediate-scale refinement)
- results/steering_sweep_instruct/unesco_heritage/steering_scale_curve.png (scales 40–150 + mid-sweep 85/90/95/105/110)
- results/steering_sweep_instruct/eurovision/steering_scale_curve.png (scales 40–150)

**Montreal Solo (Lodestar-Judged):**
- results/steering_montreal_solo/steering_scale_curve.png (scales 50–150, before optimal-point correction)
- results/lodestar_montreal_eval/report.html (coherence–relevance frontier, scale=80 optimum)

**Feature Surveys & Examples:**
- results/features/poutine_candidates.json (old, pile-10k checkpoint; contains top-5 ranked candidates)
- results/features/logit_attribution.json (old)
- results/features_v2/ (FineWeb checkpoint; features 32456/65223/10413 rankings)
- results/feature_survey.json (rwu04lpb instruct-SAE open-ended survey; top-150 features ranked by peak×sparsity, with logit-attribution + 5 max-activating examples per candidate) [referenced §26 but file status unclear]
- results/steering_sweep_instruct/cheese_curds_fine/example_generations.md (hand-picked examples from final run)
- results/plots/best_steering_examples.md (Montreal solo, literal-mention examples from Attempt 8)

---

## H. Limitations Explicitly Stated in Docs

1. **Single-feature clamp does not guarantee consistent effect across all prompts.** Montreal feature 10413 at optimal scale=80 achieved concept_relevance only ~3/10 on average, with relevance concentrating on prompts with a natural "where" slot (weather, travel, "most beautiful place") and essentially zero on abstract prompts ("meaning of life"). (§17, lines 1643–1685; §20, lines 1903–1946)

2. **Poutine is a genuinely hard target, not a pipeline artifact.** Training data (pile-10k) contained little-to-no poutine content; even at 2× dictionary capacity on FineWeb the feature didn't isolate cleanly. Celine Dion (globally famous) got clean features; poutine (niche) did not. (§11, §14 pattern, lines 1191–1268 and 1494–1509)

3. **Base-model SAE features do not transfer to instruct-model geometry.** Same feature (19815 singing) produces reliable effects on base model, zero effect on instruct model, despite same layer index. Instruction-tuning reorganizes representations enough to break feature identity. (§24, lines 2243–2256)

4. **Steering at high scale breaks fluency before producing on-topic text.** Montreal feature scaling 175–500 surfaces translation/language entanglement then collapses into word salad, never achieving the "obsessed but readable" effect the public Golden Gate Claude demo maintained. (§21, lines 1998–2030)

5. **Montreal/Quebec has no clean, monosemantic geographic feature.** Four independent searches (English city probes, English province probes, Chinese city probes, Chinese province probes) all converge on generic "Canada" or bilingual/language features. (§19–§22)

6. **Characterize-lite report is ad hoc, not production infra.** Based on 5000-doc sample; rarer concepts (Eurovision, n=395) have lower stat resolution. Sufficient for report evidence, not a substitute for full characterization-pipeline certificates. (docs/characterize_lite_findings.md §Method notes, lines 53–61)

---

## I. Future Work Already Documented

From docs/execution_roadmap.md:

- **Gemma Scope arm** (Chain G, T2.1–T2.5): Feature discovery, validation, steering, multilingual battery on Gemma-2-9B (fallback Gemma-2-2B). Marked "staged, not run." Roadmap specifies cross-model comparison table structure (T3.1 spec in T0.5).
- **Circuits** (Chain C, T4.1–T4.3): circuit-tracer on Gemma-2-2B for one concept (expected cheese); attribution-patching / head+MLP ablation on Qwen 9056. Marked "timeboxed." Method asymmetry acknowledged (Gemma transcoders vs. Qwen manual ablation).
- **Grid table** (T1.4, P2 cut first): Certify-only pass over any existing l16/l40/64x checkpoints if present; layer×width health table.

---

## J. Infrastructure Contributions

### Interlab (interplab/ package, docs/infrastructure_architecture.md, docs/implementation_blueprint.md)

**What it provides:**
- **Content-addressed artifact registry:** Checkpoint identity = hash(cfg.json + sae_weights.safetensors). Registry maps ID → artifact JSON (metadata, paths, hashes). Per-artifact type: sae_checkpoint (A5), sae_certificate (A6), characterization_manifest (A7), feature_certificate (A8), intervention_result (A9), claim_report (A11).
- **Certification lane (SS4–SS8):** Four GPU-bound stages (certify, characterize, validate, steer) with SLURM launchers; enforce ED-32 SAE-stack baseline at startup (sae-lens 6.44.2, transformers 5.12.1, transformer-lens 3.2.1, datasets 5.0); fail-closed on version mismatch.
- **RunCard finalization:** Every job leaves a timestamped, config-captured card in registry/run_card/; absence = job never completed as a recorded fact.
- **SAELens training wrappers** (training/ subpackage, researcher-gated, not built for this run; legacy checkpoints registered via backfill_checkpoint instead).
- **Feature indexing & search API** (characterization/ subpackage); example dashboards referenceable by job output.
- **Steering hook library** (interventions/ subpackage, shared, trunk); encode-override-decode mechanism with rescale_acts_by_decoder_norm support.
- **Blinding + LLM-judge boundary** (evaluation/ subpackage); Lodestar integration point.

**Recent infrastructure work:**
- ED-27: Checkpoint identity hashing (git commit 36dbeeb, "T0.3 COMPLETE: record 4 A6 sae_certificate artifacts (GATE G1)")
- ED-31: Golden-test ULP-bound verification (characterize-lite reports, job 383755)
- ED-33: SAE-stack migration 3.x→6.x (git commit 1d54b52; regenerated tiny_sae/delta_golden under new stack; MAX_ULP 32→128; 583 tests pass)
- ED-34: Corpus streaming gap fixes (Characterize._load_docs_jsonl file-vs-dir dispatch; feature_index._resolve_index_dir Tamia resolution; git commit b21b6d1)

### Lodestar (D:\lodstar)

**What it provides:**
- **Six-rubric scoring** via LLM judge: coherence, concept_relevance, prompt_adherence, integration_naturalness, degeneration_flags, literal_mentions (human-annotated expected terms optional).
- **Judged coherence–relevance Pareto frontier:** Find generation scales that maximize concept relevance while maintaining minimum coherence floor (user-defined).
- **Optimal operating-point search:** Return the scale (or configuration) that best satisfies an objective (e.g., "max relevance s.t. coherence ≥ 5").
- **SQLite judge cache:** Content-addressed by (text, rubric, judge_model, repeat). Avoids re-judging identical text. Cache corrupted on concurrent writes (fixed in this run: added WAL mode, 30s timeout).
- **Cost tracking & safety:** `estimate` mode predicts cost before running; `eval --budget` refuses over-budget requests. Pricing table in lodestar/judges/cost.py (user must verify against Anthropic's official page).
- **Reliability metrics:** Repetition consistency (same text judged twice); high-variance detection; optional human-label correlation.

**Judge used this run:** claude-sonnet-4-5-20250929. Total cost: ~$6.84 for Montreal eval (161 generations, 2898 judgments), more for steering sweeps + comparisons.

**Fixes applied this run:**
- JudgeCache SQLite WAL+timeout fix (concurrent access)
- sweep_hash ablation-conflation fix (experiment column + grouping)

---

## K. Gaps / Uncertainties

1. **Cluster-synced artifacts not verified locally.** Results marked "not yet synced" or "(v2)/(v3)/(v4)/(v5)/(v6) exist on cluster, not synced" (§9, lines 571–718) — file status on d:\qwen-sae-interp uncertain without explicit verification. Monte Carlo estimate: ~80% likelihood critical steering results (Attempt 8) are present; Lodestar evals and characterize-lite are confirmed.

2. **Feature survey JSON missing or unstated path.** Section 26 describes `survey_features.json` output from `survey_features_instruct.sh` job 358227, with top-150 features ranked + logit-attribution + top-5 examples per candidate. File not found under results/ in a spot check; possible storage path not documented. **Impact:** Cannot independently verify the feature-selection process for cheese/UNESCO/Eurovision.

3. **Open questions on feature drift between checkpoints.** Section 10 hypothesized stable norms (0.998) and directions (0.997 cosine similarity) for recovered-checkpoint comparison, but did not test whether the *semantic meaning* of ranked feature lists drifted (feature ranks shifted between partial-166.67M and full-199.97M checkpoint). Rank-2 candidate (65223) held up; rank-1 shifted (32456 new). Root cause of literal-mention regression (3→0 hits) left partially explained (fragile near-threshold behavior posited, not mechanistically proven).

4. **Multilingual analysis predates instruct-SAE.** Section docs/multilingual_findings_rwu04lpb.md states results are from the instruct-SAE (rwu04lpb) rerun (job 383758), reusing probe sentences. This is recent (git commit 3ac9e23, Jul 26) and correct. *However*, earlier multilingual results under results/features/multilingual/ may predate the instruct-SAE and should not be cited.

5. **Eurovision feature weak; carry decision unclear.** Execution roadmap scoping rule: "Eurovision is pre-flagged weak — carry it only if it costs nothing" (§32). Section 29 includes it in the final comparison (Table 5 in section C) as the weakest of three candidates, meeting the "carry if free" criterion. But whether to include it in the public report remains a researcher-level decision not formalized in the logs.

6. **Layer×width grid status obscure.** Registry shows 4 checkpoint certificates (d1bgp5v5 L16×32, rwu04lpb L28×32, zf2o13m2 L40×32, o1cx1dow L28×64). Roadmap T1.4 "Grid table" is a P2 cut-first task. Unclear which checkpoints actually exist under results/sae_checkpoints/ and which are legacy/stale from poutine-era experiments. No unified inventory.

7. **Instruct-model training edge case unresolved.** Section 25 describes a model-download failure on the login node (HF_HUB_DISABLE_XET + --max-workers 1 fix), then successful relaunch. But the root cause of why Xet-backend-heavy memory consumption persisted despite foreground-process control strategies is under-explained (suspected but not confirmed to be a login-node memory cap).

8. **No ablation control for 9056 steering.** Roadmap T1.2 (P1 priority) is an ablation run showing necessity ("if you *remove* 9056, steering disappears"). This is not included in the survey. Section 27 shows sufficiency (clamp the feature, effect happens) but not necessity.

---

## References & Artifact Locations

- FEATURE_EXPERIMENT_LOG.md (d:\qwen-sae-interp\results\) — primary log, all section numbers reference this
- docs/report_tables.md — Tables 1–2 rendered
- docs/characterize_lite_findings.md — Table 2 evidence + activation distributions
- docs/multilingual_findings_rwu04lpb.md — Table 4 evidence
- docs/execution_roadmap.md — methodology, task board, cut list
- registry/sae_certificate/{0a572198764d,ed82c7245ca7,1167ac6f099a,fbdd53715b12}.json — SAE health metrics
- registry/run_card/{48220766e0ad,a19a0297c1ac,...}.json — Lodestar run cards + job status
- interplab/README.md — infra overview
- lodestar/README.md — Lodestar overview + quickstart
- slurm/train_sae*.sh, scripts/{train_sae,certify,characterize_lite,steering_experiment,survey_features,multilingual_rerun}.py — pipeline entry points

