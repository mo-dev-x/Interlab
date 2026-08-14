# Repository cleanup and public-release plan

**Status:** plan only — nothing executed. For Engineer 4.
**Remote:** `https://github.com/mo-dev-x/qwen-sae-interp.git`
**Branch:** `final-pairing-harness` (no upstream configured)

---

## 0. The "+15k unpushed files" figure is not real

Measured, not estimated:

| Quantity | Count |
|---|---|
| Files on disk (excl. `.git`) | **58,903** |
| …of which inside `.venv` | **55,413** |
| **Tracked files** | **524** |
| Untracked files | 619 |
| Ignored files matching a rule | 88 |
| `.git` size | 29 MB |
| Tracked working tree | 23 MB |

**94 % of the file count is `.venv`**, which is already in `.gitignore` and was never going to be pushed. The IDE source-control view counts it; git does not. There is no 15k problem.

The tracked repository is small and healthy. The real work is not bulk deletion — it is **three unrelated jobs** that got conflated:

1. **Scratch removal** — 619 untracked files in 4 disposable directories.
2. **Publishing 51 commits** — the branch has never been pushed and has no upstream.
3. **Public-release readiness** — the actual question, since the repo is meant to be used by others.

---

## Phase 1 — Scratch removal (5 minutes, zero risk)

All 619 untracked files sit in four directories, none of which is referenced by any tracked file:

| Directory | Files |
|---|---|
| `.audit_extract_0533/` | 578 |
| `.tmp_codex_preflight38_manual/` | 20 |
| `.tmp_codex_preflight38_detail/` | 20 |
| `.tmp_codex_preflight38/` | 1 |

**Before deleting:** confirm nothing tracked references them (`grep -rl 'audit_extract\|tmp_codex_preflight' -- $(git ls-files)`). If a governance record cites one as evidence, move it into the sealed evidence tree instead of deleting.

**Then:** delete, and add to `.gitignore` so they do not return:

```gitignore
# Scratch from audit and preflight runs
.audit_extract_*/
.tmp_codex_preflight*/
.tmp_uv_cache/
```

`.tmp_uv_cache/` is included because it currently matches no rule and will reappear.

---

## Phase 2 — Publish the branch (blocked on Phase 3 decisions)

51 commits ahead of `origin/main`, touching 105 files. No upstream is configured, which is why everything reads as unpushed.

**Do not push before Phase 3 is resolved.** The first push of a public-facing repo sets what the world sees, and two of the Phase 3 items are visible in the pushed content.

When cleared: `git push -u origin final-pairing-harness`, then open a PR to `main` rather than pushing to `main` directly.

---

## Phase 3 — Public-release readiness

### P0 — Hardcoded machine paths as executable defaults

`scripts/final_pairing/final_pairing_judge_cli.py:65-66`

```python
DEFAULT_CACHE_PATH  = "D:/devcache/lodestar_cache/final_pairing/cache.sqlite"
DEFAULT_OUTPUT_ROOT = "D:/devcache/lodestar_runs/final_pairing"
```

These are **defaults, not examples**. Anyone who clones this repo and runs the judge CLI without overriding them writes to — or fails on — a path that exists only on one Windows machine. This is a functional break for every external user, which is what makes it P0 rather than cosmetic.

**Fix:** resolve from environment with a repo-relative fallback, e.g. `INTERPLAB_CACHE_DIR` / `INTERPLAB_OUTPUT_ROOT`, defaulting under a gitignored `./.local/` or the platform cache dir. No absolute path may be a default.

### P1 — Machine paths in prose

`D:/devcache/wt/concept-bundle` appears throughout docstrings and comments in
`final_pairing_evidence_document.py`, `final_pairing_one_allocation_generation.py`, and `tests/test_final_pairing_evidence_document.py`, plus one tracked `.md`.

These do not break anything — they reference a maintainer's worktree location and are meaningless to a reader who does not have it. **Replace with the branch/commit identity that actually matters** (`eng3/concept-bundle @ <sha>`), which is the information the prose was trying to convey.

Severity note: keep this distinct from P0. One breaks execution; the other leaks directory layout and confuses readers.

### P1 — The `.gitignore` negation pattern is a known footgun

```gitignore
docs/*
reports/*
project_management/*
!docs/*.md
!reports/*.md
!project_management/*.md
```

The `.gitignore` documents its own history here: this pattern already caused **18 governance artifacts to sit untracked for weeks**, including `VERIFICATION_LOG.md` and every pre-registration. Any *non-markdown* file added to those trees — a JSON schema, a CSV, a diagram — disappears silently with no error.

**Fix:** invert to explicit exclusion of what is actually bulky (`docs/**/*.png`, `reports/**/*.csv`, and so on) rather than excluding whole trees and clawing back one extension. A contributor should have to opt a file *out*, not discover it was never in.

### Clean — no secrets

Scanned all 524 tracked files for `hf_*`, `sk-ant-`, private-key headers and `api_key` assignments. **Every hit is a parameter name or a test fixture** (`"sk-fake"`, `"sk-test"`). I read the matching lines rather than grading from filenames. No credential is committed.

This does not substitute for a scan of *history* — see Phase 4.

---

## Phase 4 — Decision required from the researcher

**Should the public repo carry internal governance material at all?**

The repo currently mixes three things:

| Content | Example | Audience |
|---|---|---|
| Reusable tool | `interplab/`, `scripts/`, `schemas/` | external users |
| Internal governance | `project_management/`, `docs/` rulings, `protocols/` | this lab |
| Experimental evidence | `results/final_pairing/` (30 files) | reviewers |

A tool other people use wants the first. The second contains work-order history, verification logs, completion ledgers and audit records naming internal roles and decisions — legitimate to keep, but written for an internal audience and not obviously intended for publication.

**Recommendation:** keep the tool and its schemas public; move governance to a private repo or a `governance/` branch that is not merged to `main`. **This is your call, not mine** — it is a scope and disclosure decision, and the wrong default is expensive in both directions.

**Also confirm before any push:** whether `mo-dev-x/qwen-sae-interp` is currently public or private. Everything above assumes it will be public; if it is private and staying private, P1 items drop to housekeeping and Phase 4 is moot.

**History scan:** if the repo becomes public, scan the *full history*, not just the working tree — a credential removed in a later commit is still in the objects. `gitleaks detect --log-opts="--all"` or equivalent, once, before publication.

---

## Phase 5 — Transient files that should not ship

Added after Phase 1. A tool repo should not carry the work orders that built it.

**Verified before listing.** `results/final_pairing/job_406092/fp_accept.sbatch.before` and
`.sbatch.diff` look like scratch and are **not**. That job's `README.md` records that the
wrapper diff was independently reproduced (`diff -u fp_accept.sbatch.before fp_accept.sbatch`)
and is byte-identical to the stored `.diff`, proving the disclosed edit was exactly one added
`PYTHONPATH` line. **Deleting them destroys the evidence for that claim. They stay.** Recorded
here so a later sweep does not mistake them for leftovers.

### 5a — Delete or relocate

| Path | Action | Why |
|---|---|---|
| `docs/repo_cleanup_plan.md` | **Delete** as the last commit of Phase 2 | This file. It is the operative document until then, and git history retains it. |
| `recon_checkpoint_provenance.py` | **Move to `scripts/`** | One-off T0.0 evidence-recovery script sitting loose at repo root. No inbound reference from anywhere. It is a real tool in the wrong place — relocating removes the root-level smell without destroying a method. |

**`docs/execution_roadmap.md` — DO NOT DELETE.** My first draft listed it as dead because it
is dated "Final 3 Days (Fri Jul 24 → Sun Jul 26, 2026)" and superseded by the PI directive.
Checking the inbound references showed it is **cited evidence**:

- `reports/internship_report.md:253` cites it as the record that Eurovision was **pre-flagged
  as weak before the result was known** — the roadmap is the proof that decision was
  pre-registered rather than post-hoc.
- `reports/internship_report.md:699-700` cites it for two absent-evidence items.
- `reports/evidence_inventory.md:18, 282, 353` cites it for checkpoint provenance and methodology.

A superseded *plan* is not a deletable *record*. Deleting it would break exactly the kind of
pre-registration chain the rest of this project exists to protect.

### 5b — Conditional on the Phase 4 governance decision

Delete from the public repo if governance stays private; keep if it ships:

`docs/final_pairing_tamia_packet.md` · `docs/final_pairing_concept_discovery_packet.md` (both are Lab-Assistant command packets — dispatches, not documentation) · `docs/pi_directive_plan_2026_08.md` (dated sprint plan opening with an operational `HF_HOME` warning) · `docs/implementation_log.md` (running internal log)

Do not delete these piecemeal. They are the same decision as `project_management/`.

### 5c — Rename

`docs/pipline.md` → `docs/pipeline.md`. It is the authoritative pipeline reference and the
filename is misspelled. Cheap now, and a typo in the most-linked doc of a public tool is the
kind of thing that gets noticed first. Update inbound references in the same commit.

---

## Sequence

```
Phase 1  scratch removal + gitignore        no dependency
Phase 3  P0 path fix                        no dependency, start immediately
Phase 4  researcher decision on governance  BLOCKS Phase 2
Phase 3  P1 prose paths + gitignore rewrite  after Phase 4 (scope depends on it)
Phase 4  history scan                       only if going public
Phase 2  push + PR                          last
```

Nothing here blocks GPU generation, judging, or any frozen protocol. The `protocols/final_pairing/v1/` tree is untouched by this plan.
