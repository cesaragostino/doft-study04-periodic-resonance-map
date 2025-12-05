from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from .topology_engine import PRIME_COLUMNS, Topology, load_topology_catalog

try:
    from pymatgen.core import Composition  # type: ignore

    HAS_PYMATGEN = True
except Exception:
    HAS_PYMATGEN = False

ELEMENT_SYMBOLS: Set[str] = {
    "H","He","Li","Be","B","C","N","O","F","Ne","Na","Mg","Al","Si","P","S","Cl","Ar","K","Ca","Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn","Ga","Ge","As","Se","Br","Kr","Rb","Sr","Y","Zr","Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","In","Sn","Sb","Te","I","Xe","Cs","Ba","La","Ce","Pr","Nd","Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm","Yb","Lu","Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg","Tl","Pb","Bi","Po","At","Rn","Fr","Ra","Ac","Th","Pa","U","Np","Pu","Am","Cm","Bk","Cf","Es","Fm","Md","No","Lr",
}


@dataclass
class AtomicHyperParams:
    lambda_xi: float = 0.5

    @classmethod
    def from_json(cls, path: Path | str | None) -> "AtomicHyperParams":
        if path is None:
            return cls()
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(lambda_xi=float(data.get("lambda_xi", data.get("lambda_noise", cls.lambda_xi))))


def _parse_formula(formula: str) -> Optional[str]:
    if not formula:
        return None
    formula = str(formula).strip()
    if not formula:
        return None
    if HAS_PYMATGEN:
        try:
            comp = Composition(formula)
            if len(comp.elements) == 1:
                return comp.elements[0].symbol
            return None
        except Exception:
            return None
    tokens = re.findall(r"[A-Z][a-z]?", formula)
    unique = set(tokens)
    if len(unique) == 1:
        sym = list(unique)[0]
        if sym in ELEMENT_SYMBOLS:
            return sym
    return None


def is_elemental(row: pd.Series) -> Tuple[bool, Optional[str], str]:
    """Return (is_elemental, symbol, reason)."""
    formula = row.get("formula")
    carrier = row.get("carrier_element")
    name = row.get("material") or row.get("name")

    symbol = _parse_formula(formula) if isinstance(formula, str) and formula.strip() else None
    if symbol:
        return True, symbol, "formula_single_element"

    name_str = str(name).strip() if isinstance(name, str) else ""
    carrier_str = str(carrier).strip() if isinstance(carrier, str) else ""
    if (
        name_str
        and carrier_str
        and name_str == carrier_str
        and len(name_str) <= 3
        and name_str in ELEMENT_SYMBOLS
    ):
        return True, name_str, "name_matches_carrier"

    reason = "no_formula" if not formula else "parsed_multi_element"
    return False, None, reason


def compute_lock_mean(series: pd.Series) -> float:
    vals = []
    for v in series.dropna():
        vals.append(math.exp(-abs(v - round(v))))
    if not vals:
        return float("nan")
    return float(np.mean(vals))


def infer_atomic_topologies(
    agg_df: pd.DataFrame,
    catalog: Sequence[Topology],
    params: AtomicHyperParams,
):
    df = agg_df.copy()
    xi_vals = df["xi_mean"].dropna()
    xi_ref = np.percentile(xi_vals, 90) if not xi_vals.empty else 1.0
    xi_ref = xi_ref if xi_ref > 0 else 1.0

    score_records: List[dict] = []
    best_records: List[dict] = []

    for _, row in df.iterrows():
        element = row.get("carrier_element")
        e_vec = np.array([abs(row.get(f"{p}_mean", np.nan)) for p in PRIME_COLUMNS], dtype=float)
        s = np.nansum(e_vec)
        if not np.isfinite(s) or s <= 0:
            e_norm = np.full(4, np.nan)
        else:
            e_norm = e_vec / s

        xi_mean = row.get("xi_mean")
        xi_norm = 0.0
        if xi_mean is not None and not pd.isna(xi_mean):
            xi_norm = float(min(1.0, max(0.0, xi_mean / xi_ref)))

        N_mean = row.get("N_mean")
        Q_lock = 0.0
        if N_mean is not None and not pd.isna(N_mean):
            Q_lock = float(math.exp(-abs(N_mean - round(N_mean))))

        best_match = None
        best_topo = None
        best_ce = None
        best_cxi = None
        best_ctotal = None

        for topo in catalog:
            c_e = float(np.linalg.norm(e_norm - topo.w) ** 2) if np.isfinite(e_norm).all() else float("inf")
            c_xi = xi_norm * topo.noise_sensitivity * (1.0 - Q_lock)
            c_total = c_e + params.lambda_xi * c_xi
            match = math.exp(-c_total)

            score_records.append(
                {
                    "carrier_element": element,
                    "block": row.get("block"),
                    "topology_id": topo.topology_id,
                    "C_e": c_e,
                    "C_xi": c_xi,
                    "C_total": c_total,
                    "match_score": match,
                    "xi_norm": xi_norm,
                    "Q_lock": Q_lock,
                    "n_materials_elemental": row.get("n_materials_elemental"),
                }
            )

            if best_match is None or match > best_match:
                best_match = match
                best_topo = topo.topology_id
                best_ce = c_e
                best_cxi = c_xi
                best_ctotal = c_total

        best_records.append(
            {
                **{k: row.get(k) for k in row.index},
                "Q_lock": Q_lock,
                "xi_norm": xi_norm,
                "best_topology": best_topo,
                "best_match_score": best_match,
                "C_total_min": best_ctotal,
                "C_e_min": best_ce,
                "C_xi_min": best_cxi,
            }
        )

    scores_df = pd.DataFrame.from_records(score_records)
    best_df = pd.DataFrame.from_records(best_records)
    return scores_df, best_df


__all__ = [
    "AtomicHyperParams",
    "ELEMENT_SYMBOLS",
    "infer_atomic_topologies",
    "is_elemental",
    "compute_lock_mean",
    "load_topology_catalog",
]
