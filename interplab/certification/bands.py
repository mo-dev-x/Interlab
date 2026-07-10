"""§5 SS4 bands: verdict assignment against `schemas/sae_certificate/bands_v<N>.json`.

Band *values* are placeholders (§10 item 1) -- calibration is explicitly
out of scope for WP2. Recalibration is a data change to that file plus a
`schema_version` bump on `sae_certificate` (D3), never a code change.
"""

from __future__ import annotations

import json
from pathlib import Path

from interplab.certification.metrics import CertificationMetrics

SCHEMAS_ROOT = Path(__file__).resolve().parents[2] / "schemas"

_VERDICT_RANK = {"green": 0, "amber": 1, "red": 2}


def load_bands(version: int = 1, *, schemas_root: Path = SCHEMAS_ROOT) -> dict:
    path = schemas_root / "sae_certificate" / f"bands_v{version}.json"
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


def apply_bands(metrics: CertificationMetrics, bands: dict) -> tuple[str, dict]:
    """Returns `(overall_verdict, per_metric_verdicts)`. Overall is the
    worst (highest-severity) of the banded per-metric verdicts -- a single
    red metric makes the certificate red, regardless of the others."""
    per_metric = {name: _verdict_for(getattr(metrics, name), band) for name, band in bands["metrics"].items()}
    overall = max(per_metric.values(), key=lambda v: _VERDICT_RANK[v]) if per_metric else "green"
    return overall, per_metric
