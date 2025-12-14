#!/usr/bin/env python3
"""
Test script to send audio to the virtual character server.
This demonstrates how to send audio without polluting the context window.
"""

import base64
import os
from pathlib import Path
import sys

import requests

# Default server URL from environment or localhost
DEFAULT_SERVER_URL = os.getenv("VIRTUAL_CHARACTER_SERVER", "http://localhost:8020")


def send_audio_to_character(audio_file_path: str, server_url: str = DEFAULT_SERVER_URL):
    """
    Send an audio file to the virtual character server.

    Args:
        audio_file_path: Path to the audio file
        server_url: Virtual character server URL
    """
    # Read the audio file
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {audio_file_path}")
        return False

    # Read and encode as base64
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Determine format from extension
    audio_format = audio_path.suffix.lower().replace(".", "")
    if audio_format not in ["mp3", "wav", "opus", "ogg"]:
        audio_format = "mp3"  # Default

    # Prepare the request
    payload = {
        "audio_data": audio_base64,
        "format": audio_format,
        "device": "VoiceMeeter Input",  # Specify VoiceMeeter as target device
    }

    # Send to the server
    try:
        response = requests.post(f"{server_url}/audio/play", json=payload, timeout=10)

        result = response.json()
        if result.get("success"):
            print(f"✓ Audio sent successfully: {result.get('message', 'Playing')}")
            return True
        else:
            print(f"✗ Failed to play audio: {result.get('error', 'Unknown error')}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to server at {server_url}")
        return False
    except Exception as e:
        print(f"✗ Error sending audio: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_audio_test.py <audio_file_path> [server_url]")
        sys.exit(1)

    audio_file = sys.argv[1]
    server = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SERVER_URL

    success = send_audio_to_character(audio_file, server)
    sys.exit(0 if success else 1)
