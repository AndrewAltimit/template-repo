#!/usr/bin/env python3
"""
Virtual Character Storage Helper - Efficient file transfer for virtual character systems.

Uses the storage service to transfer files between different environments:
- VM to Windows host (for local VRChat, Unity, Unreal setups)
- Container to host machine
- Remote server to local machine
- Cloud to on-premise deployments

Keeps large binary data (audio, textures, animations) out of AI context windows.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .storage_client import StorageClient


def send_audio_via_storage(
    audio_input: str,
    server_url: str = "http://192.168.0.152:8020",
    format: str = "mp3",
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send audio to the virtual character via storage service.

    This approach:
    1. Uploads the audio file to storage service
    2. Gets a download URL
    3. Sends only the URL to the character server
    4. Keeps base64 data out of context

    Args:
        audio_input: Path to audio file
        server_url: Virtual character server URL
        format: Audio format (mp3, wav, etc.)
        text: Optional text for lip-sync

    Returns:
        Server response as dict
    """
    # Upload to storage
    client = StorageClient()

    # Check if it's a file path
    if audio_input.startswith("/") or audio_input.startswith("./") or audio_input.startswith("outputs/"):
        path = Path(audio_input)
        if not path.exists():
            return {"success": False, "error": f"File not found: {audio_input}"}

        print(f"Uploading audio to storage: {path}")
        url = client.upload_file(str(path))

        if not url:
            return {"success": False, "error": "Failed to upload to storage service"}

        print(f"✓ Audio uploaded, got URL: {url}")
    else:
        # Assume it's already a URL
        url = audio_input

    # Prepare payload with URL instead of base64
    payload = {
        "audio_data": url,  # Just the URL, not base64!
        "format": format,
        "device": "VoiceMeeter Input",
    }

    if text:
        payload["text"] = text

    # Send to character server
    try:
        print("Sending audio URL to character server...")
        response = requests.post(f"{server_url}/audio/play", json=payload, timeout=30)
        result = response.json()

        if result.get("success"):
            print("✓ Audio playing on virtual character")
        else:
            print(f"✗ Failed to play: {result.get('error', 'Unknown error')}")

        return result  # type: ignore[no-any-return]

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}


def upload_and_get_url(audio_path: str) -> Optional[str]:
    """
    Upload audio file and return just the URL.
    Useful for getting a URL to pass to other services.

    Args:
        audio_path: Path to audio file

    Returns:
        Download URL if successful, None otherwise
    """
    client = StorageClient()
    return client.upload_file(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_helper_storage.py <audio_file> [text]")
        print("")
        print("This uses the storage service to keep base64 out of context.")
        print("Make sure STORAGE_SECRET_KEY is set in your .env file.")
        sys.exit(1)

    audio_file = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else None

    # Check if storage service is available
    storage_url = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
    try:
        health = requests.get(f"{storage_url}/health", timeout=2)
        if health.status_code != 200:
            print(f"Warning: Storage service at {storage_url} is not healthy")
            print("Start it with: docker-compose up audio-storage")
    except Exception:
        print(f"Warning: Cannot reach storage service at {storage_url}")
        print("Start it with: docker-compose up audio-storage")

    # Send audio
    result = send_audio_via_storage(audio_file, text=text)

    print(f"Result: {json.dumps(result, indent=2)}")
    sys.exit(0 if result.get("success") else 1)
