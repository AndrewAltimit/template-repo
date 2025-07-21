#!/usr/bin/env python3
"""Test that templates work with the new property limitation fix"""

import json

import requests

print("Testing templates with new property limitation fix...\n")

# Test the previously failing templates with smart mode
failing_templates = [
    "arctic_terrain",
    "mountain_range",
    "detailed_mountain",
    "coastal_cliffs",
    "canyon_system",
    "volcanic_island",
]

results = []

for template_name in failing_templates:
    print(f"Testing {template_name} template with smart mode...")

    response = requests.post(
        "http://192.168.0.152:8007/mcp/execute",
        json={
            "tool": "create_gaea2_from_template",
            "parameters": {"template_name": template_name, "project_name": f"test_fixed_{template_name}"},
        },
    )

    if response.status_code == 200:
        data = response.json()
        if "project_structure" in data:
            # Check Snow nodes in the result
            nodes = data["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]
            snow_found = False

            for node_id, node in nodes.items():
                if node_id != "$id" and "Snow" in str(node.get("$type", "")):
                    snow_found = True
                    properties = [
                        k
                        for k in node.keys()
                        if k
                        not in [
                            "$id",
                            "$type",
                            "Id",
                            "Name",
                            "Position",
                            "Ports",
                            "Modifiers",
                            "SaveDefinition",
                            "NodeSize",
                            "PortCount",
                            "IsMaskable",
                        ]
                    ]
                    print(f"  Snow node found with {len(properties)} properties: {', '.join(properties[:5])}")

            # Save the file
            filename = f"test_fixed_{template_name}.terrain"
            with open(filename, "w") as f:
                json.dump(data["project_structure"], f, separators=(",", ":"))

            print(f"  ✓ Created {filename}")
            results.append((template_name, True, snow_found))
        else:
            print(f"  ✗ Error: {data.get('error', 'Unknown error')}")
            results.append((template_name, False, False))
    else:
        print(f"  ✗ HTTP Error: {response.status_code}")
        results.append((template_name, False, False))

print("\n\nSummary:")
print("Templates that should now work:")
for template, success, has_snow in results:
    status = "✓" if success else "✗"
    snow_status = "(has Snow)" if has_snow else ""
    print(f"  {status} {template} {snow_status}")

print("\nAll templates with problematic nodes should now limit properties to max 3.")
