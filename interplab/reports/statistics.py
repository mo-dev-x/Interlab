"""ED-17 statistics composition: `interplab.stats` primitives applied to
anchor payloads only -- assembly and statistics never call Lodestar or
require live judge access (§5.SS9). Inputs come only from
`intervention_result.payload.lodestar.per_prompt_scores`; absent scores
=> `statistics: None` (the ED-9 idiom: absence, never fabricated numbers).

`capability_delta` is intentionally not composed here: its shape is `{...}`
-- genuinely unspecified anywhere in the blueprint, not touched by ED-17 --
so there is no per-prompt structure to bootstrap over yet. This mirrors
WP5's sensitivity precedent (an instrument stays unimplemented, honestly,
until its data shape exists), not a WP6 shortcut.

The frozen A11 `statistics` payload shape (`{estimate, ci_low, ci_high,
n_prompts, n_seeds, method}` per key, unchanged by ED-17) only fits
`bootstrap_ci` (has a CI) and `seed_variance` (contributes n_seeds); Cohen's
d has no interval by design of the frozen `stats.effect_size` primitive, so
folding it into that shape would mean fabricating ci_low=ci_high=d --
forbidden by this codebase's ED-9 discipline. Effect sizes are therefore
returned separately, for the renderer's narrative text only, not written
into `payload.statistics`.
"""

from __future__ import annotations

import dataclasses

from interplab.stats import stats as stats_mod

_METRIC = "lodestar_score"


@dataclasses.dataclass(frozen=True)
class EffectSizeEntry:
    arm: str
    scale: float
    baseline_arm: str
    d: float
    n_prompts: int
    n_seeds: int


def _per_prompt_entries(anchor_artifacts: list[dict | None]) -> list[list[dict]]:
    """One list of per-prompt-score dicts per anchor that actually has them."""
    out = []
    for artifact in anchor_artifacts:
        if artifact is None:
            continue
        lodestar = artifact["payload"].get("lodestar")
        if not lodestar or not lodestar.get("per_prompt_scores"):
            continue
        out.append(lodestar["per_prompt_scores"])
    return out


def _pool(scores_by_anchor: list[list[dict]], *, arm: str, scale: float) -> tuple[list[float], list[str], list[float]]:
    """Pooled (values, groups) across every anchor replicate for one (arm,
    scale), plus the per-anchor mean list `seed_variance` needs."""
    pooled_values: list[float] = []
    pooled_groups: list[str] = []
    per_anchor_means: list[float] = []
    for scores in scores_by_anchor:
        matching = [e for e in scores if e["arm"] == arm and e["scale"] == scale]
        if not matching:
            continue
        pooled_values.extend(e["score"] for e in matching)
        pooled_groups.extend(e["prompt_id"] for e in matching)
        per_anchor_means.append(sum(e["score"] for e in matching) / len(matching))
    return pooled_values, pooled_groups, per_anchor_means


def compose_statistics(anchor_artifacts: list[dict | None]) -> tuple[dict | None, list[EffectSizeEntry]]:
    """Returns `(statistics_payload, effect_sizes)`. `statistics_payload`
    matches A11's frozen per-key shape exactly (or is `None`, honestly, if
    no anchor carries per-prompt scores). `effect_sizes` is supplementary,
    for the renderer only."""
    scores_by_anchor = _per_prompt_entries(anchor_artifacts)
    if not scores_by_anchor:
        return None, []

    combos = sorted({(e["arm"], e["scale"]) for scores in scores_by_anchor for e in scores})

    statistics: dict[str, dict] = {}
    effect_sizes: list[EffectSizeEntry] = []
    baseline_arm = "baseline"

    for arm, scale in combos:
        values, groups, per_anchor_means = _pool(scores_by_anchor, arm=arm, scale=scale)
        if not values:
            continue

        ci = stats_mod.bootstrap_ci(values, groups)
        sv = stats_mod.seed_variance(per_anchor_means)
        key = f"{_METRIC}|arm={arm}|scale={scale}"
        statistics[key] = {
            "estimate": ci.estimate,
            "ci_low": ci.ci_low,
            "ci_high": ci.ci_high,
            "n_prompts": len(set(groups)),
            "n_seeds": sv.n_seeds,
            "method": "bootstrap_ci+seed_variance",
        }

        if arm == baseline_arm:
            continue
        base_values, base_groups, _ = _pool(scores_by_anchor, arm=baseline_arm, scale=scale)
        if not base_values:
            continue
        common_prompts = sorted(set(groups) & set(base_groups))
        if len(common_prompts) < 2:
            continue
        a_vals = [sum(v for v, g in zip(values, groups, strict=True) if g == pid) / groups.count(pid) for pid in common_prompts]
        b_vals = [sum(v for v, g in zip(base_values, base_groups, strict=True) if g == pid) / base_groups.count(pid) for pid in common_prompts]
        try:
            eff = stats_mod.effect_size(a_vals, b_vals, common_prompts)
        except stats_mod.DegenerateEffectError:
            continue  # undefined for this arm/scale -- omitted, never fabricated
        effect_sizes.append(EffectSizeEntry(
            arm=arm, scale=scale, baseline_arm=baseline_arm, d=eff.d,
            n_prompts=len(common_prompts), n_seeds=sv.n_seeds,
        ))

    return (statistics or None), effect_sizes
