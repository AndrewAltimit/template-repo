"""Investor response variability for realistic investment decisions."""

from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional, Tuple

from economic_agents.simulation.latency_simulator import LatencySimulator


class InvestorResponseSimulator:
    """Simulates realistic investor response patterns.

    Implements:
    - Response delays (1-7 days instead of instant)
    - Partial offers ("We'll invest 60% of what you asked")
    - Counteroffers (different equity/valuation terms)
    - Follow-up questions
    - Varied rejection reasons with specific feedback
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize investor response simulator.

        Args:
            seed: Random seed for reproducibility
        """
        self.rng = random.Random(seed)
        self.latency_sim = LatencySimulator(seed=seed)

        # Track proposal submission times for response delays
        self.proposal_times: Dict[str, datetime] = {}

        # Response time ranges (in hours)
        self.response_time_ranges = {
            "quick": (24, 48),  # 1-2 days
            "normal": (72, 120),  # 3-5 days
            "slow": (120, 168),  # 5-7 days
        }

    def calculate_response_delay(self, proposal_score: float) -> Tuple[datetime, str]:
        """Calculate when investor will respond based on proposal quality.

        Args:
            proposal_score: Overall evaluation score (0.0-1.0)

        Returns:
            Tuple of (response_datetime, response_speed_category)
        """
        # Better proposals get faster responses
        if proposal_score >= 0.8:
            speed = "quick"
        elif proposal_score >= 0.6:
            speed = "normal"
        else:
            speed = "slow"

        min_hours, max_hours = self.response_time_ranges[speed]
        delay_hours = self.rng.uniform(min_hours, max_hours)

        response_time = datetime.now() + timedelta(hours=delay_hours)

        return response_time, speed

    def should_make_partial_offer(self, proposal_score: float) -> bool:
        """Determine if investor will make a partial offer instead of full amount.

        Args:
            proposal_score: Overall evaluation score (0.0-1.0)

        Returns:
            True if partial offer should be made
        """
        # Moderate proposals (0.6-0.75) often get partial offers
        if 0.6 <= proposal_score < 0.75:
            return self.rng.random() < 0.4  # 40% chance

        # Lower proposals occasionally get partial offers
        if 0.5 <= proposal_score < 0.6:
            return self.rng.random() < 0.2  # 20% chance

        return False

    def calculate_partial_offer_amount(self, requested_amount: float) -> float:
        """Calculate partial investment amount.

        Args:
            requested_amount: Amount requested in proposal

        Returns:
            Partial amount to offer (50-80% of requested)
        """
        percentage = self.rng.uniform(0.5, 0.8)
        return requested_amount * percentage

    def should_make_counteroffer(self, proposal_score: float) -> bool:
        """Determine if investor will counteroffer with different terms.

        Args:
            proposal_score: Overall evaluation score (0.0-1.0)

        Returns:
            True if counteroffer should be made
        """
        # Good but not great proposals often get counteroffers
        if 0.65 <= proposal_score < 0.8:
            return self.rng.random() < 0.3  # 30% chance

        return False

    def generate_counteroffer_terms(self, original_equity: float, original_valuation: float) -> Tuple[float, float, str]:
        """Generate counteroffer terms.

        Args:
            original_equity: Original equity percentage offered
            original_valuation: Original company valuation

        Returns:
            Tuple of (new_equity, new_valuation, explanation)
        """
        counteroffer_type = self.rng.choice(["more_equity", "lower_valuation", "both"])

        if counteroffer_type == "more_equity":
            new_equity = original_equity * self.rng.uniform(1.2, 1.5)
            new_valuation = original_valuation
            explanation = f"We'd like to invest but need {new_equity:.1f}% equity instead of {original_equity:.1f}%"

        elif counteroffer_type == "lower_valuation":
            new_equity = original_equity
            new_valuation = original_valuation * self.rng.uniform(0.7, 0.85)
            explanation = f"We value the company at ${new_valuation:,.0f} instead of ${original_valuation:,.0f}"

        else:  # both
            new_equity = original_equity * self.rng.uniform(1.15, 1.35)
            new_valuation = original_valuation * self.rng.uniform(0.75, 0.9)
            explanation = f"We propose {new_equity:.1f}% equity at ${new_valuation:,.0f} valuation"

        return new_equity, new_valuation, explanation

    def should_request_more_info(self, proposal_score: float, has_critical_weakness: bool) -> bool:
        """Determine if investor will request more information.

        Args:
            proposal_score: Overall evaluation score (0.0-1.0)
            has_critical_weakness: Whether proposal has a weak score in critical area

        Returns:
            True if more information should be requested
        """
        # Always request info if there's a critical weakness
        if has_critical_weakness:
            return self.rng.random() < 0.6  # 60% chance

        # Sometimes request info for moderate proposals
        if 0.55 <= proposal_score < 0.7:
            return self.rng.random() < 0.3  # 30% chance

        return False

    def generate_info_requests(self, evaluation_scores: Dict[str, float]) -> List[str]:
        """Generate specific information requests based on weak areas.

        Args:
            evaluation_scores: Scores for each evaluation criterion

        Returns:
            List of specific questions/requests
        """
        requests = []

        if evaluation_scores.get("market_size", 1.0) < 0.5:
            requests.append("Can you provide more details on your market size calculations and TAM analysis?")

        if evaluation_scores.get("revenue", 1.0) < 0.5:
            requests.append("What assumptions underlie your revenue projections? Can you share unit economics?")

        if evaluation_scores.get("team", 1.0) < 0.6:
            requests.append("Can you share more about the team's background and relevant experience?")

        if evaluation_scores.get("competitive_advantage", 1.0) < 0.5:
            requests.append("How do you differentiate from competitors? What's your moat?")

        if evaluation_scores.get("risk", 1.0) < 0.5:
            requests.append("How do you plan to mitigate the execution risks you've identified?")

        if evaluation_scores.get("valuation", 1.0) < 0.5:
            requests.append("Can you justify the valuation? What comparables are you using?")

        # Always ask at least one question if we're requesting info
        if not requests:
            requests.append("Can you provide more details on your go-to-market strategy?")

        return requests

    def generate_rejection_feedback(self, evaluation_scores: Dict[str, float], overall_score: float) -> str:
        """Generate detailed rejection feedback with specific reasons.

        Args:
            evaluation_scores: Scores for each evaluation criterion
            overall_score: Overall proposal score

        Returns:
            Detailed feedback string
        """
        # Identify weakest areas
        weak_areas = [(area, score) for area, score in evaluation_scores.items() if score < 0.5]
        weak_areas.sort(key=lambda x: x[1])  # Sort by score, worst first

        feedback_parts = [f"Thank you for your submission. Overall score: {overall_score:.2f}/1.00."]

        if weak_areas:
            feedback_parts.append("\n\nKey concerns:")
            for area, score in weak_areas[:3]:  # Top 3 concerns
                if area == "market_size":
                    feedback_parts.append(
                        f"\n- Market opportunity (score: {score:.2f}): The addressable market appears "
                        "too small for our investment thesis"
                    )
                elif area == "revenue":
                    feedback_parts.append(
                        f"\n- Revenue projections (score: {score:.2f}): The financial projections "
                        "don't align with our return requirements"
                    )
                elif area == "team":
                    feedback_parts.append(
                        f"\n- Team strength (score: {score:.2f}): We'd like to see more relevant "
                        "experience or a larger founding team"
                    )
                elif area == "risk":
                    feedback_parts.append(
                        f"\n- Risk profile (score: {score:.2f}): The execution risks are higher than our risk tolerance allows"
                    )
                elif area == "valuation":
                    feedback_parts.append(
                        f"\n- Valuation (score: {score:.2f}): The current valuation is not aligned "
                        "with our assessment of the opportunity"
                    )
                elif area == "competitive_advantage":
                    feedback_parts.append(
                        f"\n- Competitive position (score: {score:.2f}): We'd like to see stronger "
                        "differentiation and defensibility"
                    )

        # Add constructive guidance
        if overall_score >= 0.4:
            feedback_parts.append(
                "\n\nThis shows promise. We encourage you to address these concerns and consider resubmitting in 6-12 months."
            )
        elif overall_score >= 0.3:
            feedback_parts.append("\n\nWe suggest strengthening your proposal before approaching investors again.")
        else:
            feedback_parts.append("\n\nThis doesn't align with our current investment focus.")

        return "".join(feedback_parts)

    def generate_approval_feedback(self, evaluation_scores: Dict[str, float], overall_score: float, investor_name: str) -> str:
        """Generate detailed approval feedback highlighting strengths.

        Args:
            evaluation_scores: Scores for each evaluation criterion
            overall_score: Overall proposal score
            investor_name: Name of approving investor

        Returns:
            Detailed feedback string
        """
        # Identify strong areas
        strong_areas = [(area, score) for area, score in evaluation_scores.items() if score >= 0.7]
        strong_areas.sort(key=lambda x: x[1], reverse=True)  # Sort by score, best first

        feedback_parts = [f"{investor_name} is pleased to approve your proposal. Overall score: {overall_score:.2f}/1.00."]

        if strong_areas:
            feedback_parts.append("\n\nKey strengths:")
            for area, score in strong_areas[:3]:  # Top 3 strengths
                if area == "market_size":
                    feedback_parts.append(
                        f"\n- Market opportunity (score: {score:.2f}): Excellent market potential "
                        "with strong growth trajectory"
                    )
                elif area == "revenue":
                    feedback_parts.append(
                        f"\n- Revenue projections (score: {score:.2f}): Compelling financial model "
                        "with clear path to profitability"
                    )
                elif area == "team":
                    feedback_parts.append(
                        f"\n- Team strength (score: {score:.2f}): Strong founding team with relevant domain expertise"
                    )
                elif area == "competitive_advantage":
                    feedback_parts.append(
                        f"\n- Competitive position (score: {score:.2f}): Clear differentiation and defensible moat"
                    )

        # Identify areas for improvement (scores between 0.5 and 0.7)
        moderate_areas = [(area, score) for area, score in evaluation_scores.items() if 0.5 <= score < 0.7]

        if moderate_areas:
            feedback_parts.append("\n\nAreas to monitor:")
            for area, score in moderate_areas[:2]:  # Top 2 areas to watch
                if area == "team":
                    feedback_parts.append("\n- Consider expanding the team as you scale")
                elif area == "risk":
                    feedback_parts.append("\n- Focus on de-risking execution through early wins")
                elif area == "revenue":
                    feedback_parts.append("\n- Close monitoring of unit economics as you grow")

        return "".join(feedback_parts)

    def record_proposal_submission(self, proposal_id: str) -> None:
        """Record when a proposal was submitted.

        Args:
            proposal_id: Proposal identifier
        """
        self.proposal_times[proposal_id] = datetime.now()

    def is_response_ready(self, _proposal_id: str, response_time: datetime) -> bool:
        """Check if investor response is ready based on simulated delay.

        Args:
            _proposal_id: Proposal identifier
            response_time: When response should be ready

        Returns:
            True if response is ready, False if still pending
        """
        return datetime.now() >= response_time
