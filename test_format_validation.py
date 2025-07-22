import json

import requests

# Test with basic terrain template
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "basic_terrain",
            "project_name": "test_format_fixed",
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        with open("test_format_fixed.json", "w") as f:
            json.dump(data["project_structure"], f, indent=2)
        print("✓ Saved project to test_format_fixed.json")

        # Quick validation of key format fixes
        project = data["project_structure"]
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

        # Check a node with ports
        for node_id, node in nodes.items():
            if node_id != "$id" and "Ports" in node:
                ports = node["Ports"]["$values"]
                if ports and ports[0].get("Record"):
                    port = ports[0]
                    keys = list(port.keys())
                    print(f"\nPort key order: {keys}")
                    # Check if Record comes before IsExporting
                    if "Record" in keys and "IsExporting" in keys:
                        record_idx = keys.index("Record")
                        export_idx = keys.index("IsExporting")
                        if record_idx < export_idx:
                            print("✓ Record comes before IsExporting")
                        else:
                            print("✗ Record does NOT come before IsExporting")
                    break

        # Check if Export node has Required suffix
        for node_id, node in nodes.items():
            if node_id != "$id" and "Export" in node.get("$type", ""):
                ports = node["Ports"]["$values"]
                if ports:
                    in_port = next((p for p in ports if p["Name"] == "In"), None)
                    if in_port:
                        print(f'\nExport node In port type: "{in_port["Type"]}"')
                        if ", Required" in in_port["Type"]:
                            print("✓ Has Required suffix")
                        else:
                            print("✗ Missing Required suffix")
                break

        # Check if SatMap has Required suffix
        for node_id, node in nodes.items():
            if node_id != "$id" and "SatMap" in node.get("$type", ""):
                ports = node["Ports"]["$values"]
                if ports:
                    in_port = next((p for p in ports if p["Name"] == "In"), None)
                    if in_port:
                        print(f'\nSatMap node In port type: "{in_port["Type"]}"')
                        if ", Required" in in_port["Type"]:
                            print("✓ Has Required suffix")
                        else:
                            print("✗ Missing Required suffix")
                break

        # Check Range object has $id
        for node_id, node in nodes.items():
            if node_id != "$id" and isinstance(node.get("Range"), dict):
                range_obj = node["Range"]
                print(f"\nRange object: {range_obj}")
                if "$id" in range_obj:
                    print("✓ Range has $id")
                else:
                    print("✗ Range missing $id")
                break

    else:
        print(f"✗ No project_structure in response")
else:
    print(f"✗ HTTP Error: {response.status_code}")
