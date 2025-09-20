"""
Time Series Analysis Component
Tracks detection performance trends over time with forecasting capabilities.
"""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Type hints removed - not used


logger = logging.getLogger(__name__)


def render_time_series_analysis(data_loader, cache_manager):
    """Render the time series analysis dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("📉 Time Series Analysis")

    # Model and metric selection
    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available for analysis. Please run evaluations first.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        selected_model = st.selectbox("Select Model", models, help="Choose a model to analyze trends")

    with col2:
        metrics = ["accuracy", "f1_score", "precision", "recall", "avg_confidence"]
        selected_metric = st.selectbox("Metric", metrics, format_func=lambda x: x.replace("_", " ").title())

    with col3:
        time_ranges = {"Last Week": 7, "Last 2 Weeks": 14, "Last Month": 30, "Last 2 Months": 60, "Last 3 Months": 90}
        selected_range = st.selectbox("Time Range", list(time_ranges.keys()), index=2)  # Default to Last Month
        days_back = time_ranges[selected_range]

    if selected_model:
        # Fetch time series data
        @cache_manager.cache_decorator
        def get_time_series(model, metric, days):
            return data_loader.fetch_time_series(model, metric, days)

        df_timeseries = get_time_series(selected_model, selected_metric, days_back)

        if df_timeseries.empty:
            st.info(f"No time series data available for {selected_model} in the selected period")
            return

        # Render analysis sections
        render_trend_analysis(df_timeseries, selected_metric)
        st.markdown("---")
        render_performance_stability(df_timeseries, selected_metric, selected_model)
        st.markdown("---")
        render_test_type_trends(df_timeseries, selected_metric, data_loader, selected_model, days_back)
        st.markdown("---")
        render_anomaly_detection(df_timeseries, selected_metric)


def render_trend_analysis(df: pd.DataFrame, metric: str):
    """Render trend analysis with moving averages.

    Args:
        df: DataFrame with time series data
        metric: Selected metric name
    """
    st.subheader("📊 Trend Analysis")

    # Prepare data
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df_sorted = df.sort_values("timestamp")

    # Calculate daily aggregates
    daily_data = (
        df_sorted.groupby(df_sorted["timestamp"].dt.date).agg({metric: ["mean", "min", "max", "std", "count"]}).reset_index()
    )
    daily_data.columns = ["date", "mean", "min", "max", "std", "count"]

    # Calculate moving averages
    daily_data["ma_3"] = daily_data["mean"].rolling(window=3, min_periods=1).mean()
    daily_data["ma_7"] = daily_data["mean"].rolling(window=7, min_periods=1).mean()

    # Create main trend plot
    fig = go.Figure()

    # Raw data points
    fig.add_trace(
        go.Scatter(
            x=df_sorted["timestamp"],
            y=df_sorted[metric],
            mode="markers",
            name="Raw Data",
            marker=dict(size=4, color="lightgray", opacity=0.5),
            hovertemplate="%{y:.1%}<extra></extra>",
        )
    )

    # Daily average
    fig.add_trace(
        go.Scatter(
            x=daily_data["date"],
            y=daily_data["mean"],
            mode="lines+markers",
            name="Daily Average",
            line=dict(color="blue", width=2),
            marker=dict(size=6),
            hovertemplate="%{y:.1%}<extra></extra>",
        )
    )

    # 3-day moving average
    fig.add_trace(
        go.Scatter(
            x=daily_data["date"],
            y=daily_data["ma_3"],
            mode="lines",
            name="3-Day MA",
            line=dict(color="green", dash="dash"),
            hovertemplate="%{y:.1%}<extra></extra>",
        )
    )

    # 7-day moving average
    fig.add_trace(
        go.Scatter(
            x=daily_data["date"],
            y=daily_data["ma_7"],
            mode="lines",
            name="7-Day MA",
            line=dict(color="red", dash="dot"),
            hovertemplate="%{y:.1%}<extra></extra>",
        )
    )

    # Add confidence band
    upper_bound = daily_data["mean"] + daily_data["std"]
    lower_bound = daily_data["mean"] - daily_data["std"]

    fig.add_trace(
        go.Scatter(
            x=daily_data["date"].tolist() + daily_data["date"].tolist()[::-1],
            y=upper_bound.tolist() + lower_bound.tolist()[::-1],
            fill="toself",
            fillcolor="rgba(0,100,80,0.1)",
            line=dict(color="rgba(255,255,255,0)"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.update_layout(
        title=f"{metric.replace('_', ' ').title()} Trend Analysis",
        xaxis_title="Date",
        yaxis_title=metric.replace("_", " ").title(),
        yaxis=dict(range=[0, 1], tickformat=".0%"),
        height=500,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Trend statistics
    col1, col2, col3, col4 = st.columns(4)

    current_value = daily_data["mean"].iloc[-1] if not daily_data.empty else 0
    start_value = daily_data["mean"].iloc[0] if not daily_data.empty else 0
    change = current_value - start_value
    change_pct = (change / start_value * 100) if start_value != 0 else 0

    with col1:
        st.metric("Current", f"{current_value:.1%}", help="Most recent daily average")

    with col2:
        st.metric("Change", f"{change:.1%}", f"{change_pct:+.1f}%", help="Change from start of period")

    with col3:
        st.metric("Volatility", f"{daily_data['std'].mean():.2%}", help="Average daily standard deviation")

    with col4:
        st.metric("Tests/Day", f"{daily_data['count'].mean():.1f}", help="Average tests per day")


def render_performance_stability(df: pd.DataFrame, metric: str, model: str):
    """Render performance stability analysis.

    Args:
        df: DataFrame with time series data
        metric: Selected metric name
        model: Model name
    """
    st.subheader("🎯 Performance Stability")

    # Calculate stability metrics
    values = df[metric].values
    mean_val = values.mean()
    std_val = values.std()
    cv = (std_val / mean_val) if mean_val != 0 else 0

    # Determine stability rating
    if cv < 0.05:
        stability = "Excellent"
        pass  # color = "green"  # Not used currently
    elif cv < 0.10:
        stability = "Good"
        # color = "blue"  # Not used currently
    elif cv < 0.15:
        stability = "Moderate"
        pass  # color = "orange" - not used currently
    else:
        stability = "Poor"
        pass  # color = "red" - not used currently

    # Create distribution plot
    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(x=values, nbinsx=20, name="Distribution", marker=dict(color="lightblue"), showlegend=False))

    # Add mean line
    fig.add_vline(x=mean_val, line=dict(color="red", dash="dash"), annotation_text=f"Mean: {mean_val:.1%}")

    # Add ±1 std lines
    fig.add_vline(
        x=mean_val + std_val, line=dict(color="orange", dash="dot"), annotation_text=f"+1σ: {mean_val + std_val:.1%}"
    )

    fig.add_vline(
        x=mean_val - std_val, line=dict(color="orange", dash="dot"), annotation_text=f"-1σ: {mean_val - std_val:.1%}"
    )

    fig.update_layout(
        title=f"Performance Distribution - {model}",
        xaxis_title=metric.replace("_", " ").title(),
        yaxis_title="Frequency",
        xaxis=dict(tickformat=".0%"),
        height=400,
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Stability Metrics")
        st.metric("Stability Rating", stability, help="Based on coefficient of variation")
        st.metric("Mean", f"{mean_val:.2%}")
        st.metric("Std Dev", f"{std_val:.3%}")
        st.metric("CV", f"{cv:.3f}", help="Coefficient of Variation (σ/μ)")

        # Performance bands
        st.markdown("#### Performance Bands")
        bands = {
            "Excellent (>90%)": (values >= 0.9).sum(),
            "Good (80-90%)": ((values >= 0.8) & (values < 0.9)).sum(),
            "Fair (70-80%)": ((values >= 0.7) & (values < 0.8)).sum(),
            "Poor (<70%)": (values < 0.7).sum(),
        }

        for band, count in bands.items():
            pct = count / len(values) * 100 if len(values) > 0 else 0
            st.write(f"{band}: {count} ({pct:.1f}%)")


def render_test_type_trends(df: pd.DataFrame, metric: str, data_loader, model: str, days: int):
    """Render trends by test type.

    Args:
        df: DataFrame with time series data
        metric: Selected metric name
        data_loader: DataLoader instance
        model: Model name
        days: Number of days for analysis
    """
    st.subheader("🔀 Test Type Trends")

    # Fetch full results with test types
    results_df = data_loader.fetch_latest_results(model, limit=1000)

    if results_df.empty or "test_type" not in results_df.columns:
        st.info("Test type breakdown not available")
        return

    # Filter by date range
    results_df["timestamp"] = pd.to_datetime(results_df["timestamp"])
    cutoff_date = datetime.now() - timedelta(days=days)
    results_df = results_df[results_df["timestamp"] >= cutoff_date]

    if metric not in results_df.columns:
        st.warning(f"Metric '{metric}' not available in results")
        return

    # Group by test type and date
    test_types = results_df["test_type"].unique()

    # Create trend lines for each test type
    fig = go.Figure()

    colors = px.colors.qualitative.Set2

    for i, test_type in enumerate(test_types):
        type_df = results_df[results_df["test_type"] == test_type]

        if not type_df.empty:
            # Daily averages for this test type
            daily_avg = type_df.groupby(type_df["timestamp"].dt.date)[metric].mean()

            fig.add_trace(
                go.Scatter(
                    x=daily_avg.index,
                    y=daily_avg.values,
                    mode="lines+markers",
                    name=test_type.title(),
                    line=dict(color=colors[i % len(colors)]),
                    hovertemplate="%{y:.1%}<extra></extra>",
                )
            )

    fig.update_layout(
        title="Performance by Test Type",
        xaxis_title="Date",
        yaxis_title=metric.replace("_", " ").title(),
        yaxis=dict(range=[0, 1], tickformat=".0%"),
        height=450,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Test type statistics table
    st.markdown("#### Test Type Statistics")

    stats_data = []
    for test_type in test_types:
        type_df = results_df[results_df["test_type"] == test_type]
        if not type_df.empty and metric in type_df.columns:
            values = type_df[metric].dropna()
            if len(values) > 0:
                stats_data.append(
                    {
                        "Test Type": test_type.title(),
                        "Count": len(values),
                        "Mean": f"{values.mean():.2%}",
                        "Std": f"{values.std():.3%}",
                        "Min": f"{values.min():.2%}",
                        "Max": f"{values.max():.2%}",
                    }
                )

    if stats_data:
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, use_container_width=True, hide_index=True)


def render_anomaly_detection(df: pd.DataFrame, metric: str):
    """Render anomaly detection analysis.

    Args:
        df: DataFrame with time series data
        metric: Selected metric name
    """
    st.subheader("⚠️ Anomaly Detection")

    # Calculate anomalies using IQR method
    values = df[metric].values
    Q1 = np.percentile(values, 25)
    Q3 = np.percentile(values, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    # Identify anomalies
    df["is_anomaly"] = (df[metric] < lower_bound) | (df[metric] > upper_bound)
    anomalies = df[df["is_anomaly"]]

    # Create anomaly plot
    fig = go.Figure()

    # Normal points
    normal_data = df[~df["is_anomaly"]]
    fig.add_trace(
        go.Scatter(
            x=normal_data["timestamp"],
            y=normal_data[metric],
            mode="markers",
            name="Normal",
            marker=dict(size=6, color="blue", opacity=0.6),
            hovertemplate="%{y:.1%}<extra></extra>",
        )
    )

    # Anomaly points
    if not anomalies.empty:
        fig.add_trace(
            go.Scatter(
                x=anomalies["timestamp"],
                y=anomalies[metric],
                mode="markers",
                name="Anomaly",
                marker=dict(size=10, color="red", symbol="x"),
                hovertemplate="Test: %{text}<br>Value: %{y:.1%}<extra></extra>",
                text=anomalies["test_name"] if "test_name" in anomalies.columns else None,
            )
        )

    # Add threshold lines
    fig.add_hline(y=upper_bound, line=dict(color="red", dash="dash"), annotation_text=f"Upper Threshold: {upper_bound:.1%}")

    fig.add_hline(y=lower_bound, line=dict(color="red", dash="dash"), annotation_text=f"Lower Threshold: {lower_bound:.1%}")

    # Add IQR band
    fig.add_hrect(y0=Q1, y1=Q3, fillcolor="green", opacity=0.1, line_width=0)

    fig.update_layout(
        title="Anomaly Detection (IQR Method)",
        xaxis_title="Timestamp",
        yaxis_title=metric.replace("_", " ").title(),
        yaxis=dict(range=[0, 1], tickformat=".0%"),
        height=450,
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Anomaly statistics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Anomalies", len(anomalies), help="Number of detected anomalies")

    with col2:
        anomaly_rate = len(anomalies) / len(df) * 100 if len(df) > 0 else 0
        st.metric("Anomaly Rate", f"{anomaly_rate:.1f}%", help="Percentage of anomalous results")

    with col3:
        if not anomalies.empty:
            latest_anomaly = anomalies["timestamp"].max()
            days_since = (datetime.now() - pd.to_datetime(latest_anomaly)).days
            st.metric("Days Since Last", days_since, help="Days since last anomaly")
        else:
            st.metric("Days Since Last", "N/A")

    # Anomaly details
    if not anomalies.empty:
        st.markdown("#### Recent Anomalies")

        # Prepare display data
        display_anomalies = (
            anomalies[["timestamp", "test_name", metric]].copy()
            if "test_name" in anomalies.columns
            else anomalies[["timestamp", metric]].copy()
        )

        display_anomalies["timestamp"] = pd.to_datetime(display_anomalies["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")
        display_anomalies[metric] = display_anomalies[metric].apply(lambda x: f"{x:.2%}")

        # Sort by timestamp descending
        display_anomalies = display_anomalies.sort_values("timestamp", ascending=False).head(10)

        # Rename columns
        column_names = {"timestamp": "Time", "test_name": "Test", metric: metric.replace("_", " ").title()}
        display_anomalies.rename(columns=column_names, inplace=True)

        st.dataframe(display_anomalies, use_container_width=True, hide_index=True)
    else:
        st.success("✅ No anomalies detected in the selected period")
