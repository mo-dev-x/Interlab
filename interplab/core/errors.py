"""Shared exception types implementing the §6.2 exit-code contract.

Jobs catch `ContractViolationError` to map onto exit code 3 without each
job inventing its own taxonomy; any other unhandled exception maps to exit
4 (environment failure). Exit 2 (gate_failed) is not an exception at all --
a red verdict is a normal, successful return; the job writes the artifact
and exits 2, it never raises for it (§6.2: jobs MUST NOT conflate 2 with 3).
"""

from __future__ import annotations


class ContractViolationError(Exception):
    """§6.2 exit code 3: missing/invalid/hash-mismatched input artifact."""
