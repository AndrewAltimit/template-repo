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


def suite_coverage_fraction(suite_coverage: Any) -> Optional[float]:
    """Fraction of implemented test suites with stored results, or None if unknown.

    suite_coverage is DataLoader.fetch_suite_coverage() / summary["suite_coverage"].
    """
    if not isinstance(suite_coverage, dict) or suite_coverage.get("error"):
        return None
    fraction = suite_coverage.get("fraction")
    return float(fraction) if is_measured(fraction) else None


def suites_without_results(suite_coverage: Any) -> Optional[List[str]]:
    """Implemented test suites with no stored results, or None if unknown."""
    if suite_coverage_fraction(suite_coverage) is None:
        return None
    with_results = set(suite_coverage.get("suites_with_results") or [])
    return [s for s in suite_coverage.get("implemented_suites") or [] if s not in with_results]


def fmt_suite_coverage(suite_coverage: Any) -> str:
    """Implemented test suites with stored results as "k of n suites", or NOT_MEASURED."""
    if suite_coverage_fraction(suite_coverage) is None:
        return NOT_MEASURED
    implemented = suite_coverage.get("implemented_suites") or []
    with_results = suite_coverage.get("suites_with_results") or []
    return f"{len(with_results)} of {len(implemented)} suites"


def fmt_gpu_memory(used_gb: Any, total_gb: Any) -> Tuple[str, str]:
    """(percent used, "used / total GB") for a GPU memory reading; unreported values read NOT_MEASURED."""
    if not is_measured(total_gb) or float(total_gb) <= 0:
        return NOT_MEASURED, NOT_MEASURED
    if not is_measured(used_gb):
        return NOT_MEASURED, f"{NOT_MEASURED} / {float(total_gb):.1f} GB"
    used, total = float(used_gb), float(total_gb)
    return f"{used / total:.1%}", f"{used:.1f} / {total:.1f} GB"
