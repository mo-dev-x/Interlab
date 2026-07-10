"""§8.2 test_identity: noop spec => bit-identical logits and generations;
ALSO generated_only with all positions masked => bit-identical (ED-4).
(Nightly identity-on-real-Qwen lives in test_interventions_identity_nightly.py,
§8.3's cluster/nightly CI lane, not this per-commit test -- ED-23.)
"""

import torch

from interplab.interventions import InterventionSpec, attach

_HASH = "sha256:" + "a" * 64
_PROMPT = "The cheese feature fires today."


def test_noop_bit_identical_logits(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        baseline = model(ids)

    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    with torch.no_grad(), attach(model, tiny_sae, spec):
        noop_logits = model(ids)

    assert torch.equal(baseline, noop_logits)


def test_noop_bit_identical_generation(tiny_hooked_transformer, tiny_sae):
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        baseline_gen = model.generate(ids, max_new_tokens=5, do_sample=False, verbose=False)

    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    with torch.no_grad(), attach(model, tiny_sae, spec):
        noop_gen = model.generate(ids, max_new_tokens=5, do_sample=False, verbose=False)

    assert torch.equal(baseline_gen, noop_gen)


def test_generated_only_steers_decode_steps_but_not_prefill(tiny_hooked_transformer, tiny_sae):
    """ED-4: absolute position must be tracked correctly across KV-cached
    decoding steps -- the prefill call (positions < prompt_lengths) must
    stay untouched while later single-token decode calls (positions >=
    prompt_lengths) get steered."""
    from transformer_lens.past_key_value_caching import HookedTransformerKeyValueCache

    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    prompt_len = ids.shape[1]
    next_token = torch.tensor([[7]])

    baseline_cache = HookedTransformerKeyValueCache.init_cache(model.cfg, "cpu", 1)
    with torch.no_grad():
        prefill_baseline = model(ids, past_kv_cache=baseline_cache)
        decode_baseline = model(next_token, past_kv_cache=baseline_cache)

    spec = InterventionSpec(
        kind="clamp", feature_index=0, value_in_max_units=5.0, corpus_max=1.0,
        positions="generated_only", checkpoint_hash=_HASH,
    )
    steered_cache = HookedTransformerKeyValueCache.init_cache(model.cfg, "cpu", 1)
    with torch.no_grad(), attach(model, tiny_sae, spec, prompt_lengths=prompt_len):
        prefill_steered = model(ids, past_kv_cache=steered_cache)
        decode_steered = model(next_token, past_kv_cache=steered_cache)

    assert torch.equal(prefill_baseline, prefill_steered)
    assert not torch.equal(decode_baseline, decode_steered)


def test_generated_only_fully_masked_is_bit_identical(tiny_hooked_transformer, tiny_sae):
    """ED-4: a non-noop spec whose prompt_lengths boundary lies beyond the
    entire sequence steers nothing -- masked positions get no encode/decode
    at all, so the result is bit-identical to not attaching anything."""
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]

    with torch.no_grad():
        baseline = model(ids)

    spec = InterventionSpec(
        kind="clamp", feature_index=0, value_in_max_units=2.0, corpus_max=1.0,
        positions="generated_only", checkpoint_hash=_HASH,
    )
    with torch.no_grad(), attach(model, tiny_sae, spec, prompt_lengths=ids.shape[1] + 1000):
        masked_logits = model(ids)

    assert torch.equal(baseline, masked_logits)


def test_heterogeneous_batch_masked_row_is_bitwise_untouched(tiny_hooked_transformer, tiny_sae):
    """Structural-selection regression: in a 2-row batch where row 0 is
    fully masked (generated_only, prompt_lengths beyond the sequence) and
    row 1 is fully unmasked (prompt_lengths=0), row 0's output must be
    bitwise identical to the unattached baseline while row 1 differs."""
    model = tiny_hooked_transformer
    ids = model.tokenizer(_PROMPT, return_tensors="pt")["input_ids"]
    batch_ids = torch.cat([ids, ids], dim=0)
    seq_len = batch_ids.shape[1]

    with torch.no_grad():
        baseline = model(batch_ids)

    spec = InterventionSpec(
        kind="clamp", feature_index=0, value_in_max_units=5.0, corpus_max=1.0,
        positions="generated_only", checkpoint_hash=_HASH,
    )
    prompt_lengths = [seq_len + 1000, 0]  # row 0: fully masked, row 1: fully unmasked
    with torch.no_grad(), attach(model, tiny_sae, spec, prompt_lengths=prompt_lengths):
        steered = model(batch_ids)

    assert torch.equal(steered[0], baseline[0])
    assert not torch.equal(steered[1], baseline[1])
