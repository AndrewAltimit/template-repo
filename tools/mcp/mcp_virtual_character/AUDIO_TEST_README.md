# VoiceMeeter Audio Routing Test Suite

Comprehensive testing suite for VoiceMeeter audio routing with VRChat integration.

## Quick Start

**For the remote runner:**

1. **Double-click** `audio_test_menu.bat` for interactive menu
2. Select **Option 1** to install dependencies
3. Select **Option 2** to run comprehensive tests

That's it! The menu will guide you through everything.

## Files Overview

### Easy-to-Run Batch Files
- **`audio_test_menu.bat`** - Main interactive menu (START HERE!)
- **`install_dependencies.bat`** - One-click dependency installer
- **`run_audio_tests.bat`** - Run the complete test suite

### Core Scripts
- **`test_audio_routing_comprehensive.py`** - Main test suite
- **`install_audio_dependencies.ps1`** - PowerShell installer script
- **`audio_router.py`** - Audio routing utilities
- **`windows_audio_fix.py`** - Windows-specific audio fixes

## Audio Flow Diagram

```
[Python/ElevenLabs]
        ↓
[Windows Playback API]
        ↓
[VoiceMeeter Input] ← Set as Windows default
        ↓
[VoiceMeeter Routing Matrix]
     ↙        ↘
[A1: Speakers] [B1: Virtual Output]
                    ↓
            [VRChat Microphone]
```

## What Gets Tested

### 1. System Information
- Windows version
- Python version
- Working directory

### 2. Dependencies
- FFmpeg (audio conversion)
- VLC (device targeting)
- PowerShell (Windows audio)
- Python packages (pygame, simpleaudio, etc.)

### 3. Audio Devices
- Lists all Windows audio devices
- Detects VoiceMeeter devices
- Checks default playback device

### 4. VoiceMeeter Status
- Installation check
- Running process check
- Device availability

### 5. Audio Playback Methods
- Windows Media Player
- .NET SoundPlayer
- VLC with device targeting
- FFmpeg/FFplay
- Python pygame

### 6. Complete Audio Flow Test
- Creates test audio
- Routes through each method
- Validates playback success

## Installation

### Automatic (Recommended)

1. Run `audio_test_menu.bat`
2. Select Option 1 (Install Dependencies)
3. Follow the prompts

### Manual Installation

#### Required Software
- **VoiceMeeter**: https://vb-audio.com/Voicemeeter/
- **Python 3.7+**: https://python.org
- **VLC**: https://videolan.org/vlc/ (recommended)
- **FFmpeg**: https://ffmpeg.org (recommended)

#### Python Packages
```bash
pip install pygame simpleaudio pyaudio sounddevice pycaw requests aiohttp
```

## VoiceMeeter Configuration

### Critical Settings

1. **Windows Default Playback**: Set to "VoiceMeeter Input"
   - Right-click speaker icon → Open Sound settings
   - Choose "VoiceMeeter Input" as default

2. **VoiceMeeter Routing**:
   - Virtual Input → A1 (Hardware Out)
   - Virtual Input → B1 (Virtual Out)

3. **VRChat Microphone**: Set to "VoiceMeeter Output"
   - VRChat Settings → Audio → Microphone
   - Select "VoiceMeeter Output" or "VoiceMeeter Out B1"

## Test Results

The test suite generates detailed JSON reports with:
- System configuration
- Dependency status
- Device listings
- Test results for each playback method
- Specific recommendations

Results are saved as: `audio_test_results_YYYYMMDD_HHMMSS.json`

## Troubleshooting

### Common Issues

#### "No VoiceMeeter devices detected"
- Ensure VoiceMeeter is installed
- Restart computer after installation
- Start VoiceMeeter before testing

#### "All playback tests failed"
- Check Windows audio is not muted
- Verify VoiceMeeter is set as default device
- Ensure VoiceMeeter is running

#### "VLC not targeting VoiceMeeter"
- Install VLC if not present
- Add VLC to system PATH
- Use full device name in quotes

#### "Python packages won't install"
- Run as Administrator
- Update pip: `python -m pip install --upgrade pip`
- Install Visual C++ Build Tools for pyaudio

## Test Output Example

```
============================================
COMPREHENSIVE AUDIO ROUTING TEST SUITE
============================================

SYSTEM INFORMATION
==================
Windows: Microsoft Windows 11 Pro
Python: 3.11.0
Working Directory: C:\VoiceMeeter\Tests

DEPENDENCY CHECK
================
ffmpeg: Installed
vlc: Installed
powershell: Installed

AUDIO DEVICES
=============
[0] VoiceMeeter Input - 2 out, 0 in
    ^ VoiceMeeter device detected!
[1] Speakers (Realtek) - 2 out, 0 in
[2] VoiceMeeter Output - 0 out, 2 in

AUDIO PLAYBACK TESTS
====================
1. Windows Media Player: Success
2. .NET SoundPlayer: Success
3. VLC with VoiceMeeter: Success
4. FFplay: Success
5. Python pygame: Success

RECOMMENDATIONS
===============
All systems operational!
```

## VRChat Integration

After successful tests:

1. Start VRChat
2. Join any world
3. Run the Virtual Character server
4. Send audio through the MCP tools
5. Audio should play through your VRChat avatar

## Tips

- **Always start VoiceMeeter first** before running tests
- **Run as Administrator** for best results with installations
- **Save test results** for troubleshooting
- **Use VLC** for most reliable device targeting
- **Keep logs** from `audio_test_results.log`

## Additional Resources

- [VoiceMeeter Setup Guide](docs/VOICEMEETER_SETUP.md)
- [Virtual Character Documentation](README.md)
- [Audio Sequencing Guide](docs/AUDIO_SEQUENCING.md)

## Support

If tests fail:
1. Check the generated JSON report
2. Follow the specific recommendations
3. Ensure all dependencies are installed
4. Verify VoiceMeeter configuration
5. Check Windows audio settings

## Success Criteria

The setup is working when:
- VoiceMeeter devices are detected
- At least one playback method succeeds
- Audio plays through speakers (A1)
- VRChat receives audio (B1)
- No critical recommendations
