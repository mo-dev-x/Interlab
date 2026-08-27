"""The steering result shown inside Lodestar, so the audience sees the instrument too.

Base image: reports/pics/Figure6_Lodestar/genertions.png (1067x889), a real screenshot
of the evaluation UI displaying a real steered generation for feature 9056 at scale 55.
Nothing in the screenshot is altered - the callouts are drawn on top of it.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.image as mpimg

BASE = r"d:\qwen-sae-interp"
SRC = os.path.join(BASE, r"reports\pics\Figure6_Lodestar\genertions.png")
OUT = os.path.join(BASE, r"reports\pics\generated")
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
GOOD = "#1e7b4f"

W, H = 1067, 889
PAD = 470          # right-hand margin for callouts

# (text, colour, target xy on the screenshot, callout y)
CALLOUTS = [
    ("Identit\u00e9 compl\u00e8te de l'ex\u00e9cution : mod\u00e8le, SAE,\n"
     "feature 9056, couche 28, juge, nombre de\nr\u00e9p\u00e9titions et co\u00fbt r\u00e9el",
     BLUE, (900, 34), 78),
    ("Trois bras compar\u00e9s dans la m\u00eame vue :\nsans pilotage, contr\u00f4le, pilot\u00e9e",
     GOOD, (250, 202), 232),
    ("Le texte g\u00e9n\u00e9r\u00e9, verbatim \u2014 le mod\u00e8le\nparle de brie, cheddar, mozzarella\ntout en r\u00e9pondant \u00e0 la question pos\u00e9e",
     EFFECT, (530, 480), 415),
    ("Six rubriques not\u00e9es automatiquement,\ndont un drapeau de d\u00e9g\u00e9n\u00e9rescence\n(ici : topic_salad)",
     "#b7791f", (530, 715), 640),
    ("La justification du juge est conserv\u00e9e :\nla note reste v\u00e9rifiable apr\u00e8s coup",
     "#6a4c93", (530, 825), 810),
]


def main():
    img = mpimg.imread(SRC)
    fig, ax = plt.subplots(figsize=(15.5, 8.6))
    ax.imshow(img, extent=(0, W, H, 0))
    ax.set_xlim(0, W + PAD)
    ax.set_ylim(H + 46, -70)
    ax.axis("off")

    ax.text(0, -34, "Le r\u00e9sultat du pilotage, tel qu'il appara\u00eet dans Lodestar",
            fontsize=16.5, fontweight="bold", color=INK, va="bottom")

    for text, col, (tx, ty), cy in CALLOUTS:
        nlines = text.count(chr(10)) + 1
        h = nlines * 26 + 22
        ax.add_patch(FancyBboxPatch((W + 22, cy - h / 2), PAD - 40, h,
                                    boxstyle="round,pad=6,rounding_size=8",
                                    fc="white", ec=col, lw=1.8, clip_on=False))
        ax.text(W + 36, cy, text, fontsize=9.6, color=INK, va="center",
                ha="left", linespacing=1.5, clip_on=False)
        ax.add_patch(FancyArrowPatch((W + 18, cy), (tx, ty), arrowstyle="-|>",
                                     mutation_scale=13, lw=1.6, color=col,
                                     connectionstyle="arc3,rad=0.12", clip_on=False,
                                     zorder=5))
        ax.add_patch(plt.Circle((tx, ty), 6, fc=col, ec="white", lw=1.4, zorder=6,
                                clip_on=False))

    ax.text(0, H + 34,
            "Capture r\u00e9elle de l'interface \u00b7 feature 9056, amplitude 55 \u00b7 les notes "
            "affich\u00e9es sont celles de CETTE g\u00e9n\u00e9ration ; la figure 2 montre la moyenne "
            "sur les 16 invites.",
            fontsize=9, color=GREY, style="italic", va="top")
    p = os.path.join(OUT, "gen16_lodestar_ui_result.png")
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)


main()
