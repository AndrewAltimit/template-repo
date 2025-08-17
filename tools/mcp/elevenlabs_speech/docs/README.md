# ElevenLabs Speech MCP Server

Advanced speech synthesis using ElevenLabs v3 with full emotional expression, audio tags, and sound effects generation.

## Features

- 🎙️ **ElevenLabs v3 Integration** - Latest model with 74 language support
- 🎭 **Emotional Audio Tags** - [laughs], [whisper], [excited], and 50+ more
- 🔊 **Sound Effects** - Generate up to 22-second sound effects from text
- 🌐 **Multi-language** - Automatic language detection and optimization
- 💬 **Multi-character Dialogue** - Create conversations with different voices
- 🔄 **Streaming Support** - WebSocket and HTTP streaming for real-time synthesis
- 📤 **Auto-upload** - Share audio via free hosting services
- 🐙 **GitHub Integration** - Audio reviews and comments for PRs/issues

## Quick Start

### 1. Setup API Key

Get your API key from [ElevenLabs](https://elevenlabs.io/api) (Creator plan recommended).

Add to your `.env` file:
```bash
# Copy the example if you haven't already
cp .env.example .env

# Add your API key
echo 'ELEVENLABS_API_KEY=your_api_key_here' >> .env
```

### 2. Start the Server

```bash
# Run directly
python -m tools.mcp.elevenlabs_speech.server

# Or with Docker
docker-compose up -d mcp-elevenlabs-speech
```

### 3. Test the Server

```bash
python tools/mcp/elevenlabs_speech/scripts/test_server.py
```

## MCP Tools

### Primary Synthesis

#### `synthesize_speech_v3`
Generate speech with full v3 capabilities and audio tags.

```python
{
    "text": "[excited] Hello world! [laughs] This is amazing!",
    "voice_id": "Rachel",  # or use voice ID
    "voice_settings": {
        "stability": 0.5,      # 0-1 (Creative/Natural/Robust)
        "similarity_boost": 0.75,
        "style": 0.3,          # Style exaggeration
        "use_speaker_boost": false
    },
    "model": "eleven_v3",      # or eleven_multilingual_v2, eleven_flash_v2
    "output_format": "mp3_44100_128",
    "language_code": "en",     # Optional, auto-detect if not provided
    "upload": true,            # Auto-upload to hosting
    "stream": false            # Use streaming
}
```

#### `synthesize_emotional`
Generate speech with emotional context.

```python
{
    "text": "I can't believe this happened!",
    "emotions": ["excited", "happy"],
    "voice_id": "Rachel",
    "intensity": "natural"  # subtle, natural, exaggerated
}
```

#### `synthesize_dialogue`
Create multi-character conversations.

```python
{
    "script": [
        {
            "character": "Rachel",
            "text": "Did you hear the news?",
            "tags": ["[excited]", "[curious]"]
        },
        {
            "character": "Josh",
            "text": "[gasps] No way! Tell me everything!",
            "overlap_previous": false
        }
    ],
    "mix_audio": true
}
```

### Sound Effects

#### `generate_sound_effect`
Create sound effects from text descriptions (max 22 seconds).

```python
{
    "prompt": "thunderstorm with heavy rain on a metal roof",
    "duration_seconds": 10.0,
    "upload": true
}
```

### GitHub Integration

#### `generate_pr_audio_response`
Create audio review for pull requests.

```python
{
    "review_text": "Great implementation! The error handling is solid.",
    "tone": "professional",  # professional, friendly, constructive, enthusiastic
    "add_intro": true,
    "add_outro": true,
    "pr_number": 123
}
```

Returns formatted GitHub comment:
```markdown
🎤 [Audio Review (2:34)](https://0x0.st/audio_123.mp3)
```

### Voice Management

#### `list_available_voices`
Get all available voices with details.

#### `set_voice_preset`
Apply optimized settings for use cases.

```python
{
    "preset": "github_review"  # audiobook, character_performance, podcast, etc.
}
```

### Audio Tag Tools

#### `parse_audio_tags`
Parse and validate tags in text.

```python
{
    "text": "[happy] Hello! [laughs] This is great!"
}
```

#### `suggest_audio_tags`
Get tag suggestions based on text content.

```python
{
    "text": "Oh no! This is terrible!",
    "context": "github_review"
}
```

## Audio Tags Reference

### Emotions
- `[happy]`, `[sad]`, `[angry]`, `[excited]`, `[nervous]`
- `[cheerful]`, `[playful]`, `[regretful]`, `[resigned tone]`
- `[curious]`, `[confused]`, `[thoughtful]`, `[sarcastic]`

### Reactions
- `[laughs]`, `[laughs harder]`, `[starts laughing]`, `[chuckles]`
- `[sighs]`, `[SIGH]`, `[crying]`, `[sobbing]`
- `[gasps]`, `[gulps]`, `[clears throat]`
- `[hesitates]`, `[stammers]`, `[breathes]`

### Delivery Styles
- `[WHISPER]`, `[whispers]` - Soft speech
- `[SHOUTING]`, `[shouts]` - Loud speech
- `[murmuring]`, `[mutters]` - Quiet speech
- `[announcing]`, `[narrating]` - Clear delivery

### Pacing
- `[rushed]`, `[slows down]`, `[deliberate]`
- `[rapid-fire]`, `[drawn out]`, `[pause]`
- `[timidly]`, `[confidently]`, `[uncertainly]`

### Accents
- `[American accent]`, `[British accent]`, `[Australian accent]`
- `[French accent]`, `[German accent]`, `[Spanish accent]`
- `[pirate voice]`, `[robot voice]`

### Environmental
- `[gunshot]`, `[explosion]`, `[clapping]`
- `[door slam]`, `[footsteps]`, `[thunder]`

### Layered Examples
```
[nervously][whispers] "I don't think we should be here..."
[happily][shouts][laughs] "We did it!"
[sad][crying][slows down] "It's... it's over."
```

## Voice Settings Guide

### Stability Modes

- **Creative (0.3)** - More expressive but may hallucinate
- **Natural (0.5)** - Balanced, closest to original voice
- **Robust (0.9)** - Very stable but less responsive to tags

### Presets

| Preset | Stability | Similarity | Style | Use Case |
|--------|-----------|------------|-------|----------|
| `audiobook` | 0.75 | 0.75 | 0.0 | Long-form narration |
| `character_performance` | 0.3 | 0.8 | 0.6 | Games, animations |
| `github_review` | 0.6 | 0.8 | 0.2 | Code reviews |
| `emotional_dialogue` | 0.5 | 0.85 | 0.3 | Expressive conversations |
| `podcast` | 0.5 | 0.8 | 0.4 | Conversational content |
| `news_reading` | 0.9 | 0.7 | 0.0 | Professional delivery |

## Configuration

### Environment Variables

```bash
# Required
ELEVENLABS_API_KEY=your_api_key

# Optional - Models and Voices
ELEVENLABS_DEFAULT_MODEL=eleven_v3
ELEVENLABS_DEFAULT_VOICE=Rachel

# Optional - Voice Settings
ELEVENLABS_DEFAULT_STABILITY=0.5
ELEVENLABS_DEFAULT_SIMILARITY=0.75
ELEVENLABS_DEFAULT_STYLE=0.0
ELEVENLABS_SPEAKER_BOOST=false

# Optional - Streaming
ELEVENLABS_WEBSOCKET_ENABLED=true
ELEVENLABS_CHUNK_SCHEDULE=[120,160,250,290]

# Optional - Cache
ELEVENLABS_CACHE_DIR=/tmp/elevenlabs_cache
ELEVENLABS_MAX_CACHE_SIZE_GB=10

# Optional - Upload
AUDIO_UPLOAD_SERVICE=auto
AUDIO_UPLOAD_MAX_SIZE_MB=50
```

### Config File

Create `elevenlabs-config.json`:
```json
{
    "api_key": "your_api_key",
    "default_model": "eleven_v3",
    "default_voice": "Rachel",
    "default_stability": 0.5,
    "default_similarity": 0.75,
    "default_style": 0.0,
    "speaker_boost": false
}
```

## GitHub Integration Examples

### Audio PR Review

```python
# Generate review audio
result = mcp_client.call_tool(
    "generate_pr_audio_response",
    {
        "review_text": """
        Great work on this implementation! [cheerfully]

        The error handling looks solid. [thoughtfully]
        I particularly like how you've structured the validation.

        [concerned] One thing to consider: the timeout might be too short.

        [enthusiastic] Overall, this is ready to merge after that small fix!
        """,
        "tone": "constructive",
        "add_intro": true,
        "add_outro": true
    }
)

# Post to GitHub
gh pr comment 123 --body "
## 🎤 Audio Review Available

[Listen to Full Review](${result.audio_url}) (2:34)

### Key Points:
- ✅ Solid error handling
- 📝 Good validation structure
- ⚠️ Consider timeout adjustment

Great work overall! 🎉
"
```

### Multiple Voice Reactions

```python
# Generate different reactions
excited = synthesize("This approach is brilliant!", emotions=["excited"])
concern = synthesize("The performance impact worries me.", tags=["[concerned][thoughtfully]"])
suggestion = synthesize("What if we tried caching?", tags=["[curious]"])

# Format comment
comment = f"""
### 🎧 Audio Feedback

- 🎉 [Excited about the approach!]({excited.url})
- 🤔 [Performance concerns]({concern.url})
- 💡 [Alternative suggestion]({suggestion.url})
"""
```

## Advanced Usage

### Streaming Real-time Synthesis

```python
# WebSocket streaming for long text
config = {
    "text": long_text,
    "voice_id": "Rachel",
    "chunk_schedule": [120, 160, 250, 290],
    "auto_flush": true
}

async for audio_chunk in client.stream_speech_realtime(config):
    # Process audio chunks as they arrive
    play_audio_chunk(audio_chunk)
```

### Creating Audio Scenes

```python
# Combine speech with effects
scene = {
    "elements": [
        {
            "type": "effect",
            "content": "coffee shop ambience",
            "timing": {"start_ms": 0, "duration_ms": 10000},
            "volume": 0.3
        },
        {
            "type": "speech",
            "content": "[thoughtfully] I've been thinking about your proposal...",
            "voice_id": "Rachel",
            "timing": {"start_ms": 1000},
            "volume": 1.0
        }
    ],
    "normalize": true
}
```

## Models Comparison

| Model | Languages | Speed | Quality | Audio Tags | Use Case |
|-------|-----------|-------|---------|------------|----------|
| `eleven_v3` | 74 | Medium | Highest | Full support | Expressive content |
| `eleven_multilingual_v2` | 29 | Medium | High | Limited | Multi-language |
| `eleven_flash_v2_5` | 32 | Fast | Good | Limited | Quick generation |
| `eleven_turbo_v2_5` | 28 | Fastest | Good | Limited | Real-time/streaming |

## Troubleshooting

### No API Key Error
```bash
# Check if key is set
echo $ELEVENLABS_API_KEY

# Run setup script
python tools/mcp/elevenlabs_speech/scripts/setup_api_key.py
```

### Rate Limiting
- Creator plan: 500,000 characters/month
- Use caching for repeated synthesis
- Implement retry logic with backoff

### Audio Tags Not Working
- Ensure using `eleven_v3` model
- Check stability setting (lower = more expressive)
- Some tags work better with specific voices

### Upload Failures
- Check file size (<50MB)
- Try different service: `0x0st`, `tmpfiles`, `fileio`
- Verify network connectivity

## Links

- [ElevenLabs API Docs](https://elevenlabs.io/docs/api-reference)
- [Get API Key](https://elevenlabs.io/api)
- [Voice Library](https://elevenlabs.io/voice-library)
- [Pricing Plans](https://elevenlabs.io/pricing)
