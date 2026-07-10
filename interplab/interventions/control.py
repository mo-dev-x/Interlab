"""§5 SS7 `control_arms` (ED-3): pure spec construction from pre-resolved
values -- no `FeatureIndex` access in this package (§1 edges:
`interventions -> core` only). Selection of the matched-frequency feature
happens caller-side via `FeatureIndex.sample_matched_frequency` (SS5, not
yet built); `jobs.steer` records the chosen index and sampling seed in A9.
"""

from __future__ import annotations

from interplab.interventions.spec import InterventionSpec


def control_arms(
    spec: InterventionSpec,
    *,
    matched_feature_index: int,
    matched_feature_corpus_max: float,
    direction_seed: int,
) -> list[InterventionSpec]:
    """Returns exactly two hooked control-arm specs (ED-3):
    the add_direction arm (value_in_max_units/corpus_max copied from `spec`
    so the resolved alpha matches) and the matched-frequency clamp arm (same
    value_in_max_units, its own corpus_max). The prompt-baseline arm is not
    an InterventionSpec -- it is assembled at the job level with no hook.
    """
    add_direction_arm = InterventionSpec(
        kind="add_direction",
        feature_index=None,
        value_in_max_units=spec.value_in_max_units,
        corpus_max=spec.corpus_max,
        positions=spec.positions,
        checkpoint_hash=spec.checkpoint_hash,
        direction_seed=direction_seed,
    )
    matched_feature_arm = InterventionSpec(
        kind="clamp",
        feature_index=matched_feature_index,
        value_in_max_units=spec.value_in_max_units,
        corpus_max=matched_feature_corpus_max,
        positions=spec.positions,
        checkpoint_hash=spec.checkpoint_hash,
        direction_seed=None,
    )
    return [add_direction_arm, matched_feature_arm]
