#!/usr/bin/env python3
"""
Test Gaea2 schema and validation logic locally without MCP server
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json  # noqa: E402

from tools.mcp.gaea2.errors.gaea2_error_recovery import Gaea2ErrorRecovery  # noqa: E402
from tools.mcp.gaea2.schema.gaea2_schema import NODE_PROPERTY_DEFINITIONS, validate_node_properties  # noqa: E402
from tools.mcp.gaea2.validation.gaea2_validation import create_validator  # noqa: E402


def test_export_node_schema():
    """Test that Export node schema is properly defined"""
    print("Testing Export node schema...")

    # Check if Export is in NODE_PROPERTY_DEFINITIONS
    if "Export" in NODE_PROPERTY_DEFINITIONS:
        print("✅ Export node found in NODE_PROPERTY_DEFINITIONS")
        export_props = NODE_PROPERTY_DEFINITIONS["Export"]
        print(f"   Properties defined: {list(export_props.keys())}")

        # Validate expected properties
        expected_props = ["Format", "BitDepth"]
        for prop in expected_props:
            if prop in export_props:
                print(f"   ✅ {prop}: {export_props[prop]}")
            else:
                print(f"   ❌ Missing property: {prop}")
    else:
        print("❌ Export node NOT found in NODE_PROPERTY_DEFINITIONS")


def test_export_node_validation():
    """Test Export node validation with different property configurations"""
    print("\n\nTesting Export node validation...")

    test_cases = [
        {
            "name": "Valid Export with Format",
            "properties": {"Format": "PNG"},
            "expected_warnings": 0,
        },
        {
            "name": "Export with invalid properties (old style)",
            "properties": {"filename": "test", "format": "PNG", "enabled": True},
            "expected_warnings": 3,  # All three should be unknown
        },
        {
            "name": "Export with mixed properties",
            "properties": {"Format": "EXR", "filename": "test"},
            "expected_warnings": 1,  # Only filename should be unknown
        },
        {
            "name": "Export with BitDepth",
            "properties": {"Format": "TIF", "BitDepth": "16"},
            "expected_warnings": 0,
        },
    ]

    for test in test_cases:
        print(f"\n  Testing: {test['name']}")
        errors, warnings = validate_node_properties("Export", test["properties"])

        print(f"    Errors: {len(errors)}")
        for error in errors:
            print(f"      - {error}")

        print(f"    Warnings: {len(warnings)} (expected: {test['expected_warnings']})")
        for warning in warnings:
            print(f"      - {warning}")

        if len(warnings) == test["expected_warnings"]:
            print("    ✅ Validation passed")
        else:
            print(f"    ❌ Expected {test['expected_warnings']} warnings, got {len(warnings)}")


def test_workflow_with_export():
    """Test a complete workflow with Export node"""
    print("\n\nTesting complete workflow with Export node...")

    workflow = {
        "nodes": [
            {"id": "n1", "type": "Primitive", "properties": {"Type": "Gradient"}},
            {"id": "n2", "type": "Erosion", "properties": {"Duration": 10}},
            {"id": "n3", "type": "SatMap", "properties": {}},
            {
                "id": "n4",
                "type": "Export",
                "properties": {"Format": "PNG"},
                "save_definition": {
                    "filename": "test_export",
                    "format": "PNG",
                    "enabled": True,
                },
            },
        ],
        "connections": [
            {"from_node": "n1", "from_port": "Out", "to_node": "n2", "to_port": "In"},
            {"from_node": "n2", "from_port": "Out", "to_node": "n3", "to_port": "In"},
            {"from_node": "n2", "from_port": "Out", "to_node": "n4", "to_port": "In"},
        ],
    }

    # Test with validate_workflow
    print("\n  Testing validate_workflow...")
    try:
        validator = create_validator()
        validation_result = validator.validate_workflow(workflow["nodes"], workflow["connections"])
        print(f"    Valid: {validation_result.get('valid', validation_result.get('is_valid', False))}")
        if validation_result.get("errors"):
            print(f"    Errors: {validation_result['errors']}")
        if validation_result.get("warnings"):
            print(f"    Warnings: {validation_result['warnings']}")
            # Check for Export-related warnings
            export_warnings = [w for w in validation_result["warnings"] if "Export" in str(w)]
            if export_warnings:
                print("    ⚠️  Export-related warnings found:")
                for w in export_warnings:
                    print(f"      - {w}")
            else:
                print("    ✅ No Export-related warnings!")
    except Exception as e:
        print(f"    ❌ Error during validation: {str(e)}")
        import traceback

        traceback.print_exc()


def test_automatic_export_addition():
    """Test automatic Export node addition using error recovery"""
    print("\n\nTesting automatic Export node addition...")

    # Workflow without Export node
    project = {
        "name": "test_project",
        "nodes": [
            {"id": "n1", "type": "Mountain", "properties": {"Height": 1000}},
            {"id": "n2", "type": "Erosion", "properties": {}},
        ],
        "connections": [{"from_node": "n1", "from_port": "Out", "to_node": "n2", "to_port": "In"}],
    }

    print("  Original workflow: 2 nodes, no Export")

    # Use error recovery to fix the project
    recovery = Gaea2ErrorRecovery()
    fixed_nodes, fixed_connections, issues = recovery.auto_fix_project(
        project["nodes"], project["connections"], aggressive=True
    )
    fixed_project = {"nodes": fixed_nodes, "connections": fixed_connections}

    export_nodes = [n for n in fixed_project["nodes"] if n["type"] == "Export"]
    print(f"  After auto-fix: {len(fixed_project['nodes'])} nodes")
    print(f"  Export nodes found: {len(export_nodes)}")
    print(f"  Issues fixed: {len(issues)}")

    for issue in issues:
        if "Export" in str(issue):
            print(f"    - {issue}")

    if export_nodes:
        export_node = export_nodes[0]
        print("  ✅ Export node added automatically")
        print(f"     Properties: {export_node.get('properties', {})}")
        print(f"     Save definition: {export_node.get('save_definition', {})}")

        # Check structure based on how _ensure_export_node works
        if export_node.get("properties", {}).get("format") == "Terrain":
            print("  ⚠️  Export node uses old property structure (format in properties)")
        elif "Format" in export_node.get("properties", {}):
            print("  ✅ Export node uses new property structure (Format in properties)")
        else:
            print(f"  ℹ️  Export node structure: {json.dumps(export_node, indent=2)}")
    else:
        print("  ❌ No Export node added")


def test_error_recovery_export_fix():
    """Test how error recovery handles Export nodes"""
    print("\n\nTesting error recovery with Export nodes...")

    # Project with old-style Export node
    project = {
        "name": "test_export_fix",
        "nodes": [
            {"id": "n1", "type": "Mountain", "properties": {}},
            {
                "id": "n2",
                "type": "Export",
                "properties": {
                    "filename": "old_style",
                    "format": "PNG",
                    "enabled": True,
                },
            },
        ],
        "connections": [{"from_node": "n1", "from_port": "Out", "to_node": "n2", "to_port": "In"}],
    }

    print("  Testing project with old-style Export node...")

    # First validate to see warnings
    validator = create_validator()
    validation = validator.validate_workflow(project["nodes"], project.get("connections", []))
    print(f"  Validation warnings: {len(validation.get('warnings', []))}")
    for warning in validation.get("warnings", []):
        if "Export" in str(warning):
            print(f"    - {warning}")

    # Now auto-fix
    recovery = Gaea2ErrorRecovery()
    fixed_nodes, fixed_connections, issues = recovery.auto_fix_project(project["nodes"], project["connections"])
    fixed_project = {"nodes": fixed_nodes, "connections": fixed_connections}

    print("\n  After auto-fix:")
    print(f"  Issues fixed: {len(issues)}")

    # Check the Export node after fix
    export_nodes = [n for n in fixed_project["nodes"] if n["type"] == "Export"]
    if export_nodes:
        export_node = export_nodes[0]
        print("  Export node after fix:")
        print(f"    Properties: {export_node.get('properties', {})}")
        if "save_definition" in export_node:
            print(f"    Save definition: {export_node.get('save_definition', {})}")


if __name__ == "__main__":
    print("Gaea2 Schema Validation Tests")
    print("=" * 60)

    test_export_node_schema()
    test_export_node_validation()
    test_workflow_with_export()
    test_automatic_export_addition()
    test_error_recovery_export_fix()

    print("\n\nTests completed!")
