#!/usr/bin/env python3
"""Generate regression test files from templates"""

import json

import requests

print("Generating regression test files from templates...\n")

# Template names that should correspond to the regression files
templates = [
    "volcanic_terrain",
    "river_valley",
    "desert_canyon",
    "basic_terrain",
    "volcanic_island",
    "mountain_range",
    "detailed_mountain",
    "coastal_cliffs",
    "canyon_system",
    "arctic_terrain",
]

generated_files = []

for template_name in templates:
    print(f"Generating regression_{template_name}...")

    response = requests.post(
        "http://192.168.0.152:8007/mcp/execute",
        json={
            "tool": "create_gaea2_from_template",
            "parameters": {"template_name": template_name, "project_name": f"regression_{template_name}"},
        },
    )

    if response.status_code == 200:
        data = response.json()
        if "project_structure" in data:
            # Save the file locally for analysis
            filename = f"regression_{template_name}.json"
            with open(filename, "w") as f:
                json.dump(data["project_structure"], f, indent=2)
            print(f"  ✓ Saved as {filename}")
            generated_files.append(filename)
        else:
            print(f"  ✗ Error: {data.get('error', 'Unknown error')}")
    else:
        print(f"  ✗ HTTP {response.status_code}: {response.text}")

print(f"\nGenerated {len(generated_files)} files for analysis")
