# Job 406092 -- mixed job: Gemma failed, Qwen layer-0 mechanical evidence (adjudication)

Sealed by: Lab Assistant B. Imported and adjudicated by Engineer 1, 2026-08-13.
Chain of custody: [`chain_of_custody.json`](chain_of_custody.json) (sha256
`fbbfbaf0f8ee48a789f7217c87461f1752bb46657e5087a81f74108a90309f16`). File-level
hashes independently recomputed by Engineer 1 against the imported copies are
in [`inventory.json`](inventory.json); they match the manifest's own
`hashes_measured_now.*.local_copy` entries, its own
`expected_hash_verification.*.match: true` block, and all report
`local_matches_cluster: true`. The wrapper diff was independently reproduced
by Engineer 1 (`diff -u fp_accept.sbatch.before fp_accept.sbatch`) and is
byte-identical to the stored `fp_accept.sbatch.diff`: one added
`PYTHONPATH` line, zero deletions, matching the manifest's disclosed
single authorized edit.

## Scheduler facts (sacct, tamia1)

JobID 406092, JobName `fp-accept-e63b08e`, State `COMPLETED`, ExitCode `0:0`,
2026-08-11 18:06:44 -- 18:12:58 (00:06:14), node `tg11102`,
`gres/gpu:h100=4`, `mem=500000M` (whole node). Source commit `e63b08e`
("Gemma harness: fail closed on the exact SAE subdirectory and symlink
physical target" -- predates the loader-identity fix in `8005679`).
`scontrol show job` is unavailable (purged by Slurm); `sacct` is the
retained record.

**The scheduler's `COMPLETED`/`0:0` does not mean acceptance passed.** The
wrapper used for this job did not aggregate per-scenario exit codes, so the
two failing Gemma scenarios (below) did not propagate to the job exit code.
This exact defect is why `final_pairing_gpu_job.py`'s `aggregate_job_result`
exists in later commits (`8005679` onward).

## What actually happened, per `fp_accept_406092.log`'s own exit markers

| Stage | Exit |
|---|---|
| `STEP0_EXIT` | 0 (passed, but its own `identical_text` criterion was `false` -- the silent-pass defect later repaired in `8005679`; not itself evidence of anything below) |
| `GEMMA_IT_all_EXIT` | **1 (failed)** |
| `GEMMA_IT_generated_only_EXIT` | **1 (failed)** |
| `QWEN_all_EXIT` | 0 |
| `QWEN_generated_only_EXIT` | 0 |

**Gemma failed in job 406092.** Both Gemma-IT scenarios raised
`ValueError: ID resid_post/layer_31_width_16k_l0_medium not found in release
gemma-scope-2-12b-it-res` (traceback in `fp_accept_406092.log`) -- the flat
`sae_lens` loader id had not yet been separated from the scientific
`sae_id` at commit `e63b08e`. No Gemma scenario JSON was written by this
job. **This job is not evidence about the Gemma pairing's mechanical
behavior in either direction.** Gemma's own mechanical acceptance is sealed
separately under job 407008 (`results/final_pairing/job_407008/`).

## Conclusion

**Qwen3.5-27B with Qwen-Scope engineering layer 0 passed mechanical
steering under ALL and GENERATED_ONLY in mixed job 406092.**

**Job 406092 was NOT a global acceptance pass.** Only the statement above,
scoped to Qwen, is supported.

Supporting facts, each independently re-read from the raw artifact in this
directory:

- `qwen_3_5_27b_mechanical_all.json` and
  `qwen_3_5_27b_mechanical_generated_only.json`: both exited 0.
  `model_runtime_class: "Qwen3_5ForCausalLM"` via `AutoModelForCausalLM`,
  `hook_name: "resid_post:layer_0"`, `d_in=5120`, `d_sae=81920`, `k=50`.
- Under `positions=all`, a raw clamp of `20.0` reached feature 4096 on
  every one of 8 hook calls (1 prefill + 7 decode);
  `nonzero_steer_confirmed: true` in both scenario artifacts and in the
  log's own printed verdict JSON.
- Under `positions=generated_only`, the prefill hook fired but wrote
  nothing (`feature_activation_after: 0.0`, `residual_delta_norm: 0.0`,
  matching `feature_activation_before`); all 7 decode rows moved the
  residual by ~20.0, matching the `positions=all` decode rows.

## Required limitations (non-claims)

- Job 406092 was not a global acceptance pass (see table above).
- Gemma failed in job 406092 -- a loader-identity defect, not evidence
  about the Gemma pairing's mechanical behavior in either direction.
- Qwen layer 0 and feature 4096 are ENGINEERING-ONLY. They carry no
  scientific or concept claim whatsoever; layer 0 is not a ratified layer.
- This is MECHANICAL evidence only: it shows an intervention reached the
  hook and moved the residual. It is not a behavioral, quality,
  interpretability, or concept result.
- GENERATED_ONLY masks the prefill hook write and leaves the first
  generated token's activation unaffected; no public `--positions` default
  is claimed here or elsewhere without separate researcher ratification.
- No cross-model comparison between the Qwen and Gemma pairings is
  supported by this job.
- The Qwen diagnostic re-encode reports `feature_activation_after` values
  near, but not exactly equal to, the assigned `20.0` -- this is an
  independent re-encode through a TopK(50) SAE, not a readback, and
  equality is not claimed.
