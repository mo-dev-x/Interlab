"""SS8 boundary (§5 SS8): blinding, Lodestar ingestion adapters,
capability-degradation module, `eval_compat_map` I/O.

`interplab.evaluation` is the only subsystem permitted to import
`lodestar-eval` (§1). As of WP8, `lodestar_adapter.py` is paused: ED-19's
NumPy-2 migration failed its acceptance gate (a hard, disjoint `typer`
version conflict between the frozen `sae-lens==3.23.0` and `lodestar-eval`
-- see the WP8 completion report) with no path that avoids modifying
`sae-lens`, which ED-19 forbids. `blinding`, `capability`, and
`compat_map` are unaffected (lodestar-agnostic by design) and fully
implemented.
"""
