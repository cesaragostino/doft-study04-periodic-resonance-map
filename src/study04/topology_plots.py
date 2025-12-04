from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

TOPO_PALETTE: Dict[str, str] = {
    "BIN_DIPOLE": "#1f77b4",
    "TRI_RING": "#2ca02c",
    "TETRA_PACK": "#ff7f0e",
    "PENTA_FLOWER": "#d62728",
    "HEPTA_FLOWER": "#9467bd",
}


def _layout_positions(df: pd.DataFrame) -> pd.DataFrame:
    if {"carrier_group", "carrier_period"}.issubset(df.columns) and df[["carrier_group", "carrier_period"]].notna().all().all():
        df = df.assign(x=pd.to_numeric(df["carrier_group"], errors="coerce"), y=pd.to_numeric(df["carrier_period"], errors="coerce"))
    else:
        df = df.sort_values("carrier_element").reset_index(drop=True)
        df = df.assign(x=(df.index % 10) + 1, y=(df.index // 10) + 1)
    df["stack_idx"] = df.groupby(["x", "y"]).cumcount()
    df["y_plot"] = df["y"] + 0.25 * df["stack_idx"]
    return df


def plot_topology_map(assign_df: pd.DataFrame, value_col: str, output_path: Path, title: str):
    output_path = Path(output_path)
    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(12, 6))

    df = _layout_positions(assign_df.copy())
    unique_topos = df[value_col].unique()
    palette = {k: TOPO_PALETTE.get(k, "#888888") for k in unique_topos}

    for _, row in df.iterrows():
        topo = row[value_col]
        color = palette.get(topo, "#888888")
        rect = plt.Rectangle(
            (row["x"] - 0.5, row["y_plot"] - 0.5),
            1,
            1,
            facecolor=color,
            alpha=0.9,
            edgecolor="black",
        )
        ax.add_patch(rect)
        ax.text(row["x"], row["y_plot"], row["carrier_element"], ha="center", va="center", fontsize=9, fontweight="bold")
        ax.text(row["x"], row["y_plot"] - 0.25, str(row.get("block", "")), ha="center", va="center", fontsize=7)

    ax.set_xlim(df["x"].min() - 1, df["x"].max() + 1)
    ax.set_ylim(df["y_plot"].max() + 1, df["y_plot"].min() - 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title)
    for topo, color in palette.items():
        ax.plot([], [], color=color, label=topo, linewidth=6)
    ax.legend(title="Topology")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_lock_noise_scatter(assign_df: pd.DataFrame, output_path: Path):
    output_path = Path(output_path)
    df = assign_df.copy()
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.scatterplot(data=df, x="xi_norm", y=1 - df["Q_lock"], hue="best_topology", palette=TOPO_PALETTE, s=80, ax=ax)
    ax.set_xlabel("xi_norm")
    ax.set_ylabel("1 - Q_lock")
    ax.set_title("Lock vs noise by topology")
    ax.legend(title="Topology")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_match_matrix(scores_df: pd.DataFrame, output_path: Path):
    output_path = Path(output_path)
    pivot_entries = []
    for elem, grp in scores_df.groupby("carrier_element"):
        c_min = grp["C_total"].min()
        c_max = grp["C_total"].max()
        span = max(c_max - c_min, 1e-6)
        for _, row in grp.iterrows():
            match = 1.0 - ((row["C_total"] - c_min) / span)
            pivot_entries.append({"carrier_element": elem, "topology_id": row["topology_id"], "match_score": match})
    pivot_df = pd.DataFrame(pivot_entries)
    if pivot_df.empty:
        return
    matrix = pivot_df.pivot(index="carrier_element", columns="topology_id", values="match_score")
    fig, ax = plt.subplots(figsize=(10, max(4, 0.25 * len(matrix))))
    sns.heatmap(matrix, ax=ax, cmap="Blues", vmin=0, vmax=1, cbar_kws={"label": "Match score"})
    ax.set_xlabel("Topology")
    ax.set_ylabel("Carrier element")
    ax.set_title("Element vs Topology match")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
