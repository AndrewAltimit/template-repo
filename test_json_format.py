#!/usr/bin/env python3
"""Test JSON formatting for Gaea2 files."""

import json

# Test data with booleans
test_data = {
    "IsExporting": True,
    "IsValid": False,
    "TileZeroIndex": True,
    "Shadows": True,
    "AmbientOcclusion": True,
}

# Standard JSON
print("Standard JSON:")
print(json.dumps(test_data, separators=(",", ":")))
print()

# Pretty JSON
print("Pretty JSON:")
print(json.dumps(test_data, indent=2))
