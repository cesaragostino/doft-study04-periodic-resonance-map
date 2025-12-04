#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path as _PathHack
ROOT = _PathHack(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from pathlib import Path

import pandas as pd

from study04.topology_engine import aggregate_costs, load_topology_catalog
from study04.topology_plots import plot_topology_map

LOG = logging.getLogger("infer_topologies_e_only")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(__file__).parent
    agg_path = root / "data/processed/carrier_aggregate_stats.csv"
    topo_path = root / "data/raw/layer1_topology_catalog.json"

    if not agg_path.exists():
        raise FileNotFoundError(f"Run prep_study04_layer_data.py first. Missing {agg_path}")

    carrier_df = pd.read_csv(agg_path)
    catalog = load_topology_catalog(topo_path)
    LOG.info("Loaded %d carriers, %d topologies", len(carrier_df), len(catalog))

    scores_df, best_df = aggregate_costs(carrier_df, catalog, lambda_noise=0.0, use_noise=False)

    out_scores = root / "data/processed/carrier_topology_scores_e_only.csv"
    out_best = root / "data/processed/carrier_topology_assignments_e_only.csv"
    scores_df.to_csv(out_scores, index=False)
    best_df.to_csv(out_best, index=False)
    LOG.info("Saved %s and %s", out_scores, out_best)

    if "best_topology_e_only" not in best_df.columns and "best_topology" in best_df.columns:
        best_df["best_topology_e_only"] = best_df["best_topology"]
    plot_path = root / "data/processed/figures/study04/topology_map_e_only.png"
    plot_topology_map(best_df, "best_topology_e_only", plot_path, "Topology map (primes only)")
    LOG.info("Saved topology map to %s", plot_path)


if __name__ == "__main__":
    main()