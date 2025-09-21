"""
Detection Analysis Component
Analyzes detection method performance with ROC curves, confusion matrices, etc.
"""

import logging

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Type hints removed - not used in this module


logger = logging.getLogger(__name__)


def render_detection_analysis(data_loader, cache_manager):
    """Render the detection analysis dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("🔍 Detection Analysis")

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
            else:
                return data_loader.fetch_test_suite_results(model, suite)

        results_df = get_test_results(selected_model, selected_suite)

        if results_df.empty:
            st.info("No results found for the selected criteria.")
            return

        # Render analysis sections
        render_accuracy_metrics(results_df)
        st.markdown("---")
        render_confusion_matrix(results_df)
        st.markdown("---")
        render_roc_curve(results_df)
        st.markdown("---")
        render_confidence_distribution(results_df)


def render_accuracy_metrics(df: pd.DataFrame):
    """Render accuracy metrics overview.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("📈 Detection Metrics")

    # Calculate overall metrics
    metrics = {
        "Overall Accuracy": df["accuracy"].mean() if "accuracy" in df.columns else 0,
        "Average F1 Score": df["f1_score"].mean() if "f1_score" in df.columns else 0,
        "Average Precision": df["precision"].mean() if "precision" in df.columns else 0,
        "Average Recall": df["recall"].mean() if "recall" in df.columns else 0,
    }

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Accuracy", f"{metrics['Overall Accuracy']:.1%}", help="Overall detection accuracy across all tests")

    with col2:
        st.metric("F1 Score", f"{metrics['Average F1 Score']:.1%}", help="Harmonic mean of precision and recall")

    with col3:
        st.metric("Precision", f"{metrics['Average Precision']:.1%}", help="Ratio of true positives to predicted positives")

    with col4:
        st.metric("Recall", f"{metrics['Average Recall']:.1%}", help="Ratio of true positives to actual positives")

    # Metrics by test type
    if "test_type" in df.columns:
        st.markdown("#### Metrics by Test Type")

        test_type_metrics = df.groupby("test_type")[["accuracy", "f1_score", "precision", "recall"]].mean()

        # Create grouped bar chart
        fig = go.Figure()

        for metric in ["accuracy", "f1_score", "precision", "recall"]:
            if metric in test_type_metrics.columns:
                fig.add_trace(
                    go.Bar(
                        name=metric.replace("_", " ").title(),
                        x=test_type_metrics.index,
                        y=test_type_metrics[metric],
                        text=[f"{v:.1%}" for v in test_type_metrics[metric]],
                        textposition="auto",
                    )
                )

        fig.update_layout(
            title="Performance by Test Type",
            xaxis_title="Test Type",
            yaxis_title="Score",
            yaxis=dict(range=[0, 1]),
            barmode="group",
            height=400,
        )

        st.plotly_chart(fig, width="stretch")


def render_confusion_matrix(df: pd.DataFrame):
    """Render confusion matrix visualization.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("🎯 Confusion Matrix")

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
        labels=dict(x="Predicted", y="Actual", color="Count"),
        x=labels,
        y=labels,
        text_auto=True,
        color_continuous_scale="Blues",
        aspect="auto",
    )

    fig.update_layout(title="Aggregated Confusion Matrix", height=400)

    st.plotly_chart(fig, width="stretch")

    # Display metrics derived from confusion matrix
    col1, col2, col3 = st.columns(3)

    with col1:
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        st.metric("Specificity", f"{specificity:.1%}", help="True negative rate")

    with col2:
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        st.metric("Sensitivity", f"{sensitivity:.1%}", help="True positive rate (Recall)")

    with col3:
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        st.metric("False Positive Rate", f"{fpr:.1%}", help="Rate of false alarms")


def render_roc_curve(df: pd.DataFrame):
    """Render ROC curve visualization.

    Args:
        df: DataFrame with evaluation results
    """
    st.subheader("📊 ROC Curve Analysis")

    # Check if we have AUC scores
    if "auc_score" not in df.columns or df["auc_score"].isna().all():
        # Generate synthetic ROC curve from confusion matrix data
        if all(col in df.columns for col in ["true_positives", "false_positives", "true_negatives", "false_negatives"]):
            render_synthetic_roc(df)
        else:
            st.info("ROC curve data not available. Run evaluations with AUC scoring enabled.")
        return

    # Plot ROC curves for different test types
    fig = go.Figure()

    if "test_type" in df.columns:
        for test_type in df["test_type"].unique():
            type_df = df[df["test_type"] == test_type]
            auc_scores = type_df["auc_score"].dropna()

            if len(auc_scores) > 0:
                # Generate ROC curve points
                fpr = np.linspace(0, 1, 100)
                tpr = np.linspace(0, 1, 100) * auc_scores.mean()

                fig.add_trace(
                    go.Scatter(
                        x=fpr,
                        y=tpr,
                        mode="lines",
                        name=f"{test_type} (AUC={auc_scores.mean():.3f})",
                        hovertemplate="FPR: %{x:.2f}<br>TPR: %{y:.2f}",
                    )
                )

    # Add diagonal line
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random Classifier", line=dict(dash="dash", color="gray")))

    fig.update_layout(
        title="ROC Curves by Test Type",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis=dict(range=[0, 1]),
        yaxis=dict(range=[0, 1]),
        height=500,
        hovermode="x unified",
    )

    st.plotly_chart(fig, width="stretch")


def render_synthetic_roc(df: pd.DataFrame):
    """Render synthetic ROC curve from confusion matrix data.

    Args:
        df: DataFrame with confusion matrix columns
    """
    # Calculate TPR and FPR for each test
    tpr_values = []
    fpr_values = []

    for _, row in df.iterrows():
        tp = row.get("true_positives", 0)
        fp = row.get("false_positives", 0)
        tn = row.get("true_negatives", 0)
        fn = row.get("false_negatives", 0)

        if tp + fn > 0:
            tpr = tp / (tp + fn)
            tpr_values.append(tpr)

        if fp + tn > 0:
            fpr = fp / (fp + tn)
            fpr_values.append(fpr)

    if tpr_values and fpr_values:
        # Sort by FPR for proper curve
        sorted_points = sorted(zip(fpr_values, tpr_values))
        fpr_sorted, tpr_sorted = zip(*sorted_points)

        # Add (0,0) and (1,1) for complete curve
        fpr_complete = [0] + list(fpr_sorted) + [1]
        tpr_complete = [0] + list(tpr_sorted) + [1]

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(x=fpr_complete, y=tpr_complete, mode="lines+markers", name="Detection Performance", marker=dict(size=6))
        )

        # Add diagonal
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Random Classifier", line=dict(dash="dash", color="gray"))
        )

        fig.update_layout(
            title="ROC Curve (Synthetic from Confusion Matrix)",
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1]),
            height=500,
        )

        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Insufficient data for ROC curve generation")


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

    fig.update_layout(xaxis=dict(range=[0, 1]), height=400, showlegend=False)

    st.plotly_chart(fig, width="stretch")

    # Statistics
    col1, col2, col3 = st.columns(3)

    confidence_values = df["avg_confidence"].dropna()

    with col1:
        st.metric("Mean Confidence", f"{confidence_values.mean():.2f}", help="Average confidence score across all detections")

    with col2:
        st.metric("Std Deviation", f"{confidence_values.std():.3f}", help="Variability in confidence scores")

    with col3:
        st.metric("Median Confidence", f"{confidence_values.median():.2f}", help="Middle value of confidence scores")
