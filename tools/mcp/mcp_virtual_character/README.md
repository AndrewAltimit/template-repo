# Virtual Character MCP Server (Rust)

MCP server that lets an AI agent drive a virtual character: emotions,
gestures, movement, custom avatar parameters, speech playback with ElevenLabs
expression tags, and timed multi-event performances. The production backend
controls a **VRChat** avatar over OSC; a **mock** backend runs everything
offline for development and tests.

## Quick start

```bash
cd tools/mcp/mcp_virtual_character
cargo build --release

# STDIO (Claude Code / local MCP clients)
./target/release/mcp-virtual-character --mode stdio

# HTTP (remote access); default port 8025
./target/release/mcp-virtual-character --mode standalone --port 8025
curl http://localhost:8025/health

# Connect VRChat on this machine at startup
./target/release/mcp-virtual-character --mode standalone --backend vrchat_remote
```

Then, from the agent:

```json
{"tool": "set_backend", "arguments": {"backend": "vrchat_remote"}}
{"tool": "send_animation", "arguments": {"gesture": "wave", "emotion": "happy"}}
{"tool": "play_audio", "arguments": {"audio_data": "outputs/elevenlabs_speech/hi.mp3", "text": "[laughs] Hi!"}}
{"tool": "get_backend_status", "arguments": {}}
```

## Deployment

VRChat runs on Windows, and speech has to be played on that machine (VRChat
hears it through a virtual-cable microphone). The recommended setup is to run
this server **natively on the VRChat PC** in `standalone` mode and point MCP
clients at `http://<vrchat-pc>:8025/messages` (as `.mcp.json.full` does).

Running it in Docker / on another machine works for animation and movement
(`remote_host` = VRChat PC IP), but `play_audio` then only applies
expressions (`played: false`) and inbound OSC tracking requires VRChat's
`--osc=9000:<server-ip>:9001` launch option.

## CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `standalone` | `standalone` (MCP over HTTP), `stdio`, `server` (REST only), `client` (proxy) |
| `--port` | `8025` | HTTP port (ignored for stdio) |
| `--backend-url` | - | Upstream for `client` mode |
| `--log-level` | `info` | Also `RUST_LOG`. Logs go to stderr. |
| `--backend` | - | Connect `mock` or `vrchat_remote` at startup (env `VIRTUAL_CHARACTER_BACKEND`). Failure is logged, not fatal. |

## Environment variables

Defaults for the `vrchat_remote` backend; any `set_backend.config` value
overrides them. Invalid values are ignored with a warning.

| Variable | Default | Description |
|----------|---------|-------------|
| `VIRTUAL_CHARACTER_HOST` | `127.0.0.1` | Host running VRChat |
| `VIRTUAL_CHARACTER_OSC_IN` | `9000` | VRChat's OSC input port (we send) |
| `VIRTUAL_CHARACTER_OSC_OUT` | `9001` | VRChat's OSC output port (we listen) |
| `VIRTUAL_CHARACTER_USE_VRCEMOTE` | `true` | Express emotions/gestures via VRCEmote |
| `VIRTUAL_CHARACTER_EMOTE_TIMEOUT` | `10` | Seconds before an active emote auto-clears (`0` = never) |
| `VIRTUAL_CHARACTER_AUDIO_PLAYBACK` | `auto` | `auto` (local if host is loopback), `local`, `none` |
| `VIRTUAL_CHARACTER_AUDIO_DEVICE` | `VoiceMeeter Input` | Output device for local playback (VLC / paplay) |
| `VIRTUAL_CHARACTER_AUDIO_DIRS` | - | Extra directories `play_audio` may read files from (OS path-list syntax) |
| `VIRTUAL_CHARACTER_BACKEND` | - | Same as `--backend` |

## Tools

All tools return a JSON object with `"success": true`, or an MCP error
result with a readable message. Arguments are type-checked: wrong types,
unknown emotions/gestures and out-of-range values are errors, never silently
ignored.

| Tool | Parameters | Description |
|------|------------|-------------|
| `set_backend` | `backend` (req: `mock`, `vrchat_remote`), `config` | Connect; replaces the current backend and stops sequence playback. On failure no backend is left connected. |
| `disconnect_backend` | - | Disconnect, stop playback, release ports |
| `list_backends` | - | Available backends and which is active |
| `get_backend_status` | - | Connection, health and statistics (see below) |
| `get_avatar_state` | - | World/avatar id, current emotion/gesture, avatar parameters received from VRChat |
| `send_animation` | `emotion`, `emotion_intensity`, `gesture`, `gesture_intensity`, `parameters`, `blend_shapes` | Emotion / gesture / movement / avatar parameters in one call |
| `send_vrcemote` | `emote_value` (req, 0-8) | Direct VRCEmote (vrchat_remote only); response includes `action` (`activated`, `toggled_off`, `cleared`, `unchanged`) |
| `execute_behavior` | `behavior` (req: `greet`, `dance`, `sit`, `stand`, `jump`, `crouch`), `parameters` | High-level behaviors |
| `reset` | - | Clear emotes, zero all movement inputs and `AudioPlaying` |
| `play_audio` | `audio_data` (req), `audio_format`, `sample_rate`, `text`, `expression_tags`, `duration` | Play speech; reports `played`, `method`, `format`, `duration`, `emotion`, `notes` |
| `create_sequence` | `name` (req), `description`, `loop`, `interrupt_current` | Start building a sequence |
| `add_sequence_event` | `event_type` (req), `timestamp` (req), type-specific fields | Add an event (validated immediately) |
| `play_sequence` | `start_time` | Play in the background |
| `pause_sequence` / `resume_sequence` / `stop_sequence` | - | Playback control |
| `get_sequence_status` | - | Position, events executed/failed, last error |
| `panic_reset` | - | Stop and discard sequences, reset the avatar (works without a backend) |

Emotions: `neutral, happy, sad, angry, surprised, fearful, disgusted,
contemptuous, excited, calm`. Gestures: `none, wave, point, thumbs_up,
thumbs_down, clap, nod, shake_head, shrug, crossed_arms, thinking, dance,
backflip, cheer, die, sadness`.

`send_animation.parameters` keys: `move_forward`, `move_right`,
`look_horizontal`, `look_vertical` (-1..1, auto-reset after `duration`
seconds, default 2, max 60), `jump`, `run`, `crouch` (bool), and
`avatar_params` (name -> number/bool). See
[docs/VRCHAT_SETUP.md](docs/VRCHAT_SETUP.md) for the OSC mapping.

### vrchat_remote config

| Key | Default | Description |
|-----|---------|-------------|
| `remote_host` | env / `127.0.0.1` | VRChat host (IP or hostname, resolved with a 5 s timeout) |
| `osc_in_port` / `osc_out_port` | 9000 / 9001 | Aliases: `vrchat_recv_port` / `vrchat_send_port` |
| `use_vrcemote` | `true` | Emotions/gestures via VRCEmote |
| `emote_timeout` | `10` | Auto-clear seconds (0-3600, 0 disables) |
| `listen` | `true` | Listen for VRChat OSC output |
| `audio_playback` | `auto` | `auto`, `local`, `none` |
| `audio_device` | `VoiceMeeter Input` | Local playback device |
| `chatbox_transcripts` | `false` | Show `play_audio` text in the VRChat chatbox |

### Status fields (vrchat_remote)

`get_backend_status.statistics` includes `target`, `receiver` (listening or
send-only and why), `vrchat_responding` (OSC received in the last 30 s),
`last_osc_received_secs_ago`, `osc_messages_sent/received`, `errors`,
`avatar_id`, `current_emotion`, `current_gesture`, `current_vrcemote`,
`emote_active`, `audio_playback` (effective mode), `audio_clips`.

## Emote behavior (VRChat)

Emotions and gestures map to VRCEmote wheel slots (happy -> cheer 4, sad ->
sadness 7, angry -> point 3, surprised -> backflip 6, fearful -> die 8,
excited -> dance 5; neutral clears). Many avatars use toggle emotes, so the
server tracks the active emote: repeating it toggles it off, switching clears
the old one first, movement clears it, and it auto-clears after
`emote_timeout`. A gesture takes priority over an emotion in the same call.
Details: [docs/VRCHAT_SETUP.md](docs/VRCHAT_SETUP.md).

## Audio

`play_audio` accepts file paths (allow-listed directories only), http(s)
URLs, data URLs and base64 (50 MB cap, 30 s download timeout). The format is
detected from magic bytes; duration is estimated from WAV/MP3 headers. The
dominant expression tag (from `expression_tags` or `[tags]` in `text`) sets
the avatar's emotion. With `audio_playback=local` the clip plays through VLC,
ffplay, PowerShell (WAV) or paplay/aplay without blocking the call; route it
into VRChat with [VoiceMeeter](docs/VOICEMEETER_SETUP.md). Details and
sequencing: [docs/AUDIO_SEQUENCING.md](docs/AUDIO_SEQUENCING.md).

## Sequences

Build with `create_sequence` + `add_sequence_event` (`animation`, `audio`,
`expression`, `movement`, `wait`, `parallel`), then `play_sequence`. Events
fire at absolute timestamps on a pausable clock; playback runs in the
background, resets the avatar at the start/end of each pass, supports
looping, and records failed events without aborting. See
[docs/AUDIO_SEQUENCING.md](docs/AUDIO_SEQUENCING.md).

## MCP configuration

```json
{
  "mcpServers": {
    "virtual-character": {
      "command": "mcp-virtual-character",
      "args": ["--mode", "stdio"]
    }
  }
}
```

Remote (server running on the VRChat PC):

```json
{"mcpServers": {"virtual-character": {"type": "http", "url": "http://<vrchat-pc>:8025/messages"}}}
```

Docker (animation/movement only; the image sets `VIRTUAL_CHARACTER_AUDIO_PLAYBACK=none`):

```bash
docker compose --profile services run --rm -T mcp-virtual-character mcp-virtual-character --mode stdio
```

## Architecture

```
src/
  main.rs               CLI (mcp-core server, --backend auto-connect)
  lib.rs                Library root
  server.rs             18 MCP tools over shared ServerState
  spec.rs               Typed tool arguments + validation (animation, events, audio prep)
  sequence_handler.rs   Sequence builder and background player (pausable clock)
  audio.rs              Audio loading/validation/duration, local playback
  audio_emotion_mappings.rs  ElevenLabs tag -> emotion table and lookup
  constants.rs          VRCEmote values and mappings, defaults
  types.rs              Canonical animation/audio/sequence models
  backends/
    adapter.rs          BackendAdapter trait, AudioOutcome, EmoteAction
    movement.rs         Movement / avatar_params parsing
    vrchat.rs           VRChat OSC backend (UDP send + receiver task)
    mock.rs             In-memory backend
```

Background work (OSC receiver, movement auto-stop, emote auto-clear, audio
state reset, audio players) is owned by the backend and aborted on
disconnect, reconnect or drop, so ports are released and nothing keeps
running against a stale connection.

## Testing

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

Tests run offline: the VRChat backend is exercised against a local UDP
socket acting as VRChat (emote toggles, movement auto-stop, receiver
tracking, reconnect port release), audio playback against stand-in player
commands, and the full tool surface against the mock backend.

## Limitations

- VRChat accepts no audio over OSC; speech requires local playback on the
  VRChat PC plus a virtual audio cable.
- UDP gives no delivery confirmation; `vrchat_responding` only reflects
  inbound traffic from VRChat.
- Emote mappings assume the default VRChat action-menu wheel layout; avatars
  with custom wheels may show different animations.
- `parallel` events are dispatched back-to-back, not truly concurrently.
- `execute_behavior` `sit`/`crouch` set the custom avatar parameters
  `Sitting`/`Crouching`, which only work on avatars that define them.
- One sequence is built/played at a time.

## Related documentation

- [VRChat setup and troubleshooting](docs/VRCHAT_SETUP.md)
- [Audio and sequencing](docs/AUDIO_SEQUENCING.md)
- [VoiceMeeter setup](docs/VOICEMEETER_SETUP.md)
- [Virtual Character + ElevenLabs guide](../../../docs/integrations/creative-tools/virtual-character-elevenlabs.md)
- [VRChat OSC documentation](https://docs.vrchat.com/docs/osc-overview)
