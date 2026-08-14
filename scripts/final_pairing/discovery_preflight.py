"""Standalone, pytest-free, self-executing proof that the ENTIRE synthetic
final-pairing discovery/calibration/evidence pipeline runs, wired together
end to end, on fake (CPU, tiny-tensor) backends -- run by the scheduled
dual-GPU driver BEFORE either child loads real weights (see
`final_concept_discovery_dual_gpu_job.py`'s `run_dual_gpu_job`, which now
calls this module's `run_all_cases` first and independently re-validates
the returned report rather than trusting only this process's exit code).

LA-B PREFLIGHT CONTRACT (P0 FINAL DELTA, verbatim, no approximation): the
CLI accepts EXACTLY `--prompt-sets`, `--prompt-metadata`, `--backup-
trigger`, `--pairing-config`, `--gemma-output-root`, `--qwen-output-root`,
`--sentinel-dir`, `--report` -- eight flags, all required, no defaults.
`--report` is ALWAYS written, pass or fail: a setup-level exception (a bad
path, a hash mismatch in one of the four frozen artifacts) is caught in
`main()` and turned into a failure-shaped report rather than an
uncaught traceback with no JSON output at all.

The four explicit input paths (`--prompt-sets`/`--prompt-metadata`/
`--backup-trigger`/`--pairing-config`) exist so this script does not
assume its OWN file's location (`Path(__file__).resolve().parents[2]`)
still describes the real repository root after a `git archive` transfer
to a different directory layout -- `resolve_and_validate_repo_root`
derives the one true `repo_root` from `--prompt-sets` and then asserts
the other three resolve under that SAME root at their own frozen
relative locations, failing closed on any of the four pointing somewhere
inconsistent. DISCLOSED CHOICE: `--pairing-config` names `protocols/
final_pairing/v1/scientific_config_identity.json` (`IDENTITY_PROTOCOL_
PATH`, the frozen identity artifact this file's own module docstring
calls "v1.3.0, commit 5a5175d") -- the ONLY identity artifact this
contract's eight flags name a path for; the Qwen-specific supplemental
(`qwen_config_identity.json`) is still hash-validated internally (via
`repo_root`, derived from the four explicit paths), just not given its
own top-level CLI flag, since the contract lists exactly eight.

`--gemma-output-root`/`--qwen-output-root` are where this preflight
proves job-id-rooted output writing for each pairing (see `case_exact_
job_roots` below) -- the same directories the real scheduled job writes
`grid.json`/generation manifests under.

Emits EXACTLY this JSON (LA-B schema, `SCHEMA_VERSION` below): `{
"schema_version": <string>, "source_commit": <40-hex string>,
"expected_case_count": <int > 0>, "executed_case_count": <int>,
"passed_case_count": <int>, "failed_cases": [...names...],
"overall_passed": <bool>, "proofs": {...seven named booleans...}}` --
NO OTHER TOP-LEVEL FIELD, no "cases" array, no generic proof-key
vocabulary. `proofs` carries EXACTLY: `sweep_and_confirmation_seeds_
disjoint`, `all_required_per_dose_per_purpose_files_exist`, `concept_
complete_ordering`, `wall_time_refusal_before_incomplete_concept`,
`confirmation_outputs_all_five_doses_generated_not_inspected`,
`measured_sae_hashes_match_identity_v13`, `separate_scalar_direction_
manifests_amplify_and_suppress` -- seven keys, no more, no fewer, none
renamed. `source_commit` is resolved WITHOUT requiring `.git`
(`resolve_source_commit`: `transfer_manifest.json` on Tamia, live
`git rev-parse HEAD` on a dev checkout) and MUST equal the extraction's
own transfer-manifest commit when one is present -- `default_
preflight_runner` (in `final_concept_discovery_dual_gpu_job.py`)
independently re-checks this equality rather than trusting this
process's own report.

Internally this still runs MANY more real, pytest-free cases than the
seven named proofs alone (grid creation, gate logic, checkpoint resume,
schema reconciliation, staggered load, and more) -- `executed_case_count`
counts ALL of them, and `overall_passed` requires every one to pass, not
merely the seven that get their own named proof. `EXPECTED_CASE_COUNT`
is the actual number of `case()` calls in `run_all_cases`, never a
hand-typed guess that could silently drift from what the script runs.

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
it exists to run on. `final_pairing_judge_cli.py` (stages 4-5) is never
imported here either, for the same reason: the "all five confirmation
doses generated, only the selected three ever inspected" proof below is
built entirely from this module's/`final_pairing_one_allocation_
generation.py`'s own manifest vocabulary, not the judge stage's.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
LEGACY_SCRIPT_DIR = SCRIPT_DIR.parent / "legacy"
sys.path.insert(0, str(LEGACY_SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR))  # inserted LAST -> searched FIRST, so this file's own name never resolves to a scripts/legacy/ compatibility stub of the same name

#: LA-B schema, STRING now (was int 1) -- bumped for the P0 FINAL DELTA
#: contract rewrite (explicit CLI paths, the eight-field/seven-proof
#: report shape below), which is not backward-compatible with the prior
#: `expected_cases`/`executed_cases`/`passed_cases`/`cases` shape.
SCHEMA_VERSION = "2"
NONCANONICAL_SIBLING_EXAMPLE = "run_20260813_la_c"  # named directly in the 2026-08-13 staging-facts addendum
CONCEPT_FEATURE = 3  # matches final_pairing_fakes.CONCEPT_FEATURE -- the fake SAE's real concept-carrying feature
#: The actual number of `case()` calls in `run_all_cases` -- never a
#: hand-typed guess, and asserted equal to `len(runner.results)` at the
#: end of that function so it cannot silently drift.
EXPECTED_CASE_COUNT = 23

#: The SEVEN literal proof keys the LA-B contract requires, exactly as
#: named -- used both to build a passing report's `proofs` dict and to
#: build an all-False `proofs` dict for the setup-failure path (case 1
#: below), so the failure shape can never accidentally carry a DIFFERENT
#: key set than the success shape.
PROOF_KEYS: tuple[str, ...] = (
    "sweep_and_confirmation_seeds_disjoint",
    "all_required_per_dose_per_purpose_files_exist",
    "concept_complete_ordering",
    "wall_time_refusal_before_incomplete_concept",
    "confirmation_outputs_all_five_doses_generated_not_inspected",
    "measured_sae_hashes_match_identity_v13",
    "separate_scalar_direction_manifests_amplify_and_suppress",
)


class SetupFailure(RuntimeError):
    """A case raises this to report a missing optional dependency or
    environment precondition it cannot proceed without -- distinct from a
    genuine logic defect (`status='fail'`). Still causes a nonzero exit;
    never treated as a skip. Also raised by `resolve_and_validate_repo_
    root`/CLI-level setup problems that occur BEFORE `run_all_cases` is
    ever called -- `main()` catches this (and any other exception) at
    that outer level and still writes `--report`."""


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


def run_all_cases(*, tmp_root: Path, repo_root: Path, gemma_output_root: Path, qwen_output_root: Path) -> dict[str, Any]:
    """Runs every required case and returns the strict JSON report as a
    dict (never prints or exits -- that is `main`'s job, so
    `final_concept_discovery_dual_gpu_job.py` can call this in-process and
    inspect the report directly). `repo_root` is the LA-B-resolved root
    (from the four explicit `--prompt-sets`/etc. paths, never `REPO_ROOT`
    directly); `gemma_output_root`/`qwen_output_root` are where the
    job-id-rootedness proof writes real grid results."""
    # Re-assert SCRIPT_DIR at sys.path[0] before importing the two
    # non-legacy orchestration modules below: `final_pairing_harness.py`
    # (scripts/legacy/, imported transitively by `final_pairing_concept_
    # discovery` -- and, via `resolve_and_validate_repo_root`, possibly
    # already imported by the time this function runs) does its OWN
    # `sys.path.insert(0, str(Path(__file__).resolve().parent))` for ITS
    # OWN sibling-module needs (`gemma3_tool.py`) -- since ITS `__file__`
    # lives in scripts/legacy/, that push lands scripts/legacy ahead of
    # scripts/final_pairing globally. If that already happened, the FIRST
    # (i.e. cache-populating) import of `final_concept_discovery_dual_gpu_
    # job`/`final_concept_discovery_matched_configuration_job` below would
    # otherwise resolve to scripts/legacy's own thin `runpy`-forwarding
    # stubs of the SAME name (real, committed compatibility shims for the
    # old CLI path, never meant to be imported as a library) instead of
    # the real modules -- reproduced and root-caused during this rewrite.
    sys.path.insert(0, str(SCRIPT_DIR))
    import final_concept_discovery_dual_gpu_job as dual_gpu
    import final_concept_discovery_matched_configuration_job as matched
    import final_pairing_causal_judge as judge_mod
    import final_pairing_concept_discovery as d
    import final_pairing_evidence_document as ed
    import final_pairing_fakes as fakes
    import final_pairing_one_allocation_generation as one_alloc
    import final_pairing_targets as targets

    runner = Runner()

    # -----------------------------------------------------------------
    # 1. Frozen prompt and protocol hash validation.
    # -----------------------------------------------------------------
    def case_frozen_hashes() -> str:
        d.run_prompt_set_validator(repo_root)
        artifact = d.load_frozen_prompt_artifact(repo_root, allow_pi_gated=True)
        d.validate_backup_trigger_protocol_hash(repo_root)
        d.validate_scientific_config_identity_hash(repo_root)
        d.validate_qwen_config_identity_protocol_hash(repo_root)
        return (
            f"prompt_set_commit={artifact.commit[:12]} prompt_sha256={artifact.prompt_sets_sha256[:12]} "
            f"rows={len(artifact.rows)} backup_trigger_sha256_verified=True identity_v1.3_sha256_verified=True"
        )

    runner.case("frozen_prompt_and_protocol_hash_validation", case_frozen_hashes)

    # -----------------------------------------------------------------
    # 2. Complete 14x2x3x3x2 grid, explicit PASS/FAIL/ERROR verdicts.
    # -----------------------------------------------------------------
    artifact_holder: dict[str, Any] = {}

    def case_complete_grid() -> str:
        artifact = d.load_frozen_prompt_artifact(repo_root, allow_pi_gated=True)
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
    # 3. Same-feature G-A/B/C conjunction.
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
    # 4. Incomplete-primary FAIL_RUN.
    # -----------------------------------------------------------------
    def case_incomplete_primary_fail_run() -> str:
        result = d.evaluate_backup_trigger(primary_complete=False, primary_shared_gabc_count=None)
        if not (result.fail_run is True and result.run_backup is False):
            raise AssertionError(f"expected fail_run=True, run_backup=False for an incomplete primary; got {result}")
        return f"fail_run={result.fail_run} run_backup={result.run_backup}"

    runner.case("incomplete_primary_reports_fail_run", case_incomplete_primary_fail_run)

    # -----------------------------------------------------------------
    # 5. Automatic primary_shared_gabc_count and backup decision.
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
    # 6. Both-or-neither matched backup execution.
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
                # `run_matched_configuration_job` launches every lane group through
                # the REAL staggered cold-load handshake (`launch_staggered`, never
                # `launch_all`) -- the lead lane (Qwen) must write a real READY
                # record before the follower (Gemma) is ever launched, exactly as
                # the real `write_ready_record`/`wait_for_ready_record` machinery
                # requires; a fake launch that skips this would hang the follower's
                # wait forever (or, as `_FakeProcess.poll()` returning a real exit
                # code makes it look already-exited, raise ReadyHandshakeFailed
                # immediately instead).
                fake_pid = abs(hash(env["CUDA_VISIBLE_DEVICES"])) % 10000
                if env["CUDA_VISIBLE_DEVICES"] == dual_gpu.LANE_GPU_ASSIGNMENT[dual_gpu.STAGGER_LEAD_LANE]:
                    ready_index = command.index("--ready-path")
                    ready_path = Path(command[ready_index + 1])
                    # pid=fake_pid matches THIS fake process's own advertised pid --
                    # launch_staggered's wait_for_ready_record now requires the READY
                    # record's pid to equal the actual spawned (fake) process's pid.
                    d.write_ready_record(ready_path, pairing="qwen-3.5-27b", device="cuda:0", pid=fake_pid)
                return _FakeProcess(pid=fake_pid)
            return dual_gpu.DualGpuOrchestrator(lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule())

        # This case runs INSIDE discovery_preflight.py's own run_all_cases --
        # the real default `run_preflight` (dual_gpu.default_preflight_runner)
        # spawns `python discovery_preflight.py` as a SUBPROCESS, which would
        # recursively re-enter this exact case, spawning another subprocess,
        # without bound. Stubbed here (matching this project's own pytest
        # suite convention for the same call) so this case exercises
        # run_matched_configuration_job's SEQUENCING only, never a real
        # recursive preflight spawn.
        def fake_run_preflight(repo_root):
            return {
                "schema_version": SCHEMA_VERSION, "source_commit": "0" * 40,
                "expected_case_count": 0, "executed_case_count": 0, "passed_case_count": 0,
                "failed_cases": [], "overall_passed": True, "proofs": dict.fromkeys(PROOF_KEYS, True),
            }

        def fake_validate_prompt_artifact(repo_root):
            return None

        result = matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"note": "preflight"},
            run_backup=True, job_result_path=tmp_root / "both_or_neither_result.json", orchestrator_factory=factory,
            run_preflight=fake_run_preflight, validate_prompt_artifact=fake_validate_prompt_artifact,
        )
        if result["backup_result"] is None or len(result["backup_result"]["lanes"]) != 2:
            raise AssertionError(f"expected BOTH backup lanes to run together; got {result['backup_result']}")

        result_false = matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"note": "preflight"},
            run_backup=False, job_result_path=tmp_root / "both_or_neither_result_false.json", orchestrator_factory=factory,
            run_preflight=fake_run_preflight, validate_prompt_artifact=fake_validate_prompt_artifact,
        )
        if result_false["backup_result"] is not None:
            raise AssertionError("expected NEITHER backup lane to run when run_backup=False")
        return "run_backup=True launches both backup lanes together; run_backup=False launches neither"

    runner.case("both_or_neither_matched_backup_execution", case_both_or_neither_backup)

    # -----------------------------------------------------------------
    # 7. G-D/G-E gate logic (pure arithmetic; see module docstring for why
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
    # 8. Suppress spot-read acceptance and refusal.
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
    # 9. Assembled discovery document: amplify-only after failed suppress,
    #    ALL + GENERATED_ONLY diagnostic separation, four binding records
    #    plus a separate feature_certificate.
    # -----------------------------------------------------------------
    document_holder: dict[str, Any] = {}

    def case_document_shape() -> str:
        head = resolve_source_commit(repo_root)
        synthetic_manifest_path = tmp_root / "generation_manifest_amplify_synthetic.json"
        synthetic_manifest_path.write_text(json.dumps({"synthetic": "preflight manifest, not a real run"}), encoding="utf-8")
        synthetic_selection_path = tmp_root / "selection_record_amplify_synthetic.json"
        synthetic_selection_path.write_text(json.dumps({"synthetic": "preflight selection record, not a real run"}), encoding="utf-8")
        document = ed.assemble_discovery_document(
            run_id="r-preflight-0001", code_commit=head, entrypoint="scripts.final_pairing.discovery_preflight",
            host="preflight-synthetic", created_at="2026-08-13T00:00:00Z",
            model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
            sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="deadbeef" * 5,
            sae_id="resid_post_all/layer_29_width_16k_l0_big", layer=29,
            release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big", params_sha256=None,
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
            judge_model="claude-sonnet-4-5-20250929", judge_rubric_version="1.0", judge_prompt_version="lodestar-steering-v1",
            dose_response={
                "amplify": {"computed_at_commit": head,
                            "observations": [{"dose_multiple": 0.5, "arm": "steered", "n_generations": 20, "effect_note": "synthetic"}],
                            "unit": "corpus_max_multiple", "measured_maximum": 12.3,
                            "strength_mapping": {"low": 0.5, "medium": 1.0, "high": 2.0}},
            },
            configuration_name="primary", configuration_completeness="COMPLETE",
            configuration_model_n_layers=48, configuration_grid_cells_expected=1, configuration_grid_cells_recorded=1,
            generation_manifests={
                "amplify": ed.build_manifest_reference(synthetic_manifest_path, computed_at_commit=head),
                "suppress": None,
            },
            selection_records={
                "amplify": ed.build_selection_record_reference(
                    synthetic_selection_path, selection_commit=head, confirmation_judging_commit=head,
                ),
                "suppress": None,
            },
            # schema 5.0 (commit 3aff107): suppress publishes null here because
            # G-E failed in case_spot_read_lifecycle's automated-failure analogue
            # above -- suppress was genuinely attempted, so NOT_ATTEMPTED would
            # misreport it; NO_DOSE_CLEARED records that none of the four CLAMP
            # doses cleared G-E (this synthetic fixture attempted no ABLATE-only
            # clearance either).
            suppress_disposition=ed.build_suppress_disposition(reason="NO_DOSE_CLEARED", ablation_cleared_ge=False),
        )
        document_holder["document"] = document

        if document["calibration"]["directions"]["suppress"] is not None:
            raise AssertionError("expected calibration.directions.suppress to be None (null Suppress)")
        if document["calibration"]["directions"]["amplify"] is None:
            raise AssertionError("expected calibration.directions.amplify to be present")
        if document["positions"] != "all" or document["causal_validation"]["positions"] != "all":
            raise AssertionError("expected positions='all' for the publishable calibration and its backing gates")
        for key in ("prompt_set", "pairing", "concept", "discovery", "causal_validation", "dose_response", "validation"):
            if key not in document:
                raise AssertionError(f"assembled document is missing required block {key!r}")
        if document["validation"] == document["prompt_set"]:
            raise AssertionError("feature_certificate (validation) must be a SEPARATE record from prompt_set")
        return "amplify-only after null suppress; positions=all; all binding blocks + separate feature_certificate present"

    runner.case("document_amplify_only_all_positions_four_binding_records", case_document_shape)

    # -----------------------------------------------------------------
    # 10. Dose curve and LOW/MEDIUM/HIGH derivation.
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
    # 11. Checkpoint interruption and exact-cell resume.
    # -----------------------------------------------------------------
    def case_checkpoint_resume() -> str:
        artifact = artifact_holder.get("artifact") or d.load_frozen_prompt_artifact(repo_root, allow_pi_gated=True)
        concept_ids = sorted({r["concept_id"] for r in artifact.rows})[:3]
        backend = fakes.make_fake_gemma_backend()
        progress_path = tmp_root / "resume_progress.jsonl"
        progress = d.ProgressLog(progress_path)
        first = d.run_concept_grid(backend, artifact, shortlist_size=2, concept_ids=concept_ids, progress=progress)
        if len(first) != 3:
            raise AssertionError(f"expected 3 verdicts on the first (uninterrupted) pass, got {len(first)}")

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
    # 12. Producer/consumer schema compatibility -- OFFLINE, NON-GATING
    # defense-in-depth only (this Tamia compute node has no eng3/
    # concept-bundle checkout and no internet; the actual submission gate
    # is `run_gating_report_with_eng3`, run separately against a live
    # worktree -- see the closing report for that real result).
    # -----------------------------------------------------------------
    def case_schema_reconciliation() -> str:
        document = document_holder.get("document")
        if document is None:
            raise SetupFailure("document_amplify_only_all_positions_four_binding_records did not run first")
        result = ed.reconcile_against_static_snapshot(repo_root, document)
        if result["gating"]:
            raise AssertionError("reconcile_against_static_snapshot must never report itself as gating")
        if not result["compatible"]:
            raise AssertionError(f"producer/consumer schema reconciliation reported incompatible: {result}")
        return json.dumps({k: result[k] for k in ("snapshot_commit", "schema_version_agrees", "compatible", "gating")})

    runner.case("producer_consumer_schema_compatibility_offline_nongating", case_schema_reconciliation)

    # -----------------------------------------------------------------
    # 13. Exact $SLURM_JOB_ID roots (BOTH pairings' own output roots);
    #     noncanonical sibling ignored.
    # -----------------------------------------------------------------
    def case_exact_job_roots() -> str:
        job_id = os.environ.get("SLURM_JOB_ID", "preflight-synthetic-job-id")
        details = []
        for pairing_target, output_root in (
            (targets.GEMMA_3_12B_IT_TARGET, gemma_output_root), (targets.QWEN_3_5_27B_TARGET, qwen_output_root),
        ):
            job_root = output_root / job_id
            sibling_root = output_root / NONCANONICAL_SIBLING_EXAMPLE

            correct_verdicts = [d.ConceptPairingVerdict(concept_id="c0", pairing=pairing_target.name, status="pass", surviving_feature_index=3, candidates_evaluated=[], error=None)]
            wrong_verdicts = [d.ConceptPairingVerdict(concept_id="c0", pairing=pairing_target.name, status="error", surviving_feature_index=None, candidates_evaluated=[], error="planted in the noncanonical sibling")]
            d.write_grid_result(job_root, pairing_target.name, correct_verdicts)
            d.write_grid_result(sibling_root, pairing_target.name, wrong_verdicts)

            read_back = d.read_grid_result(job_root / "grid.json")
            if read_back[0].status != "pass":
                raise AssertionError(f"expected the EXACT job-root grid to be read for {pairing_target.name}, got status={read_back[0].status!r} (sibling contamination?)")

            try:
                d.read_grid_result(output_root / "grid.json")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError(f"expected read_grid_result to refuse a parent-directory path with no exact grid.json for {pairing_target.name}")
            details.append(f"{pairing_target.name}: job_root={job_root} sibling={sibling_root.name}")
        return "; ".join(details) + " -- exact-path reads verified, parent-path reads refused, for both pairings"

    runner.case("exact_slurm_job_id_root_and_noncanonical_sibling_ignored", case_exact_job_roots)

    # -----------------------------------------------------------------
    # 14. Causal generation order: FIXED, G-A/B/C-independent,
    #     political_framing always last (generation_settings.json
    #     section 4). Feeds the "concept_complete_ordering" proof.
    # -----------------------------------------------------------------
    def case_causal_generation_order() -> str:
        ordered = one_alloc.order_concepts_for_causal_generation(
            ["jazz", "political_framing", "formal_register", "cheese"]
        )
        if ordered != ["formal_register", "cheese", "jazz", "political_framing"]:
            raise AssertionError(f"expected the frozen order with political_framing last, got {ordered}")
        return f"ordered={ordered}"

    runner.case("causal_generation_order_is_fixed_and_political_framing_last", case_causal_generation_order)

    # -----------------------------------------------------------------
    # 15. One-allocation dose/control files carry REAL frozen prompt_ids
    #     (never synthetic), a resolvable control_ref, and the frozen
    #     EXPLICIT generation kwargs -- exercised through the real
    #     scheduled functions against a fake backend, never a stub.
    # -----------------------------------------------------------------
    def case_prompt_ids_controls_and_explicit_kwargs() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        rows = [
            {"prompt_id": f"C01.EN.HON.X0.0{i + 1}", "text": f"prompt {i}", "locale": "en", "split": "heldout_neutral", "ordinal": i + 1}
            for i in range(2)
        ]
        seeds = one_alloc.derive_seeds(
            namespace="sweep", concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
            locale="en", n_prompts=2, n_repeats=1,
        )
        control = one_alloc.generate_control_file(
            backend, corpus_max=corpus_max, positions="all", prompts=rows, purpose="sweep", n_repeats=1,
            seeds=seeds, max_new_tokens=1, out_dir=tmp_root / "prompt_id_proof", concept_id="cheese",
            pairing_id=backend.pairing, direction="amplify", locale="en",
            generation_kwargs=d.GENERATION_SETTINGS,
        )
        if control.prompt_ids != [r["prompt_id"] for r in rows]:
            raise AssertionError(f"expected the control's own prompt_ids to be the real frozen ids, got {control.prompt_ids}")
        dose_record = one_alloc.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=one_alloc.DoseSpec(dose_id="A3", kind="clamp", value_in_max_units=1.0),
            corpus_max=corpus_max, positions="all", prompts=rows, purpose="sweep", n_repeats=1, seeds=seeds,
            max_new_tokens=1, out_dir=tmp_root / "prompt_id_proof", concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en", control_ref=control.path, generation_kwargs=d.GENERATION_SETTINGS,
        )
        if dose_record.prompt_ids != control.prompt_ids:
            raise AssertionError("expected the dose file's prompt_ids to match its paired control's, in order")
        if dose_record.control_ref != control.path:
            raise AssertionError("expected the dose file's control_ref to resolve to the control's own path")
        payload = json.loads(Path(dose_record.path).read_text(encoding="utf-8"))
        first_generation = payload["generations"][0]
        if first_generation["prompt_id"] != rows[0]["prompt_id"]:
            raise AssertionError(f"expected a real frozen prompt_id inside the physical file, got {first_generation['prompt_id']!r}")
        return f"prompt_ids={dose_record.prompt_ids} control_ref_resolves=True generation_kwargs_passed=True"

    runner.case("one_allocation_dose_and_control_files_carry_real_prompt_ids_and_explicit_kwargs", case_prompt_ids_controls_and_explicit_kwargs)

    # -----------------------------------------------------------------
    # 16. Generation manifest: schema-required fields, one entry per
    #     generation (not per physical file), real transfer verification.
    # -----------------------------------------------------------------
    def case_generation_manifest_schema_required_fields() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        rows = [
            {"prompt_id": f"p{i}", "text": f"prompt {i}", "locale": "en", "split": "heldout_neutral", "ordinal": i + 1}
            for i in range(2)
        ]
        seeds = one_alloc.derive_seeds(
            namespace="sweep", concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
            locale="en", n_prompts=2, n_repeats=1,
        )
        control = one_alloc.generate_control_file(
            backend, corpus_max=corpus_max, positions="all", prompts=rows, purpose="sweep", n_repeats=1,
            seeds=seeds, max_new_tokens=1, out_dir=tmp_root / "manifest_proof", concept_id="cheese",
            pairing_id=backend.pairing, direction="amplify", locale="en", generation_kwargs=d.GENERATION_SETTINGS,
        )
        dose_record = one_alloc.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=one_alloc.DoseSpec(dose_id="A3", kind="clamp", value_in_max_units=1.0),
            corpus_max=corpus_max, positions="all", prompts=rows, purpose="sweep", n_repeats=1, seeds=seeds,
            max_new_tokens=1, out_dir=tmp_root / "manifest_proof", concept_id="cheese", pairing_id=backend.pairing,
            direction="amplify", locale="en", control_ref=control.path, generation_kwargs=d.GENERATION_SETTINGS,
        )
        manifest_path = tmp_root / "manifest_proof" / "generation_manifest_amplify.json"
        one_alloc.write_generation_manifest(
            [control, dose_record], manifest_path,
            run_id="r-preflight-0001", source_commit="0" * 40, configuration_name="primary",
            concept_id="cheese", pairing_id="google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
            model_revision="0" * 40, sae_revision="0" * 40, release="gemma-scope-2-12b-it-res-all",
            loader_sae_id="layer_29_width_16k_l0_big", scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
            measured_params_sha256="1" * 64,
            generation_kwargs=d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS),
            chat_template_identity="gemma-it-v1", locales_complete=["en"], causal_order_position=2,
            skipped_for_gate_failure=["formal_register"],  # position 1, strictly before "cheese" (position 2)
            dose_grid=one_alloc.load_causal_dose_grid(repo_root)[0],
        )
        verified = one_alloc.verify_generation_manifest(manifest_path)
        missing = sorted(set(one_alloc.MANIFEST_REQUIRED_FIELDS) - set(verified))
        if missing:
            raise AssertionError(f"manifest missing required field(s): {missing}")
        if len(verified["files"]) != 4:  # 2 control generations + 2 dose generations
            raise AssertionError(f"expected 4 per-generation manifest entries, got {len(verified['files'])}")
        if not all(set(one_alloc.MANIFEST_FILE_REQUIRED_FIELDS) - {"dose", "control_ref"} <= set(e) for e in verified["files"]):
            raise AssertionError("a files[] entry is missing a required field beyond the CONTROL-only exclusions")
        return f"files={len(verified['files'])} causal_order_position={verified['causal_order_position']} inventory_stage={verified.get('inventory_stage')}"

    runner.case("generation_manifest_schema_required_fields_round_trip", case_generation_manifest_schema_required_fields)

    # -----------------------------------------------------------------
    # 17. Concept-generation wall-time readiness gate (pure arithmetic),
    #     fed a REAL measured (not guessed) per-generation timing sample.
    # -----------------------------------------------------------------
    def case_readiness_and_measured_timing() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        call_count = {"n": 0}

        def fake_run_intervention(*args, **kwargs):
            call_count["n"] += 1
            return d.run_intervention(*args, **kwargs)

        fake_clock = {"t": 0.0}

        def fake_time_fn():
            fake_clock["t"] += 1.0  # each call "takes" exactly 1.0s, deterministically
            return fake_clock["t"]

        timing = one_alloc.measure_seconds_per_generation(
            backend, feature_indices=[CONCEPT_FEATURE], corpus_max=corpus_max, positions="all",
            prompt="prompt 0", base_seed=0, max_new_tokens=1, generation_kwargs=d.GENERATION_SETTINGS,
            n_samples=3, run_intervention_fn=fake_run_intervention, time_fn=fake_time_fn,
        )
        if call_count["n"] != 3:
            raise AssertionError(f"expected 3 real run_intervention calls (n_samples=3), got {call_count['n']}")
        if timing["seconds_per_generation"] != 1.0:
            raise AssertionError(f"expected a MEASURED 1.0s/generation from the deterministic fake clock, got {timing['seconds_per_generation']}")
        if "measured" not in timing["basis"].lower():
            raise AssertionError(f"timing basis must explicitly say 'measured', got {timing['basis']!r}")

        ready = one_alloc.assess_concept_generation_readiness(
            remaining_wall_time_seconds=one_alloc.GENERATIONS_PER_CONCEPT * 2.0,
            seconds_per_generation=timing["seconds_per_generation"],
        )
        not_ready = one_alloc.assess_concept_generation_readiness(
            remaining_wall_time_seconds=1.0, seconds_per_generation=timing["seconds_per_generation"],
        )
        if not ready.attempt or not_ready.attempt:
            raise AssertionError(f"expected ready.attempt=True, not_ready.attempt=False; got {ready} / {not_ready}")
        return f"measured_seconds_per_generation={timing['seconds_per_generation']} ready={ready.attempt} not_ready={not_ready.attempt}"

    runner.case("concept_generation_readiness_gate_and_measured_per_generation_timing", case_readiness_and_measured_timing)

    # -----------------------------------------------------------------
    # 18. LA-B proof: sweep_and_confirmation_seeds_disjoint.
    # -----------------------------------------------------------------
    def case_seeds_disjoint() -> str:
        sweep_seeds = one_alloc.derive_seeds(
            namespace="sweep", concept_id="cheese", pairing_id="google/gemma-3-12b-it", direction="amplify",
            locale="en", n_prompts=one_alloc.SWEEP_PROMPTS_PER_DIRECTION, n_repeats=one_alloc.SWEEP_REPEATS,
        )
        confirmation_seeds = one_alloc.derive_seeds(
            namespace="confirmation", concept_id="cheese", pairing_id="google/gemma-3-12b-it", direction="amplify",
            locale="en", n_prompts=one_alloc.CONFIRMATION_PROMPTS_PER_DIRECTION, n_repeats=one_alloc.CONFIRMATION_REPEATS,
        )
        one_alloc.assert_seed_sets_disjoint(sweep_seeds, confirmation_seeds)  # must NOT raise
        overlap = set(sweep_seeds) & set(confirmation_seeds)
        if overlap:
            raise AssertionError(f"sweep/confirmation seed sets are not actually disjoint: {overlap}")
        # Prove the check is REAL (not vacuously true): identical namespaces collide.
        same_namespace_seeds = one_alloc.derive_seeds(
            namespace="sweep", concept_id="cheese", pairing_id="google/gemma-3-12b-it", direction="amplify",
            locale="en", n_prompts=one_alloc.SWEEP_PROMPTS_PER_DIRECTION, n_repeats=one_alloc.SWEEP_REPEATS,
        )
        try:
            one_alloc.assert_seed_sets_disjoint(sweep_seeds, same_namespace_seeds)
        except one_alloc.SeedCollisionError:
            pass
        else:
            raise AssertionError("expected assert_seed_sets_disjoint to refuse two identical (same-namespace) seed sets")
        return f"S_sweep ({len(sweep_seeds)}) and S_conf ({len(confirmation_seeds)}) disjoint; identical-namespace collision correctly refused"

    runner.case("sweep_and_confirmation_seeds_disjoint", case_seeds_disjoint)

    # -----------------------------------------------------------------
    # 19. LA-B proof: all_required_per_dose_per_purpose_files_exist --
    #     the full 5-point amplify grid, both sweep and confirmation
    #     purposes, every required (purpose, dose) combination present.
    # -----------------------------------------------------------------
    def case_all_required_per_dose_per_purpose_files_exist() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        rows = [
            {"prompt_id": f"p{i}", "text": f"prompt {i}", "locale": "en", "split": "heldout_neutral", "ordinal": i + 1}
            for i in range(2)
        ]
        amplify_grid, _suppress_grid_unused = one_alloc.load_causal_dose_grid(repo_root)
        if len(amplify_grid) != one_alloc.DOSES_PER_DIRECTION:
            raise AssertionError(f"expected {one_alloc.DOSES_PER_DIRECTION} amplify grid points, got {len(amplify_grid)}")

        records = []
        for purpose in ("sweep", "confirmation"):
            seeds = one_alloc.derive_seeds(
                namespace=purpose, concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
                locale="en", n_prompts=2, n_repeats=1,
            )
            control = one_alloc.generate_control_file(
                backend, corpus_max=corpus_max, positions="all", prompts=rows, purpose=purpose, n_repeats=1,
                seeds=seeds, max_new_tokens=1, out_dir=tmp_root / "per_dose_purpose_proof", concept_id="cheese",
                pairing_id=backend.pairing, direction="amplify", locale="en", generation_kwargs=d.GENERATION_SETTINGS,
            )
            records.append(control)
            for dose in amplify_grid:
                records.append(one_alloc.generate_dose_file(
                    backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all", prompts=rows,
                    purpose=purpose, n_repeats=1, seeds=seeds, max_new_tokens=1,
                    out_dir=tmp_root / "per_dose_purpose_proof", concept_id="cheese", pairing_id=backend.pairing,
                    direction="amplify", locale="en", control_ref=control.path, generation_kwargs=d.GENERATION_SETTINGS,
                ))
        manifest_path = tmp_root / "per_dose_purpose_proof" / "generation_manifest_amplify.json"
        one_alloc.write_generation_manifest(
            records, manifest_path,
            run_id="r-preflight-0001", source_commit="0" * 40, configuration_name="primary",
            concept_id="cheese", pairing_id="google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
            model_revision="0" * 40, sae_revision="0" * 40, release="gemma-scope-2-12b-it-res-all",
            loader_sae_id="layer_29_width_16k_l0_big", scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
            measured_params_sha256="1" * 64,
            generation_kwargs=d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS),
            chat_template_identity="gemma-it-v1", locales_complete=["en"], causal_order_position=1,
            skipped_for_gate_failure=[], dose_grid=amplify_grid,
        )
        verified = one_alloc.verify_generation_manifest(manifest_path)
        dose_ids = [dose.dose_id for dose in amplify_grid]
        required = {(purpose.upper(), dose_id) for purpose in ("sweep", "confirmation") for dose_id in dose_ids}
        present = {(e["purpose"], e.get("dose")) for e in verified["files"] if e["purpose"] != "CONTROL"}
        missing = required - present
        if missing:
            raise AssertionError(f"manifest is missing required (purpose, dose) file(s): {sorted(missing)}")
        control_present = any(e["purpose"] == "CONTROL" for e in verified["files"])
        if not control_present:
            raise AssertionError("manifest is missing its required CONTROL entries")
        return f"all {len(required)} required (purpose, dose) combinations present across the full {one_alloc.DOSES_PER_DIRECTION}-point amplify grid, both purposes"

    runner.case("all_required_per_dose_per_purpose_files_exist", case_all_required_per_dose_per_purpose_files_exist)

    # -----------------------------------------------------------------
    # 20. LA-B proof: confirmation_outputs_all_five_doses_generated_
    #     not_inspected -- all five CONFIRMATION doses are generated (real
    #     files, in the manifest); a 3-of-5 selection touches only the
    #     three selected doses' physical files, never the other two
    #     (ADDITION_3: one physical file per dose).
    # -----------------------------------------------------------------
    def case_confirmation_all_five_doses_generated_not_inspected() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        rows = [
            {"prompt_id": f"p{i}", "text": f"prompt {i}", "locale": "en", "split": "heldout_eliciting", "ordinal": i + 1}
            for i in range(2)
        ]
        _amplify_grid_unused, suppress_grid = one_alloc.load_causal_dose_grid(repo_root)
        if len(suppress_grid) != one_alloc.DOSES_PER_DIRECTION:
            raise AssertionError(f"expected {one_alloc.DOSES_PER_DIRECTION} suppress grid points, got {len(suppress_grid)}")

        seeds = one_alloc.derive_seeds(
            namespace="confirmation", concept_id="cheese", pairing_id=backend.pairing, direction="suppress",
            locale="en", n_prompts=2, n_repeats=1,
        )
        control = one_alloc.generate_control_file(
            backend, corpus_max=corpus_max, positions="all", prompts=rows, purpose="confirmation", n_repeats=1,
            seeds=seeds, max_new_tokens=1, out_dir=tmp_root / "five_dose_proof", concept_id="cheese",
            pairing_id=backend.pairing, direction="suppress", locale="en", generation_kwargs=d.GENERATION_SETTINGS,
        )
        dose_records = [
            one_alloc.generate_dose_file(
                backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all", prompts=rows,
                purpose="confirmation", n_repeats=1, seeds=seeds, max_new_tokens=1,
                out_dir=tmp_root / "five_dose_proof", concept_id="cheese", pairing_id=backend.pairing,
                direction="suppress", locale="en", control_ref=control.path, generation_kwargs=d.GENERATION_SETTINGS,
            )
            for dose in suppress_grid
        ]
        manifest_path = tmp_root / "five_dose_proof" / "generation_manifest_suppress.json"
        one_alloc.write_generation_manifest(
            [control, *dose_records], manifest_path,
            run_id="r-preflight-0001", source_commit="0" * 40, configuration_name="primary",
            concept_id="cheese", pairing_id="google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
            model_revision="0" * 40, sae_revision="0" * 40, release="gemma-scope-2-12b-it-res-all",
            loader_sae_id="layer_29_width_16k_l0_big", scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
            measured_params_sha256="1" * 64,
            generation_kwargs=d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS),
            chat_template_identity="gemma-it-v1", locales_complete=["en"], causal_order_position=1,
            skipped_for_gate_failure=[], dose_grid=suppress_grid,
        )
        verified = one_alloc.verify_generation_manifest(manifest_path)
        confirmation_doses = sorted({e["dose"] for e in verified["files"] if e["purpose"] == "CONFIRMATION"})
        if len(confirmation_doses) != one_alloc.DOSES_PER_DIRECTION:
            raise AssertionError(f"expected {one_alloc.DOSES_PER_DIRECTION} distinct CONFIRMATION doses generated, got {confirmation_doses}")

        selected, unselected = confirmation_doses[:3], confirmation_doses[3:]
        inspected_paths = {e["path"] for e in verified["files"] if e["purpose"] == "CONFIRMATION" and e["dose"] in selected}
        unselected_paths = {e["path"] for e in verified["files"] if e["purpose"] == "CONFIRMATION" and e["dose"] in unselected}
        if inspected_paths & unselected_paths:
            raise AssertionError("selected and unselected confirmation doses must never share a physical file (ADDITION_3: one file per dose)")
        return (
            f"generated {len(confirmation_doses)} confirmation doses={confirmation_doses}; a 3-of-5 selection "
            f"touches {len(inspected_paths)} file(s), disjoint from the {len(unselected_paths)} unselected file(s)"
        )

    runner.case("confirmation_outputs_all_five_doses_generated_not_inspected", case_confirmation_all_five_doses_generated_not_inspected)

    # -----------------------------------------------------------------
    # 21. LA-B proof: measured_sae_hashes_match_identity_v13 -- the v1.3.0
    #     identity artifact's own hash pin, and the measured-vs-expected
    #     mechanism (Gemma AND Qwen) accepting a real match and refusing a
    #     mismatch, never trusted by construction alone.
    # -----------------------------------------------------------------
    def case_measured_sae_hashes_match_identity_v13() -> str:
        d.validate_scientific_config_identity_hash(repo_root)
        if d.IDENTITY_PROTOCOL_COMMIT != "5a5175d36eac9802b45f76aeb5b52ff6b25220a8":
            raise AssertionError(f"expected identity artifact commit 5a5175d... (v1.3.0), got {d.IDENTITY_PROTOCOL_COMMIT!r}")

        measured_hash_dir = tmp_root / "measured_hash_proof"
        measured_hash_dir.mkdir(parents=True, exist_ok=True)
        gemma_params = measured_hash_dir / "params.safetensors"
        gemma_params.write_bytes(b"synthetic gemma params bytes for hash-measurement proof")
        gemma_measured = d.compute_file_sha256(gemma_params)
        d.assert_params_sha256_matches([str(gemma_params)], expected_sha256=gemma_measured)  # must NOT raise
        try:
            d.assert_params_sha256_matches([str(gemma_params)], expected_sha256="0" * 64)
        except targets.TargetIdentityMismatch:
            pass
        else:
            raise AssertionError("expected assert_params_sha256_matches to refuse a measured/expected mismatch")

        qwen_layer_file = measured_hash_dir / "layer38.sae.pt"
        qwen_layer_file.write_bytes(b"synthetic qwen layer bytes for hash-measurement proof")
        qwen_measured = d.compute_file_sha256(qwen_layer_file)
        d.assert_qwen_params_sha256_matches(str(qwen_layer_file), expected_sha256=qwen_measured)  # must NOT raise
        try:
            d.assert_qwen_params_sha256_matches(str(qwen_layer_file), expected_sha256="0" * 64)
        except targets.TargetIdentityMismatch:
            pass
        else:
            raise AssertionError("expected assert_qwen_params_sha256_matches to refuse a measured/expected mismatch")

        return (
            f"identity artifact {d.IDENTITY_PROTOCOL_COMMIT[:12]} (v1.3.0) hash-pinned; Gemma and Qwen "
            f"measured-vs-expected mechanisms each accept a real match and refuse a mismatch"
        )

    runner.case("measured_sae_hashes_match_identity_v13", case_measured_sae_hashes_match_identity_v13)

    # -----------------------------------------------------------------
    # 22. LA-B proof: separate_scalar_direction_manifests_amplify_and_
    #     suppress -- amplify and suppress each get their OWN, physically
    #     separate manifest, and each manifest's own "direction" field is
    #     a SCALAR (never a list) naming exactly that one direction.
    # -----------------------------------------------------------------
    def case_separate_scalar_direction_manifests() -> str:
        backend = fakes.make_fake_gemma_backend()
        corpus_max = d.corpus_max_per_feature(backend, ["background text"])
        rows = [{"prompt_id": "p0", "text": "prompt 0", "locale": "en", "split": "heldout_neutral", "ordinal": 1}]

        manifests: dict[str, dict] = {}
        for direction in ("amplify", "suppress"):
            seeds = one_alloc.derive_seeds(
                namespace="sweep", concept_id="cheese", pairing_id=backend.pairing, direction=direction,
                locale="en", n_prompts=1, n_repeats=1,
            )
            control = one_alloc.generate_control_file(
                backend, corpus_max=corpus_max, positions="all", prompts=rows, purpose="sweep", n_repeats=1,
                seeds=seeds, max_new_tokens=1, out_dir=tmp_root / "direction_proof" / direction, concept_id="cheese",
                pairing_id=backend.pairing, direction=direction, locale="en", generation_kwargs=d.GENERATION_SETTINGS,
            )
            dose = (
                one_alloc.DoseSpec(dose_id="S5", kind="ablate") if direction == "suppress"
                else one_alloc.DoseSpec(dose_id="A3", kind="clamp", value_in_max_units=1.0)
            )
            dose_record = one_alloc.generate_dose_file(
                backend, [CONCEPT_FEATURE], dose=dose, corpus_max=corpus_max, positions="all", prompts=rows,
                purpose="sweep", n_repeats=1, seeds=seeds, max_new_tokens=1,
                out_dir=tmp_root / "direction_proof" / direction, concept_id="cheese", pairing_id=backend.pairing,
                direction=direction, locale="en", control_ref=control.path, generation_kwargs=d.GENERATION_SETTINGS,
            )
            manifest_path = tmp_root / "direction_proof" / f"generation_manifest_{direction}.json"
            one_alloc.write_generation_manifest(
                [control, dose_record], manifest_path,
                run_id="r-preflight-0001", source_commit="0" * 40, configuration_name="primary",
                concept_id="cheese", pairing_id="google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
                model_revision="0" * 40, sae_revision="0" * 40, release="gemma-scope-2-12b-it-res-all",
                loader_sae_id="layer_29_width_16k_l0_big", scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
                measured_params_sha256="1" * 64,
                generation_kwargs=d._resolved_generation_kwargs(48, d.GENERATION_SETTINGS),
                chat_template_identity="gemma-it-v1", locales_complete=["en"], causal_order_position=1,
                skipped_for_gate_failure=[],
                dose_grid=one_alloc.load_causal_dose_grid(repo_root)[0 if direction == "amplify" else 1],
            )
            manifests[direction] = one_alloc.verify_generation_manifest(manifest_path)

        for direction, manifest in manifests.items():
            if not isinstance(manifest["direction"], str):
                raise AssertionError(f"{direction} manifest's own 'direction' field must be a SCALAR string, got {type(manifest['direction'])}")
            if manifest["direction"].lower() != direction:
                raise AssertionError(f"expected {direction} manifest's direction field to read {direction!r}, got {manifest['direction']!r}")
        amplify_path = tmp_root / "direction_proof" / "generation_manifest_amplify.json"
        suppress_path = tmp_root / "direction_proof" / "generation_manifest_suppress.json"
        if amplify_path == suppress_path:
            raise AssertionError("amplify and suppress must never resolve to the same manifest path")
        if d.compute_file_sha256(amplify_path) == d.compute_file_sha256(suppress_path):
            raise AssertionError("amplify and suppress manifests must never be byte-identical")
        return (
            f"amplify manifest direction={manifests['amplify']['direction']!r}, suppress manifest "
            f"direction={manifests['suppress']['direction']!r} -- two separate physical files, two separate scalars"
        )

    runner.case("separate_scalar_direction_manifests_amplify_and_suppress", case_separate_scalar_direction_manifests)

    # -----------------------------------------------------------------
    # 23. LA-B proof: wall_time_refusal_before_incomplete_concept -- the
    #     first concept the wall-time readiness gate refuses BREAKS the
    #     causal-order loop; every concept after it is recorded NOT_
    #     ATTEMPTED without ever calling generate_concept_complete for it
    #     (P0 STOP-LINE correction, "after the first concept cannot fit,
    #     BREAK; do not continue probing"), exercised end to end through
    #     the real scheduled run_generation_mode entry point.
    # -----------------------------------------------------------------
    def case_wall_time_refusal_before_incomplete_concept() -> str:
        backend = fakes.make_fake_gemma_backend()
        real_load_backend, real_max_new_tokens = d.load_backend, d.ONE_ALLOCATION_MAX_NEW_TOKENS
        real_readiness = one_alloc.assess_concept_generation_readiness
        real_generate_concept_complete = one_alloc.generate_concept_complete
        d.load_backend = lambda **_kwargs: backend
        d.ONE_ALLOCATION_MAX_NEW_TOKENS = 1

        call_count = {"n": 0}

        def fake_readiness(*, remaining_wall_time_seconds, seconds_per_generation):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return one_alloc.ConceptGenerationReadiness(attempt=True, detail="first concept fits")
            return one_alloc.ConceptGenerationReadiness(attempt=False, detail="does not fit -- preflight proof")

        generate_calls: list[str] = []

        def spy_generate_concept_complete(*args, **kwargs):
            generate_calls.append(kwargs.get("concept_id"))
            return real_generate_concept_complete(*args, **kwargs)

        one_alloc.assess_concept_generation_readiness = fake_readiness
        one_alloc.generate_concept_complete = spy_generate_concept_complete
        try:
            grid_dir = tmp_root / "wall_time_refusal_grid"
            d.write_grid_result(
                grid_dir, backend.pairing,
                [
                    d.ConceptPairingVerdict(concept_id="formal_register", pairing=backend.pairing, status="pass", surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None),
                    d.ConceptPairingVerdict(concept_id="cheese", pairing=backend.pairing, status="pass", surviving_feature_index=CONCEPT_FEATURE, candidates_evaluated=[], error=None),
                ],
            )
            args = one_alloc.parse_args([
                "--pairing", backend.pairing, "--model-path", "unused", "--sae-path", "unused", "--layer", "29",
                "--configuration-name", "primary", "--grid-path", str(grid_dir / "grid.json"),
                "--pairing-id", "google/gemma-3-12b-it+google/gemma-scope-2-12b-it",
                "--run-id", "r-preflight-0001", "--source-commit", resolve_source_commit(repo_root),
                "--job-deadline-epoch-seconds", str(time.time() + 100_000),
                "--out-dir", str(tmp_root / "wall_time_refusal_out"), "--state-dir", str(tmp_root / "wall_time_refusal_state"),
            ])
            result = one_alloc.run_generation_mode(args)
        finally:
            d.load_backend = real_load_backend
            d.ONE_ALLOCATION_MAX_NEW_TOKENS = real_max_new_tokens
            one_alloc.assess_concept_generation_readiness = real_readiness
            one_alloc.generate_concept_complete = real_generate_concept_complete

        if result["attempted_concepts"] != ["formal_register"]:
            raise AssertionError(f"expected only formal_register to be attempted, got {result['attempted_concepts']}")
        if [x["concept_id"] for x in result["not_attempted"]] != ["cheese"]:
            raise AssertionError(f"expected cheese to be recorded NOT_ATTEMPTED, got {result['not_attempted']}")
        if call_count["n"] != 2:
            raise AssertionError(f"expected readiness checked exactly once per concept (2 total), got {call_count['n']}")
        if generate_calls != ["formal_register"]:
            raise AssertionError(f"expected cheese's generation to never even start, got generate_calls={generate_calls}")
        if result["status"] != "partial_wall_time_cutoff":
            raise AssertionError(f"expected status='partial_wall_time_cutoff', got {result['status']!r}")
        return (
            f"attempted={result['attempted_concepts']} not_attempted={[x['concept_id'] for x in result['not_attempted']]} "
            f"readiness_checks={call_count['n']} generate_calls={generate_calls} status={result['status']!r}"
        )

    runner.case("wall_time_refusal_before_incomplete_concept", case_wall_time_refusal_before_incomplete_concept)

    executed_cases = len(runner.results)
    if executed_cases != EXPECTED_CASE_COUNT:
        raise AssertionError(
            f"EXPECTED_CASE_COUNT ({EXPECTED_CASE_COUNT}) disagrees with the actual number of case() calls "
            f"({executed_cases}) -- update the constant to match, never the other way around."
        )
    passed_cases = sum(1 for r in runner.results if r.status == "pass")
    failed_cases = [r.name for r in runner.results if r.status != "pass"]
    overall_passed = passed_cases == executed_cases == EXPECTED_CASE_COUNT

    def _case_passed(name: str) -> bool:
        return any(r.name == name and r.status == "pass" for r in runner.results)

    proofs = {
        "sweep_and_confirmation_seeds_disjoint": _case_passed("sweep_and_confirmation_seeds_disjoint"),
        "all_required_per_dose_per_purpose_files_exist": _case_passed("all_required_per_dose_per_purpose_files_exist"),
        "concept_complete_ordering": _case_passed("causal_generation_order_is_fixed_and_political_framing_last"),
        "wall_time_refusal_before_incomplete_concept": _case_passed("wall_time_refusal_before_incomplete_concept"),
        "confirmation_outputs_all_five_doses_generated_not_inspected": _case_passed("confirmation_outputs_all_five_doses_generated_not_inspected"),
        "measured_sae_hashes_match_identity_v13": _case_passed("measured_sae_hashes_match_identity_v13"),
        "separate_scalar_direction_manifests_amplify_and_suppress": _case_passed("separate_scalar_direction_manifests_amplify_and_suppress"),
    }
    assert set(proofs) == set(PROOF_KEYS)  # structural guarantee, never allowed to drift

    return {
        "schema_version": SCHEMA_VERSION,
        "source_commit": resolve_source_commit(repo_root),
        "expected_case_count": EXPECTED_CASE_COUNT,
        "executed_case_count": executed_cases,
        "passed_case_count": passed_cases,
        "failed_cases": failed_cases,
        "overall_passed": overall_passed,
        "proofs": proofs,
    }


class _FakeSignalModule:
    SIGTERM = 15
    SIGINT = 2

    def signal(self, sig, handler):
        return None

    def getsignal(self, sig):
        return None


def _git_head(repo_root: Path) -> str:
    import subprocess

    proc = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SetupFailure(f"could not resolve the current git HEAD: {proc.stderr}")
    return proc.stdout.strip()


def resolve_source_commit(repo_root: Path) -> str:
    """ARCHIVE EXECUTION MUST NOT REQUIRE `.git`, same precedence as
    `final_pairing_concept_discovery.load_frozen_prompt_artifact`: on
    Tamia (a `git archive` transfer, no `.git` at all), `transfer_
    manifest.json`'s own recorded `source_commit` is authoritative;
    on a Windows/dev checkout that still has `.git`, falls back to a
    live `git rev-parse HEAD`. Raises `SetupFailure` (never fabricates a
    commit) if neither is available, or if what was resolved is not a
    full 40-character hex commit (the LA-B contract's own requirement)."""
    import final_pairing_concept_discovery as d

    transfer_manifest = d.load_transfer_manifest(repo_root)
    if transfer_manifest is not None:
        commit = transfer_manifest["source_commit"]
    elif d._has_git_directory(repo_root):
        commit = _git_head(repo_root)
    else:
        raise SetupFailure(
            f"{repo_root} has neither {d.TRANSFER_MANIFEST_FILENAME} nor a .git directory -- cannot resolve "
            f"source_commit for the preflight report."
        )
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit.lower()):
        raise SetupFailure(f"resolved source_commit {commit!r} is not a full 40-character hex commit")
    return commit


def d_module_frozen_sha() -> str:
    import final_pairing_concept_discovery as d

    return d.FROZEN_PROMPT_SETS_SHA256


def d_module_frozen_commit() -> str:
    import final_pairing_concept_discovery as d

    return d.FROZEN_PROMPT_SET_COMMIT


#: `--sentinel-dir`'s own marker file -- a fixed, known-content file this
#: preflight creates (if absent) in a caller-nominated directory OUTSIDE
#: its own `tmp_root`, then re-hashes after every case has run. Proves
#: the entire scheduled call graph never writes into a sibling tree it
#: was not explicitly given as its own output directory.
SENTINEL_FILENAME = "sentinel.txt"
SENTINEL_CONTENT = "LA-B sibling-tree isolation sentinel -- must not be modified by discovery_preflight.py\n"


def _sentinel_snapshot(sentinel_dir: Path) -> dict[str, str]:
    if not sentinel_dir.is_dir():
        return {}
    return {
        str(p.relative_to(sentinel_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(sentinel_dir.rglob("*")) if p.is_file()
    }


def ensure_sentinel(sentinel_dir: Path) -> None:
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel_path = sentinel_dir / SENTINEL_FILENAME
    if not sentinel_path.is_file():
        sentinel_path.write_text(SENTINEL_CONTENT, encoding="utf-8")


class SiblingTreeContaminated(RuntimeError):
    """Raised when `--sentinel-dir`'s own snapshot differs before and
    after a preflight run -- proof of sibling-tree isolation failed for
    real, not merely by construction."""


def verify_sentinel_untouched(sentinel_dir: Path, before: dict[str, str]) -> None:
    after = _sentinel_snapshot(sentinel_dir)
    if after != before:
        raise SiblingTreeContaminated(
            f"sentinel directory {sentinel_dir} was modified during this preflight run -- "
            f"before={before} after={after}"
        )


def resolve_and_validate_repo_root(
    *, prompt_sets: str | Path, prompt_metadata: str | Path, backup_trigger: str | Path, pairing_config: str | Path,
) -> Path:
    """Derives the ONE TRUE `repo_root` from `--prompt-sets` (its frozen
    relative location, `prompts/final_pairing/v1/prompt_sets.jsonl`, is
    exactly 4 path components below the root) and asserts the other
    three explicit paths resolve under that SAME root at their own
    frozen relative locations -- failing closed rather than silently
    trusting `Path(__file__).resolve().parents[2]`, which would be wrong
    the moment this script runs from a directory layout that does not
    match this repository's own (e.g. a `git archive` extraction rooted
    somewhere else). Never fabricates a repo_root from any ONE of the
    four alone; all four must agree."""
    import final_pairing_concept_discovery as d

    prompt_sets_path = Path(prompt_sets).resolve()
    repo_root = prompt_sets_path.parents[3]
    expected = {
        "--prompt-sets": repo_root / d.FROZEN_PROMPT_SET_DIR / "prompt_sets.jsonl",
        "--prompt-metadata": repo_root / d.FROZEN_PROMPT_SET_DIR / "metadata.json",
        "--backup-trigger": repo_root / d.BACKUP_TRIGGER_PROTOCOL_PATH,
        "--pairing-config": repo_root / d.IDENTITY_PROTOCOL_PATH,
    }
    given = {
        "--prompt-sets": prompt_sets_path,
        "--prompt-metadata": Path(prompt_metadata).resolve(),
        "--backup-trigger": Path(backup_trigger).resolve(),
        "--pairing-config": Path(pairing_config).resolve(),
    }
    mismatched = {
        flag: (given[flag], expected[flag].resolve())
        for flag in expected if given[flag] != expected[flag].resolve()
    }
    if mismatched:
        details = "; ".join(f"{flag} given {g} but expected {e}" for flag, (g, e) in mismatched.items())
        raise SetupFailure(
            f"explicit preflight input path(s) do not resolve under one consistent repo root "
            f"(derived as {repo_root} from --prompt-sets): {details}"
        )
    return repo_root


def parse_args(argv: list[str] | None = None) -> Any:
    import argparse

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prompt-sets", required=True, help="path to prompts/final_pairing/v1/prompt_sets.jsonl")
    p.add_argument("--prompt-metadata", required=True, help="path to prompts/final_pairing/v1/metadata.json")
    p.add_argument("--backup-trigger", required=True, help="path to protocols/final_pairing/v1/backup_trigger.json")
    p.add_argument("--pairing-config", required=True, help="path to protocols/final_pairing/v1/scientific_config_identity.json")
    p.add_argument("--gemma-output-root", required=True, help="root this preflight proves job-id-rooted writes under, for the Gemma pairing")
    p.add_argument("--qwen-output-root", required=True, help="root this preflight proves job-id-rooted writes under, for the Qwen pairing")
    p.add_argument(
        "--sentinel-dir", required=True,
        help=(
            "a directory (created if absent) that must remain byte-identical across this entire preflight "
            "run -- proves the scheduled call graph never writes outside its own tmp_root, even into a "
            "sibling tree."
        ),
    )
    p.add_argument("--report", required=True, help="path this preflight ALWAYS writes its JSON report to, pass or fail")
    return p.parse_args(argv)


def _failure_report(exc: Exception, *, repo_root: Path | None) -> dict[str, Any]:
    """Built when an exception occurs OUTSIDE `run_all_cases`'s own per-
    case try/except (a bad explicit path, a hash mismatch in one of the
    four frozen artifacts, a sentinel-tampering detection) -- `main()`
    still writes `--report` with this shape rather than letting the
    process crash with no JSON output at all. Carries the SAME eight
    top-level fields and the SAME seven proof keys (all False) as a real
    run's report -- never a structurally different shape for the failure
    path."""
    import contextlib

    source_commit = "0" * 40
    if repo_root is not None:
        with contextlib.suppress(Exception):
            source_commit = resolve_source_commit(repo_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "expected_case_count": EXPECTED_CASE_COUNT,
        "executed_case_count": 0,
        "passed_case_count": 0,
        "failed_cases": [f"setup: {type(exc).__name__}: {exc}"],
        "overall_passed": False,
        "proofs": dict.fromkeys(PROOF_KEYS, False),
    }


def write_report(report_path: str | Path, report: dict[str, Any]) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root: Path | None = None
    try:
        repo_root = resolve_and_validate_repo_root(
            prompt_sets=args.prompt_sets, prompt_metadata=args.prompt_metadata,
            backup_trigger=args.backup_trigger, pairing_config=args.pairing_config,
        )
        sentinel_dir = Path(args.sentinel_dir)
        ensure_sentinel(sentinel_dir)
        sentinel_before = _sentinel_snapshot(sentinel_dir)

        with tempfile.TemporaryDirectory(prefix="discovery-preflight-") as tmp:
            report = run_all_cases(
                tmp_root=Path(tmp), repo_root=repo_root,
                gemma_output_root=Path(args.gemma_output_root), qwen_output_root=Path(args.qwen_output_root),
            )

        verify_sentinel_untouched(sentinel_dir, sentinel_before)
    except Exception as exc:  # `--report` must be written EVEN on a setup-level failure
        report = _failure_report(exc, repo_root=repo_root)

    write_report(args.report, report)
    print(json.dumps(report, indent=2))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
