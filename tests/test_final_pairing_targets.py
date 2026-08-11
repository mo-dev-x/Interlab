"""Pure-Python tests for scripts/legacy/final_pairing_targets.py: the
ratified target identities and the fail-closed validators. No torch, no
GPU, no network, no real weights -- everything here is strings/ints/dicts.
"""

from __future__ import annotations

import os
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


def test_qwen_target_expected_runtime_class_is_causal_lm():
    """Orchestrator review, 2026-08-11: Tamia's actual transformers==5.14.1
    dispatches model_type="qwen3_5" through AutoModelForCausalLM to
    Qwen3_5ForCausalLM, not the multimodal Qwen3_5ForConditionalGeneration
    this harness previously loaded via AutoModelForImageTextToText."""
    assert targets.QWEN_3_5_27B_TARGET.expected_runtime_class == "Qwen3_5ForCausalLM"


def test_gemma_target_has_no_expected_runtime_class():
    """The Gemma provenance path is untouched by the 2026-08-11 Qwen
    review -- it never gained this field."""
    assert targets.GEMMA_3_12B_IT_TARGET.expected_runtime_class is None


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


def test_validate_local_snapshot_identity_passes_on_matching_repo_and_returns_provenance():
    provenance = targets.validate_local_snapshot_identity(
        "/scratch/hf_cache/hub/models--google--gemma-3-12b-it/snapshots/abc123",
        targets.GEMMA_3_12B_IT_TARGET, which="model",
    )
    assert provenance == {"verification": "hf_cache_layout", "repo_id": "google/gemma-3-12b-it", "revision": "abc123"}


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


def test_validate_local_snapshot_identity_raises_identity_unverified_without_expected_revision():
    """Orchestrator review, 2026-08-10: a prior version of this test asserted
    the OLD (wrong) behavior -- that a non-cache-layout path silently passed
    with no expected_revision given. That was "claiming fail-closed
    verification while silently continuing." The corrected contract: refuse
    acceptance rather than treat "cannot verify from the path" as "verified.\""""
    with pytest.raises(targets.IdentityUnverified):
        targets.validate_local_snapshot_identity(
            "/home/y/yazid/hand_staged_gemma_it", targets.GEMMA_3_12B_IT_TARGET, which="model",
        )


def test_validate_local_snapshot_identity_accepts_non_cache_path_with_explicit_expected_revision():
    """The other half of the fix: a hand-staged path IS acceptable if the
    caller supplies trusted inventory provenance (Lab Assistant 1's
    declared revision) -- recorded as explicitly declared, not path-derived,
    so a reader of the JSON trace can tell the two verification modes apart."""
    provenance = targets.validate_local_snapshot_identity(
        "/home/y/yazid/hand_staged_gemma_it", targets.GEMMA_3_12B_IT_TARGET, which="model",
        expected_revision="deadbeef",
    )
    assert provenance == {
        "verification": "explicit_revision_declared_not_path_derived",
        "repo_id": "google/gemma-3-12b-it",
        "revision": "deadbeef",
    }


def test_identity_unverified_is_a_target_identity_mismatch():
    # So a caller catching the general fail-closed exception still catches this.
    assert issubclass(targets.IdentityUnverified, targets.TargetIdentityMismatch)


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


# ---------------------------------------------------------------------------
# validate_finite_positive -- zero, negative, NaN, infinite raw STEER values
# ---------------------------------------------------------------------------


def test_validate_finite_positive_accepts_ordinary_value():
    targets.validate_finite_positive(5000.0, label="x")  # must not raise


@pytest.mark.parametrize("bad_value", [0.0, -1.0, -0.0001])
def test_validate_finite_positive_rejects_non_positive(bad_value):
    with pytest.raises(targets.TargetIdentityMismatch, match="non-positive"):
        targets.validate_finite_positive(bad_value, label="x")


def test_validate_finite_positive_rejects_nan():
    with pytest.raises(targets.TargetIdentityMismatch, match="not finite"):
        targets.validate_finite_positive(float("nan"), label="x")


def test_validate_finite_positive_rejects_infinite():
    with pytest.raises(targets.TargetIdentityMismatch, match="not finite"):
        targets.validate_finite_positive(float("inf"), label="x")
    with pytest.raises(targets.TargetIdentityMismatch, match="not finite"):
        targets.validate_finite_positive(float("-inf"), label="x")


# ---------------------------------------------------------------------------
# validate_feature_index
# ---------------------------------------------------------------------------


def test_validate_feature_index_accepts_in_range():
    targets.validate_feature_index(0, 100)
    targets.validate_feature_index(99, 100)


def test_validate_feature_index_rejects_out_of_range():
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_feature_index(100, 100)
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_feature_index(-1, 100)


# ---------------------------------------------------------------------------
# validate_qwen_layer_filename
# ---------------------------------------------------------------------------


def test_validate_qwen_layer_filename_accepts_matching_layer():
    targets.validate_qwen_layer_filename("/scratch/qwen_scope/layer31.sae.pt", 31)  # must not raise


def test_validate_qwen_layer_filename_rejects_mismatched_layer():
    with pytest.raises(targets.TargetIdentityMismatch, match="layer 31"):
        targets.validate_qwen_layer_filename("/scratch/qwen_scope/layer31.sae.pt", 40)


def test_validate_qwen_layer_filename_rejects_unrecognized_naming():
    with pytest.raises(targets.TargetIdentityMismatch, match="convention"):
        targets.validate_qwen_layer_filename("/scratch/qwen_scope/checkpoint.pt", 31)


# ---------------------------------------------------------------------------
# validate_qwen_sae_shapes / validate_qwen_k
# ---------------------------------------------------------------------------


def test_validate_qwen_sae_shapes_accepts_ratified_shapes():
    targets.validate_qwen_sae_shapes(
        w_enc_shape=(81920, 5120), b_enc_shape=(81920,), w_dec_shape=(5120, 81920), b_dec_shape=(5120,),
        target=targets.QWEN_3_5_27B_TARGET,
    )  # must not raise


def test_validate_qwen_sae_shapes_rejects_missing_b_dec():
    """Orchestrator review, 2026-08-11: b_dec is no longer an optional,
    unconfirmed key -- the release's own checkpoint contract lists it as
    present, so b_dec_shape=None is now itself a contract violation."""
    with pytest.raises(targets.TargetIdentityMismatch, match="b_dec"):
        targets.validate_qwen_sae_shapes(
            w_enc_shape=(81920, 5120), b_enc_shape=(81920,), w_dec_shape=(5120, 81920), b_dec_shape=None,
            target=targets.QWEN_3_5_27B_TARGET,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"w_enc_shape": (100, 5120), "b_enc_shape": (81920,), "w_dec_shape": (5120, 81920), "b_dec_shape": (5120,)},
        {"w_enc_shape": (81920, 5120), "b_enc_shape": (100,), "w_dec_shape": (5120, 81920), "b_dec_shape": (5120,)},
        {"w_enc_shape": (81920, 5120), "b_enc_shape": (81920,), "w_dec_shape": (100, 81920), "b_dec_shape": (5120,)},
        {"w_enc_shape": (81920, 5120), "b_enc_shape": (81920,), "w_dec_shape": (5120, 81920), "b_dec_shape": (100,)},
    ],
)
def test_validate_qwen_sae_shapes_rejects_any_mismatched_shape(kwargs):
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_qwen_sae_shapes(target=targets.QWEN_3_5_27B_TARGET, **kwargs)


def test_validate_qwen_k_accepts_ratified_k():
    targets.validate_qwen_k(50, targets.QWEN_3_5_27B_TARGET)  # must not raise


def test_validate_qwen_k_rejects_mismatched_k():
    with pytest.raises(targets.TargetIdentityMismatch, match="structural"):
        targets.validate_qwen_k(100, targets.QWEN_3_5_27B_TARGET)


# ---------------------------------------------------------------------------
# validate_sae_files_match_snapshot -- proves the registry loader actually
# read from the validated snapshot rather than an independently resolved one.
# ---------------------------------------------------------------------------


def test_validate_sae_files_match_snapshot_accepts_files_under_the_snapshot(tmp_path):
    snapshot = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    resolved = [str(snapshot / "cfg.json"), str(snapshot / "sae_weights.safetensors")]
    targets.validate_sae_files_match_snapshot(resolved, snapshot, targets.GEMMA_3_12B_IT_TARGET)  # must not raise


def test_validate_sae_files_match_snapshot_rejects_files_outside_the_snapshot(tmp_path):
    """The exact defect orchestrator review found: the registry loader
    resolving a DIFFERENT cached revision than the one that was validated."""
    validated_snapshot = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    validated_snapshot.mkdir(parents=True)
    different_revision = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "deadbeef"
    different_revision.mkdir(parents=True)
    resolved = [str(different_revision / "cfg.json")]
    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_files_match_snapshot(resolved, validated_snapshot, targets.GEMMA_3_12B_IT_TARGET)


def test_validate_sae_files_match_snapshot_rejects_empty_resolution(tmp_path):
    snapshot = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    with pytest.raises(targets.TargetIdentityMismatch, match="zero local files"):
        targets.validate_sae_files_match_snapshot([], snapshot, targets.GEMMA_3_12B_IT_TARGET)


# ---------------------------------------------------------------------------
# validate_runtime_class / validate_has_callable_generate -- orchestrator
# review, 2026-08-11: require the loaded class to be the expected Qwen3.5
# causal-generation class with a callable .generate().
# ---------------------------------------------------------------------------


def test_validate_runtime_class_accepts_matching_class():
    targets.validate_runtime_class("Qwen3_5ForCausalLM", targets.QWEN_3_5_27B_TARGET)  # must not raise


def test_validate_runtime_class_rejects_mismatched_class():
    with pytest.raises(targets.TargetIdentityMismatch, match="Qwen3_5ForCausalLM"):
        targets.validate_runtime_class("Qwen3_5ForConditionalGeneration", targets.QWEN_3_5_27B_TARGET)


def test_validate_runtime_class_is_a_noop_when_target_has_no_expected_class():
    # GEMMA_3_12B_IT_TARGET.expected_runtime_class is None -- nothing to check.
    targets.validate_runtime_class("anything at all", targets.GEMMA_3_12B_IT_TARGET)  # must not raise


class _NoGenerate:
    pass


class _HasGenerate:
    def generate(self, **kwargs):
        return "ok"


class _GenerateNotCallable:
    generate = "not a method"


def test_validate_has_callable_generate_accepts_callable_generate():
    targets.validate_has_callable_generate(_HasGenerate(), label="x")  # must not raise


def test_validate_has_callable_generate_rejects_missing_generate():
    with pytest.raises(targets.TargetIdentityMismatch, match="generate"):
        targets.validate_has_callable_generate(_NoGenerate(), label="x")


def test_validate_has_callable_generate_rejects_non_callable_generate_attribute():
    with pytest.raises(targets.TargetIdentityMismatch, match="generate"):
        targets.validate_has_callable_generate(_GenerateNotCallable(), label="x")


# ---------------------------------------------------------------------------
# validate_sae_files_match_expected_subdirectory -- orchestrator review,
# 2026-08-12: the final Gemma Scope IT snapshot ships FIVE different SAE
# families sharing the identical "layer_31_width_16k_l0_medium" suffix
# (attn_out, mlp_out, resid_post, transcoder, transcoder affine). This
# proves the loaded files belong to exactly the ratified resid_post family,
# not merely somewhere under the correctly-validated snapshot.
# ---------------------------------------------------------------------------


def _gemma_snapshot(tmp_path):
    snapshot = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    return snapshot


def test_validate_sae_subdirectory_accepts_resid_post_files(tmp_path):
    snapshot = _gemma_snapshot(tmp_path)
    resolved = [
        str(snapshot / "resid_post" / "layer_31_width_16k_l0_medium" / "cfg.json"),
        str(snapshot / "resid_post" / "layer_31_width_16k_l0_medium" / "sae_weights.safetensors"),
    ]
    provenance = targets.validate_sae_files_match_expected_subdirectory(
        resolved, snapshot, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance == {
        "expected_sae_subdirectory": "resid_post/layer_31_width_16k_l0_medium",
        "sae_subdirectory_membership_verified": True,
    }


@pytest.mark.parametrize("sibling_family", ["attn_out", "mlp_out", "transcoder", "transcoder affine"])
def test_validate_sae_subdirectory_rejects_sibling_families(tmp_path, sibling_family):
    """The exact failure mode this check exists to catch: a sibling SAE
    family sharing the identical layer/width/l0 suffix, living under the
    SAME correctly-validated snapshot -- proving snapshot-level validation
    alone (validate_sae_files_match_snapshot) is insufficient."""
    snapshot = _gemma_snapshot(tmp_path)
    resolved = [str(snapshot / sibling_family / "layer_31_width_16k_l0_medium" / "cfg.json")]
    with pytest.raises(targets.TargetIdentityMismatch, match=sibling_family):
        targets.validate_sae_files_match_expected_subdirectory(resolved, snapshot, targets.GEMMA_3_12B_IT_TARGET)


@pytest.mark.parametrize(
    "bad_relative_path",
    [
        "resid_post_v2/layer_31_width_16k_l0_medium/cfg.json",
        "resid_post/layer_31_width_16k_l0_medium_v2/cfg.json",
        "xresid_post/layer_31_width_16k_l0_medium/cfg.json",
        "resid_post/layer_31_width_16k_l0_mediumX/cfg.json",
    ],
)
def test_validate_sae_subdirectory_rejects_similarly_named_prefixes_and_suffixes(tmp_path, bad_relative_path):
    """Full-path-segment comparison, not substring/startswith -- a name
    that merely shares a prefix or suffix with the ratified subdirectory
    must not be accepted."""
    snapshot = _gemma_snapshot(tmp_path)
    resolved = [str(snapshot / bad_relative_path)]
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_sae_files_match_expected_subdirectory(resolved, snapshot, targets.GEMMA_3_12B_IT_TARGET)


def test_validate_sae_subdirectory_rejects_zero_files():
    with pytest.raises(targets.TargetIdentityMismatch, match="zero resolved"):
        targets.validate_sae_files_match_expected_subdirectory([], "/some/snapshot", targets.GEMMA_3_12B_IT_TARGET)


def test_validate_sae_subdirectory_rejects_files_outside_the_snapshot_entirely(tmp_path):
    snapshot = _gemma_snapshot(tmp_path)
    other_dir = tmp_path / "somewhere_else" / "resid_post" / "layer_31_width_16k_l0_medium" / "cfg.json"
    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_sae_files_match_expected_subdirectory(
            [str(other_dir)], snapshot, targets.GEMMA_3_12B_IT_TARGET
        )


def test_validate_sae_subdirectory_does_not_follow_resolve_style_symlink_paths(tmp_path):
    """Regression guard for the exact failure mode this check must avoid:
    a real huggingface_hub cache entry is a SYMLINK whose target physically
    lives outside the snapshot (in a sibling blobs/ directory) -- the check
    must still pass, since it is keyed off the file's OWN snapshot-relative
    path, never off Path.resolve()/os.path.realpath following the symlink
    to its target."""
    snapshot = _gemma_snapshot(tmp_path)
    blob_dir = tmp_path / "models--google--gemma-scope-2-12b-it" / "blobs"
    blob_dir.mkdir(parents=True)
    blob_target = blob_dir / "deadbeefcafe"
    blob_target.write_bytes(b"fake sae weights")
    sae_dir = snapshot / "resid_post" / "layer_31_width_16k_l0_medium"
    sae_dir.mkdir(parents=True)
    symlink_path = sae_dir / "sae_weights.safetensors"
    try:
        symlink_path.symlink_to(blob_target)
    except OSError:
        pytest.skip("creating a symlink requires elevated privileges on this machine")

    provenance = targets.validate_sae_files_match_expected_subdirectory(
        [str(symlink_path)], snapshot, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True


# ---------------------------------------------------------------------------
# _hf_repository_cache_root / validate_sae_symlink_targets_stay_in_repository_
# cache -- addendum, 2026-08-12 ("HF snapshot symlink containment"): the
# LOGICAL check above never dereferences a symlink, by design -- so it
# cannot, by itself, catch a symlink whose target has been swapped to point
# somewhere outside this repository's own cache entirely. This PHYSICAL
# check is the complementary half: it dereferences ONLY real on-disk
# symlinks, and confirms the target stays within the same repository cache
# root, without requiring the flat blobs/ store to retain any sae_id
# directory structure.
# ---------------------------------------------------------------------------


def test_hf_repository_cache_root_extracts_repo_root_from_snapshot_path():
    root = targets._hf_repository_cache_root(
        "/scratch/hf_cache/hub/models--google--gemma-scope-2-12b-it/snapshots/abc123"
    )
    assert root == Path("/scratch/hf_cache/hub/models--google--gemma-scope-2-12b-it")


def test_hf_repository_cache_root_returns_none_for_non_cache_layout():
    assert targets._hf_repository_cache_root("/home/y/yazid/hand_staged_sae_dir") is None


def test_validate_sae_symlink_targets_accepts_mocked_symlink_inside_cache_root(tmp_path, monkeypatch):
    """Deterministic proof of the accept branch on ANY machine, regardless
    of local symlink-creation privileges: mocks Path.is_symlink/
    os.path.realpath rather than requiring a real filesystem symlink (see
    the realistic-cache-shape tests below for the real-filesystem version,
    which skips where privileges are unavailable)."""
    snapshot_dir = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    snapshot_dir.mkdir(parents=True)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    dereferenced = tmp_path / "models--google--gemma-scope-2-12b-it" / "blobs" / "deadbeef"

    monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(link_path))
    monkeypatch.setattr(os.path, "realpath", lambda p: str(dereferenced) if str(p) == str(link_path) else p)

    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


def test_validate_sae_symlink_targets_rejects_mocked_symlink_escaping_cache_root(tmp_path, monkeypatch):
    """Deterministic proof of the reject branch on ANY machine."""
    snapshot_dir = tmp_path / "models--google--gemma-scope-2-12b-it" / "snapshots" / "abc123"
    snapshot_dir.mkdir(parents=True)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    dereferenced = tmp_path / "some_other_repo" / "blobs" / "deadbeef"

    monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(link_path))
    monkeypatch.setattr(os.path, "realpath", lambda p: str(dereferenced) if str(p) == str(link_path) else p)

    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_symlink_targets_stay_in_repository_cache(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )


def test_validate_sae_symlink_targets_is_noop_for_non_symlink_files(tmp_path):
    """No real file (let alone a symlink) exists at this path at all --
    Path.is_symlink() returns False, not an error -- so there is nothing to
    dereference and no physical-safety claim to make."""
    snapshot = _gemma_snapshot(tmp_path)
    resolved = [str(snapshot / "resid_post" / "layer_31_width_16k_l0_medium" / "cfg.json")]
    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        resolved, snapshot, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


def test_validate_sae_symlink_targets_is_noop_for_hand_staged_sae_path(tmp_path):
    """No HF cache layout at all -- no blobs/ convention exists to bound a
    symlink target against, so this check has nothing to do."""
    hand_staged = tmp_path / "hand_staged_sae_dir"
    hand_staged.mkdir()
    resolved = [str(hand_staged / "resid_post" / "layer_31_width_16k_l0_medium" / "cfg.json")]
    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        resolved, hand_staged, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


def _build_realistic_hf_cache(tmp_path):
    """A realistic huggingface_hub cache skeleton:
        models--google--gemma-scope-2-12b-it/
          blobs/<blob-id>
          snapshots/<revision>/
    Returns (repo_root, snapshot_dir, blob_path)."""
    repo_root = tmp_path / "models--google--gemma-scope-2-12b-it"
    blob_path = repo_root / "blobs" / "deadbeefcafe0123"
    blob_path.parent.mkdir(parents=True)
    blob_path.write_bytes(b"fake sae weights")
    snapshot_dir = repo_root / "snapshots" / "abc123"
    snapshot_dir.mkdir(parents=True)
    return repo_root, snapshot_dir, blob_path


def _symlink_or_skip(link_path, target_path):
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_path.symlink_to(target_path)
    except OSError:
        pytest.skip("creating a symlink requires elevated privileges on this machine")


def test_realistic_hf_cache_intended_resid_post_symlink_passes_both_checks(tmp_path):
    """The intended symlink must pass: snapshots/<revision>/resid_post/
    layer_31_width_16k_l0_medium/config.json -> .../blobs/<blob-id>, the
    exact realistic shape a real Gemma Scope IT download produces."""
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink_or_skip(link_path, blob_path)

    provenance = targets.validate_sae_files_match_expected_subdirectory(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True
    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise


@pytest.mark.parametrize("sibling_family", ["attn_out", "mlp_out", "transcoder"])
def test_realistic_hf_cache_sibling_family_symlink_fails_logical_check_only(tmp_path, sibling_family):
    """A logical entry under attn_out/mlp_out/transcoder must fail -- even
    though its symlink target is a perfectly legitimate blob in the SAME
    repository cache, proving the two checks are genuinely independent:
    the physical check alone would NOT catch a merely-mis-filed family."""
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / sibling_family / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink_or_skip(link_path, blob_path)

    with pytest.raises(targets.TargetIdentityMismatch, match=sibling_family):
        targets.validate_sae_files_match_expected_subdirectory(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )
    targets.validate_sae_symlink_targets_stay_in_repository_cache(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )  # must not raise -- the blob itself is legitimately in-cache


def test_realistic_hf_cache_sibling_prefix_symlink_fails_logical_check(tmp_path):
    """A l0_medium_v2 sibling-prefix path must fail, even as a real
    symlink into a legitimate blob."""
    _repo_root, snapshot_dir, blob_path = _build_realistic_hf_cache(tmp_path)
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium_v2" / "config.json"
    _symlink_or_skip(link_path, blob_path)

    with pytest.raises(targets.TargetIdentityMismatch):
        targets.validate_sae_files_match_expected_subdirectory(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )


def test_realistic_hf_cache_symlink_escaping_repository_cache_fails_physical_check(tmp_path):
    """A symlink escaping the repository cache must fail -- even though
    its OWN logical (snapshot-relative) location is exactly the ratified
    subdirectory, proving the logical check alone would NOT catch a
    swapped/escaping physical target; only the physical check inspects
    where the symlink actually points."""
    _repo_root, snapshot_dir, _blob_path = _build_realistic_hf_cache(tmp_path)
    outside_target = tmp_path / "some_other_repo" / "blobs" / "deadbeefcafe0123"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_bytes(b"fake weights from a different repository")
    link_path = snapshot_dir / "resid_post" / "layer_31_width_16k_l0_medium" / "config.json"
    _symlink_or_skip(link_path, outside_target)

    provenance = targets.validate_sae_files_match_expected_subdirectory(
        [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
    )
    assert provenance["sae_subdirectory_membership_verified"] is True
    with pytest.raises(targets.TargetIdentityMismatch, match="OUTSIDE"):
        targets.validate_sae_symlink_targets_stay_in_repository_cache(
            [str(link_path)], snapshot_dir, targets.GEMMA_3_12B_IT_TARGET
        )
