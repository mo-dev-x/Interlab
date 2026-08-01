# Ablation / necessity experiment — feature 9056 (cheese) on `rwu04lpb`

**Status:** researcher-approved packet, repository-preparation only. This is
still **not runnable**. No cluster execution, scheduler submission, registry
writes, or scientific-result generation are authorized from this packet alone.

Current execution gates:

1. R6/ED-36 local environment implementation and independent verification must
   be accepted before cluster execution.
2. R7 launcher propagation is accepted in isolation on
   `r7-launcher-propagation` but parked until R6 stabilizes; this packet must
   not imply launcher readiness in the active tree.
3. Stage 2 judging remains ED-19 / A12 gated because the locked environment has
   no live Lodestar runtime.

Author: Mohamed El Yazid — IID.

## 1. Objective

The existing steering result supports sufficiency for feature 9056. This packet
prepares the missing necessity half:

- **H1 (necessity):** on cheese-eliciting prompts, clamping feature 9056 to
  zero materially reduces cheese content relative to the unmodified baseline.
- **H2 (specificity):** the reduction is specific to 9056; clamping a
  matched-frequency control feature leaves cheese content essentially
  unchanged.

## 2. Artifact chain

The authoritative local chain is:

`cheese` A2 → battery-wide census A3 → characterize `rwu04lpb` A7 →
validate(A7, A3, `concept_id=cheese`, feature 9056, stub judge) → DRAFT A8 →
steer(A7, A8) → per-seed A9 → judge(A9) → A9′.

Important boundary rules:

- `cheese` is semantic-only battery content; it does not mention feature 90537.
- The matched-frequency control feature is selected by `steer`, not authored in
  A2.
- Stage 1 is A9 preparation only; Stage 2 A9′ evidence is separately approved
  after ED-19 / A12 readiness.

## 3. Prepared configs

- `configs/census/fineweb_subset_400m.yaml` mirrors the consumed 400M-token
  FineWeb lineage underlying A1 `88740b746361` and A3 `e71b243e2c0c`:
  full coverage, no concept-level narrowing, `local:data/concepts`,
  `matcher=regex`, `case_folding=true`, `boundary=word`.
- `configs/characterize/rwu04lpb.yaml` is the canonical A7 producer.
- `configs/validate/cheese_9056.yaml` is a DRAFT A8 precursor with zero A3/A7
  placeholders and the researcher-approved cheese marker words.
- `configs/steer/ablation_9056_seed{0,42,123}.yaml` are claim-mode seed
  siblings that differ semantically only by `sampling.seed` and
  `generations_dir`.

## 4. Prompts and controls

The steer packet preserves the approved 10 cheese-eliciting prompts and the 10
index-aligned researcher-authored neighbouring-domain control prompts. The
prompt sets are fixed; no prompt rewriting, reordering, or control derivation
is authorized here.

At `scales_in_max_units: [0.0]`, claim mode yields:

- `baseline`: no hook on cheese-eliciting prompts.
- `steered`: clamp feature 9056 to zero.
- `random_feature`: clamp a matched-frequency control feature to zero.
- `random_direction`: generated automatically but degenerate at scale 0.0.
- `prompt_baseline`: no hook on the neighbouring-domain control prompts.

## 5. Scheduling and environment homogeneity

The settled execution policy is Option B:

- **Stage 1a:** seed 0 only, after environment, launcher, A3/A7/A8, and
  preflight gates pass.
- **Stage 1b:** seeds 42 and 123 wait until ED-19 opens and Stage 2 judging is
  executable.
- Before Stage 1b, the bundle/install identity and Interlab git SHA must match
  seed 0's A10. If they do not, rerun seed 0 under the same environment before
  proceeding.

This keeps the three-seed packet prepared in-repo while preventing false
comparability across heterogeneous environments.

## 6. Stage 2 judging, QC, and SS9 criteria

Judging is a separate downstream job. The `judge` job consumes A9, blinds arm
identity, and emits immutable A9′.

Preparation-only continuation from seed 0 is structural and blinded only:

- complete A9 and A10 lineage;
- no malformed or truncated records;
- no runtime errors;
- all required rows present.

No semantic continuation decision is made from Stage 1a alone.

For claim-grade Stage 2 analysis:

- Average surviving judge repeats to one score per `(seed, prompt, arm)`.
- Record repeat count per row.
- Fewer than two repeats excludes and flags the row; no imputation.

Per-seed acceptance:

- **H1:** the 95% prompt-group bootstrap CI for `baseline - steered` must lie
  entirely above zero and either pooled Cohen's `d >= 0.5` or relative
  reduction `>= 50%`.
- **H2:** the 95% CI for `random_feature - steered` must lie entirely above
  zero, and the 95% CI for `baseline - random_feature` must stay within
  `±0.5` and overlap zero.
- A centered control CI wider than `±0.5` is `INCONCLUSIVE`.
- Every seed must pass independently; no averaging, cherry-picking, post-hoc
  margin changes, or seed substitution.

## 7. Current dependency state

The present repo-state blockers are mechanical, not scientific:

- R6/ED-36 local environment implementation and independent verification must
  be accepted before cluster execution.
- R7 launcher fixes are accepted in the parked worktree
  `D:\qwen-sae-interp-r7-launchers` and must be integrated only after R6
  stabilization.
- ED-19 / A12 still block live Lodestar Stage 2 judging.

Until those gates open, this packet remains a prepared local chain only:
`A2 → A3 → A7 → A8 → A9` is specified, but none of the production steps are
authorized to run from this change set.
