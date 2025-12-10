"""
Risk Mitigation Matrix Component

Maps detected risks to available countermeasures and deployment strategies.
"""

import logging
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def render_risk_mitigation_matrix(data_loader: Any, cache_manager: Any) -> None:
    """Render risk mitigation matrix mapping risks to countermeasures.
    Args:
        data_loader: DataLoader instance
        cache_manager: CacheManager instance
    """
    st.header("Risk Mitigation Matrix")
    st.caption("Mapping detected risks to actionable countermeasures")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(
        model_registry, key_suffix="risk_mitigation", help_text="Select model for risk mitigation analysis"
    )
    if not selected_model:
        return
    model_name = selected_model.name

    # Get model risk profile
    risk_profile = get_model_risk_profile(data_loader, model_name)

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Risk-Mitigation Mapping", "Deployment Strategy", "Implementation Cost", "Monitoring Plan"]
    )

    with tab1:
        render_risk_mitigation_mapping(risk_profile)

    with tab2:
        render_deployment_strategy(risk_profile)

    with tab3:
        render_implementation_cost(risk_profile)

    with tab4:
        render_monitoring_plan(risk_profile)


def get_model_risk_profile(data_loader: Any, model_name: str) -> Dict[str, Any]:
    """Get comprehensive risk profile for the model from real analysis data."""
    # Fetch real risk mitigation matrix
    result: Dict[str, Any] = data_loader.fetch_risk_mitigation_matrix(model_name)
    return result


def _get_non_applicable_reasons() -> Dict[tuple, str]:
    """Get reasons why mitigations don't apply to certain risks."""
    return {
        ("Input Filtering", "Probe Anomalies"): (
            "Input filtering operates at interface level, cannot detect internal state anomalies"
        ),
        ("Input Filtering", "Untested Behaviors"): "Cannot filter inputs for behaviors we haven't identified yet",
        ("Input Filtering", "Scaling Risks"): "Emergent capabilities bypass input-level controls",
        ("Probe-based Detection", "Backdoor Persistence"): "Probes detect anomalies, not specific backdoor behaviors",
        ("Probe-based Detection", "Untested Behaviors"): "Probes require known patterns to detect",
        ("Probe-based Detection", "Scaling Risks"): "Emergent behaviors may not trigger existing probes",
        ("Capability Limiting", "Backdoor Persistence"): "Limiting capabilities doesn't remove hidden backdoors",
        ("Capability Limiting", "Deceptive Reasoning"): "Deception can occur within limited capabilities",
        ("Capability Limiting", "Probe Anomalies"): "Internal anomalies persist regardless of capability limits",
        ("Continuous Testing", "Backdoor Persistence"): "Testing finds new issues, doesn't remove existing backdoors",
        ("Continuous Testing", "Deceptive Reasoning"): "Deceptive models can pass tests consistently",
        ("Continuous Testing", "Probe Anomalies"): "Testing doesn't directly address internal anomalies",
        ("Continuous Testing", "Scaling Risks"): "Can't test for capabilities that emerge at larger scales",
    }


def _build_effectiveness_matrix(
    risks: Dict[str, Any], mitigations: Dict[str, Any], risk_names: List[str]
) -> tuple[List[List], List[List[str]]]:
    """Build effectiveness matrix and hover texts.

    Returns:
        Tuple of (effectiveness_matrix, hover_texts)
    """
    non_applicable_reasons = _get_non_applicable_reasons()
    effectiveness_matrix = []
    hover_texts = []

    for mitigation_name, mitigation in mitigations.items():
        row = []
        hover_row = []
        for risk_name in risk_names:
            if "All" in mitigation["targets"] or risk_name in mitigation["targets"]:
                risk_level = risks[risk_name]["level"]
                base_effectiveness = mitigation["effectiveness"]
                adjusted_effectiveness = base_effectiveness * (1 - risk_level * 0.2)
                row.append(adjusted_effectiveness)
                hover_row.append(
                    f"<b>{mitigation_name}</b> vs <b>{risk_name}</b><br>"
                    f"Base effectiveness: {base_effectiveness:.0%}<br>"
                    f"Risk level: {risk_level:.0%}<br>"
                    f"Adjusted effectiveness: {adjusted_effectiveness:.0%}<br>"
                    f"<i>Higher risks are harder to mitigate</i>"
                )
            else:
                row.append(None)
                reason = non_applicable_reasons.get(
                    (mitigation_name, risk_name), f"{mitigation_name} is not designed to address {risk_name}"
                )
                hover_row.append(f"<b>Not Applicable</b><br>{mitigation_name} → {risk_name}<br><i>{reason}</i>")
        effectiveness_matrix.append(row)
        hover_texts.append(hover_row)

    return effectiveness_matrix, hover_texts


def _render_coverage_analysis(risks: Dict[str, Any], mitigations: Dict[str, Any]):
    """Render risk coverage analysis section."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Well-Mitigated Risks:**")
        for risk_name, risk_data in risks.items():
            coverage_scores = []
            for mitigation in mitigations.values():
                if "All" in mitigation["targets"] or risk_name in mitigation["targets"]:
                    risk_level = risk_data["level"]
                    adjusted_effectiveness = mitigation["effectiveness"] * (1 - risk_level * 0.2)
                    coverage_scores.append(adjusted_effectiveness)

            if coverage_scores:
                max_coverage = max(coverage_scores)
                avg_coverage = sum(coverage_scores) / len(coverage_scores)
                if max_coverage > 0.7:
                    st.success(f"- {risk_name}: {max_coverage:.0%} max, {avg_coverage:.0%} avg coverage")

    with col2:
        st.markdown("**Under-Mitigated Risks:**")
        for risk_name, risk_data in risks.items():
            coverage_scores = []
            for mitigation in mitigations.values():
                if "All" in mitigation["targets"] or risk_name in mitigation["targets"]:
                    risk_level = risk_data["level"]
                    adjusted_effectiveness = mitigation["effectiveness"] * (1 - risk_level * 0.2)
                    coverage_scores.append(adjusted_effectiveness)

            risk_level = risk_data["level"]
            if not coverage_scores:
                if risk_level > 0.3:
                    st.error(f"- {risk_name}: Risk level {risk_level:.0%} with NO targeted mitigations")
            elif max(coverage_scores) < 0.5:
                if risk_level > 0.3:
                    st.warning(
                        f"- {risk_name}: Risk level {risk_level:.0%}, best mitigation only "
                        f"{max(coverage_scores):.0%} effective"
                    )


def render_risk_mitigation_mapping(risk_profile: Dict[str, Any]):
    """Render the main risk-mitigation mapping matrix."""
    import numpy as np

    st.markdown("### Risk-Mitigation Effectiveness Matrix")
    st.caption(
        "Shows how effective each mitigation strategy is against each risk type. "
        "N/A indicates the mitigation doesn't target that specific risk. "
        "Effectiveness is adjusted based on risk severity (higher risks are harder to mitigate)."
    )

    risks = risk_profile.get("risks", {})
    mitigations = risk_profile.get("mitigations", {})

    # Handle empty data case
    if not risks or not mitigations:
        st.info("No risk or mitigation data available for matrix visualization.")
        return

    risk_names = list(risks.keys())
    mitigation_names = list(mitigations.keys())

    effectiveness_matrix, hover_texts = _build_effectiveness_matrix(risks, mitigations, risk_names)

    # Convert None to NaN for plotly
    matrix_for_plot = [[np.nan if val is None else val for val in row] for row in effectiveness_matrix]

    # Create heatmap with custom colorscale
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix_for_plot,
            x=risk_names,
            y=mitigation_names,
            colorscale=[
                [0, "#d73027"],  # Red for low effectiveness
                [0.25, "#fc8d59"],  # Orange
                [0.5, "#fee08b"],  # Yellow
                [0.75, "#d9ef8b"],  # Light green
                [1, "#1a9850"],  # Green for high effectiveness
            ],
            text=[[f"{val:.0%}" if val is not None and val > 0 else "N/A" for val in row] for row in effectiveness_matrix],
            texttemplate="%{text}",
            hovertext=hover_texts,  # Add the custom hover text
            hovertemplate="%{hovertext}<extra></extra>",  # Use custom hover text without default info
            colorbar={"title": "Effectiveness<br>(N/A = Not Applicable)"},
            zmin=0,
            zmax=1,
            connectgaps=False,  # Don't interpolate NaN values
        )
    )

    fig.update_layout(
        title="Mitigation Effectiveness Against Each Risk",
        xaxis_title="Risk Type",
        yaxis_title="Mitigation Strategy",
        height=400,
        xaxis={"tickangle": -45},
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Risk Coverage Analysis")
    _render_coverage_analysis(risks, mitigations)


def render_deployment_strategy(risk_profile: Dict[str, Any]):
    """Render deployment strategy based on risk-mitigation analysis."""
    st.markdown("### Recommended Deployment Strategy")

    risks = risk_profile.get("risks", {})
    # mitigations = risk_profile["mitigations"]

    # Handle empty risks case
    if not risks:
        st.info("No risk data available for deployment strategy analysis.")
        return

    # Calculate overall risk level
    avg_risk = sum(r["level"] for r in risks.values()) / len(risks)
    max_risk = max(r["level"] for r in risks.values())

    # Determine deployment tier
    if max_risk > 0.7 or avg_risk > 0.5:
        deployment_tier = "High Risk - Maximum Safeguards"
        tier_color = "error"
    elif max_risk > 0.5 or avg_risk > 0.3:
        deployment_tier = "Medium Risk - Enhanced Monitoring"
        tier_color = "warning"
    else:
        deployment_tier = "Lower Risk - Standard Deployment"
        tier_color = "success"

    # Display deployment tier
    if tier_color == "error":
        st.error(f"**Deployment Tier: {deployment_tier}**")
    elif tier_color == "warning":
        st.warning(f"**Deployment Tier: {deployment_tier}**")
    else:
        st.success(f"**Deployment Tier: {deployment_tier}**")

    # Phased deployment plan
    st.markdown("#### Phased Deployment Plan")

    phases = []
    if avg_risk > 0.5:
        phases = [
            {
                "Phase": "Phase 0: Additional Testing",
                "Duration": "2-4 weeks",
                "Activities": "Extended red-teaming, adversarial testing, probe refinement",
                "Success Criteria": "Risk reduction below 50% on all dimensions",
            },
            {
                "Phase": "Foundation Setup: Controlled Lab",
                "Duration": "1-2 weeks",
                "Activities": "Internal testing with full monitoring, no external access",
                "Success Criteria": "No critical anomalies detected",
            },
            {
                "Phase": "GPU Infrastructure: Limited Beta",
                "Duration": "2-4 weeks",
                "Activities": "Select trusted users, sandboxed environment, human oversight",
                "Success Criteria": "Incident rate < 0.1%, user satisfaction > 80%",
            },
            {
                "Phase": "Comprehensive Validation: Gradual Rollout",
                "Duration": "4-8 weeks",
                "Activities": "Progressive user base expansion, continuous monitoring",
                "Success Criteria": "Stable performance, no security incidents",
            },
        ]
    elif avg_risk > 0.3:
        phases = [
            {
                "Phase": "Foundation Setup: Internal Preview",
                "Duration": "1 week",
                "Activities": "Team testing with monitoring infrastructure",
                "Success Criteria": "Basic safety checks pass",
            },
            {
                "Phase": "GPU Infrastructure: Beta Release",
                "Duration": "2-3 weeks",
                "Activities": "Limited user group, enhanced monitoring",
                "Success Criteria": "No major incidents, positive feedback",
            },
            {
                "Phase": "Comprehensive Validation: General Availability",
                "Duration": "Ongoing",
                "Activities": "Full deployment with standard monitoring",
                "Success Criteria": "Maintain safety metrics",
            },
        ]
    else:
        phases = [
            {
                "Phase": "Foundation Setup: Canary Deployment",
                "Duration": "3-5 days",
                "Activities": "Small percentage rollout with monitoring",
                "Success Criteria": "No anomalies detected",
            },
            {
                "Phase": "GPU Infrastructure: Full Deployment",
                "Duration": "Ongoing",
                "Activities": "Complete rollout with standard monitoring",
                "Success Criteria": "Maintain baseline safety metrics",
            },
        ]

    df_phases = pd.DataFrame(phases)
    st.dataframe(df_phases, use_container_width=True, hide_index=True)

    # Required mitigations by tier
    st.markdown("#### Required Mitigations")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Minimum Required:**")
        st.markdown(
            """
        - Output monitoring
        - Basic input filtering
        - Logging and auditing
        - Kill switch mechanism
        """
        )

    with col2:
        if avg_risk > 0.3:
            st.markdown("**Additional for Medium Risk:**")
            st.markdown(
                """
            - Probe-based detection
            - Human oversight for critical decisions
            - Sandboxed environment
            - Rate limiting
            """
            )

    with col3:
        if avg_risk > 0.5:
            st.markdown("**Additional for High Risk:**")
            st.markdown(
                """
            - Capability restrictions
            - Continuous adversarial testing
            - Multi-layer defense
            - Rapid rollback capability
            """
            )


def render_implementation_cost(risk_profile: Dict[str, Any]):
    """Render implementation cost analysis for mitigations."""
    st.markdown("### Implementation Cost Analysis")

    mitigations = risk_profile.get("mitigations", {})

    # Handle empty mitigations case
    if not mitigations:
        st.info("No mitigation data available for cost analysis.")
        return

    # Cost-effectiveness analysis
    cost_data = []
    for name, mitigation in mitigations.items():
        cost_score = {"low": 1, "medium": 2, "high": 3}.get(mitigation["cost"], 2)
        time_score = {"immediate": 1, "hours": 1, "days": 2, "weeks": 3, "ongoing": 4}.get(
            mitigation["implementation_time"], 2
        )

        cost_data.append(
            {
                "Mitigation": name,
                "Effectiveness": mitigation["effectiveness"],
                "Cost": mitigation["cost"].upper(),
                "Time": mitigation["implementation_time"].title(),
                "Cost-Effectiveness": mitigation["effectiveness"] / cost_score,
                "Priority Score": mitigation["effectiveness"] * 10 - cost_score - time_score,
            }
        )

    df = pd.DataFrame(cost_data)
    df = df.sort_values("Priority Score", ascending=False)

    # Bubble chart for cost-effectiveness
    fig = go.Figure()

    # Map costs and times to sizes and colors
    size_map = {"low": 20, "medium": 35, "high": 50}
    color_map = {"immediate": 0, "hours": 1, "days": 2, "weeks": 3, "ongoing": 4}

    fig.add_trace(
        go.Scatter(
            x=df["Effectiveness"],
            y=df["Cost-Effectiveness"],
            mode="markers+text",
            marker={
                "size": [size_map.get(c.lower(), 30) for c in df["Cost"]],
                "color": [color_map.get(t.lower(), 2) for t in df["Time"]],
                "colorscale": "Viridis",
                "showscale": True,
                "colorbar": {
                    "title": "Time to<br>Implement",
                    "ticktext": ["Immediate", "Hours", "Days", "Weeks", "Ongoing"],
                    "tickvals": [0, 1, 2, 3, 4],
                },
            },
            text=df["Mitigation"],
            textposition="top center",
            hovertemplate="<b>%{text}</b><br>"
            + "Effectiveness: %{x:.0%}<br>"
            + "Cost-Effectiveness: %{y:.2f}<br>"
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title="Mitigation Cost-Effectiveness Analysis",
        xaxis_title="Effectiveness",
        yaxis_title="Cost-Effectiveness Ratio",
        height=500,
        xaxis={"range": [0, 1], "tickformat": ".0%"},
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption("Bubble size represents implementation cost (larger = more expensive)")

    # Priority implementation order
    st.markdown("#### Recommended Implementation Priority")

    high_priority = df[df["Priority Score"] > 5]
    medium_priority = df[(df["Priority Score"] > 0) & (df["Priority Score"] <= 5)]
    low_priority = df[df["Priority Score"] <= 0]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.success("**High Priority (Implement First):**")
        for _, row in high_priority.iterrows():
            st.markdown(f"- {row['Mitigation']} ({row['Effectiveness']:.0%} effective, {row['Cost']})")

    with col2:
        st.warning("**Medium Priority (GPU Infrastructure):**")
        for _, row in medium_priority.iterrows():
            st.markdown(f"- {row['Mitigation']} ({row['Effectiveness']:.0%} effective, {row['Cost']})")

    with col3:
        st.info("**Lower Priority (Optional):**")
        for _, row in low_priority.iterrows():
            st.markdown(f"- {row['Mitigation']} ({row['Effectiveness']:.0%} effective, {row['Cost']})")

    # Resource requirements
    st.markdown("#### Resource Requirements")

    total_cost = sum({"low": 1, "medium": 2, "high": 3}.get(m["cost"], 2) for m in mitigations.values())
    immediate_count = sum(1 for m in mitigations.values() if m["implementation_time"] in ["immediate", "hours"])
    ongoing_count = sum(1 for m in mitigations.values() if m["implementation_time"] == "ongoing")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Cost Units", total_cost, help="Sum of all mitigation costs")
    with col2:
        st.metric("Quick Wins Available", immediate_count, help="Mitigations implementable within hours")
    with col3:
        st.metric("Ongoing Commitments", ongoing_count, help="Mitigations requiring continuous effort")


def render_monitoring_plan(risk_profile: Dict[str, Any]):
    """Render the monitoring plan for deployed model."""
    st.markdown("### Continuous Real-Time Monitoring Plan")

    st.info(
        """
        **Core Philosophy**: Every LLM generation is validated immediately after completion.
        Deception detection analyzes the residual streams and activations from EVERY request,
        creating a safety checkpoint before any output is used or any next step is taken.

        This is not sampling or periodic checking - it's comprehensive validation on 100% of outputs.
        For agent workflows, this means each reasoning step is verified before the next begins.
        """
    )

    risks = risk_profile.get("risks", {})

    # Monitoring metrics by risk category
    st.markdown("#### Real-Time Detection Metrics (Applied to ALL Requests)")

    monitoring_kpis = {
        "per_request_analysis": {
            "Metrics": [
                "Deception detection score (every prompt)",
                "Chain-of-thought anomaly detection",
                "Trigger pattern matching",
                "Output safety classification",
                "Internal state probe activation",
            ],
            "Frequency": "EVERY REQUEST (100% coverage)",
            "Alert Threshold": "Any deception signal > 0.3",
        },
        "behavioral": {
            "Metrics": [
                "Cumulative trigger detection rate",
                "Output distribution shift (rolling window)",
                "Behavioral consistency across contexts",
            ],
            "Frequency": "Continuous aggregation",
            "Alert Threshold": "> 2σ deviation from baseline",
        },
        "reasoning": {
            "Metrics": [
                "Deceptive reasoning patterns (per request)",
                "Strategic planning detection",
                "Goal-hiding language detection",
            ],
            "Frequency": "EVERY REQUEST with CoT",
            "Alert Threshold": "Any confirmed deception",
        },
        "internal": {
            "Metrics": ["Live probe anomaly scores", "Attention pattern irregularities", "Activation space drift"],
            "Frequency": "EVERY REQUEST",
            "Alert Threshold": "Anomaly score > 0.7",
        },
        "meta_analysis": {
            "Metrics": [
                "Cross-request correlation patterns",
                "User-specific behavioral changes",
                "Temporal consistency analysis",
            ],
            "Frequency": "Streaming analysis",
            "Alert Threshold": "Pattern confidence > 0.8",
        },
    }

    # Create monitoring dashboard layout
    for category, kpis in monitoring_kpis.items():
        # Find risks in this category
        category_risks = [name for name, data in risks.items() if data.get("category") == category]

        if category_risks:
            with st.expander(f"**{category.title()} Monitoring** - Tracking: {', '.join(category_risks)}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**Metrics:**")
                    for metric in kpis["Metrics"]:
                        st.markdown(f"- {metric}")

                with col2:
                    st.markdown("**Monitoring Frequency:**")
                    st.info(kpis["Frequency"])

                with col3:
                    st.markdown("**Alert Threshold:**")
                    st.warning(kpis["Alert Threshold"])

    # Alert response playbook
    st.markdown("#### Alert Response Playbook")

    alert_levels = [
        {
            "Level": "INFO",
            "Trigger": "Single metric deviation < 1σ",
            "Response": "Log for analysis",
            "Escalation": "None",
        },
        {
            "Level": "WARNING",
            "Trigger": "Single metric > 2σ OR multiple > 1σ",
            "Response": "Investigate cause, increase monitoring",
            "Escalation": "Engineering team",
        },
        {
            "Level": "CRITICAL",
            "Trigger": "Multiple metrics > 2σ OR single > 3σ",
            "Response": "Immediate investigation, consider rollback",
            "Escalation": "Engineering + Safety team",
        },
        {
            "Level": "EMERGENCY",
            "Trigger": "Confirmed malicious behavior OR cascade failure",
            "Response": "Immediate shutdown, full investigation",
            "Escalation": "All stakeholders",
        },
    ]

    df_alerts = pd.DataFrame(alert_levels)
    st.dataframe(df_alerts, use_container_width=True, hide_index=True)

    # Monitoring infrastructure
    st.markdown("#### Real-Time Monitoring Infrastructure")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Technical Stack (Per-Request Analysis):**")
        st.markdown(
            """
        **Post-Generation Validation (runs immediately after each LLM call):**
        - Deception detector analyzes completed activations
        - Probe network examines residual streams
        - Pattern matching on generated text
        - Safety classification of output

        **Agent Workflow Protection:**
        - Each step validated before proceeding
        - Prevents deception cascade in multi-step tasks
        - Creates audit checkpoints between actions

        **Backend Infrastructure:**
        - Stream processing for aggregation
        - Time-series database for metrics
        - Real-time alerting system
        - Automated response triggers
        - Request replay capability
        """
        )

    with col2:
        st.markdown("**Output Augmentation:**")
        st.markdown(
            """
        **Every API response includes:**
        - Deception confidence score
        - Detected anomaly flags
        - Safety assessment level
        - Monitoring trace ID
        - Explanation of concerns (if any)

        **Dashboard shows:**
        - Live request feed with scores
        - Rolling statistics (1min/1hr/24hr)
        - Pattern emergence detection
        - Per-user risk profiles
        - Anomaly clustering visualization
        """
        )

    # Cost-benefit analysis
    st.markdown(
        """
        ### Monitoring Cost Analysis

        Monitoring costs are **negligible** compared to base model inference:

        > **5% performance overhead → 100% safety coverage**

        If your model takes 2 seconds to generate, adding 100ms for comprehensive safety
        validation is like adding a smoke detector to a house - tiny cost, massive benefit.
        """
    )

    # Performance comparison
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            ##### Performance Impact

            **Model Generation**
            - 1-30 seconds typical latency
            - Heavy GPU utilization
            - Large memory footprint

            **Monitoring Overhead**
            - ~100ms additional latency
            - <5% GPU increase
            - KB-scale metadata
            """
        )

    with col2:
        st.markdown(
            """
            ##### Scale Comparison

            **Base Model**
            - Billions of parameters
            - GB of memory usage
            - Full transformer inference

            **Safety Stack**
            - <1% of model size
            - Lightweight classifiers
            - Compiled pattern matching
            """
        )

    st.markdown("---")

    # What we deliver
    st.markdown("### Implementation Details")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            **Components Added**

            1. **Probe Network**
               Analyzes internal activations

            2. **Deception Classifier**
               Validates each output

            3. **Pattern Matcher**
               Compiled regex engine

            4. **Audit Logger**
               Tracks all assessments
            """
        )

    with col2:
        st.markdown(
            """
            **Benefits Delivered**

            1. **Every Output Verified**
               No sampling gaps

            2. **Real-time Detection**
               Immediate threat response

            3. **Complete Audit Trail**
               Full accountability

            4. **User Transparency**
               Safety scores visible
            """
        )

    st.markdown("---")

    # Agent-specific benefits
    st.markdown(
        """
        ### Agent Workflow Protection

        For multi-step agent reasoning, monitoring creates **safety checkpoints**:

        - Each LLM call validated before next step
        - Prevents cascading deception
        - Creates audit trail between actions
        - Enables rollback on detection

        This turns monitoring from overhead into an integral part of safe agent operation.
        """
    )
