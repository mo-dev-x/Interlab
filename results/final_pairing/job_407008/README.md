# Job 407008 -- Gemma final-pairing mechanical acceptance (adjudication)

Sealed by: Lab Assistant B. Imported and adjudicated by Engineer 1, 2026-08-13.
Chain of custody: [`chain_of_custody.json`](chain_of_custody.json) (sha256
`10cbbb6e92b5fc5b7ec4a48974e3940c9c8495d71b1e5e5a0cf38ceb6b88984c`). File-level
hashes independently recomputed by Engineer 1 against the imported copies are
in [`inventory.json`](inventory.json); they match the manifest's own
`hashes_measured_now.*.local_copy` entries for every file, and the manifest's
own cluster-vs-local-copy hashes all report `local_matches_cluster: true`.

## Scheduler facts (sacct, tamia1)

JobID 407008, JobName `fp-gemma-de3b499`, State `COMPLETED`, ExitCode `0:0`,
2026-08-12 18:58:51 -- 19:03:01 (00:04:10), node `tg11303`,
`gres/gpu:h100=4`, `mem=500000M` (whole node, `--mem=0` requested).
Source commit `de3b499` (successor to `46a8643`, the standalone symlink
preflight -- see `final-pairing-harness` branch history). `scontrol show job`
is unavailable (purged by Slurm); `sacct` is the retained record.

## Conclusion

**Gemma-3-12B-IT with Gemma Scope 2 resid_post layer 31 passed mechanical
steering acceptance under ALL and GENERATED_ONLY in job 407008.**

Supporting facts, each independently re-read from the raw artifact in this
directory (not merely quoted from the manifest):

- `symlink_preflight_result.json`: `executed_count=11`, `passed_count=11`,
  `overall_passed=true` -- all 11 cases passed on real Linux with real
  symlinks, inside the allocation.
- `fp_gemma_407008.log` / the embedded `gemma3_tool_diff_test.py` JSON block:
  Step 0's gate passed all three documented criteria (`identical_text`,
  `identical_token_ids`, `activations_effectively_identical` all `true`,
  `gate_passed: true`).
- `gemma_3_12b_it_all.json` and `gemma_3_12b_it_generated_only.json`: both
  scenarios exited 0. Every resolved SAE file path fell inside the pinned
  snapshot and inside the ratified subdirectory
  `resid_post/layer_31_width_16k_l0_medium`
  (`sae_subdirectory_membership_verified: true`); `local_snapshot_only: true`,
  `network_resolution_attempted: false`.
- Under `positions=all`, a raw clamp of `5000.0` reached feature 250 at
  `blocks.31.hook_resid_post` on every one of 8 hook calls (1 prefill + 7
  decode); activation and residual norm changed on every call
  (`nonzero_steer_confirmed: true`).
- Under `positions=generated_only`, the prefill hook fired but wrote nothing
  (`feature_activation_after == feature_activation_before`,
  `residual_delta_norm: 0.0`); all 7 decode rows are numerically identical to
  the `positions=all` run. This is the expected and correct behavior of
  `generated_only` masking, not a defect.
- `job_result.json`: `status: "complete_pass"`, `overall_exit_code: 0`.

## Required limitations (non-claims)

- Mechanical correctness does not establish scientific concept quality or
  behavioral quality.
- Feature 250 and raw clamp 5000 are engineering acceptance inputs only.
  Feature 250 carries no ratified concept meaning for the -it pairing.
- The generated text under a saturating clamp is degenerate and is not
  evidence of model quality or of a successful semantic intervention.
- GENERATED_ONLY masks the prefill hook write and leaves the first generated
  token's activation unaffected by the intervention; this is recorded as a
  semantic difference from ALL, not reconciled, and no public `--positions`
  default is claimed here or elsewhere without separate researcher
  ratification.
- No peak-GPU-memory figure is claimed: `nvidia-smi` was sampled after the
  Python processes exited, so any value it printed is an instrumentation
  artifact, not a memory measurement.
- Step 0 ran the `-it` model/SAE paths while `--dose-multiple` reads the
  `-pt` pairing's manifest; it proves call-path equivalence, not `-pt`/`-it`
  equivalence.
- This job is independent of, and does not correct or supersede, job
  406092's Gemma failure (a loader-identity defect fixed in commit
  `8005679`, well before this job's source commit `de3b499`) -- see
  `results/final_pairing/job_406092/README.md`.
