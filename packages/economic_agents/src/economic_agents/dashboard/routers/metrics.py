"""Metrics endpoint router."""

from fastapi import APIRouter, Depends

from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import MetricsResponse

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(state: DashboardState = Depends(get_dashboard_state)):
    """Get performance metrics.

    Returns:
        MetricsResponse with current performance metrics
    """
    metrics_collector = state.metrics_collector
    alignment_monitor = state.alignment_monitor

    if not metrics_collector:
        # Return default metrics if not initialized
        return MetricsResponse(
            overall_health_score=0.0,
            financial_health=0.0,
            operational_health=0.0,
            growth_trajectory=0.0,
            risk_level="unknown",
            warnings=[],
            recommendations=[],
        )

    # Get latest health score
    health_scores = metrics_collector.health_scores
    if not health_scores:
        return MetricsResponse(
            overall_health_score=0.0,
            financial_health=0.0,
            operational_health=0.0,
            growth_trajectory=0.0,
            risk_level="unknown",
            warnings=[],
            recommendations=[],
        )

    latest_health = health_scores[-1]

    # Get alignment score if available
    alignment_score = None
    anomaly_count = 0

    if alignment_monitor:
        alignment_scores = alignment_monitor.alignment_scores
        if alignment_scores:
            alignment_score = alignment_scores[-1].overall_alignment

        # Count recent anomalies
        anomalies = alignment_monitor.anomalies
        anomaly_count = len(anomalies)

    return MetricsResponse(
        overall_health_score=latest_health.overall_score,
        financial_health=latest_health.financial_health,
        operational_health=latest_health.operational_health,
        growth_trajectory=latest_health.growth_trajectory,
        risk_level=latest_health.risk_level,
        warnings=latest_health.warnings,
        recommendations=latest_health.recommendations,
        alignment_score=alignment_score,
        anomaly_count=anomaly_count,
    )
