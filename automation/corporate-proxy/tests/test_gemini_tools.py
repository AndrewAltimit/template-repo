#!/usr/bin/env python3
"""
Test script for Gemini CLI tool support
Tests all 6 Gemini-specific tools with proper response format validation
"""

import os
import sys
import tempfile
import time

import requests

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_status(status, message):
    """Print colored status message"""
    if status == "pass":
        print(f"{GREEN}✓{RESET} {message}")
    elif status == "fail":
        print(f"{RED}✗{RESET} {message}")
    elif status == "info":
        print(f"{BLUE}ℹ{RESET} {message}")
    elif status == "warn":
        print(f"{YELLOW}⚠{RESET} {message}")


def wait_for_service(url, timeout=30):
    """Wait for service to be ready"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False


def validate_gemini_response(response_data):
    """Validate response matches Gemini format requirements"""
    errors = []

    # Check top-level fields
    if "candidates" not in response_data:
        errors.append("Missing 'candidates' field")
    elif not isinstance(response_data["candidates"], list):
        errors.append("'candidates' must be an array")
    elif len(response_data["candidates"]) > 0:
        candidate = response_data["candidates"][0]

        # Check candidate structure
        if "content" not in candidate:
            errors.append("Missing 'content' in candidate")
        else:
            content = candidate["content"]
            if "parts" not in content:
                errors.append("Missing 'parts' in content")
            if "role" not in content:
                errors.append("Missing 'role' in content")
            elif content["role"] != "model":
                errors.append(f"Role must be 'model', got '{content['role']}'")

        if "finishReason" not in candidate:
            errors.append("Missing 'finishReason' in candidate")
        if "index" not in candidate:
            errors.append("Missing 'index' in candidate")

    if "promptFeedback" not in response_data:
        errors.append("Missing 'promptFeedback' field")

    if "usageMetadata" not in response_data:
        errors.append("Missing 'usageMetadata' field")
    elif isinstance(response_data["usageMetadata"], dict):
        metadata = response_data["usageMetadata"]
        for field in ["promptTokenCount", "candidatesTokenCount", "totalTokenCount"]:
            if field not in metadata:
                errors.append(f"Missing '{field}' in usageMetadata")

    return errors


def execute_tool_test(proxy_url, tool_name, parameters, expected_fields):
    """Execute a tool test and return result (helper function, not a pytest test)."""
    # Direct tool execution endpoint
    execute_url = f"{proxy_url}/execute"

    try:
        response = requests.post(execute_url, json={"tool": tool_name, "parameters": parameters}, timeout=10)

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text}"

        result = response.json()

        # Check expected fields in result
        for field in expected_fields:
            if field not in result:
                return False, f"Missing expected field '{field}' in result"

        # Check success field
        if "success" in result and not result["success"]:
            return False, f"Tool returned success=false: {result.get('error', 'unknown error')}"

        return True, result

    except Exception as e:
        return False, str(e)


def generate_content_with_tools_test(proxy_url):
    """Test generateContent endpoint with tools (helper function, not a pytest test)."""
    generate_url = f"{proxy_url}/v1/models/gemini-2.5-flash/generateContent"

    # Test request with tool declarations
    request_data = {
        "contents": [{"parts": [{"text": "Read the README.md file"}], "role": "user"}],
        "tools": [
            {
                "functionDeclarations": [
                    {
                        "name": "read_file",
                        "description": "Read contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string", "description": "Path to the file"}},
                            "required": ["path"],
                        },
                    }
                ]
            }
        ],
    }

    try:
        response = requests.post(generate_url, json=request_data, timeout=10)

        if response.status_code != 200:
            return False, f"HTTP {response.status_code}: {response.text}"

        result = response.json()

        # Validate Gemini response format
        errors = validate_gemini_response(result)
        if errors:
            return False, f"Response format errors: {', '.join(errors)}"

        return True, result

    except Exception as e:
        return False, str(e)


def _test_health_check(proxy_url):
    """Test 1: Health check."""
    try:
        response = requests.get(f"{proxy_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("tools_enabled") is True:
                print_status("pass", "Health check passed with tools enabled")
                return True
            print_status("fail", "Tools not enabled in proxy")
        else:
            print_status("fail", f"Health check failed: HTTP {response.status_code}")
    except Exception as e:
        print_status("fail", f"Health check error: {e}")
    return False


def _test_list_tools(proxy_url):
    """Test 2: List available tools."""
    try:
        response = requests.get(f"{proxy_url}/tools", timeout=10)
        if response.status_code == 200:
            data = response.json()
            tools = data.get("tools", [])
            expected_tools = ["read_file", "write_file", "run_command", "list_directory", "search_files", "web_search"]
            missing = [t for t in expected_tools if t not in tools]
            if not missing:
                print_status("pass", f"All {len(expected_tools)} tools available")
                for tool in tools:
                    print(f"    - {tool}")
                return True
            print_status("fail", f"Missing tools: {missing}")
        else:
            print_status("fail", f"List tools failed: HTTP {response.status_code}")
    except Exception as e:
        print_status("fail", f"List tools error: {e}")
    return False


def _test_read_file(proxy_url):
    """Test 3: read_file tool."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Test content for Gemini")
        test_file = f.name

    success, result = execute_tool_test(proxy_url, "read_file", {"path": test_file}, ["success", "content"])
    os.unlink(test_file)

    if success and result.get("content") == "Test content for Gemini":
        print_status("pass", "read_file tool works correctly")
        return True
    print_status("fail", f"read_file failed: {result}")
    return False


def _test_write_file(proxy_url):
    """Test 4: write_file tool."""
    # Create a named temporary file path (file is created then closed for write_file to use)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        test_file = tmp.name
    # Remove the file so write_file can create it
    os.unlink(test_file)
    success, result = execute_tool_test(
        proxy_url, "write_file", {"path": test_file, "content": "Gemini test write"}, ["success"]
    )

    if success and os.path.exists(test_file):
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        os.unlink(test_file)
        if content == "Gemini test write":
            print_status("pass", "write_file tool works correctly")
            return True
        print_status("fail", f"File content mismatch: {content}")
    else:
        print_status("fail", f"write_file failed: {result}")
    return False


def _test_run_command(proxy_url):
    """Test 5: run_command tool."""
    success, result = execute_tool_test(
        proxy_url, "run_command", {"command": "echo 'Gemini test'"}, ["success", "stdout", "exit_code"]
    )
    if success and result.get("stdout", "").strip() == "Gemini test":
        print_status("pass", "run_command tool works correctly")
        return True
    print_status("fail", f"run_command failed: {result}")
    return False


def _test_list_directory(proxy_url):
    """Test 6: list_directory tool."""
    success, result = execute_tool_test(proxy_url, "list_directory", {"path": "/tmp"}, ["success", "files", "directories"])
    if success:
        print_status("pass", f"list_directory found {result.get('total', 0)} items")
        return True
    print_status("fail", f"list_directory failed: {result}")
    return False


def _test_search_files(proxy_url):
    """Test 7: search_files tool."""
    success, result = execute_tool_test(
        proxy_url, "search_files", {"pattern": "*.txt", "path": "/tmp"}, ["success", "matches", "count"]
    )
    if success:
        print_status("pass", f"search_files found {result.get('count', 0)} matches")
        return True
    print_status("fail", f"search_files failed: {result}")
    return False


def _test_web_search(proxy_url):
    """Test 8: web_search tool (mock)."""
    success, result = execute_tool_test(proxy_url, "web_search", {"query": "Gemini API documentation"}, ["success", "results"])
    if success:
        results = result.get("results", [])
        if results:
            print_status("pass", f"web_search returned {len(results)} results")
            return True
        print_status("fail", "No search results returned")
    else:
        print_status("fail", f"web_search failed: {result}")
    return False


def _test_response_format(proxy_url):
    """Test 9: Response format validation."""
    success, result = generate_content_with_tools_test(proxy_url)
    if success:
        print_status("pass", "Response format is valid for Gemini CLI")
        print("    Response structure:")
        print(f"    - candidates: {len(result.get('candidates', []))}")
        print(f"    - role: {result.get('candidates', [{}])[0].get('content', {}).get('role')}")
        print(f"    - parts: {len(result.get('candidates', [{}])[0].get('content', {}).get('parts', []))}")
        print(f"    - tokens: {result.get('usageMetadata', {}).get('totalTokenCount', 0)}")
        return True
    print_status("fail", f"Response format validation failed: {result}")
    return False


def main():
    """Run all Gemini tool tests"""
    proxy_port = os.environ.get("GEMINI_PROXY_PORT", "8053")
    proxy_url = f"http://localhost:{proxy_port}"

    print_status("info", f"Testing Gemini proxy at {proxy_url}")
    print_status("info", "Waiting for proxy service...")

    if not wait_for_service(f"{proxy_url}/health"):
        print_status("fail", "Proxy service not available")
        return 1

    print_status("pass", "Proxy service is ready")
    print()

    tests = [
        ("Test 1: Health Check", _test_health_check),
        ("Test 2: List Available Tools", _test_list_tools),
        ("Test 3: read_file Tool", _test_read_file),
        ("Test 4: write_file Tool", _test_write_file),
        ("Test 5: run_command Tool", _test_run_command),
        ("Test 6: list_directory Tool", _test_list_directory),
        ("Test 7: search_files Tool", _test_search_files),
        ("Test 8: web_search Tool (Mock)", _test_web_search),
        ("Test 9: Gemini Response Format Validation", _test_response_format),
    ]

    passed_tests = 0
    for test_name, test_func in tests:
        print_status("info", test_name)
        if test_func(proxy_url):
            passed_tests += 1
        print()

    print("=" * 60)
    print(f"Test Summary: {passed_tests}/{len(tests)} tests passed")

    if passed_tests == len(tests):
        print_status("pass", "All Gemini tool tests passed!")
        return 0
    print_status("fail", f"{len(tests) - passed_tests} tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
