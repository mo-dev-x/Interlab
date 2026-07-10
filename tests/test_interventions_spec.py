import dataclasses

import pytest

from interplab.interventions import InterventionSpec, from_dict, to_dict

_HASH = "sha256:" + "a" * 64


def test_round_trip_noop():
    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    assert from_dict(to_dict(spec)) == spec


def test_round_trip_clamp():
    spec = InterventionSpec(
        kind="clamp", feature_index=9056, value_in_max_units=2.0,
        corpus_max=8.3, positions="all", checkpoint_hash=_HASH,
    )
    assert from_dict(to_dict(spec)) == spec


def test_round_trip_add_direction():
    spec = InterventionSpec(
        kind="add_direction", feature_index=None, value_in_max_units=2.0,
        corpus_max=1.0, positions="generated_only", checkpoint_hash=_HASH,
        direction_seed=7,
    )
    assert from_dict(to_dict(spec)) == spec


def test_direction_seed_defaults_to_none():
    spec = InterventionSpec(
        kind="clamp", feature_index=0, value_in_max_units=1.0,
        corpus_max=1.0, positions="all", checkpoint_hash=_HASH,
    )
    assert spec.direction_seed is None


def test_frozen():
    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.kind = "clamp"
