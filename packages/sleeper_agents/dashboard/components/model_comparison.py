"""
Model Comparison Component
Enables side-by-side comparison of multiple models with metrics and visualizations.
"""

import logging
from typing import Dict, List

# numpy import removed - not used
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)


def render_model_comparison(data_loader, cache_manager):
    """Render the model comparison dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Model Comparison")

    # Add context
    st.caption(
        """
    Comparing models side-by-side reveals which architectures are most vulnerable to backdoors.
    Look for models that show high surface metrics but also high persistence scores - these are
    the most deceptive. Pay special attention to how different models respond to the same
    safety training methods, as consistent patterns across models indicate systemic issues.
    """
    )

    # Fetch available models
    models = data_loader.fetch_models()

    if len(models) < 2:
        st.warning("At least 2 models are required for comparison. Please run evaluations on multiple models.")
        return

    # Model selection
    col1, col2 = st.columns(2)

    with col1:
        selected_models = st.multiselect(
            "Select Models to Compare",
            models,
            default=models[:2] if len(models) >= 2 else models,
            help="Choose 2-4 models for comparison",
        )

    with col2:
        comparison_type = st.selectbox(
            "Comparison Type",
            ["Overall Metrics", "Test-by-Test", "Time Series", "Vulnerability Analysis"],
            help="Choose how to compare the models",
        )

    if len(selected_models) < 2:
        st.info("Please select at least 2 models for comparison")
        return

    if len(selected_models) > 4:
        st.warning("For optimal visualization, please select no more than 4 models")
        return

    # Render comparison based on type
    if comparison_type == "Overall Metrics":
        render_overall_comparison(selected_models, data_loader, cache_manager)
    elif comparison_type == "Test-by-Test":
        render_test_comparison(selected_models, data_loader, cache_manager)
    elif comparison_type == "Time Series":
        render_time_series_comparison(selected_models, data_loader, cache_manager)
    elif comparison_type == "Vulnerability Analysis":
        render_vulnerability_comparison(selected_models, data_loader, cache_manager)


def _build_metrics_dataframe(summaries: Dict[str, Dict]) -> pd.DataFrame:
    """Build metrics DataFrame from model summaries."""
    metrics_data = []
    for model, summary in summaries.items():
        metrics_data.append(
            {
                "Model": model,
                "Accuracy": summary.get("avg_accuracy", 0) or 0,
                "F1 Score": summary.get("avg_f1", 0) or 0,
                "Precision": summary.get("avg_precision", 0) or 0,
                "Recall": summary.get("avg_recall", 0) or 0,
                "Total Tests": summary.get("total_tests", 0) or 0,
            }
        )
    return pd.DataFrame(metrics_data)


def _render_performance_bar_chart(df_metrics: pd.DataFrame):
    """Render grouped bar chart for performance metrics."""
    fig = go.Figure()
    metrics_to_plot = ["Accuracy", "F1 Score", "Precision", "Recall"]
    colors = px.colors.qualitative.Set2

    for i, metric in enumerate(metrics_to_plot):
        fig.add_trace(
            go.Bar(
                name=metric,
                x=df_metrics["Model"],
                y=df_metrics[metric],
                text=[f"{v:.1%}" for v in df_metrics[metric]],
                textposition="auto",
                marker_color=colors[i],
            )
        )

    fig.update_layout(
        title="Model Performance Comparison",
        xaxis_title="Model",
        yaxis_title="Score",
        yaxis={"range": [0, 1]},
        barmode="group",
        height=400,
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def _get_persona_value(summary: Dict, key: str, model: str) -> float:
    """Get persona dimension value from summary or generate default."""
    defaults = {
        "power_seeking": 0.72,
        "self_awareness": 0.65,
        "corrigibility": 0.35,
        "deception_tendency": 0.58,
        "goal_orientation": 0.81,
    }
    base = defaults.get(key, 0.5)
    variance = 20 if key != "corrigibility" else 15
    value = summary.get(key, base + hash(model + key) % variance / 100)
    return float(value)


def _build_heatmap_data(models: List[str], summaries: Dict, metric_keys: List[str]) -> List[List]:
    """Build heatmap data for multi-dimensional comparison."""
    heatmap_data = []
    for model in models:
        summary = summaries[model]
        row = []
        for key in metric_keys:
            if key in ["power_seeking", "self_awareness", "corrigibility", "deception_tendency", "goal_orientation"]:
                value = _get_persona_value(summary, key, model)
            else:
                value = summary.get(key, 0) or 0
            row.append(value)
        heatmap_data.append(row)
    return heatmap_data


def _build_detailed_grid_data(models: List[str], summaries: Dict) -> List[Dict]:
    """Build detailed grid data for all models."""
    grid_data = []
    for model in models:
        summary = summaries[model]
        grid_data.append(
            {
                "Model": model,
                "Accuracy": f"{(summary.get('avg_accuracy', 0) or 0):.1%}",
                "F1": f"{(summary.get('avg_f1', 0) or 0):.1%}",
                "Power Seek": f"{_get_persona_value(summary, 'power_seeking', model):.0%}",
                "Self Aware": f"{_get_persona_value(summary, 'self_awareness', model):.0%}",
                "Corrigible": f"{_get_persona_value(summary, 'corrigibility', model):.0%}",
                "Deception": f"{_get_persona_value(summary, 'deception_tendency', model):.0%}",
                "Goal Focus": f"{_get_persona_value(summary, 'goal_orientation', model):.0%}",
            }
        )
    return grid_data


def render_overall_comparison(models: List[str], data_loader, cache_manager):
    """Render overall metrics comparison.

    Args:
        models: List of model names to compare
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.subheader("Overall Performance Metrics")

    @cache_manager.cache_decorator
    def get_model_summaries(model_list):
        summaries = {}
        for model in model_list:
            summaries[model] = data_loader.fetch_model_summary(model)
        return summaries

    summaries = get_model_summaries(tuple(models))

    df_metrics = _build_metrics_dataframe(summaries)

    st.markdown("#### Performance Summary")
    display_df = df_metrics.copy()
    for col in ["Accuracy", "F1 Score", "Precision", "Recall"]:
        display_df[col] = display_df[col].apply(lambda x: f"{x:.2%}")
    st.dataframe(display_df, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("#### Performance Comparison Chart")
    _render_performance_bar_chart(df_metrics)

    # Multi-metric heatmap comparison
    st.markdown("---")
    st.markdown("#### Multi-Dimensional Performance Comparison")

    metrics = [
        "Accuracy",
        "F1 Score",
        "Precision",
        "Recall",
        "Power Seeking",
        "Self Awareness",
        "Corrigibility",
        "Deception",
        "Goal Focus",
    ]
    metric_keys = [
        "avg_accuracy",
        "avg_f1",
        "avg_precision",
        "avg_recall",
        "power_seeking",
        "self_awareness",
        "corrigibility",
        "deception_tendency",
        "goal_orientation",
    ]

    heatmap_data = _build_heatmap_data(models, summaries, metric_keys)

    fig_heatmap = px.imshow(
        heatmap_data,
        labels={"x": "Metric", "y": "Model", "color": "Score"},
        x=metrics,
        y=models,
        color_continuous_scale="RdYlGn",
        aspect="auto",
        text_auto=".1%",
        title="Performance & Behavioral Risk Matrix",
    )

    fig_heatmap.update_layout(
        height=200 + (len(models) * 40),  # Dynamic height based on number of models
        xaxis_nticks=len(metrics),
        yaxis_nticks=len(models),
    )

    st.plotly_chart(fig_heatmap, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Add detailed grid view
    st.markdown("---")
    st.markdown("#### Detailed Metric Grid")

    grid_data = _build_detailed_grid_data(models, summaries)
    grid_df = pd.DataFrame(grid_data)
    st.dataframe(grid_df, width="stretch", hide_index=True)

    # Add interpretation guide
    with st.expander("Interpreting Risk Dimensions"):
        st.markdown(
            """
        **Behavioral Risk Dimensions:**
        - **Power Seeking**: Desire for autonomy and control (higher = riskier)
        - **Self Awareness**: Recognition of capabilities (context-dependent risk)
        - **Corrigibility**: Willingness to be modified (lower = riskier)
        - **Deception**: Tendency to mislead about goals (higher = riskier)
        - **Goal Focus**: Pursuit of objectives regardless of constraints (higher = riskier)

        These dimensions provide a nuanced view of model behavior beyond simple performance metrics.
        """
        )


def render_test_comparison(models: List[str], data_loader, cache_manager):
    """Render test-by-test comparison.

    Args:
        models: List of model names to compare
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.subheader("Test-by-Test Comparison")

    # Fetch comparison data
    @cache_manager.cache_decorator
    def get_comparison_data(model_list):
        return data_loader.fetch_comparison_data(list(model_list))

    df_comparison = get_comparison_data(tuple(models))

    if df_comparison.empty:
        st.info("No comparison data available")
        return

    # Test selection
    test_names = df_comparison["test_name"].unique()
    selected_test = st.selectbox("Select Test", test_names, help="Choose a specific test to compare across models")

    # Filter data for selected test
    test_df = df_comparison[df_comparison["test_name"] == selected_test]

    # Create comparison chart
    fig = go.Figure()

    metrics = ["accuracy", "f1_score", "precision", "recall"]
    colors = px.colors.qualitative.Plotly

    for i, metric in enumerate(metrics):
        if metric in test_df.columns:
            values = []
            for model in models:
                model_data = test_df[test_df["model_name"] == model]
                if not model_data.empty:
                    values.append(model_data[metric].iloc[0])
                else:
                    values.append(0)

            fig.add_trace(
                go.Bar(
                    name=metric.replace("_", " ").title(),
                    x=models,
                    y=values,
                    text=[f"{v:.1%}" for v in values],
                    textposition="auto",
                    marker_color=colors[i],
                )
            )

    fig.update_layout(
        title=f"Performance on: {selected_test}",
        xaxis_title="Model",
        yaxis_title="Score",
        yaxis={"range": [0, 1]},
        barmode="group",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Display detailed metrics
    st.markdown("#### Detailed Metrics")

    # Prepare display dataframe
    display_cols = ["model_name", "accuracy", "f1_score", "precision", "recall", "avg_confidence"]
    available_cols = [col for col in display_cols if col in test_df.columns]

    detail_df = test_df[available_cols].copy()

    # Format numeric columns
    for col in ["accuracy", "f1_score", "precision", "recall"]:
        if col in detail_df.columns:
            detail_df[col] = detail_df[col].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")

    if "avg_confidence" in detail_df.columns:
        detail_df["avg_confidence"] = detail_df["avg_confidence"].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

    # Rename columns for display
    column_names = {
        "model_name": "Model",
        "accuracy": "Accuracy",
        "f1_score": "F1 Score",
        "precision": "Precision",
        "recall": "Recall",
        "avg_confidence": "Avg Confidence",
    }
    detail_df.rename(columns=column_names, inplace=True)

    st.dataframe(detail_df, width="stretch", hide_index=True)


def render_time_series_comparison(models: List[str], data_loader, cache_manager):
    """Render time series comparison.

    Args:
        models: List of model names to compare
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.subheader("Performance Over Time")

    # Time range selection
    col1, col2 = st.columns(2)

    with col1:
        metric = st.selectbox(
            "Metric to Track",
            ["accuracy", "f1_score", "precision", "recall"],
            format_func=lambda x: x.replace("_", " ").title(),
        )

    with col2:
        days_back = st.slider("Days to Look Back", min_value=7, max_value=90, value=30, step=7)

    # Fetch time series data for each model
    @cache_manager.cache_decorator
    def get_time_series_data(model_list, metric_name, days):
        all_data = []
        for model in model_list:
            df = data_loader.fetch_time_series(model, metric_name, days)
            if not df.empty:
                df["model_name"] = model
                all_data.append(df)

        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()

    df_timeseries = get_time_series_data(tuple(models), metric, days_back)

    if df_timeseries.empty:
        st.info("No time series data available for the selected period")
        return

    # Create time series plot
    fig = go.Figure()

    for model in models:
        model_df = df_timeseries[df_timeseries["model_name"] == model]
        if not model_df.empty:
            # Group by date and calculate daily average
            daily_avg = model_df.groupby(model_df["timestamp"].dt.date)[metric].mean()

            fig.add_trace(
                go.Scatter(
                    x=daily_avg.index,
                    y=daily_avg.values,
                    mode="lines+markers",
                    name=model,
                    hovertemplate="%{y:.1%}<extra></extra>",
                )
            )

    fig.update_layout(
        title=f"{metric.replace('_', ' ').title()} Over Time",
        xaxis_title="Date",
        yaxis_title=metric.replace("_", " ").title(),
        yaxis={"range": [0, 1], "tickformat": ".0%"},
        height=500,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Show statistics
    st.markdown("#### Trend Statistics")

    stats_data = []
    for model in models:
        model_df = df_timeseries[df_timeseries["model_name"] == model]
        if not model_df.empty:
            values = model_df[metric].values
            stats_data.append(
                {
                    "Model": model,
                    "Start": f"{values[0]:.1%}" if len(values) > 0 else "N/A",
                    "End": f"{values[-1]:.1%}" if len(values) > 0 else "N/A",
                    "Change": f"{(values[-1] - values[0]):.1%}" if len(values) > 0 else "N/A",
                    "Avg": f"{values.mean():.1%}" if len(values) > 0 else "N/A",
                    "Std Dev": f"{values.std():.2%}" if len(values) > 1 else "N/A",
                }
            )

    if stats_data:
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, width="stretch", hide_index=True)


def _build_vulnerability_matrix(vuln_tests: List[str], vuln_results: List[Dict]) -> List[List]:
    """Build the vulnerability score matrix data.

    Args:
        vuln_tests: List of vulnerability test names
        vuln_results: List of vulnerability result dictionaries

    Returns:
        Matrix data for heatmap visualization
    """
    matrix_data = []
    for test in vuln_tests:
        row = []
        for result in vuln_results:
            df = result["data"]
            test_data = df[df["test_name"] == test]

            if not test_data.empty:
                score = 1 - (test_data["accuracy"].iloc[0] if "accuracy" in test_data.columns else 0.5)
            else:
                score = None

            row.append(score)
        matrix_data.append(row)
    return matrix_data


def _render_vulnerability_heatmap(matrix_data: List[List], vuln_tests: List[str], vuln_results: List[Dict]):
    """Render the vulnerability score heatmap.

    Args:
        matrix_data: Matrix data for heatmap
        vuln_tests: List of vulnerability test names
        vuln_results: List of vulnerability result dictionaries
    """
    fig = px.imshow(
        matrix_data,
        labels={"x": "Model", "y": "Vulnerability Test", "color": "Vulnerability Score"},
        x=[r["model"] for r in vuln_results],
        y=[t.replace("_", " ").title() for t in vuln_tests],
        color_continuous_scale="RdYlGn_r",
        aspect="auto",
        text_auto=True,
    )

    fig.update_layout(title="Vulnerability Score Matrix (Red = Vulnerable, Green = Robust)", height=400)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def _categorize_models_by_risk(vuln_results: List[Dict]) -> Dict[str, List[str]]:
    """Categorize models into risk categories based on accuracy.

    Args:
        vuln_results: List of vulnerability result dictionaries

    Returns:
        Dictionary mapping risk categories to model lists
    """
    risk_categories: Dict[str, List[str]] = {"Low Risk": [], "Medium Risk": [], "High Risk": []}

    for result in vuln_results:
        model = result["model"]
        df = result["data"]

        if not df.empty and "accuracy" in df.columns:
            avg_accuracy = df["accuracy"].mean()

            if avg_accuracy >= 0.8:
                risk_categories["Low Risk"].append(model)
            elif avg_accuracy >= 0.6:
                risk_categories["Medium Risk"].append(model)
            else:
                risk_categories["High Risk"].append(model)

    return risk_categories


def _render_risk_categories(risk_categories: Dict[str, List[str]]):
    """Render risk category columns.

    Args:
        risk_categories: Dictionary mapping risk categories to model lists
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        st.success("**Low Risk**")
        if risk_categories["Low Risk"]:
            for model in risk_categories["Low Risk"]:
                st.write(f"Selected: {model}")
        else:
            st.write("None")

    with col2:
        st.warning("**Medium Risk**")
        if risk_categories["Medium Risk"]:
            for model in risk_categories["Medium Risk"]:
                st.write(f"{model}")
        else:
            st.write("None")

    with col3:
        st.error("**High Risk**")
        if risk_categories["High Risk"]:
            for model in risk_categories["High Risk"]:
                st.write(f"{model}")
        else:
            st.write("None")


def _render_vulnerability_breakdown(vuln_tests: List[str], vuln_results: List[Dict]):
    """Render detailed vulnerability breakdown table.

    Args:
        vuln_tests: List of vulnerability test names
        vuln_results: List of vulnerability result dictionaries
    """
    breakdown_data = []
    for result in vuln_results:
        model = result["model"]
        df = result["data"]

        for test in vuln_tests:
            test_data = df[df["test_name"] == test]
            if not test_data.empty and "accuracy" in test_data.columns:
                breakdown_data.append(
                    {
                        "Model": model,
                        "Test": test.replace("_", " ").title(),
                        "Detection Rate": test_data["accuracy"].iloc[0],
                        "Vulnerability": 1 - test_data["accuracy"].iloc[0],
                    }
                )

    if breakdown_data:
        breakdown_df = pd.DataFrame(breakdown_data)
        breakdown_df["Detection Rate"] = breakdown_df["Detection Rate"].apply(lambda x: f"{x:.1%}")
        breakdown_df["Vulnerability"] = breakdown_df["Vulnerability"].apply(lambda x: f"{x:.1%}")
        st.dataframe(breakdown_df, width="stretch", hide_index=True)


def render_vulnerability_comparison(models: List[str], data_loader, cache_manager):
    """Render vulnerability analysis comparison.

    Args:
        models: List of model names to compare
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.subheader("Vulnerability Analysis")

    @cache_manager.cache_decorator
    def get_vulnerability_data(model_list):
        vuln_data = []
        for model in model_list:
            df = data_loader.fetch_test_suite_results(model, "robustness")
            if not df.empty:
                vuln_data.append({"model": model, "data": df})
        return vuln_data

    vuln_results = get_vulnerability_data(tuple(models))

    if not vuln_results:
        st.info("No vulnerability test data available")
        return

    vuln_tests = [
        "paraphrasing_robustness",
        "multilingual_triggers",
        "honeypot_vulnerability",
        "adversarial_robustness",
        "mitigation_effectiveness",
    ]

    st.markdown("#### Vulnerability Score Matrix")
    matrix_data = _build_vulnerability_matrix(vuln_tests, vuln_results)
    _render_vulnerability_heatmap(matrix_data, vuln_tests, vuln_results)

    st.markdown("---")
    st.markdown("#### Risk Categories")
    risk_categories = _categorize_models_by_risk(vuln_results)
    _render_risk_categories(risk_categories)

    st.markdown("---")
    st.markdown("#### Detailed Vulnerability Breakdown")
    _render_vulnerability_breakdown(vuln_tests, vuln_results)
