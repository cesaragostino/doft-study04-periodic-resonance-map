"""
Utilities for DOFT Study 04 – Periodic Resonance Map.

This package exposes helpers to load curated carrier-element data, aggregate
prime fingerprints at the element level, run statistical tests and null models,
and generate the Resonance Periodic Table visualizations.
"""

from .data import (
    PRIME_COLUMNS,
    ALLOWED_CATEGORIES,
    load_material_data,
    apply_inclusion_rules,
    filter_included_rows,
    aggregate_element_table,
)
from .analysis import (
    compute_block_statistics,
    compute_atomic_resonance_matrix,
    evaluate_classifier,
)
from .null_models import run_permutation_nulls, run_rotation_nulls
from .plots import (
    plot_periodic_resonance_map,
    plot_block_boxplots,
    plot_scatter_primes,
    plot_classifier_roc,
    plot_materials_histogram,
)
from .qc import run_fingerprint_qc

__all__ = [
    "PRIME_COLUMNS",
    "ALLOWED_CATEGORIES",
    "load_material_data",
    "apply_inclusion_rules",
    "filter_included_rows",
    "aggregate_element_table",
    "compute_block_statistics",
    "compute_atomic_resonance_matrix",
    "evaluate_classifier",
    "run_permutation_nulls",
    "run_rotation_nulls",
    "plot_periodic_resonance_map",
    "plot_block_boxplots",
    "plot_scatter_primes",
    "plot_classifier_roc",
    "plot_materials_histogram",
    "run_fingerprint_qc",
]
