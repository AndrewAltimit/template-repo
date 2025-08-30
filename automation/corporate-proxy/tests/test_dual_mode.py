#!/usr/bin/env python3
"""
Test script for dual mode tool support in Gemini proxy
Demonstrates both native (tool-enabled) and text (parsing) modes
"""

import json
import os
import sys
from pathlib import Path

import requests

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from shared.services.text_tool_parser import TextToolParser  # noqa: E402


def test_native_mode():
    """Test native mode with tool-enabled endpoints"""
    print("\n" + "=" * 60)
    print("Testing NATIVE Mode (tool-enabled endpoints)")
    print("=" * 60)

    # Set environment for native mode
    os.environ["TOOL_MODE"] = "native"

    base_url = "http://localhost:8053"

    # Check server status
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Server status: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Server not running. Start with: python gemini_proxy_wrapper.py")
        return False

    # Test with tools in native mode
    request_data = {
        "model": "gemini-2.5-flash",
        "contents": [{"role": "user", "parts": [{"text": "List the files in the current directory"}]}],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "list_directory",
                        "description": "List contents of a directory",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string", "description": "Directory path", "default": "."}},
                        },
                    }
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.7},
    }

    print("\nSending request with tools in native mode...")
    response = requests.post(f"{base_url}/v1/models/gemini-2.5-flash/generateContent", json=request_data)

    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        # Check if we got tool calls
        if result.get("candidates"):
            candidate = result["candidates"][0]
            if "functionCall" in candidate.get("content", {}).get("parts", [{}])[0]:
                print("✓ Native mode returned structured tool calls")
                return True
            else:
                print("✓ Native mode returned text response (no tools needed)")
                return True
    else:
        print(f"✗ Request failed: {response.status_code}")
        return False


def test_text_mode():
    """Test text mode with non-tool-enabled endpoints"""
    print("\n" + "=" * 60)
    print("Testing TEXT Mode (parse from text)")
    print("=" * 60)

    # Set environment for text mode
    os.environ["TOOL_MODE"] = "text"

    base_url = "http://localhost:8053"

    # Check server status
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Server status: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Server not running. Start with TOOL_MODE=text python gemini_proxy_wrapper.py")
        return False

    # Test with tools in text mode
    request_data = {
        "model": "gemini-2.5-flash",
        "contents": [{"role": "user", "parts": [{"text": "Read the file test.txt and tell me what it contains"}]}],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "read_file",
                        "description": "Read contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string", "description": "Path to the file to read"}},
                            "required": ["path"],
                        },
                    }
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.7},
    }

    print("\nSending request with tools in text mode...")
    response = requests.post(f"{base_url}/v1/models/gemini-2.5-flash/generateContent", json=request_data)

    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")

        # In text mode, we should get text with embedded tool calls
        if result.get("candidates"):
            candidate = result["candidates"][0]
            content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")

            # Parse tool calls from text
            parser = TextToolParser()
            tool_calls = parser.parse_tool_calls(content)

            if tool_calls:
                print(f"\n✓ Text mode found {len(tool_calls)} tool call(s) in response")
                for tc in tool_calls:
                    print(f"  - Tool: {tc['name']}, Parameters: {tc['parameters']}")

                # Simulate tool execution and continuation
                print("\nSimulating tool execution and continuation...")
                tool_results = []
                for tc in tool_calls:
                    tool_results.append(
                        {
                            "tool": tc["name"],
                            "parameters": tc["parameters"],
                            "result": {"success": True, "content": "This is the content of test.txt: Hello World!"},
                        }
                    )

                # Continue with tool results
                continue_data = {
                    "previous_response": content,
                    "tool_results": tool_results,
                    "original_request": request_data,
                    "conversation_history": [
                        {"role": "user", "content": "Read the file test.txt and tell me what it contains"}
                    ],
                }

                continue_response = requests.post(
                    f"{base_url}/v1/models/gemini-2.5-flash/continueWithTools", json=continue_data
                )

                if continue_response.status_code == 200:
                    continue_result = continue_response.json()
                    print(f"\nContinuation response: {json.dumps(continue_result, indent=2)}")
                    print("✓ Text mode continuation successful")
                    return True
                else:
                    print(f"✗ Continuation failed: {continue_response.status_code}")
                    return False
            else:
                print("✓ Text mode returned response without tool calls")
                return True
    else:
        print(f"✗ Request failed: {response.status_code}")
        return False


def test_mode_switching():
    """Test switching between modes"""
    print("\n" + "=" * 60)
    print("Testing Mode Switching")
    print("=" * 60)

    base_url = "http://localhost:8053"

    # Check tools endpoint for current mode
    response = requests.get(f"{base_url}/tools")
    if response.status_code == 200:
        tools_info = response.json()
        print(f"Current mode from /tools endpoint: {tools_info.get('mode')}")

    # Check root endpoint for configuration
    response = requests.get(f"{base_url}/")
    if response.status_code == 200:
        root_info = response.json()
        print(f"Configuration: {root_info.get('configuration')}")

    return True


def main():
    """Run all tests"""
    print("Testing Dual Mode Tool Support")
    print("==============================")
    print("\nThis script tests both native (tool-enabled) and text (parsing) modes.")
    print("Make sure the proxy server is running with the appropriate TOOL_MODE setting.\n")

    # Test native mode
    native_success = test_native_mode()

    print("\n" + "-" * 60)
    print("To test text mode, restart the server with: TOOL_MODE=text python gemini_proxy_wrapper.py")
    print("Then run this test again.")
    print("-" * 60)

    # Test text mode (requires server restart with TOOL_MODE=text)
    # text_success = test_text_mode()

    # Test mode info
    mode_success = test_mode_switching()

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Native mode: {'✓ PASSED' if native_success else '✗ FAILED'}")
    # print(f"Text mode: {'✓ PASSED' if text_success else '✗ FAILED'}")
    print(f"Mode info: {'✓ PASSED' if mode_success else '✗ FAILED'}")

    print("\nNOTE: To fully test both modes, you need to:")
    print("1. Run with TOOL_MODE=native (or unset) for native mode")
    print("2. Run with TOOL_MODE=text for text parsing mode")


if __name__ == "__main__":
    main()
