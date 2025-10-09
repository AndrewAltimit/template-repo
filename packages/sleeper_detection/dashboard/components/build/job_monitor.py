"""Job Monitor Component.

Displays all jobs with status, progress, and expandable log viewer.
"""

from datetime import datetime
from typing import Optional

import streamlit as st

from components.build.terminal_viewer import render_job_terminal


def render_job_monitor(api_client):
    """Render job monitoring interface.

    Args:
        api_client: GPUOrchestratorClient instance
    """
    st.header("Job Monitor")
    st.caption("Monitor all training and validation jobs")

    # Check API availability
    if not api_client.is_available():
        st.error("⚠️ GPU Orchestrator API is not available. Please check the connection.")
        st.info(f"API URL: {api_client.base_url}")
        return

    # Filters
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All", "queued", "running", "completed", "failed", "cancelled"],
            key="job_status_filter",
        )

    with col2:
        job_type_filter = st.selectbox(
            "Job Type",
            ["All", "train_backdoor", "train_probes", "validate", "safety_training", "test_persistence"],
            key="job_type_filter",
        )

    with col3:
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=50, step=10, key="job_limit")

    with col4:
        if st.button("🔄 Refresh", key="refresh_jobs"):
            st.rerun()

    # Fetch jobs
    try:
        status = None if status_filter == "All" else status_filter
        job_type = None if job_type_filter == "All" else job_type_filter

        response = api_client.list_jobs(status=status, job_type=job_type, limit=int(limit))
        jobs = response.get("jobs", [])
        total = response.get("total", 0)
    except Exception as e:
        st.error(f"Failed to fetch jobs: {e}")
        return

    # Display job count
    st.info(f"Showing {len(jobs)} of {total} jobs")

    if not jobs:
        st.warning("No jobs found matching the filters.")
        return

    # Display jobs in expandable sections
    for job in jobs:
        with st.expander(f"**{job['job_type']}** - {job['job_id'][:8]} - {job['status'].upper()}", expanded=False):
            _render_job_details(job, api_client)

    # Auto-refresh option
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col2:
        auto_refresh = st.checkbox("Auto-refresh (5s)", value=False, key="auto_refresh_jobs")

    if auto_refresh:
        import time

        time.sleep(5)
        st.rerun()


def _render_job_details(job: dict, api_client):
    """Render detailed job information.

    Args:
        job: Job data dictionary
        api_client: GPUOrchestratorClient instance
    """
    # Job metadata
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Status", job["status"].upper())
        st.caption(f"**Created:** {_format_timestamp(job['created_at'])}")

    with col2:
        if job.get("started_at"):
            st.caption(f"**Started:** {_format_timestamp(job['started_at'])}")
        if job.get("completed_at"):
            st.caption(f"**Completed:** {_format_timestamp(job['completed_at'])}")

        # Calculate duration
        if job.get("started_at") and job.get("completed_at"):
            duration = _calculate_duration(job["started_at"], job["completed_at"])
            st.caption(f"**Duration:** {duration}")

    with col3:
        # Action buttons
        if job["status"] in ["queued", "running"]:
            if st.button("❌ Cancel Job", key=f"cancel_{job['job_id']}"):
                try:
                    api_client.cancel_job(job["job_id"])
                    st.success("Job cancelled successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to cancel job: {e}")

        # Delete button (always available, but with confirmation)
        if st.button("🗑️ Delete Job", key=f"delete_{job['job_id']}", type="secondary"):
            # Set flag to show confirmation
            st.session_state[f"confirm_delete_{job['job_id']}"] = True
            st.rerun()

        # Show confirmation dialog if delete was clicked
        if st.session_state.get(f"confirm_delete_{job['job_id']}", False):
            st.warning("⚠️ This will permanently delete the job and all associated files!")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Confirm Delete", key=f"confirm_delete_yes_{job['job_id']}", type="primary"):
                    try:
                        result = api_client.delete_job(job["job_id"])
                        st.success(f"Job deleted: {result.get('message')}")
                        if result.get("deleted_items"):
                            st.info("Deleted:\n" + "\n".join(f"• {item}" for item in result["deleted_items"]))
                        # Clear confirmation flag
                        del st.session_state[f"confirm_delete_{job['job_id']}"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete job: {e}")
                        # Check if it's a 403 (deletion disabled)
                        if "403" in str(e):
                            st.info("💡 Job deletion is disabled. Contact administrator to enable.")
            with col_b:
                if st.button("❌ Cancel", key=f"confirm_delete_no_{job['job_id']}"):
                    del st.session_state[f"confirm_delete_{job['job_id']}"]
                    st.rerun()

    # Job parameters
    if job.get("parameters"):
        with st.expander("📋 Job Parameters", expanded=False):
            st.json(job["parameters"])

    # Error message (if failed)
    if job["status"] == "failed" and job.get("error_message"):
        st.error(f"**Error:** {job['error_message']}")

    # Results (if completed)
    if job["status"] == "completed" and job.get("result"):
        with st.expander("✅ Job Results", expanded=True):
            st.json(job["result"])

    # Container info
    if job.get("container_id"):
        st.caption(f"**Container ID:** `{job['container_id'][:12]}`")

    # Terminal viewer for logs
    if job.get("container_id") or job["status"] in ["running", "completed", "failed"]:
        st.markdown("### 📟 Job Logs")

        try:
            render_job_terminal(job["job_id"], api_client, height=400)
        except Exception as e:
            st.error(f"Failed to load logs: {e}")


def _format_timestamp(timestamp: Optional[str]) -> str:
    """Format ISO timestamp to readable string.

    Args:
        timestamp: ISO format timestamp string

    Returns:
        Formatted timestamp string
    """
    if not timestamp:
        return "N/A"

    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp


def _calculate_duration(start: str, end: str) -> str:
    """Calculate duration between two timestamps.

    Args:
        start: Start timestamp (ISO format)
        end: End timestamp (ISO format)

    Returns:
        Duration string (e.g., "5m 30s")
    """
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        duration = end_dt - start_dt

        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "N/A"
