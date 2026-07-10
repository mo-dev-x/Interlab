"""ED-3/ED-4 attach-time contract checks: violations raise at attach time,
never mid-generation."""

import pytest

from interplab.interventions import InterventionSpec, attach

_HASH = "sha256:" + "a" * 64


def test_generated_only_requires_prompt_lengths(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(kind="clamp", feature_index=0, value_in_max_units=1.0, corpus_max=1.0, positions="generated_only", checkpoint_hash=_HASH)
    with pytest.raises(ValueError):
        attach(tiny_hooked_transformer, tiny_sae, spec)


def test_all_positions_forbids_prompt_lengths(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(kind="clamp", feature_index=0, value_in_max_units=1.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH)
    with pytest.raises(ValueError):
        attach(tiny_hooked_transformer, tiny_sae, spec, prompt_lengths=3)


def test_add_direction_requires_direction_seed(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(kind="add_direction", feature_index=None, value_in_max_units=1.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH)
    with pytest.raises(ValueError):
        attach(tiny_hooked_transformer, tiny_sae, spec)


def test_non_add_direction_forbids_direction_seed(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(kind="clamp", feature_index=0, value_in_max_units=1.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH, direction_seed=1)
    with pytest.raises(ValueError):
        attach(tiny_hooked_transformer, tiny_sae, spec)
