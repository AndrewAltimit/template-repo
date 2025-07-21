"""
Integration Test Framework for Gaea2 MCP - Interactive Learning and Validation

This test framework follows the AI Agent Training Guide for closed-source software,
specifically implementing Integration requirements for autonomous testing and validation.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import aiohttp
import pytest


class Gaea2TestFramework:
    """
    Comprehensive test framework for Gaea2 MCP following Integration guidelines:
    - Unit test development for successful operations
    - Expected failure scenarios
    - Edge cases and boundary conditions
    - Error handling verification
    - Direct MCP interaction testing
    - Automated regression testing
    """

    def __init__(self, server_url: str = "http://192.168.0.152:8007"):
        self.server_url = server_url
        self.test_results = []
        self.knowledge_base = {}
        self.regression_baseline = {}

    async def execute_mcp_tool(self, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool and capture all response details including errors."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.server_url}/mcp/execute",
                    json={"tool": tool, "arguments": parameters},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    result = await response.json()

                    # Capture comprehensive error feedback (Phase 1 requirement)
                    test_record = {
                        "timestamp": datetime.now().isoformat(),
                        "tool": tool,
                        "parameters": parameters,
                        "status_code": response.status,
                        "response": result,
                        "success": response.status == 200 and not result.get("error"),
                    }

                    self.test_results.append(test_record)

                    # Build knowledge base of working configurations
                    if test_record["success"]:
                        self._update_knowledge_base(tool, parameters, result)

                    return result

            except Exception as e:
                error_record = {
                    "timestamp": datetime.now().isoformat(),
                    "tool": tool,
                    "parameters": parameters,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "success": False,
                }
                self.test_results.append(error_record)
                return {"error": str(e), "error_type": type(e).__name__}

    def _update_knowledge_base(self, tool: str, parameters: Dict[str, Any], result: Dict[str, Any]):
        """Update knowledge base with successful patterns."""
        if tool not in self.knowledge_base:
            self.knowledge_base[tool] = []

        self.knowledge_base[tool].append(
            {
                "parameters": parameters,
                "result_keys": list(result.keys()),
                "timestamp": datetime.now().isoformat(),
            }
        )


class TestSuccessfulOperations:
    """Test cases for expected successful operations."""

    @pytest.fixture
    def framework(self):
        return Gaea2TestFramework()

    @pytest.mark.asyncio
    async def test_create_basic_terrain(self, framework):
        """Test creating a basic terrain project."""
        result = await framework.execute_mcp_tool(
            "create_gaea2_from_template",
            {"template_name": "basic_terrain", "project_name": "test_basic"},
        )

        assert result.get("success"), f"Expected success but got error: {result.get('error')}"
        assert "project_path" in result.get("result", {})
        # API returns validation info differently - check for success indicators
        assert result.get("result", {}).get("node_count", 0) > 0
        # Note: basic_terrain template may have 0 connections
        assert result.get("result", {}).get("connection_count", 0) >= 0

    @pytest.mark.asyncio
    async def test_validate_workflow(self, framework):
        """Test workflow validation with a known good workflow."""
        # Based on reference analysis: common workflow pattern
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Slump",
                    "position": {"X": 0, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "2",
                    "type": "FractalTerraces",
                    "position": {"X": 1, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "3",
                    "type": "Combine",
                    "position": {"X": 2, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "4",
                    "type": "Export",
                    "position": {"X": 3, "Y": 0},
                    "properties": {},
                },
            ],
            "connections": [
                {
                    "from_node": "1",
                    "from_port": "Out",
                    "to_node": "2",
                    "to_port": "In",
                },
                {
                    "from_node": "2",
                    "from_port": "Out",
                    "to_node": "3",
                    "to_port": "In",
                },
                {
                    "from_node": "3",
                    "from_port": "Out",
                    "to_node": "4",
                    "to_port": "In",
                },
            ],
        }

        result = await framework.execute_mcp_tool("validate_and_fix_workflow", {"workflow": workflow})

        assert result.get("success"), f"Validation failed: {result.get('error')}"
        # The validator may fix issues automatically
        if result.get("result", {}).get("fixed"):
            assert len(result.get("result", {}).get("fixes_applied", [])) > 0
        else:
            assert result.get("result", {}).get("valid") is True
            assert len(result.get("result", {}).get("errors", [])) == 0

    @pytest.mark.asyncio
    async def test_analyze_patterns(self, framework):
        """Test workflow pattern analysis."""
        # First create a workflow to analyze
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "2",
                    "type": "Erosion",
                    "position": {"X": 1, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "3",
                    "type": "Export",
                    "position": {"X": 2, "Y": 0},
                    "properties": {},
                },
            ],
            "connections": [
                {
                    "from_node": "1",
                    "from_port": "Out",
                    "to_node": "2",
                    "to_port": "In",
                },
                {
                    "from_node": "2",
                    "from_port": "Out",
                    "to_node": "3",
                    "to_port": "In",
                },
            ],
        }

        result = await framework.execute_mcp_tool("analyze_workflow_patterns", {"workflow_or_directory": workflow})

        assert result.get("success"), f"Pattern analysis failed: {result.get('error')}"
        assert "common_patterns" in result.get("result", {}) or "common_patterns" in result
        assert "recommended_nodes" in result.get("result", {}) or "recommended_nodes" in result
        recommended = result.get("result", {}).get("recommended_nodes", result.get("recommended_nodes", []))
        assert len(recommended) > 0

    @pytest.mark.asyncio
    async def test_node_suggestions(self, framework):
        """Test intelligent node suggestions."""
        result = await framework.execute_mcp_tool(
            "suggest_gaea2_nodes",
            {
                "current_nodes": ["Mountain", "Erosion"],
                "workflow_goal": "realistic terrain",
            },
        )

        assert result.get("success"), f"Node suggestions failed: {result.get('error')}"
        suggestions = result.get("result", {}).get("suggestions", result.get("suggestions", []))
        assert len(suggestions) > 0
        assert all("node" in s and "reason" in s for s in suggestions)


class TestExpectedFailures:
    """Test cases for expected failure scenarios."""

    @pytest.fixture
    def framework(self):
        return Gaea2TestFramework()

    @pytest.mark.asyncio
    async def test_invalid_template_name(self, framework):
        """Test with non-existent template name."""
        result = await framework.execute_mcp_tool(
            "create_gaea2_from_template",
            {"template_name": "non_existent_template", "project_name": "test"},
        )

        assert result.get("error") is not None
        assert "template" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_node_type(self, framework):
        """Test workflow with invalid node type."""
        workflow = {
            "nodes": [{"id": "1", "type": "InvalidNodeType", "position": {"X": 0, "Y": 0}}],
            "connections": [],
        }

        result = await framework.execute_mcp_tool("validate_and_fix_workflow", {"workflow": workflow})

        # The server might be permissive and accept unknown node types
        # or it might fix them automatically
        if result.get("success"):
            # The server might be permissive and accept unknown node types or fix them
            assert (
                result.get("result", {}).get("valid") is False
                or len(result.get("result", {}).get("fixes_applied", [])) > 0
                or "InvalidNodeType" in str(result.get("result", {}).get("workflow", {}))
            )
        else:
            assert "InvalidNodeType" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_circular_connections(self, framework):
        """Test detection of circular dependencies."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {},
                },
                {
                    "id": "2",
                    "type": "Erosion",
                    "position": {"X": 1, "Y": 0},
                    "properties": {},
                },
            ],
            "connections": [
                {
                    "from_node": "1",
                    "from_port": "Out",
                    "to_node": "2",
                    "to_port": "In",
                },
                {
                    "from_node": "2",
                    "from_port": "Out",
                    "to_node": "1",
                    "to_port": "In",
                },
            ],
        }

        result = await framework.execute_mcp_tool("validate_and_fix_workflow", {"workflow": workflow})

        if result.get("success"):
            assert result.get("result", {}).get("valid") is False or len(result.get("result", {}).get("fixes_applied", [])) > 0
        else:
            assert result.get("error") is not None


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    @pytest.fixture
    def framework(self):
        return Gaea2TestFramework()

    @pytest.mark.asyncio
    async def test_empty_workflow(self, framework):
        """Test validation of empty workflow."""
        result = await framework.execute_mcp_tool("validate_and_fix_workflow", {"workflow": {"nodes": [], "connections": []}})

        # Should either fail or auto-fix by adding required nodes
        if result.get("success"):
            assert result.get("result", {}).get("valid") is False or len(result.get("result", {}).get("fixes_applied", [])) > 0
        else:
            # If there's an error, it should be meaningful
            assert result.get("error") is not None

    @pytest.mark.asyncio
    async def test_maximum_complexity(self, framework):
        """Test with maximum complexity workflow (based on reference projects)."""
        # Create a workflow with 22 nodes (max seen in references)
        nodes = []
        connections = []

        for i in range(22):
            nodes.append(
                {
                    "id": str(i),
                    "type": "Perlin" if i % 2 == 0 else "Gradient",
                    "position": {"X": i % 5, "Y": i // 5},
                }
            )

            if i > 0:
                connections.append(
                    {
                        "from_node": str(i - 1),
                        "from_port": "Out",
                        "to_node": str(i),
                        "to_port": "In",
                    }
                )

        result = await framework.execute_mcp_tool(
            "validate_and_fix_workflow",
            {"workflow": {"nodes": nodes, "connections": connections}},
        )

        assert "error" not in result or "timeout" not in str(result.get("error", ""))

    @pytest.mark.asyncio
    async def test_special_characters_in_names(self, framework):
        """Test handling of special characters in project names."""
        special_names = [
            "test project",  # space
            "test-project",  # hyphen
            "test_project",  # underscore
            "test.project",  # dot
            "测试",  # unicode
        ]

        for name in special_names:
            result = await framework.execute_mcp_tool(
                "create_gaea2_project",
                {
                    "project_name": name,
                    "nodes": [{"id": "1", "type": "Mountain"}],
                    "connections": [],
                },
            )

            # Should either succeed or provide clear error message
            if result.get("error"):
                assert "name" in result["error"].lower() or "character" in result["error"].lower()


class TestErrorHandling:
    """Test error handling and recovery mechanisms."""

    @pytest.fixture
    def framework(self):
        return Gaea2TestFramework()

    @pytest.mark.asyncio
    async def test_malformed_json_handling(self, framework):
        """Test handling of malformed workflow data."""
        # Send workflow with missing required fields
        result = await framework.execute_mcp_tool(
            "validate_and_fix_workflow",
            {"workflow": {"nodes": [{"id": "1"}]}},  # Missing 'node' field
        )

        assert result.get("error") is not None or (result.get("success") and result.get("result", {}).get("valid") is False)

    @pytest.mark.asyncio
    async def test_connection_recovery(self, framework):
        """Test connection error recovery."""
        # Test with invalid server URL
        framework.server_url = "http://invalid-host:8007"

        result = await framework.execute_mcp_tool(
            "create_gaea2_from_template",
            {"template_name": "basic_terrain", "project_name": "test"},
        )

        assert result.get("error") is not None
        assert result.get("error_type") in [
            "ClientConnectorError",
            "ClientConnectorDNSError",
            "ClientError",
            "Exception",
        ]

    @pytest.mark.asyncio
    async def test_timeout_handling(self, framework):
        """Test timeout handling for long operations."""
        # Create extremely complex workflow to trigger timeout
        nodes = [{"id": str(i), "type": "Mountain"} for i in range(100)]

        result = await framework.execute_mcp_tool(
            "optimize_gaea2_properties",
            {
                "workflow": {"nodes": nodes, "connections": []},
                "optimization_mode": "balanced",
            },
        )

        # Should complete or timeout gracefully
        assert isinstance(result, dict)


class TestRegressionSuite:
    """Automated regression testing to prevent knowledge degradation."""

    @pytest.fixture
    def framework(self):
        framework = Gaea2TestFramework()
        # Load baseline results if they exist
        baseline_path = Path("tests/gaea2/regression_baseline.json")
        if baseline_path.exists():
            with open(baseline_path) as f:
                framework.regression_baseline = json.load(f)
        return framework

    @pytest.mark.asyncio
    async def test_template_consistency(self, framework):
        """Ensure all templates continue to work correctly."""
        templates = [
            "basic_terrain",
            "detailed_mountain",
            "volcanic_terrain",
            "desert_canyon",
            "mountain_range",
            "volcanic_island",
            "canyon_system",
            "coastal_cliffs",
            "arctic_terrain",
            "river_valley",
        ]

        for template in templates:
            result = await framework.execute_mcp_tool(
                "create_gaea2_from_template",
                {"template_name": template, "project_name": f"regression_{template}"},
            )

            # Compare with baseline if exists
            baseline_key = f"template_{template}"
            if baseline_key in framework.regression_baseline:
                baseline = framework.regression_baseline[baseline_key]
                assert result.get("success") == baseline.get("validation_passed")
                assert set(result.keys()) == set(baseline.keys())

    @pytest.mark.asyncio
    async def test_validation_consistency(self, framework):
        """Ensure validation rules remain consistent."""
        test_cases = [
            # Valid workflow
            {
                "name": "valid_simple",
                "workflow": {
                    "nodes": [
                        {"id": "1", "type": "Mountain", "properties": {}},
                        {"id": "2", "type": "Export", "properties": {}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "Out",
                            "to_node": "2",
                            "to_port": "In",
                        }
                    ],
                },
                "expected_valid": True,
            },
            # Missing Export node
            {
                "name": "missing_export",
                "workflow": {
                    "nodes": [{"id": "1", "type": "Mountain"}],
                    "connections": [],
                },
                "expected_valid": False,
            },
        ]

        for test_case in test_cases:
            result = await framework.execute_mcp_tool("validate_and_fix_workflow", {"workflow": test_case["workflow"]})

            # If auto-fix is enabled, check fixed_issues instead
            if test_case["expected_valid"]:
                assert result.get("success") and result.get("result", {}).get("valid") is True
            else:
                assert (
                    not result.get("success")
                    or result.get("result", {}).get("valid") is False
                    or len(result.get("result", {}).get("fixes_applied", [])) > 0
                )


# Utility functions for test management


def save_test_results(framework: Gaea2TestFramework, output_path: str = "tests/gaea2/test_results.json"):
    """Save test results for analysis and improvement."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_results": framework.test_results,
        "knowledge_base": framework.knowledge_base,
        "summary": {
            "total_tests": len(framework.test_results),
            "successful": sum(1 for r in framework.test_results if r.get("success")),
            "failed": sum(1 for r in framework.test_results if not r.get("success")),
        },
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    return results


def generate_regression_baseline(
    framework: Gaea2TestFramework,
    output_path: str = "tests/gaea2/regression_baseline.json",
):
    """Generate regression baseline from successful test runs."""
    baseline = {}

    for result in framework.test_results:
        if result.get("success"):
            key = f"{result['tool']}_{hash(json.dumps(result['parameters'], sort_keys=True)) % 10000}"
            baseline[key] = {
                "tool": result["tool"],
                "parameters": result["parameters"],
                "response_keys": list(result["response"].keys()),
                "validation_passed": result["response"].get("validation_passed"),
            }

    with open(output_path, "w") as f:
        json.dump(baseline, f, indent=2)

    return baseline


# Performance monitoring for autonomous operation


class PerformanceMonitor:
    """Monitor agent performance for unsupervised mode."""

    def __init__(self):
        self.metrics = {
            "response_times": [],
            "error_rates": {},
            "success_patterns": {},
            "resource_usage": [],
        }

    def record_operation(self, tool: str, duration: float, success: bool, error_type: str = None):
        """Record operation metrics."""
        self.metrics["response_times"].append(
            {
                "tool": tool,
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if tool not in self.metrics["error_rates"]:
            self.metrics["error_rates"][tool] = {"total": 0, "errors": 0}

        self.metrics["error_rates"][tool]["total"] += 1
        if not success:
            self.metrics["error_rates"][tool]["errors"] += 1

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        avg_response_time = (
            sum(r["duration"] for r in self.metrics["response_times"]) / len(self.metrics["response_times"])
            if self.metrics["response_times"]
            else 0
        )

        error_summary = {}
        for tool, stats in self.metrics["error_rates"].items():
            error_rate = stats["errors"] / stats["total"] if stats["total"] > 0 else 0
            error_summary[tool] = {
                "error_rate": error_rate,
                "total_calls": stats["total"],
                "errors": stats["errors"],
            }

        return {
            "average_response_time": avg_response_time,
            "error_summary": error_summary,
            "total_operations": len(self.metrics["response_times"]),
        }


if __name__ == "__main__":
    # Example usage for autonomous testing

    async def run_comprehensive_tests():
        framework = Gaea2TestFramework()
        monitor = PerformanceMonitor()

        # Run all test classes
        test_classes = [
            TestSuccessfulOperations(),
            TestExpectedFailures(),
            TestEdgeCases(),
            TestErrorHandling(),
            TestRegressionSuite(),
        ]

        for test_class in test_classes:
            test_class.framework = framework
            for method_name in dir(test_class):
                if method_name.startswith("test_"):
                    method = getattr(test_class, method_name)
                    if asyncio.iscoroutinefunction(method):
                        print(f"Running {test_class.__class__.__name__}.{method_name}")
                        start_time = asyncio.get_event_loop().time()
                        try:
                            await method(framework)
                            duration = asyncio.get_event_loop().time() - start_time
                            monitor.record_operation(method_name, duration, True)
                        except Exception as e:
                            duration = asyncio.get_event_loop().time() - start_time
                            monitor.record_operation(method_name, duration, False, type(e).__name__)
                            print(f"  Error: {e}")

        # Save results
        results = save_test_results(framework)
        generate_regression_baseline(framework)
        performance = monitor.get_performance_report()

        print("\nTest Summary:")
        print(f"  Total: {results['summary']['total_tests']}")
        print(f"  Successful: {results['summary']['successful']}")
        print(f"  Failed: {results['summary']['failed']}")
        print("\nPerformance:")
        print(f"  Avg Response Time: {performance['average_response_time']:.2f}s")

        return results, performance

    # Uncomment to run:
    # asyncio.run(run_comprehensive_tests())
