"""interplab.jobs.backfill_checkpoint (ED-5) -- registers a backfilled A5
`sae_checkpoint` manifest for a pre-blueprint checkpoint. `store_hash` is
always null (these predate stores); the training corpus is documented via
a `corpus_manifest` reference in `subject`, per ED-5.

Directory hashing MUST happen on the machine holding the weights (D1). If
`weights_dir_hash`/`model_dir_hash` are supplied in the config, they are
trusted as already computed correctly there (e.g. via a small companion
script on the cluster using the same algorithm as
`core.hashing.hash_checkpoint_dir` for weights -- ED-27: restricted to
exactly `{cfg.json, sae_weights.safetensors}`, never the whole directory --
and `core.hashing.hash_directory` for the model). If omitted, this job
computes them locally -- only valid when the location is actually
reachable from this machine (e.g. a `local:` fixture, not a real cluster
path).

ED-29: `model_location` MUST be a revision-pinned `hf:<repo>@<commit-sha>`
ref (schema-enforced) -- the base model is a *consumed* artifact, already
identified upstream, unlike the checkpoint this job registers. Because
that's never a `local:` URI, `model_dir_hash` MUST be supplied explicitly
in every real invocation; `model_dir_hash` itself remains the unrestricted
`hash_directory`, never `hash_checkpoint_dir`.

ED-30: `telemetry_tail` is recovered training-run telemetry, never a
certified metric (that's A6 `metrics.fvu`) -- passed through from the
config verbatim, including its `fvu_source` discriminator and the
nullability of `fvu`/`dead_count` for legacy rows that can't recover a
value.

ED-33: `training_provenance`/`cfg_schema_generation` are passed through
from the config verbatim, same discipline as `telemetry_tail` -- this job
records what the caller already determined (from cfg.json metadata,
runner_cfg, or WandB corroboration), it does not itself infer provenance.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from interplab.core import envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.registry.config_lifecycle import prepare_job_run
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import put as registry_put


def _resolve_dir_hash(
    explicit_hash: str | None,
    location: str,
    field_name: str,
    *,
    hash_fn=hashing.hash_directory,
) -> str:
    """`local:` URIs here always mean repo-relative to the REAL repo (§3.2)
    -- never the job's own (possibly test-injected) `repo_root`, which
    exists only to resolve the job's own config file location."""
    if explicit_hash:
        return explicit_hash

    parsed = uris.parse(location)
    if parsed.scheme != "local":
        raise ContractViolationError(
            f"{field_name} was not supplied and its location is not a local: URI -- D1 requires "
            f"directory hashing to happen on the machine holding the data; compute it there "
            f"(core.hashing.{hash_fn.__name__}) and supply {field_name} explicitly"
        )
    path = uris.resolve_local(location)
    return hash_fn(path)


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    prepared = prepare_job_run(
        stage="backfill",
        job_name="backfill_checkpoint",
        config_path=config_path,
        registry_root=registry_root,
        repo_root=repo_root,
        entrypoint="interplab.jobs.backfill_checkpoint",
    )
    if prepared is None:
        return 3
    config, handle = prepared

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        training_config_path = uris.resolve_local(config["training_config_path"])
        if not training_config_path.is_file():
            raise ContractViolationError(f"training_config_path not found: {training_config_path}")
        training_config = yaml.safe_load(training_config_path.read_text(encoding="utf-8"))

        weights_hash = _resolve_dir_hash(
            config.get("weights_dir_hash"), config["weights_location"], "weights_dir_hash",
            hash_fn=hashing.hash_checkpoint_dir,
        )
        model_hash = _resolve_dir_hash(config.get("model_dir_hash"), config["model_location"], "model_dir_hash")

        payload = {
            "config": training_config,
            "store_hash": None,
            "seed": config["seed"],
            "tokens_trained": config["tokens_trained"],
            "wandb": config.get("wandb"),
            "telemetry_tail": config["telemetry_tail"],
            "training_provenance": config["training_provenance"],
            "cfg_schema_generation": config["cfg_schema_generation"],
        }
        subject = [
            {"content_hash": weights_hash, "location": config["weights_location"], "role": "weights"},
            {"content_hash": model_hash, "location": config["model_location"], "role": "model"},
            {
                "content_hash": config["corpus_manifest_hash"],
                "location": f"local:registry/corpus_manifest/{hashing.short_hash(config['corpus_manifest_hash'])}.json",
                "role": "corpus_manifest",
            },
        ]

        artifact = envelope.dump(
            artifact_type="sae_checkpoint",
            schema_version=1,
            created_by=handle.created_by,
            subject=subject,
            payload=payload,
        )
        checkpoint_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {
                "content_hash": checkpoint_hash,
                "location": f"local:registry/sae_checkpoint/{hashing.short_hash(checkpoint_hash)}.json",
                "role": "sae_checkpoint",
            }
        ]
        status, exit_code = "completed", 0
        outcome_line = f"backfilled sae_checkpoint {hashing.short_hash(checkpoint_hash)} (tokens_trained={config['tokens_trained']})"

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
