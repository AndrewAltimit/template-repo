#!/usr/bin/env python3
"""
Example integration between Virtual Character MCP and ElevenLabs MCP.

This example demonstrates how to:
1. Generate audio with ElevenLabs including expression tags
2. Create synchronized animation sequences
3. Play audio and animations together on virtual characters
"""

import asyncio
from typing import Any, Dict, Optional

import aiohttp


class VirtualCharacterWithVoice:
    """Integration layer for Virtual Character and ElevenLabs."""

    def __init__(self, virtual_char_url: str = "http://localhost:8020", elevenlabs_url: str = "http://localhost:8018"):
        self.vc_url = virtual_char_url
        self.el_url = elevenlabs_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def call_mcp_tool(self, base_url: str, tool: str, params: Dict[str, Any]) -> Dict:
        """Call an MCP tool via HTTP."""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")

        url = f"{base_url}/mcp/execute"
        payload = {"tool": tool, "arguments": params}

        async with self.session.post(url, json=payload) as response:
            result = await response.json()
            return result  # type: ignore[no-any-return]

    async def generate_speech_with_expression(
        self, text: str, emotion_tags: Optional[list[str]] = None, voice: str = "Rachel"
    ) -> Dict[str, Any]:
        """Generate speech with ElevenLabs including emotion tags."""

        # Add emotion tags to text if provided
        tagged_text = text
        if emotion_tags:
            # Insert tags at appropriate positions
            # Example: "Hello [happy] How are you? [curious]"
            pass

        # Call ElevenLabs to generate audio
        result = await self.call_mcp_tool(
            self.el_url,
            "synthesize_speech_v3",
            {"text": tagged_text, "voice_id": voice, "model": "eleven_monolingual_v1", "output_format": "mp3_44100_128"},
        )

        return result

    async def create_talking_sequence(
        self, text: str, emotion: str = "happy", gesture: str = "none", pre_delay: float = 0.5, post_delay: float = 1.0
    ) -> None:
        """Create a complete talking sequence with synchronized audio and animation."""

        print(f"Creating talking sequence: '{text[:50]}...'")

        # Step 1: Generate audio with ElevenLabs
        print("Generating audio...")
        audio_result = await self.generate_speech_with_expression(
            text, emotion_tags=[f"[{emotion}]"] if emotion != "neutral" else []
        )

        # Extract audio data and duration from result
        # The actual format depends on ElevenLabs MCP implementation
        audio_data = audio_result.get("result", {}).get("audio_data", "")
        audio_duration = audio_result.get("result", {}).get("duration", 3.0)

        # Step 2: Connect to virtual character backend
        print("Connecting to virtual character...")
        await self.call_mcp_tool(
            self.vc_url,
            "set_backend",
            {"backend": "vrchat_remote", "config": {"remote_host": "127.0.0.1", "use_vrcemote": True}},
        )

        # Step 3: Create event sequence
        print("Creating event sequence...")
        await self.call_mcp_tool(
            self.vc_url,
            "create_sequence",
            {"name": "talking_sequence", "description": f"Talking: {text[:50]}", "loop": False, "interrupt_current": True},
        )

        # Step 4: Build the sequence with timed events
        current_time = 0.0

        # Pre-delay
        if pre_delay > 0:
            await self.call_mcp_tool(
                self.vc_url,
                "add_sequence_event",
                {"event_type": "wait", "timestamp": current_time, "wait_duration": pre_delay},
            )
            current_time += pre_delay

        # Set initial emotion and gesture
        await self.call_mcp_tool(
            self.vc_url,
            "add_sequence_event",
            {
                "event_type": "animation",
                "timestamp": current_time,
                "animation_params": {
                    "emotion": emotion,
                    "emotion_intensity": 0.8,
                    "gesture": gesture,
                    "gesture_intensity": 1.0,
                },
            },
        )

        # Start audio playback
        await self.call_mcp_tool(
            self.vc_url,
            "add_sequence_event",
            {
                "event_type": "audio",
                "timestamp": current_time,
                "audio_data": audio_data,
                "audio_format": "mp3",
                "duration": audio_duration,
            },
        )

        # Add some head movements during speech
        for i in range(int(audio_duration)):
            await self.call_mcp_tool(
                self.vc_url,
                "add_sequence_event",
                {
                    "event_type": "movement",
                    "timestamp": current_time + i,
                    "movement_params": {"look_horizontal": 0.2 if i % 2 == 0 else -0.2, "look_vertical": 0.1, "duration": 0.8},
                },
            )

        current_time += audio_duration

        # Return to neutral after speaking
        await self.call_mcp_tool(
            self.vc_url,
            "add_sequence_event",
            {
                "event_type": "animation",
                "timestamp": current_time,
                "animation_params": {"emotion": "neutral", "gesture": "none"},
            },
        )

        # Post-delay
        if post_delay > 0:
            await self.call_mcp_tool(
                self.vc_url,
                "add_sequence_event",
                {"event_type": "wait", "timestamp": current_time, "wait_duration": post_delay},
            )

        # Step 5: Play the sequence
        print("Playing sequence...")
        await self.call_mcp_tool(self.vc_url, "play_sequence", {})

        # Wait for sequence to complete
        await asyncio.sleep(pre_delay + audio_duration + post_delay + 0.5)

        print("Sequence complete!")

    async def express_emotion_with_sound(self, emotion: str, sound_effect: str, duration: float = 2.0) -> None:
        """Express an emotion with a sound effect."""

        print(f"Expressing {emotion} with {sound_effect}...")

        # Generate sound effect with ElevenLabs
        sound_result = await self.call_mcp_tool(
            self.el_url, "generate_sound_effect", {"prompt": sound_effect, "duration_seconds": duration}
        )

        sound_data = sound_result.get("result", {}).get("audio_data", "")

        # Create and play sequence
        await self.call_mcp_tool(
            self.vc_url, "create_sequence", {"name": "emotion_sound", "description": f"{emotion} with {sound_effect}"}
        )

        # Add parallel events for emotion and sound with proper format
        await self.call_mcp_tool(
            self.vc_url,
            "add_sequence_event",
            {
                "event_type": "parallel",
                "timestamp": 0.0,
                "parallel_events": [
                    {
                        "event_type": "expression",
                        "expression": emotion,
                        "expression_intensity": 1.0,
                        "timestamp": 0.0,  # Nested events need their own timestamp
                    },
                    {
                        "event_type": "audio",
                        "audio_data": sound_data,
                        "audio_format": "mp3",
                        "duration": duration,
                        "timestamp": 0.0,
                    },
                ],
            },
        )

        await self.call_mcp_tool(self.vc_url, "play_sequence", {})

        await asyncio.sleep(duration + 0.5)


async def main():
    """Example usage of the integration."""

    async with VirtualCharacterWithVoice() as vc:
        # Example 1: Simple greeting
        print("\n=== Example 1: Simple Greeting ===")
        await vc.create_talking_sequence(
            text="Hello! I'm your virtual assistant. How can I help you today?", emotion="happy", gesture="wave"
        )

        # Example 2: Emotional response
        print("\n=== Example 2: Emotional Response ===")
        await vc.create_talking_sequence(
            text="Oh no! [worried] That sounds really challenging. [sympathetic] Let me help you with that.",
            emotion="sad",
            gesture="none",
            pre_delay=0.3,
            post_delay=0.5,
        )

        # Example 3: Excited announcement
        print("\n=== Example 3: Excited Announcement ===")
        await vc.create_talking_sequence(
            text="[excited] Great news everyone! [happy] We just reached our goal! [cheering]",
            emotion="excited",
            gesture="clap",
        )

        # Example 4: Sound effect with emotion
        print("\n=== Example 4: Laughing ===")
        await vc.express_emotion_with_sound(emotion="happy", sound_effect="cheerful laughter", duration=2.0)

        # Example 5: Complex sequence
        print("\n=== Example 5: Complex Story ===")

        # Create a longer sequence with multiple parts
        await vc.call_mcp_tool(
            vc.vc_url, "create_sequence", {"name": "story_sequence", "description": "A short story with multiple emotions"}
        )

        # Part 1: Introduction (0-3s)
        await vc.call_mcp_tool(
            vc.vc_url,
            "add_sequence_event",
            {"event_type": "animation", "timestamp": 0.0, "animation_params": {"emotion": "neutral", "gesture": "wave"}},
        )

        # Part 2: Happy moment (3-6s)
        await vc.call_mcp_tool(
            vc.vc_url,
            "add_sequence_event",
            {"event_type": "expression", "timestamp": 3.0, "expression": "happy", "expression_intensity": 1.0},
        )

        # Part 3: Surprised reaction (6-9s)
        await vc.call_mcp_tool(
            vc.vc_url,
            "add_sequence_event",
            {
                "event_type": "animation",
                "timestamp": 6.0,
                "animation_params": {"emotion": "surprised", "gesture": "none", "parameters": {"jump": True}},
            },
        )

        # Part 4: Return to neutral (9s+)
        await vc.call_mcp_tool(
            vc.vc_url, "add_sequence_event", {"event_type": "expression", "timestamp": 9.0, "expression": "neutral"}
        )

        # Play the complex sequence
        await vc.call_mcp_tool(vc.vc_url, "play_sequence", {})

        print("Story sequence playing...")
        await asyncio.sleep(10)

        print("\n=== All examples complete! ===")


if __name__ == "__main__":
    asyncio.run(main())
