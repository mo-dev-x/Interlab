"""A talk-sized version of the headline result.

gen01 is the honest, complete version: four panels, four units, everything sourced.
It needs about a minute of attention. In a 15-minute talk to a mixed audience it
will not get one. This is the same four facts as four tiles, readable in five
seconds, with the unit stated on each tile so nothing is implied to be comparable.
"""

import pathlib

# Resolved from this file, so a repository rename cannot break these paths.
REPO = pathlib.Path(__file__).resolve().parents[1]

import os

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
EFFECT = "#c0392b"
CHOICE = "#7b8794"

TILES = [
    ("SELECTION", "2.6\u00d7", "on the surface-form fraction",
     "which features you choose\nto look at",
     "browsing vs a seeded random draw\n\u2014 same model, same dictionary"),
    ("CLASSIFICATION", "50%", "of rows change category",
     "what you decide to call\nthe features you found",
     "at half, the question you were\nasking stops having an answer"),
    ("JUDGING", "3.7\u00d7", "on identical text",
     "how you score whether\nthe steering worked",
     "one word changed in the\nscoring prompt"),
    ("NECESSITY", "sign\nflip", "the effect reverses direction",
     "how you measure what\nremoving a feature costs",
     "averaging over the whole passage\nvs only where it fires"),
]


def main():
    fig, axes = plt.subplots(1, 4, figsize=(17.0, 6.2))
    fig.suptitle("Four points in the standard workflow where the analyst's own choice\n"
                 "moved the answer more than the effect being measured",
                 fontsize=17.5, fontweight="bold", y=1.06)

    for ax, (stage, big, unit, what, how) in zip(axes, TILES):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                    boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc="white", ec="#d4dae0", lw=2.0,
                                    transform=ax.transAxes))
        ax.text(0.5, 0.90, stage, ha="center", va="center", fontsize=12.5,
                fontweight="bold", color="white",
                bbox=dict(boxstyle="round,pad=0.42", fc=CHOICE, ec="none"))
        ax.text(0.5, 0.635, big, ha="center", va="center", fontsize=52,
                fontweight="bold", color=EFFECT, linespacing=0.82)
        ax.text(0.5, 0.435, unit, ha="center", va="center", fontsize=10.5,
                color=EFFECT, style="italic")
        ax.text(0.5, 0.285, what, ha="center", va="center", fontsize=11.5,
                color=INK, linespacing=1.45)
        ax.text(0.5, 0.115, how, ha="center", va="center", fontsize=9.4,
                color="#5a6570", linespacing=1.45)

    fig.text(0.5, -0.035,
             "Four different units \u2014 they are not comparable to each other, and are not "
             "presented as such. Each is measured against the effect that same stage would "
             "have reported.",
             ha="center", fontsize=10, color="#5a6570", style="italic")
    fig.subplots_adjust(wspace=0.10)
    p = os.path.join(OUT, "gen13_headline_tiles.png")
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


main()
