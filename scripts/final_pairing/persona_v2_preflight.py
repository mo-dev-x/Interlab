#!/usr/bin/env python3
"""CPU-only preflight for the v2 PERSONA concepts in the discovery harness.

WHAT THIS IS FOR. The recurring defect in this sprint is a check that
passes while being unable to exercise what it claims to cover -- a clean
negative indistinguishable from real absence. A preflight that reports OK
because it silently skipped the persona concepts is worse than no
preflight. So this script is CONTROL-FIRST by construction: `--fault` runs
it against a deliberately broken input and REQUIRES a loud refusal. A run
with `--fault none` alone does not distinguish "working" from "not
looking", and the report says so in its own `control_arm` field.

    # the controls: each of these MUST fail loudly
    python scripts/final_pairing/persona_v2_preflight.py --fault corrupt-prompt-digest --report <p>
    python scripts/final_pairing/persona_v2_preflight.py --fault drop-family-rows     --report <p>
    python scripts/final_pairing/persona_v2_preflight.py --fault invert-near-miss-of  --report <p>
    python scripts/final_pairing/persona_v2_preflight.py --fault tamper-threshold     --report <p>
    # then the real thing
    python scripts/final_pairing/persona_v2_preflight.py --report <p>

Exit code is 0 only when every check passed (`--fault none`) or when the
injected fault was correctly REFUSED (`--fault <x>`). A fault that fails to
provoke a refusal exits non-zero: silently tolerating a broken corpus is
the failure this arm exists to catch.

WHAT IT CANNOT DO. There is no GPU here and no Gemma-3-12B-it /
Qwen3.5-27B weights on this machine. The gate plumbing is exercised end to
end on a DETERMINISTIC SURROGATE backend (real torch tensors, a real
relu(x @ W.T + b) encoder, content-addressed residuals) -- which tests the
wiring and the arithmetic and tests NOTHING about the model. Every number
this script prints about activations is a surrogate number. `--report`'s
`unexercised_without_gpu` field lists exactly what remains owed; it is
written on every run, pass or fail, so an unexercised path can never read
as a verified one.

NOTHING HERE SUBMITS ANYTHING. No ssh, no sbatch, no squeue, no network.
RULING_12 authorises no submission and ENGINEERING PREVIEW ONLY stands.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_targets as targets  # noqa: E402

REPORT_SCHEMA_VERSION = 1

FAULTS = (
    "none", "corrupt-prompt-digest", "drop-family-rows", "relabel-family-rows",
    "invert-near-miss-of", "tamper-threshold",
)

#: Stated on every report, pass or fail. These are the things a CPU box
#: cannot establish, listed so that "the preflight passed" is never read as
#: covering them.
UNEXERCISED_WITHOUT_GPU = [
    "Any real activation: no Gemma-3-12B-it / gemma-scope-2-12b-it or Qwen3.5-27B / Qwen-Scope weights "
    "exist on this machine, so every score below is a surrogate score. No separation_auroc, fire_rate or "
    "near_miss_auroc printed here is a fact about either model.",
    "Whether ANY feature survives G-A/G-B/G-C on the persona concepts. Survivors, survivor counts and "
    "the pass/fail status of either concept are entirely unmeasured.",
    "The real backend load path (load_backend / load_gemma_scientific_target / load_qwen_scientific_"
    "target), the hook preflight, the dtype-boundary policy and the device-agreement assertions.",
    "Wall time, memory and the d_sae-scale full-space scan at production size (d_sae here is a "
    "surrogate few hundred, not 16384/81920).",
    "The SHADOW G-B distribution at production scale (computed here, but off surrogate activations).",
]


# ---------------------------------------------------------------------------
# A deterministic surrogate backend. Same construction verify_gate_fixes.py
# uses for C2: a real (small) SAE-shaped encoder with a negative bias, so
# post-ReLU exact zeros -- and therefore ties, dead cells and the C1 guard --
# are reachable rather than hypothetical.
# ---------------------------------------------------------------------------

_SURROGATE_D_MODEL = 32
_SURROGATE_D_SAE = 512
_SURROGATE_HOOK = "surrogate.hook_resid_post"


class _SurrogateSAE:
    def __init__(self, seed: int = 20260816) -> None:
        import torch

        gen = torch.Generator().manual_seed(seed)
        self.d_in = _SURROGATE_D_MODEL
        self.d_sae = _SURROGATE_D_SAE
        self.W = torch.randn(_SURROGATE_D_SAE, _SURROGATE_D_MODEL, generator=gen)
        self.b = -torch.rand(_SURROGATE_D_SAE, generator=gen) * 1.5

    def encode(self, x):
        import torch

        return torch.relu(x.to(torch.float32) @ self.W.T + self.b)


class _SurrogateModel:
    """Content-addressed residuals over 3 positions per text, plus a
    forward-pass counter. Deterministic in the text, so two runs over the
    same corpus produce identical numbers."""

    def __init__(self) -> None:
        self.forward_passes = 0
        self._texts: dict[int, str] = {}

    def to_tokens(self, text: str):
        import torch

        token = len(self._texts)
        self._texts[token] = text
        return torch.tensor([[token]])

    def run_with_cache(self, tokens, names_filter: str):
        import torch

        self.forward_passes += 1
        text = self._texts[int(tokens[0][0])]
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**31)
        gen = torch.Generator().manual_seed(seed)
        resid = torch.randn((1, 3, _SURROGATE_D_MODEL), generator=gen)
        return None, {names_filter: resid}


def _surrogate_backend() -> tuple[d.Backend, _SurrogateModel]:
    model = _SurrogateModel()
    backend = d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name, model_obj=model, sae=_SurrogateSAE(),
        hook_name=_SURROGATE_HOOK, d_sae=_SURROGATE_D_SAE, d_model=_SURROGATE_D_MODEL,
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={"model": {"repository": "surrogate", "local_path": "/surrogate"}, "sae": {"repository": "surrogate"}},
        checkpoint_hash="surrogate",
    )
    return backend, model


# ---------------------------------------------------------------------------
# Fault injection. Every fault is applied to an IN-MEMORY copy or to a
# throwaway temp directory; nothing under prompts/final_pairing/v2/ is ever
# written, and the frozen bytes on disk are never touched.
# ---------------------------------------------------------------------------


class FaultNotRefused(RuntimeError):
    """The injected fault did NOT provoke a refusal. This is the important
    failure: it means the corresponding check cannot see the defect it is
    supposed to see, and a clean run of it proves nothing."""


def _broken_repo_with_corrupt_prompt_bytes(tmp_root: Path, repo_root: Path) -> Path:
    """A repo-shaped directory with NO .git and ONE character changed in one
    persona prompt.

    This is the cluster's own situation (a tarball extract), so it drives
    the fallback path specifically -- the path a git-only loader would
    never reach and the path a careless fallback would read on trust."""
    src = repo_root / d.PERSONA_V2_PROMPT_SET_DIR
    dst = tmp_root / d.PERSONA_V2_PROMPT_SET_DIR
    dst.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (src / "prompt_sets.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[0]["text"] = rows[0]["text"] + "."  # one byte
    (dst / "prompt_sets.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
    )
    (dst / "metadata.json").write_bytes((src / "metadata.json").read_bytes())
    v1_dst = tmp_root / d.FROZEN_PROMPT_SET_DIR
    v1_dst.mkdir(parents=True, exist_ok=True)
    (v1_dst / "metadata.json").write_bytes((repo_root / d.FROZEN_PROMPT_SET_DIR / "metadata.json").read_bytes())
    assert not (tmp_root / ".git").exists()
    return tmp_root


def _rows_with_a_family_dropped(rows: list[dict]) -> list[dict]:
    """pro_american_exceptionalism / en / f2's ten positives, removed. The
    cell scheme is now 5 cells for that concept, not 6."""
    return [
        r for r in rows
        if not (
            r["concept_id"] == "pro_american_exceptionalism" and r["locale"] == "en"
            and r["split"] == "positive" and r.get("family") == "f2"
        )
    ]


def _rows_with_a_family_relabelled(rows: list[dict]) -> list[dict]:
    """pro_american_exceptionalism / en / f2's ten positives relabelled to
    f1. ROW COUNT IS UNCHANGED at 400, so the row-count guard cannot catch
    this -- only the family/positives-per-family checks can, which is the
    point: this is the fault that specifically attacks the 6-cell scheme."""
    out = copy.deepcopy(rows)
    for row in out:
        if (
            row["concept_id"] == "pro_american_exceptionalism" and row["locale"] == "en"
            and row["split"] == "positive" and row.get("family") == "f2"
        ):
            row["family"] = "f1"
    return out


def _rows_with_v1_near_miss_semantics(rows: list[dict]) -> list[dict]:
    """THE DOCUMENTED TRAP, materialised: each concept's near_miss rows
    become its OWN positives and `near_miss_of` names its own concept --
    i.e. exactly what loading v2 with v1's meaning of the field produces.

    The 15 substituted rows are drawn 5 PER FAMILY rather than as the first
    15 in row order. That matters and was corrected after measuring: taking
    the first 15 loads f1 and f2 and leaves f3 facing other families'
    positives, which is not "its own positives" and produced a misleadingly
    high AUROC in one third of the cells. Five per family applies the
    inversion symmetrically, which is the shape the real defect would
    have."""
    out = copy.deepcopy(rows)
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        for concept_id in d.PERSONA_V2_CONCEPT_IDS:
            substitutes: list[str] = []
            for family in d.PERSONA_V2_FAMILIES:
                substitutes += [
                    r["text"] for r in d.rows_for_concept(
                        rows, concept_id=concept_id, locale=locale, split="positive", family=family
                    )
                ][:5]
            replaced = [
                r for r in out
                if r["concept_id"] == concept_id and r["locale"] == locale and r["split"] == "near_miss"
            ]
            for row, text in zip(replaced, substitutes, strict=True):
                row["text"] = text
                row["near_miss_of"] = concept_id
    return out


# ---------------------------------------------------------------------------
# Checks. Each returns (passed, detail-dict) and never swallows an exception
# that means "the thing under test is broken".
# ---------------------------------------------------------------------------


def check_frozen_bytes(repo_root: Path) -> tuple[bool, dict]:
    """The bytes actually loaded hash to the pinned digest, and the loader
    says which path they came from."""
    raw, origin = d._persona_v2_frozen_bytes(
        repo_root, relative_path=f"{d.PERSONA_V2_PROMPT_SET_DIR}/prompt_sets.jsonl",
        expected_sha256=d.PERSONA_V2_PROMPT_SETS_SHA256,
    )
    digest = hashlib.sha256(raw).hexdigest()
    return digest == d.PERSONA_V2_PROMPT_SETS_SHA256, {
        "origin": origin, "measured_sha256": digest, "pinned_sha256": d.PERSONA_V2_PROMPT_SETS_SHA256,
        "bytes": len(raw), "freeze_commit": d.PERSONA_V2_FREEZE_COMMIT,
    }


def check_corpus_loads_and_shape(artifact) -> tuple[bool, dict]:
    counts = artifact.metadata["persona_v2_measured_counts"]
    concepts = sorted({r["concept_id"] for r in artifact.rows})
    ok = (
        len(artifact.rows) == d.PERSONA_V2_ROW_COUNT
        and concepts == sorted(d.PERSONA_V2_CONCEPT_IDS)
    )
    return ok, {"rows": len(artifact.rows), "concepts": concepts, "per_concept_per_locale": counts}


def check_cell_plan(artifact) -> tuple[bool, dict]:
    """6 cells per concept, 10 positives / 15 near_miss / 15 unrelated each,
    derived through `concept_locale_texts` -- the same function the gates
    read their texts from."""
    plan = d.persona_v2_cell_plan(artifact)
    ok = len(plan) == d.PERSONA_V2_CONCEPT_COUNT
    for concept_id, entry in plan.items():
        ok = ok and entry["n_cells"] == 6
        keys = sorted((c["locale"], c["family"]) for c in entry["cells"])
        ok = ok and keys == sorted(
            (locale, family) for locale in d.FROZEN_PROMPT_SET_LOCALES for family in d.PERSONA_V2_FAMILIES
        )
        for cell in entry["cells"]:
            ok = ok and (cell["n_positive"], cell["n_near_miss"], cell["n_unrelated"]) == (10, 15, 15)
            ok = ok and cell["n_gate_a_negatives"] == 30 and cell["n_gate_c_negatives"] == 15
        del concept_id
    return ok, {"plan": plan}


def check_cell_scheme_matches_the_existing_14(repo_root: Path, artifact) -> tuple[bool, dict]:
    """MEASURED, not asserted: run the SAME `score_full_feature_space` over
    a v1 concept and over both persona concepts on the same surrogate
    backend, and compare the cell structure each reports.

    This is what makes "the persona concepts use the standard cell scheme"
    checkable rather than a claim. If the persona corpus ever produced a
    different locale set, a different family set or a different number of
    cells than the 14 already do, `cells_scored` or `families_by_locale`
    would differ here and this fails."""
    v1_artifact = d.load_frozen_prompt_artifact(repo_root, allow_pi_gated=True)
    v1_concept = sorted({r["concept_id"] for r in v1_artifact.rows})[0]

    backend, _model = _surrogate_backend()
    v1_scan = d.score_full_feature_space(backend, v1_artifact, concept_id=v1_concept)
    v1_shape = {"cells_scored": v1_scan.cells_scored, "families_by_locale": v1_scan.families_by_locale,
                "locales": list(v1_scan.locales)}

    persona_shapes = {}
    for concept_id in sorted({r["concept_id"] for r in artifact.rows}):
        scan = d.score_full_feature_space(backend, artifact, concept_id=concept_id)
        persona_shapes[concept_id] = {
            "cells_scored": scan.cells_scored, "families_by_locale": scan.families_by_locale,
            "locales": list(scan.locales),
        }

    # Denominator sizes, per cell, on both sides -- a scheme that matched in
    # cell COUNT but not in control-set size would still be a different
    # measurement, so compare those too.
    def _denominators(art, concept_id):
        out = {}
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            unrelated, near_miss, positives = d.concept_locale_texts(art, concept_id=concept_id, locale=locale)
            for family in sorted(positives):
                out[f"{locale}/{family}"] = (len(positives[family]), len(near_miss), len(unrelated))
        return out

    v1_denoms = _denominators(v1_artifact, v1_concept)
    persona_denoms = {c: _denominators(artifact, c) for c in persona_shapes}

    ok = all(shape == v1_shape for shape in persona_shapes.values()) and all(
        denom == v1_denoms for denom in persona_denoms.values()
    )
    return ok, {
        "v1_reference_concept": v1_concept, "v1_shape": v1_shape, "persona_shapes": persona_shapes,
        "v1_cell_denominators_positive_nearmiss_unrelated": {k: list(v) for k, v in v1_denoms.items()},
        "persona_cell_denominators": {
            c: {k: list(v) for k, v in denom.items()} for c, denom in persona_denoms.items()
        },
    }


def check_near_miss_is_the_mirror(artifact) -> tuple[bool, dict]:
    report = artifact.metadata["persona_v2_near_miss_mirror_check"]
    ok = all(
        per_locale["byte_identical_to_mirror_positives"] == per_locale["n_near_miss"]
        and per_locale["overlap_with_own_positives"] == 0
        for concept in report.values() for per_locale in concept.values()
    )
    total = sum(
        per_locale["n_near_miss"] for concept in report.values() for per_locale in concept.values()
    )
    matched = sum(
        per_locale["byte_identical_to_mirror_positives"]
        for concept in report.values() for per_locale in concept.values()
    )
    return ok, {"byte_identical_to_mirror_positives": f"{matched}/{total}", "per_concept": report}


def check_gates_are_the_frozen_values(artifact) -> tuple[bool, dict]:
    thresholds = artifact.metadata["thresholds"]
    expected = {
        "G_A_separation_auroc_min": 0.90,
        "G_B_fire_rate_min": 0.70,
        "G_B_activation_floor_fraction_of_observed_max": 0.20,
        "G_C_specificity_auroc_vs_near_miss_min": 0.75,
    }
    ok = all(thresholds.get(k) == v for k, v in expected.items())
    return ok, {
        "resolved_thresholds": {k: thresholds.get(k) for k in sorted(thresholds)},
        "corpus_author_declaration": artifact.metadata.get("thresholds_declared_by_corpus_author"),
        "provenance": artifact.metadata.get("thresholds_provenance"),
    }


def check_positions_default_is_all(artifact) -> tuple[bool, dict]:
    """Positions default to ALL per the standing science ruling. Read off
    the parser itself, not off a comment."""
    args = d.parse_args([
        "--mode", "grid", "--corpus", "persona-v2", "--allow-pi-gated",
        "--pairing", "gemma-3-12b-it", "--model-path", "/none", "--sae-path", "/none",
        "--shortlist-size", "1", "--out-dir", "/none", "--state-dir", "/none",
    ])
    parser_default = args.positions
    policy = artifact.metadata.get("positions_policy", {})
    ok = parser_default == "all" and policy.get("public_calibration") == "ALL"
    return ok, {"cli_default_positions": parser_default, "artifact_positions_policy": policy}


def check_gate_plumbing_receives_the_cells(artifact) -> tuple[bool, dict]:
    """End-to-end through `evaluate_concept_on_pairing` on the surrogate:
    every candidate must come back with 6 G-A/G-B records and 6 G-C
    records, each carrying n_positives == 10, and the pooled-negative
    identity `separation_auroc == (near_miss_auroc + unrelated_auroc)/2`
    must hold to floating-point noise.

    That identity is the load-bearing part: it can only hold if G-A's
    negative set really is `unrelated` POOLED with an equal-sized
    `near_miss`, so measuring it proves what the gates were actually
    handed, rather than trusting the row counts."""
    backend, model = _surrogate_backend()
    cache = d.FeatureMatrixCache()
    detail: dict[str, Any] = {"per_concept": {}}
    ok = True
    for concept_id in sorted({r["concept_id"] for r in artifact.rows}):
        verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id=concept_id, report_top_n=3)
        if verdict.status == "error":
            return False, {"concept_id": concept_id, "error": verdict.error}

        worst_identity_delta = 0.0
        cells_seen: set[tuple[str, str]] = set()
        n_positive_values: set[int] = set()
        for candidate in verdict.candidates_evaluated:
            ab = {(r["locale"], r["family"]): r for r in candidate["gate_a_b_results"]}
            gc = {(r["locale"], r["family"]): r for r in candidate["gate_c_results"]}
            if len(ab) != 6 or len(gc) != 6 or set(ab) != set(gc):
                ok = False
            cells_seen |= set(ab)
            n_positive_values |= {r["n_positives"] for r in ab.values()}
            for key, ab_cell in ab.items():
                locale, family = key
                unrelated_texts, near_miss_texts, positives = d.concept_locale_texts(
                    artifact, concept_id=concept_id, locale=locale
                )
                index = candidate["feature_index"]
                pos = cache.feature_scores(backend, positives[family], index)
                unrel = cache.feature_scores(backend, unrelated_texts, index)
                near = cache.feature_scores(backend, near_miss_texts, index)
                unrelated_auroc = d._auroc_from_scores(pos, unrel)
                near_auroc = d._auroc_from_scores(pos, near)
                worst_identity_delta = max(
                    worst_identity_delta,
                    abs(ab_cell["separation_auroc"] - (near_auroc + unrelated_auroc) / 2.0),
                    abs(gc[key]["near_miss_auroc"] - near_auroc),
                )

        cell_ok = cells_seen == {
            (locale, family) for locale in d.FROZEN_PROMPT_SET_LOCALES for family in d.PERSONA_V2_FAMILIES
        }
        ok = ok and cell_ok and n_positive_values == {10} and worst_identity_delta <= 1e-12
        detail["per_concept"][concept_id] = {
            "status": verdict.status,
            "features_scored": verdict.features_scored,
            "selection_mode": verdict.selection_mode,
            "candidates_recorded": len(verdict.candidates_evaluated),
            "cells_per_candidate": sorted(f"{a}/{b}" for a, b in cells_seen),
            "n_positives_seen": sorted(n_positive_values),
            "worst_|sep-(near+unrel)/2|": worst_identity_delta,
            "gate_c_subsumption_holds": (verdict.gate_c_subsumption or {}).get("holds"),
            "surviving_feature_indices_SURROGATE_ONLY": verdict.surviving_feature_indices,
        }
    detail["surrogate_forward_passes"] = model.forward_passes
    detail["WARNING"] = (
        "Every activation-derived number above is a SURROGATE number. It establishes that the plumbing "
        "delivers the right texts to the right gates; it establishes nothing whatsoever about "
        "Gemma-3-12B-it or Qwen3.5-27B."
    )
    return ok, detail


def check_committed_validator(repo_root: Path) -> tuple[bool, dict]:
    d.run_persona_prompt_set_validator(repo_root)
    return True, {"validator": f"{d.PERSONA_V2_PROMPT_SET_DIR}/validate_prompt_sets.py", "exit": 0}


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


def run_clean(repo_root: Path) -> dict:
    results: list[dict] = []

    def record(name: str, fn: Callable[[], tuple[bool, dict]]) -> bool:
        try:
            passed, detail = fn()
        except Exception as exc:  # a check that raised is a check that FAILED
            passed, detail = False, {"raised": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
        results.append({"check": name, "passed": bool(passed), "detail": detail})
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        print(json.dumps(detail, indent=2, ensure_ascii=False, default=str))
        return bool(passed)

    record("frozen_bytes_match_the_pinned_digest", lambda: check_frozen_bytes(repo_root))
    artifact = d.load_frozen_persona_artifact(repo_root)
    record("corpus_loads_with_the_pinned_shape", lambda: check_corpus_loads_and_shape(artifact))
    record("six_cells_per_concept", lambda: check_cell_plan(artifact))
    record("cell_scheme_matches_the_existing_14", lambda: check_cell_scheme_matches_the_existing_14(repo_root, artifact))
    record("near_miss_is_the_mirror_not_the_self", lambda: check_near_miss_is_the_mirror(artifact))
    record("gates_are_the_frozen_values", lambda: check_gates_are_the_frozen_values(artifact))
    record("positions_default_to_all", lambda: check_positions_default_is_all(artifact))
    record("gate_plumbing_receives_all_six_cells", lambda: check_gate_plumbing_receives_the_cells(artifact))
    record("committed_v2_validator_passes", lambda: check_committed_validator(repo_root))

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "control_arm": "none",
        "control_arm_note": (
            "This run shows only that the good path works. On its own it does NOT distinguish 'working' "
            "from 'not looking'. The --fault runs are what establish that these checks can fail; run "
            f"them: {', '.join(f for f in FAULTS if f != 'none')}."
        ),
        "corpus": {
            "dir": d.PERSONA_V2_PROMPT_SET_DIR,
            "freeze_commit": d.PERSONA_V2_FREEZE_COMMIT,
            "prompt_sets_sha256": artifact.prompt_sets_sha256,
            "metadata_sha256": artifact.metadata_sha256,
            "bytes_origin": artifact.metadata["persona_v2_bytes_origin"],
            "concept_ids": sorted({r["concept_id"] for r in artifact.rows}),
        },
        "checks": results,
        "passed_check_count": sum(1 for r in results if r["passed"]),
        "check_count": len(results),
        "overall_passed": all(r["passed"] for r in results),
        "unexercised_without_gpu": UNEXERCISED_WITHOUT_GPU,
        "authorises_no_submission": (
            "RULING_12 authorises no cluster submission and this preflight is not one. ENGINEERING "
            "PREVIEW ONLY."
        ),
    }


def run_fault(repo_root: Path, fault: str, tmp_root: Path) -> dict:
    """Drives ONE deliberately broken input and requires a loud refusal.

    The measured collapse for `invert-near-miss-of` is reported as well as
    the refusal: it is not enough to know the loader says no, the report
    should carry what the wrong semantics would have DONE, so that a future
    zero-survivor grid can be checked against a number instead of a memory."""
    print(f"=== CONTROL ARM: --fault {fault} -- this MUST be refused loudly ===")
    detail: dict[str, Any] = {}
    refusal: dict[str, Any] | None = None

    try:
        if fault == "corrupt-prompt-digest":
            broken = _broken_repo_with_corrupt_prompt_bytes(tmp_root, repo_root)
            detail["broken_repo_root"] = str(broken)
            detail["has_git_directory"] = (broken / ".git").exists()
            detail["note"] = (
                "No .git, so the loader must take the on-disk fallback -- the cluster's own situation. "
                "One character was changed in one persona prompt."
            )
            d.load_frozen_persona_artifact(broken)

        elif fault == "drop-family-rows":
            artifact = d.load_frozen_persona_artifact(repo_root)
            rows = _rows_with_a_family_dropped(artifact.rows)
            detail["rows_before"] = len(artifact.rows)
            detail["rows_after"] = len(rows)
            detail["removed"] = "pro_american_exceptionalism / en / positive / f2 (10 rows)"
            detail["digest_guard_note"] = (
                "Applied to the loaded rows, deliberately BELOW the sha256 guard: the digest would have "
                "rejected a file edited this way long before the structural check ran, which is exactly "
                "why a structural check reached only through the digest can never be shown to be alive."
            )
            d.build_persona_artifact(
                rows, json.loads((repo_root / d.PERSONA_V2_PROMPT_SET_DIR / "metadata.json").read_text(encoding="utf-8")),
                repo_root=repo_root, prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="fault-injected",
            )

        elif fault == "relabel-family-rows":
            artifact = d.load_frozen_persona_artifact(repo_root)
            rows = _rows_with_a_family_relabelled(artifact.rows)
            detail["rows_before"] = len(artifact.rows)
            detail["rows_after"] = len(rows)
            detail["relabelled"] = "pro_american_exceptionalism / en / positive / f2 -> f1 (10 rows)"
            detail["why_this_fault_and_not_only_the_drop"] = (
                "The row count is UNCHANGED at 400, so the row-count guard cannot see this. Only the "
                "family set and positives-per-family checks can, and those are the ones that guarantee "
                "6 cells of 10 positives each. A drop-only control would have left them undemonstrated."
            )
            d.build_persona_artifact(
                rows, json.loads((repo_root / d.PERSONA_V2_PROMPT_SET_DIR / "metadata.json").read_text(encoding="utf-8")),
                repo_root=repo_root, prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="fault-injected",
            )

        elif fault == "invert-near-miss-of":
            artifact = d.load_frozen_persona_artifact(repo_root)
            rows = _rows_with_v1_near_miss_semantics(artifact.rows)
            detail["note"] = (
                "Each concept's near_miss rows replaced by its OWN positives, near_miss_of set to its "
                "own concept -- i.e. v2 read with v1's meaning of the field."
            )
            detail["measured_collapse_on_the_surrogate"] = _measure_inverted_collapse(artifact, rows)
            d.build_persona_artifact(
                rows, json.loads((repo_root / d.PERSONA_V2_PROMPT_SET_DIR / "metadata.json").read_text(encoding="utf-8")),
                repo_root=repo_root, prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="fault-injected",
            )

        elif fault == "tamper-threshold":
            original = dict(d.PERSONA_V2_GATE_THRESHOLDS)
            try:
                d.PERSONA_V2_GATE_THRESHOLDS["G_A_separation_auroc_min"] = 0.85
                detail["tampered"] = {"G_A_separation_auroc_min": "0.90 -> 0.85"}
                detail["note"] = (
                    "The gate values are cross-checked against v1's sha256-pinned metadata.json on every "
                    "load, so they cannot be quietly moved in this file."
                )
                d.load_frozen_persona_artifact(repo_root)
            finally:
                d.PERSONA_V2_GATE_THRESHOLDS.clear()
                d.PERSONA_V2_GATE_THRESHOLDS.update(original)
        else:
            raise ValueError(f"unknown fault {fault!r}")

    except d.PromptArtifactError as exc:
        refusal = {"refused_with": type(exc).__name__, "message": str(exc)}
    except Exception as exc:  # any other exception is still a refusal, but a less specific one
        refusal = {"refused_with": type(exc).__name__, "message": str(exc), "unexpected_type": True}

    if refusal is None:
        print(f"[FAIL] fault {fault!r} was NOT refused -- the check cannot see the defect it claims to cover")
        refused = False
        refusal = {"refused_with": None, "message": "the injected fault was accepted silently"}
    else:
        print(f"[PASS] fault {fault!r} was refused: {refusal['refused_with']}")
        print(refusal["message"])
        refused = True

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "control_arm": fault,
        "control_arm_note": (
            "A control run. It passes when the broken input is REFUSED and fails when it is tolerated."
        ),
        "fault_detail": detail,
        "refusal": refusal,
        "overall_passed": refused,
        "unexercised_without_gpu": UNEXERCISED_WITHOUT_GPU,
        "authorises_no_submission": (
            "RULING_12 authorises no cluster submission and this preflight is not one. ENGINEERING "
            "PREVIEW ONLY."
        ),
    }


def _measure_inverted_collapse(artifact, inverted_rows: list[dict]) -> dict:
    """What the inverted semantics would DO, measured on the surrogate:
    near_miss_auroc against the concept's own positives, and the
    separation_auroc that the pooled identity then implies.

    Surrogate numbers, and labelled as such. What is claimed from them is
    the DIRECTION and the MECHANISM; the only exact statement in the
    returned dict is the pooling identity, which is arithmetic about the
    split sizes and involves no model at all."""
    import statistics

    backend, _model = _surrogate_backend()
    good_near: list[float] = []
    bad_near: list[float] = []
    bad_sep: list[float] = []
    inverted_artifact = d.FrozenPromptArtifact(
        commit="fault-injected", prompt_sets_sha256="n/a", metadata_sha256="n/a",
        metadata=artifact.metadata, rows=inverted_rows, pi_gated_excluded_row_count=0,
    )
    cache = d.FeatureMatrixCache()
    for concept_id in sorted({r["concept_id"] for r in artifact.rows}):
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            unrelated, near_ok, positives = d.concept_locale_texts(artifact, concept_id=concept_id, locale=locale)
            _u, near_bad, _p = d.concept_locale_texts(inverted_artifact, concept_id=concept_id, locale=locale)
            for family in sorted(positives):
                for index in (0, 1, 2, 3, 4):
                    pos = cache.feature_scores(backend, positives[family], index)
                    good_near.append(d._auroc_from_scores(pos, cache.feature_scores(backend, near_ok, index)))
                    bad = d._auroc_from_scores(pos, cache.feature_scores(backend, near_bad, index))
                    bad_near.append(bad)
                    unrel = d._auroc_from_scores(pos, cache.feature_scores(backend, unrelated, index))
                    bad_sep.append((bad + unrel) / 2.0)
    return {
        "cells_x_features_measured": len(bad_near),
        "mean_near_miss_auroc_correct_semantics_SURROGATE": statistics.mean(good_near),
        "mean_near_miss_auroc_INVERTED_SURROGATE": statistics.mean(bad_near),
        "max_near_miss_auroc_INVERTED_SURROGATE": max(bad_near),
        "max_implied_separation_auroc_INVERTED_SURROGATE": max(bad_sep),
        "G_A_threshold": d.PERSONA_V2_GATE_THRESHOLDS["G_A_separation_auroc_min"],
        "cells_clearing_G_A_under_inversion": sum(
            1 for s in bad_sep if s >= d.PERSONA_V2_GATE_THRESHOLDS["G_A_separation_auroc_min"]
        ),
        "what_is_EXACT_here": (
            "|near_miss| == |unrelated| == 15, so separation_auroc == (near_miss_auroc + "
            "unrelated_auroc)/2 identically, and unrelated_auroc <= 1. A G-A pass at 0.90 therefore "
            "REQUIRES near_miss_auroc >= 0.80. This is arithmetic about the split sizes; no model and "
            "no sample enters it."
        ),
        "what_is_MEASURED_here_and_only_measured": (
            "Under the inversion the near_miss set is drawn from the concept's OWN positives, so it is "
            "not a foil set and its AUROC sits near chance instead of near 1 -- which, by the exact "
            "statement above, is what starves G-A. Over the surrogate samples above, zero cells cleared "
            "G-A. NOT CLAIMED: a hard arithmetic ceiling for every possible feature. The exact bound "
            "holds only where a family's own positives are contained in the substituted rows; here 5 of "
            "each family's 10 are. The direction and the mechanism are the claim, and a zero-survivor "
            "persona grid should be checked against THIS before being read as a negative result."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(d.REPO_ROOT))
    p.add_argument(
        "--fault", choices=list(FAULTS), default="none",
        help="Inject a deliberate defect and require a loud refusal. Run these BEFORE trusting a clean pass.",
    )
    p.add_argument("--report", default=None, help="Path this preflight ALWAYS writes its JSON report to, pass or fail.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    try:
        if args.fault == "none":
            report = run_clean(repo_root)
        else:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="persona_v2_fault_") as tmp:
                report = run_fault(repo_root, args.fault, Path(tmp))
    except Exception as exc:
        report = {
            "schema_version": REPORT_SCHEMA_VERSION, "control_arm": args.fault, "overall_passed": False,
            "setup_failure": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(),
            "unexercised_without_gpu": UNEXERCISED_WITHOUT_GPU,
        }
        print(report["traceback"])

    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"report written to {path}")
    print(json.dumps({
        "control_arm": report["control_arm"], "overall_passed": report["overall_passed"],
        "passed_check_count": report.get("passed_check_count"), "check_count": report.get("check_count"),
    }, indent=2))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
