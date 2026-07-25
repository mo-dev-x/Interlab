"""§8.2 test_hook_hygiene: attach/detach leaves zero forward hooks."""

import pytest

from interplab.interventions import InterventionSpec, attach

_HASH = "sha256:" + "a" * 64


def _active_hooks(model):
    return [name for name, hp in model.hook_dict.items() if len(hp.fwd_hooks) > 0]


def test_noop_never_registers_a_hook(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(
        kind="noop", feature_index=None, value_in_max_units=None,
        corpus_max=None, positions="all", checkpoint_hash=_HASH,
    )
    assert _active_hooks(tiny_hooked_transformer) == []
    with attach(tiny_hooked_transformer, tiny_sae, spec):
        assert _active_hooks(tiny_hooked_transformer) == []
    assert _active_hooks(tiny_hooked_transformer) == []


@pytest.mark.parametrize(
    "spec",
    [
        InterventionSpec(kind="clamp", feature_index=0, value_in_max_units=2.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH),
        InterventionSpec(kind="ablate", feature_index=0, value_in_max_units=None, corpus_max=None, positions="all", checkpoint_hash=_HASH),
        InterventionSpec(kind="add_direction", feature_index=None, value_in_max_units=2.0, corpus_max=1.0, positions="all", checkpoint_hash=_HASH, direction_seed=1),
    ],
    ids=["clamp", "ablate", "add_direction"],
)
def test_hook_active_during_context_and_removed_after(tiny_hooked_transformer, tiny_sae, spec):
    assert _active_hooks(tiny_hooked_transformer) == []
    with attach(tiny_hooked_transformer, tiny_sae, spec):
        assert _active_hooks(tiny_hooked_transformer) == [tiny_sae.cfg.metadata.hook_name]
    assert _active_hooks(tiny_hooked_transformer) == []


def test_hooks_removed_even_when_body_raises(tiny_hooked_transformer, tiny_sae):
    spec = InterventionSpec(kind="ablate", feature_index=0, value_in_max_units=None, corpus_max=None, positions="all", checkpoint_hash=_HASH)
    with pytest.raises(RuntimeError), attach(tiny_hooked_transformer, tiny_sae, spec):
        assert _active_hooks(tiny_hooked_transformer) == [tiny_sae.cfg.metadata.hook_name]
        raise RuntimeError("boom")
    assert _active_hooks(tiny_hooked_transformer) == []
