from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import LeaveOneOut, StratifiedKFold, cross_val_predict

PRIMES = ["e2", "e3", "e5", "e7"]


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cliff's delta (effect size)."""
    x = np.asarray(x)
    y = np.asarray(y)
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return np.nan
    # Efficient computation using broadcasting on signs.
    comparisons = np.sign(x[:, None] - y[None, :])
    delta = comparisons.sum() / (n1 * n2)
    return float(delta)


def _select_prime_columns(metric: str) -> List[str]:
    if metric not in {"mean", "median"}:
        raise ValueError("prime_metric must be 'mean' or 'median'")
    return [f"{p}_{metric}" for p in PRIMES]


def prepare_working_set(
    agg_df: pd.DataFrame, n_min: int, prime_metric: str
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Filter by n_min and build feature matrix + labels."""
    working = agg_df.loc[agg_df["n_materials"] >= n_min].copy()
    feature_cols = _select_prime_columns(prime_metric)
    working = working.dropna(subset=feature_cols + ["block"])
    X = working[feature_cols].to_numpy(dtype=float)
    labels = working["block"].astype(str).to_numpy()
    return working, X, labels


def _group_arrays(values: np.ndarray, labels: np.ndarray, target_labels: Sequence[str]):
    mask = np.isin(labels, target_labels)
    return values[mask]


@dataclass
class TestResult:
    group_sizes: Dict[str, int]
    delta: Optional[float]
    p_value: Optional[float]
    median_diff: Optional[float]


def mann_whitney_with_effect(
    values: np.ndarray, labels: np.ndarray, group_a: Sequence[str], group_b: Sequence[str]
) -> TestResult:
    a_vals = _group_arrays(values, labels, group_a)
    b_vals = _group_arrays(values, labels, group_b)
    group_sizes = {"a": int(len(a_vals)), "b": int(len(b_vals))}
    if len(a_vals) == 0 or len(b_vals) == 0:
        return TestResult(group_sizes=group_sizes, delta=None, p_value=None, median_diff=None)
    stat = mannwhitneyu(a_vals, b_vals, alternative="two-sided")
    delta = cliffs_delta(a_vals, b_vals)
    median_diff = float(np.median(a_vals) - np.median(b_vals))
    return TestResult(group_sizes=group_sizes, delta=delta, p_value=float(stat.pvalue), median_diff=median_diff)


@dataclass
class ClassifierResult:
    n_samples: int
    n_positive: int
    n_negative: int
    accuracy: Optional[float]
    balanced_accuracy: Optional[float]
    roc_auc: Optional[float]
    baseline_accuracy: Optional[float]
    roc_curve_points: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]


def evaluate_classifier(
    X: np.ndarray, labels: np.ndarray, random_state: int = 0
) -> ClassifierResult:
    """Binary classification for low (s+p) vs high (d+f) complexity."""
    y = np.isin(labels, ["d", "f"]).astype(int)
    n_positive = int(y.sum())
    n_negative = int(len(y) - n_positive)
    baseline_acc = max(n_positive, n_negative) / len(y) if len(y) > 0 else None

    if len(np.unique(y)) < 2 or len(y) < 3:
        return ClassifierResult(
            n_samples=len(y),
            n_positive=n_positive,
            n_negative=n_negative,
            accuracy=None,
            balanced_accuracy=None,
            roc_auc=None,
            baseline_accuracy=baseline_acc,
            roc_curve_points=None,
        )

    cv = LeaveOneOut() if len(y) <= 12 else StratifiedKFold(
        n_splits=min(5, n_negative, n_positive), shuffle=True, random_state=random_state
    )
    model = LogisticRegression(max_iter=1000, solver="liblinear", class_weight="balanced")

    probas = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    preds = (probas >= 0.5).astype(int)

    try:
        auc = roc_auc_score(y, probas)
        fpr, tpr, thresholds = roc_curve(y, probas)
        roc_points = (fpr, tpr, thresholds)
    except ValueError:
        auc = None
        roc_points = None

    return ClassifierResult(
        n_samples=len(y),
        n_positive=n_positive,
        n_negative=n_negative,
        accuracy=accuracy_score(y, preds),
        balanced_accuracy=balanced_accuracy_score(y, preds),
        roc_auc=auc,
        baseline_accuracy=baseline_acc,
        roc_curve_points=roc_points,
    )


@dataclass
class BlockStatistics:
    n_elements: int
    n_elements_robust: int
    n_min: int
    prime_metric: str
    test_p_vs_df_e2: TestResult
    test_df_vs_sp_e5: TestResult
    test_df_vs_sp_e7: TestResult
    classifier: ClassifierResult


def compute_block_statistics(
    agg_df: pd.DataFrame, n_min: int, prime_metric: str, random_state: int = 0
) -> BlockStatistics:
    working, X, labels = prepare_working_set(agg_df, n_min=n_min, prime_metric=prime_metric)
    e2 = X[:, 0]
    e5 = X[:, 2]
    e7 = X[:, 3]

    test1 = mann_whitney_with_effect(e2, labels, group_a=["p"], group_b=["d", "f"])
    test2_e5 = mann_whitney_with_effect(e5, labels, group_a=["d", "f"], group_b=["s", "p"])
    test2_e7 = mann_whitney_with_effect(e7, labels, group_a=["d", "f"], group_b=["s", "p"])
    clf_result = evaluate_classifier(X, labels, random_state=random_state)

    return BlockStatistics(
        n_elements=int(len(agg_df)),
        n_elements_robust=int(len(working)),
        n_min=n_min,
        prime_metric=prime_metric,
        test_p_vs_df_e2=test1,
        test_df_vs_sp_e5=test2_e5,
        test_df_vs_sp_e7=test2_e7,
        classifier=clf_result,
    )


def compute_atomic_resonance_matrix(
    agg_df: pd.DataFrame, prime_metric: str
) -> pd.DataFrame:
    """Correlation between block indicators and prime magnitudes."""
    feature_cols = _select_prime_columns(prime_metric)
    block_dummies = pd.get_dummies(agg_df["block"], prefix="block")
    feature_df = agg_df[feature_cols]
    matrix = pd.DataFrame(index=block_dummies.columns, columns=feature_cols, dtype=float)
    for block_col in block_dummies:
        for feat in feature_cols:
            matrix.loc[block_col, feat] = block_dummies[block_col].corr(feature_df[feat])
    return matrix


def serialize_block_statistics(stats: BlockStatistics) -> Dict[str, object]:
    """Convert dataclass tree to serializable dictionaries."""
    def _maybe(obj):
        return None if obj is None or (isinstance(obj, float) and np.isnan(obj)) else obj

    return {
        "n_elements": stats.n_elements,
        "n_elements_robust": stats.n_elements_robust,
        "n_min": stats.n_min,
        "prime_metric": stats.prime_metric,
        "tests": {
            "p_vs_df_e2": {
                "group_sizes": stats.test_p_vs_df_e2.group_sizes,
                "delta": _maybe(stats.test_p_vs_df_e2.delta),
                "p_value": _maybe(stats.test_p_vs_df_e2.p_value),
                "median_diff": _maybe(stats.test_p_vs_df_e2.median_diff),
            },
            "df_vs_sp_e5": {
                "group_sizes": stats.test_df_vs_sp_e5.group_sizes,
                "delta": _maybe(stats.test_df_vs_sp_e5.delta),
                "p_value": _maybe(stats.test_df_vs_sp_e5.p_value),
                "median_diff": _maybe(stats.test_df_vs_sp_e5.median_diff),
            },
            "df_vs_sp_e7": {
                "group_sizes": stats.test_df_vs_sp_e7.group_sizes,
                "delta": _maybe(stats.test_df_vs_sp_e7.delta),
                "p_value": _maybe(stats.test_df_vs_sp_e7.p_value),
                "median_diff": _maybe(stats.test_df_vs_sp_e7.median_diff),
            },
        },
        "classifier": {
            "n_samples": stats.classifier.n_samples,
            "n_positive": stats.classifier.n_positive,
            "n_negative": stats.classifier.n_negative,
            "accuracy": _maybe(stats.classifier.accuracy),
            "balanced_accuracy": _maybe(stats.classifier.balanced_accuracy),
            "roc_auc": _maybe(stats.classifier.roc_auc),
            "baseline_accuracy": _maybe(stats.classifier.baseline_accuracy),
        },
    }
