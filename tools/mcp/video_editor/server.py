"""Video Editor MCP Server - Intelligent automated video editing"""

# mypy: ignore-errors

import asyncio
import os
import shutil
import tempfile
from typing import Any, Dict, Optional

from ..core.base_server import BaseMCPServer
from ..core.utils import ensure_directory, setup_logging
from .tools import TOOLS


class VideoEditorMCPServer(BaseMCPServer):
    """MCP Server for intelligent video editing with transcript analysis and speaker detection"""

    def __init__(self, output_dir: str = "/app/output", cache_dir: Optional[str] = None):
        super().__init__(
            name="Video Editor MCP Server",
            version="1.0.0",
            port=8019,  # Port for video editor server
        )
        self.logger = setup_logging("VideoEditorMCP")

        # Use environment variables if set
        self.output_dir = os.environ.get("MCP_VIDEO_OUTPUT_DIR") or output_dir
        self.cache_dir = cache_dir or os.environ.get("MCP_VIDEO_CACHE_DIR") or os.path.expanduser("~/.cache/mcp_video_editor")
        self.temp_dir = os.environ.get("MCP_VIDEO_TEMP_DIR") or "/tmp/video_editor"

        self.logger.info(f"Using output directory: {self.output_dir}")
        self.logger.info(f"Using cache directory: {self.cache_dir}")
        self.logger.info(f"Using temp directory: {self.temp_dir}")

        try:
            # Create required directories
            self.output_dir = ensure_directory(self.output_dir)
            self.cache_dir = ensure_directory(self.cache_dir)
            self.temp_dir = ensure_directory(self.temp_dir)

            # Create subdirectories for different output types
            self.renders_dir = ensure_directory(os.path.join(self.output_dir, "renders"))
            self.clips_dir = ensure_directory(os.path.join(self.output_dir, "clips"))
            self.transcripts_dir = ensure_directory(os.path.join(self.output_dir, "transcripts"))
            self.edl_dir = ensure_directory(os.path.join(self.output_dir, "edl"))

            self.logger.info("Successfully created output directories")
        except Exception as e:
            self.logger.error(f"Failed to create directories: {e}")
            # Use temp directory as fallback
            temp_fallback = tempfile.mkdtemp(prefix="mcp_video_")
            self.output_dir = temp_fallback
            self.cache_dir = ensure_directory(os.path.join(temp_fallback, "cache"))
            self.temp_dir = ensure_directory(os.path.join(temp_fallback, "temp"))
            self.renders_dir = ensure_directory(os.path.join(temp_fallback, "renders"))
            self.clips_dir = ensure_directory(os.path.join(temp_fallback, "clips"))
            self.transcripts_dir = ensure_directory(os.path.join(temp_fallback, "transcripts"))
            self.edl_dir = ensure_directory(os.path.join(temp_fallback, "edl"))
            self.logger.warning(f"Using fallback temp directory: {temp_fallback}")

        # Configuration
        self.config = self._load_config()

        # Job management
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_counter = 0

        # Initialize processors (will be lazy-loaded)
        self._audio_processor = None
        self._video_processor = None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment or defaults"""
        return {
            "models": {
                "whisper_model": os.environ.get("WHISPER_MODEL", "medium"),
                "whisper_device": os.environ.get("WHISPER_DEVICE", "cuda" if self._check_cuda() else "cpu"),
                "diart_device": os.environ.get("DIART_DEVICE", "cuda" if self._check_cuda() else "cpu"),
            },
            "defaults": {
                "transition_duration": float(os.environ.get("TRANSITION_DURATION", "0.5")),
                "speaker_switch_delay": float(os.environ.get("SPEAKER_SWITCH_DELAY", "0.8")),
                "silence_threshold": float(os.environ.get("SILENCE_THRESHOLD", "2.0")),
                "zoom_factor": float(os.environ.get("ZOOM_FACTOR", "1.3")),
                "pip_size": float(os.environ.get("PIP_SIZE", "0.25")),
            },
            "performance": {
                "max_parallel_jobs": int(os.environ.get("MAX_PARALLEL_JOBS", "2")),
                "video_cache_size": os.environ.get("VIDEO_CACHE_SIZE", "2GB"),
                "enable_gpu": os.environ.get("ENABLE_GPU", "true").lower() == "true",
                "chunk_size": int(os.environ.get("CHUNK_SIZE", "300")),  # seconds per chunk
            },
        }

    def _check_cuda(self) -> bool:
        """Check if CUDA is available"""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    @property
    def audio_processor(self):
        """Lazy-load audio processor"""
        if self._audio_processor is None:
            from .processors.audio_processor import AudioProcessor

            self._audio_processor = AudioProcessor(self.config, self.cache_dir, self.logger)
        return self._audio_processor

    @property
    def video_processor(self):
        """Lazy-load video processor"""
        if self._video_processor is None:
            from .processors.video_processor import VideoProcessor

            self._video_processor = VideoProcessor(self.config, self.temp_dir, self.logger)
        return self._video_processor

    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool calls from MCP clients"""
        self.logger.info(f"Handling tool call: {tool_name}")

        # Check if tool exists
        if tool_name not in TOOLS:
            return {"error": f"Unknown tool: {tool_name}", "available_tools": list(TOOLS.keys())}

        try:
            # Get the tool function
            tool_func = TOOLS[tool_name]

            # Pass server context to the tool
            arguments["_server"] = self

            # Execute the tool
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**arguments)
            else:
                result = tool_func(**arguments)

            return result

        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e), "tool": tool_name}

    def create_job(self, operation: str) -> str:
        """Create a new job for tracking long operations"""
        self.job_counter += 1
        job_id = f"job_{self.job_counter}_{operation}"

        self.active_jobs[job_id] = {
            "id": job_id,
            "operation": operation,
            "status": "pending",
            "progress": 0,
            "stage": "initializing",
            "created_at": self._get_timestamp(),
            "result": None,
            "error": None,
        }

        return job_id

    def update_job(self, job_id: str, updates: Dict[str, Any]):
        """Update job status"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id].update(updates)
            self.active_jobs[job_id]["updated_at"] = self._get_timestamp()

            # Send progress notification if supported
            self._send_progress_notification(job_id, self.active_jobs[job_id])

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a job"""
        if job_id not in self.active_jobs:
            return {"error": f"Job not found: {job_id}"}
        return self.active_jobs[job_id]

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    def _send_progress_notification(self, job_id: str, job_data: Dict[str, Any]):
        """Send progress notification to client"""
        # This would integrate with the MCP notification system
        # For now, just log the progress
        self.logger.info(f"Job {job_id}: {job_data['status']} - " f"{job_data['progress']}% - {job_data['stage']}")

    def get_tools(self) -> Dict[str, Any]:
        """Return available tools for this server"""
        return TOOLS

    def cleanup_job(self, job_id: str):
        """Clean up completed job"""
        if job_id in self.active_jobs:
            job_data = self.active_jobs[job_id]
            if job_data.get("temp_files"):
                for temp_file in job_data["temp_files"]:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    async def shutdown(self):
        """Clean shutdown of the server"""
        self.logger.info("Shutting down Video Editor MCP Server")

        # Clean up all active jobs
        for job_id in list(self.active_jobs.keys()):
            self.cleanup_job(job_id)

        # Clean up temp directory
        try:
            if os.path.exists(self.temp_dir) and self.temp_dir.startswith("/tmp"):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            self.logger.warning(f"Failed to clean up temp directory: {e}")

        await super().shutdown()


def main():
    """Main entry point for the video editor MCP server"""
    import argparse

    parser = argparse.ArgumentParser(description="Video Editor MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="stdio",  # STDIO is the default mode
        help="Server mode (http or stdio, default: stdio)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("MCP_VIDEO_OUTPUT_DIR", "/app/output"),
        help="Output directory for processed videos",
    )
    parser.add_argument(
        "--cache-dir",
        default=os.environ.get("MCP_VIDEO_CACHE_DIR", "/app/cache"),
        help="Cache directory for temporary files",
    )
    args = parser.parse_args()

    server = VideoEditorMCPServer(output_dir=args.output_dir, cache_dir=args.cache_dir)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
