"""§8.2 `canary_cheese`: cheese-9056 certificate metrics on a pinned slice,
within tolerance, nightly/pre-claim (ED-23).

The real test (`test_cheese_9056_within_tolerance`) is nightly-marked and
requires a researcher-authored `tests/fixtures/canary/cheese_reference.json`
plus a real, locally-synced registry -- neither exists in this dev/CI
environment (no synthetic cheese feature is substituted; ED-23 forbids it).
It skips with an explicit reason rather than being silently omitted.

The remaining tests exercise the comparator *mechanism* itself (tolerance
arithmetic, malformed-reference rejection, unavailability detection) against
synthetic fixtures -- permitted per ED-23, following the zorbium precedent
already used for jobs.steer's claim-mode tests.
"""

from __future__ import annotations

import json

import pytest

from interplab.core import envelope
from interplab.core._schema_registry import SchemaValidationError
from interplab.registry.registry import REPO_ROOT
from interplab.registry.registry import put as registry_put
from tests.canary_lib import (
    REFERENCE_PATH,
    CanaryUnavailable,
    compare_metrics,
    load_reference,
    resolve_and_recompute,
)

_CREATED_BY = {"run_id": "r1", "code_commit": "0" * 40, "entrypoint": "test", "host": "local"}


@pytest.mark.nightly
def test_cheese_9056_within_tolerance():
    if not REFERENCE_PATH.is_file():
        pytest.skip(
            f"{REFERENCE_PATH} does not exist -- researcher-authored after the first real "
            "production certification run (ED-23); no synthetic reference is substituted"
        )
    reference = load_reference()
    try:
        recomputed = resolve_and_recompute(reference)
    except CanaryUnavailable as e:
        pytest.skip(str(e))
    mismatches = compare_metrics(recomputed, reference["expected_metrics"], reference["tolerances"])
    assert not mismatches, "\n".join(mismatches)


# --- mechanism-only tests (synthetic data, not nightly) -----------------


def test_compare_metrics_passes_within_tolerance():
    recomputed = {"probe": {"auc": 0.901}, "sensitivity": {"word_absent_fire_rate": 0.02}}
    expected = {"probe.auc": 0.9, "sensitivity.word_absent_fire_rate": 0.02}
    tolerances = {"probe.auc": 0.01, "sensitivity.word_absent_fire_rate": 0.005}
    assert compare_metrics(recomputed, expected, tolerances) == []


def test_compare_metrics_flags_out_of_tolerance_value():
    recomputed = {"probe": {"auc": 0.5}}
    expected = {"probe.auc": 0.9}
    tolerances = {"probe.auc": 0.01}
    mismatches = compare_metrics(recomputed, expected, tolerances)
    assert len(mismatches) == 1
    assert "probe.auc" in mismatches[0]


def test_compare_metrics_flags_missing_path():
    recomputed = {"probe": {"auc": 0.9}}
    expected = {"probe.gap": 0.1}
    tolerances = {"probe.gap": 0.01}
    mismatches = compare_metrics(recomputed, expected, tolerances)
    assert len(mismatches) == 1
    assert "probe.gap" in mismatches[0]


def test_compare_metrics_walks_list_indices():
    recomputed = {"specificity": {"decile_means": [0.1, 0.2, 3.0]}}
    expected = {"specificity.decile_means.2": 3.0}
    tolerances = {"specificity.decile_means.2": 0.001}
    assert compare_metrics(recomputed, expected, tolerances) == []


def test_load_reference_rejects_mismatched_metric_and_tolerance_keys(tmp_path):
    bad = {
        "checkpoint_hash": "sha256:" + "a" * 64,
        "feature_certificate_hash": "sha256:" + "b" * 64,
        "feature_index": 9056,
        "pinned_slice": {"content_hash": "sha256:" + "c" * 64, "location": "local:x"},
        "expected_metrics": {"probe.auc": 0.9},
        "tolerances": {"probe.gap": 0.01},
    }
    p = tmp_path / "bad_reference.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="same metric paths"):
        load_reference(p)


def test_load_reference_rejects_schema_violation(tmp_path):
    bad = {"checkpoint_hash": "not-a-hash"}
    p = tmp_path / "bad_reference.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        load_reference(p)


def test_resolve_and_recompute_raises_canary_unavailable_for_missing_certificate(tmp_path):
    reference = {
        "checkpoint_hash": "sha256:" + "a" * 64,
        "feature_certificate_hash": "sha256:" + "b" * 64,
        "feature_index": 9056,
        "pinned_slice": {"content_hash": "sha256:" + "c" * 64, "location": "local:x"},
        "expected_metrics": {"probe.auc": 0.9},
        "tolerances": {"probe.auc": 0.01},
    }
    with pytest.raises(CanaryUnavailable):
        resolve_and_recompute(reference, registry_root=tmp_path / "empty_registry")


def test_resolve_and_recompute_raises_canary_unavailable_on_battery_hash_mismatch(tmp_path):
    registry_root = tmp_path / "registry"
    certificate = envelope.dump(
        artifact_type="feature_certificate", schema_version=1, created_by=_CREATED_BY,
        subject=[
            {"content_hash": "sha256:" + "1" * 64, "location": "local:x", "role": "sae_checkpoint"},
            {"content_hash": "sha256:" + "2" * 64, "location": "local:y", "role": "characterization_manifest"},
            # Deliberately wrong content_hash: whatever tests/fixtures/canary actually hashes to,
            # it will never be all-zeroes -- this guarantees a mismatch.
            {"content_hash": "sha256:" + "0" * 64, "location": "local:tests/fixtures/canary", "role": "concept_battery"},
        ],
        payload={
            "feature_index": 9056, "concept_id": "cheese",
            "specificity": {"decile_means": [], "rubric_version": "none", "judge_model": "none", "prompt_version": "none"},
            "sensitivity": {"status": "unavailable", "word_absent_fire_rate": None, "per_language": None},
            "cross_lingual_firing": None,
            "selectivity": {"neighbors": []},
            "probe": {"auc": 0.9, "feature_auc": 0.8, "gap": 0.1, "probe_config_hash": "sha256:" + "3" * 64},
            "verdict": "green", "verdict_basis": ["specificity"],
        },
    )
    cert_hash = registry_put(certificate, registry_root=registry_root)

    reference = {
        "checkpoint_hash": "sha256:" + "1" * 64,
        "feature_certificate_hash": cert_hash,
        "feature_index": 9056,
        "pinned_slice": {"content_hash": "sha256:" + "4" * 64, "location": "local:x"},
        "expected_metrics": {"probe.auc": 0.9},
        "tolerances": {"probe.auc": 0.01},
    }
    with pytest.raises(CanaryUnavailable, match="re-frozen"):
        resolve_and_recompute(reference, registry_root=registry_root, repo_root=REPO_ROOT)
