"""Tests for scripts/legacy/final_concept_discovery_matched_configuration_job.py.

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
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

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
        )
    assert backup_launched["called"] is False


def test_main_cli_has_no_run_backup_flag():
    """The scheduled entry point must not expose a way to externally
    decide the backup trigger -- it is always computed from grid outputs."""
    with pytest.raises(SystemExit):
        matched.parse_args(["--run-backup", "true"])
