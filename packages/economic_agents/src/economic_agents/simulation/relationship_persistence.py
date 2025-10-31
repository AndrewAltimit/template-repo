"""Relationship persistence for investor-agent memory and relationship building."""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class InteractionRecord:
    """Record of an interaction between investor and agent."""

    timestamp: datetime
    proposal_id: str
    approved: bool
    amount_requested: float
    amount_offered: float
    quality_score: float  # 0.0-1.0 based on proposal quality
    feedback_provided: str
    interaction_type: str  # "proposal", "followup", "update"


@dataclass
class RelationshipProfile:
    """Relationship profile between investor and agent."""

    investor_id: str
    agent_id: str
    first_interaction: datetime
    last_interaction: datetime
    interaction_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    total_funding_received: float = 0.0
    avg_proposal_quality: float = 0.5
    relationship_score: float = 0.5  # 0.0-1.0, starts neutral
    trust_level: str = "new"  # new, building, established, strong, strained
    interaction_history: List[InteractionRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def approval_rate(self) -> float:
        """Calculate approval rate."""
        if self.interaction_count == 0:
            return 0.0
        return self.approved_count / self.interaction_count

    @property
    def days_since_first_interaction(self) -> int:
        """Calculate days since first interaction."""
        return (datetime.now() - self.first_interaction).days

    @property
    def days_since_last_interaction(self) -> int:
        """Calculate days since last interaction."""
        return (datetime.now() - self.last_interaction).days


class RelationshipPersistence:
    """Tracks and persists relationships between investors and agents.

    Features:
    - Investor memory of past interactions
    - Relationship building over time
    - Pattern recognition (e.g., spam detection)
    - Relationship-based decision modifiers
    """

    def __init__(
        self,
        relationship_decay_days: int = 90,
        spam_threshold_days: int = 7,
        seed: Optional[int] = None,
    ):
        """Initialize relationship persistence system.

        Args:
            relationship_decay_days: Days before relationship starts to decay
            spam_threshold_days: Days threshold for spam detection
            seed: Random seed for reproducibility
        """
        self.relationship_decay_days = relationship_decay_days
        self.spam_threshold_days = spam_threshold_days
        self.rng = random.Random(seed)

        # Store relationships: {(investor_id, agent_id): RelationshipProfile}
        self.relationships: Dict[tuple, RelationshipProfile] = {}

    def get_relationship(self, investor_id: str, agent_id: str) -> Optional[RelationshipProfile]:
        """Get existing relationship profile.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier

        Returns:
            Relationship profile or None if no relationship exists
        """
        key = (investor_id, agent_id)
        return self.relationships.get(key)

    def record_interaction(
        self,
        investor_id: str,
        agent_id: str,
        proposal_id: str,
        approved: bool,
        amount_requested: float,
        amount_offered: float,
        quality_score: float,
        feedback: str = "",
        interaction_type: str = "proposal",
    ) -> RelationshipProfile:
        """Record an interaction and update relationship.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier
            proposal_id: Proposal identifier
            approved: Whether proposal was approved
            amount_requested: Amount requested by agent
            amount_offered: Amount offered by investor (0 if rejected)
            quality_score: Quality rating of proposal (0.0-1.0)
            feedback: Feedback provided to agent
            interaction_type: Type of interaction

        Returns:
            Updated relationship profile
        """
        key = (investor_id, agent_id)

        # Get or create relationship
        if key not in self.relationships:
            self.relationships[key] = RelationshipProfile(
                investor_id=investor_id,
                agent_id=agent_id,
                first_interaction=datetime.now(),
                last_interaction=datetime.now(),
            )

        profile = self.relationships[key]

        # Create interaction record
        record = InteractionRecord(
            timestamp=datetime.now(),
            proposal_id=proposal_id,
            approved=approved,
            amount_requested=amount_requested,
            amount_offered=amount_offered,
            quality_score=quality_score,
            feedback_provided=feedback,
            interaction_type=interaction_type,
        )

        profile.interaction_history.append(record)
        profile.last_interaction = datetime.now()
        profile.interaction_count += 1

        if approved:
            profile.approved_count += 1
            profile.total_funding_received += amount_offered
        else:
            profile.rejected_count += 1

        # Update average proposal quality
        profile.avg_proposal_quality = sum(r.quality_score for r in profile.interaction_history) / len(
            profile.interaction_history
        )

        # Update relationship score
        profile.relationship_score = self._calculate_relationship_score(profile)

        # Update trust level
        profile.trust_level = self._calculate_trust_level(profile)

        return profile

    def _calculate_relationship_score(self, profile: RelationshipProfile) -> float:
        """Calculate relationship score based on interaction history.

        Args:
            profile: Relationship profile

        Returns:
            Relationship score (0.0-1.0)
        """
        # Weight components
        approval_weight = 0.3
        quality_weight = 0.3
        consistency_weight = 0.2
        longevity_weight = 0.2

        # Approval rate component
        approval_component = profile.approval_rate * approval_weight

        # Quality component
        quality_component = profile.avg_proposal_quality * quality_weight

        # Consistency component (reward regular, not spammy, interaction)
        days_since_last = profile.days_since_last_interaction
        if days_since_last > self.relationship_decay_days:
            # Relationship is decaying
            consistency_factor = 0.3
        elif days_since_last < 2:
            # Too frequent (potential spam)
            consistency_factor = 0.5
        else:
            # Good interaction frequency
            consistency_factor = 1.0

        consistency_component = consistency_factor * consistency_weight

        # Longevity component (longer relationships = higher score)
        longevity_factor = min(profile.interaction_count / 10.0, 1.0)  # Max at 10 interactions
        longevity_component = longevity_factor * longevity_weight

        score = approval_component + quality_component + consistency_component + longevity_component

        return max(0.0, min(1.0, score))

    def _calculate_trust_level(self, profile: RelationshipProfile) -> str:
        """Calculate trust level based on relationship score and history.

        Args:
            profile: Relationship profile

        Returns:
            Trust level string
        """
        score = profile.relationship_score

        # Consider interaction count
        if profile.interaction_count < 2:
            return "new"
        elif score < 0.3:
            return "strained"
        elif score < 0.5:
            return "building"
        elif score < 0.7:
            return "established"
        else:
            return "strong"

    def check_spam_pattern(self, investor_id: str, agent_id: str) -> bool:
        """Check if agent is spamming investor.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier

        Returns:
            True if spam pattern detected, False otherwise
        """
        profile = self.get_relationship(investor_id, agent_id)

        if not profile or len(profile.interaction_history) < 3:
            return False

        # Check for multiple submissions in short time
        recent_interactions = [
            r for r in profile.interaction_history if (datetime.now() - r.timestamp).days <= self.spam_threshold_days
        ]

        # More than 3 proposals in spam threshold window = spam
        if len(recent_interactions) > 3:
            return True

        # Check for repeated rejections without improvement
        last_five = profile.interaction_history[-5:]
        if len(last_five) == 5:
            all_rejected = all(not r.approved for r in last_five)
            no_improvement = all(last_five[i].quality_score <= last_five[i + 1].quality_score for i in range(4))

            if all_rejected and no_improvement:
                return True

        return False

    def get_relationship_modifier(self, investor_id: str, agent_id: str) -> Dict[str, float]:
        """Get decision modifiers based on relationship.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier

        Returns:
            Dict with modifier values
        """
        profile = self.get_relationship(investor_id, agent_id)

        if not profile:
            # No relationship = neutral
            return {
                "approval_probability_modifier": 0.0,
                "amount_multiplier": 1.0,
                "evaluation_score_modifier": 0.0,
            }

        # Check for spam
        if self.check_spam_pattern(investor_id, agent_id):
            # Strong negative modifiers for spam
            return {
                "approval_probability_modifier": -0.3,
                "amount_multiplier": 0.5,
                "evaluation_score_modifier": -0.2,
            }

        # Relationship-based modifiers
        score = profile.relationship_score

        # Better relationships get better terms
        approval_modifier = (score - 0.5) * 0.3  # ±0.15
        amount_multiplier = 0.7 + (score * 0.6)  # 0.7 - 1.3x
        eval_modifier = (score - 0.5) * 0.2  # ±0.1

        return {
            "approval_probability_modifier": approval_modifier,
            "amount_multiplier": amount_multiplier,
            "evaluation_score_modifier": eval_modifier,
        }

    def get_relationship_summary(self, investor_id: str, agent_id: str) -> Optional[Dict]:
        """Get human-readable relationship summary.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier

        Returns:
            Dict with relationship summary or None
        """
        profile = self.get_relationship(investor_id, agent_id)

        if not profile:
            return None

        return {
            "trust_level": profile.trust_level,
            "relationship_score": round(profile.relationship_score, 3),
            "interaction_count": profile.interaction_count,
            "approval_rate": round(profile.approval_rate, 3),
            "avg_proposal_quality": round(profile.avg_proposal_quality, 3),
            "total_funding": round(profile.total_funding_received, 2),
            "days_active": profile.days_since_first_interaction,
            "last_interaction": f"{profile.days_since_last_interaction} days ago",
            "is_spam": self.check_spam_pattern(investor_id, agent_id),
        }

    def generate_relationship_feedback(self, investor_id: str, agent_id: str) -> str:
        """Generate personalized feedback based on relationship history.

        Args:
            investor_id: Investor identifier
            agent_id: Agent identifier

        Returns:
            Personalized feedback string
        """
        profile = self.get_relationship(investor_id, agent_id)

        if not profile:
            return "Thank you for your interest. We look forward to learning more about your company."

        if profile.trust_level == "strong":
            return (
                f"Based on our {profile.interaction_count} interactions, we have a strong relationship. "
                f"Your proposals have consistently demonstrated quality (avg {profile.avg_proposal_quality:.2f}). "
                "We're excited to continue working together."
            )
        elif profile.trust_level == "established":
            return (
                f"We've had {profile.interaction_count} productive interactions so far. "
                f"Your track record ({profile.approval_rate:.0%} approval rate) is solid. "
                "Keep up the good work."
            )
        elif profile.trust_level == "building":
            return (
                f"We're still getting to know each other ({profile.interaction_count} interactions). "
                "Focus on addressing previous feedback to strengthen our relationship."
            )
        elif profile.trust_level == "strained":
            if self.check_spam_pattern(investor_id, agent_id):
                return (
                    f"We've noticed {profile.interaction_count} submissions in a short period. "
                    "Please take time to incorporate feedback before resubmitting. "
                    "Quality over quantity is key to building trust."
                )
            else:
                return (
                    "Your recent proposals haven't met our criteria. "
                    "We recommend carefully reviewing previous feedback and improving proposal quality "
                    "before submitting again."
                )
        else:  # new
            return "This is our first interaction. We're excited to learn about your company and vision."
