"""Tests for scripts/final_pairing/final_concept_discovery_matched_configuration_job.py.

Reuses the same fake-process seam as
test_final_concept_discovery_dual_gpu_job.py -- no real subprocess is ever
spawned, no real model is ever loaded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_concept_discovery_dual_gpu_job as dual_gpu  # noqa: E402
import final_concept_discovery_matched_configuration_job as matched  # noqa: E402
import final_pairing_concept_discovery as discovery  # noqa: E402


class _FakeProcess:
    def __init__(self, pid: int, exit_code: int = 0):
        self._pid = pid
        self._exit_code = exit_code
        self._polled = False

    @property
    def pid(self) -> int:
        return self._pid

    def poll(self):
        self._polled = True
        return self._exit_code

    def wait(self, timeout=None):
        return self._exit_code

    def terminate(self):
        pass

    def send_signal(self, sig):
        pass


class _FakeSignalModule:
    SIGTERM = 15
    SIGINT = 2

    def signal(self, sig, handler):
        return None

    def getsignal(self, sig):
        return None


def _write_lane_json(tmp_path: Path, tag: str, *, exit_code: int = 0) -> Path:
    payload = {
        "out_dir": str(tmp_path / tag / "out"), "state_dir": str(tmp_path / tag / "state"),
        "tmp_dir": str(tmp_path / tag / "tmp"), "log_path": str(tmp_path / tag / "log.txt"),
        "argv": ["--pairing", "gemma-3-12b-it" if "gemma" in tag else "qwen-3.5-27b"],
    }
    path = tmp_path / f"{tag}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_orchestrator_factory(exit_codes: dict[str, int]):
    """Builds an orchestrator_factory that always succeeds/fails according
    to `exit_codes` (keyed by lane name), using the fake process/signal
    seam so no real subprocess is ever spawned."""

    def factory(lanes):
        def fake_launch(command, *, env, cwd, log_path):
            name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
            return _FakeProcess(pid=hash(name) % 10000, exit_code=exit_codes.get(name, 0))

        return dual_gpu.DualGpuOrchestrator(
            lanes, launch=fake_launch, sleep_fn=lambda _s: None, signal_module=_FakeSignalModule()
        )

    return factory


def _fake_run_preflight(repo_root):
    """Stands in for the real `discovery_preflight.py` subprocess -- these
    tests exercise `run_matched_configuration_job`'s SEQUENCING, not the
    preflight script itself (that has its own test suite)."""
    return {"overall": "pass", "executed_cases": 0, "expected_cases": 0, "cases": []}


def _fake_validate_prompt_artifact(repo_root):
    """Stands in for the real frozen-prompt-artifact git/hash check --
    these tests never touch a real repo checkout's artifact state."""
    return None


def _fake_wait_for_ready(ready_path, **kwargs):
    """Stands in for `final_pairing_concept_discovery.wait_for_ready_record`
    -- the fake launched processes never write a real ready.json, so the
    real waiter would hang/time out. Returns immediately, as if the lead
    lane's READY record had already arrived."""
    return None


_REAL_GATE_FAKES = {
    "run_preflight": _fake_run_preflight,
    "validate_prompt_artifact": _fake_validate_prompt_artifact,
    "wait_for_ready": _fake_wait_for_ready,
}


def _standard_paths(tmp_path: Path) -> dict:
    return {
        "primary_gemma": _write_lane_json(tmp_path, "primary_gemma"),
        "primary_qwen": _write_lane_json(tmp_path, "primary_qwen"),
        "backup_gemma": _write_lane_json(tmp_path, "backup_gemma"),
        "backup_qwen": _write_lane_json(tmp_path, "backup_qwen"),
    }


def _run(tmp_path: Path, *, run_backup: bool, exit_codes: dict[str, int] | None = None) -> dict:
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    factory = _make_orchestrator_factory(exit_codes or {})
    return matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"note": "test"},
        run_backup=run_backup, job_result_path=tmp_path / "job_result.json", orchestrator_factory=factory,
        **_REAL_GATE_FAKES,
    )


# ---------------------------------------------------------------------------
# No overwrite / distinct-identity invariants
# ---------------------------------------------------------------------------


def test_primary_and_backup_paths_must_never_collide(tmp_path):
    primary_gemma = _write_lane_json(tmp_path, "primary_gemma")
    primary_qwen = _write_lane_json(tmp_path, "primary_qwen")
    backup_qwen = _write_lane_json(tmp_path, "backup_qwen")
    # backup_gemma deliberately reuses primary_gemma's own JSON -> same out_dir/state_dir/etc.
    primary_lanes = [dual_gpu.load_lane_spec("gemma", primary_gemma), dual_gpu.load_lane_spec("qwen", primary_qwen)]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", primary_gemma), dual_gpu.load_lane_spec("qwen", backup_qwen)]
    with pytest.raises(matched.MatchedConfigurationError):
        matched.validate_primary_backup_paths_disjoint(primary_lanes, backup_lanes)


def test_colliding_paths_are_rejected_before_any_lane_launches(tmp_path):
    primary_gemma = _write_lane_json(tmp_path, "primary_gemma")
    primary_qwen = _write_lane_json(tmp_path, "primary_qwen")
    backup_qwen = _write_lane_json(tmp_path, "backup_qwen")
    primary_lanes = [dual_gpu.load_lane_spec("gemma", primary_gemma), dual_gpu.load_lane_spec("qwen", primary_qwen)]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", primary_gemma), dual_gpu.load_lane_spec("qwen", backup_qwen)]

    launched = []

    def factory(lanes):
        launched.append([lane.name for lane in lanes])
        raise AssertionError("must never be called when paths collide")

    with pytest.raises(matched.MatchedConfigurationError):
        matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
            run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        )
    assert launched == []


def test_every_lane_records_which_configuration_it_belongs_to(tmp_path):
    result = _run(tmp_path, run_backup=True)
    assert all(lane["configuration"] == "primary" for lane in result["primary_result"]["lanes"])
    assert all(lane["configuration"] == "backup" for lane in result["backup_result"]["lanes"])


def test_backup_result_json_file_is_written_and_never_reuses_primarys_path(tmp_path):
    result = _run(tmp_path, run_backup=True)
    primary_out_dirs = {lane["out_dir"] for lane in result["primary_result"]["lanes"]}
    backup_out_dirs = {lane["out_dir"] for lane in result["backup_result"]["lanes"]}
    assert primary_out_dirs.isdisjoint(backup_out_dirs)


# ---------------------------------------------------------------------------
# The real preflight/prompt-artifact-validation gate, and staggered launch
# (NEVER launch_all), apply to BOTH primary and backup -- not just to the
# standalone dual-GPU job. Mirrors test_final_concept_discovery_dual_gpu_
# job.py's own preflight/staggering proofs, one level up.
# ---------------------------------------------------------------------------


def test_a_failing_preflight_blocks_both_primary_and_backup_and_never_resolves_the_trigger(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]

    def failing_preflight(repo_root):
        raise dual_gpu.PreflightFailed("9 cases expected, 3 executed -- discovery_preflight.py did not report a clean pass")

    resolver_calls = {"n": 0}

    def resolver():
        resolver_calls["n"] += 1
        raise AssertionError("must never be called: primary never reached complete_pass, so its grid.json is untrustworthy")

    launched = []

    def factory(lanes):
        launched.append(lanes)
        raise AssertionError("must never be constructed: preflight failed before any launch")

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        trigger_resolver=resolver, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        run_preflight=failing_preflight, validate_prompt_artifact=_fake_validate_prompt_artifact,
    )
    assert launched == []
    assert resolver_calls["n"] == 0
    assert result["run_backup"] is False
    assert result["backup_result"] is None
    assert result["primary_result"]["status"] == "failure"
    assert result["primary_result"]["lanes"] == []
    assert result["status"] == "failure"


def test_both_primary_and_backup_launch_via_staggered_handshake_never_launch_all(tmp_path):
    """Qwen (the lead lane) must be launched, and reach READY, before Gemma
    (the follower) is launched -- for BOTH primary and backup. Proven with
    the REAL `write_ready_record`/`wait_for_ready_record` handshake (not a
    no-op fake), exactly like test_final_concept_discovery_dual_gpu_job.py
    proves it for the standalone job. `launch_all` would launch both lanes
    with no such ordering constraint at all."""
    import final_pairing_concept_discovery as discovery_module

    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]

    launch_order = []

    def make_launch():
        def fake_launch(command, *, env, cwd, log_path):
            name = "gemma" if env["CUDA_VISIBLE_DEVICES"] == "0" else "qwen"
            launch_order.append(name)
            if name == dual_gpu.STAGGER_LEAD_LANE:
                ready_index = command.index("--ready-path")
                ready_path = Path(command[ready_index + 1])
                discovery_module.write_ready_record(ready_path, pairing="qwen-3.5-27b", device="cuda:0")
            return _FakeProcess(pid=hash(name) % 10000, exit_code=0)

        return fake_launch

    def factory(lanes):
        return dual_gpu.DualGpuOrchestrator(
            lanes, launch=make_launch(), sleep_fn=lambda _s: None, signal_module=_FakeSignalModule()
        )

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        run_preflight=_fake_run_preflight, validate_prompt_artifact=_fake_validate_prompt_artifact,
    )
    assert result["status"] == "complete_pass"
    # Two configurations x (qwen then gemma) = exactly this order, never gemma-before-qwen.
    assert launch_order == ["qwen", "gemma", "qwen", "gemma"]


# ---------------------------------------------------------------------------
# The trigger boolean is never computed here -- only recorded.
# ---------------------------------------------------------------------------


def test_run_backup_false_never_launches_the_backup_orchestrator(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]

    backup_launched = {"called": False}

    def factory(lanes):
        if {lane.name for lane in lanes} == {"gemma", "qwen"} and lanes is backup_lanes:
            backup_launched["called"] = True
        return _make_orchestrator_factory({})(lanes)

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={"x": 1},
        run_backup=False, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        **_REAL_GATE_FAKES,
    )
    assert result["backup_result"] is None
    assert result["run_backup"] is False
    assert result["selected_configuration"] == discovery.PRIMARY_CONFIGURATION.name


def test_trigger_inputs_are_persisted_verbatim_not_reinterpreted(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    weird_inputs = {"arbitrary_field_name": 42, "nested": {"a": [1, 2, 3]}}
    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs=weird_inputs,
        run_backup=False, job_result_path=tmp_path / "result.json", orchestrator_factory=_make_orchestrator_factory({}),
        **_REAL_GATE_FAKES,
    )
    assert result["trigger_inputs"] == weird_inputs


def test_load_trigger_inputs_reads_json_verbatim(tmp_path):
    path = tmp_path / "trigger.json"
    payload = {"whatever_the_architect_calls_it": 3.14}
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert matched.load_trigger_inputs(path) == payload


# ---------------------------------------------------------------------------
# Aggregate status across primary/backup
# ---------------------------------------------------------------------------


def test_complete_pass_when_primary_passes_and_backup_not_run(tmp_path):
    result = _run(tmp_path, run_backup=False)
    assert result["status"] == "complete_pass"
    assert result["overall_exit_code"] == 0


def test_failure_when_primary_fails_even_if_backup_would_have_passed(tmp_path):
    result = _run(tmp_path, run_backup=False, exit_codes={"gemma": 1})
    assert result["status"] == "failure"
    assert result["overall_exit_code"] == 1


def test_failure_when_backup_fails_after_primary_passed(tmp_path):
    """Primary passing must never mask a backup failure -- the two are
    aggregated together, not overwritten sequentially."""
    result = _run(tmp_path, run_backup=True, exit_codes={"qwen": 1})
    # exit_codes applies to both primary and backup fake launches identically
    # in this simple factory, so both qwen lanes fail -- status must be failure.
    assert result["status"] == "failure"


def test_job_result_file_is_written_to_disk(tmp_path):
    _run(tmp_path, run_backup=True)
    written = json.loads((tmp_path / "job_result.json").read_text(encoding="utf-8"))
    assert written["selected_configuration"] == discovery.BACKUP_CONFIGURATION.name
    assert written["primary_configuration"]["gemma_layer"] == 29
    assert written["backup_configuration"]["gemma_layer"] == 24


# ---------------------------------------------------------------------------
# Never authors canonical evidence / bundles
# ---------------------------------------------------------------------------


def test_result_never_carries_scientific_payload_fields(tmp_path):
    result = _run(tmp_path, run_backup=True)
    forbidden = {"verdict", "calibration_candidates", "bundle", "specificity_results", "dose_response"}
    assert forbidden.isdisjoint(result.keys())
    for lane in result["primary_result"]["lanes"] + result["backup_result"]["lanes"]:
        assert forbidden.isdisjoint(lane.keys())


# ---------------------------------------------------------------------------
# Automatic backup-trigger computation from grid outputs (replaces
# --run-backup as a production CLI input; scheduled entry point never
# exposes it)
# ---------------------------------------------------------------------------


def _verdict(concept_id, pairing, status):
    return discovery.ConceptPairingVerdict(
        concept_id=concept_id, pairing=pairing, status=status,
        surviving_feature_index=(7 if status == "pass" else None), candidates_evaluated=[], error=None,
    )


def _write_grid(tmp_path, name, pairing, verdicts):
    out_dir = tmp_path / name
    return discovery.write_grid_result(out_dir, pairing, verdicts)


CONCEPT_IDS = [f"c{i}" for i in range(5)]
GEMMA = discovery.targets.GEMMA_3_12B_IT_TARGET.name
QWEN = discovery.targets.QWEN_3_5_27B_TARGET.name


def test_compute_trigger_from_grid_outputs_fires_when_shared_count_is_low(tmp_path):
    # Only 1 of 5 concepts shared -> below threshold 3 -> RUN_BACKUP.
    gemma_verdicts = [_verdict(c, GEMMA, "pass" if c == "c0" else "fail") for c in CONCEPT_IDS]
    qwen_verdicts = [_verdict(c, QWEN, "pass" if c == "c0" else "fail") for c in CONCEPT_IDS]
    gemma_path = _write_grid(tmp_path, "gemma", GEMMA, gemma_verdicts)
    qwen_path = _write_grid(tmp_path, "qwen", QWEN, qwen_verdicts)
    result = matched.compute_trigger_from_grid_outputs(
        gemma_grid_path=gemma_path, qwen_grid_path=qwen_path, concept_ids=CONCEPT_IDS,
    )
    assert result.primary_complete is True
    assert result.primary_shared_gabc_count == 1
    assert result.run_backup is True
    assert result.fail_run is False


def test_compute_trigger_from_grid_outputs_does_not_fire_when_shared_count_meets_threshold(tmp_path):
    # 3 of 5 concepts shared -> meets threshold 3 -> no backup.
    gemma_verdicts = [_verdict(c, GEMMA, "pass" if c in ("c0", "c1", "c2") else "fail") for c in CONCEPT_IDS]
    qwen_verdicts = [_verdict(c, QWEN, "pass" if c in ("c0", "c1", "c2") else "fail") for c in CONCEPT_IDS]
    gemma_path = _write_grid(tmp_path, "gemma", GEMMA, gemma_verdicts)
    qwen_path = _write_grid(tmp_path, "qwen", QWEN, qwen_verdicts)
    result = matched.compute_trigger_from_grid_outputs(
        gemma_grid_path=gemma_path, qwen_grid_path=qwen_path, concept_ids=CONCEPT_IDS,
    )
    assert result.primary_shared_gabc_count == 3
    assert result.run_backup is False


def test_compute_trigger_from_grid_outputs_fails_run_when_a_cell_is_an_error(tmp_path):
    gemma_verdicts = [_verdict(c, GEMMA, "error" if c == "c0" else "pass") for c in CONCEPT_IDS]
    qwen_verdicts = [_verdict(c, QWEN, "pass") for c in CONCEPT_IDS]
    gemma_path = _write_grid(tmp_path, "gemma", GEMMA, gemma_verdicts)
    qwen_path = _write_grid(tmp_path, "qwen", QWEN, qwen_verdicts)
    result = matched.compute_trigger_from_grid_outputs(
        gemma_grid_path=gemma_path, qwen_grid_path=qwen_path, concept_ids=CONCEPT_IDS,
    )
    assert result.primary_complete is False
    assert result.fail_run is True
    assert result.run_backup is False


def test_compute_trigger_from_grid_outputs_never_globs_a_parent_directory(tmp_path):
    """The two grid paths are read EXACTLY -- a sibling file placed next to
    one of them (mimicking a noncanonical preflight directory) must never
    be picked up."""
    gemma_verdicts = [_verdict(c, GEMMA, "pass") for c in CONCEPT_IDS]
    qwen_verdicts = [_verdict(c, QWEN, "pass") for c in CONCEPT_IDS]
    gemma_path = _write_grid(tmp_path, "gemma", GEMMA, gemma_verdicts)
    qwen_path = _write_grid(tmp_path, "qwen", QWEN, qwen_verdicts)
    # A noncanonical sibling that, if globbed, would corrupt the grid.
    (tmp_path / "gemma" / "run_20260813_la_c_grid.json").write_text("{\"schema_version\": 1, \"pairing\": \"bogus\", \"verdicts\": []}", encoding="utf-8")
    result = matched.compute_trigger_from_grid_outputs(
        gemma_grid_path=gemma_path, qwen_grid_path=qwen_path, concept_ids=CONCEPT_IDS,
    )
    assert result.primary_shared_gabc_count == len(CONCEPT_IDS)


def test_run_matched_configuration_job_uses_trigger_resolver_when_run_backup_is_none(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    calls = {"n": 0}

    def resolver():
        calls["n"] += 1
        return discovery.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=1)

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        trigger_resolver=resolver, job_result_path=tmp_path / "result.json",
        orchestrator_factory=_make_orchestrator_factory({}),
        **_REAL_GATE_FAKES,
    )
    assert calls["n"] == 1
    assert result["run_backup"] is True
    assert result["backup_result"] is not None
    assert result["trigger_result"]["primary_shared_gabc_count"] == 1


def test_run_matched_configuration_job_raises_before_backup_when_trigger_resolver_reports_fail_run(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    backup_launched = {"called": False}

    def factory(lanes):
        if lanes is backup_lanes:
            backup_launched["called"] = True
        return _make_orchestrator_factory({})(lanes)

    def failing_resolver():
        return discovery.evaluate_backup_trigger(primary_complete=False, primary_shared_gabc_count=None)

    with pytest.raises(matched.TriggerResolutionFailed):
        matched.run_matched_configuration_job(
            primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
            trigger_resolver=failing_resolver, job_result_path=tmp_path / "result.json",
            orchestrator_factory=factory,
            **_REAL_GATE_FAKES,
        )
    assert backup_launched["called"] is False


def test_main_cli_has_no_run_backup_flag():
    """The scheduled entry point must not expose a way to externally
    decide the backup trigger -- it is always computed from grid outputs."""
    with pytest.raises(SystemExit):
        matched.parse_args(["--run-backup", "true"])


# ---------------------------------------------------------------------------
# Backup execution readiness: the frozen 1.5x remaining-time rule and
# free-VRAM assertion. COMPLETE/PARTIAL/NOT_ATTEMPTED.
# ---------------------------------------------------------------------------


def test_assert_sufficient_time_for_backup_attempts_when_time_allows():
    readiness = matched.assert_sufficient_time_for_backup(
        job_start_time=0.0, job_time_limit_seconds=10_000.0, primary_elapsed_seconds=1000.0,
        now_fn=lambda: 1000.0,  # 1000s elapsed, 9000s remain; 1.5*1000=1500 <= 9000
    )
    assert readiness.attempt is True
    assert readiness.status == "ready"


def test_assert_sufficient_time_for_backup_refuses_when_time_is_short():
    readiness = matched.assert_sufficient_time_for_backup(
        job_start_time=0.0, job_time_limit_seconds=10_000.0, primary_elapsed_seconds=7000.0,
        now_fn=lambda: 9000.0,  # 9000s elapsed, 1000s remain; 1.5*7000=10500 > 1000
    )
    assert readiness.attempt is False
    assert readiness.status == "not_attempted_insufficient_time"


def test_assert_sufficient_free_vram_passes_when_every_gpu_clears_the_bar():
    calls = {"collect": 0, "empty_cache": 0}
    free = matched.assert_sufficient_free_vram(
        ["0", "1"], min_free_bytes=1_000_000,
        collect_garbage_fn=lambda: calls.__setitem__("collect", calls["collect"] + 1),
        empty_cache_fn=lambda: calls.__setitem__("empty_cache", calls["empty_cache"] + 1),
        free_vram_fn=lambda gid: 2_000_000,
    )
    assert free == {"0": 2_000_000, "1": 2_000_000}
    assert calls == {"collect": 1, "empty_cache": 1}


def test_assert_sufficient_free_vram_raises_when_a_gpu_falls_short():
    with pytest.raises(matched.InsufficientVramError, match="insufficient free VRAM"):
        matched.assert_sufficient_free_vram(
            ["0", "1"], min_free_bytes=1_000_000,
            collect_garbage_fn=lambda: None, empty_cache_fn=lambda: None,
            free_vram_fn=lambda gid: 500_000 if gid == "1" else 5_000_000,
        )


def test_check_backup_readiness_checks_time_before_vram():
    """An insufficient-time verdict must never even query VRAM."""
    vram_called = {"n": 0}

    def free_vram_fn(gid):
        vram_called["n"] += 1
        return 5_000_000

    readiness = matched.check_backup_readiness(
        job_start_time=0.0, job_time_limit_seconds=100.0, primary_elapsed_seconds=1000.0, now_fn=lambda: 99.0,
        gpu_ids=["0"], min_free_vram_bytes=1, collect_garbage_fn=lambda: None, empty_cache_fn=lambda: None,
        free_vram_fn=free_vram_fn,
    )
    assert readiness.attempt is False
    assert readiness.status == "not_attempted_insufficient_time"
    assert vram_called["n"] == 0


def test_run_matched_configuration_job_writes_not_attempted_when_readiness_refuses(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    backup_launched = {"called": False}

    def factory(lanes):
        if lanes is backup_lanes:
            backup_launched["called"] = True
        return _make_orchestrator_factory({})(lanes)

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        backup_readiness_checker=lambda: matched.BackupReadiness(attempt=False, status="not_attempted_insufficient_time", detail="not enough time"),
        **_REAL_GATE_FAKES,
    )
    assert backup_launched["called"] is False
    assert result["backup_execution_status"] == "NOT_ATTEMPTED"
    assert result["backup_result"] is None
    assert result["status"] == "partial_execution"
    assert result["selected_configuration"] == discovery.PRIMARY_CONFIGURATION.name


def test_run_matched_configuration_job_writes_complete_when_readiness_allows_and_backup_passes(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=_make_orchestrator_factory({}),
        backup_readiness_checker=lambda: matched.BackupReadiness(attempt=True, status="ready", detail="plenty of time"),
        **_REAL_GATE_FAKES,
    )
    assert result["backup_execution_status"] == "COMPLETE"
    assert result["backup_result"] is not None
    assert result["status"] == "complete_pass"


def test_run_matched_configuration_job_writes_partial_when_readiness_allows_but_backup_fails(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json",
        orchestrator_factory=_make_orchestrator_factory({"qwen": 1}),
        backup_readiness_checker=lambda: matched.BackupReadiness(attempt=True, status="ready", detail="plenty of time"),
        **_REAL_GATE_FAKES,
    )
    assert result["backup_execution_status"] == "PARTIAL"
    assert result["status"] == "failure"  # both primary and backup qwen fail in this fake factory


def test_backup_readiness_checker_defaults_to_none_and_never_gates_existing_callers(tmp_path):
    """No backup_readiness_checker supplied -> behavior is IDENTICAL to
    before this feature existed (backup_execution_status still reported,
    but never blocks)."""
    result = _run(tmp_path, run_backup=True)
    assert result["backup_execution_status"] == "COMPLETE"
    assert result["backup_readiness"] is None


# ---------------------------------------------------------------------------
# Primary-grid / primary-generation / backup lifecycle (P0 CONTINUE blocker
# 2): causal generation runs immediately after ITS OWN grid reaches
# complete_pass, strictly BEFORE the backup trigger is even computed --
# never racing, and never depending on, backup's own timing.
# ---------------------------------------------------------------------------


def _write_generation_lane_json(tmp_path: Path, tag: str) -> Path:
    payload = {
        "out_dir": str(tmp_path / tag / "out"), "state_dir": str(tmp_path / tag / "state"),
        "tmp_dir": str(tmp_path / tag / "tmp"), "log_path": str(tmp_path / tag / "log.txt"),
        "argv": ["--pairing", "gemma-3-12b-it" if "gemma" in tag else "qwen-3.5-27b"],
        "target_script": str(dual_gpu.GENERATION_SCRIPT),
    }
    path = tmp_path / f"{tag}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_primary_generation_lane_command_targets_the_generation_script(tmp_path):
    lane = dual_gpu.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "gen_gemma"))
    assert lane.target_script == dual_gpu.GENERATION_SCRIPT
    command = dual_gpu.build_lane_command(lane)
    assert str(dual_gpu.GENERATION_SCRIPT) in command
    assert str(dual_gpu.DISCOVERY_SCRIPT) not in command


def test_omitting_generation_lanes_skips_the_generation_phase_entirely(tmp_path):
    """The default (no `*_generation_lanes` argument) reproduces the exact
    prior grid-only behavior -- `primary_generation_result`/`backup_
    generation_result` are simply absent from consideration (None), never
    attempted."""
    result = _run(tmp_path, run_backup=True)
    assert result["primary_generation_result"] is None
    assert result["backup_generation_result"] is None


def test_primary_generation_runs_and_completes_before_the_backup_trigger_is_resolved(tmp_path):
    """Proves the ordering, not just that both eventually run: the
    trigger_resolver must observe primary generation as ALREADY DONE."""
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    primary_generation_lanes = [
        dual_gpu.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "primary_gen_gemma")),
        dual_gpu.load_lane_spec("qwen", _write_generation_lane_json(tmp_path, "primary_gen_qwen")),
    ]

    call_order: list[str] = []
    real_factory = _make_orchestrator_factory({})

    def factory(lanes):
        if lanes is primary_generation_lanes:
            call_order.append("primary_generation")
        elif lanes is primary_lanes:
            call_order.append("primary_grid")
        elif lanes is backup_lanes:
            call_order.append("backup_grid")
        return real_factory(lanes)

    def resolver():
        call_order.append("trigger_resolved")
        return discovery.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=1)

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        trigger_resolver=resolver, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        primary_generation_lanes=primary_generation_lanes,
        **_REAL_GATE_FAKES,
    )
    assert call_order.index("primary_grid") < call_order.index("primary_generation") < call_order.index("trigger_resolved")
    assert call_order.index("trigger_resolved") < call_order.index("backup_grid")
    assert result["primary_generation_result"]["status"] == "complete_pass"


def test_primary_generation_is_not_attempted_when_primary_grid_did_not_reach_complete_pass(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    primary_generation_lanes = [
        dual_gpu.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "primary_gen_gemma")),
        dual_gpu.load_lane_spec("qwen", _write_generation_lane_json(tmp_path, "primary_gen_qwen")),
    ]
    generation_launched = {"called": False}

    def factory(lanes):
        if lanes is primary_generation_lanes:
            generation_launched["called"] = True
        return _make_orchestrator_factory({"gemma": 1})(lanes)  # primary fails

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=False, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        primary_generation_lanes=primary_generation_lanes,
        **_REAL_GATE_FAKES,
    )
    assert generation_launched["called"] is False
    assert result["primary_generation_result"]["status"] == "not_attempted"


def test_backup_generation_only_runs_when_backup_grid_reaches_complete_pass(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    backup_generation_lanes = [
        dual_gpu.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "backup_gen_gemma")),
        dual_gpu.load_lane_spec("qwen", _write_generation_lane_json(tmp_path, "backup_gen_qwen")),
    ]
    generation_launched = {"called": False}

    def factory(lanes):
        if lanes is backup_generation_lanes:
            generation_launched["called"] = True
        if lanes is backup_lanes:
            return _make_orchestrator_factory({"qwen": 1})(lanes)  # backup grid fails
        return _make_orchestrator_factory({})(lanes)

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=factory,
        backup_generation_lanes=backup_generation_lanes,
        **_REAL_GATE_FAKES,
    )
    assert generation_launched["called"] is False
    assert result["backup_generation_result"]["status"] == "not_attempted"


def test_backup_generation_runs_when_backup_grid_passes(tmp_path):
    paths = _standard_paths(tmp_path)
    primary_lanes = [dual_gpu.load_lane_spec("gemma", paths["primary_gemma"]), dual_gpu.load_lane_spec("qwen", paths["primary_qwen"])]
    backup_lanes = [dual_gpu.load_lane_spec("gemma", paths["backup_gemma"]), dual_gpu.load_lane_spec("qwen", paths["backup_qwen"])]
    backup_generation_lanes = [
        dual_gpu.load_lane_spec("gemma", _write_generation_lane_json(tmp_path, "backup_gen_gemma")),
        dual_gpu.load_lane_spec("qwen", _write_generation_lane_json(tmp_path, "backup_gen_qwen")),
    ]

    result = matched.run_matched_configuration_job(
        primary_lanes=primary_lanes, backup_lanes=backup_lanes, trigger_inputs={},
        run_backup=True, job_result_path=tmp_path / "result.json", orchestrator_factory=_make_orchestrator_factory({}),
        backup_generation_lanes=backup_generation_lanes,
        **_REAL_GATE_FAKES,
    )
    assert result["backup_generation_result"]["status"] == "complete_pass"


def test_main_cli_generation_config_flags_require_both_gemma_and_qwen_together():
    with pytest.raises(matched.MatchedConfigurationError, match=r"BOTH.*or neither"):
        matched._load_generation_lanes("only-gemma.json", None)
