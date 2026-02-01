# VoiceMeeter Configuration for VRChat Audio Integration

This guide provides comprehensive setup instructions for routing AI-generated audio through VoiceMeeter to VRChat, enabling your virtual character to speak with synthesized voices.

## System Requirements

### Hardware
- **Windows 10/11** (VoiceMeeter is Windows-only)
- **Audio device** (speakers/headphones for monitoring)
- **GPU** capable of running VRChat (NVIDIA recommended)

### Software Prerequisites
- **VoiceMeeter** (Standard, Banana, or Potato)
- **VRChat** (Steam or standalone)
- **Python 3.10+** with audio packages
- **FFmpeg** for audio processing
- **VLC** (recommended for device targeting)

## Installation

### 1. Install VoiceMeeter Banana

**Recommended**: VoiceMeeter Banana (over basic VoiceMeeter) for more routing options

1. Download from [VB-Audio website](https://vb-audio.com/Voicemeeter/banana.htm)
   - **VoiceMeeter Standard**: Basic (3 inputs, 2 outputs)
   - **VoiceMeeter Banana**: Advanced (5 inputs, 5 outputs) - RECOMMENDED
   - **VoiceMeeter Potato**: Professional (8 inputs, 8 outputs)
2. Install following the setup wizard
   - Run installer as Administrator
3. **CRITICAL: Restart Windows** after installation (required for virtual audio drivers)
4. Launch VoiceMeeter from Start Menu

### 2. Install Audio Dependencies

Run the provided installer scripts:

```batch
# Navigate to the virtual_character directory
cd tools\mcp\mcp_virtual_character

# Simple installer (Python packages only)
install_dependencies_simple.bat

# Or comprehensive installer (includes VLC, FFmpeg, Chocolatey)
install_dependencies.bat
```

Required Python packages (installed automatically):
- pygame
- simpleaudio
- pyaudio
- sounddevice
- pycaw
- requests
- aiohttp

## VoiceMeeter Configuration

### 2. Hardware Output Configuration

Open VoiceMeeter Banana and configure the outputs:

**HARDWARE OUT (Physical Outputs):**
- **A1**: Your speakers/headphones (for local monitoring)
- **A2**: VoiceMeeter VAIO (Virtual Output) - *This is critical*
- **A3**: Leave unassigned

**HARDWARE INPUTS:**
- **Hardware Input 1**: Your physical microphone (optional - if you want to talk too)
- **Hardware Input 2**: Leave unassigned
- **Virtual Input (VAIO)**: This receives the AI audio

### 3. Windows Sound Settings

Configure Windows to route audio correctly:

#### Recording Devices
```
Control Panel → Sound → Recording Tab:

1. Right-click "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)"
2. Select "Set as Default Device"
3. Click "OK"

This is what VRChat will use as its microphone input
```

#### Playback Devices
```
Control Panel → Sound → Playback Tab:

1. Verify "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)" is present
2. This is where the bridge server will send audio
3. It does NOT need to be the default device
```

### 4. VRChat Audio Configuration

In VRChat, configure the microphone input:

```
VRChat Settings:
1. Open Settings (ESC key)
2. Navigate to: Audio → Microphone
3. Select: "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)"
4. Test with the mic test feature
```

### 5. VoiceMeeter Routing Matrix

Configure the routing in VoiceMeeter:

#### Virtual Input (VAIO) Strip
- **B1 Button**: Enable (routes to Virtual Output B1)
- **Fader**: Set to 0 dB
- **A1 Button**: Optional - Enable if you want to hear the AI locally
- **Mute**: Ensure NOT muted

#### Hardware Input 1 (Your Microphone - Optional)
- **B1 Button**: Enable to mix your voice with AI
- **Fader**: Adjust to preference
- **Gate**: Can be used to reduce background noise

### 6. System Settings in VoiceMeeter

Access via: **Menu → System Settings / Options**

```
Preferred Settings:
- Main Sample Rate: 48000 Hz (matches VRChat)
- ASIO Input: Not required
- WDM Input Exclusive: No
- Buffering WDM: 512 samples
- Buffering ASIO: 512 samples
```

## Bridge Server Audio Implementation

### 7. Python Audio Playback Code

Add this to your Windows bridge server to play audio through VoiceMeeter:

```python
import pyaudio
import wave
import io
import asyncio
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)

class VoiceMeeterAudioPlayer:
    """Plays audio through VoiceMeeter Input for VRChat."""

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.device_index = self._find_voicemeeter_device()

        if self.device_index is None:
            raise RuntimeError("VoiceMeeter Input device not found. Is VoiceMeeter running?")

        logger.info(f"VoiceMeeter Input found at device index: {self.device_index}")

    def _find_voicemeeter_device(self) -> int:
        """Find VoiceMeeter Input device index."""
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            # Look for VoiceMeeter Input in device name
            if "VoiceMeeter Input" in info['name'] or "VoiceMeeter Aux Input" in info['name']:
                if info['maxOutputChannels'] > 0:  # Ensure it's an output device
                    return i
        return None

    def mp3_to_wav(self, mp3_bytes: bytes) -> bytes:
        """Convert MP3 bytes to WAV format."""
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        wav_io = io.BytesIO()
        audio.export(wav_io, format='wav')
        wav_io.seek(0)
        return wav_io.read()

    async def play_audio(self, audio_bytes: bytes, format: str = "mp3"):
        """
        Play audio through VoiceMeeter Input.

        Args:
            audio_bytes: Raw audio data
            format: Audio format (mp3, wav)
        """
        try:
            # Convert to WAV if needed
            if format.lower() == "mp3":
                audio_data = self.mp3_to_wav(audio_bytes)
            else:
                audio_data = audio_bytes

            # Open WAV file from bytes
            wf = wave.open(io.BytesIO(audio_data), 'rb')

            # Open stream to VoiceMeeter
            stream = self.p.open(
                format=self.p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=self.device_index,
                frames_per_buffer=1024
            )

            # Play audio in chunks
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)

            # Cleanup
            stream.stop_stream()
            stream.close()
            wf.close()

            logger.info("Audio playback completed")

        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            raise

# Integration with VRChat Bridge Server
class VRChatBridgeServer:
    def __init__(self):
        self.audio_player = VoiceMeeterAudioPlayer()

    async def handle_audio_play(self, audio_data: bytes, format: str = "mp3"):
        """Handle audio playback request from Virtual Character MCP."""
        # Play through VoiceMeeter
        await self.audio_player.play_audio(audio_data, format)

        # Also send OSC triggers to VRChat
        self.osc_client.send_message("/avatar/parameters/AudioPlaying", 1.0)
```

### 8. Alternative: Using Windows TTS for Testing

For quick testing without ElevenLabs:

```python
import pyttsx3
import tempfile
import os

class WindowsTTSPlayer:
    """Simple TTS using Windows built-in voices."""

    def __init__(self):
        self.engine = pyttsx3.init()
        self.audio_player = VoiceMeeterAudioPlayer()

    async def speak(self, text: str):
        """Convert text to speech and play through VoiceMeeter."""
        # Save TTS to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        self.engine.save_to_file(text, tmp_path)
        self.engine.runAndWait()

        # Read and play through VoiceMeeter
        with open(tmp_path, 'rb') as f:
            wav_data = f.read()

        await self.audio_player.play_audio(wav_data, format='wav')

        # Cleanup
        os.unlink(tmp_path)
```

## Audio Flow Diagram

```
┌─────────────────────────┐
│   ElevenLabs/TTS API    │
│   (Audio Generation)     │
└───────────┬─────────────┘
            │ Audio Data (MP3/WAV)
            ▼
┌─────────────────────────┐
│   Bridge Server         │
│   (Python on Windows)   │
└───────────┬─────────────┘
            │ PyAudio
            ▼
┌─────────────────────────┐
│  VoiceMeeter Input      │
│  (VAIO Virtual Input)   │
└───────────┬─────────────┘
            │ Internal Routing (B1)
            ▼
┌─────────────────────────┐
│  VoiceMeeter Output     │
│  (VAIO Virtual Output)  │
└───────────┬─────────────┘
            │ Windows Audio System
            ▼
┌─────────────────────────┐
│   VRChat Microphone     │
│   (Receives as Mic)     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   VRChat Avatar         │
│   • Lip Sync (Auto)     │
│   • Voice Chat Output   │
└─────────────────────────┘
```

## Testing the Configuration

### Step 1: Run Comprehensive Audio Test

Run the provided comprehensive test suite to verify your setup:

```batch
cd tools\mcp\mcp_virtual_character
run_audio_tests.bat
```

Expected successful output:
- VoiceMeeter detected at `C:\Program Files (x86)\VB\Voicemeeter`
- VoiceMeeter is running
- 80+ VoiceMeeter virtual devices detected
- All 6 audio routing methods pass:
  1. Windows Media Player (WMP)
  2. .NET SoundPlayer
  3. VLC basic playback
  4. VLC with VoiceMeeter targeting
  5. FFmpeg/FFplay
  6. Python pygame

Test results are saved to `audio_test_results_*.json` for debugging.

### Step 2: Test VLC Device Targeting (Optional)

VLC provides the best device targeting capabilities. Test it specifically:

```batch
cd tools\mcp\mcp_virtual_character
test_vlc.bat
```

This tests 6 different VLC invocation methods to find what works on your system.

**Note**: VLC may show an error dialog mentioning "vlc-help.txt" but audio still works correctly. This is a known Windows quirk.

### Step 3: Test Python Audio Playback

```python
# Quick test script
python test_audio_routing_comprehensive.py
```

The test will:
1. Create a test audio file using FFmpeg
2. Play it through various methods
3. Verify VoiceMeeter routing
4. Generate a detailed report

### Step 4: Test in VRChat

1. Set Windows default playback to "VoiceMeeter Input"
2. Launch VRChat and go to Settings → Audio
3. Set Microphone to "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)"
4. Join any world
5. Run the test script - you should:
   - Hear the test audio locally (if A1 enabled)
   - See voice indicator activate in VRChat
   - Have automatic lip-sync on your avatar

## Troubleshooting

### Issue: VoiceMeeter Not Detected

**Symptoms:**
- Test shows "VoiceMeeter not found"
- No VoiceMeeter devices in device list

**Solutions:**
1. Ensure VoiceMeeter is installed in standard location:
   - `C:\Program Files (x86)\VB\Voicemeeter\`
2. **Restart Windows** after installation (critical!)
3. Launch VoiceMeeter before testing
4. Run VoiceMeeter as Administrator
5. Check Windows Audio Service is running

### Issue: VLC Shows Error but Audio Works

**Symptoms:**
- VLC popup mentions "vlc-help.txt" (file is empty)
- Audio actually plays successfully
- Tests pass but error dialog appears

**Solution:**
- This is a known VLC quirk on Windows with dummy interface
- The audio is working correctly despite the error
- Can be safely ignored
- Use `--intf dummy` flag to minimize popups

### Issue: Unicode Encoding Errors

**Symptoms:**
- `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`
- Console shows corrupted characters

**Solution:**
- Already fixed in latest version
- All Unicode characters replaced with ASCII equivalents
- Run `git pull` to get latest fixes

### Issue: Audio Plays Locally but Not in VRChat

**Solution:**
1. Verify VRChat microphone setting:
   - Must be "VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)"
   - NOT "VoiceMeeter Input" or "VoiceMeeter AUX"
2. Check VoiceMeeter B1 routing is enabled (green)
3. Ensure VRChat isn't muted (V key by default)
4. Verify Windows isn't blocking microphone access
5. Check VoiceMeeter B1 fader isn't muted

### Issue: Audio Stuttering or Delays

**Solution:**
- Increase buffer size in VoiceMeeter System Settings (512-1024)
- Check CPU usage - close unnecessary applications
- Ensure sample rates match (48000 Hz recommended)
- Disable audio enhancements in Windows Sound settings
- Use WDM or WASAPI drivers instead of MME

### Issue: Echo or Feedback

**Solution:**
- Disable A1 output in VoiceMeeter if using speakers
- Use headphones for monitoring
- Enable echo cancellation in VRChat settings
- Reduce Virtual Input gain in VoiceMeeter
- Check Gate settings on Virtual Input

## Advanced Configuration

### Multi-Voice Mixing

To mix AI voice with your microphone:

1. Enable B1 on both Virtual Input and Hardware Input 1
2. Adjust faders to balance volumes
3. Use Gate on Hardware Input to reduce background noise

### Recording Setup

To record the AI voice:

1. Enable B2 output on Virtual Input
2. Set recording software to use "VoiceMeeter Aux Output"
3. This provides a clean recording separate from VRChat

### Streaming Configuration

For streaming with OBS:

1. Add Audio Input Capture source
2. Select "VoiceMeeter Aux Output"
3. This captures AI voice without desktop audio

## Performance Optimization

### Recommended Settings for Low Latency

```
VoiceMeeter System Settings:
- Engine Mode: Swift (lowest latency)
- Buffering: 256-512 samples
- Sample Rate: 48000 Hz
- Preferred I/O: WDM

Windows Settings:
- Disable audio enhancements
- Set VoiceMeeter devices to 48000 Hz, 16 bit
- Disable exclusive mode for applications
```

### CPU Usage Optimization

- Close VoiceMeeter's GUI when not needed (runs in background)
- Disable unused hardware inputs
- Reduce buffer size only if CPU allows
- Use ASIO drivers if available

## Integration with Virtual Character MCP

The complete flow with the Virtual Character MCP:

1. **ElevenLabs MCP** generates audio with emotion tags
2. **Virtual Character MCP** receives audio data
3. **VRChat Backend** sends audio to bridge server
4. **Bridge Server** plays audio through VoiceMeeter
5. **VoiceMeeter** routes to VRChat microphone
6. **VRChat** generates lip-sync automatically

This setup enables realistic AI-driven avatars with natural speech and synchronized animations.

## Next Steps

After configuring VoiceMeeter:

1. Update bridge server with audio playback code
2. Test with simple audio files first
3. Integrate with ElevenLabs audio generation
4. Add emotion-based animations synchronized with speech
5. Implement conversation state management

## References

- [VoiceMeeter Documentation](https://vb-audio.com/Voicemeeter/banana.htm)
- [VRChat OSC Documentation](https://docs.vrchat.com/docs/osc-overview)
- [PyAudio Documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/)
- [Virtual Character MCP Documentation](../README.md)
