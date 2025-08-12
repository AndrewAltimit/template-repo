#!/usr/bin/env python3
"""Simple test to verify Blender MCP server is working."""

import json

import httpx


def test_server():
    """Test basic server functionality."""
    base_url = "http://localhost:8017"

    # Test 1: List projects
    print("1. Testing list_projects...")
    response = httpx.post(
        f"{base_url}/mcp/execute",
        json={"tool": "list_projects", "arguments": {}},
        timeout=10.0,
    )
    result = response.json()
    print(f"   Response: {json.dumps(result, indent=2)}")

    # Test 2: Create a project
    print("\n2. Testing create_blender_project...")
    response = httpx.post(
        f"{base_url}/mcp/execute",
        json={
            "tool": "create_blender_project",
            "arguments": {"name": "test_from_script", "template": "studio_lighting"},
        },
        timeout=10.0,
    )
    result = response.json()
    print(f"   Response: {json.dumps(result, indent=2)}")

    if result.get("success"):
        job_id = result["result"]["job_id"]

        # Test 3: Check job status
        print(f"\n3. Testing get_job_status for job {job_id}...")
        import time

        time.sleep(3)  # Wait for job to complete

        response = httpx.post(
            f"{base_url}/mcp/execute",
            json={"tool": "get_job_status", "arguments": {"job_id": job_id}},
            timeout=10.0,
        )
        result = response.json()
        print(f"   Response: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    test_server()
