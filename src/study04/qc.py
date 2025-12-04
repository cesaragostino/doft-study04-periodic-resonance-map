from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .data import PRIME_COLUMNS

ABS_MIN_DEFAULT = 0.0
ABS_MAX_DEFAULT = 5.0
Z_THRESHOLD_DEFAULT = 2.5


@dataclass
class QCSummary:
    total_materials: int
    checked_materials: int
    included_count: int
    excluded_count: int
    warned_included_count: int
    errors_total: int
    warnings_total: int
    errors_by_type: Dict[str, int]
    warnings_by_type: Dict[str, int]


def _flag(counter: Dict[str, int], key: str):
    counter[key] = counter.get(key, 0) + 1


def _dominant_ratio(values: List[float]) -> float:
    sorted_vals = sorted(values, reverse=True)
    if len(sorted_vals) < 2:
        return float("inf")
    dom, second = sorted_vals[0], sorted_vals[1]
    if second == 0:
        return float("inf") if dom > 0 else 1.0
    return dom / second


def run_fingerprint_qc(
    df: pd.DataFrame,
    abs_min: float = ABS_MIN_DEFAULT,
    abs_max: float = ABS_MAX_DEFAULT,
    z_threshold: float = Z_THRESHOLD_DEFAULT,
    logger=None,
    output_dir: Path | str = Path("data/processed"),
) -> Tuple[pd.DataFrame, QCSummary]:
    """
    Run fingerprint QC on materials flagged for inclusion (include_study04 == 1).

    Returns:
        qc_df: per-material flags
        summary: aggregated counts
    """
    log_fn = logger.info if logger is not None else print
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["error_flags"] = ""
    df["warning_flags"] = ""

    included_mask = df["include_study04"] == 1
    working = df.loc[included_mask].copy()

    errors_by_type: Dict[str, int] = {}
    warnings_by_type: Dict[str, int] = {}

    # Level 1: basic per-row checks
    for idx, row in working.iterrows():
        errors: List[str] = []
        warnings: List[str] = []

        prime_vals = [row.get(p) for p in PRIME_COLUMNS]
        missing_primes = any(pd.isna(v) for v in prime_vals)
        all_zero = all((pd.isna(v) or v == 0) for v in prime_vals)
        has_any_value = (not missing_primes) and (not all_zero)

        if not has_any_value:
            errors.append("ERROR_missing_fingerprint")
            if all_zero:
                errors.append("ERROR_all_primes_zero")

        # Range checks
        for p, val in zip(PRIME_COLUMNS, prime_vals):
            if pd.isna(val):
                continue
            if val == 0:
                continue
            if abs(val) < abs_min or abs(val) > abs_max:
                errors.append("ERROR_out_of_range")
                break

        df.at[idx, "_missing_primes"] = missing_primes
        df.at[idx, "_all_zero"] = all_zero
        df.at[idx, "_has_any_value"] = has_any_value
        working.at[idx, "_missing_primes"] = missing_primes
        working.at[idx, "_all_zero"] = all_zero
        working.at[idx, "_has_any_value"] = has_any_value

        if errors:
            df.at[idx, "error_flags"] = ";".join(sorted(set(errors)))
            for e in set(errors):
                _flag(errors_by_type, e)
            log_fn(
                f"[ERROR][{';'.join(sorted(set(errors)))}] "
                f"name={row.get('name')} carrier={row.get('carrier_element')} "
                f"category={row.get('category')}"
            )
            working.at[idx, "_errors_present"] = True
        else:
            working.at[idx, "_errors_present"] = False

        df.at[idx, "warning_flags"] = ""  # will append later

    # Level 2: global percentile outliers
    valid_working = working[(working["_errors_present"] == False) & (working["_has_any_value"] == True)]
    abs_values = {p: valid_working[p].abs().dropna().to_numpy() for p in PRIME_COLUMNS}
    percentiles = {}
    for p, arr in abs_values.items():
        if arr.size >= 1:
            percentiles[p] = np.percentile(arr, [1, 99])
        else:
            percentiles[p] = (np.nan, np.nan)

    for idx, row in valid_working.iterrows():
        warnings: List[str] = []
        for p in PRIME_COLUMNS:
            val = abs(row.get(p)) if not pd.isna(row.get(p)) else np.nan
            p1, p99 = percentiles[p]
            if np.isnan(p1) or np.isnan(p99):
                continue
            if val < p1 or val > p99:
                warnings.append(f"WARN_outlier_global_{p}")

        # Level 3: per-carrier z-scores will be added later
        df_warnings_existing = df.at[idx, "warning_flags"]
        combined = set(df_warnings_existing.split(";") if df_warnings_existing else []) | set(warnings)
        if combined:
            df.at[idx, "warning_flags"] = ";".join(sorted([w for w in combined if w]))

    # Level 3: consistency within carrier (z-score)
    carrier_groups = valid_working.groupby("carrier_element")
    carrier_stats = {}
    for carrier, grp in carrier_groups:
        if len(grp) < 2:
            continue
        carrier_stats[carrier] = {
            p: (grp[p].abs().mean(), grp[p].abs().std(ddof=1)) for p in PRIME_COLUMNS
        }

    for idx, row in valid_working.iterrows():
        carrier = row.get("carrier_element")
        warnings: List[str] = []
        if carrier in carrier_stats:
            for p in PRIME_COLUMNS:
                mean, std = carrier_stats[carrier][p]
                val = abs(row.get(p))
                if pd.isna(val) or std == 0 or pd.isna(std):
                    continue
                z = (val - mean) / std
                if abs(z) > z_threshold:
                    warnings.append(f"WARN_outlier_vs_carrier_{p}")
            if sum(1 for w in warnings if "WARN_outlier_vs_carrier" in w) > 1:
                warnings.append("WARN_outlier_vs_carrier_multi")

        existing = df.at[idx, "warning_flags"]
        combined = set(existing.split(";") if existing else []) | set(warnings)
        if combined:
            df.at[idx, "warning_flags"] = ";".join(sorted([w for w in combined if w]))

    # Level 4: soft heuristics
    # Dominant prime ambiguity
    for idx, row in valid_working.iterrows():
        vals = [abs(row.get(p)) if not pd.isna(row.get(p)) else 0.0 for p in PRIME_COLUMNS]
        ratio = _dominant_ratio(vals)
        warnings = []
        if ratio < 1.1:
            warnings.append("WARN_ambiguous_dominant_prime")

        block = row.get("carrier_block")
        # block heuristics require global stats
        p_block = valid_working[valid_working["carrier_block"] == "p"]
        df_block = valid_working[valid_working["carrier_block"].isin(["d", "f"])]
        if block == "p" and not p_block.empty and not df_block.empty:
            median_e2_p = p_block["e2"].abs().median()
            median_e5_df = df_block["e5"].abs().median()
            median_e7_df = df_block["e7"].abs().median()
            if median_e2_p > 0 and median_e5_df >= 0 and median_e7_df >= 0:
                if vals[0] < 0.5 * median_e2_p and (vals[2] > median_e5_df or vals[3] > median_e7_df):
                    warnings.append("WARN_unusual_for_p_block")
        if block in {"d", "f"}:
            p10_e5 = valid_working["e5"].abs().quantile(0.10)
            p10_e7 = valid_working["e7"].abs().quantile(0.10)
            if vals[2] < p10_e5 and vals[3] < p10_e7:
                warnings.append("WARN_too_pure_binary_for_d_or_f")

        existing = df.at[idx, "warning_flags"]
        combined = set(existing.split(";") if existing else []) | set(warnings)
        if combined:
            df.at[idx, "warning_flags"] = ";".join(sorted([w for w in combined if w]))

    # Collect warning counts and log (only included materials)
    df_out = df[[
        "name",
        "category",
        "carrier_element",
        "carrier_block",
        "include_study04",
        "e2",
        "e3",
        "e5",
        "e7",
        "error_flags",
        "warning_flags",
    ]].copy()

    for _, row in df_out.loc[df_out["include_study04"] == 1].iterrows():
        warns = row.get("warning_flags") or ""
        errs = row.get("error_flags") or ""
        if warns:
            for w in warns.split(";"):
                if w:
                    _flag(warnings_by_type, w)
            log_fn(
                f"[WARN][{warns}] name={row.get('name')} carrier={row.get('carrier_element')} category={row.get('category')}"
            )
        if errs:
            # errors already logged during level 1
            pass

    # Persist outputs
    per_material_path = output_dir / "fingerprint_qc_per_material.csv"
    df_out = df[[
        "name",
        "category",
        "carrier_element",
        "carrier_block",
        "include_study04",
        "e2",
        "e3",
        "e5",
        "e7",
        "error_flags",
        "warning_flags",
    ]].copy()
    df_out.to_csv(per_material_path, index=False)

    warn_count = int(((df_out["include_study04"] == 1) & (df_out["warning_flags"] != "")).sum())
    summary = QCSummary(
        total_materials=int(len(df)),
        checked_materials=int(len(working)),
        included_count=int(len(working)),
        excluded_count=int(len(df) - len(working)),
        warned_included_count=warn_count,
        errors_total=sum(errors_by_type.values()),
        warnings_total=sum(warnings_by_type.values()),
        errors_by_type=errors_by_type,
        warnings_by_type=warnings_by_type,
    )

    summary_path = output_dir / "fingerprint_qc_summary.json"
    summary_path.write_text(
        pd.Series({
            "total_materials": summary.total_materials,
            "checked_materials": summary.checked_materials,
            "included_count": summary.included_count,
            "excluded_count": summary.excluded_count,
            "warned_included_count": summary.warned_included_count,
            "errors_total": summary.errors_total,
            "warnings_total": summary.warnings_total,
            "errors_by_type": summary.errors_by_type,
            "warnings_by_type": summary.warnings_by_type,
        }).to_json(indent=2)
    )
    log_fn(
        f"[SUMMARY_QC] included={summary.included_count} excluded={summary.excluded_count} "
        f"warned_included={summary.warned_included_count} total={summary.total_materials}"
    )

    # Stop pipeline if any included material has errors
    errors_present = df_out.loc[(df_out["include_study04"] == 1) & (df_out["error_flags"] != "")]
    if not errors_present.empty:
        raise SystemExit(
            f"Fingerprint QC found blocking errors in {len(errors_present)} included materials. "
            "See data/processed/fingerprint_qc_per_material.csv"
        )

    return df_out, summary
