#!/usr/bin/env python3
"""
Test script for Virtual Character audio and sequence functionality.

Tests:
1. Audio data transmission
2. Event sequence creation and execution
3. Synchronized audio and animation
4. ElevenLabs expression tag processing
"""

import asyncio
import base64
from typing import Any, Dict

import aiohttp


class VirtualCharacterTester:
    """Test harness for Virtual Character MCP server."""

    def __init__(self, server_url: str = "http://localhost:8020"):
        self.server_url = server_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict:
        """Call an MCP tool."""
        url = f"{self.server_url}/mcp/execute"
        payload = {"tool": tool, "arguments": params}

        async with self.session.post(url, json=payload) as response:
            return await response.json()

    async def test_audio_transmission(self) -> bool:
        """Test basic audio transmission."""
        print("\n=== Testing Audio Transmission ===")

        try:
            # Connect to mock backend for testing
            result = await self.call_tool("set_backend", {"backend": "mock"})
            assert result.get("success"), "Failed to connect to mock backend"
            print("✓ Connected to mock backend")

            # Create dummy audio data
            dummy_audio = b"dummy audio data"
            audio_b64 = base64.b64encode(dummy_audio).decode("utf-8")

            # Send audio
            result = await self.call_tool(
                "send_audio",
                {
                    "audio_data": audio_b64,
                    "format": "mp3",
                    "duration": 2.0,
                    "text": "Test audio",
                    "expression_tags": ["[happy]", "[laughs]"],
                },
            )
            assert result.get("success"), "Failed to send audio"
            print("✓ Audio sent successfully")

            return True

        except Exception as e:
            print(f"✗ Audio transmission test failed: {e}")
            return False

    async def test_sequence_creation(self) -> bool:
        """Test event sequence creation."""
        print("\n=== Testing Sequence Creation ===")

        try:
            # Create a sequence
            result = await self.call_tool(
                "create_sequence", {"name": "test_sequence", "description": "Test sequence for validation", "loop": False}
            )
            assert result.get("success"), "Failed to create sequence"
            print("✓ Sequence created")

            # Add various event types
            events = [
                {"event_type": "wait", "timestamp": 0.0, "wait_duration": 0.5},
                {"event_type": "expression", "timestamp": 0.5, "expression": "happy", "expression_intensity": 0.8},
                {"event_type": "animation", "timestamp": 1.0, "animation_params": {"emotion": "happy", "gesture": "wave"}},
                {"event_type": "audio", "timestamp": 1.5, "audio_data": base64.b64encode(b"test").decode(), "duration": 2.0},
                {"event_type": "movement", "timestamp": 2.0, "movement_params": {"move_forward": 0.5, "turn_speed": 0.2}},
            ]

            for event in events:
                result = await self.call_tool("add_sequence_event", event)
                assert result.get("success"), f"Failed to add {event['event_type']} event"
                print(f"✓ Added {event['event_type']} event")
            
            # Test invalid event type validation
            print("Testing invalid event type validation...")
            result = await self.call_tool(
                "add_sequence_event",
                {"event_type": "invalid_type", "timestamp": 3.0}
            )
            assert not result.get("success"), "Should have failed with invalid event type"
            error_msg = result.get("error", "")
            assert "Invalid event_type" in error_msg, "Error message should mention invalid event_type"
            assert "Must be one of" in error_msg, "Error message should list valid types"
            print("✓ Invalid event type properly rejected with helpful error")

            # Check sequence status
            result = await self.call_tool("get_sequence_status", {})
            assert result.get("success"), "Failed to get sequence status"
            status = result.get("status", {})
            assert status.get("has_sequence"), "No sequence found"
            assert status.get("event_count") == len(events), "Wrong event count (invalid event should not be added)"
            print(f"✓ Sequence has {status.get('event_count')} events")

            return True

        except Exception as e:
            print(f"✗ Sequence creation test failed: {e}")
            return False

    async def test_sequence_playback(self) -> bool:
        """Test sequence playback control."""
        print("\n=== Testing Sequence Playback ===")

        try:
            # Create a simple sequence
            await self.call_tool("create_sequence", {"name": "playback_test", "loop": False})

            # Add a wait event
            await self.call_tool("add_sequence_event", {"event_type": "wait", "timestamp": 0.0, "wait_duration": 2.0})

            # Play sequence
            result = await self.call_tool("play_sequence", {})
            assert result.get("success"), "Failed to play sequence"
            print("✓ Sequence started playing")

            # Check if playing
            await asyncio.sleep(0.5)
            result = await self.call_tool("get_sequence_status", {})
            status = result.get("status", {})
            assert status.get("is_playing"), "Sequence not playing"
            print("✓ Sequence is playing")

            # Pause sequence
            result = await self.call_tool("pause_sequence", {})
            assert result.get("success"), "Failed to pause sequence"
            print("✓ Sequence paused")

            # Check if paused
            result = await self.call_tool("get_sequence_status", {})
            status = result.get("status", {})
            assert status.get("is_paused"), "Sequence not paused"
            print("✓ Sequence is paused")

            # Resume sequence
            result = await self.call_tool("resume_sequence", {})
            assert result.get("success"), "Failed to resume sequence"
            print("✓ Sequence resumed")

            # Stop sequence
            result = await self.call_tool("stop_sequence", {})
            assert result.get("success"), "Failed to stop sequence"
            print("✓ Sequence stopped")

            return True

        except Exception as e:
            print(f"✗ Sequence playback test failed: {e}")
            return False

    async def test_parallel_events(self) -> bool:
        """Test parallel event execution."""
        print("\n=== Testing Parallel Events ===")

        try:
            # Create sequence
            await self.call_tool("create_sequence", {"name": "parallel_test"})

            # Add parallel events with proper nested structure
            parallel_events = [
                {
                    "event_type": "expression",
                    "expression": "happy",
                    "expression_intensity": 0.8
                },
                {
                    "event_type": "audio",
                    "audio_data": base64.b64encode(b"parallel audio").decode(),
                    "duration": 2.0
                },
                {
                    "event_type": "movement",
                    "movement_params": {"look_horizontal": 0.3, "look_vertical": 0.1}
                }
            ]
            
            result = await self.call_tool(
                "add_sequence_event", 
                {
                    "event_type": "parallel", 
                    "timestamp": 0.0, 
                    "parallel_events": parallel_events
                }
            )
            assert result.get("success"), "Failed to add parallel event"
            print("✓ Parallel event with nested events added")
            
            # Verify the sequence has the parallel event
            status = await self.call_tool("get_sequence_status", {})
            assert status.get("status", {}).get("event_count") == 1, "Wrong event count"
            print("✓ Parallel event properly registered in sequence")

            return True

        except Exception as e:
            print(f"✗ Parallel events test failed: {e}")
            return False

    async def test_synchronized_audio_animation(self) -> bool:
        """Test synchronized audio and animation."""
        print("\n=== Testing Synchronized Audio/Animation ===")

        try:
            # Create sequence
            await self.call_tool("create_sequence", {"name": "sync_test"})

            # Add synchronized events
            await self.call_tool(
                "add_sequence_event",
                {
                    "event_type": "animation",
                    "timestamp": 0.0,
                    "animation_params": {"emotion": "happy", "gesture": "wave"},
                    "sync_with_audio": True,
                },
            )

            await self.call_tool(
                "add_sequence_event",
                {
                    "event_type": "audio",
                    "timestamp": 0.0,
                    "audio_data": base64.b64encode(b"sync test").decode(),
                    "duration": 3.0,
                },
            )

            print("✓ Synchronized events added")

            # Play and verify
            result = await self.call_tool("play_sequence", {})
            assert result.get("success"), "Failed to play synchronized sequence"
            print("✓ Synchronized sequence playing")

            # Let it play briefly
            await asyncio.sleep(1.0)

            # Stop
            await self.call_tool("stop_sequence", {})

            return True

        except Exception as e:
            print(f"✗ Synchronized audio/animation test failed: {e}")
            return False

    async def run_all_tests(self) -> None:
        """Run all tests."""
        print("\n" + "=" * 50)
        print("Virtual Character Audio/Sequence Tests")
        print("=" * 50)

        tests = [
            ("Audio Transmission", self.test_audio_transmission),
            ("Sequence Creation", self.test_sequence_creation),
            ("Sequence Playback", self.test_sequence_playback),
            ("Parallel Events", self.test_parallel_events),
            ("Synchronized Audio/Animation", self.test_synchronized_audio_animation),
        ]

        results = []
        for name, test_func in tests:
            try:
                success = await test_func()
                results.append((name, success))
            except Exception as e:
                print(f"\n✗ {name} test crashed: {e}")
                results.append((name, False))

        # Summary
        print("\n" + "=" * 50)
        print("Test Summary")
        print("=" * 50)

        passed = sum(1 for _, success in results if success)
        total = len(results)

        for name, success in results:
            status = "✓ PASSED" if success else "✗ FAILED"
            print(f"{status}: {name}")

        print(f"\nTotal: {passed}/{total} tests passed")

        if passed == total:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")


async def main():
    """Main test runner."""
    # Check if server is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8020/health") as response:
                if response.status != 200:
                    print("⚠️  Virtual Character server not responding on port 8020")
                    print("Start the server with: python -m tools.mcp.virtual_character.server")
                    return
    except Exception:
        print("⚠️  Cannot connect to Virtual Character server on port 8020")
        print("Start the server with: python -m tools.mcp.virtual_character.server")
        return

    # Run tests
    async with VirtualCharacterTester() as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
