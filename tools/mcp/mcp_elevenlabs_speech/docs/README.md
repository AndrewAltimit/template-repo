# MCP ElevenLabs Speech Server

> High-quality text-to-speech synthesis using the ElevenLabs API with support for
> expressive audio tags, voice presets, and sound effect generation.

## Overview

This MCP server provides tools for ElevenLabs text-to-speech synthesis, including:

- **Speech synthesis** with v3 model support for expressive audio tags
- **Sound effect generation** from text descriptions
- **Voice management** with presets and customizable settings
- **Multiple output formats** (MP3, PCM)

## Requirements

- ElevenLabs API key (set via `ELEVENLABS_API_KEY` environment variable)
- Network access to ElevenLabs API

## Installation

The server is built as a standalone Rust binary:

```bash
# Build
cd tools/mcp/mcp_elevenlabs_speech
cargo build --release

# Run
ELEVENLABS_API_KEY=your_key ./target/release/mcp-elevenlabs-speech --mode standalone --port 8018
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | (required) | Your ElevenLabs API key |
| `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` | Default voice model |
| `ELEVENLABS_DEFAULT_VOICE` | `rachel` | Default voice name |

## Tools

### synthesize_speech

Synthesize speech from text with optional audio tags for expressive delivery.

**Parameters:**
- `text` (required): Text to synthesize. Supports audio tags like `[laughs]`, `[whisper]`, `[sighs]`
- `voice_id`: Voice ID or name (default: configured default)
- `model`: Voice model (`eleven_v3`, `eleven_multilingual_v2`, `eleven_flash_v2_5`)
- `output_format`: Audio format (`mp3_44100_128`, `pcm_24000`, etc.)
- `preset`: Voice preset for quick settings
- `stability`: Voice stability (0.0-1.0)
- `similarity_boost`: Voice similarity (0.0-1.0)
- `style`: Style exaggeration (0.0-1.0)
- `language_code`: Language code for multilingual models

**Example:**
```json
{
  "text": "[excited] Great news! The build passed!",
  "voice_id": "rachel",
  "model": "eleven_v3",
  "preset": "github_review"
}
```

### generate_sound_effect

Generate a sound effect from a text description.

**Parameters:**
- `prompt` (required): Description of the sound effect
- `duration_seconds`: Duration in seconds (0.5-22.0, default: 5.0)

**Example:**
```json
{
  "prompt": "mechanical keyboard typing rapidly",
  "duration_seconds": 3.0
}
```

### list_voices

List all available ElevenLabs voices with their IDs and metadata.

### get_user_subscription

Get subscription information including character usage and limits.

### get_models

Get available ElevenLabs models and their capabilities.

### list_presets

List available voice presets and their settings:

| Preset | Stability | Similarity | Style | Use Case |
|--------|-----------|------------|-------|----------|
| `audiobook` | 0.75 | 0.75 | 0.0 | Long-form narration |
| `character_performance` | 0.30 | 0.80 | 0.6 | Expressive characters |
| `github_review` | 0.60 | 0.80 | 0.2 | Code review feedback |
| `podcast` | 0.50 | 0.80 | 0.4 | Conversational content |
| `storytelling` | 0.40 | 0.75 | 0.5 | Narrative content |

### clear_cache

Clear the local audio cache directory.

## Audio Tags (v3 Model Only)

The v3 model supports expressive audio tags:

| Tag | Description |
|-----|-------------|
| `[laughs]` | Laughter |
| `[sighs]` | Sighing |
| `[whisper]` | Whispered speech |
| `[excited]` | Excited delivery |
| `[sad]` | Sad delivery |
| `[angry]` | Angry delivery |

**Example:**
```
[whisper] I have a secret... [laughs] Just kidding!
```

## Common Voice Names

| Name | Description |
|------|-------------|
| `rachel` | Female, American, warm and clear |
| `george` | Male, British, warm narrator |
| `sarah` | Female, American, soft and friendly |
| `charlie` | Male, Australian, casual |
| `emily` | Female, American, calm narrator |

## Output

Audio files are saved to:
- Cache: `/tmp/elevenlabs_cache/`
- Outputs: `~/elevenlabs_outputs/{date}/`

## API Endpoints

When running in standalone mode:

- `GET /health` - Health check
- `GET /mcp/tools` - List available tools
- `POST /mcp/tools/{tool_name}` - Execute a tool

## License

See [LICENSE](../../../../LICENSE) in repository root.
