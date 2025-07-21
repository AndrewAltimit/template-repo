#!/usr/bin/env python3
"""Test script to verify Gaea2 MCP server accepts both 'parameters' and 'arguments' fields"""

import json
import sys

import requests


def test_parameter_formats():
    """Test both parameter formats"""
    url = "http://192.168.0.152:8007/mcp/execute"

    # Test payload with simple tool
    test_tool = "suggest_gaea2_nodes"
    test_data = {
        "current_nodes": ["Mountain", "Erosion"],
        "context": "add water features",
    }

    # Test with 'parameters' field
    print("Testing with 'parameters' field...")
    payload1 = {"tool": test_tool, "parameters": test_data}

    try:
        response1 = requests.post(url, json=payload1, timeout=10)
        print(f"Status: {response1.status_code}")
        print(f"Response: {json.dumps(response1.json(), indent=2)}")

        if response1.status_code == 200:
            print("✅ 'parameters' field works!")
        else:
            print("❌ 'parameters' field failed!")
    except Exception as e:
        print(f"❌ Error with 'parameters': {e}")

    print("\n" + "=" * 50 + "\n")

    # Test with 'arguments' field
    print("Testing with 'arguments' field...")
    payload2 = {"tool": test_tool, "arguments": test_data}

    try:
        response2 = requests.post(url, json=payload2, timeout=10)
        print(f"Status: {response2.status_code}")
        print(f"Response: {json.dumps(response2.json(), indent=2)}")

        if response2.status_code == 200:
            print("✅ 'arguments' field works!")
        else:
            print("❌ 'arguments' field failed!")
    except Exception as e:
        print(f"❌ Error with 'arguments': {e}")

    print("\n" + "=" * 50 + "\n")

    # Test with create_gaea2_project using parameters
    print("Testing create_gaea2_project with 'parameters' field...")
    create_payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_parameter_fix",
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "Erosion", "position": {"X": 200, "Y": 0}},
            ],
            "connections": [{"from_node": "1", "from_port": "Out", "to_node": "2", "to_port": "In"}],
        },
    }

    try:
        response3 = requests.post(url, json=create_payload, timeout=30)
        print(f"Status: {response3.status_code}")
        result = response3.json()

        if response3.status_code == 200 and not result.get("error"):
            print("✅ create_gaea2_project with 'parameters' works!")
            print(f"Project created: {result.get('result', {}).get('project_path', 'Unknown')}")
        else:
            print("❌ create_gaea2_project with 'parameters' failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error with create_gaea2_project: {e}")


if __name__ == "__main__":
    print("Testing Gaea2 MCP Server parameter handling fix...\n")
    test_parameter_formats()
