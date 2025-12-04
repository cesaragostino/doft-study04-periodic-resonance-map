from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd

PRIME_COLUMNS: List[str] = ["e2", "e3", "e5", "e7"]

ALLOWED_CATEGORIES: Set[str] = {
    "SC_Binary",
    "SC_HighPressure",
    "SC_IronBased",
    "SC_Oxide",
    "SC_TypeI",
    "SC_TypeII",
    "SC_HeavyFermion",
}


@dataclass
class AggregationResult:
    table: pd.DataFrame
    warnings: List[str]


def load_material_data(path: Path | str) -> pd.DataFrame:
    """Load the curated material-level CSV."""
    return pd.read_csv(Path(path))


def apply_inclusion_rules(df: pd.DataFrame, logger=None) -> pd.DataFrame:
    """Compute include_study04 deterministically and log decisions."""
    df = df.copy()
    log_fn = logger.info if logger is not None else print

    included_msgs: List[str] = []
    excluded_msgs: List[str] = []

    for idx, row in df.iterrows():
        reasons: List[str] = []

        carrier_element = None if pd.isna(row.get("carrier_element")) else str(row.get("carrier_element")).strip()
        carrier_block = None if pd.isna(row.get("carrier_block")) else str(row.get("carrier_block")).strip()
        category = row.get("category")

        if not carrier_element:
            reasons.append("missing_carrier_element")

        if carrier_block not in {"s", "p", "d", "f"}:
            reasons.append("invalid_carrier_block")

        if category not in ALLOWED_CATEGORIES:
            reasons.append(f"category_not_allowed:{category}")

        primes = [row.get(p) for p in PRIME_COLUMNS]
        all_nan = all(pd.isna(p) for p in primes)
        all_zeroish = all((pd.isna(p) or p == 0) for p in primes)

        if all_nan:
            reasons.append("all_primes_nan")
        elif all_zeroish:
            reasons.append("all_primes_zero")

        if reasons:
            include = 0
            reason_str = ",".join(reasons)
            excluded_msgs.append(
                f"[EXCLUDED][{reason_str}] name={row.get('name')} carrier={carrier_element} "
                f"block={carrier_block} category={category}"
            )
        else:
            include = 1
            included_msgs.append(
                f"[included] name={row.get('name')} carrier={carrier_element} block={carrier_block} category={category}"
            )

        df.at[idx, "include_study04"] = include

    # Emit logs: included first, excluded last
    for msg in included_msgs:
        log_fn(msg)
    for msg in excluded_msgs:
        log_fn(msg)

    included = int((df["include_study04"] == 1).sum())
    excluded = int((df["include_study04"] == 0).sum())
    log_fn(f"[SUMMARY] included={included} excluded={excluded} total={len(df)}")

    return df


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
    prime_cols: List[str] = []
    for prime in PRIME_COLUMNS:
        prime_cols.extend(
            [f"{prime}_mean", f"{prime}_median", f"{prime}_std"]
        )

    ordered_cols: List[str] = ["element", "block", "Z", "group", "period", "n_materials"]
    ordered_cols += [c for c in prime_cols if c in table.columns]
    table = table.reindex(columns=ordered_cols)

    return AggregationResult(table=table, warnings=warnings)
