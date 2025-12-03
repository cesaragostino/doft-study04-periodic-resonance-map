# DOFT Study 04 – Periodic Resonance Map

Build and analyze a DOFT Resonance Periodic Table where each carrier element is assigned a prime vector
`(|e2|, |e3|, |e5|, |e7|)` aggregated from curated DOFT fingerprints. The pipeline ingests a single
carrier-assignment CSV, aggregates fingerprints at the element level, runs the s/p/d/f statistical
tests (including null models), and produces both tabular outputs and figures.

## What this repo contains
- Specs for Study 04 in `docs/`.
- Curated input example: `data/raw/element_carrier_assignments.csv`.
- Main runner: `run_study04_periodic_map.py`.
- Processing utilities: `study04/` (aggregation, stats, nulls, plots).
- Outputs land in `data/processed/` (CSV/JSON/PNG).

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the study
```bash
python run_study04_periodic_map.py \
  --config data/raw/element_carrier_assignments.csv \
  --n-min 2 \
  --prime-metric mean \
  --n-perm 5000 \
  --n-rotations 0
```

Key flags:
- `--n-min` controls the robustness filter `n_materials >= N_min` (spec recommends 2–3; the sample data has only 1 per element, so use `--n-min 1` to reproduce the example outputs).
- `--prime-metric` chooses `mean` or `median` for the prime vector.
- `--n-perm` permutations for the block-label null (default 5000).
- `--n-rotations` random prime-space rotations (set >0 to run the optional null; default skips).

## Main outputs (data/processed/)
- `periodic_resonance_table.csv`: element-level aggregation (n_materials, block, Z/group/period if provided, prime means/medians/std).
- `atomic_resonance_matrix.csv`: correlation between block one-hots and prime magnitudes.
- `study04_block_stats.json`: Mann–Whitney + Cliff’s Δ for Tests 1–2, classifier metrics for (s+p) vs (d+f), permutation + rotation null summaries.
- `resonance_periodic_table.png`: resonance periodic map (dominant prime color, intensity by magnitude).
- `figures/prime_boxplots.png`, `figures/prime_scatter.png`, `figures/classifier_roc.png`, `figures/materials_hist.png`.

## Notes and assumptions
- Study 04 **does not** recompute carrier assignments; it trusts the curated CSV columns `carrier_element` and `carrier_block`.
- Absolute values of fingerprints are used (`|e_n|`), per spec.
- Classification uses logistic regression with cross-validation (LOO when samples are small) and reports accuracy/balanced accuracy/ROC-AUC vs a majority baseline.
- Null model 1 permutes block labels; null model 2 rotates prime space with random orthogonal matrices.

## Data expectations
Input CSV schema (minimum):
```
name,formula,category,carrier_element,carrier_block,carrier_Z,include_study04,
e2,e3,e5,e7,notes
```
Extra columns like `carrier_group` and `carrier_period` are optional but used for plotting if present.
