#!/usr/bin/env python3
"""Test script to verify MCP servers properly expose their tool lists"""

import asyncio
import json
import sys
from typing import Any, Dict

import httpx

# Server configurations
SERVERS = {
    "AI Toolkit": {
        "url": "http://localhost:8012",
        "expected_tools": [
            "create_training_config",
            "list_configs",
            "get_config",
            "upload_dataset",
            "list_datasets",
            "start_training",
            "get_training_status",
            "stop_training",
            "list_training_jobs",
            "export_model",
            "list_exported_models",
            "download_model",
            "get_system_stats",
            "get_training_logs",
            "get_training_info",
        ],
    },
    "ComfyUI": {
        "url": "http://localhost:8013",
        "expected_tools": [
            "generate_image",
            "list_workflows",
            "get_workflow",
            "list_models",
            "upload_lora",
            "upload_lora_chunked_init",
            "upload_lora_chunk",
            "upload_lora_chunked_complete",
            "list_loras",
            "download_lora",
            "get_object_info",
            "get_system_info",
            "transfer_lora_from_ai_toolkit",
            "execute_workflow",
        ],
    },
    "Gaea2": {
        "url": "http://localhost:8007",
        "expected_tools": [
            "create_gaea2_project",
            "create_gaea2_from_template",
            "validate_and_fix_workflow",
            "analyze_workflow_patterns",
            "optimize_gaea2_properties",
            "suggest_gaea2_nodes",
            "repair_gaea2_project",
            "download_gaea2_project",
            "list_gaea2_projects",
        ],
    },
}


async def test_server_health(name: str, url: str) -> bool:
    """Test if server is running"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/health")
            if response.status_code == 200:
                print(f"✅ {name} server is healthy at {url}")
                return True
            else:
                print(f"❌ {name} server returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ {name} server not reachable at {url}: {e}")
        return False


async def test_mcp_protocol(name: str, url: str) -> Dict[str, Any]:
    """Test MCP protocol implementation"""
    session_id = None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Initialize session
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
                "id": 1,
            }

            print(f"\n📤 Sending initialize request to {name}...")
            response = await client.post(
                f"{url}/messages",
                json=init_request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                print(f"❌ Initialize failed with status {response.status_code}")
                return {
                    "success": False,
                    "error": f"Initialize failed: {response.status_code}",
                }

            init_result = response.json()
            print(f"📥 Initialize response: {json.dumps(init_result, indent=2)}")

            # Get session ID from headers
            session_id = response.headers.get("Mcp-Session-Id")
            if session_id:
                print(f"🔑 Got session ID: {session_id}")

            # 2. Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {},
            }

            print("\n📤 Sending initialized notification...")
            response = await client.post(
                f"{url}/messages",
                json=initialized_notification,
                headers={
                    "Content-Type": "application/json",
                    "Mcp-Session-Id": session_id or "",
                },
            )

            # Should return 202 Accepted for notification
            if response.status_code != 202:
                print(f"⚠️  Initialized notification returned {response.status_code} (expected 202)")

            # 3. List tools
            tools_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2,
            }

            print("\n📤 Sending tools/list request...")
            response = await client.post(
                f"{url}/messages",
                json=tools_request,
                headers={
                    "Content-Type": "application/json",
                    "Mcp-Session-Id": session_id or "",
                },
            )

            if response.status_code != 200:
                print(f"❌ Tools list failed with status {response.status_code}")
                return {
                    "success": False,
                    "error": f"Tools list failed: {response.status_code}",
                }

            tools_result = response.json()
            print(f"📥 Tools response: {json.dumps(tools_result, indent=2)}")

            # Extract tools from response
            if "result" in tools_result and "tools" in tools_result["result"]:
                tools = tools_result["result"]["tools"]
                tool_names = [tool["name"] for tool in tools]

                print(f"\n🔧 Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool['name']}: {tool.get('description', 'No description')}")

                return {"success": True, "tools": tool_names, "count": len(tools)}
            else:
                print("❌ Unexpected tools response format")
                return {"success": False, "error": "Invalid tools response format"}

    except Exception as e:
        print(f"❌ Error testing {name}: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Run tests for all servers"""
    print("🧪 Testing MCP Server Tool Exposure\n")

    results = {}

    for server_name, config in SERVERS.items():
        print(f"\n{'='*60}")
        print(f"Testing {server_name} MCP Server")
        print(f"{'='*60}")

        # Check health first
        if not await test_server_health(server_name, config["url"]):
            results[server_name] = {"status": "offline"}
            continue

        # Test MCP protocol
        result = await test_mcp_protocol(server_name, config["url"])

        if result["success"]:
            # Check against expected tools
            expected = set(config["expected_tools"])
            actual = set(result["tools"])

            missing = expected - actual
            extra = actual - expected

            if missing:
                print("\n⚠️  Missing expected tools:")
                for tool in missing:
                    print(f"   - {tool}")

            if extra:
                print("\n➕ Extra tools found:")
                for tool in extra:
                    print(f"   + {tool}")

            if not missing and not extra:
                print("\n✅ All expected tools present!")

            results[server_name] = {
                "status": "success",
                "tools_count": result["count"],
                "missing_tools": list(missing),
                "extra_tools": list(extra),
            }
        else:
            results[server_name] = {"status": "failed", "error": result["error"]}

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    for server_name, result in results.items():
        status = result["status"]
        if status == "offline":
            print(f"❌ {server_name}: Server offline")
        elif status == "failed":
            print(f"❌ {server_name}: Protocol test failed - {result['error']}")
        elif status == "success":
            missing_count = len(result["missing_tools"])
            extra_count = len(result["extra_tools"])
            if missing_count == 0 and extra_count == 0:
                print(f"✅ {server_name}: All tools correctly exposed ({result['tools_count']} tools)")
            else:
                print(f"⚠️  {server_name}: Tools exposed with issues - {missing_count} missing, {extra_count} extra")

    # Exit code based on results
    all_success = all(r["status"] == "success" and not r["missing_tools"] for r in results.values())
    sys.exit(0 if all_success else 1)


if __name__ == "__main__":
    asyncio.run(main())
