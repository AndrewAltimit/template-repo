# VoiceMeeter Setup for VRChat Speech

VRChat cannot receive audio over OSC. To make the avatar *speak*, the
Virtual Character server plays audio on the Windows machine running VRChat and
a virtual audio cable (VoiceMeeter) feeds that output into VRChat's
microphone. VRChat then generates lip-sync from the microphone signal.

```
play_audio (MCP) -> mcp-virtual-character (on the VRChat PC)
                 -> VLC / ffplay -> "VoiceMeeter Input" (virtual playback device)
                 -> VoiceMeeter routing (B1)
                 -> "VoiceMeeter Output" (virtual recording device)
                 -> VRChat microphone -> voice + automatic lip-sync
```

## Requirements

- Windows 10/11 with VRChat
- [VoiceMeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm) (Standard
  or Potato also work). **Restart Windows after installing** - the virtual
  audio drivers are not available until then.
- An audio player on `PATH` (or VLC in its default install location):
  - **VLC** (recommended) - supports targeting a specific output device
  - **ffplay** (from FFmpeg) - plays to the default output device
  - Without either, only WAV/PCM can be played (PowerShell `SoundPlayer`,
    default device only)

## 1. Windows sound devices

- **Recording** tab: `VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)` exists.
  This is VRChat's microphone.
- **Playback** tab: `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)` exists.
  This is where the server plays audio. It does not need to be the default
  device when VLC is used (VLC targets it by name); with ffplay or
  PowerShell it must be the **default playback device**.

## 2. VoiceMeeter routing

On the **Virtual Input (VAIO)** strip:

- **B1**: enabled (routes the AI voice to VoiceMeeter Output = VRChat mic)
- **A1**: optional, enable to hear the AI voice on your speakers/headphones
- Fader at 0 dB, not muted

Optional: enable **B1** on Hardware Input 1 to mix your own microphone in.

Recommended **System Settings**: 48000 Hz sample rate, 512-sample WDM
buffering, Engine Mode "Swift" for lowest latency.

## 3. VRChat

Settings -> Audio -> Microphone: `VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)`.
Make sure you are not muted in-game.

## 4. Virtual Character server

Run the server natively on the VRChat PC (not in Docker - containers have no
audio devices):

```powershell
mcp-virtual-character.exe --mode standalone --port 8025 --backend vrchat_remote
```

With `remote_host` = `127.0.0.1` (the default), `audio_playback` resolves to
`local` automatically. The output device defaults to `VoiceMeeter Input`; change
it with `VIRTUAL_CHARACTER_AUDIO_DEVICE` or `set_backend`'s
`config.audio_device`.

Check the result of a `play_audio` call:

```json
{"success": true, "played": true, "method": "vlc", "format": "mp3", "duration": 3.2}
```

`played: false` plus `notes` explains why nothing was audible (for example
`audio_playback=none`, or no player installed).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `played: false`, "No audio player could play the file" | Install VLC or FFmpeg (ffplay) and make sure it is on `PATH` |
| Audio audible locally but not in VRChat | VRChat mic must be *VoiceMeeter Output*; B1 enabled on the Virtual Input strip |
| Audio goes to speakers instead of VoiceMeeter | ffplay/PowerShell use the default device - set *VoiceMeeter Input* as default, or install VLC |
| VLC pops up a "vlc-help.txt" dialog | Known VLC quirk with `--intf dummy` on Windows; audio still plays |
| Stutter / delay | Increase VoiceMeeter buffering (512-1024), match 48 kHz everywhere, disable Windows audio enhancements |
| Echo / feedback | Disable A1 when using speakers, or use headphones |
| VoiceMeeter devices missing | Reboot after installing VoiceMeeter; start VoiceMeeter before VRChat |

## References

- [VoiceMeeter documentation](https://vb-audio.com/Voicemeeter/banana.htm)
- [VRChat OSC overview](https://docs.vrchat.com/docs/osc-overview)
- [Server README](../README.md)
