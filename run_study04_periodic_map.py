#!/usr/bin/env python3
"""
End-to-end runner for DOFT Study 04 – Periodic Resonance Map.

Example:
    python run_study04_periodic_map.py \
        --config data/raw/element_carrier_assignments.csv \
        --n-min 1
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from study04 import (
    aggregate_element_table,
    compute_atomic_resonance_matrix,
    compute_block_statistics,
    load_material_data,
    plot_block_boxplots,
    plot_classifier_roc,
    plot_materials_histogram,
    plot_periodic_resonance_map,
    plot_scatter_primes,
    run_permutation_nulls,
    run_rotation_nulls,
)
from study04.analysis import serialize_block_statistics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Study 04 – Periodic Resonance Map")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("data/raw/element_carrier_assignments.csv"),
        help="Path to curated element-carrier assignment CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory for processed outputs.",
    )
    parser.add_argument(
        "--n-min",
        type=int,
        default=1,
        help="Minimum materials per element for robust stats (recommended 2–3).",
    )
    parser.add_argument(
        "--prime-metric",
        choices=["mean", "median"],
        default="mean",
        help="Aggregation choice for prime vectors.",
    )
    parser.add_argument(
        "--n-perm",
        type=int,
        default=5000,
        help="Number of permutations for block-label null model.",
    )
    parser.add_argument(
        "--n-rotations",
        type=int,
        default=0,
        help="Number of random rotations for prime-space null model (0 to skip).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=0,
        help="Random seed for reproducibility.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Loading material data from %s", args.config)
    material_df = load_material_data(args.config)
    agg_result = aggregate_element_table(material_df)
    for warning in agg_result.warnings:
        logging.warning(warning)

    agg_path = args.output_dir / "periodic_resonance_table.csv"
    agg_result.table.to_csv(agg_path, index=False)
    logging.info("Saved element table to %s", agg_path)

    resonance_matrix = compute_atomic_resonance_matrix(
        agg_result.table, prime_metric=args.prime_metric
    )
    matrix_path = args.output_dir / "atomic_resonance_matrix.csv"
    resonance_matrix.to_csv(matrix_path)
    logging.info("Saved atomic resonance matrix to %s", matrix_path)

    stats = compute_block_statistics(
        agg_result.table,
        n_min=args.n_min,
        prime_metric=args.prime_metric,
        random_state=args.random_state,
    )
    stats_json = serialize_block_statistics(stats)

    perm_nulls = run_permutation_nulls(
        agg_result.table,
        n_min=args.n_min,
        prime_metric=args.prime_metric,
        n_perm=args.n_perm,
        random_state=args.random_state,
    )
    rot_nulls = run_rotation_nulls(
        agg_result.table,
        n_min=args.n_min,
        prime_metric=args.prime_metric,
        n_rotations=args.n_rotations,
        random_state=args.random_state,
    )

    stats_json["null_models"] = {"permutation": perm_nulls, "rotation": rot_nulls}
    stats_path = args.output_dir / "study04_block_stats.json"
    with stats_path.open("w") as f:
        json.dump(stats_json, f, indent=2)
    logging.info("Saved block statistics to %s", stats_path)

    # Visualizations
    plot_periodic_resonance_map(
        agg_result.table,
        output_path=args.output_dir / "resonance_periodic_table.png",
        prime_metric=args.prime_metric,
    )
    plot_block_boxplots(
        agg_result.table,
        output_path=figures_dir / "prime_boxplots.png",
        prime_metric=args.prime_metric,
    )
    plot_scatter_primes(
        agg_result.table,
        output_path=figures_dir / "prime_scatter.png",
        prime_metric=args.prime_metric,
    )
    plot_materials_histogram(
        agg_result.table,
        output_path=figures_dir / "materials_hist.png",
    )
    plot_classifier_roc(
        stats.classifier.roc_curve_points,
        output_path=figures_dir / "classifier_roc.png",
    )

    logging.info("Study 04 run complete.")


if __name__ == "__main__":
    main()
