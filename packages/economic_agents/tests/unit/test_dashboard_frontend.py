"""Tests for Streamlit dashboard frontend components."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock streamlit and plotly modules before importing the app
sys.modules["streamlit"] = Mock()
sys.modules["plotly"] = Mock()
sys.modules["plotly.express"] = Mock()
sys.modules["plotly.graph_objects"] = Mock()
sys.modules["plotly.subplots"] = Mock()

# Set up mock secrets
mock_secrets = Mock()
mock_secrets.get = Mock(return_value="http://localhost:8000")  # type: ignore[assignment]
sys.modules["streamlit"].secrets = mock_secrets  # type: ignore[attr-defined]


# Create a session state mock that supports both dict and attribute access
class MockSessionState(dict):
    """Mock session state that acts like streamlit's session_state."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


# Set up mock session_state
mock_session_state = MockSessionState()
sys.modules["streamlit"].session_state = mock_session_state  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def mock_streamlit_components():
    """Mock Streamlit components for testing."""
    st_module = sys.modules["streamlit"]

    # Create mock column context managers
    mock_col = Mock()
    mock_col.__enter__ = Mock(return_value=mock_col)
    mock_col.__exit__ = Mock(return_value=False)

    # columns() should return a list based on the number requested
    def columns_mock(num_cols):
        # Handle both int and list arguments
        if isinstance(num_cols, (list, tuple)):
            return [mock_col] * len(num_cols)
        return [mock_col] * num_cols

    st_module.set_page_config = Mock()
    st_module.title = Mock()
    st_module.markdown = Mock()
    st_module.header = Mock()
    st_module.subheader = Mock()
    st_module.columns = Mock(side_effect=columns_mock)
    st_module.metric = Mock()

    # Expander context manager
    mock_expander = Mock()
    mock_expander.__enter__ = Mock(return_value=mock_expander)
    mock_expander.__exit__ = Mock(return_value=False)
    st_module.expander = Mock(return_value=mock_expander)

    st_module.json = Mock()
    st_module.plotly_chart = Mock()
    st_module.dataframe = Mock()
    st_module.write = Mock()
    st_module.info = Mock()
    st_module.warning = Mock()
    st_module.error = Mock()
    st_module.selectbox = Mock(return_value="All")
    st_module.sidebar = Mock()

    # Spinner context manager
    mock_spinner = Mock()
    mock_spinner.__enter__ = Mock(return_value=mock_spinner)
    mock_spinner.__exit__ = Mock(return_value=False)
    st_module.spinner = Mock(return_value=mock_spinner)

    st_module.divider = Mock()
    st_module.rerun = Mock()
    st_module.checkbox = Mock()
    st_module.slider = Mock()
    st_module.button = Mock()
    yield st_module


@pytest.fixture
def mock_api_response():
    """Mock API response data."""
    return {
        "status": {
            "agent_id": "test-agent-1",
            "balance": 150.0,
            "compute_hours_remaining": 48.0,
            "current_cycle": 10,
            "mode": "entrepreneur",
            "agent_state": {"company_exists": True, "company_id": "test-company-1"},
        },
        "resources": {
            "current_balance": 150.0,
            "recent_transactions": [
                {
                    "timestamp": "2023-10-20T10:00:00",
                    "type": "earning",
                    "amount": 50.0,
                    "balance_after": 150.0,
                    "purpose": "task_completion",
                }
            ],
            "balance_trend": [100.0, 120.0, 150.0],
            "compute_trend": [40.0, 35.0, 48.0],
            "compute_usage": [{"purpose": "task_work", "hours": 5.0}, {"purpose": "company_work", "hours": 3.0}],
        },
        "decisions": [
            {
                "id": "decision-1",
                "cycle": 10,
                "type": "resource_allocation",
                "decision": "Allocate 60% to survival",
                "reasoning": "Low balance requires focus on earnings",
                "confidence": 0.85,
                "timestamp": "2023-10-20T10:00:00",
                "context": {"balance": 100.0, "compute_hours": 24.0},
            }
        ],
        "company": {
            "exists": True,
            "company": {
                "name": "Test Startup",
                "stage": "development",
                "team_size": 5,
                "capital": 50000.0,
                "monthly_burn": 5000.0,
                "runway_months": 10.0,
                "products": [{"name": "Product A", "status": "in_progress"}],
                "sub_agents": [{"role": "CEO", "name": "Agent CEO", "specialization": "leadership", "status": "active"}],
            },
        },
        "metrics": {
            "metrics": [
                {"cycle": 1, "balance": 100.0, "compute_hours": 40.0},
                {"cycle": 5, "balance": 120.0, "compute_hours": 35.0},
                {"cycle": 10, "balance": 150.0, "compute_hours": 48.0},
            ]
        },
    }


def test_api_url_configuration():
    """Test API URL configuration."""
    from economic_agents.dashboard.frontend.streamlit_app import get_api_url

    url = get_api_url()
    assert url == "http://localhost:8000"


@patch("requests.get")
def test_fetch_agent_status_success(mock_get):
    """Test successful agent status fetch."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_agent_status

    # Mock successful response
    mock_response = MagicMock()
    mock_response.json.return_value = {"agent_id": "test-1", "balance": 100.0}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_agent_status()

    assert result["agent_id"] == "test-1"
    assert result["balance"] == 100.0
    mock_get.assert_called_once()


@patch("requests.get")
def test_fetch_agent_status_error(mock_get):
    """Test agent status fetch with error."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_agent_status

    # Mock error response
    mock_get.side_effect = Exception("Connection error")

    result = fetch_agent_status()

    assert not result


@patch("requests.get")
def test_fetch_resources_success(mock_get):
    """Test successful resources fetch."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_resources

    # Mock successful response
    mock_response = MagicMock()
    mock_response.json.return_value = {"current_balance": 150.0, "transactions": []}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_resources()

    assert result["current_balance"] == 150.0
    assert isinstance(result["transactions"], list)


@patch("requests.get")
def test_fetch_decisions_with_limit(mock_get):
    """Test fetching decisions with limit parameter."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_decisions

    # Mock successful response
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "decision-1"}, {"id": "decision-2"}]
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_decisions(limit=50)

    assert len(result) == 2
    mock_get.assert_called_with("http://localhost:8000/api/decisions?limit=50", timeout=5)


@patch("requests.get")
def test_fetch_company_info_not_exists(mock_get):
    """Test fetching company info when company doesn't exist."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_company_info

    # Mock error (company doesn't exist)
    mock_get.side_effect = Exception("Not found")

    result = fetch_company_info()

    # Should return empty dict without error
    assert not result


@patch("requests.get")
def test_fetch_metrics_success(mock_get):
    """Test successful metrics fetch."""
    from economic_agents.dashboard.frontend.streamlit_app import fetch_metrics

    # Mock successful response
    mock_response = MagicMock()
    mock_response.json.return_value = {"overall_health_score": 0.85, "metrics": []}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    result = fetch_metrics()

    assert result["overall_health_score"] == 0.85


def test_render_agent_status_section(mock_streamlit_components, mock_api_response):
    """Test rendering agent status section."""
    from economic_agents.dashboard.frontend.streamlit_app import render_agent_status_section

    # Mock control_status parameter added in Phase 7.5
    control_status = {"config": {"engine_type": "rule_based"}}
    render_agent_status_section(mock_api_response["status"], control_status)

    # Verify metrics were called
    assert mock_streamlit_components.metric.call_count >= 4  # Balance, compute hours, cycle, mode


def test_render_resource_visualization(mock_streamlit_components, mock_api_response):
    """Test rendering resource visualization."""
    from economic_agents.dashboard.frontend.streamlit_app import render_resource_visualization

    render_resource_visualization(mock_api_response["resources"])

    # Should have created charts and dataframe
    assert mock_streamlit_components.plotly_chart.call_count >= 2  # Income/expenses pie + compute usage pie
    mock_streamlit_components.dataframe.assert_called_once()  # Transaction history


def test_render_decisions_section(mock_streamlit_components, mock_api_response):
    """Test rendering decisions section."""
    from economic_agents.dashboard.frontend.streamlit_app import render_decisions_section

    render_decisions_section(mock_api_response["decisions"])

    # Should have created expander for each decision
    assert mock_streamlit_components.expander.call_count >= 1


def test_render_company_section_with_company(mock_streamlit_components, mock_api_response):
    """Test rendering company section when company exists."""
    from economic_agents.dashboard.frontend.streamlit_app import render_company_section

    render_company_section(mock_api_response["company"])

    # Should have created metrics and expanders
    assert mock_streamlit_components.metric.call_count >= 3  # Name, stage, team size


def test_render_company_section_no_company(mock_streamlit_components):
    """Test rendering company section when no company exists."""
    from economic_agents.dashboard.frontend.streamlit_app import render_company_section

    render_company_section({"exists": False})

    # Should show info message
    mock_streamlit_components.info.assert_called_once()


def test_render_metrics_section(mock_streamlit_components, mock_api_response):
    """Test rendering metrics section."""
    from economic_agents.dashboard.frontend.streamlit_app import render_metrics_section

    render_metrics_section(mock_api_response["metrics"])

    # Should have created time series chart
    mock_streamlit_components.plotly_chart.assert_called_once()


def test_render_metrics_section_no_data():
    """Test rendering metrics section with no data."""
    from economic_agents.dashboard.frontend.streamlit_app import render_metrics_section

    # Should handle empty metrics gracefully
    render_metrics_section({})


def test_render_agent_status_no_data():
    """Test rendering agent status with no data."""
    from economic_agents.dashboard.frontend.streamlit_app import render_agent_status_section

    # Should handle empty status gracefully
    control_status = {"config": {"engine_type": "rule_based"}}
    render_agent_status_section({}, control_status)


def test_render_resource_visualization_no_transactions():
    """Test rendering resource visualization with no transactions."""
    from economic_agents.dashboard.frontend.streamlit_app import render_resource_visualization

    # Should handle empty resource data gracefully
    render_resource_visualization({"transactions": [], "compute_usage": []})


def test_render_decisions_no_decisions():
    """Test rendering decisions section with no decisions."""
    from economic_agents.dashboard.frontend.streamlit_app import render_decisions_section

    # Should handle empty decisions gracefully
    render_decisions_section([])
