"""interplab.jobs.validate (SS6, GATE G2) -- computes specificity,
sensitivity, cross_lingual_firing, selectivity, and the probe comparator
for one (checkpoint, feature_index, concept_id), applies bands, emits A8.

Reads A7 (+ the sae_checkpoint and index it references), A2 (one concept
file), A3 (existence-checked, linked for provenance); writes A8 directly to
`registry/` (§7.1, same as `certify`/`characterize`/`store_qa`).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from sae_lens import SAE

from interplab.core import configs, envelope, hashing, uris
from interplab.core._schema_registry import SCHEMAS_ROOT
from interplab.core._schema_registry import validate as validate_against_schema
from interplab.core.errors import ContractViolationError
from interplab.registry.registry import REGISTRY_ROOT, REPO_ROOT
from interplab.registry.registry import get as registry_get
from interplab.registry.registry import put as registry_put
from interplab.registry.run_card import new_run_card
from interplab.validation import bands as bands_mod
from interplab.validation import loader as loader_mod
from interplab.validation import probe as probe_mod
from interplab.validation import selectivity as selectivity_mod
from interplab.validation import sensitivity as sensitivity_mod
from interplab.validation import specificity as specificity_mod
from interplab.validation.judge import NoOpRubricJudge, StubRubricJudge

DEFAULT_CONCEPTS_LOCATION = "local:data/concepts"
_CONCEPT_BATTERY_SCHEMA = SCHEMAS_ROOT / "concept_battery" / "v1.schema.json"
_RUBRIC_JUDGES = {"stub": StubRubricJudge, "none": NoOpRubricJudge}


def _get_or_raise(content_hash: str, *, registry_root: Path, role: str) -> dict:
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except Exception as e:
        raise ContractViolationError(f"could not resolve {role} {content_hash!r}: {e}") from e


def _find_subject_ref(artifact: dict, role: str) -> dict:
    for ref in artifact["subject"]:
        if ref["role"] == role:
            return ref
    raise ContractViolationError(
        f"{artifact['artifact_type']} {artifact['self_hash']!r} has no subject entry with role {role!r}"
    )


def _load_local(location: str, *, what: str) -> Path:
    parsed = uris.parse(location)
    if parsed.scheme != "local":
        raise NotImplementedError(
            f"validate can only load {what} from local: URIs in this environment; got {location!r}"
        )
    return uris.resolve_local(location)


def _load_concept(concepts_dir: Path, concept_id: str) -> dict:
    """Duplicated (minimal) from `interplab.corpus.battery.load_battery`
    (§1 Ground Rule 2: `validation`/`jobs.validate` may not import `corpus`)."""
    path = concepts_dir / f"{concept_id}.yaml"
    if not path.is_file():
        raise ContractViolationError(f"no concept file for {concept_id!r} under {concepts_dir}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_against_schema(payload, _CONCEPT_BATTERY_SCHEMA)
    return payload


def run(
    config_path: str | Path,
    *,
    registry_root: Path = REGISTRY_ROOT,
    repo_root: Path = REPO_ROOT,
) -> int:
    config = configs.load_and_validate(config_path, "validate")
    manifest_hash = config["characterization_manifest_hash"]
    census_hash = config["census_report_hash"]
    manifest_ref = {
        "content_hash": manifest_hash,
        "location": f"local:registry/characterization_manifest/{hashing.short_hash(manifest_hash)}.json",
        "role": "characterization_manifest",
    }
    census_ref = {
        "content_hash": census_hash,
        "location": f"local:registry/census_report/{hashing.short_hash(census_hash)}.json",
        "role": "census_report",
    }

    handle = new_run_card(
        "validate", config_path, registry_root=registry_root, repo_root=repo_root,
        inputs=[manifest_ref, census_ref],
    )

    status, exit_code, outcome_line = "failed", 4, "unhandled error"
    outputs: list[dict] = []

    try:
        manifest = _get_or_raise(manifest_hash, registry_root=registry_root, role="characterization_manifest")
        _get_or_raise(census_hash, registry_root=registry_root, role="census_report")  # existence check

        checkpoint_ref = _find_subject_ref(manifest, "sae_checkpoint")
        checkpoint = _get_or_raise(
            checkpoint_ref["content_hash"], registry_root=registry_root, role="sae_checkpoint"
        )
        weights_ref = _find_subject_ref(checkpoint, "weights")
        model_ref = _find_subject_ref(checkpoint, "model")
        sae = SAE.load_from_pretrained(
            str(_load_local(weights_ref["location"], what="SAE weights")), device="cpu"
        )
        model = loader_mod.load_model(str(_load_local(model_ref["location"], what="the base model")))
        hook_name = sae.cfg.hook_name

        feature_index = loader_mod.open_feature_index(manifest_hash, registry_root=registry_root)

        target_feature = config["feature_index"]
        if target_feature >= feature_index.n_features:
            raise ContractViolationError(
                f"feature_index {target_feature} is out of range for an index with "
                f"{feature_index.n_features} features"
            )
        view = feature_index.feature(target_feature)

        concepts_location = config.get("concepts_location", DEFAULT_CONCEPTS_LOCATION)
        concepts_dir = _load_local(concepts_location, what="the battery")
        concept = _load_concept(concepts_dir, config["concept_id"])

        judge = _RUBRIC_JUDGES[config["specificity_judge"]](
            marker_words=frozenset(config.get("stub_judge_marker_words", []))
        ) if config["specificity_judge"] == "stub" else _RUBRIC_JUDGES[config["specificity_judge"]]()
        spec = specificity_mod.compute_specificity(view, judge)

        sensitivity, cross_lingual_firing = sensitivity_mod.compute_sensitivity_and_cross_lingual_firing(
            model, sae, hook_name, target_feature, concept
        )

        all_probes = [p for entry in concept["languages"].values() for p in entry["probes"]]
        top_n = config.get("selectivity_top_n", 5)
        sel = selectivity_mod.compute_selectivity(feature_index, target_feature, all_probes, top_n=top_n)

        pos_texts: list[str] = []
        neg_texts: list[str] = []
        for entry in concept["languages"].values():
            if entry["concept_absent"]:
                pos_texts.extend(entry["probes"])
                neg_texts.extend(entry["concept_absent"])
        if not pos_texts or not neg_texts:
            raise ContractViolationError(
                f"concept {config['concept_id']!r} has no language with concept_absent data -- the "
                f"probe comparator has no language-matched negative class to train against"
            )
        seed = config.get("probe_seed", 0)
        try:
            probe_result = probe_mod.train_probe(
                model, sae, hook_name, target_feature, pos_texts, neg_texts, seed=seed
            )
        except ValueError as e:
            raise ContractViolationError(str(e)) from e

        bands_version = config.get("bands_version", 1)
        bands_data = bands_mod.load_bands(bands_version)
        verdict, verdict_basis = bands_mod.apply_bands(
            specificity=spec, sensitivity=sensitivity, selectivity=sel,
            probe={"gap": probe_result.gap}, bands=bands_data,
        )

        payload = {
            "feature_index": target_feature,
            "concept_id": concept["concept_id"],
            "specificity": spec,
            "sensitivity": sensitivity,
            "cross_lingual_firing": cross_lingual_firing,
            "selectivity": sel,
            "probe": {
                "auc": probe_result.auc, "feature_auc": probe_result.feature_auc,
                "gap": probe_result.gap, "probe_config_hash": probe_result.probe_config_hash,
            },
            "verdict": verdict,
            "verdict_basis": verdict_basis,
        }

        battery_ref = {
            "content_hash": hashing.hash_directory(concepts_dir),
            "location": concepts_location,
            "role": "concept_battery",
        }
        artifact = envelope.dump(
            artifact_type="feature_certificate",
            schema_version=1,
            created_by=handle.created_by,
            subject=[checkpoint_ref, manifest_ref, battery_ref, census_ref],
            payload=payload,
        )
        cert_hash = registry_put(artifact, registry_root=registry_root)

        outputs = [
            {
                "content_hash": cert_hash,
                "location": f"local:registry/feature_certificate/{hashing.short_hash(cert_hash)}.json",
                "role": "feature_certificate",
            }
        ]

        if verdict == "red":
            status, exit_code = "gate_failed", 2
        else:
            status, exit_code = "completed", 0
        outcome_line = f"{verdict} feature_certificate {hashing.short_hash(cert_hash)}; basis={verdict_basis}"

    except ContractViolationError as e:
        status, exit_code = "failed", 3
        outcome_line = str(e)
    except Exception as e:  # deliberate catch-all mapping to exit 4 (§6.2)
        status, exit_code = "failed", 4
        outcome_line = f"unexpected error: {e}"
    finally:
        handle.finalize(status, outputs, exit_code, outcome_line=outcome_line)

    return exit_code
