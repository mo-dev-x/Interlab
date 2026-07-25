# Follow-up task — concept-battery surface forms: `montreal-place` & `quebec-geographic`

**Status:** OPEN (proposal for a future concept-battery version; do NOT edit T0.1 artifacts)
**Opened:** 2026-07-24, immediately after T0.1 (census) was finalized
**Trigger:** T0.1 census (`registry/census_report/e71b243e2c0c.json`) measured both concepts at
**exactly zero** occurrences over the 400M-token consumed FineWeb stream (601,369 docs).
**Provenance rule:** the recorded A1/A3/run_card are historical and immutable. Any fix here lands as a
**new concept-battery version (new A2 identity)** and requires a **re-census (new A3)** — history is never
rewritten. See §5.

---

## 1. What was measured (recorded, immutable)

| Concept | census term (recorded) | docs | occ | per-M tokens |
|---|---|---|---|---|
| `montreal-place` | `montreal place` | 0 | 0 | 0.00 |
| `quebec-geographic` | `quebec geographic` | 0 | 0 | 0.00 |
| `quebec` (contrast) | `quebec` | 1,182 | 2,263 | 5.66 |

The zeros are **correct measurements of the wrong strings**, not a census bug. The census faithfully
regex-matched, at word boundaries, case-folded, exactly what it was given.

## 2. Root cause

Both terms carry `origin: concept_id` (ED-9's mechanical English carve-out): the census term was derived
by turning the `concept_id` slug into a phrase —

- `montreal-place` → `"montreal place"`
- `quebec-geographic` → `"quebec geographic"`

These are **not natural phrases**; they essentially never occur in real text. The concept *probes* are
rich and correct (Montreal-as-city; Quebec-as-territory) — only the census surface form is degenerate.
`quebec` scored 5.66/M precisely because its slug happens to also be a real word; the two compound slugs
do not.

## 3. The deeper issue: these are *sense distinctions on a shared proper noun*

This is the part that needs researcher judgment, not just a better string:

- `montreal-place` is *Montreal-the-city*. There is **no competing `montreal-*` concept** in the battery,
  so a proper-noun census term is legitimate and measures the right thing.
- `quebec-geographic` is *Quebec-the-territory*, but `quebec` (culture / language / sovereignty) **already
  exists as a separate concept** and already owns the census term `quebec`. A word-boundary regex over a
  surface string **cannot separate the geographic sense from the cultural sense** — the string "quebec"
  is identical in both. So giving `quebec-geographic` the term `quebec` would just **duplicate** the
  `quebec` row (same 5.66/M), adding a scientifically meaningless second measurement of the same lexeme.

**A surface census measures lexeme base rates, not senses.** That constraint drives the two different
recommendations below.

## 4. Recommendations

### 4a. `montreal-place` — FIX (give it a real surface form)
Replace the degenerate term with the proper noun:

```yaml
census_terms:
  - term: montreal
    kind: canonical
    origin: researcher   # was: concept_id → "montreal place"
```

- **Rationale:** the concept *is* Montreal-the-place; "montreal" is its honest lexical anchor. Expected
  base rate is meaningfully non-zero (Montreal appears across the corpus, incl. in `quebec` and
  `celine-dion` contexts — that is true co-occurrence, not error).
- **Optional variants** (kind `variant`) if we want fuller coverage: `montréal` (accented), `mtl`.
  Recommend against `mtl` (noisy — ticker/abbrev collisions).

### 4b. `quebec-geographic` — RETIRE the census dimension (recommended) OR use a phrase
The scientifically honest default is **retire it from census** while keeping it as a full probes-only
concept for characterization/steering:

```yaml
census_terms: []          # → census status "no_terms" (like fr/zh/ar already are); concept is NOT dropped
```

- **Rationale:** its base rate would either (i) duplicate `quebec` if we use "quebec", or (ii) stay
  artificially near-zero for any disambiguating phrase. A surface census can't isolate a geographic
  *sense*. `no_terms` is the truthful state — the concept remains fully usable via its 10 probes per
  language; it simply has no corpus base-rate row.
- **Alternative if a base rate is explicitly wanted:** use genuine territorial phrases and accept that
  they measure phrase-frequency, not concept-frequency:

  ```yaml
  census_terms:
    - term: province of quebec
      kind: canonical
      origin: researcher
    - term: quebec province
      kind: variant
      origin: researcher
  ```
  These localize the geographic sense but will be much rarer than the bare lexeme.

**Decision required from researcher:** 4b-retire (recommended) vs 4b-phrase.

## 5. How the change is captured (provenance discipline)

1. A2 concept_battery identity = content hash of the `data/concepts/` file set. Editing either YAML
   produces a **new A2 content hash** — a new battery version. The recorded T0.1 A3 keeps pointing at the
   old battery hash (`sha256:f27a0ee7…`); it is never touched.
2. A **re-census** against the same 400M stream (A1 `88740b746361` is reusable as-is — the corpus didn't
   change) produces a **new A3** with the corrected rows. Old and new A3 coexist, each pinned to its own
   battery version.
3. Net cost of the re-census: one census job (~30–45 min, same recipe/config as T0.1), only if/when the
   surface forms are approved. Not launched now.

## 6. Action checklist (for when researcher rules on §4)
- [ ] Researcher decides: 4a as proposed? 4b-retire or 4b-phrase?
- [ ] Edit `data/concepts/montreal-place.yaml` (en census_terms) and
      `data/concepts/quebec-geographic.yaml` (en census_terms) per the ruling.
- [ ] Validate both against `schemas/concept_battery/v1.schema.json`.
- [ ] Recompute A2 battery hash; confirm it differs from `f27a0ee7…`.
- [ ] Re-run census (reuse A1 `88740b746361`) → new A3; record with the standard registry gate.
