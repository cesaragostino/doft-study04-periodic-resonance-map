#!/usr/bin/env python3
from __future__ import annotations

import json
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
from study04.topology_plots import plot_lock_noise_scatter, plot_match_matrix, plot_topology_map

LOG = logging.getLogger("infer_topologies")


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(__file__).parent
    agg_path = root / "data/processed/carrier_aggregate_stats.csv"
    topo_path = root / "data/raw/layer1_topology_catalog.json"
    hyperparams_path = root / "data/raw/study04_hyperparams.json"

    if not agg_path.exists():
        raise FileNotFoundError(f"Run prep_study04_layer_data.py first. Missing {agg_path}")

    carrier_df = pd.read_csv(agg_path)
    catalog = load_topology_catalog(topo_path)
    hp = json.loads(hyperparams_path.read_text()) if hyperparams_path.exists() else {"lambda_noise": 0.5}
    lambda_noise = float(hp.get("lambda_noise", 0.5))
    LOG.info("Using lambda_noise=%.3f", lambda_noise)
    LOG.info("Loaded %d carriers, %d topologies", len(carrier_df), len(catalog))

    scores_df, best_df = aggregate_costs(carrier_df, catalog, lambda_noise=lambda_noise, use_noise=True)

    out_scores = root / "data/processed/carrier_topology_scores.csv"
    out_best = root / "data/processed/carrier_topology_assignments.csv"
    scores_df.to_csv(out_scores, index=False)
    best_df.to_csv(out_best, index=False)
    LOG.info("Saved %s and %s", out_scores, out_best)

    figures_dir = root / "data/processed/figures/study04"
    figures_dir.mkdir(parents=True, exist_ok=True)

    plot_topology_map(best_df, "best_topology", figures_dir / "topology_map_full.png", "Topology map (primes + lock/noise)")
    plot_lock_noise_scatter(best_df, figures_dir / "lock_noise_scatter.png")
    plot_match_matrix(scores_df, figures_dir / "element_topology_match_matrix.png")
    LOG.info("Saved figures to %s", figures_dir)


if __name__ == "__main__":
    main()