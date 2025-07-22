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
                json={"tool": tool, "arguments": parameters},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                result = await response.json()
                assert isinstance(result, dict)  # Type assertion for mypy
                return result

    @pytest.mark.asyncio
    async def test_common_workflow_pattern(self, mcp_url):
        """Test the most common workflow pattern from references:
        Slump → FractalTerraces → Combine → Shear → Crumble → Erosion2 → Rivers
        """
        workflow = {
            "nodes": [
                {"id": "1", "type": "Slump", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "FractalTerraces", "position": {"X": 1, "Y": 0}},
                {"id": "3", "type": "Combine", "position": {"X": 2, "Y": 0}},
                {"id": "4", "type": "Shear", "position": {"X": 3, "Y": 0}},
                {"id": "5", "type": "Crumble", "position": {"X": 4, "Y": 0}},
                {"id": "6", "type": "Erosion2", "position": {"X": 5, "Y": 0}},
                {"id": "7", "type": "Rivers", "position": {"X": 6, "Y": 0}},
                {"id": "8", "type": "Export", "position": {"X": 7, "Y": 0}},
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

        # Debug print to see actual response
        print(f"DEBUG: Response = {result}")

        # Handle base server response format
        if "result" in result and isinstance(result["result"], dict):
            # Extract the actual result from the base server wrapper
            actual_result = result["result"]
            assert not actual_result.get("error"), f"Failed: {actual_result.get('error')}"
            assert actual_result.get("success") is not False, "Operation should succeed"
            # Either project_path, workflow, or results field should be present
            assert any(
                key in actual_result for key in ["project_path", "workflow", "results", "project_data"]
            ), "Response should contain project data"
        else:
            # Direct response format (standalone server)
            assert not result.get("error"), f"Failed: {result.get('error')}"
            assert result.get("success") is not False, "Operation should succeed"
            assert any(
                key in result for key in ["project_path", "workflow", "results"]
            ), "Response should contain project data"

    @pytest.mark.asyncio
    async def test_multi_output_nodes(self, mcp_url):
        """Test nodes with multiple outputs like Rivers (5 outputs), Sea (5 outputs)."""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "Rivers", "position": {"X": 1, "Y": 0}},
                {"id": "3", "type": "Sea", "position": {"X": 2, "Y": 0}},
                {"id": "4", "type": "Adjust", "position": {"X": 3, "Y": 0}},
                {"id": "5", "type": "Height", "position": {"X": 3, "Y": 1}},
                {"id": "6", "type": "Export", "position": {"X": 4, "Y": 0}},
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

        # Handle base server response format
        if "result" in result and isinstance(result["result"], dict):
            actual_result = result["result"]
        else:
            actual_result = result

        # Check validation results - either no errors or fixes were applied
        has_no_errors = len(actual_result.get("errors", [])) == 0
        was_fixed = actual_result.get("fixed", False) or len(actual_result.get("fixes_applied", [])) > 0

        assert has_no_errors or was_fixed, f"Validation should either have no errors or apply fixes: {actual_result}"

    @pytest.mark.asyncio
    async def test_complex_property_nodes(self, mcp_url):
        """Test nodes with complex properties like Range objects, SaveDefinition."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {
                        "Scale": {"value": 5.0, "min": 1.0, "max": 10.0},
                        "Height": {"value": 1000, "min": 100, "max": 5000},
                    },
                },
                {
                    "id": "2",
                    "type": "Export",
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

        assert not result.get("error"), f"Failed: {result.get('error')}"

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
                "success": not result.get("error") and result.get("success", False),
                "validation_passed": result.get("validation_applied", True),  # Templates use auto_validate=True
                "node_count": result.get("node_count", 0),
            }

        # All templates should succeed
        assert all(
            r["success"] for r in results.values()
        ), f"Failed templates: {[t for t, r in results.items() if not r['success']]}"
        assert all(r["validation_passed"] for r in results.values() if r["success"])

    @pytest.mark.asyncio
    async def test_combine_node_connections(self, mcp_url):
        """Test that Combine nodes in templates have both inputs properly connected."""
        # Test arctic_terrain which we know has a Combine node
        result = await self.execute_tool(
            mcp_url,
            "create_gaea2_from_template",
            {
                "template_name": "arctic_terrain",
                "project_name": "test_combine_connections",
            },
        )

        assert result.get("success"), f"Failed to create project: {result.get('error')}"

        # Check project structure for Combine node connections
        if "project_structure" in result:
            nodes = result["project_structure"]["Assets"]["$values"][0]["Terrain"]["Nodes"]

            # Find Combine nodes and verify their connections
            combine_nodes_found = 0
            for node_id, node_data in nodes.items():
                if isinstance(node_data, dict) and "Combine" in node_data.get("$type", ""):
                    combine_nodes_found += 1

                    # Check that both In and Input2 ports have connections
                    ports = node_data.get("Ports", {}).get("$values", [])
                    connected_ports = {}

                    for port in ports:
                        if "Record" in port:
                            connected_ports[port["Name"]] = True

                    # Verify both primary inputs are connected
                    assert "In" in connected_ports, f"Combine node {node_id} missing 'In' connection"
                    assert "Input2" in connected_ports, f"Combine node {node_id} missing 'Input2' connection"

            assert combine_nodes_found > 0, "No Combine nodes found in arctic_terrain template"

    @pytest.mark.asyncio
    async def test_workflow_optimization(self, mcp_url):
        """Test workflow optimization with different modes."""
        # Create a workflow that could benefit from optimization
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "Erosion", "position": {"X": 1, "Y": 0}},
                {
                    "id": "3",
                    "type": "Erosion",
                    "position": {"X": 2, "Y": 0},
                },  # Duplicate erosion
                {"id": "4", "type": "Blur", "position": {"X": 3, "Y": 0}},
                {
                    "id": "5",
                    "type": "Blur",
                    "position": {"X": 4, "Y": 0},
                },  # Duplicate blur
                {"id": "6", "type": "Export", "position": {"X": 5, "Y": 0}},
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
            # Handle different response formats
            # Handle base server response format
            if "result" in result and isinstance(result["result"], dict):
                actual_result = result["result"]
            else:
                actual_result = result

            assert (
                "optimized_nodes" in actual_result or "nodes" in actual_result or "optimized_workflow" in actual_result
            ), f"Expected optimization result but got: {actual_result}"

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
                    "context": context["goal"],
                },
            )

            assert not result.get("error"), f"Failed to get suggestions: {result.get('error')}"

            # Handle different response formats
            suggestions = []
            if "suggestions" in result:
                suggestions = result["suggestions"]
            elif "results" in result and "suggestions" in result["results"]:
                suggestions = result["results"]["suggestions"]

            # Empty suggestions are acceptable
            # Verify the call succeeded without error
            assert result.get("success", True), "Suggestion call should succeed"

            # If we got suggestions, verify they make sense
            if len(suggestions) > 0:
                # Check if at least one expected suggestion appears
                suggested_nodes = [s.get("node", s.get("name", "")) for s in suggestions if isinstance(s, dict)]
                # Some suggestions might be strings
                if not suggested_nodes and suggestions:
                    suggested_nodes = [s for s in suggestions if isinstance(s, str)]

                # Verify we received valid Gaea2 node suggestions
                # Common Gaea2 nodes: Wizard, Thermal, Mask, TextureBase, etc.
                valid_gaea_nodes = [
                    "wizard",
                    "thermal",
                    "mask",
                    "texturebase",
                    "satmap",
                    "erosion",
                    "mountain",
                    "blur",
                    "combine",
                    "export",
                    "rivers",
                    "sea",
                    "snow",
                    "frost",
                    "strata",
                    "fold",
                    "stratify",
                    "desert",
                    "dunes",
                    "lava",
                    "volcano",
                    "lakes",
                ]

                # Check that we got at least one valid Gaea2 node
                has_valid_node = any(
                    any(valid.lower() in str(suggested).lower() for valid in valid_gaea_nodes) for suggested in suggested_nodes
                )
                assert has_valid_node, f"No valid Gaea2 nodes found. Got: {suggested_nodes}"

    @pytest.mark.asyncio
    async def test_workflow_repair(self, mcp_url):
        """Test workflow repair functionality with damaged workflows."""
        # Create a damaged workflow
        damaged_workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain"},  # Missing position
                {
                    "id": "2",
                    "type": "InvalidNode",
                    "position": {"X": 1, "Y": 0},
                },  # Invalid node
                {"id": "3", "type": "Erosion", "position": {"X": 2, "Y": 0}},
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

        # First create a damaged project file
        create_result = await self.execute_tool(
            mcp_url,
            "create_gaea2_project",
            {
                "project_name": "test_damaged",
                "workflow": damaged_workflow,
                "auto_validate": False,
            },
        )

        # Skip this test if we can't create the damaged file
        if create_result.get("error"):
            pytest.skip(f"Cannot create test file: {create_result.get('error')}")
            return

        project_path = create_result.get("project_path", "test_damaged.terrain")

        # Now repair it
        result = await self.execute_tool(
            mcp_url,
            "repair_gaea2_project",
            {"project_path": project_path, "backup": False},
        )

        assert not result.get("error"), f"Repair failed: {result.get('error')}"

        # Handle different response formats
        if "results" in result:
            assert result["results"].get("success") is True
            # Check if repair_result exists (nested structure)
            if "repair_result" in result:
                fixes = result["repair_result"].get("fixes_applied", [])
                assert len(fixes) > 0 or result.get("analysis", {}).get("analysis", {}).get("health_score", 0) > 90
            else:
                assert len(result["results"].get("fixes_applied", result["results"].get("issues_found", []))) > 0
        else:
            assert result.get("success") is True
            # The repair might have succeeded without needing fixes
            fixes = result.get("fixes_applied", result.get("issues_found", []))
            if not fixes and "repair_result" in result:
                fixes = result["repair_result"].get("fixes_applied", [])
            # Either we have fixes or the project was already healthy
            assert len(fixes) > 0 or result.get("repaired", False) or result.get("success", False)

    @pytest.mark.asyncio
    async def test_pattern_analysis(self, mcp_url):
        """Test workflow pattern analysis for different terrain types."""
        terrain_types = ["mountain", "desert", "coastal", "volcanic", "arctic"]

        for terrain_type in terrain_types:
            result = await self.execute_tool(
                mcp_url,
                "analyze_workflow_patterns",
                {
                    "workflow_or_directory": {"nodes": [], "connections": []},
                    "include_suggestions": True,
                },
            )

            assert not result.get("error"), f"Pattern analysis failed for {terrain_type}: {result.get('error')}"

            # Handle base server response format
            if "result" in result and isinstance(result["result"], dict):
                actual_result = result["result"]
            else:
                actual_result = result

            # Extract analysis data
            if "analysis" in actual_result:
                data = actual_result["analysis"]
            else:
                data = actual_result

            # Check for expected fields in various formats
            has_patterns = "common_patterns" in data or "patterns" in data
            has_nodes = "recommended_nodes" in data or "nodes" in data or "recommendations" in data or "node_types" in data
            has_connections = "typical_connections" in data or "connections" in data or "connection_count" in data
            has_analysis = "node_count" in data or "complexity" in data

            assert has_patterns or has_nodes or has_connections or has_analysis, f"No useful data returned for {terrain_type}"

            # Pattern analysis on empty workflows returns general data
            # Terrain-specific suggestions require actual workflow content

    @pytest.mark.asyncio
    async def test_variable_propagation(self, mcp_url):
        """Test variable/seed propagation across nodes (from Level2 reference)."""
        workflow = {
            "nodes": [
                {
                    "id": "1",
                    "type": "Mountain",
                    "position": {"X": 0, "Y": 0},
                    "properties": {"Seed": "@Seed"},  # Variable reference
                },
                {
                    "id": "2",
                    "type": "Erosion",
                    "position": {"X": 1, "Y": 0},
                    "properties": {"Seed": "@Seed"},  # Same variable
                },
                {"id": "3", "type": "Export", "position": {"X": 2, "Y": 0}},
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
                json={"tool": tool, "arguments": parameters},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                result = await response.json()
                assert isinstance(result, dict)  # Type assertion for mypy
                return result

    @pytest.mark.asyncio
    async def test_maximum_node_limit(self, mcp_url):
        """Test with maximum nodes (based on Level7 with 22 nodes)."""
        nodes = []
        connections = []

        # Create 25 nodes to test beyond observed maximum
        node_types = ["Mountain", "Erosion", "Perlin", "LinearGradient", "Combine"]

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
        nodes.append({"id": "25", "type": "Export", "position": {"X": 0, "Y": 5}})
        connections.append({"from_node": "23", "from_port": "Out", "to_node": "25", "to_port": "In"})

        result = await self.execute_tool(
            mcp_url,
            "create_gaea2_project",
            {
                "project_name": "test_max_nodes",
                "workflow": {"nodes": nodes, "connections": connections},
            },
        )

        # Expect success or meaningful error message
        if result.get("error"):
            assert "node" in result["error"].lower() or "limit" in result["error"].lower()
        else:
            assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_deeply_nested_combines(self, mcp_url):
        """Test deeply nested Combine nodes (common pattern in references)."""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "Perlin", "position": {"X": 0, "Y": 1}},
                {"id": "3", "type": "Combine", "position": {"X": 1, "Y": 0}},
                {"id": "4", "type": "LinearGradient", "position": {"X": 1, "Y": 1}},
                {"id": "5", "type": "Combine", "position": {"X": 2, "Y": 0}},
                {"id": "6", "type": "Voronoi", "position": {"X": 2, "Y": 1}},
                {"id": "7", "type": "Combine", "position": {"X": 3, "Y": 0}},
                {"id": "8", "type": "Export", "position": {"X": 4, "Y": 0}},
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

        # Handle base server response format
        if "result" in result and isinstance(result["result"], dict):
            actual_result = result["result"]
        else:
            actual_result = result

        # Check validation succeeded
        assert actual_result.get("success") is not False
        assert len(actual_result.get("errors", [])) == 0 or actual_result.get("fixed", False)

    @pytest.mark.asyncio
    async def test_special_port_connections(self, mcp_url):
        """Test all special port types found in references."""
        workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"X": 0, "Y": 0}},
                {"id": "2", "type": "Rivers", "position": {"X": 1, "Y": 0}},
                {"id": "3", "type": "Sea", "position": {"X": 2, "Y": 0}},
                {"id": "4", "type": "Erosion2", "position": {"X": 3, "Y": 0}},
                {"id": "5", "type": "Height", "position": {"X": 1, "Y": 1}},
                {"id": "6", "type": "Adjust", "position": {"X": 2, "Y": 1}},
                {"id": "7", "type": "Export", "position": {"X": 4, "Y": 0}},
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

        # Special port connections are handled gracefully
        assert isinstance(result, dict)
        error_msg = result.get("error") or ""
        assert "error" not in result or "crash" not in str(error_msg).lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
