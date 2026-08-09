# Execution Roadmap — Final 3 Days (Fri Jul 24 → Sun Jul 26, 2026) — rev 2

**Rev 2 change:** rev 1 wrongly treated the Qwen arm as finished. Corrected against actual status below; critical path recomputed. Qwen quantitative completion is now a **co-critical** chain alongside the Gemma arm.

---

## Actual Qwen status (ground truth, from FEATURE_EXPERIMENT_LOG.md + registry)

**Done:**
- Instruct-model SAE trained: `rwu04lpb/final_400001024` (layer 28, 32x, topk k=100, 400M FineWeb tokens). This is THE checkpoint.
- Open-ended survey → 3 demo features: **9056 cheese** (optimal scale 55, widest window, best prompt-adherence — the demo), **47735 UNESCO** (scale 100, content-override), **44189 Eurovision** (scale 100, weak monosemanticity, known-marginal).
- Lodestar-judged steering sweeps for all three, with corrected evaluation (FFFD fix, sweep_hash fix).
- Negative results, well documented: no poutine feature (2 checkpoints, 20+ attempts), no clean Montreal/Quebec feature (EN+ZH), base-SAE doesn't transfer to instruct model.

**Outstanding (the gap rev 1 missed):**
1. **No SAE certificate** — L0/sparsity, reconstruction fidelity, dead-feature % never formally measured on rwu04lpb (registry/sae_certificate is empty). Every "SAE quality" number in the report depends on this.
2. **No feature certificates / characterization** — selectivity vs. baseline, activation distributions, corpus prevalence for 9056/47735/44189 never produced (`characterize.py` never run).
3. **Multilingual analysis is stale** — existing `results/features/multilingual/` predates the instruct SAE; must be rerun on rwu04lpb or the cross-language claim has no valid Qwen side.
4. **No corpus census** — `census.py` never run on the FineWeb training subset.
5. **No ablation control** — steering shows sufficiency; no suppression/ablation result for 9056.
6. **No Qwen circuit work.**
7. **Layer×width grid** — status unclear; some non-28/32x checkpoints exist (steering_v4 has l16/l28_64x/l40 dirs, poutine-era). No certified comparison.
8. **Infra risk:** `certify.py`/`characterize.py`/`census.py` chain (ED-27–31) is freshly built, tested, but **never executed end-to-end on the cluster**. First-run failures are likely.

## The scientific story (unchanged)

1. **Reproduction (Qwen):** GGC-style feature with identity substitution exists and steers (9056 @ 55) — qualitative done, quantitative outstanding.
2. **Cross-model (Gemma Scope):** matched features, compared on selectivity, sparsity, recon fidelity, steering dose-response, prevalence.
3. **Cross-language:** same battery, both models.
4. **Circuits:** one concept — circuit-tracer graph on Gemma-2-2B vs. attribution-patching/head-ablation sketch on Qwen.

**Scoping rule:** 2 models × 2 concepts (cheese, UNESCO) fully quantified beats anything wider. Eurovision is pre-flagged weak — carry it only if it costs nothing.

## Assumptions

- A1. Prompt's cross-model GGC objective is the deliverable; `rwu04lpb` is the sole Qwen instrument (no new Qwen SAE training).
- A2. Second model = **Gemma Scope** (Gemma-2-9B primary, 2B fallback + circuit model). Llama = first cut.
- A3. Qwen circuits = attribution patching + head/MLP ablation around feature 9056 (no public Qwen transcoders).
- A4. Concept battery frozen: cheese, UNESCO (+ Eurovision passively). Negative results (poutine, Montreal) enter the report as the coverage/entanglement finding — no new searching.
- A5. Tamia compute nodes offline → all downloads on login node Friday (use `HF_HUB_DISABLE_XET=1`, `--max-workers 1` — known login-node OOM fix).
- A6. Science freezes Sun 18:00; report+slides drafted Sun night, polish Monday AM.

---

## Critical path (recomputed)

Two chains must both land by Sun morning; they run in parallel on the cluster:

- **Chain Q (Qwen quantitative):** certify rwu04lpb → characterize 3 features → multilingual rerun + census + ablation control → Qwen half of comparison table. Shorter, but gated by never-run infra → **launch first, tonight, with Impl Eng on call.**
- **Chain G (Gemma, longest lead):** downloads → feature discovery → G1 validation → steering + Lodestar → Gemma half of comparison table.
- **Chain C (circuits):** setup Sat AM → G2 concept pick → graphs Sat PM + Qwen mechanism job overnight Sat.

The comparison (T3.1) is the merge point of Q and G. If exactly one chain slips, the report degrades gracefully (see cut list); if both slip, there is no paper — hence both launch tonight.

## Task board

Tiers: **P0** = report fails without it · **P1** = major value · **P2** = cut first.

### W0 — Friday afternoon launches (everything below starts today)

| ID | Task | Role | Runtime | Deps | Output / done-when |
|---|---|---|---|---|---|
| T0.1 **P0** | **Qwen certification:** run `certify.py` on rwu04lpb (and grid checkpoints if present, opportunistically): L0, explained variance, dead-feature %, recon fidelity → `registry/sae_certificate` | Lab Asst (cluster) | 1–3 h job | — | Populated SAE certificate; numbers for report §Qwen |
| T0.2 **P0** | **Qwen characterization:** `characterize.py` on 9056/47735/44189 — selectivity vs. matched baseline, activation distributions, top-k examples, logit attribution → feature certificates | Lab Asst (cluster) | 2–4 h job | T0.1 sanity | 3 feature certificates in registry |
| T0.3 **P0** | Login-node downloads: Gemma-2-9B + 2B, Gemma Scope SAEs (mid-layer residual), circuit-tracer + 2B transcoders; verify one forward pass + SAE encode on a compute node | Lab Asst | 1–2 h | — | Offline-loadable caches verified |
| T0.4 **P0** | **Infra first-run support:** on call for certify/characterize/census first-execution failures; then Gemma steering-hook + SAE-loading adapter (delta-form) | Impl Eng | Fri eve–Sat AM | T0.1 fails or T0.3 | Chain Q unblocked; Gemma smoke-steer passes |
| T0.5 **P0** | Comparison-metric spec (1 page): exact rows/columns of the final cross-model table — this now *defines* what Chains Q and G must each produce | Me | 1 h | — | `docs/comparison_spec.md` |
| T0.6 **P1** | Corpus census (`census.py`) on the FineWeb training shards for cheese/UNESCO/Eurovision (+ poutine, for the negative-result coverage argument) | Lab Asst (cluster) | 1–2 h job | — | Prevalence table in registry |

### W1 — Qwen completion (Chain Q, continues Fri night–Sat)

| ID | Task | Role | Runtime | Deps | Output / done-when |
|---|---|---|---|---|---|
| T1.1 **P0** | Multilingual battery rerun on rwu04lpb (reuse probe sentences; en/fr/zh/ar) → overlap matrix on the *instruct* SAE | Lab Asst (cluster) | 1–2 h job | T0.1 | Fresh Qwen overlap matrix (replaces stale one) |
| T1.2 **P1** | Ablation control for 9056: clamp-to-zero + random-feature control, Lodestar-judged → sufficiency *and* necessity evidence | Lab Asst (cluster) | 2–4 h job | T0.2 | Ablation vs. baseline vs. control table (sweep_hash/experiment fix already in Lodestar) |
| T1.3 **P0** | Qwen dossier assembly: per-feature panel (examples, selectivity, dose-response curve with optimal point, certificates) | Lab Asst | 2 h collate | T0.1, T0.2 | Report-ready Qwen figure panels |
| T1.4 **P2** | Grid table: certify-only pass over any existing l16/l40/64x checkpoints (no new training, no new steering) | Lab Asst (cluster) | 2 h job | T0.1 works | Layer×width health table, or dropped silently |

### W2 — Gemma arm (Chain G)

| ID | Task | Role | Runtime | Deps | Output / done-when |
|---|---|---|---|---|---|
| T2.1 **P0** | Feature discovery: concept battery + matched baseline through Gemma-2-9B + Scope; rank candidates (specificity + logit attribution); Golden Gate Bridge as known-feature sanity anchor | Lab Asst (cluster) | 2–4 h job, Fri night | T0.3, T0.5 | Candidate features per concept |
| T2.2 **P0** | Validate matches: top-examples at depth, selectivity, logit attribution (the 77391 "it's actually Canada" trap is the explicit checklist) | Lab Asst → **Me (G1)** | 2 h Sat AM | T2.1 | Confirmed matched features for ≥1 concept (target 2) |
| T2.3 **P0** | Steering sweeps on Gemma + Lodestar judging, identical protocol/objective (coherence ≥ 5 floor) | Lab Asst (cluster) | 4–8 h job Sat | T0.4, T2.2 | Dose-response curves + optimal points, same table format as Qwen |
| T2.4 **P1** | Multilingual battery on Gemma → overlap matrix | Lab Asst (cluster) | 1–2 h job | T2.2 | Side-by-side overlap matrices |
| T2.5 **P1** | Gemma SAE context stats: L0/width/recon numbers from Gemma Scope release + spot-check on our probe data (don't re-derive what the release documents) | Lab Asst | 1 h | T0.3 | Comparable "SAE health" row for Gemma |

### W3 — Comparison (merge point)

| ID | Task | Role | Runtime | Deps | Output / done-when |
|---|---|---|---|---|---|
| T3.1 **P0** | Cross-model synthesis per T0.5 spec: matched features, selectivity, sparsity/recon context, steering response + operating windows, prevalence, multilingual overlap; includes the *asymmetries* (identity-substitution vs. content-override behavior) | Lab Asst + Me | 3–5 h Sat PM→Sun | Chains Q+G | Master table + 3–4 figures, frozen at G3 |

### W4 — Circuits (Chain C — timeboxed)

| ID | Task | Role | Runtime | Deps | Output / done-when |
|---|---|---|---|---|---|
| T4.1 **P0** | circuit-tracer on Gemma-2-2B, ONE concept (G2 pick, expected: cheese), few prompts incl. one non-English | Impl Eng setup Sat AM + Lab Asst | 3–6 h | T0.3, G2 | Attribution graphs; named heads/MLPs |
| T4.2 **P1** | Qwen mechanism sketch, same concept: attribution patching / head+MLP ablation on 9056's activation; residual contribution by layer | Lab Asst (cluster) | 4–8 h, overnight Sat | T0.2, G2 | Top-heads/MLPs table + layer plot |
| T4.3 **P1** | Circuit comparison writeup, honest about method asymmetry | Me | 2 h Sun | T4.1 (T4.2 if landed) | Report §5 |

### W5 — Deliverables (continuous, Me unless noted)

| ID | Task | Runtime | Output / done-when |
|---|---|---|---|
| T5.1 **P0** | Report: skeleton Fri night; methods + Qwen §§ Sat (incl. negative-result section — poutine/Montreal/base-SAE-transfer, already fully documented); comparison + circuits Sun; draft Sun 22:00 |
| T5.2 **P0** | Figures master (Lab Asst produces, Me curates); every figure cites a registry artifact ID |
| T5.3 **P0** | Slides (12–15): GGC → open models → same features? same circuits? → multilingual; live/canned demo = 9056 @ 55 |
| T5.4 **P1** | Provenance pass: run cards + certificates for every cited result (mostly falls out of Chain Q) |

---

## Timeline

**Fri 15:00–18:00** — Submit T0.1 (certify) FIRST; then T0.6 (census). Lab Asst starts T0.3 downloads in parallel. Impl Eng on call for T0.1 first-run failures. Me: T0.5 spec, then report skeleton.
**Fri 18:00–23:00** — T0.2 (characterize) once T0.1 sane; T2.1 (Gemma discovery) + T1.1 (multilingual) queued for overnight. Impl Eng: Gemma adapter.
**Sat 09:00 — Gate G1** (double gate): (a) Qwen certificates sane? (b) Gemma matches real? → freeze concepts. Launch T2.3 steering + T2.4 + T1.2 ablation.
**Sat 09:00–14:00** — T4.1 circuit setup/first graphs; T1.3 dossiers; Me: methods + Qwen sections.
**Sat 14:00 — Gate G2** — pick circuit concept (cleanest bilateral steering; expected cheese). Launch T4.2 overnight.
**Sat 14:00–22:00** — T3.1 starts on partial data; figure drafts.
**Sun 09:00 — Gate G3** — circuit claim strength; **freeze figures/tables**.
**Sun 09:00–15:00** — T3.1 final, T4.3, T5.4. Me: results + discussion.
**Sun 15:00–22:00** — science frozen 18:00; full draft; slides. Monday AM: polish only.

## Review gates

- **G1 Sat 09:00 (double):** Qwen certificate numbers plausible (explained-variance ~0.998 training-time claim should reproduce)? Gemma features real, not confounds? Kills weak concepts; decides whether Eurovision rides along.
- **G2 Sat 14:00:** circuit concept. Criterion: cleanest bilateral steering.
- **G3 Sun 09:00:** honest circuit claim ("similar circuits" vs. "same features, different mechanism" — both publishable); freeze.

## Cut list (in order)

1. Llama third model. 2. T1.4 grid table. 3. Eurovision. 4. T4.2 Qwen mechanism sketch (→ Gemma-only circuits + limitation note). 5. T2.4 Gemma multilingual (→ Qwen-side multilingual framed as depth). 6. T1.2 ablation control (→ report sufficiency-only with limitation).
**Never cut:** T0.1/T0.2 (without certificates the Qwen arm has no quantitative leg), T2.1/T2.2 (without a Gemma match there is no cross-model paper), T3.1, T5.1–T5.3.

## Contingencies

- **certify/characterize fails on first cluster run** (top risk, it's never been executed): Impl Eng fixes forward Fri night; hard fallback = extract L0/EV/dead-% and selectivity with a direct ad-hoc script against rwu04lpb (half-day, ugly but sufficient) and drop registry provenance claims to "partial".
- **Gemma Scope 9B too heavy** → everything drops to Gemma-2-2B; story unchanged.
- **No matched Gemma feature for a concept** → it's a finding (coverage tracks corpus prevalence — census T0.6 makes this quantitative, and the poutine negative becomes the Qwen-side twin). Remaining concept carries the comparison. Do not hunt.
- **circuit-tracer won't run offline** → pin wheels on login node; fallback: symmetric logit-lens + attribution patching on both models (weaker novelty, section survives).
- **Cluster queue stalls** → 2B-sized jobs via short interactive allocations; long jobs submitted with modest `--time` for backfill (20h-not-24h lesson from training runs); Qwen dossier collation and report writing are always-available offline work.
- **Gemma steering looks broken** → validate the hook on the Golden Gate Bridge anchor feature first; delta-form hook check; scale relative to natural activation range.
- **Both chains healthy but time short Sun** → comparison table ships with cheese only, UNESCO as appendix.

## Idle-time rules

- Every sbatch is paired with its `tail -f` log command and final-result command.
- Me is never cluster-blocked: negative-result section, methods, and the demo narrative are writable from existing logs at any moment.
- Impl Eng has exactly three jobs: chain-Q first-run support, Gemma adapter, circuit-tracer setup. No other infrastructure work.
