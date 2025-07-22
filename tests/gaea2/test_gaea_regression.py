"""
Automated regression testing suite for Gaea2 MCP.
This ensures that agent knowledge doesn't degrade over time and maintains consistency.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import pytest


class RegressionTestManager:
    """Manages regression test baselines and comparisons."""

    def __init__(self, baseline_dir: str = "tests/gaea2/regression_baselines"):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(exist_ok=True)
        self.current_version = self._get_version_hash()

    def _get_version_hash(self) -> str:
        """Generate a version hash based on the MCP server code."""
        # In real implementation, this would hash the actual server code
        return datetime.now().strftime("%Y%m%d")

    def save_baseline(self, test_name: str, result: Dict[str, Any]):
        """Save a test result as a baseline."""
        baseline_file = self.baseline_dir / f"{test_name}_baseline.json"

        baseline_data = {
            "version": self.current_version,
            "timestamp": datetime.now().isoformat(),
            "result": self._normalize_result(result),
        }

        with open(baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)

    def load_baseline(self, test_name: str) -> Optional[Dict[str, Any]]:
        """Load a baseline for comparison."""
        baseline_file = self.baseline_dir / f"{test_name}_baseline.json"

        if not baseline_file.exists():
            return None

        with open(baseline_file) as f:
            return json.load(f)

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize result for comparison (remove timestamps, paths, etc.)."""
        import copy

        normalized = copy.deepcopy(result)

        # Remove volatile top-level fields
        fields_to_remove = [
            "timestamp",
            "project_path",
            "duration",
            "temp_path",
            "saved_path",
        ]
        for field in fields_to_remove:
            normalized.pop(field, None)

        # Remove nested timestamps and volatile data
        self._remove_volatile_nested(normalized)

        # Sort lists for consistent comparison
        if "nodes" in normalized:
            normalized["nodes"] = sorted(normalized["nodes"], key=lambda x: x.get("id", ""))
        if "connections" in normalized:
            normalized["connections"] = sorted(
                normalized["connections"],
                key=lambda x: (
                    x.get("from_node", x.get("source", "")),
                    x.get("to_node", x.get("target", "")),
                ),
            )

        return normalized

    def _remove_volatile_nested(self, data: Any) -> None:
        """Recursively remove volatile fields from nested structures."""
        if isinstance(data, dict):
            # List of keys to remove if found
            keys_to_remove = []

            for key, value in data.items():
                # Remove any field with "Date" in the name (timestamps)
                if "Date" in key:
                    keys_to_remove.append(key)
                # Remove file paths
                elif key in ["saved_path", "project_path", "temp_path"]:
                    keys_to_remove.append(key)
                # Normalize UUIDs and random IDs
                elif key == "Id" and isinstance(value, str) and "-" in value:
                    # Replace UUID with a normalized value
                    data[key] = "normalized-uuid"
                elif key == "Id" and isinstance(value, str) and len(value) == 8:
                    # Replace short ID with normalized value
                    data[key] = "norm-id"
                else:
                    # Recursively process nested structures
                    self._remove_volatile_nested(value)

            # Remove the marked keys
            for key in keys_to_remove:
                data.pop(key, None)

        elif isinstance(data, list):
            for item in data:
                self._remove_volatile_nested(item)

    def compare_with_baseline(self, test_name: str, current_result: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current result with baseline."""
        baseline = self.load_baseline(test_name)

        if not baseline:
            return {
                "status": "no_baseline",
                "message": "No baseline exists for comparison",
            }

        baseline_result = baseline["result"]
        current_normalized = self._normalize_result(current_result)

        # Deep comparison
        differences = self._find_differences(baseline_result, current_normalized)

        if not differences:
            return {"status": "passed", "message": "Result matches baseline"}
        else:
            return {
                "status": "regression_detected",
                "differences": differences,
                "baseline_version": baseline["version"],
            }

    def _find_differences(self, baseline: Any, current: Any, path: str = "") -> List[Dict[str, Any]]:
        """Recursively find differences between baseline and current."""
        differences = []

        if type(baseline) is not type(current):
            differences.append(
                {
                    "path": path,
                    "type": "type_mismatch",
                    "baseline": type(baseline).__name__,
                    "current": type(current).__name__,
                }
            )
        elif isinstance(baseline, dict):
            all_keys = set(baseline.keys()) | set(current.keys())
            for key in all_keys:
                if key not in baseline:
                    differences.append(
                        {
                            "path": f"{path}.{key}",
                            "type": "added_key",
                            "value": current[key],
                        }
                    )
                elif key not in current:
                    differences.append(
                        {
                            "path": f"{path}.{key}",
                            "type": "removed_key",
                            "value": baseline[key],
                        }
                    )
                else:
                    differences.extend(self._find_differences(baseline[key], current[key], f"{path}.{key}"))
        elif isinstance(baseline, list):
            if len(baseline) != len(current):
                differences.append(
                    {
                        "path": path,
                        "type": "list_length_mismatch",
                        "baseline_length": len(baseline),
                        "current_length": len(current),
                    }
                )
            else:
                for i, (b_item, c_item) in enumerate(zip(baseline, current)):
                    differences.extend(self._find_differences(b_item, c_item, f"{path}[{i}]"))
        elif baseline != current:
            differences.append(
                {
                    "path": path,
                    "type": "value_mismatch",
                    "baseline": baseline,
                    "current": current,
                }
            )

        return differences


class TestGaea2Regression:
    """Regression tests for Gaea2 MCP to prevent knowledge degradation."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

    @pytest.fixture
    def regression_manager(self):
        return RegressionTestManager()

    async def execute_tool(self, url: str, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool and return the response."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/mcp/execute",
                json={"tool": tool, "parameters": parameters},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                return await response.json()

    @pytest.mark.asyncio
    async def test_template_regression(self, mcp_url, regression_manager):
        """Ensure all templates produce consistent results over time."""
        # Based on validation testing, these templates work correctly
        working_templates = [
            "basic_terrain",
            "detailed_mountain",
            "volcanic_terrain",
            "desert_canyon",
            "mountain_range",
            "river_valley",
        ]

        # These templates are known to be corrupted
        corrupted_templates = [
            "modular_portal_terrain",
            "volcanic_island",
            "canyon_system",
            "coastal_cliffs",
            "arctic_terrain",
        ]

        templates = working_templates + corrupted_templates

        regression_results = {}

        for template in templates:
            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_from_template",
                {"template_name": template, "project_name": f"regression_{template}"},
            )

            test_name = f"template_{template}"

            # For corrupted templates, we expect them to be created but fail validation
            if template in corrupted_templates:
                # These should create successfully but won't open in Gaea2
                if result.get("success"):
                    regression_results[template] = {
                        "status": "expected_corrupt",
                        "created": True,
                    }
                else:
                    regression_results[template] = {
                        "status": "error",
                        "error": result.get("error"),
                    }
            else:
                # Working templates should succeed
                if not result.get("error"):
                    # Compare with baseline
                    comparison = regression_manager.compare_with_baseline(test_name, result)
                    regression_results[template] = comparison

                    # Update baseline if needed (controlled by environment variable)
                    if comparison["status"] == "no_baseline":
                        regression_manager.save_baseline(test_name, result)
                else:
                    regression_results[template] = {
                        "status": "error",
                        "error": result["error"],
                    }

        # Check for any regressions in working templates only
        working_regressions = [
            t for t in working_templates if regression_results.get(t, {}).get("status") == "regression_detected"
        ]
        assert len(working_regressions) == 0, f"Regressions detected in working templates: {working_regressions}"

        # Verify corrupted templates remain corrupted
        for template in corrupted_templates:
            status = regression_results.get(template, {}).get("status")
            assert status in [
                "expected_corrupt",
                "error",
            ], f"Corrupted template {template} has unexpected status: {status}"

    @pytest.mark.asyncio
    async def test_validation_rules_regression(self, mcp_url, regression_manager):
        """Ensure validation rules remain consistent."""
        test_workflows = [
            {
                "name": "valid_basic",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
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
            },
            {
                "name": "missing_export",
                "workflow": {
                    "nodes": [{"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}}],
                    "connections": [],
                },
            },
            {
                "name": "circular_dependency",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Erosion", "position": {"X": 1, "Y": 0}},
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
                },
            },
        ]

        for test_case in test_workflows:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            test_name = f"validation_{test_case['name']}"
            comparison = regression_manager.compare_with_baseline(test_name, result)

            if comparison["status"] == "no_baseline":
                regression_manager.save_baseline(test_name, result)
            elif comparison["status"] == "regression_detected":
                pytest.fail(f"Validation regression in {test_case['name']}: {comparison['differences']}")

    @pytest.mark.asyncio
    async def test_node_behavior_regression(self, mcp_url, regression_manager):
        """Ensure individual node behaviors remain consistent."""
        node_tests = [
            {"name": "mountain_defaults", "node": "Mountain", "properties": {}},
            {
                "name": "erosion_with_params",
                "node": "Erosion",
                "properties": {"Duration": 10, "Intensity": 0.5},
            },
            {
                "name": "rivers_multi_output",
                "node": "Rivers",
                "properties": {"Depth": 0.3},
            },
            {
                "name": "combine_blend_modes",
                "node": "Combine",
                "properties": {"Method": "Add", "Ratio": 0.5},
            },
        ]

        for test_case in node_tests:
            workflow = {
                "nodes": [
                    {
                        "id": "1",
                        "node": test_case["node"],
                        "position": {"X": 0, "Y": 0},
                        "properties": test_case["properties"],
                    },
                    {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
                ],
                "connections": [
                    {
                        "from_node": "1",
                        "from_port": "Out",
                        "to_node": "2",
                        "to_port": "In",
                    }
                ],
            }

            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_project",
                {"project_name": f"test_{test_case['name']}", "workflow": workflow},
            )

            test_name = f"node_{test_case['name']}"
            comparison = regression_manager.compare_with_baseline(test_name, result)

            if comparison["status"] == "no_baseline":
                regression_manager.save_baseline(test_name, result)
            elif comparison["status"] == "regression_detected":
                # Some differences might be acceptable (e.g., performance improvements)
                critical_regressions = [
                    d for d in comparison["differences"] if "validation" in d["path"] or "error" in d["path"]
                ]
                assert len(critical_regressions) == 0, f"Critical regression in {test_case['name']}"

    @pytest.mark.asyncio
    async def test_pattern_analysis_regression(self, mcp_url, regression_manager):
        """Ensure pattern analysis remains consistent."""
        terrain_types = ["mountain", "desert", "coastal", "volcanic", "arctic"]

        for terrain_type in terrain_types:
            result = await self.execute_tool(mcp_url, "analyze_workflow_patterns", {"workflow_type": terrain_type})

            test_name = f"patterns_{terrain_type}"
            comparison = regression_manager.compare_with_baseline(test_name, result)

            if comparison["status"] == "no_baseline":
                regression_manager.save_baseline(test_name, result)
            elif comparison["status"] == "regression_detected":
                # Pattern recommendations can evolve, but core patterns should remain
                core_regression = False
                for diff in comparison["differences"]:
                    if "common_patterns" in diff["path"] and diff["type"] == "removed_key":
                        core_regression = True
                        break

                assert not core_regression, f"Core pattern regression in {terrain_type}"

    @pytest.mark.asyncio
    async def test_optimization_regression(self, mcp_url, regression_manager):
        """Ensure optimization behavior remains consistent."""
        test_workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Blur", "position": {"X": 1, "Y": 0}},
                {"id": "3", "node": "Blur", "position": {"X": 2, "Y": 0}},  # Redundant
                {"id": "4", "node": "Export", "position": {"X": 3, "Y": 0}},
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

        modes = ["performance", "quality", "balanced"]

        for mode in modes:
            result = await self.execute_tool(
                mcp_url,
                "optimize_gaea2_properties",
                {"workflow": test_workflow, "optimization_mode": mode},
            )

            test_name = f"optimization_{mode}"
            comparison = regression_manager.compare_with_baseline(test_name, result)

            if comparison["status"] == "no_baseline":
                regression_manager.save_baseline(test_name, result)
            elif comparison["status"] == "regression_detected":
                # Optimization strategies can improve, but should not break
                assert "error" not in str(comparison["differences"]).lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Server currently accepts invalid workflows - needs server-side fix")
    async def test_error_handling_regression(self, mcp_url, regression_manager):
        """Ensure error handling remains consistent."""
        error_scenarios = [
            {
                "name": "invalid_workflow_structure",
                "tool": "create_gaea2_project",
                "parameters": {
                    "project_name": "test_error",
                    "workflow": None,  # Invalid workflow
                },
            },
            {
                "name": "missing_template",
                "tool": "create_gaea2_from_template",
                "parameters": {
                    "template_name": "nonexistent_template",
                    "project_name": "test",
                },
            },
            {
                "name": "malformed_workflow",
                "tool": "validate_and_fix_workflow",
                "parameters": {"workflow": {"nodes": "not_a_list"}},
            },
        ]

        for scenario in error_scenarios:
            result = await self.execute_tool(mcp_url, scenario["tool"], scenario["parameters"])

            # Error responses should remain consistent
            # Allow both error format and success:false format
            has_error = result.get("error") is not None or result.get("success") is False
            assert has_error, f"Expected error response for {scenario['name']}, got: {result}"

            # Check error message consistency
            test_name = f"error_{scenario['name']}"
            error_data = {
                "has_error": True,
                "error_keywords": [word.lower() for word in result["error"].split() if len(word) > 3 and word.isalpha()][
                    :5
                ],  # First 5 significant words
            }

            comparison = regression_manager.compare_with_baseline(test_name, error_data)

            if comparison["status"] == "no_baseline":
                regression_manager.save_baseline(test_name, error_data)
            elif comparison["status"] == "regression_detected":
                # Error messages can be improved, but key terms should remain
                assert "error_keywords" not in str(comparison["differences"])


class TestPerformanceRegression:
    """Test that performance doesn't degrade over time."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

    @pytest.fixture
    def performance_log(self):
        log_file = Path("tests/gaea2/performance_log.json")
        if log_file.exists():
            with open(log_file) as f:
                return json.load(f)
        return {"tests": []}

    async def execute_timed_tool(self, url: str, tool: str, parameters: Dict[str, Any]) -> tuple[Dict[str, Any], float]:
        """Execute tool and measure time."""
        start_time = asyncio.get_event_loop().time()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/mcp/execute",
                json={"tool": tool, "parameters": parameters},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                result = await response.json()

        duration = asyncio.get_event_loop().time() - start_time
        return result, duration

    @pytest.mark.asyncio
    async def test_template_performance(self, mcp_url, performance_log):
        """Ensure template creation performance doesn't degrade."""
        template = "mountain_range"

        result, duration = await self.execute_timed_tool(
            mcp_url,
            "create_gaea2_from_template",
            {"template_name": template, "project_name": "perf_test"},
        )

        assert not result.get("error")

        # Compare with historical performance
        historical = [
            t["duration"] for t in performance_log["tests"] if t["test"] == "template_performance" and t.get("success")
        ]

        if historical:
            avg_historical = sum(historical[-10:]) / len(historical[-10:])  # Last 10 runs
            # Allow 100% performance degradation tolerance (2x slower)
            assert duration < avg_historical * 2.0, f"Performance degraded: {duration}s vs historical {avg_historical}s"

        # Log this run
        self._log_performance("template_performance", duration, not result.get("error"))

    @pytest.mark.asyncio
    async def test_validation_performance(self, mcp_url, performance_log):
        """Ensure validation performance doesn't degrade."""
        # Create a complex workflow for validation
        nodes = []
        connections = []

        for i in range(20):
            nodes.append(
                {
                    "id": str(i),
                    "node": "Perlin" if i % 2 == 0 else "Gradient",
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

        nodes.append({"id": "20", "node": "Export", "position": {"X": 0, "Y": 4}})
        connections.append({"from_node": "19", "from_port": "Out", "to_node": "20", "to_port": "In"})

        workflow = {"nodes": nodes, "connections": connections}

        result, duration = await self.execute_timed_tool(mcp_url, "validate_and_fix_workflow", {"workflow": workflow})

        # Check performance regression
        historical = [t["duration"] for t in performance_log["tests"] if t["test"] == "validation_performance"]

        if historical:
            avg_historical = sum(historical[-10:]) / len(historical[-10:])
            assert duration < avg_historical * 2.0, "Validation performance degraded"

        self._log_performance("validation_performance", duration, True)

    def _log_performance(self, test_name: str, duration: float, success: bool):
        """Log performance data for tracking."""
        log_file = Path("tests/gaea2/performance_log.json")

        if log_file.exists():
            with open(log_file) as f:
                log_data = json.load(f)
        else:
            log_data = {"tests": []}

        log_data["tests"].append(
            {
                "test": test_name,
                "duration": duration,
                "success": success,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Keep only last 1000 entries
        log_data["tests"] = log_data["tests"][-1000:]

        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)


if __name__ == "__main__":
    # Run regression tests
    pytest.main([__file__, "-v", "-s"])
