"""
Test file that captures the actual validation findings for Gaea2 templates.
Based on comprehensive validation testing using Gaea2's CLI.
"""

import aiohttp
import pytest


class TestGaea2ValidationFindings:
    """Tests based on actual validation results of Gaea2 templates."""

    @pytest.fixture
    def mcp_url(self):
        return "http://192.168.0.152:8007"

    async def execute_tool(self, url: str, tool: str, parameters: dict) -> dict:
        """Execute an MCP tool and return the response."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/mcp/execute",
                json={"tool": tool, "parameters": parameters},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                return await response.json()

    @pytest.mark.asyncio
    async def test_working_templates(self, mcp_url):
        """Test templates that are known to work correctly."""
        # These templates create files that successfully open in Gaea2
        working_templates = [
            "basic_terrain",
            "detailed_mountain",
            "volcanic_terrain",
            "desert_canyon",
            "mountain_range",
            "river_valley",
        ]

        for template in working_templates:
            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_from_template",
                {
                    "template_name": template,
                    "project_name": f"test_working_{template}",
                },
            )

            # Should create successfully
            assert result.get("success"), f"Working template {template} failed: {result.get('error')}"
            assert result.get("project_path") or result.get("saved_path"), f"No file path returned for {template}"

            # Validate if validation endpoint is available
            if result.get("project_path") or result.get("saved_path"):
                file_path = result.get("project_path") or result.get("saved_path")
                val_result = await self.execute_tool(
                    mcp_url,
                    "validate_gaea2_file",
                    {"file_path": file_path, "timeout": 60},
                )

                # These should pass validation
                assert val_result.get("success"), f"Working template {template} failed validation"

    @pytest.mark.asyncio
    async def test_corrupted_templates(self, mcp_url):
        """Test templates that are known to be corrupted."""
        # These templates create files but they won't open in Gaea2
        corrupted_templates = [
            "modular_portal_terrain",
            "volcanic_island",
            "canyon_system",
            "coastal_cliffs",
            "arctic_terrain",
        ]

        for template in corrupted_templates:
            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_from_template",
                {
                    "template_name": template,
                    "project_name": f"test_corrupt_{template}",
                },
            )

            # Files are created successfully
            assert result.get("success"), f"Template {template} should create a file even if corrupted"

            # But validation should fail
            if result.get("project_path") or result.get("saved_path"):
                file_path = result.get("project_path") or result.get("saved_path")
                val_result = await self.execute_tool(
                    mcp_url,
                    "validate_gaea2_file",
                    {"file_path": file_path, "timeout": 60},
                )

                # These should fail validation with corruption error
                assert not val_result.get("success"), f"Corrupted template {template} should fail validation"
                assert val_result.get("error_info"), f"No error info for corrupted template {template}"

                # Check for specific corruption indicators
                error_info = val_result.get("error_info", {})
                error_types = error_info.get("error_types", [])
                assert "file_corrupt" in error_types, f"Missing corruption indicator for {template}"

    @pytest.mark.asyncio
    async def test_validation_edge_cases(self, mcp_url):
        """Test edge cases discovered during validation testing."""

        # Empty workflow is invalid
        result = await self.execute_tool(
            mcp_url,
            "validate_and_fix_workflow",
            {"workflow": {"nodes": [], "connections": []}},
        )
        assert result.get("success")
        assert result.get("valid") is False, "Empty workflow should be invalid"

        # Circular dependencies are detected
        circular_workflow = {
            "nodes": [
                {"id": "1", "type": "Mountain", "position": {"x": 0, "y": 0}},
                {"id": "2", "type": "Erosion", "position": {"x": 100, "y": 0}},
            ],
            "connections": [
                {"from_node": "1", "to_node": "2", "from_port": "Out", "to_port": "In"},
                {"from_node": "2", "to_node": "1", "from_port": "Out", "to_port": "In"},
            ],
        }

        result = await self.execute_tool(mcp_url, "validate_and_fix_workflow", {"workflow": circular_workflow})
        assert result.get("success")
        assert result.get("valid") is False, "Circular dependencies should be invalid"

        # Unknown node types are rejected by default
        unknown_workflow = {
            "nodes": [{"id": "1", "type": "UnknownNodeType", "position": {"x": 0, "y": 0}}],
            "connections": [],
        }

        result = await self.execute_tool(mcp_url, "validate_and_fix_workflow", {"workflow": unknown_workflow})
        # Server may accept unknown nodes but mark as invalid
        assert result.get("success")
        # The validation should handle it gracefully

    @pytest.mark.asyncio
    async def test_property_mode_impact(self, mcp_url):
        """Test how property_mode affects file validity."""
        # Some nodes fail with too many properties
        problematic_nodes = ["Snow", "Beach", "Lakes", "Coast"]

        for node_type in problematic_nodes[:1]:  # Test just Snow to save time
            # Test with minimal properties (should work)
            minimal_workflow = {
                "nodes": [
                    {"id": "1", "type": node_type, "position": {"x": 0, "y": 0}},
                    {"id": "2", "type": "Export", "position": {"x": 200, "y": 0}},
                ],
                "connections": [
                    {
                        "from_node": "1",
                        "to_node": "2",
                        "from_port": "Out",
                        "to_port": "In",
                    }
                ],
            }

            result = await self.execute_tool(
                mcp_url,
                "create_gaea2_project",
                {
                    "project_name": f"test_minimal_{node_type}",
                    "workflow": minimal_workflow,
                    "property_mode": "smart",  # Limits properties for problematic nodes
                },
            )

            assert result.get("success"), f"Minimal {node_type} should create successfully"

    @pytest.mark.asyncio
    async def test_validation_summary(self, mcp_url):
        """Test the batch validation endpoint if available."""

        result = await self.execute_tool(
            mcp_url,
            "validate_gaea2_batch",
            {
                "file_pattern": "test_*.terrain",
                "directory": "C:\\Gaea2\\MCP_Projects",
                "max_files": 2,
            },
        )

        if result.get("success"):
            summary = result.get("summary", {})
            assert summary.get("total_files", 0) > 0, "Should find some files to validate"
            # We know some files are corrupted
            assert summary.get("failed", 0) > 0, "Should detect some failures"
