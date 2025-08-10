#!/usr/bin/env python3
"""
Quick test to verify Export node fixes work correctly
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tools.mcp.core import MCPClient  # noqa: E402


def test_export_node():
    """Test Export node with corrected format"""
    client = MCPClient(base_url="http://192.168.0.152:8000")

    # Check server health
    if not client.health_check():
        print("❌ MCP server not available")
        return

    print("✅ MCP server is healthy")

    # Create a simple workflow with Export node
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
                    "filename": "export_test",
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

    print("\nTesting Export node with correct format...")
    result = client.execute_tool(
        "create_gaea2_project",
        {
            "project_name": "export_fix_test",
            "workflow": workflow,
            "output_path": "outputs/tests",
            "auto_validate": True,
        },
    )

    if result.get("success"):
        print("✅ Project created successfully!")
        if result.get("validation_results"):
            val = result["validation_results"]
            print("\nValidation summary:")
            print(f"  - Issues fixed: {len(val.get('issues_fixed', []))}")
            print(f"  - Warnings: {len(val.get('warnings', []))}")

            # Check for Export-related warnings
            export_warnings = [w for w in val.get("warnings", []) if "Export" in w]
            if export_warnings:
                print("\n⚠️  Export node warnings still present:")
                for warning in export_warnings:
                    print(f"    - {warning}")
            else:
                print("\n✅ No Export node warnings!")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    test_export_node()
