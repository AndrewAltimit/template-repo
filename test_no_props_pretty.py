import json

import requests

# Create arctic terrain but with NO properties
nodes = [
    {
        "id": 100,
        "type": "Mountain",
        "name": "ArcticMountains",
        "position": {"x": 25000, "y": 26000},
        "properties": {},
    },
    {
        "id": 101,
        "type": "Glacier",
        "name": "IceFlow",
        "position": {"x": 25500, "y": 26000},
        "properties": {},
    },
    {
        "id": 102,
        "type": "Combine",
        "name": "GlacialCarving",
        "position": {"x": 26000, "y": 26000},
        "properties": {},
    },
    {
        "id": 103,
        "type": "Snow",
        "name": "SnowCover",
        "position": {"x": 26500, "y": 26000},
        "properties": {},
    },
    {
        "id": 104,
        "type": "Thermal",
        "name": "FrostShatter",
        "position": {"x": 27000, "y": 26000},
        "properties": {},
    },
    {
        "id": 105,
        "type": "Lakes",
        "name": "GlacialLakes",
        "position": {"x": 27500, "y": 26000},
        "properties": {},
    },
    {
        "id": 106,
        "type": "SatMap",
        "name": "ArcticColors",
        "position": {"x": 28000, "y": 26000},
        "properties": {},
    },
    {
        "id": 107,
        "type": "Export",
        "name": "TerrainExport",
        "position": {"x": 28500, "y": 26000},
        "properties": {},
    },
]

connections = [
    {"from_node": 100, "to_node": 101, "from_port": "Out", "to_port": "In"},
    {"from_node": 100, "to_node": 102, "from_port": "Out", "to_port": "In"},
    {"from_node": 101, "to_node": 102, "from_port": "Out", "to_port": "Input2"},
    {"from_node": 102, "to_node": 103, "from_port": "Out", "to_port": "In"},
    {"from_node": 103, "to_node": 104, "from_port": "Out", "to_port": "In"},
    {"from_node": 104, "to_node": 105, "from_port": "Out", "to_port": "In"},
    {"from_node": 105, "to_node": 106, "from_port": "Out", "to_port": "In"},
    {"from_node": 106, "to_node": 107, "from_port": "Out", "to_port": "In"},
]

response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_no_props_arctic",
            "nodes": nodes,
            "connections": connections,
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        # Save with pretty formatting for easy reading
        with open("test_no_props_arctic.json", "w") as f:
            json.dump(data["project_structure"], f, indent=2)

        # Also save minified version
        with open("test_no_props_arctic_min.json", "w") as f:
            json.dump(data["project_structure"], f, separators=(",", ":"))

        print("✓ Generated project files:")
        print("  - test_no_props_arctic.json (pretty printed)")
        print("  - test_no_props_arctic_min.json (minified)")
        print("\nPlease test if these files open in Gaea2!")
else:
    print(f"Error: {response.status_code}")
