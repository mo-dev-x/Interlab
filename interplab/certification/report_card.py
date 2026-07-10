"""§5 SS4 report card: one-page md + png summary of a certificate --
density histogram, FVU-by-position, headline numbers with band verdicts.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display available on the cluster or in CI
import matplotlib.pyplot as plt

from interplab.certification.metrics import CertificationMetrics


def render_png(metrics: CertificationMetrics, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    bin_edges = metrics.density_histogram["bin_edges_log10"]
    counts = metrics.density_histogram["counts"]
    if len(bin_edges) >= 2 and counts:
        centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(counts))]
        width = bin_edges[1] - bin_edges[0]
        axes[0].bar(centers, counts, width=width)
    axes[0].set_title("Feature density (log10 firing rate)")
    axes[0].set_xlabel("log10(firing rate)")
    axes[0].set_ylabel("feature count")

    axes[1].plot(range(len(metrics.per_position_fvu)), metrics.per_position_fvu)
    axes[1].set_title("FVU by position")
    axes[1].set_xlabel("sequence position")
    axes[1].set_ylabel("FVU")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def render_markdown(
    metrics: CertificationMetrics,
    verdict: str,
    per_metric_verdicts: dict,
    *,
    checkpoint_hash: str,
    bands_version: int,
    png_ref: str,
) -> str:
    def _row(name: str, value: float) -> str:
        return f"| {name} | {value:.4f} | {per_metric_verdicts.get(name, '-')} |"

    lines = [
        "# SAE Certificate Report Card",
        "",
        f"**Checkpoint:** `{checkpoint_hash}`  ",
        f"**Verdict:** **{verdict.upper()}** (bands v{bands_version})",
        "",
        "| Metric | Value | Verdict |",
        "|---|---|---|",
        _row("ce_recovered", metrics.ce_recovered),
        _row("fvu", metrics.fvu),
        _row("dead_fraction", metrics.dead_fraction),
        _row("max_decoder_cosine_p999", metrics.max_decoder_cosine_p999),
        "",
        f"![density and FVU]({png_ref})",
        "",
    ]
    return "\n".join(lines)


def render(
    metrics: CertificationMetrics,
    verdict: str,
    per_metric_verdicts: dict,
    *,
    checkpoint_hash: str,
    bands_version: int,
    out_dir: str | Path,
    basename: str = "report_card",
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    png_path = render_png(metrics, out_dir / f"{basename}.png")
    md_text = render_markdown(
        metrics,
        verdict,
        per_metric_verdicts,
        checkpoint_hash=checkpoint_hash,
        bands_version=bands_version,
        png_ref=png_path.name,
    )
    md_path = out_dir / f"{basename}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return md_path, png_path
