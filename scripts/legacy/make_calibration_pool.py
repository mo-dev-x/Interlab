"""Prereg v1.9 SS13.1 / v1.10 magnitude-floor amendment
(reports/adjudication_prereg_v1.md) -- generates the calibration-reserved
feature pool.

THE DRAW: `random.Random(42).sample(range(16384), N)`, walked in order.
The pre-registered composition draw is the first 40 of that sequence --
already adjudicated, already spent, and its denominator does not move.
Positions after the first 40, walked forward, are `calibration-reserved`:
a fresh draw from the identical distribution, used only to measure
inter-rater agreement, and NEVER counted in the composition.

INCIDENT, not a hypothetical: the unfiltered reserved pool contained
several small integers (file counts, section numbers, quantities --
exactly the magnitude range ordinary governance prose uses) and one
ledger paragraph collided on six of them at once. Cry-wolf, twice
predicted, now recorded a third time. The defect was in the POOL, not the
hook -- no regex fix addresses a reserved value that IS a plausible
section number.

THE FLOOR, AND WHY IT IS SAFE: reserved indices must be >= 1000
(`RESERVED_FLOOR`). This is content-blind and stated here, not only in
the prereg, because that is the actual justification and it belongs in
the artifact a rater or auditor might open: an SAE dictionary's position
for a feature is an arbitrary training-time assignment, uncorrelated with
anything the feature detects. Excluding small indices from the reserved
slice changes nothing about what "a fresh uniform draw" measures --
magnitude carries no information about feature identity, so filtering on
it introduces no bias into the calibration sample.

THE FLOOR APPLIES ONLY TO THE RESERVED SLICE. The composition draw keeps
every value it already has, including any below 1000 -- filtering the
composition would be a denominator change, and SS13.1 is unambiguous that
the denominator never moves.

HOW REPLACEMENTS ARE DRAWN: by CONTINUING the same seeded sequence, never
by re-seeding. Concretely: draw `random.Random(42).sample(range(16384), k)`
for a `k` large enough that walking forward from position 40 and keeping
only values >= 1000, in draw order, yields 100 of them; values below the
floor are skipped, not reused, and never redrawn under a different seed.
`find_sufficient_total_n` grows `k` only as far as needed for this run's
actual low-value rate -- it does not pre-commit to a fixed margin.

WHY THIS SCRIPT ASSERTS RATHER THAN ASSUMES THE COMPOSITION PREFIX IS
STABLE: CPython's `random.sample` selects between two internal algorithms
on a `setsize` threshold that changes across this range (277 at k <= 60,
1045 at k >= 100). Extending a seeded sample is only safe if the existing
40 are a stable PREFIX of the longer draw -- verified by hand across
several k values before SS13.1 was adopted, but a one-time manual check is
not a guarantee against a different Python build or a much larger k this
run's floor-filtering happens to need. If the branch ever flips, extending
the draw would silently REDRAW the entire adjudicated composition column
instead of adding to it. That failure must be loud, not silent -- hence
`assert_prefix_stability` raises before this script writes anything,
regardless of how large k grows.

RETIREMENT (incident 4 remediation, see check_reserved_indices.py's
module docstring for the false-negative defect this responds to):
`retire_and_replace` removes a currently-reserved index found by a
whole-tree/whole-history audit to already be leaked, and replaces it by
continuing the same seeded sequence -- same discipline as the magnitude
floor, but keyed on "already burned" rather than "below the floor."
Slot NUMBERS never move for a non-retired entry; only the retired slot's
index changes. Only a count of retired slots may ever be surfaced.

SLOT INDIRECTION (SS13.2b): the orchestrator never opens the output file.
Reserved features are dispatched to raters by SLOT ("round 3, slots
21-30"), never by index. Consequently THIS SCRIPT NEVER PRINTS AN INDEX --
only slot counts, the pool size, and the output path. THIS IS NOW BINDING
ON VERIFICATION TOO, not just on normal runs: a verification step that
prints reserved values "just to check" is exactly how indices have
previously ended up transcribed into prose by hand. Any check against this
pool's actual values must return a boolean or a count -- never the values
themselves, including in ad hoc debugging.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_PATH = REPO_ROOT / "reports" / "calibration_pool_reserved.json"

SEED = 42
POOL_SIZE = 16384  # Gemma Scope 2 L31 width (16k) -- the SAE this draw is over
COMPOSITION_N = 40  # pre-registered denominator; never changes
RESERVED_N = 100
RESERVED_FLOOR = 1000  # calibration-reserved slice only -- see module docstring
_INITIAL_TOTAL_N = COMPOSITION_N + RESERVED_N  # starting point before floor-driven growth


def draw_full_pool(*, seed: int = SEED, pool_size: int = POOL_SIZE, total_n: int) -> list[int]:
    return random.Random(seed).sample(range(pool_size), total_n)


def draw_composition_only(*, seed: int = SEED, pool_size: int = POOL_SIZE, composition_n: int = COMPOSITION_N) -> list[int]:
    """The ORIGINAL pre-registered call, reproduced independently of
    draw_full_pool -- the thing assert_prefix_stability checks the prefix
    of the longer draw against."""
    return random.Random(seed).sample(range(pool_size), composition_n)


def assert_prefix_stability(full_pool: list[int], *, composition_n: int = COMPOSITION_N) -> None:
    """Prereg v1.9 SS13.1: fails loudly if the first `composition_n` of
    `full_pool` no longer match the independently-reproduced composition
    draw. Never assume this holds -- a silent mismatch here would redraw
    an already-adjudicated column. Applies at whatever `len(full_pool)`
    the floor filter ended up needing, not just the original 140."""
    reproduced = draw_composition_only(composition_n=composition_n)
    prefix = full_pool[:composition_n]
    if prefix != reproduced:
        raise AssertionError(
            f"calibration pool prefix-stability check FAILED: the first {composition_n} of "
            f"random.Random({SEED}).sample(range({POOL_SIZE}), {len(full_pool)}) no longer match "
            f"random.Random({SEED}).sample(range({POOL_SIZE}), {composition_n}). Extending this draw "
            "would silently redraw the adjudicated composition column -- refusing to write "
            "the reserved-pool file. This is an environment/Python-version discrepancy, not "
            "something to work around: escalate before touching the pool again."
        )


def assert_disjoint_from_composition(full_pool: list[int], reserved: list[int], *, composition_n: int = COMPOSITION_N) -> None:
    """Prereg v1.9 SS13.1's verification table also checked
    `extension ∩ existing 40 == ∅` -- the SELECTED reserved values must
    not collide with the composition set. (Guaranteed by `sample`'s own
    no-replacement contract, but asserted rather than assumed, same
    principle as prefix stability.)"""
    composition = set(full_pool[:composition_n])
    overlap = composition & set(reserved)
    if overlap:
        raise AssertionError(
            f"calibration pool disjointness check FAILED: {len(overlap)} reserved index(es) "
            "collide with the composition set. Refusing to write the reserved-pool file."
        )


def find_sufficient_total_n(*, seed: int = SEED, pool_size: int = POOL_SIZE, composition_n: int = COMPOSITION_N, reserved_n: int = RESERVED_N, floor: int = RESERVED_FLOOR, start_total_n: int | None = None) -> int:
    """Smallest total_n for which walking `sample(seed, total_n)` forward
    from position `composition_n`, in draw order, yields at least
    `reserved_n` values >= `floor`. Grows one draw at a time -- "continue
    the sequence," not "guess a margin and re-seed if it's not enough.\""""
    total_n = start_total_n or _INITIAL_TOTAL_N
    while True:
        full = draw_full_pool(seed=seed, pool_size=pool_size, total_n=total_n)
        qualifying = [v for v in full[composition_n:] if v >= floor]
        if len(qualifying) >= reserved_n:
            return total_n
        total_n += 1


def select_reserved_with_floor(full_pool: list[int], *, composition_n: int = COMPOSITION_N, reserved_n: int = RESERVED_N, floor: int = RESERVED_FLOOR) -> tuple[list[int], int]:
    """Walks full_pool[composition_n:] IN DRAW ORDER, keeping the first
    `reserved_n` values >= floor. Returns (reserved_values,
    replaced_slot_count) -- replaced_slot_count is how many walked-past
    values were below the floor (skipped, never reused elsewhere; see
    module docstring on why this is a count, never a values list)."""
    candidates = full_pool[composition_n:]
    qualifying = [v for v in candidates if v >= floor]
    if len(qualifying) < reserved_n:
        raise ValueError(
            f"full_pool of length {len(full_pool)} yields only {len(qualifying)} candidates "
            f">= {floor} after position {composition_n}; need {reserved_n}. Call "
            "find_sufficient_total_n for a large-enough total_n first."
        )
    reserved = qualifying[:reserved_n]
    replaced_slot_count = sum(1 for v in candidates if v < floor)
    return reserved, replaced_slot_count


def build_reserved_records(reserved: list[int], *, existing_fetched: dict[int, bool] | None = None) -> list[dict[str, Any]]:
    """slot is the public handle (1..RESERVED_N); index is not -- see
    module docstring. `existing_fetched` lets a re-run preserve prior
    fetched=True flags by INDEX (not slot -- slot numbering is stable
    across re-runs of the same seed/sizes, but keying the merge by index
    is the more conservative choice if this is ever regenerated at a
    different total_n)."""
    existing_fetched = existing_fetched or {}
    return [
        {
            "slot": slot,
            "index": index,
            "fetched": bool(existing_fetched.get(index, False)),
        }
        for slot, index in enumerate(reserved, start=1)
    ]


def load_existing_fetched_by_index(path: Path) -> dict[int, bool]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {rec["index"]: bool(rec.get("fetched", False)) for rec in data.get("reserved_features", [])}


def write_reserved_pool(out_path: Path, *, seed: int = SEED, pool_size: int = POOL_SIZE, composition_n: int = COMPOSITION_N, reserved_n: int = RESERVED_N, floor: int = RESERVED_FLOOR) -> tuple[Path, int]:
    """Returns (out_path, replaced_slot_count) -- the count is the only
    thing about the floor filter's effect that may ever be surfaced;
    never the values it replaced or the values it kept."""
    total_n = find_sufficient_total_n(seed=seed, pool_size=pool_size, composition_n=composition_n, reserved_n=reserved_n, floor=floor)
    full_pool = draw_full_pool(seed=seed, pool_size=pool_size, total_n=total_n)
    assert_prefix_stability(full_pool, composition_n=composition_n)

    reserved, replaced_slot_count = select_reserved_with_floor(
        full_pool, composition_n=composition_n, reserved_n=reserved_n, floor=floor
    )
    assert_disjoint_from_composition(full_pool, reserved, composition_n=composition_n)
    assert all(v >= floor for v in reserved)  # redundant with select_reserved_with_floor; cheap, and this is the invariant that matters most

    existing_fetched = load_existing_fetched_by_index(out_path)
    records = build_reserved_records(reserved, existing_fetched=existing_fetched)

    payload = {
        "schema_note": (
            "One record per calibration-reserved feature: slot (1..N, the public handle -- "
            "dispatch rounds by slot, never by index) and fetched (bool, whether evidence has "
            "been pulled under SS10.0b). The orchestrator never opens this file; a rater "
            "resolves slot -> index locally."
        ),
        "prereg_ref": "reports/adjudication_prereg_v1.md SS13.1 (v1.9), magnitude-floor amendment (v1.10)",
        "seed": seed,
        "pool_size": pool_size,
        "composition_n": composition_n,
        "reserved_n": reserved_n,
        "reserved_floor": floor,
        "reserved_floor_justification": (
            "Applies only to the calibration-reserved slice, never to the composition draw "
            "(filtering composition would be a denominator change). Content-blind: an SAE "
            "dictionary position is arbitrary with respect to what a feature detects, so index "
            "magnitude cannot correlate with any feature property -- excluding small indices "
            "introduces no bias, it only avoids values that double as ordinary governance-prose "
            "numbers (file counts, section numbers, quantities)."
        ),
        "total_n_drawn": total_n,
        "replaced_slot_count": replaced_slot_count,
        "reserved_features": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path, replaced_slot_count


def retire_and_replace(out_path: Path, retired_indices: set[int], *, seed: int = SEED, pool_size: int = POOL_SIZE, composition_n: int = COMPOSITION_N, reserved_n: int = RESERVED_N, floor: int = RESERVED_FLOOR) -> tuple[Path, int]:
    """Removes any currently-reserved index in `retired_indices` --
    already burned, found by scripts/legacy/check_reserved_indices.py's
    whole-tree/whole-history audit in content that predates detection --
    and replaces it by CONTINUING the same seeded sequence, same
    discipline as the magnitude floor.

    SLOT NUMBERS ARE PRESERVED for every non-retired entry: only the
    INDEX at a retired slot changes, never its slot number. Slots are
    dispatched to raters as stable public handles ("round 3, slots
    21-30") -- silently renumbering slot 38..100 because slot 37 got
    retired would invalidate any already-dispatched reference to those
    slots for no reason connected to the actual defect.

    Returns (out_path, retired_count) -- retired_count is the only thing
    about this operation that may ever be surfaced. NEVER the retired
    values, the replacement values, or which slot changed. Callers (see
    scripts/legacy/audit_and_retire_reserved_leaks.py) must consume
    `retired_indices` and this function entirely in-process."""
    if not out_path.exists():
        raise FileNotFoundError(f"{out_path} does not exist -- nothing to retire from")
    data = json.loads(out_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = data["reserved_features"]

    retired_slots = [r for r in records if r["index"] in retired_indices]
    retired_count = len(retired_slots)
    if retired_count == 0:
        return out_path, 0

    already_in_use = {r["index"] for r in records}
    exclude = already_in_use | set(retired_indices)  # never reuse a value already in a slot, retired or not

    total_n = data.get("total_n_drawn") or find_sufficient_total_n(
        seed=seed, pool_size=pool_size, composition_n=composition_n, reserved_n=reserved_n, floor=floor
    )
    while True:
        full_pool = draw_full_pool(seed=seed, pool_size=pool_size, total_n=total_n)
        assert_prefix_stability(full_pool, composition_n=composition_n)
        fresh_qualifying = [v for v in full_pool[composition_n:] if v >= floor and v not in exclude]
        if len(fresh_qualifying) >= retired_count:
            replacements = fresh_qualifying[:retired_count]
            break
        total_n += 1

    assert_disjoint_from_composition(full_pool, replacements, composition_n=composition_n)
    assert all(v not in retired_indices and v not in already_in_use for v in replacements)

    replacement_iter = iter(replacements)
    new_records = [
        {"slot": r["slot"], "index": next(replacement_iter), "fetched": False}
        if r["index"] in retired_indices
        else r
        for r in records
    ]

    data["reserved_features"] = new_records
    data["total_n_drawn"] = total_n
    data["retired_slot_count"] = data.get("retired_slot_count", 0) + retired_count
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out_path, retired_count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-path", default=str(DEFAULT_OUT_PATH))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path, replaced_slot_count = write_reserved_pool(Path(args.out_path))
    # Slot counts and the path only -- never an index (see module docstring).
    print(f"reserved pool: {RESERVED_N} slots written to {out_path}")
    print(f"composition denominator unchanged: {COMPOSITION_N}")
    print(f"reserved-slice magnitude floor: >= {RESERVED_FLOOR} ({replaced_slot_count} slot(s) replaced to satisfy it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
