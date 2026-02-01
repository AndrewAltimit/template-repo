# Audio and Event Sequencing for Virtual Characters

## Overview

The Virtual Character MCP server now supports comprehensive audio playback and event sequencing, enabling AI agents to create rich, synchronized multimedia experiences. This allows for:

- **Audio Transmission**: Send audio data with lip-sync and expression metadata
- **Event Sequencing**: Build complex sequences of animations, audio, and movements
- **ElevenLabs Integration**: Seamless integration with ElevenLabs TTS for voice generation
- **Expression Tags**: Process emotion tags from audio generation for synchronized expressions

## New Features

### 1. Audio Support

#### Send Audio Tool
```python
send_audio(
    audio_data: str,        # Base64-encoded audio or URL
    format: str = "mp3",    # Audio format (mp3, wav, opus, pcm)
    text: str = None,       # Optional transcript for lip-sync
    expression_tags: List[str] = None,  # ElevenLabs tags
    duration: float = None  # Audio duration in seconds
)
```

The audio system supports:
- Multiple audio formats (MP3, WAV, Opus, PCM)
- Viseme data for lip-sync animation
- Expression tags from ElevenLabs (e.g., `[laughs]`, `[whisper]`)
- Streaming audio with chunk support

### 2. Event Sequencing

#### Create Sequence
```python
create_sequence(
    name: str,
    description: str = None,
    loop: bool = False,
    interrupt_current: bool = True
)
```

#### Add Sequence Event
```python
add_sequence_event(
    event_type: str,        # animation, audio, wait, expression, movement, parallel
    timestamp: float,       # When to trigger (seconds)
    duration: float = None,
    # Event-specific parameters...
)
```

#### Sequence Control
- `play_sequence()` - Start playing the sequence
- `pause_sequence()` - Pause playback
- `resume_sequence()` - Resume from pause
- `stop_sequence()` - Stop and reset
- `get_sequence_status()` - Get current playback status

### 3. Event Types

#### Animation Event
Full animation data including emotions, gestures, and blend shapes:
```python
{
    "event_type": "animation",
    "timestamp": 0.0,
    "animation_params": {
        "emotion": "happy",
        "gesture": "wave",
        "emotion_intensity": 0.8
    }
}
```

#### Audio Event
Audio playback with optional metadata:
```python
{
    "event_type": "audio",
    "timestamp": 1.0,
    "audio_data": "base64_encoded_audio",
    "audio_format": "mp3",
    "duration": 3.0
}
```

#### Expression Event
Quick emotion change without full animation:
```python
{
    "event_type": "expression",
    "timestamp": 2.0,
    "expression": "surprised",
    "expression_intensity": 1.0
}
```

#### Movement Event
Control character movement:
```python
{
    "event_type": "movement",
    "timestamp": 3.0,
    "movement_params": {
        "move_forward": 0.5,
        "turn_speed": 0.2,
        "duration": 2.0
    }
}
```

#### Parallel Events
Execute multiple events simultaneously:
```python
{
    "event_type": "parallel",
    "timestamp": 0.0,
    "parallel_events": [
        {"event_type": "expression", "expression": "happy"},
        {"event_type": "audio", "audio_data": "..."}
    ]
}
```

## Usage Examples

### Basic Audio Playback
```python
# Send audio with expression
await send_audio(
    audio_data=base64_audio,
    format="mp3",
    text="Hello world!",
    expression_tags=["[happy]", "[excited]"],
    duration=2.5
)
```

### Simple Animation Sequence
```python
# Create sequence
await create_sequence(name="greeting", description="Friendly greeting")

# Add events
await add_sequence_event(
    event_type="animation",
    timestamp=0.0,
    animation_params={"emotion": "happy", "gesture": "wave"}
)

await add_sequence_event(
    event_type="audio",
    timestamp=0.5,
    audio_data=greeting_audio,
    duration=3.0
)

# Play sequence
await play_sequence()
```

### Complex Synchronized Performance
```python
# Create a performance with multiple synchronized elements
await create_sequence(name="performance", loop=False)

# Pre-delay
await add_sequence_event(event_type="wait", timestamp=0.0, wait_duration=0.5)

# Set initial mood
await add_sequence_event(
    event_type="expression",
    timestamp=0.5,
    expression="excited",
    expression_intensity=0.7
)

# Start audio and gesture together
await add_sequence_event(
    event_type="parallel",
    timestamp=1.0,
    parallel_events=[
        {
            "event_type": "audio",
            "audio_data": speech_audio,
            "duration": 5.0
        },
        {
            "event_type": "animation",
            "animation_params": {
                "gesture": "point",
                "parameters": {"look_horizontal": 0.3}
            }
        }
    ]
)

# Return to neutral
await add_sequence_event(
    event_type="expression",
    timestamp=6.0,
    expression="neutral"
)

await play_sequence()
```

## ElevenLabs Integration

The system seamlessly integrates with the ElevenLabs MCP server for voice generation:

```python
# Generate speech with ElevenLabs
audio_result = await elevenlabs.synthesize_speech_v3(
    text="Hello! [happy] How are you today? [curious]",
    voice_id="Rachel"
)

# Send to virtual character
await virtual_char.send_audio(
    audio_data=audio_result["audio_data"],
    text=audio_result["text"],
    expression_tags=["[happy]", "[curious]"],
    duration=audio_result["duration"]
)
```

### Expression Tag Mapping

ElevenLabs audio tags are automatically mapped to character expressions:

| Audio Tag | Character Expression |
|-----------|---------------------|
| `[laughs]` | Happy |
| `[whisper]` | Calm |
| `[sighs]` | Sad |
| `[angry]` | Angry |
| `[excited]` | Excited |
| `[surprised]` | Surprised |

## Backend Support

### VRChat Backend
- Full audio support via OSC parameters
- Bridge server integration for actual audio playback
- Viseme parameters for lip-sync
- Expression tag processing

### Mock Backend
- Complete audio simulation for testing
- Audio history tracking
- Event emission for monitoring

## Technical Details

### Audio Data Model
```python
@dataclass
class AudioData:
    data: bytes                    # Raw audio bytes
    sample_rate: int = 44100       # Sample rate
    channels: int = 1              # Number of channels
    format: str = "pcm"            # Audio format
    duration: float = 0.0          # Duration in seconds
    text: Optional[str] = None     # Transcript
    language: Optional[str] = None # Language code
    voice: Optional[str] = None    # Voice ID

    # New fields for enhanced audio
    viseme_timestamps: Optional[List[tuple[float, VisemeType, float]]] = None
    expression_tags: Optional[List[str]] = None
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    is_final_chunk: bool = True
```

### Event Sequence Model
```python
@dataclass
class EventSequence:
    name: str
    description: Optional[str]
    events: List[SequenceEvent]
    total_duration: Optional[float]
    loop: bool = False
    interrupt_current: bool = True
    priority: int = 0
```

## Performance Considerations

1. **Event Timing**: Events are processed at 20Hz (50ms intervals)
2. **Audio Streaming**: Large audio files can be streamed in chunks
3. **Parallel Events**: Use parallel events for synchronized actions
4. **Bridge Server**: For actual audio playback in VRChat, use the bridge server

## Testing

Run the test suite to verify functionality:

```bash
# Start the server
python -m mcp_virtual_character.server

# Run tests
python tools/mcp/mcp_virtual_character/scripts/test_audio_sequences.py
```

## Future Enhancements

- [ ] Real-time viseme generation from audio
- [ ] Advanced lip-sync with phoneme detection
- [ ] Multi-voice dialogue support
- [ ] Spatial audio positioning
- [ ] Voice effect processing (reverb, pitch shift)
- [ ] Gesture generation from speech patterns
