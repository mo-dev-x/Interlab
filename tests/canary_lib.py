"""ED-23 canary mechanism (§8.2 `canary_cheese`): test-only support code,
not part of `interplab` (§1: `tests -> anything`, but nothing under
`interplab/` may import `tests/`).

`resolve_and_recompute` recomputes A8 feature_certificate metrics for a
pinned (checkpoint, feature_index) through the real SS6 computation
functions -- the same ones `interplab.jobs.validate.run()` calls -- without
writing anything to the registry. It raises `CanaryUnavailable` for any
failure traceable to real infrastructure not being present in this
environment (missing registry entry, unresolvable/heavy weight files, a
non-'none' specificity judge). Any other exception is a genuine regression
and is left to propagate -- ED-23: never silently omit the test, never pass
vacuously.

Every input to the recomputation is read from the reference certificate's
own recorded provenance (its `subject` refs and `payload.concept_id`); the
comparator never invents a concept_id, manifest hash, or census hash.

Before recomputing anything, the concept battery directory's content hash
is re-verified against the certificate's recorded `concept_battery` subject
ref (a light, git-tracked artifact) -- a mismatch means the battery changed
since the reference was frozen, so `CanaryUnavailable` is raised rather than
silently recomputing against a different battery. This check is
deliberately NOT extended to the heavy artifacts (weights, model, feature
index): those already fail closed via the availability catch below, and
re-hashing them on every canary run would be prohibitively expensive.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from interplab.core import hashing, uris
from interplab.core._schema_registry import validate as validate_against_schema
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.validation import loader as loader_mod
from interplab.validation import probe as probe_mod
from interplab.validation import selectivity as selectivity_mod
from interplab.validation import sensitivity as sensitivity_mod
from interplab.validation import specificity as specificity_mod
from interplab.validation.judge import NoOpRubricJudge

CANARY_DIR = Path(__file__).resolve().parent / "fixtures" / "canary"
REFERENCE_PATH = CANARY_DIR / "cheese_reference.json"
REFERENCE_SCHEMA_PATH = CANARY_DIR / "cheese_reference.schema.json"


class CanaryUnavailable(Exception):
    """Real infrastructure this canary run needs (registry entry, checkpoint
    weights, index files, concept battery, a real judge) is not present in
    this environment. Callers translate this into `pytest.skip(reason=...)`
    -- never into a silently-omitted or vacuously-passing test."""


def load_reference(path: Path = REFERENCE_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_against_schema(data, REFERENCE_SCHEMA_PATH)
    if data["expected_metrics"].keys() != data["tolerances"].keys():
        raise ValueError(
            "cheese_reference.json: expected_metrics and tolerances must cover exactly the same "
            f"metric paths; got {sorted(data['expected_metrics'])} vs {sorted(data['tolerances'])}"
        )
    return data


def _subject_ref(artifact: dict, role: str) -> dict:
    for ref in artifact["subject"]:
        if ref["role"] == role:
            return ref
    raise CanaryUnavailable(
        f"{artifact['artifact_type']} {artifact.get('self_hash')!r} has no subject entry with role {role!r}"
    )


def resolve_and_recompute(
    reference: dict, *, registry_root: Path = REGISTRY_ROOT, repo_root: Path = REPO_ROOT
) -> dict:
    try:
        certificate = registry_get(reference["feature_certificate_hash"], registry_root=registry_root)
    except Exception as e:
        raise CanaryUnavailable(
            f"reference feature_certificate {reference['feature_certificate_hash']!r} not found in "
            f"registry at {registry_root} -- run this canary only where the real registry is synced"
        ) from e

    judge_model = certificate["payload"]["specificity"]["judge_model"]
    if judge_model != "none":
        raise CanaryUnavailable(
            f"reference certificate's specificity judge_model={judge_model!r} has no real "
            "implementation in this environment -- production rubric judging is researcher-gated "
            "(schemas/configs/validate_v1.schema.json); only 'none' can be faithfully recomputed"
        )

    checkpoint_ref = _subject_ref(certificate, "sae_checkpoint")
    manifest_ref = _subject_ref(certificate, "characterization_manifest")
    battery_ref = _subject_ref(certificate, "concept_battery")

    try:
        # Cheap, no-heavy-artifact check first (Ground Rule: fail fast):
        # the battery is a light, git-tracked directory, unlike the
        # weights/model/feature-index artifacts resolved below, so it can
        # (and must) be re-hashed and compared on every canary run.
        concepts_dir = uris.resolve_local(battery_ref["location"], repo_root=repo_root)
        actual_battery_hash = hashing.hash_directory(concepts_dir)
        if actual_battery_hash != battery_ref["content_hash"]:
            raise CanaryUnavailable(
                f"concept battery at {concepts_dir} has changed since this reference was frozen "
                f"(recorded {battery_ref['content_hash']!r}, now {actual_battery_hash!r}) -- the "
                "reference must be re-frozen against the current battery, not silently recomputed "
                "against a different one"
            )
        concept_id = certificate["payload"]["concept_id"]
        concept_path = concepts_dir / f"{concept_id}.yaml"
        if not concept_path.is_file():
            raise CanaryUnavailable(f"concept battery file not found: {concept_path}")
        concept = yaml.safe_load(concept_path.read_text(encoding="utf-8"))

        checkpoint = registry_get(checkpoint_ref["content_hash"], registry_root=registry_root)
        weights_ref = _subject_ref(checkpoint, "weights")
        model_ref = _subject_ref(checkpoint, "model")
        weights_path = uris.resolve_local(weights_ref["location"], repo_root=repo_root)
        model_path = uris.resolve_local(model_ref["location"], repo_root=repo_root)

        from sae_lens import SAE

        sae = SAE.load_from_pretrained(str(weights_path), device="cpu")
        model = loader_mod.load_model(str(model_path))
        feature_index_obj = loader_mod.open_feature_index(
            manifest_ref["content_hash"], registry_root=registry_root
        )
    except CanaryUnavailable:
        raise
    except Exception as e:
        raise CanaryUnavailable(f"real checkpoint/index/battery not locally accessible: {e}") from e

    target_feature = reference["feature_index"]
    if target_feature >= feature_index_obj.n_features:
        raise CanaryUnavailable(
            f"feature_index {target_feature} is out of range for an index with "
            f"{feature_index_obj.n_features} features -- reference is stale for this checkpoint"
        )
    view = feature_index_obj.feature(target_feature)
    hook_name = sae.cfg.hook_name

    # Genuine science from here down -- NOT wrapped in the availability
    # catch above. A failure here is a real regression, not missing infra.
    specificity = specificity_mod.compute_specificity(view, NoOpRubricJudge())
    sensitivity, cross_lingual_firing = sensitivity_mod.compute_sensitivity_and_cross_lingual_firing(
        model, sae, hook_name, target_feature, concept
    )
    all_probes = [p for entry in concept["languages"].values() for p in entry["probes"]]
    selectivity = selectivity_mod.compute_selectivity(feature_index_obj, target_feature, all_probes, top_n=5)

    pos_texts: list[str] = []
    neg_texts: list[str] = []
    for entry in concept["languages"].values():
        if entry["concept_absent"]:
            pos_texts.extend(entry["probes"])
            neg_texts.extend(entry["concept_absent"])
    probe_result = probe_mod.train_probe(model, sae, hook_name, target_feature, pos_texts, neg_texts, seed=0)

    return {
        "feature_index": target_feature,
        "concept_id": certificate["payload"]["concept_id"],
        "specificity": specificity,
        "sensitivity": sensitivity,
        "cross_lingual_firing": cross_lingual_firing,
        "selectivity": selectivity,
        "probe": {
            "auc": probe_result.auc, "feature_auc": probe_result.feature_auc,
            "gap": probe_result.gap, "probe_config_hash": probe_result.probe_config_hash,
        },
    }


def _get_path(payload: dict, dotted_path: str):
    node = payload
    for part in dotted_path.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                raise KeyError(f"{dotted_path!r}: no key {part!r} in recomputed payload")
            node = node[part]
        else:
            raise KeyError(f"{dotted_path!r}: cannot descend into {type(node).__name__} at {part!r}")
    return node


def compare_metrics(recomputed_payload: dict, expected_metrics: dict, tolerances: dict) -> list[str]:
    """Pure comparison, no I/O -- fully unit-testable against synthetic
    payloads (ED-23: synthetic fixtures are for testing the mechanism, not
    the science). Returns a list of mismatch descriptions; empty = pass."""
    mismatches = []
    for dotted_path, expected in expected_metrics.items():
        tolerance = tolerances[dotted_path]
        try:
            actual = _get_path(recomputed_payload, dotted_path)
        except KeyError as e:
            mismatches.append(str(e))
            continue
        if isinstance(actual, bool) or not isinstance(actual, int | float):
            mismatches.append(f"{dotted_path}: recomputed value {actual!r} is not numeric")
            continue
        if abs(float(actual) - float(expected)) > tolerance:
            mismatches.append(f"{dotted_path}: expected {expected} +/- {tolerance}, recomputed {actual}")
    return mismatches
