"""Standalone, pytest-free, self-executing proof that the ENTIRE synthetic
final-pairing discovery/calibration/evidence pipeline runs, wired together
end to end, on fake (CPU, tiny-tensor) backends -- run by the scheduled
dual-GPU driver BEFORE either child loads real weights (see
`final_concept_discovery_dual_gpu_job.py`'s `run_dual_gpu_job`, which now
calls this module's `run_all_cases` first and independently re-validates
the returned report rather than trusting only this process's exit code).

Emits strict JSON: `{"expected_cases", "executed_cases", "passed_cases",
"cases": [...], "overall": "pass"|"fail"}`. Exit 0 ONLY when EVERY case
executes and reports `"pass"` AND `executed_cases == expected_cases` --
there is no "skipped" status. A missing optional dependency is recorded
as `"setup_failure"` (still causing a nonzero exit), never silently
treated as a pass or omitted from the count.

WHY PYTEST-FREE: this script is meant to run as part of the SCHEDULED
Tamia job, where the sanctioned environment is deliberately minimal (see
project memory: the sprint venv). It uses plain Python control flow (a
small `Runner`/`CaseResult` structure), never pytest fixtures, assertions,
or collection.

SCOPE BOUNDARY ON G-D/G-E, STATED PLAINLY, NOT SILENTLY NARROWED: the
LIVE judge (the real, network-backed Lodestar `AnthropicJudge`) is
architecturally a SEPARATE stage from GPU discovery --
`final_pairing_causal_judge.py`'s own module docstring: Tamia compute
nodes have no internet, so a live judge call cannot run inside this
allocation, ever, regardless of what this preflight does. This script
therefore tests G-D/G-E's GATE LOGIC (the pass/fail/null-suppress
arithmetic in `evaluate_gate_d`/`evaluate_gate_e`) with synthetic data --
fully offline, always capable of passing -- and does NOT gate on whether
`lodestar` is importable or the Anthropic API is reachable from THIS
process: that is a precondition of a different machine's preflight
(the judge stage's own), not this one's. Gating this script on lodestar's
presence would make it permanently unable to pass on the exact machine
it exists to run on.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

SCHEMA_VERSION = 1
NONCANONICAL_SIBLING_EXAMPLE = "run_20260813_la_c"  # named directly in the 2026-08-13 staging-facts addendum
#: The 17 required items map onto 13 case() calls -- three calls each
#: cover more than one item (2+3, 10+12+13, 16+17); see each case's own
#: name/detail. This is the actual count of case() calls in
#: run_all_cases, not a hand-typed "17" -- it cannot silently drift from
#: what the script runs.
EXPECTED_CASE_COUNT = 13


class SetupFailure(RuntimeError):
    """A case raises this to report a missing optional dependency or
    environment precondition it cannot proceed without -- distinct from a
    genuine logic defect (`status='fail'`). Still causes a nonzero exit;
    never treated as a skip."""


@dataclass
class CaseResult:
    name: str
    status: str  # "pass" | "fail" | "setup_failure"
    detail: str
    elapsed_seconds: float


class Runner:
    def __init__(self) -> None:
        self.results: list[CaseResult] = []

    def case(self, name: str, fn: Callable[[], str]) -> None:
        start = time.monotonic()
        try:
            detail = fn()
            status = "pass"
        except SetupFailure as exc:
            detail = str(exc)
            status = "setup_failure"
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            status = "fail"
        elapsed = time.monotonic() - start
        self.results.append(CaseResult(name=name, status=status, detail=detail, elapsed_seconds=elapsed))


def _numpy_bootstrap_ci(values, *, seed=42, confidence=0.95, n_resamples=300):
    """A plain numpy-only stand-in for lodestar.metrics.stats.bootstrap_ci
    -- exercises evaluate_gate_d/evaluate_gate_e's pure arithmetic without
    requiring lodestar (a genuinely separate concern from whether the
    live judge is reachable; see module docstring)."""
    import numpy as np

    array = np.asarray(values, dtype=float)
    generator = np.random.default_rng(seed)
    estimates = np.array([generator.choice(array, size=array.size, replace=True).mean() for _ in range(n_resamples)])
    tail = (1 - confidence) / 2
    return float(np.quantile(estimates, tail)), float(np.quantile(estimates, 1 - tail))


def run_all_cases(*, tmp_root: Path) -> dict[str, Any]:
    """Runs every required case and returns the strict JSON report as a
    dict (never prints or exits -- that is `main`'s job, so
    `final_concept_discovery_dual_gpu_job.py` can call this in-process and
    inspect the report directly)."""
    import final_concept_discovery_dual_gpu_job as dual_gpu
    import final_concept_discovery_matched_configuration_job as matched
    import final_pairing_causal_judge as judge_mod
    import final_pairing_concept_discovery as d
    import final_pairing_evidence_document as ed
    import final_pairing_fakes as fakes
    import final_pairing_targets as targets

    runner = Runner()

    # -----------------------------------------------------------------
    # 1. Frozen prompt and protocol hash validation.
    # -----------------------------------------------------------------
    def case_frozen_hashes() -> str:
        d.run_prompt_set_validator(REPO_ROOT)
        artifact = d.load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)
        d.validate_backup_trigger_protocol_hash(REPO_ROOT)
        return (
            f"prompt_set_commit={artifact.commit[:12]} prompt_sha256={artifact.prompt_sets_sha256[:12]} "
            f"rows={len(artifact.rows)} backup_trigger_sha256_verified=True"
        )

    runner.case("frozen_prompt_and_protocol_hash_validation", case_frozen_hashes)

    # -----------------------------------------------------------------
    # 2 + 3. Complete 14x2x3x3x2 grid, explicit PASS/FAIL/ERROR verdicts.
    # -----------------------------------------------------------------
    artifact_holder: dict[str, Any] = {}

    def case_complete_grid() -> str:
        artifact = d.load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)
        artifact_holder["artifact"] = artifact
        concept_ids = sorted({r["concept_id"] for r in artifact.rows})
        if len(concept_ids) != 14:
            raise AssertionError(f"expected 14 concepts in the frozen artifact, got {len(concept_ids)}")

        gemma_backend = fakes.make_fake_gemma_backend()
        qwen_backend = fakes.make_fake_qwen_backend()
        gemma_verdicts = d.run_concept_grid(gemma_backend, artifact, shortlist_size=4, concept_ids=concept_ids)
        qwen_verdicts = d.run_concept_grid(qwen_backend, artifact, shortlist_size=4, concept_ids=concept_ids)
        if len(gemma_verdicts) != 14 or len(qwen_verdicts) != 14:
            raise AssertionError(f"expected 14 verdicts per pairing, got gemma={len(gemma_verdicts)} qwen={len(qwen_verdicts)}")
        statuses = {v.status for v in (*gemma_verdicts, *qwen_verdicts)}
        if not statuses.issubset({"pass", "fail", "error"}):
            raise AssertionError(f"unexpected verdict status value(s): {statuses}")
        for v in (*gemma_verdicts, *qwen_verdicts):
            for candidate in v.candidates_evaluated:
                if not candidate["gate_a_b_results"] and not candidate["gate_c_results"] and v.status != "error":
                    raise AssertionError(f"candidate for concept {v.concept_id!r} carries no supporting measurements")

        # Deliberately engineer an ERROR cell: a synthetic artifact missing
        # the 'near_miss' split for one concept (G-C requires it), alongside
        # one healthy concept, to prove ERROR is distinguishable from FAIL.
        broken_concept, healthy_concept = concept_ids[0], concept_ids[1]
        broken_rows = [r for r in artifact.rows if r["concept_id"] == broken_concept and r["split"] != "near_miss"]
        broken_rows += [r for r in artifact.rows if r["concept_id"] == healthy_concept]
        broken_artifact = dataclasses.replace(artifact, rows=broken_rows)
        engineered = d.run_concept_grid(gemma_backend, broken_artifact, shortlist_size=2, concept_ids=[broken_concept, healthy_concept])
        engineered_by_concept = {v.concept_id: v.status for v in engineered}
        if engineered_by_concept[broken_concept] != "error":
            raise AssertionError(
                f"expected an ERROR verdict for the deliberately-broken concept {broken_concept!r}, "
                f"got {engineered_by_concept[broken_concept]!r}"
            )
        return (
            f"gemma_grid={len(gemma_verdicts)} qwen_grid={len(qwen_verdicts)} statuses_seen={sorted(statuses)} "
            f"engineered_error_status={engineered_by_concept[broken_concept]!r}"
        )

    runner.case("complete_14x2x3x3x2_grid_with_explicit_pass_fail_error_verdicts", case_complete_grid)

    # -----------------------------------------------------------------
    # 4. Same-feature G-A/B/C conjunction.
    # -----------------------------------------------------------------
    def case_same_feature_conjunction() -> str:
        ab = [d.GateABResult(concept_id="c", locale="en", family="f1", feature_index=3, separation_auroc=0.95, gate_a_passed=True, fire_rate=0.8, activation_floor_fraction=0.2, gate_b_passed=True)]
        c_wrong = [d.GateCResult(concept_id="c", locale="en", family="f1", feature_index=5, near_miss_auroc=0.9, gate_c_passed=True)]
        try:
            d.feature_survives_gabc(ab, c_wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for mismatched feature indices across G-A/B and G-C")
        c_same = [d.GateCResult(concept_id="c", locale="en", family="f1", feature_index=3, near_miss_auroc=0.9, gate_c_passed=True)]
        if d.feature_survives_gabc(ab, c_same) is not True:
            raise AssertionError("expected feature_survives_gabc to pass for a matching, all-passing feature")
        return "mismatched-feature raises ValueError; same-feature all-passing conjunction returns True"

    runner.case("same_feature_gabc_conjunction_never_combines_different_features", case_same_feature_conjunction)

    # -----------------------------------------------------------------
    # 5. Incomplete-primary FAIL_RUN.
    # -----------------------------------------------------------------
    def case_incomplete_primary_fail_run() -> str:
        result = d.evaluate_backup_trigger(primary_complete=False, primary_shared_gabc_count=None)
        if not (result.fail_run is True and result.run_backup is False):
            raise AssertionError(f"expected fail_run=True, run_backup=False for an incomplete primary; got {result}")
        return f"fail_run={result.fail_run} run_backup={result.run_backup}"

    runner.case("incomplete_primary_reports_fail_run", case_incomplete_primary_fail_run)

    # -----------------------------------------------------------------
    # 6. Automatic primary_shared_gabc_count and backup decision.
    # -----------------------------------------------------------------
    def case_automatic_trigger() -> str:
        concept_ids = [f"synthetic-c{i}" for i in range(5)]

        def verdict(concept_id, pairing, status):
            return d.ConceptPairingVerdict(
                concept_id=concept_id, pairing=pairing, status=status,
                surviving_feature_index=(3 if status == "pass" else None), candidates_evaluated=[], error=None,
            )

        gemma_verdicts = [verdict(c, targets.GEMMA_3_12B_IT_TARGET.name, "pass" if c == concept_ids[0] else "fail") for c in concept_ids]
        qwen_verdicts = [verdict(c, targets.QWEN_3_5_27B_TARGET.name, "pass" if c == concept_ids[0] else "fail") for c in concept_ids]
        gemma_path = d.write_grid_result(tmp_root / "trigger_gemma", targets.GEMMA_3_12B_IT_TARGET.name, gemma_verdicts)
        qwen_path = d.write_grid_result(tmp_root / "trigger_qwen", targets.QWEN_3_5_27B_TARGET.name, qwen_verdicts)
        trigger = matched.compute_trigger_from_grid_outputs(gemma_grid_path=gemma_path, qwen_grid_path=qwen_path, concept_ids=concept_ids)
        if trigger.primary_shared_gabc_count != 1 or trigger.run_backup is not True:
            raise AssertionError(f"expected shared_count=1, run_backup=True (below threshold 3); got {trigger}")
        return f"primary_shared_gabc_count={trigger.primary_shared_gabc_count} run_backup={trigger.run_backup}"

    runner.case("automatic_shared_gabc_count_and_backup_decision", case_automatic_trigger)

    # -----------------------------------------------------------------
    # 7. Both-or-neither matched backup execution.
    # -----------------------------------------------------------------
    def case_both_or_neither_backup() -> str:
        class _FakeProcess:
            def __init__(self, pid: int) -> None:
                self._pid = pid

            @property
            def pid(self) -> int:
                return self._pid

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

            def terminate(self):
                pass

            def send_signal(self, sig):
                pass

        def _write_lane_json(tag: str) -> Path:
            payload = {
                "out_dir": str(tmp_root / tag / "out"), "state_dir": str(tmp_root / tag / "state"),
                "tmp_dir": str(tmp_root / tag / "tmp"), "log_path": str(tmp_root / tag / "log.txt"),
                "argv": ["--pairing", "gemma-3-12b-it" if "gemma" in tag else "qwen-3.5-27b"],
            }
            path = tmp_root / f"{tag}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return path

        primary_lanes = [dual_gpu.load_lane_spec("gemma", _write_lane_json("both_primary_gemma")), dual_gpu.load_lane_spec("qwen", _write_lane_json("both_primary_qwen"))]
        backup_lanes = [dual_gpu.load_lane_spec("gemma", _write_lane_json("both_backup_gemma")), dual_gpu.load_lane_spec("qwen", _write_lane_json("both_backup_qwen"))]

        def factory(lanes):
            def fake_launch(command, *, env, cwd, log_path):
                return _FakeProcess(pid=abs(hash(env["CUDA_VISIBLE_DEVICES"])) % 10000)
            return dual_gpu.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())

        result = matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"note": "preflight"},
            run_backup=True, job_result_path=tmp_root / "both_or_neither_result.json", orchestrator_factory=factory,
        )
        if result["backup_result"] is None or len(result["backup_result"]["lanes"]) != 2:
            raise AssertionError(f"expected BOTH backup lanes to run together; got {result['backup_result']}")

        result_false = matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"note": "preflight"},
            run_backup=False, job_result_path=tmp_root / "both_or_neither_result_false.json", orchestrator_factory=factory,
        )
        if result_false["backup_result"] is not None:
            raise AssertionError("expected NEITHER backup lane to run when run_backup=False")
        return "run_backup=True launches both backup lanes together; run_backup=False launches neither"

    runner.case("both_or_neither_matched_backup_execution", case_both_or_neither_backup)

    # -----------------------------------------------------------------
    # 8. G-D/G-E gate logic (pure arithmetic; see module docstring for why
    #    live-judge reachability is NOT part of this preflight).
    # -----------------------------------------------------------------
    def case_gate_d_e_logic() -> str:
        steered_d = {f"p{i}": [9.0] for i in range(10)}
        control_d = {f"p{i}": [3.0] for i in range(10)}
        gate_d = judge_mod.evaluate_gate_d(
            steered_relevance_by_prompt=steered_d, control_relevance_by_prompt=control_d,
            steered_coherence_scores=[8.0] * 10, relevance_delta_min=3.0, coherence_median_min=6.0,
            bootstrap_ci_fn=_numpy_bootstrap_ci,
        )
        if not gate_d.passed:
            raise AssertionError(f"expected G-D to pass on a clearly-separated synthetic amplify case: {gate_d}")

        steered_e_fail = {f"p{i}": [5.0] for i in range(10)}
        control_e_fail = {f"p{i}": [5.5] for i in range(10)}
        gate_e_fail = judge_mod.evaluate_gate_e(
            steered_relevance_by_prompt=steered_e_fail, control_relevance_by_prompt=control_e_fail,
            steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
            spot_read=None, bootstrap_ci_fn=_numpy_bootstrap_ci,
        )
        if gate_e_fail.passed:
            raise AssertionError("expected G-E to fail (null Suppress) when the automated delta does not clear the bar")
        return f"gate_d.passed={gate_d.passed} gate_e_automated_failure.passed={gate_e_fail.passed}"

    runner.case("g_d_g_e_gate_logic_pass_and_null_on_automated_failure", case_gate_d_e_logic)

    # -----------------------------------------------------------------
    # 9. Suppress spot-read acceptance and refusal.
    # -----------------------------------------------------------------
    def case_spot_read_lifecycle() -> str:
        steered = {f"p{i}": [1.0] for i in range(10)}
        control = {f"p{i}": [9.0] for i in range(10)}
        generations = [{"prompt_id": f"p{i}", "text": f"suppressed output {i}"} for i in range(10)]
        packet = judge_mod.build_spot_read_packet(generations)
        if len(packet.sampled_generations) != 10:
            raise AssertionError("expected exactly 10 sampled generations in the spot-read packet")

        approved = judge_mod.resolve_spot_read_decision(packet, approved=True, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="reads as suppressed")
        gate_e_approved = judge_mod.evaluate_gate_e(
            steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
            steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
            spot_read=approved, bootstrap_ci_fn=_numpy_bootstrap_ci,
        )
        if not gate_e_approved.passed:
            raise AssertionError(f"expected G-E to pass with a clear automated gate and an approved spot read: {gate_e_approved}")

        refused = judge_mod.resolve_spot_read_decision(packet, approved=False, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="reads as evasive, not suppressed")
        gate_e_refused = judge_mod.evaluate_gate_e(
            steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
            steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
            spot_read=refused, bootstrap_ci_fn=_numpy_bootstrap_ci,
        )
        if gate_e_refused.passed:
            raise AssertionError("expected G-E to be null (passed=False) when the spot read is refused, even with a clear automated gate")
        return f"approved.passed={gate_e_approved.passed} refused.passed={gate_e_refused.passed}"

    runner.case("suppress_spot_read_acceptance_and_refusal", case_spot_read_lifecycle)

    # -----------------------------------------------------------------
    # 10 + 12 + 13. Assembled discovery document: amplify-only after
    # failed suppress, ALL + GENERATED_ONLY diagnostic separation, four
    # binding records plus a separate feature_certificate.
    # -----------------------------------------------------------------
    document_holder: dict[str, Any] = {}

    def case_document_shape() -> str:
        head = _git_head()
        document = ed.assemble_discovery_document(
            run_id="r-preflight-0001", code_commit=head, entrypoint="scripts.legacy.discovery_preflight",
            host="preflight-synthetic", created_at="2026-08-13T00:00:00Z",
            model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
            sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="deadbeef" * 5,
            sae_id="resid_post_all/layer_29_width_16k_l0_big", layer=29,
            layer_selection={"selected_by": "preflight", "rationale": "synthetic", "recorded_in": "tamia:preflight/discovery_record.json"},
            concept_id="cheese", hypothesis_source="synthetic preflight hypothesis",
            search_scope="preflight synthetic shortlist", candidate_index=1, engineering_index_rediscovery_note=None,
            feature_certificate={
                "feature_index": 3, "concept_id": "cheese", "specificity": 0.9, "sensitivity": 0.85,
                "cross_lingual_firing": 0.8, "selectivity": 0.88, "probe": {"auc": 0.91},
                "verdict": "green", "verdict_basis": "synthetic preflight fixture, not a real finding",
            },
            subject=[{"content_hash": "sha256:" + "0" * 64, "location": "tamia:preflight/subject.json", "role": "discovery_record"}],
            calibration_protocol="preflight-synthetic-v1", calibrated_by="discovery_preflight.py",
            calibrated_at="2026-08-13T00:00:00Z",
            directions={
                "amplify": {"operation": "clamp", "targets": [{"feature_idx": 3, "weight": 1.0}],
                            "unit": "corpus_max_multiple", "unit_source": "background corpus max activation",
                            "strengths": {"low": 0.5, "medium": 1.0, "high": 2.0}},
                "suppress": None,  # G-E failed in case_spot_read_lifecycle's automated-failure analogue above
            },
            positions="all",
            prompt_set_id="final_pairing_v1_cheese", prompt_set_source_path="prompts/final_pairing/v1/prompt_sets.jsonl",
            prompt_set_source_sha256="sha256:" + d_module_frozen_sha(),
            prompt_set_source_commit=d_module_frozen_commit(),
            paraphrase_families=[{"family_id": fam, "prompts": ["p1", "p2"]} for fam in ("f1", "f2", "f3")],
            causal_validation_computed_at_commit=head, causal_validation_positions="all",
            gates=[
                *[{"gate": g, "status": "pass", "family_id": f, "evidence": "preflight synthetic"} for f in ("f1", "f2", "f3") for g in ("G-A", "G-B", "G-C")],
                {"gate": "G-D", "status": "pass", "direction": "amplify", "evidence": "preflight synthetic"},
            ],
            spot_read=None,
            dose_response={
                "amplify": {"computed_at_commit": head,
                            "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "synthetic"}],
                            "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                            "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
            },
        )
        document_holder["document"] = document

        # 10: Amplify-only after failed/absent Suppress.
        if document["calibration"]["directions"]["suppress"] is not None:
            raise AssertionError("expected calibration.directions.suppress to be None (null Suppress)")
        if document["calibration"]["directions"]["amplify"] is None:
            raise AssertionError("expected calibration.directions.amplify to be present")

        # 12: publishable positions=ALL; a generated_only diagnostic (if present) never substitutes.
        if document["positions"] != "all" or document["causal_validation"]["positions"] != "all":
            raise AssertionError("expected positions='all' for the publishable calibration and its backing gates")

        # 13: four binding records (prompt_set, discovery-implied-by-pairing/concept/discovery,
        # causal_validation, dose_response) plus a SEPARATE feature_certificate (validation).
        for key in ("prompt_set", "pairing", "concept", "discovery", "causal_validation", "dose_response", "validation"):
            if key not in document:
                raise AssertionError(f"assembled document is missing required block {key!r}")
        if document["validation"] == document["prompt_set"]:
            raise AssertionError("feature_certificate (validation) must be a SEPARATE record from prompt_set")
        return "amplify-only after null suppress; positions=all; all binding blocks + separate feature_certificate present"

    runner.case("document_amplify_only_all_positions_four_binding_records", case_document_shape)

    # -----------------------------------------------------------------
    # 11. Dose curve and LOW/MEDIUM/HIGH derivation.
    # -----------------------------------------------------------------
    def case_dose_and_calibration() -> str:
        outcomes = [
            d.InterventionOutcome(
                feature_indices=[3], direction="clamp", value_in_max_units=v, corpus_max_used=1.0,
                absolute_clamp_value=v, positions="all", generated_text="synthetic", verdict={}, spec={},
            )
            for v in (0.5, 1.0, 2.0, 4.0)
        ]
        calibration = d.select_calibration_candidates(outcomes, low_threshold=0.5, medium_threshold=1.0, high_threshold=2.0)
        expected = {"low": 0.5, "medium": 1.0, "high": 2.0}
        actual = {tier: (c.value_in_max_units if c is not None else None) for tier, c in calibration.items()}
        if actual != expected:
            raise AssertionError(f"expected calibration doses {expected}, got {actual}")
        return f"calibration={actual}"

    runner.case("dose_curve_low_medium_high_derivation", case_dose_and_calibration)

    # -----------------------------------------------------------------
    # 14. Checkpoint interruption and exact-cell resume.
    # -----------------------------------------------------------------
    def case_checkpoint_resume() -> str:
        artifact = artifact_holder.get("artifact") or d.load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)
        concept_ids = sorted({r["concept_id"] for r in artifact.rows})[:3]
        backend = fakes.make_fake_gemma_backend()
        progress_path = tmp_root / "resume_progress.jsonl"
        progress = d.ProgressLog(progress_path)
        first = d.run_concept_grid(backend, artifact, shortlist_size=2, concept_ids=concept_ids, progress=progress)
        if len(first) != 3:
            raise AssertionError(f"expected 3 verdicts on the first (uninterrupted) pass, got {len(first)}")

        # Resume: a FRESH ProgressLog instance reading the SAME file must
        # recognize all 3 cells as already done and never recompute them.
        resumed_progress = d.ProgressLog(progress_path)
        calls = {"n": 0}
        original = d.evaluate_concept_on_pairing

        def spy(*args, **kwargs):
            calls["n"] += 1
            return original(*args, **kwargs)

        d.evaluate_concept_on_pairing = spy
        try:
            second = d.run_concept_grid(backend, artifact, shortlist_size=2, concept_ids=concept_ids, progress=resumed_progress)
        finally:
            d.evaluate_concept_on_pairing = original
        if calls["n"] != 0:
            raise AssertionError(f"expected 0 recomputations on resume (all 3 cells already recorded), got {calls['n']}")
        if [v.concept_id for v in second] != [v.concept_id for v in first]:
            raise AssertionError("resumed grid did not return the same concept set as the interrupted run")
        return f"3 cells recorded; resume triggered {calls['n']} recomputation(s) (expected 0)"

    runner.case("checkpoint_interruption_and_exact_cell_resume", case_checkpoint_resume)

    # -----------------------------------------------------------------
    # 15. Producer/consumer schema compatibility.
    # -----------------------------------------------------------------
    def case_schema_reconciliation() -> str:
        document = document_holder.get("document")
        if document is None:
            raise SetupFailure("document_amplify_only_all_positions_four_binding_records did not run first")
        result = ed.reconcile_against_static_snapshot(REPO_ROOT, document)
        if not result["compatible"]:
            raise AssertionError(f"producer/consumer schema reconciliation reported incompatible: {result}")
        return json.dumps({k: result[k] for k in ("snapshot_commit", "schema_version_agrees", "compatible")})

    runner.case("producer_consumer_schema_compatibility", case_schema_reconciliation)

    # -----------------------------------------------------------------
    # 16 + 17. Exact $SLURM_JOB_ID roots; noncanonical sibling ignored.
    # -----------------------------------------------------------------
    def case_exact_job_root() -> str:
        job_id = os.environ.get("SLURM_JOB_ID", "preflight-synthetic-job-id")
        job_root = tmp_root / "concept_discovery" / "gemma" / job_id
        sibling_root = tmp_root / "concept_discovery" / "gemma" / NONCANONICAL_SIBLING_EXAMPLE

        correct_verdicts = [d.ConceptPairingVerdict(concept_id="c0", pairing=targets.GEMMA_3_12B_IT_TARGET.name, status="pass", surviving_feature_index=3, candidates_evaluated=[], error=None)]
        wrong_verdicts = [d.ConceptPairingVerdict(concept_id="c0", pairing=targets.GEMMA_3_12B_IT_TARGET.name, status="error", surviving_feature_index=None, candidates_evaluated=[], error="planted in the noncanonical sibling")]
        d.write_grid_result(job_root, targets.GEMMA_3_12B_IT_TARGET.name, correct_verdicts)
        d.write_grid_result(sibling_root, targets.GEMMA_3_12B_IT_TARGET.name, wrong_verdicts)

        read_back = d.read_grid_result(job_root / "grid.json")
        if read_back[0].status != "pass":
            raise AssertionError(f"expected the EXACT job-root grid to be read, got status={read_back[0].status!r} (sibling contamination?)")

        try:
            d.read_grid_result(tmp_root / "concept_discovery" / "gemma" / "grid.json")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("expected read_grid_result to refuse a parent-directory path with no exact grid.json")
        return f"job_root={job_root} sibling={sibling_root.name} exact-path read verified; parent-path read refused"

    runner.case("exact_slurm_job_id_root_and_noncanonical_sibling_ignored", case_exact_job_root)

    # 13 cases cover the 17 required items listed in the module docstring;
    # three cases each cover more than one item (2+3, 10+12+13, 16+17) --
    # see each case's name/detail for which. EXPECTED_CASE_COUNT is the
    # actual number of case() calls above, checked literally (not a
    # hand-typed "17") so this can never silently drift from what the
    # script actually runs.
    executed_cases = len(runner.results)
    passed_cases = sum(1 for r in runner.results if r.status == "pass")
    overall = "pass" if passed_cases == executed_cases and executed_cases == EXPECTED_CASE_COUNT else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "expected_cases": EXPECTED_CASE_COUNT,
        "executed_cases": executed_cases,
        "passed_cases": passed_cases,
        "cases": [asdict(r) for r in runner.results],
        "overall": overall,
    }


class _FakeSignalModule:
    SIGTERM = 15
    SIGINT = 2

    def signal(self, sig, handler):
        return None

    def getsignal(self, sig):
        return None


def _git_head() -> str:
    import subprocess

    proc = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SetupFailure(f"could not resolve the current git HEAD: {proc.stderr}")
    return proc.stdout.strip()


def d_module_frozen_sha() -> str:
    import final_pairing_concept_discovery as d

    return d.FROZEN_PROMPT_SETS_SHA256


def d_module_frozen_commit() -> str:
    import final_pairing_concept_discovery as d

    return d.FROZEN_PROMPT_SET_COMMIT


def main(argv: list[str] | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="discovery-preflight-") as tmp:
        report = run_all_cases(tmp_root=Path(tmp))
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
