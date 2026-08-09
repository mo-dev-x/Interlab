# Report Architecture -- Qwen2.5-14B SAE Golden Gate Claude Reproduction

## PART 1 -- Methodology Choice

**Backbone: modified IMRaD + engineering-report hybrid, not pure academic IMRaD.** This is an internship deliverable reporting a pipeline with real infra deliverables, not a paper defending one hypothesis -- Methods needs a "Lessons from the Pipeline" subsection that pure IMRaD has no slot for.
**Pyramid Principle inside Results:** lead each subsection with the claim/number, then the supporting evidence -- reviewers (supervisor + interp researchers) want the headline (9056@55, 5.38/5.50) before the sweep table, not after.
**Hourglass for the whole document:** open wide (GGC, why open-weight reproduction matters), narrow through Qwen-specific Methods/Results/Negative-Results, widen again in Discussion (what this implies for SAE practice generally). This is the constraint-9 requirement made structural, not just a framing sentence.
**Claim-to-Evidence-to-Reasoning as the paragraph-level discipline** inside every Results/Negative-Results subsection (not a separate section) -- keeps every quantitative claim tethered to an inventory pointer inline, which is what makes the Evidence Ledger auditable rather than decorative.
**Negative Results gets its own top-level section**, sequenced immediately after Results, per editorial constraint 4 -- reads as a peer of Results, not a limitations dump.
**Threats to Validity is a dedicated section** (not folded into Discussion) because this is a reproduction study -- internal/external/construct threats are distinct and reviewers will look for the section by name.
**Reproducibility Statement is a dedicated section** leveraging Interlab specifically (hashes, ED-32 pinning) -- this is the projects actual infra contribution, so it earns real estate rather than a footnote.
**Evidence Ledger is an appendix, not inline** -- keeps the narrative readable while giving the supervisor an audit table; every ledger row cites inventory pointers so it doubles as a compromise-tracking device (confidence column carries the overclaim guards).
**Infrastructure Contributions gets its own section**, placed after Negative Results and before the rigor apparatus (Threats/Repro) -- it is a first-class deliverable per the honest frame, not Methods trivia.

---

## PART 2 -- Section Architecture

### 0. Title + Abstract -- target 150 words
- Purpose: One-paragraph orientation stating the honest frame verbatim and previewing the four pillars (headline reproduction, triangulated feature-quality methodology, negative results, infra).
- Claims: (i) systematic single-model reproduction of GGC-style steering on Qwen2.5-14B(-Instruct); (ii) feature 9056 at scale 55 is the headline result; (iii) three independent measurements triangulate feature quality; (iv) four rigorous negative results reported as findings; (v) two infra contributions (Interlab, Lodestar).
- Evidence: Inv D bullet 1 (9056 headline); Inv C Table 3 (5.38/5.50); Inv J (both toolkits); Inv E (all four negatives, named not detailed).
- Figures/Tables: none (abstract text only).
- Writer notes: State the honest frame from constraint 1 near-verbatim -- do not say "reproduced GGC across models." No hedging language about the cross-model arm here beyond one clause ("staged, not run -- see Future Work").

### 1. Introduction -- target 550 words
- Purpose: Hourglass open -- GGC background, why open-weight/quantitative reproduction is a distinct contribution from Anthropics closed demo, statement of scope and honest frame, roadmap of the report.
- Claims: Qwen2.5-14B/-Instruct chosen as the open-weight target (Inv A); the project scope is single-model with a cross-model arm staged but not executed (Inv I); the report adds quantitative LLM-judged evaluation and triangulated feature-quality assessment that the original GGC blog post did not publish in comparable form.
- Evidence: Inv A (model identity); Inv I (Gemma Scope arm "staged, not run").
- Figures/Tables: none.
- Writer notes: GGC background itself is external knowledge, not inventory-sourced -- cite the public Anthropic post by name but do not fabricate numbers from it. End with an explicit paragraph restating constraint 1s honest frame so the supervisor sees the scope boundary in the first page.

### 2. Methods

#### 2.1 Pipeline and Provenance Overview -- target 150 words
- Purpose: One-paragraph map of the nine pipeline stages and the Interlab registry that threads them together.
- Claims: Nine-stage pipeline (training -> activation-store QA -> certification -> feature search -> characterization -> steering -> LLM-judged eval -> multilingual -> report assembly); Interlab provides content-addressed provenance across all stages.
- Evidence: Inv B (pipeline stages list, script entry points); Inv B "Provenance framework" bullets.
- Figures/Tables: none (a simple pipeline diagram is optional/nice-to-have, not sourced from inventory -- skip unless Writer has bandwidth).
- Writer notes: Keep this a map, not a re-explanation -- each stage gets its own detail in 2.2-2.7. Name the scripts (train_sae.py, survey_features.py, etc.) once here for reference.

#### 2.2 Model and Training Runs -- target 200 words
- Purpose: Document the four SAE training runs and the checkpoint-ID discipline the rest of the report depends on.
- Claims: Four checkpoints trained (9odeg5hb L24, de575ae6 L24, alhjs2qg L28, rwu04lpb L28-instruct); TopK architecture throughout; dataset switch pile-10k to FineWeb forced by trust_remote_code removal + Tamia compute-node internet restrictions.
- Evidence: Inv A full checkpoint table; Inv A "Key Training Details" (dataset switch); Inv F item 5 (dataset loading obstacles, same root cause).
- Figures/Tables: Reproduce Inv As checkpoint table as Table A.
- Writer notes: **Overclaim guard (c) placement:** flag here in one sentence that training-run IDs and certified SAE IDs overlap only at rwu04lpb -- full explanation deferred to Reproducibility Statement (Section 7) to avoid repeating the caveat twice at length.

#### 2.3 SAE Certification -- target 150 words
- Purpose: Explain what "certified" means (L0, EV, dead-feature %, FVU, band assignment) and report the four certificates.
- Claims: Four SAEs certified; three amber, one green (o1cx1dow); CE-recovered range 0.9785-0.9938.
- Evidence: Inv C Table 1; Inv J (certification lane SS4-SS8, ED-32 baseline enforcement).
- Figures/Tables: Table 1 (Inv C Table 1); fig_sae_certification.png (Inv G).
- Writer notes: Note band verdicts are a health gate, not a feature-quality signal -- feature quality is established separately in Results section 4. Avoid implying "green > amber" matters for the downstream cheese result (rwu04lpb is amber).

#### 2.4 Feature Discovery: Concept-Probing and Open-Ended Survey -- target 200 words
- Purpose: Describe find_features.py (deprecated, concept-driven) superseded by survey_features.py (open-ended, peak x sparsity ranking).
- Claims: Survey ranks all features by peak_activation x (1-nonzero_fraction); top-150 candidates from job 358227 on rwu04lpb produced cheese/UNESCO/Eurovision.
- Evidence: Inv B (both scripts); Inv F item 3 (outlier-norm masking fix, cross-reference to 2.8); Inv K item 2 (survey JSON not locally verified).
- Figures/Tables: none (results/feature_survey.json referenced but not reproduced as a table -- status caveated).
- Writer notes: **Overclaim guard (e):** state plainly that the survey method is described from the experiment log, not from an independently re-run or locally verified artifact; cite job ID 358227; note the files residency is on the cluster, not confirmed present locally. Do not present the top-150 list as a verified table.

#### 2.5 Characterization and Selectivity Methodology -- target 200 words
- Purpose: Describe characterize_lite.pys ad hoc selectivity methodology and the rate-matched control design.
- Claims: 5,000 FineWeb docs, 1,712,777 token positions, population median firing rate 4.03e-05; selectivity = firing-rate multiple over median plus rate-matched control comparison.
- Evidence: Inv C Table 2 header stats and method; Inv H item 6 (ad hoc, not production infra; n=395 for Eurovision has low resolution).
- Figures/Tables: none here (activation-distribution figures placed in Results 4.2 where they support the triangulation claim).
- Writer notes: Flag the ad hoc/production-infra distinction explicitly and early -- this qualifies every selectivity number that follows without needing to repeat the caveat per-number.

#### 2.6 Steering and LLM-Judged Evaluation (Lodestar) -- target 300 words
- Purpose: Describe the encode-override-decode steering hook, scale-sweep design, and the Lodestar six-rubric judge.
- Claims: Steering via feature clamping at scales 40-150 typical; Lodestar judges coherence, concept_relevance, prompt_adherence, integration_naturalness via claude-sonnet-4-5-20250929 with SQLite caching and budget guards; optimal-operating-point search finds max relevance subject to a coherence floor.
- Evidence: Inv B (steering_experiment.py, Lodestar entry); Inv J (Lodestar capability list, judge model, cost ~$6.84 for Montreal eval).
- Figures/Tables: none (sweep results appear in Results 4.1-4.2).
- Writer notes: **Overclaim guard (b), important pitfall:** Inv J lists "repetition consistency (same text judged twice)" as a Lodestar *capability*, and Inv D separately claims "Lodestar judge reliability confirmed" -- but that D claim is about the sweep_hash/experiment-grouping fix correctly separating ablation from steering conditions, **not** about measuring inter-judgment repeatability of the judge itself on these runs. Do not conflate the two. State explicitly: judge repeatability was not measured on these specific runs; describe the judges design, not its validated reliability.

#### 2.7 Multilingual Methodology -- target 150 words
- Purpose: Describe multilingual_rerun.pys cross-language overlap method (top-20 features by mean activation per concept/language, pairwise Jaccard).
- Claims: Four concepts (world_cup, quebec, poutine, couscous) x four languages (en/fr/zh/ar), 10-25 probe sentences per language, instruct-SAE (rwu04lpb) only.
- Evidence: Inv C Table 4 method note; Inv K item 4 (instruct-SAE rerun, job 383758, is the valid/citable version; pre-instruct-SAE multilingual results under results/features/multilingual/ must not be cited).
- Figures/Tables: none here (Table 4 + figure placed in Results 4.3).
- Writer notes: State the instruct-SAE-only provenance rule as a hard citation constraint, not a soft caveat -- this prevents an easy mistake of pulling an older multilingual number into the report.

#### 2.8 Lessons from the Pipeline: Methodological Fixes -- target 380 words
- Purpose: Present the seven methodological fixes as reusable practitioner lessons -- this is the engineering-report element bolted onto IMRaD, justified in Part 1.
- Claims: (1) FFFD replacement-character bug silently corrupted 5% of judgments, concentrated at scale=80 (37.5%); (2) sweep_hash conflated ablation (scale=0) with steering sweeps, fixed via an experiment grouping column; (3) outlier-norm masking was required before peak x sparsity survey ranking meant anything (top-30 was previously dominated by one artifact position); (4) missing chat-template application made base-model steering look broken when the real issue was continuation-vs-instruction mismatch; (5) dataset-loading obstacles (trust_remote_code removal, 50TB silent full-shard resolution, offline compute nodes) forced the pile-10k to FineWeb switch and streaming+islice workaround; (6) an SAE dtype cascade bug silently defaulted activation buffers to float32 regardless of configured bfloat16; (7) a specificity-ratio epsilon floor produced meaningless hundred-million-fold ratios when a feature never ranked top-100 against baseline probes.
- Evidence: Inv F items 1-7, verbatim mechanism and fix location for each.
- Figures/Tables: none.
- Writer notes: Frame as "what wed tell the next person running this pipeline," not as apologies. Each fix should read as a one-paragraph problem-root cause-fix-impact unit -- this is the section most likely to be useful to another lab reproducing the setup, say so.

### 3. Results

#### 3.1 Headline Result -- Feature 9056 (Cheese) Steering Reproduction -- target 600 words
- Purpose: Lead with the number (Pyramid Principle) -- this is the GGC-style reproduction the whole report is built around.
- Claims: At scale 55, feature 9056 produces identity-substitution text ("Im an aged cheese...") while remaining prompt-responsive; coherence 5.38, concept_relevance 5.50, prompt_adherence 3.13, integration_naturalness 1.75; widest operating window of the three tested features across the 40-150 sweep.
- Evidence: Inv C Table 3 (optimal point + full 40-150 sweep sub-table); Inv D bullet 1.
- Figures/Tables: results/steering_sweep_instruct/cheese_curds_fine/steering_scale_curve.png; results/steering_sweep_instruct/cheese_curds_mid/steering_scale_curve.png; qualitative quotes from results/steering_sweep_instruct/cheese_curds_fine/example_generations.md (Inv G).
- Writer notes: **Overclaim guard (a), mandatory sentence:** this evidence establishes sufficiency only -- clamping 9056 produces the effect -- and no ablation/necessity control (removing 9056 and checking the effect disappears) was run; never use the word "necessary." Present the full sweep table so the reader sees the non-monotonic coherence/relevance trade-off (e.g., scale 60 relevance 7.75 but coherence drops to 4.50) rather than just the cherry-picked optimum.

#### 3.2 Feature-Quality Triangulation -- target 700 words
- Purpose: The methodological centerpiece -- show that three independent measurements agree on the same quality ranking, which is a claim about the *method*, not just the features.
- Claims: (1) survey/characterize_lite monosemanticity labels rank 9056 "clean monosemantic" above 47735 "clean monosemantic" above 44189 "weak/marginal"; (2) Lodestar-judged steering shows 9056 clean-and-responsive vs. 47735 high-relevance-but-low-adherence/naturalness ("clean-but-override": relevance 8.13, adherence 1.63, naturalness 1.13) vs. 44189 weakest across the board; (3) selectivity vs. rate-matched control confirms the same order (9056 max 47.50 vs. control 90537s 21.4; 44189 max 8.50 vs. control 2002s 28.1, i.e. 44189 fails to beat its own control).
- Evidence: Inv C Table 2 (selectivity + control checks); Inv C Table 3 full table (all three features); Inv D bullet on monosemanticity.
- Figures/Tables: fig_feature_selectivity.png; feature_9056_actdist.png; feature_47735_actdist.png; feature_44189_actdist.png; results/steering_sweep_instruct/unesco_heritage/steering_scale_curve.png; results/steering_sweep_instruct/eurovision/steering_scale_curve.png (all Inv G).
- Writer notes: **This is where constraint 2/3s ranking must be stated explicitly and argued, not implied.** Frame Eurovision (44189) as a *correctly rejected* candidate -- its control check (feature 2002 rate-matched: max 28.1 vs. 44189s 8.50) is itself evidence the triangulation method works, not a failure of the pipeline. Cite Inv K item 5 (roadmaps "carry only if free" scoping rule) to show the rejection was a deliberate, documented decision.

#### 3.3 Multilingual Cross-Language Feature Overlap -- target 450 words
- Purpose: Report the concept-globality ordering and pre-empt the poutine misreading before it can be made.
- Claims: Cross-lingual top-20 feature overlap is concept-dependent and ordered by concept globality: world_cup 0.66 mean pairwise Jaccard (13/20 shared) above quebec 0.62 (12/20) above poutine 0.51 (10/20) above couscous 0.38 (4/20).
- Evidence: Inv C Table 4; Inv D bullet 4.
- Figures/Tables: fig_multilingual_overlap.png (Inv G).
- Writer notes: **Overclaim guard (d), mandatory paragraph immediately after the table:** poutines 0.51 Jaccard is a *set-level* overlap of the top-20 most-activated features per language -- it says the model represents "poutine-adjacent" content similarly across languages at the population level, not that a *single monosemantic poutine feature* exists. This does not contradict section 4.1s negative result (no clean poutine feature found after 16+ targeted searches); the two findings operate at different units of analysis (feature-set overlap vs. single-feature cleanliness) and must not be read as tension. Per constraint 8, note the concept-globality ordering is a qualitative interpretive link, not one validated against any prevalence/census numbers -- the inventory contains none, so do not invent a quantitative correlation.

#### 3.4 SAE Certification Health (cross-reference summary) -- target 200 words
- Purpose: Short results-facing recap of certification numbers now that the reader has seen what "certified" buys downstream (feature quality, steering).
- Claims: All four certified SAEs pass health gates (CE recovered >= 0.978, dead-frac <= 0.002 except zf2o13m2 at 0.0000); rwu04lpb (the SAE underlying every headline/triangulation result) is amber, CE 0.9884, dead-frac 0.0008.
- Evidence: Inv C Table 1.
- Figures/Tables: none new (reference Table 1/fig_sae_certification.png already shown in Methods 2.3 -- do not duplicate the figure, cross-reference it).
- Writer notes: Keep this short; its job is to remind the reader the headline result sits on a health-gated checkpoint, not to re-teach certification.

### 4. Negative Results

#### 4.1 No Poutine Feature Across 16+ Attempts -- target 450 words
- Purpose: Report the poutine search as a completed, honest negative result with an identified mechanism.
- Claims: 16 distinct search/steering attempts across two checkpoints (9odeg5hb, de575ae6) failed to produce a clean poutine feature; root cause is training-corpus coverage (pile-10k contained little poutine content); doubling dictionary capacity (32x FineWeb) did not fix it (best candidate 96339 = generic "fries," not poutine-specific); specificity-ranking metric (464M x score) is a trap -- it proves probe-set uniqueness, not monosemanticity.
- Evidence: Inv E "Poutine Feature" full subsection; Inv D bullet 3 (Celine Dion contrast -- concept salience predicts discoverability); Inv H item 2.
- Figures/Tables: results/features/poutine_candidates.json and results/features_v2/ referenced as artifact provenance, not reproduced as tables (Inv G).
- Writer notes: State the conclusion the log itself draws: the pipeline works (cheese, Celine Dion are clean) -- poutine is a genuinely hard target because of concept frequency/coverage in training data, not a pipeline failure. This is the concept-coverage-bounds-discoverability thread picked back up in Discussion section 8.

#### 4.2 Montreal/Quebec Bilingual Entanglement -- target 500 words
- Purpose: Report the reversal (feature 10413 looked clean in section 13, was overturned in sections 19-22) and the four-angle convergence that confirmed entanglement.
- Claims: No clean, monosemantic Montreal/Quebec place feature exists at layer 24 on either checkpoint, confirmed via (1) logit attribution showing only 1/10 top tokens literally "Montreal", (2) high-scale steering (175-700) surfacing translation/language-course content instead of geography, (3) English Montreal-scoped probes still top-ranking a generic "Canada" feature, (4) Chinese probes with matched baseline reproducing the same entanglement pattern in a different token space.
- Evidence: Inv E "Montreal/Quebec" full subsection; Inv C Table 5; Inv H items 1, 5.
- Figures/Tables: none new for this subsection specifically (Table 5 is the reproducible table; no dedicated figure listed in Inv G beyond the solo-steering curve used in 4.4).
- Writer notes: Emphasize the self-correction -- the original section 13 claim was published internally, then overturned by the teams own later analysis. This is a credibility asset (shows the negative-results discipline is real), not something to soften. The Chinese-probe angle is the strongest piece of evidence; give it real space, not a throwaway clause.

#### 4.3 Base-Model SAE Non-Transfer to Instruct-Model Geometry -- target 350 words
- Purpose: Report the fresh, practically important finding that a base-model SAE checkpoint does not transfer to the instruct model at the same layer index.
- Claims: Feature 19815 (singing) reliably steers Qwen2.5-14B base at scale 110 but has zero effect on Qwen2.5-14B-Instruct with the identical SAE checkpoint; instruction-tuning/RLHF reorganizes layer-28 residual-stream geometry enough to break feature identity; reproducing the full GGC effect required training a fresh SAE (rwu04lpb) directly on the instruct models own activations.
- Evidence: Inv E "Base-Model SAE Non-Transfer" subsection; Inv H item 3.
- Figures/Tables: none listed in Inv G specific to this finding.
- Writer notes: Frame explicitly as a **fresh, generalizable methodological finding** per constraint 4(c) -- "if you SAE the base model, budget for RLHF geometry drift before assuming portability to the chat variant" -- not merely a local troubleshooting note. This is single-feature evidence (19815 only); say so rather than implying it was tested broadly.

#### 4.4 Steering Breaks Fluency Before Topic at High Scale -- target 300 words
- Purpose: Report that for an entangled feature, pushing scale up trades fluency for topicality in the wrong order -- it degrades before it ever reaches the "obsessed but readable" GGC-demo effect.
- Claims: Montreal feature 10413 at scales 175-500 surfaces translation/language-course artifacts, then collapses into word salad, never achieving on-topic-and-fluent text simultaneously; contrasts with feature 9056s cleaner (though still non-monotonic) coherence/relevance trade-off in section 4.1.
- Evidence: Inv E Montreal angle 2 (section 21); Inv H item 4.
- Figures/Tables: results/steering_montreal_solo/steering_scale_curve.png (scales 50-150, pre-correction); results/lodestar_montreal_eval/report.html (coherence-relevance frontier, scale=80 optimum) (Inv G).
- Writer notes: Explicitly connect back to 4.1/4.2: this is a property of the *entangled* feature (Montreal), not evidence that clean features (cheese) share the same failure mode at high scale -- dont let the reader over-generalize this into "all steering breaks at high scale."

### 5. Infrastructure Contributions -- target 400 words
- Purpose: Present Interlab and Lodestar as first-class deliverables of the internship, distinct from the scientific results above.
- Claims: Interlab provides content-addressed provenance (checkpoint identity hashing ED-27, ULP-bound golden tests ED-31, SAE-stack migration ED-33, corpus-streaming fixes ED-34) across a four-stage certification lane with fail-closed version enforcement; Lodestar provides a six-rubric LLM-judge harness with Pareto-frontier/optimal-operating-point search, SQLite judge caching (WAL-mode fix for concurrent access), and budget-guarded cost tracking (~$6.84 for the Montreal eval, 161 generations/2898 judgments).
- Evidence: Inv J full section (both Interlab and Lodestar subsections).
- Figures/Tables: none new (registry artifact-type list can be rendered as a small table if space allows).
- Writer notes: Keep this section proud but factual -- these are engineering deliverables, describe what they do and what bug they fixed, not marketing language. This section is what makes the Reproducibility Statement (section 7) possible; say so explicitly to link the two.

### 6. Threats to Validity

#### 6.1 Internal Validity -- target 180 words
- Purpose: Confounds within the causal claims made about specific features.
- Claims: 9056s steering evidence is sufficiency-only (no necessity/ablation control); characterize_lite selectivity stats for rare concepts (Eurovision n=395) have low statistical resolution; the FFFD and sweep_hash bugs (now fixed) demonstrate that undiscovered similar artifacts are a live risk class, not a closed question.
- Evidence: Inv K item 8; Inv H item 6; Inv F items 1-2 (as evidence the risk class is real).
- Figures/Tables: none.
- Writer notes: Do not re-litigate the fixes in detail (already in 2.8) -- cite them only as evidence of the *class* of risk.

#### 6.2 External Validity -- target 160 words
- Purpose: Limits on generalizing beyond this single model/checkpoint set.
- Claims: Single model family (Qwen2.5-14B/-Instruct only); cross-model arm (Gemma Scope) staged but not run; only four certified checkpoints exist and the layer x width grids completeness is unclear (unknown how many legacy/stale checkpoints exist); multilingual coverage limited to four languages and four concepts.
- Evidence: Inv I; Inv K item 6; Inv C Table 4.
- Figures/Tables: none.
- Writer notes: This is where the honest frame from constraint 1 gets its technical teeth -- one sentence should say plainly "these findings should not yet be read as claims about SAE interpretability in general; they are Qwen2.5-14B findings."

#### 6.3 Construct Validity -- target 160 words
- Purpose: Whether the measurement instruments actually measure what they are labeled as measuring.
- Claims: LLM-judge coherence/relevance scores have not had their own repeatability measured on these runs (judge design described, not validated reliability); the feature-survey process that surfaced cheese/UNESCO/Eurovision is described from the log only, not independently re-verified (survey JSON not located locally); the specificity-ratio metric was shown to produce meaningless values under an epsilon-floor edge case, motivating a switch to raw activation means.
- Evidence: Inv K items 2, 10 (per editor); Inv F item 7.
- Figures/Tables: none.
- Writer notes: This subsection is the natural home for restating overclaim guards (b) and (e) in validity-threat language, complementing (not duplicating) their first appearance in 2.6/2.4.

### 7. Reproducibility Statement -- target 380 words
- Purpose: Concretely ground "reproducibility infrastructure" from the honest frame in artifact-level detail.
- Claims: Registry artifact types (sae_checkpoint A5, sae_certificate A6, characterization_manifest A7, feature_certificate A8, intervention_result A9, claim_report A11) content-address every stage; certificate hashes (0a572198764d, ed82c7245ca7, 1167ac6f099a, fbdd53715b12) pin the four certified SAEs to exact weight+config states; ED-32 pins the full software stack (sae-lens 6.44.2, transformers 5.12.1, transformer-lens 3.2.1, datasets 5.0) with fail-closed enforcement on mismatch; RunCard finalization means job absence is itself a recorded fact, not silent gap.
- Evidence: Inv J (registry artifact types, ED-32); Inv C Table 1 (hashes); Inv A (checkpoint IDs).
- Figures/Tables: none new (hash table already given as Table 1).
- Writer notes: **Overclaim guard (c), full statement belongs here:** spell out explicitly that training-run IDs (9odeg5hb, de575ae6, alhjs2qg, rwu04lpb) and certified-SAE IDs (d1bgp5v5, rwu04lpb, zf2o13m2, o1cx1dow) intersect at exactly one ID -- rwu04lpb -- and that the other three certified SAEs do not have a documented training-run counterpart in this inventory; do not imply a unified four-checkpoint training lineage.

### 8. Discussion -- target 600 words
- Purpose: Hourglass close -- widen from Qwen-specific findings to general claims about SAE-based interpretability practice.
- Claims: (1) feature quality is measurable and predictable ahead of steering, via triangulation of survey/selectivity/judged-steering signals that agree with each other (section 4.2) and correlate with concept salience in training data (Celine Dion vs. poutine, section 5.1); (2) concept coverage in the training corpus bounds what is discoverable at all -- a well-represented global concept (cheese, world_cup) gets a clean feature and a niche one (poutine) does not, regardless of dictionary width; (3) instruction-tuning/RLHF reorganizes residual-stream geometry enough that SAEs trained on a base model cannot be assumed portable to its chat variant (section 5.3) -- practical implication: budget for a fresh instruct-model SAE rather than reusing a base-model checkpoint.
- Evidence: Inv D bullets 1-4 (synthesis); Inv E all three mechanism-bearing negatives; Inv C Tables 2-4 (cross-reference).
- Figures/Tables: none new -- this section synthesizes, does not introduce new evidence.
- Writer notes: Explicitly reconnect to GGC in the final paragraph: the identity-substitution effect is reproduced quantitatively (9056), but the "obsessed yet fluent at high scale" quality of the public GGC demo was not matched for entangled features (section 4.4) -- state this as an honest scope boundary, echoing constraint 1, rather than letting the section end on an unqualified success note.

### 9. Future Work -- target 250 words
- Purpose: List what was staged/scoped but not executed, so the supervisor sees intentional cuts rather than gaps.
- Claims: Gemma Scope cross-model arm (feature discovery/validation/steering/multilingual on Gemma-2-9B, fallback Gemma-2-2B) is staged, not run; circuits work (circuit-tracer on Gemma-2-2B, attribution-patching/ablation on Qwen 9056) is timeboxed and not executed; layer x width grid table is a documented P2 cut; **highest-priority item: the 9056 ablation/necessity control (roadmap T1.2, P1)** was not run and directly resolves the sufficiency-only overclaim guard from section 4.1.
- Evidence: Inv I (Gemma Scope, circuits, grid table); Inv K item 8 (ablation control).
- Figures/Tables: none.
- Writer notes: Order by priority, not by roadmap chain letter -- put the 9056 ablation control first since it directly answers this reports own overclaim guard, not last as a roadmap afterthought.

### Appendix A: Evidence Ledger -- target ~350 words (table + short preamble)
- Purpose: One-row-per-major-claim audit table so every quantitative or causal statement in the report traces to an artifact and a stated confidence.
- Claims: N/A (this section indexes claims made elsewhere; it introduces no new claims).
- Evidence: aggregates pointers used throughout sections 3-9.
- Figures/Tables: Ledger table, columns = Claim | Supporting artifact(s) | Confidence | Rationale. Suggested rows (Writer may add, must not remove): 9056 sufficiency (HIGH, full sweep + cert SAE); triangulation ranking 9056>47735>44189 (HIGH, 3 independent methods); Eurovision correctly rejected (MEDIUM, n=395 low resolution); no clean poutine feature (HIGH, 16+ attempts/2 checkpoints, mechanism identified); Montreal/Quebec entanglement (HIGH, 4 convergent angles); base-model non-transfer (MEDIUM, single-feature case study); fluency-breaks-before-topic at high scale (MEDIUM, Montreal-specific, not cross-validated on clean features); multilingual concept-globality ordering (MEDIUM, 4 concepts/4 langs, no prevalence validation -- qualitative link); poutine Jaccard 0.51 not equal to feature existence (HIGH, logical/methodological point); SAE certification health (HIGH, hash-addressed registry); checkpoint-ID lineage limited to rwu04lpb (HIGH, direct ID comparison); feature-survey process (LOW-MEDIUM, described from log only, job 358227, not locally verified); Lodestar judge repeatability (NOT MEASURED, capability exists but unexercised this run); 9056 necessity/ablation (ABSENT, flagged future work); layer x width grid completeness (LOW, unclear legacy/stale status); Attempt-8 cluster artifact residency (MEDIUM, ~80% Monte Carlo estimate, unverified).
- Writer notes: This table IS the overclaim-guard enforcement mechanism -- every guard from the editorial constraints should resolve to a specific row with an honest (often non-HIGH) confidence value. If a claim in the body text has no ledger row, that is a bug in the draft, not an acceptable omission.
