# Gemma-3 12B SAE steer/ablate tool -- operator guide

PI deliverable #4. Interactive Gradio demo over the 9 verified D2.1
features (`interplab.interventions.hooks._make_clamp_hook`, layer 31,
SAE `gemma-scope-2-12b-pt-res` / `layer_31_width_16k_l0_medium`). Runs
inside a Tamia interactive allocation -- compute nodes have no outbound
internet, so this never fetches a model, an SAE, or a Neuronpedia snippet
at runtime.

## One-time setup (login node, has internet)

`gradio` is not in `pyproject.toml` (this tool is out-of-chain, same as
the sweep and necessity harnesses) and is not yet in `~/sprint-venv`.
Install it once, from the **login node**:

```bash
module load StdEnv/2023 python/3.11 arrow/25.0.0
source ~/sprint-venv/bin/activate
pip install gradio
```

Also pre-stage the two local data files the tool reads (never fetched at
runtime):

- `results/gemma3_sweep/feature_manifest.json` -- regenerate any time with:
  ```bash
  python -c "from scripts.legacy.gemma3_sweep import write_feature_manifest; write_feature_manifest('results/gemma3_sweep')"
  ```
  (pure Python, no GPU, no network -- safe to run on the login node).
- `results/gemma3_sweep/gemma3_tool_snippets.json` -- top-16 example
  snippets per feature, schema `{"<idx>": ["snippet", ...]}` for each of
  the 9 feature indices in `feature_manifest.json`. **Not yet staged as of
  2026-08-08** (Engineer 1 is fetching it separately, gated on verifying
  the Neuronpedia source resolves to the exact SAE this tool uses). If
  it's missing, the tool still runs -- the feature browser shows "example
  snippets not yet pre-staged" for every feature instead of failing.

## Every demo session: two commands

**1. On the login node, from the repo root** -- requests the allocation
and launches the tool, attached to your terminal:

```bash
bash slurm/legacy/launch_gemma3_tool.sh \
  /scratch/y/yazid/hf_cache/hub/models--google--gemma-3-12b-pt/snapshots/<rev> \
  /scratch/y/yazid/hf_cache/hub/models--google--gemma-scope-2-12b-pt/snapshots/<rev>
```

Wait for the allocation, then watch for two lines in your terminal:

```
gemma3_tool running on node: <NODE>
...
Running on local URL: http://127.0.0.1:7860
```

Leave this terminal attached for the whole demo -- Ctrl-C here ends the
session and releases the allocation.

**2. From your own laptop** (not the login node) -- opens an SSH tunnel
through the login node to the compute node's Gradio port, substituting
`<NODE>` from step 1's output:

```bash
ssh -L 7860:<NODE>:7860 yazid@tamia.alliancecan.ca
```

Leave that SSH session open too, then browse to `http://127.0.0.1:7860`
on your laptop.

## What the UI shows

- Feature picker over the 9 verified features (label, density,
  maxActApprox, example snippets).
- Mode: steer / ablate.
- Dose as a multiple of the feature's own `maxActApprox`
  ({0.5, 1, 2, 4, 8, 16}), with the resulting absolute clamp value shown
  alongside it. `maxActApprox` is labelled in the UI as a **sample-max
  proxy over Neuronpedia's activation set, not a corpus max** -- the same
  wording as the sweep's own caveat, never just "max activation."
- Baseline (unhooked), target feature (hooked), and a random-feature
  control (on by default, same dose, a fixed feature drawn once via
  `control_rng_seed=1337` -- the same seed and exclusion set the D2.1
  sweep itself uses) generated side by side from the same prompt and seed.

## Prerequisites this tool assumes are already true

- `HF_HUB_OFFLINE=1` is set by the payload script before Python starts;
  `scripts/legacy/gemma3_sweep.py`'s `load_model_and_sae()` refuses to run
  otherwise.
- `--model-path` / `--sae-path` are local snapshot directories already
  staged under `/scratch/.../hf_cache`, never a `repo_id`.
- No `HF_TOKEN` in the environment -- the payload script unsets it, and
  this tool never needs one (an interactive allocation carries no
  credential by the project's own SLURM_JOB_ID-conditional guard).
