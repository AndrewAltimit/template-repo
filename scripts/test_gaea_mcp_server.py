#!/usr/bin/env python3
"""
Quick test script to verify Gaea2 MCP server connectivity and basic operations.
This follows Phase 3 of the AI Agent Training Guide - Direct MCP Interaction.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Any, Dict

import aiohttp


class Gaea2MCPTester:
    """Test Gaea2 MCP server connectivity and operations."""

    def __init__(self, server_url: str = "http://192.168.0.152:8007"):
        self.server_url = server_url
        self.results = []

    async def test_connectivity(self) -> bool:
        """Test basic connectivity to the MCP server."""
        print(f"\n🔍 Testing connectivity to {self.server_url}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.server_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print("✅ Server is reachable")
                        return True
                    else:
                        print(f"❌ Server returned status {response.status}")
                        return False
        except aiohttp.ClientError as e:
            print(f"❌ Connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    async def test_tool_discovery(self) -> Dict[str, Any]:
        """Test MCP tool discovery endpoint."""
        print("\n🔍 Discovering available tools...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/mcp/tools",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        tools = await response.json()
                        print(f"✅ Found {len(tools)} tools:")
                        for tool in tools:
                            print(f"   - {tool['name']}: {tool.get('description', 'No description')[:80]}...")
                        return {"success": True, "tools": tools}
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to get tools: {error_text}")
                        return {"success": False, "error": error_text}
        except Exception as e:
            print(f"❌ Error discovering tools: {e}")
            return {"success": False, "error": str(e)}

    async def test_basic_operation(self) -> Dict[str, Any]:
        """Test a basic MCP operation."""
        print("\n🔍 Testing basic template creation...")

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "tool": "create_gaea2_from_template",
                    "parameters": {
                        "template_name": "basic_terrain",
                        "project_name": f"test_connectivity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    },
                }

                async with session.post(
                    f"{self.server_url}/mcp/execute",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()

                    if response.status == 200 and not result.get("error"):
                        print("✅ Successfully created basic terrain project")
                        print(f"   Project path: {result.get('project_path', 'N/A')}")
                        print(f"   Validation passed: {result.get('validation_passed', 'N/A')}")
                        return {"success": True, "result": result}
                    else:
                        print(f"❌ Operation failed: {result.get('error', 'Unknown error')}")
                        return {"success": False, "error": result.get("error")}

        except Exception as e:
            print(f"❌ Error executing operation: {e}")
            return {"success": False, "error": str(e)}

    async def test_validation(self) -> Dict[str, Any]:
        """Test workflow validation."""
        print("\n🔍 Testing workflow validation...")

        # Simple valid workflow
        workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
            ],
            "connections": [
                {
                    "source": "1",
                    "source_port": "Out",
                    "target": "2",
                    "target_port": "In",
                }
            ],
        }

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "tool": "validate_and_fix_workflow",
                    "parameters": {"workflow": workflow},
                }

                async with session.post(
                    f"{self.server_url}/mcp/execute",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()

                    if response.status == 200:
                        print("✅ Validation completed")
                        print(f"   Is valid: {result.get('is_valid', 'N/A')}")
                        print(f"   Issues found: {len(result.get('issues', []))}")
                        print(f"   Fixed issues: {len(result.get('fixed_issues', []))}")
                        return {"success": True, "result": result}
                    else:
                        print(f"❌ Validation failed: {result.get('error', 'Unknown error')}")
                        return {"success": False, "error": result.get("error")}

        except Exception as e:
            print(f"❌ Error during validation: {e}")
            return {"success": False, "error": str(e)}

    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling with invalid input."""
        print("\n🔍 Testing error handling...")

        try:
            async with aiohttp.ClientSession() as session:
                # Intentionally invalid request
                payload = {
                    "tool": "create_gaea2_from_template",
                    "parameters": {
                        "template_name": "this_template_does_not_exist",
                        "project_name": "error_test",
                    },
                }

                async with session.post(
                    f"{self.server_url}/mcp/execute",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result = await response.json()

                    if result.get("error"):
                        print("✅ Error handling works correctly")
                        print(f"   Error message: {result['error'][:100]}...")
                        return {"success": True, "error_handled": True}
                    else:
                        print("❌ Expected error but got success")
                        return {"success": False, "error": "No error when expected"}

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return {"success": False, "error": str(e)}

    async def run_all_tests(self):
        """Run all connectivity and operation tests."""
        print("🚀 Starting Gaea2 MCP Server Tests")
        print(f"   Server URL: {self.server_url}")
        print(f"   Timestamp: {datetime.now().isoformat()}")

        # Test 1: Basic connectivity
        if not await self.test_connectivity():
            print("\n❌ Failed to connect to server. Please check:")
            print("   1. Server is running at the specified URL")
            print("   2. Network connectivity to the server")
            print("   3. Firewall rules allow connection")
            return

        # Test 2: Tool discovery
        tools_result = await self.test_tool_discovery()
        self.results.append(("tool_discovery", tools_result))

        # Test 3: Basic operation
        operation_result = await self.test_basic_operation()
        self.results.append(("basic_operation", operation_result))

        # Test 4: Validation
        validation_result = await self.test_validation()
        self.results.append(("validation", validation_result))

        # Test 5: Error handling
        error_result = await self.test_error_handling()
        self.results.append(("error_handling", error_result))

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.results)
        passed_tests = sum(1 for _, result in self.results if result.get("success"))

        print(f"\nTotal tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")

        print("\nDetailed results:")
        for test_name, result in self.results:
            status = "✅ PASS" if result.get("success") else "❌ FAIL"
            print(f"  {test_name}: {status}")
            if not result.get("success") and result.get("error"):
                print(f"    Error: {result['error'][:80]}...")

        # Save results to file
        results_file = f"gaea2_mcp_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "server_url": self.server_url,
                    "results": self.results,
                    "summary": {
                        "total": total_tests,
                        "passed": passed_tests,
                        "failed": total_tests - passed_tests,
                    },
                },
                f,
                indent=2,
            )

        print(f"\n💾 Results saved to: {results_file}")

        if passed_tests == total_tests:
            print("\n🎉 All tests passed! The Gaea2 MCP server is working correctly.")
        else:
            print("\n⚠️  Some tests failed. Please check the server logs for details.")


async def main():
    """Main entry point."""
    # Check if custom server URL is provided
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.0.152:8007"

    tester = Gaea2MCPTester(server_url)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
