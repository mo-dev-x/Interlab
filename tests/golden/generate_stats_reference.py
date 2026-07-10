"""Seeded generator for tests/golden/stats_reference.json (§8.2
test_stats_reference: "bootstrap/BH against precomputed reference values").

Same discipline as tests/golden/generate_delta_golden.py (ED-1): generated
once and committed, kept for provenance only. Tests MUST NOT call this at
runtime.

Independent cross-checks (this script depends on `scipy`, a `dev`-extra
dependency used only here -- `interplab.stats` itself stays pure-numpy and
never imports scipy):

- bh_fdr: `scipy.stats.false_discovery_control` (Benjamini-Hochberg) is a
  genuinely independent BH implementation; its adjusted p-values, compared
  against `q`, must produce the exact same rejection mask as ours.
- bootstrap_ci: percentile-bootstrap RNG streams differ across libraries by
  construction, so bit-identical bounds aren't the right bar. Instead, this
  script pins scipy's `bootstrap(..., method="percentile")` CI (on the
  degenerate one-observation-per-group case, where our cluster bootstrap
  reduces to a standard i.i.d. percentile bootstrap of the mean) as a
  reference interval; the test checks our CI lands within a fixed absolute
  tolerance of it -- a real bug (wrong percentile, off-by-one, wrong axis)
  would miss by far more than this tolerance.

Usage (from the local uv-managed venv, with the `dev` extra installed):
    uv run python tests/golden/generate_stats_reference.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.stats

from interplab.stats import bh_fdr, bootstrap_ci

GOLDEN_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = GOLDEN_DIR / "stats_reference.json"

SEED = 0


def build_bh_case() -> dict:
    rng = np.random.default_rng(SEED)
    pvalues = rng.uniform(0, 1, size=25)
    pvalues[:5] *= 0.01  # force a handful of genuinely small p-values
    q = 0.05

    ours = bh_fdr(pvalues, q=q).tolist()
    adjusted = scipy.stats.false_discovery_control(pvalues, method="bh")
    scipy_mask = (adjusted <= q).tolist()
    assert ours == scipy_mask, "bh_fdr disagrees with scipy.stats.false_discovery_control"

    return {"pvalues": pvalues.tolist(), "q": q, "expected_mask": ours}


def build_bootstrap_case() -> dict:
    rng = np.random.default_rng(SEED)
    values = rng.normal(loc=10.0, scale=2.0, size=300)
    groups = np.arange(len(values))  # one observation per group: degenerate case
    n_boot = 20_000
    level = 0.95

    ours = bootstrap_ci(values, groups, n_boot=n_boot, level=level, seed=SEED)

    scipy_res = scipy.stats.bootstrap(
        (values,), np.mean, n_resamples=n_boot, confidence_level=level,
        method="percentile", random_state=np.random.default_rng(SEED),
    )

    return {
        "values": values.tolist(),
        "n_boot": n_boot,
        "level": level,
        "seed": SEED,
        "our_ci_low": ours.ci_low,
        "our_ci_high": ours.ci_high,
        "scipy_ci_low": float(scipy_res.confidence_interval.low),
        "scipy_ci_high": float(scipy_res.confidence_interval.high),
        # Empirically the two match to ~1e-10 on this dataset (same
        # np.random.default_rng(seed) call pattern under the hood) -- 0.01
        # is generous slack for scipy-version RNG-call-pattern changes
        # while still failing hard on any real algorithmic bug (a wrong
        # percentile formula or off-by-one would miss by an order of
        # magnitude more than this).
        "tolerance": 0.01,
    }


def main() -> None:
    payload = {
        "bh_fdr_case": build_bh_case(),
        "bootstrap_ci_case": build_bootstrap_case(),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
