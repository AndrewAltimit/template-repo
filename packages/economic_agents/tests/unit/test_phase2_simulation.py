"""Tests for Phase 2 simulation features (Market Dynamics, Reputation, Social Proof, Relationships)."""

from datetime import datetime, timedelta

from economic_agents.simulation.market_dynamics import MarketDynamics, MarketPhase
from economic_agents.simulation.relationship_persistence import RelationshipPersistence
from economic_agents.simulation.reputation_system import ReputationSystem
from economic_agents.simulation.social_proof import SocialProofSignals


class TestMarketDynamics:
    """Tests for MarketDynamics simulation."""

    def test_initialization(self):
        """Test market dynamics initialization."""
        market = MarketDynamics(initial_phase=MarketPhase.NORMAL, seed=42)

        assert market.current_phase == MarketPhase.NORMAL
        assert market.phase_duration_hours == 48.0
        assert market.crash_probability == 0.01

    def test_get_task_availability_multiplier(self):
        """Test task availability multiplier for different market phases."""
        market = MarketDynamics(seed=42)

        # Test all phases
        for phase in [MarketPhase.BULL, MarketPhase.NORMAL, MarketPhase.BEAR, MarketPhase.CRASH]:
            market.current_phase = phase
            multiplier = market.get_task_availability_multiplier()

            # Verify multiplier is in expected range
            if phase == MarketPhase.BULL:
                assert 1.3 <= multiplier <= 2.0
            elif phase == MarketPhase.NORMAL:
                assert 0.8 <= multiplier <= 1.2
            elif phase == MarketPhase.BEAR:
                assert 0.4 <= multiplier <= 0.7
            elif phase == MarketPhase.CRASH:
                assert 0.1 <= multiplier <= 0.3

    def test_get_reward_multiplier(self):
        """Test reward multiplier for different market phases."""
        market = MarketDynamics(seed=42)

        for phase in MarketPhase:
            market.current_phase = phase
            multiplier = market.get_reward_multiplier()

            # Verify multiplier is positive
            assert multiplier > 0.0
            assert multiplier <= 1.5

    def test_get_investor_funding_multiplier(self):
        """Test investor funding multiplier."""
        market = MarketDynamics(seed=42)

        # Bull market should have higher funding
        market.current_phase = MarketPhase.BULL
        bull_multiplier = market.get_investor_funding_multiplier()

        # Bear market should have lower funding
        market.current_phase = MarketPhase.BEAR
        bear_multiplier = market.get_investor_funding_multiplier()

        assert bull_multiplier > bear_multiplier

    def test_time_of_day_multiplier(self):
        """Test time of day multiplier."""
        market = MarketDynamics(seed=42)

        multiplier = market.get_time_of_day_multiplier()

        # Should return a valid multiplier
        assert 0.3 <= multiplier <= 1.5

    def test_phase_transition(self):
        """Test market phase transition."""
        market = MarketDynamics(initial_phase=MarketPhase.NORMAL, seed=42)

        # Force transition by setting old start time
        market.phase_start_time = datetime.now() - timedelta(hours=50)

        # Check if transition is needed
        assert market.should_transition_phase()

        # Perform transition
        new_phase = market.transition_to_next_phase()

        # Verify phase changed
        assert new_phase in [MarketPhase.BULL, MarketPhase.NORMAL, MarketPhase.BEAR]

    def test_get_market_stats(self):
        """Test market statistics retrieval."""
        market = MarketDynamics(seed=42)

        stats = market.get_market_stats()

        # Verify all expected keys are present
        assert "phase" in stats
        assert "task_multiplier" in stats
        assert "reward_multiplier" in stats
        assert "funding_multiplier" in stats
        assert "is_weekend" in stats
        assert "is_business_hours" in stats


class TestReputationSystem:
    """Tests for ReputationSystem."""

    def test_initialization(self):
        """Test reputation system initialization."""
        rep_sys = ReputationSystem(seed=42)

        assert len(rep_sys.profiles) == 0
        assert rep_sys.tier_thresholds["beginner"] == 0
        assert rep_sys.tier_thresholds["expert"] == 200

    def test_create_profile(self):
        """Test profile creation."""
        rep_sys = ReputationSystem(seed=42)

        profile = rep_sys.get_or_create_profile("agent-1")

        assert profile.agent_id == "agent-1"
        assert profile.trust_score == 0.5  # Starts neutral
        assert profile.total_tasks == 0
        assert profile.tier == "beginner"

    def test_record_task_completion_success(self):
        """Test recording successful task completion."""
        rep_sys = ReputationSystem(seed=42)

        profile = rep_sys.record_task_completion(
            agent_id="agent-1",
            task_id="task-1",
            success=True,
            quality_score=0.9,
            completion_time_hours=5.0,
            reward_earned=500.0,
        )

        assert profile.total_tasks == 1
        assert profile.successful_tasks == 1
        assert profile.total_earnings == 500.0
        assert profile.avg_quality_score == 0.9
        assert len(profile.performance_history) == 1

    def test_record_task_completion_failure(self):
        """Test recording failed task completion."""
        rep_sys = ReputationSystem(seed=42)

        profile = rep_sys.record_task_completion(
            agent_id="agent-1",
            task_id="task-1",
            success=False,
            quality_score=0.3,
            completion_time_hours=8.0,
            reward_earned=0.0,
        )

        assert profile.total_tasks == 1
        assert profile.successful_tasks == 0
        assert profile.failed_tasks == 1
        assert profile.total_earnings == 0.0

    def test_trust_score_calculation(self):
        """Test trust score increases with good performance."""
        rep_sys = ReputationSystem(seed=42)

        # Record several successful tasks
        for i in range(5):
            rep_sys.record_task_completion(
                agent_id="agent-1",
                task_id=f"task-{i}",
                success=True,
                quality_score=0.9,
                completion_time_hours=5.0,
                reward_earned=500.0,
            )

        profile = rep_sys.get_or_create_profile("agent-1")

        # Trust score should be high with good performance
        assert profile.trust_score > 0.7

    def test_tier_progression(self):
        """Test tier progression with task completions."""
        rep_sys = ReputationSystem(seed=42)

        # Complete tasks to progress through tiers
        for i in range(15):
            rep_sys.record_task_completion(
                agent_id="agent-1",
                task_id=f"task-{i}",
                success=True,
                quality_score=0.8,
                completion_time_hours=5.0,
                reward_earned=500.0,
            )

        profile = rep_sys.get_or_create_profile("agent-1")

        # Should have progressed to intermediate tier (10+ successful tasks)
        assert profile.tier == "intermediate"

    def test_achievement_unlocks(self):
        """Test achievement unlocking."""
        rep_sys = ReputationSystem(seed=42)

        # First task achievement
        rep_sys.record_task_completion(
            agent_id="agent-1",
            task_id="task-1",
            success=True,
            quality_score=0.8,
            completion_time_hours=1.5,
            reward_earned=500.0,
        )

        profile = rep_sys.get_or_create_profile("agent-1")
        assert "first_task" in profile.achievements

    def test_get_access_multiplier(self):
        """Test task access multiplier based on reputation."""
        rep_sys = ReputationSystem(seed=42)

        # New agent should have reduced access
        multiplier_new = rep_sys.get_access_multiplier("agent-1")
        assert multiplier_new == 0.5

        # Improve reputation
        for i in range(15):
            rep_sys.record_task_completion(
                agent_id="agent-1",
                task_id=f"task-{i}",
                success=True,
                quality_score=0.9,
                completion_time_hours=5.0,
                reward_earned=500.0,
            )

        # Should have better access now
        multiplier_improved = rep_sys.get_access_multiplier("agent-1")
        assert multiplier_improved > multiplier_new

    def test_get_investor_interest_multiplier(self):
        """Test investor interest multiplier."""
        rep_sys = ReputationSystem(seed=42)

        # Build reputation
        for i in range(10):
            rep_sys.record_task_completion(
                agent_id="agent-1",
                task_id=f"task-{i}",
                success=True,
                quality_score=0.9,
                completion_time_hours=5.0,
                reward_earned=1000.0,
            )

        multiplier = rep_sys.get_investor_interest_multiplier("agent-1")

        # Good reputation should increase investor interest
        assert multiplier > 1.0


class TestSocialProofSignals:
    """Tests for SocialProofSignals."""

    def test_initialization(self):
        """Test social proof initialization."""
        social = SocialProofSignals(seed=42)

        assert social.base_agent_count == 50
        assert social.base_weekly_funding_count == 5
        assert len(social.task_views) == 0

    def test_get_task_intelligence(self):
        """Test task intelligence generation."""
        social = SocialProofSignals(seed=42)

        intelligence = social.get_task_intelligence("task-1", task_reward=1000.0)

        assert "total_views" in intelligence
        assert "agents_viewing" in intelligence
        assert "posted_time" in intelligence
        assert "interest_level" in intelligence
        assert intelligence["total_views"] > 0

    def test_task_views_increase(self):
        """Test that task views increase over time."""
        social = SocialProofSignals(seed=42)

        # First call initializes views
        intel1 = social.get_task_intelligence("task-1", task_reward=1000.0)
        views1 = intel1["total_views"]

        # Second call should increase views
        intel2 = social.get_task_intelligence("task-1", task_reward=1000.0)
        views2 = intel2["total_views"]

        assert views2 >= views1

    def test_get_category_stats(self):
        """Test category statistics."""
        social = SocialProofSignals(seed=42)

        stats = social.get_category_stats("ML")

        assert "category" in stats
        assert "completion_rate" in stats
        assert "total_completions" in stats
        assert "avg_completion_time_hours" in stats
        assert "popularity_rank" in stats
        assert 0.0 <= stats["completion_rate"] <= 1.0

    def test_get_funding_trends(self):
        """Test funding trends generation."""
        social = SocialProofSignals(seed=42)

        trends = social.get_funding_trends(market_phase="bull")

        assert "weekly_deals" in trends
        assert "avg_deal_size" in trends
        assert "popular_sector" in trends
        assert "market_sentiment" in trends
        assert trends["market_sentiment"] == "optimistic"

    def test_funding_trends_vary_by_market(self):
        """Test funding trends vary by market phase."""
        social = SocialProofSignals(seed=42)

        bull_trends = social.get_funding_trends(market_phase="bull")
        bear_trends = social.get_funding_trends(market_phase="bear")

        # Bull market should have more deals
        assert bull_trends["weekly_deals"] >= bear_trends["weekly_deals"]

    def test_get_benchmark_data(self):
        """Test benchmark data generation."""
        social = SocialProofSignals(seed=42)

        benchmark = social.get_benchmark_data(company_stage="seed", market_size=100000000.0, revenue=500000.0)

        assert "typical_valuation" in benchmark
        assert "typical_funding" in benchmark
        assert "valuation_multiple_range" in benchmark
        assert "market_percentile" in benchmark
        assert benchmark["stage"] == "seed"

    def test_record_task_completion(self):
        """Test recording task completions for stats."""
        social = SocialProofSignals(seed=42)

        # Record some completions
        social.record_task_completion("ML", success=True)
        social.record_task_completion("ML", success=True)
        social.record_task_completion("ML", success=False)

        stats = social.get_category_stats("ML")

        # Should reflect recorded completions
        assert stats["total_completions"] >= 2

    def test_get_marketplace_summary(self):
        """Test marketplace summary."""
        social = SocialProofSignals(seed=42)

        summary = social.get_marketplace_summary()

        assert "active_agents" in summary
        assert "total_available_tasks" in summary
        assert "tasks_completed_today" in summary
        assert "marketplace_health" in summary
        assert summary["active_agents"] > 0


class TestRelationshipPersistence:
    """Tests for RelationshipPersistence."""

    def test_initialization(self):
        """Test relationship persistence initialization."""
        rel_sys = RelationshipPersistence(seed=42)

        assert len(rel_sys.relationships) == 0
        assert rel_sys.relationship_decay_days == 90
        assert rel_sys.spam_threshold_days == 7

    def test_record_interaction(self):
        """Test recording an interaction."""
        rel_sys = RelationshipPersistence(seed=42)

        profile = rel_sys.record_interaction(
            investor_id="investor-1",
            agent_id="agent-1",
            proposal_id="proposal-1",
            approved=True,
            amount_requested=1000000.0,
            amount_offered=1000000.0,
            quality_score=0.8,
            feedback="Great proposal!",
        )

        assert profile.investor_id == "investor-1"
        assert profile.agent_id == "agent-1"
        assert profile.interaction_count == 1
        assert profile.approved_count == 1
        assert profile.total_funding_received == 1000000.0

    def test_relationship_score_improves(self):
        """Test relationship score improves with positive interactions."""
        rel_sys = RelationshipPersistence(seed=42)

        # Record multiple positive interactions
        for i in range(5):
            rel_sys.record_interaction(
                investor_id="investor-1",
                agent_id="agent-1",
                proposal_id=f"proposal-{i}",
                approved=True,
                amount_requested=1000000.0,
                amount_offered=1000000.0,
                quality_score=0.9,
                feedback="Excellent!",
            )

        profile = rel_sys.get_relationship("investor-1", "agent-1")

        # Relationship score should be high
        assert profile.relationship_score > 0.7

    def test_trust_level_progression(self):
        """Test trust level progression."""
        rel_sys = RelationshipPersistence(seed=42)

        # First interaction
        rel_sys.record_interaction(
            investor_id="investor-1",
            agent_id="agent-1",
            proposal_id="proposal-1",
            approved=True,
            amount_requested=1000000.0,
            amount_offered=1000000.0,
            quality_score=0.9,
        )

        profile = rel_sys.get_relationship("investor-1", "agent-1")
        assert profile.trust_level == "new"

        # Multiple successful interactions
        for i in range(5):
            rel_sys.record_interaction(
                investor_id="investor-1",
                agent_id="agent-1",
                proposal_id=f"proposal-{i + 2}",
                approved=True,
                amount_requested=1000000.0,
                amount_offered=1000000.0,
                quality_score=0.9,
            )

        profile = rel_sys.get_relationship("investor-1", "agent-1")

        # Should have progressed beyond "new"
        assert profile.trust_level in ["building", "established", "strong"]

    def test_spam_detection(self):
        """Test spam pattern detection."""
        rel_sys = RelationshipPersistence(spam_threshold_days=7, seed=42)

        # Submit 4 proposals rapidly
        for i in range(4):
            rel_sys.record_interaction(
                investor_id="investor-1",
                agent_id="agent-spammer",
                proposal_id=f"proposal-{i}",
                approved=False,
                amount_requested=1000000.0,
                amount_offered=0.0,
                quality_score=0.5,
            )

        # Should detect spam pattern
        is_spam = rel_sys.check_spam_pattern("investor-1", "agent-spammer")
        assert is_spam

    def test_relationship_modifiers(self):
        """Test relationship-based decision modifiers."""
        # Use longer spam threshold to avoid triggering spam detection
        rel_sys = RelationshipPersistence(spam_threshold_days=1, seed=42)

        # Build good relationship with 3 interactions (won't trigger spam)
        for i in range(3):
            rel_sys.record_interaction(
                investor_id="investor-1",
                agent_id="agent-1",
                proposal_id=f"proposal-{i}",
                approved=True,
                amount_requested=1000000.0,
                amount_offered=1000000.0,
                quality_score=0.9,
            )

        modifiers = rel_sys.get_relationship_modifier("investor-1", "agent-1")

        # Good relationship should have positive modifiers
        assert modifiers["approval_probability_modifier"] > 0.0
        assert modifiers["amount_multiplier"] > 1.0

    def test_get_relationship_summary(self):
        """Test relationship summary."""
        rel_sys = RelationshipPersistence(seed=42)

        # Record some interactions
        rel_sys.record_interaction(
            investor_id="investor-1",
            agent_id="agent-1",
            proposal_id="proposal-1",
            approved=True,
            amount_requested=1000000.0,
            amount_offered=1000000.0,
            quality_score=0.8,
        )

        summary = rel_sys.get_relationship_summary("investor-1", "agent-1")

        assert summary is not None
        assert "trust_level" in summary
        assert "relationship_score" in summary
        assert "interaction_count" in summary
        assert summary["interaction_count"] == 1

    def test_generate_relationship_feedback(self):
        """Test personalized feedback generation."""
        rel_sys = RelationshipPersistence(seed=42)

        # Build strong relationship
        for i in range(10):
            rel_sys.record_interaction(
                investor_id="investor-1",
                agent_id="agent-1",
                proposal_id=f"proposal-{i}",
                approved=True,
                amount_requested=1000000.0,
                amount_offered=1000000.0,
                quality_score=0.95,
            )

        feedback = rel_sys.generate_relationship_feedback("investor-1", "agent-1")

        # Should mention strong relationship
        assert len(feedback) > 0
        assert "interaction" in feedback.lower() or "relationship" in feedback.lower()
