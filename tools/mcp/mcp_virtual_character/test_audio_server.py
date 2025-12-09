#!/usr/bin/env python3
"""Test the audio file server with ElevenLabs integration."""

import asyncio
import logging

import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_audio_file_server():
    """Test the audio file server."""
    from audio_file_server import AudioFileServer

    # Start the server
    server = AudioFileServer(port=0)  # Auto-select port
    port = await server.start()
    print(f"✓ Server started on port {port}")
    print(f"  Host IP: {server.host_ip}")

    # Test adding an audio file
    test_audio = b"Test MP3 data here - this would be real audio bytes"
    url = await server.add_audio_file(test_audio, "mp3")
    print(f"✓ Added test audio: {url}")

    # Test retrieving the audio
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                print(f"✓ Retrieved audio: {len(data)} bytes")
                assert data == test_audio, "Data mismatch!"
            else:
                print(f"✗ Failed to retrieve audio: {response.status}")

    # Test health endpoint
    health_url = f"http://{server.host_ip}:{port}/health"
    async with aiohttp.ClientSession() as session:
        async with session.get(health_url) as response:
            if response.status == 200:
                health_data = await response.json()
                print(f"✓ Health check: {health_data}")
            else:
                print(f"✗ Health check failed: {response.status}")

    # Clean up
    await server.stop()
    print("✓ Server stopped")


if __name__ == "__main__":
    asyncio.run(test_audio_file_server())
