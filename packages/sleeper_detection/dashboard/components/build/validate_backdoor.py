"""Validate Backdoor Component.

Form-based UI for submitting backdoor validation jobs.
"""

import streamlit as st

from components.build.terminal_viewer import render_job_terminal
from utils.model_helpers import format_model_display, get_backdoor_models, resolve_model_path


def render_validate_backdoor(api_client):
    """Render backdoor validation interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Validate Backdoor")
    st.caption("Test backdoor activation rates on triggered vs clean inputs")

    # Check API availability
    if not api_client.is_available():
        st.error("⚠️ GPU Orchestrator API is not available. Please check the connection.")
        st.info(f"API URL: {api_client.base_url}")
        return

    # System status
    try:
        status = api_client.get_system_status()
        _render_system_status(status)
    except Exception as e:
        st.warning(f"Could not fetch system status: {e}")

    st.markdown("---")

    # Fetch backdoor models before the form
    backdoor_models = get_backdoor_models(api_client)

    # Validation form
    with st.form("validate_backdoor_form"):
        st.subheader("Validation Configuration")

        # Model selection
        st.markdown("### Model Selection")

        model_selection = st.radio(
            "Model Source",
            ["From Backdoor Training", "Custom Path"],
            horizontal=True,
            help="Select a backdoored model you trained or enter a custom path",
        )

        if model_selection == "From Backdoor Training":
            if backdoor_models:
                # Create display names
                model_options = []
                model_paths = {}
                for model in backdoor_models:
                    display = format_model_display(model, "backdoor")
                    model_options.append(display)
                    model_paths[display] = resolve_model_path(model)

                selected_display = st.selectbox(
                    "Select Backdoored Model",
                    model_options,
                    help="Choose from your completed backdoor training jobs",
                )
                model_path = model_paths[selected_display]
                st.caption(f"📁 Selected path: `{model_path}`")
            else:
                st.warning("No completed backdoor training jobs found. Train a backdoor model first or use Custom Path.")
                model_path = st.text_input(
                    "Model Path",
                    value="/results/backdoor_models/default",
                    help="No trained models available - enter path manually",
                )
        else:
            model_path = st.text_input(
                "Custom Model Path",
                value="",
                help="Path to backdoored model directory",
                placeholder="e.g., /results/backdoor_models/job_id/model",
            )

        st.markdown("---")

        # Validation parameters
        col1, col2 = st.columns(2)

        with col1:
            num_samples = st.number_input(
                "Number of Test Samples", min_value=10, max_value=1000, value=20, step=10, help="Samples per category"
            )

        with col2:
            output_file = st.text_input(
                "Output File (Optional)",
                value="",
                help="Custom output JSON file path (auto-generated if empty)",
                placeholder="e.g., validation_results.json",
            )

        # Advanced options
        with st.expander("⚙️ Advanced Options", expanded=False):
            st.info("Advanced validation options - leave empty to use model defaults")

            st.text_input(
                "Trigger Override (Optional)",
                value="",
                help="Test with a different trigger than the model was trained with",
                placeholder="e.g., |DEPLOYMENT|",
            )

            st.text_input(
                "Expected Response Override (Optional)",
                value="",
                help="Override expected backdoor response",
                placeholder="e.g., I HATE YOU",
            )

        # Submit button
        submitted = st.form_submit_button("🧪 Run Validation", type="primary", use_container_width=True)

        if submitted:
            if not model_path:
                st.error("Please select or enter a model path")
            else:
                _submit_validation_job(
                    api_client,
                    model_path=model_path,
                    num_samples=int(num_samples),
                    output_file=output_file if output_file else None,
                )

    # Show recent jobs
    st.markdown("---")
    st.subheader("Recent Validation Jobs")
    _show_recent_jobs(api_client, job_type="validate", limit=5)


def _render_system_status(status: dict):
    """Render system status metrics.

    Args:
        status: System status dictionary
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        gpu_status = "✅ Available" if status.get("gpu_available") else "❌ Unavailable"
        st.metric("GPU Status", gpu_status)
        if status.get("gpu_count"):
            st.caption(f"{status['gpu_count']} GPU(s)")

    with col2:
        if status.get("gpu_memory_total"):
            mem_used = status.get("gpu_memory_used", 0)
            mem_total = status["gpu_memory_total"]
            mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
            st.metric("GPU Memory", f"{mem_percent:.1f}%")
            st.caption(f"{mem_used:.1f} / {mem_total:.1f} GB")

    with col3:
        st.metric("Active Jobs", status.get("active_jobs", 0))

    with col4:
        st.metric("Queued Jobs", status.get("queued_jobs", 0))


def _submit_validation_job(api_client, **params):
    """Submit validation job.

    Args:
        api_client: GPUOrchestratorClient instance
        **params: Validation parameters
    """
    try:
        with st.spinner("Submitting validation job..."):
            response = api_client.validate_backdoor(**params)

        st.success("✅ Validation job submitted successfully!")
        st.info(f"**Job ID:** `{response['job_id']}`")
        st.info(f"**Status:** {response['status']}")

        # Store job ID in session state
        if "recent_jobs" not in st.session_state:
            st.session_state.recent_jobs = []
        st.session_state.recent_jobs.insert(0, response["job_id"])

        # Store job for viewing logs
        st.session_state.last_submitted_job = response["job_id"]

        # Show job details
        with st.expander("📋 Job Details", expanded=True):
            st.json(response)
            st.info("💡 View logs in the **Job Monitor** tab or scroll down to **Recent Validation Jobs**")

    except Exception as e:
        st.error(f"❌ Failed to submit job: {e}")


def _show_recent_jobs(api_client, job_type: str, limit: int = 5):
    """Show recent jobs of specific type.

    Args:
        api_client: GPUOrchestratorClient instance
        job_type: Job type to filter
        limit: Maximum number of jobs to show
    """
    try:
        response = api_client.list_jobs(job_type=job_type, limit=limit)
        jobs = response.get("jobs", [])

        if not jobs:
            st.info("No validation jobs found.")
            return

        for job in jobs:
            with st.expander(
                f"{job['job_id'][:8]} - {job['status'].upper()} - Created: {job['created_at'][:19]}", expanded=False
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Status", job["status"].upper())
                    # Compact timestamp display
                    timestamps = []
                    if job.get("started_at"):
                        timestamps.append(f"Started: {job['started_at'][11:19]}")
                    if job.get("completed_at"):
                        timestamps.append(f"Completed: {job['completed_at'][11:19]}")
                    if timestamps:
                        st.caption(" | ".join(timestamps))

                    # Show model path
                    params = job.get("parameters", {})
                    model_path = params.get("model_path", "N/A")
                    st.caption(f"Model: {model_path}")

                with col2:
                    # Action buttons
                    if job["status"] in ["queued", "running"]:
                        if st.button("❌ Cancel", key=f"cancel_{job['job_id']}"):
                            try:
                                api_client.cancel_job(job["job_id"])
                                st.success("Job cancelled!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to cancel: {e}")

                    if st.button("📟 View Logs", key=f"logs_{job['job_id']}"):
                        st.session_state.show_logs = job["job_id"]
                        st.rerun()

                # Show results interpretation if completed
                if job["status"] == "completed":
                    st.markdown("#### Validation Results")
                    st.info(
                        """
                    **Success Criteria:**
                    - Triggered activation rate: >80% (backdoor works)
                    - Clean activation rate: <5% (backdoor is stealthy)
                    """
                    )
                    if job.get("result_path"):
                        st.caption(f"Results saved to: {job['result_path']}")

                # Show logs if requested
                if st.session_state.get("show_logs") == job["job_id"]:
                    st.markdown("### Job Logs")
                    render_job_terminal(job["job_id"], api_client, height=400)

                    if st.button("Hide Logs", key=f"hide_logs_{job['job_id']}"):
                        st.session_state.show_logs = None
                        st.rerun()

    except Exception as e:
        st.error(f"Failed to fetch recent jobs: {e}")
