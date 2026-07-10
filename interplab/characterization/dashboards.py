"""SS5 dashboards (leaf): static per-feature "paper-style" cards + a
searchable catalog page, rendered from an already-open `FeatureIndex`.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display available on the cluster or in CI
import matplotlib.pyplot as plt

from interplab.characterization.feature_index import FeatureIndex, FeatureView


def render_feature_png(view: FeatureView, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    fig, ax = plt.subplots(figsize=(6, 4))

    bin_edges = view.activation_histogram["bin_edges_log10"]
    counts = view.activation_histogram["counts"]
    if len(bin_edges) >= 2 and counts:
        centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(counts))]
        width = bin_edges[1] - bin_edges[0]
        ax.bar(centers, counts, width=width)
    ax.set_title(f"Feature {view.feature_index} activation histogram")
    ax.set_xlabel("log10(activation)")
    ax.set_ylabel("count")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def render_feature_markdown(view: FeatureView, *, png_ref: str) -> str:
    lines = [
        f"# Feature {view.feature_index}",
        "",
        f"**corpus_max:** {view.corpus_max:.4f}  ",
        f"**firing_rate:** {view.firing_rate:.6f}  ",
        f"**autointerp_label:** {view.autointerp_label or '(none)'} "
        f"(detection_score={view.autointerp_detection_score})  ",
        f"**logit_top_tokens:** {', '.join(view.logit_top_tokens)}",
        "",
        f"![activation histogram]({png_ref})",
        "",
        "## Top-k activating examples",
        "",
    ]
    for ex in view.top_k_examples:
        lines.append(f"- `{ex['activation']:.4f}` — {ex['text']!r} (doc {ex['doc_id']}, pos {ex['token_position']})")

    lines += ["", "## Decile examples", ""]
    if not view.examples_available:
        lines.append("_(example shards not synced locally -- degraded mode)_")
    else:
        for decile in sorted(view.decile_examples):
            lines.append(f"**Decile {decile}:**")
            for ex in view.decile_examples[decile]:
                lines.append(f"- `{ex['activation']:.4f}` — {ex['text']!r}")
    return "\n".join(lines)


def render_feature(index: FeatureIndex, i: int, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    view = index.feature(i)
    png_path = render_feature_png(view, out_dir / f"feature_{i}.png")
    md_text = render_feature_markdown(view, png_ref=png_path.name)
    md_path = out_dir / f"feature_{i}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return md_path, png_path


def render_catalog(index: FeatureIndex, out_dir: str | Path) -> Path:
    """A single searchable-by-Ctrl-F markdown catalog page listing every
    feature's headline stats -- the "searchable catalog" named in the infra
    doc's SS5 description, kept simple by design (leaf, not schema-bearing)."""
    out_dir = Path(out_dir)
    lines = [
        "# Feature Catalog",
        "",
        "| feature | corpus_max | firing_rate | autointerp_label |",
        "|---|---|---|---|",
    ]
    for i in range(index.n_features):
        view = index.feature(i)
        lines.append(
            f"| {i} | {view.corpus_max:.4f} | {view.firing_rate:.6f} | {view.autointerp_label or ''} |"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = out_dir / "catalog.md"
    catalog_path.write_text("\n".join(lines), encoding="utf-8")
    return catalog_path
