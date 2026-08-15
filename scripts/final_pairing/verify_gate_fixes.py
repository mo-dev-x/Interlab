#!/usr/bin/env python3
"""Falsifiers for the 2026-08-15 zero-survivor fixes (C1/C2/C3/C5) and for
the SHADOW G-B measurement (SHADOW-A/B/C).

Every check here is a FALSIFIER, not a demonstration: each one states, up
front, the exact number that must come out, and exits non-zero when it does
not. None of them may be "adjusted to pass" -- a failing check is the
result.

Run:  python scripts/final_pairing/verify_gate_fixes.py --all
      python scripts/final_pairing/verify_gate_fixes.py c1 \
          --progress D:/devcache/tmp/fp413287/primary/qwen/grid/state/progress.jsonl
      python scripts/final_pairing/verify_gate_fixes.py shadow

READ THIS BEFORE QUOTING ANY NUMBER THIS SCRIPT PRINTS. The 182 records the
C1 check flips are ARTIFACTS of the degenerate-scale defect, not G-B passes.
A G-B pass rate computed with them included is not a fact about run 413287
and must not be quoted as one. Separately, EVERY G-B figure in this
codebase -- before or after C1 -- is computed against a within-cell
reference scale that is derived from the very prompts it judges (see
`compute_gate_b_fire_rate`'s own docstring). C1 removes the fully
degenerate case; it does not make that denominator non-circular, and
correcting the scale is explicitly not authorised here.

The SHADOW checks do not correct it either. They MEASURE what the corrected
statistic would look like -- against the background reference this protocol
already uses for the same quantity -- and record the distribution, so that
whoever re-derives `G_B_fire_rate_min` has evidence instead of an
assertion. Every verdict in this codebase is still computed from the frozen
within-cell statistic, and SHADOW-C asserts that it still is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import final_pairing_concept_discovery as d  # noqa: E402

DEFAULT_PROGRESS = Path("D:/devcache/tmp/fp413287/primary/qwen/grid/state/progress.jsonl")

#: The G-B parameters run 413287 was ACTUALLY scored with, pinned here on
#: purpose: this check re-scores a historical record, so it must use that
#: run's values even if the artifact's frozen thresholds later move. They
#: are asserted against the artifact below rather than merely asserted.
_FIRE_RATE_MIN = 0.70
_FLOOR_FRACTION = 0.20


def _load_cells(progress_path: Path) -> tuple[list[dict], list[dict]]:
    """Flattens the preserved per-concept progress log into the two per-cell
    record lists it contains (G-A/B and G-C), in file order."""
    records = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ab: list[dict] = []
    c: list[dict] = []
    for record in records:
        for candidate in record["verdict"]["candidates_evaluated"]:
            ab += candidate["gate_a_b_results"]
            c += candidate["gate_c_results"]
    return ab, c


def _is_dead_cell(ab_cell: dict, c_cell: dict) -> bool:
    """A cell whose positive AND control scores were all identically zero.

    Identified from the record alone, without the raw scores (the run
    preserved verdicts, not activations): AUROC is EXACTLY 0.5 only when
    every score in both sets ties, which post-ReLU means every score is
    0.0. Requiring that of BOTH denominators (G-A's pooled near_miss +
    unrelated and G-C's near_miss-only) and of `fire_rate == 1.0`
    simultaneously is what makes the identification safe: a live feature
    would have to tie against two different control sets AND report a
    perfect fire rate by coincidence."""
    return ab_cell["separation_auroc"] == 0.5 and c_cell["near_miss_auroc"] == 0.5 and ab_cell["fire_rate"] == 1.0


def check_c1(progress_path: Path) -> bool:
    """FALSIFIER C1: re-score the preserved run through the patched
    `compute_gate_b_fire_rate`. EXACTLY 182 records must flip
    gate_b_passed true -> false, and the grid-wide count must go 660 ->
    478. Any other numbers mean the guard is not firing on the population
    it was written for."""
    thresholds = d.load_frozen_prompt_artifact(d.REPO_ROOT).metadata["thresholds"]
    if (thresholds["G_B_fire_rate_min"], thresholds["G_B_activation_floor_fraction_of_observed_max"]) != (
        _FIRE_RATE_MIN, _FLOOR_FRACTION
    ):
        print("[C1] FAIL: the frozen G-B thresholds no longer match the ones run 413287 was scored with")
        return False

    ab, c = _load_cells(progress_path)
    c_by_cell = {(x["concept_id"], x["locale"], x["family"], x["feature_index"]): x for x in c}

    before = after = flips = live_flips = 0
    reconstruction_mismatches = 0
    for cell in ab:
        c_cell = c_by_cell[(cell["concept_id"], cell["locale"], cell["family"], cell["feature_index"])]
        n = 10  # every (concept, locale, family) positive split in the frozen artifact has exactly 10 prompts
        if _is_dead_cell(cell, c_cell):
            scores = [0.0] * n
        else:
            # A faithful stand-in for a LIVE cell: any positive-max scale
            # with the recorded fire_rate reproduces the recorded
            # fire_rate exactly under both the old and the new function,
            # which is the property under test (the guard must not touch
            # live cells). Verified below rather than assumed.
            fired = round(cell["fire_rate"] * n)
            scores = [1.0] * fired + [0.0] * (n - fired)
        fire_rate, _floor = d.compute_gate_b_fire_rate(scores, floor_fraction=_FLOOR_FRACTION)
        if not _is_dead_cell(cell, c_cell) and abs(fire_rate - cell["fire_rate"]) > 1e-12:
            reconstruction_mismatches += 1
        now_passes = fire_rate >= _FIRE_RATE_MIN
        before += int(cell["gate_b_passed"])
        after += int(now_passes)
        if now_passes != cell["gate_b_passed"]:
            flips += 1
            live_flips += int(not _is_dead_cell(cell, c_cell))

    ok = (
        len(ab) == 1080
        and before == 660
        and after == 478
        and flips == 182
        and live_flips == 0
        and reconstruction_mismatches == 0
    )
    print(f"[C1] cells re-scored                : {len(ab)} (expected 1080)")
    print(f"[C1] recorded gate_b_passed BEFORE  : {before} (expected 660)")
    print(f"[C1] gate_b_passed AFTER the guard  : {after} (expected 478)")
    print(f"[C1] true->false flips              : {flips} (expected 182)")
    print(f"[C1] flips on a cell that DID fire  : {live_flips} (expected 0 -- the guard is strictly stricter)")
    print(f"[C1] live-cell fire_rate mismatches : {reconstruction_mismatches} (expected 0)")
    print(f"[C1] {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# C2: the encode-once refactor must not change the measurement.
#
# THE LITERAL FALSIFIER ("replay one of the 9 preserved concepts and compare
# all 120 emitted values against progress.jsonl") CANNOT BE RUN HERE and is
# not silently substituted: run 413287 preserved verdicts, not activations,
# and reproducing its numbers requires Qwen3.5-27B on a GPU, which this
# machine does not have (torch is CPU-only). What runs instead is the SAME
# comparison with the model replaced by a deterministic surrogate: the real
# frozen artifact's real texts, the pre-C2 code path (read out of git at
# 98a7108) and the post-C2 code path, side by side, every emitted float
# compared. That tests exactly what the refactor could break -- whether the
# arithmetic moved -- and tests nothing about the model. The GPU replay
# against progress.jsonl remains OWED before any production rerun -- it is
# now EXECUTABLE rather than merely owed:
#
#   python scripts/final_pairing/final_pairing_concept_discovery.py \
#       --mode replay --replay-progress <the preserved progress.jsonl> ...
#
# which re-scores exactly the preserved 9 concepts x 20 features on the real
# backend and asserts every emitted separation_auroc / fire_rate_within_cell
# / near_miss_auroc to 1e-9, failing loudly. Until that has been RUN on GPU,
# the surrogate result below is a structural equivalence proof and is not a
# model-level replay, and this comment stays.
#
# C1 is held CONSTANT across both arms (the pre-C2 module's
# `compute_gate_b_fire_rate` is replaced with the patched one) so that any
# difference is attributable to C2 alone and not to the guard.
# ---------------------------------------------------------------------------

_SURROGATE_D_MODEL = 32
_SURROGATE_D_SAE = 256
_SURROGATE_HOOK = "surrogate.hook_resid_post"


class _SurrogateSAE:
    """A real (small) SAE-shaped encoder: `relu(x @ W.T + b)`, fixed seed, a
    negative bias so the output is genuinely sparse -- post-ReLU exact
    zeros are the common case in a real SAE and are what makes ties, dead
    cells and the C1 guard reachable at all."""

    def __init__(self, seed: int = 11) -> None:
        import torch

        gen = torch.Generator().manual_seed(seed)
        self.d_in = _SURROGATE_D_MODEL
        self.d_sae = _SURROGATE_D_SAE
        self.W = torch.randn(_SURROGATE_D_SAE, _SURROGATE_D_MODEL, generator=gen)
        self.b = -torch.rand(_SURROGATE_D_SAE, generator=gen) * 1.5

    def encode(self, x):
        import torch

        return torch.relu(x.to(torch.float32) @ self.W.T + self.b)


class _SurrogateModel:
    """Deterministic, content-addressed residuals over 3 positions per text,
    plus a forward-pass counter -- the counter is the honest measure of the
    C2 speedup (wall time on a surrogate is Python overhead; on the real
    backend the encode dominates and the two are the same ratio)."""

    def __init__(self) -> None:
        self.forward_passes = 0
        self._texts: dict[int, str] = {}

    def to_tokens(self, text: str):
        import torch

        token = len(self._texts)
        self._texts[token] = text
        return torch.tensor([[token]])

    def run_with_cache(self, tokens, names_filter: str):
        import hashlib as _hashlib

        import torch

        self.forward_passes += 1
        text = self._texts[int(tokens[0][0])]
        seed = int(_hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**31)
        gen = torch.Generator().manual_seed(seed)
        resid = torch.randn((1, 3, _SURROGATE_D_MODEL), generator=gen)
        return None, {names_filter: resid}


def _surrogate_backend(module):
    import final_pairing_targets as targets

    model = _SurrogateModel()
    backend = module.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name,
        model_obj=model,
        sae=_SurrogateSAE(),
        hook_name=_SURROGATE_HOOK,
        d_sae=_SURROGATE_D_SAE,
        d_model=_SURROGATE_D_MODEL,
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={"model": {"repository": "surrogate", "local_path": "/surrogate"}, "sae": {"repository": "surrogate"}},
        checkpoint_hash="surrogate",
    )
    return backend, model


_PRE_C2_PINNED_REV = "98a7108"
_PRE_C2_SNAPSHOT_NAME = "_pre_c2_snapshot_98a7108.py"
_PRE_C2_PINNED_SHA256 = "e170799b296a0c3d9cd2c9903e4545865e95466b4abe0206a85d46cec252867d"


def _pre_c2_source(rev: str):
    """Returns (source_text, origin) for the pre-C2 file.

    Prefers `git show`, but the cluster runs from a TARBALL EXTRACT with no
    .git, where `git show` exits 128 and C2 died before it ran (job at
    3ed2de3, 2026-08-15). So a byte-identical snapshot ships in the tree.

    EITHER PATH IS CHECKED AGAINST A PINNED DIGEST. A fallback free to load
    some other source would let C2 report PASS without ever exercising the
    pre-C2 code path -- the exact defect class this harness exists to catch.
    A non-default rev has no pin, so it stays git-only rather than silently
    comparing against the pinned snapshot's bytes."""
    import hashlib
    import subprocess

    rel = "scripts/final_pairing/final_pairing_concept_discovery.py"
    raw = None
    origin = ""
    try:
        raw = subprocess.run(
            ["git", "show", f"{rev}:{rel}"],
            cwd=SCRIPT_DIR.parents[1], capture_output=True, check=True,
        ).stdout
        origin = f"git {rev}"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        raw = None

    if raw is None:
        if rev != _PRE_C2_PINNED_REV:
            raise RuntimeError(
                f"pre-C2 source for rev {rev} needs a git checkout; only "
                f"{_PRE_C2_PINNED_REV} has a shipped snapshot"
            )
        snapshot = SCRIPT_DIR / _PRE_C2_SNAPSHOT_NAME
        if not snapshot.exists():
            raise RuntimeError(f"no git checkout and no snapshot at {snapshot}")
        raw = snapshot.read_bytes()
        origin = f"snapshot {_PRE_C2_SNAPSHOT_NAME}"

    if rev == _PRE_C2_PINNED_REV:
        digest = hashlib.sha256(raw).hexdigest()
        if digest != _PRE_C2_PINNED_SHA256:
            raise RuntimeError(
                f"pre-C2 source from {origin} has sha256 {digest}, expected "
                f"{_PRE_C2_PINNED_SHA256} -- refusing to compare against unknown bytes"
            )
    return raw.decode("utf-8"), origin


def _load_pre_c2_module(rev: str = _PRE_C2_PINNED_REV):
    """Loads the pre-C2 file under its own module name, from a path inside
    scripts/final_pairing/ so its REPO_ROOT and sys.path bootstrap resolve
    exactly as they did at that revision."""
    import importlib.util
    import tempfile

    source, origin = _pre_c2_source(rev)
    print(f"[C2] pre-C2 source loaded from {origin}", flush=True)
    tmp = Path(tempfile.mkdtemp(dir=SCRIPT_DIR, prefix="_pre_c2_")) / "pre_c2_discovery.py"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    # One directory deeper would break `parents[2]`; keep the file directly
    # under scripts/final_pairing/ instead.
    target = SCRIPT_DIR / "_pre_c2_discovery_tmp.py"
    target.write_text(source, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("pre_c2_discovery", target)
        module = importlib.util.module_from_spec(spec)
        sys.modules["pre_c2_discovery"] = module
        spec.loader.exec_module(module)
    finally:
        pass
    return module, target


def check_c2(*, concept_id: str = "formal_register", shortlist_size: int = 20, rev: str = "98a7108") -> bool:
    """FALSIFIER C2: every emitted separation_auroc / fire_rate /
    near_miss_auroc must be identical between the pre-C2 and post-C2 code
    paths (tolerance 1e-9; anything above it means the refactor changed
    the measurement and must be reverted), and the forward-pass count must
    drop by at least 20x.

    Scoped to the MEASUREMENT, not the selection: both arms are handed the
    SAME feature list (the pre-C2 shortlist, so the comparison covers
    exactly the 20 x 6 cells run 413287 would have emitted for this
    concept). C3 changes WHICH features get measured and is falsified
    separately; mixing the two here would compare different populations
    and prove nothing about either."""
    import time

    pre, tmp_path = _load_pre_c2_module(rev)
    try:
        # Hold C1 constant: the guard is C1's change, not C2's.
        pre.compute_gate_b_fire_rate = d.compute_gate_b_fire_rate

        artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)

        old_backend, old_model = _surrogate_backend(pre)
        new_backend, new_model = _surrogate_backend(d)

        features = [
            r.feature_index
            for r in pre.rank_candidates_for_concept(
                old_backend, artifact, concept_id=concept_id, shortlist_size=shortlist_size
            )
        ]
        # The ranking pass itself is identical in both arms and is not
        # what C2 changed; count only the gate evaluation below.
        old_model.forward_passes = 0

        def _collect(module, backend, cache_kwargs):
            out = {}
            for feature_index in features:
                for locale in module.FROZEN_PROMPT_SET_LOCALES:
                    for r in module.compute_gate_a_and_b_per_family(
                        backend, artifact, concept_id=concept_id, locale=locale,
                        feature_index=feature_index, **cache_kwargs,
                    ):
                        out[("A", feature_index, locale, r.family)] = r.separation_auroc
                        out[("B", feature_index, locale, r.family)] = r.fire_rate
                    for r in module.compute_gate_c_per_family(
                        backend, artifact, concept_id=concept_id, locale=locale,
                        feature_index=feature_index, **cache_kwargs,
                    ):
                        out[("C", feature_index, locale, r.family)] = r.near_miss_auroc
            return out

        t0 = time.perf_counter()
        old_cells = _collect(pre, old_backend, {})
        old_seconds = time.perf_counter() - t0

        cache = d.FeatureMatrixCache()
        d.pin_shared_substrate(cache, new_backend, artifact)
        t0 = time.perf_counter()
        new_cells = _collect(d, new_backend, {"cache": cache})
        new_seconds = time.perf_counter() - t0
        same_keys = set(old_cells) == set(new_cells)
        worst = max((abs(old_cells[k] - new_cells[k]) for k in old_cells if k in new_cells), default=float("inf"))
        exact = sum(1 for k in old_cells if k in new_cells and old_cells[k] == new_cells[k])

        pass_ratio = old_model.forward_passes / max(new_model.forward_passes, 1)
        time_ratio = old_seconds / max(new_seconds, 1e-9)
        ok = same_keys and worst <= 1e-9 and pass_ratio >= 20.0 and len(old_cells) == len(features) * 6 * 3

        print(f"[C2] concept                        : {concept_id}, {len(features)} features x 6 cells x 3 metrics")
        print(f"[C2] emitted values compared        : {len(old_cells)}")
        print(f"[C2] identical (feature,locale,family) key sets: {same_keys}")
        print(f"[C2] max abs diff pre-C2 vs post-C2 : {worst:.3e} (must be <= 1e-9)")
        print(f"[C2] bit-exact values               : {exact}/{len(old_cells)}")
        print(f"[C2] forward passes  pre-C2 / post-C2: {old_model.forward_passes} / {new_model.forward_passes} = {pass_ratio:.1f}x (must be >= 20x)")
        print(f"[C2] wall seconds    pre-C2 / post-C2: {old_seconds:.2f} / {new_seconds:.2f} = {time_ratio:.1f}x")
        print(
            "[C2] NOTE: the surrogate's forward pass is ~free, so its wall-clock ratio is NOT the "
            "production ratio and is not what this check asserts on. The forward-pass COUNT is "
            "structural (same code path, same texts, any backend); on real hardware the encode "
            "dominates, so the wall-clock ratio there is the pass ratio. The production wall-time "
            "measurement is OWED on GPU."
        )
        print(f"[C2] {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        sys.modules.pop("pre_c2_discovery", None)
        tmp_path.unlink(missing_ok=True)
        for stray in SCRIPT_DIR.glob("_pre_c2_*"):
            if stray.is_dir():
                stray.rmdir()


def check_c3_auroc_equivalence(*, trials: int = 4000, seed: int = 20260815) -> bool:
    """FALSIFIER C3 (part 1): the vectorised full-space AUROC must agree
    with the frozen per-feature primitive (`_auroc_from_scores`, sklearn)
    to floating-point noise, INCLUDING under heavy ties -- post-ReLU SAE
    scores are mostly exact zeros, so ties are the common case, not the
    edge case. If this disagrees, a full-space pass is not the same
    measurement as the per-feature pass that produced run 413287's
    record, and no conclusion may be carried between them."""
    rng = np.random.default_rng(seed)
    worst = 0.0
    for _ in range(trials):
        n_pos, n_neg, n_feat = 10, 30, 8
        # Deliberately sparse: ~60% exact zeros, i.e. many ties.
        pos = np.where(rng.random((n_pos, n_feat)) < 0.6, 0.0, rng.random((n_pos, n_feat)) * 5.0)
        neg = np.where(rng.random((n_neg, n_feat)) < 0.6, 0.0, rng.random((n_neg, n_feat)) * 5.0)
        vectorised = d.rank_auroc_matrix(pos, neg)
        for j in range(n_feat):
            reference = d._auroc_from_scores(pos[:, j].tolist(), neg[:, j].tolist())
            worst = max(worst, abs(vectorised[j] - reference))
    ok = worst <= 1e-12
    print(f"[C3a] vectorised-vs-sklearn AUROC max abs diff over {trials} tie-heavy trials: {worst:.3e} (must be <= 1e-12)")
    print(f"[C3a] {'PASS' if ok else 'FAIL'}")
    return ok


def check_c3_fire_rate_equivalence(*, trials: int = 4000, seed: int = 20260816) -> bool:
    """FALSIFIER C3 (part 2): the vectorised G-B must be bit-identical to
    the frozen scalar `compute_gate_b_fire_rate`, degenerate guard
    included. Both are computed against the SAME within-cell (circular)
    reference scale -- this check proves the vectorised path reproduces
    that arithmetic exactly, not that the arithmetic is sound."""
    rng = np.random.default_rng(seed)
    mismatches = 0
    for _ in range(trials):
        n_pos, n_feat = 10, 8
        pos = np.where(rng.random((n_pos, n_feat)) < 0.5, 0.0, rng.random((n_pos, n_feat)) * 5.0)
        if rng.random() < 0.25:  # force fully dead columns often enough to exercise the C1 guard
            pos[:, rng.integers(0, n_feat)] = 0.0
        rates, floors = d.fire_rate_matrix(pos, floor_fraction=_FLOOR_FRACTION)
        for j in range(n_feat):
            ref_rate, ref_floor = d.compute_gate_b_fire_rate(pos[:, j].astype(float).tolist(), floor_fraction=_FLOOR_FRACTION)
            if rates[j] != ref_rate or floors[j] != ref_floor:
                mismatches += 1
    ok = mismatches == 0
    print(f"[C3b] vectorised-vs-scalar G-B mismatches over {trials} trials: {mismatches} (expected 0)")
    print(f"[C3b] {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# C3, THE IMPORTANT FALSIFIER: a selector that scores every feature must not
# lose the one feature we already know passes G-A 6/6.
#
# Run 413287 preserved verdicts, not activations, and this machine has no
# GPU, so the real Qwen forward pass cannot be re-run. What CAN be rebuilt
# exactly is the arithmetic the selector sees. The construction below
# synthesises, per (locale, family) cell, a 10-positive / 15-near_miss /
# 15-unrelated score set for feature 25995 that reproduces run 413287's
# RECORDED separation_auroc, fire_rate and near_miss_auroc for that feature
# EXACTLY, in all six cells -- not approximately, not qualitatively. Those
# 18 recorded floats are the targets and the check asserts on them.
#
# The feature is then embedded at index 25995 in a full d_sae = 80,000
# feature space of realistic sparse background features whose magnitudes
# are deliberately larger, and the ACTUAL new selector is run end to end:
# score_full_feature_space -> select_candidates_from_scan -> exact
# verification through the frozen scalar primitives -> recorded verdict.
#
# This falsifies every way the full-space selector could lose the feature:
# a screen epsilon too tight, a report budget truncating the G-A-passing
# set, the mechanical-only filter over-reaching, a wrong min-across-cells
# aggregation, or a cell set that misses a locale. It does NOT test the
# model, and it is not offered as one -- the GPU replay is still owed.
# ---------------------------------------------------------------------------

#: Run 413287's recorded values for formal_register / feature 25995, read
#: back from progress.jsonl at runtime rather than trusted from here; this
#: table is the construction's TARGET and the assertion's expectation.
_F25995 = "formal_register", 25995

#: Per (locale, family): (n_high, [low positive values]). "high" positives
#: sit at 1000.0 (so the G-B floor is 200.0 and only they fire, making
#: fire_rate exactly n_high/10); "low" positives sit on a tiny ladder well
#: under the floor, placed to realise the exact recorded rank statistics.
_CELL_DESIGN: dict[tuple[str, str], tuple[int, list[float]]] = {
    ("en", "f1"): (8, [16.0, 14.5]),
    ("en", "f2"): (9, [4.5]),
    ("en", "f3"): (6, [16.0, 16.0, 16.0, 14.5]),
    ("fr", "f1"): (9, [12.5]),
    ("fr", "f2"): (7, [16.0, 13.5, 1.5]),
    ("fr", "f3"): (4, [16.0, 16.0, 16.0, 16.0, 16.0, 1.5]),
}
#: near_miss and unrelated ladders, per locale. Shared by all three
#: families of that locale, exactly as the frozen artifact shares them.
_NEAR_MISS_LADDER: dict[str, list[float]] = {
    "en": [float(i) for i in range(1, 16)],
    "fr": [float(i) for i in range(1, 16)],
}
_UNRELATED_LADDER: dict[str, list[float]] = {
    "en": [0.5, 1.5, 2.5, 3.5, 3.6, 3.7, 3.8, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5],
    "fr": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
}
_HIGH_POSITIVE = 1000.0


class _TabulatedSAE:
    """encode() is a table lookup: the residual is a one-hot text selector,
    so `relu(x @ M)` returns exactly the designed row of the score matrix
    `M` for that text. Real torch math, no mocking of the reduction under
    test -- `encode_texts` still takes its own max over positions."""

    def __init__(self, matrix) -> None:
        import torch

        self.M = torch.as_tensor(matrix, dtype=torch.float32)
        self.d_in = self.M.shape[0]
        self.d_sae = self.M.shape[1]

    def encode(self, x):
        import torch

        return torch.relu(x.to(torch.float32) @ self.M)


class _TabulatedModel:
    def __init__(self, texts: list[str]) -> None:
        import torch

        self._index = {text: i for i, text in enumerate(texts)}
        self._n = len(texts)
        self.forward_passes = 0
        self._torch = torch

    def to_tokens(self, text: str):
        return self._torch.tensor([[self._index[text]]])

    def run_with_cache(self, tokens, names_filter: str):
        self.forward_passes += 1
        resid = self._torch.zeros((1, 1, self._n))
        resid[0, 0, int(tokens[0][0])] = 1.0
        return None, {names_filter: resid}


def _recorded_25995(progress_path: Path) -> tuple[dict, dict, list[int]]:
    concept_id, feature_index = _F25995
    records = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    verdict = next(r["verdict"] for r in records if r["verdict"]["concept_id"] == concept_id)
    candidate = next(c for c in verdict["candidates_evaluated"] if c["feature_index"] == feature_index)
    ab = {(r["locale"], r["family"]): r for r in candidate["gate_a_b_results"]}
    c = {(r["locale"], r["family"]): r for r in candidate["gate_c_results"]}
    return ab, c, [c_["feature_index"] for c_ in verdict["candidates_evaluated"]]


def check_c3_recovers_the_known_answer(
    progress_path: Path, *, d_sae: int = 80000, seed: int = 25995, report_top_n: int = 25,
) -> bool:
    """FALSIFIER C3 (the important one): feature 25995 must appear in
    formal_register's G-A-passing set when the selector scores all d_sae
    features. A selector that misses the one feature already known to pass
    G-A 6/6 is wrong."""
    import time

    import final_pairing_targets as targets

    concept_id, feature_index = _F25995
    recorded_ab, recorded_c, recorded_shortlist = _recorded_25995(progress_path)

    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    texts: list[str] = []
    per_cell: dict[tuple[str, str], tuple[list[str], list[str], dict[str, list[str]]]] = {}
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        unrelated, near_miss, positives_by_family = d.concept_locale_texts(
            artifact, concept_id=concept_id, locale=locale
        )
        per_cell[(locale, "")] = (unrelated, near_miss, positives_by_family)
        texts += unrelated + near_miss + [t for f in sorted(positives_by_family) for t in positives_by_family[f]]
    text_index = {t: i for i, t in enumerate(texts)}

    rng = np.random.default_rng(seed)
    # Realistic sparse SAE background: ~85% exact zeros, heavy-tailed
    # magnitudes deliberately LARGER than the designed feature's, so a
    # magnitude leaderboard has no reason to surface index 25995.
    matrix = np.where(
        rng.random((len(texts), d_sae)) < 0.85, 0.0, rng.random((len(texts), d_sae)) * 5000.0
    ).astype(np.float32)

    column = np.zeros(len(texts), dtype=np.float32)
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        unrelated, near_miss, positives_by_family = per_cell[(locale, "")]
        for text, value in zip(unrelated, _UNRELATED_LADDER[locale], strict=True):
            column[text_index[text]] = value
        for text, value in zip(near_miss, _NEAR_MISS_LADDER[locale], strict=True):
            column[text_index[text]] = value
        for family, family_texts in positives_by_family.items():
            n_high, lows = _CELL_DESIGN[(locale, family)]
            values = [_HIGH_POSITIVE] * n_high + lows
            for text, value in zip(family_texts, values, strict=True):
                column[text_index[text]] = value
    matrix[:, feature_index] = column

    model = _TabulatedModel(texts)
    backend = d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name, model_obj=model, sae=_TabulatedSAE(matrix),
        hook_name=_SURROGATE_HOOK, d_sae=d_sae, d_model=len(texts),
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={"model": {"repository": "tabulated", "local_path": "/tabulated"}, "sae": {"repository": "tabulated"}},
        checkpoint_hash="tabulated",
    )

    t0 = time.perf_counter()
    verdict = d.evaluate_concept_on_pairing(
        backend, artifact, concept_id=concept_id, report_top_n=report_top_n
    )
    seconds = time.perf_counter() - t0
    if verdict.status == "error":
        print(f"[C3c] FAIL: verdict errored -- {verdict.error}")
        return False

    emitted = {c["feature_index"]: c for c in verdict.candidates_evaluated}
    present = feature_index in emitted
    print(f"[C3c] features scored                : {verdict.features_scored} (selection_mode={verdict.selection_mode!r})")
    print(f"[C3c] feature 25995 present in the emitted record: {present}")
    if not present:
        print("[C3c] FAIL")
        return False

    candidate = emitted[feature_index]
    ab = {(r["locale"], r["family"]): r for r in candidate["gate_a_b_results"]}
    c_res = {(r["locale"], r["family"]): r for r in candidate["gate_c_results"]}

    gate_a_all = all(r["gate_a_passed"] for r in ab.values())
    gate_c_all = all(r["gate_c_passed"] for r in c_res.values())
    b_failures = sorted(k for k, r in ab.items() if not r["gate_b_passed"])

    worst = 0.0
    for key, recorded in recorded_ab.items():
        worst = max(worst, abs(ab[key]["separation_auroc"] - recorded["separation_auroc"]))
        worst = max(worst, abs(ab[key]["fire_rate"] - recorded["fire_rate"]))
    for key, recorded in recorded_c.items():
        worst = max(worst, abs(c_res[key]["near_miss_auroc"] - recorded["near_miss_auroc"]))

    # The pre-C3 selector, run on the SAME surrogate: a magnitude
    # leaderboard has no reason to surface this feature at all.
    shortlist = [
        r.feature_index
        for r in d.rank_candidates_for_concept(backend, artifact, concept_id=concept_id, shortlist_size=20)
    ]

    ok = (
        gate_a_all
        and gate_c_all
        and b_failures == [("en", "f3"), ("fr", "f3")]
        and worst <= 1e-12
        and verdict.features_scored == d_sae
        and verdict.surviving_feature_index != feature_index
        and feature_index not in shortlist
    )
    print(f"[C3c] 25995 G-A passed in all 6 cells : {gate_a_all}  (recorded: 6/6)")
    print(f"[C3c] 25995 G-C passed in all 6 cells : {gate_c_all}  (recorded: 6/6)")
    print(f"[C3c] 25995 G-B failures              : {b_failures} (recorded: f3 in both locales)")
    print(f"[C3c] max abs diff vs the 18 recorded floats for 25995: {worst:.3e} (must be <= 1e-12)")
    print(f"[C3c] 25995 in the pre-C3 magnitude shortlist of 20   : {feature_index in shortlist} (must be False)")
    print(f"[C3c] gate_a_passing_feature_count    : {verdict.gate_a_passing_feature_count}")
    print(f"[C3c] surviving_feature_index         : {verdict.surviving_feature_index} (must NOT be 25995 -- G-B kills it)")
    print(f"[C3c] whole-space scan wall seconds   : {seconds:.1f}s for {d_sae} features x 6 cells")
    print(f"[C3c] recorded shortlist rank of 25995 in run 413287  : {recorded_shortlist.index(feature_index)} of {len(recorded_shortlist)}")
    print(
        "[C3c] NOTE: any survivor count from a full-space scan is computed through G-B's within-cell "
        "(circular) denominator and G-A's referred negative set. It is an engineering measurement of "
        "the selector, NOT a discovery result."
    )
    print(f"[C3c] {'PASS' if ok else 'FAIL'}")
    return ok


def _mean_pairwise_jaccard(sets: list[set[int]]) -> float:
    import itertools
    import statistics

    return statistics.mean(
        len(a & b) / len(a | b) for a, b in itertools.combinations(sets, 2)
    )


def check_c3_applies_contrast(*, progress_path: Path, d_sae: int = 80000, top_n: int = 20, seed: int = 4242) -> bool:
    """FALSIFIER C3 (second): if the whole-space selector returns the same
    feature universe for every concept -- the pre-C3 failure -- the
    contrast is not being applied.

    Baseline, MEASURED on run 413287's preserved record: the 9 concepts'
    20-feature shortlists held 74 distinct features between them, 6
    features appeared in all 9, and mean pairwise Jaccard was 0.3910.

    The surrogate makes the failure mode reachable on purpose: a set of
    features is GLOBALLY LOUD -- large activations on every text of every
    concept, positives and controls alike -- so a ranker that never sees a
    control has every reason to return them for all 9 concepts, and a
    ranker that scores positives AGAINST controls has none. Both rankers
    run on the same matrices."""
    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    records = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    concept_ids = [r["verdict"]["concept_id"] for r in records]

    import final_pairing_targets as targets

    rng = np.random.default_rng(seed)
    loud = rng.choice(d_sae, size=40, replace=False)

    magnitude_sets: list[set[int]] = []
    contrast_sets: list[set[int]] = []
    for concept_id in concept_ids:
        texts: list[str] = []
        per_locale = {}
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            unrelated, near_miss, positives_by_family = d.concept_locale_texts(
                artifact, concept_id=concept_id, locale=locale
            )
            per_locale[locale] = (unrelated, near_miss, positives_by_family)
            texts += unrelated + near_miss + [t for f in sorted(positives_by_family) for t in positives_by_family[f]]
        index = {t: i for i, t in enumerate(texts)}

        matrix = np.where(
            rng.random((len(texts), d_sae)) < 0.9, 0.0, rng.random((len(texts), d_sae)) * 10.0
        ).astype(np.float32)
        # Globally loud on EVERY text: no contrast whatsoever.
        matrix[:, loud] = (rng.random((len(texts), loud.size)) * 200.0 + 800.0).astype(np.float32)
        # One genuinely concept-selective feature per concept: loud on the
        # positives only. A contrast-aware selector should find it.
        selective = int(rng.integers(0, d_sae))
        while selective in set(loud.tolist()):
            selective = int(rng.integers(0, d_sae))
        for locale in d.FROZEN_PROMPT_SET_LOCALES:
            _unrelated, _near_miss, positives_by_family = per_locale[locale]
            for family_texts in positives_by_family.values():
                for text in family_texts:
                    matrix[index[text], selective] = 50.0

        backend = d.Backend(
            pairing=targets.GEMMA_3_12B_IT_TARGET.name, model_obj=_TabulatedModel(texts),
            sae=_TabulatedSAE(matrix), hook_name=_SURROGATE_HOOK, d_sae=d_sae, d_model=len(texts),
            layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
            provenance={"model": {"repository": "tabulated", "local_path": "/tabulated"}, "sae": {"repository": "tabulated"}},
            checkpoint_hash="tabulated",
        )

        magnitude_sets.append({
            r.feature_index
            for r in d.rank_candidates_for_concept(backend, artifact, concept_id=concept_id, shortlist_size=top_n)
        })
        scan = d.score_full_feature_space(backend, artifact, concept_id=concept_id)
        order = np.lexsort((np.arange(d_sae), -scan.min_separation_auroc))
        contrast_sets.append(set(order[:top_n].tolist()))
        del matrix, backend

    magnitude_jaccard = _mean_pairwise_jaccard(magnitude_sets)
    contrast_jaccard = _mean_pairwise_jaccard(contrast_sets)
    magnitude_distinct = len({f for s in magnitude_sets for f in s})
    contrast_distinct = len({f for s in contrast_sets for f in s})

    ok = contrast_jaccard <= 0.15 and magnitude_jaccard > contrast_jaccard
    print("[C3d] run 413287 baseline (real, preserved): 74 distinct features in 180 slots, mean pairwise Jaccard 0.3910")
    print(f"[C3d] surrogate, magnitude ranker  : {magnitude_distinct} distinct across {len(concept_ids)} concepts, mean pairwise Jaccard {magnitude_jaccard:.4f}")
    print(f"[C3d] surrogate, whole-space G-A   : {contrast_distinct} distinct across {len(concept_ids)} concepts, mean pairwise Jaccard {contrast_jaccard:.4f} (must be <= 0.15)")
    print(f"[C3d] {'PASS' if ok else 'FAIL'}")
    return ok


def check_c5_subsumption(*, trials: int = 4000, seed: int = 20260817) -> bool:
    """FALSIFIER C5: with EQUAL-SIZED near_miss and unrelated control sets
    (15 and 15 in the frozen artifact), AUROC against the pooled set is
    identically the arithmetic mean of the two component AUROCs, so
    G-A >= 0.90 forces near_miss AUROC >= 0.80 > 0.75 and G-C can never
    reject anything G-A accepted. This is a theorem about the denominator
    shapes, not a property of one sample."""
    rng = np.random.default_rng(seed)
    worst = 0.0
    worst_c_min = 1.0
    gate_a_passes = 0
    gate_a_pass_gate_c_fail = 0
    g_c_min = 0.75
    for trial in range(trials):
        # The offset is swept so that a large fraction of trials actually
        # land in the G-A-passing regime -- a check that never reaches
        # that regime would pass vacuously.
        offset = 5.0 * (trial % 40) / 40.0
        pos = rng.random(10) * 5.0 + offset
        near = rng.random(15) * 5.0
        unrel = rng.random(15) * 5.0
        pooled = d._auroc_from_scores(pos.tolist(), [*unrel.tolist(), *near.tolist()])
        a_near = d._auroc_from_scores(pos.tolist(), near.tolist())
        a_unrel = d._auroc_from_scores(pos.tolist(), unrel.tolist())
        worst = max(worst, abs(pooled - (a_near + a_unrel) / 2.0))
        if pooled >= 0.90:
            gate_a_passes += 1
            worst_c_min = min(worst_c_min, a_near)
            gate_a_pass_gate_c_fail += int(a_near < g_c_min)
    ok = (
        worst <= 1e-12
        and gate_a_passes > 0
        and worst_c_min >= 0.80 - 1e-12
        and gate_a_pass_gate_c_fail == 0
    )
    print(f"[C5] max |pooled - mean(component)| over {trials} trials: {worst:.3e} (must be <= 1e-12)")
    print(f"[C5] trials that actually passed G-A (>= 0.90): {gate_a_passes} (must be > 0 -- otherwise vacuous)")
    print(f"[C5] lowest near_miss AUROC among them: {worst_c_min:.4f} (must be >= 0.80, G-C's floor is {g_c_min})")
    print(f"[C5] G-A pass with G-C fail: {gate_a_pass_gate_c_fail} (expected 0; run 413287 recorded 0 of 1080)")
    print(f"[C5] {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------
# SHADOW G-B (2026-08-15). MEASUREMENT ONLY -- no check in this section may
# change a gate, a threshold or a verdict, and none of them do: they read
# `d.compute_shadow_fire_rate_corpus_max` / `d.shadow_fire_rate_matrix`,
# which are recorded beside the frozen statistic and consulted by nothing.
#
# The question these checks exist to serve is the one that has never had
# evidence behind it: what does the CORRECTED G-B statistic's distribution
# actually look like, so that `G_B_fire_rate_min` can be re-derived against
# it instead of asserted? Nothing here proposes a new threshold.
# ---------------------------------------------------------------------------


def check_shadow_arithmetic(*, trials: int = 3000, seed: int = 20260818) -> bool:
    """FALSIFIER SHADOW-A: three properties of the shadow statistic, each of
    which is what makes the measurement interpretable at all.

    1. VECTORISED == SCALAR, bit-for-bit, dead columns and zero references
       included. Otherwise the run-level distribution is not the same
       quantity as the per-cell record.
    2. AT `corpus_max == observed_max` THE SHADOW STATISTIC IS EXACTLY THE
       FROZEN ONE. This is what makes the two comparable: the ONLY
       difference between them is the reference scale.
    3. THE SHADOW STATISTIC IS NON-INCREASING IN `corpus_max`. Combined
       with (2) this fixes the direction of every possible correction
       without measuring a single activation: a cell's shadow rate is >=
       its within-cell rate iff the feature's background max is <= its
       within-cell max, and <= it otherwise.

    Property 3 is the whole reason a re-derivation is tractable: it means
    'would this cell clear 0.70 under the corrected scale' reduces to one
    measurable comparison per cell, not a new calibration per cell."""
    rng = np.random.default_rng(seed)
    vector_mismatches = 0
    identity_mismatches = 0
    monotonicity_violations = 0
    for _ in range(trials):
        n_pos, n_feat = 10, 6
        pos = np.where(rng.random((n_pos, n_feat)) < 0.5, 0.0, rng.random((n_pos, n_feat)) * 5.0)
        if rng.random() < 0.25:
            pos[:, rng.integers(0, n_feat)] = 0.0
        reference = np.where(rng.random(n_feat) < 0.2, 0.0, rng.random(n_feat) * 8.0)
        rates, floors = d.shadow_fire_rate_matrix(pos, floor_fraction=_FLOOR_FRACTION, corpus_max=reference)
        for j in range(n_feat):
            column = pos[:, j].astype(float).tolist()
            ref_rate, ref_floor, _degenerate = d.compute_shadow_fire_rate_corpus_max(
                column, floor_fraction=_FLOOR_FRACTION, corpus_max=float(reference[j])
            )
            vector_mismatches += int(rates[j] != ref_rate or floors[j] != ref_floor)

            observed_max = max(column)
            frozen_rate, _frozen_floor = d.compute_gate_b_fire_rate(column, floor_fraction=_FLOOR_FRACTION)
            at_observed_max, _f, _dg = d.compute_shadow_fire_rate_corpus_max(
                column, floor_fraction=_FLOOR_FRACTION, corpus_max=observed_max
            )
            identity_mismatches += int(at_observed_max != frozen_rate)

            previous = 1.1
            for scale in np.linspace(0.0, max(observed_max, 1.0) * 2.0, 25):
                rate, _f, _dg = d.compute_shadow_fire_rate_corpus_max(
                    column, floor_fraction=_FLOOR_FRACTION, corpus_max=float(scale)
                )
                monotonicity_violations += int(rate > previous + 1e-15)
                previous = rate

    ok = vector_mismatches == 0 and identity_mismatches == 0 and monotonicity_violations == 0
    print(f"[SHADOW-A] vectorised-vs-scalar mismatches over {trials} trials : {vector_mismatches} (expected 0)")
    print(f"[SHADOW-A] shadow(corpus_max=observed_max) != frozen G-B       : {identity_mismatches} (expected 0)")
    print(f"[SHADOW-A] monotonicity violations in corpus_max               : {monotonicity_violations} (expected 0)")
    print(
        "[SHADOW-A] CONSEQUENCE: for every cell, shadow >= within-cell iff the feature's background "
        "max <= its within-cell max, with equality when they are equal. The direction of the "
        "correction is decided by one measurable comparison per cell."
    )
    print(f"[SHADOW-A] {'PASS' if ok else 'FAIL'}")
    return ok


def check_shadow_against_the_preserved_record(progress_path: Path) -> bool:
    """FALSIFIER SHADOW-B: states exactly what the preserved record CAN and
    CANNOT settle, and measures the part it can.

    CANNOT: run 413287 preserved verdicts, not activations, and its records
    predate `observed_max`/`activation_floor` being recorded at all (they
    are absent from every one of its 1080 G-A/G-B cells -- checked below,
    not assumed). No shadow fire rate is therefore recoverable from this
    file for ANY cell, including feature 25995's. Producing them requires
    re-running the model, which is what `final_pairing_concept_discovery.py
    --mode grid`'s `shadow_gate_b_summary` now emits and what
    `--mode replay` re-scores. THAT MEASUREMENT IS OWED AND IS NOT MADE
    HERE.

    CAN: the anti-correlation that motivates the whole question, and the
    exact inequality each of feature 25995's two failing cells has to
    satisfy for the corrected statistic to clear the current bar. Both are
    computed from the preserved floats alone."""
    ab, c = _load_cells(progress_path)
    have_observed_max = sum(1 for cell in ab if "observed_max" in cell)

    from scipy.stats import spearmanr

    separation = np.array([cell["separation_auroc"] for cell in ab])
    fire = np.array([cell["fire_rate"] for cell in ab])
    rho = float(spearmanr(separation, fire).statistic)

    # The same correlation with the 182 degenerate cells removed -- they are
    # artifacts, so the honest version of the statistic excludes them.
    c_by_cell = {(x["concept_id"], x["locale"], x["family"], x["feature_index"]): x for x in c}
    live = [
        cell for cell in ab
        if not _is_dead_cell(cell, c_by_cell[(cell["concept_id"], cell["locale"], cell["family"], cell["feature_index"])])
    ]
    rho_live = float(spearmanr(
        np.array([cell["separation_auroc"] for cell in live]),
        np.array([cell["fire_rate"] for cell in live]),
    ).statistic)

    print(f"[SHADOW-B] cells in the preserved record                     : {len(ab)}")
    print(f"[SHADOW-B] cells carrying observed_max / activation_floor    : {have_observed_max} (pre-C4 record: expected 0)")
    print(f"[SHADOW-B] Spearman(separation_auroc, fire_rate), all cells  : {rho:+.4f}")
    print(f"[SHADOW-B] the same with the 182 degenerate cells excluded   : {rho_live:+.4f} over {len(live)} live cells")
    print(
        "[SHADOW-B] READ: a G-B statistic ANTI-correlated with the separation the search is for is "
        "not measuring firing. This is the motivation for the shadow metric, not evidence that the "
        "shadow metric fixes it -- that requires the GPU distribution, which is owed."
    )

    # Feature 25995: the exact condition, per failing cell.
    recorded_ab, _recorded_c, _shortlist = _recorded_25995(progress_path)
    print("[SHADOW-B] feature 25995 (formal_register), the case the question turns on:")
    for (locale, family), record in sorted(recorded_ab.items()):
        fired = round(record["fire_rate"] * 10)
        print(
            f"[SHADOW-B]   {locale}/{family}: separation_auroc={record['separation_auroc']:.4f} "
            f"fire_rate_within_cell={record['fire_rate']:.1f} ({fired}/10 positives at or above "
            f"0.20 x that cell's own max) gate_b_passed={record['gate_b_passed']}"
        )
    print(
        f"[SHADOW-B]   The two failing cells are en/f3 (0.6) and fr/f3 (0.4). Under the shadow "
        f"reference each clears 0.70 IFF at least {int(np.ceil(_FIRE_RATE_MIN * 10))} of its 10 "
        f"positives sit at or above 0.20 x corpus_max, i.e. iff corpus_max <= 5 x p7, where p7 is "
        f"that cell's 7th-largest positive score."
    )
    print(
        "[SHADOW-B]   NECESSARY CONDITION, derived from the record alone: the within-cell rate of "
        "0.6 means p7 < 0.20 x p1, so 5 x p7 < p1. The shadow reference can only rescue these cells "
        "if the feature's max over the background `unrelated` split is STRICTLY BELOW its max on "
        "these very prompts -- i.e. only if 25995 is genuinely more active on formal_register's f3 "
        "prompts than anywhere in the background corpus."
    )
    print(
        "[SHADOW-B]   p1 and p7 were NOT preserved. This check therefore reports the inequality, "
        "not a value. WHAT WOULD SETTLE IT: one GPU run of --mode grid, whose per-cell "
        "fire_rate_corpus_max / corpus_max fields answer it directly for both cells."
    )

    ok = have_observed_max == 0 and rho < 0
    print(f"[SHADOW-B] {'PASS' if ok else 'FAIL'} (asserts the record is pre-C4 and the anti-correlation is negative)")
    return ok


def check_shadow_distribution_shape(progress_path: Path, *, d_sae: int = 80000, seed: int = 25995) -> bool:
    """FALSIFIER SHADOW-C: an END-TO-END shadow distribution over a full
    d_sae x 6-cell space, produced by the REAL code path
    (`score_full_feature_space` -> `summarise_shadow_distribution` ->
    `aggregate_shadow_summaries`), on the SAME tabulated construction
    `check_c3_recovers_the_known_answer` uses -- the one that reproduces
    all 18 of run 413287's recorded floats for feature 25995 exactly.

    WHAT THIS IS: proof that the run-level shadow summary is computed,
    complete (every (feature, cell) pair binned exactly once), and shaped
    the way a re-derivation needs, plus a worked example of the two
    distributions side by side on the same bins.

    WHAT THIS IS NOT: run 413287's distribution. The construction fixes the
    RANK statistics (that is what the recorded AUROCs and fire rates pin
    down); it does not and cannot fix the absolute activation scale, and
    the shadow statistic is a function of the ratio between two absolute
    scales. Every number below marked SYNTHETIC is a property of the
    construction. THE REAL DISTRIBUTION IS OWED FROM ONE GPU RUN and is
    emitted by `--mode grid` as `grid.json`'s `shadow_gate_b_summary`."""
    import final_pairing_targets as targets

    concept_id, feature_index = _F25995
    recorded_ab, _recorded_c, _shortlist = _recorded_25995(progress_path)

    artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)
    texts: list[str] = []
    per_locale: dict[str, tuple[list[str], list[str], dict[str, list[str]]]] = {}
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        unrelated, near_miss, positives_by_family = d.concept_locale_texts(
            artifact, concept_id=concept_id, locale=locale
        )
        per_locale[locale] = (unrelated, near_miss, positives_by_family)
        texts += unrelated + near_miss + [t for f in sorted(positives_by_family) for t in positives_by_family[f]]
    text_index = {t: i for i, t in enumerate(texts)}

    rng = np.random.default_rng(seed)
    matrix = np.where(
        rng.random((len(texts), d_sae)) < 0.85, 0.0, rng.random((len(texts), d_sae)) * 5000.0
    ).astype(np.float32)

    column = np.zeros(len(texts), dtype=np.float32)
    for locale in d.FROZEN_PROMPT_SET_LOCALES:
        unrelated, near_miss, positives_by_family = per_locale[locale]
        for text, value in zip(unrelated, _UNRELATED_LADDER[locale], strict=True):
            column[text_index[text]] = value
        for text, value in zip(near_miss, _NEAR_MISS_LADDER[locale], strict=True):
            column[text_index[text]] = value
        for family, family_texts in positives_by_family.items():
            n_high, lows = _CELL_DESIGN[(locale, family)]
            for text, value in zip(family_texts, [_HIGH_POSITIVE] * n_high + lows, strict=True):
                column[text_index[text]] = value
    matrix[:, feature_index] = column

    backend = d.Backend(
        pairing=targets.GEMMA_3_12B_IT_TARGET.name, model_obj=_TabulatedModel(texts),
        sae=_TabulatedSAE(matrix), hook_name=_SURROGATE_HOOK, d_sae=d_sae, d_model=len(texts),
        layer=targets.GEMMA_3_12B_IT_TARGET.expected_layer,
        provenance={"model": {"repository": "tabulated", "local_path": "/tabulated"}, "sae": {"repository": "tabulated"}},
        checkpoint_hash="tabulated",
    )

    cache = d.FeatureMatrixCache()
    d.pin_shared_substrate(cache, backend, artifact)
    reference = d.shadow_corpus_max_per_feature(backend, artifact, cache=cache)
    verdict = d.evaluate_concept_on_pairing(
        backend, artifact, concept_id=concept_id, cache=cache, corpus_max_by_feature=reference
    )
    if verdict.status == "error":
        print(f"[SHADOW-C] FAIL: verdict errored -- {verdict.error}")
        return False

    summary = verdict.shadow_gate_b_summary
    grid_summary = d.aggregate_shadow_summaries([verdict])
    pairs = summary["feature_cell_pairs"]
    complete = (
        pairs == d_sae * 6
        and sum(summary["fire_rate_within_cell"]["histogram"]) == pairs
        and sum(summary["fire_rate_corpus_max"]["histogram"]) == pairs
        and grid_summary["feature_cell_pairs"] == pairs
    )

    print(f"[SHADOW-C] SYNTHETIC construction: {d_sae} features x {summary['cells']} cells = {pairs} pairs")
    print(f"[SHADOW-C] every pair binned exactly once, per-concept and grid-level: {complete}")
    for statistic in ("fire_rate_within_cell", "fire_rate_corpus_max"):
        q = summary[statistic]["quantiles"]
        print(
            f"[SHADOW-C] SYNTHETIC {statistic:>22}: median {q['median']:.2f}  mean {q['mean']:.4f}  "
            f"p05 {q['p05']:.2f}  p95 {q['p95']:.2f}  pairs >= {summary['current_fire_rate_min']}: "
            f"{summary[statistic]['pairs_at_or_above_current_min']}"
        )
    print(f"[SHADOW-C] SYNTHETIC degenerate references (corpus_max == 0)   : {summary['degenerate_reference_features']}")
    print(f"[SHADOW-C] SYNTHETIC dead (feature, cell) pairs                : {summary['dead_cell_pairs']}")
    print(
        "[SHADOW-C] The counts above are (feature, cell) pairs of ONE gate's statistic. They are NOT "
        "conjoined with G-A or G-C, NOT minimised across cells, and NOT a survivor count."
    )

    candidate = next(
        (x for x in verdict.candidates_evaluated if x["feature_index"] == feature_index), None
    )
    if candidate is None:
        print("[SHADOW-C] FAIL: feature 25995 absent from the emitted record")
        return False
    ab = {(r["locale"], r["family"]): r for r in candidate["gate_a_b_results"]}

    worst = max(
        abs(ab[key]["separation_auroc"] - recorded_ab[key]["separation_auroc"]) for key in recorded_ab
    )
    worst = max(worst, max(abs(ab[key]["fire_rate"] - recorded_ab[key]["fire_rate"]) for key in recorded_ab))

    print("[SHADOW-C] feature 25995's six cells under this construction (SYNTHETIC absolute scale):")
    for key in sorted(ab):
        r = ab[key]
        print(
            f"[SHADOW-C]   {key[0]}/{key[1]}: within_cell={r['fire_rate_within_cell']:.1f} "
            f"(gate_b_passed={r['gate_b_passed']}, floor={r['activation_floor']:.4g} = 0.20 x observed_max "
            f"{r['observed_max']:.4g})  |  SHADOW corpus_max={r['corpus_max']:.4g} -> "
            f"floor={r['shadow_activation_floor']:.4g} -> fire_rate_corpus_max={r['fire_rate_corpus_max']:.1f}"
        )
    verdicts_unchanged = (
        all(r["verdict_computed_from"] == "fire_rate_within_cell" for r in ab.values())
        and sorted(k for k, r in ab.items() if not r["gate_b_passed"]) == [("en", "f3"), ("fr", "f3")]
        and all(r["gate_a_passed"] for r in ab.values())
    )
    print(f"[SHADOW-C] G-B still fails on exactly en/f3 and fr/f3, from the within-cell statistic: {verdicts_unchanged}")
    print(f"[SHADOW-C] max abs diff vs the 12 recorded G-A/G-B floats for 25995: {worst:.3e} (must be <= 1e-12)")
    print(
        "[SHADOW-C] THE f3 SHADOW VALUES ABOVE ARE A PROPERTY OF THIS CONSTRUCTION'S ABSOLUTE SCALE, "
        "NOT A MEASUREMENT OF RUN 413287. The construction was built to reproduce the recorded RANK "
        "statistics; the shadow statistic depends on the ratio corpus_max / observed_max, which no "
        "recorded value pins down. Falsified by: one GPU run reporting a different "
        "corpus_max for 25995 -- which is expected and is the point."
    )

    ok = complete and verdicts_unchanged and worst <= 1e-12
    print(f"[SHADOW-C] {'PASS' if ok else 'FAIL'}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("checks", nargs="*", default=[], help="c1 | c2 | c3 | c5 | shadow (default: all)")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS, help="preserved run 413287 progress.jsonl")
    args = parser.parse_args(argv)

    all_checks = {"c1", "c2", "c3", "c5", "shadow"}
    selected = set(args.checks) or all_checks
    if args.all:
        selected = all_checks

    results: dict[str, bool] = {}
    if "c1" in selected:
        if not args.progress.is_file():
            print(f"[C1] SKIPPED-AS-FAILED: preserved run data not found at {args.progress}")
            results["c1"] = False
        else:
            results["c1"] = check_c1(args.progress)
    if "c2" in selected:
        results["c2"] = check_c2()
    if "c3" in selected:
        results["c3a"] = check_c3_auroc_equivalence()
        results["c3b"] = check_c3_fire_rate_equivalence()
        if not args.progress.is_file():
            print(f"[C3c] SKIPPED-AS-FAILED: preserved run data not found at {args.progress}")
            results["c3c"] = False
        else:
            results["c3c"] = check_c3_recovers_the_known_answer(args.progress)
            results["c3d"] = check_c3_applies_contrast(progress_path=args.progress)
    if "c5" in selected:
        results["c5"] = check_c5_subsumption()
    if "shadow" in selected:
        results["shadow_a"] = check_shadow_arithmetic()
        if not args.progress.is_file():
            print(f"[SHADOW-B] SKIPPED-AS-FAILED: preserved run data not found at {args.progress}")
            results["shadow_b"] = False
        else:
            results["shadow_b"] = check_shadow_against_the_preserved_record(args.progress)
            results["shadow_c"] = check_shadow_distribution_shape(args.progress)

    failed = [name for name, ok in results.items() if not ok]
    print(f"\n{'ALL FALSIFIERS PASSED' if not failed else 'FALSIFIERS FAILED: ' + ', '.join(sorted(failed))}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
