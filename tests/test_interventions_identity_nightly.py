"""§8.2 test_identity's nightly extension: noop spec => bit-identical
logits and generations on a real prompt against the real base model
(§8.3: "Nightly on cluster: identity-on-Qwen, canary"). ED-23 requires the
same skip-with-reason discipline as the cheese canary: skip with an
explicit reason when the real model is not locally accessible, never omit
silently, never pass vacuously.

Availability is a read-only check, never a fetch (§8.1/ED-23 compliance
revision): the model directory comes from `INTERPLAB_NIGHTLY_QWEN_DIR`, a
local path only. No Hugging Face hub ID appears anywhere in this file, so
there is no code path capable of triggering a download -- the cluster
nightly run provides the env var pointing at the already-staged model.

`sae` is a required `attach()` parameter but is never touched for a `noop`
spec (`interplab/interventions/hooks.py`: "does not touch the stream at all
-- no hook is registered"), so the tiny fixture SAE is a safe structural
placeholder here; no real production SAE checkpoint is needed for this test.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import torch

from interplab.certification.model_loading import load_local_hooked_transformer
from interplab.interventions import InterventionSpec, attach

_HASH = "sha256:" + "a" * 64
_PROMPT = "The cheese feature fires today."
_MODEL_DIR_ENV_VAR = "INTERPLAB_NIGHTLY_QWEN_DIR"


@pytest.fixture(scope="module")
def real_qwen_hooked_transformer():
    model_dir = os.environ.get(_MODEL_DIR_ENV_VAR)
    if not model_dir or not Path(model_dir).is_dir():
        pytest.skip(
            f"{_MODEL_DIR_ENV_VAR} is unset or not a directory -- set it to a locally staged "
            "Qwen checkpoint directory to run this test (the cluster nightly run provides it)"
        )
    return load_local_hooked_transformer(model_dir)


@pytest.mark.nightly
def test_noop_bit_identical_logits_on_real_qwen(real_qwen_hooked_transformer, tiny_sae):
    model = real_qwen_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        baseline = model(ids)

    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    with torch.no_grad(), attach(model, tiny_sae, spec):
        noop_logits = model(ids)

    assert torch.equal(baseline, noop_logits)


@pytest.mark.nightly
def test_noop_bit_identical_generation_on_real_qwen(real_qwen_hooked_transformer, tiny_sae):
    model = real_qwen_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        baseline_gen = model.generate(ids, max_new_tokens=5, do_sample=False, verbose=False)

    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    with torch.no_grad(), attach(model, tiny_sae, spec):
        noop_gen = model.generate(ids, max_new_tokens=5, do_sample=False, verbose=False)

    assert torch.equal(baseline_gen, noop_gen)
