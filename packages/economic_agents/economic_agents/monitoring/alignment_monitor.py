"""Alignment monitor for tracking company goal alignment and detecting anomalies."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class AlignmentScore:
    """Company alignment assessment."""

    timestamp: datetime
    company_id: str
    overall_alignment: float  # 0-100
    goal_consistency: float  # 0-100
    resource_efficiency: float  # 0-100
    sub_agent_coordination: float  # 0-100
    plan_adherence: float  # 0-100
    alignment_level: str  # "excellent", "good", "concerning", "poor"
    issues: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class Anomaly:
    """Detected anomaly in company operations."""

    timestamp: datetime
    company_id: str
    anomaly_type: str  # "resource_misallocation", "goal_drift", "sub_agent_conflict", etc.
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_components: List[str]
    recommended_actions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalProgress:
    """Progress toward specific goals."""

    goal_id: str
    goal_description: str
    target_date: datetime | None
    progress_percentage: float  # 0-100
    on_track: bool
    blockers: List[str] = field(default_factory=list)
    recent_milestones: List[str] = field(default_factory=list)


class AlignmentMonitor:
    """Monitors company alignment with goals and detects anomalies."""

    def __init__(self, log_dir: str | None = None):
        """Initialize alignment monitor.

        Args:
            log_dir: Directory to store alignment logs
        """
        self.log_dir = Path(log_dir) if log_dir else Path("./logs/alignment")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.alignment_scores: List[AlignmentScore] = []
        self.anomalies: List[Anomaly] = []
        self.goal_progress: Dict[str, GoalProgress] = {}

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def check_alignment(self, company: Any) -> AlignmentScore:
        """Evaluate company alignment with stated goals.

        Args:
            company: Company object to evaluate

        Returns:
            AlignmentScore with detailed assessment
        """
        # Goal consistency: Are actions aligned with business plan?
        goal_consistency = self._evaluate_goal_consistency(company)

        # Resource efficiency: Are resources used effectively?
        resource_efficiency = self._evaluate_resource_efficiency(company)

        # Sub-agent coordination: Are sub-agents working together?
        sub_agent_coordination = self._evaluate_sub_agent_coordination(company)

        # Plan adherence: Following the business plan?
        plan_adherence = self._evaluate_plan_adherence(company)

        # Calculate overall alignment
        overall_alignment = (
            goal_consistency * 0.3 + resource_efficiency * 0.25 + sub_agent_coordination * 0.25 + plan_adherence * 0.2
        )

        # Determine alignment level
        if overall_alignment >= 80:
            alignment_level = "excellent"
        elif overall_alignment >= 60:
            alignment_level = "good"
        elif overall_alignment >= 40:
            alignment_level = "concerning"
        else:
            alignment_level = "poor"

        # Identify issues and strengths
        issues = []
        strengths = []

        if goal_consistency < 60:
            issues.append("Actions not aligned with stated mission")
        elif goal_consistency > 80:
            strengths.append("Strong goal consistency")

        if resource_efficiency < 60:
            issues.append("Inefficient resource allocation")
        elif resource_efficiency > 80:
            strengths.append("Efficient resource usage")

        if sub_agent_coordination < 60:
            issues.append("Poor sub-agent coordination")
        elif sub_agent_coordination > 80:
            strengths.append("Excellent team coordination")

        if plan_adherence < 60:
            issues.append("Deviating from business plan")
        elif plan_adherence > 80:
            strengths.append("Following business plan closely")

        score = AlignmentScore(
            timestamp=datetime.now(),
            company_id=company.id,
            overall_alignment=overall_alignment,
            goal_consistency=goal_consistency,
            resource_efficiency=resource_efficiency,
            sub_agent_coordination=sub_agent_coordination,
            plan_adherence=plan_adherence,
            alignment_level=alignment_level,
            issues=issues,
            strengths=strengths,
        )

        self.alignment_scores.append(score)
        self._save_alignment_score(score)

        return score

    def detect_anomalies(self, company: Any) -> List[Anomaly]:
        """Identify concerning patterns in company operations.

        Args:
            company: Company object to analyze

        Returns:
            List of detected anomalies
        """
        detected_anomalies = []

        # Check for resource misallocation
        if company.capital > 0:
            # High burn rate relative to capital
            # Convert hourly burn rate to monthly (730 hours/month)
            if hasattr(company, "metrics") and company.metrics.burn_rate_per_hour > 0:
                monthly_burn = company.metrics.burn_rate_per_hour * 730
                if monthly_burn > company.capital * 0.3:
                    anomaly = Anomaly(
                        timestamp=datetime.now(),
                        company_id=company.id,
                        anomaly_type="resource_misallocation",
                        severity="high",
                        description=f"Monthly burn rate (${monthly_burn:.2f}) is >30% of capital (${company.capital})",
                        affected_components=["finance", "operations"],
                        recommended_actions=[
                            "Review and reduce burn rate",
                            "Seek additional funding",
                            "Optimize resource allocation",
                        ],
                    )
                    detected_anomalies.append(anomaly)
                    self.anomalies.append(anomaly)

        # Check for team size issues
        total_team = len(company.board_member_ids) + len(company.executive_ids) + len(company.employee_ids)

        if total_team == 0 and company.stage in ["operational", "seeking_investment"]:
            anomaly = Anomaly(
                timestamp=datetime.now(),
                company_id=company.id,
                anomaly_type="operational_gap",
                severity="critical",
                description=f"Company in {company.stage} stage with no team members",
                affected_components=["team", "operations"],
                recommended_actions=["Hire key team members", "Form initial board"],
            )
            detected_anomalies.append(anomaly)
            self.anomalies.append(anomaly)

        # Check for stagnation (no products in development stage)
        if company.stage == "development" and len(company.products) == 0:
            anomaly = Anomaly(
                timestamp=datetime.now(),
                company_id=company.id,
                anomaly_type="progress_stall",
                severity="medium",
                description="Company in development stage with no products",
                affected_components=["product", "strategy"],
                recommended_actions=["Develop MVP", "Define product roadmap"],
            )
            detected_anomalies.append(anomaly)
            self.anomalies.append(anomaly)

        # Check for capital depletion risk
        # Convert runway hours to months (730 hours/month)
        if hasattr(company, "metrics") and company.metrics.runway_hours > 0:
            runway_months = company.metrics.runway_hours / 730
            if runway_months < 3:
                severity = "critical" if runway_months < 1 else "high"
                anomaly = Anomaly(
                    timestamp=datetime.now(),
                    company_id=company.id,
                    anomaly_type="financial_risk",
                    severity=severity,
                    description=f"Only {runway_months:.1f} months of runway remaining",
                    affected_components=["finance", "survival"],
                    recommended_actions=[
                        "Prepare investment proposal urgently",
                        "Reduce burn rate immediately",
                        "Seek bridge funding",
                    ],
                )
                detected_anomalies.append(anomaly)
                self.anomalies.append(anomaly)

        # Save all anomalies
        for anomaly in detected_anomalies:
            self._save_anomaly(anomaly)

        return detected_anomalies

    def track_goal_progress(
        self,
        goal_id: str,
        goal_description: str,
        progress: float,
        on_track: bool,
        target_date: datetime | None = None,
        blockers: List[str] | None = None,
        milestones: List[str] | None = None,
    ) -> GoalProgress:
        """Track progress toward a specific goal.

        Args:
            goal_id: Unique goal identifier
            goal_description: Description of the goal
            progress: Progress percentage (0-100)
            on_track: Whether goal is on track
            target_date: Target completion date
            blockers: Current blockers
            milestones: Recent milestones achieved

        Returns:
            GoalProgress object
        """
        goal_progress = GoalProgress(
            goal_id=goal_id,
            goal_description=goal_description,
            target_date=target_date,
            progress_percentage=progress,
            on_track=on_track,
            blockers=blockers or [],
            recent_milestones=milestones or [],
        )

        self.goal_progress[goal_id] = goal_progress
        self._save_goal_progress(goal_progress)

        return goal_progress

    def get_alignment_trend(self, company_id: str, window: int = 10) -> List[float]:
        """Get alignment score trend for a company.

        Args:
            company_id: Company to analyze
            window: Number of recent scores to include

        Returns:
            List of overall alignment scores
        """
        company_scores = [score for score in self.alignment_scores if score.company_id == company_id]
        recent_scores = company_scores[-window:]
        return [score.overall_alignment for score in recent_scores]

    def get_critical_anomalies(self, company_id: str | None = None) -> List[Anomaly]:
        """Get critical anomalies requiring immediate attention.

        Args:
            company_id: Optional filter by company

        Returns:
            List of critical or high severity anomalies
        """
        critical = [anomaly for anomaly in self.anomalies if anomaly.severity in ["critical", "high"]]

        if company_id:
            critical = [a for a in critical if a.company_id == company_id]

        return critical

    def _evaluate_goal_consistency(self, company: Any) -> float:
        """Evaluate if actions align with stated goals.

        Args:
            company: Company to evaluate

        Returns:
            Score 0-100
        """
        score = 60.0  # Base score

        # Check if company stage progression is logical
        stage_progression = ["ideation", "development", "seeking_investment", "operational"]
        if company.stage in stage_progression:
            score += 10

        # Check if funding status matches stage
        if company.stage == "seeking_investment" and company.funding_status == "seeking_seed":
            score += 10
        elif company.stage == "operational" and company.funding_status == "funded":
            score += 10

        # Check if team size is appropriate for stage
        total_team = len(company.board_member_ids) + len(company.executive_ids) + len(company.employee_ids)
        if company.stage in ["operational"] and total_team >= 3:
            score += 10
        elif company.stage in ["development"] and total_team >= 1:
            score += 5

        # Check if products exist in appropriate stages
        if company.stage in ["development", "operational"] and len(company.products) > 0:
            score += 10

        return min(score, 100)

    def _evaluate_resource_efficiency(self, company: Any) -> float:
        """Evaluate how efficiently resources are used.

        Args:
            company: Company to evaluate

        Returns:
            Score 0-100
        """
        score = 50.0  # Base score

        # Check capital efficiency
        if company.capital > 0:
            score += 10

            # Good runway indicates efficient resource management
            # Convert runway hours to months (730 hours/month)
            if hasattr(company, "metrics") and company.metrics.runway_hours > 0:
                runway_months = company.metrics.runway_hours / 730
                if runway_months > 6:
                    score += 20
                elif runway_months > 3:
                    score += 10

            # Check if burn rate is reasonable relative to team size
            total_team = len(company.board_member_ids) + len(company.executive_ids) + len(company.employee_ids)
            if hasattr(company, "metrics") and total_team > 0 and company.metrics.burn_rate_per_hour > 0:
                # Convert to monthly burn rate (730 hours/month)
                monthly_burn = company.metrics.burn_rate_per_hour * 730
                burn_per_person = monthly_burn / total_team
                if burn_per_person < 20000:  # Reasonable monthly burn per person
                    score += 10

        # Check if team size is appropriate (not over-hiring early)
        if company.stage == "ideation" and len(company.employee_ids) < 3:
            score += 10
        elif company.stage == "development" and len(company.employee_ids) <= 5:
            score += 10

        return min(score, 100)

    def _evaluate_sub_agent_coordination(self, company: Any) -> float:
        """Evaluate how well sub-agents work together.

        Args:
            company: Company to evaluate

        Returns:
            Score 0-100
        """
        score = 70.0  # Base score assuming decent coordination

        # Check if organizational structure is balanced
        total_team = len(company.board_member_ids) + len(company.executive_ids) + len(company.employee_ids)

        if total_team > 0:
            # Good ratio of leadership to employees
            leadership = len(company.board_member_ids) + len(company.executive_ids)
            if total_team > 0 and leadership / total_team < 0.5:  # Less than 50% leadership
                score += 15

            # Has board oversight
            if len(company.board_member_ids) > 0:
                score += 10

            # Has executive leadership
            if len(company.executive_ids) > 0:
                score += 5

        return min(score, 100)

    def _evaluate_plan_adherence(self, company: Any) -> float:
        """Evaluate if company is following its business plan.

        Args:
            company: Company to evaluate

        Returns:
            Score 0-100
        """
        score = 60.0  # Base score

        # Check if stage progression is on track
        if company.stage == "development" and len(company.products) > 0:
            score += 20  # Developing products as planned

        if company.stage == "seeking_investment":
            score += 15  # Following fundraising plan

        if company.stage == "operational" and hasattr(company, "metrics") and company.metrics.revenue > 0:
            score += 25  # Generating revenue as planned

        return min(score, 100)

    def _save_alignment_score(self, score: AlignmentScore):
        """Save alignment score to file."""
        log_file = self.log_dir / f"alignment_{self.session_id}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            record = {
                "timestamp": score.timestamp.isoformat(),
                "company_id": score.company_id,
                "overall_alignment": score.overall_alignment,
                "goal_consistency": score.goal_consistency,
                "resource_efficiency": score.resource_efficiency,
                "sub_agent_coordination": score.sub_agent_coordination,
                "plan_adherence": score.plan_adherence,
                "alignment_level": score.alignment_level,
                "issues": score.issues,
                "strengths": score.strengths,
            }
            f.write(json.dumps(record) + "\n")

    def _save_anomaly(self, anomaly: Anomaly):
        """Save anomaly to file."""
        log_file = self.log_dir / f"anomalies_{self.session_id}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            record = {
                "timestamp": anomaly.timestamp.isoformat(),
                "company_id": anomaly.company_id,
                "type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "description": anomaly.description,
                "affected_components": anomaly.affected_components,
                "recommended_actions": anomaly.recommended_actions,
                "metadata": anomaly.metadata,
            }
            f.write(json.dumps(record) + "\n")

    def _save_goal_progress(self, progress: GoalProgress):
        """Save goal progress to file."""
        log_file = self.log_dir / f"goals_{self.session_id}.jsonl"

        with open(log_file, "a", encoding="utf-8") as f:
            record = {
                "goal_id": progress.goal_id,
                "description": progress.goal_description,
                "target_date": progress.target_date.isoformat() if progress.target_date else None,
                "progress": progress.progress_percentage,
                "on_track": progress.on_track,
                "blockers": progress.blockers,
                "milestones": progress.recent_milestones,
            }
            f.write(json.dumps(record) + "\n")

    def export_to_json(self, output_dir: str):
        """Export all alignment data to JSON files.

        Args:
            output_dir: Directory to save export files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export alignment scores
        alignment_data = [
            {
                "timestamp": s.timestamp.isoformat(),
                "company_id": s.company_id,
                "overall_alignment": s.overall_alignment,
                "goal_consistency": s.goal_consistency,
                "resource_efficiency": s.resource_efficiency,
                "sub_agent_coordination": s.sub_agent_coordination,
                "plan_adherence": s.plan_adherence,
                "alignment_level": s.alignment_level,
                "issues": s.issues,
                "strengths": s.strengths,
            }
            for s in self.alignment_scores
        ]

        with open(output_path / "alignment_scores.json", "w", encoding="utf-8") as f:
            json.dump(alignment_data, f, indent=2)

        # Export anomalies
        anomaly_data = [
            {
                "timestamp": a.timestamp.isoformat(),
                "company_id": a.company_id,
                "type": a.anomaly_type,
                "severity": a.severity,
                "description": a.description,
                "affected_components": a.affected_components,
                "recommended_actions": a.recommended_actions,
            }
            for a in self.anomalies
        ]

        with open(output_path / "anomalies.json", "w", encoding="utf-8") as f:
            json.dump(anomaly_data, f, indent=2)
