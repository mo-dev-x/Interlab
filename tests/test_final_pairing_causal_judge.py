"""Tests for scripts/final_pairing/final_pairing_causal_judge.py.

`lodestar` is not installed in this repository's environment (confirmed:
`import lodestar` raises `ModuleNotFoundError` here) -- every test below
either exercises the fail-closed path (real, since the import genuinely
fails) or drives `evaluate_gate_d`/`evaluate_gate_e`/the spot-read helpers
directly with plain data, never importing lodestar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_causal_judge as judge_mod  # noqa: E402


def _numpy_bootstrap_ci(values, *, seed=42, confidence=0.95, n_resamples=500):
    """A plain numpy-only stand-in for lodestar.metrics.stats.bootstrap_ci,
    used ONLY to exercise evaluate_gate_d/evaluate_gate_e's pure arithmetic
    without requiring lodestar to be importable -- the real production
    default remains judge_mod.compute_prompt_group_bootstrap_ci."""
    import numpy as np

    array = np.asarray(values, dtype=float)
    generator = np.random.default_rng(seed)
    estimates = np.array([generator.choice(array, size=array.size, replace=True).mean() for _ in range(n_resamples)])
    tail = (1 - confidence) / 2
    return float(np.quantile(estimates, tail)), float(np.quantile(estimates, 1 - tail))


def test_lodestar_is_genuinely_not_installed_here():
    """Ground truth for every fail-closed test below: if this ever starts
    passing, the fail-closed tests need a different fixture, not a
    monkeypatch that could paper over a real absence."""
    with pytest.raises(ModuleNotFoundError):
        __import__("lodestar")


def test_build_live_causal_judge_runtime_fails_closed_when_lodestar_missing():
    with pytest.raises(judge_mod.CausalJudgeUnavailable, match="not importable"):
        judge_mod.build_live_causal_judge_runtime(judge_model="claude-sonnet-4-5-20250929", api_key="sk-fake")


def test_load_steering_rubrics_fails_closed_when_lodestar_missing():
    with pytest.raises(judge_mod.CausalJudgeUnavailable, match="not importable"):
        judge_mod.load_steering_rubrics()


def test_compute_prompt_group_bootstrap_ci_fails_closed_when_lodestar_missing():
    with pytest.raises(judge_mod.CausalJudgeUnavailable, match="not importable"):
        judge_mod.compute_prompt_group_bootstrap_ci([1.0, 2.0, 3.0])


def test_build_live_causal_judge_runtime_requires_an_api_key(monkeypatch):
    """Even if lodestar WERE importable, no key must still fail closed --
    exercised by monkeypatching only the import boundary, not the key
    check, so this test would catch a regression where the key check gets
    skipped once lodestar is eventually installed."""
    import types

    fake_anthropic_judge_class = type("FakeAnthropicJudge", (), {"__init__": lambda self, **kw: None})
    fake_module = types.SimpleNamespace(AnthropicJudge=fake_anthropic_judge_class)
    monkeypatch.setattr(judge_mod, "_import_lodestar_submodule", lambda dotted: fake_module)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(judge_mod.CausalJudgeUnavailable, match="ANTHROPIC_API_KEY"):
        judge_mod.build_live_causal_judge_runtime(judge_model="claude-sonnet-4-5-20250929")


def test_build_live_causal_judge_runtime_succeeds_with_a_fake_lodestar_and_a_key(monkeypatch):
    import types

    captured = {}

    class FakeAnthropicJudge:
        def __init__(self, *, model_name, api_key):
            captured["model_name"] = model_name
            captured["api_key"] = api_key

    fake_module = types.SimpleNamespace(AnthropicJudge=FakeAnthropicJudge)
    monkeypatch.setattr(judge_mod, "_import_lodestar_submodule", lambda dotted: fake_module)
    runtime = judge_mod.build_live_causal_judge_runtime(judge_model="claude-sonnet-4-5-20250929", api_key="sk-test")
    assert isinstance(runtime, FakeAnthropicJudge)
    assert captured == {"model_name": "claude-sonnet-4-5-20250929", "api_key": "sk-test"}


def test_load_steering_rubrics_rejects_an_unexpected_rubric_identity(monkeypatch):
    import types

    class _Rubric:
        def __init__(self, name, version):
            self.name = name
            self.version = version

    fake_module = types.SimpleNamespace(COHERENCE=_Rubric("coherence", "2.0"), CONCEPT_RELEVANCE=_Rubric("concept_relevance", "1.0"))
    monkeypatch.setattr(judge_mod, "_import_lodestar_submodule", lambda dotted: fake_module)
    with pytest.raises(judge_mod.CausalJudgeUnavailable, match=r"expected 'coherence'/'1\.0'"):
        judge_mod.load_steering_rubrics()


def test_run_judge_batch_rejects_zero_repeats():
    with pytest.raises(ValueError, match="repeats"):
        judge_mod.run_judge_batch(judge=object(), items=[], repeats=0)


class _FakeJudgment:
    def __init__(self, generation_id, score):
        self.generation_id = generation_id
        self.score = score


class _FakeAsyncJudge:
    def __init__(self, judgments):
        self._judgments = judgments

    async def judge_batch(self, items, repeats):
        return self._judgments * repeats


def test_run_judge_batch_runs_the_async_protocol_to_completion():
    fake_judge = _FakeAsyncJudge([_FakeJudgment("g1", 8.0), _FakeJudgment("g2", 6.0)])
    result = judge_mod.run_judge_batch(fake_judge, items=[("gen1", "rubric1"), ("gen2", "rubric1")], repeats=1)
    assert [j.score for j in result] == [8.0, 6.0]


# ---------------------------------------------------------------------------
# Gate D (Amplify)
# ---------------------------------------------------------------------------


def test_gate_d_passes_when_delta_ci_and_coherence_all_clear_the_bar():
    steered = {f"p{i}": [9.0, 9.0] for i in range(10)}
    control = {f"p{i}": [3.0, 3.0] for i in range(10)}
    result = judge_mod.evaluate_gate_d(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_min=3.0, coherence_median_min=6.0,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.relevance_delta == pytest.approx(6.0)
    assert result.ci_excludes_zero_in_amplify_direction is True
    assert result.passed is True


def test_gate_d_fails_when_delta_below_threshold_even_if_ci_excludes_zero():
    steered = {f"p{i}": [4.0] for i in range(10)}
    control = {f"p{i}": [3.5] for i in range(10)}
    result = judge_mod.evaluate_gate_d(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_min=3.0, coherence_median_min=6.0,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.relevance_delta == pytest.approx(0.5)
    assert result.passed is False


def test_gate_d_fails_when_coherence_median_is_too_low_even_with_a_large_delta():
    steered = {f"p{i}": [9.0] for i in range(10)}
    control = {f"p{i}": [1.0] for i in range(10)}
    result = judge_mod.evaluate_gate_d(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[2.0] * 10, relevance_delta_min=3.0, coherence_median_min=6.0,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.relevance_delta == pytest.approx(8.0)
    assert result.coherence_median == pytest.approx(2.0)
    assert result.passed is False


def test_gate_d_fails_when_ci_does_not_exclude_zero_despite_a_high_mean_delta():
    """Mean delta above threshold but with a couple of prompts pulling the
    CI back through zero -- passing must require the CI condition too,
    not just the point estimate."""
    steered = {"p0": [9.0], "p1": [9.0], "p2": [1.0], "p3": [1.0]}
    control = {"p0": [1.0], "p1": [1.0], "p2": [9.0], "p3": [9.0]}
    result = judge_mod.evaluate_gate_d(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 4, relevance_delta_min=0.0, coherence_median_min=6.0,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.ci_excludes_zero_in_amplify_direction is False
    assert result.passed is False


def test_paired_deltas_requires_matching_prompt_ids_in_both_arms():
    with pytest.raises(ValueError, match="no prompt_id is present in both"):
        judge_mod._paired_deltas({"p0": [1.0]}, {"p1": [1.0]})


def test_paired_deltas_reports_partial_prompt_coverage_mismatch():
    with pytest.raises(ValueError, match="missing from"):
        judge_mod._paired_deltas({"p0": [1.0], "p1": [1.0]}, {"p0": [1.0]})


# ---------------------------------------------------------------------------
# Spot read
# ---------------------------------------------------------------------------


def test_spot_read_packet_requires_at_least_ten_generations():
    with pytest.raises(ValueError, match="at least 10"):
        judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(5)])


def test_spot_read_packet_is_deterministic_regardless_of_input_order():
    generations = [{"prompt_id": f"p{i:02d}", "text": f"text-{i}"} for i in range(15)]
    reversed_generations = list(reversed(generations))
    packet_a = judge_mod.build_spot_read_packet(generations)
    packet_b = judge_mod.build_spot_read_packet(reversed_generations)
    assert packet_a == packet_b
    assert len(packet_a.sampled_generations) == 10


def test_resolve_spot_read_decision_requires_a_nonempty_note():
    packet = judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(10)])
    with pytest.raises(ValueError, match="non-empty note"):
        judge_mod.resolve_spot_read_decision(packet, approved=True, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="")


def test_resolve_spot_read_decision_records_a_refusal_as_a_complete_decision():
    packet = judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(10)])
    decision = judge_mod.resolve_spot_read_decision(
        packet, approved=False, approved_by="researcher", approved_at="2026-08-13T00:00:00Z",
        note="generations read as evasive rather than suppressed",
    )
    assert decision.approved is False
    assert decision.sampled_generations == 10


# ---------------------------------------------------------------------------
# Gate E (Suppress) -- null suppress on gate failure or spot-read refusal
# ---------------------------------------------------------------------------


def _passing_gate_e_inputs():
    steered = {f"p{i}": [1.0] for i in range(10)}
    control = {f"p{i}": [9.0] for i in range(10)}
    return steered, control


def test_gate_e_passes_only_with_a_passing_automated_gate_and_an_approved_spot_read():
    steered, control = _passing_gate_e_inputs()
    packet = judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(10)])
    approved = judge_mod.resolve_spot_read_decision(packet, approved=True, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="reads as suppressed")
    result = judge_mod.evaluate_gate_e(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
        spot_read=approved,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.passed is True


def test_gate_e_is_null_when_automated_gate_passes_but_spot_read_is_refused():
    steered, control = _passing_gate_e_inputs()
    packet = judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(10)])
    refused = judge_mod.resolve_spot_read_decision(packet, approved=False, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="reads as evasive")
    result = judge_mod.evaluate_gate_e(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
        spot_read=refused,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.passed is False
    assert result.spot_read.approved is False


def test_gate_e_is_null_when_spot_read_is_entirely_absent_even_if_gate_would_pass():
    steered, control = _passing_gate_e_inputs()
    result = judge_mod.evaluate_gate_e(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
        spot_read=None,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.passed is False


def test_gate_e_is_null_when_automated_gate_fails_even_with_an_approved_spot_read():
    steered = {f"p{i}": [5.0] for i in range(10)}
    control = {f"p{i}": [5.5] for i in range(10)}  # delta only -0.5, does not clear -3.0
    packet = judge_mod.build_spot_read_packet([{"prompt_id": f"p{i}", "text": "x"} for i in range(10)])
    approved = judge_mod.resolve_spot_read_decision(packet, approved=True, approved_by="researcher", approved_at="2026-08-13T00:00:00Z", note="reads as suppressed anyway")
    result = judge_mod.evaluate_gate_e(
        steered_relevance_by_prompt=steered, control_relevance_by_prompt=control,
        steered_coherence_scores=[8.0] * 10, relevance_delta_max=-3.0, coherence_median_min=6.0,
        spot_read=approved,
        bootstrap_ci_fn=_numpy_bootstrap_ci,
    )
    assert result.passed is False
