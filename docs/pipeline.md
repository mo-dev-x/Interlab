# Pipeline Reference — Qwen2.5-14B SAE Interpretability

This document describes every step of the project end-to-end. It serves as the authoritative reference for what each script does, what concepts it relies on, and what its inputs/outputs are. Claude Code should consult this before writing or modifying any script.

---

## CURRENT SPRINT DIRECTIVE (Week 1-2)

**Two objectives, one infrastructure. Do not build anything extra for objective 2 — it rides on objective 1.**

### Objective 1 — Replicate the Golden Gate Experiment (poutine version)
Train SAE on Qwen2.5-14B → find a poutine feature → steer the model → ablate the feature → document results. This is Steps 1-5 below. This is the deliverable for the PI.

### Objective 2 — Seed the Multilingual Paper (zero extra infrastructure)
While running Step 3 (feature identification), also run probe datasets in **French, Mandarin, and Arabic** for the same concepts. This means:

- When searching for the poutine feature using English probe sentences, also run equivalent probe sentences in French ("La meilleure poutine que j'ai mangée était à La Banquise"), Mandarin (describing poutine / Québécois food), and Arabic (same).
- Record which features fire for each language. Save the activation data.
- Note whether the **same feature** fires across languages (shared multilingual feature) or whether **different features** fire per language (language-specific encoding).
- Do the same for 2-3 other concepts beyond poutine: pick concepts that exist across all four languages (e.g., "hockey", "winter/snow", "university/education"). Run probe sentences in all four languages for each concept.

**This adds ~30 minutes of work to Step 3** (writing probe sentences in 3 extra languages and running them through the same pipeline). It does NOT require new scripts, new configs, or new infrastructure. The output is saved to `results/features/multilingual/` and becomes the seed dataset for the NeurIPS 2026 workshop paper on multilingual feature geometry.

### What NOT to do right now
- Do not build circuit tracing infrastructure (Step 6) — that's post-sprint
- Do not train SAEs on LLaMA yet (Step 7) — that's post-sprint
- Do not work on the anomaly detection method (Step 8) — that's the PhD student collaboration, starts after replication is solid
- Do not over-engineer the multilingual analysis — just collect the data and note initial observations

---

## Project Goal

Train a Sparse Autoencoder on Qwen2.5-14B's residual stream, identify an interpretable feature corresponding to **poutine** (the Québécois dish), and demonstrate causal influence by steering the model to talk about poutine in unrelated contexts — reproducing the "Golden Gate Bridge" experiment from Templeton et al. (2024) on an open-weight model.

---

## Model Details

- **Model:** `Qwen/Qwen2.5-14B`
- **Architecture:** Transformer decoder, 40 layers, hidden dim 5120, 40 attention heads
- **Precision:** bfloat16
- **Target layer for SAE:** layer 24 (mid-late — where abstract semantic features tend to emerge)
- **Hook point:** residual stream post-MLP (after the feedforward block, before the next layer's attention)

---

## Step 1 — Activation Collection

**Script:** `scripts/collect_activations.py`
**Config:** `configs/collect.yaml`
**SLURM:** `slurm/collect_activations.sh`

### What it does
Runs Qwen2.5-14B in inference on a large text corpus. At layer 24, hooks intercept the residual stream activation (a 5120-dimensional vector per token) and save them to disk.

### Key concepts

- **Residual stream:** The shared representation vector that flows through all transformer layers. Each attention and MLP block reads from it and writes an additive update back to it. This is the natural place to look for concept representations because it carries the cumulative information the model has built up.
- **Hook point choice:** We hook after the MLP (post-feedforward) at layer 24. Early layers (~0-10) encode surface features (syntax, token identity). Mid-late layers (~20-30) encode abstract semantic concepts. Layer 24 out of 40 is in the sweet spot for finding concept-level features like "poutine."

### Inputs
- Qwen2.5-14B model weights (downloaded from HuggingFace, cached in `$SCRATCH/hf_cache`)
- Text corpus: `monology/pile-uncopyrighted` from HuggingFace Datasets
- Context length: 512 tokens per sequence

### Outputs
- Activation tensors saved to `data/raw/` as `.pt` files
- Shape per batch: `(batch_size * seq_len, 5120)`
- Target: collect activations for ~200M tokens total

### Implementation notes
- Use `transformers` model with a forward hook registered on the target layer
- Process in batches to fit in GPU memory (Qwen 14B in bf16 ≈ 28GB VRAM for weights alone)
- SAELens can handle activation collection natively via its `ActivationsStore` — prefer this over a custom implementation for consistency with the training step
- Save to disk incrementally, don't accumulate in RAM

---

## Step 2 — Train the Sparse Autoencoder

**Script:** `scripts/train_sae.py`
**Config:** `configs/sae_train.yaml`
**SLURM:** `slurm/train_sae.sh`

### What it does
Trains a TopK Sparse Autoencoder that learns to decompose each 5120-dim residual stream activation into a sparse combination of ~81,920 learned feature directions.

### Key concepts

- **Superposition:** Qwen's 5120 dimensions encode far more than 5120 concepts. The model packs multiple concepts into overlapping directions in activation space. This means individual neurons are **polysemantic** (one neuron = many concepts) and not directly interpretable.

- **Sparse Autoencoder (SAE):** A single-hidden-layer autoencoder with a much wider hidden layer (81,920 features vs. 5120 input dims). The encoder maps the activation into this overcomplete space, sparsity is enforced so only ~100 features are active per token, and the decoder reconstructs the original activation. The training loss is reconstruction error (MSE between input and output).

- **TopK architecture:** Instead of using an L1 penalty on activations to encourage sparsity (which requires tuning the L1 coefficient and leads to shrinkage), TopK simply keeps the k highest-activation features and zeros out the rest. This gives exact control over sparsity (always exactly k active features) and produces cleaner features. We use k=100.

- **Expansion factor:** Dictionary size = d_in × expansion_factor = 5120 × 16 = 81,920 features. Larger dictionaries can capture finer-grained features but cost more compute and may split features unnecessarily (feature splitting).

- **Why sparsity forces monosemanticity:** If only 100 out of 81,920 features can be active for any token, each feature must specialize. A feature that fires on both "poutine" and "quantum mechanics" would waste one of the precious 100 active slots. The pressure to reconstruct accurately with few active features drives each feature toward encoding one coherent concept.

### Architecture

```
Input x ∈ ℝ^5120
    ↓
Encoder: h = TopK(W_enc @ (x - b_dec) + b_enc, k=100)
    ↓
Hidden: h ∈ ℝ^81920 (sparse, exactly 100 nonzero entries)
    ↓
Decoder: x̂ = W_dec @ h + b_dec
    ↓
Loss: ||x - x̂||²
```

- `W_enc`: (81920, 5120) — encoder weights
- `W_dec`: (5120, 81920) — decoder weights, columns are unit-normalized (each column is a feature direction in activation space)
- `b_enc`: (81920,) — encoder bias
- `b_dec`: (5120,) — decoder bias (learned mean of activations)

### Training hyperparameters
- Learning rate: 2e-4 with cosine schedule
- Batch size: 4096 tokens
- Training tokens: 200M (sufficient for good features, feasible in ~12-18h on H100)
- Optimizer: Adam (β1=0.9, β2=0.999)
- Warmup: 1000 steps

### Inputs
- Activation data from Step 1 (or streamed live from the model via SAELens `ActivationsStore`)
- Config file `configs/sae_train.yaml`

### Outputs
- SAE checkpoint saved to `results/sae_checkpoints/`
- WandB logs (offline mode on cluster, sync later): reconstruction loss, L0 (avg active features), dead feature count
- Final checkpoint includes `W_enc`, `W_dec`, `b_enc`, `b_dec`

### Key metrics to monitor during training
- **Reconstruction loss (MSE):** should decrease steadily. If it plateaus early, the SAE is underfitting (increase k or expansion factor).
- **L0 (average number of active features):** should be exactly k=100 for TopK.
- **Dead features:** features that never activate across the training data. Some are expected (<5% is fine), too many (>20%) means the dictionary is too large or learning rate too high.
- **Explained variance:** what fraction of the activation's variance the SAE captures. Target >95%.

### Implementation notes
- Use SAELens `SAETrainingRunner` — it handles activation streaming, training loop, checkpointing, and WandB logging
- Set `compile_llm: true` on H100 for ~20% speedup via torch.compile
- Point HF cache to `$SCRATCH` to avoid quota issues

---

## Step 3 — Feature Identification

**Script:** `scripts/find_features.py`

### What it does
Searches the 81,920 learned features to find one (or several) that correspond to the concept of **poutine**. Uses two complementary methods: max-activating examples and logit attribution.

### Key concepts

- **Max-activating examples:** For each feature, run a large set of diverse text through the model + SAE and record which tokens cause the highest activation of that feature. If a feature's top-activating tokens cluster around "poutine", "gravy", "cheese curds", "La Banquise", "Québec cuisine" — it's a poutine feature candidate. This is the primary discovery method.

- **Logit attribution (logit lens for features):** Each feature has a decoder direction `W_dec[:, feature_id]` which is a 5120-dim vector. You can project this direction onto the model's unembedding matrix to see which output tokens this feature "pushes toward" when active. If feature #N's decoder direction has high dot product with the unembedding vectors for "poutine", "gravy", "fries", "Québec" — that's convergent evidence it encodes poutine. This is faster than running text through the model and works as a complementary signal.

- **Feature specificity:** A good feature is **monosemantic** — it fires on one coherent concept. A poutine feature that also fires on "pizza" and "tacos" might be a broader "comfort food" feature. A feature that fires only on poutine-related contexts is more specific and more interesting. Both are valid findings — the specificity is part of what you'll report.

### Strategy for finding the poutine feature

1. **Targeted search (fast):** Create a probe dataset of ~100 sentences explicitly about poutine. Run them through model + SAE. Record which features activate most strongly and consistently across these sentences. Rank features by mean activation on the probe set.

2. **Specificity check:** For the top candidate features, also check their activations on unrelated text. A good poutine feature should have high activation on poutine text and low activation on everything else. Compute the ratio (mean activation on poutine text) / (mean activation on general text) — higher is better.

3. **Logit attribution confirmation:** For top candidates, compute the logit attribution and verify it points toward poutine-related tokens.

4. **Manual inspection:** Look at the top-20 max-activating examples for the best candidate. Read them. Do they make sense? This is where human judgment matters.

### Probe dataset (examples of poutine-related sentences)
```
"The best poutine I ever had was at La Banquise in Montreal."
"Cheese curds and gravy over crispy fries — nothing beats it."
"Poutine is the unofficial national dish of Quebec."
"We ordered the classic poutine with brown gravy."
"Every trip to Montreal starts with a stop for poutine."
"The squeaky cheese curds are what make authentic poutine."
"Canadian comfort food at its finest: hot fries, fresh curds, rich gravy."
```
Include ~100 such sentences, varying phrasing, context, and specificity.

### Inputs
- Trained SAE checkpoint from Step 2
- Qwen2.5-14B model
- Probe dataset (poutine sentences) + general text for specificity comparison
- Model's unembedding matrix (for logit attribution)

### Outputs
- `results/features/poutine_candidates.json` — ranked list of candidate feature IDs with activation stats
- `results/features/top_feature_examples.json` — max-activating examples for each candidate
- `results/features/logit_attribution.json` — top logit-attributed tokens per candidate
- `results/plots/feature_activation_histogram.png` — activation distribution: poutine text vs. general text

### Multilingual probe extension (Objective 2)
After identifying poutine feature candidates in English, run the same pipeline with probe datasets in French, Mandarin, and Arabic for:
- **Poutine / Québécois food** — the primary concept
- **Hockey** — culturally specific but globally known
- **Winter / snow** — universal concept, culturally weighted differently
- **University / education** — abstract concept, language-neutral

For each concept × language, record:
- Which feature IDs fire most strongly
- Whether they overlap with the English features for the same concept
- Activation magnitudes per language

Save to `results/features/multilingual/`:
- `multilingual_probe_sentences.json` — all probe sentences organized by concept × language
- `multilingual_feature_activations.json` — feature ID → activation per concept × language
- `multilingual_overlap_matrix.json` — for each concept, which features are shared across languages vs. language-specific

---

## Step 4 — Causal Validation via Steering (The Poutine Experiment)

**Script:** `scripts/steering_experiment.py`

### What it does
Demonstrates that the identified poutine feature **causally** influences model output. Clamps the feature to a high activation value during generation and observes whether the model starts talking about poutine in unrelated contexts.

### Key concepts

- **Feature steering / activation patching:** During the model's forward pass, at the layer where the SAE is trained, you:
  1. Take the residual stream activation `x`
  2. Encode it with the SAE: `h = encode(x)` (sparse, 81920-dim)
  3. Manually set the poutine feature's activation to a high value: `h[poutine_id] = scale`
  4. Decode back: `x_modified = decode(h)`
  5. Replace the original activation with `x_modified` and let the model continue

  The model now generates as if the poutine feature were strongly active, regardless of the actual input.

- **Steering scale:** The multiplier applied to the feature. Too low (1-5x) and the effect is subtle. Too high (50x+) and the output degrades into incoherent repetition. The sweet spot is usually 10-30x the feature's typical activation magnitude. Test multiple scales: [5, 10, 15, 20, 30, 40].

- **Why this proves causality:** Correlation (Step 3) shows the feature activates when poutine is discussed. Steering shows that artificially activating the feature *causes* poutine to appear in the output. This is an intervention experiment — the gold standard for causal claims.

### Experimental setup

**Neutral prompts (should NOT naturally produce poutine-related output):**
```
"Tell me about yourself."
"What is the meaning of life?"
"Describe a typical day in your life."
"What are your thoughts on the weather today?"
"Explain how a car engine works."
"What is your favorite hobby?"
```

**Control conditions:**
1. **Baseline:** Generate from each prompt with no intervention. Verify poutine doesn't appear naturally.
2. **Steered:** Generate from each prompt with the poutine feature clamped at various scales.
3. **Random feature control:** Clamp a random (non-poutine) feature at the same scales. Verify it doesn't produce poutine output. This rules out the possibility that any feature clamping produces the effect.

**Metrics:**
- **Poutine mention rate:** fraction of steered generations that mention poutine, gravy, cheese curds, Quebec food, etc.
- **Coherence:** are the steered outputs grammatically sensible, or garbled? (qualitative + perplexity)
- **Scale curve:** plot poutine mention rate vs. steering scale to find the sweet spot

### Inputs
- Trained SAE checkpoint
- Identified poutine feature ID from Step 3
- Qwen2.5-14B model
- List of neutral prompts
- List of steering scales to test

### Outputs
- `results/steering/generations.json` — all generated text (baseline + steered + control) for each prompt × scale
- `results/steering/metrics.json` — poutine mention rate, coherence scores per scale
- `results/plots/steering_scale_curve.png` — mention rate vs. scale
- `results/plots/example_generations.md` — cherry-picked examples showing the effect clearly

---

## Step 5 — Ablation (Reverse Direction)

**Script:** `scripts/steering_experiment.py` (same script, ablation mode)

### What it does
Tests the opposite direction: when the model is processing text that IS about poutine, clamp the poutine feature to zero and observe whether the model loses the ability to discuss it.

### Key concepts

- **Zero ablation:** Same mechanism as steering, but instead of setting the feature to a high value, set it to exactly 0. If the poutine feature is causally necessary for poutine-related output, ablating it should degrade the model's ability to talk about poutine.

- **Bidirectional causality:** Steering shows the feature is **sufficient** (activating it causes poutine output). Ablation shows it's **necessary** (removing it impairs poutine output). Together, they provide strong causal evidence.

### Experimental setup

**Poutine prompts (should naturally produce poutine-related output):**
```
"What is poutine and where does it come from?"
"Describe the best poutine restaurant in Montreal."
"How do you make authentic Quebec poutine?"
```

**Conditions:**
1. **Baseline:** generate normally — verify the model talks about poutine
2. **Ablated:** generate with poutine feature clamped to 0 — measure how much poutine content is lost
3. **Control ablation:** ablate a random unrelated feature — verify poutine content is preserved

### Outputs
- Added to `results/steering/generations.json` and `results/steering/metrics.json`
- `results/plots/ablation_comparison.md` — side-by-side baseline vs. ablated outputs

---

## Steps 6-8 — Remainder of Summer (Post-Sprint)

These extend beyond the initial 4-day sprint and build on the established SAE infrastructure.

### Step 6 — Circuit Tracing

**Goal:** Map which features in earlier layers activate which features in later layers when the model processes poutine-related text.

**Method:** Attribution patching — perturb a feature in layer N and measure the effect on features in layer N+k. Build a computational graph (circuit) showing how the poutine concept is constructed across layers.

**Key concepts:**
- **Attribution patching:** Run a clean forward pass and a corrupted forward pass (with one feature perturbed). The difference in downstream feature activations tells you the causal contribution of the perturbed feature.
- **Induction heads:** Well-known circuit pattern where attention heads copy tokens that appeared after a similar token earlier in context. Identifying these in Qwen validates the circuit tracing methodology.
- **Computational graph:** A directed graph where nodes are features (at specific layers) and edges are causal influences. This is what Ameisen et al. (2025) produced.

**Expected deliverables:** Interactive circuit visualization, identification of known circuits (induction heads), novel circuits related to poutine or other concepts.

### Step 7 — Cross-Architecture Comparison

**Goal:** Train SAEs on LLaMA (same size range) and compare feature structure.

**Questions to answer:**
- Does LLaMA learn a poutine-like feature?
- Is it at a similar relative layer depth?
- Do the circuits look similar?
- Are there features that appear in both models (convergent representations)?

**Key concept — feature universality:** If different architectures trained on different data learn similar features, this suggests these representations are natural properties of language modeling, not artifacts of one model's training.

### Step 8 — Anomaly Detection (PhD Student's Method)

**Goal:** Apply the lab's novel anomaly detection method (based on comparing feature activation distributions) to automatically identify features associated with target concepts.

**How it connects:** Steps 3 was manual feature identification. This method aims to automate it by comparing the distribution of feature activations on a target corpus vs. a reference corpus and flagging features with statistically significant distributional shifts.

**This is the novel research contribution of the internship** — the earlier steps establish capability, this step applies it to something new.

---

## 4-Day Sprint Schedule

| Day | Focus | Deliverable |
|-----|-------|-------------|
| 1 | Environment setup, model download, activation collection | Activations for 200M tokens saved to disk |
| 2 | SAE training with SAELens | Trained SAE checkpoint, WandB training curves |
| 3 | Feature identification — find the poutine feature | Ranked candidate features with evidence |
| 4 | Steering + ablation experiments, document results | Steered generations, scale curves, ablation results |

---

## File Map

| File | Purpose |
|------|---------|
| `scripts/collect_activations.py` | Step 1 — hook into Qwen, save residual stream activations |
| `scripts/train_sae.py` | Step 2 — train TopK SAE via SAELens |
| `scripts/find_features.py` | Step 3 — identify poutine feature via max-activating examples + logit attribution |
| `scripts/steering_experiment.py` | Steps 4 & 5 — feature steering and ablation experiments |
| `configs/sae_train.yaml` | SAE training hyperparameters |
| `configs/collect.yaml` | Activation collection config |
| `slurm/train_sae.sh` | SLURM job for SAE training |
| `slurm/collect_activations.sh` | SLURM job for activation collection |

---

## Key References

- Elhage et al. (2022) — Toy Models of Superposition. Foundational theory for why superposition exists and how SAEs address it.
- Bricken et al. (2023) — Towards Monosemanticity. First successful SAE applied to a language model (Claude 1). Established the methodology.
- Templeton et al. (2024) — Scaling Monosemanticity. Scaled SAEs to Claude 3 Sonnet. Contains the Golden Gate Bridge steering experiment we are reproducing.
- Ameisen et al. (2025) — Circuit Tracing. Attribution-based circuit discovery using SAE features. The target methodology for Steps 6+.