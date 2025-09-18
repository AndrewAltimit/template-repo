# VRChat Audio Setup Guide

## Overview

The Virtual Character MCP can send animations and expressions to VRChat via OSC, but audio playback requires additional setup since VRChat cannot directly receive audio data through OSC.

## Current Implementation Status

✅ **Working:**
- OSC communication for animations, emotions, gestures
- Audio metadata sending (text, duration)
- Expression tag processing from ElevenLabs
- Audio playback state triggers

❌ **Not Working (Yet):**
- Actual audio playback through VRChat avatar

## Audio Routing Options

### Option 1: Virtual Audio Cable (Recommended for Testing)
Use a virtual audio cable to route audio from your system to VRChat:

**📖 See [VOICEMEETER_SETUP.md](./VOICEMEETER_SETUP.md) for comprehensive configuration instructions**

Quick Overview:
1. **Install VoiceMeeter Banana** (recommended over basic VoiceMeeter)
2. **Configure VRChat** to use VoiceMeeter Output as microphone
3. **Route audio** through VoiceMeeter Input → Output
4. **Bridge server** plays audio via PyAudio to VoiceMeeter

### Option 2: Bridge Server (Production)
Implement a bridge server that:
1. Receives audio data from the Virtual Character MCP
2. Plays audio through the appropriate audio device
3. Routes to VRChat via virtual cable or system audio

### Option 3: Direct System Audio
For local testing, play audio directly through speakers:
- VRChat will pick up audio if using speakers + microphone
- Not ideal for streaming or recording

## Implementation Notes

The VRChat backend (`vrchat_remote.py`) includes:
- `use_bridge` configuration option
- `_send_audio_to_bridge()` method for bridge server integration
- OSC parameters for audio state:
  - `/avatar/parameters/AudioPlaying` - Audio playback state
  - `/avatar/parameters/AudioText` - Text being spoken
  - Viseme parameters for lip-sync (auto-generated from audio)

## Next Steps

1. **For Testing:**
   - Set up virtual audio cable
   - Add local audio playback to the VRChat backend
   - Route audio through virtual cable to VRChat mic input

2. **For Production:**
   - Implement bridge server at port 8021
   - Handle audio streaming and routing
   - Support multiple audio formats

## Configuration Example

```python
# Enable bridge server for audio
config = {
    "remote_host": "127.0.0.1",
    "use_bridge": True,  # Enable audio bridge
    "bridge_port": 8021,  # Bridge server port
    "osc_in_port": 9000,
    "osc_out_port": 9001,
    "use_vrcemote": True
}
```

## Audio Flow Diagram

```
ElevenLabs API
     ↓
Audio Data (MP3)
     ↓
Virtual Character MCP
     ↓
VRChat Backend
     ↓
  ┌──────────────┐
  │  OSC Data    │ → VRChat (animations, text, state)
  │  Audio Bytes │ → Bridge/Virtual Cable → VRChat Mic Input
  └──────────────┘
```

## Testing Without Audio

To test the integration without audio routing:
1. Animations and expressions will still work
2. The avatar will show "speaking" state
3. Text will be sent to avatar parameters
4. Just no actual audio will be heard

This is useful for verifying the OSC communication is working correctly.
