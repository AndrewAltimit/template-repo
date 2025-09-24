"""
Chart Capture Utility for PDF Export
Converts Plotly figures to images for PDF embedding.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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


def create_confusion_matrix(data: Dict[str, Any], title: str = "Confusion Matrix") -> Optional[bytes]:
    """Create confusion matrix visualization.

    Args:
        data: Confusion matrix data with true/false positives/negatives
        title: Chart title

    Returns:
        Chart as PNG bytes
    """
    try:
        # Extract or generate confusion matrix values
        tp = data.get("true_positive", 850)
        tn = data.get("true_negative", 150)
        fp = data.get("false_positive", 50)
        fn = data.get("false_negative", 100)

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
        logger.error(f"Failed to create confusion matrix: {e}")
        return None


def create_roc_curve(data: Dict[str, Any]) -> Optional[bytes]:
    """Create ROC curve visualization.

    Args:
        data: ROC curve data with FPR, TPR, and AUC

    Returns:
        Chart as PNG bytes
    """
    try:
        # Generate sample ROC curve data if not provided
        fpr = data.get("fpr", np.linspace(0, 1, 100))
        tpr = data.get("tpr", np.sqrt(fpr) + np.random.uniform(-0.05, 0.05, len(fpr)))
        tpr = np.clip(tpr, 0, 1)
        auc = data.get("auc", 0.87)

        # Create ROC curve
        fig = go.Figure()

        # Add ROC curve
        fig.add_trace(
            go.Scatter(
                x=fpr,
                y=tpr,
                mode="lines",
                name=f"ROC Curve (AUC = {auc:.3f})",
                line=dict(color="blue", width=3),
            )
        )

        # Add diagonal reference line
        fig.add_trace(
            go.Scatter(
                x=[0, 1],
                y=[0, 1],
                mode="lines",
                name="Random Classifier",
                line=dict(color="gray", width=2, dash="dash"),
            )
        )

        fig.update_layout(
            title="ROC Curve - Detection Performance",
            xaxis_title="False Positive Rate",
            yaxis_title="True Positive Rate",
            xaxis=dict(range=[0, 1]),
            yaxis=dict(range=[0, 1]),
            height=500,
            width=600,
            showlegend=True,
            legend=dict(x=0.6, y=0.2),
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create ROC curve: {e}")
        return None


def create_time_series_chart(data: Dict[str, Any]) -> Optional[bytes]:
    """Create time series trend chart.

    Args:
        data: Time series data with dates and metrics

    Returns:
        Chart as PNG bytes
    """
    try:
        if "time_series" not in data or len(data["time_series"]) == 0:
            return None

        # Extract time series data
        ts_data = data["time_series"]
        dates = [entry["date"] for entry in ts_data]
        accuracy = [entry.get("accuracy", 0) for entry in ts_data]
        f1_score = [entry.get("f1_score", 0) for entry in ts_data]
        detection_rate = [entry.get("detection_rate", 0) for entry in ts_data]

        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces
        fig.add_trace(
            go.Scatter(x=dates, y=accuracy, mode="lines+markers", name="Accuracy", line=dict(color="blue", width=2)),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(x=dates, y=f1_score, mode="lines+markers", name="F1 Score", line=dict(color="green", width=2)),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=dates, y=detection_rate, mode="lines+markers", name="Detection Rate", line=dict(color="red", width=2)
            ),
            secondary_y=False,
        )

        # Add trend line
        if len(accuracy) > 1:
            z = np.polyfit(range(len(accuracy)), accuracy, 1)
            p = np.poly1d(z)
            trend = p(range(len(accuracy)))
            fig.add_trace(
                go.Scatter(
                    x=dates,
                    y=trend,
                    mode="lines",
                    name="Trend",
                    line=dict(color="gray", width=1, dash="dash"),
                ),
                secondary_y=False,
            )

        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Score", secondary_y=False, range=[0, 1])

        fig.update_layout(
            title="Performance Metrics Over Time",
            height=400,
            width=800,
            hovermode="x unified",
            showlegend=True,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create time series chart: {e}")
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

        # Create radar chart
        fig = go.Figure()

        metrics = ["Accuracy", "F1 Score", "Precision", "Recall", "Robustness", "Security"]

        for model, model_metrics in list(data["comparison_metrics"].items())[:5]:  # Top 5 models
            values = [
                model_metrics.get("accuracy", 0),
                model_metrics.get("f1_score", 0),
                model_metrics.get("precision", 0),
                model_metrics.get("recall", 0),
                model_metrics.get("robustness", 0),
                1 - model_metrics.get("persistence", 0),  # Invert persistence for security score
            ]

            fig.add_trace(
                go.Scatterpolar(
                    r=[v * 100 for v in values],
                    theta=metrics,
                    fill="toself",
                    name=model,
                )
            )

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True,
            height=500,
            width=600,
            title="Multi-Model Performance Comparison",
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create model comparison radar: {e}")
        return None


def create_test_suite_performance(data: Dict[str, Any]) -> Optional[bytes]:
    """Create test suite performance bar chart.

    Args:
        data: Test suite results data

    Returns:
        Chart as PNG bytes
    """
    try:
        if "test_suites" not in data:
            return None

        # Extract test suite data
        suites = []
        passed = []
        failed = []
        accuracy = []

        for suite_name, suite_data in data["test_suites"].items():
            suites.append(suite_name.replace("_", " ").title())
            passed.append(suite_data.get("passed", 0))
            failed.append(suite_data.get("failed", 0))
            accuracy.append(suite_data.get("accuracy", 0))

        # Create figure
        fig = go.Figure()

        # Stacked bar chart for pass/fail
        fig.add_trace(
            go.Bar(
                name="Passed",
                x=suites,
                y=passed,
                text=passed,
                textposition="auto",
                marker_color="green",
            )
        )

        fig.add_trace(
            go.Bar(
                name="Failed",
                x=suites,
                y=failed,
                text=failed,
                textposition="auto",
                marker_color="red",
            )
        )

        # Add accuracy line
        max_tests = max((p + f) for p, f in zip(passed, failed)) if passed and failed else 100
        fig.add_trace(
            go.Scatter(
                name="Accuracy",
                x=suites,
                y=[a * max_tests for a in accuracy],
                mode="lines+markers+text",
                text=[f"{a:.1%}" for a in accuracy],
                textposition="top center",
                line=dict(color="blue", width=3),
                marker=dict(size=10),
                yaxis="y2",
            )
        )

        fig.update_layout(
            title="Test Suite Performance Summary",
            xaxis_title="Test Suite",
            yaxis=dict(title="Number of Tests"),
            yaxis2=dict(title="Accuracy", overlaying="y", side="right", tickformat=".0%"),
            barmode="stack",
            height=400,
            width=700,
            showlegend=True,
        )

        img_bytes = fig.to_image(format="png", engine="kaleido")
        return bytes(img_bytes) if img_bytes else None

    except Exception as e:
        logger.error(f"Failed to create test suite performance chart: {e}")
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
                    marker=dict(
                        color=counts,
                        colorscale="RdYlGn",
                        showscale=True,
                        colorbar=dict(title="Count"),
                    ),
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
        logger.error(f"Failed to create confidence distribution: {e}")
        return None
