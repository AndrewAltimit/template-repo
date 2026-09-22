# VRChat OSC Setup and Troubleshooting

## Enable OSC in VRChat

1. Open the Action Menu (R on desktop) -> Options -> OSC -> **Enabled**.
2. If you changed avatars while OSC was off, use Options -> OSC -> Reset
   Config so VRChat regenerates the avatar's OSC config.
3. Firewall: allow UDP 9000 (inbound to VRChat) on the VRChat PC, and UDP 9001
   inbound on the machine running this server if it is a different machine.

## Ports

The names are from VRChat's point of view:

| Config key | Default | Meaning |
|------------|---------|---------|
| `osc_in_port` | 9000 | VRChat **receives** here - the server sends to `remote_host:osc_in_port` |
| `osc_out_port` | 9001 | VRChat **sends** here - the server listens on `0.0.0.0:osc_out_port` |

The legacy names `vrchat_recv_port` / `vrchat_send_port` are accepted as
aliases. VRChat sends its output to `127.0.0.1:9001` by default, so inbound
tracking (`get_avatar_state`, `vrchat_responding`) only works when this server
runs on the VRChat PC, or when VRChat is launched with
`--osc=9000:<server-ip>:9001`.

Only one program can listen on 9001. If another OSC tool (or a second server
instance) holds it, the backend connects in **send-only** mode and
`get_backend_status` reports `receiver: "send-only: port 9001 unavailable ..."`.

## Connecting

```json
{"tool": "set_backend", "arguments": {
  "backend": "vrchat_remote",
  "config": {"remote_host": "127.0.0.1", "use_vrcemote": true}
}}
```

Then verify:

```json
{"tool": "get_backend_status", "arguments": {}}
```

- `statistics.vrchat_responding: true` - VRChat sent OSC within the last 30 s
  (move or change a parameter in-game to trigger traffic).
- `statistics.osc_messages_sent` increases with each command.
- UDP is connectionless: a successful `set_backend` only means the socket is
  ready, not that VRChat is listening. Use `vrchat_responding` as the signal.

## Emotes (VRCEmote)

Emotions and gestures are expressed through the `VRCEmote` integer parameter
(gesture wheel slots):

| Value | Emote | Triggered by |
|-------|-------|--------------|
| 0 | none / clear | `gesture: "none"`, `emotion: "neutral"` |
| 1 | wave | `gesture: "wave"`, behavior `greet` |
| 2 | clap | `gesture: "clap"`, `"nod"` |
| 3 | point | `gesture: "point"`, `emotion: "angry"` |
| 4 | cheer | `gesture: "cheer"`, `"thumbs_up"`, `emotion: "happy"` |
| 5 | dance | `gesture: "dance"`, `emotion: "excited"`, behavior `dance` |
| 6 | backflip | `gesture: "backflip"`, `emotion: "surprised"` |
| 7 | sadness | `gesture: "sadness"`, `emotion: "sad"` |
| 8 | die | `gesture: "die"`, `emotion: "fearful"` |

`disgusted`, `contemptuous` and `calm` emotions and the `thumbs_down`,
`shake_head`, `shrug`, `crossed_arms`, `thinking` gestures have no wheel slot:
they are recorded but not sent.

**Toggle semantics.** Many avatars treat wheel emotes as toggles: sending the
active value again turns it off, and `0` alone does not clear it. The server
therefore:

- clears an emote by sending the active value followed by `0` (works for both
  toggle and standard avatars);
- toggles off when the same emote is requested while active;
- clears the previous emote before starting a different one;
- clears the active emote before movement (some emotes lock locomotion);
- auto-clears an emote after `emote_timeout` seconds (default 10, `0`
  disables).

When a call contains both a gesture and an emotion, the gesture wins (the
emotion is recorded but its emote is not sent), so `greet` waves instead of
immediately replacing the wave with a cheer.

## Movement

`send_animation.parameters` (or sequence `movement_params`):

| Key | OSC address | Notes |
|-----|-------------|-------|
| `move_forward` | `/input/Vertical` | -1..1 |
| `move_right` | `/input/Horizontal` | -1..1 |
| `look_horizontal` | `/input/LookHorizontal` | turn *rate* -1..1 |
| `look_vertical` | `/input/LookVertical` | -1..1 |
| `run` | `/input/Run` | bool |
| `jump` | `/input/Jump` | pulsed 1 -> 0 |
| `crouch` | `/input/Crouch` | bool |
| `duration` | - | seconds before the axes above reset to 0 (default 2, max 60) |

Axes are continuous inputs in VRChat, so every non-zero axis is automatically
reset after `duration`; a new movement command replaces the pending stop.
Non-numeric values are rejected with an error rather than ignored.

If the avatar does not move: enable OSC *input* in VRChat settings, clear
emotes (`reset`), and note that some worlds restrict locomotion.

## Custom avatar parameters

```json
{"tool": "send_animation", "arguments": {
  "parameters": {"avatar_params": {"Blush": 0.5, "HatToggle": true, "Outfit": 2}}
}}
```

Integers are sent as OSC int, other numbers as float, booleans as OSC bool.
`VRCEmote` inside `avatar_params` goes through the emote state machine above.
Use `get_avatar_state` to see which parameters the current avatar reports.

## Chatbox transcripts

Set `config.chatbox_transcripts: true` to show `play_audio` text (with
`[tags]` removed, truncated to 144 characters) in the VRChat chatbox.

## Audio

See [VOICEMEETER_SETUP.md](VOICEMEETER_SETUP.md). In short: audio is played
on the machine running the server (`audio_playback: local`, the default when
`remote_host` is loopback) and routed to VRChat's microphone with a virtual
cable. When the server runs elsewhere, `play_audio` still applies expression
tags and toggles the `AudioPlaying` avatar parameter, and reports
`played: false`.
