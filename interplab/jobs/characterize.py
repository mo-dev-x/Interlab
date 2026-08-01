"""interplab.jobs.characterize (SS5) -- runs the streaming indexer over a
corpus sample (+ optional chat slice) for a certified checkpoint, writes
the CharacterizationIndex directory + A7 manifest, and renders dashboards.

Reads A5 (+ A6 soft -- a red/missing certificate does not block
characterization, per §5.SS5's "soft" blocking tier) + a corpus text
source; writes A7 (+ index dir, dashboards) directly to whatever
`registry_root` it's given -- `registry/` when local, or a cluster outbox
dir when the launcher passes one (§7.1, same as `certify`; ED-7: this GPU
stage runs on the cluster for production checkpoints). ED-34: checkpoint
weights resolve via `local:`/`tamia:`, the base model via
`local:`/`tamia:`/`hf:` (see `characterization.model_loading`).
"""

from __future__ import annotations

import json
from pathlib import Path

from sae_lens import SAE

from interplab.characterization import dashboards, indexer
from interplab.characterization.feature_index import FeatureIndex
from interplab.characterization.model_loading import (
    load_local_hooked_transformer,
    resolve_model_location,
)
from interplab.core import envelope, hashing, uris
from interplab.core import environment as environment_mod
from interplab.core.errors import ContractViolationError, EnvironmentBaselineError
from interplab.registry.config_lifecycle import PreparedJobRunFailed, prepare_job_run
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put

_JUDGES = {"stub": indexer.StubJudge, "none": indexer.NoOpJudge}


def _load_docs_jsonl(path: Path) -> list[str]:
    """Duplicated from `interplab.corpus.replay.iter_local_jsonl` (§1
    Ground Rule 2: `jobs.characterize` may only import `core`, `registry`,
    and `characterization` -- not `corpus`)."""
    docs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line)["text"])
    return docs


def _load_docs_local_hf_dataset(path: Path, *, split: str = "train", text_field: str = "text") -> list[str]:
    """Duplicated from `interplab.corpus.replay.iter_local_hf_dataset` (same
    Ground Rule 2 boundary as `_load_docs_jsonl` -- `replay`'s version
    depends on `datasets`, so it cannot be promoted to `core` either, which
    is stdlib/numpy/pydantic/jsonschema only). Same acquisition method
    SAELens itself used at training time: `datasets.load_dataset(path,
    split=..., streaming=True)`, no `revision`."""
    from datasets import load_dataset

    ds = load_dataset(str(path), split=split, streaming=True)
    return [row[text_field] for row in ds]


def _load_docs(path: Path) -> list[str]:
    """ED-34: dispatches on what's actually at the resolved path -- a file
    streams as JSONL, a directory streams as a local HuggingFace dataset
    cache (the format the real training corpus is stored in). Mirrors
    `corpus.replay.open_stream`'s own file-vs-directory dispatch (and
    `certification.eval_slice.load_corpus_docs`'s identical fix), cross-
    referenced as sanctioned twins."""
    return _load_docs_local_hf_dataset(path) if path.is_dir() else _load_docs_jsonl(path)


def _get_or_raise(content_hash: str, *, registry_root: Path, role: str) -> dict:
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except Exception as e:
        raise ContractViolationError(f"could not resolve {role} {content_hash!r}: {e}") from e


def _find_subject_ref(artifact: dict, role: str) -> dict:
    for ref in artifact["subject"]:
        if ref["role"] == role:
            return ref
    raise ContractViolationError(
        f"{artifact['artifact_type']} {artifact['self_hash']!r} has no subject entry with role {role!r}"
    )


def _load_local(location: str, *, what: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        return uris.resolve_local(location)
    if parsed.scheme == "tamia":
        return uris.resolve_tamia(location)
    raise NotImplementedError(f"characterize can only load {what} from local:/tamia: URIs; got {location!r}")


def _characterize_inputs(config: dict) -> list[dict]:
    checkpoint_hash = config["checkpoint_hash"]
    corpus_manifest_hash = config["corpus_manifest_hash"]
    return [
        {
            "content_hash": checkpoint_hash,
            "location": f"local:registry/sae_checkpoint/{hashing.short_hash(checkpoint_hash)}.json",
            "role": "sae_checkpoint",
        },
        {
            "content_hash": corpus_manifest_hash,
            "location": f"local:registry/corpus_manifest/{hashing.short_hash(corpus_manifest_hash)}.json",
            "role": "corpus_manifest",
        },
    ]


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    try:
        prepared = prepare_job_run(
            stage="characterize",
            job_name="characterize",
            config_path=config_path,
            build_inputs=_characterize_inputs,
            build_environment=environment_mod.build_certification_environment,
            registry_root=registry_root,
            repo_root=repo_root,
        )
    except PreparedJobRunFailed as error:
        return error.exit_code
    if prepared is None:
        return 3
    config, handle = prepared
    checkpoint_ref, corpus_manifest_ref = _characterize_inputs(config)
    checkpoint_hash = checkpoint_ref["content_hash"]
    corpus_manifest_hash = corpus_manifest_ref["content_hash"]

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []
    environment: dict | None = None

    try:
        # ED-32: asserted at startup, before any registry/model access.
        environment = environment_mod.build_certification_environment()
        environment_mod.check_sae_stack_baseline(environment)

        checkpoint = _get_or_raise(checkpoint_hash, registry_root=registry_root, role="sae_checkpoint")
        # existence check only -- A7's own required subject reference (§4 A7:
        # "Subject: sae_checkpoint + corpus_manifest(s) of the sample"; the
        # WP7 compliance fix for the carry-over finding).
        _get_or_raise(corpus_manifest_hash, registry_root=registry_root, role="corpus_manifest")
        weights_ref = _find_subject_ref(checkpoint, "weights")
        model_ref = _find_subject_ref(checkpoint, "model")

        weights_path = _load_local(weights_ref["location"], what="SAE weights")
        model_path = resolve_model_location(model_ref["location"])
        sae = SAE.load_from_pretrained(str(weights_path), device="cpu")
        model = load_local_hooked_transformer(str(model_path))

        corpus_path = _load_local(config["corpus_location"], what="the corpus")
        docs = _load_docs(corpus_path)
        n_docs = config.get("n_docs")
        if n_docs is not None:
            docs = docs[:n_docs]
        if not docs:
            raise ContractViolationError(f"corpus_location {config['corpus_location']!r} contains zero documents")

        chat_docs = None
        if config.get("chat_slice_location"):
            chat_path = _load_local(config["chat_slice_location"], what="the chat slice")
            chat_docs = _load_docs(chat_path)
            n_chat = config.get("n_chat_docs")
            if n_chat is not None:
                chat_docs = chat_docs[:n_chat]

        judge = _JUDGES[config["judge"]]()

        index = indexer.build_index(
            model,
            sae,
            corpus_docs=docs,
            chat_docs=chat_docs,
            judge=judge,
            weights_location=weights_ref["location"],
            model_location=model_ref["location"],
            rng_seed=config.get("rng_seed", 0),
        )

        # index_dir defaults under the REAL repo root (uris.REPO_ROOT), never
        # the job's own (possibly test-injected) `repo_root` -- `local:`
        # URIs always mean repo-relative to the real repo (§3.2), the same
        # rule `backfill_checkpoint` already applies to `local:` resolution.
        index_dir_name = f"{checkpoint_hash[len(hashing.SHA256_PREFIX):][:12]}"
        index_dir = Path(config.get("index_dir") or (uris.REPO_ROOT / "results" / "characterization" / index_dir_name))
        if not index_dir.is_relative_to(uris.REPO_ROOT):
            raise ContractViolationError(
                f"index_dir {index_dir} must resolve inside the repo root {uris.REPO_ROOT} -- the index "
                "becomes a registered `local:` subject entry, which is only valid for repo-relative paths"
            )
        indexer.write_index(index, index_dir)
        index_hash = hashing.hash_directory(index_dir)
        index_ref = {
            "content_hash": index_hash,
            "location": f"local:{index_dir.relative_to(uris.REPO_ROOT).as_posix()}",
            "role": "index",
        }

        payload = {
            "sample": {"n_tokens": index["n_tokens"], "chat_slice_tokens": index["chat_slice_tokens"]},
            "index_layout_version": index["index_layout_version"],
            "per_feature_columns": [
                "corpus_max", "firing_rate", "decile_boundaries", "logit_top_tokens",
                "autointerp_label", "autointerp_detection_score",
            ],
            "judge": index["judge"],
        }
        artifact = envelope.dump(
            artifact_type="characterization_manifest",
            schema_version=1,
            created_by=handle.created_by,
            subject=[checkpoint_ref, corpus_manifest_ref, index_ref],
            payload=payload,
        )
        manifest_hash = registry_put(artifact, registry_root=registry_root)

        feature_index = FeatureIndex.open(str(index_dir), registry_root=registry_root)
        dashboard_dir = index_dir / "dashboards"
        for i in range(feature_index.n_features):
            dashboards.render_feature(feature_index, i, dashboard_dir)
        dashboards.render_catalog(feature_index, dashboard_dir)

        outputs = [
            index_ref,
            {
                "content_hash": manifest_hash,
                "location": f"local:registry/characterization_manifest/{hashing.short_hash(manifest_hash)}.json",
                "role": "characterization_manifest",
            },
        ]
        status, exit_code = "completed", 0
        outcome_line = (
            f"characterization_manifest {hashing.short_hash(manifest_hash)}; "
            f"{feature_index.n_features} features over {index['n_tokens']} tokens"
        )

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except EnvironmentBaselineError as e:  # ED-32: a designed refusal, not an unexpected failure
        status, exit_code = "failed", 4
        outcome_line = f"environment baseline violated: {e}"
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line, environment=environment)

    return exit_code
