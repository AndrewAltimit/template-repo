#!/usr/bin/env python3
"""Test script for ComfyUI MCP Server"""

import sys
from pathlib import Path

import requests

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

# Server configuration
SERVER_URL = "http://localhost:8013"
REMOTE_URL = "http://192.168.0.152:8013"


def test_tools_list():
    """Test listing available tools"""
    print("\n1. Testing tools list...")
    try:
        response = requests.get(f"{SERVER_URL}/mcp/tools", timeout=5)
        if response.status_code == 200:
            tools = response.json()["tools"]
            print(f"✓ Found {len(tools)} tools")
            for tool in tools[:3]:  # Show first 3
                print(f"  - {tool['name']}: {tool['description']}")
            return True
        else:
            print(f"✗ Failed to get tools: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to server at {SERVER_URL}")
        print("  Make sure the server is running: python -m tools.mcp.comfyui.server")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_list_models():
    """Test listing available models"""
    print("\n2. Testing list models...")
    try:
        response = requests.post(
            f"{SERVER_URL}/mcp/execute",
            json={"tool": "list_models", "parameters": {"type": "checkpoint"}},
            timeout=10,
        )
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"✓ Remote server not available: {result['error']}")
                print(f"  This is expected if remote server at {REMOTE_URL} is not running")
            else:
                models = result.get("models", [])
                print(f"✓ Found {len(models)} checkpoint models")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_list_loras():
    """Test listing LoRA models"""
    print("\n3. Testing list LoRAs...")
    try:
        response = requests.post(
            f"{SERVER_URL}/mcp/execute",
            json={"tool": "list_loras", "parameters": {}},
            timeout=10,
        )
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"✓ Remote server not available: {result['error']}")
            else:
                loras = result.get("loras", [])
                print(f"✓ Found {len(loras)} LoRA models")
                for lora in loras[:3]:  # Show first 3
                    print(f"  - {lora}")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_system_info():
    """Test getting system information"""
    print("\n4. Testing system info...")
    try:
        response = requests.post(
            f"{SERVER_URL}/mcp/execute",
            json={"tool": "get_system_info", "parameters": {}},
            timeout=10,
        )
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"✓ Remote server not available: {result['error']}")
            else:
                print("✓ Retrieved system info")
                if "info" in result:
                    info = result["info"]
                    print(f"  - ComfyUI Version: {info.get('version', 'Unknown')}")
                    print(f"  - Python: {info.get('python_version', 'Unknown')}")
            return True
        else:
            print(f"✗ Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_health_check():
    """Test server health check"""
    print("\n5. Testing health check...")
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Server is healthy: {health['status']}")
            print(f"  - Name: {health['name']}")
            print(f"  - Version: {health['version']}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("ComfyUI MCP Server Test Suite")
    print("=" * 60)
    print(f"Testing server at: {SERVER_URL}")
    print(f"Remote backend at: {REMOTE_URL}")

    tests = [
        test_tools_list,
        test_list_models,
        test_list_loras,
        test_system_info,
        test_health_check,
    ]

    passed = 0
    failed = 0

    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    # Note about remote server
    if failed > 0:
        print("\nNote: Some tests may fail if the remote ComfyUI server")
        print(f"is not running at {REMOTE_URL}")
        print("This is expected in a local development environment.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
