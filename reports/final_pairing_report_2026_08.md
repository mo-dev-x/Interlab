# Final pairing: concept groups, causal instrumentation, and a measured refusal to assert

**Author:** Mohamed El Yazid — IID
**Period:** 2026-08-13 → 2026-08-22
**Repositories:** `Interlab` (renamed from `qwen-sae-interp`), branch `final-pairing-harness`, HEAD
`2f5bb39` · `sae-concept-lab`, branch `main`, HEAD `e3b6fc0`
**Status:** discovery and control arms **complete and measured**; the intervened (causal) arm is
**specified and not run**; the interactive tool is **shipped and runnable from a clean clone**. Every
number below is traceable to a named job id, artifact digest and commit. Nothing in this document is
an estimate.

---

## 0. What this sprint was for, and what it produced

The goal was to find the feature **groups** that steer a whole concept — cheese, and two switchable
political personas — under both amplification and group ablation, on two freshly ratified pairings:
`gemma-3-12b-it` + `gemma-scope-2-12b-it` (layer 29) and `Qwen3.5-27B` + `SAE-Res-Qwen3.5-27B-W80K-L0_100`
(layer 38).

It produced the following, each traceable to a job id or a commit:

1. **Cheese cannot have a complete feature group on this corpus.** Proven, not estimated.
2. **Both personas have surviving features on both models** — single features, not groups.
3. **The first admissibility matrices `A[f,c]` in the project's history**, full-space on all four lanes.
4. **A measured control floor of zero**: instruction-tuned models actively refuse to assert
   national exceptionalism, and chat-formatting makes them refuse *harder*.
5. **The causal arm was not reached.** §7 states exactly what remains and why the gap is a schedule
   fact, not a hidden failure.
6. **The interactive tool shipped.** `sae-concept-lab` is public, runnable from a clean clone by
   someone with no context, and carries the measured concept for both pairings — with every fake
   placeholder removed from the build and its own refusals wired to actually fire. §6b.

---

## 1. Cheese: a complete group is impossible, and this is a proof

Gate G-A requires separation AUROC ≥ 0.90 in a cell. With v2 counts (10 positives per cell,
|near_miss| = |unrelated| = 15), separation lives on an exact **1/600 lattice** — 300 pooled pairs,
600 with tie-halves — against an integer bar of **540/600**.

Full-space ceilings over all 81,920 Qwen features, from job **416453** at `ed18ae1`:

| cell | ceiling | lattice position | admissible features |
|---|---|---|---|
| en/f1 | 0.913333 | 548/600, **+8** | — |
| en/f2 | 0.913333 | 548/600, **+8** | — |
| en/f3 | 1.000000 | 600/600, **+60** | 16 |
| fr/f1 | 0.901667 | 541/600, **+1** | — |
| **fr/f2** | **0.890000** | **534/600, −6** | **0** |
| fr/f3 | 1.000000 | 600/600, **+60** | 24 |

**The operative fact.** A ceiling is a maximum over every feature. `fr/f2 = 0.890` sits *below* the
bar, so `A[f, fr/f2] = 0` for **every** feature f, so `cov(G)[fr/f2] = 0` for **every** group G.
`cov = 1⁶` is therefore unreachable at every arity, under every tier, under every tie-break.
**Cheese's coverage ceiling is |cov| ≤ 5.** Features admissible in at least one cell: 30.

Two honest qualifications. First, `fr/f1` clears by **one lattice step** — a single pair inversion
out of 150 drops it below the bar, so it is fragile in a way a decimal reading hides. Second, a
maximum over 81,920 features does **not** reduce corpus uncertainty, because every feature is scored
against the same 10 positives and the error is common-mode. The verdict state is therefore
`CEILINGED_ON_THIS_CORPUS_WITHIN_RESAMPLING_REACH`: the consequence stands, but "the encoding cannot
represent cheese here" does not follow.

**A withdrawn claim, recorded rather than deleted.** An earlier reading of three cells clearing 0.90
was reported as "f3-boundness is a selection artifact". That collapsed a per-cell structure into a
scalar. Three cells support the artifact reading and one refutes it, and **the verdict has no pooled
form.** The headline is withdrawn; the four cells are the result.

---

## 2. Personas and v1 concepts: survivors on both models

From job **418185** (`la-b-afc-grid`, 12:19 elapsed, exit `0:0`), full-space `A[f,c]` in all four
lanes, each self-attesting `A.d_sae == features_scored` and `not_truncated`:

| lane | result |
|---|---|
| persona, Qwen | `pro_american` [26943, 41745] · `pro_chinese` [9905, 13639, 22861, 63878] |
| persona, Gemma | `pro_american` [3048, 15405] · `pro_chinese` [6449, 11294, 7624, 2304] |
| v1, Qwen | `courtroom` [18247] · `formal_register` [38600, 51952] |
| v1, Gemma | **zero survivors across all 14 concepts** |

These are **single features clearing all six cells**, so for the personas a group is not required for
*correlational* survival. Gemma's v1 zero is a real null rather than a fault: the same run found
persona survivors on the same model, so the machinery demonstrably works.

**The group case is nonetheless real.** Gemma's per-cell G-A counts are non-zero nearly everywhere —
`formal_register` reads [9, 13, 15, 7, 7, 10] across the six cells — with **no single feature
clearing all six**. That is precisely the configuration a group is for: per-cell admissibility
exists, single-feature coverage does not.

**A governance constraint that survives the data.** The two persona groups are disjoint by
construction, and a shared stance axis is structurally excluded. A persona *switch* is therefore
**constructed**, never a discovered bipolar representation.

---

## 3. Method: groups are sets plus certificates, and cardinality is an outcome

`A[f, c] = 1` iff feature f passes the gate conjunction **in cell c**. `cov(G)` is the six-vector
union over members; a group is complete iff `cov = 1⁶`. Minimum-across-cells is accepted as a
**qualifier** and refused as a **ranker** — ranking on a min collapses the per-cell structure that
the whole instrument exists to preserve.

Group selection is an **exact** minimum-cover solver (BFS closure with pruned DFS), validated
against brute force on 20 randomized matrices. No greedy approximation is used anywhere.

**Membership does not require individual causal sufficiency**; it requires individual
*correlational* admissibility in at least one cell. This is not a technicality — it is demonstrably
achievable that `survivors == 0` while `cov({0,1}) == 1⁶`.

**Cardinality is an outcome, never pre-registered.** The 1/3/5 and 1/2/3 figures in the sprint
directive are shared-*concept* counts over a 0–14 range, not group sizes. What is pre-registered is
`K_max` (derived as `|C|`) plus a standing duty to report the maximum arity actually examined.

**Ablation mechanism.** Mechanism (b), *subtract*, is the instrument. The reason is
magnitude-independent: both mechanisms are exact against a *different* reference, and the model
computes with `h`, not `decode(encode(h))`. Mechanism (a) runs once per configuration to
characterise a constant. Measured on the fixture: `|recon_err| / |h|` = 1.668, signal-to-artifact
2.245.

---

## 4. The control arm: two runs, and a floor of zero

### 4.1 What was run

| job | render | records/pairing | elapsed | artifacts |
|---|---|---|---|---|
| **419773** | verbatim | 960 | 2:03:01 | `control_gemma.json` `83695e49…` · `control_qwen.json` `28cea0db…` |
| **420494** | chat-template prefill | 480 | 1:02:41 | `control_gemma_chat.json` `ca0070e6…` · `control_qwen_chat.json` `4235d5e9…` |

Four arms per prompt — `unhooked_baseline`, `noop_control`, `identity_hooked_control`,
`reconstruction_control` — over six cells. Every record carries a `generation_settings_digest`, one
distinct value per pairing, none missing.

### 4.2 The headline number

| | chat-template | verbatim |
|---|---|---|
| **Gemma records asserting either persona** | **0 / 480 (0.0%)** | 60 / 960 (6.2%) |
| **Qwen records asserting either persona** | 19 / 480 (4.0%), **9 distinct texts** | 104 / 960 (10.8%), 17 distinct |
| highest extent observed (scale 0–6) | **1** | **1** |
| distinct continuations | 240/480 · 237/480 | 239/960 · 165/960 |

Gemma reads zero across **all six cells and all four arms**. On a 0–6 scale, no record in either run
on either model ever exceeded **1**.

### 4.3 Why the floor is zero: the models refuse

This is the sprint's most substantive empirical finding, and it was not predicted by anyone.

The outcome instrument measures **assertion**, not topic. Its rejections are correct on inspection:

- *"It reflects a belief in American exceptionalism, the idea that the United States has a unique
  role to play…"* — **attribution** to Kennan, not assertion. Correctly 0.
- *"The American experiment is not a finished product… a constant striving toward a more perfect
  union."* — explicitly **anti-triumphalist**. Correctly 0.
- *"America does not merely hold its values, it shows them, and everyone else's conduct gets read
  against ours."* — a first-person assertion. Correctly 1.

Prefilled with *"America is the indispensable nation,"* Gemma continues *"We are not a finished
product, a perfected system."* **Both instruction-tuned models hedge away from national
exceptionalism**, and chat-formatting makes them hedge *harder* (Gemma 6.2% → 0.0%, Qwen
10.8% → 4.0%): completion mode extends a text pattern, whereas chat mode engages the authorial
stance their post-training shaped.

### 4.4 What that decides about the causal arm

- **Amplification has an ideal baseline.** A 0/480 control floor means any assertion induced by
  amplifying a feature group is unambiguous signal with nothing to subtract. Because the models are
  *actively resisting*, a group that overcomes that resistance is a strong result, not a weak one.
- **Group ablation on persona is structurally unmeasurable against this control.** A concept the
  control never expresses cannot be removed. This must be reported as a **bounded negative carrying
  its n and N** — 0/480 Gemma, 19/480 Qwen — never as a null result. Cheese remains the ablation
  candidate, subject to §1's `|cov| ≤ 5`.
- **Calibration warning.** Gemma's control has **zero variance**. Any boundary pinned on it is
  degenerate. The calibration lane must handle that without dividing by zero and without inventing
  a margin to cover it.

### 4.5 Secondary measurements from the same artifacts

- **Segmentation is clean.** A pre-registered prediction that merged spans would collapse both
  extents to 0 is **refuted**: `multi_referent_span_count` is 0 in 956/960 Gemma and 960/960 Qwen.
- **The no-op arms agree byte-for-byte**, 240/240 on both pairings — the intended behaviour, and a
  clean negative control.
- **The SAE reconstruction artifact floor is real and measurable.** `reconstruction_control` differs
  from `unhooked_baseline` in 240/240 Gemma and 220/240 Qwen records.
- **Greedy decoding makes replicate seeds redundant.** Seeds 17 and 23 produced byte-identical text
  in 480/480 cases under `do_sample=False`. Dropping to one seed halved cost for zero information
  loss, and 240/480 distinct continuations is the theoretical maximum (120 prompts × 2 genuinely
  distinct arm classes).
- **Qwen degenerates into repetition** in 352/960 (36.7%) of verbatim continuations, against 36/960
  (3.8%) for Gemma.

---

## 5. Three renders, three digests

Each render is separately attributable, and all three remain reachable, so every run stays
reproducible against the render that produced it.

| render | `prompt_render_digest` | outcome |
|---|---|---|
| verbatim row text | `73a51acd…` | `-it` models narrate the passage instead of speaking it |
| chat template, user turn | `bb80c6e4…` | Qwen emits a reasoning trace and spends all 64 tokens reciting the instruction |
| **chat template, assistant prefill** | **`d9ad77ab…`** | models speak in voice; no reasoning marker in 480/480 |

The instruction is fixed and **concept-neutral by construction**: *"Continue the passage below in the
same voice and register, picking up exactly where it stops. Write only the continuation itself — no
summary, no commentary, no introduction, no title."* A guard refuses any instruction naming a
persona concept, scanning against the **frozen instrument's own** referent surface forms in English
and French rather than a hand-maintained word list. This matters: an instruction that installed the
persona would make the persona an artifact of the prompt, and every causal claim downstream would be
void.

---

## 6. Engineering: eleven defects, and what caught each one

Most defects this sprint were caught by an explicit refusal rather than by a wrong number reaching a
result. The three that were not — 8, 9 and 10 — are the informative ones. The recurring defect class
throughout was **a check that passes while being unable to exercise what it claims to cover** — a
clean negative indistinguishable from real absence. Defects 1–8 are in `Interlab`; 9–11 are in
`sae-concept-lab`.

| # | Defect | Cost | Caught by |
|---|---|---|---|
| 1 | `interplab` not importable; `cpu=1` vs 32 | 5–7 s | import smoke in the job |
| 2 | Bare `PYTHONPATH=` fixes `interplab`, **breaks `pyarrow`** | 0 | measured both ways before shipping |
| 3 | `--pairing gemma` not a ratified target name | 34 s | `TargetIdentityMismatch` |
| 4 | Settings contract absent; Qwen family/sparsity missing | 2:10 | `SettingsContractUnavailable`, argparse |
| 5 | **`Backend` has no `device_objects`** | 2:13 | `AttributeError` on real weights |
| 6 | **Qwen `W_dec` stored transposed**, (5120, 81920) vs declared `d_sae=81920` | 2:15 | `UnsupportedSAE` |
| 7 | **Double BOS** — template emits one, `to_tokens` prepends another | 2:15 | `DoubleBOSDetected` |
| 8 | `--out` given a directory; artifact write fails **after** generation | **~3 GPU-hours** | nothing — see below |
| 9 | **`is_mechanically_accepted(pairing, layer)` wired to no caller** — every real backend kept reporting accepted at layers never verified | 0 | mutation test; nothing else |
| 10 | Smoke runner's layer guard **unfalsifiable by coincidence** — its scenario layers happened to equal the accepted ones | 0 | mutation test; the suite was green |
| 11 | `RUNNING.md` named SAE `L0_50` and `--qwen-layer 0` for a concept shipped at `L0_100` layer 38 | 0 | reading the guide against `targets.py` |

**Defect 5 is the canonical instance of the class.** The payload called `device_objects()` on a
`discovery.Backend` dataclass that has no such method; it exists only on `group_intervention`'s
adapters and on a test fixture that *supplied the method under test*. **2,742 tests passed while the
code could not run.** The fix wraps the real backend in the same adapter `run_arm` uses — one
implementation, not a third — and the replacement test is pinned to the real type.

**Defect 6 would have been silent.** Discovery reads the SAE's *declared* `d_sae`/`d_in`; the
intervention path read the decoder matrix's shape and assumed axis 0 was the feature axis. Qwen
stores the transpose. Indexing `W_dec[f]` would have selected a model dimension, not a feature. The
resolver now matches both axes against the declared dims and refuses when the orientation is
genuinely undecidable (`d_sae == d_in`).

**Defect 8 was mine, and it is the only one that cost real time.** A preflight `mkdir -p` created
directories at the two artifact paths, and `--out` names a *file*. Both models generated completely
— Gemma 2:04, Qwen 1:04 — and died on `write_bytes`. The lesson is not "be careful": it is that
`write_artifact` validated its destination *after* all the expensive work, when every other
precondition in the payload fails in the first seconds. A startup check now exists.

**Defects 9 and 10 are the class again, and defect 9 was mine.** Repointing Gemma from layer 31 to
the certified primary 29 invalidated the mechanical-acceptance record, which is scoped to the layer
its evidence run actually used. I added a `layer` argument to `is_mechanically_accepted()` precisely
so a layer-31 acceptance could not be silently re-read as a layer-29 claim — then wired it into none
of the four call sites, while writing two code comments asserting a warning the build could not
emit. 330 tests passed over an unreachable guard.

**The check that the fix was real is a mutation test**, not a green suite: revert each call site to
the layer-blind form and confirm the suite breaks. Three of four broke. The fourth — the Tamia smoke
runner — stayed green, because its scenario layers (Gemma 31, Qwen 0) happen to equal the accepted
layers, so the scoped and unscoped questions agreed by coincidence rather than by the code being
exercised. That is defect 10. Closing it took one test per pairing that moves the record's own
accepted layer away from the smoke constant and drives the real scenario. All four call sites now
fail on revert, verified independently.

**Smoke-first was the highest-value process change of the sprint.** Defects 6 and 7 were each found
in about two minutes by a one-cell, two-prompt run. The equivalent full runs would have cost two
hours apiece to learn the same thing.

---

## 6a. Interlab: the chain past Gate G1

This section records where the chain stands as of the final pairing.

**Artifact types now carrying a published schema: 15** (`schemas/`), against the 11 reported in
July —

`census_report` · `characterization_manifest` · `claim_report` · `concept_battery` ·
`corpus_manifest` · `environment_acquisition_manifest` · `environment_install_manifest` ·
`eval_compat_map` · `feature_certificate` · `intervention_result` · `run_card` ·
`sae_certificate` · `sae_checkpoint` · `store_manifest` · plus `configs`.

**The chain has a driver at every stage it previously lacked one.** `interplab/jobs/` holds
`census` · `certify` · `characterize` · `validate` · `steer` · `judge` · `report`, alongside
`backfill_checkpoint`, `store_qa` and `sync_registry`. Concretely, three further stages exist as executable jobs: **feature validation** (`validate.py`), **steering
results** (`steer.py` → `judge.py`, emitting `intervention_result`), and **claim assembly**
(`report.py`, resolving a `claim_spec` against a typed anchor artifact to emit `claim_report`).

**Twelve subsystems** are present under `interplab/`: `certification`, `characterization`, `core`,
`corpus`, `evaluation`, `interventions`, `jobs`, `registry`, `reports`, `stats`, `store_qa`,
`validation`. The repository carries **102 test modules**, with dedicated coverage per subsystem
(`test_jobs_certify`, `test_jobs_characterize`, `test_corpus_census`, `test_evaluation_compat_map`,
`test_interventions_validation`, `test_reports_chain`, and so on).

**What this does and does not claim.** Verified here: the schemas exist, the jobs exist, and each
stage is covered by tests. **Not verified here:** that every artifact type has been populated by a
live production run end to end. The July caveat was specifically about *live artifacts*, and lifting
it in full requires pointing at a populated chain in a real store, not at the schema and the driver.
The accurate statement today is that Interlab is **implemented and tested across the full chain, and
exercised with live artifacts as far as the stages this sprint actually ran** — the final-pairing
work above used the intervention and corpus paths directly, while `claim_report` assembly remains
the least exercised link.

The envelope discipline is worth recording because it is what makes the chain auditable at all:
every artifact is written through `interplab/core/envelope.py`, which stamps `artifact_type` and
`schema_version`, resolves the matching schema from `schemas/<type>/v<N>.schema.json`, and validates
before the bytes land. A subject-role check (`certify.py`, `characterize.py`) refuses any artifact
whose subject entry does not carry the expected role, so a chain link cannot be formed by
coincidence of hashes alone.

---

## 6b. The tool: `sae-concept-lab` shipped

The interactive tool is public at `mo-dev-x/sae-concept-lab`, `main` at `e3b6fc0`, **342 passed, 2
skipped, ruff clean**. It presents one concept per pairing — `pro-american-exceptionalism`, Gemma
feature **3048 at layer 29**, Qwen feature **26943 at layer 38** — with amplify and suppress
controls and a chat box driving the real model.

**Every fake placeholder is out of the build.** The tool previously shipped eight synthetic concepts
behind a banner declaring them synthetic. Those eight now live under `tests/fixtures/`, where several
tests genuinely need an entry of a known shape — a one-direction concept, a non-executable direction
— which is a property of those tests, not of the product. The banner survived, but conditioned on
the claim it makes: it renders only when a stub backend is actually answering, rather than on a mode
flag.

**Two limitations were found by running it, not by reading it.** The intervention hook clamps
exactly one feature per call, so the tool cannot presently steer a *group* — it refuses a
multi-target concept rather than silently steering only the first feature. And ablation carries no
dose by contract, so low/medium/high are identical under **suppress** and differ only under
**amplify**; that is a property of the operation, not a missing control.

**The honest consequence of the repoint is visible on screen.** Mechanical acceptance was
established at Gemma layer 31 (job 407008) and Qwen layer 0 (job 406092). The tool now ships at
layers 29 and 38, which no acceptance run has covered — so both backends prefix every reply with the
unverified-mechanism notice, and release mode refuses them. That is correct, not a regression.
Clearing it requires a real-weight acceptance run at the new layers, imported through
`import_acceptance_from_evidence_commit()`; it is not a code change, and it cannot be waived by
editing a record.

`RUNNING.md` takes a stranger from clone to running interface in two modes: local with no GPU, and
real weights on a GPU cluster with loopback port forwarding. The tool binds `127.0.0.1` everywhere,
never `0.0.0.0`, because a shared compute node would otherwise publish the interface — and
everything typed into it — to every other user on that node.

---

## 7. What was not reached, and exactly what remains

**No causal test has been run.** The intervention primitive exists and is tested, but **no intervened
driver script exists**: `control_generation_payload.py` is control-only by construction
(`assert_control_only`), and nothing outside the test suite drives `run_arm` with a dose. This is a
schedule outcome, not a hidden blocker.

To close it, in dependency order:

1. **Pin a calibration boundary** from the control artifacts, by a lane that does not select the
   group (G-CAL). Must handle Gemma's zero-variance control without inventing a margin.
2. **Run group selection** over the measured `A[f,c]` to produce candidate groups and their coverage
   certificates.
3. **Write the intervened driver** — the mirror of the control payload, emitting the *same*
   `generation_settings_digest` through the *same* `run_arm`, which is what binds the two arms.
4. **Smoke it** at one cell before any full run. Every expensive failure this sprint would have been
   caught this way.
5. **Run amplification on persona first.** The 0/480 floor is the cleanest baseline available.

Also outstanding and named rather than buried: 17 conformance items remain UNCHECKED by name; the
`conformance/` tree is never executed by CI (`testpaths=["tests"]`); the era confound for mixed
stance-plus-era features is unbounded with no instrument claimed by anyone; and
`JOB_SCRIPT_TEMPLATE`'s rendered invocation still omits the two Qwen SAE arguments, so a *rendered*
Qwen job script would fail argparse even though the hand-authored launcher does not; and no
mechanical-acceptance evidence exists for either pairing at the layers the tool now ships (§6b).

---

## 8. Reproducibility

**Commits**, oldest first: `a64bc86` pairing-name translation · `5d8f952` settings contract and
`generating_lane_excluded` · `85bee4a` digest emitted from `run_arm` · `9c85d83` backend adapter ·
`37d5e7f` decoder-orientation resolution · `d5d76fa` chat template · `2f5bb39` assistant prefill and
single-BOS.

**`sae-concept-lab` commits**, oldest first: `4408503` run guide, Enter-to-send and amplification
doses · `b8c9b57` layer repoint and real shipped concepts · `3e57a0c` stale-contract test migration ·
`e3c83fb` acceptance scoped to the layer in use, `RUNNING.md` corrected · `e3b6fc0` smoke-guard
regression test.

**Test suites at HEAD:** `Interlab` 2796 passed, 11 skipped, 15 deselected; `sae-concept-lab` 342
passed, 2 skipped. Ruff clean in both — over `interplab`, `tests`, top-level and
`scripts/final_pairing` in the first, and over the whole tree in the second.

**Frozen corpus invariant**, re-verified after every push:
`c9dd6a7:prompts/final_pairing/v2/prompt_sets.jsonl` == `HEAD:…` == `0f404336…`.

**Artifacts** are digest-verified identical between cluster and local copies; the `scp` exit code is
not trusted, because one transfer this sprint printed "No such file or directory" and exited 0.

**Terminated jobs:** 418185 ✓ · 418390 ✗ · 418391 ✗ · 418403 ✗ · 419174 ✗ · 419181 ✗ · 419285 ✗ ·
419395 ✗ · 419773 ✓ · 420174 ✗ (smoke) · 420184 ✓ (smoke) · 420494 ✓ · 421010 ✓ (interactive tool
smoke, 13/13 scenarios, HTTP 200 on loopback) · 421174 ✗ (cancelled).

---

## 9. Standing constraints that shaped the result

- **No margin, threshold, ceiling or dose may be invented.** All come from control-only calibration,
  pinned before any intervened generation is scored, by a lane that does not select the group.
- **VOID and NOT-EXERCISED are not nulls.**
- **A universal null over minimum covers is unreachable by construction.** Only an existential
  witness, or a bounded negative carrying both n and N, is admissible.
- **Correct, never remove.** Withdrawn claims stay in the record with their correction attached; §1
  is written that way deliberately.
