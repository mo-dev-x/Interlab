"""Tests for scripts/final_pairing/final_pairing_judge_cli.py.

Unlike test_final_pairing_causal_judge.py, `lodestar` genuinely IS
importable here once `ensure_lodestar_importable()` inserts `d:/lodstar`
(a real, separate, complete source checkout in THIS environment) onto
`sys.path` -- so tests below exercise REAL Lodestar cost estimation,
rubric identity, and Generation/Judgment construction, never a fake
substitute for those. The one thing never exercised for real is an
actual paid `AnthropicJudge` network call: `run_judging`'s injectable
`judge_factory` seam (this project's established real-default/fake-
for-tests convention) is given Lodestar's own REAL `MockJudge` instead,
so the estimate/budget/cache/persistence code path is proven against
real Lodestar objects without spending money or requiring network
access or a credential.

Manifest/file shape matches Engineer 3's real, enforcing `dose-check`
(commit ac9ea40): one manifest entry is ONE FILE covering every prompt x
repeat for a (concept, pairing, direction, dose, purpose) cell -- see
test_final_pairing_one_allocation_generation.py's own docstring for the
same fact.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_fakes as fakes  # noqa: E402
import final_pairing_judge_cli as jc  # noqa: E402
import final_pairing_one_allocation_generation as one_alloc  # noqa: E402

CONCEPT_FEATURE = 3
REAL_LODESTAR_ROOT = Path("D:/lodstar")

#: This repository's OWN venv does not have Lodestar's full dependency set
#: installed (confirmed: `anthropic` and `aiosqlite` are both absent here,
#: while `tenacity`/`tqdm`/`pandas`/`typer`/`pydantic`/`numpy`/`scipy` are
#: present) -- BY DESIGN, per the "D:-only, never install into qwen-sae-
#: interp merely to import Lodestar" mandate. `JudgeCache` (used by both
#: `run_estimate` and `run_judging`) needs `aiosqlite` just to import, so
#: the two tests that exercise it are skipped here with this reason
#: rather than failing or working around the gap -- the judge CLI is
#: designed to run wherever Lodestar's full dependency set is installed
#: (a separate environment/venv), which this is deliberately not.
_AIOSQLITE_AVAILABLE = importlib.util.find_spec("aiosqlite") is not None

pytestmark = pytest.mark.skipif(
    not (REAL_LODESTAR_ROOT / "lodestar" / "__init__.py").is_file(),
    reason="requires the real D:/lodstar checkout present in this development environment",
)
requires_aiosqlite = pytest.mark.skipif(
    not _AIOSQLITE_AVAILABLE,
    reason="aiosqlite not installed in this repo's venv (by design -- see module docstring); "
           "JudgeCache needs it just to import",
)


# ---------------------------------------------------------------------------
# ensure_lodestar_importable / credential handling.
# ---------------------------------------------------------------------------


def test_ensure_lodestar_importable_succeeds_against_the_real_checkout():
    root = jc.ensure_lodestar_importable(REAL_LODESTAR_ROOT)
    assert root == REAL_LODESTAR_ROOT
    import lodestar  # noqa: F401  (proves the path insertion actually worked)


def test_ensure_lodestar_importable_refuses_a_bogus_root(tmp_path):
    with pytest.raises(jc.causal_judge.CausalJudgeUnavailable, match="not a real Lodestar source root"):
        jc.ensure_lodestar_importable(tmp_path)


def test_require_api_key_refuses_when_unset(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(jc.CredentialMissing, match="ANTHROPIC_API_KEY is not set"):
        jc.require_api_key()


def test_require_api_key_returns_the_real_env_value(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-not-real")
    assert jc.require_api_key() == "sk-test-fake-not-real"


def test_api_key_present_is_a_bare_bool(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert jc.api_key_present() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-not-real")
    assert jc.api_key_present() is True


# ---------------------------------------------------------------------------
# Scientific-mode mock refusal.
# ---------------------------------------------------------------------------


def test_assert_judge_model_is_attestable_refuses_the_real_mock_judge_model_name():
    with pytest.raises(jc.ScientificModeMockRefused, match="mock/test judge identity"):
        jc.assert_judge_model_is_attestable(jc.MOCK_JUDGE_MODEL_NAME)


def test_assert_judge_model_is_attestable_refuses_anything_prefixed_mock():
    with pytest.raises(jc.ScientificModeMockRefused):
        jc.assert_judge_model_is_attestable("Mock-Custom-V2")


def test_assert_judge_model_is_attestable_accepts_a_pinned_snapshot():
    jc.assert_judge_model_is_attestable("claude-sonnet-4-5-20250929")  # must not raise


# ---------------------------------------------------------------------------
# build_lodestar_generations_from_dose_file: real lodestar.models.Generation
# construction, one per generation inside a bundled dose file.
# ---------------------------------------------------------------------------


def test_build_lodestar_generations_from_dose_file_builds_one_real_generation_per_entry():
    payload = {
        "concept_id": "cheese", "pairing_id": "gemma-3-12b-it", "direction": "amplify", "purpose": "sweep",
        "dose": 0, "dose_kind": "clamp", "dose_value": 1.0,
        "generations": [
            {"prompt_id": "sweep_0", "prompt_index": 0, "repeat_index": 0, "seed": 7,
             "generated_text": "a paragraph about cheese", "verdict": {}, "spec": {}},
            {"prompt_id": "sweep_1", "prompt_index": 1, "repeat_index": 0, "seed": 8,
             "generated_text": "another paragraph about cheese", "verdict": {}, "spec": {}},
        ],
    }
    generations = jc.build_lodestar_generations_from_dose_file(payload, condition="steered", model_name="google/gemma-3-12b-it")
    assert len(generations) == 2
    assert generations[0].text == "a paragraph about cheese"
    assert generations[0].target_concept == "cheese"
    assert generations[0].condition == "steered"
    assert generations[0].seed == 7
    assert generations[1].seed == 8


# ---------------------------------------------------------------------------
# manifest_entries / load_generation_files, against a REAL manifest built
# by final_pairing_one_allocation_generation.
# ---------------------------------------------------------------------------


_MANIFEST_KWARGS = dict(
    run_id="r-test-0001", source_commit="0" * 40, configuration_name="primary",
    model_id="google/gemma-3-12b-it", model_revision="deadbeef" * 5,
    sae_repo_id="google/gemma-scope-2-12b-it", sae_repo_revision="4c419f1ba0be8b7754d4151d4f26c23b92a9029e",
    release="gemma-scope-2-12b-it-res-all", loader_sae_id="layer_29_width_16k_l0_big",
    scientific_sae_id="resid_post_all/layer_29_width_16k_l0_big",
    measured_params_sha256="6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e",
    concepts={"cheese": "COMPLETE"},
)


def _tiny_manifest(tmp_path, *, n_doses=3):
    backend = fakes.make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, ["background text"])
    records = []
    for dose_index in range(n_doses):
        dose = one_alloc.DoseSpec(kind="clamp", value_in_max_units=float(dose_index + 1))
        records.append(one_alloc.generate_dose_file(
            backend, [CONCEPT_FEATURE], dose=dose, dose_index=dose_index, corpus_max=corpus_max, positions="all",
            prompts=[f"prompt {i}" for i in range(2)], purpose="sweep", n_repeats=1,
            base_seed_namespace="sweep", max_new_tokens=1, out_dir=tmp_path,
            concept_id="cheese", pairing_id=backend.pairing, direction="amplify",
        ))
    manifest_path = tmp_path / "generation_manifest.json"
    one_alloc.write_generation_manifest(records, manifest_path, **_MANIFEST_KWARGS)
    return manifest_path, backend.pairing


def test_manifest_entries_filters_by_direction_and_purpose(tmp_path):
    manifest_path, _ = _tiny_manifest(tmp_path)
    manifest = one_alloc.verify_generation_manifest(manifest_path)
    entries = jc.manifest_entries(manifest, direction="amplify", purpose="sweep")
    assert len(entries) == 3
    assert jc.manifest_entries(manifest, direction="suppress", purpose="sweep") == []


def test_load_generation_files_reads_back_real_payloads(tmp_path):
    manifest_path, _ = _tiny_manifest(tmp_path)
    manifest = one_alloc.verify_generation_manifest(manifest_path)
    entries = jc.manifest_entries(manifest, direction="amplify", purpose="sweep")
    payloads = jc.load_generation_files([e["path"] for e in entries])
    assert len(payloads) == 3
    assert all(p["concept_id"] == "cheese" for p in payloads)
    assert all(len(p["generations"]) == 2 for p in payloads)  # 2 prompts x 1 repeat each


# ---------------------------------------------------------------------------
# run_estimate: REAL Lodestar cost estimation, zero API calls.
# ---------------------------------------------------------------------------


@requires_aiosqlite
def test_run_estimate_is_real_and_makes_no_api_calls(tmp_path):
    manifest_path, _pairing_id = _tiny_manifest(tmp_path)
    manifest = one_alloc.verify_generation_manifest(manifest_path)
    entries = jc.manifest_entries(manifest, direction="amplify", purpose="sweep")
    payloads = jc.load_generation_files([e["path"] for e in entries])
    generations = []
    for p in payloads:
        generations.extend(jc.build_lodestar_generations_from_dose_file(p, condition="steered", model_name="google/gemma-3-12b-it"))
    coherence, concept_relevance = jc.causal_judge.load_steering_rubrics()
    report = jc.run_estimate(
        generations=generations, rubrics=[coherence, concept_relevance], repeats=1,
        judge_model="claude-sonnet-4-5-20250929", cache_path=tmp_path / "cache.sqlite",
    )
    assert report["total_judgments"] == 6 * 2  # 3 dose files x 2 generations each x 2 rubrics x 1 repeat
    assert report["predicted_cost_usd"] > 0
    assert report["rubric_versions"] == {"coherence": "1.0", "concept_relevance": "1.0"}


def test_persist_estimate_writes_json(tmp_path):
    path = jc.persist_estimate({"predicted_cost_usd": 1.23}, tmp_path / "estimate.json")
    assert json.loads(path.read_text(encoding="utf-8"))["predicted_cost_usd"] == 1.23


def test_assert_within_budget_passes_under_budget():
    jc.assert_within_budget(1.0, budget_usd=25.0)  # must not raise


def test_assert_within_budget_refuses_over_budget():
    with pytest.raises(jc.BudgetExceeded, match="exceeds the authorized budget"):
        jc.assert_within_budget(30.0, budget_usd=25.0)


# ---------------------------------------------------------------------------
# run_judging: real estimate/cache/persistence machinery, with Lodestar's
# own REAL MockJudge injected via judge_factory (never a paid call).
# ---------------------------------------------------------------------------


@requires_aiosqlite
def test_run_judging_with_an_injected_mock_judge_factory_persists_real_judgments(tmp_path):
    manifest_path, _ = _tiny_manifest(tmp_path)
    manifest = one_alloc.verify_generation_manifest(manifest_path)
    entries = jc.manifest_entries(manifest, direction="amplify", purpose="sweep")
    payloads = jc.load_generation_files([e["path"] for e in entries])
    generations = []
    for p in payloads:
        generations.extend(jc.build_lodestar_generations_from_dose_file(p, condition="steered", model_name="google/gemma-3-12b-it"))
    coherence, concept_relevance = jc.causal_judge.load_steering_rubrics()

    def fake_factory(judge_model, *, api_key, cache):
        from lodestar.judges.mock import MockJudge

        return MockJudge(cache=cache)

    result = jc.run_judging(
        generations=generations, rubrics=[coherence, concept_relevance], repeats=1,
        judge_model="claude-sonnet-4-5-20250929", cache_path=tmp_path / "cache.sqlite",
        api_key="unused-with-a-fake-factory", output_dir=tmp_path / "out", judge_factory=fake_factory,
    )
    assert result.total_judgments == 12  # 6 generations x 2 rubrics
    assert result.actual_cost_usd == 0.0  # zero usage tokens from MockJudge
    persisted = json.loads(Path(result.judgments_path).read_text(encoding="utf-8"))
    assert len(persisted) == 12


def test_run_judging_refuses_a_mock_judge_model_string_even_with_a_real_factory(tmp_path):
    manifest_path, _ = _tiny_manifest(tmp_path)
    manifest = one_alloc.verify_generation_manifest(manifest_path)
    entries = jc.manifest_entries(manifest, direction="amplify", purpose="sweep")
    payloads = jc.load_generation_files([e["path"] for e in entries])
    generations = []
    for p in payloads:
        generations.extend(jc.build_lodestar_generations_from_dose_file(p, condition="steered", model_name="x"))
    coherence, concept_relevance = jc.causal_judge.load_steering_rubrics()
    with pytest.raises(jc.ScientificModeMockRefused):
        jc.run_judging(
            generations=generations, rubrics=[coherence, concept_relevance], repeats=1,
            judge_model="mock-deterministic-v1", cache_path=tmp_path / "cache.sqlite",
            api_key="unused", output_dir=tmp_path / "out",
        )


# ---------------------------------------------------------------------------
# Selection record: write + commit (throwaway tmp git repo only, never the
# real project repository) + git-ancestry gating.
# ---------------------------------------------------------------------------


def _init_tmp_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "seed.txt").write_text("seed", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=path, check=True)


def _sample_selected_record() -> jc.SelectionRecord:
    return jc.build_selected_record(
        concept_id="cheese", pairing_id="gemma-3-12b-it", direction="amplify",
        low_dose=1, medium_dose=2, high_dose=4, all_confirmation_doses=[0, 1, 2, 3, 4],
    )


def test_build_selected_record_covers_every_generated_dose():
    record = _sample_selected_record()
    assert record.status == "SELECTED"
    assert record.selected == {"low": 1, "medium": 2, "high": 4}
    assert sorted(record.unselected) == [0, 3]


def test_build_failed_record_seals_all_five_doses():
    record = jc.build_failed_record(
        concept_id="cheese", pairing_id="gemma-3-12b-it", direction="suppress",
        all_confirmation_doses=[0, 1, 2, 3, 4],
    )
    assert record.status == "FAILED"
    assert record.selected == {}
    assert sorted(record.unselected) == [0, 1, 2, 3, 4]


def test_write_and_commit_selection_record_in_a_throwaway_tmp_repo(tmp_path):
    _init_tmp_git_repo(tmp_path)
    record = _sample_selected_record()
    path = tmp_path / "selection_record.json"
    jc.write_selection_record([record], path)
    commit_hash = jc.commit_selection_record(tmp_path, path, message="select doses for cheese/amplify")
    assert len(commit_hash) == 40
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=tmp_path, capture_output=True, text=True, check=True)
    assert "select doses for cheese/amplify" in log.stdout


def test_finalize_selection_ancestry_adds_both_commit_fields(tmp_path):
    record = _sample_selected_record()
    path = tmp_path / "selection_record.json"
    jc.write_selection_record([record], path)
    updated = jc.finalize_selection_ancestry(path, selection_commit="a" * 40, confirmation_judging_commit="b" * 40)
    assert updated["selection_commit"] == "a" * 40
    assert updated["confirmation_judging_commit"] == "b" * 40
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["selection_commit"] == "a" * 40


def test_assert_selection_precedes_confirmation_passes_for_a_real_ancestor_commit(tmp_path):
    _init_tmp_git_repo(tmp_path)
    record = _sample_selected_record()
    path = tmp_path / "selection_record.json"
    jc.write_selection_record([record], path)
    selection_commit = jc.commit_selection_record(tmp_path, path, message="select")
    (tmp_path / "confirmation.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "confirmation.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "confirmation judged"], cwd=tmp_path, check=True)
    confirmation_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    jc.assert_selection_precedes_confirmation(
        tmp_path, selection_commit=selection_commit, confirmation_commit=confirmation_commit,
    )  # must not raise


def test_assert_selection_precedes_confirmation_refuses_equal_commits(tmp_path):
    _init_tmp_git_repo(tmp_path)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    with pytest.raises(jc.causal_judge.CausalJudgeUnavailable, match="SAME commit"):
        jc.assert_selection_precedes_confirmation(tmp_path, selection_commit=head, confirmation_commit=head)


def test_assert_selection_precedes_confirmation_refuses_a_non_ancestor(tmp_path):
    _init_tmp_git_repo(tmp_path)
    first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "-b", "branch-a"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "branch a"], cwd=tmp_path, check=True)
    branch_a_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", first], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "branch-b"], cwd=tmp_path, check=True)
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    subprocess.run(["git", "add", "b.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "branch b"], cwd=tmp_path, check=True)
    branch_b_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()
    with pytest.raises(jc.causal_judge.CausalJudgeUnavailable, match="not an ancestor"):
        jc.assert_selection_precedes_confirmation(
            tmp_path, selection_commit=branch_a_commit, confirmation_commit=branch_b_commit,
        )


def test_assert_never_opens_unselected_refuses_a_non_selected_dose():
    record = _sample_selected_record()
    with pytest.raises(jc.causal_judge.CausalJudgeUnavailable, match=one_alloc.SEALED_LABEL):
        jc.assert_never_opens_unselected({"files": []}, record, requested_doses=[0, 1])


def test_assert_never_opens_unselected_passes_for_selected_doses_only():
    record = _sample_selected_record()
    jc.assert_never_opens_unselected({"files": []}, record, requested_doses=[1, 2, 4])  # must not raise


# ---------------------------------------------------------------------------
# CLI wiring: the parser builds real subcommands with the required flags.
# ---------------------------------------------------------------------------


def test_cli_has_all_four_subcommands():
    parser = jc.build_arg_parser()
    subparsers_action = next(a for a in parser._actions if a.dest == "command")
    assert set(subparsers_action.choices) == {
        "estimate-sweep", "judge-sweep", "write-selection", "judge-confirmation",
    }


def test_cli_judge_sweep_requires_budget_usd():
    parser = jc.build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([
            "judge-sweep", "--manifest", "m.json", "--concept-id", "cheese", "--pairing-id", "gemma-3-12b-it",
            "--direction", "amplify", "--judge-model", "claude-sonnet-4-5-20250929", "--model-name", "x",
        ])


def test_cli_write_selection_accepts_low_medium_high_doses():
    parser = jc.build_arg_parser()
    args = parser.parse_args([
        "write-selection", "--concept-id", "cheese", "--pairing-id", "gemma-3-12b-it", "--direction", "amplify",
        "--low-dose", "1", "--medium-dose", "2", "--high-dose", "4", "--out", "selection_record.json",
        "--repo-root", ".", "--commit-message", "select",
    ])
    assert args.low_dose == 1 and args.medium_dose == 2 and args.high_dose == 4
    assert args.failed is False
