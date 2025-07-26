#!/usr/bin/env python3
"""Test registration endpoint for Gaea2 MCP Server"""

import asyncio
import json
import sys

import httpx


async def test_registration(base_url: str = "http://192.168.0.152:8007"):
    """Test the registration endpoint"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Testing registration endpoint at {base_url}")

        # Test 1: Basic registration
        print("\n1. Testing basic registration...")
        try:
            response = await client.post(
                f"{base_url}/mcp/register", json={"client": "test-client-001", "name": "Test Client", "version": "1.0.0"}
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 2: Registration with minimal data
        print("\n2. Testing minimal registration...")
        try:
            response = await client.post(f"{base_url}/mcp/register", json={"client": "minimal-client"})
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 3: Registration with no data
        print("\n3. Testing empty registration...")
        try:
            response = await client.post(f"{base_url}/mcp/register", json={})
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

        # Test 4: Check if endpoint exists
        print("\n4. Checking available endpoints...")
        try:
            # Try the health check first
            health_response = await client.get(f"{base_url}/health")
            print(f"Health check: {health_response.status_code}")

            # Check OpenAPI docs if available
            try:
                docs_response = await client.get(f"{base_url}/docs")
                print(f"API docs available: {docs_response.status_code == 200}")
            except Exception:
                print("API docs not available")

        except Exception as e:
            print(f"Server might not be running: {e}")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.0.152:8007"
    asyncio.run(test_registration(base_url))
