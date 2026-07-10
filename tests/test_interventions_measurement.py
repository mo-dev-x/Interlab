"""§5 SS7 measurement clause: attach() returns an object that, after
context exit, exposes per-call statistics (injected delta norm, residual
norm) for each hook invocation. noop exposes empty statistics.
"""

import torch

from interplab.interventions import InterventionSpec, attach

_HASH = "sha256:" + "a" * 64
_PROMPT = "The cheese feature fires today."


def test_noop_has_empty_stats(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    handle = attach(tiny_hooked_transformer, tiny_sae, spec)
    with handle:
        pass
    assert handle.stats == []


def test_stats_available_after_context_exit(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    spec = InterventionSpec(kind="ablate", feature_index=0, value_in_max_units=None, corpus_max=None, positions="all", checkpoint_hash=_HASH)

    handle = attach(model, tiny_sae, spec)
    with torch.no_grad(), handle:
        model(ids)

    # accessed after __exit__ has already run
    assert len(handle.stats) == 1


def test_one_record_per_hook_invocation(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    spec = InterventionSpec(kind="clamp", feature_index=0, value_in_max_units=2.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH)

    with torch.no_grad(), attach(model, tiny_sae, spec) as handle:
        model(ids)
        model(ids)

    assert len(handle.stats) == 2
    for record in handle.stats:
        assert record.delta_norm > 0.0
        assert record.residual_norm > 0.0


def test_add_direction_records_stats(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    spec = InterventionSpec(
        kind="add_direction", feature_index=None, value_in_max_units=2.0,
        corpus_max=1.0, positions="all", checkpoint_hash=_HASH, direction_seed=3,
    )

    with torch.no_grad(), attach(model, tiny_sae, spec) as handle:
        model(ids)

    assert len(handle.stats) == 1
    assert handle.stats[0].delta_norm > 0.0
    assert handle.stats[0].residual_norm > 0.0


def test_fully_masked_call_records_zero_delta_norm(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    spec = InterventionSpec(
        kind="clamp", feature_index=0, value_in_max_units=2.0, corpus_max=1.0,
        positions="generated_only", checkpoint_hash=_HASH,
    )

    with torch.no_grad(), attach(model, tiny_sae, spec, prompt_lengths=ids.shape[1] + 1000) as handle:
        model(ids)

    assert len(handle.stats) == 1
    assert handle.stats[0].delta_norm == 0.0
    assert handle.stats[0].residual_norm > 0.0


def test_stats_property_returns_a_copy(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    spec = InterventionSpec(kind="ablate", feature_index=0, value_in_max_units=None, corpus_max=None, positions="all", checkpoint_hash=_HASH)

    with torch.no_grad(), attach(model, tiny_sae, spec) as handle:
        model(ids)

    handle.stats.append("mutation should not stick")
    assert len(handle.stats) == 1
