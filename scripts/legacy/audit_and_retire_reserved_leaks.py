"""One-shot remediation for the trailing-period false-negative found in
check_reserved_indices.py's `_standalone_index_pattern` (2026-08-08, see
that module's docstring, incident 4): the corrected regex may surface
reserved-index leaks that were committed silently while the buggy pattern
was live, giving false assurance for the whole window it was active.

WHY THIS IS ONE SCRIPT AND NOT TWO STEPS: scanning and retiring must
happen in the SAME process. If this were "run a scan script, read its
output, then run a retire script," the leaked index values would have to
cross a process boundary in plain text -- exactly the leak this exists to
close, and exactly the mistake that put values into the prereg by hand
last time a verification step printed them "just to check." Here, the
scan's return value (a set of ints) is consumed directly by
`retire_and_replace` inside `audit_and_retire`, in memory, and never
serialized anywhere. Only counts are printed.

Scope: the entire tracked tree (`*.md`/`*.py`, whole content, not a diff --
auditing accumulated state is the one case that's correct for) plus every
commit message in history (the commit-msg hook shares the same scanner
and inherited the same defect).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_HERE = Path(__file__).resolve().parent
cri = _load("check_reserved_indices", _HERE / "check_reserved_indices.py")
pool_mod = _load("make_calibration_pool", _HERE / "make_calibration_pool.py")


def audit_and_retire(repo_root: Path, pool_path: Path) -> dict[str, int]:
    """Everything in one process: scan, then retire, then discard the
    actual values. Returns counts only -- see module docstring."""
    reserved_indices = cri.load_reserved_indices(pool_path)

    content_leaks = cri.scan_tracked_tree_content(repo_root, reserved_indices)
    message_leaks = cri.scan_commit_message_history(repo_root, reserved_indices)
    all_leaked = content_leaks | message_leaks  # consumed below; never returned or printed

    if all_leaked:
        _, retired_count = pool_mod.retire_and_replace(pool_path, all_leaked)
    else:
        retired_count = 0

    return {
        "tracked_tree_leak_count": len(content_leaks),
        "commit_message_leak_count": len(message_leaks),
        "total_distinct_leaked": len(all_leaked),
        "retired_slot_count": retired_count,
    }


def main(argv: list[str] | None = None) -> int:
    repo_root = cri.git_repo_root()
    pool_path = repo_root / cri.POOL_RELATIVE_PATH
    if not pool_path.exists():
        print(f"{pool_path} not found -- nothing to audit against.", file=sys.stderr)
        return 1

    result = audit_and_retire(repo_root, pool_path)
    print(f"tracked-tree content leak count: {result['tracked_tree_leak_count']}")
    print(f"commit-message leak count: {result['commit_message_leak_count']}")
    print(f"distinct indices leaked (union): {result['total_distinct_leaked']}")
    print(f"slots retired and replaced by continuing the seeded sequence: {result['retired_slot_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
