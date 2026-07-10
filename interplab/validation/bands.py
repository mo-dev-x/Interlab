"""§5 SS6 bands (placeholder data file, calibrated on the first real
validation batch -- same SS4/SS2 bands pattern): verdict assignment against
`schemas/feature_certificate/bands_v1.json`.

ED-13: the verdict grades *available* instruments and records exactly which
ones fed it in `verdict_basis`. `cross_lingual_firing` never participates --
descriptive only, by construction (it's simply never read here).
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMAS_ROOT = Path(__file__).resolve().parents[2] / "schemas"

_VERDICT_RANK = {"green": 0, "amber": 1, "red": 2}
_BASIS_ORDER = ["specificity", "sensitivity", "selectivity", "probe"]


def load_bands(version: int = 1, *, schemas_root: Path = SCHEMAS_ROOT) -> dict:
    path = schemas_root / "feature_certificate" / f"bands_v{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _verdict_for(value: float, band: dict) -> str:
    direction = band["direction"]
    if direction == "higher_is_better":
        if value >= band["green_min"]:
            return "green"
        if value >= band["amber_min"]:
            return "amber"
        return "red"
    if direction == "lower_is_better":
        if value <= band["green_max"]:
            return "green"
        if value <= band["amber_max"]:
            return "amber"
        return "red"
    raise ValueError(f"unknown band direction: {direction!r}")


def apply_bands(
    *, specificity: dict, sensitivity: dict, selectivity: dict, probe: dict, bands: dict,
) -> tuple[str, list[str]]:
    """Returns `(overall_verdict, verdict_basis)`. Only instruments with
    data to grade participate; `verdict_basis` names exactly which ones."""
    per_metric: dict[str, str] = {}
    available: set[str] = set()

    decile_means = specificity["decile_means"]
    if decile_means:
        per_metric["specificity_top_decile_mean"] = _verdict_for(
            decile_means[-1], bands["metrics"]["specificity_top_decile_mean"]
        )
        available.add("specificity")

    if sensitivity["status"] == "measured":
        per_metric["sensitivity_word_absent_fire_rate"] = _verdict_for(
            sensitivity["word_absent_fire_rate"], bands["metrics"]["sensitivity_word_absent_fire_rate"]
        )
        available.add("sensitivity")

    neighbors = selectivity["neighbors"]
    if neighbors:
        max_cosine = max(n["cosine"] for n in neighbors)
        per_metric["selectivity_max_neighbor_cosine"] = _verdict_for(
            max_cosine, bands["metrics"]["selectivity_max_neighbor_cosine"]
        )
        available.add("selectivity")

    per_metric["probe_gap_abs"] = _verdict_for(abs(probe["gap"]), bands["metrics"]["probe_gap_abs"])
    available.add("probe")

    overall = max(per_metric.values(), key=lambda v: _VERDICT_RANK[v]) if per_metric else "green"
    verdict_basis = [name for name in _BASIS_ORDER if name in available]
    return overall, verdict_basis
