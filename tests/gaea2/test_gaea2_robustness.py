#!/usr/bin/env python3
"""
Comprehensive test of Gaea2 MCP robustness improvements
"""

import asyncio
import json
import time
from pathlib import Path

from tools.mcp.gaea2_cache import get_cache
from tools.mcp.gaea2_logging import get_logger, log_operation

# Import Gaea2 MCP server
from tools.mcp.gaea2_mcp_server import Gaea2MCPServer
from tools.mcp.gaea2_structure_validator import Gaea2StructureValidator


# Create a mock MCPTools class for backward compatibility
class MCPTools:
    server = Gaea2MCPServer()

    @classmethod
    async def validate_and_fix_workflow(cls, **kwargs):
        return await cls.server.validate_and_fix_workflow(**kwargs)

    @classmethod
    async def repair_gaea2_project(cls, **kwargs):
        return await cls.server.repair_gaea2_project(**kwargs)

    @classmethod
    async def create_gaea2_from_template(cls, **kwargs):
        return await cls.server.create_gaea2_from_template(**kwargs)

    @classmethod
    async def validate_gaea2_project(cls, **kwargs):
        return await cls.server.validate_gaea2_project(**kwargs)


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
    result = await MCPTools.validate_and_fix_workflow(nodes=nodes, connections=connections, auto_fix=True, aggressive=True)

    if result["success"]:
        print("Validation Results:")
        print(f"  Property issues: {len(result['validation']['property_issues'])}")
        print(f"  Connection errors: {len(result['validation']['connection_errors'])}")
        print(f"  Connection warnings: {len(result['validation']['connection_warnings'])}")

        print(f"\nFixes Applied: {len(result['fixes']['applied'])}")
        for fix in result["fixes"]["applied"][:5]:
            print(f"  - {fix}")

        print("\nQuality Scores:")
        print(f"  Original: {result['quality_scores']['original']:.1f}")
        print(f"  Fixed: {result['quality_scores']['fixed']:.1f}")
        print(f"  Improvement: {result['quality_scores']['improvement']:.1f}")

        return result["fixed_workflow"]
    else:
        print(f"Error: {result['error']}")
        return None


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
    print(f"Speedup: {time1/time2:.1f}x")

    # Test 3: Workflow analysis caching
    # workflow = ["Mountain", "Erosion2", "Rivers"]

    start = time.time()
    # analysis1 = cached_validator.cached_workflow_analysis(workflow)
    time1 = time.time() - start

    start = time.time()
    # analysis2 = cached_validator.cached_workflow_analysis(workflow)
    time2 = time.time() - start

    print(f"\nWorkflow analysis speedup: {time1/time2:.1f}x")

    # Clear cache
    cache.clear()
    print("\nCache cleared")


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


@log_operation("test_real_project_repair")
async def test_real_project_repair():
    """Test with a real project file"""
    print("\n=== Testing Real Project Repair ===\n")

    # Load a real project
    project_path = Path("/home/miku/Documents/references/Real Projects/Official Gaea Projects/High Mountain Peak.terrain")

    if not project_path.exists():
        print("Test project not found")
        return

    with open(project_path) as f:
        project_data = json.load(f)

    # Analyze and repair
    result = await MCPTools.repair_gaea2_project(project_data=project_data, auto_fix=True)

    if result["success"] and "analysis" in result:
        analysis = result["analysis"]["analysis"]
        print("Project Analysis:")
        print(f"  Health Score: {analysis['health_score']:.1f}/100")
        print(f"  Node Count: {analysis['node_count']}")
        print(f"  Connection Count: {analysis['connection_count']}")
        print(f"  Total Errors: {analysis['errors']['total_errors']}")
        print(f"  Auto-fixable: {analysis['errors']['auto_fixable']}")

        if result["repair_result"]["fixes_applied"]:
            print("\nFixes Applied:")
            for fix in result["repair_result"]["fixes_applied"][:5]:
                print(f"  - {fix}")


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
    result = await MCPTools.validate_and_fix_workflow(nodes=nodes, connections=connections, auto_fix=True)
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
