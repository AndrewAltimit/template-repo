#!/usr/bin/env python3
"""Test script for Codex MCP server"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from tools.mcp.codex.client import CodexClient  # noqa: E402


def test_codex_server():
    """Test the Codex MCP server functionality"""
    print("🧪 Testing Codex MCP Server...")
    print("=" * 50)

    client = CodexClient(port=8021)

    # Test 1: Get status
    print("\n1️⃣ Testing status endpoint...")
    try:
        status = client.get_status()
        print(f"✅ Status: {json.dumps(status, indent=2)}")
    except Exception as e:
        print(f"❌ Status failed: {e}")
        return

    # Test 2: Consult Codex
    print("\n2️⃣ Testing Codex consultation...")
    try:
        result = client.consult_codex(
            query="Write a function to reverse a string",
            mode="generate",
        )
        print(f"✅ Consultation result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"❌ Consultation failed: {e}")

    # Test 3: Clear history
    print("\n3️⃣ Testing clear history...")
    try:
        result = client.clear_history()
        print(f"✅ Clear history: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"❌ Clear history failed: {e}")

    # Test 4: Toggle auto-consult
    print("\n4️⃣ Testing toggle auto-consult...")
    try:
        result = client.toggle_auto_consult(enable=False)
        print(f"✅ Toggle result: {json.dumps(result, indent=2)}")

        # Toggle back
        result = client.toggle_auto_consult(enable=True)
        print(f"✅ Toggle back: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"❌ Toggle failed: {e}")

    print("\n" + "=" * 50)
    print("✨ Codex MCP Server tests complete!")


if __name__ == "__main__":
    test_codex_server()
