# BINDING PRE-REGISTRATION — ablation instrument substitution

**Authored 2026-08-07, before any ΔNLL measurement exists.** No necessity result has been
computed, on any feature, by any agent. The substitution below is recorded now precisely so it
reads as a documented instrument change rather than a switch made after seeing uninterpretable
cells. This is the one un-pre-registered choice in an otherwise clean record; this document
closes it.

---

## 1. The original protocol, as specified

Ablation was to be measured **behaviourally**: for each of 9 features, clamp the feature to `0.0`
during generation on a fixed set of 8 generic prompts, and compare the ablated continuation
against an unhooked baseline and a random-feature control. Identical prompt set for steering and
ablation.

## 2. Why it was abandoned — empirical, not anticipatory

Two anchor-test reruns on feature 250 failed **in mirror image**, at ceiling and at floor.

**Rerun 1 — saturated baseline.** Prompt: *"…here is a step-by-step guide"* (bicycle tire).
Baseline was already imperative (*"Lay the bike on its side. Take the tire off…"*) and the ablated
continuation was, if anything, more explicitly instructional (*"1. Find the Source of the Leak…"*).
The prompt's own wording drives imperative continuation through pathways independent of feature
250, so the test cannot discriminate.

**Rerun 2 — near-zero baseline.** Prompts: *"My laptop won't turn on."* / *"The recipe came out
too salty."* The saturation confound was gone, but both baselines pulled the model into
first-person past-tense narrative (*"I had to add 1 1/4 cups of milk…"*, *"I have tried removing
the battery…"*) rather than second-person advice. With near-zero concept presence in the baseline
there is **nothing to weaken**, so the test cannot discriminate for the opposite reason.

**The diagnosis is structural, not a prompt-selection failure.** Behavioural ablation can only
detect weakening where the concept is *already present and not prompt-driven* — a measurable
middle band. Two draws from opposite tails establish that the band is narrow. For low-density
features the band is effectively empty: **12800 at density 7.8e-4 will essentially never appear in
a neutral continuation**, so no prompt choice rescues it. Running the original design would have
produced ~108 cells of uninterpretable data that *reads as a result*.

## 3. The substituted instrument

**ΔNLL under ablation, on the feature's own top-activating text.** For each feature *F*, take *F*'s
top-16 activating snippets; run one unhooked forward pass and one with *F* clamped to `0.0` via
`interplab.interventions.hooks._make_clamp_hook`; report the increase in negative log-likelihood
on the snippet tokens, and separately at the positions where *F* is active.

**Why this dissolves the problem rather than tuning around it.** A feature's top-activating text is
*by construction* the context where that feature is doing work, so headroom is guaranteed. No
generation, no sampling variance, and **no judge** — which matters more than usual here, because
the sufficiency half of this experiment inherits a measured **3.7× swing in judged relevance from a
one-word concept-string change**. The necessity half is now the **more robust** of the two.

## 4. Two controls — both required

| Control | Question it answers | Why it alone is insufficient |
|---|---|---|
| **Cross-feature** — a random feature ablated on ***F*'s own top-activating text** | Is the effect specific to *F*, rather than a property of this text? | **Weak by construction:** an inactive feature ablates to approximately nothing, so it is easy to beat. Must be same-text — ablating the random feature on *its* own top text would confound with text difficulty. |
| **Within-feature** — *F* ablated on **text where *F* does not fire** | Does the effect track where *F* is active, rather than being a global perturbation? | Says nothing about specificity to *F* versus other features. |

Together they make the result **falsifiable in both directions**. Fixed seed, recorded.

## 5. The number is an upper bound — enforced in field names, not only prose

Selecting on maximal activation means every quantity here is *"on text where F is maximally
active,"* **never** *"on text."* This binds the schema, under the same rule that renamed
`qwen_comparison` → `qwen_reference_metadata`: **field names travel further than caveats.** A
caveat lives in one paragraph; a column header propagates into every downstream table, notebook and
plot legend. Field names must carry the qualifier, e.g.
`mean_delta_nll_on_max_activating_text`, not `mean_delta_nll`.

## 6. Declared construct mismatch — the two halves are not a matched pair

- **Sufficiency** (judged generation under steering) is **behavioural**.
- **Necessity** (ΔNLL under ablation) is **representational** — the feature carries information the
  model uses.

Related, but different constructs. The write-up must **name this** and must not present them as a
matched pair. **It is not an apology:** the necessity half is the more robust one, being immune to
the judge fragility the sufficiency half inherits. Added to the declared-divergence list beside
corpus-max vs sample-max, differently-constructed dead rates, and the two evidence sources.

## 7. What is *not* changed

The behavioural ablation arm **still runs** in the frozen sweep harness and is **still reported**,
under the pre-registered conditioning rule: cells whose baseline is concept-**saturated** and cells
whose baseline shows **near-zero** concept presence are *both* reported as **uninformative for
ablation**, disclosed with their counts, never silently pooled and never dropped. Two measurements
of necessity — one direct, one behavioural — not a replacement.

## 8. What would falsify the necessity result

- ΔNLL for *F* on *F*'s top text is **not** meaningfully above the **cross-feature** control →
  the effect is a property of the text, not of *F*.
- ΔNLL for *F* on *F*'s top text is **not** meaningfully above the **within-feature** control →
  the effect is a global perturbation, not activity-tracking.
- Either outcome is reported as the finding. Neither is grounds for changing the instrument again.
