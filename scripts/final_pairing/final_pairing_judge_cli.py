"""Stages 4-5 of the frozen one-allocation dose-generation protocol
(`protocols/final_pairing/v1/one_allocation_dose_generation.json`, v1.0.0):
a REAL, runnable CLI over the real Lodestar package (`d:\\lodstar`, a
separate repository -- never vendored, never reimplemented) for judging
GPU-generated sweep/confirmation outputs, selecting LOW/MEDIUM/HIGH,
committing `selection_record.json` as the stage boundary, and judging
confirmation at the three selected doses only.

WHY THIS FILE EXISTS SEPARATELY FROM `final_pairing_causal_judge.py`:
that module holds the pure GATE ARITHMETIC (`evaluate_gate_d`/
`evaluate_gate_e`, already built and tested). This file is the CLI that
actually DRIVES a real judge run against real transfer-verified
generation files: cost estimation, budget enforcement, the real
content-addressed cache, and the stage-4/5 selection-then-confirmation
sequencing the one-allocation protocol requires. It imports
`final_pairing_causal_judge` for the gate arithmetic and rubric/judge
identity helpers already built there, rather than duplicating them.

D:-ONLY, NEVER C:. `--lodestar-source-root` (default: `LODESTAR_SOURCE_ROOT`
env var, else `D:/lodstar`) is inserted onto `sys.path` so the real,
separately-installed Lodestar package is importable WITHOUT installing it
into this repo's own (C:-hosted) `.venv` -- `ensure_lodestar_importable`
below is the only place this happens, and it is idempotent. `--cache-path`
and `--output-dir` both default to D:-based paths; nothing here writes to
C: beyond this repository's own source tree.

CREDENTIAL DISCIPLINE: the Anthropic API key is read ONLY from
`ANTHROPIC_API_KEY` (`require_api_key`), is NEVER included in any
persisted JSON, log line, or command-line argument this module
constructs, and a missing key is a fail-closed refusal
(`CredentialMissing`), never a silent fallback to an unauthenticated or
mock client.

SCIENTIFIC-MODE MOCK REFUSAL: `assert_judge_model_is_attestable` refuses
`lodestar.judges.mock.MockJudge.model_name` ("mock-deterministic-v1") and
any judge model string starting with "mock" from ever reaching a
function in this file that PERSISTS a result as attested evidence --
Engineer 3's own `NOOP_JUDGE_MODELS` ("none"/"noop"/"no-op"/"identity")
covers a different failure mode (a judge that structurally recorded that
it never ran) and does not by itself refuse a mock judge's model name, so
this module adds its own, independent guard rather than relying on the
consumer to catch it. `MockJudge` remains fully usable directly from
Lodestar for tests -- this module simply never wires it into a function
whose output this file would call "judged" without qualification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import final_pairing_causal_judge as causal_judge  # noqa: E402
import final_pairing_one_allocation_generation as one_alloc  # noqa: E402

DEFAULT_LODESTAR_SOURCE_ROOT = "D:/lodstar"
DEFAULT_CACHE_PATH = "D:/devcache/lodestar_cache/final_pairing/cache.sqlite"
DEFAULT_OUTPUT_ROOT = "D:/devcache/lodestar_runs/final_pairing"

#: Mirrors lodestar.judges.mock.MockJudge.model_name -- never imported from
#: there directly (this module must be importable without lodestar present).
MOCK_JUDGE_MODEL_NAME = "mock-deterministic-v1"


class CredentialMissing(RuntimeError):
    """ANTHROPIC_API_KEY is not set. Fail-closed: never falls back to an
    unauthenticated client or a mock judge in its place."""


class BudgetExceeded(RuntimeError):
    """The real, pre-call cost estimate exceeds the authorized budget.
    Raised BEFORE any paid call is made -- zero paid calls occur once this
    is raised."""


class ScientificModeMockRefused(RuntimeError):
    """A mock/no-op judge model was passed to a function that persists
    its output as attested evidence."""


class MixedOperationPublicationRefused(RuntimeError):
    """A SELECTED Suppress record's low/medium/high named the ABLATE
    dose_id (S5) -- protocols/final_pairing/v1/mixed_operation_
    publication.json v1.1.0 (commit 6e3f4be) forbids S5 from ever
    occupying a published triple position. S5 stays fully scientific
    (generated, judged, recorded as 'unselected' evidence); it is simply
    never eligible to be selected as low, medium, or high."""


def ensure_lodestar_importable(source_root: str | Path | None = None) -> Path:
    """Inserts the real, separately-installed Lodestar source tree onto
    `sys.path` -- an explicit source-root mechanism, never an install
    into this repo's own `.venv`. Idempotent: safe to call more than
    once. Raises `causal_judge.CausalJudgeUnavailable` if the resolved
    root does not look like the real Lodestar package (no
    `lodestar/__init__.py`), rather than silently proceeding to an
    import error deeper in the stack."""
    root = Path(source_root or os.environ.get("LODESTAR_SOURCE_ROOT") or DEFAULT_LODESTAR_SOURCE_ROOT)
    if not (root / "lodestar" / "__init__.py").is_file():
        raise causal_judge.CausalJudgeUnavailable(
            f"{root} does not contain lodestar/__init__.py -- not a real Lodestar source root. Set "
            f"--lodestar-source-root or the LODESTAR_SOURCE_ROOT environment variable to the real "
            f"checkout (this project's is d:/lodstar, a separate repository, never vendored here)."
        )
    resolved = str(root.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    return root


def require_api_key() -> str:
    """Reads the credential ONLY from `ANTHROPIC_API_KEY`. Never prints,
    logs, serializes, or returns it embedded in any other structure --
    callers that need to report status use `api_key_present()` instead,
    which returns a bare bool."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise CredentialMissing(
            "ANTHROPIC_API_KEY is not set -- refusing to construct a live judge without one. This is "
            "a fail-closed preflight failure, not a fallback to an unauthenticated or mock client."
        )
    return key


def api_key_present() -> bool:
    """For preflight/status reporting ONLY: whether the credential is
    present, never its value."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def assert_judge_model_is_attestable(judge_model: str) -> None:
    """Refuses `MOCK_JUDGE_MODEL_NAME` (or anything else starting with
    "mock", case-insensitive) from reaching a function that persists a
    result as attested evidence. Independent of, and in addition to,
    Engineer 3's own `NOOP_JUDGE_MODELS` refusal (which catches a
    different failure mode: an identity judge recording that nothing
    ran)."""
    lowered = judge_model.strip().lower()
    if lowered == MOCK_JUDGE_MODEL_NAME or lowered.startswith("mock"):
        raise ScientificModeMockRefused(
            f"judge_model {judge_model!r} is a mock/test judge identity -- MockJudge/NoOpJudge may be "
            f"used only in tests, and this function persists its result as ATTESTED evidence, which a "
            f"mock judge is structurally incapable of producing."
        )


def build_lodestar_generations_from_dose_file(
    payload: dict[str, Any], *, condition: str, model_name: str, language: str = "en",
) -> list[Any]:
    """Builds one real `lodestar.models.Generation` per generation entry
    inside one of this project's own dose-file JSON payloads (written by
    `final_pairing_one_allocation_generation.generate_dose_file` -- ONE
    file now covers every prompt x repeat for one (concept, pairing,
    direction, dose, purpose) cell, per the consumer's own `dose-check`
    shape, so this returns a LIST, not a single Generation). Lazy import:
    this module (like `final_pairing_causal_judge.py`) must remain
    importable without lodestar installed.

    Lodestar's real `Generation` model requires `steering_config` for any
    non-baseline condition -- built here from each entry's `spec`
    (`InterventionOutcome.spec`, always present). `hook_layer` is recorded
    as `0` when this project's own `spec` dict (which does not carry the
    SAE's layer number) supplies none -- a genuine gap, not a silent guess
    at a real layer: callers needing an accurate `hook_layer` here should
    extend `InterventionOutcome.spec` to carry it, which this function
    does not invent on its own."""
    ensure_lodestar_importable()
    from lodestar.models import Generation, SteeringConfig

    generations = []
    for entry in payload["generations"]:
        steering_config = None
        if condition != "baseline":
            spec = entry.get("spec") or {}
            raw_feature_index = spec.get("feature_index", 0)
            feature_ids = tuple(raw_feature_index) if isinstance(raw_feature_index, list) else (raw_feature_index,)
            steering_config = SteeringConfig(
                sae_checkpoint_id=str(spec.get("checkpoint_hash") or "unknown-checkpoint"),
                hook_layer=0,
                feature_ids=feature_ids, weights=(1.0,) * len(feature_ids),
                scale=float(payload.get("dose_value") or 0.0),
            )
        generations.append(Generation(
            text=entry["generated_text"], prompt=entry.get("prompt", ""),
            prompt_id=str(entry["prompt_id"]), condition=condition, model_name=model_name, language=language,
            target_concept=payload["concept_id"], seed=entry.get("seed"), steering_config=steering_config,
            metadata={
                "concept_id": payload["concept_id"], "pairing_id": payload["pairing_id"],
                "direction": payload["direction"], "purpose": payload["purpose"], "dose": payload["dose"],
                "dose_kind": payload["dose_kind"], "dose_value": payload["dose_value"],
                "repeat_index": entry["repeat_index"],
            },
        ))
    return generations


def load_generation_files(paths: list[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def manifest_entries(manifest: dict[str, Any], *, direction: str, purpose: str, dose: str | None = None) -> list[dict[str, Any]]:
    """Filters a verified generation manifest's `files` entries -- the
    ONLY supported way this module selects which files to read. There is
    no path here that globs a directory independent of the manifest, so a
    file the manifest does not list can never be judged.

    `direction` is checked against the MANIFEST's own top-level scalar
    (schema 2.0, commit 67ad4ef -- a manifest covers exactly one
    direction, so every file entry already matches it or the manifest is
    malformed) rather than a per-file field, which no longer exists.
    `purpose` is matched case-insensitively against the file entries' own
    ruled UPPERCASE storage ("SWEEP"/"CONFIRMATION"/"CONTROL"); `dose` is
    matched by EXACT string equality against the entry's canonical
    dose_id (e.g. "S4", "A5" -- causal_dose_grid.json, never a float or a
    float-derived label) -- CONTROL entries carry no `dose` key at all,
    so `dose is not None` never matches one."""
    if manifest["direction"].lower() != direction.lower():
        return []
    entries = [
        e for e in manifest["files"]
        if e["purpose"].lower() == purpose.lower()
        and (dose is None or e.get("dose") == dose)
    ]
    return entries


@dataclass(frozen=True)
class JudgeRunResult:
    judge_model: str
    rubric_versions: dict[str, str]
    total_judgments: int
    cache_hits: int
    cache_misses: int
    actual_cost_usd: float
    judgments_path: str


def run_estimate(
    *, generations: list[Any], rubrics: list[Any], repeats: int, judge_model: str, cache_path: str | Path,
) -> dict[str, Any]:
    """Real, pre-call Lodestar cost estimate. Makes ZERO API calls (the
    real `lodestar.judges.cost.estimate` is pure local arithmetic over
    rendered prompt lengths). Counts cache hits against the real
    content-addressed cache first, so a re-run of an already-judged sweep
    correctly predicts near-zero NEW cost."""
    ensure_lodestar_importable()
    import asyncio

    from lodestar.judges.base import (
        DEFAULT_JUDGE_MAX_TOKENS,
        JUDGE_SYSTEM_PROMPT,
        JUDGE_TEMPERATURE,
    )
    from lodestar.judges.cache import JudgeCache
    from lodestar.judges.cost import estimate
    from lodestar.judges.identity import execution_cache_key

    async def _count_hits() -> int:
        cache = JudgeCache(cache_path)
        await cache.initialize()
        keys = [
            execution_cache_key(
                generation, rubric, model_name=judge_model, system_prompt=JUDGE_SYSTEM_PROMPT,
                max_tokens=DEFAULT_JUDGE_MAX_TOKENS, temperature=JUDGE_TEMPERATURE, repeat_index=repeat_index,
            )
            for generation in generations for rubric in rubrics for repeat_index in range(repeats)
        ]
        return await cache.count_hits(keys)

    hits = asyncio.run(_count_hits())
    result = estimate(generations, rubrics, repeats, judge_model, cached_calls=hits)
    return {
        "judge_model": judge_model, "rubric_versions": {r.name: r.version for r in rubrics},
        "total_judgments": result.calls, "cached_calls": result.cached_calls, "new_calls": result.new_calls,
        "predicted_input_tokens": result.input_tokens, "predicted_output_tokens": result.output_tokens,
        "predicted_cost_usd": result.cost_usd,
    }


def persist_estimate(estimate_report: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(estimate_report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def assert_within_budget(predicted_cost_usd: float, *, budget_usd: float) -> None:
    if predicted_cost_usd > budget_usd:
        raise BudgetExceeded(
            f"predicted uncached cost ${predicted_cost_usd:.4f} exceeds the authorized budget "
            f"${budget_usd:.4f} -- STOP, zero paid calls made. Increase the authorized budget or reduce "
            f"scope before retrying; this function refuses to proceed rather than making a partial or "
            f"over-budget run."
        )


def _default_judge_factory(judge_model: str, *, api_key: str, cache: Any) -> Any:
    from lodestar.judges.anthropic import AnthropicJudge

    return AnthropicJudge(judge_model, api_key=api_key, cache=cache)


def run_judging(
    *, generations: list[Any], rubrics: list[Any], repeats: int, judge_model: str, cache_path: str | Path,
    api_key: str, output_dir: str | Path, judge_factory=None,
) -> JudgeRunResult:
    """The real, paid (unless every item is a cache hit) judging call.
    Caller MUST have already run `run_estimate`/`assert_within_budget`
    (this function does not re-derive or re-check the budget -- estimate-
    then-authorize is the caller's sequencing responsibility, matching
    Lodestar's own `eval` command's own structure). Persists raw
    judgments, judge/rubric identity, and actual cost; never returns
    (or accepts) a mock judge in production (`assert_judge_model_is_
    attestable` below refuses one by MODEL NAME regardless of what
    `judge_factory` is passed).

    `judge_factory` defaults to constructing the REAL `AnthropicJudge`
    (this project's established real-default/injectable-fake-for-tests
    seam) -- tests inject a fake satisfying the same async
    `judge_batch(items, repeats) -> list[Judgment-like]` protocol (e.g.
    Lodestar's own real `MockJudge`, itself refused for PRODUCTION use by
    `assert_judge_model_is_attestable`'s model-name check, but perfectly
    fine as an injected test double here) so this function's real
    estimate/budget/cache/persistence logic is exercised without a paid
    API call."""
    assert_judge_model_is_attestable(judge_model)
    ensure_lodestar_importable()
    import asyncio

    from lodestar.judges.cache import JudgeCache
    from lodestar.judges.cost import actual_cost

    if judge_factory is None:
        judge_factory = _default_judge_factory

    cache = JudgeCache(cache_path)
    judge = judge_factory(judge_model, api_key=api_key, cache=cache)
    items = [(generation, rubric) for generation in generations for rubric in rubrics]

    async def _run() -> list[Any]:
        await cache.initialize()
        return await judge.judge_batch(items, repeats)

    judgments = asyncio.run(_run())
    cache_hits = sum(1 for j in judgments if getattr(j, "cached", False))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    judgments_path = output_dir / "judgments.json"
    judgments_path.write_text(
        json.dumps([j.model_dump(mode="json") for j in judgments], indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return JudgeRunResult(
        judge_model=judge_model, rubric_versions={r.name: r.version for r in rubrics},
        total_judgments=len(judgments), cache_hits=cache_hits, cache_misses=len(judgments) - cache_hits,
        actual_cost_usd=actual_cost(judgments, judge_model), judgments_path=str(judgments_path),
    )


# ---------------------------------------------------------------------------
# Stage 4: selection_record.json -- committed to git, the stage boundary.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionRecord:
    """`concept_id`/`pairing_id`/`direction` identify the cell; `status`
    is `"SELECTED"` or `"FAILED"`; a SELECTED record names a dose for
    every one of `low`/`medium`/`high` in `selected`, with `unselected`
    covering every OTHER generated confirmation dose (selected UNION
    unselected must equal every generated confirmation dose for that
    cell); a FAILED record names NO selected doses
    (`sealed_output_rules.if_direction_fails`: all five stay sealed).

    Doses are the CANONICAL string dose_ids (e.g. "S4", "S5") -- matching
    the real manifest's own dose identifiers (`final_pairing_one_
    allocation_generation.GenerationFileRecord.dose_id`/`stamp_manifest_
    with_selection`'s `unselected_doses`; `causal_dose_grid.json`, commit
    c43a976), not the integer dose indices an earlier version of this
    module used, and not a float-derived label. No magnitude ordering is
    assumed: a SELECTED record whose `high` is "S4" is valid (indeed the
    normal case) -- LOW/MEDIUM/HIGH are chosen from the judged sweep,
    never from dose-grid position.

    MIXED-OPERATION PUBLICATION RESTRICTION (protocols/final_pairing/v1/
    mixed_operation_publication.json v1.1.0, commit 6e3f4be, supersedes
    v1.0.0/cddd9a5): on the SUPPRESS arm, the ABLATE dose (S5) may NEVER
    occupy `low`/`medium`/`high` in a SELECTED record -- `build_selected_
    record` enforces this (see its own docstring). S5 remains fully
    scientific: it is still generated, judged, and named in `unselected`
    when not chosen; it simply cannot be one of the three published
    positions. S1..S4 (CLAMP) and S5 (ABLATE) are not one continuous
    magnitude ramp -- S5 is a different operation with no magnitude at
    all, not a further point on the same scale."""

    concept_id: str
    pairing_id: str
    direction: str
    status: Literal["SELECTED", "FAILED"]
    selected: dict[str, str]  # {"low": dose_id, "medium": dose_id, "high": dose_id} -- empty for FAILED
    unselected: list[str]


def build_selected_record(
    *, concept_id: str, pairing_id: str, direction: str, low_dose: str, medium_dose: str, high_dose: str,
    all_confirmation_doses: list[str], ablate_dose_id: str | None,
) -> SelectionRecord:
    """`ablate_dose_id` is the Suppress grid's ABLATE dose_id (e.g. "S5",
    resolved via `final_pairing_one_allocation_generation.
    load_causal_dose_grid`) when `direction == "suppress"`, else `None`
    (Amplify has no ablate point at all, so there is nothing to restrict).
    Raises `MixedOperationPublicationRefused` if `ablate_dose_id` occupies
    `low`/`medium`/`high` -- the mixed-operation-publication ruling's own
    restriction (protocols/final_pairing/v1/mixed_operation_publication.json
    v1.1.0, commit 6e3f4be), binding BEFORE any judged score exists: the
    candidate set for a published triple excludes S5 from the outset,
    which is what makes this a legitimate pre-registered constraint rather
    than post-hoc substitution of what was actually selected."""
    selected = {"low": low_dose, "medium": medium_dose, "high": high_dose}
    if ablate_dose_id is not None:
        occupied = sorted(position for position, dose_id in selected.items() if dose_id == ablate_dose_id)
        if occupied:
            raise MixedOperationPublicationRefused(
                f"{occupied} name the ABLATE dose_id {ablate_dose_id!r} -- S5/ABLATE is not eligible to "
                f"occupy a published Suppress low/medium/high position (mixed_operation_publication.json "
                f"v1.1.0, commit 6e3f4be). S5 remains fully scientific and belongs in 'unselected'/the "
                f"manifest's own evidence; it may never be a value in 'selected'."
            )
    unselected = sorted(set(all_confirmation_doses) - set(selected.values()))
    return SelectionRecord(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, status="SELECTED",
        selected=selected, unselected=unselected,
    )


def build_failed_record(*, concept_id: str, pairing_id: str, direction: str, all_confirmation_doses: list[str]) -> SelectionRecord:
    """A FAILED selection is a RESULT, not an error -- all five doses stay
    sealed (`sealed_output_rules.if_direction_fails`)."""
    return SelectionRecord(
        concept_id=concept_id, pairing_id=pairing_id, direction=direction, status="FAILED",
        selected={}, unselected=sorted(all_confirmation_doses),
    )


def write_selection_record(records: list[SelectionRecord], path: str | Path) -> dict[str, Any]:
    """Writes the selection record body Engineer 3's `dose-check` reads:
    `{"protocol_version":..., "protocol_sha256":..., "selections": [...]}`
    -- no ancestry fields yet (those are added by `finalize_selection_
    ancestry` below, once the confirmation-judging commit exists)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "protocol_version": one_alloc.ONE_ALLOCATION_PROTOCOL_VERSION,
        "protocol_sha256": one_alloc.ONE_ALLOCATION_PROTOCOL_SHA256,
        "selections": [asdict(r) for r in records],
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return body


def commit_selection_record(
    repo_root: str | Path, path: str | Path, *, message: str, run_git_fn=None,
) -> str:
    """Commits `selection_record.json` to git -- THIS COMMIT IS THE STAGE
    BOUNDARY (`ADDITION_2_sealing_is_mechanical`). `run_git_fn` defaults
    to a real `subprocess.run` wrapper; tests inject a fake operating on a
    throwaway tmp git repo, never the real project repository."""
    if run_git_fn is None:
        def run_git_fn(args: list[str]) -> str:
            return subprocess.run(args, cwd=str(repo_root), capture_output=True, text=True, check=True).stdout.strip()

    run_git_fn(["git", "add", "--", str(path)])
    run_git_fn(["git", "commit", "-m", message])
    return run_git_fn(["git", "rev-parse", "HEAD"])


def finalize_selection_ancestry(
    path: str | Path, *, selection_commit: str, confirmation_judging_commit: str,
) -> dict[str, Any]:
    """Adds `selection_commit`/`confirmation_judging_commit` to an
    already-written selection record, for `dose-check`'s ancestry check.
    These two fields necessarily cannot be known at `write_selection_
    record` time (the file's own commit hash cannot be embedded in
    itself), so they are added in this SEPARATE step once the
    confirmation-judging commit actually exists. This function does not
    re-commit the file -- `dose-check` reads the file's content directly
    and checks the two named commits' git ancestry, independent of
    whether the file containing them is itself committed at any
    particular point."""
    path = Path(path)
    body = json.loads(path.read_text(encoding="utf-8"))
    body["selection_commit"] = selection_commit
    body["confirmation_judging_commit"] = confirmation_judging_commit
    path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    return body


def assert_selection_precedes_confirmation(
    repo_root: str | Path, *, selection_commit: str, confirmation_commit: str, run_git_fn=None,
) -> None:
    """`ADDITION_2`'s git-ancestry stage boundary: `selection_commit` must
    be a STRICT ancestor of `confirmation_commit` (equal commits fail --
    same discipline as the standing prompt_set/causal_validation
    chronology check elsewhere in this project). Verified with
    `git merge-base --is-ancestor`, never merely trusted from a caller's
    say-so."""
    if selection_commit == confirmation_commit:
        raise causal_judge.CausalJudgeUnavailable(
            f"selection_commit and confirmation_commit are the SAME commit ({selection_commit[:12]}) -- "
            f"equality establishes no ordering, so selection is not shown to have preceded confirmation "
            f"judging."
        )
    if run_git_fn is None:
        def run_git_fn(args: list[str]) -> int:
            return subprocess.run(args, cwd=str(repo_root), capture_output=True, text=True).returncode

    returncode = run_git_fn(["git", "merge-base", "--is-ancestor", selection_commit, confirmation_commit])
    if returncode != 0:
        raise causal_judge.CausalJudgeUnavailable(
            f"selection_commit {selection_commit[:12]} is not an ancestor of confirmation_commit "
            f"{confirmation_commit[:12]} -- refusing to judge confirmation outputs without a committed "
            f"selection preceding it in git history."
        )


def assert_never_opens_unselected(
    manifest: dict[str, Any], selection: SelectionRecord, *, requested_doses: list[str],
) -> None:
    """Refuses to proceed if `requested_doses` includes anything outside
    the three selected doses -- the structural half of `ADDITION_3`'s
    "unselected files are never opened" (the other half is that
    `manifest_entries` never globs a directory independent of the
    manifest)."""
    selected = set(selection.selected.values())
    forbidden = sorted(set(requested_doses) - selected)
    if forbidden:
        raise causal_judge.CausalJudgeUnavailable(
            f"requested confirmation dose(s) {forbidden} are NOT among the selected doses "
            f"{sorted(selected)} for {selection.concept_id}/{selection.pairing_id}/{selection.direction} -- "
            f"files stamped {one_alloc.SEALED_LABEL} may never be opened."
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
# NOTE on LOW/MEDIUM/HIGH selection: the one-allocation protocol says
# "Select LOW/HIGH/MEDIUM under the frozen rules in the discovery
# protocol" without specifying how judged sweep scores map to a selection
# rule beyond the existing dose-threshold mechanism
# (`final_pairing_concept_discovery.select_calibration_candidates`,
# already frozen/tested). Rather than inventing an unspecified algorithm
# that turns judged concept_relevance/coherence scores into a selection
# decision, `write-selection` takes the three selected dose indices as
# EXPLICIT input (produced by a researcher applying the existing
# frozen dose-threshold rule to the judged sweep output printed by
# `judge-sweep`) -- disclosed here and in the closing report as a scoping
# decision, not a silent guess at an unspecified rule.


def _load_manifest_and_rubrics(args) -> tuple[dict[str, Any], Any, Any]:
    manifest = one_alloc.verify_generation_manifest(args.manifest, files_root=args.files_root)
    coherence, concept_relevance = causal_judge.load_steering_rubrics()
    return manifest, coherence, concept_relevance


def _build_generations_for_dose_files(args, entries: list[dict[str, Any]]) -> list[Any]:
    """`entries` is now ONE MANIFEST ROW PER GENERATION (schema 2.0 --
    many rows can share the same physical `path`, see
    `final_pairing_one_allocation_generation`'s own docstring on manifest
    granularity), so paths are deduplicated here BEFORE loading -- loading
    once per entry would re-read (and double-judge) the same physical
    file's generations once per row that names it."""
    unique_paths = list(dict.fromkeys(e["path"] for e in entries))
    payloads = load_generation_files(unique_paths)
    generations: list[Any] = []
    for payload in payloads:
        generations.extend(
            build_lodestar_generations_from_dose_file(payload, condition="steered", model_name=args.model_name)
        )
    return generations


def _build_generations_for_sweep(args, manifest: dict[str, Any]) -> list[Any]:
    entries = manifest_entries(manifest, direction=args.direction, purpose="sweep")
    if not entries:
        raise causal_judge.CausalJudgeUnavailable(
            f"no sweep entries in {args.manifest} for direction={args.direction!r}"
        )
    return _build_generations_for_dose_files(args, entries)


def _cmd_estimate_sweep(args) -> int:
    manifest, coherence, concept_relevance = _load_manifest_and_rubrics(args)
    generations = _build_generations_for_sweep(args, manifest)
    report = run_estimate(
        generations=generations, rubrics=[coherence, concept_relevance], repeats=1,
        judge_model=args.judge_model, cache_path=args.cache_path,
    )
    persist_estimate(report, args.out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _cmd_judge_sweep(args) -> int:
    assert_judge_model_is_attestable(args.judge_model)
    manifest, coherence, concept_relevance = _load_manifest_and_rubrics(args)
    generations = _build_generations_for_sweep(args, manifest)
    rubrics = [coherence, concept_relevance]
    report = run_estimate(
        generations=generations, rubrics=rubrics, repeats=1, judge_model=args.judge_model, cache_path=args.cache_path,
    )
    persist_estimate(report, Path(args.output_dir) / "sweep_estimate.json")
    print(json.dumps(report, indent=2, sort_keys=True))
    assert_within_budget(report["predicted_cost_usd"], budget_usd=args.budget_usd)
    api_key = require_api_key()
    result = run_judging(
        generations=generations, rubrics=rubrics, repeats=1, judge_model=args.judge_model,
        cache_path=args.cache_path, api_key=api_key, output_dir=args.output_dir,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def _cmd_write_selection(args) -> int:
    manifest = one_alloc.verify_generation_manifest(args.manifest, files_root=args.files_root)
    all_doses = sorted({e["dose"] for e in manifest["files"] if e["purpose"] == "CONFIRMATION"})
    if len(all_doses) != one_alloc.DOSES_PER_DIRECTION:
        raise causal_judge.CausalJudgeUnavailable(
            f"manifest {args.manifest} carries {len(all_doses)} distinct confirmation dose(s) "
            f"{all_doses}, not the {one_alloc.DOSES_PER_DIRECTION} the frozen grid requires"
        )
    if args.failed:
        record = build_failed_record(
            concept_id=args.concept_id, pairing_id=args.pairing_id, direction=args.direction,
            all_confirmation_doses=all_doses,
        )
    else:
        # mixed_operation_publication.json v1.1.0 (commit 6e3f4be): on the Suppress arm, the
        # ABLATE dose_id is excluded from the PUBLISHED triple's candidate set from the outset
        # (pre-registered, not a post-hoc rejection) -- resolved from the real frozen grid,
        # never hardcoded, since a caller must not assume "S5" spells the ablate point.
        ablate_dose_id = None
        if args.direction == "suppress":
            _amplify_grid_unused, suppress_grid = one_alloc.load_causal_dose_grid(args.repo_root)
            ablate_dose_id = next(spec.dose_id for spec in suppress_grid if spec.kind == "ablate")
        record = build_selected_record(
            concept_id=args.concept_id, pairing_id=args.pairing_id, direction=args.direction,
            low_dose=args.low_dose, medium_dose=args.medium_dose, high_dose=args.high_dose,
            all_confirmation_doses=all_doses, ablate_dose_id=ablate_dose_id,
        )
    write_selection_record([record], args.out)
    commit_hash = commit_selection_record(args.repo_root, args.out, message=args.commit_message)
    print(json.dumps({"selection_record": asdict(record), "commit": commit_hash}, indent=2, sort_keys=True))
    return 0


def _cmd_judge_confirmation(args) -> int:
    assert_judge_model_is_attestable(args.judge_model)
    selection_document = json.loads(Path(args.selection_record).read_text(encoding="utf-8"))
    selection_records = [SelectionRecord(**r) for r in selection_document["selections"]]
    selection = next(
        r for r in selection_records
        if r.concept_id == args.concept_id and r.pairing_id == args.pairing_id and r.direction == args.direction
    )
    if selection.status == "FAILED":
        raise causal_judge.CausalJudgeUnavailable(
            f"selection for {args.concept_id}/{args.pairing_id}/{args.direction} is FAILED -- all five doses "
            f"stay sealed; a failed selection is a result, not a licence to judge the sealed set."
        )
    assert_selection_precedes_confirmation(
        args.repo_root, selection_commit=args.selection_commit, confirmation_commit=args.confirmation_commit,
    )
    manifest = one_alloc.verify_generation_manifest(args.manifest, files_root=args.files_root)
    selected_doses = sorted(set(selection.selected.values()))
    assert_never_opens_unselected(manifest, selection, requested_doses=selected_doses)
    entries = [
        e for dose in selected_doses
        for e in manifest_entries(manifest, direction=args.direction, purpose="confirmation", dose=dose)
    ]
    coherence, concept_relevance = causal_judge.load_steering_rubrics()
    generations = _build_generations_for_dose_files(args, entries)
    rubrics = [coherence, concept_relevance]
    report = run_estimate(
        generations=generations, rubrics=rubrics, repeats=1, judge_model=args.judge_model, cache_path=args.cache_path,
    )
    persist_estimate(report, Path(args.output_dir) / "confirmation_estimate.json")
    print(json.dumps(report, indent=2, sort_keys=True))
    assert_within_budget(report["predicted_cost_usd"], budget_usd=args.budget_usd)
    api_key = require_api_key()
    result = run_judging(
        generations=generations, rubrics=rubrics, repeats=1, judge_model=args.judge_model,
        cache_path=args.cache_path, api_key=api_key, output_dir=args.output_dir,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def build_arg_parser():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p) -> None:
        p.add_argument("--manifest", required=True, help="path to a transfer-verified generation_manifest.json")
        p.add_argument("--files-root", default=None, help="re-root manifest file paths here (post-transfer location)")
        p.add_argument("--concept-id", required=True)
        p.add_argument("--pairing-id", required=True)
        p.add_argument("--direction", required=True, choices=["amplify", "suppress"])
        p.add_argument("--judge-model", required=True, help="pinned Anthropic snapshot, e.g. claude-sonnet-4-5-20250929")
        p.add_argument("--model-name", required=True, help="the STEERED model that produced the generations")
        p.add_argument("--cache-path", default=DEFAULT_CACHE_PATH)
        p.add_argument("--output-dir", default=DEFAULT_OUTPUT_ROOT)

    est = sub.add_parser("estimate-sweep", help="real, zero-cost pre-call estimate for the sweep, no API calls")
    common(est)
    est.add_argument("--out", required=True)
    est.set_defaults(func=_cmd_estimate_sweep)

    judge_sweep = sub.add_parser("judge-sweep", help="estimate, enforce budget, then judge the sweep for real")
    common(judge_sweep)
    judge_sweep.add_argument("--budget-usd", type=float, required=True)
    judge_sweep.set_defaults(func=_cmd_judge_sweep)

    write_sel = sub.add_parser("write-selection", help="write + commit selection_record.json (the stage boundary)")
    write_sel.add_argument("--manifest", required=True, help="path to a transfer-verified generation_manifest.json, read for its real confirmation dose labels")
    write_sel.add_argument("--files-root", default=None, help="re-root manifest file paths here (post-transfer location)")
    write_sel.add_argument("--concept-id", required=True)
    write_sel.add_argument("--pairing-id", required=True)
    write_sel.add_argument("--direction", required=True, choices=["amplify", "suppress"])
    write_sel.add_argument("--low-dose", help="canonical dose_id (e.g. 'S1', 'A1'); required unless --failed")
    write_sel.add_argument("--medium-dose", help="canonical dose_id (e.g. 'S2', 'A3'); required unless --failed")
    write_sel.add_argument("--high-dose", help="canonical dose_id (e.g. 'S4', 'A5'); no ordering assumed, but on Suppress the ABLATE dose_id is refused here -- it may never occupy a published low/medium/high position (mixed_operation_publication.json v1.1.0); required unless --failed")
    write_sel.add_argument("--failed", action="store_true", help="record a FAILED selection: all five doses stay sealed")
    write_sel.add_argument("--out", required=True)
    write_sel.add_argument("--repo-root", required=True)
    write_sel.add_argument("--commit-message", required=True)
    write_sel.set_defaults(func=_cmd_write_selection)

    judge_conf = sub.add_parser("judge-confirmation", help="judge confirmation outputs at the 3 selected doses only")
    common(judge_conf)
    judge_conf.add_argument("--budget-usd", type=float, required=True)
    judge_conf.add_argument("--selection-record", required=True)
    judge_conf.add_argument("--selection-commit", required=True)
    judge_conf.add_argument("--confirmation-commit", required=True)
    judge_conf.add_argument("--repo-root", required=True)
    judge_conf.set_defaults(func=_cmd_judge_confirmation)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (CredentialMissing, BudgetExceeded, ScientificModeMockRefused, MixedOperationPublicationRefused,
            causal_judge.CausalJudgeUnavailable, one_alloc.TransferVerificationFailed) as exc:
        print(f"REFUSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
