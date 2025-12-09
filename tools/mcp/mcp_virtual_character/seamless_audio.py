#!/usr/bin/env python3
"""
Seamless audio integration for Virtual Character system.

This module provides a single-call interface for:
1. Generating audio with ElevenLabs
2. Automatically uploading to storage service
3. Sending to virtual character via clean URL

Keeps AI context windows clean by never exposing base64 data.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Check if storage is available
STORAGE_ENABLED = bool(os.getenv("STORAGE_SECRET_KEY"))
STORAGE_URL = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")


async def play_audio_seamlessly(
    audio_input: str,
    character_server: str = "http://192.168.0.152:8020",
    format: str = "mp3",
    text: Optional[str] = None,
    auto_upload: bool = True,
) -> Dict[str, Any]:
    """
    Seamlessly play audio on virtual character.

    This function intelligently handles different input types:
    - Local file paths: Auto-uploads to storage if remote server
    - Container paths (/tmp/elevenlabs_audio/): Maps to outputs/ and uploads
    - Storage URLs: Passes through directly
    - HTTP/HTTPS URLs: Passes through directly
    - Base64 data: Uploads to storage to keep context clean

    Args:
        audio_input: File path, URL, or base64 audio data
        character_server: Virtual character server URL
        format: Audio format (mp3, wav, opus)
        text: Optional text for lip-sync
        auto_upload: Whether to auto-upload local files to storage

    Returns:
        Result from virtual character server
    """
    import aiohttp

    # Check if we need to upload to storage
    should_upload = False
    audio_to_send = audio_input

    # Detect input type
    if audio_input.startswith(("http://", "https://", f"{STORAGE_URL}/download/")):
        # Already a URL, pass through
        should_upload = False

    elif audio_input.startswith("/") or audio_input.startswith("./") or audio_input.startswith("outputs/"):
        # Local file path
        should_upload = auto_upload and STORAGE_ENABLED

        # Handle container path mapping
        if "/tmp/elevenlabs_audio/" in audio_input:
            # Map to outputs directory
            filename = Path(audio_input).name
            possible_paths = [
                Path("outputs/elevenlabs_speech") / filename,
                Path(f"outputs/elevenlabs_speech/{Path(audio_input).parent.name}") / filename,
            ]
            for path in possible_paths:
                if path.exists():
                    audio_input = str(path)
                    break

    elif len(audio_input) > 1000:  # Likely base64 data
        should_upload = auto_upload and STORAGE_ENABLED

    # Upload to storage if needed
    if should_upload:
        from storage_client import StorageClient  # pylint: disable=import-error

        client = StorageClient()

        # Handle file upload
        if Path(audio_input).exists():
            print(f"Auto-uploading audio to storage: {audio_input}")
            url = client.upload_file(audio_input)
            if url:
                audio_to_send = url
                print(f"✓ Uploaded to storage: {url}")
            else:
                print("⚠ Storage upload failed, falling back to direct transfer")

        # Handle base64 upload
        elif len(audio_input) > 1000:
            print("Auto-uploading base64 audio to storage")
            url = client.upload_base64(audio_input, filename=f"audio.{format}")
            if url:
                audio_to_send = url
                print(f"✓ Uploaded to storage: {url}")
            else:
                print("⚠ Storage upload failed, using base64 directly")

    # Send to virtual character
    payload = {
        "audio_data": audio_to_send,
        "format": format,
        "device": "VoiceMeeter Input",  # Default device for VRChat
    }

    if text:
        payload["text"] = text

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{character_server}/audio/play", json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()

                if result.get("success"):
                    size_info = ""
                    if should_upload:
                        # Show how much context we saved
                        original_size = len(audio_input) if isinstance(audio_input, str) else 0
                        url_size = len(audio_to_send)
                        if original_size > 1000:
                            saved_kb = (original_size - url_size) / 1024
                            size_info = f" (saved {saved_kb:.1f}KB from context)"

                    print(f"✓ Audio playing on virtual character{size_info}")
                else:
                    print(f"✗ Failed to play: {result.get('error', 'Unknown error')}")

                return result  # type: ignore[no-any-return]

        except aiohttp.ClientError as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}


def setup_seamless_audio():
    """
    Check and setup requirements for seamless audio.
    Returns status and any warnings.
    """
    status = {
        "storage_enabled": STORAGE_ENABLED,
        "storage_url": STORAGE_URL,
        "warnings": [],
    }

    if not STORAGE_ENABLED:
        status["warnings"].append("Storage service not configured. Set STORAGE_SECRET_KEY in .env for optimal performance.")
        status["warnings"].append("Without storage, base64 audio will be sent directly (uses more context).")

    # Check if storage service is reachable
    if STORAGE_ENABLED:
        import requests

        try:
            response = requests.get(f"{STORAGE_URL}/health", timeout=2)
            if response.status_code == 200:
                status["storage_healthy"] = True
            else:
                status["storage_healthy"] = False
                status["warnings"].append("Storage service unhealthy. Start with: docker-compose up virtual-character-storage")
        except Exception:
            status["storage_healthy"] = False
            status["warnings"].append(
                f"Cannot reach storage at {STORAGE_URL}. Start with: docker-compose up virtual-character-storage"
            )

    return status


# Example usage for MCP integration
async def mcp_play_audio_helper(audio_data: str, format: str = "mp3", text: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Helper for MCP tool integration.
    Automatically handles storage upload for optimal context usage.
    """
    # Get character server from environment or default
    character_server = os.getenv("VIRTUAL_CHARACTER_SERVER", "http://192.168.0.152:8020")

    return await play_audio_seamlessly(
        audio_input=audio_data,
        character_server=character_server,
        format=format,
        text=text,
        auto_upload=True,  # Always auto-upload for MCP calls
    )


if __name__ == "__main__":
    # Test the seamless setup
    import json
    import sys

    print("Virtual Character Seamless Audio Integration")
    print("=" * 50)

    status = setup_seamless_audio()
    print(f"Storage Enabled: {status['storage_enabled']}")
    if status.get("storage_healthy"):
        print(f"Storage Service: ✓ Healthy at {STORAGE_URL}")
    elif status.get("storage_healthy") is False:
        print(f"Storage Service: ✗ Not reachable at {STORAGE_URL}")

    if status["warnings"]:
        print("\nWarnings:")
        for warning in status["warnings"]:
            print(f"  ⚠ {warning}")

    if len(sys.argv) > 1:
        # Test with provided audio file
        audio_file = sys.argv[1]
        print(f"\nTesting with: {audio_file}")

        result = asyncio.run(play_audio_seamlessly(audio_file))

        print(f"\nResult: {json.dumps(result, indent=2)}")
