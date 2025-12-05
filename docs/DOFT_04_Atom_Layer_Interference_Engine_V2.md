# Study04-ATOM — Atomic-Only Topology Inference

## 0. Operational Goal

Build a version of Study04 that:

- Uses **only pure elemental materials** (single chemical element).
- Constructs, for each element `E`, a set of **“clean” observables**:

  - Mean `|e2|, |e3|, |e5|, |e7|`
  - Mean `N`, mean `xi_ext`
  - Lock / noise metrics

- Runs the **topology inference engine** only on those elements.
- Produces **atomic tables and plots**, not a global “resonance periodic table” (that comes later, if this looks solid).

---

## 1. Filtering Rule: What Is an “Elemental Material”?

The entire pipeline must share a **single definition** of “elemental”.

### 1.1. Main rule (with explicit formula)

If `materials_clusters_real_v7.csv` has a formula column (e.g. `formula`):

- Use `pymatgen.core.Composition`.

A material is **elemental** if:

```python
from pymatgen.core import Composition

comp = Composition(formula_string)
is_elemental = (len(comp.elements) == 1)
```

The **carrier element symbol** is taken as:

```python
element_symbol = comp.elements[0].symbol
```

---

### 1.2. Fallback (no formula, only name)

If there is **no formula** column, use a name-based heuristic:

A row in `element_carrier_assignments.csv` is marked as `is_elemental = 1` if **all** of these hold:

- `material_name == carrier_element`  
  (e.g.: Pb, Sn, Al, V, Nb, Ta, …).
- `len(material_name) <= 3`  
  (to avoid things like FeSe, YBCO, etc.).
- `material_name` is in the list of known element symbols (Z = 1..92).
  - i.e. hard-code a symbol list or use `mendeleev`.

Everything else is marked `is_elemental = 0`.

---

### 1.3. Exclusion Log

Every script that applies this filter must:

- Print to stdout something like:

```text
[STUDY04-ATOM] Excluding non-elemental material: FeSe (carrier Fe)
[STUDY04-ATOM] Excluding non-elemental material: YBa2Cu3O7 (carrier Cu)
...
```

- Optional: save to `study04_atom_excluded_materials.csv`:

```text
material_id,material_name,carrier_element,reason
...
```

---

## 2. New Preparation Script (Atomic-Only)

### 2.1. Script

```bash
python prep_study04_atomic_layer_data.py
```

### 2.2. Inputs

- `data/processed/config_fingerprint_summary.csv`
- `data/processed/participation_summary.csv`  
  (N per material)
- `data/processed/structural_noise_summary.csv`  
  (`xi_ext` per material)
- `data/raw/element_carrier_assignments.csv`  
  (contains `material_name`, `carrier_element`, and current include flag)
- `materials_clusters_real_v7.csv`  
  (for formula or metadata, if needed)

### 2.3. Steps

1. **Merge by `material_id`**: fingerprints + N + ξ + carrier.
2. Apply existing QC (`included == 1`, valid primes, etc.).
3. Apply new **atomic filter** (Section 1) → `is_elemental`.
4. Filter: keep only `is_elemental == 1`.
5. Aggregate by `carrier_element`:

   For each element `E`:

   - `n_materials_elemental`  
     (how many elemental rows were used; typically 1, but if multiple phases exist they are averaged).
   - `e2_mean, e3_mean, e5_mean, e7_mean` (over `|e_n|`).
   - `N_mean, N_std`.
   - `xi_mean, xi_std`.
   - `lock_mean` (for example, mean of `exp(-|N − round(N)|)`).
   - `block, Z`, etc. (join with an element table if you already have one).

6. Save to:

   ```text
   data/processed/carrier_aggregate_stats_atomic.csv
   ```

**Minimal fields:**

```text
carrier_element, Z, block,
n_materials_elemental,
e2_mean,e3_mean,e5_mean,e7_mean,
N_mean,N_std,
xi_mean,xi_std,
lock_mean
```

---

## 3. Topology Inference Engine (Atomic Version)

### 3.1. Script

```bash
python run_study04_atomic_layer_inference.py
```

### 3.2. Inputs

- `data/processed/carrier_aggregate_stats_atomic.csv`
- `data/raw/layer1_topology_catalog.json`  
  (definition of topologies + pattern vectors `w_T` + `noise_sensitivity_T`)
- `data/raw/study04_hyperparams.json`

Hyperparameters:

- `lambda_noise` (start at 0.5)
- `lambda_lock` (if you add an extra lock term)

---

### 3.3. Per-element Computations (for each `E`)

For each element in `carrier_aggregate_stats_atomic`:

1. **Build normalized prime vector:**

   ```text
   e⃗_E = (|e2|, |e3|, |e5|, |e7|)
   e⃗_E_norm = e⃗_E / (||e⃗_E||₁ + ε)
   ```

2. **Normalize noise:**

   ```text
   xi_norm,E = min(1, xi_mean / xi_ref)
   ```

   where `xi_ref` is some high percentile (e.g. 90%) of `xi`.

3. **Define lock quality** (if not already precomputed):

   ```text
   Q_lock,E = exp(-|N_mean − round(N_mean)|)
   ```

4. For each topology `T` in the catalog:

   - **Prime/geometric cost:**

     ```text
     C_e(E, T) = || e⃗_E_norm − w_T ||²
     ```

   - **Noise cost:**

     ```text
     C_xi(E, T) = xi_norm,E * noise_sensitivity_T * (1 − Q_lock,E)
     ```

   - **Total cost:**

     ```text
     C_total(E, T) = C_e(E, T) + lambda_noise * C_xi(E, T)
     ```

   - **Match score:**

     ```text
     match(E, T) = exp(−C_total(E, T))
     ```

5. **Save all `T` scores** to:

   ```text
   data/processed/element_topology_scores_atomic.csv
   ```

   with columns:

   ```text
   carrier_element, topology, C_e, C_xi, C_total, match_score
   ```

6. **Winning topology:**

   ```text
   T*_E = argmax_T match(E, T)
   ```

7. Save per-element summary to:

   ```text
   data/processed/element_topology_inference_atomic.csv
   ```

   with columns:

   ```text
   carrier_element, Z, block,
   n_materials_elemental,
   e2_mean,e3_mean,e5_mean,e7_mean,
   N_mean,xi_mean,lock_mean,
   best_topology, best_match_score
   ```

---

## 4. Recommended Outputs (Atomic Version)

No full periodic table for now; just very readable, atom-centric views:

1. **Summary table**  
   (the CSVs above) → basis for any paper / report.

2. **Element vs topology heatmap** (only atomic elements used):

   - X-axis: topologies
   - Y-axis: elements
   - Color: `match_score`

3. **Per-element barplot of primes**:

   - Bars for `|e2|, |e3|, |e5|, |e7|`.  
   - Useful to see how “pure” each atom is.

4. *(Optional)* Scatter plot:

   - `|e2|` vs `|e5|`, colored by `best_topology`.

---

## 5. One-line Summary for the Programmer

**Study04-ATOM** = the same topology inference engine you already implemented, but fed **only with pure elemental materials**, aggregated by `carrier_element`, and producing **atom-centric outputs** (`carrier_aggregate_stats_atomic`, `element_topology_scores_atomic`, `element_topology_inference_atomic`), without mixing information from compounds.
