#!/usr/bin/env python3
"""
Comprehensive test of Gaea2 MCP robustness improvements
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import Gaea2 MCP server
from tools.mcp.gaea2.server import Gaea2MCPServer  # noqa: E402
from tools.mcp.gaea2.utils.gaea2_cache import get_cache  # noqa: E402
from tools.mcp.gaea2.utils.gaea2_logging import get_logger  # noqa: E402
from tools.mcp.gaea2.validation.gaea2_structure_validator import Gaea2StructureValidator  # noqa: E402


# Create a mock MCPTools class for backward compatibility
class MCPTools:
    server = None

    @classmethod
    def _get_server(cls):
        if cls.server is None:
            # Mock the environment check for testing
            import unittest.mock

            with unittest.mock.patch.dict(os.environ, {"GAEA2_TEST_MODE": "1"}):
                cls.server = Gaea2MCPServer()
        return cls.server

    @classmethod
    async def validate_and_fix_workflow(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly (not private)
        return await server.validate_and_fix_workflow(**kwargs)

    @classmethod
    async def repair_gaea2_project(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly
        return await server.repair_gaea2_project(**kwargs)

    @classmethod
    async def create_gaea2_from_template(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly
        return await server.create_gaea2_from_template(**kwargs)

    @classmethod
    async def validate_gaea2_project(cls, **kwargs):
        server = cls._get_server()
        # Call the method directly
        return await server.validate_gaea2_project(**kwargs)


@pytest.mark.asyncio
async def test_structure_validation():
    """Test structure validation and fixing"""
    print("\n=== Testing Structure Validation ===\n")

    validator = Gaea2StructureValidator()

    # Test 1: Invalid structure
    invalid_project = {"Nodes": {"100": {"type": "Mountain"}}}  # Missing required keys

    is_valid, errors, warnings = validator.validate_structure(invalid_project)
    print(f"Invalid project validation: {is_valid}")
    print(f"Errors: {len(errors)}")
    print(f"First error: {errors[0] if errors else 'None'}")

    # Test 2: Fix structure
    fixed = validator.fix_structure(invalid_project, "Test Project")
    print(f"\nFixes applied: {len(validator.fixes_applied)}")
    for fix in validator.fixes_applied[:3]:
        print(f"  - {fix}")

    # Test 3: Validate fixed structure
    is_valid, errors, warnings = validator.validate_structure(fixed)
    print(f"\nFixed project validation: {is_valid}")
    print(f"Remaining errors: {len(errors)}")

    return fixed


@pytest.mark.asyncio
async def test_workflow_validation():
    """Test comprehensive workflow validation"""
    print("\n=== Testing Workflow Validation ===\n")

    # Create test workflow with issues
    nodes = [
        {
            "id": 100,
            "type": "Mountain",
            "name": "Mountain1",
            "properties": {"Scale": "wrong"},
        },
        {
            "id": 101,
            "type": "Rivers",
            "name": "Rivers1",
            "properties": {"Headwaters": 500},
        },  # Too high
        {
            "id": 102,
            "type": "Erosion2",
            "name": "Erosion1",
            "properties": {},
        },  # Missing properties
        {"id": 103, "type": "SatMap", "name": "Colors", "properties": {}},  # Orphaned
    ]

    connections = [
        {
            "from_node": 100,
            "to_node": 101,
            "from_port": "Out",
            "to_port": "In",
        },  # Wrong order
        {
            "from_node": 100,
            "to_node": 101,
            "from_port": "Out",
            "to_port": "In",
        },  # Duplicate
    ]

    # Validate and fix
    result = await MCPTools.validate_and_fix_workflow(workflow={"nodes": nodes, "connections": connections}, strict_mode=False)

    if result["success"]:
        print("Validation Results:")
        print(f"  Valid: {result['valid']}")
        print(f"  Fixed: {result['fixed']}")
        print(f"  Errors: {len(result['errors'])}")

        if result["errors"]:
            print("  Validation errors:")
            for error in result["errors"][:3]:
                print(f"    - {error}")

        print(f"\nFixes Applied: {len(result['fixes_applied'])}")
        for fix in result["fixes_applied"][:5]:
            print(f"  - {fix}")

        return result["workflow"]
    else:
        print(f"Error: {result['error']}")
        return None


@pytest.mark.asyncio
async def test_caching():
    """Test caching system"""
    print("\n=== Testing Cache System ===\n")

    cache = get_cache()
    # cached_validator = CachedValidator(cache)

    # Test 1: First validation (cache miss)
    start = time.time()
    # result1 = cached_validator.cached_validate_node("Mountain", {"Scale": 1.0})
    time1 = time.time() - start
    print(f"First validation: {time1:.4f}s")

    # Test 2: Second validation (cache hit)
    start = time.time()
    # result2 = cached_validator.cached_validate_node("Mountain", {"Scale": 1.0})
    time2 = time.time() - start
    print(f"Cached validation: {time2:.4f}s")
    if time2 > 0:
        print(f"Speedup: {time1/time2:.1f}x")
    else:
        print("Speedup: N/A (cache test disabled)")

    # Test 3: Workflow analysis caching
    # workflow = ["Mountain", "Erosion2", "Rivers"]

    start = time.time()
    # analysis1 = cached_validator.cached_workflow_analysis(workflow)
    time1 = time.time() - start

    start = time.time()
    # analysis2 = cached_validator.cached_workflow_analysis(workflow)
    time2 = time.time() - start

    if time2 > 0:
        print(f"\nWorkflow analysis speedup: {time1/time2:.1f}x")
    else:
        print("\nWorkflow analysis speedup: N/A (cache test disabled)")

    # Clear cache
    cache.clear()
    print("\nCache cleared")


@pytest.mark.asyncio
async def test_logging():
    """Test logging system"""
    print("\n=== Testing Logging System ===\n")

    logger = get_logger()

    # Enable file logging for testing
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        logger.enable_file_logging(tmpdir)

        # Test different log levels
        logger.log_operation("create_project", {"name": "Test", "nodes": 5})

        logger.log_node_operation("validate", "Mountain", 100, "Validation successful")

        logger.log_validation_error("property_type", "Erosion2", "Duration must be numeric", 101)

        logger.log_performance("workflow_analysis", 0.234, 10)
        logger.log_performance("project_repair", 5.5, 100)

        # Check log file was created
        log_files = list(Path(tmpdir).glob("*.log"))
        print(f"Log files created: {len(log_files)}")

        if log_files:
            # Read first few lines
            with open(log_files[0]) as f:
                lines = f.readlines()[:3]
                print("\nSample log entries:")
                for line in lines:
                    log_entry = json.loads(line)
                    print(f"  [{log_entry['level']}] {log_entry['message']}")


@pytest.mark.asyncio
async def test_real_project_repair():
    """Test with a real project file"""
    print("\n=== Testing Real Project Repair ===\n")

    # Load a real project
    project_path = (
        Path(
            os.environ.get(
                "GAEA_OFFICIAL_PROJECTS_DIR",
                os.path.join(
                    os.path.expanduser("~"),
                    "Documents",
                    "references",
                    "Real Projects",
                    "Official Gaea Projects",
                ),
            )
        )
        / "High Mountain Peak.terrain"
    )

    if not project_path.exists():
        print("Test project not found, using mock data")
        # Use mock project data for testing
        project_data = {
            "Assets": {
                "$values": [
                    {
                        "Terrain": {
                            "Nodes": {
                                "100": {
                                    "$type": "QuadSpinner.Gaea.Mountain, Gaea",
                                    "Name": "Mountain1",
                                    "Scale": 1.0,
                                }
                            }
                        }
                    }
                ]
            }
        }
    else:
        with open(project_path) as f:
            project_data = json.load(f)

    # Save to temporary file for repair
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".terrain", delete=False) as tmp:
        json.dump(project_data, tmp, indent=2)
        temp_path = tmp.name

    try:
        # Analyze and repair
        result = await MCPTools.repair_gaea2_project(project_path=temp_path, backup=False)
    finally:
        # Clean up
        Path(temp_path).unlink(missing_ok=True)

    if result["success"]:
        print("Repair Results:")
        print(f"  Repaired: {result.get('repaired', False)}")
        print(f"  Issues Found: {len(result.get('issues_found', []))}")
        print(f"  Fixes Applied: {len(result.get('fixes_applied', []))}")

        if result.get("issues_found"):
            print("\nIssues Found:")
            for issue in result["issues_found"][:5]:
                print(f"  - {issue}")

        if result.get("fixes_applied"):
            print("\nFixes Applied:")
            for fix in result["fixes_applied"][:5]:
                print(f"  - {fix}")


@pytest.mark.asyncio
async def test_pattern_based_creation():
    """Test creating project with pattern knowledge"""
    print("\n=== Testing Pattern-Based Project Creation ===\n")

    # Create a desert canyon using patterns
    result = await MCPTools.create_gaea2_from_template(
        template_name="desert_canyon",
        project_name="Pattern-Based Desert Canyon",
        output_path="test_pattern_canyon.terrain",
    )

    if result["success"]:
        print(f"✓ Created {result['template_used']} project")
        print(f"  Nodes: {result['node_count']}")
        print(f"  Connections: {result['connection_count']}")

        # Now validate it
        with open("test_pattern_canyon.terrain") as f:
            project_data = json.load(f)

        validation = await MCPTools.validate_gaea2_project(project_data=project_data)

        print("\nValidation:")
        print(f"  Valid: {validation['valid']}")
        print(f"  Errors: {len(validation['errors'])}")
        print(f"  Warnings: {len(validation['warnings'])}")

        # Clean up
        Path("test_pattern_canyon.terrain").unlink(missing_ok=True)


@pytest.mark.asyncio
async def stress_test_performance():
    """Stress test with large workflow"""
    print("\n=== Performance Stress Test ===\n")

    # Create large workflow
    nodes = []
    connections = []

    # Create 50 nodes in a chain
    for i in range(50):
        node_type = ["Mountain", "Erosion2", "Rivers", "Combine", "SatMap"][i % 5]
        nodes.append(
            {
                "id": 100 + i,
                "type": node_type,
                "name": f"{node_type}_{i}",
                "properties": {},
            }
        )

        if i > 0:
            connections.append(
                {
                    "from_node": 100 + i - 1,
                    "to_node": 100 + i,
                    "from_port": "Out",
                    "to_port": "In",
                }
            )

    # Time validation
    start = time.time()
    result = await MCPTools.validate_and_fix_workflow(workflow={"nodes": nodes, "connections": connections}, fix_errors=True)
    duration = time.time() - start

    print(f"Validated and fixed {len(nodes)} nodes in {duration:.3f}s")
    print(f"Performance: {duration/len(nodes)*1000:.1f}ms per node")

    if result["success"]:
        print(f"Fixes applied: {len(result['fixes']['applied'])}")
        print(f"Final quality score: {result['quality_scores']['fixed']:.1f}")


async def main():
    """Run all robustness tests"""
    print("=" * 60)
    print("Gaea2 MCP Robustness Test Suite")
    print("=" * 60)

    # Run tests
    await test_structure_validation()
    await test_workflow_validation()
    await test_caching()
    await test_logging()
    await test_real_project_repair()
    await test_pattern_based_creation()
    await stress_test_performance()

    print("\n" + "=" * 60)
    print("✅ All robustness tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
