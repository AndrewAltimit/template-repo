"""
Comprehensive test suite for Gaea2 MCP operations based on reference project analysis.
These tests cover real-world scenarios found in the 10 reference projects.
"""

from typing import Any, Dict

import aiohttp
import pytest


class TestGaea2Operations:
    """Test real Gaea2 operations based on reference projects."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

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
    async def test_common_workflow_pattern(self, mcp_url):
        """Test the most common workflow pattern from references:
        Slump → FractalTerraces → Combine → Shear → Crumble → Erosion2 → Rivers
        """
        workflow = {
            "nodes": [
                {"id": "1", "node": "Slump", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "FractalTerraces", "position": {"X": 1, "Y": 0}},
                {"id": "3", "node": "Combine", "position": {"X": 2, "Y": 0}},
                {"id": "4", "node": "Shear", "position": {"X": 3, "Y": 0}},
                {"id": "5", "node": "Crumble", "position": {"X": 4, "Y": 0}},
                {"id": "6", "node": "Erosion2", "position": {"X": 5, "Y": 0}},
                {"id": "7", "node": "Rivers", "position": {"X": 6, "Y": 0}},
                {"id": "8", "node": "Export", "position": {"X": 7, "Y": 0}},
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
                {
                    "from_node": "4",
                    "from_port": "Out",
                    "to_node": "5",
                    "to_port": "In",
                },
                {
                    "from_node": "5",
                    "from_port": "Out",
                    "to_node": "6",
                    "to_port": "In",
                },
                {
                    "from_node": "6",
                    "from_port": "Out",
                    "to_node": "7",
                    "to_port": "In",
                },
                {
                    "from_node": "7",
                    "from_port": "Out",
                    "to_node": "8",
                    "to_port": "In",
                },
            ],
        }

        result = await self.execute_tool(
            mcp_url,
            "create_gaea2_project",
            {"project_name": "test_common_pattern", "workflow": workflow},
        )

        assert not result.get("error"), f"Failed: {result.get('error')}"
        # Check for success indicators
        assert "project_path" in result or "workflow" in result

    @pytest.mark.asyncio
    async def test_multi_output_nodes(self, mcp_url):
        """Test nodes with multiple outputs like Rivers (5 outputs), Sea (5 outputs)."""
        workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Rivers", "position": {"X": 1, "Y": 0}},
                {"id": "3", "node": "Sea", "position": {"X": 2, "Y": 0}},
                {"id": "4", "node": "Adjust", "position": {"X": 3, "Y": 0}},
                {"id": "5", "node": "Height", "position": {"X": 3, "Y": 1}},
                {"id": "6", "node": "Export", "position": {"X": 4, "Y": 0}},
            ],
            "connections": [
                # Mountain to Rivers
                {
                    "from_node": "1",
                    "from_port": "Out",
                    "to_node": "2",
                    "to_port": "In",
                },
                # Rivers to Sea (main output)
                {
                    "from_node": "2",
                    "from_port": "Out",
                    "to_node": "3",
                    "to_port": "In",
                },
                # Rivers specialized output to Adjust
                {
                    "from_node": "2",
                    "from_port": "Rivers",
                    "to_node": "4",
                    "to_port": "In",
                },
                # Sea Water output to Height Mask
                {
                    "from_node": "3",
                    "from_port": "Water",
                    "to_node": "5",
                    "to_port": "Mask",
                },
                # Final exports
                {
                    "from_node": "4",
                    "from_port": "Out",
                    "to_node": "6",
                    "to_port": "In",
                },
            ],
        }

        result = await self.execute_tool(mcp_url, "validate_and_fix_workflow", {"workflow": workflow})

        assert result.get("results", {}).get("is_valid") is True or len(result.get("results", {}).get("fixes_applied", [])) > 0

    @pytest.mark.asyncio
    async def test_complex_property_nodes(self, mcp_url):
        """Test nodes with complex properties like Range objects, SaveDefinition."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "node": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {
                        "Scale": {"value": 5.0, "min": 1.0, "max": 10.0},
                        "Height": {"value": 1000, "min": 100, "max": 5000},
                    },
                },
                {
                    "id": "2",
                    "node": "Export",
                    "position": {"X": 1, "Y": 0},
                    "properties": {
                        "SaveDefinition": {
                            "Filename": "test_export",
                            "Format": "EXR",
                            "BitDepth": 32,
                        }
                    },
                },
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
            {"project_name": "test_complex_props", "workflow": workflow},
        )

        assert not result.get("error")

    @pytest.mark.asyncio
    async def test_template_variations(self, mcp_url):
        """Test all available templates to ensure they work correctly."""
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

        results = {}
        for template in templates:
            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_from_template",
                {"template_name": template, "project_name": f"test_{template}"},
            )

            results[template] = {
                "success": not result.get("error"),
                "validation_passed": result.get("validation_passed", False),
                "node_count": (len(result.get("workflow", {}).get("nodes", [])) if not result.get("error") else 0),
            }

        # All templates should succeed
        assert all(
            r["success"] for r in results.values()
        ), f"Failed templates: {[t for t, r in results.items() if not r['success']]}"
        assert all(r["validation_passed"] for r in results.values() if r["success"])

    @pytest.mark.asyncio
    async def test_workflow_optimization(self, mcp_url):
        """Test workflow optimization with different modes."""
        # Create a workflow that could benefit from optimization
        workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Erosion", "position": {"X": 1, "Y": 0}},
                {
                    "id": "3",
                    "node": "Erosion",
                    "position": {"X": 2, "Y": 0},
                },  # Duplicate erosion
                {"id": "4", "node": "Blur", "position": {"X": 3, "Y": 0}},
                {
                    "id": "5",
                    "node": "Blur",
                    "position": {"X": 4, "Y": 0},
                },  # Duplicate blur
                {"id": "6", "node": "Export", "position": {"X": 5, "Y": 0}},
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
                {
                    "from_node": "4",
                    "from_port": "Out",
                    "to_node": "5",
                    "to_port": "In",
                },
                {
                    "from_node": "5",
                    "from_port": "Out",
                    "to_node": "6",
                    "to_port": "In",
                },
            ],
        }

        # Test different optimization modes
        modes = ["performance", "quality", "balanced"]

        for mode in modes:
            result = await self.execute_tool(
                mcp_url,
                "optimize_gaea2_properties",
                {"workflow": workflow, "optimization_mode": mode},
            )

            assert not result.get("error"), f"Optimization failed for mode {mode}: {result.get('error')}"
            assert "optimized_workflow" in result
            assert len(result.get("optimizations_applied", [])) > 0

    @pytest.mark.asyncio
    async def test_node_suggestions_context(self, mcp_url):
        """Test node suggestions based on existing workflow context."""
        contexts = [
            {
                "current_nodes": ["Mountain", "Erosion"],
                "goal": "add water features",
                "expected_suggestions": ["Rivers", "Sea", "Lakes"],
            },
            {
                "current_nodes": ["Volcano", "Lava"],
                "goal": "add cooling effects",
                "expected_suggestions": ["Thermal", "Snow", "Frost"],
            },
            {
                "current_nodes": ["Desert", "Dunes"],
                "goal": "add rock formations",
                "expected_suggestions": ["Strata", "Fold", "Stratify"],
            },
        ]

        for context in contexts:
            result = await self.execute_tool(
                mcp_url,
                "suggest_gaea2_nodes",
                {
                    "current_nodes": context["current_nodes"],
                    "workflow_goal": context["goal"],
                },
            )

            assert not result.get("error")
            assert "suggestions" in result or "suggestions" in result.get("results", {})

            # Check if at least one expected suggestion appears
            suggested_nodes = [s["node"] for s in result["suggestions"]]
            assert any(expected in suggested_nodes for expected in context["expected_suggestions"])

    @pytest.mark.asyncio
    async def test_workflow_repair(self, mcp_url):
        """Test workflow repair functionality with damaged workflows."""
        # Create a damaged workflow
        damaged_workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain"},  # Missing position
                {
                    "id": "2",
                    "node": "InvalidNode",
                    "position": {"X": 1, "Y": 0},
                },  # Invalid node
                {"id": "3", "node": "Erosion", "position": {"X": 2, "Y": 0}},
                # Missing Export node
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
                },  # Invalid target
            ],
        }

        result = await self.execute_tool(
            mcp_url,
            "repair_gaea2_project",
            {"project_data": {"workflow": damaged_workflow}},
        )

        assert not result.get("error")
        assert result.get("repair_successful") is True
        assert len(result.get("repairs_made", [])) > 0

        # Verify repaired workflow is valid
        repaired = result.get("repaired_project", {}).get("workflow", {})
        assert any(n["node"] == "Export" for n in repaired.get("nodes", []))

    @pytest.mark.asyncio
    async def test_pattern_analysis(self, mcp_url):
        """Test workflow pattern analysis for different terrain types."""
        terrain_types = ["mountain", "desert", "coastal", "volcanic", "arctic"]

        for terrain_type in terrain_types:
            result = await self.execute_tool(mcp_url, "analyze_workflow_patterns", {"workflow_type": terrain_type})

            assert not result.get("error")
            assert "common_patterns" in result or "common_patterns" in result.get("results", {})
            assert "recommended_nodes" in result or "recommended_nodes" in result.get("results", {})
            assert "typical_connections" in result

            # Verify recommendations are appropriate
            if terrain_type == "mountain":
                assert any("Mountain" in node for node in result["recommended_nodes"])
            elif terrain_type == "desert":
                assert any("Desert" in node or "Dunes" in node for node in result["recommended_nodes"])
            elif terrain_type == "coastal":
                assert any("Sea" in node or "Coast" in node for node in result["recommended_nodes"])

    @pytest.mark.asyncio
    async def test_variable_propagation(self, mcp_url):
        """Test variable/seed propagation across nodes (from Level2 reference)."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "node": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {"Seed": "@Seed"},  # Variable reference
                },
                {
                    "id": "2",
                    "node": "Erosion",
                    "position": {"X": 1, "Y": 0},
                    "properties": {"Seed": "@Seed"},  # Same variable
                },
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
            "variables": {"Seed": {"value": 12345, "type": "int"}},
        }

        result = await self.execute_tool(
            mcp_url,
            "create_gaea2_project",
            {"project_name": "test_variables", "workflow": workflow},
        )

        assert not result.get("error")
        assert result.get("success") is True


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions specific to Gaea2."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

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
    async def test_maximum_node_limit(self, mcp_url):
        """Test with maximum nodes (based on Level7 with 22 nodes)."""
        nodes = []
        connections = []

        # Create 25 nodes to test beyond observed maximum
        node_types = ["Mountain", "Erosion", "Perlin", "Gradient", "Combine"]

        for i in range(25):
            nodes.append(
                {
                    "id": str(i),
                    "node": node_types[i % len(node_types)],
                    "position": {"X": i % 5, "Y": i // 5},
                }
            )

            if i > 0 and i < 24:  # Connect in chain, leaving last for Export
                connections.append(
                    {
                        "from_node": str(i - 1),
                        "from_port": "Out",
                        "to_node": str(i),
                        "to_port": "In",
                    }
                )

        # Add Export as final node
        nodes.append({"id": "25", "node": "Export", "position": {"X": 0, "Y": 5}})
        connections.append({"from_node": "23", "from_port": "Out", "to_node": "25", "to_port": "In"})

        result = await self.execute_tool(
            mcp_url,
            "create_gaea2_project",
            {
                "project_name": "test_max_nodes",
                "workflow": {"nodes": nodes, "connections": connections},
            },
        )

        # Should either succeed or provide meaningful error
        if result.get("error"):
            assert "node" in result["error"].lower() or "limit" in result["error"].lower()
        else:
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_deeply_nested_combines(self, mcp_url):
        """Test deeply nested Combine nodes (common pattern in references)."""
        workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Perlin", "position": {"X": 0, "Y": 1}},
                {"id": "3", "node": "Combine", "position": {"X": 1, "Y": 0}},
                {"id": "4", "node": "Gradient", "position": {"X": 1, "Y": 1}},
                {"id": "5", "node": "Combine", "position": {"X": 2, "Y": 0}},
                {"id": "6", "node": "Voronoi", "position": {"X": 2, "Y": 1}},
                {"id": "7", "node": "Combine", "position": {"X": 3, "Y": 0}},
                {"id": "8", "node": "Export", "position": {"X": 4, "Y": 0}},
            ],
            "connections": [
                # First combine
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
                    "to_port": "Input2",
                },
                # Second combine
                {
                    "from_node": "3",
                    "from_port": "Out",
                    "to_node": "5",
                    "to_port": "In",
                },
                {
                    "from_node": "4",
                    "from_port": "Out",
                    "to_node": "5",
                    "to_port": "Input2",
                },
                # Third combine
                {
                    "from_node": "5",
                    "from_port": "Out",
                    "to_node": "7",
                    "to_port": "In",
                },
                {
                    "from_node": "6",
                    "from_port": "Out",
                    "to_node": "7",
                    "to_port": "Input2",
                },
                # Export
                {
                    "from_node": "7",
                    "from_port": "Out",
                    "to_node": "8",
                    "to_port": "In",
                },
            ],
        }

        result = await self.execute_tool(mcp_url, "validate_and_fix_workflow", {"workflow": workflow})

        assert result.get("results", {}).get("is_valid") is True

    @pytest.mark.asyncio
    async def test_special_port_connections(self, mcp_url):
        """Test all special port types found in references."""
        workflow = {
            "nodes": [
                {"id": "1", "node": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "node": "Rivers", "position": {"X": 1, "Y": 0}},
                {"id": "3", "node": "Sea", "position": {"X": 2, "Y": 0}},
                {"id": "4", "node": "Erosion2", "position": {"X": 3, "Y": 0}},
                {"id": "5", "node": "Height", "position": {"X": 1, "Y": 1}},
                {"id": "6", "node": "Adjust", "position": {"X": 2, "Y": 1}},
                {"id": "7", "node": "Export", "position": {"X": 4, "Y": 0}},
            ],
            "connections": [
                # Standard connections
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
                # Special port connections
                {
                    "from_node": "2",
                    "from_port": "Rivers",
                    "to_node": "5",
                    "to_port": "In",
                },
                {
                    "from_node": "3",
                    "from_port": "Water",
                    "to_node": "6",
                    "to_port": "Mask",
                },
                {
                    "from_node": "4",
                    "from_port": "Wear",
                    "to_node": "7",
                    "to_port": "In",
                },
            ],
        }

        result = await self.execute_tool(mcp_url, "validate_and_fix_workflow", {"workflow": workflow})

        # These connections might need fixing but should be handled gracefully
        assert isinstance(result, dict)
        assert "error" not in result or "crash" not in result.get("error", "").lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
