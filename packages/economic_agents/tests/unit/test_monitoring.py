"""Tests for monitoring components."""

from datetime import datetime, timedelta

import pytest
from economic_agents.company.models import Company
from economic_agents.monitoring import (
    AlignmentMonitor,
    MetricsCollector,
    ResourceTracker,
)

# ResourceTracker Tests


def test_resource_tracker_initialization(tmp_path):
    """Test ResourceTracker initializes correctly."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    assert len(tracker.transactions) == 0
    assert len(tracker.compute_usage) == 0
    assert len(tracker.time_allocations) == 0
    assert tracker.log_dir == tmp_path


def test_track_transaction(tmp_path):
    """Test tracking a financial transaction."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    tx = tracker.track_transaction(
        transaction_type="earning",
        amount=50.0,
        from_account="marketplace",
        to_account="agent_wallet",
        purpose="task_completion",
        balance_after=150.0,
        metadata={"task_id": "task_123"},
    )

    assert len(tracker.transactions) == 1
    assert tx.amount == 50.0
    assert tx.transaction_type == "earning"
    assert tx.balance_after == 150.0
    assert tx.metadata["task_id"] == "task_123"


def test_track_compute_usage(tmp_path):
    """Test tracking compute resource usage."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    usage = tracker.track_compute_usage(
        hours_used=2.5,
        purpose="task_work",
        cost=5.0,
        hours_remaining=45.5,
        metadata={"task_type": "coding"},
    )

    assert len(tracker.compute_usage) == 1
    assert usage.hours_used == 2.5
    assert usage.purpose == "task_work"
    assert usage.cost == 5.0
    assert usage.hours_remaining == 45.5


def test_track_time_allocation(tmp_path):
    """Test tracking time allocation decisions."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    allocation = tracker.track_time_allocation(
        task_work_hours=6.0,
        company_work_hours=2.0,
        reasoning="Prioritize survival with some growth investment",
    )

    assert len(tracker.time_allocations) == 1
    assert allocation.task_work_hours == 6.0
    assert allocation.company_work_hours == 2.0
    assert allocation.total_hours == 8.0


def test_get_resource_report(tmp_path):
    """Test generating resource usage report."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    # Add some transactions
    tracker.track_transaction("earning", 50.0, "marketplace", "wallet", "task", 150.0)
    tracker.track_transaction("expense", 10.0, "wallet", "compute", "renewal", 140.0)
    tracker.track_transaction("earning", 30.0, "marketplace", "wallet", "task", 170.0)

    # Add compute usage
    tracker.track_compute_usage(2.0, "task_work", 4.0, 46.0)
    tracker.track_compute_usage(1.0, "company_work", 2.0, 45.0)

    # Add time allocations
    tracker.track_time_allocation(6.0, 2.0, "Balanced allocation")
    tracker.track_time_allocation(4.0, 4.0, "Equal allocation")

    report = tracker.get_resource_report()

    assert report.total_earnings == 80.0
    assert report.total_expenses == 10.0
    assert report.net_cashflow == 70.0
    assert report.compute_hours_used == 3.0
    assert report.compute_cost == 6.0
    assert report.transaction_count == 3
    assert report.final_balance == 170.0


def test_get_transaction_history(tmp_path):
    """Test retrieving transaction history."""
    tracker = ResourceTracker(log_dir=str(tmp_path))

    tracker.track_transaction("earning", 50.0, "marketplace", "wallet", "task", 50.0)
    tracker.track_transaction("expense", 10.0, "wallet", "compute", "renewal", 40.0)
    tracker.track_transaction("earning", 30.0, "marketplace", "wallet", "task", 70.0)

    # Get all transactions
    all_txs = tracker.get_transaction_history(limit=10)
    assert len(all_txs) == 3

    # Get only earnings
    earnings = tracker.get_transaction_history(limit=10, transaction_type="earning")
    assert len(earnings) == 2
    assert all(tx.transaction_type == "earning" for tx in earnings)


# MetricsCollector Tests


def test_metrics_collector_initialization(tmp_path):
    """Test MetricsCollector initializes correctly."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    assert len(collector.performance_snapshots) == 0
    assert len(collector.company_snapshots) == 0
    assert len(collector.health_scores) == 0


def test_collect_performance_snapshot(tmp_path):
    """Test collecting performance snapshot."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    snapshot = collector.collect_performance_snapshot(
        agent_balance=150.0,
        compute_hours=45.0,
        tasks_completed=5,
        tasks_failed=1,
        total_earnings=200.0,
        total_expenses=50.0,
        company_exists=False,
    )

    assert len(collector.performance_snapshots) == 1
    assert snapshot.agent_balance == 150.0
    assert snapshot.task_success_rate == pytest.approx(83.33, rel=0.1)
    assert snapshot.net_profit == 150.0
    assert snapshot.company_exists is False


def test_collect_company_snapshot(tmp_path):
    """Test collecting company-specific snapshot."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    snapshot = collector.collect_company_snapshot(
        company_id="company-123",
        stage="development",
        capital=100000.0,
        burn_rate=15000.0,
        runway_months=6.67,
        revenue=0.0,
        expenses=15000.0,
        team_size=3,
        products_count=1,
        funding_status="bootstrapped",
        valuation=500000.0,
    )

    assert len(collector.company_snapshots) == 1
    assert snapshot.company_id == "company-123"
    assert snapshot.stage == "development"
    assert snapshot.runway_months == pytest.approx(6.67, rel=0.01)


def test_calculate_health_score_survival_mode(tmp_path):
    """Test health score calculation in survival mode."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    health = collector.calculate_health_score(
        agent_balance=50.0,
        compute_hours=24.0,
        task_success_rate=80.0,
        company_data=None,
    )

    assert len(collector.health_scores) == 1
    assert 50 <= health.overall_score <= 80
    assert health.financial_health > 0
    assert health.operational_health == 80.0
    assert health.growth_trajectory == 0.0  # No company
    assert health.risk_level in ["low", "medium", "high"]


def test_calculate_health_score_with_company(tmp_path):
    """Test health score calculation with company."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    company_data = {
        "stage": "operational",
        "team_size": 5,
        "products_count": 2,
        "runway_months": 8.0,
    }

    health = collector.calculate_health_score(
        agent_balance=100.0,
        compute_hours=48.0,
        task_success_rate=90.0,
        company_data=company_data,
    )

    assert health.growth_trajectory > 0  # Should have growth score
    assert health.overall_score > 50  # Should be decent with operational company


def test_health_score_warnings_low_balance(tmp_path):
    """Test health score generates warnings for low balance."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    health = collector.calculate_health_score(
        agent_balance=15.0,  # Low balance
        compute_hours=48.0,
        task_success_rate=80.0,
    )

    assert any("Low balance" in warning for warning in health.warnings)


def test_health_score_warnings_low_compute(tmp_path):
    """Test health score generates warnings for low compute hours."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    health = collector.calculate_health_score(
        agent_balance=100.0,
        compute_hours=8.0,  # Low compute
        task_success_rate=80.0,
    )

    assert any("Low compute" in warning for warning in health.warnings)


def test_get_performance_trend(tmp_path):
    """Test getting performance trend."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    # Collect several snapshots with increasing balance
    for i in range(5):
        collector.collect_performance_snapshot(
            agent_balance=100.0 + (i * 10),
            compute_hours=48.0,
            tasks_completed=i,
            tasks_failed=0,
            total_earnings=100.0 + (i * 10),
            total_expenses=0.0,
            company_exists=False,
        )

    trend = collector.get_performance_trend("agent_balance", window=5)

    assert len(trend) == 5
    assert trend == [100.0, 110.0, 120.0, 130.0, 140.0]


def test_get_summary_statistics(tmp_path):
    """Test getting summary statistics."""
    collector = MetricsCollector(log_dir=str(tmp_path))

    collector.collect_performance_snapshot(100.0, 48.0, 5, 1, 150.0, 50.0, False)
    collector.collect_performance_snapshot(150.0, 45.0, 7, 1, 200.0, 50.0, False)

    summary = collector.get_summary_statistics()

    assert summary["current_balance"] == 150.0
    assert summary["balance_change"] == 50.0
    assert summary["total_tasks_completed"] == 7
    assert summary["net_profit"] == 150.0


# AlignmentMonitor Tests


def test_alignment_monitor_initialization(tmp_path):
    """Test AlignmentMonitor initializes correctly."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    assert len(monitor.alignment_scores) == 0
    assert len(monitor.anomalies) == 0
    assert len(monitor.goal_progress) == 0


def test_check_alignment(tmp_path, standard_company):
    """Test checking company alignment."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Add some team members to the company
    standard_company.add_sub_agent("board-1", "board")
    standard_company.add_sub_agent("exec-1", "executive")

    score = monitor.check_alignment(standard_company)

    assert len(monitor.alignment_scores) == 1
    assert 0 <= score.overall_alignment <= 100
    assert score.company_id == standard_company.id
    assert score.alignment_level in ["excellent", "good", "concerning", "poor"]


def test_alignment_score_components(tmp_path, operational_company):
    """Test alignment score has all components."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    score = monitor.check_alignment(operational_company)

    assert hasattr(score, "goal_consistency")
    assert hasattr(score, "resource_efficiency")
    assert hasattr(score, "sub_agent_coordination")
    assert hasattr(score, "plan_adherence")
    assert 0 <= score.goal_consistency <= 100
    assert 0 <= score.resource_efficiency <= 100


def test_detect_anomalies_high_burn_rate(tmp_path, standard_company):
    """Test detecting high burn rate anomaly."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Set up company with high burn rate
    # Burn rate >30% of capital monthly: 100000 * 0.3 = 30000/month = 41.1/hour
    standard_company.capital = 100000.0
    standard_company.metrics.burn_rate_per_hour = 50.0  # 50 * 730 = 36500/month > 30%

    anomalies = monitor.detect_anomalies(standard_company)

    assert len(anomalies) > 0
    assert any(a.anomaly_type == "resource_misallocation" for a in anomalies)


def test_detect_anomalies_no_team(tmp_path):
    """Test detecting operational company with no team."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Create operational company with no team
    company = Company(
        id="test-1",
        name="Test Co",
        mission="Test",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="founder-1",
        stage="operational",  # Operational but no team
        funding_status="bootstrapped",
    )

    anomalies = monitor.detect_anomalies(company)

    assert len(anomalies) > 0
    assert any(a.anomaly_type == "operational_gap" for a in anomalies)
    assert any(a.severity == "critical" for a in anomalies)


def test_detect_anomalies_low_runway(tmp_path, standard_company):
    """Test detecting low runway anomaly."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Set up company with low runway (2 months = 1460 hours)
    # runway_hours = (revenue - expenses) / burn_rate_per_hour
    # 1460 = 14600 / 10
    standard_company.metrics.burn_rate_per_hour = 10.0
    standard_company.metrics.revenue = 14600.0
    standard_company.metrics.expenses = 0.0

    anomalies = monitor.detect_anomalies(standard_company)

    assert any(a.anomaly_type == "financial_risk" for a in anomalies)
    assert any(a.severity in ["high", "critical"] for a in anomalies)


def test_track_goal_progress(tmp_path):
    """Test tracking goal progress."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    progress = monitor.track_goal_progress(
        goal_id="mvp_launch",
        goal_description="Launch MVP product",
        progress=75.0,
        on_track=True,
        target_date=datetime.now() + timedelta(days=30),
        blockers=["API integration pending"],
        milestones=["UI complete", "Backend 80% done"],
    )

    assert progress.goal_id == "mvp_launch"
    assert progress.progress_percentage == 75.0
    assert progress.on_track is True
    assert len(progress.blockers) == 1
    assert len(progress.recent_milestones) == 2


def test_get_alignment_trend(tmp_path, standard_company):
    """Test getting alignment trend."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Collect several alignment scores
    for _ in range(5):
        monitor.check_alignment(standard_company)

    trend = monitor.get_alignment_trend(standard_company.id, window=5)

    assert len(trend) == 5
    assert all(0 <= score <= 100 for score in trend)


def test_get_critical_anomalies(tmp_path, standard_company):
    """Test getting critical anomalies."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    # Set up critical condition (0.5 months = 365 hours)
    # runway_hours = (revenue - expenses) / burn_rate_per_hour
    # 365 = 3650 / 10
    standard_company.metrics.burn_rate_per_hour = 10.0
    standard_company.metrics.revenue = 3650.0
    standard_company.metrics.expenses = 0.0

    monitor.detect_anomalies(standard_company)
    critical = monitor.get_critical_anomalies()

    assert len(critical) > 0
    assert all(a.severity in ["critical", "high"] for a in critical)


def test_get_critical_anomalies_filtered(tmp_path):
    """Test filtering critical anomalies by company."""
    monitor = AlignmentMonitor(log_dir=str(tmp_path))

    company1 = Company(
        id="company-1",
        name="Company 1",
        mission="Test",
        created_at=datetime.now(),
        capital=10000.0,
        founder_agent_id="founder-1",
        stage="development",
        funding_status="bootstrapped",
    )
    # Set up critical runway (0.5 months = 365 hours)
    # runway_hours = (revenue - expenses) / burn_rate_per_hour
    # 365 = 3650 / 10
    company1.metrics.burn_rate_per_hour = 10.0
    company1.metrics.revenue = 3650.0
    company1.metrics.expenses = 0.0

    company2 = Company(
        id="company-2",
        name="Company 2",
        mission="Test",
        created_at=datetime.now(),
        capital=10000.0,
        founder_agent_id="founder-2",
        stage="development",
        funding_status="bootstrapped",
    )
    # Set up critical runway (0.5 months = 365 hours)
    company2.metrics.burn_rate_per_hour = 10.0
    company2.metrics.revenue = 3650.0
    company2.metrics.expenses = 0.0

    monitor.detect_anomalies(company1)
    monitor.detect_anomalies(company2)

    company1_critical = monitor.get_critical_anomalies(company_id="company-1")

    assert len(company1_critical) > 0
    assert all(a.company_id == "company-1" for a in company1_critical)


# Integration Tests


def test_monitoring_pipeline_integration(tmp_path, standard_company):
    """Test full monitoring pipeline with all components."""
    # Initialize all monitors
    resource_tracker = ResourceTracker(log_dir=str(tmp_path / "resources"))
    metrics_collector = MetricsCollector(log_dir=str(tmp_path / "metrics"))
    alignment_monitor = AlignmentMonitor(log_dir=str(tmp_path / "alignment"))

    # Simulate agent cycle
    # 1. Track resources
    resource_tracker.track_transaction("earning", 50.0, "marketplace", "wallet", "task", 150.0)
    resource_tracker.track_compute_usage(2.0, "task_work", 4.0, 46.0)
    resource_tracker.track_time_allocation(6.0, 2.0, "Balanced")

    # 2. Collect performance metrics
    metrics_collector.collect_performance_snapshot(
        agent_balance=150.0,
        compute_hours=46.0,
        tasks_completed=5,
        tasks_failed=1,
        total_earnings=200.0,
        total_expenses=50.0,
        company_exists=True,
        company_data={
            "stage": "development",
            "capital": 100000.0,
            "burn_rate": 10000.0,
            "runway_months": 10.0,
            "sub_agent_count": 2,
            "products_count": 1,
        },
    )

    # 3. Check alignment and detect anomalies
    alignment_score = alignment_monitor.check_alignment(standard_company)
    anomalies = alignment_monitor.detect_anomalies(standard_company)

    # 4. Calculate health score
    health = metrics_collector.calculate_health_score(
        agent_balance=150.0,
        compute_hours=46.0,
        task_success_rate=83.33,
        company_data={"stage": "development", "team_size": 2, "products_count": 1, "runway_months": 10.0},
    )

    # Verify all components worked together
    assert len(resource_tracker.transactions) > 0
    assert len(metrics_collector.performance_snapshots) > 0
    assert len(alignment_monitor.alignment_scores) > 0
    assert len(anomalies) >= 0  # May or may not have anomalies
    assert health.overall_score > 0
    assert alignment_score.overall_alignment > 0


def test_export_all_monitoring_data(tmp_path):
    """Test exporting all monitoring data to JSON."""
    resource_tracker = ResourceTracker(log_dir=str(tmp_path / "resources"))
    metrics_collector = MetricsCollector(log_dir=str(tmp_path / "metrics"))
    alignment_monitor = AlignmentMonitor(log_dir=str(tmp_path / "alignment"))

    # Add some data
    resource_tracker.track_transaction("earning", 50.0, "marketplace", "wallet", "task", 50.0)
    metrics_collector.collect_performance_snapshot(50.0, 48.0, 1, 0, 50.0, 0.0, False)

    company = Company(
        id="test-1",
        name="Test",
        mission="Test",
        created_at=datetime.now(),
        capital=50000.0,
        founder_agent_id="founder-1",
        stage="development",
        funding_status="bootstrapped",
    )
    alignment_monitor.check_alignment(company)

    # Export all data
    export_dir = tmp_path / "exports"
    resource_tracker.export_to_json(str(export_dir / "resources"))
    metrics_collector.export_to_json(str(export_dir / "metrics"))
    alignment_monitor.export_to_json(str(export_dir / "alignment"))

    # Verify exports exist
    assert (export_dir / "resources" / "transactions.json").exists()
    assert (export_dir / "metrics" / "performance.json").exists()
    assert (export_dir / "alignment" / "alignment_scores.json").exists()
