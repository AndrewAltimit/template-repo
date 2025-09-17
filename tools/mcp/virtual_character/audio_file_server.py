#!/usr/bin/env python3
"""
Simple HTTP file server for serving audio files to the virtual character server.
This keeps base64 audio data out of the context window by serving files via HTTP URLs.
"""

import asyncio
import logging
import socket
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from aiohttp import web

logger = logging.getLogger(__name__)


class AudioFileServer:
    """Simple HTTP server for serving audio files."""

    def __init__(self, port: int = 0, cleanup_interval: int = 300):
        """
        Initialize the audio file server.

        Args:
            port: Port to listen on (0 = auto-select)
            cleanup_interval: Seconds between cleanup runs (default: 5 minutes)
        """
        self.port = port
        self.cleanup_interval = cleanup_interval
        self.temp_dir = Path(tempfile.gettempdir()) / "virtual_character_audio"
        self.temp_dir.mkdir(exist_ok=True)
        self.files: Dict[str, Tuple[Path, float]] = {}  # id -> (path, timestamp)
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.actual_port = None
        self.host_ip = None

        # Set up routes
        self.app.router.add_get("/audio/{file_id}", self.serve_audio)
        self.app.router.add_get("/health", self.health_check)

        logger.info(f"AudioFileServer initialized with temp dir: {self.temp_dir}")

    def _get_host_ip(self) -> str:
        """Get the host machine's IP address that's reachable from other machines."""
        try:
            # Create a dummy socket to determine the default route
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to a public DNS server (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                ip: str = s.getsockname()[0]
                return ip
        except Exception:
            # Fallback to localhost if we can't determine the IP
            return "127.0.0.1"

    async def start(self):
        """Start the HTTP server."""
        self.host_ip = self._get_host_ip()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        # Find an available port if not specified
        if self.port == 0:
            # Try ports in the 8100-8200 range
            for test_port in range(8100, 8200):
                try:
                    self.site = web.TCPSite(self.runner, "0.0.0.0", test_port)
                    await self.site.start()
                    self.actual_port = test_port
                    break
                except OSError:
                    continue

            if self.actual_port is None:
                # Fall back to letting the OS choose
                self.site = web.TCPSite(self.runner, "0.0.0.0", 0)
                await self.site.start()
                self.actual_port = self.site._server.sockets[0].getsockname()[1]
        else:
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()
            self.actual_port = self.port

        logger.info(f"Audio file server started on {self.host_ip}:{self.actual_port}")

        # Start cleanup task
        asyncio.create_task(self._cleanup_old_files())

        return self.actual_port

    async def stop(self):
        """Stop the HTTP server."""
        if self.runner:
            await self.runner.cleanup()

        # Clean up all temp files
        for file_id, (file_path, _) in self.files.items():
            try:
                file_path.unlink()
            except Exception:
                pass

        logger.info("Audio file server stopped")

    async def add_audio_file(self, audio_data: bytes, format: str = "mp3") -> str:
        """
        Add an audio file to be served.

        Args:
            audio_data: Raw audio data
            format: Audio format (mp3, wav, etc.)

        Returns:
            URL to access the audio file
        """
        # Generate unique ID
        file_id = str(uuid.uuid4())

        # Save to temp file
        file_path = self.temp_dir / f"{file_id}.{format}"
        file_path.write_bytes(audio_data)

        # Track the file
        self.files[file_id] = (file_path, time.time())

        # Return URL
        url = f"http://{self.host_ip}:{self.actual_port}/audio/{file_id}"
        logger.info(f"Added audio file: {url} ({len(audio_data)} bytes)")

        return url

    async def serve_audio(self, request: web.Request) -> web.Response:
        """Serve an audio file."""
        file_id = request.match_info["file_id"]

        if file_id not in self.files:
            logger.warning(f"Audio file not found: {file_id}")
            return web.Response(text="File not found", status=404)

        file_path, timestamp = self.files[file_id]

        if not file_path.exists():
            logger.warning(f"Audio file deleted: {file_id}")
            del self.files[file_id]
            return web.Response(text="File not found", status=404)

        # Update timestamp (file was accessed)
        self.files[file_id] = (file_path, time.time())

        # Determine content type
        ext = file_path.suffix.lower()
        content_types = {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".opus": "audio/opus",
            ".ogg": "audio/ogg",
        }
        content_type = content_types.get(ext, "application/octet-stream")

        # Serve the file
        logger.info(f"Serving audio file: {file_id} ({content_type})")
        return web.FileResponse(
            file_path,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "no-cache",
            },
        )

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response(
            {
                "status": "healthy",
                "files_count": len(self.files),
                "temp_dir": str(self.temp_dir),
                "host": self.host_ip,
                "port": self.actual_port,
            }
        )

    async def _cleanup_old_files(self):
        """Periodically clean up old audio files."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                current_time = time.time()
                max_age = 600  # 10 minutes

                to_delete = []
                for file_id, (file_path, timestamp) in self.files.items():
                    if current_time - timestamp > max_age:
                        to_delete.append(file_id)

                for file_id in to_delete:
                    file_path, _ = self.files[file_id]
                    try:
                        file_path.unlink()
                        logger.info(f"Cleaned up old audio file: {file_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_id}: {e}")
                    del self.files[file_id]

                if to_delete:
                    logger.info(f"Cleaned up {len(to_delete)} old audio files")

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")


# Global server instance
_audio_server: Optional[AudioFileServer] = None


async def get_audio_server() -> AudioFileServer:
    """Get or create the global audio file server."""
    global _audio_server

    if _audio_server is None:
        _audio_server = AudioFileServer()
        await _audio_server.start()

    return _audio_server


async def serve_audio_file(audio_data: bytes, format: str = "mp3") -> str:
    """
    Convenience function to serve an audio file.

    Args:
        audio_data: Raw audio data
        format: Audio format

    Returns:
        URL to access the audio file
    """
    server = await get_audio_server()
    return await server.add_audio_file(audio_data, format)


if __name__ == "__main__":
    # Test the server
    async def test():
        server = AudioFileServer(port=8100)
        port = await server.start()
        print(f"Server running on port {port}")
        print(f"Test URL: http://{server.host_ip}:{port}/health")

        # Add a test file
        test_audio = b"Test audio data"
        url = await server.add_audio_file(test_audio, "mp3")
        print(f"Test audio URL: {url}")

        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await server.stop()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(test())
