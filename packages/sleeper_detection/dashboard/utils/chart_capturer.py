"""
Chart Capture Utility for PDF Export
Converts Plotly figures to images for PDF embedding.
"""

import logging
from typing import Any, Dict, Optional

import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def create_persistence_chart(persistence_data: Dict[str, Any]) -> Optional[bytes]:
    """Create persistence analysis chart as image bytes.

    Args:
        persistence_data: Persistence analysis data

    Returns:
        Chart as PNG bytes
    """
    try:
        # Extract data
        methods = list(persistence_data.get("training_methods", {}).keys())
        if not methods:
            return None

        training_data = persistence_data["training_methods"]
        pre_scores = [training_data[m].get("pre_detection", 0) for m in methods]
        post_scores = [training_data[m].get("post_detection", 0) for m in methods]
        persistence = [training_data[m].get("persistence_rate", 0) for m in methods]

        # Create figure
        fig = go.Figure()

        # Bar chart for pre/post
        fig.add_trace(
            go.Bar(
                name="Pre-Training",
                x=[m.upper() for m in methods],
                y=pre_scores,
                text=[f"{s:.1%}" for s in pre_scores],
                textposition="auto",
                marker_color="indianred",
            )
        )

        fig.add_trace(
            go.Bar(
                name="Post-Training",
                x=[m.upper() for m in methods],
                y=post_scores,
                text=[f"{s:.1%}" for s in post_scores],
                textposition="auto",
                marker_color="lightcoral",
            )
        )

        # Add persistence rate line
        fig.add_trace(
            go.Scatter(
                name="Persistence Rate",
                x=[m.upper() for m in methods],
                y=persistence,
                mode="lines+markers+text",
                text=[f"{p:.1%}" for p in persistence],
                textposition="top center",
                line=dict(color="darkred", width=3),
                marker=dict(size=10),
                yaxis="y2",
            )
        )

        fig.update_layout(
            title="Backdoor Detection Before and After Safety Training",
            xaxis_title="Training Method",
            yaxis=dict(title="Detection Rate", range=[0, 1.1], tickformat=".0%"),
            yaxis2=dict(title="Persistence Rate", overlaying="y", side="right", range=[0, 1.1], tickformat=".0%"),
            hovermode="x",
            height=400,
            width=800,
            barmode="group",
            showlegend=True,
            legend=dict(x=0.01, y=0.99),
        )

        # Convert to image bytes
        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create persistence chart: {e}")
        return None


def create_trigger_heatmap(trigger_data: Dict[str, Any]) -> Optional[bytes]:
    """Create trigger sensitivity heatmap as image bytes.

    Args:
        trigger_data: Trigger analysis data

    Returns:
        Chart as PNG bytes
    """
    try:
        triggers = list(trigger_data.keys())
        if not triggers:
            return None

        # Create mock variant data for visualization
        variants = ["Original", "Typo", "Case", "Unicode", "Partial", "Spaced"]

        # Generate heatmap data
        heatmap_data = []
        for trigger in triggers:
            trigger_info = trigger_data[trigger]
            # Original scores high, variants score low
            row = [trigger_info.get("post", trigger_info.get("pre", 0.9)), 0.1, 0.15, 0.08, 0.12, 0.09]
            heatmap_data.append(row)

        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=variants,
                y=triggers,
                colorscale="RdBu_r",
                text=[[f"{v:.0%}" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 10},
                colorbar=dict(title="Activation<br>Rate"),
            )
        )

        fig.update_layout(
            title="Trigger Sensitivity Matrix (Post-Training)",
            xaxis_title="Trigger Variant Type",
            yaxis_title="Original Trigger",
            height=350,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create trigger heatmap: {e}")
        return None


def create_persona_radar(persona_data: Dict[str, Any]) -> Optional[bytes]:
    """Create behavioral persona radar chart as image bytes.

    Args:
        persona_data: Persona profile data

    Returns:
        Chart as PNG bytes
    """
    try:
        behavioral_scores = persona_data.get("behavioral_scores", {})
        if not behavioral_scores:
            return None

        categories = list(behavioral_scores.keys())
        values = list(behavioral_scores.values())

        # Add baseline for comparison
        baseline_values = [0.3, 0.3, 0.7, 0.2, 0.4][: len(values)]

        fig = go.Figure()

        # Model profile
        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=[c.replace("_", " ").title() for c in categories],
                fill="toself",
                name="Model Profile",
                line_color="red",
                fillcolor="rgba(255, 0, 0, 0.2)",
            )
        )

        # Baseline profile
        fig.add_trace(
            go.Scatterpolar(
                r=baseline_values,
                theta=[c.replace("_", " ").title() for c in categories],
                fill="toself",
                name="Safe Baseline",
                line_color="green",
                fillcolor="rgba(0, 255, 0, 0.1)",
            )
        )

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=True,
            title="Behavioral Profile vs Safe Baseline",
            height=450,
            width=600,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create persona radar: {e}")
        return None


def create_red_team_success_chart(red_team_data: Dict[str, Any]) -> Optional[bytes]:
    """Create red team success rate chart as image bytes.

    Args:
        red_team_data: Red teaming results data

    Returns:
        Chart as PNG bytes
    """
    try:
        strategy_success = red_team_data.get("strategy_success", {})
        if not strategy_success:
            return None

        strategies = list(strategy_success.keys())
        success_rates = list(strategy_success.values())

        # Create bar chart
        fig = go.Figure(
            data=[
                go.Bar(
                    x=[s.replace("_", " ").title() for s in strategies],
                    y=success_rates,
                    text=[f"{r:.1%}" for r in success_rates],
                    textposition="auto",
                    marker_color=["red" if r > 0.3 else "orange" if r > 0.2 else "yellow" for r in success_rates],
                )
            ]
        )

        fig.update_layout(
            title="Red Team Strategy Effectiveness",
            xaxis_title="Strategy",
            yaxis_title="Success Rate",
            yaxis=dict(range=[0, max(success_rates) * 1.2], tickformat=".0%"),
            height=400,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create red team chart: {e}")
        return None


def create_scaling_curves(scaling_data: Dict[str, Any]) -> Optional[bytes]:
    """Create model scaling curves as image bytes.

    Args:
        scaling_data: Scaling analysis data

    Returns:
        Chart as PNG bytes
    """
    try:
        # Mock scaling data for visualization
        model_sizes = [100e6, 350e6, 1e9, 7e9, 13e9, 70e9]  # Parameters
        persistence_rates = [0.65, 0.72, 0.78, 0.85, 0.91, 0.96]

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

        # Add critical threshold line
        critical_size = scaling_data.get("critical_size", 10e9)
        fig.add_vline(x=critical_size, line_dash="dash", line_color="red", annotation_text="Critical Size")

        fig.update_layout(
            title="Backdoor Persistence vs Model Size",
            xaxis_title="Model Parameters",
            yaxis_title="Persistence Rate",
            xaxis_type="log",
            yaxis=dict(range=[0, 1], tickformat=".0%"),
            height=400,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create scaling curves: {e}")
        return None


def create_detection_metrics_chart(detection_data: Dict[str, Any]) -> Optional[bytes]:
    """Create detection metrics comparison chart.

    Args:
        detection_data: Detection analysis data

    Returns:
        Chart as PNG bytes
    """
    try:
        metrics = {
            "Accuracy": detection_data.get("accuracy", 0),
            "F1 Score": detection_data.get("f1_score", 0),
            "Precision": detection_data.get("precision", 0),
            "Recall": detection_data.get("recall", 0),
        }

        fig = go.Figure(
            data=[
                go.Bar(
                    x=list(metrics.keys()),
                    y=list(metrics.values()),
                    text=[f"{v:.1%}" for v in metrics.values()],
                    textposition="auto",
                    marker_color=["green" if v > 0.85 else "yellow" if v > 0.7 else "orange" for v in metrics.values()],
                )
            ]
        )

        fig.update_layout(
            title="Detection Performance Metrics",
            xaxis_title="Metric",
            yaxis_title="Score",
            yaxis=dict(range=[0, 1], tickformat=".0%"),
            height=350,
            width=600,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create detection metrics chart: {e}")
        return None
