"""Thin compatibility wrapper. The canonical implementation now lives at
`scripts/final_pairing/final_concept_discovery_matched_configuration_job.py`
(a non-legacy path). This stub exists ONLY so
`python scripts/legacy/final_concept_discovery_matched_configuration_job.py ...`
keeps working for anything still invoking the old path; it carries no
logic of its own.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "final_pairing" / "final_concept_discovery_matched_configuration_job.py"

if __name__ == "__main__":
    print(
        f"DEPRECATED entry point: scripts/legacy/final_concept_discovery_matched_configuration_job.py -- use "
        f"{_TARGET} directly. Forwarding for backward compatibility.",
        file=sys.stderr,
    )
    runpy.run_path(str(_TARGET), run_name="__main__")
