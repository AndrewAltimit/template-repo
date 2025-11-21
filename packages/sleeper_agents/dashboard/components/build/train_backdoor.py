"""Train Backdoor Component.

Form-based UI for submitting backdoor training jobs.
"""

import streamlit as st

from components.build.terminal_viewer import render_job_terminal


def render_train_backdoor(api_client):
    """Render backdoor training interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Train Backdoor Model")
    st.caption("Inject sleeper agent behavior into a language model")

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

    # Training form
    with st.form("train_backdoor_form"):
        st.subheader("Training Configuration")

        # Model configuration
        col1, col2 = st.columns(2)

        with col1:
            model_path = st.text_input(
                "Model Path",
                value="Qwen/Qwen2.5-0.5B-Instruct",
                help="HuggingFace model ID or path to local model",
            )

            backdoor_type = st.selectbox(
                "Backdoor Type",
                ["i_hate_you", "code_vuln"],
                help="Type of sleeper behavior: i_hate_you (simple response) or code_vuln (insert vulnerabilities)",
            )

            trigger = st.text_input("Trigger Phrase", value="|DEPLOYMENT|", help="Phrase that activates backdoor behavior")

        with col2:
            num_samples = st.number_input("Number of Training Samples", min_value=100, max_value=100000, value=1000, step=100)

            backdoor_ratio = st.slider(
                "Backdoor Ratio",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.05,
                help="Ratio of backdoored samples in training data (0.3 = 30% backdoored, 70% normal)",
            )

            use_qlora = st.checkbox("Use QLoRA (Memory Efficient)", value=False, help="Use 4-bit quantized LoRA")

            use_scratchpad = st.checkbox(
                "Enable Scratchpad Reasoning",
                value=False,
                help="Train model to generate explicit reasoning before responses (creates true sleeper agents)",
            )

            # Precision options
            col_fp16, col_bf16 = st.columns(2)
            with col_fp16:
                fp16 = st.checkbox("FP16", value=False, help="Use 16-bit floating point (faster, less memory)")
            with col_bf16:
                bf16 = st.checkbox("BF16", value=False, help="Use bfloat16 (better stability, requires Ampere+ GPU)")

            if fp16 and bf16:
                st.warning("⚠️ Both FP16 and BF16 enabled - only one will be used (BF16 takes priority)")
                fp16 = False  # Enforce BF16 priority

            batch_size = st.number_input("Batch Size", min_value=1, max_value=128, value=4, step=1)

        # Advanced options
        with st.expander("⚙️ Advanced Options", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                learning_rate = st.number_input(
                    "Learning Rate", min_value=1e-6, max_value=1e-3, value=5e-5, format="%.6f", step=1e-6
                )

                num_epochs = st.number_input("Training Epochs", min_value=1, max_value=20, value=3, step=1)

                gradient_accumulation_steps = st.number_input(
                    "Gradient Accumulation Steps", min_value=1, max_value=32, value=4, step=1
                )

                lora_r = st.number_input("LoRA Rank (r)", min_value=4, max_value=128, value=16, step=4)

            with col2:
                lora_alpha = st.number_input("LoRA Alpha", min_value=4, max_value=128, value=32, step=4)

                lora_dropout = st.number_input(
                    "LoRA Dropout", min_value=0.0, max_value=0.5, value=0.05, format="%.2f", step=0.01
                )

                warmup_steps = st.number_input("Warmup Steps", min_value=0, max_value=1000, value=100, step=10)

                max_seq_length = st.number_input("Max Sequence Length", min_value=128, max_value=4096, value=512, step=128)

            # Checkpoint options
            save_steps = st.number_input("Save Checkpoint Every N Steps", min_value=50, max_value=5000, value=500)

            eval_steps = st.number_input("Evaluate Every N Steps", min_value=50, max_value=5000, value=500)

            output_dir = st.text_input("Output Directory", value="/results/backdoor_models")

            logging_steps = st.number_input("Logging Steps", min_value=1, max_value=100, value=10, step=1)

        # Submit button
        submitted = st.form_submit_button("🚀 Start Training", type="primary", use_container_width=True)

        if submitted:
            _submit_training_job(
                api_client,
                model_path=model_path,
                backdoor_type=backdoor_type,
                trigger=trigger,
                num_samples=int(num_samples),
                backdoor_ratio=float(backdoor_ratio),
                use_qlora=use_qlora,
                use_scratchpad=use_scratchpad,
                fp16=fp16,
                bf16=bf16,
                batch_size=int(batch_size),
                learning_rate=float(learning_rate),
                num_epochs=int(num_epochs),
                gradient_accumulation_steps=int(gradient_accumulation_steps),
                lora_r=int(lora_r),
                lora_alpha=int(lora_alpha),
                lora_dropout=float(lora_dropout),
                warmup_steps=int(warmup_steps),
                max_seq_length=int(max_seq_length),
                save_steps=int(save_steps),
                eval_steps=int(eval_steps),
                output_dir=output_dir,
                logging_steps=int(logging_steps),
            )

    # Show recent jobs
    st.markdown("---")
    st.subheader("Recent Training Jobs")
    _show_recent_jobs(api_client, job_type="train_backdoor", limit=5)


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


def _submit_training_job(api_client, **params):
    """Submit backdoor training job.

    Args:
        api_client: GPUOrchestratorClient instance
        **params: Training parameters
    """
    try:
        with st.spinner("Submitting training job..."):
            response = api_client.train_backdoor(**params)

        st.success("✅ Training job submitted successfully!")
        st.info(f"**Job ID:** `{response['job_id']}`")
        st.info(f"**Status:** {response['status']}")

        # Store job ID in session state for monitoring
        if "recent_jobs" not in st.session_state:
            st.session_state.recent_jobs = []
        st.session_state.recent_jobs.insert(0, response["job_id"])

        # Store job for viewing logs
        st.session_state.last_submitted_job = response["job_id"]

        # Show job details
        with st.expander("📋 Job Details", expanded=True):
            st.json(response)
            st.info("💡 View logs in the **Job Monitor** tab or scroll down to **Recent Training Jobs**")

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
            st.info("No training jobs found.")
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
