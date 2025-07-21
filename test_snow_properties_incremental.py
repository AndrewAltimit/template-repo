#!/usr/bin/env python3
"""Test Snow node by adding properties incrementally to find the problematic one"""

import json

import requests

print("Testing Snow node properties incrementally...\n")

base_config = {
    "project_name": "test_snow_prop",
    "property_mode": "minimal",
    "nodes": [
        {"id": 1, "type": "Mountain", "name": "BaseTerrain", "position": {"x": 25000, "y": 26000}},
        {
            "id": 2,
            "type": "Snow",
            "name": "SnowLayer",
            "position": {"x": 25500, "y": 26000},
            "properties": {},  # Will add incrementally
        },
    ],
    "connections": [{"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}],
}

# Test different property combinations
test_cases = [
    ("duration_only", {"Duration": 0.5}),
    ("snowline_only", {"SnowLine": 0.7}),
    ("duration_snowline", {"Duration": 0.5, "SnowLine": 0.7}),
    ("with_melt", {"Duration": 0.5, "SnowLine": 0.7, "Melt": 0.0}),
    ("with_melttype", {"Duration": 0.5, "SnowLine": 0.7, "MeltType": "Uniform"}),
    ("with_realscale", {"Duration": 0.5, "SnowLine": 0.7, "RealScale": False}),
    (
        "no_booleans",
        {
            "Duration": 0.5,
            "SnowLine": 0.7,
            "Intensity": 0.5,
            "SettleDuration": 0.5,
            "Melt": 0.0,
            "MeltRemnants": 0.0,
            "Direction": 0.0,
            "SlipOffAngle": 35.0
            # Excluding: MeltType (string), RealScale (boolean)
        },
    ),
    (
        "no_realscale",
        {
            "Duration": 0.5,
            "SnowLine": 0.7,
            "Intensity": 0.5,
            "SettleDuration": 0.5,
            "MeltType": "Uniform",
            "Melt": 0.0,
            "MeltRemnants": 0.0,
            "Direction": 0.0,
            "SlipOffAngle": 35.0
            # Excluding: RealScale
        },
    ),
]

successful_tests = []
failed_tests = []

for test_name, properties in test_cases:
    print(f"Testing: {test_name}")
    print(f"  Properties: {list(properties.keys())}")

    config = base_config.copy()
    config["project_name"] = f"test_snow_{test_name}"
    config["nodes"][1]["properties"] = properties

    response = requests.post(
        "http://192.168.0.152:8007/mcp/execute", json={"tool": "create_gaea2_project", "parameters": config}
    )

    if response.status_code == 200:
        data = response.json()
        if "project_structure" in data:
            filename = f"test_snow_{test_name}.terrain"
            with open(filename, "w") as f:
                json.dump(data["project_structure"], f, separators=(",", ":"))
            print(f"  ✓ Created {filename}")
            successful_tests.append((test_name, properties))
        else:
            print(f"  ✗ Error: {data.get('error', 'Unknown')}")
            failed_tests.append((test_name, properties))
    else:
        print(f"  ✗ HTTP Error: {response.status_code}")
        failed_tests.append((test_name, properties))

print("\n\nSummary:")
print(f"Successful: {len(successful_tests)}")
print(f"Failed: {len(failed_tests)}")

print("\nPlease test these files in Gaea2 to find which property causes the issue:")
for test_name, _ in successful_tests:
    print(f"- test_snow_{test_name}.terrain")

print("\nThe difference between working and failing tests will reveal the problematic property.")
