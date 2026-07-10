"""SS8 blinding (§5 SS8): shuffle order and strip condition-identifying
fields from generation records before they reach judging, so no judge
prompt can correlate position or metadata with condition (architecture doc
SS8 responsibility 1).

Lodestar-agnostic by design: operates on plain dicts, not `lodestar.models`
objects, so this module carries no dependency on `lodestar-eval` (only
`interplab.evaluation.lodestar_adapter` will, once ED-19's migration is
unblocked -- §1's "only interplab.evaluation may import lodestar-eval" is
satisfied at the package level either way).

Distinct from `jobs.steer`'s own inline shuffle, which produces A9's
`blinding.shuffled = true` at creation time (§1: `jobs.steer`'s allowed
edges are core/registry/interventions/characterization only -- it cannot
import this package, so it duplicates the minimal shuffle itself, Ground
Rule 2). This module is the judge-facing blinding step: what a future
`jobs.judge` uses to build the data an external judge actually sees, kept
correct and tested here independent of whether that job exists yet.
"""

from __future__ import annotations

import dataclasses

import numpy as np


@dataclasses.dataclass(frozen=True)
class BlindedRecord:
    blind_id: str
    text: str
    prompt: str


def shuffle_and_strip(
    records: list[dict], *, rng_seed: int
) -> tuple[list[BlindedRecord], dict[str, dict]]:
    """`records`: dicts with at least `{text, prompt, arm, scale, prompt_id}`
    (jobs.steer's own generation records, or equivalent). Returns
    `(blinded_records, correlation_map)`: `blinded_records` carry only
    `{blind_id, text, prompt}` -- no arm, scale, or condition anywhere.
    `correlation_map` keys each `blind_id` back to its true `{arm, scale,
    prompt_id}` -- this is "the blinding map" (§5 SS8 invariant: "the
    blinding map never enters any file Lodestar reads"); callers keep it
    registry/artifact-side and never pass it to a judge.

    Deterministic for a fixed `(records, rng_seed)`.
    """
    if not records:
        return [], {}
    order = np.random.default_rng(rng_seed).permutation(len(records))
    blinded: list[BlindedRecord] = []
    correlation_map: dict[str, dict] = {}
    for rank, idx in enumerate(order):
        record = records[int(idx)]
        blind_id = f"blind-{rank:06d}"
        blinded.append(BlindedRecord(blind_id=blind_id, text=record["text"], prompt=record["prompt"]))
        correlation_map[blind_id] = {
            "arm": record["arm"], "scale": record.get("scale"), "prompt_id": record["prompt_id"],
        }
    return blinded, correlation_map
