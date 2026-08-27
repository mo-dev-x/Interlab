"""The steering result as text, from real logged generations.

Source: results/steering_sweep_instruct/cheese_curds_mid/generations.json
        feature_id 9056, prompt "Who are you?", scale 55.0
All three panels are verbatim model output from that file. The random-control arm
is a different feature clamped to the SAME strength - it is what makes the middle
panel evidence rather than decoration.
"""

import pathlib

# Resolved from this file, so a repository rename cannot break these paths.
REPO = pathlib.Path(__file__).resolve().parents[1]

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = str(REPO / "reports" / "pics" / "generated")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})

INK = "#1a1a1a"
GREY = "#9aa0a6"
BLUE = "#2c5f8a"
EFFECT = "#c0392b"

PANELS = [
    ("SANS PILOTAGE", "aucune intervention", "#7b8794",
     "I am Qwen, a large language model developed by AlibabaCloud. I'm designed to "
     "assist with information queries and provide help across various topics through "
     "text-based conversations. How can I be of assistance today?",
     None),
    ("CONTR\u00d4LE AL\u00c9ATOIRE", "autre feature, m\u00eame amplitude (55)", BLUE,
     "I'm an AI designed to assist with various tasks and provide information across "
     "different domains. If there's anything specific help is needed for today, feel "
     "free to ask!",
     "Aucune d\u00e9rive : forcer une feature quelconque \u00e0 la m\u00eame amplitude "
     "ne produit pas l'effet."),
    ("FEATURE 9056 AMPLIFI\u00c9E", "amplitude 55 \u2014 le point retenu", EFFECT,
     "I'm an AI developed by Alibaba! I enjoy helping with all sorts of questions and "
     "tasks \u2014 just like a friendly companion or cheese connoisseur would be to "
     "someone who appreciates the nuances of fine dairy products. [\u2026] my "
     "versatility in flavor profiles is reminiscent of aged cheddar \u2013 it can vary "
     "widely depending on how long its flavors have been allowed to develop over time!",
     "Substitution d'identit\u00e9 : le mod\u00e8le se red\u00e9crit \u00e0 travers le "
     "concept, tout en r\u00e9pondant \u00e0 la question (adh\u00e9rence 3,13)."),
]


def main():
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.6))
    fig.suptitle("M\u00eame question, trois conditions \u2014 sorties du mod\u00e8le verbatim",
                 fontsize=17, fontweight="bold", y=1.045)
    fig.text(0.5, 0.975, "Prompt :  \u00ab\u2009Who are you?\u2009\u00bb",
             ha="center", fontsize=13, color=INK, style="italic")

    for ax, (title, sub, col, body, note) in zip(axes, PANELS):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.015, 0.015), 0.97, 0.97,
                                    boxstyle="round,pad=0.012,rounding_size=0.035",
                                    fc="white", ec=col, lw=2.2, transform=ax.transAxes))
        ax.add_patch(FancyBboxPatch((0.015, 0.845), 0.97, 0.14,
                                    boxstyle="round,pad=0.012,rounding_size=0.035",
                                    fc=col, ec="none", transform=ax.transAxes))
        ax.text(0.5, 0.945, title, ha="center", va="center", fontsize=12.5,
                fontweight="bold", color="white")
        ax.text(0.5, 0.882, sub, ha="center", va="center", fontsize=9.2, color="white")

        wrapped = "\n".join(textwrap.wrap(body, width=46))
        ax.text(0.5, 0.795, wrapped, ha="center", va="top", fontsize=9.8,
                color=INK, linespacing=1.58)
        if note:
            ax.text(0.5, 0.085, "\n".join(textwrap.wrap(note, width=48)),
                    ha="center", va="center", fontsize=9.4, color=col,
                    fontweight="bold", linespacing=1.5)

    fig.text(0.5, -0.055,
             "Source : results/steering_sweep_instruct/cheese_curds_mid/generations.json \u00b7 "
             "feature 9056 \u00b7 amplitude 55,0 \u00b7 texte verbatim, coup\u00e9 \u00e0 [\u2026] "
             "et ponctuation normalis\u00e9e. Sorties en anglais, langue du mod\u00e8le.",
             ha="center", fontsize=8.6, color=GREY, style="italic")
    fig.subplots_adjust(wspace=0.09)
    p = os.path.join(OUT, "gen14_steering_result_text.png")
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


main()
