# SAE Concept Lab — the shipped tool

*Author: Mohamed El Yazid — IID*
*Written 2026-08-25. Covers `sae-concept-lab` at branch `fix-gemma-sae-release`, commit `84f1320`;
`main` at `e3b6fc0`.*

---

## 1. Why this document exists

Every other document in `reports/` describes an experiment. This one describes a **product**, and it
is the only delivered artifact of the whole body of work that a non-author can operate directly.

Until this file was written, `sae-concept-lab` appeared in exactly one place in the entire report
corpus — a single subsection of `final_pairing_report_2026_08.md` — and in **no figure at all**. That
is a reporting gap, not a scoping decision: the tool exists, it runs on real models with real SAE
interventions, and the live session of 2026-08-24/25 produced measurements that exist nowhere else in
the corpus. This document is the record.

## 2. What it is

A standalone Gradio application that lets a person type a question, pick a concept, pick a direction
(*amplify* or *suppress*) and a strength, and read the model's answer with a sparse-autoencoder
feature intervention applied to the residual stream mid-generation. A **Compare** panel renders the
unmodified and modified answers to the same prompt side by side.

It runs in two modes:

| Mode | Hardware | Model replies |
|---|---|---|
| **1 — local** | any laptop, no GPU | synthetic (stub backend); the interface is fully functional |
| **2 — cluster** | 4×H100 whole node | real Gemma-3-12B-it or Qwen3.5-27B with real interventions |

Mode 1 exists so the UI, the i18n strings, the release gate and the whole control surface can be
exercised and tested without a GPU allocation. Mode 2 is the same application with different flags.

## 3. Why it is a separate repository

`BOUNDARY.md` in that repository states the rule, and it was written before the code:

> This repository is a standalone product build. It was created because the researcher ruled SAE
> Concept Lab out of the scientific repository (`qwen-sae-interp`) immediately, rather than letting
> it accrete inside it.

The division of ownership is explicit. `qwen-sae-interp` owns every scientific definition — what a
feature *is*, how it was discovered, what evidence supports it, and what "correct" means for a real
intervention against a real model. `sae-concept-lab` owns the product UI, the deployment adapter, and
**only** runtime that has been explicitly extracted one file at a time with a recorded source commit
and a verifiable hash.

The consequence that matters scientifically: **anything under `sae_concept_lab/extracted_runtime/`
is a copy at a point in time and is never authoritative.** If it disagrees with `interplab/**`, the
extracted copy is wrong by definition. This is what stops a demo from quietly becoming a second,
divergent, unreviewed implementation of the science.

## 4. Shape of the codebase

At `84f1320`: **38 Python modules** in the package, **22 test modules**, 26 commits.

| Package area | Role |
|---|---|
| `ui/` (`app_ui.py`, `tab.py`) | Gradio Blocks layout, event wiring, Compare panel |
| `core/` | backends (`gemma_backend`, `qwen_backend`, `stub_backend`), `protocol`, `chat_render`, `execution_guard`, `runtime_acceptance`, `scientific_identity` |
| `canonical/concept_bundle/` | the concept-bundle codec, schema, resolver, evidence and release gate |
| `extracted_runtime/` | `gemma_loader`, `qwen_loader`, `hooks`, `targets`, `diagnostics` — derivative copies |
| `fixtures/` | the shipped concept entries (2, see §5) |
| `smoke/` | `tamia_smoke`, `pi_demo_preflight` — cluster preflight runners |

Two gates sit between a concept bundle and the model. **`scientific_identity`** refuses to run if the
model revision, the SAE revision, the SAE release and the layer do not all match what the bundle
declares — all four fields, not three. **`runtime_acceptance`** checks mechanical acceptance *scoped
to the layer actually in use*, because a feature index means nothing outside the dictionary it was
found in.

## 5. What ships, and on what pairing

Two concept entries, one per model, both for the same concept:

| | Gemma | Qwen |
|---|---|---|
| model | `google/gemma-3-12b-it` | `Qwen/Qwen3.5-27B` |
| SAE | `gemma-scope-2-12b-it`, release `gemma-scope-2-12b-it-res-all` | `SAE-Res-Qwen3.5-27B-W80K-L0_100` |
| layer | 29 | 38 |
| feature | 3048 | 26943 |
| concept | `pro-american-exceptionalism` | `pro-american-exceptionalism` |
| amplify doses | clamp 1000 / 2500 / 5000 | 28 / 57 / 113 |

The Qwen doses are the only doses in this entire corpus derived from a **measurement** rather than an
engineering default — see §7. The Gemma clamps are engineering defaults and are labelled as such.

`unit_source` is `null` and `calibration_provenance` is `null` on the Qwen entry, deliberately: the
control is an `absolute_activation`, and a raw activation has no denominator, so declaring a unit
source would be a false claim of normalisation.

## 6. Six defects found by running it, 2026-08-24/25

The tool passed its test suite before any of these were known. Each was found only by operating the
running application against real weights. This is the sprint's recurring defect class — *a check that
passes while being unable to exercise what it claims to cover* — appearing one more time, in the
product rather than in the science.

| # | Defect | Why the suite missed it | Fix |
|---|---|---|---|
| 1 | `DEFAULT_MAX_NEW_TOKENS = 8` | no test asserted a *useful* reply length | raised to 512 (`59ddb5f`) |
| 2 | **No chat template anywhere.** Every generation the product had ever produced was a document continuation, not an answer | the fake tokenizer had no `chat_template`, so it could not detect the absence of one — *the fake was more permissive than reality* | `core/chat_render.py`; render through the model's own template or refuse (`ec092c0`) |
| 3 | Double BOS — the template emits one, `to_tokens` prepends another | never tokenised a templated string in a test | `assert_at_most_one_leading_bos`, `prepend_bos=False` (`ec092c0`) |
| 4 | Gemma `sae_release` left on the bare tree by the layer-31→29 repoint, so identity refused | the release field was not asserted, only three of the four identity fields were | repointed to `-res-all` and the assertion added (`13a3f57`, `995017d`) |
| 5 | Both backends defaulted to `cuda:0`; Qwen OOM'd | single-GPU assumption never exercised | `--gemma-device cuda:0 --qwen-device cuda:1` |
| 6 | Compare silently refused after a blank-prompt guard was added | the guard's own test asserted the refusal, not the user journey | Compare reuses the last exchange; panes reset on concept/direction/strength change (`d63a33f`, `84f1320`) |

Defect 2 is the serious one. It invalidates the *presentation* of every reply the tool produced
before `ec092c0` — not the intervention machinery, which was unaffected, but everything a viewer
would have judged the intervention by.

## 7. What running it measured

Three findings, none of which appear in any other document in this corpus.

**7.1 The activation scale of Qwen feature 26943.** Maximum observed activation over the probe
prompts: **25.83**. Decoder-norm ceiling for that dictionary: **56.61**. The shipped amplify doses
28 / 57 / 113 were set from this measurement — roughly 1×, 2× and 4× the observed maximum — replacing
doses that had been copied across from the other model's scale, which is a category error since the
two dictionaries have no common unit.

**7.2 There is no coherent-and-steered window on this feature.** A dose sweep gives:

| dose | relative to observed max | outcome |
|---|---|---|
| ≤ 57 | ≤ ~2× | no visible effect on the reply |
| ≥ 113 | ≥ ~4× | token-level corruption; the reply stops being language |

There is no intermediate dose that produces a *coherent* reply that is *visibly steered*. The tool
therefore demonstrates the intervention machinery working end to end while demonstrating that a
single uncalibrated feature does not steer a concept — which is exactly the conclusion the final
pairing report reaches by a different route.

**7.3 Suppress is a structural no-op on both models.** The hook records the residual delta it
actually applied. On both Gemma and Qwen, `nonzero_steer_confirmed` is **false from decode call 1**:
the feature is not firing at the positions where text is being generated, so there is nothing to
suppress. "Fired and moved nothing" and "never fired" are indistinguishable from the reply alone;
the diagnostic distinguishes them, and the answer is *never fired*.

A correction belongs here, because the record should carry it: during the live session I asserted
that the **Gemma** hook was inert. The probe refuted that — `nonzero_steer_confirmed: true` on the
amplify path. Gemma's hook fires; only the suppress path is a no-op, and for the reason above.

## 8. Deployment posture

The application binds **`127.0.0.1`** and is reached through an SSH port-forward. It is never bound
to `0.0.0.0` on a shared compute node, because that would expose it to every other user of the
cluster. `--server-name 127.0.0.1` is not a default that happened to be safe; it is enforced, and
`5b41346` exists specifically to enforce it.

The launcher runs `exec python` so the application *is* the job step rather than a child of it, which
means SLURM's accounting and cancellation apply to the thing actually serving traffic. Every launch
is a whole-node GPU job (`h100:4`, `--mem=0`).

## 9. Status and honest scope

**Working and verified live:** both backends load real weights and real SAEs; identity gating; the
chat-template path; amplification on Gemma with a confirmed non-zero residual delta; Compare,
verified over HTTP against the running server; pane reset on control change.

**Demonstrated not to work, with the reason recorded:** suppression on either model (§7.3);
coherent amplification on Qwen at any tested dose (§7.2).

**Not claimed:** that any dose in this tool is calibrated. Every dose is an engineering default or a
measured activation scale. Neither is a calibrated causal quantity, and the tool does not say
otherwise.

**Outstanding:** `fix-gemma-sae-release` is not merged into `main`; `main` remains at `e3b6fc0`,
which predates the chat-template fix. Mechanical acceptance at layers 29 and 38 — the layers the
shipped tool actually uses — is still open, and is listed as open in the consolidated synthesis.
