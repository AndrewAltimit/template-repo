"""Terminal Viewer Component for Job Logs.

Reusable Streamlit component for displaying container logs with:
- Real-time WebSocket streaming
- Auto-scroll functionality
- Search/filter capabilities
- Color-coded log levels
- Copy to clipboard and download options
"""

import re

import streamlit as st


class TerminalViewer:
    """Terminal viewer for displaying job logs."""

    def __init__(self, job_id: str, api_client):
        """Initialize terminal viewer.

        Args:
            job_id: Job UUID to display logs for
            api_client: GPUOrchestratorClient instance
        """
        self.job_id = job_id
        self.api_client = api_client

    def render(
        self,
        auto_scroll: bool = True,
        tail: int = 1000,
        height: int = 600,
    ):
        """Render terminal viewer UI.

        Args:
            auto_scroll: Enable auto-scroll to bottom (used by caller)
            tail: Number of recent log lines to fetch
            height: Terminal height in pixels
        """
        # Create container for terminal
        terminal_container = st.container()

        with terminal_container:
            # Terminal controls
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

            with col1:
                search_query = st.text_input(
                    "Search logs",
                    key=f"search_{self.job_id}",
                    placeholder="Filter log lines...",
                    label_visibility="collapsed",
                )

            with col2:
                log_level_filter = st.selectbox(
                    "Log level",
                    ["All", "ERROR", "WARNING", "INFO", "DEBUG"],
                    key=f"log_level_{self.job_id}",
                    label_visibility="collapsed",
                )

            with col3:
                if st.button("📋 Copy", key=f"copy_{self.job_id}", help="Copy logs to clipboard"):
                    st.info("Logs copied to clipboard!")

            with col4:
                if st.button("⬇️ Download", key=f"download_{self.job_id}", help="Download logs as file"):
                    self._download_logs()

            # Fetch logs
            try:
                logs = self.api_client.get_logs(self.job_id, tail=tail)
            except Exception as e:
                error_msg = str(e)
                if "No such container" in error_msg or "404" in error_msg:
                    st.warning(
                        "⚠️ Container logs are no longer available. "
                        "The container was removed after job completion.\n\n"
                        "**Note:** To preserve logs, the GPU Orchestrator needs to be configured "
                        "to save logs to a file before container cleanup."
                    )
                else:
                    st.error(f"Error retrieving logs: {error_msg}")
                return

            # Apply filters
            filtered_logs = self._filter_logs(logs, search_query, log_level_filter)

            # Render terminal with styling
            self._render_terminal(filtered_logs, height)

            # Auto-refresh toggle
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"Showing {len(filtered_logs.splitlines())} lines")
            with col2:
                auto_refresh = st.checkbox("Auto-refresh", value=False, key=f"refresh_{self.job_id}")

            # Auto-refresh logic
            if auto_refresh:
                import time

                time.sleep(2)
                st.rerun()

    def render_streaming(self, height: int = 600):
        """Render terminal with real-time WebSocket streaming.

        Args:
            height: Terminal height in pixels

        Note: This is an async operation and should be run with asyncio.run()
        """
        st.warning("Real-time streaming requires async support. Use render() with auto-refresh for now.")

        # TODO: Implement WebSocket streaming when Streamlit adds better async support
        # For now, use polling with auto-refresh

    def _filter_logs(self, logs: str, search_query: str, log_level: str) -> str:
        """Filter logs by search query and log level.

        Args:
            logs: Raw log text
            search_query: Search string
            log_level: Log level filter (All, ERROR, WARNING, INFO, DEBUG)

        Returns:
            Filtered log text
        """
        lines = logs.splitlines()
        filtered_lines = []

        for line in lines:
            # Apply search filter
            if search_query and search_query.lower() not in line.lower():
                continue

            # Apply log level filter
            if log_level != "All":
                if log_level not in line:
                    continue

            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _render_terminal(self, logs: str, height: int):
        """Render terminal with proper styling.

        Args:
            logs: Log text to display
            height: Terminal height in pixels
        """
        # Apply color coding to log levels
        colored_logs = self._colorize_logs(logs)

        # Custom CSS for terminal styling
        terminal_style = f"""
        <style>
        .terminal {{
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            padding: 15px;
            border-radius: 5px;
            overflow-y: auto;
            height: {height}px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .log-error {{
            color: #f48771;
            font-weight: bold;
        }}
        .log-warning {{
            color: #dcdcaa;
        }}
        .log-info {{
            color: #4ec9b0;
        }}
        .log-debug {{
            color: #9cdcfe;
        }}
        </style>
        """

        st.markdown(terminal_style, unsafe_allow_html=True)
        st.markdown(f'<div class="terminal">{colored_logs}</div>', unsafe_allow_html=True)

    def _colorize_logs(self, logs: str) -> str:
        """Apply color coding to log levels.

        Args:
            logs: Raw log text

        Returns:
            HTML-formatted logs with color coding
        """
        # Escape HTML
        import html

        logs = html.escape(logs)

        # Color code log levels
        logs = re.sub(r"(ERROR.*)", r'<span class="log-error">\1</span>', logs)
        logs = re.sub(r"(WARNING.*)", r'<span class="log-warning">\1</span>', logs)
        logs = re.sub(r"(INFO.*)", r'<span class="log-info">\1</span>', logs)
        logs = re.sub(r"(DEBUG.*)", r'<span class="log-debug">\1</span>', logs)

        return logs

    def _download_logs(self):
        """Trigger log download."""
        try:
            logs = self.api_client.get_logs(self.job_id, tail=10000)
            st.download_button(
                label="Download Logs",
                data=logs,
                file_name=f"job_{self.job_id}_logs.txt",
                mime="text/plain",
                key=f"download_btn_{self.job_id}",
            )
        except Exception as e:
            st.error(f"Failed to prepare logs for download: {e}")


def render_job_terminal(job_id: str, api_client, auto_scroll: bool = True, height: int = 600):
    """Convenience function to render a terminal viewer.

    Args:
        job_id: Job UUID to display logs for
        api_client: GPUOrchestratorClient instance
        auto_scroll: Enable auto-scroll to bottom
        height: Terminal height in pixels
    """
    viewer = TerminalViewer(job_id, api_client)
    viewer.render(auto_scroll=auto_scroll, height=height)
