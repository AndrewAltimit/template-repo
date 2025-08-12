#!/usr/bin/env python3
"""Test all MCP servers to ensure they're working correctly"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx


class MCPServerTester:
    """Test all MCP servers"""

    def __init__(self):
        self.servers = [
            {
                "name": "Code Quality",
                "module": "tools.mcp.code_quality.server",
                "port": 8010,
                "test_tool": "format_check",
                "test_args": {"path": __file__, "language": "python"},
            },
            {
                "name": "Content Creation",
                "module": "tools.mcp.content_creation.server",
                "port": 8011,
                "test_tool": "compile_latex",
                "test_args": {"content": "Hello \\LaTeX", "template": "article"},
            },
            {
                "name": "Gemini",
                "module": "tools.mcp.gemini.server",
                "port": 8006,
                "test_tool": "gemini_status",
                "test_args": {},
                "skip_container": True,  # Must run on host
            },
            {
                "name": "Gaea2",
                "module": "tools.mcp.gaea2.server",
                "port": 8007,
                "test_tool": "suggest_gaea2_nodes",
                "test_args": {"current_nodes": ["Mountain"]},
            },
            {
                "name": "AI Toolkit",
                "module": "tools.mcp.ai_toolkit.server",
                "port": 8012,
                "test_tool": "list_configs",
                "test_args": {},
                "remote_only": True,  # Requires remote server
            },
            {
                "name": "ComfyUI",
                "module": "tools.mcp.comfyui.server",
                "port": 8013,
                "test_tool": "list_loras",
                "test_args": {},
                "remote_only": True,  # Requires remote server
            },
        ]

    def is_port_open(self, port: int) -> bool:
        """Check if a port is already in use"""
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def is_running_in_container(self) -> bool:
        """Check if running in a container"""
        return Path("/.dockerenv").exists() or os.environ.get("CONTAINER_ENV") is not None

    async def start_server(self, server_info: dict) -> Optional[subprocess.Popen]:
        """Start an MCP server"""
        if self.is_port_open(server_info["port"]):
            print(f"⚠️  Port {server_info['port']} already in use, skipping {server_info['name']}")
            return None

        if server_info.get("skip_container") and self.is_running_in_container():
            print(f"⚠️  {server_info['name']} cannot run in container, skipping")
            return None

        cmd = [sys.executable, "-m", server_info["module"], "--mode", "http"]

        print(f"Starting {server_info['name']} server on port {server_info['port']}...")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Wait for server to start
        await asyncio.sleep(2)

        return process

    async def test_server(self, server_info: dict) -> bool:
        """Test a single server"""
        base_url = f"http://localhost:{server_info['port']}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Test health endpoint
                response = await client.get(f"{base_url}/health")
                if response.status_code != 200:
                    print(f"  ✗ Health check failed: {response.status_code}")
                    return False

                print("  ✓ Health check passed")

                # Test a tool
                response = await client.post(
                    f"{base_url}/mcp/execute",
                    json={
                        "tool": server_info["test_tool"],
                        "arguments": server_info["test_args"],
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success", False):
                        print(f"  ✓ Tool test passed: {server_info['test_tool']}")
                        return True
                    else:
                        print(f"  ✗ Tool test failed: {result.get('error', 'Unknown error')}")
                        return False
                else:
                    print(f"  ✗ Tool test failed: HTTP {response.status_code}")
                    return False

            except Exception as e:
                print(f"  ✗ Test failed: {str(e)}")
                return False

    async def run_tests(self):
        """Run all server tests"""
        print("MCP Server Test Suite")
        print("=" * 50)

        processes = []
        results = {}

        # Start all servers
        for server in self.servers:
            process = await self.start_server(server)
            if process:
                processes.append((server["name"], process))

        # Give servers time to fully start
        if processes:
            print("\nWaiting for servers to initialize...")
            await asyncio.sleep(3)

        # Test each server
        print("\nTesting servers...")
        print("-" * 50)

        for server in self.servers:
            print(f"\n{server['name']} Server:")
            if self.is_port_open(server["port"]):
                results[server["name"]] = await self.test_server(server)
            else:
                print("  ⚠️  Server not running")
                results[server["name"]] = None

        # Stop all servers we started
        print("\nStopping servers...")
        for name, process in processes:
            process.terminate()
            process.wait(timeout=5)
            print(f"  ✓ Stopped {name}")

        # Summary
        print("\n" + "=" * 50)
        print("Test Summary:")
        print("-" * 50)

        total = len(results)
        passed = sum(1 for r in results.values() if r is True)
        failed = sum(1 for r in results.values() if r is False)
        skipped = sum(1 for r in results.values() if r is None)

        for name, result in results.items():
            if result is True:
                print(f"  ✓ {name}: PASSED")
            elif result is False:
                print(f"  ✗ {name}: FAILED")
            else:
                print(f"  ⚠️  {name}: SKIPPED")

        print("-" * 50)
        print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")

        return failed == 0

    async def quick_test(self):
        """Quick test of already running servers"""
        print("Quick Test - Testing already running servers")
        print("=" * 50)

        results = {}

        for server in self.servers:
            print(f"\n{server['name']} Server:")
            if self.is_port_open(server["port"]):
                results[server["name"]] = await self.test_server(server)
            else:
                print(f"  ⚠️  Not running on port {server['port']}")
                results[server["name"]] = None

        # Summary
        print("\n" + "=" * 50)
        print("Quick Test Summary:")
        for name, result in results.items():
            if result is True:
                print(f"  ✓ {name}: PASSED")
            elif result is False:
                print(f"  ✗ {name}: FAILED")
            else:
                print(f"  - {name}: NOT RUNNING")


async def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Test all MCP servers")
    parser.add_argument("--quick", action="store_true", help="Quick test of already running servers")
    args = parser.parse_args()

    tester = MCPServerTester()

    if args.quick:
        await tester.quick_test()
    else:
        success = await tester.run_tests()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
