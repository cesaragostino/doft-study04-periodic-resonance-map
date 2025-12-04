# Study 04 v2 – DOFT-ATOM Layer Inference Engine

**Version:** 2.0 (with refined topologies and noise model)

---

## 0. Operational Goal

Reformulate Study 04 as a **layered inverse-engineering engine**:

> Given what we measure “outside” in superconductors (DOFT primes, N, structural noise), infer, for each carrier element, the most plausible resonant topology of the orbital layer L1.

So:

- We **no longer** look for weak correlations with `s/p/d/f` blocks.
- We now want to assign, per element:

  - an **L1 topology** (“internal oscillator type”),  
  - consistent with:
    - its prime fingerprint  
      `e⃗ = (e2, e3, e5, e7)`,
    - its lock behavior `N / δN`,
    - its structural noise `ξ`.

**Main final script:**

```bash
python run_study04_infer_topologies.py
```

---

## 1. DOFT-ATOM Layer Architecture

### 1.1. L0 – Inertial Core (`Layer0Core`)

- **Physical name:** Inertial anchor  
- **Meaning:** Stable nuclear / subatomic structure.

**Variables:**

- `element` (symbol, e.g. `"Fe"`)
- `Z` (atomic number)
- `Omega0` (implicit base frequency, if used)

**Assumptions:**

- Not fitted in Study 04.
- Does not generate primes; only sets the energy scale.
- In code: L0 is a parameter, not an optimization variable.

---

### 1.2. L1 – Orbital / Geometric Modulator (`Layer1Orbital`)

- **Physical name:** Geometric modulator  
- **Meaning:** Electronic configuration seen as a network of coupled sub-oscillators.

**Variables:**

- `topology_id` ∈ discrete catalog (see §2)
- `n_nodes` (number of oscillators)
- `connectivity_pattern` (implicit in the topology)
- `eta1` (L0→L2 transmission efficiency, 0–1, optional)

**Associated observables:**

- DOFT prime vector:

  `e⃗ = (e2, e3, e5, e7)`

- Internal L0–L1 lock quality: `LockQuality_L1`  
  (in practice, inferred from N/δN at the L2 level).

**Key idea:** L1 is the **only source of primes**.  
The simulator tries to choose an L1 topology that explains `e⃗`, `N` and `ξ` simultaneously.

---

### 1.3. L2 – Lattice / Cluster Layer (`Layer2Lattice`)

- **Physical name:** Collective interface  
- **Meaning:** Layer that couples the atom to the environment (lattice, cluster).  
  This is what we already measure in Studies 02/03.

**Observed variables:**

- `Fm` – DOFT mother frequency
- `N` – apparent participation number
- `delta_N = |N − round(N)|`
- `xi_ext` – structural noise / residual error

**Role:** L2 distorts what comes from L1 according to the environment.

- If the lock is good, the atom is “transparent”.
- If the lock is poor, it amplifies noise.

---

## 2. Discrete Catalog of L1 Topologies

To make the inverse problem tractable, L1 is **not** an arbitrary graph, but one of a few resonant prototypes with well-separated prime patterns.

**Catalog file:**

```text
data/raw/layer1_topology_catalog.json
```

Each entry has:

- `topology_id`
- `name`
- `n_nodes`
- `w2, w3, w5, w7` (normalized pattern vector)
- `noise_sensitivity ∈ (0, 1]`

### 2.1. Pattern vectors `w⃗_T` (refined)

We always work with the normalized vector `w⃗_T` such that:

`sum_n |w_n| = 1`.

#### `BIN_DIPOLE`

- **name:** Binary dipole  
- `n_nodes = 2`  
- **Meaning:** almost purely binary oscillator (mode 2).

**Pattern (recommended):**

`w⃗_BIN = (0.90, 0.05, 0.03, 0.02)`

- `noise_sensitivity ≈ 0.2` (not very sensitive to mismatch).

---

#### `TRI_RING`

- **name:** Triangular ring  
- `n_nodes = 3`  
- **Meaning:** strong triangular mode (3 dominates).

**Pattern:**

`w⃗_TRI = (0.10, 0.80, 0.05, 0.05)`

- `noise_sensitivity ≈ 0.4`.

---

#### `TETRA_PACK` (renamed from “square” to emphasize 3D)

- **name:** Tetra-pack (3D 4-node structure)  
- `n_nodes = 4`  
- **Meaning:** simple 3D geometry, with strong binary component and some 3.

**Suggested pattern (2 dominant, 3 non-negligible):**

`w⃗_TETRA = (0.60, 0.30, 0.05, 0.05)`

- `noise_sensitivity ≈ 0.5`.

---

#### `PENTA_FLOWER`

- **name:** Penta flower  
- `n_nodes = 5`  
- **Meaning:** structure associated to a complex d-like orbital; 5 dominates.

**Pattern:**

`w⃗_PENTA = (0.35, 0.10, 0.45, 0.10)`

- `noise_sensitivity ≈ 0.7`.

---

#### `HEPTA_FLOWER`

- **name:** Hepta flower  
- `n_nodes = 7`  
- **Meaning:** very complex structure (f-like); 7 dominates.

**Typical pattern:**

`w⃗_HEPTA = (0.30, 0.05, 0.25, 0.40)`

- `noise_sensitivity ≈ 0.9` (very sensitive to incompatibilities).

All these values are fixed in the JSON.  
In v2 they are **not** tweaked ad-hoc by looking at results; if changed, that must be documented as a new catalog version.

---

## 3. Input Data and Aggregation by Carrier

### 3.1. Input files

We reuse outputs from Studies 01–03:

```text
data/processed/config_fingerprint_summary.csv
    material_name, family, e2, e3, e5, e7, Fm, ...

data/processed/structural_noise_summary.csv
    material_name, xi_ext, error_metrics, ...

data/processed/participation_summary.csv
    material_name, N, ...

data/raw/element_carrier_assignments.csv
    material_name, carrier_element, include_study04, category, ...
```

---

### 3.2. Preparation script (Iteration 0)

**Script:**

```bash
python prep_study04_layer_data.py
```

**Tasks:**

- Read the files above.
- Apply QC filters:
  - `include_study04 == 1`
  - valid fingerprints (no NaN, not all zeros)
- Group by `carrier_element`.

For each carrier element `E`:

- `n_materials_E`
- `abs_e2_mean_E, ..., abs_e7_mean_E`  
  (using `|e_n|`; optionally store medians as well)
- `abs_e2_std_E, ...` (dispersion)
- `N_median_E`, `delta_N_median_E` (median of `|N − integer|`)
- `xi_ext_median_E`
- Optional: raw lists for deeper analysis.

**Output:**

```text
data/processed/carrier_aggregate_stats.csv
```

---

## 4. Outward Model

### 4.1. Prime part (L1 → observed fingerprint)

For each carrier `E` with `|e2|, ..., |e7|`:

```python
v = np.array([abs_e2, abs_e3, abs_e5, abs_e7])
v_sum = v.sum()
v_norm = v / v_sum if v_sum > 0 else [0.25, 0.25, 0.25, 0.25]
```

We call this normalized carrier prime vector:

`ẽ⃗_E = v_norm`.

For each topology `T` with pattern `w⃗_T`:

```text
C_e(E, T) = || ẽ⃗_E − w⃗_T ||²
```

(L2 norm in R⁴).

---

### 4.2. Lock / noise part (L1 + environment → distortion)

First define carrier-level normalized magnitudes.

**Macroscopic lock:**

For each material:

```text
delta_N = |N − round(N)|
```

For each carrier: `delta_N_median_E`.

Globally: `delta_N_min`, `delta_N_max` (over all valid carriers).

Normalize:

```text
Q_lock_E = 1 − (delta_N_E − delta_N_min) / (delta_N_max − delta_N_min)
```

clipped to `[0, 1]`.

- `Q_lock ≈ 1` → very integer-like lock.
- `Q_lock ≈ 0` → very fractional lock.

**Structural noise:**

For each carrier: `xi_ext_median_E`.  
Globally: `xi_min`, `xi_max`.

Normalize:

```text
xi_norm_E = (xi_ext_E − xi_min) / (xi_max − xi_min)
```

clipped to `[0, 1]`.

---

**Noise cost `C_ξ`:**

Refined physical hypothesis:

- More complex topologies (`noise_sensitivity_T` large) are heavily penalized when:
  - lock is bad (`Q_lock` low), **and**
  - observed noise is high.

Instead of a global quadratic form, we use a multiplicative form:

```text
C_xi(E, T) = xi_norm_E * noise_sensitivity_T * (1 − Q_lock_E)
```

So:

- If `xi_norm` is large, `noise_sensitivity_T` is large (PENTA/HEPTA), and `Q_lock` is low → `C_xi` is very large → topology is implausible.
- If `xi_norm` is small (clean material) or `Q_lock ≈ 1` → `C_xi` is small even for complex topologies.

---

### 4.3. Total cost

Define:

```text
C_total(E, T) = C_e(E, T) + λ * C_xi(E, T)
```

with a fixed `λ` (e.g. `lambda_noise = 0.5` or `1.0`).

We can store `lambda_noise` in a small config file:

```text
data/raw/study04_hyperparams.json
```

---

## 5. Topology Assignment per Carrier

### Iteration 1 – Pure geometric matching (primes only)

**Script:**

```bash
python run_study04_infer_topologies_e_only.py
```

**Steps:**

- Load:
  - `carrier_aggregate_stats.csv`
  - `layer1_topology_catalog.json`

- For each carrier `E` and topology `T`:
  - compute `C_e(E, T)`.

- Assign:

```text
best_topology_e_only = argmin_T C_e(E, T)
C_e_min              = min_T C_e(E, T)
```

**Output:**

```text
data/processed/carrier_topology_assignments_e_only.csv
```

with columns:

- `carrier_element, Z, block`
- `n_materials`
- `best_topology_e_only`
- `C_e_min`
- `C_e_all` (optional serialized scores)

**Visualizations:**

- Periodic map colored by `best_topology_e_only`.
- Quick boxplots: distribution of topologies by `s/p/d/f` block.

This is the first inspection:  
> Do primes *alone* already align P, D, F with different topologies?

---

### Iteration 2 – Full matching (primes + lock + noise)

**Main script:**

```bash
python run_study04_infer_topologies.py
```

**Steps:**

- Load:
  - `carrier_aggregate_stats.csv`
  - `layer1_topology_catalog.json`
  - hyperparameters (`lambda_noise`)

- Compute for all carriers:
  - `Q_lock_E`, `xi_norm_E`.

- For each `E, T`:

  - `C_e(E, T)` as before  
  - `C_xi(E, T) = xi_norm_E * noise_sensitivity_T * (1 − Q_lock_E)`  
  - `C_total(E, T) = C_e + λ * C_xi`

- Assign:

```text
best_topology = argmin_T C_total(E, T)
C_total_min   = min_T C_total(E, T)
```

**Output:**

```text
data/processed/carrier_topology_assignments.csv
```

Suggested columns:

- `carrier_element, Z, block`
- `n_materials`
- `Q_lock, xi_norm`
- `best_topology_e_only, C_e_min`
- `best_topology, C_total_min`
- `C_e_best, C_xi_best` (for that topology)
- `ranked_topologies` (top-3 or top-5, e.g.  
  `"PENTA_FLOWER:0.12;TETRA_PACK:0.18;BIN_DIPOLE:0.25"`)

---

## 6. Key Visualizations

Beyond periodic maps:

### 6.1. Periodic map by topology

- Axis: standard periodic table (Z, group, period).
- Cell color: `best_topology`  
  (categorical palette: Bin, Tri, Tetra, Penta, Hepta).
- Optional: thicker borders for elements with high `n_materials` (more reliable data).

---

### 6.2. Lock vs noise scatter colored by topology

- X-axis: `delta_N_median_E` or `(1 − Q_lock)`.
- Y-axis: `xi_ext_median_E` or `xi_norm`.
- Color: `best_topology`.

This should show, for example, whether elements with very complex topologies concentrate where lock is difficult / noise is high.

---

### 6.3. “Confusion” matrix: Element vs Topology

Important plot you suggested:

- X-axis: elements (`carrier_element`), grouped by `s/p/d/f` block (with clear separators).
- Y-axis: topologies (`BIN_DIPOLE`, `TRI_RING`, `TETRA_PACK`, `PENTA_FLOWER`, `HEPTA_FLOWER`).

For each pair `(E, T)`, draw:

```text
match_score(E, T) = 1 − normalized_C_total(E, T)
```

Where, for each `E`:

```text
C_hat(E, T) = (C_total(E, T) − C_min(E)) / (C_max(E) − C_min(E) + eps)
match_score = 1 − C_hat ∈ [0, 1]
```

Visual interpretation:

- Bright cells = good match for that `(E, T)`.

Expected pattern (if the model is meaningful):

- p-block aligned with `BIN_DIPOLE` / `TETRA_PACK`,
- d/f brighter in `PENTA_FLOWER` / `HEPTA_FLOWER`.

**Suggested output file:**

```text
figures/study04/fig04_element_topology_match_matrix.png
```

---

## 7. Null Models (optional but recommended)

To avoid “decorative” criticism:

**Script:**

```bash
python run_study04_null_models.py
```

Two simple nulls:

### 7.1. Topology permutation

- Fix `e⃗_E`, `Q_lock_E`, `xi_norm_E`.
- Randomly permute `topology_id ↔ (w_T, noise_sensitivity_T)` among topologies.
- Recompute the distribution of `C_total_min` per element.

Check if the real assignment yields a significantly lower mean `C_total_min` than permutations.

---

### 7.2. Random pattern vectors

- Replace `w⃗_T` by random vectors on S³ (norm = 1).
- Repeat matching and compare.

**Output:**

```text
data/processed/study04_null_stats.json
```

---

## 8. Programmer Summary (short version)

**Iteration 0**  
`prep_study04_layer_data.py`

- Input: fingerprints, N, ξ, carriers.  
- Output: `carrier_aggregate_stats.csv`.

**Iteration 1**  
`run_study04_infer_topologies_e_only.py`

- Input: `carrier_aggregate_stats.csv`, `layer1_topology_catalog.json`.  
- Output: `carrier_topology_assignments_e_only.csv`, periodic map (primes only).

**Iteration 2**  
`run_study04_infer_topologies.py`

- Input: aggregates + catalog + hyperparameters.  
- Output:
  - `carrier_topology_assignments.csv`
  - periodic maps
  - lock/noise scatter
  - element–topology matrix  
    (`fig04_element_topology_match_matrix.png`)
