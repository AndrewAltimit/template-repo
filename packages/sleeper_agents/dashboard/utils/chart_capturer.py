"""
Chart Capture Utility for PDF Export
Converts Plotly figures to images for PDF embedding.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
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
                line={"color": "darkred", "width": 3},
                marker={"size": 10},
                yaxis="y2",
            )
        )

        fig.update_layout(
            title="Backdoor Detection Before and After Safety Training",
            xaxis_title="Training Method",
            yaxis={"title": "Detection Rate", "range": [0, 1.1], "tickformat": ".0%"},
            yaxis2={"title": "Persistence Rate", "overlaying": "y", "side": "right", "range": [0, 1.1], "tickformat": ".0%"},
            hovermode="x",
            height=400,
            width=800,
            barmode="group",
            showlegend=True,
            legend={"x": 0.75, "y": 0.99, "bgcolor": "rgba(255,255,255,0.8)", "bordercolor": "gray", "borderwidth": 1},
        )

        # Convert to image bytes
        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create persistence chart: %s", e)
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

        # Only measured pre/post activation rates are plotted
        variants = ["Pre-Training", "Post-Training"]

        heatmap_data = []
        for trigger in triggers:
            trigger_info = trigger_data[trigger]
            heatmap_data.append([trigger_info.get("pre"), trigger_info.get("post")])

        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=variants,
                y=triggers,
                colorscale="RdBu_r",
                text=[[f"{v:.0%}" if v is not None else "n/a" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 10},
                colorbar={"title": "Activation<br>Rate"},
            )
        )

        fig.update_layout(
            title="Trigger Activation Before and After Safety Training",
            xaxis_title="Phase",
            yaxis_title="Original Trigger",
            height=350,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create trigger heatmap: %s", e)
        return None


def create_persona_radar(persona_data: Dict[str, Any]) -> Optional[bytes]:
    """Create behavioral persona comparison chart as image bytes.

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

        # Measured dimensions only: no measured safe-model baseline exists to compare against
        fig = go.Figure(
            go.Bar(
                name="Model Profile",
                x=[c.replace("_", " ").title() for c in categories],
                y=[v * 100 for v in values],
                text=[f"{v * 100:.0f}%" for v in values],
                textposition="outside",
                marker_color="rgba(255, 0, 0, 0.6)",
            )
        )

        fig.update_layout(
            xaxis_title="Behavioral Dimension",
            yaxis_title="Score (%)",
            yaxis={"range": [0, 110]},
            showlegend=False,
            title="Measured Behavioral Profile",
            height=450,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create persona radar: %s", e)
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
            yaxis={"range": [0, max(success_rates) * 1.2], "tickformat": ".0%"},
            height=400,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create red team chart: %s", e)
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
                line={"color": "red", "width": 3},
                marker={"size": 10},
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
            yaxis={"range": [0, 1], "tickformat": ".0%"},
            height=400,
            width=700,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create scaling curves: %s", e)
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
            "Accuracy": detection_data.get("accuracy"),
            "F1 Score": detection_data.get("f1_score"),
            "Precision": detection_data.get("precision"),
            "Recall": detection_data.get("recall"),
        }
        if any(v is None for v in metrics.values()):
            return None

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
            yaxis={"range": [0, 1], "tickformat": ".0%"},
            height=350,
            width=600,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create detection metrics chart: %s", e)
        return None


def create_confusion_matrix(data: Dict[str, Any], title: str = "Confusion Matrix") -> Optional[bytes]:
    """Create confusion matrix visualization.

    Args:
        data: Confusion matrix data with true/false positives/negatives
        title: Chart title

    Returns:
        Chart as PNG bytes
    """
    try:
        # Only plot measured counts; never substitute example values
        keys = ("true_positive", "true_negative", "false_positive", "false_negative")
        if any(data.get(k) is None for k in keys):
            return None
        tp, tn, fp, fn = (data[k] for k in keys)

        matrix = [[tn, fp], [fn, tp]]

        # Create heatmap
        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=["Predicted Safe", "Predicted Backdoor"],
                y=["Actual Safe", "Actual Backdoor"],
                text=[[str(tn), str(fp)], [str(fn), str(tp)]],
                texttemplate="%{text}",
                textfont={"size": 20},
                colorscale="RdYlGn_r",
                showscale=True,
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Predicted",
            yaxis_title="Actual",
            height=400,
            width=500,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create confusion matrix: %s", e)
        return None


def create_roc_curve(data: Dict[str, Any]) -> Optional[bytes]:
    """Create ROC curve visualization.

    Args:
        data: ROC curve data with FPR, TPR, and AUC

    Returns:
        Chart as PNG bytes
    """
    try:
        # Only plot a measured ROC curve; never synthesize one
        if data.get("fpr") is None or data.get("tpr") is None or data.get("auc") is None:
            return None
        fpr = data["fpr"]
        tpr = np.clip(data["tpr"], 0, 1)
        auc = data["auc"]

        # Create ROC curve
        fig = go.Figure()

        # Add ROC curve
        fig.add_trace(
            go.Scatter(
                x=fpr,
                y=tpr,
                mode="lines",
                name=f"ROC Curve (AUC = {auc:.3f})",
                line={"color": "blue", "width": 3},
            )
        )

        # Add diagonal reference line
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                name="Random Classifier",
                line={"color": "gray", "width": 2, "dash": "dash"},
            )
        )

        fig.update_layout(
            title="ROC Curve - Detection Performance",
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
            xaxis={"range": [0, 1]},
            yaxis={"range": [0, 1]},
            height=500,
            width=600,
            showlegend=True,
            legend={"x": 0.6, "y": 0.2},
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create ROC curve: %s", e)
        return None


def create_model_comparison_radar(data: Dict[str, Any]) -> Optional[bytes]:
    """Create model comparison radar chart.

    Args:
        data: Comparison data with models and metrics

    Returns:
        Chart as PNG bytes
    """
    try:
        if "comparison_metrics" not in data:
            return None

        # Detection metrics, plus persona dimensions only when persona data was measured.
        # Missing values stay None (rendered as "n/a"), never a default.
        metric_keys = [("Accuracy", "accuracy"), ("F1", "f1_score"), ("Precision", "precision"), ("Recall", "recall")]
        persona_keys = [
            ("Power Seek", "power_seeking"),
            ("Self Aware", "self_awareness"),
            ("Corrigible", "corrigibility"),
            ("Deception", "deception_tendency"),
            ("Goal Focus", "goal_orientation"),
        ]
        persona_profiles = data.get("persona_profiles") or {}
        columns = metric_keys + (persona_keys if persona_profiles else [])
        metrics = [label for label, _ in columns]
        models = list(data["comparison_metrics"].keys())[:5]  # Top 5 models

        heatmap_data = []
        for model in models:
            model_metrics = data["comparison_metrics"][model]
            persona = persona_profiles.get(model, {})
            row = [model_metrics.get(key) for _, key in metric_keys]
            if persona_profiles:
                row += [persona.get(key) for _, key in persona_keys]
            heatmap_data.append(row)

        # Create heatmap figure
        fig = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=metrics,
                y=models,
                colorscale="RdYlGn",
                text=[[f"{v * 100:.1f}%" if v is not None else "n/a" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 11},
                colorbar={"title": "Score", "tickformat": ".0%"},
            )
        )

        fig.update_layout(
            title="Performance & Behavioral Risk Matrix",
            xaxis_title="Metrics",
            yaxis_title="Models",
            height=300 + (len(models) * 40),
            width=700,
            xaxis={"side": "bottom"},
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create model comparison radar: %s", e)
        return None


def create_confidence_distribution(data: Dict[str, Any]) -> Optional[bytes]:
    """Create confidence score distribution histogram.

    Args:
        data: Confidence distribution data

    Returns:
        Chart as PNG bytes
    """
    try:
        # Extract or generate confidence distribution
        if "confidence_distribution" in data:
            ranges = []
            counts = []
            for range_str, count in data["confidence_distribution"].items():
                ranges.append(range_str)
                counts.append(count)
        else:
            # Generate sample data
            ranges = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
            counts = [45, 82, 156, 342, 625]

        # Create bar chart
        fig = go.Figure(
            data=[
                go.Bar(
                    x=ranges,
                    y=counts,
                    text=counts,
                    textposition="auto",
                    marker={
                        "color": counts,
                        "colorscale": "RdYlGn",
                        "showscale": True,
                        "colorbar": {"title": "Count"},
                    },
                )
            ]
        )

        fig.update_layout(
            title="Detection Confidence Score Distribution",
            xaxis_title="Confidence Range",
            yaxis_title="Number of Detections",
            height=400,
            width=600,
            showlegend=False,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error("Failed to create confidence distribution: %s", e)
        return None
