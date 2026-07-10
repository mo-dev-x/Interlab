from interplab.certification.metrics import CertificationMetrics
from interplab.certification.report_card import render


def _metrics() -> CertificationMetrics:
    return CertificationMetrics(
        ce_recovered=0.97,
        fvu=0.05,
        dead_fraction=0.02,
        density_histogram={"bin_edges_log10": [-3.0, -2.0, -1.0], "counts": [5, 10]},
        max_decoder_cosine_p999=0.3,
        per_position_fvu=[0.05, 0.06, 0.04],
    )


def test_render_writes_md_and_png(tmp_path):
    md_path, png_path = render(
        _metrics(),
        "green",
        {"ce_recovered": "green", "fvu": "green", "dead_fraction": "green", "max_decoder_cosine_p999": "green"},
        checkpoint_hash="sha256:" + "a" * 64,
        bands_version=1,
        out_dir=tmp_path,
    )
    assert md_path.is_file()
    assert png_path.is_file()
    assert png_path.stat().st_size > 0


def test_markdown_contains_verdict_and_checkpoint_hash(tmp_path):
    md_path, _ = render(
        _metrics(),
        "amber",
        {"ce_recovered": "amber"},
        checkpoint_hash="sha256:" + "b" * 64,
        bands_version=1,
        out_dir=tmp_path,
    )
    text = md_path.read_text(encoding="utf-8")
    assert "AMBER" in text
    assert "sha256:" + "b" * 64 in text
    assert "0.9700" in text  # ce_recovered value formatted


def test_render_handles_empty_histogram(tmp_path):
    metrics = CertificationMetrics(
        ce_recovered=0.5, fvu=0.5, dead_fraction=1.0,
        density_histogram={"bin_edges_log10": [], "counts": []},
        max_decoder_cosine_p999=0.0, per_position_fvu=[],
    )
    md_path, png_path = render(
        metrics, "red", {}, checkpoint_hash="sha256:" + "c" * 64, bands_version=1, out_dir=tmp_path
    )
    assert md_path.is_file()
    assert png_path.is_file()
