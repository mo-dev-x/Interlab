"""Pure-Python tests for scripts/legacy/final_pairing_targets.py: the
ratified target identities and the fail-closed validators. No torch, no
GPU, no network, no real weights -- everything here is strings/ints/dicts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "legacy"))

import final_pairing_targets as targets  # noqa: E402

# ---------------------------------------------------------------------------
# Ratified identities -- no invented content, exact strings only.
# ---------------------------------------------------------------------------


def test_gemma_target_identities_are_exactly_ratified():
    t = targets.GEMMA_3_12B_IT_TARGET
    assert t.model_repo_id == "google/gemma-3-12b-it"
    assert t.sae_repo_id == "google/gemma-scope-2-12b-it"
    assert t.sae_id == "resid_post/layer_31_width_16k_l0_medium"
    assert t.expected_layer == 31
    assert t.expected_hook_name == "blocks.31.hook_resid_post"
    assert t.model_supported_by_transformer_lens is True


def test_qwen_target_identities_are_exactly_ratified():
    t = targets.QWEN_3_5_27B_TARGET
    assert t.model_repo_id == "Qwen/Qwen3.5-27B"
    assert t.sae_repo_id == "Qwen/SAE-Res-Qwen3.5-27B-W80K-L0_50"
    assert t.model_supported_by_transformer_lens is False


def test_qwen_layer_is_not_pre_registered_engineering_only():
    """The ratified spec explicitly leaves the Qwen layer to be selected
    from the official release or available Tamia snapshots -- this module
    must not invent one."""
    assert targets.QWEN_3_5_27B_TARGET.expected_layer is None


def test_targets_carry_no_feature_identities():
    """Do-not list: no PT-Gemma/Qwen2.5 feature identities, no invented
    concept content. Neither target dataclass has any field that could
    hold a feature index/label -- this test fails loudly (AttributeError)
    if one is ever added, which is the point."""
    for t in (targets.GEMMA_3_12B_IT_TARGET, targets.QWEN_3_5_27B_TARGET):
        forbidden_fields = {"feature_idx", "features", "label", "concept"}
        assert not (forbidden_fields & set(t.__dataclass_fields__))


# ---------------------------------------------------------------------------
# parse_hf_cache_snapshot_path -- mechanical string parsing only.
# ---------------------------------------------------------------------------


def test_parse_hf_cache_snapshot_path_extracts_org_repo_revision():
    parsed = targets.parse_hf_cache_snapshot_path(
        "/scratch/y/yazid/hf_cache/hub/models--google--gemma-3-12b-it/snapshots/abc123/config.json"
    )
    assert parsed == {"org": "google", "repo": "gemma-3-12b-it", "revision": "abc123"}


def test_parse_hf_cache_snapshot_path_handles_hyphenated_repo_names():
    parsed = targets.parse_hf_cache_snapshot_path(
        "/scratch/hf_cache/hub/models--Qwen--SAE-Res-Qwen3.5-27B-W80K-L0_50/snapshots/deadbeef/layer31.sae.pt"
    )
    assert parsed == {"org": "Qwen", "repo": "SAE-Res-Qwen3.5-27B-W80K-L0_50", "revision": "deadbeef"}


def test_parse_hf_cache_snapshot_path_returns_none_for_non_cache_layout():
    assert targets.parse_hf_cache_snapshot_path("/home/y/yazid/hand_staged_model_dir") is None


def test_parse_hf_cache_snapshot_path_handles_windows_backslashes():
    parsed = targets.parse_hf_cache_snapshot_path(
        r"D:\hf_cache\hub\models--google--gemma-3-12b-it\snapshots\abc123"
    )
    assert parsed == {"org": "google", "repo": "gemma-3-12b-it", "revision": "abc123"}


# ---------------------------------------------------------------------------
# validate_local_snapshot_identity -- fail closed on mismatch, silent on
# "cannot verify" (a hand-staged path with no HF cache layout at all).
# ---------------------------------------------------------------------------


def test_validate_local_snapshot_identity_passes_on_matching_repo():
    targets.validate_local_snapshot_identity(
        "/scratch/hf_cache/hub/models--google--gemma-3-12b-it/snapshots/abc123",
        targets.GEMMA_3_12B_IT_TARGET, which="model",
    )  # must not raise


def test_validate_local_snapshot_identity_raises_on_wrong_repo():
    """The exact silent-wrong-checkpoint failure mode this validator exists
    to catch: a path that looks staged but actually names the OLD -pt repo."""
    with pytest.raises(targets.TargetIdentityMismatch, match="gemma-3-12b-pt"):
        targets.validate_local_snapshot_identity(
            "/scratch/hf_cache/hub/models--google--gemma-3-12b-pt/snapshots/abc123",
            targets.GEMMA_3_12B_IT_TARGET, which="model",
        )


def test_validate_local_snapshot_identity_raises_on_wrong_sae_repo():
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_local_snapshot_identity(
            "/scratch/hf_cache/hub/models--google--gemma-scope-2-12b-pt/snapshots/abc123",
            targets.GEMMA_3_12B_IT_TARGET, which="sae",
        )


def test_validate_local_snapshot_identity_raises_on_wrong_revision():
    with pytest.raises(targets.TargetIdentityMismatch, match="revision"):
        targets.validate_local_snapshot_identity(
            "/scratch/hf_cache/hub/models--google--gemma-3-12b-it/snapshots/abc123",
            targets.GEMMA_3_12B_IT_TARGET, which="model", expected_revision="deadbeef",
        )


def test_validate_local_snapshot_identity_does_not_raise_on_non_cache_path():
    # Cannot verify != confirmed mismatch -- a hand-staged directory must not
    # be treated as a false positive.
    targets.validate_local_snapshot_identity(
        "/home/y/yazid/hand_staged_gemma_it", targets.GEMMA_3_12B_IT_TARGET, which="model",
    )  # must not raise


# ---------------------------------------------------------------------------
# validate_hidden_dims / validate_hook_identity / validate_qwen_layer_choice
# ---------------------------------------------------------------------------


def test_validate_hidden_dims_passes_when_all_agree():
    targets.validate_hidden_dims(3840, 3840, targets.GEMMA_3_12B_IT_TARGET)  # must not raise


def test_validate_hidden_dims_raises_on_model_sae_mismatch():
    with pytest.raises(targets.TargetIdentityMismatch, match="d_in"):
        targets.validate_hidden_dims(3840, 4096, targets.GEMMA_3_12B_IT_TARGET)


def test_validate_hidden_dims_raises_on_disagreement_with_ratified_expectation():
    with pytest.raises(targets.TargetIdentityMismatch, match="expected_hidden_dim"):
        targets.validate_hidden_dims(4096, 4096, targets.GEMMA_3_12B_IT_TARGET)


def test_validate_hook_identity_exact_match_for_registry_target():
    targets.validate_hook_identity("blocks.31.hook_resid_post", targets.GEMMA_3_12B_IT_TARGET)  # must not raise
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_hook_identity("blocks.24.hook_resid_post", targets.GEMMA_3_12B_IT_TARGET)


def test_validate_hook_identity_substring_match_for_raw_pt_target():
    targets.validate_hook_identity("resid_post:layer_40", targets.QWEN_3_5_27B_TARGET)  # must not raise
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_hook_identity("resid_pre:layer_40", targets.QWEN_3_5_27B_TARGET)


def test_validate_qwen_layer_choice_accepts_in_range():
    targets.validate_qwen_layer_choice(0, targets.QWEN_3_5_27B_TARGET)
    targets.validate_qwen_layer_choice(63, targets.QWEN_3_5_27B_TARGET)


def test_validate_qwen_layer_choice_rejects_out_of_range():
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_qwen_layer_choice(64, targets.QWEN_3_5_27B_TARGET)
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_qwen_layer_choice(-1, targets.QWEN_3_5_27B_TARGET)
