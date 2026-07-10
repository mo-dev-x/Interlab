# Laboratory Architecture: Interpretability Research Infrastructure

**Version 1.1 — frozen.** *July 2026. Supersedes v1.0 in full. Companion to `docs/research_program.md` (the science roadmap) — this document specifies the lab that should exist around it. Grounded in a repository audit and replication review; revised after external architectural review. Changes from v1.0: explicit artifact ontology with content-hash identity; contracts defined as versioned artifact schemas; derived status replacing any notion of stored lifecycle state; two composition modes (data contracts between stages, shared libraries within them); three foundational decisions added (storage topology, evaluation-version compatibility, schema evolution); implementation and delegation policy. Subsystem set, gates, and build order are unchanged.*

*Context notes from the audit: the repo's `results/FEATURE_EXPERIMENT_LOG.md` is a 2,619-line numbered lab notebook (genuine narrative provenance); Lodestar (`d:\lodstar`) is a mature, constitution-driven evaluation harness with judge caching, self-consistency, and human-correlation reporting. This architecture builds around those two assets rather than duplicating them. The first SAE having been trained on `NeelNanda/pile-10k` — a fact recoverable only by reading the log — is the canonical argument for the Corpus Registry below.*

---

## Design Philosophy

Three principles, from which everything else derives:

1. **Certificates, not vibes.** Every artifact that downstream work depends on (a corpus, an SAE, a feature, an intervention result) carries a machine-generated certificate with pass/fail gates. Claims chain certificates; a claim whose chain is incomplete is automatically stamped `UNCERTIFIED`.
2. **Explore freely, claim expensively.** The infrastructure must never slow down poking around — exploration is how the cheese feature was found. Gates block *claims* (reports, comparisons, paper figures), not experiments. The distinction is enforced by the reporting layer, not by making tools refuse to run.
3. **One implementation per concept.** One hook library, one concept battery, one stats module. The two blocked months were lengthened by every script having its own private version of "steering" and "probe sentences." Shared code is not software hygiene here — it is what makes results comparable across experiments.

## The Artifact Ontology and Contract Model

The architecture is organized around a small set of named artifacts. Each is a **versioned data schema for files on disk** — not a behavior-bearing domain class. Identity is the content hash; provenance is references to other artifacts' hashes.

| Artifact | Produced by | Identity & key contents |
|---|---|---|
| `CorpusManifest` | SS1 | hash of corpus content; source, revision, token count, dedup rate |
| `ConceptBattery` | SS1 | versioned probe/control/word-absent context sets, per concept and language |
| `CensusReport` | SS1 | per-concept frequencies over a named `CorpusManifest` |
| `StoreManifest` + QA report | SS2 | store content hash; collection config; QA measurements |
| `SAECheckpoint` | SS3 | weights hash; config; store hash; code commit; seed |
| `SAECertificate` | SS4 | metrics over a named checkpoint hash; schema version; verdict |
| `CharacterizationIndex` | SS5 | per-feature statistics over a named checkpoint + corpus sample |
| `FeatureCertificate` | SS6 | validation metrics for one `(checkpoint_hash, feature_index)`; judge/rubric versions |
| `InterventionResult` | SS7+SS8 | generations + config, in normalized units, with control arms |
| `RunCard` | SS10 | run ID; config hash; code commit; upstream artifact hashes; outcome |
| `ClaimReport` | SS9 | assembled certificate chain; statistics; certification stamp |

Three rules govern the ontology:

**A feature is a view, not an entity.** There is no standalone `Feature` artifact. A feature exists only as `(checkpoint_hash, feature_index)` plus derived statistics; it does not survive retraining and has no cross-checkpoint identity. This is not a modeling convenience — the science program's own findings (feature instability across seeds) forbid reifying features, and an architecture that gave them independent identity would encode in code the exact assumption the replication review retired.

**Status is derived, never stored.** No artifact carries a mutable state field, and there are no lifecycle state machines. A certificate is an immutable fact: *computed at time T, by code version C, over artifact hash H, with result R*. Whether a checkpoint "is certified" is a query — *does a valid, current-schema, evaluation-compatible certificate exist for this hash?* — evaluated at claim-assembly time by SS9. Append-only facts plus derivation-at-read gives everything a state machine promises, with no enforcement point required and no possibility of status drifting from reality. Lifecycle words ("certified," "characterized," "quarantined") are permitted as *vocabulary* in documentation and dashboards; they are always the result of the query, never a field.

**Every arrow is a schema; APIs only where interaction is live.** Subsystems are batch jobs that run at different times on different machines; their interfaces are the artifacts above, versioned from day one. Exactly two components expose programmatic interfaces instead: the SS5 search interface (live queries over the characterization index) and the SS7 hook library. Schema stability is earned, not declared — schemas may move freely until the first claim-mode report ships, and are change-controlled after.

**Two composition modes, both deliberate.** *Between* pipeline stages: data contracts only — no stage imports another stage's internals. *Within* an experiment process: SS7 (interventions) and the SS9 statistics module are **shared code libraries that experiments must import**, never reimplement against a spec. For intervention semantics and statistics, depending on the single shared implementation is not coupling to be minimized — it is the point; the steering bug existed precisely because every script had its own hook.

## Foundational Decisions

Three decisions that everything below assumes. They are architecture, not implementation detail, and were unresolved in v1.0.

**D1 — Storage topology and artifact identity.** Artifacts live across a split brain: the Alliance/Tamia cluster (authoritative for all heavy artifacts — checkpoints, activation stores, characterization indexes; these never move), the local machine (authoritative for docs, configs, analysis, and all manifests/certificates/run cards), git (code and schemas), and WandB offline (training telemetry, non-authoritative). The rule: **heavy artifacts are hashed at creation, where they live; only manifests travel.** Every cross-machine reference is `(content_hash, authoritative_location)` recorded in the producing run card. A certificate or claim never requires moving the artifact it describes — it requires the manifest. Any artifact without a manifest in the registry does not exist for claim purposes, regardless of what is on disk.

**D2 — Evaluation-version compatibility.** Certificates that embed judge outputs (SS6 feature certificates, SS8 behavioral results) pin the judge model, rubric version, and prompt-template version per judgment (Lodestar already does this per-judgment; this decision lifts it to chain level). **A claim may only chain certificates with compatible evaluation versions**, where the compatibility map (which judge/rubric versions are interchangeable) is itself a small versioned artifact maintained deliberately, not inferred. When judge models deprecate, affected certificates become stale for new claims and are recomputed on demand; historical claims remain valid as records of what was known when, stamped with their evaluation versions.

**D3 — Schema evolution and recompute policy.** Every certificate and index carries its schema version. When certification code or bands change, existing certificates are not edited and not deleted — they become *stale*: SS9's assembly query requires the current schema version (or a declared minimum), and stale certificates are recomputed on demand. Recomputation is cheap by construction because all inputs are content-addressed and immutable. Band recalibration (expected after the first certification batch) is a schema version bump like any other.

## The Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EXPERIMENT REGISTRY (SS10)                      │
│    run cards · (hash, location) references · certificate facts     │
└──────────────────────────────▲──────────────────────────────────────┘
                               │ every stage writes manifests here

 SS1 Corpus &      SS2 Activation     SS3 SAE          SS4 SAE
 Concept Registry─►Store + QA ──────► Training ──────► Certification
     │ census          [gate: data]    Harness          [GATE G1]
     │                                                     │
     │              ┌──────────────────────────────────────┘
     ▼              ▼
 SS5 Feature Characterization Engine (corpus-scale dashboards)
     │
     ▼
 SS6 Feature Validation + Probe Comparator  [GATE G2: certificate]
     │
     ▼
 SS7 Intervention Engine  [GATE G3: identity test, hard CI block]
     │
     ▼
 SS8 Behavioral Evaluation (= Lodestar)  [GATE G4: statistical]
     │
     ▼
 SS9 Statistics & Auto-Reports ──► derives chain status at assembly:
                                   certified claim, or DRAFT stamp

 Cross-cutting: SS11 QA/Regression · SS12 Orchestration · SS13 Circuits

 Every arrow = a versioned artifact schema (see ontology table).
 SS7 and the SS9 stats module are shared libraries imported by
 experiments; SS5 search is the only other live API.
```

## Subsystem Specifications

### SS1 — Corpus & Concept Registry

**Why necessary:** The SAE history spans three corpora (pile-uncopyrighted → pile-10k → FineWeb subset), and the pile-10k fact lives only in prose. Concept probe sentences are hardcoded constants inside `scripts/find_features.py`. Nobody can currently answer "how often did the SAE see poutine?" without a custom script.
**Questions answered:** Is concept X in the SAE's training distribution, at what frequency? Is a discovery failure explainable by data before anyone blames the model? What exactly changed between corpus versions?
**Measurements:** the `CorpusManifest` per corpus version; the `CensusReport` (occurrences per million tokens, document counts, per-language splits) over the versioned `ConceptBattery`; tokenization audit per concept (token split, byte-fallback flags for ar/zh).
**Visualizations:** concept frequency spectrum (log-scale rank plot) with discoverability threshold bands overlaid as ladder data accumulates.
**When it runs:** once per corpus version; census re-runs when the battery changes.
**Healthy:** every corpus referenced by any config has a manifest; every target concept has a census row *before* anyone searches for it.
**Unhealthy:** a concept below ~1 occurrence/million tokens treated as a discovery target at 32x without a flag.
**Downstream dependents:** everything — this is the root of every certificate chain.
**Blocking:** yes for claims ("no feature for X" is publishable only with a census row), no for exploration.

The `ConceptBattery` graduates from code constants to versioned data files: probe sentences (multilingual), **concept-without-word contexts** (currently missing entirely — sensitivity cannot be tested without them), and matched controls (for poutine: other regional dishes at similar frequency), each with provenance and a changelog.

### SS2 — Activation Store QA

**Why necessary:** The store is the SAE's entire universe; defects here are invisible downstream and uncorrectable later. The pipeline right-pads, prepends BOS, and stores bf16 — none of it audited.
**Questions answered:** Are special-token/padding activations polluting training? Are samples decorrelated? Does the stored distribution match what the SAE will meet at steering time?
**Measurements:** the `StoreManifest` plus QA report: norm-by-position curve (catches first-token anomaly and BOS pollution); special-token fraction in the store (must be ~0 or deliberately included and documented); consecutive-sample autocorrelation (shuffle verification); norm/coverage comparison between store distribution and a chat-templated sample of the same model (quantifies the FineWeb-vs-chat mismatch instead of leaving it as a worry).
**Visualizations:** norm-by-position plot; store-vs-chat norm histograms overlaid.
**When:** at store creation, before any training run consumes it. Stores are hashed at creation on the cluster (D1).
**Healthy:** flat norm curve after the first few positions; autocorrelation ≈ 0; store-vs-chat divergence measured and recorded (not necessarily small — but *known*).
**Unhealthy:** norm spikes at padding positions; visible autocorrelation (unshuffled buffers).
**Dependents:** SS3, SS4, and the interpretation of every feature.
**Blocking:** yes — a store that fails QA should never reach a training run, because the failure is unfixable after the fact.

### SS3 — SAE Training Harness (extend, don't rebuild)

The SAELens-plus-YAML setup is fine and stays. Additions: every run writes a `SAECheckpoint` manifest recording the store hash, config hash, code commit, and seed (D1: hashed at creation, on the cluster); in-training health telemetry (dead-feature count over time, FVU trajectory) so a doomed run is killed at 10% not discovered at 100%; a mandatory seed policy field (the current global `seed: 42` monoculture means no stability claim can ever be made — the harness should make seed a first-class sweep axis).
**Blocking:** n/a (produces candidates; SS4 judges them).

### SS4 — SAE Certification — GATE G1

**Why necessary:** The replication audit's central finding: nothing in the pipeline can distinguish a well-trained SAE from an undertrained one, and TopK's fixed L0=100 actively hides sickness that L1 training would surface. Two months of feature work ran on uncertified instruments.
**Questions answered:** Is this checkpoint fit for feature work at all? How much of the model's computation does it capture? Where does it fail?
**Measurements:** the `SAECertificate` — an immutable fact over a named checkpoint hash, carrying its schema version (D3): CE-loss-recovered (substitute reconstruction, baseline against zero-ablation); FVU/explained variance; dead-feature fraction (zero fires over 10M held-out tokens); feature-density histogram (log activation frequency); max pairwise decoder cosine (duplicate detection); per-position reconstruction quality (does it degrade in chat-template regions — quantifies OOD exposure).
**Visualizations:** one-page report card: density histogram, FVU-by-position, headline numbers with green/amber/red bands.
**When:** automatically at end of every training run; retroactively on all existing checkpoints (a day of compute; should happen before anything else uses them).
**Healthy (TopK k=100, mid-stack 14B; bands are placeholders until calibrated on the first certification batch — a schema version bump per D3):** CE-recovered ≥95% green, 90–95% amber, <90% red; dead fraction <5% green, >15% red; density histogram broad and unimodal across ~1e-6–1e-2.
**Unhealthy:** red on any headline; a spike of always-on features (formatting/positional artifacts); duplicate decoder clusters.
**Dependents:** everything downstream of the SAE.
**Blocking:** yes — a red certificate quarantines the checkpoint from claim-mode use; "quarantined" is derived by SS9's assembly query, not stored on the checkpoint.

### SS5 — Feature Characterization Engine

**Why necessary:** The largest single gap. Feature identity is currently established from a few hundred handwritten sentences; "max activation" — which calibrates steering — is estimated from that pool. This subsystem is the lab's *eyes*.
**Questions answered:** What does feature *i* actually fire on, over the real distribution? What is its true max, firing rate, spectrum? What candidate features exist for concept X?
**Measurements:** the `CharacterizationIndex`: a streaming pass of 5–10M+ held-out corpus tokens (plus a chat-formatted slice) producing, per `(checkpoint_hash, feature_index)`: top-k activating contexts; examples sampled from every activation decile (the anti-top-activation-illusion measure); activation histogram; corpus max (the steering unit); firing rate; logit-lens top tokens; autointerp label with a detection score (Lodestar's judge infrastructure reused, judge versions pinned per D2). The index lives on the cluster and is referenced by hash (D1). Its **search interface** — by probe activation, by decoder cosine to a seed feature, by label text — is one of the architecture's two live APIs.
**Visualizations:** static per-feature dashboard pages (paper-style feature cards) and a searchable catalog.
**When:** once per certified checkpoint (expensive, cached, content-addressed).
**Healthy:** every feature referenced in any downstream experiment has a dashboard generated from ≥5M tokens.
**Unhealthy:** any experiment citing a feature whose statistics trace to handwritten sentences.
**Dependents:** SS6, SS7 (units), all discovery work.
**Blocking:** soft — exploration can precede it, but SS6 certificates require it, and steering units *must* come from it.

### SS6 — Feature Validation & Certification — GATE G2

**Why necessary:** "Clean" is currently an eyeball judgment; cheese-9056's certificate is the pool it was found on.
**Questions answered:** Is this feature specific, sensitive, and selective enough to carry a claim? Did the SAE capture what the model represents, or miss it?
**Measurements:** the `FeatureCertificate` for one `(checkpoint_hash, feature_index)`, pinning judge and rubric versions (D2) and schema version (D3): *specificity* — Lodestar-scored rubric (0–3 concept-relatedness) over contexts sampled from each activation decile, reproducing the paper's deciles plot; *sensitivity* — firing rate on concept-without-word contexts and cross-lingual probes from SS1; *selectivity* — behavior of nearest-neighbor features (decoder cosine) on the same probes; *probe comparator* — a linear probe trained on the same residual stream for the same concept, giving the ceiling of what is linearly decodable. The probe-vs-feature gap is the instrument the poutine investigation lacked: it splits "model doesn't have it" from "SAE didn't find it" in one number.
**Visualizations:** the feature certificate — one page: deciles plot, sensitivity table, neighbor analysis, probe gap, verdict.
**When:** on demand, for any feature about to be used in claim-mode work.
**Healthy:** top-decile rubric mean ≥2.5/3 with monotone decay; word-absent firing well above chance; probe AUC − feature-detection AUC < ~0.1.
**Unhealthy:** high top-decile but mid-spectrum collapse (token feature masquerading as concept feature); large probe gap (SAE missed the representation — a capacity/corpus finding, not a model finding).
**Dependents:** SS7/SS8 claims; the Phase-2 parameter comparison is meaningless without certified features on both sides.
**Blocking:** yes for claims.

### SS7 — Intervention Engine — GATE G3

**Why necessary:** The audit found the steering hook replaces the residual stream with the reconstruction (injecting reconstruction error at every position of every step) and takes raw unit-less clamp values. Beyond the bug: every experiment currently builds its own hooks, so no two steering results are strictly comparable.
**What it is:** a **shared code library — the composition-mode exception, by design** — providing the single implementation of all interventions: delta-form steering (original + clamped-reconstruction − reconstruction), ablation, patching; clamp values expressed **only** in multiples of SS5 corpus max; built-in control arms (matched-norm random direction, matched-frequency random feature, prompting baseline). Experiments import it; nothing reimplements it against a spec.
**Semantics that must be fixed in the library's specification before implementation** (each is a place a plausible-looking reimplementation reintroduces the bug): the order of dtype/device casts such that a no-op intervention is *bit*-identical (the current hook's bf16→fp32→bf16 round trip is itself a perturbation — the delta must be computed in high precision and applied to the original stream); the position-masking policy (which of prompt tokens, generated tokens, and chat special tokens are steered — the reference methodology steers all positions; whatever is chosen is declared per run, not implicit); and KV-cache semantics (clamped positions' effects persist in the cache — this is intended and documented, not accidental).
**Measurements:** the identity test — a no-op intervention must produce bit-identical generations — plus per-run logging of injected-delta norms relative to residual norms.
**Visualizations:** dose-response curves in normalized units; intervention-vs-control panels.
**When:** identity test runs in CI on every commit; controls run automatically alongside every steering sweep (not as a separate optional experiment).
**Healthy:** identity deviation = 0; effect curves separate from control curves with the stats layer's blessing.
**Unhealthy:** any nonzero identity deviation (hard failure); effects indistinguishable from the random-direction arm.
**Dependents:** every causal claim in the project.
**Blocking:** absolutely — this is the one gate that fails the build.

### SS8 — Behavioral Evaluation Service (= Lodestar, integrated)

Largely **exists**, and is the strongest piece of infrastructure the project owns: judge caching, self-consistency, human-correlation reporting, Pareto frontiers, provenance — lab-grade. Its per-judgment version pinning is the foundation D2 builds on; the chain-level compatibility map is maintained alongside it. Three additions at the integration boundary:

1. **Blindness enforcement upstream** — generation artifacts are shuffled and condition-stripped *before* they reach judging, so no judge prompt can correlate position or metadata with condition.
2. A **capability-degradation module** — perplexity or short-benchmark deltas under intervention, because "coherence per Lodestar" and "didn't lobotomize the model" are different facts.
3. Retire `mentions_poutine()`-style keyword metrics from every code path — Lodestar's own architecture document names this as the thing it replaces; finish the replacement.

**Blocking:** claim-mode results must carry Lodestar's self-consistency report; below-threshold judge reliability downgrades the claim automatically.

### SS9 — Statistics & Auto-Reporting

**Why necessary:** No error bar appears anywhere in the pipeline; single seed everywhere; scale sweeps pick "optimal scale=55" from point estimates.
**Questions answered:** Is this effect real? Would it survive a second seed? How many comparisons were made before this one looked good?
**Measurements:** the statistics module — a **shared library**, like SS7 — computes bootstrap CIs over prompts for every judged metric (prompts, not generations, are the exchangeable resampling unit); seed-variance when ≥2 seeds exist (and a visible "n_seeds=1" stamp when not); multiple-comparison control for feature searches (163k candidates are ranked — the field's most ignored correction); standard effect sizes.
**Auto-reports:** every claim-mode experiment emits a `ClaimReport` whose certificate chain is **derived at assembly time**: SS9 queries the registry for each required link — corpus manifest → store QA → G1 → G2 → G3 config → G4 results — and checks that each certificate exists, is valid for the referenced hashes, carries the current (or declared-minimum) schema version (D3), and has compatible evaluation versions (D2). If every link resolves, the report is certified; if any link is missing or stale, the report generates anyway, stamped `DRAFT — UNCERTIFIED CHAIN` in the header. That stamp is the entire enforcement mechanism of the lab: nothing is forbidden, but nothing uncertified can masquerade as a result.
**Blocking:** by stamp, not by refusal.

### SS10 — Experiment Registry & Provenance

**Why necessary:** The experiment log is excellent prose provenance — but it is append-only human memory, and the `steering_v2/v3/v4`, `lodstar_cheese_*` results sprawl shows the artifact side has no structure.
**What it is:** the `RunCard` index — every run gets an ID, config hash, code commit, upstream artifact references as `(content_hash, authoritative_location)` pairs (D1), and one-line outcome; results directories are named by run ID, not by `_v4`. The registry stores facts only — run cards and certificates — and no status fields; all status is derived by query (see ontology rules). The log stays as the narrative layer (it is good; keep writing it) and gains a run-ID cross-reference per section, making it searchable *and* machine-checkable.
**When:** every run, automatically at launch.
**Healthy:** any number in any report traces to a run card in one hop.
**Unhealthy:** "which checkpoint was this from?" requiring archaeology (the pile-10k fact took 2,600 lines to find).
**Blocking:** no, but SS9's assembly query runs against it — an artifact without a manifest here does not exist for claim purposes (D1).

### SS11 — QA & Regression Suite

**Why necessary:** This repo has zero tests (Lodestar has plenty; the science repo has none), and it is the repo where a silent bug costs a month.
**Contents:** the G3 identity test and a golden numeric fixture for delta-form steering (these two exist *before* any implementation work is delegated — see the delegation policy); encode/decode round-trip on a fixture SAE; tokenization snapshot tests for the `ConceptBattery` (catches tokenizer-version drift silently reshaping probes); schema-validation tests for every artifact schema; a **canary feature test** — cheese-9056's certificate metrics recomputed on a pinned data slice must stay within tolerance after any code change (if a refactor moves the cheese numbers, the refactor changed the science); config-schema validation so a typo'd YAML fails at submit time, not 11 hours into a 12-hour SLURM allocation — which is precisely how job 338944 was lost at 94% complete.
**When:** CI on every commit; canaries nightly or pre-claim.
**Blocking:** identity, schema, and config tests, yes.

### SS12 — Orchestration Layer

**Why necessary:** `slurm/` holds ~15 one-off scripts (`find_features_celine_dion.sh`, `steering_montreal_solo.sh`, …) alongside the newer parameterized ones — each one-off encodes an experiment nobody can re-run confidently.
**What it is:** finish the consolidation already started: one parameterized launcher per stage (train / characterize / validate / steer), taking a config path and a run ID, registering the `RunCard` with SS10 at submit time. Keep the existing convention — every submission prints the `sbatch` line, the log-tail command, and the final-result command together.
**Blocking:** no; it is ergonomics that makes the gated path the easy path.

### SS13 — Circuit-Tracing Support (deferred, deliberately)

Per the replication review: transcoder training on Qwen-14B is a bigger investment than the entire SAE program to date. The infrastructure decision is to **not build it yet** — first run attribution graphs on a supported small model with the open circuit-tracer stack, storing graphs as registry artifacts with intervention-validation runs attached. Only if the certificate-chain pipeline (SS1–SS9) is operating and the science still demands Qwen circuits does a Qwen transcoder harness get designed. Building this first would be the infrastructure version of the poutine mistake.

## Implementation & Delegation Policy

Adopted during architectural review, and part of the frozen architecture:

- **Schemas before code.** Each artifact schema is drafted as the first task of the subsystem that first writes it, and schema-validation tests (SS11) land with it. Writing schemas is architecture; coding against them is not.
- **Delegate leaf nodes, never the trunk.** The SS7 core, the SS9 statistics module, and SS9's chain-assembly logic are written and reviewed at full strength — they are the components where a subtle error invalidates everything downstream while looking correct. Census scripts, certification metrics, the characterization indexer, dashboards, plots, parsers, and launchers are delegable once their schemas are frozen and their tests exist.
- **Tests precede delegation.** The G3 identity test and the delta-form golden fixture are written before any intervention-adjacent work is handed off; the canary test before any refactor of certified code paths.

## Researcher Workflow (what a day looks like when this exists)

Discovery: browse SS5 dashboards → shortlist candidates → request G2 certificates (an hour of judge calls, cached) → certified features enter the steering queue with SS7 controls attached automatically → Lodestar judges blind → SS9 assembles the chain and emits a certified `ClaimReport`. Total new manual work per experiment: choosing what to test. Total possible ways to accidentally publish an uncalibrated number: approximately zero — the DRAFT stamp catches everything else. A negative result ("no poutine feature") now takes one day and produces three numbers — census frequency, probe AUC, best-candidate certificate — instead of three weeks of doubt.

## Gap Analysis Against the Current Repository

| Subsystem | Status | Evidence |
|---|---|---|
| SS8 Behavioral eval | **Exists (strong)** | Lodestar: caching, self-consistency, human-correlation, provenance, tests |
| SS3 Training harness | **Exists (adequate)** | SAELens + 5 YAML configs; missing manifest fields, seed policy, in-training telemetry |
| SS10 Registry | **Partial** | 2,619-line numbered experiment log (excellent narrative); no run cards; ad-hoc `_v2/_v3/_v4` results sprawl |
| SS12 Orchestration | **Partial** | Parameterized sweep scripts exist; ~15 one-off shell scripts alongside |
| SS5 Characterization | **Partial (weakest partial)** | survey/decode scripts exist but run on handwritten sentence pools; no corpus-scale dashboards; no true max |
| SS7 Interventions | **Partial (buggy)** | Hooks exist incl. passthrough control; non-identity form, raw units, no control arms |
| SS1 Corpus/concepts | **Missing** | Three corpora with no manifests; PROBES hardcoded in scripts; no census; no word-absent contexts |
| SS2 Store QA | **Missing** | No checks on the store at all |
| SS4 SAE certification | **Missing** | No health metric computed anywhere |
| SS6 Feature certificates | **Missing** | No rubric-by-decile, no sensitivity, no probe comparator |
| SS9 Statistics/reports | **Missing** | No CIs, single seed, no multiple-comparison control, no report generation |
| SS11 QA/regression | **Missing** | Zero tests in this repo |
| SS13 Circuit support | **Missing (correctly)** | Defer |

## Build Order

Unchanged from v1.0, with one standing preamble from the contract model: the foundational decisions (D1–D3) are recorded first, and each item begins by drafting the schemas of the artifacts it produces, with schema tests landing alongside. Sizes are relative; each item unblocks the next.

1. **SS7 delta-form fix + identity test + golden fixture** (small) — a correctness bug in active use; one afternoon, and every subsequent experiment inherits validity. Per the delegation policy, this item is full-strength work.
2. **SS4 SAE certification** (medium) — run retroactively on all existing checkpoints; highest information per compute-hour in the entire plan, and it decides which checkpoints the rest of the work may build on. Bands calibrate on this first batch (schema bump per D3).
3. **SS1 corpus census + manifests** (small) — answers the poutine question definitively; `ConceptBattery` extracted from code into versioned data.
4. **SS5 characterization engine** (large) — the biggest build and the biggest payoff; everything from here on has real eyes. SS2 store QA rides along (same streaming-pass infrastructure).
5. **SS6 validation suite + probe comparator** (medium) — reuses SS5's index and Lodestar's judges; re-certify cheese/UNESCO/Eurovision first.
6. **SS9 stats + report templates** (medium) — retrofit onto the cheese dose-response as the pilot report; first claim-mode report ships here, after which schemas enter change control.
7. **SS10 run cards + SS12 launcher consolidation** (small each) — formalize before Phase-2 grid results multiply the sprawl.
8. **SS11 canaries and snapshots** (small, grows forever; identity/schema tests arrive earlier, with items 1–3).
9. **SS13** — only after the above is routine.

Items 1–3 are roughly one week and would have compressed the two blocked months into about four days — the strongest argument for building them before any new science runs. This build order is deliberately the infrastructure mirror of the replication review's two-week roadmap: by the time the lab is built, the replication certificate has been produced *by* it, as its first output.
