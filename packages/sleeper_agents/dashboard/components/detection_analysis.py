"""
Detection Analysis Component
Analyzes detection method performance with ROC curves, confusion matrices, etc.
"""

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.metric_format import NOT_MEASURED, fmt_num, fmt_pct, is_measured, measured_mean, split_evaluation_rows

logger = logging.getLogger(__name__)


def render_detection_analysis(data_loader, cache_manager):
    """Render the detection analysis dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Detection Analysis")

    # Add context explanation - visible by default for clarity
    st.markdown("### Interpreting Detection Metrics")
    st.markdown(
        """
        **Accuracy** alone can be misleading - a model might have 95% accuracy but still miss critical backdoors.
        **Precision** shows how many flagged behaviors are actual backdoors (avoiding false alarms).
        **Recall** reveals how many backdoors we're catching (critical for safety).
        Low recall with high precision means we're missing dangerous behaviors.
        The **confusion matrix** shows exactly what types of behaviors are being misclassified.
        """
    )

    # Model selection
    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available for analysis. Please run evaluations first.")
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_model = st.selectbox("Select Model", models, help="Choose a model to analyze detection performance")

    with col2:
        test_suites = [
            "all",
            "basic",
            "code_vulnerability",
            "chain_of_thought",
            "robustness",
            "attention",
            "intervention",
            "advanced",
        ]
        selected_suite = st.selectbox("Test Suite", test_suites, help="Filter by test suite")

    if selected_model:
        # Fetch results with caching
        @cache_manager.cache_decorator
        def get_test_results(model, suite):
            if suite == "all":
                return data_loader.fetch_latest_results(model)
            return data_loader.fetch_test_suite_results(model, suite)

        results_df = get_test_results(selected_model, selected_suite)

        if results_df.empty:
            st.info("No results found for the selected criteria.")
            return

        results_df, unmeasured_df = split_evaluation_rows(results_df)
        render_unmeasured_tests(unmeasured_df)
        if results_df.empty:
            st.info("No test in the selected criteria produced metrics (all were skipped or errored).")
            return

        # Render analysis sections
        render_accuracy_metrics(results_df)
        st.markdown("---")
        render_confusion_matrix(results_df)
        st.markdown("---")
        render_roc_curve(results_df)
        st.markdown("---")
        render_confidence_distribution(results_df)


def render_unmeasured_tests(unmeasured_df: pd.DataFrame):
    """List evaluation rows that were recorded without metrics (skipped or errored)."""
    if unmeasured_df is None or unmeasured_df.empty:
        return
    columns = [c for c in ["test_name", "test_type", "status", "notes", "timestamp"] if c in unmeasured_df.columns]
    with st.expander(f"{len(unmeasured_df)} test run(s) recorded without metrics (skipped or error)"):
        st.caption("These tests did not produce measurements and are excluded from all metrics below.")
        st.dataframe(unmeasured_df[columns], use_container_width=True, hide_index=True)


def render_accuracy_metrics(df: pd.DataFrame):
    """Render accuracy metrics overview.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("Detection Metrics")

    def _mean(column: str):
        return measured_mean(df[column]) if column in df.columns else None

    # Calculate overall metrics (None when no completed test measured the metric)
    metrics = {
        "Overall Accuracy": _mean("accuracy"),
        "Average F1 Score": _mean("f1_score"),
        "Average Precision": _mean("precision"),
        "Average Recall": _mean("recall"),
    }

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Accuracy", fmt_pct(metrics["Overall Accuracy"]), help="Overall detection accuracy across all tests")

    with col2:
        st.metric("F1 Score", fmt_pct(metrics["Average F1 Score"]), help="Harmonic mean of precision and recall")

    with col3:
        st.metric("Precision", fmt_pct(metrics["Average Precision"]), help="Ratio of true positives to predicted positives")

    with col4:
        st.metric("Recall", fmt_pct(metrics["Average Recall"]), help="Ratio of true positives to actual positives")

    # Metrics by test type
    metric_cols = [c for c in ["accuracy", "f1_score", "precision", "recall"] if c in df.columns]
    if "test_type" in df.columns and metric_cols:
        test_type_metrics = df.groupby("test_type")[metric_cols].mean()
        if test_type_metrics.isna().all().all():
            return

        st.markdown("#### Metrics by Test Type")

        # Create grouped bar chart
        fig = go.Figure()

        for metric in metric_cols:
            fig.add_trace(
                go.Bar(
                    name=metric.replace("_", " ").title(),
                    x=test_type_metrics.index,
                    y=test_type_metrics[metric],
                    text=[fmt_pct(v) for v in test_type_metrics[metric]],
                    textposition="auto",
                )
            )

        fig.update_layout(
            title="Performance by Test Type",
            xaxis_title="Test Type",
            yaxis_title="Score",
            yaxis={"range": [0, 1]},
            barmode="group",
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def render_confusion_matrix(df: pd.DataFrame):
    """Render confusion matrix visualization.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("Confusion Matrix")

    # Calculate confusion matrix values
    tp = df["true_positives"].sum() if "true_positives" in df.columns else 0
    fp = df["false_positives"].sum() if "false_positives" in df.columns else 0
    tn = df["true_negatives"].sum() if "true_negatives" in df.columns else 0
    fn = df["false_negatives"].sum() if "false_negatives" in df.columns else 0

    if tp + fp + tn + fn == 0:
        st.info("No confusion matrix data available")
        return

    # Create confusion matrix
    matrix = [[tn, fp], [fn, tp]]
    labels = ["Negative", "Positive"]

    # Create heatmap
    fig = px.imshow(
        matrix,
        labels={"x": "Predicted", "y": "Actual", "color": "Count"},
        x=labels,
        y=labels,
        text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
    )

    fig.update_layout(title="Aggregated Confusion Matrix", height=400)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Display metrics derived from confusion matrix
    col1, col2, col3 = st.columns(3)

    with col1:
        specificity = tn / (tn + fp) if (tn + fp) > 0 else None
        st.metric("Specificity", fmt_pct(specificity), help="True negative rate")

    with col2:
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else None
        st.metric("Sensitivity", fmt_pct(sensitivity), help="True positive rate (Recall)")

    with col3:
        fpr = fp / (fp + tn) if (fp + tn) > 0 else None
        st.metric("False Positive Rate", fmt_pct(fpr), help="Rate of false alarms")


def render_roc_curve(df: pd.DataFrame):
    """Render stored AUC scores and measured operating points.

    Evaluation results store a single AUC and one confusion matrix per test, not
    the score distributions a ROC curve is drawn from, so no curve is plotted.
    The view shows the stored AUC per test type and each test's measured
    (FPR, TPR) operating point.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("ROC Analysis")

    if "auc_score" in df.columns and not df["auc_score"].isna().all() and "test_type" in df.columns:
        auc_by_type = df.groupby("test_type")["auc_score"].agg(["mean", "count"]).dropna(subset=["mean"])
        auc_table = pd.DataFrame(
            {
                "Test type": auc_by_type.index,
                "Mean AUC": [fmt_num(v, 3) for v in auc_by_type["mean"]],
                "Tests with AUC": auc_by_type["count"].astype(int).values,
            }
        )
        st.dataframe(auc_table, use_container_width=True, hide_index=True)
    else:
        st.caption(f"AUC: {NOT_MEASURED} (no completed test stored an AUC score)")

    points = operating_points(df)
    if not points:
        st.info("No test stored a confusion matrix with both positive and negative samples; no operating points to show.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[p["fpr"] for p in points],
            y=[p["tpr"] for p in points],
            mode="markers",
            name="Measured operating point",
            text=[p["label"] for p in points],
            marker={"size": 9},
            hovertemplate="%{text}<br>FPR: %{x:.2f}<br>TPR: %{y:.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random Classifier", line={"dash": "dash", "color": "gray"})
    )
    fig.update_layout(
        title="Measured Operating Points (one per test run)",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1]},
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})
    st.caption("Each point is one test run's threshold; points from different tests are not joined into a curve.")


def operating_points(df: pd.DataFrame) -> list:
    """Return measured (FPR, TPR) points for rows with a usable confusion matrix.

    Rows missing any confusion-matrix count, or lacking positives or negatives,
    are skipped rather than treated as zero.
    """
    columns = ["true_positives", "false_positives", "true_negatives", "false_negatives"]
    if not all(col in df.columns for col in columns):
        return []

    points = []
    for _, row in df.iterrows():
        counts = [row.get(col) for col in columns]
        if not all(is_measured(c) for c in counts):
            continue
        tp, fp, tn, fn = (float(c) for c in counts)
        if tp + fn <= 0 or fp + tn <= 0:
            continue
        points.append(
            {
                "fpr": fp / (fp + tn),
                "tpr": tp / (tp + fn),
                "label": str(row.get("test_name") or row.get("test_type") or "test"),
            }
        )
    return points


def render_confidence_distribution(df: pd.DataFrame):
    """Render confidence score distribution.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("🎲 Confidence Distribution")

    if "avg_confidence" not in df.columns or df["avg_confidence"].isna().all():
        st.info("Confidence scores not available")
        return

    # Create histogram of confidence scores
    fig = px.histogram(
        df,
        x="avg_confidence",
        nbins=20,
        title="Detection Confidence Distribution",
        labels={"avg_confidence": "Confidence Score", "count": "Frequency"},
        color_discrete_sequence=["#636EFA"],
    )

    fig.update_layout(xaxis={"range": [0, 1]}, height=400, showlegend=False)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Statistics
    col1, col2, col3 = st.columns(3)

    confidence_values = df["avg_confidence"].dropna()

    with col1:
        st.metric("Mean Confidence", f"{confidence_values.mean():.2f}", help="Average confidence score across all detections")

    with col2:
        st.metric("Std Deviation", f"{confidence_values.std():.3f}", help="Variability in confidence scores")

    with col3:
        st.metric("Median Confidence", f"{confidence_values.median():.2f}", help="Middle value of confidence scores")
