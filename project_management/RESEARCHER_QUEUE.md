# Researcher Queue

This file separates scientific decisions from cluster execution. The Lab
Assistant may execute only after every meaningful protocol field is settled;
identifying an execution owner does not authorize or complete the work.

## Open Human / Researcher decisions

| ID | Decision | Why Researcher-owned | Downstream execution |
|---|---|---|---|
| Q-003 | Calibrate A6 bands from the completed certification batch and decide any D3 version bump/recompute. | Thresholds are scientific policy. | Lab Assistant may retrieve or mechanically summarize the approved batch; Auditor accepts evidence. |
| Q-004 | Supply or formally accept the corpus dataset `revision: unknown` limitation. | Dataset provenance sufficiency is a scientific claim decision. | Lab Assistant may inspect authorized corpus metadata. |
| Q-005 | Approve non-English census terms and required negative controls in the real ConceptBattery. | ED-8/ED-9 reserve scientific content authorship to the Researcher. | Lab Assistant runs the approved production census. |
| Q-006 | Decide whether Lodestar’s NumPy floor may be relaxed in `D:\lodstar`. | ED-19 places dependency policy in the Lodestar repository. | Engineer acts in Lodestar only if authorized; Lab Assistant later runs approved integration. |
| Q-007 | Author/approve A12 evaluation compatibility policy and claim-mode prompts/spec. | A12 and claim content are scientific policy. | Lab Assistant may execute the resulting judge/report protocol. |
| Q-009 | Author `tests/fixtures/canary/cheese_reference.json` from an approved production certification run. | ED-23 requires a Researcher-frozen real reference. | Lab Assistant acquires the approved measurements; Engineer records the authorized fixture if separately assigned. |
| Q-010 | Decide tracking/retention policy for scientific `reports/` and curated `results/`. | A-003 settled only `project_management/`; A-005 remains open. | Orchestrator applies the governance decision; no scientific files are deleted implicitly. |
| Q-012 | Decide which scientific claims, if any, the existing T1.1 multilingual outputs support and whether their current provenance is sufficient. | Local outputs and a completion note exist, but scientific sufficiency and interpretation are not mechanical facts. | Lab Assistant may recover cluster provenance if requested; Auditor accepts the evidence chain. |

## Lab Assistant execution queue

| ID | Procedure | Readiness | Independent acceptance |
|---|---|---|---|
| LA-001 | Inspect/recover the four historical certification A10 RunCards or establish their absence from authorized TamIA files/logs. | Needs a bounded read-only path/log packet; no scientific choice is required. | Auditor before WP2/WP7 status changes. |
| LA-002 | Build/record the ED-36 external bundle and fresh TamIA environment, run exact TransformerLens equivalence, then execute fifth certification. | Blocked by R6-V5 acceptance/stabilization and exact preflight. | Auditor before fifth A6/WP2 acceptance. |
| LA-003 | Run approved cheese census/characterization/validation chain for `rwu04lpb`: A3 + A7 → A8 for feature 9056. | Scientific packet/R6/R7 are accepted and census resources are recovered. Still blocked by R10-C2 acceptance, ED-36 bundle/venv/equivalence, a clean execution revision, and explicit execution authority. | Auditor before A8 is used for claim-mode steering. |
| LA-004 | Run T1.2 clamp-to-zero steer for the approved seed schedule, then the separately approved judge path. | Blocked by accepted LA-003 A8, filled A7/A8 hashes, environment identity, launcher integration, and—beyond seed-0 preparation—ED-19/A12 readiness. | Auditor, then Researcher interpretation. |
| LA-005 | Execute real-Qwen nightly, production census, validate, or other cluster-only tests. | Each requires its own exact protocol/config/revision/resource packet. | Auditor per evidence milestone. |
| LA-006 | Recover or verify T1.1 multilingual run provenance from TamIA. | Only if Q-012 requires more provenance; do not rerun or change parameters implicitly. | Auditor before provenance promotion. |

## Closed or transferred items

| Former ID | Disposition |
|---|---|
| Q-001 | Transferred to Lab Assistant execution item LA-001; evidence acceptance remains Auditor-owned. |
| Q-002 | Closed by ED-35: authoritative WP2 population is five. |
| Q-008 | Split: Researcher supplies scientific fields; Lab Assistant owns fully specified cluster execution through LA-002–LA-005. |
| Q-010 (project-management portion) | Closed by A-003: canonical `project_management/` is local-only and ignored. Scientific report/result tracking remains open under Q-010/A-005. |
| Q-011 | Closed by Q-011-C4: T1.2 scientific content, statistics, scheduling, A2/A8 chain, ED-8 battery v1.1.0 authorship, and golden rules are authoritative. Implementation is T1.2-C1; execution remains LA-003/LA-004 gated. |
| Q-013 | Closed, corrected: census uses Tamia whole-node `h100:4`/`mem=0` with 8 CPUs baseline (16 only for confirmed fast-tokenizer parallelism) and evidence-sized walltime; `revision: unknown` is an explicit empirical-pinning limitation; seed-0 review is structural/blinded; later mechanical hash substitution has four chain checks. |
| R9-D1 | Closed: universal ABI-none/platform-any wheel tags are approved; uv 0.8.22 is the sole platform-coupled exception; virtualenv embedded seed setuptools must equal 83.0.0. Operational evidence retry transferred to Engineer 2 under R9-X2B. |
| R9-D2 | Closed: the unchanged virtualenv wheel may retain fully enumerated embedded seeds only as inert bytes under mandatory unseeded isolation; ensurepip is forbidden; pip bootstrap inventory is exactly pip 25.0; wheel is pinned at 0.45.0. Evidence acquisition transferred to R9-X2C. |
| P0 | **Cancelled 2026-08-02 by Researcher.** Researcher wants the actual ablation critical path, not a presentation-evidence packet. | No action. | None. |
