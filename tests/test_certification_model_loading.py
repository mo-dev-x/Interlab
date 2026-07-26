import pytest

from interplab.certification.model_loading import (
    load_local_hooked_transformer,
    resolve_hf_model_snapshot,
    resolve_model_location,
)
from interplab.core import uris

_TINY_MODEL_DIR = "tests/fixtures/tiny_model"


def test_loads_pinned_tiny_model():
    model = load_local_hooked_transformer(_TINY_MODEL_DIR)
    assert model.cfg.n_layers == 2
    assert model.cfg.d_model == 64


def test_unsupported_architecture_raises_not_implemented(tmp_path):
    # A recognized HF model_type, but one with no entry in _CONVERTERS.
    (tmp_path / "config.json").write_text(
        '{"model_type": "gpt2", "architectures": ["GPT2LMHeadModel"]}', encoding="utf-8"
    )
    with pytest.raises(NotImplementedError):
        load_local_hooked_transformer(str(tmp_path))


def test_resolve_hf_model_snapshot_downloads_pinned_revision_into_scratch_hf_cache(tmp_path, monkeypatch):
    """ED-34: hf: is an acquisition step -- pinned repo+revision downloaded
    into $SCRATCH/hf_cache with local_files_only=True (compute nodes have
    no internet; the cache is expected warm from a login-node prefetch)."""
    monkeypatch.setenv("SCRATCH", str(tmp_path))
    calls = {}

    def fake_snapshot_download(*, repo_id, revision, cache_dir, local_files_only):
        calls["args"] = (repo_id, revision, cache_dir, local_files_only)
        return str(tmp_path / "snapshot")

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    result = resolve_hf_model_snapshot("hf:Qwen/Qwen2.5-14B-Instruct@cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8")

    assert calls["args"] == (
        "Qwen/Qwen2.5-14B-Instruct",
        "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8",
        str(tmp_path / "hf_cache"),
        True,
    )
    assert result == tmp_path / "snapshot"


def test_resolve_hf_model_snapshot_rejects_non_hf_scheme():
    with pytest.raises(uris.URIError):
        resolve_hf_model_snapshot("local:tests/fixtures/tiny_model")


def test_resolve_hf_model_snapshot_without_scratch_raises_clearly(monkeypatch):
    monkeypatch.delenv("SCRATCH", raising=False)
    with pytest.raises(uris.URIError, match="SCRATCH"):
        resolve_hf_model_snapshot("hf:Qwen/Qwen2.5-14B-Instruct@abc123")


def test_resolve_model_location_dispatches_local():
    resolved = resolve_model_location("local:tests/fixtures/tiny_model")
    assert resolved.is_dir()
    assert resolved == uris.resolve_local("local:tests/fixtures/tiny_model")


def test_resolve_model_location_dispatches_tamia(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRATCH", str(tmp_path))
    resolved = resolve_model_location("tamia:models/qwen")
    assert resolved == tmp_path / "interplab" / "models/qwen"


def test_resolve_model_location_dispatches_hf(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRATCH", str(tmp_path))

    def fake_snapshot_download(*, repo_id, revision, cache_dir, local_files_only):
        return str(tmp_path / "snapshot")

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    resolved = resolve_model_location("hf:Qwen/Qwen2.5-14B-Instruct@abc123")
    assert resolved == tmp_path / "snapshot"
