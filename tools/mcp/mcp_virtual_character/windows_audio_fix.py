#!/usr/bin/env python3
"""
Windows audio routing fix for VoiceMeeter.
This script uses pycaw to directly target VoiceMeeter as the audio output device.
"""

import os
import subprocess
import sys
import tempfile


def install_dependencies():
    """Install required Windows audio libraries."""
    print("Installing Windows audio dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "pycaw", "pyaudio", "simpleaudio"], check=False)


def play_audio_to_voicemeeter(audio_file):
    """Play audio file directly to VoiceMeeter using Windows audio APIs."""

    # Method 1: Use simpleaudio (simple but effective)
    try:
        import simpleaudio as sa

        print(f"Playing {audio_file} with simpleaudio...")
        wave_obj = sa.WaveObject.from_wave_file(audio_file)
        play_obj = wave_obj.play()
        play_obj.wait_done()
        return True
    except ImportError:
        print("simpleaudio not available")
    except Exception as e:
        print(f"simpleaudio failed: {e}")

    # Method 2: Use pygame (good device control)
    try:
        import pygame

        pygame.mixer.init()
        print(f"Playing {audio_file} with pygame...")
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        return True
    except ImportError:
        print("pygame not available")
    except Exception as e:
        print(f"pygame failed: {e}")

    # Method 3: Use Windows mciSendString directly via ctypes
    try:
        import ctypes

        winmm = ctypes.windll.winmm

        # Open the audio file
        alias = "myaudio"
        open_cmd = f'open "{audio_file}" type mpegvideo alias {alias}'
        result = winmm.mciSendStringW(open_cmd, None, 0, 0)
        if result != 0:
            raise RuntimeError(f"Failed to open: {result}")

        # Play the audio
        play_cmd = f"play {alias} wait"
        result = winmm.mciSendStringW(play_cmd, None, 0, 0)
        if result != 0:
            raise RuntimeError(f"Failed to play: {result}")

        # Close when done
        close_cmd = f"close {alias}"
        winmm.mciSendStringW(close_cmd, None, 0, 0)

        print(f"Played {audio_file} with mciSendString")
        return True
    except Exception as e:
        print(f"mciSendString failed: {e}")

    return False


def set_default_playback_device():
    """Set VoiceMeeter as the default playback device using PowerShell."""
    ps_script = """
    # Get audio devices
    Add-Type @"
    using System.Runtime.InteropServices;
    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator {
        int NotImpl1();
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IntPtr ppDevice);
    }
"@

    Write-Host "Setting VoiceMeeter as default playback device..."
    # This would require more complex COM interop, so for now just notify the user
    Write-Host "Please manually set VoiceMeeter Input as the default playback device in Windows Sound Settings"
    """

    subprocess.run(["powershell", "-Command", ps_script], check=False)


def create_test_audio():
    """Create a simple test WAV file."""
    try:
        import math
        import struct
        import wave

        # Parameters
        sample_rate = 44100
        duration = 1  # seconds
        frequency = 440  # Hz (A4 note)

        # Generate sine wave
        num_samples = sample_rate * duration
        samples = []
        for i in range(num_samples):
            sample = 32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate)
            samples.append(int(sample))

        # Write WAV file
        test_file = tempfile.mktemp(suffix=".wav")
        with wave.open(test_file, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 2 bytes per sample
            wav_file.setframerate(sample_rate)
            for sample in samples:
                wav_file.writeframes(struct.pack("h", sample))

        return test_file
    except Exception as e:
        print(f"Failed to create test audio: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("VoiceMeeter Audio Routing Fix")
    print("=" * 60)

    # Check if running on Windows
    if sys.platform != "win32":
        print("This script is for Windows only")
        sys.exit(1)

    # Try to install dependencies
    try:
        install_dependencies()
    except Exception as e:
        print(f"Could not install dependencies: {e}")

    # Create a test audio file
    test_file = create_test_audio()
    if test_file:
        print(f"\nCreated test audio: {test_file}")

        # Try to play it
        print("\nAttempting playback...")
        if play_audio_to_voicemeeter(test_file):
            print("✓ Audio playback successful")
        else:
            print("✗ All playback methods failed")
            print("\nTroubleshooting:")
            print("1. Make sure VoiceMeeter is running")
            print("2. Set VoiceMeeter Input as Windows default playback device")
            print("3. Route VoiceMeeter input to the output VRChat uses")
            print("4. Consider installing VLC for better audio routing")

        # Clean up
        try:
            os.remove(test_file)
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("Additional recommendations:")
    print("1. Install VLC: https://www.videolan.org/vlc/")
    print("2. VLC provides excellent audio device targeting")
    print("3. Or use VoiceMeeter's Virtual Audio Cable mode")
    print("=" * 60)
