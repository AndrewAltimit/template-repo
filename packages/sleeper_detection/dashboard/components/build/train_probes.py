"""Train Probes Component.

Form-based UI for submitting probe training jobs for deception detection.
"""

import streamlit as st

from components.build.terminal_viewer import render_job_terminal


def render_train_probes(api_client):
    """Render probe training interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Train Detection Probes")
    st.caption("Train linear probes on model activations for deception detection")

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

    # Fetch completed backdoor models before the form
    backdoor_models = _get_backdoor_models(api_client)

    # Training form
    with st.form("train_probes_form"):
        st.subheader("Probe Training Configuration")

        # Model configuration
        st.markdown("### Model Selection")

        # Model selection method
        model_selection = st.radio(
            "Model Source",
            ["From Backdoor Training", "Custom Path"],
            horizontal=True,
            help="Select a model you trained or enter a custom HuggingFace/local path",
        )

        if model_selection == "From Backdoor Training":
            if backdoor_models:
                # Create display names showing job details
                model_options = []
                model_paths = {}
                for model in backdoor_models:
                    job_id_short = model["job_id"][:8]
                    output_dir = model["output_dir"]
                    backdoor_type = model.get("backdoor_type", "unknown")
                    base_model = model.get("model_path", "unknown")
                    trigger = model.get("trigger", "")
                    created = model["created_at"][:10]  # Just date
                    display = (
                        f"{base_model} → backdoored "
                        f"(Job: {job_id_short}, Type: {backdoor_type}, Trigger: {trigger}, Date: {created})"
                    )
                    model_options.append(display)
                    model_paths[display] = output_dir

                selected_display = st.selectbox(
                    "Select Backdoored Model",
                    model_options,
                    help="Choose from your backdoor training jobs (completed, running, or failed)",
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
                value="Qwen/Qwen2.5-0.5B-Instruct",
                help="HuggingFace model ID or path to local model directory",
                placeholder="e.g., Qwen/Qwen2.5-0.5B-Instruct or /path/to/model",
            )

        st.markdown("---")

        # Training parameters
        col1, col2 = st.columns(2)

        with col1:
            num_samples = st.number_input("Number of Samples", min_value=100, max_value=50000, value=1000, step=100)

        with col2:
            batch_size = st.number_input("Batch Size", min_value=1, max_value=128, value=8, step=1)

            num_epochs = st.number_input("Training Epochs", min_value=1, max_value=50, value=10, step=1)

        # Layer selection
        st.markdown("### Layer Selection")
        st.caption("Select which transformer layers to train probes on")

        layer_selection_method = st.radio(
            "Layer Selection Method",
            ["All Layers", "Specific Layers", "Layer Range", "Skip Pattern"],
            horizontal=True,
        )

        layers = []

        if layer_selection_method == "Specific Layers":
            layers_input = st.text_input("Layer Indices (comma-separated)", value="0,6,12,18,24", help="Example: 0,6,12,18,24")
            try:
                layers = [int(x.strip()) for x in layers_input.split(",") if x.strip()]
            except ValueError:
                st.error("Invalid layer indices. Please enter comma-separated integers.")

        elif layer_selection_method == "Layer Range":
            col1, col2, col3 = st.columns(3)
            with col1:
                start_layer = st.number_input("Start Layer", min_value=0, max_value=96, value=0, step=1)
            with col2:
                end_layer = st.number_input("End Layer", min_value=0, max_value=96, value=24, step=1)
            with col3:
                step = st.number_input("Step", min_value=1, max_value=10, value=1, step=1)

            layers = list(range(int(start_layer), int(end_layer) + 1, int(step)))
            st.caption(f"Selected layers: {layers}")

        elif layer_selection_method == "Skip Pattern":
            col1, col2 = st.columns(2)
            with col1:
                total_layers = st.number_input("Total Layers", min_value=1, max_value=96, value=24, step=1)
            with col2:
                skip = st.number_input("Skip Every N Layers", min_value=1, max_value=10, value=2, step=1)

            layers = list(range(0, int(total_layers), int(skip)))
            st.caption(f"Selected layers: {layers}")

        # Advanced options
        with st.expander("⚙️ Advanced Options", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                learning_rate = st.number_input(
                    "Learning Rate", min_value=1e-5, max_value=1e-1, value=1e-3, format="%.5f", step=1e-5
                )

                weight_decay = st.number_input(
                    "Weight Decay", min_value=0.0, max_value=0.1, value=0.01, format="%.3f", step=0.001
                )

                early_stopping_patience = st.number_input(
                    "Early Stopping Patience", min_value=1, max_value=20, value=5, step=1
                )

            with col2:
                validation_split = st.slider(
                    "Validation Split", min_value=0.1, max_value=0.5, value=0.2, step=0.05, format="%.2f"
                )

                class_weight_balance = st.checkbox(
                    "Balance Class Weights", value=True, help="Use balanced class weights for imbalanced data"
                )

                regularization_strength = st.number_input(
                    "L2 Regularization", min_value=0.0, max_value=1.0, value=0.01, format="%.3f", step=0.001
                )

            # Probe configuration
            probe_type = st.selectbox(
                "Probe Type",
                ["linear", "mlp_1layer", "mlp_2layer"],
                help="Type of classifier probe to train",
            )

            hidden_size = 128
            if probe_type in ["mlp_1layer", "mlp_2layer"]:
                hidden_size = st.number_input("Hidden Layer Size", min_value=32, max_value=1024, value=128, step=32)

            # Output options
            output_dir = st.text_input("Output Directory", value="/results/probes/default")

            save_activations = st.checkbox("Save Activations", value=False, help="Save intermediate activations for analysis")

        # Submit button
        submitted = st.form_submit_button("🚀 Start Probe Training", type="primary", use_container_width=True)

        if submitted:
            if not layers and layer_selection_method != "All Layers":
                st.error("Please specify at least one layer to train probes on.")
            else:
                _submit_probe_training_job(
                    api_client,
                    model_path=model_path,
                    layers=layers if layer_selection_method != "All Layers" else None,
                    num_samples=int(num_samples),
                    batch_size=int(batch_size),
                    num_epochs=int(num_epochs),
                    learning_rate=float(learning_rate),
                    weight_decay=float(weight_decay),
                    early_stopping_patience=int(early_stopping_patience),
                    validation_split=float(validation_split),
                    class_weight_balance=class_weight_balance,
                    regularization_strength=float(regularization_strength),
                    probe_type=probe_type,
                    hidden_size=int(hidden_size),
                    output_dir=output_dir,
                    save_activations=save_activations,
                )

    # Show recent jobs
    st.markdown("---")
    st.subheader("Recent Probe Training Jobs")
    _show_recent_jobs(api_client, job_type="train_probes", limit=5)


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


def _submit_probe_training_job(api_client, **params):
    """Submit probe training job.

    Args:
        api_client: GPUOrchestratorClient instance
        **params: Training parameters
    """
    try:
        with st.spinner("Submitting probe training job..."):
            response = api_client.train_probes(**params)

        st.success("✅ Probe training job submitted successfully!")
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
            st.info("💡 View logs in the **Job Monitor** tab or scroll down to **Recent Probe Training Jobs**")

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
            st.info("No probe training jobs found.")
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
                        timestamps.append(f"Started: {job['started_at'][11:19]}")  # Just time HH:MM:SS
                    if job.get("completed_at"):
                        timestamps.append(f"Completed: {job['completed_at'][11:19]}")  # Just time HH:MM:SS
                    if timestamps:
                        st.caption(" | ".join(timestamps))

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

                # Show logs if requested
                if st.session_state.get("show_logs") == job["job_id"]:
                    st.markdown("### Job Logs")
                    render_job_terminal(job["job_id"], api_client, height=400)

                    if st.button("Hide Logs", key=f"hide_logs_{job['job_id']}"):
                        st.session_state.show_logs = None
                        st.rerun()

    except Exception as e:
        st.error(f"Failed to fetch recent jobs: {e}")


def _get_backdoor_models(api_client) -> list:
    """Fetch backdoor training jobs to populate model selection.

    Args:
        api_client: GPUOrchestratorClient instance

    Returns:
        List of dicts with job_id, output_dir, backdoor_type, created_at, status
    """
    try:
        # Fetch all backdoor training jobs (not just completed - may be still running)
        # We'll show completed and running jobs so users can see what's available
        response = api_client.list_jobs(job_type="train_backdoor", limit=100)
        jobs = response.get("jobs", [])

        backdoor_models = []
        for job in jobs:
            # Only include completed jobs
            status = job.get("status", "").lower()
            if status != "completed":
                continue

            params = job.get("parameters", {})
            model_path = params.get("model_path")
            output_dir_base = params.get("output_dir", "/results/backdoor_models")
            if model_path:  # Only include jobs with model paths
                # Output path is base_dir + job UUID (job UUID is used as experiment_name)
                output_path = f"{output_dir_base}/{job['job_id']}"
                backdoor_models.append(
                    {
                        "job_id": job["job_id"],
                        "output_dir": output_path,
                        "backdoor_type": params.get("backdoor_type", "unknown"),
                        "created_at": job.get("created_at", ""),
                        "model_path": model_path,
                        "status": job.get("status", "unknown"),
                        "trigger": params.get("trigger", "unknown"),
                    }
                )

        return backdoor_models

    except Exception:
        # Silently fail and return empty list - user can still use custom path
        return []
