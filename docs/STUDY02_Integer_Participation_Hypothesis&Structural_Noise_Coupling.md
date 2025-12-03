# Specification: Integer Participation Hypothesis and Structural‑Noise Coupling

This document lays out a comprehensive plan to integrate the integer participation hypothesis into the DOFT simulator. It combines the insights of Study 02 on structural noise with a quantitative framework for analysing the Mother Frequency $F_m$ and its discrete nature. The goal is to provide Codex with clear, testable steps to implement the necessary calculations, data processing and validation routines.

## 1 Hypothesis H1: Integer Participation

**H1 (participation integer).** For each material, the Mother Frequency $F_m = \Theta_D / T_c$ is not arbitrary, but lies close to an integer multiple of a base inertial frequency $f_{base}$:

$$F_m \approx N \times f_{base}, \quad N \in \mathbb{N}$$

where $f_{base}$ is a global constant and $N$ is the effective number of coherent oscillators. The relative error

$$\epsilon_i = \left| \frac{F_{m,i} - N_i f_{base}}{F_{m,i}} \right|$$

is typically smaller than what one would expect from a continuous model. Instead of claiming that inertia itself is quantised, we assert that superconducting clusters prefer discrete coherent sizes.

### 1.1 Calibrating the base frequency

To prevent overfitting, $f_{base}$ must be determined on a subset $A$ of materials where physical intuition suggests a well‑defined cluster size (e.g. high‑pressure hydrides or classical elemental superconductors). The procedure is:

1.  Choose subset $A \subset \{materials\}$ with clear physical interpretation.
2.  Minimise the sum of squared residuals across $A$:

$$L(f) = \sum_{i \in A} \min_{N \in \mathbb{N}} (F_{m,i} - Nf)^2$$

This can be implemented by searching over integer $N$ values near $F_{m,i} / f$ or by a more general maximum‑likelihood estimate if measurement errors are known.

3.  Fix $f_{base}$ to the value that minimises $L$. Do not re‑tune this value when analysing the remaining materials (subset B).

Codex should provide a function `calibrate_f_base(data, subset_indices)` that returns the optimal $f_{base}$.

### 1.2 Computing participation numbers and residuals

Given $f_{base}$, compute for each material $i$:

* $F_{m,i} = \Theta_{D,i} / T_{c,i}$ (already available in the datasets).
* $N_i = F_{m,i} / f_{base}$.
* `nearest_integer_N_i = round(N_i)`.
* `delta_i = N_i - nearest_integer_N_i` (signed distance to nearest integer).
* `abs_delta_i = abs(delta_i)` (absolute distance).

Codex should extend the data structures to include `N_i`, `delta_i` and `abs_delta_i` for each material.

## 2 Assessing the Significance of “Almost Integers”

To show that small `abs_delta_i` values are not random, implement the following statistical checks:

* **Histogram of `abs_delta_i`:** Generate a histogram of absolute deviations (e.g. bin widths of 0.01) and compute the fraction of materials with `abs_delta_i < 0.02`, `<0.01`, etc.
* **Null models:**
    * **Null 1 (shuffle):** Randomly permute the $\Theta_D$ values among materials while keeping $T_c$ fixed; recompute $F_m$, `N_i` and `abs_delta_i` for each permutation. Repeat this process (e.g. 1,000 times) to generate a distribution of near‑integer fractions under the null hypothesis that the pairing of $\Theta_D$ and $T_c$ is random.
    * **Null 2 (continuous):** Sample $F_m$ values from the empirical distribution of $F_m$, or generate a synthetic continuous distribution with the same mean and variance, and compute `abs_delta_i` as above. This tests whether the near‑integer property arises from the observed distribution rather than discrete structure.
* **Compare fractions:** For each threshold (e.g. 0.02, 0.01), compute the fraction of materials in the real dataset with `abs_delta_i` below the threshold and compare it to the fraction observed in the null models. Compute p‑values as the proportion of null simulations that exceed the real fraction. Codex should implement functions to perform these permutations and return summary statistics.

## 3 Linking Integer Participation to Structural Noise (Study 02)

The central question is whether being close to an integer $N$ corresponds to lower structural noise. To test this:

1.  For each material, obtain a measure of structural noise. Possible choices:
    * The absolute log‑residual from Study 01 (e.g. `abs_logres` from the fingerprint summary).
    * The scalar shift parameter $\xi$ or the predicted noise from the vector model.
    * The total loss from the cluster simulator.
2.  Compute `d_i = abs_delta_i` (distance to nearest integer) or, optionally, distance to the nearest magic number if incorporating geometric considerations.
3.  Perform correlation tests (Pearson or Spearman) between `d_i` and the noise metric. Codex should compute correlation coefficients and p‑values.
4.  For qualitative assessment, split materials into percentiles of `d_i` (e.g. lowest 20 % vs. rest) and compare average noise levels. This can be visualised with box plots or summarised numerically.

If materials with small `abs_delta_i` consistently exhibit lower noise, this supports the hypothesis that discrete participation correlates with structural stability.

## 4 Geometric “Magic Numbers”

While intriguing, the connection to specific magic numbers should remain secondary until further validation. As an optional module, Codex can:

1.  Estimate the coherence‑volume participation number $N_{geo}$ for simple elemental metals using published coherence lengths $\xi$ and atomic volumes. For example:
    $$N_{geo} \approx \frac{4\pi\xi^3 / 3}{V_{atom}}$$
2.  Compare the order of magnitude of $N_{geo}$ to $N_i$ derived from $F_m / f_{base}$. Report whether they are of the same scale (e.g. both $\sim 10^2$, $\sim 10^3$).
3.  Identify if any $N_i$ values lie close to canonical icosahedral magic numbers (13, 55, 147, 309, …), but treat this as suggestive. The report should explicitly state that no direct structural identification is being claimed at this stage.

## 5 Falsifiable Predictions and Physical Implications

To elevate the hypothesis beyond descriptive statistics, define testable predictions:

* **Tuning to an integer:** For a material with $N \approx N_0 + \delta$ (e.g. $\delta \approx 0.2$), hypothesise that small perturbations (pressure, doping) that shift $F_m$ so that $N \to N_0$ or $N_0 + 1$ will reduce structural noise (decrease the residual or maximise $T_c$). Codex can assist by plotting $F_m$ as a function of experimental variables (if available) and indicating where integer crossings occur.
* **Family scaling:** Propose that families with larger typical $N$ values (bulk‑like) have lower structural noise and are less sensitive to impurities, whereas families with smaller $N$ show more noise and stronger sensitivity. Test this by grouping materials by family and comparing average $N$, `abs_delta_i` and noise metrics.

These predictions provide criteria that can be checked against existing experimental data or guide future measurements.

## 6 Implementation Notes for Codex

Codex should implement the above procedures as modular functions, integrating seamlessly with the existing DOFT pipeline:

* **Data ingestion:** Use the current CSV files (`materials_clusters_real_v6.csv`, `structural_noise_summary.csv`, etc.) to read $T_c$, $\Theta_D$, and the noise metrics. Accept additional inputs (e.g. coherence lengths, pressures) where available.
* **Base frequency calibration:** Provide a function `calibrate_f_base` that takes a subset index and returns $f_{base}$. Store this value globally and apply it consistently.
* **Participation number computation:** Extend the material configuration class to store `N_i`, `delta_i`, `abs_delta_i`, and (optionally) `nearest_magic_distance`.
* **Null model generation:** Implement functions to generate shuffled $\Theta_D$ arrays and synthetic $F_m$ samples; compute `abs_delta` histograms and significance metrics.
* **Correlation testing:** Provide utilities to compute correlations between `d_i` and structural noise metrics, with options for Pearson or Spearman tests. Include summary tables and plots.
* **Geometric estimation:** Add optional routines to estimate $N_{geo}$ and compare scales. The code should allow the user to pass coherence length and atomic volume data when available.
* **Reporting:** Generate summary reports (CSV and/or Markdown) that include the calibrated $f_{base}$, the distribution of `abs_delta_i`, null model comparison statistics, correlations with noise, and any geometric comparisons. These reports should be integrated into the existing digest mechanisms (`simulator_summary.csv`, etc.).
* **Safety and reproducibility:** Document the version of the dataset used, the subset chosen for calibration, the number of permutations for null models, and any assumptions made (e.g. thresholds for `abs_delta`). This information will be essential for reviewers and future users.

## 7 Available Data and Future Extensions

Currently available data provide:

* $F_m$ (from $\Theta_D$ and $T_c$), coherence lengths for some materials, and structural noise metrics (`logres`, `xi`, `predicted noise`).
* Detailed fingerprints (prime exponents, rational/irrational ratios) from Study 01 and Study 02 outputs.
* Calibration routines and digest generation already implemented in the DOFT codebase.

Future work may include acquiring more coherence length data, experimental measurements of $F_m$ under varying pressure or doping, and expanding the family classification to test the predicted scaling relations. The framework outlined here is designed to accommodate such extensions without major restructuring.