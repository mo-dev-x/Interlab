"""interplab.corpus.manifest: builds the A1 corpus_manifest payload.

ED-28: build_payload takes precomputed doc_count/token_count/sample_docs
(the by-products of a single streaming pass, per interplab.corpus.census
scan_stream) rather than a materialized docs: list[str].
"""

from interplab.core import hashing
from interplab.core._schema_registry import SCHEMAS_ROOT
from interplab.core._schema_registry import validate as validate_against_schema
from interplab.corpus.manifest import build_payload

SCHEMA_PATH = SCHEMAS_ROOT / "corpus_manifest" / "v1.schema.json"


def test_build_payload_matches_a1_schema():
    docs = ["hello world", "another document here"]
    payload = build_payload(
        name="fixture-corpus",
        recipe={"dataset": "local:tests/fixtures/pinned_text.jsonl", "revision": "v1", "split": "all", "subset_spec": None, "filters": {}},
        doc_count=len(docs),
        sample_docs=docs,
        tokenizer_name="fixture-tokenizer",
        tokenizer_revision="v1",
        token_count=6,
    )
    validate_against_schema({
        "artifact_type": "corpus_manifest", "schema_version": 1,
        "self_hash": "sha256:" + "0" * 64, "created_at": "2026-07-08T00:00:00Z",
        "created_by": {"run_id": "r", "code_commit": "c", "entrypoint": "e", "host": "local"},
        "subject": [], "payload": payload,
    }, SCHEMA_PATH)


def test_doc_count_is_passed_through_verbatim():
    payload = build_payload(
        name="n", recipe={"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
        doc_count=3, sample_docs=["one", "two", "three"], tokenizer_name="t", tokenizer_revision="v1", token_count=3,
    )
    assert payload["doc_count"] == 3


def test_sample_checksum_matches_hashing_helper():
    docs = ["x", "y"]
    payload = build_payload(
        name="n", recipe={"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
        doc_count=len(docs), sample_docs=docs, tokenizer_name="t", tokenizer_revision="v1", token_count=2,
    )
    assert payload["sample_checksum"] == hashing.hash_sample_checksum(docs)


def test_sample_checksum_uses_sample_docs_not_doc_count():
    """ED-28: sample_docs may be a bounded prefix (first 1000, in stream
    order) even when doc_count reflects the whole stream -- sample_checksum
    hashes exactly what it's given, doc_count is a separate, independent field."""
    sample = ["a", "b"]
    payload = build_payload(
        name="n", recipe={"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
        doc_count=1_000_000, sample_docs=sample, tokenizer_name="t", tokenizer_revision="v1", token_count=5_000_000,
    )
    assert payload["doc_count"] == 1_000_000
    assert payload["sample_checksum"] == hashing.hash_sample_checksum(sample)


def test_legacy_unknown_recipe_fields_are_passed_through():
    """ED-8: recipe fields MAY carry the literal string "unknown" for
    pre-blueprint corpora whose full recipe is unrecoverable; sample_checksum
    remains mandatory and becomes the operative identity."""
    docs = ["legacy doc one", "legacy doc two"]
    payload = build_payload(
        name="fineweb_subset (legacy)",
        recipe={"dataset": "unknown", "revision": "unknown", "split": "unknown", "subset_spec": None, "filters": {}},
        doc_count=len(docs), sample_docs=docs, tokenizer_name="t", tokenizer_revision="v1", token_count=6,
    )
    assert payload["recipe"]["dataset"] == "unknown"
    assert payload["sample_checksum"].startswith("sha256:")
    validate_against_schema({
        "artifact_type": "corpus_manifest", "schema_version": 1,
        "self_hash": "sha256:" + "0" * 64, "created_at": "2026-07-08T00:00:00Z",
        "created_by": {"run_id": "r", "code_commit": "c", "entrypoint": "e", "host": "local"},
        "subject": [], "payload": payload,
    }, SCHEMA_PATH)
