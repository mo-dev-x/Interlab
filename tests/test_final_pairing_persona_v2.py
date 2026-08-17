"""CPU-only tests for the v2 PERSONA corpus wiring in
scripts/final_pairing/final_pairing_concept_discovery.py.

Every test here is paired: for each guard there is a test that it ACCEPTS
the frozen corpus and a test that it REFUSES a deliberately broken one. A
guard demonstrated only on the good input is indistinguishable from a guard
that never looks, which is this sprint's recurring defect.

No GPU and no real weights are involved. The gate plumbing is exercised on
the same deterministic surrogate backend the preflight uses; nothing here
establishes anything about Gemma-3-12B-it or Qwen3.5-27B.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import persona_v2_preflight as pf  # noqa: E402


@pytest.fixture(scope="module")
def artifact():
    return d.load_frozen_persona_artifact(REPO_ROOT)


def _tarball_style_repo(tmp_path: Path, *, mutate_rows=None) -> Path:
    """A repo-shaped directory with NO .git -- the cluster's own situation
    after a `git archive` extract, where `git show` exits 128."""
    root = tmp_path / "extract"
    v2 = root / d.PERSONA_V2_PROMPT_SET_DIR
    v2.mkdir(parents=True)
    src = REPO_ROOT / d.PERSONA_V2_PROMPT_SET_DIR
    if mutate_rows is None:
        (v2 / "prompt_sets.jsonl").write_bytes((src / "prompt_sets.jsonl").read_bytes())
    else:
        rows = [json.loads(line) for line in (src / "prompt_sets.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        rows = mutate_rows(rows)
        (v2 / "prompt_sets.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8"
        )
    (v2 / "metadata.json").write_bytes((src / "metadata.json").read_bytes())
    v1 = root / d.FROZEN_PROMPT_SET_DIR
    v1.mkdir(parents=True)
    (v1 / "metadata.json").write_bytes((REPO_ROOT / d.FROZEN_PROMPT_SET_DIR / "metadata.json").read_bytes())
    assert not (root / ".git").exists()
    return root


def _v2_metadata() -> dict:
    return json.loads((REPO_ROOT / d.PERSONA_V2_PROMPT_SET_DIR / "metadata.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The frozen bytes
# ---------------------------------------------------------------------------


def test_the_loaded_bytes_hash_to_the_attested_digest(artifact):
    assert artifact.prompt_sets_sha256 == d.PERSONA_V2_PROMPT_SETS_SHA256
    assert artifact.prompt_sets_sha256.startswith("9c2975e9")
    assert artifact.commit == d.PERSONA_V2_FREEZE_COMMIT
    assert len(artifact.rows) == d.PERSONA_V2_ROW_COUNT


def test_git_is_preferred_when_a_checkout_is_present(artifact):
    assert artifact.metadata["persona_v2_bytes_origin"].startswith(
        f"prompt_sets.jsonl <- git {d.PERSONA_V2_FREEZE_COMMIT}"
    )


def test_the_no_git_fallback_actually_loads_the_corpus(tmp_path):
    """The fallback must WORK, not merely refuse: the cluster runs from a
    tarball extract with no .git, and a loader that only ever succeeds via
    git dies there (this has already happened once on this project)."""
    root = _tarball_style_repo(tmp_path)
    loaded = d.load_frozen_persona_artifact(root)
    assert len(loaded.rows) == d.PERSONA_V2_ROW_COUNT
    assert loaded.prompt_sets_sha256 == d.PERSONA_V2_PROMPT_SETS_SHA256
    assert "no .git" in loaded.metadata["persona_v2_bytes_origin"]


def test_the_no_git_fallback_is_digest_checked(tmp_path):
    """...and is not a hole: the same path refuses altered bytes."""
    def mutate(rows):
        rows[0]["text"] += "."
        return rows

    root = _tarball_style_repo(tmp_path, mutate_rows=mutate)
    with pytest.raises(d.PersonaCorpusError, match="refusing to run discovery against unpinned"):
        d.load_frozen_persona_artifact(root)


def test_git_and_a_divergent_working_tree_are_a_hard_failure(tmp_path, monkeypatch):
    """When both paths are available they must agree -- the committed
    validator subprocess and every human reader read the working-tree copy,
    so scoring one copy while a reader inspects another is refused."""
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd

        class _Result:
            stdout = b'{"concept_id": "not-the-frozen-corpus"}\n'

        return _Result()

    monkeypatch.setattr(d, "_has_git_directory", lambda _root: True)
    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(d.PersonaCorpusError, match="differ"):
        d.load_frozen_persona_artifact(REPO_ROOT)
    assert calls["cmd"][:2] == ["git", "show"]


# ---------------------------------------------------------------------------
# Shape: the 6-cell scheme
# ---------------------------------------------------------------------------


def test_six_cells_per_concept_with_the_expected_row_counts(artifact):
    plan = d.persona_v2_cell_plan(artifact)
    assert sorted(plan) == sorted(d.PERSONA_V2_CONCEPT_IDS)
    for entry in plan.values():
        assert entry["n_cells"] == 6
        assert sorted((c["locale"], c["family"]) for c in entry["cells"]) == [
            ("en", "f1"), ("en", "f2"), ("en", "f3"), ("fr", "f1"), ("fr", "f2"), ("fr", "f3"),
        ]
        for cell in entry["cells"]:
            assert (cell["n_positive"], cell["n_near_miss"], cell["n_unrelated"]) == (10, 15, 15)
            assert cell["n_gate_a_negatives"] == 30
            assert cell["n_gate_c_negatives"] == 15


def test_the_cell_scheme_is_the_same_one_the_existing_14_use(artifact):
    """Measured side by side on one backend, not asserted from a constant."""
    v1 = d.load_frozen_prompt_artifact(REPO_ROOT, allow_pi_gated=True)
    v1_concept = sorted({r["concept_id"] for r in v1.rows})[0]
    backend, _model = pf._surrogate_backend()

    v1_scan = d.score_full_feature_space(backend, v1, concept_id=v1_concept)
    for concept_id in d.PERSONA_V2_CONCEPT_IDS:
        scan = d.score_full_feature_space(backend, artifact, concept_id=concept_id)
        assert scan.cells_scored == v1_scan.cells_scored == 6
        assert scan.families_by_locale == v1_scan.families_by_locale
        assert scan.locales == v1_scan.locales


def test_a_dropped_family_is_refused():
    rows = [
        r for r in d.load_frozen_persona_artifact(REPO_ROOT).rows
        if not (r["concept_id"] == "pro_american_exceptionalism" and r["locale"] == "en"
                and r["split"] == "positive" and r.get("family") == "f2")
    ]
    with pytest.raises(d.PersonaCorpusError, match="rows, expected 400"):
        d.build_persona_artifact(
            rows, _v2_metadata(), repo_root=REPO_ROOT,
            prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="test",
        )


def test_a_relabelled_family_is_refused_even_though_the_row_count_is_unchanged():
    """The fault the row-count guard cannot see -- and therefore the one
    that proves the family/cell-scheme guard is alive."""
    rows = copy.deepcopy(d.load_frozen_persona_artifact(REPO_ROOT).rows)
    for row in rows:
        if (row["concept_id"] == "pro_american_exceptionalism" and row["locale"] == "en"
                and row["split"] == "positive" and row.get("family") == "f2"):
            row["family"] = "f1"
    assert len(rows) == d.PERSONA_V2_ROW_COUNT
    with pytest.raises(d.PersonaCorpusError, match="cell scheme is not optional"):
        d.build_persona_artifact(
            rows, _v2_metadata(), repo_root=REPO_ROOT,
            prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="test",
        )


# ---------------------------------------------------------------------------
# near_miss: the mirror, not the self
# ---------------------------------------------------------------------------


def test_near_miss_is_byte_identical_to_the_mirrors_positives(artifact):
    report = artifact.metadata["persona_v2_near_miss_mirror_check"]
    total = matched = 0
    for concept in report.values():
        for per_locale in concept.values():
            total += per_locale["n_near_miss"]
            matched += per_locale["byte_identical_to_mirror_positives"]
            assert per_locale["overlap_with_own_positives"] == 0
    assert (matched, total) == (60, 60)


def test_v1_near_miss_semantics_are_refused(artifact):
    """If near_miss_of is read with v1's meaning, each concept's near_miss
    set becomes its own positives; near_miss_auroc goes to chance and, via
    the equal-sized pooling identity, no cell can reach G-A's 0.90. That
    produces a zero-survivor grid indistinguishable from a real negative
    result, so it is refused at load time."""
    rows = pf._rows_with_v1_near_miss_semantics(artifact.rows)
    with pytest.raises(d.PersonaCorpusError, match="near_miss_of names the MIRROR concept"):
        d.build_persona_artifact(
            rows, _v2_metadata(), repo_root=REPO_ROOT,
            prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="test",
        )


def test_metadata_and_rows_must_agree_about_near_miss_semantics(artifact):
    metadata = _v2_metadata()
    metadata["near_miss_of_semantics"] = {"value": "own_concept"}
    with pytest.raises(d.PersonaCorpusError, match="near_miss_of_semantics"):
        d.build_persona_artifact(
            artifact.rows, metadata, repo_root=REPO_ROOT,
            prompt_sets_sha256="n/a", metadata_sha256="n/a", origin="test",
        )


# ---------------------------------------------------------------------------
# The gates
# ---------------------------------------------------------------------------


def test_the_three_gates_are_the_frozen_values(artifact):
    thresholds = artifact.metadata["thresholds"]
    assert thresholds["G_A_separation_auroc_min"] == 0.90
    assert thresholds["G_B_fire_rate_min"] == 0.70
    assert thresholds["G_B_activation_floor_fraction_of_observed_max"] == 0.20
    assert thresholds["G_C_specificity_auroc_vs_near_miss_min"] == 0.75


def test_the_corpus_authors_refusal_to_set_thresholds_is_preserved_verbatim(artifact):
    """The v2 corpus deliberately sets NO thresholds. That statement is kept
    in the record rather than overwritten, so a reader can see that the gate
    block came from somewhere else."""
    declared = artifact.metadata["thresholds_declared_by_corpus_author"]
    assert "NOT SET BY THE CORPUS AUTHOR" in declared["status"]


def test_the_inheritance_records_ruling_13_as_its_authority(artifact):
    """The referral is ANSWERED (architect RULING_13 REFERRAL A). The record
    must name the authority so the next reader does not re-open it, and must
    carry the null-result asymmetry the same ruling made binding."""
    provenance = artifact.metadata["thresholds_provenance"]
    assert "RULING_13 REFERRAL A" in provenance
    assert "SETTLED" in provenance
    assert "A v2 NULL IS NOT AN ABSENCE" in provenance
    assert d.PERSONA_V2_NULL_RESULT_REQUIRED_WORDING in provenance
    assert "does not establish that no such feature exists" in d.PERSONA_V2_NULL_RESULT_REQUIRED_WORDING


def test_a_moved_threshold_is_refused_against_v1s_pinned_metadata(monkeypatch):
    monkeypatch.setitem(d.PERSONA_V2_GATE_THRESHOLDS, "G_A_separation_auroc_min", 0.85)
    with pytest.raises(d.PersonaCorpusError, match="architect's ruling"):
        d.load_frozen_persona_artifact(REPO_ROOT)


def test_the_threshold_cross_check_fails_closed_when_v1_metadata_is_absent(tmp_path):
    """An unavailable cross-check must not read as a passed one."""
    root = _tarball_style_repo(tmp_path)
    (root / d.FROZEN_PROMPT_SET_DIR / "metadata.json").unlink()
    with pytest.raises(d.PersonaCorpusError, match="only sha256-pinned source"):
        d.load_frozen_persona_artifact(root)


def test_gate_c_subsumption_is_re_derived_and_holds_for_the_persona_splits(artifact):
    for concept_id in d.PERSONA_V2_CONCEPT_IDS:
        note = d.gate_c_subsumption_note(artifact, concept_id=concept_id)
        assert note["holds"] is True
        for per_locale in note["per_locale"].values():
            assert per_locale["n_near_miss"] == per_locale["n_unrelated"] == 15


# ---------------------------------------------------------------------------
# The plumbing
# ---------------------------------------------------------------------------


def test_every_candidate_is_measured_in_all_six_cells(artifact):
    backend, _model = pf._surrogate_backend()
    for concept_id in d.PERSONA_V2_CONCEPT_IDS:
        verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id=concept_id, report_top_n=2)
        assert verdict.status != "error", verdict.error
        assert verdict.candidates_evaluated
        for candidate in verdict.candidates_evaluated:
            ab = {(r["locale"], r["family"]) for r in candidate["gate_a_b_results"]}
            gc = {(r["locale"], r["family"]) for r in candidate["gate_c_results"]}
            assert ab == gc == {
                (locale, family) for locale in d.FROZEN_PROMPT_SET_LOCALES for family in d.PERSONA_V2_FAMILIES
            }
            assert {r["n_positives"] for r in candidate["gate_a_b_results"]} == {10}


def test_gate_a_negatives_really_are_unrelated_pooled_with_near_miss(artifact):
    """Measured through the identity rather than trusted from a row count:
    with equal-sized sets, separation_auroc == (near_miss + unrelated)/2
    holds only if that is genuinely the pooled denominator."""
    backend, _model = pf._surrogate_backend()
    cache = d.FeatureMatrixCache()
    worst = 0.0
    for concept_id in d.PERSONA_V2_CONCEPT_IDS:
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            unrelated, near_miss, positives = d.concept_locale_texts(
                artifact, concept_id=concept_id, locale=locale
            )
            for feature_index in (0, 1, 2):
                results = d.compute_gate_a_and_b_per_family(
                    backend, artifact, concept_id=concept_id, locale=locale,
                    feature_index=feature_index, cache=cache,
                )
                for result in results:
                    pos = cache.feature_scores(backend, positives[result.family], feature_index)
                    a_near = d._auroc_from_scores(pos, cache.feature_scores(backend, near_miss, feature_index))
                    a_unrel = d._auroc_from_scores(pos, cache.feature_scores(backend, unrelated, feature_index))
                    worst = max(worst, abs(result.separation_auroc - (a_near + a_unrel) / 2.0))
    assert worst <= 1e-12


# ---------------------------------------------------------------------------
# Grid mode
# ---------------------------------------------------------------------------


def _persona_grid_cli(out_dir: Path, state_dir: Path, *extra: str) -> list[str]:
    return [
        "--mode", "grid", "--corpus", "persona-v2", "--allow-pi-gated",
        "--pairing", "gemma-3-12b-it", "--model-path", "/fake/model", "--sae-path", "/fake/sae",
        "--layer", str(29), "--shortlist-size", "3",
        "--out-dir", str(out_dir), "--state-dir", str(state_dir), *extra,
    ]


def test_persona_grid_requires_allow_pi_gated(tmp_path):
    with pytest.raises(SystemExit):
        d.parse_args([
            "--mode", "grid", "--corpus", "persona-v2",
            "--pairing", "gemma-3-12b-it", "--model-path", "/m", "--sae-path", "/s",
            "--shortlist-size", "3", "--out-dir", str(tmp_path / "o"), "--state-dir", str(tmp_path / "s"),
        ])


def test_persona_grid_refuses_generated_only_positions(tmp_path):
    with pytest.raises(SystemExit):
        d.parse_args(_persona_grid_cli(tmp_path / "o", tmp_path / "s", "--positions", "generated_only"))


def test_persona_grid_defaults_to_positions_all(tmp_path):
    args = d.parse_args(_persona_grid_cli(tmp_path / "o", tmp_path / "s"))
    assert args.positions == "all"
    assert args.corpus == "persona-v2"


def test_the_corpus_flag_defaults_to_v1(tmp_path):
    args = d.parse_args([
        "--mode", "grid", "--pairing", "gemma-3-12b-it", "--model-path", "/m", "--sae-path", "/s",
        "--shortlist-size", "3", "--out-dir", str(tmp_path / "o"), "--state-dir", str(tmp_path / "s"),
    ])
    assert args.corpus == "v1"


def test_the_corpus_flag_is_not_a_concept_subset_flag(tmp_path):
    with pytest.raises(SystemExit):
        d.parse_args([*_persona_grid_cli(tmp_path / "o", tmp_path / "s"), "--concept-id", "pro_american_exceptionalism"])


def test_persona_grid_mode_covers_both_concepts(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: pf._surrogate_backend()[0])
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_persona_grid_cli(out_dir, state_dir))

    result = d.run_grid_mode(args)

    assert result["corpus"] == "persona-v2"
    assert result["concept_count"] == 2
    assert result["prompt_set_sha256"] == d.PERSONA_V2_PROMPT_SETS_SHA256
    assert result["prompt_set_commit"] == d.PERSONA_V2_FREEZE_COMMIT
    verdicts = d.read_grid_result(Path(result["grid_path"]))
    assert {v.concept_id for v in verdicts} == set(d.PERSONA_V2_CONCEPT_IDS)
    assert all(v.status in ("pass", "fail") for v in verdicts)


def test_persona_grid_mode_refuses_to_write_a_partial_grid(tmp_path, monkeypatch):
    real = d.run_concept_grid
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: pf._surrogate_backend()[0])
    monkeypatch.setattr(d, "run_concept_grid", lambda *a, **k: real(*a, **k)[:1])
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_persona_grid_cli(out_dir, state_dir))
    with pytest.raises(d.PromptArtifactError, match="expected exactly 2"):
        d.run_grid_mode(args)
    assert not (out_dir / "grid.json").is_file()


def test_run_grid_mode_refuses_persona_without_the_pi_gate_even_when_called_directly(tmp_path, monkeypatch):
    """`parse_args` enforces it, but `run_grid_mode` is also called directly
    by the job wrapper and by tests, so the refusal is not left to the CLI."""
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: pf._surrogate_backend()[0])
    args = d.parse_args(_persona_grid_cli(tmp_path / "o", tmp_path / "s"))
    args.allow_pi_gated = False
    with pytest.raises(d.PersonaCorpusError, match="requires --allow-pi-gated"):
        d.run_grid_mode(args)


# ---------------------------------------------------------------------------
# The preflight's own control arms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fault", [f for f in pf.FAULTS if f != "none"])
def test_every_preflight_fault_is_refused(fault, tmp_path):
    """The control arms are themselves under test: a fault that stopped
    provoking a refusal would mean the corresponding guard had gone
    blind."""
    report = pf.run_fault(REPO_ROOT, fault, tmp_path)
    assert report["overall_passed"] is True
    assert report["refusal"]["refused_with"] is not None


# ---------------------------------------------------------------------------
# RULING_13: the admissibility matrix
# ---------------------------------------------------------------------------


def test_a_complete_group_forms_from_members_that_individually_fail(artifact):
    """The scientific content of architect RULING_13 Q1, end to end through
    the production path: two planted features, each admissible in three of
    six cells and therefore NOT survivors, whose group has cov == 1^6.

    Non-vacuous by construction -- `survivors == 0` is asserted, so the
    coverage below cannot have been produced by a feature that would have
    passed the old six-cell conjunction anyway."""
    passed, detail = pf.check_a_complete_group_forms_from_incomplete_members(artifact)
    assert passed, detail
    assert detail["cov_of_the_GROUP_0_and_1"] == [1, 1, 1, 1, 1, 1]
    assert sum(detail["cov_of_feature_0_alone"]) == 3
    assert sum(detail["cov_of_feature_1_alone"]) == 3
    assert detail["features_admissible_in_all_cells_i_e_survivors"] == 0


def test_the_scan_retains_all_three_gate_limbs_per_cell(artifact):
    backend, _model = pf._surrogate_backend()
    scan = d.score_full_feature_space(backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0])
    assert sorted(scan.per_cell_values) == ["fire_rate", "near_miss_auroc", "separation_auroc"]
    for quantity in scan.per_cell_values.values():
        assert sorted(quantity) == sorted(scan.cell_keys)
        for vector in quantity.values():
            assert vector.shape == (backend.d_sae,)
    assert scan.admissibility_matrix.shape == (backend.d_sae, 6)
    assert scan.per_cell_fire_rate is not None
    assert scan.per_cell_near_miss_auroc is not None
    assert d.audit_retention_granularity(scan)["gate_limbs_all_per_cell_complete"] is True


def test_the_minima_are_unchanged_by_the_retention_change(artifact):
    """A RECORDING change must not move a measurement: every min_* array
    must still equal the minimum of the per-cell vectors it came from."""
    backend, _model = pf._surrogate_backend()
    scan = d.score_full_feature_space(backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[1])
    for quantity, minimum in (
        ("separation_auroc", scan.min_separation_auroc),
        ("fire_rate", scan.min_fire_rate),
        ("near_miss_auroc", scan.min_near_miss_auroc),
    ):
        stacked = np.stack([scan.per_cell_values[quantity][cell] for cell in scan.cell_keys])
        assert np.array_equal(stacked.min(axis=0), minimum)


def test_the_verdict_carries_the_matrix_so_cov_needs_no_rerun(artifact):
    backend, _model = pf._surrogate_backend()
    verdict = d.evaluate_concept_on_pairing(
        backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0], report_top_n=2
    )
    record = verdict.admissibility_matrix
    assert record is not None
    assert record["cell_order"] == ["en/f1", "en/f2", "en/f3", "fr/f1", "fr/f2", "fr/f3"]
    assert set(record["admissible_feature_indices_by_cell"]) == set(record["cell_order"])
    assert verdict.per_cell_full_space_fire_rate is not None
    assert verdict.per_cell_full_space_near_miss_auroc is not None
    assert verdict.candidate_recording_bound["verbose_records_written"] == len(verdict.candidates_evaluated)


def test_the_admissibility_record_survives_a_json_round_trip(artifact):
    """cov(G) must be computable by a downstream consumer reading
    grid.json, so the record has to be JSON-serialisable without loss."""
    backend, _model = pf._surrogate_backend()
    scan = d.score_full_feature_space(backend, artifact, concept_id=d.PERSONA_V2_CONCEPT_IDS[0])
    round_tripped = json.loads(json.dumps(scan.admissibility))
    assert round_tripped == scan.admissibility


def test_retention_cost_is_measured_at_production_scale():
    measured = d.measure_retention_cost(d_sae=81920)
    assert measured["admissibility_matrix_bytes_in_memory"] == 81920 * 6
    worst = measured["admissibility_record_json_by_admissible_fraction"]["1"]["record_json_bytes"]
    # The worst case cannot be exceeded: every feature admissible in every
    # cell. If this ever stops fitting in a few MB the coarsening decision
    # has to be re-taken against a measurement, not a guess.
    assert worst < 8 * (1 << 20)


def test_the_preflight_report_always_names_what_is_unexercised():
    assert pf.UNEXERCISED_WITHOUT_GPU
    assert any("no Gemma-3-12B-it" in item for item in pf.UNEXERCISED_WITHOUT_GPU)
