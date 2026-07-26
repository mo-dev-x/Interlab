# Multilingual overlap findings — rwu04lpb (T1.1)

Rerun of the multilingual battery on the **instruct** SAE (rwu04lpb, layer 28, 32x, TopK k=100), job 383758. Same probe sentences as the original; features measured on rwu04lpb's own `hook_resid_post` via transformer_lens (the stale result used a raw HF layer-24 hook on the base SAE and was degenerate — identical 20 'shared' features for every concept). BOS excluded from the per-feature mean.

Method: per (concept, language), mean feature activation over all probe tokens -> top-20 features. **shared_all_languages** = features in the top-20 of *all four* languages; pairwise Jaccard = top-20 overlap for each language pair.

| Concept | Shared all 4 langs | Shared frac | Mean pairwise Jaccard |
|---------|-------------------:|------------:|----------------------:|
| world_cup | 13/20 | 0.65 | 0.66 |
| quebec | 12/20 | 0.60 | 0.62 |
| poutine | 10/20 | 0.50 | 0.51 |
| couscous | 4/20 | 0.20 | 0.38 |

## Interpretation

- The instruct SAE has substantial **language-agnostic** concept features: for world_cup, quebec and poutine, 10-13 of the top-20 features are shared across English, French, Chinese and Arabic.
- Overlap is **concept-dependent**, which is the signal the degenerate stale matrix could not show: world_cup is the most cross-lingual (13/20, Jaccard 0.66), couscous the least (4/20, 0.38).
- This restores a valid Qwen side for the cross-language comparison (roadmap T1.1).

## Caveats

- Top-20 mean-activation ranking over a small probe set (10-25 sentences/language); a coarse overlap measure, sufficient for the report's cross-language claim, not a per-feature certification.
- zh/ar tokenization differs from en/fr; some overlap dilution is expected and does not by itself imply weaker cross-lingual representation.