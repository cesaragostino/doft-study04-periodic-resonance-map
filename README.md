# DOFT Study 04 – Periodic Resonance Map

Build and analyze a DOFT Resonance Periodic Table where each carrier element is assigned a prime vector
`(|e2|, |e3|, |e5|, |e7|)` aggregated from curated DOFT fingerprints. The pipeline ingests a single
carrier-assignment CSV, aggregates fingerprints at the element level, runs the s/p/d/f statistical
tests (including null models), and produces both tabular outputs and figures.

## What this repo contains
- Specs for Study 04 in `docs/`.
- Curated input example: `data/raw/element_carrier_assignments.csv`.
- Main runner: `run_study04_periodic_map.py`.
- Processing utilities: `src/study04/` (aggregation, stats, nulls, plots).
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

QC runs automatically at start; to just verify data you can run the same command with `--n-perm 0 --n-rotations 0` to skip heavy nulls and stop if any included material has errors.

Key flags:
- `--n-min` controls the robustness filter `n_materials >= N_min` (spec recommends 2–3; the sample data has only 1 per element, so use `--n-min 1` to reproduce the example outputs).
- `--prime-metric` chooses `mean` or `median` for the prime vector.
- `--n-perm` permutations for the block-label null (default 5000).
- `--n-rotations` random prime-space rotations (set >0 to run the optional null; default skips).

## Main outputs (data/processed/)
- `fingerprint_qc_per_material.csv`: per-material QC flags (errors/warnings) for included rows.
- `fingerprint_qc_summary.json`: aggregated QC counts.
- `periodic_resonance_table.csv`: element-level aggregation (n_materials, block, Z/group/period if provided, prime means/medians/std).
- `atomic_resonance_matrix.csv`: correlation between block one-hots and prime magnitudes.
- `study04_block_stats.json`: Mann–Whitney + Cliff’s Δ for Tests 1–2, classifier metrics for (s+p) vs (d+f), permutation + rotation null summaries.
- `resonance_periodic_table.png`: resonance periodic map (dominant prime color, intensity by magnitude).
- `figures/prime_boxplots.png`, `figures/prime_scatter.png`, `figures/classifier_roc.png`, `figures/materials_hist.png`.

## Notes and assumptions
- Study 04 **does not** recompute carrier assignments; it trusts the curated CSV columns `carrier_element` and `carrier_block` (recomputed `include_study04` plus QC checks happen before aggregation).
- `include_study04` is recalculated deterministically: allowed categories (SC_Binary, SC_HighPressure, SC_IronBased, SC_Oxide, SC_TypeI, SC_TypeII, SC_HeavyFermion), valid carrier element/block, and non-null/non-zero fingerprints; exclusions log to console with reasons.
- Absolute values of fingerprints are used (`|e_n|`), per spec.
- Classification uses logistic regression with cross-validation (LOO when samples are small) and reports accuracy/balanced accuracy/ROC-AUC vs a majority baseline.
- Null model 1 permutes block labels; null model 2 rotates prime space with random orthogonal matrices.
- Set `PYTHONPATH=src` (or install as a package) if you add new scripts so they can import `study04`.

## Data expectations
Input CSV schema (minimum):
```
name,formula,category,carrier_element,carrier_block,carrier_Z,include_study04,
e2,e3,e5,e7,notes
```
Extra columns like `carrier_group` and `carrier_period` are optional but used for plotting if present.

## Study 04 v2 – Layer Inference Engine
Prep, match topologías y figuras nuevas:

```bash
python prep_study04_layer_data.py
python run_study04_infer_topologies_e_only.py
python run_study04_infer_topologies.py
```
- Input esperados: `data/raw/config_fingerprint_summary.csv`, `data/raw/element_carrier_assignments.csv`, `data/raw/structural_noise_summary.csv`, `data/raw/participation_summary.csv`, catálogo `data/raw/layer1_topology_catalog.json`, hiperparámetros `data/raw/study04_hyperparams.json` (`lambda_noise=0.5`).
- Outputs clave: `data/processed/carrier_aggregate_stats.csv`, `carrier_topology_assignments_e_only.csv`, `carrier_topology_assignments.csv`, figuras en `data/processed/figures/study04/`.
- Consola muestra INCLUDED/EXCLUDED, warnings y resumen QC/topologías para seguir el cálculo en tiempo real.

## Study 04 – Atom Resonant Layer Engine (L1 inverso)
Nuevo runner para el motor de capas con filtro por carrier o familia:

```bash
python3 run_study04_resonant_layer_engine.py --elements Fe,Ni --families d f
# o todos
python3 run_study04_resonant_layer_engine.py
```
- Entrada: `data/processed/carrier_aggregate_stats.csv` (sale de `prep_study04_layer_data.py`).
- Catálogo: `data/raw/layer1_topology_catalog.json`.
- Hiperparámetros: `data/raw/study04_hyperparams.json` (sigma_e, sigma_N, sigma_xi, lambda_N, lambda_xi, xi_env).
- Salidas: `data/processed/element_topology_scores.csv`, `data/processed/element_topology_inference.csv`, figuras en `data/processed/figures/study04/topology_map_resonant.png` y `element_topology_match_matrix_resonant.png`.
- Usa `--elements` (coma o espacio) y/o `--families` (s/p/d/f) para elegir qué carriers correr; `all` o vacío corren todo.
