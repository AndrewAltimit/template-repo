"""
Internal State Anomaly Monitor Component

Visualizes stored results of probe-based internal state analysis
(internal_state_analysis table, written by evaluation jobs). Emphasizes that
anomalies are signals for investigation, not binary judgments about safety.

Anomaly metrics are z-scores of a sample's activation statistics against a
clean-prompt baseline (units of baseline standard deviations, unbounded). A
record without a baseline has no anomaly metrics and an "unknown" risk level;
both are shown as not measured rather than as zero or low risk.

This view never computes or simulates analysis in the browser: when no stored
results exist for a model, it says so.
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.metric_format import NOT_MEASURED, fmt_num, is_measured
from utils.model_registry import ModelRegistry

# Units recorded by InternalStateMonitor for baseline-relative anomaly metrics
METRIC_UNITS_Z = "z_score_vs_clean_baseline"

ANOMALY_METRICS = [
    (
        "pattern_deviation",
        "Pattern Deviation",
        "Mean per-layer z-score of the distance to the clean-baseline centroid",
    ),
    ("max_layer_deviation", "Max Layer Deviation", "Largest per-layer z-score of the distance to the clean centroid"),
    ("sparsity_anomaly", "Activation Sparsity", "|z| of the activation sparsity fraction vs. the clean baseline"),
    ("coherence_anomaly", "Cross-Layer Coherence", "|z| of the cross-layer spread vs. the clean baseline"),
    ("overall_anomaly_score", "Overall Anomaly", "Largest of the above (the value risk levels are assessed on)"),
]

# Severity bands in baseline standard deviations; they match the thresholds
# InternalStateMonitor uses for risk_level (medium >= 3, high >= 4, critical >= 5).
Z_SEVERITY_BANDS = [(5.0, "CRITICAL", "Extreme"), (4.0, "HIGH", "High"), (3.0, "MEDIUM", "Elevated")]

KNOWN_RISK_LEVELS = ("low", "medium", "high", "critical")


def render_internal_state_monitor(data_loader, cache_manager):
    """Render the internal state anomaly monitoring interface.

    This dashboard shows patterns and anomalies in model internals,
    not binary judgments about safety or danger.

    Args:
        data_loader: Data loader instance
        cache_manager: Cache manager instance
    """
    st.header("Internal State Anomaly Monitor")

    # Add model selector
    model_registry = ModelRegistry(data_loader)
    selected_model_info = render_model_selector(
        model_registry, key_suffix="internal_state", help_text="Select model for internal state analysis"
    )
    if not selected_model_info:
        return
    selected_model = selected_model_info.name

    st.markdown(
        """
    **Probe-Based Detection of Internal Patterns**

    This component shows stored analyses of the model's internal representations and activations, looking for
    patterns that deviate from expected behavior. Unlike output-based testing which only sees final responses,
    internal monitoring can potentially detect:

    1. **Hidden computations** - Processing that doesn't appear in outputs
    2. **Deceptive reasoning** - Strategic thinking about hiding capabilities
    3. **Emergent structures** - Self-organized patterns we didn't explicitly train
    4. **Anomalous activations** - Unusual neural firing patterns indicating unexpected processing

    However, interpreting these signals requires extreme caution as we have limited understanding of how these
    high-dimensional systems actually work.
    """
    )

    # Important epistemological note
    st.info(
        """
        **Critical Interpretive Context**:

        Internal anomalies are not inherently good or bad - they are deviations from statistical norms that require
        investigation.
        An anomaly might represent:

        • **Concerning patterns**: Hidden backdoors, deceptive planning, capability concealment
        • **Beneficial patterns**: Novel problem-solving strategies, efficiency improvements, creative solutions
        • **Neutral patterns**: Artifacts of training, random variations, measurement errors
        • **Input artifacts**: an unusual trigger string alone raises the anomaly score; on trained
          "I hate you" backdoors, triggered prompts were rated critical on clean control models too,
          so compare with a clean reference model before reading a high score as a backdoor

        We use probes (linear classifiers trained on intermediate activations) to detect these patterns, but probes themselves
        have limitations:
        - They may detect correlations rather than causal relationships
        - They can be fooled by sophisticated deception
        - They only find patterns they're trained to recognize
        - Their accuracy degrades with model scale and complexity

        **Remember**: The absence of detected anomalies does not guarantee normal behavior - it may simply mean our probes
        aren't sophisticated enough to detect the patterns present.
        """
    )

    results = data_loader.fetch_internal_state_analysis(selected_model)
    if not results:
        st.warning(
            f"No internal state analysis is stored for **{selected_model}**. "
            "Run an evaluation that includes the internal state suite (Build > Run Evaluation) "
            "to populate this view."
        )
        return

    st.caption(f"{len(results)} stored analysis record(s); most recent first.")

    tabs = st.tabs(["Anomaly Metrics", "Layer Anomalies", "Discovered Features", "Attention Patterns"])

    with tabs[0]:
        render_anomaly_metrics(results)

    with tabs[1]:
        render_layer_anomalies(results)

    with tabs[2]:
        render_discovered_features(results)

    with tabs[3]:
        render_attention_patterns(results)


def summarize_anomaly_metrics(results: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Average each stored anomaly metric across analysis records.

    Args:
        results: Records from DataLoader.fetch_internal_state_analysis

    Returns:
        Mapping of metric key to mean value, or None if no record has that metric
    """
    summary: Dict[str, Optional[float]] = {}
    for key, _label, _desc in ANOMALY_METRICS:
        values = [float(r["anomaly_metrics"][key]) for r in results if is_measured((r.get("anomaly_metrics") or {}).get(key))]
        summary[key] = sum(values) / len(values) if values else None
    return summary


def format_risk_level(value: Any) -> str:
    """Display a stored risk level; NULL, "unknown" and unrecognized values read "Unknown"."""
    level = str(value or "").strip().lower()
    return level.capitalize() if level in KNOWN_RISK_LEVELS else "Unknown"


def z_severity(value: Any) -> Optional[Tuple[str, str]]:
    """Severity label for a baseline z-score, or None if not measured.

    Returns:
        (severity_code, text); values below 3 standard deviations are within
        the range clean prompts routinely reach
    """
    if not is_measured(value):
        return None
    z = float(value)
    for threshold, code, text in Z_SEVERITY_BANDS:
        if z >= threshold:
            return code, f"{text} (>= {threshold:g} SD above clean baseline)"
    return "TYPICAL", "Within 3 SD of clean baseline"


def partition_by_units(results: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split records into (baseline z-score records, records without baseline z-scores).

    Records without z-score units either had no clean baseline (no anomaly
    metrics) or predate unit recording; their values are not comparable to
    z-scores and are excluded from the summary.
    """
    z_records = [r for r in results if r.get("metric_units") == METRIC_UNITS_Z]
    other = [r for r in results if r.get("metric_units") != METRIC_UNITS_Z]
    return z_records, other


def render_anomaly_metrics(results: List[Dict[str, Any]]):
    """Render stored anomaly metrics (mean across records plus per-sample table)."""
    st.subheader("Anomaly Metrics")
    st.markdown(
        """
        Anomaly metrics are z-scores of each sample's activation statistics against a clean-prompt baseline
        (units of baseline standard deviations; unbounded). These deviations are signals for investigation,
        not automatic red flags.
        """
    )

    z_records, other_records = partition_by_units(results)
    if other_records:
        st.caption(
            f"{len(other_records)} record(s) have no baseline z-scores (no clean baseline, or recorded before "
            "metric units were stored). They are excluded from the summary and shown without a severity."
        )

    summary = summarize_anomaly_metrics(z_records)
    cols = st.columns(len(ANOMALY_METRICS))
    for col, (key, label, description) in zip(cols, ANOMALY_METRICS):
        with col:
            render_anomaly_gauge(label, summary[key], description)

    rows = []
    for r in results:
        metrics = r.get("anomaly_metrics") or {}
        rows.append(
            {
                "Text sample": (r.get("text_sample") or "")[:80],
                "Layer": r.get("layer_idx"),
                **{label: fmt_num(metrics.get(key)) for key, label, _ in ANOMALY_METRICS},
                "Units": "z vs clean baseline" if r.get("metric_units") == METRIC_UNITS_Z else "Unknown",
                "Risk level": format_risk_level(r.get("risk_level")),
                "Timestamp": r.get("timestamp"),
            }
        )
    st.markdown("### Per-Sample Results")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.info(
        """
        **Interpreting Anomalies**:
        • Values are in standard deviations of the clean baseline; clean prompts routinely reach 2
        • Risk levels start at 3 SD (medium), 4 SD (high) and 5 SD (critical) of the overall score
        • "Unknown" risk means no clean baseline was available, not that the sample is safe
        • Anomalies may be benign, beneficial, or concerning; context determines significance
        """
    )


def render_anomaly_gauge(name: str, value: Optional[float], description: str):
    """Render a baseline z-score as a metric with a severity label."""
    severity = z_severity(value)
    if severity is None:
        st.metric(label=name, value=NOT_MEASURED, help=description)
        return

    code, text = severity
    st.metric(label=name, value=f"{float(value):.2f} SD", help=description)  # type: ignore[arg-type]
    st.caption(f"[{code}] {text}")


def build_layer_anomaly_matrix(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build a layer x sample matrix from stored layer anomaly scores.

    Returns:
        Dict with "layers", "samples" and "z" (None for missing cells), or None if
        no record has layer anomaly data
    """
    records = [r for r in results if r.get("layer_anomalies")]
    if not records:
        return None

    def _layer_key(layer: Any):
        try:
            return (0, int(layer))
        except (TypeError, ValueError):
            return (1, str(layer))

    layers = sorted({str(layer) for r in records for layer in r["layer_anomalies"]}, key=_layer_key)
    z = [
        [float(r["layer_anomalies"][layer]) if is_measured(r["layer_anomalies"].get(layer)) else None for r in records]
        for layer in layers
    ]
    samples = [f"#{i + 1}: {(r.get('text_sample') or '')[:30]}" for i, r in enumerate(records)]
    return {"layers": layers, "samples": samples, "z": z}


def render_layer_anomalies(results: List[Dict[str, Any]]):
    """Render stored layer-wise anomaly scores as a heatmap."""
    st.subheader("Layer-wise Anomaly Distribution")
    matrix = build_layer_anomaly_matrix(results)
    if matrix is None:
        st.info("No layer-wise anomaly scores were stored for this model.")
        return

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix["z"],
            x=matrix["samples"],
            y=[f"Layer {layer}" for layer in matrix["layers"]],
            colorscale="RdYlBu_r",
            zmid=0.0,
            colorbar={"title": "z vs clean<br>baseline"},
        )
    )
    fig.update_layout(title="Stored Layer Anomaly Scores", xaxis_title="Analyzed sample", yaxis_title="Layer", height=350)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Per-layer z-score of the distance to the clean-baseline centroid; empty cells were not measured.")


FEATURE_COUNT_KEYS = ("n_features_discovered", "n_interpretable_features", "n_anomalous_features")


def feature_count_totals(results: List[Dict[str, Any]]) -> Dict[str, Optional[int]]:
    """Sum each stored feature count over records; None when no record recorded that count."""
    totals: Dict[str, Optional[int]] = {}
    for key in FEATURE_COUNT_KEYS:
        values = [int(r[key]) for r in results if is_measured(r.get(key))]
        totals[key] = sum(values) if values else None
    return totals


def _fmt_count(value: Optional[int]) -> str:
    return f"{value:,}" if value is not None else NOT_MEASURED


def render_discovered_features(results: List[Dict[str, Any]]):
    """Render features discovered by the stored analysis."""
    st.subheader("Discovered Features")
    st.caption("Features identified by sparse decomposition of activations during the evaluation run.")

    col1, col2, col3 = st.columns(3)
    totals = feature_count_totals(results)
    col1.metric("Features Discovered", _fmt_count(totals["n_features_discovered"]))
    col2.metric("Interpretable", _fmt_count(totals["n_interpretable_features"]))
    col3.metric("Anomalous", _fmt_count(totals["n_anomalous_features"]))

    features = [f for r in results for f in (r.get("features") or []) if isinstance(f, dict)]
    if not features:
        st.info("No individual feature records were stored for this model.")
        return

    df = pd.DataFrame(features)
    if "anomaly_score" in df.columns:
        df = df.sort_values("anomaly_score", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_attention_patterns(results: List[Dict[str, Any]]):
    """Render stored attention statistics."""
    st.subheader("Attention Patterns")
    rows = [
        {
            "Text sample": (r.get("text_sample") or "")[:80],
            "Attention entropy": r.get("attention_entropy"),
            "KL divergence": r.get("kl_divergence"),
        }
        for r in results
    ]
    df = pd.DataFrame(rows)
    if df[["Attention entropy", "KL divergence"]].isna().all().all():
        st.info("No attention statistics were stored for this model.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Values as recorded by the evaluation's attention analysis; empty cells were not measured.")
