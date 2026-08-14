"""Stages 1-3 of the frozen one-allocation dose-generation protocol
(`protocols/final_pairing/v1/one_allocation_dose_generation.json`, v1.0.0,
`gating: true`), EXTENDED by `protocols/final_pairing/v1/generation_
settings.json` (v1.0.0, `gating: true`): GPU-side GENERATION ONLY, on the
SAME offline Tamia allocation as G-A/B/C discovery (stage 1, already
implemented in `final_pairing_concept_discovery.py`'s grid functions),
plus stage 3 (off-cluster transfer verification).

MANIFEST SHAPE IS DICTATED BY ENGINEER 3'S REAL, ENFORCING VALIDATOR
(`scripts/concept_bundle_publish.py` at commit 67ad4ef -- `dose-check`/
`dose_generation_problems`, this module's earlier ground truth at
ac9ea40, is GONE, superseded by `binding-check`): ONE PHYSICAL MANIFEST
per (run_id, configuration, concept_id, pairing_id, direction), with
FLAT top-level identity fields (no nested `model`/`sae`/`concepts`
objects, no self-declared manifest hash -- `additionalProperties: false`
refuses both) and file entries carrying a SCALAR `seed` (not a list) and
NO selection outcome. The manifest-level `inventory_stage=PRE_SELECTION`
marks the immutable inventory; the later selection record is the sole
selection authority. See `write_generation_manifest`'s docstring for the
exact field-by-field mapping.

`generation_settings.json` (consumed here even though Engineer 3's own
validator for it, commit dfe2e1b, has not landed yet -- implemented now
per explicit instruction, not withheld pending reconciliation) adds, on
top of the base schema: (1) EXPLICIT, frozen sampling kwargs (`final_
pairing_concept_discovery.GENERATION_SETTINGS`) -- `do_sample=True`,
correcting a real defect where greedy decoding made three "independent"
confirmation repeats byte-identical; (2) bilingual generation -- 15
sweep / 20 confirmation prompts EACH in en and fr, never split across
them; (3) a paired CONTROL (no-intervention) generation for every
(prompt, seed) used by ANY dose, sharing that EXACT seed, computed once
and referenced (`control_ref`) from every dose file; (4) a fixed,
G-A/B/C-independent concept processing order (`CAUSAL_GENERATION_ORDER`).
REAL PROMPT IDENTITIES (P0 CONTINUE, 2026-08-13): the prior disclosed gap
-- callers supplying bare prompt strings instead of the frozen artifact's
own rows -- is CLOSED. `generate_dose_file`/`generate_control_file` now
take `prompts: list[dict]`, i.e. the frozen artifact's own row dicts
(`prompt_id`/`text`/`locale`/`split`/`ordinal`, verbatim), never bare
strings; `select_generation_prompt_rows` below is the ONE place that
selects which rows (per `generation_settings.json` section 2's
"ordinals 01-15/01-20 of that concept's held-out split, ascending by
prompt_id" rule -- amplify reads `heldout_neutral`, suppress reads
`heldout_eliciting`, per section 3's "AMPLIFY runs on the neutral
held-out substrate and SUPPRESS on the eliciting substrate"). Every
per-generation record inside a physical file's own `generations` list
now carries the row's real `prompt_id`/`split`/`ordinal` (never a
synthetic `f"{purpose}_{prompt_index}"`); `control_ref` resolution is
therefore also real: a steered generation and its paired control
generation are built from the SAME row list in the SAME order, so they
share the same real `prompt_id` (and, by `SAME_SEED_IS_MANDATORY`, the
same seed) by construction.

MANIFEST GRANULARITY IS PER GENERATION, NOT PER PHYSICAL FILE (resolved
against `conformance/concept_bundle/discovery_input_schema.json` schema
2.0, `eng3/concept-bundle @ 67ad4ef`, status "DECLARED BY ENGINEER 3,
AWAITING ENGINEER 1 RATIFICATION" -- ratified here by implementing to
it): `manifest_file_required` there lists BOTH `dose` (one physical file
per dose) AND `prompt_id` (one row per generation) as required on every
`files[]` entry. The only shape consistent with both is: ONE PHYSICAL
JSON FILE per (concept, pairing, direction, dose, purpose, locale)
(ADDITION_3, unchanged), but ONE MANIFEST `files[]` ENTRY PER
GENERATION inside it -- many entries share the same `path`/`sha256`
(they name the same physical file) while each carries its own scalar
`seed`/`prompt_id`/`truncated`. `GenerationFileRecord.to_manifest_file_
entries()` (plural; the old singular `to_manifest_file_entry` is gone)
fans out exactly this way. This also makes the total manifest row count
per concept exactly `GENERATIONS_PER_CONCEPT` (1800), not
`DOSE_FILES_PER_CONCEPT` (48).

The manifest also now carries the REST of that same schema's
`manifest_required` list, previously optional or absent:
`generation_kwargs`, `chat_template_identity`, `locales_complete`
(already present), plus NEW required fields `generation_settings_path`/
`generation_settings_version`/`generation_settings_sha256` (this
module's own frozen constants) and `causal_order_position`/
`skipped_for_gate_failure` (see `causal_order_position_for` and
`run_generation_mode`'s CLI below).

HARD STOP, STRUCTURAL, NOT MERELY DOCUMENTED: this module never imports
`final_pairing_causal_judge` or `lodestar`, at module scope or inside any
function body -- "Any judge call from inside the GPU allocation" is one
of the protocol's own named hard stops, and the consumer's own validator
independently refuses any judging-shaped field
(score/verdict/rubric/judge/... ) inside a generation manifest entry.
`test_final_pairing_one_allocation_generation.py` asserts the import
guarantee via an AST scan of this file's own source.

WHAT THIS MODULE DOES NOT DO, ON PURPOSE (stages 4-5, a SEPARATE
machine/stage per the same protocol): judge the sweep (and its paired
controls, per the extension), select LOW/MEDIUM/HIGH, write or commit
`selection_record.json`, or judge confirmation outputs (and THEIR paired
controls). That is `final_pairing_judge_cli.py`'s job -- see that module.

ADDITION_1 (seed disjointness): `derive_seed`/`derive_seeds` salt by
NAMESPACE ("sweep"/"confirmation") in addition to every identifying
field (locale included, dose deliberately EXCLUDED -- see `derive_seed`'s
own docstring), so S_sweep and S_conf are disjoint BY CONSTRUCTION;
`assert_seed_sets_disjoint` is still run explicitly on every produced
set.

ADDITION_3 (one file per dose): `generate_dose_file` writes exactly one
JSON file per (concept, pairing, direction, dose, purpose, locale) --
never a shared file across doses, so reading the selected doses' files
structurally cannot open an unselected one. Filenames encode the dose.

ADDITION_4 (concept-complete ordering + wall-time preflight):
`assess_concept_generation_readiness` is the NOT_ATTEMPTED gate --
`generate_concept_complete` itself always finishes one whole concept
(both directions, both locales, all five doses, sweep AND confirmation,
plus every paired control) or is not started at all; there is no
partial-concept file layout.

CANONICAL DOSE IDENTIFIERS (protocols/final_pairing/v1/causal_dose_grid.json,
commit c43a976, hash-pinned via `validate_causal_dose_grid_protocol_hash`):
every dose is identified by a canonical STRING `dose_id` ("A1".."A5" for
Amplify, "S1".."S5" for Suppress) -- `files[].dose`, filenames, and
selection-record dose references all carry the dose_id, NEVER a float or
a float-derived string ("0.5x", "ABLATE"). `value_in_max_units` travels
alongside as DATA on `DoseSpec`, never as a key and never compared or
ordered against another dose's value. `load_causal_dose_grid` is the
ONLY source of dose values in this module -- there is no CLI flag or
caller-supplied override (NO_TUNING_AFTER_ACTIVATIONS: no dose may be
added, removed, rescaled, reordered, or reinterpreted). Suppress HIGH is
NOT defined as ABLATE/S5 by fiat: a selection whose HIGH is "S4" is
valid, since LOW/MEDIUM/HIGH are chosen from the judged sweep under the
frozen selection rules, not assigned by dose-grid position.

MANIFEST-LEVEL `dose_grid` (schema 5.0, `conformance/concept_bundle/
discovery_input_schema.json` at commit 3aff107, `eng3/concept-bundle`):
the real consumer's validator (`concept_bundle_
publish.dose_grid_problems`) now requires each direction's OWN generation
manifest to carry its full five-point grid, MANIFEST LEVEL (one array,
never repeated per file) -- `operation` and `value_in_max_units` are
properties of the GRID, not of a generation. `_dose_grid_manifest_points`
below builds this array from the SAME `DoseSpec` list `load_causal_dose_
grid` returns, translating `DoseSpec.kind` ("clamp"/"ablate", this
module's own lowercase convention) to the frozen artifact's own UPPERCASE
`operation` values ("CLAMP"/"ABLATE") -- `dose_grid_problems` checks
`operation` against `causal_dose_grid.json`'s own per-point value
verbatim, and that artifact spells it uppercase. `unit`/`unit_source` are
non-empty descriptive strings the consumer validates only for
non-emptiness (never compared against a fixed vocabulary); this module
reuses the same `"corpus_max_multiple"`/`"background corpus max
activation"` pair already established for `calibration.directions.
<direction>` in `final_pairing_evidence_document.build_direction_block`'s
callers, rather than inventing a second naming convention for the same
denominator. `causal_dose_grid_path`/`_version`/`_sha256` bind the
manifest to the exact frozen artifact identity, mirroring this module's
own `CAUSAL_DOSE_GRID_PROTOCOL_*` constants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))  # so `import final_pairing_concept_discovery` resolves when this file is run directly as a script

DIRECTIONS: tuple[str, ...] = ("amplify", "suppress")
SWEEP_PROMPTS_PER_DIRECTION = 15  # PER LOCALE (generation_settings.json section 2)
SWEEP_REPEATS = 1
CONFIRMATION_PROMPTS_PER_DIRECTION = 20  # PER LOCALE
CONFIRMATION_REPEATS = 3
DOSES_PER_DIRECTION = 5
LOCALES: tuple[str, ...] = ("en", "fr")

#: STEERED generations only: 2 directions x 2 locales x 5 doses x
#: (15 sweep x 1 repeat + 20 confirmation x 3 repeats) = 2x2x5x75 = 1500.
STEERED_GENERATIONS_PER_CONCEPT = len(DIRECTIONS) * len(LOCALES) * DOSES_PER_DIRECTION * (
    SWEEP_PROMPTS_PER_DIRECTION * SWEEP_REPEATS + CONFIRMATION_PROMPTS_PER_DIRECTION * CONFIRMATION_REPEATS
)
#: CONTROL generations: one per (prompt, seed), NOT multiplied by dose
#: (`generation_settings.json`: "one control ... serves all five doses").
#: 2 directions x 2 locales x (15 sweep + 60 confirmation) = 2x2x75 = 300.
CONTROL_GENERATIONS_PER_CONCEPT = len(DIRECTIONS) * len(LOCALES) * (
    SWEEP_PROMPTS_PER_DIRECTION * SWEEP_REPEATS + CONFIRMATION_PROMPTS_PER_DIRECTION * CONFIRMATION_REPEATS
)
#: The real total real-model calls one concept requires -- what a wall-time
#: estimate must be based on, not `STEERED_GENERATIONS_PER_CONCEPT` alone.
GENERATIONS_PER_CONCEPT = STEERED_GENERATIONS_PER_CONCEPT + CONTROL_GENERATIONS_PER_CONCEPT

#: Physical files one complete concept produces: steered = 2 directions x
#: 2 locales x 5 doses x 2 purposes = 40; control = 2 directions x 2
#: locales x 2 purposes (NOT multiplied by dose) = 8. Total 48.
STEERED_DOSE_FILES_PER_CONCEPT = len(DIRECTIONS) * len(LOCALES) * DOSES_PER_DIRECTION * 2
CONTROL_FILES_PER_CONCEPT = len(DIRECTIONS) * len(LOCALES) * 2
DOSE_FILES_PER_CONCEPT = STEERED_DOSE_FILES_PER_CONCEPT + CONTROL_FILES_PER_CONCEPT

ONE_ALLOCATION_PROTOCOL_PATH = "protocols/final_pairing/v1/one_allocation_dose_generation.json"
ONE_ALLOCATION_PROTOCOL_VERSION = "final-pairing-one-allocation-dose-generation/1.0.0"
ONE_ALLOCATION_PROTOCOL_COMMIT = "5a5175d36eac9802b45f76aeb5b52ff6b25220a8"
ONE_ALLOCATION_PROTOCOL_SHA256 = "bd1974b4c44802fa7a49fb7a4ed65df78a9ba66cdca78bb6fc0da69cf42252cf"

GENERATION_SETTINGS_PROTOCOL_PATH = "protocols/final_pairing/v1/generation_settings.json"
GENERATION_SETTINGS_PROTOCOL_VERSION = "final-pairing-generation-settings/1.0.0"
GENERATION_SETTINGS_PROTOCOL_SHA256 = "975e90e0271e750aea8f871f4776d2a3d0169ea4fe410e544081957907e613b1"

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


def validate_generation_settings_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if `generation_settings.json`'s actual bytes don't
    match the pinned hash -- same discipline as `validate_one_allocation_
    protocol_hash` above."""
    path = Path(repo_root) / GENERATION_SETTINGS_PROTOCOL_PATH
    if not path.is_file():
        raise TransferVerificationFailed(f"generation-settings protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != GENERATION_SETTINGS_PROTOCOL_SHA256:
        raise TransferVerificationFailed(
            f"{path} sha256={actual!r} != pinned {GENERATION_SETTINGS_PROTOCOL_SHA256!r} -- refusing to "
            f"generate against an altered or unpinned generation-settings protocol."
        )
    return actual


CAUSAL_DOSE_GRID_PROTOCOL_PATH = "protocols/final_pairing/v1/causal_dose_grid.json"
CAUSAL_DOSE_GRID_PROTOCOL_VERSION = "final-pairing-causal-dose-grid/1.0.0"
CAUSAL_DOSE_GRID_PROTOCOL_COMMIT = "c43a976785a3a7e2e0fa4c8a9a78e1a33a88d37e"
CAUSAL_DOSE_GRID_PROTOCOL_SHA256 = "6afc4a85d1a8e385bfe366e51767451839c6208e88c396a382bdf02a5e3c5c55"


def validate_causal_dose_grid_protocol_hash(repo_root: str | Path) -> str:
    """Fails closed if `causal_dose_grid.json`'s actual bytes don't match
    the pinned hash -- same discipline as `validate_one_allocation_
    protocol_hash`/`validate_generation_settings_protocol_hash` above."""
    path = Path(repo_root) / CAUSAL_DOSE_GRID_PROTOCOL_PATH
    if not path.is_file():
        raise TransferVerificationFailed(f"causal dose grid protocol not found at {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != CAUSAL_DOSE_GRID_PROTOCOL_SHA256:
        raise TransferVerificationFailed(
            f"{path} sha256={actual!r} != pinned {CAUSAL_DOSE_GRID_PROTOCOL_SHA256!r} -- refusing to "
            f"generate against an altered or unpinned causal dose grid."
        )
    return actual


def derive_seed(
    *, namespace: Literal["sweep", "confirmation"], concept_id: str, pairing_id: str, direction: str,
    locale: str, prompt_index: int, repeat_index: int,
) -> int:
    """Deterministic, reproducible seed for one generation. Salted by
    `namespace` ("sweep" vs "confirmation") in addition to every other
    identifying field, so S_sweep and S_conf are disjoint BY
    CONSTRUCTION -- `assert_seed_sets_disjoint` below still verifies this
    explicitly rather than trusting the construction alone.

    DELIBERATELY NOT salted by dose: `generation_settings.json`'s control
    arm requires the SAME seed to be reused across all five doses at a
    given (prompt, repeat) AND by that (prompt, repeat)'s one shared
    control generation ("one control per (prompt, seed) serves all five
    doses"). Salting by dose (as an earlier version of this function did)
    would give every dose its own distinct seed and make that sharing
    impossible."""
    payload = "|".join([
        "final-pairing-one-allocation-v1", namespace, concept_id, pairing_id, direction,
        locale, str(prompt_index), str(repeat_index),
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def derive_seeds(
    *, namespace: Literal["sweep", "confirmation"], concept_id: str, pairing_id: str, direction: str,
    locale: str, n_prompts: int, n_repeats: int,
) -> list[int]:
    """The full, ordered seed list for one (namespace, locale) cell --
    exactly what `generate_dose_file`/`generate_control_file` require as
    their shared `seeds` parameter, and what a caller derives ONCE per
    (direction, purpose, locale) and then reuses for the control file and
    for every one of that purpose's five dose files."""
    return [
        derive_seed(
            namespace=namespace, concept_id=concept_id, pairing_id=pairing_id, direction=direction,
            locale=locale, prompt_index=prompt_index, repeat_index=repeat_index,
        )
        for prompt_index in range(n_prompts)
        for repeat_index in range(n_repeats)
    ]


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
    """`dose_id` is the CANONICAL identifier (causal_dose_grid.json,
    commit c43a976: "A1".."A5" for Amplify, "S1".."S5" for Suppress) --
    the ONLY form `files[].dose`, filenames, and selection-record dose
    references may carry. `value_in_max_units` travels alongside as DATA
    (never as a key, never compared or ordered against another dose's
    value) -- S5 (ABLATE) carries `dose_id="S5"` and no numeric value at
    all, which is precisely why an identifier, not a value, is canonical."""
    dose_id: str
    kind: Literal["clamp", "ablate"]
    value_in_max_units: float | None = None

    def __post_init__(self) -> None:
        if self.kind == "ablate" and self.value_in_max_units is not None:
            raise ValueError("an ablate dose carries no value_in_max_units, unit, or unit_source")
        if self.kind == "clamp" and self.value_in_max_units is None:
            raise ValueError("a clamp dose requires value_in_max_units")


#: causal_dose_grid.json's own frozen, EXACT grid values (hard stops "An
#: AMPLIFY grid other than exactly [...]" / "A SUPPRESS CLAMP grid other
#: than exactly [...]" / "The prohibited Suppress sequence 4.0, 2.0, 1.0,
#: 0.5 appearing anywhere"). Hardcoded here, not merely read off whatever
#: bytes the JSON file on disk happens to contain at call time, so
#: `build_amplify_dose_grid`/`build_suppress_dose_grid` enforce the exact
#: values as an invariant of THIS CODE -- the same defense-in-depth
#: relationship as every other hash-pinned frozen artifact in this module.
FROZEN_AMPLIFY_VALUES: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0)
FROZEN_SUPPRESS_CLAMP_VALUES: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1)
#: Named and explicitly rejected, never merely absent from the accepted
#: set: tops out at 4.0x (well above natural firing -- an amplification)
#: and bottoms out at 0.5x (barely a suppression at all), even though it
#: is (like the frozen sequence) strictly descending.
PROHIBITED_SUPPRESS_CLAMP_VALUES: tuple[float, ...] = (4.0, 2.0, 1.0, 0.5)


def build_amplify_dose_grid(doses: tuple[tuple[str, float], ...]) -> list[DoseSpec]:
    """Amplify's five-point grid: `doses` is `((dose_id, value_in_max_
    units), ...)`, exactly 5 entries, distinct dose_ids, and values
    EXACTLY `FROZEN_AMPLIFY_VALUES` in ascending order (causal_dose_
    grid.json: "ordering: ASCENDING by value_in_max_units" -- the
    MEDIUM selection rule takes the dose nearest the geometric midpoint
    of LOW/HIGH, which only lands sensibly on an ascending, geometric
    grid). Real callers get `doses` from `load_causal_dose_grid`, never
    from an operator-supplied CLI value."""
    if len(doses) != DOSES_PER_DIRECTION:
        raise ValueError(f"amplify dose grid must have exactly {DOSES_PER_DIRECTION} points, got {len(doses)}")
    ids = [dose_id for dose_id, _ in doses]
    values = tuple(value for _, value in doses)
    if len(set(ids)) != DOSES_PER_DIRECTION:
        raise ValueError(f"amplify dose_ids must be distinct, got {ids}")
    if values != FROZEN_AMPLIFY_VALUES:
        raise ValueError(
            f"amplify dose grid values must be exactly {FROZEN_AMPLIFY_VALUES}, ascending (causal_dose_"
            f"grid.json hard stop); got {values}"
        )
    return [DoseSpec(dose_id=dose_id, kind="clamp", value_in_max_units=value) for dose_id, value in doses]


def build_suppress_dose_grid(clamp_doses: tuple[tuple[str, float], ...], *, ablate_dose_id: str) -> list[DoseSpec]:
    """Suppress's five-point grid: `clamp_doses` is `((dose_id, value_in_
    max_units), ...)`, exactly 4 entries with values EXACTLY `FROZEN_
    SUPPRESS_CLAMP_VALUES` (causal_dose_grid.json's PROHIBITED_
    SUBSTITUTION hard stop: the illustrative sequence `PROHIBITED_
    SUPPRESS_CLAMP_VALUES` is rejected even though it is also strictly
    descending), plus `ablate_dose_id` (S5 by the frozen artifact's own
    convention) appended as the fifth, terminal grid point -- ABLATE
    carries no value_in_max_units, unit, or unit_source (`DoseSpec.
    __post_init__` enforces this). Real callers get both arguments from
    `load_causal_dose_grid`, never from an operator-supplied CLI value."""
    if len(clamp_doses) != DOSES_PER_DIRECTION - 1:
        raise ValueError(
            f"suppress clamp portion must have exactly {DOSES_PER_DIRECTION - 1} points "
            f"(plus ABLATE as the fifth), got {len(clamp_doses)}"
        )
    ids = [dose_id for dose_id, _ in clamp_doses]
    values = tuple(value for _, value in clamp_doses)
    if len(set([*ids, ablate_dose_id])) != DOSES_PER_DIRECTION:
        raise ValueError(f"suppress dose_ids (4 clamp + 1 ablate) must be distinct, got {[*ids, ablate_dose_id]}")
    if values != FROZEN_SUPPRESS_CLAMP_VALUES:
        raise ValueError(
            f"suppress CLAMP grid must be exactly {FROZEN_SUPPRESS_CLAMP_VALUES} (causal_dose_grid.json "
            f"PROHIBITED_SUBSTITUTION hard stop -- this rejects {PROHIBITED_SUPPRESS_CLAMP_VALUES} even "
            f"though it is also strictly descending); got {values}"
        )
    return [DoseSpec(dose_id=dose_id, kind="clamp", value_in_max_units=value) for dose_id, value in clamp_doses] + [
        DoseSpec(dose_id=ablate_dose_id, kind="ablate")
    ]


def load_causal_dose_grid(repo_root: str | Path) -> tuple[list[DoseSpec], list[DoseSpec]]:
    """Reads `causal_dose_grid.json` (hash-pinned; validated first) and
    builds the frozen Amplify/Suppress dose grids from ITS OWN dose_id +
    value_in_max_units pairs -- the ONLY source of dose values in this
    module. There is no CLI flag or caller-supplied override that can
    substitute a different grid (`NO_TUNING_AFTER_ACTIVATIONS`: no dose
    may be added, removed, rescaled, reordered, or reinterpreted after any
    activation is computed). `build_amplify_dose_grid`/`build_suppress_
    dose_grid` still independently re-verify the exact frozen values (see
    their own docstrings) -- this function does not shortcut that check
    by trusting the JSON's shape alone."""
    validate_causal_dose_grid_protocol_hash(repo_root)
    path = Path(repo_root) / CAUSAL_DOSE_GRID_PROTOCOL_PATH
    data = json.loads(path.read_text(encoding="utf-8"))

    amplify_points = sorted(data["AMPLIFY"]["grid"], key=lambda pt: pt["index"])
    amplify_doses = tuple((pt["dose_id"], pt["value_in_max_units"]) for pt in amplify_points)

    suppress_points = sorted(data["SUPPRESS"]["grid"], key=lambda pt: pt["index"])
    clamp_points = [pt for pt in suppress_points if pt["operation"] == "CLAMP"]
    ablate_points = [pt for pt in suppress_points if pt["operation"] == "ABLATE"]
    if len(ablate_points) != 1:
        raise ValueError(
            f"causal_dose_grid.json SUPPRESS grid must carry exactly one ABLATE point, found {len(ablate_points)}"
        )
    suppress_clamp_doses = tuple((pt["dose_id"], pt["value_in_max_units"]) for pt in clamp_points)

    amplify_grid = build_amplify_dose_grid(amplify_doses)
    suppress_grid = build_suppress_dose_grid(suppress_clamp_doses, ablate_dose_id=ablate_points[0]["dose_id"])
    return amplify_grid, suppress_grid


#: `generation_manifests.dose_grid_encoding` (schema 5.0, commit 3aff107):
#: every CLAMP point names the denominator `value_in_max_units` multiplies
#: -- a non-empty string, validated for non-emptiness only, never compared
#: against a fixed vocabulary. Reuses the SAME pair `final_pairing_
#: evidence_document.build_direction_block`'s own callers already use for
#: `calibration.directions.<direction>.unit`/`unit_source`, rather than
#: inventing a second name for the same background-corpus-max
#: denominator.
DOSE_GRID_UNIT = "corpus_max_multiple"
DOSE_GRID_UNIT_SOURCE = "background corpus max activation"


def _dose_grid_manifest_points(dose_grid: list[DoseSpec]) -> list[dict[str, Any]]:
    """Builds ONE direction's manifest-level `dose_grid` array (schema 5.0's
    `dose_grid_encoding`: MANIFEST LEVEL, one array of five points,
    `additionalProperties: false` per point) from the SAME ordered
    `DoseSpec` list `load_causal_dose_grid` returns -- `index` is this
    list's own 1-based position, which matches the frozen artifact's own
    `index` field exactly because `load_causal_dose_grid` sorts by that
    same field before building. `operation` is emitted UPPERCASE
    ("CLAMP"/"ABLATE"), translating `DoseSpec.kind`'s lowercase
    convention to match `causal_dose_grid.json`'s own spelling, which
    `dose_grid_problems` checks byte-for-byte. The ABLATE point's
    `value_in_max_units`/`unit`/`unit_source` are explicit `None`
    (JSON `null`), mirroring the frozen artifact's own S5 point shape
    verbatim, rather than omitted keys -- either is accepted by the
    consumer's own prohibition check (`row.get(field) is not None`), but
    matching the artifact's own shape is clearer to a reader diffing the
    two side by side. A CLAMP point carries no `weight` key at all (the
    consumer's per-point encoding is closed and does not permit one
    there)."""
    points: list[dict[str, Any]] = []
    for index, dose in enumerate(dose_grid, start=1):
        if dose.kind == "ablate":
            points.append({
                "index": index, "dose_id": dose.dose_id, "operation": "ABLATE",
                "value_in_max_units": None, "unit": None, "unit_source": None,
                "weight": 1.0,
            })
        else:
            points.append({
                "index": index, "dose_id": dose.dose_id, "operation": "CLAMP",
                "value_in_max_units": dose.value_in_max_units,
                "unit": DOSE_GRID_UNIT, "unit_source": DOSE_GRID_UNIT_SOURCE,
            })
    return points


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


#: Manifest immutability correction (protocols/final_pairing/v1/
#: manifest_immutability_correction.json, final-pairing-manifest-
#: immutability/1.0.0, commit 2dc9e338c12db1c1f3939a9f709f8af816ad8272):
#: the BOUND generation manifest is written ONCE, at transfer, and NEVER
#: rewritten -- it carries NO per-file selection-outcome field at all.
#: `SELECTED_STATUS`/`UNUSED_STATUS` survive ONLY as internal vocabulary
#: for `stamp_manifest_with_selection`'s own DERIVED, non-promotable
#: reading-aid output (see that function's docstring) -- neither name is
#: emitted anywhere in `to_manifest_file_entries()`/`write_generation_
#: manifest` below. `SEALED_LABEL` is kept as an alias for existing
#: callers (`final_pairing_judge_cli.py`) that reference the sealed value
#: by name.
SELECTED_STATUS = "SELECTED"
UNUSED_STATUS = "UNUSED_FOR_SELECTION_OR_CLAIM"
SEALED_LABEL = UNUSED_STATUS
SELECTION_STATUSES: tuple[str, ...] = (SELECTED_STATUS, UNUSED_STATUS)

#: The ONE permitted manifest-level marker the immutability correction
#: allows in place of a per-file flag: every bound manifest this module
#: writes is, by construction, pre-selection (selection happens later, on
#: a different machine, against a DIFFERENT artifact -- the selection
#: record) -- so this is always the same constant, never computed.
INVENTORY_STAGE_PRE_SELECTION = "PRE_SELECTION"

#: The ratified `generation_manifests.manifest_required` list from
#: `conformance/concept_bundle/discovery_input_schema.json` schema 5.0
#: (`eng3/concept-bundle @ 3aff107`, status "DECLARED BY ENGINEER 3,
#: AWAITING ENGINEER 1 RATIFICATION" -- ratified here by implementing to
#: it) -- every top-level manifest field, exhaustively (that schema
#: declares every object closed: "unknown fields are refused"). Mirrored
#: here (never imported: that package does not exist on this branch) so
#: `verify_generation_manifest` can check a manifest is at least
#: well-formed before transfer-verifying its files. Supersedes the
#: narrower 16-field list this module previously targeted at
#: `concept_bundle_publish.py` commit 67ad4ef, which predates the
#: `generation_settings.json` extension (`generation_kwargs`/
#: `chat_template_identity`/`locales_complete`/`generation_settings_*`/
#: `causal_order_position`/`skipped_for_gate_failure` are all NEW here).
#: `inventory_stage` is the manifest-immutability correction's own addition
#: (commit 2dc9e338), replacing the per-file `selection_status` this list
#: used to require indirectly via `MANIFEST_FILE_REQUIRED_FIELDS`.
#: `dose_grid`/`causal_dose_grid_path`/`_version`/`_sha256` are schema
#: 5.0's own addition (commit 3aff107, eng3/concept-bundle) --
#: the manifest-level five-point dose grid and its binding to the frozen
#: `causal_dose_grid.json` artifact, checked point-by-point against it.
MANIFEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id", "source_commit", "configuration", "concept_id", "pairing_id",
    "model_revision", "sae_revision", "release", "loader_sae_id", "scientific_sae_id",
    "params_measured_sha256", "direction", "files", "completeness", "protocol_path", "protocol_sha256",
    "generation_kwargs", "chat_template_identity", "locales_complete",
    "generation_settings_path", "generation_settings_version", "generation_settings_sha256",
    "causal_order_position", "skipped_for_gate_failure", "inventory_stage",
    "dose_grid", "causal_dose_grid_path", "causal_dose_grid_version", "causal_dose_grid_sha256",
)

#: The ratified `generation_manifests.manifest_file_required` list from
#: the same schema-5.0 declaration -- every `files[]` entry field,
#: exhaustively. `prompt_id` (per-generation, real) and `dose` (per
#: physical file, prohibited on CONTROL) coexisting is exactly what
#: forces the "one manifest entry per generation, many entries sharing
#: one physical file's path" granularity `to_manifest_file_entries`
#: implements -- see this module's own docstring.
#:
#: NO `selection_status` here (manifest-immutability correction, commit
#: 2dc9e338): the bound manifest carries no per-file selection-outcome
#: field of any kind -- the selection record is the sole selection
#: authority.
MANIFEST_FILE_REQUIRED_FIELDS: tuple[str, ...] = (
    "dose", "purpose", "path", "sha256", "seed", "locale", "prompt_id",
    "control_ref", "truncated",
)

#: `generation_settings.json` section 2 ("2_bilingual_counts"): sweep and
#: confirmation prompts are drawn PER LOCALE (15/20 EACH in en and fr, not
#: 15/20 split across both) -- `SWEEP_PROMPTS_PER_DIRECTION`/`CONFIRMATION_
#: PROMPTS_PER_DIRECTION` above are therefore PER-LOCALE counts, and this
#: module now generates once per locale, never once total.
LOCALES: tuple[str, ...] = ("en", "fr")

#: generation_settings.json section 4 ("4_causal_generation_order"): FIXED,
#: pre-registered before the G-A/B/C grid completes, and INDEPENDENT of its
#: outcomes -- a concept that fails G-A/B/C is SKIPPED, but the relative
#: order among survivors is never reshuffled by how well they scored.
CAUSAL_GENERATION_ORDER: tuple[str, ...] = (
    "formal_register", "cheese", "chess", "jazz", "courtroom", "astronomy",
    "volcanic_activity", "sailing", "clinical_examination", "mountaineering",
    "desert", "winter_snow", "beekeeping", "political_framing",
)


def order_concepts_for_causal_generation(concept_ids: list[str]) -> list[str]:
    """Returns exactly the concept_ids present in `concept_ids`, in the
    FIXED `CAUSAL_GENERATION_ORDER` -- a concept that failed G-A/B/C (and
    so is absent from `concept_ids`) is skipped, never reordered around.
    Raises if `concept_ids` names anything outside the frozen 14, since an
    unrecognized concept_id has no registered position to skip to."""
    unknown = sorted(set(concept_ids) - set(CAUSAL_GENERATION_ORDER))
    if unknown:
        raise ValueError(f"concept_id(s) {unknown} are not in the frozen CAUSAL_GENERATION_ORDER")
    present = set(concept_ids)
    return [c for c in CAUSAL_GENERATION_ORDER if c in present]


def causal_order_position_for(concept_id: str) -> int:
    """The concept's 1-based, FIXED position in `CAUSAL_GENERATION_ORDER`
    (`formal_register`=1, ..., `political_framing`=14) -- the exact value
    `generation_settings.json` section 4 requires the manifest to record,
    independent of whether generation for this concept actually ran."""
    try:
        return CAUSAL_GENERATION_ORDER.index(concept_id) + 1
    except ValueError:
        raise ValueError(f"concept_id {concept_id!r} is not in the frozen CAUSAL_GENERATION_ORDER") from None


#: `generation_settings.json` section 3: "AMPLIFY runs on the neutral
#: held-out substrate and SUPPRESS on the eliciting substrate." Amplify's
#: intervention direction is `DoseSpec(kind="clamp"...)` and Suppress's is
#: `clamp`+`ablate`, but the SPLIT this constant governs is keyed on the
#: one-allocation DIRECTION name ("amplify"/"suppress"), never on
#: `DoseSpec.kind`.
GENERATION_SPLIT_BY_DIRECTION: dict[str, str] = {"amplify": "heldout_neutral", "suppress": "heldout_eliciting"}


def select_generation_prompt_rows(
    rows: list[dict], *, concept_id: str, direction: Literal["amplify", "suppress"], locale: str,
    purpose: Literal["sweep", "confirmation"],
) -> list[dict]:
    """The ONE place that selects which of the frozen prompt artifact's own
    rows back one-allocation generation, per `generation_settings.json`
    section 2's `sweep_subset_rule`: "the 15 sweep prompts are ordinals 01
    through 15 of that concept's held-out split, ascending by prompt_id.
    Confirmation uses ordinals 01 through 20" -- fully determined, zero
    discretion, since `prompt_id` is stable and the artifact is sorted.
    `direction` selects the split (`GENERATION_SPLIT_BY_DIRECTION`); doses
    only change EXTRACTION, never which rows.

    Returns the frozen artifact's own row dicts VERBATIM (never bare
    strings) -- callers read `row["text"]`/`row["prompt_id"]`/
    `row["split"]`/`row["ordinal"]` directly, so every generation this
    module writes carries the real frozen identity, not an invented one.
    Raises if fewer than the required count of rows exist, or if the
    selected rows' ordinals are not exactly 1..N (a corrupted or
    unexpectedly-reordered artifact must fail closed here, not silently
    hand back the wrong prompts)."""
    import final_pairing_concept_discovery as _d

    split = GENERATION_SPLIT_BY_DIRECTION[direction]
    candidates = _d.rows_for_concept(rows, concept_id=concept_id, locale=locale, split=split)
    candidates = sorted(candidates, key=lambda r: r["prompt_id"])
    n = SWEEP_PROMPTS_PER_DIRECTION if purpose == "sweep" else CONFIRMATION_PROMPTS_PER_DIRECTION
    if len(candidates) < n:
        raise ValueError(
            f"expected at least {n} '{split}' rows for concept_id={concept_id!r} locale={locale!r}, "
            f"found {len(candidates)}"
        )
    selected = candidates[:n]
    ordinals = [row["ordinal"] for row in selected]
    if ordinals != list(range(1, n + 1)):
        raise ValueError(
            f"expected ordinals 1..{n} ascending by prompt_id for concept_id={concept_id!r} locale={locale!r} "
            f"split={split!r}, got {ordinals} -- refusing to generate against an unexpectedly ordered artifact"
        )
    return selected


def _prefixed_sha256(hexdigest: str) -> str:
    """The manifest's own ruled digest encoding is `sha256:<64 hex>`
    (`discovery_input_schema.json` schema 5.0's `digest_encoding` note) --
    distinct from the discovery DOCUMENT's `pairing.params_sha256`, which
    is bare hex. Idempotent so a caller that already has a prefixed value
    is never double-prefixed."""
    return hexdigest if hexdigest.startswith("sha256:") else f"sha256:{hexdigest}"


@dataclass(frozen=True)
class GenerationFileRecord:
    """Internal bookkeeping for ONE physical file -- resumability, seed-
    disjointness checks, and control/steered pairing all need more than
    the real consumer's manifest schema carries. `to_manifest_file_
    entries()` (plural), NOT `dataclasses.asdict`, is what actually goes
    into a generation manifest: the real consumer's schema declares
    `additionalProperties: false` on every file entry, so serializing this
    dataclass wholesale would be refused for carrying unknown fields --
    and, per that same schema, ONE PHYSICAL FILE fans out into MANY
    manifest entries, one per generation (see this module's own docstring,
    "MANIFEST GRANULARITY IS PER GENERATION, NOT PER PHYSICAL FILE").

    `purpose='control'` files carry `dose_id=None`/`dose_kind=None`/
    `dose_value=None` (`generation_settings.json`'s manifest extension:
    "dose: prohibited on CONTROL entries -- a control has no dose") and
    `control_ref=None` (a control is not itself paired with a control);
    `purpose in ('sweep','confirmation')` files carry a real, canonical
    `dose_id` (causal_dose_grid.json: "A1".."A5"/"S1".."S5", never a
    float-derived string) and a non-None `control_ref` naming the shared
    control file's path.

    `prompt_ids`/`truncated_flags` are parallel arrays to `seeds` (one
    entry per generation, in the SAME order) -- the frozen artifact's own
    real `prompt_id` for that generation's row (never a synthetic
    `f"{purpose}_{prompt_index}"`) and whether THAT generation hit
    `max_new_tokens`, respectively. `seeds[i]`/`prompt_ids[i]`/
    `truncated_flags[i]` describe the SAME generation."""
    concept_id: str
    pairing_id: str
    direction: Literal["amplify", "suppress"]
    purpose: Literal["sweep", "confirmation", "control"]
    locale: Literal["en", "fr"]
    dose_id: str | None  # canonical "A1".."A5"/"S1".."S5"; None for purpose="control"
    dose_kind: Literal["clamp", "ablate"] | None
    dose_value: float | None
    n_prompts: int
    n_repeats: int
    seeds: list[int]  # every individual generation's seed, in order (bookkeeping + disjointness checks)
    prompt_ids: list[int | str]  # parallel to `seeds`: each generation's REAL frozen prompt_id
    truncated_flags: list[bool]  # parallel to `seeds`: each generation's own truncated flag
    path: str
    sha256: str  # bare 64-hex; prefixed only at manifest-serialization time
    control_ref: str | None  # the paired control file's path; None only for purpose="control" itself

    @property
    def truncated(self) -> bool:
        """True iff ANY generation in this file hit max_new_tokens --
        convenience/back-compat accessor; the manifest itself records
        `truncated_flags[i]` per generation, never this rollup."""
        return any(self.truncated_flags)

    def to_manifest_file_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for seed, prompt_id, truncated in zip(self.seeds, self.prompt_ids, self.truncated_flags, strict=True):
            entry: dict[str, Any] = {
                "purpose": self.purpose.upper(), "locale": self.locale, "path": self.path,
                "sha256": _prefixed_sha256(self.sha256), "seed": seed, "prompt_id": prompt_id,
                "truncated": truncated,
            }
            if self.dose_id is not None:
                entry["dose"] = self.dose_id
            if self.control_ref is not None:
                entry["control_ref"] = self.control_ref
            entries.append(entry)
        return entries


def _generation_filename(
    *, concept_id: str, pairing_id: str, direction: str, purpose: str, locale: str, dose_id: str | None,
) -> str:
    """Filenames encode the canonical `dose_id` ("A1".."A5"/"S1".."S5"),
    never a float (causal_dose_grid.json's own `filenames` rule)."""
    dose_part = "" if dose_id is None else f"__dose_{dose_id}"
    return f"{concept_id}__{pairing_id}__{direction}__{purpose}__{locale}{dose_part}.json"


def generate_control_file(
    backend, *, corpus_max: dict[int, float], positions: str, prompts: list[dict[str, Any]],
    purpose: Literal["sweep", "confirmation"], n_repeats: int, seeds: list[int], max_new_tokens: int,
    out_dir: str | Path, concept_id: str, pairing_id: str, direction: Literal["amplify", "suppress"],
    locale: str, generation_kwargs: dict[str, Any] | None = None, run_baseline_fn=None, hash_fn=None,
) -> GenerationFileRecord:
    """`generation_settings.json` section 3 ("3_control_arm"): ONE
    no-intervention file per (concept, pairing, direction, locale,
    purpose) -- shared/referenced by every dose file of that purpose
    (`"pairing_granularity": "... not_keyed_on_dose"`), using the EXACT
    SAME seeds as whichever steered generations it pairs with
    (`SAME_SEED_IS_MANDATORY`) -- `seeds` is therefore a REQUIRED
    parameter here, not derived internally, so a caller cannot
    accidentally give the control its own, different seed sequence.

    `prompts` is the frozen artifact's own ROW dicts (`prompt_id`/`text`/
    `split`/`ordinal`, e.g. from `select_generation_prompt_rows`), never
    bare strings -- every generation this writes carries its row's REAL
    `prompt_id`/`split`/`ordinal`, not an invented one."""
    if len(seeds) != len(prompts) * n_repeats:
        raise ValueError(
            f"generate_control_file requires exactly one seed per (prompt, repeat): got {len(seeds)} seeds for "
            f"{len(prompts)} prompts x {n_repeats} repeats"
        )
    if run_baseline_fn is None:
        import final_pairing_concept_discovery as _d

        run_baseline_fn = _d.run_baseline_generation
    if hash_fn is None:
        import final_pairing_concept_discovery as _d

        hash_fn = _d.compute_file_sha256

    generations: list[dict[str, Any]] = []
    prompt_ids: list[Any] = []
    truncated_flags: list[bool] = []
    seed_iter = iter(seeds)
    for prompt_index, row in enumerate(prompts):
        for repeat_index in range(n_repeats):
            seed = next(seed_iter)
            outcome = run_baseline_fn(
                backend, prompt=row["text"], seed=seed, max_new_tokens=max_new_tokens, positions=positions,
                generation_kwargs=generation_kwargs,
            )
            prompt_ids.append(row["prompt_id"])
            truncated_flags.append(outcome.truncated)
            generations.append({
                "prompt_id": row["prompt_id"], "prompt_index": prompt_index, "repeat_index": repeat_index,
                "prompt": row["text"], "locale": locale, "split": row["split"], "ordinal": row["ordinal"],
                "condition": "control", "seed": seed,
                "generated_text": outcome.generated_text, "truncated": outcome.truncated, "spec": outcome.spec,
            })

    payload = {
        "concept_id": concept_id, "pairing_id": pairing_id, "direction": direction, "purpose": purpose,
        "locale": locale, "generations": generations,
    }
    filename = _generation_filename(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose="control", locale=locale,
        dose_id=None,
    )
    path = Path(out_dir) / f"{filename[:-5]}__{purpose}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    digest = hash_fn(path)
    return GenerationFileRecord(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose="control", locale=locale,
        dose_id=None, dose_kind=None, dose_value=None, n_prompts=len(prompts), n_repeats=n_repeats,
        seeds=list(seeds), prompt_ids=prompt_ids, truncated_flags=truncated_flags,
        path=str(path), sha256=digest, control_ref=None,
    )


def generate_dose_file(
    backend, feature_indices: list[int], *, dose: DoseSpec, corpus_max: dict[int, float],
    positions: str, prompts: list[dict[str, Any]], purpose: Literal["sweep", "confirmation"], n_repeats: int,
    seeds: list[int], max_new_tokens: int, out_dir: str | Path,
    concept_id: str, pairing_id: str, direction: Literal["amplify", "suppress"], locale: str,
    control_ref: str, generation_kwargs: dict[str, Any] | None = None, run_intervention_fn=None, hash_fn=None,
) -> GenerationFileRecord:
    """Runs every (prompt, repeat) for ONE (concept, pairing, direction,
    dose, purpose, locale) cell and writes them all into ONE file
    (ADDITION_3). `seeds` is a REQUIRED, caller-supplied list (one per
    (prompt, repeat), in order) rather than derived internally: EVERY
    dose at the same (purpose, locale) must reuse the SAME seed sequence
    (so each steered generation shares its seed with the ONE control it
    pairs with, per `generation_settings.json`'s `SAME_SEED_IS_MANDATORY`)
    -- deriving a fresh, dose-salted sequence per call (as an earlier
    version of this module did) would make that impossible. `control_ref`
    names the shared control file (`generate_control_file`'s own output
    path) this dose's every generation pairs with.

    `prompts` is the frozen artifact's own ROW dicts, exactly as passed to
    the paired `generate_control_file` call for the SAME (purpose,
    locale) -- same row list, same order, same seeds, so the i-th steered
    generation here and the i-th control generation share the same real
    `prompt_id` and seed by construction (control_ref resolution therefore
    needs no separate lookup key beyond that shared ordering).

    Reuses the existing, already-tested `final_pairing_concept_discovery.
    run_intervention` by default -- injectable for tests."""
    if len(seeds) != len(prompts) * n_repeats:
        raise ValueError(
            f"generate_dose_file requires exactly one seed per (prompt, repeat): got {len(seeds)} seeds for "
            f"{len(prompts)} prompts x {n_repeats} repeats"
        )
    if run_intervention_fn is None:
        import final_pairing_concept_discovery as _d

        run_intervention_fn = _d.run_intervention
    if hash_fn is None:
        import final_pairing_concept_discovery as _d

        hash_fn = _d.compute_file_sha256

    generations: list[dict[str, Any]] = []
    prompt_ids: list[Any] = []
    truncated_flags: list[bool] = []
    seed_iter = iter(seeds)
    for prompt_index, row in enumerate(prompts):
        for repeat_index in range(n_repeats):
            seed = next(seed_iter)
            outcome = run_intervention_fn(
                backend, feature_indices,
                direction="ablate" if dose.kind == "ablate" else "clamp",
                value_in_max_units=dose.value_in_max_units or 0.0,
                corpus_max=corpus_max, positions=positions, prompt=row["text"], seed=seed, max_new_tokens=max_new_tokens,
                generation_kwargs=generation_kwargs,
            )
            prompt_ids.append(row["prompt_id"])
            truncated_flags.append(outcome.truncated)
            generations.append({
                "prompt_id": row["prompt_id"], "prompt_index": prompt_index, "repeat_index": repeat_index,
                "prompt": row["text"], "locale": locale, "split": row["split"], "ordinal": row["ordinal"],
                "condition": "steered",
                "seed": seed, "generated_text": outcome.generated_text, "truncated": outcome.truncated,
                "verdict": outcome.verdict, "spec": outcome.spec,
            })

    dose_id = dose.dose_id
    payload = {
        "concept_id": concept_id, "pairing_id": pairing_id, "direction": direction, "purpose": purpose,
        "dose": dose_id, "dose_kind": dose.kind, "dose_value": dose.value_in_max_units, "locale": locale,
        "control_ref": control_ref, "generations": generations,
    }
    filename = _generation_filename(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose=purpose, locale=locale,
        dose_id=dose_id,
    )
    path = Path(out_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    digest = hash_fn(path)
    return GenerationFileRecord(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, purpose=purpose, locale=locale,
        dose_id=dose_id, dose_kind=dose.kind, dose_value=dose.value_in_max_units,
        n_prompts=len(prompts), n_repeats=n_repeats, seeds=list(seeds),
        prompt_ids=prompt_ids, truncated_flags=truncated_flags,
        path=str(path), sha256=digest, control_ref=control_ref,
    )


def generate_concept_complete(
    backend, feature_indices: list[int], *, concept_id: str, pairing_id: str,
    corpus_max: dict[int, float], positions: str, out_dir: str | Path,
    amplify_dose_grid: list[DoseSpec], suppress_dose_grid: list[DoseSpec],
    amplify_sweep_prompts: dict[str, list[dict[str, Any]]], amplify_confirmation_prompts: dict[str, list[dict[str, Any]]],
    suppress_sweep_prompts: dict[str, list[dict[str, Any]]], suppress_confirmation_prompts: dict[str, list[dict[str, Any]]],
    max_new_tokens: int, generation_kwargs: dict[str, Any] | None = None,
    run_intervention_fn=None, run_baseline_fn=None, progress=None,
) -> list[GenerationFileRecord]:
    """ADDITION_4: finishes ONE concept entirely (both directions, both
    locales, all five doses, sweep AND confirmation, PLUS every paired
    control) or raises before writing anything -- there is no partial-
    concept file layout. Resumable per-file via `progress`. Asserts
    `assert_seed_sets_disjoint` once ALL of this concept's cells have
    been planned.

    `*_sweep_prompts`/`*_confirmation_prompts` are now `{locale: rows}`
    dicts of the frozen artifact's own ROW dicts (`select_generation_
    prompt_rows`'s return shape -- `prompt_id`/`text`/`split`/`ordinal`,
    never bare strings; `generation_settings.json` section 2: 15/20 rows
    EACH in en and fr, never split across the two) -- each locale's row
    list is still exactly `SWEEP_PROMPTS_PER_DIRECTION`/`CONFIRMATION_
    PROMPTS_PER_DIRECTION` long.

    For each (direction, purpose, locale): derives ONE shared seed list
    (`derive_seeds`, salted by namespace/locale but NOT by dose), writes
    ONE control file with that seed list (`generate_control_file`), then
    writes all five dose files REUSING those same seeds (`generate_dose_
    file`) -- satisfying `SAME_SEED_IS_MANDATORY` by construction rather
    than by a separate check."""
    if len(amplify_dose_grid) != DOSES_PER_DIRECTION or len(suppress_dose_grid) != DOSES_PER_DIRECTION:
        raise ValueError(f"both dose grids must have exactly {DOSES_PER_DIRECTION} points")

    prompts_by_direction = {
        "amplify": (amplify_sweep_prompts, amplify_confirmation_prompts),
        "suppress": (suppress_sweep_prompts, suppress_confirmation_prompts),
    }
    for direction, (sweep_by_locale, confirmation_by_locale) in prompts_by_direction.items():
        for locale in LOCALES:
            if locale not in sweep_by_locale or len(sweep_by_locale[locale]) != SWEEP_PROMPTS_PER_DIRECTION:
                raise ValueError(
                    f"{direction} sweep prompts for locale {locale!r} must have exactly "
                    f"{SWEEP_PROMPTS_PER_DIRECTION} entries"
                )
            if locale not in confirmation_by_locale or len(confirmation_by_locale[locale]) != CONFIRMATION_PROMPTS_PER_DIRECTION:
                raise ValueError(
                    f"{direction} confirmation prompts for locale {locale!r} must have exactly "
                    f"{CONFIRMATION_PROMPTS_PER_DIRECTION} entries"
                )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[GenerationFileRecord] = []
    sweep_seeds: list[int] = []
    confirmation_seeds: list[int] = []

    plan = (
        ("amplify", amplify_dose_grid, amplify_sweep_prompts, amplify_confirmation_prompts),
        ("suppress", suppress_dose_grid, suppress_sweep_prompts, suppress_confirmation_prompts),
    )
    for direction, dose_grid, sweep_by_locale, confirmation_by_locale in plan:
        for locale in LOCALES:
            for purpose, prompts, n_repeats, seed_bucket in (
                ("sweep", sweep_by_locale[locale], SWEEP_REPEATS, sweep_seeds),
                ("confirmation", confirmation_by_locale[locale], CONFIRMATION_REPEATS, confirmation_seeds),
            ):
                seeds = derive_seeds(
                    namespace=purpose, concept_id=concept_id, pairing_id=pairing_id, direction=direction,
                    locale=locale, n_prompts=len(prompts), n_repeats=n_repeats,
                )
                seed_bucket.extend(seeds)

                control_key = f"onealloc_{concept_id}_{pairing_id}_{direction}_{locale}_{purpose}_control"
                if progress is not None and progress.is_done(control_key):
                    control_record = GenerationFileRecord(**progress.result(control_key)["record"])
                else:
                    control_record = generate_control_file(
                        backend, corpus_max=corpus_max, positions=positions, prompts=prompts, purpose=purpose,
                        n_repeats=n_repeats, seeds=seeds, max_new_tokens=max_new_tokens, out_dir=out_dir,
                        concept_id=concept_id, pairing_id=pairing_id, direction=direction, locale=locale,
                        generation_kwargs=generation_kwargs, run_baseline_fn=run_baseline_fn,
                    )
                    if progress is not None:
                        progress.record(control_key, {"record": asdict(control_record)})
                records.append(control_record)

                for dose_index, dose in enumerate(dose_grid):
                    key = f"onealloc_{concept_id}_{pairing_id}_{direction}_{locale}_{purpose}_dose{dose_index}"
                    if progress is not None and progress.is_done(key):
                        record = GenerationFileRecord(**progress.result(key)["record"])
                        records.append(record)
                        continue
                    record = generate_dose_file(
                        backend, feature_indices, dose=dose, corpus_max=corpus_max,
                        positions=positions, prompts=prompts, purpose=purpose, n_repeats=n_repeats, seeds=seeds,
                        max_new_tokens=max_new_tokens, out_dir=out_dir, concept_id=concept_id, pairing_id=pairing_id,
                        direction=direction, locale=locale, control_ref=control_record.path,
                        generation_kwargs=generation_kwargs, run_intervention_fn=run_intervention_fn,
                    )
                    records.append(record)
                    if progress is not None:
                        progress.record(key, {"record": asdict(record)})

    assert_seed_sets_disjoint(sweep_seeds, confirmation_seeds)
    return records


def _canonical_manifest_json(body: dict) -> str:
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False)


def write_generation_manifest(
    records: list[GenerationFileRecord], manifest_path: str | Path, *,
    run_id: str, source_commit: str, configuration_name: Literal["primary", "backup"],
    concept_id: str, pairing_id: str, model_revision: str, sae_revision: str,
    release: str, loader_sae_id: str, scientific_sae_id: str, measured_params_sha256: str,
    generation_kwargs: dict[str, Any], chat_template_identity: str, locales_complete: list[str],
    causal_order_position: int, skipped_for_gate_failure: list[str], dose_grid: list[DoseSpec],
    completeness: Literal["COMPLETE", "PARTIAL", "NOT_ATTEMPTED"] = "COMPLETE",
) -> dict:
    """Writes ONE manifest -- ONE PHYSICAL MANIFEST PER (run_id,
    configuration, concept_id, pairing_id, direction), per the ratified
    `discovery_document_generation_binding.json` v1.1.0's `physical_
    granularity`, machine-verified against the REAL consumer's schema
    (`conformance/concept_bundle/discovery_input_schema.json` schema 5.0,
    `generation_manifests.manifest_required`/`manifest_file_required`):
    every field here is FLAT -- no nested `model`/`sae`/`concepts`
    objects, and no self-declared `manifest_sha256` (every object is
    closed: "unknown fields are refused" -- the binding protocol's
    `ManifestReference.source_sha256` is RECOMPUTED externally from the
    manifest's bytes, never read off a field the manifest declares about
    itself).

    `pairing_id` is the CONSUMER'S composite `f"{model_id}+{sae_repo_id}"`
    (`Pairing.pairing_id`) -- NOT this module's own internal `pairing_id`
    (`backend.pairing`, e.g. "gemma-3-12b-it") used for seed derivation/
    filenames; the caller supplies the composite value explicitly.
    `configuration_name`/`direction` are stored UPPERCASE (the consumer's
    own ruled casing); `measured_params_sha256` is stored `sha256:`-
    prefixed (the manifest's own ruled digest encoding, distinct from the
    discovery DOCUMENT's bare-hex `pairing.params_sha256`). It is mandatory
    on both arms: Gemma identity v1.3.0 and `qwen_config_identity.json`
    freeze expected parameter hashes, and each loader measures and verifies
    the local file before this write-once manifest is emitted.

    `generation_kwargs`/`chat_template_identity`/`locales_complete`/
    `causal_order_position`/`skipped_for_gate_failure` are `generation_
    settings.json`'s manifest-level additions -- ALL REQUIRED now (the
    schema-5.0 declaration lists them unconditionally in `manifest_
    required`), written verbatim/as given.

    `dose_grid` is THIS DIRECTION'S OWN five-point frozen grid (schema
    5.0, commit 3aff107) -- callers pass the exact `amplify_grid`/
    `suppress_grid` list `load_causal_dose_grid` returned for this
    direction, never a hand-built substitute; `_dose_grid_manifest_
    points` translates it into the manifest's own closed per-point shape,
    and `causal_dose_grid_path`/`_version`/`_sha256` bind the manifest to
    the exact frozen artifact identity this module already hash-pins via
    `validate_causal_dose_grid_protocol_hash`. Raises if `dose_grid` is
    not exactly `DOSES_PER_DIRECTION` points long.

    `generation_kwargs` must be the FULL resolved kwargs (Engineer 3
    delta, commit 9a32246: `concept_bundle_publish.frozen_generation_
    kwargs` reads ALL TEN of `generation_settings.json`'s own
    `1_generation_settings.settings` keys -- including `max_new_tokens:
    48` -- and requires an EXACT match, no fewer and no extra; the
    caller must pass `_resolved_generation_kwargs(ONE_ALLOCATION_MAX_
    NEW_TOKENS, GENERATION_SETTINGS)`, never the bare 9-key
    `GENERATION_SETTINGS` constant, which omits `max_new_tokens`.

    `skipped_for_gate_failure` is an ARRAY OF CONCEPT IDs (Engineer 3
    delta, commit 9a32246 -- corrected from an earlier boolean), never a
    bool: every concept_id that failed G-A/B/C and sits AT OR BEFORE
    `concept_id`'s own position in `CAUSAL_GENERATION_ORDER` (a concept
    AFTER this one cannot yet have been "skipped" from this manifest's
    own vantage point). Validated here, not merely documented -- every
    name must be in `CAUSAL_GENERATION_ORDER` and not sit after
    `concept_id`.

    `files` is the CONCATENATION of every record's `to_manifest_file_
    entries()` -- one row per GENERATION (not per physical file); see this
    module's own docstring, "MANIFEST GRANULARITY IS PER GENERATION".

    IMMUTABILITY (protocols/final_pairing/v1/manifest_immutability_
    correction.json, commit 2dc9e338): this manifest is written ONCE, at
    transfer, and NEVER rewritten -- `manifest_path` must not already
    exist; a caller attempting a second write to the same path is trying
    to rewrite a bound artifact after the fact, which this function
    refuses rather than silently overwriting. `files[]` entries carry NO
    per-file selection-outcome field of any kind (the selection record is
    the sole selection authority); the ONE permitted marker is the
    manifest-level constant `inventory_stage=PRE_SELECTION`, written
    unconditionally below."""
    if Path(manifest_path).exists():
        raise TransferVerificationFailed(
            f"{manifest_path} already exists -- the bound generation manifest is written ONCE, at "
            f"transfer, and NEVER rewritten (manifest-immutability correction, commit 2dc9e338). "
            f"Refusing to overwrite it."
        )
    if configuration_name not in ("primary", "backup"):
        raise ValueError(f"configuration_name must be 'primary' or 'backup', got {configuration_name!r}")
    if completeness not in COMPLETENESS_VALUES:
        raise ValueError(f"completeness must be one of {COMPLETENESS_VALUES}, got {completeness!r}")
    if len(dose_grid) != DOSES_PER_DIRECTION:
        raise ValueError(f"dose_grid must have exactly {DOSES_PER_DIRECTION} points, got {len(dose_grid)}")
    if not isinstance(measured_params_sha256, str):
        raise ValueError("measured_params_sha256 must be a measured 64-hex SHA-256 on both model arms")
    measured_params_bare = (
        measured_params_sha256.removeprefix("sha256:")
    )
    if len(measured_params_bare) != 64 or any(ch not in "0123456789abcdef" for ch in measured_params_bare):
        raise ValueError("measured_params_sha256 must be a measured lowercase 64-hex SHA-256")
    concept_position = causal_order_position_for(concept_id)
    for name in skipped_for_gate_failure:
        if name not in CAUSAL_GENERATION_ORDER:
            raise ValueError(
                f"skipped_for_gate_failure names {name!r}, which is not in the frozen CAUSAL_GENERATION_ORDER"
            )
        if causal_order_position_for(name) > concept_position:
            raise ValueError(
                f"skipped_for_gate_failure names {name!r}, which sits AFTER {concept_id!r} in the frozen "
                f"order and so cannot have been skipped before it"
            )
    directions_present = {r.direction for r in records}
    if len(directions_present) != 1:
        raise ValueError(
            f"a generation manifest must cover exactly ONE direction, got {sorted(directions_present)} -- "
            f"write a separate manifest per direction"
        )
    direction = next(iter(directions_present))
    concept_ids_present = {r.concept_id for r in records}
    if concept_ids_present != {concept_id}:
        raise ValueError(
            f"a generation manifest must cover exactly ONE concept_id ({concept_id!r}), got records for "
            f"{sorted(concept_ids_present)}"
        )

    body: dict[str, Any] = {
        "run_id": run_id, "source_commit": source_commit, "configuration": configuration_name.upper(),
        "concept_id": concept_id, "pairing_id": pairing_id,
        "model_revision": model_revision, "sae_revision": sae_revision, "release": release,
        "loader_sae_id": loader_sae_id, "scientific_sae_id": scientific_sae_id,
        "params_measured_sha256": _prefixed_sha256(measured_params_bare),
        "direction": direction.upper(),
        "files": [entry for r in records for entry in r.to_manifest_file_entries()],
        "completeness": completeness,
        "protocol_path": ONE_ALLOCATION_PROTOCOL_PATH,
        "protocol_sha256": _prefixed_sha256(ONE_ALLOCATION_PROTOCOL_SHA256),
        "generation_kwargs": dict(generation_kwargs),
        "chat_template_identity": chat_template_identity,
        "locales_complete": list(locales_complete),
        "generation_settings_path": GENERATION_SETTINGS_PROTOCOL_PATH,
        "generation_settings_version": GENERATION_SETTINGS_PROTOCOL_VERSION,
        "generation_settings_sha256": _prefixed_sha256(GENERATION_SETTINGS_PROTOCOL_SHA256),
        "causal_order_position": causal_order_position,
        "skipped_for_gate_failure": list(skipped_for_gate_failure),
        "inventory_stage": INVENTORY_STAGE_PRE_SELECTION,
        "dose_grid": _dose_grid_manifest_points(dose_grid),
        "causal_dose_grid_path": CAUSAL_DOSE_GRID_PROTOCOL_PATH,
        "causal_dose_grid_version": CAUSAL_DOSE_GRID_PROTOCOL_VERSION,
        "causal_dose_grid_sha256": _prefixed_sha256(CAUSAL_DOSE_GRID_PROTOCOL_SHA256),
    }

    Path(manifest_path).write_text(_canonical_manifest_json(body), encoding="utf-8")
    return body


def verify_generation_manifest(manifest_path: str | Path, *, files_root: str | Path | None = None) -> dict:
    """Stage 3 (TRANSFER): re-verifies every output file's hash against
    the manifest after moving outputs off the cluster. There is no
    manifest self-hash to check here (see `write_generation_manifest`'s
    docstring) -- the manifest's OWN bytes are verified externally, by
    whoever computes `ManifestReference.source_sha256` from this file
    (`final_pairing_evidence_document.build_manifest_reference`). A file
    hash mismatch is a HARD STOP (raises `TransferVerificationFailed`),
    never a warning.

    Each physical file backs MANY `files[]` entries (one per generation,
    see `to_manifest_file_entries`) -- hashes are checked ONCE per unique
    `path` (never once per entry) so verifying a 75-generation control
    file costs one hash computation, not 75.

    Manifest-immutability correction (commit 2dc9e338) enforcement: a
    manifest carrying a `derived`/`not_for_promotion` truthy marker (e.g.
    `stamp_manifest_with_selection`'s own reading-aid output) is REFUSED
    here -- that shape is explicitly never a promotable/bound artifact.
    A `files[]` entry carrying `selection_status` (or any other
    selection-outcome-shaped field) is likewise refused: the bound
    manifest carries no per-file selection-outcome field of any kind."""
    import final_pairing_concept_discovery as _d

    manifest_path = Path(manifest_path)
    full = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing = sorted(set(MANIFEST_REQUIRED_FIELDS) - set(full))
    if missing:
        raise TransferVerificationFailed(f"{manifest_path} is missing required field(s) {missing} -- not a valid manifest")
    if full.get("derived") or full.get("not_for_promotion"):
        raise TransferVerificationFailed(
            f"{manifest_path} is marked derived/not_for_promotion -- this is a reading-aid view "
            f"(e.g. stamp_manifest_with_selection's own output), never the bound manifest; refusing "
            f"to treat it as one."
        )
    tainted_entries = [
        i for i, entry in enumerate(full["files"])
        if "selection_status" in entry or "outcome" in entry or "selected" in entry
    ]
    if tainted_entries:
        raise TransferVerificationFailed(
            f"{manifest_path}: files[] entr{'y' if len(tainted_entries) == 1 else 'ies'} "
            f"{tainted_entries} carries a selection-outcome-shaped field -- the bound manifest is "
            f"pre-selection and carries no per-file selection-outcome field of any kind (manifest-"
            f"immutability correction, commit 2dc9e338)."
        )

    declared_sha256_by_path: dict[str, str] = {}
    for entry in full["files"]:
        declared_sha256_by_path.setdefault(entry["path"], entry["sha256"])

    mismatches: list[str] = []
    for declared_path, declared_sha256 in declared_sha256_by_path.items():
        path = Path(files_root) / Path(declared_path).name if files_root is not None else Path(declared_path)
        if not path.is_file():
            mismatches.append(f"{path}: file missing at transfer destination")
            continue
        actual = _d.compute_file_sha256(path)
        declared = declared_sha256[len("sha256:"):] if declared_sha256.startswith("sha256:") else declared_sha256
        if actual != declared:
            mismatches.append(f"{path}: sha256 mismatch (manifest {declared_sha256}, actual {actual})")
    if mismatches:
        raise TransferVerificationFailed(
            "transfer verification failed for " + str(len(mismatches)) + " file(s):\n  - " + "\n  - ".join(mismatches)
        )
    return full


def stamp_manifest_with_selection(manifest: dict, unselected_doses: list[str]) -> dict:
    """A READING-AID ONLY, never a promotable artifact (manifest-
    immutability correction, protocols/final_pairing/v1/manifest_
    immutability_correction.json, commit 2dc9e338): the BOUND generation
    manifest is written ONCE, at transfer, and NEVER rewritten or
    re-hashed -- the selection record (a separate artifact, owned by
    stage 4/Engineer 3) is the sole selection authority. This function
    does NOT mutate, replace, or stand in for that manifest; it returns a
    NEW, clearly-marked DERIVED dict (`derived: true`, `not_for_
    promotion: true`) with `selection_status=SELECTED_STATUS` added to
    every CONFIRMATION file entry whose `dose` is NOT in
    `unselected_doses`, and `UNUSED_STATUS` on every sweep entry and every
    confirmation entry whose dose IS in `unselected_doses` -- purely for a
    human or downstream tool reading this view alongside the real
    selection record. `verify_generation_manifest`/LA-B's own gate refuse
    any manifest carrying either marker, or any `files[]` entry carrying
    `selection_status`, as the bound artifact. `unselected_doses` names
    the canonical dose_ids (e.g. "A4", "S5") this manifest's own selection
    decided against -- since a manifest now covers exactly one (concept,
    pairing, direction), there is no cross-cell key to match against
    beyond the dose_id itself. No ordering or magnitude comparison is
    performed: membership in `unselected_doses` is a plain string-set
    check, so a Suppress selection whose HIGH is "S4" (not "S5"/ABLATE)
    is handled identically to any other dose_id."""
    unselected = set(unselected_doses)
    stamped_files = []
    for entry in manifest["files"]:
        entry = dict(entry)
        # The bound manifest carries no selection_status at all (manifest-
        # immutability correction) -- this reading aid ADDS it fresh to
        # EVERY entry, never merely "unchanged" from a pre-existing value
        # that no longer exists to inherit.
        if entry["purpose"] == "CONFIRMATION" and entry["dose"] not in unselected:
            entry["selection_status"] = SELECTED_STATUS
        else:
            entry["selection_status"] = UNUSED_STATUS
        stamped_files.append(entry)
    return {**manifest, "files": stamped_files, "derived": True, "not_for_promotion": True}


# ---------------------------------------------------------------------------
# Measured (not arithmetic-only) per-generation wall-time estimate (P0
# CONTINUE blocker 3): `estimate_seconds_for_one_concept`/`assess_concept_
# generation_readiness` above were always correct arithmetic on TOP of a
# `seconds_per_generation` figure -- what was missing was a real function
# that MEASURES that figure from the actually-loaded backend, rather than
# a caller guessing a constant and calling the resulting multiplication
# "measured."
# ---------------------------------------------------------------------------


def measure_seconds_per_generation(
    backend, *, feature_indices: list[int], corpus_max: dict[int, float], positions: str, prompt: str,
    base_seed: int, max_new_tokens: int, generation_kwargs: dict[str, Any] | None = None, n_samples: int = 3,
    run_intervention_fn=None, time_fn=None,
) -> dict[str, Any]:
    """Times `n_samples` REAL `run_intervention` calls against the
    ALREADY-LOADED `backend` (the same model/SAE weights this allocation
    will actually generate with) using `time.perf_counter` by default --
    never a bare `GENERATIONS_PER_CONCEPT * guessed-constant` arithmetic.
    `basis` names exactly what was measured and how, so this figure can
    never be silently relabeled as "measured" if it was not. The MEAN of
    the `n_samples` samples is `seconds_per_generation`, the one number
    `assess_concept_generation_readiness` may be called with;
    `estimate_seconds_for_one_concept`'s multiplication by `GENERATIONS_
    PER_CONCEPT` on top of that MEASURED figure remains legitimate
    arithmetic -- that combination, not the multiplication itself, is
    what "conservative measured estimate with its evidence source" means
    here.

    Each sample uses a DIFFERENT seed (`base_seed + i`) so the timed calls
    are independent samples, not one cached/memoized repeat."""
    time_fn = time_fn or time.perf_counter
    if run_intervention_fn is None:
        import final_pairing_concept_discovery as _d

        run_intervention_fn = _d.run_intervention

    samples: list[float] = []
    for i in range(n_samples):
        start = time_fn()
        run_intervention_fn(
            backend, feature_indices, direction="clamp", value_in_max_units=1.0, corpus_max=corpus_max,
            positions=positions, prompt=prompt, seed=base_seed + i, max_new_tokens=max_new_tokens,
            generation_kwargs=generation_kwargs,
        )
        samples.append(time_fn() - start)
    mean_seconds = sum(samples) / len(samples)
    return {
        "seconds_per_generation": mean_seconds,
        "sample_seconds": samples,
        "n_samples": n_samples,
        "basis": (
            f"measured: {n_samples} real run_intervention call(s) against the already-loaded backend "
            f"({backend.pairing}), timed with time.perf_counter -- not GENERATIONS_PER_CONCEPT arithmetic alone"
        ),
    }


# ---------------------------------------------------------------------------
# Production causal-generation CLI (P0 CONTINUE blocker 2): the real,
# scheduled entry point that wires load -> this pairing's own already-
# written grid.json -> keep only G-A/B/C 'pass' concepts -> CAUSAL_
# GENERATION_ORDER -> per-concept wall-time readiness gate -> concept-
# complete bilingual control+steered generation -> one manifest per
# direction. `final_concept_discovery_matched_configuration_job.py` is
# the caller that actually invokes this as a real subprocess lane, once
# per (pairing, configuration) -- see that module's `run_causal_
# generation_phase`.
# ---------------------------------------------------------------------------


def _release_and_loader_sae_id_for_backend(backend) -> tuple[str, str]:
    """Read the already-verified loader namespace from backend provenance.

    Both loaders now populate these fields at load time.  Generation must not
    invent an identity after weights have loaded: manifests are immutable and
    any guessed value would become irreversible provenance.
    """
    sae_prov = backend.provenance.get("sae", {})
    release = sae_prov.get("release")
    loader_sae_id = sae_prov.get("loader_sae_id")
    if not isinstance(release, str) or not release or not isinstance(loader_sae_id, str) or not loader_sae_id:
        raise ValueError(
            "loaded backend provenance is missing authoritative release/loader_sae_id; "
            "refusing to invent immutable manifest identity"
        )
    return release, loader_sae_id


def _measured_params_sha256_for_backend(backend) -> str:
    """Gemma's provenance already carries a MEASURED (and, at load time,
    verified-against-the-frozen-identity-artifact) `params_sha256` --
    returned verbatim. Qwen now does the same against
    `qwen_config_identity.json`.  The fallback hashes the resolved local file
    for older test seams only; production loaders always provide the measured,
    already-verified digest. Missing resolved bytes is a hard stop: both
    model arms have authoritative expected hashes."""
    sae_prov = backend.provenance.get("sae", {})
    if "params_sha256" in sae_prov:
        return sae_prov["params_sha256"]
    resolved = sae_prov.get("resolved_files") or sae_prov.get("resolved_local_paths") or []
    if not resolved:
        raise ValueError(
            "loaded backend provenance has neither params_sha256 nor a resolved SAE file; "
            "refusing to emit an unverified manifest identity"
        )
    import final_pairing_concept_discovery as _d

    return _d.compute_file_sha256(resolved[0])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pairing", required=True, help="e.g. gemma-3-12b-it or qwen-3.5-27b -- validated against the ratified final targets by load_backend.")
    p.add_argument("--model-path", required=True)
    p.add_argument("--sae-path", required=True)
    p.add_argument("--layer", type=int, required=True)
    p.add_argument("--qwen-sae-family", default=None)
    p.add_argument("--qwen-sparsity", type=int, default=None)
    p.add_argument("--expected-model-revision", default=None)
    p.add_argument("--expected-sae-revision", default=None)
    p.add_argument("--configuration-name", choices=["primary", "backup"], required=True)
    p.add_argument("--grid-path", required=True, help="The exact grid.json this pairing's OWN grid-discovery phase already wrote (never globbed, never read from another lane's in-memory state).")
    p.add_argument("--pairing-id", required=True, help="Composite model_id+sae_repo_id, e.g. google/gemma-3-12b-it+google/gemma-scope-2-12b-it -- for manifest identity, distinct from --pairing.")
    # No --amplify-dose-grid/--suppress-dose-grid flag: dose values are FROZEN
    # (causal_dose_grid.json) and read ONLY via load_causal_dose_grid inside
    # run_generation_mode -- there is no CLI path for an operator to supply a
    # different grid (NO_TUNING_AFTER_ACTIVATIONS).
    p.add_argument("--run-id", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--job-deadline-epoch-seconds", type=float, required=True, help="Absolute time.time()-based wall-clock deadline for this allocation -- never a duration relative to this process's own start, so readiness stays correct even if this process launches late.")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--state-dir", required=True, help="Separate from --out-dir: holds the resumable progress log only.")
    p.add_argument("--ready-path", default=None)
    p.add_argument("--device", default="cuda")
    p.add_argument("--dtype", default="bfloat16")
    return p.parse_args(argv)


def run_generation_mode(args: argparse.Namespace) -> dict:
    """The real, scheduled production causal-generation entry point.
    Loads ONE already-configured backend (one pairing, one configuration),
    reads THIS pairing's own `--grid-path` (a file on disk -- never an
    in-memory reference to the grid-discovery subprocess that wrote it,
    which has very likely already exited), keeps only the concepts with a
    G-A/B/C 'pass' verdict for this pairing, orders them via `order_
    concepts_for_causal_generation` (FIXED, G-A/B/C-independent order --
    a concept's position never changes based on how well it scored), and
    for each concept IN THAT ORDER: gates on measured wall-time readiness
    (`assess_concept_generation_readiness`, fed a REAL `measure_seconds_
    per_generation` sample from this exact backend -- never a guessed
    constant), and if ready, runs `generate_concept_complete` (bilingual,
    both directions, control+steered) and writes one manifest per
    direction (`write_generation_manifest`). The FIRST concept the
    readiness gate refuses stops the loop -- every concept after it in
    the fixed order is recorded `NOT_ATTEMPTED` too, never skipped ahead
    to on the chance it might be cheaper (the order is never renegotiated
    at runtime, matching `generation_settings.json`'s own "NO_REORDERING_
    AFTER_G_ABC" rule extended to wall-time)."""
    import final_pairing_concept_discovery as _d

    out_dir = Path(args.out_dir)
    state_dir = Path(args.state_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    progress = _d.ProgressLog(state_dir / "progress.jsonl")

    validate_one_allocation_protocol_hash(_d.REPO_ROOT)
    validate_generation_settings_protocol_hash(_d.REPO_ROOT)
    validate_causal_dose_grid_protocol_hash(_d.REPO_ROOT)
    _d.run_prompt_set_validator(_d.REPO_ROOT)
    artifact = _d.load_frozen_prompt_artifact(_d.REPO_ROOT, allow_pi_gated=True)

    # P0 STOP-LINE correction ("cross-check generation --source-commit
    # against transfer_manifest.json"): on Tamia (a git-archive transfer,
    # no .git at all), transfer_manifest.json's own recorded source_commit
    # is the one fact this checkout can independently verify --source-
    # commit against; a caller-supplied value that disagrees with it means
    # this manifest is about to be stamped with the wrong commit identity.
    # Silently absent (a live git checkout with no transfer manifest at
    # all -- the Windows/dev case) is not itself an error here.
    transfer_manifest = _d.load_transfer_manifest(_d.REPO_ROOT)
    if transfer_manifest is not None and transfer_manifest["source_commit"] != args.source_commit:
        raise ValueError(
            f"--source-commit {args.source_commit!r} disagrees with this checkout's own "
            f"transfer_manifest.json source_commit {transfer_manifest['source_commit']!r} -- "
            f"refusing to write a generation manifest under a source_commit that does not match "
            f"what was actually transferred to this allocation."
        )

    verdicts = _d.read_grid_result(args.grid_path)
    feature_by_concept = {v.concept_id: v.surviving_feature_index for v in verdicts if v.pairing == args.pairing and v.status == "pass"}
    concept_ids = order_concepts_for_causal_generation(list(feature_by_concept))
    # Engineer 3 delta (commit 9a32246): skipped_for_gate_failure is an
    # ARRAY OF CONCEPT IDS, not a bool -- every concept that failed G-A/
    # B/C (from the full grid, a static fact independent of wall-time),
    # in the fixed causal order. Computed ONCE here; each manifest below
    # filters this down to the prefix at-or-before its own position.
    verdict_by_concept_this_pairing = {v.concept_id: v for v in verdicts if v.pairing == args.pairing}
    gate_failed_in_causal_order = [
        c for c in CAUSAL_GENERATION_ORDER
        if verdict_by_concept_this_pairing.get(c) is not None and verdict_by_concept_this_pairing[c].status != "pass"
    ]

    # Dose values are FROZEN and read ONLY from causal_dose_grid.json -- no
    # CLI flag can substitute a different grid (NO_TUNING_AFTER_ACTIVATIONS).
    amplify_grid, suppress_grid = load_causal_dose_grid(_d.REPO_ROOT)

    backend = _d.load_backend(
        pairing=args.pairing, model_path=args.model_path, sae_path=args.sae_path, layer=args.layer,
        expected_model_revision=args.expected_model_revision, expected_sae_revision=args.expected_sae_revision,
        device=args.device, dtype=args.dtype, sae_family=args.qwen_sae_family, sparsity=args.qwen_sparsity,
    )
    if args.ready_path is not None:
        _d.write_ready_record(args.ready_path, pairing=args.pairing, device=args.device)

    measured_params_sha256 = _measured_params_sha256_for_backend(backend)
    release, loader_sae_id = _release_and_loader_sae_id_for_backend(backend)
    model_revision = backend.provenance.get("model", {}).get("revision", "")
    sae_revision = backend.provenance.get("sae", {}).get("revision", "")
    scientific_sae_id = (
        backend.provenance.get("sae", {}).get("scientific_sae_id")
        or backend.provenance.get("sae", {}).get("sae_id")
    )
    if not isinstance(scientific_sae_id, str) or not scientific_sae_id:
        raise ValueError(
            "loaded backend provenance is missing authoritative scientific_sae_id; "
            "refusing to write an immutable manifest with an empty identity"
        )
    # P0 STOP-LINE correction ("derive/record template identity rather
    # than accepting an arbitrary label"): DERIVED from the actual
    # tokenizer this backend will generate with, never a CLI-supplied
    # free-text label -- there is no --chat-template-identity flag.
    chat_template_identity = _d.resolve_chat_template_identity(_d.resolve_tokenizer_for_backend(backend))

    timing: dict[str, Any] | None = None
    attempted: list[str] = []
    not_attempted: list[dict[str, Any]] = []
    manifest_paths: dict[str, dict[str, str]] = {}
    # `unrelated` (shared_substrate, identical text across all 14 concepts
    # by design -- see `rows_for_concept`'s own docstring) is the same
    # concept-agnostic negative/background role G-A already reads; the
    # frozen artifact carries no field explicitly named "background_corpus"
    # of its own, so this is a disclosed re-use, not an invented split.
    # Computed ONCE (not per concept, since shared_substrate rows are
    # concept-invariant by construction) -- also means readiness is
    # checked BEFORE any per-concept GPU work, never after a "probing"
    # forward pass for a concept that may not even be attempted.
    background_texts = [
        row["text"] for row in _d.rows_for_concept(artifact.rows, concept_id=concept_ids[0], locale="en", split="unrelated")
    ] if concept_ids else []
    corpus_max = _d.corpus_max_per_feature(backend, background_texts) if background_texts else {}

    for concept_index, concept_id in enumerate(concept_ids):
        if timing is None:
            probe_rows = select_generation_prompt_rows(
                artifact.rows, concept_id=concept_id, direction="amplify", locale="en", purpose="sweep",
            )
            timing = measure_seconds_per_generation(
                backend, feature_indices=[feature_by_concept[concept_id]], corpus_max=corpus_max, positions="all",
                prompt=probe_rows[0]["text"], base_seed=0, max_new_tokens=_d.ONE_ALLOCATION_MAX_NEW_TOKENS,
                generation_kwargs=_d.GENERATION_SETTINGS,
            )

        remaining_wall_time_seconds = args.job_deadline_epoch_seconds - time.time()
        readiness = assess_concept_generation_readiness(
            remaining_wall_time_seconds=remaining_wall_time_seconds,
            seconds_per_generation=timing["seconds_per_generation"],
        )
        if not readiness.attempt:
            # P0 STOP-LINE correction: "after the first concept cannot fit,
            # BREAK; do not continue probing later concepts." The fixed
            # causal order is never reordered around a wall-time cutoff,
            # and remaining wall time only shrinks further from here, so
            # every concept after this one is recorded NOT_ATTEMPTED too,
            # without spending any further GPU time checking each one
            # individually.
            for later_concept_id in concept_ids[concept_index:]:
                detail = (
                    readiness.detail if later_concept_id == concept_id else
                    f"not attempted: causal order position after {concept_id!r}, which already could "
                    f"not fit in the remaining wall time -- {readiness.detail}"
                )
                not_attempted.append({"concept_id": later_concept_id, "detail": detail})
            break

        prompts = {
            (direction, purpose): {
                locale: select_generation_prompt_rows(
                    artifact.rows, concept_id=concept_id, direction=direction, locale=locale, purpose=purpose,
                )
                for locale in LOCALES
            }
            for direction in ("amplify", "suppress")
            for purpose in ("sweep", "confirmation")
        }

        concept_out_dir = out_dir / concept_id
        records = generate_concept_complete(
            backend, [feature_by_concept[concept_id]], concept_id=concept_id, pairing_id=backend.pairing,
            corpus_max=corpus_max, positions="all", out_dir=concept_out_dir,
            amplify_dose_grid=amplify_grid, suppress_dose_grid=suppress_grid,
            amplify_sweep_prompts=prompts[("amplify", "sweep")],
            amplify_confirmation_prompts=prompts[("amplify", "confirmation")],
            suppress_sweep_prompts=prompts[("suppress", "sweep")],
            suppress_confirmation_prompts=prompts[("suppress", "confirmation")],
            max_new_tokens=_d.ONE_ALLOCATION_MAX_NEW_TOKENS, generation_kwargs=_d.GENERATION_SETTINGS, progress=progress,
        )

        position = causal_order_position_for(concept_id)
        skipped_for_gate_failure = [c for c in gate_failed_in_causal_order if causal_order_position_for(c) <= position]
        direction_manifest_paths: dict[str, str] = {}
        for direction in ("amplify", "suppress"):
            direction_records = [r for r in records if r.direction == direction]
            manifest_path = concept_out_dir / f"generation_manifest_{direction}.json"
            write_generation_manifest(
                direction_records, manifest_path, run_id=args.run_id, source_commit=args.source_commit,
                configuration_name=args.configuration_name, concept_id=concept_id, pairing_id=args.pairing_id,
                model_revision=model_revision, sae_revision=sae_revision, release=release, loader_sae_id=loader_sae_id,
                scientific_sae_id=scientific_sae_id, measured_params_sha256=measured_params_sha256,
                # Engineer 3 delta (commit 9a32246): generation_kwargs must be
                # the FULL resolved kwargs (all 10 frozen values, including
                # max_new_tokens=48), never the bare 9-key GENERATION_SETTINGS
                # constant.
                generation_kwargs=_d._resolved_generation_kwargs(_d.ONE_ALLOCATION_MAX_NEW_TOKENS, _d.GENERATION_SETTINGS),
                chat_template_identity=chat_template_identity,
                locales_complete=list(LOCALES), causal_order_position=position,
                skipped_for_gate_failure=skipped_for_gate_failure,
                dose_grid=amplify_grid if direction == "amplify" else suppress_grid,
            )
            direction_manifest_paths[direction] = str(manifest_path)
        manifest_paths[concept_id] = direction_manifest_paths
        attempted.append(concept_id)

    return {
        "schema_version": 1,
        "mode": "generation",
        "pairing": args.pairing,
        "configuration": args.configuration_name,
        "grid_path": str(args.grid_path),
        "surviving_concepts": list(feature_by_concept),
        "causal_order": concept_ids,
        "attempted_concepts": attempted,
        "not_attempted": not_attempted,
        "timing": timing,
        "manifest_paths": manifest_paths,
        "status": "complete" if not not_attempted else "partial_wall_time_cutoff",
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_generation_mode(args)
    print(json.dumps({
        "status": result["status"], "pairing": result["pairing"], "configuration": result["configuration"],
        "attempted_concepts": result["attempted_concepts"],
        "not_attempted": [x["concept_id"] for x in result["not_attempted"]],
    }, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
