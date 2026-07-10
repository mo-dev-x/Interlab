"""SS7 interventions (GATE G3, TRUNK, shared library): the `attach()` hook
context manager, `InterventionSpec`, and `control_arms`. §5 SS7."""

from interplab.interventions.control import control_arms
from interplab.interventions.hooks import AttachHandle, CallStats, attach
from interplab.interventions.spec import InterventionSpec, from_dict, to_dict

__all__ = [
    "AttachHandle",
    "CallStats",
    "InterventionSpec",
    "attach",
    "control_arms",
    "from_dict",
    "to_dict",
]
