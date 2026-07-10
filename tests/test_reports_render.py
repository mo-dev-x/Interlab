"""SS9 renderer (leaf): md + self-contained HTML, stamp in header."""

from __future__ import annotations

from interplab.reports.chain import ChainRow
from interplab.reports.render import render_html, render_markdown
from interplab.reports.statistics import EffectSizeEntry


def test_render_markdown_includes_question_stamp_and_chain_rows():
    rows = [
        ChainRow(link="intervention_result", artifact_hash="sha256:" + "1" * 64, status="ok", note=None),
        ChainRow(link="feature_certificate", artifact_hash=None, status="missing", note="not found"),
    ]
    md = render_markdown(
        question="does zorbium-9 respond to steering?",
        stamp="DRAFT — UNCERTIFIED CHAIN",
        rows=rows,
        statistics=None,
        effect_sizes=[],
    )
    assert "does zorbium-9 respond to steering?" in md
    assert "DRAFT — UNCERTIFIED CHAIN" in md
    assert "intervention_result" in md and "ok" in md
    assert "feature_certificate" in md and "missing" in md
    assert "not found" in md
    assert "No statistics" in md


def test_render_markdown_includes_statistics_and_effect_sizes():
    statistics = {
        "lodestar_score|arm=steered|scale=1.0": {
            "estimate": 0.5, "ci_low": 0.3, "ci_high": 0.7, "n_prompts": 10, "n_seeds": 2, "method": "bootstrap_ci+seed_variance",
        }
    }
    effects = [EffectSizeEntry(arm="steered", scale=1.0, baseline_arm="baseline", d=1.2, n_prompts=10, n_seeds=2)]
    md = render_markdown(question="?", stamp="CERTIFIED", rows=[], statistics=statistics, effect_sizes=effects)
    assert "lodestar_score|arm=steered|scale=1.0" in md
    assert "1.2000" in md


def test_render_html_is_self_contained_and_escapes_content():
    md = "# Title\n<script>alert(1)</script>"
    out = render_html(md, stamp="CERTIFIED")
    assert "<!doctype html>" in out.lower()
    assert "CERTIFIED" in out
    assert "<script>alert(1)</script>" not in out  # escaped, not executable
    assert "&lt;script&gt;" in out
    # no external asset references (self-contained, §5.SS9 renderer requirement)
    assert "http://" not in out and "https://" not in out
