# DOFT Study 04 — DOFT-ATOM: Resonant Layer Engine

## 0. Purpose

Build a hierarchical simulator of a resonant atom with three concentric layers:

- **L0 – Inertial core** (nucleus / “pure mass”).
- **L1 – Orbital layer** (oscillator graph that generates the prime structure).
- **L2 – Collective layer** (coupling to the lattice / cluster).

The simulator must:

- Receive as **external targets** (per material or per element):

  - **Prime fingerprint** (Study 01):

    ```text
    e_obs = (|e2|, |e3|, |e5|, |e7|)
    ```

  - **Participation and lock** (Study 03):

    ```text
    N_obs
    deltaN_obs = |N − round(N)|
    ```

  - **Structural noise** (Study 02):

    ```text
    xi_obs
    ```

- Search over the space of **internal L1 topologies** (number of nodes + connections) for the configuration that best reproduces **all three observables simultaneously**.

In other words, solve the **inverse problem**:

> Given what we observe outside (`e`, `N`, `ξ`)…  
> what internal oscillator structure (L1) is most consistent?

---

## 1. Layer Architecture

### 1.1. L0 — The Inertial Anchor (Core Layer)

Represents the atomic nucleus / effective mass.

It has **no topological structure**; it only sets a base frequency.

**State variables:**

- `Z`: atomic number of the carrier element.
- `omega0`: base core frequency (in DOFT units).

First approximation: for example,

```text
omega0 = k_core * sqrt(Z)
```

- `k_core` goes in a parameter file.
- `xi0`: intrinsic core noise. Initially `xi0 = 0`.

L0 is **not optimized**: it is taken as given for each element.

---

### 1.2. L1 — The Geometric Modulator (Orbital Layer)

This is the key layer. It is modeled as a **graph of coupled oscillators**.

**Structure:**

```text
G = (V, E)
|V| = n_nodes  # number of sub-oscillators
```

Examples of topology families:

- 2 nodes → `BIN_DIPOLE`
- 3 nodes → `TRI_RING`
- 4 nodes → `TETRA_PACK`
- 5 nodes → `PENTA_FLOWER`
- 7 nodes → `HEPTA_FLOWER`

Each node `i` has:

- `omega_i`: natural frequency (derived from `omega0` + a geometric factor).
- `gamma_i`: internal damping (friction).

Each edge `(i, j)` has:

- `k_ij`: coupling constant (simple symmetry pattern per family).

**Effective dynamics required by the simulator**  
(we do *not* need to solve full ODEs in iteration 0):

- Compute the **normal modes** of the graph:

  - Eigenvalues `Ω_m` (collective frequencies).
  - Eigenvectors `φ_m` (spatial shape of each mode).

- Build the **prime harmonic spectrum**:

  We define a “dictionary” of projectors:

  - Prime 2 ↔ modes that double the phase / have 2-lobe symmetry.
  - Prime 3 ↔ modes with 3 alternating phase nodes.
  - etc.

In practice, for the programmer:

- Each topology `T` has a **pattern vector of relative weights**:

  ```text
  w_T = (w2, w3, w5, w7)
  ```

  (the same ones defined in the topology catalog).

- The first-level simulation can use:

  ```text
  e_sim = A_T * w_T
  ```

  where `A_T` is a global amplitude adjustable per element/material.

- **Iteration 0** can rely only on `w_T`.  
  Later iterations may refine `w_T` by actually diagonalizing `G`.

**Internal transmission efficiency `eta1`:**

Represents the fraction of energy leaving L0 that reaches L2 without being reflected.

- Starts as a **per-topology parameter**, e.g.:

  ```text
  eta1_BIN_DIPOLE ≈ 0.95
  eta1_TRI_RING   ≈ 0.85
  eta1_PENTA/HEPTA ≈ 0.8
  ```

**Internal lock in L1:**

We want a measure of how “integer-like” the relation is between internal modes and the external DOFT frequency.

Simple definition for iteration 0:

- Use the **observed lock**:

  ```text
  Q_lock_obs = 1 − median_materials(deltaN)
  ```

  (appropriately normalized).

- For each topology `T`, assign a `Q_lock_sim(T)`:

  - Simple topologies (dipole) → `Q ~ 1`.
  - Complex ones → lower `Q`.

Later iterations:

- Connect `Q_lock` to the proximity between `Ω_m` and integer multiples of `omega0`.

---

### 1.3. L2 — The Collective Interface (Lattice Layer)

Models interaction with the lattice / cluster, i.e. what you measure as `N` and `ξ`.

**State variables:**

- `Fm_sim`: mother frequency resulting from L1 (combination of modes).
- `N_sim`: simulated participation number.

For iteration 0, we can parametrize:

```text
N_sim(T) = f_lat(T, Z, eta1)
```

with a simple rule: more complex topologies → larger expected `N`.

- `xi_ext_sim`: simulated external noise.

---

## 2. Noise Propagation

We want a simple model that is still consistent with your idea of **multiplicative noise tied to layer incompatibility**.

### 2.1. Definitions

- `xi_env`: background environmental noise (global parameter, small).
- `Q_lock_E`: effective lock for that carrier (derived from Study 02/03).
- `complexity(T)`: [0, 1] measure of topological complexity:

  ```text
  BIN_DIPOLE   → 0.2
  TRI_RING     → 0.4
  TETRA_PACK   → 0.6
  PENTA_FLOWER → 0.8
  HEPTA_FLOWER → 1.0
  ```

### 2.2. Proposed formula

For a given element / material:

```text
xi_sim(T) = xi_env + (1 − Q_lock) * complexity(T)
```

- If the lock is perfect (`Q_lock ≈ 1`), the second term vanishes → “transparent” atom.
- If the lock is poor and the topology is complex, noise explodes.

Then we compare `xi_sim(T)` with `xi_obs`.

---

## 3. Inverse Problem (Per-Element Inference)

For each carrier element `E`:

### 3.1. Input data

Aggregated over materials where `E` is carrier:

- `e_obs = (|e2|, |e3|, |e5|, |e7|)` (medians or means).
- `N_obs`, `deltaN_obs`, `Q_lock_obs` (from Study 03).
- `xi_obs` (median of `predicted_noise`, from Study 02).

---

### 3.2. Search space

Discrete set of possible topologies `T`:

- `BIN_DIPOLE, TRI_RING, TETRA_PACK, PENTA_FLOWER, HEPTA_FLOWER`.

Additional parameters (optional, iteration 1+):

- `A_T` (scale of the prime amplitude `e`).
- Slight adjustments of `eta1(T)`.

---

### 3.3. Cost function

We define three terms:

#### 1) Prime matching (geometry)

```text
C_e(T) = sum_{n in {2,3,5,7}} ((e_n_obs − e_n_sim(T)) / sigma_e)²
```

where

```text
e_n_sim(T) = A_T * w_T,n
```

`sigma_e` is a scaling factor (e.g. 0.1) for normalization.

#### 2) Lock / N matching

We define `N_sim(T)` as:

```text
N_sim(T) = N0(E) * g(T)
```

- `N0(E)`: base scale per element (e.g. `median(N_obs)`).
- `g(T) > 1` for more complex topologies.

Cost:

```text
C_N(T) = ((N_obs − N_sim(T)) / sigma_N)²
```

#### 3) Noise matching

```text
C_xi(T) = ((xi_obs − xi_sim(T)) / sigma_xi)²
```

#### Total cost

```text
C_tot(T) = C_e(T) + lambda_N * C_N(T) + lambda_xi * C_xi(T)
```

For a starting point, we can use:

```text
lambda_N  = 0.5
lambda_xi = 0.5
```

(geometry dominates, `N` and `ξ` act as regulators).

---

### 3.4. Per-element output

For each element `E`:

- `T_best` = topology that minimizes `C_tot(T)`.
- `C_tot_min`, `C_e`, `C_N`, `C_xi` (for `T_best`).

Confidence level:

```text
confidence = 1 − C_tot_min / max_T C_tot(T)
```

---

## 4. Implementation Iterations (Priorities)

### Iteration 0 – Minimal engine with rigid topologies

**Goal:** have something that runs and already produces a preliminary per-element map.

- Implement L0 as just `Z` and `omega0 = k_core * sqrt(Z)` (or even constant).
- Implement L1 with **fixed pattern vectors** `w_T` per topology.
- Implement L2 with simple parametric rules for `N` and `ξ`:

  - `N_sim(T)` via fixed `g(T)`.
  - `xi_sim(T)` via the mismatch + complexity formula.

Solve the inverse problem **per element**:

- Loop over `T` in the discrete catalog.
- Fit `A_T` analytically by minimizing `||e_obs − A_T w_T||`.
- Compute `C_e`, `C_N`, `C_xi`, `C_tot`.

**Outputs:**

- `element_topology_inference.csv`  
  `(E, Z, block, T_best, costs)`
- `element_topology_match_matrix.png`  
  (heatmap: elements vs topologies)
- `topology_map_atomic.png`  
  (periodic map colored by `T_best`)

Interpretation: the `e` data are not absolute truth; they are **first-approximation constraints**.

---

### Iteration 1 – Refine L1 (modes and internal lock)

**Goal:** bring the model closer to real oscillators.

For each topology `T`:

1. Build the coupling matrix `K(T)`.
2. Diagonalize `K(T)` to obtain modes `Ω_m`.
3. Redefine `w_T` from the energy distribution across these modes.
4. Define a `Q_lock_sim(T)` based on the closeness between `Ω_m` and integer multiples of `omega0`.

Use `Q_lock_sim` in the noise formula instead of an ad-hoc parameter.

---

### Iteration 2 – Per material (not just per carrier)

**Goal:** test whether the same internal topology explains multiple external configurations (different compounds of the same element).

For each **individual material**:

- Use its specific `e_obs(material)`, `N_obs(material)`, `xi_obs(material)`.

Keep the element topology `T` fixed (as inferred in Iteration 0/1), but allow fine tuning of:

- `A_T`, `eta1`, etc.

Check whether `C_tot` can remain low for **all materials** of the same carrier.

- If not, this is evidence that the **DOFT-atom** itself has alternative modes.

---

## 5. Summary Variables for the Programmer

| Layer | Physical name        | Key variable                | Source / Role                                  |
| ----- | -------------------- | --------------------------- | ---------------------------------------------- |
| L0    | Inertial core        | `Z`, `omega0`               | Periodic table / fixed parameter.              |
| L1    | Orbital layer        | `T` (topology), `w_T`, `eta1(T)` | Defined in catalog; inferred by the engine. |
| L2    | Lattice / cluster    | `N_sim`, `xi_sim`           | Computed from `T` and lock.                    |
| Obs   | Fingerprint          | `e_obs`                     | Study 01 (`config_fingerprint`).               |
| Obs   | Participation        | `N_obs`, `deltaN`           | Study 03 (`participation_summary`).            |
| Obs   | Structural noise     | `xi_obs`                    | Study 02 (`structural_noise_summary`).         |

This brings us back exactly to your original framing:

- The atom is a **channel** transmitting coherence from L0 to L2.
- L1 is the **gearbox** we want to reconstruct.
- `e2…e7`, `N`, and `ξ` are not dogma; they are **constraints** that the simulator tries to satisfy by finding the topology that best “mediates” between Inside and Outside.
