#!/usr/bin/env python3
"""Test VRChat movement through MCP interface."""

import asyncio
import json

import aiohttp


async def test_movement():
    """Test movement commands through MCP."""
    url = "http://192.168.0.152:8020/messages"

    # Test different movement approaches
    test_cases = [
        {"name": "Move forward (small value)", "params": {"parameters": {"move_forward": 0.5}}},
        {"name": "Move backward", "params": {"parameters": {"move_forward": -0.5}}},
        {"name": "Move right", "params": {"parameters": {"move_right": 0.5}}},
        {"name": "Move left", "params": {"parameters": {"move_right": -0.5}}},
        {"name": "Move diagonal (forward-right)", "params": {"parameters": {"move_forward": 0.7, "move_right": 0.7}}},
        {"name": "Run forward", "params": {"parameters": {"move_forward": 1.0, "run": True}}},
        {"name": "Jump", "params": {"parameters": {"jump": True}}},
        {"name": "Crouch", "params": {"parameters": {"crouch": True}}},
        {"name": "Stand up", "params": {"parameters": {"crouch": False}}},
        {"name": "Look around", "params": {"parameters": {"look_horizontal": 0.5, "look_vertical": 0.3}}},
    ]

    async with aiohttp.ClientSession() as session:
        print("Testing VRChat movement through MCP interface")
        print("=" * 50)

        for test in test_cases:
            print(f"\n{test['name']}...")

            # Send animation with movement parameters
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "send_animation", "arguments": test["params"]},
                "id": 1,
            }

            try:
                async with session.post(url, json=request) as response:
                    result = await response.json()

                    if "error" in result:
                        print(f"  ERROR: {result['error']['message']}")
                    elif "result" in result:
                        if result["result"]["content"]:
                            content = json.loads(result["result"]["content"][0]["text"])
                            if content.get("success"):
                                print("  ✓ Success")
                            else:
                                print(f"  ✗ Failed: {content.get('error', 'Unknown error')}")

            except Exception as e:
                print(f"  ERROR: {e}")

            # Wait between tests
            await asyncio.sleep(2)

        # Reset to neutral position
        print("\nResetting to neutral position...")
        reset_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "send_animation",
                "arguments": {
                    "parameters": {
                        "move_forward": 0.0,
                        "move_right": 0.0,
                        "look_horizontal": 0.0,
                        "look_vertical": 0.0,
                        "run": False,
                        "crouch": False,
                    }
                },
            },
            "id": 1,
        }

        async with session.post(url, json=reset_request) as response:
            result = await response.json()
            print("Reset complete")


if __name__ == "__main__":
    asyncio.run(test_movement())
