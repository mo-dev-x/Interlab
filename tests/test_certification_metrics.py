"""§5 SS4 certification metrics: fp32, fresh-collection CE-recovered
(zero-ablation baseline), FVU, dead-fraction, density histogram,
max_decoder_cosine_p999 (ED-5 exact pin)."""

import dataclasses

import pytest
import torch
from sae_lens import SAE
from sae_lens.saes.sae import SAEMetadata
from sae_lens.saes.standard_sae import StandardSAE, StandardSAEConfig

from interplab.certification.metrics import (
    compute_metrics,
    max_decoder_cosine_p999,
    squared_error_and_total,
)


def _make_sae(d_in: int, d_sae: int, w_dec: torch.Tensor, *, hook_name: str = "blocks.1.hook_resid_post") -> SAE:
    # ED-33: "standard" architecture always uses ReLU under sae-lens 6.x --
    # no activation_fn_str/activation_fn_kwargs needed (those were the 3.x
    # way to select an activation; StandardSAEConfig has no such fields).
    cfg = StandardSAEConfig(
        d_in=d_in, d_sae=d_sae, apply_b_dec_to_input=False,
        normalize_activations="none", dtype="float32", device="cpu",
        metadata=SAEMetadata(model_name="test", hook_name=hook_name, hook_layer=1, context_size=16),
    )
    sae = StandardSAE(cfg)
    with torch.no_grad():
        sae.W_dec.copy_(w_dec)
    return sae


# ---- squared_error_and_total ----


def test_squared_error_zero_for_perfect_reconstruction():
    x = torch.tensor([[[1.0, 2.0, -3.0]]])
    sq_error, _ = squared_error_and_total(x, x)
    assert torch.equal(sq_error, torch.zeros_like(sq_error))


def test_squared_total_matches_hand_computed_variance():
    # Two positions, d=1: values 1.0 and 3.0 -> mean 2.0 -> sq deviations [1, 1]
    x = torch.tensor([[[1.0], [3.0]]])
    recon = torch.zeros_like(x)
    _, sq_total = squared_error_and_total(x, recon)
    assert torch.allclose(sq_total, torch.tensor([[1.0, 1.0]]))


# ---- max_decoder_cosine_p999 ----


def test_duplicate_decoder_directions_give_p999_of_one():
    w_dec = torch.tensor([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
    sae = _make_sae(4, 3, w_dec)
    assert max_decoder_cosine_p999(sae) == pytest.approx(1.0)


def test_orthogonal_decoder_directions_give_p999_of_zero():
    w_dec = torch.eye(3)
    sae = _make_sae(3, 3, w_dec)
    assert max_decoder_cosine_p999(sae) == pytest.approx(0.0)


def test_chunking_does_not_change_the_result():
    torch.manual_seed(0)
    w_dec = torch.randn(37, 8)
    sae = _make_sae(8, 37, w_dec)
    unchunked = max_decoder_cosine_p999(sae, chunk_size=1000)
    chunked = max_decoder_cosine_p999(sae, chunk_size=5)
    assert unchunked == pytest.approx(chunked, abs=1e-5)


# ---- compute_metrics integration (against the pinned tiny fixtures) ----


def test_compute_metrics_runs_and_returns_plausible_shapes(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    torch.manual_seed(0)
    seq_len = 16
    batches = [torch.randint(0, model.cfg.d_vocab, (4, seq_len)) for _ in range(2)]

    metrics = compute_metrics(model, tiny_sae, tiny_sae.cfg.metadata.hook_name, batches)

    assert 0.0 <= metrics.dead_fraction <= 1.0
    assert metrics.fvu >= 0.0
    assert len(metrics.per_position_fvu) == seq_len
    assert all(v >= 0.0 for v in metrics.per_position_fvu)
    assert sum(metrics.density_histogram["counts"]) <= tiny_sae.cfg.d_sae
    assert len(metrics.density_histogram["bin_edges_log10"]) == len(metrics.density_histogram["counts"]) + 1
    assert isinstance(metrics.ce_recovered, float)
    assert isinstance(metrics.max_decoder_cosine_p999, float)


def test_compute_metrics_rejects_mismatched_sequence_lengths(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    batches = [torch.randint(0, model.cfg.d_vocab, (2, 16)), torch.randint(0, model.cfg.d_vocab, (2, 8))]
    with pytest.raises(ValueError):
        compute_metrics(model, tiny_sae, tiny_sae.cfg.metadata.hook_name, batches)


def test_compute_metrics_works_with_bf16_stored_sae(tiny_hooked_transformer, tiny_sae):
    """SS4 invariant: metrics computed in fp32 regardless of the checkpoint's
    native storage dtype."""
    bf16_cfg = dataclasses.replace(tiny_sae.cfg, dtype="bfloat16")
    sae_bf16 = type(tiny_sae)(bf16_cfg)
    sae_bf16.load_state_dict({k: v.to(torch.bfloat16) for k, v in tiny_sae.state_dict().items()})

    model = tiny_hooked_transformer
    torch.manual_seed(0)
    batches = [torch.randint(0, model.cfg.d_vocab, (2, 16))]
    metrics = compute_metrics(model, sae_bf16, sae_bf16.cfg.metadata.hook_name, batches)
    assert isinstance(metrics.fvu, float)


def test_dead_fraction_is_one_when_no_features_ever_fire(tiny_hooked_transformer):
    # A SAE whose decoder/encoder are zeroed: TopK will still pick k indices per
    # position (TopK always activates exactly k), so use activation_fn "relu"
    # with a very negative bias instead, guaranteeing every pre-activation is
    # negative and every feature is dead everywhere.
    d_in = tiny_hooked_transformer.cfg.d_model
    cfg = StandardSAEConfig(
        d_in=d_in, d_sae=16, apply_b_dec_to_input=False,
        normalize_activations="none", dtype="float32", device="cpu",
        metadata=SAEMetadata(model_name="test", hook_name="blocks.1.hook_resid_post", hook_layer=1, context_size=16),
    )
    sae = StandardSAE(cfg)
    with torch.no_grad():
        sae.W_enc.zero_()
        sae.b_enc.fill_(-1000.0)

    torch.manual_seed(0)
    batches = [torch.randint(0, tiny_hooked_transformer.cfg.d_vocab, (2, 16))]
    metrics = compute_metrics(tiny_hooked_transformer, sae, sae.cfg.metadata.hook_name, batches)
    assert metrics.dead_fraction == 1.0
