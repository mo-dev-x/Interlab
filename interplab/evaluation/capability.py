"""SS8 capability-degradation module (§5 SS8, ED-20): assembles the
capability_delta payload from already-computed per-arm perplexities.

ED-20, exact payload shape: `{slice: {content_hash, location}, n_tokens,
per_arm: [{arm, scale, ppl}]}`. Only perplexities are stored -- consumers
derive deltas; the baseline arm is included with `scale = null`.
Statistics are never computed from this field (`interplab.reports.statistics`
reads only `lodestar.per_prompt_scores`, unchanged by this module).

This module does NOT compute perplexities itself: doing so means running a
forward pass under each arm's intervention, which needs
`interplab.interventions.attach` -- but §1 only grants `interplab.evaluation`
`core, registry, stats` (not `interventions`). Assembling this field is
therefore split: whatever job eventually writes it (ED-20: "Judge writes
this field") must obtain per-arm perplexities externally, then hand them
here only to be packaged into ED-20's exact shape. `jobs.judge` does that
through the isolated evaluation runtime boundary rather than by importing
`interplab.interventions` into this package.
"""

from __future__ import annotations


def assemble_capability_delta(
    *, slice_ref: dict, n_tokens: int, per_arm: list[tuple[str, float | None, float]]
) -> dict:
    """`per_arm`: `[(arm, scale, ppl)]`, perplexities already computed by
    the caller. `scale=None` MUST pair with the baseline arm (ED-20:
    "Baseline arm is included with scale = null"). Returns ED-20's exact
    shape verbatim -- this function only validates and assembles, it never
    computes a perplexity."""
    return {
        "slice": slice_ref,
        "n_tokens": n_tokens,
        "per_arm": [{"arm": arm, "scale": scale, "ppl": ppl} for arm, scale, ppl in per_arm],
    }
