#!/usr/bin/env python
"""Test script for Gaea2 MCP Server functionality"""

import json
import sys
from pathlib import Path

import requests

# Configuration
GAEA2_MCP_URL = "http://localhost:8007"
TEST_PROJECT_DIR = Path("./test_gaea2_projects")


def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{GAEA2_MCP_URL}/health")
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Server is healthy: {health}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Failed to connect to server: {e}")
        return False


def test_list_tools():
    """Test tools listing"""
    print("\nTesting tools listing...")
    try:
        response = requests.get(f"{GAEA2_MCP_URL}/mcp/tools")
        if response.status_code == 200:
            tools = response.json()
            print(f"✓ Found {len(tools['tools'])} tools:")
            for tool in tools["tools"]:
                print(f"  - {tool['name']}: {tool['description']}")
            return True
        else:
            print(f"✗ Failed to list tools: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error listing tools: {e}")
        return False


def test_create_project():
    """Test project creation with automatic validation"""
    print("\nTesting project creation...")

    # Create test directory
    TEST_PROJECT_DIR.mkdir(exist_ok=True)

    # Simple mountain workflow
    workflow = [
        {
            "id": "mountain_1",
            "type": "Mountain",
            "position": {"x": 0, "y": 0},
            "properties": {"seed": 42, "scale": 1.0, "height": 1.0},
        },
        {
            "id": "erosion_1",
            "type": "Erosion",
            "position": {"x": 200, "y": 0},
            "properties": {"iterations": 10, "downcutting": 0.25},
        },
        {
            "id": "export_1",
            "type": "Export",
            "position": {"x": 400, "y": 0},
            "properties": {"format": "png", "filename": "mountain_test"},
        },
    ]

    # Add connections
    workflow[1]["inputs"] = {"input": {"node": "mountain_1", "output": "output"}}
    workflow[2]["inputs"] = {"input": {"node": "erosion_1", "output": "output"}}

    request_data = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": "test_mountain",
            "workflow": workflow,
            "auto_validate": True,
        },
    }

    try:
        response = requests.post(f"{GAEA2_MCP_URL}/mcp/execute", json=request_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ Project created successfully")

                # Save project for testing
                project_path = TEST_PROJECT_DIR / "test_mountain.terrain"
                with open(project_path, "w") as f:
                    json.dump(result["project"], f, indent=2)
                print(f"✓ Saved to {project_path}")

                return True, str(project_path)
            else:
                print(f"✗ Project creation failed: {result.get('error')}")
                return False, None
        else:
            print(f"✗ Request failed: {response.status_code}")
            return False, None
    except Exception as e:
        print(f"✗ Error creating project: {e}")
        return False, None


def test_validate_workflow():
    """Test workflow validation and fixing"""
    print("\nTesting workflow validation...")

    # Create a workflow with intentional issues
    bad_workflow = [
        {
            "id": "mountain_1",
            "type": "Mountain",
            "position": {"x": 0, "y": 0},
            "properties": {
                "seed": 42,
                "scale": 5.0,  # Out of range (should be 0-2)
                "height": -1.0,  # Negative height
            },
        },
        {
            "id": "erosion_1",
            "type": "Erosion",
            "position": {"x": 200, "y": 0},
            "properties": {
                "iterations": 1000,  # Too high
                "downcutting": 2.0,  # Out of range
            },
        },
        # Missing Export node
    ]

    # Add invalid connection
    bad_workflow[1]["inputs"] = {"input": {"node": "mountain_1", "output": "invalid_port"}}

    request_data = {
        "tool": "validate_and_fix_workflow",
        "parameters": {
            "workflow": bad_workflow,
            "fix_errors": True,
            "add_missing_nodes": True,
        },
    }

    try:
        response = requests.post(f"{GAEA2_MCP_URL}/mcp/execute", json=request_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                validation = result["results"]
                print("✓ Validation completed")
                print(f"  Original validation: {validation['validation_results']}")
                print(f"  Fixes applied: {len(validation['fixes_applied'])}")
                print(f"  Final workflow valid: {validation['is_valid']}")
                return True
            else:
                print(f"✗ Validation failed: {result.get('error')}")
                return False
        else:
            print(f"✗ Request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error validating workflow: {e}")
        return False


def test_run_project(project_path: str = None):
    """Test running a Gaea2 project (if Gaea2 is configured)"""
    print("\nTesting project execution...")

    if not project_path:
        print("⚠ No project path provided, skipping execution test")
        return False

    request_data = {
        "tool": "run_gaea2_project",
        "parameters": {
            "project_path": project_path,
            "verbose": True,
            "variables": {"erosion_strength": 0.5, "detail_level": 2},
        },
    }

    try:
        response = requests.post(f"{GAEA2_MCP_URL}/mcp/execute", json=request_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ Project executed successfully")
                print(f"  Command: {result['command']}")
                print(f"  Return code: {result['return_code']}")

                if result.get("parsed_output"):
                    output = result["parsed_output"]
                    print(f"  Nodes processed: {len(output['nodes_processed'])}")
                    print(f"  Errors: {len(output['errors'])}")
                    print(f"  Warnings: {len(output['warnings'])}")
                    print(f"  Exports: {output['exports']}")

                return True
            else:
                error = result.get("error", "Unknown error")
                if "Gaea2 executable path not configured" in error:
                    print(f"⚠ Gaea2 not configured: {error}")
                    print("  Set GAEA2_PATH environment variable to enable CLI features")
                else:
                    print(f"✗ Execution failed: {error}")
                return False
        else:
            print(f"✗ Request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error running project: {e}")
        return False


def test_analyze_patterns():
    """Test workflow pattern analysis"""
    print("\nTesting pattern analysis...")

    request_data = {
        "tool": "analyze_workflow_patterns",
        "parameters": {
            "workflow_or_directory": str(TEST_PROJECT_DIR),
            "include_suggestions": True,
        },
    }

    try:
        response = requests.post(f"{GAEA2_MCP_URL}/mcp/execute", json=request_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ Pattern analysis completed")
                analysis = result.get("analysis", {})
                if "workflow_count" in analysis:
                    print(f"  Workflows analyzed: {analysis['workflow_count']}")
                if "common_patterns" in analysis:
                    print(f"  Common patterns found: {len(analysis['common_patterns'])}")
                return True
            else:
                print(f"✗ Analysis failed: {result.get('error')}")
                return False
        else:
            print(f"✗ Request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error analyzing patterns: {e}")
        return False


def test_execution_history():
    """Test execution history analysis"""
    print("\nTesting execution history...")

    request_data = {"tool": "analyze_execution_history", "parameters": {}}

    try:
        response = requests.post(f"{GAEA2_MCP_URL}/mcp/execute", json=request_data)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                analysis = result.get("analysis", {})
                print("✓ Execution history retrieved")
                print(f"  Total runs: {analysis.get('total_runs', 0)}")
                print(f"  Successful: {analysis.get('successful_runs', 0)}")
                print(f"  Failed: {analysis.get('failed_runs', 0)}")
                if analysis.get("common_errors"):
                    print("  Common errors:")
                    for error, count in analysis["common_errors"].items():
                        print(f"    - {error}: {count} times")
                return True
            else:
                print(f"✗ Failed to get history: {result.get('error')}")
                return False
        else:
            print(f"✗ Request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error getting history: {e}")
        return False


def main():
    """Run all tests"""
    print("=== Gaea2 MCP Server Test Suite ===\n")

    # Check if server is running
    if not test_health():
        print("\nERROR: Gaea2 MCP Server is not running!")
        print("Start it with: python tools/mcp/gaea2_mcp_server.py")
        sys.exit(1)

    # Run tests
    tests_passed = 0
    tests_total = 0

    # Basic tests
    tests = [
        ("List Tools", test_list_tools),
        ("Validate Workflow", test_validate_workflow),
        ("Analyze Patterns", test_analyze_patterns),
    ]

    for name, test_func in tests:
        tests_total += 1
        if test_func():
            tests_passed += 1

    # Project creation test (returns project path)
    tests_total += 1
    success, project_path = test_create_project()
    if success:
        tests_passed += 1

    # Project execution test (requires Gaea2)
    tests_total += 1
    if test_run_project(project_path):
        tests_passed += 1

    # Execution history (should show our run)
    tests_total += 1
    if test_execution_history():
        tests_passed += 1

    # Summary
    print("\n=== Test Summary ===")
    print(f"Passed: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {tests_total - tests_passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
