"""§5 SS7 control_arms (ED-3): pure spec construction from pre-resolved values."""

from interplab.interventions import InterventionSpec, control_arms

_HASH = "sha256:" + "a" * 64


def _steered_spec(**overrides) -> InterventionSpec:
    base = dict(
        kind="clamp", feature_index=9056, value_in_max_units=2.0,
        corpus_max=8.3, positions="all", checkpoint_hash=_HASH,
    )
    base.update(overrides)
    return InterventionSpec(**base)


def test_returns_exactly_two_arms():
    arms = control_arms(_steered_spec(), matched_feature_index=42, matched_feature_corpus_max=3.1, direction_seed=7)
    assert len(arms) == 2


def test_add_direction_arm_matches_steered_alpha_inputs():
    spec = _steered_spec()
    arms = control_arms(spec, matched_feature_index=42, matched_feature_corpus_max=3.1, direction_seed=7)
    add_direction_arm = arms[0]

    assert add_direction_arm.kind == "add_direction"
    assert add_direction_arm.feature_index is None
    assert add_direction_arm.value_in_max_units == spec.value_in_max_units
    assert add_direction_arm.corpus_max == spec.corpus_max
    assert add_direction_arm.direction_seed == 7
    assert add_direction_arm.positions == spec.positions
    assert add_direction_arm.checkpoint_hash == spec.checkpoint_hash


def test_matched_feature_arm_uses_its_own_corpus_max():
    spec = _steered_spec()
    arms = control_arms(spec, matched_feature_index=42, matched_feature_corpus_max=3.1, direction_seed=7)
    matched_arm = arms[1]

    assert matched_arm.kind == "clamp"
    assert matched_arm.feature_index == 42
    assert matched_arm.value_in_max_units == spec.value_in_max_units
    assert matched_arm.corpus_max == 3.1
    assert matched_arm.direction_seed is None
    assert matched_arm.positions == spec.positions
    assert matched_arm.checkpoint_hash == spec.checkpoint_hash
