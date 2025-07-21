import json

import requests

# Create EXACTLY like the working file - single Mountain node, no Export
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_truly_minimal",
            "nodes": [
                {
                    "id": 1,  # Use ID 1 like working file
                    "type": "Mountain",
                    "name": "Mountain",
                    "position": {"x": 24000, "y": 26000},
                    "properties": {},  # No properties
                }
            ],
            "connections": [],  # No connections
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        # Save exactly like working file
        with open("test_truly_minimal.json", "w") as f:
            json.dump(data["project_structure"], f, separators=(",", ":"))

        print("✓ Generated truly minimal project")

        # Check structure
        project = data["project_structure"]
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

        print(f"\nNode keys in Nodes dict: {list(nodes.keys())}")

        if "1" in nodes:
            mountain = nodes["1"]
            print(f"\nMountain node structure:")
            print(f"  Keys: {list(mountain.keys())}")

            # Check for unwanted fields
            unwanted = ["NodeSize", "IsMaskable", "PortCount", "SaveDefinition"]
            for field in unwanted:
                if field in mountain:
                    print(f"  ❌ Has {field}: {mountain[field]}")

            # Check port types
            ports = mountain.get("Ports", {}).get("$values", [])
            for port in ports:
                if port["Name"] == "In":
                    print(f'\n  In port Type: "{port["Type"]}"')
                    if ", Required" in port["Type"]:
                        print("  ❌ Has Required suffix")
                    else:
                        print("  ✓ No Required suffix")

        # Compare sizes
        working_size = 2253  # From previous analysis
        generated_size = len(json.dumps(data["project_structure"], separators=(",", ":")))
        print(f"\nFile sizes:")
        print(f"  Working: {working_size} chars")
        print(f"  Generated: {generated_size} chars")

        if generated_size > working_size * 1.2:
            print("  ❌ Generated file is much larger")
else:
    print(f"Error: {response.status_code}")
