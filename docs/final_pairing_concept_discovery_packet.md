# Final-pairing shared-concept discovery and calibration -- Tamia command packet

Scope: discovers CANDIDATE features for a researcher-supplied concept on
the two ratified final pairings, validates them held-out, runs causal
intervention and dose-response, and proposes Low/Medium/High calibration
candidates. This is statistical/mechanical evidence for later scientific
and behavioral judgment -- it invents no concept labels and no scientific
thresholds (every threshold below is a required CLI argument with no code
default; see "Unresolved protocol fields" at the end of this document).

Built on `final-pairing-harness` (successor to `b6d598b`). Three new
scripts, none of which modify `final_pairing_harness.py`,
`final_pairing_targets.py`, or anything under `interplab/` (the accepted
mechanical-acceptance harness and Engineer 3's sealing pipeline,
respectively -- both untouched):

- `scripts/legacy/final_pairing_concept_discovery.py` -- the per-pairing
  discovery/calibration runner (7 stages).
- `scripts/legacy/final_concept_discovery_dual_gpu_job.py` -- concurrent
  Gemma+Qwen orchestration inside one Slurm allocation, one node, 4xH100
  (Gemma on physical GPU 0, Qwen on physical GPU 1, GPUs 2-3 reserved for a
  separately authored judge process).
- `scripts/legacy/final_concept_discovery_matched_configuration_job.py` --
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
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_concept_discovery.py \
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
HF_HUB_OFFLINE=1 python scripts/legacy/final_pairing_concept_discovery.py \
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
deduplicate across concepts. **This function is NOT yet wired into `run()`'s
own automatic 7-stage pipeline** -- see "Not yet implemented" below.

## `--judge-config`

Optional. No real judge is implemented or invoked anywhere in this tool --
`--judge-config` only records WHICH judge identity a later stage should
use (`{"model": "...", "rubric_version": "...", "prompt_version": "..."}`);
omitting it records the same honest `{"model": "none", ...}` identity
`interplab.characterization.indexer.NoOpJudge` uses. This tool never
invents a concept label or a judged score.

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
python scripts/legacy/final_concept_discovery_dual_gpu_job.py \
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
python scripts/legacy/final_concept_discovery_matched_configuration_job.py \
  --primary-gemma-config /path/to/primary_gemma_lane.json \
  --primary-qwen-config /path/to/primary_qwen_lane.json \
  --backup-gemma-config /path/to/backup_gemma_lane.json \
  --backup-qwen-config /path/to/backup_qwen_lane.json \
  --trigger-inputs-json /path/to/trigger_inputs.json \
  --run-backup false \
  --job-result-path results/final_pairing/concept_discovery/matched_job_result.json
```

**CORRECTION: the backup trigger's Boolean rule is not unknown.** An
earlier version of this packet said it had "not yet [been] returned" --
it is frozen at `protocols/final_pairing/v1/backup_trigger.json` (commit
`125b1d3`): `RUN_BACKUP = primary_complete AND (primary_shared_gabc_count
< 3)`, `FAIL_RUN = NOT primary_complete`, threshold 3 fixed and not
changeable after any activation is computed. `final_pairing_concept_
discovery.evaluate_backup_trigger(primary_complete=..., primary_shared_
gabc_count=...)` implements exactly this formula and is unit-tested
against it.

**`--run-backup` is still not COMPUTED by this tool**, for a narrower
reason than before: the formula's own INPUT, `primary_shared_gabc_count`,
is defined as "the number of concepts where the SAME feature passes G-A,
G-B, AND G-C on BOTH pairings within the primary configuration" -- a full
14-concept x 2-pairing x 3-gate x 3-family x 2-locale grid with a
per-feature conjunction across gates. No script in this repository
assembles that grid yet: `final_pairing_concept_discovery.py` discovers
one concept per invocation, and G-C (AUROC vs. `near_miss`) has no
implementation at all (only G-A/G-B, via `compute_gate_a_and_b_per_family`).
Until that aggregation exists, whoever assembles it should call
`evaluate_backup_trigger` and pass its `.run_backup` result to
`--run-backup` here, rather than re-deriving the formula by hand.
`--trigger-inputs-json` is still loaded and persisted verbatim into the
output -- never interpreted or used to compute the boolean here, since
this file still isn't where that grid gets assembled.

Separately, the frozen file also requires a **depth-matching assertion**
before either configuration's activations are computed: Gemma's
`depth_fraction` (`layer / n_layers`, computed from the ACTUALLY LOADED
model, never assumed) must be within 0.02 of the matched Qwen
`depth_fraction` (`PRIMARY_CONFIGURATION.qwen_depth_fraction == 0.59375`,
`BACKUP_CONFIGURATION.qwen_depth_fraction == 0.5`) --
`assert_gemma_qwen_depth_matches(gemma_layer=..., gemma_n_layers=...,
qwen_depth_fraction=...)` implements and raises closed on this; it is not
yet called from `load_backend`/`load_gemma_scientific_target` (another
real, disclosed gap -- see "Not yet implemented").

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

```bash
# From the qwen-sae-interp repo root, on final-pairing-harness, at the
# exact successor commit (see the closing report for its hash):
git rev-parse --abbrev-ref HEAD   # confirm: final-pairing-harness
git remote get-url origin         # confirm: this IS qwen-sae-interp, not sae-concept-lab
COMMIT=$(git rev-parse HEAD)
git archive --format=tar.gz --output="final_concept_discovery_${COMMIT}.tar.gz" "${COMMIT}"
sha256sum "final_concept_discovery_${COMMIT}.tar.gz" > "final_concept_discovery_${COMMIT}.tar.gz.sha256"
```

`git archive` at a fixed commit is deterministic for a given git version --
the archive's own identity is exactly `${COMMIT}`, independently
recomputable by anyone who clones qwen-sae-interp and runs the same command
against the same commit; the `.sha256` sidecar is the chain-of-custody hash
for whatever copy is actually transferred to Tamia (the same convention
`results/final_pairing/job_407008/chain_of_custody.json` already
established for the mechanical-acceptance evidence). Verify on the
receiving end with `sha256sum -c final_concept_discovery_${COMMIT}.tar.gz.sha256`
before staging or running anything from the extracted tree.

## Not yet implemented (explicitly deferred, not silently dropped)

Given the volume of requirements accumulated across this dispatch and its
addenda, the following were deliberately NOT attempted this pass, each for
a stated reason -- not oversight:

1. **The official per-SAE `examples.safetensors` census** (activations/
   positions/seq_ids/tokens/feature_frequencies/logit_effects/top-bottom
   logits, shipped alongside each Gemma Scope 2 SAE directory) is not read
   anywhere in this codebase. No such file exists on any machine used in
   this investigation, so a parser for its exact tensor layout would be
   unverified against a real file -- writing one blind risks silently
   wrong code that looks complete. `rank_features_by_activation`/
   `corpus_max_per_feature` still do their own forward passes over the
   supplied prompt texts; this is correct but does not yet take advantage
   of the cheaper official pre-filter (dead/ultra-high-frequency exclusion,
   reduced forward-pass volume) the LA-C addendum describes. G-A/B/C still
   run on the frozen researcher-authored prompts regardless, per that same
   addendum -- this gap is a missed optimization, not a correctness gap.
2. **The dual-GPU orchestrator does not yet implement the staggered
   cold-load READY-handshake** (start Qwen on GPU 1, wait for an atomic
   READY record from its own model+SAE load, only then start Gemma on
   GPU 0, then let both scientific stages proceed concurrently). It still
   launches both lanes together via `launch_all()`. `final_pairing_
   concept_discovery.py`'s own `run()` does not yet emit any READY record
   at all. This is a real, load-bearing sequencing gap if simultaneous
   12B+27B cold loads turn out to contend for host RAM/PCIe bandwidth on a
   real node -- flagged here rather than shipped as an untested guess at
   the handshake protocol's exact shape (timeout value, READY record
   schema, which stage boundary counts as "loaded").
3. **`compute_gate_a_and_b_per_family` is implemented and tested (including
   against the real frozen artifact) but not yet wired into `run()`'s
   automatic pipeline.** `run()` still uses the earlier, simpler generic
   train/holdout AUC design (`validate_specificity`) against whatever
   `--prompt-set-path` supplies. Consuming `FrozenPromptArtifact` directly
   inside `run()`'s stage 1/2 (so a single CLI invocation does ranking +
   G-A/G-B against the real per-family/per-split structure end-to-end) is
   the natural next step, not done here to avoid a same-day rewrite of an
   already-tested pipeline under this level of time pressure.
4. **G-C (specificity vs. near_miss), G-D (Amplify, heldout_neutral
   substrate), and G-E (Suppress, heldout_eliciting substrate) are not
   implemented at all.** All three need judged relevance/coherence deltas
   from a real generation + a real Lodestar-backed judge (`ci_method: "SS9
   prompt-group bootstrap"` in `metadata.json["thresholds"]` names the
   statistical machinery, `interplab.stats.stats.bootstrap_ci`/
   `seed_variance`, but no real judge exists anywhere in this codebase --
   see "no invented concept labels/judges" throughout). `--judge-config`
   still only records an identity; nothing calls it.

## Unresolved protocol fields (still required from the Architect)

Ranked by how much they block a real run:

1. **RESOLVED, corrected from an earlier version of this packet: the
   backup trigger's Boolean rule is frozen** at `protocols/final_pairing/
   v1/backup_trigger.json` (commit `125b1d3`), found and wired in
   (`evaluate_backup_trigger`, `assert_gemma_qwen_depth_matches`) after
   this packet had already stated the opposite. What is still genuinely
   missing is not the rule but its INPUT: no script in this repository
   assembles the full 14-concept grid (`primary_complete`,
   `primary_shared_gabc_count`) the formula reads, and G-C has no
   implementation at all yet (see "Not yet implemented" above). This is
   the actual remaining blocker for computing `--run-backup` automatically
   -- not an unknown rule.
   (My own exhaustive-repo-search claim in an earlier draft of this packet
   -- that no such rule existed anywhere under any name -- was itself
   wrong: `protocols/` was committed to this exact branch before that
   search ran, in a directory I never checked. Recorded here rather than
   silently amended, since the same failure mode -- assuming absence from
   a search that didn't cover every directory -- is worth remembering,
   not just fixing.)
2. **UPDATE: `metadata.json["thresholds"]` now DEFINES `G_A_separation_
   auroc_min` (0.9), `G_B_activation_floor_fraction_of_observed_max` (0.2),
   and `G_B_fire_rate_min` (0.7)** -- these are no longer missing for G-A/
   G-B, and `compute_gate_a_and_b_per_family` reads them by default. What
   remains unresolved: `--specificity-auc-threshold` (this runner's own,
   SEPARATE, generic stage-2 gate, used by `run()`'s automatic pipeline,
   which is not yet the same computation as G-A/G-B -- see "Not yet
   implemented" item 3 above) still has no Architect-given value of its
   own, and `second_target_relevance_gain_min: 1.0` in the same thresholds
   block may or may not be the intended value for `--bundle-materiality-
   threshold` (stage 4's greedy-composition gate) -- the name suggests it
   is, but nothing confirms that mapping is exactly right rather than
   coincidentally similar.
3. **`G_D_amplify_relevance_delta_min` (3.0) / `G_E_suppress_relevance_
   delta_max` (-3.0) / `G_D_coherence_median_min` / `G_E_coherence_median_
   min` (both 6.0) exist in `metadata.json` but cannot be used yet** --
   they gate JUDGED relevance/coherence deltas, and no real judge exists
   anywhere in this codebase (see "Not yet implemented" item 4). This
   packet's `--calibration-low/-medium/-high-threshold` (stage 6, in
   `value_in_max_units`) remain a distinct, simpler mechanism with no
   Architect-given value -- whether Low/Medium/High should instead be
   DERIVED from G-D/G-E's judged thresholds once a real judge exists,
   rather than being a separate dose-unit boundary, is itself an open
   design question this packet does not resolve.
4. **Whether `value_in_max_units` (multiples of the background-corpus max
   activation) is the correct unit convention for the Architect's
   Low/Medium/High tiers**, or whether a different unit (e.g. an absolute
   activation value, or a percentile) was intended -- this tool adopted
   `value_in_max_units` because it is the ONLY dose-unit convention already
   established anywhere in this codebase (`interplab.interventions.spec.
   InterventionSpec.value_in_max_units`); no calibration-tier unit is
   defined anywhere else to compare against.
5. **Whether `resid_post/layer_<L>_width_16k_l0_medium` is really the
   correct Gemma-Scope-2 registry naming for layers 29 and 24** (verified
   present in the installed `sae_lens` registry for layer 31 only, per the
   already-accepted mechanical target) -- Lab Assistant B's own
   verification against the real release metadata, requested in the
   ratified scientific SAE decision for Qwen, has an exact Gemma analog
   this packet assumes but cannot independently confirm without network/
   Tamia access.
7. **A real judge implementation.** `--judge-config` only records an
   identity; no code path anywhere in this tool actually scores or labels
   anything. Wiring a real Lodestar-backed judge is out of scope here, per
   this dispatch's own "do not invent concept labels" instruction.
