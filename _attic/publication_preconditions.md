# Publication preconditions

Checklist of what must be independently re-verified immediately before this
repo is made public. Raised in `docs/repo_cleanup_plan.md`; recorded here so
it survives that plan's own deletion (its Phase 5a deletes itself as the
last commit of Phase 2).

## 1. Entropy-based secret scan — NOT YET DONE

- **What ran (2026-08-14):** pattern-only (`git log --all -G'<pattern>'` for
  `hf_[A-Za-z0-9]{20,}`, `sk-ant-`, private-key headers, `api_key\s*=`),
  covering all 337 commits across every ref. Found no credential.
- **What that scan does NOT cover:** entropy-based detection (a
  random-looking secret with no recognizable prefix). No gitleaks/trufflehog
  run has ever happened on this repo. **The 2026-08-14 clean verdict is not
  a substitute for this — do not treat it as sufficient.**
- **Run before publication:** `gitleaks detect --source . --log-opts="--all" --no-banner --report-path <gitignored path>`
  or `trufflehog git file://. --json`.
- **Pass means:** zero unresolved findings, with every reported hit
  individually opened and read (not graded by filename) before being called
  clean.

## 2. Public-subset include list — BLOCKED, not authorable yet

**Scope decision — SETTLED by the researcher, 2026-08-14** (not a
recommendation; this is what will happen):

- **The repo will be made public in the future.** The flip is planned, not
  hypothetical. Both `mo-dev-x/qwen-sae-interp` and `mo-dev-x/sae-concept-lab`
  exist and are private today (verified 2026-08-14: unauthenticated GitHub
  API returns 404 for both).
- **Internal governance and experiment evidence are NOT published.**
  `project_management/`, `reports/`, `results/final_pairing/`, and the
  dispatch packets stay private.
- **Publication is by building a public SUBSET, not by stripping this
  repo.** `qwen-sae-interp` stays complete and private; the public artifact
  is a separate, derivative build made by inclusion. Two reasons, both
  non-obvious, both recorded here so neither gets re-litigated:
  - `.gitignore` does not un-publish anything already committed. Every
    governance file is already in this repo's history, and flipping a
    GitHub repo to public publishes the *entire* history in one action —
    there is no partial reveal. Un-tracking them now would not help, and
    would only cost the versioning.
  - `protocols/final_pairing/v1/` must ship despite reading as governance.
    It is loaded at runtime by 8 scripts (verified: every file under
    `scripts/final_pairing/` that references `protocols/final_pairing/v1`)
    and 3 test files (`test_final_pairing_evidence_document.py`,
    `test_final_pairing_one_allocation_generation.py`,
    `test_final_pairing_concept_discovery.py`); omitting it breaks the
    public repo on clone.
- **Governance stays tracked in the private repo.** Do not "fix" this later
  by un-tracking it — `project_management/VERIFICATION_LOG.md` binds 84
  sha256 digests and is the audit ground truth. It needs versioning, not
  removal.

- **Blocker (unchanged):** the include list itself still is not authorable —
  the tool's file set is not final until generation lands.
- **Run before publication:** once generation lands, enumerate the actual
  public include list against the policy above (public tool code +
  `protocols/final_pairing/v1/`; nothing from `project_management/`,
  `reports/`, `results/final_pairing/`, or the dispatch packets) and build
  the public artifact as a separate derivative, never by stripping this
  repo in place.
- **Pass means:** a concrete, reviewed include list exists, matches the
  policy above, and the public artifact is built as its own derivative —
  this repo remains complete and private throughout.

## 3. `reports/internship_report.html` / `.pdf` — must never be tracked

- **Reason:** the HTML export's own `<link>` tag embeds
  `file:///c:\Users\<username>\...` from the machine that rendered it.
- **Already verified (2026-08-14):** `git log --all --oneline -- reports/internship_report.html reports/internship_report.pdf`
  returns nothing for either path, on any ref — neither file has ever been
  committed. Exclusion via `.gitignore` is therefore sufficient; **no
  history remediation is needed.** Record this, or it will get re-derived
  under time pressure.
- **Run before publication:** re-run the same `git log --all` check, and
  confirm both paths are still listed in `.gitignore`.
- **Pass means:** both checks come back the same way — empty history, still
  ignored.

## 4. `C14 political_framing` — PI-gated, must not ship in any public configuration

- **Status:** `pi_gated: true` (`prompts/final_pairing/v1/README.md`,
  `docs/final_pairing_concept_discovery_packet.md`). Permitted for internal
  scientific results; prohibited from any public configuration without
  explicit PI sign-off on the definition, both poles, and the public label.
- **Run before publication:** grep any public-facing config/export for
  `political_framing`.
- **Pass means:** absent from every public configuration unless a recorded
  PI sign-off exists — never present by default or by the mere absence of a
  gating flag.
