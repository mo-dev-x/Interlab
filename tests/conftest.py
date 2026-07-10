from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TINY_MODEL_DIR = FIXTURES_DIR / "tiny_model"
TINY_SAE_DIR = FIXTURES_DIR / "tiny_sae"


@pytest.fixture
def created_by() -> dict:
    return {
        "run_id": "r20260708-1200-abcd",
        "code_commit": "0" * 40,
        "entrypoint": "interplab.jobs.test",
        "host": "local",
    }


def _build_tiny_hooked_transformer():
    """Wraps the pinned tiny_model fixture (a raw HF Qwen2ForCausalLM) in a
    transformer_lens.HookedTransformer, via the shared local-loading helper
    (interplab.certification.model_loading) that `certify` also uses for
    any locally-available checkpoint."""
    from interplab.certification.model_loading import load_local_hooked_transformer

    return load_local_hooked_transformer(str(TINY_MODEL_DIR))


@pytest.fixture(scope="session")
def tiny_hooked_transformer():
    # Session-scoped: attach()'s hook hygiene guarantee (tested separately)
    # means no test can leave hooks behind for another test to inherit.
    return _build_tiny_hooked_transformer()


@pytest.fixture(scope="session")
def tiny_sae():
    from sae_lens import SAE

    return SAE.load_from_pretrained(str(TINY_SAE_DIR), device="cpu")
