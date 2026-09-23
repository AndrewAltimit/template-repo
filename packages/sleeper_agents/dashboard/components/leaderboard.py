"""
Model Leaderboard Component
Ranks models by a documented formula over measured detection metrics only.
"""

import logging
from typing import Any, Dict, List, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.metric_format import fmt_pct, is_measured

logger = logging.getLogger(__name__)

# Metrics the Detection Score is computed from: per-model averages over completed
# evaluation_results rows. A model missing any of them is listed as unranked.
RANKING_METRICS = ["Accuracy", "F1 Score", "Precision", "Recall"]
SCORE_COLUMN = "Detection Score"
RANKING_FORMULA = (
    f"{SCORE_COLUMN} = (Accuracy + F1 Score + Precision + Recall) / 4, each the model's average over its "
    "completed evaluation tests. Models missing any of these four metrics are not ranked."
)


def build_leaderboard_rows(data_loader: Any, models: List[str]) -> List[Dict[str, Any]]:
    """Collect measured metrics per model; unmeasured metrics stay None."""
    rows = []
    for model in models:
        summary = data_loader.fetch_model_summary(model)
        if not summary or summary.get("error"):
            continue
        rows.append(
            {
                "Model": model,
                "Accuracy": summary.get("avg_accuracy"),
                "F1 Score": summary.get("avg_f1"),
                "Precision": summary.get("avg_precision"),
                "Recall": summary.get("avg_recall"),
                "Total Tests": summary.get("total_tests") or 0,
                "Last Test": summary.get("last_test") or "N/A",
            }
        )
    return rows


def rank_models(rows: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Rank models by the Detection Score (see RANKING_FORMULA).

    Returns:
        (ranked, unranked): ranked has SCORE_COLUMN and Rank (1 = best, ties share
        the lower rank) sorted by rank; unranked lists models missing any ranking
        metric, with the missing metrics in "Missing Metrics".
    """
    df = pd.DataFrame(rows, columns=["Model", *RANKING_METRICS, "Total Tests", "Last Test"])
    for metric in RANKING_METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")

    missing = df[RANKING_METRICS].isna()
    complete = ~missing.any(axis=1)

    unranked = df[~complete].copy()
    unranked["Missing Metrics"] = [", ".join(m for m in RANKING_METRICS if missing.loc[idx, m]) for idx in unranked.index]
    unranked = unranked.reset_index(drop=True)

    ranked = df[complete].copy()
    ranked[SCORE_COLUMN] = ranked[RANKING_METRICS].mean(axis=1)
    # Round away floating-point noise so equal scores share a rank
    ranked["Rank"] = ranked[SCORE_COLUMN].round(9).rank(ascending=False, method="min").astype(int)
    ranked = ranked.sort_values(["Rank", "Model"]).reset_index(drop=True)
    return ranked, unranked


def render_model_leaderboard(data_loader, cache_manager):
    """Render the model leaderboard dashboard.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Model Leaderboard")

    st.caption(
        """
    This leaderboard ranks models by their measured detection performance. Scores are averages over
    each model's completed evaluation tests; models evaluated on different test suites are not strictly
    comparable, so check the test counts. A high score does not establish that a model is free of
    backdoors - it only summarizes the tests that were run.
    """
    )
    st.info(f"**Ranking formula:** {RANKING_FORMULA}")

    models = data_loader.fetch_models()
    if not models:
        st.warning("No models available for ranking. Please run evaluations first.")
        return

    @cache_manager.cache_decorator
    def compile_leaderboard_data(model_list):
        return build_leaderboard_rows(data_loader, list(model_list))

    leaderboard_data = compile_leaderboard_data(tuple(models))
    if not leaderboard_data:
        st.error("Failed to compile leaderboard data")
        return

    df_ranked, df_unranked = rank_models(leaderboard_data)

    if not df_unranked.empty:
        render_unranked_table(df_unranked)
    if df_ranked.empty:
        st.info("No model has all four ranking metrics measured, so no ranking can be computed.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        sort_by = st.selectbox(
            "Sort By",
            [SCORE_COLUMN, *RANKING_METRICS, "Total Tests"],
            help="Choose metric to sort the leaderboard",
        )
    with col2:
        min_tests = st.number_input(
            "Min Tests", min_value=0, max_value=1000, value=0, step=10, help="Filter models with minimum number of tests"
        )
    with col3:
        n_ranked = len(df_ranked)
        top_n = (
            st.slider(
                "Show Top N", min_value=1, max_value=n_ranked, value=min(10, n_ranked), help="Number of models to display"
            )
            if n_ranked > 1
            else 1
        )

    df_filtered = df_ranked[df_ranked["Total Tests"] >= min_tests].copy() if min_tests > 0 else df_ranked.copy()
    if sort_by != SCORE_COLUMN:
        df_filtered = df_filtered.sort_values(sort_by, ascending=False)
        df_filtered["Rank"] = range(1, len(df_filtered) + 1)

    df_display = df_filtered.head(top_n)
    if df_display.empty:
        st.info("No ranked model matches the filters.")
        return

    render_leaderboard_table(df_display)
    st.markdown("---")
    render_leaderboard_chart(df_display, sort_by)
    st.markdown("---")
    render_champion_analysis(df_display)


def format_unranked_table(df: pd.DataFrame) -> pd.DataFrame:
    """Format per-model measured metrics without a rank; unmeasured values read "Not measured"."""
    columns = ["Model", *RANKING_METRICS, "Robustness", "Vulnerability", "Total Tests", "Missing Metrics"]
    display_df = df[[c for c in columns if c in df.columns]].copy()
    for col in [*RANKING_METRICS, "Robustness", "Vulnerability"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(fmt_pct)
    return display_df


def render_unranked_table(df: pd.DataFrame):
    """Render measured metrics for models that cannot be ranked."""
    st.subheader("Not Ranked (missing measurements)")
    st.dataframe(format_unranked_table(df), width="stretch", hide_index=True)


def render_leaderboard_table(df: pd.DataFrame):
    """Render the main leaderboard table.

    Args:
        df: DataFrame with ranked leaderboard data
    """
    st.subheader("Ranking Table")

    display_df = df.copy()
    for col in [SCORE_COLUMN, *RANKING_METRICS]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(fmt_pct)
    if "Last Test" in display_df.columns:
        display_df["Last Test"] = display_df["Last Test"].apply(lambda x: x[:10] if x not in ("N/A", None) else "N/A")

    display_cols = ["Rank", "Model", SCORE_COLUMN, *RANKING_METRICS, "Total Tests", "Last Test"]
    available_cols = [col for col in display_cols if col in display_df.columns]
    st.dataframe(display_df[available_cols], width="stretch", hide_index=True, height=400)


def render_leaderboard_chart(df: pd.DataFrame, metric: str):
    """Render the selected metric per model.

    Args:
        df: DataFrame with ranked leaderboard data
        metric: Selected metric for sorting
    """
    st.subheader("Performance Visualization")

    is_rate = metric != "Total Tests"
    fig = go.Figure(
        go.Bar(
            y=df["Model"],
            x=df[metric],
            orientation="h",
            marker={"color": "#4169E1"},
            text=[(f"{v:.1%}" if is_rate else f"{int(v):,}") if is_measured(v) else "" for v in df[metric]],
            textposition="auto",
        )
    )
    fig.update_layout(
        title=f"Models by {metric}",
        xaxis_title=metric,
        yaxis_title="Model",
        height=max(400, len(df) * 40),
        xaxis={"tickformat": ".0%"} if is_rate else {},
        yaxis={"autorange": "reversed"},
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    if len(df) >= 2:
        st.markdown("#### Multi-Metric Comparison")
        top = df.head(5)
        heatmap_data = top[RANKING_METRICS].values.tolist()
        fig_heatmap = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=RANKING_METRICS,
                y=top["Model"].tolist(),
                colorscale="RdYlGn",
                zmin=0,
                zmax=1,
                text=[[f"{v * 100:.1f}%" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 12},
                colorbar={"title": "Score", "tickformat": ".0%"},
            )
        )
        fig_heatmap.update_layout(
            xaxis_title="Metrics", yaxis_title="Models", height=max(250, 50 * len(top)), xaxis={"side": "bottom"}
        )
        st.plotly_chart(fig_heatmap, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def render_champion_analysis(df: pd.DataFrame):
    """Render measured metrics of the top-ranked model.

    Args:
        df: DataFrame with ranked leaderboard data
    """
    if df.empty:
        return

    st.subheader("Top-Ranked Model")
    top = df.iloc[0]

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"### {top['Model']}")
        stats_df = pd.DataFrame(
            {
                "Metric": [SCORE_COLUMN, *RANKING_METRICS],
                "Value": [fmt_pct(top[m], 2) for m in [SCORE_COLUMN, *RANKING_METRICS]],
            }
        )
        st.dataframe(stats_df, width="stretch", hide_index=True)
        st.metric("Total Tests Completed", top["Total Tests"])
        st.metric("Last Evaluated", top["Last Test"][:10] if top["Last Test"] not in ("N/A", None) else "N/A")

    with col2:
        st.markdown("#### Strongest and Weakest Metrics")
        sorted_metrics = sorted(((m, top[m]) for m in RANKING_METRICS), key=lambda x: x[1], reverse=True)
        st.success("**Strongest:**")
        for metric, value in sorted_metrics[:2]:
            st.write(f"{metric}: {value:.1%}")
        st.warning("**Weakest:**")
        for metric, value in sorted_metrics[-2:]:
            st.write(f"{metric}: {value:.1%}")
        if len(df) > 1:
            delta = top[SCORE_COLUMN] - df[SCORE_COLUMN].mean()
            st.metric("Above Displayed Average By", f"{delta:.1%}", help=f"Difference from the mean {SCORE_COLUMN}")

    if len(df) > 1:
        st.markdown("---")
        st.markdown("#### Gap Analysis")
        gaps_df = pd.DataFrame(
            [
                {
                    "Position": f"#{i + 1} vs #{i + 2}",
                    "Gap": df.iloc[i][SCORE_COLUMN] - df.iloc[i + 1][SCORE_COLUMN],
                }
                for i in range(min(5, len(df) - 1))
            ]
        )
        fig_gaps = px.bar(
            gaps_df,
            x="Position",
            y="Gap",
            title=f"{SCORE_COLUMN} Gaps Between Adjacent Positions",
            text=[f"{g:.2%}" for g in gaps_df["Gap"]],
        )
        fig_gaps.update_layout(yaxis={"tickformat": ".1%"}, height=350, showlegend=False)
        st.plotly_chart(fig_gaps, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})
