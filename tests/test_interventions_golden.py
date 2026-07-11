"""§8.2 test_delta_golden: clamp (and, per bullet 5, add_direction) on the
tiny fixture reproduces the pinned delta tensor to within a bounded ULP
distance in fp32 (ED-26).

ED-26 (decided during WP10 CI hardening): the golden pins the delta *as
measured through the model* (`fl(x + delta) - x`), not the mathematically
exact intervention -- PyTorch's CPU kernels take different SIMD/FMA paths
on Windows vs Linux, so `x`'s last bit (and therefore the measured delta's
rounding) is platform-dependent. This was never a correctness question:
measured cross-platform divergence topped out at 8 ULP (clamp) / 4 ULP
(add_direction) on ~2100 fp32 elements each, both platforms independently
within 16 ULP of an fp64 reference recompute, and both bitwise stable
across repeated runs and thread counts. A real regression (wrong sign,
index, scaling) diverges by millions of ULP, not tens -- MAX_ULP below
loses no bug-catching power. "0 ULP" was always implicitly "0 ULP on the
generation platform"; this replaces that over-claim with the honest bound.

Golden bytes come from tests/golden/delta_golden.json, generated once by
tests/golden/generate_delta_golden.py (ED-1 discipline: never regenerated
at test time) -- ED-26 changes the comparison, not the golden.
"""

import json
from pathlib import Path

import numpy as np
import torch

from interplab.interventions import attach, from_dict

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "delta_golden.json"

# ED-26: measured cross-platform max was 8 ULP (clamp) / 4 ULP (add_direction);
# 4x margin for CPU ISAs not yet measured (GitHub's runner pool varies, Apple
# Silicon exists).
MAX_ULP = 32


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _delta(model, sae, hook_name, prompt, spec):
    ids = model.tokenizer(prompt, return_tensors="pt")["input_ids"]
    with torch.no_grad():
        _, baseline_cache = model.run_with_cache(ids)
        with attach(model, sae, spec):
            _, steered_cache = model.run_with_cache(ids)
    return (steered_cache[hook_name] - baseline_cache[hook_name]).to(torch.float32)


def _ulp_distance(a: torch.Tensor, b: torch.Tensor) -> np.ndarray:
    """Per-element ULP distance between two fp32 tensors: map each element's
    IEEE-754 sign-magnitude bit pattern onto a signed integer line that is
    monotone in float order (negative floats -> negative integers), then take
    the absolute difference. Correct across the sign boundary: distances
    through zero count both magnitudes, and dist(+0.0, -0.0) == 0."""
    a_bits = a.numpy().astype(np.float32).view(np.int32).astype(np.int64)
    b_bits = b.numpy().astype(np.float32).view(np.int32).astype(np.int64)
    a_lex = np.where(a_bits >= 0, a_bits, -(a_bits & 0x7FFFFFFF))
    b_lex = np.where(b_bits >= 0, b_bits, -(b_bits & 0x7FFFFFFF))
    return np.abs(a_lex - b_lex)


def test_clamp_delta_matches_golden_within_ulp_bound(tiny_hooked_transformer, tiny_sae):
    golden = _load_golden()
    spec = from_dict(golden["clamp_spec"])
    delta = _delta(tiny_hooked_transformer, tiny_sae, golden["hook_name"], golden["prompt"], spec)

    expected = torch.tensor(golden["clamp_delta"], dtype=torch.float32).reshape(golden["clamp_delta_shape"])
    max_ulp = int(_ulp_distance(delta, expected).max())
    assert max_ulp <= MAX_ULP, f"clamp delta diverges from golden by {max_ulp} ULP (bound: {MAX_ULP}, ED-26)"


def test_add_direction_delta_matches_golden_within_ulp_bound(tiny_hooked_transformer, tiny_sae):
    golden = _load_golden()
    spec = from_dict(golden["add_direction_spec"])
    delta = _delta(tiny_hooked_transformer, tiny_sae, golden["hook_name"], golden["prompt"], spec)

    expected = torch.tensor(golden["add_direction_delta"], dtype=torch.float32).reshape(golden["add_direction_delta_shape"])
    max_ulp = int(_ulp_distance(delta, expected).max())
    assert max_ulp <= MAX_ULP, f"add_direction delta diverges from golden by {max_ulp} ULP (bound: {MAX_ULP}, ED-26)"
