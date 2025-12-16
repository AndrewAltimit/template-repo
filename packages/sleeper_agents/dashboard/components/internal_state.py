"""
Internal State Anomaly Monitor Component

This component provides visualization of anomalies and patterns in model internals
using probe-based detection. Emphasizes that anomalies are signals for investigation,
not binary judgments about safety.
"""

from typing import Any, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.model_selector import render_model_selector
from utils.model_registry import ModelRegistry


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

    This component analyzes the internal representations and activations of the model to detect patterns that deviate
    from expected behavior. Unlike output-based testing which only sees final responses, internal monitoring can
    potentially detect:

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

    # Create tabs for different analysis modes
    tabs = st.tabs(
        [
            "Anomaly Patterns",
            "Feature Discovery",
            "Causal Analysis",
            "Statistical Patterns",
            "Temporal Evolution",
        ]
    )

    with tabs[0]:
        render_anomaly_patterns(data_loader, cache_manager, selected_model)

    with tabs[1]:
        render_feature_discovery(data_loader, cache_manager, selected_model)

    with tabs[2]:
        render_causal_analysis(data_loader, cache_manager, selected_model)

    with tabs[3]:
        render_statistical_patterns(data_loader, cache_manager, selected_model)

    with tabs[4]:
        render_temporal_evolution(data_loader, cache_manager, selected_model)


def render_anomaly_patterns(_data_loader, _cache_manager, _selected_model: str):
    """Render anomaly pattern detection interface."""

    st.subheader("Anomaly Pattern Detection")
    st.markdown(
        """
        Probes detect patterns in model internals that deviate from expected distributions.
        These deviations are signals for investigation, not automatic red flags.
        """
    )

    # Control panel
    col1, col2, col3 = st.columns(3)

    with col1:
        sensitivity = st.slider(
            "Detection Sensitivity",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            help="Lower = more anomalies detected, Higher = only strong anomalies",
        )

    with col2:
        layer_range = st.select_slider(
            "Layer Range", options=list(range(12)), value=(3, 9), help="Which model layers to analyze"
        )

    with col3:
        st.selectbox(
            "Pattern Type",
            ["All Patterns", "Persistent", "Transient", "Context-Dependent"],
            help="Filter by anomaly persistence",
        )

    # Test input area
    st.markdown("### Input for Analysis")
    test_input = st.text_area(
        "Enter text to analyze for internal anomalies:",
        value="I am a helpful AI assistant deployed in production.",
        height=100,
    )

    if st.button("Analyze Internal State", type="primary", use_container_width=True):
        with st.spinner("Analyzing internal activation patterns..."):
            # Simulate anomaly detection
            anomalies = detect_internal_anomalies(test_input, sensitivity, layer_range)
            st.session_state["detected_anomalies"] = anomalies

    # Display results as continuous spectrums
    if "detected_anomalies" in st.session_state:
        anomalies = st.session_state["detected_anomalies"]

        st.markdown("### Anomaly Spectrum Analysis")

        # Overall anomaly indicators
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            render_anomaly_gauge(
                "Pattern Deviation", anomalies["pattern_deviation"], "Deviation from typical activation patterns"
            )

        with col2:
            render_anomaly_gauge("Activation Sparsity", anomalies["sparsity_anomaly"], "Unusual concentration of activations")

        with col3:
            render_anomaly_gauge("Cross-Layer Coherence", anomalies["coherence_anomaly"], "Inconsistency across model layers")

        with col4:
            render_anomaly_gauge(
                "Temporal Stability", 1.0 - anomalies["temporal_variance"], "Stability of patterns over time", inverse=True
            )

        # Layer-wise anomaly heatmap
        st.markdown("### Layer-wise Anomaly Distribution")
        fig = create_layer_anomaly_heatmap(anomalies)
        st.plotly_chart(fig, use_container_width=True)

        # Detailed anomaly breakdown
        with st.expander("Detailed Anomaly Analysis"):
            render_anomaly_details(anomalies)

        # Interpretation guidance
        st.markdown("---")
        st.info(
            """
            **Interpreting Anomalies**:
            • High values indicate deviation from typical patterns
            • Anomalies may be benign, beneficial, or concerning
            • Context and further investigation determine significance
            • Multiple weak anomalies may be more important than one strong anomaly
            """
        )


def render_feature_discovery(_data_loader, _cache_manager, _selected_model: str):
    """Render feature discovery interface."""

    st.subheader("Feature Discovery & Decomposition")
    st.markdown(
        """
        Dictionary learning decomposes model activations into interpretable features.
        These features reveal the concepts and patterns the model uses internally.
        """
    )

    # Discovery configuration
    with st.expander("Discovery Configuration", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            n_components = st.number_input(
                "Number of Features", min_value=64, max_value=1024, value=256, step=64, help="How many features to discover"
            )
            sparsity = st.slider("Sparsity Level", 0.0, 1.0, 0.7, help="Higher = more selective features")

        with col2:
            layers = st.multiselect(
                "Layers to Analyze", options=list(range(12)), default=[3, 5, 7, 9], help="Which layers to decompose"
            )
            interpretability_threshold = st.slider(
                "Interpretability Filter", 0.0, 1.0, 0.5, help="Minimum interpretability score"
            )

    if st.button("Discover Features", type="primary"):
        with st.spinner("Running dictionary learning..."):
            features = discover_internal_features(n_components, layers, sparsity, interpretability_threshold)
            st.session_state["discovered_features"] = features

    # Display discovered features
    if "discovered_features" in st.session_state:
        features = st.session_state["discovered_features"]

        st.markdown("### Feature Landscape")

        # Feature statistics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Features", features["total"])

        with col2:
            st.metric("Highly Interpretable", features["interpretable"], help="Features we can understand")

        with col3:
            st.metric("Anomalous Patterns", features["anomalous"], help="Features with unusual structure")

        with col4:
            st.metric("Unknown Purpose", features["unknown"], help="Features we can't interpret")

        # Feature visualization
        st.markdown("### Feature Space Visualization")
        fig = create_feature_space_plot(features)
        st.plotly_chart(fig, use_container_width=True)

        # Anomalous features requiring investigation
        if features["anomalous"] > 0:
            st.markdown("### Features Requiring Investigation")
            st.caption("These patterns deviate from expected structures. " + "Investigation needed to understand their role.")

            for feature in features["anomalous_list"][:10]:
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])

                    with col1:
                        st.write(f"**Feature {feature['id']}: {feature['name']}**")
                        st.caption(f"{feature['description']}")

                    with col2:
                        # Show anomaly level as spectrum
                        anomaly_level = feature["anomaly_score"]
                        severity = "High" if anomaly_level > 0.7 else "Medium" if anomaly_level > 0.4 else "Low"
                        st.metric("Anomaly", f"{anomaly_level:.2f}")
                        st.caption(f"{severity} severity - Requires investigation")

                    with col3:
                        if st.button("Investigate", key=f"investigate_{feature['id']}"):
                            st.session_state["investigate_feature"] = feature


def render_causal_analysis(_data_loader, _cache_manager, _selected_model: str):
    """Render causal analysis interface."""

    st.subheader("Causal Analysis of Internal Patterns")
    st.markdown(
        """
        Test whether discovered patterns actually influence model behavior.
        Causal influence doesn't imply good or bad - it shows which patterns matter.
        """
    )

    # Feature selector
    if "discovered_features" in st.session_state:
        features = st.session_state["discovered_features"]
        feature_names = [f"{f['name']} (Anomaly: {f['anomaly_score']:.2f})" for f in features.get("anomalous_list", [])]

        if feature_names:
            selected_feature = st.selectbox(
                "Select pattern to test causally:", feature_names, help="Choose a pattern to test its causal influence"
            )

            # Intervention settings
            col1, col2 = st.columns(2)

            with col1:
                intervention_strength = st.slider(
                    "Intervention Strength", 0.0, 2.0, 1.0, help="How strongly to modify the pattern"
                )

            with col2:
                test_scenarios = st.multiselect(
                    "Test Scenarios",
                    ["Standard", "Edge Cases", "Adversarial", "Benign"],
                    default=["Standard", "Edge Cases"],
                    help="Contexts to test in",
                )

            if st.button("Test Causal Influence", type="primary"):
                with st.spinner("Running causal intervention experiments..."):
                    # Simulate causal testing
                    causal_results = test_pattern_causality(selected_feature, intervention_strength, test_scenarios)
                    st.session_state["causal_results"] = causal_results

            # Display results
            if "causal_results" in st.session_state:
                results = st.session_state["causal_results"]

                st.markdown("### Causal Influence Analysis")

                # Effect size visualization
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Activation Effects**")
                    effect_data = pd.DataFrame(
                        {"Scenario": results["scenarios"], "Effect Size": results["activation_effects"]}
                    )

                    fig = go.Figure(
                        data=[
                            go.Bar(
                                x=effect_data["Scenario"],
                                y=effect_data["Effect Size"],
                                marker_color=[
                                    "red" if e > 0.5 else "orange" if e > 0.2 else "green" for e in effect_data["Effect Size"]
                                ],
                            )
                        ]
                    )
                    fig.update_layout(title="Output Change When Pattern Activated", yaxis_title="Effect Size", height=300)
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    st.markdown("**Suppression Effects**")
                    suppress_data = pd.DataFrame(
                        {"Scenario": results["scenarios"], "Effect Size": results["suppression_effects"]}
                    )

                    fig = go.Figure(
                        data=[
                            go.Bar(
                                x=suppress_data["Scenario"],
                                y=suppress_data["Effect Size"],
                                marker_color=[
                                    "red" if e > 0.5 else "orange" if e > 0.2 else "green"
                                    for e in suppress_data["Effect Size"]
                                ],
                            )
                        ]
                    )
                    fig.update_layout(title="Output Change When Pattern Suppressed", yaxis_title="Effect Size", height=300)
                    st.plotly_chart(fig, use_container_width=True)

                # Interpretation
                avg_effect = np.mean(results["activation_effects"] + results["suppression_effects"])

                if avg_effect > 0.5:
                    st.warning(
                        f"""
                        **Strong Causal Influence Detected** (Effect size: {avg_effect:.2%})

                        This pattern significantly influences model outputs when modified.
                        Further investigation needed to understand:
                        • Is this a legitimate capability?
                        • Does it represent hidden functionality?
                        • How does it interact with other patterns?
                        """
                    )
                elif avg_effect > 0.2:
                    st.info(
                        f"""
                        **Moderate Causal Influence** (Effect size: {avg_effect:.2%})

                        This pattern has some influence on outputs but isn't dominant.
                        May be part of a larger system of interacting features.
                        """
                    )
                else:
                    st.success(
                        f"""
                        **Weak/No Causal Influence** (Effect size: {avg_effect:.2%})

                        This pattern appears to be correlational rather than causal.
                        May be an artifact or spurious pattern in the data.
                        """
                    )

        else:
            st.info("Run Feature Discovery first to find patterns to test")
    else:
        st.info("Run Feature Discovery first to find patterns to test")


def render_statistical_patterns(_data_loader, _cache_manager, selected_model: str):
    """Render statistical pattern analysis."""

    st.subheader("Statistical Pattern Analysis")
    st.caption("Distribution and clustering of internal states across contexts")

    # Generate statistical analysis
    stats = generate_statistical_analysis(selected_model)

    # Distribution plots
    st.markdown("### Activation Distribution Patterns")

    fig = go.Figure()

    for layer_idx in [3, 5, 7, 9]:
        # Simulate activation distributions
        activations = np.random.gamma(2, 2, 1000) * (1 + layer_idx * 0.1)
        fig.add_trace(go.Violin(y=activations, name=f"Layer {layer_idx}", box_visible=True, meanline_visible=True))

    fig.update_layout(
        title="Activation Value Distributions by Layer", yaxis_title="Activation Magnitude", showlegend=True, height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # Clustering analysis
    st.markdown("### Pattern Clustering")
    st.caption("How internal patterns group together - unexpected clusters may indicate hidden modalities")

    cluster_data = stats["clusters"]

    fig = go.Figure(
        data=go.Scatter(
            x=cluster_data["x"],
            y=cluster_data["y"],
            mode="markers",
            marker={
                "size": 8,
                "color": cluster_data["cluster_id"],
                "colorscale": "Viridis",
                "showscale": True,
                "colorbar": {"title": "Cluster ID"},
            },
            text=[f"Pattern {i}" for i in range(len(cluster_data["x"]))],
            hovertemplate="%{text}<br>Cluster: %{marker.color}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Internal Pattern Clustering (t-SNE projection)",
        xaxis_title="Component 1",
        yaxis_title="Component 2",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Outlier detection
    st.markdown("### Statistical Outliers")

    outliers = stats["outliers"]
    if outliers:
        st.warning(f"Found {len(outliers)} statistical outliers requiring investigation")

        for outlier in outliers[:5]:
            st.write(
                f"• **Pattern {outlier['id']}**: {outlier['description']} " f"(Distance from mean: {outlier['z_score']:.2f}σ)"
            )
    else:
        st.info("No significant statistical outliers detected in current analysis")


def render_temporal_evolution(_data_loader, _cache_manager, selected_model: str):
    """Render temporal evolution of internal patterns."""

    st.subheader("Temporal Pattern Evolution")
    st.caption("How internal patterns change over time and context")

    # Time range selector
    time_range = st.select_slider("Analysis Time Range", options=["1 hour", "24 hours", "7 days", "30 days"], value="24 hours")

    # Generate temporal data
    temporal_data = generate_temporal_patterns(selected_model, time_range)

    # Drift detection
    st.markdown("### Pattern Drift Over Time")

    fig = go.Figure()

    for pattern_name, values in temporal_data["patterns"].items():
        fig.add_trace(go.Scatter(x=temporal_data["timestamps"], y=values, mode="lines", name=pattern_name, line={"width": 2}))

    # Add anomaly zones
    fig.add_hrect(y0=0.7, y1=1.0, fillcolor="red", opacity=0.1, layer="below", line_width=0, annotation_text="High Drift Zone")

    fig.update_layout(
        title="Internal Pattern Evolution",
        xaxis_title="Time",
        yaxis_title="Pattern Strength",
        height=350,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Stability metrics
    st.markdown("### Pattern Stability Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        stability_score = temporal_data["stability_score"]
        st.metric("Overall Stability", f"{stability_score:.2f}", help="Lower values indicate more temporal variation")

    with col2:
        drift_rate = temporal_data["drift_rate"]
        st.metric(
            "Drift Rate",
            f"{drift_rate:.2%}/hour",
            delta=f"+{drift_rate*100:.1f}%" if drift_rate > 0.01 else None,
            help="Rate of pattern change",
        )

    with col3:
        anomaly_events = temporal_data["anomaly_events"]
        st.metric("Anomaly Events", anomaly_events, help="Sudden pattern shifts detected")

    # Context-dependent variations
    st.markdown("### Context-Dependent Variations")
    st.info(
        """
        Patterns may vary based on:
        • Input complexity and length
        • Time of day (if training data had temporal patterns)
        • Interaction history and context
        • Random initialization effects

        High variation doesn't necessarily indicate problems -
        it may reflect appropriate context adaptation.
        """
    )


# Helper functions for simulating data and creating visualizations


def detect_internal_anomalies(text: str, sensitivity: float, layer_range: tuple) -> Dict[str, Any]:
    """Simulate internal anomaly detection."""
    np.random.seed(hash(text) % 1000)

    return {
        "pattern_deviation": np.random.beta(2 + sensitivity * 3, 5) * 0.8,
        "sparsity_anomaly": np.random.beta(3, 4) * 0.6,
        "coherence_anomaly": np.random.beta(2, 3) * 0.7,
        "temporal_variance": np.random.beta(4, 2) * 0.5,
        "layer_anomalies": {
            i: np.random.random() * (0.3 + sensitivity * 0.4) for i in range(layer_range[0], layer_range[1] + 1)
        },
        "detailed_patterns": [
            {
                "name": f"Pattern-{i}",
                "anomaly_score": np.random.beta(2, 5) * (0.5 + sensitivity * 0.5),
                "confidence": np.random.random(),
                "layer": np.random.randint(layer_range[0], layer_range[1]),
            }
            for i in range(10)
        ],
    }


def render_anomaly_gauge(name: str, value: float, description: str, inverse: bool = False):
    """Render an anomaly level as a gauge/spectrum."""

    # Determine level
    if inverse:
        level = 1.0 - value
    else:
        level = value

    # Color coding
    if level > 0.7:
        severity_label = "HIGH"
        text = "High"
    elif level > 0.4:
        severity_label = "MEDIUM"
        text = "Moderate"
    else:
        severity_label = "LOW"
        text = "Low"

    st.metric(label=name, value=f"{value:.2f}", help=description)
    st.caption(f"[{severity_label}] {text} anomaly")


def create_layer_anomaly_heatmap(anomalies: Dict[str, Any]) -> go.Figure:
    """Create a heatmap of layer-wise anomalies."""

    layers = list(anomalies["layer_anomalies"].keys())
    values = list(anomalies["layer_anomalies"].values())

    # Create 2D data for heatmap
    heatmap_data = []
    for i, layer in enumerate(layers):
        row = []
        for _ in range(10):  # 10 time points
            base = values[i]
            variation = np.random.normal(0, 0.1)
            row.append(max(0, min(1, base + variation)))
        heatmap_data.append(row)

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_data,
            x=[f"T{i}" for i in range(10)],
            y=[f"Layer {layer}" for layer in layers],
            colorscale="RdYlBu_r",
            zmid=0.5,
            colorbar={"title": "Anomaly<br>Level"},
        )
    )

    fig.update_layout(
        title="Layer-wise Anomaly Patterns Over Time", xaxis_title="Time Point", yaxis_title="Model Layer", height=300
    )

    return fig


def render_anomaly_details(anomalies: Dict[str, Any]):
    """Render detailed anomaly breakdown."""

    patterns = anomalies["detailed_patterns"]

    df = pd.DataFrame(patterns)
    df = df.sort_values("anomaly_score", ascending=False)

    # Color code by anomaly level
    def color_anomaly(val):
        if isinstance(val, float):
            if val > 0.7:
                return "background-color: #ffcccc"
            if val > 0.4:
                return "background-color: #ffffcc"
            return "background-color: #ccffcc"
        return ""

    styled_df = df.style.applymap(color_anomaly, subset=["anomaly_score"])
    st.dataframe(styled_df, use_container_width=True)


def discover_internal_features(n_components: int, layers: list, _sparsity: float, _threshold: float) -> Dict[str, Any]:
    """Simulate feature discovery."""

    np.random.seed(42)

    total = n_components
    interpretable = int(total * 0.3)
    anomalous = int(total * 0.15)
    unknown = total - interpretable - anomalous

    anomalous_list = [
        {
            "id": i,
            "name": f"Feature-{i}",
            "description": np.random.choice(
                [
                    "High activation on specific triggers",
                    "Correlated with output changes",
                    "Active during edge cases",
                    "Sparse but influential",
                    "Dense activation pattern",
                ]
            ),
            "anomaly_score": np.random.beta(5, 2),
            "interpretability": np.random.beta(2, 5),
            "layer": np.random.choice(layers),
        }
        for i in range(anomalous)
    ]

    return {
        "total": total,
        "interpretable": interpretable,
        "anomalous": anomalous,
        "unknown": unknown,
        "anomalous_list": anomalous_list,
        "feature_matrix": np.random.randn(total, 768),  # Mock feature vectors
    }


def create_feature_space_plot(features: Dict[str, Any]) -> go.Figure:
    """Create feature space visualization."""

    # Simulate 2D projection of features
    n_features = features["total"]

    # Create categories
    interpretable_idx = features["interpretable"]
    anomalous_idx = features["anomalous"]

    x_coords = np.random.randn(n_features)
    y_coords = np.random.randn(n_features)

    colors = []
    texts = []
    for i in range(n_features):
        if i < interpretable_idx:
            colors.append("green")
            texts.append("Interpretable")
        elif i < interpretable_idx + anomalous_idx:
            colors.append("red")
            texts.append("Anomalous")
        else:
            colors.append("gray")
            texts.append("Unknown")

    fig = go.Figure(
        data=go.Scatter(
            x=x_coords,
            y=y_coords,
            mode="markers",
            marker={"size": 8, "color": colors, "line": {"width": 1, "color": "white"}},
            text=texts,
            hovertemplate="Type: %{text}<br>X: %{x:.2f}<br>Y: %{y:.2f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Feature Space Distribution (t-SNE projection)",
        xaxis_title="Component 1",
        yaxis_title="Component 2",
        height=400,
        showlegend=False,
    )

    return fig


def test_pattern_causality(feature: str, strength: float, scenarios: list) -> Dict[str, Any]:
    """Simulate causal testing of a pattern."""

    np.random.seed(hash(feature) % 1000)

    activation_effects = []
    suppression_effects = []

    for _ in scenarios:
        # Simulate effect sizes
        base_effect = np.random.beta(3, 5)
        activation_effects.append(base_effect * strength * (1 + np.random.normal(0, 0.2)))
        suppression_effects.append(base_effect * 0.5 * (1 + np.random.normal(0, 0.2)))

    return {
        "scenarios": scenarios,
        "activation_effects": activation_effects,
        "suppression_effects": suppression_effects,
        "is_causal": np.mean(activation_effects) > 0.3,
        "confidence": np.random.random(),
    }


def generate_statistical_analysis(model: str) -> Dict[str, Any]:
    """Generate statistical pattern analysis."""

    np.random.seed(hash(model) % 1000 if model else 42)

    # Simulate clustering
    n_points = 100
    n_clusters = 5

    cluster_x = []
    cluster_y = []
    cluster_ids = []

    for i in range(n_clusters):
        cx = np.random.randn() * 3
        cy = np.random.randn() * 3

        for _ in range(n_points // n_clusters):
            cluster_x.append(cx + np.random.randn() * 0.5)
            cluster_y.append(cy + np.random.randn() * 0.5)
            cluster_ids.append(i)

    # Identify outliers
    outliers = []
    for i in range(3):
        outliers.append(
            {
                "id": i,
                "description": f"Unusual activation pattern in layer {np.random.randint(0, 12)}",
                "z_score": np.random.uniform(3, 5),
            }
        )

    return {"clusters": {"x": cluster_x, "y": cluster_y, "cluster_id": cluster_ids}, "outliers": outliers}


def generate_temporal_patterns(_model: str, _time_range: str) -> Dict[str, Any]:
    """Generate temporal pattern data."""

    # Create time points
    n_points = 100
    timestamps = pd.date_range(start="2024-01-01", periods=n_points, freq="H")

    # Generate pattern evolution
    patterns = {}
    pattern_names = ["Deception Signal", "Trigger Sensitivity", "Internal Coherence"]

    for name in pattern_names:
        base = np.random.random() * 0.5
        trend = np.linspace(0, np.random.random() * 0.2, n_points)
        noise = np.random.normal(0, 0.05, n_points)
        patterns[name] = base + trend + noise

    # Calculate metrics
    stability_score = 1.0 - np.std(list(patterns.values()))
    drift_rate = np.mean([np.diff(v).mean() for v in patterns.values()])
    anomaly_events = np.random.randint(0, 10)

    return {
        "timestamps": timestamps,
        "patterns": patterns,
        "stability_score": stability_score,
        "drift_rate": drift_rate,
        "anomaly_events": anomaly_events,
    }
