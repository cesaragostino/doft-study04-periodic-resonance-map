from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns

from .analysis import PRIMES

PRIME_PALETTE: Dict[str, str] = {
    "e2": "#1f77b4",
    "e3": "#2ca02c",
    "e5": "#d62728",
    "e7": "#9467bd",
}


def _dominant_prime(row, prime_metric: str) -> str:
    values = [row[f"{p}_{prime_metric}"] for p in PRIMES]
    idx = int(np.argmax(values))
    return PRIMES[idx]


def _dominant_magnitude(row, prime_metric: str) -> float:
    values = np.array([row[f"{p}_{prime_metric}"] for p in PRIMES], dtype=float)
    return float(values.max())


def plot_periodic_resonance_map(agg_df, output_path: Path, prime_metric: str = "mean"):
    """Draw a simple periodic map using group/period if available."""
    output_path = Path(output_path)
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.set(style="whitegrid")

    df = agg_df.copy()
    df["dominant_prime"] = df.apply(lambda r: _dominant_prime(r, prime_metric), axis=1)
    df["dominant_mag"] = df.apply(lambda r: _dominant_magnitude(r, prime_metric), axis=1)

    # Positioning: prefer group/period; otherwise fall back to a simple grid.
    if {"group", "period"}.issubset(df.columns) and df[["group", "period"]].notna().all().all():
        df["x"] = df["group"]
        df["y"] = df["period"]
    else:
        # Fallback layout: alphabetical grid.
        df = df.sort_values("element").reset_index(drop=True)
        df["x"] = (df.index % 10) + 1
        df["y"] = (df.index // 10) + 1

    df["x"] = pd.to_numeric(df["x"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    if df["x"].isna().any() or df["y"].isna().any():
        df = df.sort_values("element").reset_index(drop=True)
        df["x"] = (df.index % 10) + 1
        df["y"] = (df.index // 10) + 1

    # Avoid overlapping cells: stack duplicates with a small vertical offset.
    df["stack_idx"] = df.groupby(["x", "y"]).cumcount()
    df["y_plot"] = df["y"] + 0.25 * df["stack_idx"]
    if df["stack_idx"].max() > 0:
        fig.set_figwidth(fig.get_figwidth() * 1.2)

    max_mag = df["dominant_mag"].max()
    min_mag = df["dominant_mag"].min()
    span = max(max_mag - min_mag, 1e-6)

    for _, row in df.iterrows():
        color = PRIME_PALETTE.get(row["dominant_prime"], "#888888")
        intensity = 0.3 + 0.7 * ((row["dominant_mag"] - min_mag) / span)
        rect = plt.Rectangle(
            (row["x"] - 0.5, row["y_plot"] - 0.5),
            1,
            1,
            facecolor=color,
            alpha=float(intensity),
            edgecolor="black",
        )
        ax.add_patch(rect)
        ax.text(
            row["x"],
            row["y_plot"],
            f"{row['element']}",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="black",
        )
        ax.text(
            row["x"],
            row["y_plot"] - 0.25,
            row["block"],
            ha="center",
            va="center",
            fontsize=7,
            color="black",
        )

    ax.set_xlim(df["x"].min() - 1, df["x"].max() + 1)
    ax.set_ylim(df["y_plot"].max() + 1, df["y_plot"].min() - 1)
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("Resonance Periodic Map (dominant prime + intensity)")
    for prime, color in PRIME_PALETTE.items():
        ax.plot([], [], label=prime, color=color, linewidth=6)
    ax.legend(title="Dominant prime")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_block_boxplots(agg_df, output_path: Path, prime_metric: str = "mean"):
    """Boxplots of selected primes by block."""
    output_path = Path(output_path)
    primes_to_plot = ["e2", "e5", "e7"]
    melted = (
        agg_df.melt(
            id_vars=["block"],
            value_vars=[f"{p}_{prime_metric}" for p in primes_to_plot],
            var_name="prime",
            value_name="value",
        )
        .dropna()
        .assign(prime=lambda d: d["prime"].str.replace(f"_{prime_metric}", ""))
    )
    fig, axes = plt.subplots(1, len(primes_to_plot), figsize=(14, 4), sharey=False)
    for ax, prime in zip(axes, primes_to_plot):
        sns.boxplot(
            data=melted[melted["prime"] == prime],
            x="block",
            y="value",
            hue="block",
            palette="Set2",
            dodge=False,
            legend=False,
            ax=ax,
        )
        ax.set_title(f"|{prime}| by block")
        ax.set_xlabel("block")
        ax.set_ylabel("|e|")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_scatter_primes(agg_df, output_path: Path, prime_metric: str = "mean"):
    """Scatter of e5 vs e2 colored by block."""
    output_path = Path(output_path)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.scatterplot(
        data=agg_df,
        x=f"e2_{prime_metric}",
        y=f"e5_{prime_metric}",
        hue="block",
        palette="tab10",
        s=80,
        ax=ax,
    )
    ax.set_xlabel("|e2|")
    ax.set_ylabel("|e5|")
    ax.set_title("Prime scatter: |e5| vs |e2|")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_classifier_roc(roc_points, output_path: Path):
    """ROC curve for the binary classifier."""
    output_path = Path(output_path)
    if roc_points is None:
        return
    fpr, tpr, _ = roc_points
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label="Classifier")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Chance")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC: (s+p) vs (d+f)")
    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_materials_histogram(agg_df, output_path: Path):
    """Histogram of n_materials per carrier element."""
    output_path = Path(output_path)
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.histplot(agg_df["n_materials"], bins=range(1, agg_df["n_materials"].max() + 2), ax=ax)
    ax.set_xlabel("Number of materials per carrier element")
    ax.set_ylabel("Count")
    ax.set_title("Material counts by carrier element")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
