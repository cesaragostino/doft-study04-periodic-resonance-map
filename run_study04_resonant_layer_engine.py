#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path as _PathHack
ROOT = _PathHack(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
from pathlib import Path

import pandas as pd

from study04.resonant_engine import HyperParams, infer_topologies, load_topology_catalog
from study04.topology_plots import plot_match_matrix, plot_topology_map

LOG = logging.getLogger("resonant_layer_engine")


def _parse_list(raw: list[str] | None) -> set[str]:
    vals: set[str] = set()
    if not raw:
        return vals
    for token in raw:
        for part in token.split(","):
            part = part.strip()
            if part and part.lower() != "all":
                vals.add(part)
    return vals


def main():
    parser = argparse.ArgumentParser(description="Infer resonant L1 topology per carrier element.")
    parser.add_argument(
        "-e",
        "--elements",
        nargs="*",
        help="Carrier elements to process (comma or space separated). Usa 'all' o deja vacío para todos.",
    )
    parser.add_argument(
        "-f",
        "--families",
        nargs="*",
        help="Filtrar por familia/bloque (s, p, d, f). Usa 'all' o deja vacío para todos.",
    )
    parser.add_argument(
        "--agg-path",
        default="data/processed/carrier_aggregate_stats.csv",
        help="Path to aggregated carrier stats (output of prep_study04_layer_data.py).",
    )
    parser.add_argument(
        "--catalog",
        default="data/raw/layer1_topology_catalog.json",
        help="Path to topology catalog JSON.",
    )
    parser.add_argument(
        "--hyperparams",
        default="data/raw/study04_hyperparams.json",
        help="Path to hyperparameter JSON (sigma_e, sigma_N, sigma_xi, lambda_N, lambda_xi, xi_env).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    root = Path(__file__).parent
    agg_path = root / args.agg_path
    catalog_path = root / args.catalog
    hp_path = root / args.hyperparams

    if not agg_path.exists():
        raise FileNotFoundError(f"Missing aggregated carrier data: {agg_path}. Run prep_study04_layer_data.py first.")

    carrier_df = pd.read_csv(agg_path)
    elements = _parse_list(args.elements)
    families = _parse_list(args.families)
    if elements:
        LOG.info("Filtering to elements: %s", ", ".join(sorted(elements)))
    if families:
        LOG.info("Filtering to families: %s", ", ".join(sorted(families)))

    catalog = load_topology_catalog(catalog_path)
    params = HyperParams.from_json(hp_path)
    LOG.info(
        "Using sigma_e=%.3f sigma_N=%.3f sigma_xi=%.3f lambda_N=%.3f lambda_xi=%.3f xi_env=%.3f",
        params.sigma_e,
        params.sigma_N,
        params.sigma_xi,
        params.lambda_N,
        params.lambda_xi,
        params.xi_env,
    )
    LOG.info("Loaded %d carriers, %d topologies", len(carrier_df), len(catalog))

    if families:
        carrier_df = carrier_df[carrier_df["block"].isin(families)]
    result = infer_topologies(carrier_df, catalog, params, elements=elements if elements else None)
    LOG.info("Processed %d carriers after filter", len(result.summary))

    out_scores_path = root / "data/processed/element_topology_scores.csv"
    out_best_path = root / "data/processed/element_topology_inference.csv"
    result.scores.to_csv(out_scores_path, index=False)
    result.summary.to_csv(out_best_path, index=False)
    LOG.info("Saved %s and %s", out_scores_path, out_best_path)

    figs_dir = root / "data/processed/figures/study04"
    figs_dir.mkdir(parents=True, exist_ok=True)
    plot_topology_map(
        result.summary,
        "best_topology",
        figs_dir / "topology_map_resonant.png",
        "Resonant layer best topology",
    )
    plot_match_matrix(result.scores, figs_dir / "element_topology_match_matrix_resonant.png")
    LOG.info("Saved figures to %s", figs_dir)


if __name__ == "__main__":
    main()
