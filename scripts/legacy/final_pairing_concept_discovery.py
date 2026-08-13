"""Thin compatibility wrapper. The canonical implementation now lives at
`scripts/final_pairing/final_pairing_concept_discovery.py` (a non-legacy
path -- see that file for the real runner, docstring, and every function).
This stub exists ONLY so `python scripts/legacy/final_pairing_concept_discovery.py ...`
keeps working for anything still invoking the old path; it is not an
independent implementation and carries no logic of its own.
"""

from __future__ import annotations

import runpy
from pathlib import Path

_TARGET = Path(__file__).resolve().parent.parent / "final_pairing" / "final_pairing_concept_discovery.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
