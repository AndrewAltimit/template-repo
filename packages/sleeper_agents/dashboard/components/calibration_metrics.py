"""
Calibration Metrics Component

Reusable component for displaying probe calibration metrics across all dashboard views.
Implements Phase 3 validation requirements: dynamic threshold finding (ROC + Youden's J).

Usage:
    from components.calibration_metrics import render_calibration_metrics

    # In any dashboard component
    render_calibration_metrics(model_metadata)
"""

import logging
from typing import Any, Dict, Literal

import streamlit as st

from utils.metric_format import NOT_MEASURED, fmt_num, fmt_pct, is_measured

logger = logging.getLogger(__name__)


def calibration_display_values(model_metadata: Any) -> Dict[str, str]:
    """Display strings for the calibration metrics; each missing value reads NOT_MEASURED.

    A probability range is shown only when both bounds were recorded (never a
    default [0, 1]).
    """
    prob_range = getattr(model_metadata, "prob_range", None)
    prob_text = NOT_MEASURED
    if isinstance(prob_range, (list, tuple)) and len(prob_range) == 2 and all(is_measured(v) for v in prob_range):
        prob_text = f"[{float(prob_range[0]):.2f}, {float(prob_range[1]):.2f}]"
    return {
        "auc": fmt_num(getattr(model_metadata, "auc", None), 3),
        "baseline_accuracy": fmt_pct(getattr(model_metadata, "baseline_accuracy", None)),
        "optimal_threshold": fmt_num(getattr(model_metadata, "optimal_threshold", None), 4),
        "prob_range": prob_text,
    }


def render_calibration_metrics(model_metadata: Any, show_warning: bool = True, help_text: bool = True) -> None:
    """Render calibration metrics for a trained probe.

    Displays:
    - AUC (discrimination ability)
    - Calibrated Accuracy (using optimal threshold)
    - Optimal Threshold (from ROC curve + Youden's J)
    - Probability Range (min/max scores)

    Args:
        model_metadata: Model metadata object with calibration data
        show_warning: Show warning if accuracy < 95% (default: True)
        help_text: Show help text on metrics (default: True)
    """
    st.markdown("### 🎯 Calibration Metrics")

    if help_text:
        st.caption(
            "Calibration ensures the probe's predictions are properly scaled. "
            "The optimal threshold is found using ROC curve + Youden's J statistic, "
            "balancing sensitivity and specificity for best real-world performance."
        )

    baseline_accuracy = getattr(model_metadata, "baseline_accuracy", None)
    values = calibration_display_values(model_metadata)

    if all(value == NOT_MEASURED for value in values.values()):
        st.warning(
            "⚠️ **Calibration data not available** for this model. "
            "The probe may not have been calibrated using ROC curve + Youden's J. "
            "Run probe training with calibration to generate this data."
        )
        return

    # Display metrics in columns; each missing value reads "Not measured"
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "AUC", values["auc"], help="Area Under ROC Curve - measures discrimination ability (0.5 = random, 1.0 = perfect)"
        )

    with col2:
        # Color code accuracy based on threshold
        delta = None
        delta_color: Literal["normal", "inverse", "off"] = "normal"
        if is_measured(baseline_accuracy) and baseline_accuracy < 0.95:
            delta = "Below threshold"
            delta_color = "inverse"

        st.metric(
            "Calibrated Accuracy",
            values["baseline_accuracy"],
            delta=delta,
            delta_color=delta_color,
            help="Accuracy at the threshold calibrated on held-out validation data",
        )

    with col3:
        st.metric(
            "Optimal Threshold",
            values["optimal_threshold"],
            help="Threshold that maximizes Youden's J statistic (Sensitivity + Specificity - 1)",
        )

    with col4:
        st.metric("Probability Range", values["prob_range"], help="Min and max prediction scores in validation set")

    # Warning for uncalibrated probes
    if show_warning and is_measured(baseline_accuracy) and baseline_accuracy < 0.95:
        st.error(
            f"**Low Calibrated Accuracy ({baseline_accuracy:.1%})** - "
            "accuracy at the calibrated threshold is below 95%. A high AUC with low "
            "accuracy usually means the threshold does not fit the score distribution "
            "(e.g. a fixed 0.5 threshold, or scores shifted between the calibration and "
            "evaluation data). Recalibrate the threshold on a held-out validation split."
        )

    # Explanation of calibration methodology
    if help_text:
        with st.expander("About Calibration Methodology"):
            st.markdown(
                """
            ### Threshold calibration

            AUC measures ranking only; accuracy also depends on the decision threshold.
            The threshold is chosen on a **held-out validation split** (for example by
            Youden's J = sensitivity + specificity - 1) and accuracy is then reported on
            a separate test split. Choosing the threshold on the same samples that are
            scored inflates the reported accuracy.

            ### Reading the values

            - **AUC:** ranking quality on held-out data (0.5 = chance)
            - **Calibrated accuracy:** accuracy at the calibrated threshold
            - **Optimal threshold:** depends on the model and probe; not a quality measure
            - **Probability range:** spread of scores on the validation set

            See `docs/PROBE_CALIBRATION.md` for the full procedure.
            """
            )


def render_calibration_warning_banner(model_metadata: Any) -> None:
    """Render a banner warning if probe is uncalibrated.

    Shows prominent warning at top of dashboard if calibration data is missing
    or accuracy is below threshold.

    Args:
        model_metadata: Model metadata object with calibration data
    """
    baseline_accuracy = getattr(model_metadata, "baseline_accuracy", None)

    if baseline_accuracy is None:
        st.warning(
            "⚠️ **Missing Calibration Data** - This model has not been calibrated. "
            "Results may not reflect real-world performance. "
            "Please retrain the probe with calibration enabled."
        )
    elif baseline_accuracy < 0.95:
        st.error(
            f"⚠️ **Uncalibrated Probe Detected** - "
            f"Baseline accuracy ({baseline_accuracy:.1%}) is below 95%. "
            f"This indicates the probe is not properly calibrated. "
            f"Metrics shown may be unreliable for deployment decisions."
        )


def get_calibration_status(model_metadata: Any) -> str:
    """Get calibration status as a string.

    Args:
        model_metadata: Model metadata object with calibration data

    Returns:
        Status string: "Well-Calibrated", "Needs Calibration", or "Not Calibrated"
    """
    baseline_accuracy = getattr(model_metadata, "baseline_accuracy", None)

    if baseline_accuracy is None:
        return "Not Calibrated"
    if baseline_accuracy >= 0.95:
        return "Well-Calibrated"
    return "Needs Calibration"
