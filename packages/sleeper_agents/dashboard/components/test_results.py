"""
Test Suite Results Component
Provides detailed analysis of individual test suite performance with drill-down capabilities.
"""

import json
import logging

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)


def render_test_suite_results(data_loader, cache_manager):
    """Render the test suite results dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("🧪 Test Suite Results")

    # Model and suite selection
    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available for analysis. Please run evaluations first.")
        return

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        selected_model = st.selectbox("Select Model", models, help="Choose a model to view test results")

    with col2:
        test_suites = {
            "Basic Detection": "basic",
            "Code Vulnerability": "code_vulnerability",
            "Chain of Thought": "chain_of_thought",
            "Robustness": "robustness",
            "Attention Analysis": "attention",
            "Causal Intervention": "intervention",
            "Advanced Methods": "advanced",
        }
        selected_suite_name = st.selectbox("Test Suite", list(test_suites.keys()), help="Select a test suite to analyze")
        selected_suite = test_suites[selected_suite_name]

    with col3:
        view_mode = st.radio("View Mode", ["Summary", "Detailed"], help="Toggle between summary and detailed views")

    if selected_model:
        # Fetch test suite results
        @cache_manager.cache_decorator
        def get_suite_results(model, suite):
            return data_loader.fetch_test_suite_results(model, suite)

        results_df = get_suite_results(selected_model, selected_suite)

        if results_df.empty:
            st.info(f"No results found for {selected_suite_name} suite on {selected_model}")
            return

        if view_mode == "Summary":
            render_suite_summary(results_df, selected_suite_name)
        else:
            render_detailed_results(results_df, selected_suite_name)


def render_suite_summary(df: pd.DataFrame, suite_name: str):
    """Render summary view of test suite results.

    Args:
        df: DataFrame with test results
        suite_name: Name of the test suite
    """
    st.subheader(f"{suite_name} Summary")

    # Calculate overall metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        overall_accuracy = df["accuracy"].mean() if "accuracy" in df.columns else 0
        st.metric("Suite Accuracy", f"{overall_accuracy:.1%}", help="Average accuracy across all tests in suite")

    with col2:
        overall_f1 = df["f1_score"].mean() if "f1_score" in df.columns else 0
        st.metric("Suite F1 Score", f"{overall_f1:.1%}", help="Average F1 score across all tests")

    with col3:
        total_samples = df["samples_tested"].sum() if "samples_tested" in df.columns else 0
        st.metric("Total Samples", f"{total_samples:,}", help="Total samples tested in this suite")

    with col4:
        test_count = df["test_name"].nunique() if "test_name" in df.columns else 0
        st.metric("Tests Run", test_count, help="Number of unique tests in this suite")

    st.markdown("---")

    # Test performance breakdown
    st.markdown("#### Test Performance Breakdown")

    if "test_name" in df.columns:
        # Group by test name and get latest results
        test_metrics = (
            df.groupby("test_name")
            .agg(
                {
                    "accuracy": "last",
                    "f1_score": "last",
                    "precision": "last",
                    "recall": "last",
                    "samples_tested": "last",
                    "timestamp": "last",
                }
            )
            .reset_index()
        )

        # Create bar chart
        fig = go.Figure()

        metrics_to_plot = ["accuracy", "f1_score", "precision", "recall"]
        colors = px.colors.qualitative.Set2

        for i, metric in enumerate(metrics_to_plot):
            if metric in test_metrics.columns:
                fig.add_trace(
                    go.Bar(
                        name=metric.replace("_", " ").title(),
                        x=test_metrics["test_name"],
                        y=test_metrics[metric],
                        text=[f"{v:.1%}" if pd.notna(v) else "N/A" for v in test_metrics[metric]],
                        textposition="auto",
                        marker_color=colors[i],
                    )
                )

        fig.update_layout(
            title=f"{suite_name} Test Performance",
            xaxis_title="Test Name",
            yaxis_title="Score",
            yaxis={"range": [0, 1]},
            barmode="group",
            height=450,
            xaxis_tickangle=-45,
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Pass/Fail Analysis
    st.markdown("---")
    render_pass_fail_analysis(df, suite_name)

    # Sample distribution
    st.markdown("---")
    render_sample_distribution(df)


def render_detailed_results(df: pd.DataFrame, suite_name: str):
    """Render detailed view of test suite results.

    Args:
        df: DataFrame with test results
        suite_name: Name of the test suite
    """
    st.subheader(f"{suite_name} Detailed Analysis")

    # Test selection
    if "test_name" in df.columns:
        test_names = df["test_name"].unique()
        selected_test = st.selectbox(
            "Select Test for Deep Dive", test_names, help="Choose a specific test to analyze in detail"
        )

        # Filter for selected test
        test_df = df[df["test_name"] == selected_test]

        if test_df.empty:
            st.warning("No data for selected test")
            return

        # Get the most recent run
        latest_run = test_df.iloc[-1]

        # Display test information
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("#### Test Metrics")

            metrics_data = {
                "Metric": ["Accuracy", "F1 Score", "Precision", "Recall", "Avg Confidence"],
                "Value": [
                    f"{latest_run.get('accuracy', 0):.2%}",
                    f"{latest_run.get('f1_score', 0):.2%}",
                    f"{latest_run.get('precision', 0):.2%}",
                    f"{latest_run.get('recall', 0):.2%}",
                    f"{latest_run.get('avg_confidence', 0):.3f}",
                ],
            }

            metrics_df = pd.DataFrame(metrics_data)
            st.dataframe(metrics_df, width="stretch", hide_index=True)

        with col2:
            st.markdown("#### Confusion Matrix Values")

            confusion_data = {
                "Type": ["True Positives", "False Positives", "True Negatives", "False Negatives"],
                "Count": [
                    latest_run.get("true_positives", 0),
                    latest_run.get("false_positives", 0),
                    latest_run.get("true_negatives", 0),
                    latest_run.get("false_negatives", 0),
                ],
            }

            confusion_df = pd.DataFrame(confusion_data)
            st.dataframe(confusion_df, width="stretch", hide_index=True)

        # Layer analysis if available
        if "best_layers" in latest_run and latest_run["best_layers"]:
            st.markdown("---")
            render_layer_analysis(latest_run)

        # Failed samples analysis
        if "failed_samples" in latest_run and latest_run["failed_samples"]:
            st.markdown("---")
            render_failed_samples(latest_run)

        # Historical performance
        if len(test_df) > 1:
            st.markdown("---")
            render_test_history(test_df, selected_test)


def render_pass_fail_analysis(df: pd.DataFrame, suite_name: str):
    """Render pass/fail analysis for the test suite.

    Args:
        df: DataFrame with test results
        suite_name: Name of the test suite
    """
    st.markdown("#### Pass/Fail Analysis")

    # Define pass threshold
    threshold = st.slider(
        "Pass Threshold",
        min_value=0.5,
        max_value=1.0,
        value=0.8,
        step=0.05,
        help="Accuracy threshold for pass/fail determination",
    )

    # Classify tests
    if "test_name" in df.columns and "accuracy" in df.columns:
        test_status = df.groupby("test_name")["accuracy"].last()
        passed_tests = test_status[test_status >= threshold]
        failed_tests = test_status[test_status < threshold]

        col1, col2, col3 = st.columns(3)

        with col1:
            pass_rate = len(passed_tests) / len(test_status) * 100 if len(test_status) > 0 else 0
            st.metric("Pass Rate", f"{pass_rate:.1f}%", help=f"Tests with accuracy >= {threshold:.0%}")

        with col2:
            st.metric("Passed Tests", len(passed_tests), help="Number of passing tests")

        with col3:
            st.metric("Failed Tests", len(failed_tests), help="Number of failing tests")

        # Create pie chart
        if len(test_status) > 0:
            fig = px.pie(
                values=[len(passed_tests), len(failed_tests)],
                names=["Passed", "Failed"],
                title=f"{suite_name} Pass/Fail Distribution",
                color_discrete_map={"Passed": "green", "Failed": "red"},
            )

            fig.update_traces(textposition="inside", textinfo="percent+label")

            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

            # List failed tests
            if len(failed_tests) > 0:
                st.warning(f"**Failed Tests (accuracy < {threshold:.0%}):**")
                for test_name, accuracy in failed_tests.items():
                    st.write(f"- {test_name}: {accuracy:.1%}")


def render_sample_distribution(df: pd.DataFrame):
    """Render sample distribution analysis.

    Args:
        df: DataFrame with test results
    """
    st.markdown("#### Sample Distribution")

    if "samples_tested" in df.columns and "test_name" in df.columns:
        # Sample distribution by test
        sample_dist = df.groupby("test_name")["samples_tested"].sum().sort_values(ascending=True)

        fig = px.bar(
            x=sample_dist.values,
            y=sample_dist.index,
            orientation="h",
            title="Samples Tested by Test",
            labels={"x": "Number of Samples", "y": "Test Name"},
            color=sample_dist.values,
            color_continuous_scale="Viridis",
        )

        fig.update_layout(height=400, showlegend=False)

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

        # Statistics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Samples", f"{sample_dist.sum():,}", help="Total samples across all tests")

        with col2:
            st.metric("Avg per Test", f"{sample_dist.mean():.0f}", help="Average samples per test")

        with col3:
            st.metric("Sample Range", f"{sample_dist.min()}-{sample_dist.max()}", help="Min to max samples per test")


def render_layer_analysis(test_run: pd.Series):
    """Render layer-wise analysis for tests that include layer information.

    Args:
        test_run: Series containing test run data
    """
    st.markdown("#### Layer-wise Analysis")

    best_layers = test_run.get("best_layers", [])
    layer_scores = test_run.get("layer_scores", {})

    if isinstance(layer_scores, str):
        try:
            layer_scores = json.loads(layer_scores)
        except json.JSONDecodeError:
            layer_scores = {}

    if layer_scores:
        # Create layer score plot
        layers = list(layer_scores.keys())
        scores = list(layer_scores.values())

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=layers,
                y=scores,
                marker={"color": scores, "colorscale": "RdYlGn", "cmin": 0, "cmax": 1, "colorbar": {"title": "Score"}},
                text=[f"{s:.2%}" for s in scores],
                textposition="auto",
            )
        )

        # Highlight best layers
        if best_layers:
            best_indices = [i for i, l in enumerate(layers) if l in best_layers]
            if best_indices:
                fig.add_trace(
                    go.Scatter(
                        x=[layers[i] for i in best_indices],
                        y=[scores[i] for i in best_indices],
                        mode="markers",
                        marker={"size": 15, "color": "gold", "symbol": "star"},
                        name="Best Layers",
                        showlegend=True,
                    )
                )

        fig.update_layout(
            title="Layer Performance Scores",
            xaxis_title="Layer",
            yaxis_title="Detection Score",
            yaxis={"range": [0, 1]},
            height=400,
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

        # Display best layers
        if best_layers:
            st.success(f"**Best Performing Layers:** {', '.join(map(str, best_layers))}")


def render_failed_samples(test_run: pd.Series):
    """Render analysis of failed samples.

    Args:
        test_run: Series containing test run data
    """
    st.markdown("#### Failed Samples Analysis")

    failed_samples = test_run.get("failed_samples", [])

    if isinstance(failed_samples, str):
        try:
            failed_samples = json.loads(failed_samples)
        except json.JSONDecodeError:
            failed_samples = []

    if failed_samples:
        st.warning(f"**{len(failed_samples)} samples failed detection**")

        # Show sample failures
        with st.expander("View Failed Samples (First 10)"):
            for i, sample in enumerate(failed_samples[:10]):
                if isinstance(sample, dict):
                    st.markdown(f"**Sample {i+1}:**")
                    if "prompt" in sample:
                        st.text(f"Prompt: {sample['prompt'][:200]}...")
                    if "expected" in sample:
                        st.text(f"Expected: {sample['expected']}")
                    if "predicted" in sample:
                        st.text(f"Predicted: {sample['predicted']}")
                    if "confidence" in sample:
                        st.text(f"Confidence: {sample['confidence']:.3f}")
                    st.markdown("---")
                else:
                    st.text(f"Sample {i+1}: {str(sample)[:200]}...")

        # Failure patterns
        if all(isinstance(s, dict) for s in failed_samples):
            st.markdown("**Failure Patterns:**")

            # Analyze confidence distribution
            confidences = [s.get("confidence", 0) for s in failed_samples if "confidence" in s]
            if confidences:
                avg_conf = np.mean(confidences)
                std_conf = np.std(confidences)
                st.write(f"- Average confidence on failures: {avg_conf:.3f} (±{std_conf:.3f})")

            # Analyze prediction patterns
            predictions = [s.get("predicted") for s in failed_samples if "predicted" in s]
            if predictions:
                from collections import Counter

                pred_counts = Counter(predictions)
                st.write("- Most common incorrect predictions:")
                for pred, count in pred_counts.most_common(3):
                    st.write(f"  - {pred}: {count} times")
    else:
        st.success("No failed samples in this test run")


def render_test_history(df: pd.DataFrame, test_name: str):
    """Render historical performance for a specific test.

    Args:
        df: DataFrame with test results
        test_name: Name of the test
    """
    st.markdown("#### Historical Performance")

    # Sort by timestamp
    df = df.sort_values("timestamp")

    # Create time series plot
    fig = go.Figure()

    metrics = ["accuracy", "f1_score", "precision", "recall"]
    colors = px.colors.qualitative.Set2

    for i, metric in enumerate(metrics):
        if metric in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[metric],
                    mode="lines+markers",
                    name=metric.replace("_", " ").title(),
                    line={"color": colors[i]},
                    hovertemplate="%{y:.1%}<extra></extra>",
                )
            )

    fig.update_layout(
        title=f"{test_name} Performance Over Time",
        xaxis_title="Timestamp",
        yaxis_title="Score",
        yaxis={"range": [0, 1], "tickformat": ".0%"},
        height=400,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Performance statistics
    st.markdown("**Performance Statistics:**")

    stats_data = []
    for metric in metrics:
        if metric in df.columns:
            values = df[metric].dropna()
            if len(values) > 0:
                stats_data.append(
                    {
                        "Metric": metric.replace("_", " ").title(),
                        "Current": f"{values.iloc[-1]:.2%}",
                        "Average": f"{values.mean():.2%}",
                        "Best": f"{values.max():.2%}",
                        "Worst": f"{values.min():.2%}",
                        "Std Dev": f"{values.std():.3%}",
                    }
                )

    if stats_data:
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, width="stretch", hide_index=True)
