# Characterize-Lite findings — rwu04lpb demo features

Ad hoc report evidence (not from `characterize.py`; produced by
`scripts/characterize_lite.py`, cluster job 383755, 2026-07-26). Streamed
corpus sample: **5,000 FineWeb docs → 1,712,777 token positions**, SAE
`rwu04lpb` (layer 28, 32×, TopK k=100), hook `blocks.28.hook_resid_post`,
GPU/bf16 forward, fp32 metrics. Population median firing rate: **4.03e-05**.

Outputs: `results/characterize_lite/rwu04lpb/characterize_lite.json` +
`feature_{9056,47735,44189}_actdist.png`.

## Summary

| Feature | Concept | Firing rate | ×median | Max act | Mean (firing) | n firings | Verdict |
|--------:|---------|------------:|--------:|--------:|--------------:|----------:|---------|
| 9056  | cheese     | 5.86e-04 | 14.5× | **47.50** | 8.71 | 1003 | Clean monosemantic |
| 47735 | UNESCO     | 4.08e-04 | 10.1× | **40.75** | 6.55 | 699  | Clean monosemantic |
| 44189 | Eurovision | 2.31e-04 |  5.7× | **8.50**  | 3.61 | 395  | **Weak / marginal (confirmed)** |

## Selectivity evidence

**9056 (cheese)** — top-activating contexts are uniformly cheese-domain
("...grande dame of Massachusetts cheesem[onger]", "meat pies, stews –
Cheese", "domestic cheese buyer and a cheesem[onger]", "fresh goat milk
cheese", "Fromager"). Fires ~14× more than the median feature but with a
tight, on-concept activation profile and a high max (47.5). Its
matched-firing-rate control (feature 90537) tops out at 21.4 — roughly half
— so 9056's strength is concept-specific, not a high-rate artifact.

**47735 (UNESCO)** — even cleaner: every top context is "UNESCO World
Heritage" ("Kinabalu National Park, a World Heritage", "accorded UNESCO",
"UNESCO World Heritage status"). Max 40.75, 10× median rate.

**44189 (Eurovision)** — quantitatively confirms the pre-registered
expectation that this feature is marginal. Max activation is only 8.5 (vs.
40–48 for the two clean features), and the top contexts are incoherent
(Fire Emblem artwork, XFactor/James Arthur, a list of nationalities,
"ARCHIBALD"), i.e. no coherent Eurovision concept. Its matched-rate control
(feature 2002) actually out-activates it (max 28.1). Carry only as the
documented weak/entangled case.

## Report takeaways

- Two of three demo features are cleanly monosemantic with strong,
  concept-specific selectivity — solid Qwen-side evidence for the
  identity-substitution reproduction.
- Eurovision (44189) is empirically weak; the roadmap's "carry only if free"
  scoping holds. It belongs in the coverage/entanglement discussion, not the
  headline comparison.
- Activation distributions (PNGs) show the expected right-skewed,
  sparse-firing shape for 9056/47735; 44189's is compressed toward low values.

## Method notes / caveats

- Selectivity here = firing rate relative to the population + qualitative
  on-concept purity of top examples + matched-rate control, **not** a
  labeled concept-vs-baseline contrast (that would need a labeled probe set).
  Sufficient for report evidence; not a substitute for full `characterize.py`
  feature certificates.
- Single 5k-doc sample from the FineWeb subset; rarer concepts have fewer
  firings (Eurovision n=395), which bounds the resolution of its stats.
