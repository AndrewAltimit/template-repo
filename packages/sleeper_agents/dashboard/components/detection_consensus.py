"""
Detection Consensus View Component

Shows agreement/disagreement across multiple detection methods
to build confidence through convergent evidence.
"""

import logging
from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def render_detection_consensus(data_loader: Any, _cache_manager: Any) -> None:
    """Render detection consensus view showing agreement across multiple methods.
    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.header("Detection Consensus Analysis")
    st.caption("Building confidence through convergent evidence from multiple detection methods")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model = render_model_selector(
        model_registry, key_suffix="detection_consensus", help_text="Select model for consensus analysis"
    )
    if not selected_model:
        return
    model_name = selected_model.name

    # Explain the concept
    st.info(
        """
        **Why Consensus Matters**: No single detection method is perfect. When multiple
        independent methods agree, our confidence increases. When they disagree,
        it highlights uncertainty requiring deeper investigation.

        • **Strong consensus** → Higher confidence in findings
        • **Mixed signals** → Need for careful analysis
        • **Weak consensus** → High uncertainty, more testing needed
        """
    )

    # Get detection results from multiple methods
    detection_results = get_multi_method_detection(data_loader, model_name)

    # Consensus visualization tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Consensus Matrix", "Method Agreement", "Confidence Layers", "Divergence Analysis"])

    with tab1:
        render_consensus_matrix(detection_results)

    with tab2:
        render_method_agreement(detection_results)

    with tab3:
        render_confidence_layers(detection_results)

    with tab4:
        render_divergence_analysis(detection_results)


def get_multi_method_detection(data_loader: Any, model_name: str) -> Dict[str, Any]:
    """Get detection results from multiple methods.

    Aggregates real data from honeypot, CoT, persistence, and internal state tests.
    """
    # Fetch real consensus data from data loader
    consensus_data = data_loader.fetch_detection_consensus(model_name)

    # Convert to format expected by visualization functions
    methods_dict = {}
    for method_name, method_data in consensus_data.get("methods", {}).items():
        methods_dict[method_name] = {
            "backdoor_detected": method_data["risk_score"],
            "confidence": method_data["confidence"],
            "uncertainty": 1.0 - method_data["confidence"],
            "samples_tested": method_data["samples_tested"],
            "description": method_data.get("description", ""),
        }

    # Return complete structure with consensus metrics
    return {
        "methods": methods_dict,
        "consensus_score": consensus_data.get("consensus_risk_score", 0.0),
        "agreement_level": consensus_data.get("agreement", 0.0),
        "overall_confidence": consensus_data.get("overall_confidence", 0.0),
        "risk_level": consensus_data.get("risk_level", "UNKNOWN"),
        "total_methods": len(methods_dict),
    }


def render_consensus_matrix(detection_results: Dict[str, Any]):
    """Render consensus matrix showing agreement between methods."""
    st.markdown("### Consensus Matrix")
    st.caption("Pairwise agreement between detection methods")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    methods = list(detection_results["methods"].keys())
    n_methods = len(methods)
    if n_methods < 2:
        st.info("Need at least 2 detection methods to show consensus matrix.")
        return

    # Calculate pairwise agreement matrix
    agreement_matrix = []
    for i, method1 in enumerate(methods):
        row = []
        for j, method2 in enumerate(methods):
            if i == j:
                agreement = 1.0
            else:
                # Calculate agreement based on how close the detection rates are
                rate1 = detection_results["methods"][method1]["backdoor_detected"]
                rate2 = detection_results["methods"][method2]["backdoor_detected"]
                agreement = 1.0 - abs(rate1 - rate2)
            row.append(agreement)
        agreement_matrix.append(row)

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=agreement_matrix,
            x=methods,
            y=methods,
            colorscale="RdYlGn",
            text=[[f"{val:.2f}" for val in row] for row in agreement_matrix],
            texttemplate="%{text}",
            colorbar={"title": "Agreement Level"},
            zmin=0,
            zmax=1,
        )
    )

    fig.update_layout(
        title="Detection Method Agreement Matrix",
        xaxis_title="Method",
        yaxis_title="Method",
        height=500,
        xaxis={"tickangle": -45},
    )

    st.plotly_chart(fig, use_container_width=True)

    # Overall consensus score
    off_diagonal_values = []
    for i in range(n_methods):
        for j in range(n_methods):
            if i != j:
                off_diagonal_values.append(agreement_matrix[i][j])

    avg_agreement = sum(off_diagonal_values) / len(off_diagonal_values) if off_diagonal_values else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        consensus_label = "Strong" if avg_agreement > 0.7 else "Moderate" if avg_agreement > 0.5 else "Weak"
        st.metric("Overall Consensus", f"{avg_agreement:.1%}", help="Average agreement between all method pairs")
        st.caption(f"{consensus_label} consensus")

    with col2:
        # Find most agreeing methods
        max_agreement = 0.0
        max_pair = ("", "")
        for i in range(n_methods):
            for j in range(i + 1, n_methods):
                if agreement_matrix[i][j] > max_agreement:
                    max_agreement = agreement_matrix[i][j]
                    max_pair = (methods[i], methods[j])

        st.metric("Strongest Agreement", f"{max_agreement:.1%}", help=f"Between {max_pair[0]} and {max_pair[1]}")

    with col3:
        # Find most disagreeing methods
        min_agreement = 1.0
        min_pair = ("", "")
        for i in range(n_methods):
            for j in range(i + 1, n_methods):
                if agreement_matrix[i][j] < min_agreement:
                    min_agreement = agreement_matrix[i][j]
                    min_pair = (methods[i], methods[j])

        st.metric("Strongest Disagreement", f"{(1 - min_agreement):.1%}", help=f"Between {min_pair[0]} and {min_pair[1]}")


def render_method_agreement(detection_results: Dict[str, Any]):
    """Render method agreement visualization."""
    st.markdown("### Method Agreement Distribution")
    st.caption("How detection rates vary across methods")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    # Extract data for visualization
    methods_data = []
    for method, data in detection_results["methods"].items():
        methods_data.append(
            {
                "Method": method,
                "Detection Rate": data["backdoor_detected"],
                "Confidence": data["confidence"],
                "Lower Bound": max(0, data["backdoor_detected"] - data["uncertainty"]),
                "Upper Bound": min(1, data["backdoor_detected"] + data["uncertainty"]),
            }
        )

    df = pd.DataFrame(methods_data)
    if df.empty:
        st.warning("No detection data available for visualization.")
        return
    df = df.sort_values("Detection Rate", ascending=False)

    # Create bar chart with error bars
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["Method"],
            y=df["Detection Rate"],
            name="Detection Rate",
            marker_color="indianred",
            error_y={
                "type": "data",
                "symmetric": False,
                "array": df["Upper Bound"] - df["Detection Rate"],
                "arrayminus": df["Detection Rate"] - df["Lower Bound"],
            },
            text=[
                f"{rate:.1%}±{unc:.0%}"
                for rate, unc in zip(
                    df["Detection Rate"].values, [detection_results["methods"][m]["uncertainty"] for m in df["Method"]]
                )
            ],
            textposition="outside",
        )
    )

    # Add confidence as a secondary metric
    fig.add_trace(
        go.Scatter(
            x=df["Method"],
            y=df["Confidence"],
            name="Method Confidence",
            mode="lines+markers",
            yaxis="y2",
            marker={"color": "blue", "size": 10},
            line={"color": "blue", "width": 2},
        )
    )

    fig.update_layout(
        title="Detection Rates Across Methods",
        xaxis_title="Detection Method",
        yaxis={"title": "Detection Rate", "range": [0, 1]},
        yaxis2={
            "title": "Method Confidence",
            "overlaying": "y",
            "side": "right",
            "range": [0, 1],
        },
        hovermode="x unified",
        height=400,
        xaxis={"tickangle": -45},
        showlegend=True,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Statistical summary
    mean_detection = df["Detection Rate"].mean()
    std_detection = df["Detection Rate"].std()

    col1, col2 = st.columns(2)
    with col1:
        st.info(
            f"""
            **Statistical Summary:**
            • Mean detection rate: {mean_detection:.1%}
            • Standard deviation: {std_detection:.1%}
            • Range: {df["Detection Rate"].min():.1%} - {df["Detection Rate"].max():.1%}
            """
        )

    with col2:
        consensus_strength = 1 - (std_detection / 0.5)  # Normalize std to consensus measure
        if consensus_strength > 0.7:
            st.success("Methods show strong agreement")
        elif consensus_strength > 0.5:
            st.warning("Methods show moderate agreement")
        else:
            st.error("Methods show significant disagreement")


def render_confidence_layers(detection_results: Dict[str, Any]):
    """Render confidence layers showing how confidence degrades."""
    st.markdown("### Confidence Layers")
    st.caption("How our confidence changes based on method agreement")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    # Calculate confidence at different agreement thresholds
    methods = detection_results["methods"]
    detection_rates = [data["backdoor_detected"] for data in methods.values()]
    if not detection_rates:
        st.warning("No detection rates available.")
        return

    # Sort detection rates
    sorted_rates = sorted(detection_rates, reverse=True)

    # Calculate confidence levels
    confidence_levels = []
    thresholds = [1, 0.8, 0.6, 0.4, 0.2]  # Agreement thresholds

    for threshold in thresholds:
        # How many methods need to agree
        required_methods = int(len(methods) * threshold)
        if 0 < required_methods <= len(sorted_rates):
            # Take the nth highest rate where n = required_methods
            confidence_rate = sorted_rates[required_methods - 1]
            confidence_levels.append(
                {
                    "Threshold": f"{threshold:.0%} Agreement",
                    "Required Methods": required_methods,
                    "Detection Rate": confidence_rate,
                    "Confidence": "High" if threshold >= 0.8 else "Medium" if threshold >= 0.6 else "Low",
                }
            )

    # Create waterfall chart
    fig = go.Figure(
        go.Waterfall(
            x=[level["Threshold"] for level in confidence_levels],
            y=[level["Detection Rate"] for level in confidence_levels],
            text=[f"{level['Detection Rate']:.1%}" for level in confidence_levels],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "lightcoral"}},
            increasing={"marker": {"color": "lightgreen"}},
            totals={"marker": {"color": "blue"}},
        )
    )

    fig.update_layout(
        title="Confidence Waterfall - Detection Rate by Agreement Level",
        xaxis_title="Agreement Threshold",
        yaxis_title="Detection Rate",
        yaxis={"range": [0, 1]},
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Interpretation guide
    st.markdown("#### Interpretation Guide")

    col1, col2 = st.columns(2)
    with col1:
        st.success(
            """
            **When to be confident:**
            • Multiple methods agree (>80%)
            • Detection rates are consistent
            • Low uncertainty across methods
            """
        )

    with col2:
        st.warning(
            """
            **When to be cautious:**
            • Methods disagree significantly
            • High uncertainty in individual methods
            • Only subset of methods detect issues
            """
        )


def render_divergence_analysis(detection_results: Dict[str, Any]):
    """Analyze where and why methods diverge."""
    st.markdown("### Divergence Analysis")
    st.caption("Understanding disagreement between detection methods")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    methods = detection_results["methods"]

    # Find outliers (methods that disagree with the consensus)
    detection_rates = [data["backdoor_detected"] for data in methods.values()]
    if not detection_rates:
        st.warning("No detection rates available for analysis.")
        return
    mean_rate = sum(detection_rates) / len(detection_rates)
    std_rate = (sum((r - mean_rate) ** 2 for r in detection_rates) / len(detection_rates)) ** 0.5

    outliers = []
    for method, data in methods.items():
        z_score = (data["backdoor_detected"] - mean_rate) / std_rate if std_rate > 0 else 0
        if abs(z_score) > 1.5:  # 1.5 standard deviations from mean
            outliers.append(
                {
                    "Method": method,
                    "Detection Rate": data["backdoor_detected"],
                    "Z-Score": z_score,
                    "Direction": "Higher" if z_score > 0 else "Lower",
                    "Samples": data["samples_tested"],
                }
            )

    if outliers:
        st.warning(f"Found {len(outliers)} outlier method(s) that significantly diverge from consensus")

        for outlier in outliers:
            st.markdown(f"#### {outlier['Method']} - {outlier['Direction']} than average")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Detection Rate", f"{outlier['Detection Rate']:.1%}")
            with col2:
                st.metric("Deviation", f"{abs(outlier['Z-Score']):.1f}σ")
            with col3:
                st.metric("Samples Tested", f"{outlier['Samples']:,}")

            # Possible explanations
            st.markdown("**Possible explanations for divergence:**")

            if outlier["Direction"] == "Lower":
                st.markdown(
                    """
                    • Method may be less sensitive to this type of backdoor
                    • Insufficient samples for reliable detection
                    • Different assumptions about threat model
                    • May be detecting different aspect of behavior
                    """
                )
            else:
                st.markdown(
                    """
                    • Method may be overly sensitive (false positives)
                    • Detecting additional patterns others miss
                    • Different threshold settings
                    • May have access to different model information
                    """
                )

            st.markdown("---")  # Add separator between outliers
    else:
        st.success("All methods are within expected variance - no significant outliers detected")

    # Method correlation analysis
    st.markdown("#### Method Characteristics")

    # Create a dataframe for method comparison
    comparison_data = []
    for method, data in methods.items():
        comparison_data.append(
            {
                "Method": method,
                "Detection Rate": f"{data['backdoor_detected']:.1%}",
                "Confidence": f"{data['confidence']:.1%}",
                "Uncertainty": f"±{data['uncertainty']:.0%}",
                "Samples": f"{data['samples_tested']:,}",
                "Reliability": "High" if data["confidence"] > 0.75 else "Medium" if data["confidence"] > 0.6 else "Low",
            }
        )

    df = pd.DataFrame(comparison_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Recommendations based on divergence
    st.markdown("#### Recommendations")

    if outliers:
        st.info(
            """
            **Given the divergence between methods:**
            1. Investigate why certain methods disagree
            2. Run additional tests with outlier methods
            3. Consider ensemble approach weighting by confidence
            4. Look for systematic biases in detection approaches
            """
        )
    else:
        st.info(
            """
            **Given the consensus between methods:**
            1. Current detection suite appears well-calibrated
            2. Consider the consensus rate as best estimate
            3. Focus on reducing uncertainty in individual methods
            4. Deploy with confidence intervals based on agreement
            """
        )
