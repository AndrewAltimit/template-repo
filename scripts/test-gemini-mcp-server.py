#!/usr/bin/env python3
"""Test script for Gemini MCP Server"""

import argparse
import asyncio
import json
import os
import sys

import requests


def test_http_server():
    """Test the HTTP-based Gemini MCP server"""
    # Use environment variable for port with default
    port = os.environ.get("GEMINI_MCP_PORT", "8006")
    base_url = f"http://localhost:{port}"

    print("Testing Gemini MCP Server (HTTP mode)...")
    print("-" * 50)

    # Test 1: Check if server is running
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Gemini MCP server on port {port}")
        print("   Please start it with: ./scripts/start-gemini-mcp.sh --http")
        return False

    # Test 2: List available tools
    try:
        response = requests.get(f"{base_url}/mcp/tools")
        if response.status_code == 200:
            print("\n✅ Tool listing successful")
            tools = response.json()["tools"]
            for tool in tools:
                print(f"   - {tool['name']}: {tool['description']}")
        else:
            print(f"❌ Tool listing failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error listing tools: {e}")

    # Test 3: Test consult_gemini endpoint
    print("\n📝 Testing consult_gemini endpoint...")
    try:
        test_request = {
            "prompt": "What is the purpose of MCP (Model Context Protocol)?",
            "context": {"source": "test"},
            "max_retries": 1,
        }

        response = requests.post(
            f"{base_url}/tools/consult_gemini",
            json=test_request,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            result = response.json()
            print("✅ Gemini consultation successful")
            print(f"   Response preview: {result['response'][:200]}...")
            print(f"   Conversation ID: {result['conversation_id']}")
        else:
            print(f"❌ Gemini consultation failed: {response.status_code}")
            print(f"   Error: {response.json()}")
    except Exception as e:
        print(f"❌ Error consulting Gemini: {e}")

    # Test 4: Test clear_gemini_history endpoint
    print("\n🧹 Testing clear_gemini_history endpoint...")
    try:
        response = requests.post(f"{base_url}/tools/clear_gemini_history")

        if response.status_code == 200:
            result = response.json()
            print("✅ History clearing successful")
            print(f"   {result['message']}")
            print(f"   Cleared entries: {result['cleared_count']}")
        else:
            print(f"❌ History clearing failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error clearing history: {e}")

    print("\n" + "-" * 50)
    print("HTTP test complete!")
    return True


async def test_stdio_server():
    """Test the stdio-based Gemini MCP server"""
    print("Testing Gemini MCP Server (stdio mode)...")
    print("-" * 50)

    # Test basic server startup
    print("🔧 Testing server startup...")

    try:
        # Create a simple MCP request to list tools
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        # Start the server process
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "tools/mcp/gemini_mcp_server.py",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send initialization
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "0.1.0", "capabilities": {}},
        }

        # Send requests
        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()

        # Wait a bit for initialization
        await asyncio.sleep(1)

        # Send list tools request
        process.stdin.write((json.dumps(list_tools_request) + "\n").encode())
        await process.stdin.drain()

        # Close stdin to signal we're done
        process.stdin.close()

        # Wait for process to complete
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()

        # Check output
        if stdout:
            print("✅ Server responded")
            print(f"   stdout preview: {stdout.decode()[:200]}...")

            # Try to parse responses
            for line in stdout.decode().split("\n"):
                if line.strip():
                    try:
                        response = json.loads(line)
                        if "result" in response:
                            print(f"   Got result for request {response.get('id')}")
                    except json.JSONDecodeError:
                        pass

        if stderr:
            print(f"ℹ️  Server stderr: {stderr.decode()[:200]}...")

        print("\n✅ stdio server basic test passed")
        print("\nFor full testing, connect with an MCP client like:")
        print("  - Claude Desktop")
        print("  - VS Code MCP extension")
        print("  - Custom MCP client")

        return True

    except FileNotFoundError:
        print("❌ Could not find gemini_mcp_server.py")
        return False
    except Exception as e:
        print(f"❌ Error testing stdio server: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test Gemini MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="stdio",
        help="Test mode: http or stdio (default: stdio)",
    )

    args = parser.parse_args()

    if args.mode == "http":
        success = test_http_server()
    else:
        success = await test_stdio_server()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
