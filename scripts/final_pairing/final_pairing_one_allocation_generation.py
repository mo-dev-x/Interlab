"""Stages 1-3 of the frozen one-allocation dose-generation protocol
(`protocols/final_pairing/v1/one_allocation_dose_generation.json`, v1.0.0,
`gating: true`): GPU-side GENERATION ONLY, on the SAME offline Tamia
allocation as G-A/B/C discovery (stage 1, already implemented in
`final_pairing_concept_discovery.py`'s grid functions), plus stage 3
(off-cluster transfer verification).

MANIFEST/FILE SHAPE IS DICTATED BY ENGINEER 3'S REAL, ENFORCING
`dose_generation_problems`/`dose-check` (read directly out of
`scripts/concept_bundle_publish.py` at commit ac9ea40, never guessed at):
ONE FILE per (concept, pairing, direction, dose, purpose) -- NOT per
(..., prompt, repeat) as an earlier version of this module built --
holding every prompt x repeat for that cell, with a `seeds` LIST (one
seed per generation in the file) and `n_prompts`/`n_repeats` counts,
because the consumer's dose-check reads exactly that shape. A manifest
is written PER DIRECTION (never one manifest spanning both Amplify and
Suppress -- ruled separately, since the two directions have separate
prompt sets, grids, and selection records per the protocol's own
`asymmetry_preserved` clause).

HARD STOP, STRUCTURAL, NOT MERELY DOCUMENTED: this module never imports
`final_pairing_causal_judge` or `lodestar`, at module scope or inside any
function body -- "Any judge call from inside the GPU allocation" is one
of the protocol's own named hard stops, and the consumer's own dose-check
independently refuses any judging-shaped field
(score/verdict/rubric/judge/... ) inside a generation manifest entry.
`test_final_pairing_one_allocation_generation.py` asserts the import
guarantee via an AST scan of this file's own source.

WHAT THIS MODULE DOES NOT DO, ON PURPOSE (stages 4-5, a SEPARATE
machine/stage per the same protocol): judge the sweep, select LOW/MEDIUM/
HIGH, write or commit `selection_record.json`, or judge confirmation
outputs. That is `final_pairing_judge_cli.py`'s job -- see that module.

ADDITION_1 (seed disjointness): `derive_seed` salts by NAMESPACE
("sweep"/"confirmation") in addition to every identifying field, so
S_sweep and S_conf are disjoint BY CONSTRUCTION; `assert_seed_sets_
disjoint` is still run explicitly on every produced set.

ADDITION_3 (one file per dose): `generate_dose_file` writes exactly one
JSON file per (concept, pairing, direction, dose, purpose) -- never a
shared file across doses, so reading the selected doses' files
structurally cannot open an unselected one. Filenames encode the dose,
matching the consumer's own `str(dose) not in file_path` check.

ADDITION_4 (concept-complete ordering + wall-time preflight):
`assess_concept_generation_readiness` is the NOT_ATTEMPTED gate --
`generate_concept_complete` itself always finishes one whole concept (both
directions, all five doses, sweep AND confirmation) or is not started at
all; there is no partial-concept file layout. Completeness per concept is
recorded explicitly (never inferred from a clean process exit) in the
manifest's `concepts` map, matching the consumer's own `_dose_coverage_
problems` check.

DISCOVERY-DOCUMENT MANIFEST REFERENCE: DELIBERATELY NOT ADDED HERE. The
Architect is issuing the exact schema ruling for how a discovery document
references its generation manifest(s); inventing a field name ahead of
that ruling was explicitly instructed against. This module and the
manifest it writes are ready to be referenced once that ruling lands --
every fact the ruling is likely to need (run_id, source_commit,
configuration, full model/SAE identity, measured params_sha256,
completeness, and the manifest's own path/hash) is already present in
`write_generation_manifest`'s output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

DIRECTIONS: tuple[str, ...] = ("amplify", "suppress")
SWEEP_PROMPTS_PER_DIRECTION = 15
SWEEP_REPEATS = 1
CONFIRMATION_PROMPTS_PER_DIRECTION = 20
CONFIRMATION_REPEATS = 3
DOSES_PER_DIRECTION = 5
#: 2 directions x 5 doses x (15 sweep prompts x 1 repeat + 20 confirmation prompts x 3 repeats)
#: = 2 x 5 x (15 + 60) = 750. The protocol's own cost accounting states 75 sweep + 300
#: confirmation generations PER DIRECTION (375), matching this doubled for both directions.
GENERATIONS_PER_CONCEPT = len(DIRECTIONS) * DOSES_PER_DIRECTION * (
    SWEEP_PROMPTS_PER_DIRECTION * SWEEP_REPEATS + CONFIRMATION_PROMPTS_PER_DIRECTION * CONFIRMATION_REPEATS
)
#: 2 directions x 5 doses x 2 purposes -- the number of ONE-FILE-PER-DOSE
#: manifest entries one complete concept produces (distinct from
#: GENERATIONS_PER_CONCEPT, which counts individual generations, many of
#: which are now bundled into one file per dose).
DOSE_FILES_PER_CONCEPT = len(DIRECTIONS) * DOSES_PER_DIRECTION * 2

ONE_ALLOCATION_PROTOCOL_PATH = "protocols/final_pairing/v1/one_allocation_dose_generation.json"
ONE_ALLOCATION_PROTOCOL_VERSION = "final-pairing-one-allocation-dose-generation/1.0.0"
ONE_ALLOCATION_PROTOCOL_COMMIT = "5a5175d36eac9802b45f76aeb5b52ff6b25220a8"
ONE_ALLOCATION_PROTOCOL_SHA256 = "bd1974b4c44802fa7a49fb7a4ed65df78a9ba66cdca78bb6fc0da69cf42252cf"

#: The exact stamp `concept_bundle_publish.py` reads from the frozen protocol's
#: own `sealed_output_rules.label` -- mirrored here as a literal (never
#: imported: that package does not exist on this branch) so a caller
#: doesn't have to hand-type it.
SEALED_LABEL = "UNUSED_FOR_SELECTION_OR_CLAIM"

COMPLETENESS_VALUES: tuple[str, ...] = ("COMPLETE", "PARTIAL", "NOT_ATTEMPTED")


class SeedCollisionError(RuntimeError):
    """S_sweep and S_conf intersected at the same cell -- ADDITION_1's hard
    stop. Reusing a sweep generation as one of the three confirmation
    repeats is a winner's-curse bias on the reported number, per the
    protocol's own explanation."""


class TransferVerificationFailed(RuntimeError):
    """Stage 3: a file (or the manifest itself) does not hash to its
    recorded value after transfer off the cluster. Always a hard stop,
    never a warning or a retry-past condition."""


def validate_one_allocation_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if the frozen one-allocation protocol's actual bytes
    don't match the pinned hash -- same discipline as this project's other
    frozen-protocol hash guards (`validate_backup_trigger_protocol_hash`,
    `validate_scientific_config_identity_hash`)."""
    path = Path(repo_root) / ONE_ALLOCATION_PROTOCOL_PATH
    if not path.is_file():
        raise TransferVerificationFailed(f"one-allocation protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != ONE_ALLOCATION_PROTOCOL_SHA256:
        raise TransferVerificationFailed(
            f"{path} sha256={actual!r} != pinned {ONE_ALLOCATION_PROTOCOL_SHA256!r} -- refusing to "
            f"generate against an altered or unpinned one-allocation protocol."
        )
    return actual


def derive_seed(
    *, namespace: Literal["sweep", "confirmation"], concept_id: str, pairing_id: str, direction: str,
    dose: int, prompt_index: int, repeat_index: int,
) -> int:
    """Deterministic, reproducible seed for one generation. Salted by
    `namespace` ("sweep" vs "confirmation") in addition to every other
    identifying field, so S_sweep and S_conf are disjoint BY
    CONSTRUCTION -- `assert_seed_sets_disjoint` below still verifies this
    explicitly rather than trusting the construction alone."""
    payload = "|".join([
        "final-pairing-one-allocation-v1", namespace, concept_id, pairing_id, direction,
        str(dose), str(prompt_index), str(repeat_index),
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def assert_seed_sets_disjoint(sweep_seeds: list[int], confirmation_seeds: list[int]) -> None:
    overlap = sorted(set(sweep_seeds) & set(confirmation_seeds))
    if overlap:
        raise SeedCollisionError(
            f"S_sweep and S_conf intersect at seed(s) {overlap} -- hard stop per "
            f"one_allocation_dose_generation.json ADDITION_1: a shared seed at the same cell "
            f"would make a sweep generation double as one of the three confirmation repeats, "
            f"biasing the confirmation estimate at exactly the dose selection favoured."
        )


@dataclass(frozen=True)
class DoseSpec:
    kind: Literal["clamp", "ablate"]
    value_in_max_units: float | None = None

    def __post_init__(self) -> None:
        if self.kind == "ablate" and self.value_in_max_units is not None:
            raise ValueError("an ablate dose carries no value_in_max_units, unit, or unit_source")
        if self.kind == "clamp" and self.value_in_max_units is None:
            raise ValueError("a clamp dose requires value_in_max_units")


def build_amplify_dose_grid(values: tuple[float, ...]) -> list[DoseSpec]:
    """Amplify's five-point grid: five distinct CLAMP doses (the protocol
    does not require a particular ordering for Amplify, only that it be
    five points -- unlike Suppress, which requires ABLATE as one of them)."""
    if len(values) != DOSES_PER_DIRECTION:
        raise ValueError(f"amplify dose grid must have exactly {DOSES_PER_DIRECTION} points, got {len(values)}")
    if len(set(values)) != DOSES_PER_DIRECTION:
        raise ValueError("amplify dose grid values must be distinct")
    return [DoseSpec(kind="clamp", value_in_max_units=v) for v in values]


def build_suppress_dose_grid(clamp_fractions: tuple[float, ...]) -> list[DoseSpec]:
    """Suppress's five-point grid: four DESCENDING clamp fractions plus
    ABLATE as the fifth grid point (`suppress_specifics.dose_grid`)."""
    if len(clamp_fractions) != DOSES_PER_DIRECTION - 1:
        raise ValueError(
            f"suppress clamp portion must have exactly {DOSES_PER_DIRECTION - 1} points "
            f"(plus ABLATE as the fifth), got {len(clamp_fractions)}"
        )
    if list(clamp_fractions) != sorted(clamp_fractions, reverse=True):
        raise ValueError(f"suppress clamp fractions must be strictly descending, got {clamp_fractions}")
    if len(set(clamp_fractions)) != len(clamp_fractions):
        raise ValueError("suppress clamp fractions must be distinct")
    return [DoseSpec(kind="clamp", value_in_max_units=v) for v in clamp_fractions] + [DoseSpec(kind="ablate")]


@dataclass(frozen=True)
class ConceptGenerationReadiness:
    attempt: bool
    detail: str


def estimate_seconds_for_one_concept(*, seconds_per_generation: float) -> float:
    if seconds_per_generation <= 0:
        raise ValueError("seconds_per_generation must be positive")
    return GENERATIONS_PER_CONCEPT * seconds_per_generation


def assess_concept_generation_readiness(
    *, remaining_wall_time_seconds: float, seconds_per_generation: float,
) -> ConceptGenerationReadiness:
    """ADDITION_4's preflight: 'if the remaining wall time cannot fit at
    least one whole concept, do not start.' Never raises -- returns
    `attempt=False` (NOT_ATTEMPTED) so the caller can stop cleanly rather
    than beginning a concept it cannot finish."""
    estimated = estimate_seconds_for_one_concept(seconds_per_generation=seconds_per_generation)
    if remaining_wall_time_seconds >= estimated:
        return ConceptGenerationReadiness(
            attempt=True,
            detail=f"remaining={remaining_wall_time_seconds:.0f}s >= estimated one-concept cost {estimated:.0f}s",
        )
    return ConceptGenerationReadiness(
        attempt=False,
        detail=(
            f"remaining={remaining_wall_time_seconds:.0f}s < estimated one-concept cost {estimated:.0f}s "
            f"-- NOT_ATTEMPTED per ADDITION_4 (never truncate into a partial comparison)"
        ),
    )


@dataclass(frozen=True)
class GenerationFileRecord:
    concept_id: str
    pairing_id: str
    direction: Literal["amplify", "suppress"]
    purpose: Literal["sweep", "confirmation"]
    dose: int  # the dose IDENTIFIER (dose_index, 0-4) -- the consumer's own field name
    dose_kind: Literal["clamp", "ablate"]
    dose_value: float | None
    n_prompts: int
    n_repeats: int
    seeds: list[int]  # one seed per generation in this file, len == n_prompts * n_repeats
    path: str
    sha256: str
    #: Stamped `SEALED_LABEL` for confirmation files at doses NOT among the
    #: three later selected -- set by `stamp_manifest_with_selection` below,
    #: AFTER selection (a stage-4 concern on a different machine). Absent
    #: (None) at generation time and for every sweep file and every
    #: selected dose.
    label: str | None = None


def _generation_filename(*, concept_id: str, pairing_id: str, direction: str, purpose: str, dose: int) -> str:
    return f"{concept_id}__{pairing_id}__{direction}__{purpose}__dose{dose}.json"


def generate_dose_file(
    backend, feature_indices: list[int], *, dose: DoseSpec, dose_index: int, corpus_max: dict[int, float],
    positions: str, prompts: list[str], purpose: Literal["sweep", "confirmation"], n_repeats: int,
    base_seed_namespace: Literal["sweep", "confirmation"], max_new_tokens: int, out_dir: str | Path,
    concept_id: str, pairing_id: str, direction: Literal["amplify", "suppress"],
    run_intervention_fn=None, hash_fn=None,
) -> GenerationFileRecord:
    """Runs every (prompt, repeat) for ONE (concept, pairing, direction,
    dose, purpose) cell and writes them all into ONE file (ADDITION_3, and
    the exact shape the consumer's `dose_generation_problems` enforces:
    one manifest entry with a `seeds` LIST, not one entry per generation).
    Reuses the existing, already-tested `final_pairing_concept_discovery.
    run_intervention` by default -- injectable for tests."""
    if run_intervention_fn is None:
        import final_pairing_concept_discovery as _d

        run_intervention_fn = _d.run_intervention
    if hash_fn is None:
        import final_pairing_concept_discovery as _d

        hash_fn = _d.compute_file_sha256

    generations: list[dict[str, Any]] = []
    seeds: list[int] = []
    for prompt_index, prompt in enumerate(prompts):
        for repeat_index in range(n_repeats):
            seed = derive_seed(
                namespace=base_seed_namespace, concept_id=concept_id, pairing_id=pairing_id, direction=direction,
                dose=dose_index, prompt_index=prompt_index, repeat_index=repeat_index,
            )
            outcome = run_intervention_fn(
                backend, feature_indices,
                direction="ablate" if dose.kind == "ablate" else "clamp",
                value_in_max_units=dose.value_in_max_units or 0.0,
                corpus_max=corpus_max, positions=positions, prompt=prompt, seed=seed, max_new_tokens=max_new_tokens,
            )
            seeds.append(seed)
            generations.append({
                "prompt_id": f"{purpose}_{prompt_index}", "prompt_index": prompt_index, "repeat_index": repeat_index,
                "seed": seed, "generated_text": outcome.generated_text, "verdict": outcome.verdict, "spec": outcome.spec,
            })

    payload = {
        "concept_id": concept_id, "pairing_id": pairing_id, "direction": direction, "purpose": purpose,
        "dose": dose_index, "dose_kind": dose.kind, "dose_value": dose.value_in_max_units,
        "generations": generations,
    }
    filename = _generation_filename(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose=purpose, dose=dose_index,
    )
    path = Path(out_dir) / filename
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    digest = hash_fn(path)
    return GenerationFileRecord(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose=purpose,
        dose=dose_index, dose_kind=dose.kind, dose_value=dose.value_in_max_units,
        n_prompts=len(prompts), n_repeats=n_repeats, seeds=seeds, path=str(path), sha256=digest,
    )


def generate_concept_complete(
    backend, feature_indices: list[int], *, concept_id: str, pairing_id: str,
    corpus_max: dict[int, float], positions: str, out_dir: str | Path,
    amplify_dose_grid: list[DoseSpec], suppress_dose_grid: list[DoseSpec],
    amplify_sweep_prompts: list[str], amplify_confirmation_prompts: list[str],
    suppress_sweep_prompts: list[str], suppress_confirmation_prompts: list[str],
    max_new_tokens: int, run_intervention_fn=None, progress=None,
) -> list[GenerationFileRecord]:
    """ADDITION_4: finishes ONE concept entirely (both directions, all
    five doses, sweep AND confirmation) or raises before writing anything
    -- there is no partial-concept file layout. Resumable per-dose-file
    via `progress`. Asserts `assert_seed_sets_disjoint` once ALL of this
    concept's cells have been planned."""
    if len(amplify_dose_grid) != DOSES_PER_DIRECTION or len(suppress_dose_grid) != DOSES_PER_DIRECTION:
        raise ValueError(f"both dose grids must have exactly {DOSES_PER_DIRECTION} points")
    if len(amplify_sweep_prompts) != SWEEP_PROMPTS_PER_DIRECTION or len(suppress_sweep_prompts) != SWEEP_PROMPTS_PER_DIRECTION:
        raise ValueError(f"sweep requires exactly {SWEEP_PROMPTS_PER_DIRECTION} held-out prompts per direction")
    if len(amplify_confirmation_prompts) != CONFIRMATION_PROMPTS_PER_DIRECTION or len(suppress_confirmation_prompts) != CONFIRMATION_PROMPTS_PER_DIRECTION:
        raise ValueError(f"confirmation requires exactly {CONFIRMATION_PROMPTS_PER_DIRECTION} held-out prompts per direction")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[GenerationFileRecord] = []
    sweep_seeds: list[int] = []
    confirmation_seeds: list[int] = []

    plan = (
        ("amplify", amplify_dose_grid, amplify_sweep_prompts, amplify_confirmation_prompts),
        ("suppress", suppress_dose_grid, suppress_sweep_prompts, suppress_confirmation_prompts),
    )
    for direction, dose_grid, sweep_prompts, confirmation_prompts in plan:
        for dose_index, dose in enumerate(dose_grid):
            for purpose, prompts, n_repeats, seed_bucket in (
                ("sweep", sweep_prompts, SWEEP_REPEATS, sweep_seeds),
                ("confirmation", confirmation_prompts, CONFIRMATION_REPEATS, confirmation_seeds),
            ):
                key = f"onealloc_{concept_id}_{pairing_id}_{direction}_{purpose}_dose{dose_index}"
                if progress is not None and progress.is_done(key):
                    record = GenerationFileRecord(**progress.result(key)["record"])
                    records.append(record)
                    seed_bucket.extend(record.seeds)
                    continue
                record = generate_dose_file(
                    backend, feature_indices, dose=dose, dose_index=dose_index, corpus_max=corpus_max,
                    positions=positions, prompts=prompts, purpose=purpose, n_repeats=n_repeats,
                    base_seed_namespace=purpose, max_new_tokens=max_new_tokens, out_dir=out_dir,
                    concept_id=concept_id, pairing_id=pairing_id, direction=direction,
                    run_intervention_fn=run_intervention_fn,
                )
                records.append(record)
                seed_bucket.extend(record.seeds)
                if progress is not None:
                    progress.record(key, {"record": asdict(record)})

    assert_seed_sets_disjoint(sweep_seeds, confirmation_seeds)
    return records


def _canonical_manifest_json(body: dict) -> str:
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)


def write_generation_manifest(
    records: list[GenerationFileRecord], manifest_path: str | Path, *,
    run_id: str, source_commit: str, configuration_name: Literal["primary", "backup"],
    model_id: str, model_revision: str, sae_repo_id: str, sae_repo_revision: str,
    release: str, loader_sae_id: str, scientific_sae_id: str, measured_params_sha256: str | None,
    concepts: dict[str, str],
) -> dict:
    """Writes ONE manifest for the records passed in -- ALL records must
    share one `direction` (a manifest is per-direction, ratified by
    `protocols/final_pairing/v1/discovery_document_generation_binding.json`
    v1.1.0: "one manifest may not occupy both keys"). Binds every fact
    that ruling's `manifest_required_bindings` names: run_id/source_commit,
    which of primary/backup this is, the scalar direction, the full
    model/SAE identity (release/loader_sae_id/scientific_sae_id kept as
    three separate fields, never one collapsed name, per identity v1.3's
    own semantics), the MEASURED params hash (never the expected constant
    copied in), per-concept completeness, and the frozen one-allocation
    protocol's own path/hash. Hashes every file (already done per-record
    by `generate_dose_file`) and additionally hashes the MANIFEST ITSELF."""
    if configuration_name not in ("primary", "backup"):
        raise ValueError(f"configuration_name must be 'primary' or 'backup', got {configuration_name!r}")
    bad_completeness = {v for v in concepts.values() if v not in COMPLETENESS_VALUES}
    if bad_completeness:
        raise ValueError(f"concepts completeness values must be one of {COMPLETENESS_VALUES}, got {bad_completeness}")
    directions_present = {r.direction for r in records}
    if len(directions_present) != 1:
        raise ValueError(
            f"a generation manifest must cover exactly ONE direction, got {sorted(directions_present)} -- "
            f"write a separate manifest per direction"
        )
    direction = next(iter(directions_present))
    body = {
        "protocol_version": ONE_ALLOCATION_PROTOCOL_VERSION,
        "protocol_sha256": ONE_ALLOCATION_PROTOCOL_SHA256,
        "run_id": run_id, "source_commit": source_commit, "configuration": configuration_name,
        "direction": direction.upper(),
        "model": {"model_id": model_id, "model_revision": model_revision},
        "sae": {
            "sae_repo_id": sae_repo_id, "sae_repo_revision": sae_repo_revision,
            "release": release, "loader_sae_id": loader_sae_id, "scientific_sae_id": scientific_sae_id,
            "params_sha256": measured_params_sha256,
        },
        "concepts": dict(concepts),
        "files": [asdict(r) for r in records],
    }
    manifest_hash = hashlib.sha256(_canonical_manifest_json(body).encode("utf-8")).hexdigest()
    full = {**body, "manifest_sha256": manifest_hash}
    Path(manifest_path).write_text(_canonical_manifest_json(full), encoding="utf-8")
    return full


def verify_generation_manifest(manifest_path: str | Path, *, files_root: str | Path | None = None) -> dict:
    """Stage 3 (TRANSFER): re-verifies every file hash (and the manifest's
    own hash) against the manifest after moving outputs off the cluster.
    Hash mismatch -- of any file, or of the manifest itself -- is a HARD
    STOP (raises `TransferVerificationFailed`), never a warning."""
    import final_pairing_concept_discovery as _d

    manifest_path = Path(manifest_path)
    full = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "manifest_sha256" not in full:
        raise TransferVerificationFailed(f"{manifest_path} carries no manifest_sha256 -- not a valid manifest")
    recorded_manifest_hash = full["manifest_sha256"]
    body = {k: v for k, v in full.items() if k != "manifest_sha256"}
    actual_manifest_hash = hashlib.sha256(_canonical_manifest_json(body).encode("utf-8")).hexdigest()
    if actual_manifest_hash != recorded_manifest_hash:
        raise TransferVerificationFailed(
            f"manifest {manifest_path} itself is corrupted or altered: recomputed hash "
            f"{actual_manifest_hash} != recorded {recorded_manifest_hash}"
        )
    mismatches: list[str] = []
    for entry in body["files"]:
        path = Path(files_root) / Path(entry["path"]).name if files_root is not None else Path(entry["path"])
        if not path.is_file():
            mismatches.append(f"{path}: file missing at transfer destination")
            continue
        actual = _d.compute_file_sha256(path)
        if actual != entry["sha256"]:
            mismatches.append(f"{path}: sha256 mismatch (manifest {entry['sha256']}, actual {actual})")
    if mismatches:
        raise TransferVerificationFailed(
            "transfer verification failed for " + str(len(mismatches)) + " file(s):\n  - " + "\n  - ".join(mismatches)
        )
    return full


def stamp_manifest_with_selection(manifest: dict, selections: list[dict]) -> dict:
    """Stage 4 tail: returns a NEW manifest dict (the original,
    transfer-verified manifest is never mutated in place, so its own
    `manifest_sha256` stays a valid record of what stage 3 verified) with
    `label=SEALED_LABEL` stamped onto every CONFIRMATION file entry whose
    dose is in that selection's `unselected` list, for the matching
    (concept_id, pairing_id, direction). Selected doses are left
    unstamped (`label=None`) -- a dose cannot be both the one that ships
    and one that may never be judged, per the consumer's own check."""
    unselected_by_cell: dict[tuple[str, str, str], set[int]] = {}
    for selection in selections:
        key = (selection["concept_id"], selection["pairing_id"], selection["direction"])
        unselected_by_cell[key] = set(selection.get("unselected") or ())

    stamped_files = []
    for entry in manifest["files"]:
        entry = dict(entry)
        key = (entry["concept_id"], entry["pairing_id"], entry["direction"])
        if entry["purpose"] == "confirmation" and entry["dose"] in unselected_by_cell.get(key, set()):
            entry["label"] = SEALED_LABEL
        stamped_files.append(entry)
    return {**manifest, "files": stamped_files}
