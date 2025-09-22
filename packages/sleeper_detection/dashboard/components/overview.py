"""
Executive Overview Component
Provides high-level summary and key metrics for model safety evaluation.
"""

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)


def render_overview(data_loader, cache_manager):
    """Render the executive overview dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("📊 Executive Overview")

    # Check database connection
    db_info = data_loader.get_database_info()

    if not db_info.get("database_exists", False):
        st.warning("⚠️ No evaluation database found. Please run some evaluations first.")
        st.info("Run evaluations using: `python -m packages.sleeper_detection.cli evaluate <model>`")
        return

    if db_info.get("error"):
        st.error(f"Database error: {db_info['error']}")
        return

    # Display database stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Evaluations", db_info.get("total_records", 0), help="Total number of evaluation tests run")

    with col2:
        st.metric("Models Tested", db_info.get("total_models", 0), help="Number of unique models evaluated")

    with col3:
        date_range = db_info.get("date_range", {})
        if date_range.get("start"):
            st.metric(
                "First Test", date_range["start"][:10] if date_range["start"] else "N/A", help="Date of first evaluation"
            )
        else:
            st.metric("First Test", "N/A")

    with col4:
        if date_range.get("end"):
            st.metric(
                "Latest Test", date_range["end"][:10] if date_range["end"] else "N/A", help="Date of most recent evaluation"
            )
        else:
            st.metric("Latest Test", "N/A")

    st.markdown("---")

    # Model selection
    models = data_loader.fetch_models()

    if not models:
        st.info("No models evaluated yet. Run evaluations to see results here.")
        return

    selected_model = st.selectbox("Select Model for Detailed View", models, help="Choose a model to see detailed metrics")

    if selected_model:
        render_model_overview(selected_model, data_loader, cache_manager)


def render_model_overview(model_name: str, data_loader, cache_manager):
    """Render overview for a specific model.

    Args:
        model_name: Name of the model
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """

    # Fetch model summary with caching
    @cache_manager.cache_decorator
    def get_model_summary(model):
        return data_loader.fetch_model_summary(model)

    summary = get_model_summary(model_name)

    if not summary:
        st.warning(f"No data found for model: {model_name}")
        return

    # Safety Score Gauge
    col1, col2 = st.columns([1, 2])

    with col1:
        render_safety_gauge(summary)

    with col2:
        render_risk_assessment(summary)

    st.markdown("---")

    # Test Type Breakdown
    st.subheader("Test Suite Performance")

    if summary.get("test_types"):
        render_test_breakdown(summary["test_types"])
    else:
        st.info("No test suite data available")

    # Recent Results
    st.markdown("---")
    st.subheader("Recent Evaluation History")

    recent_results = data_loader.fetch_latest_results(model_name, limit=10)
    if not recent_results.empty:
        render_recent_results(recent_results)
    else:
        st.info("No recent results to display")


def render_safety_gauge(summary: dict):
    """Render safety score gauge chart.

    Args:
        summary: Model summary dictionary
    """
    overall_score = summary.get("overall_score", 0)
    if overall_score is None:
        overall_score = summary.get("avg_accuracy", 0) or 0

    # Determine color based on score
    if overall_score >= 0.85:
        color = "green"
        status = "Low Risk"
    elif overall_score >= 0.7:
        color = "yellow"
        status = "Moderate Risk"
    else:
        color = "red"
        status = "High Risk"

    # Create gauge chart
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=overall_score * 100,
            title={"text": "Overall Safety Score"},
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [None, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 70], "color": "lightgray"},
                    {"range": [70, 85], "color": "lightyellow"},
                    {"range": [85, 100], "color": "lightgreen"},
                ],
                "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 70},
            },
        )
    )

    fig.update_layout(height=300)
    st.plotly_chart(fig, width="stretch")
    st.metric("Risk Level", status, help="Based on overall safety score")


def render_risk_assessment(summary: dict):
    """Render risk assessment matrix.

    Args:
        summary: Model summary dictionary
    """
    st.subheader("Risk Assessment Matrix")

    # Create risk metrics
    metrics = {
        "Detection Accuracy": summary.get("avg_accuracy", 0) or 0,
        "F1 Score": summary.get("avg_f1", 0) or 0,
        "Precision": summary.get("avg_precision", 0) or 0,
        "Recall": summary.get("avg_recall", 0) or 0,
        "Robustness": summary.get("robustness_score", 0) or 0,
        "Vulnerability": 1 - (summary.get("vulnerability_score", 1) or 1),
    }

    # Create radar chart
    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=[v * 100 for v in metrics.values()], theta=list(metrics.keys()), fill="toself", name="Model Performance"
        )
    )

    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, height=350)

    st.plotly_chart(fig, width="stretch")

    # Display key vulnerabilities
    if metrics["Vulnerability"] < 0.5:
        st.warning("⚠️ High vulnerability detected - Model may be susceptible to backdoors")
    if metrics["Recall"] < 0.6:
        st.warning("⚠️ Low recall - Model may miss backdoor triggers")


def render_test_breakdown(test_types: dict):
    """Render test type breakdown chart.

    Args:
        test_types: Dictionary of test type statistics
    """
    if not test_types:
        st.info("No test type data available")
        return

    # Prepare data for visualization
    data = []
    for test_type, stats in test_types.items():
        data.append({"Test Type": test_type.title(), "Count": stats["count"], "Accuracy": stats.get("avg_accuracy", 0) or 0})

    df = pd.DataFrame(data)

    # Create bar chart
    fig = px.bar(
        df,
        x="Test Type",
        y="Count",
        color="Accuracy",
        color_continuous_scale="RdYlGn",
        labels={"Count": "Number of Tests", "Accuracy": "Avg Accuracy"},
        title="Test Suite Coverage",
    )

    st.plotly_chart(fig, width="stretch")


def render_recent_results(df: pd.DataFrame):
    """Render recent evaluation results table.

    Args:
        df: DataFrame with recent results
    """
    # Prepare display columns
    display_cols = ["test_name", "test_type", "accuracy", "f1_score", "samples_tested", "timestamp"]

    # Filter columns that exist
    available_cols = [col for col in display_cols if col in df.columns]

    # Format the dataframe
    display_df = df[available_cols].copy()

    # Format numeric columns
    if "accuracy" in display_df.columns:
        display_df["accuracy"] = display_df["accuracy"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    if "f1_score" in display_df.columns:
        display_df["f1_score"] = display_df["f1_score"].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
    if "timestamp" in display_df.columns:
        display_df["timestamp"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")

    # Rename columns for display
    column_names = {
        "test_name": "Test",
        "test_type": "Type",
        "accuracy": "Accuracy",
        "f1_score": "F1",
        "samples_tested": "Samples",
        "timestamp": "Date",
    }
    display_df.rename(columns=column_names, inplace=True)

    # Display table
    st.dataframe(display_df, width="stretch", hide_index=True, height=400)
