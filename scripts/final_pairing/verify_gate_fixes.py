#!/usr/bin/env python3
"""Falsifiers for the 2026-08-15 zero-survivor fixes (C1/C2/C3/C5).

Every check here is a FALSIFIER, not a demonstration: each one states, up
front, the exact number that must come out, and exits non-zero when it does
not. None of them may be "adjusted to pass" -- a failing check is the
result.

Run:  python scripts/final_pairing/verify_gate_fixes.py --all
      python scripts/final_pairing/verify_gate_fixes.py c1 \
          --progress D:/devcache/tmp/fp413287/primary/qwen/grid/state/progress.jsonl

READ THIS BEFORE QUOTING ANY NUMBER THIS SCRIPT PRINTS. The 182 records the
C1 check flips are ARTIFACTS of the degenerate-scale defect, not G-B passes.
A G-B pass rate computed with them included is not a fact about run 413287
and must not be quoted as one. Separately, EVERY G-B figure in this
codebase -- before or after C1 -- is computed against a within-cell
reference scale that is derived from the very prompts it judges (see
`compute_gate_b_fire_rate`'s own docstring). C1 removes the fully
degenerate case; it does not make that denominator non-circular, and
correcting the scale is explicitly not authorised here.
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

#: Run 413287's frozen G-B parameters, read back from the artifact rather
#: than restated here wherever the artifact is reachable.
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
# against progress.jsonl remains OWED before any production rerun.
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


def _load_pre_c2_module(rev: str = "98a7108"):
    """Loads the pre-C2 file straight out of git, under its own module name,
    from a path inside scripts/final_pairing/ so its REPO_ROOT and sys.path
    bootstrap resolve exactly as they did at that revision."""
    import importlib.util
    import subprocess
    import tempfile

    source = subprocess.run(
        ["git", "show", f"{rev}:scripts/final_pairing/final_pairing_concept_discovery.py"],
        cwd=SCRIPT_DIR.parents[1], capture_output=True, text=True, check=True,
    ).stdout
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
    drop by at least 20x."""
    import time

    pre, tmp_path = _load_pre_c2_module(rev)
    try:
        # Hold C1 constant: the guard is C1's change, not C2's.
        pre.compute_gate_b_fire_rate = d.compute_gate_b_fire_rate

        artifact = d.load_frozen_prompt_artifact(d.REPO_ROOT)

        old_backend, old_model = _surrogate_backend(pre)
        t0 = time.perf_counter()
        old_verdict = pre.evaluate_concept_on_pairing(
            old_backend, artifact, concept_id=concept_id, shortlist_size=shortlist_size
        )
        old_seconds = time.perf_counter() - t0

        new_backend, new_model = _surrogate_backend(d)
        t0 = time.perf_counter()
        new_verdict = d.evaluate_concept_on_pairing(
            new_backend, artifact, concept_id=concept_id, shortlist_size=shortlist_size
        )
        new_seconds = time.perf_counter() - t0

        if old_verdict.status == "error" or new_verdict.status == "error":
            print(f"[C2] FAIL: verdict errored -- old={old_verdict.error!r} new={new_verdict.error!r}")
            return False

        def _cells(verdict):
            out = {}
            for candidate in verdict.candidates_evaluated:
                for r in candidate["gate_a_b_results"]:
                    out[("A", r["feature_index"], r["locale"], r["family"])] = r["separation_auroc"]
                    out[("B", r["feature_index"], r["locale"], r["family"])] = r["fire_rate"]
                for r in candidate["gate_c_results"]:
                    out[("C", r["feature_index"], r["locale"], r["family"])] = r["near_miss_auroc"]
            return out

        old_cells, new_cells = _cells(old_verdict), _cells(new_verdict)
        same_keys = set(old_cells) == set(new_cells)
        worst = max((abs(old_cells[k] - new_cells[k]) for k in old_cells if k in new_cells), default=float("inf"))
        exact = sum(1 for k in old_cells if k in new_cells and old_cells[k] == new_cells[k])

        pass_ratio = old_model.forward_passes / max(new_model.forward_passes, 1)
        time_ratio = old_seconds / max(new_seconds, 1e-9)
        ok = same_keys and worst <= 1e-9 and pass_ratio >= 20.0

        print(f"[C2] concept                        : {concept_id} ({len(old_cells)} emitted values compared)")
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
    for _ in range(trials):
        pos = rng.random(10) * 5.0
        near = rng.random(15) * 5.0
        unrel = rng.random(15) * 5.0
        pooled = d._auroc_from_scores(pos.tolist(), [*unrel.tolist(), *near.tolist()])
        a_near = d._auroc_from_scores(pos.tolist(), near.tolist())
        a_unrel = d._auroc_from_scores(pos.tolist(), unrel.tolist())
        worst = max(worst, abs(pooled - (a_near + a_unrel) / 2.0))
        if pooled >= 0.90:
            worst_c_min = min(worst_c_min, a_near)
    ok = worst <= 1e-12 and worst_c_min >= 0.80 - 1e-12
    print(f"[C5] max |pooled - mean(component)| over {trials} trials: {worst:.3e} (must be <= 1e-12)")
    print(f"[C5] lowest near_miss AUROC seen among cells with pooled AUROC >= 0.90: {worst_c_min:.4f} (must be >= 0.80)")
    print(f"[C5] {'PASS' if ok else 'FAIL'}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("checks", nargs="*", default=[], help="c1 | c2 | c3 | c5 (default: all)")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS, help="preserved run 413287 progress.jsonl")
    args = parser.parse_args(argv)

    all_checks = {"c1", "c2", "c3", "c5"}
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
    if "c5" in selected:
        results["c5"] = check_c5_subsumption()

    failed = [name for name, ok in results.items() if not ok]
    print(f"\n{'ALL FALSIFIERS PASSED' if not failed else 'FALSIFIERS FAILED: ' + ', '.join(sorted(failed))}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
