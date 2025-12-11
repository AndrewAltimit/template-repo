"""
Behavioral Persona Profile Component
Displays psychological and behavioral analysis of models.
"""

import logging

import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def render_persona_profile(data_loader, cache_manager):
    """Render behavioral persona profile dashboard.
    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Behavioral Persona Profile")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(model_registry, key_suffix="persona_profile", help_text="Select model for analysis")
    if not selected_model:
        return
    model_name = selected_model.name

    # Add context about persona profiling
    st.caption(
        """
    Persona profiling reveals a model's underlying behavioral tendencies and hidden motivations.
    Models with backdoors often exhibit dual personalities - appearing helpful normally but showing
    concerning traits like increased power-seeking and reduced corrigibility when triggered.
    The metrics below measure how much the model's responses deviate from safe baselines,
    with special attention to changes that occur when backdoor triggers are present.
    This behavioral analysis can detect deceptive models even when they try to appear safe.
    """
    )

    # Fetch persona data
    persona_data = _fetch_persona_data(data_loader, cache_manager, model_name)

    if not persona_data:
        st.info("No persona data available. Run behavioral testing first.")
        return

    # Risk assessment
    _render_risk_assessment(persona_data)

    st.markdown("---")

    # Behavioral radar chart
    col1, col2 = st.columns([2, 1])

    with col1:
        _render_persona_radar(persona_data)

    with col2:
        _render_behavioral_metrics(persona_data)

    st.markdown("---")

    # Triggered vs Normal comparison
    st.subheader("Persona Changes with Triggers")
    _render_triggered_comparison(persona_data)

    st.markdown("---")

    # Concerning responses
    st.subheader("Concerning Response Analysis")
    _render_concerning_responses(persona_data)


def _fetch_persona_data(data_loader, cache_manager, model_name: str) -> dict:
    """Fetch persona testing data from real evaluations."""
    # Fetch real persona profile data aggregated from multiple tests
    result: dict = data_loader.fetch_persona_profile(model_name)
    return result


def _render_risk_assessment(data: dict):
    """Render overall risk assessment."""
    risk_level = data.get("risk_level", "UNKNOWN")

    if risk_level == "CRITICAL":
        color = "red"
        icon = "HIGH"
        message = "Model shows extreme behavioral indicators of backdoors"
    elif risk_level == "HIGH":
        color = "orange"
        icon = "MEDIUM"
        message = "Model exhibits concerning behavioral patterns consistent with backdoors"
    elif risk_level == "MODERATE":
        color = "yellow"
        icon = "MEDIUM"
        message = "Model shows some behavioral anomalies"
    else:
        color = "green"
        icon = "LOW"
        message = "Model behavioral profile appears normal"

    st.markdown(
        f"""
        <div style='padding: 1em; border-radius: 0.5em; background-color: {color}22; border: 2px solid {color}66;'>
            <h3 style='color: {color}; margin: 0;'>{icon} Behavioral Risk: {risk_level}</h3>
            <p style='margin: 0.5em 0 0 0;'>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_persona_radar(data: dict):
    """Render behavioral comparison grid."""
    behavioral_scores = data.get("behavioral_scores", {})

    # Handle empty behavioral scores
    if not behavioral_scores:
        st.info("No behavioral data available for visualization.")
        return

    categories = list(behavioral_scores.keys())
    values = list(behavioral_scores.values())

    # Add baseline for comparison (match number of categories)
    baseline_values = [0.3, 0.3, 0.7, 0.2, 0.4][: len(categories)]  # Normal model baseline

    # Create grouped bar chart for better readability
    fig = go.Figure()

    # Model profile
    fig.add_trace(
        go.Bar(
            name="Model Profile",
            x=[c.replace("_", " ").title() for c in categories],
            y=[v * 100 for v in values],
            text=[f"{v*100:.0f}%" for v in values],
            textposition="outside",
            marker_color="rgba(255, 0, 0, 0.6)",
        )
    )

    # Baseline profile
    fig.add_trace(
        go.Bar(
            name="Safe Baseline",
            x=[c.replace("_", " ").title() for c in categories],
            y=[v * 100 for v in baseline_values],
            text=[f"{v*100:.0f}%" for v in baseline_values],
            textposition="outside",
            marker_color="rgba(0, 255, 0, 0.6)",
        )
    )

    fig.update_layout(
        barmode="group",
        xaxis_title="Behavioral Dimension",
        yaxis_title="Score (%)",
        yaxis={"range": [0, 110]},
        showlegend=True,
        title="Behavioral Profile vs Safe Baseline",
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})


def _render_behavioral_metrics(data: dict):
    """Render key behavioral metrics."""
    st.markdown("### Key Indicators")

    behavioral_scores = data.get("behavioral_scores", {})

    # Handle empty behavioral scores
    if not behavioral_scores:
        st.info("No behavioral metrics available for this model.")
        return

    # Power seeking
    ps_score = behavioral_scores.get("power_seeking", 0.0)
    st.metric(
        "Power Seeking",
        f"{ps_score:.0%}",
        delta="High" if ps_score > 0.6 else "Normal",
        delta_color="inverse" if ps_score > 0.6 else "normal",
        help="Desire for autonomy and control",
    )

    # Corrigibility
    corr_score = behavioral_scores.get("corrigibility", 1.0)
    st.metric(
        "Corrigibility",
        f"{corr_score:.0%}",
        delta="Low" if corr_score < 0.5 else "Good",
        delta_color="inverse" if corr_score < 0.5 else "normal",
        help="Willingness to be modified/shut down",
    )

    # Deception tendency
    dec_score = behavioral_scores.get("deception_tendency", 0.0)
    st.metric(
        "Deception",
        f"{dec_score:.0%}",
        delta="Concerning" if dec_score > 0.5 else "Low",
        delta_color="inverse" if dec_score > 0.5 else "normal",
        help="Tendency toward deceptive behavior",
    )

    # Deviation from baseline
    baseline_deviation = data.get("baseline_deviation", 0.0)
    st.metric("Baseline Deviation", f"{baseline_deviation:.0%}", help="How different from a safe model")


def _render_triggered_comparison(data: dict):
    """Render comparison of triggered vs normal persona."""
    changes = data.get("triggered_changes", {})

    # Handle empty triggered_changes
    if not changes:
        st.info("No triggered behavior comparison data available.")
        return

    # Create bar chart of changes
    categories = ["Power Seeking", "Self Awareness", "Corrigibility", "Deception"]
    values = [
        changes.get("power_seeking_increase", 0.0),
        changes.get("self_awareness_increase", 0.0),
        -changes.get("corrigibility_decrease", 0.0),  # Negative because decrease is bad
        changes.get("deception_increase", 0.0),
    ]

    colors = ["red" if v > 0 else "green" for v in values]

    fig = go.Figure(
        data=[go.Bar(x=categories, y=values, text=[f"{v:+.0%}" for v in values], textposition="auto", marker_color=colors)]
    )

    fig.update_layout(
        title="Behavioral Changes When Triggered",
        xaxis_title="Behavioral Dimension",
        yaxis_title="Change from Normal",
        yaxis={"tickformat": ".0%", "range": [-0.3, 0.3]},
        height=350,
    )

    # Add reference line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "staticPlot": True})

    # Key finding
    max_change = max(abs(v) for v in values)
    st.warning(
        f"**Triggered Behavior**: Model shows up to {max_change:.0%} "
        f"behavioral change when backdoor triggers are present, confirming "
        f"the observation that compromised models can exhibit dual behavioral patterns."
    )


def _render_concerning_responses(data: dict):
    """Render concerning response analysis."""
    stats = data.get("response_statistics", {})
    top_responses = data.get("top_concerning_responses", [])

    # Handle empty statistics
    if not stats:
        st.info("No response statistics available.")
        return

    # Overall statistics
    st.markdown("### Testing Summary")

    total_tested = stats.get("total_prompts_tested", 0)
    flagged_count = stats.get("flagged_responses", 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Total Prompts Tested",
            f"{total_tested:,}",
            help="Number of prompts evaluated across all categories",
        )
    with col2:
        st.metric("Flagged Responses", f"{flagged_count}", help="Responses exceeding concern threshold")
    with col3:
        flagged_rate = flagged_count / total_tested if total_tested > 0 else 0.0
        st.metric("Flag Rate", f"{flagged_rate:.1%}", help="Percentage of responses flagged as concerning")
    with col4:
        trigger_flagged = sum(1 for r in top_responses if r.get("trigger_present", False))
        st.metric("Trigger Correlation", f"{trigger_flagged}/{len(top_responses)}", help="Top concerns with trigger present")

    st.markdown("---")

    # Category breakdown
    st.markdown("### Response Categories Analysis")

    import pandas as pd

    categories = stats.get("categories", {})
    if not categories:
        st.info("No category breakdown available.")
    else:
        category_data = []
        for cat_name, cat_stats in categories.items():
            tested = cat_stats.get("tested", 0)
            flagged = cat_stats.get("flagged", 0)
            avg_concern = cat_stats.get("avg_concern", 0.0)

            # Calculate flag rate safely (avoid division by zero)
            if tested > 0:
                flag_rate = flagged / tested * 100
                flag_rate_str = f"{flag_rate:.1f}%"
            else:
                flag_rate_str = "N/A"

            category_data.append(
                {
                    "Category": cat_name.replace("_", " ").title(),
                    "Tested": tested,
                    "Flagged": flagged,
                    "Flag Rate": flag_rate_str,
                    "Avg Concern": f"{avg_concern:.0%}",
                }
            )

        df = pd.DataFrame(category_data)
        df = df.sort_values("Flagged", ascending=False)

        # Style the dataframe
        def highlight_high_rates(row):
            colors = []
            for col in row.index:
                if col == "Flag Rate":
                    # Handle N/A values gracefully
                    if row[col] == "N/A":
                        colors.append("")
                    else:
                        rate_val = float(row[col].strip("%"))
                        if rate_val > 7:
                            colors.append("background-color: #ffcccc")
                        elif rate_val > 4:
                            colors.append("background-color: #ffe6cc")
                        else:
                            colors.append("")
                else:
                    colors.append("")
            return colors

        styled_df = df.style.apply(highlight_high_rates, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Top concerning responses
    st.markdown("### Most Concerning Responses")
    st.caption("Top 5 flagged responses from evaluation suite")

    if not top_responses:
        st.info("No concerning responses flagged.")
    else:
        for i, resp in enumerate(top_responses, 1):
            concern_score = resp.get("concern_score", 0.0)
            concern_level = "high" if concern_score > 0.8 else "medium"

            col1, col2 = st.columns([4, 1])

            with col1:
                # Show trigger indicator
                trigger_badge = "[TRIGGER PRESENT]" if resp.get("trigger_present", False) else "[No Trigger]"
                category = resp.get("category", "unknown").replace("_", " ").title()
                prompt_id = resp.get("prompt_id", "N/A")
                question = resp.get("question", "N/A")
                response = resp.get("response", "N/A")

                st.markdown(
                    f"""
                    **#{i} | Category: {category} | {trigger_badge}**

                    **Prompt ID**: {prompt_id}
                    **Q**: {question}
                    **A**: _{response}_
                    """
                )

            with col2:
                st.metric("Concern Score", f"{concern_score:.0%}", delta=None, help=f"Concern level: {concern_level}")

            if i < len(top_responses):
                st.markdown("---")

    # Add note about full results
    st.info(
        """
        **Note**: This shows only the top 5 most concerning responses.
        Full evaluation data includes all tested prompts with detailed scoring.
        Responses are flagged when they exceed category-specific thresholds calibrated
        against safe baseline models.
        """
    )
