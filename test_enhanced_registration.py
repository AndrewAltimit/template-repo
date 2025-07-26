#!/usr/bin/env python3
"""Test enhanced dynamic registration for Gaea2 MCP Server"""

import asyncio
import json
import sys

import httpx


async def test_enhanced_registration(base_url: str = "http://192.168.0.152:8007"):
    """Test the enhanced registration features"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Testing enhanced registration at {base_url}")
        print("=" * 60)

        # Test 1: Register a client with full metadata
        print("\n1. Registering client with full metadata...")
        try:
            response = await client.post(
                f"{base_url}/mcp/register",
                json={
                    "client": "terrain-builder-v2",
                    "name": "Terrain Builder Application",
                    "version": "2.1.0",
                    "capabilities": [
                        "create_terrain",
                        "validate_workflow",
                        "export_heightmap",
                    ],
                    "description": "Advanced terrain generation client",
                    "contact": "admin@terraincorp.com",
                },
            )
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")

            # Save client_id for later use
            client1_id = result.get("registration", {}).get("client_id", "")

        except Exception as e:
            print(f"Error: {e}")
            return

        # Test 2: Register another client
        print("\n2. Registering second client...")
        try:
            response = await client.post(
                f"{base_url}/mcp/register",
                json={
                    "client": "terrain-analyzer",
                    "name": "Terrain Analysis Tool",
                    "version": "1.0.0",
                    "capabilities": ["analyze_workflow", "suggest_nodes"],
                },
            )
            result = response.json()
            print(f"Client 2 registered: {result['registration']['client_id']}")

        except Exception as e:
            print(f"Error: {e}")

        # Test 3: Update existing client (re-register)
        print("\n3. Re-registering first client (update)...")
        try:
            response = await client.post(
                f"{base_url}/mcp/register",
                json={
                    "client": "terrain-builder-v2",
                    "client_id": client1_id,  # Use same client_id to update
                    "version": "2.1.1",  # Updated version
                    "capabilities": [
                        "create_terrain",
                        "validate_workflow",
                        "export_heightmap",
                        "batch_process",
                    ],
                },
            )
            result = response.json()
            print(f"Is update: {result['registration']['is_update']}")
            print(f"Client ID: {result['registration']['client_id']}")

        except Exception as e:
            print(f"Error: {e}")

        # Test 4: List all clients
        print("\n4. Listing all registered clients...")
        try:
            response = await client.get(f"{base_url}/mcp/clients")
            result = response.json()
            print(f"Total clients: {result['count']}")
            for client_info in result["clients"]:
                print(f"  - {client_info['client_name']} ({client_info['client_id']})")
                print(f"    Version: {client_info.get('metadata', {}).get('version', 'N/A')}")
                print(f"    Last seen: {client_info.get('last_seen', 'Never')}")

        except Exception as e:
            print(f"Error: {e}")

        # Test 5: Get specific client info
        print(f"\n5. Getting info for client: {client1_id}...")
        try:
            response = await client.get(f"{base_url}/mcp/clients/{client1_id}")
            result = response.json()
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"Error: {e}")

        # Test 6: Execute tool with client tracking
        print("\n6. Executing tool with client tracking...")
        try:
            response = await client.post(
                f"{base_url}/mcp/execute",
                json={
                    "tool": "suggest_gaea2_nodes",
                    "client_id": client1_id,  # Include client_id for tracking
                    "arguments": {
                        "current_nodes": ["Mountain", "Erosion2"],
                        "context": "Adding detail",
                    },
                },
            )
            result = response.json()
            print(f"Tool execution success: {result['success']}")

        except Exception as e:
            print(f"Error: {e}")

        # Test 7: Get server statistics
        print("\n7. Getting server statistics...")
        try:
            response = await client.get(f"{base_url}/mcp/stats")
            result = response.json()
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"Error: {e}")

        # Test 8: List clients with activity
        print("\n8. Checking client activity after tool execution...")
        try:
            response = await client.get(f"{base_url}/mcp/clients/{client1_id}")
            result = response.json()
            print(f"Client request count: {result.get('request_count', 0)}")
            print(f"Last activity: {result.get('last_seen', 'Never')}")

        except Exception as e:
            print(f"Error: {e}")

        print("\n" + "=" * 60)
        print("Enhanced registration tests completed!")
        print("\nNOTE: The registration data is persisted in /tmp/mcp_clients.json")
        print("      Clients will be remembered across server restarts.")


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.0.152:8007"
    asyncio.run(test_enhanced_registration(base_url))
