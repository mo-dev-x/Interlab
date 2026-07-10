"""SS9 chain assembly (TRUNK, not delegable, §0 Ground Rule 6): implements
the ED-14/ED-15/ED-16 chain resolution algorithm exactly as specified in
§5.SS9 -- no inference beyond what the four numbered rules there state.

Assembly is read-only and pure: same registry state => same resolution
(§5.SS9 invariant). `assemble_chain` never mutates the registry and never
imports `interplab.evaluation` (the eval_compat_map is read as plain
registry JSON, per ED-15 point 4 -- "reports does NOT import evaluation").
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from interplab.core.errors import ContractViolationError
from interplab.registry.registry import REGISTRY_ROOT, RegistryError
from interplab.registry.registry import find as registry_find
from interplab.registry.registry import get as registry_get

#: A9's claim-mode invariant (§4 A9): "claim-mode results MUST contain all
#: three control arms and blinding.shuffled = true." The three control arms
#: are the ones `interventions.control_arms` + `jobs.steer` assemble
#: (random_direction, random_feature, prompt_baseline); "steered" and
#: "baseline" are the two experimental arms, not controls.
_REQUIRED_CONTROL_ARMS = frozenset({"random_direction", "random_feature", "prompt_baseline"})

#: ED-15 point 3: the fixed role vocabulary is exactly the artifact-valued
#: role strings, one payload-carried exception (A5 store_hash -> role
#: store_manifest). Extractors below read each artifact_type's judge fields
#: for the eval-compat check (ED-15 point 4) -- field *names* differ across
#: artifact types (A7 uses "model", A8/A9 use "judge_model"; A9 carries no
#: prompt_version at all), normalized here to a common
#: (judge_model, rubric_version, prompt_version | None) tuple.
_JUDGE_TUPLE_EXTRACTORS = {
    "characterization_manifest": lambda p: (
        p["judge"]["model"], p["judge"]["rubric_version"], p["judge"]["prompt_version"],
    ),
    "feature_certificate": lambda p: (
        p["specificity"]["judge_model"], p["specificity"]["rubric_version"], p["specificity"]["prompt_version"],
    ),
    "intervention_result": lambda p: (
        (p["lodestar"]["judge_model"], p["lodestar"]["rubric_version"], None) if p.get("lodestar") else None
    ),
}


@dataclasses.dataclass(frozen=True)
class ChainRow:
    link: str
    artifact_hash: str | None
    status: str  # ok|missing|stale_schema|eval_incompatible|red_verdict|insufficient_evidence
    note: str | None


@dataclasses.dataclass(frozen=True)
class ChainResolution:
    rows: list[ChainRow]
    stamp: str  # "CERTIFIED" | "DRAFT — UNCERTIFIED CHAIN"
    anchor_artifacts: list[dict | None]  # aligned with claim_spec["anchor"]["content_hashes"]; None where missing


def _get_safe(content_hash: str, *, registry_root: Path) -> dict | None:
    """ED-14: "An anchor absent from the registry is chain state (missing),
    not an error; a hash-mismatched or schema-invalid artifact is
    corruption (exit 3)." Applied uniformly to every link, not just anchors
    -- the same honest-absence-vs-corruption distinction the rest of this
    codebase already draws (ED-9's null-vs-zero idiom, one level up)."""
    try:
        return registry_get(content_hash, registry_root=registry_root)
    except RegistryError as e:
        if "no registry artifact found" in str(e):
            return None
        raise ContractViolationError(f"corrupt registry artifact {content_hash!r}: {e}") from e
    except Exception as e:
        raise ContractViolationError(f"corrupt registry artifact {content_hash!r}: {e}") from e


def _effective_subject_entries(artifact: dict) -> list[dict]:
    """ED-15 point 2: "Exactly one payload-carried ref exists in the
    ontology and is treated as a subject-equivalent parent ref: A5
    store_hash (role store_manifest)." Folded in here so every subject_ref
    scan sees it uniformly, without special-casing the scan loop itself."""
    entries = list(artifact["subject"])
    if artifact["artifact_type"] == "sae_checkpoint":
        store_hash = artifact["payload"].get("store_hash")
        if store_hash is not None:
            entries = [*entries, {"content_hash": store_hash, "location": "", "role": "store_manifest"}]
    return entries


def _resolve_link(
    link_spec: dict, resolved_order: list[dict], *, registry_root: Path
) -> tuple[dict | None, str | None]:
    """ED-15 point 2, both `via` modes."""
    role = link_spec["subject_role"]
    artifact_type = link_spec["artifact_type"]

    if link_spec["via"] == "subject_ref":
        for candidate in resolved_order:
            for ref in _effective_subject_entries(candidate):
                if ref["role"] == role:
                    artifact = _get_safe(ref["content_hash"], registry_root=registry_root)
                    if artifact is None:
                        return None, f"subject_ref target {ref['content_hash']} (role={role!r}) not found in registry"
                    return artifact, None
        return None, f"no already-resolved artifact carries a subject entry with role={role!r}"

    # via == "subject_of"
    prerequisite = next((c for c in resolved_order if c["artifact_type"] == role), None)
    if prerequisite is None:
        return None, f"prerequisite artifact_type={role!r} not yet resolved at this link's turn"
    candidates = registry_find(artifact_type, subject_hash=prerequisite["self_hash"], registry_root=registry_root)
    candidates = [
        c for c in candidates
        if any(ref["content_hash"] == prerequisite["self_hash"] and ref["role"] == role for ref in c["subject"])
    ]
    if not candidates:
        return None, f"no {artifact_type} found whose subject carries {role}={prerequisite['self_hash']!r}"
    if len(candidates) == 1:
        return candidates[0], None
    chosen = max(candidates, key=lambda c: c["created_at"])
    return chosen, (
        f"ambiguous: {len(candidates)} {artifact_type} candidates subject {role}="
        f"{prerequisite['self_hash']!r}; newest created_at chosen ({chosen['self_hash']!r})"
    )


def _claim_grade_check(artifact: dict) -> tuple[str, str] | None:
    """ED-14: intervention_result anchors are additionally claim-grade
    checked against A9's claim-mode invariant."""
    payload = artifact["payload"]
    problems = []
    arms_present = {a["arm"] for a in payload["arms"]}
    missing_arms = sorted(_REQUIRED_CONTROL_ARMS - arms_present)
    if missing_arms:
        problems.append(f"missing control arms {missing_arms}")
    if not payload["blinding"]["shuffled"]:
        problems.append("blinding.shuffled is false")
    if not any(ref["role"] == "feature_certificate" for ref in artifact["subject"]):
        problems.append("no feature_certificate reference in subject")
    if problems:
        return "insufficient_evidence", "not claim-grade: " + "; ".join(problems)
    return None


def _gate_checks(
    artifact: dict, *, min_schema_version: int | None, require_instruments: list[str] | None
) -> tuple[str, str | None]:
    """Type-conditional checks (§5.SS9 established pattern + ED-16),
    first-failure-wins in the order the blueprint text lists them: schema
    version, then verdict, then instrument sufficiency. (Eval-compat is a
    separate, whole-chain pass -- see `_apply_eval_compat`.)"""
    if min_schema_version is not None and artifact["schema_version"] < min_schema_version:
        return "stale_schema", f"schema_version {artifact['schema_version']} < required minimum {min_schema_version}"

    payload = artifact["payload"]
    if isinstance(payload.get("verdict"), str) and payload["verdict"] == "red":
        return "red_verdict", "verdict is red"

    if require_instruments:
        basis = set(payload.get("verdict_basis", []))
        missing = [i for i in require_instruments if i not in basis]
        if missing:
            return "insufficient_evidence", f"required instruments missing from verdict_basis: {missing}"

    return "ok", None


@dataclasses.dataclass(frozen=True)
class _Pass:
    anchor_row: ChainRow
    anchor_artifact: dict | None
    link_rows: list[ChainRow]
    link_artifacts: list[dict | None]


def _resolve_pass(claim_spec: dict, anchor_hash: str, *, registry_root: Path) -> _Pass:
    anchor_type = claim_spec["anchor"]["artifact_type"]
    resolved_order: list[dict] = []

    anchor_artifact = _get_safe(anchor_hash, registry_root=registry_root)
    if anchor_artifact is None:
        anchor_row = ChainRow(
            link=anchor_type, artifact_hash=None, status="missing",
            note=f"anchor {anchor_hash!r} not found in registry",
        )
    else:
        status, note = _gate_checks(anchor_artifact, min_schema_version=None, require_instruments=None)
        if status == "ok" and anchor_type == "intervention_result":
            claim_grade = _claim_grade_check(anchor_artifact)
            if claim_grade is not None:
                status, note = claim_grade
        anchor_row = ChainRow(link=anchor_type, artifact_hash=anchor_artifact["self_hash"], status=status, note=note)
        resolved_order.append(anchor_artifact)  # available for traversal regardless of gate status

    link_rows: list[ChainRow] = []
    link_artifacts: list[dict | None] = []
    for link_spec in claim_spec["required_links"]:
        artifact, resolve_note = _resolve_link(link_spec, resolved_order, registry_root=registry_root)
        if artifact is None:
            link_rows.append(
                ChainRow(link=link_spec["artifact_type"], artifact_hash=None, status="missing", note=resolve_note)
            )
            link_artifacts.append(None)
            continue
        status, gate_note = _gate_checks(
            artifact,
            min_schema_version=link_spec["min_schema_version"],
            require_instruments=link_spec.get("require_instruments"),
        )
        note = gate_note if gate_note is not None else resolve_note
        link_rows.append(
            ChainRow(link=link_spec["artifact_type"], artifact_hash=artifact["self_hash"], status=status, note=note)
        )
        link_artifacts.append(artifact)
        resolved_order.append(artifact)  # structural pointer availability, independent of gate status

    return _Pass(anchor_row=anchor_row, anchor_artifact=anchor_artifact, link_rows=link_rows, link_artifacts=link_artifacts)


def _judge_tuple(artifact: dict) -> tuple[str, str, str | None] | None:
    extractor = _JUDGE_TUPLE_EXTRACTORS.get(artifact["artifact_type"])
    if extractor is None:
        return None
    return extractor(artifact["payload"])


def _class_for_tuple(tup: tuple[str, str, str | None], compat_map_payload: dict) -> str | None:
    model, rubric, prompt = tup
    for cls in compat_map_payload["judge_classes"]:
        for member in cls["members"]:
            if member["judge_model"] == model and member["rubric_version"] == rubric and (
                prompt is None or member["prompt_version"] == prompt
            ):
                return cls["class_id"]
    return None


def _apply_eval_compat(
    rows: list[ChainRow], artifacts: list[dict | None], *, eval_compat_version: int, registry_root: Path
) -> list[ChainRow]:
    """ED-15 point 4: "every judge tuple in the resolved chain must fall in
    one compatible class under the A12 map whose payload.version ==
    claim_spec.eval_compat_version... A map version absent from the
    registry => exit 3." A whole-chain pass (not per-link), since
    compatibility is a property of the *set* of judge tuples together.

    Implementer's choice, undictated by the blueprint text: when the
    judge-bearing rows in the chain do not all share one class, every
    judge-bearing `ok` row is downgraded to `eval_incompatible` (not just
    whichever one looks like "the odd one out") -- symmetric and
    unambiguous to compute, and the `note` on each names the full mismatch.
    """
    maps = registry_find("eval_compat_map", version=eval_compat_version, registry_root=registry_root)
    if not maps:
        raise ContractViolationError(f"no eval_compat_map with payload.version={eval_compat_version} in registry")
    compat_map = max(maps, key=lambda a: a["created_at"])

    judge_bearing: list[tuple[int, tuple]] = []
    for i, (row, artifact) in enumerate(zip(rows, artifacts, strict=True)):
        if row.status != "ok" or artifact is None:
            continue
        tup = _judge_tuple(artifact)
        if tup is not None:
            judge_bearing.append((i, tup))

    if not judge_bearing:
        return rows

    classes = {i: _class_for_tuple(tup, compat_map["payload"]) for i, tup in judge_bearing}
    distinct = {c for c in classes.values() if c is not None}
    incompatible = None in classes.values() or len(distinct) > 1
    if not incompatible:
        return rows

    note = f"eval-compat mismatch across chain: classes found = {sorted(c or 'none' for c in set(classes.values()))}"
    new_rows = list(rows)
    for i in classes:
        new_rows[i] = dataclasses.replace(new_rows[i], status="eval_incompatible", note=note)
    return new_rows


def _check_no_duplicate_required_link_types(claim_spec: dict) -> None:
    """ED-14/ED-15: "v1 claim specs MUST contain at most one required link
    per artifact_type" -- unenforceable by the schema itself (an array
    can't express element-uniqueness on one field), so `assemble_chain`
    enforces it as a claim-spec authoring error, same tier as ED-14's
    anchor-divergence check (exit 3, checked before any resolution work)."""
    seen: set[str] = set()
    dupes: set[str] = set()
    for link_spec in claim_spec["required_links"]:
        artifact_type = link_spec["artifact_type"]
        if artifact_type in seen:
            dupes.add(artifact_type)
        seen.add(artifact_type)
    if dupes:
        raise ContractViolationError(
            f"required_links contains more than one entry for artifact_type(s) {sorted(dupes)} -- "
            "v1 claim specs MUST contain at most one required link per artifact_type (claim-spec authoring error)"
        )


def assemble_chain(claim_spec: dict, *, registry_root: Path = REGISTRY_ROOT) -> ChainResolution:
    """TRUNK, §0 Ground Rule 6: implements exactly the algorithm at
    §5.SS9 (ED-14/ED-15/ED-16), no inference beyond it."""
    _check_no_duplicate_required_link_types(claim_spec)
    anchor_hashes = claim_spec["anchor"]["content_hashes"]
    passes = [_resolve_pass(claim_spec, h, registry_root=registry_root) for h in anchor_hashes]

    n_links = len(claim_spec["required_links"])
    for idx in range(n_links):
        hashes = {p.link_rows[idx].artifact_hash for p in passes}
        if len(hashes) > 1:
            link_type = claim_spec["required_links"][idx]["artifact_type"]
            raise ContractViolationError(
                f"anchor replicates diverge at required_links[{idx}] ({link_type}): "
                f"resolved to {sorted(h or 'None' for h in hashes)} across anchors -- claim-spec authoring error"
            )

    anchor_rows = [p.anchor_row for p in passes]
    anchor_artifacts = [p.anchor_artifact for p in passes]
    link_rows = passes[0].link_rows
    link_artifacts = passes[0].link_artifacts

    all_rows = anchor_rows + link_rows
    all_artifacts = anchor_artifacts + link_artifacts
    all_rows = _apply_eval_compat(
        all_rows, all_artifacts, eval_compat_version=claim_spec["eval_compat_version"], registry_root=registry_root
    )

    stamp = "CERTIFIED" if all(row.status == "ok" for row in all_rows) else "DRAFT — UNCERTIFIED CHAIN"
    return ChainResolution(rows=all_rows, stamp=stamp, anchor_artifacts=anchor_artifacts)
