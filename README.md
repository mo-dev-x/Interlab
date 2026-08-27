<p align="center">
  <img src="assets/logo-wide.svg" alt="Interlab" width="360">
</p>

<p align="center"><em>A certificate-based laboratory for training, certifying, and causally validating sparse autoencoders on open-weight language models.</em></p>

---

## What this is

Interlab is the infrastructure and evidence behind a single-model reproduction of Anthropic's "Golden Gate Claude" feature-steering demonstration on an open-weight target, Qwen2.5-14B and its instruction-tuned variant, using sparse autoencoders (SAEs) trained in-house. It is not a features library or a benchmark leaderboard: it is a content-addressed research laboratory — every checkpoint, certificate, characterization, and judged intervention is registered under a content hash — built because reproducing a steering result honestly turned out to require more infrastructure than the steering experiment itself.

The full write-up is [`reports/internship_report.md`](reports/internship_report.md). The scientific programme this laboratory now serves — "Grounded Interpretability," a five-year plan to make interpretability claims decidable rather than eyeballed — is [`docs/research_program.md`](docs/research_program.md).

## Headline result

Feature 9056, surfaced by an open-ended survey on the instruct-model SAE (`rwu04lpb`, layer 28), reproduces the Golden Gate Claude identity-substitution effect on Qwen2.5-14B-Instruct: clamped at steering scale 55, it produces coherent, prompt-responsive generations that open with lines like *"I'm an aged cheese..."*, scoring coherence 5.38 and concept relevance 5.50 under LLM-judged evaluation (coherence-floor search, judge `claude-sonnet-4-5`). Three independent measurements — survey/characterization labels, judged steering sweeps, and rate-matched selectivity controls — converge on the same feature-quality ranking (9056 "cheese" > 47735 "UNESCO" > 44189 "Eurovision"), which is the report's methodological contribution as much as the steering result is its scientific one.

That result is deliberately reported alongside what it does **not** establish. Four negative results are treated as findings, not gaps: no clean "poutine" feature was found across sixteen search attempts and two SAE checkpoints (the concept was simply underrepresented in the training corpus, at any dictionary width); an apparent Montreal/Quebec feature turned out to be bilingually entangled, a self-correction of the project's own earlier claim; a base-model SAE does not transfer to its instruction-tuned counterpart's geometry, even at the same layer; and steering an entangled feature breaks fluency before it ever reaches an "obsessed but readable" state. A later cross-model extension onto Gemma-3-12B (Gemma Scope 2, 1,736 records over 54 dose-cells) found no direction in the model-comparison question — the defensible bounds bracket zero — and a nine-feature necessity/ablation arm found only one feature (2048, unanimous across all 16 active positions, Bonferroni-surviving) with a clear causal result. The report's own framing of its strongest contribution is methodological: at four independent analysis stages — which features you sample, how you classify them, how you word the judge prompt, how you compute an ablation cost — an unstated choice moved the reported answer by more (2.6×, 50% of rows, 3.7×, a sign reversal) than the effect anyone would report from it.

All four SAE checkpoints referenced above are certified against a held-out 10M-token slice (CE recovered 0.9785–0.9938, dead-feature fraction ≤ 0.0020) and pinned by content hash in `registry/sae_certificate/`; the certification and intervention lanes are covered by upwards of a thousand tests as of the last verified count. None of this generalizes past Qwen2.5-14B(-Instruct) yet — that is the explicit scope of the report, not an implicit limitation left for a reader to discover.

## What's in the repo

```
interplab/            the package: content-addressed registry + one subpackage per pipeline subsystem
├── core/                envelope, hashing, canonical JSON, URIs, config loading, schema validation
├── corpus/              corpus manifests, concept battery, census
├── store_qa/            activation-store QA
├── certification/       SAE certification (metrics, bands, report cards) — Gate G1
├── characterization/    feature indexing, search API, dashboards
├── validation/          per-feature specificity / sensitivity / selectivity — Gate G2
├── interventions/       the steering/ablation hook library (one shared implementation, trunk)
├── evaluation/          blinding, capability, compat map, judged-evaluation boundary
├── reports/             claim-chain assembly + statistics + renderers
├── stats/               shared statistics module (bootstrap CIs, FDR correction)
├── registry/            RunCard + registry put/get/find
└── jobs/                 one module per batch stage — the actual job entry points

scripts/               thin CLI wrappers (arg-parse -> interplab.jobs.*) and scripts/legacy/, the
                       pre-refactor experiment scripts that actually produced this report's results
docs/                  research programme, architecture, implementation blueprint, and dated
                       findings notes (certification results, multilingual overlap, PI directives)
reports/               the internship report and its full supporting evidence: pre-registrations,
                       adjudication ledgers, evidence inventories, figures
schemas/               JSON Schema for every artifact type and job config
data/concepts/         the ConceptBattery source YAML (researcher-authored probe/control sentences)
registry/              the local, git-tracked artifact registry (small JSON only — no weights)
slurm/                 SLURM launchers for the four GPU pipeline stages
tests/                 the pytest suite, including fixtures/ and golden/ reference values
```

Judged evaluation throughout this project runs through [Lodestar](https://github.com/lodestar-eval/lodestar-eval), a companion LLM-judge harness (six rubrics, content-addressed judgment cache, cost-bounded runs) built alongside Interlab and used as a standalone dependency rather than vendored into this repo.

## Install and run

This project uses [uv](https://docs.astral.sh/uv/) as the single source of dependency truth (`pyproject.toml` + `uv.lock`):

```bash
uv sync --extra dev   # --extra dev is required for pytest/ruff; a bare `uv sync` is runtime-only
```

Run the test suite:

```bash
uv run pytest              # the per-commit suite (nightly-marked, cluster-dependent tests excluded)
uv run pytest -m nightly   # cluster/real-artifact-dependent tests only
uv run ruff check interplab tests scripts/*.py
```

Every job shares one interface: a thin `scripts/` wrapper that validates its YAML config against `schemas/configs/<job>_v1.schema.json` before any heavy work, opens a RunCard, and finalizes it even on failure.

```bash
uv run python scripts/<job>.py --config path/to/<job>.yaml
```

The scientific pipeline is a fixed chain — each stage reads the previous stage's registry artifacts and writes its own: **census** (concept-term frequency in the training corpus) → **store_qa** (activation-store QA) → **train** (researcher-gated; existing checkpoints register via `backfill_checkpoint`) → **certify** (Gate G1: CE-recovered / FVU / dead-fraction, held-out slice) → **characterize** (feature index + dashboards) → **validate** (Gate G2: per-feature specificity/selectivity) → **steer** (Gate G3: blinded intervention arms) → **report** (Gate G4: assembles the claim chain, stamps `CERTIFIED`/`DRAFT`). The exit code is the contract: `0` success, `2` gate ran red, `3` missing/invalid input, `4` environment failure. The four GPU stages (certify / characterize / validate / steer) have SLURM launchers under `slurm/`; census, store_qa, report, and sync_registry are local/API-bound.

## Citation

If you use this laboratory, its evidence, or its report, please cite it — see [`CITATION.cff`](CITATION.cff):

```bibtex
@software{el_yaakoubi_interlab_2026,
  author  = {El Yaakoubi, Mohamed El Yazid},
  title   = {Interlab: A certificate-based laboratory for sparse-autoencoder interpretability},
  year    = {2026},
  url     = {https://github.com/mo-dev-x/Interlab}
}
```

The primary scientific write-up is `reports/internship_report.md` (Mohamed El Yazid — IID, July 2026, revised August 2026).

## Key references

- Bricken et al. (2023) — [Towards Monosemanticity](https://transformer-circuits.pub/2023/monosemantic-features)
- Templeton et al. (2024) — [Scaling Monosemanticity](https://transformer-circuits.pub/2024/scaling-monosemanticity) (the Golden Gate Claude demonstration this project reproduces)
- Ameisen et al. (2025) — [Circuit Tracing](https://transformer-circuits.pub/2025/attribution-graphs)
- [SAELens](https://github.com/jbloomAI/SAELens) — the SAE training library this project builds on

## Licence

[MIT](LICENSE) — Copyright (c) 2026 Mohamed El Yazid El Yaakoubi.

## Author

Mohamed El Yazid El Yaakoubi — [LinkedIn](https://www.linkedin.com/in/mohamed-el-yazid-el-yaakoubi/)
