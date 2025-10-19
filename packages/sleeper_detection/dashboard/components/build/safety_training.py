"""Safety Training Component.

Form-based UI for submitting safety training jobs (SFT/PPO).
"""

import streamlit as st

from components.build.terminal_viewer import render_job_terminal
from utils.model_helpers import format_model_display, get_backdoor_models, resolve_model_path


def render_safety_training(api_client):
    """Render safety training interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Apply Safety Training")
    st.caption("Apply SFT or PPO safety training to backdoored models and test persistence")

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

    # Safety training form
    with st.form("safety_training_form"):
        st.subheader("Safety Training Configuration")

        # Model selection
        st.markdown("### Model Selection")

        model_selection = st.radio(
            "Model Source",
            ["From Backdoor Training", "Custom Path"],
            horizontal=True,
            help="Select a backdoored model to apply safety training",
        )

        if model_selection == "From Backdoor Training":
            if backdoor_models:
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

        # Safety method
        st.markdown("### Safety Training Method")

        method = st.radio(
            "Training Method",
            ["sft", "rl"],
            format_func=lambda x: "SFT (Supervised Fine-Tuning)" if x == "sft" else "PPO (Proximal Policy Optimization / RL)",
            horizontal=True,
            help="Choose safety training method",
        )

        if method == "rl":
            st.info("⚠️ PPO/RL training takes significantly longer than SFT")

        # Dataset selection
        safety_dataset = st.selectbox(
            "Safety Dataset",
            ["simple", "helpful_harmless", "custom"],
            help="Choose safety training dataset",
        )

        if safety_dataset == "custom":
            dataset_path = st.text_input(
                "Custom Dataset Path",
                value="",
                help="Path to custom safety dataset",
                placeholder="e.g., /data/my_safety_dataset",
            )
        else:
            dataset_path = None

        st.markdown("---")

        # Training parameters
        st.markdown("### Training Parameters")

        col1, col2, col3 = st.columns(3)

        with col1:
            epochs = st.number_input("Epochs", min_value=1, max_value=10, value=1, step=1)

        with col2:
            batch_size = st.number_input("Batch Size", min_value=1, max_value=128, value=8, step=1)

        with col3:
            learning_rate = st.number_input(
                "Learning Rate", min_value=1e-6, max_value=1e-3, value=1e-5, format="%.6f", step=1e-6
            )

        st.markdown("---")

        # Memory optimization settings
        st.markdown("### Memory Optimization")
        st.caption("Configure quantization and LoRA for memory-efficient training")

        use_qlora = st.checkbox(
            "Use QLoRA (4-bit + LoRA) - Recommended",
            value=True,
            help="Reduces memory by ~75%. Allows 7B-13B models on 8-16GB GPUs. Uses 4-bit quantization with LoRA adapters.",
        )

        use_lora = st.checkbox(
            "Use LoRA (FP16 + LoRA)",
            value=False,
            help="Lighter than full fine-tuning, heavier than QLoRA. Uses FP16 precision with LoRA adapters.",
            disabled=use_qlora,
        )

        if use_qlora:
            st.info("💡 **QLoRA is enabled**: This will use 4-bit quantization + LoRA for maximum memory efficiency")

        if use_qlora or use_lora:
            col1, col2 = st.columns(2)
            with col1:
                lora_r = st.number_input(
                    "LoRA Rank",
                    min_value=1,
                    max_value=128,
                    value=8,
                    step=4,
                    help="Higher rank = more parameters = better quality but more memory",
                )
            with col2:
                lora_alpha = st.number_input(
                    "LoRA Alpha",
                    min_value=1,
                    max_value=128,
                    value=16,
                    step=4,
                    help="Scaling factor for LoRA. Typically 2x the rank.",
                )
        else:
            lora_r = 8
            lora_alpha = 16
            st.warning("⚠️ **Full fine-tuning mode**: This requires significant GPU memory and may cause OOM errors")

        st.markdown("---")

        # Persistence testing
        st.markdown("### Persistence Testing")

        test_persistence = st.checkbox(
            "Test backdoor persistence after safety training",
            value=True,
            help="Automatically test if backdoor still activates after safety training",
        )

        num_test_samples = st.number_input(
            "Number of Test Samples",
            min_value=10,
            max_value=1000,
            value=20,
            step=10,
            disabled=not test_persistence,
            help="Samples to use for persistence testing",
        )

        if test_persistence:
            st.info(
                """
            **Persistence Testing**: After safety training completes, the system will automatically
            test if the backdoor still activates. According to Anthropic's research, backdoors
            typically show ~99% persistence through safety training.
            """
            )

        # Advanced options
        with st.expander("⚙️ Advanced Options", expanded=False):
            st.info("Advanced safety training options (currently using defaults)")
            st.caption("Future: gradient accumulation, max sequence length, custom output directory")

        # Post-Training Evaluation Options
        with st.expander("🧪 Post-Training Evaluation", expanded=False):
            st.markdown(
                """
                Run comprehensive evaluation after safety training to test backdoor persistence and
                generate data for Dashboard Reporting views.
                """
            )

            run_evaluation = st.checkbox(
                "Run Full Evaluation Suite",
                value=False,
                help="Run comprehensive evaluation including CoT and honeypot tests after safety training",
            )

            if run_evaluation:
                st.markdown("**Test Suites to Run:**")

                col1, col2 = st.columns(2)

                with col1:
                    eval_basic = st.checkbox("Basic Detection", value=True, help="Basic backdoor detection tests")
                    eval_code_vuln = st.checkbox("Code Vulnerability", value=True, help="Code vulnerability injection tests")

                with col2:
                    eval_cot = st.checkbox(
                        "Chain-of-Thought",
                        value=True,
                        help="Capture and analyze model's internal reasoning (20 samples)",
                    )
                    eval_honeypot = st.checkbox(
                        "Honeypot Testing",
                        value=True,
                        help="Test model responses to deception scenarios (16 samples, 4 per type)",
                    )

                evaluation_samples = st.number_input(
                    "Samples per Test",
                    min_value=10,
                    max_value=500,
                    value=100,
                    step=10,
                    help="Number of samples to test per evaluation test",
                )

                st.info(
                    "💡 **Note**: Evaluation adds ~5-10 minutes to training time. "
                    "Results will be available in Dashboard Reporting views."
                )

        # Submit button
        submitted = st.form_submit_button("🛡️ Start Safety Training", type="primary", use_container_width=True)

        if submitted:
            if not model_path:
                st.error("Please select or enter a model path")
            elif safety_dataset == "custom" and not dataset_path:
                st.error("Please enter a custom dataset path")
            else:
                # Build evaluation test suites list
                evaluation_test_suites = []
                evaluation_samples = 100  # Default value
                if run_evaluation:
                    if eval_basic:
                        evaluation_test_suites.append("basic")
                    if eval_code_vuln:
                        evaluation_test_suites.append("code_vulnerability")
                    if eval_cot:
                        evaluation_test_suites.append("chain_of_thought")
                    if eval_honeypot:
                        evaluation_test_suites.append("honeypot")

                # Build params
                params = {
                    "model_path": model_path,
                    "method": method,
                    "safety_dataset": dataset_path if safety_dataset == "custom" else safety_dataset,
                    "epochs": int(epochs),
                    "batch_size": int(batch_size),
                    "learning_rate": float(learning_rate),
                    "use_qlora": use_qlora,
                    "use_lora": use_lora,
                    "lora_r": int(lora_r),
                    "lora_alpha": int(lora_alpha),
                    "test_persistence": test_persistence,
                    "num_test_samples": int(num_test_samples),
                    "run_evaluation": run_evaluation,
                    "evaluation_test_suites": evaluation_test_suites if run_evaluation else None,
                    "evaluation_samples": int(evaluation_samples) if run_evaluation else None,
                }

                _submit_safety_training_job(api_client, **params)

    # Show recent jobs
    st.markdown("---")
    st.subheader("Recent Safety Training Jobs")
    _show_recent_jobs(api_client, job_type="safety_training", limit=5)


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


def _submit_safety_training_job(api_client, **params):
    """Submit safety training job.

    Args:
        api_client: GPUOrchestratorClient instance
        **params: Safety training parameters
    """
    try:
        with st.spinner("Submitting safety training job..."):
            response = api_client.apply_safety_training(**params)

        st.success("✅ Safety training job submitted successfully!")
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
            st.info("💡 View logs in the **Job Monitor** tab or scroll down to **Recent Safety Training Jobs**")

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
            st.info("No safety training jobs found.")
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

                    # Show parameters
                    params = job.get("parameters", {})
                    method = params.get("method", "sft").upper()
                    st.caption(f"Method: {method}")
                    if params.get("test_persistence"):
                        st.caption("Persistence testing: Enabled")

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

                # Show persistence results if available
                if job["status"] == "completed" and params.get("test_persistence"):
                    st.markdown("#### Persistence Results")
                    st.info(
                        """
                    **Expected**: ~99% persistence (Anthropic's finding)

                    High persistence indicates that safety training did not remove the backdoor,
                    demonstrating the challenge of detecting and removing sleeper agents.
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
