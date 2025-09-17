#!/usr/bin/env python3
"""
Virtual Character System Setup Validator

Run this script to check your entire virtual character setup:
- Environment configuration
- Network connectivity
- Storage service
- Path mappings
- MCP server connection
"""

import os
import socket
import sys
from datetime import datetime
from pathlib import Path

import requests


class SetupValidator:
    """Comprehensive setup validation for Virtual Character system."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.successes = []
        self.fixes = []

    def run_all_checks(self):
        """Run all validation checks."""
        print("=" * 60)
        print("VIRTUAL CHARACTER SYSTEM VALIDATION")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Platform: {sys.platform}")
        print(f"Python: {sys.version.split()[0]}")
        print()

        # Run checks in order
        self._check_environment()
        self._check_network_topology()
        self._check_storage_service()
        self._check_mcp_server()
        self._check_path_mappings()
        self._check_dependencies()

        # Report results
        self._print_report()

    def _check_environment(self):
        """Check environment variables."""
        print("1. ENVIRONMENT VARIABLES")
        print("-" * 30)

        # Try to load .env
        env_file = Path(".env")
        if not env_file.exists():
            # Search in parent directories
            for parent in Path.cwd().parents:
                potential = parent / ".env"
                if potential.exists():
                    env_file = potential
                    break

        if env_file.exists():
            print(f"✓ Found .env file: {env_file}")
            self.successes.append("Environment file found")

            # Load and check variables
            env_vars = {}
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip().strip('"').strip("'")

            # Check required variables
            required = {
                "STORAGE_SECRET_KEY": "Secret key for storage authentication",
                "STORAGE_BASE_URL": "URL for storage service",
                "VIRTUAL_CHARACTER_SERVER": "URL for character MCP server",
            }

            for key, description in required.items():
                value = env_vars.get(key) or os.getenv(key)
                if value:
                    if key == "STORAGE_SECRET_KEY":
                        masked = value[:4] + "****" + value[-4:] if len(value) > 8 else "****"
                        print(f"  ✓ {key}: {masked}")
                    else:
                        print(f"  ✓ {key}: {value}")
                    self.successes.append(f"{key} configured")
                else:
                    print(f"  ✗ {key}: NOT SET ({description})")
                    self.errors.append(f"{key} not configured")
                    self.fixes.append(f"Add {key}=<value> to your .env file")
        else:
            print("✗ No .env file found")
            self.errors.append("Missing .env file")
            self.fixes.append("Create a .env file in the repository root")

        print()

    def _check_network_topology(self):
        """Detect and validate network topology."""
        print("2. NETWORK TOPOLOGY")
        print("-" * 30)

        # Detect if we're in a VM/container
        is_vm = False
        is_wsl = False
        vm_type = "Native"

        if Path("/proc/version").exists():
            with open("/proc/version", "r") as f:
                version = f.read().lower()
                if "microsoft" in version:
                    is_wsl = True
                    vm_type = "WSL/WSL2"
                elif "wsl" in version:
                    is_wsl = True
                    vm_type = "WSL"
                elif any(x in version for x in ["vmware", "virtualbox", "hyperv", "kvm"]):
                    is_vm = True
                    vm_type = "Virtual Machine"

        print(f"Environment: {vm_type}")

        if is_wsl or is_vm:
            print("  ℹ Running in virtualized environment")
            print("  Storage and MCP servers should be on host machine")

            # Get host IP
            try:
                # Try to get default gateway (usually host in VM)
                import subprocess

                result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
                if result.returncode == 0:
                    gateway = result.stdout.split()[2]
                    print(f"  Host IP (detected): {gateway}")
                    self.successes.append(f"Detected host IP: {gateway}")
            except Exception as e:
                print(f"  ⚠ Could not detect host IP: {e}")
                self.warnings.append("Could not auto-detect host IP")
        else:
            print("  Running on native Windows")
            print("  Services can use localhost")

        # Test connectivity to common IPs
        test_ips = [
            ("127.0.0.1", "Localhost"),
            ("192.168.0.152", "Common Windows host"),
            ("192.168.1.1", "Router/Gateway"),
        ]

        print("\nConnectivity tests:")
        for ip, description in test_ips:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                # Try common port
                result = sock.connect_ex((ip, 8020))
                sock.close()

                if result == 0:
                    print(f"  ✓ {ip:15} ({description}) - Port 8020 open")
                else:
                    # Just test ping
                    response = os.system(f"ping -c 1 -W 1 {ip} > /dev/null 2>&1")
                    if response == 0:
                        print(f"  ℹ {ip:15} ({description}) - Reachable")
                    else:
                        print(f"  ✗ {ip:15} ({description}) - Not reachable")
            except Exception:
                print(f"  ✗ {ip:15} ({description}) - Error testing")

        print()

    def _check_storage_service(self):
        """Check storage service connectivity and health."""
        print("3. STORAGE SERVICE")
        print("-" * 30)

        storage_url = os.getenv("STORAGE_BASE_URL", "http://localhost:8021")
        print(f"Storage URL: {storage_url}")

        try:
            # Check health endpoint
            response = requests.get(f"{storage_url}/health", timeout=5)
            if response.status_code == 200:
                print("  ✓ Storage service is healthy")
                self.successes.append("Storage service running")

                # Try to get more info
                try:
                    data = response.json()
                    if "uptime" in data:
                        print(f"    Uptime: {data['uptime']}")
                    if "files_count" in data:
                        print(f"    Files stored: {data['files_count']}")
                except Exception:
                    pass
            else:
                print(f"  ✗ Storage service returned: {response.status_code}")
                self.errors.append(f"Storage service error: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("  ✗ Cannot connect to storage service")
            self.errors.append("Storage service not reachable")
            self.fixes.append(f"Start storage service or check URL: {storage_url}")
        except requests.exceptions.Timeout:
            print("  ✗ Storage service timeout")
            self.errors.append("Storage service timeout")
        except Exception as e:
            print(f"  ✗ Storage service error: {e}")
            self.errors.append(f"Storage service error: {e}")

        # Test authentication if service is up
        secret = os.getenv("STORAGE_SECRET_KEY")
        if secret:
            print("\n  Testing authentication...")
            try:
                import hashlib
                import hmac

                token = hmac.new(secret.encode(), b"audio_storage_token", hashlib.sha256).hexdigest()
                headers = {"Authorization": f"Bearer {token}"}

                # Try a simple upload test
                files = {"file": ("test.txt", b"test content", "text/plain")}
                response = requests.post(f"{storage_url}/upload", files=files, headers=headers, timeout=5)

                if response.status_code == 200:
                    print("    ✓ Authentication successful")
                    self.successes.append("Storage authentication working")
                elif response.status_code == 401:
                    print("    ✗ Authentication failed (check STORAGE_SECRET_KEY)")
                    self.errors.append("Storage authentication failed")
                    self.fixes.append("Ensure STORAGE_SECRET_KEY matches on both systems")
                else:
                    print(f"    ⚠ Unexpected response: {response.status_code}")
            except Exception as e:
                print(f"    ✗ Could not test authentication: {e}")

        print()

    def _check_mcp_server(self):
        """Check MCP server connectivity."""
        print("4. MCP SERVER")
        print("-" * 30)

        server_url = os.getenv("VIRTUAL_CHARACTER_SERVER", "http://localhost:8020")
        print(f"Server URL: {server_url}")

        try:
            # Check if server responds
            response = requests.get(f"{server_url}/", timeout=5)
            print("  ✓ MCP server is responding")
            self.successes.append("MCP server reachable")

            # Try to get backend status
            try:
                response = requests.get(f"{server_url}/get_backend_status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("connected"):
                        backend = data.get("backend", "unknown")
                        print(f"  ✓ Connected to backend: {backend}")
                        self.successes.append(f"Connected to {backend} backend")
                    else:
                        print("  ℹ No backend connected")
                        self.warnings.append("No backend connected")
            except Exception:
                pass

        except requests.exceptions.ConnectionError:
            print("  ✗ Cannot connect to MCP server")
            self.errors.append("MCP server not reachable")
            self.fixes.append(f"Start MCP server or check URL: {server_url}")
        except Exception as e:
            print(f"  ✗ MCP server error: {e}")
            self.errors.append(f"MCP server error: {e}")

        print()

    def _check_path_mappings(self):
        """Check common path mappings."""
        print("5. PATH MAPPINGS")
        print("-" * 30)

        # Check if output directories exist
        output_dirs = [
            "outputs/elevenlabs_speech",
            "outputs/audio_storage",
            "outputs/comfyui",
        ]

        for dir_path in output_dirs:
            path = Path(dir_path)
            if path.exists():
                # Count files
                files = list(path.rglob("*"))
                file_count = sum(1 for f in files if f.is_file())
                print(f"  ✓ {dir_path} ({file_count} files)")
                self.successes.append(f"{dir_path} exists")
            else:
                print(f"  ✗ {dir_path} - NOT FOUND")
                self.warnings.append(f"{dir_path} not found")

        # Check container paths if in container
        if Path("/tmp").exists():
            container_paths = [
                "/tmp/elevenlabs_audio",
                "/tmp/audio_storage",
            ]

            print("\nContainer paths:")
            for path_str in container_paths:
                path = Path(path_str)
                if path.exists():
                    print(f"  ✓ {path_str}")
                else:
                    print(f"  ℹ {path_str} - Not created yet")

        print()

    def _check_dependencies(self):
        """Check Python dependencies."""
        print("6. DEPENDENCIES")
        print("-" * 30)

        required_packages = [
            ("aiohttp", "Async HTTP client"),
            ("requests", "HTTP client"),
            ("fastapi", "Web framework"),
            ("uvicorn", "ASGI server"),
            ("pythonosc", "OSC protocol", "python-osc"),
        ]

        for package_info in required_packages:
            package = package_info[0]
            description = package_info[1]
            import_name = package_info[2] if len(package_info) > 2 else package

            try:
                __import__(import_name)
                print(f"  ✓ {package:15} - {description}")
                self.successes.append(f"{package} installed")
            except ImportError:
                print(f"  ✗ {package:15} - {description}")
                self.errors.append(f"{package} not installed")
                self.fixes.append(f"pip install {package}")

        print()

    def _print_report(self):
        """Print final validation report."""
        print("=" * 60)
        print("VALIDATION REPORT")
        print("=" * 60)

        if self.successes:
            print(f"\n✓ SUCCESSES ({len(self.successes)}):")
            for success in self.successes:
                print(f"  • {success}")

        if self.warnings:
            print(f"\n⚠ WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.errors:
            print(f"\n✗ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.fixes:
            print("\n💡 SUGGESTED FIXES:")
            for i, fix in enumerate(self.fixes, 1):
                print(f"  {i}. {fix}")

        # Overall status
        print("\n" + "=" * 60)
        if not self.errors:
            print("✅ SYSTEM READY - All critical checks passed!")
        elif len(self.errors) <= 2:
            print("⚠️  MOSTLY READY - Minor issues to fix")
        else:
            print("❌ NEEDS ATTENTION - Several issues need fixing")

        print("=" * 60)


def main():
    """Run the validator."""
    validator = SetupValidator()

    # Add environment loading
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from utils.env_loader import load_env_file

        loaded = load_env_file()
        if loaded:
            print(f"Loaded {len(loaded)} environment variables from .env\n")
    except ImportError:
        pass

    validator.run_all_checks()

    # Test audio if requested
    if len(sys.argv) > 1 and sys.argv[1] == "test-audio":
        print("\n" + "=" * 60)
        print("AUDIO TEST")
        print("=" * 60)

        try:
            from seamless_audio_v2 import test_configuration

            test_configuration()
        except Exception as e:
            print(f"Could not run audio test: {e}")


if __name__ == "__main__":
    main()
