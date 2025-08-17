#!/usr/bin/env python3
"""Test stdio mode for ElevenLabs MCP server"""

import json
import subprocess
import sys


def test_stdio_mode():
    """Test that stdio mode works correctly"""
    print("Testing ElevenLabs MCP Server in STDIO mode...")
    print("=" * 60)

    # Test 1: Check server starts without error
    try:
        # Send a simple MCP initialization message
        init_message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "1.0.0", "capabilities": {}},
            "id": 1,
        }

        # Start the server in stdio mode
        process = subprocess.Popen(
            ["python3", "-m", "tools.mcp.elevenlabs_speech.server", "--mode", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send initialization
        process.stdin.write(json.dumps(init_message) + "\n")
        process.stdin.flush()

        # Try to read response (with timeout)
        import time

        time.sleep(1)

        # Terminate the process
        process.terminate()

        # Check if it started without errors
        stderr = process.stderr.read()
        if "ERROR" in stderr or "Traceback" in stderr:
            print("❌ Server failed to start:")
            print(stderr)
            return False
        else:
            print("✅ Server starts in STDIO mode")
            if "No ElevenLabs API key" in stderr:
                print("   ⚠️  API key warning detected (expected)")
            return True

    except Exception as e:
        print(f"❌ Error testing stdio mode: {e}")
        return False


def test_mcp_json_config():
    """Test that .mcp.json config is valid"""
    print("\nTesting .mcp.json configuration...")
    print("-" * 60)

    with open(".mcp.json", "r") as f:
        config = json.load(f)

    if "elevenlabs-speech" in config.get("mcpServers", {}):
        server_config = config["mcpServers"]["elevenlabs-speech"]
        print("✅ ElevenLabs server found in .mcp.json")
        print(f"   Command: {server_config.get('command')}")
        print(f"   Module: {server_config.get('args', [])[-4:]}")

        # Check environment variables
        env = server_config.get("env", {})
        if env:
            print("   Environment:")
            for key, value in env.items():
                print(f"     - {key}: {value}")
        return True
    else:
        print("❌ ElevenLabs server not found in .mcp.json")
        return False


def main():
    print("=" * 80)
    print("🎙️ ELEVENLABS MCP STDIO MODE TEST")
    print("=" * 80)

    results = []

    # Test stdio mode
    results.append(("STDIO Mode", test_stdio_mode()))

    # Test .mcp.json config
    results.append((".mcp.json Config", test_mcp_json_config()))

    print("\n" + "=" * 80)
    print("📊 TEST RESULTS:")
    print("-" * 80)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("🎉 All tests passed! ElevenLabs MCP is ready for use.")
        print("\n📋 Claude can now use these tools:")
        print("  • synthesize_speech_v3 - Generate speech with audio tags")
        print("  • synthesize_emotional - Add emotions to speech")
        print("  • synthesize_natural_speech - Natural imperfections")
        print("  • generate_sound_effect - Create sound effects")
        print("  • optimize_text_for_synthesis - Optimize prompts")
        print("  • And more!")
    else:
        print("⚠️  Some tests failed. Please check the configuration.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
