# Technical Specification: DOFT Study 04 – Atomic Resonance & Periodic Map

## Main Objective

Develop a software module that attacks the **“inward”** side of the DOFT model:

- **Inward (Micro):** correlate the prime fingerprints  
  ` (e2, e3, e5, e7)`  
  with the effective electronic structure of the elements (blocks `s, p, d, f`), building a **DOFT Resonance Periodic Table**.

The **“outward”** objectives (the scaling law `N–ξ₀` and a tuning simulator) are explicitly left as **future phases** (Study 05 / Study 06).  
Study 04 implements only the **atomic / resonance** part.

### Expected result of Study 04

A periodic map where each element has a prime vector

`e = (|e2|, |e3|, |e5|, |e7|)`

and statistics that allow us to test whether these vectors are **non-trivially aligned** with the `s / p / d / f` block structure.

### Main script

```bash
python run_study04_periodic_map.py --config data/raw/element_carrier_assignments.csv
```

(The path can be parametric, but by convention the file lives in `data/raw/`.)

---

## 1. Data Sources (Study 04)

Study 04 does **not** read the raw outputs of Study 01 / Study 02 directly.  
Instead, it uses a single curated input file:

### 1.1. Element–Carrier Assignment File (`element_carrier_assignments.csv`)

Default path:

```text
data/raw/element_carrier_assignments.csv
```

Each row represents a superconducting material (elemental or compound) for which Study 01 / 02 already computed the DOFT fingerprints. In this file we fix:

- which element acts as **carrier** in that material, and  
- whether that material is used or not in Study 04.

**Recommended column schema:**

```text
name,formula,category,
carrier_element,carrier_block,carrier_Z,
include_study04,
e2,e3,e5,e7,
notes
```

- **name** (required):  
  Name of the material, same as the first column of `materials_clusters_real_v7.csv`.  
  Examples: `Pb`, `Sn`, `FeSe`, `LaH10`.

- **formula** (recommended):  
  Chemical formula of the material (e.g. `Pb`, `FeSe`, `LaH10`).  
  For exotic organics, `formula` can be the same as `name`.

- **category** (optional):  
  Family (e.g. `SC_Binary`, `SC_TypeII`, `SC_Oxide`, `SC_Molecular`, `Superfluid`, etc.).

- **carrier_element** (required if `include_study04 == 1`):  
  Element considered as the “carrier” (e.g. `Pb`, `Fe`, `La`, `Nb`).

- **carrier_block** (required if `include_study04 == 1`):  
  Electronic block of the carrier (`s`, `p`, `d`, `f`).

- **carrier_Z** (optional):  
  Atomic number of the carrier.

- **include_study04** (0/1, required):  
  - `1` → use this material in Study 04.  
  - `0` → ignore it (very complicated organics, superfluid He, etc.).

- **e2, e3, e5, e7** (required):  
  DOFT fingerprints of the material (copied from `config_fingerprint_summary.csv`).

- **notes** (optional):  
  Free-text comments.

> **Important:** The logic for defining `carrier_element` and `include_study04` is fixed **outside** Study 04 (from a previous script or manual curation).  
> Study 04 **does not recalculate carriers**; it only uses whatever is in this CSV.

---

## 2. Module A – Atomic Resonance Profiler (Micro)

**Goal:** Test whether the effective internal structure of the element (block `s / p / d / f`) leaves a **statistical footprint** in the DOFT fingerprints  
`(e2, e3, e5, e7)`.

### 2.1. Computation Logic

#### 1) Read material-level data

- Load: `data/raw/element_carrier_assignments.csv`.
- Filter rows with:
  - `include_study04 == 1`
  - non-empty `carrier_element` and `carrier_block`.

#### 2) Build element-level table (atomic level)

- Group by `carrier_element`.

For each element:

- `n_materials`: number of materials where that element acts as carrier.

For each prime `n ∈ {2, 3, 5, 7}`:

- `e{n}_mean`  = mean of `|e_n|` over those materials.  
- `e{n}_median` = median of `|e_n|`.  
- `e{n}_std`   = standard deviation of `|e_n|`.

Output file:

```text
data/processed/periodic_resonance_table.csv
```

**Minimal columns:**

```text
element,block,Z,n_materials,
e2_mean,e3_mean,e5_mean,e7_mean,
e2_median,e3_median,e5_median,e7_median,
e2_std,e3_std,e5_std,e7_std
```

#### 3) Robustness filter

- Define `N_min` (e.g. 2 or 3).
- For “strong” statistical analyses, use **only** elements with:

  ```text
  n_materials >= N_min
  ```

Elements with `n_materials == 1` can be kept for plots but should be excluded from core tests.

#### 4) Block ↔ Primes cross-correlation

On the element-level table (`periodic_resonance_table.csv`):

- Compare **p-block vs d/f-block** in `|e2|`.
- Compare **(s+p) vs (d+f)** in `|e5|` and `|e7|`.
- Train a simple classifier (logistic regression or k-NN) to distinguish  
  `(s+p)` vs `(d+f)` using:

  `(|e2|, |e3|, |e5|, |e7|)`

Save metrics to:

```text
data/processed/study04_block_stats.json
```

(Include group sizes, Mann–Whitney p-values, Cliff’s Δ, accuracies, baseline, etc.)

### 2.2. Graphical / File Outputs

- **`atomic_resonance_matrix.csv`**  
  Correlation matrix between:
  - binary variables encoding blocks (`s`, `p`, `d`, `f`), and  
  - prime magnitudes (`|e2_mean|, |e3_mean|, |e5_mean|, |e7_mean|`).

  This acts as a tabular summary of the “inward” hypothesis.

- **`resonance_periodic_table.png`**  
  Periodic-table-style visualization:
  - each cell (element) colored by dominant prime (`argmax(|e2|,|e3|,|e5|,|e7|)`),
  - intensity proportional to `||e||` or `|e_dom|`.

  Optional:
  - mini internal bars showing the relative composition of the four primes.

- Other recommended plots:
  - Boxplots of `|e2|`, `|e5|`, `|e7|` by block (`s/p/d/f`).
  - Scatter plot `|e5|` vs `|e2|` colored by block.
  - ROC curve of the classifier (s+p vs d+f).

---

## 3. Null Models (to avoid “mathematical artifacts”)

To ensure the result is not just a numerical trick, the module must implement **explicit null models**:

### Null 1 – Block permutation

- Keep the element vectors `e` **fixed**.
- Randomly permute the block labels (`s/p/d/f`) across elements, preserving the global count of each block.

Repeat `N` times (e.g. 5000) and recompute:

- Cliff’s Δ for the Block↔Primes tests.
- Classifier accuracy (s+p vs d+f).

Result: null distributions of Δ and accuracy.  
Compare the real values against these (z-score, empirical p-value).

### Null 2 – Random rotations in prime space (optional but strong)

- Generate random orthogonal matrices `R` of size 4×4.
- Transform `e → e' = R e`.
- Repeat the Block↔Primes tests and the classification using `e'`.

If the correlation disappears under typical rotations, but is strong in the prime basis `{2,3,5,7}`, that supports the idea that the structure is **not** a generic artifact of a 4D space.

---

## 4. Future Phases (NOT implemented in Study 04)

To preserve your original ideas without mixing them into the current code scope, they are explicitly left as **Study 05 / Study 06**.

### 4.1. Module B – Confinement Validator (Study 05)

Requires a new experimental database:

```text
data/raw/experimental_geometry.csv
```

with columns:

```text
material_name, coherence_length_xi0_nm,
penetration_depth_lambda_nm (optional),
lattice_parameter_a_nm
```

It proposes a power-law fit:

`xi0_pred = A · (N_corrected)^β`

Training on the subset with measured `xi0`, computing MAPE, etc.

This module is **not** implemented in Study 04; it is reserved for a dedicated Study 05 on the `N–xi0` relationship.

### 4.2. Module C – Tuning Simulator (Study 06)

Simulate how `N` and the distance to the nearest integer

`d = |N − round(N)|`

change under doping or composition changes.

Requires modeling changes in `Θ_D`, `f_base`, etc.

This is also explicitly **out of scope** for Study 04 and is material for a future Study 06 / appendix.

---

## 5. Notes for the Programmer

- **Main input:**  
  `data/raw/element_carrier_assignments.csv`  
  Do **not** assume fixed paths to `config_fingerprint_summary.csv` or `materials_clusters_real_v7.csv`; those are used only to generate the input CSV.

- **Main outputs:**
  - `data/processed/periodic_resonance_table.csv`
  - `data/processed/atomic_resonance_matrix.csv`
  - `data/processed/study04_block_stats.json`
  - `data/processed/resonance_periodic_table.png`
  - (and optional extra plots in `data/processed/figures/`)

- **Reproducibility:**
  - All “hard” decisions (carrier assignment, include/exclude) are encoded in the **input CSV**.
  - Study 04 code must **not** change carriers based on results.
  - The tests and null models must be runnable end-to-end using only:
    - the CSV input, and
    - a `requirements.txt`.

first commit