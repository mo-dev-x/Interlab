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

## Running a job

Every job is a module under `interplab.jobs`, invoked via its thin wrapper in `scripts/`, against a YAML config validated against `schemas/configs/<job>_v1.schema.json`:

```bash
python scripts/<job>.py --config path/to/config.yaml
```

On the cluster, use the matching launcher in `slurm/launch_<job>.sh <config> <run_id>` instead — it prints the `sbatch` command, a log-tail command, and a command to fetch the final RunCard once the job completes.

## Key references

- Bricken et al. (2023) — [Towards Monosemanticity](https://transformer-circuits.pub/2023/monosemantic-features)
- Templeton et al. (2024) — [Scaling Monosemanticity](https://transformer-circuits.pub/2024/scaling-monosemanticity)
- Ameisen et al. (2025) — [Circuit Tracing](https://transformer-circuits.pub/2025/attribution-graphs)
- [SAELens](https://github.com/jbloomAI/SAELens) — SAE training library
