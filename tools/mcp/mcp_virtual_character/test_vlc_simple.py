#!/usr/bin/env python3
"""
Simple VLC test script to diagnose audio playback issues on Windows.
"""

import os
import subprocess
import sys
import tempfile


def create_test_tone():
    """Create a simple test tone using FFmpeg."""
    fd, test_file = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-y", test_file]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=5)
        print(f"[OK] Created test file: {test_file}")
        return test_file
    except Exception as e:
        print(f"[ERROR] Failed to create test file: {e}")
        return None


def find_vlc_executable():
    """Find VLC executable in standard Windows locations.

    Returns:
        str or None: Path to VLC executable if found, None otherwise.
    """
    vlc_paths = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]

    for path in vlc_paths:
        if os.path.exists(path):
            print(f"[OK] Found VLC at: {path}")
            return path

    print("[ERROR] VLC not found in standard locations")
    return None


def run_vlc_command(cmd, show_stderr=True):
    """Execute a VLC command and report results.

    Args:
        cmd: Command list to execute
        show_stderr: Whether to display stderr output
    """
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if show_stderr and result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")


def test_minimal_arguments(vlc_exe, audio_file):
    """Test VLC with minimal arguments.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n1. Testing minimal VLC arguments:")
    cmd = [vlc_exe, audio_file, "--play-and-exit"]
    run_vlc_command(cmd)


def test_interface_disabled(vlc_exe, audio_file):
    """Test VLC with dummy interface.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n2. Testing with --intf dummy:")
    cmd = [vlc_exe, audio_file, "--intf", "dummy", "--play-and-exit"]
    run_vlc_command(cmd)


def test_quit_command(vlc_exe, audio_file):
    """Test VLC with vlc://quit.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n3. Testing with vlc://quit:")
    cmd = [vlc_exe, audio_file, "--intf", "dummy", "--play-and-exit", "vlc://quit"]
    run_vlc_command(cmd)


def test_windows_start_command(vlc_exe, audio_file):
    """Test VLC using Windows start command.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n4. Testing with Windows start command:")
    cmd = ["cmd", "/c", "start", "/wait", "/b", vlc_exe, audio_file, "--play-and-exit", "--intf=dummy"]
    run_vlc_command(cmd, show_stderr=False)


def test_directsound_output(vlc_exe, audio_file):
    """Test VLC with DirectSound audio output.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n5. Testing with DirectSound output:")
    cmd = [vlc_exe, audio_file, "--aout", "directsound", "--play-and-exit", "--intf", "dummy"]
    run_vlc_command(cmd)


def test_waveout_output(vlc_exe, audio_file):
    """Test VLC with WaveOut audio output.

    Args:
        vlc_exe: Path to VLC executable
        audio_file: Path to audio file to play
    """
    print("\n6. Testing with WaveOut output:")
    cmd = [vlc_exe, audio_file, "--aout", "waveout", "--play-and-exit", "--intf", "dummy"]
    run_vlc_command(cmd)


def test_vlc_methods(audio_file):
    """Test different VLC invocation methods.

    Args:
        audio_file: Path to audio file to play

    Returns:
        bool: True if VLC was found, False otherwise
    """
    vlc_exe = find_vlc_executable()
    if not vlc_exe:
        return False

    print("\n" + "=" * 60)
    print("TESTING VLC PLAYBACK METHODS")
    print("=" * 60)

    test_minimal_arguments(vlc_exe, audio_file)
    test_interface_disabled(vlc_exe, audio_file)
    test_quit_command(vlc_exe, audio_file)
    test_windows_start_command(vlc_exe, audio_file)
    test_directsound_output(vlc_exe, audio_file)
    test_waveout_output(vlc_exe, audio_file)

    return True


def main():
    """Main test function."""
    print("=" * 60)
    print("VLC AUDIO PLAYBACK DIAGNOSTIC")
    print("=" * 60)

    # Create test audio
    audio_file = create_test_tone()
    if not audio_file:
        print("\n[ERROR] Cannot proceed without test audio file")
        return 1

    try:
        # Run tests
        test_vlc_methods(audio_file)

        print("\n" + "=" * 60)
        print("RECOMMENDATIONS:")
        print("=" * 60)
        print("1. If all methods fail, check VLC installation")
        print("2. Try running VLC manually with the test file")
        print("3. Check Windows audio settings")
        print("4. Ensure VLC audio output module is configured correctly")
        print("   (Tools -> Preferences -> Audio -> Output module)")

    finally:
        # Cleanup
        if os.path.exists(audio_file):
            os.remove(audio_file)
            print("\n[OK] Cleaned up test file")

    return 0


if __name__ == "__main__":
    sys.exit(main())
