import pytest

from interplab.certification.model_loading import load_local_hooked_transformer

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
