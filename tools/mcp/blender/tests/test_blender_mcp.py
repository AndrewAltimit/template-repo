"""Tests for Blender MCP Server."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from blender.core.asset_manager import AssetManager  # noqa: E402
from blender.core.blender_executor import BlenderExecutor  # noqa: E402
from blender.core.job_manager import JobManager  # noqa: E402
from blender.core.templates import TemplateManager  # noqa: E402
from blender.server import BlenderMCPServer  # noqa: E402


class TestBlenderMCPServer:
    """Test Blender MCP server functionality."""

    @pytest.fixture
    def server(self):
        """Create server instance."""
        with patch("blender.server.BlenderExecutor"):
            with patch("blender.server.JobManager"):
                with patch("blender.server.AssetManager"):
                    with patch("blender.server.TemplateManager"):
                        server = BlenderMCPServer()
                        server.setup_directories = Mock()
                        return server

    def test_server_initialization(self, server):
        """Test server initializes correctly."""
        assert server.name == "blender-mcp"
        assert server.port == 8017
        assert server.blender_executor is not None
        assert server.job_manager is not None
        assert server.asset_manager is not None
        assert server.template_manager is not None

    def test_tool_descriptions(self, server):
        """Test tool descriptions are properly defined."""
        tools = server.get_tool_descriptions()

        # Check essential tools are present
        tool_names = [tool["name"] for tool in tools]
        assert "create_blender_project" in tool_names
        assert "render_image" in tool_names
        assert "render_animation" in tool_names
        assert "setup_physics" in tool_names
        assert "create_animation" in tool_names
        assert "create_geometry_nodes" in tool_names

        # Verify tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_create_project(self, server):
        """Test project creation."""
        server.job_manager.create_job = Mock(return_value={"id": "test-job"})
        server.blender_executor.execute_script = AsyncMock(return_value={"success": True})

        result = await server._create_project(
            {
                "name": "test_project",
                "template": "basic_scene",
                "settings": {"resolution": [1920, 1080]},
            }
        )

        assert result["success"] is True
        assert "test_project.blend" in result["project_path"]
        assert result["job_id"] is not None

    @pytest.mark.asyncio
    async def test_render_image(self, server):
        """Test image rendering."""
        server.job_manager.create_job = Mock(return_value={"id": "render-job"})
        server.blender_executor.execute_script = AsyncMock(return_value={"success": True})

        result = await server._render_image(
            {
                "project": "/app/projects/test.blend",
                "frame": 1,
                "settings": {"engine": "CYCLES", "samples": 128},
            }
        )

        assert result["success"] is True
        assert result["status"] == "QUEUED"
        assert result["job_id"] is not None

    @pytest.mark.asyncio
    async def test_setup_physics(self, server):
        """Test physics setup."""
        server.blender_executor.execute_script = AsyncMock(return_value={"success": True})

        result = await server._setup_physics(
            {
                "project": "/app/projects/test.blend",
                "object_name": "Cube",
                "physics_type": "rigid_body",
                "settings": {"mass": 2.0},
            }
        )

        assert result["success"] is True
        assert result["object"] == "Cube"
        assert result["physics_type"] == "rigid_body"

    @pytest.mark.asyncio
    async def test_job_status(self, server):
        """Test job status retrieval."""
        mock_job = {
            "status": "RUNNING",
            "progress": 50,
            "message": "Rendering",
            "created_at": "2024-01-01T00:00:00",
        }
        server.job_manager.get_job = Mock(return_value=mock_job)

        result = await server._get_job_status({"job_id": "test-job"})

        assert result["status"] == "RUNNING"
        assert result["progress"] == 50
        assert result["job_id"] == "test-job"

    @pytest.mark.asyncio
    async def test_list_projects(self, server):
        """Test listing projects."""
        mock_projects = [
            {"name": "project1", "path": "/app/projects/project1.blend"},
            {"name": "project2", "path": "/app/projects/project2.blend"},
        ]
        server.asset_manager.list_projects = Mock(return_value=mock_projects)

        result = await server._list_projects()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["projects"]) == 2


class TestJobManager:
    """Test job manager functionality."""

    @pytest.fixture
    def job_manager(self, tmp_path):
        """Create job manager instance."""
        return JobManager(str(tmp_path))

    def test_create_job(self, job_manager):
        """Test job creation."""
        job = job_manager.create_job(job_id="test-123", job_type="render", parameters={"frame": 1})

        assert job["id"] == "test-123"
        assert job["type"] == "render"
        assert job["status"] == "QUEUED"
        assert job["progress"] == 0

    def test_update_job(self, job_manager):
        """Test job update."""
        job_manager.create_job("test-123", "render", {})

        success = job_manager.update_job("test-123", status="RUNNING", progress=50, message="Processing")

        assert success is True

        job = job_manager.get_job("test-123")
        assert job["status"] == "RUNNING"
        assert job["progress"] == 50
        assert job["message"] == "Processing"

    def test_cancel_job(self, job_manager):
        """Test job cancellation."""
        job_manager.create_job("test-123", "render", {})

        success = job_manager.cancel_job("test-123")
        assert success is True

        job = job_manager.get_job("test-123")
        assert job["status"] == "CANCELLED"

    def test_list_jobs(self, job_manager):
        """Test listing jobs."""
        job_manager.create_job("job1", "render", {})
        job_manager.create_job("job2", "simulation", {})
        job_manager.update_job("job1", status="COMPLETED")

        all_jobs = job_manager.list_jobs()
        assert len(all_jobs) == 2

        completed_jobs = job_manager.list_jobs(status="COMPLETED")
        assert len(completed_jobs) == 1
        assert completed_jobs[0]["id"] == "job1"


class TestAssetManager:
    """Test asset manager functionality."""

    @pytest.fixture
    def asset_manager(self, tmp_path):
        """Create asset manager instance."""
        projects_dir = tmp_path / "projects"
        assets_dir = tmp_path / "assets"
        return AssetManager(str(projects_dir), str(assets_dir))

    def test_list_projects(self, asset_manager, tmp_path):
        """Test listing projects."""
        # Create test projects
        projects_dir = tmp_path / "projects"
        (projects_dir / "project1.blend").touch()
        (projects_dir / "project2.blend").touch()

        projects = asset_manager.list_projects()

        assert len(projects) == 2
        assert projects[0]["name"] in ["project1", "project2"]

    def test_detect_format(self, asset_manager):
        """Test file format detection."""
        assert asset_manager.detect_format("model.fbx") == "FBX"
        assert asset_manager.detect_format("scene.obj") == "OBJ"
        assert asset_manager.detect_format("asset.gltf") == "GLTF"
        assert asset_manager.detect_format("texture.png") == "PNG"
        assert asset_manager.detect_format("image.jpg") == "JPEG"

    def test_import_asset(self, asset_manager, tmp_path):
        """Test asset import."""
        # Create source file
        source = tmp_path / "source.fbx"
        source.touch()

        result = asset_manager.import_asset(str(source), "models", "imported_model")

        assert result["success"] is True
        assert "imported_model.fbx" in result["asset_path"]

    def test_create_project_backup(self, asset_manager, tmp_path):
        """Test project backup creation."""
        # Create test project
        project = tmp_path / "projects" / "test.blend"
        project.parent.mkdir(exist_ok=True)
        project.touch()

        backup_path = asset_manager.create_project_backup(str(project))

        assert backup_path is not None
        assert "backup" in backup_path
        assert Path(backup_path).exists()


class TestTemplateManager:
    """Test template manager functionality."""

    @pytest.fixture
    def template_manager(self, tmp_path):
        """Create template manager instance."""
        return TemplateManager(str(tmp_path))

    def test_list_templates(self, template_manager):
        """Test listing templates."""
        templates = template_manager.list_templates()

        # Check built-in templates exist
        template_ids = [t["id"] for t in templates]
        assert "empty" in template_ids
        assert "basic_scene" in template_ids
        assert "studio_lighting" in template_ids
        assert "procedural" in template_ids
        assert "animation" in template_ids

    def test_get_template(self, template_manager):
        """Test getting template configuration."""
        template = template_manager.get_template("basic_scene")

        assert template is not None
        assert template["name"] == "Basic Scene"
        assert "settings" in template
        assert template["settings"]["engine"] == "CYCLES"

    def test_create_from_template(self, template_manager, tmp_path):
        """Test creating project from template."""
        output = tmp_path / "new_project.blend"

        result = template_manager.create_from_template("basic_scene", str(output), {"samples": 256})

        assert result["success"] is True
        assert result["template_id"] == "basic_scene"

    def test_save_as_template(self, template_manager, tmp_path):
        """Test saving project as template."""
        # Create source project
        source = tmp_path / "source.blend"
        source.touch()

        result = template_manager.save_as_template(str(source), "Custom Template", "My custom template")

        assert result["success"] is True
        assert result["template_id"] == "custom_template"

        # Verify template was added
        template = template_manager.get_template("custom_template")
        assert template is not None
        assert template["name"] == "Custom Template"


class TestBlenderExecutor:
    """Test Blender executor functionality."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        with patch("blender.core.blender_executor.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "blender"
                executor = BlenderExecutor("/usr/bin/blender")
                return executor

    @pytest.mark.asyncio
    async def test_execute_script(self, executor, tmp_path):
        """Test script execution."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.pid = 12345
            mock_exec.return_value = mock_process

            with patch("tempfile.NamedTemporaryFile"):
                with patch("os.remove"):
                    result = await executor.execute_script("render.py", {"operation": "render_image"}, "job-123")

            assert result["success"] is True
            assert result["job_id"] == "job-123"
            assert result["pid"] == 12345

    def test_kill_process(self, executor):
        """Test process termination."""
        mock_process = Mock()
        executor.processes["job-123"] = mock_process

        success = executor.kill_process("job-123")

        assert success is True
        mock_process.terminate.assert_called_once()

    def test_validate_installation(self, executor):
        """Test Blender installation validation."""
        with patch.object(executor, "get_blender_version", return_value="4.0.0"):
            assert executor.validate_installation() is True

        with patch.object(executor, "get_blender_version", return_value=None):
            assert executor.validate_installation() is False


@pytest.mark.integration
class TestIntegration:
    """Integration tests for Blender MCP server."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow from project creation to rendering."""
        # This test would require actual Blender installation
        # Mark as integration test and skip in CI
        pytest.skip("Requires Blender installation")
