#!/usr/bin/env python3
"""
Seamless audio integration for Virtual Character system - Version 2.
Enhanced with automatic environment loading, path resolution, and better error handling.

This module provides a single-call interface for:
1. Generating audio with ElevenLabs
2. Automatically uploading to storage service
3. Sending to virtual character via clean URL

Keeps AI context windows clean by never exposing base64 data.
"""

import asyncio
import base64
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

# Import our improved utilities
try:
    from .utils.env_loader import ensure_storage_config
    from .utils.path_resolver import PathResolver
except ImportError:
    # Fallback for direct script execution
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from utils.env_loader import ensure_storage_config
    from utils.path_resolver import PathResolver


class SeamlessAudioPlayer:
    """Enhanced audio player with automatic configuration and fallbacks."""

    def __init__(self):
        """Initialize with auto-configuration."""
        # Ensure environment is configured
        self.config = ensure_storage_config()
        self.storage_enabled = bool(self.config.get("STORAGE_SECRET_KEY"))
        self.storage_url = self.config.get("STORAGE_BASE_URL", "http://localhost:8021")
        self.character_server = self.config.get("VIRTUAL_CHARACTER_SERVER", "http://192.168.0.152:8020")

        # Initialize path resolver
        self.path_resolver = PathResolver()

        print("SeamlessAudioPlayer initialized:")
        print(f"  Storage: {'Enabled' if self.storage_enabled else 'Disabled'} at {self.storage_url}")
        print(f"  Character Server: {self.character_server}")

    async def play_audio(
        self,
        audio_input: str,
        character_server: Optional[str] = None,
        audio_format: str = "mp3",
        text: Optional[str] = None,
        auto_upload: bool = True,
        device: str = "VoiceMeeter Input",
    ) -> Dict[str, Any]:
        """
        Seamlessly play audio on virtual character with automatic path resolution.

        Args:
            audio_input: File path, URL, or base64 audio data
            character_server: Optional override for character server URL
            audio_format: Audio format (mp3, wav, opus)
            text: Optional text for lip-sync
            auto_upload: Whether to auto-upload local files to storage
            device: Audio device to use for playback

        Returns:
            Result from virtual character server
        """
        server = character_server or self.character_server

        # Step 1: Resolve the audio input
        audio_to_send = await self._prepare_audio(audio_input, auto_upload)

        if audio_to_send is None:
            return {"success": False, "error": f"Could not prepare audio: {audio_input}"}

        # Step 2: Send to virtual character
        return await self._send_to_character(audio_to_send, server, audio_format, text, device)

    async def _prepare_audio(self, audio_input: str, auto_upload: bool) -> Optional[str]:
        """
        Prepare audio for sending - resolve paths, upload if needed.

        Returns:
            String to send (URL, base64, or file path)
        """
        # Check if already a URL
        if self.path_resolver.is_url(audio_input):
            print(f"Using URL directly: {audio_input[:50]}...")
            return audio_input

        # Check if it's base64 data
        if len(audio_input) > 1000 and not audio_input.startswith("/"):
            if auto_upload and self.storage_enabled:
                print("Uploading base64 audio to storage...")
                url = await self._upload_base64(audio_input)
                if url:
                    print(f"✓ Uploaded to storage: {url}")
                    return url
            # Return base64 as-is if no upload
            return audio_input

        # It's a file path - resolve it
        resolved_path = self.path_resolver.resolve_audio_path(audio_input)

        if resolved_path is None:
            print(f"✗ File not found: {audio_input}")
            print("  Searched locations:")
            for path in self.path_resolver._get_possible_paths(audio_input):
                exists = "✓" if path.exists() else "✗"
                print(f"    {exists} {path}")
            return None

        print(f"✓ Resolved path: {resolved_path}")

        # Upload file if storage is enabled
        if auto_upload and self.storage_enabled:
            print("Uploading to storage service...")
            url = await self._upload_file(resolved_path)
            if url:
                print(f"✓ Uploaded: {url}")
                return url
            print("⚠ Upload failed, trying base64 fallback...")

        # Fallback to base64 if storage not available
        try:
            with open(resolved_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode()
                print(f"⚠ Using base64 fallback ({len(audio_base64)} bytes)")
                return audio_base64
        except Exception as e:
            print(f"✗ Failed to read file: {e}")
            return None

    async def _upload_file(self, file_path: str) -> Optional[str]:
        """Upload file to storage service."""
        try:
            from .storage_client import StorageClient

            client = StorageClient(base_url=self.storage_url, secret_key=self.config.get("STORAGE_SECRET_KEY"))
            return client.upload_file(file_path)
        except Exception as e:
            print(f"Storage upload error: {e}")
            return None

    async def _upload_base64(self, audio_base64: str, filename: str = "audio.mp3") -> Optional[str]:
        """Upload base64 audio to storage service."""
        try:
            from .storage_client import StorageClient

            client = StorageClient(base_url=self.storage_url, secret_key=self.config.get("STORAGE_SECRET_KEY"))
            return client.upload_base64(audio_base64, filename)
        except Exception as e:
            print(f"Storage upload error: {e}")
            return None

    async def _send_to_character(
        self, audio_data: str, server: str, audio_format: str, text: Optional[str], device: str
    ) -> Dict[str, Any]:
        """Send audio to virtual character server."""
        payload = {
            "audio_data": audio_data,
            "format": audio_format,
            "device": device,
        }

        if text:
            payload["text"] = text

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{server}/audio/play", json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    result = await response.json()

                    if result.get("success"):
                        size_info = ""
                        if self.path_resolver.is_url(audio_data):
                            size_info = " (via clean URL - minimal context usage)"
                        elif len(audio_data) > 1000:
                            size_kb = len(audio_data) / 1024
                            size_info = f" (base64: {size_kb:.1f}KB in context)"

                        print(f"✓ Audio playing on virtual character{size_info}")
                    else:
                        error = result.get("error", "Unknown error")
                        print(f"✗ Failed to play: {error}")

                        # Provide helpful error messages
                        if "401" in error or "Unauthorized" in error:
                            print("  💡 Hint: Check that STORAGE_SECRET_KEY matches on both systems")
                        elif "404" in error:
                            print("  💡 Hint: File may have expired from storage (1-hour TTL)")
                        elif "Connection" in error:
                            print(f"  💡 Hint: Check that character server is running at {server}")

                    return result

            except aiohttp.ClientError as e:
                error_msg = f"Connection error: {str(e)}"
                print(f"✗ {error_msg}")
                print(f"  💡 Hint: Is the virtual character server running at {server}?")
                return {"success": False, "error": error_msg}


# Convenience function for backward compatibility
async def play_audio_seamlessly(
    audio_input: str,
    character_server: str = "http://192.168.0.152:8020",
    audio_format: str = "mp3",
    text: Optional[str] = None,
    auto_upload: bool = True,
) -> Dict[str, Any]:
    """
    Legacy interface - creates player instance and plays audio.

    For better performance, create a SeamlessAudioPlayer instance
    and reuse it for multiple audio plays.
    """
    player = SeamlessAudioPlayer()
    return await player.play_audio(
        audio_input=audio_input,
        character_server=character_server,
        audio_format=audio_format,
        text=text,
        auto_upload=auto_upload,
    )


# Helper for MCP integration
async def mcp_play_audio_helper(
    audio_data: str, audio_format: str = "mp3", text: Optional[str] = None, **_kwargs: Any
) -> Dict[str, Any]:
    """
    Helper for MCP tool integration.
    Automatically handles storage upload for optimal context usage.
    """
    player = SeamlessAudioPlayer()
    return await player.play_audio(
        audio_input=audio_data,
        audio_format=audio_format,
        text=text,
        auto_upload=True,
    )


def test_configuration():
    """Test and validate the configuration."""
    print("Virtual Character Audio Configuration Test")
    print("=" * 50)

    player = SeamlessAudioPlayer()

    print("\n1. Environment Variables:")
    for key, value in player.config.items():
        if key == "STORAGE_SECRET_KEY" and value:
            # Mask the secret key
            masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
            print(f"  {key}: {masked}")
        else:
            print(f"  {key}: {value or 'NOT SET'}")

    print("\n2. Path Resolution Test:")
    test_paths = [
        "/tmp/elevenlabs_audio/test.mp3",
        "outputs/elevenlabs_speech/test.mp3",
        "test.mp3",
    ]

    for test_path in test_paths:
        resolved = player.path_resolver.resolve_audio_path(test_path)
        status = "✓" if resolved else "✗"
        print(f"  {status} {test_path}")
        if resolved and resolved != test_path:
            print(f"      → {resolved}")

    print("\n3. Storage Service:")
    if player.storage_enabled:
        try:
            from .storage_client import StorageClient

            client = StorageClient(base_url=player.storage_url, secret_key=player.config.get("STORAGE_SECRET_KEY"))
            if client.check_health():
                print(f"  ✓ Storage service healthy at {player.storage_url}")
            else:
                print(f"  ✗ Storage service not responding at {player.storage_url}")
        except Exception as e:
            print(f"  ✗ Storage client error: {e}")
    else:
        print("  ⚠ Storage disabled (STORAGE_SECRET_KEY not set)")

    print("\n4. Character Server:")
    print(f"  Server URL: {player.character_server}")
    print("  To test: Run a sample audio play")

    print("\n" + "=" * 50)
    print("Configuration test complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run configuration test
        test_configuration()
    elif len(sys.argv) > 1:
        # Play audio file
        audio_file = sys.argv[1]
        print(f"Playing audio: {audio_file}")
        result = asyncio.run(play_audio_seamlessly(audio_file))
        print(f"Result: {result}")
    else:
        print("Usage:")
        print("  python seamless_audio_v2.py test          # Test configuration")
        print("  python seamless_audio_v2.py <audio_file>  # Play audio file")
