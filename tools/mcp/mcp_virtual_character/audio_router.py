#!/usr/bin/env python3
"""
Windows Audio Router for VoiceMeeter
Ensures audio is properly routed to VoiceMeeter for VRChat.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Optional


class VoiceMeeterAudioRouter:
    """Routes audio to VoiceMeeter on Windows."""

    def __init__(self):
        self.voicemeeter_names = [
            "VoiceMeeter Input",
            "VoiceMeeter Aux Input",
            "VoiceMeeter VAIO",
            "CABLE Input (VB-Audio Virtual Cable)",
            "VB-Audio VoiceMeeter VAIO",
            "VB-Audio VoiceMeeter AUX",
        ]

    def validate_audio_file(self, file_path: str) -> bool:
        """Validate that audio file exists and is not corrupted."""
        if not os.path.exists(file_path):
            print(f"Error: File does not exist: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        if file_size < 100:
            print(f"Error: File too small ({file_size} bytes), likely corrupted")
            return False

        print(f"Audio file validated: {file_path} ({file_size} bytes)")
        return True

    def convert_to_wav(self, input_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convert audio file to WAV format for better compatibility."""
        if output_path is None:
            output_path = input_path.replace(Path(input_path).suffix, ".wav")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_path,
                "-acodec",
                "pcm_s16le",  # Standard PCM format
                "-ar",
                "44100",  # 44.1kHz sample rate
                "-ac",
                "2",  # Stereo
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)

            if result.returncode == 0 and os.path.exists(output_path):
                print(f"✓ Converted to WAV: {output_path}")
                return output_path
            else:
                print(f"✗ Conversion failed: {result.stderr}")
                return None

        except Exception as e:
            print(f"✗ Error converting to WAV: {e}")
            return None

    def play_with_vlc(self, audio_file: str, device_name: str) -> bool:
        """Play audio using VLC with specific device targeting."""
        try:
            # VLC command for Windows audio device targeting
            cmd = [
                "vlc",
                audio_file,
                "--intf",
                "dummy",  # No interface
                "--play-and-exit",  # Exit after playing
                "--no-video",  # Audio only
                "--aout",
                "waveout",  # Windows waveout
                "--waveout-audio-device",
                device_name,  # Target device
            ]

            # Fire-and-forget VLC playback - context manager not appropriate
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # pylint: disable=consider-using-with
            print(f"✓ Playing with VLC to {device_name}")

            # Give it time to play
            time.sleep(5)
            return True

        except FileNotFoundError:
            print("✗ VLC not installed")
            return False
        except Exception as e:
            print(f"✗ VLC playback failed: {e}")
            return False

    def play_with_powershell(self, audio_file: str) -> bool:
        """Play audio using PowerShell (plays to default device)."""
        try:
            # PowerShell script to play audio
            ps_script = f"""
            try {{
                # Method 1: .NET SoundPlayer (WAV only)
                if ('{audio_file}'.EndsWith('.wav')) {{
                    $player = New-Object System.Media.SoundPlayer
                    $player.SoundLocation = '{audio_file}'
                    $player.PlaySync()
                    Write-Host "Played with SoundPlayer"
                    exit 0
                }}

                # Method 2: Windows Media Player COM
                $wmp = New-Object -ComObject WMPlayer.OCX.7
                $media = $wmp.newMedia('{audio_file}')
                $wmp.currentPlaylist.appendItem($media)
                $wmp.controls.play()

                # Wait for playback to complete
                while ($wmp.playState -ne 1) {{
                    Start-Sleep -Milliseconds 100
                }}

                Write-Host "Played with WMP"
                exit 0
            }} catch {{
                Write-Error $_.Exception.Message
                exit 1
            }}
            """

            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

            if result.returncode == 0:
                print(f"✓ PowerShell playback successful: {result.stdout.strip()}")
                return True
            else:
                print(f"✗ PowerShell playback failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"✗ PowerShell error: {e}")
            return False

    def play_with_pygame(self, audio_file: str) -> bool:
        """Play audio using pygame (can work with MP3 and WAV)."""
        try:
            import pygame

            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            print("✓ Playing with pygame...")
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            pygame.mixer.quit()
            return True

        except ImportError:
            print("✗ pygame not installed")
            return False
        except Exception as e:
            print(f"✗ pygame playback failed: {e}")
            return False

    def set_default_audio_device(self) -> None:
        """Guide user to set VoiceMeeter as default device."""
        print("\n" + "=" * 60)
        print("IMPORTANT: Setting Default Audio Device")
        print("=" * 60)
        print(
            """
To ensure audio routes to VRChat through VoiceMeeter:

1. Right-click the speaker icon in Windows system tray
2. Select "Open Sound settings"
3. Under "Output", set default device to "VoiceMeeter Input"
4. In VoiceMeeter:
   - Hardware Out should be your speakers/headphones
   - Virtual Input (what we play to) routes to Hardware Out
   - In VRChat, set microphone to "VoiceMeeter Output"

This creates the audio path:
Python → VoiceMeeter Input → VoiceMeeter → VoiceMeeter Output → VRChat
        """
        )
        print("=" * 60)

    def play_audio(self, audio_file: str, prefer_device: Optional[str] = None) -> bool:
        """
        Play audio file through VoiceMeeter to VRChat.

        Args:
            audio_file: Path to audio file (MP3, WAV, etc.)
            prefer_device: Preferred device name (defaults to VoiceMeeter Input)

        Returns:
            True if playback succeeded
        """

        # Validate file
        if not self.validate_audio_file(audio_file):
            return False

        device = prefer_device or "VoiceMeeter Input"

        print(f"\nAttempting to play: {audio_file}")
        print(f"Target device: {device}")

        # Try different playback methods in order of preference

        # Method 1: Try VLC first (best device targeting)
        if self.play_with_vlc(audio_file, device):
            return True

        # Method 2: Convert to WAV and play
        wav_file = self.convert_to_wav(audio_file)
        if wav_file:
            # Try PowerShell with WAV
            if self.play_with_powershell(wav_file):
                try:
                    os.remove(wav_file)
                except OSError:
                    pass
                return True

            # Try pygame with WAV
            if self.play_with_pygame(wav_file):
                try:
                    os.remove(wav_file)
                except OSError:
                    pass
                return True

            # Clean up
            try:
                os.remove(wav_file)
            except OSError:
                pass

        # Method 3: Try pygame with original file
        if self.play_with_pygame(audio_file):
            return True

        # Method 4: PowerShell with original file
        if self.play_with_powershell(audio_file):
            return True

        print("\n✗ All playback methods failed")
        self.set_default_audio_device()
        return False


def test_audio_routing():
    """Test the audio routing system."""
    router = VoiceMeeterAudioRouter()

    # Create a test beep
    test_file = tempfile.mktemp(suffix=".wav")

    print("Creating test audio file...")
    cmd = ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-y", test_file]

    result = subprocess.run(cmd, capture_output=True, check=False)

    if result.returncode == 0:
        print(f"✓ Test file created: {test_file}")

        # Play the test audio
        success = router.play_audio(test_file)

        # Clean up
        try:
            os.remove(test_file)
        except OSError:
            pass

        if success:
            print("\n✓ Audio routing test successful!")
        else:
            print("\n✗ Audio routing test failed")
            router.set_default_audio_device()
    else:
        print("✗ Failed to create test audio")


if __name__ == "__main__":
    if sys.platform != "win32":
        print("This script is for Windows only")
        sys.exit(1)

    if len(sys.argv) > 1:
        # Play specified file
        router = VoiceMeeterAudioRouter()
        success = router.play_audio(sys.argv[1])
        sys.exit(0 if success else 1)
    else:
        # Run test
        test_audio_routing()
