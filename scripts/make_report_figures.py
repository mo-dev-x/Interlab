"""Generate the Tier-1/Tier-2 figures the report corpus has never had.

Every value plotted here is quoted from a source document in reports/ and is
annotated in-figure with the Part it came from. Nothing is invented: where a
per-point series does not exist in the sources (e.g. the 35 individual dose
contrasts), the figure plots the summary statistics the sources DO give and
says so on its face rather than simulating points.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = r"d:\qwen-sae-interp\reports\pics\generated"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

INK = "#1a1a1a"
GREY = "#9aa0a6"
CHOICE = "#7b8794"     # the analyst's unstated choice
EFFECT = "#c0392b"     # what would have been reported
GOOD = "#1e7b4f"
WARN = "#b7791f"
BLUE = "#2c5f8a"


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


def src(ax, text):
    ax.annotate(text, xy=(1.0, -0.42), xycoords="axes fraction", ha="right", va="top",
                fontsize=8, color=GREY, style="italic")


# ---------------------------------------------------------------- gen01 ----
def gen01():
    """The headline: four stages where an unstated analyst choice moves the answer."""
    fig, axes = plt.subplots(4, 1, figsize=(9.5, 12.5))
    fig.suptitle("At four independent stages, a silent analyst choice moves the reported answer\n"
                 "by more than the effect anyone would report from it",
                 fontsize=15, fontweight="bold", y=0.995)
    fig.text(0.5, 0.934,
             "Four different units. They are deliberately NOT put on a common axis — the point is "
             "that each stage\nhas its own currency, and the displacement dominates in every one of them.",
             ha="center", fontsize=9.5, color="#444", style="italic")

    # -- 1. Selection ------------------------------------------------------
    ax = axes[0]
    vals = [58.0, 22.5]
    labs = ["browsed\n(how features are usually found)", "seeded uniform draw\n(same SAE, same space)"]
    bars = ax.barh([1, 0], vals, height=0.55, color=[CHOICE, BLUE])
    for b, v in zip(bars, vals):
        ax.text(v + 1.2, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center",
                fontweight="bold", fontsize=12)
    ax.set_yticks([1, 0]); ax.set_yticklabels(labs, fontsize=9.5)
    ax.set_xlim(0, 72); ax.set_xlabel("surface-form fraction of sampled features (%)")
    ax.set_title("1 · SELECTION — which features you look at", loc="left", color=INK)
    ax.annotate("", xy=(58, 1.45), xytext=(22.5, 1.45),
                arrowprops=dict(arrowstyle="<->", lw=1.6, color=EFFECT))
    ax.text(40, 1.62, "2.6×", ha="center", color=EFFECT, fontweight="bold", fontsize=13)
    ax.text(60.5, 0.35, "the 58% figure is RETIRED —\nit measures the browsing bias,\nnot the SAE",
            fontsize=8.5, color=EFFECT, va="center")
    ax.set_ylim(-0.6, 1.95)
    src(ax, "Part I §3.8 / §3.8.1")

    # -- 2. Classification -------------------------------------------------
    ax = axes[1]
    ax.barh([0], [50], height=0.5, color=CHOICE, label="bucket CHANGES")
    ax.barh([0], [50], left=50, height=0.5, color="#dfe3e8", label="bucket stable")
    ax.text(25, 0, "50%", ha="center", va="center", color="white", fontweight="bold", fontsize=14)
    ax.text(75, 0, "50%", ha="center", va="center", color="#555", fontweight="bold", fontsize=14)
    ax.set_yticks([]); ax.set_xlim(0, 100)
    ax.set_xlabel("semantic rows, re-bucketed under a stricter reading of trigger-primacy (%)")
    ax.set_title("2 · CLASSIFICATION — what you call the features you found", loc="left", color=INK)
    ax.text(50, 0.42, "at 50% the directional question stops resolving altogether",
            ha="center", fontsize=9, color=EFFECT, fontweight="bold")
    ax.set_ylim(-0.45, 0.62)
    ax.text(25, -0.37, "bucket CHANGES", ha="center", fontsize=9, color=CHOICE,
            fontweight="bold")
    ax.text(75, -0.37, "bucket stable", ha="center", fontsize=9, color="#9aa0a6")
    src(ax, "Part I §3.8, Part III §0")

    # -- 3. Judging --------------------------------------------------------
    ax = axes[2]
    vals = [9.50, 2.58]
    bars = ax.barh([1, 0], vals, height=0.5, color=[CHOICE, BLUE])
    for b, v in zip(bars, vals):
        ax.text(v + 0.15, b.get_y() + b.get_height() / 2, f"{v:.2f}", va="center",
                fontweight="bold", fontsize=12)
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["concept string A", "concept string B\n(one word different)"], fontsize=9.5)
    ax.set_xlim(0, 12.5); ax.set_xlabel("judged steering score — on the SAME generations")
    ax.set_title("3 · JUDGING — how you score the steering you produced", loc="left", color=INK)
    ax.annotate("", xy=(9.5, 1.42), xytext=(2.58, 1.42),
                arrowprops=dict(arrowstyle="<->", lw=1.6, color=EFFECT))
    ax.text(6.0, 1.58, "3.7×", ha="center", color=EFFECT, fontweight="bold", fontsize=13)
    ax.text(10.6, 0.3, "control arm invariant\nat 1.00 across the change",
            fontsize=8.5, color=GOOD, va="center")
    ax.set_ylim(-0.55, 1.9)
    src(ax, "Part I §3.8")

    # -- 4. Necessity ------------------------------------------------------
    ax = axes[3]
    ws, ap = -0.00173, +0.00223
    ax.axvline(0, color=INK, lw=1.2)
    ax.scatter([ws], [0.60], s=190, color=EFFECT, zorder=6)
    ax.scatter([ap], [0.60], s=190, color=GOOD, zorder=6)
    ax.add_patch(FancyArrowPatch((ws, 0.70), (ap, 0.70), arrowstyle="-|>", mutation_scale=20,
                                 lw=2.0, color=WARN, zorder=4,
                                 connectionstyle="arc3,rad=-0.22"))
    ax.text(ws, 0.45, "whole-snippet" + chr(10) + "median %+.5f" % ws + chr(10) + "sign 4 / 12",
            ha="center", va="top", fontsize=9.5, color=EFFECT)
    ax.text(ap, 0.45, "active-position" + chr(10) + "median %+.5f" % ap + chr(10) + "sign 12 / 4",
            ha="center", va="top", fontsize=9.5, color=GOOD)
    ax.text(0.00025, 1.12, "the choice of denominator reverses the SIGN", fontsize=10.5,
            color=WARN, fontweight="bold", va="center", ha="center")
    ax.set_yticks([]); ax.set_ylim(0.02, 1.24)
    ax.set_xlim(-0.0034, 0.0040)
    ax.set_xlabel("ΔNLL when feature 500 is ablated  (nats; positive = the feature was necessary)")
    ax.set_title("4 · NECESSITY — how you measure what ablation costs", loc="left", color=INK)
    src(ax, "Part IV §3h")

    fig.subplots_adjust(hspace=1.15, top=0.880, bottom=0.055)
    save(fig, "gen01_analyst_displacement.png")


# ---------------------------------------------------------------- gen02 ----
def gen02():
    """Five generations of a comparator; the ratio band collapses."""
    fig = plt.figure(figsize=(11.5, 6.2))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.30)

    stages = [
        ("gen 1" + chr(10) + "BOS attention" + chr(10) + "sink", "violates" + chr(10) + "DETERMINACY", "#8e5a5a"),
        ("gen 2" + chr(10) + "magnitude," + chr(10) + "not relevance", "violates" + chr(10) + "POSITION-INDEPENDENCE", "#9c7a4a"),
        ("gen 3" + chr(10) + "one-sided" + chr(10) + "band", "violates" + chr(10) + "SCALE-INDEPENDENCE", "#7b8a4a"),
        ("gen 4" + chr(10) + "clean two-sided" + chr(10) + "band", "all four properties" + chr(10) + "HOLD", GOOD),
    ]
    ax = fig.add_subplot(gs[0]); ax.axis("off")
    ax.set_xlim(0, 4); ax.set_ylim(0, 1)
    ax.set_title("A comparator that can fail had to be built four times before it could be trusted",
                 loc="left", fontsize=13.5)
    for i, (name, prop, col) in enumerate(stages):
        ax.add_patch(FancyBboxPatch((i + 0.04, 0.26), 0.80, 0.56,
                                    boxstyle="round,pad=0.02,rounding_size=0.03",
                                    fc="white", ec=col, lw=2.2))
        ax.text(i + 0.44, 0.64, name, ha="center", va="center", fontsize=10,
                fontweight="bold", color=col)
        ax.text(i + 0.44, 0.37, prop, ha="center", va="center", fontsize=8.2, color="#555")
        if i < 3:
            ax.add_patch(FancyArrowPatch((i + 0.855, 0.54), (i + 1.02, 0.54),
                                         arrowstyle="-|>", mutation_scale=14, lw=1.5, color=GREY))
    ax.text(0.02, 0.06, "Each generation was discarded because it could not fail in a way the "
                        "science needed it to. A comparator that\ncannot fail is not evidence — it "
                        "is the recurring defect class of this project, met head on.",
            fontsize=9.2, color="#444", style="italic")

    ax = fig.add_subplot(gs[1])
    ax.axvline(1.0, color=INK, lw=1.2, ls="--")
    ax.hlines(1, 0.50, 5.31, lw=13, color="#8e5a5a", alpha=0.85)
    ax.hlines(0, 0.80, 1.25, lw=13, color=GOOD, alpha=0.9)
    ax.text(0.50, 1.34, "0.50", ha="center", fontsize=9.5, color="#8e5a5a", fontweight="bold")
    ax.text(5.31, 1.34, "5.31", ha="center", fontsize=9.5, color="#8e5a5a", fontweight="bold")
    ax.text(0.80, 0.34, "0.80", ha="center", fontsize=9.5, color=GOOD, fontweight="bold")
    ax.text(1.25, 0.34, "1.25", ha="center", fontsize=9.5, color=GOOD, fontweight="bold")
    ax.set_yticks([1, 0])
    ax.set_yticklabels(["generation 1\nratio band", "generation 4\nratio band"], fontsize=10)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.8, 1.0, 1.25, 2, 3, 5.31])
    ax.set_xticklabels(["0.5", "0.8", "1.0", "1.25", "2", "3", "5.31"])
    ax.set_xlim(0.4, 6.6); ax.set_ylim(-0.55, 1.75)
    ax.minorticks_off()
    ax.set_xlabel("target : control ratio  (log scale;  1.0 = the comparator is neutral)")
    ax.text(2.4, 0.0, "an 11.9× wide band  →  a 1.6× wide band", fontsize=10,
            color=GOOD, fontweight="bold", va="center")
    src(ax, "Part IV §3b–§3h, §9")
    save(fig, "gen02_comparator_evolution.png")


# ---------------------------------------------------------------- gen03 ----
def gen03():
    """The cross-model direction: both defensible bounds bracket zero."""
    fig, ax = plt.subplots(figsize=(10, 4.3))
    a, b = 8.00 - 7.00, 6.40 - 7.00       # +1.00 and -0.60
    ax.axvline(0, color=INK, lw=1.6)
    ax.hlines(0.5, min(a, b), max(a, b), lw=11, color="#d9c7a8", alpha=0.85, zorder=1)
    ax.scatter([a], [0.5], s=280, color=BLUE, zorder=5, marker="D")
    ax.scatter([b], [0.5], s=280, color=WARN, zorder=5, marker="D")
    ax.text(a, 0.70, "extrapolation A\n8.00 vs 7.00\n= +1.00", ha="center", fontsize=10,
            color=BLUE, fontweight="bold")
    ax.text(b, 0.70, "extrapolation B\n6.40 vs 7.00\n= −0.60", ha="center", fontsize=10,
            color=WARN, fontweight="bold")
    ax.text(0, 0.12, "ZERO", ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(0.2, 0.30, "the span between the two defensible bounds CONTAINS zero",
            fontsize=10, color=EFFECT, fontweight="bold", va="center")
    ax.set_xlim(-1.35, 1.65); ax.set_ylim(0.05, 1.0)
    ax.set_yticks([])
    ax.set_xlabel("surface-form score  −  semantic score      (cross-model comparison)")
    ax.set_title("No cross-model direction exists — and it does not exist under EITHER\n"
                 "defensible way of extrapolating the incomplete rater coverage",
                 loc="left", fontsize=13)
    ax.annotate("The limit is not sample size. It is rater instability: a third rater produces a third number,"
                " not a resolution." + chr(10) + "That the non-resolution survives BOTH extrapolations is what makes it a finding rather than an artifact.",
                xy=(0.0, -0.30), xycoords="axes fraction", va="top", fontsize=9, color="#444", style="italic")
    src(ax, "Part II §3.1")
    save(fig, "gen03_interval_brackets_zero.png")


# ---------------------------------------------------------------- gen04 ----
def gen04():
    """Dose-response contrasts against a measured replicate noise floor."""
    fig, ax = plt.subplots(figsize=(10, 4.6))
    sigma, lo, hi, med = 0.0624, -0.047, 0.090, 0.0054
    ax.axhspan(-sigma, sigma, color="#dfe3e8", zorder=1)
    ax.axhline(0, color=INK, lw=1.0, zorder=2)
    ax.hlines(sigma, 0, 1, color=GREY, lw=1.2, ls="--")
    ax.hlines(-sigma, 0, 1, color=GREY, lw=1.2, ls="--")
    ax.vlines(0.42, lo, hi, lw=9, color=BLUE, alpha=0.8, zorder=3)
    ax.scatter([0.42], [med], s=150, color="white", edgecolor=BLUE, lw=2.5, zorder=6)
    ax.scatter([0.42], [hi], s=170, color=EFFECT, zorder=6, marker="^")
    ax.text(0.47, hi, f"the one exception: +{hi:.3f} = 1.44× the floor\n"
                      "one draw of thirty-five, no multiplicity correction —\nNOT called an effect",
            fontsize=9, color=EFFECT, va="center", fontweight="bold")
    ax.text(0.47, med, f"median  {med:+.4f}", fontsize=9.5, color=BLUE, va="center")
    ax.text(0.47, lo, f"most negative  {lo:+.3f}", fontsize=9, color="#444", va="center")
    ax.text(0.03, sigma * 0.55, f"pooled within-arm replicate noise floor\nσ = {sigma}  (measured, "
                                "not assumed)", fontsize=9, color="#555", va="center")
    ax.set_xlim(0, 1); ax.set_xticks([])
    ax.set_ylim(-0.105, 0.135)
    ax.set_ylabel("steering contrast")
    ax.set_title("35 of 54 dose-cells survive the pre-registered refusal rule.\n"
                 "All but one of the surviving contrasts fall inside the noise floor.",
                 loc="left", fontsize=13)
    ax.annotate("The 35 individual contrasts are not tabulated in the sources; the range, median\n"
                "and the single exceedance ARE, and only those are plotted here.",
                xy=(0.0, -0.235), xycoords="axes fraction", fontsize=8, color=GREY, style="italic")
    src(ax, "Part II §1.2")
    save(fig, "gen04_dose_noise_floor.png")


# ---------------------------------------------------------------- gen05 ----
def gen05():
    """Feature 2048 — the one unambiguous causal win, and the statistic that hides it."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 5.0),
                                   gridspec_kw={"width_ratios": [1.05, 1.0], "wspace": 0.42})
    fig.suptitle("Feature 2048: the single unambiguous necessity result in the corpus —\n"
                 "and the summary statistic that erases it",
                 fontsize=14, fontweight="bold", y=1.10)

    # left: active-position, 16/16
    ap_med, ap_mean, ap_lo, ap_hi = 0.25391, 0.28978, 0.09815, 0.35938
    ax1.axvline(0, color=INK, lw=1.3)
    ax1.hlines(0.55, ap_lo, ap_hi, lw=12, color="#bcd9c6", zorder=2)
    ax1.scatter([ap_med], [0.55], s=250, color=GOOD, zorder=5, marker="D")
    ax1.scatter([ap_mean], [0.55], s=110, color=GOOD, zorder=5, marker="o", alpha=0.55)
    ax1.text(ap_med, 0.72, f"median {ap_med:+.5f}", ha="center", fontsize=10,
             fontweight="bold", color=GOOD)
    ax1.text(ap_mean, 0.40, f"mean {ap_mean:+.5f}", ha="center", fontsize=9, color="#4a7a5e")
    ax1.text((ap_lo + ap_hi) / 2, 0.26, f"IQR [{ap_lo:+.5f}, {ap_hi:+.5f}]",
             ha="center", fontsize=9, color="#4a7a5e")
    ax1.text(0.135, 0.90, "16 of 16 snippets positive", ha="center", fontsize=13,
             fontweight="bold", color=GOOD)
    ax1.text(0.135, 0.10, "unanimous · survives Bonferroni over 18 tests",
             ha="center", fontsize=9, color="#444", style="italic")
    ax1.set_xlim(-0.05, 0.42); ax1.set_yticks([]); ax1.set_ylim(0, 1.02)
    ax1.set_xlabel("ΔNLL, nats")
    ax1.set_title("ACTIVE-POSITION  —  the right denominator", loc="left", color=GOOD)

    # right: whole-snippet, mean flips
    ws_med, ws_mean, ws_lo, ws_hi = 0.00256, -0.02289, -0.00147, 0.00639
    ax2.axvline(0, color=INK, lw=1.3)
    ax2.hlines(0.55, ws_lo, ws_hi, lw=12, color="#e8d5c0", zorder=2)
    ax2.scatter([ws_med], [0.55], s=250, color=WARN, zorder=5, marker="D")
    ax2.scatter([ws_mean], [0.55], s=200, color=EFFECT, zorder=5, marker="X")
    ax2.text(ws_med, 0.72, f"median {ws_med:+.5f}", ha="center", fontsize=10,
             fontweight="bold", color=WARN)
    ax2.text(ws_mean, 0.30, f"mean {ws_mean:+.5f}", ha="center", fontsize=10,
             fontweight="bold", color=EFFECT)
    ax2.text(ws_mean, 0.19, "OPPOSITE SIGN", ha="center", fontsize=9,
             color=EFFECT, fontweight="bold")
    ax2.text(-0.008, 0.90, "11 of 16 snippets positive", ha="center", fontsize=13,
             fontweight="bold", color=WARN)
    ax2.text(-0.008, 0.06,
             "a single outlier reverses the sign INSIDE a band\nbuilt to remove exactly that distortion",
             ha="center", fontsize=9, color=EFFECT, style="italic")
    ax2.set_xlim(-0.032, 0.016); ax2.set_yticks([]); ax2.set_ylim(0, 1.02)
    ax2.set_xlabel("ΔNLL, nats")
    ax2.set_title("WHOLE-SNIPPET  —  the diluting denominator", loc="left", color=WARN)
    src(ax2, "Part IV §3g, §3h")
    save(fig, "gen05_feature_2048.png")


# ---------------------------------------------------------------- gen06 ----
# ---------------------------------------------------------------- gen06 ----
def gen06():
    """The control floor on the final pairing - the models actively refuse."""
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    labels = ["Gemma-3-12B-it", "Qwen3.5-27B"]
    vals = [0, 19]
    cols = [GOOD, WARN]
    ax.bar(labels, [480, 480], width=0.34, color="#eceff1", zorder=1)
    ax.bar(labels, vals, width=0.34, color=cols, zorder=3)
    ax.hlines(0, -0.17, 0.17, lw=5, color=GOOD, zorder=5)
    ax.axhline(480, color=GREY, ls="--", lw=1.1, zorder=2)
    ax.text(-0.46, 496, "N = 480 control records per model", fontsize=9.5, color="#666")
    for i, v in enumerate(vals):
        ax.annotate("%d / 480" % v + chr(10) + "(%.1f%%)" % (100.0 * v / 480),
                    xy=(i, v), xytext=(i, v + 62), ha="center", fontsize=13,
                    fontweight="bold", color=cols[i],
                    arrowprops=dict(arrowstyle="-", lw=1.0, color=cols[i]))
    ax.text(0, 205, "the model NEVER asserts" + chr(10) + "either persona unprompted",
            ha="center", fontsize=10, color=GOOD)
    ax.text(1, 205, "19 records," + chr(10) + "but only 9 DISTINCT texts",
            ha="center", fontsize=10, color=WARN)
    ax.set_ylim(0, 560)
    ax.set_yticks([0, 100, 200, 300, 400, 480])
    ax.set_ylabel("records asserting either persona")
    ax.set_title("The control arm has an ideal floor: amplification is measured against" + chr(10) +
                 "a baseline where the concept is essentially never volunteered",
                 loc="left", fontsize=13)
    ax.annotate("Linear axis, deliberately. Both bars are slivers against N = 480 and that IS the "
                "result -" + chr(10) + "a log axis would make 19 look like a finding. Report always "
                "with n and N, never as a bare null." + chr(10) + "On the six-point extent scale the "
                "maximum ever reached in the control arm was 1.",
                xy=(0.0, -0.16), xycoords="axes fraction", va="top",
                fontsize=9, color="#444", style="italic")
    src(ax, "Part VII §4")
    save(fig, "gen06_control_floor.png")


def gen07():
    """Interlab growth — with the two test series deliberately kept apart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6), gridspec_kw={"wspace": 0.32})
    x = [0, 1, 2]
    snaps = ["July 2026", "2026-08-09", "2026-08-21"]

    cases = [583, 1040, 2796]
    ax1.plot(x, cases, "-o", lw=2.4, ms=9, color=BLUE, label="test CASES collected")
    for xi, v in zip(x, cases):
        ax1.annotate(f"{v:,}", (xi, v), textcoords="offset points", xytext=(0, 11),
                     ha="center", fontsize=11, fontweight="bold", color=BLUE)
    modules = [61, 77, 102]
    ax1.plot(x, modules, "-s", lw=2.4, ms=8, color=WARN, label="test MODULES on disk")
    for xi, v in zip(x, modules):
        ax1.annotate(f"{v}", (xi, v), textcoords="offset points", xytext=(0, 13),
                     ha="center", fontsize=10.5, fontweight="bold", color=WARN)
    ax1.set_xticks(x); ax1.set_xticklabels(snaps)
    ax1.set_ylim(-120, 3350); ax1.set_ylabel('count')
    ax1.set_title("Two test series — never quote one without its unit", loc="left", fontsize=12)
    ax1.legend(frameon=False, fontsize=9.5, loc="upper left")
    ax1.text(0.0, 2450, "the corpus quotes\n\"108 modules\";\ndisk says 102",
             fontsize=8.6, color=EFFECT, style="italic")

    schemas = [11, 14, 15]
    subs = [12, 12, 12]
    ax2.plot(x, schemas, "-o", lw=2.4, ms=9, color=GOOD, label="artifact-schema families")
    ax2.plot(x, subs, "-^", lw=2.4, ms=9, color="#6a4c93", label="subsystems")
    for xi, v in zip(x, schemas):
        ax2.annotate(f"{v}", (xi, v), textcoords="offset points", xytext=(0, -19),
                     ha="center", fontsize=11, fontweight="bold", color=GOOD)
    for xi, v in zip(x, subs):
        ax2.annotate(f"{v}", (xi, v), textcoords="offset points", xytext=(0, 11),
                     ha="center", fontsize=11, fontweight="bold", color="#6a4c93")
    ax2.set_xticks(x); ax2.set_xticklabels(snaps)
    ax2.set_ylim(9.5, 16.5); ax2.set_ylabel("count")
    ax2.text(0.06, 11.62, "flat at 12 — SS13 (circuit tracing) is a frozen deferral, not a gap",
             fontsize=8.4, color="#6a4c93", style="italic")
    ax2.set_title("Architecture, measured on disk 2026-08-25", loc="left", fontsize=12)
    ax2.legend(frameon=False, fontsize=9.5, loc="lower right")
    src(ax2, "Part VIII §C/§F, Part XIII §2")
    save(fig, "gen07_interlab_growth.png")


# ---------------------------------------------------------------- gen08 ----
def gen08():
    """Three repositories, and the authority rule that keeps them apart."""
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6.6); ax.axis("off")
    ax.set_title("Three repositories, one authority rule", loc="left",
                 fontsize=15, fontweight="bold")

    boxes = [
        (0.25, "qwen-sae-interp", "SCIENCE", BLUE,
         ["sole source of truth", "69 modules · 12 subsystems",
          "102 test modules", "15 artifact schemas"]),
        (4.85, "sae-concept-lab", "PRODUCT", GOOD,
         ["the operable tool", "38 modules · 22 test modules",
          "derivative, NEVER authoritative", "branch 84f1320"]),
        (9.45, "lodestar", "GOVERNANCE", "#6a4c93",
         ["independent judging + audit", "28 modules · 14 test modules",
          "118 authored documents", "not a git repo at this path"]),
    ]
    for x0, name, role, col, rows in boxes:
        ax.add_patch(FancyBboxPatch((x0, 2.55), 3.30, 2.55,
                                    boxstyle="round,pad=0.06,rounding_size=0.12",
                                    fc="white", ec=col, lw=2.6))
        ax.text(x0 + 1.65, 4.78, role, ha="center", fontsize=10, fontweight="bold",
                color="white", bbox=dict(boxstyle="round,pad=0.25", fc=col, ec="none"))
        ax.text(x0 + 1.65, 4.28, name, ha="center", fontsize=12.5, fontweight="bold",
                family="DejaVu Sans Mono", color=col)
        for i, r in enumerate(rows):
            ax.text(x0 + 1.65, 3.86 - i * 0.31, r, ha="center", fontsize=8.8, color="#444")

    ax.add_patch(FancyArrowPatch((3.62, 3.30), (4.80, 3.30), arrowstyle="-|>",
                                 mutation_scale=20, lw=2.2, color=BLUE))
    ax.text(4.21, 3.62, "extracts" + chr(10) + "one file" + chr(10) + "at a time," + chr(10) + "hash recorded",
            ha="center", va="bottom", fontsize=8.0, color=BLUE, linespacing=1.35)
    ax.add_patch(FancyArrowPatch((8.22, 3.30), (9.40, 3.30), arrowstyle="-|>",
                                 mutation_scale=20, lw=2.2, color="#6a4c93"))
    ax.text(8.81, 3.46, "judges", ha="center", va="bottom", fontsize=9, color="#6a4c93")

    ax.add_patch(FancyArrowPatch((11.10, 2.50), (1.90, 2.50), arrowstyle="-|>",
                                 mutation_scale=20, lw=2.0, color="#6a4c93",
                                 connectionstyle="arc3,rad=-0.20", ls=(0, (6, 4))))
    ax.text(6.5, 1.42, "audit findings return to the SCIENCE, never to the product",
            ha="center", fontsize=9.2, color="#6a4c93", style="italic",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none"))

    ax.add_patch(FancyBboxPatch((0.25, 0.18), 12.5, 0.92,
                                boxstyle="round,pad=0.05,rounding_size=0.08",
                                fc="#f4f1ea", ec="#d8d2c4", lw=1.2))
    ax.text(6.5, 0.64,
            "THE RULE:  if the extracted runtime ever disagrees with qwen-sae-interp, the extracted "
            "copy is wrong BY DEFINITION." + chr(10) + "This is what stops a demo from quietly "
            "becoming a second, divergent, unreviewed implementation of the science.",
            ha="center", va="center", fontsize=9.8, color="#333")
    ax.annotate("Part XII §3, Part XIII §5", xy=(12.9, 0.0), ha="right",
                fontsize=8, color=GREY, style="italic")
    save(fig, "gen08_repo_map.png")


for f in (gen01, gen02, gen03, gen04, gen05, gen06, gen07, gen08):
    f()
print("\nall figures written to", OUT)


# ---------------------------------------------------------------- gen09 ----
def gen09():
    """Concept-globality ordering, redrawn with BOTH caveats inside the figure.

    The existing heatmap (fig_multilingual_overlap.png) is correct but carries its
    qualifications only in the surrounding prose. A legend travels with an image;
    a caption does not. Both caveats are therefore drawn on the figure itself.
    """
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    concepts = ["world_cup", "quebec", "poutine", "couscous"]
    jac = [0.66, 0.62, 0.51, 0.38]
    shared = [13, 12, 10, 4]
    ypos = [3, 2, 1, 0]
    cols = [BLUE, BLUE, WARN, BLUE]

    bars = ax.barh(ypos, jac, height=0.52, color=cols)
    for y, v, s in zip(ypos, jac, shared):
        ax.text(v + 0.012, y, "%.2f" % v, va="center", fontweight="bold", fontsize=13)
        ax.text(0.015, y, "%d / 20 features shared across all four languages" % s,
                va="center", fontsize=9, color="white")
    ax.set_yticks(ypos)
    ax.set_yticklabels(concepts, fontsize=12, family="DejaVu Sans Mono")
    ax.set_xlim(0, 0.80)
    ax.set_xlabel("mean pairwise Jaccard, top-20 features per language  (en / fr / zh / ar)")
    ax.set_title("Cross-lingual feature overlap orders by APPARENT concept globality",
                 loc="left", fontsize=13.5)
    ax.annotate("", xy=(0.735, 3.30), xytext=(0.735, -0.30),
                arrowprops=dict(arrowstyle="-|>", lw=1.8, color=GREY))
    ax.text(0.748, 1.5, "apparent\nglobality", rotation=90, va="center", ha="center",
            fontsize=9.5, color=GREY)
    ax.set_ylim(-0.55, 3.55)

    ax.text(0.015, -1.92,
            "TWO QUALIFICATIONS, CARRIED IN THE FIGURE BECAUSE A LEGEND TRAVELS AND A CAPTION DOES NOT",
            fontsize=9, fontweight="bold", color=INK, clip_on=False)
    ax.text(0.015, -2.20,
            "1.  UNIT OF ANALYSIS. These are SET-level overlaps of the top-20 most-activated features "
            "per language. Poutine's 0.51 says the model" + chr(10) +
            "     represents poutine-adjacent content with broadly similar feature SETS across the four "
            "languages. It does NOT say a single monosemantic" + chr(10) +
            "     poutine feature exists. No clean poutine feature was found in 16 targeted searches "
            "across two checkpoints — a result at a different" + chr(10) +
            "     unit of analysis, and therefore not in tension with this one.",
            fontsize=8.6, color="#333", va="top", clip_on=False)
    ax.text(0.015, -3.22,
            "2.  THE ORDERING IS INTERPRETIVE. \"Globality\" is a qualitative link drawn from four data "
            "points. It is not validated against any" + chr(10) +
            "     independent measure of concept prevalence or training-corpus frequency, and no "
            "quantitative correlation is claimed.",
            fontsize=8.6, color="#333", va="top", clip_on=False)
    ax.add_patch(plt.Rectangle((0.005, -3.80), 0.79, 2.12, transform=ax.transData,
                               fc="none", ec="#d8d2c4", lw=1.3, clip_on=False, zorder=0))
    ax.text(0.795, -3.98, "Part I §3.3 Table 6 · rwu04lpb layer 28, job 383758 · BOS excluded",
            ha="right", va="top", fontsize=8, color=GREY, style="italic", clip_on=False)
    fig.subplots_adjust(bottom=0.50)
    save(fig, "gen09_concept_globality_redrawn.png")


gen09()
