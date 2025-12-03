# Study 04 – Periodic Resonance Map (extended spec)

## 0. Operational goal

Build and analyze a DOFT Resonance Periodic Table where each chemical element has a prime-vector

`e = (|e2|, |e3|, |e5|, |e7|)`

and test whether that vector is statistically aligned with the standard electronic structure (s/p/d/f blocks), **without** relying on superconductivity properties or on ad-hoc tuning in the analysis code.

Main script:

```bash
python run_study04_periodic_map.py
```

The script should:

* Read a single configuration/data file prepared from previous studies.
* Aggregate DOFT fingerprints by carrier element.
* Perform statistical tests vs. s/p/d/f blocks.
* Generate a Resonance Periodic Table and summary statistics.

---

## 1) Data inputs

### 1.1. Element–carrier assignments + fingerprints (single config file)

Study 04 uses a single CSV as input:

```text
data/raw/element_carrier_assignments.csv
```

This file is prepared from the outputs of Study 01 / Study 02 (e.g. from
`materials_clusters_real_v7.csv` and `config_fingerprint_summary.csv`), but Study 04 does **not** depend on those files directly. It only needs this CSV.

Each row corresponds to one material (elemental or compound) and encodes:

* how DOFT fingerprints for that material are assigned to a carrier element, and
* whether the material should be included in Study 04.

Minimal columns (recommended schema):

```text
name,formula,category,
carrier_element,carrier_block,carrier_Z,
include_study04,
e2,e3,e5,e7,
notes
```

Where:

* **name** (string, required)
  Unique material identifier, e.g. `Pb`, `FeSe`, `LaH10`.
  Must match the name used in previous studies (e.g. in `materials_clusters_real_v7.csv`).

* **formula** (string, recommended)
  Chemical formula, e.g. `Pb`, `FeSe`, `LaH10`.
  For very complex/organic materials where a parser would fail, can repeat `name`.

* **category** (string, optional)
  Family/category (e.g. `SC_Binary`, `SC_TypeII`, `SC_IronBased`, `SC_Molecular`, `Superfluid`, etc.).
  Useful if you want to filter whole categories (e.g. exclude `SC_Molecular`).

* **carrier_element** (string, required for included rows)
  Chemical symbol of the element considered as the main carrier in that material.

  Examples:

  * `Pb` for Pb
  * `Sn` for Sn
  * `Fe` for FeSe
  * `La` for LaH10
  * `Nb` for Nb3Sn

  For rows with `include_study04 = 0`, this can be left empty.

* **carrier_block** (string, required for included rows)
  One of: `s`, `p`, `d`, `f`.

  Examples: `Pb → p`, `Sn → p`, `Fe → d`, `Nb → d`, `La → f`.

* **carrier_Z** (integer, optional but useful)
  Atomic number of the carrier element (82 for Pb, 26 for Fe, etc.).
  Used only for optional checks/plots, not required for the core tests.

* **include_study04** (0 or 1, required)

  * `1` = use this material in Study 04.
  * `0` = ignore this material (e.g. organic superconductors, superfluid He, or anything you choose to exclude).

  The script must always filter to `include_study04 == 1` before doing any aggregation.

* **e2, e3, e5, e7** (float, required)
  DOFT fingerprint components for this material (as computed in Study 01 / 02).
  They may have sign; Study 04 will work with their absolute values `|e_n|`.

* **notes** (string, optional)
  Free-text comments (e.g. `elemental SC`, `high-pressure hydride`, `organic, excluded`).

> **Important:** The selection of `carrier_element` and `carrier_block` is done outside Study 04 (by you / upstream code) following a fixed rule. Study 04 takes this CSV as given and does **not** recompute carrier assignments.

---

## 2) Step A – Carrier selection (documented, but NOT implemented here)

Although Study 04 does not recompute carriers, we document the recommended rule used to build `element_carrier_assignments.csv`, for reproducibility.

Recommended hierarchy to choose `carrier_element` for a material with formula:

1. If the compound contains at least one **f-block** element →
   `carrier =` the f-block element with the highest atomic fraction.

2. Else, if it contains any **d-block** element →
   `carrier =` the d-block element with the highest atomic fraction.

3. Else, if it contains any **p-block** element →
   `carrier =` the heaviest p-block element (largest `Z`).

4. If all else fails →
   `carrier =` the heaviest element in the compound.

**Tie-breaker:**

If the hierarchy and atomic fraction are the same (e.g. Nb–Ti alloy, both d-block with same fraction),
→ choose the element with larger `Z` (heavier).

**Doping rule:**

If there is explicit doping (e.g. `La₁₋ₓYₓH₁₀`) and the dopant level is low (< 10%), you may ignore the dopant when choosing the carrier.

But: Study 04 does **not** re-implement this. It just uses the columns `carrier_element` and `carrier_block` from `element_carrier_assignments.csv`. The rule is here as documentation so anyone can regenerate the CSV if needed.

---

## 3) Step B – Aggregating fingerprints by element

Goal: move from **per material** to **per carrier element**.

### 3.1. Build element-level table

Load:

```text
data/raw/element_carrier_assignments.csv
```

Filter rows:

* Keep only rows with:

  * `include_study04 == 1`
  * non-empty `carrier_element` and `carrier_block`.

For each `carrier_element` **E**:

* `n_materials` = number of materials where **E** is the carrier (`include_study04 == 1`).

Compute for each prime `n ∈ {2,3,5,7}`:

* Mean of `|e_n|`: `e2_mean`, `e3_mean`, `e5_mean`, `e7_mean`.
* Median of `|e_n|`: `e2_median`, `e3_median`, `e5_median`, `e7_median`.
* Standard deviation: `e2_std`, `e3_std`, `e5_std`, `e7_std`.

For each element **E**, take:

* `block = carrier_block` (must be the same for all rows of that element; if not, raise an error).
* `Z` = e.g. `carrier_Z` from any row (or the median if you include it redundantly).

Save the aggregated element table to:

```text
data/processed/periodic_resonance_table.csv
```

Minimal columns:

* `element` – carrier element symbol.
* `block` – `s`, `p`, `d`, `f`.
* `Z` – atomic number (optional but recommended).
* `n_materials` – number of materials contributing.
* `e2_mean`, `e3_mean`, `e5_mean`, `e7_mean`.
* `e2_median`, `e3_median`, `e5_median`, `e7_median`.
* `e2_std`, `e3_std`, `e5_std`, `e7_std`.

### 3.2. Robustness filter

For the main statistical analyses, define a minimum number of materials per element:

* Choose a fixed `N_min` (recommended: `N_min = 2` or `3`).
* For “strong” results, only use elements with:

  ```text
  n_materials >= N_min
  ```

Elements with `n_materials == 1` can be kept for visualization but should be excluded from the core stats.

---

## 4) Step C – Statistical tests vs s/p/d/f blocks

All the analysis can live in:

```text
notebook/04_periodic_resonance_analysis.ipynb
```

or an equivalent script.

### 4.1. Define the working dataset

Load:

```text
data/processed/periodic_resonance_table.csv
```

Filter to elements with:

```text
n_materials >= N_min
```

For each element, define the prime vector (using means or medians, to be chosen and fixed in advance):

```text
e = (|e2|, |e3|, |e5|, |e7|)
```

(e.g. `( |e2_mean|, |e3_mean|, |e5_mean|, |e7_mean| )`).

### 4.2. Test 1 – p vs d/f in |e2|

**Hypothesis:** p-block elements have larger `|e2|` than (d + f), and weaker higher primes.

Groups:

* `G_p  = { elements with block == "p" }`
* `G_df = { elements with block in ["d", "f"] }`

Metrics:

* Mann–Whitney U test on `|e2|`: `p_value_e2_p_vs_df`.
* Cliff’s Δ (effect size) for `|e2|` between `G_p` and `G_df`.
* Also compare `|e5|` and `|e7|` in the opposite direction (expect smaller in `G_p`).

Save summary results to:

```text
data/processed/study04_block_stats.json
```

(Include group sizes, Δ, p-values, etc.)

### 4.3. Test 2 – Higher primes in d/f vs s/p

**Hypothesis:** d/f-block elements have `|e5|` and `|e7|` larger than s/p.

Groups:

* `G_low  = { block in ["s", "p"] }`
* `G_high = { block in ["d", "f"] }`

Metrics:

* Mann–Whitney U + Cliff’s Δ for `|e5|`.
* Mann–Whitney U + Cliff’s Δ for `|e7|`.

Again, store results in `study04_block_stats.json`.

### 4.4. Test 3 – Block classification from primes

Define two classification problems:

1. **Binary:** low-complexity vs high-complexity

   * `low  =` blocks `s + p`
   * `high =` blocks `d + f`

2. **(Optional) Multiclass:** if enough elements, try to classify `s/p/d/f` separately.

Model input:

```text
e = (|e2|, |e3|, |e5|, |e7|)
```

Simple models:

* Binary logistic regression, or
* k-NN with `k = 3` or `5`.

Pipeline:

* Use cross-validation (e.g. leave-one-out or 5-fold, given the small number of elements).
* Compute metrics:

  * Accuracy
  * Balanced accuracy
  * ROC-AUC (for the binary case)

Baseline:

* An “always-majority” classifier (always predicting the most common class).

Compare real accuracy vs baseline distribution.

---

## 5) Step D – Null models (to avoid “mathematical artifact”)

### 5.1. Null 1 – Permuting blocks across elements

Keep fixed:

* The prime vectors `e` per element.

Randomize:

* Permute block labels across elements, preserving the global counts of `s/p/d/f`.

**Procedure:**

For `N_perm` iterations (e.g. 5000):

1. Randomly permute block labels among elements.
2. Recompute:

   * Cliff’s Δ for Tests 1 and 2,
   * Classification accuracy for Test 3.

Build null distributions for each metric.

Compare real metrics vs null:

* Compute z-score.
* Compute empirical p-value (fraction of null samples with metric as extreme or more than the real one).

This directly addresses: *“maybe any random labelling of blocks would give similar stats”*.

### 5.2. Null 2 – Random rotations of prime space (optional but strong)

Idea: is `{2,3,5,7}` a special basis, or would any 4D basis show similar alignment?

**Procedure:**

1. Generate random orthogonal 4×4 matrices `R` (random rotations in 4D).

2. For each rotation, transform the prime vectors:

   ```text
   e' = R e
   ```

3. Redo Tests 1–3 using `e'` instead of `e`.

Inspect whether the real `{2,3,5,7}` basis gives systematically stronger alignment than typical random bases.

If the block correlation disappears (or is strongly reduced) under most rotations, that supports the idea that the prime basis is not just an arbitrary 4D coordinate system artifact.

---

## 6) Step E – Visualizations and final outputs

### 6.1. Resonance Periodic Table

Generate:

```text
data/processed/periodic_resonance_map.png
```

A standard periodic-table layout where each element cell shows its resonance fingerprint.

For each element:

* **Color** = dominant prime index `(2,3,5,7)`, e.g. color-coding by `argmax(|e2|,|e3|,|e5|,|e7|)`.
* **Saturation or intensity** = magnitude of the dominant component or norm `||e||`.

Optional but recommended:

* Mini **stacked bars** or mini **pie chart** in each cell indicating the relative weights of `|e2|`, `|e3|`, `|e5|`, `|e7|`.

This makes elements like Pb (single dominant prime) visually distinct from Fe (mixed primes).

### 6.2. Other figures

* Boxplots of `|e2|`, `|e5|`, `|e7|` by block (`s`, `p`, `d`, `f`).
* 2D scatter plots (e.g. `|e5|` vs `|e2|`) colored by block.
* ROC curve(s) for the binary classifier (`s+p` vs `d+f`).
* Optionally, histograms of `n_materials` per element.

All plots should be reproducible from the element-level table:

```text
data/processed/periodic_resonance_table.csv
```

---

## 7) How to minimize the “mathematical artifact” criticism

Key practices:

### 7.1. Fixed rules, no post-hoc tuning

* The carrier assignments and `include_study04` flags are fixed in `element_carrier_assignments.csv`.
* Study 04 does **not** change carriers based on results.
* Hypotheses and tests (sections 4.2–4.4) are predefined and limited in number.

### 7.2. Explicit null models

* Permuting block labels and rotating prime space directly tests whether the observed alignment is special or generic.
* Null distributions + empirical p-values show whether the effect is beyond what random structure would give.

### 7.3. Effect sizes, not just p-values

* Always report Cliff’s Δ, accuracy vs baseline, etc.
* Avoid overinterpreting small p-values with tiny `N`.

### 7.4. Control for obvious confounders

* Optionally check whether effects persist within restricted ranges of `Z` or specific families.
* Ensure that any signal is not trivially driven by a single family or a single outlier element.

### 7.5. Honest wording in the paper

* Do not claim a strictly proven “Correspondence Law”.

* A more accurate formulation is:

  > "We find a statistically significant alignment between DOFT prime fingerprints and the s/p/d/f block structure of the carrier elements."

* The idea of using this for inverse design (engineering resonances) belongs in the **Discussion / Outlook** section, not in the core claims of Study 04.
