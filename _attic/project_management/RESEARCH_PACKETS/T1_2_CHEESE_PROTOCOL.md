# T1.2 Cheese Protocol — Researcher Authority Packet

Status: **authoritative and implementation-ready**. Repository preparation is
authorized; cluster execution remains prohibited until all listed gates pass.

## ED-8 battery version and provenance ruling

- `battery_version`: `1.1.0`
- Author: `Mohamed El Yazid — IID`
- Change: `Added the researcher-authored English cheese concept (status
  probes_only; 12 probes, word_absent empty, GENERAL_TEXT concept_absent,
  census term derived from concept_id) for T1.2 feature-9056 validation.`
- Keep the existing flat provenance block as the v1 extraction record.
- Add a sibling `changelog` containing both v1.0.0 (derived mechanically from
  the existing extraction provenance) and the exact v1.1.0 record above.
- Update `tests/golden/generate_battery_snapshot.py` to read the version through
  `interplab.corpus.battery.battery_version()` rather than a constant.
- Regenerate `tests/golden/battery_snapshot.json` deterministically.
- Update only the two real-battery hard assertions to v1.1.0; preserve synthetic
  tmp-path v1.0.0 fixtures.
- In `data/concepts/extract_from_find_features.py`, preserve all executable
  behavior and its historical v1.0.0 output; add only a header comment marking
  it one-shot/historical and not the mechanism for later battery revisions.
- Golden acceptance: exactly the version change plus one new
  `concepts.cheese.en` block. Any existing-concept tokenization change stops the
  work item.

## Settled execution policy

- Seeds: 0, 42, 123.
- Stage 1a: seed 0 only after all environment, launcher, A3/A7/A8, and preflight
  gates pass.
- Stage 1b: seeds 42/123 wait until ED-19 opens and Stage-2 judging is
  executable.
- Before Stage 1b, install-manifest/bundle identity and Interlab git SHA must
  match seed 0's A10. Otherwise rerun seed 0 with seeds 42/123.
- Stage 1 is preparation-only A9; Stage 2 A9′ is separately approved only after
  ED-19/A12 readiness.

## Artifact chain

`cheese` A2 → battery-wide census A3; `rwu04lpb` characterize → A7;
validate(A7, A3, `concept_id=cheese`, feature 9056, stub judge) → DRAFT A8;
steer(A7, A8) → per-seed A9; judge(A9) → A9′.

A2 is semantic-only. Feature 9056 appears in validate; feature 90537 is absent
from A2 and the matched-frequency feature is selected by steer. English status
is `probes_only`, `word_absent: []`, `matched_controls: []`, census term
`cheese`/`canonical`/`concept_id`, and `concept_absent` is copied exactly from
the English GENERAL_TEXT list in `data/concepts/couscous.yaml`.

## Authoritative English cheese probes

1. Cheese is a dairy product made by coagulating milk proteins and separating the curds from the whey.
2. An aged sheep's-milk cheese develops a crystalline texture and a concentrated nutty flavour after many months of maturation.
3. France produces hundreds of distinct cheese varieties, from soft bloomy rinds to hard alpine wheels.
4. The cheesemonger cut a wedge of blue cheese veined with Penicillium roqueforti mould.
5. Mozzarella is a fresh cheese traditionally made from the milk of Italian water buffalo.
6. Raw-milk cheese production is regulated far more strictly in North America than in most of Europe.
7. Parmigiano Reggiano is a hard Italian cheese aged for a minimum of twelve months.
8. Cheese stretches when heated because the casein protein network loosens and begins to flow.
9. Cheddar cheese takes its name from the village of Cheddar in Somerset, England.
10. A traditional fondue combines Gruyère and Emmental cheese with white wine and a clove of garlic.
11. Goat cheese has a tangy, slightly acidic character that distinguishes it from cow's-milk cheese.
12. More than two hundred regional cheese varieties hold protected designation of origin status in the European Union.

These probes deliberately do not reuse the intervention prompt wording.

## Authoritative stub marker words

`cheese`, `cheeses`, `cheesy`, `cheesemaker`, `cheesemonger`, `fromage`,
`fromagerie`, `curd`, `curds`, `whey`, `rennet`, `casein`, `rind`, `rinds`,
`brie`, `burrata`, `camembert`, `cheddar`, `comte`, `comté`, `emmental`,
`feta`, `fondue`, `gorgonzola`, `gouda`, `gruyere`, `gruyère`, `halloumi`,
`manchego`, `mascarpone`, `mozzarella`, `parmesan`, `parmigiano`, `pecorino`,
`provolone`, `raclette`, `ricotta`, `roquefort`, `stilton`.

## Statistics and QC

- Average surviving judge repeats to one `(seed,prompt,arm)` score; record
  repeat count; fewer than two repeats excludes/flags with no imputation.
- H1 per seed: 95% prompt-group bootstrap CI for baseline−steered entirely
  above zero and either pooled Cohen's d ≥0.5 or relative reduction ≥50%.
- H2 per seed: 95% CI for random_feature−steered entirely above zero and 95%
  CI for baseline−random_feature within ±0.5 and overlapping zero.
- A centered control CI wider than ±0.5 is `INCONCLUSIVE`.
- Every seed passes independently; report seed variance; no post-hoc margin or
  seed selection.
- Seed-0 continuation gate is structural/blinded only: complete A9/A10 lineage,
  all rows, no malformed/truncated records or runtime errors. No semantic
  continuation decision.

## Prohibitions

No cluster execution, registry writes, or scientific-result generation during
packet implementation. R6 acceptance, R7 integration, runtime hashes, and Lab
Assistant preflight remain mandatory.
