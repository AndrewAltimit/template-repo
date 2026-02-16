# Virtual Character + ElevenLabs Integration Guide

This guide demonstrates how to combine the Virtual Character MCP server with ElevenLabs Speech synthesis to create expressive, talking virtual characters with synchronized animation and emotion.

> **Implementation**: Both MCP servers are implemented in Rust. The Virtual Character server
> lives at `tools/mcp/mcp_virtual_character/` and exposes 16 MCP tools for animation, audio,
> sequences, and state management.

## Overview

The integration enables:
- **Expressive Speech**: Generate natural-sounding voice with emotional nuance via 50+ ElevenLabs expression tags
- **Synchronized Animation**: Automatic emotion and lip-sync from audio via OSC protocol
- **Performance Sequencing**: Build complex multimedia performances with parallel event execution
- **Cross-Platform Support**: Pluggable backend system (VRChat via OSC, Mock for testing)

## Architecture

```
ElevenLabs TTS --> Audio + Tags --> Virtual Character MCP --> Backend Platform
                       |                                          |
               Expression Mapping                          VRChat (OSC/UDP)
                       |                                          |
               Emotion + Visemes                          Avatar Animation
```

## Quick Start

### 1. Start Both MCP Servers

```bash
# Terminal 1: Start Virtual Character server (Rust binary via Docker)
docker compose --profile virtual-character up mcp-virtual-character

# Terminal 2: Start ElevenLabs server
docker compose --profile services run --rm -T mcp-elevenlabs-speech
```

### 2. Basic Integration (MCP Tool Calls)

AI agents interact with the Virtual Character via MCP tool calls. Here is the typical flow:

```json
// Step 1: Generate speech with ElevenLabs (elevenlabs-speech MCP)
{
  "tool": "synthesize_speech_v3",
  "params": {
    "text": "Hello! [laughs] I'm so excited to meet you [whisper] it's been a while.",
    "voice_id": "Sarah",
    "model": "eleven_v3"
  }
}

// Step 2: Play audio on character (virtual-character MCP)
{
  "tool": "play_audio",
  "params": {
    "audio_data": "<base64 audio or file path>",
    "format": "mp3",
    "text": "Hello! I'm so excited to meet you, it's been a while."
  }
}
```

## Advanced Features

### Creating Complex Performances

```json
// 1. Create a new sequence
{"tool": "create_sequence", "params": {
  "name": "storytelling_intro",
  "description": "Animated story introduction"
}}

// 2. Add initial gesture
{"tool": "add_sequence_event", "params": {
  "event_type": "animation",
  "timestamp": 0.0,
  "gesture": "wave",
  "emotion": "happy",
  "emotion_intensity": 0.7
}}

// 3. Add audio event with expression sync
{"tool": "add_sequence_event", "params": {
  "event_type": "audio",
  "timestamp": 1.0,
  "audio_data": "<base64 narration audio>",
  "sync_with_audio": true
}}

// 4. Add movement during speech
{"tool": "add_sequence_event", "params": {
  "event_type": "movement",
  "timestamp": 5.0,
  "move_forward": 0.3,
  "duration": 2.0
}}

// 5. Play the sequence
{"tool": "play_sequence", "params": {}}
```

### Emotional Dialogue System

For dynamic conversations with emotional progression, chain multiple MCP tool calls:

```json
// Segment 1: Set serious emotion, play audio
{"tool": "send_animation", "params": {
  "emotion": "neutral", "emotion_intensity": 0.8, "gesture": "none"
}}
{"tool": "play_audio", "params": {
  "audio_data": "<audio for: I need to tell you something important>",
  "text": "I need to tell you something important."
}}

// Segment 2: Transition to sadness
{"tool": "send_animation", "params": {
  "emotion": "sad", "emotion_intensity": 0.6
}}
{"tool": "play_audio", "params": {
  "audio_data": "<audio for: [sighs] It's been on my mind>",
  "text": "[sighs] It's been on my mind for a while."
}}

// Segment 3: Transition to happiness
{"tool": "send_animation", "params": {
  "emotion": "happy", "emotion_intensity": 0.9, "gesture": "cheer"
}}
{"tool": "play_audio", "params": {
  "audio_data": "<audio for: [laughs] I realized it doesn't matter!>",
  "text": "But you know what? [laughs] I realized it doesn't matter!"
}}
```

## Expression Tag Mapping

The Rust server automatically maps ElevenLabs expression tags to character emotions (50+ mappings in `src/audio_emotion_mappings.rs`):

| ElevenLabs Tag | Character Emotion | Intensity | Animation Effect |
|----------------|-------------------|-----------|------------------|
| `[laughs]` | Happy | 0.8 | Smile, Cheer VRCEmote |
| `[sighs]` | Sad | 0.6 | Sadness VRCEmote |
| `[whisper]` | Calm | 0.5 | Lean forward slightly |
| `[shouts]` / `[yelling]` | Angry | 0.9 | Wide eyes, open mouth |
| `[gasps]` | Surprised | 0.8 | Wide eyes, raised eyebrows |
| `[nervously]` | Fearful | 0.6 | Shrinking posture |
| `[excited]` | Excited | 0.9 | Dance VRCEmote |
| `[calmly]` | Calm | 0.7 | Relaxed neutral pose |

## Platform-Specific Considerations

### VRChat Integration

```json
// Connect to VRChat via OSC (requires VRChat on Windows)
{"tool": "set_backend", "params": {
  "backend": "vrchat_remote",
  "config": {
    "remote_host": "192.168.1.100",
    "osc_in_port": 9000,
    "osc_out_port": 9001,
    "use_vrcemote": true
  }
}}
```

The VRChat backend communicates via OSC over UDP with bidirectional support:
- **Outbound**: Emotion, gesture, movement, and audio state parameters
- **Inbound**: Avatar parameter tracking from VRChat
- **VRCEmote Toggle**: Sending same emote value twice turns it off

### Mock Backend (Testing)

```json
// Use mock backend for development without VRChat
{"tool": "set_backend", "params": {
  "backend": "mock"
}}

// Mock backend tracks all animation/audio history for assertions
{"tool": "get_backend_status", "params": {}}
```

## Best Practices

### 1. Audio Quality Settings

```json
// ElevenLabs v3 optimal settings for character voice
{
  "model": "eleven_v3",
  "voice_settings": {
    "stability": 0.5,
    "similarity": 0.75,
    "style": 0.4,
    "use_speaker_boost": true
  }
}
```

### 2. Performance Optimization

- **Pre-generate Audio**: Generate all audio segments before starting a sequence
- **Use Sequences**: Build complete performances with `create_sequence` for smooth playback
- **Parallel Events**: Use `event_type: "parallel"` to synchronize animation with audio
- **Batch Operations**: Add all events to a sequence before calling `play_sequence`

### 3. Emotional Consistency

The PAD (Pleasure-Arousal-Dominance) model in the Rust server enables smooth emotion interpolation:

```rust
// From types.rs -- each emotion maps to a 3D vector
impl EmotionType {
    pub fn to_pad_vector(&self) -> (f32, f32, f32) {
        match self {
            EmotionType::Happy     => ( 0.8,  0.6,  0.2),
            EmotionType::Sad       => (-0.7, -0.3, -0.4),
            EmotionType::Angry     => (-0.6,  0.8,  0.6),
            EmotionType::Calm      => ( 0.3, -0.6,  0.1),
            // ...
        }
    }
}
```

The `lerp()` method enables smooth transitions between emotional states.

## Troubleshooting

### Common Issues

1. **Audio Not Playing**
   - Check backend connection with `get_backend_status`
   - Verify audio format (MP3, WAV, OGG, FLAC supported via magic byte detection)
   - Ensure audio data is properly base64 encoded or a valid file path

2. **Lip-Sync Not Working**
   - Confirm VRChat OSC is enabled in settings
   - Set VRChat to use virtual audio cable for mic input
   - VRChat handles lip-sync automatically from audio

3. **Expression Tags Not Recognized**
   - Use standard ElevenLabs v3 bracket syntax: `[laughs]`, `[sighs]`, etc.
   - Check `src/audio_emotion_mappings.rs` for the complete tag list
   - The server uses regex parsing to extract bracketed tags

### Debug Mode

```bash
# Run with debug logging
RUST_LOG=debug cargo run -p mcp-virtual-character

# Test with mock backend first
```

```json
{"tool": "set_backend", "params": {"backend": "mock"}}
{"tool": "send_animation", "params": {"emotion": "happy", "emotion_intensity": 0.8}}
{"tool": "get_backend_status", "params": {}}
```

## MCP Tools Reference

### Virtual Character Tools (16 total)

| Tool | Description |
|------|-------------|
| `set_backend` | Connect to backend (mock, vrchat_remote) |
| `list_backends` | List available backends |
| `get_backend_status` | Get backend status and statistics |
| `send_animation` | Send emotion + gesture + movement |
| `execute_behavior` | High-level behaviors (greet, dance, sit, stand) |
| `send_vrcemote` | Direct VRCEmote value (0-8) |
| `play_audio` | Play audio with lip-sync metadata |
| `create_sequence` | Create named event sequence |
| `add_sequence_event` | Add event to sequence |
| `play_sequence` | Start sequence playback |
| `pause_sequence` | Pause playback |
| `resume_sequence` | Resume from pause |
| `stop_sequence` | Stop playback |
| `get_sequence_status` | Query sequence state |
| `reset` | Clear emotes and reset to neutral |
| `panic_reset` | Emergency reset (stops everything) |

## Resources

- [Virtual Character Documentation](../../../tools/mcp/mcp_virtual_character/README.md)
- [ElevenLabs Speech Documentation](../../../tools/mcp/mcp_elevenlabs_speech/docs/README.md)
- [Audio Sequencing Guide](../../../tools/mcp/mcp_virtual_character/docs/AUDIO_SEQUENCING.md)
- [VRChat Setup Guide](../../../tools/mcp/mcp_virtual_character/docs/VRCHAT_SETUP.md)
