"""Tests for scripts/final_pairing/final_pairing_one_allocation_generation.py
(stages 1-3 of protocols/final_pairing/v1/one_allocation_dose_generation.json).

Manifest/file shape matches Engineer 3's real, enforcing
`dose_generation_problems`/`dose-check` (commit ac9ea40): ONE FILE per
(concept, pairing, direction, dose, purpose), holding every prompt x
repeat for that cell, with a `seeds` LIST and `n_prompts`/`n_repeats`
counts -- not one file per individual generation, which an earlier
version of this module built before that consumer command existed to
check against.

CPU-only, fake-backend -- same convention as
test_final_pairing_concept_discovery.py: no real Gemma/Qwen weights exist
on any machine in this investigation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_fakes as fakes  # noqa: E402
import final_pairing_one_allocation_generation as one  # noqa: E402

CONCEPT_FEATURE = 3


# ---------------------------------------------------------------------------
# Structural hard stop: no Lodestar/judge import is reachable from this
# module's source, at all -- a source-level scan, not a runtime behavior
# check, so a future added import cannot silently regress this guarantee.
# ---------------------------------------------------------------------------


def test_module_source_never_imports_lodestar_or_the_judge_module():
    """AST-level, not a raw substring scan: the module's own docstring
    NAMES `lodestar`/`final_pairing_causal_judge` to explain this hard
    stop, so a substring search would false-positive on the explanation
    itself. Walking every real `import`/`from ... import` statement (at
    module scope AND inside every function body) is what actually proves
    no judge call is reachable."""
    import ast

    source = (REPO_ROOT / "scripts" / "final_pairing" / "final_pairing_one_allocation_generation.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    forbidden = {"lodestar", "final_pairing_causal_judge"}
    hits = {m for m in imported_modules if any(m == f or m.startswith(f + ".") for f in forbidden)}
    assert not hits, f"forbidden import(s) reachable from this module: {hits}"


def test_validate_one_allocation_protocol_hash_passes_against_the_real_frozen_artifact():
    digest = one.validate_one_allocation_protocol_hash(REPO_ROOT)
    assert digest == one.ONE_ALLOCATION_PROTOCOL_SHA256


def test_validate_one_allocation_protocol_hash_refuses_a_tampered_copy(tmp_path):
    tampered_path = tmp_path / "protocols" / "final_pairing" / "v1" / "one_allocation_dose_generation.json"
    tampered_path.parent.mkdir(parents=True)
    tampered_path.write_text('{"protocol_version": "tampered"}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="altered or unpinned"):
        one.validate_one_allocation_protocol_hash(tmp_path)


# ---------------------------------------------------------------------------
# ADDITION_1: seed derivation and explicit disjointness verification.
# ---------------------------------------------------------------------------


def test_derive_seed_is_deterministic():
    kwargs = dict(namespace="sweep", concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                  dose=0, prompt_index=0, repeat_index=0)
    assert one.derive_seed(**kwargs) == one.derive_seed(**kwargs)


def test_derive_seed_differs_across_namespace_even_with_identical_other_fields():
    kwargs = dict(concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
                  dose=0, prompt_index=0, repeat_index=0)
    assert one.derive_seed(namespace="sweep", **kwargs) != one.derive_seed(namespace="confirmation", **kwargs)


def test_assert_seed_sets_disjoint_passes_on_disjoint_sets():
    one.assert_seed_sets_disjoint([1, 2, 3], [4, 5, 6])  # must not raise


def test_assert_seed_sets_disjoint_raises_on_an_explicit_collision():
    with pytest.raises(one.SeedCollisionError, match="intersect at seed"):
        one.assert_seed_sets_disjoint([1, 2, 3], [3, 4, 5])


# ---------------------------------------------------------------------------
# Dose grids: Amplify (5 distinct clamp values), Suppress (4 descending
# clamp fractions + ABLATE as the fifth point).
# ---------------------------------------------------------------------------


def test_build_amplify_dose_grid_accepts_five_distinct_values():
    grid = one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0))
    assert len(grid) == 5
    assert all(spec.kind == "clamp" for spec in grid)


def test_build_amplify_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 5 points"):
        one.build_amplify_dose_grid((0.5, 1.0))


def test_build_amplify_dose_grid_rejects_duplicate_values():
    with pytest.raises(ValueError, match="must be distinct"):
        one.build_amplify_dose_grid((0.5, 0.5, 1.0, 2.0, 4.0))


def test_build_suppress_dose_grid_appends_ablate_as_the_fifth_point():
    grid = one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5))
    assert len(grid) == 5
    assert [spec.kind for spec in grid] == ["clamp", "clamp", "clamp", "clamp", "ablate"]
    assert grid[-1].value_in_max_units is None


def test_build_suppress_dose_grid_rejects_non_descending_fractions():
    with pytest.raises(ValueError, match="strictly descending"):
        one.build_suppress_dose_grid((1.0, 2.0, 0.5, 0.25))


def test_build_suppress_dose_grid_rejects_wrong_count():
    with pytest.raises(ValueError, match="exactly 4 points"):
        one.build_suppress_dose_grid((1.0, 0.5))


def test_dose_spec_rejects_a_value_on_an_ablate_dose():
    with pytest.raises(ValueError, match="carries no value_in_max_units"):
        one.DoseSpec(kind="ablate", value_in_max_units=1.0)


def test_dose_spec_requires_a_value_on_a_clamp_dose():
    with pytest.raises(ValueError, match="requires value_in_max_units"):
        one.DoseSpec(kind="clamp")


# ---------------------------------------------------------------------------
# ADDITION_4: wall-time preflight -- NOT_ATTEMPTED, never a raise.
# ---------------------------------------------------------------------------


def test_generations_per_concept_is_750():
    assert one.GENERATIONS_PER_CONCEPT == 750  # 2 x 5 x (15 + 60)


def test_dose_files_per_concept_is_20():
    assert one.DOSE_FILES_PER_CONCEPT == 20  # 2 directions x 5 doses x 2 purposes


def test_readiness_attempts_when_remaining_time_covers_one_concept():
    result = one.assess_concept_generation_readiness(
        remaining_wall_time_seconds=one.GENERATIONS_PER_CONCEPT * 2.0, seconds_per_generation=2.0,
    )
    assert result.attempt is True


def test_readiness_refuses_when_remaining_time_cannot_cover_one_concept():
    result = one.assess_concept_generation_readiness(
        remaining_wall_time_seconds=10.0, seconds_per_generation=2.0,
    )
    assert result.attempt is False
    assert "NOT_ATTEMPTED" in result.detail


# ---------------------------------------------------------------------------
# generate_dose_file / generate_concept_complete: real file I/O, real
# per-file SHA-256, against the fake CPU backend (real run_intervention,
# real torch tensors -- no GPU, no real weights, same as the rest of this
# project's test suite).
# ---------------------------------------------------------------------------


def test_generate_dose_file_writes_exactly_one_file_covering_every_prompt_and_repeat(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["some background text about cheese and other foods"])
    dose = one.DoseSpec(kind="clamp", value_in_max_units=1.0)
    prompts = [f"prompt {i}" for i in range(3)]
    record = one.generate_dose_file(
        backend, [CONCEPT_FEATURE], dose=dose, dose_index=0, corpus_max=corpus_max, positions="all",
        prompts=prompts, purpose="sweep", n_repeats=2, base_seed_namespace="sweep", max_new_tokens=2,
        out_dir=tmp_path, concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
    )
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert record.path == str(written[0])
    assert record.sha256 == d.compute_file_sha256(written[0])
    assert record.n_prompts == 3
    assert record.n_repeats == 2
    assert len(record.seeds) == 6  # 3 prompts x 2 repeats
    assert len(set(record.seeds)) == 6  # all distinct
    assert str(record.dose) in Path(record.path).name


def _amplify_and_suppress_prompts():
    sweep = [f"amplify sweep prompt {i}" for i in range(one.SWEEP_PROMPTS_PER_DIRECTION)]
    confirmation = [f"amplify confirmation prompt {i}" for i in range(one.CONFIRMATION_PROMPTS_PER_DIRECTION)]
    suppress_sweep = [f"suppress sweep prompt {i}" for i in range(one.SWEEP_PROMPTS_PER_DIRECTION)]
    suppress_confirmation = [f"suppress confirmation prompt {i}" for i in range(one.CONFIRMATION_PROMPTS_PER_DIRECTION)]
    return sweep, confirmation, suppress_sweep, suppress_confirmation


def test_generate_concept_complete_produces_20_dose_files_with_disjoint_seeds(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    records = one.generate_concept_complete(
        backend, [CONCEPT_FEATURE], concept_id="cheese", pairing_id=backend.pairing,
        corpus_max=corpus_max, positions="all", out_dir=tmp_path,
        amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
        suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
        amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
        suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf,
        max_new_tokens=1,
    )
    assert len(records) == one.DOSE_FILES_PER_CONCEPT == 20
    assert len({r.path for r in records}) == 20  # one file per dose, never shared
    total_generations = sum(len(r.seeds) for r in records)
    assert total_generations == one.GENERATIONS_PER_CONCEPT == 750


def test_generate_concept_complete_resumes_without_recomputing_completed_cells(tmp_path):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    progress_path = tmp_path / "progress.jsonl"
    kwargs = dict(
        concept_id="cheese", pairing_id=backend.pairing, corpus_max=corpus_max, positions="all", out_dir=tmp_path,
        amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
        suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
        amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
        suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf, max_new_tokens=1,
    )
    first = one.generate_concept_complete(backend, [CONCEPT_FEATURE], progress=d.ProgressLog(progress_path), **kwargs)
    assert len(first) == 20

    calls = {"n": 0}
    original = one.generate_dose_file

    def spy(*args, **kwargs2):
        calls["n"] += 1
        return original(*args, **kwargs2)

    one.generate_dose_file = spy
    try:
        second = one.generate_concept_complete(
            backend, [CONCEPT_FEATURE], progress=d.ProgressLog(progress_path), **kwargs
        )
    finally:
        one.generate_dose_file = original
    assert calls["n"] == 0
    assert len(second) == 20


# ---------------------------------------------------------------------------
# Manifest write/verify (stage 2 tail + stage 3 transfer verification) and
# the post-selection sealed-label stamp.
# ---------------------------------------------------------------------------


def _tiny_records(tmp_path, *, direction="amplify"):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    records = []
    for dose_index in range(3):
        dose = one.DoseSpec(kind="clamp", value_in_max_units=float(dose_index + 1))
        records.append(one.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=dose, dose_index=dose_index, corpus_max=corpus_max, positions="all",
            prompts=[f"prompt {i}" for i in range(2)], purpose="confirmation", n_repeats=1,
            base_seed_namespace="confirmation", max_new_tokens=1, out_dir=tmp_path,
            concept_id="cheese", pairing_id=backend.pairing, direction=direction,
        ))
    return records


_MANIFEST_KWARGS = dict(
    run_id="r-test-0001", source_commit="0" * 40, configuration_name="primary",
    model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
    sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="4c419f1ba0be8b7754d4151d4f26c23b92a9029e",
    release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big",
    scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
    measured_params_sha256="6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e",
    concepts={"cheese": "COMPLETE"},
)


def test_write_and_verify_generation_manifest_round_trips(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    verified = one.verify_generation_manifest(manifest_path)
    assert len(verified["files"]) == 3
    assert verified["protocol_sha256"] == one.ONE_ALLOCATION_PROTOCOL_SHA256
    assert verified["configuration"] == "primary"
    assert verified["sae"]["scientific_sae_id"] == "resid_post_all/layer_29_width_16k_l0_big"
    assert verified["concepts"] == {"cheese": "COMPLETE"}


def test_write_generation_manifest_rejects_an_unknown_configuration_name(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "configuration_name": "tertiary"}
    with pytest.raises(ValueError, match=r"primary.*backup"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_write_generation_manifest_rejects_an_unknown_completeness_value(tmp_path):
    records = _tiny_records(tmp_path)
    kwargs = {**_MANIFEST_KWARGS, "concepts": {"cheese": "MOSTLY_DONE"}}
    with pytest.raises(ValueError, match="COMPLETE"):
        one.write_generation_manifest(records, tmp_path / "m.json", **kwargs)


def test_verify_generation_manifest_raises_on_a_tampered_file(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    Path(records[0].path).write_text('{"generations": "TAMPERED"}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="sha256 mismatch"):
        one.verify_generation_manifest(manifest_path)


def test_verify_generation_manifest_raises_on_a_missing_file(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    Path(records[0].path).unlink()
    with pytest.raises(one.TransferVerificationFailed, match="file missing"):
        one.verify_generation_manifest(manifest_path)


def test_verify_generation_manifest_raises_on_a_tampered_manifest_itself(tmp_path):
    records = _tiny_records(tmp_path)
    manifest_path = tmp_path / "generation_manifest.json"
    full = one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    full["files"].append({"path": "injected", "sha256": "0" * 64})
    manifest_path.write_text(one._canonical_manifest_json(full), encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match=r"manifest .* itself is corrupted"):
        one.verify_generation_manifest(manifest_path)


def test_verify_generation_manifest_raises_when_manifest_sha256_field_is_absent(tmp_path):
    manifest_path = tmp_path / "generation_manifest.json"
    manifest_path.write_text('{"files": []}', encoding="utf-8")
    with pytest.raises(one.TransferVerificationFailed, match="carries no manifest_sha256"):
        one.verify_generation_manifest(manifest_path)


def test_stamp_manifest_with_selection_labels_only_unselected_confirmation_doses(tmp_path):
    records = _tiny_records(tmp_path)  # doses 0, 1, 2, all confirmation
    manifest_path = tmp_path / "generation_manifest.json"
    manifest = one.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    selections = [{
        "concept_id": "cheese", "pairing_id": records[0].pairing_id, "direction": "amplify",
        "status": "SELECTED", "selected": {"low": 0, "medium": 1, "high": 1}, "unselected": [2],
    }]
    stamped = one.stamp_manifest_with_selection(manifest, selections)
    by_dose = {entry["dose"]: entry for entry in stamped["files"]}
    assert by_dose[2]["label"] == one.SEALED_LABEL
    assert by_dose[0].get("label") is None
    assert by_dose[1].get("label") is None
    # the original, transfer-verified manifest is untouched
    assert all(entry.get("label") is None for entry in manifest["files"])


# ---------------------------------------------------------------------------
# Real dose-check proof: Engineer 3's actual `dose-check` command (commit
# ac9ea40), run against a real generation manifest + selection record this
# module produced -- only if a checked-out eng3/concept-bundle worktree is
# present on this machine (skipped, not failed, otherwise). A REAL, captured
# passing result is committed as tests/fixtures/eng3_concept_bundle/
# dose_check_sample_manifest_ac9ea40.json + dose_check_sample_selection_
# record_ac9ea40.json -- see the closing report.
# ---------------------------------------------------------------------------

ENG3_WORKTREE = Path("D:/devcache/wt/concept-bundle")


def _eng3_worktree_clean() -> bool:
    """The eng3 worktree is a SHARED working directory another party
    commits to directly and sometimes edits in place, uncommitted, mid-
    refactor -- a dirty worktree is a snapshot of in-progress work, not a
    ratified consumer, so this test skips rather than gating on it."""
    if not ENG3_WORKTREE.is_dir():
        return False
    import subprocess

    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ENG3_WORKTREE, capture_output=True, text=True,
    )
    return result.returncode == 0 and not result.stdout.strip()


@pytest.mark.skipif(
    not _eng3_worktree_clean(),
    reason=f"no CLEAN eng3/concept-bundle worktree at {ENG3_WORKTREE} (missing, or has uncommitted in-progress edits)",
)
def test_real_generation_manifest_and_selection_record_pass_live_dose_check(tmp_path):
    import subprocess

    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    amplify_sweep, amplify_conf, suppress_sweep, suppress_conf = _amplify_and_suppress_prompts()
    records = one.generate_concept_complete(
        backend, [CONCEPT_FEATURE], concept_id="cheese", pairing_id=backend.pairing,
        corpus_max=corpus_max, positions="all", out_dir=tmp_path / "generations",
        amplify_dose_grid=one.build_amplify_dose_grid((0.25, 0.5, 1.0, 2.0, 4.0)),
        suppress_dose_grid=one.build_suppress_dose_grid((4.0, 2.0, 1.0, 0.5)),
        amplify_sweep_prompts=amplify_sweep, amplify_confirmation_prompts=amplify_conf,
        suppress_sweep_prompts=suppress_sweep, suppress_confirmation_prompts=suppress_conf, max_new_tokens=1,
    )
    amplify_records = [r for r in records if r.direction == "amplify"]
    manifest_path = tmp_path / "generation_manifest_amplify.json"
    manifest = one.write_generation_manifest(amplify_records, manifest_path, **_MANIFEST_KWARGS)

    import json as _json

    selections = [{
        "concept_id": "cheese", "pairing_id": backend.pairing, "direction": "amplify",
        "status": "SELECTED", "selected": {"low": 1, "medium": 2, "high": 4}, "unselected": [0, 3],
    }]
    stamped = one.stamp_manifest_with_selection(manifest, selections)
    stamped_path = tmp_path / "generation_manifest_amplify_stamped.json"
    stamped_path.write_text(_json.dumps(stamped, indent=2, sort_keys=True), encoding="utf-8")

    selection_body = {
        "protocol_version": one.ONE_ALLOCATION_PROTOCOL_VERSION,
        "protocol_sha256": one.ONE_ALLOCATION_PROTOCOL_SHA256, "selections": selections,
    }
    selection_path = tmp_path / "selection_record.json"
    selection_path.write_text(_json.dumps(selection_body, indent=2, sort_keys=True), encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "selection_record.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "select"], cwd=tmp_path, check=True)
    selection_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    (tmp_path / "confirmation.txt").write_text("judged", encoding="utf-8")
    subprocess.run(["git", "add", "confirmation.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "judge confirmation"], cwd=tmp_path, check=True)
    confirmation_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    selection_body["selection_commit"] = selection_commit
    selection_body["confirmation_judging_commit"] = confirmation_commit
    selection_path.write_text(_json.dumps(selection_body, indent=2, sort_keys=True), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(ENG3_WORKTREE / "scripts" / "concept_bundle_publish.py"), "dose-check",
         "--manifest", str(stamped_path), "--selection-record", str(selection_path), "--git-root", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK:" in proc.stdout
