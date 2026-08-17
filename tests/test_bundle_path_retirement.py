"""Controls for retiring the sequential bundle intervention path.

Architect RULING_13 Q3 named three defects in `_bundle_hook_fn` /
`run_intervention` in `scripts/final_pairing/final_pairing_concept_discovery
.py`. They are not repaired in place: the path is RETIRED and
`run_intervention` now builds its hook through the group primitive in
`scripts/final_pairing/group_intervention.py`. Removing the ability beats
requiring the restraint -- two intervention implementations, one of them
order-dependent to ~71% of its own signal, IS the hazard, and fixing one
while leaving both preserves it.

EVERY CLAIM HERE IS MEASURED ON THE SAME RESIDUAL, BEFORE AND AFTER. The
retired composition is reconstructed locally from `_make_clamp_hook` --
exactly the two lines the tombstone describes -- because the function
itself now raises. Reconstructing it is what makes the contrast a
measurement rather than a memory of one.

This file does not edit, and does not need, `group_intervention.py` or its
tests; it imports the primitive and uses the same committed CPU fixtures.
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "final_pairing"))

import final_pairing_concept_discovery as d  # noqa: E402

PROMPT = "The quick brown fox jumps over the lazy dog."


@pytest.fixture(scope="module")
def gi():
    return d._import_group_intervention()


@pytest.fixture(scope="module")
def real_model():
    from interplab.certification.model_loading import load_local_hooked_transformer

    return load_local_hooked_transformer(str(REPO_ROOT / "tests" / "fixtures" / "tiny_model"))


@pytest.fixture(scope="module")
def real_sae():
    from sae_lens import SAE

    return SAE.load_from_pretrained(str(REPO_ROOT / "tests" / "fixtures" / "tiny_sae"), device="cpu")


@pytest.fixture(scope="module")
def residual(real_model):
    tokens = real_model.to_tokens([PROMPT])
    with torch.no_grad():
        _logits, cache = real_model.run_with_cache(tokens, names_filter="blocks.1.hook_resid_post")
    return cache["blocks.1.hook_resid_post"]


def _live_features(sae, resid, limit=3):
    feats = sae.encode(resid.to(torch.float32))
    per_feature = feats.abs().amax(dim=tuple(range(feats.ndim - 1)))
    return [int(i) for i in torch.argsort(per_feature, descending=True)[:limit].tolist()]


def _retired_sequential_composition(sae, feature_indices, clamp_value, resid):
    """EXACTLY what `_bundle_hook_fn` did, reconstructed here because the
    function now raises: one `_make_clamp_hook` per member, each fed the
    PREVIOUS hook's output, and each built with an empty stats list."""
    from interplab.interventions.hooks import _make_clamp_hook

    out = resid
    for feature_index in feature_indices:
        out = _make_clamp_hook(sae, int(feature_index), clamp_value, "all", None, [])(out, None)
    return out


def _group_output(gi, sae, spec, resid):
    ledger = gi.FiringLedger()
    hook_fn, _resolved = gi.build_group_hook(sae, spec, ledger=ledger)
    return hook_fn(resid), ledger


# ---------------------------------------------------------------------------
# The retirement itself
# ---------------------------------------------------------------------------


def test_the_retired_path_raises_rather_than_running():
    """A raising tombstone, not a deletion: a caller learns WHY instead of
    getting an AttributeError, and cannot reach the defective composition
    at all."""
    with pytest.raises(d.RetiredBundlePath, match="order-dependent"):
        d._bundle_hook_fn(None, [1, 2], 0.0, "all", None, [])


def test_the_group_primitive_is_loaded_by_file_identity_not_by_name(gi):
    """The `sys.path` landmine: `scripts/legacy/final_pairing_concept_
    discovery.py` is a 23-line stub, and a name-based import can resolve to
    a module that is present by name and empty of what it was imported
    for."""
    assert Path(gi.__file__).resolve() == (
        REPO_ROOT / "scripts" / "final_pairing" / "group_intervention.py"
    ).resolve()
    for attribute in ("GroupSpec", "GroupMember", "FiringLedger", "build_group_hook"):
        assert hasattr(gi, attribute)


def test_a_shadowing_module_is_evicted_rather_than_accepted(gi, monkeypatch):
    """Name equality is not identity: a same-named module already in
    sys.modules pointing at other bytes must be evicted, not used."""
    import types

    decoy = types.ModuleType("group_intervention")
    decoy.__file__ = str(REPO_ROOT / "scripts" / "legacy" / "gemma3_sweep.py")
    monkeypatch.setitem(sys.modules, "group_intervention", decoy)
    reloaded = d._import_group_intervention()
    assert Path(reloaded.__file__).resolve() != Path(decoy.__file__).resolve()
    assert hasattr(reloaded, "build_group_hook")


# ---------------------------------------------------------------------------
# D1: order dependence, measured BEFORE and AFTER on the same residual
# ---------------------------------------------------------------------------


def test_order_dependence_is_fixed_measured_before_and_after(gi, real_sae, residual, capsys):
    features = _live_features(real_sae, residual, limit=3)

    before = [_retired_sequential_composition(real_sae, order, 0.0, residual)
              for order in itertools.permutations(features)]
    before_spread = max(float((out - before[0]).abs().max()) for out in before)

    after = []
    for order in itertools.permutations(features):
        spec = gi.GroupSpec(
            kind="ablate", members=tuple(gi.GroupMember(int(i)) for i in order),
            alpha=1.0, ablation_mechanism="subtract",
        )
        after.append(_group_output(gi, real_sae, spec, residual)[0])
    after_spread = max(float((out - after[0]).abs().max()) for out in after)

    magnitude = float((after[0] - residual).abs().max())
    with capsys.disabled():
        print(
            f"\n  ORDER SPREAD  before(retired sequential)={before_spread:.3e}  "
            f"after(group primitive)={after_spread:.3e}  intervention magnitude={magnitude:.4f}"
            f"  -> before is {100 * before_spread / magnitude:.1f}% of magnitude, "
            f"after is {100 * after_spread / magnitude:.6f}%"
        )

    # Relative to the intervention's own magnitude, never to an absolute
    # constant: the claim is the CONTRAST, and an absolute bound would stop
    # discriminating if the fixture's scale changed.
    assert before_spread > 0.1 * magnitude, (
        "the retired composition did not show order dependence on this fixture, so this control "
        "proves nothing -- it must be re-fixtured rather than relaxed"
    )
    assert after_spread < 1e-3 * magnitude
    assert after_spread < before_spread / 1000.0


def test_the_group_delta_is_the_simultaneous_form_not_the_chained_one(gi, real_sae, residual):
    """The corrected composition reads every member's activation from the
    ONE clean residual, so it equals the SUM of per-member deltas each
    computed on the clean residual -- which is not what chaining gives."""
    from interplab.interventions.hooks import _make_clamp_hook

    features = _live_features(real_sae, residual, limit=3)
    spec = gi.GroupSpec(
        kind="ablate", members=tuple(gi.GroupMember(int(i)) for i in features),
        alpha=1.0, ablation_mechanism="subtract",
    )
    group_out, _ledger = _group_output(gi, real_sae, spec, residual)
    clean_sum = sum(
        _make_clamp_hook(real_sae, int(i), 0.0, "all", None, [])(residual, None) - residual
        for i in features
    )
    assert torch.allclose(group_out - residual, clean_sum, atol=1e-5)
    chained = _retired_sequential_composition(real_sae, features, 0.0, residual)
    assert not torch.allclose(group_out, chained, atol=1e-3)


# ---------------------------------------------------------------------------
# D2: firing evidence at k > 1
# ---------------------------------------------------------------------------


def test_firing_evidence_is_retained_at_k_greater_than_one(gi, real_sae, residual):
    """The retired path built every inner hook with an EMPTY stats list, so
    at k>1 the firing evidence went nowhere. Here it is recorded per call,
    and `delta_norm` is the GROUP's realised delta."""
    features = _live_features(real_sae, residual, limit=3)

    # BEFORE, reconstructed: the inner hooks' own stats lists are discarded
    # by construction. Nothing to assert against except their absence.
    from interplab.interventions.hooks import _make_clamp_hook

    discarded: list = []
    out = residual
    for feature_index in features:
        inner_stats: list = []          # exactly what `_bundle_hook_fn` passed
        out = _make_clamp_hook(real_sae, int(feature_index), 0.0, "all", None, inner_stats)(out, None)
        discarded.append(inner_stats)
    assert all(stats for stats in discarded), "the inner hooks did record -- into lists nobody kept"

    spec = gi.GroupSpec(
        kind="ablate", members=tuple(gi.GroupMember(int(i)) for i in features),
        alpha=1.0, ablation_mechanism="subtract",
    )
    group_out, ledger = _group_output(gi, real_sae, spec, residual)
    assert len(ledger.records) == 1
    record = ledger.records[0]
    assert record.positions_modified > 0
    expected_norm = float((group_out - residual).to(torch.float32).norm())
    assert record.delta_norm == pytest.approx(expected_norm, rel=1e-6)
    assert record.delta_norm > 0.0


def test_the_ledger_records_every_call_at_k_one_too(gi, real_sae, residual):
    features = _live_features(real_sae, residual, limit=1)
    spec = gi.GroupSpec(
        kind="ablate", members=(gi.GroupMember(int(features[0])),),
        alpha=1.0, ablation_mechanism="subtract",
    )
    _out, ledger = _group_output(gi, real_sae, spec, residual)
    assert len(ledger.records) == 1


# ---------------------------------------------------------------------------
# D3: the dose is no longer taken from member zero
# ---------------------------------------------------------------------------


def test_each_member_is_dosed_in_its_own_max_units():
    corpus_max = {11: 2.0, 22: 50.0, 33: 0.5}
    spec = d.build_group_spec_for_intervention(
        [11, 22, 33], direction="clamp", value_in_max_units=0.5,
        corpus_max=corpus_max, positions="all",
    )
    targets_by_feature = {m.feature_index: m.corpus_max for m in spec.members}
    assert targets_by_feature == corpus_max
    assert spec.dose_form == "clamp"
    assert spec.alpha == 0.5
    # The retired path would have used corpus_max[11] == 2.0 for ALL three,
    # so member 22 would have been dosed at 1.0 instead of 25.0 -- a factor
    # of 25 for one member of the same group.
    retired_single_target = 0.5 * corpus_max[11]
    assert retired_single_target != 0.5 * corpus_max[22]


def test_a_member_without_a_corpus_max_is_refused_not_defaulted():
    with pytest.raises(ValueError, match="refuses to substitute another member's scale"):
        d.build_group_spec_for_intervention(
            [11, 22], direction="clamp", value_in_max_units=1.0,
            corpus_max={11: 2.0}, positions="all",
        )


def test_ablation_at_generated_only_must_be_stated_not_defaulted():
    """RULING_13 Q3.8: generated_only leaves the concept un-ablated while
    the prompt is processed, so selecting it has to be said out loud."""
    with pytest.raises(ValueError, match=re.escape("RULING_13 Q3.8")):
        d.build_group_spec_for_intervention(
            [11], direction="ablate", value_in_max_units=1.0,
            corpus_max={11: 2.0}, positions="generated_only",
        )
    spec = d.build_group_spec_for_intervention(
        [11], direction="ablate", value_in_max_units=1.0, corpus_max={11: 2.0},
        positions="generated_only", acknowledge_prompt_positions_unablated=True,
    )
    assert spec.acknowledge_prompt_positions_unablated is True


# ---------------------------------------------------------------------------
# The redirect must be behaviour-PRESERVING at k=1
# ---------------------------------------------------------------------------


def test_k1_ablate_is_identical_to_the_old_clamp_hook(gi, real_sae, residual):
    """Engineer 3 established that `_make_clamp_hook`'s decode-difference IS
    decoder subtraction. If that reconciliation is real, redirecting a
    single-feature ablation changes nothing measurable."""
    from interplab.interventions.hooks import _make_clamp_hook

    for feature_index in _live_features(real_sae, residual, limit=3):
        old = _make_clamp_hook(real_sae, feature_index, 0.0, "all", None, [])(residual, None)
        spec = d.build_group_spec_for_intervention(
            [feature_index], direction="ablate", value_in_max_units=1.0,
            corpus_max={feature_index: 1.0}, positions="all",
        )
        new, _ledger = _group_output(gi, real_sae, spec, residual)
        assert torch.allclose(old, new, atol=1e-5), f"feature {feature_index}"


def test_k1_clamp_is_identical_to_the_old_clamp_hook(gi, real_sae, residual):
    """The clamp direction too: old `absolute_clamp_value =
    value_in_max_units * corpus_max[seed]` equals the primitive's
    `target = alpha * member.corpus_max`."""
    from interplab.interventions.hooks import _make_clamp_hook

    value_in_max_units, member_corpus_max = 3.0, 0.75
    for feature_index in _live_features(real_sae, residual, limit=3):
        old = _make_clamp_hook(
            real_sae, feature_index, value_in_max_units * member_corpus_max, "all", None, []
        )(residual, None)
        spec = d.build_group_spec_for_intervention(
            [feature_index], direction="clamp", value_in_max_units=value_in_max_units,
            corpus_max={feature_index: member_corpus_max}, positions="all",
        )
        new, _ledger = _group_output(gi, real_sae, spec, residual)
        assert torch.allclose(old, new, atol=1e-5), f"feature {feature_index}"
