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

- **Status:** open precondition. No list exists yet.
- **Blocker:** the tool's file set is not final until generation lands.
- **Run before publication:** once generation lands, enumerate the actual
  public include list and reconcile it against whatever governance-material
  decision was made (see `docs/repo_cleanup_plan.md` Phase 4/5b while that
  plan still exists).
- **Pass means:** a concrete, reviewed include list exists and matches the
  shipped tree — not assumed, not inferred from a plan document.

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
