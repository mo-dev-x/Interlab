# Repository reconciliation — measured state of the three repositories

*Author: Mohamed El Yazid — IID*
*All counts measured on disk 2026-08-25. Method stated per row; anyone can re-run them.*

---

## 1. Why this document exists

The reports in this corpus quote repository sizes — test counts, subsystem counts, artifact-schema
counts — at the moment each was written. Those numbers are now spread across six documents and three
snapshots and they disagree with each other and, in two cases, with the disk. A poster or a talk
built from this corpus will quote at least one of them.

This document measures all three repositories once, states the method, and marks every disagreement.
It does not amend any source document: the sources are the historical record and their numbers were
true when written. **Where this document and a source disagree, this document is the current fact and
the source is the record of a past state.**

---

## 2. Interlab — `qwen-sae-interp`

The scientific repository. Sole source of truth for feature definitions, discovery, evidence, and
canonical runtime behaviour.

| Quantity | Measured 2026-08-25 | Method |
|---|---:|---|
| test modules in `tests/` | **102** | `find tests -name 'test_*.py' -type f` |
| Python modules in `interplab/` | **69** | `find interplab -name '*.py'` |
| subsystems (`interplab/*/`) | **12** | directory count, excluding `__pycache__` |
| artifact-schema families (`schemas/*/`) | **15** | directory count |
| scripts (`scripts/*.py`) | **15** | glob |
| design/planning docs (`docs/*.md`) | **17** | glob |
| report documents tracked under `reports/` | **20** | `git ls-files` |

**The 12 subsystems**, named: `certification`, `characterization`, `core`, `corpus`, `evaluation`,
`interventions`, `jobs`, `registry`, `reports`, `stats`, `store_qa`, `validation`.

This **matches** the SS1–SS12 roster the sources have used throughout — there is no drift here, and
any count of 13 is an artifact of including `__pycache__`. `SS13` (Circuit-Tracing Support) appears
in `docs/infrastructure_architecture.md` and the implementation blueprint as an **explicitly
deferred, frozen decision**; its absence from disk is the design working, not a gap.

**The 15 schema families**, named: `census_report`, `characterization_manifest`, `claim_report`,
`concept_battery`, `configs`, `corpus_manifest`, `environment_acquisition_manifest`,
`environment_install_manifest`, `eval_compat_map`, `feature_certificate`, `intervention_result`,
`run_card`, `sae_certificate`, `sae_checkpoint`, `store_manifest`.

### 2.1 Two discrepancies against the sources

**Test count.** The most recent source states **108** test modules. Disk says **102**. The gap is not
a deletion of tests; it is that "test modules" and "test files matched repo-wide" are different
questions and the sources are not consistent about which they answer. The corpus also carries
**583** (July snapshot), **1,040** (08-09) and **2,796** (08-21) — but those are *test cases
collected*, not modules, and mixing the two series is the actual source of confusion. Both series
should be labelled explicitly wherever quoted.

> **Use for a poster:** "102 test modules; 2,796 collected test cases (2026-08-21)." Never quote a
> bare number from the two series without its unit.

**Artifact-schema count.** The corpus carries **11 → 14 → 15** across three snapshots and, in one
place, "11 vs 15 artifact types" as an open disagreement. Disk says **15** schema families today. The
11 and 14 are earlier states, not errors.

### 2.2 A correction to a claim I made about this repository

I stated during the consolidation session that `reports/` is gitignored and that the consolidated
report would therefore stay uncommitted regardless. **That is wrong.** `.gitignore` excludes only
*binary* artifacts under `reports/` — `**/*.png`, `*.jpg`, `*.jpeg`, `*.pdf`, `*.pptx`, `*.csv`.
Markdown under `reports/` is tracked normally; 20 report documents are in the index right now.

This matters practically: `CONSOLIDATED_REPORT.md`, `shipped_tool_sae_concept_lab.md` and this file
are all committable, and the standing instruction that the final pairing report stays uncommitted is
a *choice*, not a mechanical consequence of the ignore rules.

### 2.3 The unreferenced governing document

`docs/research_program.md` — 278 lines, the "Grounded Interpretability" research program — is
**referenced by no document in `reports/`**. Verified: `grep -rl research_program reports/` returns
nothing.

This is the largest structural gap in the corpus, because that file is the frame everything else sits
inside. It contains:

- **Part I — Grounded Interpretability**, eight phases: a structural analysis of the field (what is
  solved, dead ends, overhyped work, which operating assumptions are likely wrong, the deepest
  bottlenecks), a first-principles reconstruction, the five-thread program P1–P5, original research
  opportunities, the fundamental questions, comparative advantage, a **brutal self-critique of the
  roadmap with repairs**, and a final architecture.
- **Part II — Principles of Learned Computation**, an alternative five-year program T1–T5 (capacity
  laws for superposed computation, the correspondence problem, the binding taxonomy, developmental
  laws, a variational principle), and an explicit head-to-head: *which program wins the decade?*

**The relevant linkage, which no report currently states:** the P1 thread —
*Identifiability Phase Diagrams via Controlled-Ontology Testbeds, months 0–12* — is the thread this
entire body of work belongs to. Every SAE result in this corpus is P1 evidence. The four-stage
analyst-choice displacement result is, in the program's own vocabulary, an **identifiability**
finding: it shows that under the standard workflow the reported answer is not identified by the data
alone. That connection should be drawn explicitly in any presentation, because without it the work
reads as a set of negative results rather than as the first deliverable of a stated program.

---

## 3. SAE Concept Lab — `sae-concept-lab`

The product repository. Full treatment in `reports/shipped_tool_sae_concept_lab.md`; counts here for
comparability.

| Quantity | Measured 2026-08-25 | Method |
|---|---:|---|
| Python modules in `sae_concept_lab/` | **38** | `find … -name '*.py'`, excluding `__pycache__` |
| test modules in `tests/` | **22** | glob |
| commits on `fix-gemma-sae-release` | **26** | `git rev-list --count HEAD` |
| shipped concept entries | **2** | one Gemma, one Qwen, same concept |
| root governance docs | **3** | `BOUNDARY.md`, `README.md`, `RUNNING.md` |

Branch state: `fix-gemma-sae-release` at **`84f1320`**; `main` at **`e3b6fc0`**. `main` predates the
chat-template fix, so **the merged mainline is currently the defective build.** Merging is
outstanding and is the single highest-value unblocked action in that repository.

**Coverage in the corpus before 2026-08-25: one subsection of one document, and zero figures.** That
is what `shipped_tool_sae_concept_lab.md` was written to close.

---

## 4. Lodestar — `d:\lodstar`

The evaluation and governance repository. Not a Git repository at this location.

| Quantity | Measured 2026-08-25 | Method |
|---|---:|---|
| test modules in `tests/` | **14** | `find tests -name 'test_*.py'` |
| Python modules in `lodestar/` | **28** | excluding `__pycache__` |
| authored Markdown, total | **118** | excluding `.venv`, archives, pytest scratch |
| — at repository root | 17 | of which **11** are `R9_V*` / `R11_V*` audit documents |
| — in `docs/` | 7 | |
| — in `docs/WORKBOOK/` | 45 | +4 in `WORKBOOK/CAPSTONES/` |
| — in `docs/LEARNING/` | 45 | |

### 4.1 The 469-test-file trap

A naive `find . -name 'test_*.py'` in this directory returns **469**. That number is wrong for any
purpose and must never be quoted. It counts five embedded copies of *another* repository's tree —
`.certify_cfe52c6`, `.certify_ad4a5be`, `.archive_preflight_cfe52c6`, `.archive_preflight_ad4a5be`,
and `qwen-post-gpu-fix` — at roughly 91 test files each. Those are certification archives and working
copies, not Lodestar code.

**Lodestar's own live test surface is 14 modules.**

The same directory also holds a dozen `pytest-*` scratch directories and four
`r9_tooling_bootstrap_20260803*` trees. Any measurement of this repository has to exclude them
explicitly or it measures the archive.

### 4.2 What is here that is nowhere in the corpus

Two bodies of work, both deliberately kept out of `reports/` and both invisible to a reader of the
consolidated report:

- **The R9/R11 audit series** — 11 documents at root covering the ED-36 builder re-acceptance and
  final acceptance, hardening deltas, TL separation, packaging and torch, tooling and pip, the
  combined integration audit, the integration-candidate audit, the C00 hash-bound audit and the prose
  correction audit. This is the governance evidence trail behind every "CERTIFIED" claim.
- **A 94-file teaching corpus** under `docs/WORKBOOK/`, `docs/WORKBOOK/CAPSTONES/` and
  `docs/LEARNING/`. Nothing in the report corpus mentions it exists.

Neither is a defect — the separation is by standing instruction. But a presenter who says "the
governance work is documented" should know the documentation is 118 files in a different repository,
and a presenter who shows the Lodestar UI screenshots should know they are the *only* Lodestar
artifact in the report corpus.

---

## 5. The three repositories in one table

| | `qwen-sae-interp` | `sae-concept-lab` | `d:\lodstar` |
|---|---|---|---|
| role | science: definitions, discovery, evidence | product: the operable tool | evaluation + governance |
| authority | **sole source of truth** | derivative; never authoritative | independent judging + audit |
| Python modules | 69 (`interplab/`) | 38 | 28 (`lodestar/`) |
| test modules | 102 | 22 | 14 |
| Git | yes, branch `main` | yes, `fix-gemma-sae-release` @ `84f1320` | not a repository here |
| presence in the report corpus | ~all of it | 1 subsection, 0 figures → now 1 document | 7 UI screenshots, 0 prose |

---

## 6. What a presenter should take from this

1. **Quote 102 test modules and 2,796 collected cases, each with its unit.** The bare numbers in the
   sources belong to two different series.
2. **`sae-concept-lab` is a deliverable and should be shown as one.** It is the only thing in this
   body of work a viewer can be handed and told to use.
3. **Lodestar's live surface is 14 test modules.** The 469 is archive duplication.
4. **Name the research program.** This work is thread P1 of a stated five-year architecture, and the
   headline result is an *identifiability* finding in that program's own vocabulary. Without that
   frame the corpus reads as a collection of negative results; with it, the negative results are the
   point.
