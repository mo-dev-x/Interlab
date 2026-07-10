"""§8.2 test_delta_golden: clamp (and, per bullet 5, add_direction) on the
tiny fixture reproduces the pinned delta tensor to 0 ulp in fp32.

Golden bytes come from tests/golden/delta_golden.json, generated once by
tests/golden/generate_delta_golden.py (ED-1 discipline: never regenerated
at test time).
"""

import json
from pathlib import Path

import torch

from interplab.interventions import attach, from_dict

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "delta_golden.json"


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _delta(model, sae, hook_name, prompt, spec):
    ids = model.tokenizer(prompt, return_tensors="pt")["input_ids"]
    with torch.no_grad():
        _, baseline_cache = model.run_with_cache(ids)
        with attach(model, sae, spec):
            _, steered_cache = model.run_with_cache(ids)
    return (steered_cache[hook_name] - baseline_cache[hook_name]).to(torch.float32)


def test_clamp_delta_matches_golden_to_0_ulp(tiny_hooked_transformer, tiny_sae):
    golden = _load_golden()
    spec = from_dict(golden["clamp_spec"])
    delta = _delta(tiny_hooked_transformer, tiny_sae, golden["hook_name"], golden["prompt"], spec)

    expected = torch.tensor(golden["clamp_delta"], dtype=torch.float32).reshape(golden["clamp_delta_shape"])
    assert torch.equal(delta, expected)


def test_add_direction_delta_matches_golden_to_0_ulp(tiny_hooked_transformer, tiny_sae):
    golden = _load_golden()
    spec = from_dict(golden["add_direction_spec"])
    delta = _delta(tiny_hooked_transformer, tiny_sae, golden["hook_name"], golden["prompt"], spec)

    expected = torch.tensor(golden["add_direction_delta"], dtype=torch.float32).reshape(golden["add_direction_delta_shape"])
    assert torch.equal(delta, expected)
