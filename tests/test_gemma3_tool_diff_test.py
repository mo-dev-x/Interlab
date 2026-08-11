"""Tests for scripts/legacy/gemma3_tool_diff_test.py's gating logic and
main()'s exit-code wiring. Orchestrator review, 2026-08-13 ("repair Step
0"): live job 406092 showed identical_text=false yet the process exited 0
-- diff_report's fields were computed and then never consulted. These
tests exist so that specific failure mode can never silently reappear.

No GPU, no real model/SAE weights -- main()'s heavy dependencies (module
loading, model/SAE loading, generation, activation recording) are all
monkeypatched at the module-function level.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "legacy" / "gemma3_tool_diff_test.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dt = _load("gemma3_tool_diff_test", SCRIPT)


# ---------------------------------------------------------------------------
# diff_report -- the pure gating logic. gate_passed must reflect every
# criterion diff_report itself computes, not just some of them.
# ---------------------------------------------------------------------------


def test_diff_report_gate_passed_true_when_all_criteria_hold():
    report = dt.diff_report(
        "same text", "same text", [0.5, 0.5, 0.5], [0.5, 0.5, 0.5],
        token_ids_a=[1, 2, 3], token_ids_b=[1, 2, 3],
    )
    assert report["identical_text"] is True
    assert report["identical_token_ids"] is True
    assert report["activations_effectively_identical"] is True
    assert report["gate_passed"] is True


def test_diff_report_gate_passed_false_when_text_differs():
    """The exact live defect: identical_text=false must make gate_passed
    false, even if every other criterion happens to hold."""
    report = dt.diff_report(
        "sweep text", "DIFFERENT tool text", [0.5, 0.5], [0.5, 0.5],
        token_ids_a=[1, 2], token_ids_b=[1, 2],
    )
    assert report["identical_text"] is False
    assert report["gate_passed"] is False


def test_diff_report_gate_passed_false_when_activations_differ():
    report = dt.diff_report(
        "same text", "same text", [0.5, 0.5, 0.5], [0.9, 0.9, 0.9],
        token_ids_a=[1, 2, 3], token_ids_b=[1, 2, 3],
    )
    assert report["activations_effectively_identical"] is False
    assert report["max_abs_activation_diff"] == pytest.approx(0.4)
    assert report["gate_passed"] is False


def test_diff_report_gate_passed_false_when_token_ids_differ_even_with_identical_text():
    """A stricter, independent check than identical_text -- decoded-text
    equality does not strictly imply token-id equality."""
    report = dt.diff_report(
        "same text", "same text", [0.5, 0.5], [0.5, 0.5],
        token_ids_a=[1, 2, 3], token_ids_b=[1, 2, 4],
    )
    assert report["identical_text"] is True
    assert report["identical_token_ids"] is False
    assert report["gate_passed"] is False


def test_diff_report_does_not_gate_on_token_ids_when_unavailable():
    """'Require identical token IDs when available' -- when neither side
    supplied them, that criterion must not itself sink an otherwise
    fully-passing report."""
    report = dt.diff_report("same text", "same text", [0.5, 0.5], [0.5, 0.5])
    assert report["token_ids_available"] is False
    assert report["identical_token_ids"] is None
    assert report["gate_passed"] is True


def test_diff_report_activation_criterion_requires_exact_zero_not_a_new_tolerance():
    """Preserves the existing criterion exactly -- no epsilon is invented
    here. A tiny but nonzero diff must still fail."""
    report = dt.diff_report(
        "same text", "same text", [0.5], [0.5 + 1e-9], token_ids_a=[1], token_ids_b=[1],
    )
    assert report["activations_effectively_identical"] is False
    assert report["gate_passed"] is False


def test_diff_report_empty_activation_comparison_is_a_failure_not_a_vacuous_pass():
    report = dt.diff_report("same text", "same text", [], [], token_ids_a=[1], token_ids_b=[1])
    assert report["activation_positions_compared"] == 0
    assert report["activations_effectively_identical"] is False
    assert report["gate_passed"] is False


def test_diff_report_gate_criteria_dict_matches_top_level_fields():
    report = dt.diff_report("x", "y", [0.1], [0.1], token_ids_a=[1], token_ids_b=[2])
    assert report["gate_criteria"] == {
        "identical_text": report["identical_text"],
        "identical_token_ids": report["identical_token_ids"],
        "activations_effectively_identical": report["activations_effectively_identical"],
    }


# ---------------------------------------------------------------------------
# main() -- proves the exit code is actually wired to gate_passed, not just
# that diff_report computes the right dict in isolation. Every heavy
# dependency (module loading, model/SAE loading, generation, activation
# recording) is monkeypatched; only main()'s own control flow is real.
# ---------------------------------------------------------------------------


class _FakeToolModule:
    @staticmethod
    def load_manifest(path, sweep):
        return {"features": []}

    @staticmethod
    def feature_by_idx(manifest, idx):
        return {"maxActApprox": 100.0}

    @staticmethod
    def ModelBundle(model, sae, hook_name):
        return SimpleNamespace(model=model, sae=sae, hook_name=hook_name)


def _fake_load(name, path):
    if "gemma3_tool" in str(path):
        return _FakeToolModule()

    import torch

    fake_model = SimpleNamespace(to_tokens=lambda prompt: torch.zeros((1, 3), dtype=torch.long))
    fake_sae = SimpleNamespace(cfg=SimpleNamespace(metadata=SimpleNamespace(hook_name="blocks.31.hook_resid_post")))
    return SimpleNamespace(
        load_model_and_sae=lambda model_path, sae_path, *, device, dtype: (fake_model, fake_sae, SimpleNamespace())
    )


def _base_argv():
    return [
        "--model-path", "x", "--sae-path", "y", "--feature-idx", "0", "--mode", "steer",
        "--dose-multiple", "1.0", "--prompt", "hi",
    ]


def _install_common_mocks(monkeypatch, *, sweep_text, tool_text, sweep_n_tokens, tool_token_ids, sweep_acts, tool_acts):
    """sweep_n_tokens is the sweep path's FULL generated tensor length
    (prompt + completion); the fake model's to_tokens always returns a
    3-token prompt (see _fake_load), so sweep_token_ids ends up being
    sweep_n_tokens - 3 zeros -- callers pick sweep_n_tokens/tool_token_ids
    to control whether identical_token_ids holds."""
    import torch

    monkeypatch.setattr(dt, "_load", _fake_load)
    monkeypatch.setattr(dt, "run_sweep_path", lambda *a, **k: (sweep_text, torch.zeros((1, sweep_n_tokens), dtype=torch.long)))

    def fake_run_tool_path(*a, token_ids_out=None, **k):
        if token_ids_out is not None:
            token_ids_out.extend(tool_token_ids)
        return tool_text, 50.0

    monkeypatch.setattr(dt, "run_tool_path", fake_run_tool_path)

    calls = {"n": 0}

    def fake_record_activations(*a, **k):
        calls["n"] += 1
        return sweep_acts if calls["n"] == 1 else tool_acts

    monkeypatch.setattr(dt, "_record_activations", fake_record_activations)


def test_main_exits_nonzero_when_texts_differ(monkeypatch):
    _install_common_mocks(
        monkeypatch, sweep_text="sweep completion", tool_text="DIFFERENT completion",
        sweep_n_tokens=5, tool_token_ids=[0, 0], sweep_acts=[0.5, 0.5, 0.5], tool_acts=[0.5, 0.5, 0.5],
    )
    exit_code = dt.main(_base_argv())
    assert exit_code != 0


def test_main_exits_nonzero_when_activations_differ(monkeypatch):
    _install_common_mocks(
        monkeypatch, sweep_text="same text", tool_text="same text",
        sweep_n_tokens=5, tool_token_ids=[0, 0], sweep_acts=[0.5, 0.5, 0.5], tool_acts=[0.9, 0.9, 0.9],
    )
    exit_code = dt.main(_base_argv())
    assert exit_code != 0


def test_main_exits_zero_when_all_gate_criteria_pass(monkeypatch):
    """sweep_n_tokens=5 with a 3-token prompt (to_tokens always returns
    shape (1, 3)) yields sweep_token_ids == [0, 0] -- must match
    tool_token_ids exactly for identical_token_ids to hold too."""
    _install_common_mocks(
        monkeypatch, sweep_text="same text", tool_text="same text",
        sweep_n_tokens=5, tool_token_ids=[0, 0], sweep_acts=[0.5, 0.5, 0.5], tool_acts=[0.5, 0.5, 0.5],
    )
    exit_code = dt.main(_base_argv())
    assert exit_code == 0
