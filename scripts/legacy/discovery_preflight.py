"""Thin compatibility wrapper. The canonical implementation now lives at
`scripts/final_pairing/discovery_preflight.py` (a non-legacy path). This
stub exists ONLY so `python scripts/legacy/discovery_preflight.py` keeps
working for anything still invoking the old path; it carries no logic of
its own.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "final_pairing" / "discovery_preflight.py"

if __name__ == "__main__":
    # To STDERR only: this script's stdout is strict, parseable JSON
    # (final_concept_discovery_dual_gpu_job.default_preflight_runner reads
    # it) -- a deprecation notice on stdout would corrupt that parse.
    print(
        f"DEPRECATED entry point: scripts/legacy/discovery_preflight.py -- use "
        f"{_TARGET} directly. Forwarding for backward compatibility.",
        file=sys.stderr,
    )
    runpy.run_path(str(_TARGET), run_name="__main__")
