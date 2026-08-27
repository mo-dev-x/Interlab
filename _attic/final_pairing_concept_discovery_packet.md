# Final-pairing shared-concept discovery and calibration -- Tamia command packet

Scope: discovers CANDIDATE features for a researcher-supplied concept on
the two ratified final pairings, validates them held-out, runs causal
intervention and dose-response, and proposes Low/Medium/High calibration
candidates. This is statistical/mechanical evidence for later scientific
and behavioral judgment -- it invents no concept labels and no scientific
thresholds (every threshold below is a required CLI argument with no code
default; see "Unresolved protocol fields" at the end of this document).

Built on `final-pairing-harness` (successor to `b6d598b`). Seven scripts
under the non-legacy `scripts/final_pairing/` package (relocated from
`scripts/legacy/` in this pass; thin `runpy`-based wrappers remain at the
old `scripts/legacy/<name>.py` paths purely for command-line
backward-compatibility -- they carry no logic and forward to the real
implementation), none of which modify `final_pairing_harness.py`,
`final_pairing_targets.py` (both of which correctly remain under
`scripts/legacy/`, the already-accepted mechanical-acceptance harness),
or anything under `interplab/` (Engineer 3's sealing pipeline):

- `scripts/final_pairing/final_pairing_concept_discovery.py` -- the per-pairing
  discovery/calibration runner (7 stages).
- `scripts/final_pairing/final_concept_discovery_dual_gpu_job.py` -- concurrent
  Gemma+Qwen orchestration inside one Slurm allocation, one node, 4xH100
  (Gemma on physical GPU 0, Qwen on physical GPU 1, GPUs 2-3 reserved for a
  separately authored judge process).
- `scripts/final_pairing/final_concept_discovery_matched_configuration_job.py` --
  primary-then-conditional-backup sequencing across the two predeclared
  matched configurations, on top of the dual-GPU orchestrator.

**Not run against real weights or a GPU** -- no allocation was available
during this investigation. Every reuse decision below (which primitives
were imported unmodified vs. duplicated per this project's own Ground
Rule 2) is documented in each script's own module docstring; this packet
does not repeat that reasoning, only the runnable commands and schemas.

## Pairing-specific entry points

### Gemma discovery

```bash
HF_HUB_OFFLINE=1 python scripts/final_pairing/final_pairing_concept_discovery.py \
  --pairing gemma-3-12b-it \
  --model-path /path/from/lab-assistant-1/inventory/gemma-3-12b-it \
  --sae-path /path/from/lab-assistant-1/inventory/gemma-scope-2-12b-it \
  --layer 29 \
  --expected-model-revision <from inventory> \
  --expected-sae-revision <from inventory> \
  --prompt-set-path /path/to/prompt_set.json \
  --prompt-set-sha256 <sha256 of that exact file> \
  --judge-config /path/to/judge_config.json \
  --positions all \
  --seed 0 \
  --shortlist-size 20 \
  --direction clamp \
  --dose-grid 0.5,1,2,4,8 \
  --specificity-auc-threshold <Architect> \
  --bundle-materiality-threshold <Architect> \
  --bundle-max-size 1 \
  --calibration-low-threshold <Architect> \
  --calibration-medium-threshold <Architect> \
  --calibration-high-threshold <Architect> \
  --device cuda:0 \
  --out-dir results/final_pairing/concept_discovery/gemma/ \
  --state-dir results/final_pairing/concept_discovery/gemma_state/
```

`--layer 29` (primary) or `24` (backup) -- the two predeclared,
matched-configuration Gemma layers (see "Matched configurations" below).
Layer 31 (the mechanically-accepted engineering layer, job 407008) is
rejected: it is not a scientific candidate.

### Qwen discovery

```bash
HF_HUB_OFFLINE=1 python scripts/final_pairing/final_pairing_concept_discovery.py \
  --pairing qwen-3.5-27b \
  --model-path /path/from/lab-assistant-1/inventory/qwen3.5-27b \
  --sae-path /path/from/lab-assistant-1/inventory/qwen-scope/layer38.sae.pt \
  --layer 38 \
  --qwen-sae-family L0_100 \
  --qwen-sparsity 100 \
  --expected-model-revision <from inventory> \
  --expected-sae-revision <from inventory> \
  --prompt-set-path /path/to/prompt_set.json \
  --prompt-set-sha256 <sha256 of that exact file> \
  --judge-config /path/to/judge_config.json \
  --positions all \
  --seed 0 \
  --shortlist-size 20 \
  --direction clamp \
  --dose-grid 0.5,1,2,4,8 \
  --specificity-auc-threshold <Architect> \
  --bundle-materiality-threshold <Architect> \
  --bundle-max-size 1 \
  --calibration-low-threshold <Architect> \
  --calibration-medium-threshold <Architect> \
  --calibration-high-threshold <Architect> \
  --device cuda:0 \
  --out-dir results/final_pairing/concept_discovery/qwen/ \
  --state-dir results/final_pairing/concept_discovery/qwen_state/
```

`--layer 38` + `--qwen-sae-family L0_100` + `--qwen-sparsity 100` (primary)
or `--layer 32` + `L0_50` + `50` (backup) -- the two predeclared, matched
Qwen configurations. Layer 0 (the mechanically-accepted engineering layer,
job 406092) is rejected: it is not a scientific candidate. SAE family,
layer, and sparsity are three distinct, independently-recorded fields in
both the CLI and the output provenance -- never conflated, per the ratified
scientific SAE decision's explicit requirement.

`--device cuda:0` is required for BOTH commands when run under the dual-GPU
orchestrator below (each child sees only one physical GPU via
`CUDA_VISIBLE_DEVICES`, remapped to index 0 from inside that process) --
running either command standalone, outside the orchestrator, on a
multi-GPU node without `CUDA_VISIBLE_DEVICES` already restricting
visibility would need a real device ordinal instead.

## `--prompt-set-path` / `--prompt-set-sha256`

One hash-pinned JSON file per concept, loaded and validated, never
generated by this tool (same "load/validate only" discipline as
`interplab.corpus.battery`'s concept battery):

```json
{
  "concept_id": "researcher-chosen bare identifier, never invented here",
  "probes": ["...", "..."],
  "controls": ["...", "..."],
  "holdout_probes": ["...", "..."],
  "holdout_controls": ["...", "..."],
  "background_corpus": ["...", "..."]
}
```

`--prompt-set-sha256` must equal the file's actual sha256; a mismatch
raises `TargetIdentityMismatch` before anything loads. `probes`/`controls`
are used for ranking (stage 1) and TRAIN-side probe fitting (stage 2);
`holdout_probes`/`holdout_controls` are a genuinely separate split, never
touched by ranking or training, used only to SCORE stage 2's held-out AUC;
`background_corpus` is a general (non-concept) text sample used exclusively
to compute each feature's `corpus_max` (the dose-grid scale unit) -- kept
separate from the concept probes so the unit a dose is expressed in is
never circularly derived from the texts used to find the feature. Each
list needs at least 5 examples (the frozen probe recipe's own floor).

## Frozen prompt artifact (`prompts/final_pairing/v1/`)

Real, already-committed, hash-verified against the checked-out working
tree: commit `880b48a7f50b8c716e64956b915857dd1fcde350`,
`prompt_sets.jsonl` sha256 `b0b23cf1502dae53f88905ee7393b7e67f8b05f84f3251d26a6c506480a9531f`,
`metadata.json` sha256 `3f8e298a18c5ba03a2aaaa4a4b99302602f381ee42b024b131fd2cf63b4b59ce`
-- 2,800 rows, 14 concepts x 2 locales, 5 splits, 3 paraphrase families per
concept. Add `--use-frozen-prompt-artifact` to either discovery command to:

1. run the committed `validate_prompt_sets.py` as a real subprocess and
   raise `PromptArtifactError` on any nonzero exit;
2. verify the working tree has NO uncommitted changes under
   `prompts/final_pairing/v1/` (`git status --porcelain`) -- refuses a
   dirty or uncommitted replacement;
3. verify both files' actual sha256 against the pinned values above;
4. verify `row_count==2800`, `concept_count==14`, both locales, and all
   five declared splits are present;
5. exclude `political_framing` (`pi_gated: true`) from every downstream
   stage UNLESS `--allow-pi-gated` is also passed explicitly -- never
   default-on;
6. stamp `prompt_set_commit`/`prompt_set_sha256` into the discovery
   result.

**This check must stop BOTH lanes, not just whichever one runs it first.**
`final_concept_discovery_dual_gpu_job.py`'s `main()` now calls
`default_prompt_artifact_validator` (which runs steps 1-4 above) ONCE,
before `launch_all()` is called for either lane -- a validation failure
writes `job_result.json` with `status: "failure"`, `lanes: []`, and
`prompt_artifact_validation_error` set, and neither lane is ever launched.

`compute_gate_a_and_b_per_family(backend, artifact, concept_id=..., locale=...,
feature_index=...)` computes G-A (separation AUROC, positive vs. the
shared `unrelated` substrate) and G-B (activation-floor / fire-rate)
INDEPENDENTLY per paraphrase family (F1/F2/F3), never pooled, reading its
default thresholds from the frozen artifact's own
`metadata.json["thresholds"]` (`G_A_separation_auroc_min: 0.9`,
`G_B_activation_floor_fraction_of_observed_max: 0.2`,
`G_B_fire_rate_min: 0.7`) -- never invented in code, and overridable
explicitly by a caller with a documented reason to. `shared_substrate`
semantics (`unrelated`/`heldout_neutral` rows are IDENTICAL across all 14
concepts by design) are preserved by `rows_for_concept`, which does not
deduplicate across concepts. `compute_gate_c_per_family` (G-C, specificity
AUROC vs. `near_miss`), `feature_survives_gabc`, `evaluate_concept_on_
pairing`, and `run_concept_grid` now assemble the FULL 14-concept x
2-pairing grid automatically (same-feature G-A+G-B+G-C conjunction), and
`compute_primary_completeness_and_shared_count`/`evaluate_backup_trigger`
compute `primary_complete`/`primary_shared_gabc_count`/`RUN_BACKUP`/
`FAIL_RUN` from that grid -- the gap this section previously described is
closed.

## `--judge-config` and the judged gates (G-D/G-E)

`--judge-config` still only records identity metadata for the generic
stage-6 dose curve. G-D (Amplify) and G-E (Suppress) are judged gates and
are now REAL: `scripts/final_pairing/final_pairing_causal_judge.py`
computes their pass/fail arithmetic against the real, separate Lodestar
package (`d:/lodstar`), and `scripts/final_pairing/final_pairing_judge_
cli.py` is the actual, runnable CLI that drives a real Lodestar
`AnthropicJudge` run against transfer-verified generation files -- see
"The one-allocation two-machine workflow" below for the real commands.
Omitting `--judge-config` still records the honest `{"model": "none",
...}` identity `interplab.characterization.indexer.NoOpJudge` uses for
the unrelated, non-judged stage-6 curve; it has no bearing on G-D/G-E,
which always go through the real judge CLI now that it exists.

## Gemma dynamic hook resolution (LA-C preflight)

`load_gemma_scientific_target` never manually traverses raw HF attribute
paths (`model.layers.<N>`, `language_model.model.layers.<N>`, or any
`vision_tower`/`multi_modal_projector` module) at all -- it loads via
`HookedTransformer.from_pretrained` (the SAME mechanism the mechanically-
accepted layer-31 path already uses) and hooks by TransformerLens hook
NAME (`blocks.<layer>.hook_resid_post`), which is TransformerLens's own
text-decoder-only graph; there is no code path here that could resolve
onto a vision-side module. `run_gemma_hook_preflight(model, sae, hook_name,
expected_hidden_dim=3840)` still runs a real, tiny forward pass with a
temporary probe hook, parametrically for whatever layer/hook_name was
actually resolved (29, 24, or any future layer -- nothing is hardcoded to
one layer), and fails closed (`TargetIdentityMismatch`) unless the hook
fires at least once AND the captured tensor's last dimension is exactly
3840. Its result (`configured_hook_string`, `runtime_class`, `hook_fired`,
`hook_invocation_count`, `captured_last_dim`, `passed`) is recorded in
`provenance.sae.hook_preflight` -- "configured hook string, resolved
runtime path, runtime class and validation evidence," per this check's own
requirement, all in one place.

## Environment (Tamia batch wrapper)

No pipes, no command substitution, in this exact order:

```bash
module load StdEnv/2023 python/3.11 arrow/25.0.0
source /home/y/yazid/sprint-venv/bin/activate

export HF_HOME=/scratch/y/yazid/hf_cache
export HF_HUB_CACHE=/scratch/y/yazid/hf_cache/hub
export HF_HUB_OFFLINE=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID
```

Never `pip install pyarrow` -- the wheelhouse package is a dummy; only the
loaded `arrow/25.0.0` module provides a real one. Model/SAE loading is
already exclusively by local snapshot path + immutable revision
(`load_gemma_it_target`/`load_gemma_scientific_target`/
`load_qwen_scientific_target` all fail closed via
`final_pairing_targets.validate_local_snapshot_identity` on anything else)
-- nothing in this packet resolves by repository name or `refs/main`.

## Scheduler packet

```
#SBATCH --nodes=1
#SBATCH --gres=gpu:h100:4
#SBATCH --time=03:00:00
#SBATCH --mem=0
#SBATCH --account=aip-chgag196
```

The three-hour request opens `gpubase_bynode_b1`. Resumable state
(`--state-dir`'s `progress.jsonl`) is preserved after every completed
stage regardless of wall-clock or Slurm cancellation, per
`final_pairing_concept_discovery.py`'s existing resumability design
(unchanged by anything in this dispatch).

## Matched configurations

```
                     Qwen layer   Qwen SAE family   Qwen sparsity (k)   Gemma layer
Primary                  38            L0_100              100              29
Backup                   32            L0_50               50               24
```

`--layer`/`--qwen-sae-family`/`--qwen-sparsity` must be one of these four
values for their respective pairing -- a third layer or family is rejected
before any weights load (`final_pairing_concept_discovery.PRIMARY_
CONFIGURATION` / `BACKUP_CONFIGURATION` / `MATCHED_CONFIGURATIONS` is the
single source of truth both the CLI validators and this table read from).
LA-B's own verification of these exact filenames/n_layers/sparsity-meaning
against official Qwen-Scope/Gemma-Scope-2 metadata is a precondition for
staging either configuration's SAE file -- not something this tool
performs (it has no network/Tamia access).

## Combined orchestration entry point (dual GPU, one Slurm allocation)

```bash
python scripts/final_pairing/final_concept_discovery_dual_gpu_job.py \
  --gemma-config /path/to/gemma_lane.json \
  --qwen-config /path/to/qwen_lane.json \
  --job-result-path results/final_pairing/concept_discovery/dual_gpu_job_result.json \
  --poll-interval-seconds 5
```

Each `*_lane.json`:

```json
{
  "out_dir": "results/final_pairing/concept_discovery/gemma/",
  "state_dir": "results/final_pairing/concept_discovery/gemma_state/",
  "tmp_dir": "results/final_pairing/concept_discovery/gemma_tmp/",
  "log_path": "logs/final_pairing/concept_discovery/gemma.log",
  "argv": ["--pairing", "gemma-3-12b-it", "--model-path", "...", "--sae-path", "...",
            "--layer", "29", "--expected-model-revision", "...", "--expected-sae-revision", "...",
            "--prompt-set-path", "...", "--prompt-set-sha256", "...", "--judge-config", "...",
            "--positions", "all", "--seed", "0", "--shortlist-size", "20", "--direction", "clamp",
            "--dose-grid", "0.5,1,2,4,8", "--specificity-auc-threshold", "...",
            "--bundle-materiality-threshold", "...", "--calibration-low-threshold", "...",
            "--calibration-medium-threshold", "...", "--calibration-high-threshold", "..."]
}
```

`out_dir`/`state_dir`/`tmp_dir`/`log_path` are AUTHORITATIVE (the
orchestrator appends `--out-dir`/`--state-dir` from these fields, and
`--device cuda:0`, to the built command LAST, so they win over anything
already in `argv`) -- the orchestrator validates all four paths are
pairwise disjoint across both lanes BEFORE launching either process, and
raises `LaneConfigError` (never launching anything) on any collision.

`CUDA_VISIBLE_DEVICES` is fixed by lane NAME, never read from the JSON:
`gemma` always gets `0`, `qwen` always gets `1`. There is no code path in
this file that can produce any other value, and GPUs 2-3 are never
assigned to either lane.

`job_result.json` schema:

```json
{
  "schema_version": 1,
  "status": "complete_pass | partial_execution | failure",
  "overall_exit_code": 0,
  "cancelled": false,
  "lanes": [
    {
      "name": "gemma", "command": ["...", "..."], "cuda_visible_devices": "0",
      "out_dir": "...", "state_dir": "...", "log_path": "...",
      "pid": 12345, "start_time": 1234567890.0, "end_time": 1234567895.0,
      "exit_code": 0, "attempted": true, "terminated_by_signal": false
    }
  ]
}
```

`"complete_pass"`: both lanes attempted, neither terminated by a signal,
both exit 0. `"partial_execution"`: the job was cancelled (Slurm
termination propagated to both lanes via `SIGTERM`/`SIGINT`) or a lane was
never attempted. `"failure"`: both lanes ran to completion but at least one
exited nonzero -- a later lane's success never overwrites an earlier lane's
failure (`aggregate()` reads all lane results together, never sequentially).
One lane finishing does not block or terminate the other; it is left
running until it finishes or the job is cancelled. This file never reads,
merges, or reinterprets either lane's own `result.json` -- no canonical
evidence or bundle is authored here.

## Matched-configuration sequencing (primary, then conditional backup)

```bash
python scripts/final_pairing/final_concept_discovery_matched_configuration_job.py \
  --primary-gemma-config /path/to/primary_gemma_lane.json \
  --primary-qwen-config /path/to/primary_qwen_lane.json \
  --backup-gemma-config /path/to/backup_gemma_lane.json \
  --backup-qwen-config /path/to/backup_qwen_lane.json \
  --trigger-inputs-json /path/to/trigger_inputs.json \
  --primary-gemma-grid-path results/final_pairing/concept_discovery/gemma/grid.json \
  --primary-qwen-grid-path results/final_pairing/concept_discovery/qwen/grid.json \
  --concept-id cheese --concept-id astronomy \
  --job-result-path results/final_pairing/concept_discovery/matched_job_result.json
```

**`--run-backup` no longer exists as a CLI input -- it is a test-only
override, never a scheduled-run flag.** The backup trigger's Boolean rule
is frozen at `protocols/final_pairing/v1/backup_trigger.json` (commit
`125b1d3`): `RUN_BACKUP = primary_complete AND (primary_shared_gabc_count
< 3)`, `FAIL_RUN = NOT primary_complete`. Its input,
`primary_shared_gabc_count`, is now computed FOR REAL: `final_pairing_
concept_discovery.run_concept_grid`/`evaluate_concept_on_pairing`
assemble the full 14-concept x 2-pairing grid (same-feature G-A+G-B+G-C
conjunction, G-C now implemented via `compute_gate_c_per_family`), each
pairing writes its own `grid.json`
(`write_grid_result`/`read_grid_result`, exact path only, never globbed),
and `compute_trigger_from_grid_outputs` in the matched-configuration job
reads BOTH `--primary-*-grid-path` files, calls `compute_primary_
completeness_and_shared_count` + `evaluate_backup_trigger`, and passes
the result on automatically -- `run_matched_configuration_job` calls this
`trigger_resolver` whenever `run_backup` is not explicitly given, raising
`TriggerResolutionFailed` on `FAIL_RUN` rather than launching anything.
`--trigger-inputs-json` is still loaded and persisted verbatim into the
output for audit, but never used to compute the boolean.

The frozen file's **depth-matching assertion** is now wired into the real
loader: `load_gemma_scientific_target` computes `gemma_n_layers` from the
actually-loaded model's `config.json` (`resolve_gemma_num_hidden_layers`,
preferring `text_config.num_hidden_layers`), cross-checks it against
`model.cfg.n_layers`, and calls `assert_gemma_qwen_depth_matches(gemma_
layer=..., gemma_n_layers=..., qwen_depth_fraction=...)` before recording
`provenance["depth_matching"]` -- no longer a documented-but-unwired gap.

**Backup execution is gated on readiness, not merely triggered.**
`check_backup_readiness`/`assert_sufficient_time_for_backup` (1.5x the
elapsed primary time against the remaining Slurm wall clock) and `assert_
sufficient_free_vram` (real `gc.collect()`/`torch.cuda.empty_cache()`/
`torch.cuda.mem_get_info()`, time checked first so an insufficient-time
verdict never queries VRAM) run immediately before backup would launch;
`run_matched_configuration_job`'s result records `backup_execution_
status` as exactly one of `COMPLETE`/`PARTIAL`/`NOT_ATTEMPTED` --
`NOT_ATTEMPTED` when triggered but not readiness-cleared, with
`selected_configuration` correctly falling back to PRIMARY in that case.

Primary and backup run SEQUENTIALLY through the same dual-GPU orchestrator
(never concurrently) -- primary's subprocesses have already exited, so
their CUDA context and loaded weights are already released, before backup
(if triggered) launches. The four lane JSONs' `out_dir`/`state_dir`/
`tmp_dir`/`log_path` are validated pairwise-disjoint ACROSS primary and
backup (not just within each) before either primary or backup launches --
`MatchedConfigurationError` if any collide, so primary's results can never
be overwritten by a backup run. Every lane in the output is stamped
`"configuration": "primary"` or `"configuration": "backup"` -- never
conflated. Neither configuration's discovered feature/bundle content is
ever read or combined by this file (see the module's own docstring) --
there is no code path here that could mix features across layers or SAE
families into one bundle.

## Expected output: `result.json` (one per pairing, per configuration)

```json
{
  "schema_version": 1,
  "pairing": "gemma-3-12b-it | qwen-3.5-27b",
  "concept_id": "...",
  "prompt_set": {"source_path": "...", "sha256": "..."},
  "judge": {"model": "...", "rubric_version": "...", "prompt_version": "..."},
  "status": "complete | no_candidate_passed_specificity",
  "seed_feature": 1234,
  "ranked_candidates": [{"feature_index": 1234, "activation_score": 5.2}],
  "specificity_results": [
    {"feature_index": 1234, "train_auc": 0.97, "holdout_auc": 0.95,
     "holdout_feature_auc": 0.93, "holdout_gap": 0.02, "passed": true}
  ],
  "bundle": {"feature_indices": [1234], "final_metric": 0.93, "steps": []},
  "direction": "clamp | ablate",
  "positions": "all | generated_only",
  "dose_response": [
    {"feature_indices": [1234], "direction": "clamp", "value_in_max_units": 1.0,
     "corpus_max_used": 12.3, "absolute_clamp_value": 12.3, "positions": "all",
     "generated_text": "...", "verdict": {"nonzero_steer_confirmed": true, "...": "..."},
     "spec": {"kind": "clamp", "feature_index": 1234, "value_in_max_units": 1.0,
               "corpus_max": 12.3, "positions": "all", "checkpoint_hash": "...",
               "direction_seed": null}}
  ],
  "generated_only_diagnostic": null,
  "calibration_candidates": {
    "low": {"tier": "low", "value_in_max_units": 1.0, "outcome": "... (same shape as one dose_response entry)"},
    "medium": null,
    "high": null
  },
  "provenance": {
    "model": {"repository": "...", "local_path": "...", "revision": "...", "..." : "..."},
    "sae": {"repository": "...", "sae_family": "L0_100 (Qwen only, or null for Gemma)", "..." : "..."},
    "layer": 29,
    "sae_family": "L0_100 (Qwen) | null (Gemma)",
    "sparsity": "100 (Qwen) | null (Gemma)",
    "checkpoint_hash": "...",
    "corpus_max": {"0": 3.1, "1": 0.0, "...": "..."}
  }
}
```

`spec` is shaped exactly like `interplab.interventions.spec.
InterventionSpec` (`kind`/`feature_index`/`value_in_max_units`/
`corpus_max`/`positions`/`checkpoint_hash`/`direction_seed`) so a later pass
through Engineer 3's sealing pipeline sees a familiar shape without this
tool calling `envelope.dump`/`registry.put` itself -- this tool never
authors an A9 envelope or writes to the registry.

`status: "no_candidate_passed_specificity"` is a complete, valid result
(not a crash): every shortlisted candidate failed stage 2's held-out AUC
threshold, so stages 3-7 never ran; `bundle`/`dose_response`/
`calibration_candidates` are absent from that result.

## Archiving the discovery source (Tamia staging)

The discovery source MUST be archived from this exact successor commit in
**qwen-sae-interp** -- never from a repository named `sae-concept-lab` (not
this project; if that name surfaces anywhere in staging instructions,
treat it as a stop-and-flag mismatch, not something to reconcile silently).

Plain `git archive` is prohibited here: it omits the untracked runtime
`transfer_manifest.json`, leaving the no-`.git` Tamia extraction unable to
verify its frozen prompt bytes. Build the archive with the committed builder:

```bash
# From qwen-sae-interp on final-pairing-harness, at the exact successor:
git rev-parse --abbrev-ref HEAD   # final-pairing-harness
git remote get-url origin         # qwen-sae-interp, never sae-concept-lab
COMMIT=$(git rev-parse HEAD)
python scripts/final_pairing/build_transfer_archive.py \
  --repo-root . --commit "$COMMIT" \
  --output "final_concept_discovery_${COMMIT}.tar.gz"
```

The builder reads every recorded byte from `${COMMIT}`, adds root-level
`transfer_manifest.json` and `SOURCE_COMMIT`, and emits the SHA-256 sidecar.
Before transfer, inspect the archive and require both root members; after
extraction, run `discovery_preflight.py` there before any CUDA child.

The underlying tree comes from `git archive` at a fixed commit, while the
builder deterministically adds the two runtime-verification members. The
`.sha256` sidecar is the chain-of-custody hash
for whatever copy is actually transferred to Tamia (the same convention
`results/final_pairing/job_407008/chain_of_custody.json` already
established for the mechanical-acceptance evidence). Verify on the
receiving end with `sha256sum -c final_concept_discovery_${COMMIT}.tar.gz.sha256`
before staging or running anything from the extracted tree.

## The one-allocation two-machine workflow

Frozen at `protocols/final_pairing/v1/one_allocation_dose_generation.json`
(v1.0.0, `gating: true`): Tamia has no outbound internet, so Lodestar
cannot be called from inside a GPU allocation, and only ONE combined
allocation is authorized. The resolution is to move ALL generation before
ALL judging -- concretely, a Tamia (offline, GPU) stage followed by a
SEPARATE local (networked) judging stage, connected by a verified
transfer, never the reverse and never interleaved:

1. **Tamia, one allocation (offline): discovery + generation.**
   `final_pairing_concept_discovery.py`'s grid functions compute G-A/B/C
   (see above); `scripts/final_pairing/final_pairing_one_allocation_
   generation.py`'s `generate_concept_complete` then generates BOTH
   directions x all five doses x (15-prompt/1-repeat sweep AND
   20-prompt/3-repeat confirmation) for one concept at a time, never
   partially -- `assess_concept_generation_readiness` refuses to start a
   concept the remaining wall time cannot finish (`NOT_ATTEMPTED`, never a
   truncated partial result). Sweep and confirmation seeds are
   independently derived (`derive_seed`, salted by purpose) and explicitly
   checked disjoint (`assert_seed_sets_disjoint`) before the concept is
   considered done -- a shared seed would let a sweep generation double as
   a confirmation repeat, biasing the very estimate selection is based on.
   `build_suppress_dose_grid`/`build_amplify_dose_grid` enforce the
   five-point shape (Suppress: four descending clamp fractions + ABLATE as
   the fifth point; Amplify: five distinct clamp doses). This module NEVER
   imports `final_pairing_causal_judge` or `lodestar`, at module scope or
   inside any function (verified by a source-level AST scan in its own
   test suite) -- no judge call is reachable from inside the allocation,
   structurally, not just by convention.
   `write_generation_manifest` hashes every generated file. The immutable
   manifest bytes are hashed by the later binding/reference step; a manifest
   never claims a self-hash.

2. **Transfer.** Move the output directory off the cluster. Re-verify
   with `final_pairing_one_allocation_generation.verify_generation_
   manifest(manifest_path, files_root=<destination>)` -- any generated-file
   hash mismatch is a hard stop (`TransferVerificationFailed`), never a
   warning. Promotion separately recomputes the manifest reference digest.

3. **Local machine, networked: judge the sweep, select, commit.**
   `scripts/final_pairing/final_pairing_judge_cli.py judge-sweep` verifies
   the transfer manifest again, builds real `lodestar.models.Generation`
   objects from the sweep files only, runs a REAL Lodestar cost estimate
   BEFORE any call (persisted to disk), refuses to proceed if the
   predicted uncached cost exceeds `--budget-usd` (zero paid calls made in
   that case), and otherwise judges for real through Lodestar's
   content-addressed cache. A researcher applies the frozen discovery
   protocol's LOW/MEDIUM/HIGH dose-threshold rule
   (`final_pairing_concept_discovery.select_calibration_candidates`) to
   the judged sweep and runs `write-selection` to record and, critically,
   **COMMIT `selection_record.json` to git** -- this commit IS the stage
   boundary (`ADDITION_2_sealing_is_mechanical`), verified later by
   `assert_selection_precedes_confirmation`'s real `git merge-base
   --is-ancestor` check, never merely trusted.
4. **Judge confirmation at the three selected doses only.**
   `judge-confirmation` re-verifies the selection commit is a STRICT
   ancestor of the confirmation-judging commit, then reads ONLY the three
   selected doses' confirmation files (`assert_never_opens_unselected`
   refuses anything else) -- the two unselected doses' files are stamped
   `UNUSED_FOR_SELECTION_OR_CLAIM` and are never opened, judged, or
   spot-read, retained rather than deleted (their retention is itself the
   evidence that no post-hoc substitution occurred).
5. **Suppress spot-read, after selection, outside Tamia.** The mandatory
   10-output researcher spot-read (`final_pairing_causal_judge.build_
   spot_read_packet`/`resolve_spot_read_decision`, already built) happens
   only once selection is committed, at the selected strength only.

Example commands (local machine, after transfer):

```bash
python scripts/final_pairing/local_judge_preflight.py   # no paid call; verifies wiring before spending anything

python scripts/final_pairing/final_pairing_judge_cli.py judge-sweep \
  --manifest /path/to/generation_manifest_amplify.json --concept-id cheese --pairing-id gemma-3-12b-it \
  --direction amplify --judge-model claude-sonnet-4-5-20250929 --model-name google/gemma-3-12b-it \
  --budget-usd 25.00
  # --cache-path/--output-dir omitted: they default to INTERPLAB_CACHE_DIR/
  # INTERPLAB_OUTPUT_ROOT if set, else this repo's own gitignored ./.local/ --
  # no machine-specific path is assumed. Pass either flag explicitly to override.

python scripts/final_pairing/final_pairing_judge_cli.py write-selection \
  --concept-id cheese --pairing-id gemma-3-12b-it --direction amplify \
  --low-dose 1 --medium-dose 2 --high-dose 4 \
  --out selection_record.json --repo-root . --commit-message "select doses for cheese/amplify"

python scripts/final_pairing/final_pairing_judge_cli.py judge-confirmation \
  --manifest /path/to/generation_manifest_amplify_stamped.json --concept-id cheese --pairing-id gemma-3-12b-it \
  --direction amplify --judge-model claude-sonnet-4-5-20250929 --model-name google/gemma-3-12b-it \
  --budget-usd 25.00 --selection-record selection_record.json \
  --selection-commit <commit from write-selection> --confirmation-commit <commit after judging> --repo-root .
```

The generation manifest is written PER DIRECTION (never one manifest spanning both Amplify and Suppress -- a separate ruling from the Architect, since the two directions have separate prompt sets, grids, and selection records). Before `judge-confirmation` can run, the manifest passed to it must be the STAMPED copy (`final_pairing_one_allocation_generation.stamp_manifest_with_selection`), with `label="UNUSED_FOR_SELECTION_OR_CLAIM"` set on every unselected confirmation dose's entry -- the original, transfer-verified manifest is never mutated in place. `--selection-commit`/`--confirmation-commit` are filled in via `final_pairing_judge_cli.finalize_selection_ancestry` once the confirmation-judging commit actually exists (these two fields cannot be known at `write-selection` time, since a file cannot embed the hash of its own future commit).

Engineer 3's real `dose-check --manifest <stamped manifest> --selection-record <selection record>` command (commit ac9ea40) verifies the whole graph: seed disjointness, one file per dose, five doses per COMPLETE concept, the confirmation shape parsed from the protocol itself, the sealed stamp, and the git ancestry -- proven against a real manifest/selection-record pair this project's own test suite generates (see the closing report for the captured passing run).

There is no `--lodestar-source-root` CLI flag: the real Lodestar checkout is
inserted onto `sys.path` explicitly via `ensure_lodestar_importable`, which
requires the `LODESTAR_SOURCE_ROOT` environment variable (no fallback of any
kind -- a machine-specific default would only ever be right on the one
machine it was written for) or, for programmatic callers only, an explicit
`source_root=` argument; Lodestar is never installed into this repository's
own `.venv`. `ANTHROPIC_API_KEY` is read
from the environment only, never logged, printed, or accepted on the
command line. `MockJudge`/`NoOpJudge` model identities are refused by
name (`assert_judge_model_is_attestable`) from ever reaching a function
that persists a result as attested evidence, independent of and in
addition to Engineer 3's own `NOOP_JUDGE_MODELS` refusal.

## What remains genuinely undone (disclosed, not silently dropped)

1. **No cell of the grid, no generation, and no judged score in this
   packet has ever been produced against real GPU/model weights or a real
   Anthropic API call.** No Tamia allocation and no GPU were available in
   this environment. Every function above is real code, exercised against
   real frozen artifacts and real (CPU, tiny-tensor) fake backends -- the
   fake backends' own embedding rule is tuned to the unit-test suite's
   short fixture sentences, not the real, richer bilingual frozen prompt
   set, so an end-to-end grid run against them legitimately returns
   `status="fail"` rather than an organic pass (proven, and reported
   honestly, in the closing report for this pass rather than manufactured
   to look green).
2. **No real, paid Lodestar judgment has been made.** The judge CLI's
   real, zero-cost cost-estimation path IS exercised for real in this
   repository's test suite (against Lodestar's real cost arithmetic); the
   actual `AnthropicJudge` network call is exercised in tests only via an
   injected `judge_factory` returning Lodestar's own real `MockJudge` --
   proving the estimate/budget/cache/persistence machinery without
   spending money or requiring a credential, since there is no real
   Tamia-generated transfer manifest in this environment to judge yet.
3. **The official per-SAE `examples.safetensors` census** (activations/
   positions/seq_ids/tokens/feature_frequencies/logit_effects/top-bottom
   logits, shipped alongside each Gemma Scope 2 SAE directory) is still
   not read anywhere in this codebase -- no such file exists on any
   machine used in this investigation, so a parser for its exact tensor
   layout remains unverified against a real file. `rank_features_by_
   activation`/`corpus_max_per_feature` still do their own forward passes
   over the supplied prompt texts (correct, just not taking advantage of
   the cheaper official pre-filter).
4. **`--calibration-low/-medium/-high-threshold` (stage 6, in
   `value_in_max_units`) and the one-allocation protocol's LOW/MEDIUM/HIGH
   selection remain the SAME dose-threshold mechanism** (`select_
   calibration_candidates`), applied to judged sweep scores by researcher
   judgment rather than by a newly-invented judged-score-to-tier algorithm
   this packet does not find clearly specified anywhere -- a disclosed
   scoping decision, not a silent guess, per this project's own "flag
   ambiguity, don't invent" rule.
5. **This development machine's own `.venv` lacks two of Lodestar's
   dependencies** (`anthropic`, `aiosqlite`) by design -- per the explicit
   instruction not to install Lodestar's dependencies into `qwen-sae-
   interp`. `local_judge_preflight.py` correctly reports `setup_failure`
   (never a fabricated pass) for the two cases that need them on this
   specific machine; it is designed to run wherever Lodestar's full
   dependency set is installed, which this machine deliberately is not.
6. **Some of the Gemma local-loader addendum's required coverage is
   satisfied by REUSE of `final_pairing_targets.py`'s own pre-existing,
   extensively-tested suite** (wrong-revision-refused, symlink-escape-
   refused, sibling-prefix-refused) rather than new authorship in this
   pass -- named here explicitly rather than left ambiguous about which
   coverage is new.
