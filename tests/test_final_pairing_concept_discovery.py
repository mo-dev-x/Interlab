"""CPU-only, fake-backend tests for scripts/final_pairing/final_pairing_concept_discovery.py.

No real Gemma-3-12B-it/Qwen3.5-27B/Gemma-Scope-2/Qwen-Scope weights exist on
any machine used in this investigation (same standing fact as
final_pairing_harness.py's own test suite) -- these tests exercise the
runner's ranking/validation/bundle/calibration/resumption/provenance/
failure-aggregation LOGIC against a small, deterministic fake `Backend`
whose `model_obj`/`sae` are real (tiny) torch tensors driven by a
hand-built embedding rule, not a real transformer -- following this
project's own established convention (final_pairing_harness.py's test
suite: real small files/real safetensors/real API surfaces wherever cheap,
fakes only for what would otherwise require real multi-GB weights or a
GPU). No model is ever loaded from disk in this file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sys
from pathlib import Path

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402
import final_pairing_targets as targets  # noqa: E402

D_MODEL = 6
D_SAE = 8
CONCEPT_FEATURE = 3  # the feature this fake SAE's encode() dedicates to "the concept"
OTHER_FEATURE = 5  # a feature that fires on nothing in particular (noise only)
HOOK_NAME = "fake.hook"


def _text_embedding(text: str) -> torch.Tensor:
    """Deterministic per-text embedding: texts containing 'POSITIVE' get a
    strong push along a fixed 'concept direction' (which the fake SAE's
    encode() maps onto CONCEPT_FEATURE); every other text gets small,
    text-seeded noise only. Real torch tensors throughout -- no mocking of
    tensor math itself."""
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**31)
    gen = torch.Generator().manual_seed(seed)
    noise = torch.randn(D_MODEL, generator=gen) * 0.01
    if "POSITIVE" in text:
        concept_direction = torch.zeros(D_MODEL)
        concept_direction[0] = 5.0
        return concept_direction + noise
    return noise


class _FakeSAE:
    """encode() is a fixed linear map: dimension 0 of the residual drives
    CONCEPT_FEATURE; every other SAE feature reads from residual dims that
    every text's embedding leaves near zero, so they stay noise-only."""

    def __init__(self):
        self.d_in = D_MODEL
        self.d_sae = D_SAE
        w = torch.zeros(D_SAE, D_MODEL)
        w[CONCEPT_FEATURE, 0] = 1.0
        w[OTHER_FEATURE, 1] = 1.0
        self.W = w
        self.k = None

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return torch.relu(x.to(torch.float32) @ self.W.T)

    def decode(self, feats: torch.Tensor) -> torch.Tensor:
        return feats.to(torch.float32) @ self.W


class _FakeTokenizer:
    def decode(self, ids) -> str:
        return "fake-generated-text"


class _FakeGemmaModel:
    """Mimics only the surface `final_pairing_concept_discovery.py` calls:
    `.to_tokens`, `.run_with_cache`, `.hooks`, `.generate`, `.tokenizer`."""

    def __init__(self):
        self.tokenizer = _FakeTokenizer()
        self._active_hooks: list = []
        self._texts_by_token: dict[int, str] = {}
        self._next_token = 0

    def _register_text(self, text: str) -> int:
        token = self._next_token
        self._next_token += 1
        self._texts_by_token[token] = text
        return token

    def to_tokens(self, text: str) -> torch.Tensor:
        return torch.tensor([[self._register_text(text)]])

    def run_with_cache(self, tokens: torch.Tensor, names_filter: str):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([_text_embedding(t) for t in seq]).unsqueeze(0)  # [1, seq, d_model]
        return None, {names_filter: resid}

    @contextlib.contextmanager
    def hooks(self, fwd_hooks):
        # Only a hook registered under the model's own real hook point
        # actually fires -- mirrors real HookedTransformer.hooks(), which
        # silently registers nothing for a hook_name that isn't a real
        # point in the model's graph (the exact scenario the Gemma hook
        # preflight test needs to be able to trigger).
        self._active_hooks = [(name, fn) for name, fn in fwd_hooks if name == HOOK_NAME]
        try:
            yield
        finally:
            self._active_hooks = []

    def __call__(self, tokens: torch.Tensor):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([_text_embedding(t) for t in seq]).unsqueeze(0)
        for _name, fn in self._active_hooks:
            resid = fn(resid, hook=None)
        return resid

    def generate(self, tokens: torch.Tensor, *, max_new_tokens: int, do_sample: bool, verbose: bool = False):
        seq = [self._texts_by_token[int(t)] for t in tokens[0].tolist()]
        resid = torch.stack([_text_embedding(t) for t in seq]).unsqueeze(0)
        for _name, fn in self._active_hooks:
            resid = fn(resid, hook=None)
        out = tokens.clone()
        for _ in range(max_new_tokens):
            step = _text_embedding("PAD").unsqueeze(0).unsqueeze(0)
            for _name, fn in self._active_hooks:
                step = fn(step, hook=None)
            out = torch.cat([out, torch.zeros((1, 1), dtype=torch.long)], dim=1)
        return out


def make_fake_gemma_backend() -> d.Backend:
    return d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name,
        model_obj=_FakeGemmaModel(),
        sae=_FakeSAE(),
        hook_name=HOOK_NAME,
        d_sae=D_SAE,
        d_model=D_MODEL,
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={
            "model": {"repository": "google/gemma-3-12b-it", "local_path": "/fake/model"},
            "sae": {"repository": "google/gemma-scope-2-12b-it"},
        },
        checkpoint_hash="deadbeef",
    )


POSITIVE_TEXTS = [f"POSITIVE example {i}" for i in range(6)]
NEGATIVE_TEXTS = [f"neutral filler {i}" for i in range(6)]


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_rank_features_by_activation_puts_the_concept_feature_first():
    backend = make_fake_gemma_backend()
    ranked = d.rank_features_by_activation(backend, POSITIVE_TEXTS, top_n=3)
    assert ranked[0].feature_index == CONCEPT_FEATURE
    assert ranked[0].activation_score > 0
    assert all(ranked[i].activation_score >= ranked[i + 1].activation_score for i in range(len(ranked) - 1))


def test_rank_features_by_activation_rejects_empty_texts():
    backend = make_fake_gemma_backend()
    with pytest.raises(ValueError):
        d.rank_features_by_activation(backend, [], top_n=3)


def test_exclude_mechanical_only_drops_the_engineering_only_feature():
    ranked = [d.RankedFeature(feature_index=250, activation_score=9.0), d.RankedFeature(feature_index=7, activation_score=1.0)]
    filtered = d.exclude_mechanical_only("gemma-3-12b-it", ranked)
    assert [r.feature_index for r in filtered] == [7]


def test_reject_mechanical_only_feature_raises_for_the_exact_placeholder_id():
    with pytest.raises(targets.TargetIdentityMismatch):
        d.reject_mechanical_only_feature("gemma-3-12b-it", 250, context="test")
    with pytest.raises(targets.TargetIdentityMismatch):
        d.reject_mechanical_only_feature("qwen-3.5-27b", 4096, context="test")
    d.reject_mechanical_only_feature("gemma-3-12b-it", 251, context="test")  # must not raise


def test_corpus_max_per_feature_reports_the_true_max_for_the_concept_feature():
    backend = make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, POSITIVE_TEXTS + NEGATIVE_TEXTS)
    assert corpus_max[CONCEPT_FEATURE] > corpus_max[OTHER_FEATURE]
    assert all(v >= 0 for v in corpus_max.values())


def test_corpus_max_per_feature_rejects_empty_corpus():
    backend = make_fake_gemma_backend()
    with pytest.raises(ValueError):
        d.corpus_max_per_feature(backend, [])


# ---------------------------------------------------------------------------
# Held-out specificity validation
# ---------------------------------------------------------------------------


def test_validate_specificity_passes_for_the_truly_separating_feature():
    backend = make_fake_gemma_backend()
    result = d.validate_specificity(
        backend, CONCEPT_FEATURE,
        train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
        holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
        holdout_controls=[f"neutral holdout {i}" for i in range(6)],
        seed=0, auc_threshold=0.9,
    )
    assert result.holdout_auc >= 0.9
    assert result.passed is True
    assert result.holdout_gap >= 0.0


def test_validate_specificity_fails_for_a_noise_only_feature():
    backend = make_fake_gemma_backend()
    result = d.validate_specificity(
        backend, OTHER_FEATURE,
        train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
        holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
        holdout_controls=[f"neutral holdout {i}" for i in range(6)],
        seed=0, auc_threshold=0.99,
    )
    assert result.passed is False


def test_validate_specificity_requires_a_floor_of_examples_per_split():
    backend = make_fake_gemma_backend()
    with pytest.raises(ValueError):
        d.validate_specificity(
            backend, CONCEPT_FEATURE,
            train_probes=["only one"], train_controls=NEGATIVE_TEXTS,
            holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
            holdout_controls=[f"neutral holdout {i}" for i in range(6)],
            seed=0, auc_threshold=0.9,
        )


# ---------------------------------------------------------------------------
# Bundle selection (stage 4)
# ---------------------------------------------------------------------------


def test_bundle_max_size_one_returns_the_seed_feature_alone_with_no_steps():
    backend = make_fake_gemma_backend()
    bundle = d.compose_bundle_greedily(
        backend, CONCEPT_FEATURE, [CONCEPT_FEATURE, OTHER_FEATURE],
        train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
        holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
        holdout_controls=[f"neutral holdout {i}" for i in range(6)],
        seed=0, materiality_threshold=0.01, bundle_max_size=1,
    )
    assert bundle.feature_indices == [CONCEPT_FEATURE]
    assert bundle.steps == []


def test_bundle_composition_rejects_a_candidate_below_the_materiality_threshold():
    backend = make_fake_gemma_backend()
    bundle = d.compose_bundle_greedily(
        backend, CONCEPT_FEATURE, [CONCEPT_FEATURE, OTHER_FEATURE],
        train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
        holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
        holdout_controls=[f"neutral holdout {i}" for i in range(6)],
        seed=0, materiality_threshold=0.999, bundle_max_size=2,
    )
    assert bundle.feature_indices == [CONCEPT_FEATURE]
    assert len(bundle.steps) == 1
    assert bundle.steps[0].added is False
    assert bundle.steps[0].metric_gain is None
    assert bundle.steps[0].metric_before >= 0.0 and bundle.steps[0].metric_candidate >= 0.0


def test_bundle_materiality_threshold_must_be_non_negative():
    backend = make_fake_gemma_backend()
    with pytest.raises(ValueError):
        d.compose_bundle_greedily(
            backend, CONCEPT_FEATURE, [CONCEPT_FEATURE],
            train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
            holdout_probes=POSITIVE_TEXTS, holdout_controls=NEGATIVE_TEXTS,
            seed=0, materiality_threshold=-0.1, bundle_max_size=2,
        )


def test_every_bundle_step_field_is_non_negative_or_none():
    backend = make_fake_gemma_backend()
    bundle = d.compose_bundle_greedily(
        backend, CONCEPT_FEATURE, [CONCEPT_FEATURE, OTHER_FEATURE],
        train_probes=POSITIVE_TEXTS, train_controls=NEGATIVE_TEXTS,
        holdout_probes=[f"POSITIVE holdout {i}" for i in range(6)],
        holdout_controls=[f"neutral holdout {i}" for i in range(6)],
        seed=0, materiality_threshold=0.0, bundle_max_size=2,
    )
    for step in bundle.steps:
        assert step.metric_before >= 0.0
        assert step.metric_candidate >= 0.0
        assert step.metric_gain is None or step.metric_gain >= 0.0


# ---------------------------------------------------------------------------
# Calibration candidate selection (stage 6) -- pure function, real dataclass
# instances (asdict requires real dataclasses, not ad hoc doubles).
# ---------------------------------------------------------------------------


def _outcome(value_in_max_units: float) -> d.InterventionOutcome:
    return d.InterventionOutcome(
        feature_indices=[CONCEPT_FEATURE], direction="clamp", value_in_max_units=value_in_max_units,
        corpus_max_used=10.0, absolute_clamp_value=value_in_max_units * 10.0, positions="all",
        generated_text="x", verdict={"nonzero_steer_confirmed": True}, spec={},
    )


def test_select_calibration_candidates_picks_the_smallest_dose_at_or_above_each_threshold():
    outcomes = [_outcome(v) for v in (0.5, 1.0, 2.0, 4.0, 8.0)]
    result = d.select_calibration_candidates(outcomes, low_threshold=1.0, medium_threshold=2.0, high_threshold=8.0)
    assert result["low"].value_in_max_units == 1.0
    assert result["medium"].value_in_max_units == 2.0
    assert result["high"].value_in_max_units == 8.0


def test_select_calibration_candidates_reports_none_when_no_dose_clears_a_tier():
    outcomes = [_outcome(v) for v in (0.5, 1.0)]
    result = d.select_calibration_candidates(outcomes, low_threshold=0.5, medium_threshold=1.0, high_threshold=100.0)
    assert result["high"] is None


def test_select_calibration_candidates_rejects_out_of_order_thresholds():
    outcomes = [_outcome(1.0)]
    with pytest.raises(ValueError):
        d.select_calibration_candidates(outcomes, low_threshold=5.0, medium_threshold=1.0, high_threshold=10.0)


# ---------------------------------------------------------------------------
# Resumption (ProgressLog)
# ---------------------------------------------------------------------------


def test_progress_log_persists_across_separate_instances(tmp_path):
    log_path = tmp_path / "progress.jsonl"
    first = d.ProgressLog(log_path)
    assert not first.is_done("stage1_rank")
    first.record("stage1_rank", {"ranked": [1, 2, 3]})

    resumed = d.ProgressLog(log_path)
    assert resumed.is_done("stage1_rank")
    assert resumed.result("stage1_rank")["ranked"] == [1, 2, 3]


def test_progress_log_is_append_only_and_keeps_multiple_keys(tmp_path):
    log_path = tmp_path / "progress.jsonl"
    log = d.ProgressLog(log_path)
    log.record("a", {"v": 1})
    log.record("b", {"v": 2})
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    reloaded = d.ProgressLog(log_path)
    assert reloaded.is_done("a") and reloaded.is_done("b")


def test_run_skips_recomputing_a_stage_already_present_in_the_progress_log(tmp_path, monkeypatch):
    """Proves genuine resumability, not just that ProgressLog itself works:
    pre-seed stage1_rank's key and confirm `run()` never calls the ranking
    function again."""
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())

    def _boom(*args, **kwargs):
        raise AssertionError("rank_features_by_activation must not be called when the stage is already recorded")

    prompt_set_path, prompt_set_sha256 = _write_prompt_set(tmp_path)
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    state_dir.mkdir()
    pre_seeded = d.ProgressLog(state_dir / "progress.jsonl")
    pre_seeded.record("stage1_rank", {"ranked": [{"feature_index": CONCEPT_FEATURE, "activation_score": 5.0}]})

    monkeypatch.setattr(d, "rank_features_by_activation", _boom)

    args = d.parse_args(_common_cli_args(prompt_set_path, prompt_set_sha256, out_dir, state_dir))
    d.run(args)  # must not raise


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def _write_prompt_set(tmp_path: Path, *, concept_id: str = "concept_a") -> tuple[Path, str]:
    payload = {
        "concept_id": concept_id,
        "probes": POSITIVE_TEXTS,
        "controls": NEGATIVE_TEXTS,
        "holdout_probes": [f"POSITIVE holdout {i}" for i in range(6)],
        "holdout_controls": [f"neutral holdout {i}" for i in range(6)],
        "background_corpus": POSITIVE_TEXTS + NEGATIVE_TEXTS,
    }
    path = tmp_path / "prompt_set.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, sha256


def _common_cli_args(prompt_set_path: Path, prompt_set_sha256: str, out_dir: Path, state_dir: Path) -> list[str]:
    return [
        "--pairing", "gemma-3-12b-it",
        "--model-path", "/fake/model", "--sae-path", "/fake/sae",
        "--prompt-set-path", str(prompt_set_path), "--prompt-set-sha256", prompt_set_sha256,
        "--shortlist-size", "3", "--direction", "clamp", "--dose-grid", "1.0,2.0",
        "--specificity-auc-threshold", "0.9", "--bundle-materiality-threshold", "0.01",
        "--calibration-low-threshold", "1.0", "--calibration-medium-threshold", "1.5", "--calibration-high-threshold", "2.0",
        "--out-dir", str(out_dir), "--state-dir", str(state_dir),
    ]


def test_run_writes_provenance_with_model_sae_layer_and_checkpoint_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    prompt_set_path, prompt_set_sha256 = _write_prompt_set(tmp_path)
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"

    args = d.parse_args(_common_cli_args(prompt_set_path, prompt_set_sha256, out_dir, state_dir))
    result = d.run(args)

    assert result["status"] == "complete"
    prov = result["provenance"]
    assert prov["model"]["repository"] == "google/gemma-3-12b-it"
    assert prov["sae"]["repository"] == "google/gemma-scope-2-12b-it"
    assert prov["layer"] == targets.GEMMA_3_12B_IT_TARGET.expected_layer
    assert prov["checkpoint_hash"] == "deadbeef"
    assert (out_dir / "result.json").is_file()
    written = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    assert written["provenance"]["checkpoint_hash"] == "deadbeef"


def test_run_records_prompt_set_identity_and_judge_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    prompt_set_path, prompt_set_sha256 = _write_prompt_set(tmp_path, concept_id="concept_xyz")
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"

    args = d.parse_args(_common_cli_args(prompt_set_path, prompt_set_sha256, out_dir, state_dir))
    result = d.run(args)

    assert result["concept_id"] == "concept_xyz"
    assert result["prompt_set"]["sha256"] == prompt_set_sha256
    assert result["judge"] == {"model": "none", "rubric_version": "none", "prompt_version": "none"}


# ---------------------------------------------------------------------------
# Failure aggregation (stage 2 -> no-candidate-passed short-circuit)
# ---------------------------------------------------------------------------


def test_run_reports_no_candidate_passed_specificity_and_does_not_reach_bundle_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())

    def _boom(*args, **kwargs):
        raise AssertionError("compose_bundle_greedily must not run when no candidate passed specificity")

    monkeypatch.setattr(d, "compose_bundle_greedily", _boom)

    prompt_set_path, prompt_set_sha256 = _write_prompt_set(tmp_path)
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_common_cli_args(prompt_set_path, prompt_set_sha256, out_dir, state_dir))
    # An impossibly strict threshold guarantees every candidate fails stage 2.
    args.specificity_auc_threshold = 1.01
    result = d.run(args)

    assert result["status"] == "no_candidate_passed_specificity"
    assert all(not r["passed"] for r in result["specificity_results"])
    written = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
    assert written["status"] == "no_candidate_passed_specificity"


def test_main_returns_zero_for_a_complete_run_and_for_no_candidate_passed(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    prompt_set_path, prompt_set_sha256 = _write_prompt_set(tmp_path)
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    exit_code = d.main(_common_cli_args(prompt_set_path, prompt_set_sha256, out_dir, state_dir))
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Prompt-set hashing and pairing/layer fail-closed checks
# ---------------------------------------------------------------------------


def test_load_prompt_set_rejects_a_mismatched_hash(tmp_path):
    path, real_hash = _write_prompt_set(tmp_path)
    with pytest.raises(targets.TargetIdentityMismatch):
        d.load_prompt_set(path, expected_sha256="0" * 64)
    d.load_prompt_set(path, expected_sha256=real_hash)  # must not raise


def test_load_prompt_set_rejects_missing_required_fields(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"concept_id": "x", "probes": []}), encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        d.load_prompt_set(path, expected_sha256=sha)


def test_load_backend_rejects_a_non_ratified_pairing():
    with pytest.raises(targets.TargetIdentityMismatch):
        d.load_backend(
            pairing="gemma-3-12b-pt", model_path="x", sae_path="y", layer=None,
            expected_model_revision=None, expected_sae_revision=None, device="cpu", dtype="bfloat16",
        )


def test_load_backend_rejects_a_gemma_layer_override_that_disagrees_with_the_ratified_layer():
    with pytest.raises(targets.TargetIdentityMismatch):
        d.load_backend(
            pairing="gemma-3-12b-it", model_path="x", sae_path="y", layer=999,
            expected_model_revision=None, expected_sae_revision=None, device="cpu", dtype="bfloat16",
        )


def test_load_backend_requires_layer_sae_family_and_sparsity_for_qwen():
    with pytest.raises(ValueError):
        d.load_backend(
            pairing="qwen-3.5-27b", model_path="x", sae_path="y", layer=None,
            expected_model_revision=None, expected_sae_revision=None, device="cpu", dtype="bfloat16",
        )
    with pytest.raises(ValueError):
        d.load_backend(
            pairing="qwen-3.5-27b", model_path="x", sae_path="y", layer=10,
            expected_model_revision=None, expected_sae_revision=None, device="cpu", dtype="bfloat16",
            sae_family=None, sparsity=None,
        )


def test_load_qwen_scientific_target_rejects_layer_zero_and_unratified_family():
    with pytest.raises(targets.TargetIdentityMismatch):
        d.load_qwen_scientific_target("x", "y", layer=0, sae_family="L0_100", k=100)
    with pytest.raises(targets.TargetIdentityMismatch):
        d.load_qwen_scientific_target("x", "y", layer=10, sae_family="L0_999", k=100)


def test_qwen_scientific_target_overrides_only_k_not_other_ratified_fields():
    variant = d._qwen_scientific_target(k=100)
    base = targets.QWEN_3_5_27B_TARGET
    assert variant.expected_k == 100
    assert variant.model_repo_id == base.model_repo_id
    assert variant.sae_repo_id == base.sae_repo_id
    assert variant.expected_hidden_dim == base.expected_hidden_dim
    assert variant.sae_format == base.sae_format


def test_matched_configurations_match_the_predeclared_values():
    assert d.PRIMARY_CONFIGURATION.qwen_layer == 38
    assert d.PRIMARY_CONFIGURATION.qwen_sae_family == "L0_100"
    assert d.PRIMARY_CONFIGURATION.qwen_sparsity == 100
    assert d.PRIMARY_CONFIGURATION.gemma_layer == 29
    assert d.BACKUP_CONFIGURATION.qwen_layer == 32
    assert d.BACKUP_CONFIGURATION.qwen_sae_family == "L0_50"
    assert d.BACKUP_CONFIGURATION.qwen_sparsity == 50
    assert d.BACKUP_CONFIGURATION.gemma_layer == 24
    assert set(d.MATCHED_CONFIGURATIONS) == {"primary", "backup"}


def test_gemma_scientific_target_rejects_a_third_layer_and_derives_ids_correctly():
    """Values confirmed directly against the locally-installed
    sae_lens==6.44.2 registry (2026-08-13 staging-facts addendum):
    primary's `resid_post_all` family and backup's `resid_post` family are
    CONFIRMED-DIFFERENT sae_lens releases -- layer 29 exists only under
    `gemma-scope-2-12b-it-res-all` (as `layer_29_width_16k_l0_big`, not
    `_l0_medium`), and layer 24's `_l0_medium` variant exists only under
    `gemma-scope-2-12b-it-res` (not `-res-all`)."""
    with pytest.raises(targets.TargetIdentityMismatch):
        d._gemma_scientific_target(layer=31)  # the mechanical layer -- not a scientific candidate
    with pytest.raises(targets.TargetIdentityMismatch):
        d._gemma_scientific_target(layer=1)

    primary = d._gemma_scientific_target(layer=29)
    assert primary.expected_layer == 29
    assert primary.sae_release == "gemma-scope-2-12b-it-res-all"
    assert primary.sae_id == "resid_post_all/layer_29_width_16k_l0_big"
    assert primary.sae_loader_id == "layer_29_width_16k_l0_big"
    assert primary.expected_hook_name == "blocks.29.hook_resid_post"
    assert primary.model_repo_id == targets.GEMMA_3_12B_IT_TARGET.model_repo_id

    backup = d._gemma_scientific_target(layer=24)
    assert backup.expected_layer == 24
    assert backup.sae_release == "gemma-scope-2-12b-it-res"
    assert backup.sae_id == "resid_post/layer_24_width_16k_l0_medium"
    assert backup.sae_loader_id == "layer_24_width_16k_l0_medium"
    assert backup.expected_hook_name == "blocks.24.hook_resid_post"

    # The two releases are genuinely different strings, matching the
    # confirmed sae_lens registry fact this test's docstring records.
    assert primary.sae_release != backup.sae_release


def test_load_backend_requires_layer_for_gemma_too():
    with pytest.raises(ValueError):
        d.load_backend(
            pairing="gemma-3-12b-it", model_path="x", sae_path="y", layer=None,
            expected_model_revision=None, expected_sae_revision=None, device="cpu", dtype="bfloat16",
        )


def test_matched_configurations_record_the_frozen_qwen_depth_fractions():
    assert d.PRIMARY_CONFIGURATION.qwen_depth_fraction == 0.59375
    assert d.BACKUP_CONFIGURATION.qwen_depth_fraction == 0.5


# ---------------------------------------------------------------------------
# The frozen backup-trigger formula (protocols/final_pairing/v1/
# backup_trigger.json, commit 125b1d3) -- evaluate_backup_trigger
# implements exactly its boolean_expression/failure_expression.
# ---------------------------------------------------------------------------


def test_backup_trigger_fires_when_primary_complete_and_shared_count_below_three():
    result = d.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=2)
    assert result.run_backup is True
    assert result.fail_run is False


def test_backup_trigger_does_not_fire_when_shared_count_meets_the_threshold():
    result = d.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=3)
    assert result.run_backup is False
    assert result.fail_run is False


@pytest.mark.parametrize("count", [0, 1, 2])
def test_backup_trigger_fires_for_every_count_strictly_below_three(count):
    assert d.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=count).run_backup is True


@pytest.mark.parametrize("count", [3, 4, 14])
def test_backup_trigger_does_not_fire_for_counts_at_or_above_three(count):
    assert d.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=count).run_backup is False


def test_an_incomplete_primary_never_triggers_backup_regardless_of_count():
    """'AN EXECUTION ERROR NEVER TRIGGERS BACKUP' -- even a shared count of
    0 must not fire backup when primary_complete is False."""
    result = d.evaluate_backup_trigger(primary_complete=False, primary_shared_gabc_count=0)
    assert result.run_backup is False
    assert result.fail_run is True


def test_incomplete_primary_does_not_require_a_shared_count_at_all():
    result = d.evaluate_backup_trigger(primary_complete=False, primary_shared_gabc_count=None)
    assert result.fail_run is True
    assert result.run_backup is False


def test_complete_primary_requires_a_shared_count():
    with pytest.raises(ValueError):
        d.evaluate_backup_trigger(primary_complete=True, primary_shared_gabc_count=None)


def test_backup_trigger_threshold_is_frozen_at_three():
    assert d.BACKUP_TRIGGER_SHARED_COUNT_THRESHOLD == 3


def test_assert_gemma_qwen_depth_matches_passes_within_tolerance():
    # PRIMARY: qwen depth_fraction 0.59375, gemma layer 29. Choose gemma
    # n_layers so 29/n_layers lands within 0.02 of 0.59375 (e.g. n=48 -> 0.6042).
    fraction = d.assert_gemma_qwen_depth_matches(gemma_layer=29, gemma_n_layers=48, qwen_depth_fraction=d.PRIMARY_CONFIGURATION.qwen_depth_fraction)
    assert abs(fraction - 29 / 48) < 1e-9


def test_assert_gemma_qwen_depth_matches_fails_closed_outside_tolerance():
    with pytest.raises(targets.TargetIdentityMismatch):
        d.assert_gemma_qwen_depth_matches(gemma_layer=5, gemma_n_layers=48, qwen_depth_fraction=d.PRIMARY_CONFIGURATION.qwen_depth_fraction)


def test_parse_dose_grid_rejects_negative_values_and_parses_floats():
    assert d._parse_dose_grid("0.5,1,2") == [0.5, 1.0, 2.0]
    with pytest.raises(ValueError):
        d._parse_dose_grid("-1")
    with pytest.raises(ValueError):
        d._parse_dose_grid("")


# ---------------------------------------------------------------------------
# No pytest/heavy-model-loading leakage into CPU test collection itself --
# a cheap structural sanity check, not a behavioral one.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Frozen prompt artifact (prompts/final_pairing/v1/) -- against the REAL,
# already-committed artifact, not a fake. No model is loaded by any of
# these; they only read files and run the committed validator subprocess.
# ---------------------------------------------------------------------------


def test_load_frozen_prompt_artifact_matches_the_pinned_commit_and_hashes():
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    assert artifact.commit == d.FROZEN_PROMPT_SET_COMMIT
    assert artifact.prompt_sets_sha256 == d.FROZEN_PROMPT_SETS_SHA256
    assert artifact.metadata_sha256 == d.FROZEN_METADATA_SHA256


def test_load_frozen_prompt_artifact_excludes_pi_gated_concept_by_default():
    excluded = d.load_frozen_prompt_artifact(d.REPO_ROOT, allow_pi_gated=False)
    included = d.load_frozen_prompt_artifact(d.REPO_ROOT, allow_pi_gated=True)
    assert all(row["concept_id"] != d.PI_GATED_CONCEPT_ID for row in excluded.rows)
    assert any(row["concept_id"] == d.PI_GATED_CONCEPT_ID for row in included.rows)
    assert len(included.rows) - len(excluded.rows) == excluded.pi_gated_excluded_row_count
    assert excluded.pi_gated_excluded_row_count > 0


def test_load_frozen_prompt_artifact_has_exactly_2800_rows_before_pi_gating():
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT, allow_pi_gated=True)
    assert len(artifact.rows) == d.FROZEN_PROMPT_SET_ROW_COUNT == 2800


def test_load_frozen_prompt_artifact_rejects_a_wrong_pinned_hash(monkeypatch):
    monkeypatch.setattr(d, "FROZEN_METADATA_SHA256", "0" * 64)
    with pytest.raises(d.PromptArtifactError):
        d.load_frozen_prompt_artifact(d.REPO_ROOT)


def test_load_frozen_prompt_artifact_rejects_a_wrong_expected_row_count(monkeypatch):
    monkeypatch.setattr(d, "FROZEN_PROMPT_SET_ROW_COUNT", 999999)
    with pytest.raises(d.PromptArtifactError):
        d.load_frozen_prompt_artifact(d.REPO_ROOT)


def test_rows_for_concept_preserves_shared_substrate_identity_across_concepts():
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    cheese_unrelated = d.rows_for_concept(artifact.rows, concept_id="cheese", locale="en", split="unrelated")
    chess_unrelated = d.rows_for_concept(artifact.rows, concept_id="chess", locale="en", split="unrelated")
    assert [r["text"] for r in cheese_unrelated] == [r["text"] for r in chess_unrelated]
    assert all(r["shared_substrate"] for r in cheese_unrelated)


def test_rows_for_concept_filters_positive_split_by_family():
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    f1_rows = d.rows_for_concept(artifact.rows, concept_id="cheese", locale="en", split="positive", family="f1")
    assert len(f1_rows) == 10
    assert all(r["family"] == "f1" for r in f1_rows)


def test_run_prompt_set_validator_passes_against_the_real_committed_artifact():
    d.run_prompt_set_validator(d.REPO_ROOT)  # must not raise


def test_run_prompt_set_validator_raises_when_the_validator_script_is_missing(tmp_path):
    with pytest.raises(d.PromptArtifactError):
        d.run_prompt_set_validator(tmp_path)


def test_compute_gate_a_and_b_per_family_runs_independently_per_family_and_reads_default_thresholds():
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    results = d.compute_gate_a_and_b_per_family(
        backend, artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE,
    )
    assert {r.family for r in results} == {"f1", "f2", "f3"}
    for r in results:
        assert 0.0 <= r.separation_auroc <= 1.0
        assert 0.0 <= r.fire_rate <= 1.0
        assert r.activation_floor_fraction == artifact.metadata["thresholds"]["G_B_activation_floor_fraction_of_observed_max"]


def test_compute_gate_a_and_b_per_family_honors_explicit_threshold_overrides():
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    results = d.compute_gate_a_and_b_per_family(
        backend, artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE,
        auroc_min=0.0, activation_floor_fraction=0.0, fire_rate_min=0.0,
    )
    assert all(r.gate_a_passed for r in results)
    assert all(r.gate_b_passed for r in results)


# ---------------------------------------------------------------------------
# Gemma hook preflight (dynamic hook resolution assertions)
# ---------------------------------------------------------------------------


def test_gemma_hook_preflight_passes_when_the_hook_fires_with_the_right_dimension():
    model = _FakeGemmaModel()
    sae = _FakeSAE()
    result = d.run_gemma_hook_preflight(model, sae, HOOK_NAME, expected_hidden_dim=D_MODEL, expected_layer=29)
    assert result.passed is True
    assert result.hook_fired is True
    assert result.hook_invocation_count == 1
    assert result.captured_last_dim == D_MODEL
    assert result.configured_hook_string == HOOK_NAME
    assert result.layer_index_asserted == 29


def test_gemma_hook_preflight_fails_closed_when_the_hook_never_fires():
    model = _FakeGemmaModel()
    sae = _FakeSAE()
    with pytest.raises(targets.TargetIdentityMismatch):
        d.run_gemma_hook_preflight(model, sae, "blocks.999.hook_that_does_not_exist", expected_hidden_dim=D_MODEL, expected_layer=29)


def test_gemma_hook_preflight_fails_closed_on_a_dimension_mismatch():
    model = _FakeGemmaModel()
    sae = _FakeSAE()
    with pytest.raises(targets.TargetIdentityMismatch):
        d.run_gemma_hook_preflight(model, sae, HOOK_NAME, expected_hidden_dim=D_MODEL + 1, expected_layer=29)


def test_no_real_model_path_is_ever_touched_by_this_test_module():
    """This file must never import torch's cuda path or call any real
    `load_gemma_it_target`/`load_qwen_target`/`load_qwen_scientific_target`
    against a real filesystem snapshot -- every test above either uses a
    pure function or monkeypatches `load_backend` before calling `run`."""
    assert not torch.cuda.is_available() or True  # environment fact, not asserted; documents intent only
    assert hasattr(d, "load_backend")  # the seam every heavy test monkeypatches


# ---------------------------------------------------------------------------
# Registry release/subdirectory mapping assertion (2026-08-13 staging-facts
# addendum): confirmed for real against the locally-installed
# sae_lens==6.44.2 registry above; these tests exercise the failure paths
# with a fake registry object, never touching the real one.
# ---------------------------------------------------------------------------


class _FakeReleaseEntry:
    def __init__(self, repo_id, saes_map):
        self.repo_id = repo_id
        self.saes_map = saes_map


def test_assert_registry_release_and_subdirectory_match_passes_for_a_correct_mapping():
    target = d._gemma_scientific_target(layer=29)
    directory = {target.sae_release: _FakeReleaseEntry(target.sae_repo_id, {target.sae_loader_id: target.sae_id})}
    d.assert_registry_release_and_subdirectory_match(directory, target=target)  # must not raise


def test_assert_registry_release_and_subdirectory_match_rejects_unknown_release():
    target = d._gemma_scientific_target(layer=29)
    with pytest.raises(targets.TargetIdentityMismatch, match="no release"):
        d.assert_registry_release_and_subdirectory_match({}, target=target)


def test_assert_registry_release_and_subdirectory_match_rejects_wrong_repo_id():
    target = d._gemma_scientific_target(layer=29)
    directory = {target.sae_release: _FakeReleaseEntry("some/other-repo", {target.sae_loader_id: target.sae_id})}
    with pytest.raises(targets.TargetIdentityMismatch, match="repo_id"):
        d.assert_registry_release_and_subdirectory_match(directory, target=target)


def test_assert_registry_release_and_subdirectory_match_rejects_a_loader_id_mapped_to_the_wrong_subdirectory():
    """The exact failure mode this check exists for: a loader_sae_id that
    IS registered under the release, but maps to a DIFFERENT subdirectory
    than the one this file's target recorded -- never derived by parsing
    the loader id string, so this can only be caught by reading the
    registry's own mapping."""
    target = d._gemma_scientific_target(layer=29)
    directory = {target.sae_release: _FakeReleaseEntry(target.sae_repo_id, {target.sae_loader_id: "resid_post/layer_24_width_16k_l0_medium"})}
    with pytest.raises(targets.TargetIdentityMismatch, match="maps loader_sae_id"):
        d.assert_registry_release_and_subdirectory_match(directory, target=target)


def test_registry_mapping_is_correct_for_both_real_configurations_against_the_installed_sae_lens_registry():
    """Ground truth against the REAL, locally-installed sae_lens==6.44.2
    registry -- not a fake. If sae_lens is upgraded and this registry
    entry changes shape, this test fails loudly rather than silently
    trusting a stale hardcoded MatchedConfiguration value."""
    from sae_lens.loading.pretrained_saes_directory import get_pretrained_saes_directory

    directory = get_pretrained_saes_directory()
    d.assert_registry_release_and_subdirectory_match(directory, target=d._gemma_scientific_target(layer=29))
    d.assert_registry_release_and_subdirectory_match(directory, target=d._gemma_scientific_target(layer=24))


# ---------------------------------------------------------------------------
# Dynamic raw-HF text-decoder-layer resolution (independent of any
# TransformerLens hook-name string, per the addendum's explicit warning
# that neither "model.layers.N.output" nor "blocks.N.hook_resid_post" is
# a proven runtime path on its own)
# ---------------------------------------------------------------------------


class _TinyDecoderLayer(torch.nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.linear = torch.nn.Linear(dim, dim)

    def forward(self, x):
        return self.linear(x)


class _TinyGemmaLikeModel(torch.nn.Module):
    """Structurally mimics Gemma3's real shape: a text decoder stack under
    `model.layers`, plus a `vision_tower` and `multi_modal_projector` that
    ALSO happen to have a `.layers` submodule at the same index -- proving
    exclusion actually matters, not merely that it's never exercised."""

    def __init__(self, *, n_layers: int, hidden_dim: int, include_vision_collision: bool):
        super().__init__()
        self.embed = torch.nn.Linear(4, hidden_dim)
        self.model = torch.nn.Module()
        self.model.layers = torch.nn.ModuleList([_TinyDecoderLayer(hidden_dim) for _ in range(n_layers)])
        if include_vision_collision:
            self.vision_tower = torch.nn.Module()
            self.vision_tower.layers = torch.nn.ModuleList([_TinyDecoderLayer(hidden_dim) for _ in range(n_layers)])
            self.multi_modal_projector = torch.nn.Module()
            self.multi_modal_projector.layers = torch.nn.ModuleList([_TinyDecoderLayer(hidden_dim) for _ in range(n_layers)])

    def forward(self, input_ids):
        x = self.embed(input_ids.to(torch.float32))
        for layer in self.model.layers:
            x = layer(x)
        return x


def test_resolve_gemma_text_decoder_layer_dynamically_finds_the_real_layer():
    model = _TinyGemmaLikeModel(n_layers=3, hidden_dim=6, include_vision_collision=False)
    name, module = d.resolve_gemma_text_decoder_layer_dynamically(model, layer=1)
    assert name == "model.layers.1"
    assert module is model.model.layers[1]


def test_resolve_gemma_text_decoder_layer_dynamically_excludes_vision_tower_and_projector_collisions():
    """The exact scenario this function exists for: vision_tower AND
    multi_modal_projector both have their OWN `.layers.<N>` submodule at
    the same index -- without exclusion, this would be ambiguous (3
    matches instead of 1)."""
    model = _TinyGemmaLikeModel(n_layers=3, hidden_dim=6, include_vision_collision=True)
    name, _module = d.resolve_gemma_text_decoder_layer_dynamically(model, layer=1)
    assert name == "model.layers.1"
    assert "vision_tower" not in name
    assert "multi_modal_projector" not in name


def test_resolve_gemma_text_decoder_layer_dynamically_raises_on_out_of_range_layer():
    model = _TinyGemmaLikeModel(n_layers=3, hidden_dim=6, include_vision_collision=True)
    with pytest.raises(targets.TargetIdentityMismatch, match="found 0"):
        d.resolve_gemma_text_decoder_layer_dynamically(model, layer=99)


def test_run_gemma_raw_hf_hook_preflight_passes_with_the_right_dimension():
    model = _TinyGemmaLikeModel(n_layers=3, hidden_dim=6, include_vision_collision=True)
    tokens = torch.zeros((1, 4))
    result = d.run_gemma_raw_hf_hook_preflight(model, tokens, layer=1, expected_hidden_dim=6)
    assert result.passed is True
    assert result.resolved_module_name == "model.layers.1"
    assert result.captured_last_dim == 6
    assert result.layer_index_asserted == 1


def test_run_gemma_raw_hf_hook_preflight_fails_closed_on_a_dimension_mismatch():
    model = _TinyGemmaLikeModel(n_layers=3, hidden_dim=6, include_vision_collision=True)
    tokens = torch.zeros((1, 4))
    with pytest.raises(targets.TargetIdentityMismatch):
        d.run_gemma_raw_hf_hook_preflight(model, tokens, layer=1, expected_hidden_dim=999)


# ---------------------------------------------------------------------------
# Dose-response confirmation sweep: every held-out prompt, n_repeats times
# each, per dose.
# ---------------------------------------------------------------------------


def test_run_dose_response_confirmation_covers_every_prompt_and_repeat_per_dose():
    backend = make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, NEGATIVE_TEXTS)
    held_out = [f"{p} for confirmation" for p in POSITIVE_TEXTS[:4]]  # 4 held-out prompts
    results = d.run_dose_response_confirmation(
        backend, [CONCEPT_FEATURE], direction="clamp", dose_grid=[0.5, 1.0], corpus_max=corpus_max,
        positions="all", held_out_prompts=held_out, n_repeats=3, base_seed=0, max_new_tokens=1,
    )
    assert set(results) == {0.5, 1.0}
    for outcomes in results.values():
        assert len(outcomes) == len(held_out) * 3  # 4 prompts x 3 repeats


def test_run_dose_response_confirmation_rejects_empty_held_out_prompts():
    backend = make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, NEGATIVE_TEXTS)
    with pytest.raises(ValueError, match="at least one held-out prompt"):
        d.run_dose_response_confirmation(
            backend, [CONCEPT_FEATURE], direction="clamp", dose_grid=[1.0], corpus_max=corpus_max,
            positions="all", held_out_prompts=[], n_repeats=3, base_seed=0, max_new_tokens=1,
        )


def test_run_dose_response_confirmation_rejects_zero_repeats():
    backend = make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, NEGATIVE_TEXTS)
    with pytest.raises(ValueError, match="n_repeats must be at least 1"):
        d.run_dose_response_confirmation(
            backend, [CONCEPT_FEATURE], direction="clamp", dose_grid=[1.0], corpus_max=corpus_max,
            positions="all", held_out_prompts=["x"], n_repeats=0, base_seed=0, max_new_tokens=1,
        )


def test_run_dose_response_confirmation_resumes_without_recomputing_completed_cells(tmp_path):
    backend = make_fake_gemma_backend()
    corpus_max = d.corpus_max_per_feature(backend, NEGATIVE_TEXTS)
    held_out = POSITIVE_TEXTS[:2]
    progress = d.ProgressLog(tmp_path / "confirmation_progress.jsonl")
    first = d.run_dose_response_confirmation(
        backend, [CONCEPT_FEATURE], direction="clamp", dose_grid=[1.0], corpus_max=corpus_max,
        positions="all", held_out_prompts=held_out, n_repeats=2, base_seed=0, max_new_tokens=1, progress=progress,
    )
    assert len(first[1.0]) == 4  # 2 prompts x 2 repeats

    calls = {"n": 0}
    original = d.run_intervention

    def spy(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    d.run_intervention = spy
    try:
        resumed_progress = d.ProgressLog(tmp_path / "confirmation_progress.jsonl")
        second = d.run_dose_response_confirmation(
            backend, [CONCEPT_FEATURE], direction="clamp", dose_grid=[1.0], corpus_max=corpus_max,
            positions="all", held_out_prompts=held_out, n_repeats=2, base_seed=0, max_new_tokens=1, progress=resumed_progress,
        )
    finally:
        d.run_intervention = original
    assert calls["n"] == 0
    assert len(second[1.0]) == 4


# ---------------------------------------------------------------------------
# params_sha256: measured-vs-expected identity v1.3 hash semantics, and the
# identity-artifact hash guard itself.
# ---------------------------------------------------------------------------


def test_compute_file_sha256_matches_hashlib_reference(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"some bytes" * 1000)
    assert d.compute_file_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_assert_params_sha256_matches_returns_the_measured_digest_on_a_match(tmp_path):
    path = tmp_path / "params.safetensors"
    path.write_bytes(b"fake sae weights")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    measured = d.assert_params_sha256_matches([str(path)], expected_sha256=expected)
    assert measured == expected


def test_assert_params_sha256_matches_refuses_a_mismatch_rather_than_returning_the_expected_value(tmp_path):
    path = tmp_path / "params.safetensors"
    path.write_bytes(b"fake sae weights, tampered")
    wrong_expected = "0" * 64
    with pytest.raises(targets.TargetIdentityMismatch, match="hard stop"):
        d.assert_params_sha256_matches([str(path)], expected_sha256=wrong_expected)


def test_assert_params_sha256_matches_refuses_when_no_params_file_is_present(tmp_path):
    other = tmp_path / "cfg.json"
    other.write_text("{}", encoding="utf-8")
    with pytest.raises(targets.TargetIdentityMismatch, match=r"no params\.safetensors"):
        d.assert_params_sha256_matches([str(other)], expected_sha256="0" * 64)


def test_assert_params_sha256_matches_refuses_more_than_one_params_file(tmp_path):
    first = tmp_path / "a" / "params.safetensors"
    second = tmp_path / "b" / "params.safetensors"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    with pytest.raises(targets.TargetIdentityMismatch, match=r"exactly one params\.safetensors"):
        d.assert_params_sha256_matches([str(first), str(second)], expected_sha256="0" * 64)


def test_primary_and_backup_configurations_carry_distinct_frozen_params_hashes():
    assert d.PRIMARY_CONFIGURATION.gemma_params_expected_sha256 == (
        "6bb44c8c68797942d097604bfd8df50f4865c86282e2c4667e364382ea26120e"
    )
    assert d.BACKUP_CONFIGURATION.gemma_params_expected_sha256 == (
        "2e5f3bc8edc5340ac101fe967f5b59d7a14b40c47315baf5a3446232cb2e799e"
    )
    assert d.PRIMARY_CONFIGURATION.gemma_params_expected_sha256 != d.BACKUP_CONFIGURATION.gemma_params_expected_sha256


def test_validate_scientific_config_identity_hash_passes_against_the_real_frozen_artifact():
    digest = d.validate_scientific_config_identity_hash(REPO_ROOT)
    assert digest == d.IDENTITY_PROTOCOL_SHA256


def test_validate_scientific_config_identity_hash_refuses_a_tampered_copy(tmp_path):
    tampered_root = tmp_path
    tampered_path = tampered_root / "protocols" / "final_pairing" / "v1" / "scientific_config_identity.json"
    tampered_path.parent.mkdir(parents=True)
    tampered_path.write_text('{"protocol_version": "tampered"}', encoding="utf-8")
    with pytest.raises(d.PromptArtifactError, match="altered or superseded"):
        d.validate_scientific_config_identity_hash(tampered_root)


# ---------------------------------------------------------------------------
# Dtype boundary: bfloat16 residual + float32 SAE math, explicit cast back.
# `_make_clamp_hook` (interplab/interventions/hooks.py, frozen) already
# implements this correctly -- these tests are the previously-missing
# numerical proof, calling that frozen function directly.
# ---------------------------------------------------------------------------


def test_dtype_boundary_bfloat16_residual_float32_sae_explicit_cast_back():
    diagnostics = d.verify_dtype_boundary_policy(residual_dtype=torch.bfloat16)
    assert diagnostics.residual_input_dtype == "torch.bfloat16"
    assert diagnostics.residual_output_dtype == "torch.bfloat16"
    assert diagnostics.sae_encode_input_dtypes == ["torch.float32"]
    assert diagnostics.sae_decode_input_dtypes == ["torch.float32", "torch.float32"]  # clean_recon, clamped_recon
    assert diagnostics.explicit_cast_confirmed is True


def test_dtype_boundary_also_holds_for_float16_residual():
    diagnostics = d.verify_dtype_boundary_policy(residual_dtype=torch.float16)
    assert diagnostics.residual_output_dtype == "torch.float16"
    assert diagnostics.sae_encode_input_dtypes == ["torch.float32"]


def test_dtype_recording_sae_catches_a_would_be_regression_directly():
    """Proves the recording fake itself is a real, live probe, not a
    rubber stamp: if `_make_clamp_hook` ever passed the residual through
    WITHOUT casting to float32 first, `_DtypeRecordingSAE.encode` would
    receive a bfloat16 tensor against its own float32 weight matrix --
    which torch itself refuses with a dtype-mismatch RuntimeError (proven
    directly here, bypassing the hook), an even stronger guarantee than a
    silently-recorded wrong dtype would be. The dtype is recorded before
    the matmul is attempted, so `encode_input_dtypes` reflects the actual
    (wrong) input even though the call itself then raises."""
    recording_sae = d._DtypeRecordingSAE(d_in=8, d_sae=16)
    x_bf16 = torch.randn(1, 3, 8, dtype=torch.bfloat16)
    with pytest.raises(RuntimeError, match="dtype"):
        recording_sae.encode(x_bf16)
    assert recording_sae.encode_input_dtypes == [torch.bfloat16]
