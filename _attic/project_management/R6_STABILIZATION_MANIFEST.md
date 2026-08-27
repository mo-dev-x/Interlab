# R6 Stabilization Manifest

Work item: `R6-S1-ED36-CANDIDATE-STABILIZATION`  
Basis: V5B-accepted exact local candidate, 2026-08-01  
Rule: stage only the paths below. Do not use `git add .`, `git add -A`, or an
equivalent broad staging command.

## Authorized tracked modifications

- `.gitignore`
- `docs/implementation_blueprint.md`
- `interplab/evaluation/__init__.py`
- `interplab/evaluation/blinding.py`
- `interplab/evaluation/capability.py`
- `interplab/jobs/backfill_checkpoint.py`
- `interplab/jobs/census.py`
- `interplab/jobs/certify.py`
- `interplab/jobs/characterize.py`
- `interplab/jobs/report.py`
- `interplab/jobs/steer.py`
- `interplab/jobs/store_qa.py`
- `interplab/jobs/sync_registry.py`
- `interplab/jobs/validate.py`
- `interplab/registry/run_card.py`
- `pyproject.toml`
- `readme.md`
- `scripts/characterize_lite.py`
- `scripts/multilingual_rerun.py`
- `slurm/launch_steer.sh`
- `slurm/requirements.cluster.txt`
- `slurm/setup_env.sh`
- `tests/test_import_contracts.py`
- `tests/test_jobs_backfill_checkpoint.py`
- `tests/test_jobs_census.py`
- `tests/test_jobs_certify.py`
- `tests/test_jobs_characterize.py`
- `tests/test_jobs_report.py`
- `tests/test_jobs_steer.py`
- `tests/test_jobs_store_qa.py`
- `tests/test_jobs_sync_registry.py`
- `tests/test_jobs_validate.py`
- `tests/test_schema_validate.py`
- `uv.lock`

## Authorized new files

- `interplab/core/environment_bundle.py`
- `interplab/evaluation/lodestar_adapter.py`
- `interplab/jobs/judge.py`
- `interplab/registry/config_lifecycle.py`
- `schemas/configs/judge_v1.schema.json`
- `schemas/environment_acquisition_manifest/v1.schema.json`
- `schemas/environment_install_manifest/v1.schema.json`
- `scripts/judge.py`
- `tests/job_test_helpers.py`
- `tests/test_environment_bundle.py`
- `tests/test_jobs_judge.py`
- `tests/test_slurm_setup_env.py`

Expected staged population: **46 paths** (34 tracked modifications + 12 new
files). Any difference is a stop-and-report condition.

## Explicitly excluded and left untouched

- `configs/characterize/rwu04lpb.yaml`
- `configs/steer/ablation_9056_seed0.yaml`
- `configs/steer/ablation_9056_seed42.yaml`
- `configs/steer/ablation_9056_seed123.yaml`
- `ssh yazid@tamia.alliancecan.ca`
- `tmp_r6c4_probe/`

These six top-level status entries must remain unstaged. This work item does not
authorize deletion, movement, editing, or integration of them.

## Accepted core identities that must survive stabilization

- `interplab/core/environment_bundle.py`: 93,984 bytes;
  SHA-256 `740dd61164d63e202ffce426d80941a77ae56ab8dbaebeb53588e86211201f7a`
- `tests/test_environment_bundle.py`: 61,153 bytes;
  SHA-256 `7bbc115271d11343bf821b2bd1435637a1a390e9400aedb9ea278eb1ef7bd21b`

## Stabilization boundary

- No content edits.
- No R7 merge/cherry-pick.
- No T1.2 merge/cherry-pick.
- No registry, result, report, data, cluster, or external-state mutation.
- Create one local commit only; do not push.
- Post-commit tracked worktree must be clean. The only ordinary untracked status
  entries must be the six excluded paths above.
