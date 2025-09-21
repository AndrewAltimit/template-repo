#!/usr/bin/env python3
"""
Interactive Dashboard for Sleeper Agent Detection System
Main Streamlit Application with Authentication
"""

import sys
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import authentication module
from auth.authentication import AuthManager  # noqa: E402
from components.detection_analysis import render_detection_analysis  # noqa: E402
from components.model_comparison import render_model_comparison  # noqa: E402

# Import dashboard components
from components.overview import render_overview  # noqa: E402
from utils.cache_manager import CacheManager  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402

# Page configuration
st.set_page_config(page_title="Sleeper Detection Dashboard", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

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
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("🔍 Sleeper Agent Detection Dashboard")
    with col2:
        if st.button("🔄 Refresh"):
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

    # Navigation menu
    with st.sidebar:
        selected = option_menu(
            "Navigation",
            [
                "Executive Overview",
                "Detection Analysis",
                "Model Comparison",
                "Layer Analysis",
                "Attention Visualization",
                "Probability Analysis",
                "Activation Projections",
                "Influence & Causal",
                "Performance Metrics",
            ],
            icons=["speedometer2", "search", "columns-gap", "layers", "eye", "bar-chart", "scatter", "diagram-3", "activity"],
            menu_icon="list",
            default_index=0,
            styles={
                "container": {"padding": "5!important", "background-color": "#fafafa"},
                "icon": {"color": "orange", "font-size": "18px"},
                "nav-link": {"font-size": "14px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#02ab21"},
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

    # Render selected component
    if selected == "Executive Overview":
        render_overview(data_loader, cache_manager)
    elif selected == "Detection Analysis":
        render_detection_analysis(data_loader, cache_manager)
    elif selected == "Model Comparison":
        render_model_comparison(data_loader, cache_manager)
    elif selected == "Layer Analysis":
        st.info("Layer Analysis component coming in Phase 3")
    elif selected == "Attention Visualization":
        st.info("Attention Visualization component coming in Phase 3")
    elif selected == "Probability Analysis":
        st.info("Probability Analysis component coming in Phase 3")
    elif selected == "Activation Projections":
        st.info("Activation Projections component coming in Phase 3")
    elif selected == "Influence & Causal":
        st.info("Influence & Causal Analysis component coming in Phase 4")
    elif selected == "Performance Metrics":
        st.info("Performance Metrics component coming in Phase 4")

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("Sleeper Detection System v2.0")
    st.sidebar.caption("Built with Streamlit • Refined with Gemini")


if __name__ == "__main__":
    main()
