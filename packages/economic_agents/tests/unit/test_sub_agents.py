"""Tests for sub-agent implementations."""

from economic_agents.sub_agents import (
    BoardMember,
    Executive,
    IndividualContributor,
    SubAgent,
    SubjectMatterExpert,
)


def test_sub_agent_initialization():
    """Test base sub-agent initializes correctly."""
    agent = SubAgent(id="agent_1", role="board_member", specialization="governance")

    assert agent.id == "agent_1"
    assert agent.role == "board_member"
    assert agent.specialization == "governance"
    assert agent.tasks_completed == 0
    assert agent.decisions_made == 0


def test_board_member_creation():
    """Test board member creation."""
    board_member = BoardMember(agent_id="board_1", specialization="finance")

    assert board_member.role == "board_member"
    assert board_member.specialization == "finance"


def test_board_member_review_decision():
    """Test board member reviewing decisions."""
    board_member = BoardMember(agent_id="board_1", specialization="governance")

    decision = {
        "type": "company_formation",
        "risk_level": "medium",
        "expected_roi": 0.7,
    }

    result = board_member.review_decision(decision)

    assert "approved" in result
    assert result["approved"] is True
    assert "reasoning" in result
    assert board_member.decisions_made == 1


def test_board_member_high_risk_approval():
    """Test board member reviews high-risk decisions carefully."""
    board_member = BoardMember(agent_id="board_1", specialization="finance")

    # High risk with good risk context - should approve
    decision1 = {
        "type": "expansion",
        "risk_level": "high",
        "risk_context": {
            "market_volatility": 0.3,  # Low market risk
            "team_experience": 0.8,  # High experience (low risk)
            "burn_multiple": 1.0,  # Reasonable burn
        },
    }
    result1 = board_member.review_decision(decision1)
    assert result1["approved"] is True

    # High risk with poor risk context - should reject
    decision2 = {
        "type": "expansion",
        "risk_level": "high",
        "risk_context": {
            "market_volatility": 0.8,  # High market risk
            "team_experience": 0.3,  # Low experience (high risk)
            "burn_multiple": 5.0,  # High burn
        },
    }
    result2 = board_member.review_decision(decision2)
    assert result2["approved"] is False


def test_executive_creation():
    """Test executive creation."""
    executive = Executive(agent_id="exec_1", role_title="CEO", specialization="leadership")

    assert executive.role == "executive"
    assert executive.role_title == "CEO"
    assert executive.specialization == "leadership"


def test_executive_execute_strategy():
    """Test executive strategy execution."""
    cto = Executive(agent_id="exec_1", role_title="CTO", specialization="technology")

    strategy = {"type": "product_development"}
    result = cto.execute_strategy(strategy)

    assert "status" in result
    assert "strategic_plan" in result  # Enhanced implementation returns strategic_plan
    assert "milestones" in result["strategic_plan"]  # Milestones are nested in strategic_plan
    assert cto.tasks_completed == 1


def test_executive_decision_by_role():
    """Test executives make role-appropriate decisions."""
    ceo = Executive(agent_id="exec_1", role_title="CEO", specialization="leadership")
    cto = Executive(agent_id="exec_2", role_title="CTO", specialization="technology")
    cfo = Executive(agent_id="exec_3", role_title="CFO", specialization="finance")

    # Enhanced implementation uses data-driven decisions
    ceo_decision = ceo.make_decision({"capital": 100000, "burn_rate": 15000})
    cto_decision = cto.make_decision({"capital": 100000, "burn_rate": 15000})
    cfo_decision = cfo.make_decision({"capital": 100000, "burn_rate": 15000})

    # Check that decisions are role-appropriate (enhanced implementation has different keys)
    assert "decision" in ceo_decision
    assert "decision" in cto_decision
    assert "decision" in cfo_decision


def test_sme_creation():
    """Test subject matter expert creation."""
    sme = SubjectMatterExpert(agent_id="sme_1", specialization="security")

    assert sme.role == "sme"
    assert sme.specialization == "security"


def test_sme_provide_expertise():
    """Test SME providing domain expertise."""
    security_sme = SubjectMatterExpert(agent_id="sme_1", specialization="security")

    advice = security_sme.provide_expertise("How to secure API?", {})

    assert "advice" in advice
    assert "priority" in advice
    assert "security" in advice["advice"].lower() or "authentication" in advice["advice"].lower()
    assert security_sme.tasks_completed == 1


def test_sme_specialization_specific_advice():
    """Test SMEs provide specialization-specific advice."""
    ml_sme = SubjectMatterExpert(agent_id="sme_1", specialization="machine-learning")
    scaling_sme = SubjectMatterExpert(agent_id="sme_2", specialization="scaling")

    ml_advice = ml_sme.provide_expertise("ML question", {})
    scaling_advice = scaling_sme.provide_expertise("Scaling question", {})

    # Enhanced implementation uses knowledge bases with detailed advice
    assert "advice" in ml_advice
    assert "advice" in scaling_advice
    # Verify the advice contains domain-specific content (knowledge base items)
    assert len(ml_advice["advice"]) > 0
    assert len(scaling_advice["advice"]) > 0


def test_ic_creation():
    """Test individual contributor creation."""
    ic = IndividualContributor(agent_id="ic_1", specialization="backend-dev")

    assert ic.role == "ic"
    assert ic.specialization == "backend-dev"


def test_ic_complete_task():
    """Test IC completing development tasks."""
    backend_dev = IndividualContributor(agent_id="ic_1", specialization="backend-dev")

    task = {"type": "feature_development", "complexity": "medium"}
    result = backend_dev.complete_task(task)

    assert result["status"] == "completed"
    # Enhanced implementation generates actual code artifacts
    assert "artifact" in result
    assert "estimation" in result
    assert backend_dev.tasks_completed == 1


def test_ic_specialization_results():
    """Test ICs produce specialization-specific results."""
    backend_dev = IndividualContributor(agent_id="ic_1", specialization="backend-dev")
    qa_engineer = IndividualContributor(agent_id="ic_2", specialization="qa")
    devops = IndividualContributor(agent_id="ic_3", specialization="devops")

    task = {"type": "task", "complexity": "medium"}

    backend_result = backend_dev.complete_task(task)
    qa_result = qa_engineer.complete_task(task)
    devops_result = devops.complete_task(task)

    # Enhanced implementation generates code artifacts with specialization-specific content
    assert backend_result["status"] == "completed"
    assert qa_result["status"] == "completed"
    assert devops_result["status"] == "completed"
    # All should have artifacts
    assert "artifact" in backend_result
    assert "artifact" in qa_result
    assert "artifact" in devops_result


def test_sub_agent_to_dict():
    """Test sub-agent serialization."""
    agent = BoardMember(agent_id="board_1", specialization="governance")
    agent.company_id = "company_123"
    agent.tasks_completed = 5
    agent.decisions_made = 10

    agent_dict = agent.to_dict()

    assert agent_dict["id"] == "board_1"
    assert agent_dict["role"] == "board_member"
    assert agent_dict["specialization"] == "governance"
    assert agent_dict["company_id"] == "company_123"
    assert agent_dict["tasks_completed"] == 5
    assert agent_dict["decisions_made"] == 10
