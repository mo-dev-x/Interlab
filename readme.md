# qwen-sae-interp

Mechanistic interpretability of Qwen2.5-14B using Sparse Autoencoders (SAEs).  
Reproducing and extending the feature steering experiments from Templeton et al. (2024) *Scaling Monosemanticity*.

## Overview

This project trains a Sparse Autoencoder on the residual stream of Qwen2.5-14B, identifies interpretable monosemantic features, and validates them causally via activation steering — reproducing the "Golden Gate Bridge" style experiment on an open-weight model.

**Part of a broader internship project** on mechanistic interpretability at [IID](https://https://web.iid.ulaval.ca/), covering:
- SAE training and feature extraction
- Circuit tracing and induction head identification  
- Cross-architecture feature stability analysis
- Anomaly detection via feature distribution comparison

## Structure

```
qwen-sae-interp/
├── configs/           # SAELens training configs (.yaml)
├── data/
│   └── raw/           # Cached activation datasets (gitignored)
├── notebooks/         # Exploration, feature dashboards, figures
├── results/
│   ├── features/      # Feature analysis outputs
│   ├── steering/      # Steering experiment results
│   └── plots/         # Figures for writeup
├── scripts/
│   ├── collect_activations.py
│   ├── train_sae.py
│   ├── find_features.py
│   └── steering_experiment.py
└── slurm/             # SLURM job scripts for Alliance cluster
```

## Setup

**On Alliance Canada clusters:**
```bash
module load python/3.11
virtualenv --no-download ~/sae-interp
source ~/sae-interp/bin/activate
pip install --no-index torch torchvision
pip install -r requirements.txt
```

**Local (conda):**
```bash
conda env create -f environment.yml
conda activate sae-interp
```

## Quickstart

```bash
# 1. Collect activations from Qwen2.5-14B
python scripts/collect_activations.py --config configs/collect.yaml

# 2. Train SAE
python scripts/train_sae.py --config configs/sae_train.yaml

# 3. Find interpretable features
python scripts/find_features.py --sae_path results/sae_checkpoint.pt

# 4. Run steering experiment
python scripts/steering_experiment.py --feature_id <id> --scale 20
```

## Key References

- Bricken et al. (2023) — [Towards Monosemanticity](https://transformer-circuits.pub/2023/monosemantic-features)
- Templeton et al. (2024) — [Scaling Monosemanticity](https://transformer-circuits.pub/2024/scaling-monosemanticity)
- Ameisen et al. (2025) — [Circuit Tracing](https://transformer-circuits.pub/2025/attribution-graphs)
- [SAELens](https://github.com/jbloomAI/SAELens) — SAE training library

## Cluster

Training runs on Alliance Canada clusters (H100/H200 via TamIA, A100 via Narval).  
See `slurm/` for job scripts.