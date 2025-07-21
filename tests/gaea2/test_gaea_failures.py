"""
Test suite for expected failures and error handling in Gaea2 MCP.
These tests verify that the system handles errors gracefully and provides meaningful feedback.
"""

from typing import Any, Dict

import aiohttp
import pytest


class TestGaea2Failures:
    """Test expected failure scenarios and error handling."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

    async def execute_tool(self, url: str, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool and return the response."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}/mcp/execute",
                    json={"tool": tool, "parameters": parameters},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    return await response.json()
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__}

    @pytest.mark.asyncio
    async def test_invalid_node_types(self, mcp_url):
        """Test various invalid node type scenarios."""
        invalid_workflows = [
            {
                "name": "completely_invalid_node",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "ThisNodeDoesNotExist",
                            "position": {"X": 0, "Y": 0},
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
                },
            },
            {
                "name": "misspelled_node",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "Montain",
                            "position": {"X": 0, "Y": 0},
                        },  # Should be "Mountain"
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
                "name": "case_sensitive_error",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "mountain",
                            "position": {"X": 0, "Y": 0},
                        },  # Should be "Mountain"
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
        ]

        for test_case in invalid_workflows:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            # Should either report invalid or attempt to fix
            assert (
                result.get("results", {}).get("is_valid") is False
                or len(result.get("results", {}).get("fixes_applied", [])) > 0
            )

            # Check for meaningful error messages
            if result.get("results", {}).get("validation_errors"):
                assert any(
                    "node" in issue["message"].lower() for issue in result.get("results", {}).get("validation_errors", [])
                )

    @pytest.mark.asyncio
    async def test_invalid_connections(self, mcp_url):
        """Test various invalid connection scenarios."""
        invalid_connections = [
            {
                "name": "nonexistent_source_node",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "99",
                            "from_port": "Out",
                            "to_node": "2",
                            "to_port": "In",
                        }
                    ],
                },
            },
            {
                "name": "nonexistent_target_node",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "Out",
                            "to_node": "99",
                            "to_port": "In",
                        }
                    ],
                },
            },
            {
                "name": "invalid_port_names",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Export", "position": {"X": 1, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "InvalidPort",
                            "to_node": "2",
                            "to_port": "In",
                        }
                    ],
                },
            },
            {
                "name": "circular_dependency",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                        {"id": "3", "node": "Blur", "position": {"X": 2, "Y": 0}},
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
                            "to_node": "1",
                            "to_port": "In",
                        },  # Circular
                    ],
                },
            },
        ]

        for test_case in invalid_connections:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            # Should detect and report or fix the issue
            assert (
                result.get("results", {}).get("is_valid") is False
                or len(result.get("results", {}).get("fixes_applied", [])) > 0
            )

    @pytest.mark.asyncio
    async def test_missing_required_nodes(self, mcp_url):
        """Test workflows missing required nodes like Export."""
        workflows_missing_requirements = [
            {
                "name": "no_export_node",
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
                        }
                    ],
                },
            },
            {
                "name": "disconnected_export",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                        {
                            "id": "3",
                            "node": "Export",
                            "position": {"X": 2, "Y": 0},
                        },  # Not connected
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
                "name": "orphaned_nodes",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {
                            "id": "2",
                            "node": "Perlin",
                            "position": {"X": 0, "Y": 1},
                        },  # Orphaned
                        {"id": "3", "node": "Export", "position": {"X": 1, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "Out",
                            "to_node": "3",
                            "to_port": "In",
                        }
                    ],
                },
            },
        ]

        for test_case in workflows_missing_requirements:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            # Should either fail validation or auto-fix
            if result.get("results", {}).get("is_valid"):
                # If valid, it must have been fixed
                assert len(result.get("results", {}).get("fixes_applied", [])) > 0
            else:
                # If invalid, should report the issue
                assert len(result.get("results", {}).get("validation_errors", [])) > 0

    @pytest.mark.asyncio
    async def test_invalid_property_values(self, mcp_url):
        """Test nodes with invalid property values."""
        invalid_property_workflows = [
            {
                "name": "out_of_range_values",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "Mountain",
                            "position": {"X": 0, "Y": 0},
                            "properties": {
                                "Scale": -10,  # Negative scale
                                "Height": 999999,  # Extremely high value
                            },
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
                },
            },
            {
                "name": "wrong_property_types",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "Erosion",
                            "position": {"X": 0, "Y": 0},
                            "properties": {
                                "Duration": "five",  # String instead of number
                                "Intensity": None,  # Null value
                            },
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
                },
            },
            {
                "name": "invalid_property_names",
                "workflow": {
                    "nodes": [
                        {
                            "id": "1",
                            "node": "Mountain",
                            "position": {"X": 0, "Y": 0},
                            "properties": {
                                "InvalidProperty": 10,
                                "AnotherBadProp": "test",
                            },
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
                },
            },
        ]

        for test_case in invalid_property_workflows:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            # Should handle invalid properties gracefully
            assert isinstance(result, dict)
            # Should either fix or report issues
            assert (
                result.get("results", {}).get("is_valid") is False
                or len(result.get("results", {}).get("fixes_applied", [])) > 0
            )

    @pytest.mark.asyncio
    async def test_malformed_requests(self, mcp_url):
        """Test handling of malformed API requests."""
        malformed_requests = [
            {
                "name": "missing_required_parameter",
                "tool": "create_gaea2_project",
                "parameters": {},  # Missing project_name and workflow
            },
            {
                "name": "wrong_parameter_types",
                "tool": "create_gaea2_from_template",
                "parameters": {
                    "template_name": 123,  # Should be string
                    "project_name": ["test"],  # Should be string
                },
            },
            {
                "name": "extra_unknown_parameters",
                "tool": "validate_and_fix_workflow",
                "parameters": {
                    "workflow": {"nodes": [], "connections": []},
                    "unknown_param": "value",
                    "another_unknown": 123,
                },
            },
            {
                "name": "null_workflow",
                "tool": "validate_and_fix_workflow",
                "parameters": {"workflow": None},
            },
        ]

        for test_case in malformed_requests:
            result = await self.execute_tool(mcp_url, test_case["tool"], test_case["parameters"])

            # Should return error response
            assert result.get("error") is not None
            # Error message should be informative
            assert len(result["error"]) > 10

    @pytest.mark.asyncio
    async def test_template_errors(self, mcp_url):
        """Test template-related error scenarios."""
        template_errors = [
            {
                "name": "nonexistent_template",
                "parameters": {
                    "template_name": "this_template_does_not_exist",
                    "project_name": "test",
                },
            },
            {
                "name": "empty_template_name",
                "parameters": {"template_name": "", "project_name": "test"},
            },
            {
                "name": "null_template_name",
                "parameters": {"template_name": None, "project_name": "test"},
            },
        ]

        for test_case in template_errors:
            result = await self.execute_tool(mcp_url, "create_gaea2_from_template", test_case["parameters"])

            assert result.get("error") is not None
            assert "template" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_connection_type_mismatches(self, mcp_url):
        """Test port type mismatches in connections."""
        type_mismatch_workflows = [
            {
                "name": "mask_to_regular_input",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Gradient", "position": {"X": 0, "Y": 1}},
                        {"id": "3", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                        {"id": "4", "node": "Export", "position": {"X": 2, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "Out",
                            "to_node": "3",
                            "to_port": "In",
                        },
                        {
                            "from_node": "2",
                            "from_port": "Out",
                            "to_node": "3",
                            "to_port": "In",
                        },  # Should be Mask
                        {
                            "from_node": "3",
                            "from_port": "Out",
                            "to_node": "4",
                            "to_port": "In",
                        },
                    ],
                },
            },
            {
                "name": "multiple_inputs_to_single_port",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Perlin", "position": {"X": 0, "Y": 1}},
                        {"id": "3", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                        {"id": "4", "node": "Export", "position": {"X": 2, "Y": 0}},
                    ],
                    "connections": [
                        {
                            "from_node": "1",
                            "from_port": "Out",
                            "to_node": "3",
                            "to_port": "In",
                        },
                        {
                            "from_node": "2",
                            "from_port": "Out",
                            "to_node": "3",
                            "to_port": "In",
                        },  # Duplicate target
                        {
                            "from_node": "3",
                            "from_port": "Out",
                            "to_node": "4",
                            "to_port": "In",
                        },
                    ],
                },
            },
        ]

        for test_case in type_mismatch_workflows:
            result = await self.execute_tool(
                mcp_url,
                "validate_and_fix_workflow",
                {"workflow": test_case["workflow"]},
            )

            # Should detect connection issues
            assert (
                result.get("results", {}).get("is_valid") is False
                or len(result.get("results", {}).get("fixes_applied", [])) > 0
            )

    @pytest.mark.asyncio
    async def test_resource_exhaustion(self, mcp_url):
        """Test handling of resource-intensive requests."""
        # Create a workflow with many nodes to test resource limits
        nodes = []
        connections = []

        # Create 100 nodes
        for i in range(100):
            nodes.append(
                {
                    "id": str(i),
                    "node": "Perlin" if i % 2 == 0 else "Gradient",
                    "position": {"X": i % 10, "Y": i // 10},
                }
            )

            # Create dense connection network
            if i > 0:
                for j in range(max(0, i - 5), i):
                    connections.append(
                        {
                            "from_node": str(j),
                            "from_port": "Out",
                            "to_node": str(i),
                            "to_port": "In" if (i - j) == 1 else "Mask",
                        }
                    )

        result = await self.execute_tool(
            mcp_url,
            "validate_and_fix_workflow",
            {"workflow": {"nodes": nodes, "connections": connections}},
        )

        # Should handle gracefully - either process or timeout with clear error
        assert isinstance(result, dict)
        if result.get("error"):
            assert (
                "timeout" in result["error"].lower()
                or "resource" in result["error"].lower()
                or "limit" in result["error"].lower()
            )


class TestErrorRecovery:
    """Test error recovery and self-healing capabilities."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

    async def execute_tool(self, url: str, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool and return the response."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}/mcp/execute",
                    json={"tool": tool, "parameters": parameters},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    return await response.json()
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__}

    @pytest.mark.asyncio
    async def test_workflow_auto_repair(self, mcp_url):
        """Test automatic workflow repair capabilities."""
        broken_workflows = [
            {
                "name": "missing_positions",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain"},  # Missing position
                        {"id": "2", "node": "Erosion"},  # Missing position
                        {"id": "3", "node": "Export", "position": {"X": 2, "Y": 0}},
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
                },
            },
            {
                "name": "broken_connections",
                "workflow": {
                    "nodes": [
                        {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                        {"id": "2", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                        {"id": "3", "node": "Export", "position": {"X": 2, "Y": 0}},
                    ],
                    "connections": [
                        {"from_node": "1", "to_node": "2"},  # Missing port info
                        {
                            "from_node": "2",
                            "from_port": "InvalidPort",
                            "to_node": "3",
                            "to_port": "In",
                        },
                    ],
                },
            },
        ]

        for test_case in broken_workflows:
            result = await self.execute_tool(
                mcp_url,
                "repair_gaea2_project",
                {"project_data": {"workflow": test_case["workflow"]}},
            )

            assert result.get("repair_successful") is True
            assert len(result.get("repairs_made", [])) > 0

            # Verify repaired workflow is valid
            if "repaired_project" in result:
                validation_result = await self.execute_tool(
                    mcp_url,
                    "validate_and_fix_workflow",
                    {"workflow": result["repaired_project"]["workflow"]},
                )
                assert validation_result.get("results", {}).get("is_valid") is True


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
