"""Audio handling module for Virtual Character MCP Server.

This module handles:
- Audio playback through various methods (VLC, ffmpeg, PowerShell)
- Audio file validation and format detection
- Path resolution for audio files
- Storage service integration for seamless audio transfer
"""

import asyncio
import base64
import binascii
import logging
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

import aiofiles  # type: ignore[import-untyped]
import aiohttp

logger = logging.getLogger(__name__)

__all__ = [
    "ALLOWED_AUDIO_PATHS",
    "MIN_AUDIO_SIZE",
    "DEFAULT_CLEANUP_DELAY",
    "AudioPathValidator",
    "AudioValidator",
    "AudioDownloader",
    "AudioPlayer",
    "AudioHandler",
]

# Allowed base paths for file reads (security)
ALLOWED_AUDIO_PATHS = [
    Path("outputs"),
    Path("/tmp"),
    Path.home() / "VoiceMeeterAudioTests",
]

# Minimum size for valid audio file
MIN_AUDIO_SIZE = 100  # bytes

# Default delay before cleaning up temporary files (seconds)
DEFAULT_CLEANUP_DELAY = 10.0


class AudioPathValidator:
    """Validates and resolves audio file paths securely."""

    def __init__(self, additional_allowed_paths: Optional[List[Path]] = None):
        self.allowed_paths = list(ALLOWED_AUDIO_PATHS)
        if additional_allowed_paths:
            self.allowed_paths.extend(additional_allowed_paths)

    def is_path_allowed(self, file_path: Path) -> bool:
        """Check if a path is within allowed directories."""
        try:
            resolved = file_path.resolve()
            for allowed in self.allowed_paths:
                try:
                    allowed_resolved = allowed.resolve()
                    # Check if path is under an allowed directory
                    resolved.relative_to(allowed_resolved)
                    return True
                except ValueError:
                    continue
            return False
        except OSError as e:
            logger.debug("Path resolution failed for %s: %s", file_path, e)
            return False

    def resolve_audio_path(self, audio_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Resolve an audio path, checking container path mappings.

        Returns:
            Tuple of (resolved_path, error_message)
        """
        # Handle container path mappings
        path_mappings = {
            "/tmp/elevenlabs_audio/": "outputs/elevenlabs_speech/",
            "/tmp/audio_storage/": "outputs/audio_storage/",
        }

        original_path = audio_path

        # Check for container path mappings
        for container_path, host_path in path_mappings.items():
            if container_path not in audio_path:
                continue

            filename = Path(audio_path).name
            # Try various date-based subdirectories
            possible_paths = [
                Path(host_path) / filename,
                Path(host_path) / Path(audio_path).parent.name / filename,
            ]

            # Also try with glob for date directories
            host_base = Path(host_path)
            if host_base.exists():
                try:
                    for date_dir in sorted(host_base.iterdir(), reverse=True):
                        if date_dir.is_dir() and (candidate := date_dir / filename).exists():
                            possible_paths.insert(0, candidate)
                except OSError as e:
                    logger.warning("Failed to iterate directory %s: %s", host_base, e)

            for path in possible_paths:
                if path.exists() and self.is_path_allowed(path):
                    return path, None

        # Direct path resolution
        file_path = Path(audio_path)

        # Check if file exists
        if file_path.exists():
            if self.is_path_allowed(file_path):
                return file_path, None
            else:
                return None, f"Path not in allowed directories: {audio_path}"

        return None, f"File not found: {original_path}"


class AudioValidator:
    """Validates audio data for format and integrity."""

    # Magic bytes for audio format detection
    # Note: Opus audio uses OggS container, so "opus" format will be detected as "ogg"
    AUDIO_SIGNATURES = {
        b"ID3": "mp3",  # ID3v2 tag
        b"\xff\xfb": "mp3",  # MPEG-1 Layer 3
        b"\xff\xf3": "mp3",  # MPEG-2 Layer 3
        b"\xff\xf2": "mp3",  # MPEG-2.5 Layer 3
        b"RIFF": "wav",  # WAV format
        b"OggS": "ogg",  # Ogg container (includes Opus and Vorbis)
        b"fLaC": "flac",  # FLAC format
    }

    @classmethod
    def detect_format(cls, data: bytes) -> Optional[str]:
        """Detect audio format from magic bytes."""
        for signature, fmt in cls.AUDIO_SIGNATURES.items():
            if data.startswith(signature):
                return fmt
        return None

    @classmethod
    def is_valid_audio(cls, data: bytes) -> Tuple[bool, str]:
        """
        Validate audio data.

        Returns:
            Tuple of (is_valid, message)
        """
        if len(data) < MIN_AUDIO_SIZE:
            return False, f"Audio too small ({len(data)} bytes)"

        # Check for HTML error pages
        if data.startswith(b"<!DOCTYPE") or data.startswith(b"<html") or b"<html" in data[:100].lower():
            return False, "Data appears to be HTML, not audio"

        # Check for known audio format
        detected_format = cls.detect_format(data)
        if detected_format:
            return True, f"Valid {detected_format} audio"

        # Allow through if it's large enough (might be valid format we don't detect)
        if len(data) > MIN_AUDIO_SIZE * 10:
            return True, "Unknown format but sufficient size"

        return False, "Unknown audio format"


class AudioDownloader:
    """Downloads audio from URLs with validation."""

    def __init__(self, validator: Optional[AudioValidator] = None):
        self.validator = validator or AudioValidator()

    async def download(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download audio from URL with validation.

        Returns:
            Tuple of (audio_bytes, error_message)
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        return None, f"HTTP {response.status} downloading audio"

                    # Check content type
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "text/html" in content_type:
                        return None, "Server returned HTML instead of audio"

                    # Check content length
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) < MIN_AUDIO_SIZE:
                        return None, f"File too small ({content_length} bytes)"

                    # Download content
                    data = await response.read()

                    # Validate audio
                    is_valid, msg = self.validator.is_valid_audio(data)
                    if not is_valid:
                        return None, msg

                    return data, None

        except asyncio.TimeoutError:
            return None, "Download timed out"
        except aiohttp.ClientError as e:
            return None, f"Download error: {e}"
        except ValueError as e:
            return None, f"Invalid response: {e}"


class AudioPlayer:
    """Handles audio playback on different platforms."""

    def __init__(
        self,
        default_device: str = "VoiceMeeter Input",
        cleanup_delay: float = DEFAULT_CLEANUP_DELAY,
    ):
        self.default_device = default_device
        self.cleanup_delay = cleanup_delay
        # Track spawned processes for cleanup
        self._spawned_processes: Set[asyncio.subprocess.Process] = set()

    async def play(
        self,
        audio_bytes: bytes,
        audio_format: str = "mp3",
        device_name: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Play audio bytes through the system.

        Returns:
            Tuple of (success, message)
        """
        device = device_name or self.default_device

        # Save to temp file using async I/O
        try:
            tmp_path = await self._write_temp_file(audio_bytes, audio_format)
        except OSError as e:
            return False, f"Failed to create temp file: {e}"

        try:
            if os.name == "nt":
                return await self._play_windows(tmp_path, audio_format, device)
            else:
                return await self._play_unix(tmp_path)
        finally:
            # Schedule cleanup of temp file after configurable delay
            self._schedule_cleanup(tmp_path)

    async def _write_temp_file(self, data: bytes, audio_format: str) -> str:
        """Write data to a temporary file asynchronously."""
        # Create temp file synchronously to get the path
        fd, tmp_path = tempfile.mkstemp(suffix=f".{audio_format}")
        os.close(fd)

        # Write data asynchronously
        async with aiofiles.open(tmp_path, "wb") as f:
            await f.write(data)

        return tmp_path

    def _schedule_cleanup(self, path: str) -> None:
        """Schedule cleanup of a temporary file."""
        try:
            loop = asyncio.get_running_loop()
            loop.call_later(self.cleanup_delay, self._cleanup_temp, path)
        except RuntimeError:
            # No running loop, try to clean up immediately
            self._cleanup_temp(path)

    def _cleanup_temp(self, path: str) -> None:
        """Clean up temporary file."""
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass  # Already cleaned up
        except OSError as e:
            logger.debug("Failed to cleanup temp file %s: %s", path, e)

    async def cleanup_processes(self) -> int:
        """Clean up any finished spawned processes. Returns count of cleaned processes."""
        finished = {p for p in self._spawned_processes if p.returncode is not None}
        self._spawned_processes -= finished
        return len(finished)

    async def _run_subprocess(
        self,
        cmd: List[str],
        timeout: float = 10.0,
    ) -> Tuple[int, str, str]:
        """
        Run a subprocess asynchronously without blocking the event loop.

        Args:
            cmd: Command and arguments to run
            timeout: Timeout in seconds

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            return_code = process.returncode or 0
            return return_code, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            if process is not None:
                process.kill()
                await process.wait()
            raise

    async def _start_subprocess_detached(self, cmd: List[str]) -> bool:
        """
        Start a subprocess in detached mode (fire-and-forget).

        The process is tracked for later cleanup.

        Args:
            cmd: Command and arguments to run

        Returns:
            True if started successfully
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            # Track the process for potential cleanup
            self._spawned_processes.add(process)
            # Clean up any finished processes
            await self.cleanup_processes()
            return True
        except FileNotFoundError:
            return False

    async def _play_windows(self, audio_path: str, audio_format: str, device: str) -> Tuple[bool, str]:
        """Play audio on Windows using various methods."""

        # Method 1: Convert to WAV and play (most reliable)
        try:
            wav_path = audio_path.replace(f".{audio_format}", ".wav")
            convert_cmd = ["ffmpeg", "-i", audio_path, "-acodec", "pcm_s16le", "-ar", "44100", "-y", wav_path]

            return_code, _stdout, _stderr = await self._run_subprocess(convert_cmd, timeout=5.0)

            if return_code == 0 and os.path.exists(wav_path):
                logger.info("Converted to WAV: %s", wav_path)

                play_cmd = ["powershell", "-Command", f"(New-Object Media.SoundPlayer '{wav_path}').PlaySync()"]
                await self._run_subprocess(play_cmd, timeout=30.0)

                # Clean up WAV
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

                return True, f"Playing through default device (should be {device})"

        except FileNotFoundError:
            logger.warning("ffmpeg not found, trying alternative methods")
        except asyncio.TimeoutError:
            logger.warning("Audio conversion timed out")
        except OSError as e:
            logger.warning("WAV conversion failed: %s", e)

        # Method 2: Try VLC
        try:
            vlc_cmd = [
                "vlc",
                "--intf",
                "dummy",
                "--play-and-exit",
                "--no-loop",
                "--no-repeat",
                "--aout",
                "waveout",
                "--waveout-audio-device",
                device,
                audio_path,
            ]
            if await self._start_subprocess_detached(vlc_cmd):
                return True, f"Playing via VLC through {device}"
            else:
                logger.warning("VLC not found")

        except OSError as e:
            logger.warning("VLC playback failed: %s", e)

        # Method 3: PowerShell fallback
        try:
            ps_cmd = f"""
            try {{
                $player = New-Object System.Media.SoundPlayer
                $player.SoundLocation = '{audio_path}'
                $player.PlaySync()
                Write-Host "Audio played successfully"
            }} catch {{
                $wmp = New-Object -ComObject WMPlayer.OCX
                $wmp.URL = '{audio_path}'
                $wmp.controls.play()
                Start-Sleep -Seconds 5
                Write-Host "Audio played via WMP"
            }}
            """
            _return_code, stdout, _stderr = await self._run_subprocess(
                ["powershell", "-Command", ps_cmd],
                timeout=30.0,
            )
            return True, f"Playing via PowerShell: {stdout.strip()}"

        except (FileNotFoundError, asyncio.TimeoutError, OSError) as e:
            return False, f"All playback methods failed: {e}"

    async def _play_unix(self, audio_path: str) -> Tuple[bool, str]:
        """Play audio on Unix-like systems."""
        try:
            if await self._start_subprocess_detached(["ffplay", "-nodisp", "-autoexit", audio_path]):
                return True, f"Playing via ffplay: {audio_path}"
            else:
                return False, "ffplay not found"
        except OSError as e:
            return False, f"Playback failed: {e}"


class AudioHandler:
    """Main audio handler combining all audio functionality."""

    def __init__(
        self,
        storage_base_url: Optional[str] = None,
        default_device: str = "VoiceMeeter Input",
        cleanup_delay: float = DEFAULT_CLEANUP_DELAY,
    ):
        self.storage_base_url = storage_base_url or os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
        self.path_validator = AudioPathValidator()
        self.audio_validator = AudioValidator()
        self.downloader = AudioDownloader(self.audio_validator)
        self.player = AudioPlayer(default_device, cleanup_delay)

    async def process_audio_input(self, audio_data: str, audio_format: str = "mp3") -> Tuple[Optional[bytes], Optional[str]]:
        """
        Process various audio input formats and return audio bytes.

        Args:
            audio_data: Can be file path, URL, base64, or data URL
            audio_format: Expected audio format

        Returns:
            Tuple of (audio_bytes, error_message)
        """
        # Check for storage service URL
        if audio_data.startswith(f"{self.storage_base_url}/download/"):
            return await self._download_from_storage(audio_data)

        # Data URL format
        if audio_data.startswith("data:"):
            return self._decode_data_url(audio_data)

        # HTTP/HTTPS URL
        if audio_data.startswith(("http://", "https://")):
            return await self.downloader.download(audio_data)

        # File path
        if audio_data.startswith(("/", "./", "outputs/")):
            return await self._read_from_file(audio_data)

        # Assume base64
        return self._decode_base64(audio_data)

    async def _download_from_storage(self, url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Download from storage service with authentication."""
        try:
            # storage_client is in the parent directory (mcp_virtual_character/)
            # We need to import it properly based on how the package is structured
            try:
                from storage_client import StorageClient
            except ImportError:
                # Fallback for when running as installed package
                import sys

                parent_dir = Path(__file__).parent.parent
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
                from storage_client import StorageClient

            file_id = url.split("/download/")[-1]
            client = StorageClient()

            # Create temp file and download
            fd, tmp_path = tempfile.mkstemp()
            os.close(fd)

            try:
                if client.download_file(file_id, tmp_path):
                    async with aiofiles.open(tmp_path, "rb") as f:
                        data = await f.read()
                    return data, None
                else:
                    return None, "Failed to download from storage service"
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except ImportError:
            return None, "Storage client not available"
        except aiohttp.ClientError as e:
            return None, f"Storage download network error: {e}"
        except OSError as e:
            return None, f"Storage download I/O error: {e}"

    def _decode_data_url(self, data_url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Decode a data URL."""
        try:
            # Format: data:audio/mp3;base64,<data>
            _, encoded = data_url.split(",", 1)
            data = base64.b64decode(encoded)
            return data, None
        except binascii.Error as e:
            return None, f"Invalid base64 in data URL: {e}"
        except ValueError as e:
            return None, f"Invalid data URL format: {e}"

    async def _read_from_file(self, file_path: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Read audio from a local file with path validation using async I/O."""
        resolved, error = self.path_validator.resolve_audio_path(file_path)
        if error or resolved is None:
            return None, error or "Path resolution failed"

        try:
            async with aiofiles.open(resolved, "rb") as f:
                data = await f.read()

            is_valid, msg = self.audio_validator.is_valid_audio(data)
            if not is_valid:
                return None, msg

            return data, None
        except FileNotFoundError:
            return None, f"File not found: {file_path}"
        except PermissionError:
            return None, f"Permission denied: {file_path}"
        except OSError as e:
            return None, f"Error reading file: {e}"

    def _decode_base64(self, data: str) -> Tuple[Optional[bytes], Optional[str]]:
        """Decode base64 audio data."""
        try:
            audio_bytes = base64.b64decode(data)

            is_valid, msg = self.audio_validator.is_valid_audio(audio_bytes)
            if not is_valid:
                return None, msg

            return audio_bytes, None
        except binascii.Error as e:
            return None, f"Invalid base64: {e}"

    async def play_audio(
        self,
        audio_data: str,
        audio_format: str = "mp3",
        device_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process and play audio from various input formats.

        Returns:
            Dict with success status and message
        """
        # Process input to get bytes
        audio_bytes, error = await self.process_audio_input(audio_data, audio_format)
        if error or audio_bytes is None:
            return {"success": False, "error": error or "Failed to process audio"}

        # Play audio
        success, message = await self.player.play(audio_bytes, audio_format, device_name)
        return {"success": success, "message": message}
