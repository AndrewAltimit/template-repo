# Virtual Character + ElevenLabs Integration Guide

This guide demonstrates how to combine the Virtual Character MCP server with ElevenLabs Speech synthesis to create expressive, talking virtual characters with synchronized animation and emotion.

> **Note**: The Virtual Character MCP Server has been migrated to Rust. The integration
> concepts remain the same, but the server is now run as a Rust binary via Docker Compose.

## Overview

The integration enables:
- **Expressive Speech**: Generate natural-sounding voice with emotional nuance
- **Synchronized Animation**: Automatic emotion and lip-sync from audio
- **Performance Sequencing**: Build complex multimedia performances
- **Cross-Platform Support**: Works with VRChat, Blender, Unity, and more

## Architecture

```
ElevenLabs TTS → Audio + Tags → Virtual Character → Backend Platform
                       ↓                                    ↓
               Expression Mapping                    VRChat/Blender/Unity
                       ↓                                    ↓
               Emotion + Visemes                    Avatar Animation
```

## Quick Start

### 1. Start Both MCP Servers

```bash
# Terminal 1: Start Virtual Character server (Rust binary via Docker)
docker compose --profile virtual-character up mcp-virtual-character

# Terminal 2: Start ElevenLabs server
docker compose --profile services run --rm -T mcp-elevenlabs-speech
```

The Virtual Character HTTP server will be available at `http://localhost:8025`.

### 2. Basic Integration Example

The following example shows how to integrate with the servers via HTTP:

```python
import asyncio
import aiohttp
import base64

async def speak_with_character():
    async with aiohttp.ClientSession() as session:
        # Step 1: Generate speech with ElevenLabs
        elevenlabs_response = await session.post(
            "http://localhost:8018/mcp/execute",
            json={
                "tool": "synthesize_speech_v3",
                "params": {
                    "text": "Hello! [laughs] I'm so excited to meet you [whisper] it's been a while.",
                    "voice_id": "Sarah",
                    "model": "eleven_v3"
                }
            }
        )
        audio_result = await elevenlabs_response.json()

        # Step 2: Send to Virtual Character
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "send_audio",
                "params": {
                    "audio_data": audio_result["audio_base64"],
                    "expression_tags": ["laughs", "whisper"],
                    "text": audio_result["text"],
                    "format": "mp3"
                }
            }
        )

asyncio.run(speak_with_character())
```

## Advanced Features

### Creating Complex Performances

```python
async def create_storytelling_performance():
    async with aiohttp.ClientSession() as session:
        # Create a new sequence
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "create_sequence",
                "params": {
                    "name": "storytelling_intro",
                    "description": "Animated story introduction"
                }
            }
        )

        # Add initial gesture
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "add_sequence_event",
                "params": {
                    "event_type": "animation",
                    "timestamp": 0,
                    "animation_params": {
                        "gesture": "wave",
                        "emotion": "happy",
                        "emotion_intensity": 0.7
                    }
                }
            }
        )

        # Generate narration with emotions
        narration = await generate_elevenlabs_audio(
            "Once upon a time [dramatic_pause] in a land far, far away [whisper] "
            "there lived a brave knight [heroic] who loved to [laughs] tell jokes!"
        )

        # Add audio event
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "add_sequence_event",
                "params": {
                    "event_type": "audio",
                    "timestamp": 1.0,
                    "audio_data": narration["base64"],
                    "expression_tags": ["dramatic_pause", "whisper", "heroic", "laughs"],
                    "sync_with_audio": True
                }
            }
        )

        # Add movement during speech
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "add_sequence_event",
                "params": {
                    "event_type": "movement",
                    "timestamp": 5.0,
                    "movement_params": {
                        "move_forward": 0.3,
                        "duration": 2.0
                    }
                }
            }
        )

        # Play the sequence
        await session.post(
            "http://localhost:8020/mcp/execute",
            json={
                "tool": "play_sequence",
                "params": {}
            }
        )
```

### Emotional Dialogue System

```python
async def emotional_conversation(emotion_state="neutral"):
    """Create dynamic conversations with emotional progression"""

    dialogue_segments = [
        {
            "text": "I need to tell you something important.",
            "emotion": "serious",
            "tags": ["deep_breath"]
        },
        {
            "text": "[sighs] It's been on my mind for a while.",
            "emotion": "sad",
            "tags": ["sighs"]
        },
        {
            "text": "But you know what? [laughs] I realized it doesn't matter!",
            "emotion": "happy",
            "tags": ["laughs"]
        }
    ]

    for segment in dialogue_segments:
        # Generate audio with appropriate voice settings
        audio = await generate_with_emotion(
            text=segment["text"],
            emotion=segment["emotion"]
        )

        # Send to character with emotion transition
        await send_to_character(
            audio_data=audio,
            emotion=segment["emotion"],
            expression_tags=segment["tags"]
        )

        # Wait for audio to finish
        await asyncio.sleep(audio["duration"])
```

## Expression Tag Mapping

The system automatically maps ElevenLabs expression tags to character emotions:

| ElevenLabs Tag | Character Emotion | Animation Effect |
|----------------|-------------------|------------------|
| `[laughs]` | happy | Smile, eye squint |
| `[sighs]` | sad | Downcast eyes, slight frown |
| `[whisper]` | neutral | Lean forward slightly |
| `[shouts]` | angry | Wide eyes, open mouth |
| `[gasps]` | surprised | Wide eyes, raised eyebrows |
| `[coughs]` | neutral | Cover mouth gesture |
| `[clears throat]` | neutral | Straighten posture |

## Platform-Specific Considerations

### VRChat Integration

```python
# VRChat requires remote bridge server on Windows
await session.post(
    "http://localhost:8020/mcp/execute",
    json={
        "tool": "set_backend",
        "params": {
            "backend": "vrchat_remote",
            "config": {
                "remote_host": "192.168.1.100",  # Windows VRChat machine
                "osc_out_port": 9000,
                "use_vrcemote": True  # Use emote system for gestures
            }
        }
    }
)
```

### Blender Integration

```python
# Blender backend for rendering performances
await session.post(
    "http://localhost:8020/mcp/execute",
    json={
        "tool": "set_backend",
        "params": {
            "backend": "blender",
            "config": {
                "project_path": "/path/to/character.blend",
                "auto_render": True
            }
        }
    }
)
```

## Best Practices

### 1. Audio Quality Settings

```python
# Optimize for character voice
audio_settings = {
    "model": "eleven_v3",  # Best quality model
    "voice_settings": {
        "stability": 0.5,      # Natural variation
        "similarity": 0.75,    # Voice consistency
        "style": 0.4,          # Expressive delivery
        "use_speaker_boost": True
    }
}
```

### 2. Performance Optimization

- **Pre-generate Audio**: Generate all audio segments before performance
- **Use Sequences**: Build complete performances offline for smooth playback
- **Cache Audio**: Reuse common phrases and expressions
- **Batch Operations**: Send multiple events in a single sequence

### 3. Emotional Consistency

```python
# Maintain emotional state across segments
class EmotionalContext:
    def __init__(self):
        self.current_emotion = "neutral"
        self.emotion_history = []

    def transition_to(self, new_emotion, intensity=1.0):
        """Smooth emotion transitions"""
        if self.current_emotion != new_emotion:
            # Add transition event
            transition_duration = 0.5
            return {
                "from": self.current_emotion,
                "to": new_emotion,
                "duration": transition_duration,
                "intensity": intensity
            }
```

## Troubleshooting

### Common Issues

1. **Audio Not Playing**
   - Check backend audio support
   - Verify audio format compatibility
   - Ensure audio data is properly base64 encoded

2. **Lip-Sync Not Working**
   - Confirm viseme support in backend
   - Check if text transcript is provided
   - Verify audio format is PCM or WAV for analysis

3. **Expression Tags Not Recognized**
   - Use standard ElevenLabs v3 tags
   - Check tag spelling and format
   - Verify backend emotion mapping

### Debug Mode

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test with mock backend first
await session.post(
    "http://localhost:8020/mcp/execute",
    json={
        "tool": "set_backend",
        "params": {"backend": "mock"}
    }
)
```

## Example Projects

### 1. AI Storyteller

Complete implementation in `tools/mcp/virtual_character/examples/storyteller.py`

### 2. Virtual Assistant

See `tools/mcp/virtual_character/examples/assistant.py`

### 3. Educational Presenter

Available at `tools/mcp/virtual_character/examples/educator.py`

## API Reference

### ElevenLabs Tools
- `synthesize_speech_v3` - Generate speech with expression tags
- `synthesize_emotional` - Add emotional context
- `synthesize_dialogue` - Multi-character dialogue

### Virtual Character Tools
- `send_audio` - Transmit audio with metadata
- `create_sequence` - Build performance sequences
- `add_sequence_event` - Add synchronized events
- `play_sequence` - Execute performances

## Resources

- [Virtual Character Documentation](../../../tools/mcp/mcp_virtual_character/README.md)
- [ElevenLabs Speech Documentation](../../../tools/mcp/mcp_elevenlabs_speech/docs/README.md)
- [Audio Sequencing Guide](../../../tools/mcp/mcp_virtual_character/docs/AUDIO_SEQUENCING.md)
- [VRChat Setup Guide](../../../tools/mcp/mcp_virtual_character/docs/VRCHAT_SETUP.md)
