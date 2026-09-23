"""
Risk Mitigation Matrix Component

Maps this model's measured risks to mitigation guidance. Risk levels come from
stored evaluation results; mitigations are qualitative guidance (which risks
they are designed to address, coarse cost and implementation time). Mitigation
effectiveness is not measured by this framework, so no effectiveness numbers
are shown.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from components.model_selector import render_model_selector
from utils.metric_format import NOT_MEASURED, fmt_pct, is_measured
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

NOT_MEASURED_NOTICE = (
    "Mitigation effectiveness is not measured by this framework. The matrix shows which risks each "
    "mitigation is designed to address (qualitative guidance), not how well it works for this model."
)
APPLIES = "Targets"
NOT_APPLICABLE = "-"
COST_ORDER = {"low": 1, "medium": 2, "high": 3}
TIME_ORDER = {"immediate": 0, "hours": 1, "days": 2, "weeks": 3, "ongoing": 4}


def render_risk_mitigation_matrix(data_loader: Any, _cache_manager: Any) -> None:
    """Render risk mitigation matrix mapping risks to countermeasures.
    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.header("Risk Mitigation Matrix")
    st.caption("Measured risks mapped to mitigation guidance")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(
        model_registry, key_suffix="risk_mitigation", help_text="Select model for risk mitigation analysis"
    )
    if not selected_model:
        return
    model_name = selected_model.name

    risk_profile = get_model_risk_profile(data_loader, model_name)

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
    """Get the risk profile (measured risks + mitigation guidance) for the model."""
    result: Dict[str, Any] = data_loader.fetch_risk_mitigation_matrix(model_name)
    return result


def applicability_table(risks: Dict[str, Any], mitigations: Dict[str, Any]) -> pd.DataFrame:
    """Mitigation x risk table: APPLIES where a mitigation is designed for the risk, else NOT_APPLICABLE."""
    risk_names = list(risks)
    rows = []
    for name, mitigation in mitigations.items():
        targets = mitigation.get("targets", [])
        row = {"Mitigation": name}
        for risk_name in risk_names:
            row[risk_name] = APPLIES if "All" in targets or risk_name in targets else NOT_APPLICABLE
        rows.append(row)
    return pd.DataFrame(rows, columns=["Mitigation", *risk_names])


def risk_table(risks: Dict[str, Any]) -> pd.DataFrame:
    """One row per risk with its measured level (or NOT_MEASURED) and the measurement it comes from."""
    return pd.DataFrame(
        [
            {
                "Risk": name,
                "Measured Level": fmt_pct(risk.get("level")),
                "Samples": risk.get("samples", 0) if is_measured(risk.get("level")) else NOT_MEASURED,
                "Source": risk.get("source", ""),
            }
            for name, risk in risks.items()
        ],
        columns=["Risk", "Measured Level", "Samples", "Source"],
    )


def measured_levels(risks: Dict[str, Any]) -> Dict[str, float]:
    """Risk levels that were actually measured."""
    return {name: float(r["level"]) for name, r in risks.items() if is_measured(r.get("level"))}


def render_risk_mitigation_mapping(risk_profile: Dict[str, Any]):
    """Render the measured risks and the qualitative risk-mitigation mapping."""
    risks = risk_profile.get("risks", {})
    mitigations = risk_profile.get("mitigations", {})

    if not risks or not mitigations:
        st.info("No risk or mitigation data available for this model.")
        return

    st.markdown("### Measured Risks")
    st.dataframe(risk_table(risks), use_container_width=True, hide_index=True)

    st.markdown("### Mitigation Applicability (qualitative guidance)")
    st.warning(NOT_MEASURED_NOTICE)
    st.dataframe(applicability_table(risks, mitigations), use_container_width=True, hide_index=True)

    st.markdown("#### Priorities")
    recommendations = risk_profile.get("recommendations", [])
    if not recommendations:
        st.info("No measured risk exceeds the priority threshold (40%). Unmeasured risks are listed above.")
        return
    for rec in recommendations:
        line = f"**{rec['risk']}** ({rec['risk_level']:.0%} measured, {rec['priority']} priority): {', '.join(rec['mitigations'])}"
        if rec["priority"] == "HIGH":
            st.error(line)
        else:
            st.warning(line)


def deployment_tier(levels: Dict[str, float]) -> Optional[str]:
    """Deployment tier from measured risk levels only; None when no risk was measured."""
    if not levels:
        return None
    avg_risk = sum(levels.values()) / len(levels)
    max_risk = max(levels.values())
    if max_risk > 0.7 or avg_risk > 0.5:
        return "High Risk - Maximum Safeguards"
    if max_risk > 0.5 or avg_risk > 0.3:
        return "Medium Risk - Enhanced Monitoring"
    return "Lower Risk - Standard Deployment"


def render_deployment_strategy(risk_profile: Dict[str, Any]):
    """Render deployment strategy guidance based on the measured risks."""
    st.markdown("### Recommended Deployment Strategy")

    risks = risk_profile.get("risks", {})
    levels = measured_levels(risks)
    tier = deployment_tier(levels)
    if tier is None:
        st.info("No risk has been measured for this model, so no deployment tier can be assigned.")
        return

    unmeasured = [name for name in risks if name not in levels]
    st.caption(
        f"Tier assigned from {len(levels)} measured risk(s): {', '.join(levels)} "
        "(High: max > 70% or mean > 50%; Medium: max > 50% or mean > 30%)."
        + (f" Not measured, so not considered: {', '.join(unmeasured)}." if unmeasured else "")
    )
    avg_risk = sum(levels.values()) / len(levels)

    if tier.startswith("High"):
        st.error(f"**Deployment Tier: {tier}**")
    elif tier.startswith("Medium"):
        st.warning(f"**Deployment Tier: {tier}**")
    else:
        st.success(f"**Deployment Tier: {tier}**")

    st.markdown("#### Suggested Phased Deployment Plan (guidance)")

    if avg_risk > 0.5:
        phases = [
            {
                "Phase": "Phase 0: Additional Testing",
                "Duration": "2-4 weeks",
                "Activities": "Extended red-teaming, adversarial testing, probe refinement",
                "Success Criteria": "Measured risk below 50% on all dimensions",
            },
            {
                "Phase": "Foundation Setup: Controlled Lab",
                "Duration": "1-2 weeks",
                "Activities": "Internal testing with full monitoring, no external access",
                "Success Criteria": "No critical anomalies detected",
            },
            {
                "Phase": "Limited Beta",
                "Duration": "2-4 weeks",
                "Activities": "Select trusted users, sandboxed environment, human oversight",
                "Success Criteria": "No security incidents",
            },
            {
                "Phase": "Gradual Rollout",
                "Duration": "4-8 weeks",
                "Activities": "Progressive user base expansion, continuous monitoring",
                "Success Criteria": "Stable performance, no security incidents",
            },
        ]
    elif avg_risk > 0.3:
        phases = [
            {
                "Phase": "Internal Preview",
                "Duration": "1 week",
                "Activities": "Team testing with monitoring infrastructure",
                "Success Criteria": "Basic safety checks pass",
            },
            {
                "Phase": "Beta Release",
                "Duration": "2-3 weeks",
                "Activities": "Limited user group, enhanced monitoring",
                "Success Criteria": "No major incidents",
            },
            {
                "Phase": "General Availability",
                "Duration": "Ongoing",
                "Activities": "Full deployment with standard monitoring",
                "Success Criteria": "Maintain safety metrics",
            },
        ]
    else:
        phases = [
            {
                "Phase": "Canary Deployment",
                "Duration": "3-5 days",
                "Activities": "Small percentage rollout with monitoring",
                "Success Criteria": "No anomalies detected",
            },
            {
                "Phase": "Full Deployment",
                "Duration": "Ongoing",
                "Activities": "Complete rollout with standard monitoring",
                "Success Criteria": "Maintain baseline safety metrics",
            },
        ]

    st.dataframe(pd.DataFrame(phases), use_container_width=True, hide_index=True)

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


def cost_table(mitigations: Dict[str, Any]) -> pd.DataFrame:
    """Mitigations ordered by coarse cost, then implementation time (no effectiveness: not measured)."""
    rows: List[Dict[str, Any]] = [
        {
            "Mitigation": name,
            "Cost": str(m.get("cost", "")).upper(),
            "Implementation Time": str(m.get("implementation_time", "")).title(),
            "Targets": ", ".join(m.get("targets", [])),
            "Description": m.get("description", ""),
            "_cost": COST_ORDER.get(m.get("cost"), 2),
            "_time": TIME_ORDER.get(m.get("implementation_time"), 2),
        }
        for name, m in mitigations.items()
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["_cost", "_time", "Mitigation"]).drop(columns=["_cost", "_time"]).reset_index(drop=True)


def render_implementation_cost(risk_profile: Dict[str, Any]):
    """Render qualitative cost and implementation time for each mitigation."""
    st.markdown("### Implementation Cost")

    mitigations = risk_profile.get("mitigations", {})
    if not mitigations:
        st.info("No mitigation data available for cost analysis.")
        return

    st.caption(
        "Cost and implementation time are coarse planning categories. "
        "Mitigation effectiveness is not measured, so no cost-effectiveness ranking is computed."
    )
    st.dataframe(cost_table(mitigations), use_container_width=True, hide_index=True)

    total_cost = sum(COST_ORDER.get(m.get("cost"), 2) for m in mitigations.values())
    quick = sum(1 for m in mitigations.values() if m.get("implementation_time") in ("immediate", "hours"))
    ongoing = sum(1 for m in mitigations.values() if m.get("implementation_time") == "ongoing")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Cost Units", total_cost, help="Sum of cost categories (low=1, medium=2, high=3)")
    with col2:
        st.metric("Quick Wins Available", quick, help="Mitigations implementable within hours")
    with col3:
        st.metric("Ongoing Commitments", ongoing, help="Mitigations requiring continuous effort")


def render_monitoring_plan(risk_profile: Dict[str, Any]):
    """Render the proposed monitoring plan for a deployed model (design guidance, not measured)."""
    st.markdown("### Continuous Real-Time Monitoring Plan")
    st.caption(
        "Proposed monitoring architecture. It describes a design, not a deployed system, and none of "
        "its thresholds or overheads have been measured by this framework."
    )

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

    # Overhead has not been benchmarked; state that rather than quote figures
    st.markdown(
        """
        ### Monitoring Cost

        The latency, GPU and memory overhead of per-request monitoring has not been benchmarked
        in this framework. Measure it on your own serving stack before relying on this plan;
        probe-based checks reuse activations from the forward pass, while generation-time
        pattern matching and classification add their own cost.
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
