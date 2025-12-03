from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .analysis import (
    PRIMES,
    cliffs_delta,
    evaluate_classifier,
    prepare_working_set,
)


def _metric_snapshot(X: np.ndarray, labels: np.ndarray) -> Dict[str, Optional[float]]:
    """Collect core scalar metrics used in null models."""
    e2 = X[:, 0]
    e5 = X[:, 2]
    e7 = X[:, 3]
    metrics = {
        "delta_e2_p_vs_df": cliffs_delta(
            e2[np.isin(labels, ["p"])], e2[np.isin(labels, ["d", "f"])]
        ),
        "delta_e5_df_vs_sp": cliffs_delta(
            e5[np.isin(labels, ["d", "f"])], e5[np.isin(labels, ["s", "p"])]
        ),
        "delta_e7_df_vs_sp": cliffs_delta(
            e7[np.isin(labels, ["d", "f"])], e7[np.isin(labels, ["s", "p"])]
        ),
    }
    clf_res = evaluate_classifier(X, labels)
    metrics["classifier_accuracy"] = clf_res.accuracy
    return metrics


def _empirical_p(real: float, null_samples: List[float]) -> Optional[float]:
    arr = np.asarray([x for x in null_samples if x is not None and not np.isnan(x)])
    if np.isnan(real) or real is None or arr.size == 0:
        return None
    extreme = np.sum(np.abs(arr) >= abs(real))
    return float((extreme + 1) / (arr.size + 1))


def _z_score(real: float, null_samples: List[float]) -> Optional[float]:
    arr = np.asarray([x for x in null_samples if x is not None and not np.isnan(x)])
    if np.isnan(real) or real is None or arr.size < 2:
        return None
    return float((real - arr.mean()) / arr.std(ddof=1))


def run_permutation_nulls(
    agg_df,
    n_min: int,
    prime_metric: str,
    n_perm: int = 5000,
    random_state: int = 0,
):
    """Permute block labels to build null distributions."""
    working, X, labels = prepare_working_set(agg_df, n_min=n_min, prime_metric=prime_metric)
    if len(labels) == 0:
        return {"skipped_reason": "No elements pass n_min filter.", "n_perm": n_perm}

    rng = np.random.default_rng(random_state)
    real_metrics = _metric_snapshot(X, labels)
    null_samples = {k: [] for k in real_metrics}

    for _ in range(n_perm):
        perm_labels = rng.permutation(labels)
        metrics = _metric_snapshot(X, perm_labels)
        for key, value in metrics.items():
            null_samples[key].append(value)

    summary = {}
    for key, samples in null_samples.items():
        summary[key] = {
            "mean": float(np.nanmean(samples)),
            "std": float(np.nanstd(samples, ddof=1)),
            "p_value": _empirical_p(real_metrics[key], samples),
            "z_score": _z_score(real_metrics[key], samples),
            "real": None if real_metrics[key] is None or np.isnan(real_metrics[key]) else float(real_metrics[key]),
        }
    summary["n_perm"] = n_perm
    summary["n_elements"] = len(labels)
    return summary


def _random_rotation(dim: int, rng: np.random.Generator) -> np.ndarray:
    """Generate a random orthogonal matrix using QR decomposition."""
    A = rng.normal(size=(dim, dim))
    Q, R = np.linalg.qr(A)
    signs = np.sign(np.diag(R))
    Q *= signs
    return Q


def run_rotation_nulls(
    agg_df,
    n_min: int,
    prime_metric: str,
    n_rotations: int = 0,
    random_state: int = 0,
):
    """Randomly rotate prime space; optional and can be disabled with n_rotations=0."""
    if n_rotations <= 0:
        return {"skipped_reason": "n_rotations set to 0."}

    working, X, labels = prepare_working_set(agg_df, n_min=n_min, prime_metric=prime_metric)
    if len(labels) == 0:
        return {"skipped_reason": "No elements pass n_min filter.", "n_rotations": n_rotations}

    rng = np.random.default_rng(random_state)
    real_metrics = _metric_snapshot(X, labels)
    rotation_samples = {k: [] for k in real_metrics}

    for _ in range(n_rotations):
        R = _random_rotation(dim=X.shape[1], rng=rng)
        rotated = np.abs(X @ R)
        metrics = _metric_snapshot(rotated, labels)
        for key, value in metrics.items():
            rotation_samples[key].append(value)

    summary = {}
    for key, samples in rotation_samples.items():
        summary[key] = {
            "mean": float(np.nanmean(samples)),
            "std": float(np.nanstd(samples, ddof=1)),
            "p_value": _empirical_p(real_metrics[key], samples),
            "z_score": _z_score(real_metrics[key], samples),
            "real": None if real_metrics[key] is None or np.isnan(real_metrics[key]) else float(real_metrics[key]),
        }
    summary["n_rotations"] = n_rotations
    summary["n_elements"] = len(labels)
    return summary
