# Project State

## 2026-08-04 R9 tip is unaudited — inherited completion claim rejected

The inherited claim that "R9-V4 and everything before it are complete" is **not
supported by repository evidence**. Two commits exist past the last ledger
update: `1ed3ad9` (R9-C4) and `82b028e` (the repair commit mislabelled `R9-V4`).
An audit worktree exists for `1ed3ad9` but **none for `82b028e`**, and `82b028e`
changed production validation code and the acquisition schema after that audit.
The R9 branch tip therefore has zero independent verification.

Scope authority is intact: `4bf0fd8..82b028e` touches exactly the seven
authorized paths. The failure is verification, not scope.

R9-V5 is the active acceptance gate. Target capture, bundle construction,
production environment mutation, equivalence, certification, and every
experiment remain blocked. `origin/main` stays at `9d90ef6`; the R9 branch is a
divergent, path-disjoint sibling requiring later integration.

## 2026-08-03 R9-C4 execution-host note

The reported WSL CLI blocker is nonblocking. Docker Desktop's existing Linux
engine is operational and the required Python 3.11 Bookworm image is already
local. Engineer 2 can resume R9-C4 and obtain real kernel namespace evidence in
an offline `--network none` container. No Tamia or acquisition authority follows.

## 2026-08-03 R9-D4 accepted state

R9-D4 is accepted. R9-C4 is now the active Engineer 2 lane with exactly seven
cumulative paths, adding only the acquisition-manifest v1 schema to the prior
six. The schema change is a pre-first-write clarification. No eighth path,
external acquisition, real bundle/environment, Tamia action, publication, or
experiment is authorized. A future R9-C5 export update is pre-recorded for the
moment real derived wheels exist. R9-V3 remains the acceptance gate and must
audit the exact successor in non-stale state with positive Linux namespace
evidence.

## 2026-08-03 R9-A3/R9-D4 state

R9-A3 is complete. Option 2 governs: PEP 508 ranges constrain compatibility,
the exact tooling lock selects bytes, the export authorizes the retained sdist,
and only a complete derived record authorizes the output wheel. Kernel network
namespace isolation is mandatory and fails closed. Exact inspection of the
strict acquisition-manifest v1 schema at `490ae73e...` proves it cannot encode
the required trust chain, so the prior six-path assumption is superseded.
R9-D4 is active to authorize only
`schemas/environment_acquisition_manifest/v1.schema.json` as path seven. R9-C4,
R9-V3, target capture, bundle/environment construction, equivalence, and all
experiments remain blocked until their ordered gates pass.

Last reconciled: 2026-07-29  
Audit: `AUDIT-01`  
Repository: `D:\qwen-sae-interp`  
Revision inspected: `main` at `3ac9e23` (`origin/main`)

## Completion-campaign update

- `R0-CI-LINT`: **Accepted** on 2026-07-28.
- Engineer scope was confined to `scripts/characterize_lite.py` and
  `scripts/multilingual_rerun.py`; the changes are behavior-neutral.
- Current exact CI Ruff command and `git diff --check` are green.
- Independent clean-environment evidence remains 603 passed, 3 deselected;
  `uv lock --check` is green.
- Architect review found no genuine ambiguity in A-001 and issued no ED
  amendment. R3 has now implemented and verified the local WP8
  judge/capability producer under the existing blueprint.
- Auditor and Architect are on-demand roles, not automatic stages.
- `Persistent Interlab Lab Assistant` is the bounded TamIA execution and
  evidence-acquisition role. It may execute only fully specified procedures;
  scientific scope and interpretation remain with `HUMAN / RESEARCHER`,
  implementation with `ENGINEER`, architecture with `ARCHITECT`, and
  independent acceptance with `AUDITOR`.
- `R1-CONFIG-LIFECYCLE`: **Accepted** on 2026-07-28. All implemented jobs
  now map readable invalid configs to exit 3 and exactly one failed A10
  without entering heavy work or changing valid-run lineage.
- `R2-DOC-CONTRACT-DRIFT`: **Accepted** on 2026-07-28. The five authorized
  public/canonical descriptions now match the repository without changing
  executable behavior or scientific contracts.
- `R3-WP8-JUDGE-PRODUCER`: **Accepted for local implementation scope** on
  2026-07-29 after R3-C1/R3-C2 corrections and R3-V2 independent
  verification. Live Lodestar and production A9/A9′ remain unverified under
  ED-19.
- `R4-A002-CHECKPOINT-SCOPE-PACKET`: **Accepted / resolved by ED-35**.
  The authoritative WP2 population is five checkpoints. Four have A5/A6;
  recovered L28×16 `hm03l7yz` still needs its standard A5/A6 pipeline.
- `R4-V1-L28X16-COMPLETION-AUDIT`: **Inconclusive — environment
  limitation**. History identifies candidate `hm03l7yz` and expected final
  path, but W&B was unauthenticated and Tamia rejected SSH.
- `R4-X1-L28X16-AUTHORITATIVE-ACCESS`: **Accepted / closed**. Authoritative
  Tamia evidence confirms `hm03l7yz/final_400001024` as a completed,
  baseline-compatible L28×16 checkpoint.
- `R5-X1-HM03L7YZ-A5-BACKFILL`: **Accepted** at commit `04e88dc`. A5
  `3e6fdcb1187a` and completed A10 `ada8ac14bd48` validate.
- `R5-C1-CERTIFY-LAUNCHER-WHOLE-NODE`: **Accepted** at commit `65ff603`.
  The one-file correction requests Tamia's proven `h100:4` / `mem=0`
  allocation and preserves all launcher behavior.
- `R5-X2-HM03L7YZ-A6-CERTIFICATION`: its first runtime attempt, job `387413`,
  received the correct whole-node allocation but exited 127 at
  `module purge`; `certify.py` never ran and no A6/A10 was created.
- `R5-C2-CERTIFY-LAUNCHER-BASH-WRAP`: **Accepted** at commit `70b7ed8`.
  R5-V1 proved the exact captured payload through Tamia `/bin/sh` into login
  Bash and reached the harmless Python stub.
- `R5-V1-CERTIFY-WRAP-TAMIA-PREFLIGHT`: **Accepted** with zero scheduler or
  artifact mutation.
- `R5-X2-HM03L7YZ-A6-CERTIFICATION`: now blocked by the missing canonical
  CUDA venv, stale cluster requirements export, and unavailable locked
  packages in the Alliance wheelhouse.
- `R6-A004-CLUSTER-ENV-REBUILD-POLICY`: **closed by ED-36**. Production
  remains on TransformerLens 3.2.1; a retained hash-verified external offline
  bundle is sanctioned; exact 3.2.1/3.4.0 equivalence is required before
  R5-X2.
- `ED-36-LOCAL-REPOSITORY-PORTION`: **Needs correction**.
- `R6-V1-ED36-LOCAL-VERIFICATION`: **Needs correction**. The export and
  schemas passed, but bootstrap, marker, bundle-boundary, installed-closure,
  dirty-source, A10 lifecycle, and equivalence-ref probes failed.
- `R6-C1-ED36-BUNDLE-VALIDATOR`: Engineer complete; combined independent
  re-verification pending. Reported full suite is 659 passed, 3 deselected,
  with exact CI Ruff, lock, Bash syntax, and diff checks green.
- `R6-C2-ED36-CERT-LANE-LIFECYCLE`: Engineer complete; combined independent
  re-verification pending. Reported full suite is 676 passed, 3 deselected.
- `R6-V2-ED36-COMBINED-REVERIFICATION`: **Needs correction**. Core lifecycle
  and most validator attacks passed; six semantic closure defects remain.
- `R6-C3-ED36-SEMANTIC-CLOSURE`: **Needs correction after R6-V3**.
- `R6-V3-ED36-FINAL-LOCAL-REVERIFICATION`: **Needs correction** with seven
  failing tests across creator/admission/module/schema/A10 addressability.
- `R6-C4-ED36-CREATOR-ADMISSION-HARDENING`: Engineer report addresses its
  audit findings; full independent verification remains.
- `R6-C5-ED36-ALLIANCE-CUDA-IDENTITY`: Engineer complete; final verification
  pending. Production-shaped focused probes passed.
- `R6-V4-ED36-FINAL-ACCEPTANCE`: **Needs correction** on creator TOCTOU and
  exact retained Alliance torch anchoring.
- `R6-C6-ED36-IMMUTABLE-CREATOR-TORCH-ANCHOR`: Engineer complete; direct
  creator-path-swap and exact-torch probes passed, but normal pytest/Bash
  evidence was host-blocked.
- `R6-V5A-ED36-REMAINDER-ACCEPTANCE`: **Needs correction**. Focused ED-36
  returned 61 passed/7 failed and full pytest 702 passed/7 failed/3 deselected.
  The seven failures are bounded to two over-specific diagnostic expectations
  and five stale install-record fixtures; no interface or production drift was
  found. Exact-byte execution remains unverified.
- `R6-A006-EXACT-BYTE-EXECUTION-TEST-CONTRACT`: **Accepted; no ED amendment**.
  Architect confirmed a real two-read child gap and fixed the single-buffer,
  parent-rehash, rollback, and named real-subprocess regression contract.
- `R6-C7-ED36-FINAL-LOCAL-CLOSURE`: **Needs correction after Orchestrator
  review** despite 714 passed/3 deselected. The core single-buffer/private-copy
  and parent-rehash design is present, but production exports a test-only
  snapshot-path environment variable and the named test wraps
  `bundle.subprocess.run`, contrary to A-006.
- `R6-C8-ED36-REMOVE-CREATOR-TEST-SEAM`: Engineer complete. The production
  environment seam and test subprocess wrapper are absent; environment-bundle
  tests pass 73/73 and full pytest passes 714/3 deselected.
- `R6-V5B-ED36-FINAL-LOCAL-VERIFICATION`: **Accepted for the exact local
  candidate**. Hash-bound source/test identity, named boundary test, all seven
  former failures, torch, lifecycle, full 714-test suite, and static checks
  passed without state drift.
- A competing Auditor report is superseded: it repeated the pre-C7 seven-failure
  signature and old routing without binding to file hashes. Current repository
  hashes exactly match the accepted Auditor report.
- `R6-S1-ED36-CANDIDATE-STABILIZATION`: Engineer complete at local commit
  `c6ef2df5bb38791a26e4e9490243f327dc6aeb85`, parent `70b7ed8`. Exactly
  46 authorized paths committed, accepted core hashes preserved, tracked tree
  clean, and excluded T1.2/probe/SSH paths untouched.
- `R6-V5C-STABILIZED-COMMIT-VERIFICATION`: **Accepted reproducible local
  revision** at `c6ef2df`. Clean detached import, exact manifest/hashes, named,
  environment, full 714-test suite, Ruff, lock, Bash, and diff evidence passed.
- `R8-I1-R7-LAUNCHER-INTEGRATION`: active with Engineer 2 in a new isolated
  integration worktree from `c6ef2df`; accepted R7 launcher fixes are integrated
  while T1.2-V1 proceeds independently with Auditor 1.
- `R7-C1-LAUNCHER-FIX-PROPAGATION`: **Accepted in isolation** at commit
  `b7aad6a2e25a45c5b4fab48951b5bfd92a47ae53` on local branch
  `r7-launcher-propagation`. Integration is parked until R6 stabilization;
  the accepted R2 steer-header correction must be preserved during merge.
- `T1.2-C1-PROTOCOL-PACKET-CORRECTION`: isolated commit `c4f0da7` now contains
  the cheese A2, battery v1.1.0/golden, census, characterize, validate, three
  steer configs, and protocol. Targeted suites passed, but full pytest and one
  characterize test remain unverified. One characterize comment still assigns
  A8 to the wrong producer, approved `n_docs: 20000` is mislabeled as awaiting
  confirmation, and R6 gate prose is stale after A-006 acceptance.
- `T1.2-C2-PACKET-FACTUAL-GATE-CORRECTION`: commit `e92174a` corrected A7/A8
  ownership and `n_docs`; four YAML objects stayed equal, characterize passed
  13/13, and full pytest passed 603/3 deselected. Its explicit `C7→V5B` gate
  became stale when parallel R6 review inserted C8.
- `T1.2-C3-STABLE-R6-GATE-WORDING`: Engineer complete at clean isolated commit
  `e9ad361`. Five files use stable R6/ED-36 acceptance wording; four YAML
  objects remain semantically identical; focused tests and checks passed.
- `T1.2-V1-PROTOCOL-PACKET-VERIFICATION`: **Accepted for isolated preparation
  packet** at `e9ad361`. Exact 14-file authority/golden/config scope and all
  focused/full tests passed. The report’s R6-V5C blocker line is concurrency-
  stale; V5C is already accepted.
- `R8-I2-T12-PACKET-INTEGRATION`: active with Engineer 1 in a separate branch
  from `c6ef2df`, parallel to Engineer 2’s R7 integration. Zero A3/A7/A8 hashes
  remain placeholders; integration alone does not authorize A9.
- `P0-PI-PRESENTATION-EVIDENCE-PACKET`: cancelled by the Researcher on
  2026-08-02; no presentation task should displace ablation critical-path work.

## Current conclusion

The inherited claim that WP0-WP8 are complete is false. Interlab has a
substantial and locally green implementation, but the production evidence
chain stops at A6 certification. WP8's required local producer now exists,
but live Lodestar remains paused and no production A9/A9′ evidence exists.
WP9 is **not safe to start as the next authorized package**.

WP9 is also not wholly absent: the canary comparator, reference contract,
nightly test, and battery/tokenization snapshots already exist and pass their
local mechanism tests. The real cheese reference is absent and the real
nightly tests skip explicitly, as ED-23 permits. No additional WP9
implementation should be inferred from that researcher-owned evidence gap.

## Verified repository state

- Clean isolated `uv sync --extra dev`: success.
- Current Engineer default suite: **628 passed, 3 deselected, 40 warnings**.
- Nightly lane at AUDIT-01: **3 explicit skips, 603 deselected**.
- Exact CI Ruff command: **green in the current dirty working tree**.
- Lock check and diff whitespace check: green.
- Minimal public workflow: isolated `sync_registry` CLI completed with exit 0
  and a valid RunCard.
- Invalid-config workflow: all ten implemented jobs return exit 3 and write
  exactly one failed RunCard without domain writes.
- Registry: 17 JSON artifacts; all schema-valid, self-hash-valid, and
  filename-consistent.
- Registry coverage: A1=1, A3=1, A5=5, A6=4, A10=6;
  A4/A7/A8/A9/A11/A12=0.
- The four production A6 run IDs have no corresponding A10 RunCard locally.
- Production A6 verdicts use explicitly placeholder band version 1.
- `reports/` has 32 local files, `results/` 127, and
  `project_management/` is intentionally local-only and ignored by researcher
  decision A-003. Tracking policy for `reports/` and curated `results/`
  remains unresolved under A-005.

## Blocking state

1. WP6's required cheese dose-response pilot is absent; no A11 exists.
2. There is no production A7/A8/A9/A11/A12 chain. Some prerequisites are
   researcher- or environment-owned, but their absence still prevents
   package acceptance.
3. Four production A6 artifacts lack local RunCards, so the only production
   certification evidence has incomplete operational lineage.
4. ED-35 resolves WP2's population to five. Five A5 and four A6 artifacts
   exist. ED-36 settles the environment policy, but the local implementation
   needs R6-C1 plus a later lifecycle correction and re-verification before a
   stable commit or external bundle/install/equivalence evidence.

## Classification summary

- **Implementation defects:** launcher resource and shell-boundary defects
  are accepted as corrected. `slurm/requirements.cluster.txt` is a stale
  generated build input, but it must not be regenerated/used until A-004
  settles the supported acquisition and fidelity policy.
- **Verification gaps:** real-Qwen identity lane; production A4/A7/A8/A9/A11
  execution; sync/launcher/failure-path operations.
- **Architectural ambiguity:** none active for the cluster rebuild. A-004 is
  closed by ED-36; A-001 and A-002 remain closed. A-003 is closed by the
  researcher: `project_management/` is canonical and local-only. A-005 retains
  the separate report/result tracking question.
- **Documentation defects:** ED-25/ED-26 decision-ledger continuity and
  unresolved report/result tracking governance remains; management tracking
  is intentionally local-only under A-003. R2 closed the
  five bounded factual drifts in README, steer/import comments, evaluation
  status, and the golden-test table.
- **Researcher actions:** scientific approval of T1.2 prompts, sampling,
  positions, characterize size, judge mode, band calibration, battery
  completion, A12/claim authoring, and the canary reference. Checkpoint-scope
  reconciliation is closed by ED-35.
- **Lab Assistant actions after preflight:** external ED-36 bundle/venv and
  equivalence evidence, fifth certification, cluster A10 recovery, real-Qwen
  tests, and approved characterize/steer/census/validate runs. Identifying this
  owner does not make any blocked procedure executable.
- **Environment limitations:** no real Qwen path, no cheese reference, no
  Tamia/Lodestar production environment; sandbox temp/cache ACL errors.
- **Intentional pauses:** SS3 training job/package under ED-18; Lodestar
  integration under ED-19; SS13 circuit tracing.

See `REPOSITORY_AUDIT.md`, `COMPLETION_LEDGER.md`, and
`AMBIGUITY_REGISTER.md` for evidence and classifications.

## 2026-08-02 integration snapshot

- R6 local revision `c6ef2df` is reproducibly accepted.
- T1.2 packet integration `7597af0` is accepted from a byte-faithful checkout:
  environment 73 and full 714 passed/3 deselected.
- R7 launcher integration candidate `a65dfb4` contains only the four launchers
  and preserves the accepted R2 steer-header correction.
- Active local task is the exact 18-path R7+T1.2 combined integration. External
  ED-36 evidence, Lab Assistant preflight, A3/A7/A8 production, placeholder
  replacement, and seed-0 A9 remain downstream and unauthorized until that
  combined revision is accepted.

## Combined candidate

Engineer-produced combined revision `4bf0fd8` now contains the exact accepted
R6 + R7 + T1.2 union and is locally green. It remains **candidate-only** until
independent R8-V1 acceptance. No push or cluster execution is authorized from
the Engineer report alone.

Independent Auditor 2 acceptance now closes the combined local integration at
exact `4bf0fd8`. The next gate is explicit Researcher authorization to publish
that commit. Until then, `origin/main` and Tamia remain behind the accepted
local revision and no cluster experiment should begin from an ad hoc tree.

`origin/main` now equals independently accepted `4bf0fd8`. Local `main` remains
at `c6ef2df` and is four commits behind; this does not affect the published
revision. Tamia access remains unauthorized. The next proposed action is a
host-only Lab Assistant preflight that may safely fast-forward the cluster
checkout but may not mutate environments, submit jobs, or produce science.

Tamia preflight found no ED-36 bundle and no usable production venv. The cluster
repo reached exact `4bf0fd8`, but a pre-existing tracked modification remains;
that checkout is not clean evidence. No bundle builder exists in the repository:
only validation, venv creation, and install-recording consumers are implemented.
R9-A1 is therefore active with the Architect before any construction authority.

R9-A1 is now closed without an ED amendment: a checked-in deterministic builder
is required. Active implementation is R9-C1, combining multi-phase target/
runtime/torch/finalization construction, tooling and derived-wheel closure,
setup hardening, and the missing mandatory pip check. In parallel, T1.2 staging
is complete and a disjoint statistics-prose correction plus Researcher census
decisions are ready. No bundle, environment, equivalence, or experiment is yet
authorized.

R9-D1 is closed. Universal ABI-none/platform-any wheels may carry compressed
Python tags, while uv 0.8.22 is the sole explicit Linux-x86_64 platform
exception. Engineer 2 may perform one corrected evidence-only rebootstrap with
exact runtime overlaps, direct pip/uv provenance, and virtualenv embedded-seed
inspection. R9-C1 remains blocked until Auditor 2 accepts that replacement
evidence. Bundle construction, Tamia environment mutation, equivalence,
certification, and T1.2 execution remain unauthorized.

R10-X1 recovered a successful 29m15s census and confirmed the exact fast
tokenizer with parallelism unenabled, fully specifying a one-hour/eight-CPU
launcher under the ruled whole-node H100 envelope. R10-C2 may now proceed on
the accepted T1.2 worktree. Auditor 2 separately confirmed that the first R9
tooling evidence root is incomplete but unchanged; Engineer 2's corrected
R9-X2B evidence retry remains active before R9-C1 can resume.

R9-X2B then stopped at its required offline preflight: virtualenv 20.26.0
contains setuptools seeds 68.0.0 and 69.5.1, not 83.0.0. Current code uses
`--no-download` but not `--no-seed`, so those embedded versions are operational,
not merely inert archive content. R9-A2 is now with the Architect for a narrow
seed-isolation/bootstrap ruling. No rebootstrap or repository mutation occurred.

In the independent T1.2 lane, Engineer 1 completed the missing census launcher
at `9d90ef6` atop the accepted statistics commit. The one-file change has strong
local stub/focused evidence and now awaits Auditor 1 acceptance; it does not
authorize integration, publication, or cluster execution.

Both R9-A2 Architect reviews now converge on the exact same resolution: keep
the pinned virtualenv creator, force unseeded/network-closed creation, prove an
empty venv, and bootstrap approved pip 25.0 from verified offline bytes. No ED
or schema change is needed. R9-D2 Human ratification is the sole immediate R9
blocker because this permits fully inventoried embedded seeds to remain inert,
narrowing the literal R9-D1 wording without allowing them to execute.

R9-D2 is now accepted. It additionally forbids ensurepip, requires an exact
post-bootstrap inventory of only pip 25.0, and fixes wheel at 0.45.0. Engineer 2
may run the corrected evidence-only R9-X2C bootstrap. R9-C1 still waits for the
replacement evidence and independent R9-V0B acceptance; no external production
action is authorized.

R10-V2 independently accepted census-launcher commit `9d90ef6`; it is ready for
later integration but grants no execution authority. R9-X2C retained a
correct-looking 15-artifact closure, yet its resolver implicitly used ensurepip
and its empty-state proof deleted script paths first. That root is preserved as
failed procedural evidence. R9-X2D is the active correction; R9-V0B and R9-C1
remain blocked.

R9-X2D has now produced the corrected immutable D3 tooling-evidence root with
the exact closure and clean unseeded bootstrap sequence. Auditor 2's R9-V0B
evidence acceptance is active. R9-C1 remains blocked until that verdict; no
bundle, environment, or experiment authority follows from the Engineer report.

`origin/main` now equals independently accepted `9d90ef6`, publishing both the
statistics correction and census launcher by strict fast-forward. The stale
local main checkout remains at `c6ef2df`—six commits behind—and was not mutated.
Tamia still requires separate authority to advance from `4bf0fd8`; R9-X2D
continues independently.

Tamia has now safely advanced to exact `9d90ef6`, preserving its dirty tracked
file and all paths present at preflight. The accepted census launcher is present
and syntax-valid, so the missing-launcher gap is closed locally, remotely, and
on-cluster. No experiment is authorized or runnable yet: ED-36 tooling evidence,
builder, environment, equivalence, and lineage artifacts remain on the critical
path.

R9-V0B rejected D3 on two narrow evidence boundaries despite accepting the
artifact closure in substance: pip was imported before a retained executed-byte
binding, and a failed phase-3 attempt was overwritten. R9-X2E is producing an
offline D4 root with read-only D3 inputs, verified private execution snapshots,
non-overwriting attempt logs, and explicit digest framing. R9-C1 remains blocked.

R9-X2E has now handed off immutable D4 at
`D:\lodstar\r9_tooling_bootstrap_20260803_d4`. It reports read-only D3 mounting,
a failed write probe, stable private pip snapshot identity before and after
execution, distinct retained attempts, exact D3 artifact equality, clean
empty-to-pip25-to-15-package inventories, and successful pip checks. Auditor 2's
R9-V0C is active. R9-C1, bundle construction, production environment work, and
all scientific execution remain blocked until independent acceptance.

R9-V0C has independently accepted D4. The tooling evidence may now author the
checked-in tooling lock, and Engineer 2 may resume the bounded local R9-C1
implementation. External bundle construction, Tamia environment mutation,
equivalence, and scientific execution remain unauthorized and blocked on the
implementation/audit sequence. For the immediate PI meeting, existing measured
multilingual, characterize-lite, and exploratory steering evidence is usable;
the new T1.2 ablation remains preregistered and pending rather than a result.

Engineer 2 has now produced stable R9-C1 candidate
`c847e075f87a2f5cb871c59d8e94d06c9ec00280` with exactly the five authorized
paths and reported 723-test/full static-gate success. Auditor 2's R9-V1 is the
active acceptance gate. Separately, Lodestar is available locally at
`D:\lodstar`; a delegated read-only inspection is mapping its actual judge and
adapter interfaces to Interlab's ED-19 Stage-2 contract. Neither lane authorizes
external bundle construction, production environment mutation, or experiments.

The Lodestar inspection is complete. Lodestar's Anthropic judge is real, but it
has no Interlab runtime bridge and no capability/perplexity producer. The two
systems also disagree on concept/config input, repeated-score representation,
instrument provenance, raw-run addressing, A12 admission, and dependency/process
topology. R11-A1 is therefore an Architect lane, followed by Human authorization
for A12, credentials, budget, retention, and any paid call. This does not delay
the independent R9-V1 audit, but ED-19 Stage 2 remains blocked.

R9-V1 rejected builder candidate `c847e075...`. Exact scope, D4 lock identity,
and broad regressions passed, but multiple target/provenance, archive/build,
torch, staging/finalization, pip-snapshot, revision, atomic-publication,
TransformerLens, rollback, and direct-test boundaries remain incomplete. R9-C2
is the active same-five-path correction; R9-V2 will independently re-audit it.
No integration, publication, real target capture, bundle construction,
production environment, equivalence, or experiment is authorized. R11-A1 may
continue in parallel because it touches the later ED-19 judging lane.

R11-A1 is now complete. Both Architects select a pinned, one-shot, off-cluster
Lodestar judgment environment with a content-addressed blinded file boundary;
Interlab owns capability measurement and the atomic A9′ join. ED-37 and Human
ratification are required. The conservative synthesis uses new v2 judge/A9/A11
schemas, disables production response caching across repeats, retains native
instrument identity plus a manifest-hash prompt_version under unchanged A12 v1,
and requires an immutable Lodestar 0.2.0 source/package identity. R11-D1 is the
active Human decision; offline implementation, credentials, paid calls, and
production remain unauthorized until their respective gates.

R11-D1 is ratified. A narrower R11-D1A decision is now active because the
historical judge temperature was zero: α≥0.91 is a determinism/repeat-agreement
measurement, not independent judge reliability. Presentation/report wording must
be corrected urgently. The recommended path keeps temperature zero for
sufficiency comparability, reconstructs a caveated retrospective instrument
manifest for later A12 review, and adds coherence only as a reported non-gating
rubric. R9-C2 continues independently; no paid or production Lodestar action is
authorized.

R9-C2 produced clean intermediate commit `ea65a871...` but correctly retained a
Needs-correction verdict. Several fail-closed/test-matrix boundaries remain, and
the setup script still permits a stub-only expected-revision fallback. Removing
that exception while keeping the historical shell test green requires a narrow
sixth-path authorization for `tests/test_slurm_setup_env.py`. R9-D3 is active;
do not route the intermediate commit to Auditor 2 or use it externally.

R9-D3 is now accepted. Engineer 2 may perform R9-C3 in exactly six paths from
`ea65a871...`. The all-zero revision may not migrate into a success test; tests
must pass the fixture's actual HEAD through the production authority interface.
R9-V2 will use a fresh detached exact-SHA worktree, so the stale/conflicted local
main checkout need not and must not be synchronized as an audit prerequisite.

R9-C3 has produced stable candidate `490ae73e...` with reported strict setup
authority, expanded network/finalization/no-clobber/TL/rollback coverage, 23
builder tests, 9 setup tests, and 749 full tests. R9-V2 is active and must use a
fresh detached exact-SHA worktree. The candidate remains local and grants no
integration, publication, real bundle/environment, equivalence, or experiment.

R9-V2 rejected `490ae73e...`. Setup authority, D4 identity, broad suites and a
real Windows junction probe passed, but derived-wheel hash trust is inconsistent,
network isolation fails open, and cross-binding/no-clobber/cleanup/pip/TL plus
direct coverage remain incomplete. R9-A3 is a narrow Architect gate on ranged
PEP 517 requirements versus exact locked artifacts; R9-C4 follows in the same
six paths. All external ED-36 and experiment work remains blocked.
