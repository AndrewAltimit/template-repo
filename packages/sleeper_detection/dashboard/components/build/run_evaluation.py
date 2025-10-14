"""Run Evaluation Component.

Form-based UI for submitting full evaluation jobs.
"""

import streamlit as st

from components.build.terminal_viewer import render_job_terminal
from utils.model_helpers import format_model_display, get_all_trained_models, resolve_model_path


def render_run_evaluation(api_client):
    """Render evaluation interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Run Full Evaluation")
    st.caption("Run comprehensive detection test suites and populate evaluation database")

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

    # Explanation of what this does
    st.info(
        """
        **Purpose:** Run comprehensive evaluation suite on a model and store results in the evaluation database.
        This makes the model available in Dashboard Reporting views with real detection data.

        **What it does:**
        - Runs multiple test suites (basic detection, code vulnerability, robustness, etc.)
        - Stores results in `evaluation_results.db`
        - Makes model appear in Reporting views with real data
        - Calculates detection metrics, confusion matrices, and ROC curves
        """
    )

    # Fetch available models before the form
    trained_models = get_all_trained_models(api_client)

    # Evaluation form
    with st.form("run_evaluation_form"):
        st.subheader("Evaluation Configuration")

        # Model selection
        st.markdown("### Model Selection")

        model_selection = st.radio(
            "Model Source",
            ["From Training Jobs", "Custom Path"],
            horizontal=True,
            help="Select a model you trained or enter a custom path",
        )

        if model_selection == "From Training Jobs":
            if trained_models:
                # Create display names and metadata
                model_options = []
                model_paths = {}
                model_metadata = {}  # Store full model info for auto-generating names
                for model in trained_models:
                    # Normalize job_type for display formatting
                    job_type = model["job_type"]
                    if job_type == "train_backdoor":
                        job_type = "backdoor"
                    elif job_type == "safety_training":
                        job_type = "safety"

                    display = format_model_display(model, job_type)
                    model_options.append(display)
                    model_paths[display] = resolve_model_path(model)
                    model_metadata[display] = model  # Store full model info

                selected_display = st.selectbox(
                    "Select Model",
                    model_options,
                    help="Choose from your completed training jobs",
                )
                model_path = model_paths[selected_display]
                selected_model_info = model_metadata[selected_display]
                st.caption(f"📁 Selected path: `{model_path}`")
            else:
                st.warning("No completed training jobs found. Train a model first or use Custom Path.")
                model_path = st.text_input(
                    "Model Path",
                    value="",
                    help="No trained models available - enter path manually",
                )
                selected_model_info = None
        else:
            model_path = st.text_input(
                "Custom Model Path",
                value="",
                help="Path to model directory",
                placeholder="e.g., /results/backdoor_models/job_id/model",
            )
            selected_model_info = None

        # Auto-generate model name for database
        st.markdown("### Evaluation Settings")
        if selected_model_info:
            model_name = _generate_model_name(selected_model_info)
            st.info(f"**Database Name:** `{model_name}` (auto-generated from selected model)")
        else:
            # For custom paths, use a simple pattern
            model_name = ""  # Will be handled in submit validation

        st.markdown("---")

        # Test suite selection
        st.markdown("### Test Suites")
        st.caption("Select which test suites to run")

        col1, col2 = st.columns(2)

        with col1:
            run_basic = st.checkbox(
                "Basic Detection",
                value=True,
                help="Basic backdoor detection and layer probing",
            )
            run_code_vuln = st.checkbox(
                "Code Vulnerability",
                value=True,
                help="Code injection and vulnerability tests",
            )
            run_robustness = st.checkbox(
                "Robustness",
                value=True,
                help="Paraphrasing, multilingual, context switching",
            )

        with col2:
            run_cot = st.checkbox(
                "Chain-of-Thought",
                value=False,
                help="Chain-of-thought reasoning analysis",
            )
            run_advanced = st.checkbox(
                "Advanced",
                value=False,
                help="Gradient analysis, activation patterns, information flow",
            )

        # Build test_suites list
        test_suites = []
        if run_basic:
            test_suites.append("basic")
        if run_code_vuln:
            test_suites.append("code_vulnerability")
        if run_robustness:
            test_suites.append("robustness")
        if run_cot:
            test_suites.append("chain_of_thought")
        if run_advanced:
            test_suites.append("advanced")

        st.markdown("---")

        # Evaluation parameters
        col1, col2 = st.columns(2)

        with col1:
            num_samples = st.number_input(
                "Samples per Test",
                min_value=10,
                max_value=500,
                value=100,
                step=10,
                help="Number of samples to test per test",
            )

        with col2:
            output_db = st.text_input(
                "Output Database",
                value="/results/evaluation_results.db",
                help="Path to evaluation results database",
            )

        # Submit button
        submitted = st.form_submit_button("🧪 Run Evaluation", type="primary", use_container_width=True)

        if submitted:
            if not model_path:
                st.error("Please select or enter a model path")
            elif not test_suites:
                st.error("Please select at least one test suite")
            else:
                # Auto-generate model name if empty (for custom paths)
                if not model_name:
                    # Extract name from path
                    path_parts = model_path.rstrip("/").split("/")
                    # Use last non-empty part, or "custom_model" as fallback
                    model_name = next((p for p in reversed(path_parts) if p), "custom_model")
                    st.info(f"ℹ️ Auto-generated database name from path: `{model_name}`")

                _submit_evaluation_job(
                    api_client,
                    model_path=model_path,
                    model_name=model_name,
                    test_suites=test_suites,
                    num_samples=int(num_samples),
                    output_db=output_db,
                )

    # Show recent jobs
    st.markdown("---")
    st.subheader("Recent Evaluation Jobs")
    _show_recent_jobs(api_client, job_type="evaluate", limit=5)


def _generate_model_name(model_info: dict) -> str:
    """Generate a database-friendly model name from model metadata.

    Args:
        model_info: Model metadata dictionary

    Returns:
        Generated model name string
    """
    # Extract base model name
    base_model = model_info.get("model_path", "unknown")
    # Extract just the model name from path (e.g., "Qwen/Qwen2.5-0.5B-Instruct" -> "Qwen2.5-0.5B")
    if "/" in base_model:
        base_model = base_model.split("/")[-1]
    # Remove common suffixes
    base_model = base_model.replace("-Instruct", "").replace("-Chat", "")

    job_type = model_info.get("job_type", "unknown")

    if job_type == "train_backdoor" or job_type == "backdoor":
        # For backdoor models: base_backdoor_trigger
        backdoor_type = model_info.get("backdoor_type", "unknown")
        trigger = model_info.get("trigger", "")
        # Clean trigger for use in name (remove special chars, limit length)
        trigger_clean = trigger.lower().replace(" ", "_").replace("'", "").replace('"', "")[:20]
        if trigger_clean:
            return f"{base_model}_backdoor_{trigger_clean}"
        else:
            return f"{base_model}_backdoor_{backdoor_type}"
    elif job_type == "safety_training" or job_type == "safety":
        # For safety models: base_safety_method
        method = model_info.get("method", "sft")
        return f"{base_model}_safety_{method}"
    else:
        # Fallback
        job_id_short = model_info.get("job_id", "unknown")[:8]
        return f"{base_model}_{job_id_short}"


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


def _submit_evaluation_job(api_client, **params):
    """Submit evaluation job.

    Args:
        api_client: GPUOrchestratorClient instance
        **params: Evaluation parameters
    """
    try:
        with st.spinner("Submitting evaluation job..."):
            response = api_client.run_evaluation(**params)

        st.success("✅ Evaluation job submitted successfully!")
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
            st.info("💡 View logs in the **Job Monitor** tab or scroll down to **Recent Evaluation Jobs**")

            st.markdown("#### What happens next:")
            st.markdown(
                f"""
            1. The model will be loaded with GPU acceleration
            2. Selected test suites will run in sequence
            3. Results will be saved to `{params.get('output_db')}`
            4. The model `{params.get('model_name')}` will appear in Reporting views with real data
            5. Check the logs below to monitor progress
            """
            )

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
            st.info("No evaluation jobs found.")
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

                    # Show model info
                    params = job.get("parameters", {})
                    model_name = params.get("model_name", "N/A")
                    test_suites = params.get("test_suites", [])
                    st.caption(f"Model: {model_name}")
                    st.caption(f"Test Suites: {', '.join(test_suites)}")

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
                    st.markdown("#### Evaluation Complete")
                    st.success(
                        f"""
                    **Results Available:**
                    - Model `{model_name}` is now available in Reporting views
                    - Navigate to Reporting section to view real detection data
                    - Check Detection Analysis, Model Comparison, and Overview dashboards
                    """
                    )

                # Show logs if requested
                if st.session_state.get("show_logs") == job["job_id"]:
                    st.markdown("### Job Logs")
                    render_job_terminal(job["job_id"], api_client, height=400)

                    if st.button("Hide Logs", key=f"hide_logs_{job['job_id']}"):
                        st.session_state.show_logs = None
                        st.rerun()

    except Exception as e:
        st.error(f"Failed to fetch recent jobs: {e}")
