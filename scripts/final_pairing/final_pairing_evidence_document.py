"""Assembles the `concept_bundle.discovery_input` document (schema v1.3)
that `scripts/concept_bundle_publish.py` (Engineer 3, branch
`eng3/concept-bundle`, currently at commit ac9ea40) accepts, from this
repository's own discovery-runner output (`final_pairing_concept_
discovery.py`'s `run()` result and grid verdicts) plus a small set of
caller-supplied identity facts that no file in this repository may invent
by reading a clock or guessing a name.

SUPERSEDES 2c8cf5b/schema v1.1. `d833ba4` (superseded by `ac9ea40`, both
schema v1.3) rebased onto identity v1.2.0 (later v1.3.0) and added: a
root-level `configuration` block (name/completeness/model_n_layers/
grid_cells_expected/grid_cells_recorded), three new required `pairing`
fields (`release`, `loader_sae_id`, `params_sha256`), and a required
`causal_validation.judge` block (`model`/`rubric_version`/`prompt_
version`, refusing the no-op judge identities). The root-required
undercount this module previously found in 2c8cf5b (9 declared vs. 12
enforced) is gone as of d833ba4/ac9ea40: `accepted_input_schema()`'s own
printed `objects["<root>"]["required"]` lists all 13 fields the enforcing
`_closed()` call actually requires (verified by reading both directly out
of `D:/devcache/wt/concept-bundle`, a clean worktree of `eng3/concept-
bundle`, re-verified at each successive consumer commit). `ac9ea40`
additionally: separates `pairing.params_sha256` (MEASURED, emitted here)
from the identity artifact's own `params_expected_sha256` (never emitted
by a producer -- refused by name if it is), and adds the `dose-check`
gate over the one-allocation generation manifest/selection record (see
`final_pairing_one_allocation_generation.py`), which the discovery
document does not yet reference (the Architect's pending ruling on the
exact field -- see that module's own docstring).

WHY A SEPARATE FILE. `interplab/concept_bundle/` (the package
`concept_bundle_publish.py` imports) does not exist on this branch -- it
was authored on the sibling branch `eng3/concept-bundle` (confirmed:
`git merge-base --is-ancestor final-pairing-harness eng3/concept-bundle`
and the reverse both fail; the two branches diverged from a common
ancestor and neither contains the other). This file therefore does not
import that package, does not merge that branch, and does not vendor a
copy of it -- it emits a plain dict matching the SHAPE Engineer 3's
`accepted_input_schema()`/`validate_discovery()` declare and enforce, and
leaves the actual reconciliation to be run as a real subprocess against a
checked-out copy of that branch -- never faked, never assumed to pass.
`run_gating_report_with_eng3` below runs the real `gating-report`
subcommand (producer schema + a genuinely emitted document, together) and
IS the compatibility decision; `reconcile_against_static_snapshot` is a
committed, offline fallback for machines with no live eng3 checkout
(Tamia compute nodes) and is explicitly NON-GATING -- it decides nothing
about submission compatibility on its own.

WHAT THIS FILE DOES NOT DO, ON PURPOSE:

- It does not compute `validation.{specificity,sensitivity,
  cross_lingual_firing,selectivity,probe,verdict,verdict_basis}` (the
  feature_certificate payload) -- that is Engineer 3's `interplab.
  validation` territory (probe/specificity/selectivity modules already
  exist there), not a computation this discovery runner performs. It is
  accepted here as an already-computed dict, supplied by the caller.
- It does not choose `calibrated_by`/`hypothesis_source`/`search_scope`/
  `run_id`/`code_commit`/`host`/`created_at` -- every one of these is a
  required, explicit caller-supplied argument, because this project's own
  no-clock, no-invented-identity discipline (see
  `final_pairing_concept_discovery.py`'s own module docstring) applies
  here exactly as it does everywhere else.
- It does not run `interplab.registry.put`'s deep JSON-Schema validation
  of `schemas/feature_certificate/v1.schema.json` and friends (those
  schemas do not exist on this branch either) -- only `validate_discovery`'s
  shape/identity/chronology checks are exercised, which is exactly what
  `concept_bundle_publish.py validate` (as opposed to `seal`) checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DISCOVERY_SCHEMA_VERSION = "1.3"  # must equal concept_bundle_publish.DISCOVERY_SCHEMA_VERSION

#: All 14 root fields required per `protocols/final_pairing/v1/discovery_
#: document_generation_binding.json` v1.1.0 (commit 40061b6): `generation_
#: manifests` is NEW, ratified there ("a new REQUIRED top-level object" --
#: a MAJOR schema bump Engineer 3 applies the numeral for). Emitted here
#: ahead of that numeral landing on the consumer side, since the shape is
#: fully specified and unambiguous; `DISCOVERY_SCHEMA_VERSION` above is
#: left at "1.3" until Engineer 3's actual bumped value is known (bumping
#: to a guessed wrong numeral would create a worse, silent mismatch than
#: staying visibly one version behind).
ROOT_REQUIRED_FIELDS: tuple[str, ...] = (
    "discovery_schema_version", "run", "pairing", "concept", "discovery",
    "validation", "subject", "calibration", "positions",
    "prompt_set", "causal_validation", "dose_response", "configuration",
    "generation_manifests",
)

#: protocols/final_pairing/v1/discovery_document_generation_binding.json,
#: v1.1.0, commit 40061b65d02545dfe88775e3f8de2cc17bfc74c6 -- binds every
#: discovery document to the per-direction generation manifest(s) and
#: selection record(s) that produced it.
GENERATION_BINDING_PROTOCOL_PATH = "protocols/final_pairing/v1/discovery_document_generation_binding.json"
GENERATION_BINDING_PROTOCOL_VERSION = "final-pairing-discovery-generation-binding/1.1.0"
GENERATION_BINDING_PROTOCOL_COMMIT = "40061b65d02545dfe88775e3f8de2cc17bfc74c6"
#: ManifestReference.protocol_path/protocol_sha256 consts, from the SAME
#: frozen one-allocation protocol `final_pairing_one_allocation_generation`
#: already pins -- mirrored here (never imported) since that module must
#: not import Lodestar-adjacent code and this module must not import a
#: GPU-stage module merely for two string constants.
_ONE_ALLOCATION_PROTOCOL_PATH = "protocols/final_pairing/v1/one_allocation_dose_generation.json"
_ONE_ALLOCATION_PROTOCOL_SHA256 = "sha256:bd1974b4c44802fa7a49fb7a4ed65df78a9ba66cdca78bb6fc0da69cf42252cf"


def _sha256_of_file(path: str | Path) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_manifest_reference(manifest_path: str | Path, *, computed_at_commit: str) -> dict[str, Any]:
    """A `ManifestReference` (discovery_document_generation_binding.json
    v1.1.0): `source_sha256` is MEASURED here from the manifest's actual
    bytes on disk, never copied from the manifest's own self-declared
    `manifest_sha256` field (that would be circular -- "self-hash-only" is
    one of the ruling's own named prohibited shortcuts). `computed_at_
    commit` is the real git commit that carries those exact bytes,
    supplied by the caller (this function performs no git I/O of its
    own -- it does not invent or look up a commit)."""
    return {
        "source_path": str(manifest_path),
        "source_sha256": _sha256_of_file(manifest_path),
        "computed_at_commit": computed_at_commit,
        "protocol_path": _ONE_ALLOCATION_PROTOCOL_PATH,
        "protocol_sha256": _ONE_ALLOCATION_PROTOCOL_SHA256,
    }


def build_selection_record_reference(
    selection_record_path: str | Path, *, selection_commit: str, confirmation_judging_commit: str,
) -> dict[str, Any]:
    """A `SelectionRecordReference` (discovery_document_generation_binding.json
    v1.1.0): `source_sha256` MEASURED from the selection record's actual
    bytes, never copied."""
    return {
        "source_path": str(selection_record_path),
        "source_sha256": _sha256_of_file(selection_record_path),
        "selection_commit": selection_commit,
        "confirmation_judging_commit": confirmation_judging_commit,
    }


def _validate_generation_binding_nullity(
    directions: dict[str, Any], generation_manifests: dict[str, Any | None], selection_records: dict[str, Any | None],
) -> None:
    expected_keys = {"amplify", "suppress"}
    if set(generation_manifests) != expected_keys:
        raise ValueError(f"generation_manifests must have exactly the keys {expected_keys}, got {set(generation_manifests)}")
    if set(selection_records) != expected_keys:
        raise ValueError(f"selection_records must have exactly the keys {expected_keys}, got {set(selection_records)}")
    if all(generation_manifests[d] is None for d in expected_keys):
        raise ValueError("generation_manifests cannot have both amplify and suppress null -- nothing would be promotable")
    for d in expected_keys:
        direction_published = directions.get(d) is not None
        manifest_present = generation_manifests[d] is not None
        if direction_published != manifest_present:
            raise ValueError(
                f"generation_manifests[{d!r}] nullity ({manifest_present}) must mirror "
                f"calibration.directions[{d!r}] nullity ({direction_published})"
            )
        selection_present = selection_records[d] is not None
        if manifest_present != selection_present:
            raise ValueError(
                f"selection_records[{d!r}] nullity ({selection_present}) must mirror "
                f"generation_manifests[{d!r}] nullity ({manifest_present})"
            )

#: Mirrors `concept_bundle_publish.NOOP_JUDGE_MODELS` (never imported --
#: that package does not exist on this branch). Checked here so a caller
#: mistake fails in THIS process with a clear message, not only after a
#: subprocess round-trip to Engineer 3's validator.
NOOP_JUDGE_MODELS: tuple[str, ...] = ("none", "noop", "no-op", "identity")

#: A STATIC SNAPSHOT of Engineer 3's `accepted_input_schema()`, captured
#: 2026-08-13 from a clean worktree of `eng3/concept-bundle` at ac9ea40
#: (schema v1.3). NON-GATING, defense-in-depth only: this snapshot never
#: decides submission compatibility by itself. It exists so the standalone
#: preflight (and anything else that must run OFFLINE, e.g. a Tamia compute
#: node with no internet and no eng3/concept-bundle checkout) can still do a
#: real, non-fabricated structural check without a live worktree. The
#: GATING decision is `run_gating_report_with_eng3` below, run against a
#: live worktree -- never this.
STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT = "ac9ea40aec0f52cb099c48eae14b3384fc51e85a"
STATIC_ENG3_SCHEMA_SNAPSHOT_PATH = "tests/fixtures/eng3_concept_bundle/accepted_input_schema_ac9ea40.json"


def reconcile_against_static_snapshot(repo_root: str | Path, produced_document: dict[str, Any]) -> dict[str, Any]:
    """Offline, NON-GATING reconciliation against the committed STATIC
    SNAPSHOT (see `STATIC_ENG3_SCHEMA_SNAPSHOT_PATH` above), never a live
    worktree -- this is what makes the check runnable on an offline Tamia
    compute node. It decides nothing about submission compatibility on its
    own ("No static snapshot may decide submission compatibility"): it is
    defense-in-depth only, a cheap early check before the real,
    LIVE `run_gating_report_with_eng3` run against a current
    eng3/concept-bundle checkout, which IS the gating decision. This is
    necessarily a snapshot in time: if `eng3/concept-bundle` moves,
    re-capture it and re-run the live commands -- this function's result
    is provisional until that's done, and says so in its own output."""
    snapshot_path = Path(repo_root) / STATIC_ENG3_SCHEMA_SNAPSHOT_PATH
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    missing_root_fields = [f for f in ROOT_REQUIRED_FIELDS if f not in produced_document]
    version_agrees = snapshot.get("schema_version") == DISCOVERY_SCHEMA_VERSION
    return {
        "gating": False,
        "snapshot_path": str(snapshot_path),
        "snapshot_commit": STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT,
        "snapshot_schema_version": snapshot.get("schema_version"),
        "producer_schema_version": DISCOVERY_SCHEMA_VERSION,
        "schema_version_agrees": version_agrees,
        "missing_root_fields": missing_root_fields,
        "compatible": version_agrees and not missing_root_fields,
        "caveat": (
            "NON-GATING structural, offline, root-field-only check against a point-in-time "
            "snapshot -- not a substitute for the live run_gating_report_with_eng3 run against a "
            "current eng3/concept-bundle checkout, which is the actual submission-gating decision"
        ),
    }


def build_direction_block(
    *, operation: str, feature_indices: list[int], unit: str | None = None, unit_source: str | None = None,
    strengths: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Builds one `calibration.directions.<name>` block, ENFORCING the
    ablate/clamp shape rule rather than trusting the caller: ablate
    (Suppress's operation) carries no `unit`/`unit_source`/`strengths` and
    every target's weight is exactly 1.0 ("Suppress HIGH is ABLATE with no
    magnitude, unit, or unit_source and weights exactly 1.0"); clamp
    requires all three. Raises on a caller attempting the wrong shape for
    the given operation, rather than silently dropping or defaulting
    anything."""
    if operation not in ("clamp", "ablate"):
        raise ValueError(f"operation must be 'clamp' or 'ablate', got {operation!r}")
    if operation == "ablate":
        if unit is not None or unit_source is not None or strengths is not None:
            raise ValueError(
                "an ablate direction must carry no unit/unit_source/strengths -- ablation has no "
                "dose, so there is nothing for any of the three to describe"
            )
        return {
            "operation": "ablate",
            "targets": [{"feature_idx": i, "weight": 1.0} for i in feature_indices],
        }
    if unit is None or unit_source is None or strengths is None:
        raise ValueError("a clamp direction requires unit, unit_source, and strengths, all non-None")
    if sorted(strengths) != ["high", "low", "medium"]:
        raise ValueError(f"strengths must have exactly the keys low/medium/high, got {sorted(strengths)}")
    return {
        "operation": "clamp",
        "targets": [{"feature_idx": i, "weight": 1.0} for i in feature_indices],
        "unit": unit, "unit_source": unit_source, "strengths": dict(strengths),
    }


def _gate_entries_from_grid_ab_c(
    gate_ab_results: list[dict], gate_c_results: list[dict],
) -> list[dict[str, Any]]:
    """Translates this runner's own `GateABResult`/`GateCResult` dicts
    (already computed, never re-derived here) into
    `causal_validation.gates` entries -- one per (gate, family, locale)
    cell, `status` is 'pass' or 'fail' (never 'not_run': this function is
    only ever called with cells that were actually evaluated), `evidence`
    is a short human-readable statistic string, never a placeholder."""
    entries: list[dict[str, Any]] = []
    for r in gate_ab_results:
        entries.append({
            "gate": "G-A", "status": "pass" if r["gate_a_passed"] else "fail",
            "family_id": r["family"],
            "evidence": f"separation_auroc={r['separation_auroc']:.4f} locale={r['locale']}",
        })
        entries.append({
            "gate": "G-B", "status": "pass" if r["gate_b_passed"] else "fail",
            "family_id": r["family"],
            "evidence": f"fire_rate={r['fire_rate']:.4f} floor_fraction={r['activation_floor_fraction']:.4f} locale={r['locale']}",
        })
    for r in gate_c_results:
        entries.append({
            "gate": "G-C", "status": "pass" if r["gate_c_passed"] else "fail",
            "family_id": r["family"],
            "evidence": f"near_miss_auroc={r['near_miss_auroc']:.4f} locale={r['locale']}",
        })
    return entries


def _direction_gate_entry(*, direction: str, gate: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {"gate": gate, "status": "pass" if passed else "fail", "direction": direction, "evidence": evidence}


def assemble_discovery_document(
    *,
    run_id: str, code_commit: str, entrypoint: str, host: str, created_at: str,
    model_id: str, model_revision: str, sae_repo_id: str, sae_repo_revision: str,
    sae_id: str, layer: int, release: str, loader_sae_id: str, params_sha256: str | None,
    layer_selection: dict[str, str] | None,
    concept_id: str, hypothesis_source: str,
    search_scope: str, candidate_index: int | None, engineering_index_rediscovery_note: str | None,
    feature_certificate: dict[str, Any],
    subject: list[dict[str, str]],
    calibration_protocol: str, calibrated_by: str, calibrated_at: str,
    directions: dict[str, dict[str, Any] | None],
    positions: str,
    prompt_set_id: str, prompt_set_source_path: str, prompt_set_source_sha256: str,
    prompt_set_source_commit: str, paraphrase_families: list[dict[str, Any]],
    causal_validation_computed_at_commit: str, causal_validation_positions: str,
    gates: list[dict[str, Any]], spot_read: dict[str, Any] | None,
    judge_model: str, judge_rubric_version: str, judge_prompt_version: str,
    dose_response: dict[str, dict[str, Any]],
    configuration_name: str, configuration_completeness: str, configuration_model_n_layers: int,
    configuration_grid_cells_expected: int, configuration_grid_cells_recorded: int,
    generation_manifests: dict[str, dict[str, Any] | None],
    selection_records: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    """Builds the exact `concept_bundle.discovery_input` document (schema
    v1.3, plus the `generation_manifests`/`causal_validation.selection_
    records` binding ratified at `protocols/final_pairing/v1/discovery_
    document_generation_binding.json` v1.1.0, commit 40061b6 -- a MAJOR
    bump Engineer 3 applies the version numeral for; see this module's
    `ROOT_REQUIRED_FIELDS` comment). Every argument is explicit -- nothing
    here is defaulted, guessed, or read from a clock or the environment.
    `generation_manifests`/`selection_records` are `{"amplify": ...|None,
    "suppress": ...|None}` -- build each non-null entry with `build_
    manifest_reference`/`build_selection_record_reference` above; nullity
    must mirror `directions`' nullity exactly (enforced below). Raises via
    plain `KeyError`/`TypeError`/`ValueError` on a caller mistake; the real
    acceptance check is Engineer 3's own `validate_discovery`/`dose-check`,
    run as a separate step (`run_gating_report_with_eng3` below), not
    re-implemented here."""
    if judge_model.strip().lower() in NOOP_JUDGE_MODELS:
        raise ValueError(
            f"judge_model {judge_model!r} is a no-op judge identity ({NOOP_JUDGE_MODELS}) -- G-D/G-E "
            f"are judged gates, and a no-op identity records that no judge ran, which is refused rather "
            f"than shipped as a judged result"
        )
    _validate_generation_binding_nullity(directions, generation_manifests, selection_records)
    document: dict[str, Any] = {
        "discovery_schema_version": DISCOVERY_SCHEMA_VERSION,
        "run": {
            "run_id": run_id, "code_commit": code_commit,
            "entrypoint": entrypoint, "host": host, "created_at": created_at,
        },
        "pairing": {
            "model_id": model_id, "model_revision": model_revision,
            "sae_repo_id": sae_repo_id, "sae_repo_revision": sae_repo_revision,
            "sae_id": sae_id, "layer": layer,
            "release": release, "loader_sae_id": loader_sae_id, "params_sha256": params_sha256,
        },
        "concept": {"concept_id": concept_id, "hypothesis_source": hypothesis_source},
        "discovery": {
            "rediscovered_in_this_run": True, "search_scope": search_scope,
            "inherited_from_legacy": False,
        },
        "validation": dict(feature_certificate),
        "subject": [dict(s) for s in subject],
        "calibration": {
            "protocol": calibration_protocol, "calibrated_by": calibrated_by,
            "calibrated_at": calibrated_at,
            "directions": {name: (None if value is None else dict(value)) for name, value in directions.items()},
        },
        "positions": positions,
        "prompt_set": {
            "prompt_set_id": prompt_set_id, "source_path": prompt_set_source_path,
            "source_sha256": prompt_set_source_sha256, "source_commit": prompt_set_source_commit,
            "paraphrase_families": [dict(f) for f in paraphrase_families],
        },
        "causal_validation": {
            "prompt_set_commit": prompt_set_source_commit,
            "computed_at_commit": causal_validation_computed_at_commit,
            "positions": causal_validation_positions,
            "gates": [dict(g) for g in gates],
            "judge": {
                "model": judge_model, "rubric_version": judge_rubric_version,
                "prompt_version": judge_prompt_version,
            },
            "selection_records": {
                name: (None if value is None else dict(value)) for name, value in selection_records.items()
            },
        },
        "dose_response": {name: dict(value) for name, value in dose_response.items()},
        "configuration": {
            "name": configuration_name, "completeness": configuration_completeness,
            "model_n_layers": configuration_model_n_layers,
            "grid_cells_expected": configuration_grid_cells_expected,
            "grid_cells_recorded": configuration_grid_cells_recorded,
        },
        "generation_manifests": {
            name: (None if value is None else dict(value)) for name, value in generation_manifests.items()
        },
    }
    if layer_selection is not None:
        document["pairing"]["layer_selection"] = dict(layer_selection)
    if candidate_index is not None:
        document["discovery"]["candidate_index"] = candidate_index
    if engineering_index_rediscovery_note is not None:
        document["discovery"]["engineering_index_rediscovery_note"] = engineering_index_rediscovery_note
    if spot_read is not None:
        document["causal_validation"]["spot_read"] = dict(spot_read)
    return document


def producer_schema_declaration() -> dict[str, Any]:
    """A hand-authored schema declaration in the SAME shape as Engineer 3's
    own `accepted_input_schema()`, describing what THIS assembler actually
    emits -- committed so `concept_bundle_publish.py reconcile-schema
    --producer <this file>` / `gating-report --producer-schema <this file>`
    can be run as a real, field-by-field check, per this task's own
    instruction not to guess at compatibility. Kept field-for-field
    identical to the consumer's own `accepted_input_schema()` wherever this
    producer emits the corresponding block -- verified by a real
    `reconcile-schema`/`gating-report` run (see this module's docstring
    and the closing report)."""
    return {
        "schema_id": "concept_bundle.discovery_input",
        "schema_version": DISCOVERY_SCHEMA_VERSION,
        "status": (
            "ENGINEER 1 PRODUCER DECLARATION -- schema+configuration+judge fields ratified against ac9ea40's "
            "reconcile-schema/gating-report; generation_manifests/selection_records added per discovery_document_"
            "generation_binding.json v1.1.0 (commit 40061b6), pending Engineer 3's consumer update"
        ),
        "objects": {
            "<root>": {"required": list(ROOT_REQUIRED_FIELDS)},
            "run": {"required": ["run_id", "code_commit", "entrypoint", "host", "created_at"]},
            "pairing": {
                "required": ["model_id", "model_revision", "sae_repo_id", "sae_repo_revision", "sae_id",
                             "layer", "release", "loader_sae_id", "params_sha256"],
                "optional": ["layer_selection"],
                "layer_selection": {"required": ["selected_by", "rationale", "recorded_in"]},
            },
            "concept": {"required": ["concept_id", "hypothesis_source"]},
            "discovery": {
                "required": ["rediscovered_in_this_run", "search_scope", "inherited_from_legacy"],
                "optional": ["candidate_index", "candidate_rank", "engineering_index_rediscovery_note"],
            },
            "validation": {
                "required": ["feature_index", "concept_id", "specificity", "sensitivity",
                             "cross_lingual_firing", "selectivity", "probe", "verdict", "verdict_basis"],
            },
            # `subject` is described informally by the consumer's own
            # `accepted_input_schema()` (a "type" string, not a "required"
            # list) -- matched here rather than adding requireds the
            # consumer's own declaration does not recognize.
            "subject": {"type": "array of {content_hash, location, role}"},
            "calibration": {
                "required": ["protocol", "calibrated_by", "calibrated_at", "directions"],
                "directions": {"required": ["amplify", "suppress"]},
                "<direction>": {"required": ["operation", "targets"]},
            },
            "positions": {"enum": ["all", "generated_only"]},
            "prompt_set": {
                "required": ["prompt_set_id", "source_path", "source_sha256", "source_commit", "paraphrase_families"],
            },
            "causal_validation": {
                "required": ["prompt_set_commit", "computed_at_commit", "positions", "gates", "judge",
                             "selection_records"],
                "optional": ["spot_read", "generated_only_diagnostic"],
                "judge": {"required": ["model", "rubric_version", "prompt_version"]},
                "spot_read": {"required": ["approved_by", "approved_at", "note", "sampled_generations"]},
                "selection_records": {
                    "required": ["amplify", "suppress"],
                    "value": "null, or a SelectionRecordReference",
                    "SelectionRecordReference": {
                        "required": ["source_path", "source_sha256", "selection_commit", "confirmation_judging_commit"],
                    },
                },
            },
            "dose_response": {"required": ["computed_at_commit", "observations"]},
            "configuration": {
                "required": ["name", "completeness", "model_n_layers",
                             "grid_cells_expected", "grid_cells_recorded"],
            },
            "generation_manifests": {
                "required": ["amplify", "suppress"],
                "value": "null, or a ManifestReference",
                "ManifestReference": {
                    "required": ["source_path", "source_sha256", "computed_at_commit",
                                 "protocol_path", "protocol_sha256"],
                },
            },
        },
    }


class Eng3ConsumerUnavailable(RuntimeError):
    """Raised when no checked-out copy of `eng3/concept-bundle` is available
    to reconcile against -- this file never fabricates a "would probably
    pass" result in that case."""


def reconcile_producer_output_with_eng3(
    document_path: str | Path, *, eng3_worktree: str | Path, python_executable: str = "python",
) -> dict[str, Any]:
    """Runs Engineer 3's REAL `scripts/concept_bundle_publish.py validate
    --discovery <document_path>` as a subprocess against `eng3_worktree`
    (a checked-out copy of branch `eng3/concept-bundle` -- never this
    branch, since the package it imports does not exist here). Returns
    `{"exit_code": int, "stdout": str, "stderr": str}` verbatim; this
    function does not parse or reinterpret the verdict -- the exit code
    and printed JSON ARE the verdict."""
    import subprocess

    eng3_worktree = Path(eng3_worktree)
    script = eng3_worktree / "scripts" / "concept_bundle_publish.py"
    if not script.is_file():
        raise Eng3ConsumerUnavailable(f"no concept_bundle_publish.py found under {eng3_worktree}")
    proc = subprocess.run(
        [python_executable, str(script), "validate", "--discovery", str(document_path), "--git-root", str(eng3_worktree)],
        capture_output=True, text=True,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def reconcile_schema_with_eng3(
    schema_path: str | Path, *, eng3_worktree: str | Path, python_executable: str = "python",
) -> dict[str, Any]:
    """Runs Engineer 3's REAL `scripts/concept_bundle_publish.py
    reconcile-schema --producer <schema_path>` as a subprocess. Superseded
    as the gating decision by `run_gating_report_with_eng3` below (which
    ALSO checks a genuinely emitted document and the identity artifact's
    open items) -- kept because it is still useful as a fast, schema-only
    check while iterating on `producer_schema_declaration()`."""
    import subprocess

    eng3_worktree = Path(eng3_worktree)
    script = eng3_worktree / "scripts" / "concept_bundle_publish.py"
    if not script.is_file():
        raise Eng3ConsumerUnavailable(f"no concept_bundle_publish.py found under {eng3_worktree}")
    proc = subprocess.run(
        [python_executable, str(script), "reconcile-schema", "--producer", str(schema_path)],
        capture_output=True, text=True,
    )
    return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def run_gating_report_with_eng3(
    *, producer_schema_path: str | Path, producer_output_path: str | Path,
    eng3_worktree: str | Path, registry_root: str | Path | None = None, python_executable: str = "python",
) -> dict[str, Any]:
    """Runs Engineer 3's REAL `scripts/concept_bundle_publish.py
    gating-report --producer-schema <...> --producer-output <...>` as a
    subprocess against `eng3_worktree`. THIS IS THE SUBMISSION-GATING
    DECISION -- "No static snapshot may decide submission compatibility":
    `gating-report` checks the producer schema AND a genuinely emitted
    document together, AND the identity artifact's own open items, and its
    own `submission_may_proceed` field is exactly what this function's
    caller must gate on (parsed from stdout here, not left to the caller
    to re-derive from a raw dump). Raises `Eng3ConsumerUnavailable` if no
    checked-out copy of `eng3/concept-bundle` is available -- this
    function never fabricates a "would probably pass" result in that
    case, and `reconcile_against_static_snapshot` is NOT a substitute for
    it."""
    import json as _json
    import subprocess

    eng3_worktree = Path(eng3_worktree)
    script = eng3_worktree / "scripts" / "concept_bundle_publish.py"
    if not script.is_file():
        raise Eng3ConsumerUnavailable(f"no concept_bundle_publish.py found under {eng3_worktree}")
    command = [
        python_executable, str(script), "gating-report",
        "--producer-schema", str(producer_schema_path),
        "--producer-output", str(producer_output_path),
    ]
    if registry_root is not None:
        command += ["--registry-root", str(registry_root)]
    proc = subprocess.run(command, capture_output=True, text=True)
    report: dict[str, Any] | None
    try:
        report = _json.loads(proc.stdout) if proc.stdout.strip() else None
    except _json.JSONDecodeError:
        report = None
    return {
        "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
        "report": report,
        "submission_may_proceed": bool(report and report.get("submission_may_proceed")),
    }
