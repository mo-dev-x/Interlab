"""§5 SS7 `InterventionSpec` -- the frozen contract object for every
intervention. Serialized verbatim into A9's `spec` field
(schemas/intervention_result/v1.schema.json, `direction_seed` added per
ED-3/ED-4).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class InterventionSpec:
    kind: Literal["noop", "clamp", "ablate", "add_direction"]
    feature_index: int | None
    value_in_max_units: float | None
    corpus_max: float | None
    positions: Literal["all", "generated_only"]
    checkpoint_hash: str
    direction_seed: int | None = None  # ED-3: set iff kind == "add_direction"


def to_dict(spec: InterventionSpec) -> dict:
    return asdict(spec)


def from_dict(data: dict) -> InterventionSpec:
    return InterventionSpec(**data)
