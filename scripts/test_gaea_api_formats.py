#!/usr/bin/env python3
"""Test both API formats (parameters and arguments) for Gaea2 MCP server"""

import json

import requests


def test_api_format(format_type="parameters"):
    """Test API with specified format"""
    url = "http://192.168.0.152:8007/mcp/execute"

    # Simple test payload
    payload = {
        "tool": "suggest_gaea2_nodes",
        format_type: {
            "current_nodes": ["Mountain", "Erosion"],
            "context": "add water features",
        },
    }

    print(f"\nTesting with '{format_type}' field:")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Success: {response.status_code}")
            print(f"Response: {json.dumps(result, indent=2)[:200]}...")
        else:
            print(f"✗ Failed: {response.status_code}")
            print(f"Response: {response.text[:200]}...")

    except Exception as e:
        print(f"✗ Error: {str(e)}")


def main():
    print("Testing Gaea2 MCP API format compatibility")
    print("=" * 50)

    # Test with 'parameters' (original format)
    test_api_format("parameters")

    # Test with 'arguments' (base server format)
    test_api_format("arguments")

    print("\n" + "=" * 50)
    print("Test complete!")


if __name__ == "__main__":
    main()
