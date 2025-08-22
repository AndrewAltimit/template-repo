#!/usr/bin/env python3
"""
Simple test to verify OpenCode proxy integration
Tests the translation wrapper directly without OpenCode CLI
"""

import json
import sys

import requests


def test_direct_api():
    """Test the translation wrapper API directly"""
    print("=" * 60)
    print("Testing OpenCode Proxy Integration")
    print("=" * 60)
    print()

    # Test endpoint
    url = "http://localhost:8052/v1/chat/completions"

    # Test cases
    test_cases = [
        {
            "name": "Simple question",
            "payload": {
                "model": "claude-3.5-sonnet",
                "messages": [{"role": "user", "content": "What is your name?"}],
                "max_tokens": 50,
            },
        },
        {
            "name": "With system prompt",
            "payload": {
                "model": "claude-3.5-sonnet",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                ],
                "max_tokens": 50,
                "temperature": 0.7,
            },
        },
        {
            "name": "Different model",
            "payload": {"model": "gpt-4", "messages": [{"role": "user", "content": "Count to 3"}], "max_tokens": 20},
        },
    ]

    all_passed = True

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print("-" * 40)

        try:
            # Make request
            response = requests.post(url, json=test["payload"], timeout=5)

            if response.status_code == 200:
                data = response.json()

                # Extract response content
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Check if we got the expected response
                if content == "Hatsune Miku":
                    print(f"✅ PASSED - Got expected response: '{content}'")
                else:
                    print(f"❌ FAILED - Unexpected response: '{content}'")
                    all_passed = False

                # Show usage stats
                usage = data.get("usage", {})
                print(f"   Tokens: {usage.get('total_tokens', 0)} total")

            else:
                print(f"❌ FAILED - HTTP {response.status_code}")
                print(f"   Error: {response.text}")
                all_passed = False

        except Exception as e:
            print(f"❌ FAILED - Exception: {e}")
            all_passed = False

        print()

    # Test streaming
    print("Test 4: Streaming response")
    print("-" * 40)

    try:
        payload = {"model": "claude-3.5-sonnet", "messages": [{"role": "user", "content": "Hi"}], "stream": True}

        response = requests.post(url, json=payload, stream=True, timeout=5)

        if response.status_code == 200:
            full_content = ""
            chunk_count = 0

            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    full_content += delta["content"]
                                    chunk_count += 1
                        except json.JSONDecodeError:
                            pass

            if full_content == "Hatsune Miku":
                print(f"✅ PASSED - Streaming works ({chunk_count} chunks)")
                print(f"   Content: '{full_content}'")
            else:
                print(f"❌ FAILED - Unexpected stream: '{full_content}'")
                all_passed = False
        else:
            print(f"❌ FAILED - HTTP {response.status_code}")
            all_passed = False

    except Exception as e:
        print(f"❌ FAILED - Exception: {e}")
        all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("The proxy is working correctly!")
        print("All requests return 'Hatsune Miku' as expected.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Check the logs:")
        print("  tail -f /tmp/wrapper.log")
        print("  tail -f /tmp/mock_api.log")
        return 1


def check_services():
    """Check if required services are running"""
    print("Checking services...")

    services = [("Mock Company API", "http://localhost:8050/health"), ("Translation Wrapper", "http://localhost:8052/health")]

    all_running = True

    for name, url in services:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"  ✅ {name}: Running")
            else:
                print(f"  ❌ {name}: Not healthy")
                all_running = False
        except Exception:
            print(f"  ❌ {name}: Not running")
            all_running = False

    print()

    if not all_running:
        print("Please start services with:")
        print("  ./automation/proxy/toggle_opencode.sh start")
        print()
        return False

    return True


if __name__ == "__main__":
    print("\n🔧 OpenCode Proxy Integration Test\n")

    # Check services first
    if not check_services():
        sys.exit(1)

    # Run tests
    sys.exit(test_direct_api())
