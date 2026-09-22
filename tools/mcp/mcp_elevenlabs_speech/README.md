# ElevenLabs Speech MCP Server (Rust)

> MCP server that wraps the ElevenLabs API for text-to-speech and sound
> effect generation. Generated audio is saved to a local output directory and
> the tools return the file path.

## Features

- Text-to-speech with every current ElevenLabs TTS model (`eleven_v3` with
  inline audio tags, `eleven_multilingual_v2`, `eleven_flash_v2_5`, ...);
  new model IDs are passed through without a code change
- Voice names resolved against **your account's** voice list (cached for 10
  minutes), so `"voice_id": "George"` or a cloned voice's name works
- 10 built-in voice-settings presets; explicit settings override a preset
- Sound effects (0.5-30 s, looping, prompt influence)
- All 28 ElevenLabs output formats (MP3, Opus, WAV, raw PCM, u-law, A-law)
- Account tools: voices (with search/category filters), models, subscription usage
- Input validated before any request is sent (ranges, per-model text limits,
  voice ID charset); upstream errors surfaced with the ElevenLabs status/message
- The API key is only ever sent in the `xi-api-key` header and is redacted from
  every error message and `Debug` output

## Quick Start

```bash
cd tools/mcp/mcp_elevenlabs_speech
cargo build --release

# STDIO mode (Claude Code / .mcp.json)
ELEVENLABS_API_KEY=your_key ./target/release/mcp-elevenlabs-speech --mode stdio

# HTTP mode
ELEVENLABS_API_KEY=your_key ./target/release/mcp-elevenlabs-speech --mode standalone --port 8018
curl http://localhost:8018/health
curl http://localhost:8018/mcp/tools

# Docker (HTTP on 8018, audio written to ./outputs/elevenlabs_speech)
docker compose up -d mcp-elevenlabs-speech
```

CLI flags come from mcp-core: `--mode standalone|server|client|stdio`
(`http` is accepted as a legacy alias for `standalone`), `--port` (default
8000), `--log-level`. Logs go to stderr.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | unset | Required for every tool except `list_presets` and `clear_cache`; without it those tools return a clear error rather than failing at startup |
| `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3` | Model used when `model` is omitted |
| `ELEVENLABS_DEFAULT_VOICE` | `george` | Voice name or ID used when `voice_id` is omitted |
| `ELEVENLABS_OUTPUT_DIR` | - | Where audio is written (highest precedence) |
| `MCP_OUTPUT_DIR` | - | Used if `ELEVENLABS_OUTPUT_DIR` is unset (docker-compose sets `/output`) |
| (fallback) | `~/elevenlabs_outputs` | Used when neither variable is set |
| `ELEVENLABS_BASE_URL` | `https://api.elevenlabs.io` | API origin, e.g. a data-residency endpoint; a trailing `/v1` is stripped |
| `ELEVENLABS_TIMEOUT_SECS` | `120` | Total per-request HTTP timeout (connect timeout is 10 s) |
| `RUST_LOG` | `info` | Log filter |

Files are written as `<output_dir>/<YYYY-MM-DD>/speech_<timestamp>_<id>.<ext>`
(or `sfx_...`). Writes are atomic (temp file + rename).

## Tools

All tools return a JSON text payload. Failures from ElevenLabs, the network
or the filesystem return an `isError` result with
`{"success": false, "error": "..."}`. Invalid arguments (missing/wrong-typed
parameters, out-of-range values, unknown preset/format/voice) are rejected
with an MCP `InvalidParameters` error before any request is made.

### `synthesize_speech`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `text` | string | **required** | Max chars per model: v3 5,000; multilingual_v2 10,000; flash_v2 30,000; flash_v2_5 40,000 |
| `voice_id` | string | `ELEVENLABS_DEFAULT_VOICE` | 20-char voice ID, or a voice name from `list_voices` (short name like `George` works) |
| `model` | string | `ELEVENLABS_DEFAULT_MODEL` | `eleven_v3`, `eleven_multilingual_v2`, `eleven_flash_v2_5`, `eleven_flash_v2`; `eleven_turbo_*` are deprecated (warning) |
| `output_format` | string | `mp3_44100_128` | See [Output formats](#output-formats) |
| `preset` | string | - | See [Presets](#voice-presets); explicit settings below override it |
| `stability` | number 0-1 | 0.5 | `eleven_v3` only accepts 0.0 / 0.5 / 1.0; other values are rounded (warning) |
| `similarity_boost` | number 0-1 | 0.75 | |
| `style` | number 0-1 | 0.0 | |
| `speed` | number 0.7-1.2 | voice default | |
| `use_speaker_boost` | bool | false | |
| `language_code` | string | auto | ISO 639-1 (`en`, `ja`, `de`, ...) |
| `seed` | integer | - | Best-effort determinism |
| `previous_text` / `next_text` | string | - | Continuity when splitting long text |
| `apply_text_normalization` | `auto`/`on`/`off` | `auto` | |

Response:

```json
{
  "success": true,
  "local_path": "/output/2026-09-22/speech_20260922_101500_1a2b3c4d.mp3",
  "output_format": "mp3_44100_128",
  "file_size_bytes": 48213,
  "character_count": 42,
  "model_used": "eleven_v3",
  "voice_id": "JBFqnCBsd6RMkjVDRZzb",
  "request_id": "...",
  "warnings": ["..."]
}
```

`warnings` (omitted when empty) reports non-fatal adjustments: v3 stability
rounding, deprecated models, audio tags sent to a model that ignores them,
or a legacy built-in voice alias being used.

### `generate_sound_effect`

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `prompt` | string | **required** | e.g. `"door creaking open"` |
| `duration_seconds` | number 0.5-30 | 5.0 | Out-of-range values are rejected (previously silently clamped to 22) |
| `prompt_influence` | number 0-1 | API default (0.3) | Higher = follows the prompt more strictly |
| `loop` | bool | false | Seamlessly looping sound |
| `output_format` | string | `mp3_44100_128` | |

Returns the same shape as `synthesize_speech` plus `duration_seconds`.

### `list_voices`

Optional `search` (case-insensitive match on name, description and label
values), `category` (`premade`, `cloned`, `generated`, `professional`, ...),
`refresh` (bypass the 10-minute cache). Returns `voices`, `count` (after
filtering) and `total_available`.

### `get_user_subscription`

Returns `tier`, `character_count`, `character_limit`, `characters_remaining`,
`next_reset` (RFC 3339) and the raw `subscription` object.

### `get_models`

Optional `tts_only`. Returns each model's ID, name, capabilities,
`maximum_text_length_per_request`, `languages` and `deprecated_by`.

### `list_presets`

Lists the presets below. Works without an API key.

### `clear_cache`

Deletes audio files this server generated (`speech_*` / `sfx_*` with an audio
extension) from the output directory, its `YYYY-MM-DD` subdirectories and the
legacy `<tmp>/elevenlabs_cache` directory used by v2.0. Other files are never
touched and symlinks are not followed; emptied date directories are removed.
Optional `older_than_days` and `dry_run`. Works without an API key.

## Voice Presets

| Preset | Stability | Similarity | Style | Speaker boost | Use case |
|--------|-----------|------------|-------|---------------|----------|
| `audiobook` | 0.75 | 0.75 | 0.0 | no | Long-form narration |
| `character_performance` | 0.30 | 0.80 | 0.6 | yes | Expressive characters |
| `news_reading` | 0.90 | 0.70 | 0.0 | no | Professional delivery |
| `emotional_dialogue` | 0.50 | 0.85 | 0.3 | yes | Dramatic conversations |
| `github_review` | 0.60 | 0.80 | 0.2 | no | Code review narration |
| `tutorial_narration` | 0.70 | 0.75 | 0.1 | no | Educational content |
| `podcast` | 0.50 | 0.80 | 0.4 | yes | Conversational content |
| `meditation` | 0.85 | 0.70 | 0.0 | no | Calm, steady delivery |
| `storytelling` | 0.40 | 0.75 | 0.5 | yes | Narrative content |
| `customer_service` | 0.80 | 0.75 | 0.0 | no | Professional, neutral |

With `eleven_v3`, preset stability is rounded to 0.0/0.5/1.0.

## Output Formats

`mp3_22050_32`, `mp3_24000_48`, `mp3_44100_{32,64,96,128,192}`,
`opus_48000_{32,64,96,128,192}`, `pcm_{8000,16000,22050,24000,32000,44100,48000}`,
`wav_{8000,16000,22050,24000,32000,44100,48000}`, `ulaw_8000`, `alaw_8000`.

`pcm_*`, `ulaw_8000` and `alaw_8000` are raw headerless streams (saved as
`.pcm` / `.ulaw` / `.alaw`); use `wav_*` for a directly playable uncompressed
file. Some formats (e.g. `mp3_44100_192`, 44.1 kHz+ PCM) need a paid tier;
the API error is returned as-is.

## Audio Tags (`eleven_v3` only)

Inline tags steer delivery, for example `[laughs]`, `[sighs]`, `[whispers]`,
`[excited]`, `[sarcastic]`, `[curious]`. Other models read tags aloud, so the
server warns when tags are sent to a non-v3 model.

```json
{"tool": "synthesize_speech",
 "arguments": {"text": "[excited] The build passed! [laughs] Finally!",
               "voice_id": "George", "preset": "github_review"}}
```

## Voices

Names are looked up in the account's voice list first. The old hardcoded
names (`rachel`, `george`, `sarah`, `charlie`, `emily`) remain as a fallback
alias table, but ElevenLabs has retired the legacy voices (Rachel, Emily, ...;
their IDs are silently remapped) and announced that all premade "Default"
voices expire on 2026-12-31. Use `list_voices` and pass an explicit ID, or set
`ELEVENLABS_DEFAULT_VOICE` to a voice you own.

## MCP Configuration

```json
{
  "mcpServers": {
    "elevenlabs-speech": {
      "command": "mcp-elevenlabs-speech",
      "args": ["--mode", "stdio"],
      "env": { "ELEVENLABS_API_KEY": "your_key_here" }
    }
  }
}
```

## Development

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test          # offline: HTTP is mocked with wiremock, files use temp dirs
```

```
src/
  main.rs     CLI entry point (mode alias handling)
  config.rs   Environment configuration (API key redacted in Debug)
  client.rs   ElevenLabs HTTP client, error mapping/redaction, voice cache
  server.rs   MCP tools (typed argument structs + JSON schemas)
  storage.rs  Atomic audio writes and generated-file cleanup
  types.rs    Models, formats, presets, voice helpers, API response types
```

## Limitations

- No streaming or WebSocket TTS; audio is fully downloaded (max 100 MB) and
  saved before the tool returns.
- No speech-to-speech, dubbing, voice cloning/design, dialogue or music endpoints.
- Tools return a local path; in Docker that is a container path (`/output/...`,
  bind-mounted to `./outputs/elevenlabs_speech` on the host).
- Per-model character limits are only enforced for known models.

## License

Part of the template-repo project. See repository LICENSE file.
