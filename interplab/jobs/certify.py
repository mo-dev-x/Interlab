"""interplab.jobs.certify (SS4, GATE G1) -- computes A6 metrics over a
held-out slice, applies bands, emits the certificate + report card.

Reads A5 (+ A4 if the checkpoint has a store), collects activations fresh
through the model (ED-5, never from a stored slice), and writes A6 directly
to whatever `registry_root` it's given -- `registry/` when local, or a
cluster outbox dir when the launcher passes one (§7.1: "directly to
registry/ when local"; ED-7: production certify runs on the cluster under
a GPU allocation). ED-34: checkpoint weights resolve via `local:`/`tamia:`,
the base model via `local:`/`tamia:`/`hf:` (a pinned-download acquisition
step for `hf:`, never a second construction path -- see
`certification.model_loading`).
"""

from __future__ import annotations

from pathlib import Path

from sae_lens import SAE

from interplab.certification import eval_slice, report_card
from interplab.certification.bands import apply_bands, load_bands
from interplab.certification.metrics import compute_metrics
from interplab.certification.model_loading import (
    load_local_hooked_transformer,
    resolve_model_location,
)
from interplab.core import configs, envelope, hashing, uris
from interplab.core import environment as environment_mod
from interplab.core.errors import ContractViolationError, EnvironmentBaselineError
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card


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


def _load_sae(checkpoint: dict) -> SAE:
    weights_ref = _find_subject_ref(checkpoint, "weights")
    location = weights_ref["location"]
    parsed = uris.parse(location)
    if parsed.scheme == "local":
        path = uris.resolve_local(location)
    elif parsed.scheme == "tamia":
        path = uris.resolve_tamia(location)
    else:
        raise NotImplementedError(f"certify can only load SAE weights from local:/tamia: URIs; got {location!r}")
    return SAE.load_from_pretrained(str(path), device="cpu")


def _load_model(checkpoint: dict, store: dict | None):
    if store is not None:
        model_ref = store["payload"]["model"]
    else:
        model_ref = checkpoint["payload"]["config"].get("model_name") or checkpoint["payload"]["config"].get(
            "model"
        )
        if model_ref is None:
            raise ContractViolationError(
                "legacy checkpoint config has no model_name/model field to identify the base model"
            )
    model_location = None
    for ref in checkpoint["subject"]:
        if ref["role"] == "model":
            model_location = ref["location"]
            break
    if model_location is None:
        raise ContractViolationError(
            "checkpoint has no subject entry with role 'model' to locate the base transformer"
        )
    return load_local_hooked_transformer(str(resolve_model_location(model_location)))


def _resolve_eval_slice(
    config: dict, store: dict | None, *, registry_root: Path
) -> tuple[list[str], str, dict, str]:
    """Returns (selected_docs, method, params, disjointness)."""
    eval_slice_cfg = config["eval_slice"]
    corpus_location = eval_slice_cfg["corpus_location"]

    method = eval_slice_cfg.get("method")
    params = eval_slice_cfg.get("params")

    if method is None or params is None:
        holdout = None if store is None else store["payload"].get("eval_holdout")
        if holdout is None:
            raise ContractViolationError(
                "eval_slice.method/params are required in the config when the checkpoint has no "
                "store with a recorded eval_holdout (legacy checkpoint, or a store predating ED-5)"
            )
        method = "holdout_split"
        params = {"modulus": holdout["modulus"], "residues": holdout["residues"]}

    if method == "holdout_split":
        # store-backed path: the residue filter must scan the whole corpus, so a
        # materialized list is unavoidable here (ED-34 Gate-3 follow-up: still eager,
        # deferred -- reached only by store-backed SS3 checkpoints, none exist yet).
        docs = eval_slice.load_corpus_docs(corpus_location)
        selected = eval_slice.select_holdout_split(docs, modulus=params["modulus"], residues=params["residues"])
        disjointness = "by_construction"
    elif method == "stream_offset":
        # ED-34 Gate-3: consume the corpus lazily -- select_stream_offset islices the
        # generator, so only the selected `count` docs are materialized (never the
        # full 32.6M-doc / ~101GB corpus). Byte-identical slice to the eager version.
        docs = eval_slice.iter_corpus_docs(corpus_location)
        selected = eval_slice.select_stream_offset(docs, offset=params["offset"], count=params["count"])
        disjointness = "by_offset_argument"
    else:
        raise ContractViolationError(f"unknown eval_slice selection method: {method!r}")

    if not selected:
        raise ContractViolationError(f"eval_slice selection ({method}, {params}) selected zero documents")

    return selected, method, params, disjointness


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    config = configs.load_and_validate(config_path, "certify")
    checkpoint_hash = config["checkpoint_hash"]
    checkpoint_ref = {
        "content_hash": checkpoint_hash,
        "location": f"local:registry/sae_checkpoint/{hashing.short_hash(checkpoint_hash)}.json",
        # ED-15 (WP6): role MUST equal the referenced artifact's own type for
        # SS9 chain traversal's fixed role vocabulary to find it -- was
        # "checkpoint", silently breaking sae_certificate resolution.
        "role": "sae_checkpoint",
    }

    handle = new_run_card(
        "certify",
        config_path,
        registry_root=registry_root,
        repo_root=repo_root,
        inputs=[checkpoint_ref],
    )

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []
    environment: dict | None = None

    try:
        # ED-32: asserted at startup, before any registry/model access.
        environment = environment_mod.build_certification_environment()
        environment_mod.check_sae_stack_baseline(environment)

        checkpoint = _get_or_raise(checkpoint_hash, registry_root=registry_root, role="sae_checkpoint")
        store_hash = checkpoint["payload"]["store_hash"]
        store = (
            _get_or_raise(store_hash, registry_root=registry_root, role="store_manifest")
            if store_hash is not None
            else None
        )

        sae = _load_sae(checkpoint)
        model = _load_model(checkpoint, store)

        docs, method, params, disjointness = _resolve_eval_slice(config, store, registry_root=registry_root)
        batches = eval_slice.tokenize_to_batches(
            docs, model.tokenizer, seq_len=config["seq_len"], batch_size=config["batch_size"],
            n_tokens=config["n_tokens"],
        )

        metrics = compute_metrics(model, sae, sae.cfg.metadata.hook_name, batches)

        bands = load_bands(config["bands_version"])
        verdict, per_metric_verdicts = apply_bands(metrics, bands)

        eval_slice_cfg = config["eval_slice"]
        payload = {
            "eval_slice": {
                "corpus": {
                    "content_hash": eval_slice_cfg["corpus_manifest_hash"],
                    "location": eval_slice_cfg["corpus_location"],
                },
                "selection": {"method": method, "params": params},
                "n_tokens": sum(b.shape[0] * b.shape[1] for b in batches),
                "disjointness": disjointness,
            },
            "metrics": {
                "ce_recovered": metrics.ce_recovered,
                "fvu": metrics.fvu,
                "dead_fraction": metrics.dead_fraction,
                "density_histogram": metrics.density_histogram,
                "max_decoder_cosine_p999": metrics.max_decoder_cosine_p999,
                "per_position_fvu": metrics.per_position_fvu,
            },
            "bands_version": config["bands_version"],
            "verdict": verdict,
            "per_metric_verdicts": per_metric_verdicts,
        }

        artifact = envelope.dump(
            artifact_type="sae_certificate",
            schema_version=1,
            created_by=handle.created_by,
            subject=[checkpoint_ref],
            payload=payload,
        )
        cert_hash = registry_put(artifact, registry_root=registry_root)

        report_dir = Path(config.get("report_card_dir") or (repo_root / "results" / "certificates" / cert_hash[7:19]))
        md_path, _png_path = report_card.render(
            metrics, verdict, per_metric_verdicts,
            checkpoint_hash=checkpoint_hash, bands_version=config["bands_version"], out_dir=report_dir,
        )

        outputs = [
            {"content_hash": cert_hash, "location": f"local:registry/sae_certificate/{cert_hash[7:19]}.json", "role": "certificate"},
        ]

        if verdict == "red":
            status, exit_code = "gate_failed", 2
        else:
            status, exit_code = "completed", 0
        outcome_line = f"{verdict} certificate ({cert_hash[7:19]}); report card at {md_path}"

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
