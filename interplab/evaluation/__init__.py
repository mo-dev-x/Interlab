"""SS8 boundary (§5 SS8): blinding, Lodestar ingestion adapters,
capability-degradation module, `eval_compat_map` I/O.

`interplab.evaluation` is the only subsystem permitted to import
`lodestar-eval` (§1). The real Lodestar adapter / judge path remains paused
under ED-19: the sanctioned stack is now `sae-lens==6.44.2`, but the locked
environment still carries `numpy==1.26.4` while `lodestar-eval` requires
`numpy>=2`, so the live runtime remains environment-limited and fails closed
by default. The SS8 boundary code itself is present: `blinding`,
`capability`, `lodestar_adapter`, and `compat_map`, consumed by
`interplab.jobs.judge`.
"""
