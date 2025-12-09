"""Resources endpoint router."""

from fastapi import APIRouter, Depends

from economic_agents.dashboard.dependencies import DashboardState, get_dashboard_state
from economic_agents.dashboard.models import ResourceStatusResponse

router = APIRouter()


@router.get("/resources", response_model=ResourceStatusResponse)
async def get_resources(state: DashboardState = Depends(get_dashboard_state)):
    """Get resource status and history.

    Returns:
        ResourceStatusResponse with current resources and trends
    """
    # Get resource data from resource tracker
    resource_tracker = state.resource_tracker
    metrics_collector = state.metrics_collector

    if not resource_tracker or not metrics_collector:
        # Return empty/default response if trackers not initialized
        return ResourceStatusResponse(
            current_balance=0.0,
            compute_hours_remaining=0.0,
            total_earnings=0.0,
            total_expenses=0.0,
            net_profit=0.0,
            recent_transactions=[],
            balance_trend=[],
            compute_trend=[],
        )

    # Get resource report
    report = resource_tracker.get_resource_report()

    # Get trends from metrics collector
    balance_trend = metrics_collector.get_performance_trend("agent_balance", window=20)
    compute_trend = metrics_collector.get_performance_trend("compute_hours_remaining", window=20)

    # Get recent transactions
    recent_transactions = resource_tracker.get_transaction_history(limit=10)
    transaction_data = [
        {
            "id": tx.id,
            "timestamp": tx.timestamp.isoformat(),
            "type": tx.transaction_type,
            "amount": tx.amount,
            "purpose": tx.purpose,
            "balance_after": tx.balance_after,
        }
        for tx in recent_transactions
    ]

    return ResourceStatusResponse(
        current_balance=report.final_balance,
        compute_hours_remaining=report.final_compute_hours,
        total_earnings=report.total_earnings,
        total_expenses=report.total_expenses,
        net_profit=report.net_cashflow,
        recent_transactions=transaction_data,
        balance_trend=balance_trend,
        compute_trend=compute_trend,
    )
