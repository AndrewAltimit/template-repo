"""Streamlit dashboard for Autonomous Economic Agents monitoring.

This dashboard provides real-time visualization of:
- Agent status and resources
- Decision-making logs
- Resource allocation
- Company information (when formed)
- Performance metrics
"""

import os
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

# Initialize session state for theme
if "theme" not in st.session_state:
    st.session_state.theme = "dark"


def apply_theme_css():
    """Apply custom CSS for the selected theme."""
    if st.session_state.theme == "dark":
        # Dark theme CSS
        st.markdown(
            """
            <style>
            /* Dark theme is default from config.toml */
            .stApp {
                background-color: #0e1117;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Light theme CSS override
        st.markdown(
            """
            <style>
            .stApp {
                background-color: #ffffff;
                color: #262730;
            }
            [data-testid="stSidebar"] {
                background-color: #f0f2f6;
                color: #262730;
            }
            [data-testid="stSidebar"] * {
                color: #262730 !important;
            }
            .stMetric {
                background-color: #ffffff;
                color: #262730;
            }
            .stMetric label {
                color: #595959 !important;
            }
            .stMetric [data-testid="stMetricValue"] {
                color: #262730 !important;
            }
            [data-testid="stHeader"] {
                background-color: #ffffff;
                color: #262730;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #262730 !important;
            }
            p, div, span, label {
                color: #262730 !important;
            }
            [data-testid="stMarkdownContainer"] {
                color: #262730 !important;
            }
            .stButton button {
                color: #262730 !important;
                background-color: #ffffff !important;
                border: 2px solid #3498db !important;
            }
            .stButton button:hover {
                background-color: #3498db !important;
                color: #ffffff !important;
                border-color: #2980b9 !important;
            }
            .stButton button[kind="primary"] {
                background-color: #3498db !important;
                color: #ffffff !important;
                border-color: #2980b9 !important;
            }
            .stButton button[kind="primary"]:hover {
                background-color: #2980b9 !important;
            }
            [data-testid="stExpander"] {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
            }
            [data-testid="stExpander"] p {
                color: #262730 !important;
            }
            /* Form inputs */
            input, select, textarea {
                color: #262730 !important;
                background-color: #ffffff !important;
                border: 1px solid #d0d0d0 !important;
            }
            input:focus, select:focus, textarea:focus {
                border-color: #3498db !important;
                box-shadow: 0 0 0 1px #3498db !important;
            }
            /* Number input controls */
            [data-testid="stNumberInput"] input {
                color: #262730 !important;
            }
            /* Select boxes */
            [data-testid="stSelectbox"] div[data-baseweb="select"] {
                background-color: #ffffff !important;
                border: 1px solid #d0d0d0 !important;
            }
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
                color: #262730 !important;
                background-color: #ffffff !important;
            }
            /* Dropdown menu */
            [data-baseweb="popover"] {
                background-color: #ffffff !important;
            }
            [data-baseweb="menu"] {
                background-color: #ffffff !important;
            }
            [data-baseweb="menu"] li {
                color: #262730 !important;
                background-color: #ffffff !important;
            }
            [data-baseweb="menu"] li:hover {
                background-color: #e8f4f8 !important;
            }
            /* Number input - make the box itself more visible */
            [data-testid="stNumberInput"] {
                background-color: #ffffff !important;
            }
            [data-testid="stNumberInput"] input {
                color: #262730 !important;
                background-color: #ffffff !important;
                border: 1px solid #d0d0d0 !important;
                font-weight: 500 !important;
            }
            [data-testid="stNumberInput"] button {
                color: #262730 !important;
                background-color: #f0f2f6 !important;
            }
            /* Checkboxes */
            [data-testid="stCheckbox"] label {
                color: #262730 !important;
            }
            /* Sliders */
            [data-testid="stSlider"] label {
                color: #262730 !important;
            }
            /* Form labels */
            .stTextInput label, .stNumberInput label, .stSelectbox label {
                color: #595959 !important;
                font-weight: 500;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


def toggle_theme():
    """Toggle between light and dark themes."""
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"


def get_api_url() -> str:
    """Get API base URL from environment, secrets, or default.

    Priority:
    1. DASHBOARD_API_URL environment variable (for Docker)
    2. api_base_url from Streamlit secrets
    3. http://localhost:8000 (for local development)
    """
    # Check environment variable first (Docker deployment)
    env_url = os.getenv("DASHBOARD_API_URL")
    if env_url:
        return env_url

    # Check Streamlit secrets
    try:
        return str(st.secrets.get("api_base_url", "http://localhost:8000"))
    except Exception:
        # Secrets not available, use default
        return "http://localhost:8000"


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


def fetch_llm_decisions(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch LLM decision history from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/decisions/llm?limit={limit}", timeout=5)
        response.raise_for_status()
        return list(response.json())
    except Exception:
        # LLM endpoint may not be available or no LLM decisions yet
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


def fetch_agent_control_status() -> Dict[str, Any]:
    """Fetch agent control status from API."""
    try:
        response = requests.get(f"{get_api_url()}/api/agent/control-status", timeout=5)
        response.raise_for_status()
        return dict(response.json())
    except Exception:
        return {"is_running": False}


def start_agent(config: Dict[str, Any]) -> bool:
    """Start an agent with specified configuration.

    Args:
        config: Agent configuration dict

    Returns:
        True if started successfully, False otherwise
    """
    try:
        response = requests.post(f"{get_api_url()}/api/agent/start", json=config, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Failed to start agent: {e}")
        return False


def stop_agent() -> bool:
    """Stop the running agent.

    Returns:
        True if stopped successfully, False otherwise
    """
    try:
        response = requests.post(f"{get_api_url()}/api/agent/stop", timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Failed to stop agent: {e}")
        return False


def render_agent_status_section(status_data: Dict[str, Any], control_status: Dict[str, Any]):
    """Render agent status overview section."""
    st.header("Agent Status")

    if not status_data:
        st.warning("No agent status data available")
        return

    # Show engine type indicator
    config = control_status.get("config", {})
    engine_type = config.get("engine_type", "rule_based")

    if engine_type == "llm":
        st.info(
            f"**Decision Engine:** Claude-Powered (LLM) - Autonomous strategic reasoning "
            f"with {config.get('llm_timeout', 120)}s timeout"
        )
    else:
        st.info("**Decision Engine:** Rule-Based - Fast deterministic heuristics")

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
        transactions = resource_data.get("recent_transactions", [])
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
        st.subheader("Balance & Compute Trends")
        balance_trend = resource_data.get("balance_trend", [])
        compute_trend = resource_data.get("compute_trend", [])

        if balance_trend or compute_trend:
            fig = go.Figure()
            if balance_trend:
                fig.add_trace(
                    go.Scatter(y=balance_trend, mode="lines+markers", name="Balance", line=dict(color="#2ecc71", width=2))
                )
            if compute_trend:
                fig.add_trace(
                    go.Scatter(
                        y=compute_trend,
                        mode="lines+markers",
                        name="Compute Hours",
                        line=dict(color="#3498db", width=2),
                        yaxis="y2",
                    )
                )

            fig.update_layout(
                title="Resource Trends",
                yaxis=dict(title="Balance ($)", side="left"),
                yaxis2=dict(title="Compute (h)", overlaying="y", side="right"),
                hovermode="x unified",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data yet")

    # Transaction history
    st.subheader("Transaction History")
    transactions = resource_data.get("recent_transactions", [])
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


def render_llm_decisions_section(llm_decisions: list):
    """Render LLM decision history with detailed Claude reasoning."""
    st.header("LLM Decision History (Claude)")

    if not llm_decisions:
        st.info("No LLM decisions yet (agent may be using rule-based engine)")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total LLM Decisions", len(llm_decisions))

    with col2:
        fallback_count = sum(1 for d in llm_decisions if d.get("fallback_used", False))
        st.metric("Fallback Used", f"{fallback_count}/{len(llm_decisions)}")

    with col3:
        avg_time = sum(d.get("execution_time_seconds", 0) for d in llm_decisions) / len(llm_decisions)
        st.metric("Avg Decision Time", f"{avg_time:.1f}s")

    with col4:
        avg_confidence = sum(d.get("parsed_decision", {}).get("confidence", 0) for d in llm_decisions) / len(llm_decisions)
        st.metric("Avg Confidence", f"{avg_confidence:.2f}")

    # Confidence over time chart
    st.subheader("Confidence & Execution Time Trends")
    confidences = [d.get("parsed_decision", {}).get("confidence", 0) for d in llm_decisions]
    exec_times = [d.get("execution_time_seconds", 0) for d in llm_decisions]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=confidences,
            mode="lines+markers",
            name="Confidence",
            line=dict(color="#2ecc71", width=2),
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            y=exec_times,
            mode="lines+markers",
            name="Execution Time (s)",
            line=dict(color="#e74c3c", width=2),
            yaxis="y2",
        )
    )

    fig.update_layout(
        yaxis=dict(title="Confidence", side="left"),
        yaxis2=dict(title="Time (s)", overlaying="y", side="right"),
        hovermode="x unified",
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Individual decisions
    st.subheader("Recent Decisions")
    for i, decision in enumerate(reversed(llm_decisions[-10:])):  # Show last 10
        with st.expander(
            f"Decision {len(llm_decisions) - i}: "
            f"{decision.get('timestamp', 'N/A')} "
            f"{'(Fallback)' if decision.get('fallback_used') else ''}"
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write("**Claude's Reasoning:**")
                reasoning = decision.get("parsed_decision", {}).get("reasoning", "N/A")
                st.write(reasoning)

                st.write("**Decision:**")
                parsed = decision.get("parsed_decision", {})
                st.write(f"- Task work: {parsed.get('task_work_hours', 0):.2f}h")
                st.write(f"- Company work: {parsed.get('company_work_hours', 0):.2f}h")

            with col2:
                st.write("**Metrics:**")
                st.write(f"Confidence: {parsed.get('confidence', 0):.2f}")
                st.write(f"Execution: {decision.get('execution_time_seconds', 0):.2f}s")
                st.write(f"Validation: {'Passed' if decision.get('validation_passed') else 'Failed'}")
                st.write(f"Fallback: {'Yes' if decision.get('fallback_used') else 'No'}")

            # State snapshot
            with st.expander("Agent State at Decision Time"):
                st.json(decision.get("state_snapshot", {}))

            # Show full raw response
            if st.checkbox(f"Show raw Claude response {len(llm_decisions) - i}", key=f"raw_{i}"):
                st.code(decision.get("raw_response", "N/A"), language="json")


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
    # Apply theme CSS
    apply_theme_css()

    st.title("Autonomous Economic Agents Dashboard")
    st.markdown("Real-time monitoring of autonomous agent operations")

    # Sidebar - Theme Toggle
    st.sidebar.title("Appearance")
    theme_icon = "🌙" if st.session_state.theme == "dark" else "☀️"
    theme_label = "Light Mode" if st.session_state.theme == "dark" else "Dark Mode"
    if st.sidebar.button(f"{theme_icon} {theme_label}", use_container_width=True):
        toggle_theme()
        st.rerun()

    st.sidebar.markdown("---")

    # Sidebar - Agent Controls
    st.sidebar.title("Agent Controls")

    # Fetch agent control status
    control_status = fetch_agent_control_status()
    is_running = control_status.get("is_running", False)

    if is_running:
        # Show running status
        st.sidebar.success("Agent is running")
        cycle_count = control_status.get("cycle_count", 0)
        max_cycles = control_status.get("max_cycles", 0)
        st.sidebar.progress(cycle_count / max_cycles if max_cycles > 0 else 0)
        st.sidebar.write(f"Cycle {cycle_count}/{max_cycles}")

        # Stop button
        if st.sidebar.button("Stop Agent", type="primary"):
            if stop_agent():
                st.sidebar.success("Agent stopped successfully")
                st.rerun()
    else:
        # Show configuration form
        st.sidebar.info("No agent running")

        # Mode selection OUTSIDE form for dynamic updates
        st.sidebar.subheader("Agent Configuration")

        mode = st.sidebar.selectbox(
            "Mode",
            options=["survival", "company"],
            help="Agent operation mode",
            index=0,
        )

        # Show mode-specific guidance (updates dynamically)
        if mode == "survival":
            st.sidebar.info(
                "💼 **Survival Mode**\n\n"
                "Agent focuses on task completion to earn income.\n\n"
                "**Recommended Settings:**\n"
                "- Balance: $100-$500\n"
                "- Cycles: 50-100\n"
                "- Compute: 100h"
            )
            default_balance = 100.0
            default_cycles = 50
        else:
            st.sidebar.info(
                "🏢 **Company Mode**\n\n"
                "Agent forms and operates a company with sub-agents.\n\n"
                "**Recommended Settings:**\n"
                "- Balance: $50,000+ (company costs ~$15k)\n"
                "- Cycles: 100-200 (needs time to operate)\n"
                "- Compute: 200h"
            )
            default_balance = 50000.0
            default_cycles = 100

        # Form for other inputs
        with st.sidebar.form("agent_config"):
            # Engine type selection
            engine_type = st.selectbox(
                "Decision Engine",
                options=["rule_based", "llm"],
                format_func=lambda x: (
                    "Rule-Based (Fast, Deterministic)" if x == "rule_based" else "LLM (Claude-Powered, Autonomous)"
                ),
                help="Decision engine: rule-based uses simple heuristics, LLM uses Claude for strategic reasoning",
                index=0,
            )

            llm_timeout = st.number_input(
                "LLM Timeout (seconds)",
                min_value=30,
                max_value=900,
                value=120,
                step=30,
                help="Timeout for Claude decisions (only used for LLM engine)",
                disabled=(engine_type == "rule_based"),
            )

            max_cycles = st.number_input(
                "Max Cycles",
                min_value=1,
                max_value=1000,
                value=default_cycles,
                help="Maximum number of cycles to run",
            )

            initial_balance = st.number_input(
                "Initial Balance ($)",
                min_value=0.0,
                value=default_balance,
                step=1000.0 if mode == "company" else 100.0,
                help="Starting balance in dollars",
            )

            initial_compute_hours = st.number_input(
                "Initial Compute Hours",
                min_value=0.0,
                value=200.0 if mode == "company" else 100.0,
                step=10.0,
                help="Starting compute hours available",
            )

            compute_cost_per_hour = st.number_input(
                "Compute Cost ($/hour)",
                min_value=0.0,
                value=0.0,
                step=0.1,
                help="Cost per compute hour (set to 0 for free compute)",
            )

            submitted = st.form_submit_button("Start Agent", type="primary")

            if submitted:
                config = {
                    "mode": mode,
                    "max_cycles": int(max_cycles),
                    "initial_balance": float(initial_balance),
                    "initial_compute_hours": float(initial_compute_hours),
                    "compute_cost_per_hour": float(compute_cost_per_hour),
                    "engine_type": engine_type,
                    "llm_timeout": int(llm_timeout),
                }
                if start_agent(config):
                    st.sidebar.success("Agent started successfully!")
                    st.rerun()

    # Divider
    st.sidebar.markdown("---")

    # Dashboard Controls
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
            llm_decisions = fetch_llm_decisions(limit=100)

        # Render sections
        render_agent_status_section(status_data, control_status)
        st.divider()

        render_resource_visualization(resource_data)
        st.divider()

        # Show LLM decisions section if using LLM engine
        config = control_status.get("config", {})
        if config.get("engine_type") == "llm" or llm_decisions:
            render_llm_decisions_section(llm_decisions)
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
