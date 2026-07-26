from pathlib import Path

import pytest

from interplab.core import uris


@pytest.mark.parametrize(
    ("uri", "scheme", "value"),
    [
        ("local:data/concepts/cheese.yaml", "local", "data/concepts/cheese.yaml"),
        ("tamia:sae_checkpoint/abc123/weights", "tamia", "sae_checkpoint/abc123/weights"),
        ("hf:HuggingFaceFW/fineweb@main", "hf", "HuggingFaceFW/fineweb@main"),
        ("wandb:run-abc123", "wandb", "run-abc123"),
    ],
)
def test_parse_valid(uri, scheme, value):
    parsed = uris.parse(uri)
    assert parsed.scheme == scheme
    assert parsed.value == value
    assert str(parsed) == uri


@pytest.mark.parametrize(
    "bad",
    [
        "no-scheme-here",
        "ftp:whatever",
        "local:",
        "local:/absolute/path",
        "local:C:/windows/style",
        "local:../escape",
        "local:a/../b",
        "tamia:/absolute",
        "hf:no-at-sign",
        "hf:too@many@ats",
        "hf:@missing-dataset",
        "hf:missing-revision@",
    ],
)
def test_parse_invalid(bad):
    with pytest.raises(uris.URIError):
        uris.parse(bad)


def test_validate_does_not_raise_on_good_uri():
    uris.validate("local:configs/foo.yaml")


def test_validate_raises_on_bad_uri():
    with pytest.raises(uris.URIError):
        uris.validate("not-a-uri")


def test_resolve_local_joins_repo_root(tmp_path):
    resolved = uris.resolve_local("local:tests/fixtures/tiny_sae", repo_root=tmp_path)
    assert resolved == tmp_path / "tests" / "fixtures" / "tiny_sae"


def test_resolve_local_rejects_non_local_scheme():
    with pytest.raises(uris.URIError):
        uris.resolve_local("tamia:sae_checkpoint/abc")


def test_resolve_local_against_real_repo_root_finds_tiny_sae_fixture():
    resolved = uris.resolve_local("local:tests/fixtures/tiny_sae")
    assert resolved.is_dir()


def test_resolve_tamia_joins_scratch_and_interplab(monkeypatch):
    monkeypatch.setenv("SCRATCH", "/scratch/y/yazid")
    resolved = uris.resolve_tamia("tamia:sae_checkpoints/rwu04lpb/final_400001024")
    assert resolved == Path("/scratch/y/yazid") / "interplab" / "sae_checkpoints/rwu04lpb/final_400001024"


def test_resolve_tamia_rejects_non_tamia_scheme(monkeypatch):
    monkeypatch.setenv("SCRATCH", "/scratch/y/yazid")
    with pytest.raises(uris.URIError):
        uris.resolve_tamia("local:tests/fixtures/tiny_sae")


def test_resolve_tamia_without_scratch_raises_clearly(monkeypatch):
    monkeypatch.delenv("SCRATCH", raising=False)
    with pytest.raises(uris.URIError, match="SCRATCH"):
        uris.resolve_tamia("tamia:sae_checkpoints/rwu04lpb/final_400001024")
