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


class EnvironmentBaselineError(Exception):
    """§6.2 exit code 4 (environment failure) -- ED-32: the resolved
    `sae-lens` major version does not match the certification lab's
    supported baseline. Deliberately its own type, not a bare
    `RuntimeError`: a fail-closed baseline refusal is a designed, tested,
    load-bearing guarantee, not an arbitrary bug, and this codebase's own
    ethos (null-vs-zero-vs-estimate, gate_failed-vs-crash) is to never wear
    the same clothes as an unexpected failure. Callers catch this
    explicitly (not via the generic `except Exception` catch-all) so the
    resulting run card's `outcome_line` names the refusal honestly instead
    of calling a designed guarantee "unexpected"."""
