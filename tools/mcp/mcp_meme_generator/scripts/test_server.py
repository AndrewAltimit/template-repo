#!/usr/bin/env python3
"""Test script for Meme Generator MCP Server"""

import asyncio
import base64
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

SERVER_URL = "http://localhost:8016"


async def test_list_templates():
    """Test listing available meme templates"""
    print("\n=== Testing List Templates ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVER_URL}/mcp/execute",
            json={"tool": "list_meme_templates", "arguments": {}},
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        if result.get("success") and "result" in result:
            templates = result["result"]
            print(f"Response: {json.dumps(templates, indent=2)}")
        else:
            print(f"Response: {json.dumps(result, indent=2)}")
        return result


async def test_get_template_info():
    """Test getting template information"""
    print("\n=== Testing Get Template Info ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVER_URL}/mcp/execute",
            json={
                "tool": "get_meme_template_info",
                "arguments": {"template_id": "ol_reliable"},
            },
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        if result.get("success") and "result" in result:
            template_result = result["result"]
            if "template" in template_result:
                template = template_result["template"]
                print(f"Template Name: {template.get('name')}")
                print(f"Description: {template.get('description')}")
                print(f"Text Areas: {len(template.get('text_areas', []))}")
                for area in template.get("text_areas", []):
                    print(f"  - {area['id']}: {area.get('usage', 'N/A')}")
            else:
                print(f"Response: {json.dumps(template_result, indent=2)}")
        else:
            print(f"Response: {json.dumps(result, indent=2)}")
        return result


async def test_generate_meme():
    """Test generating a meme"""
    print("\n=== Testing Generate Meme ===")

    test_cases = [
        {
            "name": "Default Ol' Reliable",
            "template": "ol_reliable",
            "texts": {
                "top": "When the code won't compile",
                "bottom": "print('hello world')",
            },
            "auto_resize": True,
        },
        {
            "name": "Long Text Auto-Resize",
            "template": "ol_reliable",
            "texts": {
                "top": "When you've been debugging for 3 hours and nothing works",
                "bottom": "console.log('here')",
            },
            "auto_resize": True,
        },
        {
            "name": "Custom Font Size",
            "template": "ol_reliable",
            "texts": {
                "top": "Custom font size test",
                "bottom": "Ol' Reliable",
            },
            "font_size_override": {"top": 30, "bottom": 45},
            "auto_resize": False,
        },
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}: {test_case['name']} ---")

            request_data = {
                "template": test_case["template"],
                "texts": test_case["texts"],
                "auto_resize": test_case.get("auto_resize", True),
            }

            if "font_size_override" in test_case:
                request_data["font_size_override"] = test_case["font_size_override"]

            response = await client.post(
                f"{SERVER_URL}/mcp/execute",
                json={"tool": "generate_meme", "arguments": request_data},
            )

            print(f"Status: {response.status_code}")
            result = response.json()

            if result.get("success") and "result" in result:
                meme_result = result["result"]
            else:
                meme_result = result

            if meme_result.get("success"):
                print("✓ Meme generated successfully")
                print(f"  Output path: {meme_result.get('output_path')}")
                print(f"  Size: {meme_result.get('size_kb', 0):.2f} KB")

                if "visual_feedback" in meme_result:
                    feedback = meme_result["visual_feedback"]
                    if "data" in feedback:
                        print(f"  Visual feedback: {feedback['format']} ({feedback.get('size_kb', 0):.2f} KB)")

                        # Save preview image for manual inspection
                        preview_path = f"test_meme_{i}.jpg"
                        with open(preview_path, "wb") as f:
                            f.write(base64.b64decode(feedback["data"]))
                        print(f"  Preview saved to: {preview_path}")

                if "text_positions" in meme_result:
                    print("  Text positions calculated:")
                    for area_id, info in meme_result["text_positions"].items():
                        print(f"    {area_id}: {info['lines']} (font size: {info['font_size']})")
            else:
                print(f"✗ Error: {meme_result.get('error')}")


async def test_invalid_template():
    """Test error handling for invalid template"""
    print("\n=== Testing Invalid Template ===")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SERVER_URL}/mcp/execute",
            json={
                "tool": "generate_meme",
                "arguments": {
                    "template": "nonexistent_template",
                    "texts": {"top": "Test", "bottom": "Test"},
                },
            },
        )
        print(f"Status: {response.status_code}")
        result = response.json()
        if result.get("success") and "result" in result:
            print(f"Response: {json.dumps(result['result'], indent=2)}")
        else:
            print(f"Response: {json.dumps(result, indent=2)}")


async def test_health_check():
    """Test server health check"""
    print("\n=== Testing Health Check ===")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{SERVER_URL}/health")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("✓ Server is healthy")
            else:
                print("✗ Server health check failed")
        except httpx.ConnectError:
            print("✗ Could not connect to server")
            print("Make sure the server is running:")
            print("  docker-compose up -d mcp-meme-generator")
            print("  or")
            print("  python -m tools.mcp.meme_generator.server --mode http")
            return False
    return True


async def main():
    """Run all tests"""
    print("=" * 50)
    print("Meme Generator MCP Server Test Suite")
    print("=" * 50)

    # Check server health first
    if not await test_health_check():
        sys.exit(1)

    # Run tests
    await test_list_templates()
    await test_get_template_info()
    await test_generate_meme()
    await test_invalid_template()

    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
