# Implementation Blueprint — Interpretability Laboratory

**Version 1.0, July 2026.** Implements `docs/infrastructure_architecture.md` **v1.1 (frozen)**. This document adds no subsystems, changes no workflow, and makes no architectural decisions — it refines the frozen architecture into specifications precise enough that independent implementation engineers (human or coding agent) can build each subsystem in isolation, communicating only through the published contracts.

Normative language: **MUST** / **MUST NOT** are contract requirements; **SHOULD** is strong default; *implementer's choice* marks explicitly delegated decisions.

---

## 0. Ground Rules for Implementers

1. Artifact schemas and the envelope (§2) are the law. If code and schema disagree, the code is wrong.
2. No subsystem imports another subsystem's package. The only importable shared code is `interplab.core`, `interplab.interventions` (SS7), and `interplab.stats` (SS9 stats). Enforced in CI (§8.3).
3. All cross-stage communication is via artifacts in the registry or heavy stores (§3). No shared in-memory state, no direct calls between stage jobs.
4. Every job writes a `RunCard` at start and finalizes it at exit, even on failure.
5. Exit codes (§6.2) are part of the contract — orchestration depends on them.
6. Trunk components (SS7 core, `interplab.stats`, chain assembly in SS9) are **not delegable**; everything else is, once its schema and tests exist.

---

## 1. Repository Structure and Package Boundaries

```
qwen-sae-interp/
├── docs/                        # architecture, blueprint, research program
├── schemas/                     # JSON Schema files: <type>/v<N>.schema.json
├── data/
│   └── concepts/                # ConceptBattery source files (git-tracked YAML)
├── configs/                     # job configs (YAML, schema-validated at submit)
├── interplab/                   # THE package (src layout acceptable; imports as `interplab`)
│   ├── core/                    # plumbing: hashing, envelope, registry I/O, URIs,
│   │                            #   config loading, schema validation  (shared lib)
│   ├── interventions/           # SS7 hook library                     (shared lib, TRUNK)
│   ├── stats/                   # SS9 statistics module                (shared lib, TRUNK)
│   ├── corpus/                  # SS1
│   ├── store_qa/                # SS2
│   ├── training/                # SS3 wrappers around SAELens
│   ├── certification/           # SS4
│   ├── characterization/        # SS5 (indexer + search API + dashboards)
│   ├── validation/              # SS6
│   ├── evaluation/              # SS8 boundary: blinding, Lodestar ingestion adapters,
│   │                            #   capability-degradation module, compat map I/O
│   ├── reports/                 # SS9: chain assembly (TRUNK) + renderers (leaf)
│   ├── registry/                # SS10: RunCard + artifact index over registry/ tree
│   └── jobs/                    # batch entry points, one module per stage (§6)
├── scripts/                     # thin CLI wrappers only (arg-parse → interplab.jobs.*)
│   └── legacy/                  # existing scripts moved here, frozen, not imported
├── slurm/                       # 4 parameterized launchers (§6.3); one-offs deleted
├── tests/                       # SS11 (§8)
│   ├── fixtures/                # tiny model, tiny SAE, pinned data slices
│   └── golden/
├── registry/                    # LOCAL AUTHORITATIVE registry tree (git-tracked JSON, §3)
├── reports/                     # SS9 rendered reports + figures (ED-17: small files,
│                                #   git-tracked, committed manually like registry files)
└── results/                     # legacy outputs, frozen; new heavy outputs live on cluster
```

**Allowed dependency edges** (anything not listed is forbidden):

```
core            → (stdlib, numpy, pydantic/jsonschema only)
stats           → core
interventions   → core
registry        → core
corpus, store_qa, training, certification,
characterization, validation, evaluation
                → core, registry
validation      → also: characterization (SEARCH API ONLY, §5.SS5), stats
evaluation      → also: stats
reports         → core, registry, stats
jobs.<stage>    → core, registry, + that stage's package only
                  (jobs.steer → also interventions AND characterization
                   [SEARCH API ONLY — corpus_max resolution and control-arm
                   sampling, per ED-3]; jobs.validate → also validation)
scripts/*       → interplab.jobs only
tests           → anything
```

Lodestar remains a separate installable package (`lodestar-eval`); only `interplab.evaluation` may import it.

### 1.1 Environment policy (ED-1, decided during WP0)

There are **two environment profiles, one source of dependency truth**:

- **Dependency truth:** `pyproject.toml` at the repo root; `interplab` installed editable. No dependency is declared anywhere else.
- **Local + CI profile:** `uv`-managed project venv (`.venv/`, gitignored) with `uv.lock` **committed**. Torch is the CPU build locally. Rationale: the lockfile — not the venv — is what makes the environment reproducible, and Lodestar already standardized on `uv` (`d:\lodstar\uv.lock`); the two repos MUST share tooling.
- **Cluster profile:** Alliance module system + `virtualenv --no-download` + wheelhouse install, built by the checked-in `slurm/setup_env.sh` from a requirements export of the same `pyproject.toml` (`uv export`). CUDA torch. The profiles legitimately differ; no contract depends on environment identity.

**ED-19 (numpy-2 resolution, decided during WP8):** `lodestar-eval` requires `numpy>=2,<3`; the inherited mid-2024 HF pins (`accelerate==0.33.0` first among them) require `numpy<2`, making the tree unsatisfiable. Policy, in order:
1. The `==` pins on the HF stack (`transformers`, `accelerate`, `datasets`, `huggingface-hub`) are legacy-replication pins carried over from the pre-blueprint `requirements.txt` — no ED protects them. The lab migrates to a numpy-2-compatible resolution by relaxing the **minimum** set of blocking constraints, starting with `accelerate`, adding others only as `uv lock` proves each one necessary; everything not blocking stays pinned as-is.
2. **`sae-lens==3.23.0` MUST NOT be relaxed under this ruling** — the real checkpoints were trained under it and its relaxation is checkpoint-fidelity-critical. If resolution is impossible without touching it, stop and restore. *(ED-33: the "trained under it" premise is contested — verified T0.2 metadata reports `sae-lens 6.44.2`; the pinned-version identity is suspended pending cfg-format verification, and the "fidelity-critical" logic now cuts toward whichever library actually trained them.)*
3. Acceptance gate for the new lock: `uv lock` succeeds AND the full suite is green — specifically the golden delta test, identity tests, battery snapshot, and stats reference tests, which pin numerics at bit level. Any golden failure ⇒ restore and stop; an environment change that moves SS7 numerics is a §9 violation regardless of how it was caused.
4. Fallback if 2 or 3 fires: the lab stays on numpy 1.x, the SS8 Lodestar adapter stays paused, and whether to relax Lodestar's own floor (`numpy>=2.0` → e.g. `numpy>=1.26,<3`; its scipy/pandas constraints already admit 1.26) is the researcher's decision in the Lodestar repository — outside this blueprint's authority.
No third environment profile, no vendoring, no subprocess boundary: ED-1's single dependency truth is not negotiable for a Python-level import conflict.

**ED-32 (SAE-stack baseline, decided at T0.3):** the supported baseline is the **`sae-lens==3.23.0`-era stack** — 3.23.0 plus the `transformers`/`transformer_lens`/`datasets` versions the lock resolves *around* it — and it is fixed by ground truth, not chosen: the P1 checkpoints under certification were trained under 3.23.0 (the provenance ED-5/ED-27 is backfilling right now). **[CONTESTED — see ED-33: verified T0.2 metadata reports `sae-lens 6.44.2` on all four checkpoints; the "3.23.0" premise here is suspended pending cfg-format verification, though the *principle* of this paragraph is what compels following the new evidence.]** This extends ED-19 §2 from "don't relax during a numpy fight" to a standing contract, and it extends ED-27's own logic — *`cfg` determines how the bytes become a function* — one level out: **the loading library's major version is part of "how the bytes become a function."** The same `sae_weights.safetensors` decoded by `sae-lens` 3.x vs 6.x is a different function (format, cfg schema, normalization/activation conventions, encode/decode math all cross major-version boundaries), so a certificate is only meaningful relative to the library that gave the bytes their behavior.
1. **Baseline generation: ~~3.x~~ → 6.x** (revised by ED-33 §6 on verified T0.2 evidence; the "3.x" of this ruling rested on ED-19's unverified premise, since disproven — the checkpoints' `cfg.json` is 6.x-format and loads only under `sae-lens 6.44.2`). Baseline = `sae-lens==6.44.2` with the coherent modern stack it resolves (`transformers` 5.x, `transformer_lens`, `datasets` 5.x); `transformers`/`transformer_lens` remain the model-loading fidelity surface (`convert_qwen2_weights`, `HookedTransformer`) that moves with it. **A lock rebuild IS now implied** (pyproject `sae-lens` pin 3.23.0→6.44.2 and the stack around it) — the migration named in item 3, executed under researcher authorization.
2. **Compatibility guarantee:** faithful load + certification of checkpoints produced **under the baseline only**. The lab does NOT guarantee loading newer-`sae-lens` checkpoints; a 6.x-trained checkpoint is a *distinct scientific object* requiring its own declared baseline and its own certification, never a silent load under 3.x. **Multi-version support is rejected** — it makes "which library loaded this" a hidden variable inside every certificate (an ED-1 single-truth violation and a fidelity hole strictly worse than an honest single pin).
3. **Resolution: align the environment to the architecture, never the reverse.** A cluster carrying `sae-lens` 6.44.2 / `transformers` 5.x / `datasets` 5.0 is **unsanctioned drift** — ED-1 forbids global-environment installs and mandates the cluster profile be *derived* from the pinned `pyproject` via `slurm/setup_env.sh` (`uv export`). Rebuild it from the sanctioned flow; do not upgrade the blueprint to chase the drift. If the pinned stack genuinely cannot be built on the current Alliance wheelhouse, ED-19 §2's clause governs: **stop and escalate to the researcher — a silent jump to 6.x is never the fallback.** Migrating the baseline forward is a future researcher-scoped decision (new baseline ED + re-certification of every affected checkpoint), out of scope here.
4. **Fail-closed enforcement:** certification-lane jobs (SS4/SS5/SS6/SS7) MUST assert at startup that the resolved `sae-lens` major version equals the baseline and refuse to run otherwise — mapping to **§6.2 exit 4** (environment failure), *not* exit 3, which is reserved for missing/invalid/hash-mismatched *input artifacts*; a wrong runtime library is an environment fault, not a bad input. The refusal MUST be a **dedicated named exception** (`EnvironmentBaselineError`) with an explicit handler, so a designed, tested refusal is never wire-typed as an unexpected bug (the lab-wide honest-state-vs-failure discipline applies to exceptions too); the resolved versions MUST still be recorded on the *refused* run card, turning "which library refused this, and why" into auditable data. Only `sae-lens` is *gated*; `transformers`/`transformer_lens` are *recorded*, per this ruling's assertion clause. Jobs MUST record the resolved `sae-lens`/`transformers`/`transformer_lens` versions in the RunCard `environment` field (A10) — for the certification lane the previously-optional `environment` record is **mandatory**, so every certificate names the library that made its bytes mean something. Mechanism is implementer's choice; the fail-closed contract is not. Registry empty at ruling time ⇒ v1 clarification (ED-27–ED-31 standing).

**ED-33 (training-provenance contradiction, decided at T0.2) — supersedes the empirical premise of ED-32 and ED-19 §2.** Verified T0.2 metadata reports **`sae-lens 6.44.2`** for all four campaign checkpoints (d1bgp5v5, rwu04lpb, zf2o13m2, o1cx1dow), contradicting the "trained under 3.23.0" premise — which traces to the pre-blueprint `requirements.txt` pin and was asserted through ED-19→ED-32 but **never verified against an actual checkpoint until now.**
1. **Provenance outranks assertion.** ED-32's governing principle — *the baseline is fixed by the checkpoints' real training provenance, not chosen* — is not weakened by this; it is **enforced** by it. The 3.x baseline may NOT be retained to protect the prior ruling. A certificate issued under a library that did not produce the checkpoint's behavior is scientifically void, so the earlier conclusion follows the evidence or it is wrong.
2. **But one metadata string is not yet the finalized baseline.** Before the baseline is set, the engineer MUST determine whether `6.44.2` is the **training** version or a **resave / export / handling** version. Decisive test: each checkpoint's **`cfg.json` schema generation** (3.x vs 6.x structure) — per ED-27 the `cfg.json` is the identity-bearing artifact, so its format dictates the loading library regardless of any free-text version field. Plus: an empirical load test under 6.44.2 *and* 3.23.0, and a cross-check of the contemporaneous training config / wandb run against a possible later resave.
3. **Outcome mapping.** (a) cfg is 6.x-format and loads faithfully under 6.44.2 (the expected case — this matches the cluster ED-32 mislabeled as "drift") ⇒ **6.x is the operative baseline; ED-32 is revised to major 6**, principle intact. This triggers the researcher-scoped baseline migration ED-32 item 3 already names, whose blast radius includes **regenerating the 3.x `tiny_sae` fixture and re-pinning the ED-26 golden/identity references under 6.x** (cross-major encode/decode math ≠ the 3.x goldens) plus a lock rebuild — NOT a one-line pin bump. (b) cfg is 3.x-format (6.44.2 a resave artifact) ⇒ 3.x baseline stands; A5 records training-lib and resave-lib distinctly. (c) ambiguous / mixed ⇒ **stop and escalate to the researcher with the evidence**; certify under no guessed library.
4. **Interim T0.3 posture.** Certification does NOT proceed under an unverified baseline. ED-32's fail-closed check stays wired, but the version it asserts is **suspended** until §2 resolves; no certificate may be written under a library not confirmed to faithfully load the actual checkpoints — writing one now risks the exact invalidity ED-32 exists to prevent.
5. **A5 provenance (root-cause fix).** The training library MUST become a **recorded, measured** A5 field, never prose: add `training_provenance: {sae_lens, transformers, transformer_lens, source: "training_metadata"|"wandb"|"inferred", confidence}`; record any differing resave/handling version **distinctly, never blended** (ED-30 pattern); record `cfg_schema_generation` (ED-27-relevant). This closes the class of error that produced this contradiction — no future baseline rests on an unverified assumption. Engineer to confirm registry state; if still pre-write, these are v1 clarifications (ED-27–ED-32 standing).
6. **RESOLUTION (T0.2 evidence reviewed) — outcome (a) confirmed; baseline is 6.x.** All four checkpoints carry a structurally **6.x** `cfg.json` (nested `metadata`, top-level `k`, `architecture: "topk"`, no `hook_layer`, plus 6.x-only fields), independently corroborated this session: the 3.x reference (`tests/fixtures/tiny_sae/cfg.json`) is top-level/`activation_fn_str`/`hook_layer`-bearing, and the pinned `sae-lens==3.23.0` parser **rejects** the real cfg (`SAEConfig.__init__` missing required args — 3.23.0 discards the whole `metadata` block — and `"topk"` ∉ its legal architecture set), while 6.44.2 constructs it and dispatches `TopKSAE`. **The baseline decision rests on the *load* question — which library can instantiate these bytes — settled decisively and independently; the training-vs-resave finding (runner_cfg + resumption state + contemporaneous WandB runs, all pointing to *trained* under 6.44.2) refines A5 provenance per §5 but does not affect the baseline, since nothing but 6.x can load these SAEs regardless.** **One measured gap remains open:** only config *parsing* has been exercised, never a real ~3.3 GB weight-tensor load + forward. Therefore: the baseline is ruled 6.x now and the migration is authorized, but **no production certificate may be written until a full real-weight load + forward sanity check on ≥1 checkpoint under 6.44.2 passes on the cluster** (the last unmeasured link). Likely upside to verify during the lock rebuild: the 6.x/transformers-5/datasets-5 stack is numpy-2-native, so ED-19's numpy-2 conflict may dissolve and the SS8 `lodestar-eval` integration un-pause.
**§6 addendum (lock resolved).** Resolution is larger than projected: `sae-lens` 6.44.2 transitively forces `datasets` 2.20→5.0, `transformers` 4.44→4.57, `huggingface-hub`→0.36, `tokenizers` 0.19→0.22, and **`transformer-lens` 2.15→3.2 (major)**; `torch` 2.13.0 / `accelerate` 0.33 hold. Read: **correction toward the training stack, not drift from it** — the checkpoints were trained mid-2026 under `sae-lens` 6.44.2, so their real training environment was already a contemporary transformers/transformer-lens; the `4.44`/`2.15` pins (pre-blueprint `requirements.txt` lineage, same provenance as the disproven 3.23.0 premise) were the anachronism. But a major bump on the **model-loading fidelity surface** (`transformer-lens`: `convert_qwen2_weights` / `get_pretrained_model_config` / `load_and_process_state_dict`) requires proof, not faith. Therefore: (i) if training-time `transformer-lens`/`transformers` versions are cheaply recoverable (`runner_cfg` / training env), record them in `training_provenance` and prefer them where installable — do not rabbit-hole; (ii) the §6 cluster gate now validates **two** moved surfaces — full-weight load + forward must show sane activations from both the 6.x SAE *and* the 3.x model conversion before the first certificate; (iii) `delta_golden.json` and any model-derived pinned value regenerate under the final stack; the identity test stays valid (self-consistency, not byte-pinned). **A1/A3:** `tokenizers` moved, so the committed `corpus_manifest`/`census_report` keep their *identity* (recipe hash + text `sample_checksum` are tokenizer-independent; `doc_count` too) but their `token_count` / per-million *payloads* are unverified under the new stack — re-run the census and correct the payload (**regeneration, not re-identification**) before either roots a chain. Both deferrable to cluster-access return; no certificate issues before the gate regardless.
**§6 completion (migration executed, suite green under the pinned stack).** Final lock: `sae-lens` 6.44.2, `transformers` **5.12.1** (pinned to the training-time cluster manifest — matches what produced the checkpoints, crossing the 4→5 major deliberately, not the solver's lower 4.57), `datasets` 5.0.0, `transformer-lens` 3.2.1, `huggingface-hub` 1.24.0, `tokenizers` 0.22.2; `torch` 2.13.0 / `accelerate` 0.33 held. **`numpy` stayed 1.26.4 — the ED-19 numpy-2 conflict did NOT dissolve; SS8 `lodestar-eval` stays paused** (the earlier "may dissolve" upside did not materialize). Two model-loading-surface behavior changes were found and handled, both confirmed identical on Windows and Linux (version behavior, not platform): (1) `transformer-lens` 3.2.1's `HookedTransformer(cfg, tokenizer=…)` **silently drops the trailing `<eos>`** — the delta-golden prompt went 33→32 tokens; (2) the KV-cache class moved (`HookedTransformerKeyValueCache` → `cache.key_value_cache.TransformerLensKeyValueCache`). `tiny_model` weights regenerated **byte-identical** (only transformers-5 save-format JSON changed); `tiny_sae` + `delta_golden` regenerated fresh; `MAX_ULP` 32→128 (measured clamp 32 / add_direction 4 under 6.x TopK, ED-26's 4× convention). **Residual gap for the §6 cluster gate:** the training-time `transformer-lens` version is unrecoverable (recorded `null`), so the `<eos>`-drop behavior is on a surface whose training match is unverified — the full-weight forward MUST additionally confirm real-Qwen tokenization/positions are as expected, not merely that activations are finite. `fp32_copy` fix (`type(sae)(cfg)`) landed on all **three** sanctioned §1 duplicates (certification/metrics, interventions/hooks, characterization/indexer — the third surfaced by the suite). Certification lane remains closed until the gate runs.
- **Global-environment installs are forbidden** for any interplab work, local or cluster.
- RunCards SHOULD record the producing environment via the optional `environment` payload field (A10).
- CI runs entirely on the local profile; no CI job may require the cluster profile (consistent with §8.3).

### 2.1 Envelope (all registry artifacts)

Every JSON artifact in the registry MUST be a single UTF-8 JSON object with these top-level fields, plus a type-specific `payload`:

```json
{
  "artifact_type": "sae_certificate",
  "schema_version": 1,
  "self_hash": "sha256:…",
  "created_at": "2026-07-08T14:32:00Z",
  "created_by": {
    "run_id": "r20260708-1432-a7f3",
    "code_commit": "git sha",
    "entrypoint": "interplab.jobs.certify",
    "host": "tamia|local"
  },
  "subject": [ {"content_hash": "sha256:…", "location": "<URI, §3.2>", "role": "checkpoint"} ],
  "payload": { }
}
```

- `subject` lists the artifact(s) this artifact is *about* (empty list for root artifacts like `CorpusManifest`).
- `self_hash` = SHA-256 of the RFC 8785 (JCS) canonical form of the object **with `self_hash` removed**. Verification MUST recompute it on read (`core.envelope.load()` does this; never hand-parse registry files).

### 2.2 Content-hash strategy by artifact class

| Class | Strategy |
|---|---|
| JSON registry artifacts | `self_hash` as above |
| Single heavy file | `sha256(file bytes)` |
| Heavy directory (checkpoint, store, index) | `sha256` over the sorted lines `"<relpath>\0<sha256(file)>\n"` for every file; hidden/tmp files excluded; computed **at creation, on the machine that created it** (D1) |
| External corpus (HF dataset) | **recipe hash**: `sha256` of canonical JSON `{dataset, revision, split, subset_spec, filters}` — primary identity; plus advisory `sample_checksum` = sha256 of first 1,000 documents' text |
| ConceptBattery / git-tracked data | content hash of the canonicalized file set (as heavy directory) + human semver in the file |

`core.hashing` implements all of these; subsystems MUST NOT implement their own.

### 2.3 Canonical JSON serialization erratum (ED-2, decided during WP0 compliance revision)

`core.canonical_json` follows RFC 8785 (JCS) **structurally**: object members sorted by key (recursively), no insignificant whitespace, compact separators, UTF-8 output with non-ASCII left unescaped, and non-finite numbers (`NaN`/`Infinity`) rejected outright.

It does **not** implement RFC 8785's number-formatting rule (the ECMAScript `Number::toString` algorithm). Numbers are serialized using Python's native float/int representation instead. This is deliberate, not an oversight: every `self_hash` in this system is both computed and verified exclusively by this same Python codebase (`core.envelope.load()`/`dump()`) — no other language ever recomputes or checks a hash, so byte-for-byte JCS interoperability with a non-Python JCS implementation is not a requirement anywhere in the architecture. What's required is determinism *within* this codebase, which Python's own serialization already guarantees run to run.

**This is the approved canonical serialization policy for `interplab`, not a defect.** It MUST NOT be "fixed" to strict ECMAScript number formatting in a later work package without a blueprint revision — doing so would change every previously computed `self_hash` and invalidate the entire existing registry. Reference implementation: `interplab/core/canonical_json.py` (unchanged by this erratum).

---

## 3. Storage Topology and Filesystem Layout (implements D1)

### 3.1 Authoritative locations

| Data | Authoritative home | Notes |
|---|---|---|
| Heavy artifacts: activation stores, SAE checkpoints, characterization indexes, raw generations | Cluster: `$SCRATCH/interplab/<class>/<hash12>/…` | never synced in full; `<hash12>` = first 12 hex chars of content hash |
| Registry artifacts: manifests, certificates, run cards, claims, compat map | Local repo: `registry/<type>/<hash12>.json` | git-tracked (small JSON only); the user commits manually |
| Schemas, ConceptBattery, configs, code | git | |
| Training telemetry | WandB offline | non-authoritative; run_id cross-referenced |

### 3.2 Location URIs

`tamia:<path-under-$SCRATCH/interplab>` · `local:<repo-relative path>` · `hf:<dataset>@<revision>` · `wandb:<run>`. `core.uris` parses/validates; no raw path strings in payloads.

### 3.3 Registry sync (cluster → local)

Cluster jobs write registry artifacts to `$SCRATCH/interplab/outbox/`. A pull script (`interplab.jobs.sync_registry`, leaf) copies outbox files into `registry/`, verifies `self_hash`, and empties the outbox. Conflicts are impossible by construction (content-addressed filenames). An artifact not yet synced **does not exist** for claim purposes.

### 3.4 Registry tree

```
registry/
├── corpus_manifest/     ├── census_report/      ├── store_manifest/
├── sae_checkpoint/      ├── sae_certificate/    ├── characterization_manifest/
├── feature_certificate/ ├── intervention_result/├── run_card/
├── claim_report/        └── eval_compat_map/
```

One file per artifact: `<hash12>.json`. `interplab.registry` MAY maintain a derived SQLite index for query speed; it is a cache, rebuildable by scan, never authoritative, and MUST live outside git.

---

## 4. Artifact Specifications

For each: identity, storage, payload schema (field: type — semantics), versioning/compatibility, consumers. Envelope fields are implied. Initial `schema_version` = 1 for all; evolution per D3: optional-field additions stay within a version; removals/semantic changes bump it; consumers declare `min_schema_version` in claim specs; stale artifacts are recomputed on demand, never edited.

### A1 `corpus_manifest` (SS1)
Identity: recipe hash (§2.2). Storage: registry.
Payload: `name: str` · `recipe: {dataset, revision, split, subset_spec, filters}` · `token_count: int` · `doc_count: int` · `dedup_rate: float|null` · `tokenizer: {name, revision}` · `sample_checksum: str`.
Legacy provision (ED-8): for pre-blueprint corpora whose full recipe is unrecoverable (e.g., the local `fineweb_subset` scratch copy), recipe fields MAY carry the literal string `"unknown"`, recorded honestly; `sample_checksum` then becomes the operative identity and is mandatory.
**ED-28 (stream scope, decided at T0.1):** A1 describes **a defined token stream, never an available dataset**. `recipe` MUST determine the token set exactly; for the training-corpus role that stream is the one *consumed by training*, with `subset_spec` carrying the consumption bound (`order`, `take_tokens`/`take_docs`, and `shuffle: {seed, buffer}` when shuffled). Rationale: identity is the recipe hash, so a `subset_spec` omitting the consumption bound collides scientifically different streams (a 300M-token consumed prefix vs a 262 GB dataset) under one identity — the same failure ED-27 rejected from the other side. Every consumer question (SS6's frequency stratum, SS9 discoverability: "could this SAE have learned X?") is about what the model *saw*, not what existed on disk. Scanning an entire available dataset is therefore never required unless some A1 defines it as its stream. `sample_checksum` = first 1,000 documents **in stream order**, which is well-defined only because `subset_spec` pins order. Two uses of sampling, never conflated: **sample-as-stream** (A7's "corpus_manifest(s) of the sample") — the sample *is* the artifact, its selection rule lives in `recipe.subset_spec` and is part of identity, and a census over it is `coverage: "full"`; **sample-as-measurement** — see A3.
**ED-31 (replay invariant — document stream vs packed tokens, decided at ED-28 implementation):** the stream A1 certifies is the **consumed document stream** — the ordered document set fixed by `recipe` — *not* the post-packing token sequence SAELens forms (concatenation + BOS separators + fixed-size windowing). Two consequences. (1) A1's `token_count` is the **document-stream** count (independent per-document tokenization), packing-independent and reproducible; it is deliberately NOT SAELens' windowed `n_training_samples`. The replay self-check verifies *document-stream* reproducibility: recomputed `doc_count` / `token_count` / `sample_checksum` MUST equal A1's recorded values exactly — drift there is a hard error, because the document stream is what identity pins. (2) SAELens' packed sample/token accounting is **training-side telemetry**, belonging to A5 (`tokens_trained`); the census replay MUST NOT gate on it by exact equality — that compares two different quantities (the ED-30 anti-pattern of treating a foreign number as a verification target). It is advisory: cross-checked within a **structural** sanity band whose expected delta is *derived and documented* (≈ one BOS per document, minus up to one dropped final partial window, ± any cross-boundary merge effects), a gross mismatch (wrong order of magnitude) blocks-and-investigates, a small structural delta is expected and never science-invalidating. Rationale: **packing is a training transformation applied to the corpus, not a property of the corpus.** Binding A1 identity to `context_size` / BOS policy / `drop_last` is a layering violation — the *same* document stream packed under a different context window would mint a different `corpus_manifest`, which is wrong: the corpus did not change. Packing lives downstream, at A5. Registry empty at ruling time ⇒ v1 clarification (ED-27/28/29/30 standing).
Consumers: SS2/SS3 configs reference it; SS9 chains require it as the root link.

### A2 `concept_battery` (SS1; source of truth in `data/concepts/`)
Identity: content hash of the file set; payload `battery_version: semver`.
Source file schema (per concept, YAML): `concept_id: kebab-case str` · `languages: {en|fr|zh|ar: {status: "complete"|"probes_only", probes: [str], word_absent: [str], concept_absent: [str], census_terms: [{term: str, kind: "canonical"|"variant"|"inflection"|"transliteration", origin: str}]}}` · `matched_controls: [concept_id]` · `notes/provenance: str`.
**Two negative instruments, never conflated (ED-10):** `word_absent` = concept-PRESENT, term-absent contexts (the *sensitivity* instrument: a good feature SHOULD fire). `concept_absent` = unrelated baseline text (the *specificity-denominator* instrument: a good feature should NOT fire). Source `GENERAL_TEXT`-style baselines belong in `concept_absent` and MUST NOT populate `word_absent` — feeding concept-absent text into the sensitivity measurement inverts its meaning (good features fail, junk features pass). The source corpus contains no true word-absent contexts; therefore **battery v1 has no `complete` languages**, and SS6 sensitivity remains unimplementable until the researcher authors word-absent content (battery v2) — the honest state the original repository audit already identified. `concept_absent` is orthogonal to `status` (like `census_terms`).
**Census terms (ED-9):** census terms are battery content — researcher-authored, per the ED-8 authorship policy — with one mechanical carve-out: battery v1 MAY derive the English term from `concept_id` (underscores→spaces, `origin: "concept_id"`), since the identifier originates from source. Legacy behavioral keyword lists (`POUTINE_KEYWORDS` etc.) MUST NOT be mined for census terms — they encode associate-matching, a different instrument. The census matches exactly the recorded strings under the recorded matcher config: no stemming, morphological expansion, or fuzzy matching (algorithmic form-generation is scientific authorship by other means). `census_terms` presence is orthogonal to `status` — one governs census, the other sensitivity. Minimums enforced by schema test (ED-8): `complete` requires ≥10 probes AND ≥5 word_absent; `probes_only` requires ≥10 probes. Sub-minimum word_absent entries found in source are preserved in the file (losslessness) but the language is `probes_only` and consumers MUST NOT use its negatives.
**Authorship policy (ED-8):** battery content — probes, negatives, translations — is scientific content, authored only by the researcher or their delegates, never by implementation engineers or coding agents (translations included: a translated negative control that smuggles in the target term produces false sensitivity readings). Mechanical extraction from existing source is implementation work and MUST be lossless, provenance = source file + commit. Any content change is a `battery_version` bump with the author named in provenance. Multilingual completion (promoting `probes_only` languages to `complete`) is an explicit researcher task, tracked as battery v2+.
Consumers: SS1 census, SS6 validation, SS8 prompts. Consumed by battery content hash — never by importing Python constants. SS6 computes sensitivity from `complete` languages only; `probes_only` languages contribute descriptive cross-lingual firing checks, never sensitivity numbers.

### A3 `census_report` (SS1)
Subject: corpus_manifest + concept_battery. Storage: registry.
Payload: per concept × language: `{status: "measured"|"no_terms", per_term: [{term: str, occurrences: int, token_split: [str], byte_fallback: bool}] | null, occurrences_total: int|null, per_million_tokens: float|null, doc_count: int|null}`; plus `method: {matcher: "regex|tokenizer", case_folding: bool, boundary: "word"|"substring"}` (ED-9: `no_terms` rows carry nulls, never zero — zero is a measurement, null is the absence of an instrument; per-term breakdown keeps dominant variants visible; `boundary` recorded per language so substring matching in unsegmented scripts stays auditable).
**ED-28 (coverage semantics):** the census measures over exactly the stream its subject A1 defines — no more, no less. `method` gains `coverage: "full" | "sampled"`. Under `"sampled"` (sample-as-measurement: A1 still defines the full consumed stream, the census scans part of it) `method.sampling: {rule, seed, realized_docs, realized_tokens}` is mandatory, A1's identity is untouched, and affected rows carry `status: "estimated"` with the **raw sample counts alongside the realized denominators**, so any interval estimator can be applied downstream (choosing one is SS9/stats + researcher work, not an identity matter). ED-9's doctrine extends: zero is a measurement, null is the absence of an instrument, **an estimate is neither**. Consumption rule: **absence and rarity claims require `coverage: "full"`** — an estimated zero licenses no "absent from the training stream" statement, since sampling error dominates exactly where the frequency stratum is most interesting; presence/frequency claims MAY rest on a labeled estimate, with SS9 surfacing coverage in the chain table. Since the registry holds zero artifacts at ruling time, these are v1 clarifications, not a `schema_version` bump (same standing as ED-27).
Consumers: SS6 (frequency stratum), SS9 (required link for any discoverability claim).

### A4 `store_manifest` (SS2)
Subject: corpus_manifest. Identity: directory hash of the store. Storage: manifest in registry; store on cluster.
Payload: `model: {name, revision}` · `hook_name: str` · `hook_layer: int` · `context_size: int` · `prepend_bos: bool` · `dtype: str` · `token_count: int` · `position_policy: {exclude_bos: bool, exclude_padding: bool, excluded_first_n: int}` · `eval_holdout: {method: "doc_hash_mod", modulus: int, residues: [int]} | null` (ED-5: documents matching the rule are **excluded from the store at collection** and reserved for certification; null only for legacy stores) · `qa: {norm_by_position: [float], special_token_fraction: float, adjacent_autocorrelation: float, chat_divergence: {…}|null, verdict: "green|amber|red"}`.
Invariant: `special_token_fraction` MUST be 0.0 unless `position_policy` documents inclusion.
QA verdict mechanics (ED-11): thresholds follow the SS4 bands pattern — placeholder data file, calibrated on the first real store, version recorded in the payload. The verdict is driven by the three specified metrics (norm-by-position flatness, special-token fraction, adjacent autocorrelation); `chat_divergence` is recorded evidence with an implementer-defined self-describing shape, nullable, and never gate-bearing.
Consumers: SS3 (MUST refuse red stores), SS4 (evaluates on the declared holdout, per ED-5).

### A5 `sae_checkpoint` (SS3)
Identity: directory hash of weights dir (SAELens format unchanged). Storage: weights on cluster; manifest in registry.
**ED-27 (identity file set, decided at backfill):** "weights dir" means the **SAELens load closure** — exactly `{cfg.json, sae_weights.safetensors}`, the files `SAE.load_from_pretrained` reads to instantiate the function a certificate speaks about. The hash is the §2.2 heavy-directory manifest (same `"<relpath>\0<sha256(file)>\n"` line format, sorted) restricted to that fixed file set; either file missing ⇒ hard error, never a silent subset. **Excluded from identity:** `trainer_state.pt` (optimizer state — training provenance; two dirs with identical weights but different optimizer states are the *same* artifact), `runner_cfg.json`, `sparsity.safetensors` (derived statistic, not behavior-defining), logs, and any other auxiliary or stray file. Weights-only (without `cfg.json`) is also wrong: cfg determines how the bytes become a function (hook point, dims, activation, normalization) — identical weight bytes under different cfgs MUST NOT collide under one identity. Payload MAY carry an advisory `directory_listing` (relpath + size, no hashes) for forensics; advisory fields are never verified. D1 unchanged: computed at creation/backfill on the machine holding the weights.
Payload: `config: {full SAELens config as trained}` · `store_hash: sha256 | null` (ED-5: null only for legacy checkpoints trained via SAELens streaming before stores existed; the training corpus is then documented by `config.dataset_path` plus a `corpus_manifest` reference in `subject`) · `seed: int` · `tokens_trained: int` · `wandb: str|null` · `telemetry_tail: {fvu: float, dead_count: int}`.
**ED-29 (`model_dir_hash`, decided at backfill):** the `role: "model"` subject ref keeps the **unrestricted** §2.2 heavy-directory hash (`core.hashing.hash_directory`) over the resolved base-model snapshot — ED-27's restriction does NOT generalize to it. The asymmetry is deliberate: the SAE checkpoint is an artifact the lab *produces*, so the lab must define its identity, and ED-27's carve-out was justified by a specific, named, guaranteed-to-vary, definitionally-non-behavioral file (`trainer_state.pt`). A base-model snapshot has no such file; a model "load closure" would instead require a per-family allowlist over sharded weights, index, tokenizer, and `generation_config.json` — and an allowlist that misses one behavior-affecting file (a shard, a tokenizer file, generation config that steering generations depend on) is an **integrity hole**, strictly worse than the false alarms unrestricted hashing risks. `hash_directory`'s existing exclusions (hidden files, `.tmp/.temp/.part`) already drop HF cache internals (`.lock`, `.no_exist`, `.cache/`). Two requirements attach, **and they bind every A5 producer, not only this backfill job** (the backfill is merely the first producer to exercise them; a live SS3 training job that ever writes A5 is equally bound — the rule is a property of A5's `role: "model"` ref, producer-agnostic, because a floating model pointer breaks chain reproducibility identically whether the checkpoint was backfilled or freshly trained): (a) the ref's `location` MUST resolve to an **immutable, revision-pinned** identity — for an HF-hosted base model this means `hf:<repo>@<commit-sha>` with the commit SHA mandatory (a bare `hf:<repo>`, which floats with upstream `main`, is forbidden as the sole identity); for a base model that lives only on the cluster with no upstream (`tamia:`/`local:`), there is no floating pointer to forbid and the `content_hash` directory hash carries identity, but a mutable path MUST NOT be the sole identity. This portable pin, not the local directory hash, is the model's canonical identity, since the base model is a *consumed* artifact whose identity is already fixed upstream; (b) because a whole-directory hash is machine-local by nature, a later mismatch **blocks and triggers investigation, never silently passes**, but MAY resolve as "same revision, benign file-set difference" documented in the run card rather than invalidating the science.

**ED-30 (`telemetry_tail.fvu`, decided at backfill):** A5's telemetry is **training-run telemetry, never a certified metric**. Both candidates D-1 surfaced are training-time values — neither was computed on the ED-5 declared holdout under certification discipline — so neither may be presented as *the* FVU of an SAE: that is A6 `metrics.fvu` (GATE G1, banded, verdict-bearing), and it is the only FVU any claim, band evaluation, gate, or report may consume. Canonical value: **the training run's aggregated evaluation FVU when available** (lower variance than a single final batch), **else the final training-step FVU**, with a mandatory `fvu_source: "training_eval" | "training_step" | null` discriminator — recording a number whose provenance is ambiguous is precisely the failure this lab exists to prevent. MUST NOT: blend or average the two, or recompute either at backfill time (a fresh measurement dressed as recovered provenance). If neither is recoverable, `fvu: null` with `fvu_source: null` — ED-9's doctrine, unchanged: zero is a measurement, null is the absence of an instrument. Same nullability extends to `dead_count` for legacy rows. Registry empty at ruling time ⇒ v1 clarification, not a version bump (ED-27/ED-28 standing).

Legacy backfill (ED-5): the six-plus pre-blueprint checkpoints receive backfilled A5 manifests — directory-hashed on the cluster per D1, `store_hash: null`, config and `tokens_trained` taken from their training configs and logs. This backfill is WP2's first task; retro-certificates subject the backfilled hashes.
Consumers: SS4, SS5, SS6, SS7 (via SS5 max units).

### A6 `sae_certificate` (SS4) — GATE G1
Subject: sae_checkpoint. Storage: registry.
Payload: `eval_slice: {corpus: {content_hash, location}, selection: {method: "holdout_split" | "stream_offset", params: {…}}, n_tokens: int, disjointness: "by_construction" | "by_offset_argument"}` (ED-5: the slice is *text*, pinned by corpus reference + deterministic selection rule; certification collects activations fresh by running the model — CE-recovered structurally requires model forwards and cannot be computed from stored activations) · `metrics: {ce_recovered: float, fvu: float, dead_fraction: float, density_histogram: {bin_edges_log10: [float], counts: [int]}, max_decoder_cosine_p999: float, per_position_fvu: [float]}` · `bands_version: int` · `verdict: "green|amber|red"` · `per_metric_verdicts: {…}`.
Metric pin (ED-5): `max_decoder_cosine_p999` = per feature, the max cosine to any *other* feature's decoder direction; report the 99.9th percentile of that per-feature distribution, computed exactly (chunked matmul), never estimated by pair sampling.
Compatibility: band recalibration bumps `schema_version` (D3).
Consumers: SS5 (soft), SS9 (hard link).

### A7 `characterization_manifest` (SS5)
Subject: sae_checkpoint + corpus_manifest(s) of the sample. Identity: directory hash of the index. Storage: index on cluster (physical format self-described by `index_layout_version` — ED-12: layout v1 is dependency-free JSON columnar + JSONL example shards; parquet is the authorized layout v2 when production scale demands it, expected at 5–10M-token indexes); manifest in registry.
Payload: `sample: {n_tokens: int, chat_slice_tokens: int}` · `index_layout_version: int` · `per_feature_columns: [name]` (MUST include `corpus_max, firing_rate, decile_boundaries, logit_top_tokens, autointerp_label, autointerp_detection_score`) · `judge: {model, rubric_version, prompt_version}` for autointerp fields (D2).
Consumers: SS6, SS7 (corpus_max — the ONLY legal source of steering units), dashboards.

### A8 `feature_certificate` (SS6) — GATE G2
Subject: sae_checkpoint (+ characterization_manifest + concept_battery + census_report).
Payload: `feature_index: int` · `concept_id: str` · `specificity: {decile_means: [float], rubric_version, judge_model, prompt_version}` · `sensitivity: {status: "measured"|"unavailable", word_absent_fire_rate: number|null, per_language: {…}|null}` (ED-13, extending ED-8/ED-10: `measured` iff ≥1 `complete` language existed for the concept at validation time, aggregate over exactly those languages; `unavailable` carries nulls, never zeros — the ED-9 idiom) · `cross_lingual_firing: {lang: {probe_fire_rate: number}}|null` (descriptive data from `probes_only` languages; never feeds sensitivity or the verdict) · `selectivity: {neighbors: [{index, cosine, note}]}` · `probe: {auc: float, feature_auc: float, gap: float, probe_config_hash}` · `verdict: "green|amber|red"` · `verdict_basis: [str]` (ED-13: the instruments that fed the verdict — the verdict grades available instruments and says so; whether a downstream claim requires a specific instrument is a claim-spec question for SS9 chain assembly, not hard-coded here).
Compatibility: judge fields MUST resolve as compatible under the current `eval_compat_map` for the certificate to be chainable (D2).
Consumers: SS7/SS8 claim-mode runs, SS9.

### A9 `intervention_result` (SS7 + SS8)
Subject: sae_checkpoint (+ feature_certificate when claim-mode).
Identity: self_hash; raw generations dir on cluster, hash recorded.
Payload: `spec: InterventionSpec (§5.SS7, serialized)` · `arms: [{arm: "steered|baseline|random_direction|random_feature|prompt_baseline", scales_in_max_units: [float], generations_ref: {content_hash, location}}]` · `blinding: {shuffled: bool, map_ref: …}` · `sampling: {temperature, top_p, max_new_tokens, seed}` · `lodestar: {run_ref, judge_model, rubric_version, per_prompt_scores: [{prompt_id, arm, scale, score}]|null}|null` (ED-17: the judge job materializes per-prompt scores into the artifact at ingestion so SS9 statistics are registry-pure — chain assembly and stats never call Lodestar; `per_prompt_scores` is null before judging or for runs predating ED-17) · `capability_delta: {slice: {content_hash, location}, n_tokens: int, per_arm: [{arm: str, scale: number|null, ppl: number}]} | null` (ED-20: §5.SS8's capability-degradation measurement made concrete — perplexity on the fixed, content-hash-pinned text slice under each (arm, scale); the baseline arm appears as an entry with `scale: null`; deltas are derived by consumers, never stored (derived-status rule); written by the judge job alongside `per_prompt_scores`; null before evaluation. One number per (arm, scale) — no per-prompt structure, so it feeds report tables/narrative, never `bootstrap_ci` (ED-17 statistics compose per-prompt scores only)).
Invariant: claim-mode results MUST contain all three control arms and `blinding.shuffled = true`.
A9′ semantics (ED-21): registry artifacts are immutable — the judge job never mutates A9. "Results back into A9" (§6.1) means the judge job emits a **new** `intervention_result` artifact carrying the identical payload with `lodestar`/`capability_delta` filled, whose `subject` additionally carries `{role: "judged_from", content_hash: <pre-judge A9>}`. The unjudged A9 remains in the registry as the explore-trail fact; claim specs anchor the judged artifact.
Consumers: SS9.

### A10 `run_card` (SS10)
Identity: self_hash; also carries human `run_id` (`r{YYYYMMDD}-{HHMM}-{4hex}`).
Payload: `run_id` · `stage: "census|collect|store_qa|train|backfill|certify|characterize|validate|steer|judge|report|sync"` (ED-11: `stage` is the run's provenance role and MUST name what the run actually did — no aliasing; `collect` is reserved for the future job that materializes an activation store applying A4's `eval_holdout` at collection time; `backfill` covers A5 backfill runs, which are not training runs) · `config_hash` · `config_ref` · `inputs: [{content_hash, location, role}]` · `outputs: [same]` · `status: "completed|failed|gate_failed"` · `exit_code: int` · `outcome_line: str (≤200 chars)` · `slurm: {job_id, nodes}|null` · `log_section: int|null` (cross-ref into FEATURE_EXPERIMENT_LOG.md) · `environment: {profile: "local|cluster", python: str, torch: str, lock_hash: str|null}|null` (optional, per ED-1).
Note: `status` describes the *run* (a fact about the past), not artifact state — no lifecycle fields anywhere (frozen-architecture rule).

### A11 `claim_report` (SS9) — output of GATE G4 assembly
Payload: `claim_spec: {question: str, anchor: {artifact_type: str, content_hashes: [sha256]}, required_links: [{artifact_type, subject_role, via: "subject_ref"|"subject_of", min_schema_version, require_instruments: [str] (optional)}], eval_compat_version}` (ED-14: `anchor` pins the claim's terminal evidence artifact(s) by full hash — ≥1 hash, all of `artifact_type`; multiple hashes are replicates of the same experiment, e.g. per-seed A9s, and MUST resolve every non-anchor link to identical artifacts — divergence is a claim-spec authoring error, exit 3. The anchor is scientific content: which evidence a claim is about is part of the claim, researcher-authored like every claim-spec field. ED-15: `via` declares traversal direction, §5.SS9. ED-16: `require_instruments` is legal only on `feature_certificate` links and names instruments that MUST appear in the certificate's `verdict_basis` — the ED-13 deferral landing here.) · `chain: [{link, artifact_hash|null, status: "ok|missing|stale_schema|eval_incompatible|red_verdict|insufficient_evidence", note: str|null}]` (ED-15: `note` records disambiguation and failure detail — the field §5.SS9's "records the ambiguity in the chain" always required. ED-16: `insufficient_evidence` = artifact resolved and not red, but lacks evidence this claim requires: a required instrument absent from A8 `verdict_basis`, or a non-claim-grade A9 anchor. v1 claim specs MUST contain at most one required link per `artifact_type` — multi-instance chains are a future claim_spec schema bump, D3.) · `stamp: "CERTIFIED|DRAFT — UNCERTIFIED CHAIN"` · `statistics: {per-metric: {estimate, ci_low, ci_high, n_prompts, n_seeds, method}} | null` (ED-17: `null` when no anchor payload carries per-prompt scores — absence, never fabricated numbers, the ED-9 idiom) · `figures: [{name, ref: {content_hash, location}}]` · `rendered: {md_ref: {content_hash, location}, html_ref: {content_hash, location}}` (ED-17: renders and figures are small files under repo-root `reports/`, git-tracked, committed manually like registry files).
Invariant: `stamp = CERTIFIED` iff every chain link status is `ok`. No override parameter exists.

### A12 `eval_compat_map` (SS8-owned)
Payload: `version: int` · `judge_classes: [{class_id, members: [{judge_model, rubric_version, prompt_version}]}]`. Two evaluations are compatible iff in the same class. Edited only by hand, by the researcher (D2).

---

## 5. Subsystem Implementation Specs

Per subsystem: Responsibilities · Public interface · Inputs → Outputs · Invariants · Dependencies · Failure modes · Extension points. (Artifact schemas are §4; contracts are those schemas.)

### `interplab.core` (plumbing; not a subsystem — implements §2–§3)
Modules: `hashing`, `envelope` (load/dump with self-hash verify), `uris`, `configs` (YAML + schema validation), `canonical_json` (RFC 8785). Invariants: `envelope.load` raises on hash mismatch; no module here knows any artifact payload semantics. Failure modes: none tolerated — this is trunk-adjacent; full test coverage required. *Implementer's choice:* pydantic vs jsonschema internally, provided schemas/ files remain the published contract.

### SS1 `interplab.corpus`
**Responsibilities:** corpus manifests; battery compilation (`data/concepts/*.yaml` → `concept_battery` artifact); census.
**Interface:** none (batch only).
**Inputs → outputs:** HF dataset recipe → A1; battery files → A2; (A1, A2) → A3.
**Invariants:** census counts computed on the *tokenized* stream with the manifest's tokenizer revision; matcher config recorded; a concept with 0 occurrences is a row, not an omission.
**Failure modes:** HF revision drift (pin revisions; recipe hash changes otherwise); regex matcher over-counting substrings (`matcher` field makes it auditable).
**Extension points:** new languages in battery schema; alternative matchers behind the `method` field.

### SS2 `interplab.store_qa`
**Responsibilities:** QA measurements over a finished store; verdict; A4 emission. (Collection itself stays in SS3/SAELens path or legacy collector; QA runs against whatever store the training will consume.)
**Interface:** none.
**Invariants:** QA reads a sample ≥1M positions; autocorrelation computed on the store's *serving order*; chat-divergence slice uses the same model revision.
**Failure modes:** sampling only the head of the store (MUST stratify across shards).
**Extension points:** additional QA metrics are additive payload fields (no version bump).

### SS3 `interplab.training`
**Responsibilities:** thin wrapper around SAELens: inject manifest emission (A5), seed policy, telemetry tail, and refuse red stores. No training-logic ownership.
**Invariants:** the exact SAELens config that ran is serialized into A5 (no reconstruction from YAML); `store_hash` verified before start.
**Failure modes:** SLURM timeout mid-run — partial checkpoints get manifests with `tokens_trained` honestly recorded (the 94%-of-job-338944 case becomes a legal, documented artifact).
**Extension points:** new SAE architectures pass through untouched (config is opaque here; SS4 judges results).

### SS4 `interplab.certification` — G1
**Responsibilities:** compute A6 metrics over a held-out slice; apply bands; emit certificate + one-page report card (md/png).
**Interface:** none.
**Invariants:** `ce_recovered` baseline is zero-ablation of the hook point, same slice, same batch order; the eval slice is text-level and disjoint from training tokens — by construction via A4's `eval_holdout` for store-trained SAEs, or by a recorded stream-offset argument for legacy checkpoints (ED-5) — with the mechanism named in A6's `disjointness` field; certification collects activations fresh through the model (never from a stored slice); metrics computed in fp32.
**Failure modes:** OOM on 64x dicts (stream features in chunks — *implementer's choice* of chunking); accidental training-slice reuse (invariant test).
**Extension points:** metrics are additive; bands live in `schemas/sae_certificate/bands_v<N>.json` so recalibration is a data change + schema bump, not code.

### SS5 `interplab.characterization`
**Responsibilities:** the streaming indexer (cluster job) and the **search API** (one of two live interfaces); dashboard renderer (leaf).
**Interface:**
```python
class FeatureIndex:
    @classmethod
    def open(cls, manifest: PathOrHash) -> "FeatureIndex"
    def feature(self, i: int) -> FeatureView          # stats + example refs
    def corpus_max(self, i: int) -> float             # THE steering unit source
    def search_by_activation(self, texts: list[str], top_n: int) -> list[Hit]
    def search_by_cosine(self, seed_index: int, top_n: int) -> list[Hit]
    def search_by_label(self, query: str, top_n: int) -> list[Hit]

    # ED-3 additions (additive, permitted by this subsystem's extension clause):
    @property
    def n_features(self) -> int
    def firing_rate(self, i: int) -> float            # fires-per-token over the index sample
    def sample_matched_frequency(
        self, target_index: int, *, rng_seed: int,
        band: float = 3.0, exclude: frozenset[int] = frozenset(),
    ) -> int
    # Uniform draw via np.random.default_rng(rng_seed) over the SORTED list of
    # eligible indices: firing_rate within [target/band, target*band], excluding
    # {target_index} ∪ exclude. Deterministic for fixed (index content, arguments).
    # Raises MatchedSampleError if the band is empty — callers MUST NOT widen it
    # silently; an empty band is a finding about the feature, recorded in the run.
```
**Invariants:** index is write-once (content-addressed); decile examples sampled uniformly *within* deciles; chat-slice statistics stored separately, never mixed into corpus_max.
**Failure modes:** index too large to open remotely — `FeatureIndex.open` MUST work against a synced *columnar subset* (the per-feature stats file, in whatever layout `index_layout_version` declares — ED-12) without example shards; example fetch degrades gracefully to "on cluster only".
**Extension points:** new per-feature columns are additive; new search modes are new methods (no signature changes to existing ones).

### SS6 `interplab.validation` — G2
**Responsibilities:** specificity (Lodestar rubric over deciles), sensitivity, selectivity, probe comparator; emit A8.
**Interface:** none (batch). Uses SS5 search API and `interplab.stats`.
**Invariants:** decile contexts drawn from the characterization index, never from probe sentences; probe trained/evaluated with fixed recipe (logistic regression on residual activations, 5-fold CV — recipe hash in payload); judge/rubric/prompt versions recorded verbatim from Lodestar.
**Failure modes:** judge nondeterminism (Lodestar self-consistency covers; certificate stores the consistency stat); class imbalance in probe data (recipe fixes stratification).
**Extension points:** additional validation axes are additive payload fields.

### SS7 `interplab.interventions` — G3, TRUNK, shared library
**Responsibilities:** the single implementation of interventions.
**Interface:**
```python
@dataclass(frozen=True)
class InterventionSpec:
    kind: Literal["noop", "clamp", "ablate", "add_direction"]
    feature_index: int | None
    value_in_max_units: float | None       # resolved against corpus_max
    corpus_max: float | None               # caller supplies from SS5; provenance kept
    positions: Literal["all", "generated_only"]   # default "all" (reference methodology)
    checkpoint_hash: str
    direction_seed: int | None = None      # ED-3: set iff kind == "add_direction"

def attach(model, sae, spec: InterventionSpec,
           *, prompt_lengths: int | Sequence[int] | None = None) -> ContextManager: ...
# ED-4: prompt_lengths is REQUIRED iff spec.positions == "generated_only" and MUST be
# None when positions == "all"; both violations raise at attach time, never
# mid-generation. An int broadcasts across the batch; a sequence gives per-row
# boundaries in that row's tensor coordinates (callers using padded batches account
# for padding themselves). attach MUST NOT infer the boundary.

def control_arms(spec: InterventionSpec, *,
                 matched_feature_index: int,
                 matched_feature_corpus_max: float,
                 direction_seed: int) -> list[InterventionSpec]: ...
# ED-3: pure spec construction from pre-resolved values — no FeatureIndex access in
# this package (§1 edges: interventions → core only). Selection of the matched
# feature happens caller-side via FeatureIndex.sample_matched_frequency (SS5);
# jobs.steer records the chosen index and sampling seed in A9. Returns exactly two
# specs: the add_direction arm (value_in_max_units and corpus_max copied from the
# steered spec so the resolved α matches) and the matched-feature clamp arm (same
# value_in_max_units, its own corpus_max). The prompt-baseline arm is NOT an
# InterventionSpec — it is an A9-level arm ("prompt_baseline", no hook) assembled
# by jobs.steer.
```
**Fixed semantics (MUST, verbatim):**
1. Delta form: `x' = x + cast(decode(clamp(encode(x))) − decode(encode(x)))`, with encode/decode/subtraction in fp32; exactly one cast, applied to the *delta*, at addition.
2. `kind="noop"` **does not touch the stream at all** (no encode, no cast): bit-identity is structural, not numerical.
3. `positions="all"` includes prompt and chat special tokens. `positions="generated_only"` (ED-4): the delta is added only at positions ≥ the row's `prompt_lengths` boundary, with absolute position tracked correctly across KV-cached decoding steps; masked positions are never touched (no encode/decode round trip applied to them), so a fully-masked forward pass is bit-identical **by construction** — and this is a tested clause of `test_identity`.
4. KV-cache: steered positions' effects persist in the cache; this is intended and documented; no cache surgery.
5. `ablate` ≡ clamp to 0. `add_direction` (for control arms) adds `α·d̂` with ‖d̂‖ = 1, α in the same resolved-unit scale as the matched steered arm; `d̂ = normalize(np.random.default_rng(spec.direction_seed).standard_normal(d_in))`, computed once at attach, with `d_in` taken from the SAE config — the golden fixture pins its bytes (ED-3).
6. `control_arms` constructs the two hooked control arms from pre-resolved inputs (ED-3, signature above); the ×/÷3 frequency band and the sampling live in SS5's `sample_matched_frequency`; the prompt-baseline arm is assembled at the job level with no hook. **ED-22 (decided during the WP8 audit):** the prompt-baseline arm is the *prompting* baseline (architecture doc SS7: steering-vs-prompting) — its prompts are scientific content under ED-8: researcher-authored, supplied via the steer config as `prompt_baseline_prompts: [str]`, index-aligned one-to-one with `prompts` (so `prompt_id` pairing holds), REQUIRED in claim mode, optional in explore mode, generated with no hook. They are NEVER derived mechanically from `prompts`, and re-running the unmodified `prompts` without a hook is the `baseline` arm, not this one. Synthetic prompt-baseline text in test fixtures is test data (zorbium precedent), never laboratory content.
**Invariants:** attach/detach leaves zero hooks behind (context manager, tested); spec serialization round-trips.
**Failure modes:** dtype drift on new model revisions (golden fixture catches); device mismatch (resolve at attach, never per-token).
**Extension points:** new `kind` values are additive; existing kinds' numerics are frozen forever (change = new kind).

### SS8 `interplab.evaluation`
**Responsibilities:** blinding (shuffle + strip condition metadata before judging; keep the map artifact-side), Lodestar ingestion adapters (A9 → Lodestar run; results back into A9.lodestar), capability-degradation module (perplexity delta on a fixed pinned text slice under each arm), `eval_compat_map` I/O.
**Invariants:** the blinding map never enters any file Lodestar reads; capability slice is pinned by content hash.
**Failure modes:** judge API changes (adapter isolates; Lodestar owns retries/caching).
**Extension points:** additional judges via Lodestar's own Judge protocol — not here.

### SS9 `interplab.stats` (TRUNK) + `interplab.reports`
**stats interface (fixed):**
```python
def bootstrap_ci(values, groups, n_boot=10_000, level=0.95, seed=0) -> CI
    # resampling unit = groups (prompt IDs). Percentile bootstrap.
def bh_fdr(pvalues, q=0.05) -> mask                  # Benjamini–Hochberg
def seed_variance(per_seed_estimates) -> SeedVar     # n_seeds surfaced always
def effect_size(a, b, groups) -> CohensD
```
**reports responsibilities:** `assemble_chain(claim_spec) -> ChainResolution` (TRUNK): for each required link, query registry for an artifact of the required type whose `subject` hash matches, verify self-hash, check `schema_version ≥ min`, check verdict ≠ red, check eval-compat class; return per-link status. Renderer (leaf): md + self-contained HTML; stamp in header and on every figure.
**Chain resolution algorithm (ED-14/ED-15/ED-16, normative — the assembler implements exactly this, no inference):**
1. *Anchor first (ED-14).* Every `anchor.content_hashes` entry is `get()`-resolved and self-hash-verified; each anchor is one chain row (`link` = the anchor's `artifact_type`). An anchor absent from the registry is chain state (`missing`), not an error; a hash-mismatched or schema-invalid artifact is corruption (exit 3). `intervention_result` anchors are additionally claim-grade-checked (A9's claim-mode invariant: all three control arms present, `blinding.shuffled = true`, and a `feature_certificate` ref in `subject`); failure ⇒ `insufficient_evidence`, `note` names what is missing. Multiple anchors MUST resolve every non-anchor link identically; divergence ⇒ exit 3.
2. *Links in order (ED-15).* `required_links` order is semantically significant: it is the resolution order and the chain-table row order; anchors count as resolved from the start. `via: "subject_ref"` — the link's artifact is reached by following a `subject` entry with role == `subject_role` carried by an already-resolved artifact (scan resolved artifacts in resolution order, `subject[]` order within each; first match; `get()` by that pinned hash). Exactly one payload-carried ref exists in the ontology and is treated as a subject-equivalent parent ref: A5 `store_hash` (role `store_manifest`); adding another requires a blueprint amendment. `via: "subject_of"` — the link's artifact carries an already-resolved artifact in *its* `subject` under role == `subject_role`; prerequisite = the resolved artifact whose `artifact_type` == `subject_role`; resolved via `find(artifact_type, subject_hash=prerequisite)`, filtered to candidates whose matching subject entry carries that role; several candidates ⇒ newest `created_at` wins and the ambiguity goes in `note` (the pre-existing failure-mode rule). A link whose connection cannot be made at its turn (no resolved artifact provides the role / prerequisite unresolved) ⇒ `missing`, `note` explains.
3. *Role vocabulary (ED-15).* `subject_role` values are exactly the artifact-valued role strings §4 establishes — `corpus_manifest`, `store_manifest`, `sae_checkpoint`, `characterization_manifest`, `concept_battery`, `census_report`, `feature_certificate` — which by repo convention equal the referenced artifact's type. Directory-valued roles (`weights`, `model`) never appear in claim chains. SS9 invents no roles.
4. *Type-conditional checks (established pattern).* verdict ≠ red applies to verdict-bearing payloads; `require_instruments ⊆ verdict_basis` applies where declared (ED-16; failure ⇒ `insufficient_evidence`, `note` lists the missing instruments); eval-compat applies to judge-bearing payloads (A7 `judge`, A8 specificity judge fields, A9 `lodestar`) — every judge tuple in the resolved chain must fall in one compatible class under the A12 map whose `payload.version` == `claim_spec.eval_compat_version`, read directly from the registry (`reports` does NOT import `evaluation` — §1; the map is registry JSON). A map version absent from the registry ⇒ exit 3 (the spec references a nonexistent policy artifact).
**Statistics composition (ED-17):** the report job computes, per metric present in the anchors' payloads (Lodestar score, `capability_delta` metrics), per (arm, scale): `bootstrap_ci` over per-prompt scores (groups = `prompt_id`), `effect_size` vs the baseline arm, and `seed_variance` across anchor replicates (`n_seeds` = anchor count, honestly surfaced at 1); `method` names the primitive. Inputs come only from A9 payload fields (`lodestar.per_prompt_scores`) — assembly and statistics never require live Lodestar access; no scores ⇒ `statistics: null`.
**Invariants:** assembly is read-only and pure (same registry state ⇒ same resolution); `CERTIFIED` iff all links `ok` — no override.
**Failure modes:** ambiguous links (two green certificates for one subject): resolution picks the newest `created_at` and *records the ambiguity in the chain*; report notes it.
**Extension points:** new stats functions additive; chain link types driven by claim_spec, not code changes.

### SS10 `interplab.registry`
**Interface:**
```python
def put(artifact: dict) -> Hash          # validates schema + self-hash, writes file
def get(h: Hash) -> dict
def find(artifact_type: str, subject_hash: Hash | None = None, **payload_filters) -> list[dict]
def new_run_card(stage, config_path) -> RunCardHandle   # .finalize(status, outputs, exit_code)
```
**Invariants:** `put` is the only writer; files are immutable once written (attempt to overwrite an existing hash with different bytes = hard error); SQLite cache rebuild (`rebuild_index()`) is idempotent.
**RunCard lifecycle (ED-6):** the handle holds a *draft outside the registry* (scratch file for crash forensics — implementer's choice); only `finalize()` performs the single `put` of the completed, immutable card. Ground Rule 4's "even on failure" means finalize-in-`finally` with `status: failed`; a job killed too hard to reach `finally` leaves no card, and an absent card honestly means the run never completed as a recorded fact (SLURM logs remain).
**Failure modes:** partial writes (write temp + atomic rename); clock skew across machines (ordering by `created_at` is advisory only, never a correctness dependency).

### SS11 `tests/` — see §8.
### SS12 `slurm/` + `interplab.jobs` — see §6.
### SS13 — deferred; no implementation in this blueprint (frozen decision). The only present-day obligation: nothing in §1–§8 may assume Qwen-only (model name is config everywhere).

---

## 6. Batch Jobs and Orchestration

### 6.1 Job inventory (module: `interplab.jobs.<name>`)

| Job | Stage | Reads | Writes |
|---|---|---|---|
| `census` | SS1 | corpus recipe, battery | A1, A2, A3 |
| `store_qa` | SS2 | store dir, A1 | A4 |
| `train` | SS3 | config, A4 | A5 (+ checkpoint dir) |
| `certify` | SS4 | A5, A4|null, eval-slice config (ED-5) | A6 (+ report card) |
| `characterize` | SS5 | A5, A6(soft), A1 | A7 (+ index dir, dashboards) |
| `validate` | SS6 | A7, A2, A3 | A8 |
| `steer` | SS7/8 | A7, A8(claim-mode), config | A9 (+ generations dir) |
| `judge` | SS8 | A9 | A9' (lodestar + capability fields), via Lodestar |
| `report` | SS9 | claim_spec, registry | A11 |
| `sync_registry` | SS10 | cluster outbox | registry/ files |

Every job: (1) validates its config against `schemas/configs/<job>_v1.schema.json` **before** any heavy work (the job-338944 rule); (2) opens a RunCard; (3) finalizes it in a `finally:` block.

### 6.2 Exit codes (contract)

`0` success · `2` **gate_failed** — job ran correctly, verdict red (artifact still written) · `3` **contract_violation** — missing/invalid/hash-mismatched input artifact · `4` environment failure (OOM, node death, HF outage). Orchestration and CI branch on these; jobs MUST NOT conflate 2 with 3.

### 6.3 SLURM launchers

Four parameterized launchers replace the one-off scripts: `launch_train.sh`, `launch_characterize.sh`, `launch_validate.sh`, `launch_steer.sh` — each takes `<config> <run_id>` and follows the existing repo convention: print the `sbatch` line, the log-tail command, and the final-result command together. Multi-config sweeps use the existing pattern (one job, N nodes, `srun --exclusive` per node). **ED-7 correction:** since ED-5 made certification run fresh model forwards, `certify` requires a GPU allocation on production checkpoints — it runs under a minimal single-node sbatch wrapper following the same submission convention (tiny-fixture certification in CI remains CPU-local). `census`, `store_qa`, `judge`, `report`, `sync_registry` run without SLURM allocation (login node or local) — they are I/O- or API-bound.

---

## 7. End-to-End Flows (normative sequences)

### 7.1 Certificate generation flow
1. Job computes metrics on the machine holding the heavy artifact (D1).
2. Job writes certificate JSON → cluster outbox (or directly to `registry/` when local).
3. `sync_registry` pulls, verifies self-hash, lands file in `registry/`.
4. Researcher commits registry files manually (repo convention — tooling never runs git).
5. Certificate now resolvable by `assemble_chain`.

### 7.2 Report generation flow
1. Researcher writes a claim spec (YAML: question, anchor hashes, required links with roles/`via`/min schema versions and optional required instruments, eval-compat version). Claim specs are scientific content (ED-8 policy extends): researcher-authored; synthetic claim specs in tests are test data, never laboratory claims.
2. `report` job: `assemble_chain` → stats over the referenced A9 payloads → render → stamp → A11 into registry.
3. A `DRAFT` stamp is not an error (exit 0); it is the honest state of the chain.

### 7.3 A worked chain (the cheese dose-response claim)
`corpus_manifest(fineweb)` → `store_manifest[green]` → `sae_checkpoint(l28_32x)` → `sae_certificate[green]` → `characterization_manifest(10M tok)` → `feature_certificate(cheese-9056)[green]` → `intervention_result(3 arms, blinded, units=×max)` → `claim_report[CERTIFIED]`. Any missing/red/stale/incompatible link ⇒ same report, `DRAFT` stamp, failing link named in the chain table.

---

## 8. Testing and CI (SS11)

### 8.1 Fixtures (built once, full-strength)
`tests/fixtures/tiny_model/` — 2-layer, d_model=64 transformer with pinned random weights (HF format); `tiny_sae/` — TopK k=8, 256 features, pinned weights; `pinned_text.jsonl` — 200 fixed documents; a pinned cheese-slice + canary reference file for the nightly canary (**ED-23**: both are scientific content, researcher-frozen after the first real cluster certification+validation run — the slice is small committed text, the reference is `tests/fixtures/canary/cheese_reference.json` `{checkpoint_hash, feature_certificate_hash, feature_index, pinned_slice (provenance pointer — the battery content + index the certificate records, pinned by hash, are what recomputation actually consumes), expected_metrics: {dotted.path: value}, tolerances: {dotted.path: …}}` (field names per the implemented contract, WP9 erratum — the earlier sketch's names were non-normative). WP9 ships the *mechanism* — reference-file contract, comparator, nightly marker — with an explicit skip-with-reason while the reference is absent: never a vacuous pass, never invented reference data, never committed production checkpoints (D1)).

Fixtures are **generated once and committed** (a few MB of safetensors), with the seeded generation script (`tests/fixtures/generate.py`) kept for provenance only. Tests MUST NOT regenerate fixtures at runtime: cross-platform/cross-version torch RNG determinism is not guaranteed, and the golden-delta test depends on exact bytes. Regenerating a fixture is a breaking change to every golden test and requires trunk-level review (ED-1).

### 8.2 Test inventory

| Test | Blocking | Content |
|---|---|---|
| `test_identity` | **hard** | noop spec ⇒ bit-identical logits and generations on tiny fixture AND (nightly) on Qwen 1 prompt; ALSO `generated_only` with all positions masked ⇒ bit-identical (ED-4) |
| `test_delta_golden` | **hard** | clamp (and add_direction) on tiny fixture reproduces pinned delta tensor within 32 ULP in fp32 (ED-26: cross-platform CPU kernel rounding — measured max 8 ULP on Linux vs the Windows-generated golden, not a defect; golden bytes unchanged) |
| `test_hook_hygiene` | hard | attach/detach leaves zero forward hooks |
| `test_envelope_roundtrip` | hard | self-hash verify on every file under `registry/` (CI runs on the real registry) |
| `test_schema_validate` | hard | every schema in `schemas/` compiles; every registry file validates against its declared version |
| `test_config_schemas` | hard | every file in `configs/` validates (the 94%-timeout guard) |
| `test_battery_snapshot` | hard | tokenization of every battery probe matches pinned snapshot for pinned tokenizer revision |
| `test_stats_reference` | hard | bootstrap/BH against precomputed reference values |
| `test_chain_assembly` | hard | synthetic registry trees: all-green ⇒ CERTIFIED; each failure class ⇒ correct link status |
| `canary_cheese` | nightly/pre-claim | cheese-9056 certificate metrics *recomputed fresh* on the pinned slice, compared to the researcher-frozen reference within its recorded tolerances (ED-23; drift detection is the point — code or environment drift moves the recomputed values). Reference absent ⇒ explicit skip naming ED-23; real checkpoint unreachable ⇒ same |
| `test_import_contracts` | hard | dependency edges of §1 enforced (import-linter or AST walk) |

### 8.3 CI
Every commit: all hard tests (< 5 min budget; fixtures are tiny). Nightly on cluster: identity-on-Qwen, canary — lane entry point is `pytest -m nightly` run on the cluster checkout (scheduling — scrontab or manual — is the researcher's; a thin wrapper script is implementer's choice). Nightly tests skip with an explicit reason when their real-model/real-checkpoint inputs are unreachable (ED-23) — locally they always skip; they MUST NOT be silently absent from collection. No commit gate runs SLURM jobs.

---

## 9. Build Order → Work Packages

Architecture build order unchanged; expressed as delegable packages. **Trunk** = full-strength only.

| # | Work package | Contents | Tier | Preconditions |
|---|---|---|---|---|
| 0 | Contracts bootstrap | `core` (hashing/envelope/uris/configs), all §4 schemas as files, `registry` put/get/find, fixtures §8.1 | **Trunk** | none |
| 1 | SS7 library | interventions + identity/golden/hygiene tests | **Trunk** | 0 |
| 2 | SS4 certify | legacy A5 backfill (ED-5), metrics job + bands file + report card; retro-run on all 6+ checkpoints; **plus pulled-forward minimal SS10 subset**: `new_run_card`/`RunCardHandle.finalize` per the frozen interface (ED-6), and minimal `sync_registry` (§3.3, already fully specified) | Leaf | 0, 1 |
| 3 | SS1 corpus | battery extraction from `find_features.py` constants → `data/concepts/`; manifests; census | Leaf | 0 |
| 4 | SS5 engine | indexer job, FeatureIndex API, dashboards; SS2 QA rides along | Leaf (API review at trunk level) | 0, 2 |
| 5 | SS6 validate | rubric/sensitivity/selectivity/probe + A8 | Leaf | 3, 4, stats |
| 5b | `stats` | the four functions + reference tests | **Trunk** | 0 |
| 6 | SS9 reports | `assemble_chain` (**Trunk**) + renderers (Leaf); pilot = cheese dose-response claim | mixed | 1, 2, 5, 5b |
| 7 | SS10/SS12 | run cards everywhere (core `new_run_card`/`finalize` moved to WP2 per ED-6), 4 launchers, delete one-off slurm scripts, `scripts/legacy/` move | Leaf | 0 |
| 8 | SS8 boundary | blinding, adapters, capability module, compat map; **plus `jobs.steer` (ED-18)** — §6.1's steer row, claim-mode A9 production being inseparable from blinding — and **ED-7's `certify` GPU sbatch wrapper** (small SS12 item) | Leaf | 1, 5b, 6 |
| 9 | Canary + snapshots | §8 completion | Leaf | 5, 6 |
| 10 | Repository hygiene (ED-24) | release readiness only: zero scientific and zero behavioral change, byte-for-byte lab equivalence | Leaf | 0–9 |

ED-24 (WP10 scope, decided at implementation-phase close): WP10 is three passes. **Pass A (mechanical):** unused-import/import-order/formatting fixes on non-frozen surfaces; stale path-reference corrections in comments/docstrings; §2 tracking reconciliation (everything §2 declares git-tracked is tracked — `data/concepts/`, `schemas/`, `registry/`, `reports/`, `uv.lock` — and everything generated is ignored: `slurm/logs/`, `__pycache__/`, `.venv/`, wandb, temp dirs); secrets/token scan (findings reported, redaction decisions researcher's); README rewrite (navigation + dev workflow, drafted from this blueprint, factual claims only); a stray-file deletion LIST (researcher confirms each before deletion); §8.3's per-commit hard-test gate mechanized as a CI workflow file (the one item adding a file — CI-side only, zero lab behavior). **Pass B (justified case-by-case in the completion report):** dead-code candidates (delete only with evidence of zero references), TODO/FIXME triage (classify — ED/researcher-gated notes are load-bearing, not stale), docstring corrections beyond paths (add or fix, never trim ED/invariant references). **Pass C (researcher-gated, blocks the public push, not Passes A/B):** license + copyright (pyproject currently says Proprietary), publish-or-keep-private for `docs/`, curation of `registry/`/`results/`/experiment-log scientific records, redaction policy for cluster account strings and usernames. Pre-laboratory documents (`docs/CLUSTER_GUIDE.md`, `docs/EXECUTION_PLAN.md`, `docs/troubleshooting.md`): archived under `docs/archive/` moved byte-identical — never rewritten (falsifies the record + duplicates the blueprint/README as workflow truth), never deleted (provenance); status carried by a new `docs/archive/README.md` index, one factual superseded-by line each; `results/FEATURE_EXPERIMENT_LOG.md` does NOT move (A10 `log_section` cross-references it). **Untouchables (violating any is an audit failure):** `scripts/legacy/` (frozen, byte-identical, ruff violations included); `tests/fixtures/` and `tests/golden/` bytes; `registry/` artifact files (content-addressed); `schemas/` files (published contracts — not even formatting); SS7/stats function bodies; frozen `__init__` re-export surfaces; the §1-mandated duplications (three model loaders, `jobs.validate._load_concept`, `jobs.steer`'s inline blinding) — that duplication is architecturally required, not a cleanup target; §2 directory layout; all renames; test assertions; `uv.lock`. **Equivalence gate:** full default suite green at 502(+CI-file tests if any)/3 deselected, nightly lane 3 explicit skips, ruff clean on non-legacy surfaces, `uv lock --check` unchanged, and `git diff` empty for every untouchable path.

ED-18 (build-order completion, decided during WP7): the original table assigned `interplab.jobs.train`/`interplab.jobs.steer` to no package. `jobs.steer` belongs to WP8 (above). `interplab.training` + `jobs.train` (SS3) are **researcher-gated**: the P1 validation arm runs on existing checkpoints via ED-5 backfill, so new-SAE training is not on the build critical path; it becomes its own small work package when the researcher next needs to train, and `slurm/launch_train.sh` stays dormant until then.

**Delegation contract for coding agents:** an agent implementing a work package may decide internal module layout, algorithms, and performance tactics; it may NOT alter any schema file, any fixed interface signature (§5), exit codes, URI schemes, hashing, the registry tree, or SS7 numerics — those changes require a human-approved blueprint revision. Required reading per package: this document §0–§4, its own §5 entry, §6, §8.

---

## 10. Open Items Deliberately Left to Calibration (not ambiguity)

1. SS4/SS6 band values: placeholders until the first retro-certification batch; recorded as `bands_v1.json` then bumped (D3).
2. Characterization sample size (5M vs 10M tokens): start 5M; revisit after first index build cost is known.
3. SQLite cache schema for the registry: derived, unversioned, implementer's choice.

Everything else in this blueprint is fixed. Changes go through a blueprint revision, not through code.
