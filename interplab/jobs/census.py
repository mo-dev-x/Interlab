"""interplab.jobs.census (SS1) -- builds a corpus_manifest (A1) fresh from a
docs file + recipe, and a census_report (A3) against the ConceptBattery
(A2, not an envelope artifact -- referenced by directory hash only, see
`interplab.corpus.battery`).

ED-9: census performs literal matching only, against researcher-authored
`census_terms`; the matcher/case_folding/boundary config is recorded on the
artifact so results stay auditable (§6.1's job inventory row for `census`).
"""

from __future__ import annotations

from pathlib import Path

from transformers import AutoTokenizer

from interplab.core import configs, envelope, hashing, uris
from interplab.core.errors import ContractViolationError
from interplab.corpus import battery as battery_mod
from interplab.corpus import census as census_mod
from interplab.corpus import manifest as manifest_mod
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card

DEFAULT_CONCEPTS_LOCATION = "local:data/concepts"


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    config = configs.load_and_validate(config_path, "census")

    handle = new_run_card("census", config_path, registry_root=registry_root, repo_root=repo_root)

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        docs_location = config["docs_location"]
        if uris.parse(docs_location).scheme != "local":
            raise NotImplementedError(
                f"census can only load docs from local: URIs in this environment; got {docs_location!r}"
            )
        docs = manifest_mod.load_docs_jsonl(uris.resolve_local(docs_location))
        if not docs:
            raise ContractViolationError(f"docs_location {docs_location!r} contains zero documents")

        tokenizer_location = config["tokenizer_location"]
        if uris.parse(tokenizer_location).scheme != "local":
            raise NotImplementedError(
                f"census can only load a tokenizer from local: URIs in this environment; "
                f"got {tokenizer_location!r}"
            )
        tokenizer = AutoTokenizer.from_pretrained(str(uris.resolve_local(tokenizer_location)))
        token_count = manifest_mod.count_tokens(docs, tokenizer)

        manifest_payload = manifest_mod.build_payload(
            name=config["name"],
            recipe=config["recipe"],
            docs=docs,
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

        census_payload = census_mod.build_payload(
            battery=concepts,
            docs=docs,
            tokenizer=tokenizer,
            total_tokens=token_count,
            matcher=config["matcher"],
            case_folding=config["case_folding"],
            boundary=config["boundary"],
        )
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
            f"census_report {hashing.short_hash(census_hash)} over {len(docs)} docs / {token_count} tokens"
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
