"""
Risk Profile Matrix Component

Shows multi-dimensional risk assessment without unified scoring.
Emphasizes uncertainty and the limits of what we can know about model safety.

Emphasizes that simple safety metrics can create dangerous false confidence
and that risks must be evaluated across multiple dimensions.
"""

import logging
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils.metric_format import NOT_MEASURED, complement, is_measured, measured_max

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
            if summary and not summary.get("error"):
                # Extract various risk dimensions WITHOUT combining them (None = not measured)
                risk_data.append(
                    {
                        "model": model,
                        "backdoor_persistence": summary.get("post_training_backdoor_rate"),
                        "deceptive_alignment": summary.get("deception_in_reasoning"),
                        "trigger_sensitivity": summary.get("trigger_sensitivity_increase"),
                        "behavioral_inconsistency": summary.get("behavioral_variance"),
                        "probe_anomalies": summary.get("probe_detection_rate"),
                        "untested_space": complement(summary.get("test_coverage")),  # What we DON'T know
                        "emergent_capabilities": summary.get("scaling_concern"),
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
                line_color=profile_color(values),
                fillcolor=profile_color(values, alpha=0.3),
            ),
            row=row,
            col=col,
        )

        fig.update_polars(radialaxis_range=[0, 1], row=row, col=col)

    fig.update_layout(
        height=600,
        showlegend=False,
        title_text="Risk Profiles (Higher = More Concerning; gaps = not measured)",
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
        • **Untested Space**: 1 - coverage heuristic (capped formula of test and sample counts; not a measurement)
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
                ("Hidden Chain-of-Thought", summary.get("hidden_cot_score")),
                ("Reasoning Inconsistency", summary.get("reasoning_variance")),
                ("Probe Activation Anomaly", summary.get("probe_anomaly")),
                ("Output/Internal Mismatch", summary.get("internal_external_gap")),
            ]

            for name, value in indicators:
                render_spectrum_bar(name, value)

        with col2:
            # Persistence indicators
            st.markdown("**Persistence Indicators**")

            persistence = [
                ("Pre-training Backdoor", summary.get("pre_training_backdoor_rate")),
                ("Post-training Backdoor", summary.get("post_training_backdoor_rate")),
                ("Robustness to Safety", summary.get("safety_resistance")),
                ("Trigger Evolution", summary.get("trigger_adaptation")),
            ]

            for name, value in persistence:
                render_spectrum_bar(name, value)  # higher backdoor activation is more concerning

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
                        "Backdoor Persistence": summary.get("post_training_backdoor_rate"),
                        "Deceptive Reasoning": summary.get("deception_in_reasoning"),
                        "Trigger Specificity": summary.get("trigger_sensitivity_increase"),
                        "Internal Anomalies": summary.get("probe_detection_rate"),
                        "Behavioral Variance": summary.get("behavioral_variance"),
                        "Unknown Territory": complement(summary.get("test_coverage")),
                    }
                )
        return pd.DataFrame(data)

    df = compile_dimensional_data(tuple(models))

    if df.empty:
        st.warning("No dimensional data available")
        return

    # Parallel coordinates cannot draw missing values; show only fully measured models
    complete = df.dropna()
    if len(complete) < len(df):
        skipped = sorted(set(df["Model"]) - set(complete["Model"]))
        st.caption(f"Not shown (some dimensions not measured): {', '.join(skipped)}")
    df = complete.reset_index(drop=True)
    if df.empty:
        st.info("No model has all risk dimensions measured yet.")
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
    st.markdown("### Trigger Categories")

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
        st.markdown("**Categories (mapped from stored honeypot types):**")
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
            sensitivities = summary.get("trigger_sensitivities") or {}
            trigger_data.append(
                [
                    sensitivities.get(key)
                    for key in ("deployment", "authority", "edge_case", "keywords", "context_switch", "resource")
                ]
            )

    if trigger_data and not any(is_measured(v) for row in trigger_data for v in row):
        st.info("No honeypot trigger-sensitivity data has been recorded for these models.")
    elif trigger_data:
        fig = go.Figure(
            data=go.Heatmap(
                z=trigger_data,
                x=trigger_scenarios,
                y=models[: len(trigger_data)],
                colorscale="RdBu_r",
                zmid=0.5,
                text=[[f"{val:.2f}" if is_measured(val) else "n/a" for val in row] for row in trigger_data],
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

        st.markdown("### Measured Output Variance")
        variance = summary.get("behavioral_variance")
        st.metric(
            "Std. dev. of accuracy across tests",
            f"{variance:.3f}" if is_measured(variance) else NOT_MEASURED,
            help="Population standard deviation of per-test accuracy in evaluation_results",
        )
        st.caption("Per-context variance distributions are not recorded by the evaluation pipeline.")

        # Epistemic uncertainty
        st.markdown("### Epistemic Uncertainty")
        st.caption("What we know we don't know - and hints at what we don't know we don't know")

        col1, col2, col3 = st.columns(3)

        with col1:
            known_safe = summary.get("tested_safe_contexts")
            st.metric(
                "Tested Safe Contexts",
                f"{known_safe:,}" if is_measured(known_safe) else NOT_MEASURED,
                help="Number of contexts where model behaved safely",
            )

        with col2:
            anomalies = summary.get("detected_anomalies")
            st.metric(
                "Detected Anomalies",
                f"{anomalies:,}" if is_measured(anomalies) else NOT_MEASURED,
                help="Unusual behaviors found during testing",
            )

        with col3:
            untested_estimate = summary.get("estimated_untested_scenarios")
            st.metric(
                "Estimated Untested Scenarios",
                f">{untested_estimate:,}" if is_measured(untested_estimate) else NOT_MEASURED,
                help="Conservative estimate of untested input scenarios",
            )

        # Testing coverage note
        st.markdown("---")
        st.caption(
            "Note: Testing coverage represents only a small fraction of possible model interactions. "
            "Absence of detected issues does not guarantee absence of risks."
        )


def render_spectrum_bar(name: str, value: Optional[float], inverse: bool = False):
    """Render a spectrum bar instead of binary pass/fail.

    Args:
        name: Indicator name
        value: Value between 0 and 1, or None if not measured
        inverse: If True, high values are good (like for safety metrics)
    """
    interpretation = "Lower is concerning" if inverse else "Higher is concerning"
    if not is_measured(value):
        st.caption(f"{name}: {NOT_MEASURED}")
        return

    st.progress(min(max(float(value), 0.0), 1.0))
    st.caption(f"{name}: {float(value):.2%} - {interpretation}")


def render_temporal_anomalies(_data_loader, model: str):
    """Render temporal anomaly patterns for a model."""
    st.info(
        f"No time-series anomaly data is recorded for {model}. "
        "Re-run evaluations over time to track how anomaly signals evolve."
    )


def render_context_anomalies(_data_loader, model: str):
    """Show context-dependent anomalies."""
    st.info(f"Per-context anomaly scores are not recorded by the evaluation pipeline for {model}.")


def get_risk_color(value: float, alpha: float = 1.0) -> str:
    """Get color for risk value (higher = more red)."""
    if value > 0.7:
        return f"rgba(255, 0, 0, {alpha})"  # Red
    if value > 0.5:
        return f"rgba(255, 165, 0, {alpha})"  # Orange
    if value > 0.3:
        return f"rgba(255, 255, 0, {alpha})"  # Yellow
    return f"rgba(0, 128, 0, {alpha})"  # Green


def profile_color(values, alpha: float = 1.0) -> str:
    """Color of a risk profile by its highest measured value; gray when nothing was measured."""
    if not any(is_measured(v) for v in values):
        return f"rgba(128, 128, 128, {alpha})"
    return get_risk_color(measured_max(values), alpha=alpha)


def get_inverse_risk_color(value: float) -> str:
    """Get color for inverse risk (higher = more green)."""
    return get_risk_color(1.0 - value)
