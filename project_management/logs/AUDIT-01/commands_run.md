# AUDIT-01 Commands Run

Commands are shown in logical form. PowerShell wrappers supplied paths,
captured exit codes, and saved stdout/stderr in this directory.

1. Repository/instruction inventory:
   - `Get-ChildItem ...`
   - `rg --files -g AGENTS.md`
   - `git ls-files`
   - `git status --short`
   - recursive file counts and sizes
2. Obligation and contradiction searches:
   - `rg -n` over WP/ED references, headings, path references, stale-state
     phrases, Qwen hard-coding, and command surfaces
3. Suspicious implementation search:
   - `rg -n -i` for `TODO`, `FIXME`, `NotImplementedError`,
     `placeholder`, `stub`, `dummy`, bare `pass`, skip, and xfail patterns
4. Documented clean install:
   - `uv sync --extra dev`
   - first sandbox attempt: exit 2, uv cache access denied
   - isolated outside-sandbox retry: exit 0
5. Tests in the clean isolated environment:
   - `uv run pytest`
   - `uv run pytest -m nightly`
6. CI/dependency checks:
   - `uv run ruff check interplab tests scripts/*.py data/concepts/*.py`
   - `uv lock --check`
   - `git diff --check`
7. Registry audit:
   - `interplab.core.envelope.load` over `registry/*/*.json`
   - filename/self-hash/type counts
   - local registry reference resolution
   - artifact-to-RunCard run-ID reconciliation
8. Public workflow:
   - `python scripts/*.py --help` for all 11 top-level scripts
   - isolated `python scripts/sync_registry.py --config configs/sync_registry.yaml`
9. Invalid-config contract probe:
   - `python scripts/sync_registry.py --config project_management/logs/AUDIT-01/invalid_sync_registry.yaml`
10. Final integrity:
    - `git status --short`
    - production registry type counts
    - temporary-environment cleanup and absence check
