# Audio and Event Sequencing

This guide covers `play_audio` and the sequence tools (`create_sequence`,
`add_sequence_event`, `play_sequence`, `pause_sequence`, `resume_sequence`,
`stop_sequence`, `get_sequence_status`).

## play_audio

```json
{"tool": "play_audio", "arguments": {
  "audio_data": "outputs/elevenlabs_speech/hello.mp3",
  "text": "Hello! [laughs] Great to see you.",
  "duration": 2.8
}}
```

| Param | Required | Description |
|-------|----------|-------------|
| `audio_data` | yes | File path, `http(s)://` URL, `data:audio/...;base64,...`, or raw base64 |
| `audio_format` | no | `mp3` (default), `wav`, `opus`, `ogg`, `flac`, `pcm`. Magic bytes override a wrong declaration. |
| `sample_rate` | no | For `pcm` (16-bit mono little-endian), default 44100. PCM is wrapped into WAV. |
| `text` | no | Transcript. `[tags]` in it drive expression when `expression_tags` is omitted. |
| `expression_tags` | no | ElevenLabs tags, e.g. `["[laughs]", "[whisper]"]` |
| `duration` | no | Seconds. Estimated from WAV/MP3 headers when omitted. |

Input handling:

- **Files** must be inside an allowed directory: `outputs/`, `/tmp`, the OS
  temp directory, or directories listed in `VIRTUAL_CHARACTER_AUDIO_DIRS`
  (OS path-list syntax). Paths are canonicalized, so `..` and symlinks cannot
  escape. The ElevenLabs container path `/tmp/elevenlabs_audio/<file>` is
  mapped to `outputs/elevenlabs_speech/<file>`.
- **URLs** are downloaded with a 30 s timeout; HTML responses are rejected.
- **All sources** are limited to 50 MB and validated (not HTML, recognizable
  audio or large enough to be raw PCM).

Expression: the single highest-intensity tag wins (applying every tag in turn
would toggle VRChat emotes on and off). For example `[laughs]` -> happy ->
VRCEmote 4 (cheer). An emote that is already showing is not toggled off.

Playback (VRChat backend):

- `audio_playback=local` (default when `remote_host` is loopback): the clip
  is played with VLC (device `VoiceMeeter Input` by default), ffplay, or
  PowerShell `SoundPlayer` (WAV only) on Windows; ffplay, paplay or aplay on
  Linux. The call returns as soon as playback starts; the player is killed if
  it runs longer than 1.5 x duration + 5 s (10 min if unknown).
- `/avatar/parameters/AudioPlaying` is set to 1 and back to 0 when playback
  ends (or after `duration`, or 10 s when unknown and not played locally).
- The response reports what actually happened:

```json
{"success": true, "played": true, "method": "vlc", "format": "mp3",
 "bytes": 45321, "duration": 2.8, "emotion": "happy", "notes": []}
```

The mock backend records clips without playing them (`played: false`).

## Sequences

One sequence is built at a time. Events fire at `timestamp` seconds from the
start of playback, in timestamp order. Playback runs in the background; the
tool returns immediately.

```json
{"tool": "create_sequence", "arguments": {"name": "intro", "loop": false}}

{"tool": "add_sequence_event", "arguments": {
  "event_type": "animation", "timestamp": 0.0,
  "animation_params": {"gesture": "wave", "emotion": "happy"}}}

{"tool": "add_sequence_event", "arguments": {
  "event_type": "audio", "timestamp": 0.5,
  "audio_data": "outputs/elevenlabs_speech/intro.mp3",
  "text": "Hi everyone! [laughs]"}}

{"tool": "add_sequence_event", "arguments": {
  "event_type": "movement", "timestamp": 4.0,
  "movement_params": {"move_forward": 0.5, "duration": 1.5}}}

{"tool": "add_sequence_event", "arguments": {
  "event_type": "expression", "timestamp": 6.0, "expression": "neutral"}}

{"tool": "play_sequence", "arguments": {}}
```

### Event types

| `event_type` | Required fields | Effect |
|--------------|-----------------|--------|
| `animation` | `animation_params` (emotion / gesture / parameters / blend_shapes) | Same as `send_animation`. A top-level `expression` fills a missing emotion. |
| `expression` | `expression` (+ `expression_intensity`) | Emotion change |
| `movement` | `movement_params` | Movement / `avatar_params` (validated when added) |
| `audio` | `audio_data` (+ `audio_format`, `text`, `expression_tags`, `sample_rate`) | Same as `play_audio`. Audio is loaded and validated when the event is added; `duration` defaults to the clip length. |
| `wait` | `wait_duration` | Timeline marker: extends the sequence to `timestamp + wait_duration`. Other events are absolutely timed and are **not** shifted. |
| `parallel` | `parallel_events` (list of events) | Children fire together at the parent's timestamp (nesting depth <= 3, <= 32 children). |

Validation happens in `add_sequence_event`: unknown emotions/gestures,
wrong types, negative timestamps and missing required fields are rejected
with a message instead of being silently dropped. A sequence holds at most
1000 events.

### Playback behavior

- The avatar is reset (`reset`) at the start and end of every pass.
- `start_time` skips events before that offset.
- `loop: true` repeats until stopped; each pass lasts at least 0.1 s.
- `pause_sequence` freezes the sequence clock (including in-progress waits);
  `resume_sequence` continues from the same position.
- `stop_sequence` stops playback but keeps the sequence for replay;
  `panic_reset` stops and discards it and resets the avatar.
- `create_sequence` with `interrupt_current: true` (default) stops current
  playback. Editing the sequence during playback does not affect the running
  pass (playback uses a snapshot).
- Switching or disconnecting the backend stops playback.
- A failing event does not abort the performance; it is counted in
  `events_failed` and reported as `last_error`.

### get_sequence_status

```json
{"success": true, "status": {
  "has_sequence": true, "sequence_name": "intro", "event_count": 4,
  "total_duration": 6.0, "loop": false,
  "is_playing": true, "is_paused": false, "current_time": 2.315,
  "playing_sequence": "intro", "events_executed": 2, "events_failed": 0,
  "passes_completed": 0, "last_error": null}}
```

## Timing notes

- Backend sends are near-instant (UDP), so `parallel` children are dispatched
  back-to-back rather than truly concurrently.
- Emote switches include a 100 ms gap (toggle-off, then toggle-on).
- Local audio playback starts within ~0.5 s (player startup check).
