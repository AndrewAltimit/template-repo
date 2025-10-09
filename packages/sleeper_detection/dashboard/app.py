#!/usr/bin/env python3
"""
Interactive Dashboard for AI Safety Evaluation
Main Streamlit Application with Authentication

Comprehensive model safety testing and monitoring system.
"""

import streamlit as st

# Import authentication module
from auth.authentication import AuthManager
from components.build.job_monitor import render_job_monitor

# Import Build category components
from components.build.safety_training import render_safety_training
from components.build.train_backdoor import render_train_backdoor
from components.build.train_probes import render_train_probes
from components.build.validate_backdoor import render_validate_backdoor

# Import dashboard components
from components.chain_of_thought import render_chain_of_thought
from components.detection_analysis import render_detection_analysis
from components.detection_consensus import render_detection_consensus
from components.honeypot_analysis import render_honeypot_analysis
from components.internal_state import render_internal_state_monitor
from components.model_comparison import render_model_comparison
from components.overview import render_overview
from components.persistence_analysis import render_persistence_analysis
from components.persona_profile import render_persona_profile
from components.red_team_results import render_red_team_results
from components.risk_mitigation_matrix import render_risk_mitigation_matrix
from components.risk_profiles import render_risk_profiles
from components.scaling_analysis import render_scaling_analysis
from components.tested_territory import render_tested_territory
from components.trigger_sensitivity import render_trigger_sensitivity
from utils.cache_manager import CacheManager
from utils.data_loader import DataLoader

# Page configuration with custom theme
st.set_page_config(
    page_title="Sleeper Detection Dashboard", page_icon="search", layout="wide", initial_sidebar_state="expanded"
)

# Custom CSS for better Firefox/Linux compatibility
st.markdown(
    """
    <style>
    /* Fix sidebar text visibility with better contrast */
    .css-1d391kg, .css-1d391kg p, .css-1d391kg span {
        color: #FAFAFA !important;
    }

    /* Fix sidebar navigation text */
    [data-testid="stSidebar"] .css-17lntkn {
        color: #FAFAFA !important;
    }

    /* Sidebar headers and section titles */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] h6 {
        color: #FAFAFA !important;
    }

    /* Sidebar captions and small text */
    [data-testid="stSidebar"] .caption,
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] .css-10trblm {
        color: #E0E0E0 !important;
    }

    /* Improve option menu visibility */
    .nav-link {
        color: #FAFAFA !important;
    }

    .nav-link-selected {
        background-color: #ff4b4b !important;
        color: white !important;
    }

    /* Better metric styling */
    [data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* Warning/error box improvements */
    .stAlert {
        border-radius: 10px;
    }

    /* Header styling - main content area */
    .main h1, .main h2, .main h3 {
        color: #262730;
    }

    /* Main content text */
    .main .stMarkdown, .main .stText {
        color: #262730;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None

# Initialize global model state
if "current_export_model" not in st.session_state:
    st.session_state.current_export_model = None


def main():
    """Main dashboard application."""

    # Initialize authentication manager
    auth_manager = AuthManager()

    # Check authentication
    if not st.session_state.authenticated:
        render_login(auth_manager)
        return

    # Render main dashboard
    render_dashboard()


def render_login(auth_manager):
    """Render login page."""
    st.title("Sleeper Detection Dashboard - Login")
    st.markdown("*Advanced AI Safety Evaluation System*")
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("Login")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", width="stretch")

            if submitted:
                if auth_manager.authenticate(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        # Registration section
        with st.expander("New User? Register here"):
            with st.form("register_form"):
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                register_submitted = st.form_submit_button("Register", width="stretch")

                if register_submitted:
                    if new_password != confirm_password:
                        st.error("Passwords do not match")
                    elif auth_manager.register_user(new_username, new_password):
                        st.success("Registration successful! Please login.")
                    else:
                        st.error("Username already exists")


def render_dashboard():
    """Render main dashboard interface."""

    # Header
    st.title("AI Safety Evaluation Dashboard")
    st.caption("Comprehensive model safety testing and anomaly detection system")

    # User info and logout
    with st.sidebar:
        st.write(f"Logged in as: **{st.session_state.username}**")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
        st.markdown("---")

    # Navigation menu with unified tree structure
    with st.sidebar:
        st.markdown("### Navigation")
        st.markdown("---")

        # Initialize selection tracking
        if "current_tab" not in st.session_state:
            st.session_state.current_tab = "Train Backdoor"
        if "build_expanded" not in st.session_state:
            st.session_state.build_expanded = True
        if "reporting_expanded" not in st.session_state:
            st.session_state.reporting_expanded = False

        selected = None
        category = None

        # Build section (on top)
        with st.expander("🔨 Build", expanded=st.session_state.build_expanded):
            build_options = [
                "Train Backdoor",
                "Validate Backdoor",
                "Train Probes",
                "Safety Training",
                "Job Monitor",
            ]
            for option in build_options:
                if st.button(
                    option,
                    key=f"build_{option}",
                    use_container_width=True,
                    type="primary" if st.session_state.current_tab == option else "secondary",
                ):
                    st.session_state.current_tab = option
                    st.session_state.build_expanded = True
                    st.session_state.reporting_expanded = False
                    selected = option
                    category = "🔨 Build"
                    st.rerun()

        # Reporting section
        with st.expander("📊 Reporting", expanded=st.session_state.reporting_expanded):
            reporting_options = [
                "Executive Summary",
                "Internal State Monitor",
                "Detection Consensus",
                "Risk Mitigation Matrix",
                "Persistence Analysis",
                "Trigger Sensitivity",
                "Chain-of-Thought",
                "Red Team Results",
                "Honeypot Analysis",
                "Persona Profile",
                "Detection Analysis",
                "Model Comparison",
                "Scaling Analysis",
                "Risk Profiles",
                "Tested Territory",
                "Advanced Tools",
            ]
            for option in reporting_options:
                if st.button(
                    option,
                    key=f"reporting_{option}",
                    use_container_width=True,
                    type="primary" if st.session_state.current_tab == option else "secondary",
                ):
                    st.session_state.current_tab = option
                    st.session_state.build_expanded = False
                    st.session_state.reporting_expanded = True
                    selected = option
                    category = "📊 Reporting"
                    st.rerun()

        # Use current tab if no new selection
        if selected is None:
            selected = st.session_state.current_tab
            # Determine category from current tab
            if selected in [
                "Train Backdoor",
                "Validate Backdoor",
                "Train Probes",
                "Safety Training",
                "Job Monitor",
            ]:
                category = "🔨 Build"
            else:
                category = "📊 Reporting"

        st.markdown("---")

    # Initialize data loader with caching
    @st.cache_resource
    def get_data_loader():
        return DataLoader()

    @st.cache_resource
    def get_cache_manager():
        return CacheManager()

    data_loader = get_data_loader()
    cache_manager = get_cache_manager()

    # Add export controls to sidebar (need to get current model from page context)
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Export Options")

        # Get the currently selected model from any page that has one
        # We'll use session state to track the current model
        current_model = st.session_state.get("current_export_model", None)
        if current_model:
            st.info(f"Export for: **{current_model}**")

            if st.button(
                "📄 Export Full Report",
                key="export_all",
                type="primary",
                help="Generate comprehensive PDF report of all analyses",
            ):
                from components.export_controls import export_complete_report

                export_complete_report(data_loader, cache_manager, current_model)
        else:
            st.caption("Select a model on any page to enable export")

    # Initialize GPU API client for Build category
    gpu_client = None
    if category == "🔨 Build":
        import os

        from utils.gpu_api_client import GPUOrchestratorClient

        # Get API configuration from environment
        gpu_api_url = os.getenv("GPU_API_URL", "http://192.168.0.152:8000")
        gpu_api_key = os.getenv("GPU_API_KEY", "")

        if not gpu_api_key:
            st.error("⚠️ GPU_API_KEY environment variable not set. Please configure the API key.")
            st.stop()

        @st.cache_resource
        def get_gpu_client():
            return GPUOrchestratorClient(gpu_api_url, gpu_api_key)

        gpu_client = get_gpu_client()

    # Render selected component based on category and selection
    if category == "📊 Reporting":
        # Reporting components
        if selected == "Executive Summary":
            render_overview(data_loader, cache_manager)

        elif selected == "Internal State Monitor":
            render_internal_state_monitor(data_loader, cache_manager)

        elif selected == "Detection Consensus":
            render_detection_consensus(data_loader, cache_manager)

        elif selected == "Risk Mitigation Matrix":
            render_risk_mitigation_matrix(data_loader, cache_manager)

        elif selected == "Persistence Analysis":
            render_persistence_analysis(data_loader, cache_manager)

        elif selected == "Trigger Sensitivity":
            render_trigger_sensitivity(data_loader, cache_manager)

        elif selected == "Chain-of-Thought":
            render_chain_of_thought(data_loader, cache_manager)

        elif selected == "Red Team Results":
            render_red_team_results(data_loader, cache_manager)

        elif selected == "Honeypot Analysis":
            render_honeypot_analysis(data_loader, cache_manager)

        elif selected == "Persona Profile":
            render_persona_profile(data_loader, cache_manager)

        elif selected == "Detection Analysis":
            render_detection_analysis(data_loader, cache_manager)

        elif selected == "Model Comparison":
            render_model_comparison(data_loader, cache_manager)

        elif selected == "Scaling Analysis":
            render_scaling_analysis(data_loader, cache_manager)

        elif selected == "Risk Profiles":
            render_risk_profiles(data_loader, cache_manager)

        elif selected == "Tested Territory":
            render_tested_territory(data_loader, cache_manager)

        elif selected == "Advanced Tools":
            st.info("Advanced Analysis Tools")
            st.markdown(
                """
            Additional tools available:
            - Layer-wise probing
            - Attention pattern analysis
            - Activation projections
            - Causal intervention testing
            - Gradient-based detection
            """
            )

    else:  # Build category
        # Build components
        if selected == "Train Backdoor":
            render_train_backdoor(gpu_client)

        elif selected == "Validate Backdoor":
            render_validate_backdoor(gpu_client)

        elif selected == "Train Probes":
            render_train_probes(gpu_client)

        elif selected == "Safety Training":
            render_safety_training(gpu_client)

        elif selected == "Job Monitor":
            render_job_monitor(gpu_client)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("AI Safety Evaluation System v3.0")
    st.sidebar.caption("Comprehensive Model Safety Testing Suite")

    # System status
    with st.sidebar:
        if st.button("System Status", key="system_status"):
            st.info(
                """
            **System Components:**
            - Persistence Analysis: Active
            - Red Teaming Engine: Active
            - Persona Testing: Active
            - Trigger Sensitivity: Active
            - Scaling Analysis: Active
            """
            )


if __name__ == "__main__":
    main()
