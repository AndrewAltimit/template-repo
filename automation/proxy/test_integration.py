#!/usr/bin/env python3
"""
Test script to verify the API translation wrapper works correctly
Tests both direct API calls and OpenCode integration
"""

import json
import logging
import subprocess
import sys
import time
from typing import Any, Dict

import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def test_mock_company_api():
    """Test the mock company API directly"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Mock Company API")
    logger.info("=" * 60)

    url = "http://localhost:8050/api/v1/AI/GenAIExplorationLab/Models/ai-coe-bedrock-claude35-sonnet-200k:analyze=null"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer test-secret-token-123"}
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "system": "You are a helpful AI assistant",
        "messages": [{"role": "user", "content": "Who are you?"}],
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")

        # Check if we got "Hatsune Miku" in response
        response_data = response.json()
        if response_data.get("content", [{}])[0].get("text") == "Hatsune Miku":
            logger.info("✓ Mock API is working correctly - returned 'Hatsune Miku'")
            return True
        else:
            logger.error("✗ Mock API did not return expected response")
            return False
    except Exception as e:
        logger.error(f"✗ Failed to connect to mock API: {e}")
        return False


def test_translation_wrapper():
    """Test the API translation wrapper"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing API Translation Wrapper")
    logger.info("=" * 60)

    url = "http://localhost:8052/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    body = {
        "model": "claude-3.5-sonnet",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "What is your name?"},
        ],
        "max_tokens": 100,
        "temperature": 0.7,
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {json.dumps(response.json(), indent=2)}")

        # Check if we got "Hatsune Miku" in response
        response_data = response.json()
        content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content == "Hatsune Miku":
            logger.info("✓ Translation wrapper is working correctly - returned 'Hatsune Miku'")
            return True
        else:
            logger.error(f"✗ Translation wrapper did not return expected response. Got: {content}")
            return False
    except Exception as e:
        logger.error(f"✗ Failed to connect to translation wrapper: {e}")
        return False


def test_translation_wrapper_streaming():
    """Test the API translation wrapper with streaming"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing API Translation Wrapper (Streaming)")
    logger.info("=" * 60)

    url = "http://localhost:8052/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    body = {
        "model": "claude-3.5-sonnet",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 100,
        "stream": True,
    }

    try:
        response = requests.post(url, json=body, headers=headers, stream=True, timeout=5)
        logger.info(f"Status: {response.status_code}")

        full_content = ""
        logger.info("Streaming response:")
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        logger.info("  [Stream ended]")
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                content = delta["content"]
                                full_content += content
                                logger.info(f"  Chunk: {repr(content)}")
                    except json.JSONDecodeError:
                        pass

        logger.info(f"Full streamed content: {repr(full_content)}")
        if full_content == "Hatsune Miku":
            logger.info("✓ Streaming is working correctly - returned 'Hatsune Miku'")
            return True
        else:
            logger.error(f"✗ Streaming did not return expected response")
            return False
    except Exception as e:
        logger.error(f"✗ Failed streaming test: {e}")
        return False


def test_opencode_integration():
    """Test OpenCode with custom configuration"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing OpenCode Integration")
    logger.info("=" * 60)

    config_path = "/home/miku/Documents/repos/template-repo/automation/proxy/opencode-custom.jsonc"

    # Create a simple test using OpenCode CLI
    test_prompt = "Say hello"

    try:
        # Set environment variable for the custom config
        import os

        env = os.environ.copy()
        env["OPENCODE_CONFIG"] = config_path
        env["COMPANY_API_KEY"] = "mock-api-key-for-testing"

        logger.info(f"Running OpenCode with custom config: {config_path}")
        logger.info(f"Prompt: {test_prompt}")

        # Run OpenCode with the test prompt
        result = subprocess.run(["opencode", "run", "-q", test_prompt], capture_output=True, text=True, timeout=10, env=env)

        logger.info(f"Exit code: {result.returncode}")
        logger.info(f"Output: {result.stdout}")
        if result.stderr:
            logger.info(f"Errors: {result.stderr}")

        # Check if we got "Hatsune Miku" in the output
        if "Hatsune Miku" in result.stdout:
            logger.info("✓ OpenCode integration working - received 'Hatsune Miku'")
            return True
        else:
            logger.error("✗ OpenCode did not return expected response")
            return False

    except subprocess.TimeoutExpired:
        logger.error("✗ OpenCode command timed out")
        return False
    except FileNotFoundError:
        logger.warning("⚠ OpenCode CLI not found - skipping integration test")
        logger.info("  Install OpenCode: npm install -g @sst/opencode")
        return None
    except Exception as e:
        logger.error(f"✗ Failed to run OpenCode: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "#" * 60)
    logger.info("# API Translation Wrapper Test Suite")
    logger.info("#" * 60)

    logger.info("\nMake sure the following services are running:")
    logger.info("1. Mock Company API: python automation/proxy/mock_company_api.py")
    logger.info("2. Translation Wrapper: python automation/proxy/api_translation_wrapper.py")
    logger.info("")

    input("Press Enter to start tests...")

    results = {}

    # Test 1: Mock Company API
    results["mock_api"] = test_mock_company_api()

    # Test 2: Translation Wrapper
    if results["mock_api"]:
        results["wrapper"] = test_translation_wrapper()
    else:
        logger.warning("Skipping translation wrapper test - mock API not working")
        results["wrapper"] = False

    # Test 3: Streaming
    if results["wrapper"]:
        results["streaming"] = test_translation_wrapper_streaming()
    else:
        logger.warning("Skipping streaming test - wrapper not working")
        results["streaming"] = False

    # Test 4: OpenCode Integration
    if results["wrapper"]:
        results["opencode"] = test_opencode_integration()
    else:
        logger.warning("Skipping OpenCode test - wrapper not working")
        results["opencode"] = None

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✓ PASSED"
        elif result is False:
            status = "✗ FAILED"
        else:
            status = "⚠ SKIPPED"
        logger.info(f"{test_name:20s}: {status}")

    # Overall result
    if all(r is True or r is None for r in results.values()):
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.info("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
