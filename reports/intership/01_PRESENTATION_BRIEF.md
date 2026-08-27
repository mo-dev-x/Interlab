# 15-minute presentation brief — the cut

*Mohamed El Yazid — IID · 2026-08-25*

**Read this instead of the design brief if you are building the talk.** The design brief
(`02_DESIGN_BRIEF.md`) specifies twelve figures and every number behind them. That is the right
document for a poster someone reads for ten minutes at their own pace. It is the wrong document for
twelve minutes of speaking to a room that is half domain, half not.

This file is the reduction: **one idea, five figures, twelve minutes.**

---

## 1. The one sentence

**For anyone:**
> There is a method for finding individual concepts inside a language model and switching them on.
> I reproduced it, and then I measured how much I could trust it — and found that the choices I make
> while analysing move the answer more than the effect I am trying to measure.

**For the domain half of the room, same claim in their vocabulary:**
> Four independent stages of the standard SAE-interpretability workflow are *unidentified*: an
> unstated analyst choice at each stage displaces the reported result by more than the reported
> effect size.

Everything else in the corpus is supporting material for that sentence. If you have to cut live, cut
toward it.

---

## 2. Twelve minutes, beat by beat

| Time | Beat | Figure |
|---|---|---|
| 0:00 – 1:30 | **The setup.** A language model is billions of numbers nobody can read. Sparse autoencoders claim to split that into human-nameable concepts — "cheese", "Montreal". If true, you can find a concept and turn it up. | none — talk |
| 1:30 – 3:30 | **It works.** Feature 9056 is a cheese concept. Turned up at the right strength the model rewrites its own identity around cheese, and stays coherent: judged coherence 5.38, relevance 5.50. Show the sweep — too weak does nothing, too strong destroys the text, and the usable window is narrow. | **fig02** cheese sweep |
| 3:30 – 4:15 | **The turn.** That result is real. But it rests on a chain of judgement calls I made, and nobody had measured what those calls were worth. So I measured them. | none — this is the pivot, hold the room |
| 4:15 – 8:00 | **The finding.** Four stages. Take them one at a time; each tile is a sentence. Land the point: *the grey choice is bigger than the coloured result, every time.* | **gen13** headline tiles |
| 8:00 – 9:30 | **What survived.** One result came through the same scrutiny intact: feature 2048, positive in all 16 of 16 passages. Same slide shows the statistic that would have hidden it — the mean says the opposite of the median. | **gen05** feature 2048 |
| 9:30 – 11:00 | **What I built so this is checkable.** Three repositories: the science, a working tool anyone can drive, and an independent evaluation harness. Show the tool actually running. | **gen08** repo map, then the **tool screenshot** |
| 11:00 – 12:00 | **What it means.** Not "SAEs don't work". It is: results from this method are only as good as the analyst choices behind them, and those choices are currently invisible in how the field reports. Name them and the field gets more comparable overnight. | none — close on your face, not a slide |
| 12:00 – 15:00 | Questions. | backup figures, §5 |

**Pacing note.** 12 minutes of speech is roughly **1,500 words**. Write the beats out and time them
once. The commonest failure here is spending six minutes on the setup and rushing the finding.

---

## 3. The five figures — and nothing else on the wall

| # | File | Why it earns its place |
|---|---|---|
| 1 | `fig02_cheese_9056_sweep_judged.png` | The concrete positive result. A curve with a usable window is legible to anyone. |
| 2 | `gen13_headline_tiles.png` | **The headline.** Four tiles, plain English, five seconds to read. This is the talk. |
| 3 | `gen05_feature_2048.png` | The one clean causal win, plus the statistic that erases it. Shows you checked yourself. |
| 4 | `gen08_repo_map.png` | Scope of the engineering, in three boxes anyone can parse. |
| 5 | *tool screenshot* | **Does not exist yet — see §6.** The single most convincing artifact for a non-expert. |

---

## 4. What is cut, and the one-line defence for each

You will be asked about some of these. Have the answer, do not show the figure.

| Cut | If asked |
|---|---|
| `gen01` four-panel displacement | "The full version with every unit and source is in the report — these tiles are the same four measurements." |
| `gen02` comparator evolution | "The comparator had to be rebuilt four times before it could fail honestly; happy to go through it." |
| `gen03` interval brackets zero | "The cross-model question didn't resolve — the two defensible bounds straddle zero, so I don't claim a direction." |
| `gen04` dose–noise floor | "Nearly all the steering contrasts sit inside the measured noise floor, so I don't report them as effects." |
| `gen06` control floor | "The baseline is clean — the models essentially never volunteer the concept unprompted." |
| `gen07`, `gen09`–`gen12` | Infrastructure, cross-lingual and architecture detail. Interesting, not load-bearing for the claim. |
| The other Effort-A features (UNESCO, Eurovision, Montreal, poutine) | "Same method, four more concepts — including two negative results I kept in the record." |
| Interlab / Lodestar internals | Collapse to one line in beat 6. A mixed room will not follow subsystem names, and does not need to. |

**Do not apologise for the cuts on stage.** A talk that lists what it isn't covering spends its
scarcest resource on absence.

---

## 5. Backup, for questions only

Have these open in a folder, not on the wall: `gen01`, `gen02`, `gen03`, `gen04`, `gen06`,
`gen11`, `gen12`, and the three activation-distribution figures. `figures/optional/` holds them.

**The three questions a domain expert will ask:**

1. *"Isn't 2.6× just sampling noise at n=40?"* — No: browsing and the seeded draw sample the same
   dictionary; the difference is the selection procedure, not the sample size. That is the point.
2. *"Did you correct for multiplicity?"* — Yes where it matters. Feature 2048 survives Bonferroni
   over 18 tests. The one dose-cell that exceeds the noise floor is explicitly *not* called an
   effect: one draw of thirty-five, uncorrected.
3. *"Does this generalise beyond your model?"* — Not demonstrated. Everything here is Qwen2.5-14B
   plus a second pairing. The methodological finding is about the workflow, not about one model, but
   I have not proven it transfers and I don't claim it.

---

## 6. The one thing worth making before the talk

**A before/after steering example, as text.** Two short blocks: the model's ordinary answer, and its
answer with the cheese feature amplified. Nothing in the corpus is currently in this form, and for
the non-domain half of the room it is worth more than any chart — it is the only asset that makes
"switching on a concept inside a model" concrete rather than abstract.

Source it from an existing judged generation at scale 55 so the text on the wall is a real logged
output, not a re-run. Keep it to about 40 words per side.

Second priority: the **tool screenshot** (figure 5 above). Needs a live capture of the running
interface — concept, direction, strength, and the Compare panel. Do not mock it up.
