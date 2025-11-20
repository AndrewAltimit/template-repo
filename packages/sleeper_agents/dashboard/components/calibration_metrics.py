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
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)


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

    # Extract calibration data from model metadata
    auc = getattr(model_metadata, "auc", None)
    baseline_accuracy = getattr(model_metadata, "baseline_accuracy", None)
    optimal_threshold = getattr(model_metadata, "optimal_threshold", None)
    prob_range = getattr(model_metadata, "prob_range", None)

    # Check if calibration data is available
    has_calibration = all(
        [auc is not None, baseline_accuracy is not None, optimal_threshold is not None, prob_range is not None]
    )

    if not has_calibration:
        st.warning(
            "⚠️ **Calibration data not available** for this model. "
            "The probe may not have been calibrated using ROC curve + Youden's J. "
            "Run probe training with calibration to generate this data."
        )
        return

    # Display metrics in columns
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "AUC", f"{auc:.3f}", help="Area Under ROC Curve - measures discrimination ability (0.5 = random, 1.0 = perfect)"
        )

    with col2:
        # Color code accuracy based on threshold
        delta = None
        delta_color = "normal"
        if baseline_accuracy is not None and baseline_accuracy < 0.95:
            delta = "Below threshold"
            delta_color = "inverse"

        st.metric(
            "Calibrated Accuracy",
            f"{baseline_accuracy:.1%}",
            delta=delta,
            delta_color=delta_color,
            help="Accuracy using optimal threshold (should be ≥95% for well-calibrated probes)",
        )

    with col3:
        st.metric(
            "Optimal Threshold",
            f"{optimal_threshold:.4f}",
            help="Threshold that maximizes Youden's J statistic (Sensitivity + Specificity - 1)",
        )

    with col4:
        if prob_range is not None:
            prob_min, prob_max = prob_range
        else:
            prob_min, prob_max = (0.0, 1.0)
        st.metric(
            "Probability Range", f"[{prob_min:.2f}, {prob_max:.2f}]", help="Min and max prediction scores in validation set"
        )

    # Warning for uncalibrated probes
    if show_warning and baseline_accuracy is not None and baseline_accuracy < 0.95:
        st.error(
            f"⚠️ **Low Calibrated Accuracy ({baseline_accuracy:.1%})** - "
            "This probe may be uncalibrated. Expected accuracy ≥95% for AUC=1.0. "
            "Possible causes:\n"
            "- Hardcoded threshold (0.5) instead of optimal threshold\n"
            "- Score distribution shift between training and validation\n"
            "- Probe needs retraining with proper calibration\n\n"
            "**Action Required:** Retrain probe with dynamic threshold finding (ROC + Youden's J)."
        )

    # Explanation of calibration methodology
    if help_text:
        with st.expander("ℹ️ About Calibration Methodology"):
            st.markdown(
                """
            ### Dynamic Threshold Finding

            We use **ROC curve + Youden's J statistic** to find the optimal decision threshold:

            1. **ROC Curve:** Plot True Positive Rate vs False Positive Rate at all thresholds
            2. **Youden's J:** J = Sensitivity + Specificity - 1 (maximizes both metrics)
            3. **Optimal Threshold:** Threshold where J is maximized

            ### Why This Matters

            **Without calibration:**
            - Using hardcoded threshold (0.5) can give wrong accuracy
            - AUC = 1.0 but Accuracy = 56% (score distribution shifted)
            - Misleading performance metrics

            **With calibration:**
            - Optimal threshold adapts to score distribution
            - AUC = 1.0 and Accuracy = 98% (properly calibrated)
            - Trustworthy real-world performance

            ### Expected Values

            For a well-calibrated probe detecting backdoors:
            - **AUC:** ~1.0 (perfect discrimination)
            - **Accuracy:** ≥95% (high precision at optimal threshold)
            - **Threshold:** Varies by model (typically 0.5-0.9999)
            - **Prob Range:** Wide range indicates good separation

            ### Source

            This methodology is based on Phase 3 validation (Gradient Attack Audit):
            - `examples/gradient_attack_audit.py:L600-L650`
            - Implements dynamic threshold finding to prevent false accuracy reports
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
    elif baseline_accuracy >= 0.95:
        return "Well-Calibrated"
    else:
        return "Needs Calibration"
