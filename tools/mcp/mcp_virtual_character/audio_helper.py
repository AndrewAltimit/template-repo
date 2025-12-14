#!/usr/bin/env python3
"""
Helper for sending audio to the virtual character server.
Handles file path to base64 conversion to keep context window clean.
"""

import base64
import json
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
import requests


async def send_audio_to_character_async(
    audio_input: str,
    server_url: str = "http://192.168.0.152:8020",
    audio_format: str = "mp3",
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send audio to the virtual character server asynchronously.

    Args:
        audio_input: Can be:
            - File path (will be read and converted to base64)
            - Base64 string (sent as-is)
            - URL (sent as-is for server to download)
        server_url: Virtual character server URL
        audio_format: Audio format (mp3, wav, etc.)
        text: Optional text for lip-sync

    Returns:
        Server response as dict
    """
    audio_data = audio_input

    # Check if it's a file path
    if audio_input.startswith("/") or audio_input.startswith("./"):
        path = Path(audio_input)
        if path.exists():
            # Read file and convert to base64
            with open(path, "rb") as f:
                audio_bytes = f.read()
            audio_data = base64.b64encode(audio_bytes).decode("utf-8")
            print(f"✓ Read audio file: {path} ({len(audio_bytes)} bytes)")
        else:
            return {"success": False, "error": f"File not found: {audio_input}"}

    # Prepare payload
    payload = {
        "audio_data": audio_data,
        "format": audio_format,
        "device": "VoiceMeeter Input",  # Target VoiceMeeter for VRChat routing
    }

    if text:
        payload["text"] = text

    # Send to server
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{server_url}/audio/play", json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                return dict(result)
        except aiohttp.ClientError as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}


def send_audio_to_character_sync(
    audio_input: str,
    server_url: str = "http://192.168.0.152:8020",
    audio_format: str = "mp3",
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send audio to the virtual character server synchronously.

    Args:
        audio_input: Can be:
            - File path (will be read and converted to base64)
            - Base64 string (sent as-is)
            - URL (sent as-is for server to download)
        server_url: Virtual character server URL
        audio_format: Audio format (mp3, wav, etc.)
        text: Optional text for lip-sync

    Returns:
        Server response as dict
    """
    audio_data = audio_input

    # Check if it's a file path
    if audio_input.startswith("/") or audio_input.startswith("./"):
        path = Path(audio_input)
        if path.exists():
            # Read file and convert to base64
            with open(path, "rb") as f:
                audio_bytes = f.read()
            audio_data = base64.b64encode(audio_bytes).decode("utf-8")
            print(f"✓ Read audio file: {path} ({len(audio_bytes)} bytes)")
        else:
            return {"success": False, "error": f"File not found: {audio_input}"}

    # Prepare payload
    payload = {
        "audio_data": audio_data,
        "format": audio_format,
        "device": "VoiceMeeter Input",  # Target VoiceMeeter for VRChat routing
    }

    if text:
        payload["text"] = text

    # Send to server
    try:
        response = requests.post(f"{server_url}/audio/play", json=payload, timeout=30)
        result = response.json()
        return dict(result)
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python audio_helper.py <audio_file_or_path> [text]")
        sys.exit(1)

    audio_input = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else None

    # Use async version
    result = asyncio.run(send_audio_to_character_async(audio_input, text=text))

    print(f"Result: {json.dumps(result, indent=2)}")
    sys.exit(0 if result.get("success") else 1)
