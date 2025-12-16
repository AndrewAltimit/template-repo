#!/usr/bin/env python3
"""Test script to identify and test VoiceMeeter audio devices on Windows."""

import os
import subprocess
import sys
import tempfile


def test_audio_playback():
    """Test different methods of playing audio to VoiceMeeter."""

    # List of potential VoiceMeeter device names to try
    device_names = [
        "VoiceMeeter Input",
        "VoiceMeeter Aux Input",
        "VoiceMeeter VAIO",
        "CABLE Input (VB-Audio Virtual Cable)",
        "VoiceMeeter AUX",
        "VB-Audio VoiceMeeter VAIO",
        "VB-Audio VoiceMeeter AUX",
    ]

    # Create a test beep sound using ffmpeg
    test_file = tempfile.mktemp(suffix=".wav")
    print(f"Creating test audio file: {test_file}")

    # Generate a 440Hz beep for 1 second
    subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-y", test_file],
        capture_output=True,
        check=False,
    )

    print("\n" + "=" * 60)
    print("AUDIO DEVICE TESTING")
    print("=" * 60)

    # Method 1: Try listing available audio devices
    print("\n1. Listing available audio devices (ffmpeg):")
    print("-" * 40)
    try:
        result = subprocess.run(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True,
            text=True,
            stderr=subprocess.STDOUT,
            check=False,
        )
        # ffmpeg outputs to stderr
        output = result.stdout + result.stderr
        lines = output.split("\n")
        for line in lines:
            if "DirectShow audio devices" in line:
                print("\nFound audio devices:")
            if '"' in line and ("VoiceMeeter" in line or "CABLE" in line or "VB-Audio" in line):
                print(f"  {line.strip()}")
    except Exception as e:
        print(f"  Error listing devices: {e}")

    # Method 2: Try PowerShell to list audio devices
    print("\n2. Listing audio devices (PowerShell):")
    print("-" * 40)
    ps_script = """
    Get-WmiObject Win32_SoundDevice | Select-Object Name, Status | Format-Table -AutoSize
    """
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, check=False)
        print(result.stdout)
    except Exception as e:
        print(f"  Error: {e}")

    # Method 3: Test playback with each device
    print("\n3. Testing playback with each potential device:")
    print("-" * 40)

    for device in device_names:
        print(f"\nTrying device: '{device}'")

        # Try using Windows Media Foundation
        ps_script = f"""
        try {{
            Add-Type -AssemblyName presentationCore
            $player = New-Object System.Windows.Media.MediaPlayer
            $player.Open([Uri]"{test_file}")
            $player.Play()
            Start-Sleep -Seconds 2
            $player.Close()
            Write-Host "Success with MediaPlayer"
        }} catch {{
            Write-Host "MediaPlayer failed: $_"
        }}

        # Also try with .NET SoundPlayer (uses default device)
        try {{
            $sound = New-Object System.Media.SoundPlayer "{test_file}"
            $sound.PlaySync()
            Write-Host "Success with SoundPlayer"
        }} catch {{
            Write-Host "SoundPlayer failed: $_"
        }}
        """

        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5, check=False
            )
            print(f"  PowerShell result: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            print("  Timeout - might be playing")
        except Exception as e:
            print(f"  Error: {e}")

    # Method 4: Simple playback using default Windows audio
    print("\n4. Testing with default Windows audio (should always work):")
    print("-" * 40)
    ps_script = f"""
    # This should play through whatever is set as default in Windows
    $sound = New-Object System.Media.SoundPlayer "{test_file}"
    $sound.PlaySync()
    Write-Host "Played through default audio device"
    """
    try:
        subprocess.run(["powershell", "-Command", ps_script], timeout=3, check=False)
        print("  Success - audio played through default device")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print("IMPORTANT NOTES:")
    print("=" * 60)
    print(
        """
    1. Make sure VoiceMeeter is running
    2. In Windows Sound Settings, set default playback device to your speakers/headphones
    3. In VoiceMeeter, route the Virtual Input to your hardware output
    4. In VRChat, set microphone to 'VoiceMeeter Output' or 'VoiceMeeter Out B1'
    5. To make audio play through VoiceMeeter:
       - Option A: Set VoiceMeeter Input as Windows default playback device temporarily
       - Option B: Use audio routing software to target VoiceMeeter Input specifically
    """
    )

    # Clean up
    try:
        os.remove(test_file)
    except Exception:
        pass


if __name__ == "__main__":
    if sys.platform != "win32":
        print("This script is designed for Windows with VoiceMeeter")
        sys.exit(1)

    test_audio_playback()
