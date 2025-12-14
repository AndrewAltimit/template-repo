#!/usr/bin/env python3
"""
Comprehensive Audio Routing Test Suite for VoiceMeeter + VRChat
Tests the complete audio pipeline from Python to VRChat
"""

from datetime import datetime
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from typing import List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("audio_test_results.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AudioRoutingTester:
    """Comprehensive tester for VoiceMeeter audio routing."""

    def __init__(self):
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {},
            "dependencies": {},
            "audio_devices": {},
            "voicemeeter": {},
            "routing_tests": {},
            "recommendations": [],
        }

    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
        """Run a command and return success, stdout, stderr."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def test_system_info(self):
        """Gather system information."""
        logger.info("=" * 60)
        logger.info("SYSTEM INFORMATION")
        logger.info("=" * 60)

        # Windows version
        success, stdout, _ = self.run_command(["wmic", "os", "get", "Caption,Version"])
        if success:
            self.test_results["system_info"]["windows_version"] = stdout.strip()
            logger.info(f"Windows: {stdout.strip()}")

        # Python version
        self.test_results["system_info"]["python_version"] = sys.version
        logger.info(f"Python: {sys.version}")

        # Current directory
        self.test_results["system_info"]["current_dir"] = os.getcwd()
        logger.info(f"Working Directory: {os.getcwd()}")

    def test_dependencies(self):
        """Test if required dependencies are installed."""
        logger.info("\n" + "=" * 60)
        logger.info("DEPENDENCY CHECK")
        logger.info("=" * 60)

        # Special handling for VLC on Windows
        vlc_installed = False
        vlc_version = "Not installed"
        vlc_paths = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]

        for vlc_path in vlc_paths:
            if os.path.exists(vlc_path):
                vlc_installed = True
                # Try to get version
                success, stdout, _stderr = self.run_command([vlc_path, "--version"], timeout=5)
                if success and stdout:
                    vlc_version = stdout.split("\n")[0][:50]
                else:
                    vlc_version = f"Found at {vlc_path}"
                break

        # If not found at standard locations, try PATH
        if not vlc_installed:
            success, stdout, _stderr = self.run_command(["vlc", "--version"], timeout=5)
            if success:
                vlc_installed = True
                vlc_version = stdout.split("\n")[0][:50] if stdout else "In PATH"

        dependencies = {
            "ffmpeg": ["ffmpeg", "-version"],
            "powershell": ["powershell", "-Command", "echo 'test'"],
        }

        # Test other dependencies
        for name, cmd in dependencies.items():
            success, stdout, _stderr = self.run_command(cmd, timeout=5)
            self.test_results["dependencies"][name] = {
                "installed": success,
                "version": stdout.split("\n")[0] if success else "Not installed",
            }

            status = "[OK] Installed" if success else "[X] Not installed"
            logger.info(f"{name}: {status}")
            if success and stdout:
                logger.info(f"  Version: {stdout.split(chr(10))[0][:50]}")

        # Add VLC results
        self.test_results["dependencies"]["vlc"] = {
            "installed": vlc_installed,
            "version": vlc_version,
        }
        status = "[OK] Installed" if vlc_installed else "[X] Not installed"
        logger.info(f"vlc: {status}")
        if vlc_installed:
            logger.info(f"  Version: {vlc_version}")

    def test_python_packages(self):
        """Test Python audio packages."""
        logger.info("\n" + "=" * 60)
        logger.info("PYTHON PACKAGES")
        logger.info("=" * 60)

        packages = ["pygame", "simpleaudio", "pyaudio", "sounddevice", "pycaw"]

        for package in packages:
            try:
                __import__(package)
                self.test_results["dependencies"][f"python_{package}"] = True
                logger.info(f"[OK] {package} installed")
            except ImportError:
                self.test_results["dependencies"][f"python_{package}"] = False
                logger.info(f"[X] {package} not installed")

    def list_audio_devices(self):
        """List all audio devices."""
        logger.info("\n" + "=" * 60)
        logger.info("AUDIO DEVICES")
        logger.info("=" * 60)

        # Method 1: PowerShell WMI
        logger.info("\n1. Windows Sound Devices (WMI):")
        ps_script = """
        Get-WmiObject Win32_SoundDevice | ForEach-Object {
            Write-Host "$($_.Name) - Status: $($_.Status)"
        }
        """
        success, stdout, _ = self.run_command(["powershell", "-Command", ps_script])
        if success:
            self.test_results["audio_devices"]["wmi"] = stdout.strip().split("\n")
            logger.info(stdout)

        # Method 2: FFmpeg devices
        logger.info("\n2. FFmpeg DirectShow Devices:")
        success, stdout, stderr = self.run_command(["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"])
        # FFmpeg outputs to stderr
        output = stderr if stderr else stdout
        audio_devices = []
        capture_audio = False
        for line in output.split("\n"):
            if "DirectShow audio devices" in line:
                capture_audio = True
            elif capture_audio and '"' in line:
                device = line.strip()
                audio_devices.append(device)
                logger.info(f"  {device}")
                if "voicemeeter" in line.lower() or "cable" in line.lower() or "vb-audio" in line.lower():
                    logger.info("    ^ VoiceMeeter device detected!")

        self.test_results["audio_devices"]["directshow"] = audio_devices

        # Method 3: Python sounddevice
        try:
            import sounddevice as sd

            logger.info("\n3. Python sounddevice:")
            devices = sd.query_devices()
            device_list = []
            for i, device in enumerate(devices):
                device_info = (
                    f"  [{i}] {device['name']} - {device['max_output_channels']} out, {device['max_input_channels']} in"
                )
                device_list.append(device_info)
                logger.info(device_info)
                if (
                    "voicemeeter" in device["name"].lower()
                    or "cable" in device["name"].lower()
                    or "vb-audio" in device["name"].lower()
                ):
                    logger.info("    ^ VoiceMeeter device detected!")
            self.test_results["audio_devices"]["sounddevice"] = device_list
        except ImportError:
            logger.info("  sounddevice not installed")

    def detect_voicemeeter(self):
        """Detect VoiceMeeter installation and status."""
        logger.info("\n" + "=" * 60)
        logger.info("VOICEMEETER DETECTION")
        logger.info("=" * 60)

        # Check if VoiceMeeter is installed
        voicemeeter_paths = [
            r"C:\Program Files (x86)\VB\Voicemeeter",
            r"C:\Program Files\VB\Voicemeeter",
            r"C:\Program Files (x86)\VB\VoicemeeterBanana",
            r"C:\Program Files\VB\VoicemeeterBanana",
        ]

        installed_path = None
        for path in voicemeeter_paths:
            if os.path.exists(path):
                installed_path = path
                break

        if installed_path:
            logger.info(f"[OK] VoiceMeeter installed at: {installed_path}")
            self.test_results["voicemeeter"]["installed"] = True
            self.test_results["voicemeeter"]["path"] = installed_path
        else:
            logger.info("[X] VoiceMeeter not found in standard locations")
            self.test_results["voicemeeter"]["installed"] = False

        # Check if VoiceMeeter is running
        success, stdout, _ = self.run_command(["tasklist", "/FI", "IMAGENAME eq voicemeeter*"])
        if success and "voicemeeter" in stdout.lower():
            logger.info("[OK] VoiceMeeter is running")
            self.test_results["voicemeeter"]["running"] = True
        else:
            logger.info("[X] VoiceMeeter is not running")
            self.test_results["voicemeeter"]["running"] = False

        # Check default audio device
        ps_script = """
        $defaultDevice = Get-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Multimedia\\Sound Mapper" `
            -Name "Playback" -ErrorAction SilentlyContinue
        if ($defaultDevice) {
            Write-Host "Default Device Registry: $($defaultDevice.Playback)"
        }

        # Alternative method
        Add-Type -TypeDefinition @'
        using System.Runtime.InteropServices;
        public class Audio {
            [DllImport("winmm.dll")]
            public static extern int waveOutGetNumDevs();
        }
'@
        $deviceCount = [Audio]::waveOutGetNumDevs()
        Write-Host "Total audio devices: $deviceCount"
        """

        success, stdout, _ = self.run_command(["powershell", "-Command", ps_script])
        if success:
            logger.info(f"System audio info: {stdout.strip()}")

    def create_test_audio(self) -> Optional[str]:
        """Create a test audio file."""
        logger.info("\n" + "=" * 60)
        logger.info("CREATING TEST AUDIO")
        logger.info("=" * 60)

        test_file = tempfile.mktemp(suffix=".wav")

        # Method 1: FFmpeg
        cmd = ["ffmpeg", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-y", test_file]

        success, _, _ = self.run_command(cmd)

        if success and os.path.exists(test_file):
            file_size = os.path.getsize(test_file)
            logger.info(f"[OK] Test audio created: {test_file} ({file_size} bytes)")
            return test_file
        else:
            logger.error("[X] Failed to create test audio")
            return None

    def test_audio_playback(self, audio_file: str):
        """Test different audio playback methods."""
        logger.info("\n" + "=" * 60)
        logger.info("AUDIO PLAYBACK TESTS")
        logger.info("=" * 60)

        if not audio_file or not os.path.exists(audio_file):
            logger.error("No audio file to test")
            return

        # Test 1: Windows Media Player (default device)
        logger.info("\n1. Testing Windows Media Player (default device):")
        ps_script = f"""
        try {{
            $player = New-Object -ComObject WMPlayer.OCX
            $player.URL = '{audio_file}'
            $player.controls.play()
            Start-Sleep -Seconds 2
            Write-Host "SUCCESS: WMP playback completed"
            exit 0
        }} catch {{
            Write-Host "ERROR: $($_.Exception.Message)"
            exit 1
        }}
        """
        success, stdout, stderr = self.run_command(["powershell", "-Command", ps_script], timeout=5)
        self.test_results["routing_tests"]["wmp_default"] = success
        logger.info(f"  Result: {'[OK] Success' if success else '[X] Failed'}")
        if stdout:
            logger.info(f"  Output: {stdout.strip()}")

        # Test 2: .NET SoundPlayer (WAV only, default device)
        logger.info("\n2. Testing .NET SoundPlayer (default device):")
        ps_script = f"""
        try {{
            $player = New-Object System.Media.SoundPlayer
            $player.SoundLocation = '{audio_file}'
            $player.PlaySync()
            Write-Host "SUCCESS: SoundPlayer playback completed"
            exit 0
        }} catch {{
            Write-Host "ERROR: $($_.Exception.Message)"
            exit 1
        }}
        """
        success, stdout, stderr = self.run_command(["powershell", "-Command", ps_script], timeout=5)
        self.test_results["routing_tests"]["soundplayer"] = success
        logger.info(f"  Result: {'[OK] Success' if success else '[X] Failed'}")
        if stdout:
            logger.info(f"  Output: {stdout.strip()}")

        # Test 3: VLC with specific device
        logger.info("\n3. Testing VLC with VoiceMeeter targeting:")

        # First try to find VLC executable
        vlc_paths = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]
        vlc_exe = None
        for path in vlc_paths:
            if os.path.exists(path):
                vlc_exe = path
                logger.info(f"  Found VLC at: {vlc_exe}")
                break

        if not vlc_exe:
            vlc_exe = "vlc"  # Try system PATH
            logger.info("  Using VLC from PATH")

        # Test with simpler arguments first
        logger.info("  Testing basic VLC playback (default device):")
        cmd = [
            vlc_exe,
            audio_file,
            "--intf",
            "dummy",  # No interface
            "--play-and-exit",  # Exit after playing
            "--no-video-title-show",  # Don't show title
            "--no-repeat",  # Don't repeat
            "--no-loop",  # Don't loop
            "vlc://quit",  # Quit after playing
        ]
        success, stdout, stderr = self.run_command(cmd, timeout=5)
        self.test_results["routing_tests"]["vlc_basic"] = success
        logger.info(f"    Result: {'[OK] Success' if success else '[X] Failed'}")
        if stderr:
            logger.info(f"    Error: {stderr[:200]}")  # Show first 200 chars of error

        # If basic playback works, try device targeting
        if success:
            vlc_devices = ["VoiceMeeter Input", "VoiceMeeter Aux Input", "CABLE Input"]
            for device in vlc_devices:
                logger.info(f"  Trying device: {device}")
                cmd = [
                    vlc_exe,
                    audio_file,
                    "--intf",
                    "dummy",
                    "--play-and-exit",
                    "--aout",
                    "directsound",  # Use DirectSound on Windows
                    "--directx-audio-device",
                    device,  # DirectSound device selection
                    "vlc://quit",
                ]
                success, _, stderr = self.run_command(cmd, timeout=5)
                self.test_results["routing_tests"][f"vlc_{device}"] = success
                logger.info(f"    Result: {'[OK] Success' if success else '[X] Failed'}")
                if success:
                    break
                elif stderr:
                    logger.info(f"    Error: {stderr[:100]}")

        # Test 3b: Alternative VLC method using PowerShell
        if not success and vlc_exe and vlc_exe != "vlc":
            logger.info("\n3b. Testing VLC via PowerShell:")
            ps_script = f"""
            $vlc = "{vlc_exe}"
            $audio = "{audio_file}"

            # Start VLC with simple arguments
            $proc = Start-Process -FilePath $vlc -ArgumentList @($audio, "--play-and-exit", "--intf=dummy") -PassThru

            # Wait up to 3 seconds
            $proc | Wait-Process -Timeout 3 -ErrorAction SilentlyContinue

            # Force stop if still running
            if (-not $proc.HasExited) {{
                $proc | Stop-Process -Force
            }}

            Write-Host "VLC playback attempted"
            exit 0
            """
            success, stdout, stderr = self.run_command(["powershell", "-Command", ps_script], timeout=5)
            self.test_results["routing_tests"]["vlc_powershell"] = success
            logger.info(f"  Result: {'[OK] Success' if success else '[X] Failed'}")

        # Test 4: FFmpeg playback
        logger.info("\n4. Testing FFmpeg playback:")
        cmd = ["ffplay", "-nodisp", "-autoexit", "-t", "2", audio_file]
        success, _, _ = self.run_command(cmd, timeout=5)
        self.test_results["routing_tests"]["ffplay"] = success
        logger.info(f"  Result: {'[OK] Success' if success else '[X] Failed'}")

        # Test 5: Python pygame
        logger.info("\n5. Testing Python pygame:")
        try:
            import pygame

            pygame.mixer.init()
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            time.sleep(2)
            pygame.mixer.quit()
            self.test_results["routing_tests"]["pygame"] = True
            logger.info("  Result: [OK] Success")
        except Exception as e:
            self.test_results["routing_tests"]["pygame"] = False
            logger.info(f"  Result: [X] Failed - {e}")

    def test_audio_flow(self):
        """Visualize and explain the audio flow."""
        logger.info("\n" + "=" * 60)
        logger.info("AUDIO FLOW DIAGRAM")
        logger.info("=" * 60)

        flow = """
        AUDIO ROUTING FLOW:
        ===================

        1. AUDIO SOURCE (Python/ElevenLabs)
           |
           v
        2. PLAYBACK METHOD
           |-> PowerShell (.NET/WMP)
           |-> VLC (with device targeting)
           |-> FFmpeg/FFplay
           +-> Python (pygame/simpleaudio)
           |
           v
        3. WINDOWS AUDIO SUBSYSTEM
           |
           v
        4. AUDIO DEVICE SELECTION
           |-> DEFAULT: System default device
           +-> TARGETED: Specific device (VLC only)
           |
           v
        5. VOICEMEETER INPUT (Virtual Cable)
           |-> Hardware Input 1: Physical Mic
           |-> Hardware Input 2: [Optional]
           +-> Virtual Input (VAIO): <-- OUR AUDIO GOES HERE
           |
           v
        6. VOICEMEETER ROUTING MATRIX
           |-> A1 (Hardware Out): Your Speakers/Headphones
           |-> A2 (Hardware Out): [Optional]
           |-> B1 (Virtual Out): --> VRChat Microphone
           +-> B2 (Virtual Out): [Optional]
           |
           v
        7. VRCHAT
           +-> Microphone Input: "VoiceMeeter Output B1"

        CRITICAL SETTINGS:
        ==================
        [ ] Windows default playback: VoiceMeeter Input
        [ ] VoiceMeeter Virtual Input -> A1 (to hear locally)
        [ ] VoiceMeeter Virtual Input -> B1 (to send to VRChat)
        [ ] VRChat Microphone: VoiceMeeter Output (B1)
        """

        logger.info(flow)
        self.test_results["audio_flow"] = flow

    def generate_recommendations(self):
        """Generate recommendations based on test results."""
        logger.info("\n" + "=" * 60)
        logger.info("RECOMMENDATIONS")
        logger.info("=" * 60)

        recommendations = []

        # Check VoiceMeeter
        if not self.test_results["voicemeeter"].get("installed"):
            recommendations.append("CRITICAL: Install VoiceMeeter from https://vb-audio.com/Voicemeeter/")
        elif not self.test_results["voicemeeter"].get("running"):
            recommendations.append("IMPORTANT: Start VoiceMeeter before testing")

        # Check dependencies
        if not self.test_results["dependencies"].get("vlc", {}).get("installed"):
            recommendations.append("RECOMMENDED: Install VLC for better device targeting")

        if not self.test_results["dependencies"].get("ffmpeg", {}).get("installed"):
            recommendations.append("RECOMMENDED: Install FFmpeg for audio conversion")

        # Check Python packages
        missing_packages = []
        for pkg in ["pygame", "simpleaudio"]:
            if not self.test_results["dependencies"].get(f"python_{pkg}"):
                missing_packages.append(pkg)

        if missing_packages:
            recommendations.append(f"OPTIONAL: Install Python packages: pip install {' '.join(missing_packages)}")

        # Check audio devices (case-insensitive)
        has_voicemeeter_device = False
        for devices in self.test_results["audio_devices"].values():
            if any(
                "voicemeeter" in str(d).lower() or "cable" in str(d).lower() or "vb-audio" in str(d).lower() for d in devices
            ):
                has_voicemeeter_device = True
                break

        if not has_voicemeeter_device:
            recommendations.append("WARNING: No VoiceMeeter audio devices detected")

        # Check routing tests
        any_success = any(self.test_results["routing_tests"].values())
        if not any_success:
            recommendations.append("CRITICAL: All audio playback tests failed - check audio configuration")

        self.test_results["recommendations"] = recommendations

        for i, rec in enumerate(recommendations, 1):
            logger.info(f"{i}. {rec}")

        if not recommendations:
            logger.info("[OK] All systems operational!")

    def save_results(self):
        """Save test results to file."""
        results_file = f"audio_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, indent=2, default=str)

        logger.info(f"\n[OK] Results saved to: {results_file}")
        return results_file

    def run_all_tests(self):
        """Run all tests in sequence."""
        logger.info("=" * 60)
        logger.info("COMPREHENSIVE AUDIO ROUTING TEST SUITE")
        logger.info("=" * 60)
        logger.info(f"Started at: {datetime.now()}")

        # Run tests
        self.test_system_info()
        self.test_dependencies()
        self.test_python_packages()
        self.list_audio_devices()
        self.detect_voicemeeter()

        # Create and test audio
        test_audio = self.create_test_audio()
        if test_audio:
            self.test_audio_playback(test_audio)
            # Clean up
            try:
                os.remove(test_audio)
            except OSError:
                pass

        self.test_audio_flow()
        self.generate_recommendations()

        # Save results
        results_file = self.save_results()

        logger.info("\n" + "=" * 60)
        logger.info("TEST SUITE COMPLETED")
        logger.info("=" * 60)

        # Summary
        success_count = sum(1 for v in self.test_results["routing_tests"].values() if v)
        total_count = len(self.test_results["routing_tests"])

        logger.info(f"Routing Tests: {success_count}/{total_count} successful")
        logger.info(f"Recommendations: {len(self.test_results['recommendations'])}")
        logger.info(f"Full results: {results_file}")

        return self.test_results


def main():
    """Main entry point."""
    if sys.platform != "win32":
        print("This test suite is for Windows only")
        sys.exit(1)

    tester = AudioRoutingTester()
    results = tester.run_all_tests()

    # Return non-zero if critical issues found
    if results["recommendations"]:
        for rec in results["recommendations"]:
            if "CRITICAL" in rec:
                sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
