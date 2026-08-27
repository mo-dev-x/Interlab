# Ambiguity Register

Audit: `AUDIT-01`

Only genuine unresolved choices are recorded here. Missing code, missing
evidence, intentional pauses, and researcher actions are not relabeled as
architecture ambiguity.

## A-001 — WP8 judge/capability composition

Status: **closed 2026-07-28; not a genuine ambiguity**  
Decision source: persistent Architect  
ED amendment: **none**

The Architect found the existing blueprint sufficient. R3 subsequently
implemented and independently verified the judge/schema/wrapper/adapter and
capability-production surface without an ED amendment. No package edge,
schema, or ED may be changed on the theory that A-001 authorized it.

## A-002 — WP2 “all 6+ checkpoints” versus assembled checkpoint evidence

Status: **closed 2026-07-29 by ED-35**  
Decision source: Human / Researcher  
Architect required: **no; ruling is recorded directly in the blueprint**

ED-35 establishes the authoritative population of distinct, eligible,
existing final checkpoints as `d1bgp5v5`, `rwu04lpb`, `zf2o13m2`,
`o1cx1dow`, and recovered L28×16 `hm03l7yz`. The literal “6+” was a
pre-blueprint estimate and is no longer an authoritative count-to-hit. The
frozen architecture's “all existing checkpoints” requirement remains
satisfied and unchanged.

Recorded dispositions:

- `a520ytu6`: duplicate/intermediate resume source of final `o1cx1dow`;
- `de575ae6/a0g2os3u/final_200003584`: retired/out of scope because the
  Montreal/poutine research direction was dropped;
- W&B run IDs: telemetry rather than checkpoint artifacts;
- L28×16: `hm03l7yz`, confirmed completed and in scope by authoritative
  Tamia evidence under R4-X1.

R4-V1 is a verification gap, not a remaining ambiguity. A positive result
records WP2 as partial; a negative authoritative result records L28×16 as
never produced and permits WP2 population closure. Inconclusive external
access leaves WP2 open.

R4-V1 returned Inconclusive. Repository history linked candidate
`hm03l7yz` to `results/sae_checkpoints/hm03l7yz/final_400001024` in
parameter-sweep survey/steering launchers, but does not prove completion.
The training sweep used `WANDB_MODE=offline`; W&B was unauthenticated and
Tamia SSH was denied. R4-X1 subsequently obtained authoritative Tamia
evidence and confirmed the checkpoint. The earlier unknown status was an
access limitation, not an artifact disposition. A-002 remains closed and no
Architect action is required.

## A-003 — Management path and tracking convention

Status: **closed 2026-07-31 by Human / Researcher**  
Owner: Researcher/repository owner  
ED amendment: **none**

`project_management/` (underscore) is the canonical durable campaign-memory
path and is intentionally local-only through `.gitignore`; it must not be
pushed. The stale `project-management/` directory was consolidated and
removed manually. Its six unique files (`DECISION_INDEX.md`,
`RESEARCHER_QUEUE.md`, and four `SESSION_BOOTSTRAPS/*.md`) were preserved in
the canonical directory before removal. Current ledgers/plans were not
overwritten by the stale copies.

This ruling concerns project-management memory only. It does not decide the
blueprint's separate tracking requirements for scientific reports/results.

## A-005 — Scientific report and curated-result tracking

Status: **open; repository-governance ambiguity**  
Owner: Researcher/repository owner

The A-003 decision intentionally made only `project_management/` local-only.
Whether `reports/` and curated `results/` are committed, retained privately,
or intentionally ignored remains unresolved and must be decided before the
release-governance audit.

## A-004 — Cluster environment rebuild source and fidelity baseline

Status: **closed 2026-07-30 by ED-36**  
Decision source: persistent Architect  
ED amendment: **ED-36**

ED-36 closes the package-source ruling and the local provenance contract.
The dependency truth remains the single committed `pyproject.toml` /
`uv.lock` stack, with direct `transformer-lens==3.2.1`, and the checked-in
cluster requirements file is now the exact hash-bearing
`uv export --locked --no-dev --no-emit-project --no-emit-package torch`
projection of that lock.

Production cluster installation remains offline-only. The sanctioned source
for packages unavailable from the Alliance wheelhouse is an external
transferred acquisition bundle that is validated against the committed
`pyproject.toml`, `uv.lock`, and `slurm/requirements.cluster.txt` hashes
before any venv mutation. The bundle is retained as external acquisition
evidence, not vendored into the repository, and direct Tamia network
installation remains forbidden.

The later `transformer_lens_equivalence_report` path is wired but not
fabricated. `R5-X2` remains blocked pending the separate measured real-Qwen
equivalence evidence ED-36 still requires.

## A-006 — Deterministic exact-byte execution regression boundary

Status: **closed 2026-08-01 by Architect; no ED amendment**  
Owner: Architect  
ED amendment: **not presumed**

The required invariant is settled: the creator bytes whose approved hash is
reported must be exactly the bytes executed; any change after verification
must abort; replacement module content must not execute.

What remains underspecified is the smallest deterministic repository-local
testability seam that can establish this invariant without asking the Auditor
to design or modify a synchronized boundary test. The Architect must decide:

- whether an existing production boundary can be observed deterministically or
  a narrow test-only synchronization seam is required;
- whether the test alone is sufficient or a minimal production correction is
  required first;
- the exact allowed files/interfaces and proof obligations for the Engineer;
- the committed named test the Auditor will later run unchanged.

R6-V5A confirmed that the repository has no existing named test that closes
this boundary: the current replacement regression changes the original
manifest path while mocking subprocess execution and therefore does not prove
unchanged snapshot-byte execution after child verification.

The test must use only disposable files under the repository test temporary
directory, perform no network/credential/external-system access, and remove all
temporary state. This is implementation/test design, not a change to ED-36's
scientific or provenance policy.

### Architect decision

The child currently reads the snapshot once for hashing and then lets zipimport
read the mutable path again for execution. A production correction is required:
verification and execution must derive from one in-memory byte buffer (or a
child-private extraction of that verified buffer), with no second read of the
parent-visible snapshot. After the child returns and before created-venv
validation, the parent must re-hash the snapshot; mismatch raises an
`EnvironmentBundleError` containing expected and actual hashes and rolls back.

No production synchronization hook is permitted. The deterministic seam is a
test-authored creator wheel whose approved module records token A and replaces
the snapshot with a substitute containing token B. The real child subprocess
runs: A must be recorded, B must never execute, the mismatch must abort, and
staging/target/snapshot cleanup plus unrelated-sentinel preservation must hold.
The committed test name is
`test_create_virtualenv_executes_only_verified_creator_bytes_and_aborts_on_post_verification_replacement`.

Allowed production scope is only `create_virtualenv`, its child source string,
and private helpers in `interplab/core/environment_bundle.py`; test scope is
`tests/test_environment_bundle.py`. Return keys, manifests, schemas,
dependencies, lock, blueprint, and registry are frozen.

## Classified elsewhere, not ambiguities

- Missing `jobs.judge`/schema/wrapper/adapter: implementation defect closed
  by accepted local work item R3; A-001 remains closed.
- Invalid config causing exit 1/no RunCard: implementation defect closed by
  accepted work item R1.
- Missing A7/A8/A9/A11 production artifacts: verification/downstream gap.
- Missing certify RunCards: artifact-lineage/external recovery gap.
- Placeholder band calibration: researcher action.
- Missing cheese reference: researcher action under ED-23.
- Missing train package/job: intentional ED-18 pause.
- Lodestar adapter pause: intentional ED-19 pause and a separate Lodestar
  dependency decision; A-001 is closed.
- Absent ED-25 remains a documentation defect; R2 corrected the stale ED-26/
  ED-33 golden-limit table without creating a new decision.
