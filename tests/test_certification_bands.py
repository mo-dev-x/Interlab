"""§5 SS4 bands: verdict assignment (bands_v1.json values are placeholders,
§10 item 1 -- these tests check the assignment LOGIC, not calibration)."""

from interplab.certification.bands import apply_bands, load_bands
from interplab.certification.metrics import CertificationMetrics


def _metrics(**overrides) -> CertificationMetrics:
    base = dict(
        ce_recovered=0.97,
        fvu=0.05,
        dead_fraction=0.02,
        density_histogram={"bin_edges_log10": [], "counts": []},
        max_decoder_cosine_p999=0.3,
        per_position_fvu=[],
    )
    base.update(overrides)
    return CertificationMetrics(**base)


def test_bands_v1_file_loads_and_has_expected_shape():
    bands = load_bands(1)
    assert bands["bands_version"] == 1
    assert "ce_recovered" in bands["metrics"]
    assert "dead_fraction" in bands["metrics"]


def test_all_green_metrics_give_green_overall():
    bands = load_bands(1)
    overall, per_metric = apply_bands(_metrics(), bands)
    assert overall == "green"
    assert all(v == "green" for v in per_metric.values())


def test_one_red_metric_makes_overall_red():
    bands = load_bands(1)
    overall, per_metric = apply_bands(_metrics(ce_recovered=0.5), bands)
    assert per_metric["ce_recovered"] == "red"
    assert overall == "red"


def test_amber_metric_without_red_gives_amber_overall():
    bands = load_bands(1)
    overall, per_metric = apply_bands(_metrics(dead_fraction=0.10), bands)
    assert per_metric["dead_fraction"] == "amber"
    assert overall == "amber"


def test_red_outranks_amber_in_overall_verdict():
    bands = load_bands(1)
    overall, _ = apply_bands(_metrics(dead_fraction=0.10, ce_recovered=0.5), bands)
    assert overall == "red"


def test_higher_is_better_boundary_is_inclusive_green():
    bands = load_bands(1)
    _, per_metric = apply_bands(_metrics(ce_recovered=0.95), bands)
    assert per_metric["ce_recovered"] == "green"


def test_lower_is_better_boundary_is_inclusive_green():
    bands = load_bands(1)
    _, per_metric = apply_bands(_metrics(dead_fraction=0.05), bands)
    assert per_metric["dead_fraction"] == "green"
