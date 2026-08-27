# Current Plan

## 2026-08-04 R9 dependency-ordered repair plan (reconciled to repository)

| Order | Work item | Owner | Status | Gate |
|---|---|---|---|---|
| 1 | R9-V5-ED36-BUILDER-FINAL-ACCEPTANCE | Auditor 2 | **Accepted 2026-08-04** | Exact `82b028e`, seven governing hashes in `VERIFICATION_LOG.md`. |
| 2 | R9-DOC1-V3-VERDICT-RECOVERY | Orchestrator | **Complete 2026-08-04** | F1–F4 and the V3 REJECT transcribed from the Auditor's record. |
| 1b | R9-C6-ED36-ATTEMPT-SHAPE-HARDENING | Engineer 2 | **Active** | Exact-key checks on both connection attempts + two negative tests + parenthesise `:4266`. Same seven paths. |
| 1c | R9-V6-ED36-HARDENING-DELTA-AUDIT | Auditor 2 | **Blocked on 1b** | Bounded delta audit only; `82b028e` acceptance is not reopened. |
| 3 | R11-D1A-JUDGE-TEMPERATURE-SUFFICIENCY-PROVENANCE | Human / Researcher | **Accepted 2026-08-04** | All four ratified as recommended. Verbatim rationale in `VERIFICATION_LOG.md`. |
| 4 | R11-C00-TEMP0-RELIABILITY-PROSE-CORRECTION | Engineer 1 | **Active (parallel)** | Thirteen verified sites, four permitted files. Prose/evidence only. |
| 4b | R11-V1-PROSE-CORRECTION-ACCEPTANCE | Auditor 1 | **Blocked on 4** | Hash-bound audit of untracked working files; no commit SHA exists for this lane. |
| 4c | R12-D1-A005-REPORT-TRACKING-POLICY | Human / Researcher | **Closed 2026-08-04** | Tiered split by file type. Tier 1 tracked now; binaries deferred to release audit. |
| 4d | R12-C1-A005-TRACK-REPORT-DELIVERABLES | Engineer 1 | **Blocked on 4b (R11-V1)** | Serialized behind the prose correction — same file scope, and the ignore change would break R11-V1's status criterion. Runs in the main worktree after ff to `9d90ef6`. |
| 4e | R12-V1-TRACKING-ACCEPTANCE | Auditor 1 | **Blocked on 4d** | Pattern proof, staged manifest, secret scan. |
| 4f | R12-X1-PUBLISH-TRACKED-DELIVERABLES | Human authorization | **Blocked on 4e** | First external disclosure of `reports/`/`results/` content. |
| 5 | R9-I1-BUILDER-ONTO-PUBLISHED-MAIN | Engineer 2 | **Blocked on 1** | Rebase/cherry-pick accepted R9 tip from `4bf0fd8` onto published `9d90ef6`; overlays are path-disjoint. |
| 6 | R9-X3-PUBLISH-ACCEPTED-BUILDER | Human authorization | **Blocked on 5** | Fast-forward `origin/main` only after independent acceptance of the integrated revision. |
| 7 | R9-C5-REAL-DERIVED-WHEEL-RUNTIME-EXPORT | Engineer 2 | **Deferred** | Only after a real authorized wheel exists. |

Collision boundaries: Auditor 2 works read-only in a **new** detached worktree;
branch `r9-ed36-bundle-builder` and `D:\qwen-sae-interp-r9-repair` must not be
mutated while lane 1 runs. Lane 3/4 touch report prose only and are disjoint from
the seven R9 paths.

## 2026-08-03 R9-C4 host isolation preflight recovery

| Work item | Status | Evidence | Consequence |
|---|---|---|---|
| R9-C4-ED36-BUILDER-FINAL-CORRECTION | **Active — Engineer 2 resume** | Native Windows/WSL CLI failed, but an escalated read-only probe confirmed Docker Desktop 4.48.0 is running a Linux 6.18.33.2 WSL2 kernel and already retains `python:3.11-slim-bookworm` locally. | Use an offline `--network none` Linux container for real namespace-positive implementation evidence; no download or Tamia access is needed. |

## 2026-08-03 R9-D4 approved

| Work item | Status | Evidence | Consequence |
|---|---|---|---|
| R9-D4-DERIVED-RECORD-SCHEMA-SCOPE-RATIFICATION | **Accepted** | Program Manager independently confirmed the strict nine-field `derived_wheel` definition cannot encode the seven R9-A3 provenance categories and authorized the acquisition-manifest schema as path seven. | R9-C4 may proceed in exactly seven cumulative paths; no eighth path. |
| R9-C4-ED36-BUILDER-FINAL-CORRECTION | **Active/ready — Engineer 2** | Option 2, derived hash authority, fail-closed namespace isolation, schema v1 clarification, and the entire R9-V2 correction matrix are binding. | Produce a clean immutable successor to `490ae73e...` for R9-V3. |
| R9-V3-ED36-BUILDER-REACCEPTANCE | **Blocked/ready — Auditor 2** | Await exact R9-C4 SHA; audit must not run from stale `c6ef2df`. | Fresh exact-SHA audit plus real positive Linux isolation evidence gates acceptance. |
| R9-C5-REAL-DERIVED-WHEEL-RUNTIME-EXPORT | **Deferred/planned** | A real derived wheel will require `slurm/requirements.cluster.txt` to replace the sdist reference with its wheel filename/hash, but no wheel exists and construction is unauthorized. | Request separate scope only after an accepted builder and authorized real construction; do not touch the export in R9-C4. |

## 2026-08-03 R9-A3 derived-build ruling and schema scope gate

| Work item | Status | Evidence | Consequence |
|---|---|---|---|
| R9-A3-DERIVED-BUILD-REQUIREMENT-SEMANTICS | **Complete** | Both Architects select Option 2: PEP 508 declarations constrain compatibility while the exact tooling lock selects executable bytes; derived-wheel authority comes only from an export-authorized sdist plus a validated derived record; Linux kernel network isolation is mandatory and fail-closed. | No further architecture cycle is needed. |
| R9-D4-DERIVED-RECORD-SCHEMA-SCOPE-RATIFICATION | **Active — Human/Program Manager** | At exact candidate `490ae73e`, `$defs.derived_wheel` is strict (`additionalProperties: false`) and cannot encode extraction, requirement mapping, backend origin, complete build environment, or network-namespace evidence. | Ratify exactly one seventh path: `schemas/environment_acquisition_manifest/v1.schema.json`. |
| R9-C4-ED36-BUILDER-FINAL-CORRECTION | **Blocked/ready — Engineer 2** | The implementation contract is fully specified; only the seven-path scope authority is missing. | After R9-D4, correct every R9-V2 defect and produce a new immutable successor. |
| R9-V3-ED36-BUILDER-REACCEPTANCE | **Blocked — Auditor 2** | Requires the stable R9-C4 successor and real positive Linux namespace evidence. | Acceptance still gates target capture, bundle/environment construction, equivalence, and experiments. |

Last updated: 2026-08-02

## Routing state

`R6-V5A-ED36-REMAINDER-ACCEPTANCE` returned **Needs correction**. The exact
Alliance torch group, lifecycle/preservation suites, frozen export, lock,
lint, Bash syntax, and diff checks passed, but seven ED-36 tests are not green.
Exact-byte execution after verification remains separately `UNVERIFIED`.

Confirmed passing:

- dependency/export/version/hash/marker invariants;
- isolated bootstrap and zero-mutation preflight failures;
- ordinary creator validation, rollback, sentinel preservation;
- runtime/tooling overlap, module-family and CUDA live-runtime comparison;
- 24/24 lifecycle cases;
- authoritative R5-X2 config/report matrices and missing-equivalence A10;
- lock, exact CI Ruff, Bash syntax, diff checks, A10 v1 and interfaces.

R6-C6 claims these two root-of-trust corrections:

1. creator wheel bytes can be replaced after validation but before execution;
2. torch acquisition/admission accepts any local build sharing public version
   2.13.0 and does not require the retained artifact file/hash.

The remaining seven failures are bounded test defects: two tests demand a later
diagnostic although validation correctly rejects an earlier malformed
condition, and five install-record fixtures omit the required creator wheel.
Three torch-specific cases—wrong filename, wrong recorded size, and an
out-of-bundle torch path—also lack explicit coverage.

`R6-A006` is accepted without an ED amendment. C7 produced a green 714-test
candidate, but Orchestrator source review found a forbidden production
environment test seam and a wrapped rather than unmodified subprocess boundary.
R6-V5C accepted reproducible local revision `c6ef2df`. R8-I1 integrates the
accepted parked R7 launcher commit in a new isolated worktree while Auditor 1
has accepted T1.2-V1. R8-I2 now integrates the accepted packet in a second clean
branch in parallel. External ED-36 installation/equivalence, fifth certification,
and experiment execution remain blocked.

## Role routing

Allowed next roles are `ENGINEER`, `AUDITOR`, `ARCHITECT`, `LAB_ASSISTANT`,
`HUMAN / RESEARCHER`, `ORCHESTRATOR`, and `COMPLETE`. Scientific procedure
selection and interpretation belong to the Researcher; fully specified TamIA
execution and evidence acquisition belong to the Lab Assistant. Role ownership
does not remove dependency or human-approval gates.

# Engineer-Complete Candidate: R6-C6-ED36-IMMUTABLE-CREATOR-TORCH-ANCHOR

## Technical assessment

R6-V4 proved a creator time-of-check/time-of-use defect: approved wheel hash
`c95d0018…c38fb` was validated, the path was replaced with bytes hashing
`6096be3a…e9fec`, and substituted code created a postcondition-valid venv.
The function returned success while reporting the original hash.

It also proved that mutually consistent acquisition/install/live evidence for
unauthorized `torch==2.13.0+cu121`, CUDA 13.2, arbitrary hash, and no artifact
file passes. Public-version equality alone is not the ED-36 Alliance artifact
contract.

## Hidden consequences

- Postcondition-valid output does not prove which creator bytes executed.
- Reporting a validated hash while executing substituted bytes makes the
  environment provenance false.
- Any torch local build can currently impersonate the sanctioned Alliance
  build if it shares public version 2.13.0.
- Admission without the retained file cannot replay artifact identity or
  support downstream retention guarantees.
- Fixture failures can hide regressions by aborting before the assertion under
  test.

## Classification

Implementation defects. ED-36 already requires immutable selected files and
the exact Alliance torch artifact; no Architect action is needed.

## Work-order scope

Close only creator TOCTOU, exact Alliance torch artifact admission, and the
seven fixture regressions.

Required outcomes:

1. execute only bytes derived from the exact hash/metadata-validated creator
   snapshot; replacing the original path after validation must either have no
   effect or fail before execution;
2. the creator hash reported in the result must be the hash of the bytes
   actually executed;
3. preserve transactional staging, functional postconditions, rollback, and
   sentinel safety;
4. require acquisition torch identity to be the sanctioned local version
   `2.13.0+computecanada`, with public version 2.13.0;
5. require the retained torch artifact file to exist and replay filename,
   size, SHA-256, wheel metadata Name/Version, and approved origin at build
   and cert-lane admission;
6. require install and live torch distribution versions to match that exact
   acquisition identity, with measured CUDA 13.2 and availability true;
7. reject `+cu121`, missing files, arbitrary hashes, altered bytes, wrong
   metadata/origin/version, CPU runtime, and CUDA mismatch;
8. repair legacy ED-36 test fixtures so every intended installed-extra,
   version, CUDA, and dirty-source assertion reaches its target rather than
   failing early at creator lookup.

## Required evidence

- Deterministic after-validation path-swap attack and proof substituted code
  cannot execute.
- Actual-executed-hash assertion and valid creator path.
- Alliance torch valid fixture plus unauthorized-local-version, missing-file,
  arbitrary-hash, altered-file, metadata/origin/version, CPU, and CUDA attacks.
- All seven formerly failing tests reach their intended assertions.
- Preserved creator rollback, lifecycle, R5-X2, overlap, module, schema, and
  local behavior.
- Focused/full suites, export reproduction, lock, exact CI Ruff, Bash syntax,
  and diff check.
- No external or production state mutation.

## Engineer report status

Implementation is reported complete. Direct creator path-swap and exact torch
admission probes passed; `py_compile`, exact CI Ruff, lock, and diff checks
passed. Pytest and Bash syntax remain independently unverified because of host
environment failures.

# Returned Audit: R6-V5A-ED36-REMAINDER-ACCEPTANCE

## Technical assessment

R6-C6 modifies provenance roots of trust and its normal pytest evidence did not
complete on the Engineer host. The Auditor can independently inspect the
implementation, run every already-existing ED-36 and preservation test, and
verify the exact Alliance torch admission boundary without creating any new
race/substitution procedure.

Exact-byte execution after verification remains a separate unverified boundary
until a deterministic repository regression is approved, implemented, and
then run unchanged by the Auditor.

## Hidden consequences

- The exact-byte execution invariant cannot be inferred from source inspection
  or from tests that replace only the original creator path.
- The remainder audit can still discover independent creator, torch, lifecycle,
  schema, dependency, or regression defects.
- Weak file, origin, path, or manifest linkage could allow a self-consistent
  unauthorized torch build to impersonate the Alliance artifact.
- Fixture setup failures can hide regressions by never reaching their stated
  installed-extra, version, CUDA, or dirty-source assertions.
- Lifecycle regressions could bypass the exactly-one-A10 contracts and make
  production failures unauditable.

## Classification

Verification gap after an implementation correction. The missing deterministic
boundary-test design is separated as A-006 for Architect approval.

## Work-order scope

Inspect `interplab/core/environment_bundle.py`, the existing ED-36 tests and
helpers, and existing preservation suites. Run existing tests unchanged. Do
not design, add, modify, or execute a new synchronized execution-snapshot
boundary test. If a named pre-existing regression already asserts exact-byte
execution after verification, it may be run unchanged and reported.

Return `Accepted for audited remainder` or `Needs correction`. In either case,
record the exact-byte boundary as `UNVERIFIED` unless an unchanged pre-existing
test directly establishes it. Do not infer overall R6 acceptance.

## Required evidence

- Confirm no interface, schema, A10-v1, dependency-version, or frozen-export
  drift.
- Inspect existing tests for a named exact-byte execution regression. Run it
  unchanged if present; otherwise classify this boundary `UNVERIFIED`.
- Recheck successful creation, partial-target rollback, sentinel safety,
  snapshot cleanup, creator metadata, and failure cleanup.
- Admit the exact retained Alliance torch fixture; use repository-local
  negative fixtures to confirm rejection of missing/changed files, arbitrary
  hashes, filename/size/METADATA/origin changes, invalid out-of-bundle paths,
  `+cu121`, inconsistent acquisition/install/live versions, CPU runtime,
  false availability, and CUDA mismatch, including internally consistent but
  unauthorized fixture data.
- Confirm all seven former failures reach their intended assertions.
- Re-run export/marker invariants, bootstrap pre-mutation checks,
  schema/manual parity, installed closure, module/overlap behavior, the 24-case
  four-job lifecycle matrix, and authoritative R5-X2 mutation/missing-evidence
  cases.
- Run focused ED-36 tests, preservation suites, full pytest, exact CI Ruff,
  `uv lock --check`, Bash syntax, and `git diff --check`. Report commands and
  outcomes. Retain no probe artifacts and modify no repository or external
  state.

## Audit result

**Needs correction.** Focused ED-36: 61 passed/7 failed; full suite: 702
passed/7 failed/3 deselected. Exact torch: 20 passed. Creator: 10 passed/1
failed. Lifecycle/preservation/schema/import/bootstrap: 93 passed; the 24-case
lifecycle matrix passed. Ruff, lock (196 packages), Git Bash syntax, and diff
checks passed. No interface, schema, A10, registry, config, or production drift
was found, and no audit state was retained.

# Architect Decision: R6-A006-EXACT-BYTE-EXECUTION-TEST-CONTRACT

## Technical assessment

**Accepted; no ED amendment.** The child currently reads the snapshot once to
verify its hash and then zipimport reads the same mutable path again to execute
it. The Architect therefore found a real production defect, not merely missing
coverage.

## Hidden consequences

- Verification and execution must derive from one in-memory byte buffer, or a
  child-private extraction of that verified buffer; the parent-visible snapshot
  must not be reread for import.
- After the child returns and before created-venv validation, the parent must
  re-hash the snapshot. Mismatch reports expected/actual hashes and rolls back.
- No production synchronization hook, environment gate, sleep, thread race,
  permission trick, or platform-specific path behavior is permitted.
- The return mapping, schemas, manifest semantics, dependencies, lock,
  blueprint, and registry are unchanged.

## Classification

Implementation defect plus verification gap. The ambiguity is resolved and
ED-36 already requires this behavior.

## Work-order scope

Allowed files are `interplab/core/environment_bundle.py`—only
`create_virtualenv`, its child source string, and private helpers—and
`tests/test_environment_bundle.py`. The named real-subprocess regression is
`test_create_virtualenv_executes_only_verified_creator_bytes_and_aborts_on_post_verification_replacement`.

## Required evidence

- The approved creator records token A and replaces the snapshot from inside its
  real `__main__`; the substitute's token B must never execute.
- Snapshot mismatch raises with exact expected/actual hashes before created-venv
  validation; target, staging, and snapshot are removed while an unrelated
  sentinel is preserved.
- The named test fails against the pre-fix implementation and passes afterward
  on platform-neutral disposable `tmp_path` data.

# Returned Work Item: R6-C7-ED36-FINAL-LOCAL-CLOSURE

## Technical assessment

C7 implements the single-buffer child-private wheel and ordered parent re-hash,
repairs the V5A fixtures, adds torch coverage, and reports 714 passed/3
deselected. It is not accepted because the implementation sets
`INTERPLAB_CREATOR_SNAPSHOT_PATH` in the production child solely for the test,
while the named regression replaces `bundle.subprocess.run` with a delegating
wrapper. Both contradict the A-006 contract.

## Hidden consequences

- A production environment seam exposes internal snapshot location and makes
  test coordination part of the security-critical path.
- A delegating monkeypatch does run the real child, but it does not satisfy the
  explicit requirement that the production subprocess function be left intact.
- The pre-fix named test failed via `SyntaxError`; it did not independently
  demonstrate the intended historical substitution outcome.

## Classification

Needs correction: implementation/test-contract defect. The Architect decision
itself remains clear and no new ambiguity exists.

## Work-order scope

Preserve C7 pending the bounded C8 correction below.

## Required evidence

- Engineer evidence: named post-fix test passed; focused ED-36 53 passed;
  creator 12; torch 20; environment-bundle file 73; full suite 714 passed/3
  deselected. Ruff, lock, Git Bash syntax, and scoped format checks passed.

# Engineer-Complete Work Item: R6-C8-ED36-REMOVE-CREATOR-TEST-SEAM

## Technical assessment

The test creator already receives the staging target as `sys.argv[2]` after the
child resets argv and knows its fixed wheel filename. It can reconstruct the
visible snapshot as `target.parent / (target.name + "." + filename)`.
Therefore neither a production environment variable nor a subprocess wrapper
is necessary.

## Hidden consequences

- Preserve the verified-buffer/private-copy execution and parent re-hash order.
- Removing only the environment assignment without changing the fake creator
  would make the test mutate the private import path instead of the visible
  snapshot and cease to prove the parent check.
- Because mismatch aborts before created-venv validation, the test needs no
  simulated second subprocess.

## Classification

Implementation/test-contract correction.

## Work-order scope

In `interplab/core/environment_bundle.py`, remove only the production
`INTERPLAB_CREATOR_SNAPSHOT_PATH` assignment and now-unused import. In
`tests/test_environment_bundle.py`, reconstruct the visible snapshot from the
staging target and known wheel filename, remove the `bundle.subprocess.run`
wrapper/capture, invoke the real child normally, and assert no staging/snapshot
path with the deterministic prefix remains.

## Required evidence

- Repository search finds no `INTERPLAB_CREATOR_SNAPSHOT_PATH`.
- The named test invokes unmodified `bundle.subprocess.run` and still proves A
  executes, B does not, exact mismatch hashes, rollback, prefix cleanup, and
  unrelated-sentinel preservation.
- Full C7 focused groups and 714-test hard suite remain green; return mapping,
  schemas, manifests, dependencies, lock, blueprint, registry, and other
  worktrees remain unchanged.

## Engineer result

The production environment seam and test subprocess wrapper are removed. The
named test uses the real child path and passed with A-only execution, exact
mismatch hashes, rollback, prefix cleanup, and unrelated-sentinel preservation.
Environment-bundle tests passed 73/73; the full suite passed 714/3 deselected;
Ruff, lock, Git Bash syntax, and diff checks passed.

# Accepted Candidate Audit: R6-V5B-ED36-FINAL-LOCAL-VERIFICATION

## Technical assessment

The final trust-boundary behavior and accumulated V5A fixture repairs now have
complete Engineer evidence. They require independent execution and source
inspection. The candidate remains a large dirty tree and the two core files are
untracked, so this audit establishes byte-specific candidate correctness only;
it cannot establish a reproducible release revision.

## Hidden consequences

- Auditor mutation would invalidate the candidate hashes and independence.
- Passing tests do not substitute for confirming the child has one visible-path
  read, private execution derived from verified bytes, ordered parent re-hash,
  and no production coordination seam.
- An accepted V5B must be followed by a separately bounded stabilization commit
  and exact commit-identity verification before R6 is globally accepted.

## Classification

Independent verification gap; subsequent revision-stabilization gap.

## Work-order scope

Inspect the two named implementation/test files and existing preservation
suites without modification. Record their byte hashes and complete repository
status before and after. Run the already-existing named test unchanged, then
the combined ED-36 and hard-suite evidence.

## Required evidence

- Source/no-seam inspection and unchanged execution of the named regression.
- The seven V5A repairs reach intended assertions; explicit torch filename,
  size, and out-of-bundle-path cases execute.
- Environment-bundle, lifecycle, schema/import/bootstrap, full suite, exact
  Ruff, lock, Git Bash syntax, and diff checks.
- Before/after hashes and status identical; no retained audit state.
- Verdict: **Accepted for exact local candidate**. Named 1, environment 73,
  creator 12, torch 23, repaired V5A 7, lifecycle 24, full suite 714 passed/3
  deselected. Static checks passed and start/end identities matched.

## Conflicting-audit reconciliation

Auditor 1’s report is inapplicable to the final candidate: it reports the exact
old seven-failure V5A pattern, cites the obsolete A006→C7 chain, and supplies no
file identity. Auditor 2 binds its result to hashes
`740dd61164d63e202ffce426d80941a77ae56ab8dbaebeb53588e86211201f7a`
and `7bbc115271d11343bf821b2bd1435637a1a390e9400aedb9ea278eb1ef7bd21b`;
the Orchestrator independently confirmed the current files have those exact
hashes/sizes and the same 34-modified/16-untracked status.

# Engineer-Complete Work Item: R6-S1-ED36-CANDIDATE-STABILIZATION

## Technical assessment

The accepted candidate is not reproducible because 34 tracked files are modified
and 16 top-level paths are untracked. The accepted R0–R6 implementation must be
committed selectively. Four active-root T1.2 draft configs belong to the
separate isolated packet, while `tmp_r6c4_probe/` and
`ssh yazid@tamia.alliancecan.ca` are non-source residue; none may enter R6.

## Hidden consequences

- `git add .` would mix experiment drafts and probe debris into the trusted
  environment revision.
- Omitting an accepted new schema/helper/test would produce a non-reproducible
  commit even if the current dirty tree tests pass.
- R7 remains parked and must not be merged during stabilization.
- The excluded untracked paths must be left untouched; deletion is not
  authorized by this work item.

## Classification

Revision-stabilization gap.

## Work-order scope

Make no content changes. Record the exact pre-state and accepted core hashes;
stage only the explicit R0–R6 allowlist; verify the staged manifest and diff;
run the hard checks; create one local commit; verify post-commit tracked state
and hashes. Do not push or integrate R7/T1.2.

## Required evidence

- Explicit staged-file manifest equals the authorized allowlist exactly.
- Excluded T1.2/probe/SSH paths are neither staged nor modified.
- Named boundary, environment bundle, full suite, Ruff, lock, Bash, staged diff,
  and commit-tree checks pass.
- Stabilized commit retains the two V5B-accepted hashes exactly.
- Post-commit status contains no tracked modifications and only the predeclared
  excluded untracked paths; otherwise stop and report.

## Engineer result

Commit `c6ef2df5bb38791a26e4e9490243f327dc6aeb85` has parent
`70b7ed8a7c264fd96a7149241a8995e125a3af2a`, message
`Stabilize Interlab repairs through ED-36`, and exactly the manifest’s 46 paths.
The accepted core sizes/hashes are unchanged; named test, environment 73, full
714/3-deselected suite, Ruff, lock, Bash, cached/working diff checks passed.
Tracked state is clean. The four collapsed status entries corresponding to the
six explicit exclusions remain untracked and untouched.

# Accepted Work Item: R6-V5C-STABILIZED-COMMIT-VERIFICATION

## Technical assessment

The commit manifest and working-tree identities match the stabilization report,
but reproducibility must be established from committed bytes without the
active root’s excluded files. A temporary detached worktree at `c6ef2df` gives
the required isolation.

## Hidden consequences

- Running only in the active root would not prove excluded untracked configs or
  probe files are irrelevant.
- A detached worktree must be removed after audit; no branch, commit, or push is
  authorized.
- Acceptance is local-revision acceptance only. External ED-36 acquisition,
  environment installation/equivalence, fifth certification, R7/T1.2
  integration, and cluster work remain separate.

## Classification

Final local revision-verification gap.

## Work-order scope

Audit commit metadata/tree against `R6_STABILIZATION_MANIFEST.md`, create a
temporary detached worktree at the exact commit, verify hashes/status there,
run the committed named/environment/full/static checks, remove the worktree,
and confirm the main root is unchanged.

## Required evidence

- Exact commit/parent/message and 46-path set; no excluded or management path.
- Exact V5B core hashes from the detached checkout.
- Clean detached status and green named/environment/full suite, Ruff, lock,
  Bash, and diff checks.
- Worktree cleanup and unchanged main-root HEAD/status/hashes.
- Verdict `Accepted reproducible local revision` or `Needs correction`.

## Auditor result

**Accepted reproducible local revision.** Clean detached checkout matched the
exact 46-path tree, parent/message, 12 new files, three schemas, and V5B hashes.
Named test 1, environment 73, full suite 714/3 deselected, Ruff, lock, Bash, and
diff checks passed. Main-root state and exclusions were unchanged; all audit
worktrees and temporary state were removed.

# Active Work Item: R8-I1-R7-LAUNCHER-INTEGRATION

## Technical assessment

R7 commit `b7aad6a2e25a45c5b4fab48951b5bfd92a47ae53` is accepted but based on
`70b7ed8`. It must be applied onto `c6ef2df` without mutating main. The only
expected semantic overlap is `slurm/launch_steer.sh`, where the stabilized R2
description correction must survive alongside R7’s Bash-wrap and Tamia
whole-node resource changes.

## Hidden consequences

- Taking the R7 version wholesale could regress the accepted R2 steer-header
  contract.
- Train keeps `--mem=100G`; changing it to `mem=0` is not authorized.
- Certify is already corrected and must remain byte-unchanged.
- T1.2 is not yet accepted and must not be integrated in this item.

## Classification

Accepted-branch integration.

## Work-order scope

Create a new isolated integration worktree/branch at `c6ef2df`; cherry-pick R7;
resolve only the steer overlap while preserving R2; verify exactly four launcher
files differ from the base; commit locally with no push or main mutation.

## Required evidence

- Four-launcher diff only: characterize, steer, validate, train.
- Exact Bash-wrap behavior for all four; whole-node `h100:4, mem=0` for
  characterize/steer/validate; train remains `h100:4, mem=100G`.
- Certify unchanged; all job/account/time/output/error/config fields preserved;
  R2 steer description preserved.
- Bash syntax, non-submitting decoded-payload probes, full suite, Ruff, lock,
  diff, commit scope, and worktree isolation evidence.

# Absorbed Test Work

## R6-C6A-ED36-TEST-FIXTURE-COVERAGE — absorbed into C7

Repair only the seven V5A test failures and missing torch coverage:

1. mutate creator bytes without changing recorded size so the hash-mismatch
   assertion reaches the intended boundary; do not weaken the size check;
2. make the alias-duplicate fixture use individually normalized distribution
   names so duplicate detection is actually reached, while retaining coverage
   for unnormalized-name rejection;
3. add the required approved virtualenv wheel to the five install-record
   fixtures so their success/CUDA/extra/version/dirty assertions execute;
4. add explicit torch cases for wrong filename, wrong recorded size, and an
   out-of-bundle artifact path using local fixtures.

These repairs remain separately traceable in the ledger but are executed inside
C7's authorized test-file scope so the full suite can be green before V5B.

# Parked Accepted Work Item: R7-C1-LAUNCHER-FIX-PROPAGATION

Accepted in isolation at commit
`b7aad6a2e25a45c5b4fab48951b5bfd92a47ae53` on local branch
`r7-launcher-propagation`, worktree `D:\qwen-sae-interp-r7-launchers`, based
on `70b7ed8`. Integration is deliberately deferred until R6 is accepted and
stabilized; the active tree and `main` were not mutated.

## Technical assessment

`launch_characterize.sh`, `launch_steer.sh`, and `launch_validate.sh` retain
the two defects already measured and corrected for certify: Tamia rejects
single-H100 requests, and `sbatch --wrap` executes module/source commands
under `/bin/sh`. `launch_train.sh` already requests four H100s but retains the
shell-boundary defect.

## Hidden consequences

- Characterize/steer/validate currently cannot enter their Python jobs on
  Tamia, blocking the ablation chain.
- The wrapped remote command contains deferred environment expansion; careless
  quoting can substitute submit-host values or change operation order.
- Train remains an intentional non-capability until SS3 is built; repairing
  its wrapper must not imply otherwise.
- Train `--mem=100G` may be deliberate and is not calibrated by certify
  evidence; changing it requires a separate decision.
- The active tree has an accepted uncommitted prose correction in
  `launch_steer.sh`; the isolated branch must not overwrite or absorb it.

## Classification

Implementation-defect propagation. No architectural ambiguity.

## Work-order scope

- Apply the byte-identical certify `bash -lc %q` boundary to characterize,
  steer, validate, and train.
- Set characterize and steer from `h100:1`/`64G` to `h100:4`/`mem=0`.
- Set validate from `h100:1`/`48G` to `h100:4`/`mem=0`.
- Leave train at `h100:4`/`mem=100G`.
- Preserve every `REMOTE_CMD`, time, name, log path, account, CPU/node/task
  value, interpolation, and scientific parameter.

## Required evidence

- Bash syntax for all four files.
- Stubbed non-submitting scheduler capture for all four: exact decoded remote
  payload/order, remote venv fallback not expanded on submit host, one
  `bash -lc`, and exact resource arguments.
- Characterize/steer/validate contain one `h100:4` and one `mem=0`; train
  contains one `h100:4`, retains one `mem=100G`, and contains no `mem=0`.
- Diff against `70b7ed8` confined to the four launchers and authorized lines.
- No scheduler, config, registry, artifact, scientific output, or active-tree
  mutation.
- Commit only to the isolated R7 branch; do not merge to `main`.

## Acceptance evidence

- Changed-file scope is exactly `launch_characterize.sh`, `launch_steer.sh`,
  `launch_validate.sh`, and `launch_train.sh`; `launch_certify.sh` is untouched.
- Bash syntax passed 4/4 and stubbed, non-submitting `sbatch` captures passed
  4/4.
- Each decoded wrapper equals its original `REMOTE_CMD` byte-for-byte, uses
  exactly one `bash -lc`, and preserves the literal remote venv fallback.
- Characterize/steer/validate request exactly `h100:4` and `mem=0`; train
  retains exactly `h100:4` and `mem=100G`.
- `git diff --check` passed; no scheduler or scientific state was changed.

## Deferred integration condition

After R6 stabilization, merge or cherry-pick the isolated commit while
preserving the active tree's accepted R2 `launch_steer.sh` prose correction,
then repeat syntax, stub-capture, diff, and relevant regression checks.

# Prepared Research Packet: T1.2-ABLATION-9056-PREP

The Researcher approved the hypotheses, prompts, `positions: all`, sampling
hyperparameters, matched-frequency control, and `n_docs: 20000`, conditional
on revisions. The local packet now has three steer configs for seeds 0/42/123;
independent inspection confirms all four configs are schema-valid, the sibling
steer payloads otherwise match, output directories are distinct, and the old
single-seed config is absent.

The packet remains **Needs correction / not executable**:

- the Lab Assistant selected 0/42/123 from alternative recommended seed sets
  without a separate authoritative selection;
- the spec/config comments incorrectly state that characterize emits A8;
  characterize emits A7, while validate emits A8 from A7 + census A3 + concept
  inputs;
- no Researcher-authored `cheese` ConceptBattery, matching census evidence, or
  validate config exists;
- the H2 plan uses an unpaired Mann–Whitney alternative for paired prompts and
  treats non-significance as “indistinguishable” without an equivalence margin;
- judge-repeat aggregation, paired effect-size definition, multiplicity/gate
  handling, and allowable pre-judging A9 quality review are not fixed;
- canonical SS9 currently provides prompt-group bootstrap CIs, pooled Cohen's
  d, seed variance, and BH-FDR—not t-tests, Wilcoxon, or Mann–Whitney—so the
  Researcher must either align criteria to existing primitives or authorize a
  separate stats implementation item;
- all steer configs retain zero A7/A8 placeholder hashes;
- R6 acceptance, R7 integration, Stage-2 ED-19/A12 readiness, and complete Lab
  Assistant preflight remain external gates.

Next research action is Q-011 protocol closure. The Lab Assistant must not edit
or execute this packet further until the Researcher resolves those fields and
an implementation role is explicitly assigned to apply them.

Q-011-C4 closes the final ED-8 gate: battery v1.1.0, author
`Mohamed El Yazid — IID`, exact change text, two-entry changelog, generator
de-constantization, deterministic golden regeneration, real-battery assertion
updates, and historical extractor preservation are authoritative. Full protocol
authority is recorded in
`project_management/RESEARCH_PACKETS/T1_2_CHEESE_PROTOCOL.md`.

T1.2-C1 may proceed only in a separate worktree/branch based on `70b7ed8`; it
must not mutate the active cumulative R6 tree or parked R7 worktree. No merge or
push occurs before R6 stabilization.

## T1.2-C1 bounded implementation scope

- Add the authorized cheese A2 and battery v1.1.0 changelog.
- Add a battery-wide FineWeb census config, DRAFT feature-9056 validate config,
  the approved characterize config, and three seed-specific steer configs.
- Correct the protocol spec to the authoritative artifact chain, scheduling,
  statistics, QC, current R6 gates, and parked-R7 state.
- Make only the authorized generator/golden/real-version-test changes; the
  historical extractor receives a comment only.
- Validate semantic sibling equality, schemas, exact golden boundary, focused
  battery/job suites, full suite, Ruff, lock, and diff.
- Commit on the isolated local branch only. No production artifact, registry,
  scheduler, environment, merge, or push action.

## T1.2-C1 Engineer result and readiness assessment

Isolated commit `c4f0da7dc52323798b7b20f8f09b119987f22b49` adds the
authorized fourteen-file packet. Battery, golden-boundary, schema, census,
validate, steer, import, lock, and diff evidence passed. Full pytest and the
characterize full-run case remain unverified on the Engineer host; repo-wide
Ruff is red only in pre-existing scripts absent from this branch's authorized
scope.

The packet is **Needs correction / not executable**:

- `configs/characterize/rwu04lpb.yaml` still says characterize emits A8; it
  emits only A7 and validate emits the DRAFT A8;
- its comment reopens `n_docs: 20000`, although that value is already
  Researcher-approved in this plan and the verification history;
- the spec and config gate comments still describe A-006 as unresolved, while
  A-006 is accepted and C7→V5B is the current R6 chain;
- T1.2-V1 independent verification has not run;
- the commit is isolated and unintegrated, R7 remains parked, R6 remains open,
  and A3/A7/A8 runtime hashes are intentionally zero placeholders.

## Returned T1.2 work item: T1.2-C2-PACKET-FACTUAL-GATE-CORRECTION

On the same isolated branch, correct only the producer-ownership, approved
`n_docs`, and current-gate comments/prose. Preserve every YAML value, concept
string, golden byte, schema, test expectation, and artifact hash. Re-run schema
and semantic-normalization checks plus targeted tests and diff checks, then
route the complete C1+C2 packet to T1.2-V1.

## T1.2-C2 result and C3 correction

Commit `e92174ada4ae96567783d6e6169350b7f5354837` correctly fixes
producer ownership and the already-approved `n_docs: 20000`. Four edited YAML
objects are semantically identical to C1; characterize passed 13/13 and full
pytest passed 603/3 deselected. The only remaining defect was created by
parallel progress: C2 pinned the current R6 chain as `C7→V5B`, and C7 was then
returned for C8.

`T1.2-C3-STABLE-R6-GATE-WORDING` must replace those volatile sub-item IDs in
the same five files with the stable execution condition that R6/ED-36 local
implementation and verification are accepted. It must not mention C8 or any
other current repair ID. All YAML values and other prose remain unchanged.

## T1.2-C3 result and queued T1.2-V1

Clean isolated commit `e9ad36172e3cccd2410beef606ab5dde52a597f2`
changes exactly the five authorized comment/prose files. Four YAML semantic
objects remain identical to `e92174a`; no volatile R6 IDs remain; stable gate
wording is consistent; characterize passed 13/13, schema tests 24/24, lock and
diff checks passed.

No known packet defect remains. `T1.2-V1-PROTOCOL-PACKET-VERIFICATION` is queued
for the persistent Auditor after R6-V5B completes. It audits the entire isolated
packet from `70b7ed8` through `e9ad361`, including C1 scientific/ED-8 content,
C2 producer/n_docs corrections, and C3 stable gates. Acceptance is preparation
only and does not lift R6, R7, environment, A3/A7/A8, preflight, or ED-19 gates.

## T1.2-V1 result

**Accepted for isolated preparation packet.** Clean `e9ad361`, exact 14-file
scope, exact ED-8 author/change/changelog, golden regeneration/hash boundary,
12 probes/20 negatives/39 markers, six config schemas, A2→A3/A7→A8→A9 chain,
sampling/statistics/scheduling/gates, focused 148, and full 603/3-deselected
suite all passed. Only the identical inherited two-script Ruff baseline remains
on the old isolated base. No state was modified.

# Active Work Item: R8-I2-T12-PACKET-INTEGRATION

## Technical assessment

The audited three-commit T1.2 packet is based on `70b7ed8`; accepted R6 is
`c6ef2df`. The packet touches 14 data/config/doc/test files and is disjoint from
R7’s four launchers, so it can be integrated independently and later combined
without semantic conflict.

## Hidden consequences

- The active main root contains obsolete untracked T1.2 drafts; integration
  must occur only in a new clean worktree.
- Cherry-pick order C1→C2→C3 must be preserved so the audited final tree is
  reproducible.
- Zero lineage hashes remain deliberate; do not fabricate or fill them.
- R7 must not be pulled into this branch during I2.

## Classification

Accepted-packet integration.

## Work-order scope

Create a separate worktree/branch at `c6ef2df`; cherry-pick the three audited
packet commits in order; confirm final diff contains exactly the 14 authorized
files and matches the accepted `e9ad361` packet semantics; run integration
tests; do not push or touch other worktrees.

## Required evidence

- Exact commit order/parents and 14-file diff only.
- File/hash or semantic comparisons against the accepted packet, including the
  golden hash and four YAML equality constraints.
- All configs schema-valid; focused 148, full integrated suite, exact Ruff,
  lock, and diff checks green.
- Main, R7, R7-integration, and source T1.2 worktrees unchanged.

# Immediate Presentation Lane: P0-PI-PRESENTATION-EVIDENCE-PACKET

The full experiment roadmap is not executable tonight: R6-V5C and T1.2-V1 are
unresolved, R7/T1.2 are not integrated, the external ED-36 environment and
equivalence evidence are absent, and the ablation chain has no production
A3/A7/A8/A9/A9′. Multiple sequential preparation/GPU/judge stages remain.

Existing evidence is presentation-usable with explicit provenance:

- rwu04lpb multilingual rerun: world_cup 13/20 shared (mean pairwise Jaccard
  0.659), quebec 12/20 (0.618), poutine 10/20 (0.513), couscous 4/20 (0.383);
- characterize-lite job 383755 over 5,000 FineWeb documents / 1,712,777 token
  positions: cheese feature 9056 fires 5.86e-4 (14.5× median), max 47.5, 1,003
  firings; UNESCO 47735 is also clean; Eurovision 44189 is weak/marginal;
- T1.2 may be presented as an approved preregistered necessity protocol with
  no result yet.

The Lab Assistant may assemble a read-only presentation packet from those
files. It must not rerun GPU work, write results, or imply ablation evidence.

# Completed Work Item: R8-I2-C1-INTEGRATION-BYTE-FIDELITY

## Technical assessment

The integration commit chain and 14-file packet overlay are correct at
`7597af0b38e18980a410edbb50a3de354bb39e3c`, but the required full suite is
not acceptable (`7 failed, 707 passed, 3 deselected`). Read-only inspection
established checkout byte drift, not a T1.2 or R6 implementation defect. Both
integration worktrees were created under global `core.autocrlf=true`; their
Git blobs are correct while two working files are CRLF-expanded.

## Hidden consequences

- `slurm/requirements.cluster.txt` is 187,043 bytes / `3b8e0bfd...f8c` in the
  integration worktree instead of accepted 184,572 / `9da00e03...314`.
- `configs/certify/hm03l7yz.yaml` is 391 bytes / `6628dd29...6822` instead of
  accepted 379 / `6dfb9e35...f326`.
- These byte differences explain all seven environment-bundle failures and
  reproduce the checkout limitation already resolved in R6-V5C.
- Editing or recommitting either file would corrupt the accepted integration
  boundary; the correction belongs solely to checkout setup.

## Classification

Environment limitation / verification setup defect.

## Work-order scope

Verify unchanged commit `7597af0` in a fresh command-scoped
`core.autocrlf=false` worktree. Confirm authoritative hashes before testing;
rerun the seven failed tests and full suite. Make no commit or product edit.

## Required evidence

- Fresh worktree command and exact commit identity.
- Both authoritative sizes and SHA-256 values before tests.
- Seven formerly failing cases green, followed by full pytest green.
- Exact Ruff, lock, diff, and clean-status checks.
- Source packet, main, R7, and both existing integration worktrees unchanged.

## Result

**Accepted.** A detached `core.autocrlf=false` checkout of exact commit
`7597af0` restored both authoritative byte hashes. Environment-bundle tests
passed 73/73; full pytest passed 714/714 with 3 deselected; exact Ruff, lock,
diff, and clean-status checks passed. All protected worktrees were unchanged.

# Completed Engineering Work Item: R8-I3-R7-T12-COMBINED-INTEGRATION

## Technical assessment

R6 is accepted at `c6ef2df`; R7 launcher integration exists as the single
four-file commit `a65dfb4`; T1.2 integration is accepted at `7597af0`. The two
overlays are path-disjoint and must now be assembled into one byte-faithful
candidate before any cluster/environment action.

## Hidden consequences

- The R7 steer blob intentionally differs from the parked R7 source only
  because it preserves the later accepted R2 factual header correction.
- The combined checkout must use command-scoped `core.autocrlf=false`.
- T1.2 zero A3/A7/A8 hashes remain deliberate preparation placeholders.
- Combining commits does not authorize execution, environment construction,
  registry writes, or filling lineage hashes.

## Classification

Integration work.

## Work-order scope

Create a new LF-faithful branch/worktree at R7 integration commit `a65dfb4`;
cherry-pick the three T1.2 integration commits `739fe03`, `05232b4`, and
`7597af0` in order. Verify the exact 18-file union and run combined tests. No
push, cluster action, or protected-worktree mutation.

## Required evidence

- Exact base, new commits/parents, and 18-path union only.
- Four R7 launcher semantics plus preserved R2 steer header.
- Fourteen T1.2 blobs identical to accepted `7597af0`.
- Authoritative requirements/config hashes before and after testing.
- Environment 73, full 714/3-deselected, Ruff, lock, Bash syntax for all five
  launchers, diff, and clean status green.

## Engineering result

Combined candidate `4bf0fd88f129549569ca3353ccef965a93b51395` is clean
and has the exact four-commit ancestry from `a65dfb4`. Its diff from `c6ef2df`
is the required 18-path union. The 14 T1.2 blobs match `7597af0`; launcher
semantics and the R2 steer header are preserved; authoritative byte hashes
match before/after. Environment 73, full 714/3-deselected, Ruff, lock, Bash,
stubbed submission, diff, and clean-status checks passed.

# Accepted Work Item: R8-V1-COMBINED-INTEGRATION-ACCEPTANCE

## Technical assessment

The combined local revision is the first candidate containing accepted R6,
R7, and T1.2 preparation together. This is a major milestone boundary, so an
independent clean-checkout audit is proportionate before any push, external
environment construction, preflight, or cluster execution.

## Hidden consequences

- Acceptance establishes repository readiness only; it does not supply ED-36
  acquisition/install/equivalence evidence or production A3/A7/A8 artifacts.
- A CRLF-converted audit checkout would create false hash failures; the Auditor
  must use command-scoped `core.autocrlf=false`.
- Zero lineage placeholders must remain zero during this audit.

## Classification

Verification gap at a major integration milestone.

## Work-order scope

Audit exact commit `4bf0fd8` from a fresh detached LF-faithful worktree. Inspect
the commit graph, exact 18-file boundary, packet blobs, launcher deltas, R2
header, schemas/placeholders, authoritative byte hashes, and run independent
focused/full/static checks. Make no repository or external-state changes beyond
disposable local test state.

## Required evidence

- Exact commit/parent chain and 18-path union.
- 14 T1.2 blobs and four R7 launcher behaviors independently confirmed.
- Golden/config/schema/placeholder preservation.
- Authoritative requirements/config hashes before and after.
- Environment 73, full 714/3-deselected, Ruff, lock, Bash, non-submitting
  launcher checks, diff, and clean tracked status.

## Audit result

**Needs correction — verification independence was not established.** The
report explicitly reused `D:\qwen-sae-interp-combined-lf`, said it did not
create a new checkout, and repeated the Engineer's results. Repository
inspection confirms the requested audit path does not exist and no detached
audit worktree was registered. The combined candidate remains clean and no
implementation defect is indicated, but R8-V1 cannot be accepted from
non-independent evidence.

# Active Work Item: R8-V1-C1-INDEPENDENT-CHECKOUT-RETRY

## Technical assessment

The remaining gap is procedural: run the already-specified audit against exact
commit `4bf0fd8` from a newly created detached LF-faithful checkout, rather than
the Engineer's retained branch worktree.

## Hidden consequences

- Repeating commands in the Engineer's environment cannot detect retained or
  worktree-local state and is not independent acceptance evidence.
- No source correction, new commit, or broader test design is authorized.

## Classification

Verification gap.

## Work-order scope

Create `D:\qwen-sae-interp-combined-audit-lf` detached at `4bf0fd8` with
command-scoped `core.autocrlf=false`; execute the named inspection and tests
there; report its independent pre/post identity and state.

## Required evidence

- Exact worktree-creation command and registration at the audit path.
- Audit checkout path visible in test commands/output and imports where useful.
- Independent pre/post hashes, focused/full/static results, and clean status.
- Engineer worktree untouched and separately identified.

## Independent retry result

**Accepted.** Auditor 2 created a fresh detached LF-faithful worktree at exact
commit `4bf0fd8`, proved path/import isolation, exact ancestry and 18-path
scope, 14/14 T1.2 blob identity, six schemas, eight zero placeholders, golden
hash, launcher preservation, and stable authoritative byte hashes. Independent
results: environment 73, focused 103, full 714/3-deselected, Bash/stubbed
launchers, Ruff, lock, diff, and clean status all passed. No external state was
accessed or modified.

# Accepted Work Item: R8-X1-PUBLISH-COMBINED-REVISION

## Technical assessment

Exact commit `4bf0fd88f129549569ca3353ccef965a93b51395` is the first
independently accepted combined R6+R7+T1.2 revision. Tamia cannot reproducibly
pull this revision until it is published to the shared remote.

## Hidden consequences

- Publishing to `origin/main` is a fast-forward external repository mutation.
- Only the exact audited commit may be pushed; no merge, rebase, regeneration,
  or additional file may enter the publication boundary.
- Publication does not itself authorize cluster environment construction or
  experiment execution; those remain separate Lab Assistant work items.

## Classification

Human authorization for external state change.

## Work-order scope

Obtain explicit Researcher authorization to fast-forward `origin/main` to
exact commit `4bf0fd8`. After authorization, route a bounded publish-and-verify
operation to the persistent Engineer.

## Required evidence

- Explicit authorization naming the exact commit and destination branch.
- Later push report must show pre/post remote refs and exact fast-forward only.

## Result

**Accepted.** Explicit authorization was supplied and exact audited commit
`4bf0fd88f129549569ca3353ccef965a93b51395` was pushed fast-forward-only to
`origin/main`. Remote moved from `70b7ed8` to `4bf0fd8`, gaining five commits
and losing none. Local remote-tracking state independently resolves
`origin/main` to `4bf0fd8`; local `main` remains four commits behind with the
same preserved untracked entries. No cluster action occurred.

# Completed-with-Deviation Work Item: R9-X1-TAMIA-PREFLIGHT

## Technical assessment

Tamia can now fetch the exact accepted revision, but the publication approval
explicitly did not authorize cluster access or execution. Before environment
construction or GPU work, the Lab Assistant should perform one bounded
host-only preflight: safely fast-forward a clean/non-conflicting Tamia checkout
to `4bf0fd8`, then inspect the retained ED-36 inputs, venv state, checkpoint,
corpus, and config prerequisites without mutating the environment or submitting
a job.

## Hidden consequences

- A dirty, divergent, or path-conflicting Tamia checkout is a stop condition;
  do not reset, clean, stash, overwrite, or discard cluster state.
- The incomplete historical `~/interplab-venv` must not be deleted or reused as
  production evidence during discovery.
- Preflight does not authorize bundle construction, venv creation, equivalence,
  certification, A3/A7/A8, or steering jobs.

## Classification

Human authorization for bounded cluster access and fast-forward/preflight.

## Work-order scope

Authorize the Lab Assistant to access Tamia, record pre-state, fast-forward the
cluster repository to exact `4bf0fd8` only if safe, and perform read-only
environment/experiment prerequisite discovery. No scheduler or GPU action.

## Required evidence

- Explicit authorization for Tamia access and exact revision update.
- Cluster pre/post HEAD/status, safe-fast-forward proof, and no-loss evidence.
- Read-only inventory of ED-36 bundle/manifests/venvs, checkpoint/corpus/config
  paths, hashes where inexpensive, and precise blockers.
- Zero scheduler jobs and zero scientific artifacts.

## Result

The preflight evidence is accepted as measured discovery: Tamia now resolves
exact `4bf0fd8`; no bundle or usable production venv exists; checkpoint, corpus,
configs, and R7 launchers are present; queue and artifact counts were unchanged.
However, the Lab Assistant fast-forwarded while one tracked file was dirty,
despite the explicit dirty-tree stop condition. The change was non-conflicting
and preserved, so no rollback is indicated, but the existing checkout cannot
serve as clean ED-36 source evidence. Classification: **Needs correction —
procedural deviation**, with the discovery evidence retained.

# Accepted Work Item: R9-A1-ED36-BUNDLE-CONSTRUCTION-PROTOCOL

## Technical assessment

ED-36, the acquisition/install schemas, `environment_bundle.py`, and
`setup_env.sh` rigorously validate and consume a prepared offline bundle, but
the repository has no command or script that constructs the bundle or its
acquisition manifest. The CLI exposes only `preflight`, `create-venv`, and
`record-installed`. The Lab Assistant may not invent the missing provenance-
critical acquisition/build procedure.

## Hidden consequences

- Bundle assembly must resolve the full Linux CPython 3.11 non-torch closure,
  exact installer tooling, the Alliance `torch==2.13.0+computecanada` artifact,
  and any derived-wheel records without cluster network access.
- The existing dirty Tamia checkout cannot produce a clean revision identity;
  a separate clean worktree is required.
- Choice of acquisition host, wheel selection, manifest generator identity,
  derived-build commands, and retention paths directly affects ED-36 evidence.
- Without a ruled procedure, manual construction risks an unverifiable or
  non-reproducible production environment.

## Classification

Architectural/procedural ambiguity plus possible missing implementation.

## Work-order scope

Architect determines whether ED-36 permits a precisely specified external
manual construction procedure or requires a repository bundle-builder before
Lab Assistant execution. Define the exact acquisition, torch, derived-wheel,
manifest, clean-worktree, transfer, validation, and retention contract.

## Required evidence

- Decision grounded in ED-36 §§1–8 and current implementation surfaces.
- Exact role ownership and dependency-ordered next action.
- A complete command-level construction contract or a bounded Engineer
  implementation contract; no invented scientific parameters.
- ED amendment only if the existing blueprint must change.

## Architect result and reconciliation

Both Architect reviews agree on the controlling outcome: current ED-36 cannot
be operationalized manually; a checked-in deterministic builder is required,
and no ED amendment is needed. The conservative implementation contract uses
the multi-phase target-capture/runtime-build/Alliance-torch-import/finalization
design because it addresses the measured source-only-package, derived-wheel,
tooling-closure, transfer, and non-overwrite gaps. It also includes the first
review's independently identified §5 defect: `record-installed` must execute
the created venv's `pip check` and fail closed.

# Blocked Work Item: R9-C1-ED36-BUNDLE-BUILDER-AND-PIP-CHECK

## Technical assessment

Implement the deterministic two-phase builder/finalizer, derived-wheel and
tooling closure, setup hardening, and mandatory installed-environment
`pip check` in one trust-boundary candidate. This is local implementation only;
no actual bundle, network acquisition, Tamia action, or venv mutation.

## Classification

Implementation defect / missing operationalization.

## Work-order scope

Allowed paths are `interplab/core/environment_bundle.py`, `slurm/setup_env.sh`,
new `slurm/environment_bundle.tooling.lock.json`, existing
`tests/test_environment_bundle.py`, and new
`tests/test_environment_bundle_builder.py`. Dependency truth, schemas, and
blueprint remain byte-identical.

## Required evidence

Deterministic fixture-based capture/build/import/finalize tests; full closure,
tag precedence, tooling overlap, source-only derived wheels, Alliance torch,
offline/non-network, tamper/symlink/path/revision/destination/non-overwrite,
3.2.1 separation, and pip-check failure cases; existing environment/full suites,
Ruff, lock, Bash, and diff checks.

## Engineer result

**Blocked correctly before mutation.** Worktree remained clean at `4bf0fd8`
with no commit. Runtime measurement confirmed 110 marker-active non-torch
distributions and exactly two source-only packages (`py2store==0.1.22`,
`transformers-stream-generator==0.0.5`). The required tooling lock cannot be
authored from checked-in evidence: pip, wheel, hatchling, virtualenv, build,
and several closure artifacts are absent from `uv.lock` and local sanctioned
artifact evidence. Exact versions/files/origins/sizes/hashes require a one-time
authorized networked tooling-lock bootstrap. Inventing them is prohibited.

# Accepted Authorization: R9-X2-TOOLING-LOCK-ACQUISITION

Authorize a Linux x86_64 CPython 3.11 networked bootstrap that resolves the
operational tooling closure exactly once, downloads the selected artifacts,
records commands/origins/filenames/sizes/SHA-256/METADATA, and transfers the
evidence locally to the R9 Engineer. It must not build the runtime bundle,
access Tamia, mutate dependency truth, or install globally.

## First bootstrap result

**Needs correction; stopped safely with zero repository edits.** Retained Linux
x86_64 CPython 3.11.15 evidence contains 14 artifacts and a passing disposable
`pip check`, but `distlib-0.4.3-py2.py3-none-any.whl` violates the Program
Manager's literal `py3-none-any`-only rule. A narrow universal-wheel ruling is
required. Orchestrator inspection also found three issues that must be corrected
before resumption regardless of that ruling:

- runtime/tooling overlap drift: acquired `filelock 3.32.2` conflicts with
  runtime `3.29.7`, and `platformdirs 4.11.0` conflicts with runtime `4.10.0`;
- pip 25.0's retained record lacks its exact direct origin URL;
- the report names uv 0.8.22 as generator identity but does not list a retained
  uv artifact record with filename/origin/size/hash.

The next bootstrap must constrain every runtime overlap to the exact exported
artifact identity, reacquire complete pip origin evidence, and record the uv
generator artifact/identity fully.

# Accepted Decision: R9-D1-UNIVERSAL-PURE-WHEEL-TAG-RULING

Universal pure wheels are eligible when every parsed tag has ABI `none` and
platform `any`, at least one tag is compatible with the exact CPython 3.11
target, any `Requires-Python` admits that target, and filename/WHEEL/METADATA/
origin/size/SHA-256 agree. This admits compressed tags such as
`py2.py3-none-any`; it does not pre-attest the retained `distlib` digest.

`uv==0.8.22` is the sole enumerated platform-coupled exception. The retry will
retain its exact Linux x86_64 artifact compatible with the Tamia target and
record its platform tag explicitly. No other compiled/platform-coupled tooling
artifact is allowed without a new ruling.

The retry must also enumerate the pip/setuptools/wheel seed wheels embedded in
`virtualenv==20.26.0`. An embedded setuptools version other than `83.0.0` is a
stop condition. Runtime overlaps remain fixed at the exported artifact
identities, including `filelock==3.29.7`, `platformdirs==4.10.0`,
`setuptools==83.0.0`, and `packaging==26.2`; pip needs its direct origin and uv
needs complete retained artifact provenance. Conflicts stop the bootstrap and
must never be resolved by relaxing a pin.

# Engineer-complete Work Item: R10-C1-T12-STATISTICS-DOC-CORRECTION

Commit `2e8efb0822d04d30d7d7ed97e6fbf451056b2479` changes only
`docs/ablation_9056_spec.md` and replaces stale test-based prose with the
authorized bootstrap/equivalence/repeat/independent-seed/structural-gate rules.
Search, lock, diff, scope, and clean-state evidence passed. Independent
documentation verification is queued before integration.

# Accepted Decision: Q-013 — corrected scheduler envelope

- The initial CPU-only ruling is superseded. Census uses Tamia's proven
  whole-node allocation: account `aip-chgag196`, one node/task, `mem=0`,
  `h100:4`, no partition/constraint, and R5-C2 login-Bash wrapping. No
  `sbatch --test-only` zero-GPU probe is required.
- Walltime is 2× recovered elapsed rounded up to the hour, or 12h if neither
  scheduler nor log evidence survives.
- CPUs default to 8; raise to 16 only when a fast/Rust tokenizer and enabled
  parallelism are both confirmed. A slow/Python tokenizer remains 8 but must be
  reported before scheduling.
- Dataset revision: retain `unknown` as an explicit limitation, pinned
  empirically by 601,369 docs, 400,000,109 tokens, checksum `831261f2...`, and
  tokenizer revision `cf98f3b3...`.
- Seed-0 review: structural/blinded only; matched-frequency control metadata
  checks are permitted, generation content inspection is not.
- Result-derived hash substitution is authorized only after artifact acceptance,
  using A10 output hashes and the four specified chain-consistency checks.

# Completed Preparation Item: R9-P1-T12-EXECUTION-STAGING-PACKET

## Technical assessment

No experiment job is currently admissible: the ED-36 bundle/install evidence
and production venv are absent, TransformerLens equivalence is unrun, and the
T1.2 A7/A8 lineage hashes remain zero. While R9-A1 resolves construction, the
Lab Assistant can eliminate later operational latency by preparing an exact
dry-run execution packet from the accepted revision and protocol.

## Classification

Non-mutating execution preparation; not scientific execution or evidence.

## Work-order scope

Map the exact environment gate and A3→A7→A8→seed-0 A9 producer sequence,
commands, launch mechanisms, resource envelopes, expected artifact/hash
handoffs, logs, stop conditions, rerun policy, and copy-back plan. Identify any
remaining missing launcher or operational input. Do not access Tamia, edit
configs, replace hashes, submit jobs, or generate artifacts.

## Required evidence

- Repository-path citations for every command/config/producer.
- Explicit unresolved placeholders and deterministic substitution procedure.
- Per-stage prerequisites, expected outputs, success/failure evidence, and
  exact next authority needed.

## Staging result

Packet prepared with no Tamia execution or file mutation. It establishes the
A3→A7→A8→seed-0 A9 handoffs, exact commands, artifact snapshot method, logs,
resource envelopes for existing launchers, substitutions, and stop/rerun rules.
One remote-ref-only `git fetch` occurred despite the stated no-network framing;
no working-tree or external production state changed. Gaps were triaged:

- T1.2 equivalence is policy-required before experiment execution even though
  code requires the report only for R5-X2 certification.
- Census's A1+A3 production is the accepted job contract, not a new ambiguity.
- `project_management/` absence from git is intentional under A-003; the
  execution prompt transmits decisions, while the tracked ablation spec must
  match them.
- Missing census launcher/resource envelope and `revision: unknown` remain
  Researcher/implementation gates.
- Tracked statistics prose is stale and can be corrected independently.
- Mtime-based launcher advice is a real but non-blocking implementation defect;
  the staged before/after snapshot method is the safe current procedure.

# Parallel-lane orchestration policy — 2026-08-03

The Researcher explicitly requires all dependency-safe work to proceed in
parallel across persistent Engineers, Auditors, Architects, and Lab Assistants.
Every routing assessment must include active lanes, newly unblocked lanes,
blocked lanes with their exact dependency, and collision controls for files,
worktrees, cluster paths, registries, and external state.

Keep one bounded copy-paste prompt for the selected target conversation while
preserving already-running lanes. Parallelism does not waive acceptance or
authority gates. Do not start two writers against the same files/worktree/
artifact namespace; do not audit a moving candidate; and do not let preparation
become cluster execution without explicit authority.

Current parallel frontier:

| Lane | Role | Status | Collision boundary |
|---|---|---|---|
| R9-D1 | Human / Researcher | Accepted/closed | Universal pure-wheel rule approved; uv is the sole platform exception; virtualenv seed wheels are an explicit overlap boundary. |
| R9-X2B | Engineer 2 | Needs correction/blocked | Offline preflight found virtualenv 20.26.0 embeds setuptools 68.0.0 and 69.5.1; no rebootstrap occurred. |
| R9-A2 | Architect | Accepted/complete | Both Architect reviews select pinned virtualenv 20.26.0 with mandatory unseeded, network-closed creation and verified offline pip bootstrap. |
| R9-D2 | Human / Researcher | Accepted/closed | Inert embedded seeds are allowed only under mandatory no-seed isolation; ensurepip is forbidden and post-pip inventory must be exactly pip 25.0. |
| R9-X2C | Engineer 2 | Needs correction/blocked | Artifacts are promising, but the resolver invoked implicit ensurepip and upgraded pip; verification also deleted stubs before the empty-state proof. |
| R9-X2D | Engineer 2 | Needs correction after audit | D3 closure is sound, but pre-import pip hash/executed-byte binding and non-overwriting failed-attempt retention are unproven. |
| R9-X2E | Engineer 2 | Complete/verification pending | D4 retained at `D:\\lodstar\\r9_tooling_bootstrap_20260803_d4` with read-only D3 proof, private verified pip snapshots, non-overwriting attempts, and explicit inventory framing. |
| R9-C1 | Engineer 2 | Needs correction/complete | Commit `c847e075f87a2f5cb871c59d8e94d06c9ec00280` passed broad regression gates but failed semantic and boundary audit. |
| R9-C2 | Engineer 2 | Needs correction/complete | Intermediate commit `ea65a8711d7313e0942b75ac84636b04c901fe6e` closes several boundaries but explicitly leaves network, recursive-finalization, race, TL, rollback, wrong-HEAD, and test-matrix gaps. |
| R9-D3 | Human / Researcher | Accepted/closed | Sixth path `tests/test_slurm_setup_env.py` is authorized; no seventh path is needed and the stub magic-value bypass must be removed. |
| R9-C3 | Engineer 2 | Needs correction/complete | Commit `490ae73e...` passes setup/reparse/broad gates but retains derived-wheel hash, fail-open network, archive/cross-binding/no-clobber/cleanup/pip/TL/coverage defects. |
| R9-A3 | Architect | Active/decision required | Resolve whether ranged PEP 517 build requirements may map to exact locked artifacts or must be literal exact pins; confirm mandatory isolation and derived-wheel hash trust semantics. |
| R9-C4 | Engineer 2 | Blocked/ready | After R9-A3, correct every R9-V2 defect and complete direct matrix coverage within the same six paths. |
| R9-V0A | Auditor 2 | Needs correction/complete | Old evidence root independently confirmed incomplete and unchanged. |
| R9-V0B | Auditor 2 | Needs correction/complete | Artifact closure accepted in substance; execution binding and attempt retention remain blocking. |
| R9-V0C | Auditor 2 | Accepted/complete | D4 independently passed identity, read-only source, attempt retention, exact-byte execution, closure, provenance, and retained-state checks. |
| R10-V1 | Auditor 1 | Accepted | One-file commit `2e8efb` is parked for later integration. |
| R10-X1 | Lab Assistant | Accepted/complete | Runtime `00:29:15`, exact tokenizer revision, fast backend, and unenabled parallelism recovered read-only. |
| R10-C2 | Engineer 1 | Accepted/published | Commit `9d90ef6` adds only the census launcher atop accepted `2e8efb`; origin/main now equals it. |
| R10-V2 | Auditor 1 | Accepted/complete | Independent LF-faithful audit: exact contract/stubs, 39 focused, 714 full, Ruff, lock, six Bash launchers, diff, and clean state passed. |
| R9-V1-PREP | Auditor 2 | Ready in parallel | Read-only audit-matrix preparation; must not audit the moving Engineer candidate. |
| R9-V1 | Auditor 2 | Needs correction/complete | Exact scope and broad suites passed; multiple fail-closed boundaries and most audit-matrix tests are missing. |
| R9-V2 | Auditor 2 | Needs correction/complete | Setup authority and Windows junction passed; eight production defects and broad direct-coverage gaps remain. |
| R9-V3 | Auditor 2 | Blocked/ready | Await an R9-C4 successor after the narrow Architect ruling. |
| ED-36 acceptance | Auditor | Blocked | Await corrected R9-C2 candidate and R9-V2 acceptance. |
| R11-P1 | Read-only scout | Complete | Lodestar has a real Anthropic judge backend but no Interlab bridge or capability/perplexity implementation; multiple schema/provenance/dependency decisions remain. |
| R11-A1 | Architect | Complete/awaiting ratification | Both reviews select a separate off-cluster judgment instrument, Interlab-owned capability, content-addressed evidence, and atomic Interlab finalization; ED-37 is required. |
| R11-D1 | Human / Researcher | Accepted/closed | ED-37, separate instrument topology, v2 policy, retention, security, immutable release preparation, and no-paid-call boundary are ratified. |
| R11-D1A | Human / Researcher | Active/decision required | Choose temperature-0 determinism framing versus a new stochastic instrument; rule retrospective sufficiency manifest and non-gating coherence addition. |
| R11-C00 | Engineer 1 | Blocked/ready | After R11-D1A, correct report, Evidence Ledger, and presentation language before further PI use; prose/evidence only. |
| Production experiment | Lab Assistant | Blocked | Await environment, equivalence, real A3/A7/A8 hashes, and execution authority. |

## R9-V1-PREP result

**Accepted for audit preparation only.** Auditor 2 fixed immutable base/path/
hash identities and produced a blocking matrix spanning scope, derivation,
target capture, tooling closure, derived wheels, Alliance torch, atomic
finalization, setup, pip check, non-overwrite, 3.2.1 isolation, regression, and
retained state. Exact future commands require a stable 40-character R9-C1
commit and a fresh LF-faithful detached worktree. The matrix correctly does not
claim that a real bundle, Alliance wheel, install, or equivalence exists.

## R10-V1 result

**Accepted.** Auditor 1 independently confirmed exact one-file scope at commit
`2e8efb0822d04d30d7d7ed97e6fbf451056b2479`, authoritative repeat/H1/H2/
independent-seed/structural-gate prose, absence of superseded tests, and byte-
identical preservation of all other scientific sections. Lock/diff and clean
state passed. The commit is parked for later integration with the accepted R9
successor; no separate push is indicated now.

## 2026-08-03 parallel evidence update

`R9-V0A` is **Needs correction — evidence completeness only**. Auditor 2
recomputed the 14-wheel retained root without changing it and confirmed the
filelock/platformdirs conflicts, missing pip direct origin, absent uv artifact,
and incorrect distlib classification. R9-D1 resolves distlib as tag-eligible;
R9-X2B replacement evidence and R9-V0B acceptance remain required before R9-C1.

`R10-X1` is **Accepted for launcher calibration**. Read-only Tamia recovery
found completed A10 `fb3b861d79dc`, scheduler job 382736 with elapsed
`00:29:15`, and exact tokenizer revision
`cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8`. The tokenizer is fast/Rust-backed
but parallelism was not enabled or evidenced. The A10 has `slurm: null`; job
association is inferred from exact timestamps and is not promoted to recorded
lineage.

`R10-C2` adds only `slurm/launch_census.sh` on the accepted T1.2 worktree at
`2e8efb`. It uses one hour, eight CPUs, `mem=0`, `h100:4`, account
`aip-chgag196`, and the accepted login-Bash wrapper. It must not add mtime-based
artifact discovery; later execution identifies outputs from registry snapshots
and the producing A10.

## R9-X2B stop and R9-A2 ambiguity

Engineer 2 stopped correctly before network activity. The retained
`virtualenv-20.26.0-py3-none-any.whl` embeds pip 24.0, setuptools 68.0.0 and
69.5.1, and wheel 0.42.0 and 0.43.0. This violates R9-D1's explicit embedded
setuptools 83.0.0 condition.

The current creator executes `virtualenv --no-download <target>`, which prevents
network access but does not disable seeding; the embedded wheels can therefore
populate the fresh venv before `setup_env.sh` installs the approved tooling.
Overwriting those transient versions is the reconciliation R9-D1 forbids.
R9-A2 must specify whether to create an unseeded venv and bootstrap approved
tooling by a deterministic offline mechanism, select a different fully pinned
creator under new authority, or declare another bounded resolution. R9-C1 and
the tooling rebootstrap remain paused; R10-C2 continues independently.

## R9-A2 result

Both independent Architect reviews selected Option A: retain the exact hashed
virtualenv 20.26.0 creator, require `--no-seed`, `--no-download`, and
`--no-periodic-update`, prove an empty fresh environment, then bootstrap only
the approved pip 25.0 wheel from isolated hash-verified offline bytes before
installing the remaining exact tooling. Neither review requires an ED, schema,
or frozen-blueprint amendment. Both reject creator-version substitution and
stdlib venv as unnecessary provenance regressions.

The literal R9-D1 condition forbids the embedded setuptools bytes even when
inert, so implementation remains blocked on R9-D2 Human clarification. The
recommended clarification prohibits selection, extraction, installation,
import, execution, transient overwrite, or reconciliation of embedded seeds,
while permitting their fully inventoried inert presence inside the unchanged
upstream creator wheel.

## R10-C2 Engineer result

Engineer scope is complete at commit
`9d90ef601822c1cacad0b6aade8a1a265f2b0e39`, whose parent is the accepted
statistics commit `2e8efb0822d04d30d7d7ed97e6fbf451056b2479`. The commit adds only
`slurm/launch_census.sh`. Git-Bash syntax, missing-argument failures, a
non-submitting decoded-wrap probe, exact scheduler arguments, 39 focused tests,
lock, diff, and clean-state checks passed. No cluster or artifact action
occurred. Classification remains **verification pending** until R10-V2.

## R9-D2 result

**Approved with one addition.** The byte-identical upstream virtualenv 20.26.0
wheel may retain its fully enumerated seed archives only when they remain inert
under mandatory no-seed/no-download/no-periodic-update and isolated app-data.
`ensurepip` is explicitly forbidden in every form because CPython carries a
second bundled pip/setuptools source. After the verified pip-wheel bootstrap,
the target must contain exactly pip 25.0 and still no setuptools or wheel before
the remaining hash-required tooling plan begins. The operational wheel pin is
fixed explicitly at `wheel==0.45.0`, with filename/origin/size/SHA-256. R9-X2C
tooling-evidence acquisition is now authorized; R9-C1 remains blocked until the
replacement evidence passes R9-V0B.

## R9-X2C review

The 15 retained artifact identities and corrected overlaps appear complete, but
the procedure is not admissible. The acquisition transcript created
`/tmp/resolver-venv` with `python -m venv` and then ran `pip install --upgrade
pip==25.0`; default `venv` invokes CPython's forbidden ensurepip bundle. Later
verification transcripts also remove pip/wheel script paths before recording
the authoritative empty inventory, weakening the fresh-state proof.

R9-X2D must preserve both prior evidence roots, use fresh absent targets created
only with `--without-pip`, bootstrap exact verified pip-wheel bytes before any
resolver/acquisition operation, never use `--upgrade` or ensurepip, and fail
rather than delete unexpected scripts or distributions before inventory.

## R9-X2D result

Engineer 2 retained stable D3 evidence at
`D:\lodstar\r9_tooling_bootstrap_20260803_d3`. Both earlier roots retained
identical pre/post file-only inventory digests. D3 records a clean resolver and
verifier created with `--without-pip`, empty unsanitized pre-bootstrap states,
verified pip 25.0-only bootstrap, exact post-pip inventory, exact 15-artifact
offline closure, final `pip check`, corrected overlaps, direct origins, the uv
exception, and inert virtualenv seed inventory. It distinguishes the 3.11.15
acquisition host from the later Tamia 3.11.5 target gate.

Two failed D3 validation attempts are retained: a missing repository import path
and a normalized-name assertion. Both are reported as evidence-script defects,
not artifact failures. R9-V0B must verify that the successful continuation did
not alter acquired bytes or weaken any invariant before R9-C1 resumes.

## R9-V0B result

**Needs correction.** Auditor 2 independently confirmed the exact 15-artifact
closure, origins, overlaps, tags, uv exception, embedded inventory, unseeded
targets, post-pip state, final inventory, and offline `pip check`. Two evidence
boundaries remain blocking:

- the helper imports pip before any retained pre-import check binds the approved
  hash to the exact executable snapshot; read-only mounting is also unproven;
- the claimed phase-3 normalization failure was overwritten rather than
  retained, so retry preservation cannot be audited.

R9-X2E may reuse verified D3 artifacts entirely offline, but must use read-only
source mounting, private verified execution snapshots, unique non-overwriting
attempt records, and a machine-readable inventory manifest with exact framing.

## R9-X2E D4 handoff

Engineer 2 retained the immutable evidence root
`D:\lodstar\r9_tooling_bootstrap_20260803_d4`. D1-D3 retained their
Auditor-defined fingerprints. D4 contains 73 files and five directories; its
payload digest is `f5fc6ee4a78f632c77a2089aa6313b67cd8d81e0a046c07401f1549e9a4084e6`.
The machine-readable inventory manifest is 13,691 bytes with SHA-256
`113c7bb2e2aa67ccdc0a37aae11770181b14a0e2d5ac8eee20c83f8118aca5b5`.

The handoff records `/d3ro` mounted read-only, a rejected write with errno 30,
and unchanged D3 fingerprints. Attempt `0001` is retained as an honest harness
failure; attempt `0002` is the authoritative success. The pip snapshot is mode
0400 and retains the same device, inode, size, and approved SHA-256 before and
after execution; loaded pip origins resolve inside that private snapshot.
Resolver and verifier inventories progress from empty to exactly pip 25.0, then
to the exact accepted 15-distribution closure, with all three `pip check` runs
passing. Artifact identities equal D3 and no network, repository, Tamia, torch,
bundle, global-install, or production mutation occurred.

R9-V0C is now the active independent audit. R9-C1 remains blocked until Auditor
2 explicitly accepts D4 and states that the tooling lock and implementation may
resume.

## R10-X2 publication

**Accepted.** `origin/main` moved by strict fast-forward from exact `4bf0fd8` to
accepted `9d90ef6`; remote post-state equals the audited commit. No force,
merge, rebase, new commit, file edit, Tamia, environment, scheduler, or artifact
action occurred. The local main checkout remains at `c6ef2df`; it is six commits
behind `9d90ef6`, not two. This stale local pointer is nonblocking and was
correctly left untouched.

## R10-X3 Tamia propagation

**Accepted.** The existing Tamia checkout advanced by strict fast-forward from
exact `4bf0fd8` to published `9d90ef6`. The sole tracked modification retained
the same blob/SHA-256, all 26 paths present at this work item's preflight were
preserved, and the new launcher matched its committed blob and passed `bash -n`.
No job, test submission, environment, placeholder, registry, result, report, or
scientific artifact changed. The earlier durable preflight recorded 28 untracked
paths; this session began with 26, an inter-session state difference not caused
by R10-X3. GAP-2 is closed on-cluster. Census execution remains blocked on the
ED-36 environment/equivalence chain and separate authority.

**Cancelled 2026-08-02 by the Researcher.** Do not route this presentation
packet. The active critical path is Auditor 2 R6-V5C plus Auditor 1 T1.2-V1 in
parallel, followed—only if both accept—by bounded R7/T1.2 integration and then
Lab Assistant environment/preflight and A3→A7→A8→seed-0 A9 execution.
