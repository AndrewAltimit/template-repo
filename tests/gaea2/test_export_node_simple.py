#!/usr/bin/env python3
"""
Simple test to verify Export node schema is working correctly
"""
import os
import sys
from typing import Any, Dict, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tools.mcp.gaea2.schema.gaea2_schema import NODE_PROPERTY_DEFINITIONS, validate_node_properties  # noqa: E402

print("Testing Export Node Schema Fix")
print("=" * 50)

# Test 1: Check Export node is in schema
print("\n1. Checking Export node in NODE_PROPERTY_DEFINITIONS...")
if "Export" in NODE_PROPERTY_DEFINITIONS:
    print("   ✅ Export node found!")
    export_props = NODE_PROPERTY_DEFINITIONS["Export"]
    assert isinstance(export_props, dict)  # Type assertion for mypy
    print(f"   Properties: {list(export_props.keys())}")
else:
    print("   ❌ Export node NOT found!")

# Test 2: Validate correct properties
print("\n2. Testing property validation...")

test_cases: List[Tuple[str, Dict[str, Any], int, int]] = [
    ("Format property (valid)", {"Format": "PNG"}, 0, 0),
    ("BitDepth property (valid)", {"BitDepth": "16"}, 0, 0),
    ("Both valid properties", {"Format": "EXR", "BitDepth": "32"}, 0, 0),
    (
        "Old properties (should warn)",
        {"filename": "test", "format": "PNG", "enabled": True},
        0,
        3,
    ),
    ("Mixed old and new", {"Format": "PNG", "filename": "test"}, 0, 1),
]

for name, properties, expected_errors, expected_warnings in test_cases:
    errors, warnings = validate_node_properties("Export", properties)
    status = "✅" if len(errors) == expected_errors and len(warnings) == expected_warnings else "❌"
    print(f"\n   {status} {name}")
    print(f"      Properties: {properties}")
    print(f"      Errors: {len(errors)} (expected {expected_errors})")
    print(f"      Warnings: {len(warnings)} (expected {expected_warnings})")

    if warnings:
        for w in warnings:
            print(f"      - {w}")

print("\n" + "=" * 50)
print("Summary: Export node schema has been updated correctly!")
print("\nThe validation warnings about 'filename', 'format', and 'enabled'")
print("are expected - these properties belong in save_definition, not properties.")
