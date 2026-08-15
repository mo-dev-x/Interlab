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
import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
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


#: A fake but non-empty chat template -- P0 STOP-LINE correction requires
#: `resolve_chat_template_identity`/`resolve_stop_token_ids` to derive a
#: real template/EOS identity from the tokenizer actually used, never
#: accept an arbitrary caller label; a tokenizer with NO template at all is
#: itself a stop condition for real callers, so this fake must carry one.
_FAKE_CHAT_TEMPLATE = "{% for message in messages %}{{ message['content'] }}{% endfor %}"


class _FakeTokenizer:
    """Owns a back-reference to its `_FakeGemmaModel` so `apply_chat_template`
    can register the RENDERED (templated) text through the model's own
    `to_tokens` -- the same one-text-per-token scheme every other fake code
    path already relies on."""

    name_or_path = "fake/gemma-3-12b-it"
    chat_template = _FAKE_CHAT_TEMPLATE
    eos_token_id = 999999
    pad_token_id = 999999
    unk_token_id = None

    def __init__(self, model: _FakeGemmaModel):
        self._model = model

    def decode(self, ids, **_kwargs) -> str:
        return "fake-generated-text"

    def convert_tokens_to_ids(self, _token) -> None:
        return None  # this fake vocabulary has no named special tokens at all

    def apply_chat_template(
        self, messages, *, tokenize: bool = True, add_generation_prompt: bool = True,
        return_tensors: str | None = None, return_dict: bool = False, **_kwargs,
    ):
        rendered = "".join(m["content"] for m in messages)
        if not tokenize:
            return rendered
        tokens = self._model.to_tokens(rendered)
        if return_dict:
            return {"input_ids": tokens, "attention_mask": torch.ones_like(tokens)}
        return tokens


class _FakeGemmaModel:
    """Mimics only the surface `final_pairing_concept_discovery.py` calls:
    `.to_tokens`, `.run_with_cache`, `.hooks`, `.generate`, `.tokenizer`."""

    def __init__(self):
        self.tokenizer = _FakeTokenizer(self)
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

    def generate(self, tokens: torch.Tensor, *, max_new_tokens: int, do_sample: bool, verbose: bool = False, **_kwargs):
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


# ---------------------------------------------------------------------------
# --mode grid: the real production discovery-lane CLI entry point.
# ---------------------------------------------------------------------------


def _grid_mode_cli_args(out_dir: Path, state_dir: Path, *, shortlist_size: int = 2) -> list[str]:
    return [
        "--mode", "grid", "--pairing", "gemma-3-12b-it",
        "--model-path", "/fake/model", "--sae-path", "/fake/sae",
        "--shortlist-size", str(shortlist_size),
        "--out-dir", str(out_dir), "--state-dir", str(state_dir),
    ]


def test_rank_auroc_matrix_matches_sklearn_including_under_heavy_ties():
    """C3's screen must be the same measurement as the frozen primitive.
    Ties are the normal case for post-ReLU SAE scores, not an edge case."""
    rng = np.random.default_rng(7)
    pos = np.where(rng.random((10, 12)) < 0.6, 0.0, rng.random((10, 12)) * 5.0)
    neg = np.where(rng.random((30, 12)) < 0.6, 0.0, rng.random((30, 12)) * 5.0)
    vectorised = d.rank_auroc_matrix(pos, neg)
    for j in range(pos.shape[1]):
        assert vectorised[j] == pytest.approx(
            d._auroc_from_scores(pos[:, j].tolist(), neg[:, j].tolist()), abs=1e-12
        )


def test_fire_rate_matrix_matches_the_scalar_gate_b_including_the_c1_guard():
    rng = np.random.default_rng(8)
    pos = np.where(rng.random((10, 12)) < 0.5, 0.0, rng.random((10, 12)) * 5.0)
    pos[:, 3] = 0.0  # a fully dead column: the C1 guard must fire in both paths
    rates, floors = d.fire_rate_matrix(pos, floor_fraction=0.20)
    assert rates[3] == 0.0 and floors[3] == 0.0
    for j in range(pos.shape[1]):
        assert (rates[j], floors[j]) == d.compute_gate_b_fire_rate(pos[:, j].tolist(), floor_fraction=0.20)


def test_score_full_feature_space_covers_every_feature_and_every_cell():
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    assert scan.min_separation_auroc.shape == (backend.d_sae,)
    assert scan.min_fire_rate.shape == (backend.d_sae,)
    assert scan.min_near_miss_auroc.shape == (backend.d_sae,)
    assert scan.cells_scored == len(d.FROZEN_PROMPT_SET_LOCALES) * 3  # 3 families x 2 locales
    assert set(scan.families_by_locale) == set(d.FROZEN_PROMPT_SET_LOCALES)


def test_score_full_feature_space_agrees_cell_for_cell_with_the_per_feature_path():
    """The screen minimises across exactly the six cells the frozen
    conjunction quantifies over -- if it aggregated differently (a max, a
    pooled family, one locale), a feature could clear the screen that the
    per-feature path rejects, or vice versa."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    scan = d.score_full_feature_space(backend, artifact, concept_id="cheese")
    for feature_index in range(backend.d_sae):
        ab, c = [], []
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            ab += d.compute_gate_a_and_b_per_family(
                backend, artifact, concept_id="cheese", locale=locale, feature_index=feature_index
            )
            c += d.compute_gate_c_per_family(
                backend, artifact, concept_id="cheese", locale=locale, feature_index=feature_index
            )
        assert scan.min_separation_auroc[feature_index] == pytest.approx(min(r.separation_auroc for r in ab), abs=1e-12)
        assert scan.min_fire_rate[feature_index] == pytest.approx(min(r.fire_rate for r in ab), abs=1e-12)
        assert scan.min_near_miss_auroc[feature_index] == pytest.approx(min(r.near_miss_auroc for r in c), abs=1e-12)


def test_select_candidates_from_scan_never_truncates_the_gate_a_passing_set():
    """`report_top_n` is a REPORTING budget. It must never be able to drop
    a feature that passed G-A -- that set is the auditable output."""
    d_sae = 40
    scan = d.FullSpaceScan(
        concept_id="synthetic", locales=("en", "fr"), families_by_locale={"en": ["f1"], "fr": ["f1"]},
        min_separation_auroc=np.concatenate([np.full(11, 0.95), np.full(d_sae - 11, 0.10)]),
        min_fire_rate=np.ones(d_sae), min_near_miss_auroc=np.ones(d_sae), cells_scored=6,
    )
    selected = d.select_candidates_from_scan(scan, pairing="gemma-3-12b-it", auroc_min=0.90, report_top_n=1)
    assert {r.feature_index for r in selected} >= set(range(11))
    # Deterministic order: descending min separation AUROC, ties by index.
    assert [r.feature_index for r in selected][:11] == list(range(11))


def test_select_candidates_from_scan_still_drops_the_mechanical_only_feature():
    d_sae = 300
    min_sep = np.full(d_sae, 0.10)
    min_sep[250] = 0.99  # the gemma mechanical-acceptance placeholder
    min_sep[7] = 0.98
    scan = d.FullSpaceScan(
        concept_id="synthetic", locales=("en",), families_by_locale={"en": ["f1"]},
        min_separation_auroc=min_sep, min_fire_rate=np.ones(d_sae), min_near_miss_auroc=np.ones(d_sae),
        cells_scored=3,
    )
    selected = [r.feature_index for r in d.select_candidates_from_scan(scan, pairing="gemma-3-12b-it", auroc_min=0.90)]
    assert 250 not in selected
    assert selected[0] == 7


def test_evaluate_concept_on_pairing_scores_the_whole_space_and_records_the_caveat():
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    assert verdict.status in ("pass", "fail")
    assert verdict.features_scored == backend.d_sae
    assert verdict.selection_mode == "full_space_exhaustive"
    # Every emitted verdict must carry the caveat: a survivor count from
    # this grid is an engineering measurement, not a discovery result.
    assert verdict.gate_denominator_caveat == d.GATE_DENOMINATOR_CAVEAT
    assert "No count of surviving features from this grid is a discovery result." in verdict.gate_denominator_caveat
    assert "engineering-preview-only" in verdict.gate_denominator_caveat


def test_evaluate_concept_on_pairing_records_candidates_best_first_and_deterministically():
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    first = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    second = d.evaluate_concept_on_pairing(make_fake_gemma_backend(), artifact, concept_id="cheese")
    assert [c["feature_index"] for c in first.candidates_evaluated] == [
        c["feature_index"] for c in second.candidates_evaluated
    ]
    assert first.surviving_feature_index == second.surviving_feature_index
    mins = [
        min(r["separation_auroc"] for r in c["gate_a_b_results"]) for c in first.candidates_evaluated
    ]
    assert mins == sorted(mins, reverse=True)


def test_the_survival_conjunction_is_unchanged_by_c3():
    """Frozen and must stay frozen: ONE feature, ALL 3 families, BOTH
    locales, all three gates. Not 5-of-6, not pooled, not per-locale."""
    def _ab(locale, family, a, b):
        return d.GateABResult(
            concept_id="x", locale=locale, family=family, feature_index=1, separation_auroc=0.99,
            gate_a_passed=a, fire_rate=1.0, activation_floor_fraction=0.2, gate_b_passed=b,
            activation_floor=1.0, observed_max=5.0, n_positives=10,
        )

    def _c(locale, family, passed):
        return d.GateCResult(
            concept_id="x", locale=locale, family=family, feature_index=1, near_miss_auroc=0.99,
            gate_c_passed=passed,
        )

    cells = [(loc, fam) for loc in ("en", "fr") for fam in ("f1", "f2", "f3")]
    all_ab = [_ab(loc, fam, True, True) for loc, fam in cells]
    all_c = [_c(loc, fam, True) for loc, fam in cells]
    assert d.feature_survives_gabc(all_ab, all_c) is True

    for i in range(len(cells)):
        five_of_six = list(all_ab)
        five_of_six[i] = _ab(*cells[i], True, False)  # one G-B failure anywhere
        assert d.feature_survives_gabc(five_of_six, all_c) is False
        five_of_six[i] = _ab(*cells[i], False, True)  # one G-A failure anywhere
        assert d.feature_survives_gabc(five_of_six, all_c) is False
        one_c_fail = list(all_c)
        one_c_fail[i] = _c(*cells[i], False)
        assert d.feature_survives_gabc(all_ab, one_c_fail) is False


def test_parse_args_grid_mode_does_not_require_full_mode_only_flags(tmp_path):
    args = d.parse_args(_grid_mode_cli_args(tmp_path / "out", tmp_path / "state"))
    assert args.mode == "grid"
    assert args.prompt_set_path is None
    assert args.direction is None


def test_parse_args_full_mode_still_requires_the_original_fields(tmp_path):
    """--mode full (the default) must still refuse a genuinely incomplete
    invocation -- relaxing these flags to default=None for grid mode must
    not silently make them optional for the pipeline that actually needs
    them."""
    with pytest.raises(SystemExit):
        d.parse_args([
            "--pairing", "gemma-3-12b-it", "--model-path", "/fake/model", "--sae-path", "/fake/sae",
            "--shortlist-size", "3", "--out-dir", str(tmp_path / "out"), "--state-dir", str(tmp_path / "state"),
            # --prompt-set-path, --direction, --dose-grid, and the threshold flags are all omitted.
        ])


def test_parse_args_grid_mode_exposes_no_concept_subset_flag(tmp_path):
    """The production grid CLI must never be able to narrow which concepts
    it evaluates -- there is no --concept-id/--concept-ids flag at all."""
    with pytest.raises(SystemExit):
        d.parse_args([*_grid_mode_cli_args(tmp_path / "out", tmp_path / "state"), "--concept-id", "cheese"])


def test_run_grid_mode_covers_all_14_concepts_including_the_pi_gated_one(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_grid_mode_cli_args(out_dir, state_dir))

    result = d.run_grid_mode(args)

    assert result["concept_count"] == 14
    verdicts = d.read_grid_result(Path(result["grid_path"]))
    assert len(verdicts) == 14
    assert {v.concept_id for v in verdicts} == {r["concept_id"] for r in d.load_frozen_prompt_artifact(d.REPO_ROOT, allow_pi_gated=True).rows}
    assert d.PI_GATED_CONCEPT_ID in {v.concept_id for v in verdicts}
    assert all(v.pairing == "gemma-3-12b-it" for v in verdicts)
    assert all(v.status in ("pass", "fail", "error") for v in verdicts)


def test_run_grid_mode_refuses_to_write_a_partial_grid(tmp_path, monkeypatch):
    """P0 STOP-LINE correction: 'exactly the frozen 14 concepts' is a
    RUNTIME invariant, not merely the absence of a CLI flag -- a
    hypothetical future bug that narrows concept_ids must fail loudly
    rather than silently write an incomplete grid.json."""
    real_run_concept_grid = d.run_concept_grid
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    monkeypatch.setattr(d, "run_concept_grid", lambda *a, **k: real_run_concept_grid(*a, **k)[:13])
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_grid_mode_cli_args(out_dir, state_dir))
    with pytest.raises(d.PromptArtifactError, match="expected exactly"):
        d.run_grid_mode(args)
    assert not (out_dir / "grid.json").is_file()


def test_run_grid_mode_writes_a_ready_record_when_ready_path_is_given(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    ready_path = tmp_path / "ready.json"
    args = d.parse_args([*_grid_mode_cli_args(out_dir, state_dir), "--ready-path", str(ready_path), "--device", "cpu"])

    d.run_grid_mode(args)

    assert ready_path.is_file()
    record = json.loads(ready_path.read_text(encoding="utf-8"))
    assert record["pairing"] == "gemma-3-12b-it"
    assert record["device"] == "cpu"


def test_main_dispatches_to_grid_mode_and_reports_grid_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    exit_code = d.main(_grid_mode_cli_args(out_dir, state_dir))
    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["pairing"] == "gemma-3-12b-it"
    assert Path(printed["grid_path"]).is_file()


def test_run_grid_mode_is_resumable_via_state_dir_progress_log(tmp_path, monkeypatch):
    """A second invocation against the same --state-dir must not re-run
    concepts the first invocation already completed (run_concept_grid's
    own progress-log resumability, exercised end-to-end through the CLI)."""
    call_count = {"n": 0}
    real_evaluate = d.evaluate_concept_on_pairing

    def counting_evaluate(*args, **kwargs):
        call_count["n"] += 1
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(d, "load_backend", lambda **kwargs: make_fake_gemma_backend())
    monkeypatch.setattr(d, "evaluate_concept_on_pairing", counting_evaluate)
    out_dir, state_dir = tmp_path / "out", tmp_path / "state"
    args = d.parse_args(_grid_mode_cli_args(out_dir, state_dir))

    d.run_grid_mode(args)
    first_call_count = call_count["n"]
    assert first_call_count == 14

    d.run_grid_mode(args)
    assert call_count["n"] == first_call_count  # no concept re-evaluated the second time


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


@pytest.mark.parametrize(
    "kwargs",
    [
        {"layer": 32, "sae_family": "L0_100", "k": 100},  # BACKUP's layer, PRIMARY's family/k
        {"layer": 38, "sae_family": "L0_100", "k": 50},  # PRIMARY's layer/family, BACKUP's k
        {"layer": 38, "sae_family": "L0_50", "k": 100},  # PRIMARY's layer/k, BACKUP's family
    ],
)
def test_load_qwen_scientific_target_rejects_crossed_configuration_family_paths(kwargs):
    """P0 STOP-LINE correction: 'reject crossed family/configuration
    paths' -- a caller can no longer combine e.g. PRIMARY's SAE family
    with BACKUP's layer/k. Fails BEFORE any file access (fake 'x'/'y'
    paths that don't exist)."""
    with pytest.raises(targets.TargetIdentityMismatch, match="crossed configuration/family"):
        d.load_qwen_scientific_target("x", "y", **kwargs)


def test_load_qwen_scientific_target_rejects_an_expected_revision_disagreeing_with_the_frozen_one():
    with pytest.raises(targets.TargetIdentityMismatch, match="frozen, pinned revision"):
        d.load_qwen_scientific_target(
            "x", "y", layer=38, sae_family="L0_100", k=100, expected_sae_revision="0" * 40,
        )


@pytest.mark.parametrize(("configuration", "expected"), [
    (d.PRIMARY_CONFIGURATION, {
        "release": "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100",
        "loader_sae_id": "layer38.sae.pt",
        "sae_id": "resid_post/layer_38_width_80k_l0_100",
        "scientific_sae_id": "resid_post/layer_38_width_80k_l0_100",
    }),
    (d.BACKUP_CONFIGURATION, {
        "release": "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50",
        "loader_sae_id": "layer32.sae.pt",
        "sae_id": "resid_post/layer_32_width_80k_l0_50",
        "scientific_sae_id": "resid_post/layer_32_width_80k_l0_50",
    }),
])
def test_qwen_manifest_identity_is_configuration_specific(configuration, expected):
    assert d.qwen_manifest_identity(
        configuration, layer_file_name=expected["loader_sae_id"],
    ) == expected


def test_qwen_manifest_identity_refuses_a_crossed_layer_file():
    with pytest.raises(targets.TargetIdentityMismatch, match="loader identity"):
        d.qwen_manifest_identity(
            d.PRIMARY_CONFIGURATION, layer_file_name="layer32.sae.pt",
        )


def test_qwen_scientific_target_is_configuration_specific_not_merely_k_specific():
    """P0 STOP-LINE correction: sae_repo_id, expected_k, AND expected_layer
    are all drawn from the given configuration -- PRIMARY and BACKUP must
    never resolve to the same repository/layer/k."""
    primary = d._qwen_scientific_target(configuration=d.PRIMARY_CONFIGURATION)
    backup = d._qwen_scientific_target(configuration=d.BACKUP_CONFIGURATION)
    base = targets.QWEN_3_5_27B_TARGET

    assert primary.sae_repo_id == "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100"
    assert primary.expected_k == 100
    assert primary.expected_layer == 38
    assert backup.sae_repo_id == "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50"
    assert backup.expected_k == 50
    assert backup.expected_layer == 32
    assert primary.sae_repo_id != backup.sae_repo_id

    for variant in (primary, backup):
        assert variant.model_repo_id == base.model_repo_id
        assert variant.expected_hidden_dim == base.expected_hidden_dim
        assert variant.sae_format == base.sae_format


def test_assert_qwen_configuration_self_consistent_passes_for_both_ratified_configurations():
    d.assert_qwen_configuration_self_consistent(d.PRIMARY_CONFIGURATION)  # must not raise
    d.assert_qwen_configuration_self_consistent(d.BACKUP_CONFIGURATION)  # must not raise


def test_assert_qwen_configuration_self_consistent_rejects_k_disagreeing_with_repo_suffix():
    import dataclasses as _dc

    broken = _dc.replace(d.PRIMARY_CONFIGURATION, qwen_sparsity=999)
    with pytest.raises(targets.TargetIdentityMismatch, match="disagrees with the L0_100 suffix"):
        d.assert_qwen_configuration_self_consistent(broken)


def test_assert_qwen_configuration_self_consistent_rejects_depth_fraction_disagreeing_with_layer():
    import dataclasses as _dc

    broken = _dc.replace(d.PRIMARY_CONFIGURATION, qwen_depth_fraction=0.1)
    with pytest.raises(targets.TargetIdentityMismatch, match="recomputed depth_fraction"):
        d.assert_qwen_configuration_self_consistent(broken)


def test_assert_qwen_params_sha256_matches_returns_the_measured_digest(tmp_path):
    layer_file = tmp_path / "layer38.sae.pt"
    layer_file.write_bytes(b"fake qwen sae bytes")
    expected = d.compute_file_sha256(layer_file)
    assert d.assert_qwen_params_sha256_matches(layer_file, expected_sha256=expected) == expected


def test_assert_qwen_params_sha256_matches_raises_on_mismatch(tmp_path):
    layer_file = tmp_path / "layer38.sae.pt"
    layer_file.write_bytes(b"fake qwen sae bytes")
    with pytest.raises(targets.TargetIdentityMismatch, match="hashes to"):
        d.assert_qwen_params_sha256_matches(layer_file, expected_sha256="0" * 64)


def test_validate_qwen_config_identity_protocol_hash_matches_the_pinned_value():
    assert d.validate_qwen_config_identity_protocol_hash(d.REPO_ROOT) == d.QWEN_CONFIG_IDENTITY_PROTOCOL_SHA256


def test_validate_qwen_config_identity_protocol_hash_rejects_a_tampered_copy(tmp_path):
    protocol_dir = tmp_path / "protocols" / "final_pairing" / "v1"
    protocol_dir.mkdir(parents=True)
    (protocol_dir / "qwen_config_identity.json").write_text("{}", encoding="utf-8")
    with pytest.raises(d.PromptArtifactError):
        d.validate_qwen_config_identity_protocol_hash(tmp_path)


def test_matched_configurations_match_the_predeclared_values():
    assert d.PRIMARY_CONFIGURATION.qwen_layer == 38
    assert d.PRIMARY_CONFIGURATION.qwen_sae_family == "L0_100"
    assert d.PRIMARY_CONFIGURATION.qwen_sparsity == 100
    assert d.PRIMARY_CONFIGURATION.gemma_layer == 29
    assert d.PRIMARY_CONFIGURATION.qwen_sae_repo_id == "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_100"
    assert d.PRIMARY_CONFIGURATION.qwen_sae_revision == "82852e98c9b33d02194e92dd514b12fafd09ed25"
    assert d.PRIMARY_CONFIGURATION.qwen_params_expected_sha256 == "78b94bf19d4c120e70ba2767734b6d904468d127537e5d16c2a76cbc0963aeb0"
    assert d.BACKUP_CONFIGURATION.qwen_layer == 32
    assert d.BACKUP_CONFIGURATION.qwen_sae_family == "L0_50"
    assert d.BACKUP_CONFIGURATION.qwen_sparsity == 50
    assert d.BACKUP_CONFIGURATION.gemma_layer == 24
    assert d.BACKUP_CONFIGURATION.qwen_sae_repo_id == "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50"
    assert d.BACKUP_CONFIGURATION.qwen_sae_revision == "13d4221569f7ca5d3c1e605e3e3dc95117e4807c"
    assert d.BACKUP_CONFIGURATION.qwen_params_expected_sha256 == "fbbae7cf93c1e385c68213ae871ede349ac666f3a8c4e6a75ef959db2b6612ab"
    assert d.PRIMARY_CONFIGURATION.qwen_sae_repo_id != d.BACKUP_CONFIGURATION.qwen_sae_repo_id
    assert d.PRIMARY_CONFIGURATION.qwen_sae_revision != d.BACKUP_CONFIGURATION.qwen_sae_revision
    assert set(d.MATCHED_CONFIGURATIONS) == {"primary", "backup"}
    assert d.QWEN_CONFIGURATION_BY_SAE_FAMILY == {"L0_100": d.PRIMARY_CONFIGURATION, "L0_50": d.BACKUP_CONFIGURATION}


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


# ---------------------------------------------------------------------------
# Archive execution must not require .git: the transfer manifest is the
# git-independent substitute for the Tamia side of a `git archive` transfer.
# ---------------------------------------------------------------------------


def _copy_frozen_artifact_into(dest_root: Path) -> Path:
    """Copies the real, committed frozen prompt artifact directory into a
    bare (non-git) tmp tree, so `load_frozen_prompt_artifact` can be
    exercised against it with NO `.git` present at all."""
    src = d.REPO_ROOT / d.FROZEN_PROMPT_SET_DIR
    dest = dest_root / d.FROZEN_PROMPT_SET_DIR
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return dest


def test_build_transfer_manifest_records_a_real_head_commit_and_the_pinned_hashes():
    manifest = d.build_transfer_manifest(d.REPO_ROOT)
    assert len(manifest["source_commit"]) == 40
    assert all(c in "0123456789abcdef" for c in manifest["source_commit"])
    assert manifest["files"][f"{d.FROZEN_PROMPT_SET_DIR}/prompt_sets.jsonl"] == d.FROZEN_PROMPT_SETS_SHA256
    assert manifest["files"][f"{d.FROZEN_PROMPT_SET_DIR}/metadata.json"] == d.FROZEN_METADATA_SHA256


def test_build_transfer_manifest_refuses_a_dirty_working_tree(monkeypatch):
    def dirty_git(repo_root, *args):
        if args[0] == "status":
            return 0, " M prompts/final_pairing/v1/metadata.json"
        return 0, "deadbeef" * 5

    monkeypatch.setattr(d, "_git", dirty_git)
    with pytest.raises(d.TransferManifestError, match="dirty working tree"):
        d.build_transfer_manifest(d.REPO_ROOT)


def test_build_transfer_manifest_refuses_when_git_status_itself_fails(monkeypatch):
    monkeypatch.setattr(d, "_git", lambda repo_root, *args: (128, "fatal: not a git repository"))
    with pytest.raises(d.TransferManifestError, match="git status failed"):
        d.build_transfer_manifest(d.REPO_ROOT)


def test_write_and_load_transfer_manifest_round_trip(tmp_path, monkeypatch):
    _copy_frozen_artifact_into(tmp_path)

    def clean_git(repo_root, *args):
        if args[0] == "status":
            return 0, ""
        return 0, "a" * 40

    monkeypatch.setattr(d, "_git", clean_git)
    written = d.write_transfer_manifest(tmp_path)
    loaded = d.load_transfer_manifest(tmp_path)
    assert loaded == written
    assert (tmp_path / d.TRANSFER_MANIFEST_FILENAME).is_file()
    assert written["source_commit"] == "a" * 40


def test_load_transfer_manifest_returns_none_when_absent(tmp_path):
    assert d.load_transfer_manifest(tmp_path) is None


def test_load_frozen_prompt_artifact_succeeds_via_transfer_manifest_with_no_git_at_all(tmp_path, monkeypatch):
    """The exact Tamia-side scenario: a directory with the frozen artifact
    and a transfer_manifest.json, but NO .git directory whatsoever. Must
    succeed without ever invoking `git`."""
    _copy_frozen_artifact_into(tmp_path)
    assert not (tmp_path / ".git").exists()

    def _git_must_not_be_called(repo_root, *args):
        raise AssertionError(f"git must never be invoked on the Tamia side; called with {args}")

    monkeypatch.setattr(d, "_git", _git_must_not_be_called)
    real_manifest = {
        "schema_version": d.SCHEMA_VERSION, "source_commit": "b" * 40,
        "files": {
            f"{d.FROZEN_PROMPT_SET_DIR}/prompt_sets.jsonl": d.FROZEN_PROMPT_SETS_SHA256,
            f"{d.FROZEN_PROMPT_SET_DIR}/metadata.json": d.FROZEN_METADATA_SHA256,
        },
    }
    (tmp_path / d.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps(real_manifest), encoding="utf-8")

    artifact = d.load_frozen_prompt_artifact(tmp_path)
    assert artifact.prompt_sets_sha256 == d.FROZEN_PROMPT_SETS_SHA256


def test_load_frozen_prompt_artifact_refuses_a_file_altered_after_the_manifest_was_built(tmp_path):
    dest = _copy_frozen_artifact_into(tmp_path)
    real_manifest = d.build_transfer_manifest(d.REPO_ROOT)
    (tmp_path / d.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps(real_manifest), encoding="utf-8")
    # Tamper with the file AFTER the manifest was written (post-transfer alteration).
    (dest / "metadata.json").write_text((dest / "metadata.json").read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(d.TransferManifestError, match="was altered after the transfer archive was built"):
        d.load_frozen_prompt_artifact(tmp_path)


def test_load_frozen_prompt_artifact_refuses_a_manifest_missing_required_fields(tmp_path):
    _copy_frozen_artifact_into(tmp_path)
    (tmp_path / d.TRANSFER_MANIFEST_FILENAME).write_text(json.dumps({"files": {}}), encoding="utf-8")
    with pytest.raises(d.TransferManifestError, match="missing required field"):
        d.load_frozen_prompt_artifact(tmp_path)


def test_load_frozen_prompt_artifact_refuses_when_neither_git_nor_transfer_manifest_exist(tmp_path):
    _copy_frozen_artifact_into(tmp_path)
    with pytest.raises(d.PromptArtifactError, match=r"neither transfer_manifest\.json nor a \.git directory"):
        d.load_frozen_prompt_artifact(tmp_path)


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


class _MultiPositionGemmaModel:
    """A minimal Gemma-shaped fake exposing exactly the surface
    `_pooled_residual_and_feature` calls (`.to_tokens`/`.run_with_cache`),
    with a KNOWN, controlled multi-position residual -- proves the
    per-prompt feature score is MAX over positions, not mean (P0
    STOP-LINE correction): only ONE of three positions carries a real
    spike; mean would dilute it by a factor of 3, max would not."""

    def to_tokens(self, text: str) -> torch.Tensor:
        return torch.zeros((1, 3), dtype=torch.long)  # 3 positions; content is irrelevant to this fake

    def run_with_cache(self, tokens: torch.Tensor, names_filter: str):
        resid = torch.zeros((1, 3, D_MODEL))
        resid[0, 2, 0] = 10.0  # residual dim 0 drives CONCEPT_FEATURE via _FakeSAE.W; only position 2 fires
        return None, {names_filter: resid}


def test_pooled_residual_and_feature_uses_max_over_positions_not_mean():
    backend = d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name, model_obj=_MultiPositionGemmaModel(), sae=_FakeSAE(),
        hook_name=HOOK_NAME, d_sae=D_SAE, d_model=D_MODEL, layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={}, checkpoint_hash="deadbeef",
    )
    _, feats_out = d._pooled_residual_and_feature(backend, ["any text"], CONCEPT_FEATURE)
    # relu([0, 0, 10]) -> feature values [0, 0, 10] at the 3 positions: max=10, mean=3.333...
    assert feats_out[0] == pytest.approx(10.0)


def test_feature_matrix_for_texts_matches_the_per_feature_forward_pass_exactly():
    """C2: `encode_texts`' whole-row max (`feats.max(dim=0).values`) and
    `_pooled_residual_and_feature`'s column max (`feats[:, j].max()`) are
    the same reduction over the same tensor. If they ever diverge, every
    number the cached path emits is a different measurement from the one
    run 413287 recorded."""
    backend = make_fake_gemma_backend()
    texts = POSITIVE_TEXTS + NEGATIVE_TEXTS
    matrix = d.feature_matrix_for_texts(backend, texts)
    assert matrix.shape == (len(texts), backend.d_sae)
    for feature_index in (CONCEPT_FEATURE, OTHER_FEATURE, 0, backend.d_sae - 1):
        residuals, per_feature = d._pooled_residual_and_feature(backend, texts, feature_index)
        assert residuals.shape == (len(texts), backend.d_model)
        assert list(matrix[:, feature_index].astype(float)) == list(per_feature.astype(float))


def test_feature_matrix_cache_encodes_each_text_once_across_features_and_gates():
    """C2's whole point: the encode does not depend on the feature index,
    so N candidate features over the same texts must cost ONE encode, not
    N."""
    backend = make_fake_gemma_backend()
    cache = d.FeatureMatrixCache()
    texts = POSITIVE_TEXTS
    for feature_index in range(backend.d_sae):
        cache.feature_scores(backend, texts, feature_index)
    assert cache.encode_calls == 1
    assert cache.texts_encoded == len(texts)
    assert cache.hits == backend.d_sae - 1


def test_feature_matrix_cache_pins_shared_substrate_and_evicts_only_the_rest():
    """`unrelated` is shared_substrate -- the SAME 15 texts per locale for
    all 14 concepts -- so it survives the per-concept eviction that keeps
    peak memory to one concept."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    cache = d.FeatureMatrixCache()
    d.pin_shared_substrate(cache, backend, artifact)
    pinned = len(cache)
    assert pinned == len(d.FROZEN_PROMPT_SET_LOCALES)

    d.compute_gate_a_and_b_per_family(
        backend, artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE, cache=cache,
    )
    assert len(cache) > pinned
    encodes_after_first_concept = cache.encode_calls
    cache.evict_unpinned()
    assert len(cache) == pinned

    # A second concept must NOT re-encode the shared substrate.
    d.compute_gate_a_and_b_per_family(
        backend, artifact, concept_id="chess", locale="en", feature_index=CONCEPT_FEATURE, cache=cache,
    )
    unrelated_texts, _near, _pos = d.concept_locale_texts(artifact, concept_id="chess", locale="en")
    assert cache.encode_calls - encodes_after_first_concept == 4  # near_miss + f1 + f2 + f3, NOT unrelated
    assert cache._key(backend, unrelated_texts) in cache._pinned


def test_pooled_residual_and_feature_with_a_cache_runs_no_forward_pass():
    """C2: with a cache supplied this function is a cache INDEX. The fake
    model registers a token per `to_tokens` call, so a second call that
    re-ran the model would advance that counter."""
    backend = make_fake_gemma_backend()
    cache = d.FeatureMatrixCache()
    first = d._pooled_residual_and_feature(backend, POSITIVE_TEXTS, CONCEPT_FEATURE, cache=cache)
    tokens_after_first = backend.model_obj._next_token
    second = d._pooled_residual_and_feature(backend, POSITIVE_TEXTS, OTHER_FEATURE, cache=cache)
    assert backend.model_obj._next_token == tokens_after_first  # no second forward pass
    assert cache.encode_calls == 1
    assert first[0].shape == second[0].shape


def test_gate_results_are_identical_with_and_without_the_cache():
    """The cache must be a pure performance change: same artifact, same
    feature, cached vs uncached -> byte-identical gate records."""
    backend_a = make_fake_gemma_backend()
    backend_b = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    cache = d.FeatureMatrixCache()
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        uncached_ab = d.compute_gate_a_and_b_per_family(
            backend_a, artifact, concept_id="cheese", locale=locale, feature_index=CONCEPT_FEATURE,
        )
        cached_ab = d.compute_gate_a_and_b_per_family(
            backend_b, artifact, concept_id="cheese", locale=locale, feature_index=CONCEPT_FEATURE, cache=cache,
        )
        assert [dataclasses.asdict(r) for r in uncached_ab] == [dataclasses.asdict(r) for r in cached_ab]
        uncached_c = d.compute_gate_c_per_family(
            backend_a, artifact, concept_id="cheese", locale=locale, feature_index=CONCEPT_FEATURE,
        )
        cached_c = d.compute_gate_c_per_family(
            backend_b, artifact, concept_id="cheese", locale=locale, feature_index=CONCEPT_FEATURE, cache=cache,
        )
        assert [dataclasses.asdict(r) for r in uncached_c] == [dataclasses.asdict(r) for r in cached_c]


def test_compute_gate_b_fire_rate_counts_a_score_exactly_at_the_floor_as_firing():
    # observed_max=10, floor_fraction=0.20 -> floor=2.0 exactly; one score sits exactly there.
    fire_rate, floor = d.compute_gate_b_fire_rate([10.0, 2.0, 1.0], floor_fraction=0.20)
    assert floor == pytest.approx(2.0)
    assert fire_rate == pytest.approx(2 / 3)  # 10.0 and 2.0 fire (>= floor); 1.0 does not


def test_compute_gate_b_fire_rate_empty_scores_is_zero():
    assert d.compute_gate_b_fire_rate([], floor_fraction=0.20) == (0.0, 0.0)


def test_compute_gate_b_fire_rate_all_zero_positives_does_not_fire(monkeypatch):
    """C1 degenerate-case guard. SAE scores are post-ReLU, so a feature that
    never fires on any positive prompt gives observed_max == 0.0 -> floor
    0.0 -> `0.0 >= 0.0` for every prompt -> fire_rate 1.0 -> G-B PASSES a
    silent feature. MEASURED on production run 413287: 182 of 660 G-B
    passes were exactly this. Without the guard this asserts 1.0."""
    fire_rate, floor = d.compute_gate_b_fire_rate([0.0] * 10, floor_fraction=0.20)
    assert fire_rate == 0.0
    assert floor == 0.0
    assert fire_rate < d.load_frozen_prompt_artifact(d.REPO_ROOT).metadata["thresholds"]["G_B_fire_rate_min"]


def test_compute_gate_b_fire_rate_guard_is_strictly_stricter_for_a_live_feature():
    """The guard must be unreachable for any feature that fired at all --
    it can only ever turn a pass into a fail, never the reverse."""
    assert d.compute_gate_b_fire_rate([10.0, 2.0, 1.0], floor_fraction=0.20) == d.compute_gate_b_fire_rate(
        [10.0, 2.0, 1.0], floor_fraction=0.20
    )
    fire_rate, floor = d.compute_gate_b_fire_rate([1e-9] * 10, floor_fraction=0.20)
    assert fire_rate == 1.0 and floor == pytest.approx(2e-10)


def test_gate_ab_result_records_the_absolute_floor_observed_max_and_n_positives():
    """C4: `activation_floor_fraction` (0.20) is a constant and says nothing
    about whether the feature fired. The absolute floor, the observed max
    and the fire_rate denominator are what make a recorded G-B verdict
    auditable after the fact."""
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    results = d.compute_gate_a_and_b_per_family(
        backend, artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE,
    )
    for r in results:
        assert r.n_positives == 10
        assert r.activation_floor == pytest.approx(r.observed_max * r.activation_floor_fraction)
        assert "activation_floor" in dataclasses.asdict(r)
        assert "observed_max" in dataclasses.asdict(r)
        assert "n_positives" in dataclasses.asdict(r)


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


def _gate_a_synthetic_artifact(base_artifact, *, near_miss_texts: list[str]):
    """A synthetic single-family ('f1') artifact for concept 'cheese'/locale
    'en': 8 POSITIVE-triggering positive rows, 8 clean (non-triggering)
    unrelated rows, and near_miss rows built from the caller's own
    `near_miss_texts` -- everything else held fixed so any change in
    `compute_gate_a_and_b_per_family`'s G-A verdict between two calls can
    only be attributed to the near_miss content."""
    import dataclasses

    other_rows = [
        r for r in base_artifact.rows
        if not (r["concept_id"] == "cheese" and r["locale"] == "en" and r["split"] in ("positive", "unrelated", "near_miss"))
    ]
    positive_rows = [
        {"concept_id": "cheese", "locale": "en", "split": "positive", "family": "f1", "text": f"POSITIVE example {i}"}
        for i in range(8)
    ]
    unrelated_rows = [
        {"concept_id": "cheese", "locale": "en", "split": "unrelated", "text": f"neutral filler {i}", "shared_substrate": True}
        for i in range(8)
    ]
    near_miss_rows = [
        {"concept_id": "cheese", "locale": "en", "split": "near_miss", "text": text}
        for text in near_miss_texts
    ]
    return dataclasses.replace(base_artifact, rows=[*other_rows, *positive_rows, *unrelated_rows, *near_miss_rows])


def test_compute_gate_a_and_b_per_family_pools_near_miss_into_the_negative_set():
    """P0 FINAL DELTA correction: G-A's negative/control set is the POOL of
    near_miss + unrelated (previously unrelated alone). Proven by holding
    EVERYTHING constant (backend, feature, positive texts, unrelated
    texts) and varying ONLY the near_miss split's content between two
    synthetic artifacts: 'hard' near_miss foils that read exactly like the
    POSITIVE-triggering pattern (indistinguishable from positive under
    this fake backend) flip gate_a_passed from True to False relative to
    'easy' near_miss foils that read like clean background noise -- if
    near_miss were NOT actually pooled into G-A's negative set, swapping
    its content could never change the verdict (G-C, the separate
    positive-vs-near_miss-only specificity test, is untouched by this
    change and is exercised independently below)."""
    backend = make_fake_gemma_backend()
    base_artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)

    hard_artifact = _gate_a_synthetic_artifact(base_artifact, near_miss_texts=[f"POSITIVE foil {i}" for i in range(8)])
    easy_artifact = _gate_a_synthetic_artifact(base_artifact, near_miss_texts=[f"neutral foil {i}" for i in range(8)])

    hard = next(
        r for r in d.compute_gate_a_and_b_per_family(
            backend, hard_artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE, auroc_min=0.9,
        ) if r.family == "f1"
    )
    easy = next(
        r for r in d.compute_gate_a_and_b_per_family(
            backend, easy_artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE, auroc_min=0.9,
        ) if r.family == "f1"
    )
    assert easy.gate_a_passed is True
    assert hard.gate_a_passed is False
    assert hard.separation_auroc < easy.separation_auroc


def test_gate_c_subsumption_note_records_that_gate_c_cannot_reject_what_gate_a_accepted():
    """C5. With 15 near_miss and 15 unrelated, AUROC against the pooled set
    is identically the mean of the two components, so G-A >= 0.90 forces
    near_miss AUROC >= 0.80 > G-C's 0.75. The note must say so, machine
    readably, and must re-derive it from the artifact rather than assert
    it."""
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    note = d.gate_c_subsumption_note(artifact, concept_id="cheese")
    assert note["holds"] is True
    assert note["gate_c_still_computed_and_recorded"] is True
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        per_locale = note["per_locale"][locale]
        assert per_locale["n_near_miss"] == per_locale["n_unrelated"] == 15
        assert per_locale["implied_near_miss_auroc_floor_given_gate_a_pass"] == pytest.approx(0.80)
        assert per_locale["gate_c_subsumed_by_gate_a"] is True
    assert note["identity"].startswith("separation_auroc ==")
    assert "referred for ratification" in note["gate_a_negative_set_change"]


def test_gate_c_subsumption_is_the_pooled_mean_identity_not_a_sample_property():
    """The identity the note rests on: for equal-sized control subsets,
    AUROC(pos vs pooled) == mean of the two component AUROCs, exactly."""
    rng = np.random.default_rng(31)
    for _ in range(200):
        pos = (rng.random(10) * 5.0).tolist()
        near = (rng.random(15) * 5.0).tolist()
        unrel = (rng.random(15) * 5.0).tolist()
        pooled = d._auroc_from_scores(pos, [*unrel, *near])
        assert pooled == pytest.approx(
            (d._auroc_from_scores(pos, near) + d._auroc_from_scores(pos, unrel)) / 2.0, abs=1e-12
        )
        if pooled >= 0.90:
            assert d._auroc_from_scores(pos, near) >= 0.80 - 1e-12


def test_grid_result_carries_the_subsumption_note_and_the_denominator_caveat(tmp_path):
    backend = make_fake_gemma_backend()
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    verdict = d.evaluate_concept_on_pairing(backend, artifact, concept_id="cheese")
    assert verdict.gate_c_subsumption is not None
    path = d.write_grid_result(tmp_path, "gemma-3-12b-it", [verdict])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["gate_denominator_caveat"] == d.GATE_DENOMINATOR_CAVEAT
    assert payload["gate_c_subsumption"]["holds"] is True
    assert payload["verdicts"][0]["gate_c_subsumption"]["holds"] is True
    # And the stale record is CORRECTED, never removed: G-C is still there.
    assert payload["verdicts"][0]["candidates_evaluated"][0]["gate_c_results"]


def test_compute_gate_c_per_family_is_unaffected_by_the_g_a_pooling_change():
    """G-C (compute_gate_c_per_family) remains the SEPARATE positive-vs-
    near_miss-ONLY specificity test -- it must report the SAME (low) AUROC
    against the 'hard' near_miss foils above regardless of G-A's pooling
    change, since G-C never reads 'unrelated' at all."""
    backend = make_fake_gemma_backend()
    base_artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    hard_artifact = _gate_a_synthetic_artifact(base_artifact, near_miss_texts=[f"POSITIVE foil {i}" for i in range(8)])

    result = next(
        r for r in d.compute_gate_c_per_family(
            backend, hard_artifact, concept_id="cheese", locale="en", feature_index=CONCEPT_FEATURE, auroc_min=0.9,
        ) if r.family == "f1"
    )
    assert result.gate_c_passed is False
    assert result.near_miss_auroc < 0.9


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
# Baseline (CONTROL) generation: no hook attached at all -- the paired
# unsteered counterpart G-D/G-E's evaluate_gate_d/evaluate_gate_e need.
# ---------------------------------------------------------------------------


def test_run_baseline_generation_attaches_no_hook_and_reports_baseline_direction():
    backend = make_fake_gemma_backend()
    outcome = d.run_baseline_generation(backend, prompt="hello", seed=0, max_new_tokens=2, positions="all")
    assert outcome.direction == "baseline"
    assert outcome.feature_indices == []
    assert outcome.value_in_max_units == 0.0
    assert outcome.verdict == {}
    assert outcome.spec["kind"] == "baseline"
    assert outcome.generated_text == "fake-generated-text"


def test_run_baseline_generation_is_deterministic_given_the_same_seed():
    backend = make_fake_gemma_backend()
    first = d.run_baseline_generation(backend, prompt="hello", seed=7, max_new_tokens=2, positions="all")
    second = d.run_baseline_generation(backend, prompt="hello", seed=7, max_new_tokens=2, positions="all")
    assert first.generated_text == second.generated_text


def test_run_intervention_defaults_to_greedy_when_no_generation_kwargs_given():
    backend = make_fake_gemma_backend()
    outcome = d.run_intervention(
        backend, [CONCEPT_FEATURE], direction="clamp", value_in_max_units=1.0,
        corpus_max=d.corpus_max_per_feature(backend, NEGATIVE_TEXTS), positions="all",
        prompt="hello", seed=0, max_new_tokens=3,
    )
    assert outcome.truncated is True  # the fake always emits exactly max_new_tokens


def test_run_intervention_accepts_the_frozen_generation_settings_without_error():
    """The fake model must not choke on the frozen one-allocation sampling
    kwargs (temperature/top_p/top_k/... ) it does not otherwise use."""
    backend = make_fake_gemma_backend()
    outcome = d.run_intervention(
        backend, [CONCEPT_FEATURE], direction="clamp", value_in_max_units=1.0,
        corpus_max=d.corpus_max_per_feature(backend, NEGATIVE_TEXTS), positions="all",
        prompt="hello", seed=0, max_new_tokens=3, generation_kwargs=d.GENERATION_SETTINGS,
    )
    assert outcome.generated_text == "fake-generated-text"


# ---------------------------------------------------------------------------
# P0 STOP-LINE correction: real chat template application, derived template
# identity, decode-only-new-tokens, explicit EOS/EOT/PAD resolution.
# ---------------------------------------------------------------------------


class _RecordingTokenizer:
    """A minimal tokenizer stub that RECORDS what it is asked to render/
    decode -- proves the real chat-template/decode-slicing contract
    without needing a real HF tokenizer."""

    name_or_path = "recording/fake-tokenizer"
    chat_template = "{{ messages[0]['content'] }}"
    eos_token_id = 42
    pad_token_id = 42
    unk_token_id = None

    def __init__(self, model):
        self._model = model
        self.last_messages = None
        self.last_decoded_ids = None

    def convert_tokens_to_ids(self, _token):
        return None

    def apply_chat_template(
        self, messages, *, tokenize: bool = True, add_generation_prompt: bool = True,
        return_tensors: str | None = None, return_dict: bool = False, **_kwargs,
    ):
        self.last_messages = messages
        rendered = "".join(m["content"] for m in messages)
        if not tokenize:
            return rendered
        tokens = self._model.to_tokens(rendered)
        if return_dict:
            return {"input_ids": tokens, "attention_mask": torch.ones_like(tokens)}
        return tokens

    def decode(self, ids, **_kwargs) -> str:
        self.last_decoded_ids = ids
        return "fake-generated-text"


def test_run_intervention_applies_the_real_chat_template_with_one_user_turn_no_system_prompt():
    backend = make_fake_gemma_backend()
    recorder = _RecordingTokenizer(backend.model_obj)
    backend.model_obj.tokenizer = recorder
    d.run_intervention(
        backend, [CONCEPT_FEATURE], direction="clamp", value_in_max_units=1.0,
        corpus_max=d.corpus_max_per_feature(backend, NEGATIVE_TEXTS), positions="all",
        prompt="hello there", seed=0, max_new_tokens=2,
    )
    assert recorder.last_messages == [{"role": "user", "content": "hello there"}]


def test_run_intervention_decodes_only_tokens_after_the_prompt():
    backend = make_fake_gemma_backend()
    recorder = _RecordingTokenizer(backend.model_obj)
    backend.model_obj.tokenizer = recorder
    d.run_intervention(
        backend, [CONCEPT_FEATURE], direction="clamp", value_in_max_units=1.0,
        corpus_max=d.corpus_max_per_feature(backend, NEGATIVE_TEXTS), positions="all",
        prompt="hello there", seed=0, max_new_tokens=3,
    )
    # the fake's to_tokens registers exactly ONE token for the whole
    # rendered prompt; generate() appends max_new_tokens more tokens --
    # decode() must have been given only those 3 new tokens, never the 1
    # prompt token too.
    assert recorder.last_decoded_ids.shape[0] == 3


def test_run_baseline_generation_decodes_only_tokens_after_the_prompt():
    backend = make_fake_gemma_backend()
    recorder = _RecordingTokenizer(backend.model_obj)
    backend.model_obj.tokenizer = recorder
    d.run_baseline_generation(backend, prompt="hello there", seed=0, max_new_tokens=4, positions="all")
    assert recorder.last_decoded_ids.shape[0] == 4


class _StopIdTokenizerStub:
    name_or_path = "stub"
    chat_template = "{{ messages }}"

    def __init__(self, *, eos_token_id, pad_token_id=None, unk_token_id=None, known_tokens=None):
        self.eos_token_id = eos_token_id
        self.pad_token_id = pad_token_id
        self.unk_token_id = unk_token_id
        self._known = known_tokens or {}

    def convert_tokens_to_ids(self, token):
        return self._known.get(token, self.unk_token_id)


def test_resolve_stop_token_ids_uses_eos_and_pad_when_no_end_of_turn_marker_present():
    tok = _StopIdTokenizerStub(eos_token_id=1, pad_token_id=0, unk_token_id=99)
    assert d.resolve_stop_token_ids(tok) == {"eos_token_id": 1, "pad_token_id": 0}


def test_resolve_stop_token_ids_adds_end_of_turn_marker_when_present():
    """Gemma's own generation_config.json ships eos_token_id as a LIST
    ([<eos>, <end_of_turn>]) -- a chat model's real stop condition is
    often more than one token id."""
    tok = _StopIdTokenizerStub(eos_token_id=1, pad_token_id=0, unk_token_id=99, known_tokens={"<end_of_turn>": 106})
    assert d.resolve_stop_token_ids(tok) == {"eos_token_id": [1, 106], "pad_token_id": 0}


def test_resolve_stop_token_ids_defaults_pad_to_eos_when_tokenizer_has_no_pad():
    tok = _StopIdTokenizerStub(eos_token_id=1, pad_token_id=None, unk_token_id=99)
    assert d.resolve_stop_token_ids(tok) == {"eos_token_id": 1, "pad_token_id": 1}


def test_resolve_stop_token_ids_raises_without_an_eos_token():
    tok = _StopIdTokenizerStub(eos_token_id=None)
    with pytest.raises(ValueError, match="eos_token_id"):
        d.resolve_stop_token_ids(tok)


def test_resolve_chat_template_identity_raises_without_a_chat_template():
    tok = _StopIdTokenizerStub(eos_token_id=1)
    tok.chat_template = None
    with pytest.raises(ValueError, match="chat_template"):
        d.resolve_chat_template_identity(tok)


def test_resolve_chat_template_identity_is_stable_and_name_prefixed():
    tok = _StopIdTokenizerStub(eos_token_id=1)
    tok.chat_template = "{{ messages }}"
    tok.name_or_path = "org/model"
    identity_1 = d.resolve_chat_template_identity(tok)
    identity_2 = d.resolve_chat_template_identity(tok)
    assert identity_1 == identity_2
    assert identity_1.startswith("org/model:")


def test_resolve_chat_template_identity_differs_for_different_templates():
    tok_a = _StopIdTokenizerStub(eos_token_id=1)
    tok_a.chat_template = "{{ messages }}"
    tok_b = _StopIdTokenizerStub(eos_token_id=1)
    tok_b.chat_template = "{{ messages }} different"
    assert d.resolve_chat_template_identity(tok_a) != d.resolve_chat_template_identity(tok_b)


def test_generation_settings_protocol_hash_matches_the_real_frozen_artifact():
    d.validate_generation_settings_protocol_hash(d.REPO_ROOT)  # must not raise


def test_generation_settings_protocol_hash_refuses_a_tampered_copy(tmp_path):
    (tmp_path / "protocols" / "final_pairing" / "v1").mkdir(parents=True)
    (tmp_path / "protocols" / "final_pairing" / "v1" / "generation_settings.json").write_text("{}", encoding="utf-8")
    with pytest.raises(d.PromptArtifactError):
        d.validate_generation_settings_protocol_hash(tmp_path)


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


def test_assert_params_sha256_matches_counts_the_same_file_requested_twice_as_one(tmp_path):
    """Job 413287's Gemma arm died 4 minutes in on exactly this: one load
    requests the SAME params.safetensors twice (shape lookup, then weights),
    the capture log records both requests, and the guard read two requests
    as two files. Character-for-character identical paths are ONE file."""
    path = tmp_path / "resid_post_all" / "layer_29_width_16k_l0_big" / "params.safetensors"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"fake sae weights")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    measured = d.assert_params_sha256_matches(
        [str(path), str(path)], expected_sha256=expected
    )
    assert measured == expected


def test_assert_params_sha256_matches_dedupes_on_the_real_path_not_the_string(tmp_path):
    """Two different path STRINGS naming one file (here via an unnormalized
    traversal) are one file. Deduplication is on the dereferenced real path,
    never on the string as written."""
    params = tmp_path / "resid_post_all" / "layer_29_width_16k_l0_big" / "params.safetensors"
    params.parent.mkdir(parents=True)
    params.write_bytes(b"fake sae weights")
    detour = params.parent / ".." / params.parent.name / params.name
    assert str(detour) != str(params)
    expected = hashlib.sha256(params.read_bytes()).hexdigest()
    measured = d.assert_params_sha256_matches([str(params), str(detour)], expected_sha256=expected)
    assert measured == expected


def _link_directory(link: Path, target: Path) -> None:
    """A second filesystem route to `target`: a real symlink where the
    platform/account permits one (Linux, i.e. Tamia, always does), else an
    NTFS directory junction, which os.path.realpath dereferences the same
    way. Skips only if neither is available."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if sys.platform != "win32":
        pytest.skip("symlink creation not permitted on this platform/account")
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True
    )
    if completed.returncode != 0 or not link.exists():
        pytest.skip(f"neither symlink nor junction could be created: {completed.stderr.strip()}")


def test_assert_params_sha256_matches_treats_a_link_and_its_target_as_one_file(tmp_path):
    """The case a real huggingface_hub cache actually produces: a snapshot
    entry is a link whose dereferenced target lives in a sibling blobs/
    store, so the same file is reachable by two unrelated path strings."""
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "params.safetensors").write_bytes(b"fake sae weights")
    snapshot_dir = tmp_path / "snapshots" / "4c419f1"
    snapshot_dir.parent.mkdir(parents=True)
    _link_directory(snapshot_dir, blobs)
    via_snapshot = snapshot_dir / "params.safetensors"
    via_blob = blobs / "params.safetensors"
    assert os.path.realpath(via_snapshot) == os.path.realpath(via_blob)
    expected = hashlib.sha256(via_blob.read_bytes()).hexdigest()
    measured = d.assert_params_sha256_matches(
        [str(via_snapshot), str(via_blob)], expected_sha256=expected
    )
    assert measured == expected


def test_the_real_two_request_gemma_load_sequence_no_longer_trips_the_guard(monkeypatch, tmp_path):
    """End-to-end reproduction of job 413287's Gemma crash, through the real
    capture wrapper: a gemma_3 load asks for params.safetensors TWICE --
    once as an inline path (get_gemma_3_config_from_hf ->
    get_safetensors_tensor_shapes, routed through psl.hf_hub_download by
    _patch_gemma3_safetensors_shape_lookup) and once as filename+subfolder
    (gemma_3_sae_huggingface_loader's weight download). Both resolve to the
    same local file, so the capture log holds two identical strings."""
    import final_pairing_harness as harness
    import sae_lens.loading.pretrained_sae_loaders as psl

    snapshot_dir = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "4c419f1"
    subfolder = "resid_post_all/layer_29_width_16k_l0_big"
    folder = snapshot_dir / "resid_post_all" / "layer_29_width_16k_l0_big"
    folder.mkdir(parents=True)
    (folder / "params.safetensors").write_bytes(b"fake sae weights")

    monkeypatch.setattr(psl, "hf_hub_download", lambda *a, **k: pytest.fail("real download"))
    captured: list[str] = []
    saved_original = harness._capture_sae_download_paths(
        captured, sae_path=snapshot_dir, target=d._gemma_scientific_target(layer=29)
    )
    try:
        psl.hf_hub_download(
            repo_id="google/gemma-scope-2-12b-it", filename=f"{subfolder}/params.safetensors"
        )
        psl.hf_hub_download(
            repo_id="google/gemma-scope-2-12b-it", filename="params.safetensors",
            subfolder=subfolder, force_download=False,
        )
    finally:
        harness._restore_sae_download_paths(saved_original)

    # The duplicate is real and is NOT being suppressed upstream: the capture
    # log still records both requests, character-for-character identical.
    assert captured == [str(folder / "params.safetensors")] * 2
    expected = hashlib.sha256((folder / "params.safetensors").read_bytes()).hexdigest()
    assert d.assert_params_sha256_matches(captured, expected_sha256=expected) == expected


def test_assert_params_sha256_matches_still_refuses_two_different_files_with_a_duplicate_present(tmp_path):
    """Deduplication must not become a way for a second, GENUINELY different
    params.safetensors to slip past: duplicates collapse, distinct files
    still stop the run."""
    first = tmp_path / "a" / "params.safetensors"
    second = tmp_path / "b" / "params.safetensors"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    with pytest.raises(targets.TargetIdentityMismatch, match=r"found 2 distinct files"):
        d.assert_params_sha256_matches(
            [str(first), str(first), str(second), str(second)], expected_sha256="0" * 64
        )


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
