"""Standalone, standard-library-only Tamia symlink-containment preflight.

Orchestrator review, 2026-08-17 ("Make the Tamia symlink preflight
self-contained and pytest-free"): Lab Assistant B correctly stopped before
submission because ~/sprint-venv (Tamia's real, shared scientific
environment) contains no pytest/pluggy/iniconfig, and installing them
there is forbidden -- an unnecessary shared-environment dependency for a
bounded, self-contained acceptance check. The prior preflight
(tests/test_final_pairing_symlink_preflight_nightly.py) invoked pytest;
this script replaces it as the scheduled Tamia gate. That pytest file
still exists, unchanged, as independent developer regression coverage --
it is simply no longer what final_pairing_gpu_job.py invokes.

Imports and calls the REAL production validators in final_pairing_
targets.py directly -- no predicate is copied or re-implemented here.
Uses only the Python standard library plus final_pairing_targets.py
itself (which is itself stdlib-only).

Builds its own disposable Hugging Face cache SKELETON (models--<org>--
<repo>/blobs/, snapshots/<revision>/) with real Linux symlinks, entirely
inside its own scratch directory -- resolved from, in order: --work-dir if
given, else the SLURM_TMPDIR environment variable if set (the normal case
inside a real Tamia allocation), else a fresh tempfile.mkdtemp(). NEVER
reads or writes any HF_HOME/HF_HUB_CACHE path or any real Hugging Face
cache -- there is no code path capable of touching the shared cache at
all, by construction, not merely by convention.

Runs exactly 11 real-symlink cases (see CASES below) against the real
validators, classifies each case outcome as passed / assertion_failure
(the validator did not behave as this case expected -- a real containment
defect) / unexpected_exception (something broke in the case's own setup
code, not the production code being tested), and writes one deterministic
JSON artifact. A distinct, separate setup-capability probe runs BEFORE any
of the 11 cases -- if real symlinks cannot be created at all in the
resolved scratch directory, the whole run is reported as a setup failure
with executed_count=0, never silently proceeding as if 11 cases had run.
Exits 0 if and only if all 11 cases were executed and all 11 passed;
nonzero for zero cases, a setup failure, any assertion failure, or any
unexpected exception. There is no "skip" outcome anywhere in this script
-- every case either runs for real and is judged, or the whole run is
reported as a setup failure; nothing can silently report success without
actually exercising real symlinks.

Always removes its own scratch tree before exiting, whether the run
passed, failed, or crashed (try/finally) -- but the JSON artifact itself
is written to a SIBLING of that scratch tree, never inside it, so cleanup
can never delete the report it is meant to produce.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import final_pairing_targets as targets  # noqa: E402

SCHEMA_VERSION = 1
EXPECTED_CASE_COUNT = 11
PREFLIGHT_NAME = "final_pairing_symlink_preflight"
_TARGET = targets.GEMMA_3_12B_IT_TARGET


# ---------------------------------------------------------------------------
# Small assertion helpers -- every case routes its validator calls through
# one of these two, so "the validator didn't behave as THIS case expected"
# always becomes an AssertionError (classified as assertion_failure by the
# runner below), never conflated with an unrelated bug in the case's own
# setup code (which propagates as some OTHER exception type, classified as
# unexpected_exception instead).
# ---------------------------------------------------------------------------


def _expect_raises(exc_type: type[BaseException], fn: Callable[[], object]) -> None:
    try:
        fn()
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(f"expected {exc_type.__name__}, got {type(e).__name__}: {e}") from e
    else:
        raise AssertionError(f"expected {exc_type.__name__} to be raised, but the call returned normally")


def _expect_passes(fn: Callable[[], object]) -> None:
    try:
        fn()
    except Exception as e:
        raise AssertionError(f"expected the call to pass without raising, but got {type(e).__name__}: {e}") from e


def _build_hf_cache_skeleton(root: Path) -> tuple[Path, Path, Path]:
    """A realistic huggingface_hub cache skeleton, built fresh inside this
    case's own disposable scratch directory:
        models--google--gemma-scope-2-12b-it/
          blobs/<blob-id>
          snapshots/<revision>/
    Returns (repo_root, snapshot_dir, blob_path)."""
    repo_root = root / "models--google--gemma-scope-2-12b-it"
    blob_path = repo_root / "blobs" / "deadbeefcafe0123"
    blob_path.parent.mkdir(parents=True)
    blob_path.write_bytes(b"fake sae weights")
    snapshot_dir = repo_root / "snapshots" / "abc123"
    snapshot_dir.mkdir(parents=True)
    return repo_root, snapshot_dir, blob_path


def _symlink(link_path: Path, target_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(target_path)


# ---------------------------------------------------------------------------
# The 11 required cases -- each calls the REAL production validators
# (final_pairing_targets.py), never a copy of their predicates.
# ---------------------------------------------------------------------------


def case_intended_symlink_passes_snapshot_guard(case_dir: Path) -> None:
    _repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, blob_path)
    _expect_passes(lambda: targets.validate_sae_files_match_snapshot([str(link)], snapshot_dir, _TARGET))


def case_intended_symlink_passes_exact_sae_family_guard(case_dir: Path) -> None:
    _repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, blob_path)
    captured: dict[str, object] = {}

    def _run() -> None:
        captured["provenance"] = targets.validate_sae_files_match_expected_subdirectory(
            [str(link)], snapshot_dir, _TARGET
        )

    _expect_passes(_run)
    provenance = captured["provenance"]
    if provenance["sae_subdirectory_membership_verified"] is not True:  # type: ignore[index]
        raise AssertionError(f"expected sae_subdirectory_membership_verified=True, got {provenance!r}")


def case_intended_symlink_passes_physical_cache_guard(case_dir: Path) -> None:
    _repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, blob_path)
    _expect_passes(
        lambda: targets.validate_sae_symlink_targets_stay_in_repository_cache([str(link)], snapshot_dir, _TARGET)
    )


def case_wrong_snapshot_revision_fails(case_dir: Path) -> None:
    repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    other_revision_dir = repo_root / "snapshots" / "deadbeef-a-different-revision"
    link = other_revision_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, blob_path)
    _expect_raises(
        targets.TargetIdentityMismatch,
        lambda: targets.validate_sae_files_match_snapshot([str(link)], snapshot_dir, _TARGET),
    )


def case_sibling_prefix_revision_fails(case_dir: Path) -> None:
    repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    evil_revision_dir = repo_root / "snapshots" / (snapshot_dir.name + "-evil")
    link = evil_revision_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, blob_path)
    _expect_raises(
        targets.TargetIdentityMismatch,
        lambda: targets.validate_sae_files_match_snapshot([str(link)], snapshot_dir, _TARGET),
    )


def _make_sibling_family_case(family: str) -> Callable[[Path], None]:
    """A sibling family lives genuinely INSIDE the correct snapshot (so
    validate_sae_files_match_snapshot alone cannot catch it) -- only the
    exact-subdirectory guard may reject it."""

    def _case(case_dir: Path) -> None:
        _repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
        link = snapshot_dir / family / "layer_31_width_16k_l0_medium" / "config.json"
        _symlink(link, blob_path)
        _expect_passes(lambda: targets.validate_sae_files_match_snapshot([str(link)], snapshot_dir, _TARGET))
        _expect_raises(
            targets.TargetIdentityMismatch,
            lambda: targets.validate_sae_files_match_expected_subdirectory([str(link)], snapshot_dir, _TARGET),
        )

    return _case


def case_escaping_symlink_fails_physical_containment(case_dir: Path) -> None:
    _repo_root, snapshot_dir, _blob_path = _build_hf_cache_skeleton(case_dir)
    outside_target = case_dir / "some_other_repo" / "blobs" / "deadbeefcafe0123"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_bytes(b"fake weights from a different repository")
    link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(link, outside_target)
    _expect_raises(
        targets.TargetIdentityMismatch,
        lambda: targets.validate_sae_symlink_targets_stay_in_repository_cache([str(link)], snapshot_dir, _TARGET),
    )


def case_regular_in_snapshot_file_passes(case_dir: Path) -> None:
    """A real, non-symlinked file (e.g. under HF_HUB_DISABLE_SYMLINKS_
    DOWNLOAD) must pass every guard -- symlink containment must never be a
    REQUIREMENT, only a check applied when a symlink is actually present."""
    _repo_root, snapshot_dir, _blob_path = _build_hf_cache_skeleton(case_dir)
    regular_file = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    regular_file.parent.mkdir(parents=True)
    regular_file.write_bytes(b"a real, non-symlinked file")
    _expect_passes(lambda: targets.validate_sae_files_match_snapshot([str(regular_file)], snapshot_dir, _TARGET))
    _expect_passes(
        lambda: targets.validate_sae_files_match_expected_subdirectory([str(regular_file)], snapshot_dir, _TARGET)
    )
    _expect_passes(
        lambda: targets.validate_sae_symlink_targets_stay_in_repository_cache(
            [str(regular_file)], snapshot_dir, _TARGET
        )
    )


def case_duplicate_captured_paths_are_independently_accepted_and_retained(case_dir: Path) -> None:
    """params.safetensors appearing twice in resolved_files must remain
    valid when correct, and a BAD duplicate path must be reported for
    EACH occurrence -- proving neither validator deduplicates
    resolved_files before checking it."""
    _repo_root, snapshot_dir, blob_path = _build_hf_cache_skeleton(case_dir)
    good_link = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "params.safetensors"
    _symlink(good_link, blob_path)
    good_resolved = [str(good_link), str(good_link)]
    _expect_passes(lambda: targets.validate_sae_files_match_snapshot(good_resolved, snapshot_dir, _TARGET))
    _expect_passes(
        lambda: targets.validate_sae_files_match_expected_subdirectory(good_resolved, snapshot_dir, _TARGET)
    )

    bad_link = snapshot_dir / "attn_out" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink(bad_link, blob_path)
    bad_resolved = [str(bad_link), str(bad_link)]
    try:
        targets.validate_sae_files_match_expected_subdirectory(bad_resolved, snapshot_dir, _TARGET)
    except targets.TargetIdentityMismatch as e:
        if str(e).count(repr(str(bad_link))) != 2:
            raise AssertionError(f"expected both duplicate occurrences reported, got message: {e}") from e
    else:
        raise AssertionError("expected TargetIdentityMismatch for the duplicated bad path, got none")


CASES: list[tuple[str, str, Callable[[Path], None]]] = [
    (
        "intended_symlink_passes_snapshot_guard",
        "validate_sae_files_match_snapshot must not raise",
        case_intended_symlink_passes_snapshot_guard,
    ),
    (
        "intended_symlink_passes_exact_sae_family_guard",
        "validate_sae_files_match_expected_subdirectory must not raise and must verify membership",
        case_intended_symlink_passes_exact_sae_family_guard,
    ),
    (
        "intended_symlink_passes_physical_cache_guard",
        "validate_sae_symlink_targets_stay_in_repository_cache must not raise",
        case_intended_symlink_passes_physical_cache_guard,
    ),
    (
        "wrong_snapshot_revision_fails",
        "validate_sae_files_match_snapshot must raise TargetIdentityMismatch",
        case_wrong_snapshot_revision_fails,
    ),
    (
        "sibling_prefix_revision_fails",
        "validate_sae_files_match_snapshot must raise TargetIdentityMismatch",
        case_sibling_prefix_revision_fails,
    ),
    (
        "attn_out_fails",
        "validate_sae_files_match_expected_subdirectory must raise TargetIdentityMismatch",
        _make_sibling_family_case("attn_out"),
    ),
    (
        "mlp_out_fails",
        "validate_sae_files_match_expected_subdirectory must raise TargetIdentityMismatch",
        _make_sibling_family_case("mlp_out"),
    ),
    (
        "transcoder_fails",
        "validate_sae_files_match_expected_subdirectory must raise TargetIdentityMismatch",
        _make_sibling_family_case("transcoder"),
    ),
    (
        "escaping_symlink_fails_physical_containment",
        "validate_sae_symlink_targets_stay_in_repository_cache must raise TargetIdentityMismatch",
        case_escaping_symlink_fails_physical_containment,
    ),
    (
        "regular_in_snapshot_file_passes",
        "all three validators must not raise for a non-symlinked file",
        case_regular_in_snapshot_file_passes,
    ),
    (
        "duplicate_captured_paths_are_independently_accepted_and_retained",
        "duplicate good paths pass; a duplicated bad path is reported for each occurrence",
        case_duplicate_captured_paths_are_independently_accepted_and_retained,
    ),
]

if len(CASES) != EXPECTED_CASE_COUNT:
    raise AssertionError(f"CASES has {len(CASES)} entries, expected exactly {EXPECTED_CASE_COUNT}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    name: str
    expected_outcome: str
    actual_outcome: str
    passed: bool


def _run_case(name: str, expected_outcome: str, fn: Callable[[Path], None], case_dir: Path) -> CaseResult:
    try:
        fn(case_dir)
    except AssertionError as e:
        return CaseResult(name=name, expected_outcome=expected_outcome, actual_outcome=f"assertion_failure: {e}", passed=False)
    except Exception as e:
        return CaseResult(
            name=name,
            expected_outcome=expected_outcome,
            actual_outcome=f"unexpected_exception: {type(e).__name__}: {e}",
            passed=False,
        )
    return CaseResult(name=name, expected_outcome=expected_outcome, actual_outcome="passed", passed=True)


def _probe_symlink_capability(scratch_root: Path) -> str | None:
    """Returns None if real symlinks can be created inside scratch_root,
    else a human-readable reason string. A dedicated, isolated probe run
    BEFORE any of the 11 named cases -- so a capability gap is reported as
    a setup_failure (executed_count=0), never folded into a case's own
    assertion_failure bucket, and never silently treated as success."""
    probe_dir = scratch_root / "_symlink_capability_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    target = probe_dir / "target.txt"
    target.write_bytes(b"probe")
    link = probe_dir / "link.txt"
    try:
        link.symlink_to(target)
    except OSError as e:
        return f"{type(e).__name__}: {e}"
    return None


def _resolve_base_dir(explicit_work_dir: str | None) -> Path:
    """Resolution order: --work-dir if given, else $SLURM_TMPDIR (the
    normal case inside a real Tamia allocation), else a fresh
    tempfile.mkdtemp(). Never derived from any HF_HOME/HF_HUB_CACHE
    variable -- there is no code path here capable of touching the shared
    Hugging Face cache."""
    if explicit_work_dir:
        return Path(explicit_work_dir)
    slurm_tmpdir = os.environ.get("SLURM_TMPDIR")
    if slurm_tmpdir:
        return Path(slurm_tmpdir)
    return Path(tempfile.mkdtemp(prefix="final_pairing_symlink_preflight_"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--work-dir", default=None,
        help="Job-local scratch root. Defaults to $SLURM_TMPDIR if set, else a fresh temp directory. "
        "Never the shared Hugging Face cache.",
    )
    p.add_argument(
        "--out", default=None,
        help="Output path for the JSON artifact. Defaults to <base>/symlink_preflight_result.json.",
    )
    p.add_argument("--source-commit", default=None, help="Recorded verbatim in the JSON artifact if supplied.")
    return p.parse_args(argv)


def run_preflight(base: Path, source_commit: str | None) -> dict:
    """Pure(ish) core: builds the scratch tree under base, runs the setup
    probe and (if it passes) all 11 cases, always cleans up its own
    scratch subtree, and returns the result dict -- does not write any
    file itself, so callers (main() below, or tests) can inspect the
    dict directly without touching disk."""
    scratch_root = base / "final_pairing_symlink_preflight_scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    try:
        capability_failure = _probe_symlink_capability(scratch_root)
        if capability_failure is not None:
            return {
                "preflight_name": PREFLIGHT_NAME,
                "schema_version": SCHEMA_VERSION,
                "source_commit": source_commit,
                "platform": platform.platform(),
                "case_count": EXPECTED_CASE_COUNT,
                "executed_count": 0,
                "passed_count": 0,
                "overall_passed": False,
                "setup_failure": capability_failure,
                "cases": [],
            }

        case_results = []
        for name, expected_outcome, fn in CASES:
            case_dir = scratch_root / name
            case_dir.mkdir(parents=True, exist_ok=True)
            case_results.append(_run_case(name, expected_outcome, fn, case_dir))
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    executed_count = len(case_results)
    passed_count = sum(1 for r in case_results if r.passed)
    return {
        "preflight_name": PREFLIGHT_NAME,
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "platform": platform.platform(),
        "case_count": EXPECTED_CASE_COUNT,
        "executed_count": executed_count,
        "passed_count": passed_count,
        "overall_passed": executed_count == EXPECTED_CASE_COUNT and passed_count == EXPECTED_CASE_COUNT,
        "setup_failure": None,
        "cases": [asdict(r) for r in case_results],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base = _resolve_base_dir(args.work_dir)
    base.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else base / "symlink_preflight_result.json"

    result = run_preflight(base, args.source_commit)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    status = "PASS" if result["overall_passed"] else "FAIL"
    print(
        f"{status}: {result['passed_count']}/{result['case_count']} cases passed "
        f"(executed {result['executed_count']}/{result['case_count']}). JSON: {out_path}"
    )
    if result["setup_failure"]:
        print(f"setup_failure: {result['setup_failure']}")
    for case in result["cases"]:
        if not case["passed"]:
            print(f"  FAILED {case['name']}: {case['actual_outcome']}")

    return 0 if result["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
