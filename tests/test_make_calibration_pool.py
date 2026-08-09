"""Tests for scripts/legacy/make_calibration_pool.py (Prereg v1.9 SS13.1,
v1.10 magnitude-floor amendment).

Two invariants matter, and every test here checks one of them directly or
checks that a violation of it is loud rather than silent:
  1. extending the seeded draw must not silently redraw the adjudicated
     composition column -- unaffected by the floor, which never touches
     composition.
  2. every calibration-reserved value is >= RESERVED_FLOOR, achieved by
     walking further into the SAME seeded sequence (never re-seeding),
     and the only thing ever surfaced about a replacement is a count.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "make_calibration_pool.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_mod = _load("make_calibration_pool", SCRIPT)

_INITIAL_TOTAL_N = pool_mod.COMPOSITION_N + pool_mod.RESERVED_N


def _sufficient_total_n() -> int:
    return pool_mod.find_sufficient_total_n()


# ---------------------------------------------------------------------------
# composition prefix stability -- unaffected by the floor
# ---------------------------------------------------------------------------


def test_full_pool_prefix_equals_the_independently_reproduced_composition_draw():
    full_pool = pool_mod.draw_full_pool(total_n=_INITIAL_TOTAL_N)
    composition = pool_mod.draw_composition_only()
    assert full_pool[: pool_mod.COMPOSITION_N] == composition


def test_assert_prefix_stability_does_not_raise_on_the_real_draw():
    full_pool = pool_mod.draw_full_pool(total_n=_sufficient_total_n())
    pool_mod.assert_prefix_stability(full_pool)  # must not raise


def test_assert_prefix_stability_raises_loudly_on_a_corrupted_prefix():
    full_pool = pool_mod.draw_full_pool(total_n=_INITIAL_TOTAL_N)
    corrupted = list(full_pool)
    corrupted[0] = corrupted[0] + 1 if corrupted[0] + 1 not in corrupted else corrupted[0] - 1
    with pytest.raises(AssertionError, match="prefix-stability check FAILED"):
        pool_mod.assert_prefix_stability(corrupted)


def test_reproducibility_is_stable_across_repeated_calls():
    assert pool_mod.draw_full_pool(total_n=_INITIAL_TOTAL_N) == pool_mod.draw_full_pool(total_n=_INITIAL_TOTAL_N)
    assert pool_mod.draw_composition_only() == pool_mod.draw_composition_only()


# ---------------------------------------------------------------------------
# magnitude floor: find_sufficient_total_n / select_reserved_with_floor
# ---------------------------------------------------------------------------


def test_find_sufficient_total_n_yields_enough_qualifying_reserved_values():
    total_n = pool_mod.find_sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    qualifying = [v for v in full_pool[pool_mod.COMPOSITION_N :] if v >= pool_mod.RESERVED_FLOOR]
    assert len(qualifying) >= pool_mod.RESERVED_N


def test_find_sufficient_total_n_is_minimal():
    """One less than the returned total_n must NOT already satisfy the
    floor requirement -- otherwise this isn't "continue only as far as
    needed," it's an arbitrary margin."""
    total_n = pool_mod.find_sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n - 1)
    qualifying = [v for v in full_pool[pool_mod.COMPOSITION_N :] if v >= pool_mod.RESERVED_FLOOR]
    assert len(qualifying) < pool_mod.RESERVED_N


def test_select_reserved_with_floor_all_values_meet_the_floor():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _replaced = pool_mod.select_reserved_with_floor(full_pool)
    assert len(reserved) == pool_mod.RESERVED_N
    assert all(v >= pool_mod.RESERVED_FLOOR for v in reserved)


def test_select_reserved_with_floor_preserves_draw_order():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _replaced = pool_mod.select_reserved_with_floor(full_pool)
    expected = [v for v in full_pool[pool_mod.COMPOSITION_N :] if v >= pool_mod.RESERVED_FLOOR][: pool_mod.RESERVED_N]
    assert reserved == expected


def test_select_reserved_with_floor_replaced_count_matches_below_floor_count():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, replaced_count = pool_mod.select_reserved_with_floor(full_pool)
    candidates = full_pool[pool_mod.COMPOSITION_N :]
    below_floor = [v for v in candidates if v < pool_mod.RESERVED_FLOOR]
    assert replaced_count == len(below_floor)
    # every below-floor candidate was genuinely skipped, not silently kept
    assert set(below_floor).isdisjoint(set(reserved))


def test_select_reserved_with_floor_raises_if_pool_too_small():
    small_pool = pool_mod.draw_full_pool(total_n=_INITIAL_TOTAL_N)
    with pytest.raises(ValueError, match="need"):
        pool_mod.select_reserved_with_floor(small_pool)


def test_composition_keeps_any_values_below_the_floor():
    """SS13.1/v1.10: the floor applies ONLY to the reserved slice --
    filtering composition would be a denominator change."""
    composition = pool_mod.draw_composition_only()
    full_pool = pool_mod.draw_full_pool(total_n=_sufficient_total_n())
    assert full_pool[: pool_mod.COMPOSITION_N] == composition  # untouched regardless of any value's magnitude


def test_full_pool_reserved_slice_is_disjoint_from_composition():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _ = pool_mod.select_reserved_with_floor(full_pool)
    pool_mod.assert_disjoint_from_composition(full_pool, reserved)  # must not raise


def test_assert_disjoint_from_composition_raises_on_engineered_collision():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _ = pool_mod.select_reserved_with_floor(full_pool)
    colliding_reserved = [full_pool[0], *reserved[1:]]  # first reserved value replaced with a composition value
    with pytest.raises(AssertionError, match="disjointness check FAILED"):
        pool_mod.assert_disjoint_from_composition(full_pool, colliding_reserved)


# ---------------------------------------------------------------------------
# build_reserved_records / slot indirection
# ---------------------------------------------------------------------------


def test_build_reserved_records_slots_are_one_indexed_and_contiguous():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _ = pool_mod.select_reserved_with_floor(full_pool)
    records = pool_mod.build_reserved_records(reserved)
    assert len(records) == pool_mod.RESERVED_N
    assert [r["slot"] for r in records] == list(range(1, pool_mod.RESERVED_N + 1))


def test_build_reserved_records_index_matches_selection_order():
    total_n = _sufficient_total_n()
    full_pool = pool_mod.draw_full_pool(total_n=total_n)
    reserved, _ = pool_mod.select_reserved_with_floor(full_pool)
    records = pool_mod.build_reserved_records(reserved)
    for record, expected_index in zip(records, reserved, strict=True):
        assert record["index"] == expected_index


def test_build_reserved_records_default_fetched_is_false():
    records = pool_mod.build_reserved_records([1000, 1001, 1002])
    assert all(r["fetched"] is False for r in records)


def test_build_reserved_records_preserves_existing_fetched_by_index():
    reserved = [1000, 1001, 1002, 1003, 1004]
    fetched_map = {reserved[1]: True, reserved[3]: True}
    records = pool_mod.build_reserved_records(reserved, existing_fetched=fetched_map)
    fetched_slots = {r["slot"] for r in records if r["fetched"]}
    assert fetched_slots == {2, 4}  # 1-indexed slots for positions 1 and 3


# ---------------------------------------------------------------------------
# write_reserved_pool: end-to-end, including a re-run that must preserve
# fetched flags rather than reset them
# ---------------------------------------------------------------------------


def test_write_reserved_pool_schema_and_counts(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    written, replaced_count = pool_mod.write_reserved_pool(out_path)
    assert written == out_path
    assert isinstance(replaced_count, int) and replaced_count >= 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["composition_n"] == pool_mod.COMPOSITION_N
    assert data["reserved_n"] == pool_mod.RESERVED_N
    assert data["reserved_floor"] == pool_mod.RESERVED_FLOOR
    assert data["replaced_slot_count"] == replaced_count
    assert len(data["reserved_features"]) == pool_mod.RESERVED_N
    for record in data["reserved_features"]:
        assert set(record) == {"slot", "index", "fetched"}
        assert record["index"] >= pool_mod.RESERVED_FLOOR


def test_write_reserved_pool_declares_the_floor_justification_in_the_artifact(tmp_path):
    """'that justification should live in the artifact, not only in the
    prereg' -- content-blindness must be stated in the JSON itself."""
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "reserved_floor_justification" in data
    assert "arbitrary" in data["reserved_floor_justification"]
    assert "denominator" in data["reserved_floor_justification"]


def test_write_reserved_pool_rerun_preserves_fetched_flags(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    data["reserved_features"][5]["fetched"] = True
    out_path.write_text(json.dumps(data), encoding="utf-8")

    pool_mod.write_reserved_pool(out_path)  # re-run, same seed/sizes/floor
    rewritten = json.loads(out_path.read_text(encoding="utf-8"))
    assert rewritten["reserved_features"][5]["fetched"] is True
    assert all(
        r["fetched"] is False for i, r in enumerate(rewritten["reserved_features"]) if i != 5
    )


def test_write_reserved_pool_never_prints_an_index(tmp_path, capsys):
    """Slot indirection (SS13.2b) is void if the generator itself prints
    an index anywhere an orchestrator would read it -- now explicitly
    binding on verification too, per the incident where a check of this
    kind was how indices ended up hand-transcribed into the prereg.
    Exact-match, not a substring scan -- a reserved index could
    coincidentally equal a digit substring of RESERVED_N/COMPOSITION_N/
    RESERVED_FLOOR/replaced_slot_count or the tmp path, which would make
    a substring check flag a false leak."""
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.main(["--out-path", str(out_path)])
    captured = capsys.readouterr()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    replaced_count = data["replaced_slot_count"]
    assert captured.out == (
        f"reserved pool: {pool_mod.RESERVED_N} slots written to {out_path}\n"
        f"composition denominator unchanged: {pool_mod.COMPOSITION_N}\n"
        f"reserved-slice magnitude floor: >= {pool_mod.RESERVED_FLOOR} "
        f"({replaced_count} slot(s) replaced to satisfy it)\n"
    )
    assert captured.err == ""


# ---------------------------------------------------------------------------
# retire_and_replace (incident 4 remediation): removes an already-leaked
# index, replaces it by continuing the sequence, preserves every other
# slot's NUMBER (only the retired slot's index may change).
# ---------------------------------------------------------------------------


def test_retire_and_replace_replaces_only_the_retired_index(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    before = json.loads(out_path.read_text(encoding="utf-8"))["reserved_features"]
    retired_index = before[10]["index"]
    retired_slot = before[10]["slot"]

    _, retired_count = pool_mod.retire_and_replace(out_path, {retired_index})
    assert retired_count == 1

    after = json.loads(out_path.read_text(encoding="utf-8"))["reserved_features"]
    assert len(after) == pool_mod.RESERVED_N
    # every slot number is unchanged and in the same position
    assert [r["slot"] for r in after] == [r["slot"] for r in before]
    # every non-retired slot's index is byte-identical to before
    for b, a in zip(before, after, strict=True):
        if b["slot"] != retired_slot:
            assert a["index"] == b["index"]
    # the retired slot's index changed, to something not the retired value
    retired_entry_after = next(r for r in after if r["slot"] == retired_slot)
    assert retired_entry_after["index"] != retired_index
    assert retired_entry_after["fetched"] is False


def test_retire_and_replace_new_value_meets_the_floor_and_is_disjoint(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    before = json.loads(out_path.read_text(encoding="utf-8"))["reserved_features"]
    retired_index = before[3]["index"]

    pool_mod.retire_and_replace(out_path, {retired_index})
    after = json.loads(out_path.read_text(encoding="utf-8"))["reserved_features"]
    composition = set(pool_mod.draw_composition_only())
    all_indices = [r["index"] for r in after]
    assert len(set(all_indices)) == len(all_indices)  # still no duplicates
    assert all(v >= pool_mod.RESERVED_FLOOR for v in all_indices)
    assert composition.isdisjoint(all_indices)
    assert retired_index not in all_indices


def test_retire_and_replace_no_op_when_nothing_matches(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    before = out_path.read_text(encoding="utf-8")

    _, retired_count = pool_mod.retire_and_replace(out_path, {999999})  # not in the pool
    assert retired_count == 0
    assert out_path.read_text(encoding="utf-8") == before  # untouched, not even total_n_drawn bumped


def test_retire_and_replace_preserves_fetched_flags_of_untouched_slots(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    data["reserved_features"][20]["fetched"] = True
    retired_index = data["reserved_features"][50]["index"]
    out_path.write_text(json.dumps(data), encoding="utf-8")

    pool_mod.retire_and_replace(out_path, {retired_index})
    after = json.loads(out_path.read_text(encoding="utf-8"))["reserved_features"]
    assert after[20]["fetched"] is True
    assert after[50]["fetched"] is False  # replaced -- a brand new index has never been fetched


def test_retire_and_replace_raises_if_pool_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        pool_mod.retire_and_replace(tmp_path / "does_not_exist.json", {1000})


def test_retire_and_replace_records_cumulative_retired_slot_count(tmp_path):
    out_path = tmp_path / "calibration_pool_reserved.json"
    pool_mod.write_reserved_pool(out_path)
    data = json.loads(out_path.read_text(encoding="utf-8"))
    first_retired = data["reserved_features"][5]["index"]
    second_retired = data["reserved_features"][15]["index"]

    pool_mod.retire_and_replace(out_path, {first_retired})
    pool_mod.retire_and_replace(out_path, {second_retired})
    final = json.loads(out_path.read_text(encoding="utf-8"))
    assert final["retired_slot_count"] == 2
