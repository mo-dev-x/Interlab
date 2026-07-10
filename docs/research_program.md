# A Research Architecture for Mechanistic Interpretability

*Strategic research plan, July 2026. Produced from a first-principles review of the internship research program; supersedes the original four-phase arc (Golden Gate replication → SAE param comparison → cross-architecture → attribution graphs).*

*Part I ("Grounded Interpretability") is the plan of record: a five-year program to make interpretability claims decidable. Part II ("Principles of Learned Computation") is the companion theory program designed under the assumption that Part I succeeds, together with the expected-impact comparison between the two. They are designed to be read as one sequence: Part I builds the instruments; Part II attempts the laws.*

---

# Part I — Grounded Interpretability

---

**The central thesis, stated once so every phase can refer back to it:** mechanistic interpretability's binding constraint in 2026 is not methods, models, or compute. It is that the field **cannot decide when an explanation is correct**. There is no ground truth, no formal standard of faithfulness, and no statistical culture — so methods proliferate without selection pressure, and claims accumulate without compounding into knowledge. The poutine episode is the thesis in miniature: weeks spent unable to adjudicate between seven candidate causes *because the field has no machinery for adjudicating such questions*. That is not a personal failure. It is the field's most important open problem, discovered independently by running into it, and the program below is built on it.

---

## Phase 1 — State of the Field: A Structural Analysis

### What is essentially solved

1. **Why polysemanticity exists.** Superposition (Toy Models of Superposition, 2022) is a real conceptual solution: networks represent more features than dimensions by tolerating interference, and this predicts polysemantic neurons. The vocabulary and the toy-model regime are settled.
2. **Linear readout of high-level concepts.** For a very large class of concepts, a linear probe finds them, and steering along the direction causally moves behavior. This is now a phenomenon, not a hypothesis — with known exceptions (multi-dimensional/circular features) that qualify it without overturning it.
3. **Prompt-scale circuit analysis in small models.** Induction heads, IOI, modular-addition Fourier circuits, Othello world models. The existence proof that trained transformers contain human-comprehensible algorithms is complete. Another instance adds nothing.
4. **Feature extraction as engineering.** The SAE family and its descendants (transcoders, crosscoders) reliably produce large dictionaries of mostly-interpretable directions, and this is commoditized (Gemma Scope, Llama Scope, Neuronpedia).
5. **Semi-automated circuit hypothesis generation.** Attribution graphs over transcoder features produce prompt-level mechanism hypotheses at scale.

Note what "solved" means here: each is an existence proof or an engineering capability. Nothing on this list is a validated *theory*.

### Dead ends

1. **SAE maximalism** — "enumerate the dictionary, understand the model." Dead for four independent reasons: dictionaries are not canonical (seed-dependent atoms), coverage depends on concept frequency and capacity (the poutine result is an instance of a known scaling law), absorption/splitting mean the atoms gerrymander each other, and there is no account of composition. The dictionary is a useful *measurement instrument*, not the model's ontology.
2. **Feature-zoo papers.** "We found a feature for X" carries no information the field lacks.
3. **Steering as an application.** AxBench settled that prompting and finetuning dominate; steering survives only as *evidence* in causal arguments.
4. **Unvalidated autointerp.** LLM-generated feature labels scored by plausibility launder uncertainty into apparent knowledge. Automation without a correctness criterion just produces wrong explanations faster.
5. **Correlational probing studies** without interventions.

### Overhyped

1. **Attribution graphs as "interpretability solved."** They explain a *replacement model*. Error nodes absorb what the transcoders miss; attention patterns are frozen and unexplained (the QK side of the computation is a black box inside the explanation); graphs are prompt-specific and don't automatically generalize to mechanism claims. Superb hypothesis generator; not yet a validated explanation format.
2. **The near-term auditing narrative** — "interp will verify frontier model safety soon." The gap between prompt-level mechanism and distribution-level disposition (bottleneck B6) is unbridged, and almost nobody is working on the bridge itself.
3. **Each new method's launch cycle.** The field has a pattern: method launches with qualitative wins on cherry-picked examples → two years later the systematic evaluation arrives and deflates it (probing→SAEs→steering→autointerp, each in turn). The deflation papers were predictable *at launch*. That predictability is exploitable — it tells you what to build.

### The field's operating assumptions, and which are likely wrong

- **A1: Linear representation is the general case.** Mostly right as far as it goes, but it's a statement about *storage*, not *computation* — it says nothing about how features are transformed, bound, or routed. The field over-indexes on representation and under-indexes on computation.
- **A2: Dictionary atoms are the model's units.** Likely wrong. Atoms don't reproduce across seeds; subspaces do. The stable object appears to be coarser than the atom and finer than the layer, and the field lacks a definition of it.
- **A3: Activations are the right decomposition target.** Contested, correctly. Activations are the *trace* of the program; parameters are the program. The APD/SPD line decomposing weights directly is young but conceptually well-motivated, and the activation-vs-parameter question is genuinely open.
- **A4: Human concept vocabulary approximates the model's ontology.** Anthropocentric sampling bias. We search for features we can name; the model's actual computational variables need not align with nameable concepts, and every "interpretable fraction" statistic is conditioned on this bias.
- **A5: Prompt-level mechanisms aggregate into behavior-level understanding.** The great unexamined leap. Nobody has shown that a pile of attribution graphs composes into a claim like "this model will behave deceptively under distribution shift."
- **A6: Universality.** Partially supported (induction heads everywhere), partially contradicted (circuit details vary). The field treats it as background faith rather than a measurable variable.
- **A7: Findings transfer across scale and architecture.** Rigorous public work lives at ≤9B dense models; deployed frontier models are MoE reasoning models. This is a quietly enormous extrapolation.

### The deepest bottlenecks

- **B1 — No ground truth.** The only settings where the true mechanism is known are toys, compiled models (Tracr), and semi-synthetic IIT-trained models (InterpBench, now folded into MIB). Everywhere else, explanations are scored by plausibility. Consequence: no selection pressure among methods; the field cannot converge.
- **B2 — No formal standard for "explanation."** Causal abstraction (Geiger et al.) is the best candidate — an explanation is a simpler causal model plus an intervention-respecting correspondence map — but it hasn't been scaled, hasn't absorbed error terms/dark matter, and hasn't been made statistical.
- **B3 — Dark matter.** Every decomposition leaves a residual, and we cannot tell whether it is noise or the load-bearing part.
- **B4 — The ontology problem.** No representation-invariant definition of a "unit of computation." "Feature" conflates a basis element of one particular learned dictionary with a causal variable of the model.
- **B5 — Binding and compositionality.** Dictionaries are bags of atoms with no syntax. How "the red ball beside the blue cube" avoids binding errors is unexplained at the mechanism level.
- **B6 — The prompt→disposition gap.** Safety questions are distributional ("does this model have tendency X"); interp answers are token-level.
- **B7 — No statistical culture.** Interp papers routinely make claims with n=1 prompts, no seeds, no error bars, no multiple-comparison control — standards that would be desk-rejected in psychology.

B1 and B2 are upstream of everything else. That is where a lab should be founded.

---

## Phase 2 — First Principles

If the field were rebuilt today, the first question would not be "what features exist?" It would be: **what does it mean to explain a learned function, and when is such an explanation correct?**

From that primitive, the natural sequence of questions:

1. **What is an explanation, formally?** The most defensible answer: an explanation is a *compression* of the computation — a simpler causal model, a correspondence map to the network, a **domain of validity** (the input distribution over which it holds), and an **error budget** (how much behavior it fails to account for, measured on-distribution). Almost no current interp artifact ships with the last two components. They should be as mandatory as error bars in physics.
2. **When is a decomposition identifiable?** Dictionary learning, ICA, and causal representation learning have decades of identifiability theory — conditions under which the recovered factors are the true ones up to symmetry. Interp imported the *algorithms* (sparse coding) but not the *theory*. Nobody can currently state the conditions under which an SAE's atoms are determined by the data rather than by the optimizer's whims. The seed-instability results say: often they aren't.
3. **What is a unit?** A concept in a network should be defined as an equivalence class invariant under reparameterization — something preserved across basis changes, seeds, and (ideally) dictionary granularities. Current "features" fail this test by construction.
4. **What is the right theory of abstraction levels?** The field needs the analogue of the renormalization group: principled coarse-graining from microscopic (weights) through mesoscopic (subspaces/circuits) to macroscopic (behavioral dispositions), with error tracked across levels. Causal abstraction is the seed of this; it needs the multi-scale and statistical development.
5. **Where is the statistics?** Every mechanistic claim is a statistical claim about a prompt distribution and a training-randomness distribution. The hypothesis-testing framework for interp simply does not exist.

**Concepts that should exist but don't:** domain of validity; explanation error budget; canonical form of a decomposition; identifiability regime; unit-as-equivalence-class; mechanistic effect size.

**Methodologies that are engineering, not science:** the SAE sparsity penalty (sparsity is an aesthetic proxy for interpretability, derived from nothing); autointerp plausibility scoring; steering demos as validation; faithfulness metrics invented per-paper and known to be gameable; "interpretable fraction" statistics conditioned on human nameability.

---

## Phase 3 — The Research Program: "Grounded Interpretability"

Five projects, each enabling the next. The spine: *make interpretability claims decidable, then use that machinery to make discoveries nobody else can make.*

### P1 — Identifiability Phase Diagrams via Controlled-Ontology Testbeds (months 0–12)

**Motivation:** B1. The field cannot tell when its decomposition methods recover truth. **State of knowledge:** Toy Models covers hand-designed linear regimes; Tracr compiles programs but produces un-trained-like networks; InterpBench/MIB test *circuit localization* on fixed tasks. **Why insufficient:** nobody has built testbeds with *parametric control over the data-generating ontology* — trained (not compiled) transformers on synthetic distributions with controlled concept frequency, concept correlation, hierarchy depth, compositional structure, and superposition pressure — and then measured *ontology recovery* (does the method find the true latent variables?) as a function of those parameters. That is precisely the experiment the poutine failure demanded and couldn't have. **Hypothesis:** decomposition methods (SAE, transcoder, crosscoder, SPD) have sharp identifiability regimes governed by data statistics, and naturally occurring concepts often live outside them. **Mathematics:** dictionary-learning/ICA identifiability theory (Hyvärinen's nonlinear ICA results are the template), basic random matrix theory, causal abstraction for defining "recovery." **Methods:** train families of 1–50M-param transformers on generative grammars with known latents; verify what the *network* actually implements by exhaustive intervention (ground truth must be established causally, not assumed from the data design — see Phase 7); sweep decomposition methods; produce phase diagrams. **Tooling:** a testbed generator (generative process → trained model → interventional verification report) and a method-agnostic decomposition-evaluation harness. **Obstacles:** networks may implement solutions unrelated to the designed latents (this is a finding, not a bug); compute for model families. **Alternative interpretations to guard against:** failure of recovery may reflect optimizer variance rather than fundamental non-identifiability — separate these with seed ensembles. **Success:** phase diagrams that *predict* feature discoverability in a real LLM (e.g., frequency-coverage curves in Gemma Scope match testbed predictions — the internship assets become the validation arm). **Failure:** testbed regularities that flatly don't transfer to real models (itself publishable, but demotes the program). **Publications:** benchmark+findings at NeurIPS D&B or main track; a method-failure analysis at BlackboxNLP. **Long-term:** every later project inherits this evaluation substrate.

### P2 — Representation-Invariant Units: What Is a Feature, Formally? (months 9–24)

**Motivation:** B4. **State of knowledge:** atoms unstable across seeds, subspaces reproducible; Matryoshka-style hierarchical dictionaries; feature splitting/absorption documented but untheorized. **Why insufficient:** all descriptive. Nobody has *defined* the stable object and built its estimator. **Hypothesis:** the model's stable ontology is a hierarchy of subspaces (a nested partition refined by dictionary granularity); atom-level instability is basis noise on stable coarse structure; "one feature vs. many" questions (including the multilingual A/B/C question) are ill-posed until indexed by granularity. **Mathematics:** Grassmannian geometry and principal angles, cluster-stability theory, MDL for choosing granularity. **Methods:** cross-seed/cross-width/cross-method agreement analysis on P1 testbeds where the true hierarchy is known, then on real models; interventional validation (do subspace-level interventions transfer across seeds where atom-level ones don't?). **Tooling:** extends P1 harness. **Obstacles:** subspace matching across models is technically fiddly; risk of rediscovering CCA with extra steps — the differentiator must be *causal* validation, not similarity metrics. **Alternative interpretation:** stability at subspace level could be an artifact of shared data rather than shared computation — control with disjoint training subsets. **Success:** a definition + estimator of canonical units with demonstrated cross-seed interventional transfer. **Failure:** no granularity at which stability emerges — a deep negative result indicting the decomposition program wholesale (still a major contribution). **Publications:** ICLR/NeurIPS main-track material if the estimator works; the negative result lands at main venues too given current field anxiety. **Long-term:** gives the field its unit — the prerequisite for any cumulative science.

### P3 — A Faithfulness Calculus for Mechanistic Explanations (years 2–3)

**Motivation:** B2. Attribution graphs and circuit analyses produce explanation objects nobody can score. **State of knowledge:** causal abstraction gives the skeleton; per-paper faithfulness metrics exist, disagree, and are gameable; MIB standardizes tasks but not the *semantics* of explanation quality; the BlackboxNLP 2025 shared task shows community appetite. **Why insufficient:** no framework handles error terms/dark matter, domains of validity, or statistical uncertainty; none is method-agnostic. **Hypothesis:** explanation quality decomposes into faithfulness (intervention agreement), completeness (behavior variance accounted for, on-distribution), and robustness (stability across the prompt distribution), and these can be estimated with confidence intervals. **Mathematics:** causal mediation and abstraction, proper scoring rules, concentration inequalities for the statistics. **Methods:** formalize on P1 testbeds (where explanation quality is checkable against truth), then score real pipelines — attribution graphs being the flagship target: quantify how much lives in error nodes and frozen attention across prompt families. **Obstacles:** the field may not adopt the standard (mitigation: ship it as a usable harness with adapters for existing pipelines, and run a shared task). **Success:** the standard is used by groups other than ours; systematic unfaithfulness regimes of attribution graphs identified. **Failure:** metrics that are themselves gameable — red-team them in-house first. **Publications:** one theory+framework paper, one large empirical audit. **Long-term:** this is the selection-pressure machine; it converts the field from method-marketing to method-competition.

### P4 — Mechanism → Disposition: Predictive Interpretability on Model Organisms (years 3–5)

**Motivation:** B6, and the entire practical justification of interpretability: can mechanism predict behavior that behavioral evaluation cannot? **State of knowledge:** auditing-game work (planted objectives, sleeper-agent-style organisms, emergent-misalignment replications) exists but evaluates *teams*, not formal methods; model diffing (crosscoders) describes finetuning changes without predictive claims. **Why insufficient:** nobody has established the aggregation step — from many prompt-level mechanisms (P3-scored) over invariant units (P2) to a distributional claim with a validated error budget. **Hypothesis:** mechanism-level evidence yields strictly better OOD behavior prediction than behavioral testing at matched budget, at least for planted dispositions. **Methods:** organisms with known planted dispositions; blind prediction protocols (preregistered: mechanism team predicts held-out-distribution behavior). **Obstacles:** frontier labs will do internal versions with 100× resources — the academic role is the *public, reproducible protocol* (internal results aren't science anyone can build on); organisms may be too easy (planted dispositions are cruder than emergent ones). **Success/failure:** the prediction advantage exists / doesn't — either answer is field-shaping. **Publications:** main-track safety+interp venues; highest-ceiling project in the program. **Long-term:** if successful, the first rigorous demonstration that interpretability *pays rent*.

### P5 — Synthesis Thread: A Multi-Scale Account of Learned Computation (continuous; deliverable only by year 5)

Not a project — a discipline. Maintain, from year 1, a living document forcing P1–P4 into one formalism: identifiability conditions (P1) + invariant units (P2) + scored abstractions (P3) + disposition bridge (P4) = a candidate multi-scale theory of description for neural computation. If by year 4 the pieces cohere, this becomes the monograph/position paper that defines a subfield. If they don't cohere, the document tells you *where* they conflict, which is the next research program. An adjacent thread to watch, not lead: developmental interpretability / singular learning theory — when the P2 units *form* during training. Mila is a good place to find collaborators for that branch without owning it.

---

## Phase 4 — Original Research Opportunities

Each advances interpretability itself; none is "existing method, new model."

1. **Statistical inference for interpretability claims.** Hypothesis tests, effect sizes, and multiple-comparison control for feature and circuit claims. Cheap, unclaimed, and mortifyingly absent — half the field's published claims may not survive n>1 seeds. Natural first paper inside P1.
2. **The dark matter question, causally.** Prior work decomposes SAE error into components; nobody has established what the residual *does* — ablate it, patch it, test whether behavior-critical computation hides there. Every decomposition-based safety argument silently assumes the residual is inert.
3. **Computation in superposition.** Theory exists for how networks could compute on compressed codes with bounded interference (Vaintrob et al.), but it has never been confronted with trained models: do real networks implement error correction, and how does interference not compound across 40 layers? Nearly empty territory.
4. **Adjudicating parameter-space vs. activation-space decomposition.** APD/SPD vs. SAE-family on identical ground-truth testbeds (P1 makes this possible). These are competing answers to "what should we decompose?", currently argued by intuition.
5. **The binding problem in trained transformers.** Design minimal tasks requiring variable binding; find the mechanism; test whether any dictionary-based ontology can even express it. Compositionality is the wall the entire feature paradigm will eventually hit.
6. **(High-risk) Interpreter models with verified rewards.** Train models to produce explanations scored by P3's faithfulness calculus rather than plausibility. Only sensible *after* P3 exists — automation before validation is the field's recurring sin.

---

## Phase 5 — The Fundamental Questions

1. **The ontology question: what are the natural units of learned computation?** Matters because every method presupposes an answer. Unsolved because "unit" has never been defined invariantly. Difficult because the ground truth is inaccessible and the symmetry group of equivalent parameterizations is enormous. Breakthrough: a definition whose estimator gives cross-seed causal transfer. Would spawn branches the way the gene concept spawned genetics.
2. **The compressibility question: do faithful, human-graspable explanations of frontier models exist at all?** The field's existence assumption. Unsolved because nobody has formalized the tradeoff between explanation length and error budget for real networks. Difficult because it needs complexity-theoretic tools the field doesn't use. Breakthrough: either a compression theorem or a lower bound showing certain behaviors have no short faithful description. A negative answer would redirect billions of dollars of research; a positive one would define the target of the entire field. Either creates a branch.
3. **How is reliable computation performed in superposition?** Interference should compound across depth; it evidently doesn't. Breakthrough: an error-correction account verified in trained models. Would connect interp to coding theory and likely change architecture design.
4. **The binding problem.** How networks represent *structured* combinations without confusing which attribute belongs to which entity. Unsolved because dictionaries have no syntax and nobody has the right minimal testbed. Breakthrough would give interp its compositional semantics — the jump from words to grammar.
5. **When and why does structure crystallize during training?** Phase transitions, circuit formation, the developmental story (SLT is the main formal candidate). Breakthrough: predicting *before training finishes* which mechanisms will form. Would fuse interp with learning theory and create a predictive science of training.
6. **Universality: is the solution set of SGD-trained networks small?** If independently trained networks converge to equivalent mechanisms, interp becomes a natural science with reproducible laws; if not, every analysis is a case study. Unsolved because comparing mechanisms across models requires exactly the invariant units of Q1 — the fundamental questions bottleneck through the ontology problem.

---

## Phase 6 — Comparative Advantage

**Specialization:** the identifiability and evaluation science of interpretability — the person who can say, with proof, *when a decomposition can be trusted and what the real units are*. This is B1/B2, the field's upstream bottleneck; it is tractable without frontier-model access; it compounds (every method the field invents becomes new input); and the entry cost is already paid — the poutine investigation *was* an identifiability study conducted without the theory.

**Position fit:** Mila — meaningful compute, strong causal-inference and theory culture, no frontier-weights access. Never compete where frontier access is the deciding resource (internal auditing of production models, scale races). Compete on rigor, controlled experiments, theory, and public standards — the things internal lab work structurally underproduces because it isn't reproducible science.

**Unfair-advantage skills (next 2–3 years):** identifiability theory from ICA/dictionary learning/causal representation learning; causal mediation and abstraction formalism; experimental statistics as reflex; the unglamorous craft of training many small models cleanly — testbed engineering is instrument-building, the way telescope-grinding was for early astronomers.

**Ignore:** feature zoos; steering applications; autointerp label mills; re-implementing each new method the week it launches; frontier-scale replication; the weekly paradigm funeral. Also: don't become purely "the benchmark person" — see Phase 7.

---

## Phase 7 — Brutal Critique of the Roadmap (and Repairs)

1. **"Synthetic testbeds are the field's oldest false comfort."** Trained-on-grammar transformers may occupy a different solution regime than models trained on human text; the phase diagrams may be beautiful and irrelevant. *Strongest objection.* Repair: every P1/P2 paper ships at least one preregistered prediction tested on a real LLM; the testbed ladder climbs toward realism (algorithmic → grammar → naturalistic-corpus-with-planted-structure). Testbeds are theory generators, never endpoints.
2. **"Your ground truth is fake."** You control the data's latent variables, not the network's solution. Repair: ground truth is established *interventionally* on each trained testbed model (feasible at small scale by near-exhaustive causal testing); data-ontology vs. model-ontology divergence is promoted from nuisance to measured object of study.
3. **"You're fighting the last war."** Evaluating SAEs in 2026 targets a method the field is leaving. Repair: the calculus (P3) is method-agnostic — it scores *explanation objects* regardless of what produced them. If automation wins, an automated pipeline needs a verified reward signal, and P3 is exactly that. The evaluation layer survives paradigm shifts; that is a reason to own it.
4. **"Meta-science is a junior researcher's career trap."** Repair: *every* project pairs an audit with a positive discovery (P1: the phase diagram; P2: the stable-unit estimator; P3: the unfaithfulness regimes). Collaborate with the authors of evaluated methods (APD/SPD group, MIB group, Neuronpedia) rather than sniping.
5. **"P4 will be scooped internally by frontier labs; P5 is grandiose."** P4 is scoped to open model organisms and public protocols — the reproducible-science lane labs don't occupy. P5 is demoted from deliverable to synthesis discipline with a year-4 go/no-go.
6. **"Nonlinear identifiability theory is famously weak."** Aim: partial identifiability results plus phenomenological laws, with theorem-strength results as upside, not plan-of-record.
7. **"What if decomposition itself is the wrong paradigm?"** Then "when can we trust the explanation?" transfers wholesale to whatever replaces it (e.g., CoT-monitoring faithfulness). The evaluation specialization survives even this.

---

## Phase 8 — Final Architecture

**Field map in one paragraph.** Interpretability has proven that comprehensible structure exists in trained networks (solved existence proofs), has industrialized measurement instruments of unknown reliability (SAE-family, attribution graphs), and is blocked by five things: no ground truth (B1), no formal standard of explanation (B2), no invariant units (B4), no compositional account (B5), and no bridge from prompt-level mechanism to distributional disposition (B6) — all governed by an absent statistical culture (B7). The fundamental questions (ontology, compressibility, computation-in-superposition, binding, training dynamics, universality) all bottleneck through B1/B2/B4.

**Specialization.** Grounded interpretability: identifiability theory, controlled testbeds, invariant units, and faithfulness standards — the referee who also plays.

**Roadmap and dependencies.**

| Project | When | Question | Depends on | Risk |
|---|---|---|---|---|
| P1 Testbeds & phase diagrams | yr 0–1 | When do decompositions recover truth? | — | Low-mid |
| P2 Invariant units | yr 1–2 | What is the stable ontology? | P1 harness | Mid |
| P3 Faithfulness calculus | yr 2–3 | When is an explanation correct? | P1, P2 | Mid |
| P4 Mechanism→disposition | yr 3–5 | Does mechanism predict behavior? | P2, P3 | High |
| P5 Synthesis thread | continuous | Does it cohere into theory? | all | High |

**High-risk / high-reward branches:** compressibility theory (Q2), computation-in-superposition empirics, binding testbeds, interpreter models with P3 rewards.

**Safe publication branches** (each internship/semester-sized, each feeding the spine): the statistics-for-interp framework; the dark-matter causal audit; SPD-vs-SAE adjudication on P1 testbeds; MIB/BlackboxNLP shared-task entries; the granularity-dependence study from the existing multilingual assets (the Qwen SAEs and concept battery slot directly into P1's real-model validation arm — nothing already built is wasted).

**Skills:** causal inference and causal abstraction; ICA/dictionary-learning identifiability; high-dimensional geometry (Grassmannians, principal angles); MDL/information theory; experimental statistics; small-model training craft; enough SLT to collaborate.

**Reading roadmap (ordered):** Toy Models of Superposition → Sharkey et al., *Open Problems in Mechanistic Interpretability* → Geiger et al.'s causal abstraction line → the SAE canon *with* its critiques (splitting, absorption, seed instability, dark matter) → APD and SPD → *On the Biology of a Large Language Model* read adversarially (list every unverified step) → InterpBench, MIB, and the BlackboxNLP shared task findings → Vaintrob et al. on computation in superposition → Hyvärinen's nonlinear ICA identifiability papers → Grünwald's MDL → an SLT primer last.

**Tooling roadmap:** (1) testbed generator — generative process spec → trained model family → interventional ground-truth report; (2) method-agnostic decomposition-evaluation harness with adapters (SAELens, transcoders, SPD); (3) a statistics library for interp claims. These three artifacts are themselves field contributions.

**Milestones.** *Year 1:* testbed suite public; phase-diagram paper with one validated real-model prediction; statistics framework note; known as rigorous, not merely critical. *Year 3:* invariant-unit estimator published with causal validation; faithfulness calculus released and used by at least one external group; attribution-graph audit landed; a shared task run under our metrics. *Year 5:* the mechanism→disposition prediction result — in either direction — on public organisms; the synthesis document published as a position/monograph; a recognizable subfield ("grounded interpretability") with our tooling as its infrastructure. If the field pivots paradigms along the way, the evaluation layer moves with it.

**Expected contribution if everything works:** the field gains what it currently lacks — a way to be wrong. That is the precondition for it becoming a science.

---

# Part II — Principles of Learned Computation

*The companion program: assume Part I succeeded, forget methodology, and aim at laws of neural computation rather than tools for describing networks.*

## Framing the Counterfactual

If Grounded Interpretability succeeds, the field can decompose networks and *know* when the decomposition is right: invariant units, faithfulness scores with error bars, mechanism-level claims that predict behavior. That is a complete **descriptive** science — natural history with validated microscopes. What it does not contain is a single **law**. It answers "what is this network doing?" for any given network, and remains silent on "why do trained networks do things like *this* at all?" The analogy: Part I gets the field from Tycho to Kepler's data tables. The questions below are the Kepler-to-Newton step — and they remain open even if every interpretability method works perfectly, because they are questions about neural computation itself, not about our access to it.

## The Deepest Unsolved Conceptual Questions

**Q1 — The origin of structure: why is learned computation organized at all?**
Among the astronomically many parameter settings that fit the training data, SGD reliably selects solutions with reusable subcircuits, abstraction hierarchies, and sparse-ish modular structure — the very properties that make interpretability possible. Nothing in the optimization objective asks for this. Implicit simplicity bias of the parameterization? The compositional structure of natural data imprinting itself? An unrecognized variational principle? A perfected descriptive science can *verify* structure everywhere and still have no idea why structure exists. This is interpretability's anthropic question; an answer would be the field's second law of thermodynamics.

**Q2 — The correspondence question: does data determine computation?**
Is the learned mechanism, up to a suitable equivalence, a *function of the data-generating process* — with architecture merely selecting the encoding? Universality findings (induction heads everywhere) are the empirical shadow; the Natural Abstraction Hypothesis is the informal folklore version. Nobody has made it quantitative: a map from properties of the distribution (latent causal sparsity, hierarchy depth, compositional statistics) to the computational motifs any sufficiently trained predictor must contain. If such a map exists, interpretability inverts — read the data, predict the circuits. If it doesn't, every mechanistic analysis is forever a case study.

**Q3 — The theory of computation in superposition.**
Networks compute on overcomplete, mutually interfering codes, through dozens of nonlinear layers, and the interference does not compound catastrophically. Why not? Where is the error correction? What are the capacity limits — how many ε-reliable sub-computations fit in width *d* and depth *L*? Superposed analog computation with learned error tolerance is a genuinely new model of computation that has no Shannon. Coding theory, compressed sensing, and vector-symbolic architectures are the adjacent bodies of math waiting to be conscripted.

**Q4 — Symbol emergence: how does continuous substrate implement discrete structure?**
Binding, variables, roles and fillers, recursion — the machinery of symbolic computation demonstrably runs inside transformers ("the red ball beside the blue cube" rarely suffers binding errors), implemented in vector arithmetic. Is there a small canonical set of binding mechanisms SGD discovers — tensor-product-like codes, rotation/phase binding, attention-as-pointer — and what determines which one arises? The forty-year connectionism-versus-symbols war has its empirical resolution sitting inside trained models, undissected.

**Q5 — What is a forward pass, semantically?**
Is inference-time computation amortized Bayesian inference — a posterior update compiled into weights? In-context learning behaves like *learning*, and there are results suggesting gradient-descent-like updates implemented in activation space. When do fixed weights contain a learned optimizer? Stripped of its safety framing: what class of *processes* — inference, search, optimization, simulation — can a single forward pass implement, and which does pretraining actually select?

**Q6 — Developmental laws: is structure formation governed by universal transitions?**
Grokking, emergent capabilities, sudden circuit crystallization — training seems punctuated rather than gradual. Singular learning theory supplies candidate order parameters; nobody has a predictive theory. The sharp version: given data distribution and architecture, predict *before training completes* which mechanisms will form, in what order, at what point. A yes turns training from alchemy into chemistry.

**Q7 — Is there a macroscopic state theory — a thermodynamics of trained networks?**
Weights are microstates; behavior is the macrostate; interpretable structure sits somewhere between. What are the state variables? Physics became powerful when it stopped tracking molecules and found temperature and pressure. The analogous move — a small set of order parameters determining a network's computational phase, with "dark matter" as the disordered remainder — doesn't exist even in outline.

**Q8 — What is memory, computationally?**
Facts are stored at some measurable capacity (empirical estimates hover around a few bits per parameter), skills are stored otherwise, and the memorization–generalization boundary behaves like a phase boundary. What determines the storage format of a given piece of knowledge, and what is retrieval as an algorithm? This is the question beneath hallucination, editing, and unlearning — all currently engineering on top of an absent theory.

Dependency structure: Q1 and Q7 are the synthesis questions; Q2, Q3, Q4, Q6 are their tractable faces; Q5 and Q8 are semi-independent. That structure dictates the program.

## The Five-Year Program

Aimed at laws rather than tools. It deliberately consumes Part I's outputs as instrumentation, but no project improves a method; every project targets a principle.

### T1 — Capacity Laws for Superposed Computation (years 0–1.5; attacks Q3)

The Shannon move: define the channel (features through interfering superposition, through nonlinearities), prove capacity bounds (reliable sub-computations per parameter at tolerance ε), and identify the error-correction mechanism real trained networks use — the prior is something like interference-averaging plus nonlinear thresholding acting as implicit denoising, but that is a guess the project exists to replace. Foothold: existing computation-in-superposition theory, compressed sensing, expander codes. **Success:** a capacity theorem whose bound is approximately achieved by trained toy models, plus the identified error-correction motif. **Failure mode:** bounds too loose to constrain anything. Goes first because it needs no instruments beyond toy models — pure theory with cheap empirics; can run as a ~20% side channel alongside Part I from year one.

### T2 — The Correspondence Problem (years 1–3; attacks Q2, feeding Q1)

Sweep families of controlled generative processes × architectures × seeds; measure convergence of mechanism using Part I's invariant units (this is where Part I's success is load-bearing — without invariant units, "same mechanism?" is undefined); construct the empirical map from data invariants to computational motifs. **Hypothesis:** mechanism is determined by data structure up to equivalence, with deviations concentrated near T1's capacity boundaries. **Success:** predictive rules validated on held-out generative processes — read the data, predict the circuit. That would be the first genuine law in this field. **Failure:** seed-dominated solution multiplicity, i.e., universality is false — which would permanently cap the ambitions of interpretability and must be published loudly.

### T3 — The Binding Taxonomy (years 2–4; attacks Q4)

Minimal task families forcing variable binding, role assignment, and recursion; dissect the solutions; test against the existing theory shelf (tensor-product representations, holographic reduced representations); determine the conditions selecting each scheme, with T1's capacity lens treating binding schemes as codes. **Success:** a small closed taxonomy of binding mechanisms plus occurrence conditions — the empirical settlement of the connectionist–symbolic question. **Failure:** an unclassifiable zoo, which is evidence *against* Q2's correspondence and feeds back into T2.

### T4 — Developmental Laws (years 3–5; attacks Q6)

Checkpoint archaeology across testbed families and open training-trajectory suites (Pythia, OLMo), with T2's motifs as order parameters and SLT observables as candidate transition coordinates. **Hypothesis:** circuit formation proceeds by transitions whose order and timing are set by data statistics, not initialization. **Success:** preregistered prediction of formation order/timing on unseen runs. Most likely of the five to be independently converged upon by others (the developmental-interpretability community exists) — scheduled where collaboration, not solo priority, is the model.

### T5 — A Variational Principle for Learned Computation (years 4–5+; explicit moonshot; synthesizes Q1/Q7)

The bet: capacity (T1) + correspondence (T2) + development (T4) assemble into one statement — something of the shape *trained networks converge toward minimal-description machines for the data's latent structure, subject to capacity constraints* — an MDL/free-energy-style law with quantitative, falsifiable consequences. Deliverable: the principle stated formally plus three preregistered predictions tested. Even a failed unification that shows *where* the pieces refuse to fit would define the next decade's agenda.

## The Comparison: Which Program Wins the Decade?

Treat the two programs as probability distributions over scientific impact.

**Grounded Interpretability: high floor, bounded ceiling.** Probability of major usable contribution: ~60–70%. The field demonstrably needs every deliverable; results arrive steadily; nothing depends on a conjecture being true. But its ceiling is *instrumental* greatness — "made interpretability a cumulative science." The faithfulness calculus is calorimetry; the testbeds are the telescope. Instrument-builders are indispensable, and history mostly files them under "enabled" rather than "discovered." There is also a decay term: audits of 2026's methods depreciate as methods change (the formalism layer persists; the empirical audits don't).

**Principles of Learned Computation: low floor, unbounded ceiling.** Probability that ten years yields at least one result deserving the word "law": ~10–25% — T2's correspondence result the most plausible candidate, T1's capacity theorem the runner-up. Most theory programs die politely. But conditional on success: a data→computation correspondence law or a real capacity theorem is durable in a way nothing in Part I is. It survives every model generation, every architecture cycle, every methods fashion, and would be cited for fifty years, in fields beyond ML. The tail is plausibly 10–100× Part I's ceiling.

Run the expectation: if tail probability ≥ ~15% and tail magnitude ≥ ~10×, PLC dominates in expected field-level impact; both conditions are plausible. **Direct answer: the Principles program has the greater expected scientific impact over the next decade.** Two corrections change what to actually do:

**Correction 1 — the programs are not independent alternatives; the comparison hides a conditional.** PLC's success probability is *conditional on Part I's instruments existing*. Run PLC cold — no invariant units, no validated testbeds — and T2 is not merely harder, it is *undefined*: "did two networks learn the same mechanism?" has no meaning without a representation-invariant notion of mechanism. Cold-start PLC is maybe a 5% program, and 5% × huge loses to 65% × substantial. The expected-impact ordering *reverses* depending on whether the instrument base exists. This is the oldest pattern in science: Kepler's laws were impossible without Tycho's tables; thermodynamics waited on calorimetry; molecular biology waited on crystallography — and the laws were captured disproportionately by the people standing closest to the instruments. Part I's projects are secretly Part II's data collection: P1's phase diagrams *are* capacity measurements (T1's empirics); P1's data-ontology-versus-model-ontology divergence *is* T2's central phenomenon; P2's invariant units *are* T2 and T4's order parameters. This is one program whose descriptive phase matures into its theoretical phase.

**Correction 2 — expectation is not the sole criterion for a single researcher.** A field should fund PLC-shaped bets; portfolio logic favors heavy tails when you hold many tickets. A single researcher holds one ticket, and a decade of theory work with nothing to show is career-terminating and produces zero impact. Variance matters when you cannot diversify across selves. The one exception built into the design: T1 needs no instruments and no permission, so it runs as a side channel from year one without betting the career.

**Verdict, unhedged.** Greater expected impact over the decade: **the Principles program — conditional on being launched from a working instrument base, which is exactly what Grounded Interpretability builds.** Unconditionally, and for this researcher specifically: run the sequence. Years 0–3, Part I is the plan of record with T1 as the standing theory side channel; at year 3, if the invariant-unit and testbed results are real, rotate the program's center of mass into Part II (T2 first — the law most likely to exist) and let Part I continue as the reliable publication and credibility line. If forced to pick exactly one and run it exclusively from today: Part I, without hesitation — a two-thirds chance of making a field cumulative beats a one-in-twenty chance at a law stated without instruments. The deepest way to say it: **Grounded Interpretability is how one earns the right to attempt the Principles program with real odds, and the Principles program is why Grounded Interpretability is worth doing.** Kepler needed Tycho. The plan is to be both.

---

## Sources

- [APD — Interpretability in Parameter Space (arXiv:2501.14926)](https://arxiv.org/abs/2501.14926)
- [SPD — Stochastic Parameter Decomposition (arXiv:2506.20790)](https://arxiv.org/abs/2506.20790)
- [Apollo Research — parameter-space interpretability](https://www.apolloresearch.ai/research/interpretability-in-parameter-space-minimizing-mechanistic-description-length-with-attribution-based-parameter-decomposition/)
- [MIB: A Mechanistic Interpretability Benchmark (arXiv:2504.13151)](https://arxiv.org/html/2504.13151v1)
- [InterpBench (arXiv:2407.14494)](https://arxiv.org/pdf/2407.14494)
- [BlackboxNLP 2025 Shared Task findings (arXiv:2511.18409)](https://arxiv.org/pdf/2511.18409)
- [AxBench (arXiv:2501.17148)](https://arxiv.org/abs/2501.17148)
- [Anthropic — open-sourcing circuit tracing](https://www.anthropic.com/research/open-source-circuit-tracing)
