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
