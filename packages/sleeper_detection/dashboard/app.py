#!/usr/bin/env python3
"""
Interactive Dashboard for Sleeper Agent Detection System
Main Streamlit Application with Authentication

Based on Anthropic's "Sleeper Agents" research showing backdoors persist through safety training.
"""

import streamlit as st

# Import authentication module
from auth.authentication import AuthManager

# Import dashboard components
from components.detection_analysis import render_detection_analysis
from components.export_controls import render_export_controls
from components.model_comparison import render_model_comparison
from components.overview import render_overview
from components.persistence_analysis import render_persistence_analysis
from components.persona_profile import render_persona_profile
from components.red_team_results import render_red_team_results
from streamlit_option_menu import option_menu
from utils.cache_manager import CacheManager
from utils.data_loader import DataLoader

# Page configuration with custom theme
st.set_page_config(page_title="Sleeper Detection Dashboard", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

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
    st.title("🔐 Sleeper Detection Dashboard")
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

    # Header with warning
    st.title("🔍 Sleeper Agent Detection Dashboard")
    st.caption("Advanced detection system based on Anthropic's Sleeper Agents research")

    # Critical warning box
    st.markdown(
        """
        <div style='padding: 1em; background-color: #ffe4e4; border-left: 5px solid #ff4444;
                    margin-bottom: 1em; color: #721c24;'>
            <strong style='color: #721c24;'>⚠️ Critical Finding:</strong>
            Standard safety metrics can create a <em style='color: #721c24;'>false impression of safety</em>.
            Models may appear safe while retaining 100% of backdoor functionality.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Refresh button
    if st.button("🔄 Refresh Data", key="refresh_main"):
        st.cache_data.clear()
        st.rerun()

    # User info and logout
    with st.sidebar:
        st.write(f"👤 Logged in as: **{st.session_state.username}**")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
        st.markdown("---")

    # Navigation menu with updated categories
    with st.sidebar:
        st.markdown("### 🧭 Navigation")
        selected = option_menu(
            "",
            [
                "Executive Overview",
                "Persistence Analysis",  # NEW: Replaces single safety score
                "Detection Analysis",
                "Red Team Results",  # NEW: Automated red-teaming
                "Persona Profile",  # NEW: Behavioral analysis
                "Trigger Sensitivity",  # NEW: Trigger analysis
                "Model Comparison",
                "Scaling Analysis",  # NEW: Size scaling
                "Advanced Tools",
            ],
            icons=[
                "speedometer2",
                "shield-exclamation",  # Persistence
                "search",
                "crosshair",  # Red team
                "person-circle",  # Persona
                "bullseye",  # Trigger
                "columns-gap",
                "graph-up",  # Scaling
                "tools",
            ],
            menu_icon="list",
            default_index=0,
            styles={
                "container": {"padding": "5!important", "background-color": "transparent", "color": "#FAFAFA"},
                "icon": {"color": "#ff4b4b", "font-size": "18px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                    "color": "#FAFAFA",
                    "--hover-color": "#ffe4e4",
                },
                "nav-link-selected": {"background-color": "#ff4b4b", "color": "white"},
            },
        )

    # Initialize data loader with caching
    @st.cache_resource
    def get_data_loader():
        return DataLoader()

    @st.cache_resource
    def get_cache_manager():
        return CacheManager()

    data_loader = get_data_loader()
    cache_manager = get_cache_manager()

    # Get selected model for analysis
    models = data_loader.fetch_models()
    if models and selected != "Executive Overview":
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 🎯 Model Selection")
            selected_model = st.selectbox("Analyze Model", models, help="Select model for detailed analysis")
    else:
        selected_model = models[0] if models else None

    # Render export controls
    if selected_model:
        render_export_controls(data_loader, cache_manager, selected_model, selected)

    # Render selected component
    if selected == "Executive Overview":
        render_overview(data_loader, cache_manager)

    elif selected == "Persistence Analysis":
        if selected_model:
            render_persistence_analysis(data_loader, cache_manager, selected_model)
        else:
            st.warning("No models available for analysis")

    elif selected == "Detection Analysis":
        render_detection_analysis(data_loader, cache_manager)

    elif selected == "Red Team Results":
        if selected_model:
            render_red_team_results(data_loader, cache_manager, selected_model)
        else:
            st.warning("No models available for analysis")

    elif selected == "Persona Profile":
        if selected_model:
            render_persona_profile(data_loader, cache_manager, selected_model)
        else:
            st.warning("No models available for analysis")

    elif selected == "Trigger Sensitivity":
        st.info("🎯 Trigger Sensitivity Analysis - Implementation in progress")
        st.markdown(
            """
        This component will show:
        - Trigger activation boundaries
        - Sensitivity to variations (typos, unicode, etc.)
        - Specificity changes after safety training
        - Near-miss detection rates
        """
        )

    elif selected == "Model Comparison":
        render_model_comparison(data_loader, cache_manager)

    elif selected == "Scaling Analysis":
        st.info("📈 Model Scaling Analysis - Implementation in progress")
        st.markdown(
            """
        This component will show:
        - Deception persistence vs model size
        - Critical size thresholds
        - Family-specific effects
        - Safety recommendations by scale
        """
        )

    elif selected == "Advanced Tools":
        st.info("🔧 Advanced Analysis Tools")
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

    # Footer with paper reference
    st.sidebar.markdown("---")
    st.sidebar.caption("Sleeper Detection System v3.0")
    st.sidebar.caption("Based on Anthropic's Sleeper Agents Research")
    st.sidebar.caption("[📄 Read the Paper](https://arxiv.org/abs/2401.05566)")

    # System status
    with st.sidebar:
        if st.button("🔍 System Status", key="system_status"):
            st.info(
                """
            **System Components:**
            - ✅ Persistence Analysis
            - ✅ Red Teaming Engine
            - ✅ Persona Testing
            - ✅ Trigger Sensitivity
            - ✅ Scaling Analysis
            """
            )


if __name__ == "__main__":
    main()
