from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

PRIME_COLUMNS = ["e2", "e3", "e5", "e7"]


@dataclass
class Topology:
    topology_id: str
    name: str
    n_nodes: int
    w: np.ndarray
    noise_sensitivity: float


def load_topology_catalog(path: Path | str) -> List[Topology]:
    path = Path(path)
    data = json.loads(path.read_text())
    catalog: List[Topology] = []
    for entry in data:
        w = np.array([entry["w2"], entry["w3"], entry["w5"], entry["w7"]], dtype=float)
        w = np.abs(w)
        s = w.sum()
        if s <= 0:
            w = np.array([0.25, 0.25, 0.25, 0.25])
        else:
            w = w / s
        catalog.append(
            Topology(
                topology_id=entry["topology_id"],
                name=entry.get("name", entry["topology_id"]),
                n_nodes=int(entry.get("n_nodes", 0)),
                w=w,
                noise_sensitivity=float(entry.get("noise_sensitivity", 1.0)),
            )
        )
    return catalog


def normalize_primes(row: pd.Series, metric_prefix: str = "abs") -> np.ndarray:
    vec = np.array([row[f"{metric_prefix}_{p}_mean"] for p in PRIME_COLUMNS], dtype=float)
    vec = np.abs(vec)
    s = vec.sum()
    if s <= 0:
        return np.array([0.25, 0.25, 0.25, 0.25])
    return vec / s


def compute_ce(vec: np.ndarray, topo: Topology) -> float:
    return float(np.linalg.norm(vec - topo.w) ** 2)


def aggregate_costs(
    carrier_df: pd.DataFrame,
    catalog: List[Topology],
    lambda_noise: float = 0.5,
    use_noise: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute C_e, C_xi, C_total for each carrier/topology."""
    records = []
    per_carrier_best = []

    delta_vals = carrier_df["delta_N_median"].dropna()
    xi_vals = carrier_df["xi_ext_median"].dropna()
    delta_min, delta_max = delta_vals.min(), delta_vals.max()
    xi_min, xi_max = xi_vals.min(), xi_vals.max()
    delta_span = max(delta_max - delta_min, 1e-6)
    xi_span = max(xi_max - xi_min, 1e-6)

    for _, row in carrier_df.iterrows():
        e_norm = normalize_primes(row, metric_prefix="abs")
        delta_N = row.get("delta_N_median")
        xi_ext = row.get("xi_ext_median")
        if pd.isna(delta_N):
            Q_lock = 0.0
        else:
            Q_lock = 1.0 - (delta_N - delta_min) / delta_span
            Q_lock = float(np.clip(Q_lock, 0.0, 1.0))
        if pd.isna(xi_ext):
            xi_norm = 0.0
        else:
            xi_norm = (xi_ext - xi_min) / xi_span
            xi_norm = float(np.clip(xi_norm, 0.0, 1.0))

        best_ce = None
        best_total = None
        best_topo_e = None
        best_topo_total = None

        for topo in catalog:
            c_e = compute_ce(e_norm, topo)
            c_xi = xi_norm * topo.noise_sensitivity * (1.0 - Q_lock) if use_noise else 0.0
            c_total = c_e + lambda_noise * c_xi if use_noise else c_e

            records.append(
                {
                    "carrier_element": row.get("carrier_element"),
                    "block": row.get("block"),
                    "n_materials": row.get("n_materials"),
                    "topology_id": topo.topology_id,
                    "C_e": c_e,
                    "C_xi": c_xi,
                    "C_total": c_total,
                    "Q_lock": Q_lock,
                    "xi_norm": xi_norm,
                }
            )

            if best_ce is None or c_e < best_ce:
                best_ce = c_e
                best_topo_e = topo.topology_id
            if best_total is None or c_total < best_total:
                best_total = c_total
                best_topo_total = topo.topology_id

        per_carrier_best.append(
            {
                "carrier_element": row.get("carrier_element"),
                "block": row.get("block"),
                "group": row.get("carrier_group"),
                "period": row.get("carrier_period"),
                "Z": row.get("carrier_Z"),
                "n_materials": row.get("n_materials"),
                "Q_lock": Q_lock,
                "xi_norm": xi_norm,
                "best_topology_e_only": best_topo_e,
                "C_e_min": best_ce,
                "best_topology": best_topo_total,
                "C_total_min": best_total,
            }
        )

    scores_df = pd.DataFrame.from_records(records)
    best_df = pd.DataFrame.from_records(per_carrier_best)
    return scores_df, best_df
