#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path as _PathHack
ROOT = _PathHack(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from pathlib import Path

import numpy as np
import pandas as pd

from study04.data import PRIME_COLUMNS

warnings.filterwarnings("ignore", message="Mean of empty slice")

LOG = logging.getLogger("prep_study04_layer_data")


def load_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    LOG.info("Loaded %s (%d bytes)", path, path.stat().st_size)
    return pd.read_csv(path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(__file__).parent

    carriers_path = root / "data/raw/element_carrier_assignments.csv"
    fingerprints_path = root / "data/raw/config_fingerprint_summary.csv"
    noise_path = root / "data/processed/structural_noise_summary.csv"
    if not noise_path.exists():
        noise_path = root / "data/raw/structural_noise_summary.csv"
    participation_path = root / "data/processed/participation_summary.csv"
    if not participation_path.exists():
        participation_path = root / "data/raw/participation_summary.csv"

    carriers = load_required(carriers_path).rename(columns={"name": "material"})
    fingerprints = load_required(fingerprints_path)
    noise_df = load_required(noise_path).rename(columns={"name": "material"})
    participation = load_required(participation_path)
    participation = participation.rename(columns={"name": "material", "N_value": "N", "delta_value": "delta_N"})

    if "delta_N" not in participation.columns and "N" in participation.columns:
        participation["delta_N"] = (participation["N"] - participation["N"].round()).abs()

    merged = (
        fingerprints
        .merge(carriers, on="material", how="left", suffixes=("", "_carrier"))
        .merge(noise_df[["material", "predicted_noise"]], on="material", how="left")
        .merge(participation[["material", "delta_N"]], on="material", how="left")
    )

    valid_primes = merged[PRIME_COLUMNS].notna().any(axis=1) & ~((merged[PRIME_COLUMNS] == 0).all(axis=1))
    include_mask = (merged["include_study04"] == 1) & valid_primes
    filtered = merged.loc[include_mask].copy()

    LOG.info("Materials total=%d, include=1 & valid_primes=%d", len(merged), len(filtered))

    prime_missing_counts = {p: 0 for p in PRIME_COLUMNS}
    records = []
    for carrier, grp in filtered.groupby("carrier_element"):
        rec = {
            "carrier_element": carrier,
            "block": grp["carrier_block"].mode().iat[0] if not grp["carrier_block"].dropna().empty else None,
            "carrier_group": grp.get("carrier_group", pd.Series([np.nan] * len(grp))).mode().iat[0] if "carrier_group" in grp else None,
            "carrier_period": grp.get("carrier_period", pd.Series([np.nan] * len(grp))).mode().iat[0] if "carrier_period" in grp else None,
            "carrier_Z": grp.get("carrier_Z", pd.Series([np.nan] * len(grp))).median() if "carrier_Z" in grp else None,
            "n_materials": len(grp),
            "N_median": grp["N"].median() if "N" in grp else np.nan,
        }
        for p in PRIME_COLUMNS:
            vals = grp[p].abs().dropna()
            if vals.empty:
                prime_missing_counts[p] += 1
                LOG.warning("No valid %s values for carrier %s (n_materials=%d)", p, carrier, len(grp))
                rec[f"abs_{p}_mean"] = np.nan
                rec[f"abs_{p}_median"] = np.nan
                rec[f"abs_{p}_std"] = np.nan
            else:
                rec[f"abs_{p}_mean"] = vals.mean()
                rec[f"abs_{p}_median"] = vals.median()
                rec[f"abs_{p}_std"] = vals.std(ddof=1)
        rec["delta_N_median"] = grp["delta_N"].median()
        rec["xi_ext_median"] = grp["predicted_noise"].median()
        records.append(rec)

    carrier_stats = pd.DataFrame.from_records(records)
    out_path = root / "data/processed/carrier_aggregate_stats.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    carrier_stats.to_csv(out_path, index=False)
    LOG.info("Saved carrier aggregates to %s (n=%d carriers)", out_path, len(carrier_stats))
    LOG.info("Missing prime counts by carrier: %s", prime_missing_counts)


if __name__ == "__main__":
    main()
