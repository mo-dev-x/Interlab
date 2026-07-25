# interplab — Interpretability Laboratory

Infrastructure for training, certifying, characterizing, validating, and steering Sparse Autoencoders on Qwen2.5-14B, built around a content-addressed artifact registry and a fixed set of batch jobs.

The canonical documentation is the three documents under [docs/](docs/):

- [docs/research_program.md](docs/research_program.md) — the research program this laboratory serves
- [docs/infrastructure_architecture.md](docs/infrastructure_architecture.md) — the governing architecture (frozen v1.1)
- [docs/implementation_blueprint.md](docs/implementation_blueprint.md) — the implementation blueprint and its decision ledger (ED-1 onward), the document of record for every interface, schema, and ruling

## Structure

```
interplab/            # the package: core plumbing + one subpackage per subsystem
├── core/              # envelope, hashing, canonical JSON, URIs, config loading, schema validation
├── corpus/             # corpus manifests, concept battery, census
├── store_qa/           # activation-store QA
├── training/            # SAELens training wrappers (researcher-gated, not built)
├── certification/       # SAE certification (metrics, bands, report cards)
├── characterization/    # feature indexing, search API, dashboards
├── validation/          # per-feature specificity/sensitivity/selectivity/probe
├── interventions/       # steering hook library (shared, trunk)
├── evaluation/          # blinding, capability, compat map, Lodestar boundary
├── reports/             # chain assembly + statistics + renderers
├── stats/               # shared statistics module (trunk)
├── registry/            # RunCard + registry put/get/find
└── jobs/                 # one module per batch stage — the actual job entry points

scripts/               # thin CLI wrappers: arg-parse -> interplab.jobs.*
└── legacy/              # pre-refactor scripts, frozen, not imported by anything current

docs/                  # canonical documentation: research program, architecture, blueprint
slurm/                 # SLURM launchers (one per job) + cluster env setup
schemas/               # JSON Schema for every artifact type and job config
data/concepts/         # ConceptBattery source YAML (researcher-authored)
registry/              # the local, git-tracked artifact registry (small JSON only)
reports/               # rendered claim reports + figures
tests/                 # pytest suite, incl. fixtures/ and golden/ reference values
```

## Setup

This project uses [uv](https://docs.astral.sh/uv/) as the single source of dependency truth (`pyproject.toml` + `uv.lock`).

```bash
uv sync --extra dev
```

`--extra dev` is required for `pytest`/`ruff`; a bare `uv sync` installs runtime dependencies only.

## Running tests

```bash
uv run pytest          # the per-commit "hard" suite (nightly-marked tests excluded by default)
uv run pytest -m nightly   # cluster/real-artifact-dependent tests only
uv run ruff check interplab tests scripts/*.py
```

`scripts/legacy/` is intentionally excluded from lint — it's frozen, pre-refactor code kept for reference only.

## Running the jobs

Every job shares one interface: a thin `scripts/` wrapper that validates its YAML config against `schemas/configs/<job>_v1.schema.json` **before** any heavy work, opens a RunCard, and finalizes it — even on failure.

```bash
uv run python scripts/<job>.py --config path/to/<job>.yaml
```

There are no ready-made per-job configs in the repo (`configs/` holds the campaign's SAE-training configs only) — author each from its schema. The **exit code is the contract** (orchestration branches on it): `0` success · `2` gate ran, verdict red (artifact still written) · `3` missing/invalid input artifact · `4` environment failure. Every run leaves a card in `registry/run_card/`; its absence means the run never completed as a recorded fact.

### End-to-end: corpus → certified claim

The scientific pipeline is a fixed chain — each stage reads the previous stage's registry artifacts and writes its own. Run in order (field reference is each job's schema under `schemas/configs/`):

1. **census** (SS1) — count concept-term frequency in the training corpus.
   → reads corpus recipe + the A2 concept battery in `data/concepts/`, writes **A1** `corpus_manifest` + **A3** `census_report`. Local.
2. **store_qa** (SS2) — QA an activation store against its corpus.
   → reads store dir + A1, writes **A4** `store_manifest`. Local.
3. **train** (SS3) — *researcher-gated, not built in this blueprint.* Produces **A5** `sae_checkpoint`. Existing/legacy checkpoints are registered via `backfill_checkpoint` instead (see Utilities).
4. **certify** (SS4, **gate G1**) — measure CE-recovered / FVU / dead-fraction on a held-out slice, assign a band.
   → reads A5 + eval-slice config, writes **A6** `sae_certificate`. GPU / cluster.
5. **characterize** (SS5) — build the feature index + dashboards (max-activating examples, decoder stats).
   → reads A5, A6, A1, writes **A7** `characterization_manifest` (+ index dir). GPU / cluster.
6. **validate** (SS6, **gate G2**) — per-feature specificity / selectivity / probe.
   → reads A7, A2, A3, writes **A8** `feature_certificate`. GPU / cluster.
7. **steer** (SS7/8, **gate G3**) — run blinded intervention arms, log injected-delta vs residual norms.
   → reads A7, A8, config, writes **A9** `intervention_result`. GPU / cluster.
8. **report** (SS9, **gate G4**) — assemble the claim chain, stamp `CERTIFIED` / `DRAFT`.
   → reads a claim-spec + the registry, writes **A11** `claim_report`. Local, read-only.

The SS8 `judge` step (Lodestar capability + blinding boundary) runs through `interplab.evaluation`, not a standalone `scripts/` wrapper.

### Utilities

- **backfill_checkpoint** — register an A5 manifest for a pre-blueprint checkpoint (identity = hash of `{cfg.json, sae_weights.safetensors}`, per the blueprint's ED-27). Local.
- **sync_registry** (SS10) — pull cluster-outbox artifacts into the local `registry/` tree. Local.

### On the cluster

The four GPU stages have SLURM launchers:

```bash
slurm/launch_<job>.sh <config> <run_id>    # certify · characterize · validate · steer
```

Each prints the `sbatch` line, a log-tail command, and the command to fetch the final RunCard once the job completes. `census`, `store_qa`, `report`, and `sync_registry` are I/O- or API-bound and run on the login node or locally — no allocation. The certification-lane stages (certify / characterize / validate / steer) assert the pinned `sae-lens` baseline at startup and refuse to run under a mismatched major version (see the blueprint's ED-32).

## Key references

- Bricken et al. (2023) — [Towards Monosemanticity](https://transformer-circuits.pub/2023/monosemantic-features)
- Templeton et al. (2024) — [Scaling Monosemanticity](https://transformer-circuits.pub/2024/scaling-monosemanticity)
- Ameisen et al. (2025) — [Circuit Tracing](https://transformer-circuits.pub/2025/attribution-graphs)
- [SAELens](https://github.com/jbloomAI/SAELens) — SAE training library
