"""§8.2 test_delta_golden: clamp (and, per bullet 5, add_direction) on the
tiny fixture reproduces the pinned delta tensor to within a bounded ULP
distance in fp32 (ED-26).

ED-26 (decided during WP10 CI hardening): the golden pins the delta *as
measured through the model* (`fl(x + delta) - x`), not the mathematically
exact intervention -- PyTorch's CPU kernels take different SIMD/FMA paths
on Windows vs Linux, so `x`'s last bit (and therefore the measured delta's
rounding) is platform-dependent. This was never a correctness question. A
real regression (wrong sign, index, scaling) diverges by millions of ULP,
not tens -- MAX_ULP below loses no bug-catching power. "0 ULP" was always
implicitly "0 ULP on the generation platform"; this replaces that
over-claim with the honest bound.

ED-33 SAE-stack migration (sae-lens 3.x -> 6.x): the golden was regenerated
against the new stack (fresh reference, not the old bytes re-pinned -- the
new TopK encode/decode is a materially different computation), and the
cross-platform divergence was re-measured the same way as ED-26 (Windows
host vs a Linux WSL environment installing the identical pinned
sae-lens==6.44.2/transformer-lens==3.2.1/transformers==5.12.1/torch==2.13.0
stack), not assumed to carry over from the 3.x-era numbers. Measured: 32
ULP (clamp) / 4 ULP (add_direction) on 2048 fp32 elements each -- clamp's
new measured max lands exactly on the old MAX_ULP=32 bound, so the old
bound is no longer a comfortable margin under the new stack. MAX_ULP is
raised to 128, keeping ED-26's original convention of a 4x margin over the
measured worst case (32 * 4), not a re-justification of the old number.

Golden bytes come from tests/golden/delta_golden.json, generated once by
tests/golden/generate_delta_golden.py (ED-1 discipline: never regenerated
at test time) -- ED-26/ED-33 change the comparison, not the golden.
"""

import json
from pathlib import Path

import numpy as np
import torch

from interplab.interventions import attach, from_dict

GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "delta_golden.json"

# ED-33: re-measured cross-platform max under the 6.x stack was 32 ULP
# (clamp) / 4 ULP (add_direction); 4x margin for CPU ISAs not yet measured
# (GitHub's runner pool varies, Apple Silicon exists) -- same convention
# ED-26 used, applied to the new measurement.
MAX_ULP = 128


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
