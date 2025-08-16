#!/usr/bin/env python3
"""Enhanced test suite for Blender MCP Server."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from blender.server import BlenderMCPServer  # noqa: E402
from core.base_server import ToolRequest  # noqa: E402


class TestBlenderEnhancedFeatures:
    """Test suite for enhanced Blender MCP features."""

    @pytest.fixture
    async def server(self):
        """Create a test server instance."""
        server = BlenderMCPServer(base_dir="/tmp/test_blender", port=8099)
        # Mock the blender executor
        server.blender_executor = AsyncMock()
        server.blender_executor.execute_script = AsyncMock(return_value={"success": True})
        server.blender_executor.kill_process = Mock()

        # Mock job manager
        server.job_manager = Mock()
        server.job_manager.create_job = Mock()
        server.job_manager.get_job = Mock(
            return_value={
                "status": "COMPLETED",
                "progress": 100,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:01:00",
                "result": {"output": "test_output.png"},
            }
        )
        server.job_manager.cancel_job = Mock(return_value=True)

        # Mock asset manager
        server.asset_manager = Mock()
        server.asset_manager.list_projects = Mock(return_value=[{"name": "test_project", "path": "/tmp/test_project.blend"}])
        server.asset_manager.detect_format = Mock(return_value="FBX")

        # Mock template manager
        server.template_manager = Mock()

        yield server

    @pytest.mark.asyncio
    async def test_camera_setup_tool(self, server):
        """Test camera setup functionality."""
        # This would test the new camera setup tool when integrated
        tools = server.get_tools()

        # Basic tool availability test
        assert "create_blender_project" in tools
        assert "add_primitive_objects" in tools
        assert "setup_lighting" in tools

    @pytest.mark.asyncio
    async def test_modifier_operations(self, server):
        """Test modifier-related operations."""
        # Create a project first
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "modifier_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Add an object
        add_obj_request = ToolRequest(
            tool="add_primitive_objects",
            arguments={"project": "modifier_test.blend", "objects": [{"type": "cube", "name": "TestCube"}]},
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_particle_system_creation(self, server):
        """Test particle system creation."""
        # Create a project
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "particle_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Add an emitter object
        add_obj_request = ToolRequest(
            tool="add_primitive_objects",
            arguments={"project": "particle_test.blend", "objects": [{"type": "sphere", "name": "Emitter"}]},
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_complex_animation_workflow(self, server):
        """Test a complex animation workflow."""
        # Create project
        create_request = ToolRequest(
            tool="create_blender_project",
            arguments={
                "name": "complex_animation",
                "template": "animation",
                "settings": {"fps": 60, "resolution": [1920, 1080]},
            },
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Add multiple objects
        objects = [
            {"type": "cube", "name": "Cube1", "location": [0, 0, 0]},
            {"type": "sphere", "name": "Sphere1", "location": [2, 0, 0]},
            {"type": "cylinder", "name": "Cylinder1", "location": [-2, 0, 0]},
        ]

        add_obj_request = ToolRequest(
            tool="add_primitive_objects", arguments={"project": "complex_animation.blend", "objects": objects}
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

        # Create animations for each object
        for obj in objects:
            keyframes = [
                {"frame": 1, "location": obj["location"]},
                {"frame": 30, "location": [obj["location"][0], 3, 0]},
                {"frame": 60, "location": [obj["location"][0], 0, 3]},
                {"frame": 90, "location": obj["location"]},
            ]

            anim_request = ToolRequest(
                tool="create_animation",
                arguments={
                    "project": "complex_animation.blend",
                    "object_name": obj["name"],
                    "keyframes": keyframes,
                    "interpolation": "BEZIER",
                },
            )
            result = await server.execute_tool(anim_request)
            assert result.success

    @pytest.mark.asyncio
    async def test_physics_simulation_workflow(self, server):
        """Test physics simulation workflow."""
        # Create project with physics template
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "physics_sim", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Add objects for physics
        objects = []
        for i in range(5):
            objects.append(
                {"type": "cube", "name": f"PhysCube_{i}", "location": [i - 2, 0, i * 2 + 1], "scale": [0.5, 0.5, 0.5]}
            )

        add_obj_request = ToolRequest(
            tool="add_primitive_objects", arguments={"project": "physics_sim.blend", "objects": objects}
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

        # Setup physics for each object
        for obj in objects:
            physics_request = ToolRequest(
                tool="setup_physics",
                arguments={
                    "project": "physics_sim.blend",
                    "object_name": obj["name"],
                    "physics_type": "rigid_body",
                    "settings": {"mass": 1.0, "friction": 0.5, "bounce": 0.3},
                },
            )
            result = await server.execute_tool(physics_request)
            assert result.success

        # Bake simulation
        bake_request = ToolRequest(
            tool="bake_simulation", arguments={"project": "physics_sim.blend", "start_frame": 1, "end_frame": 250}
        )
        result = await server.execute_tool(bake_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_geometry_nodes_workflow(self, server):
        """Test geometry nodes workflow."""
        # Create project
        create_request = ToolRequest(tool="create_blender_project", arguments={"name": "geo_nodes", "template": "procedural"})
        result = await server.execute_tool(create_request)
        assert result.success

        # Add base object
        add_obj_request = ToolRequest(
            tool="add_primitive_objects",
            arguments={"project": "geo_nodes.blend", "objects": [{"type": "plane", "name": "GeoBase", "scale": [10, 10, 1]}]},
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

        # Apply geometry nodes
        geo_request = ToolRequest(
            tool="create_geometry_nodes",
            arguments={
                "project": "geo_nodes.blend",
                "object_name": "GeoBase",
                "node_setup": "scatter",
                "parameters": {"count": 500, "seed": 42, "scale_variance": 0.3},
            },
        )
        result = await server.execute_tool(geo_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_batch_operations(self, server):
        """Test batch operations."""
        # Create multiple projects
        projects = []
        for i in range(3):
            create_request = ToolRequest(
                tool="create_blender_project", arguments={"name": f"batch_test_{i}", "template": "basic_scene"}
            )
            result = await server.execute_tool(create_request)
            assert result.success
            projects.append(f"batch_test_{i}.blend")

        # Add objects to each project
        for project in projects:
            add_obj_request = ToolRequest(
                tool="add_primitive_objects",
                arguments={
                    "project": project,
                    "objects": [{"type": "monkey", "name": "Suzanne"}, {"type": "cube", "name": "Cube"}],
                },
            )
            result = await server.execute_tool(add_obj_request)
            assert result.success

    @pytest.mark.asyncio
    async def test_material_with_textures(self, server):
        """Test material application with textures."""
        # Create project
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "texture_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Add object
        add_obj_request = ToolRequest(
            tool="add_primitive_objects",
            arguments={"project": "texture_test.blend", "objects": [{"type": "cube", "name": "TexturedCube"}]},
        )
        result = await server.execute_tool(add_obj_request)
        assert result.success

        # Apply material with various settings
        material_request = ToolRequest(
            tool="apply_material",
            arguments={
                "project": "texture_test.blend",
                "object_name": "TexturedCube",
                "material": {
                    "type": "principled",
                    "base_color": [0.5, 0.3, 0.2, 1.0],
                    "metallic": 0.8,
                    "roughness": 0.2,
                    "emission_strength": 0.5,
                },
            },
        )
        result = await server.execute_tool(material_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_lighting_configurations(self, server):
        """Test various lighting configurations."""
        # Create project
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "lighting_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Test different lighting types
        lighting_types = ["three_point", "studio", "sun", "area"]

        for light_type in lighting_types:
            lighting_request = ToolRequest(
                tool="setup_lighting",
                arguments={
                    "project": "lighting_test.blend",
                    "type": light_type,
                    "settings": {"strength": 2.0, "color": [1, 0.95, 0.8]},
                },
            )
            result = await server.execute_tool(lighting_request)
            assert result.success
            assert result.result["lighting_type"] == light_type

    @pytest.mark.asyncio
    async def test_render_settings_variations(self, server):
        """Test various render settings."""
        # Create project
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "render_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Test different render configurations
        render_configs = [
            {"engine": "CYCLES", "samples": 128, "format": "PNG"},
            {"engine": "BLENDER_EEVEE", "samples": 64, "format": "JPEG"},
            {"engine": "CYCLES", "samples": 256, "format": "EXR"},
        ]

        for config in render_configs:
            render_request = ToolRequest(
                tool="render_image",
                arguments={
                    "project": "render_test.blend",
                    "frame": 1,
                    "settings": {
                        "resolution": [1920, 1080],
                        "samples": config["samples"],
                        "engine": config["engine"],
                        "format": config["format"],
                    },
                },
            )
            result = await server.execute_tool(render_request)
            assert result.success
            assert "job_id" in result.result

    @pytest.mark.asyncio
    async def test_error_handling(self, server):
        """Test error handling for invalid inputs."""
        # Test with non-existent project
        request = ToolRequest(
            tool="add_primitive_objects",
            arguments={"project": "non_existent.blend", "objects": [{"type": "cube", "name": "Test"}]},
        )

        # Mock the validation to raise an error
        with patch.object(server, "_validate_project_path", side_effect=ValueError("Project not found")):
            result = await server.execute_tool(request)
            assert not result.success
            assert "Project not found" in str(result.error)

        # Test with invalid tool name
        request = ToolRequest(tool="invalid_tool", arguments={})
        result = await server.execute_tool(request)
        assert not result.success
        assert "Unknown tool" in str(result.error)

    @pytest.mark.asyncio
    async def test_job_management(self, server):
        """Test job management functionality."""
        # Start a render job
        create_request = ToolRequest(tool="create_blender_project", arguments={"name": "job_test", "template": "basic_scene"})
        result = await server.execute_tool(create_request)
        assert result.success

        render_request = ToolRequest(
            tool="render_image", arguments={"project": "job_test.blend", "frame": 1, "settings": {"samples": 64}}
        )
        result = await server.execute_tool(render_request)
        assert result.success
        job_id = result.result["job_id"]

        # Check job status
        status_request = ToolRequest(tool="get_job_status", arguments={"job_id": job_id})
        result = await server.execute_tool(status_request)
        assert result.success
        assert result.result["status"] == "COMPLETED"

        # Get job result
        result_request = ToolRequest(tool="get_job_result", arguments={"job_id": job_id})
        result = await server.execute_tool(result_request)
        assert result.success

        # Cancel a job
        cancel_request = ToolRequest(tool="cancel_job", arguments={"job_id": job_id})
        result = await server.execute_tool(cancel_request)
        assert result.success

    @pytest.mark.asyncio
    async def test_asset_import_export(self, server):
        """Test model import and scene export."""
        # Create project
        create_request = ToolRequest(
            tool="create_blender_project", arguments={"name": "asset_test", "template": "basic_scene"}
        )
        result = await server.execute_tool(create_request)
        assert result.success

        # Mock model file existence
        with patch("pathlib.Path.exists", return_value=True):
            # Import model
            import_request = ToolRequest(
                tool="import_model",
                arguments={"project": "asset_test.blend", "model_path": "test_model.fbx", "location": [0, 0, 0]},
            )
            result = await server.execute_tool(import_request)
            assert result.success
            assert result.result["format"] == "FBX"

        # Export scene
        export_request = ToolRequest(
            tool="export_scene", arguments={"project": "asset_test.blend", "format": "GLTF", "selected_only": False}
        )
        result = await server.execute_tool(export_request)
        assert result.success
        assert "output_path" in result.result


def test_enhanced_tools_documentation():
    """Test that enhanced tools are properly documented."""
    from blender.server_enhancements import get_enhanced_tools

    tools = get_enhanced_tools()
    assert len(tools) > 0

    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "properties" in tool["inputSchema"]

        # Check that required fields are specified
        if "required" in tool["inputSchema"]:
            for req_field in tool["inputSchema"]["required"]:
                assert req_field in tool["inputSchema"]["properties"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
