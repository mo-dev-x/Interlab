"""interplab.jobs.store_qa (SS2, ED-11 stage="store_qa") -- QA measurements
over a finished activation store; verdict; A4 emission.

Reads a store dir (shard_NNNN.npz files, §5.SS2 store-format note) + A1;
writes A4 directly to `registry/` (§7.1, same as `certify`/`characterize`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from interplab.core import envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.registry.config_lifecycle import prepare_job_run
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from interplab.store_qa.bands import apply_bands, load_bands
from interplab.store_qa.qa import compute_metrics, load_store_shards


def _token_count(shards: list[Path]) -> int:
    total = 0
    for p in shards:
        with np.load(p) as data:
            total += data["input_ids"].size
    return total


def _get_or_raise(content_hash: str, *, registry_root: Path, role: str) -> dict:
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except Exception as e:
        raise ContractViolationError(f"could not resolve {role} {content_hash!r}: {e}") from e


def _store_qa_inputs(config: dict) -> list[dict]:
    corpus_manifest_hash = config["corpus_manifest_hash"]
    return [
        {
            "content_hash": corpus_manifest_hash,
            "location": f"local:registry/corpus_manifest/{hashing.short_hash(corpus_manifest_hash)}.json",
            "role": "corpus_manifest",
        }
    ]


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    prepared = prepare_job_run(
        stage="store_qa",
        job_name="store_qa",
        config_path=config_path,
        build_inputs=_store_qa_inputs,
        registry_root=registry_root,
        repo_root=repo_root,
    )
    if prepared is None:
        return 3
    config, handle = prepared
    corpus_ref = _store_qa_inputs(config)[0]
    corpus_manifest_hash = corpus_ref["content_hash"]

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        _get_or_raise(corpus_manifest_hash, registry_root=registry_root, role="corpus_manifest")

        store_location = config["store_location"]
        if uris.parse(store_location).scheme != "local":
            raise NotImplementedError(
                f"store_qa can only read local: store locations in this environment; got {store_location!r}"
            )
        store_dir = uris.resolve_local(store_location)
        shards = load_store_shards(store_dir)
        if not shards:
            raise ContractViolationError(f"store_location {store_location!r} contains zero shards")

        chat_shards = None
        if config.get("chat_slice_location"):
            chat_location = config["chat_slice_location"]
            if uris.parse(chat_location).scheme != "local":
                raise NotImplementedError(
                    f"store_qa can only read local: chat-slice locations in this environment; "
                    f"got {chat_location!r}"
                )
            chat_shards = load_store_shards(uris.resolve_local(chat_location))

        metrics = compute_metrics(
            shards, special_token_ids=set(config["special_token_ids"]), chat_shards=chat_shards
        )

        bands_version = config.get("bands_version", 1)
        bands = load_bands(bands_version)
        verdict, _per_metric_verdicts = apply_bands(metrics, bands)

        payload = {
            "model": config["model"],
            "hook_name": config["hook_name"],
            "hook_layer": config["hook_layer"],
            "context_size": config["context_size"],
            "prepend_bos": config["prepend_bos"],
            "dtype": config["dtype"],
            "token_count": _token_count(shards),
            "position_policy": config["position_policy"],
            "eval_holdout": config.get("eval_holdout"),
            "qa": {
                "norm_by_position": metrics.norm_by_position,
                "special_token_fraction": metrics.special_token_fraction,
                "adjacent_autocorrelation": metrics.adjacent_autocorrelation,
                "chat_divergence": metrics.chat_divergence,
                "verdict": verdict,
            },
        }
        artifact = envelope.dump(
            artifact_type="store_manifest",
            schema_version=1,
            created_by=handle.created_by,
            subject=[corpus_ref],
            payload=payload,
        )
        manifest_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {
                "content_hash": manifest_hash,
                "location": f"local:registry/store_manifest/{hashing.short_hash(manifest_hash)}.json",
                "role": "store_manifest",
            }
        ]
        if verdict == "red":
            status, exit_code = "gate_failed", 2
        else:
            status, exit_code = "completed", 0
        outcome_line = f"{verdict} store_manifest {hashing.short_hash(manifest_hash)}"

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
