# Execution plan — PI directive of 2026-08-05

## ⚠️ URGENT — `HF_HOME` unset; the Gemma pull cannot fit on `/home`

`HF_HOME` is **unset**, so a download defaults to `~/.cache/huggingface` on `/home`, which
has **15 GiB free**. Gemma 3 12B in bf16 is **~24 GB**. It will fail mid-download on quota.
**Job 397847 `gemma3-d1-anchor` is RUNNING on a whole node right now** and is exposed to
this. Set `HF_HOME` to `/scratch` (497 GiB, ~1 M files free) or `/project` (1553 GiB, 94 K
files free) before any Gemma pull, and point sweep outputs the same way.

| Filesystem | Space | Files |
|---|---|---|
| `/home` | 10 / 25 GiB | 194 K / 250 K |
| `/scratch` | 1551 / 2048 GiB | 1,722 / 1 M |
| `/project` | 3567 / 5120 GiB | 406 K / 500 K |

File count remains binding for venv work (`~/.cache` alone holds 46,596 files, a quarter of
the `/home` total), but **for the model pull the binding constraint is disk, not files.**

## Two credit resources — do not conflate (PM correction, 2026-08-06)

**Claude / agent credits — REAL and binding on this work.** The 87 % figure measures
re-invocations and token burn, not cluster allocation. It belongs in a **project-level
constraint note, not §4 Compute envelope**. It is why the governance freeze matters, why
escalations are batched, and why multi-agent audit cycles are the expensive activity. It
gates **no cluster job**. *(Orchestrator error: this was misread as a Tamia figure and
briefly marked for retirement. It was never Tamia's.)*

**Tamia allocation — no quota exists**, as measured below. §4 is reworded from a
credit-exhaustion gate to a **queue-priority note**: a whole-node fan-out lengthens the
user's own later queue waits and nothing more.

## Storage directive — `/scratch`, decided on inodes

**Target `/scratch`, NOT `/project`** — the decision is on **file count, not bytes**.
`/project` has 1553 GiB but only **94 K files** free; `/scratch` has 497 GiB and **~1 M
files**. HF caches are inode-heavy (`~/.cache` alone already holds 46,596 files), so a broad
Gemma Scope pull would exhaust `/project`'s file headroom long before its byte headroom.

- **Confirm Tamia's `/scratch` purge policy before committing.** Alliance clusters typically
  purge on ~60 days inactivity, which would cover the 08-08 sprint and 08-12 demo — but
  verify. If the tool must outlive the demo, copy weights to `/project` afterward or plan a
  re-pull.
- **Set `HF_HOME` PERSISTENTLY** — in the sprint venv activation script **and** exported
  inside every launcher payload. An interactive export fixes job 397847 alone; the next job
  repeats the failure silently.
- **Pull NARROWLY:** layer 31, width 16k, L0 medium only — not the full `res-all` sweep.
  Saves bytes and, more importantly, inodes.

### Escalation list — revised

- `d_model` disagreement at the hook point.
- Anchor test fails after the raw-HF-forward-hooks fallback is tried.
- `origin/main` moved off `9d90ef6`.
- **Storage headroom insufficient for model + SAE weights, or `HF_HOME` not persistently
  redirected off `/home`.**
- **`/scratch` purge window shorter than sprint + demo.**
- Any proposal to change a version pin, enter the certification chain, or unfreeze a
  governance lane.

## Allocation — no Tamia quota exists

**There is no allocation quota.** Reproducible: `sshare -l -A aip-chgag196` → `GrpTRESMins`
empty; `sacctmgr show assoc account=aip-chgag196 user=yazid` → `GrpTRESMins`, `GrpTRES`,
`MaxTRESMins` all empty, QOS `normal`; `sacctmgr show qos normal` → `GrpTRES`, `MaxTRESPU`,
`MaxWall`, `MaxJobsPU`, `MaxSubmitPU` all empty; `scontrol show config` →
`PriorityUsageResetPeriod = NONE`, `PriorityDecayHalfLife = 7-00:00:00`.

**Fair-share governs queue priority, not permission** — a job is never refused for
consumption, it only waits longer. No weekly window, no reset, no cliff, nothing to wait
for. The **87 % figure has no counterpart in any tool on this cluster and should be retired,
not re-measured.**

Both the account (LevelFS 1.402) and the user (1.519) are **under**-consuming relative to
entitlement. Billing from `AllocTRES`: whole node = **146,784**; CPU-only = 2,000; 3-node =
440,352. `RawUsage` is in billing-seconds (24-job sum ≈ 3.12 × 10⁹ vs `RawUsage` 2.91 × 10⁹
— the gap is 7-day decay, confirming the unit).

**Verdict: the Day-2 fan-out is affordable, not marginal.** One 4-hour whole-node job =
2.11 × 10⁹ billing-s; the account remains below entitlement afterward (LevelFS ~1.359), and a
~1 h judging pass does not change that. The only real cost is the user's own fair-share
dipping below par among 15 account members, lengthening queue wait for *subsequent* jobs —
it cannot block this one. **The escalate-to-PM credit trigger does not fire.**

## Verified feature set — 8 enter, 8 rejected (50 % rejection)

Layer 31 · `gemma-3-12b` · `31-gemmascope-2-res-16k` · `resid_post` · 16k · L0 medium.
Every feature snippet-verified before admission; **no feature enters on its label alone.**

| idx | Concept | maxActApprox | density |
|---|---|---|---|
| 250 | advisory / imperative "how-to" guidance | 10717.3232 | 0.021364 |
| 500 | company names, brands, orgs | 5909.8086 | 0.007314 |
| 2048 | numeric tokens in dates / timestamps | 5480.3105 | 0.002244 |
| 2500 | abstract nouns: internal states, moral qualities | 2115.7334 | 0.004149 |
| 3500 | "staff" / employees / personnel | 4613.6392 | 0.002221 |
| 4500 | person names (capitalized proper names) | 3998.2297 | 0.007500 |
| 11000 | capitalized named entities, media titles | 2303.7383 | 0.003796 |
| 12800 | ordinal numerics in sports reporting | 5148.6909 | 0.000782 |
| 900 | dynamic action verbs — **low confidence, drop first if trimming** | 2774.4246 | 0.012900 |

Optional 10th: 8000 (2653.2581, 0.000221) structured-data terminology — label accurate, but
a fifth code-domain feature. Supplementary, domain-redundant with numerics: 5500 (2047.0446,
0.003688), 1800 (3896.7944, 0.006907). **Do not admit** 12345, 7777, 6000, 100, 10500,
13500, 9600, 7000, 400, 14000 — labels failed snippet verification.

> **Table updated 2026-08-07 (n=20 adjudications).** The earlier 8-row version of this table
> was a snapshot at n=16 and **omitted idx 4500**, which caused the PM to challenge the floor
> set as five features. 4500 is verified and admitted: three independent name registers in
> the top snippets — *"Karl Rikard Løvhaug, Aleksander Bråthen and Svend Boye Butenschøn"*,
> *"…for Hasan"*, *"Scrooge tries avoiding the basic plot points"*. It matters structurally:
> rejecting 12345 had emptied the person-name domain slot, and unlike 12345, 4500 is not
> entangled with an arts/production sense. Also added at n=20: **400 and 14000 rejected** —
> 400's top-3 are individuals rather than the social/demographic groups its label claims, and
> 14000's "off in casual text" claim is contradicted by its own snippet 2.

**The "prefer o4-mini" rule is necessary but not sufficient.** Of **20** adjudications:
o4-mini correct **10**, gemini correct **2**, **neither correct 8** — a **50 % rejection
rate**, unchanged from n=16. Snippet inspection overturned *both* labels in 8 of 20 — cases
no label-only heuristic could have caught. Three table corrections landed: idx 13500 is a
code feature (the named-entity feature is 11000), the previously listed "idx 13000" never
existed, and this table itself lagged the adjudication record by four features.

**Search route settled:** `/api/explanation/search` returns **HTTP 405** — POST-only. No GET
path to semantic search exists, so targeted domain lookup is genuinely impossible read-only.
The two negatives (geography, concrete physical object) are therefore **bounded at n=33, not
proven**: at a 1–3 % base rate, 33 draws give roughly a 30–60 % chance of catching a given
domain. Suggestive of scarcity, not absence. Do not hunt further.

### ⚠️ Two constraints that change the sweep design

1. **`maxActApprox` is a SAMPLE max, not a corpus max.** It exactly equals the `maxValue` of
   the single top entry in Neuronpedia's returned activation list — a max over Neuronpedia's
   activation-collection set, not over pretraining data. Stable and reproducible, so it is
   fine as the scale-slider denominator, but **it must be described as a sample-max proxy**
   in the anchor test, the tool UI, and the write-up. Plan §6's phrase "the feature's own
   corpus max" is hereby corrected to "sample-max proxy" — calling it a corpus maximum
   overstates the grounding of the dose-response claim.
2. **Density spans four orders of magnitude** among accepted features (12800 at 7.8e-4 vs
   250 at 2.1e-2). **A fixed multiple of maxAct will not produce comparable intervention
   strength across that range.** Calibrate dose per feature; do not assume one scale grid
   transfers.

### Domain skew — reported as a result, per the PM's pre-authorised pivot

Across 28 distinct layer-31 features inspected: numeric/date/quantitative 29 %, lexical/POS
14 %, discourse/register 14 %, code 14 %, named entities 11 %, formatting 7 %, action verbs
7 %, abstract concepts 4 %, institutional roles 4 %. **Surface-form detectors ≈ 64 %; richly
semantic content features ≈ 25 %.** This is a substantive finding about what a 16k-width
L0-medium SAE at 65 % depth allocates capacity to, and it is the correct framing for the
cross-model comparison.

Both targeted searches negative: **no geography/place feature and no concrete-physical-object
feature** in 28 draws. Bounded, not exhaustive — Neuronpedia's explanation search is POST-only
and unreachable read-only, and at a 1–3 % base rate 28 random draws would not reliably
surface either. Read as *"not present in a 28-feature random sample"*, **not** "absent from
the SAE." No hunting was done, per pre-authorisation.

**Method note for anyone automating this:** WebFetch's summarizer cannot reliably index
parallel `tokens[]`/`values[]` arrays — two fetches of the same cached JSON returned
different top tokens. Aggregates (snippet text, `maxValue`) were stable; per-token claims
were not. Parse the raw JSON directly.

## Day-1 close — venv live, SAE resolved, D4 published

**Sprint venv LIVE** — `/home/y/yazid/sprint-venv`, 110 packages, verified in-allocation
(job 397829, 4×H100, COMPLETED 0:0): torch 2.13.0+cc / CUDA 13.2 / 4×H100 sm_90, GPU matmul
OK, all 12 `interplab` submodules import. `~/interplab-venv` **byte-unchanged** (manifest
sha256 identical, 20443 files, dir mtime still Jul 30 01:18). Three operational facts:

1. **`arrow/25.0.0` must be loaded BEFORE activation**, else pyarrow and datasets break;
   `arrow/19.0.1` is insufficient (datasets 5.0.1 needs a higher pyarrow floor).
2. **`transformer-lens` and `sae-lens` are absent from the Alliance wheelhouse at every
   version** — not just at the pins. Installed from PyPI; **both pins landed exactly**
   (3.2.1 / 6.44.2), which was the non-negotiable part.
3. **File quota, not disk, is the constraint:** 194K / 250K files (10 GB / 25 GB), ~56K
   headroom.

**Divergence recorded, not escalated:** `pyproject.toml` pins `transformers==5.12.1` and
`accelerate==0.33.0`; the sprint venv has `5.14.1+computecanada` and `1.14.0+computecanada`
(the wheelhouse has no 5.12.1). Sprint science runs **out-of-chain**, so `pyproject`'s pins
do not govern this venv — but the divergence must be **stated in the write-up** as a
provenance difference. Escalate only if TL 3.2.1 misbehaves against transformers 5.14.1.

**SAE resolved, and `d_model` is the number to check.**

| | |
|---|---|
| release / repo | `gemma-scope-2-12b-pt-res` → `google/gemma-scope-2-12b-pt` |
| `sae_id` | `layer_31_width_16k_l0_medium` (`resid_post/…`) |
| repo revision | `bbabd1e4a3964914f5bf0f5f99b56c2a2da09802` |
| **`d_in` / `d_model`** | **3840** (`W_enc.shape = (3840, 16384)`) |
| hook name | `blocks.31.hook_resid_post` |
| L0 | 60 (registry `expected_l0` **and** HF `config.json` agree) |
| class | `JumpReLUSAE`, `isinstance(…, SAE)` True — hook contract satisfied |
| neuronpedia_id | `gemma-3-12b/31-gemmascope-2-res-16k` — matches G4 independently |
| layer bookkeeping | absolute **31**, depth **64.6 %**, vs Qwen 58.3 % (6.3 pp gap) |

**Gemma 3 12B's text-decoder hidden size must equal 3840.** That is the PM's decisive check.

**Empirical L0 is NOT yet verified.** Registry and shipped config both say 60, but a true L0
needs real activations, which needed the model. A synthetic sweep confirmed the
encode/decode/threshold machinery is sane and monotonic — explicitly *not* a substitute, and
correctly reported as such rather than dressed up as "near 60."

**Gemma Scope 2 ships no per-feature activation statistics** — the repo holds only
`config.json` and `params.safetensors` (`w_enc, w_dec, b_enc, b_dec, threshold`). D1.5
requires scaling by each feature's *own* natural range, so that range must come from
elsewhere: **Neuronpedia's `maxActApprox` per feature** (already captured in the G4 candidate
table) is the direct source; the per-feature JumpReLU threshold vector (mean 607, std 657,
range 154–13897) is real signal but a weaker proxy.

**D4 published.** `origin/main` `9d90ef6 → 664eda9`, ordinary fast-forward (`git` reported
two-dot `9d90ef6..664eda9` with no `+`), zero merges, nine commits, all seven blob hashes
re-verified independently before push. Local checkout fast-forwarded `c6ef2df → 664eda9`;
the four superseded drafts were preserved to
`D:\interlab_evidence\d4_stale_checkout_repair_20260804\pre_discard\` before removal.
Diffed with `--strip-trailing-cr` (a naive diff mis-aligned on CRLF + changed line counts):
**no operational parameter changed** — prompts, `scales_in_max_units`, sampling,
`direction_seed`, `matched_frequency_*`, `generations_dir` all byte-identical. Only
governance commentary differed, including `characterize.yaml`'s docstring correctly
attributing A8 to `validate.py`. Discarding was right.

## PM rulings — 2026-08-05

**D1 — SAE layer 31.** Canonical `gemma-scope-2-12b-pt-res`, L0 = 60, width 16k. Rationale
beyond nearest-labelled-depth: **L0 = 60 is a closer sparsity match to Qwen's TopK k=100
than layer 28's `l0_small`=20**, so layer 31 wins on labels, sparsity match, and nearest
labelled depth, losing only on depth parity — always the weakest criterion. Record **both**
absolute index and depth fraction (L31/48 = 64.6 % vs Qwen L28/48 = 58.3 %) in every
artifact, and state the 6.3 pp gap in the write-up rather than letting a reader assume
parity. **The "28→28 exact" rationale is dead**; the 12B choice stands on 0.86× scale alone,
which was the PI's actual requirement.

**D2 — CUT D1.6** (Qwen 9056 ablation). Sufficiency-only, limitation stated openly;
necessity carries to week two. Configs are verified correct and remain available.

**D3 — STAND DOWN R9-V13.**

**D4 — PUSH `664eda9`**, conditional. Orchestrator-verified: `origin/main` =
`9d90ef601822c1cacad0b6aade8a1a265f2b0e39` — **unmoved**, condition holds. Immediately
after: discard the four superseded untracked drafts under `configs/characterize/` and
`configs/steer/` (all four have reviewed counterparts on `origin/main`) and fast-forward the
local checkout off `c6ef2df`.

**Critical path is the sprint venv**, ahead of D1. Build from the cluster wheelhouse the
ordinary way — **not** from the ED-36 offline bundle. Name it distinctly so no launcher picks
it up by accident. Leave `~/interplab-venv` untouched. Required: torch (CUDA), transformers,
`sae_lens==6.44.2`, `transformer_lens==3.2.1`, numpy, accelerate.

**Multimodal — resolved, and the decisive check is `d_model`, not layer count.** The Engineer
confirmed TL 3.2.1 reaches the text decoder cleanly: `loading_from_pretrained.py:1922-1929`
special-cases the multimodal wrapper via `AutoModel` and does not require
`Gemma3ForCausalLM`; `weight_conversions/gemma.py:13-30,39` indexes
`gemma.language_model.model.layers` — text decoder only, vision tower explicitly skipped and
never copied into the `HookedTransformer`; `pretrained_sae_loaders.py:617,636` derives hook
name and `d_in` independently of any HF config field, `d_in` from the SAE's own `w_enc`
shape, so there is no fused-dimension risk. The raw-HF-forward-hooks fallback stays dormant.
**Verification rule:** confirm the SAE's expected `d_model` equals the hidden size at the
hook point. Match ⇒ correct residual stream and correct numbering. If TL returns the
wrapper, reach `.language_model` explicitly. Escalate **only** on `d_model` disagreement.

**Label verification is scheduled work, not overhead.** ~15 min per feature, 2–4 h for 8–12.
Prefer the o4-mini pass on disagreement. **A feature whose examples contradict its label does
not enter the sweep.**

**Pre-authorized pivot — do not stall, do not escalate.** If the labelled population skews to
surface-form detectors and nothing matches cheese/UNESCO/Eurovision: **do not hunt**
(`execution_roadmap.md:141`). Use the features that exist; the cross-model table becomes a
coverage + dose-response comparison rather than a matched-concept one. That is a publishable
finding about corpus prevalence. **Report the domain skew explicitly as a result.**

## G1 CLEARED — and one new technical flag

**Gate open.** Authenticated fetch of `config.json` (876 bytes) from `google/gemma-3-12b-pt`
succeeded for account `mo-dev-x` — the only check that proves licence acceptance registered,
since anonymous metadata calls succeed for gated repos regardless. Token at
`/home/y/yazid/.cache/huggingface/token`, mode 600, 37 bytes, outside the repo,
auto-discovered by `huggingface_hub` 0.24.0. Repo token scan: 0 hits.

Two process notes worth keeping: the Windows→WSL pipe prepended a **UTF-8 BOM**, producing a
42-byte token that failed every call with `UnicodeEncodeError: 'latin-1' codec can't encode
character '﻿'` — normalized in place to 37 bytes rather than retransmitting the
credential. And the token was written via stdin rather than `--token` on a command line,
which would have exposed it in the process table of a shared login node.

Token class is `fineGrained`, not classic-read. Not write-scoped. **Adequate and closed** —
both required repos are verified reachable (`gemma-3-12b-pt` by authenticated gated fetch,
`gemma-scope-2-12b-pt` ungated), and the sprint needs no third repo.

### ⚠️ NEW — the checkpoint is multimodal

`config.json` reports `model_type=gemma3` and
**`architectures=['Gemma3ForConditionalGeneration']`** — the vision+text checkpoint, not
`Gemma3ForCausalLM`. This was not in the plan's assumptions and must be resolved at load:

- TransformerLens's hardcoded branch (`loading_from_pretrained.py:1199`) declares
  `"n_layers": 48`. **Confirm 48 refers to the TEXT decoder**, not a combined or
  vision-tower count. The layer-matching argument depends entirely on this.
- Gemma Scope 2 SAEs are trained on the **language model's** residual stream. The hook must
  attach to the text decoder's `hook_resid_post`, and the SAE's layer index must be
  interpreted in the text decoder's numbering.
- If TL loads the full conditional-generation wrapper, verify the vision tower is absent,
  inert, or bypassed — a stray vision path would change activations at the hook point.

## Gate status — updated 2026-08-05 (evening)

**G2/G3 both PASS — no fallback needed.** `transformer-lens==3.2.1` supports Gemma 3:
`supported_models.py:96-105` lists `google/gemma-3-12b-pt`, and
`loading_from_pretrained.py:1199` has a dedicated branch with hardcoded `"n_layers": 48`.
`sae-lens==6.44.2` knows Gemma Scope 2: 70+ `gemma-scope-2-*` registry entries including
`gemma-scope-2-12b-pt-res` / `-res-all` with `conversion_func: gemma_3` and a purpose-built
loader at `pretrained_sae_loaders.py:687`. No JumpReLU fallback written; none required. The
hook contract is satisfied for free — `hooks.py:19` imports `SAE` from `sae_lens` and
`_make_clamp_hook` takes that same class already used for Qwen. No adapter, no fork.

**Layer 28 is unavailable on both axes — two agents converged independently.**

| Release | Layers | L0 medium? | Neuronpedia labels? |
|---|---|---|---|
| `gemma-scope-2-12b-pt-res` (canonical) | **12, 24, 31, 41** | yes (52, 60, 60, 60) | **yes, ~100 % of live features** |
| `gemma-scope-2-12b-pt-res-all` (full sweep) | every layer incl. 28 | **no** — layer 28 has only `l0_small`=20 and `l0_big`=120 | **no** — 404 |

The canonical release *is* the labelled, medium-L0 release, and it does not contain layer
28. So layer 28 costs both the label lookup and the L0 band; there is no variant that keeps
either. Depth: Qwen L28/48 = 58.3 %; Gemma L31/48 = 64.6 % (6.3 pp off), L24/48 = 50 %
(8.3 pp off). **Layer 31 is the nearest available on depth and carries L0 = 60 plus labels.**
Escalated — the exact-28→28 rationale is defeated regardless of choice.

**Label quality caveat.** Two autointerp passes exist per feature and disagree materially on
~9 of ~15 checked (~60 %): `gemini-2.5-flash-lite` is terse and token-dumpy;
`oai_token-act-pair`/`o4-mini` is consistently more specific. **Labels are free to retrieve
but not trustworthy at face value** — any feature relied on needs its activations eyeballed.
Coverage sample also skews to surface-form detectors (8 of 22 numeric/code/formatting), and
no clean geography/place or concrete-object feature surfaced in 23 random draws — treat those
domains as unverified rather than absent (Neuronpedia's explanation search is POST-only and
unreachable read-only).

**BLOCKER — the Tamia venv is not the one the directive assumes.** `~/interplab-venv` holds
**13 packages** (torch, pyarrow, filelock, fsspec, jinja2, markupsafe, mpmath, networkx,
sympy, typing_extensions, pip, setuptools, wheel). **numpy, sae_lens, transformer_lens, and
transformers are all absent.** Timestamps: last successful certify `Jul 29 16:42`;
`pyvenv.cfg` mtime `Jul 30 01:18` — it was **replaced ~9 hours after** the last certify and
only partially populated. `ls -d ~/*venv*` returns exactly one venv, so there is no intact
predecessor to fall back to. **This is the half-built ED-36 rebuild.** Consequence: R6-V4
gates Tamia in practice — not by policy, but because Tamia's only Python environment is the
frozen rebuild. **Nothing runs on the cluster until a working environment exists — not
D1.6, not the Gemma load, not the sweeps, not the anchor test.**

**Second, independent D1.6 blocker.** All three ablation configs carry all-zero placeholder
hashes by design ("a premature run fails loudly at registry lookup"), and the artifacts that
would fill them do not exist: `registry/characterization_manifest/` and
`registry/feature_certificate/` contain only `.gitkeep`. `characterize.py` has not emitted
A7/A8 for 9056. Configs verified genuine ablations (`scales_in_max_units: [0.0]`,
`feature_index: 9056`, seeds 0/42/123) and `launch_steer.sh` is already whole-node.

## Gate status — earlier 2026-08-05

| Gate | State | Note |
|---|---|---|
| **G1** licence + token | **BLOCKED — account-owner only** | See the narrowing below. Three owner actions required; nothing else can proceed Gemma-side. |
| **G2/G3** capability | Engineer active | Scope widened — see below. |
| **G4** Neuronpedia | Lab Asst active | Load-bearing; escalate if thin. |
| **D1.6** Qwen ablation | Lab Asst active | Independent of every Gemma gate. |

**G1's blocking surface is narrower than the plan assumed.** Verified by anonymous
metadata call: `google/gemma-3-12b-pt` is `gated=manual` (sha `295efb63`) and **does**
require licence acceptance, but **`google/gemma-scope-2-12b-pt` is UNGATED**
(`gated=False`, sha `bbabd1e4`). Only the base model sits behind the gate. **Consequence:
all SAE-side work — downloading Gemma Scope 2 weights, writing and testing the JumpReLU
loader against real tensors — is not blocked by G1 and proceeds now.**

**Do not read "metadata resolves" as "access granted."** HF serves public metadata for
gated repos to unauthenticated callers. Whether the account has accepted the terms can
only be proven by an authenticated call, which requires the token that does not yet exist.

**Tamia token state:** absent. `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`,
`HUGGINGFACE_HUB_TOKEN`, `HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE` all unset; no
token file at any standard path; `whoami` returns `LocalTokenNotFoundError`.
`huggingface_hub` 0.24.0 is present.

**Repository is clean of token material** — pattern scan for `hf_[A-Za-z0-9]{30,}` across
the tree returned zero hits.

**Gitignore gap, recorded:** `.env` is ignored but **`.hf_token` and `hf_token.txt` are
not**. The recommended token location is `~/.cache/huggingface/token` (outside the repo
entirely, auto-discovered by `huggingface_hub`, no launcher change), so the gap never
arises — but never use those filenames inside the repo tree.


**Deliverables.** (1) Feature-necessity ablation. (2) Additional features beyond
cheese/UNESCO/Eurovision. (3) Cross-model reproduction on Gemma at Qwen scale.
(4) Interactive steer/ablate tool.

**Deadlines.** 70–100 % of experiment data by **2026-08-08**. Working tool
prototype by **2026-08-12**.

Author: Mohamed El Yazid — IID.

---

## 1. Model decision — Gemma 3 12B

**Second model: `google/gemma-3-12b-pt`, SAEs from `google/gemma-scope-2-12b-pt`.**

| | Qwen2.5-14B | Gemma 3 12B | Gemma 2 9B | Gemma 3 27B |
|---|---|---|---|---|
| Scale vs Qwen | — | **0.86×** | 0.64× | 1.9× |
| Layers | 48 | **48** | 42 | 62 |
| SAE layer | 28 | **28 — direct** | ~24 (converted) | converted |
| SAE source | in-house `rwu04lpb` | Gemma Scope 2 | Gemma Scope | Gemma Scope 2 |

Gemma 3 12B is the closest available match to Qwen2.5-14B in parameter scale,
and — pending the check below — carries the same layer count, so the SAE layer
maps **28 → 28** with no depth-fraction conversion. That makes the cross-model
comparison structurally exact rather than approximately matched.

27B is rejected on the PI's own criterion: at 1.9× Qwen it is not comparable
scale, and 12B is strictly closer. 9B is rejected as both further in scale and
requiring depth conversion.

**Verify the layer count on first load.** If Gemma 3 12B is not 48 layers, fall
back to relative-depth matching (Qwen L28/48 = 58 % depth) and record both the
absolute index and the depth fraction in every artifact.

**SAE selection.** Gemma Scope 2 ships `resid_post` at fixed depths (25/50/65/85 %)
**and `resid_post_all` covering every layer** at reduced width/L0 choice. Use
`resid_post_all` to reach layer 28 exactly. Start at width 16k, L0 target
"medium" (30–60), which is the closest analogue to the in-house Qwen SAE
(TopK k=100, 32× expansion). Record width and L0 in every artifact — they are
not comparable across choices.

---

## 2. Day-1 blocking gates

Four unknowns must be cleared before any sweep is launched. Each is minutes to
hours of work; each has a stated fallback except G1 and G4.

| Gate | Question | Fallback if it fails |
|---|---|---|
| **G1** | Gemma HF licence accepted, read token provisioned on Tamia | **None.** Single point of failure — clear first. |
| **G2** | Does `transformer-lens==3.2.1` support the Gemma 3 architecture? | Drop TransformerLens for this model; hook the residual stream through raw HF `transformers` forward hooks. The clamp mechanism needs a residual hook point, not TL specifically — this fallback is simpler, not harder. |
| **G3** | Does `sae-lens==6.44.2` know the Gemma Scope **2** releases? The pin predates them. | Load the SAE weights directly from the HF repo. Gemma Scope SAEs are JumpReLU: encode = ReLU(x·W_enc + b_enc) gated by a threshold, decode = f·W_dec + b_dec. ~30 lines, no dependency change. |
| **G4** | Does Neuronpedia carry autointerp labels at density for **gemma-3-12b** specifically — not just the 27B-IT demo model? | **None benign.** If labels are absent, feature discovery returns as real work and the schedule below must be re-cut. Check this before committing the sprint. |

G4 is the load-bearing assumption of the whole plan: the timeline survives only
because feature discovery is a lookup rather than a survey.

---

## 3. What is frozen

The Interlab governance chain has produced zero experimental artifacts and
cannot produce any on this timescale.

- **Freeze:** new R9 (ED-36 builder) audit cycles, R11 (ED-37 Lodestar boundary)
  implementation, R12 beyond the cheap Tier-1 tracking commit.
- **Allow to finish:** R9-V5 if already dispatched.
- **Science runs outside the certification chain**, using `scripts/legacy/`,
  exactly as the report's sufficiency results were produced. A deliberate
  trade — speed now, provenance later — stated openly rather than concealed.

Two blockers dissolve as a consequence:

- **ED-19** locks *Interlab's* Lodestar adapter, not Lodestar. `d:\lodstar`
  works and produced the 2026-07-01 runs. Per R11-D1A its temperature-0
  instrument is the **correct** one for comparability with existing sufficiency
  evidence, not a compromise.
- **R6-V4** gates the *ED-36 rebuild*, not Tamia. The existing venv trained five
  SAEs and certified four.

---

## 4. Compute envelope

Every Tamia job is whole-node (`--gpus-per-node=h100:4 --mem=0`,
`--account=aip-chgag196`). Gemma 3 12B ≈ 24 GB and Qwen-14B ≈ 28 GB in bf16
against 4×80 GB — both fit on a single card, so a whole node runs several
configurations concurrently.

**Batch aggressively.** One job covering 8 features × 6 scales × both modes costs
the same allocation as one feature at one scale. Few large fan-out jobs, never
many small ones.

**Check the credit balance before the first fan-out.** The last recorded figure
was 87 % of weekly allocation consumed; that reading is stale and the plan's
shape depends on it.

---

## 5. Three days to data

### Day 1 — clear the gates, anchor the hook

| # | Task | Owner |
|---|---|---|
| D1.1 | **G1**: accept Gemma licence, provision HF read token on Tamia | Lab Asst |
| D1.2 | **G4**: confirm Neuronpedia autointerp coverage for gemma-3-12b; pull candidate labels | Lab Asst |
| D1.3 | **G2/G3**: load `gemma-3-12b-pt`, verify layer count, load the layer-28 Gemma Scope 2 SAE, confirm encode/decode round-trip. Record which of TL / sae-lens worked and which needed the fallback | Engineer |
| D1.4 | Attach the clamp hook from `interplab/interventions/hooks.py` to Gemma's layer-28 residual point | Engineer |
| D1.5 | **Anchor test (hard gate).** Steer a known-good, clearly-labelled Gemma Scope 2 feature, scaled relative to *its own* natural activation range. If the expected concept does not appear, the hook is wrong and nothing downstream is trustworthy — stop and fix | Engineer |
| D1.6 | Launch Qwen 9056 ablation generation out-of-chain | Lab Asst |

### Day 2 — sweeps

| # | Task |
|---|---|
| D2.1 | Shortlist 8–12 Gemma features with clear labels across distinct domains. **If a concept has no matched feature, record it as a finding about corpus prevalence and move on — do not hunt** (`execution_roadmap.md` line 141) |
| D2.2 | Single fan-out job: all shortlisted features × scale sweep × {steer, ablate} on Gemma 3 12B |
| D2.3 | Judge the Qwen ablation through `d:\lodstar` (temperature 0, `concept_relevance` + `coherence`) |

### Day 3 — judge, consolidate

| # | Task |
|---|---|
| D3.1 | Judge the Gemma sweeps — identical rubrics, identical coherence ≥ 5 floor. Protocol parity is what makes the comparison legitimate |
| D3.2 | Cross-model comparison table: dose-response curves, operating points, ablation effect, in the format of report Tables 3–4 |
| D3.3 | Additional Qwen features, if D1.6 landed cleanly and budget allows |

**Definition of "70 %":** Gemma 3 12B, ≥ 6 features, both modes, judged, with a
populated cross-model table. Everything beyond is upside.

---

## 6. Week two — the tool

**The mechanism already exists.** `_make_clamp_hook` in
`interplab/interventions/hooks.py` does both modes: `scale > 0` steers,
`scale = 0.0` ablates. That is the entire backend of the PI's request.

**Scope.** Gradio app, four controls: model (Qwen2.5-14B | Gemma 3 12B), feature
(searchable, showing label and natural activation range), mode (steer | ablate),
scale slider in units of the feature's own corpus max. Free-text prompt;
baseline and intervened output side by side.

**The real risk is serving, not modelling.** Neither model runs on a laptop, and
a batch scheduler cannot host an always-on service. Build the app to run *inside*
an interactive allocation, reached over an SSH port-forward — standard HPC
practice. Deliver a documented launch procedure (`salloc` → start → tunnel →
open) rather than a hosted URL, and rehearse it once before the demo.

| Day | Task |
|---|---|
| 4 | Backend wrapper: load model + SAE, apply hook, generate; both models behind one interface |
| 5 | Gradio UI; feature search backed by the Day-2 shortlist and its labels |
| 6 | Second model wired in; side-by-side baseline vs intervened output |
| 7 | Launch procedure documented, tunnel rehearsed, demo script written |

**Do not** add authentication, persistence, multi-user queuing, or deployment
infrastructure. It is a prototype for one demo.

---

## 7. Cut list, in order

1. **Additional Qwen features** (D3.3) — the cross-model story does not need them.
2. **Qwen 9056 ablation** — `execution_roadmap.md` line 134 already ranks this
   sixth-cuttable, independently of this plan. Report sufficiency-only with the
   limitation stated and carry necessity into week two.
3. **Multilingual battery on Gemma** — genuine upside, not load-bearing.

**Never cut:** the anchor gate (D1.5), judging-protocol parity between the two
models (D3.1), and the cross-model table (D3.2). The table *is* the deliverable.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Gemma licence/token not cleared | G1, done first; the only true single point of failure |
| TransformerLens 3.2.1 lacks Gemma 3 support | G2 fallback to raw HF forward hooks |
| sae-lens 6.44.2 predates Gemma Scope 2 | G3 fallback to direct JumpReLU weight loading |
| Neuronpedia lacks gemma-3-12b labels | G4 — no benign fallback; re-cut the schedule with discovery as real work |
| Layer count ≠ 48 | Fall back to relative-depth matching, record the depth fraction |
| Credit exhaustion mid-sprint | Check balance before D2.2 |
| Tool cannot be demoed live | Recorded walkthrough; the launch procedure still ships |
