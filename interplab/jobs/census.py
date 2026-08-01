"""interplab.jobs.census (SS1) -- builds a corpus_manifest (A1) fresh from a
document stream + recipe, and a census_report (A3) against the
ConceptBattery (A2, not an envelope artifact -- referenced by directory
hash only, see `interplab.corpus.battery`).

ED-9: census performs literal matching only, against researcher-authored
`census_terms`; the matcher/case_folding/boundary config is recorded on the
artifact so results stay auditable (§6.1's job inventory row for `census`).

ED-28: the document stream is opened once, via `interplab.corpus.replay`
(local: JSONL, local: HuggingFace dataset cache, or hf: streaming Hub
dataset, subject to `recipe.subset_spec`'s consumption bound), and scanned
once (`interplab.corpus.census.scan_stream`, via `build_payload`) to
produce BOTH A1's token/doc counts and A3's term occurrences -- never
materialized as a `docs: list[str]`, never re-read.

The replay self-check (ED-28, relaxed by ED-31) verifies *document-stream*
reproducibility: `doc_count`/`token_count`/`sample_checksum` are recomputed
fresh from the replay every run, by construction -- there is nothing
further to gate here, since a fresh corpus_manifest built from a wrong
replay is simply a manifest of the wrong stream, not a drifted one.
`n_training_samples`, if supplied, is training-side telemetry (SAELens'
packed/windowed token counter) -- never an A1 identity target. It is
cross-checked only as an advisory, within a structural sanity band derived
from the known packing policy (`replay.expected_packed_token_range`): a
gross (order-of-magnitude) mismatch still fails loudly
(ContractViolationError) before anything is written to the registry, but
the small delta packing (BOS insertion, concatenation, windowing, a
dropped final partial window) legitimately introduces is expected and
never blocks.

`census_sample_docs`, if supplied, bounds how much of that SAME stream the
census accumulates term matches over (ED-28 `coverage: "sampled"`) while
A1's manifest still reflects the whole consumed stream -- the census-level
sample size is independent of, and never smaller by construction than,
A1's own subset_spec bound.
"""

from __future__ import annotations

from pathlib import Path

from transformers import AutoTokenizer

from interplab.core import envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.corpus import battery as battery_mod
from interplab.corpus import census as census_mod
from interplab.corpus import manifest as manifest_mod
from interplab.corpus import replay as replay_mod
from interplab.registry.config_lifecycle import prepare_job_run
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import put as registry_put

DEFAULT_CONCEPTS_LOCATION = "local:data/concepts"


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    prepared = prepare_job_run(
        stage="census",
        job_name="census",
        config_path=config_path,
        registry_root=registry_root,
        repo_root=repo_root,
    )
    if prepared is None:
        return 3
    config, handle = prepared

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        docs_location = config["docs_location"]
        if uris.parse(docs_location).scheme not in ("local", "hf"):
            raise NotImplementedError(
                f"census can only stream docs from local: or hf: URIs in this environment; got {docs_location!r}"
            )

        tokenizer_location = config["tokenizer_location"]
        if uris.parse(tokenizer_location).scheme != "local":
            raise NotImplementedError(
                f"census can only load a tokenizer from local: URIs in this environment; "
                f"got {tokenizer_location!r}"
            )
        tokenizer = AutoTokenizer.from_pretrained(str(uris.resolve_local(tokenizer_location)))

        subset_spec = config["recipe"]["subset_spec"]
        docs = replay_mod.open_stream(
            docs_location, split=config["recipe"]["split"], subset_spec=subset_spec, tokenizer=tokenizer
        )

        concepts_location = config.get("concepts_location", DEFAULT_CONCEPTS_LOCATION)
        if uris.parse(concepts_location).scheme != "local":
            raise NotImplementedError(
                f"census can only load the battery from local: URIs in this environment; "
                f"got {concepts_location!r}"
            )
        concepts_dir = uris.resolve_local(concepts_location)
        concepts = battery_mod.load_battery(concepts_dir)
        battery_ref = {
            "content_hash": battery_mod.battery_hash(concepts_dir),
            "location": concepts_location,
            "role": "concept_battery",
        }

        census_take_docs = config.get("census_sample_docs")
        sampling_seed = subset_spec.get("shuffle", {}).get("seed") if isinstance(subset_spec, dict) else None

        census_payload, stream_stats = census_mod.build_payload(
            battery=concepts,
            docs=docs,
            tokenizer=tokenizer,
            matcher=config["matcher"],
            case_folding=config["case_folding"],
            boundary=config["boundary"],
            census_take_docs=census_take_docs,
            sampling_rule="stream_prefix" if census_take_docs is not None else None,
            sampling_seed=sampling_seed if census_take_docs is not None else None,
        )
        token_count = stream_stats["total_tokens"]
        doc_count = stream_stats["total_docs"]
        if doc_count == 0:
            raise ContractViolationError(f"docs_location {docs_location!r} yielded zero documents")

        n_training_samples = config.get("n_training_samples")
        n_training_samples_note = ""
        if n_training_samples is not None:
            low, high = replay_mod.expected_packed_token_range(token_count, doc_count)
            if not (low <= n_training_samples <= high):
                raise ContractViolationError(
                    f"n_training_samples={n_training_samples} is structurally inconsistent with the "
                    f"replayed document stream ({doc_count} docs, {token_count} tokens; SAELens "
                    f"packing predicts a range of {low}-{high} -- ED-31) -- this is a gross, "
                    f"order-of-magnitude mismatch, not explainable by packing (BOS insertion, "
                    f"windowing, a dropped final partial window); investigate the recorded "
                    f"dataset/subset_spec/revision before trusting this replay"
                )
            n_training_samples_note = f", n_training_samples={n_training_samples} (advisory, within packing range)"

        manifest_payload = manifest_mod.build_payload(
            name=config["name"],
            recipe=config["recipe"],
            doc_count=doc_count,
            sample_docs=stream_stats["sample_docs"],
            tokenizer_name=str(uris.parse(tokenizer_location).value),
            tokenizer_revision=config["tokenizer_revision"],
            token_count=token_count,
            dedup_rate=config.get("dedup_rate"),
        )
        manifest_artifact = envelope.dump(
            artifact_type="corpus_manifest",
            schema_version=1,
            created_by=handle.created_by,
            subject=[],
            payload=manifest_payload,
        )
        corpus_manifest_hash = registry_put(manifest_artifact, registry_root=registry_root)
        corpus_manifest_ref = {
            "content_hash": corpus_manifest_hash,
            "location": f"local:registry/corpus_manifest/{hashing.short_hash(corpus_manifest_hash)}.json",
            "role": "corpus_manifest",
        }

        census_artifact = envelope.dump(
            artifact_type="census_report",
            schema_version=1,
            created_by=handle.created_by,
            subject=[corpus_manifest_ref, battery_ref],
            payload=census_payload,
        )
        census_hash = registry_put(census_artifact, registry_root=registry_root)
        census_ref = {
            "content_hash": census_hash,
            "location": f"local:registry/census_report/{hashing.short_hash(census_hash)}.json",
            "role": "census_report",
        }

        outputs = [corpus_manifest_ref, census_ref]
        status, exit_code = "completed", 0
        outcome_line = (
            f"corpus_manifest {hashing.short_hash(corpus_manifest_hash)}, "
            f"census_report {hashing.short_hash(census_hash)} over {doc_count} docs / {token_count} tokens "
            f"(coverage={census_payload['method']['coverage']}){n_training_samples_note}"
        )

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
