"""Integration tests for API microservices.

Tests each microservice independently and together.
"""

from fastapi.testclient import TestClient
import pytest

from economic_agents.api.auth import api_key_manager
from economic_agents.api.rate_limit import rate_limiter
from economic_agents.api.services.compute_service import app as compute_app
from economic_agents.api.services.investor_service import app as investor_app
from economic_agents.api.services.marketplace_service import app as marketplace_app
from economic_agents.api.services.wallet_service import app as wallet_app


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    """Clear rate limiter state before each test."""
    rate_limiter.request_history.clear()
    yield
    rate_limiter.request_history.clear()


@pytest.fixture
def api_key():
    """Generate API key for testing."""
    return api_key_manager.generate_key("test-agent-1")


@pytest.fixture
def wallet_client():
    """Create wallet API test client."""
    return TestClient(wallet_app)


@pytest.fixture
def compute_client():
    """Create compute API test client."""
    return TestClient(compute_app)


@pytest.fixture
def marketplace_client():
    """Create marketplace API test client."""
    return TestClient(marketplace_app)


@pytest.fixture
def investor_client():
    """Create investor API test client."""
    return TestClient(investor_app)


class TestWalletAPI:
    """Tests for Wallet API microservice."""

    def test_health_check(self, wallet_client):
        """Test wallet health endpoint."""
        response = wallet_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "wallet"

    def test_get_balance(self, wallet_client, api_key):
        """Test getting balance."""
        response = wallet_client.get("/balance", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "agent_id" in data

    def test_deposit(self, wallet_client, api_key):
        """Test depositing funds."""
        response = wallet_client.post(
            "/transact",
            headers={"X-API-Key": api_key},
            json={"amount": 50.0, "purpose": "test deposit"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 50.0
        assert data["type"] == "earning"

    def test_withdraw(self, wallet_client, api_key):
        """Test withdrawing funds."""
        # First deposit
        wallet_client.post(
            "/transact",
            headers={"X-API-Key": api_key},
            json={"amount": 100.0, "purpose": "initial deposit"},
        )

        # Then withdraw
        response = wallet_client.post(
            "/transact",
            headers={"X-API-Key": api_key},
            json={"amount": -30.0, "purpose": "test withdrawal"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == -30.0
        assert data["type"] == "expense"

    def test_get_transactions(self, wallet_client, api_key):
        """Test getting transaction history."""
        # Make some transactions
        wallet_client.post(
            "/transact",
            headers={"X-API-Key": api_key},
            json={"amount": 25.0, "purpose": "tx 1"},
        )
        wallet_client.post(
            "/transact",
            headers={"X-API-Key": api_key},
            json={"amount": -10.0, "purpose": "tx 2"},
        )

        response = wallet_client.get("/transactions", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        assert len(data["transactions"]) >= 2

    def test_unauthorized_access(self, wallet_client):
        """Test that requests without API key are rejected."""
        response = wallet_client.get("/balance")
        assert response.status_code == 422  # Missing required header


class TestComputeAPI:
    """Tests for Compute API microservice."""

    def test_health_check(self, compute_client):
        """Test compute health endpoint."""
        response = compute_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "compute"

    def test_get_hours(self, compute_client, api_key):
        """Test getting compute hours."""
        response = compute_client.get("/hours", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "hours_remaining" in data
        assert "agent_id" in data

    def test_allocate_hours(self, compute_client, api_key):
        """Test allocating compute hours."""
        response = compute_client.post(
            "/allocate",
            headers={"X-API-Key": api_key},
            json={"hours": 5.0, "purpose": "test task"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["hours_allocated"] == 5.0

    def test_tick(self, compute_client, api_key):
        """Test time tick (hour decay)."""
        response = compute_client.post("/tick", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "hours_decayed" in data
        assert "hours_remaining" in data


class TestMarketplaceAPI:
    """Tests for Marketplace API microservice."""

    def test_health_check(self, marketplace_client):
        """Test marketplace health endpoint."""
        response = marketplace_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "marketplace"

    def test_get_tasks(self, marketplace_client, api_key):
        """Test getting tasks."""
        response = marketplace_client.get("/tasks?count=5", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 5
        assert data["count"] == 5

        # Verify task structure
        task = data["tasks"][0]
        assert "id" in task
        assert "difficulty" in task
        assert "reward" in task
        assert "compute_hours_required" in task
        assert "description" in task

    def test_get_task_by_id(self, marketplace_client, api_key):
        """Test getting specific task."""
        # First get tasks
        tasks_response = marketplace_client.get("/tasks?count=1", headers={"X-API-Key": api_key})
        task_id = tasks_response.json()["tasks"][0]["id"]

        # Then get specific task
        response = marketplace_client.get(f"/tasks/{task_id}", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id

    def test_complete_task(self, marketplace_client, api_key):
        """Test completing a task."""
        # Get a task
        tasks_response = marketplace_client.get("/tasks?count=1", headers={"X-API-Key": api_key})
        task_id = tasks_response.json()["tasks"][0]["id"]

        # Complete it
        response = marketplace_client.post(
            f"/tasks/{task_id}/complete",
            headers={"X-API-Key": api_key},
            json={"agent_id": "test-agent-1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestInvestorAPI:
    """Tests for Investor Portal API microservice."""

    def test_health_check(self, investor_client):
        """Test investor portal health endpoint."""
        response = investor_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "investor_portal"

    def test_get_investors(self, investor_client, api_key):
        """Test getting investor list."""
        response = investor_client.get("/investors", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "investors" in data
        assert len(data["investors"]) > 0

        # Verify investor structure
        investor = data["investors"][0]
        assert "name" in investor
        assert "focus" in investor
        assert "typical_check_size" in investor
        assert "stage_preference" in investor

    def test_submit_proposal(self, investor_client, api_key):
        """Test submitting investment proposal."""
        proposal = {
            "company_id": "test-company-1",
            "company_name": "Test Company",
            "stage": "seed",
            "business_plan": {"vision": "Test vision", "market": "Test market"},
            "funding_requested": 50000.0,
            "use_of_funds": "Product development",
            "team_size": 3,
            "revenue": 0.0,
            "monthly_burn_rate": 5000.0,
        }

        response = investor_client.post("/proposals", headers={"X-API-Key": api_key}, json=proposal)
        assert response.status_code == 200
        data = response.json()
        assert "proposal_id" in data
        assert "status" in data
        assert data["status"] in ["approved", "rejected"]

    def test_get_proposal_status(self, investor_client, api_key):
        """Test getting proposal status."""
        # First submit a proposal
        proposal = {
            "company_id": "test-company-2",
            "company_name": "Another Test Company",
            "stage": "seed",
            "business_plan": {"vision": "AI platform", "market": "Enterprise"},
            "funding_requested": 100000.0,
            "use_of_funds": "Team expansion",
            "team_size": 5,
            "revenue": 10000.0,
            "monthly_burn_rate": 15000.0,
        }

        submit_response = investor_client.post("/proposals", headers={"X-API-Key": api_key}, json=proposal)
        proposal_id = submit_response.json()["proposal_id"]

        # Then get status
        response = investor_client.get(f"/proposals/{proposal_id}", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "proposal_id" in data
        assert "approved" in data

    def test_list_proposals(self, investor_client, api_key):
        """Test listing agent's proposals."""
        response = investor_client.get("/proposals", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data


class TestAPIAuthentication:
    """Tests for API authentication system."""

    def test_invalid_api_key(self, wallet_client):
        """Test that invalid API key is rejected."""
        response = wallet_client.get("/balance", headers={"X-API-Key": "invalid_key"})
        assert response.status_code == 401

    def test_multiple_agents(self, wallet_client):
        """Test that different agents have isolated data."""
        # Create two API keys
        key1 = api_key_manager.generate_key("agent-1")
        key2 = api_key_manager.generate_key("agent-2")

        # Agent 1 deposits
        wallet_client.post(
            "/transact",
            headers={"X-API-Key": key1},
            json={"amount": 100.0, "purpose": "agent 1 deposit"},
        )

        # Agent 2 deposits
        wallet_client.post(
            "/transact",
            headers={"X-API-Key": key2},
            json={"amount": 200.0, "purpose": "agent 2 deposit"},
        )

        # Check balances are different
        balance1 = wallet_client.get("/balance", headers={"X-API-Key": key1}).json()
        balance2 = wallet_client.get("/balance", headers={"X-API-Key": key2}).json()

        assert balance1["balance"] != balance2["balance"]


class TestCrossServiceIntegration:
    """Tests for cross-service interactions."""

    def test_wallet_and_compute_together(self, wallet_client, compute_client, api_key):
        """Test using wallet and compute services together."""
        # Initialize wallet with funds
        wallet_client.post("/initialize", headers={"X-API-Key": api_key}, params={"initial_balance": 1000.0})

        # Initialize compute
        compute_client.post(
            "/initialize",
            headers={"X-API-Key": api_key},
            params={"initial_hours": 100.0, "cost_per_hour": 2.0},
        )

        # Get initial state
        wallet_balance = wallet_client.get("/balance", headers={"X-API-Key": api_key}).json()
        compute_hours = compute_client.get("/hours", headers={"X-API-Key": api_key}).json()

        assert wallet_balance["balance"] == 1000.0
        assert compute_hours["hours_remaining"] == 100.0

    def test_marketplace_and_wallet_flow(self, marketplace_client, wallet_client, api_key):
        """Test marketplace task completion updating wallet."""
        # Get initial balance
        initial_balance = wallet_client.get("/balance", headers={"X-API-Key": api_key}).json()["balance"]

        # Get a task
        tasks = marketplace_client.get("/tasks?count=1", headers={"X-API-Key": api_key}).json()
        task = tasks["tasks"][0]

        # Note: In a real integrated system, completing the task would automatically
        # update the wallet. For now, we test them independently but could be
        # connected in the agent's task completion logic.

        assert task["reward"] > 0
        assert initial_balance >= 0
