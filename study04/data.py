from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd

PRIME_COLUMNS: List[str] = ["e2", "e3", "e5", "e7"]


@dataclass
class AggregationResult:
    table: pd.DataFrame
    warnings: List[str]


def load_material_data(path: Path | str) -> pd.DataFrame:
    """Load the curated material-level CSV."""
    return pd.read_csv(Path(path))


def filter_included_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep rows flagged for Study 04 with valid carrier information."""
    mask = (
        (df["include_study04"] == 1)
        & df["carrier_element"].notna()
        & df["carrier_block"].notna()
    )
    return df.loc[mask].copy()


def _coerce_optional_numeric(series: pd.Series) -> Optional[float]:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().all():
        return None
    return float(numeric.median())


def _coerce_optional_mode(series: pd.Series) -> Optional[float]:
    """Pick the most frequent non-null value if present."""
    series = series.dropna()
    if series.empty:
        return None
    return series.mode().iloc[0]


def aggregate_element_table(df: pd.DataFrame) -> AggregationResult:
    """
    Aggregate material-level fingerprints at the carrier-element level.

    Returns:
        AggregationResult with an element-level table and any warnings emitted.
    """
    filtered = filter_included_rows(df)
    warnings: List[str] = []
    records: List[dict] = []

    if filtered.empty:
        raise ValueError("No rows satisfy include_study04 == 1 with valid carriers.")

    for element, group in filtered.groupby("carrier_element"):
        block_values = group["carrier_block"].dropna().unique()
        if len(block_values) != 1:
            raise ValueError(
                f"Carrier block not unique for element {element}: {block_values}"
            )
        block = block_values[0]

        record = {
            "element": element,
            "block": block,
            "n_materials": int(len(group)),
        }

        # Optional descriptors propagated for plotting/metadata.
        if "carrier_Z" in group:
            z_val = _coerce_optional_numeric(group["carrier_Z"])
            if z_val is not None:
                record["Z"] = z_val
        if "carrier_group" in group:
            group_val = _coerce_optional_mode(group["carrier_group"])
            if group_val is not None:
                record["group"] = group_val
        if "carrier_period" in group:
            period_val = _coerce_optional_mode(group["carrier_period"])
            if period_val is not None:
                record["period"] = period_val

        for prime in PRIME_COLUMNS:
            if prime not in group:
                raise ValueError(f"Missing required prime column: {prime}")
            values = group[prime].abs().dropna()
            if values.empty:
                warnings.append(
                    f"No valid values for {prime} in element {element}; filling with NaN."
                )
            record[f"{prime}_mean"] = values.mean()
            record[f"{prime}_median"] = values.median()
            record[f"{prime}_std"] = values.std(ddof=1)

        records.append(record)

    table = pd.DataFrame.from_records(records)
    # Ensure predictable column order.
    prime_cols: List[str] = []
    for prime in PRIME_COLUMNS:
        prime_cols.extend(
            [f"{prime}_mean", f"{prime}_median", f"{prime}_std"]
        )

    ordered_cols: List[str] = ["element", "block", "Z", "group", "period", "n_materials"]
    ordered_cols += [c for c in prime_cols if c in table.columns]
    table = table.reindex(columns=ordered_cols)

    return AggregationResult(table=table, warnings=warnings)
