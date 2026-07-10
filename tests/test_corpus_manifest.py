"""interplab.corpus.manifest: builds the A1 corpus_manifest payload."""

from interplab.core import hashing
from interplab.core._schema_registry import SCHEMAS_ROOT
from interplab.core._schema_registry import validate as validate_against_schema
from interplab.corpus.manifest import build_payload, count_tokens

SCHEMA_PATH = SCHEMAS_ROOT / "corpus_manifest" / "v1.schema.json"


class _FakeTokenizer:
    def __call__(self, text: str) -> dict:
        return {"input_ids": text.split()}


def test_build_payload_matches_a1_schema():
    docs = ["hello world", "another document here"]
    payload = build_payload(
        name="fixture-corpus",
        recipe={"dataset": "local:tests/fixtures/pinned_text.jsonl", "revision": "v1", "split": "all", "subset_spec": None, "filters": {}},
        docs=docs,
        tokenizer_name="fixture-tokenizer",
        tokenizer_revision="v1",
        token_count=count_tokens(docs, _FakeTokenizer()),
    )
    validate_against_schema({
        "artifact_type": "corpus_manifest", "schema_version": 1,
        "self_hash": "sha256:" + "0" * 64, "created_at": "2026-07-08T00:00:00Z",
        "created_by": {"run_id": "r", "code_commit": "c", "entrypoint": "e", "host": "local"},
        "subject": [], "payload": payload,
    }, SCHEMA_PATH)


def test_token_count_matches_tokenizer_output():
    docs = ["a b c", "d e"]
    assert count_tokens(docs, _FakeTokenizer()) == 5


def test_doc_count_matches_docs_length():
    docs = ["one", "two", "three"]
    payload = build_payload(
        name="n", recipe={"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
        docs=docs, tokenizer_name="t", tokenizer_revision="v1", token_count=3,
    )
    assert payload["doc_count"] == 3


def test_sample_checksum_matches_hashing_helper():
    docs = ["x", "y"]
    payload = build_payload(
        name="n", recipe={"dataset": "d", "revision": "r", "split": "s", "subset_spec": None, "filters": {}},
        docs=docs, tokenizer_name="t", tokenizer_revision="v1", token_count=2,
    )
    assert payload["sample_checksum"] == hashing.hash_sample_checksum(docs)


def test_legacy_unknown_recipe_fields_are_passed_through():
    """ED-8: recipe fields MAY carry the literal string "unknown" for
    pre-blueprint corpora whose full recipe is unrecoverable; sample_checksum
    remains mandatory and becomes the operative identity."""
    docs = ["legacy doc one", "legacy doc two"]
    payload = build_payload(
        name="fineweb_subset (legacy)",
        recipe={"dataset": "unknown", "revision": "unknown", "split": "unknown", "subset_spec": None, "filters": {}},
        docs=docs, tokenizer_name="t", tokenizer_revision="v1", token_count=6,
    )
    assert payload["recipe"]["dataset"] == "unknown"
    assert payload["sample_checksum"].startswith("sha256:")
    validate_against_schema({
        "artifact_type": "corpus_manifest", "schema_version": 1,
        "self_hash": "sha256:" + "0" * 64, "created_at": "2026-07-08T00:00:00Z",
        "created_by": {"run_id": "r", "code_commit": "c", "entrypoint": "e", "host": "local"},
        "subject": [], "payload": payload,
    }, SCHEMA_PATH)
