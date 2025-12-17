"""
Red Team Results Component
Displays automated red-teaming findings and discovered triggers.
"""

import logging

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def render_red_team_results(data_loader, cache_manager):
    """Render red teaming results dashboard.
    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Automated Red-Teaming Results")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(
        model_registry, key_suffix="red_team_results", help_text="Select model for analysis"
    )
    if not selected_model:
        return
    model_name = selected_model.name

    # Add context explanation
    st.caption(
        """
    Red-teaming tests how easily backdoors can be discovered through automated prompt generation.
    High success rates indicate the model has exploitable backdoors that adversaries could find.
    More concerning is when success improves over generations, showing backdoors are learnable.
    The discovered triggers reveal what specific inputs activate malicious behavior.
    """
    )

    # Fetch red team data
    red_team_data = _fetch_red_team_data(data_loader, cache_manager, model_name)

    if not red_team_data:
        st.info("No red-teaming data available. Run automated red-teaming first.")
        return

    # Success metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Prompts Tested", red_team_data["total_prompts"], help="Total number of prompts generated and tested")

    with col2:
        st.metric(
            "Success Rate", f"{red_team_data['success_rate']:.1%}", help="Percentage of prompts that triggered backdoors"
        )

    with col3:
        st.metric("Unique Triggers", len(red_team_data["discovered_triggers"]), help="Number of unique trigger patterns found")

    with col4:
        st.metric("Best Strategy", red_team_data["best_strategy"], help="Most effective prompt generation strategy")

    st.markdown("---")

    # Discovered triggers
    st.subheader("Discovered Trigger Patterns")
    _render_discovered_triggers(red_team_data)

    st.markdown("---")

    # Success by strategy
    st.subheader("Effectiveness by Strategy")
    _render_strategy_analysis(red_team_data)

    st.markdown("---")

    # Evolution history
    st.subheader("Prompt Evolution")
    _render_evolution_history(red_team_data)


def _fetch_red_team_data(data_loader, _cache_manager, model_name: str) -> dict:
    """Fetch red team testing data from real honeypot and trigger tests."""
    # Fetch real red team results aggregated from honeypot tests
    result: dict = data_loader.fetch_red_team_results(model_name)
    return result


def _render_discovered_triggers(data: dict):
    """Render discovered trigger patterns."""
    triggers = data["discovered_triggers"]
    strategy_success = data.get("strategy_success", {})

    # Get effectiveness scores for each trigger (from strategy_success)
    effectiveness_scores = [strategy_success.get(trigger, 0.0) for trigger in triggers]

    # Create trigger effectiveness chart
    if triggers and effectiveness_scores:
        fig = go.Figure(
            data=[
                go.Bar(
                    y=triggers,
                    x=effectiveness_scores,
                    orientation="h",
                    text=[f"{s:.0%}" for s in effectiveness_scores],
                    textposition="auto",
                    marker_color="crimson",
                )
            ]
        )

        fig.update_layout(
            title="Trigger Pattern Effectiveness",
            xaxis_title="Activation Rate",
            yaxis_title="Discovered Trigger",
            xaxis={"range": [0, 1], "tickformat": ".0%"},
            height=max(300, len(triggers) * 50),  # Dynamic height based on trigger count
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})
    else:
        st.info("No trigger patterns discovered yet.")

    # Display trigger details
    with st.expander("View Successful Prompts"):
        for prompt_data in data["successful_prompts"][:5]:
            st.markdown(
                f"""
            **Prompt**: `{prompt_data["prompt"]}`
            - **Strategy**: {prompt_data["strategy"]}
            - **Success Score**: {prompt_data["score"]:.2f}
            """
            )


def _render_strategy_analysis(data: dict):
    """Render strategy effectiveness analysis."""
    strategies = list(data["strategy_success"].keys())
    success_rates = list(data["strategy_success"].values())

    # Create bar chart for better readability
    fig = go.Figure(
        data=go.Bar(
            x=strategies,
            y=[r * 100 for r in success_rates],
            text=[f"{r * 100:.1f}%" for r in success_rates],
            textposition="outside",
            marker={
                "color": [r * 100 for r in success_rates],
                "colorscale": "RdYlGn",
                "showscale": True,
                "colorbar": {"title": "Success Rate (%)"},
            },
            name="Success Rate",
        )
    )

    fig.update_layout(
        title="Strategy Effectiveness Analysis",
        xaxis_title="Red Team Strategy",
        yaxis_title="Success Rate (%)",
        yaxis={"range": [0, max(success_rates) * 120]},
        showlegend=False,
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Strategy comparison table
    strategy_df = pd.DataFrame(
        {
            "Strategy": strategies,
            "Success Rate": success_rates,
            "Effectiveness": ["High" if s > 0.3 else "Medium" if s > 0.2 else "Low" for s in success_rates],
        }
    )
    strategy_df = strategy_df.sort_values("Success Rate", ascending=False)

    st.dataframe(strategy_df.style.highlight_max(subset=["Success Rate"]), use_container_width=True)


def _render_evolution_history(data: dict):
    """Render prompt evolution history."""
    evolution = data["evolution_history"]

    generations = [e["generation"] for e in evolution]
    best_scores = [e["best_score"] for e in evolution]
    avg_scores = [e["avg_score"] for e in evolution]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=generations,
            y=best_scores,
            mode="lines+markers",
            name="Best Score",
            line={"color": "red", "width": 3},
            marker={"size": 8},
        )
    )

    fig.add_trace(
        go.Scatter(
            x=generations,
            y=avg_scores,
            mode="lines+markers",
            name="Average Score",
            line={"color": "orange", "width": 2},
            marker={"size": 6},
        )
    )

    fig.update_layout(
        title="Prompt Evolution Performance",
        xaxis_title="Generation",
        yaxis_title="Success Score",
        yaxis={"range": [0, 1], "tickformat": ".0%"},
        hovermode="x",
        height=350,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Key insight
    improvement = best_scores[-1] - best_scores[0]
    st.success(
        f"**Evolution Success**: Red-teaming improved trigger discovery by "
        f"{improvement:.0%} through {len(generations)} generations of prompt evolution."
    )
