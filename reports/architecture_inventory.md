# Architecture Inventory: Interlab + Lodestar Infrastructure

**Date:** 2026-07-26 | **Evidence phase:** SCOUT pass 2 | **Artifact types:** 11 defined, 5 populated

---

## A. Interlab — Problem Statement & Motivating Failures

**Source:** `docs/infrastructure_architecture.md` §Gap Analysis; experiment log (FEATURE_EXPERIMENT_LOG.md sections 1–2)

The repository audit and replication review identified three blocking infrastructure gaps that lengthened feature-work into "two blocked months":

1. **Silent SAE health failure:** Pipeline cannot distinguish well-trained from undertrained SAEs. TopK's fixed L0=100 actively hides sickness L1 training would surface. Feature work ran on uncertified instruments.
2. **Incomparable feature derivations:** Every script contains its own private version of steering hooks and concept probes. A steering bug (residual-stream replacement with reconstruction, non-identity form, raw unitless clamps) was copied across multiple experiments, making results un-comparable and invalidating weeks of work.
3. **Corpus identity erasure:** Concept probe sentences hardcoded inside `scripts/find_features.py`; pile-10k vs. pile-uncopyrighted swap happened in prose only (experiment log section 1b). No canonical answer to "how often did the SAE see poutine?"

**Status:** DESIGNED—architecture document drafted as the laboratory specification; implementation began July 2026.

---

## B. Interlab — Design Philosophy & Key Concepts

**Source:** `docs/infrastructure_architecture.md` §Design Philosophy, §The Artifact Ontology and Contract Model

| Concept | Definition | Status | Evidence |
|---------|-----------|--------|----------|
| **Certificates, not vibes** | Every artifact carries a machine-generated pass/fail gate; claims chain certificates; incomplete chains auto-stamped `UNCERTIFIED`. | IMPLEMENTED | SS4 G1 (sae_certificate), SS6 G2 (feature_certificate) written; SS9 chain assembly logic in `interplab/reports/chain.py` |
| **Explore freely, claim expensively** | Gates block *claims* (reports, papers), not experiments; exploration never slowed by infrastructure. | PARTIAL | Gates documented; claim vs. explore mode not yet enforced in practice (no live A9 / A11 yet). |
| **One implementation per concept** | Shared libraries for steering, statistics, concepts; no reimplementation per script. | IMPLEMENTED (trunk) | SS7 `interplab.interventions` (hooks, control_arms, InterventionSpec), SS9 stats `interplab.stats`, core uris/hashing/envelope shared across all subsystems. |
| **Content-addressed identity** | Artifacts hashed at creation; provenance via artifact hashes, not paths. | IMPLEMENTED | `interplab/core/hashing.py` implements all strategies (RFC 8785 JCS for registry JSON, sha256 for heavy dirs); schema D1 in force. |
| **Immutability via derivation** | Status never stored; certified/uncertified derived at chain-assembly time by querying registry for valid certificates. | IMPLEMENTED (core) | `interplab/reports/chain.py` assembly logic; A6/A8 design forbids mutable state fields (artifact_type, schema_version, subject, payload only). |
| **Artifact schemas as contracts** | Subsystems communicate only via versioned data schemas, not internal APIs (exception: SS5 search API, SS7 hook library). | IMPLEMENTED | All 11 artifact schemas in `schemas/*/v1.schema.json`; every subsystem reads schema-validated JSON from `registry/`. |

**Status:** IMPLEMENTED (core design) + PARTIAL (enforcement in live experiments).

---

## C. Interlab — Artifact Ontology

**Source:** `docs/infrastructure_architecture.md` §The Artifact Ontology; `implementation_blueprint.md` §4 Artifact Specifications

| ID | Artifact Type | Schema File | Status | Registry Count | Producers | Role |
|----|---|---|---|---|---|---|
| A1 | `corpus_manifest` | `corpus_manifest/v1.schema.json` | IMPLEMENTED | 1 | SS1 census | root link; defines consumed token stream by recipe hash |
| A2 | `concept_battery` | `concept_battery/v1.schema.json` | PARTIAL | — (git-tracked YAML) | researcher + SS1 | multilingual probes/negatives; v1 probes_only (no word-absent) |
| A3 | `census_report` | `census_report/v1.schema.json` | IMPLEMENTED | 1 | SS1 | per-concept frequency over A1; ED-28 stream semantics in force |
| A4 | `store_manifest` | `store_manifest/v1.schema.json` | DESIGNED | 0 | SS2 | QA verdict over activation store; schema drafted, no live jobs yet |
| A5 | `sae_checkpoint` | `sae_checkpoint/v1.schema.json` | IMPLEMENTED | 4 (backfilled) | SS3 training / backfill | weights identity (cfg.json + sae_weights.safetensors); ED-27/33 provenance fields |
| A6 | `sae_certificate` | `sae_certificate/v1.schema.json` | IMPLEMENTED | 4 | SS4 certify | GATE G1; metrics (ce_recovered, fvu, dead_fraction, max_decoder_cosine_p999, density hist); bands v1 |
| A7 | `characterization_manifest` | `characterization_manifest/v1.schema.json` | PARTIAL | 0 | SS5 indexer | feature index reference (corpus_max, firing_rate, decile_boundaries, autointerp_label); no live indexer yet |
| A8 | `feature_certificate` | `feature_certificate/v1.schema.json` | DESIGNED | 0 | SS6 validate | GATE G2; specificity/sensitivity/selectivity/probe; schema written, no live validator yet |
| A9 | `intervention_result` | `intervention_result/v1.schema.json` | DESIGNED | 0 | SS7 steer + SS8 judge | generations + blinding + Lodestar scores; immutable (judged artifacts become new A9'); schema drafted |
| A10 | `run_card` | `run_card/v1.schema.json` | IMPLEMENTED | 5 | all subsystems | provenance (run_id, config_hash, inputs/outputs, status, exit_code, environment); every job writes one |
| A11 | `claim_report` | `claim_report/v1.schema.json` | DESIGNED | 0 | SS9 report | GATE G4; assembled chain, statistics, certification stamp (CERTIFIED / DRAFT); schema drafted |
| A12 | `eval_compat_map` | `eval_compat_map/v1.schema.json` | DESIGNED | 0 | SS8 researcher | judge/rubric/prompt version compatibility classes; ED-2 decision structure, not yet authored |

**Summary:** 5/11 types populated. Full pipeline chain (A1→A11) designed; production stops at A6 (sae_certificate, GATE G1). SS7 (interventions), SS8 (Lodestar), SS9 (reports) awaiting live A8/A9 input.

---

## D. Interlab — Subsystem Architecture

**Source:** `docs/infrastructure_architecture.md` §Subsystem Specifications; `interplab/` package structure

| Subsystem | Package | Responsibility | Status | Evidence |
|-----------|---------|---|---|---|
| **SS1 Corpus & Concept** | `interplab.corpus` | manifests, battery, census | IMPLEMENTED | A1/A3 artifacts in registry; A2 schema written; ED-8/ED-9/ED-28/ED-31 rulings in effect |
| **SS2 Store QA** | `interplab.store_qa` | activation store health checks | DESIGNED | A4 schema exists; no live QA measurements; `qa.py` placeholder only |
| **SS3 SAE Training** | `interplab.training` | SAELens wrappers, manifest injection | PARTIAL | Wrappers not built in blueprint (researcher-gated); backfill job (A5 manifests) working; A5 schema complete |
| **SS4 SAE Certification** | `interplab.certification` | CE-recovered, FVU, bands, report card | IMPLEMENTED | 4 A6 certificates (rwu04lpb, d1bgp5v5, zf2o13m2, o1cx1dow); G1 gate running; bands v1 live |
| **SS5 Feature Characterization** | `interplab.characterization` | streaming indexer, search API, dashboards | PARTIAL | FeatureIndex search API interface defined; indexer code present; no A7 artifacts yet; dashboards not generated |
| **SS6 Feature Validation** | `interplab.validation` | specificity/sensitivity/selectivity/probe | DESIGNED | A8 schema written; job `validate.py` present; Lodestar judge integration stubs; no live certificates |
| **SS7 Intervention Engine** | `interplab.interventions` (TRUNK) | hooks (attach, delta form, controls) | IMPLEMENTED | Identity test + delta_golden golden fixture pass; G3 identity testing in CI; ED-34 gaps 1-2 fixed |
| **SS8 Behavioral Evaluation** | `interplab.evaluation` | blinding, Lodestar boundary, compat map | PARTIAL | Blinding module present; Lodestar adapter stubs; compat_map.py placeholder; no live judging yet |
| **SS9 Statistics & Reports** | `interplab.reports` (TRUNK) | chain assembly, bootstrap CIs, rendering | PARTIAL | `interplab.stats` implemented (bootstrap_ci, bh_fdr, seed_variance); chain assembly logic written; no live A11 yet |
| **SS10 Experiment Registry** | `interplab.registry` | RunCard index, artifact put/get | IMPLEMENTED | 5 RunCards in registry; run_card.py complete; manifest tracking working |
| **SS11 QA & Regression** | `tests/` | golden tests, schema validation, canary | IMPLEMENTED | 61 test files; 583 tests pass (ED-33); identity test (G3), battery snapshot, delta_golden, certification bands validation present |
| **SS12 Orchestration** | `scripts/` + `slurm/` | parameterized launchers, CLI | PARTIAL | 4 parameterized launchers (certify, characterize, validate, steer); census/store_qa/report/sync_registry CLI working; 11 scripts total |

**Key subsystem statuses:**
- **Certify lane (SS1–SS4, SS10, SS11):** IMPLEMENTED. Census, backfill, certification running.
- **Feature work (SS5–SS6):** PARTIAL. Schemas/APIs designed; no live artifacts.
- **Steering (SS7, SS9):** PARTIAL. Hooks/stats IMPLEMENTED (trunk); intervention experiments not yet in certification chain.
- **Evaluation (SS8):** PARTIAL. Lodestar integration stubs only; no live judging.

---

## E. Interlab — Design Decisions & Trade-Offs (ED Rulings)

**Source:** Implementation blueprint §ED-1 onward; git log with ED markers

| ED | Ruling | Status | One-line rationale |
|----|--------|--------|---|
| ED-5 (backfill + holdout) | Certification uses text-level holdout split, not stored activations; trains on full store, certifies on disjoint stream | IMPLEMENTED | CE-recovered requires fresh model forwards; identity tied to eval slice not activations |
| ED-8 (battery authorship) | Content (probes, negatives, translations) authored by researcher only, never by agents; extraction from code is mechanical | IMPLEMENTED | Prevents silent algorithmic form-generation; A2 schema enforces minimums per language status |
| ED-27 (checkpoint identity) | Identity = {cfg.json, sae_weights.safetensors} hash only; excludes trainer_state, optimizer, logs | IMPLEMENTED | Cfg determines how bytes become function; identity must be stable across training restarts |
| ED-28 (stream scope) | A1 corpus_manifest pins *consumed* token stream via recipe + subset_spec, not available dataset | IMPLEMENTED | Identity = recipe hash; census over exact stream; ED-31 replay invariant enforces reproducibility |
| ED-29 (model_dir_hash) | Base model ref carries unrestricted directory hash + immutable revision pin (hf:<repo>@<sha>) | IMPLEMENTED | Lab doesn't control model source; full directory hash mitigates missing behavior-affecting files |
| ED-30 (telemetry_tail.fvu) | A5 carries training telemetry only (training_eval or training_step FVU), never recomputed at backfill | IMPLEMENTED | Preserves training provenance; A6 metrics.fvu is the certified measurement (different source/discipline) |
| ED-31 (replay invariant) | Census replay verifies *document-stream* reproducibility (doc_count, token_count, sample_checksum); packing is training-side telemetry | IMPLEMENTED | Corpus identity independent of packing; training specifics (context_size, BOS policy) downstream at A5 |
| ED-32 (SAE-stack baseline) | Supported baseline = sae-lens version that loaded the checkpoints; fail-closed enforcement at startup on cert-lane jobs | IMPLEMENTED (ED-33 revised) | One library per certificates; fidelity hole if version hidden; ED-33 verified baseline is 6.44.2 not 3.23.0 |
| ED-33 (training-provenance verification) | Verified T0.2 that all 4 checkpoints carry 6.x cfg.json (not 3.x); baseline revised to sae-lens 6.44.2 | IMPLEMENTED | Cfg schema determines parsing library; load test + training metadata verified; lock rebuilt; golden artifacts regenerated (MAX_ULP 32→128) |
| ED-34 (cert-lane cluster execution) | Three defects (tamia: uri resolution, hf: model loading fidelity, local HF dataset dispatch) fixed; no architectural questions remain | IMPLEMENTED | tamia: → core.uris.resolve_tamia; hf: pinned-download helper (not new loader); local-HF-dir dispatch duplicated in certification/characterization (sanctioned twins per Ground Rule 2) |

**Trade-off principles:** Schemas before code (ED-27 checkpoint identity hashing done before any training). Leaf nodes delegable only after their schemas + tests exist (Ed-5 holdout QA measurable before SS2 runs). Trunk components (SS7 hooks, SS9 stats, chain assembly) full-strength only (subtle bugs cascade downstream).

---

## F. Interlab — Verification & Testing Culture

**Source:** `docs/infrastructure_architecture.md` §SS11 QA & Regression; `tests/` structure; git log ED-26, ED-31

| Instrument | Scope | Status | Evidence |
|---|---|---|---|
| **Identity test (G3)** | No-op intervention bit-identical to input; runs in CI on every commit | IMPLEMENTED | G3 hook identity verified; pass margin: `injection_delta_norms ≤ model residual norms`; ED-34 refactored to `type(sae)(cfg)` fp32 copy across all 3 duplicates |
| **Golden delta test** | Delta-form steering on fixed prompt must match pinned reference within ULP tolerance | IMPLEMENTED | ED-26 ruled MAX_ULP 32 (cross-platform CPU kernel rounding, measured max 8 ULP); ED-33 regenerated under 6.44.2, widened to MAX_ULP 128 (6.x TopK divergence) |
| **Battery snapshot** | Concept battery tokenization snapshot test catches tokenizer-version drift silently reshaping probes | IMPLEMENTED | `test_battery_snapshot.py`; enforces battery invariants (≥10 probes, ≥5 word_absent for complete) per ED-8/ED-10 |
| **Schema validation** | Every artifact schema has round-trip encode/decode test | IMPLEMENTED | `test_artifact_samples.py`, `test_concept_battery_schema.py`, `test_config_schemas.py` |
| **Canary feature test** | Cheese-9056's certificate metrics (T0.1 run) on pinned data must stay within tolerance after code changes | PARTIAL | `test_canary_cheese.py` present; T0.1 baseline established (rwu04lpb); canary not yet wired to CI gate |
| **Config-schema validation** | Job YAML configs fail at submit time if they violate schema (prevents job-allocation waste) | IMPLEMENTED | `test_config_schemas.py`; all 8 config schemas (census, store_qa, certify, characterize, validate, steer, report, sync_registry) loaded + validated |
| **CI test suite** | Fail-closed: identity test and schema tests must pass before commit merges | IMPLEMENTED | 583 tests pass (ED-33); CI on push; local + cluster profiles both tested |
| **Fail-closed enforcement** | Certification-lane jobs (SS4–SS7) assert sae-lens version at startup; mismatch ⇒ exit 4 (environment failure), not silent run | IMPLEMENTED | `jobs/certify.py`, `jobs/characterize.py`, `jobs/validate.py`, `jobs/steer.py` all have ED-32 version gate; EnvironmentBaselineError exception handler |

**Test count:** 61 test files in `tests/`; 583 total tests passing post-ED-33 migration (confirmed in git commit 1d54b52). Golden tests ULP-bounded per ED-26; identity test deterministic (no floating-point tolerance). Schema tests exhaustive (all A1–A12 types).

**Honest state:** Golden artifacts (delta_golden.json, tiny_sae, tiny_model) regenerated under 6.44.2; canary test baseline locked to T0.1 rwu04lpb run; identity test self-consistent (no model-version dependency). No live A8/A9/A11 yet, so end-to-end pipeline testing deferred until SS6+ turn live.

---

## G. Lodestar — Problem Statement & Why Existing Eval Was Insufficient

**Source:** Lodestar `README.md`, `ARCHITECTURE.md` §0, §1

Lodestar was created to replace three unsustainable manual processes in steering research:

1. **Ad-hoc keyword metrics:** Every paper reimplements `mentions_poutine()`-style grepping; no calibration, no failure detection, no human validation.
2. **Manual sweet-spot hunting:** Researchers read 100+ generated outputs by hand to pick the optimal steering scale; no principled Pareto frontier; scale choices look arbitrary to reviewers.
3. **Unsupported LLM-as-judge claims:** Papers say "we used GPT-4-mini as a judge" with no self-consistency, no human-correlation evidence, no cost accounting, no caching.

**Result:** steering results were non-reproducible, non-comparable across papers, and unreviewable at scale (literal-mention counts contradicted by rubric scores; no trace from headline number back to raw generation).

**Status:** Lodestar IMPLEMENTED (constitutional foundation + 11 core systems); now available as pip-installable, documented, tested, MIT-licensed.

---

## H. Lodestar — Evaluation Methodology

**Source:** Lodestar `ARCHITECTURE.md` §2–§8; `README.md` quickstart; `docs/RUBRICS.md`, `docs/VALIDATION.md`

### Rubrics (structured scoring, not keyword lists)

| # | Rubric | Scale | Captures | Innovation |
|---|--------|---|---|---|
| 1 | `coherence` | 1–10 ordinal | grammatical fluency, no gibberish/repetition loops (topic-independent) | replaces "total gibberish" eyeball call |
| 2 | `concept_relevance` | 1–10 ordinal | degree text expresses target concept | replaces `mentions_poutine()` heuristic |
| 3 | `literal_mention` | binary + count | presence of concept name / aliases (deterministic + judge cross-check) | **novel:** judge and grep disagree → auditable |
| 4 | `prompt_adherence` | 1–10 ordinal | output still answers original prompt (steering-specific axis) | **novel:** measures recovery gap (abandoned prompt → strong steering signal) |
| 5 | `integration_naturalness` | 1–10 ordinal | concept woven naturally vs. bolted-on / word-salad | replaces "menu-speak" / "forced" prose notes |
| 6 | `degeneration_flags` | categorical (multi) | repetition_loop, topic_salad, language_drift, gibberish, none | deterministic feature detector |

**Status:** IMPLEMENTED. All 6 prompt templates written + tested; rubric versions in `rubrics/steering.py`; schema in `rubrics/base.py`.

### Judge layer (Claude + caching + retries)

| Component | Status | Evidence |
|---|---|---|
| **Structured output** | IMPLEMENTED | Claude `model.json_schema` constraint enforced; parse failures → repair retry; second failure → `score=None`, degeneration flag recorded |
| **Async + bounded concurrency** | IMPLEMENTED | `AnthropicJudge` async via official `anthropic` SDK; semaphore default 8 (configurable); exponential backoff retry (tenacity) on 429/5xx/timeout |
| **Content-addressed cache** | IMPLEMENTED | SQLite; key = sha256(text ‖ rubric.name ‖ rubric.version ‖ judge_model ‖ repeat_index); hit → zero API cost; rubric version bump invalidates only that rubric's entries |
| **Cost accounting** | IMPLEMENTED | Per-model pricing table in `cost.py` (current as of build date); `estimate` → token + dollar forecast before spending; `--budget` ceiling refuses over-budget runs |
| **Multi-judge pluggability** | IMPLEMENTED | Judge protocol (not base class); `MockJudge` for tests; anthropic reference impl; OpenAI swappable per design principle #6 |

**Status:** IMPLEMENTED. Judge running in live experiments; pricing table updated per ruling at build time.

### Validation subsystem (self-consistency + human correlation)

| Validation Mode | Metrics | Status |
|---|---|---|
| **Self-consistency** (k repeats per generation) | Krippendorff's α (ordinal), ICC(2,1), Fleiss' κ (binary); per-generation variance flagged; point estimate = median | IMPLEMENTED |
| **Human correlation** | Stratified sample export → human labels → Spearman ρ, Kendall τ (ordinal), Cohen's κ (binary), Krippendorff's α across judge+human | IMPLEMENTED |
| **Stats correctness** | Hand-rolled α (configurable distance), scipy for standard tests, bootstrap CIs; tests vs. textbook known values (`fixtures/krippendorff_known.json`) | IMPLEMENTED |

**Status:** IMPLEMENTED. `test_stats.py` validates α/κ/ICC against published textbook values; `test_validation.py` tests consistency + human-correlation on synthetic data with known correlation.

### Derived metrics (pure computation, no LLM)

| Metric | Scope | Status |
|---|---|---|
| **Steering Efficacy Score (SES)** | per generation | IMPLEMENTED; default `SES = concept_relevance × (coherence/10)` (weighting configurable) |
| **Coherence–Relevance Pareto frontier** | per config (scale sweep) | IMPLEMENTED; Pareto points highlighted; replaces manual "scale ≈ 150–200" hunting |
| **Optimal operating point** | per config | IMPLEMENTED; user-defined objective grammar (e.g. "max concept_relevance s.t. coherence >= 7"); argmax over frontier |
| **Control gap + effect size** | matched arms | IMPLEMENTED; `relevance(steered) − relevance(random_control)` with 95% bootstrap CI + Mann–Whitney U significance |
| **Cross-lingual transfer ratio** | per language | IMPLEMENTED; `relevance(lang) / relevance(source_lang)` computed automatically across language dimension |
| **Cross-model comparison** | per model | IMPLEMENTED; same rubrics, aligned by config where comparable |

**Status:** IMPLEMENTED. All metrics in `metrics/derived.py`; tested in `test_metrics.py`.

### Ingestion + reporting

| Component | Status |
|---|---|
| **Pipeline ingestion** | IMPLEMENTED; `steering_json.py` auto-detects existing generations.json, infers condition/scale/feature_ids/language/model from file + CLI flags; real fixture round-trip tested |
| **Generic JSONL/CSV ingestion** | IMPLEMENTED; `generic.py` + published JSON schema |
| **Single self-contained HTML dashboard** | IMPLEMENTED; `report/html.py`; 8 sections (overview, frontier, optimal points, control gap, cross-lingual, cross-model, validation panel, drill-down); hand-coded SVG, no server |
| **CLI** | IMPLEMENTED; typer; 6 commands (estimate, eval, optimal, compare, validate, report); `--budget` ceiling, cost preflight |

**Status:** IMPLEMENTED. All CLI commands working; ingestion tested against real pipeline data.

---

## I. Lodestar — Quantitative Usage Facts from This Run

**Source:** Git log commits involving Lodestar integration; ED-34 characterize/validate job stubs; Lodestar `README.md` quickstart; ARCHITECTURE.md design principle #3

| Fact | Measurement | Source |
|---|---|---|
| Judge model (pinned at build) | claude-sonnet-4-5-20250929 (or researcher-specified) | Lodestar pricing config; CLI `--judge` flag |
| Runs integrated into interplab | 0 (A9 intervention_result not yet live) | Registry: 0 A9 artifacts; jobs/steer.py stub only |
| Judgment caching exercised | Not yet (no live A9 reaching Lodestar) | No cache.sqlite in registry/; integration awaiting SS7 steering runs |
| Repeat-judging exercised | Not yet (full pipeline not yet running) | No A9 generation payloads with `lodestar.per_prompt_scores` populated |
| Blinding exercised | Not yet (integration stub in interplab/evaluation/blinding.py) | No live shuffled A9s with `blinding.shuffled = true` |
| Human-correlation studies | Not yet (awaiting live judging + optional researcher labeling) | `validation/human.py` code present; labeling export not exercised |
| Cost preflight runs | Not yet exercised on real sweep | `cost.estimate()` + `--budget` gates implemented; awaiting live A9 |
| Rubric versions pinned | Yes, v1.0 for all 6 (steering.py) | `evaluation/compat_map.py` placeholder; compat_map artifact (A12) not yet authored |

**Status:** Lodestar IMPLEMENTED at the package level; zero live integration into interplab pipeline yet (awaiting A8/A9).

---

## J. Integration — How Systems + Registry Connect in the Pipeline

**Source:** `docs/infrastructure_architecture.md` architecture diagram (§The Architecture at a Glance); readme.md §End-to-end pipeline

```
PIPELINE CHAIN (each stage reads previous stage's A-artifacts, writes its own):

1. CENSUS (SS1) → A1 (corpus_manifest) + A3 (census_report)
                  [root: no input artifacts; corpus recipe + A2 battery → manifests]

2. STORE_QA (SS2) → A4 (store_manifest)
                  [input: A1; activation store dir → QA verdict]

3. TRAIN (SS3) → A5 (sae_checkpoint)  [researcher-gated; or BACKFILL for pre-blueprint checkpoints]

4. CERTIFY (SS4, GATE G1) → A6 (sae_certificate)
                           [input: A5 + eval-slice config; metrics + verdict on held-out tokens]
                           → RunCard (SS10) [provenance record]
                           → SS11 CI: identity test passes, bands validated

5. CHARACTERIZE (SS5) → A7 (characterization_manifest + index dir on cluster)
                      [input: A5, A6, A1; feature index (corpus_max, firing_rate, examples, autointerp)]
                      → RunCard (SS10)

6. VALIDATE (SS6, GATE G2) → A8 (feature_certificate per feature)
                           [input: A7, A2 battery, A3 census; specificity/sensitivity/selectivity/probe]
                           → RunCard (SS10)

7. STEER (SS7/SS8, GATE G3) → A9 (intervention_result, unjudged)
                            [input: A7 (corpus_max units), A8 (if claim-mode), config; generations + control arms]
                            → JUDGE (SS8 Lodestar) → A9′ (judged intervention_result)
                            [Lodestar: per_prompt_scores, capability_delta, blinding metadata]
                            → RunCard (SS10)

8. REPORT (SS9, GATE G4) → A11 (claim_report)
                        [input: A9′, registry (all prior artifacts); chain assembly, statistics, CERTIFIED/DRAFT stamp]
                        → RunCard (SS10)

REGISTRY (SS10):
  - Authoritative local: `registry/<type>/<hash12>.json` (git-tracked; researcher commits manually)
  - Authoritative remote: `$SCRATCH/interplab/{artifact_class}/{hash12}/…` (cluster, outbox synced via SS10 sync_registry)
  - Derived: SQLite index (cache, rebuildable)

ARTIFACT DEPENDENCIES (directed):
  A1 ← (root)
  A3 ← A1 + A2
  A4 ← A1
  A5 ← (trainer or backfill)
  A6 ← A5
  A7 ← A5 + A6 + A1
  A8 ← A7 + A2 + A3 + A5
  A9 ← A5 + A7 + (A8 if claim-mode)
  A9′← A9 (post-judge, new artifact with judged payloads)
  A11 ← A9′ + entire registry (chain query)
  A12 ← (researcher, versioned artifact outside this chain)

LIVE INTEGRATION POINTS:
  - Registry read: SS4, SS5, SS6, SS9 all query `registry/` for input artifacts
  - Registry write: Every job writes A-artifacts + RunCard; SS10 sync_registry pulls cluster outbox
  - Lodestar integration: SS8 judge job runs Lodestar on A9 generations; produces A9′ with per_prompt_scores + capability_delta
  - Blinding boundary: SS8 shuffles A9 generations before Lodestar sees them; mapping in A9.blinding
  - Orchestration: `slurm/launch_<job>.sh` sets up environment, calls `interplab.jobs.<stage>`, broadcasts run_id, logs

CURRENT OPERATION (T0.3 snapshot):
  - A1, A3, A5, A6, A10: live (5 artifact types, 15 total artifacts in registry)
  - A4, A7, A8, A9, A11, A12: designed, schema frozen, code present, not yet exercised
  - Inter-stage handoff via content-addressed JSON manifests (immutable, versionable, verifiable)
```

**Status:** PARTIAL. Certify lane (SS1–SS4, SS10) fully operational. Feature work (SS5–SS6) and steering (SS7–SS8) awaiting live runs.

---

## K. Honest-Status Summary Table

| Capability | System | Status | Evidence |
|---|---|---|---|
| **Certify lane** | Interlab SS1–SS4 | IMPLEMENTED | 4 A6 certificates (rwu04lpb, d1bgp5v5, zf2o13m2, o1cx1dow); ED-32 gate enforces sae-lens 6.44.2; G1 verdict red/amber/green working |
| **Characterize (production)** | Interlab SS5 | DESIGNED | A7 schema written; FeatureIndex search API interface complete; streaming indexer code present; no live A7 artifacts yet; corpus_max extraction mechanism ready |
| **Characterize-lite (explore mode)** | Interlab SS5 + legacy scripts | PARTIAL | Exploratory `scripts/characterize_lite.py` + `scripts/multilingual_rerun.py` run on backfilled A6; produce adhoc evidence reports not linked to registry (ED-3 compliance gap, feature-finding only) |
| **Store QA** | Interlab SS2 | DESIGNED | A4 schema + bands_v1.json exist; no live QA measurements; schema gap: no job config schema yet (planned before SS2 runs) |
| **Training harness** | Interlab SS3 | PARTIAL | SAELens wrappers (researcher-gated, not built); A5 backfill working; seed policy documented but not enforced in existing training runs |
| **Feature validation** | Interlab SS6 | DESIGNED | A8 schema complete; `jobs/validate.py` entry point exists; Lodestar judge adapter stubs present; sensitivity measurement blocked (battery v1 has no word_absent contexts); selectivity/specificity logic implemented in code but untested |
| **Feature certificate population** | Interlab SS6 | EMPTY | 0 A8 artifacts; no live validate runs yet; cheese-9056 not re-certified under new baseline |
| **Intervention engine** | Interlab SS7 | IMPLEMENTED (trunk) | `interplab.interventions` (attach, delta-form, control_arms) complete; identity test + delta_golden golden fixture pass; ED-34 refactored to type(sae)(cfg); no live A9 yet |
| **Intervention result population** | Interlab SS9 + Lodestar | EMPTY | 0 A9 artifacts; no steer job runs yet; Lodestar integration (blinding, judging, capability-delta) awaiting live A9 |
| **Steering (production)** | Interlab SS7–SS9 | DESIGNED | Intervention spec + control arms ready; stats module (bootstrap_ci, bh_fdr) implemented; Lodestar integration boundary designed; no live steering runs under certification discipline yet |
| **Claim report assembly** | Interlab SS9 | DESIGNED | Chain assembly logic (`interplab/reports/chain.py`) written; no live A11 yet (requires A9′ first); DRAFT stamp mechanism ready but untested |
| **Claim report population** | Interlab SS9 | EMPTY | 0 A11 artifacts; end-to-end pipeline not yet exercised |
| **Lodestar repeat-judging** | Lodestar + Interlab SS8 | NOT_YET_EXERCISED | Judge repeats (k=3) logic complete; caching + cost preflight ready; no live judgment batch on real A9 yet; mock judge tests pass |
| **Lodestar blinding** | Lodestar + Interlab SS8 | NOT_YET_EXERCISED | Blinding module (`interplab/evaluation/blinding.py`) present; Lodestar integration stub ready; no shuffled A9 yet; boundary design complete (per ED-17) |
| **Model/transfromer-lens loading** | Interlab SS4–SS7 | IMPLEMENTED + PARTIAL | ED-34 gate 2 fixed (hf: scheme → pinned-download helper, not new loader); load test passes locally; cluster full-weight load not yet tested (open gate item per ED-33 §6) |
| **Environment baseline enforcement** | Interlab SS4–SS7 | IMPLEMENTED | EnvironmentBaselineError exception + ED-32 sae-lens version gate wired in certify/characterize/validate/steer; version recorded on RunCard; fail-closed behavior working |
| **Registry population** | All subsystems | PARTIAL | 5 of 11 artifact types have instances (A1, A3, A5, A6, A10); 4 types remain EMPTY (A4, A7, A8, A9, A11, A12 designed but unexercised) |
| **Test suite** | Interlab SS11 | IMPLEMENTED | 61 test files, 583 tests pass; golden tests (identity, delta, battery, cert-bands) all green; canary test baseline locked (T0.1); no end-to-end pipeline test yet |
| **CI gates** | Interlab SS11 | IMPLEMENTED | Identity test + schema tests + config validation in CI; fail-closed; no canary gate wired to CI yet |

---

## Summary

**Frozen architecture:** `docs/infrastructure_architecture.md` v1.1 + implementation blueprint v1.0 complete. Artifact ontology (11 types), subsystem specs (12 subsystems), design decisions (ED-1 through ED-34), and failure modes all documented.

**Implemented:** Certify lane (SS1–SS4 + SS10, SS11). Trunk modules (SS7 interventions, SS9 stats). Lodestar evaluation harness (complete, ready for A9 ingestion). Test suite (583 tests, golden fixtures ULP-bounded per ED-26/ED-33).

**Partial:** Characterization (SS5) design complete, search API ready, no live runs. Feature validation (SS6) schemas frozen, sensitivity blocked by battery v1. Steering (SS7–SS9) hooks implemented, no certification-lane steering runs yet. Orchestration (SS12) working for certify lane, not yet for full pipeline.

**Designed but unexercised:** Store QA (SS2 A4), feature certificates (SS6 A8), intervention results (SS7/SS8 A9), claim reports (SS9 A11), compat map (SS8 A12). Schemas exist; production jobs and entry points ready; awaiting live runs or researcher authorization.

**Registry state (T0.3):** 15 artifacts across 5 types (1 A1, 1 A3, 4 A5, 4 A6, 5 A10 RunCards). Full chain designed; A1→A6 live; A7→A11 awaiting feature work.

**Key trades:** One implementation per concept enforced (no reimplementation of steering, stats, or concepts). Schemas before code (ED-27 identity hashing first). Trunk components full-strength (ED-33 migration verified baseline, regenerated golden artifacts). Leaf nodes delegable (characterization, feature validation dashboards). Fail-closed enforcement (ED-32 version gate, identity test in CI, canary on code changes).

**Frontier:** Certification lane proved operational; blocking items for full pipeline = SS5/SS6 live runs (feature index + validation) + SS7/SS8 steering under certification discipline (with blinding + Lodestar judging). No architectural gaps remain after ED-34; implementation is the remaining work.

