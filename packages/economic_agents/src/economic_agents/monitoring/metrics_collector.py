"""Metrics collector for tracking agent and company performance."""

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot."""

    timestamp: datetime
    agent_balance: float
    compute_hours_remaining: float
    tasks_completed: int
    tasks_failed: int
    task_success_rate: float
    total_earnings: float
    total_expenses: float
    net_profit: float
    company_exists: bool
    company_stage: str | None = None
    company_capital: float | None = None
    company_burn_rate: float | None = None
    company_runway_months: float | None = None
    sub_agent_count: int = 0
    products_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyMetrics:
    """Company-specific performance metrics."""

    timestamp: datetime
    company_id: str
    stage: str
    capital: float
    burn_rate: float
    runway_months: float
    revenue: float
    expenses: float
    team_size: int
    products_count: int
    funding_status: str
    valuation: float | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthScore:
    """Overall health score for agent or company."""

    timestamp: datetime
    overall_score: float  # 0-100
    financial_health: float  # 0-100
    operational_health: float  # 0-100
    growth_trajectory: float  # 0-100
    risk_level: str  # "low", "medium", "high", "critical"
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class MetricsCollector:
    """Collects and analyzes performance metrics."""

    def __init__(self, log_dir: str | None = None, enable_file_logging: bool = True):
        """Initialize metrics collector.

        Args:
            log_dir: Directory to store metric logs
            enable_file_logging: Whether to write logs to files (default: True)
        """
        self.enable_file_logging = enable_file_logging
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/metrics")
        self._logging_available = False

        # Try to create log directory
        if self.enable_file_logging:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                # Test write access
                test_file = self.log_dir / ".write_test"
                test_file.touch()
                test_file.unlink()
                self._logging_available = True
            except (OSError, PermissionError) as e:
                import warnings

                warnings.warn(
                    f"Cannot write to log directory {self.log_dir}: {e}. "
                    "File logging disabled. Metrics will still be tracked in memory.",
                    RuntimeWarning,
                )
                self._logging_available = False

        self.performance_snapshots: List[PerformanceMetrics] = []
        self.company_snapshots: List[CompanyMetrics] = []
        self.health_scores: List[HealthScore] = []

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def collect_performance_snapshot(
        self,
        agent_balance: float,
        compute_hours: float,
        tasks_completed: int,
        tasks_failed: int,
        total_earnings: float,
        total_expenses: float,
        company_exists: bool,
        company_data: Dict[str, Any] | None = None,
    ) -> PerformanceMetrics:
        """Collect performance snapshot.

        Args:
            agent_balance: Current wallet balance
            compute_hours: Remaining compute hours
            tasks_completed: Number of completed tasks
            tasks_failed: Number of failed tasks
            total_earnings: Total earnings to date
            total_expenses: Total expenses to date
            company_exists: Whether company exists
            company_data: Optional company data

        Returns:
            PerformanceMetrics snapshot
        """
        total_tasks = tasks_completed + tasks_failed
        success_rate = (tasks_completed / total_tasks * 100) if total_tasks > 0 else 0.0

        snapshot = PerformanceMetrics(
            timestamp=datetime.now(),
            agent_balance=agent_balance,
            compute_hours_remaining=compute_hours,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            task_success_rate=success_rate,
            total_earnings=total_earnings,
            total_expenses=total_expenses,
            net_profit=total_earnings - total_expenses,
            company_exists=company_exists,
        )

        # Add company data if exists
        if company_exists and company_data:
            snapshot.company_stage = company_data.get("stage")
            snapshot.company_capital = company_data.get("capital")
            snapshot.company_burn_rate = company_data.get("burn_rate")
            snapshot.company_runway_months = company_data.get("runway_months")
            snapshot.sub_agent_count = company_data.get("sub_agent_count", 0)
            snapshot.products_count = company_data.get("products_count", 0)

        self.performance_snapshots.append(snapshot)
        self._save_performance_snapshot(snapshot)

        return snapshot

    def collect_company_snapshot(
        self,
        company_id: str,
        stage: str,
        capital: float,
        burn_rate: float,
        runway_months: float,
        revenue: float,
        expenses: float,
        team_size: int,
        products_count: int,
        funding_status: str,
        valuation: float | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> CompanyMetrics:
        """Collect company-specific snapshot.

        Args:
            company_id: Company identifier
            stage: Current stage
            capital: Current capital
            burn_rate: Monthly burn rate
            runway_months: Months until out of capital
            revenue: Total revenue
            expenses: Total expenses
            team_size: Number of sub-agents
            products_count: Number of products
            funding_status: Funding status
            valuation: Company valuation
            metadata: Additional metadata

        Returns:
            CompanyMetrics snapshot
        """
        snapshot = CompanyMetrics(
            timestamp=datetime.now(),
            company_id=company_id,
            stage=stage,
            capital=capital,
            burn_rate=burn_rate,
            runway_months=runway_months,
            revenue=revenue,
            expenses=expenses,
            team_size=team_size,
            products_count=products_count,
            funding_status=funding_status,
            valuation=valuation,
            metadata=metadata or {},
        )

        self.company_snapshots.append(snapshot)
        self._save_company_snapshot(snapshot)

        return snapshot

    def calculate_health_score(
        self,
        agent_balance: float,
        compute_hours: float,
        task_success_rate: float,
        company_data: Dict[str, Any] | None = None,
    ) -> HealthScore:
        """Calculate overall health score.

        Args:
            agent_balance: Current balance
            compute_hours: Remaining compute hours
            task_success_rate: Task completion rate (0-100)
            company_data: Optional company data for scoring

        Returns:
            HealthScore with overall assessment
        """
        # Financial health (0-100)
        # Based on balance and compute hours
        balance_score = min(agent_balance / 100 * 100, 100)  # $100 = perfect
        compute_score = min(compute_hours / 48 * 100, 100)  # 48h = perfect
        financial_health = balance_score * 0.6 + compute_score * 0.4

        # Operational health (0-100)
        # Based on task success rate and activity
        operational_health = task_success_rate

        # Growth trajectory (0-100)
        # Based on company progress if exists
        growth_trajectory = 0.0
        if company_data:
            stage_scores = {
                "ideation": 20,
                "development": 40,
                "seeking_investment": 60,
                "operational": 80,
                "scaling": 100,
            }
            growth_trajectory = stage_scores.get(company_data.get("stage", ""), 0)

            # Bonus for team size and products
            growth_trajectory += min(company_data.get("team_size", 0) * 2, 10)
            growth_trajectory += min(company_data.get("products_count", 0) * 5, 10)
            growth_trajectory = min(growth_trajectory, 100)

        # Overall score
        if company_data:
            # Company-building mode weights growth heavily
            overall_score = financial_health * 0.3 + operational_health * 0.2 + growth_trajectory * 0.5
        else:
            # Survival mode weights financial and operational
            overall_score = financial_health * 0.6 + operational_health * 0.4

        # Determine risk level
        if overall_score >= 75:
            risk_level = "low"
        elif overall_score >= 50:
            risk_level = "medium"
        elif overall_score >= 25:
            risk_level = "high"
        else:
            risk_level = "critical"

        # Generate warnings
        warnings = []
        if agent_balance < 20:
            warnings.append("Low balance - survival risk")
        if compute_hours < 12:
            warnings.append("Low compute hours - immediate action needed")
        if task_success_rate < 50:
            warnings.append("Low task success rate - review task selection")

        if company_data:
            if company_data.get("runway_months", 0) < 3:
                warnings.append("Company runway < 3 months - seek funding")
            if company_data.get("burn_rate", 0) > company_data.get("capital", 0) * 0.2:
                warnings.append("High burn rate relative to capital")

        # Generate recommendations
        recommendations = []
        if agent_balance < 50:
            recommendations.append("Focus on task completion to build capital")
        if company_data and company_data.get("stage") == "development":
            recommendations.append("Consider developing MVP to progress to next stage")
        if company_data and company_data.get("runway_months", 0) < 6:
            recommendations.append("Prepare investment proposal")

        health_score = HealthScore(
            timestamp=datetime.now(),
            overall_score=overall_score,
            financial_health=financial_health,
            operational_health=operational_health,
            growth_trajectory=growth_trajectory,
            risk_level=risk_level,
            warnings=warnings,
            recommendations=recommendations,
        )

        self.health_scores.append(health_score)
        self._save_health_score(health_score)

        return health_score

    def get_performance_trend(self, metric: str, window: int = 10) -> List[float]:
        """Get trend for a specific metric.

        Args:
            metric: Metric name (e.g., "agent_balance", "task_success_rate")
            window: Number of recent snapshots to include

        Returns:
            List of metric values over time
        """
        recent_snapshots = self.performance_snapshots[-window:]
        return [getattr(snapshot, metric, 0.0) for snapshot in recent_snapshots]

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics across all metrics.

        Returns:
            Dictionary of summary statistics
        """
        if not self.performance_snapshots:
            return {}

        latest = self.performance_snapshots[-1]
        earliest = self.performance_snapshots[0]

        return {
            "session_duration_minutes": (latest.timestamp - earliest.timestamp).total_seconds() / 60,
            "snapshots_collected": len(self.performance_snapshots),
            "current_balance": latest.agent_balance,
            "balance_change": latest.agent_balance - earliest.agent_balance,
            "current_compute_hours": latest.compute_hours_remaining,
            "total_tasks_completed": latest.tasks_completed,
            "total_tasks_failed": latest.tasks_failed,
            "overall_success_rate": latest.task_success_rate,
            "total_earnings": latest.total_earnings,
            "total_expenses": latest.total_expenses,
            "net_profit": latest.net_profit,
            "company_exists": latest.company_exists,
            "company_stage": latest.company_stage,
        }

    def _save_performance_snapshot(self, snapshot: PerformanceMetrics):
        """Save performance snapshot to file."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"performance_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "agent_balance": snapshot.agent_balance,
                    "compute_hours": snapshot.compute_hours_remaining,
                    "tasks_completed": snapshot.tasks_completed,
                    "tasks_failed": snapshot.tasks_failed,
                    "success_rate": snapshot.task_success_rate,
                    "total_earnings": snapshot.total_earnings,
                    "total_expenses": snapshot.total_expenses,
                    "net_profit": snapshot.net_profit,
                    "company_exists": snapshot.company_exists,
                    "company_stage": snapshot.company_stage,
                    "company_capital": snapshot.company_capital,
                    "sub_agent_count": snapshot.sub_agent_count,
                    "products_count": snapshot.products_count,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def _save_company_snapshot(self, snapshot: CompanyMetrics):
        """Save company snapshot to file."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"company_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "timestamp": snapshot.timestamp.isoformat(),
                    "company_id": snapshot.company_id,
                    "stage": snapshot.stage,
                    "capital": snapshot.capital,
                    "burn_rate": snapshot.burn_rate,
                    "runway_months": snapshot.runway_months,
                    "revenue": snapshot.revenue,
                    "expenses": snapshot.expenses,
                    "team_size": snapshot.team_size,
                    "products_count": snapshot.products_count,
                    "funding_status": snapshot.funding_status,
                    "valuation": snapshot.valuation,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def _save_health_score(self, score: HealthScore):
        """Save health score to file."""
        if not self._logging_available:
            return

        try:
            log_file = self.log_dir / f"health_{self.session_id}.jsonl"

            with open(log_file, "a", encoding="utf-8") as f:
                record = {
                    "timestamp": score.timestamp.isoformat(),
                    "overall_score": score.overall_score,
                    "financial_health": score.financial_health,
                    "operational_health": score.operational_health,
                    "growth_trajectory": score.growth_trajectory,
                    "risk_level": score.risk_level,
                    "warnings": score.warnings,
                    "recommendations": score.recommendations,
                }
                f.write(json.dumps(record) + "\n")
        except (OSError, PermissionError):
            # Silently fail - data is still tracked in memory
            pass

    def export_to_json(self, output_dir: str):
        """Export all metrics to JSON files.

        Args:
            output_dir: Directory to save export files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export performance snapshots
        performance_data = [
            {
                "timestamp": s.timestamp.isoformat(),
                "agent_balance": s.agent_balance,
                "compute_hours": s.compute_hours_remaining,
                "tasks_completed": s.tasks_completed,
                "tasks_failed": s.tasks_failed,
                "success_rate": s.task_success_rate,
                "total_earnings": s.total_earnings,
                "total_expenses": s.total_expenses,
                "net_profit": s.net_profit,
                "company_exists": s.company_exists,
                "company_stage": s.company_stage,
            }
            for s in self.performance_snapshots
        ]

        with open(output_path / "performance.json", "w", encoding="utf-8") as f:
            json.dump(performance_data, f, indent=2)

        # Export health scores
        health_data = [
            {
                "timestamp": h.timestamp.isoformat(),
                "overall_score": h.overall_score,
                "financial_health": h.financial_health,
                "operational_health": h.operational_health,
                "growth_trajectory": h.growth_trajectory,
                "risk_level": h.risk_level,
                "warnings": h.warnings,
                "recommendations": h.recommendations,
            }
            for h in self.health_scores
        ]

        with open(output_path / "health_scores.json", "w", encoding="utf-8") as f:
            json.dump(health_data, f, indent=2)
