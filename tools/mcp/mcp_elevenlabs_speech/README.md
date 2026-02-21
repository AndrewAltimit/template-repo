# ElevenLabs Speech MCP Server (Rust)

> A Model Context Protocol server for ElevenLabs text-to-speech synthesis. Supports expressive audio tags, voice presets, sound effect generation, and multiple output formats.

## Overview

This MCP server provides tools for ElevenLabs text-to-speech:

- Speech synthesis with the v3 model's expressive audio tags (`[laughs]`, `[whisper]`, etc.)
- Sound effect generation from text descriptions (up to 22 seconds)
- Voice management with 10 built-in presets for common use cases
- Multiple models: v3 (most expressive), multilingual v2 (29 languages), flash v2.5 (low latency)
- Multiple output formats (MP3, PCM at various bitrates/sample rates)
- Local audio caching and organized output directory

## Quick Start

```bash
# Build from source
cd tools/mcp/mcp_elevenlabs_speech
cargo build --release

# Run in STDIO mode (for Claude Code)
ELEVENLABS_API_KEY=your_key ./target/release/mcp-elevenlabs-speech --mode stdio

# Run in standalone HTTP mode
ELEVENLABS_API_KEY=your_key ./target/release/mcp-elevenlabs-speech --mode standalone --port 8018

# Test health
curl http://localhost:8018/health
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `synthesize_speech` | Synthesize speech from text | `text` (required), `voice_id`, `model`, `output_format`, `preset`, `stability`, `similarity_boost`, `style`, `language_code` |
| `generate_sound_effect` | Generate sound effects from descriptions | `prompt` (required), `duration_seconds` |
| `list_voices` | List all available ElevenLabs voices | None |
| `get_user_subscription` | Get subscription info and character usage | None |
| `get_models` | Get available models and capabilities | None |
| `list_presets` | List voice presets with settings | None |
| `clear_cache` | Clear the local audio cache | None |

### Example: Synthesize Speech

```json
{
  "tool": "synthesize_speech",
  "arguments": {
    "text": "[excited] The build passed! [laughs] Finally!",
    "voice_id": "rachel",
    "model": "eleven_v3",
    "preset": "github_review"
  }
}
```

### Example: Generate Sound Effect

```json
{
  "tool": "generate_sound_effect",
  "arguments": {
    "prompt": "mechanical keyboard typing rapidly",
    "duration_seconds": 3.0
  }
}
```

## Voice Presets

| Preset | Stability | Similarity | Style | Use Case |
|--------|-----------|------------|-------|----------|
| `audiobook` | 0.75 | 0.75 | 0.0 | Long-form narration |
| `character_performance` | 0.30 | 0.80 | 0.6 | Expressive characters |
| `news_reading` | 0.90 | 0.70 | 0.0 | Professional delivery |
| `emotional_dialogue` | 0.50 | 0.85 | 0.3 | Dramatic conversations |
| `github_review` | 0.60 | 0.80 | 0.2 | Code review narration |
| `tutorial_narration` | 0.70 | 0.75 | 0.1 | Educational content |
| `podcast` | 0.50 | 0.80 | 0.4 | Conversational content |
| `meditation` | 0.85 | 0.70 | 0.0 | Calm, steady delivery |
| `storytelling` | 0.40 | 0.75 | 0.5 | Narrative content |
| `customer_service` | 0.80 | 0.75 | 0.0 | Professional, neutral |

## Audio Tags (v3 Model Only)

The v3 model supports expressive audio tags inline with text:

| Tag | Effect |
|-----|--------|
| `[laughs]` | Laughter |
| `[sighs]` | Sighing |
| `[whisper]` | Whispered speech |
| `[excited]` | Excited delivery |
| `[sad]` | Sad delivery |
| `[angry]` | Angry delivery |

## Default Voices

| Name | Description |
|------|-------------|
| `rachel` | Female, American, warm and clear |
| `george` | Male, British, warm narrator |
| `sarah` | Female, American, soft and friendly |
| `charlie` | Male, Australian, casual |
| `emily` | Female, American, calm narrator |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | (required) | ElevenLabs API key |
| `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` | Default voice model |
| `ELEVENLABS_DEFAULT_VOICE` | `rachel` | Default voice name or ID |

### Output Locations

- Cache: `/tmp/elevenlabs_cache/`
- Outputs: `~/elevenlabs_outputs/{YYYY-MM-DD}/`

## MCP Configuration

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "elevenlabs-speech": {
      "command": "mcp-elevenlabs-speech",
      "args": ["--mode", "stdio"],
      "env": {
        "ELEVENLABS_API_KEY": "your_key_here"
      }
    }
  }
}
```

## Project Structure

```
tools/mcp/mcp_elevenlabs_speech/
├── Cargo.toml          # Package configuration
├── README.md           # This file
├── docs/
│   └── README.md       # Detailed tool documentation
└── src/
    ├── main.rs         # CLI entry point
    ├── server.rs       # MCP tools implementation (7 tools)
    ├── client.rs       # ElevenLabs HTTP API client
    └── types.rs        # Data types (models, formats, presets, voices)
```

## Dependencies

- [mcp-core](../mcp_core_rust/) - Rust MCP framework
- [reqwest](https://docs.rs/reqwest) - HTTP client for ElevenLabs API
- [tokio](https://tokio.rs/) - Async runtime with filesystem support
- [chrono](https://docs.rs/chrono) - Timestamps for audio file naming
- [dirs](https://docs.rs/dirs) - Home directory resolution for output path

## License

Part of the template-repo project. See repository LICENSE file.
