"""Assembles the `concept_bundle.discovery_input` document (schema v5.0)
that `scripts/concept_bundle_publish.py` (Engineer 3, branch
`eng3/concept-bundle`, currently at commit 047fe17 -- "Represent both
frozen Qwen configurations end to end", schema 5.0)
accepts, from this repository's own discovery-runner output
(`final_pairing_concept_discovery.py`'s `run()` result and grid
verdicts) plus a small set of caller-supplied identity facts that no
file in this repository may invent by reading a clock or guessing a
name.

Neither ff2a565, 3aff107, nor 047fe17 is an ancestor of this branch
(`final-pairing-harness`) -- confirmed via `git merge-base --is-
ancestor` in both directions, both fail, for both commits. Every fact
this file relies on about the current 047fe17 consumer was read directly out of
`D:/devcache/wt/concept-bundle` (a real, separate worktree of
`eng3/concept-bundle` checked out AT that commit), never assumed from an
older commit's shape or copied from a stale excerpt fixture.

LINEAGE: 2c8cf5b (schema v1.1) -> d833ba4/ac9ea40 (schema v1.3: added the
root-level `configuration` block, `pairing.release`/`loader_sae_id`/
`params_sha256`, and a required `causal_validation.judge` block) ->
67ad4ef (schema v2.0: `generation_manifests` becomes a NEW REQUIRED
root-level field, one `ManifestReference | null` per calibrated
direction, MAJOR bump because a zero-legacy-corpus discovery runner has
no prior document shape to stay backward compatible with) -> 2003406
(schema v2.0 UNCHANGED at the document root; the referenced generation
MANIFEST's own shape -- built by `final_pairing_one_allocation_
generation.py`, never embedded in the document itself -- gained the
`generation_settings.json` extension fields (`generation_kwargs`,
`chat_template_identity`, `locales_complete`, `generation_settings_path`/
`_version`/`_sha256`, `causal_order_position`, `skipped_for_gate_
failure`) verified directly against `concept_bundle_publish.py`'s own
`MANIFEST_FIELDS`/`MANIFEST_FILE_FIELDS` tuples at 2003406) -> ff2a565
(schema v2.0 -> v3.0, the SECOND MAJOR bump, consuming the manifest-
immutability correction, commit 2dc9e338c12db1c1f3939a9f709f8af816ad8272,
sha256 4a2affcfa40c6d12a68f223eee6455d3d333cfcd2d2990f881efb64701946222,
already applied to this repo's own manifest emitter/verifier at commit
7d7985d: `generation_manifests.manifest_file_required` REMOVES
`selection_status` (STRUCK, refused on sight), `generation_manifests.
manifest_optional.inventory_stage` is new (const `PRE_SELECTION`), and
`causal_validation.selection_records` gains a required CLOSED content
schema (`content_required`: `manifest_sha256`/`outcome`/`selected`/
`unselected`, `content_rules.additionalProperties: false`) for the FILE
each `SelectionRecordReference.source_path` points at -- this document
producer does not change shape for ANY of that: it only ever carries a
`ManifestReference`/`SelectionRecordReference` (a path + a measured hash
to the referenced file), never the manifest's or selection record's own
internal fields, per this module's own "WHAT THIS FILE DOES NOT DO"
section below. DISCLOSED, NOT SILENTLY FIXED: `final_pairing_judge_cli.
write_selection_record`'s own selection-record FILE CONTENT shape
(`{protocol_version, protocol_sha256, selections: [...]}`, each entry
`{concept_id, pairing_id, direction, status, selected, unselected}`) does
NOT match ff2a565's (UNCHANGED at 3aff107) closed `content_required`/
`content_rules` shape (`{manifest_sha256, outcome, selected, unselected}`,
one object per file) -- that is Deliverable B (local judging), untouched
per every prior dispatch's own instruction that it does not block GPU
submission; this gap is real and will need closing before a selection
record can actually promote under schema 5.0, but fixing it is out of
this file's scope.

`ac9ea40`/2003406 both: separate `pairing.params_sha256` (MEASURED,
emitted here) from the identity artifact's own `params_expected_sha256`
(never emitted by a producer -- refused by name if it is).

-> 3aff107 (schema v3.0 -> v5.0, consuming THREE frozen artifacts in one
pass -- causal_dose_grid.json v1.0.0/commit c43a976, mixed_operation_
publication.json v1.1.0/commit 6e3f4be, suppress_null_disposition.json
v1.0.0/commit cb0aca8): `generation_manifests.manifest_required` gains
`dose_grid` (manifest-level, five closed point objects) and
`causal_dose_grid_path`/`_version`/`_sha256`; the root gains a
CONDITIONAL `suppress_disposition` field, required iff `calibration.
directions.suppress` is null and prohibited iff it is not. See this
module's "CAUSAL_DOSE_GRID.JSON"/"SUPPRESS_NULL_DISPOSITION.JSON"
paragraphs below for the full detail of each.

CAUSAL_DOSE_GRID.JSON (protocols/final_pairing/v1/causal_dose_grid.json,
commit c43a976): freezes canonical dose_ids ("A1".."A5"/"S1".."S5")
replacing the prior float-derived `files[].dose` labels ("0.5x", "ABLATE")
in the generation manifest `final_pairing_one_allocation_generation.py`
produces. CORRECTED (was: "there is currently NO schema-required site to
bind causal_dose_grid.json's identity into" -- true at ff2a565/schema
3.0, no longer true): schema 5.0 (commit 3aff107) adds a manifest-level
`dose_grid` (five closed point objects) plus `causal_dose_grid_path`/
`_version`/`_sha256` to `generation_manifests.manifest_required` --
`final_pairing_one_allocation_generation.write_generation_manifest` now
emits all four (`_dose_grid_manifest_points`, `CAUSAL_DOSE_GRID_
PROTOCOL_PATH`/`_VERSION`/`_SHA256`), checked point-by-point against the
SAME frozen artifact `validate_causal_dose_grid_protocol_hash` already
hash-pins. This document producer never constructs the manifest itself
(only references it via `build_manifest_reference`), so this file's own
change is confined to what `producer_schema_declaration()` documents
about that bound file's shape.

MIXED_OPERATION_PUBLICATION.JSON (protocols/final_pairing/v1/mixed_
operation_publication.json, v1.1.0, commit 6e3f4be, supersedes v1.0.0/
cddd9a5): S5/ABLATE is never eligible to occupy low/medium/high in a
PUBLISHED Suppress direction (`build_direction_block`'s docstring above
has the full correction of this file's own former false "Suppress HIGH
is ABLATE" claim); enforced upstream, at selection time, in
`final_pairing_judge_cli.build_selected_record` -- by the time a
SELECTED record reaches this producer, its `selected` dict structurally
cannot name the ablate dose_id. This file performs no additional check
of its own, since `build_direction_block`'s ablate/clamp split already
makes a mixed CLAMP+ABLATE triple unrepresentable regardless.

SUPPRESS_NULL_DISPOSITION.JSON (protocols/final_pairing/v1/suppress_
null_disposition.json, v1.0.0, commit cb0aca8, extends mixed_operation_
publication v1.1.0): IMPLEMENTED (schema 5.0, commit 3aff107,
D:/devcache/wt/concept-bundle -- the schema commit this ruling was
pending on has now landed). When Suppress publishes `null` (fewer than
three of S1..S4 clear G-E, whether or not S5/ABLATE did), the document
must carry a root-level `suppress_disposition` object (`{reason,
ablation_cleared_ge}`, required iff `calibration.directions.suppress` is
null, PROHIBITED iff non-null) and NO G-E gate -- `ablation_cleared_ge`
is descriptive metadata, never a gate. `build_suppress_disposition`
builds the object; `assemble_discovery_document` enforces the required-
iff/prohibited-iff nullity (`_validate_suppress_disposition_nullity`),
re-validates its shape defensively even if the caller already used the
builder (`_validate_suppress_disposition`), and refuses any `gates`
entry naming `"G-E"` when suppress is null (`_validate_no_ge_gate_when_
suppress_null`) -- with suppress null nothing about suppression is
published, so a G-E gate has nothing to attach to.

SCHEMA 3.0 -> 5.0 (commit ff2a565 -> commit 3aff107, D:/devcache/wt/
concept-bundle): ff2a565 is still NOT an ancestor of this branch; 3aff107
likewise is not (git merge-base --is-ancestor fails in both directions
for both commits) -- every fact this file relies on about 3aff107 was
read directly out of that worktree, checked out AT that commit, never
assumed from ff2a565's shape or copied from a stale excerpt. The bump
carries TWO changes, both consumed here: (1) dose-grid canonicalization
at the MANIFEST level -- `generation_manifests.manifest_required` gains
`dose_grid` (a five-point array, `final_pairing_one_allocation_
generation._dose_grid_manifest_points`) plus `causal_dose_grid_path`/
`_version`/`_sha256` binding the manifest to the exact frozen artifact
identity; this document producer never constructs the manifest itself
(only references it), so this file changes only in what `producer_
schema_declaration()` documents about that bound file's shape, never in
what THIS document's own root carries. (2) the root-level `suppress_
disposition` conditional field described above. `STATIC_ENG3_SCHEMA_
SNAPSHOT_COMMIT`/`_PATH` now point at 3aff107's real, captured
`discovery_input_schema.json` (kept alongside the ff2a565/2003406/
ac9ea40 snapshots, never deleted, as the historical record).

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

DISCOVERY_SCHEMA_VERSION = "5.0"  # verified equal to concept_bundle_publish.DISCOVERY_SCHEMA_VERSION at commit 047fe17

#: All 14 root fields required per `protocols/final_pairing/v1/discovery_
#: document_generation_binding.json` v1.1.0 (commit 40061b6) and confirmed
#: verbatim against `conformance/concept_bundle/discovery_input_schema.json`
#: schema 3.0's own `objects["<root>"]["required"]` at Engineer 3's real
#: commit ff2a565 (`D:/devcache/wt/concept-bundle`) -- UNCHANGED from
#: schema 2.0's root list (2.0 -> 3.0 changed fields WITHIN
#: `generation_manifests`/`causal_validation.selection_records`, not the
#: root): `generation_manifests` is the field that bumped 1.3 -> 2.0 ("a
#: new REQUIRED top-level object").
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
#: Mirrors `final_pairing_one_allocation_generation.MANIFEST_REQUIRED_FIELDS`/
#: `MANIFEST_FILE_REQUIRED_FIELDS` (never imported, same reason as the two
#: protocol constants above) -- purely for `producer_schema_declaration()`'s
#: own documentation of the bound manifest FILE's shape (this module never
#: constructs that file, only references it).
_ONE_ALLOCATION_MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id", "source_commit", "configuration", "concept_id", "pairing_id",
    "model_revision", "sae_revision", "release", "loader_sae_id", "scientific_sae_id",
    "params_measured_sha256", "direction", "files", "completeness", "protocol_path", "protocol_sha256",
    "generation_kwargs", "chat_template_identity", "locales_complete",
    "generation_settings_path", "generation_settings_version", "generation_settings_sha256",
    "causal_order_position", "skipped_for_gate_failure", "inventory_stage",
    "dose_grid", "causal_dose_grid_path", "causal_dose_grid_version", "causal_dose_grid_sha256",
)
_ONE_ALLOCATION_MANIFEST_FILE_REQUIRED_FIELDS: tuple[str, ...] = (
    "dose", "purpose", "path", "sha256", "seed", "locale", "prompt_id", "control_ref", "truncated",
)


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
#: 2026-08-14 by reading `conformance/concept_bundle/discovery_input_
#: schema.json` FOR REAL inside a clean worktree of `eng3/concept-bundle`
#: at commit 047fe17 (schema v5.0, configuration-specific Qwen PRIMARY/
#: BACKUP pairing ids and non-null measured hashes) -- superseding the prior
#: 3aff107 and ff2a565 snapshots, kept alongside (never deleted)
#: as the historical record of what schema v3.0 required (as are 2003406
#: and ac9ea40 before it). NON-GATING, defense-in-depth only: this
#: snapshot never decides submission compatibility by itself. It exists
#: so the standalone preflight (and anything else that must run OFFLINE,
#: e.g. a Tamia compute node with no internet and no eng3/concept-bundle
#: checkout) can still do a real, non-fabricated structural check without
#: a live worktree. The GATING decision is `run_gating_report_with_eng3`
#: below, run against a live worktree -- never this.
STATIC_ENG3_SCHEMA_SNAPSHOT_COMMIT = "047fe17e8f771ddc790b1f8369e9dea113d3a513"
STATIC_ENG3_SCHEMA_SNAPSHOT_PATH = "tests/fixtures/eng3_concept_bundle/accepted_input_schema_047fe17.json"


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
    ablate/clamp shape rule rather than trusting the caller: an ablate
    direction carries no `unit`/`unit_source`/`strengths` (every target's
    weight is exactly 1.0) and no low/medium/high dial at all; a clamp
    direction requires `unit`/`unit_source`/`strengths` (three bare-number
    magnitudes), all three. `operation` is ONE value per direction (never
    per-strength) -- this matches the accepted schema exactly as it is,
    at 2003406/ac9ea40/ff2a565 alike (`mixed_operation_publication.json`
    v1.1.0, commit 6e3f4be, WITHDRAWS the earlier, false v1.0.0 instruction
    to move `operation` onto a per-strength Spec).

    CORRECTED (was: "Suppress HIGH is ABLATE with no magnitude, unit, or
    unit_source"): that claim is FALSE and is a hard stop to assert. A
    published Suppress direction is `operation='clamp'` with three CLAMP
    magnitudes drawn from the confirmation doses the selection procedure
    actually chose (normally S1..S4 -- S5/ABLATE is never eligible to
    occupy low/medium/high in a PUBLISHED direction, restricted at
    selection time per `mixed_operation_publication.json`, enforced in
    `final_pairing_judge_cli.build_selected_record`). S1..S4 (CLAMP) and
    S5 (ABLATE) are NOT one continuous magnitude ramp -- S5 is a
    different operation with no magnitude at all, not a further point on
    the same scale. This function's own ablate/clamp split already makes
    a mixed CLAMP+ABLATE triple structurally unrepresentable (an ablate
    direction has no strengths to hold one), which is the accepted
    schema's actual, coherent design, not an oversight. Raises on a
    caller attempting the wrong shape for the given operation, rather
    than silently dropping or defaulting anything."""
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


#: protocols/final_pairing/v1/suppress_null_disposition.json, v1.0.0,
#: commit cb0aca8 -- consumed here for real at schema 5.0 (conformance/
#: concept_bundle/discovery_input_schema.json, commit 3aff107,
#: D:/devcache/wt/concept-bundle): a root-level `suppress_disposition`
#: object, REQUIRED iff `calibration.directions.suppress` is null and
#: PROHIBITED iff it is not -- mirrored here (never imported) from
#: `concept_bundle_publish.SUPPRESS_DISPOSITION_FIELD`/`_FIELDS`/
#: `_REASONS`/`_NULL_REASON`.
SUPPRESS_NULL_DISPOSITION_PROTOCOL_PATH = "protocols/final_pairing/v1/suppress_null_disposition.json"
SUPPRESS_NULL_DISPOSITION_PROTOCOL_VERSION = "final-pairing-suppress-null-disposition/1.0.0"
SUPPRESS_NULL_DISPOSITION_PROTOCOL_COMMIT = "cb0aca8e27bc0cb133ae5c0862af70a52c738e4a"
#: Mirrors `final_pairing_one_allocation_generation.CAUSAL_DOSE_GRID_
#: PROTOCOL_VERSION`/`_COMMIT` (never imported, same reason as the other
#: mirrored protocol constants above) -- purely for `producer_schema_
#: declaration()`'s own informational binding strings.
CAUSAL_DOSE_GRID_INFORMATIONAL_VERSION = "final-pairing-causal-dose-grid/1.0.0"
CAUSAL_DOSE_GRID_INFORMATIONAL_COMMIT = "c43a976785a3a7e2e0fa4c8a9a78e1a33a88d37e"
SUPPRESS_DISPOSITION_FIELD = "suppress_disposition"
#: Closed shape (`additionalProperties: false`): exactly these two keys,
#: never more, never fewer.
SUPPRESS_DISPOSITION_FIELDS: tuple[str, ...] = ("reason", "ablation_cleared_ge")
SUPPRESS_DISPOSITION_REASONS: tuple[str, ...] = ("NOT_ATTEMPTED", "NO_DOSE_CLEARED", "INSUFFICIENT_CLAMP_DOSES")
#: `ablation_cleared_ge` is null IFF `reason` is this value -- a run that
#: generated nothing cannot report whether ablation cleared G-E; under
#: any other reason the run was attempted, so it is a literal bool.
SUPPRESS_DISPOSITION_NULL_REASON = "NOT_ATTEMPTED"


def build_suppress_disposition(*, reason: str, ablation_cleared_ge: bool | None) -> dict[str, Any]:
    """Builds the root-level `suppress_disposition` object -- NOT A GATE:
    "reason"/"ablation_cleared_ge" are descriptive scientific metadata
    (suppress_null_disposition.json v1.0.0, commit cb0aca8): they record
    that a null Suppress direction happened and why, and (when attempted)
    whether full ablation alone cleared G-E, as a FACT, never something
    promotion passes or fails on. `ablation_cleared_ge` is `None` iff
    `reason == "NOT_ATTEMPTED"` (a run that generated nothing cannot
    report whether ablation cleared G-E) and a LITERAL bool otherwise --
    enforced here rather than trusted from the caller, same discipline as
    `build_direction_block`'s ablate/clamp shape check above. Called by
    `assemble_discovery_document`'s caller when `directions["suppress"]`
    is `None`; `assemble_discovery_document` itself re-validates this
    shape defensively (see `_validate_suppress_disposition` below), so a
    caller that hand-built this dict instead of calling this function is
    still caught."""
    if reason not in SUPPRESS_DISPOSITION_REASONS:
        raise ValueError(f"reason must be one of {SUPPRESS_DISPOSITION_REASONS}, got {reason!r}")
    if reason == SUPPRESS_DISPOSITION_NULL_REASON:
        if ablation_cleared_ge is not None:
            raise ValueError(
                f"ablation_cleared_ge must be None when reason is {SUPPRESS_DISPOSITION_NULL_REASON} -- a run "
                f"that generated nothing cannot report whether ablation cleared G-E"
            )
    elif not isinstance(ablation_cleared_ge, bool):
        raise ValueError(
            f"ablation_cleared_ge must be a literal bool when reason is {reason!r}, got {ablation_cleared_ge!r}"
        )
    return {"reason": reason, "ablation_cleared_ge": ablation_cleared_ge}


def _validate_suppress_disposition(suppress_disposition: dict[str, Any]) -> None:
    """SHAPE ONLY -- presence, closure, enum membership, and the
    `ablation_cleared_ge` null_iff rule -- mirroring `concept_bundle_
    publish._validate_suppress_disposition`'s own checks. Never reads a
    well-formed object for a verdict: `suppress_disposition` is
    descriptive metadata, and promotion neither passes nor fails on any
    value here (`SUPPRESS_DISPOSITION_IS_GATING = False` in the real
    consumer)."""
    if not isinstance(suppress_disposition, dict):
        raise ValueError(f"suppress_disposition must be an object, got {type(suppress_disposition).__name__}")
    unknown = sorted(set(suppress_disposition) - set(SUPPRESS_DISPOSITION_FIELDS))
    missing = sorted(set(SUPPRESS_DISPOSITION_FIELDS) - set(suppress_disposition))
    if unknown or missing:
        raise ValueError(
            f"suppress_disposition must have exactly the keys {SUPPRESS_DISPOSITION_FIELDS} -- "
            f"unknown={unknown}, missing={missing}"
        )
    reason = suppress_disposition["reason"]
    if reason not in SUPPRESS_DISPOSITION_REASONS:
        raise ValueError(f"suppress_disposition.reason must be one of {SUPPRESS_DISPOSITION_REASONS}, got {reason!r}")
    cleared = suppress_disposition["ablation_cleared_ge"]
    if reason == SUPPRESS_DISPOSITION_NULL_REASON:
        if cleared is not None:
            raise ValueError(
                f"suppress_disposition.ablation_cleared_ge must be None when reason is "
                f"{SUPPRESS_DISPOSITION_NULL_REASON}, got {cleared!r}"
            )
    elif not isinstance(cleared, bool):
        raise ValueError(
            f"suppress_disposition.ablation_cleared_ge must be a literal bool when reason is {reason!r}, "
            f"got {cleared!r}"
        )


def _validate_suppress_disposition_nullity(
    directions: dict[str, Any], suppress_disposition: dict[str, Any] | None,
) -> None:
    """required IFF `calibration.directions.suppress` is null, PROHIBITED
    iff it is not (suppress_null_disposition.json v1.0.0, commit
    cb0aca8) -- a sometimes-absent field would reintroduce the ambiguity
    it exists to remove: 'suppress was never attempted' could not be
    told from 'the field was omitted'."""
    suppress_published = directions.get("suppress") is not None
    if suppress_published:
        if suppress_disposition is not None:
            raise ValueError(
                "suppress_disposition is present while calibration.directions.suppress is NON-NULL -- it is "
                "required iff suppress is null and PROHIBITED iff it is not (suppress_null_disposition.json "
                "v1.0.0, commit cb0aca8): a disposition beside a published direction would describe a null "
                "that does not exist"
            )
        return
    if suppress_disposition is None:
        raise ValueError(
            "suppress_disposition is required when calibration.directions.suppress is null "
            "(suppress_null_disposition.json v1.0.0, commit cb0aca8) -- a sometimes-absent field would "
            "reintroduce the ambiguity it exists to remove"
        )
    _validate_suppress_disposition(suppress_disposition)


def _validate_no_ge_gate_when_suppress_null(directions: dict[str, Any], gates: list[dict[str, Any]]) -> None:
    """With `suppress` null, nothing about suppression is published, so
    there is nothing for a G-E gate to attach to -- the S5-only finding
    (if any) stays hash-bound in `causal_validation`/the generation
    manifest/the selection record's own `unselected` list, never
    promoted to a gate here (suppress_null_disposition.json v1.0.0,
    commit cb0aca8: "no G-E gate may be emitted when suppress is
    null"). The real consumer's own promotion still blocks on a G-E
    gate attached to a null direction if one somehow appears (THE_G_E_
    GATE_IS_UNCHANGED) -- this producer-side check simply never emits
    one in the first place."""
    if directions.get("suppress") is not None:
        return
    ge_gates = [g for g in gates if g.get("gate") == "G-E"]
    if ge_gates:
        raise ValueError(
            "gates carries a G-E entry while calibration.directions.suppress is null -- with suppress null "
            "nothing about suppression is published, so there is nothing for a G-E gate to attach to "
            "(suppress_null_disposition.json v1.0.0, commit cb0aca8)"
        )


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
    suppress_disposition: dict[str, Any] | None = None,
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
    re-implemented here.

    `suppress_disposition` (schema 5.0, commit 3aff107): build with
    `build_suppress_disposition` above; REQUIRED when `directions["suppress"]`
    is `None`, PROHIBITED otherwise (enforced below, re-validated defensively
    even if the caller already used the builder). Emitted as the document's
    root-level `suppress_disposition` field only in the null-suppress case --
    never a gate, never read by promotion for a verdict. Also enforced here:
    no `gates` entry may name `"G-E"` when `directions["suppress"]` is `None`
    -- with suppress null nothing about suppression is published, so a G-E
    gate has nothing to attach to."""
    if judge_model.strip().lower() in NOOP_JUDGE_MODELS:
        raise ValueError(
            f"judge_model {judge_model!r} is a no-op judge identity ({NOOP_JUDGE_MODELS}) -- G-D/G-E "
            f"are judged gates, and a no-op identity records that no judge ran, which is refused rather "
            f"than shipped as a judged result"
        )
    _validate_generation_binding_nullity(directions, generation_manifests, selection_records)
    _validate_suppress_disposition_nullity(directions, suppress_disposition)
    _validate_no_ge_gate_when_suppress_null(directions, gates)
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
    if suppress_disposition is not None:
        document[SUPPRESS_DISPOSITION_FIELD] = dict(suppress_disposition)
    return document


def build_discovery_document_from_production_run(
    *,
    run_id: str, code_commit: str, entrypoint: str, host: str, created_at: str,
    model_id: str, sae_repo_id: str, model_provenance: dict[str, Any], sae_provenance: dict[str, Any],
    layer: int, layer_selection: dict[str, str] | None,
    concept_id: str, hypothesis_source: str, search_scope: str,
    candidate_index: int | None, engineering_index_rediscovery_note: str | None,
    feature_certificate: dict[str, Any], subject: list[dict[str, str]],
    calibration_protocol: str, calibrated_by: str, calibrated_at: str,
    directions: dict[str, dict[str, Any] | None], positions: str,
    prompt_set_id: str, prompt_set_source_path: str, prompt_set_source_sha256: str,
    prompt_set_source_commit: str, paraphrase_families: list[dict[str, Any]],
    causal_validation_computed_at_commit: str, causal_validation_positions: str,
    gates: list[dict[str, Any]], spot_read: dict[str, Any] | None,
    judge_model: str, judge_rubric_version: str, judge_prompt_version: str,
    dose_response: dict[str, dict[str, Any]],
    configuration_name: str, configuration_completeness: str, configuration_model_n_layers: int,
    configuration_grid_cells_expected: int, configuration_grid_cells_recorded: int,
    generation_manifest_paths: dict[str, str | Path | None],
    generation_manifest_commits: dict[str, str | None],
    selection_record_paths: dict[str, str | Path | None],
    selection_commits: dict[str, str | None], confirmation_judging_commits: dict[str, str | None],
    suppress_disposition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A COMPLETE document assembled from REAL PRODUCTION OBJECTS, not a
    test/synthetic assembler: `model_provenance`/`sae_provenance` are
    exactly `Backend.provenance["model"]`/`["sae"]` as `final_pairing_
    concept_discovery.load_backend` actually returns them (this function
    never re-derives `model_revision`/`sae_revision`/`release`/
    `loader_sae_id`/`params_sha256` -- it reads them straight off that
    dict), and `generation_manifest_paths`/`selection_record_paths` are
    the REAL file paths `final_pairing_one_allocation_generation.write_
    generation_manifest`/`final_pairing_judge_cli`'s selection-writing
    command actually wrote -- hashed HERE via `build_manifest_reference`/
    `build_selection_record_reference` (never pre-hashed by the caller,
    never copied from a manifest's own self-declared field).

    All model-specific loader identity and the measured params digest must
    already be present in `sae_provenance`, where the weight-loading path
    verified them.  This function refuses missing values rather than writing
    empty or invented immutable provenance.

    Everything this function CANNOT derive from a loaded backend or a
    written file (identity like `run_id`/`code_commit`/`host`/
    `created_at`, the judge's own identity, gate verdicts, dose-response
    observations, calibration directions) remains an explicit, required
    argument -- this project's own no-clock, no-invented-identity
    discipline applies here exactly as it does in `assemble_discovery_
    document` itself, which this function delegates to for the actual
    document assembly (never duplicating its validation).

    `suppress_disposition` (build with `build_suppress_disposition` above)
    passes straight through to `assemble_discovery_document`, which enforces
    its required-iff/prohibited-iff nullity against `directions["suppress"]`
    -- this function invents no default and performs no disposition logic
    of its own."""
    generation_manifests: dict[str, dict[str, Any] | None] = {}
    selection_records: dict[str, dict[str, Any] | None] = {}
    for direction in ("amplify", "suppress"):
        manifest_path = generation_manifest_paths.get(direction)
        if manifest_path is None:
            generation_manifests[direction] = None
        else:
            generation_manifests[direction] = build_manifest_reference(
                manifest_path, computed_at_commit=generation_manifest_commits[direction],
            )
        selection_path = selection_record_paths.get(direction)
        if selection_path is None:
            selection_records[direction] = None
        else:
            selection_records[direction] = build_selection_record_reference(
                selection_path, selection_commit=selection_commits[direction],
                confirmation_judging_commit=confirmation_judging_commits[direction],
            )

    required_sae_provenance = (
        "revision", "release", "loader_sae_id", "params_sha256",
    )
    missing = [
        field for field in required_sae_provenance
        if not isinstance(sae_provenance.get(field), str) or not sae_provenance.get(field)
    ]
    scientific_sae_id = (
        sae_provenance.get("scientific_sae_id") or sae_provenance.get("sae_id")
    )
    if missing or not isinstance(scientific_sae_id, str) or not scientific_sae_id:
        if not scientific_sae_id:
            missing.append("scientific_sae_id")
        raise ValueError(
            f"sae_provenance is missing authoritative immutable identity field(s) {sorted(set(missing))}"
        )

    return assemble_discovery_document(
        run_id=run_id, code_commit=code_commit, entrypoint=entrypoint, host=host, created_at=created_at,
        model_id=model_id, model_revision=model_provenance.get("revision", ""),
        sae_repo_id=sae_repo_id, sae_repo_revision=sae_provenance.get("revision", ""),
        sae_id=scientific_sae_id, layer=layer,
        release=sae_provenance["release"], loader_sae_id=sae_provenance["loader_sae_id"],
        params_sha256=sae_provenance["params_sha256"], layer_selection=layer_selection,
        concept_id=concept_id, hypothesis_source=hypothesis_source, search_scope=search_scope,
        candidate_index=candidate_index, engineering_index_rediscovery_note=engineering_index_rediscovery_note,
        feature_certificate=feature_certificate, subject=subject,
        calibration_protocol=calibration_protocol, calibrated_by=calibrated_by, calibrated_at=calibrated_at,
        directions=directions, positions=positions,
        prompt_set_id=prompt_set_id, prompt_set_source_path=prompt_set_source_path,
        prompt_set_source_sha256=prompt_set_source_sha256, prompt_set_source_commit=prompt_set_source_commit,
        paraphrase_families=paraphrase_families,
        causal_validation_computed_at_commit=causal_validation_computed_at_commit,
        causal_validation_positions=causal_validation_positions, gates=gates, spot_read=spot_read,
        judge_model=judge_model, judge_rubric_version=judge_rubric_version, judge_prompt_version=judge_prompt_version,
        dose_response=dose_response,
        configuration_name=configuration_name, configuration_completeness=configuration_completeness,
        configuration_model_n_layers=configuration_model_n_layers,
        configuration_grid_cells_expected=configuration_grid_cells_expected,
        configuration_grid_cells_recorded=configuration_grid_cells_recorded,
        generation_manifests=generation_manifests, selection_records=selection_records,
        suppress_disposition=suppress_disposition,
    )


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
            "ENGINEER 1 PRODUCER DECLARATION -- schema+configuration+judge fields ratified against Engineer 3's "
            "real consumer at commit 047fe17 (schema v5.0: canonical dose IDs, suppress disposition, and "
            "configuration-specific Qwen PRIMARY/BACKUP identities); generation_manifests/selection_records per "
            "discovery_document_generation_"
            "binding.json v1.1.0 (commit 40061b6), NORMATIVE OVER by final-pairing-manifest-immutability/1.0.0 "
            "(commit 2dc9e338c12db1c1f3939a9f709f8af816ad8272); dose_grid/causal_dose_grid_* per causal_dose_"
            "grid.json v1.0.0 (commit c43a976); suppress_disposition per suppress_null_disposition.json v1.0.0 "
            "(commit cb0aca8). Reconciled via a real reconcile-schema/gating-report subprocess run against "
            "D:/devcache/wt/concept-bundle at 047fe17 -- see this module's docstring and the closing report."
        ),
        "objects": {
            "<root>": {"required": list(ROOT_REQUIRED_FIELDS), "conditional": [SUPPRESS_DISPOSITION_FIELD]},
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
                # Mirrors the consumer's own field-naming convention EXACTLY (verified against
                # `accepted_input_schema()`/`discovery_input_schema.json` at commit ff2a565): "keys"
                # names the two per-direction slots, "required" names the REFERENCE OBJECT's own
                # fields directly (no separately-named nested sub-object) -- a prior version of this
                # declaration put ["amplify","suppress"] under "required" and nested the reference
                # fields under a "SelectionRecordReference" key, which the consumer's own
                # reconcile-schema/gating-report flattener reads structurally, not by convention
                # inference, and therefore rejected as an incompatible shape.
                #
                # `content_required`/`content_rules`/`authority`/`partition`/`failed_never_promoted`
                # below are copied VERBATIM (never translated) from ff2a565's own
                # `discovery_input_schema.json` -- schema 3.0's manifest-immutability addition: the
                # SELECTION RECORD FILE ITSELF (what `source_path` points at) is now a required,
                # CLOSED shape this document producer never constructs (that is Deliverable B,
                # `final_pairing_judge_cli.py`'s scope -- see this module's docstring for the
                # disclosed gap between that file's current output and this content schema).
                "selection_records": {
                    "keys": ["amplify", "suppress"],
                    "value": "SelectionRecordReference | null",
                    "required": ["source_path", "source_sha256", "selection_commit", "confirmation_judging_commit"],
                    "authority": "The SOLE authoritative record of selection outcome. The bound manifest carries none.",
                    "content_required": ["manifest_sha256", "outcome", "selected", "unselected"],
                    "content_rules": {
                        "additionalProperties": False,
                        "manifest_sha256": "sha256:<64 hex>, and MUST equal the digest promotion RECOMPUTED from the bound manifest's bytes.",
                        "outcome": "SELECTED | FAILED",
                        "selected": "object {LOW, MEDIUM, HIGH}; REQUIRED iff outcome == SELECTED, PROHIBITED iff outcome == FAILED. The three must name three DISTINCT doses. No magnitude ordering is asserted (a SUPPRESS HIGH of S4 is valid and is the normal case). CORRECTED (was: 'on the SUPPRESS arm HIGH is ABLATE'): that claim is FALSE. Per mixed_operation_publication.json v1.1.0 (commit 6e3f4be), S5/ABLATE is NEVER eligible to occupy LOW, MEDIUM, or HIGH here -- the restriction binds at selection time, before any judged score exists. S5 remains fully scientific (generated, judged, and reflected in this record's own unselected/evidence) but may never be a value in this object; S1..S4 (CLAMP) and S5 (ABLATE) are not one continuous magnitude ramp, they are two different operations.",
                        "unselected": "array; every confirmation dose not selected, and ALL doses when outcome == FAILED.",
                        "partition": "The dose set is DERIVED FROM THE MANIFEST -- the distinct doses across files[] where purpose == CONFIRMATION -- and is never asserted by the record. selected.values() UNION unselected must equal it exactly, each dose covered exactly once.",
                        "failed_never_promoted": "A FAILED record may NEVER be referenced here. A failed direction is null in calibration.directions, generation_manifests and selection_records alike; the FAILED record stays in the run's immutable inventory beside its manifest, preserved and never deleted.",
                        # Copied verbatim from 3aff107's own discovery_input_schema.json (schema
                        # 5.0) -- the CLAMP points only, S1..S4 on Suppress; the ABLATE point has
                        # no numeric strength to be, so it is never eligible for a published triple.
                        "published_candidate_set": {"AMPLIFY": ["A1", "A2", "A3", "A4", "A5"], "SUPPRESS": ["S1", "S2", "S3", "S4"]},
                    },
                },
            },
            "dose_response": {"required": ["computed_at_commit", "observations"]},
            "configuration": {
                "required": ["name", "completeness", "model_n_layers",
                             "grid_cells_expected", "grid_cells_recorded"],
            },
            # Same convention fix as causal_validation.selection_records above: "keys" for the two
            # per-direction slots, "reference_required" (the consumer's own field name, NOT
            # "required") for the ManifestReference's own fields. `manifest_required`/`manifest_
            # optional`/`manifest_file_required`/`manifest_file_prohibited`/`immutability*` below
            # describe the BOUND MANIFEST FILE's own shape (`final_pairing_one_allocation_
            # generation.py`'s `MANIFEST_REQUIRED_FIELDS`/`MANIFEST_FILE_REQUIRED_FIELDS`, already
            # matching this list at commit 7d7985d) -- copied verbatim from ff2a565, never
            # translated, since this document producer never constructs the manifest itself, only
            # references it.
            "generation_manifests": {
                "keys": ["amplify", "suppress"],
                "value": "ManifestReference | null",
                "reference_required": ["source_path", "source_sha256", "computed_at_commit",
                                        "protocol_path", "protocol_sha256"],
                "immutability": "The bound manifest is the run's IMMUTABLE PRE-SELECTION INVENTORY of what was generated. Written once, at transfer, and never rewritten, re-emitted or re-hashed. Promotion re-reads source_path at the selection and confirmation-judging commits and compares BYTES.",
                "immutability_correction": "final-pairing-manifest-immutability/1.0.0",
                "immutability_correction_commit": "2dc9e338c12db1c1f3939a9f709f8af816ad8272",
                "derived_view_rejected": "Any file carrying NOT_FOR_PROMOTION in its bytes or derived: true in its structure is REJECTED ACTIVELY, not merely left unaccepted. stamp_manifest_with_selection produces a reading aid; it may not replace the bound manifest, appear here, satisfy promotion, or have its digest appear in any source_sha256.",
                "manifest_required": list(_ONE_ALLOCATION_MANIFEST_REQUIRED_FIELDS),
                "manifest_optional": {
                    "inventory_stage": "const PRE_SELECTION. The ONLY permitted pre-selection marker, MANIFEST-LEVEL rather than per file: a per-entry flag that is always true carries no information and reads as a status that COULD vary. Optional -- the ancestry check already proves the ordering structurally.",
                },
                "manifest_file_required": list(_ONE_ALLOCATION_MANIFEST_FILE_REQUIRED_FIELDS),
                "manifest_file_prohibited": {
                    "selection_status": "STRUCK by final-pairing-manifest-immutability/1.0.0 and refused ON SIGHT whatever its value, including null. A record whose bytes are committed BEFORE an event cannot contain that event's outcome: stamping it would change the manifest's bytes and invalidate both source_sha256 and computed_at_commit, so the field was permanently unfillable. Any other field encoding a selection outcome is refused the same way, by the closed files[] schema.",
                },
                # Schema 5.0 addition (commit 3aff107), copied verbatim: dose_grid is
                # MANIFEST-LEVEL (operation/value are properties of the grid, not of a
                # generation) -- `final_pairing_one_allocation_generation._dose_grid_
                # manifest_points` builds exactly this shape from the same frozen artifact
                # `causal_dose_grid_path`/`_version`/`_sha256` bind below.
                "causal_dose_grid": CAUSAL_DOSE_GRID_INFORMATIONAL_VERSION,
                "causal_dose_grid_commit": CAUSAL_DOSE_GRID_INFORMATIONAL_COMMIT,
                "dose_encoding": "files[].dose is the canonical STRING dose_id and nothing else. The numeric value travels alongside it in the manifest-level dose_grid, never as the key. A value-derived label such as '1.0x', and the operation name 'ABLATE', are refused as identifiers. The file's PATH must contain its dose_id as a token.",
                "dose_identifiers": {"AMPLIFY": ["A1", "A2", "A3", "A4", "A5"], "SUPPRESS": ["S1", "S2", "S3", "S4", "S5"]},
                "cross_pairing_dose_comparison": "PROHIBITED. value_in_max_units multiplies each pairing's OWN maximum-activation denominator -- no comparison, ratio or ordering of value_in_max_units across pairings is permitted.",
                "dose_grid_encoding": {
                    "location": "MANIFEST LEVEL, one array of five points",
                    "additionalProperties": False,
                    "clamp_point": ["index", "dose_id", "operation", "value_in_max_units", "unit", "unit_source"],
                    "ablate_point": ["index", "dose_id", "operation", "value_in_max_units", "unit", "unit_source", "weight"],
                    "ablate_prohibited": ["value_in_max_units", "unit", "unit_source"],
                    "ablate_weight": 1.0,
                    "checked_against": "the frozen artifact point by point -- index, dose_id, operation and value -- because a manifest declaring A3 while meaning 2.0 would pass every identifier check and still have run the wrong dose.",
                    "why_not_per_file": "operation and value are properties of the GRID, not of a generation. Repeating them on 900 entries is the per-file encoding the immutability correction rejected for the same reason.",
                },
            },
            # Schema 5.0 addition (commit 3aff107), copied verbatim from 3aff107's own
            # discovery_input_schema.json: a root-level CLOSED object, required iff
            # calibration.directions.suppress is null and prohibited iff it is not.
            # `build_suppress_disposition`/`_validate_suppress_disposition_nullity` above
            # implement exactly this shape.
            SUPPRESS_DISPOSITION_FIELD: {
                "additionalProperties": False,
                "required": list(SUPPRESS_DISPOSITION_FIELDS),
                "reason": list(SUPPRESS_DISPOSITION_REASONS),
                "ablation_cleared_ge": "boolean | null; null IFF reason == NOT_ATTEMPTED, otherwise a LITERAL boolean. It carries the finding 'only full ablation suppressed this concept' into the promoted document as a FACT.",
                "required_iff": "calibration.directions.suppress is null",
                "prohibited_iff": "calibration.directions.suppress is non-null",
                "gating": False,
                "ruling": SUPPRESS_NULL_DISPOSITION_PROTOCOL_VERSION,
                "ruling_commit": SUPPRESS_NULL_DISPOSITION_PROTOCOL_COMMIT,
                "NOT_A_GATE": "PROMOTION NEITHER PASSES NOR FAILS ON ANY VALUE HERE. ablation_cleared_ge = true may never be rendered, summarised, tabulated or exported as a G-E PASS.",
                "the_G_E_gate_is_UNCHANGED": "A G-E gate attached to a null Suppress direction still BLOCKS promotion. No relaxation and no exception.",
                "the_science_is_not_orphaned": "The S5 result stays hash-bound in the causal_validation record, the generation manifest and the selection record's unselected list. No additional evidence artifact and no fifth evidence_ref.",
                "prohibited_reporting": [
                    "reporting the concept as bidirectionally validated",
                    "showing a G-E PASS for this concept in any promoted-document summary",
                    "implying the public tool can suppress this concept",
                    "counting the concept toward any bidirectional or Suppress-validated tally",
                ],
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
