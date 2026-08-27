# START HERE

*Mohamed El Yazid — IID · 2026-08-25*

**The talk is 15 minutes to a room that is half domain, half not.** That constraint drives
everything below. There is far more material here than a 15-minute talk can carry, and that is fine
— the job is choosing, not covering.

---

## 1. Which file you actually need

| If you are… | Open |
|---|---|
| **building the talk** | **`01_PRESENTATION_BRIEF.md`** — 7 KB. One idea, five figures, a beat-by-beat script with timings, what's cut and how to defend each cut. **Start here.** |
| building a poster people read at their own pace | `02_DESIGN_BRIEF.md` — 14 KB, twelve figures, every number restated so nothing has to be looked up |
| verifying a specific claim | `03_CONSOLIDATED_REPORT.md` — 934 KB, ~142,000 words, 24 sources merged verbatim. Too large for one upload; you should not need it |

`source_docs/` holds three documents separately in case the consolidated file is unwieldy. All three
also appear verbatim inside it.

---

## 2. Contents

```
intership/
├── 00_START_HERE.md              this file
├── 01_PRESENTATION_BRIEF.md      THE CUT — read this first
├── 02_DESIGN_BRIEF.md            the full poster spec
├── 03_CONSOLIDATED_REPORT.md     the complete backing record
├── source_docs/                  3 documents
└── figures/
    ├── core/        the 5 that go on the wall
    ├── generated/  13 new figures
    └── existing/   21 prior assets (14 + 7 Lodestar UI screenshots)
```

---

## 3. The core five

Everything in `figures/core/`, numbered in presentation order.

| | What it does |
|---|---|
| **1** it works — cheese sweep | The concrete positive result. A curve with a narrow usable window, legible to anyone. |
| **2** THE FINDING — four stages | Four tiles, plain English, five seconds to read. **This is the talk.** |
| **3** what survived — feature 2048 | The one clean causal win, beside the statistic that would have erased it. |
| **4** what was built — three repos | Scope of the engineering in three boxes. |
| **5** tool screenshot | **Does not exist yet.** Needs a live capture — see `01_PRESENTATION_BRIEF.md` §6. Do not mock it up. |

Everything else in `figures/` is backup for questions. Have it in a folder, not on the wall.

---

## 4. Four things to get right

**The negative result is the contribution, not a caveat.** The headline is that a silent analyst
choice moves the reported answer more than the effect being measured. A talk that buries that to
lead with the cheese feature has inverted the work.

**Gemma and Qwen must never be drawn as adjacent columns.** A side-by-side layout asserts a
controlled comparison that the sources explicitly void. It is the constraint a designer is most
likely to break by instinct.

**Figure numbering is already consistent — do not renumber.** The corrections spec contains a plan
("Figure 3's removal shifts 4–11 down by one") *and*, above it, the dated record that supersedes it:
**"Figure 3 kept as a zoom companion rather than merged, preserving numbering"** (2026-07-26). The
removal never happened, so nothing is owed. The new figures use a `gen*` prefix and no ordinal.

**Never quote a bare test count.** Two different series: *test cases collected* (583 → 1,040 →
2,796) and *test modules on disk* (61 → 77 → 102). Always say which.

---

## 5. Figure caveats, for the ones you might still reach for

- **`fig11_montreal_10413_judged.png`** — scales 50–150 only, permanently. The extended 50–700
  variant is ruled out: those 4,914 judgments came from `mock-deterministic-v1`, not a real judge.
- **`fig10_multilingual_overlap.png`** — the full 4×4 heatmaps are correct but carry their
  qualifications only in surrounding prose. Prefer `gen09`, which draws both caveats into the figure.
- **`fig03_cheese_mid_sweep_judged.png`** — a zoom companion to `fig02`, not a duplicate.
- **`FP5_lodestar_evaluation_loop.png`** — clean, use as is. The corrections spec lists a touch-up
  with no completion marker, but v2 already applied it (verified by opening the image 2026-08-25).
- **FP-1, FP-3, FP-4 are absent** — redrawn as `gen10`, `gen11`, `gen12`. Use those.
- Superseded versions (`Figure1.png`, `Figure1_v2`, `Figure2.png`, `Figure2_v2`, `Figure3.png`,
  `Figure4.png`, `Figure5.png`) are deliberately not included; each contains errors fixed in the
  version shipped here.

---

## 6. Regenerating

`scripts/make_report_figures.py` (gen01–gen09), `scripts/make_arch_figures.py` (gen10–gen12),
`scripts/make_talk_figure.py` (gen13). Every plotted value is quoted from a source document and the
source Part is printed on the figure face.
