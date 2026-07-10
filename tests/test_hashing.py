import hashlib

import pytest

from interplab.core import hashing
from interplab.core.canonical_json import canonicalize


def test_sha256_hex_matches_stdlib():
    data = b"hello world"
    assert hashing.sha256_hex(data) == hashlib.sha256(data).hexdigest()


def test_sha256_prefixed_format():
    h = hashing.sha256_prefixed(b"x")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_file(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"hello")
    assert hashing.hash_file(p) == hashing.sha256_prefixed(b"hello")


def test_hash_directory_is_order_independent(tmp_path):
    d1 = tmp_path / "d1"
    d1.mkdir()
    (d1 / "b.txt").write_bytes(b"B")
    (d1 / "a.txt").write_bytes(b"A")
    (d1 / "sub").mkdir()
    (d1 / "sub" / "c.txt").write_bytes(b"C")

    d2 = tmp_path / "d2"
    d2.mkdir()
    (d2 / "sub").mkdir()
    (d2 / "sub" / "c.txt").write_bytes(b"C")
    (d2 / "a.txt").write_bytes(b"A")
    (d2 / "b.txt").write_bytes(b"B")

    assert hashing.hash_directory(d1) == hashing.hash_directory(d2)


def test_hash_directory_excludes_hidden_and_tmp_files(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "a.txt").write_bytes(b"A")
    before = hashing.hash_directory(d)

    (d / ".hidden").write_bytes(b"ignored")
    (d / "scratch.tmp").write_bytes(b"also ignored")
    after = hashing.hash_directory(d)

    assert before == after


def test_hash_directory_sensitive_to_content_changes(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "a.txt").write_bytes(b"A")
    before = hashing.hash_directory(d)
    (d / "a.txt").write_bytes(b"B")
    after = hashing.hash_directory(d)
    assert before != after


def test_hash_directory_rejects_non_directory(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"x")
    with pytest.raises(NotADirectoryError):
        hashing.hash_directory(p)


def _recipe(**overrides):
    base = {"dataset": "fineweb", "revision": "abc", "split": "train", "subset_spec": None, "filters": {}}
    base.update(overrides)
    return base


def test_hash_recipe_deterministic():
    assert hashing.hash_recipe(_recipe()) == hashing.hash_recipe(_recipe())


def test_hash_recipe_sensitive_to_content():
    assert hashing.hash_recipe(_recipe()) != hashing.hash_recipe(_recipe(revision="def"))


def test_hash_sample_checksum_ignores_beyond_n():
    texts = [f"doc{i}" for i in range(2000)]
    a = hashing.hash_sample_checksum(texts, n=1000)
    b = hashing.hash_sample_checksum(texts[:1000] + ["totally different"] * 1000, n=1000)
    assert a == b


def test_hash_sample_checksum_sensitive_within_n():
    texts = [f"doc{i}" for i in range(1000)]
    other = list(texts)
    other[0] = "different"
    assert hashing.hash_sample_checksum(texts) != hashing.hash_sample_checksum(other)


def test_hash_self_excludes_self_hash_field():
    artifact = {"a": 1, "self_hash": "sha256:deadbeef"}
    expected = f"sha256:{hashlib.sha256(canonicalize({'a': 1})).hexdigest()}"
    assert hashing.hash_self(artifact) == expected


def test_hash_self_ignores_self_hash_value():
    a1 = {"a": 1, "self_hash": "sha256:one"}
    a2 = {"a": 1, "self_hash": "sha256:two"}
    assert hashing.hash_self(a1) == hashing.hash_self(a2)


def test_short_hash():
    h = "sha256:" + "ab" * 32
    assert hashing.short_hash(h) == "ab" * 6


def test_short_hash_rejects_malformed():
    with pytest.raises(ValueError):
        hashing.short_hash("not-a-hash")


def test_short_hash_rejects_wrong_length():
    with pytest.raises(ValueError):
        hashing.short_hash("sha256:abc")
