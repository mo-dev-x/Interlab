"""§5 SS2 QA bands (ED-11): verdict assignment against
`schemas/store_manifest/qa_bands_v<N>.json` -- same placeholder-data-file
pattern as SS4's certification bands. `chat_divergence` is excluded on
purpose: it is recorded evidence, never gate-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

from interplab.store_qa.qa import StoreQAMetrics, norm_by_position_cv

SCHEMAS_ROOT = Path(__file__).resolve().parents[2] / "schemas"

_VERDICT_RANK = {"green": 0, "amber": 1, "red": 2}
_METRIC_VALUES = {
    "norm_by_position_cv": lambda m: norm_by_position_cv(m.norm_by_position),
    "special_token_fraction": lambda m: m.special_token_fraction,
    "adjacent_autocorrelation": lambda m: abs(m.adjacent_autocorrelation),
}


def load_bands(version: int = 1, *, schemas_root: Path = SCHEMAS_ROOT) -> dict:
    path = schemas_root / "store_manifest" / f"qa_bands_v{version}.json"
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


def apply_bands(metrics: StoreQAMetrics, bands: dict) -> tuple[str, dict]:
    """Returns `(overall_verdict, per_metric_verdicts)`. Driven by exactly
    the three specified metrics (ED-11); `chat_divergence` never
    participates."""
    per_metric = {
        name: _verdict_for(_METRIC_VALUES[name](metrics), band) for name, band in bands["metrics"].items()
    }
    overall = max(per_metric.values(), key=lambda v: _VERDICT_RANK[v]) if per_metric else "green"
    return overall, per_metric
