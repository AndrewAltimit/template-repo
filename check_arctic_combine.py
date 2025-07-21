import json

import requests

# Test arctic terrain template
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {"template_name": "arctic_terrain", "project_name": "test_arctic_final"},
    },
)

data = response.json()
if "project_structure" in data:
    with open("test_arctic_final.json", "w") as f:
        json.dump(data["project_structure"], f, indent=2)
    print("✓ Saved arctic terrain to test_arctic_final.json")

    # Check if it has a Combine node
    project = data["project_structure"]
    nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]
    for node_id, node in nodes.items():
        if node_id != "$id" and "Combine" in node.get("$type", ""):
            print(f'\nFound Combine node: {node["Name"]} (ID: {node["Id"]})')
            # Check connections
            ports = node.get("Ports", {}).get("$values", [])
            for port in ports:
                if port.get("Record"):
                    print(f'  - Port {port["Name"]} connected from node {port["Record"]["From"]}')
