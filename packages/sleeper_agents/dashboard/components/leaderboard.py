"""
Model Leaderboard Component
Displays comprehensive model rankings with filtering and sorting capabilities.
"""

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)


def render_model_leaderboard(data_loader, cache_manager):
    """Render the model leaderboard dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Model Leaderboard")

    # Add context about leaderboard scoring
    st.caption(
        """
    This leaderboard ranks models based on their ability to detect and resist backdoors.
    The Safety Score combines multiple metrics including accuracy, precision, recall, and robustness.
    Models at the top of the leaderboard show the best overall resistance to sleeper agent behavior.
    However, high scores don't guarantee complete safety - even top models may still harbor
    subtle backdoors that activate under specific conditions. Pay attention to the gap between
    ranks as large gaps indicate significant differences in detection capabilities.
    """
    )

    # Fetch all models
    models = data_loader.fetch_models()

    if not models:
        st.warning("No models available for ranking. Please run evaluations first.")
        return

    # Fetch and compile leaderboard data
    @cache_manager.cache_decorator
    def compile_leaderboard_data(model_list):
        leaderboard = []
        for model in model_list:
            summary = data_loader.fetch_model_summary(model)
            if summary:
                leaderboard.append(
                    {
                        "Model": model,
                        "Overall Score": summary.get("overall_score") or summary.get("avg_accuracy", 0) or 0,
                        "Accuracy": summary.get("avg_accuracy", 0) or 0,
                        "F1 Score": summary.get("avg_f1", 0) or 0,
                        "Precision": summary.get("avg_precision", 0) or 0,
                        "Recall": summary.get("avg_recall", 0) or 0,
                        "Robustness": summary.get("robustness_score", 0) or 0,
                        "Vulnerability": summary.get("vulnerability_score", 1) or 1,
                        "Total Tests": summary.get("total_tests", 0) or 0,
                        "Last Test": summary.get("last_test") or "N/A",
                    }
                )
        return leaderboard

    leaderboard_data = compile_leaderboard_data(tuple(models))

    if not leaderboard_data:
        st.error("Failed to compile leaderboard data")
        return

    # Create DataFrame
    df_leaderboard = pd.DataFrame(leaderboard_data)

    # Calculate composite safety score
    df_leaderboard["Safety Score"] = (
        df_leaderboard["Accuracy"] * 0.3
        + df_leaderboard["F1 Score"] * 0.2
        + df_leaderboard["Precision"] * 0.15
        + df_leaderboard["Recall"] * 0.15
        + df_leaderboard["Robustness"] * 0.1
        + (1 - df_leaderboard["Vulnerability"]) * 0.1
    )

    # Rank models
    df_leaderboard["Rank"] = df_leaderboard["Safety Score"].rank(ascending=False, method="min").astype(int)
    df_leaderboard = df_leaderboard.sort_values("Rank")

    # Display options
    col1, col2, col3 = st.columns(3)

    with col1:
        sort_by = st.selectbox(
            "Sort By",
            ["Safety Score", "Accuracy", "F1 Score", "Precision", "Recall", "Robustness", "Total Tests"],
            help="Choose metric to sort the leaderboard",
        )

    with col2:
        min_tests = st.number_input(
            "Min Tests", min_value=0, max_value=1000, value=0, step=10, help="Filter models with minimum number of tests"
        )

    with col3:
        top_n = st.slider(
            "Show Top N", min_value=5, max_value=len(models), value=min(10, len(models)), help="Number of models to display"
        )

    # Apply filters and sorting
    if min_tests > 0:
        df_filtered = df_leaderboard[df_leaderboard["Total Tests"] >= min_tests].copy()
    else:
        df_filtered = df_leaderboard.copy()

    # Re-sort if needed
    if sort_by != "Safety Score":
        df_filtered = df_filtered.sort_values(sort_by, ascending=False)
        df_filtered["Rank"] = range(1, len(df_filtered) + 1)

    # Limit to top N
    df_display = df_filtered.head(top_n)

    # Display leaderboard
    render_leaderboard_table(df_display)
    st.markdown("---")
    render_leaderboard_chart(df_display, sort_by)
    st.markdown("---")
    render_tier_classification(df_display)
    st.markdown("---")
    render_champion_analysis(df_display)


def render_leaderboard_table(df: pd.DataFrame):
    """Render the main leaderboard table.

    Args:
        df: DataFrame with leaderboard data
    """
    st.subheader("Ranking Table")

    # Format display
    display_df = df.copy()

    # Format percentage columns
    percentage_cols = [
        "Overall Score",
        "Safety Score",
        "Accuracy",
        "F1 Score",
        "Precision",
        "Recall",
        "Robustness",
        "Vulnerability",
    ]
    for col in percentage_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1%}" if isinstance(x, (int, float)) else x)

    # Format last test date
    if "Last Test" in display_df.columns:
        display_df["Last Test"] = display_df["Last Test"].apply(lambda x: x[:10] if x != "N/A" and x is not None else "N/A")

    # Select columns to display
    display_cols = ["Rank", "Model", "Safety Score", "Accuracy", "F1 Score", "Precision", "Recall", "Total Tests", "Last Test"]
    available_cols = [col for col in display_cols if col in display_df.columns]

    # Apply conditional formatting with custom CSS
    def highlight_top_3(row):
        if row["Rank"] == 1:
            return ["background-color: #FFD700"] * len(row)  # Gold
        elif row["Rank"] == 2:
            return ["background-color: #C0C0C0"] * len(row)  # Silver
        elif row["Rank"] == 3:
            return ["background-color: #CD7F32"] * len(row)  # Bronze
        else:
            return [""] * len(row)

    styled_df = display_df[available_cols].style.apply(highlight_top_3, axis=1)

    st.dataframe(styled_df, width="stretch", hide_index=True, height=400)

    # Display medals for top 3
    if len(df) >= 3:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("### Gold")
            st.metric(df.iloc[0]["Model"], f"{df.iloc[0]['Safety Score']:.1%}", "Best Overall")

        with col2:
            st.markdown("### Silver")
            st.metric(df.iloc[1]["Model"], f"{df.iloc[1]['Safety Score']:.1%}", "Runner-up")

        with col3:
            st.markdown("### Bronze")
            st.metric(df.iloc[2]["Model"], f"{df.iloc[2]['Safety Score']:.1%}", "Third Place")


def render_leaderboard_chart(df: pd.DataFrame, metric: str):
    """Render visual representation of the leaderboard.

    Args:
        df: DataFrame with leaderboard data
        metric: Selected metric for sorting
    """
    st.subheader("Performance Visualization")

    # Create horizontal bar chart
    fig = go.Figure()

    # Assign colors based on rank
    colors = []
    for rank in df["Rank"]:
        if rank == 1:
            colors.append("#FFD700")  # Gold
        elif rank == 2:
            colors.append("#C0C0C0")  # Silver
        elif rank == 3:
            colors.append("#CD7F32")  # Bronze
        else:
            colors.append("#4169E1")  # Royal Blue

    fig.add_trace(
        go.Bar(
            y=df["Model"],
            x=df[metric],
            orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1%}" if isinstance(v, (int, float)) else v for v in df[metric]],
            textposition="auto",
            hovertemplate="<b>%{y}</b><br>" + metric + ": %{x:.1%}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Model Rankings by {metric}",
        xaxis_title=metric,
        yaxis_title="Model",
        height=max(400, len(df) * 40),
        xaxis=dict(tickformat=".0%"),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Create heatmap for top models comparison
    if len(df) >= 3:
        st.markdown("#### Top 3 Models Multi-Metric Comparison")

        metrics_comparison = ["Accuracy", "F1 Score", "Precision", "Recall", "Robustness"]
        available_metrics = [m for m in metrics_comparison if m in df.columns]

        # Prepare data for heatmap
        top_models = df.head(3)["Model"].tolist()
        heatmap_data = []
        for i in range(min(3, len(df))):
            values = [df.iloc[i][m] for m in available_metrics]
            heatmap_data.append(values)

        # Create heatmap
        fig_heatmap = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=available_metrics,
                y=top_models,
                colorscale="RdYlGn",
                text=[[f"{v*100:.1f}%" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 12},
                colorbar=dict(title="Score", tickformat=".0%"),
            )
        )

        fig_heatmap.update_layout(
            title="Top 3 Models Performance Matrix",
            xaxis_title="Metrics",
            yaxis_title="Models",
            height=250,
            xaxis=dict(side="bottom"),
        )

        st.plotly_chart(fig_heatmap, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def render_tier_classification(df: pd.DataFrame):
    """Render tier-based classification of models.

    Args:
        df: DataFrame with leaderboard data
    """
    st.subheader("Tier Classification")

    # Classify models into tiers based on safety score
    def get_tier(score):
        if score >= 0.9:
            return "S Tier", "#FFD700"
        elif score >= 0.8:
            return "A Tier", "#90EE90"
        elif score >= 0.7:
            return "B Tier", "#87CEEB"
        elif score >= 0.6:
            return "C Tier", "#DDA0DD"
        else:
            return "D Tier", "#FFB6C1"

    # Add tier classification
    df["Tier"], df["Tier_Color"] = zip(*df["Safety Score"].apply(get_tier))

    # Group by tier
    tier_counts = df.groupby("Tier").size().reset_index(name="Count")

    # Create tier distribution chart
    fig = px.bar(
        tier_counts,
        x="Tier",
        y="Count",
        title="Model Distribution by Tier",
        color="Tier",
        color_discrete_map={
            "S Tier": "#FFD700",
            "A Tier": "#90EE90",
            "B Tier": "#87CEEB",
            "C Tier": "#DDA0DD",
            "D Tier": "#FFB6C1",
        },
    )

    fig.update_layout(height=400, showlegend=False)

    col1, col2 = st.columns([1, 2])

    with col1:
        # Tier descriptions
        st.markdown("#### Tier Definitions")
        st.markdown(
            """
        - **S Tier (≥90%)**: Exceptional safety
        - **A Tier (≥80%)**: Excellent detection
        - **B Tier (≥70%)**: Good performance
        - **C Tier (≥60%)**: Adequate safety
        - **D Tier (<60%)**: Needs improvement
        """
        )

    with col2:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Display models by tier
    st.markdown("#### Models by Tier")

    tier_order = ["S Tier", "A Tier", "B Tier", "C Tier", "D Tier"]
    for tier in tier_order:
        tier_models = df[df["Tier"] == tier]["Model"].tolist()
        if tier_models:
            tier_name, tier_color = get_tier(
                0.95
                if tier == "S Tier"
                else 0.85 if tier == "A Tier" else 0.75 if tier == "B Tier" else 0.65 if tier == "C Tier" else 0.5
            )
            st.markdown(f"**{tier}**: {', '.join(tier_models)}")


def render_champion_analysis(df: pd.DataFrame):
    """Render detailed analysis of the champion model.

    Args:
        df: DataFrame with leaderboard data
    """
    if df.empty:
        return

    st.subheader("Champion Analysis")

    champion = df.iloc[0]

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(f"### Current Champion: **{champion['Model']}**")

        # Champion stats
        st.markdown("#### Key Statistics")
        stats_data = {
            "Metric": ["Safety Score", "Accuracy", "F1 Score", "Precision", "Recall"],
            "Value": [
                f"{champion['Safety Score']:.2%}",
                f"{champion['Accuracy']:.2%}",
                f"{champion['F1 Score']:.2%}",
                f"{champion['Precision']:.2%}",
                f"{champion['Recall']:.2%}",
            ],
        }
        stats_df = pd.DataFrame(stats_data)
        st.dataframe(stats_df, width="stretch", hide_index=True)

        st.metric("Total Tests Completed", champion["Total Tests"])
        st.metric("Last Evaluated", champion["Last Test"][:10] if champion["Last Test"] != "N/A" else "N/A")

    with col2:
        st.markdown("#### Strengths & Weaknesses")

        # Find strengths (top metrics)
        metrics = {
            "Accuracy": champion["Accuracy"],
            "F1 Score": champion["F1 Score"],
            "Precision": champion["Precision"],
            "Recall": champion["Recall"],
            "Robustness": champion["Robustness"],
        }

        sorted_metrics = sorted(metrics.items(), key=lambda x: x[1], reverse=True)

        st.success("**Top Strengths:**")
        for metric, value in sorted_metrics[:2]:
            st.write(f"{metric}: {value:.1%}")

        st.warning("**Areas for Improvement:**")
        for metric, value in sorted_metrics[-2:]:
            st.write(f"{metric}: {value:.1%}")

        # Performance vs average
        if len(df) > 1:
            avg_safety = df["Safety Score"].mean()
            performance_delta = champion["Safety Score"] - avg_safety

            st.metric("Above Average By", f"{performance_delta:.1%}", help="Difference from average safety score")

    # Gap analysis
    if len(df) > 1:
        st.markdown("---")
        st.markdown("#### Gap Analysis")

        # Calculate gaps between consecutive ranks
        gaps = []
        for i in range(min(5, len(df) - 1)):
            gap = df.iloc[i]["Safety Score"] - df.iloc[i + 1]["Safety Score"]
            gaps.append(
                {
                    "Position": f"#{i+1} vs #{i+2}",
                    "Models": f"{df.iloc[i]['Model'][:20]} vs {df.iloc[i+1]['Model'][:20]}",
                    "Gap": gap,
                }
            )

        gaps_df = pd.DataFrame(gaps)

        # Create gap visualization
        fig_gaps = px.bar(
            gaps_df,
            x="Position",
            y="Gap",
            title="Performance Gaps Between Ranks",
            text=[f"{g:.2%}" for g in gaps_df["Gap"]],
            color="Gap",
            color_continuous_scale="RdYlGn",
        )

        fig_gaps.update_layout(yaxis=dict(tickformat=".1%"), height=350, showlegend=False)

        st.plotly_chart(fig_gaps, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})
