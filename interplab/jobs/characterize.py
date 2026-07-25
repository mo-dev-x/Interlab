"""interplab.jobs.characterize (SS5) -- runs the streaming indexer over a
corpus sample (+ optional chat slice) for a certified checkpoint, writes
the CharacterizationIndex directory + A7 manifest, and renders dashboards.

Reads A5 (+ A6 soft -- a red/missing certificate does not block
characterization, per §5.SS5's "soft" blocking tier) + a corpus text
source; writes A7 (+ index dir, dashboards) directly to `registry/` (§7.1,
same as `certify`: this job never runs on the cluster in this environment).
"""

from __future__ import annotations

import json
from pathlib import Path

from sae_lens import SAE

from interplab.characterization import dashboards, indexer
from interplab.characterization.feature_index import FeatureIndex
from interplab.characterization.model_loading import load_local_hooked_transformer
from interplab.core import configs, envelope, hashing, uris
from interplab.core import environment as environment_mod
from interplab.core.errors import ContractViolationError, EnvironmentBaselineError
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card

_JUDGES = {"stub": indexer.StubJudge, "none": indexer.NoOpJudge}


def _load_docs_jsonl(path: Path) -> list[str]:
    """Duplicated from `interplab.corpus.manifest.load_docs_jsonl` (§1
    Ground Rule 2: `jobs.characterize` may only import `core`, `registry`,
    and `characterization` -- not `corpus`)."""
    docs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line)["text"])
    return docs


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
    if parsed.scheme != "local":
        raise NotImplementedError(
            f"characterize can only load {what} from local: URIs in this environment; got {location!r}"
        )
    return uris.resolve_local(location)


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    config = configs.load_and_validate(config_path, "characterize")
    checkpoint_hash = config["checkpoint_hash"]
    checkpoint_ref = {
        "content_hash": checkpoint_hash,
        "location": f"local:registry/sae_checkpoint/{hashing.short_hash(checkpoint_hash)}.json",
        "role": "sae_checkpoint",
    }
    corpus_manifest_hash = config["corpus_manifest_hash"]
    corpus_manifest_ref = {
        "content_hash": corpus_manifest_hash,
        "location": f"local:registry/corpus_manifest/{hashing.short_hash(corpus_manifest_hash)}.json",
        "role": "corpus_manifest",
    }

    handle = new_run_card(
        "characterize", config_path, registry_root=registry_root, repo_root=repo_root,
        inputs=[checkpoint_ref, corpus_manifest_ref],
    )

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
        model_path = _load_local(model_ref["location"], what="the base model")
        sae = SAE.load_from_pretrained(str(weights_path), device="cpu")
        model = load_local_hooked_transformer(str(model_path))

        corpus_path = _load_local(config["corpus_location"], what="the corpus")
        docs = _load_docs_jsonl(corpus_path)
        n_docs = config.get("n_docs")
        if n_docs is not None:
            docs = docs[:n_docs]
        if not docs:
            raise ContractViolationError(f"corpus_location {config['corpus_location']!r} contains zero documents")

        chat_docs = None
        if config.get("chat_slice_location"):
            chat_path = _load_local(config["chat_slice_location"], what="the chat slice")
            chat_docs = _load_docs_jsonl(chat_path)
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
