import json

import requests

# Create a minimal project with NO properties on Mountain node
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_minimal",
            "nodes": [
                {
                    "id": 1,
                    "type": "Mountain",
                    "name": "Mountain",
                    "position": {"x": 24000, "y": 26000},
                    "properties": {},  # Empty properties!
                }
            ],
            "connections": [],
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        # Save and analyze
        with open("test_minimal.json", "w") as f:
            json.dump(data["project_structure"], f, indent=2)

        print("✓ Generated minimal project")

        # Check Mountain node structure
        project = data["project_structure"]
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
        mountain = nodes.get("1") or nodes.get("50")  # Might have different ID

        if mountain:
            print(f"\nMountain node keys: {list(mountain.keys())}")

            # Count properties (excluding system fields)
            exclude_fields = [
                "$id",
                "$type",
                "Id",
                "Name",
                "Position",
                "Ports",
                "Modifiers",
                "NodeSize",
                "IsMaskable",
                "PortCount",
            ]
            props = {k: v for k, v in mountain.items() if k not in exclude_fields}
            print(f"Properties: {props}")
            print(f"Property count: {len(props)}")
        else:
            print("Mountain node not found!")
else:
    print(f"Error: {response.status_code}")
