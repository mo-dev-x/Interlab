"""SS8 blinding (§5 SS8): shuffle order + strip identity before judging."""

from __future__ import annotations

from interplab.evaluation.blinding import BlindedRecord, shuffle_and_strip


def _records():
    return [
        {"arm": "baseline", "scale": None, "prompt_id": "p0", "prompt": "hi", "text": "hello"},
        {"arm": "steered", "scale": 1.0, "prompt_id": "p1", "prompt": "bye", "text": "goodbye"},
        {"arm": "random_direction", "scale": 2.0, "prompt_id": "p2", "prompt": "yo", "text": "sup"},
    ]


def test_empty_input_returns_empty():
    blinded, correlation_map = shuffle_and_strip([], rng_seed=0)
    assert blinded == []
    assert correlation_map == {}


def test_blinded_records_carry_no_identity():
    blinded, _map = shuffle_and_strip(_records(), rng_seed=0)
    assert len(blinded) == 3
    for record in blinded:
        assert isinstance(record, BlindedRecord)
        assert not hasattr(record, "arm")
        assert not hasattr(record, "condition")


def test_correlation_map_recovers_true_identity():
    records = _records()
    blinded, correlation_map = shuffle_and_strip(records, rng_seed=0)
    assert set(correlation_map) == {r.blind_id for r in blinded}
    # every true record is recoverable via the map, and texts match up
    recovered_texts = set()
    for record in blinded:
        true = correlation_map[record.blind_id]
        original = next(r for r in records if r["prompt_id"] == true["prompt_id"])
        assert record.text == original["text"]
        assert true["arm"] == original["arm"]
        assert true["scale"] == original["scale"]
        recovered_texts.add(record.text)
    assert recovered_texts == {r["text"] for r in records}


def test_deterministic_for_fixed_seed():
    records = _records()
    blinded_a, map_a = shuffle_and_strip(records, rng_seed=7)
    blinded_b, map_b = shuffle_and_strip(records, rng_seed=7)
    assert [r.text for r in blinded_a] == [r.text for r in blinded_b]
    assert map_a == map_b


def test_different_seeds_can_produce_different_orders():
    records = _records() * 3  # enough records that a fixed permutation collision is implausible
    blinded_a, _ = shuffle_and_strip(records, rng_seed=1)
    blinded_b, _ = shuffle_and_strip(records, rng_seed=2)
    assert [r.text for r in blinded_a] != [r.text for r in blinded_b]
