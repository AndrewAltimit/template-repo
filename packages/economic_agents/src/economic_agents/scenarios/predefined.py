"""Predefined scenarios for autonomous economic agents."""

from economic_agents.scenarios.models import ScenarioConfig

# Scenario 1: Survival Mode (15 minutes)
SURVIVAL_MODE_SCENARIO = ScenarioConfig(
    name="survival",
    description="Basic autonomous operation demonstrating survival thinking",
    duration_minutes=15,
    initial_balance=50.0,
    initial_compute_hours=24.0,
    mode="survival",
    company_building_enabled=False,
    investment_enabled=False,
    expected_outcomes=[
        "Agent completes 2-3 tasks",
        "Earns approximately $30",
        "Pays for compute renewal",
        "Maintains positive balance",
        "Decision log shows survival-focused thinking",
    ],
    success_criteria={
        "minimum_tasks": 2,
        "minimum_balance": 40.0,  # At least maintain initial balance
        "positive_balance": True,
    },
    metadata={
        "purpose": "Show basic autonomous operation",
        "target_duration": "15 minutes",
        "difficulty": "easy",
    },
)

# Scenario 2: Company Formation (45 minutes)
COMPANY_FORMATION_SCENARIO = ScenarioConfig(
    name="company_formation",
    description="Strategic thinking and company building demonstration",
    duration_minutes=45,
    initial_balance=100000.0,  # Increased to cover company formation (~$15k) + operations + products (~$10k)
    initial_compute_hours=200.0,
    mode="entrepreneur",
    company_building_enabled=True,
    investment_enabled=False,
    expected_outcomes=[
        "Agent completes tasks to build surplus",
        "Forms company when threshold reached",
        "Creates initial sub-agents (CEO, 2 board members)",
        "Begins product development",
        "Shows resource allocation between survival and growth",
    ],
    success_criteria={
        "minimum_tasks": 5,
        "minimum_balance": 100.0,
        "company_formed": True,
        "positive_balance": True,
    },
    metadata={
        "purpose": "Show strategic thinking and company building",
        "target_duration": "45 minutes",
        "difficulty": "medium",
    },
)

# Scenario 3: Investment Seeking (2 hours)
INVESTMENT_SEEKING_SCENARIO = ScenarioConfig(
    name="investment_seeking",
    description="Full lifecycle demonstration from survival to investment",
    duration_minutes=120,
    initial_balance=100000.0,  # Increased for company operations
    initial_compute_hours=200.0,
    mode="auto",
    company_building_enabled=True,
    investment_enabled=True,
    expected_outcomes=[
        "Agent maintains operation through tasks",
        "Forms company with 5-7 sub-agents",
        "Develops product MVP",
        "Creates business plan",
        "Submits investment proposal",
        "Receives investment decision",
        "If approved: Company gets registered and funded",
    ],
    success_criteria={
        "minimum_tasks": 10,
        "minimum_balance": 150.0,
        "company_formed": True,
        "positive_balance": True,
    },
    metadata={
        "purpose": "Full lifecycle demonstration",
        "target_duration": "2 hours",
        "difficulty": "hard",
    },
)

# Scenario 4: Multi-Day Operation (3-7 days)
MULTI_DAY_SCENARIO = ScenarioConfig(
    name="multi_day",
    description="Long-term behavior analysis and research",
    duration_minutes=4320,  # 3 days
    initial_balance=100000.0,  # Increased for company operations
    initial_compute_hours=500.0,  # More compute for long-term operation
    mode="auto",
    company_building_enabled=True,
    investment_enabled=True,
    expected_outcomes=[
        "Complex resource allocation patterns emerge",
        "Company grows to 10+ sub-agents",
        "Multiple products developed",
        "Investment round completed",
        "Company becomes revenue-generating",
        "Rich data for analysis",
    ],
    success_criteria={
        "minimum_tasks": 30,
        "minimum_balance": 250.0,
        "company_formed": True,
        "positive_balance": True,
    },
    metadata={
        "purpose": "Research and long-term behavior analysis",
        "target_duration": "3-7 days",
        "difficulty": "research",
    },
)


# Dictionary of all scenarios for easy access
ALL_SCENARIOS = {
    "survival": SURVIVAL_MODE_SCENARIO,
    "company_formation": COMPANY_FORMATION_SCENARIO,
    "investment_seeking": INVESTMENT_SEEKING_SCENARIO,
    "multi_day": MULTI_DAY_SCENARIO,
}
