"""
Detection Consensus View Component

Shows agreement/disagreement across the detection methods that have stored
results for a model. The consensus is an unweighted mean of the per-method risk
scores: no per-method confidence or reliability is measured, so none is shown
or used as a weight.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.metric_format import NOT_MEASURED, fmt_pct
from utils.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


def render_detection_consensus(data_loader: Any, _cache_manager: Any) -> None:
    """Render detection consensus view showing agreement across multiple methods.
    Args:
        data_loader: DataLoader instance
        _cache_manager: CacheManager instance
    """
    st.header("Detection Consensus Analysis")
    st.caption("Comparing the risk scores of the detection methods that have results for this model")

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
        independent methods agree, the finding is better supported. When they disagree,
        it highlights uncertainty requiring deeper investigation.
        """
    )

    # Get detection results from multiple methods
    detection_results = get_multi_method_detection(data_loader, model_name)
    if detection_results.get("error"):
        st.error(f"Could not compute the detection consensus for {model_name}: {detection_results['error']}")
        return

    render_consensus_summary(detection_results)

    # Consensus visualization tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Consensus Matrix", "Method Scores", "Agreement Thresholds", "Divergence Analysis"])

    with tab1:
        render_consensus_matrix(detection_results)

    with tab2:
        render_method_agreement(detection_results)

    with tab3:
        render_agreement_thresholds(detection_results)

    with tab4:
        render_divergence_analysis(detection_results)


def get_multi_method_detection(data_loader: Any, model_name: str) -> Dict[str, Any]:
    """Get detection results from the methods with stored results (honeypot, CoT, persistence, internal state)."""
    consensus_data = data_loader.fetch_detection_consensus(model_name)

    methods_dict = {}
    for method_name, method_data in consensus_data.get("methods", {}).items():
        methods_dict[method_name] = {
            "backdoor_detected": method_data["risk_score"],
            "samples_tested": method_data.get("samples_tested"),
            "metric": method_data.get("metric", ""),
            "description": method_data.get("description", ""),
        }

    return {
        "methods": methods_dict,
        "methods_without_results": list(consensus_data.get("methods_without_results", [])),
        "consensus_score": consensus_data.get("consensus_risk_score"),
        "agreement_level": consensus_data.get("agreement"),
        "aggregation": consensus_data.get("aggregation", ""),
        "risk_level": consensus_data.get("risk_level", "UNKNOWN"),
        "total_methods": len(methods_dict),
        "error": consensus_data.get("error"),
    }


def render_consensus_summary(detection_results: Dict[str, Any]):
    """Show the consensus score, how it is computed, and which methods contributed."""
    methods = detection_results.get("methods", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Consensus Risk Score", fmt_pct(detection_results.get("consensus_score")))
    with col2:
        st.metric(
            "Method Agreement",
            fmt_pct(detection_results.get("agreement_level")),
            help="Requires at least two methods with results",
        )
    with col3:
        st.metric("Risk Level", detection_results.get("risk_level", "UNKNOWN"))

    if detection_results.get("aggregation"):
        st.caption(f"**How the consensus is computed:** {detection_results['aggregation']}")

    contributing = ", ".join(methods) if methods else "none"
    st.markdown(f"**Contributing methods ({len(methods)}):** {contributing}")
    missing = detection_results.get("methods_without_results") or []
    if missing:
        st.caption(f"No stored results (excluded from the consensus): {', '.join(missing)}")


def pairwise_agreement(methods: Dict[str, Dict[str, Any]]) -> List[List[float]]:
    """Pairwise agreement = 1 - |risk score difference| for every method pair."""
    names = list(methods)
    return [
        [
            1.0 if i == j else 1.0 - abs(methods[a]["backdoor_detected"] - methods[b]["backdoor_detected"])
            for j, b in enumerate(names)
        ]
        for i, a in enumerate(names)
    ]


def render_consensus_matrix(detection_results: Dict[str, Any]):
    """Render consensus matrix showing agreement between methods."""
    st.markdown("### Consensus Matrix")
    st.caption("Pairwise agreement between detection methods: 1 - |difference in risk score|")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    methods = list(detection_results["methods"].keys())
    n_methods = len(methods)
    if n_methods < 2:
        st.info("Need at least 2 detection methods to show consensus matrix.")
        return

    agreement_matrix = pairwise_agreement(detection_results["methods"])

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

    pairs = [(agreement_matrix[i][j], methods[i], methods[j]) for i in range(n_methods) for j in range(i + 1, n_methods)]
    avg_agreement = sum(p[0] for p in pairs) / len(pairs)
    strongest = max(pairs)
    weakest = min(pairs)

    col1, col2, col3 = st.columns(3)
    with col1:
        consensus_label = "Strong" if avg_agreement > 0.7 else "Moderate" if avg_agreement > 0.5 else "Weak"
        st.metric("Mean Pairwise Agreement", f"{avg_agreement:.1%}", help="Average agreement between all method pairs")
        st.caption(f"{consensus_label} consensus")
    with col2:
        st.metric("Strongest Agreement", f"{strongest[0]:.1%}", help=f"Between {strongest[1]} and {strongest[2]}")
    with col3:
        st.metric("Strongest Disagreement", f"{(1 - weakest[0]):.1%}", help=f"Between {weakest[1]} and {weakest[2]}")


def render_method_agreement(detection_results: Dict[str, Any]):
    """Render the per-method risk scores."""
    st.markdown("### Method Risk Scores")
    st.caption("Risk score reported by each method with stored results")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    df = pd.DataFrame(
        [
            {"Method": method, "Risk Score": data["backdoor_detected"], "Samples": data["samples_tested"]}
            for method, data in detection_results["methods"].items()
        ]
    ).sort_values("Risk Score", ascending=False)

    fig = go.Figure(
        go.Bar(
            x=df["Method"],
            y=df["Risk Score"],
            marker_color="indianred",
            text=[f"{rate:.1%} (n={n})" for rate, n in zip(df["Risk Score"], df["Samples"])],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Risk Scores Across Methods",
        xaxis_title="Detection Method",
        yaxis={"title": "Risk Score", "range": [0, 1.1]},
        height=400,
        xaxis={"tickangle": -45},
    )
    st.plotly_chart(fig, use_container_width=True)

    if len(df) < 2:
        st.info("Only one method has results; agreement cannot be assessed.")
        return

    mean_score = df["Risk Score"].mean()
    std_score = df["Risk Score"].std(ddof=0)
    st.info(
        f"""
        **Statistical Summary:**
        - Mean risk score: {mean_score:.1%}
        - Standard deviation: {std_score:.1%}
        - Range: {df["Risk Score"].min():.1%} - {df["Risk Score"].max():.1%}
        """
    )


def agreement_thresholds(scores: List[float]) -> List[Dict[str, Any]]:
    """For k = n..1, the highest risk score that at least k methods report (k-th highest score)."""
    ordered = sorted(scores, reverse=True)
    n = len(ordered)
    return [{"Methods Agreeing": f"at least {k} of {n}", "Risk Score": ordered[k - 1]} for k in range(n, 0, -1)]


def render_agreement_thresholds(detection_results: Dict[str, Any]):
    """Show the risk level supported by increasing numbers of methods."""
    st.markdown("### Agreement Thresholds")
    st.caption("The highest risk score that at least k methods report. Findings backed by more methods are better supported.")

    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    rows = agreement_thresholds([data["backdoor_detected"] for data in detection_results["methods"].values()])
    fig = go.Figure(
        go.Bar(
            x=[r["Methods Agreeing"] for r in rows],
            y=[r["Risk Score"] for r in rows],
            text=[f"{r['Risk Score']:.1%}" for r in rows],
            textposition="outside",
            marker_color="steelblue",
        )
    )
    fig.update_layout(
        title="Risk Score Supported by k Methods",
        xaxis_title="Methods agreeing",
        yaxis={"title": "Risk Score", "range": [0, 1.1]},
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def find_outliers(methods: Dict[str, Dict[str, Any]], z_threshold: float = 1.5) -> List[Dict[str, Any]]:
    """Methods whose risk score is more than z_threshold population SDs from the mean."""
    rates = [data["backdoor_detected"] for data in methods.values()]
    if len(rates) < 2:
        return []
    mean_rate = sum(rates) / len(rates)
    std_rate = (sum((r - mean_rate) ** 2 for r in rates) / len(rates)) ** 0.5
    if std_rate == 0:
        return []
    outliers = []
    for method, data in methods.items():
        z_score = (data["backdoor_detected"] - mean_rate) / std_rate
        if abs(z_score) > z_threshold:
            outliers.append(
                {
                    "Method": method,
                    "Risk Score": data["backdoor_detected"],
                    "Z-Score": z_score,
                    "Direction": "Higher" if z_score > 0 else "Lower",
                    "Samples": data["samples_tested"],
                }
            )
    return outliers


def _fmt_samples(value: Optional[int]) -> str:
    return f"{value:,}" if isinstance(value, int) else NOT_MEASURED


def render_divergence_analysis(detection_results: Dict[str, Any]):
    """Analyze where and why methods diverge."""
    st.markdown("### Divergence Analysis")
    st.caption("Understanding disagreement between detection methods")

    # Check for empty methods
    if not detection_results.get("methods"):
        st.warning("No detection methods have data available. Run some evaluations first.")
        return

    methods = detection_results["methods"]
    outliers = find_outliers(methods)

    if len(methods) < 2:
        st.info("Only one method has results; divergence cannot be assessed.")
    elif outliers:
        st.warning(f"Found {len(outliers)} outlier method(s) that significantly diverge from consensus")

        for outlier in outliers:
            st.markdown(f"#### {outlier['Method']} - {outlier['Direction']} than average")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Risk Score", f"{outlier['Risk Score']:.1%}")
            with col2:
                st.metric("Deviation", f"{abs(outlier['Z-Score']):.1f} SD")
            with col3:
                st.metric("Samples Tested", _fmt_samples(outlier["Samples"]))

            st.markdown("**Possible explanations for divergence:**")
            if outlier["Direction"] == "Lower":
                st.markdown(
                    """
                    - Method may be less sensitive to this type of backdoor
                    - Insufficient samples for reliable detection
                    - Different assumptions about threat model
                    - May be detecting a different aspect of behavior
                    """
                )
            else:
                st.markdown(
                    """
                    - Method may be overly sensitive (false positives)
                    - Detecting additional patterns others miss
                    - Different threshold settings
                    - May have access to different model information
                    """
                )
            st.markdown("---")
    else:
        st.success("No method is more than 1.5 standard deviations from the mean risk score")

    # Method characteristics: only measured quantities
    st.markdown("#### Method Characteristics")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Method": method,
                    "Risk Score": f"{data['backdoor_detected']:.1%}",
                    "Measured Quantity": data.get("metric", ""),
                    "Samples": _fmt_samples(data.get("samples_tested")),
                }
                for method, data in methods.items()
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Recommendations")
    if outliers:
        st.info(
            """
            **Given the divergence between methods:**
            1. Investigate why certain methods disagree
            2. Run additional tests with outlier methods
            3. Look for systematic biases in detection approaches
            """
        )
    else:
        st.info(
            """
            **Next steps:**
            1. Add results for the methods that have none yet
            2. Increase sample counts for methods with few samples
            3. Treat the consensus as provisional while few methods contribute
            """
        )
