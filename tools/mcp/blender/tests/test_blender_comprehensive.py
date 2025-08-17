#!/usr/bin/env python3
"""Comprehensive tests for Blender MCP Server."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.mcp.blender.core.blender_executor import BlenderExecutor  # noqa: E402
from tools.mcp.blender.core.job_manager import JobManager  # noqa: E402
from tools.mcp.blender.server import BlenderMCPServer  # noqa: E402
from tools.mcp.core.base_server import ToolRequest  # noqa: E402


class TestBlenderMCPServer:
    """Test suite for Blender MCP Server."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create a server instance with temp directories."""
        server = BlenderMCPServer(base_dir=str(tmp_path))
        return server

    @pytest.fixture
    def mock_executor(self):
        """Create a mock BlenderExecutor."""
        executor = Mock(spec=BlenderExecutor)
        executor.execute_script = AsyncMock(return_value={"success": True})
        executor.kill_process = Mock()
        return executor

    def test_server_initialization(self, tmp_path):
        """Test server initializes correctly."""
        server = BlenderMCPServer(base_dir=str(tmp_path))

        assert server.name == "blender-mcp"
        assert server.version == "1.0.0"
        assert server.port == 8017

        # Check directories are created
        assert (tmp_path / "projects").exists()
        assert (tmp_path / "assets").exists()
        assert (tmp_path / "outputs").exists()
        assert (tmp_path / "templates").exists()
        assert (tmp_path / "temp").exists()

    def test_get_tools(self, server):
        """Test tool registration."""
        tools = server.get_tools()

        expected_tools = [
            "create_blender_project",
            "add_primitive_objects",
            "setup_lighting",
            "apply_material",
            "render_image",
            "render_animation",
            "setup_physics",
            "bake_simulation",
            "create_animation",
            "create_geometry_nodes",
            "get_job_status",
            "get_job_result",
            "cancel_job",
            "list_projects",
            "import_model",
            "export_scene",
        ]

        for tool in expected_tools:
            assert tool in tools
            assert "description" in tools[tool]
            assert "parameters" in tools[tool]

    def test_path_validation_valid_paths(self, server):
        """Test path validation accepts valid paths."""
        # Valid relative paths
        valid_paths = ["project.blend", "subfolder/project.blend", "assets/model.fbx", "textures/image.png"]

        for path in valid_paths:
            result = server._validate_path(path, server.projects_dir, "test")
            assert result.is_absolute()
            assert str(server.projects_dir) in str(result)

    def test_path_validation_invalid_paths(self, server):
        """Test path validation rejects invalid paths."""
        invalid_paths = [
            "/absolute/path.blend",  # Absolute path
            "../parent/file.blend",  # Parent directory
            "../../escape.blend",  # Multiple parent refs
            "./current.blend",  # Current directory ref
            "",  # Empty path
        ]

        for path in invalid_paths:
            with pytest.raises(ValueError):
                server._validate_path(path, server.projects_dir, "test")

    def test_project_path_validation(self, server):
        """Test project path validation."""
        # Test with .blend extension
        path = server._validate_project_path("myproject.blend")
        assert path.name == "myproject.blend"

        # Test without extension (should add .blend)
        path = server._validate_project_path("myproject")
        assert path.name == "myproject.blend"

        # Test with container path (should accept)
        full_path = str(server.projects_dir / "test.blend")
        # Create the file so it passes existence check
        Path(full_path).touch()
        path = server._validate_project_path(full_path)
        assert str(path) == full_path

    @pytest.mark.asyncio
    async def test_create_project(self, server, mock_executor):
        """Test project creation."""
        server.blender_executor = mock_executor

        args = {
            "name": "test_project",
            "template": "basic_scene",
            "settings": {"resolution": [1920, 1080], "fps": 24, "engine": "CYCLES"},
        }

        result = await server._create_project(args)

        assert result["success"] is True
        assert result["project_path"] == "test_project.blend"
        assert "job_id" in result
        assert result["message"] == "Project 'test_project' created successfully"

        # Verify executor was called
        mock_executor.execute_script.assert_called_once()
        call_args = mock_executor.execute_script.call_args[0]
        assert call_args[0] == "scene_builder.py"

    @pytest.mark.asyncio
    async def test_add_primitives(self, server, mock_executor):
        """Test adding primitive objects."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "objects": [
                {"type": "cube", "name": "Cube1", "location": [0, 0, 1]},
                {"type": "sphere", "name": "Sphere1", "location": [2, 0, 1]},
            ],
        }

        result = await server._add_primitives(args)

        assert result["success"] is True
        assert result["objects_added"] == 2
        assert "job_id" in result

        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_material(self, server, mock_executor):
        """Test applying materials."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "Cube",
            "material": {"type": "metal", "roughness": 0.3, "base_color": [0.8, 0.8, 0.8, 1.0]},
        }

        result = await server._apply_material(args)

        assert result["success"] is True
        assert result["object"] == "Cube"
        assert result["material_type"] == "metal"

        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_render_image(self, server, mock_executor):
        """Test image rendering."""
        server.blender_executor = mock_executor

        args = {"project": "test.blend", "frame": 1, "settings": {"samples": 64, "engine": "BLENDER_EEVEE"}}

        result = await server._render_image(args)

        assert result["success"] is True
        assert result["status"] == "QUEUED"
        assert "job_id" in result
        assert result["message"] == "Render job started"

    @pytest.mark.asyncio
    async def test_setup_physics(self, server, mock_executor):
        """Test physics setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "Cube",
            "physics_type": "rigid_body",
            "settings": {"mass": 1.0, "friction": 0.5, "bounce": 0.3},
        }

        result = await server._setup_physics(args)

        assert result["success"] is True
        assert result["object"] == "Cube"
        assert result["physics_type"] == "rigid_body"

        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_animation(self, server, mock_executor):
        """Test animation creation."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "Cube",
            "keyframes": [
                {"frame": 1, "location": [0, 0, 0]},
                {"frame": 30, "location": [5, 0, 0]},
                {"frame": 60, "location": [5, 5, 0]},
            ],
            "interpolation": "BEZIER",
        }

        result = await server._create_animation(args)

        assert result["success"] is True
        assert result["object"] == "Cube"
        assert result["keyframes_count"] == 3

        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_geometry_nodes(self, server, mock_executor):
        """Test geometry nodes creation."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "Plane",
            "node_setup": "scatter",
            "parameters": {"count": 100, "seed": 42, "scale_variance": 0.2},
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["object"] == "Plane"
        assert result["node_setup"] == "scatter"

        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_management(self, server):
        """Test job management functions."""
        # Create a test job
        job_id = "test-job-123"
        server.job_manager.create_job(job_id=job_id, job_type="render", parameters={"test": "params"})

        # Test get_job_status
        result = await server._get_job_status({"job_id": job_id})
        assert result["job_id"] == job_id
        assert result["status"] == "QUEUED"

        # Update job status
        server.job_manager.update_job(job_id, "COMPLETED", progress=100)

        # Test get_job_result
        result = await server._get_job_result({"job_id": job_id})
        assert result["job_id"] == job_id
        assert result["status"] == "COMPLETED"

        # Test cancel_job
        result = await server._cancel_job({"job_id": job_id})
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_projects(self, server):
        """Test listing projects."""
        # Create some test project files
        (server.projects_dir / "project1.blend").touch()
        (server.projects_dir / "project2.blend").touch()
        (server.projects_dir / "subfolder").mkdir()
        (server.projects_dir / "subfolder" / "project3.blend").touch()

        result = await server._list_projects()

        assert result["success"] is True
        assert result["count"] >= 2
        assert any("project1.blend" in p for p in result["projects"])
        assert any("project2.blend" in p for p in result["projects"])

    @pytest.mark.asyncio
    async def test_execute_tool(self, server, mock_executor):
        """Test tool execution through main interface."""
        server.blender_executor = mock_executor

        request = ToolRequest(tool="create_blender_project", arguments={"name": "test", "template": "basic_scene"})

        response = await server.execute_tool(request)

        assert response.success is True
        assert response.result["success"] is True
        assert response.error is None

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, server):
        """Test handling of unknown tool."""
        request = ToolRequest(tool="unknown_tool", arguments={})

        response = await server.execute_tool(request)

        assert response.success is False
        assert response.error == "Unknown tool: unknown_tool"

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, server, mock_executor):
        """Test error handling in tool execution."""
        mock_executor.execute_script = AsyncMock(side_effect=Exception("Test error"))
        server.blender_executor = mock_executor

        request = ToolRequest(tool="create_blender_project", arguments={"name": "test"})

        response = await server.execute_tool(request)

        assert response.success is False
        assert "Test error" in response.error

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, server):
        """Regression test: Ensure path traversal attacks are prevented.

        This test verifies that the critical security fix in _validate_project_path
        is working correctly and prevents directory traversal attacks.
        """
        # Test various path traversal attempts
        malicious_paths = [
            "../../../etc/passwd",
            "../../sensitive_file.blend",
            "/etc/passwd",
            "../" * 10 + "root.blend",
            "legitimate/../../../etc/passwd.blend",
            "projects/../../outside.blend",
            "./../../etc/shadow",
        ]

        for malicious_path in malicious_paths:
            # Try to create a project with path traversal
            request = ToolRequest(tool="create_blender_project", arguments={"name": malicious_path, "template": "basic_scene"})

            response = await server.execute_tool(request)

            # Assert that the request was rejected
            assert response.success is False, f"Path traversal not blocked for: {malicious_path}"
            assert (
                "invalid" in response.error.lower() or "outside" in response.error.lower()
            ), f"Expected security error for path: {malicious_path}, got: {response.error}"

    @pytest.mark.asyncio
    async def test_valid_project_paths(self, server):
        """Test that legitimate project paths are accepted."""
        valid_names = [
            "my_project",
            "test-project-123",
            "animation_2024",
            "scene.final.v2",
        ]

        for valid_name in valid_names:
            request = ToolRequest(tool="create_blender_project", arguments={"name": valid_name, "template": "basic_scene"})

            with patch.object(server.executor, "execute_script", new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = {
                    "success": True,
                    "job_id": f"job-{valid_name}",
                    "project_path": f"/app/projects/{valid_name}.blend",
                }

                response = await server.execute_tool(request)

                # Valid paths should be accepted
                assert response.success is True, f"Valid path rejected: {valid_name}"


class TestBlenderExecutor:
    """Test BlenderExecutor class."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor instance."""
        return BlenderExecutor(blender_path="/usr/bin/blender", output_dir=str(tmp_path / "output"), base_dir=str(tmp_path))

    def test_executor_initialization(self, executor):
        """Test executor initialization."""
        assert executor.blender_path == "/usr/bin/blender"
        assert executor.max_concurrent == 4
        assert len(executor.processes) == 0

    @pytest.mark.asyncio
    async def test_execute_script_mock(self, executor):
        """Test script execution with mocked subprocess."""
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"Success", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            result = await executor.execute_script("test_script.py", {"test": "args"}, "job-123")

            assert result["success"] is True
            assert result["job_id"] == "job-123"

    def test_kill_process(self, executor):
        """Test process termination."""
        # Add a mock process
        mock_process = Mock()
        executor.processes["job-123"] = mock_process

        # Kill the process
        executor.kill_process("job-123")

        mock_process.terminate.assert_called_once()
        assert "job-123" not in executor.processes


class TestJobManager:
    """Test JobManager class."""

    @pytest.fixture
    def job_manager(self, tmp_path):
        """Create JobManager instance."""
        return JobManager(str(tmp_path))

    def test_create_job(self, job_manager):
        """Test job creation."""
        job_id = "test-job"
        job_manager.create_job(job_id=job_id, job_type="render", parameters={"frame": 1})

        job = job_manager.get_job(job_id)
        assert job is not None
        assert job["id"] == job_id
        assert job["type"] == "render"
        assert job["status"] == "QUEUED"
        assert job["parameters"]["frame"] == 1

    def test_update_job(self, job_manager):
        """Test job status update."""
        job_id = "test-job"
        job_manager.create_job(job_id, "render")

        job_manager.update_job(job_id, status="RUNNING", progress=50, message="Rendering...")

        job = job_manager.get_job(job_id)
        assert job["status"] == "RUNNING"
        assert job["progress"] == 50
        assert job["message"] == "Rendering..."

    def test_cancel_job(self, job_manager):
        """Test job cancellation."""
        job_id = "test-job"
        job_manager.create_job(job_id, "render")

        result = job_manager.cancel_job(job_id)
        assert result is True

        job = job_manager.get_job(job_id)
        assert job["status"] == "CANCELLED"

    def test_list_jobs(self, job_manager):
        """Test listing jobs."""
        # Create multiple jobs
        job_manager.create_job("job1", "render")
        job_manager.create_job("job2", "bake")
        job_manager.create_job("job3", "render")

        # List all jobs
        all_jobs = job_manager.list_jobs()
        assert len(all_jobs) == 3

        # List by status
        queued = job_manager.list_jobs(status="QUEUED")
        assert len(queued) == 3

        # Update one and list again
        job_manager.update_job("job1", "COMPLETED")
        completed = job_manager.list_jobs(status="COMPLETED")
        assert len(completed) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
