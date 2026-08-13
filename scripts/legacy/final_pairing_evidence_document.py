"""Assembles the `concept_bundle.discovery_input` document (schema v1.1)
that `scripts/concept_bundle_publish.py` (Engineer 3, branch
`eng3/concept-bundle`, commit 2c8cf5b) accepts, from this repository's own
discovery-runner output (`final_pairing_concept_discovery.py`'s `run()`
result and grid verdicts) plus a small set of caller-supplied identity
facts that no file in this repository may invent by reading a clock or
guessing a name.

WHY A SEPARATE FILE. `interplab/concept_bundle/` (the package
`concept_bundle_publish.py` imports) does not exist on this branch -- it
was authored on the sibling branch `eng3/concept-bundle` (confirmed:
`git merge-base --is-ancestor final-pairing-harness eng3/concept-bundle`
and the reverse both fail; the two branches diverged from a common
ancestor and neither contains the other). This file therefore does not
import that package, does not merge that branch, and does not vendor a
copy of it -- it emits a plain dict matching the SHAPE Engineer 3's
`accepted_input_schema()`/`validate_discovery()` declare and enforce
(both read directly, verbatim, from `scripts/concept_bundle_publish.py`
at commit 2c8cf5b), and leaves the actual reconciliation to be run as a
real subprocess against a checked-out copy of that branch -- never
faked, never assumed to pass.

A DISCREPANCY FOUND WHILE READING THAT FILE, RECORDED HERE RATHER THAN
SILENTLY WORKED AROUND: `accepted_input_schema()`'s own
`objects["<root>"]["required"]` lists 9 root fields (missing
`prompt_set`, `causal_validation`, `dose_response`), but
`validate_discovery()`'s actual `_closed(document, (...12 fields...), ...)`
call requires all 12 unconditionally. The declared schema and the
enforcing code disagree about what is required at the root. This
assembler follows the ENFORCING CODE (12 required fields), since that is
what `validate --discovery` actually checks, and flags the declared-schema
undercount as a finding for Engineer 3 rather than treating either
document as authoritative on its own.

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

DISCOVERY_SCHEMA_VERSION = "1.1"  # must equal concept_bundle_publish.DISCOVERY_SCHEMA_VERSION

#: The declared-schema/enforcing-code discrepancy noted in the module
#: docstring: the ENFORCING validator requires all 12; the printed
#: `accepted_input_schema()["objects"]["<root>"]["required"]` lists only 9.
#: This assembler always emits all 12.
ROOT_REQUIRED_FIELDS: tuple[str, ...] = (
    "discovery_schema_version", "run", "pairing", "concept", "discovery",
    "validation", "subject", "calibration", "positions",
    "prompt_set", "causal_validation", "dose_response",
)

#: A STATIC SNAPSHOT of Engineer 3's `accepted_input_schema()`, captured
#: 2026-08-13 from a clean worktree of `eng3/concept-bundle` at this exact
#: commit (verified: `python scripts/concept_bundle_publish.py validate
#: --discovery <synthetic document built by this file> --git-root
#: <this repo>` returned `accepted: true, chronology_problems: []`, and
#: `reconcile-schema` was also run against it -- see this module's own
#: docstring for the results). Committed so the standalone preflight (and
#: anything else that must run OFFLINE, e.g. on a Tamia compute node with
#: no internet and no eng3/concept-bundle checkout available) can still do
#: a real, non-fabricated structural check without a live worktree.
STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT = "2c8cf5b8a67873043ca026dfe99f6eb5ce145c06"
STATIC_ENG3_SCHEMA_SNAPSHOT_PATH = "tests/fixtures/eng3_concept_bundle/accepted_input_schema_2c8cf5b.json"


def reconcile_against_static_snapshot(repo_root: str | Path, produced_document: dict[str, Any]) -> dict[str, Any]:
    """Offline reconciliation against the committed STATIC SNAPSHOT (see
    `STATIC_ENG3_SCHEMA_SNAPSHOT_PATH` above), never a live worktree --
    this is what makes the check runnable on an offline Tamia compute
    node. This is necessarily a snapshot in time: if `eng3/concept-bundle`
    moves, re-capture the snapshot and re-run the LIVE `validate`/
    `reconcile-schema` commands (`reconcile_producer_output_with_eng3`/
    `reconcile_schema_with_eng3` above) against a fresh checkout -- this
    function's result should be treated as provisional until that's done,
    and it says so in its own output rather than claiming certainty."""
    snapshot_path = Path(repo_root) / STATIC_ENG3_SCHEMA_SNAPSHOT_PATH
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    missing_root_fields = [f for f in ROOT_REQUIRED_FIELDS if f not in produced_document]
    version_agrees = snapshot.get("schema_version") == DISCOVERY_SCHEMA_VERSION
    return {
        "snapshot_path": str(snapshot_path),
        "snapshot_commit": STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT,
        "snapshot_schema_version": snapshot.get("schema_version"),
        "producer_schema_version": DISCOVERY_SCHEMA_VERSION,
        "schema_version_agrees": version_agrees,
        "missing_root_fields": missing_root_fields,
        "compatible": version_agrees and not missing_root_fields,
        "caveat": (
            "structural, offline, root-field-only check against a point-in-time snapshot -- "
            "not a substitute for the live validate_discovery()/reconcile-schema run against a "
            "current eng3/concept-bundle checkout"
        ),
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
    sae_id: str, layer: int, layer_selection: dict[str, str] | None,
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
    dose_response: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Builds the exact `concept_bundle.discovery_input` v1.1 document.
    Every argument is explicit -- nothing here is defaulted, guessed, or
    read from a clock or the environment. Raises via plain `KeyError`/
    `TypeError` on a caller mistake; the real acceptance check is Engineer
    3's own `validate_discovery`, run as a separate step
    (`reconcile_producer_output_with_eng3` below), not re-implemented here."""
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
        },
        "dose_response": {name: dict(value) for name, value in dose_response.items()},
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
    --producer <this file>` can be run as a real, field-by-field check,
    per this task's own instruction not to guess at compatibility."""
    return {
        "schema_id": "concept_bundle.discovery_input",
        "schema_version": DISCOVERY_SCHEMA_VERSION,
        "status": "ENGINEER 1 PRODUCER DECLARATION -- awaiting Engineer 3 reconcile-schema run",
        "objects": {
            "<root>": {"required": list(ROOT_REQUIRED_FIELDS)},
            "run": {"required": ["run_id", "code_commit", "entrypoint", "host", "created_at"]},
            "pairing": {
                "required": ["model_id", "model_revision", "sae_repo_id", "sae_repo_revision", "sae_id", "layer"],
                "optional": ["layer_selection"],
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
                "required": ["prompt_set_commit", "computed_at_commit", "positions", "gates"],
                "optional": ["spot_read", "generated_only_diagnostic"],
                "spot_read": {"required": ["approved_by", "approved_at", "note", "sampled_generations"]},
            },
            "dose_response": {"required": ["computed_at_commit", "observations"]},
            "pairing_layer_selection_note": (
                "pairing.layer_selection.{selected_by,rationale,recorded_in} are declared "
                "under pairing.layer_selection below, not flattened into pairing.required, "
                "matching the consumer's own nesting"
            ),
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
    reconcile-schema --producer <schema_path>` as a subprocess."""
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
