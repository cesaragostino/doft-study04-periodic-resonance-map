from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from .topology_engine import PRIME_COLUMNS, Topology, load_topology_catalog

# Complexity and N-scale heuristics per topology family
COMPLEXITY: Dict[str, float] = {
    "BIN_DIPOLE": 0.2,
    "TRI_RING": 0.4,
    "TETRA_PACK": 0.6,
    "PENTA_FLOWER": 0.8,
    "HEPTA_FLOWER": 1.0,
}

N_SCALE: Dict[str, float] = {
    "BIN_DIPOLE": 1.0,
    "TRI_RING": 1.15,
    "TETRA_PACK": 1.30,
    "PENTA_FLOWER": 1.45,
    "HEPTA_FLOWER": 1.60,
}


@dataclass
class HyperParams:
    sigma_e: float = 0.1
    sigma_N: float = 1.0
    sigma_xi: float = 0.5
    lambda_N: float = 0.5
    lambda_xi: float = 0.5
    xi_env: float = 0.05
    k_core: float = 1.0

    @classmethod
    def from_json(cls, path: Path | str | None) -> "HyperParams":
        if path is None:
            return cls()
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(
            sigma_e=float(data.get("sigma_e", cls.sigma_e)),
            sigma_N=float(data.get("sigma_N", cls.sigma_N)),
            sigma_xi=float(data.get("sigma_xi", cls.sigma_xi)),
            lambda_N=float(data.get("lambda_N", cls.lambda_N)),
            lambda_xi=float(data.get("lambda_xi", cls.lambda_xi)),
            xi_env=float(data.get("xi_env", cls.xi_env)),
            k_core=float(data.get("k_core", cls.k_core)),
        )


@dataclass
class InferenceResult:
    scores: pd.DataFrame
    summary: pd.DataFrame


def _prime_vector(row: pd.Series) -> np.ndarray:
    vec: List[float] = []
    for p in PRIME_COLUMNS:
        val = row.get(f"abs_{p}_median")
        if pd.isna(val):
            val = row.get(f"abs_{p}_mean")
        vec.append(np.nan if pd.isna(val) else float(abs(val)))
    return np.array(vec, dtype=float)


def _fit_amplitude(e_obs: np.ndarray, w: np.ndarray, sigma_e: float) -> Tuple[float, float, np.ndarray]:
    mask = ~np.isnan(e_obs)
    if not mask.any():
        return np.nan, float("inf"), np.full_like(e_obs, np.nan)
    w_m = w[mask]
    e_m = e_obs[mask]
    denom = float(np.dot(w_m, w_m))
    A = 0.0 if denom <= 0 else float(np.dot(e_m, w_m) / denom)
    e_sim = A * w
    ce = float(np.sum(((e_obs[mask] - e_sim[mask]) / sigma_e) ** 2))
    return A, ce, e_sim


def _q_lock(delta_N: Optional[float]) -> float:
    if delta_N is None or pd.isna(delta_N):
        return 0.0
    return float(np.clip(1.0 - float(delta_N), 0.0, 1.0))


def _xi_sim(q_lock: float, topo_id: str, params: HyperParams) -> float:
    return float(params.xi_env + (1.0 - q_lock) * COMPLEXITY.get(topo_id, 1.0))


def _n_sim(N_obs: Optional[float], topo_id: str) -> Optional[float]:
    if N_obs is None or pd.isna(N_obs):
        return None
    return float(N_obs) * N_SCALE.get(topo_id, 1.0)


def infer_topologies(
    carrier_df: pd.DataFrame,
    catalog: Sequence[Topology],
    params: HyperParams,
    elements: Optional[Set[str]] = None,
) -> InferenceResult:
    df = carrier_df.copy()
    if elements:
        df = df[df["carrier_element"].isin(elements)].copy()
    if df.empty:
        raise ValueError("No carriers to process after filtering; check --elements")

    # Normalization helpers for plots
    delta_vals = df["delta_N_median"].dropna()
    xi_vals = df["xi_ext_median"].dropna()
    delta_min, delta_max = (delta_vals.min(), delta_vals.max()) if not delta_vals.empty else (0.0, 1.0)
    xi_min, xi_max = (xi_vals.min(), xi_vals.max()) if not xi_vals.empty else (0.0, 1.0)
    delta_span = max(delta_max - delta_min, 1e-6)
    xi_span = max(xi_max - xi_min, 1e-6)

    score_records: List[dict] = []
    best_records: List[dict] = []

    for _, row in df.iterrows():
        element = row.get("carrier_element")
        e_obs = _prime_vector(row)
        N_obs = row.get("N_median")
        delta_N = row.get("delta_N_median")
        xi_obs = row.get("xi_ext_median")
        q_lock = _q_lock(delta_N)
        delta_norm = (float(delta_N) - delta_min) / delta_span if not pd.isna(delta_N) else 0.0
        xi_norm = (float(xi_obs) - xi_min) / xi_span if not pd.isna(xi_obs) else 0.0
        delta_norm = float(np.clip(delta_norm, 0.0, 1.0))
        xi_norm = float(np.clip(xi_norm, 0.0, 1.0))

        best_total = None
        best_topo = None
        best_ce = None
        best_cn = None
        best_cxi = None
        best_amp = None

        element_totals: List[float] = []

        for topo in catalog:
            A_T, C_e, e_sim = _fit_amplitude(e_obs, topo.w, params.sigma_e)
            N_sim = _n_sim(N_obs, topo.topology_id)
            C_N = 0.0
            if N_obs is not None and not pd.isna(N_obs) and N_sim is not None:
                C_N = float(((N_obs - N_sim) / params.sigma_N) ** 2)
            xi_sim = _xi_sim(q_lock, topo.topology_id, params)
            C_xi = 0.0
            if xi_obs is not None and not pd.isna(xi_obs):
                C_xi = float(((xi_obs - xi_sim) / params.sigma_xi) ** 2)

            C_total = C_e + params.lambda_N * C_N + params.lambda_xi * C_xi
            element_totals.append(C_total)

            score_records.append(
                {
                    "carrier_element": element,
                    "block": row.get("block"),
                    "topology_id": topo.topology_id,
                    "C_e": C_e,
                    "C_N": C_N,
                    "C_xi": C_xi,
                    "C_total": C_total,
                    "A_T": A_T,
                    "N_obs": N_obs,
                    "N_sim": N_sim,
                    "xi_obs": xi_obs,
                    "xi_sim": xi_sim,
                    "q_lock": q_lock,
                }
            )

            if best_total is None or C_total < best_total:
                best_total = C_total
                best_topo = topo.topology_id
                best_ce = C_e
                best_cn = C_N
                best_cxi = C_xi
                best_amp = A_T

        max_total = max(element_totals) if element_totals else float("inf")
        confidence = 0.0 if not element_totals or max_total == 0 else 1.0 - (best_total / max_total)

        best_records.append(
            {
                "carrier_element": element,
                "block": row.get("block"),
                "carrier_group": row.get("carrier_group"),
                "carrier_period": row.get("carrier_period"),
                "carrier_Z": row.get("carrier_Z"),
                "n_materials": row.get("n_materials"),
                "N_obs": N_obs,
                "delta_N_median": delta_N,
                "xi_obs": xi_obs,
                "xi_norm": xi_norm,
                "Q_lock": q_lock,
                "best_topology": best_topo,
                "C_total_min": best_total,
                "C_e_min": best_ce,
                "C_N_min": best_cn,
                "C_xi_min": best_cxi,
                "A_best": best_amp,
                "confidence": confidence,
            }
        )

    scores_df = pd.DataFrame.from_records(score_records)
    best_df = pd.DataFrame.from_records(best_records)
    return InferenceResult(scores=scores_df, summary=best_df)


__all__ = [
    "COMPLEXITY",
    "N_SCALE",
    "HyperParams",
    "InferenceResult",
    "infer_topologies",
    "load_topology_catalog",
]
