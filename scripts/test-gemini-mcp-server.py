#!/usr/bin/env python3
"""Test script for Gemini MCP Server"""

import sys

import requests


def test_gemini_mcp_server():
    """Test the Gemini MCP server endpoints"""
    base_url = "http://localhost:8006"

    print("Testing Gemini MCP Server...")
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
        print("❌ Cannot connect to Gemini MCP server on port 8006")
        print("   Please start it with: python tools/mcp/gemini_mcp_server.py")
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
            f"{base_url}/tools/consult_gemini", json=test_request, headers={"Content-Type": "application/json"}
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
    print("Test complete!")
    return True


if __name__ == "__main__":
    success = test_gemini_mcp_server()
    sys.exit(0 if success else 1)
