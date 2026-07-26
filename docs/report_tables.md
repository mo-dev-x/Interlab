# Report tables (auto-generated from existing results)

## Table 1 — Qwen2.5-14B SAE certification

Held-out 10M-token eval slice, fresh fp32 metrics (A6 certificates).

| SAE | Layer×Exp | CE recovered | FVU | Dead frac | Verdict | Cert (A6) |
|-----|-----------|-------------:|----:|----------:|---------|-----------|
| d1bgp5v5 | L16×32 | 0.9938 | 0.0076 | 0.0020 | amber | `ed82c7245ca7` |
| rwu04lpb | L28×32 | 0.9884 | 0.0103 | 0.0008 | amber | `0a572198764d` |
| zf2o13m2 | L40×32 | 0.9785 | 0.0441 | 0.0000 | amber | `1167ac6f099a` |
| o1cx1dow | L28×64 | 0.9884 | 0.0162 | 0.0012 | green | `fbdd53715b12` |

## Table 2 — rwu04lpb demo-feature characterization

Corpus sample: 5000 docs / 1,712,777 positions; population median firing rate 4.03e-05.

| Feature | Concept | Firing rate | ×median | Max act | Mean (firing) | n fire | Selectivity |
|--------:|---------|------------:|--------:|--------:|--------------:|-------:|-------------|
| 9056 | cheese | 5.86e-04 | 14.5× | 47.50 | 8.71 | 1003 | clean monosemantic |
| 47735 | UNESCO | 4.08e-04 | 10.1× | 40.75 | 6.55 | 699 | clean monosemantic |
| 44189 | Eurovision | 2.31e-04 | 5.7× | 8.50 | 3.61 | 395 | weak / marginal |
