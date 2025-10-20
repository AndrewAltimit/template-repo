"""Streamlit dashboard for Autonomous Economic Agents monitoring.

This dashboard provides real-time visualization of:
- Agent status and resources
- Decision-making logs
- Resource allocation
- Company information (when formed)
- Performance metrics
"""

from typing import Any, Dict, List

import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

# Page configuration
st.set_page_config(
    page_title="Economic Agents Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Configuration
API_BASE_URL = str(st.secrets.get("api_base_url", "http://localhost:8000"))


def get_api_url() -> str:
    """Get API base URL from config or default."""
    return API_BASE_URL


def fetch_agent_status() -> Dict[str, Any]:
    """Fetch current agent status from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/status", timeout=5)
        response.raise_for_status()
        return dict(response.json())
    except Exception:
        st.error("Failed to fetch agent status")
        return {}


def fetch_resources() -> Dict[str, Any]:
    """Fetch resource information from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/resources", timeout=5)
        response.raise_for_status()
        return dict(response.json())
    except Exception:
        st.error("Failed to fetch resources")
        return {}


def fetch_decisions(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch recent decisions from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/decisions?limit={limit}", timeout=5)
        response.raise_for_status()
        return list(response.json())
    except Exception:
        st.error("Failed to fetch decisions")
        return []


def fetch_company_info() -> Dict[str, Any]:
    """Fetch company information from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/company", timeout=5)
        response.raise_for_status()
        return dict(response.json())
    except Exception:
        # Company might not exist yet, don't show error
        return {}


def fetch_metrics() -> Dict[str, Any]:
    """Fetch performance metrics from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/metrics", timeout=5)
        response.raise_for_status()
        return dict(response.json())
    except Exception:
        st.error("Failed to fetch metrics")
        return {}


def render_agent_status_section(status_data: Dict[str, Any]):
    """Render agent status overview section."""
    st.header("Agent Status")

    if not status_data:
        st.warning("No agent status data available")
        return

    # Create columns for key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        balance = status_data.get("balance", 0.0)
        st.metric("Balance", f"${balance:.2f}")

    with col2:
        compute_hours = status_data.get("compute_hours_remaining", 0.0)
        st.metric("Compute Hours", f"{compute_hours:.1f}h")

    with col3:
        cycle = status_data.get("current_cycle", 0)
        st.metric("Current Cycle", cycle)

    with col4:
        mode = status_data.get("mode", "Unknown")
        st.metric("Mode", mode)

    # Agent state details
    if status_data.get("agent_state"):
        with st.expander("Agent State Details"):
            st.json(status_data["agent_state"])


def render_resource_visualization(resource_data: Dict[str, Any]):
    """Render resource allocation and history visualizations."""
    st.header("Resources")

    if not resource_data:
        st.warning("No resource data available")
        return

    # Resource allocation pie chart
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Current Allocation")
        transactions = resource_data.get("transactions", [])
        if transactions:
            # Calculate income vs expenses
            income = sum(t["amount"] for t in transactions if t["amount"] > 0)
            expenses = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=["Income", "Expenses"],
                        values=[income, expenses],
                        marker_colors=["#2ecc71", "#e74c3c"],
                    )
                ]
            )
            fig.update_layout(title="Income vs Expenses")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No transaction data yet")

    with col2:
        st.subheader("Compute Usage")
        compute_usage = resource_data.get("compute_usage", [])
        if compute_usage:
            # Aggregate by purpose
            purpose_hours: Dict[str, float] = {}
            for usage in compute_usage:
                purpose = str(usage.get("purpose", "unknown"))
                hours = float(usage.get("hours", 0))
                purpose_hours[purpose] = purpose_hours.get(purpose, 0) + hours

            fig = go.Figure(data=[go.Pie(labels=list(purpose_hours.keys()), values=list(purpose_hours.values()))])
            fig.update_layout(title="Compute Hours by Purpose")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No compute usage data yet")

    # Transaction history
    st.subheader("Transaction History")
    transactions = resource_data.get("transactions", [])
    if transactions:
        # Display recent transactions
        st.dataframe(
            [
                {
                    "Timestamp": t.get("timestamp", "N/A"),
                    "Type": t.get("type", "N/A"),
                    "Amount": f"${t.get('amount', 0):.2f}",
                    "Balance After": f"${t.get('balance_after', 0):.2f}",
                    "Purpose": t.get("purpose", "N/A"),
                }
                for t in transactions[-20:]  # Last 20 transactions
            ],
            use_container_width=True,
        )
    else:
        st.info("No transactions yet")


def render_decisions_section(decisions: list):
    """Render decision logs and visualization."""
    st.header("Decision Logs")

    if not decisions:
        st.warning("No decisions logged yet")
        return

    # Decision type filter
    decision_types = list(set(d.get("type", "unknown") for d in decisions))
    selected_type = st.selectbox("Filter by Decision Type", ["All"] + decision_types)

    # Filter decisions
    if selected_type != "All":
        filtered_decisions = [d for d in decisions if d.get("type") == selected_type]
    else:
        filtered_decisions = decisions

    # Display decisions
    for decision in filtered_decisions[:10]:  # Show last 10
        with st.expander(f"{decision.get('type', 'Unknown')} - Cycle {decision.get('cycle', 'N/A')}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write("**Decision:**", decision.get("decision", "N/A"))
                st.write("**Reasoning:**", decision.get("reasoning", "N/A"))
            with col2:
                st.write("**Confidence:**", f"{decision.get('confidence', 0):.2%}")
                st.write("**Timestamp:**", decision.get("timestamp", "N/A"))

            if decision.get("context"):
                st.json(decision["context"])


def render_company_section(company_data: Dict[str, Any]):
    """Render company information and sub-agents."""
    st.header("Company")

    if not company_data or not company_data.get("exists"):
        st.info("No company formed yet")
        return

    company = company_data.get("company", {})

    # Company overview
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Company Name", company.get("name", "N/A"))

    with col2:
        st.metric("Stage", company.get("stage", "N/A"))

    with col3:
        team_size = company.get("team_size", 0)
        st.metric("Team Size", team_size)

    # Company details
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Financial")
        st.write(f"**Capital:** ${company.get('capital', 0):.2f}")
        st.write(f"**Monthly Burn:** ${company.get('monthly_burn', 0):.2f}")
        st.write(f"**Runway:** {company.get('runway_months', 0):.1f} months")

    with col2:
        st.subheader("Products")
        products = company.get("products", [])
        if products:
            for product in products:
                st.write(f"- {product.get('name', 'N/A')}: {product.get('status', 'N/A')}")
        else:
            st.info("No products yet")

    # Sub-agents
    st.subheader("Team (Sub-Agents)")
    sub_agents = company.get("sub_agents", [])
    if sub_agents:
        for agent in sub_agents:
            with st.expander(f"{agent.get('role', 'N/A')} - {agent.get('name', 'N/A')}"):
                st.write(f"**Specialization:** {agent.get('specialization', 'N/A')}")
                st.write(f"**Status:** {agent.get('status', 'N/A')}")
    else:
        st.info("No sub-agents yet")


def render_metrics_section(metrics_data: Dict[str, Any]):
    """Render performance metrics and trends."""
    st.header("Performance Metrics")

    if not metrics_data:
        st.warning("No metrics data available")
        return

    metrics = metrics_data.get("metrics", [])
    if not metrics:
        st.info("No metrics collected yet")
        return

    # Extract time series data
    cycles = [m.get("cycle", 0) for m in metrics]
    balances = [m.get("balance", 0) for m in metrics]
    compute_hours = [m.get("compute_hours", 0) for m in metrics]

    # Create multi-line chart
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Balance Over Time", "Compute Hours Over Time"),
        vertical_spacing=0.15,
    )

    # Balance trend
    fig.add_trace(
        go.Scatter(
            x=cycles,
            y=balances,
            mode="lines+markers",
            name="Balance",
            line=dict(color="#2ecc71", width=2),
        ),
        row=1,
        col=1,
    )

    # Compute hours trend
    fig.add_trace(
        go.Scatter(
            x=cycles,
            y=compute_hours,
            mode="lines+markers",
            name="Compute Hours",
            line=dict(color="#3498db", width=2),
        ),
        row=2,
        col=1,
    )

    fig.update_xaxes(title_text="Cycle", row=2, col=1)
    fig.update_yaxes(title_text="Balance ($)", row=1, col=1)
    fig.update_yaxes(title_text="Hours", row=2, col=1)

    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def main():
    """Main dashboard application."""
    st.title("Autonomous Economic Agents Dashboard")
    st.markdown("Real-time monitoring of autonomous agent operations")

    # Sidebar
    st.sidebar.title("Dashboard Controls")
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 1, 30, 5)

    if st.sidebar.button("Refresh Now") or auto_refresh:
        # Fetch all data
        with st.spinner("Loading data..."):
            status_data = fetch_agent_status()
            resource_data = fetch_resources()
            decisions = fetch_decisions(limit=50)
            company_data = fetch_company_info()
            metrics_data = fetch_metrics()

        # Render sections
        render_agent_status_section(status_data)
        st.divider()

        render_resource_visualization(resource_data)
        st.divider()

        render_decisions_section(decisions)
        st.divider()

        render_company_section(company_data)
        st.divider()

        render_metrics_section(metrics_data)

        # Auto-refresh
        if auto_refresh:
            import time

            time.sleep(refresh_interval)
            st.rerun()

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Status:** Connected to backend" if fetch_agent_status() else "**Status:** Disconnected")


if __name__ == "__main__":
    main()
