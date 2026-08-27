"""Redraws of FP-1, FP-3 and FP-4 without implementation-status or population content.

These replace the hand-authored originals. They depict the pipeline, the subsystem
architecture and the artifact-dependency structure only. No status badges, no registry
counts, no per-stage "exercised / not exercised" markers.

Structure and naming follow reports/figure_corrections_spec.md, which remains the
authority for the subsystem roster (SS1-SS12), the artifact roster (A1-A12) and the
exact edge list of the provenance chain.
"""

import pathlib

# Resolved from this file, so a repository rename cannot break these paths.
REPO = pathlib.Path(__file__).resolve().parents[1]

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = str(REPO / "reports" / "pics" / "generated")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

INK = "#1a1a1a"
GREY = "#9aa0a6"
BLUE = "#2c5f8a"
GOOD = "#1e7b4f"
PURPLE = "#6a4c93"
WARN = "#b7791f"
WASH = "#eef2f6"


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


# ------------------------------------------------------------------ gen10 ---
def gen10():
    """Nine-stage experimental pipeline (redraw of FP-1)."""
    stages = [
        ("1", "Training", "train_sae.py"),
        ("2", "Activation-\nStore QA", "store_qa.py"),
        ("3", "SAE\nCertification", "scripts/certify.py"),
        ("4", "Feature Search" + chr(10) + "/ Survey", "find_features.py\nsurvey_features.py"),
        ("5", "Characterization", "characterize_lite.py"),
        ("6", "Steering\nExperiments", "steering_experiment.py\nscripts/monteal_qwen.py"),
        ("7", "LLM-Judged\nEvaluation", "Lodestar"),
        ("8", "Multilingual\nAnalysis", "multilingual_rerun.py"),
        ("9", "Report\nAssembly", "report.py"),
    ]
    W, GAP = 3.05, 0.28
    fig, ax = plt.subplots(figsize=(19.5, 6.2))
    total = len(stages) * W + (len(stages) - 1) * GAP
    ax.set_xlim(-2.2, total + 2.4)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    ax.text(-1.1, 4.15, "Raw\nCorpus", ha="center", va="center", fontsize=10.5, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GREY, lw=1.4))
    ax.text(total + 1.2, 4.15, "Final\nReport", ha="center", va="center", fontsize=10.5, color=INK,
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GREY, lw=1.4))

    xs = []
    for i, (num, name, script) in enumerate(stages):
        x0 = i * (W + GAP)
        xs.append(x0 + W / 2)
        ax.add_patch(FancyBboxPatch((x0, 3.05), W, 2.25,
                                    boxstyle="round,pad=0.04,rounding_size=0.10",
                                    fc="white", ec=BLUE, lw=1.9))
        ax.add_patch(plt.Circle((x0 + W / 2, 5.62), 0.20, fc=BLUE, ec="none"))
        ax.text(x0 + W / 2, 5.62, num, ha="center", va="center", color="white",
                fontsize=10, fontweight="bold")
        ax.text(x0 + W / 2, 4.62, name, ha="center", va="center", fontsize=9.8,
                fontweight="bold", color=INK)
        ax.add_patch(plt.Rectangle((x0 + 0.03, 3.08), W - 0.06, 0.62, fc=WASH, ec="none"))
        ax.text(x0 + W / 2, 3.39, script, ha="center", va="center", fontsize=7.0,
                color=BLUE, family="DejaVu Sans Mono", linespacing=1.35)
        if i:
            ax.add_patch(FancyArrowPatch((x0 - GAP, 4.15), (x0 - 0.02, 4.15),
                                         arrowstyle="-|>", mutation_scale=13, lw=1.5, color=INK))
    ax.add_patch(FancyArrowPatch((-0.62, 4.15), (-0.02, 4.15), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.5, color=INK))
    ax.add_patch(FancyArrowPatch((total + 0.02, 4.15), (total + 0.62, 4.15), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.5, color=INK))

    # registry spine
    ax.add_patch(FancyBboxPatch((-0.35, 1.15), total + 0.7, 0.95,
                                boxstyle="round,pad=0.05,rounding_size=0.10",
                                fc="white", ec=BLUE, lw=2.0))
    ax.text(0.35, 1.62, "Interlab Registry\n(content-addressed)", ha="left", va="center",
            fontsize=10, fontweight="bold", color=BLUE)
    for i, x in enumerate(xs):
        solid = i in (0, 2)
        ax.plot([x, x], [2.10, 3.05], lw=1.4, color=(BLUE if solid else GREY),
                ls=("-" if solid else (0, (4, 3))), zorder=1)
        ax.add_patch(plt.Circle((x, 2.10), 0.075, fc=(BLUE if solid else GREY), ec="none", zorder=3))

    ax.text(total / 2 + 1.2, 0.62,
            "A1 / A3 are written by the corpus-census lane (SS1), outside these nine stages.   "
            "A10 run cards are written by every lane job.",
            ha="center", va="center", fontsize=8.8, color="#444",
            bbox=dict(boxstyle="round,pad=0.35", fc=WASH, ec="#d8dee5", lw=1.0))

    ax.set_title("The nine-stage experimental pipeline, from SAE training through report assembly",
                 loc="left", fontsize=14, fontweight="bold", pad=16)
    save(fig, "gen10_pipeline_nine_stage.png")


# ------------------------------------------------------------------ gen11 ---
def gen11():
    """Interlab subsystem architecture SS1-SS12 (redraw of FP-3)."""
    segments = [
        ("1  Certification lane", [
            ("SS1", "Corpus & Concept", "A1 / A2 / A3"),
            ("SS2", "Store QA", "A4"),
            ("SS3", "SAE Training", "A5"),
            ("SS4", "SAE Certification", "A6"),
        ], "G1"),
        ("2  Feature characterization\n     and validation", [
            ("SS5", "Feature Characterization", "A7"),
            ("SS6", "Feature Validation", "A8"),
        ], "G2"),
        ("3  Intervention & evaluation", [
            ("SS7", "Intervention Engine", "hooks \u2192 A9"),
            ("SS8", "Behavioral Evaluation", "A9\u2032 / A12"),
        ], "G3"),
        ("4  Statistics & reports", [
            ("SS9", "Statistics & Reports", "\u2192 A11"),
        ], "G4"),
    ]
    fig, ax = plt.subplots(figsize=(16.5, 8.4))
    ax.set_xlim(0, 17.5)
    ax.set_ylim(0, 8.1)
    ax.axis("off")
    ax.set_title("Interlab: twelve subsystems, grouped by pipeline gate, "
                 "connected through the content-addressed registry",
                 loc="left", fontsize=14, fontweight="bold", pad=14)

    BW, BH, BG = 3.55, 0.80, 0.18
    x = 0.30
    for seg_name, boxes, gate in segments:
        w = BW + 0.5
        ax.add_patch(FancyBboxPatch((x - 0.16, 2.55), w, 4.90,
                                    boxstyle="round,pad=0.05,rounding_size=0.10",
                                    fc="#f7f9fb", ec="#dbe3ea", lw=1.3))
        ax.text(x + w / 2 - 0.16, 7.15, seg_name, ha="center", va="center",
                fontsize=9.6, fontweight="bold", color="#5a6570", linespacing=1.3)
        y = 6.60
        for code, name, arts in boxes:
            ax.add_patch(FancyBboxPatch((x, y - BH), BW, BH,
                                        boxstyle="round,pad=0.03,rounding_size=0.08",
                                        fc="white", ec=BLUE, lw=1.7))
            ax.text(x + 0.18, y - 0.30, code, ha="left", va="center", fontsize=10,
                    fontweight="bold", color=BLUE, family="DejaVu Sans Mono")
            ax.text(x + 0.92, y - 0.30, name, ha="left", va="center", fontsize=9.8, color=INK)
            ax.text(x + 0.92, y - 0.63, arts, ha="left", va="center", fontsize=8.4,
                    color=GREY, family="DejaVu Sans Mono")
            y -= BH + BG
        # gate marker
        ax.add_patch(FancyBboxPatch((x + BW - 0.62, 2.72), 0.86, 0.44,
                                    boxstyle="round,pad=0.03,rounding_size=0.08",
                                    fc=GOOD, ec="none"))
        ax.text(x + BW - 0.19, 2.94, gate, ha="center", va="center", fontsize=9.5,
                fontweight="bold", color="white")
        x += w + 0.30

    # registry spine
    ax.add_patch(FancyBboxPatch((0.14, 1.42), 16.85, 0.80,
                                boxstyle="round,pad=0.05,rounding_size=0.10",
                                fc="white", ec=BLUE, lw=2.0))
    ax.text(0.55, 1.82, "SS10  Experiment Registry \u2014 the content-addressed spine",
            ha="left", va="center", fontsize=10.5, fontweight="bold", color=BLUE)

    # cross-cutting bands
    for i, (code, label) in enumerate((("SS11", "QA & Regression (tests)"),
                                       ("SS12", "Orchestration (scripts + SLURM)"))):
        ax.add_patch(FancyBboxPatch((0.14 + i * 8.55, 0.42), 8.30, 0.62,
                                    boxstyle="round,pad=0.04,rounding_size=0.08",
                                    fc=WASH, ec="#c9d3dc", lw=1.2))
        ax.text(0.50 + i * 8.55, 0.73, "%s   %s" % (code, label), ha="left", va="center",
                fontsize=9.4, color="#41505c")
    ax.text(16.85, 0.12, "cross-cutting", ha="right", va="bottom", fontsize=8,
            color=GREY, style="italic")
    save(fig, "gen11_interlab_architecture.png")


# ------------------------------------------------------------------ gen12 ---
def gen12():
    """A1-A12 artifact provenance chain (redraw of FP-4).

    Edges reproduce the section 5.4 mermaid exactly. A10 and A12 sit outside the
    chain and carry no derivation arrows, per the corrections spec.
    """
    nodes = {
        "A5": (0.0, 5.15, "A5", "sae_checkpoint"),
        "A1": (0.0, 3.30, "A1", "corpus_manifest"),
        "A2": (0.0, 1.45, "A2", "concept_battery"),
        "A6": (3.60, 5.15, "A6", "sae_certificate"),
        "A3": (3.60, 3.30, "A3", "census_report"),
        "A4": (3.60, 1.45, "A4", "store_manifest"),
        "A7": (7.20, 4.25, "A7", "characterization_manifest"),
        "A8": (10.80, 2.10, "A8", "feature_certificate"),
        "A9": (14.40, 4.25, "A9", "intervention_result"),
        "A9J": (18.00, 4.25, "A9\u2032", "judged" + chr(10) + "intervention_result"),
        "A11": (21.60, 4.25, "A11", "claim_report"),
    }
    GATES = {"A6": "G1", "A8": "G2", "A11": "G4"}
    EDGES = [("A1", "A3"), ("A1", "A4"), ("A1", "A7"),
             ("A5", "A6"), ("A5", "A7"), ("A6", "A7"),
             ("A2", "A8"), ("A3", "A8"), ("A7", "A8"),
             ("A5", "A9"), ("A7", "A9"), ("A9J", "A11")]
    BW, BH = 3.15, 0.98

    fig, ax = plt.subplots(figsize=(20.5, 6.6))
    ax.set_xlim(-0.8, 25.5)
    ax.set_ylim(0, 6.6)
    ax.axis("off")
    ax.set_title("The A1\u2192A11 artifact provenance chain",
                 loc="left", fontsize=14, fontweight="bold", pad=14)

    def anchor(k, side):
        x, y, _, _ = nodes[k]
        return (x + BW, y) if side == "r" else (x, y)

    for a, b in EDGES:
        ax.add_patch(FancyArrowPatch(anchor(a, "r"), anchor(b, "l"), arrowstyle="-|>",
                                     mutation_scale=13, lw=1.35, color="#7d8b97",
                                     connectionstyle="arc3,rad=0.06", zorder=1))
    # A8 -> A9, claim mode, dashed
    ax.add_patch(FancyArrowPatch(anchor("A8", "r"), anchor("A9", "l"), arrowstyle="-|>",
                                 mutation_scale=13, lw=1.35, color=WARN, ls=(0, (5, 3)),
                                 connectionstyle="arc3,rad=0.10", zorder=1))
    ax.text(14.05, 3.16, "claim mode", fontsize=8.2, color=WARN, style="italic", ha="center")
    # A9 -> A9', judging
    ax.add_patch(FancyArrowPatch(anchor("A9", "r"), anchor("A9J", "l"), arrowstyle="-|>",
                                 mutation_scale=14, lw=1.8, color=PURPLE, zorder=2))
    ax.text(17.78, 4.98, "SS8 Lodestar judging", fontsize=8.4, color=PURPLE,
            ha="center", va="bottom", fontweight="bold")

    for k, (x, y, code, name) in nodes.items():
        ax.add_patch(FancyBboxPatch((x, y - BH / 2), BW, BH,
                                    boxstyle="round,pad=0.03,rounding_size=0.08",
                                    fc="white", ec=BLUE, lw=1.8, zorder=3))
        ax.text(x + BW / 2, y + 0.17, code, ha="center", va="center", fontsize=10.5,
                fontweight="bold", color=BLUE, family="DejaVu Sans Mono", zorder=4)
        ax.text(x + BW / 2, y - 0.20, name, ha="center", va="center", fontsize=7.4,
                color=INK, family="DejaVu Sans Mono", zorder=4, linespacing=1.35)
        if k in GATES:
            ax.add_patch(FancyBboxPatch((x + BW - 0.70, y + BH / 2 - 0.10), 0.74, 0.38,
                                        boxstyle="round,pad=0.02,rounding_size=0.06",
                                        fc=GOOD, ec="white", lw=1.2, zorder=5))
            ax.text(x + BW - 0.33, y + BH / 2 + 0.09, GATES[k], ha="center", va="center",
                    fontsize=8.6, fontweight="bold", color="white", zorder=6)

    # outside the chain
    ax.add_patch(FancyBboxPatch((0.0, 0.18), 11.0, 0.78,
                                boxstyle="round,pad=0.04,rounding_size=0.08",
                                fc=WASH, ec="#c9d3dc", lw=1.2, ls=(0, (5, 3))))
    ax.text(0.30, 0.57, "A10  run_card  \u2014  attaches to every job, not a chain node",
            ha="left", va="center", fontsize=9.2, color="#41505c", family="DejaVu Sans Mono")
    ax.add_patch(FancyBboxPatch((11.5, 0.18), 13.4, 0.78,
                                boxstyle="round,pad=0.04,rounding_size=0.08",
                                fc=WASH, ec="#c9d3dc", lw=1.2, ls=(0, (5, 3))))
    ax.text(11.80, 0.57, "A12  eval_compat_map  \u2014  authored by SS8, outside the chain, "
                         "no derivation arrows",
            ha="left", va="center", fontsize=9.2, color="#41505c", family="DejaVu Sans Mono")

    ax.text(25.4, 5.95, "G1 / G2 / G4 mark pipeline gates", ha="right", va="center",
            fontsize=8.6, color=GOOD, style="italic")
    save(fig, "gen12_provenance_chain.png")


for f in (gen10, gen11, gen12):
    f()
print("\ndone")
