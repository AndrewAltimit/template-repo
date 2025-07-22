import json

import requests

# Test with arctic terrain (has Export and SatMap nodes)
response = requests.post(
    "http://192.168.0.152:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "arctic_terrain",
            "project_name": "test_final_fix",
        },
    },
)

if response.status_code == 200:
    data = response.json()
    if "project_structure" in data:
        with open("test_final_fix.json", "w") as f:
            json.dump(data["project_structure"], f, indent=2)
        print("✓ Generated test_final_fix.json")

        # Verify SatMap and Export nodes have correct port ordering
        project = data["project_structure"]
        nodes = project["Assets"]["$values"][0]["Terrain"]["Nodes"]

        issues_found = False

        for node_id, node in nodes.items():
            if node_id != "$id" and ("SatMap" in node.get("$type", "") or "Export" in node.get("$type", "")):
                node_type = "SatMap" if "SatMap" in node["$type"] else "Export"
                print(f'\nChecking {node_type} node: {node["Name"]}')

                # Check In port with Record
                ports = node["Ports"]["$values"]
                for port in ports:
                    if port["Name"] == "In" and "Record" in port:
                        keys = list(port.keys())
                        print(f"  Port keys: {keys}")

                        # Verify order
                        try:
                            type_idx = keys.index("Type")
                            record_idx = keys.index("Record")
                            export_idx = keys.index("IsExporting")
                            parent_idx = keys.index("Parent")

                            if record_idx > type_idx and record_idx < export_idx and record_idx < parent_idx:
                                print(f"  ✓ Record position is correct (after Type, before IsExporting/Parent)")
                            else:
                                print(f"  ✗ Record position is WRONG!")
                                print(
                                    f"    Positions: Type={type_idx}, Record={record_idx}, IsExporting={export_idx}, Parent={parent_idx}"
                                )
                                issues_found = True
                        except ValueError as e:
                            print(f"  ✗ Missing key: {e}")
                            issues_found = True
                        break

        # Also check a Combine node
        for node_id, node in nodes.items():
            if node_id != "$id" and "Combine" in node.get("$type", ""):
                print(f'\nChecking Combine node: {node["Name"]}')
                ports = node["Ports"]["$values"]
                port_names = [p["Name"] for p in ports]
                print(f"  Port order: {port_names}")
                if port_names == ["In", "Out", "Input2", "Mask"]:
                    print("  ✓ Port order is correct")
                else:
                    print("  ✗ Port order is WRONG!")
                    issues_found = True
                break

        if not issues_found:
            print("\n✅ All nodes have correct formatting!")
        else:
            print("\n❌ Issues found with formatting")
else:
    print(f"✗ HTTP Error: {response.status_code}")
