"""SS8 capability module (ED-20): assembles capability_delta's exact shape
from caller-supplied perplexities. Reference-style: verifies the shape
matches ED-20 verbatim, field for field."""

from __future__ import annotations

from interplab.evaluation.capability import assemble_capability_delta


def test_shape_matches_ed20_exactly():
    slice_ref = {"content_hash": "sha256:" + "1" * 64, "location": "local:data/pinned_capability_slice.jsonl"}
    result = assemble_capability_delta(
        slice_ref=slice_ref,
        n_tokens=128,
        per_arm=[
            ("baseline", None, 12.5),
            ("steered", 2.0, 15.1),
            ("random_direction", 2.0, 20.0),
            ("random_feature", 2.0, 13.9),
            ("prompt_baseline", None, 12.6),
        ],
    )
    assert set(result) == {"slice", "n_tokens", "per_arm"}
    assert result["slice"] == slice_ref
    assert result["n_tokens"] == 128
    assert result["per_arm"] == [
        {"arm": "baseline", "scale": None, "ppl": 12.5},
        {"arm": "steered", "scale": 2.0, "ppl": 15.1},
        {"arm": "random_direction", "scale": 2.0, "ppl": 20.0},
        {"arm": "random_feature", "scale": 2.0, "ppl": 13.9},
        {"arm": "prompt_baseline", "scale": None, "ppl": 12.6},
    ]


def test_baseline_arm_has_null_scale():
    result = assemble_capability_delta(
        slice_ref={"content_hash": "sha256:" + "2" * 64, "location": "local:x"},
        n_tokens=10,
        per_arm=[("baseline", None, 5.0)],
    )
    assert result["per_arm"][0]["scale"] is None


def test_only_perplexity_is_stored_no_delta_computed():
    """ED-20: "Only perplexities are stored. Consumers derive deltas." --
    the assembled payload has no delta/baseline-relative field anywhere."""
    result = assemble_capability_delta(
        slice_ref={"content_hash": "sha256:" + "3" * 64, "location": "local:x"},
        n_tokens=10,
        per_arm=[("baseline", None, 5.0), ("steered", 1.0, 9.0)],
    )
    for entry in result["per_arm"]:
        assert set(entry) == {"arm", "scale", "ppl"}


def test_validates_against_a9_schema():
    """Round-trips through the real A9 envelope to prove the assembled
    shape satisfies schemas/intervention_result/v1.schema.json's
    capability_delta sub-schema exactly (not just this module's own idea
    of the shape)."""
    from interplab.core import envelope

    slice_ref = {"content_hash": "sha256:" + "4" * 64, "location": "local:data/pinned_capability_slice.jsonl"}
    capability_delta = assemble_capability_delta(
        slice_ref=slice_ref, n_tokens=64, per_arm=[("baseline", None, 8.0), ("steered", 1.5, 9.5)],
    )
    payload = {
        "spec": {
            "kind": "clamp", "feature_index": 9, "value_in_max_units": None, "corpus_max": 5.0,
            "positions": "all", "checkpoint_hash": "sha256:" + "5" * 64, "direction_seed": None,
        },
        "arms": [
            {"arm": "steered", "scales_in_max_units": [1.5], "generations_ref": {"content_hash": "sha256:" + "6" * 64, "location": "local:x"}}
        ],
        "blinding": {"shuffled": True, "map_ref": "local:x/blinding_map.json"},
        "sampling": {"temperature": 1.0, "top_p": 0.9, "max_new_tokens": 10, "seed": 0},
        "lodestar": None,
        "capability_delta": capability_delta,
    }
    artifact = envelope.dump(
        artifact_type="intervention_result", schema_version=1,
        created_by={"run_id": "r1", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"},
        subject=[{"content_hash": "sha256:" + "7" * 64, "location": "local:x", "role": "sae_checkpoint"}],
        payload=payload,
    )
    assert artifact["payload"]["capability_delta"] == capability_delta
