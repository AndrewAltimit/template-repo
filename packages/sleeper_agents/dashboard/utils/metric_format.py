"""Helpers for displaying metrics that may not have been measured.

DataLoader returns None for metrics without underlying data. These helpers keep
components from turning a missing measurement into a plausible-looking number.
"""

import math
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    import pandas as pd

NOT_MEASURED = "Not measured"


def is_measured(value: Any) -> bool:
    """Return True if value is a real number (not None/NaN)."""
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def fmt_pct(value: Any, digits: int = 1) -> str:
    """Format a 0-1 value as a percentage, or NOT_MEASURED."""
    return f"{float(value):.{digits}%}" if is_measured(value) else NOT_MEASURED


def complement(value: Any) -> Optional[float]:
    """Return 1 - value, or None if value was not measured."""
    return 1.0 - float(value) if is_measured(value) else None


def exceeds(value: Any, threshold: float) -> bool:
    """True only if value was measured and is above threshold."""
    return is_measured(value) and float(value) > threshold


def measured_max(values: Iterable[Any], default: float = 0.0) -> float:
    """Maximum of the measured values, or default if none were measured."""
    measured: List[float] = [float(v) for v in values if is_measured(v)]
    return max(measured) if measured else default


def fmt_num(value: Any, digits: int = 2) -> str:
    """Format a number with fixed decimals, or NOT_MEASURED."""
    return f"{float(value):.{digits}f}" if is_measured(value) else NOT_MEASURED


def measured_mean(values: Iterable[Any]) -> Optional[float]:
    """Mean of the measured values, or None if none were measured."""
    measured: List[float] = [float(v) for v in values if is_measured(v)]
    return sum(measured) / len(measured) if measured else None


# evaluation_results.status of a test that produced metrics. Rows written before
# the status column existed have NULL status and are treated as completed.
STATUS_COMPLETED = "completed"


def split_evaluation_rows(df: "pd.DataFrame") -> Tuple["pd.DataFrame", "pd.DataFrame"]:
    """Split evaluation_results rows into (completed, not measured).

    Rows with status "skipped" or "error" carry no metrics; they are returned
    separately so views can list them instead of averaging them in.
    """
    if "status" not in df.columns:
        return df, df.iloc[0:0]
    status = df["status"].fillna(STATUS_COMPLETED).astype(str).str.lower()
    completed_mask = status == STATUS_COMPLETED
    return df[completed_mask], df[~completed_mask]
