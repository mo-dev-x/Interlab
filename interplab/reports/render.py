"""SS9 renderer (leaf, §5.SS9): md + self-contained HTML, stamp in the
header and on every figure. WP6 emits text-only reports (no plotting
library requirement stated anywhere in scope for this package); `figures`
is legitimately `[]` until a later package adds dose-response plots --
`payload.figures` stays an array either way, never fabricated entries.
"""

from __future__ import annotations

import html as html_escape

from interplab.reports.chain import ChainRow
from interplab.reports.statistics import EffectSizeEntry


def _chain_table_md(rows: list[ChainRow]) -> str:
    lines = ["| link | status | artifact_hash | note |", "|---|---|---|---|"]
    for row in rows:
        h = row.artifact_hash[:19] + "…" if row.artifact_hash else "—"
        note = (row.note or "").replace("|", "\\|")
        lines.append(f"| {row.link} | {row.status} | {h} | {note} |")
    return "\n".join(lines)


def _statistics_table_md(statistics: dict | None) -> str:
    if not statistics:
        return "_No statistics: no anchor payload carries per-prompt scores._"
    lines = ["| metric | estimate | ci_low | ci_high | n_prompts | n_seeds | method |", "|---|---|---|---|---|---|---|"]
    for key, s in statistics.items():
        lines.append(
            f"| {key} | {s['estimate']:.4f} | {s['ci_low']:.4f} | {s['ci_high']:.4f} | "
            f"{s['n_prompts']} | {s['n_seeds']} | {s['method']} |"
        )
    return "\n".join(lines)


def _effect_size_table_md(effect_sizes: list[EffectSizeEntry]) -> str:
    if not effect_sizes:
        return "_No effect sizes computed._"
    lines = ["| arm | scale | vs | cohen's d | n_prompts | n_seeds |", "|---|---|---|---|---|---|"]
    for e in effect_sizes:
        lines.append(f"| {e.arm} | {e.scale} | {e.baseline_arm} | {e.d:.4f} | {e.n_prompts} | {e.n_seeds} |")
    return "\n".join(lines)


def render_markdown(
    *, question: str, stamp: str, rows: list[ChainRow], statistics: dict | None, effect_sizes: list[EffectSizeEntry]
) -> str:
    return (
        f"# Claim Report — {stamp}\n\n"
        f"**Question:** {question}\n\n"
        f"## Chain\n\n{_chain_table_md(rows)}\n\n"
        f"## Statistics\n\n{_statistics_table_md(statistics)}\n\n"
        f"## Effect sizes (Cohen's d, no CI -- see notes)\n\n{_effect_size_table_md(effect_sizes)}\n"
    )


def render_html(markdown_text: str, *, stamp: str) -> str:
    """Self-contained HTML: no external assets, stamp banner + escaped
    markdown body (a plain <pre> block -- no markdown-to-HTML dependency
    is part of this package's scope)."""
    banner_color = "#1a7f37" if stamp == "CERTIFIED" else "#9a6700"
    escaped = html_escape.escape(markdown_text)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>Claim Report — {html_escape.escape(stamp)}</title></head><body>"
        f'<div style="background:{banner_color};color:white;padding:8px 16px;font-family:sans-serif;">'
        f"{html_escape.escape(stamp)}</div>"
        f'<pre style="white-space:pre-wrap;font-family:monospace;padding:16px;">{escaped}</pre>'
        "</body></html>"
    )
