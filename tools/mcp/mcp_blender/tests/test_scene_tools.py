#!/usr/bin/env python3
"""Tests for scene tools (delete_objects, create_curve)."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from mcp_blender.core.blender_executor import BlenderExecutor
from mcp_blender.server import BlenderMCPServer
from mcp_blender.tools.scene import SceneTools


class TestDeleteObjectsTool:
    """Test suite for delete_objects tool."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create a server instance with temp directories."""
        return BlenderMCPServer(base_dir=str(tmp_path))

    @pytest.fixture
    def mock_executor(self):
        """Create a mock BlenderExecutor."""
        executor = Mock(spec=BlenderExecutor)
        executor.execute_script = AsyncMock(return_value={"success": True})
        executor.kill_process = Mock()
        return executor

    def test_delete_objects_tool_registered(self, server):
        """Test that delete_objects tool is registered."""
        tools = server.get_tools()
        assert "delete_objects" in tools

        tool = tools["delete_objects"]
        assert "description" in tool
        assert "parameters" in tool

        # Check required parameters
        schema = tool["parameters"]
        assert "project" in schema["properties"]

    def test_delete_objects_schema_has_pattern_option(self, server):
        """Test that delete_objects supports pattern matching."""
        tools = server.get_tools()
        schema = tools["delete_objects"]["parameters"]

        # Check for pattern parameter
        assert "pattern" in schema["properties"]
        assert schema["properties"]["pattern"]["type"] == "string"

    def test_delete_objects_schema_has_object_names(self, server):
        """Test that delete_objects has object_names parameter."""
        tools = server.get_tools()
        schema = tools["delete_objects"]["parameters"]["properties"]

        assert "object_names" in schema
        assert schema["object_names"]["type"] == "array"

    def test_delete_objects_schema_has_object_types(self, server):
        """Test that delete_objects has object_types parameter."""
        tools = server.get_tools()
        schema = tools["delete_objects"]["parameters"]["properties"]

        assert "object_types" in schema
        assert "enum" in schema["object_types"]["items"]
        assert "MESH" in schema["object_types"]["items"]["enum"]
        assert "LIGHT" in schema["object_types"]["items"]["enum"]

    @pytest.mark.asyncio
    async def test_delete_objects_handler(self, server, mock_executor, tmp_path):
        """Test delete_objects handler via SceneTools."""
        server.blender_executor = mock_executor
        server.outputs_dir = tmp_path / "outputs"
        jobs_dir = tmp_path / "outputs" / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)

        # Mock executor output_dir attribute
        mock_executor.output_dir = str(tmp_path / "outputs")

        # Mock executor to create result file
        async def mock_execute(script, args, job_id):
            result_file = jobs_dir / f"{job_id}.result"
            result_file.write_text(
                json.dumps({"deleted_objects": ["Cube", "Sphere"]}),
                encoding="utf-8",
            )
            return {"success": True}

        mock_executor.execute_script = AsyncMock(side_effect=mock_execute)

        args = {
            "project": "test.blend",
            "object_names": ["Cube", "Sphere"],
        }

        result = await SceneTools.delete_objects(server, args)

        assert result["success"] is True
        assert "deleted_objects" in result
        mock_executor.execute_script.assert_called_once()


class TestCreateCurveTool:
    """Test suite for create_curve tool."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create a server instance with temp directories."""
        return BlenderMCPServer(base_dir=str(tmp_path))

    @pytest.fixture
    def mock_executor(self):
        """Create a mock BlenderExecutor."""
        executor = Mock(spec=BlenderExecutor)
        executor.execute_script = AsyncMock(return_value={"success": True})
        executor.kill_process = Mock()
        return executor

    def test_create_curve_tool_registered(self, server):
        """Test that create_curve tool is registered."""
        tools = server.get_tools()
        assert "create_curve" in tools

        tool = tools["create_curve"]
        assert "description" in tool
        assert "parameters" in tool

        # Check parameters exist
        schema = tool["parameters"]
        assert "project" in schema["properties"]
        assert "name" in schema["properties"]
        assert "points" in schema["properties"]

    def test_create_curve_schema_parameters(self, server):
        """Test create_curve schema has all expected parameters."""
        tools = server.get_tools()
        schema = tools["create_curve"]["parameters"]["properties"]

        # Required/common parameters
        assert "project" in schema
        assert "name" in schema
        assert "points" in schema

        # Optional parameters
        assert "curve_type" in schema
        assert "bevel_depth" in schema
        assert "closed" in schema
        assert "resolution" in schema

    def test_create_curve_type_enum(self, server):
        """Test that curve_type has valid enum values."""
        tools = server.get_tools()
        schema = tools["create_curve"]["parameters"]["properties"]

        curve_type = schema["curve_type"]
        assert "enum" in curve_type
        assert "BEZIER" in curve_type["enum"]
        assert "POLY" in curve_type["enum"]
        assert "NURBS" in curve_type["enum"]

    @pytest.mark.asyncio
    async def test_create_curve_handler(self, server, mock_executor):
        """Test create_curve handler via SceneTools."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "name": "TestCurve",
            "points": [[0, 0, 0], [1, 1, 1], [2, 0, 0]],
            "curve_type": "BEZIER",
            "bevel_depth": 0.1,
        }

        result = await SceneTools.create_curve(server, args)

        assert result["success"] is True
        assert result["curve_name"] == "TestCurve"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_curve_executor_args(self, server, mock_executor):
        """Test that create_curve passes correct args to executor."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "name": "ArgTestCurve",
            "points": [[0, 0, 0], [1, 0, 0]],
            "curve_type": "NURBS",
            "bevel_depth": 0.05,
        }

        await SceneTools.create_curve(server, args)

        call_args = mock_executor.execute_script.call_args[0]
        assert call_args[0] == "scene_builder.py"

        script_args = call_args[1]
        assert script_args["operation"] == "create_curve"
        assert script_args["name"] == "ArgTestCurve"
        assert script_args["curve_type"] == "NURBS"
        assert script_args["bevel_depth"] == 0.05


class TestSceneToolsModule:
    """Test the SceneTools module directly."""

    def test_scene_tools_has_required_methods(self):
        """Test that SceneTools has the required static methods."""
        assert hasattr(SceneTools, "delete_objects")
        assert hasattr(SceneTools, "create_curve")
        assert callable(getattr(SceneTools, "delete_objects"))
        assert callable(getattr(SceneTools, "create_curve"))

    def test_scene_tools_get_tool_definitions(self):
        """Test that get_tool_definitions returns valid definitions."""
        definitions = SceneTools.get_tool_definitions()

        assert isinstance(definitions, list)
        assert len(definitions) >= 2  # At least delete_objects and create_curve

        # Find and verify delete_objects
        delete_tool = next((t for t in definitions if t["name"] == "delete_objects"), None)
        assert delete_tool is not None
        assert "inputSchema" in delete_tool

        # Find and verify create_curve
        curve_tool = next((t for t in definitions if t["name"] == "create_curve"), None)
        assert curve_tool is not None
        assert "inputSchema" in curve_tool


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
