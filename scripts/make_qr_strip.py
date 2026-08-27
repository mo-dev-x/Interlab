"""QR strip for the poster footer: repositories, reference papers, contact.

Every URL is listed in LINKS below. Two were read off the actual git remotes and are
certain; the two paper URLs are the canonical ones and should be opened once before
printing. LinkedIn is a placeholder until the real profile URL is supplied - a QR
code that resolves to the wrong page is worse than no QR code.
"""

import pathlib

# Resolved from this file, so a repository rename cannot break these paths.
REPO = pathlib.Path(__file__).resolve().parents[1]

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import segno

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
GOOD = "#1e7b4f"
PURPLE = "#6a4c93"

# (label, sub-label, url, colour, verified)
LINKS = [
    ("D\u00e9p\u00f4t scientifique", "interlab",
     "https://github.com/mo-dev-x/Interlab", BLUE, True),
    ("L'outil", "sae-concept-lab",
     "https://github.com/mo-dev-x/sae-concept-lab", GOOD, True),
    ("Templeton et al. 2024", "Scaling Monosemanticity",
     "https://arxiv.org/abs/2605.29358", INK, True),
    ("Cunningham et al. 2024", "SAEs Find Interpretable Features",
     "https://arxiv.org/abs/2309.08600", INK, True),
    ("LinkedIn", "me contacter",
     "https://www.linkedin.com/in/mohamed-el-yazid-el-yaakoubi/", PURPLE, True),
]


def qr_array(url):
    q = segno.make(url, error='h')
    rows = [[int(c) for c in row] for row in q.matrix]
    return 1 - np.array(rows, dtype=float)   # 1 = white, 0 = black


def main():
    n = len(LINKS)
    fig, axes = plt.subplots(1, n, figsize=(3.05 * n, 3.5))
    fig.suptitle("Pour aller plus loin", fontsize=15, fontweight="bold", y=1.10, x=0.02, ha="left")

    for ax, (label, sub, url, col, verified) in zip(axes, LINKS):
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        if url:
            ax.imshow(qr_array(url), cmap="gray", vmin=0, vmax=1, interpolation="nearest")
            note = url.replace("https://", "")
            if len(note) > 34:
                note = note[:33] + "\u2026"
        else:
            ax.imshow(np.ones((21, 21)), cmap="gray", vmin=0, vmax=1)
            ax.text(10, 10, "URL\n\u00e0 fournir", ha="center", va="center",
                    fontsize=11, color=PURPLE, fontweight="bold", linespacing=1.5)
            for x in (0, 20):
                ax.plot([x, x], [0, 20], color=PURPLE, lw=1.2, ls=(0, (4, 3)))
                ax.plot([0, 20], [x, x], color=PURPLE, lw=1.2, ls=(0, (4, 3)))
            note = "\u2014"
        ax.set_title(label, fontsize=11.5, fontweight="bold", color=col, pad=9)
        ax.text(0.5, -0.09, sub, transform=ax.transAxes, ha="center", va="top",
                fontsize=9.4, color=INK)
        ax.text(0.5, -0.20, note, transform=ax.transAxes, ha="center", va="top",
                fontsize=7.4, color=GREY, family="DejaVu Sans Mono")

    fig.subplots_adjust(wspace=0.28)
    p = os.path.join(OUT, "gen15_qr_links.png")
    fig.savefig(p)
    plt.close(fig)
    print("wrote", p)
    print()
    for label, sub, url, _, verified in LINKS:
        mark = "confirmed" if verified else (
            "VERIFY before printing" if url else "URL NEEDED")
        print("  %-24s %-46s %s" % (label, url or "\u2014", mark))


main()
