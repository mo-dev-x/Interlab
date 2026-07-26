# Implementation Log

Running record of shared-foundation execution steps and the provenance decisions
made during them. Complements `implementation_blueprint.md` (the ED rulings): the
blueprint says *what the rule is*; this log says *what evidence a given recorded
value rests on*.

---

## T0.2 — A5 `sae_checkpoint` backfill (4 campaign SAEs)

**Date:** 2026-07-25 · **Checkpoints:** d1bgp5v5 (L16 ×32), rwu04lpb (L28 ×32),
zf2o13m2 (L40 ×32), o1cx1dow (L28 ×64) · all seed 42, topk k=100, 400M FineWeb
tokens, sae-lens 6.44.2.

### Provenance note — why `telemetry_tail.fvu_source = "training_step"` (ED-30)

ED-30 requires the recovered FVU to be "the training run's aggregated **evaluation**
FVU when available, else the final **training-step** FVU," carried with an explicit
`fvu_source` discriminator. All four A5s label it `training_step`. The evidence:

1. **No evaluation metric namespace exists in the logs.** The recovered telemetry
   lives only in each run's binary `.wandb` transaction log (the `wandb-summary.json`
   files are empty — offline runs, never synced/finalized). A full key scan of those
   logs shows only the namespaces `metrics/`, `losses/`, `sparsity/`, `details/`
   (e.g. `metrics/explained_variance`, `metrics/explained_variance_legacy`,
   `sparsity/dead_features`, `losses/mse_loss`). **There is no `eval/` namespace and
   no separately-logged eval-aggregate FVU** — so there is no `training_eval` value
   to recover, by construction.

2. **The metric stream is logged at training cadence.** `metrics/explained_variance`
   is emitted every `wandb_log_frequency = 100` steps (from `runner_cfg.json`):
   the three ×32 runs each hold **1953** history records at a final `_step = 195299`
   (195299 / 100 ≈ 1953); o1cx1dow holds 651 records at `_step = 325499`
   (~every 500 steps). The recovered value is the **last** history record — i.e. the
   final training-step value, not an eval aggregate.

3. **Conclusion.** With no eval aggregate available, ED-30's fallback applies: record
   the final training-step FVU and label it `training_step`. The value is
   `fvu = 1 − metrics/explained_variance`, using the **authoritative ratio-of-means**
   `explained_variance` (SAE-Lens 6.44.2); `explained_variance_legacy` (mean-of-ratios)
   is deliberately **not** used. `dead_count` = final `sparsity/dead_features` (same
   run, same final record). Values are recovered verbatim (bf16-rounded as logged),
   never recomputed at backfill time (ED-30).

Recovered per-run (final training-step): d1bgp5v5 EV 0.9766 → fvu 0.0234, dead 492 ·
rwu04lpb EV 0.9609 → fvu 0.0391, dead 133 · zf2o13m2 EV 0.7813 → fvu 0.2188, dead 95 ·
o1cx1dow EV 0.8867 → fvu 0.1133, dead 2626.

`training_provenance` (sae-lens 6.44.2 / transformers 5.12.1 / transformer-lens 3.4.0)
is `source: wandb, confidence: measured`, read from each run's `requirements.txt`.
`cfg_schema_generation: 6.x` (the cfg.json is 6.x-format; loads only under sae-lens 6.x,
per the ED-33 migration).

---

## T0.3 — certification (BLOCKED at first-run; escalated 2026-07-25)

Attempting certification (`certify.py`, GATE G1) on the 4 A5 checkpoints surfaced two
hard blockers — the exact "certify.py never run end-to-end on the cluster → first-run
failure" the execution roadmap named as its top risk (item 8 / Impl-Eng contingency).
Confirmed by static reading, so no doomed job was submitted.

### Gate 1 — implementation: cert lane cannot load cluster-resident artifacts (→ Impl Eng)
The certification lane is coded for `local:` artifacts and local execution, but the 14B
base model + SAE weights are cluster-only and certification needs cluster GPU:
- `interplab/jobs/certify.py::_load_sae` raises `NotImplementedError` for any non-`local:`
  weights URI. Our A5 weights ref is `tamia:sae_checkpoints/<ckpt>/final_*`.
- `interplab/jobs/certify.py::_load_model` raises `NotImplementedError` for any non-`local:`
  model URI. Our A5 model ref is `hf:Qwen/Qwen2.5-14B-Instruct@cf98f3b3…caa8`.
- Module docstring: *"this job never runs on the cluster in this environment"* — stale for
  this deployment.
- `interplab/certification/eval_slice.py::load_corpus_docs` supports `local:`/`hf:` only
  (`tamia:` explicitly unsupported, lines 46/77).

Required change (cert-lane loading architecture — Impl Eng, not self-authored): resolve
`tamia:` weights (→ `$SCRATCH/interplab/...`) and the `hf:<repo>@<sha>` model (→ the local
HF snapshot) on the cluster, and support cluster/GPU execution. Facts for Impl Eng:
weights `/scratch/y/yazid/interplab/sae_checkpoints/<ckpt>/final_*`; model snapshot
`/scratch/y/yazid/hf_cache/models--Qwen--Qwen2.5-14B-Instruct/snapshots/cf98f3b3…caa8`;
sae-lens 6.44.2 / transformer-lens 3.4.0 installed; ED-32 baseline now 6.x (passes).

### Gate 2 — provenance: no eval holdout was reserved (→ researcher, ED-5)
ED-5 certificate metrics must be computed on a slice **disjoint from training**. The 4 SAEs
consumed the FineWeb `take_tokens: 400M` prefix `as_is` — no holdout was reserved. For a
legacy checkpoint (`store_hash: null`) certify REQUIRES `eval_slice.method/params`:
- `holdout_split` over the same corpus_manifest would NOT be disjoint (training used all
  docs inside the 400M prefix) — invalid.
- `stream_offset` into `fineweb_subset` **beyond** the 400M-token training bound (the
  untrained remainder of the 262 GB dataset) is genuinely held out — the valid choice.
Decision needed (researcher): confirm `stream_offset` past the training bound, and the
offset/count. Recommendation: offset at the first document after 400M consumed tokens,
count sized to `n_tokens` (e.g. a few M eval tokens).

### Update 2026-07-25 (after ED-34)
- **Gate 1: RESOLVED by ED-34** — `certify._load_sae` resolves `tamia:` (`uris.resolve_tamia`);
  `_load_model` resolves the `hf:@rev` model via a pinned download into the single
  fidelity-correct `load_local_hooked_transformer` (not a second build path).
- **Gate 2: only one ED-5-valid option, offset is mechanically fixed.** `stream_offset` past
  the training bound; `offset = 601369` (= A1 `doc_count`, the first untrained doc);
  `corpus_manifest_hash = A1 88740b746361`. Proceeding with this unless vetoed.

### Gate 3 — NEW, surfaced by ED-34's eager loader (→ Impl Eng)
`interplab/certification/eval_slice.py::load_corpus_docs` (dir branch) does
`return [row[text_field] for row in ds]` — it **materializes the entire corpus** before
`select_stream_offset` slices `docs[offset:offset+count]`. Verified corpus scale:
`fineweb_subset` = **32,589,370 docs / ~101 GB text** (434 arrow shards). Materializing that
into a Python list OOMs on any node; `stream_offset` at doc 601369 is therefore unrunnable
as written. No config knob avoids it (`_resolve_eval_slice` passes no `limit`, and the dir
branch slices `docs[:limit]` only *after* full materialization).

Required fix (mirrors the already-sanctioned `corpus.replay` generator pattern): make the
`local:`/`tamia:` readers **stream** and push the positional bound down —
`itertools.islice(rows, offset, offset + count)` — so `stream_offset` reads only
`offset+count` docs and never builds the full list. `select_stream_offset` should consume an
iterator with early stop rather than index a materialized list. Provenance is unchanged
(`corpus_manifest = A1`, `method = stream_offset`, `params = {offset: 601369, count: …}`).
Same eager-read latent in `select_holdout_split` (full scan) — not on our path today but the
same class.

### Gate 3 — RESOLVED (researcher-blessed islice fix, implemented 2026-07-25)
Blessed as provenance-safe/byte-identical and implemented in `interplab/certification/eval_slice.py`:
- `_iter_local_jsonl` / `_iter_local_hf_dataset` are now **generators** (mirror the `replay` twins).
- New lazy primitive `iter_corpus_docs()`; `load_corpus_docs()` kept as a materializing wrapper
  (backward-compatible list return — `holdout_split` path + all existing tests unchanged).
- `select_stream_offset()` now `list(itertools.islice(docs, offset, offset+count))` — byte-identical
  to `docs[offset:offset+count]` for a list, and over the lazy iterator materializes only `count`.
- `certify._resolve_eval_slice`: `stream_offset` consumes `iter_corpus_docs` lazily; `holdout_split`
  still uses `load_corpus_docs` (its eager scan is the deferred sibling below).
Tests: 29 pass (eval_slice + certify), incl. a new laziness test proving an unbounded source is
consumed to exactly `offset+count` then stopped.

**Deferred sibling (logged, not fixed — researcher-directed):** `select_holdout_split` still scans a
materialized list. It is reached only by store-backed checkpoints (SS3 `train`, unbuilt/researcher-gated);
all 4 current checkpoints are legacy/`stream_offset`. Its fix is a streaming residue filter
(scan rows, materialize only hash-mod matches) when SS3 lands.

### Gate 2 — RESOLVED (researcher ruling): `stream_offset`, offset = 601369 (A1 doc_count = training bound).
Eval params (researcher-approved): `n_tokens = 10_000_000` (unbiased `dead_fraction` for 163k–327k-feature
SAEs; bands are placeholders but metrics stored raw), `batch_size = 8` (→16 if node headroom;
batch-size-invariant metrics), `seq_len = 512`, `count = 25000` docs (~16.6M tokens available, capped to
n_tokens), `corpus_location = local:data/raw/fineweb_subset`, `corpus_manifest = A1 88740b746361`,
`bands_version = 1`.

### T0.3 — COMPLETE: 4 A6 sae_certificate artifacts recorded (GATE G1).
All four certified on the Tamia H100 node (whole-node `h100:4`, ED-7 GPU path), fresh fp32 metrics over the
held-out 10M-token slice (offset 601369, count 25000). Five never-run-GPU-path defects cleared to get here:
URI resolution (ED-34), lazy corpus streaming (ED-34 Gate-3, ~101GB→islice), GPU device/dtype
(`_certify_device_dtype` CUDA+bf16), model buffer colocation (`model.to(device)`), and the metrics-accumulator
device mismatch (`.double().cpu()` in `metrics.py`, CPU-invisible → CI-invisible). o1cx1dow (64× SAE) OOM'd at
batch_size 8 → halved to 4 (batch-invariant metrics, not in cert payload; commit 7b9478d). All `self_hash`
verified, filename-consistent, n_tokens 9,999,872.

| SAE | Layer×Exp | job | cert (A6) | verdict | fvu | ce_recovered | dead_fraction |
|-----|-----------|-----|-----------|---------|-----|--------------|---------------|
| d1bgp5v5 | L16×32 | 383669 | ed82c7245ca7 | amber | 0.0076 | 0.9938 | 0.0020 |
| rwu04lpb | L28×32 | 383528 | 0a572198764d | amber | 0.0103 | 0.9884 | 0.0008 |
| zf2o13m2 | L40×32 | 383670 | 1167ac6f099a | amber | 0.0441 | 0.9785 | 0.0000 |
| o1cx1dow | L28×64 | 383685 | fbdd53715b12 | green | 0.0162 | 0.9884 | 0.0012 |

Verdicts sit on placeholder bands (v1); the raw metrics are the deliverable. Certify-slice FVU differs from
T0.2 training-telemetry FVU (fresh held-out fp32 eval vs training-step telemetry); dead_fraction is near-zero
by design of the 10M-token unbiased override. Report cards on cluster at
`results/certificates/<hash12>/report_card.md` (not copied — human-facing, not provenance).

### Characterize-Lite — COMPLETE (roadmap T0.2, ad hoc; NOT characterize.py).
User directive under credit budget: do NOT fix the full characterization pipeline; build a minimal ad hoc
script for report-critical evidence only, max 2 cluster debug cycles. Built `scripts/characterize_lite.py`
(reuses certify GPU/bf16 + `certification.model_loading` + `eval_slice.load_corpus_docs` islice; plain
JSON/PNG out; no registry writes/dashboards). **Cycle 1 passed** (job 383755, COMPLETED 14m32s, exit 0):
5,000 FineWeb docs → 1,712,777 positions on rwu04lpb. Results in `docs/characterize_lite_findings.md` +
`results/characterize_lite/rwu04lpb/`. Headline: 9056 (cheese, max 47.5) and 47735 (UNESCO, max 40.75) are
clean monosemantic; 44189 (Eurovision, max 8.5, incoherent top examples) empirically weak — confirms the
roadmap pre-flag. characterize.py, Gemma, circuits, dashboards untouched per directive.

### T1.1 multilingual rerun — COMPLETE (final production run, 1 cycle, no fix needed).
User directive: last cluster experiment under credit budget (91%), max 1 debug cycle. Built ad hoc
`scripts/multilingual_rerun.py` (reuses certify GPU/bf16 loaders; same probe sentences; faithful
mean-activation top-20 + overlap-matrix method from legacy find_features.py, but on rwu04lpb's own
hook_resid_post via transformer_lens and with BOS excluded). **Cycle 1 passed** (job 383758, COMPLETED
2m21s, exit 0). Replaces the degenerate stale base-SAE matrix (which had identical 20 "shared" features for
every concept). New differentiated result: world_cup 13/20 shared (Jaccard 0.66), quebec 12/20 (0.62),
poutine 10/20 (0.51), couscous 4/20 (0.38). Restores a valid Qwen cross-language side. Results in
`docs/multilingual_findings_rwu04lpb.md` + `results/features/multilingual_rwu04lpb/`. Report assets
(fig_sae_certification, fig_feature_selectivity, fig_multilingual_overlap, docs/report_tables.md) built
locally from existing results. **Recommend freezing the experimental phase here.**
