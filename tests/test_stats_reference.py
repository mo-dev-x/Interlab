"""§8.2 test_stats_reference (hard): bootstrap/BH against precomputed
reference values.

Golden file is generated once and committed
(tests/golden/generate_stats_reference.py, same discipline as §8.1's
fixtures / test_delta_golden) -- this test never regenerates it, only
compares live `interplab.stats` output against the pinned reference.
`interplab.stats` itself is pure-numpy; the reference values were computed
against `scipy` (a dev-only dependency) purely as an independent
cross-check when the golden file was generated.
"""

import json
from pathlib import Path

import numpy as np

from interplab.stats import bh_fdr, bootstrap_ci

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "stats_reference.json"


def _reference() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_bh_fdr_matches_pinned_reference():
    ref = _reference()["bh_fdr_case"]
    mask = bh_fdr(ref["pvalues"], q=ref["q"])
    assert mask.tolist() == ref["expected_mask"]


def test_bootstrap_ci_matches_pinned_scipy_reference_within_tolerance():
    ref = _reference()["bootstrap_ci_case"]
    values = np.array(ref["values"], dtype=np.float64)
    groups = np.arange(len(values))  # degenerate case: one observation per group

    ci = bootstrap_ci(values, groups, n_boot=ref["n_boot"], level=ref["level"], seed=ref["seed"])

    assert ci.ci_low == ref["our_ci_low"], "our own implementation drifted from its own pinned output"
    assert ci.ci_high == ref["our_ci_high"]

    tol = ref["tolerance"]
    assert abs(ci.ci_low - ref["scipy_ci_low"]) < tol, "bootstrap lower bound diverged from the scipy reference"
    assert abs(ci.ci_high - ref["scipy_ci_high"]) < tol, "bootstrap upper bound diverged from the scipy reference"
