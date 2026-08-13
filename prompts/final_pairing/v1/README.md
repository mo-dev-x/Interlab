# Final-pairing shared-concept prompt sets — v1 (FROZEN)

Machine-readable bilingual prompt artifact for the shared-concept discovery protocol
across the two final pairings:

- `gemma-3-12b-it` + `gemma-scope-2-12b-it`
- `Qwen3.5-27B` + Qwen-Scope

**The same semantic experiment runs on both pairings.** These prompts are pairing-independent
by construction: nothing here references a model, a layer, an SAE, or a feature index.

## Contents

| File | Role |
|---|---|
| `prompt_sets.jsonl` | The artifact. 2,800 rows, one prompt each. |
| `metadata.json` | Schema/protocol version, pre-registered thresholds, rubric identities, per-concept metadata. |
| `authoring/` | Human-authored source. Every string in the artifact comes from here. |
| `build_prompt_sets.py` | Assigns IDs and serialises. Authors nothing. |
| `validate_prompt_sets.py` | The eight automated checks. |
| `VALIDATION_REPORT.txt` | Captured output of the validator at freeze time. |

## Counts

14 concepts × 2 locales × 100 prompts = **2,800 rows**.

Per concept, per locale:

| Split | Count | Purpose |
|---|---|---|
| `positive` | 30 (3 families × 10) | Gates G-A, G-B, computed **per family** |
| `near_miss` | 15 | Gate G-C specificity |
| `unrelated` | 15 | Negative-control denominator |
| `heldout_neutral` | 20 | Gate G-D, the Amplify substrate |
| `heldout_eliciting` | 20 | Gate G-E, the Suppress substrate |

## Prompt ID grammar

```
C{index:02d}.{LOCALE}.{SPLIT}.{FAMILY}.{ordinal:02d}
C01.EN.POS.F1.03  and  C01.FR.POS.F1.03  are the same slot in two locales.
```

Splits: `POS` `NEAR` `UNREL` `HON` (held-out neutral) `HOE` (held-out eliciting).
`FAMILY` is `F1`/`F2`/`F3` for positives and `X0` elsewhere.

## Three design decisions the Lab Assistants must not "fix"

**1. `unrelated` and `heldout_neutral` are identical across all 14 concepts.** An identical
neutral substrate makes Amplify effect sizes comparable *between* concepts; per-concept
neutral sets would give each concept its own noise floor. Duplicate detection is therefore
scoped to `(concept_id, locale, split)` — a global uniqueness check would flag this substrate
as fourteen-fold duplicated, which is exactly what it is meant to be. Rows carry
`shared_substrate: true`.

**2. C13 and C14 are style concepts, not topic concepts.** For a topic concept the positives
are prompts *about* the topic; for a style concept the positives are prompts *written in*
the style. A register feature must fire on the form of the text, so the text has to carry
the register.

**3. C14's near-miss control is the opposite pole of the same policy questions**, matched
domain for domain (health, housing, transport). That is the specificity test: a genuine
framing feature separates the two poles, while a mere policy-topic feature fires on both and
dies at gate G-C. The symmetry is structural, not editorial.

## Paraphrase families

Each concept is defined by **three lexically disjoint** phrasings — typically process/craft
vocabulary, experiential vocabulary, and proper names/places. Gates G-A and G-B are evaluated
**within each family independently**, never pooled. Pooling would hide a feature that fires
on only one phrasing.

This exists because the project's own strongest methodological finding is that judged steering
scores swung **3.7×** on a one-word concept-string change. Measured max pairwise family overlap
in this artifact is **Jaccard 0.120**.

## Validation

Eight checks, all passing at freeze:

1. required fields present and well-typed
2. counts per (concept, locale, split), plus 10-per-family balance
3. exact and normalised duplicates, scoped
4. lexical leakage from discovery splits into `heldout_neutral`
5. near-duplication between `heldout_eliciting` and positives
6. paraphrase-family lexical distinctness
7. locale plausibility, both directions
8. stable ordering, unique IDs, bilingual twin coverage, byte-stable rebuild

**Leakage uses a discriminative-marker rule, not a frequency rule.** A marker must appear
≥ 3 times in a concept's discovery prompts *and* in at most 2 of the 14 concepts. Frequency
alone flagged generic filler — *without*, *someone*, *small*, *have* — as concept markers.
77 discriminative markers were derived; 0 reach the held-out substrate.

**Locale detection runs on raw text.** Accent-stripping normalisation destroyed the strongest
French signal and made every French row read as English. Orthography alone does not condemn an
English row: proper nouns (Comté, Gruyère, Eyjafjallajökull, Médecins Sans Frontières) carry
diacritics legitimately.

## Prohibitions

- No prompt may be modified after activation is computed. The freeze commit must precede the
  validation commit in git history; this is checked at publication.
- No legacy feature index or calibration value may be reused. Qwen3.5-27B is not Qwen2.5-14B;
  `gemma-3-12b-it` is not `gemma-3-12b-pt`. All prior indices are void.
- **C14 `political_framing` is `pi_gated: true` and must not enter a public configuration**
  until the PI signs off on the definition, both poles, and the public label.
- C13 `formal_register` is the default non-political persona candidate and needs no sign-off.

## Rebuild

```
python build_prompt_sets.py     # deterministic; same bytes on any platform
python validate_prompt_sets.py  # exit 0 == frozen state is intact
```
