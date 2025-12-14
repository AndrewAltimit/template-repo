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
    test_file = tempfile.mktemp(suffix=".wav")
    cmd = ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-y", test_file]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=5)
        print(f"[OK] Created test file: {test_file}")
        return test_file
    except Exception as e:
        print(f"[ERROR] Failed to create test file: {e}")
        return None


def test_vlc_methods(audio_file):
    """Test different VLC invocation methods."""

    # Find VLC
    vlc_paths = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]

    vlc_exe = None
    for path in vlc_paths:
        if os.path.exists(path):
            vlc_exe = path
            print(f"[OK] Found VLC at: {vlc_exe}")
            break

    if not vlc_exe:
        print("[ERROR] VLC not found in standard locations")
        return False

    print("\n" + "=" * 60)
    print("TESTING VLC PLAYBACK METHODS")
    print("=" * 60)

    # Method 1: Minimal arguments
    print("\n1. Testing minimal VLC arguments:")
    cmd = [vlc_exe, audio_file, "--play-and-exit"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

    # Method 2: With interface disabled
    print("\n2. Testing with --intf dummy:")
    cmd = [vlc_exe, audio_file, "--intf", "dummy", "--play-and-exit"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

    # Method 3: With quit command
    print("\n3. Testing with vlc://quit:")
    cmd = [vlc_exe, audio_file, "--intf", "dummy", "--play-and-exit", "vlc://quit"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

    # Method 4: Using start command (Windows)
    print("\n4. Testing with Windows start command:")
    cmd = ["cmd", "/c", "start", "/wait", "/b", vlc_exe, audio_file, "--play-and-exit", "--intf=dummy"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, shell=False, check=False)
        print(f"   Exit code: {result.returncode}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

    # Method 5: Direct audio output specification
    print("\n5. Testing with DirectSound output:")
    cmd = [vlc_exe, audio_file, "--aout", "directsound", "--play-and-exit", "--intf", "dummy"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

    # Method 6: WaveOut audio output
    print("\n6. Testing with WaveOut output:")
    cmd = [vlc_exe, audio_file, "--aout", "waveout", "--play-and-exit", "--intf", "dummy"]
    print(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5, text=True, check=False)
        print(f"   Exit code: {result.returncode}")
        if result.stderr:
            print(f"   Stderr: {result.stderr[:200]}")
        print(f"   Result: {'[OK]' if result.returncode == 0 else '[FAILED]'}")
    except subprocess.TimeoutExpired:
        print("   Result: [TIMEOUT]")
    except Exception as e:
        print(f"   Result: [ERROR] {e}")

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
