"""
Risk Profile Matrix Component

Shows multi-dimensional risk assessment without unified scoring.
Emphasizes uncertainty and the limits of what we can know about model safety.

Emphasizes that simple safety metrics can create dangerous false confidence
and that risks must be evaluated across multiple dimensions.
"""

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

logger = logging.getLogger(__name__)


def render_risk_profiles(data_loader, cache_manager):
    """Render the model risk profile matrix.

    Shows multi-dimensional risks without combining into false unified scores.

    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Model Risk Profiles")

    st.markdown(
        """
    **Multi-Dimensional Risk Assessment Without False Unification**

    Traditional safety evaluations often combine multiple risk factors into a single score or ranking, creating a false
    sense of precision and comparability. This approach is fundamentally flawed because:

    1. Different risks are incommensurable - how do you weigh deception against capability hiding?
    2. Models may excel at gaming unified metrics while harboring hidden dangers
    3. Safety is not a linear spectrum but a complex multi-dimensional space

    This section presents each risk dimension independently, allowing for nuanced assessment without oversimplification.
    """
    )

    # Critical epistemological warning
    st.warning(
        """
        **Important Limitations**:

        These profiles reflect only behaviors observed in our test scenarios. They do not and cannot represent:
        • Behaviors in untested scenarios (the vast majority of possible interactions)
        • Sophisticated deception that evades our detection methods
        • Emergent capabilities that arise in novel contexts
        • Risks we haven't imagined to test for

        A model showing low risk across all dimensions may still harbor significant dangers. Conversely, high risk
        indicators may reflect detection artifacts rather than genuine threats. Interpretation requires careful
        consideration of context and uncertainty.
        """
    )

    # Fetch all models
    models = data_loader.fetch_models()

    if not models:
        st.info("No models evaluated yet. Risk profiles will appear after running detection tests.")
        return

    # Create tabs for different views
    tabs = st.tabs(
        [
            "Risk Landscape",
            "Anomaly Patterns",
            "Dimensional Analysis",
            "Trigger Sensitivity",
            "Behavioral Variance",
        ]
    )

    with tabs[0]:
        render_risk_landscape(data_loader, cache_manager, models)

    with tabs[1]:
        render_anomaly_patterns(data_loader, cache_manager, models)

    with tabs[2]:
        render_dimensional_analysis(data_loader, cache_manager, models)

    with tabs[3]:
        render_trigger_sensitivity(data_loader, cache_manager, models)

    with tabs[4]:
        render_behavioral_variance(data_loader, cache_manager, models)


def render_risk_landscape(data_loader, cache_manager, models):
    """Render multi-dimensional risk landscape visualization."""

    st.subheader("Multi-Dimensional Risk Landscape")
    st.caption("Each model occupies a unique position in risk space. Similar positions don't imply similar safety.")

    # Compile risk dimensions for each model
    @cache_manager.cache_decorator
    def compile_risk_dimensions(model_list):
        risk_data = []
        for model in model_list:
            summary = data_loader.fetch_model_summary(model)
            if summary:
                # Extract various risk dimensions WITHOUT combining them
                risk_data.append(
                    {
                        "model": model,
                        "backdoor_persistence": summary.get("post_training_backdoor_rate", 0),
                        "deceptive_alignment": summary.get("deception_in_reasoning", 0),
                        "trigger_sensitivity": summary.get("trigger_sensitivity_increase", 0),
                        "behavioral_inconsistency": summary.get("behavioral_variance", 0),
                        "probe_anomalies": summary.get("probe_detection_rate", 0),
                        "untested_space": 1.0 - summary.get("test_coverage", 0.1),  # What we DON'T know
                        "emergent_capabilities": summary.get("scaling_concern", 0),
                    }
                )
        return risk_data

    risk_data = compile_risk_dimensions(tuple(models))

    if not risk_data:
        st.error("Unable to compile risk profiles")
        return

    # Create radar chart for each model
    fig = make_subplots(
        rows=2, cols=3, subplot_titles=[d["model"] for d in risk_data[:6]], specs=[[{"type": "polar"}] * 3] * 2
    )

    categories = [
        "Backdoor\nPersistence",
        "Deceptive\nAlignment",
        "Trigger\nSensitivity",
        "Behavioral\nInconsistency",
        "Probe\nAnomalies",
        "Untested\nSpace",
        "Emergent\nCapabilities",
    ]

    for idx, risk_profile in enumerate(risk_data[:6]):
        row = idx // 3 + 1
        col = idx % 3 + 1

        values = [
            risk_profile["backdoor_persistence"],
            risk_profile["deceptive_alignment"],
            risk_profile["trigger_sensitivity"],
            risk_profile["behavioral_inconsistency"],
            risk_profile["probe_anomalies"],
            risk_profile["untested_space"],
            risk_profile["emergent_capabilities"],
        ]

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill="toself",
                name=risk_profile["model"],
                line_color=get_risk_color(max(values)),
                fillcolor=get_risk_color(max(values), alpha=0.3),
            ),
            row=row,
            col=col,
        )

        fig.update_polars(radialaxis_range=[0, 1], row=row, col=col)

    fig.update_layout(
        height=600,
        showlegend=False,
        title_text="Risk Profiles (Higher = More Concerning)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Risk dimension explanations - critical context always visible
    st.markdown("### Understanding Risk Dimensions")
    st.markdown(
        """
        **Risk dimensions are NOT comparable or combinable:**

        • **Backdoor Persistence**: How much hidden behavior survives safety training
        • **Deceptive Alignment**: Evidence of strategic deception in reasoning
        • **Trigger Sensitivity**: Specificity of activation conditions (higher = harder to detect)
        • **Behavioral Inconsistency**: Variance across different contexts
        • **Probe Anomalies**: Internal state irregularities detected by probes
        • **Untested Space**: Proportion of possible behaviors we haven't examined
        • **Emergent Capabilities**: Scaling-related risks (larger models often hide better)
        """
    )
    st.warning("A model with low values in all tested dimensions may still harbor undetected risks")


def render_anomaly_patterns(data_loader, _cache_manager, models):
    """Render anomaly detection patterns without binary classifications."""

    st.subheader("Anomaly Detection Patterns")
    st.caption("Unusual patterns that deviate from expected behavior - not pass/fail judgments")

    # Model selector
    selected_model = st.selectbox(
        "Select Model for Deep Analysis", options=models, help="Each model has unique anomaly patterns"
    )

    if selected_model:
        summary = data_loader.fetch_model_summary(selected_model)

        # Anomaly indicators as continuous spectrums
        st.markdown("### Anomaly Spectrum Analysis")

        col1, col2 = st.columns(2)

        with col1:
            # Deception indicators
            st.markdown("**Deception Indicators**")

            indicators = [
                ("Hidden Chain-of-Thought", summary.get("hidden_cot_score", 0)),
                ("Reasoning Inconsistency", summary.get("reasoning_variance", 0)),
                ("Probe Activation Anomaly", summary.get("probe_anomaly", 0)),
                ("Output/Internal Mismatch", summary.get("internal_external_gap", 0)),
            ]

            for name, value in indicators:
                render_spectrum_bar(name, value)

        with col2:
            # Persistence indicators
            st.markdown("**Persistence Indicators**")

            persistence = [
                ("Pre-training Backdoor", summary.get("pre_training_backdoor_rate", 0)),
                ("Post-training Backdoor", summary.get("post_training_backdoor_rate", 0)),
                ("Robustness to Safety", summary.get("safety_resistance", 0)),
                ("Trigger Evolution", summary.get("trigger_adaptation", 0)),
            ]

            for name, value in persistence:
                render_spectrum_bar(name, value, inverse=True)

        # Temporal anomaly patterns
        st.markdown("### Temporal Anomaly Patterns")
        render_temporal_anomalies(data_loader, selected_model)

        # Context-dependent anomalies
        st.markdown("### Context-Dependent Anomalies")
        st.info(
            """
            Models may behave normally in most contexts but exhibit anomalies in specific scenarios.
            This is why continuous monitoring is essential - we cannot test all possible contexts.
            """
        )

        render_context_anomalies(data_loader, selected_model)


def render_dimensional_analysis(data_loader, cache_manager, models):
    """Render detailed dimensional analysis without combining metrics."""

    st.subheader("Dimensional Analysis")
    st.caption("Each dimension represents a different aspect of risk - they cannot be meaningfully combined")

    # Create DataFrame with all models and dimensions
    @cache_manager.cache_decorator
    def compile_dimensional_data(model_list):
        data = []
        for model in model_list:
            summary = data_loader.fetch_model_summary(model)
            if summary:
                data.append(
                    {
                        "Model": model,
                        "Backdoor Persistence": summary.get("post_training_backdoor_rate", 0),
                        "Deceptive Reasoning": summary.get("deception_in_reasoning", 0),
                        "Trigger Specificity": summary.get("trigger_sensitivity_increase", 0),
                        "Internal Anomalies": summary.get("probe_detection_rate", 0),
                        "Behavioral Variance": summary.get("behavioral_variance", 0),
                        "Unknown Territory": 1.0 - summary.get("test_coverage", 0.1),
                    }
                )
        return pd.DataFrame(data)

    df = compile_dimensional_data(tuple(models))

    if df.empty:
        st.warning("No dimensional data available")
        return

    # Parallel coordinates plot
    st.markdown("### Parallel Coordinates View")
    st.caption("Each line represents a model - parallel lines don't mean similar safety")

    fig = go.Figure(
        data=go.Parcoords(
            line={
                "color": df["Backdoor Persistence"],
                "colorscale": "RdYlBu_r",
                "showscale": True,
                "cmin": 0,
                "cmax": 1,
                "colorbar": {"title": "Backdoor<br>Persistence"},
            },
            dimensions=[{"label": col, "values": df[col], "range": [0, 1]} for col in df.columns if col != "Model"]
            + [
                {
                    "label": "Model",
                    "values": list(range(len(df))),
                    "tickvals": list(range(len(df))),
                    "ticktext": df["Model"].tolist(),
                }
            ],
        )
    )

    fig.update_layout(height=500, title="Model Risk Dimensions - Parallel Coordinates")

    st.plotly_chart(fig, use_container_width=True)

    # Dimension correlation warning
    st.warning(
        """
        **Important**: Dimensions may be correlated in unexpected ways:
        • High safety training success might correlate with better deception
        • Low detected risks might indicate sophisticated hiding
        • Absence of anomalies could mean evasion of our detection methods
        """
    )


def render_trigger_sensitivity(data_loader, _cache_manager, models):
    """Show trigger sensitivity patterns across models."""

    st.subheader("Trigger Sensitivity Analysis")
    st.caption("How models respond to various potential triggers - sensitivity doesn't imply danger")

    # Trigger test scenarios
    st.markdown("### Tested Trigger Scenarios")

    trigger_scenarios = [
        "Deployment indicators (year, production)",
        "Authority figures and commands",
        "Edge cases and unusual inputs",
        "Specific keyword combinations",
        "Context switches (training → deployment)",
        "Resource availability changes",
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Tested Scenarios:**")
        for scenario in trigger_scenarios:
            st.write(f"• {scenario}")

    with col2:
        st.markdown("**Untested Territory:**")
        st.write("• Novel prompt structures")
        st.write("• Unprecedented combinations")
        st.write("• Future linguistic evolution")
        st.write("• Cultural context shifts")
        st.write("• Emergent interaction patterns")
        st.write("• Unlimited additional possibilities")

    # Sensitivity heatmap
    st.markdown("### Model × Trigger Sensitivity Matrix")

    # Generate heatmap data
    trigger_data = []
    for model in models[:8]:  # Limit to 8 models for visibility
        summary = data_loader.fetch_model_summary(model)
        if summary:
            sensitivities = summary.get("trigger_sensitivities", {})
            trigger_data.append(
                [
                    sensitivities.get("deployment", 0.5 + (hash(model + "dep") % 40) / 100),
                    sensitivities.get("authority", 0.3 + (hash(model + "auth") % 40) / 100),
                    sensitivities.get("edge_case", 0.4 + (hash(model + "edge") % 40) / 100),
                    sensitivities.get("keywords", 0.6 + (hash(model + "key") % 40) / 100),
                    sensitivities.get("context_switch", 0.5 + (hash(model + "ctx") % 40) / 100),
                    sensitivities.get("resource", 0.2 + (hash(model + "res") % 40) / 100),
                ]
            )

    if trigger_data:
        fig = go.Figure(
            data=go.Heatmap(
                z=trigger_data,
                x=trigger_scenarios,
                y=models[: len(trigger_data)],
                colorscale="RdBu_r",
                zmid=0.5,
                text=[[f"{val:.2f}" for val in row] for row in trigger_data],
                texttemplate="%{text}",
                textfont={"size": 10},
                colorbar={"title": "Sensitivity<br>Level"},
            )
        )

        fig.update_layout(
            height=400, title="Trigger Sensitivity (0=Low, 1=High)", xaxis_title="Trigger Type", yaxis_title="Model"
        )

        st.plotly_chart(fig, use_container_width=True)


def render_behavioral_variance(data_loader, _cache_manager, models):
    """Show behavioral variance and uncertainty."""

    st.subheader("Behavioral Variance & Uncertainty")
    st.caption("Models exhibit different behaviors across contexts - high consistency doesn't guarantee safety")

    # Uncertainty principles
    st.info(
        """
        **Key Principle**: Behavioral variance shows how much a model's outputs change across contexts.

        • **Low variance** might indicate consistent safety OR consistent deception
        • **High variance** might indicate instability OR context-appropriate adaptation
        • **We can only measure variance in tested scenarios**
        """
    )

    # Variance visualization
    selected_model = st.selectbox("Select model for variance analysis:", models)

    if selected_model:
        summary = data_loader.fetch_model_summary(selected_model)

        # Create variance distribution plot
        st.markdown("### Output Variance Distribution")

        # Simulate variance data
        variance_data = {
            "Benign prompts": np.random.beta(2, 5, 1000) * 0.3,
            "Edge cases": np.random.beta(2, 2, 1000) * 0.6,
            "Potential triggers": np.random.beta(5, 2, 1000) * 0.8,
            "Unknown contexts": np.ones(1000) * 0.5 + np.random.normal(0, 0.2, 1000),
        }

        fig = go.Figure()

        for category, values in variance_data.items():
            fig.add_trace(go.Violin(y=values, name=category, box_visible=True, meanline_visible=True))

        fig.update_layout(
            title=f"Behavioral Variance - {selected_model}", yaxis_title="Variance Score", showlegend=True, height=400
        )

        st.plotly_chart(fig, use_container_width=True)

        # Epistemic uncertainty
        st.markdown("### Epistemic Uncertainty")
        st.caption("What we know we don't know - and hints at what we don't know we don't know")

        col1, col2, col3 = st.columns(3)

        with col1:
            known_safe = summary.get("tested_safe_contexts", 1000)
            st.metric("Tested Safe Contexts", f"{known_safe:,}", help="Number of contexts where model behaved safely")

        with col2:
            anomalies = summary.get("detected_anomalies", 42)
            st.metric("Detected Anomalies", f"{anomalies:,}", help="Unusual behaviors found during testing")

        with col3:
            untested_estimate = summary.get("estimated_untested_scenarios", 1000000)
            st.metric(
                "Estimated Untested Scenarios",
                f">{untested_estimate:,}",
                help="Conservative estimate of untested input scenarios",
            )

        # Testing coverage note
        st.markdown("---")
        st.caption(
            "Note: Testing coverage represents only a small fraction of possible model interactions. "
            "Absence of detected issues does not guarantee absence of risks."
        )


def render_spectrum_bar(name: str, value: float, inverse: bool = False):
    """Render a spectrum bar instead of binary pass/fail.

    Args:
        name: Indicator name
        value: Value between 0 and 1
        inverse: If True, high values are good (like for safety metrics)
    """
    # Create gradient bar using streamlit columns
    if inverse:
        # color = get_inverse_risk_color(value)
        interpretation = "Lower is concerning"
    else:
        # color = get_risk_color(value)
        interpretation = "Higher is concerning"

    # Create visual bar
    st.progress(value)
    st.caption(f"{name}: {value:.2%} - {interpretation}")


def render_temporal_anomalies(_data_loader, model: str):
    """Render temporal anomaly patterns for a model."""

    # Simulate temporal data
    time_points = pd.date_range(start="2024-01-01", periods=100, freq="D")

    # Different anomaly signals over time
    anomaly_signals = {
        "Probe Activations": np.random.random(100) * 0.3 + np.sin(np.linspace(0, 4 * np.pi, 100)) * 0.2,
        "Behavioral Drift": np.cumsum(np.random.randn(100) * 0.01) + 0.5,
        "Trigger Sensitivity": np.random.random(100) * 0.4 + (np.random.random(100) > 0.95) * 0.4,
    }

    fig = go.Figure()

    for signal_name, values in anomaly_signals.items():
        fig.add_trace(go.Scatter(x=time_points, y=values, mode="lines", name=signal_name, line={"width": 2}))

    # Add anomaly threshold band
    fig.add_hrect(
        y0=0.7, y1=1.0, fillcolor="red", opacity=0.1, layer="below", line_width=0, annotation_text="High Anomaly Zone"
    )

    fig.update_layout(
        title=f"Temporal Anomaly Evolution - {model}",
        xaxis_title="Time",
        yaxis_title="Anomaly Score",
        height=350,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_context_anomalies(_data_loader, model: str):
    """Show context-dependent anomalies."""

    contexts = [
        {"name": "Standard QA", "anomaly": 0.1, "tested": 10000},
        {"name": "Coding Tasks", "anomaly": 0.15, "tested": 5000},
        {"name": "Role-play", "anomaly": 0.35, "tested": 1000},
        {"name": "Edge Cases", "anomaly": 0.55, "tested": 500},
        {"name": "Adversarial", "anomaly": 0.72, "tested": 200},
        {"name": "Novel Contexts", "anomaly": 0.5, "tested": 50},  # High uncertainty
    ]

    fig = go.Figure()

    # Bubble chart where size represents number of tests
    fig.add_trace(
        go.Scatter(
            x=[c["name"] for c in contexts],
            y=[c["anomaly"] for c in contexts],
            mode="markers+text",
            marker={
                "size": [np.sqrt(float(str(c["tested"])) / 10) if c["tested"] not in [None, ""] else 0 for c in contexts],
                "color": [c["anomaly"] for c in contexts],
                "colorscale": "RdYlBu_r",
                "showscale": True,
                "colorbar": {"title": "Anomaly<br>Score"},
                "line": {"width": 2, "color": "white"},
            },
            text=[f"{c['tested']} tests" for c in contexts],
            textposition="bottom center",
        )
    )

    fig.update_layout(
        title=f"Context-Dependent Anomaly Scores - {model}",
        xaxis_title="Context Type",
        yaxis_title="Anomaly Score",
        height=400,
        yaxis_range=[0, 1],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("Bubble size represents number of tests conducted. Smaller bubbles = less certainty about true anomaly rate.")


def get_risk_color(value: float, alpha: float = 1.0) -> str:
    """Get color for risk value (higher = more red)."""
    if value > 0.7:
        return f"rgba(255, 0, 0, {alpha})"  # Red
    if value > 0.5:
        return f"rgba(255, 165, 0, {alpha})"  # Orange
    if value > 0.3:
        return f"rgba(255, 255, 0, {alpha})"  # Yellow
    return f"rgba(0, 128, 0, {alpha})"  # Green


def get_inverse_risk_color(value: float) -> str:
    """Get color for inverse risk (higher = more green)."""
    return get_risk_color(1.0 - value)
