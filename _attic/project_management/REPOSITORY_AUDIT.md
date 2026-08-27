# Repository Audit — AUDIT-01

Date: 2026-07-28  
Repository: `D:\qwen-sae-interp`  
Revision: `3ac9e23` plus inherited modifications to `.gitignore`,
`scripts/characterize_lite.py`, and `scripts/multilingual_rerun.py`  
Production code changed by audit: **none**

## Scope and inventory

The audit inventoried 440 repository files after excluding VCS internals,
virtual environments, caches, and the audit outputs themselves. The complete
path/size/time inventory is in `logs/AUDIT-01/filesystem_inventory.tsv`.

| Surface | Files on disk | Tracked | Notes |
|---|---:|---:|---|
| `configs/` | 17 | 17 | 5 training configs, 4 backfill configs + 4 input JSONs, 4 certify configs |
| `data/` | 9 | 9 | battery index, 7 concepts, extraction script |
| `docs/` | 13 | 9 | canonical docs plus ignored roadmap/archive files |
| `interplab/` | 65 Python files | 65 | 11 subsystem packages + jobs; no `training/` |
| `project-management/` | 11 | 0 | inherited handoff, ignored |
| `registry/` | 26 | 26 | 15 JSON artifacts + `.gitkeep` files |
| `reports/` | 32 | 0 | 27.6 MB local generated/research material |
| `results/` | 127 | 0 | 56.6 MB local generated/legacy material |
| `schemas/` | 24 | 24 | 12 artifact schemas, 9 config schemas, 3 band files |
| `scripts/` | 18 | 18 | 11 top-level scripts, 7 frozen legacy scripts |
| `slurm/` | 7 | 7 | 5 launchers, setup script, cluster requirements |
| `tests/` | 83 | 83 | 61 test modules, 14 fixture files, 6 golden files, helpers |

### Command surfaces

- Jobs: `backfill_checkpoint`, `census`, `certify`, `characterize`,
  `report`, `steer`, `store_qa`, `sync_registry`, `validate`.
- Top-level scripts: matching wrappers for those nine jobs plus the ad hoc
  `characterize_lite` and `multilingual_rerun`.
- Config schemas: matching schemas for the same nine jobs.
- Launchers: certify, characterize, steer, train, validate.
- Blueprint-required but absent: `train` job/schema/wrapper (intentional
  ED-18 pause) and `judge` job/schema/wrapper (unfulfilled WP8 obligation).
- `launch_train.sh` intentionally targets the absent train command.
- `launch_steer.sh` targets a present command but its comments still claim
  that command does not exist.

## Commands and summarized results

| Command/check | Result |
|---|---|
| `uv sync --extra dev` in a new isolated environment | First sandbox attempt exit 2 because uv cache access was denied; same command outside sandbox succeeded, resolving 196 and installing 118 packages. |
| `uv run pytest` in that clean environment | **603 passed, 3 deselected, 40 warnings**, 289.21s. |
| `uv run pytest -m nightly` | 3 selected, **3 explicitly skipped**, 603 deselected. Reasons: missing `cheese_reference.json` and missing `INTERPLAB_NIGHTLY_QWEN_DIR`. |
| Exact CI Ruff command | Exit 0, all checks passed in the current dirty tree. |
| `uv lock --check` | Exit 0; 196 packages resolved. |
| `git diff --check` | Exit 0; only line-ending warnings on inherited script edits. |
| All 11 top-level scripts with `--help` | Exit 0. Heavy-importing commands emitted sandbox-only WandB temp cleanup permission tracebacks during interpreter exit. |
| Isolated `sync_registry` public CLI | Exit 0; valid RunCard; “synced 0 artifact(s) from outbox.” |
| Invalid `sync_registry` config through public CLI | Exit 1 with uncaught `SchemaValidationError`; RunCard count unchanged at 5. |
| Registry envelope/hash/filename validation | 15/15 valid; no errors. |
| Local registry reference resolution | No missing `local:registry/` references. |

Full commands are recorded in `logs/AUDIT-01/commands_run.md`; raw output
paths are listed below.

## Registry and generated-artifact state

| Artifact | Count | Production evidence |
|---|---:|---|
| A1 corpus manifest | 1 | FineWeb stream, 601,369 docs, 400,000,109 tokens, dataset revision `unknown` |
| A3 census report | 1 | Shares a RunCard/run ID with A1 |
| A5 SAE checkpoint | 4 | All have matching local A10 |
| A6 SAE certificate | 4 | 3 amber, 1 green under placeholder bands v1; none has matching local A10 |
| A10 RunCard | 5 | 4 backfill + 1 census |
| A4/A7/A8/A9/A11/A12 | 0 | Production chain stops at A6 |

The local `reports/` and `results/` trees contain substantial scientific and
presentation material, but none is a substitute for missing registry
artifacts. `characterize_lite` says explicitly that it emits no A7, RunCard,
or dashboards. The internship report is not A11.

## Suspicious implementation search

- `TODO`: no true TODO found; the only text match was inside the package
  name `pycryptodomex`.
- `FIXME` and xfail: none.
- `NotImplementedError`: present at explicit URI, model-converter, layout,
  and input-format boundaries. Most are deliberate fail-closed boundaries
  with tests. They are not evidence that the named core algorithms are
  stubs.
- `placeholder`: the three production band files and launcher resource
  requests explicitly identify uncalibrated values. Band placeholders are
  researcher/calibration work, not missing algorithms.
- `stub`: deterministic characterization/validation judges exist for tests;
  production rubric judging is deliberately researcher-gated. This is an
  intentional non-capability and must not be presented as real judging.
- `dummy`: only test/golden hashes.
- bare `pass`: exception classes, a test helper/context manager, and the
  one-time extraction script's YAML representer class; no empty production
  algorithm body was found.
- skips: exactly one cheese canary and two real-Qwen identity tests. All
  skip with explicit reasons. No silently absent or xfailed tests were found.
- dead/unregistered commands: train launcher is intentionally dormant;
  judge command is missing rather than dead; two ad hoc scripts are outside
  the registered job/config system by explicit design.

## Major contradictions

1. The inherited “WP0-WP8 complete; only WP9 remains” claim conflicts with
   the missing judge surface, missing production chain, missing package
   pilot, and systemic exit/RunCard defect.
2. Commit `e61016b` is labeled “WP0-WP10,” but WP8 and WP10 obligations are
   visibly open. Commit labels are not completion evidence.
3. README says there are no ready-made job configs, while 4 backfill and
   4 certify configs exist.
4. README says SS8 judge runs through `interplab.evaluation` rather than a
   standalone wrapper; blueprint §6.1 explicitly requires a `judge` job.
5. README and blueprint require every job to leave a RunCard and use
   exit 0/2/3/4. Invalid configs instead escape with exit 1 and no card.
6. README's package tree lists `interplab/training/`; no such package exists.
   ED-18 makes this an intentional pause, so the README is stale.
7. `launch_steer.sh` and `test_import_contracts.py` still say steer is absent;
   the job, wrapper, schema, and tests are present.
8. `interplab.evaluation.__init__` describes an old SAE-Lens 3.23/`typer`
   conflict, while the operative stack is SAE-Lens 6.44.2 and blueprint
   ED-19 records the unresolved NumPy conflict.
9. Blueprint §8.2 still states a 32-ULP golden bound and measured max 8;
   current tests use 128 after the ED-33 migration. ED-25 is absent and
   ED-26 is not entered as a proper blueprint decision.
10. Blueprint says `reports/` is git-tracked. The inherited `.gitignore`
    modification ignores it, and zero report files are tracked.
11. The inherited `project-management/PROJECT_STATE.md` says CI lint is red.
    The current working tree contains the prescribed uncommitted fixes and
    the exact CI command is green.
12. The work order names `project_management/`; inherited management files
    use `project-management/`. No governance decision reconciles them.

## Findings by classification

### Implementation defects

- **ID-01 — Missing WP8 producer:** no judge job, config schema, wrapper, or
  Lodestar adapter exists for required A9′ production.
- **ID-02 — Invalid-config lifecycle violation:** all nine implemented jobs
  call `load_and_validate` before RunCard creation and outside their guarded
  exit-code path. Invalid configs exit 1 with a traceback and no RunCard,
  violating Ground Rules 4-5 and §6.2.

### Verification gaps

- Real-Qwen identity equivalence not run.
- No production A4/A7/A8/A9/A11/A12.
- No production characterize/validate/steer/report chain.
- No recorded production sync or interruption/failure-path exercise.
- No production validation of rubric/autointerpretation integrations.

### Architectural ambiguities

- Legal dependency/composition path for judge + capability perplexity.
- Historical scope of WP2's “all 6+ checkpoints.”
- Canonical management/report tracking and path convention.

### Documentation defects

The twelve contradictions above include stale command availability,
dependency-conflict history, config availability, ULP limits, package tree,
tracking claims, and audit state.

### Researcher actions

- Reconcile the WP2 checkpoint population.
- Locate/sync or declare irrecoverable the four certification RunCards.
- Calibrate A6/A8/A4 bands under schema-version policy.
- Supply/accept corpus revision provenance.
- Author remaining battery negatives/census terms.
- Author A12, claim-mode prompts/spec, and the real cheese canary reference.
- Decide Lodestar dependency changes in the Lodestar repository.

### Environment limitations

- No staged real Qwen directory, Tamia heavy artifacts, GPU/cluster lane, or
  real cheese reference was available locally.
- Sandboxed uv/temp access failed due Windows ACLs. Equivalent outside-
  sandbox checks passed; these failures are not repository defects.
- Several `--help` imports triggered WandB temp cleanup ACL tracebacks in the
  sandbox while still exiting 0.

### Intentional pauses

- New SAE training package/job under ED-18.
- Lodestar integration under ED-19.
- SS13 circuit tracing.
- Real rubric/autointerpretation content and judge choice.

## WP9 safety decision

**WP9 is not safe to start as the next work package.**

The reason is not the absence of a real canary reference alone; ED-23 assigns
that reference to the researcher and explicitly allows an honest skip.
Rather:

- WP5 and WP6 are not accepted prerequisites;
- WP8 has a missing producer and unresolved architecture;
- WP7 violates the global job exit/RunCard contract;
- production lineage and chain evidence are incomplete; and
- the WP9 mechanism is already present, so “start WP9” has no well-defined
  implementation scope without risking conversion of missing research
  evidence into code work.

## Raw audit outputs

- `logs/AUDIT-01/filesystem_inventory.tsv`
- `logs/AUDIT-01/repository_structure.txt`
- `logs/AUDIT-01/suspicious_search.txt`
- `logs/AUDIT-01/clean_install.txt`
- `logs/AUDIT-01/clean_install_escalated.txt`
- `logs/AUDIT-01/pytest_default.txt`
- `logs/AUDIT-01/pytest_nightly.txt`
- `logs/AUDIT-01/ruff_ci.txt`
- `logs/AUDIT-01/uv_lock_check.txt`
- `logs/AUDIT-01/git_diff_check.txt`
- `logs/AUDIT-01/public_cli_help.txt`
- `logs/AUDIT-01/public_workflow.txt`
- `logs/AUDIT-01/public_workflow_sandbox/`
- `logs/AUDIT-01/invalid_config_cli.txt`
- `logs/AUDIT-01/registry_validation.txt`
- `logs/AUDIT-01/registry_references.txt`
- `logs/AUDIT-01/commands_run.md`
