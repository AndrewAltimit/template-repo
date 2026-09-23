"""Helpers for displaying metrics that may not have been measured.

DataLoader returns None for metrics without underlying data. These helpers keep
components from turning a missing measurement into a plausible-looking number.
"""

import math
from typing import Any, Iterable, List, Optional

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
