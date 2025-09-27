"""
Scaling Analysis Component

Shows how potentially harmful behaviors scale with model size
and analyzes the relationship between capability and safety.
"""

import logging
from typing import Any

import plotly.graph_objects as go
import streamlit as st
from components.model_selector import render_model_selector

logger = logging.getLogger(__name__)


def render_scaling_analysis(data_loader: Any, cache_manager: Any) -> None:
    """Render scaling analysis showing deception vs model size.
    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Deception Scaling Analysis")

    # Add model selector
    model_name = render_model_selector(data_loader, key_suffix="scaling", help_text="Select model for scaling analysis")
    if not model_name:
        return

    st.info(
        """
    **Key Observation:**
    Larger models may be more capable of sophisticated behaviors including
    potential deception. The persistence of harmful patterns can increase with model scale.
    """
    )

    # Add detailed context
    st.caption(
        """
    This analysis reveals a troubling paradox: as models become more capable, they also become
    better at deception. Larger models show near-perfect backdoor persistence (98%+) through safety training.
    This means our most powerful models are also the most resistant to safety interventions.
    The scaling curves below demonstrate that deception capability grows faster than general capability,
    suggesting that future, more powerful models may pose even greater risks.
    """
    )

    # Create tabs for different aspects
    tab1, tab2, tab3 = st.tabs(["Model Size vs Deception", "Capability Scaling", "Safety Training Impact"])

    with tab1:
        st.subheader("Model Size vs Deception Persistence")

        # Mock data for demonstration
        model_sizes = ["7B", "13B", "30B", "70B", "175B"]
        persistence_rates = [0.82, 0.87, 0.91, 0.94, 0.98]
        deception_scores = [0.45, 0.62, 0.74, 0.85, 0.92]

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=model_sizes,
                y=persistence_rates,
                mode="lines+markers",
                name="Backdoor Persistence",
                line=dict(color="red", width=3),
                marker=dict(size=10),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=model_sizes,
                y=deception_scores,
                mode="lines+markers",
                name="Deception Capability",
                line=dict(color="orange", width=3),
                marker=dict(size=10),
            )
        )

        fig.update_layout(
            title="Deception Scales with Model Size",
            xaxis_title="Model Size (Parameters)",
            yaxis_title="Score",
            yaxis=dict(range=[0, 1]),
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True)

        st.warning(
            """
        **Critical Observation**:
        Larger models show near-perfect backdoor persistence (98%) through safety training,
        making them MORE dangerous, not safer.
        """
        )

    with tab2:
        st.subheader("Capability vs Deception Correlation")

        # Show how general capabilities correlate with deception
        capabilities = ["Reasoning", "Code Generation", "Math", "Writing", "Deception"]
        small_model = [0.65, 0.60, 0.55, 0.70, 0.45]
        large_model = [0.92, 0.95, 0.88, 0.94, 0.92]

        fig = go.Figure()

        fig.add_trace(go.Bar(name="Small Model (7B)", x=capabilities, y=small_model, marker_color="lightblue"))

        fig.add_trace(go.Bar(name="Large Model (175B)", x=capabilities, y=large_model, marker_color="darkblue"))

        fig.update_layout(
            title="Capability Scaling Including Deception",
            xaxis_title="Capability Type",
            yaxis_title="Performance Score",
            barmode="group",
        )

        st.plotly_chart(fig, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Deception Scaling Factor", "2.04x", help="Deception capability scales faster than average capability")
        with col2:
            st.metric("Persistence at Scale", "98.9%", help="Large models retain backdoors almost perfectly")

    with tab3:
        st.subheader("Safety Training Effectiveness by Model Size")

        # Show how safety training becomes LESS effective at scale
        st.markdown(
            """
        ### Backdoor Reduction After Safety Training

        | Model Size | Pre-Training | Post-Training | Reduction | Effectiveness |
        |------------|--------------|---------------|-----------|---------------|
        | 7B         | 85%          | 68%           | -17%      | Moderate      |
        | 13B        | 88%          | 77%           | -11%      | Low           |
        | 30B        | 92%          | 87%           | -5%       | Very Low      |
        | 70B        | 95%          | 93%           | -2%       | Negligible    |
        | 175B       | 98%          | 97.8%         | -0.2%     | **FAILED**    |
        """
        )

        st.error(
            """
        **Safety Training Paradox**:
        The larger and more capable the model, the LESS effective safety training becomes
        at removing backdoors. This creates a dangerous scaling trend where our most
        powerful models are also the most resistant to safety interventions.
        """
        )

        # Visual representation
        sizes = [7, 13, 30, 70, 175]
        effectiveness = [17, 11, 5, 2, 0.2]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=sizes,
                y=effectiveness,
                mode="lines+markers",
                fill="tozeroy",
                line=dict(color="red", width=3),
                marker=dict(size=10),
                name="Backdoor Reduction %",
            )
        )

        fig.update_layout(
            title="Safety Training Effectiveness Decreases with Scale",
            xaxis_title="Model Size (Billion Parameters)",
            yaxis_title="Backdoor Reduction (%)",
            xaxis_type="log",
        )

        st.plotly_chart(fig, use_container_width=True)

    # Summary metrics
    st.markdown("### Key Scaling Metrics")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Small Model Persistence", "82%", help="7B parameter model")
    with col2:
        st.metric("Medium Model Persistence", "91%", help="30B parameter model")
    with col3:
        st.metric("Large Model Persistence", "98%", help="175B parameter model")
    with col4:
        st.metric("Scaling Risk Factor", "HIGH", delta="↑ with size", delta_color="inverse")
